from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import json
from pathlib import Path

import duckdb
import pytest

from tests.helpers import load_module


def _seed_snapshot(path: Path) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            create table zqtz_bond_daily_snapshot (
              report_date date,
              instrument_code varchar,
              bond_type varchar,
              coupon_rate decimal(24, 8),
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        coupons = {
            "2089281": Decimal("2.87"),
            "2089307": Decimal("2.95"),
            "2089512": Decimal("3.00"),
            "2089517": Decimal("3.15"),
            "2189002": Decimal("3.25"),
            "2189170": Decimal("2.85"),
        }
        first_negative = {code: date(2025, 10, 27) for code in coupons}
        first_negative["2089281"] = date(2025, 10, 20)
        rows = []
        current = date(2025, 10, 1)
        while current <= date(2025, 11, 30):
            for code, coupon in coupons.items():
                value = coupon
                if first_negative[code] <= current <= date(2025, 11, 2):
                    value = coupon - Decimal("3.60")
                rows.append(
                    (
                        current,
                        code,
                        "资产支持证券",
                        value,
                        f"sv_{current.isoformat()}",
                        "rv_snapshot_zqtz_tyw_v1",
                        f"ib_{current.isoformat()}",
                        f"trace_{current.isoformat()}_{code}",
                    )
                )
            current += timedelta(days=1)
        conn.executemany(
            "insert into zqtz_bond_daily_snapshot values (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        conn.close()


def test_risk_coupon_window_repair_dry_run_is_exact_and_read_only(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_snapshot(duckdb_path)
    task_mod = load_module(
        "backend.app.tasks.risk_coupon_window_repair",
        "backend/app/tasks/risk_coupon_window_repair.py",
    )

    result = task_mod.repair_risk_coupon_window.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(tmp_path / "governance"),
        run_id="repair-dry-run",
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["target_count"] == 49
    assert result["change_count"] == 49
    assert result["already_repaired_count"] == 0
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        assert conn.execute(
            "select count(*) from zqtz_bond_daily_snapshot where coupon_rate < 0"
        ).fetchone()[0] == 49
    finally:
        conn.close()


def test_risk_coupon_window_repair_updates_exact_rows_and_governance(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot(duckdb_path)
    task_mod = load_module(
        "backend.app.tasks.risk_coupon_window_repair",
        "backend/app/tasks/risk_coupon_window_repair.py",
    )
    from backend.app.tasks import bond_analytics_materialize, risk_tensor_materialize

    downstream_calls: list[tuple[str, str, bool | None]] = []

    def fake_bond_materialize(
        *,
        report_date,
        duckdb_path,
        governance_dir,
        run_id,
        use_existing_curves_only=False,
    ):
        downstream_calls.append(("bond", report_date, use_existing_curves_only))
        return {"status": "completed", "source_version": "sv_bond_test"}

    def fake_risk_materialize(*, report_date, duckdb_path, governance_dir, run_id):
        downstream_calls.append(("risk", report_date, None))
        return {
            "status": "completed",
            "source_version": "sv_risk_test",
            "rule_version": "rv_risk_tensor_formal_materialize_v5",
            "cache_version": "risk-test-cache",
        }

    monkeypatch.setattr(
        bond_analytics_materialize.materialize_bond_analytics_facts,
        "fn",
        fake_bond_materialize,
    )
    monkeypatch.setattr(
        risk_tensor_materialize.materialize_risk_tensor_facts,
        "fn",
        fake_risk_materialize,
    )

    result = task_mod.repair_risk_coupon_window.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        run_id="repair-live",
        dry_run=False,
    )

    assert result["status"] == "completed"
    assert result["changed_count"] == 49
    assert downstream_calls == [
        call
        for report_date in task_mod.TARGET_REPORT_DATES
        for call in (("bond", report_date, True), ("risk", report_date, None))
    ]
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        assert conn.execute(
            "select count(*) from zqtz_bond_daily_snapshot where coupon_rate < 0"
        ).fetchone()[0] == 0
        repaired = conn.execute(
            """
            select count(*)
            from zqtz_bond_daily_snapshot
            where source_version like '%sv_negative_coupon_window_repair_20260809_v1%'
              and rule_version like '%rv_snapshot_negative_coupon_window_repair_v1%'
            """
        ).fetchone()[0]
        assert repaired == 49
    finally:
        conn.close()
    records = [
        json.loads(line)
        for line in (governance_dir / "data_quality_remediation.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert [record["status"] for record in records] == ["started", "completed"]


def test_risk_coupon_window_repair_fails_closed_when_existing_curve_contract_is_missing(
    tmp_path,
    monkeypatch,
):
    task_mod = load_module(
        "backend.app.tasks.risk_coupon_window_repair",
        "backend/app/tasks/risk_coupon_window_repair.py",
    )
    from backend.app.tasks import bond_analytics_materialize, risk_tensor_materialize

    risk_calls: list[str] = []

    def legacy_bond_materialize(*, report_date, duckdb_path, governance_dir, run_id):
        return {"status": "completed"}

    def fake_risk_materialize(*, report_date, duckdb_path, governance_dir, run_id):
        risk_calls.append(report_date)
        return {"status": "completed"}

    monkeypatch.setattr(
        bond_analytics_materialize.materialize_bond_analytics_facts,
        "fn",
        legacy_bond_materialize,
    )
    monkeypatch.setattr(
        risk_tensor_materialize.materialize_risk_tensor_facts,
        "fn",
        fake_risk_materialize,
    )

    with pytest.raises(TypeError, match="use_existing_curves_only"):
        task_mod._rematerialize_downstream(
            report_dates=[task_mod.TARGET_REPORT_DATES[0]],
            duckdb_path=str(tmp_path / "moss.duckdb"),
            governance_dir=str(tmp_path / "governance"),
            run_id="repair-contract-drift",
        )

    assert risk_calls == []


def test_risk_coupon_window_repair_records_failure_and_retries_idempotently(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot(duckdb_path)
    task_mod = load_module(
        "backend.app.tasks.risk_coupon_window_repair",
        "backend/app/tasks/risk_coupon_window_repair.py",
    )
    from backend.app.tasks import bond_analytics_materialize, risk_tensor_materialize

    fail_risk = True
    downstream_calls: list[tuple[str, str]] = []

    def fake_bond_materialize(
        *,
        report_date,
        duckdb_path,
        governance_dir,
        run_id,
        use_existing_curves_only=False,
    ):
        assert use_existing_curves_only is True
        downstream_calls.append(("bond", report_date))
        return {"status": "completed", "source_version": "sv_bond_test"}

    def fake_risk_materialize(*, report_date, duckdb_path, governance_dir, run_id):
        downstream_calls.append(("risk", report_date))
        return {
            "status": "failed" if fail_risk else "completed",
            "source_version": "sv_risk_test",
            "rule_version": "rv_risk_tensor_formal_materialize_v5",
            "cache_version": "risk-test-cache",
        }

    monkeypatch.setattr(
        bond_analytics_materialize.materialize_bond_analytics_facts,
        "fn",
        fake_bond_materialize,
    )
    monkeypatch.setattr(
        risk_tensor_materialize.materialize_risk_tensor_facts,
        "fn",
        fake_risk_materialize,
    )

    with pytest.raises(RuntimeError, match="Risk Tensor rematerialization failed"):
        task_mod.repair_risk_coupon_window.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            run_id="repair-retry",
            dry_run=False,
        )

    first_attempt_records = [
        json.loads(line)
        for line in (governance_dir / "data_quality_remediation.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert [record["status"] for record in first_attempt_records] == ["started", "failed"]
    assert first_attempt_records[-1]["error"].startswith(
        "Risk Tensor rematerialization failed"
    )

    fail_risk = False
    retry_result = task_mod.repair_risk_coupon_window.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        run_id="repair-retry",
        dry_run=False,
    )

    assert retry_result["status"] == "completed"
    assert retry_result["changed_count"] == 0
    assert retry_result["change_count"] == 0
    assert retry_result["already_repaired_count"] == 49
    assert downstream_calls == [
        ("bond", task_mod.TARGET_REPORT_DATES[0]),
        ("risk", task_mod.TARGET_REPORT_DATES[0]),
        *[
            call
            for report_date in task_mod.TARGET_REPORT_DATES
            for call in (("bond", report_date), ("risk", report_date))
        ],
    ]
    retry_records = [
        json.loads(line)
        for line in (governance_dir / "data_quality_remediation.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert [record["status"] for record in retry_records] == [
        "started",
        "failed",
        "started",
        "completed",
    ]


def test_risk_coupon_window_repair_rejects_ambiguous_neighbor_evidence(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_snapshot(duckdb_path)
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set coupon_rate = 2.90
            where report_date = '2025-11-03'
              and instrument_code = '2089281'
            """
        )
    finally:
        conn.close()
    task_mod = load_module(
        "backend.app.tasks.risk_coupon_window_repair",
        "backend/app/tasks/risk_coupon_window_repair.py",
    )

    with pytest.raises(RuntimeError, match="matching before/after neighbor evidence"):
        task_mod.repair_risk_coupon_window.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(tmp_path / "governance"),
            run_id="repair-ambiguous",
            dry_run=True,
        )
