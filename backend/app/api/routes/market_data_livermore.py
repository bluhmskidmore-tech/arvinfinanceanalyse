from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Annotated

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
from backend.app.services.livermore_candidate_history_service import livermore_candidate_history_envelope
from backend.app.services.livermore_stock_detail_service import livermore_stock_detail_envelope
from backend.app.services.market_data_livermore_service import (
    _risk_exit_input_block_reason,
    livermore_strategy_envelope,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/ui/market-data", tags=["market-data"])
_STOCK_CODE_LIVERMORE_PATTERN = re.compile(r"^[0-9A-Za-z.\-]{1,16}$")
LIVERMORE_SIGNAL_CONFLUENCE_RESULT_KIND = "market_data.livermore.signal_confluence"
LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION = "rv_livermore_signal_confluence_v1"
LIVERMORE_SIGNAL_CONFLUENCE_CACHE_VERSION = "cv_livermore_signal_confluence_v1"


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

    result_payload = build_livermore_signal_confluence(
        as_of_date=resolved_as_of_date or "",
        livermore_payload=livermore_payload,
        macro_payload=macro_payload,
    )
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_signal_confluence_{date.today().strftime('%Y%m%d')}",
        result_kind=LIVERMORE_SIGNAL_CONFLUENCE_RESULT_KIND,
        cache_version=LIVERMORE_SIGNAL_CONFLUENCE_CACHE_VERSION,
        source_version=_combine_lineage(
            [livermore_meta.get("source_version"), macro_meta.get("source_version")],
            empty_value="sv_livermore_signal_confluence_empty",
        ),
        rule_version=LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION,
        quality_flag=_merge_quality_flag(
            livermore_meta.get("quality_flag"),
            macro_meta.get("quality_flag"),
        ),
        vendor_version=_combine_lineage(
            [livermore_meta.get("vendor_version"), macro_meta.get("vendor_version")],
            empty_value="vv_none",
        ),
        vendor_status=_merge_vendor_status(
            livermore_meta.get("vendor_status"),
            macro_meta.get("vendor_status"),
        ),
        fallback_mode=_merge_fallback_mode(
            livermore_meta.get("fallback_mode"),
            macro_meta.get("fallback_mode"),
        ),
        filters_applied={
            "requested_as_of_date": _optional_text(as_of_date),
            "as_of_date": resolved_as_of_date,
        },
        tables_used=_combine_tables(
            livermore_meta.get("tables_used"),
            macro_meta.get("tables_used"),
        ),
        evidence_rows=_safe_int(livermore_meta.get("evidence_rows")) + _safe_int(macro_meta.get("evidence_rows")),
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
    return livermore_stock_detail_envelope(
        duckdb_path=str(settings.duckdb_path),
        stock_code=cleaned,
        as_of_date=parsed_as_of,
        lookback=lookback,
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
    return livermore_candidate_history_envelope(
        duckdb_path=str(settings.duckdb_path),
        stock_code=stock_code,
        snapshot_from=snapshot_from,
        snapshot_to=snapshot_to,
        limit=limit,
    )


def _mapping(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _dict_payload(value: object) -> dict[str, object]:
    return _mapping(value)


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


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
