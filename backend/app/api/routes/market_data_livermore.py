from __future__ import annotations

import re
import time
from datetime import date
from pathlib import Path
from typing import Annotated

from backend.app.api.deps import ensure_read_allowed
from backend.app.api.perf_logging import timed_api_call
from backend.app.api.response_cache import market_home_response_cache
from backend.app.governance.settings import get_settings
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
from backend.app.services.livermore_signal_confluence_service import livermore_signal_confluence_envelope
from backend.app.services.livermore_stock_detail_service import livermore_stock_detail_envelope
from backend.app.services.macro_bond_linkage_service import get_macro_context_v1

# Route-support helpers moved to the service layer. Re-import them into this
# module namespace so existing monkeypatch/import contracts keep working;
# endpoints keep calling them through unqualified module globals.
from backend.app.services.market_data_livermore_route_support import (
    _actionable_unsupported_output_count,
    _active_data_gap_count,
    _active_diagnostic_count,
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
    _stock_heavyweight_trends_cache_key,
    _stock_kline_analysis_cache_key,
    _sum_optional_counts,
    _with_livermore_workbench_summary,
)
from backend.app.services.market_data_livermore_service import (
    livermore_business_inputs_version,
    livermore_data_version,
    livermore_strategy_envelope_from_catalog,
    theme_overlay_fingerprint,
    theme_overlay_reader_from_settings,
)
from backend.app.services.stock_analysis_workbench_service import (
    DEFAULT_INCLUDE_KEYS,
    stock_analysis_workbench_envelope,
)
from backend.app.services.stock_heavyweight_trend_service import stock_heavyweight_trend_envelope
from backend.app.services.stock_kline_analysis_service import stock_kline_analysis_envelope
from backend.app.services.stock_official_evidence_service import stock_official_evidence_envelope
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel

# Keep existing module hooks while the implementations remain service-owned.
_theme_overlay_reader_from_settings = theme_overlay_reader_from_settings
_theme_overlay_fingerprint = theme_overlay_fingerprint

router = APIRouter(prefix="/ui/market-data", tags=["market-data"])
_STOCK_CODE_LIVERMORE_PATTERN = re.compile(r"^[0-9A-Za-z.\-]{1,16}$")
# Freshness comes from DuckDB, Choice catalog, repository business-input, and
# theme-overlay fingerprints. Keep unchanged snapshots for one day.
STOCK_ANALYSIS_WORKBENCH_CACHE_TTL_SECONDS = 24 * 60 * 60.0


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
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _livermore_strategy_cache_key(
    *,
    duckdb_path: str,
    catalog_file: object,
    as_of_date: str | None,
    theme_overlay_fingerprint: str = "theme-overlay-reader:not-configured",
) -> str:
    return (
        f"livermore/strategy::as_of={as_of_date or ''}::catalog={catalog_file}::{duckdb_path}"
        f"::data_version={livermore_data_version(duckdb_path)}"
        f"::theme_overlay={theme_overlay_fingerprint}"
        f"::business_inputs={livermore_business_inputs_version()}"
    )


def _stock_analysis_workbench_cache_key(
    *,
    duckdb_path: str,
    catalog_file: object,
    as_of_date: str | None,
    include: str | None,
    sector_window_days: int,
    top_k: int,
    theme_overlay_fingerprint: str = "theme-overlay-reader:not-configured",
) -> str:
    include_keys = set(DEFAULT_INCLUDE_KEYS)
    include_keys.update(item.strip() for item in str(include or "").split(",") if item.strip())
    include_token = ",".join(sorted(include_keys))
    return (
        f"livermore/workbench::as_of={as_of_date or ''}::include={include_token}"
        f"::sector_window_days={sector_window_days}::top_k={top_k}"
        f"::catalog={catalog_file}::catalog_version={_choice_stock_catalog_fingerprint(catalog_file)}"
        f"::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
        f"::theme_overlay={theme_overlay_fingerprint}"
        f"::business_inputs={livermore_business_inputs_version()}"
    )


def _livermore_signal_confluence_cache_key(
    *,
    duckdb_path: str,
    catalog_file: object,
    as_of_date: str | None,
    theme_overlay_fingerprint: str = "theme-overlay-reader:not-configured",
) -> str:
    return (
        f"livermore/signal-confluence::as_of={as_of_date or ''}::catalog={catalog_file}::{duckdb_path}"
        f"::data_version={livermore_data_version(duckdb_path)}"
        f"::theme_overlay={theme_overlay_fingerprint}"
        f"::business_inputs={livermore_business_inputs_version()}"
    )


def _choice_stock_catalog_fingerprint(catalog_file: object) -> str:
    try:
        stat = Path(str(catalog_file)).stat()
    except OSError:
        return "missing"
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def _cached_stock_analysis_workbench(
    *,
    settings: object,
    as_of_date: str | None,
    include: str | None,
    sector_window_days: int,
    top_k: int,
) -> tuple[dict[str, object], str, float, float, float]:
    duckdb_path = str(settings.duckdb_path)  # type: ignore[attr-defined]
    catalog_file = settings.choice_stock_catalog_file  # type: ignore[attr-defined]
    overlay_started = time.perf_counter()
    theme_overlay_reader = _theme_overlay_reader_from_settings(settings)
    overlay_fingerprint = _theme_overlay_fingerprint(theme_overlay_reader)
    overlay_ms = (time.perf_counter() - overlay_started) * 1000
    compute_ms = 0.0

    def build() -> dict[str, object]:
        nonlocal compute_ms
        compute_started = time.perf_counter()
        try:
            return timed_api_call(
                "/ui/market-data/stock-analysis/workbench",
                lambda: stock_analysis_workbench_envelope(
                    duckdb_path=duckdb_path,
                    as_of_date=as_of_date,
                    choice_stock_catalog_file=catalog_file,
                    include=include,
                    sector_window_days=sector_window_days,
                    top_k=top_k,
                    theme_overlay_reader=theme_overlay_reader,
                ),
            )
        finally:
            compute_ms = (time.perf_counter() - compute_started) * 1000

    cache_started = time.perf_counter()
    payload, cache_status = market_home_response_cache.get_or_build_with_status(
        _stock_analysis_workbench_cache_key(
            duckdb_path=duckdb_path,
            catalog_file=catalog_file,
            as_of_date=as_of_date,
            include=include,
            sector_window_days=sector_window_days,
            top_k=top_k,
            theme_overlay_fingerprint=overlay_fingerprint,
        ),
        build,
        ttl_seconds=STOCK_ANALYSIS_WORKBENCH_CACHE_TTL_SECONDS,
    )
    cache_ms = (time.perf_counter() - cache_started) * 1000
    return payload, cache_status, compute_ms, overlay_ms, cache_ms


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
    return market_home_response_cache.get_or_build(
        _livermore_signal_confluence_cache_key(
            duckdb_path=duckdb_path,
            catalog_file=catalog_file,
            as_of_date=as_of_date,
            theme_overlay_fingerprint=overlay_fingerprint,
        ),
        lambda: _with_livermore_workbench_summary(
            livermore_signal_confluence_envelope(
                duckdb_path=duckdb_path,
                as_of_date=as_of_date,
                choice_stock_catalog_file=catalog_file,
                theme_overlay_reader=theme_overlay_reader,
            ),
            summary_kind="signal_confluence",
        ),
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
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        csv_path = _resolve_livermore_position_csv_path(
            data_input_root=settings.data_input_root,
            csv_path=request.csv_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not csv_path.exists():
        raise HTTPException(status_code=422, detail=f"Livermore position snapshot CSV not found: {csv_path}")

    try:
        return queue_livermore_position_snapshot_csv(
            as_of_date=request.as_of_date,
            csv_path=csv_path,
            duckdb_path=settings.duckdb_path,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        return queue_livermore_position_snapshot_rows(
            as_of_date=request.as_of_date,
            rows=[position.model_dump() for position in request.positions],
            duckdb_path=settings.duckdb_path,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LivermoreGateSupplementRefreshConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LivermoreGateSupplementRefreshQueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

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
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
            raise HTTPException(status_code=422, detail=str(exc)) from exc
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
