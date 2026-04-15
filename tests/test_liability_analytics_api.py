# -*- coding: utf-8 -*-
"""Contract tests for liability analytics V1-compatible payloads inside governed envelopes."""

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
    instrument_name: str,
    bond_type: str,
    amount: Decimal,
    is_issuance_like: bool,
    coupon_rate: Decimal,
    ytm_value: Decimal,
    maturity_date: str,
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
            instrument_name,
            "p1",
            "cc1",
            "cat",
            "债券类",
            bond_type,
            "issuer-x",
            "银行",
            "AAA",
            "CNY",
            amount,
            amount,
            amount,
            Decimal("0"),
            coupon_rate,
            ytm_value,
            maturity_date,
            None,
            0,
            is_issuance_like,
            "固定",
            "sv-liab",
            "rv-liab",
            "ib-liab",
            "tr-liab",
        ],
    )


def _insert_tyw(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    position_id: str,
    product_type: str,
    position_side: str,
    counterparty_name: str,
    principal: Decimal,
    funding_cost_rate_percent: Decimal,
    maturity_date: str,
    core_customer_type: str | None = None,
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
            counterparty_name,
            "acct",
            None,
            core_customer_type,
            "CNY",
            principal,
            Decimal("0"),
            funding_cost_rate_percent,
            maturity_date,
            None,
            "sv-liab",
            "rv-liab",
            "ib-liab",
            "tr-liab",
        ],
    )


def _assert_close(actual: float | None, expected: float, tolerance: float = 1e-9) -> None:
    assert actual is not None
    assert abs(actual - expected) <= tolerance


def _build_client(db_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db_path))
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    return TestClient(main_mod.app)


def _unwrap_liability_envelope(body: dict[str, object], *, result_kind: str) -> dict[str, object]:
    assert "result_meta" in body
    assert "result" in body
    meta = body["result_meta"]
    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False
    assert meta["scenario_flag"] is False
    assert meta["result_kind"] == result_kind
    return body["result"]


def test_liability_analytics_v1_compatible_endpoints(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "liability.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)

        _insert_zqtz(
            conn,
            report_date="2026-01-31",
            instrument_code="A1",
            instrument_name="国债A1",
            bond_type="国债",
            amount=Decimal("300000000"),
            is_issuance_like=False,
            coupon_rate=Decimal("0.030"),
            ytm_value=Decimal("0.035"),
            maturity_date="2028-01-01",
        )
        conn.execute(
            "update zqtz_bond_daily_snapshot set asset_class = ? where report_date = ? and instrument_code = ?",
            ["可供出售金融资产", "2026-01-31", "A1"],
        )
        _insert_zqtz(
            conn,
            report_date="2026-01-31",
            instrument_code="L1",
            instrument_name="同业存单L1",
            bond_type="同业存单",
            amount=Decimal("300000000"),
            is_issuance_like=True,
            coupon_rate=Decimal("0.022"),
            ytm_value=Decimal("0.022"),
            maturity_date="2026-10-01",
        )
        _insert_tyw(
            conn,
            report_date="2026-01-31",
            position_id="TA1",
            product_type="拆放同业",
            position_side="asset",
            counterparty_name="同业资产A",
            principal=Decimal("200000000"),
            funding_cost_rate_percent=Decimal("2.0"),
            maturity_date="2026-05-01",
        )
        _insert_tyw(
            conn,
            report_date="2026-01-31",
            position_id="TL1",
            product_type="同业拆入",
            position_side="liability",
            counterparty_name="银行A",
            principal=Decimal("400000000"),
            funding_cost_rate_percent=Decimal("2.5"),
            maturity_date="2026-04-01",
            core_customer_type="银行",
        )
        _insert_tyw(
            conn,
            report_date="2026-01-31",
            position_id="TL2",
            product_type="同业拆入",
            position_side="liability",
            counterparty_name="基金公司B",
            principal=Decimal("100000000"),
            funding_cost_rate_percent=Decimal("3.0"),
            maturity_date="2026-06-01",
            core_customer_type="基金",
        )
        _insert_tyw(
            conn,
            report_date="2026-01-31",
            position_id="TL3",
            product_type="同业拆入",
            position_side="liability",
            counterparty_name="青岛银行股份有限公司",
            principal=Decimal("50000000"),
            funding_cost_rate_percent=Decimal("1.8"),
            maturity_date="2026-03-01",
            core_customer_type="银行",
        )

        _insert_zqtz(
            conn,
            report_date="2026-01-30",
            instrument_code="L0",
            instrument_name="同业存单L0",
            bond_type="同业存单",
            amount=Decimal("100000000"),
            is_issuance_like=True,
            coupon_rate=Decimal("0.020"),
            ytm_value=Decimal("0.020"),
            maturity_date="2026-08-01",
        )
        _insert_tyw(
            conn,
            report_date="2026-01-30",
            position_id="TL0A",
            product_type="同业拆入",
            position_side="liability",
            counterparty_name="银行A",
            principal=Decimal("300000000"),
            funding_cost_rate_percent=Decimal("2.4"),
            maturity_date="2026-02-20",
            core_customer_type="银行",
        )
        _insert_tyw(
            conn,
            report_date="2026-01-30",
            position_id="TL0B",
            product_type="同业拆入",
            position_side="liability",
            counterparty_name="基金公司B",
            principal=Decimal("100000000"),
            funding_cost_rate_percent=Decimal("3.0"),
            maturity_date="2026-03-20",
            core_customer_type="基金",
        )
    finally:
        conn.close()

    client = _build_client(db_path, monkeypatch)

    risk = client.get("/api/risk/buckets", params={"report_date": "2026-01-31"})
    assert risk.status_code == 200, risk.text
    risk_payload = _unwrap_liability_envelope(
        risk.json(),
        result_kind="liability_analytics.risk_buckets",
    )
    totals = {item["name"]: item["amount"] for item in risk_payload["liabilities_structure"]}
    _assert_close(totals["同业负债"], 550000000.0)
    _assert_close(totals["发行负债"], 300000000.0)

    yld = client.get("/api/analysis/yield_metrics", params={"report_date": "2026-01-31"})
    assert yld.status_code == 200, yld.text
    yld_payload = _unwrap_liability_envelope(
        yld.json(),
        result_kind="liability_analytics.yield_metrics",
    )
    _assert_close(yld_payload["kpi"]["asset_yield"], 0.029)
    _assert_close(yld_payload["kpi"]["market_liability_cost"], 0.02411764705882353)
    _assert_close(yld_payload["kpi"]["nim"], 0.004882352941176468)

    cp = client.get(
        "/api/analysis/liabilities/counterparty",
        params={"report_date": "2026-01-31", "top_n": 2000},
    )
    assert cp.status_code == 200, cp.text
    cp_payload = _unwrap_liability_envelope(
        cp.json(),
        result_kind="liability_analytics.counterparty",
    )
    _assert_close(cp_payload["total_value"], 500000000.0)
    assert [row["name"] for row in cp_payload["top_10"]] == ["银行A", "基金公司B"]
    by_type = {item["name"]: item["value"] for item in cp_payload["by_type"]}
    _assert_close(by_type["Bank"], 400000000.0)
    _assert_close(by_type["Non-Bank FI"], 100000000.0)


def test_liability_counterparty_uses_v1_type_labels_and_contains_based_self_exclusion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "liability-counterparty-types.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        _insert_tyw(
            conn,
            report_date="2026-02-26",
            position_id="TL-BANK",
            product_type="同业拆入",
            position_side="liability",
            counterparty_name="中国农业银行股份有限公司",
            principal=Decimal("100000000"),
            funding_cost_rate_percent=Decimal("1.5"),
            maturity_date="2026-03-26",
            core_customer_type="银行",
        )
        _insert_tyw(
            conn,
            report_date="2026-02-26",
            position_id="TL-FUND",
            product_type="同业拆入",
            position_side="liability",
            counterparty_name="青银理财有限责任公司",
            principal=Decimal("80000000"),
            funding_cost_rate_percent=Decimal("1.4"),
            maturity_date="2026-03-26",
            core_customer_type="理财",
        )
        _insert_tyw(
            conn,
            report_date="2026-02-26",
            position_id="TL-CORP",
            product_type="同业拆入",
            position_side="liability",
            counterparty_name="山东港口集团财务有限责任公司",
            principal=Decimal("70000000"),
            funding_cost_rate_percent=Decimal("1.3"),
            maturity_date="2026-03-26",
            core_customer_type="财务公司",
        )
        _insert_tyw(
            conn,
            report_date="2026-02-26",
            position_id="TL-SELF",
            product_type="同业拆入",
            position_side="liability",
            counterparty_name="中国银行股份有限公司青岛银行合作部",
            principal=Decimal("60000000"),
            funding_cost_rate_percent=Decimal("1.2"),
            maturity_date="2026-03-26",
            core_customer_type="银行",
        )
    finally:
        conn.close()

    client = _build_client(db_path, monkeypatch)
    response = client.get(
        "/api/analysis/liabilities/counterparty",
        params={"report_date": "2026-02-26", "top_n": 2000},
    )
    assert response.status_code == 200, response.text
    payload = _unwrap_liability_envelope(
        response.json(),
        result_kind="liability_analytics.counterparty",
    )

    top_map = {item["name"]: item for item in payload["top_10"]}
    assert top_map["中国农业银行股份有限公司"]["type"] == "Bank"
    assert top_map["青银理财有限责任公司"]["type"] == "Non-Bank FI"
    assert top_map["山东港口集团财务有限责任公司"]["type"] == "Corporate/Other"
    assert "中国银行股份有限公司青岛银行合作部" not in top_map

    by_type = {item["name"]: item["value"] for item in payload["by_type"]}
    _assert_close(by_type["Bank"], 100000000.0)
    _assert_close(by_type["Non-Bank FI"], 80000000.0)
    _assert_close(by_type["Corporate/Other"], 70000000.0)


def test_liability_yield_metrics_normalizes_percentage_style_bond_rates(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "liability-rates.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        _insert_zqtz(
            conn,
            report_date="2026-02-26",
            instrument_code="A1",
            instrument_name="国债A1",
            bond_type="国债",
            amount=Decimal("100000000"),
            is_issuance_like=False,
            coupon_rate=Decimal("2.5"),
            ytm_value=Decimal("2.4"),
            maturity_date="2027-02-26",
        )
        conn.execute(
            "update zqtz_bond_daily_snapshot set asset_class = ? where report_date = ? and instrument_code = ?",
            ["可供出售金融资产", "2026-02-26", "A1"],
        )
        _insert_zqtz(
            conn,
            report_date="2026-02-26",
            instrument_code="L1",
            instrument_name="同业存单L1",
            bond_type="同业存单",
            amount=Decimal("100000000"),
            is_issuance_like=True,
            coupon_rate=Decimal("1.8"),
            ytm_value=Decimal("1.8"),
            maturity_date="2026-08-26",
        )
        _insert_tyw(
            conn,
            report_date="2026-02-26",
            position_id="TL1",
            product_type="同业拆入",
            position_side="liability",
            counterparty_name="银行A",
            principal=Decimal("100000000"),
            funding_cost_rate_percent=Decimal("1.6"),
            maturity_date="2026-03-26",
            core_customer_type="银行",
        )
    finally:
        conn.close()

    client = _build_client(db_path, monkeypatch)
    response = client.get("/api/analysis/yield_metrics", params={"report_date": "2026-02-26"})
    assert response.status_code == 200, response.text
    payload = _unwrap_liability_envelope(
        response.json(),
        result_kind="liability_analytics.yield_metrics",
    )

    _assert_close(payload["kpi"]["asset_yield"], 0.024)
    _assert_close(payload["kpi"]["liability_cost"], 0.017)
    _assert_close(payload["kpi"]["market_liability_cost"], 0.017)
    _assert_close(payload["kpi"]["nim"], 0.007)


def test_liability_yield_metrics_uses_interest_bearing_bond_asset_scope(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "liability-yield-scope.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        _insert_zqtz(
            conn,
            report_date="2026-02-26",
            instrument_code="AFS1",
            instrument_name="可供出售债",
            bond_type="商业银行债",
            amount=Decimal("100000000"),
            is_issuance_like=False,
            coupon_rate=Decimal("0.03"),
            ytm_value=Decimal("0.03"),
            maturity_date="2027-02-26",
        )
        conn.execute(
            "update zqtz_bond_daily_snapshot set asset_class = ? where report_date = ? and instrument_code = ?",
            ["可供出售金融资产", "2026-02-26", "AFS1"],
        )
        _insert_zqtz(
            conn,
            report_date="2026-02-26",
            instrument_code="TRD1",
            instrument_name="交易性债",
            bond_type="商业银行债",
            amount=Decimal("100000000"),
            is_issuance_like=False,
            coupon_rate=Decimal("0.01"),
            ytm_value=Decimal("0.01"),
            maturity_date="2027-02-26",
        )
        conn.execute(
            "update zqtz_bond_daily_snapshot set asset_class = ? where report_date = ? and instrument_code = ?",
            ["交易性金融资产", "2026-02-26", "TRD1"],
        )
    finally:
        conn.close()

    client = _build_client(db_path, monkeypatch)
    response = client.get("/api/analysis/yield_metrics", params={"report_date": "2026-02-26"})
    assert response.status_code == 200, response.text
    payload = _unwrap_liability_envelope(
        response.json(),
        result_kind="liability_analytics.yield_metrics",
    )

    _assert_close(payload["kpi"]["asset_yield"], 0.03)


def test_liability_risk_buckets_use_market_value_for_issuance_and_short_bucket_for_missing_maturity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "liability-buckets.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        _insert_zqtz(
            conn,
            report_date="2026-02-26",
            instrument_code="ISS1",
            instrument_name="同业存单A",
            bond_type="同业存单",
            amount=Decimal("100000000"),
            is_issuance_like=True,
            coupon_rate=Decimal("0.018"),
            ytm_value=Decimal("0.018"),
            maturity_date="2026-08-26",
        )
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set face_value_native = ?, market_value_native = ?
            where report_date = ? and instrument_code = ?
            """,
            [Decimal("120000000"), Decimal("100000000"), "2026-02-26", "ISS1"],
        )
        _insert_tyw(
            conn,
            report_date="2026-02-26",
            position_id="TL-NONE",
            product_type="同业存放",
            position_side="liability",
            counterparty_name="银行A",
            principal=Decimal("50000000"),
            funding_cost_rate_percent=Decimal("1.6"),
            maturity_date="2026-03-26",
            core_customer_type="银行",
        )
        conn.execute(
            """
            update tyw_interbank_daily_snapshot
            set maturity_date = null
            where report_date = ? and position_id = ?
            """,
            ["2026-02-26", "TL-NONE"],
        )
    finally:
        conn.close()

    client = _build_client(db_path, monkeypatch)
    response = client.get("/api/risk/buckets", params={"report_date": "2026-02-26"})
    assert response.status_code == 200, response.text
    payload = _unwrap_liability_envelope(
        response.json(),
        result_kind="liability_analytics.risk_buckets",
    )

    structure = {item["name"]: item["amount"] for item in payload["issued_liabilities_structure"]}
    _assert_close(structure["同业存单"], 100000000.0)

    term = {item["bucket"]: item["amount"] for item in payload["interbank_liabilities_term_buckets"]}
    _assert_close(term["3个月以内"], 50000000.0)
    assert "已到期/逾期" not in term


def test_liability_risk_buckets_use_v1_day_boundaries_for_term_buckets(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "liability-term-boundary.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        _insert_tyw(
            conn,
            report_date="2026-02-26",
            position_id="TL-181",
            product_type="同业存放",
            position_side="liability",
            counterparty_name="银行A",
            principal=Decimal("500000000"),
            funding_cost_rate_percent=Decimal("1.6"),
            maturity_date="2026-08-26",
            core_customer_type="银行",
        )
    finally:
        conn.close()

    client = _build_client(db_path, monkeypatch)
    response = client.get("/api/risk/buckets", params={"report_date": "2026-02-26"})
    assert response.status_code == 200, response.text
    payload = _unwrap_liability_envelope(
        response.json(),
        result_kind="liability_analytics.risk_buckets",
    )

    term = {item["bucket"]: item["amount"] for item in payload["interbank_liabilities_term_buckets"]}
    _assert_close(term["6-12个月"], 500000000.0)
    assert "3-6个月" not in term


def test_liabilities_monthly_uses_v1_counterparty_proportion_and_type_collapse(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "liabilities-monthly-counterparty.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        _insert_zqtz(
            conn,
            report_date="2026-01-31",
            instrument_code="ISS1",
            instrument_name="CD A",
            bond_type="CD",
            amount=Decimal("1000000000"),
            is_issuance_like=True,
            coupon_rate=Decimal("2.5"),
            ytm_value=Decimal("2.5"),
            maturity_date="2026-07-31",
        )
        _insert_tyw(
            conn,
            report_date="2026-01-31",
            position_id="BANK1",
            product_type="IB BORROW",
            position_side="liability",
            counterparty_name="ALPHA BANK",
            principal=Decimal("400000000"),
            funding_cost_rate_percent=Decimal("2.0"),
            maturity_date="2026-03-31",
            core_customer_type="bank",
        )
        _insert_tyw(
            conn,
            report_date="2026-01-31",
            position_id="FUND1",
            product_type="IB DEPOSIT",
            position_side="liability",
            counterparty_name="BETA WEALTH",
            principal=Decimal("100000000"),
            funding_cost_rate_percent=Decimal("3.0"),
            maturity_date="2026-04-30",
            core_customer_type="wealth",
        )
        _insert_tyw(
            conn,
            report_date="2026-01-31",
            position_id="CORP1",
            product_type="REPO",
            position_side="liability",
            counterparty_name="GAMMA CORP",
            principal=Decimal("50000000"),
            funding_cost_rate_percent=Decimal("3.2"),
            maturity_date="2026-05-31",
            core_customer_type="corp",
        )
    finally:
        conn.close()

    client = _build_client(db_path, monkeypatch)
    response = client.get("/api/liabilities/monthly", params={"year": 2026})
    assert response.status_code == 200, response.text
    payload = _unwrap_liability_envelope(
        response.json(),
        result_kind="liability_analytics.monthly",
    )

    month = payload["months"][0]
    detail_map = {item["name"]: item for item in month["counterparty_details"]}
    _assert_close(detail_map["ALPHA BANK"]["proportion"], 72.72727272727273)
    _assert_close(detail_map["ALPHA BANK"]["pct"], 25.806451612903224)
    assert detail_map["BETA WEALTH"]["type"] == "NonBank"
    assert detail_map["GAMMA CORP"]["type"] == "NonBank"

    by_type = {item["type"]: item for item in month["by_institution_type"]}
    assert set(by_type) == {"Bank", "NonBank"}
    _assert_close(by_type["Bank"]["avg_value"], 400000000.0)
    _assert_close(by_type["Bank"]["amount"], 400000000.0)
    _assert_close(by_type["Bank"]["pct"], 72.72727272727273)
    _assert_close(by_type["NonBank"]["avg_value"], 150000000.0)
    _assert_close(by_type["NonBank"]["amount"], 150000000.0)
    _assert_close(by_type["NonBank"]["pct"], 27.27272727272727)

    assert payload["ytd_avg_liability_cost"] is None


def test_liabilities_monthly_uses_v1_term_buckets_and_shape_fields(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "liabilities-monthly-buckets.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        _insert_zqtz(
            conn,
            report_date="2026-02-26",
            instrument_code="ISS-SHORT",
            instrument_name="CD A",
            bond_type="CD",
            amount=Decimal("100000000"),
            is_issuance_like=True,
            coupon_rate=Decimal("2.4"),
            ytm_value=Decimal("2.4"),
            maturity_date="2026-03-31",
        )
        _insert_zqtz(
            conn,
            report_date="2026-02-26",
            instrument_code="ISS-LONG",
            instrument_name="BANK BOND",
            bond_type="BANK BOND",
            amount=Decimal("200000000"),
            is_issuance_like=True,
            coupon_rate=Decimal("2.8"),
            ytm_value=Decimal("2.8"),
            maturity_date="2028-02-26",
        )
        _insert_tyw(
            conn,
            report_date="2026-02-26",
            position_id="IB-NULL",
            product_type="IB DEPOSIT",
            position_side="liability",
            counterparty_name="OMEGA BANK",
            principal=Decimal("50000000"),
            funding_cost_rate_percent=Decimal("1.8"),
            maturity_date="2026-03-15",
            core_customer_type="bank",
        )
        conn.execute(
            """
            update tyw_interbank_daily_snapshot
            set maturity_date = null
            where report_date = ? and position_id = ?
            """,
            ["2026-02-26", "IB-NULL"],
        )
    finally:
        conn.close()

    client = _build_client(db_path, monkeypatch)
    response = client.get("/api/liabilities/monthly", params={"year": 2026})
    assert response.status_code == 200, response.text
    payload = _unwrap_liability_envelope(
        response.json(),
        result_kind="liability_analytics.monthly",
    )

    month = payload["months"][0]
    assert [item["bucket"] for item in month["term_buckets"]] == [
        "0-3M",
        "3-6M",
        "6-12M",
        "1-3Y",
        "3-5Y",
        "5-10Y",
        "10Y+",
        "Matured",
    ]

    bucket_map = {item["bucket"]: item for item in month["term_buckets"]}
    _assert_close(bucket_map["0-3M"]["avg_balance"], 150000000.0)
    _assert_close(bucket_map["0-3M"]["amount"], 150000000.0)
    _assert_close(bucket_map["0-3M"]["pct"], 42.857142857142854)
    _assert_close(bucket_map["1-3Y"]["avg_balance"], 200000000.0)
    _assert_close(bucket_map["1-3Y"]["amount"], 200000000.0)
    _assert_close(bucket_map["1-3Y"]["pct"], 57.14285714285714)
    _assert_close(bucket_map["Matured"]["avg_balance"], 0.0)
    _assert_close(bucket_map["Matured"]["amount"], 0.0)
    _assert_close(bucket_map["Matured"]["pct"], 0.0)

    assert set(month["structure_overview"][0]) >= {"category", "avg_balance", "proportion", "amount", "pct"}
    assert set(month["counterparty_top10"][0]) >= {
        "name",
        "avg_value",
        "proportion",
        "amount",
        "pct",
        "weighted_cost",
        "type",
    }


def test_liability_monthly_and_risk_buckets_use_amortized_cost_for_issued_bonds(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "liability-issued-basis.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        _insert_zqtz(
            conn,
            report_date="2026-02-26",
            instrument_code="ISS-AMORT",
            instrument_name="CD AMORT",
            bond_type="CD",
            amount=Decimal("100000000"),
            is_issuance_like=True,
            coupon_rate=Decimal("2.4"),
            ytm_value=Decimal("2.4"),
            maturity_date="2026-06-30",
        )
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set market_value_native = ?, amortized_cost_native = ?
            where report_date = ? and instrument_code = ?
            """,
            [Decimal("93000000"), Decimal("101000000"), "2026-02-26", "ISS-AMORT"],
        )
    finally:
        conn.close()

    client = _build_client(db_path, monkeypatch)

    monthly = client.get("/api/liabilities/monthly", params={"year": 2026})
    assert monthly.status_code == 200, monthly.text
    monthly_payload = _unwrap_liability_envelope(
        monthly.json(),
        result_kind="liability_analytics.monthly",
    )
    month = monthly_payload["months"][0]
    _assert_close(month["avg_issued_liabilities"], 101000000.0)
    _assert_close(month["avg_total_liabilities"], 101000000.0)
    _assert_close(month["structure_overview"][1]["avg_balance"], 101000000.0)
    _assert_close(month["issued_term_buckets"][1]["avg_balance"], 101000000.0)

    risk = client.get("/api/risk/buckets", params={"report_date": "2026-02-26"})
    assert risk.status_code == 200, risk.text
    risk_payload = _unwrap_liability_envelope(
        risk.json(),
        result_kind="liability_analytics.risk_buckets",
    )
    issued = {item["name"]: item["amount"] for item in risk_payload["issued_liabilities_structure"]}
    _assert_close(issued["CD"], 101000000.0)


def test_liabilities_monthly_uses_v1_tie_break_for_equal_counterparty_avg_values(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "liability-counterparty-ties.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        _insert_tyw(
            conn,
            report_date="2026-02-01",
            position_id="100",
            product_type="IB DEPOSIT",
            position_side="liability",
            counterparty_name="ALPHA BANK",
            principal=Decimal("100000000"),
            funding_cost_rate_percent=Decimal("1.2"),
            maturity_date="2026-02-28",
            core_customer_type="bank",
        )
        _insert_tyw(
            conn,
            report_date="2026-02-01",
            position_id="200",
            product_type="IB DEPOSIT",
            position_side="liability",
            counterparty_name="ZETA BANK",
            principal=Decimal("100000000"),
            funding_cost_rate_percent=Decimal("1.5"),
            maturity_date="2026-02-28",
            core_customer_type="bank",
        )
        _insert_tyw(
            conn,
            report_date="2026-02-02",
            position_id="150",
            product_type="IB DEPOSIT",
            position_side="liability",
            counterparty_name="MID BANK",
            principal=Decimal("100000000"),
            funding_cost_rate_percent=Decimal("1.3"),
            maturity_date="2026-02-28",
            core_customer_type="bank",
        )
    finally:
        conn.close()

    client = _build_client(db_path, monkeypatch)
    response = client.get("/api/liabilities/monthly", params={"year": 2026})
    assert response.status_code == 200, response.text
    payload = _unwrap_liability_envelope(
        response.json(),
        result_kind="liability_analytics.monthly",
    )

    names = [item["name"] for item in payload["months"][0]["counterparty_details"]]
    assert names == ["ZETA BANK", "ALPHA BANK", "MID BANK"]
