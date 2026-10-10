from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.app.core_finance.pnl_by_business_insights import prior_year_same_period_date
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.repositories.pnl_repo import PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION
from backend.app.tasks import pnl_by_business_precompute, pnl_materialize


@pytest.mark.parametrize(
    ("as_of_date", "expected"),
    [
        ("2026-08-31", "2025-08-31"),
        ("2024-02-29", "2023-02-28"),
        ("2025-02-28", "2024-02-28"),
    ],
)
def test_prior_year_same_period_date_clamps_leap_day(as_of_date, expected) -> None:
    assert prior_year_same_period_date(as_of_date) == expected


def test_insight_dependency_cutoffs_use_exact_baseline_and_prior_year_latest() -> None:
    class FakeRepo:
        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            return "2025-08-31" if as_of_cap == "2025-08-31" else "2025-12-31"

    assert pnl_materialize._pnl_by_business_insight_dependency_cutoffs(
        FakeRepo(),
        report_date="2026-08-31",
    ) == [(2025, "2025-08-31"), (2025, "2025-12-31")]


def test_insight_dependency_cutoffs_skip_missing_history() -> None:
    class FakeRepo:
        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            return None

    assert (
        pnl_materialize._pnl_by_business_insight_dependency_cutoffs(
            FakeRepo(),
            report_date="2026-08-31",
        )
        == []
    )


def test_insight_dependency_cutoffs_include_resolved_baseline_fallback() -> None:
    class FakeRepo:
        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            return "2025-07-31" if as_of_cap == "2025-08-31" else "2025-12-31"

    assert pnl_materialize._pnl_by_business_insight_dependency_cutoffs(
        FakeRepo(),
        report_date="2026-08-31",
    ) == [(2025, "2025-07-31"), (2025, "2025-12-31")]


def test_materialize_rebuilds_only_stale_insight_dependency(monkeypatch) -> None:
    class FakeRepo:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            return "2025-08-31" if as_of_cap == "2025-08-31" else "2025-12-31"

    checks: list[str] = []
    rebuilds: list[str] = []

    def is_current(**kwargs):
        checks.append(str(kwargs["as_of_date"]))
        return kwargs["as_of_date"] == "2025-08-31"

    def precompute(**kwargs):
        rebuilds.append(str(kwargs["as_of_date"]))
        return {
            "records": 118,
            "source_version": f"source::{kwargs['as_of_date']}",
        }

    monkeypatch.setattr(pnl_materialize, "PnlRepository", FakeRepo)
    monkeypatch.setattr(
        pnl_materialize,
        "pnl_by_business_insight_dependencies_are_current",
        is_current,
    )
    monkeypatch.setattr(
        pnl_materialize,
        "precompute_pnl_by_business_payloads",
        precompute,
    )

    result = pnl_materialize._materialize_pnl_by_business_insight_dependencies(
        duckdb_path="isolated.duckdb",
        governance_dir="isolated-governance",
        report_date="2026-08-31",
    )

    assert checks == ["2025-08-31", "2025-12-31"]
    assert rebuilds == ["2025-12-31"]
    assert result == [
        {
            "year": 2025,
            "as_of_date": "2025-08-31",
            "status": "current",
            "records": 0,
        },
        {
            "year": 2025,
            "as_of_date": "2025-12-31",
            "status": "rebuilt",
            "records": 118,
            "rule_version": PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
        },
    ]


@pytest.mark.parametrize(
    ("failure_stage", "error_type"),
    [("validation", RuntimeError), ("rebuild", ValueError)],
)
def test_optional_dependency_failure_is_recorded_and_other_cutoffs_continue(
    monkeypatch,
    failure_stage,
    error_type,
) -> None:
    class FakeRepo:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            return "2025-08-31" if as_of_cap == "2025-08-31" else "2025-12-31"

    rebuilds: list[str] = []

    def is_current(**kwargs):
        cutoff = str(kwargs["as_of_date"])
        if cutoff == "2025-08-31" and failure_stage == "validation":
            raise error_type("optional history unavailable")
        return cutoff == "2025-12-31"

    def precompute(**kwargs):
        cutoff = str(kwargs["as_of_date"])
        rebuilds.append(cutoff)
        raise error_type("optional history unavailable")

    monkeypatch.setattr(pnl_materialize, "PnlRepository", FakeRepo)
    monkeypatch.setattr(
        pnl_materialize,
        "pnl_by_business_insight_dependencies_are_current",
        is_current,
    )
    monkeypatch.setattr(pnl_materialize, "precompute_pnl_by_business_payloads", precompute)

    result = pnl_materialize._materialize_pnl_by_business_insight_dependencies(
        duckdb_path="isolated.duckdb",
        governance_dir="isolated-governance",
        report_date="2026-08-31",
    )

    assert result[0]["status"] == "failed"
    assert result[0]["failure_stage"] == failure_stage
    assert result[0]["error_message"] == "optional history unavailable"
    assert result[1]["status"] == "current"
    assert rebuilds == ([] if failure_stage == "validation" else ["2025-08-31"])


def test_current_materialize_completes_when_optional_dependencies_fail(
    tmp_path,
    monkeypatch,
) -> None:
    dependency_result = [
        {
            "year": 2025,
            "as_of_date": "2025-12-31",
            "status": "failed",
            "failure_stage": "rebuild",
            "error_message": "optional history unavailable",
            "records": 0,
        }
    ]
    # Reloads keep the Actor identity while rebinding fn to a new module's globals.
    actor_globals = pnl_materialize.materialize_pnl_facts.fn.__globals__
    monkeypatch.setitem(
        actor_globals,
        "precompute_pnl_by_business_payloads",
        lambda **kwargs: {"records": 1, "as_of_date": kwargs["as_of_date"]},
    )
    monkeypatch.setitem(
        actor_globals,
        "_materialize_pnl_by_business_insight_dependencies",
        lambda **_kwargs: dependency_result,
    )
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    payload = pnl_materialize.materialize_pnl_facts.fn(
        report_date="2026-08-31",
        is_month_end=True,
        fi_rows=[
            {
                "report_date": "2026-08-31",
                "instrument_code": "240001.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "交易性金融资产",
                "interest_income_514": "12.50",
                "fair_value_change_516": "-3.25",
                "capital_gain_517": "1.75",
                "manual_adjustment": "0.50",
                "currency_basis": "CNY",
                "source_version": "src-v1",
                "rule_version": "rule-v1",
                "ingest_batch_id": "batch-fi",
                "trace_id": "trace-fi",
                "approval_status": "approved",
                "event_semantics": "realized_incremental",
                "realized_flag": True,
            }
        ],
        nonstd_rows_by_type={},
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        formal_pnl_enabled=True,
        formal_pnl_scope_json='["*"]',
    )

    assert payload["status"] == "completed"
    completed = [
        record
        for record in GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
        if record.get("job_name") == "pnl_materialize" and record.get("status") == "completed"
    ]
    assert completed[-1]["pnl_by_business_insight_dependencies"] == dependency_result


def test_dependency_current_check_requires_ytd_and_monthly_with_full_versions(
    monkeypatch,
) -> None:
    fetch_calls: list[dict[str, object]] = []

    class FakeRepo:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            return as_of_cap

        def fetch_pnl_by_business_precompute(self, **kwargs):
            fetch_calls.append(kwargs)
            return None if kwargs["result_kind"] == "monthly" else {"result": "ready"}

    monkeypatch.setattr(pnl_by_business_precompute, "PnlRepository", FakeRepo)
    monkeypatch.setattr(
        pnl_by_business_precompute,
        "get_settings",
        lambda: SimpleNamespace(ftp_rate_pct=Decimal("9.99")),
    )
    monkeypatch.setattr(
        pnl_by_business_precompute,
        "active_pnl_by_business_manual_adjustments_for_period",
        lambda *_args, **_kwargs: [{"adjustment_id": "approved-a"}],
    )
    monkeypatch.setattr(
        pnl_by_business_precompute,
        "pnl_by_business_manual_adjustment_source_version",
        lambda _records: "sv-adjustments-current",
    )

    assert not pnl_by_business_precompute.pnl_by_business_insight_dependencies_are_current(
        duckdb_path="isolated.duckdb",
        governance_dir="isolated-governance",
        year=2025,
        as_of_date="2025-12-31",
    )
    assert [call["result_kind"] for call in fetch_calls] == ["ytd", "monthly"]
    assert all(
        call["expected_rule_version"] == PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION
        and call["supplemental_source_version"] == "sv-adjustments-current"
        and call["effective_ftp_rate_pct"] == Decimal("1.75")
        for call in fetch_calls
    )
