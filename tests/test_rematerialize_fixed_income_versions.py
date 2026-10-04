"""Selection and receipt semantics of scripts/rematerialize_fixed_income_versions.py.

No DuckDB writes: the planner is exercised with a stub lineage resolver and the
executor with a stub runner, so the test proves which dates/modules would be rebuilt
and how failures are recorded — not the materialization itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.core_finance.fixed_income_version_set import FIXED_INCOME_VERSION_SET
from scripts import rematerialize_fixed_income_versions as remat

BOND_CURRENT = FIXED_INCOME_VERSION_SET.bond_analytics.rule_version
RISK_CURRENT = FIXED_INCOME_VERSION_SET.risk_tensor.rule_version


def _resolver(state: dict[tuple[str, str], str | None]):
    def resolve(report_date: str, version):
        observed = state.get((report_date, version.module_name))
        return None if observed is None else {"rule_version": observed}

    return resolve


def test_plan_skips_dates_already_at_current_versions_and_orders_bond_before_risk() -> None:
    state = {
        ("2026-07-31", "bond_analytics"): BOND_CURRENT,
        ("2026-07-31", "risk_tensor"): RISK_CURRENT,
        ("2026-07-30", "bond_analytics"): "rv_bond_analytics_formal_materialize_v2",
        ("2026-07-30", "risk_tensor"): "rv_risk_tensor_formal_materialize_v6",
        ("2026-04-04", "bond_analytics"): BOND_CURRENT,
        ("2026-04-04", "risk_tensor"): "rv_risk_tensor_formal_materialize_v5",
    }
    plans = remat.plan_dates(
        ["2026-07-31", "2026-07-30", "2026-04-04"],
        modules=("risk_tensor", "bond_analytics"),
        resolve_lineage=_resolver(state),
    )
    assert [(p.report_date, p.modules) for p in plans] == [
        ("2026-07-30", ("bond_analytics", "risk_tensor")),
        ("2026-04-04", ("risk_tensor",)),
    ]
    assert plans[0].current_versions == {
        "bond_analytics": "rv_bond_analytics_formal_materialize_v2",
        "risk_tensor": "rv_risk_tensor_formal_materialize_v6",
    }


def test_plan_reruns_risk_tensor_whenever_bond_analytics_is_rebuilt() -> None:
    # Risk tensor already at v7 but its bond inputs are stale: it must follow the rebuild.
    state = {
        ("2026-01-05", "bond_analytics"): None,
        ("2026-01-05", "risk_tensor"): RISK_CURRENT,
    }
    plans = remat.plan_dates(["2026-01-05"], modules=remat.MODULE_ORDER, resolve_lineage=_resolver(state))
    assert plans == [
        remat.DatePlan(
            report_date="2026-01-05",
            modules=("bond_analytics", "risk_tensor"),
            current_versions={"bond_analytics": None, "risk_tensor": RISK_CURRENT},
        )
    ]


def test_plan_force_rebuilds_even_when_current() -> None:
    state = {("2026-07-31", "bond_analytics"): BOND_CURRENT, ("2026-07-31", "risk_tensor"): RISK_CURRENT}
    plans = remat.plan_dates(["2026-07-31"], modules=remat.MODULE_ORDER, resolve_lineage=_resolver(state), force=True)
    assert [p.modules for p in plans] == [("bond_analytics", "risk_tensor")]


def test_execute_records_failures_skips_dependent_risk_and_continues(tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    def run(module_name: str, report_date: str) -> dict[str, object]:
        calls.append((module_name, report_date))
        if report_date == "2026-01-02" and module_name == "bond_analytics":
            raise RuntimeError("Could not set lock on file")
        return {"status": "completed"}

    receipt = tmp_path / "receipt.jsonl"
    plans = [
        remat.DatePlan("2026-01-02", ("bond_analytics", "risk_tensor"), {"bond_analytics": None, "risk_tensor": None}),
        remat.DatePlan("2026-01-03", ("bond_analytics", "risk_tensor"), {"bond_analytics": None, "risk_tensor": None}),
    ]
    summary = remat.execute_plans(plans, run=run, receipt_path=receipt, stop_on_failure=False, emit=lambda _line: None)

    assert calls == [
        ("bond_analytics", "2026-01-02"),
        ("bond_analytics", "2026-01-03"),
        ("risk_tensor", "2026-01-03"),
    ]
    assert summary["completed"] == 2
    assert summary["failed"] == 1
    assert summary["skipped_dependents"] == 1
    assert summary["failures"] == [{"report_date": "2026-01-02", "module": "bond_analytics"}]

    records = [json.loads(line) for line in receipt.read_text(encoding="utf-8").splitlines()]
    statuses = [(r["report_date"], r["module"], r["status"]) for r in records]
    assert statuses == [
        ("2026-01-02", "bond_analytics", "failed"),
        ("2026-01-02", "risk_tensor", "skipped_bond_failed"),
        ("2026-01-03", "bond_analytics", "completed"),
        ("2026-01-03", "risk_tensor", "completed"),
    ]
    assert "Could not set lock" in records[0]["error"]
    assert records[2]["target_rule_version"] == BOND_CURRENT


def test_execute_stop_on_failure_halts_after_first_failed_module(tmp_path: Path) -> None:
    def run(module_name: str, report_date: str) -> dict[str, object]:
        return {"status": "failed", "error_message": "boom"}

    plans = [
        remat.DatePlan("2026-01-02", ("bond_analytics",), {}),
        remat.DatePlan("2026-01-03", ("bond_analytics",), {}),
    ]
    summary = remat.execute_plans(plans, run=run, receipt_path=None, stop_on_failure=True, emit=lambda _line: None)
    assert summary["failed"] == 1
    assert summary.get("stopped_early") is True


def test_main_rejects_unknown_module(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        remat.main(["--modules", "bond_analytics,unknown", "--dry-run", "--dates", "2026-01-02"])
    assert excinfo.value.code == 2
    assert "unknown modules" in capsys.readouterr().err


def test_risk_only_run_is_blocked_when_bond_facts_are_stale(tmp_path: Path) -> None:
    """--modules risk_tensor 不得把 v7 风险张量叠在 v2 债券事实上：计划为 blocked_bond_stale，不执行。"""
    state = {
        ("2026-02-01", "bond_analytics"): "rv_bond_analytics_formal_materialize_v2",
        ("2026-02-01", "risk_tensor"): "rv_risk_tensor_formal_materialize_v6",
        ("2026-02-02", "bond_analytics"): BOND_CURRENT,
        ("2026-02-02", "risk_tensor"): "rv_risk_tensor_formal_materialize_v6",
    }
    plans = remat.plan_dates(["2026-02-01", "2026-02-02"], modules=("risk_tensor",), resolve_lineage=_resolver(state))
    assert [(p.report_date, p.modules) for p in plans] == [
        ("2026-02-01", (remat.BLOCKED_BOND_STALE,)),
        ("2026-02-02", ("risk_tensor",)),
    ]

    calls: list[tuple[str, str]] = []

    def run(module_name: str, report_date: str) -> dict[str, object]:
        calls.append((module_name, report_date))
        return {"status": "completed"}

    receipt = tmp_path / "receipt.jsonl"
    summary = remat.execute_plans(plans, run=run, receipt_path=receipt, stop_on_failure=False, emit=lambda _l: None)
    assert calls == [("risk_tensor", "2026-02-02")]
    assert summary["skipped_dependents"] == 1 and summary["completed"] == 1 and summary["failed"] == 0
    records = [json.loads(line) for line in receipt.read_text(encoding="utf-8").splitlines()]
    assert records[0]["status"] == remat.BLOCKED_BOND_STALE
    assert records[0]["bond_rule_version"] == "rv_bond_analytics_formal_materialize_v2"
    assert records[0]["target_rule_version"] == RISK_CURRENT


def test_main_rejects_malformed_dates_and_inverted_range(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        remat.main(["--dry-run", "--dates", "2026-7-1"])
    assert excinfo.value.code == 2
    assert "--dates must be YYYY-MM-DD" in capsys.readouterr().err

    with pytest.raises(SystemExit) as excinfo:
        remat.main(["--dry-run", "--dates", "2026-07-01", "--from", "2026-08-01", "--to", "2026-07-01"])
    assert excinfo.value.code == 2
    assert "is after --to" in capsys.readouterr().err


def test_select_dates_is_inclusive_on_both_bounds() -> None:
    dates = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
    assert remat._select_dates(dates, date_from="2026-01-02", date_to="2026-01-03") == ["2026-01-02", "2026-01-03"]
    assert remat._select_dates(dates, date_from=None, date_to="2026-01-01") == ["2026-01-01"]
    assert remat._select_dates(dates, date_from="2026-01-04", date_to=None) == ["2026-01-04"]


def test_main_dry_run_reports_plan_and_honours_limit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """dry-run 不写库：用 stub lineage 让三个日期都待重算，--limit 2 只保留前两个。"""
    monkeypatch.setattr(remat, "_governance_lineage_resolver", lambda _dir: (lambda _d, _v: None))

    exit_code = remat.main([
        "--dry-run",
        "--dates", "2026-03-01", "2026-03-02", "2026-03-03",
        "--from", "2026-03-01",
        "--limit", "2",
        "--duckdb-path", "unused.duckdb",
        "--governance-dir", "unused-governance",
    ])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "dry_run"
    assert payload["candidate_dates"] == 3
    assert payload["pending_dates"] == 2
    assert [p["report_date"] for p in payload["plan"]] == ["2026-03-01", "2026-03-02"]
    assert payload["plan"][0]["modules"] == ["bond_analytics", "risk_tensor"]
    assert payload["target_versions"] == {"bond_analytics": BOND_CURRENT, "risk_tensor": RISK_CURRENT}
    assert payload["boundary"]["uses_api_or_service_write_path"] is False
