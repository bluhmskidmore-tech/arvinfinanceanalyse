"""Verify the formal PnL materialization flow when formal_pnl_enabled=True."""

from __future__ import annotations

import json
from decimal import Decimal

import duckdb
import pytest

from backend.app.governance.settings import get_settings
from backend.app.tasks.pnl_materialize import run_pnl_materialize_sync


def _minimal_fi_row(*, instrument_code: str = "240001.IB", portfolio_name: str = "Portfolio A") -> dict[str, object]:
    return {
        "report_date": "2025-12-31",
        "instrument_code": instrument_code,
        "portfolio_name": portfolio_name,
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
        "event_semantics": "realized_formal",
        "realized_flag": True,
    }


def _minimal_nonstd_rows() -> dict[str, list[dict[str, object]]]:
    return {
        "516": [
            {
                "voucher_date": "2025-12-30",
                "account_code": "51601010004",
                "asset_code": "BOND-001",
                "portfolio_name": "Portfolio A",
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
        ]
    }


def test_formal_pnl_materialize_succeeds_when_enabled(tmp_path, monkeypatch):
    """With formal_pnl_enabled=True and scope='*', materialization should
    write rows to fact_formal_pnl_fi and fact_nonstd_pnl_bridge."""
    monkeypatch.setenv("MOSS_FORMAL_PNL_ENABLED", "true")
    monkeypatch.setenv("MOSS_FORMAL_PNL_SCOPE_JSON", '["*"]')
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "test.duckdb"))
    monkeypatch.setenv("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", "1")
    get_settings.cache_clear()

    duckdb_path = tmp_path / "test.duckdb"
    governance_dir = tmp_path / "governance"

    payload = run_pnl_materialize_sync(
        report_date="2025-12-31",
        is_month_end=True,
        fi_rows=[_minimal_fi_row()],
        nonstd_rows_by_type=_minimal_nonstd_rows(),
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        fi_count = conn.execute("select count(*) from fact_formal_pnl_fi").fetchone()[0]
        bridge_count = conn.execute("select count(*) from fact_nonstd_pnl_bridge").fetchone()[0]
        fi_total = conn.execute("select total_pnl from fact_formal_pnl_fi limit 1").fetchone()[0]
    finally:
        conn.close()

    assert int(fi_count) >= 1
    assert int(bridge_count) >= 1
    assert fi_total == Decimal("11.50")

    manifests = [
        json.loads(line)
        for line in (governance_dir / "cache_manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert manifests[-1]["cache_key"] == payload["cache_key"]
    assert manifests[-1]["source_version"] == payload["source_version"]

    get_settings.cache_clear()


def test_formal_pnl_materialize_respects_scope_restriction(tmp_path, monkeypatch):
    """With a restricted scope, only allowed portfolios should pass the gate."""
    monkeypatch.setenv("MOSS_FORMAL_PNL_ENABLED", "true")
    monkeypatch.setenv("MOSS_FORMAL_PNL_SCOPE_JSON", '["Portfolio A"]')
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "test.duckdb"))
    monkeypatch.setenv("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", "1")
    get_settings.cache_clear()

    row_a = _minimal_fi_row(portfolio_name="Portfolio A")
    row_b = _minimal_fi_row(instrument_code="240002.IB", portfolio_name="Portfolio B")

    with pytest.raises(RuntimeError, match="Formal pnl emission is not enabled for the requested scope"):
        run_pnl_materialize_sync(
            report_date="2025-12-31",
            is_month_end=True,
            fi_rows=[row_a, row_b],
            nonstd_rows_by_type={},
            duckdb_path=str(tmp_path / "test.duckdb"),
            governance_dir=str(tmp_path / "governance"),
        )

    get_settings.cache_clear()


def test_formal_pnl_can_be_disabled_via_env(tmp_path, monkeypatch):
    """Even with default True, env override to False should block emission."""
    monkeypatch.setenv("MOSS_FORMAL_PNL_ENABLED", "false")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "test.duckdb"))
    monkeypatch.setenv("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", "1")
    get_settings.cache_clear()

    governance_dir = tmp_path / "governance"

    with pytest.raises(RuntimeError, match="Formal pnl emission is disabled"):
        run_pnl_materialize_sync(
            report_date="2025-12-31",
            is_month_end=True,
            fi_rows=[_minimal_fi_row()],
            nonstd_rows_by_type={},
            duckdb_path=str(tmp_path / "test.duckdb"),
            governance_dir=str(governance_dir),
        )

    get_settings.cache_clear()
