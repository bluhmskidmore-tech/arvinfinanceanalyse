from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

from backend.app.services.product_category_source_service import (
    _parse_average_workbook,
    _parse_ledger_workbook,
)


def test_product_category_average_workbook_with_single_sheet_is_treated_as_partial_input(tmp_path: Path):
    avg_path = tmp_path / "日均202401.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "年"
    sheet["A4"] = "CNX"
    sheet["B4"] = "13304010001"
    sheet["C4"] = 123
    workbook.save(avg_path)

    annual_rows, monthly_rows = _parse_average_workbook(avg_path)

    assert annual_rows[("13304010001", "CNX")] == Decimal("123")
    assert monthly_rows == {}


def test_product_category_ledger_workbook_accepts_optional_leading_prefix_column(tmp_path: Path):
    ledger_path = tmp_path / "总账对账202401.xlsx"
    workbook = Workbook()
    cnx = workbook.active
    cnx.title = "综本"
    cny = workbook.create_sheet(title="人民币")

    for worksheet in (cnx, cny):
        worksheet.append(["header"])
        worksheet.append([None])
        worksheet.append(["header"])
        worksheet.append(["header"])
        worksheet.append(["header"])

    cnx.append(["组合科目代码", "组合科目名称", "币种", "期初余额", "本期借方", "本期贷方", "期末余额"])
    cnx.append([10101000001, "业务库存现金", "CNX", 10, 20, 5, 25])

    cny.append(["seicd", "组合科目代码", "组合科目名称", "币种", "期初余额", "本期借方", "本期贷方", "期末余额"])
    cny.append(["101", 10101000002, "ATM库存现金", "CNY", 30, 50, 15, 65])
    workbook.save(ledger_path)

    rows = _parse_ledger_workbook(ledger_path)

    assert rows[("10101000001", "CNX")]["beginning_balance"] == Decimal("10")
    assert rows[("10101000001", "CNX")]["ending_balance"] == Decimal("25")
    assert rows[("10101000001", "CNX")]["monthly_pnl"] == Decimal("-15")
    assert rows[("10101000002", "CNY")]["beginning_balance"] == Decimal("30")
    assert rows[("10101000002", "CNY")]["ending_balance"] == Decimal("65")
    assert rows[("10101000002", "CNY")]["monthly_pnl"] == Decimal("-35")
