from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.product_category_pnl import (
    CanonicalFactRow,
    _calculate_sum,
    _matches_account,
    _normalize_pattern,
)


def _row(account_code: str, *, currency: str = "CNX", daily_avg_balance: str = "0", monthly_pnl: str = "0") -> CanonicalFactRow:
    return CanonicalFactRow(
        report_date=date(2026, 1, 31),
        account_code=account_code,
        currency=currency,
        account_name=account_code,
        beginning_balance=Decimal("0"),
        ending_balance=Decimal("0"),
        monthly_pnl=Decimal(monthly_pnl),
        daily_avg_balance=Decimal(daily_avg_balance),
        annual_avg_balance=Decimal("0"),
        days_in_period=31,
    )


def test_normalize_pattern_matches_v1_sign_convention() -> None:
    assert _normalize_pattern(None) == (0, "")
    assert _normalize_pattern("") == (0, "")
    assert _normalize_pattern("143") == (1, "143")
    assert _normalize_pattern(" 51401 ") == (1, "51401")
    assert _normalize_pattern("-14301010002") == (-1, "14301010002")


def test_matches_account_supports_exact_and_prefix_modes() -> None:
    assert _matches_account("14301010002", "143", exact=False) is True
    assert _matches_account("14301010002", "14301010002", exact=False) is True
    assert _matches_account("14301010002", "14301010002", exact=True) is True
    assert _matches_account("14301010002", "143", exact=True) is False
    assert _matches_account("51401000002", "51401", exact=False) is True
    assert _matches_account("51401000002", "51402", exact=False) is False


def test_calculate_sum_uses_prefix_matching_for_pnl_fields() -> None:
    rows = [
        _row("51401000001", monthly_pnl="5"),
        _row("51401000002", monthly_pnl="7"),
        _row("51402000001", monthly_pnl="11"),
    ]

    total = _calculate_sum(
        rows,
        ["51401", "-51401000002"],
        "monthly_pnl",
        "CNX",
        exact=False,
    )

    assert total == Decimal("5")


def test_calculate_sum_uses_exact_matching_when_requested() -> None:
    rows = [
        _row("140", daily_avg_balance="100"),
        _row("14004000001", daily_avg_balance="10"),
        _row("14005000001", daily_avg_balance="5"),
    ]

    total = _calculate_sum(
        rows,
        ["140", "-14004", "-14005"],
        "daily_avg_balance",
        "CNX",
        exact=True,
    )

    assert total == Decimal("100")
