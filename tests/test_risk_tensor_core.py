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


def test_six_month_tenor_maps_to_nearest_one_year_krd_bucket():
    mod = _risk_tensor_module()

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(dv01="0.25", tenor_bucket="6M"),
            _row(dv01="1.00", tenor_bucket="1Y"),
        ],
        report_date=date(2026, 3, 31),
    )

    assert tensor.krd_1y == Decimal("1.25")
    assert not any("Unsupported tenor buckets excluded" in warning for warning in tensor.warnings)


def test_zero_dv01_fallback_buckets_do_not_appear_in_remap_warning():
    mod = _risk_tensor_module()

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(dv01="-0E-8", tenor_bucket="6M"),
            _row(dv01="0.00000000", tenor_bucket="20Y"),
            _row(dv01="1.00", tenor_bucket="1Y"),
        ],
        report_date=date(2026, 3, 31),
    )

    assert tensor.krd_1y == Decimal("1.00")
    assert tensor.krd_30y == Decimal("0")
    assert not any("Non-standard tenor buckets remapped" in warning for warning in tensor.warnings)


def test_nonzero_fallback_rows_still_warn_when_bucket_nets_to_zero():
    mod = _risk_tensor_module()

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(dv01="0.00000001", tenor_bucket="20Y"),
            _row(dv01="-0.00000001", tenor_bucket="20Y"),
        ],
        report_date=date(2026, 3, 31),
    )

    assert tensor.krd_30y == Decimal("0")
    assert any(
        warning == "Non-standard tenor buckets remapped to nearest KRD bucket: 20Y"
        for warning in tensor.warnings
    )


def test_nonzero_missing_tenor_bucket_is_excluded_and_explicitly_warned():
    mod = _risk_tensor_module()

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(dv01="2.50", tenor_bucket=""),
            _row(dv01="-2.00", tenor_bucket=None),
            _row(dv01="0", tenor_bucket=""),
            _row(dv01="1.00", tenor_bucket="1Y"),
        ],
        report_date=date(2026, 3, 31),
    )

    assert tensor.portfolio_dv01 == Decimal("1.50")
    assert tensor.krd_1y == Decimal("1.00")
    assert sum(
        (
            tensor.krd_1y,
            tensor.krd_3y,
            tensor.krd_5y,
            tensor.krd_7y,
            tensor.krd_10y,
            tensor.krd_30y,
        ),
        Decimal("0"),
    ) == Decimal("1.00")
    assert tensor.quality_flag == "warning"
    assert any(
        "2 rows with missing tenor_bucket and non-zero DV01 excluded" in warning
        and "net_dv01=0.50" in warning
        for warning in tensor.warnings
    )


def test_unknown_tenor_nonzero_dv01_warns_while_zero_and_fallback_rows_do_not():
    mod = _risk_tensor_module()

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(dv01="3.00", tenor_bucket="UNMAPPED"),
            _row(dv01="0", tenor_bucket="ALSO_UNMAPPED"),
            _row(dv01="2.00", tenor_bucket="2Y"),
        ],
        report_date=date(2026, 3, 31),
    )

    assert tensor.portfolio_dv01 == Decimal("5.00")
    assert tensor.krd_3y == Decimal("2.00")
    assert any(
        warning == "Unsupported tenor buckets excluded from minimal KRD tensor: UNMAPPED"
        for warning in tensor.warnings
    )
    assert any(
        warning == "Non-standard tenor buckets remapped to nearest KRD bucket: 2Y"
        for warning in tensor.warnings
    )


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


def test_input_quality_metadata_counts_assumption_based_rows_without_excluding_them():
    mod = _risk_tensor_module()
    report_date = date(2026, 3, 31)
    maturity_date = report_date + timedelta(days=365)
    rows = [
        _row(dv01="1", market_value="100", maturity_date=maturity_date)
        | {
            "modified_duration": Decimal("1"),
            "duration_quality_flag": "observed",
        },
        _row(dv01="2", market_value="200", maturity_date=maturity_date)
        | {
            "modified_duration": Decimal("1"),
            "duration_quality_flag": "ytm_par_fallback",
        },
        _row(dv01="3", market_value="300", maturity_date=maturity_date)
        | {
            "modified_duration": Decimal("1"),
            "duration_quality_flag": "ytm_unavailable",
        },
        _row(dv01="4", market_value="400", maturity_date=maturity_date)
        | {
            "modified_duration": Decimal("1"),
            "duration_quality_flag": "coupon_unavailable",
        },
        _row(dv01="5", market_value="500", maturity_date=report_date)
        | {
            "modified_duration": Decimal("0"),
            "duration_quality_flag": "no_remaining_term",
        },
    ]

    tensor = mod.compute_portfolio_risk_tensor(rows, report_date=report_date)

    assert tensor.input_quality_metadata == {
        "assumption_value_row_count": 3,
        "total_row_count": 5,
    }
    assert tensor.portfolio_dv01 == Decimal("15")
    assert tensor.bond_count == 5
    assert any(
        "3 of 5 bond analytics rows use assumption-based duration inputs" in warning
        for warning in tensor.warnings
    )


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
    assert "0 matured on or before report_date with outstanding market_value" in warning
    assert "1 future-dated with non-positive modified_duration" in warning
    assert tensor.rate_risk_market_value == Decimal("100000000")
    assert tensor.rate_risk_dv01 == Decimal("40000")
    assert tensor.rate_risk_modified_duration == Decimal("4")
    assert tensor.duration_excluded_market_value == Decimal("400000000")
    assert tensor.duration_excluded_count == 2
    assert tensor.missing_maturity_market_value == Decimal("300000000")
    assert tensor.missing_maturity_count == 1


def test_duration_exclusion_warning_separates_matured_outstanding_rows():
    mod = _risk_tensor_module()
    report_date = date(2026, 6, 30)

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(
                dv01="40000",
                market_value="100000000",
                maturity_date=report_date + timedelta(days=365),
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
                market_value="200000000",
                maturity_date=report_date - timedelta(days=1),
            )
            | {"modified_duration": Decimal("2")},
            _row(
                dv01="0",
                market_value="100000000",
                maturity_date=report_date + timedelta(days=180),
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
    assert "1 without maturity_date (market_value=300000000)" in warning
    assert (
        "1 matured on or before report_date with outstanding market_value "
        "(market_value=200000000)"
    ) in warning
    assert (
        "1 future-dated with non-positive modified_duration (market_value=100000000)"
    ) in warning
    assert tensor.rate_risk_market_value == Decimal("100000000")
    assert tensor.duration_excluded_market_value == Decimal("600000000")
    assert tensor.duration_excluded_count == 3


def test_invalid_nonempty_maturity_date_counts_as_missing_maturity_in_warning_breakdown():
    mod = _risk_tensor_module()
    report_date = date(2026, 6, 30)

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(
                dv01="40000",
                market_value="100000000",
                maturity_date=report_date + timedelta(days=365),
            )
            | {"modified_duration": Decimal("4")},
            _row(
                dv01="0",
                market_value="300000000",
            )
            | {"maturity_date": "not-a-date", "modified_duration": Decimal("0")},
            _row(
                dv01="0",
                market_value="200000000",
                maturity_date=report_date - timedelta(days=1),
            )
            | {"modified_duration": Decimal("2")},
            _row(
                dv01="0",
                market_value="100000000",
                maturity_date=report_date + timedelta(days=180),
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
    assert "3 rows" in warning
    assert "market_value=600000000" in warning
    assert "1 without maturity_date (market_value=300000000)" in warning
    assert (
        "1 matured on or before report_date with outstanding market_value "
        "(market_value=200000000)"
    ) in warning
    assert (
        "1 future-dated with non-positive modified_duration (market_value=100000000)"
    ) in warning
    assert tensor.rate_risk_market_value == Decimal("100000000")
    assert tensor.duration_excluded_market_value == Decimal("600000000")
    assert tensor.duration_excluded_count == 3
    assert tensor.missing_maturity_market_value == Decimal("300000000")
    assert tensor.missing_maturity_count == 1


def test_duration_exclusion_disclosure_separates_funds_unknown_dates_and_matured_balances():
    mod = _risk_tensor_module()
    report_date = date(2026, 8, 31)
    rows = [
        _row(market_value="100", maturity_date=None)
        | {"instrument_code": "SA-FUND", "bond_type": "其他", "modified_duration": Decimal("0")},
        _row(market_value="20", maturity_date=None)
        | {"instrument_code": "BOND-UNKNOWN", "bond_type": "国债", "modified_duration": Decimal("0")},
        _row(market_value="30", maturity_date=None)
        | {"instrument_code": "SA-INVALID", "bond_type": "其他", "maturity_date": "invalid", "modified_duration": Decimal("0")},
        _row(market_value="40", maturity_date=report_date)
        | {"instrument_code": "BOND-TODAY", "modified_duration": Decimal("0")},
        _row(market_value="10", maturity_date=report_date - timedelta(days=1))
        | {"instrument_code": "BOND-PAST", "modified_duration": Decimal("0")},
        _row(market_value="0", maturity_date=report_date - timedelta(days=1))
        | {"instrument_code": "BOND-SETTLED", "modified_duration": Decimal("0")},
        _row(market_value="5", maturity_date=report_date + timedelta(days=1))
        | {"instrument_code": "BOND-ZERO-DURATION", "modified_duration": Decimal("0")},
        _row(dv01="2", market_value="200", maturity_date=report_date + timedelta(days=365))
        | {"instrument_code": "SA-TERM-FUND", "bond_type": "其他", "modified_duration": Decimal("2")},
    ]

    tensor = mod.compute_portfolio_risk_tensor(rows, report_date=report_date)

    assert tensor.total_market_value == Decimal("405")
    assert tensor.rate_risk_market_value == Decimal("200")
    assert tensor.portfolio_modified_duration == Decimal("2")
    assert tensor.portfolio_dv01 == Decimal("2")
    assert tensor.duration_excluded_market_value == Decimal("205")
    assert tensor.duration_excluded_count == 6
    assert tensor.missing_maturity_market_value == Decimal("150")
    assert tensor.missing_maturity_count == 3
    assert (tensor.fund_no_maturity_market_value, tensor.fund_no_maturity_count) == (Decimal("100"), 1)
    assert (tensor.unknown_maturity_market_value, tensor.unknown_maturity_count) == (Decimal("50"), 2)
    assert (tensor.matured_outstanding_market_value, tensor.matured_outstanding_count) == (Decimal("50"), 2)
    assert (tensor.nonpositive_duration_market_value, tensor.nonpositive_duration_count) == (Decimal("5"), 1)
    assert sum(
        (
            tensor.fund_no_maturity_market_value,
            tensor.unknown_maturity_market_value,
            tensor.matured_outstanding_market_value,
            tensor.nonpositive_duration_market_value,
        )
    ) == tensor.duration_excluded_market_value
    assert any("fund_no_maturity" in warning and "unknown_maturity" in warning for warning in tensor.warnings)
    assert not any("until inputs are remediated" in warning for warning in tensor.warnings)


def test_nonempty_invalid_fund_maturity_values_remain_unknown():
    mod = _risk_tensor_module()
    report_date = date(2026, 8, 31)
    rows = [
        _row(market_value="10", maturity_date=None)
        | {"instrument_code": "SA-ZERO", "bond_type": "其他", "maturity_date": 0},
        _row(market_value="20", maturity_date=None)
        | {"instrument_code": "SA-FALSE", "bond_type": "其他", "maturity_date": False},
    ]

    tensor = mod.compute_portfolio_risk_tensor(rows, report_date=report_date)

    assert tensor.fund_no_maturity_count == 0
    assert tensor.unknown_maturity_count == 2
    assert tensor.unknown_maturity_market_value == Decimal("30")
