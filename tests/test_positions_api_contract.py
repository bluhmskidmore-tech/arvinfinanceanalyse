"""Contract tests for positions HTTP API (envelope + snapshot read behaviors)."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

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
    issuer_name: str,
    market_value: Decimal,
    ytm: Decimal,
    coupon: Decimal,
    is_issuance_like: bool,
    face_value: Decimal | None = None,
    amortized_cost: Decimal | None = None,
    rating: str = "AAA",
    industry: str = "閾惰",
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
            "bond-asset-class",
            bond_type,
            issuer_name,
            industry,
            rating,
            "CNY",
            face_value if face_value is not None else market_value,
            market_value,
            amortized_cost if amortized_cost is not None else market_value,
            Decimal("0"),
            coupon,
            ytm,
            "2030-01-01",
            None,
            0,
            is_issuance_like,
            "鍥哄畾",
            "sv-pos-test",
            "rv-pos-test",
            "ib-pos",
            "tr-pos",
        ],
    )


def _insert_tyw(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    position_id: str,
    product_type: str,
    position_side: str,
    counterparty: str,
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
            counterparty,
            "a",
            "s",
            "c",
            "CNY",
            principal,
            Decimal("0"),
            rate,
            "2030-06-01",
            None,
            "sv-pos-tyw",
            "rv-pos-test",
            "ib-pos-t",
            "tr-pos-t",
        ],
    )


def _seed_positions_db(path: Path) -> None:
    conn = duckdb.connect(str(path), read_only=False)
    try:
        _ensure_tables(conn)
        conn.execute("delete from zqtz_bond_daily_snapshot")
        conn.execute("delete from tyw_interbank_daily_snapshot")
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="B001",
            bond_type="GOV",
            issuer_name="鍙戣浜虹敳",
            market_value=Decimal("100"),
            ytm=Decimal("0.03"),
            coupon=Decimal("0.025"),
            is_issuance_like=False,
        )
        _insert_zqtz(
            conn,
            report_date="2026-01-12",
            instrument_code="B001",
            bond_type="GOV",
            issuer_name="鍙戣浜虹敳",
            market_value=Decimal("120"),
            ytm=Decimal("0.031"),
            coupon=Decimal("0.025"),
            is_issuance_like=False,
        )
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="B002",
            bond_type="CREDIT",
            issuer_name="鍙戣浜轰箼",
            market_value=Decimal("200"),
            ytm=Decimal("0.04"),
            coupon=Decimal("0.035"),
            is_issuance_like=True,
        )
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="B003",
            bond_type="CREDIT",
            issuer_name="鍙戣浜轰箼",
            market_value=Decimal("50"),
            ytm=Decimal("0.045"),
            coupon=Decimal("0.04"),
            is_issuance_like=False,
        )
        _insert_tyw(
            conn,
            report_date="2026-01-10",
            position_id="T1",
            product_type="REPO",
            position_side="Asset",
            counterparty="CP_ASSET",
            principal=Decimal("1000"),
            rate=Decimal("0.02"),
        )
        _insert_tyw(
            conn,
            report_date="2026-01-12",
            position_id="T2",
            product_type="REPO",
            position_side="Liability",
            counterparty="CP_LIAB",
            principal=Decimal("500"),
            rate=Decimal("0.025"),
        )
    finally:
        conn.close()


def _assert_envelope(payload: dict[str, Any], *, result_kind: str) -> None:
    assert "result_meta" in payload
    assert "result" in payload
    meta = payload["result_meta"]
    for key in ("trace_id", "basis", "source_version", "rule_version", "cache_version", "result_kind"):
        assert key in meta, f"result_meta missing {key!r}"
        assert meta[key] not in (None, ""), f"result_meta.{key} must be non-empty"
    assert meta["basis"] == "formal"
    assert meta["result_kind"] == result_kind


def test_positions_endpoints_envelope_and_empty_db(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    r = client.get("/api/positions/bonds/sub_types", params={"report_date": "2026-01-10"})
    assert r.status_code == 200
    _assert_envelope(r.json(), result_kind="positions.bonds.sub_types")
    assert r.json()["result"]["sub_types"] == []

    r2 = client.get(
        "/api/positions/bonds",
        params={"report_date": "2026-01-10", "sub_type": "GOV", "page": 1, "page_size": 10},
    )
    assert r2.status_code == 200
    _assert_envelope(r2.json(), result_kind="positions.bonds.list")
    assert r2.json()["result"]["items"] == []
    assert r2.json()["result"]["total"] == 0


def test_positions_bonds_filters_issuance_and_pagination(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos.duckdb"
    _seed_positions_db(db)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    sub = client.get("/api/positions/bonds/sub_types", params={"report_date": "2026-01-10"})
    assert sub.status_code == 200
    assert set(sub.json()["result"]["sub_types"]) == {"GOV", "CREDIT"}

    with_issued = client.get(
        "/api/positions/bonds",
        params={
            "report_date": "2026-01-10",
            "sub_type": "CREDIT",
            "page": 1,
            "page_size": 10,
            "include_issued": "true",
        },
    )
    assert with_issued.status_code == 200
    assert with_issued.json()["result"]["total"] == 2

    no_issued = client.get(
        "/api/positions/bonds",
        params={
            "report_date": "2026-01-10",
            "sub_type": "CREDIT",
            "page": 1,
            "page_size": 10,
        },
    )
    assert no_issued.status_code == 200
    assert no_issued.json()["result"]["total"] == 1
    assert no_issued.json()["result"]["items"][0]["bond_code"] == "B003"

    page2 = client.get(
        "/api/positions/bonds",
        params={
            "report_date": "2026-01-10",
            "sub_type": "GOV",
            "page": 2,
            "page_size": 1,
        },
    )
    assert page2.status_code == 200
    assert page2.json()["result"]["total"] == 1
    assert page2.json()["result"]["items"] == []


def test_positions_counterparty_and_interbank(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos.duckdb"
    _seed_positions_db(db)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    cp = client.get(
        "/api/positions/counterparty/bonds",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "sub_type": "GOV",
            "top_n": 10,
            "page": 1,
            "page_size": 10,
        },
    )
    assert cp.status_code == 200
    _assert_envelope(cp.json(), result_kind="positions.counterparty.bonds")
    body = cp.json()["result"]
    assert body["num_days"] == 2
    assert body["total_customers"] == 1
    assert len(body["items"]) == 1

    pt = client.get("/api/positions/interbank/product_types", params={"report_date": "2026-01-10"})
    assert pt.status_code == 200
    assert pt.json()["result"]["product_types"] == ["REPO"]

    ib = client.get(
        "/api/positions/interbank",
        params={
            "report_date": "2026-01-10",
            "product_type": "REPO",
            "direction": "Asset",
            "page": 1,
            "page_size": 10,
        },
    )
    assert ib.status_code == 200
    assert ib.json()["result"]["total"] == 1
    assert ib.json()["result"]["items"][0]["direction"] == "Asset"

    split = client.get(
        "/api/positions/counterparty/interbank/split",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31", "product_type": "REPO"},
    )
    assert split.status_code == 200
    sp = split.json()["result"]
    assert sp["num_days"] == 2
    assert len(sp["asset_items"]) >= 1
    assert len(sp["liability_items"]) >= 1


def test_positions_counterparty_bonds_excludes_issuance_like_from_asset_scope(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos.duckdb"
    _seed_positions_db(db)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    cp = client.get(
        "/api/positions/counterparty/bonds",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "top_n": 10,
            "page": 1,
            "page_size": 10,
        },
    )
    assert cp.status_code == 200
    body = cp.json()["result"]

    assert body["total_amount"] == "270.00000000"
    assert body["total_avg_daily"] == "135.00000000"
    assert body["total_customers"] == 2
    items_by_customer = {item["customer_name"]: item for item in body["items"]}
    assert set(items_by_customer) == {"鍙戣浜虹敳", "鍙戣浜轰箼"}
    assert items_by_customer["鍙戣浜虹敳"]["total_amount"] == "220.00000000"
    assert items_by_customer["鍙戣浜轰箼"]["total_amount"] == "50.00000000"
    assert items_by_customer["鍙戣浜轰箼"]["avg_daily_balance"] == "25.00000000"


def test_positions_stats_rating_industry_customer(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos.duckdb"
    _seed_positions_db(db)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    rt = client.get(
        "/api/positions/stats/rating",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31", "sub_type": "CREDIT"},
    )
    assert rt.status_code == 200
    assert rt.json()["result"]["items"]

    ind = client.get(
        "/api/positions/stats/industry",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31", "top_n": 5},
    )
    assert ind.status_code == 200
    assert ind.json()["result"]["items"]

    det = client.get(
        "/api/positions/customer/details",
        params={"customer_name": "鍙戣浜轰箼", "report_date": "2026-01-10"},
    )
    assert det.status_code == 200
    assert det.json()["result"]["bond_count"] == 2

    tr = client.get(
        "/api/positions/customer/trend",
        params={"customer_name": "鍙戣浜虹敳", "end_date": "2026-01-12", "days": 30},
    )
    assert tr.status_code == 200
    assert len(tr.json()["result"]["items"]) == 2



def test_positions_rating_and_industry_stats_exclude_issuance_like_from_asset_scope(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    try:
        _ensure_tables(conn)
        conn.execute("delete from zqtz_bond_daily_snapshot")
        conn.execute("delete from tyw_interbank_daily_snapshot")
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="A001",
            bond_type="TEST",
            issuer_name="Issuer-Asset",
            market_value=Decimal("100"),
            ytm=Decimal("0.03"),
            coupon=Decimal("0.02"),
            is_issuance_like=False,
            rating="AAA",
            industry="Bank",
        )
        _insert_zqtz(
            conn,
            report_date="2026-01-11",
            instrument_code="A001",
            bond_type="TEST",
            issuer_name="Issuer-Asset",
            market_value=Decimal("120"),
            ytm=Decimal("0.031"),
            coupon=Decimal("0.02"),
            is_issuance_like=False,
            rating="AAA",
            industry="Bank",
        )
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="L001",
            bond_type="TEST",
            issuer_name="Issuer-Liability",
            market_value=Decimal("200"),
            ytm=Decimal("0.08"),
            coupon=Decimal("0.07"),
            is_issuance_like=True,
            rating="BBB",
            industry="Broker",
        )
    finally:
        conn.close()
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    rating = client.get(
        "/api/positions/stats/rating",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31", "sub_type": "TEST"},
    )
    assert rating.status_code == 200
    rating_body = rating.json()["result"]
    assert rating_body["total_amount"] == "220.00000000"
    assert rating_body["total_avg_daily"] == "110.00000000"
    assert [item["rating"] for item in rating_body["items"]] == ["AAA"]
    assert rating_body["items"][0]["bond_count"] == 2

    industry = client.get(
        "/api/positions/stats/industry",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31", "sub_type": "TEST", "top_n": 5},
    )
    assert industry.status_code == 200
    industry_body = industry.json()["result"]
    assert industry_body["total_amount"] == "220.00000000"
    assert industry_body["total_avg_daily"] == "110.00000000"
    items_by_industry = {item["industry"]: item for item in industry_body["items"]}
    assert set(items_by_industry) == {"Bank"}
    assert items_by_industry["Bank"]["bond_count"] == 2

def test_positions_routes_registered() -> None:
    from backend.app.main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/positions/bonds/sub_types" in paths
    assert "/api/positions/bonds" in paths
    assert "/api/positions/counterparty/bonds" in paths
    assert "/api/positions/interbank/product_types" in paths
    assert "/api/positions/interbank" in paths
    assert "/api/positions/counterparty/interbank/split" in paths
    assert "/api/positions/stats/rating" in paths
    assert "/api/positions/stats/industry" in paths
    assert "/api/positions/customer/details" in paths
    assert "/api/positions/customer/trend" in paths

def test_positions_rating_order_follows_business_priority_not_amount_order(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    try:
        _ensure_tables(conn)
        conn.execute("delete from zqtz_bond_daily_snapshot")
        conn.execute("delete from tyw_interbank_daily_snapshot")
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="R1",
            bond_type="Credit",
            issuer_name="Issuer-AAA",
            market_value=Decimal("10"),
            ytm=Decimal("0.03"),
            coupon=Decimal("0.03"),
            is_issuance_like=False,
            rating="AAA",
        )
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="R2",
            bond_type="Credit",
            issuer_name="Issuer-AA",
            market_value=Decimal("200"),
            ytm=Decimal("0.04"),
            coupon=Decimal("0.04"),
            is_issuance_like=False,
            rating="AA",
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get(
        "/api/positions/stats/rating",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31", "sub_type": "Credit"},
    )
    assert response.status_code == 200
    items = response.json()["result"]["items"]
    assert [item["rating"] for item in items] == ["AAA", "AA"]


def test_positions_reads_normalize_percentage_rates_and_compute_net_price_from_market_over_face(
    tmp_path,
    monkeypatch,
) -> None:
    db = tmp_path / "pos.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    try:
        _ensure_tables(conn)
        conn.execute("delete from zqtz_bond_daily_snapshot")
        conn.execute("delete from tyw_interbank_daily_snapshot")
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="PX1",
            bond_type="Gov",
            issuer_name="Issuer-Gov",
            market_value=Decimal("120"),
            face_value=Decimal("100"),
            amortized_cost=Decimal("80"),
            ytm=Decimal("3.25"),
            coupon=Decimal("2.50"),
            is_issuance_like=False,
        )
        _insert_tyw(
            conn,
            report_date="2026-01-10",
            position_id="T100",
            product_type="IB",
            position_side="Asset",
            counterparty="CP-A",
            principal=Decimal("1000"),
            rate=Decimal("2.5"),
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    bond_response = client.get(
        "/api/positions/bonds",
        params={"report_date": "2026-01-10", "sub_type": "Gov", "page": 1, "page_size": 10},
    )
    assert bond_response.status_code == 200
    bond_item = bond_response.json()["result"]["items"][0]
    assert bond_item["yield_rate"] == "0.03250000"
    assert bond_item["valuation_net_price"] == "120.00000000"

    ib_response = client.get(
        "/api/positions/interbank",
        params={
            "report_date": "2026-01-10",
            "product_type": "IB",
            "direction": "Asset",
            "page": 1,
            "page_size": 10,
        },
    )
    assert ib_response.status_code == 200
    ib_item = ib_response.json()["result"]["items"][0]
    assert ib_item["interest_rate"] == "0.02500000"


def test_positions_optional_report_date_routes_fall_back_to_latest_snapshot_date(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos.duckdb"
    _seed_positions_db(db)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    subtypes = client.get("/api/positions/bonds/sub_types")
    assert subtypes.status_code == 200
    assert subtypes.json()["result"]["sub_types"] == ["GOV"]

    details = client.get(
        "/api/positions/customer/details",
        params={"customer_name": "鍙戣浜虹敳"},
    )
    assert details.status_code == 200
    assert details.json()["result"]["report_date"] == "2026-01-12"
    assert details.json()["result"]["bond_count"] == 1

