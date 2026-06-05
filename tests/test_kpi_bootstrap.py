from __future__ import annotations

import json
import sys

from sqlalchemy.orm import sessionmaker

from tests.helpers import load_module


def test_bootstrap_kpi_seed_loads_json_into_empty_sqlite(tmp_path):
    script_module = load_module(
        "scripts.bootstrap_kpi_postgres",
        "scripts/bootstrap_kpi_postgres.py",
    )
    load_module(
        "backend.app.repositories.kpi_repo",
        "backend/app/repositories/kpi_repo.py",
    )
    model_module = sys.modules["backend.app.models.kpi"]

    seed_path = tmp_path / "kpi_seed.json"
    seed_path.write_text(
        json.dumps(
            {
                "owners": [
                    {
                        "owner_name": "Fixed Income",
                        "org_unit": "Trading",
                        "person_name": None,
                        "year": 2026,
                        "scope_type": "department",
                        "scope_key": {"scope": "fi"},
                        "is_active": True,
                        "metrics": [
                            {
                                "metric_code": "GOAL_FI",
                                "major_category": "Business Goal",
                                "indicator_category": "Completion",
                                "metric_name": "Goal Completion",
                                "target_value": "100",
                                "target_text": None,
                                "score_weight": "60",
                                "unit": "%",
                                "scoring_text": None,
                                "scoring_rule_type": "MANUAL",
                                "data_source_type": "MANUAL",
                                "progress_plan": None,
                                "remarks": None,
                                "is_active": True,
                                "values": [
                                    {
                                        "as_of_date": "2026-03-31",
                                        "actual_value": "95",
                                        "actual_text": None,
                                        "completion_ratio": "95",
                                        "progress_pct": "95",
                                        "score_value": "57",
                                        "source": "bootstrap",
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    dsn = f"sqlite:///{tmp_path / 'kpi.db'}"
    result = script_module.bootstrap_kpi_seed(dsn=dsn, seed_path=seed_path, if_empty=True)

    assert result["status"] == "ok"
    assert result["inserted_owners"] == 1
    assert result["inserted_metrics"] == 1
    assert result["inserted_values"] == 1

    repo = script_module.KpiRepository(dsn)
    session_factory = sessionmaker(repo.engine, future=True)
    with session_factory() as session:
        assert session.query(model_module.KpiOwner).count() == 1
        assert session.query(model_module.KpiMetric).count() == 1
        assert session.query(model_module.KpiMetricValue).count() == 1


def test_dev_postgres_cluster_finds_kpi_bootstrap_file(tmp_path):
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )

    repo_root = tmp_path / "repo"
    seed_path = repo_root / "config" / "kpi_bootstrap.json"
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text("{}", encoding="utf-8")

    config = module.build_cluster_config(repo_root)

    assert module._find_kpi_bootstrap_file(config) == seed_path.resolve()
