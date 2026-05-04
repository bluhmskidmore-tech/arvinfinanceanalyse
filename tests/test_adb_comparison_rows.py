"""Tests for ADB comparison breakdown row ordering and totals inputs."""

from datetime import date
from decimal import Decimal

from backend.app.core_finance.adb_analytics import build_comparison_rows


def test_build_comparison_rows_sorts_by_avg_balance_desc() -> None:
    spot_map = {"A": Decimal("100"), "B": Decimal("500")}
    sum_map = {"A": Decimal("600"), "B": Decimal("300")}  # 3 calendar days in range
    rows = build_comparison_rows(
        "Asset",
        spot_map,
        sum_map,
        Decimal("3"),
        None,
        False,
        date(2025, 1, 1),
        lambda *_: Decimal("1"),
    )
    assert [r["category"] for r in rows] == ["A", "B"]


def test_build_comparison_rows_top_n_truncates_after_sort() -> None:
    spot_map = {"big": Decimal("10"), "small": Decimal("10")}
    sum_map = {"big": Decimal("300"), "small": Decimal("30")}  # avg 100 vs 10 over 3 days
    rows = build_comparison_rows(
        "Asset",
        spot_map,
        sum_map,
        Decimal("3"),
        1,
        False,
        date(2025, 1, 1),
        lambda *_: Decimal("1"),
    )
    assert len(rows) == 1
    assert rows[0]["category"] == "big"
