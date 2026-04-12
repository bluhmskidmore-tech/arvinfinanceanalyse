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
    assert any("latest available cdb curve from trade_date=2025-12-30" in warning for warning in warnings)
    assert "sv_treasury_latest" in payload["result_meta"]["source_version"]
    assert "sv_treasury_prior" in payload["result_meta"]["source_version"]
    assert "sv_cdb_latest" in payload["result_meta"]["source_version"]
    assert "sv_cdb_prior" in payload["result_meta"]["source_version"]
    assert "vv_treasury_latest" in payload["result_meta"]["vendor_version"]
    assert "vv_cdb_latest" in payload["result_meta"]["vendor_version"]
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
