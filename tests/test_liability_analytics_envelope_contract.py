from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import duckdb

from tests.test_liability_analytics_api import (
    _build_client,
    _ensure_tables,
    _insert_tyw,
    _insert_zqtz,
)


def test_liability_risk_buckets_returns_governed_envelope(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "liability-envelope.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        _insert_zqtz(
            conn,
            report_date="2026-01-31",
            instrument_code="ISS1",
            instrument_name="同业存单A",
            bond_type="同业存单",
            amount=Decimal("100000000"),
            is_issuance_like=True,
            coupon_rate=Decimal("0.020"),
            ytm_value=Decimal("0.020"),
            maturity_date="2026-10-01",
        )
        _insert_tyw(
            conn,
            report_date="2026-01-31",
            position_id="TL1",
            product_type="同业拆入",
            position_side="liability",
            counterparty_name="银行A",
            principal=Decimal("200000000"),
            funding_cost_rate_percent=Decimal("2.5"),
            maturity_date="2026-04-01",
            core_customer_type="银行",
        )
    finally:
        conn.close()

    client = _build_client(db_path, monkeypatch)
    response = client.get("/api/risk/buckets", params={"report_date": "2026-01-31"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert "result_meta" in body
    assert "result" in body
    assert body["result_meta"]["basis"] == "analytical"
    assert body["result_meta"]["formal_use_allowed"] is False
    assert body["result_meta"]["scenario_flag"] is False
    assert body["result_meta"]["result_kind"] == "liability_analytics.risk_buckets"
    assert body["result"]["report_date"] == "2026-01-31"


def test_liability_launch_endpoints_keep_envelope_shape_when_inputs_are_empty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "liability-empty.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
    finally:
        conn.close()

    client = _build_client(db_path, monkeypatch)
    targets = [
        ("/api/risk/buckets", {"report_date": "2026-01-31"}, "liability_analytics.risk_buckets"),
        ("/api/analysis/yield_metrics", {"report_date": "2026-01-31"}, "liability_analytics.yield_metrics"),
        (
            "/api/analysis/liabilities/counterparty",
            {"report_date": "2026-01-31", "top_n": "10"},
            "liability_analytics.counterparty",
        ),
        ("/api/liabilities/monthly", {"year": "2026"}, "liability_analytics.monthly"),
    ]

    for path, params, result_kind in targets:
        response = client.get(path, params=params)

        assert response.status_code == 200, response.text
        body = response.json()
        assert "result_meta" in body
        assert "result" in body
        assert body["result_meta"]["basis"] == "analytical"
        assert body["result_meta"]["formal_use_allowed"] is False
        assert body["result_meta"]["scenario_flag"] is False
        assert body["result_meta"]["result_kind"] == result_kind
