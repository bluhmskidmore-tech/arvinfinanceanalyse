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
