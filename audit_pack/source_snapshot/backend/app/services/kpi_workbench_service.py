from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from backend.app.models.kpi import KpiMetric, KpiMetricValue, KpiOwner
from backend.app.repositories.kpi_repo import KpiRepository


class KpiWorkbenchError(RuntimeError):
    """Base error for KPI workbench operations."""


class KpiNotFoundError(KpiWorkbenchError):
    """Raised when a KPI entity cannot be found."""


class KpiInvalidDateError(KpiWorkbenchError):
    """Raised when a KPI request date cannot be parsed."""


class KpiStorageError(KpiWorkbenchError):
    """Raised when storage access fails."""


def _parse_decimal(value: object | None) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _decimal_text(value: object | None, *, default: str | None = None) -> str | None:
    dec = _parse_decimal(value)
    if dec is None:
        return default
    return format(dec.quantize(Decimal("0.000001")), "f")


def _parse_as_of_date(as_of_date: str) -> date:
    try:
        return date.fromisoformat(as_of_date)
    except ValueError as exc:
        raise KpiInvalidDateError(f"Invalid as_of_date: {as_of_date}") from exc


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
    metric: KpiMetric,
    value: KpiMetricValue,
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


def _metric_to_dict(metric: KpiMetric) -> dict[str, object]:
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


def _value_to_dict(value: KpiMetricValue) -> dict[str, object]:
    def ds(raw_value: object | None) -> str | None:
        return format(Decimal(str(raw_value)), "f") if raw_value is not None else None

    return {
        "value_id": value.value_id,
        "metric_id": value.metric_id,
        "as_of_date": value.as_of_date.isoformat(),
        "actual_value": ds(value.actual_value),
        "actual_text": value.actual_text,
        "completion_ratio": ds(value.completion_ratio),
        "progress_pct": ds(value.progress_pct),
        "score_value": ds(value.score_value),
        "source": value.source,
        "created_at": value.created_at.isoformat(),
        "updated_at": value.updated_at.isoformat(),
    }


def _result_item(
    *,
    metric: KpiMetric,
    value: KpiMetricValue | None,
    fetch_status: str,
    score_status: str,
    error_message: str | None = None,
) -> dict[str, object]:
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


def _repo(dsn: str) -> KpiRepository:
    return KpiRepository(dsn)


def list_metrics(
    *,
    dsn: str,
    owner_id: int | None = None,
    year: int | None = None,
    is_active: bool | None = None,
) -> dict[str, object]:
    try:
        repo = _repo(dsn)
        with repo.session() as session:
            stmt = select(KpiMetric)
            if owner_id is not None:
                stmt = stmt.where(KpiMetric.owner_id == owner_id)
            if year is not None:
                stmt = stmt.where(KpiMetric.year == year)
            if is_active is not None:
                stmt = stmt.where(KpiMetric.is_active.is_(is_active))
            stmt = stmt.order_by(KpiMetric.year.desc(), KpiMetric.metric_id.asc())
            rows = session.execute(stmt).scalars().all()
        metrics = [_metric_to_dict(row) for row in rows]
        return {"metrics": metrics, "total": len(metrics)}
    except Exception as exc:
        raise KpiStorageError(str(exc)) from exc


def get_metric(*, dsn: str, metric_id: int) -> dict[str, object]:
    try:
        repo = _repo(dsn)
        with repo.session() as session:
            metric = session.get(KpiMetric, metric_id)
        if metric is None:
            raise KpiNotFoundError(f"KPI metric {metric_id} not found")
        return _metric_to_dict(metric)
    except KpiWorkbenchError:
        raise
    except Exception as exc:
        raise KpiStorageError(str(exc)) from exc


def create_metric(*, dsn: str, data: dict[str, object]) -> dict[str, object]:
    try:
        repo = _repo(dsn)
        now = datetime.now(timezone.utc)
        metric = KpiMetric(
            metric_code=str(data["metric_code"]),
            metric_name=str(data["metric_name"]),
            major_category=str(data["major_category"]),
            owner_id=int(data["owner_id"]),
            year=int(data["year"]),
            score_weight=Decimal(str(data["score_weight"])),
            data_source_type=str(data["data_source_type"]),
            scoring_rule_type=str(data["scoring_rule_type"]),
            indicator_category=data.get("indicator_category"),
            target_value=Decimal(str(data["target_value"])) if data.get("target_value") else None,
            target_text=data.get("target_text"),
            unit=data.get("unit"),
            scoring_text=data.get("scoring_text"),
            remarks=data.get("remarks"),
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        with repo.session() as session:
            session.add(metric)
            session.commit()
            session.refresh(metric)
            return _metric_to_dict(metric)
    except Exception as exc:
        raise KpiStorageError(str(exc)) from exc


def update_metric(*, dsn: str, metric_id: int, data: dict[str, object]) -> dict[str, object]:
    try:
        repo = _repo(dsn)
        with repo.session() as session:
            metric = session.get(KpiMetric, metric_id)
            if metric is None:
                raise KpiNotFoundError(f"KPI metric {metric_id} not found")
            metric.metric_code = str(data["metric_code"])
            metric.metric_name = str(data["metric_name"])
            metric.major_category = str(data["major_category"])
            metric.owner_id = int(data["owner_id"])
            metric.year = int(data["year"])
            metric.score_weight = Decimal(str(data["score_weight"]))
            metric.data_source_type = str(data["data_source_type"])
            metric.scoring_rule_type = str(data["scoring_rule_type"])
            metric.indicator_category = data.get("indicator_category")
            metric.target_value = Decimal(str(data["target_value"])) if data.get("target_value") else None
            metric.target_text = data.get("target_text")
            metric.unit = data.get("unit")
            metric.scoring_text = data.get("scoring_text")
            metric.remarks = data.get("remarks")
            metric.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(metric)
            return _metric_to_dict(metric)
    except KpiWorkbenchError:
        raise
    except Exception as exc:
        raise KpiStorageError(str(exc)) from exc


def delete_metric(*, dsn: str, metric_id: int) -> None:
    try:
        repo = _repo(dsn)
        with repo.session() as session:
            metric = session.get(KpiMetric, metric_id)
            if metric is None:
                raise KpiNotFoundError(f"KPI metric {metric_id} not found")
            session.delete(metric)
            session.commit()
    except KpiWorkbenchError:
        raise
    except Exception as exc:
        raise KpiStorageError(str(exc)) from exc


def get_values(*, dsn: str, owner_id: int, as_of_date: str, include_trace: bool) -> dict[str, object]:
    del include_trace
    target_date = _parse_as_of_date(as_of_date)
    try:
        repo = _repo(dsn)
        with repo.session() as session:
            owner = session.get(KpiOwner, owner_id)
            if owner is None:
                raise KpiNotFoundError(f"KPI owner {owner_id} not found")
            metrics = session.execute(
                select(KpiMetric)
                .where(KpiMetric.owner_id == owner_id)
                .where(KpiMetric.is_active.is_(True))
                .order_by(KpiMetric.metric_id.asc())
            ).scalars().all()
            metric_ids = [metric.metric_id for metric in metrics]
            values_rows = session.execute(
                select(KpiMetricValue)
                .where(KpiMetricValue.metric_id.in_(metric_ids) if metric_ids else False)
                .where(KpiMetricValue.as_of_date == target_date)
                .order_by(KpiMetricValue.metric_id.asc(), KpiMetricValue.updated_at.desc())
            ).scalars().all()

        latest_by_metric: dict[int, KpiMetricValue] = {}
        for value in values_rows:
            latest_by_metric.setdefault(value.metric_id, value)

        def ds(raw_value: object | None) -> str | None:
            return format(Decimal(str(raw_value)), "f") if raw_value is not None else None

        result_metrics: list[dict[str, object]] = []
        for metric in metrics:
            value = latest_by_metric.get(metric.metric_id)
            row = _metric_to_dict(metric)
            if value is not None:
                row.update(
                    {
                        "value_id": value.value_id,
                        "as_of_date": value.as_of_date.isoformat(),
                        "actual_value": ds(value.actual_value),
                        "actual_text": value.actual_text,
                        "completion_ratio": ds(value.completion_ratio),
                        "progress_pct": ds(value.progress_pct),
                        "score_value": ds(value.score_value),
                        "source": value.source,
                    }
                )
            result_metrics.append(row)

        return {
            "owner_id": owner.owner_id,
            "owner_name": owner.owner_name,
            "as_of_date": as_of_date,
            "metrics": result_metrics,
            "total": len(result_metrics),
        }
    except KpiWorkbenchError:
        raise
    except Exception as exc:
        raise KpiStorageError(str(exc)) from exc


def create_value(*, dsn: str, data: dict[str, object]) -> dict[str, object]:
    target_date = _parse_as_of_date(str(data["as_of_date"]))
    try:
        repo = _repo(dsn)
        now = datetime.now(timezone.utc)
        with repo.session() as session:
            metric = session.get(KpiMetric, int(data["metric_id"]))
            if metric is None:
                raise KpiNotFoundError(f"KPI metric {data['metric_id']} not found")
            value = session.execute(
                select(KpiMetricValue)
                .where(KpiMetricValue.metric_id == int(data["metric_id"]))
                .where(KpiMetricValue.as_of_date == target_date)
                .order_by(KpiMetricValue.updated_at.desc())
            ).scalars().first()
            if value is None:
                value = KpiMetricValue(
                    metric_id=int(data["metric_id"]),
                    as_of_date=target_date,
                    created_at=now,
                    updated_at=now,
                )
                session.add(value)
            _apply_value_payload(
                metric=metric,
                value=value,
                target_value=_parse_decimal(data.get("target_value")),
                actual_value=_parse_decimal(data.get("actual_value")),
                actual_text=data.get("actual_text"),
                progress_pct=_parse_decimal(data.get("progress_pct")),
                source=data.get("source"),
            )
            session.commit()
            session.refresh(value)
            return _value_to_dict(value)
    except KpiWorkbenchError:
        raise
    except Exception as exc:
        raise KpiStorageError(str(exc)) from exc


def update_value(*, dsn: str, value_id: int, data: dict[str, object]) -> dict[str, object]:
    try:
        repo = _repo(dsn)
        with repo.session() as session:
            value = session.get(KpiMetricValue, value_id)
            if value is None:
                raise KpiNotFoundError(f"KPI value {value_id} not found")
            metric = session.get(KpiMetric, value.metric_id)
            if metric is None:
                raise KpiNotFoundError(f"KPI metric {value.metric_id} not found")
            _apply_value_payload(
                metric=metric,
                value=value,
                target_value=_parse_decimal(data.get("target_value")),
                actual_value=_parse_decimal(data.get("actual_value")),
                actual_text=data.get("actual_text"),
                progress_pct=_parse_decimal(data.get("progress_pct")),
                score_value=_parse_decimal(data.get("score_value")),
                source=data.get("source"),
            )
            session.commit()
            session.refresh(value)
            return _value_to_dict(value)
    except KpiWorkbenchError:
        raise
    except Exception as exc:
        raise KpiStorageError(str(exc)) from exc


def batch_update_values(*, dsn: str, as_of_date: str, items: list[dict[str, object]]) -> dict[str, object]:
    target_date = _parse_as_of_date(as_of_date)
    try:
        repo = _repo(dsn)
        success_count = 0
        failed_count = 0
        errors: list[str] = []
        now = datetime.now(timezone.utc)
        with repo.session() as session:
            for item in items:
                metric = session.get(KpiMetric, int(item["metric_id"]))
                if metric is None:
                    failed_count += 1
                    errors.append(f"KPI metric {item['metric_id']} not found")
                    continue
                value = session.execute(
                    select(KpiMetricValue)
                    .where(KpiMetricValue.metric_id == int(item["metric_id"]))
                    .where(KpiMetricValue.as_of_date == target_date)
                    .order_by(KpiMetricValue.updated_at.desc())
                ).scalars().first()
                if value is None:
                    value = KpiMetricValue(
                        metric_id=int(item["metric_id"]),
                        as_of_date=target_date,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(value)
                _apply_value_payload(
                    metric=metric,
                    value=value,
                    actual_value=_parse_decimal(item.get("actual_value")),
                    progress_pct=_parse_decimal(item.get("progress_pct")),
                    source="batch-import",
                )
                success_count += 1
            session.commit()
        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "errors": errors,
        }
    except KpiWorkbenchError:
        raise
    except Exception as exc:
        raise KpiStorageError(str(exc)) from exc


def fetch_and_recalc(
    *,
    dsn: str,
    owner_id: int,
    as_of_date: str,
    metric_ids: list[int] | None,
) -> dict[str, object]:
    target_date = _parse_as_of_date(as_of_date)
    try:
        repo = _repo(dsn)
        with repo.session() as session:
            owner = session.get(KpiOwner, owner_id)
            if owner is None:
                raise KpiNotFoundError(f"KPI owner {owner_id} not found")
            owner_name = owner.owner_name

            metric_stmt = (
                select(KpiMetric)
                .where(KpiMetric.owner_id == owner_id)
                .where(KpiMetric.is_active.is_(True))
                .order_by(KpiMetric.metric_id.asc())
            )
            if metric_ids:
                metric_stmt = metric_stmt.where(KpiMetric.metric_id.in_(metric_ids))
            metrics = session.execute(metric_stmt).scalars().all()
            metric_id_list = [metric.metric_id for metric in metrics]
            values = session.execute(
                select(KpiMetricValue)
                .where(KpiMetricValue.metric_id.in_(metric_id_list) if metric_id_list else False)
                .where(KpiMetricValue.as_of_date == target_date)
                .order_by(KpiMetricValue.metric_id.asc(), KpiMetricValue.updated_at.desc())
            ).scalars().all()
            latest_by_metric: dict[int, KpiMetricValue] = {}
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
    except KpiWorkbenchError:
        raise
    except Exception as exc:
        raise KpiStorageError(str(exc)) from exc


def build_report(
    *,
    dsn: str,
    year: int,
    owner_id: int | None = None,
    as_of_date: str | None = None,
) -> dict[str, object]:
    target_date = _parse_as_of_date(as_of_date) if as_of_date else date(year, 12, 31)
    try:
        repo = _repo(dsn)
        with repo.session() as session:
            owner_stmt = select(KpiOwner).where(KpiOwner.year == year).where(KpiOwner.is_active.is_(True))
            if owner_id is not None:
                owner_stmt = owner_stmt.where(KpiOwner.owner_id == owner_id)
            owners = session.execute(owner_stmt).scalars().all()

            metric_stmt = select(KpiMetric).where(KpiMetric.year == year).where(KpiMetric.is_active.is_(True))
            if owner_id is not None:
                metric_stmt = metric_stmt.where(KpiMetric.owner_id == owner_id)
            metrics = session.execute(metric_stmt.order_by(KpiMetric.owner_id, KpiMetric.metric_id)).scalars().all()

            metric_ids = [metric.metric_id for metric in metrics]
            values_rows = session.execute(
                select(KpiMetricValue)
                .where(KpiMetricValue.metric_id.in_(metric_ids) if metric_ids else False)
                .where(KpiMetricValue.as_of_date <= target_date)
                .order_by(KpiMetricValue.metric_id.asc(), KpiMetricValue.as_of_date.desc(), KpiMetricValue.updated_at.desc())
            ).scalars().all()

        latest_by_metric: dict[int, KpiMetricValue] = {}
        for value in values_rows:
            latest_by_metric.setdefault(value.metric_id, value)

        owner_map = {owner.owner_id: owner for owner in owners}

        def ds(raw_value: object | None) -> str:
            return f"{Decimal(str(raw_value)):f}" if raw_value is not None else "0"

        rows: list[dict[str, object]] = []
        for metric in metrics:
            owner = owner_map.get(metric.owner_id)
            value = latest_by_metric.get(metric.metric_id)
            rows.append(
                {
                    "owner_name": owner.owner_name if owner else "",
                    "org_unit": owner.org_unit if owner else "",
                    "major_category": metric.major_category,
                    "indicator_category": metric.indicator_category,
                    "metric_name": metric.metric_name,
                    "target_value": ds(metric.target_value),
                    "target_text": metric.target_text,
                    "unit": metric.unit,
                    "score_weight": ds(metric.score_weight),
                    "scoring_text": metric.scoring_text,
                    "actual_value": ds(value.actual_value if value else None),
                    "completion_ratio": ds(value.completion_ratio if value else None),
                    "progress_pct": ds(value.progress_pct if value else None),
                    "score_value": ds(value.score_value if value else None),
                    "remarks": metric.remarks,
                }
            )

        return {
            "year": year,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "rows": rows,
            "total": len(rows),
        }
    except KpiWorkbenchError:
        raise
    except Exception as exc:
        raise KpiStorageError(str(exc)) from exc
