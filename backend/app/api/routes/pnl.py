from importlib import import_module
from typing import Annotated

from backend.app.api.perf_logging import timed_api_call
from backend.app.governance.settings import get_settings
from backend.app.schemas.pnl import PnlByBusinessAnalysisDimension, PnlByBusinessManualAdjustmentRequest
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/api")


def _pnl_service():
    return import_module("backend.app.services.pnl_service")


@router.get("/pnl/dates")
def dates() -> dict[str, object]:
    settings = get_settings()
    try:
        return _pnl_service().pnl_dates_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/pnl/data")
def data(
    date: str = Query(
        ...,
        description="Requested report date for formal /api/pnl data.",
    ),
) -> dict[str, object]:
    settings = get_settings()
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


@router.get("/pnl/bridge")
def pnl_bridge(
    report_date: str = Query(..., description="Requested report date for formal /pnl bridge."),
) -> dict[str, object]:
    settings = get_settings()
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


@router.get("/pnl/overview")
def overview(
    report_date: str = Query(..., description="Requested report date for formal /api/pnl overview."),
) -> dict[str, object]:
    settings = get_settings()
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


@router.get("/pnl/v1-data")
def v1_data(
    date: str = Query(
        ...,
        description="Requested report date for V1-compatible /api/pnl detail data.",
    ),
) -> dict[str, object]:
    settings = get_settings()
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


@router.get("/pnl/by-business")
def by_business(
    report_date: str = Query(..., description="Requested report date for governed PnL by ZQTZ business type 1."),
) -> dict[str, object]:
    settings = get_settings()
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


@router.get("/pnl/by-business-ytd")
def by_business_ytd(
    year: int = Query(..., description="Requested calendar year for V1-compatible PnL by business type."),
    as_of_date: str | None = Query(
        None,
        description="Optional report-date cutoff for V1-compatible YTD PnL.",
    ),
) -> dict[str, object]:
    settings = get_settings()
    try:
        return _pnl_service().pnl_by_business_ytd_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            year=year,
            as_of_date=as_of_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/pnl/by-business-monthly")
def by_business_monthly(
    year: int = Query(..., description="Requested calendar year for monthly PnL by business type."),
    as_of_date: str | None = Query(
        None,
        description="Optional report-date cutoff for monthly PnL by business type.",
    ),
) -> dict[str, object]:
    settings = get_settings()
    try:
        return _pnl_service().pnl_by_business_monthly_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            year=year,
            as_of_date=as_of_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/pnl/by-business-analysis")
def by_business_analysis(
    year: int = Query(..., description="Requested calendar year for PnL by business analysis."),
    as_of_date: str | None = Query(
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
    try:
        return timed_api_call(
            "/api/pnl/by-business-analysis",
            lambda: _pnl_service().pnl_by_business_analysis_envelope(
                duckdb_path=str(settings.duckdb_path),
                governance_dir=str(settings.governance_path),
                year=year,
                as_of_date=as_of_date,
                business_key=business_key,
                dimension=dimension,
            ),
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
    return _pnl_service().create_pnl_by_business_manual_adjustment(settings, payload)


@router.get("/pnl/by-business/manual-adjustments")
def list_by_business_manual_adjustments(
    report_date: str = Query(..., description="Report date for PnL by-business manual adjustment audit."),
) -> dict[str, object]:
    return _pnl_service().list_pnl_by_business_manual_adjustments(get_settings(), report_date=report_date)


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


@router.get("/pnl/yearly-summary")
def yearly_summary(
    year: int = Query(..., description="Requested calendar year for governed PnL by ZQTZ business type 1."),
) -> dict[str, object]:
    settings = get_settings()
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


@router.post("/data/refresh_pnl")
def refresh_pnl(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
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
        return service.refresh_pnl(settings, report_date=report_date)
    except service.PnlRefreshConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/data/import_status/pnl")
def import_status(run_id: str | None = Query(None)) -> dict[str, object]:
    settings = get_settings()
    try:
        return _pnl_service().pnl_import_status(settings, run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
