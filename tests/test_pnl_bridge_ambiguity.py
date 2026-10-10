from decimal import Decimal

import pytest

from backend.app.core_finance.pnl_bridge import (
    build_pnl_bridge_rows,
    required_curve_types_for_pnl_bridge,
)


def _pnl(*, basis="FVTPL", currency="CNY", code="BOND-1"):
    return {
        "report_date": "2025-12-31", "instrument_code": code,
        "portfolio_name": "Desk", "cost_center": "CC", "currency_basis": currency,
        "accounting_basis": basis, "instrument_name": "国债",
        "interest_income_514": "0", "fair_value_change_516": "-2",
        "capital_gain_517": "0", "manual_adjustment": "0", "total_pnl": "-2",
    }


def _balance(*, basis="FVTPL", currency="CNY", code="BOND-1", mv="100", duration="2"):
    return {
        "instrument_code": code, "portfolio_name": "Desk", "cost_center": "CC",
        "currency_basis": currency, "accounting_basis": basis,
        "market_value_amount": mv, "accrued_interest_amount": "0",
        "modified_duration": duration, "instrument_name": "国债",
    }


@pytest.mark.parametrize(
    ("basis", "currency", "balance_basis", "balance_currencies", "prefix"),
    [
        ("FVTPL", "CNY", "FVTPL", ("CNY", "CNY"), "DUPLICATE_BALANCE_KEY"),
        ("FVTPL", "CNY", "", ("CNY", "CNY"), "AMBIGUOUS_BALANCE_WITHOUT_BASIS_KEY"),
        ("FVTPL", "", "FVTPL", ("CNY", "USD"), "AMBIGUOUS_BALANCE_FALLBACK_KEY"),
    ],
)
def test_matched_ambiguous_balance_rejected_in_both_entry_points(
    basis, currency, balance_basis, balance_currencies, prefix
):
    pnl = [_pnl(basis=basis, currency=currency)]
    balances = [
        _balance(basis=balance_basis, currency=balance_currencies[0], mv="100", duration="2"),
        _balance(basis=balance_basis, currency=balance_currencies[1], mv="400", duration="4"),
    ]
    prior = [_balance(mv="200", duration="3")]
    errors = []
    for ordered in (balances, list(reversed(balances))):
        with pytest.raises(RuntimeError, match=prefix) as curve_error:
            required_curve_types_for_pnl_bridge(pnl, ordered, prior)
        with pytest.raises(RuntimeError, match=prefix) as bridge_error:
            build_pnl_bridge_rows(
                pnl, ordered, prior,
                treasury_curve_current={"2Y": Decimal("0.03"), "5Y": Decimal("0.03")},
                treasury_curve_prior={"2Y": Decimal("0.02"), "5Y": Decimal("0.02")},
            )
        assert str(curve_error.value) == str(bridge_error.value)
        errors.append(str(bridge_error.value))
    assert errors[0] == errors[1]


def test_unrelated_duplicate_and_broad_fallback_do_not_block_unique_exact():
    pnl = [_pnl()]
    balances = [
        _balance(),
        _balance(currency="USD", mv="400"),
        _balance(code="OTHER", mv="100"),
        _balance(code="OTHER", mv="400"),
    ]
    assert required_curve_types_for_pnl_bridge(pnl, balances, []) == {"treasury"}
    rows = build_pnl_bridge_rows(pnl, balances, [])
    assert len(rows) == 1
    assert rows[0].ending_dirty_mv == Decimal("100")
