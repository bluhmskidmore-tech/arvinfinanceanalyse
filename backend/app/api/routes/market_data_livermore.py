from __future__ import annotations

import re
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Annotated

from backend.app.api.perf_logging import timed_api_call
from backend.app.api.response_cache import market_home_response_cache
from backend.app.governance.settings import get_settings
from backend.app.repositories.stock_analysis_theme_overlay_reader import (
    StockAnalysisThemeOverlayReader,
    ThemeOverlayManifestAccessor,
)
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.livermore_candidate_history_service import (
    livermore_candidate_history_cycle_proxy_backtest_envelope,
    livermore_candidate_history_envelope,
    livermore_candidate_history_portfolio_backtest_envelope,
    livermore_candidate_history_strategy_optimization_envelope,
    livermore_candidate_history_strategy_score_envelope,
)
from backend.app.services.livermore_gate_supplement_compute_service import (
    compute_and_materialize_gate_supplement,
)
from backend.app.services.livermore_sector_rank_series_service import livermore_sector_rank_series_envelope
from backend.app.services.livermore_signal_confluence_service import livermore_signal_confluence_envelope
from backend.app.services.livermore_stock_detail_service import livermore_stock_detail_envelope
from backend.app.services.macro_bond_linkage_service import get_macro_context_v1
from backend.app.services.market_data_livermore_service import (
    livermore_business_inputs_version,
    livermore_data_version,
    livermore_strategy_envelope_from_catalog,
)
from backend.app.services.stock_analysis_workbench_service import (
    DEFAULT_INCLUDE_KEYS,
    stock_analysis_workbench_envelope,
)
from backend.app.services.stock_kline_analysis_service import stock_kline_analysis_envelope
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel

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
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="market_data.livermore",
            action="read",
        )
    except PermissionError as exc:
        if _allows_development_fallback_read(auth=auth, environment=getattr(settings, "environment", "")):
            return
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _allows_development_fallback_read(*, auth: AuthContext, environment: object) -> bool:
    return (
        str(environment).strip().lower() == "development"
        and auth.identity_source == "fallback"
        and auth.user_id == "anonymous"
        and auth.role == "viewer"
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


def _resolve_livermore_position_csv_path(*, data_input_root: Path, csv_path: str) -> Path:
    base_root = Path(data_input_root).resolve()
    allowed_root = (base_root / "livermore").resolve()
    raw_path = Path(csv_path).expanduser()
    candidate = raw_path.resolve() if raw_path.is_absolute() else (base_root / raw_path).resolve()
    try:
        candidate.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError("Livermore position snapshot CSV must be under data_input/livermore.") from exc
    return candidate


def _invalidate_livermore_response_cache() -> None:
    market_home_response_cache.invalidate()


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
    )


def _theme_overlay_reader_from_settings(settings: object) -> StockAnalysisThemeOverlayReader | None:
    governance_path = getattr(settings, "governance_path", None)
    archive_root = getattr(settings, "local_archive_path", None)
    if governance_path is None or archive_root is None:
        return None
    try:
        governance_repo = ThemeOverlayManifestAccessor(
            base_dir=governance_path,
            sql_dsn=str(getattr(settings, "governance_sql_dsn", "") or ""),
            backend_mode=str(getattr(settings, "governance_backend", "jsonl") or "jsonl"),
        )
    except Exception:
        return None
    return StockAnalysisThemeOverlayReader(
        archive_root=archive_root,
        governance_repo=governance_repo,
    )


def _theme_overlay_fingerprint(reader: StockAnalysisThemeOverlayReader | None) -> str:
    return reader.fingerprint() if reader is not None else "theme-overlay-reader:not-configured"


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
) -> tuple[dict[str, object], str, float]:
    duckdb_path = str(settings.duckdb_path)  # type: ignore[attr-defined]
    catalog_file = settings.choice_stock_catalog_file  # type: ignore[attr-defined]
    theme_overlay_reader = _theme_overlay_reader_from_settings(settings)
    theme_overlay_fingerprint = _theme_overlay_fingerprint(theme_overlay_reader)
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

    payload, cache_status = market_home_response_cache.get_or_build_with_status(
        _stock_analysis_workbench_cache_key(
            duckdb_path=duckdb_path,
            catalog_file=catalog_file,
            as_of_date=as_of_date,
            include=include,
            sector_window_days=sector_window_days,
            top_k=top_k,
            theme_overlay_fingerprint=theme_overlay_fingerprint,
        ),
        build,
        ttl_seconds=STOCK_ANALYSIS_WORKBENCH_CACHE_TTL_SECONDS,
    )
    return payload, cache_status, compute_ms


def _livermore_stock_detail_cache_key(
    *, duckdb_path: str, stock_code: str, as_of_date: str | None, lookback: int
) -> str:
    return (
        f"livermore/stock-detail::stock={stock_code}::as_of={as_of_date or ''}"
        f"::lookback={lookback}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


def _stock_kline_analysis_cache_key(*, duckdb_path: str, stock_code: str, as_of_date: str | None, lookback: int) -> str:
    return f"stock-analysis/kline::stock={stock_code}::as_of={as_of_date or ''}::lookback={lookback}::{duckdb_path}"


def _livermore_candidate_history_cache_key(
    *,
    duckdb_path: str,
    stock_code: str | None,
    snapshot_from: str | None,
    snapshot_to: str | None,
    evaluation_as_of_date: str | None,
    limit: int,
) -> str:
    return (
        f"livermore/candidate-history::stock={stock_code or ''}"
        f"::from={snapshot_from or ''}::to={snapshot_to or ''}"
        f"::evaluation={evaluation_as_of_date or ''}::limit={limit}::{duckdb_path}"
        f"::data_version={livermore_data_version(duckdb_path)}"
    )


def _livermore_strategy_score_cache_key(
    *,
    duckdb_path: str,
    snapshot_from: str | None,
    snapshot_to: str | None,
    current_market_state: str | None,
    min_sample: int,
    primary_horizon: str,
) -> str:
    return (
        f"livermore/strategy-score::from={snapshot_from or ''}::to={snapshot_to or ''}"
        f"::market_state={current_market_state or ''}::min_sample={min_sample}"
        f"::primary_horizon={primary_horizon}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


def _livermore_strategy_optimization_cache_key(
    *,
    duckdb_path: str,
    snapshot_from: str | None,
    snapshot_to: str | None,
    current_market_state: str | None,
    min_sample: int,
    primary_horizon: str,
) -> str:
    return (
        f"livermore/strategy-optimization::from={snapshot_from or ''}::to={snapshot_to or ''}"
        f"::market_state={current_market_state or ''}::min_sample={min_sample}"
        f"::primary_horizon={primary_horizon}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


def _livermore_cycle_proxy_backtest_cache_key(
    *, duckdb_path: str, snapshot_from: str | None, snapshot_to: str | None
) -> str:
    return f"livermore/cycle-proxy-backtest::from={snapshot_from or ''}::to={snapshot_to or ''}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"


def _livermore_portfolio_backtest_cache_key(
    *, duckdb_path: str, snapshot_from: str | None, snapshot_to: str | None
) -> str:
    return (
        f"livermore/candidate-history-portfolio-backtest::from={snapshot_from or ''}"
        f"::to={snapshot_to or ''}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


def _livermore_sector_rank_series_cache_key(
    *,
    duckdb_path: str,
    as_of_date: str | None,
    window_days: int,
    sector_code: str | None,
    top_k: int,
) -> str:
    return (
        f"livermore/sector-rank-series::as_of={as_of_date or ''}::window_days={window_days}"
        f"::sector={sector_code or ''}::top_k={top_k}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


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
    theme_overlay_fingerprint = _theme_overlay_fingerprint(theme_overlay_reader)
    return market_home_response_cache.get_or_build(
        _livermore_strategy_cache_key(
            duckdb_path=duckdb_path,
            catalog_file=catalog_file,
            as_of_date=as_of_date,
            theme_overlay_fingerprint=theme_overlay_fingerprint,
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
    payload, cache_status, compute_ms = _cached_stock_analysis_workbench(
        settings=settings,
        as_of_date=as_of_date,
        include=include,
        sector_window_days=sector_window_days,
        top_k=top_k,
    )
    total_ms = (time.perf_counter() - started_at) * 1000
    response.headers["Server-Timing"] = (
        f'workbench;dur={total_ms:.3f}, compute;dur={compute_ms:.3f}, cache;desc="{cache_status}"'
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
    theme_overlay_fingerprint = _theme_overlay_fingerprint(theme_overlay_reader)
    return market_home_response_cache.get_or_build(
        _livermore_signal_confluence_cache_key(
            duckdb_path=duckdb_path,
            catalog_file=catalog_file,
            as_of_date=as_of_date,
            theme_overlay_fingerprint=theme_overlay_fingerprint,
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
        from backend.app.tasks.livermore_position_snapshot_materialize import (
            materialize_livermore_position_snapshot,
        )

        run_id = f"livermore_position_snapshot:{request.as_of_date}:{uuid.uuid4().hex[:12]}"
        materialize_livermore_position_snapshot.send(
            as_of_date=request.as_of_date,
            csv_path=str(csv_path),
            duckdb_path=str(settings.duckdb_path),
            run_id=run_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "status": "queued",
        "run_id": run_id,
        "as_of_date": request.as_of_date,
        "input_mode": "csv",
        "csv_path": str(csv_path),
    }


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
        from backend.app.tasks.livermore_position_snapshot_materialize import (
            materialize_livermore_position_snapshot_rows,
        )

        run_id = f"livermore_position_snapshot:{request.as_of_date}:{uuid.uuid4().hex[:12]}"
        materialize_livermore_position_snapshot_rows.send(
            as_of_date=request.as_of_date,
            rows=[position.model_dump() for position in request.positions],
            duckdb_path=str(settings.duckdb_path),
            run_id=run_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "status": "queued",
        "run_id": run_id,
        "as_of_date": request.as_of_date,
        "input_mode": "manual",
    }


@router.post("/livermore/refresh-gate-supplement")
def refresh_gate_supplement(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    as_of_date: str | None = Query(None),
    lookback_days: int = Query(default=30, ge=7, le=365),
) -> dict[str, object]:
    """Compute and write breadth_5d + limit_up_quality_ok from landed CSI300 data."""
    parsed_date: date | None = None
    if as_of_date is not None:
        try:
            parsed_date = date.fromisoformat(as_of_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    _ensure_livermore_gate_supplement_refresh_allowed(settings=settings, auth=auth)
    try:
        result = compute_and_materialize_gate_supplement(
            duckdb_path=str(settings.duckdb_path),
            as_of_date=parsed_date,
            lookback_days=lookback_days,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    _invalidate_livermore_response_cache()
    return result


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


def _livermore_macro_context_v1_for_date(as_of_date: str) -> dict[str, object] | None:
    as_of_text = _optional_text(as_of_date)
    if not as_of_text:
        return None
    return get_macro_context_v1(
        date.fromisoformat(as_of_text[:10]),
        as_of_date=as_of_text[:10],
    )


def _mapping(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _count_array(value: object) -> int | None:
    if isinstance(value, list):
        return len(value)
    return None


def _count_mapping(value: object) -> int | None:
    if isinstance(value, dict):
        return len(value)
    return None


def _count_array_or_mapping(value: object) -> int | None:
    if isinstance(value, (list, dict)):
        return len(value)
    return None


def _present(value: object) -> bool:
    return value not in (None, "", [], {})


def _optional_count(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(parsed, 0)


def _item_count(value: object) -> int | None:
    mapping = _mapping(value)
    if "items" in mapping:
        return _count_array(mapping.get("items"))
    return _count_array_or_mapping(value)


def _active_data_gap_count(value: object) -> int | None:
    if not isinstance(value, list):
        return None
    return sum(1 for item in value if not (isinstance(item, dict) and str(item.get("status") or "").lower() == "ready"))


def _active_diagnostic_count(value: object) -> int | None:
    if not isinstance(value, list):
        return None
    return sum(
        1 for item in value if not (isinstance(item, dict) and str(item.get("severity") or "").lower() == "info")
    )


def _actionable_unsupported_output_count(value: object) -> int | None:
    if not isinstance(value, list):
        return None
    return sum(
        1 for item in value if not (isinstance(item, dict) and _is_known_livermore_policy_pause(item.get("reason")))
    )


def _is_known_livermore_policy_pause(reason: object) -> bool:
    lower = str(reason or "").strip().lower()
    return (
        ("stock candidate policy" in lower and "inactive in overheat" in lower)
        or "mean reversion watchlist is paused" in lower
        or ("theme breakout execution is paused" in lower and "overheat" in lower)
        or ("hybrid fusion is observation-only" in lower and "warm/hot" in lower)
        or ("uptrend momentum watchlist is paused" in lower and "warm or hot" in lower)
    )


def _sum_optional_counts(*values: int | None) -> int | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def _livermore_workbench_strategy_summary(result: dict[str, object]) -> dict[str, object]:
    data_gap_count = _active_data_gap_count(result.get("data_gaps"))
    diagnostic_count = _active_diagnostic_count(result.get("diagnostics"))
    unsupported_output_count = _actionable_unsupported_output_count(result.get("unsupported_outputs"))
    return {
        "kind": "strategy",
        "as_of_date": result.get("as_of_date") if _present(result.get("as_of_date")) else None,
        "requested_as_of_date": (
            result.get("requested_as_of_date") if _present(result.get("requested_as_of_date")) else None
        ),
        "strategy_name": result.get("strategy_name") if _present(result.get("strategy_name")) else None,
        "basis": result.get("basis") if _present(result.get("basis")) else None,
        "market_gate_present": _present(result.get("market_gate")),
        "rule_readiness_count": _count_array(result.get("rule_readiness")),
        "module_state_count": _count_array(result.get("module_states")),
        "factor_screen_candidate_count": _item_count(result.get("factor_screen_candidates")),
        "hybrid_fusion_candidate_count": _item_count(result.get("hybrid_fusion_candidates")),
        "sector_rank_count": _item_count(result.get("sector_rank")),
        "data_gap_count": data_gap_count,
        "diagnostic_count": diagnostic_count,
        "supported_output_count": _count_array(result.get("supported_outputs")),
        "unsupported_output_count": unsupported_output_count,
        "actionable_boundary_count": _sum_optional_counts(data_gap_count, diagnostic_count, unsupported_output_count),
        "total_data_gap_count": _count_array(result.get("data_gaps")),
        "total_diagnostic_count": _count_array(result.get("diagnostics")),
        "total_unsupported_output_count": _count_array(result.get("unsupported_outputs")),
        "risk_exit_present": _present(result.get("risk_exit")),
    }


def _livermore_workbench_signal_summary(result: dict[str, object]) -> dict[str, object]:
    replay = _mapping(result.get("replay_evidence"))
    return {
        "kind": "signal_confluence",
        "as_of_date": result.get("as_of_date") if _present(result.get("as_of_date")) else None,
        "macro_context_present": _present(result.get("macro_context")),
        "adversarial_context_present": _present(result.get("adversarial_context")),
        "strategy_context_present": _present(result.get("strategy_context")),
        "closed_loop_state_present": _present(result.get("closed_loop_state")),
        "entry_observation_count": _count_array(result.get("entry_observations")),
        "exit_observation_count": _count_array(result.get("exit_observations")),
        "replay_evidence_present": _present(result.get("replay_evidence")),
        "replay_evidence_row_count": _optional_count(replay.get("row_count")) if replay else None,
        "replay_evidence_sample_count": _count_array(replay.get("sample_items")) if replay else None,
        "diagnostic_count": _count_array(result.get("diagnostics")),
        "position_size_hint_present": _present(result.get("position_size_hint")),
    }


def _livermore_workbench_candidate_history_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "candidate_history",
        "item_count": _count_array(result.get("items")),
        "summary_present": _present(result.get("summary")),
        "backtest_window_summary_present": _present(result.get("backtest_window_summary")),
        "snapshot_from": result.get("snapshot_from") if _present(result.get("snapshot_from")) else None,
        "snapshot_to": result.get("snapshot_to") if _present(result.get("snapshot_to")) else None,
        "stock_code_present": _present(result.get("stock_code")),
        "limit": _optional_count(result.get("limit")),
    }


def _livermore_workbench_strategy_score_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "strategy_score",
        "row_count": _count_array(result.get("rows")),
        "current_market_state_row_count": _count_array(result.get("current_market_state_rows")),
        "scope_count": _count_array_or_mapping(result.get("stock_candidate_state_scopes")),
        "review_thresholds_present": _present(result.get("review_thresholds")),
        "snapshot_from": result.get("snapshot_from") if _present(result.get("snapshot_from")) else None,
        "snapshot_to": result.get("snapshot_to") if _present(result.get("snapshot_to")) else None,
        "primary_horizon": result.get("primary_horizon") if _present(result.get("primary_horizon")) else None,
        "min_sample": _optional_count(result.get("min_sample")),
        "backtest_window_summary_present": _present(result.get("backtest_window_summary")),
    }


def _livermore_workbench_strategy_optimization_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "strategy_optimization",
        "strategy_summary_count": _count_array(result.get("strategy_summaries")),
        "slice_count": _count_array(result.get("slices")),
        "optimization_review_item_count": _count_array(result.get("recommendations")),
        "pending_summary_present": _present(result.get("pending_summary")),
        "sample_maturity_present": _present(result.get("sample_maturity")),
        "review_thresholds_present": _present(result.get("review_thresholds")),
        "snapshot_from": result.get("snapshot_from") if _present(result.get("snapshot_from")) else None,
        "snapshot_to": result.get("snapshot_to") if _present(result.get("snapshot_to")) else None,
    }


def _livermore_workbench_cycle_proxy_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "cycle_proxy_backtest",
        "status": result.get("status") if _present(result.get("status")) else None,
        "full_strategy_status": (
            result.get("full_strategy_status") if _present(result.get("full_strategy_status")) else None
        ),
        "proxy_signal_kind": result.get("proxy_signal_kind") if _present(result.get("proxy_signal_kind")) else None,
        "proxy_rule_present": _present(result.get("proxy_rule")),
        "summary_present": _present(result.get("summary")),
        "nav_series_count": _count_array(result.get("nav_series")),
        "warning_count": _count_array(result.get("warnings")),
        "missing_input_count": _count_array(result.get("missing_full_strategy_inputs")),
        "snapshot_from": result.get("snapshot_from") if _present(result.get("snapshot_from")) else None,
        "snapshot_to": result.get("snapshot_to") if _present(result.get("snapshot_to")) else None,
    }


def _livermore_workbench_portfolio_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "candidate_history_portfolio_backtest",
        "status": result.get("status") if _present(result.get("status")) else None,
        "full_strategy_status": (
            result.get("full_strategy_status") if _present(result.get("full_strategy_status")) else None
        ),
        "signal_kind": result.get("signal_kind") if _present(result.get("signal_kind")) else None,
        "rebalance_rule_present": _present(result.get("rebalance_rule")),
        "weighting_rule_present": _present(result.get("weighting_rule")),
        "summary_present": _present(result.get("summary")),
        "nav_series_count": _count_array(result.get("nav_series")),
        "rebalance_log_count": _count_array(result.get("rebalance_log")),
        "warning_count": _count_array(result.get("warnings")),
        "missing_input_count": _count_array(result.get("missing_full_strategy_inputs")),
        "snapshot_from": result.get("snapshot_from") if _present(result.get("snapshot_from")) else None,
        "snapshot_to": result.get("snapshot_to") if _present(result.get("snapshot_to")) else None,
    }


def _livermore_workbench_sector_series_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "sector_rank_series",
        "state": result.get("state") if _present(result.get("state")) else None,
        "as_of_date": result.get("as_of_date") if _present(result.get("as_of_date")) else None,
        "series_count": _count_array(result.get("series")),
        "top_k": _optional_count(result.get("top_k")),
        "window_days": _optional_count(result.get("window_days")),
        "formula_version": result.get("formula_version") if _present(result.get("formula_version")) else None,
        "unsupported_note_count": _count_array(result.get("unsupported_notes")),
    }


def _livermore_workbench_summary(result: dict[str, object], *, summary_kind: str) -> dict[str, object]:
    if summary_kind == "strategy":
        return _livermore_workbench_strategy_summary(result)
    if summary_kind == "signal_confluence":
        return _livermore_workbench_signal_summary(result)
    if summary_kind == "candidate_history":
        return _livermore_workbench_candidate_history_summary(result)
    if summary_kind == "strategy_score":
        return _livermore_workbench_strategy_score_summary(result)
    if summary_kind == "strategy_optimization":
        return _livermore_workbench_strategy_optimization_summary(result)
    if summary_kind == "cycle_proxy_backtest":
        return _livermore_workbench_cycle_proxy_summary(result)
    if summary_kind == "candidate_history_portfolio_backtest":
        return _livermore_workbench_portfolio_summary(result)
    if summary_kind == "sector_rank_series":
        return _livermore_workbench_sector_series_summary(result)
    return {
        "kind": summary_kind,
        "field_count": _count_mapping(result),
    }


def _with_livermore_workbench_summary(
    envelope: dict[str, object],
    *,
    summary_kind: str,
) -> dict[str, object]:
    result_value = envelope.get("result")
    if not isinstance(result_value, dict):
        return envelope
    result_value["workbench_summary"] = _livermore_workbench_summary(result_value, summary_kind=summary_kind)
    return envelope


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


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
