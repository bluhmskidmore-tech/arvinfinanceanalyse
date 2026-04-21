from __future__ import annotations

import sys
from unittest.mock import Mock
from datetime import date, datetime, timezone

from sqlalchemy.orm import sessionmaker

from tests.helpers import load_module


def test_kpi_repository_lists_active_owners_and_period_summary(tmp_path):
    repo_module = load_module(
        "backend.app.repositories.kpi_repo",
        "backend/app/repositories/kpi_repo.py",
    )
    model_module = sys.modules["backend.app.models.kpi"]

    dsn = f"sqlite:///{tmp_path / 'kpi.db'}"
    repo = repo_module.KpiRepository(dsn)
    session_factory = sessionmaker(repo.engine, future=True)
    now = datetime.now(timezone.utc)
    with session_factory() as session:
        owner = model_module.KpiOwner(
            owner_name="固定收益部",
            org_unit="金融市场部",
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
        goal_metric = model_module.KpiMetric(
            metric_code="GOAL_FI",
            owner_id=owner.owner_id,
            year=2026,
            major_category="经营目标",
            indicator_category="目标完成",
            metric_name="目标完成率",
            target_value=100,
            target_text=None,
            score_weight=60,
            unit="%",
            scoring_text=None,
            scoring_rule_type="LINEAR_RATIO",
            data_source_type="MANUAL",
            progress_plan=None,
            remarks=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        risk_metric = model_module.KpiMetric(
            metric_code="RISK_BUDGET",
            owner_id=owner.owner_id,
            year=2026,
            major_category="风险预算",
            indicator_category="预算使用",
            metric_name="风险预算使用率",
            target_value=100,
            target_text=None,
            score_weight=40,
            unit="%",
            scoring_text=None,
            scoring_rule_type="LINEAR_RATIO",
            data_source_type="MANUAL",
            progress_plan=None,
            remarks=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add_all([goal_metric, risk_metric])
        session.flush()
        session.add_all(
            [
                model_module.KpiMetricValue(
                    metric_id=goal_metric.metric_id,
                    as_of_date=date(2026, 3, 31),
                    actual_value=95,
                    actual_text=None,
                    completion_ratio=95,
                    progress_pct=95,
                    score_value=57,
                    source="manual",
                    created_at=now,
                    updated_at=now,
                ),
                model_module.KpiMetricValue(
                    metric_id=risk_metric.metric_id,
                    as_of_date=date(2026, 3, 31),
                    actual_value=88,
                    actual_text=None,
                    completion_ratio=88,
                    progress_pct=88,
                    score_value=35.2,
                    source="manual",
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.commit()

    owners = repo.list_owners(year=2026, is_active=True)
    assert len(owners) == 1
    assert owners[0]["owner_name"] == "固定收益部"

    summary = repo.fetch_period_summary(owner_id=owners[0]["owner_id"], year=2026, period_type="YEAR")
    assert summary["owner_name"] == "固定收益部"
    assert summary["total"] == 2
    assert summary["total_weight"] == "100.000000"
    assert summary["total_score"] == "92.200000"
    assert {row["metric_code"] for row in summary["metrics"]} == {"GOAL_FI", "RISK_BUDGET"}


def test_kpi_repository_normalizes_postgres_dsn_to_psycopg(monkeypatch):
    repo_module = load_module(
        "backend.app.repositories.kpi_repo",
        "backend/app/repositories/kpi_repo.py",
    )

    captured = {}

    class DummyEngine:
        dialect = type("Dialect", (), {"name": "postgresql"})()

    def fake_create_engine(dsn, future=True):
        captured["dsn"] = dsn
        return DummyEngine()

    monkeypatch.setattr(repo_module, "create_engine", fake_create_engine)
    monkeypatch.setattr(repo_module, "sessionmaker", lambda *args, **kwargs: Mock())

    repo_module.KpiRepository("postgresql://moss:moss@127.0.0.1:55432/moss")

    assert captured["dsn"] == "postgresql+psycopg://moss:moss@127.0.0.1:55432/moss"
