from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.core_finance.ledger_financial_indicator_summary import (
    LedgerAccountBalance,
    build_ledger_financial_indicator_summary,
    compute_ledger_indicator_components,
)
from backend.app.services import ledger_pnl_service
from tests.helpers import ROOT


def _bal(code: str, yuan: str) -> LedgerAccountBalance:
    return LedgerAccountBalance(account_code=code, ending_balance_yuan=Decimal(yuan))


def _synthetic_rows() -> list[LedgerAccountBalance]:
    """构造一套借贷闭合的小型总账（元）：

    收入类（贷方负值）：501 -900, 514 -100, 511 -60, 516 -40
    支出类（借方正值）：521 300, 527 10, 529 190, 530 10,
                        531 100（其中 53101 80）, 533 20, 534 5, 536 5
    营业外收入：515 -10；所得税：550 90
    → 营业收入 = 900+100+60+40 - (300+10) = 790
      业务及管理费 = 200；减值 = 100（贷款 80 / 其他 20）
      税金 = 20；营业外净收支 = 10-5-5 = 0
      利润总额 = 790-200-100-20+0 = 470；净利润 = 470-90 = 380
    资产：122 -> 60000, 141 -> 40000, 131 -> -600（拨备）
    负债：201 -> -50000, 272 -> -49020
    权益：301 -> -0（此处保持 3xx 缺省）→ 用 301 补平借贷。
    """
    rows = [
        _bal("50101001", "-900"),
        _bal("51401001", "-100"),
        _bal("51101001", "-60"),
        _bal("51601001", "-40"),
        _bal("52101001", "300"),
        _bal("52701001", "10"),
        _bal("52901001", "190"),
        _bal("53000001", "10"),
        _bal("53101001", "80"),
        _bal("53102001", "20"),
        _bal("53301001", "20"),
        _bal("53401001", "5"),
        _bal("53601001", "5"),
        _bal("51501001", "-10"),
        _bal("55000001", "90"),
        # 资产 / 负债 / 权益（时点）
        _bal("12201001", "60000"),
        _bal("14101001", "40000"),
        _bal("13101001", "-600"),
        _bal("20101001", "-50000"),
        _bal("27201001", "-49020"),
    ]
    # 权益补平：资产净额 99400 - 负债 99020 - 当期净利 380 = 0
    balance_gap = sum(row.ending_balance_yuan for row in rows)
    rows.append(_bal("30101001", str(-balance_gap)))
    return rows


def test_components_match_income_statement_composition():
    components = compute_ledger_indicator_components(_synthetic_rows())

    yi = Decimal("100000000")
    assert components["revenue"] == Decimal("790") / yi
    assert components["opex"] == Decimal("200") / yi
    assert components["impairment"] == Decimal("100") / yi
    assert components["impairment_loan"] == Decimal("80") / yi
    assert components["impairment_other"] == Decimal("20") / yi
    assert components["tax_surcharge"] == Decimal("20") / yi
    assert components["nonop_net"] == Decimal("0")
    assert components["profit_before_tax"] == Decimal("470") / yi
    assert components["income_tax"] == Decimal("90") / yi
    assert components["net_profit"] == Decimal("380") / yi
    assert components["loan_balance"] == Decimal("60000") / yi
    assert components["deposit_balance"] == Decimal("50000") / yi
    assert components["loan_provision_balance"] == Decimal("600") / yi
    # 总资产为 1 类科目净额（含备抵负值）
    assert components["total_assets"] == Decimal("99400") / yi
    # 成本收入比 = 200/790；拨贷比 = 600/60000
    assert components["cost_income_ratio_pct"] == Decimal("25.316456")
    assert components["provision_loan_ratio_pct"] == Decimal("1.000000")
    # 恒等：净利润 = -(全部 5 类科目余额)；借贷闭合 gap 为 0
    assert components["_identity_net_profit_gap_yuan"] == Decimal("0")
    assert components["_balance_identity_gap_yuan"] == Decimal("0")


def test_leaf_expansion_excludes_parent_level_rows():
    rows = [
        _bal("531", "100"),
        _bal("53101", "80"),
        _bal("5310101", "80"),
        _bal("53102", "20"),
    ]
    components = compute_ledger_indicator_components(rows)
    # 父科目 531 / 53101 是层级汇总行，只应统计叶子 5310101 + 53102。
    assert components["impairment"] == Decimal("100") / Decimal("100000000")
    assert components["impairment_loan"] == Decimal("80") / Decimal("100000000")


def test_summary_builds_ytd_periods_with_missing_compare_month():
    balances = {
        "202601": _synthetic_rows(),
        "202602": _synthetic_rows(),
        "202501": _synthetic_rows(),
        "202512": _synthetic_rows(),
        # 202502 缺失 → 2 月期间组 flow 同比不可用
    }
    payload = build_ledger_financial_indicator_summary(
        report_month="202602",
        currency_basis="CNX",
        balances_by_month=balances,
    )

    assert payload["data_status"] == "ready"
    assert [period["period_id"] for period in payload["periods"]] == [
        "202601",
        "202602",
    ]
    first, second = payload["periods"]
    assert first["flow_label"] == "2026年1月"
    assert first["flow_compare_month"] == "202501"
    assert first["point_compare_month"] == "202512"
    assert first["flow_compare_available"] is True
    assert second["flow_label"] == "2026年1-2月"
    assert second["flow_compare_available"] is False
    assert second["point_compare_available"] is True

    rows_by_id = {
        row["row_id"]: row
        for section in payload["sections"]
        for row in section["rows"]
    }
    revenue_row = rows_by_id["fin.mother_revenue"]
    assert revenue_row["availability"] == "ledger_computed"
    feb_cells = revenue_row["values"][1]
    assert feb_cells["current"] == "0.0000079000"
    assert feb_cells["compare"] is None
    assert feb_cells["delta"] is None
    assert feb_cells["delta_pct"] is None

    # 余额行按上年末比较，202512 存在 → compare 可用
    loans_row = rows_by_id["biz.mother_loans"]
    assert loans_row["values"][1]["compare"] == "0.0006000000"

    # percent 行：增减额为百分点差，增减幅置空
    ratio_row = rows_by_id["fin.mother_cost_income_ratio"]
    jan_cells = ratio_row["values"][0]
    assert jan_cells["current"] == "25.316456"
    assert jan_cells["delta"] == "0.000000"
    assert jan_cells["delta_pct"] is None


def test_summary_keeps_unavailable_rows_null_with_reasons():
    payload = build_ledger_financial_indicator_summary(
        report_month="202601",
        currency_basis="CNX",
        balances_by_month={"202601": _synthetic_rows()},
    )
    rows_by_id = {
        row["row_id"]: row
        for section in payload["sections"]
        for row in section["rows"]
    }
    group_revenue = rows_by_id["fin.group_revenue"]
    assert group_revenue["availability"] == "no_system_source"
    assert group_revenue["unavailable_reason"]
    assert all(
        cell["current"] is None and cell["compare"] is None
        for cell in group_revenue["values"]
    )
    npl_row = rows_by_id["aq.npl_amount"]
    assert npl_row["availability"] == "no_system_source"
    assert "五级分类" in npl_row["unavailable_reason"]
    # 汇总表行结构齐全：三大板块 50 行
    assert payload["coverage"] == {
        "row_total": 50,
        "row_computed": 13,
        "row_unavailable": 37,
    }


def test_summary_flags_identity_gap_as_failed_check():
    rows = _synthetic_rows()
    rows.append(_bal("19901001", "5"))  # 借贷不平 5 元
    payload = build_ledger_financial_indicator_summary(
        report_month="202601",
        currency_basis="CNX",
        balances_by_month={"202601": rows},
    )
    checks = {
        (check["check_id"], check["month"]): check
        for check in payload["quality_checks"]
    }
    assert checks[("balance_identity", "202601")]["passed"] is False
    assert checks[("balance_identity", "202601")]["gap_yuan"] == "5"
    assert checks[("net_profit_identity", "202601")]["passed"] is True


def test_summary_no_data_when_report_month_source_missing():
    payload = build_ledger_financial_indicator_summary(
        report_month="202603",
        currency_basis="CNX",
        balances_by_month={"202601": _synthetic_rows()},
    )
    assert payload["data_status"] == "no_data"
    assert [period["current_available"] for period in payload["periods"]] == [
        True,
        False,
        False,
    ]


@dataclass
class _FakePair:
    month_key: str
    report_date: date
    ledger_path: Path
    avg_path: Path
    source_version: str


def test_summary_envelope_meta_and_source_files(monkeypatch):
    fake_pairs = [
        _FakePair("202601", date(2026, 1, 31), Path("总账对账202601.xlsx"), Path("日均202601.xlsx"), "sv_a"),
        _FakePair("202501", date(2025, 1, 31), Path("总账对账202501.xlsx"), Path("日均202501.xlsx"), "sv_b"),
        _FakePair("202512", date(2025, 12, 31), Path("总账对账202512.xlsx"), Path("日均202512.xlsx"), "sv_c"),
        _FakePair("202401", date(2024, 1, 31), Path("总账对账202401.xlsx"), Path("日均202401.xlsx"), "sv_ignored"),
    ]

    class _FakeFact:
        def __init__(self, account_code: str, currency: str, ending_balance: str):
            self.account_code = account_code
            self.currency = currency
            self.ending_balance = Decimal(ending_balance)

    synthetic = [
        _FakeFact(row.account_code, "CNX", str(row.ending_balance_yuan))
        for row in _synthetic_rows()
    ] + [_FakeFact("50101001", "CNY", "-1")]

    monkeypatch.setattr(
        ledger_pnl_service,
        "discover_source_pairs",
        lambda _dir: fake_pairs,
    )
    monkeypatch.setattr(
        ledger_pnl_service,
        "_cached_ledger_only_facts",
        lambda _pair: synthetic,
    )

    envelope = ledger_pnl_service.ledger_pnl_financial_indicator_summary_envelope(
        source_dir="unused",
        report_month="202601",
        currency="CNX",
    )

    meta = envelope["result_meta"]
    assert meta["result_kind"] == "ledger_pnl.financial_indicator_summary"
    assert meta["cache_key"] == (
        "ledger_pnl.financial_indicator_summary:202601:CNX"
    )
    assert meta["date_basis"] == "ledger_report_month"
    assert meta["resolved_report_date"] == "2026-01-31"
    assert meta["filters_applied"]["currency_basis"] == "CNX"

    payload = envelope["result"]
    assert payload["data_status"] == "ready"
    # 2024 年文件不属于本请求所需月份，不应出现在来源清单。
    assert {item["month"] for item in payload["source_files"]} == {
        "202601",
        "202501",
        "202512",
    }
    rows_by_id = {
        row["row_id"]: row
        for section in payload["sections"]
        for row in section["rows"]
    }
    # CNY 行被币种过滤排除，CNX 收入口径不受影响。
    assert rows_by_id["fin.mother_revenue"]["values"][0]["current"] == "0.0000079000"


def test_summary_envelope_rejects_invalid_report_month():
    with pytest.raises(ledger_pnl_service.LedgerPnlRequestError):
        ledger_pnl_service.ledger_pnl_financial_indicator_summary_envelope(
            source_dir="unused",
            report_month="202613",
        )


def _real_ledger_source_dir() -> Path | None:
    ledger_token = "\u603b\u8d26\u5bf9\u8d26"
    average_token = "\u65e5\u5747"
    data_input = ROOT / "data_input"
    if not data_input.exists():
        return None
    for path in data_input.iterdir():
        if path.is_dir() and ledger_token in path.name and average_token in path.name:
            return path
    return None


def test_golden_202603_cnx_matches_financial_indicator_workbook():
    """黄金核对：202603 CNX 与《2026年财务指标表-3月最终》工作簿逐项一致。

    工作簿显示值为手工录入的分级四舍五入结果（如营业收入 40.5057623568），
    总账原始精度聚合后第 10 位小数存在 ±1 的录入尾差，此处冻结系统 Decimal
    精确值。
    """
    source_dir = _real_ledger_source_dir()
    if source_dir is None:
        pytest.skip("real ledger source directory is unavailable")

    envelope = ledger_pnl_service.ledger_pnl_financial_indicator_summary_envelope(
        source_dir=str(source_dir),
        report_month="202603",
        currency="CNX",
    )
    payload = envelope["result"]
    assert payload["data_status"] == "ready"
    rows_by_id = {
        row["row_id"]: row
        for section in payload["sections"]
        for row in section["rows"]
    }

    def cells(row_id: str) -> dict[str, str | None]:
        row = rows_by_id[row_id]
        return {value["period_id"]: value for value in row["values"]}["202603"]

    golden = {
        "fin.mother_revenue": ("40.5057623569", "37.9361212775", "2.5696410794"),
        "fin.mother_opex": ("9.2856413190", "9.1799191205", "0.1057221985"),
        "fin.mother_impairment": ("13.8357855232", "16.2492800346", "-2.4134945114"),
        "fin.mother_impairment_loan": ("13.0832767606", "9.5729515021", "3.5103252585"),
        "fin.mother_impairment_other": ("0.7525087626", "6.6763285325", "-5.9238197699"),
        "fin.mother_profit_total": ("16.9243165590", "12.0222594531", "4.9020571059"),
        "fin.mother_net_profit": ("13.9118472051", "11.5608705076", "2.3509766975"),
        "biz.mother_loans": ("4189.4674724086", "3964.6879269004", "224.7795455082"),
    }
    for row_id, (current, compare, delta) in golden.items():
        cell = cells(row_id)
        assert cell["current"] == current, row_id
        assert cell["compare"] == compare, row_id
        assert cell["delta"] == delta, row_id

    ratio_cell = cells("fin.mother_cost_income_ratio")
    assert ratio_cell["current"] == "22.924248"
    assert ratio_cell["compare"] == "24.198360"

    identity_checks = [
        check for check in payload["quality_checks"]
        if check["check_id"] == "net_profit_identity"
    ]
    assert identity_checks and all(check["passed"] for check in identity_checks)
