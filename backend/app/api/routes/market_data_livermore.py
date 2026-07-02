from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Annotated

from backend.app.api.perf_logging import timed_api_call
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.livermore_candidate_history_service import (
    livermore_candidate_history_cycle_proxy_backtest_envelope,
    livermore_candidate_history_envelope,
    livermore_candidate_history_envelope_or_none,
    livermore_candidate_history_portfolio_backtest_envelope,
    livermore_candidate_history_strategy_optimization_envelope,
    livermore_candidate_history_strategy_score_envelope,
)
from backend.app.services.livermore_gate_supplement_compute_service import (
    compute_and_materialize_gate_supplement,
)
from backend.app.services.livermore_sector_rank_series_service import livermore_sector_rank_series_envelope
from backend.app.services.livermore_signal_confluence_service import (
    build_livermore_signal_confluence,
)
from backend.app.services.livermore_stock_detail_service import livermore_stock_detail_envelope
from backend.app.services.macro_bond_linkage_service import (
    get_macro_context_v1,
    get_macro_environment_context,
)
from backend.app.services.market_data_livermore_service import (
    _risk_exit_input_block_reason,
    livermore_strategy_envelope_from_catalog,
)
from backend.app.services.stock_analysis_workbench_service import stock_analysis_workbench_envelope
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/ui/market-data", tags=["market-data"])
_STOCK_CODE_LIVERMORE_PATTERN = re.compile(r"^[0-9A-Za-z.\-]{1,16}$")
LIVERMORE_SIGNAL_CONFLUENCE_RESULT_KIND = "market_data.livermore.signal_confluence"
LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION = "rv_livermore_signal_confluence_v1"
LIVERMORE_SIGNAL_CONFLUENCE_CACHE_VERSION = "cv_livermore_signal_confluence_v1"


def load_macro_adversarial_signal_payload(
    *, output_dir: str | Path | None = None
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        from backend.app.services.macro_adversarial_signal_service import (
            load_macro_adversarial_signal_payload as loader,
        )
    except ModuleNotFoundError as exc:
        if exc.name != "backend.app.services.macro_adversarial_signal_service":
            raise
        return {}, {}

    payload, meta = loader(output_dir=output_dir)
    return _dict_payload(payload), _mapping(meta)


def _attach_replay_evidence(
    payload: dict[str, object],
    *,
    duckdb_path: str,
    as_of_date: str | None,
    replay_summary: dict[str, object],
) -> None:
    replay_evidence = _candidate_history_replay_evidence(
        payload=payload,
        duckdb_path=duckdb_path,
        as_of_date=as_of_date,
        replay_summary=replay_summary,
    )
    payload["replay_evidence"] = replay_evidence


def livermore_candidate_history_backtest_window_summary(
    *,
    duckdb_path: str,
    stock_code: str | None,
    snapshot_from: str | None,
    snapshot_to: str | None,
) -> dict[str, object]:
    if not snapshot_from and not snapshot_to:
        return _unsupported_replay_summary()
    envelope = livermore_candidate_history_envelope_or_none(
        duckdb_path=duckdb_path,
        stock_code=stock_code,
        snapshot_from=snapshot_from,
        snapshot_to=snapshot_to,
        limit=500,
    )
    if envelope is None:
        return _unsupported_replay_summary()
    result = _mapping(envelope.get("result"))
    summary = _mapping(result.get("backtest_window_summary"))
    if "status" in summary and "replay_dates_completed" in summary:
        return summary
    return _unsupported_replay_summary()


def _candidate_history_replay_evidence(
    *,
    payload: dict[str, object],
    duckdb_path: str,
    as_of_date: str | None,
    replay_summary: dict[str, object],
) -> dict[str, object]:
    snapshot_as_of_date = as_of_date[:10] if as_of_date else None
    if not as_of_date:
        return _empty_replay_evidence(snapshot_as_of_date=snapshot_as_of_date)
    path = Path(duckdb_path)
    if not path.is_file():
        return _empty_replay_evidence(snapshot_as_of_date=snapshot_as_of_date)
    row_count = _replay_window_candidate_row_count(replay_summary)
    if row_count <= 0:
        return _empty_replay_evidence(snapshot_as_of_date=snapshot_as_of_date)
    envelope = livermore_candidate_history_envelope_or_none(
        duckdb_path=duckdb_path,
        stock_code=None,
        snapshot_from=snapshot_as_of_date,
        snapshot_to=snapshot_as_of_date,
        limit=max(row_count, 5),
    )
    if envelope is None:
        return _empty_replay_evidence(snapshot_as_of_date=snapshot_as_of_date)

    result = _mapping(envelope.get("result"))
    all_items = _list_of_mappings(result.get("items"))

    replay_stock_codes = {_normalized_stock_code(item.get("stock_code")) for item in all_items}
    replay_stock_codes.discard("")
    entry_stock_codes = {
        _normalized_stock_code(item.get("stock_code"))
        for item in _list_of_mappings(payload.get("entry_observations"))
    }
    entry_stock_codes.discard("")

    return {
        "status": "available",
        "snapshot_as_of_date": snapshot_as_of_date,
        "row_count": row_count,
        "matched_entry_count": len(entry_stock_codes & replay_stock_codes),
        "sample_items": [_replay_sample_item(item) for item in all_items[:5]],
    }


def _empty_replay_evidence(*, snapshot_as_of_date: str | None) -> dict[str, object]:
    return {
        "status": "missing",
        "snapshot_as_of_date": snapshot_as_of_date,
        "row_count": 0,
        "matched_entry_count": 0,
        "sample_items": [],
    }


def _unsupported_replay_summary() -> dict[str, object]:
    return {
        "status": "unsupported",
        "snapshot_from": None,
        "snapshot_to": None,
        "replay_dates_total": 0,
        "replay_dates_completed": 0,
        "replay_dates_pending": 0,
        "replay_dates_unsupported": 0,
        "replay_dates_proxy_only": 0,
        "completed_rows": 0,
        "pending_rows": 0,
        "unsupported_rows": 0,
        "proxy_only_rows": 0,
        "included_completed_stats_dates": [],
        "excluded_from_completed_stats_dates": [],
        "date_reasons": [],
    }


def _replay_window_candidate_row_count(summary: dict[str, object]) -> int:
    return (
        _non_negative_int(summary.get("completed_rows"))
        + _non_negative_int(summary.get("pending_rows"))
        + _non_negative_int(summary.get("unsupported_rows"))
        + _non_negative_int(summary.get("proxy_only_rows"))
    )


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
    return _with_livermore_workbench_summary(
        livermore_strategy_envelope_from_catalog(
            duckdb_path=str(settings.duckdb_path),
            as_of_date=as_of_date,
            choice_stock_catalog_file=settings.choice_stock_catalog_file,
        ),
        summary_kind="strategy",
    )


@router.get("/stock-analysis/workbench")
def stock_analysis_workbench(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
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
    return timed_api_call(
        "/ui/market-data/stock-analysis/workbench",
        lambda: stock_analysis_workbench_envelope(
            duckdb_path=str(settings.duckdb_path),
            as_of_date=as_of_date,
            choice_stock_catalog_file=settings.choice_stock_catalog_file,
            include=include,
            sector_window_days=sector_window_days,
            top_k=top_k,
        ),
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
    livermore_envelope = livermore_strategy_envelope_from_catalog(
        duckdb_path=str(settings.duckdb_path),
        as_of_date=as_of_date,
        choice_stock_catalog_file=settings.choice_stock_catalog_file,
    )
    livermore_meta = _mapping(livermore_envelope.get("result_meta"))
    livermore_payload = _dict_payload(livermore_envelope.get("result"))
    resolved_as_of_date = _optional_text(livermore_payload.get("as_of_date")) or _optional_text(as_of_date)

    macro_meta: dict[str, object] = {}
    macro_payload: dict[str, object] = {}
    if resolved_as_of_date:
        macro_envelope = get_macro_environment_context(date.fromisoformat(resolved_as_of_date))
        macro_meta = _mapping(macro_envelope.get("result_meta"))
        macro_payload = _dict_payload(macro_envelope.get("result"))
    adversarial_payload, adversarial_meta = load_macro_adversarial_signal_payload(output_dir=None)
    adversarial_meta_for_envelope = (
        {}
        if adversarial_payload.get("status") == "missing"
        and not adversarial_payload.get("items")
        else adversarial_meta
    )
    replay_summary = livermore_candidate_history_backtest_window_summary(
        duckdb_path=str(settings.duckdb_path),
        stock_code=None,
        snapshot_from=resolved_as_of_date[:10] if resolved_as_of_date else None,
        snapshot_to=resolved_as_of_date[:10] if resolved_as_of_date else None,
    )

    result_payload = build_livermore_signal_confluence(
        as_of_date=resolved_as_of_date or "",
        livermore_payload=livermore_payload,
        macro_payload=macro_payload,
        adversarial_payload=adversarial_payload,
        backtest_window_summary=replay_summary,
    )
    _attach_replay_evidence(
        result_payload,
        duckdb_path=str(settings.duckdb_path),
        as_of_date=resolved_as_of_date,
        replay_summary=replay_summary,
    )
    return _with_livermore_workbench_summary(
        build_result_envelope(
            basis="analytical",
            trace_id=f"tr_livermore_signal_confluence_{date.today().strftime('%Y%m%d')}",
            result_kind=LIVERMORE_SIGNAL_CONFLUENCE_RESULT_KIND,
            cache_version=LIVERMORE_SIGNAL_CONFLUENCE_CACHE_VERSION,
            source_version=_combine_lineage(
                [
                    _meta_source_version(livermore_meta),
                    _meta_source_version(macro_meta),
                    _meta_source_version(adversarial_meta_for_envelope),
                ],
                empty_value="sv_livermore_signal_confluence_empty",
            ),
            rule_version=LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION,
            quality_flag=_merge_quality_flag(
                _meta_quality_flag(livermore_meta),
                _meta_quality_flag(macro_meta),
                _meta_quality_flag(adversarial_meta_for_envelope),
            ),
            vendor_version=_combine_lineage(
                [
                    _meta_vendor_version(livermore_meta),
                    _meta_vendor_version(macro_meta),
                    _meta_vendor_version(adversarial_meta_for_envelope),
                ],
                empty_value="vv_none",
            ),
            vendor_status=_merge_vendor_status(
                _meta_vendor_status(livermore_meta),
                _meta_vendor_status(macro_meta),
                _meta_vendor_status(adversarial_meta_for_envelope),
            ),
            fallback_mode=_merge_fallback_mode(
                _meta_fallback_mode(livermore_meta),
                _meta_fallback_mode(macro_meta),
                _meta_fallback_mode(adversarial_meta_for_envelope),
            ),
            filters_applied={
                "requested_as_of_date": _optional_text(as_of_date),
                "as_of_date": resolved_as_of_date,
            },
            tables_used=_combine_tables(
                _meta_tables_used(livermore_meta),
                _meta_tables_used(macro_meta),
                _meta_tables_used(adversarial_meta_for_envelope),
            ),
            evidence_rows=(
                _safe_int(_meta_evidence_rows(livermore_meta))
                + _safe_int(_meta_evidence_rows(macro_meta))
                + _safe_int(_meta_evidence_rows(adversarial_meta_for_envelope))
            ),
            result_payload=result_payload,
        ),
        summary_kind="signal_confluence",
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

    try:
        from backend.app.tasks.livermore_position_snapshot_materialize import (
            materialize_livermore_position_snapshot,
        )

        payload = materialize_livermore_position_snapshot(
            as_of_date=request.as_of_date,
            csv_path=str(csv_path),
            duckdb_path=str(settings.duckdb_path),
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    block_reason = _risk_exit_input_block_reason(
        duckdb_path=str(settings.duckdb_path),
        as_of_date=request.as_of_date,
    )
    payload["risk_exit_input_status"] = "blocked" if block_reason else "ready"
    payload["risk_exit_input_block_reason"] = block_reason
    return payload


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

        payload = materialize_livermore_position_snapshot_rows(
            as_of_date=request.as_of_date,
            rows=[position.model_dump() for position in request.positions],
            duckdb_path=str(settings.duckdb_path),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    block_reason = _risk_exit_input_block_reason(
        duckdb_path=str(settings.duckdb_path),
        as_of_date=request.as_of_date,
    )
    payload["risk_exit_input_status"] = "blocked" if block_reason else "ready"
    payload["risk_exit_input_block_reason"] = block_reason
    return payload


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
    return timed_api_call(
        "/ui/market-data/livermore/stock-detail",
        lambda: livermore_stock_detail_envelope(
            duckdb_path=str(settings.duckdb_path),
            stock_code=cleaned,
            as_of_date=parsed_as_of,
            lookback=lookback,
        ),
    )


@router.get("/livermore/candidate-history")
def livermore_candidate_history(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    stock_code: str | None = Query(default=None, max_length=16),
    snapshot_from: str | None = Query(default=None),
    snapshot_to: str | None = Query(default=None),
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

    settings = get_settings()
    _ensure_livermore_read_allowed(settings=settings, auth=auth)
    return timed_api_call(
        "/ui/market-data/livermore/candidate-history",
        lambda: _with_livermore_workbench_summary(
            livermore_candidate_history_envelope(
                duckdb_path=str(settings.duckdb_path),
                stock_code=stock_code,
                snapshot_from=snapshot_from,
                snapshot_to=snapshot_to,
                limit=limit,
            ),
            summary_kind="candidate_history",
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
    return timed_api_call(
        "/ui/market-data/livermore/strategy-score",
        lambda: _with_livermore_workbench_summary(
            livermore_candidate_history_strategy_score_envelope(
                duckdb_path=str(settings.duckdb_path),
                snapshot_from=snapshot_from,
                snapshot_to=snapshot_to,
                current_market_state=current_market_state,
                min_sample=min_sample,
                primary_horizon=primary_horizon,
                macro_context_loader=_livermore_macro_context_v1_for_date,
            ),
            summary_kind="strategy_score",
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
    return timed_api_call(
        "/ui/market-data/livermore/strategy-optimization",
        lambda: _with_livermore_workbench_summary(
            livermore_candidate_history_strategy_optimization_envelope(
                duckdb_path=str(settings.duckdb_path),
                snapshot_from=snapshot_from,
                snapshot_to=snapshot_to,
                current_market_state=current_market_state,
                min_sample=min_sample,
                primary_horizon=primary_horizon,
                macro_context_loader=_livermore_macro_context_v1_for_date,
            ),
            summary_kind="strategy_optimization",
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
    return timed_api_call(
        "/ui/market-data/livermore/cycle-proxy-backtest",
        lambda: _with_livermore_workbench_summary(
            livermore_candidate_history_cycle_proxy_backtest_envelope(
                duckdb_path=str(settings.duckdb_path),
                snapshot_from=snapshot_from,
                snapshot_to=snapshot_to,
            ),
            summary_kind="cycle_proxy_backtest",
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
    return timed_api_call(
        "/ui/market-data/livermore/candidate-history-portfolio-backtest",
        lambda: _with_livermore_workbench_summary(
            livermore_candidate_history_portfolio_backtest_envelope(
                duckdb_path=str(settings.duckdb_path),
                snapshot_from=snapshot_from,
                snapshot_to=snapshot_to,
            ),
            summary_kind="candidate_history_portfolio_backtest",
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
    return sum(1 for item in value if not (isinstance(item, dict) and str(item.get("severity") or "").lower() == "info"))


def _actionable_unsupported_output_count(value: object) -> int | None:
    if not isinstance(value, list):
        return None
    return sum(1 for item in value if not (isinstance(item, dict) and _is_known_livermore_policy_pause(item.get("reason"))))


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


def _list_of_mappings(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _dict_payload(value: object) -> dict[str, object]:
    return _mapping(value)


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _non_negative_int(value: object, *, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 0)


def _normalized_stock_code(value: object) -> str:
    return str(value or "").strip().upper()


def _replay_sample_item(item: dict[str, object]) -> dict[str, object]:
    return {
        "stock_code": item.get("stock_code"),
        "stock_name": item.get("stock_name"),
        "candidate_rank": item.get("candidate_rank"),
        "signal_kind": item.get("signal_kind"),
        "data_status": item.get("data_status"),
    }


def _meta_source_version(meta: dict[str, object]) -> object:
    source = _mapping(meta.get("source"))
    return meta.get("source_version") or source.get("source_version") or source.get("version")


def _meta_quality_flag(meta: dict[str, object]) -> object:
    source = _mapping(meta.get("source"))
    return meta.get("quality_flag") or source.get("quality_flag") or source.get("status")


def _meta_vendor_version(meta: dict[str, object]) -> object:
    vendor = _mapping(meta.get("vendor"))
    return meta.get("vendor_version") or vendor.get("vendor_version") or vendor.get("version")


def _meta_vendor_status(meta: dict[str, object]) -> object:
    vendor = _mapping(meta.get("vendor"))
    return meta.get("vendor_status") or vendor.get("vendor_status") or vendor.get("status")


def _meta_fallback_mode(meta: dict[str, object]) -> object:
    source = _mapping(meta.get("source"))
    return meta.get("fallback_mode") or source.get("fallback_mode")


def _meta_tables_used(meta: dict[str, object]) -> object:
    return meta.get("tables_used") or meta.get("tables")


def _meta_evidence_rows(meta: dict[str, object]) -> object:
    evidence = _mapping(meta.get("evidence"))
    return meta.get("evidence_rows") or evidence.get("evidence_rows") or evidence.get("rows")


def _combine_lineage(values: list[object], *, empty_value: str) -> str:
    unique_values: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in unique_values:
            unique_values.append(text)
    if not unique_values:
        return empty_value
    if len(unique_values) == 1:
        return unique_values[0]
    return "__".join(unique_values)


def _merge_quality_flag(*values: object) -> str:
    normalized = {str(value or "").strip() for value in values if str(value or "").strip()}
    if "error" in normalized:
        return "error"
    if "stale" in normalized:
        return "stale"
    if "warning" in normalized:
        return "warning"
    return "ok"


def _merge_vendor_status(*values: object) -> str:
    normalized = {str(value or "").strip() for value in values if str(value or "").strip()}
    if "vendor_unavailable" in normalized:
        return "vendor_unavailable"
    if "vendor_stale" in normalized:
        return "vendor_stale"
    return "ok"


def _merge_fallback_mode(*values: object) -> str:
    if any(str(value or "").strip() == "latest_snapshot" for value in values):
        return "latest_snapshot"
    return "none"


def _combine_tables(*values: object) -> list[str]:
    combined: list[str] = []
    for value in values:
        if not isinstance(value, list):
            continue
        for item in value:
            text = str(item or "").strip()
            if text and text not in combined:
                combined.append(text)
    return combined


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


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
    return timed_api_call(
        "/ui/market-data/livermore/sector-rank-series",
        lambda: _with_livermore_workbench_summary(
            livermore_sector_rank_series_envelope(
                duckdb_path=str(settings.duckdb_path),
                as_of_date=parsed_as_of,
                window_days=window_days,
                sector_code=sector_code,
                top_k=top_k,
            ),
            summary_kind="sector_rank_series",
        ),
    )
