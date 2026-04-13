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
    assert tensor.krd_30y == Decimal("0")
    assert tensor.quality_flag == "warning"
    assert any("Unsupported tenor buckets" in warning for warning in tensor.warnings)
    assert any("without maturity_date" in warning for warning in tensor.warnings)
    assert any("Total market value is zero" in warning for warning in tensor.warnings)
