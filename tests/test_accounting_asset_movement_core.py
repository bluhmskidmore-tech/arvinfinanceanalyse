from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.accounting_asset_movement import (
    GlAccountingAssetBalance,
    ZqtzAccountingAssetBalance,
    build_accounting_asset_movement_rows,
)


def test_monthly_accounting_asset_movement_reconciles_zqtz_to_gl_141_144():
    report_date = date(2026, 2, 28)
    rows = build_accounting_asset_movement_rows(
        report_date=report_date,
        zqtz_rows=[
            ZqtzAccountingAssetBalance(
                report_date=report_date,
                accounting_basis="FVTPL",
                market_value_amount=Decimal("110"),
                amortized_cost_amount=Decimal("100"),
            ),
            ZqtzAccountingAssetBalance(
                report_date=report_date,
                accounting_basis="AC",
                market_value_amount=Decimal("260"),
                amortized_cost_amount=Decimal("265"),
            ),
            ZqtzAccountingAssetBalance(
                report_date=report_date,
                accounting_basis="FVOCI",
                market_value_amount=Decimal("80"),
                amortized_cost_amount=Decimal("75"),
            ),
        ],
        gl_rows=[
            GlAccountingAssetBalance(report_date=report_date, account_code="14101010001", beginning_balance=Decimal("100"), ending_balance=Decimal("110")),
            GlAccountingAssetBalance(report_date=report_date, account_code="14201010001", beginning_balance=Decimal("200"), ending_balance=Decimal("220")),
            GlAccountingAssetBalance(report_date=report_date, account_code="14301040001", beginning_balance=Decimal("50"), ending_balance=Decimal("45")),
            GlAccountingAssetBalance(report_date=report_date, account_code="14401010001", beginning_balance=Decimal("70"), ending_balance=Decimal("80")),
        ],
    )

    by_bucket = {row.basis_bucket: row for row in rows}

    assert by_bucket["TPL"].previous_balance == Decimal("100")
    assert by_bucket["TPL"].current_balance == Decimal("110")
    assert by_bucket["TPL"].balance_change == Decimal("10")
    assert by_bucket["TPL"].zqtz_amount == Decimal("110")
    assert by_bucket["TPL"].gl_amount == Decimal("110")
    assert by_bucket["TPL"].reconciliation_status == "matched"

    assert by_bucket["AC"].current_balance == Decimal("265")
    assert by_bucket["AC"].balance_change == Decimal("15")
    assert by_bucket["AC"].zqtz_amount == Decimal("265")
    assert by_bucket["AC"].reconciliation_status == "matched"

    assert by_bucket["OCI"].current_balance == Decimal("80")
    assert by_bucket["OCI"].balance_change == Decimal("10")
    assert by_bucket["OCI"].zqtz_amount == Decimal("80")
    assert by_bucket["OCI"].reconciliation_status == "matched"


def test_monthly_accounting_asset_movement_flags_reconciliation_mismatch():
    report_date = date(2026, 2, 28)
    rows = build_accounting_asset_movement_rows(
        report_date=report_date,
        zqtz_rows=[
            ZqtzAccountingAssetBalance(
                report_date=report_date,
                accounting_basis="FVTPL",
                market_value_amount=Decimal("111"),
                amortized_cost_amount=Decimal("100"),
            ),
        ],
        gl_rows=[
            GlAccountingAssetBalance(report_date=report_date, account_code="14101010001", beginning_balance=Decimal("100"), ending_balance=Decimal("110")),
        ],
        tolerance=Decimal("0.01"),
    )

    tpl = next(row for row in rows if row.basis_bucket == "TPL")
    assert tpl.reconciliation_diff == Decimal("1")
    assert tpl.reconciliation_status == "mismatch"
