from importlib import import_module

from fastapi import APIRouter, HTTPException, Query

from backend.app.governance.settings import get_settings


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
        description="Requested report date for future formal /api/pnl data.",
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
    report_date: str = Query(..., description="Requested report date for formal /pnl overview."),
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


@router.post("/data/refresh_pnl")
def refresh_pnl(report_date: str | None = Query(None)) -> dict[str, object]:
    settings = get_settings()
    service = _pnl_service()
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
