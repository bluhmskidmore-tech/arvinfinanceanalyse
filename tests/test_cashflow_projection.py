from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module

CASHFLOW_PROJECTION_READ_HEADERS = {
    "X-User-Id": "cashflow-projection-read-user",
    "X-User-Role": "viewer",
}


def _grant_cashflow_projection_read_scope(tmp_path, monkeypatch, *, user_id: str = "*") -> None:
    sqlite_path = tmp_path / "cashflow-projection-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    repo_module = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo_module.UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id=user_id,
        role=None,
        resource="cashflow_projection",
        action="read",
    )


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
                "coupon_rate": Decimal("6.0"),
                "interest_mode": "semi annual",
                "currency_code": "CNY",
            },
            {
                "instrument_code": "BOND-OLD",
                "instrument_name": "Expired Bond",
                "maturity_date": date(2025, 12, 31),
                "face_value": Decimal("50"),
                "coupon_rate": Decimal("5.0"),
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
                "coupon_rate": Decimal("6.0"),
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
                "coupon_rate": Decimal("6.0"),
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


def test_interbank_low_percent_funding_rate_is_normalized():
    module = _core_module()

    events = module.project_tyw_cashflows(
        [
            {
                "position_id": "TYW-LOW-PCT",
                "counterparty_name": "Bank A",
                "position_scope": "asset",
                "maturity_date": date(2026, 1, 31),
                "principal_amount": Decimal("365"),
                "funding_cost_rate": Decimal("0.8"),
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
        ("funding_income", "2026-01-31", Decimal("0.24")),
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
                "coupon_rate": Decimal("5.0"),
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
                "coupon_rate": Decimal("4.0"),
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
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
            },
            {
                "position_id": "TYW-LIAB-001",
                "counterparty_name": "Bank Liability",
                "position_scope": "liability",
                "maturity_date": date(2028, 1, 1),
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
            },
        ],
        report_date=date(2026, 1, 1),
        horizon_months=24,
    )

    assert result.asset_weighted_duration == Decimal("1.147945205479452054794520548")
    assert result.liability_weighted_duration == Decimal("1.666666666666666666666666667")
    assert result.total_asset_market_value == Decimal("200")
    assert result.total_liability_value == Decimal("150")
    # Full duration coverage: nothing excluded, coverage == 1 on both sides, so the
    # honest caliber must reproduce the textbook full-balance result exactly.
    assert result.asset_duration_covered_balance == Decimal("200")
    assert result.liability_duration_covered_balance == Decimal("150")
    assert result.asset_excluded_balance == Decimal("0")
    assert result.liability_excluded_balance == Decimal("0")
    assert result.asset_duration_coverage_ratio == Decimal("1")
    assert result.liability_duration_coverage_ratio == Decimal("1")
    # Honest caliber: DD_A = Σ(D_i * balance_i) over covered rows; DGAP uses the
    # duration-covered leverage (here L_cov/A_cov == 150/200); D_E = (DD_A - DD_L)/E.
    days_tyw_asset = Decimal((date(2026, 7, 1) - date(2026, 1, 1)).days)
    days_bond_liab = Decimal((date(2027, 1, 1) - date(2026, 1, 1)).days)
    days_tyw_liab = Decimal((date(2028, 1, 1) - date(2026, 1, 1)).days)
    asset_dollar_duration = Decimal("1.8") * Decimal("100") + (days_tyw_asset / Decimal("365")) * Decimal("100")
    liability_dollar_duration = (
        (days_bond_liab / Decimal("365")) * Decimal("50") + (days_tyw_liab / Decimal("365")) * Decimal("100")
    )
    equity = Decimal("200") - Decimal("150")
    expected_gap = result.asset_weighted_duration - (
        Decimal("150") / Decimal("200")
    ) * result.liability_weighted_duration
    expected_equity_duration = (asset_dollar_duration - liability_dollar_duration) / equity
    assert result.duration_gap == expected_gap
    assert result.modified_duration_gap == expected_gap
    assert result.equity_duration == expected_equity_duration
    # Sign convention: rates up 1bp -> equity value change = -(DD_A - DD_L) * 1bp
    assert result.rate_sensitivity_1bp == -((asset_dollar_duration - liability_dollar_duration) * Decimal("0.0001"))
    assert any("remaining-term proxy" in warning for warning in result.warnings)


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
                "coupon_rate": Decimal("4.0"),
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
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
            },
            {
                "position_id": "TYW-002",
                "counterparty_name": "Bank B",
                "position_scope": "liability",
                "maturity_date": date(2028, 1, 1),
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
            },
        ],
        report_date=date(2026, 1, 1),
        horizon_months=24,
    )

    assert result.asset_weighted_duration == Decimal("3.2")
    assert result.liability_weighted_duration == Decimal("2")
    assert result.total_asset_market_value == Decimal("300")
    assert result.total_liability_value == Decimal("200")
    # Honest caliber: the 100 liability lacking maturity is NOT assigned the covered
    # average duration; it is disclosed as excluded_balance with coverage 0.5.
    assert result.asset_duration_covered_balance == Decimal("300")
    assert result.liability_duration_covered_balance == Decimal("100")
    assert result.asset_excluded_balance == Decimal("0")
    assert result.liability_excluded_balance == Decimal("100")
    assert result.asset_duration_coverage_ratio == Decimal("1")
    assert result.liability_duration_coverage_ratio == Decimal("0.5")
    # Gap leverage now uses the duration-covered liability base (100/300), not 200/300.
    assert result.duration_gap == Decimal("3.2") - (Decimal("100") / Decimal("300")) * Decimal("2")
    assert result.modified_duration_gap == result.duration_gap
    # DD_A - DD_L = 3.2*300 - 2*100 = 760; D_E = 760/100 = 7.6.
    assert result.equity_duration == Decimal("7.6")
    assert result.rate_sensitivity_1bp == Decimal("-0.076")
    # Regression guard: the old average-duration extrapolation reported 5.6 / -0.0560.
    assert result.equity_duration != Decimal("5.6")
    assert result.rate_sensitivity_1bp != Decimal("-0.0560")
    assert any("missing maturity information" in warning for warning in result.warnings)
    assert any("does not extrapolate" in warning for warning in result.warnings)


def test_duration_gap_excludes_asset_without_duration_from_dollar_duration():
    module = _core_module()

    result = module.compute_duration_gap(
        zqtz_rows=[
            {
                "instrument_code": "BOND-DUR",
                "instrument_name": "Bond with duration",
                "position_scope": "asset",
                "maturity_date": date(2030, 1, 1),
                "market_value_amount": Decimal("100"),
                "macaulay_duration": Decimal("4"),
                "interest_mode": "annual",
                "currency_code": "CNY",
            },
            {
                "instrument_code": "BOND-NODUR",
                "instrument_name": "Asset missing duration",
                "position_scope": "asset",
                "maturity_date": None,
                "market_value_amount": Decimal("100"),
                "interest_mode": "annual",
                "currency_code": "CNY",
            },
        ],
        tyw_rows=[
            {
                "position_id": "TYW-LIAB",
                "counterparty_name": "Bank",
                "position_scope": "liability",
                "maturity_date": date(2027, 1, 1),
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
            },
        ],
        report_date=date(2026, 1, 1),
        horizon_months=24,
    )

    # 200 of asset balance, only 100 carries duration.
    assert result.total_asset_market_value == Decimal("200")
    assert result.asset_duration_covered_balance == Decimal("100")
    assert result.asset_excluded_balance == Decimal("100")
    assert result.asset_duration_coverage_ratio == Decimal("0.5")
    assert result.asset_weighted_duration == Decimal("4")
    assert result.liability_excluded_balance == Decimal("0")

    liability_duration = Decimal((date(2027, 1, 1) - date(2026, 1, 1)).days) / Decimal("365")
    assert result.liability_weighted_duration == liability_duration

    # Honest DD gap uses the covered asset balance only: 4*100 - D_L*100. The old
    # caliber applied D_A=4 to the full 200 (=> 800), inflating equity duration.
    equity = Decimal("200") - Decimal("100")
    expected_equity_dollar_duration = Decimal("4") * Decimal("100") - liability_duration * Decimal("100")
    assert result.equity_duration == expected_equity_dollar_duration / equity
    assert result.rate_sensitivity_1bp == -(expected_equity_dollar_duration * Decimal("0.0001"))
    # Gap leverage uses covered asset base (100), not the full 200.
    assert result.duration_gap == Decimal("4") - (Decimal("100") / Decimal("100")) * liability_duration
    assert result.duration_gap != Decimal("4") - (Decimal("100") / Decimal("200")) * liability_duration
    assert any("does not extrapolate" in warning for warning in result.warnings)


def test_duration_gap_zero_assets_returns_unavailable_metrics():
    module = _core_module()

    result = module.compute_duration_gap(
        zqtz_rows=[
            {
                "instrument_code": "BOND-LIAB",
                "instrument_name": "Issued bond",
                "position_scope": "liability",
                "maturity_date": date(2028, 1, 1),
                "market_value_amount": Decimal("500"),
                "coupon_rate": Decimal("3.0"),
                "interest_mode": "annual",
                "currency_code": "CNY",
            },
        ],
        tyw_rows=[],
        report_date=date(2026, 1, 1),
        horizon_months=24,
    )

    assert result.total_asset_market_value == Decimal("0")
    assert result.total_liability_value == Decimal("500")
    # Asset denominator is zero -> duration-gap family is unavailable (None), never a
    # misleading -liability_duration value.
    assert result.asset_weighted_duration is None
    assert result.duration_gap is None
    assert result.modified_duration_gap is None
    assert result.equity_duration is None
    assert result.rate_sensitivity_1bp is None
    assert result.reinvestment_risk_12m is None
    assert result.asset_duration_coverage_ratio is None
    # Liability duration is still observable and disclosed.
    liability_duration = Decimal((date(2028, 1, 1) - date(2026, 1, 1)).days) / Decimal("365")
    assert result.liability_weighted_duration == liability_duration
    assert result.liability_duration_covered_balance == Decimal("500")
    assert any("unavailable" in warning for warning in result.warnings)


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
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
            },
            {
                "position_id": "TYW-LIAB-001",
                "product_type": "同业存放",
                "counterparty_name": "Bank Liability",
                "position_scope": "liability",
                "maturity_date": None,
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("3.0"),
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
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
            },
            {
                "position_id": "TYW-LIAB-001",
                "product_type": "同业存放",
                "counterparty_name": "Bank Liability",
                "position_scope": "liability",
                "maturity_date": None,
                "principal_amount": Decimal("80"),
                "funding_cost_rate": Decimal("3.0"),
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
                "coupon_rate": Decimal("3.0"),
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
                "coupon_rate": Decimal("5.0"),
                "interest_mode": "骞翠粯",
                "currency_code": "CNY",
            },
        ],
        tyw_rows=[],
        report_date=date(2026, 1, 1),
        horizon_months=24,
    )

    assert result.reinvestment_risk_12m == Decimal("0.25")


def test_cashflow_projection_read_surface_requires_explicit_read_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{(tmp_path / 'cashflow-projection-read-scope.db').as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
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
        headers=CASHFLOW_PROJECTION_READ_HEADERS,
    )

    assert response.status_code == 403


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
                "coupon_rate": Decimal("5.0"),
                "interest_mode": "骞翠粯",
                "currency_code": "CNY",
                "source_version": "sv_bond_1",
                "rule_version": "rv_bond_1",
            }
        ]

    def fake_fetch_tyw_rows(self, *, report_date, currency_basis="CNY"):
        assert report_date == "2026-01-01"
        assert currency_basis == "CNY"
        return [
            {
                "position_id": "TYW-001",
                "counterparty_name": "Bank A",
                "position_scope": "liability",
                "maturity_date": date(2026, 3, 1),
                "principal_amount": Decimal("80"),
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
                "source_version": "sv_tyw_1",
                "rule_version": "rv_tyw_1",
            }
        ]

    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_zqtz_rows",
        fake_fetch_zqtz_rows,
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
    _grant_cashflow_projection_read_scope(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(route_mod.router)
    client = TestClient(app)
    response = client.get(
        "/api/cashflow-projection",
        params={"report_date": "2026-01-01"},
        headers=CASHFLOW_PROJECTION_READ_HEADERS,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result_meta"]["scenario_flag"] is False
    assert payload["result_meta"]["result_kind"] == "cashflow_projection.overview"
    assert payload["result_meta"]["source_surface"] == "cashflow"
    assert payload["result_meta"]["requested_report_date"] == "2026-01-01"
    assert payload["result_meta"]["resolved_report_date"] == "2026-01-01"
    assert payload["result_meta"]["as_of_date"] == "2026-01-01"
    assert payload["result_meta"]["date_basis"] == "cashflow_projection_report_date"
    assert payload["result_meta"]["filters_applied"] == {
        "report_date": "2026-01-01",
        "position_scope": "all",
        "currency_basis": "CNY",
    }
    assert payload["result_meta"]["tables_used"] == [
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
    ]
    assert payload["result_meta"]["evidence_rows"] == 2
    assert payload["result"]["report_date"] == "2026-01-01"
    assert "duration_gap" in payload["result"]
    assert payload["result"]["duration_gap"]["unit"] == "years"
    assert payload["result"]["duration_gap"]["precision"] == 2
    assert payload["result"]["duration_gap"]["sign_aware"] is True
    assert payload["result"]["asset_duration"]["unit"] == "years"
    assert payload["result"]["asset_duration"]["precision"] == 2
    assert payload["result"]["asset_duration"]["sign_aware"] is False
    assert payload["result"]["liability_duration"]["unit"] == "years"
    assert payload["result"]["liability_duration"]["precision"] == 2
    assert payload["result"]["liability_duration"]["sign_aware"] is False
    assert payload["result"]["equity_duration"]["unit"] == "years"
    assert payload["result"]["equity_duration"]["precision"] == 2
    assert payload["result"]["equity_duration"]["sign_aware"] is True
    assert payload["result"]["rate_sensitivity_1bp"]["unit"] == "yuan"
    assert payload["result"]["reinvestment_risk_12m"]["unit"] == "pct"
    assert "monthly_buckets" in payload["result"]
    assert "top_maturing_assets_12m" in payload["result"]
    assert "computed_at" in payload["result"]

    get_settings.cache_clear()


def test_api_prefers_materialized_asset_macaulay_duration(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()

    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
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

    def fake_fetch_tyw_rows(self, *, report_date, currency_basis="CNY"):
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
                "coupon_rate": Decimal("0.03"),
                "ytm": Decimal("0.035"),
                "macaulay_duration": Decimal("1.25"),
            }
        ]

    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_zqtz_rows",
        fake_fetch_zqtz_rows,
    )
    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_tyw_liability_rows",
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
    _grant_cashflow_projection_read_scope(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(route_mod.router)
    client = TestClient(app)
    response = client.get(
        "/api/cashflow-projection",
        params={"report_date": "2026-01-01"},
        headers=CASHFLOW_PROJECTION_READ_HEADERS,
    )

    assert response.status_code == 200
    payload = response.json()
    assert Decimal(str(payload["result"]["asset_duration"]["raw"])) == Decimal("1.25")

    get_settings.cache_clear()


def test_duration_fallback_uses_decimal_rates_and_semiannual_frequency():
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    bond_duration_mod = load_module(
        "backend.app.core_finance.bond_duration",
        "backend/app/core_finance/bond_duration.py",
    )
    row = {
        "report_date": date(2026, 1, 1),
        "maturity_date": date(2031, 1, 1),
        "instrument_code": "BOND-SEMI-001",
        "coupon_rate": Decimal("0.03"),
        "ytm": Decimal("0.035"),
        "interest_mode": "semi-annual",
        "macaulay_duration": None,
    }

    expected = bond_duration_mod.estimate_duration(
        date(2031, 1, 1),
        date(2026, 1, 1),
        coupon_rate=Decimal("0.03"),
        ytm=Decimal("0.035"),
        bond_code="BOND-SEMI-001",
        coupon_frequency=2,
    )

    assert service_mod._recompute_macaulay_duration(row) == expected


def test_cashflow_quality_discloses_non_preceding_bullet_value_dates():
    service_mod = load_module('backend.app.services.cashflow_projection_service', 'backend/app/services/cashflow_projection_service.py')
    maturity = date(2027, 1, 1)
    rows = [
        {'interest_mode': 'bullet', 'market_value': Decimal('50'), 'value_date': maturity, 'maturity_date': maturity},
        {'interest_mode': 'bullet', 'market_value': Decimal('70'), 'value_date': date(2027, 1, 2), 'maturity_date': maturity},
    ]
    disclosures = service_mod._cashflow_projection_quality_disclosures(rows)
    assert disclosures['bullet_value_date_fallback_count'] == 2
    assert disclosures['bullet_value_date_fallback_market_value'] == Decimal('120')
    assert any('one-year interest proxy' in warning for warning in disclosures['warnings'])


def test_cashflow_quality_disclosures_cover_frequency_floating_and_bullet_proxies():
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    rows = [
        {"interest_mode": "fixed", "market_value": Decimal("90"), "maturity_date": date(2027, 1, 1)},
        {"interest_mode": "floating", "market_value": Decimal("180"), "maturity_date": date(2027, 1, 1)},
        {"interest_mode": "fixed", "interest_payment_frequency": "semi-annual", "market_value": Decimal("70"), "maturity_date": date(2027, 1, 1)},
        {"interest_mode": "bullet", "market_value": Decimal("50"), "value_date": None, "maturity_date": date(2027, 1, 1)},
    ]

    disclosures = service_mod._cashflow_projection_quality_disclosures(rows)

    assert disclosures["payment_frequency_fallback_count"] == 2
    assert disclosures["payment_frequency_fallback_market_value"] == Decimal("270")
    assert disclosures["floating_rate_proxy_count"] == 1
    assert disclosures["floating_rate_proxy_market_value"] == Decimal("180")
    assert disclosures["bullet_value_date_fallback_count"] == 1
    assert disclosures["bullet_value_date_fallback_market_value"] == Decimal("50")


def test_attach_duration_treats_materialized_zero_as_valid():
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    key_fields = {
        "instrument_code": "MATURED-BOND",
        "portfolio_name": "P1",
        "cost_center": "C1",
        "currency_code": "CNY",
    }
    zqtz_row = {**key_fields, "position_scope": "asset"}
    analytics_row = {
        **key_fields,
        "macaulay_duration": Decimal("0"),
        "report_date": date(2026, 1, 1),
        "maturity_date": date(2031, 1, 1),
        "coupon_rate": Decimal("0.03"),
        "ytm": Decimal("0.035"),
        "interest_mode": "annual",
    }

    assert service_mod._attach_macaulay_duration([zqtz_row], [analytics_row])[0][
        "macaulay_duration"
    ] == Decimal("0")
