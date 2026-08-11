from __future__ import annotations

from datetime import date
from typing import Annotated

from backend.app.api.deps import ensure_read_allowed
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.risk_tensor_service import (
    risk_tensor_dates_envelope,
    risk_tensor_envelope,
    risk_tensor_history_envelope,
)
from backend.app.services.risk_scenario_stress_service import risk_scenario_stress_envelope
from backend.app.services.formal_result_runtime import build_result_envelope
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/risk", tags=["risk"])


def _risk_tensor_unavailable_response(
    *,
    error: RuntimeError,
    result_kind: str,
    basis: str,
    report_date: str | None = None,
) -> JSONResponse:
    envelope = build_result_envelope(
        basis=basis,  # type: ignore[arg-type]
        trace_id="trace_risk_tensor_unavailable",
        result_kind=result_kind,
        cache_version="cv_risk_tensor_unavailable",
        source_version="sv_risk_tensor_unavailable",
        rule_version="rv_risk_tensor_unavailable",
        quality_flag="error",
        vendor_status="vendor_unavailable",
        source_surface="risk_tensor",
        requested_report_date=report_date,
        resolved_report_date=None,
        as_of_date=None,
        result_payload={"error": str(error), "readiness": "unavailable"},
    )
    return JSONResponse(status_code=503, content=envelope)


def _ensure_risk_tensor_read_allowed(auth: AuthContext, settings) -> None:
    ensure_read_allowed(auth, "risk_tensor", settings=settings, authorize=ensure_user_allowed)


def _validate_risk_report_date(report_date: str) -> None:
    try:
        date.fromisoformat(report_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid report_date. Expected YYYY-MM-DD.") from exc


@router.get("/tensor/dates")
def risk_tensor_dates(auth: Annotated[AuthContext, Depends(get_auth_context)]) -> dict:
    settings = get_settings()
    _ensure_risk_tensor_read_allowed(auth, settings)
    try:
        return risk_tensor_dates_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
        )
    except RuntimeError as exc:
        return _risk_tensor_unavailable_response(
            error=exc,
            result_kind="risk.tensor.dates",
            basis="formal",
        )


@router.get("/tensor")
def risk_tensor(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str = Query(...),
) -> dict:
    _validate_risk_report_date(report_date)
    settings = get_settings()
    _ensure_risk_tensor_read_allowed(auth, settings)
    try:
        return risk_tensor_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=report_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        return _risk_tensor_unavailable_response(
            error=exc,
            result_kind="risk.tensor",
            basis="formal",
            report_date=report_date,
        )


@router.get("/tensor/history")
def risk_tensor_history(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str = Query(...),
    periods: int = Query(24, ge=2, le=60),
) -> dict:
    _validate_risk_report_date(report_date)
    settings = get_settings()
    _ensure_risk_tensor_read_allowed(auth, settings)
    try:
        return risk_tensor_history_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=report_date,
            periods=periods,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        return _risk_tensor_unavailable_response(
            error=exc,
            result_kind="risk.tensor.history",
            basis="formal",
            report_date=report_date,
        )


@router.get("/scenario-stress")
def risk_scenario_stress(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str = Query(...),
) -> dict:
    _validate_risk_report_date(report_date)
    settings = get_settings()
    _ensure_risk_tensor_read_allowed(auth, settings)
    try:
        return risk_scenario_stress_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=report_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        return _risk_tensor_unavailable_response(
            error=exc,
            result_kind="risk.tensor.scenario_stress",
            basis="scenario",
            report_date=report_date,
        )
