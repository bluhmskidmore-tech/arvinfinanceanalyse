from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Annotated

import duckdb
from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_stock_adapter import load_choice_stock_readiness
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.livermore_gate_supplement_compute_service import (
    compute_and_materialize_gate_supplement,
)
from backend.app.services.livermore_signal_confluence_service import (
    build_livermore_signal_confluence,
)
from backend.app.services.macro_bond_linkage_service import get_macro_bond_linkage
from backend.app.services.livermore_candidate_history_service import (
    livermore_candidate_history_envelope,
    livermore_candidate_history_strategy_score_envelope,
)
from backend.app.services.livermore_sector_rank_series_service import livermore_sector_rank_series_envelope
from backend.app.services.livermore_stock_detail_service import livermore_stock_detail_envelope
from backend.app.services.market_data_livermore_service import (
    _risk_exit_input_block_reason,
    livermore_strategy_envelope,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.api.perf_logging import timed_api_call

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
    try:
        envelope = livermore_candidate_history_envelope(
            duckdb_path=duckdb_path,
            stock_code=stock_code,
            snapshot_from=snapshot_from,
            snapshot_to=snapshot_to,
            limit=500,
        )
    except duckdb.Error:
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
    try:
        envelope = livermore_candidate_history_envelope(
            duckdb_path=duckdb_path,
            stock_code=None,
            snapshot_from=snapshot_as_of_date,
            snapshot_to=snapshot_as_of_date,
            limit=max(row_count, 5),
        )
    except duckdb.Error:
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
def livermore_strategy(as_of_date: str | None = Query(None)) -> dict[str, object]:
    if as_of_date is not None:
        try:
            date.fromisoformat(as_of_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    stock_readiness = load_choice_stock_readiness(settings.choice_stock_catalog_file)
    return livermore_strategy_envelope(
        duckdb_path=str(settings.duckdb_path),
        as_of_date=as_of_date,
        stock_readiness=stock_readiness,
    )


@router.get("/livermore/signal-confluence")
def livermore_signal_confluence(as_of_date: str | None = Query(None)) -> dict[str, object]:
    if as_of_date is not None:
        try:
            date.fromisoformat(as_of_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    stock_readiness = load_choice_stock_readiness(settings.choice_stock_catalog_file)
    livermore_envelope = livermore_strategy_envelope(
        duckdb_path=str(settings.duckdb_path),
        as_of_date=as_of_date,
        stock_readiness=stock_readiness,
    )
    livermore_meta = _mapping(livermore_envelope.get("result_meta"))
    livermore_payload = _dict_payload(livermore_envelope.get("result"))
    resolved_as_of_date = _optional_text(livermore_payload.get("as_of_date")) or _optional_text(as_of_date)

    macro_meta: dict[str, object] = {}
    macro_payload: dict[str, object] = {}
    if resolved_as_of_date:
        macro_envelope = get_macro_bond_linkage(date.fromisoformat(resolved_as_of_date))
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
    return build_result_envelope(
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
    try:
        result = compute_and_materialize_gate_supplement(
            duckdb_path=str(settings.duckdb_path),
            as_of_date=parsed_date,
            lookback_days=lookback_days,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return result


@router.get("/livermore/stock-detail")
def livermore_stock_detail(
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
    return timed_api_call(
        "/ui/market-data/livermore/candidate-history",
        lambda: livermore_candidate_history_envelope(
            duckdb_path=str(settings.duckdb_path),
            stock_code=stock_code,
            snapshot_from=snapshot_from,
            snapshot_to=snapshot_to,
            limit=limit,
        ),
    )


@router.get("/livermore/strategy-score")
def livermore_strategy_score(
    snapshot_from: str | None = Query(default=None),
    snapshot_to: str | None = Query(default=None),
    current_market_state: str | None = Query(default=None, max_length=32),
    min_sample: int = Query(default=20, ge=1, le=10000),
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
    return timed_api_call(
        "/ui/market-data/livermore/strategy-score",
        lambda: livermore_candidate_history_strategy_score_envelope(
            duckdb_path=str(settings.duckdb_path),
            snapshot_from=snapshot_from,
            snapshot_to=snapshot_to,
            current_market_state=current_market_state,
            min_sample=min_sample,
            primary_horizon=primary_horizon,
        ),
    )


def _mapping(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


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
    return timed_api_call(
        "/ui/market-data/livermore/sector-rank-series",
        lambda: livermore_sector_rank_series_envelope(
            duckdb_path=str(settings.duckdb_path),
            as_of_date=parsed_as_of,
            window_days=window_days,
            sector_code=sector_code,
            top_k=top_k,
        ),
    )
