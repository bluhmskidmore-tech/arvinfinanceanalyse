from __future__ import annotations

import json
import sys
from decimal import Decimal

import duckdb
import pytest

from tests.helpers import load_module


def test_pnl_materialize_task_writes_fact_tables_and_governance_records(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )
    repo_module = sys.modules.get("backend.app.repositories.pnl_repo")
    if repo_module is None:
        repo_module = load_module(
            "backend.app.repositories.pnl_repo",
            "backend/app/repositories/pnl_repo.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    payload = task_module.materialize_pnl_facts.fn(
        report_date="2025-12-31",
        is_month_end=True,
        fi_rows=[
            {
                "report_date": "2025-12-31",
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
            }
        ],
        nonstd_rows_by_type={
            "516": [
                {
                    "voucher_date": "2025-12-30",
                    "account_code": "51601010004",
                    "asset_code": "BOND-001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "dc_flag": "credit",
                    "event_type": "mtm",
                    "raw_amount": "40.00",
                    "source_file": "nonstd-516.xlsx",
                    "source_version": "src-v1",
                    "rule_version": "rule-v1",
                    "ingest_batch_id": "batch-bridge",
                    "trace_id": "trace-001",
                },
                {
                    "voucher_date": "2025-12-31",
                    "account_code": "51601010004",
                    "asset_code": "BOND-001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "dc_flag": "credit",
                    "event_type": "mtm",
                    "raw_amount": "60.00",
                    "source_file": "nonstd-516.xlsx",
                    "source_version": "src-v1",
                    "rule_version": "rule-v1",
                    "ingest_batch_id": "batch-bridge",
                    "trace_id": "trace-002",
                },
            ]
        },
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"
    assert payload["report_date"] == "2025-12-31"
    assert payload["formal_fi_rows"] == 1
    assert payload["nonstd_bridge_rows"] == 1

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        fi_rows = conn.execute(
            """
            select report_date, instrument_code, total_pnl, source_version
            from fact_formal_pnl_fi
            """
        ).fetchall()
        bridge_rows = conn.execute(
            """
            select report_date, bond_code, total_pnl, trace_id
            from fact_nonstd_pnl_bridge
            """
        ).fetchall()
    finally:
        conn.close()

    assert fi_rows == [("2025-12-31", "240001.IB", Decimal("11.50"), "src-v1")]
    assert bridge_rows == [("2025-12-31", "BOND-001", Decimal("100.00"), "trace-001,trace-002")]

    repo = repo_module.PnlRepository(str(duckdb_path))
    assert repo.list_formal_fi_report_dates() == ["2025-12-31"]
    assert repo.list_nonstd_bridge_report_dates() == ["2025-12-31"]
    assert repo.fetch_formal_fi_rows("2025-12-31")[0]["total_pnl"] == Decimal("11.50")
    assert repo.fetch_nonstd_bridge_rows("2025-12-31")[0]["total_pnl"] == Decimal("100.00")
    assert repo.fetch_formal_fi_rows("2025-12-31")[0]["rule_version"] == task_module.RULE_VERSION
    assert repo.fetch_nonstd_bridge_rows("2025-12-31")[0]["rule_version"] == task_module.RULE_VERSION

    build_runs = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    manifests = [
        json.loads(line)
        for line in (governance_dir / "cache_manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert build_runs[-1]["status"] == "completed"
    assert build_runs[-1]["source_version"] == payload["source_version"]
    assert manifests[-1]["cache_key"] == payload["cache_key"]
    assert manifests[-1]["source_version"] == payload["source_version"]


def test_pnl_materialize_task_rebuilds_same_report_date_without_duplicate_rows(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    base_kwargs = {
        "report_date": "2025-12-31",
        "is_month_end": True,
        "duckdb_path": str(duckdb_path),
        "governance_dir": str(governance_dir),
    }

    task_module.materialize_pnl_facts.fn(
        fi_rows=[
            {
                "report_date": "2025-12-31",
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
            }
        ],
        nonstd_rows_by_type={},
        **base_kwargs,
    )

    task_module.materialize_pnl_facts.fn(
        fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "240001.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "交易性金融资产",
                "interest_income_514": "20.00",
                "fair_value_change_516": "-2.00",
                "capital_gain_517": "1.00",
                "manual_adjustment": "0.00",
                "currency_basis": "CNY",
                "source_version": "src-v2",
            }
        ],
        nonstd_rows_by_type={},
        **base_kwargs,
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        rows = conn.execute(
            """
            select instrument_code, total_pnl, source_version
            from fact_formal_pnl_fi
            where report_date = '2025-12-31'
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [("240001.IB", Decimal("19.00"), "src-v2")]


def test_pnl_materialize_task_rejects_rows_outside_requested_report_date(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    with pytest.raises(ValueError, match="report_date"):
        task_module.materialize_pnl_facts.fn(
            report_date="2025-12-31",
            is_month_end=True,
            fi_rows=[
                {
                    "report_date": "2025-11-30",
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
                }
            ],
            nonstd_rows_by_type={},
            duckdb_path=str(tmp_path / "moss.duckdb"),
            governance_dir=str(tmp_path / "governance"),
        )
