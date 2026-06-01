from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timezone

from sqlalchemy.orm import sessionmaker

from tests.helpers import load_module


def _load_kpi_workbench_service_module():
    return load_module(
        f"tests._kpi_workbench_service.kpi_workbench_service_{uuid.uuid4().hex}",
        "backend/app/services/kpi_workbench_service.py",
    )


def _seed_kpi_sqlite(tmp_path):
    repo_module = load_module(
        f"tests._kpi_repo.seed_{uuid.uuid4().hex}",
        "backend/app/repositories/kpi_repo.py",
    )
    model_module = sys.modules["backend.app.models.kpi"]

    dsn = f"sqlite:///{tmp_path / 'kpi-workbench.db'}"
    repo = repo_module.KpiRepository(dsn)
    session_factory = sessionmaker(repo.engine, future=True)
    now = datetime.now(timezone.utc)

    with session_factory() as session:
        owner = model_module.KpiOwner(
            owner_name="Fixed Income",
            org_unit="Trading",
            person_name=None,
            year=2026,
            scope_type="department",
            scope_key_json='{"scope":"fi"}',
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add(owner)
        session.flush()

        metric = model_module.KpiMetric(
            metric_code="GOAL_FI",
            owner_id=owner.owner_id,
            year=2026,
            major_category="Business Goal",
            indicator_category="Completion",
            metric_name="Goal Completion",
            target_value=100,
            target_text=None,
            score_weight=10,
            unit="%",
            scoring_text=None,
            scoring_rule_type="MANUAL",
            data_source_type="MANUAL",
            progress_plan=None,
            remarks=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add(metric)
        session.commit()
        owner_id = owner.owner_id
        metric_id = metric.metric_id

    return dsn, owner_id, metric_id, session_factory, model_module


def test_create_value_prefers_explicit_progress_pct_for_completion_and_score(tmp_path):
    module = _load_kpi_workbench_service_module()
    dsn, _owner_id, metric_id, _session_factory, _model_module = _seed_kpi_sqlite(tmp_path)

    payload = module.create_value(
        dsn=dsn,
        data={
            "metric_id": metric_id,
            "as_of_date": "2026-03-31",
            "actual_value": "60",
            "progress_pct": "50",
            "source": "manual",
        },
    )

    assert payload["actual_value"] == "60.000000"
    assert payload["progress_pct"] == "50.000000"
    assert payload["completion_ratio"] == "50.000000"
    assert payload["score_value"] == "5.000000"


def test_update_value_recomputes_score_and_updates_metric_target(tmp_path):
    module = _load_kpi_workbench_service_module()
    dsn, _owner_id, metric_id, session_factory, model_module = _seed_kpi_sqlite(tmp_path)
    now = datetime.now(timezone.utc)

    with session_factory() as session:
        value = model_module.KpiMetricValue(
            metric_id=metric_id,
            as_of_date=date(2026, 3, 31),
            actual_value=40,
            actual_text=None,
            completion_ratio=40,
            progress_pct=40,
            score_value=4,
            source="manual",
            created_at=now,
            updated_at=now,
        )
        session.add(value)
        session.commit()
        value_id = value.value_id

    payload = module.update_value(
        dsn=dsn,
        value_id=value_id,
        data={
            "target_value": "120",
            "actual_value": "60",
            "progress_pct": "50",
            "actual_text": "manual refresh",
        },
    )

    assert payload["completion_ratio"] == "50.000000"
    assert payload["score_value"] == "5.000000"

    with session_factory() as session:
        metric = session.get(model_module.KpiMetric, metric_id)
        assert metric.target_value == 120


def test_batch_update_values_preserves_response_shape(tmp_path):
    module = _load_kpi_workbench_service_module()
    dsn, owner_id, metric_id, _session_factory, _model_module = _seed_kpi_sqlite(tmp_path)

    payload = module.batch_update_values(
        dsn=dsn,
        as_of_date="2026-03-31",
        items=[
            {
                "metric_id": metric_id,
                "actual_value": "55",
                "progress_pct": "55",
            }
        ],
    )

    assert payload == {"success_count": 1, "failed_count": 0, "errors": []}

    values = module.get_values(dsn=dsn, owner_id=owner_id, as_of_date="2026-03-31", include_trace=False)
    metric = values["metrics"][0]
    assert metric["score_value"] == "5.500000"


def test_fetch_and_recalc_scores_manual_metrics(tmp_path):
    module = _load_kpi_workbench_service_module()
    dsn, owner_id, metric_id, session_factory, model_module = _seed_kpi_sqlite(tmp_path)
    now = datetime.now(timezone.utc)

    with session_factory() as session:
        session.add(
            model_module.KpiMetricValue(
                metric_id=metric_id,
                as_of_date=date(2026, 3, 31),
                actual_value=80,
                actual_text=None,
                completion_ratio=None,
                progress_pct=80,
                score_value=None,
                source="manual",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()

    payload = module.fetch_and_recalc(
        dsn=dsn,
        owner_id=owner_id,
        as_of_date="2026-03-31",
        metric_ids=[metric_id],
    )

    assert payload["total_metrics"] == 1
    assert payload["fetched_count"] == 0
    assert payload["scored_count"] == 1
    assert payload["skipped_count"] == 1
    assert payload["failed_count"] == 0
    assert payload["results"][0]["fetch_status"] == "SKIPPED"
    assert payload["results"][0]["score_status"] == "SCORED"
    assert payload["results"][0]["score_value"] == "8.000000"
