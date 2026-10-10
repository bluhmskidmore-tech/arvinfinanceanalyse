from __future__ import annotations

import pytest

from backend.app.core_finance.field_normalization import (
    derive_accounting_basis_value,
    is_approved_status,
    normalize_currency_basis_value,
    original_asset_currency_from_instrument_code,
    resolve_pnl_source_currency,
)


def test_is_approved_status_is_case_and_whitespace_insensitive() -> None:
    assert is_approved_status("approved")
    assert is_approved_status(" APPROVED ")
    assert not is_approved_status("approved in comment")
    assert not is_approved_status("pending")


@pytest.mark.parametrize(
    ("invest_type", "expected_basis"),
    [("T", "FVTPL"), ("A", "FVOCI"), ("H", "AC")],
)
def test_derive_accounting_basis_value_maps_each_invest_type(
    invest_type: str,
    expected_basis: str,
) -> None:
    assert derive_accounting_basis_value(invest_type) == expected_basis  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("CNY", "CNY"),
        ("人民币", "CNY"),
        ("RMB", "CNY"),
        ("CNH", "CNY"),
        ("CNX", "CNX"),
        ("综本", "CNX"),
    ],
)
def test_normalize_currency_basis_value(raw: str, expected: str) -> None:
    assert normalize_currency_basis_value(raw) == expected


def test_resolve_pnl_source_currency_marks_usd_for_fx_conversion() -> None:
    assert resolve_pnl_source_currency("USD") == ("CNY", "USD")
    assert resolve_pnl_source_currency("人民币") == ("CNY", None)
    assert resolve_pnl_source_currency("综本") == ("CNX", None)


@pytest.mark.parametrize(
    ("instrument_code", "expected_currency"),
    [("J1001", "USD"), ("j1-lower", "USD"), ("JM001", "CNY"), ("J4001", "CNY"), ("P001", "CNY")],
)
def test_original_asset_currency_uses_confirmed_j1_rule(
    instrument_code: str,
    expected_currency: str,
) -> None:
    assert original_asset_currency_from_instrument_code(instrument_code) == expected_currency
