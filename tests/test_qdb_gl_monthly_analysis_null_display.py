"""Regression guards for missing-versus-zero cells on the landed QDB summary."""

from decimal import Decimal

import pytest

from backend.app.core_finance.qdb_gl_monthly_analysis import build_qdb_gl_monthly_analysis_workbook
from backend.app.core_finance.qdb_gl_monthly_analysis import merge_all

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_qdb_gl,
]

B = Decimal("100000000")


@pytest.mark.parametrize(
    ("closing", "month_average", "year_average", "expected"),
    [
        (-10, None, None, [None, None, None, None, None, None]),
        (-10, None, -8, [None, -8, None, None, None, None]),
        (-10, -9, None, [-9, None, -1, -11.11, None, None]),
        (0, 0, 0, [0, 0, 0, None, 0, None]),
        (-10, -10, -10, [-10, -10, 0, 0, 0, 0]),
    ],
    ids=["both-missing", "month-missing", "year-missing", "real-zero", "zero-deviation"],
)
def test_summary_preserves_missing_average_cells_and_real_zero(
    closing, month_average, year_average, expected
):
    row = {
        "科目代码": "501",
        "名称": "贷款利息收入",
        "期初余额": -9 * B,
        "期末余额": closing * B,
        "变动额": (closing + 9) * B,
        "月日均": None if month_average is None else month_average * B,
        "年日均": None if year_average is None else year_average * B,
    }

    workbook = build_qdb_gl_monthly_analysis_workbook(
        report_month="202608", merged_data={"3位": [row]}
    )
    summary = next(sheet for sheet in workbook["sheets"] if sheet["key"] == "summary_3d")
    actual = summary["rows"][0]

    assert [actual[field] for field in ("月日均", "年日均", "偏离额", "偏离%", "趋势额", "趋势%")] == expected
    assert actual["期初余额"] == -9
    assert actual["期末余额"] == closing
    assert actual["变动额"] == closing + 9


@pytest.mark.parametrize(("code", "sheet_key"), [("101", "asset_structure"), ("201", "liability_structure")])
@pytest.mark.parametrize("month_average", [None, 0, 2])
def test_structure_preserves_missing_month_average_and_observed_zero(code, sheet_key, month_average):
    row = {
        "科目代码": code,
        "名称": "结构核验科目",
        "期初余额": B,
        "期末余额": 2 * B,
        "变动额": B,
        "月日均": None if month_average is None else month_average * B,
        "年日均": B,
    }
    workbook = build_qdb_gl_monthly_analysis_workbook(report_month="202608", merged_data={"3位": [row]})
    sheets = {sheet["key"]: sheet for sheet in workbook["sheets"]}
    assert sheets[sheet_key]["rows"][0]["月日均"] == month_average
    assert sheets[sheet_key]["rows"][0]["月日均"] == sheets["summary_3d"]["rows"][0]["月日均"]


@pytest.mark.parametrize("missing_prefix", ["123", "201", "205"])
@pytest.mark.parametrize("average", [None, 0, 1])
def test_industry_workbook_preserves_missing_average_from_merge(missing_prefix, average):
    ledger = []
    averages = []
    for prefix, amount in [("123", 1), ("201", -2), ("205", -3)]:
        ledger.append({
            "科目代码": prefix + "03000001", "科目名称": "合成行业科目", "币种": "CNX",
            "大类3": prefix, "大类5": prefix + "03", "大类1": prefix[0],
            "期初余额": amount * B, "期末余额": amount * B,
            "变动额": 0, "本期借方": 0, "本期贷方": 0, "本期净额": 0,
        })
        if prefix != missing_prefix or average is not None:
            value = amount if prefix != missing_prefix else average * (1 if prefix == "123" else -1)
            averages.append({"科目代码": prefix + "03", "日均余额": value * B})
    merged = merge_all({"综本": ledger}, {"月日均_CNX_5d": averages, "年日均_CNX_5d": averages})
    workbook = build_qdb_gl_monthly_analysis_workbook(report_month="202608", merged_data=merged)
    sheets = {sheet["key"]: sheet for sheet in workbook["sheets"]}
    key = {"123": "loan_industry", "201": "deposit_demand_industry", "205": "deposit_term_industry"}[missing_prefix]
    industry = sheets[key]["rows"][0]
    gap = sheets["industry_gap"]["rows"][0]
    if average is None:
        assert [industry[field] for field in ("月日均", "年日均", "偏离额", "偏离%", "趋势%")] == [None] * 5
        assert gap["贷款月日均" if missing_prefix == "123" else "存款月日均"] is None
        assert gap["存贷差_日均"] is None
    else:
        signed_average = average * (1 if missing_prefix == "123" else -1)
        assert industry["月日均"] == signed_average
        assert industry["年日均"] == signed_average
        expected_loan = average if missing_prefix == "123" else 1
        expected_deposit = (average if missing_prefix == "201" else 2) + (average if missing_prefix == "205" else 3)
        assert gap["存贷差_日均"] == expected_loan - expected_deposit
    assert gap["存贷差_时点"] == -4
