from __future__ import annotations

import json
import sys
from decimal import Decimal

import duckdb
import pytest

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def test_pnl_materialize_rule_version_tracks_vat_normalization_policy() -> None:
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    assert task_module.RULE_VERSION == "rv_pnl_phase2_materialize_v3"


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
                "approval_status": "approved",
                "event_semantics": "realized_incremental",
                "realized_flag": True,
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
        formal_pnl_enabled=True,
        formal_pnl_scope_json='["*"]',
    )

    assert payload["status"] == "completed"
    assert payload["report_date"] == "2025-12-31"
    assert payload["formal_fi_rows"] == 1
    assert payload["nonstd_bridge_rows"] == 1
    assert payload["pnl_by_business_precompute_records"] > 0

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
        precompute_count = conn.execute(
            """
            select count(*)
            from fact_pnl_by_business_precompute
            where year = 2025
              and as_of_date = '2025-12-31'
            """
        ).fetchone()[0]
    finally:
        conn.close()

    assert fi_rows == [("2025-12-31", "240001.IB", Decimal("11.50"), "src-v1")]
    assert bridge_rows == [("2025-12-31", "BOND-001", Decimal("100.00"), "trace-001,trace-002")]
    assert precompute_count == payload["pnl_by_business_precompute_records"]

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

    assert build_runs[0]["status"] == "running"
    assert build_runs[0]["started_at"]
    assert build_runs[-1]["status"] == "completed"
    assert build_runs[-1]["source_version"] == payload["source_version"]
    assert manifests[-1]["cache_key"] == payload["cache_key"]
    assert manifests[-1]["cache_version"] == task_module.PNL_RESULT_CACHE_VERSION
    assert manifests[-1]["basis"] == "formal"
    assert manifests[-1]["module_name"] == "pnl"
    assert manifests[-1]["fact_tables"] == ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"]
    assert manifests[-1]["source_version"] == payload["source_version"]


def test_pnl_materialize_applies_vat_to_taxable_fi_and_jm_514(tmp_path) -> None:
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    task_module.materialize_pnl_facts.fn(
        report_date="2026-06-30",
        is_month_end=True,
        fi_rows=[
            {
                "report_date": "2026-06-30",
                "instrument_code": "NCD-TAXABLE",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "交易性金融资产",
                "asset_class": "同业存单",
                "interest_income_514": "106.00",
                "currency_basis": "CNY",
                "source_version": "src-fi-tax",
            },
            {
                "report_date": "2026-06-30",
                "instrument_code": "GOV-EXEMPT",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "A",
                "asset_class": "国债",
                "interest_income_514": "106.00",
                "currency_basis": "CNY",
                "source_version": "src-fi-tax",
            },
            {
                "report_date": "2026-06-30",
                "instrument_code": "NCD-EXACT",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "交易性金融资产",
                "asset_class": "同业存单",
                "interest_income_514": "206700.0",
                "currency_basis": "CNY",
                "source_version": "src-fi-tax",
            },
            {
                "report_date": "2026-06-30",
                "instrument_code": "T-GOV-EXEMPT",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "T",
                "asset_class": "国债",
                "interest_income_514": "106.00",
                "currency_basis": "CNY",
                "source_version": "src-fi-tax",
            },
            {
                "report_date": "2026-06-30",
                "instrument_code": "H-GOV-EXEMPT",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "H",
                "asset_class": "国债",
                "interest_income_514": "106.00",
                "currency_basis": "CNY",
                "source_version": "src-fi-tax",
            },
        ],
        nonstd_rows_by_type={
            "514": [
                {
                    "voucher_date": "2026-06-30",
                    "account_code": "51401000004",
                    "asset_code": "JM0001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "dc_flag": "贷",
                    "event_type": "interest",
                    "raw_amount": "106.00",
                    "source_file": "非标514-20260101-0630(1).xlsx",
                    "source_version": "src-nonstd-tax",
                },
                {
                    "voucher_date": "2026-06-30",
                    "account_code": "51401000004",
                    "asset_code": "J40001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "dc_flag": "贷",
                    "event_type": "interest",
                    "raw_amount": "106.00",
                    "source_file": "非标514-20260101-0630(1).xlsx",
                    "source_version": "src-nonstd-tax",
                },
                {
                    "voucher_date": "2026-06-30",
                    "account_code": "51401000004",
                    "asset_code": "JM0002",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "dc_flag": "贷",
                    "event_type": "interest",
                    "raw_amount": "206700.0",
                    "source_file": "非标514-20260101-0630(1).xlsx",
                    "source_version": "src-nonstd-tax",
                },
            ]
        },
        duckdb_path=str(duckdb_path),
        governance_dir=str(tmp_path / "governance"),
        formal_pnl_enabled=True,
        formal_pnl_scope_json='["*"]',
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        fi_rows = conn.execute(
            """
            select instrument_code, interest_income_514
            from fact_formal_pnl_fi
            order by instrument_code
            """
        ).fetchall()
        nonstd_rows = conn.execute(
            """
            select bond_code, interest_income_514
            from fact_nonstd_pnl_bridge
            order by bond_code
            """
        ).fetchall()
    finally:
        conn.close()

    assert fi_rows == [
        ("GOV-EXEMPT", Decimal("106.00000000")),
        ("H-GOV-EXEMPT", Decimal("106.00000000")),
        ("NCD-EXACT", Decimal("195000.00000000")),
        ("NCD-TAXABLE", Decimal("100.00000000")),
        ("T-GOV-EXEMPT", Decimal("106.00000000")),
    ]
    assert nonstd_rows == [
        ("J40001", Decimal("106.00000000")),
        ("JM0001", Decimal("100.00000000")),
        ("JM0002", Decimal("195000.00000000")),
    ]


def test_pnl_materialize_recognizes_2026h1_cumulative_fi_517_after_vat(tmp_path) -> None:
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    task_module.materialize_pnl_facts.fn(
        report_date="2026-06-30",
        is_month_end=True,
        fi_rows=[
            {
                "report_date": "2026-06-30",
                "instrument_code": "FI-517-A",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "A",
                "asset_class": "企业债",
                "interest_income_514": "0",
                "fair_value_change_516": "5",
                "capital_gain_517": "-106",
                "event_type": "fi_cumulative_realized_517",
                "currency_basis": "CNY",
                "source_version": "src-fi-517",
            },
            {
                "report_date": "2026-06-30",
                "instrument_code": "FI-517-H",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "H",
                "asset_class": "企业债",
                "interest_income_514": "0",
                "fair_value_change_516": "5",
                "capital_gain_517": "-212",
                "event_type": "fi_cumulative_realized_517",
                "currency_basis": "CNY",
                "source_version": "src-fi-517",
            },
            {
                "report_date": "2026-06-30",
                "instrument_code": "FI-517-T",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "T",
                "asset_class": "企业债",
                "interest_income_514": "0",
                "fair_value_change_516": "5",
                "capital_gain_517": "-318",
                "event_type": "fi_cumulative_realized_517",
                "currency_basis": "CNY",
                "source_version": "src-fi-517",
            },
        ],
        nonstd_rows_by_type={},
        duckdb_path=str(duckdb_path),
        governance_dir=str(tmp_path / "governance"),
        formal_pnl_enabled=True,
        formal_pnl_scope_json='["*"]',
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select instrument_code, fair_value_change_516, capital_gain_517, total_pnl
            from fact_formal_pnl_fi
            order by instrument_code
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        ("FI-517-A", Decimal("0E-8"), Decimal("100.00000000"), Decimal("100.00000000")),
        ("FI-517-H", Decimal("0E-8"), Decimal("200.00000000"), Decimal("200.00000000")),
        ("FI-517-T", Decimal("5.00000000"), Decimal("300.00000000"), Decimal("305.00000000")),
    ]


def test_formal_fi_fact_projection_preserves_source_classification_metadata() -> None:
    pnl_module = load_module("backend.app.core_finance.pnl", "backend/app/core_finance/pnl.py")

    normalized = pnl_module.normalize_fi_pnl_records(
        [
            {
                "report_date": "2026-03-31",
                "instrument_code": "2605287",
                "instrument_name": "26山东债19",
                "portfolio_name": "FIOA",
                "cost_center": "50101002",
                "invest_type_raw": "A",
                "asset_class": "地方政府债券",
                "interest_income_514": "0",
                "fair_value_change_516": "0",
                "capital_gain_517": "192000",
                "event_type": "fi_cumulative_realized_517",
                "currency_basis": "CNY",
            }
        ]
    )

    fact_row = pnl_module.build_formal_pnl_fi_fact_rows(normalized)[0]

    assert fact_row.instrument_name == "26山东债19"
    assert fact_row.asset_class == "地方政府债券"


def test_pnl_materialize_holds_global_duckdb_writer_lock(tmp_path, monkeypatch):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )
    materialize_mod = load_module(
        "backend.app.tasks.materialize",
        "backend/app/tasks/materialize.py",
    )
    locks_mod = load_module(
        "backend.app.governance.locks",
        "backend/app/governance/locks.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    writer_lock = materialize_mod.resolve_materialize_lock(duckdb_path)
    observed = {"contention_checked": False}
    original_normalize = task_module.normalize_fi_pnl_records

    def normalize_under_lock(*args, **kwargs):
        with pytest.raises(TimeoutError):
            with locks_mod.acquire_lock(
                writer_lock,
                base_dir=duckdb_path.parent,
                timeout_seconds=0.01,
            ):
                pass
        observed["contention_checked"] = True
        return original_normalize(*args, **kwargs)

    monkeypatch.setattr(task_module, "normalize_fi_pnl_records", normalize_under_lock)

    payload = task_module.materialize_pnl_facts.fn(
        report_date="2025-12-31",
        is_month_end=True,
        fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "240001.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "TRADING_ASSET",
                "interest_income_514": "12.50",
                "fair_value_change_516": "-3.25",
                "capital_gain_517": "1.75",
                "manual_adjustment": "0.50",
                "currency_basis": "CNY",
                "source_version": "src-v1",
                "approval_status": "approved",
                "event_semantics": "realized_incremental",
                "realized_flag": True,
            }
        ],
        nonstd_rows_by_type={},
        duckdb_path=str(duckdb_path),
        governance_dir=str(tmp_path / "governance"),
        formal_pnl_enabled=True,
        formal_pnl_scope_json='["*"]',
    )

    assert payload["status"] == "completed"
    assert payload["lock"] == task_module.PNL_MATERIALIZE_LOCK.key
    assert observed["contention_checked"] is True


def test_pnl_materialize_failed_terminal_preserves_computed_source_version(tmp_path, monkeypatch):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )
    governance_mod = sys.modules.get("backend.app.repositories.governance_repo")
    if governance_mod is None:
        governance_mod = load_module(
            "backend.app.repositories.governance_repo",
            "backend/app/repositories/governance_repo.py",
        )

    original_append_many_atomic = governance_mod.GovernanceRepository.append_many_atomic

    def fail_completed_terminal_write(self, entries):
        if any(stream == governance_mod.CACHE_MANIFEST_STREAM for stream, _payload in entries):
            raise RuntimeError("completed terminal write failed")
        return original_append_many_atomic(self, entries)

    monkeypatch.setattr(
        governance_mod.GovernanceRepository,
        "append_many_atomic",
        fail_completed_terminal_write,
    )

    governance_dir = tmp_path / "governance"
    with pytest.raises(RuntimeError, match="completed terminal write failed"):
        task_module.materialize_pnl_facts.fn(
            report_date="2025-12-31",
            is_month_end=True,
            fi_rows=[
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "240001.IB",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "invest_type_raw": "TRADING_ASSET",
                    "interest_income_514": "12.50",
                    "fair_value_change_516": "-3.25",
                    "capital_gain_517": "1.75",
                    "manual_adjustment": "0.50",
                    "currency_basis": "CNY",
                    "source_version": "src-v1",
                    "approval_status": "approved",
                    "event_semantics": "realized_incremental",
                    "realized_flag": True,
                }
            ],
            nonstd_rows_by_type={},
            duckdb_path=str(tmp_path / "moss.duckdb"),
            governance_dir=str(governance_dir),
            formal_pnl_enabled=True,
            formal_pnl_scope_json='["*"]',
        )

    build_runs = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [row["status"] for row in build_runs] == ["running", "failed"]
    assert build_runs[-1]["source_version"] == "src-v1"
    assert build_runs[-1]["error_message"] == "completed terminal write failed"


def test_pnl_materialize_task_converts_usd_fi_rows_with_month_end_fx(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fx_daily_mid (
              trade_date varchar,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(24, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              source_version varchar,
              observed_trade_date varchar
            )
            """
        )
        conn.execute(
            """
            insert into fx_daily_mid values
            ('2025-12-31', 'USD', 'CNY', 7.20000000, 'CFETS', true, false, 'sv_fx_usd', '2025-12-31')
            """
        )
    finally:
        conn.close()

    task_module.materialize_pnl_facts.fn(
        report_date="2025-12-31",
        is_month_end=True,
        fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "240002.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "交易性金融资产",
                "interest_income_514": "10.00",
                "fair_value_change_516": "-2.00",
                "capital_gain_517": "1.00",
                "manual_adjustment": "0.50",
                "currency_basis": "CNY",
                "fx_base_currency": "USD",
                "source_version": "src-v-usd",
                "approval_status": "approved",
                "event_semantics": "realized_incremental",
                "realized_flag": True,
            }
        ],
        nonstd_rows_by_type={},
        duckdb_path=str(duckdb_path),
        governance_dir=str(tmp_path / "governance"),
        formal_pnl_enabled=True,
        formal_pnl_scope_json='["*"]',
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        rows = conn.execute(
            """
            select instrument_code, interest_income_514, fair_value_change_516, capital_gain_517,
                   manual_adjustment, total_pnl, source_version
            from fact_formal_pnl_fi
            where report_date = '2025-12-31'
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        (
            "240002.IB",
            Decimal("72.00000000"),
            Decimal("-14.40000000"),
            Decimal("7.20000000"),
            Decimal("3.60000000"),
            Decimal("68.40000000"),
            "src-v-usd__sv_fx_usd",
        )
    ]


def test_pnl_materialize_task_converts_j1_nonstd_rows_with_month_end_fx(tmp_path) -> None:
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fx_daily_mid (
              trade_date varchar,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(24, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              source_version varchar,
              observed_trade_date varchar
            )
            """
        )
        conn.execute(
            """
            insert into fx_daily_mid values
            ('2026-06-30', 'USD', 'CNY', 7.20000000, 'CFETS', true, false, 'sv_fx_usd', '2026-06-30')
            """
        )
    finally:
        conn.close()

    task_module.materialize_pnl_facts.fn(
        report_date="2026-06-30",
        is_month_end=True,
        fi_rows=[],
        nonstd_rows_by_type={
            "514": [
                {
                    "voucher_date": "2026-06-30",
                    "account_code": "51401000004",
                    "asset_code": "J12006190502",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "dc_flag": "贷",
                    "event_type": "interest",
                    "raw_amount": "106.00",
                    "fx_base_currency": "USD",
                    "source_file": "非标514-20260101-0630.xlsx",
                    "source_version": "src-j1",
                },
                {
                    "voucher_date": "2026-06-30",
                    "account_code": "51401000004",
                    "asset_code": "J40001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "dc_flag": "贷",
                    "event_type": "interest",
                    "raw_amount": "106.00",
                    "source_file": "非标514-20260101-0630.xlsx",
                    "source_version": "src-j4",
                },
            ]
        },
        duckdb_path=str(duckdb_path),
        governance_dir=str(tmp_path / "governance"),
        formal_pnl_enabled=True,
        formal_pnl_scope_json='["*"]',
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select bond_code, interest_income_514, total_pnl, source_version
            from fact_nonstd_pnl_bridge
            order by bond_code
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        ("J12006190502", Decimal("763.20000000"), Decimal("763.20000000"), "src-j1__sv_fx_usd"),
        ("J40001", Decimal("106.00000000"), Decimal("106.00000000"), "src-j4"),
    ]


def test_pnl_materialize_task_fails_when_only_prior_business_day_fx_exists(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fx_daily_mid (
              trade_date varchar,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(24, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              source_version varchar,
              observed_trade_date varchar
            )
            """
        )
        conn.execute(
            """
            insert into fx_daily_mid values
            ('2025-12-30', 'USD', 'CNY', 7.10000000, 'CFETS', true, false, 'sv_fx_prev', '2025-12-30')
            """
        )
    finally:
        conn.close()

    with pytest.raises(ValueError, match="Missing formal fx rate"):
        task_module.materialize_pnl_facts.fn(
            report_date="2025-12-31",
            is_month_end=True,
            fi_rows=[
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "240002.IB",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "invest_type_raw": "交易性金融资产",
                    "interest_income_514": "10.00",
                    "fair_value_change_516": "-2.00",
                    "capital_gain_517": "1.00",
                    "manual_adjustment": "0.50",
                    "currency_basis": "CNY",
                    "fx_base_currency": "USD",
                    "source_version": "src-v-usd",
                    "approval_status": "approved",
                    "event_semantics": "realized_incremental",
                    "realized_flag": True,
                }
            ],
            nonstd_rows_by_type={},
            duckdb_path=str(duckdb_path),
            governance_dir=str(tmp_path / "governance"),
            formal_pnl_enabled=True,
            formal_pnl_scope_json='["*"]',
        )


def test_pnl_materialize_task_accepts_weekend_fx_carry_forward(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fx_daily_mid (
              trade_date varchar,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(24, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              source_version varchar,
              observed_trade_date varchar
            )
            """
        )
        conn.execute(
            """
            insert into fx_daily_mid values
            ('2026-01-03', 'USD', 'CNY', 7.10000000, 'CFETS', false, true, 'sv_fx_carry', '2026-01-02')
            """
        )
    finally:
        conn.close()

    task_module.materialize_pnl_facts.fn(
        report_date="2026-01-03",
        is_month_end=True,
        fi_rows=[
            {
                "report_date": "2026-01-03",
                "instrument_code": "240002.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "交易性金融资产",
                "interest_income_514": "10.00",
                "fair_value_change_516": "-2.00",
                "capital_gain_517": "1.00",
                "manual_adjustment": "0.50",
                "currency_basis": "CNY",
                "fx_base_currency": "USD",
                "source_version": "src-v-usd",
                "approval_status": "approved",
                "event_semantics": "realized_incremental",
                "realized_flag": True,
            }
        ],
        nonstd_rows_by_type={},
        duckdb_path=str(duckdb_path),
        governance_dir=str(tmp_path / "governance"),
        formal_pnl_enabled=True,
        formal_pnl_scope_json='["*"]',
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        row = conn.execute(
            """
            select interest_income_514, total_pnl, source_version
            from fact_formal_pnl_fi
            where report_date = '2026-01-03'
            """
        ).fetchone()
    finally:
        conn.close()

    assert row == (
        Decimal("71.00000000"),
        Decimal("67.45000000"),
        "src-v-usd__sv_fx_carry",
    )


def test_pnl_materialize_task_accepts_cfets_currency_holiday_fx_carry_forward(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fx_daily_mid (
              trade_date varchar,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(24, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              source_version varchar,
              observed_trade_date varchar
            )
            """
        )
        conn.execute(
            """
            insert into fx_daily_mid values
            ('2026-01-19', 'USD', 'CNY', 7.10000000, 'CFETS', false, true, 'sv_fx_usd_holiday', '2026-01-16')
            """
        )
    finally:
        conn.close()

    task_module.materialize_pnl_facts.fn(
        report_date="2026-01-19",
        is_month_end=True,
        fi_rows=[
            {
                "report_date": "2026-01-19",
                "instrument_code": "240002.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "TRADING_ASSET",
                "interest_income_514": "10.00",
                "fair_value_change_516": "-2.00",
                "capital_gain_517": "1.00",
                "manual_adjustment": "0.50",
                "currency_basis": "CNY",
                "fx_base_currency": "USD",
                "source_version": "src-v-usd",
                "approval_status": "approved",
                "event_semantics": "realized_incremental",
                "realized_flag": True,
            }
        ],
        nonstd_rows_by_type={},
        duckdb_path=str(duckdb_path),
        governance_dir=str(tmp_path / "governance"),
        formal_pnl_enabled=True,
        formal_pnl_scope_json='["*"]',
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        row = conn.execute(
            """
            select interest_income_514, total_pnl, source_version
            from fact_formal_pnl_fi
            where report_date = '2026-01-19'
            """
        ).fetchone()
    finally:
        conn.close()

    assert row == (
        Decimal("71.00000000"),
        Decimal("67.45000000"),
        "src-v-usd__sv_fx_usd_holiday",
    )


def test_pnl_materialize_task_rejects_business_day_fx_carry_forward(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fx_daily_mid (
              trade_date varchar,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(24, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              source_version varchar,
              observed_trade_date varchar
            )
            """
        )
        conn.execute(
            """
            insert into fx_daily_mid values
            ('2025-12-31', 'USD', 'CNY', 7.10000000, 'CFETS', false, true, 'sv_fx_carry', '2025-12-30')
            """
        )
    finally:
        conn.close()

    with pytest.raises(ValueError, match="carry-forward is only allowed"):
        task_module.materialize_pnl_facts.fn(
            report_date="2025-12-31",
            is_month_end=True,
            fi_rows=[
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "240002.IB",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "invest_type_raw": "TRADING_ASSET",
                    "interest_income_514": "10.00",
                    "fair_value_change_516": "-2.00",
                    "capital_gain_517": "1.00",
                    "manual_adjustment": "0.50",
                    "currency_basis": "CNY",
                    "fx_base_currency": "USD",
                    "source_version": "src-v-usd",
                    "approval_status": "approved",
                    "event_semantics": "realized_incremental",
                    "realized_flag": True,
                }
            ],
            nonstd_rows_by_type={},
            duckdb_path=str(duckdb_path),
            governance_dir=str(tmp_path / "governance"),
            formal_pnl_enabled=True,
            formal_pnl_scope_json='["*"]',
        )


def test_pnl_materialize_task_rejects_contradictory_fx_carry_forward_metadata(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fx_daily_mid (
              trade_date varchar,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(24, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              source_version varchar,
              observed_trade_date varchar
            )
            """
        )
        conn.execute(
            """
            insert into fx_daily_mid values
            ('2025-12-31', 'USD', 'CNY', 7.10000000, 'CFETS', false, true, 'sv_fx_bad', '2025-12-31')
            """
        )
    finally:
        conn.close()

    with pytest.raises(ValueError, match="Invalid formal fx carry-forward metadata"):
        task_module.materialize_pnl_facts.fn(
            report_date="2025-12-31",
            is_month_end=True,
            fi_rows=[
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "240002.IB",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "invest_type_raw": "交易性金融资产",
                    "interest_income_514": "10.00",
                    "fair_value_change_516": "-2.00",
                    "capital_gain_517": "1.00",
                    "manual_adjustment": "0.50",
                    "currency_basis": "CNY",
                    "fx_base_currency": "USD",
                    "source_version": "src-v-usd",
                    "approval_status": "approved",
                    "event_semantics": "realized_incremental",
                    "realized_flag": True,
                }
            ],
            nonstd_rows_by_type={},
            duckdb_path=str(duckdb_path),
            governance_dir=str(tmp_path / "governance"),
            formal_pnl_enabled=True,
            formal_pnl_scope_json='["*"]',
        )


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
        "formal_pnl_enabled": True,
        "formal_pnl_scope_json": '["*"]',
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
                "approval_status": "approved",
                "event_semantics": "realized_incremental",
                "realized_flag": True,
            },
            {
                "report_date": "2025-12-31",
                "instrument_code": "240002.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "交易性金融资产",
                "interest_income_514": "5.00",
                "fair_value_change_516": "0.00",
                "capital_gain_517": "0.00",
                "manual_adjustment": "0.00",
                "currency_basis": "CNY",
                "source_version": "src-v1",
                "approval_status": "approved",
                "event_semantics": "realized_incremental",
                "realized_flag": True,
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
                "approval_status": "approved",
                "event_semantics": "realized_incremental",
                "realized_flag": True,
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


def test_pnl_materialize_task_writes_recognized_formal_totals_not_standardized_totals(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    task_module.materialize_pnl_facts.fn(
        report_date="2025-12-31",
        is_month_end=True,
        fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "AC-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "持有至到期",
                "interest_income_514": "10.00",
                "fair_value_change_516": "5.00",
                "capital_gain_517": "4.00",
                "manual_adjustment": "3.00",
                "currency_basis": "CNY",
                "source_version": "src-recognition",
                "approval_status": "approved",
                "event_semantics": "realized_formal",
                "realized_flag": True,
            },
            {
                "report_date": "2025-12-31",
                "instrument_code": "OCI-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "可供出售",
                "interest_income_514": "10.00",
                "fair_value_change_516": "5.00",
                "capital_gain_517": "4.00",
                "manual_adjustment": "3.00",
                "currency_basis": "CNY",
                "source_version": "src-recognition",
                "governance_status": "pending",
                "event_semantics": "realized_formal",
                "realized_flag": True,
            },
            {
                "report_date": "2025-12-31",
                "instrument_code": "TPL-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "交易性金融资产",
                "interest_income_514": "10.00",
                "fair_value_change_516": "5.00",
                "capital_gain_517": "4.00",
                "manual_adjustment": "3.00",
                "currency_basis": "CNY",
                "source_version": "src-recognition",
                "approval_status": "pending",
                "event_semantics": "mark_to_market",
                "realized_flag": False,
            },
            {
                "report_date": "2025-12-31",
                "instrument_code": "TPL-REALIZED-FORMAL-BUT-OVERLAP-NOT-PROVEN",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "T",
                "interest_income_514": "10.00",
                "fair_value_change_516": "5.00",
                "capital_gain_517": "4.00",
                "manual_adjustment": "3.00",
                "currency_basis": "CNY",
                "source_version": "src-recognition",
                "approval_status": "pending",
                "event_semantics": "realized_formal",
                "realized_flag": True,
            },
            {
                "report_date": "2025-12-31",
                "instrument_code": "TPL-INCREMENTAL",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "T",
                "interest_income_514": "10.00",
                "fair_value_change_516": "5.00",
                "capital_gain_517": "4.00",
                "manual_adjustment": "3.00",
                "currency_basis": "CNY",
                "source_version": "src-recognition",
                "approval_status": "pending",
                "event_semantics": "realized_incremental",
                "realized_flag": True,
            },
        ],
        nonstd_rows_by_type={},
        duckdb_path=str(duckdb_path),
        governance_dir=str(tmp_path / "governance"),
        formal_pnl_enabled=True,
        formal_pnl_scope_json='["*"]',
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        rows = conn.execute(
            """
            select instrument_code, fair_value_change_516, capital_gain_517, manual_adjustment, total_pnl
            from fact_formal_pnl_fi
            order by instrument_code
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        ("AC-001", Decimal("0.00"), Decimal("4.00"), Decimal("3.00"), Decimal("17.00")),
        ("OCI-001", Decimal("0.00"), Decimal("4.00"), Decimal("0.00"), Decimal("14.00")),
        ("TPL-001", Decimal("5.00"), Decimal("0.00"), Decimal("0.00"), Decimal("15.00")),
        (
            "TPL-INCREMENTAL",
            Decimal("5.00"),
            Decimal("4.00"),
            Decimal("0.00"),
            Decimal("19.00"),
        ),
        (
            "TPL-REALIZED-FORMAL-BUT-OVERLAP-NOT-PROVEN",
            Decimal("5.00"),
            Decimal("0.00"),
            Decimal("0.00"),
            Decimal("15.00"),
        ),
    ]


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
            formal_pnl_enabled=True,
            formal_pnl_scope_json='["*"]',
        )


def test_pnl_materialize_task_rejects_formal_fi_rows_when_formal_emission_is_disabled(
    tmp_path,
    monkeypatch,
):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    monkeypatch.setenv("MOSS_FORMAL_PNL_ENABLED", "false")
    get_settings.cache_clear()

    governance_dir = tmp_path / "governance"

    with pytest.raises(RuntimeError, match="Formal pnl emission is disabled"):
        task_module.materialize_pnl_facts.fn(
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
                }
            ],
            nonstd_rows_by_type={},
            duckdb_path=str(tmp_path / "moss.duckdb"),
            governance_dir=str(governance_dir),
        )

    build_runs = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [row["status"] for row in build_runs] == ["running", "failed"]
    assert build_runs[-1]["report_date"] == "2025-12-31"
    assert "Formal pnl emission is disabled" in build_runs[-1]["error_message"]
    get_settings.cache_clear()


def test_pnl_materialize_task_rejects_enabled_formal_fi_rows_without_scope(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    governance_dir = tmp_path / "governance"

    with pytest.raises(RuntimeError, match="Formal pnl scope config is empty"):
        task_module.materialize_pnl_facts.fn(
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
                }
            ],
            nonstd_rows_by_type={},
            duckdb_path=str(tmp_path / "moss.duckdb"),
            governance_dir=str(governance_dir),
            formal_pnl_enabled=True,
            formal_pnl_scope_json="[]",
        )

    build_runs = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [row["status"] for row in build_runs] == ["running", "failed"]
    assert build_runs[-1]["report_date"] == "2025-12-31"
    assert "Formal pnl scope config is empty" in build_runs[-1]["error_message"]


def test_pnl_materialize_task_rejects_settings_enabled_formal_fi_rows_without_scope(
    tmp_path,
    monkeypatch,
):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    monkeypatch.setenv("MOSS_FORMAL_PNL_ENABLED", "true")
    monkeypatch.setenv("MOSS_FORMAL_PNL_SCOPE_JSON", "[]")
    get_settings.cache_clear()

    governance_dir = tmp_path / "governance"

    with pytest.raises(RuntimeError, match="Formal pnl scope config is empty"):
        task_module.materialize_pnl_facts.fn(
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
                }
            ],
            nonstd_rows_by_type={},
            duckdb_path=str(tmp_path / "moss.duckdb"),
            governance_dir=str(governance_dir),
        )

    build_runs = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [row["status"] for row in build_runs] == ["running", "failed"]
    assert build_runs[-1]["report_date"] == "2025-12-31"
    assert "Formal pnl scope config is empty" in build_runs[-1]["error_message"]
    get_settings.cache_clear()


def test_pnl_materialize_task_allows_formal_fi_rows_for_named_scope_token(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

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
                "approval_status": "approved",
                "event_semantics": "realized_formal",
                "realized_flag": True,
            }
        ],
        nonstd_rows_by_type={},
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
        formal_pnl_enabled=True,
        formal_pnl_scope_json='["240001.IB"]',
    )

    assert payload["status"] == "completed"
    assert payload["formal_fi_rows"] == 1


def test_pnl_materialize_task_rejects_formal_fi_rows_outside_named_scope_token(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    with pytest.raises(RuntimeError, match="Formal pnl emission is not enabled for the requested scope"):
        task_module.materialize_pnl_facts.fn(
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
                    "approval_status": "approved",
                    "event_semantics": "realized_formal",
                    "realized_flag": True,
                }
            ],
            nonstd_rows_by_type={},
            duckdb_path=str(tmp_path / "moss.duckdb"),
            governance_dir=str(tmp_path / "governance"),
            formal_pnl_enabled=True,
            formal_pnl_scope_json='["OTHER_SCOPE"]',
        )
