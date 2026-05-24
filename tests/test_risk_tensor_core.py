from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from tests.helpers import load_module


def _risk_tensor_module():
    return load_module(
        "backend.app.core_finance.risk_tensor",
        "backend/app/core_finance/risk_tensor.py",
    )


def _row(
    *,
    dv01: str = "0",
    tenor_bucket: str = "5Y",
    is_credit: bool = False,
    spread_dv01: str = "0",
    convexity: str = "0",
    market_value: str = "0",
    face_value: str | None = None,
    coupon_rate: str = "0",
    interest_mode: str = "annual",
    issuer_name: str = "Issuer A",
    maturity_date: date | None = None,
    accounting_class: str = "AC",
) -> dict[str, object]:
    return {
        "dv01": Decimal(dv01),
        "tenor_bucket": tenor_bucket,
        "is_credit": is_credit,
        "spread_dv01": Decimal(spread_dv01),
        "convexity": Decimal(convexity),
        "market_value": Decimal(market_value),
        "face_value": Decimal(face_value if face_value is not None else market_value),
        "coupon_rate": Decimal(coupon_rate),
        "interest_mode": interest_mode,
        "issuer_name": issuer_name,
        "maturity_date": maturity_date,
        "accounting_class": accounting_class,
    }


def test_dv01_is_sum_of_bond_dv01s():
    mod = _risk_tensor_module()

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(dv01="1.25", tenor_bucket="1Y"),
            _row(dv01="2.75", tenor_bucket="5Y"),
            _row(dv01="-0.50", tenor_bucket="10Y"),
        ],
        report_date=date(2026, 3, 31),
    )

    assert tensor.portfolio_dv01 == Decimal("3.50")


def test_regulatory_dv01_defaults_to_direct_net_sum_of_included_rows():
    mod = _risk_tensor_module()

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(dv01="1.25", tenor_bucket="1Y"),
            _row(dv01="2.75", tenor_bucket="5Y"),
            _row(dv01="-0.50", tenor_bucket="10Y"),
        ],
        report_date=date(2026, 3, 31),
    )

    assert tensor.portfolio_dv01 == Decimal("3.50")
    assert tensor.regulatory_dv01 == Decimal("3.50")


def test_regulatory_dv01_scope_rules_can_exclude_future_rows():
    mod = _risk_tensor_module()
    scope_mod = load_module(
        "backend.app.core_finance.risk_tensor_regulatory_scope",
        "backend/app/core_finance/risk_tensor_regulatory_scope.py",
    )

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(dv01="1.25", accounting_class="AC"),
            _row(dv01="2.75", accounting_class="OCI"),
            _row(dv01="-0.50", accounting_class="TPL"),
        ],
        report_date=date(2026, 3, 31),
        regulatory_scope_rules=[
            scope_mod.RegulatoryDv01ScopeRule(
                rule_id="test_include_only_ac_oci",
                rule_version="test_v1",
                include=True,
                match_fields={"accounting_class": ("AC", "OCI")},
            )
        ],
    )

    assert tensor.portfolio_dv01 == Decimal("3.50")
    assert tensor.regulatory_dv01 == Decimal("4.00")


def test_regulatory_dv01_scope_exclude_overrides_default_include_all():
    mod = _risk_tensor_module()
    scope_mod = load_module(
        "backend.app.core_finance.risk_tensor_regulatory_scope",
        "backend/app/core_finance/risk_tensor_regulatory_scope.py",
    )

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(dv01="1.25", accounting_class="AC"),
            _row(dv01="2.75", accounting_class="OCI"),
            _row(dv01="-0.50", accounting_class="TPL"),
        ],
        report_date=date(2026, 3, 31),
        regulatory_scope_rules=[
            scope_mod.DEFAULT_REGULATORY_DV01_SCOPE_RULE,
            scope_mod.RegulatoryDv01ScopeRule(
                rule_id="test_exclude_tpl",
                rule_version="test_v1",
                include=False,
                match_fields={"accounting_class": ("TPL",)},
            ),
        ],
    )

    assert tensor.portfolio_dv01 == Decimal("3.50")
    assert tensor.regulatory_dv01 == Decimal("4.00")


def test_krd_buckets_sum_to_portfolio_dv01():
    mod = _risk_tensor_module()

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(dv01="1.00", tenor_bucket="1Y"),
            _row(dv01="2.00", tenor_bucket="3Y"),
            _row(dv01="3.00", tenor_bucket="5Y"),
            _row(dv01="4.00", tenor_bucket="7Y"),
            _row(dv01="5.00", tenor_bucket="10Y"),
            _row(dv01="6.00", tenor_bucket="30Y"),
        ],
        report_date=date(2026, 3, 31),
    )

    assert (
        tensor.krd_1y
        + tensor.krd_3y
        + tensor.krd_5y
        + tensor.krd_7y
        + tensor.krd_10y
        + tensor.krd_30y
    ) == tensor.portfolio_dv01


def test_cs01_only_includes_credit_bonds():
    mod = _risk_tensor_module()

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(is_credit=True, spread_dv01="10.50"),
            _row(is_credit=False, spread_dv01="99.99"),
            _row(is_credit=True, spread_dv01="-2.25"),
        ],
        report_date=date(2026, 3, 31),
    )

    assert tensor.cs01 == Decimal("8.25")


def test_issuer_hhi_calculation():
    mod = _risk_tensor_module()

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(issuer_name="Issuer A", market_value="60"),
            _row(issuer_name="Issuer B", market_value="30"),
            _row(issuer_name="Issuer C", market_value="10"),
        ],
        report_date=date(2026, 3, 31),
    )

    assert tensor.total_market_value == Decimal("100")
    assert tensor.issuer_concentration_hhi == Decimal("0.46")
    assert tensor.issuer_top5_weight == Decimal("1")


def test_calc_hhi_for_group_matches_v1_style_sum_of_squared_weights():
    mod = _risk_tensor_module()

    hhi = mod._calc_hhi_for_group(
        [Decimal("60"), Decimal("30"), Decimal("10")],
        Decimal("100"),
    )

    assert hhi == Decimal("0.46")


def test_calc_hhi_for_group_returns_zero_when_total_market_value_is_zero():
    mod = _risk_tensor_module()

    assert mod._calc_hhi_for_group([Decimal("10"), Decimal("20")], Decimal("0")) == Decimal("0")


def test_liquidity_gap_date_filter():
    mod = _risk_tensor_module()
    report_date = date(2026, 3, 31)

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(market_value="100", maturity_date=report_date + timedelta(days=10)),
            _row(market_value="200", maturity_date=report_date + timedelta(days=40)),
            _row(market_value="300", maturity_date=report_date + timedelta(days=100)),
            _row(market_value="400", maturity_date=report_date - timedelta(days=5)),
            _row(market_value="500", maturity_date=None),
        ],
        report_date=report_date,
    )

    assert tensor.asset_cashflow_30d == Decimal("100")
    assert tensor.asset_cashflow_90d == Decimal("300")
    assert tensor.liability_cashflow_30d == Decimal("0")
    assert tensor.liability_cashflow_90d == Decimal("0")
    assert tensor.liquidity_gap_30d == Decimal("100")
    assert tensor.liquidity_gap_90d == Decimal("300")
    assert tensor.liquidity_gap_30d == tensor.asset_cashflow_30d - tensor.liability_cashflow_30d
    assert tensor.liquidity_gap_90d == tensor.asset_cashflow_90d - tensor.liability_cashflow_90d


def test_empty_rows_returns_zero_tensor():
    mod = _risk_tensor_module()

    tensor = mod.compute_portfolio_risk_tensor([], report_date=date(2026, 3, 31))

    assert tensor.portfolio_dv01 == Decimal("0")
    assert tensor.regulatory_dv01 == Decimal("0")
    assert tensor.krd_1y == Decimal("0")
    assert tensor.cs01 == Decimal("0")
    assert tensor.portfolio_convexity == Decimal("0")
    assert tensor.issuer_concentration_hhi == Decimal("0")
    assert tensor.asset_cashflow_30d == Decimal("0")
    assert tensor.asset_cashflow_90d == Decimal("0")
    assert tensor.liability_cashflow_30d == Decimal("0")
    assert tensor.liability_cashflow_90d == Decimal("0")
    assert tensor.liquidity_gap_30d == Decimal("0")
    assert tensor.liquidity_gap_30d_ratio == Decimal("0")
    assert tensor.portfolio_modified_duration == Decimal("0")
    assert tensor.total_market_value == Decimal("0")
    assert tensor.bond_count == 0
    assert tensor.quality_flag == "warning"
    assert tensor.warnings


def test_warning_paths_flag_degraded_tensor_inputs():
    mod = _risk_tensor_module()
    report_date = date(2026, 3, 31)

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(
                dv01="1.00",
                tenor_bucket="20Y",
                market_value="0",
                maturity_date=None,
            ),
        ],
        report_date=report_date,
    )

    assert tensor.portfolio_dv01 == Decimal("1.00")
    assert tensor.krd_1y == Decimal("0")
    assert tensor.krd_30y == Decimal("1.00")
    assert tensor.quality_flag == "warning"
    assert any("Non-standard tenor buckets remapped" in warning for warning in tensor.warnings)
    assert any("without maturity_date" in warning for warning in tensor.warnings)
    assert any("Total market value is zero" in warning for warning in tensor.warnings)


def test_missing_maturity_market_value_warns_that_duration_and_dv01_are_zeroed():
    mod = _risk_tensor_module()
    report_date = date(2026, 3, 31)

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(
                dv01="0",
                market_value="100000000",
                maturity_date=None,
            ),
        ],
        report_date=report_date,
    )

    assert tensor.quality_flag == "warning"
    assert any(
        "excluded from portfolio duration denominator" in warning
        and "market_value=100000000" in warning
        for warning in tensor.warnings
    )


def test_missing_maturity_assets_do_not_dilute_portfolio_duration_denominator():
    mod = _risk_tensor_module()
    report_date = date(2026, 3, 31)

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(
                dv01="40000",
                market_value="100000000",
                maturity_date=report_date + timedelta(days=365 * 4),
            )
            | {"modified_duration": Decimal("4")},
            _row(
                dv01="0",
                market_value="300000000",
                maturity_date=None,
            )
            | {"modified_duration": Decimal("0")},
        ],
        report_date=report_date,
    )

    assert tensor.total_market_value == Decimal("400000000")
    assert tensor.portfolio_dv01 == Decimal("40000")
    assert tensor.portfolio_modified_duration == Decimal("4")


def test_duration_exclusion_warning_counts_all_rows_outside_duration_denominator():
    mod = _risk_tensor_module()
    report_date = date(2026, 3, 31)

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(
                dv01="40000",
                market_value="100000000",
                maturity_date=report_date + timedelta(days=365 * 4),
            )
            | {"modified_duration": Decimal("4")},
            _row(
                dv01="0",
                market_value="300000000",
                maturity_date=None,
            )
            | {"modified_duration": Decimal("0")},
            _row(
                dv01="0",
                market_value="100000000",
                maturity_date=report_date + timedelta(days=365),
            )
            | {"modified_duration": Decimal("0")},
        ],
        report_date=report_date,
    )

    warning = next(
        warning
        for warning in tensor.warnings
        if "excluded from portfolio duration denominator" in warning
    )
    assert "2 rows" in warning
    assert "market_value=400000000" in warning
    assert "1 without maturity_date" in warning
    assert "1 with non-positive modified_duration" in warning
