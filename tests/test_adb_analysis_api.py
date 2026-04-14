"""Contract tests for ADB (/api/analysis/adb*) — DuckDB 读模型与 V1 口径对齐。"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import duckdb
from fastapi.testclient import TestClient

from tests.helpers import load_module


def _ensure_tables(conn: duckdb.DuckDBPyConnection) -> None:
    snapshot_mod = load_module(
        "backend.app.repositories.snapshot_repo",
        "backend/app/repositories/snapshot_repo.py",
    )
    snapshot_mod.ensure_snapshot_tables(conn)


def _insert_zqtz(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    instrument_code: str,
    bond_type: str,
    market_value: Decimal,
    is_issuance_like: bool,
) -> None:
    conn.execute(
        """
        insert into zqtz_bond_daily_snapshot (
          report_date, instrument_code, instrument_name, portfolio_name, cost_center,
          account_category, asset_class, bond_type, issuer_name, industry_name, rating,
          currency_code, face_value_native, market_value_native, amortized_cost_native,
          accrued_interest_native, coupon_rate, ytm_value, maturity_date, next_call_date,
          overdue_days, is_issuance_like, interest_mode, source_version, rule_version,
          ingest_batch_id, trace_id
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            report_date,
            instrument_code,
            instrument_code,
            "p1",
            "cc1",
            "cat",
            "债券类",
            bond_type,
            "issuer-x",
            "银行",
            "AAA",
            "CNY",
            market_value,
            market_value,
            market_value,
            Decimal("0"),
            Decimal("0.03"),
            Decimal("0.035"),
            "2030-01-01",
            None,
            0,
            is_issuance_like,
            "固定",
            "sv-adb",
            "rv-adb",
            "ib-adb",
            "tr-adb",
        ],
    )


def _insert_tyw(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    position_id: str,
    product_type: str,
    position_side: str,
    principal: Decimal,
    rate: Decimal,
) -> None:
    conn.execute(
        """
        insert into tyw_interbank_daily_snapshot (
          report_date, position_id, product_type, position_side, counterparty_name,
          account_type, special_account_type, core_customer_type, currency_code,
          principal_native, accrued_interest_native, funding_cost_rate, maturity_date,
          pledged_bond_code, source_version, rule_version, ingest_batch_id, trace_id
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            report_date,
            position_id,
            product_type,
            position_side,
            "cp",
            "acct",
            None,
            None,
            "CNY",
            principal,
            Decimal("0"),
            rate,
            "2030-01-01",
            None,
            "sv-adb",
            "rv-adb",
            "ib-adb",
            "tr-adb",
        ],
    )


def test_adb_endpoints_return_structure(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "adb.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        _insert_zqtz(
            conn,
            report_date="2025-06-02",
            instrument_code="B1",
            bond_type="国债",
            market_value=Decimal("100000000"),
            is_issuance_like=False,
        )
        _insert_zqtz(
            conn,
            report_date="2025-06-03",
            instrument_code="B1",
            bond_type="国债",
            market_value=Decimal("200000000"),
            is_issuance_like=False,
        )
        _insert_tyw(
            conn,
            report_date="2025-06-03",
            position_id="T1",
            product_type="拆放同业",
            position_side="资产",
            principal=Decimal("50000000"),
            rate=Decimal("2.5"),
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db_path))
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_mod.app)

    r = client.get("/api/analysis/adb", params={"start_date": "2025-06-02", "end_date": "2025-06-03"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "summary" in body and "trend" in body and "breakdown" in body
    assert body["summary"]["total_avg_assets"] > 0

    c = client.get(
        "/api/analysis/adb-comparison",
        params={"start_date": "2025-06-02", "end_date": "2025-06-03", "top_n": 5},
    )
    assert c.status_code == 200, c.text
    cmp = c.json()
    assert cmp["num_days"] == 2
    assert "assets" in cmp and isinstance(cmp["assets"], list)
    assert cmp["report_date"] == "2025-06-03"
    assert "assets_breakdown" in cmp and isinstance(cmp["assets_breakdown"], list)
    assert "liabilities_breakdown" in cmp and isinstance(cmp["liabilities_breakdown"], list)
    assert "total_spot_assets" in cmp
    assert "total_avg_assets" in cmp
    assert "asset_yield" in cmp
    assert "liability_cost" in cmp
    assert "net_interest_margin" in cmp

    c_alias = client.get(
        "/api/analysis/adb/comparison",
        params={"start_date": "2025-06-02", "end_date": "2025-06-03", "top_n": 5},
    )
    assert c_alias.status_code == 200, c_alias.text
    cmp_alias = c_alias.json()
    assert cmp_alias["report_date"] == cmp["report_date"]
    assert cmp_alias["total_spot_assets"] == cmp["total_spot_assets"]
    assert cmp_alias["total_avg_assets"] == cmp["total_avg_assets"]

    m = client.get("/api/analysis/adb/monthly", params={"year": 2025})
    assert m.status_code == 200, m.text
    mon = m.json()
    assert mon["year"] == 2025
    assert "months" in mon and "ytd_avg_assets" in mon
