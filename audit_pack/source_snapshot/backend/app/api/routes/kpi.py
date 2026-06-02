from __future__ import annotations

import csv
from io import StringIO
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services import kpi_workbench_service
from backend.app.services.kpi_service import kpi_owners_payload, kpi_period_summary_payload

router = APIRouter(prefix="/api/kpi", tags=["kpi"])


class KpiMetricUpsertRequest(BaseModel):
    metric_code: str
    metric_name: str
    major_category: str
    owner_id: int
    year: int
    score_weight: str
    data_source_type: str
    scoring_rule_type: str
    indicator_category: str | None = None
    target_value: str | None = None
    target_text: str | None = None
    unit: str | None = None
    scoring_text: str | None = None
    remarks: str | None = None


class KpiValueCreateRequest(BaseModel):
    metric_id: int
    as_of_date: str
    target_value: str | None = None
    actual_value: str | None = None
    actual_text: str | None = None
    progress_pct: str | None = None
    source: str | None = None


class KpiValueUpdateRequest(BaseModel):
    target_value: str | None = None
    actual_value: str | None = None
    actual_text: str | None = None
    progress_pct: str | None = None
    score_value: str | None = None
    source: str | None = None


class KpiValueBatchItem(BaseModel):
    metric_id: int
    actual_value: str | None = None
    progress_pct: str | None = None


class KpiValuesBatchRequest(BaseModel):
    as_of_date: str
    items: list[KpiValueBatchItem]


class KpiFetchAndRecalcRequest(BaseModel):
    metric_ids: list[int] | None = None


def _get_dsn() -> str:
    settings = get_settings()
    return str(settings.governance_sql_dsn or settings.postgres_dsn)


def _body_dict(model: BaseModel) -> dict[str, object]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _raise_workbench_http_error(exc: Exception) -> None:
    if isinstance(exc, kpi_workbench_service.KpiNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, kpi_workbench_service.KpiInvalidDateError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, kpi_workbench_service.KpiStorageError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    raise exc


def _render_report_csv(*, rows: list[dict[str, object]], year: int, as_of_date: str | None) -> PlainTextResponse:
    buffer = StringIO()
    fieldnames = [
        "owner_name",
        "org_unit",
        "major_category",
        "indicator_category",
        "metric_name",
        "target_value",
        "target_text",
        "unit",
        "score_weight",
        "scoring_text",
        "actual_value",
        "completion_ratio",
        "progress_pct",
        "score_value",
        "remarks",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    suffix = as_of_date or "latest"
    return PlainTextResponse(
        buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="kpi_report_{year}_{suffix}.csv"',
        },
    )


@router.get("/owners")
def kpi_owners(
    year: int | None = Query(None, ge=2000, le=2100),
    is_active: bool | None = Query(True),
) -> dict:
    try:
        return kpi_owners_payload(dsn=_get_dsn(), year=year, is_active=is_active)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/values/summary")
def kpi_values_summary(
    owner_id: int = Query(..., ge=1),
    year: int = Query(..., ge=2000, le=2100),
    period_type: str = Query(...),
    period_value: int | None = Query(None),
) -> dict:
    try:
        return kpi_period_summary_payload(
            dsn=_get_dsn(),
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
def list_kpi_metrics(
    owner_id: int | None = Query(None, ge=1),
    year: int | None = Query(None, ge=2000, le=2100),
    is_active: bool | None = Query(None),
) -> dict:
    try:
        return kpi_workbench_service.list_metrics(
            dsn=_get_dsn(),
            owner_id=owner_id,
            year=year,
            is_active=is_active,
        )
    except Exception as exc:
        _raise_workbench_http_error(exc)


@router.get("/metrics/{metric_id}")
def get_kpi_metric(metric_id: int) -> dict:
    try:
        return kpi_workbench_service.get_metric(dsn=_get_dsn(), metric_id=metric_id)
    except Exception as exc:
        _raise_workbench_http_error(exc)


@router.post("/metrics", status_code=201)
def create_kpi_metric(
    body: KpiMetricUpsertRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict:
    settings = get_settings()
    try:
        ensure_user_allowed(auth=auth, settings=settings, resource="kpi.metric", action="write")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        return kpi_workbench_service.create_metric(dsn=_get_dsn(), data=_body_dict(body))
    except Exception as exc:
        _raise_workbench_http_error(exc)


@router.put("/metrics/{metric_id}")
def update_kpi_metric(
    metric_id: int,
    body: KpiMetricUpsertRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict:
    settings = get_settings()
    try:
        ensure_user_allowed(auth=auth, settings=settings, resource="kpi.metric", action="write")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        return kpi_workbench_service.update_metric(dsn=_get_dsn(), metric_id=metric_id, data=_body_dict(body))
    except Exception as exc:
        _raise_workbench_http_error(exc)


@router.delete("/metrics/{metric_id}", status_code=204)
def delete_kpi_metric(
    metric_id: int,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> None:
    settings = get_settings()
    try:
        ensure_user_allowed(auth=auth, settings=settings, resource="kpi.metric", action="delete")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        kpi_workbench_service.delete_metric(dsn=_get_dsn(), metric_id=metric_id)
    except Exception as exc:
        _raise_workbench_http_error(exc)


@router.get("/values")
def get_kpi_values(
    owner_id: int = Query(..., ge=1),
    as_of_date: str = Query(...),
    include_trace: bool = Query(False),
) -> dict:
    try:
        return kpi_workbench_service.get_values(
            dsn=_get_dsn(),
            owner_id=owner_id,
            as_of_date=as_of_date,
            include_trace=include_trace,
        )
    except Exception as exc:
        _raise_workbench_http_error(exc)


@router.post("/values", status_code=201)
def create_kpi_value(
    body: KpiValueCreateRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict:
    settings = get_settings()
    try:
        ensure_user_allowed(auth=auth, settings=settings, resource="kpi.value", action="write")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        return kpi_workbench_service.create_value(dsn=_get_dsn(), data=_body_dict(body))
    except Exception as exc:
        _raise_workbench_http_error(exc)


@router.put("/values/{value_id}")
def update_kpi_value(
    value_id: int,
    body: KpiValueUpdateRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict:
    settings = get_settings()
    try:
        ensure_user_allowed(auth=auth, settings=settings, resource="kpi.value", action="write")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        return kpi_workbench_service.update_value(dsn=_get_dsn(), value_id=value_id, data=_body_dict(body))
    except Exception as exc:
        _raise_workbench_http_error(exc)


@router.post("/values/batch")
def batch_update_kpi_values(
    body: KpiValuesBatchRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict:
    settings = get_settings()
    try:
        ensure_user_allowed(auth=auth, settings=settings, resource="kpi.value", action="write")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        items = [_body_dict(item) for item in body.items]
        return kpi_workbench_service.batch_update_values(
            dsn=_get_dsn(),
            as_of_date=body.as_of_date,
            items=items,
        )
    except Exception as exc:
        _raise_workbench_http_error(exc)


@router.post("/fetch_and_recalc")
def fetch_and_recalc_kpi(
    body: KpiFetchAndRecalcRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    owner_id: int = Query(..., ge=1),
    as_of_date: str = Query(...),
) -> dict:
    settings = get_settings()
    try:
        ensure_user_allowed(auth=auth, settings=settings, resource="kpi.value", action="write")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        return kpi_workbench_service.fetch_and_recalc(
            dsn=_get_dsn(),
            owner_id=owner_id,
            as_of_date=as_of_date,
            metric_ids=body.metric_ids,
        )
    except Exception as exc:
        _raise_workbench_http_error(exc)


@router.get("/report", response_model=None)
def get_kpi_report(
    year: int = Query(..., ge=2000, le=2100),
    owner_id: int | None = Query(None, ge=1),
    as_of_date: str | None = Query(None),
    format: str | None = Query(None),
) -> object:
    try:
        payload = kpi_workbench_service.build_report(
            dsn=_get_dsn(),
            year=year,
            owner_id=owner_id,
            as_of_date=as_of_date,
        )
    except Exception as exc:
        _raise_workbench_http_error(exc)

    if str(format or "").lower() == "csv":
        return _render_report_csv(rows=payload["rows"], year=year, as_of_date=as_of_date)
    return payload
