from __future__ import annotations

from backend.app.core_finance import rate_units


def test_rate_units_explicit_percent_and_basis_point_conversions() -> None:
    assert rate_units.pct_to_decimal(2.55) == 0.0255
    assert rate_units.decimal_to_pct(0.0255) == 2.55
    assert rate_units.bp_to_decimal(50) == 0.005
    assert rate_units.decimal_to_bp(0.005) == 50
    assert rate_units.pct_to_bp(2.55) == 255
    assert rate_units.bp_to_pct(255) == 2.55


def test_normalize_annual_rate_to_decimal_accepts_decimal_and_percent_inputs() -> None:
    assert rate_units.normalize_annual_rate_to_decimal(0.035) == 0.035
    assert rate_units.normalize_annual_rate_to_decimal(3.5) == 0.035


def test_normalize_annual_rate_to_decimal_rejects_invalid_values() -> None:
    assert rate_units.normalize_annual_rate_to_decimal(None) is None
    assert rate_units.normalize_annual_rate_to_decimal(-1) is None
    assert rate_units.normalize_annual_rate_to_decimal(101) is None
