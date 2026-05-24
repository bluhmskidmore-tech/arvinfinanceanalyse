"""Contract tests for bond-analytics portfolio headlines & top holdings (formal envelope)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module

REPORT_DATE = "2026-03-31"


def _make_bond_analytics_row(
    *,
    report_date: str,
    instrument_code: str,
    asset_class_std: str,
    market_value: Decimal,
    ytm: Decimal,
    modified_duration: Decimal,
    maturity_date: date | None = date(2030, 1, 1),
) -> Any:
    from backend.app.core_finance.bond_analytics.engine import BondAnalyticsRow

    macaulay_duration = modified_duration * Decimal("1.02")
    return BondAnalyticsRow(
        report_date=date.fromisoformat(report_date),
        instrument_code=instrument_code,
        instrument_name=instrument_code,
        portfolio_name="P1",
        cost_center="C1",
        asset_class_raw=asset_class_std,
        asset_class_std=asset_class_std,
        bond_type=asset_class_std,
        issuer_name="I",
        industry_name="bank",
        rating="AAA",
        accounting_class="AC",
        accounting_rule_id="r1",
        currency_code="CNY",
        face_value=market_value,
        market_value_native=market_value,
        market_value=market_value,
        amortized_cost=market_value,
        accrued_interest=Decimal("0"),
        coupon_rate=Decimal("0.025"),
        interest_mode="fixed",
        interest_payment_frequency="annual",
        interest_rate_style="fixed",
        ytm=ytm,
        maturity_date=maturity_date,
        next_call_date=None,
        years_to_maturity=Decimal("2.5"),
        tenor_bucket="1-3Y",
        macaulay_duration=macaulay_duration,
        modified_duration=modified_duration,
        convexity=Decimal("0.01"),
        dv01=market_value * modified_duration / Decimal("10000"),
        is_credit=asset_class_std == "credit",
        spread_dv01=market_value * modified_duration / Decimal("10000") if asset_class_std == "credit" else Decimal("0"),
        source_version="sv",
        rule_version="rv",
        ingest_batch_id="ib",
        trace_id="tr",
    )


def _metric_raw(value: Any) -> Decimal:
    if isinstance(value, dict):
        return Decimal(str(value["raw"]))
    return Decimal(str(value))


def _assert_formal_envelope(payload: dict[str, Any]) -> None:
    assert "result_meta" in payload
    assert "result" in payload
    meta = payload["result_meta"]
    assert meta.get("basis") == "formal"
    assert meta.get("formal_use_allowed") is True
    for key in ("trace_id", "source_version", "rule_version", "result_kind"):
        assert key in meta, f"result_meta missing {key!r}"
        assert meta[key] not in (None, ""), f"result_meta.{key} must be non-empty"


def test_portfolio_headlines_empty_duckdb(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "empty.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    try:
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/api/bond-analytics/portfolio-headlines",
            params={"report_date": REPORT_DATE},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        _assert_formal_envelope(payload)
        assert payload["result_meta"]["result_kind"] == "bond_analytics.portfolio_headlines"
        result = payload["result"]
        assert result["report_date"] == REPORT_DATE
        assert result["bond_count"] == 0
        assert result["by_asset_class"] == []
        assert result["warnings"]
    finally:
        get_settings.cache_clear()


def test_portfolio_headlines_weighted_yield_and_duration_exclude_other_or_no_maturity_assets(tmp_path, monkeypatch) -> None:
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository

    duckdb_path = tmp_path / "portfolio-headlines.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    try:
        repo = BondAnalyticsRepository(str(duckdb_path))
        repo.replace_bond_analytics_rows(
            report_date=REPORT_DATE,
            rows=[
                _make_bond_analytics_row(
                    report_date=REPORT_DATE,
                    instrument_code="RATE",
                    asset_class_std="rate",
                    market_value=Decimal("100"),
                    ytm=Decimal("0.02"),
                    modified_duration=Decimal("2"),
                ),
                _make_bond_analytics_row(
                    report_date=REPORT_DATE,
                    instrument_code="CREDIT",
                    asset_class_std="credit",
                    market_value=Decimal("300"),
                    ytm=Decimal("0.04"),
                    modified_duration=Decimal("6"),
                ),
                _make_bond_analytics_row(
                    report_date=REPORT_DATE,
                    instrument_code="OTHER",
                    asset_class_std="other",
                    market_value=Decimal("600"),
                    ytm=Decimal("0"),
                    modified_duration=Decimal("0"),
                ),
                _make_bond_analytics_row(
                    report_date=REPORT_DATE,
                    instrument_code="NO-MATURITY",
                    asset_class_std="rate",
                    market_value=Decimal("1000"),
                    ytm=Decimal("0.99"),
                    modified_duration=Decimal("0"),
                    maturity_date=None,
                ),
            ],
        )

        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/api/bond-analytics/portfolio-headlines",
            params={"report_date": REPORT_DATE},
        )

        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert result["bond_count"] == 4
        assert _metric_raw(result["weighted_ytm"]) == Decimal("0.035")
        assert _metric_raw(result["weighted_duration"]) == Decimal("5")
    finally:
        get_settings.cache_clear()


def test_top_holdings_empty_duckdb(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "empty.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    try:
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/api/bond-analytics/top-holdings",
            params={"report_date": REPORT_DATE, "top_n": 10},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        _assert_formal_envelope(payload)
        assert payload["result_meta"]["result_kind"] == "bond_analytics.top_holdings"
        result = payload["result"]
        assert result["report_date"] == REPORT_DATE
        assert result["top_n"] == 10
        assert result["items"] == []
    finally:
        get_settings.cache_clear()
