from __future__ import annotations

import logging
import re
import time
from collections.abc import Mapping
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel

from backend.app.api.deps import ensure_read_allowed
from backend.app.governance.settings import get_settings
from backend.app.observability.perf_logging import timed_api_call
from backend.app.observability.response_cache import market_home_response_cache
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.livermore_candidate_history_service import (
    livermore_candidate_history_cycle_proxy_backtest_envelope,
    livermore_candidate_history_envelope,
    livermore_candidate_history_portfolio_backtest_envelope,
    livermore_candidate_history_strategy_optimization_envelope,
    livermore_candidate_history_strategy_score_envelope,
)
from backend.app.services.livermore_gate_supplement_compute_service import (
    LivermoreGateSupplementRefreshConflictError,
    LivermoreGateSupplementRefreshQueueError,
    livermore_gate_supplement_refresh_status,
    queue_gate_supplement_refresh,
)
from backend.app.services.livermore_position_snapshot_dispatch_service import (
    queue_livermore_position_snapshot_csv,
    queue_livermore_position_snapshot_rows,
)
from backend.app.services.livermore_sector_rank_series_service import livermore_sector_rank_series_envelope
from backend.app.services.livermore_signal_confluence_service import (
    livermore_signal_confluence_envelope,
)
from backend.app.services.livermore_stock_detail_service import livermore_stock_detail_envelope
from backend.app.services.macro_bond_linkage_service import get_macro_context_v1

# Route-support helpers moved to the service layer. Re-import them into this
# module namespace so existing monkeypatch/import contracts keep working;
# endpoints keep calling them through unqualified module globals.
from backend.app.services.market_data_livermore_route_support import (
    STOCK_ANALYSIS_WORKBENCH_CACHE_TTL_SECONDS,
    _actionable_unsupported_output_count,
    _active_data_gap_count,
    _active_diagnostic_count,
    _cached_livermore_signal_confluence,
    _cached_stock_analysis_workbench,
    _count_array,
    _count_array_or_mapping,
    _count_mapping,
    _invalidate_livermore_response_cache,
    _is_known_livermore_policy_pause,
    _item_count,
    _livermore_candidate_history_cache_key,
    _livermore_cycle_proxy_backtest_cache_key,
    _livermore_macro_context_v1_for_date,
    _livermore_portfolio_backtest_cache_key,
    _livermore_sector_rank_series_cache_key,
    _livermore_stock_detail_cache_key,
    _livermore_strategy_cache_key,
    _livermore_strategy_optimization_cache_key,
    _livermore_strategy_score_cache_key,
    _livermore_workbench_candidate_history_summary,
    _livermore_workbench_cycle_proxy_summary,
    _livermore_workbench_portfolio_summary,
    _livermore_workbench_sector_series_summary,
    _livermore_workbench_signal_summary,
    _livermore_workbench_strategy_optimization_summary,
    _livermore_workbench_strategy_score_summary,
    _livermore_workbench_strategy_summary,
    _livermore_workbench_summary,
    _mapping,
    _optional_count,
    _optional_text,
    _present,
    _resolve_livermore_position_csv_path,
    _selected_pretrade_external_read,
    _stock_analysis_workbench_cache_key,
    _stock_heavyweight_trends_cache_key,
    _stock_kline_analysis_cache_key,
    _sum_optional_counts,
    _with_livermore_workbench_summary,
)
from backend.app.services.market_data_livermore_route_support import (
    _livermore_signal_confluence_cache_key as _livermore_signal_confluence_cache_key,
)
from backend.app.services.market_data_livermore_route_support import (
    _qualified_livermore_signal_confluence as _qualified_livermore_signal_confluence_support,
)
from backend.app.services.market_data_livermore_service import (
    livermore_strategy_envelope_from_catalog,
    theme_overlay_fingerprint,
    theme_overlay_reader_from_settings,
)
from backend.app.services.pretrade_qualification import (
    STRATEGY_CALCULATION_MODE as STRATEGY_CALCULATION_MODE,
)
from backend.app.services.pretrade_qualification import (
    canonical_pretrade_confluence_projection_sha256 as canonical_pretrade_confluence_projection_sha256,
)
from backend.app.services.stock_analysis_workbench_service import (
    DEFAULT_INCLUDE_KEYS,
    WORKBENCH_CACHE_VERSION,
    WORKBENCH_RULE_VERSION,
    stock_analysis_workbench_envelope,
)
from backend.app.services.stock_heavyweight_trend_service import stock_heavyweight_trend_envelope
from backend.app.services.stock_kline_analysis_service import stock_kline_analysis_envelope
from backend.app.services.stock_official_evidence_service import stock_official_evidence_envelope
from backend.app.services.stock_portfolio_construction_service import (
    SUPPORTED_PORTFOLIO_ID,
    stock_portfolio_construction_envelope,
)

__all__ = [
    "DEFAULT_INCLUDE_KEYS",
    "STOCK_ANALYSIS_WORKBENCH_CACHE_TTL_SECONDS",
    "WORKBENCH_CACHE_VERSION",
    "WORKBENCH_RULE_VERSION",
    "_actionable_unsupported_output_count",
    "_active_data_gap_count",
    "_active_diagnostic_count",
    "_count_array",
    "_count_array_or_mapping",
    "_count_mapping",
    "_invalidate_livermore_response_cache",
    "_is_known_livermore_policy_pause",
    "_item_count",
    "_livermore_workbench_candidate_history_summary",
    "_livermore_workbench_cycle_proxy_summary",
    "_livermore_workbench_portfolio_summary",
    "_livermore_workbench_sector_series_summary",
    "_livermore_workbench_signal_summary",
    "_livermore_workbench_strategy_optimization_summary",
    "_livermore_workbench_strategy_score_summary",
    "_livermore_workbench_strategy_summary",
    "_livermore_workbench_summary",
    "_mapping",
    "_optional_count",
    "_optional_text",
    "_present",
    "_stock_analysis_workbench_cache_key",
    "_sum_optional_counts",
    "get_macro_context_v1",
    "stock_analysis_workbench_envelope",
]

# Keep existing module hooks while the implementations remain service-owned.
_theme_overlay_reader_from_settings = theme_overlay_reader_from_settings
_theme_overlay_fingerprint = theme_overlay_fingerprint

router = APIRouter(prefix="/ui/market-data", tags=["market-data"])
logger = logging.getLogger(__name__)
_STOCK_CODE_LIVERMORE_PATTERN = re.compile(r"^[0-9A-Za-z.\-]{1,16}$")


class LivermorePositionSnapshotRequest(BaseModel):
    as_of_date: str
    csv_path: str


class LivermoreManualPositionInput(BaseModel):
    stock_code: str
    stock_name: str | None = None
    entry_cost: float
    bars_since_entry: int | None = None
    entry_date: str | None = None
    position_quantity: float | None = None
    position_status: str = "ACTIVE"


class LivermoreManualPositionSnapshotRequest(BaseModel):
    as_of_date: str
    positions: list[LivermoreManualPositionInput]


def _ensure_livermore_position_import_allowed(*, settings: object, auth: AuthContext) -> None:
    ensure_user_allowed(
        auth=auth,
        settings=settings,
        resource="market_data.livermore_position_snapshot",
        action="import",
    )


def _ensure_livermore_read_allowed(*, settings: object, auth: AuthContext) -> None:
    ensure_read_allowed(
        auth,
        "market_data.livermore",
        settings=settings,
        allow_dev_fallback=True,
        authorize=ensure_user_allowed,
    )


def _ensure_livermore_gate_supplement_refresh_allowed(*, settings: object, auth: AuthContext) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="market_data.livermore_gate_supplement",
            action="refresh",
        )
    except PermissionError as exc:
        logger.warning(
            "Livermore gate-supplement refresh forbidden error_type=%s detail=%s",
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=403,
            detail="LIVERMORE_GATE_SUPPLEMENT_FORBIDDEN：无权执行该刷新操作",
        ) from exc
    except RuntimeError as exc:
        logger.error(
            "Livermore gate-supplement authorization unavailable error_type=%s detail=%s",
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail="LIVERMORE_GATE_SUPPLEMENT_AUTH_UNAVAILABLE：权限服务暂不可用，请稍后重试",
        ) from exc


@router.get("/livermore")
def livermore_strategy(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    as_of_date: str | None = Query(None),
) -> dict[str, object]:
    if as_of_date is not None:
        try:
            date.fromisoformat(as_of_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    _ensure_livermore_read_allowed(settings=settings, auth=auth)
    duckdb_path = str(settings.duckdb_path)
    catalog_file = settings.choice_stock_catalog_file
    theme_overlay_reader = _theme_overlay_reader_from_settings(settings)
    overlay_fingerprint = _theme_overlay_fingerprint(theme_overlay_reader)
    return market_home_response_cache.get_or_build(
        _livermore_strategy_cache_key(
            duckdb_path=duckdb_path,
            catalog_file=catalog_file,
            as_of_date=as_of_date,
            theme_overlay_fingerprint=overlay_fingerprint,
        ),
        lambda: _with_livermore_workbench_summary(
            livermore_strategy_envelope_from_catalog(
                duckdb_path=duckdb_path,
                as_of_date=as_of_date,
                choice_stock_catalog_file=catalog_file,
                theme_overlay_reader=theme_overlay_reader,
            ),
            summary_kind="strategy",
        ),
    )


@router.get("/stock-analysis/workbench")
def stock_analysis_workbench(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    response: Response,
    as_of_date: str | None = Query(None),
    include: str | None = Query(None),
    sector_window_days: int = Query(default=20, ge=2, le=60),
    top_k: int = Query(default=10, ge=1, le=50),
) -> dict[str, object]:
    if as_of_date is not None:
        try:
            date.fromisoformat(as_of_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    _ensure_livermore_read_allowed(settings=settings, auth=auth)
    started_at = time.perf_counter()
    payload, cache_status, compute_ms, overlay_ms, cache_ms = _cached_stock_analysis_workbench(
        settings=settings,
        as_of_date=as_of_date,
        include=include,
        sector_window_days=sector_window_days,
        top_k=top_k,
    )
    total_ms = (time.perf_counter() - started_at) * 1000
    wait_ms = cache_ms if cache_status == "wait" else 0.0
    response.headers["Server-Timing"] = (
        f'workbench;dur={total_ms:.3f}, overlay;dur={overlay_ms:.3f}, '
        f'cache;desc="{cache_status}";dur={cache_ms:.3f}, wait;dur={wait_ms:.3f}, compute;dur={compute_ms:.3f}'
    )
    return payload


@router.get("/stock-analysis/portfolio-construction")
def stock_analysis_portfolio_construction(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    portfolio_id: str = Query(..., min_length=7),
    as_of_date: str | None = Query(None),
) -> dict[str, object]:
    """Return a proposal-only stock target projection from the cached workbench."""
    normalized_portfolio_id = portfolio_id.strip()
    if normalized_portfolio_id != SUPPORTED_PORTFOLIO_ID:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid portfolio_id. Phase 2A supports only {SUPPORTED_PORTFOLIO_ID}.",
        )
    if as_of_date is not None:
        try:
            as_of_date = date.fromisoformat(as_of_date.strip()).isoformat()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    _ensure_livermore_read_allowed(settings=settings, auth=auth)
    # Reuse the workbench response/cache so this projection does not trigger a
    # second stock strategy scan for the same page context.
    workbench_payload, _cache_status, _compute_ms, _overlay_ms, _cache_ms = _cached_stock_analysis_workbench(
        settings=settings,
        as_of_date=as_of_date,
        include=None,
        sector_window_days=20,
        top_k=10,
    )
    return stock_portfolio_construction_envelope(
        portfolio_id=normalized_portfolio_id,
        workbench_envelope=workbench_payload,
        as_of_date=as_of_date,
    )


@router.get("/livermore/signal-confluence")
def livermore_signal_confluence(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    as_of_date: str | None = Query(None),
) -> dict[str, object]:
    if as_of_date is not None:
        try:
            date.fromisoformat(as_of_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    _ensure_livermore_read_allowed(settings=settings, auth=auth)
    duckdb_path = str(settings.duckdb_path)
    catalog_file = settings.choice_stock_catalog_file
    theme_overlay_reader = _theme_overlay_reader_from_settings(settings)
    overlay_fingerprint = _theme_overlay_fingerprint(theme_overlay_reader)
    (
        pretrade_qualification,
        captured_external_inputs,
        target_date,
        authority_fingerprint,
    ) = _selected_pretrade_external_read(
        catalog_file=catalog_file,
        as_of_date=as_of_date,
    )
    return _cached_livermore_signal_confluence(
        duckdb_path=duckdb_path,
        as_of_date=as_of_date,
        catalog_file=catalog_file,
        theme_overlay_reader=theme_overlay_reader,
        theme_overlay_fingerprint=overlay_fingerprint,
        selected_pretrade_read=(
            pretrade_qualification,
            captured_external_inputs,
            target_date,
            authority_fingerprint,
        ),
        qualified_builder=_qualified_livermore_signal_confluence,
    )


def _qualified_livermore_signal_confluence(
    *,
    duckdb_path: str,
    as_of_date: str | None,
    catalog_file: object,
    theme_overlay_reader: Any,
    pretrade_qualification: Mapping[str, object] | None = None,
    captured_external_inputs: Mapping[str, object] | None = None,
    target_date: str | None = None,
) -> dict[str, object]:
    return _qualified_livermore_signal_confluence_support(
        duckdb_path=duckdb_path,
        as_of_date=as_of_date,
        catalog_file=catalog_file,
        theme_overlay_reader=theme_overlay_reader,
        pretrade_qualification=pretrade_qualification,
        captured_external_inputs=captured_external_inputs,
        target_date=target_date,
        envelope_builder=livermore_signal_confluence_envelope,
    )

@router.post("/livermore/position-snapshot")
def materialize_position_snapshot(
    request: LivermorePositionSnapshotRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    try:
        date.fromisoformat(request.as_of_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    try:
        _ensure_livermore_position_import_allowed(settings=settings, auth=auth)
    except PermissionError as exc:
        logger.warning(
            "Livermore position snapshot import forbidden error_type=%s detail=%s",
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=403,
            detail="LIVERMORE_POSITION_SNAPSHOT_FORBIDDEN：无权执行该导入操作",
        ) from exc
    except RuntimeError as exc:
        logger.error(
            "Livermore position snapshot authorization unavailable error_type=%s detail=%s",
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail="LIVERMORE_POSITION_SNAPSHOT_AUTH_UNAVAILABLE：权限服务暂不可用，请稍后重试",
        ) from exc

    try:
        csv_path = _resolve_livermore_position_csv_path(
            data_input_root=settings.data_input_root,
            csv_path=request.csv_path,
        )
    except ValueError as exc:
        logger.warning(
            "Livermore position snapshot CSV path rejected error_type=%s detail=%s",
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=422,
            detail="LIVERMORE_POSITION_CSV_PATH_INVALID：数据文件路径无效，请检查后重试",
        ) from exc

    if not csv_path.exists():
        logger.warning("Livermore position snapshot CSV not found path=%s", csv_path)
        raise HTTPException(
            status_code=404,
            detail="LIVERMORE_POSITION_CSV_NOT_FOUND：数据文件缺失，请联系管理员刷新数据源",
        )

    try:
        return queue_livermore_position_snapshot_csv(
            as_of_date=request.as_of_date,
            csv_path=csv_path,
            duckdb_path=settings.duckdb_path,
        )
    except Exception as exc:
        logger.error(
            "Livermore position snapshot queue failed error_type=%s detail=%s",
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail="LIVERMORE_POSITION_SNAPSHOT_QUEUE_FAILED：任务提交失败，请稍后重试",
        ) from exc


@router.post("/livermore/position-snapshot/manual")
def materialize_manual_position_snapshot(
    request: LivermoreManualPositionSnapshotRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    try:
        date.fromisoformat(request.as_of_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    try:
        _ensure_livermore_position_import_allowed(settings=settings, auth=auth)
    except PermissionError as exc:
        logger.warning(
            "Livermore manual position snapshot import forbidden error_type=%s detail=%s",
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=403,
            detail="LIVERMORE_POSITION_SNAPSHOT_FORBIDDEN：无权执行该导入操作",
        ) from exc
    except RuntimeError as exc:
        logger.error(
            "Livermore manual position snapshot authorization unavailable error_type=%s detail=%s",
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail="LIVERMORE_POSITION_SNAPSHOT_AUTH_UNAVAILABLE：权限服务暂不可用，请稍后重试",
        ) from exc

    try:
        return queue_livermore_position_snapshot_rows(
            as_of_date=request.as_of_date,
            rows=[position.model_dump() for position in request.positions],
            duckdb_path=settings.duckdb_path,
        )
    except Exception as exc:
        logger.error(
            "Livermore manual position snapshot queue failed error_type=%s detail=%s",
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail="LIVERMORE_POSITION_SNAPSHOT_QUEUE_FAILED：任务提交失败，请稍后重试",
        ) from exc


@router.post("/livermore/refresh-gate-supplement", status_code=202)
def refresh_gate_supplement(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    as_of_date: str | None = Query(None),
    lookback_days: int = Query(default=30, ge=7, le=365),
) -> dict[str, object]:
    """Queue worker-owned breadth and Livermore gate-supplement materialization."""
    parsed_date: date | None = None
    if as_of_date is not None:
        try:
            parsed_date = date.fromisoformat(as_of_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    _ensure_livermore_gate_supplement_refresh_allowed(settings=settings, auth=auth)
    try:
        result = queue_gate_supplement_refresh(
            duckdb_path=str(settings.duckdb_path),
            governance_path=str(settings.governance_path),
            as_of_date=parsed_date,
            lookback_days=lookback_days,
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        logger.warning(
            "Livermore gate-supplement refresh request rejected error_type=%s detail=%s",
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=422,
            detail="LIVERMORE_GATE_SUPPLEMENT_REQUEST_INVALID：刷新请求参数无效，请检查后重试",
        ) from exc
    except LivermoreGateSupplementRefreshConflictError as exc:
        logger.warning(
            "Livermore gate-supplement refresh conflict error_type=%s detail=%s",
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=409,
            detail="LIVERMORE_GATE_SUPPLEMENT_REFRESH_CONFLICT：刷新任务已在执行，请稍后重试",
        ) from exc
    except LivermoreGateSupplementRefreshQueueError as exc:
        logger.error(
            "Livermore gate-supplement refresh queue failed error_type=%s detail=%s",
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail="LIVERMORE_GATE_SUPPLEMENT_QUEUE_FAILED：刷新任务提交失败，请稍后重试",
        ) from exc
    except Exception as exc:
        logger.error(
            "Livermore gate-supplement refresh failed error_type=%s detail=%s",
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail="LIVERMORE_GATE_SUPPLEMENT_REFRESH_FAILED：刷新服务暂不可用，请稍后重试",
        ) from exc

    return result


@router.get("/livermore/refresh-gate-supplement/status")
def refresh_gate_supplement_status(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    run_id: str = Query(..., min_length=1),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_livermore_read_allowed(settings=settings, auth=auth)
    if not run_id.strip():
        raise HTTPException(status_code=422, detail="run_id must be non-empty.")
    try:
        return livermore_gate_supplement_refresh_status(
            settings.governance_path,
            run_id=run_id,
        )
    except ValueError as exc:
        logger.warning(
            "Livermore gate-supplement refresh run not found run_id=%s error_type=%s detail=%s",
            run_id,
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=404,
            detail="LIVERMORE_GATE_SUPPLEMENT_RUN_NOT_FOUND：未找到对应的刷新任务",
        ) from exc


@router.get("/livermore/stock-detail")
def livermore_stock_detail(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    stock_code: str = Query(..., min_length=1, max_length=16),
    as_of_date: str | None = Query(None),
    lookback: int = Query(60, ge=5, le=250),
) -> dict[str, object]:
    cleaned = stock_code.strip()
    if not _STOCK_CODE_LIVERMORE_PATTERN.fullmatch(cleaned):
        raise HTTPException(
            status_code=422,
            detail="Invalid stock_code. Allowed characters: letters, digits, '.', '-'.",
        )
    parsed_as_of: date | None = None
    if as_of_date is not None:
        text = as_of_date.strip()
        if not text:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.")
        try:
            parsed_as_of = date.fromisoformat(text)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    _ensure_livermore_read_allowed(settings=settings, auth=auth)
    duckdb_path = str(settings.duckdb_path)
    as_of_text = parsed_as_of.isoformat() if parsed_as_of is not None else None
    return market_home_response_cache.get_or_build(
        _livermore_stock_detail_cache_key(
            duckdb_path=duckdb_path,
            stock_code=cleaned,
            as_of_date=as_of_text,
            lookback=lookback,
        ),
        lambda: timed_api_call(
            "/ui/market-data/livermore/stock-detail",
            lambda: livermore_stock_detail_envelope(
                duckdb_path=duckdb_path,
                stock_code=cleaned,
                as_of_date=parsed_as_of,
                lookback=lookback,
            ),
        ),
    )


@router.get("/stock-analysis/kline-analysis")
def stock_kline_analysis(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    stock_code: str = Query(..., min_length=1, max_length=16),
    as_of_date: str | None = Query(None),
    lookback: int = Query(60, ge=30, le=250),
) -> dict[str, object]:
    cleaned = stock_code.strip()
    if not _STOCK_CODE_LIVERMORE_PATTERN.fullmatch(cleaned):
        raise HTTPException(
            status_code=422,
            detail="Invalid stock_code. Allowed characters: letters, digits, '.', '-'.",
        )
    parsed_as_of: date | None = None
    if as_of_date is not None:
        text = as_of_date.strip()
        if not text:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.")
        try:
            parsed_as_of = date.fromisoformat(text)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    _ensure_livermore_read_allowed(settings=settings, auth=auth)
    duckdb_path = str(settings.duckdb_path)
    as_of_text = parsed_as_of.isoformat() if parsed_as_of is not None else None
    return market_home_response_cache.get_or_build(
        _stock_kline_analysis_cache_key(
            duckdb_path=duckdb_path,
            stock_code=cleaned,
            as_of_date=as_of_text,
            lookback=lookback,
        ),
        lambda: timed_api_call(
            "/ui/market-data/stock-analysis/kline-analysis",
            lambda: stock_kline_analysis_envelope(
                duckdb_path=duckdb_path,
                stock_code=cleaned,
                as_of_date=parsed_as_of,
                lookback=lookback,
            ),
        ),
    )


@router.get("/stock-analysis/heavyweight-trends")
def stock_heavyweight_trends(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    response: Response,
    as_of_date: str | None = Query(None),
    window_days: int = Query(default=20, ge=5, le=60),
    sector_limit: int = Query(default=8, ge=1, le=20),
    stocks_per_sector: int = Query(default=3, ge=1, le=10),
) -> dict[str, object]:
    parsed_as_of: date | None = None
    if as_of_date is not None:
        text = as_of_date.strip()
        if not text:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.")
        try:
            parsed_as_of = date.fromisoformat(text)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    _ensure_livermore_read_allowed(settings=settings, auth=auth)
    duckdb_path = str(settings.duckdb_path)
    started_at = time.perf_counter()
    payload = market_home_response_cache.get_or_build(
        _stock_heavyweight_trends_cache_key(
            duckdb_path=duckdb_path,
            as_of_date=None if parsed_as_of is None else parsed_as_of.isoformat(),
            window_days=window_days,
            sector_limit=sector_limit,
            stocks_per_sector=stocks_per_sector,
        ),
        lambda: timed_api_call(
            "/ui/market-data/stock-analysis/heavyweight-trends",
            lambda: stock_heavyweight_trend_envelope(
                duckdb_path=duckdb_path,
                as_of_date=parsed_as_of,
                window_days=window_days,
                sector_limit=sector_limit,
                stocks_per_sector=stocks_per_sector,
            ),
        ),
    )
    total_ms = (time.perf_counter() - started_at) * 1000
    response.headers["Server-Timing"] = f"heavyweight-trends;dur={total_ms:.3f}"
    return payload


@router.get("/stock-analysis/official-evidence")
def stock_official_evidence(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    response: Response,
    stock_code: str = Query(..., min_length=1, max_length=16),
    as_of_date: str | None = Query(None),
    limit_per_type: int = Query(default=10, ge=1, le=20),
) -> dict[str, object]:
    cleaned = stock_code.strip()
    if not _STOCK_CODE_LIVERMORE_PATTERN.fullmatch(cleaned):
        raise HTTPException(
            status_code=422,
            detail="Invalid stock_code. Allowed characters: letters, digits, '.', '-'.",
        )
    if as_of_date is None:
        parsed_as_of = date.today()
    else:
        text = as_of_date.strip()
        if not text:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.")
        try:
            parsed_as_of = date.fromisoformat(text)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    _ensure_livermore_read_allowed(settings=settings, auth=auth)
    started_at = time.perf_counter()
    payload = timed_api_call(
        "/ui/market-data/stock-analysis/official-evidence",
        lambda: stock_official_evidence_envelope(
            duckdb_path=str(settings.duckdb_path),
            stock_code=cleaned,
            as_of_date=parsed_as_of,
            limit_per_type=limit_per_type,
        ),
    )
    total_ms = (time.perf_counter() - started_at) * 1000
    response.headers["Server-Timing"] = f"official-evidence;dur={total_ms:.3f}, query;dur={total_ms:.3f}"
    return payload


@router.get("/livermore/candidate-history")
def livermore_candidate_history(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    stock_code: str | None = Query(default=None, max_length=16),
    snapshot_from: str | None = Query(default=None),
    snapshot_to: str | None = Query(default=None),
    evaluation_as_of_date: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, object]:
    if stock_code is not None and stock_code.strip():
        cleaned_code = stock_code.strip()
        if not _STOCK_CODE_LIVERMORE_PATTERN.fullmatch(cleaned_code):
            raise HTTPException(
                status_code=422,
                detail="Invalid stock_code. Allowed characters: letters, digits, '.', '-'.",
            )
    for label, value in (("snapshot_from", snapshot_from), ("snapshot_to", snapshot_to)):
        if value is None or not str(value).strip():
            continue
        text = str(value).strip()
        try:
            date.fromisoformat(text[:10])
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid {label}. Expected YYYY-MM-DD.",
            ) from exc

    normalized_evaluation_date: str | None = None
    if evaluation_as_of_date is not None:
        text = evaluation_as_of_date.strip()
        if not text:
            raise HTTPException(
                status_code=422,
                detail="Invalid evaluation_as_of_date. Expected YYYY-MM-DD.",
            )
        try:
            normalized_evaluation_date = date.fromisoformat(text).isoformat()
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail="Invalid evaluation_as_of_date. Expected YYYY-MM-DD.",
            ) from exc

    settings = get_settings()
    _ensure_livermore_read_allowed(settings=settings, auth=auth)
    duckdb_path = str(settings.duckdb_path)
    return market_home_response_cache.get_or_build(
        _livermore_candidate_history_cache_key(
            duckdb_path=duckdb_path,
            stock_code=stock_code,
            snapshot_from=snapshot_from,
            snapshot_to=snapshot_to,
            evaluation_as_of_date=normalized_evaluation_date,
            limit=limit,
        ),
        lambda: timed_api_call(
            "/ui/market-data/livermore/candidate-history",
            lambda: _with_livermore_workbench_summary(
                livermore_candidate_history_envelope(
                    duckdb_path=duckdb_path,
                    stock_code=stock_code,
                    snapshot_from=snapshot_from,
                    snapshot_to=snapshot_to,
                    limit=limit,
                    evaluation_as_of_date=normalized_evaluation_date,
                ),
                summary_kind="candidate_history",
            ),
        ),
    )


@router.get("/livermore/strategy-score")
def livermore_strategy_score(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    snapshot_from: str | None = Query(default=None),
    snapshot_to: str | None = Query(default=None),
    current_market_state: str | None = Query(default=None, max_length=32),
    min_sample: int = Query(default=30, ge=1, le=10000),
    primary_horizon: str = Query(default="return_5d"),
) -> dict[str, object]:
    for label, value in (("snapshot_from", snapshot_from), ("snapshot_to", snapshot_to)):
        if value is None or not str(value).strip():
            continue
        text = str(value).strip()
        try:
            date.fromisoformat(text[:10])
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid {label}. Expected YYYY-MM-DD.",
            ) from exc
    if primary_horizon not in {"return_1d", "return_5d", "return_20d"}:
        raise HTTPException(
            status_code=422,
            detail="Invalid primary_horizon. Expected return_1d, return_5d, or return_20d.",
        )

    settings = get_settings()
    _ensure_livermore_read_allowed(settings=settings, auth=auth)
    duckdb_path = str(settings.duckdb_path)
    return market_home_response_cache.get_or_build(
        _livermore_strategy_score_cache_key(
            duckdb_path=duckdb_path,
            snapshot_from=snapshot_from,
            snapshot_to=snapshot_to,
            current_market_state=current_market_state,
            min_sample=min_sample,
            primary_horizon=primary_horizon,
        ),
        lambda: timed_api_call(
            "/ui/market-data/livermore/strategy-score",
            lambda: _with_livermore_workbench_summary(
                livermore_candidate_history_strategy_score_envelope(
                    duckdb_path=duckdb_path,
                    snapshot_from=snapshot_from,
                    snapshot_to=snapshot_to,
                    current_market_state=current_market_state,
                    min_sample=min_sample,
                    primary_horizon=primary_horizon,
                    macro_context_loader=_livermore_macro_context_v1_for_date,
                ),
                summary_kind="strategy_score",
            ),
        ),
    )


@router.get("/livermore/strategy-optimization")
def livermore_strategy_optimization(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    snapshot_from: str | None = Query(default=None),
    snapshot_to: str | None = Query(default=None),
    current_market_state: str | None = Query(default=None, max_length=32),
    min_sample: int = Query(default=30, ge=1, le=10000),
    primary_horizon: str = Query(default="return_5d"),
) -> dict[str, object]:
    _validate_snapshot_window(snapshot_from=snapshot_from, snapshot_to=snapshot_to)
    _validate_livermore_primary_horizon(primary_horizon)

    settings = get_settings()
    _ensure_livermore_read_allowed(settings=settings, auth=auth)
    duckdb_path = str(settings.duckdb_path)
    return market_home_response_cache.get_or_build(
        _livermore_strategy_optimization_cache_key(
            duckdb_path=duckdb_path,
            snapshot_from=snapshot_from,
            snapshot_to=snapshot_to,
            current_market_state=current_market_state,
            min_sample=min_sample,
            primary_horizon=primary_horizon,
        ),
        lambda: timed_api_call(
            "/ui/market-data/livermore/strategy-optimization",
            lambda: _with_livermore_workbench_summary(
                livermore_candidate_history_strategy_optimization_envelope(
                    duckdb_path=duckdb_path,
                    snapshot_from=snapshot_from,
                    snapshot_to=snapshot_to,
                    current_market_state=current_market_state,
                    min_sample=min_sample,
                    primary_horizon=primary_horizon,
                    macro_context_loader=_livermore_macro_context_v1_for_date,
                ),
                summary_kind="strategy_optimization",
            ),
        ),
    )


@router.get("/livermore/cycle-proxy-backtest")
def livermore_cycle_proxy_backtest(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    snapshot_from: str | None = Query(default=None),
    snapshot_to: str | None = Query(default=None),
) -> dict[str, object]:
    _validate_snapshot_window(snapshot_from=snapshot_from, snapshot_to=snapshot_to)

    settings = get_settings()
    _ensure_livermore_read_allowed(settings=settings, auth=auth)
    duckdb_path = str(settings.duckdb_path)
    return market_home_response_cache.get_or_build(
        _livermore_cycle_proxy_backtest_cache_key(
            duckdb_path=duckdb_path,
            snapshot_from=snapshot_from,
            snapshot_to=snapshot_to,
        ),
        lambda: timed_api_call(
            "/ui/market-data/livermore/cycle-proxy-backtest",
            lambda: _with_livermore_workbench_summary(
                livermore_candidate_history_cycle_proxy_backtest_envelope(
                    duckdb_path=duckdb_path,
                    snapshot_from=snapshot_from,
                    snapshot_to=snapshot_to,
                ),
                summary_kind="cycle_proxy_backtest",
            ),
        ),
    )


@router.get("/livermore/candidate-history-portfolio-backtest")
def livermore_candidate_history_portfolio_backtest(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    snapshot_from: str | None = Query(default=None),
    snapshot_to: str | None = Query(default=None),
) -> dict[str, object]:
    _validate_snapshot_window(snapshot_from=snapshot_from, snapshot_to=snapshot_to)

    settings = get_settings()
    _ensure_livermore_read_allowed(settings=settings, auth=auth)
    duckdb_path = str(settings.duckdb_path)
    return market_home_response_cache.get_or_build(
        _livermore_portfolio_backtest_cache_key(
            duckdb_path=duckdb_path,
            snapshot_from=snapshot_from,
            snapshot_to=snapshot_to,
        ),
        lambda: timed_api_call(
            "/ui/market-data/livermore/candidate-history-portfolio-backtest",
            lambda: _with_livermore_workbench_summary(
                livermore_candidate_history_portfolio_backtest_envelope(
                    duckdb_path=duckdb_path,
                    snapshot_from=snapshot_from,
                    snapshot_to=snapshot_to,
                ),
                summary_kind="candidate_history_portfolio_backtest",
            ),
        ),
    )


def _validate_snapshot_window(*, snapshot_from: str | None, snapshot_to: str | None) -> None:
    for label, value in (("snapshot_from", snapshot_from), ("snapshot_to", snapshot_to)):
        if value is None or not str(value).strip():
            continue
        text = str(value).strip()
        try:
            date.fromisoformat(text[:10])
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid {label}. Expected YYYY-MM-DD.",
            ) from exc


def _validate_livermore_primary_horizon(primary_horizon: str) -> None:
    if primary_horizon not in {"return_1d", "return_5d", "return_20d"}:
        raise HTTPException(
            status_code=422,
            detail="Invalid primary_horizon. Expected return_1d, return_5d, or return_20d.",
        )


@router.get("/livermore/sector-rank-series")
def livermore_sector_rank_series(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    as_of_date: str | None = Query(default=None),
    window_days: int = Query(default=20, ge=2, le=60),
    sector_code: str | None = Query(default=None, max_length=32),
    top_k: int = Query(default=10, ge=1, le=50),
) -> dict[str, object]:
    settings = get_settings()
    parsed_as_of: date | None = None
    if as_of_date is not None:
        try:
            parsed_as_of = date.fromisoformat(as_of_date.strip()[:10])
        except ValueError as exc:
            logger.warning(
                "Livermore sector-rank-series as_of_date rejected error_type=%s detail=%s",
                type(exc).__name__,
                exc,
            )
            raise HTTPException(
                status_code=422,
                detail="LIVERMORE_AS_OF_DATE_INVALID：日期格式无效，应为 YYYY-MM-DD",
            ) from exc
    _ensure_livermore_read_allowed(settings=settings, auth=auth)
    duckdb_path = str(settings.duckdb_path)
    as_of_text = parsed_as_of.isoformat() if parsed_as_of is not None else None
    return market_home_response_cache.get_or_build(
        _livermore_sector_rank_series_cache_key(
            duckdb_path=duckdb_path,
            as_of_date=as_of_text,
            window_days=window_days,
            sector_code=sector_code,
            top_k=top_k,
        ),
        lambda: timed_api_call(
            "/ui/market-data/livermore/sector-rank-series",
            lambda: _with_livermore_workbench_summary(
                livermore_sector_rank_series_envelope(
                    duckdb_path=duckdb_path,
                    as_of_date=parsed_as_of,
                    window_days=window_days,
                    sector_code=sector_code,
                    top_k=top_k,
                ),
                summary_kind="sector_rank_series",
            ),
        ),
    )
