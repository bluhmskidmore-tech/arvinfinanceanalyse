from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from backend.app.services.product_category_source_service import (
    LedgerWorkbookSheetError,
    SourcePair,
    _parse_average_workbook,
    _parse_ledger_workbook,
    build_canonical_facts,
)


def _ledger_workbook_with_named_sheets(
    *sheet_titles: str,
    report_date: date = date(2024, 1, 31),
) -> Workbook:
    workbook = Workbook()
    first, *rest = sheet_titles
    workbook.active.title = first
    for title in rest:
        workbook.create_sheet(title=title)
    for worksheet in workbook.worksheets:
        for _ in range(5):
            worksheet.append(["header"])
        worksheet.append(
            ["组合科目代码", "组合科目名称", "币种", "期初余额", "本期借方", "本期贷方", "期末余额"]
        )
        worksheet["A5"] = f"会计期间： {report_date.replace(day=1)}--{report_date}"
    return workbook


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


def test_product_category_average_workbook_ignores_misaligned_non_currency_blocks(tmp_path: Path):
    avg_path = tmp_path / "日均202401.xlsx"
    workbook = Workbook()
    year_sheet = workbook.active
    year_sheet.title = "annual"
    month_sheet = workbook.create_sheet(title="monthly")

    for sheet in (year_sheet, month_sheet):
        row = [None] * 20
        row[12] = "CNX"
        row[13] = "23401000001"
        row[14] = 100
        row[16] = "23402000001"
        row[17] = -20
        row[18] = 20
        sheet.append(["header"])
        sheet.append(["header"])
        sheet.append(["header"])
        sheet.append(row)

    workbook.save(avg_path)

    annual_rows, monthly_rows = _parse_average_workbook(avg_path)

    assert annual_rows[("23401000001", "CNX")] == Decimal("100")
    assert monthly_rows[("23401000001", "CNX")] == Decimal("100")
    assert all(currency in {"CNX", "CNY"} for _code, currency in annual_rows)
    assert all(currency in {"CNX", "CNY"} for _code, currency in monthly_rows)
    assert ("-20", "23402000001") not in annual_rows
    assert ("-20", "23402000001") not in monthly_rows


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

    cnx["A5"] = "会计期间： 2024-01-01--2024-01-31"
    cny["B5"] = "会计期间： 2024-01-01--2024-01-31"
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


@pytest.mark.parametrize(
    "sheet_titles",
    [
        ("Sheet1", "人民币"),
        ("综本", "Sheet2"),
        ("青岛地区综本", "人民币账"),
    ],
)
def test_product_category_ledger_workbook_fails_loud_when_named_sheet_missing(
    tmp_path: Path,
    sheet_titles: tuple[str, ...],
):
    """R7：总账 sheet 必须按名称精确匹配「综本」「人民币」，缺失即抛类型化异常。"""
    ledger_path = tmp_path / "总账对账202401.xlsx"
    _ledger_workbook_with_named_sheets(*sheet_titles).save(ledger_path)

    with pytest.raises(LedgerWorkbookSheetError, match="missing required sheet"):
        _parse_ledger_workbook(ledger_path)


def test_product_category_ledger_workbook_selects_sheets_by_name_not_position(
    tmp_path: Path,
):
    """R7：即使「青岛地区综本」被移到前两个位置，也只解析「综本」「人民币」。"""
    ledger_path = tmp_path / "总账对账202401.xlsx"
    workbook = _ledger_workbook_with_named_sheets("青岛地区综本", "综本", "人民币")
    workbook["青岛地区综本"].append([90909000001, "青岛污染行", "CNX", 1, 2, 3, 4])
    workbook["综本"].append([10101000001, "业务库存现金", "CNX", 10, 20, 5, 25])
    workbook["人民币"].append([10101000001, "业务库存现金", "CNY", 30, 50, 15, 65])
    workbook.save(ledger_path)

    rows = _parse_ledger_workbook(ledger_path)

    assert set(rows) == {("10101000001", "CNX"), ("10101000001", "CNY")}
    assert ("90909000001", "CNX") not in rows


def test_product_category_ledger_202412_preserves_verified_preclosing_source(tmp_path: Path):
    ledger_path = tmp_path / "总账对账202412.xlsx"
    workbook = _ledger_workbook_with_named_sheets(
        "结转后综本", "结转后人民币", "结转前综本", "结转前人民币",
        report_date=date(2024, 12, 31),
    )
    for title, currency in (("综本", "CNX"), ("人民币", "CNY")):
        workbook[f"结转前{title}"].append([10101000001, "库存现金", currency, 10, 20, 5, 25])
        workbook[f"结转后{title}"].append([10101000001, "库存现金", currency, 10, 20, 50, 70])
    workbook.save(ledger_path)

    rows = _parse_ledger_workbook(ledger_path)

    assert set(rows) == {("10101000001", "CNX"), ("10101000001", "CNY")}
    for row in rows.values():
        assert row["ending_balance"] == Decimal("25")
        assert row["monthly_pnl"] == Decimal("-15")


@pytest.mark.parametrize(
    ("filename", "sheet_titles"),
    [
        ("总账对账202512.xlsx", ("结转前综本", "结转前人民币")),
        ("总账对账202412.xlsx", ("结转前综本", "结转后人民币")),
        ("总账对账202412.xlsx", ("综本", "结转前综本", "结转前人民币")),
    ],
)
def test_product_category_ledger_legacy_names_do_not_relax_other_checks(
    tmp_path: Path, filename: str, sheet_titles: tuple[str, ...]
):
    ledger_path = tmp_path / filename
    _ledger_workbook_with_named_sheets(*sheet_titles).save(ledger_path)
    with pytest.raises(LedgerWorkbookSheetError, match="missing required sheet"):
        _parse_ledger_workbook(ledger_path)


def test_product_category_ledger_workbook_warns_on_duplicate_account_currency_key(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
):
    """R8：同 (科目,币种) 键重复时保留"后行覆盖前行"，但产生 warning 证据。"""
    ledger_path = tmp_path / "总账对账202401.xlsx"
    workbook = _ledger_workbook_with_named_sheets("综本", "人民币")
    workbook["综本"].append([10101000001, "业务库存现金", "CNX", 10, 20, 5, 25])
    workbook["综本"].append([10101000001, "业务库存现金", "CNX", 11, 21, 6, 26])
    workbook.save(ledger_path)

    with caplog.at_level(logging.WARNING):
        rows = _parse_ledger_workbook(ledger_path)

    duplicate_records = [
        record for record in caplog.records
        if "ledger.duplicate_full_code" in record.getMessage()
    ]
    assert len(duplicate_records) == 1
    assert "10101000001" in duplicate_records[0].getMessage()
    # 覆盖行为保持不变（金额语义不变）。
    assert rows[("10101000001", "CNX")]["ending_balance"] == Decimal("26")


def test_build_canonical_facts_tags_ledger_and_average_only_rows(tmp_path: Path):
    """R1：构建端打标——缺总账侧填 0 的行为 average_only，其余为 ledger。"""
    ledger_path = tmp_path / "总账对账202401.xlsx"
    ledger_workbook = _ledger_workbook_with_named_sheets("综本", "人民币")
    ledger_workbook["综本"].append([10101000001, "业务库存现金", "CNX", 10, 20, 5, 25])
    ledger_workbook.save(ledger_path)

    avg_path = tmp_path / "日均202401.xlsx"
    avg_workbook = Workbook()
    annual_sheet = avg_workbook.active
    annual_sheet.title = "年"
    monthly_sheet = avg_workbook.create_sheet(title="月")
    for sheet in (annual_sheet, monthly_sheet):
        for _ in range(3):
            sheet.append(["header"])
        sheet.append(["CNX", "10101000001", 100])
        sheet.append(["CNX", "13304010001", 55])
    avg_workbook.save(avg_path)

    pair = SourcePair(
        month_key="202401",
        report_date=date(2024, 1, 31),
        ledger_path=ledger_path,
        avg_path=avg_path,
        source_version="sv_test_pair",
    )

    facts = build_canonical_facts(pair)

    by_key = {(fact.account_code, fact.currency): fact for fact in facts}
    ledger_fact = by_key[("10101000001", "CNX")]
    synthetic_fact = by_key[("13304010001", "CNX")]
    assert ledger_fact.source_presence == "ledger"
    assert ledger_fact.ending_balance == Decimal("25")
    assert synthetic_fact.source_presence == "average_only"
    assert synthetic_fact.account_name == ""
    assert synthetic_fact.beginning_balance == Decimal("0")
    assert synthetic_fact.ending_balance == Decimal("0")
    assert synthetic_fact.monthly_pnl == Decimal("0")
    assert synthetic_fact.daily_avg_balance == Decimal("55")
