from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Body, HTTPException, Path, Query

from backend.app.governance.settings import get_settings
from backend.app.services.kpi_service import kpi_owners_payload, kpi_period_summary_payload

router = APIRouter(prefix="/api/kpi", tags=["kpi"])

_KPI_RESERVED_DETAIL = (
    "KPI metrics/value-management/report routes are reserved and not backed by the "
    "current governed rollout yet. Only /api/kpi/owners and /api/kpi/values/summary "
    "are currently live read surfaces."
)


def _raise_kpi_not_promoted() -> None:
    raise HTTPException(status_code=503, detail=_KPI_RESERVED_DETAIL)


def _validate_optional_iso_date(value: str | None) -> str | None:
    candidate = str(value or "").strip()
    if not candidate:
        return None
    try:
        date.fromisoformat(candidate)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc
    return candidate


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


@router.get("/metrics")
def kpi_metrics(
    year: int | None = Query(None, ge=2000, le=2100),
    owner_id: int | None = Query(None, ge=1),
    is_active: bool | None = Query(True),
) -> dict[str, object]:
    _raise_kpi_not_promoted()


@router.get("/metrics/{metric_id}")
def kpi_metric_detail(metric_id: int = Path(..., ge=1)) -> dict[str, object]:
    _raise_kpi_not_promoted()


@router.post("/metrics")
def create_kpi_metric(payload: dict[str, object] = Body(...)) -> dict[str, object]:
    _raise_kpi_not_promoted()


@router.put("/metrics/{metric_id}")
def update_kpi_metric(
    metric_id: int = Path(..., ge=1),
    payload: dict[str, object] = Body(...),
) -> dict[str, object]:
    _raise_kpi_not_promoted()


@router.delete("/metrics/{metric_id}")
def delete_kpi_metric(metric_id: int = Path(..., ge=1)) -> dict[str, object]:
    _raise_kpi_not_promoted()


@router.get("/values")
def kpi_values(
    owner_id: int = Query(..., ge=1),
    as_of_date: str = Query(...),
) -> dict[str, object]:
    _validate_optional_iso_date(as_of_date)
    _raise_kpi_not_promoted()


@router.post("/values")
def create_kpi_value(payload: dict[str, object] = Body(...)) -> dict[str, object]:
    _validate_optional_iso_date(str(payload.get("as_of_date") or ""))
    _raise_kpi_not_promoted()


@router.put("/values/{value_id}")
def update_kpi_value(
    value_id: int = Path(..., ge=1),
    payload: dict[str, object] = Body(...),
) -> dict[str, object]:
    if "as_of_date" in payload:
        _validate_optional_iso_date(str(payload.get("as_of_date") or ""))
    _raise_kpi_not_promoted()


@router.post("/values/batch")
def batch_update_kpi_values(payload: dict[str, object] = Body(...)) -> dict[str, object]:
    _validate_optional_iso_date(str(payload.get("as_of_date") or ""))
    _raise_kpi_not_promoted()


@router.post("/fetch_and_recalc")
def fetch_and_recalc_kpi(
    owner_id: int = Query(..., ge=1),
    as_of_date: str = Query(...),
    payload: dict[str, object] = Body(default_factory=dict),
) -> dict[str, object]:
    _validate_optional_iso_date(as_of_date)
    _raise_kpi_not_promoted()


@router.get("/report")
def kpi_report(
    year: int = Query(..., ge=2000, le=2100),
    as_of_date: str | None = Query(None),
    owner_id: int | None = Query(None, ge=1),
    format: str | None = Query(None),
) -> dict[str, object]:
    _validate_optional_iso_date(as_of_date)
    _raise_kpi_not_promoted()
