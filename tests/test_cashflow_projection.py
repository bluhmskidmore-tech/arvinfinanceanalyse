from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def _core_module():
    return load_module(
        "backend.app.core_finance.cashflow_projection",
        "backend/app/core_finance/cashflow_projection.py",
    )


def test_bond_cashflow_projection_basic():
    module = _core_module()

    events = module.project_bond_cashflows(
        [
            {
                "instrument_code": "BOND-001",
                "instrument_name": "Alpha Bond",
                "maturity_date": date(2026, 7, 15),
                "face_value": Decimal("100"),
                "coupon_rate": Decimal("0.06"),
                "interest_mode": "半年付息",
                "currency_code": "CNY",
            },
            {
                "instrument_code": "BOND-OLD",
                "instrument_name": "Expired Bond",
                "maturity_date": date(2025, 12, 31),
                "face_value": Decimal("50"),
                "coupon_rate": Decimal("0.05"),
                "interest_mode": "年付",
                "currency_code": "CNY",
            },
        ],
        report_date=date(2026, 1, 14),
        horizon_months=12,
    )

    assert [
        (event.event_type, event.event_date.isoformat(), event.amount)
        for event in events
    ] == [
        ("coupon", "2026-01-15", Decimal("3")),
        ("coupon", "2026-07-15", Decimal("3")),
        ("principal", "2026-07-15", Decimal("100")),
    ]


def test_bond_cashflow_projection_treats_bullet_as_maturity_only_coupon():
    module = _core_module()

    events = module.project_bond_cashflows(
        [
            {
                "instrument_code": "BOND-BULLET",
                "instrument_name": "Bullet Bond",
                "maturity_date": date(2027, 7, 15),
                "face_value": Decimal("100"),
                "coupon_rate": Decimal("0.06"),
                "interest_mode": "到期一次还本付息",
                "currency_code": "CNY",
            }
        ],
        report_date=date(2026, 1, 14),
        horizon_months=24,
    )

    assert [
        (event.event_type, event.event_date.isoformat(), event.amount)
        for event in events
    ] == [
        ("coupon", "2027-07-15", Decimal("6")),
        ("principal", "2027-07-15", Decimal("100")),
    ]


def test_liability_cashflow_projection():
    module = _core_module()

    events = module.project_liability_cashflows(
        [
            {
                "position_id": "TYW-001",
                "counterparty_name": "Bank A",
                "position_side": "liability",
                "maturity_date": date(2026, 1, 31),
                "principal_amount": Decimal("365"),
                "funding_cost_rate": Decimal("0.10"),
                "currency_code": "CNY",
            }
        ],
        report_date=date(2026, 1, 1),
        horizon_months=12,
    )

    assert [
        (event.event_type, event.event_date.isoformat(), event.amount)
        for event in events
    ] == [
        ("funding_cost", "2026-01-31", Decimal("-3.0")),
        ("maturity", "2026-01-31", Decimal("-365")),
    ]


def test_monthly_bucket_aggregation():
    module = _core_module()

    buckets = module.build_monthly_buckets(
        [
            module.CashflowEvent(
                event_date=date(2026, 1, 20),
                event_type="coupon",
                instrument_code="A1",
                instrument_name="Asset A1",
                side="asset",
                amount=Decimal("100"),
                currency_code="CNY",
            ),
            module.CashflowEvent(
                event_date=date(2026, 1, 25),
                event_type="funding_cost",
                instrument_code="L1",
                instrument_name="Liability L1",
                side="liability",
                amount=Decimal("-20"),
                currency_code="CNY",
            ),
            module.CashflowEvent(
                event_date=date(2026, 2, 10),
                event_type="principal",
                instrument_code="A2",
                instrument_name="Asset A2",
                side="asset",
                amount=Decimal("50"),
                currency_code="CNY",
            ),
            module.CashflowEvent(
                event_date=date(2026, 2, 15),
                event_type="maturity",
                instrument_code="L2",
                instrument_name="Liability L2",
                side="liability",
                amount=Decimal("-30"),
                currency_code="CNY",
            ),
        ],
        report_date=date(2026, 1, 15),
        horizon_months=2,
    )

    assert [(bucket.year_month, bucket.net_cashflow, bucket.cumulative_net) for bucket in buckets] == [
        ("2026-01", Decimal("80"), Decimal("80")),
        ("2026-02", Decimal("20"), Decimal("100")),
    ]

    assert buckets[0].asset_inflow == Decimal("100")
    assert buckets[0].liability_outflow == Decimal("20")
    assert buckets[1].asset_inflow == Decimal("50")
    assert buckets[1].liability_outflow == Decimal("30")


def test_duration_gap_calculation():
    module = _core_module()

    result = module.compute_duration_gap(
        bond_rows=[
            {
                "instrument_code": "BOND-001",
                "instrument_name": "Bond 1",
                "maturity_date": date(2028, 1, 1),
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0.05"),
                "modified_duration": Decimal("2"),
                "years_to_maturity": Decimal("2"),
                "interest_mode": "年付",
                "currency_code": "CNY",
            },
            {
                "instrument_code": "BOND-002",
                "instrument_name": "Bond 2",
                "maturity_date": date(2030, 1, 1),
                "face_value": Decimal("300"),
                "market_value": Decimal("300"),
                "coupon_rate": Decimal("0.04"),
                "modified_duration": Decimal("4"),
                "years_to_maturity": Decimal("4"),
                "interest_mode": "年付",
                "currency_code": "CNY",
            },
        ],
        tyw_rows=[
            {
                "position_id": "TYW-001",
                "counterparty_name": "Bank A",
                "position_side": "liability",
                "maturity_date": date(2027, 1, 1),
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("0.03"),
                "currency_code": "CNY",
            },
            {
                "position_id": "TYW-002",
                "counterparty_name": "Bank B",
                "position_side": "liability",
                "maturity_date": date(2028, 1, 1),
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("0.03"),
                "currency_code": "CNY",
            },
        ],
        report_date=date(2026, 1, 1),
        horizon_months=24,
    )

    assert result.asset_weighted_duration == Decimal("3.5")
    assert result.liability_weighted_duration == Decimal("1.5")
    assert result.duration_gap == Decimal("2.0")
    assert result.modified_duration_gap == Decimal("2.0")
    assert result.total_asset_market_value == Decimal("400")
    assert result.total_liability_value == Decimal("200")
    assert result.equity_duration == Decimal("4.0")
    assert result.rate_sensitivity_1bp == Decimal("0.0800")


def test_reinvestment_risk_ratio():
    module = _core_module()

    result = module.compute_duration_gap(
        bond_rows=[
            {
                "instrument_code": "BOND-NEAR",
                "instrument_name": "Near Maturity",
                "maturity_date": date(2026, 6, 1),
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0.03"),
                "modified_duration": Decimal("0.4"),
                "years_to_maturity": Decimal("0.41666667"),
                "interest_mode": "年付",
                "currency_code": "CNY",
            },
            {
                "instrument_code": "BOND-LONG",
                "instrument_name": "Long Bond",
                "maturity_date": date(2028, 1, 1),
                "face_value": Decimal("300"),
                "market_value": Decimal("300"),
                "coupon_rate": Decimal("0.05"),
                "modified_duration": Decimal("3.5"),
                "years_to_maturity": Decimal("2"),
                "interest_mode": "年付",
                "currency_code": "CNY",
            },
        ],
        tyw_rows=[],
        report_date=date(2026, 1, 1),
        horizon_months=24,
    )

    assert result.reinvestment_risk_12m == Decimal("0.25")


def test_api_returns_envelope(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()

    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )

    def fake_fetch_bond_rows(self, *, report_date, asset_class="all", accounting_class="all"):
        assert report_date == "2026-01-01"
        return [
            {
                "instrument_code": "BOND-001",
                "instrument_name": "Bond 1",
                "maturity_date": date(2026, 7, 1),
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0.05"),
                "modified_duration": Decimal("1.5"),
                "years_to_maturity": Decimal("0.5"),
                "interest_mode": "年付",
                "currency_code": "CNY",
                "source_version": "sv_bond_1",
                "rule_version": "rv_bond_1",
            }
        ]

    def fake_fetch_tyw_rows(self, *, report_date, currency_basis="CNY"):
        assert report_date == "2026-01-01"
        return [
            {
                "position_id": "TYW-001",
                "counterparty_name": "Bank A",
                "position_side": "liability",
                "maturity_date": date(2026, 3, 1),
                "principal_amount": Decimal("80"),
                "funding_cost_rate": Decimal("0.03"),
                "currency_code": "CNY",
                "source_version": "sv_tyw_1",
                "rule_version": "rv_tyw_1",
            }
        ]

    monkeypatch.setattr(
        service_mod.BondAnalyticsRepository,
        "fetch_bond_analytics_rows",
        fake_fetch_bond_rows,
    )
    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_tyw_liability_rows",
        fake_fetch_tyw_rows,
    )

    route_mod = load_module(
        "backend.app.api.routes.cashflow_projection",
        "backend/app/api/routes/cashflow_projection.py",
    )
    app = FastAPI()
    app.include_router(route_mod.router)
    client = TestClient(app)
    response = client.get(
        "/api/cashflow-projection",
        params={"report_date": "2026-01-01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result_meta"]["scenario_flag"] is False
    assert payload["result_meta"]["result_kind"] == "cashflow_projection.overview"
    assert payload["result"]["report_date"] == "2026-01-01"
    assert "duration_gap" in payload["result"]
    assert "monthly_buckets" in payload["result"]
    assert "top_maturing_assets_12m" in payload["result"]
    assert "computed_at" in payload["result"]

    get_settings.cache_clear()
