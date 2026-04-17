from __future__ import annotations

import uuid

from tests.helpers import load_module


def _load_kpi_service_module():
    return load_module(
        f"tests._kpi_service.kpi_service_{uuid.uuid4().hex}",
        "backend/app/services/kpi_service.py",
    )


def test_resolve_executive_kpi_metrics_returns_empty_when_repository_bootstrap_fails(monkeypatch):
    module = _load_kpi_service_module()

    def _raise_on_init(*_args, **_kwargs):
        raise ModuleNotFoundError("psycopg2")

    monkeypatch.setattr(module, "KpiRepository", _raise_on_init)

    assert module.resolve_executive_kpi_metrics(
        dsn="postgresql://example.invalid/moss",
        report_date="2026-03-31",
    ) == []


def test_resolve_executive_kpi_metrics_aggregates_active_owners_within_target_year(monkeypatch):
    module = _load_kpi_service_module()

    class AggregateRepo:
        def __init__(self, *_args, **_kwargs):
            pass

        def list_owners(self, *, year=None, is_active=None):
            assert is_active is True
            return [
                {"owner_id": 1, "owner_name": "固定收益部", "year": 2026},
                {"owner_id": 2, "owner_name": "金融市场部", "year": 2026},
            ]

        def fetch_period_summary(self, *, owner_id, year, period_type):
            assert year == 2026
            assert period_type == "YEAR"
            payloads = {
                1: {
                    "total_weight": "100",
                    "total_score": "80",
                    "metrics": [
                        {
                            "metric_code": "RISK_A",
                            "metric_name": "风险预算A",
                            "major_category": "风险预算",
                            "indicator_category": "预算使用",
                            "score_weight": "40",
                            "period_progress_pct": "90",
                            "period_completion_ratio": None,
                        }
                    ],
                },
                2: {
                    "total_weight": "50",
                    "total_score": "45",
                    "metrics": [
                        {
                            "metric_code": "RISK_B",
                            "metric_name": "风险预算B",
                            "major_category": "风险预算",
                            "indicator_category": "预算使用",
                            "score_weight": "20",
                            "period_progress_pct": "60",
                            "period_completion_ratio": None,
                        }
                    ],
                },
            }
            return payloads[owner_id]

    monkeypatch.setattr(module, "KpiRepository", AggregateRepo)

    metrics = module.resolve_executive_kpi_metrics(
        dsn="sqlite:///tmp/kpi.db",
        report_date="2026-03-31",
    )

    by_id = {item["id"]: item for item in metrics}
    assert by_id["goal"]["value"] == "83.33%"
    assert by_id["risk-budget"]["value"] == "80.00%"
    assert "2 个 active owners" in by_id["goal"]["detail"]
    assert "2 个 active owners" in by_id["risk-budget"]["detail"]


def test_resolve_executive_kpi_metrics_uses_latest_active_year_when_report_date_missing(monkeypatch):
    module = _load_kpi_service_module()
    summary_calls: list[int] = []

    class LatestYearRepo:
        def __init__(self, *_args, **_kwargs):
            pass

        def list_owners(self, *, year=None, is_active=None):
            assert is_active is True
            assert year is None
            return [
                {"owner_id": 20, "owner_name": "历史 owner", "year": 2025},
                {"owner_id": 30, "owner_name": "最新 owner A", "year": 2026},
                {"owner_id": 31, "owner_name": "最新 owner B", "year": 2026},
            ]

        def fetch_period_summary(self, *, owner_id, year, period_type):
            summary_calls.append(owner_id)
            assert year == 2026
            assert period_type == "YEAR"
            payloads = {
                30: {
                    "total_weight": "40",
                    "total_score": "32",
                    "metrics": [],
                },
                31: {
                    "total_weight": "60",
                    "total_score": "48",
                    "metrics": [],
                },
            }
            return payloads[owner_id]

    monkeypatch.setattr(module, "KpiRepository", LatestYearRepo)

    metrics = module.resolve_executive_kpi_metrics(
        dsn="sqlite:///tmp/kpi.db",
        report_date=None,
    )

    by_id = {item["id"]: item for item in metrics}
    assert by_id["goal"]["value"] == "80.00%"
    assert summary_calls == [30, 31]
