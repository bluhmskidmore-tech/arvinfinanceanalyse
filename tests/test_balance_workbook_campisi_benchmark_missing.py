# 回归（B10-2，2026-08 审计）：Campisi 归因的利差基准 = 在册"政策性金融债"加权票面。
# 在册无政金债（或基准行票面全缺失）时 benchmark 不得静默取 0——否则 spread_bp
# 退化为票息×100、利差收入=全部票息收入且无标记（违反 docs/calc_rules.md §14）。
# 修复后：基准缺失时 spread_bp / spread_income_amount 显式输出 None，并由
# rule_reference 的 bal_campisi_benchmark_missing_null 行披露该口径。
#
# 说明：本文件只测生产权威实现（单体 balance_analysis_workbook.py）。
# balance_workbook/ 包内的 _analysis_tables._build_campisi_table 是不在生产调用
# 路径上的休眠副本（builder.py 为委托壳），已同步为同一"基准缺失→null"口径；
# 双实现等价性由 tests/test_balance_workbook_campisi_rate.py 钉住。
from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.balance_analysis import FormalZqtzBalanceFactRow
from backend.app.core_finance.balance_analysis_workbook import (
    _build_campisi_table,
    _build_rule_reference_table,
)
from backend.app.schemas.balance_analysis import BalanceAnalysisWorkbookTable

RD = date(2026, 3, 31)
MAT = date(2031, 3, 31)


def _asset_row(*, code: str, bond_type: str, face: Decimal, coupon: Decimal | None) -> FormalZqtzBalanceFactRow:
    return FormalZqtzBalanceFactRow(
        report_date=RD,
        instrument_code=code,
        instrument_name=code,
        portfolio_name="P",
        cost_center="C",
        account_category="",
        asset_class="FVTPL债",
        bond_type=bond_type,
        issuer_name="I",
        industry_name="未分类",
        rating="",
        invest_type_std="T",
        accounting_basis="FVTPL",
        position_scope="asset",
        currency_basis="native",
        currency_code="CNY",
        face_value_amount=face,
        market_value_amount=face,
        amortized_cost_amount=face,
        accrued_interest_amount=Decimal("0"),
        coupon_rate=coupon,
        ytm_value=coupon,
        maturity_date=MAT,
        interest_mode="固定",
        is_issuance_like=False,
    )


def test_campisi_benchmark_missing_outputs_null_spread_not_coupon_times_100() -> None:
    # 在册无政策性金融债：spread 列必须为 None，而不是把基准当 0 后的
    # spread_bp=320（票息×100）与利差收入=全部票息收入。
    rows = [
        _asset_row(code="B1", bond_type="企业债", face=Decimal("200000000"), coupon=Decimal("3.20")),
        _asset_row(code="B2", bond_type="中期票据", face=Decimal("150000000"), coupon=Decimal("2.55")),
    ]

    table = _build_campisi_table(rows)
    out_rows = {row["bond_type"]: row for row in table["rows"]}

    for bond_type in ("企业债", "中期票据"):
        assert out_rows[bond_type]["spread_bp"] is None
        assert out_rows[bond_type]["spread_income_amount"] is None

    # 其余列不受基准缺失影响，保持原有口径。
    assert out_rows["企业债"]["weighted_rate_pct"] == Decimal("3.20")
    assert out_rows["企业债"]["coupon_income_amount"] == Decimal("640")
    assert out_rows["中期票据"]["coupon_income_amount"] == Decimal("382.5")


def test_campisi_benchmark_present_keeps_spread_semantics() -> None:
    rows = [
        _asset_row(code="B1", bond_type="政策性金融债", face=Decimal("100000000"), coupon=Decimal("2.85")),
        _asset_row(code="B2", bond_type="企业债", face=Decimal("200000000"), coupon=Decimal("3.20")),
    ]

    table = _build_campisi_table(rows)
    out_rows = {row["bond_type"]: row for row in table["rows"]}

    assert out_rows["政策性金融债"]["spread_bp"] == Decimal("0")
    assert out_rows["企业债"]["spread_bp"] == Decimal("35.00")
    assert out_rows["企业债"]["spread_income_amount"] == Decimal("70")


def test_campisi_zero_coupon_benchmark_is_real_zero_not_missing() -> None:
    # 真实零票息政金债：基准是 Decimal("0")（可计算），不得被当成"缺失"。
    rows = [
        _asset_row(code="B1", bond_type="政策性金融债", face=Decimal("100000000"), coupon=Decimal("0")),
        _asset_row(code="B2", bond_type="企业债", face=Decimal("200000000"), coupon=Decimal("3.20")),
    ]

    table = _build_campisi_table(rows)
    out_rows = {row["bond_type"]: row for row in table["rows"]}

    assert out_rows["企业债"]["spread_bp"] == Decimal("320.00")
    assert out_rows["企业债"]["spread_income_amount"] is not None


def test_rule_reference_discloses_campisi_benchmark_missing_semantics() -> None:
    rows = _build_rule_reference_table()["rows"]
    rule = next(row for row in rows if row["rule_id"] == "bal_campisi_benchmark_missing_null")

    assert rule["rule_name"] == "Campisi 基准缺失口径"
    assert "政策性金融债" in rule["summary"]
    assert "null" in rule["summary"]
    assert "不允许把基准静默降级为 0" in rule["summary"]
    assert rule["source_doc"] == "docs/calc_rules.md"
    assert rule["source_section"] == "14 禁止事项（不允许静默降级为 0 且不打标记）"


def test_campisi_null_spread_rows_pass_workbook_table_schema() -> None:
    # API 契约安全：schema 行值类型为 Decimal | str | int | None，null 利差列可过网。
    rows = [
        _asset_row(code="B1", bond_type="企业债", face=Decimal("200000000"), coupon=Decimal("3.20")),
    ]
    table = _build_campisi_table(rows)
    validated = BalanceAnalysisWorkbookTable.model_validate(table)
    assert validated.rows[0]["spread_bp"] is None
