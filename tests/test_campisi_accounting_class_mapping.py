"""会计分类（AC/OCI/TPL）在 Campisi model 链路上的键映射回归测试。

背景（2026-08 生产缺陷）：`bond_four_effects` 原来只从 `asset_class_start` /
`asset_class` 推断会计分类，而 `merge_positions` 写进 `asset_class_start` 的是
`asset_class_std` + 评级（如 `credit AAA`），根本不含会计口径信息 →
`infer_accounting_class` 对全部持仓返回 TPL，"AC 类仅计票息"保护完全失效。

本文件同时钉住三件事：
1. 权威字段 `accounting_class` 优先于标签推断；
2. AC 行不产生市场效应，OCI / TPL 行保留市场效应；
3. **fixture 与生产行键名一致**——所有 analytics 行 fixture 只能用
   `_ANALYTICS_COLUMNS` 里真实存在的列名构造，避免再次出现
   "fixture 里有 `asset_class`、生产没有"的错位（正是本缺陷长期未被测试发现的原因）。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from backend.app.core_finance.bond_four_effects import (
    compute_bond_four_effects,
    compute_bond_six_effects,
    resolve_accounting_class,
)
from backend.app.core_finance.campisi import campisi_attribution, campisi_enhanced
from backend.app.repositories.bond_analytics_repo import _ANALYTICS_COLUMNS
from backend.app.services.campisi_attribution_service import merge_positions

MARKET_START = {
    "treasury_1y": 2.00,
    "treasury_3y": 2.40,
    "treasury_5y": 2.70,
    "treasury_7y": 2.90,
    "treasury_10y": 3.00,
    "treasury_30y": 3.40,
    "credit_spread_aaa_3y": 50.0,
    "credit_spread_aa_plus_3y": 80.0,
    "credit_spread_aa_3y": 120.0,
}
MARKET_END = {
    "treasury_1y": 2.20,
    "treasury_3y": 2.60,
    "treasury_5y": 2.90,
    "treasury_7y": 3.10,
    "treasury_10y": 3.20,
    "treasury_30y": 3.60,
    "credit_spread_aaa_3y": 70.0,
    "credit_spread_aa_plus_3y": 100.0,
    "credit_spread_aa_3y": 150.0,
}

START = date(2026, 6, 30)
END = date(2026, 7, 15)


def analytics_row(**overrides: Any) -> dict[str, Any]:
    """构造一行与生产 `fetch_bond_analytics_rows` 完全同形的 analytics 行。

    未知列名会直接失败：这就是 fixture/生产键名一致性的守卫。
    """
    unknown = set(overrides) - set(_ANALYTICS_COLUMNS)
    assert not unknown, f"fixture 使用了 analytics 行不存在的列：{sorted(unknown)}"
    row: dict[str, Any] = dict.fromkeys(_ANALYTICS_COLUMNS)
    row.update(
        report_date="2026-06-30",
        instrument_code="000001.IB",
        instrument_name="测试债",
        portfolio_name="自营",
        cost_center="CC1",
        asset_class_raw="债权投资类金融资产",
        asset_class_std="credit",
        bond_type="企业债",
        rating="AAA",
        accounting_class="AC",
        currency_code="CNY",
        face_value=100_000_000.0,
        market_value=101_000_000.0,
        accrued_interest=500_000.0,
        coupon_rate=3.0,
        ytm=3.2,
        maturity_date=date(2031, 6, 30),
    )
    row.update(overrides)
    return row


def bond_from(accounting_class: str | None, **overrides: Any) -> dict[str, Any]:
    """单券入参，asset_class_start 刻意使用生产同款的 `asset_class_std + 评级` 形态。"""
    bond = {
        "bond_code": "000001.IB",
        "market_value_start": 101_000_000.0,
        "market_value_end": 100_400_000.0,
        "face_value_start": 100_000_000.0,
        "coupon_rate_start": Decimal("0.03"),
        "yield_to_maturity_start": Decimal("0.032"),
        "asset_class_start": "credit AAA",
        "maturity_date_start": date(2031, 6, 30),
        "accrued_interest_start": 500_000.0,
        "accrued_interest_end": 620_000.0,
    }
    if accounting_class is not None:
        bond["accounting_class"] = accounting_class
    bond.update(overrides)
    return bond


class TestProductionRowKeyParity:
    """生产行键名事实：只有 accounting_class / asset_class_raw / asset_class_std。"""

    def test_analytics_rows_have_no_asset_class_key(self):
        assert "asset_class" not in _ANALYTICS_COLUMNS
        assert "asset_class_start" not in _ANALYTICS_COLUMNS

    def test_analytics_rows_expose_authoritative_accounting_class(self):
        assert "accounting_class" in _ANALYTICS_COLUMNS
        assert "asset_class_raw" in _ANALYTICS_COLUMNS
        assert "asset_class_std" in _ANALYTICS_COLUMNS

    def test_merge_positions_carries_accounting_class_through(self):
        rows = [analytics_row(accounting_class="OCI", asset_class_raw="可供出售类金融资产")]
        merged = merge_positions(rows, rows)
        assert len(merged) == 1
        position = merged[0]
        assert position["accounting_class"] == "OCI"
        # asset_class_start 是 std+评级标签，不含会计口径 —— 这正是缺陷根因。
        assert position["asset_class_start"] == "credit AAA"
        assert "AC" not in position["asset_class_start"]


class TestResolveAccountingClass:
    def test_authoritative_field_wins_over_label(self):
        assert resolve_accounting_class(bond_from("AC")) == "AC"
        assert resolve_accounting_class(bond_from("OCI")) == "OCI"
        assert resolve_accounting_class(bond_from("TPL")) == "TPL"

    def test_token_is_case_and_whitespace_tolerant(self):
        assert resolve_accounting_class(bond_from(" ac ")) == "AC"

    @pytest.mark.parametrize("empty", [None, "", "   ", "UNKNOWN"])
    def test_falls_back_to_label_inference_when_field_unusable(self, empty):
        bond = bond_from(empty, asset_class_start="债权投资类金融资产")
        assert resolve_accounting_class(bond) == "AC"

    def test_label_only_bond_without_accounting_hint_stays_tpl(self):
        assert resolve_accounting_class(bond_from(None)) == "TPL"


class TestAccountingClassGatesMarketEffects:
    def test_ac_row_produces_income_only(self):
        result = compute_bond_four_effects(
            bond_from("AC"), 15, Decimal("0.002"), Decimal("0.002"), START
        )
        assert result["treasury_effect"] == Decimal("0")
        assert result["spread_effect"] == Decimal("0")
        assert result["selection_effect"] == Decimal("0")
        assert result["total_return"] == result["income_return"]

    def test_ac_row_produces_no_second_order_effects(self):
        result = compute_bond_six_effects(
            bond_from("AC"), 15, Decimal("0.002"), Decimal("0.002"), START
        )
        assert result["convexity_effect"] == Decimal("0")
        assert result["cross_effect"] == Decimal("0")
        assert result["treasury_effect"] == Decimal("0")

    @pytest.mark.parametrize("basis", ["OCI", "TPL"])
    def test_non_ac_rows_keep_market_effects(self, basis):
        result = compute_bond_six_effects(
            bond_from(basis), 15, Decimal("0.002"), Decimal("0.002"), START
        )
        assert result["treasury_effect"] != Decimal("0")
        assert result["spread_effect"] != Decimal("0")
        assert result["convexity_effect"] != Decimal("0")

    def test_ac_gate_is_not_reachable_through_std_label_alone(self):
        """回归钉子：只给 std+评级标签时保护不生效，必须靠 accounting_class。"""
        result = compute_bond_four_effects(
            bond_from(None), 15, Decimal("0.002"), Decimal("0.002"), START
        )
        assert result["treasury_effect"] != Decimal("0")


class TestCampisiEndToEndFromProductionShapedRows:
    @staticmethod
    def _positions() -> list[dict[str, Any]]:
        start_rows = [
            analytics_row(
                instrument_code="AC001.IB",
                accounting_class="AC",
                asset_class_raw="债权投资类金融资产",
            ),
            analytics_row(
                instrument_code="OCI001.IB",
                accounting_class="OCI",
                asset_class_raw="可供出售类金融资产",
                asset_class_std="rate",
                rating="AAA",
            ),
            analytics_row(
                instrument_code="TPL001.IB",
                accounting_class="TPL",
                asset_class_raw="交易性金融资产",
                asset_class_std="credit",
                rating="AA+",
            ),
        ]
        end_rows = [
            {**row, "report_date": "2026-07-15", "market_value": 100_400_000.0}
            for row in start_rows
        ]
        return merge_positions(start_rows, end_rows)

    def test_enhanced_zeroes_market_effects_only_for_ac_rows(self):
        result = campisi_enhanced(self._positions(), MARKET_START, MARKET_END, START, END)
        by_code = {row["bond_code"]: row for row in result["by_bond"]}
        assert by_code["AC001.IB"]["treasury_effect"] == 0.0
        assert by_code["AC001.IB"]["convexity_effect"] == 0.0
        assert by_code["AC001.IB"]["selection_effect"] == 0.0
        assert by_code["OCI001.IB"]["treasury_effect"] != 0.0
        assert by_code["TPL001.IB"]["treasury_effect"] != 0.0

    def test_by_asset_class_buckets_are_labelled_not_empty(self):
        result = campisi_enhanced(self._positions(), MARKET_START, MARKET_END, START, END)
        buckets = {row["asset_class"] for row in result["by_asset_class"]}
        assert buckets == {"credit AAA", "rate AAA", "credit AA+"}
        assert not buckets & {"", "未分类", "None"}

    def test_enhanced_closure_identity_holds(self):
        result = campisi_enhanced(self._positions(), MARKET_START, MARKET_END, START, END)
        totals = result["totals"]
        parts = sum(
            totals[key]
            for key in (
                "income_return",
                "treasury_effect",
                "spread_effect",
                "convexity_effect",
                "cross_effect",
                "reinvestment_effect",
                "selection_effect",
            )
        )
        assert parts == pytest.approx(totals["total_return"], rel=1e-9, abs=1e-6)

    def test_four_effects_closure_identity_holds(self):
        result = campisi_attribution(self._positions(), MARKET_START, MARKET_END, START, END)
        totals = result.totals
        parts = (
            totals["income_return"]
            + totals["treasury_effect"]
            + totals["spread_effect"]
            + totals["selection_effect"]
        )
        assert parts == pytest.approx(totals["total_return"], rel=1e-9, abs=1e-6)
