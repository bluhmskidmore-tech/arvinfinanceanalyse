from __future__ import annotations

import csv
from io import StringIO
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from backend.app.governance.settings import get_settings
from backend.app.services.kpi_service import kpi_owners_payload, kpi_period_summary_payload
from backend.app.repositories.kpi_repo import KpiRepository

router = APIRouter(prefix="/api/kpi", tags=["kpi"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_dsn() -> str:
    settings = get_settings()
    return str(settings.governance_sql_dsn or settings.postgres_dsn)


def _parse_decimal(value: object | None) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _decimal_text(value: object | None, *, default: str | None = None) -> str | None:
    dec = _parse_decimal(value)
    if dec is None:
        return default
    return format(dec.quantize(Decimal("0.000001")), "f")


def _compute_completion_ratio(
    *,
    target_value: object | None,
    actual_value: object | None,
    progress_pct: object | None,
) -> Decimal | None:
    progress = _parse_decimal(progress_pct)
    if progress is not None:
        return progress
    actual = _parse_decimal(actual_value)
    target = _parse_decimal(target_value)
    if actual is None or target in (None, Decimal("0")):
        return None
    return (actual / target) * Decimal("100")


def _compute_score_value(score_weight: object | None, completion_ratio: object | None) -> Decimal | None:
    weight = _parse_decimal(score_weight)
    ratio = _parse_decimal(completion_ratio)
    if weight is None or ratio is None:
        return None
    return (weight * ratio) / Decimal("100")


def _apply_value_payload(
    *,
    metric,
    value,
    target_value: Decimal | None = None,
    actual_value: Decimal | None = None,
    actual_text: str | None = None,
    progress_pct: Decimal | None = None,
    score_value: Decimal | None = None,
    source: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    if target_value is not None:
        metric.target_value = target_value
        metric.updated_at = now
    if actual_value is not None:
        value.actual_value = actual_value
    if actual_text is not None:
        value.actual_text = actual_text
    if progress_pct is not None:
        value.progress_pct = progress_pct
    completion_ratio = _compute_completion_ratio(
        target_value=metric.target_value,
        actual_value=value.actual_value,
        progress_pct=value.progress_pct,
    )
    value.completion_ratio = completion_ratio
    value.score_value = score_value if score_value is not None else _compute_score_value(metric.score_weight, completion_ratio)
    if source is not None:
        value.source = source
    value.updated_at = now


def _result_item(
    *,
    metric,
    value,
    fetch_status: str,
    score_status: str,
    error_message: str | None = None,
) -> dict:
    return {
        "metric_id": metric.metric_id,
        "metric_code": metric.metric_code,
        "metric_name": metric.metric_name,
        "target_value": _decimal_text(metric.target_value, default="0") or "0",
        "actual_value": _decimal_text(value.actual_value if value else None, default="0") or "0",
        "completion_ratio": _decimal_text(value.completion_ratio if value else None, default="0") or "0",
        "progress_pct": _decimal_text(value.progress_pct if value else None, default="0") or "0",
        "score_value": _decimal_text(value.score_value if value else None, default="0") or "0",
        "fetch_status": fetch_status,
        "score_status": score_status,
        "error_message": error_message,
    }


def _metric_to_dict(metric) -> dict:
    return {
        "metric_id": metric.metric_id,
        "metric_code": metric.metric_code,
        "owner_id": metric.owner_id,
        "year": metric.year,
        "major_category": metric.major_category,
        "indicator_category": metric.indicator_category,
        "metric_name": metric.metric_name,
        "target_value": format(Decimal(str(metric.target_value)), "f") if metric.target_value is not None else None,
        "target_text": metric.target_text,
        "score_weight": format(Decimal(str(metric.score_weight)), "f"),
        "unit": metric.unit,
        "scoring_text": metric.scoring_text,
        "scoring_rule_type": metric.scoring_rule_type,
        "data_source_type": metric.data_source_type,
        "progress_plan": metric.progress_plan,
        "remarks": metric.remarks,
        "is_active": metric.is_active,
        "created_at": metric.created_at.isoformat(),
        "updated_at": metric.updated_at.isoformat(),
    }


def _value_to_dict(v) -> dict:
    def ds(val):
        return format(Decimal(str(val)), "f") if val is not None else None
    return {
        "value_id": v.value_id,
        "metric_id": v.metric_id,
        "as_of_date": v.as_of_date.isoformat(),
        "actual_value": ds(v.actual_value),
        "actual_text": v.actual_text,
        "completion_ratio": ds(v.completion_ratio),
        "progress_pct": ds(v.progress_pct),
        "score_value": ds(v.score_value),
        "source": v.source,
        "created_at": v.created_at.isoformat(),
        "updated_at": v.updated_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Existing endpoints
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Metrics CRUD
# ---------------------------------------------------------------------------

@router.get("/metrics")
def list_kpi_metrics(
    owner_id: int | None = Query(None, ge=1),
    year: int | None = Query(None, ge=2000, le=2100),
    is_active: bool | None = Query(None),
) -> dict:
    from sqlalchemy import select
    from backend.app.models.kpi import KpiMetric
    try:
        repo = KpiRepository(_get_dsn())
        with repo._session_factory() as session:
            stmt = select(KpiMetric)
            if owner_id is not None:
                stmt = stmt.where(KpiMetric.owner_id == owner_id)
            if year is not None:
                stmt = stmt.where(KpiMetric.year == year)
            if is_active is not None:
                stmt = stmt.where(KpiMetric.is_active.is_(is_active))
            stmt = stmt.order_by(KpiMetric.year.desc(), KpiMetric.metric_id.asc())
            rows = session.execute(stmt).scalars().all()
            metrics = [_metric_to_dict(r) for r in rows]
        return {"metrics": metrics, "total": len(metrics)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/metrics/{metric_id}")
def get_kpi_metric(metric_id: int) -> dict:
    from backend.app.models.kpi import KpiMetric
    try:
        repo = KpiRepository(_get_dsn())
        with repo._session_factory() as session:
            metric = session.get(KpiMetric, metric_id)
        if metric is None:
            raise HTTPException(status_code=404, detail=f"KPI metric {metric_id} not found")
        return _metric_to_dict(metric)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/metrics", status_code=201)
def create_kpi_metric(body: KpiMetricUpsertRequest) -> dict:
    from backend.app.models.kpi import KpiMetric
    try:
        repo = KpiRepository(_get_dsn())
        now = datetime.now(timezone.utc)
        metric = KpiMetric(
            metric_code=body.metric_code,
            metric_name=body.metric_name,
            major_category=body.major_category,
            owner_id=body.owner_id,
            year=body.year,
            score_weight=Decimal(body.score_weight),
            data_source_type=body.data_source_type,
            scoring_rule_type=body.scoring_rule_type,
            indicator_category=body.indicator_category,
            target_value=Decimal(body.target_value) if body.target_value else None,
            target_text=body.target_text,
            unit=body.unit,
            scoring_text=body.scoring_text,
            remarks=body.remarks,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        with repo._session_factory() as session:
            session.add(metric)
            session.commit()
            session.refresh(metric)
            return _metric_to_dict(metric)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.put("/metrics/{metric_id}")
def update_kpi_metric(metric_id: int, body: KpiMetricUpsertRequest) -> dict:
    from backend.app.models.kpi import KpiMetric
    try:
        repo = KpiRepository(_get_dsn())
        with repo._session_factory() as session:
            metric = session.get(KpiMetric, metric_id)
            if metric is None:
                raise HTTPException(status_code=404, detail=f"KPI metric {metric_id} not found")
            metric.metric_code = body.metric_code
            metric.metric_name = body.metric_name
            metric.major_category = body.major_category
            metric.owner_id = body.owner_id
            metric.year = body.year
            metric.score_weight = Decimal(body.score_weight)
            metric.data_source_type = body.data_source_type
            metric.scoring_rule_type = body.scoring_rule_type
            metric.indicator_category = body.indicator_category
            metric.target_value = Decimal(body.target_value) if body.target_value else None
            metric.target_text = body.target_text
            metric.unit = body.unit
            metric.scoring_text = body.scoring_text
            metric.remarks = body.remarks
            metric.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(metric)
            return _metric_to_dict(metric)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.delete("/metrics/{metric_id}", status_code=204)
def delete_kpi_metric(metric_id: int) -> None:
    from backend.app.models.kpi import KpiMetric
    try:
        repo = KpiRepository(_get_dsn())
        with repo._session_factory() as session:
            metric = session.get(KpiMetric, metric_id)
            if metric is None:
                raise HTTPException(status_code=404, detail=f"KPI metric {metric_id} not found")
            session.delete(metric)
            session.commit()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Values
# ---------------------------------------------------------------------------

@router.get("/values")
def get_kpi_values(
    owner_id: int = Query(..., ge=1),
    as_of_date: str = Query(...),
    include_trace: bool = Query(False),
) -> dict:
    from sqlalchemy import select
    from backend.app.models.kpi import KpiMetric, KpiMetricValue, KpiOwner
    try:
        target_date = date.fromisoformat(as_of_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid as_of_date: {as_of_date}") from exc
    try:
        repo = KpiRepository(_get_dsn())
        with repo._session_factory() as session:
            owner = session.get(KpiOwner, owner_id)
            if owner is None:
                raise HTTPException(status_code=404, detail=f"KPI owner {owner_id} not found")
            owner_name = owner.owner_name
            metrics = session.execute(
                select(KpiMetric)
                .where(KpiMetric.owner_id == owner_id)
                .where(KpiMetric.is_active.is_(True))
                .order_by(KpiMetric.metric_id.asc())
            ).scalars().all()
            metric_ids = [m.metric_id for m in metrics]
            values_rows = session.execute(
                select(KpiMetricValue)
                .where(KpiMetricValue.metric_id.in_(metric_ids) if metric_ids else False)
                .where(KpiMetricValue.as_of_date == target_date)
                .order_by(KpiMetricValue.metric_id.asc(), KpiMetricValue.updated_at.desc())
            ).scalars().all()
            latest_by_metric: dict[int, object] = {}
            for v in values_rows:
                latest_by_metric.setdefault(v.metric_id, v)

            def ds(val):
                return format(Decimal(str(val)), "f") if val is not None else None

            result_metrics = []
            for m in metrics:
                v = latest_by_metric.get(m.metric_id)
                row = _metric_to_dict(m)
                if v is not None:
                    row.update({
                        "value_id": v.value_id,
                        "as_of_date": v.as_of_date.isoformat(),
                        "actual_value": ds(v.actual_value),
                        "actual_text": v.actual_text,
                        "completion_ratio": ds(v.completion_ratio),
                        "progress_pct": ds(v.progress_pct),
                        "score_value": ds(v.score_value),
                        "source": v.source,
                    })
                result_metrics.append(row)

            return {
                "owner_id": owner.owner_id,
                "owner_name": owner.owner_name,
                "as_of_date": as_of_date,
                "metrics": result_metrics,
                "total": len(result_metrics),
            }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/values", status_code=201)
def create_kpi_value(body: KpiValueCreateRequest) -> dict:
    from sqlalchemy import select
    from backend.app.models.kpi import KpiMetric, KpiMetricValue
    try:
        target_date = date.fromisoformat(body.as_of_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid as_of_date: {body.as_of_date}") from exc
    try:
        repo = KpiRepository(_get_dsn())
        now = datetime.now(timezone.utc)
        with repo._session_factory() as session:
            metric = session.get(KpiMetric, body.metric_id)
            if metric is None:
                raise HTTPException(status_code=404, detail=f"KPI metric {body.metric_id} not found")
            value = session.execute(
                select(KpiMetricValue)
                .where(KpiMetricValue.metric_id == body.metric_id)
                .where(KpiMetricValue.as_of_date == target_date)
                .order_by(KpiMetricValue.updated_at.desc())
            ).scalars().first()
            if value is None:
                value = KpiMetricValue(
                    metric_id=body.metric_id,
                    as_of_date=target_date,
                    created_at=now,
                    updated_at=now,
                )
                session.add(value)
            _apply_value_payload(
                metric=metric,
                value=value,
                target_value=_parse_decimal(body.target_value),
                actual_value=_parse_decimal(body.actual_value),
                actual_text=body.actual_text,
                progress_pct=_parse_decimal(body.progress_pct),
                source=body.source,
            )
            session.commit()
            session.refresh(value)
            return _value_to_dict(value)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.put("/values/{value_id}")
def update_kpi_value(value_id: int, body: KpiValueUpdateRequest) -> dict:
    from backend.app.models.kpi import KpiMetric, KpiMetricValue
    try:
        repo = KpiRepository(_get_dsn())
        with repo._session_factory() as session:
            value = session.get(KpiMetricValue, value_id)
            if value is None:
                raise HTTPException(status_code=404, detail=f"KPI value {value_id} not found")
            metric = session.get(KpiMetric, value.metric_id)
            if metric is None:
                raise HTTPException(status_code=404, detail=f"KPI metric {value.metric_id} not found")
            _apply_value_payload(
                metric=metric,
                value=value,
                target_value=_parse_decimal(body.target_value),
                actual_value=_parse_decimal(body.actual_value),
                actual_text=body.actual_text,
                progress_pct=_parse_decimal(body.progress_pct),
                score_value=_parse_decimal(body.score_value),
                source=body.source,
            )
            session.commit()
            session.refresh(value)
            return _value_to_dict(value)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/values/batch")
def batch_update_kpi_values(body: KpiValuesBatchRequest) -> dict:
    from sqlalchemy import select
    from backend.app.models.kpi import KpiMetric, KpiMetricValue

    try:
        target_date = date.fromisoformat(body.as_of_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid as_of_date: {body.as_of_date}") from exc

    try:
        repo = KpiRepository(_get_dsn())
        success_count = 0
        failed_count = 0
        errors: list[str] = []
        now = datetime.now(timezone.utc)
        with repo._session_factory() as session:
            for item in body.items:
                metric = session.get(KpiMetric, item.metric_id)
                if metric is None:
                    failed_count += 1
                    errors.append(f"KPI metric {item.metric_id} not found")
                    continue
                value = session.execute(
                    select(KpiMetricValue)
                    .where(KpiMetricValue.metric_id == item.metric_id)
                    .where(KpiMetricValue.as_of_date == target_date)
                    .order_by(KpiMetricValue.updated_at.desc())
                ).scalars().first()
                if value is None:
                    value = KpiMetricValue(
                        metric_id=item.metric_id,
                        as_of_date=target_date,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(value)
                _apply_value_payload(
                    metric=metric,
                    value=value,
                    actual_value=_parse_decimal(item.actual_value),
                    progress_pct=_parse_decimal(item.progress_pct),
                    source="batch-import",
                )
                success_count += 1
            session.commit()
        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "errors": errors,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/fetch_and_recalc")
def fetch_and_recalc_kpi(
    body: KpiFetchAndRecalcRequest,
    owner_id: int = Query(..., ge=1),
    as_of_date: str = Query(...),
) -> dict:
    from sqlalchemy import select
    from backend.app.models.kpi import KpiMetric, KpiMetricValue, KpiOwner

    try:
        target_date = date.fromisoformat(as_of_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid as_of_date: {as_of_date}") from exc

    try:
        repo = KpiRepository(_get_dsn())
        with repo._session_factory() as session:
            owner = session.get(KpiOwner, owner_id)
            if owner is None:
                raise HTTPException(status_code=404, detail=f"KPI owner {owner_id} not found")
            owner_name = owner.owner_name

            metric_stmt = (
                select(KpiMetric)
                .where(KpiMetric.owner_id == owner_id)
                .where(KpiMetric.is_active.is_(True))
                .order_by(KpiMetric.metric_id.asc())
            )
            if body.metric_ids:
                metric_stmt = metric_stmt.where(KpiMetric.metric_id.in_(body.metric_ids))
            metrics = session.execute(metric_stmt).scalars().all()
            metric_ids = [metric.metric_id for metric in metrics]
            values = session.execute(
                select(KpiMetricValue)
                .where(KpiMetricValue.metric_id.in_(metric_ids) if metric_ids else False)
                .where(KpiMetricValue.as_of_date == target_date)
                .order_by(KpiMetricValue.metric_id.asc(), KpiMetricValue.updated_at.desc())
            ).scalars().all()
            latest_by_metric: dict[int, object] = {}
            for value in values:
                latest_by_metric.setdefault(value.metric_id, value)

            fetched_count = 0
            scored_count = 0
            failed_count = 0
            skipped_count = 0
            results: list[dict[str, object]] = []

            for metric in metrics:
                value = latest_by_metric.get(metric.metric_id)
                if value is None:
                    skipped_count += 1
                    results.append(
                        _result_item(
                            metric=metric,
                            value=None,
                            fetch_status="SKIPPED",
                            score_status="SKIPPED",
                            error_message="No KPI value captured for the target date.",
                        )
                    )
                    continue

                if str(metric.data_source_type).upper() != "MANUAL":
                    failed_count += 1
                    results.append(
                        _result_item(
                            metric=metric,
                            value=value,
                            fetch_status="FAILED",
                            score_status="SKIPPED",
                            error_message="Automatic KPI fetch is not implemented on this surface yet.",
                        )
                    )
                    continue

                _apply_value_payload(metric=metric, value=value)
                skipped_count += 1
                scored_count += 1
                results.append(
                    _result_item(
                        metric=metric,
                        value=value,
                        fetch_status="SKIPPED",
                        score_status="SCORED",
                    )
                )

            session.commit()
        return {
            "owner_id": owner_id,
            "owner_name": owner_name,
            "as_of_date": as_of_date,
            "total_metrics": len(metrics),
            "fetched_count": fetched_count,
            "scored_count": scored_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "results": results,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@router.get("/report", response_model=None)
def get_kpi_report(
    year: int = Query(..., ge=2000, le=2100),
    owner_id: int | None = Query(None, ge=1),
    as_of_date: str | None = Query(None),
    format: str | None = Query(None),
) -> object:
    from sqlalchemy import select
    from backend.app.models.kpi import KpiMetric, KpiMetricValue, KpiOwner
    try:
        repo = KpiRepository(_get_dsn())
        with repo._session_factory() as session:
            owner_stmt = select(KpiOwner).where(KpiOwner.year == year).where(KpiOwner.is_active.is_(True))
            if owner_id is not None:
                owner_stmt = owner_stmt.where(KpiOwner.owner_id == owner_id)
            owners = session.execute(owner_stmt).scalars().all()

            metric_stmt = (
                select(KpiMetric)
                .where(KpiMetric.year == year)
                .where(KpiMetric.is_active.is_(True))
            )
            if owner_id is not None:
                metric_stmt = metric_stmt.where(KpiMetric.owner_id == owner_id)
            metrics = session.execute(metric_stmt.order_by(KpiMetric.owner_id, KpiMetric.metric_id)).scalars().all()

            metric_ids = [m.metric_id for m in metrics]
            target_date = date.fromisoformat(as_of_date) if as_of_date else date(year, 12, 31)
            values_rows = session.execute(
                select(KpiMetricValue)
                .where(KpiMetricValue.metric_id.in_(metric_ids) if metric_ids else False)
                .where(KpiMetricValue.as_of_date <= target_date)
                .order_by(KpiMetricValue.metric_id.asc(), KpiMetricValue.as_of_date.desc(), KpiMetricValue.updated_at.desc())
            ).scalars().all()

            latest_by_metric: dict[int, object] = {}
            for v in values_rows:
                latest_by_metric.setdefault(v.metric_id, v)

            owner_map = {o.owner_id: o for o in owners}

            def ds(val):
                return f"{Decimal(str(val)):f}" if val is not None else "0"

            rows = []
            for m in metrics:
                owner = owner_map.get(m.owner_id)
                v = latest_by_metric.get(m.metric_id)
                rows.append({
                    "owner_name": owner.owner_name if owner else "",
                    "org_unit": owner.org_unit if owner else "",
                    "major_category": m.major_category,
                    "indicator_category": m.indicator_category,
                    "metric_name": m.metric_name,
                    "target_value": ds(m.target_value),
                    "target_text": m.target_text,
                    "unit": m.unit,
                    "score_weight": ds(m.score_weight),
                    "scoring_text": m.scoring_text,
                    "actual_value": ds(v.actual_value if v else None),
                    "completion_ratio": ds(v.completion_ratio if v else None),
                    "progress_pct": ds(v.progress_pct if v else None),
                    "score_value": ds(v.score_value if v else None),
                    "remarks": m.remarks,
                })

        payload = {
            "year": year,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "rows": rows,
            "total": len(rows),
        }
        if str(format or "").lower() == "csv":
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
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
