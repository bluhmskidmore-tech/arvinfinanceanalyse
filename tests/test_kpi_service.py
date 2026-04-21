from __future__ import annotations

import uuid

import pytest

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


def test_resolve_kpi_authority_gate_blocks_when_no_active_owners(monkeypatch):
    module = _load_kpi_service_module()

    class EmptyRepo:
        def __init__(self, *_args, **_kwargs):
            pass

        def list_owners(self, *, year=None, is_active=None):
            assert is_active is True
            return []

    monkeypatch.setattr(module, "KpiRepository", EmptyRepo)

    gate = module.resolve_kpi_authority_gate(
        dsn="postgresql://moss:moss@127.0.0.1:55432/moss",
        year=2026,
    )

    assert gate["status"] == "blocked"
    assert gate["reason"] == "no-active-owners"
    assert gate["owner_count"] == 0


def test_resolve_kpi_authority_gate_blocks_when_dsn_missing():
    module = _load_kpi_service_module()

    gate = module.resolve_kpi_authority_gate(dsn="", year=2026)

    assert gate["status"] == "blocked"
    assert gate["reason"] == "missing-dsn"


def test_kpi_owners_payload_raises_when_authority_is_blocked(monkeypatch):
    module = _load_kpi_service_module()

    monkeypatch.setattr(
        module,
        "resolve_kpi_authority_gate",
        lambda **_kwargs: {
            "status": "blocked",
            "reason": "no-active-owners",
            "owner_count": 0,
            "year": 2026,
        },
    )

    with pytest.raises(module.KpiAuthorityBlockedError, match="authority unavailable"):
        module.kpi_owners_payload(
            dsn="postgresql://moss:moss@127.0.0.1:55432/moss",
            year=2026,
            is_active=True,
        )


def test_kpi_owners_payload_allows_inactive_lookup_without_active_gate(monkeypatch):
    module = _load_kpi_service_module()

    monkeypatch.setattr(
        module,
        "resolve_kpi_authority_gate",
        lambda **_kwargs: {
            "status": "blocked",
            "reason": "no-active-owners",
            "owner_count": 0,
            "year": 2026,
        },
    )

    class InactiveRepo:
        def __init__(self, *_args, **_kwargs):
            pass

        def list_owners(self, *, year=None, is_active=None):
            assert year == 2026
            assert is_active is False
            return [
                {
                    "owner_id": 9,
                    "owner_name": "Inactive Owner",
                    "org_unit": "Trading",
                    "person_name": None,
                    "year": 2026,
                    "scope_type": "department",
                    "scope_key": None,
                    "is_active": False,
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-02T00:00:00+00:00",
                }
            ]

    monkeypatch.setattr(module, "KpiRepository", InactiveRepo)

    payload = module.kpi_owners_payload(
        dsn="postgresql://moss:moss@127.0.0.1:55432/moss",
        year=2026,
        is_active=False,
    )

    assert payload["total"] == 1
    assert payload["owners"][0]["owner_name"] == "Inactive Owner"


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


def test_resolve_executive_kpi_metrics_raises_when_summary_breaks_after_gate(monkeypatch):
    module = _load_kpi_service_module()

    monkeypatch.setattr(
        module,
        "resolve_kpi_authority_gate",
        lambda **_kwargs: {
            "status": "available",
            "reason": "active-owners-present",
            "owner_count": 1,
            "year": 2026,
        },
    )

    class BrokenRepo:
        def __init__(self, *_args, **_kwargs):
            pass

        def list_owners(self, *, year=None, is_active=None):
            return [{"owner_id": 1, "owner_name": "Fixed Income", "year": 2026}]

        def fetch_period_summary(self, *, owner_id, year, period_type):
            raise RuntimeError("summary failed")

    monkeypatch.setattr(module, "KpiRepository", BrokenRepo)

    with pytest.raises(RuntimeError, match="metrics resolution failed"):
        module.resolve_executive_kpi_metrics(
            dsn="postgresql://moss:moss@127.0.0.1:55432/moss",
            report_date="2026-03-31",
        )


def test_resolve_executive_kpi_metrics_returns_empty_on_malformed_report_date(monkeypatch):
    module = _load_kpi_service_module()

    monkeypatch.setattr(
        module,
        "resolve_kpi_authority_gate",
        lambda **_kwargs: {
            "status": "available",
            "reason": "active-owners-present",
            "owner_count": 1,
            "year": 2026,
        },
    )

    class Repo:
        def __init__(self, *_args, **_kwargs):
            pass

        def list_owners(self, *, year=None, is_active=None):
            assert year is None
            assert is_active is True
            return [{"owner_id": 1, "owner_name": "Fixed Income", "year": 2026}]

        def fetch_period_summary(self, *, owner_id, year, period_type):
            assert year == 2026
            return {
                "total_weight": "10",
                "total_score": "9",
                "metrics": [],
            }

    monkeypatch.setattr(module, "KpiRepository", Repo)

    result = module.resolve_executive_kpi_metrics(
        dsn="postgresql://moss:moss@127.0.0.1:55432/moss",
        report_date="2026/03/31",
    )

    assert result == []


def test_kpi_period_summary_payload_raises_when_authority_is_blocked(monkeypatch):
    module = _load_kpi_service_module()

    monkeypatch.setattr(
        module,
        "resolve_kpi_authority_gate",
        lambda **_kwargs: {
            "status": "blocked",
            "reason": "no-active-owners",
            "owner_count": 0,
            "year": 2026,
        },
    )

    with pytest.raises(module.KpiAuthorityBlockedError, match="authority unavailable"):
        module.kpi_period_summary_payload(
            dsn="postgresql://moss:moss@127.0.0.1:55432/moss",
            owner_id=1,
            year=2026,
            period_type="YEAR",
        )
