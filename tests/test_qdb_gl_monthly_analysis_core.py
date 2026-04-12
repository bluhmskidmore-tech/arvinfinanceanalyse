from __future__ import annotations

from io import BytesIO
from pathlib import Path

from openpyxl import Workbook, load_workbook

from tests.helpers import load_module


B = 100_000_000


def test_parse_daily_avg_coerces_codes_and_builds_expected_groups(tmp_path):
    module = load_module(
        "backend.app.core_finance.qdb_gl_monthly_analysis",
        "backend/app/core_finance/qdb_gl_monthly_analysis.py",
    )
    avg_path, _ledger_path = _write_month_pair(tmp_path, "202602")

    parsed = module.parse_daily_avg(avg_path)

    assert sorted(parsed) == [
        "年日均_CNX_11d",
        "年日均_CNX_3d",
        "年日均_CNX_5d",
        "年日均_CNX_7d",
        "年日均_CNY_11d",
        "年日均_CNY_3d",
        "年日均_CNY_5d",
        "年日均_CNY_7d",
        "月日均_CNX_11d",
        "月日均_CNX_3d",
        "月日均_CNX_5d",
        "月日均_CNX_7d",
        "月日均_CNY_11d",
        "月日均_CNY_3d",
        "月日均_CNY_5d",
        "月日均_CNY_7d",
    ]
    month_11 = parsed["月日均_CNX_11d"]
    assert "12301000001" in {row["科目代码"] for row in month_11}
    assert next(row["日均余额"] for row in month_11 if row["科目代码"] == "14001000001") == 230 * B


def test_build_workbook_payload_computes_metrics_gap_alerts_and_foreign_split(tmp_path):
    module = load_module(
        "backend.app.core_finance.qdb_gl_monthly_analysis",
        "backend/app/core_finance/qdb_gl_monthly_analysis.py",
    )
    avg_path, ledger_path = _write_month_pair(tmp_path, "202602")

    parsed_avg = module.parse_daily_avg(avg_path)
    parsed_ledger = module.parse_general_ledger(ledger_path)
    merged = module.merge_all(parsed_ledger, parsed_avg)
    workbook = module.build_qdb_gl_monthly_analysis_workbook(
        report_month="202602",
        merged_data=merged,
    )

    sheet_titles = [sheet["title"] for sheet in workbook["sheets"]]
    assert sheet_titles == [
        "经营概览",
        "3位科目总览",
        "资产结构",
        "负债结构",
        "贷款行业",
        "存款行业_活期",
        "存款行业_定期",
        "行业存贷差",
        "11位偏离TOP",
        "异动预警",
        "外币分析",
    ]

    overview = next(sheet for sheet in workbook["sheets"] if sheet["key"] == "overview")
    overview_rows = {row["指标"]: row["值"] for row in overview["rows"]}
    assert overview_rows["贷款总额(亿)"] == 1000
    assert overview_rows["存款总额(亿)"] == 1600
    assert overview_rows["存贷比%"] == 62.5
    assert overview_rows["拨贷比%"] == 3

    gap_sheet = next(sheet for sheet in workbook["sheets"] if sheet["key"] == "industry_gap")
    agriculture = next(row for row in gap_sheet["rows"] if row["行业"] == "农林牧渔")
    assert agriculture["存贷差_时点"] == -600
    assert agriculture["存贷差_日均"] == -400

    alerts_sheet = next(sheet for sheet in workbook["sheets"] if sheet["key"] == "alerts")
    alerts = {(row["科目代码"], row["异动类型"]) for row in alerts_sheet["rows"]}
    assert ("14001000001", "同业业务月末操纵嫌疑") in alerts
    assert ("13001000001", "逾期贷款异动") in alerts
    assert ("23401000001", "同业业务月末操纵嫌疑") in alerts

    foreign_sheet = next(sheet for sheet in workbook["sheets"] if sheet["key"] == "foreign_currency")
    foreign_rows = {row["科目代码"]: row for row in foreign_sheet["rows"]}
    assert foreign_rows["14201000001"]["外币部分"] == 50
    assert foreign_rows["14401000001"]["外币部分"] == 30


def test_exported_workbook_contains_all_required_sheets(tmp_path):
    module = load_module(
        "backend.app.core_finance.qdb_gl_monthly_analysis",
        "backend/app/core_finance/qdb_gl_monthly_analysis.py",
    )
    avg_path, ledger_path = _write_month_pair(tmp_path, "202602")
    workbook = module.build_qdb_gl_monthly_analysis_workbook(
        report_month="202602",
        merged_data=module.merge_all(
            module.parse_general_ledger(ledger_path),
            module.parse_daily_avg(avg_path),
        ),
    )

    content = module.export_qdb_gl_monthly_analysis_workbook_xlsx_bytes(workbook)
    exported = load_workbook(BytesIO(content))
    assert "经营概览" in exported.sheetnames
    assert "异动预警" in exported.sheetnames
    assert "外币分析" in exported.sheetnames


def _write_month_pair(target_dir: Path, month_key: str) -> tuple[Path, Path]:
    avg_path = target_dir / f"日均{month_key}.xlsx"
    ledger_path = target_dir / f"总账对账{month_key}.xlsx"
    _write_average_workbook(avg_path)
    _write_ledger_workbook(ledger_path)
    return avg_path, ledger_path


def _write_average_workbook(path: Path) -> None:
    workbook = Workbook()
    year_sheet = workbook.active
    year_sheet.title = "年"
    month_sheet = workbook.create_sheet(title="月")

    for worksheet in (year_sheet, month_sheet):
        worksheet.append(["机构：199200青岛银行"])
        worksheet.append(["日期：2026-02-01 至 2026-02-28"])
        worksheet.append([None] * 31)

    month_rows = [
        _avg_row(cnx_3="101", cnx_3_val=18 * B, cny_3="101", cny_3_val=18 * B),
        _avg_row(cnx_3="110", cnx_3_val=28 * B, cny_3="110", cny_3_val=28 * B),
        _avg_row(cnx_3="114", cnx_3_val=20 * B, cny_3="114", cny_3_val=20 * B),
        _avg_row(cnx_3="123", cnx_3_val=900 * B, cnx_5="12301", cnx_5_val=1100 * B, cnx_11="12301000001", cnx_11_val=900 * B,
                 cny_3="123", cny_3_val=900 * B, cny_5="12301", cny_5_val=1100 * B, cny_11="12301000001", cny_11_val=900 * B),
        _avg_row(cnx_3="130", cnx_3_val=8 * B, cnx_11="13001000001", cnx_11_val=8 * B, cny_3="130", cny_3_val=8 * B, cny_11="13001000001", cny_11_val=8 * B),
        _avg_row(cnx_3="131", cnx_3_val=-28 * B, cnx_11="13101000001", cnx_11_val=-28 * B, cny_3="131", cny_3_val=-28 * B, cny_11="13101000001", cny_11_val=-28 * B),
        _avg_row(cnx_3="140", cnx_3_val=230 * B, cnx_11="14001000001", cnx_11_val=230 * B, cny_3="140", cny_3_val=230 * B, cny_11="14001000001", cny_11_val=230 * B),
        _avg_row(cnx_3="142", cnx_3_val=280 * B, cnx_11="14201000001", cnx_11_val=280 * B, cny_3="142", cny_3_val=260 * B, cny_11="14201000001", cny_11_val=260 * B),
        _avg_row(cnx_3="144", cnx_3_val=170 * B, cnx_11="14401000001", cnx_11_val=170 * B, cny_3="144", cny_3_val=150 * B, cny_11="14401000001", cny_11_val=150 * B),
        _avg_row(cnx_3="201", cnx_3_val=-650 * B, cnx_5="20101", cnx_5_val=-650 * B, cnx_11="20101000001", cnx_11_val=-650 * B,
                 cny_3="201", cny_3_val=-650 * B, cny_5="20101", cny_5_val=-650 * B, cny_11="20101000001", cny_11_val=-650 * B),
        _avg_row(cnx_3="205", cnx_3_val=-850 * B, cnx_5="20501", cnx_5_val=-850 * B, cnx_11="20501000001", cnx_11_val=-850 * B,
                 cny_3="205", cny_3_val=-850 * B, cny_5="20501", cny_5_val=-850 * B, cny_11="20501000001", cny_11_val=-850 * B),
        _avg_row(cnx_3="234", cnx_3_val=-269 * B, cnx_11="23401000001", cnx_11_val=-269 * B, cny_3="234", cny_3_val=-269 * B, cny_11="23401000001", cny_11_val=-269 * B),
        _avg_row(cnx_3="255", cnx_3_val=-197 * B, cnx_11="25501000001", cnx_11_val=-197 * B, cny_3="255", cny_3_val=-197 * B, cny_11="25501000001", cny_11_val=-197 * B),
    ]
    year_rows = [
        _avg_row(cnx_3="101", cnx_3_val=17 * B, cny_3="101", cny_3_val=17 * B),
        _avg_row(cnx_3="110", cnx_3_val=26 * B, cny_3="110", cny_3_val=26 * B),
        _avg_row(cnx_3="114", cnx_3_val=18 * B, cny_3="114", cny_3_val=18 * B),
        _avg_row(cnx_3="123", cnx_3_val=850 * B, cnx_5="12301", cnx_5_val=900 * B, cnx_11="12301000001", cnx_11_val=850 * B,
                 cny_3="123", cny_3_val=850 * B, cny_5="12301", cny_5_val=900 * B, cny_11="12301000001", cny_11_val=850 * B),
        _avg_row(cnx_3="130", cnx_3_val=5 * B, cnx_11="13001000001", cnx_11_val=5 * B, cny_3="130", cny_3_val=5 * B, cny_11="13001000001", cny_11_val=5 * B),
        _avg_row(cnx_3="131", cnx_3_val=-25 * B, cnx_11="13101000001", cnx_11_val=-25 * B, cny_3="131", cny_3_val=-25 * B, cny_11="13101000001", cny_11_val=-25 * B),
        _avg_row(cnx_3="140", cnx_3_val=220 * B, cnx_11="14001000001", cnx_11_val=220 * B, cny_3="140", cny_3_val=220 * B, cny_11="14001000001", cny_11_val=220 * B),
        _avg_row(cnx_3="142", cnx_3_val=260 * B, cnx_11="14201000001", cnx_11_val=260 * B, cny_3="142", cny_3_val=240 * B, cny_11="14201000001", cny_11_val=240 * B),
        _avg_row(cnx_3="144", cnx_3_val=160 * B, cnx_11="14401000001", cnx_11_val=160 * B, cny_3="144", cny_3_val=140 * B, cny_11="14401000001", cny_11_val=140 * B),
        _avg_row(cnx_3="201", cnx_3_val=-620 * B, cnx_5="20101", cnx_5_val=-600 * B, cnx_11="20101000001", cnx_11_val=-620 * B,
                 cny_3="201", cny_3_val=-620 * B, cny_5="20101", cny_5_val=-600 * B, cny_11="20101000001", cny_11_val=-620 * B),
        _avg_row(cnx_3="205", cnx_3_val=-830 * B, cnx_5="20501", cnx_5_val=-800 * B, cnx_11="20501000001", cnx_11_val=-830 * B,
                 cny_3="205", cny_3_val=-830 * B, cny_5="20501", cny_5_val=-800 * B, cny_11="20501000001", cny_11_val=-830 * B),
        _avg_row(cnx_3="234", cnx_3_val=-250 * B, cnx_11="23401000001", cnx_11_val=-250 * B, cny_3="234", cny_3_val=-250 * B, cny_11="23401000001", cny_11_val=-250 * B),
        _avg_row(cnx_3="255", cnx_3_val=-180 * B, cnx_11="25501000001", cnx_11_val=-180 * B, cny_3="255", cny_3_val=-180 * B, cny_11="25501000001", cny_11_val=-180 * B),
    ]

    for row in year_rows:
        year_sheet.append(row)
    for row in month_rows:
        month_sheet.append(row)

    workbook.save(path)


def _avg_row(
    *,
    cnx_3=None,
    cnx_3_val=None,
    cnx_5=None,
    cnx_5_val=None,
    cnx_11=None,
    cnx_11_val=None,
    cny_3=None,
    cny_3_val=None,
    cny_5=None,
    cny_5_val=None,
    cny_11=None,
    cny_11_val=None,
):
    row = [None] * 31
    if cnx_3 is not None:
        row[0] = "CNX"
        row[1] = float(cnx_3)
        row[2] = cnx_3_val
    if cnx_5 is not None:
        row[4] = "CNX"
        row[5] = float(cnx_5)
        row[6] = cnx_5_val
    if cnx_11 is not None:
        row[12] = "CNX"
        row[13] = float(cnx_11)
        row[14] = cnx_11_val
    if cny_3 is not None:
        row[16] = "CNY"
        row[17] = float(cny_3)
        row[18] = cny_3_val
    if cny_5 is not None:
        row[20] = "CNY"
        row[21] = float(cny_5)
        row[22] = cny_5_val
    if cny_11 is not None:
        row[28] = "CNY"
        row[29] = float(cny_11)
        row[30] = cny_11_val
    return row


def _write_ledger_workbook(path: Path) -> None:
    workbook = Workbook()
    default = workbook.active
    workbook.remove(default)

    for sheet_name, currency in (("综本", "CNX"), ("人民币", "CNY")):
        worksheet = workbook.create_sheet(title=sheet_name)
        worksheet.append(["总账对账"])
        worksheet.append([None])
        worksheet.append(["分类账来源"])
        worksheet.append(["公司：青岛银行"])
        worksheet.append(["会计期间：2026-02-01--2026-02-28"])
        worksheet.append(["组合科目代码", "组合科目名称", "币种", "期初余额", "本期借方", "本期贷方", "期末余额"])
        for row in _ledger_rows(currency):
            worksheet.append(row)

    workbook.save(path)


def _ledger_rows(currency: str):
    return [
        _balanced_ledger_row("10101000001", "现金", currency, 18 * B, 20 * B),
        _balanced_ledger_row("11001000001", "存放央行", currency, 28 * B, 30 * B),
        _balanced_ledger_row("11401000001", "存放同业", currency, 20 * B, 25 * B),
        _balanced_ledger_row("12301000001", "公司贷款-农林牧渔", currency, 900 * B, 1000 * B),
        _balanced_ledger_row("13001000001", "逾期贷款", currency, 50 * B, 86 * B),
        _balanced_ledger_row("13101000001", "贷款减值准备", currency, -28 * B, -30 * B),
        _balanced_ledger_row("14001000001", "买入返售", currency, 230 * B, 58 * B),
        _balanced_ledger_row("14201000001", "AC债券投资", currency, (280 if currency == "CNX" else 240) * B, (310 if currency == "CNX" else 260) * B),
        _balanced_ledger_row("14401000001", "FVOCI金融资产", currency, (170 if currency == "CNX" else 140) * B, (180 if currency == "CNX" else 150) * B),
        _balanced_ledger_row("20101000001", "单位活期存款-农林牧渔", currency, -650 * B, -700 * B),
        _balanced_ledger_row("20501000001", "单位定期存款-农林牧渔", currency, -850 * B, -900 * B),
        _balanced_ledger_row("23401000001", "同业存放", currency, -269 * B, -359 * B),
        _balanced_ledger_row("25501000001", "卖出回购", currency, -197 * B, -60 * B),
    ]


def _balanced_ledger_row(
    account_code: str,
    account_name: str,
    currency: str,
    opening_balance: float,
    ending_balance: float,
):
    delta = ending_balance - opening_balance
    debit = delta if delta >= 0 else 0
    credit = abs(delta) if delta < 0 else 0
    return (account_code, account_name, currency, opening_balance, debit, credit, ending_balance)
