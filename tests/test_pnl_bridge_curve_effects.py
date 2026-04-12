from __future__ import annotations

from decimal import Decimal

import duckdb
import pytest

from backend.app.governance.settings import get_settings
from backend.app.repositories.yield_curve_repo import FORMAL_FACT_TABLE, ensure_yield_curve_tables
from tests.helpers import load_module
from tests.test_pnl_api_contract import (
    _append_manifest_override,
    _materialize_three_pnl_dates,
    _seed_pnl_bridge_balance_rows,
)


def _seed_curve_rows(duckdb_path, rows: list[tuple[object, ...]]) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_yield_curve_tables(conn)
        conn.executemany(
            f"""
            insert into {FORMAL_FACT_TABLE} (
              trade_date, curve_type, tenor, rate_pct, vendor_name, vendor_version, source_version, rule_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    finally:
        conn.close()


def test_pnl_bridge_warns_when_latest_curve_fallback_is_used_and_merges_lineage(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_curve",
        vendor_version="vv_pnl_curve",
        rule_version="rv_pnl_curve",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    _seed_curve_rows(
        duckdb_path,
        [
            ("2025-12-30", "treasury", "1Y", Decimal("2.00"), "akshare", "vv_treasury_latest", "sv_treasury_latest", "rv_curve"),
            ("2025-12-30", "treasury", "2Y", Decimal("3.00"), "akshare", "vv_treasury_latest", "sv_treasury_latest", "rv_curve"),
            ("2025-12-30", "treasury", "3Y", Decimal("4.00"), "akshare", "vv_treasury_latest", "sv_treasury_latest", "rv_curve"),
            ("2025-12-30", "cdb", "1Y", Decimal("2.20"), "choice", "vv_cdb_latest", "sv_cdb_latest", "rv_curve"),
            ("2025-12-30", "cdb", "2Y", Decimal("3.20"), "choice", "vv_cdb_latest", "sv_cdb_latest", "rv_curve"),
            ("2025-12-30", "cdb", "3Y", Decimal("4.20"), "choice", "vv_cdb_latest", "sv_cdb_latest", "rv_curve"),
            ("2025-10-31", "treasury", "1Y", Decimal("1.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
            ("2025-10-31", "treasury", "2Y", Decimal("2.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
            ("2025-10-31", "treasury", "3Y", Decimal("3.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
            ("2025-10-31", "cdb", "1Y", Decimal("1.10"), "choice", "vv_cdb_prior", "sv_cdb_prior", "rv_curve"),
            ("2025-10-31", "cdb", "2Y", Decimal("2.10"), "choice", "vv_cdb_prior", "sv_cdb_prior", "rv_curve"),
            ("2025-10-31", "cdb", "3Y", Decimal("3.10"), "choice", "vv_cdb_prior", "sv_cdb_prior", "rv_curve"),
        ],
    )

    client = load_module("backend.app.main", "backend/app/main.py").app
    from fastapi.testclient import TestClient

    response = TestClient(client).get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    warnings = payload["result"]["warnings"]
    assert any("latest available treasury curve from trade_date=2025-12-30" in warning for warning in warnings)
    assert "sv_treasury_latest" in payload["result_meta"]["source_version"]
    assert "sv_treasury_prior" in payload["result_meta"]["source_version"]
    assert "vv_treasury_latest" in payload["result_meta"]["vendor_version"]
    get_settings.cache_clear()


def test_pnl_bridge_keeps_fresh_metadata_when_missing_credit_curve_is_irrelevant(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_curve",
        vendor_version="vv_pnl_curve",
        rule_version="rv_pnl_curve",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    _seed_curve_rows(
        duckdb_path,
        [
            ("2025-12-31", "treasury", "1Y", Decimal("2.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
            ("2025-12-31", "treasury", "2Y", Decimal("3.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
            ("2025-12-31", "treasury", "3Y", Decimal("4.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
            ("2025-10-31", "treasury", "1Y", Decimal("1.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
            ("2025-10-31", "treasury", "2Y", Decimal("2.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
            ("2025-10-31", "treasury", "3Y", Decimal("3.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
        ],
    )

    from fastapi.testclient import TestClient

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["vendor_status"] == "ok"
    assert payload["result_meta"]["fallback_mode"] == "none"
    assert not any("aaa_credit" in warning for warning in payload["result"]["warnings"])
    get_settings.cache_clear()


def test_pnl_bridge_ignores_corrupt_irrelevant_credit_curve_lineage(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_curve",
        vendor_version="vv_pnl_curve",
        rule_version="rv_pnl_curve",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, invest_type_std,
              accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id, asset_class, bond_type
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("2025-12-31", "CB-IRRELEVANT", "OTHER", "CC999", "A", "OCI", "asset", "CNY", "CNY", "50", "49", "1", False, "sv_irrel", "rv_irrel", "ib_irrel", "tr_irrel", "信用债", "企业债"),
                ("2025-10-31", "CB-IRRELEVANT", "OTHER", "CC999", "A", "OCI", "asset", "CNY", "CNY", "48", "47", "1", False, "sv_irrel", "rv_irrel", "ib_irrel", "tr_irrel", "信用债", "企业债"),
            ],
        )
    finally:
        conn.close()
    _seed_curve_rows(
        duckdb_path,
        [
            ("2025-12-31", "treasury", "1Y", Decimal("2.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
            ("2025-12-31", "treasury", "2Y", Decimal("3.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
            ("2025-12-31", "treasury", "3Y", Decimal("4.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
            ("2025-10-31", "treasury", "1Y", Decimal("1.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
            ("2025-10-31", "treasury", "2Y", Decimal("2.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
            ("2025-10-31", "treasury", "3Y", Decimal("3.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
            ("2025-12-31", "aaa_credit", "1Y", Decimal("4.00"), "choice", "vv_a", "sv_a", "rv_curve"),
            ("2025-12-31", "aaa_credit", "2Y", Decimal("5.00"), "other", "vv_a", "sv_a", "rv_curve"),
        ],
    )

    from fastapi.testclient import TestClient

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["vendor_status"] == "ok"
    assert payload["result_meta"]["fallback_mode"] == "none"
    get_settings.cache_clear()


def test_pnl_bridge_fails_closed_when_same_day_curve_snapshot_lineage_is_corrupt(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_curve",
        vendor_version="vv_pnl_curve",
        rule_version="rv_pnl_curve",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    _seed_curve_rows(
        duckdb_path,
        [
            ("2025-12-31", "treasury", "1Y", Decimal("2.00"), "akshare", "vv_curve", "sv_curve", "rv_curve"),
            ("2025-12-31", "treasury", "2Y", Decimal("3.00"), "choice", "vv_curve", "sv_curve", "rv_curve"),
            ("2025-10-31", "treasury", "1Y", Decimal("1.00"), "akshare", "vv_prior", "sv_prior", "rv_curve"),
            ("2025-10-31", "treasury", "2Y", Decimal("2.00"), "akshare", "vv_prior", "sv_prior", "rv_curve"),
        ],
    )

    service_mod = load_module(
        "backend.app.services.pnl_bridge_service",
        "backend/app/services/pnl_bridge_service.py",
    )

    with pytest.raises(RuntimeError, match="corrupt|inconsistent|lineage"):
        service_mod.pnl_bridge_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date="2025-12-31",
        )
    get_settings.cache_clear()


def test_pnl_bridge_marks_result_meta_unavailable_when_credit_curve_missing(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_curve",
        vendor_version="vv_pnl_curve",
        rule_version="rv_pnl_curve",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )

    from fastapi.testclient import TestClient

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert payload["result_meta"]["fallback_mode"] == "none"
    get_settings.cache_clear()
