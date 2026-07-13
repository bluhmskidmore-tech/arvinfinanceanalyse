from datetime import date
from importlib import import_module
from typing import Annotated

from backend.app.api.perf_logging import timed_api_call
from backend.app.governance.settings import get_settings
from backend.app.schemas.pnl import PnlByBusinessAnalysisDimension, PnlByBusinessManualAdjustmentRequest
from backend.app.schemas.result_meta import ResultEnvelope
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from fastapi import APIRouter, Depends, Header, HTTPException, Query

router = APIRouter(prefix="/api")


def _pnl_service():
    return import_module("backend.app.services.pnl_service")


def _ensure_pnl_read_allowed(auth: AuthContext, settings) -> None:
    try:
        ensure_user_allowed(auth=auth, settings=settings, resource="pnl", action="read")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/pnl/dates", response_model=ResultEnvelope)
def dates(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    _ensure_pnl_read_allowed(auth, settings)
    try:
        return _pnl_service().pnl_dates_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/pnl/data", response_model=ResultEnvelope)
def data(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    date: str = Query(
        ...,
        description="Requested report date for formal /api/pnl data.",
    ),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_pnl_read_allowed(auth, settings)
    try:
        return _pnl_service().pnl_data_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/pnl/bridge", response_model=ResultEnvelope)
def pnl_bridge(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str = Query(..., description="Requested report date for formal /pnl bridge."),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_pnl_read_allowed(auth, settings)
    try:
        return import_module("backend.app.services.pnl_bridge_service").pnl_bridge_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=report_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/pnl/overview", response_model=ResultEnvelope)
def overview(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str = Query(..., description="Requested report date for formal /api/pnl overview."),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_pnl_read_allowed(auth, settings)
    try:
        return _pnl_service().pnl_overview_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=report_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/pnl/v1-data", response_model=ResultEnvelope)
def v1_data(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    date: str = Query(
        ...,
        description="Requested report date for V1-compatible /api/pnl detail data.",
    ),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_pnl_read_allowed(auth, settings)
    try:
        return _pnl_service().pnl_v1_data_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/pnl/by-business", response_model=ResultEnvelope)
def by_business(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str = Query(..., description="Requested report date for governed PnL by ZQTZ business type 1."),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_pnl_read_allowed(auth, settings)
    try:
        return _pnl_service().pnl_by_business_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=report_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/pnl/by-business-ytd", response_model=ResultEnvelope)
def by_business_ytd(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    year: int = Query(..., description="Requested calendar year for V1-compatible PnL by business type."),
    as_of_date: date | None = Query(
        None,
        description="Optional report-date cutoff for V1-compatible YTD PnL.",
    ),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_pnl_read_allowed(auth, settings)
    try:
        return _pnl_service().pnl_by_business_ytd_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            year=year,
            as_of_date=as_of_date.isoformat() if as_of_date else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/pnl/by-business-monthly", response_model=ResultEnvelope)
def by_business_monthly(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    year: int = Query(..., description="Requested calendar year for monthly PnL by business type."),
    as_of_date: date | None = Query(
        None,
        description="Optional report-date cutoff for monthly PnL by business type.",
    ),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_pnl_read_allowed(auth, settings)
    try:
        return _pnl_service().pnl_by_business_monthly_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            year=year,
            as_of_date=as_of_date.isoformat() if as_of_date else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/pnl/by-business-analysis", response_model=ResultEnvelope)
def by_business_analysis(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    year: int = Query(..., description="Requested calendar year for PnL by business analysis."),
    as_of_date: date | None = Query(
        None,
        description="Optional report-date cutoff for PnL by business analysis.",
    ),
    business_key: str | None = Query(
        None,
        description="Optional ZQTZ_ASSET_BOND_ROWS row_key selected from /api/pnl/by-business-ytd.",
    ),
    dimension: PnlByBusinessAnalysisDimension = Query(
        "monthly",
        description="Analysis dimension.",
    ),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_pnl_read_allowed(auth, settings)
    try:
        return timed_api_call(
            "/api/pnl/by-business-analysis",
            lambda: _pnl_service().pnl_by_business_analysis_envelope(
                duckdb_path=str(settings.duckdb_path),
                governance_dir=str(settings.governance_path),
                year=year,
                as_of_date=as_of_date.isoformat() if as_of_date else None,
                business_key=business_key,
                dimension=dimension,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/pnl/by-business-candidate-insights", response_model=ResultEnvelope)
def by_business_candidate_insights(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    year: int = Query(..., description="Requested calendar year for candidate business-type insights."),
    as_of_date: str = Query(..., description="Requested report-date cutoff for candidate business-type insights."),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_pnl_read_allowed(auth, settings)
    try:
        return import_module(
            "backend.app.services.pnl_by_business_candidate_insights"
        ).pnl_by_business_candidate_insights_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            year=year,
            as_of_date=as_of_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/pnl/by-business/manual-adjustments")
def create_by_business_manual_adjustment(
    payload: PnlByBusinessManualAdjustmentRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    _ensure_by_business_adjustment_write_allowed(auth, settings)
    return _pnl_service().create_pnl_by_business_manual_adjustment(
        settings,
        payload,
        created_by=auth.user_id,
    )


@router.get("/pnl/by-business/manual-adjustments")
def list_by_business_manual_adjustments(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str = Query(..., description="Report date for PnL by-business manual adjustment audit."),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_pnl_read_allowed(auth, settings)
    return _pnl_service().list_pnl_by_business_manual_adjustments(settings, report_date=report_date)


@router.post("/pnl/by-business/manual-adjustments/{adjustment_id}/edit")
def edit_by_business_manual_adjustment(
    adjustment_id: str,
    payload: PnlByBusinessManualAdjustmentRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    _ensure_by_business_adjustment_write_allowed(auth, settings)
    try:
        return _pnl_service().update_pnl_by_business_manual_adjustment(
            settings,
            adjustment_id=adjustment_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/pnl/by-business/manual-adjustments/{adjustment_id}/approve")
def approve_by_business_manual_adjustment(
    adjustment_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    _ensure_by_business_adjustment_approve_allowed(auth, settings)
    try:
        return _pnl_service().approve_pnl_by_business_manual_adjustment(
            settings,
            adjustment_id=adjustment_id,
            approved_by=auth.user_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/pnl/by-business/manual-adjustments/{adjustment_id}/revoke")
def revoke_by_business_manual_adjustment(
    adjustment_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    _ensure_by_business_adjustment_write_allowed(auth, settings)
    try:
        return _pnl_service().revoke_pnl_by_business_manual_adjustment(settings, adjustment_id=adjustment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/pnl/by-business/manual-adjustments/{adjustment_id}/restore")
def restore_by_business_manual_adjustment(
    adjustment_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    _ensure_by_business_adjustment_write_allowed(auth, settings)
    try:
        return _pnl_service().restore_pnl_by_business_manual_adjustment(settings, adjustment_id=adjustment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/pnl/yearly-summary", response_model=ResultEnvelope)
def yearly_summary(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    year: int = Query(..., description="Requested calendar year for governed PnL by ZQTZ business type 1."),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_pnl_read_allowed(auth, settings)
    try:
        return _pnl_service().pnl_yearly_summary_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            year=year,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _ensure_by_business_adjustment_write_allowed(auth: AuthContext, settings) -> None:
    try:
        ensure_user_allowed(auth=auth, settings=settings, resource="pnl_by_business.adjustment", action="write")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _ensure_by_business_adjustment_approve_allowed(auth: AuthContext, settings) -> None:
    try:
        ensure_user_allowed(auth=auth, settings=settings, resource="pnl_by_business.adjustment", action="approve")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/data/refresh_pnl")
def refresh_pnl(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    report_date: str | None = Query(None),
) -> dict[str, object]:
    settings = get_settings()
    service = _pnl_service()
    try:
        ensure_user_allowed(auth=auth, settings=settings, resource="formal_pnl", action="refresh")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        return service.refresh_pnl(
            settings,
            report_date=report_date,
            idempotency_key=idempotency_key,
        )
    except service.PnlRefreshConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/data/import_status/pnl")
def import_status(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    run_id: str | None = Query(None),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_pnl_read_allowed(auth, settings)
    try:
        return _pnl_service().pnl_import_status(settings, run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
