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
    report_date: date,
    maturity_date: date,
    face_value: str,
    market_value: str = "0",
    coupon_rate: str = "0",
    interest_mode: str = "annual",
) -> dict[str, object]:
    return {
        "report_date": report_date,
        "face_value": Decimal(face_value),
        "market_value": Decimal(market_value),
        "coupon_rate": Decimal(coupon_rate),
        "interest_mode": interest_mode,
        "maturity_date": maturity_date,
        "issuer_name": "Issuer A",
    }


def _liability_row(
    *,
    maturity_date: date,
    principal_amount: str,
    funding_cost_rate: str = "0",
) -> dict[str, object]:
    return {
        "position_id": "TYW-LIAB-1",
        "counterparty_name": "Bank L",
        "position_side": "liability",
        "maturity_date": maturity_date,
        "principal_amount": Decimal(principal_amount),
        "funding_cost_rate": Decimal(funding_cost_rate),
        "currency_code": "CNY",
    }


def test_bullet_bond_maturity_within_30d():
    mod = _risk_tensor_module()
    report_date = date(2026, 3, 31)

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(
                report_date=report_date,
                maturity_date=report_date + timedelta(days=20),
                face_value="100",
                market_value="95",
                coupon_rate="0.05",
                interest_mode="bullet",
            )
        ],
        report_date=report_date,
    )

    assert tensor.liquidity_gap_30d == Decimal("105")
    assert tensor.liquidity_gap_90d == Decimal("105")


def test_annual_coupon_within_90d():
    mod = _risk_tensor_module()
    report_date = date(2026, 3, 31)

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(
                report_date=report_date,
                maturity_date=date(2030, 5, 15),
                face_value="100",
                coupon_rate="0.06",
                interest_mode="annual",
            )
        ],
        report_date=report_date,
    )

    assert tensor.liquidity_gap_30d == Decimal("0")
    assert tensor.liquidity_gap_90d == Decimal("6")


def test_annual_coupon_on_report_date_counts_in_window():
    mod = _risk_tensor_module()
    report_date = date(2026, 3, 31)

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(
                report_date=report_date,
                maturity_date=date(2030, 3, 31),
                face_value="100",
                coupon_rate="0.06",
                interest_mode="annual",
            )
        ],
        report_date=report_date,
    )

    assert tensor.liquidity_gap_30d == Decimal("6")
    assert tensor.liquidity_gap_90d == Decimal("6")


def test_semi_annual_coupon_within_30d():
    mod = _risk_tensor_module()
    report_date = date(2026, 3, 31)

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(
                report_date=report_date,
                maturity_date=date(2028, 4, 15),
                face_value="200",
                coupon_rate="0.08",
                interest_mode="semi-annual",
            )
        ],
        report_date=report_date,
    )

    assert tensor.liquidity_gap_30d == Decimal("8")
    assert tensor.liquidity_gap_90d == Decimal("8")


def test_chinese_semiannual_interest_mode_uses_half_year_coupon():
    mod = _risk_tensor_module()
    report_date = date(2026, 3, 31)

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(
                report_date=report_date,
                maturity_date=date(2028, 4, 15),
                face_value="200",
                coupon_rate="0.08",
                interest_mode="半年付息",
            )
        ],
        report_date=report_date,
    )

    assert tensor.liquidity_gap_30d == Decimal("8")
    assert tensor.liquidity_gap_90d == Decimal("8")


def test_month_end_coupon_schedule_preserves_anchor_day():
    mod = _risk_tensor_module()

    next_coupon_date = mod._find_next_coupon_date(
        report_date=date(2026, 3, 31),
        maturity_date=date(2028, 8, 31),
        interval_months=6,
    )

    assert next_coupon_date == date(2026, 8, 31)


def test_no_cashflow_outside_window():
    mod = _risk_tensor_module()
    report_date = date(2026, 3, 31)

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(
                report_date=report_date,
                maturity_date=date(2028, 8, 15),
                face_value="150",
                market_value="140",
                coupon_rate="0.05",
                interest_mode="annual",
            )
        ],
        report_date=report_date,
    )

    assert tensor.liquidity_gap_30d == Decimal("0")
    assert tensor.liquidity_gap_90d == Decimal("0")


def test_quarterly_coupon_window_counts_multiple_coupon_events_within_90d():
    mod = _risk_tensor_module()
    report_date = date(2026, 1, 30)

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(
                report_date=report_date,
                maturity_date=date(2027, 10, 30),
                face_value="120",
                coupon_rate="0.12",
                interest_mode="quarterly",
            )
        ],
        report_date=report_date,
    )

    assert tensor.liquidity_gap_30d == Decimal("3.6")
    assert tensor.liquidity_gap_90d == Decimal("7.2")


def test_mixed_portfolio_liquidity_gap():
    mod = _risk_tensor_module()
    report_date = date(2026, 3, 31)

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(
                report_date=report_date,
                maturity_date=report_date + timedelta(days=20),
                face_value="100",
                market_value="95",
                coupon_rate="0.05",
                interest_mode="bullet",
            ),
            _row(
                report_date=report_date,
                maturity_date=date(2030, 5, 15),
                face_value="100",
                coupon_rate="0.06",
                interest_mode="annual",
            ),
            _row(
                report_date=report_date,
                maturity_date=date(2028, 4, 15),
                face_value="200",
                coupon_rate="0.08",
                interest_mode="semi-annual",
            ),
            _row(
                report_date=report_date,
                maturity_date=date(2028, 8, 15),
                face_value="150",
                market_value="140",
                coupon_rate="0.05",
                interest_mode="annual",
            ),
        ],
        report_date=report_date,
    )

    assert tensor.liquidity_gap_30d == Decimal("113")
    assert tensor.liquidity_gap_90d == Decimal("119")


def test_liquidity_gap_nets_liability_outflows_within_window():
    mod = _risk_tensor_module()
    report_date = date(2026, 3, 31)

    tensor = mod.compute_portfolio_risk_tensor(
        [
            _row(
                report_date=report_date,
                maturity_date=report_date + timedelta(days=20),
                face_value="100",
                market_value="95",
                coupon_rate="0.05",
                interest_mode="bullet",
            )
        ],
        report_date=report_date,
        liability_rows=[
            _liability_row(
                maturity_date=report_date + timedelta(days=10),
                principal_amount="40",
            )
        ],
    )

    assert tensor.asset_cashflow_30d == Decimal("105")
    assert tensor.asset_cashflow_90d == Decimal("105")
    assert tensor.liability_cashflow_30d == Decimal("40")
    assert tensor.liability_cashflow_90d == Decimal("40")
    assert tensor.liquidity_gap_30d == Decimal("65")
    assert tensor.liquidity_gap_90d == Decimal("65")
    assert tensor.liquidity_gap_30d == tensor.asset_cashflow_30d - tensor.liability_cashflow_30d
    assert tensor.liquidity_gap_90d == tensor.asset_cashflow_90d - tensor.liability_cashflow_90d
