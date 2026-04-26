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
                "interest_mode": "semi annual",
                "currency_code": "CNY",
            },
            {
                "instrument_code": "BOND-OLD",
                "instrument_name": "Expired Bond",
                "maturity_date": date(2025, 12, 31),
                "face_value": Decimal("50"),
                "coupon_rate": Decimal("0.05"),
                "interest_mode": "annual",
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
                "interest_mode": "bullet",
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


def test_bullet_bond_with_value_date_projects_full_maturity_coupon():
    module = _core_module()

    events = module.project_bond_cashflows(
        [
            {
                "instrument_code": "BOND-BULLET-3Y",
                "instrument_name": "Three Year Bullet Bond",
                "value_date": date(2024, 7, 15),
                "maturity_date": date(2027, 7, 15),
                "face_value": Decimal("100"),
                "coupon_rate": Decimal("0.06"),
                "interest_mode": "bullet",
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
        ("coupon", "2027-07-15", Decimal("18.00")),
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


def test_interbank_percent_funding_rate_is_normalized():
    module = _core_module()

    events = module.project_tyw_cashflows(
        [
            {
                "position_id": "TYW-PCT",
                "counterparty_name": "Bank A",
                "position_scope": "asset",
                "maturity_date": date(2026, 1, 31),
                "principal_amount": Decimal("365"),
                "funding_cost_rate": Decimal("10.0"),
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
        ("funding_income", "2026-01-31", Decimal("3.0")),
        ("maturity", "2026-01-31", Decimal("365")),
    ]


def test_scope_recognizes_non_mojibake_chinese_asset_and_liability_labels():
    module = _core_module()

    assert module._row_scope({"position_scope": "资产"}) == "asset"
    assert module._row_scope({"position_scope": "负债"}) == "liability"
    assert module._row_scope({"position_scope": "璧勪骇"}) == "asset"


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


def test_duration_gap_calculation_uses_full_scope_term_proxy():
    module = _core_module()

    result = module.compute_duration_gap(
        zqtz_rows=[
            {
                "instrument_code": "BOND-001",
                "instrument_name": "Bond 1",
                "position_scope": "asset",
                "maturity_date": date(2028, 1, 1),
                "face_value_amount": Decimal("100"),
                "market_value_amount": Decimal("100"),
                "coupon_rate": Decimal("0.05"),
                "macaulay_duration": Decimal("1.8"),
                "interest_mode": "annual",
                "currency_code": "CNY",
            },
            {
                "instrument_code": "BOND-002",
                "instrument_name": "Bond 2",
                "position_scope": "liability",
                "maturity_date": date(2027, 1, 1),
                "face_value_amount": Decimal("50"),
                "market_value_amount": Decimal("50"),
                "coupon_rate": Decimal("0.04"),
                "interest_mode": "annual",
                "currency_code": "CNY",
            },
        ],
        tyw_rows=[
            {
                "position_id": "TYW-ASSET-001",
                "counterparty_name": "Bank Asset",
                "position_scope": "asset",
                "maturity_date": date(2026, 7, 1),
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("0.03"),
                "currency_code": "CNY",
            },
            {
                "position_id": "TYW-LIAB-001",
                "counterparty_name": "Bank Liability",
                "position_scope": "liability",
                "maturity_date": date(2028, 1, 1),
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("0.03"),
                "currency_code": "CNY",
            },
        ],
        report_date=date(2026, 1, 1),
        horizon_months=24,
    )

    assert result.asset_weighted_duration == Decimal("1.147945205479452054794520548")
    assert result.liability_weighted_duration == Decimal("1.666666666666666666666666667")
    assert result.duration_gap == Decimal("-0.518721461187214611872146119")
    assert result.modified_duration_gap == Decimal("-0.518721461187214611872146119")
    assert result.total_asset_market_value == Decimal("200")
    assert result.total_liability_value == Decimal("150")
    assert result.equity_duration == Decimal("-2.074885844748858447488584476")
    assert result.rate_sensitivity_1bp == Decimal("-0.01037442922374429223744292238")


def test_duration_gap_warns_when_missing_maturity_excludes_rows():
    module = _core_module()

    result = module.compute_duration_gap(
        zqtz_rows=[
            {
                "instrument_code": "BOND-001",
                "instrument_name": "Bond 1",
                "position_scope": "asset",
                "maturity_date": date(2030, 1, 1),
                "face_value_amount": Decimal("300"),
                "market_value_amount": Decimal("300"),
                "coupon_rate": Decimal("0.04"),
                "macaulay_duration": Decimal("3.2"),
                "interest_mode": "annual",
                "currency_code": "CNY",
            },
        ],
        tyw_rows=[
            {
                "position_id": "TYW-001",
                "counterparty_name": "Bank A",
                "position_scope": "liability",
                "maturity_date": None,
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("0.03"),
                "currency_code": "CNY",
            },
            {
                "position_id": "TYW-002",
                "counterparty_name": "Bank B",
                "position_scope": "liability",
                "maturity_date": date(2028, 1, 1),
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("0.03"),
                "currency_code": "CNY",
            },
        ],
        report_date=date(2026, 1, 1),
        horizon_months=24,
    )

    assert result.asset_weighted_duration == Decimal("3.2")
    assert result.liability_weighted_duration == Decimal("2")
    assert result.duration_gap == Decimal("1.2")
    assert result.modified_duration_gap == Decimal("1.2")
    assert result.total_asset_market_value == Decimal("300")
    assert result.total_liability_value == Decimal("200")
    assert result.equity_duration == Decimal("3.6")
    assert result.rate_sensitivity_1bp == Decimal("0.0360")
    assert any("missing maturity information" in warning for warning in result.warnings)


def test_tywl_demand_positions_without_maturity_use_one_month_proxy():
    module = _core_module()

    result = module.compute_duration_gap(
        zqtz_rows=[],
        tyw_rows=[
            {
                "position_id": "TYW-ASSET-001",
                "product_type": "存放同业",
                "counterparty_name": "Bank Asset",
                "position_scope": "asset",
                "maturity_date": None,
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("0.03"),
                "currency_code": "CNY",
            },
            {
                "position_id": "TYW-LIAB-001",
                "product_type": "同业存放",
                "counterparty_name": "Bank Liability",
                "position_scope": "liability",
                "maturity_date": None,
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("0.03"),
                "currency_code": "CNY",
            },
        ],
        report_date=date(2026, 1, 1),
        horizon_months=24,
    )

    one_month_proxy = Decimal("31") / Decimal("365")
    assert result.asset_weighted_duration == one_month_proxy
    assert result.liability_weighted_duration == one_month_proxy
    assert result.duration_gap == Decimal("0")
    assert result.modified_duration_gap == Decimal("0")
    assert all("missing maturity information" not in warning for warning in result.warnings)


def test_tywl_demand_positions_without_maturity_project_into_next_month():
    module = _core_module()

    cashflows = module.project_tyw_cashflows(
        [
            {
                "position_id": "TYW-ASSET-001",
                "product_type": "存放同业",
                "counterparty_name": "Bank Asset",
                "position_scope": "asset",
                "maturity_date": None,
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("0.03"),
                "currency_code": "CNY",
            },
            {
                "position_id": "TYW-LIAB-001",
                "product_type": "同业存放",
                "counterparty_name": "Bank Liability",
                "position_scope": "liability",
                "maturity_date": None,
                "principal_amount": Decimal("80"),
                "funding_cost_rate": Decimal("0.03"),
                "currency_code": "CNY",
            },
        ],
        report_date=date(2026, 1, 1),
        horizon_months=2,
    )

    assert [(event.event_type, event.event_date.isoformat(), event.side, event.amount) for event in cashflows] == [
        ("funding_cost", "2026-02-01", "liability", Decimal("-0.2038356164383561643835616438")),
        ("funding_income", "2026-02-01", "asset", Decimal("0.2547945205479452054794520548")),
        ("maturity", "2026-02-01", "asset", Decimal("100")),
        ("maturity", "2026-02-01", "liability", Decimal("-80")),
    ]


def test_reinvestment_risk_ratio():
    module = _core_module()

    result = module.compute_duration_gap(
        zqtz_rows=[
            {
                "instrument_code": "BOND-NEAR",
                "instrument_name": "Near Maturity",
                "position_scope": "asset",
                "maturity_date": date(2026, 6, 1),
                "face_value_amount": Decimal("100"),
                "market_value_amount": Decimal("100"),
                "coupon_rate": Decimal("0.03"),
                "interest_mode": "骞翠粯",
                "currency_code": "CNY",
            },
            {
                "instrument_code": "BOND-LONG",
                "instrument_name": "Long Bond",
                "position_scope": "asset",
                "maturity_date": date(2028, 1, 1),
                "face_value_amount": Decimal("300"),
                "market_value_amount": Decimal("300"),
                "coupon_rate": Decimal("0.05"),
                "interest_mode": "骞翠粯",
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

    def fake_fetch_zqtz_rows(self, *, report_date, position_scope="all", currency_basis="CNY"):
        assert report_date == "2026-01-01"
        assert position_scope == "all"
        assert currency_basis == "CNY"
        return [
            {
                "instrument_code": "BOND-001",
                "instrument_name": "Bond 1",
                "position_scope": "asset",
                "maturity_date": date(2026, 7, 1),
                "face_value_amount": Decimal("100"),
                "market_value_amount": Decimal("100"),
                "coupon_rate": Decimal("0.05"),
                "interest_mode": "骞翠粯",
                "currency_code": "CNY",
                "source_version": "sv_bond_1",
                "rule_version": "rv_bond_1",
            }
        ]

    def fake_fetch_tyw_rows(self, *, report_date, position_scope="all", currency_basis="CNY"):
        assert report_date == "2026-01-01"
        assert position_scope == "all"
        assert currency_basis == "CNY"
        return [
            {
                "position_id": "TYW-001",
                "counterparty_name": "Bank A",
                "position_scope": "liability",
                "maturity_date": date(2026, 3, 1),
                "principal_amount": Decimal("80"),
                "funding_cost_rate": Decimal("0.03"),
                "currency_code": "CNY",
                "source_version": "sv_tyw_1",
                "rule_version": "rv_tyw_1",
            }
        ]

    monkeypatch.setattr(
        service_mod.BalanceAnalysisRepository,
        "fetch_formal_zqtz_rows",
        fake_fetch_zqtz_rows,
    )
    monkeypatch.setattr(
        service_mod.BalanceAnalysisRepository,
        "fetch_formal_tyw_rows",
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


def test_api_recomputes_asset_macaulay_duration_from_percent_rates(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()

    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    bond_duration_mod = load_module(
        "backend.app.core_finance.bond_duration",
        "backend/app/core_finance/bond_duration.py",
    )

    def fake_fetch_zqtz_rows(self, *, report_date, position_scope="all", currency_basis="CNY"):
        assert report_date == "2026-01-01"
        return [
            {
                "instrument_code": "BOND-001",
                "instrument_name": "Bond 1",
                "portfolio_name": "P1",
                "cost_center": "C1",
                "position_scope": "asset",
                "maturity_date": date(2031, 1, 1),
                "face_value_amount": Decimal("100"),
                "market_value_amount": Decimal("100"),
                "coupon_rate": Decimal("3.0"),
                "ytm_value": Decimal("3.5"),
                "interest_mode": "annual",
                "currency_code": "CNY",
                "source_version": "sv_zqtz_1",
                "rule_version": "rv_zqtz_1",
            }
        ]

    def fake_fetch_tyw_rows(self, *, report_date, position_scope="all", currency_basis="CNY"):
        assert report_date == "2026-01-01"
        return []

    def fake_fetch_bond_analytics_rows(self, *, report_date, asset_class="all", accounting_class="all"):
        assert report_date == "2026-01-01"
        return [
            {
                "report_date": date(2026, 1, 1),
                "instrument_code": "BOND-001",
                "instrument_name": "Bond 1",
                "portfolio_name": "P1",
                "cost_center": "C1",
                "currency_code": "CNY",
                "maturity_date": date(2031, 1, 1),
                "coupon_rate": Decimal("3.0"),
                "ytm": Decimal("3.5"),
                "macaulay_duration": Decimal("1.25"),
            }
        ]

    monkeypatch.setattr(
        service_mod.BalanceAnalysisRepository,
        "fetch_formal_zqtz_rows",
        fake_fetch_zqtz_rows,
    )
    monkeypatch.setattr(
        service_mod.BalanceAnalysisRepository,
        "fetch_formal_tyw_rows",
        fake_fetch_tyw_rows,
    )
    monkeypatch.setattr(
        service_mod.BondAnalyticsRepository,
        "fetch_bond_analytics_rows",
        fake_fetch_bond_analytics_rows,
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
    expected = bond_duration_mod.estimate_duration(
        date(2031, 1, 1),
        date(2026, 1, 1),
        coupon_rate=Decimal("0.03"),
        ytm=Decimal("0.035"),
        bond_code="BOND-001",
    )
    assert Decimal(str(payload["result"]["asset_duration"]["raw"])) == expected

    get_settings.cache_clear()
