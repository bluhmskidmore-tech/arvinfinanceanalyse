from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from backend.app.core_finance.yield_by_period import rollup_yield_periods


def test_rollup_yield_periods_monthly_groups_by_year_month() -> None:
    rows = [
        {
            "report_date": "2025-01-31",
            "business_type_primary": "A",
            "total_pnl": Decimal("10"),
            "scale_amount": Decimal("100"),
        },
        {
            "report_date": "2025-01-31",
            "business_type_primary": "B",
            "total_pnl": Decimal("5"),
            "scale_amount": Decimal("100"),
        },
        {
            "report_date": "2025-02-28",
            "business_type_primary": "A",
            "total_pnl": Decimal("3"),
            "scale_amount": Decimal("50"),
        },
    ]
    out = rollup_yield_periods(rows, year=2025, period_type="monthly")
    assert [p["period"] for p in out] == ["2025-01", "2025-02"]
    jan = out[0]
    assert jan["num_days"] == 31
    assert jan["period_days"] == 31
    assert jan["covered_days"] == 31  # full month observed (last row is month-end)
    assert jan["total_pnl"] == 15.0
    assert jan["total_avg_balance"] == 200.0
    assert abs(float(jan["overall_yield"] or 0) - 7.5) < 1e-9


def test_rollup_yield_periods_filters_other_calendar_year() -> None:
    rows = [
        {"report_date": "2024-12-31", "business_type_primary": "X", "total_pnl": Decimal("99"), "scale_amount": Decimal("1")},
        {"report_date": "2025-06-30", "business_type_primary": "X", "total_pnl": Decimal("1"), "scale_amount": Decimal("1")},
    ]
    out = rollup_yield_periods(rows, year=2025, period_type="monthly")
    assert len(out) == 1
    assert out[0]["period"] == "2025-06"


def test_rollup_yield_periods_quarterly_uses_average_month_end_scale() -> None:
    """季桶分母 = 各月末规模均值，不是月末规模之和（P1-05 / audit H-1）。"""
    rows = [
        {
            "report_date": "2025-01-31",
            "business_type_primary": "A",
            "total_pnl": Decimal("10"),
            "scale_amount": Decimal("100"),
        },
        {
            "report_date": "2025-02-28",
            "business_type_primary": "A",
            "total_pnl": Decimal("10"),
            "scale_amount": Decimal("100"),
        },
        {
            "report_date": "2025-03-31",
            "business_type_primary": "A",
            "total_pnl": Decimal("10"),
            "scale_amount": Decimal("100"),
        },
    ]
    out = rollup_yield_periods(rows, year=2025, period_type="quarterly")
    assert len(out) == 1
    q1 = out[0]
    assert q1["period"] == "2025-Q1"
    assert q1["num_days"] == 90
    assert q1["period_days"] == 90
    assert q1["covered_days"] == 90  # full quarter observed (last row is quarter-end)
    assert q1["total_pnl"] == 30.0
    assert q1["total_avg_balance"] == 100.0
    assert abs(float(q1["overall_yield"] or 0) - 30.0) < 1e-9
    # (30/100) * (365/90) * 100 — full quarter observed, so annualization factor
    # is unchanged by the covered-days fix (regression guard).
    expected_ann = 30.0 / 100.0 * (365.0 / 90.0) * 100.0
    assert abs(float(q1["overall_annualized_yield"] or 0) - expected_ann) < 1e-9


def test_rollup_yield_periods_yearly_uses_average_month_end_scale() -> None:
    rows = [
        {"report_date": "2025-01-31", "business_type_primary": "A", "total_pnl": Decimal("1"), "scale_amount": Decimal("100")},
        {"report_date": "2025-02-28", "business_type_primary": "A", "total_pnl": Decimal("1"), "scale_amount": Decimal("100")},
        {"report_date": "2025-03-31", "business_type_primary": "A", "total_pnl": Decimal("1"), "scale_amount": Decimal("100")},
        {"report_date": "2025-04-30", "business_type_primary": "A", "total_pnl": Decimal("1"), "scale_amount": Decimal("100")},
        {"report_date": "2025-05-31", "business_type_primary": "A", "total_pnl": Decimal("1"), "scale_amount": Decimal("100")},
        {"report_date": "2025-06-30", "business_type_primary": "A", "total_pnl": Decimal("1"), "scale_amount": Decimal("100")},
        {"report_date": "2025-07-31", "business_type_primary": "A", "total_pnl": Decimal("1"), "scale_amount": Decimal("100")},
        {"report_date": "2025-08-31", "business_type_primary": "A", "total_pnl": Decimal("1"), "scale_amount": Decimal("100")},
        {"report_date": "2025-09-30", "business_type_primary": "A", "total_pnl": Decimal("1"), "scale_amount": Decimal("100")},
        {"report_date": "2025-10-31", "business_type_primary": "A", "total_pnl": Decimal("1"), "scale_amount": Decimal("100")},
        {"report_date": "2025-11-30", "business_type_primary": "A", "total_pnl": Decimal("1"), "scale_amount": Decimal("100")},
        {"report_date": "2025-12-31", "business_type_primary": "A", "total_pnl": Decimal("1"), "scale_amount": Decimal("100")},
    ]
    out = rollup_yield_periods(rows, year=2025, period_type="yearly")
    assert len(out) == 1
    y = out[0]
    assert y["total_pnl"] == 12.0
    assert y["total_avg_balance"] == 100.0
    assert abs(float(y["overall_yield"] or 0) - 12.0) < 1e-9
    # Full-year regression: all 12 months observed, so num_days stays the nominal
    # 365 and covered_days must match it exactly (annualization factor unchanged).
    assert y["num_days"] == 365
    assert y["period_days"] == 365
    assert y["covered_days"] == 365
    expected_ann = 12.0 / 100.0 * (365.0 / 365.0) * 100.0
    assert abs(float(y["overall_annualized_yield"] or 0) - expected_ann) < 1e-9


def test_rollup_yield_periods_leap_year_full_coverage_uses_366_days() -> None:
    rows = [
        {"report_date": f"2024-{m:02d}-{monthrange(2024, m)[1]:02d}", "business_type_primary": "A", "total_pnl": Decimal("1"), "scale_amount": Decimal("100")}
        for m in range(1, 13)
    ]
    out = rollup_yield_periods(rows, year=2024, period_type="yearly")
    y = out[0]
    assert y["num_days"] == 366
    assert y["period_days"] == 366
    assert y["covered_days"] == 366
    expected_ann = 12.0 / 100.0 * (365.0 / 366.0) * 100.0
    assert abs(float(y["overall_annualized_yield"] or 0) - expected_ann) < 1e-9


def test_rollup_yield_periods_in_progress_year_annualizes_by_covered_days_not_365() -> None:
    """YTD bug fix: 8 months of data must annualize by actual elapsed days (Jan 1
    through Aug 31), not by the full nominal 365-day year (audit Medium fix)."""
    rows = [
        {
            "report_date": f"2025-{m:02d}-{monthrange(2025, m)[1]:02d}",
            "business_type_primary": "A",
            "total_pnl": Decimal("10"),
            "scale_amount": Decimal("1000"),
        }
        for m in range(1, 9)
    ]
    out = rollup_yield_periods(rows, year=2025, period_type="yearly")
    assert len(out) == 1
    y = out[0]
    covered_days = (date(2025, 8, 31) - date(2025, 1, 1)).days + 1  # 243
    assert y["num_days"] == 365
    assert y["period_days"] == 365
    assert y["covered_days"] == covered_days
    assert y["total_pnl"] == 80.0
    assert y["total_avg_balance"] == 1000.0
    # (80/1000) * (365/243) * 100 — using actual covered days, not 365.
    expected_ann = 80.0 / 1000.0 * (365.0 / covered_days) * 100.0
    assert abs(float(y["overall_annualized_yield"] or 0) - expected_ann) < 1e-9
    # Sanity: the old (buggy) 365-day annualization would have been materially
    # smaller than the corrected value (systemic understatement).
    buggy_ann = 80.0 / 1000.0 * (365.0 / 365.0) * 100.0
    assert float(y["overall_annualized_yield"]) > buggy_ann


def test_rollup_yield_periods_mid_month_annualizes_by_elapsed_days_not_full_month() -> None:
    rows = [
        {
            "report_date": "2025-01-15",
            "business_type_primary": "A",
            "total_pnl": Decimal("5"),
            "scale_amount": Decimal("100"),
        },
    ]
    out = rollup_yield_periods(rows, year=2025, period_type="monthly")
    jan = out[0]
    assert jan["num_days"] == 31
    assert jan["period_days"] == 31
    assert jan["covered_days"] == 15
    expected_ann = 5.0 / 100.0 * (365.0 / 15.0) * 100.0
    assert abs(float(jan["overall_annualized_yield"] or 0) - expected_ann) < 1e-9


def test_rollup_yield_periods_single_day_at_period_start_covered_days_is_one() -> None:
    rows = [
        {
            "report_date": "2025-01-01",
            "business_type_primary": "A",
            "total_pnl": Decimal("1"),
            "scale_amount": Decimal("100"),
        },
    ]
    out = rollup_yield_periods(rows, year=2025, period_type="monthly")
    jan = out[0]
    assert jan["covered_days"] == 1
    expected_ann = 1.0 / 100.0 * (365.0 / 1.0) * 100.0
    assert abs(float(jan["overall_annualized_yield"] or 0) - expected_ann) < 1e-9


def test_rollup_yield_periods_empty_rows_returns_empty_list() -> None:
    assert rollup_yield_periods([], year=2025, period_type="yearly") == []
    assert rollup_yield_periods([], year=2025, period_type="monthly") == []


def test_rollup_yield_periods_quarterly_sums_same_date_business_types_before_average() -> None:
    rows = [
        {
            "report_date": "2025-01-31",
            "business_type_primary": "A",
            "total_pnl": Decimal("5"),
            "scale_amount": Decimal("40"),
        },
        {
            "report_date": "2025-01-31",
            "business_type_primary": "B",
            "total_pnl": Decimal("5"),
            "scale_amount": Decimal("60"),
        },
        {
            "report_date": "2025-02-28",
            "business_type_primary": "A",
            "total_pnl": Decimal("4"),
            "scale_amount": Decimal("50"),
        },
        {
            "report_date": "2025-02-28",
            "business_type_primary": "B",
            "total_pnl": Decimal("6"),
            "scale_amount": Decimal("50"),
        },
    ]
    out = rollup_yield_periods(rows, year=2025, period_type="quarterly")
    q1 = out[0]
    # dates: Jan scale 100, Feb scale 100 → avg 100; pnl 20
    assert q1["total_avg_balance"] == 100.0
    assert q1["total_pnl"] == 20.0
    items = {i["business_type_primary"]: i for i in q1["items"]}
    assert items["A"]["scale_amount"] == 45.0  # (40+50)/2
    assert items["B"]["scale_amount"] == 55.0  # (60+50)/2
