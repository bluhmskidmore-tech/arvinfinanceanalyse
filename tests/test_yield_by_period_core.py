from __future__ import annotations

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
