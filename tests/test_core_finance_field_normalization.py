from __future__ import annotations

import pytest

from backend.app.core_finance.field_normalization import (
    derive_accounting_basis_value,
    derive_invest_type_std_value,
    is_approved_status,
    normalize_currency_basis_value,
    resolve_pnl_source_currency,
)


def test_is_approved_status_is_case_and_whitespace_insensitive() -> None:
    assert is_approved_status("approved")
    assert is_approved_status(" APPROVED ")
    assert not is_approved_status("approved in comment")
    assert not is_approved_status("pending")


@pytest.mark.parametrize(
    ("raw", "expected_type", "expected_basis"),
    [
        ("交易性金融资产", "T", "FVTPL"),
        ("TRADING_ASSET_RAW", "T", "FVTPL"),
        ("可供出售债券", "A", "FVOCI"),
        ("FVOCI", "A", "FVOCI"),
        ("持有至到期投资", "H", "AC"),
        ("应收投资款项", "H", "AC"),
        ("摊余成本", "H", "AC"),
    ],
)
def test_invest_type_and_accounting_basis_use_shared_mapping(
    raw: str,
    expected_type: str,
    expected_basis: str,
) -> None:
    invest_type = derive_invest_type_std_value(raw)
    assert invest_type == expected_type
    assert derive_accounting_basis_value(invest_type) == expected_basis


def test_invest_type_shared_mapping_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="Unrecognized invest_type_raw"):
        derive_invest_type_std_value("未知口径")


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
