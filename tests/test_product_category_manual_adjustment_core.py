from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.product_category_pnl import (
    CanonicalFactRow,
    ManualAdjustment,
    apply_manual_adjustments,
)


def test_apply_manual_adjustments_treats_approved_status_case_and_whitespace_insensitively() -> None:
    rows = [
        CanonicalFactRow(
            report_date=date(2026, 2, 28),
            account_code="13304010001",
            currency="CNX",
            account_name="测试科目",
            beginning_balance=Decimal("0"),
            ending_balance=Decimal("100"),
            monthly_pnl=Decimal("10"),
            daily_avg_balance=Decimal("80"),
            annual_avg_balance=Decimal("75"),
            days_in_period=28,
        )
    ]
    adjustments = [
        ManualAdjustment(
            report_date=date(2026, 2, 28),
            operator="DELTA",
            approval_status=" APPROVED ",
            account_code="13304010001",
            currency="CNX",
            monthly_pnl=Decimal("5"),
        )
    ]

    adjusted = apply_manual_adjustments(rows, adjustments)

    assert len(adjusted) == 1
    assert adjusted[0].monthly_pnl == Decimal("15")
