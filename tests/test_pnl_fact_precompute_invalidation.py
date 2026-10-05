from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import duckdb
import pytest

from backend.app.core_finance.balance_analysis import FormalZqtzBalanceFactRow
from backend.app.repositories import balance_analysis_repo as balance_repo_module
from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
from backend.app.repositories.duckdb_migrations import _v24_zqtz_accounting_sub_type
from backend.app.repositories.pnl_precompute_state import (
    current_pnl_by_business_event_revision_on_connection,
)
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.tasks import pnl_materialize


def _fi_row(report_date: str, source_version: str) -> dict[str, object]:
    return {
        "report_date": report_date,
        "instrument_code": f"FI-{report_date}",
        "portfolio_name": "FI Desk",
        "cost_center": "CC100",
        "invest_type_raw": "交易性金融资产",
        "interest_income_514": "10.00",
        "fair_value_change_516": "1.00",
        "capital_gain_517": "2.00",
        "manual_adjustment": "0.00",
        "currency_basis": "CNY",
        "source_version": source_version,
        "approval_status": "approved",
        "event_semantics": "realized_incremental",
        "realized_flag": True,
    }


def _nonstd_rows(report_date: str) -> dict[str, list[dict[str, object]]]:
    return {
        "516": [
            {
                "voucher_date": report_date,
                "account_code": "51601010004",
                "asset_code": f"NS-{report_date}",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "dc_flag": "credit",
                "event_type": "mtm",
                "raw_amount": "3.00",
                "source_file": f"nonstd-{report_date}.xlsx",
                "source_version": f"nonstd-{report_date}",
                "rule_version": "nonstd-rule-v1",
                "ingest_batch_id": f"nonstd-batch-{report_date}",
                "trace_id": f"nonstd-trace-{report_date}",
            }
        ]
    }


def _materialize_pnl(
    *,
    duckdb_path,
    governance_dir,
    report_date: str,
    include_rows: bool = True,
) -> None:
    pnl_materialize.materialize_pnl_facts.fn(
        report_date=report_date,
        is_month_end=True,
        fi_rows=[_fi_row(report_date, f"source-{report_date}")] if include_rows else [],
        nonstd_rows_by_type=_nonstd_rows(report_date) if include_rows else {},
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        formal_pnl_enabled=True,
        formal_pnl_scope_json='["*"]',
    )


def _event_revision(duckdb_path) -> int:
    with duckdb.connect(str(duckdb_path), read_only=True) as conn:
        return current_pnl_by_business_event_revision_on_connection(conn)


def test_pnl_fact_commits_persist_revision_for_rerun_history_and_deletion(
    tmp_path, monkeypatch
) -> None:
    duckdb_path = tmp_path / "pnl-invalidation.duckdb"
    governance_dir = tmp_path / "governance"
    precompute_dates: list[str] = []
    insight_dependency_dates: list[str] = []

    def precompute(**kwargs):
        precompute_dates.append(kwargs["as_of_date"])
        return {"records": 0}

    def materialize_insight_dependencies(**kwargs):
        insight_dependency_dates.append(kwargs["report_date"])
        return []

    # Actor registration keeps its identity but may replace fn after a module reload.
    actor_globals = pnl_materialize.materialize_pnl_facts.fn.__globals__
    monkeypatch.setitem(
        actor_globals,
        "precompute_pnl_by_business_payloads",
        precompute,
    )
    monkeypatch.setitem(
        actor_globals,
        "_materialize_pnl_by_business_insight_dependencies",
        materialize_insight_dependencies,
    )

    _materialize_pnl(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date="2025-12-31",
    )
    assert _event_revision(duckdb_path) == 1

    _materialize_pnl(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date="2025-12-31",
    )
    assert _event_revision(duckdb_path) == 3

    _materialize_pnl(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date="2026-01-31",
    )
    _materialize_pnl(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date="2025-06-30",
    )
    assert _event_revision(duckdb_path) == 5

    pending = PnlRepository(str(duckdb_path)).list_pending_pnl_by_business_precompute()
    latest_2025 = max(
        (item for item in pending if item["year"] == 2025),
        key=lambda item: item["dependency_revision"],
    )
    assert latest_2025["dirty_from_date"] == "2025-06-30"
    assert latest_2025["target_dates"] == ("2025-06-30", "2025-12-31")
    assert any(item["year"] == 2026 for item in pending)

    _materialize_pnl(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date="2025-06-30",
        include_rows=False,
    )
    assert _event_revision(duckdb_path) == 7
    expected_dates = [
        "2025-12-31",
        "2025-12-31",
        "2026-01-31",
        "2025-06-30",
        "2025-06-30",
    ]
    assert precompute_dates == expected_dates
    assert insight_dependency_dates == expected_dates
    with duckdb.connect(str(duckdb_path), read_only=True) as conn:
        assert (
            conn.execute(
                "select count(*) from fact_formal_pnl_fi where report_date = '2025-06-30'"
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                "select count(*) from fact_nonstd_pnl_bridge where report_date = '2025-06-30'"
            ).fetchone()[0]
            == 0
        )


def _zqtz_row(report_date: str) -> FormalZqtzBalanceFactRow:
    return FormalZqtzBalanceFactRow(
        report_date=date.fromisoformat(report_date),
        instrument_code="BOND-001",
        instrument_name="Bond",
        portfolio_name="FI Desk",
        cost_center="CC100",
        account_category="交易性金融资产",
        asset_class="bond",
        bond_type="government",
        issuer_name="Issuer",
        industry_name="Government",
        rating="AAA",
        invest_type_std="T",
        accounting_basis="TPL",
        position_scope="asset",
        currency_basis="CNY",
        currency_code="CNY",
        face_value_amount=Decimal("100"),
        market_value_amount=Decimal("101"),
        amortized_cost_amount=Decimal("100"),
        accrued_interest_amount=Decimal("1"),
        coupon_rate=Decimal("2"),
        ytm_value=Decimal("2.1"),
        maturity_date=date(2030, 12, 31),
        interest_mode="fixed",
        is_issuance_like=False,
        source_version="balance-v1",
        rule_version="balance-rule-v1",
        ingest_batch_id="balance-batch",
        trace_id="balance-trace",
    )


def test_balance_replace_persists_purge_and_insert_as_separate_revisions(tmp_path) -> None:
    duckdb_path = tmp_path / "balance-invalidation.duckdb"
    repo = BalanceAnalysisRepository(str(duckdb_path))
    row = _zqtz_row("2025-12-31")

    with repository_task_write_scope("backend.app.tasks.balance_invalidation_test"):
        repo.replace_formal_balance_rows(
            report_date="2025-12-31",
            zqtz_rows=[row],
            tyw_rows=[],
        )
        assert _event_revision(duckdb_path) == 1
        repo.replace_formal_balance_rows(
            report_date="2025-12-31",
            zqtz_rows=[row],
            tyw_rows=[],
        )

    assert _event_revision(duckdb_path) == 3


def test_balance_daily_history_deletion_stays_dirty_without_registering_daily_cutoff(
    tmp_path,
) -> None:
    duckdb_path = tmp_path / "balance-daily-deletion.duckdb"
    repo = BalanceAnalysisRepository(str(duckdb_path))
    report_date = "2025-06-15"

    with repository_task_write_scope("backend.app.tasks.balance_invalidation_test"):
        repo.replace_formal_balance_rows(
            report_date=report_date,
            zqtz_rows=[_zqtz_row(report_date)],
            tyw_rows=[],
        )
        repo.replace_formal_balance_rows(
            report_date=report_date,
            zqtz_rows=[],
            tyw_rows=[],
        )

    assert _event_revision(duckdb_path) == 2
    pending = PnlRepository(str(duckdb_path)).list_pending_pnl_by_business_precompute()
    assert len(pending) == 1
    assert pending[0]["dirty_from_date"] == report_date
    assert pending[0]["target_dates"] == ()
    with duckdb.connect(str(duckdb_path), read_only=True) as conn:
        assert (
            conn.execute(
                "select count(*) from fact_formal_zqtz_balance_daily where report_date = ?",
                [report_date],
            ).fetchone()[0]
            == 0
        )


def test_balance_insert_invalidation_failure_rolls_back_only_insert_transaction(
    tmp_path, monkeypatch
) -> None:
    duckdb_path = tmp_path / "balance-invalidation-rollback.duckdb"
    repo = BalanceAnalysisRepository(str(duckdb_path))
    row = _zqtz_row("2025-12-31")
    with repository_task_write_scope("backend.app.tasks.balance_invalidation_test"):
        repo.replace_formal_balance_rows(
            report_date="2025-12-31",
            zqtz_rows=[row],
            tyw_rows=[],
        )

    real_invalidate = balance_repo_module.invalidate_pnl_by_business_precompute_on_connection
    calls = 0

    def invalidate_then_fail(conn, *, changed_report_dates, reason):
        nonlocal calls
        calls += 1
        receipt = real_invalidate(
            conn,
            changed_report_dates=changed_report_dates,
            reason=reason,
        )
        if calls == 2:
            raise RuntimeError("stop insert commit")
        return receipt

    monkeypatch.setattr(
        balance_repo_module,
        "invalidate_pnl_by_business_precompute_on_connection",
        invalidate_then_fail,
    )
    with repository_task_write_scope("backend.app.tasks.balance_invalidation_test"):
        with pytest.raises(RuntimeError, match="stop insert commit"):
            repo.replace_formal_balance_rows(
                report_date="2025-12-31",
                zqtz_rows=[row],
                tyw_rows=[],
            )

    assert calls == 2
    assert _event_revision(duckdb_path) == 2
    with duckdb.connect(str(duckdb_path), read_only=True) as conn:
        assert (
            conn.execute(
                "select count(*) from fact_formal_zqtz_balance_daily where report_date = '2025-12-31'"
            ).fetchone()[0]
            == 0
        )


def test_v24_zqtz_backfill_invalidates_in_the_migration_transaction(tmp_path) -> None:
    duckdb_path = tmp_path / "v24-invalidation.duckdb"
    with duckdb.connect(str(duckdb_path), read_only=False) as conn:
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
                report_date varchar,
                business_type_primary varchar,
                sub_type varchar
            )
            """
        )
        conn.execute(
            "insert into fact_formal_zqtz_balance_daily values ('2024-12-31', '政府债券', '')"
        )

        conn.execute("begin transaction")
        _v24_zqtz_accounting_sub_type(conn)
        assert current_pnl_by_business_event_revision_on_connection(conn) == 1
        conn.execute("rollback")

        assert (
            conn.execute(
                "select sub_type from fact_formal_zqtz_balance_daily where report_date = '2024-12-31'"
            ).fetchone()[0]
            == ""
        )
        assert current_pnl_by_business_event_revision_on_connection(conn) == 0

        conn.execute("begin transaction")
        _v24_zqtz_accounting_sub_type(conn)
        conn.execute("commit")

        assert (
            conn.execute(
                "select sub_type from fact_formal_zqtz_balance_daily where report_date = '2024-12-31'"
            ).fetchone()[0]
            == "政府债券"
        )
        assert current_pnl_by_business_event_revision_on_connection(conn) == 1


def test_rebuild_actor_pins_dependency_revision_in_compute_and_receipts(
    tmp_path, monkeypatch
) -> None:
    received: list[dict[str, object]] = []

    def precompute(**kwargs):
        received.append(kwargs)
        return {
            "year": 2025,
            "as_of_date": "2025-12-31",
            "records": 3,
            "source_version": "source-v1",
            "generated_at": "2026-09-13T00:00:00+00:00",
            "dependency_revision": 11,
        }

    monkeypatch.setattr(pnl_materialize, "precompute_pnl_by_business_payloads", precompute)
    governance_dir = tmp_path / "governance"
    result = pnl_materialize._rebuild_pnl_by_business_precompute(
        year=2025,
        as_of_date="2025-12-31",
        duckdb_path=str(tmp_path / "actor-revision.duckdb"),
        governance_dir=str(governance_dir),
        run_id="revision-run",
        dependency_revision=11,
    )

    assert result["dependency_revision"] == 11
    assert len(received) == 1
    resource_budget_latch = received[0].pop("on_resource_budget_exceeded")
    assert callable(resource_budget_latch)
    assert received == [
        {
            "duckdb_path": str(tmp_path / "actor-revision.duckdb"),
            "governance_dir": str(governance_dir),
            "year": 2025,
            "as_of_date": "2025-12-31",
            "expected_dependency_revision": 11,
        }
    ]
    records = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert [record["dependency_revision"] for record in records] == [11, 11]

    resource_limits = {"max_memory_bytes": 1024}
    resource_budget_latch(resource_limits)
    latched_record = json.loads(
        (governance_dir / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert latched_record["status"] == "failed"
    assert latched_record["failure_category"] == "resource_over_budget"
    assert latched_record["dependency_revision"] == 11
    assert latched_record["resource_limits"] == resource_limits


def test_rebuild_actor_confirms_adjustment_handoff_before_compute(
    tmp_path, monkeypatch
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def confirm(**kwargs):
        calls.append(("confirm", kwargs))
        return {
            "dependency_revision": 12,
            "target_dates": ("2025-12-31",),
            "handoff_ids": ("handoff-1",),
            "acknowledged": True,
            "source_versions": {"2025-12-31": "adjustment-v2"},
        }

    def precompute(**kwargs):
        calls.append(("compute", kwargs))
        return {
            "year": 2025,
            "as_of_date": "2025-12-31",
            "records": 3,
            "source_version": "source-v2",
            "generated_at": "2026-09-13T00:00:00+00:00",
            "dependency_revision": 12,
        }

    monkeypatch.setattr(
        pnl_materialize,
        "confirm_pnl_by_business_adjustment_handoffs_under_writer",
        confirm,
    )
    monkeypatch.setattr(pnl_materialize, "precompute_pnl_by_business_payloads", precompute)
    duckdb_path = tmp_path / "actor-handoff.duckdb"
    governance_dir = tmp_path / "governance"

    result = pnl_materialize._rebuild_pnl_by_business_precompute(
        year=2025,
        as_of_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        run_id="handoff-run",
        dependency_revision=11,
        adjustment_handoff_ids=["handoff-1"],
    )

    assert result["dependency_revision"] == 12
    assert [name for name, _kwargs in calls] == ["confirm", "compute"]
    assert calls[0][1] == {
        "duckdb_path": str(duckdb_path),
        "governance_dir": str(governance_dir),
        "handoff_ids": ["handoff-1"],
        "year": 2025,
        "target_dates": ["2025-12-31"],
    }
    assert calls[1][1]["expected_dependency_revision"] == 12
    records = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert [record["dependency_revision"] for record in records] == [11, 12, 12]
    assert records[-1]["adjustment_handoffs_acknowledged"] is True
