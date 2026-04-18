from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance import bond_duration


def test_compute_macaulay_duration_returns_years_to_maturity_for_zero_coupon() -> None:
    years = Decimal("5")

    assert (
        bond_duration.compute_macaulay_duration(
            years_to_maturity=years,
            coupon_rate=Decimal("0"),
            ytm=Decimal("0.032"),
        )
        == years
    )


def test_estimate_duration_returns_zero_for_matured_bond() -> None:
    assert bond_duration.estimate_duration(
        maturity_date=date(2026, 3, 30),
        report_date=date(2026, 3, 31),
        coupon_rate=Decimal("0.03"),
        bond_code="240001.IB",
        ytm=Decimal("0.03"),
    ) == Decimal("0")


def test_modified_duration_from_macaulay_keeps_duration_for_negative_yield() -> None:
    assert bond_duration.modified_duration_from_macaulay(
        duration=Decimal("4.25"),
        ytm=Decimal("-0.01"),
        coupon_frequency=2,
    ) == Decimal("4.25")


def test_estimate_duration_prefers_wind_duration_when_available() -> None:
    assert bond_duration.estimate_duration(
        maturity_date=date(2031, 3, 31),
        report_date=date(2026, 3, 31),
        coupon_rate=Decimal("0.03"),
        bond_code="240001.IB",
        ytm=Decimal("0.031"),
        wind_metrics={"240001.IB": {"duration": Decimal("2.75")}},
    ) == Decimal("2.75")


@pytest.mark.parametrize("bond_code", ["SA2301", "scp999"])
def test_estimate_duration_short_term_codes_return_quarter_year(bond_code: str) -> None:
    assert bond_duration.estimate_duration(
        maturity_date=None,
        report_date=date(2026, 3, 31),
        coupon_rate=Decimal("0.03"),
        bond_code=bond_code,
        ytm=Decimal("0.03"),
    ) == Decimal("0.25")


@pytest.mark.parametrize(
    ("asset_class", "expected"),
    [
        ("债权投资", "AC"),
        ("交易性金融资产", "TPL"),
        ("可供出售金融资产", "OCI"),
        (None, "TPL"),
    ],
)
def test_infer_accounting_class_maps_supported_labels(
    asset_class: str | None,
    expected: str,
) -> None:
    assert bond_duration.infer_accounting_class(asset_class) == expected
