from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.bond_four_effects import (
    compute_bond_four_effects,
    compute_bond_six_effects,
)


def _sample_trading_bond(**overrides):
    bond = {
        "bond_code": "240001.IB",
        "market_value_start": Decimal("100"),
        "market_value_end": Decimal("101"),
        "face_value_start": Decimal("100"),
        "coupon_rate_start": Decimal("0.05"),
        "yield_to_maturity_start": Decimal("0.04"),
        "asset_class_start": "交易性金融资产",
        "maturity_date_start": date(2028, 1, 1),
    }
    bond.update(overrides)
    return bond


def test_compute_bond_four_effects_uses_full_price_basis_when_accrued_interest_is_present() -> None:
    effects = compute_bond_four_effects(
        bond=_sample_trading_bond(
            accrued_interest_start=Decimal("1.0"),
            accrued_interest_end=Decimal("1.5"),
        ),
        num_days=365,
        benchmark_yield_change=Decimal("0"),
        spread_change=Decimal("0"),
        report_date=date(2026, 1, 1),
    )

    assert effects["income_return"] == Decimal("5.00")
    assert effects["total_return"] == Decimal("1.5")
    assert effects["selection_effect"] == Decimal("-3.50")
    assert effects["mod_duration"] > Decimal("0")


def test_compute_bond_four_effects_zeroes_market_effects_for_ac_positions() -> None:
    effects = compute_bond_four_effects(
        bond=_sample_trading_bond(
            asset_class_start="持有至到期债权投资",
            market_value_end=Decimal("102"),
        ),
        num_days=365,
        benchmark_yield_change=Decimal("0.01"),
        spread_change=Decimal("0.002"),
        report_date=date(2026, 1, 1),
    )

    assert effects["income_return"] == Decimal("5.00")
    assert effects["treasury_effect"] == Decimal("0")
    assert effects["spread_effect"] == Decimal("0")
    assert effects["selection_effect"] == Decimal("0")
    assert effects["total_return"] == effects["income_return"]
    assert effects["total_price_change"] == Decimal("2")


def test_compute_bond_six_effects_preserves_component_identity_for_trading_positions() -> None:
    effects = compute_bond_six_effects(
        bond=_sample_trading_bond(market_value_end=Decimal("98")),
        num_days=365,
        benchmark_yield_change=Decimal("0.01"),
        spread_change=Decimal("0.005"),
        report_date=date(2026, 1, 1),
    )

    reconstructed = (
        effects["income_return"]
        + effects["treasury_effect"]
        + effects["spread_effect"]
        + effects["convexity_effect"]
        + effects["cross_effect"]
        + effects["reinvestment_effect"]
        + effects["selection_effect"]
    )

    assert effects["convexity_effect"] > Decimal("0")
    assert effects["cross_effect"] > Decimal("0")
    assert reconstructed == effects["total_return"]
