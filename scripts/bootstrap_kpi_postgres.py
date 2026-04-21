from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from backend.app.models.kpi import KpiMetric, KpiMetricValue, KpiOwner
from backend.app.repositories.kpi_repo import KpiRepository


def _read_seed(seed_path: Path) -> dict[str, object]:
    return json.loads(seed_path.read_text(encoding="utf-8"))


def _decimal(value: object | None) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def bootstrap_kpi_seed(
    *,
    dsn: str,
    seed_path: Path,
    if_empty: bool = False,
) -> dict[str, int | str]:
    repo = KpiRepository(dsn)
    payload = _read_seed(seed_path)
    owners_payload = list(payload.get("owners") or [])

    inserted_owners = 0
    inserted_metrics = 0
    inserted_values = 0
    updated_owners = 0
    updated_metrics = 0
    updated_values = 0

    now = datetime.now(timezone.utc)
    with repo._session_factory() as session:
        existing_owner_count = session.query(KpiOwner).count()
        if if_empty and existing_owner_count > 0:
            return {
                "status": "skipped-nonempty",
                "inserted_owners": 0,
                "inserted_metrics": 0,
                "inserted_values": 0,
                "updated_owners": 0,
                "updated_metrics": 0,
                "updated_values": 0,
            }

        for owner_data in owners_payload:
            owner_name = str(owner_data["owner_name"]).strip()
            year = int(owner_data["year"])
            owner = (
                session.query(KpiOwner)
                .filter(KpiOwner.owner_name == owner_name, KpiOwner.year == year)
                .one_or_none()
            )
            if owner is None:
                owner = KpiOwner(
                    owner_name=owner_name,
                    org_unit=str(owner_data["org_unit"]).strip(),
                    person_name=(str(owner_data.get("person_name") or "").strip() or None),
                    year=year,
                    scope_type=str(owner_data.get("scope_type") or "department").strip(),
                    scope_key_json=json.dumps(owner_data.get("scope_key")) if owner_data.get("scope_key") is not None else None,
                    is_active=bool(owner_data.get("is_active", True)),
                    created_at=now,
                    updated_at=now,
                )
                session.add(owner)
                session.flush()
                inserted_owners += 1
            else:
                owner.org_unit = str(owner_data["org_unit"]).strip()
                owner.person_name = (str(owner_data.get("person_name") or "").strip() or None)
                owner.scope_type = str(owner_data.get("scope_type") or owner.scope_type).strip()
                owner.scope_key_json = (
                    json.dumps(owner_data.get("scope_key")) if owner_data.get("scope_key") is not None else None
                )
                owner.is_active = bool(owner_data.get("is_active", owner.is_active))
                owner.updated_at = now
                updated_owners += 1

            for metric_data in list(owner_data.get("metrics") or []):
                metric_code = str(metric_data["metric_code"]).strip()
                metric = (
                    session.query(KpiMetric)
                    .filter(
                        KpiMetric.owner_id == owner.owner_id,
                        KpiMetric.year == year,
                        KpiMetric.metric_code == metric_code,
                    )
                    .one_or_none()
                )
                if metric is None:
                    metric = KpiMetric(
                        metric_code=metric_code,
                        owner_id=owner.owner_id,
                        year=year,
                        major_category=str(metric_data["major_category"]).strip(),
                        indicator_category=(str(metric_data.get("indicator_category") or "").strip() or None),
                        metric_name=str(metric_data["metric_name"]).strip(),
                        target_value=_decimal(metric_data.get("target_value")),
                        target_text=(str(metric_data.get("target_text") or "").strip() or None),
                        score_weight=_decimal(metric_data["score_weight"]) or Decimal("0"),
                        unit=(str(metric_data.get("unit") or "").strip() or None),
                        scoring_text=(str(metric_data.get("scoring_text") or "").strip() or None),
                        scoring_rule_type=str(metric_data.get("scoring_rule_type") or "MANUAL").strip(),
                        data_source_type=str(metric_data.get("data_source_type") or "MANUAL").strip(),
                        progress_plan=(str(metric_data.get("progress_plan") or "").strip() or None),
                        remarks=(str(metric_data.get("remarks") or "").strip() or None),
                        is_active=bool(metric_data.get("is_active", True)),
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(metric)
                    session.flush()
                    inserted_metrics += 1
                else:
                    metric.major_category = str(metric_data["major_category"]).strip()
                    metric.indicator_category = (str(metric_data.get("indicator_category") or "").strip() or None)
                    metric.metric_name = str(metric_data["metric_name"]).strip()
                    metric.target_value = _decimal(metric_data.get("target_value"))
                    metric.target_text = (str(metric_data.get("target_text") or "").strip() or None)
                    metric.score_weight = _decimal(metric_data["score_weight"]) or Decimal("0")
                    metric.unit = (str(metric_data.get("unit") or "").strip() or None)
                    metric.scoring_text = (str(metric_data.get("scoring_text") or "").strip() or None)
                    metric.scoring_rule_type = str(metric_data.get("scoring_rule_type") or metric.scoring_rule_type).strip()
                    metric.data_source_type = str(metric_data.get("data_source_type") or metric.data_source_type).strip()
                    metric.progress_plan = (str(metric_data.get("progress_plan") or "").strip() or None)
                    metric.remarks = (str(metric_data.get("remarks") or "").strip() or None)
                    metric.is_active = bool(metric_data.get("is_active", metric.is_active))
                    metric.updated_at = now
                    updated_metrics += 1

                for value_data in list(metric_data.get("values") or []):
                    as_of_date = datetime.fromisoformat(str(value_data["as_of_date"])).date()
                    value = (
                        session.query(KpiMetricValue)
                        .filter(
                            KpiMetricValue.metric_id == metric.metric_id,
                            KpiMetricValue.as_of_date == as_of_date,
                        )
                        .one_or_none()
                    )
                    if value is None:
                        value = KpiMetricValue(
                            metric_id=metric.metric_id,
                            as_of_date=as_of_date,
                            created_at=now,
                            updated_at=now,
                        )
                        session.add(value)
                        inserted_values += 1
                    else:
                        updated_values += 1
                    value.actual_value = _decimal(value_data.get("actual_value"))
                    value.actual_text = (str(value_data.get("actual_text") or "").strip() or None)
                    value.completion_ratio = _decimal(value_data.get("completion_ratio"))
                    value.progress_pct = _decimal(value_data.get("progress_pct"))
                    value.score_value = _decimal(value_data.get("score_value"))
                    value.source = (str(value_data.get("source") or "").strip() or None)
                    value.updated_at = now
        session.commit()

    return {
        "status": "ok",
        "inserted_owners": inserted_owners,
        "inserted_metrics": inserted_metrics,
        "inserted_values": inserted_values,
        "updated_owners": updated_owners,
        "updated_metrics": updated_metrics,
        "updated_values": updated_values,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--seed-file", required=True)
    parser.add_argument("--if-empty", action="store_true")
    args = parser.parse_args()

    result = bootstrap_kpi_seed(
        dsn=args.dsn,
        seed_path=Path(args.seed_file).resolve(),
        if_empty=args.if_empty,
    )
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
