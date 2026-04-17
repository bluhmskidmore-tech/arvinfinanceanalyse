from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.governance.settings import get_settings
from backend.app.services.kpi_service import kpi_owners_payload, kpi_period_summary_payload

router = APIRouter(prefix="/api/kpi", tags=["kpi"])


@router.get("/owners")
def kpi_owners(
    year: int | None = Query(None, ge=2000, le=2100),
    is_active: bool | None = Query(True),
) -> dict[str, object]:
    settings = get_settings()
    try:
        return kpi_owners_payload(
            dsn=str(settings.governance_sql_dsn or settings.postgres_dsn),
            year=year,
            is_active=is_active,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/values/summary")
def kpi_values_summary(
    owner_id: int = Query(..., ge=1),
    year: int = Query(..., ge=2000, le=2100),
    period_type: str = Query(...),
    period_value: int | None = Query(None),
) -> dict[str, object]:
    settings = get_settings()
    try:
        return kpi_period_summary_payload(
            dsn=str(settings.governance_sql_dsn or settings.postgres_dsn),
            owner_id=owner_id,
            year=year,
            period_type=period_type,
            period_value=period_value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
