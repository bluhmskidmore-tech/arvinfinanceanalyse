"""缺到期日持仓在 KRD 分桶中的回归护栏：backend/app/core_finance/krd.py。

背景（W-fi-2026-08 P2 的后续回归）：缺到期日的久期口径统一为
``common.resolve_missing_maturity_duration`` → ``DURATION_UNAVAILABLE = Decimal("0")``
之后，``Decimal("0")`` 从"罕见边界"变成了**有业务含义的常见值**（2026-07-31 有
127 笔基金持仓落在该分支，合计 433.99 亿、占组合市值 12.6786%）。

于是 ``_get_tenor_from_position`` 里的

    get_tenor_bucket(float(duration or Decimal("5")))

成为陷阱：``Decimal("0")`` 是 falsy，这批持仓的久期 0 被当成"没有久期"，
回退成 5 年占位并被错分进 5Y 桶。修正为 ``duration if duration is not None``，
区分"久期确实是 0（不可用标记）"与"根本没传久期"。

2026-07-31 只读快照实测（KRD 与 DV01 均不受影响——修正久期确实是 0，
仅 ``market_value_weight`` 展示列错位）：

    桶    market_value_weight    修复前 → 修复后
    1Y                          0.274786 → 0.401571
    5Y                          0.238332 → 0.111546

两者恰好相差 0.126786，即那批缺到期日持仓的市值占比。

本文件用最小组合复现同一错位：一只落在 5Y 桶的真债 + 一笔缺到期日的基金持仓，
各占市值 50%。修复前两者同归 5Y（5Y 权重 1.0）；修复后基金持仓落在 ON 桶，
再经 ``KRD_SHORT_END_BUCKET_MERGE`` 归并进 1Y（各 0.5）。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.bond_analytics.common import DURATION_UNAVAILABLE
from backend.app.core_finance.krd import (
    _get_tenor_from_position,
    build_krd_position_metrics,
    compute_krd_curve_risk,
)

REPORT_DATE = date(2026, 1, 1)

# 1826 天 / 365 = 5.0027… → 落在 5Y 桶 [4.0, 6.0)
BOND_5Y = {
    "bond_code": "B_5Y",
    "market_value": Decimal("1000000"),
    "face_value": Decimal("1000000"),
    "coupon_rate": Decimal("0.0250"),
    "yield_to_maturity": Decimal("0.0250"),
    "maturity_date": date(2031, 1, 1),
    "report_date": REPORT_DATE,
    "sub_type": "国债",
    "asset_class": "交易性金融资产",
    "coupon_frequency": 2,
}

# 缺到期日的基金持仓：``estimate_duration`` 返回 DURATION_UNAVAILABLE(0)
FUND_NO_MATURITY = {
    "bond_code": "F_FUND",
    "market_value": Decimal("1000000"),
    "face_value": Decimal("0"),
    "coupon_rate": Decimal("0"),
    "yield_to_maturity": Decimal("0"),
    "maturity_date": None,
    "report_date": REPORT_DATE,
    "sub_type": "基金",
    "asset_class": "交易性金融资产",
}

PORTFOLIO = [BOND_5Y, FUND_NO_MATURITY]


class TestZeroDurationIsNotMissing:
    """``Decimal("0")`` 必须被当成真实的 0，不得回退默认值。"""

    def test_duration_unavailable_is_falsy_but_not_none(self):
        """陷阱本身：这就是 ``or`` 会误判的原因，用例显式钉住该前提。"""
        assert DURATION_UNAVAILABLE == Decimal("0")
        assert not DURATION_UNAVAILABLE  # falsy —— ``or`` 在此处会吞掉它
        assert DURATION_UNAVAILABLE is not None

    def test_zero_duration_maps_to_overnight_bucket_not_five_year(self):
        position = {"bond_code": "F_FUND"}
        bucket = _get_tenor_from_position(
            position,
            report_date=REPORT_DATE,
            duration=DURATION_UNAVAILABLE,
        )
        assert bucket == "ON", "久期 0 被当成缺失并回退 5 年占位"
        assert bucket != "5Y"

    def test_absent_duration_still_uses_five_year_placeholder(self):
        """``None`` 才是"根本没有值"；保留既有 5 年占位，避免被顺手简化掉。"""
        assert (
            _get_tenor_from_position({"bond_code": "X"}, report_date=REPORT_DATE, duration=None)
            == "5Y"
        )

    def test_maturity_date_still_wins_over_duration(self):
        """有到期日时走剩余年限，久期只是缺到期日的兜底输入。"""
        assert (
            _get_tenor_from_position(BOND_5Y, report_date=REPORT_DATE, duration=Decimal("0"))
            == "5Y"
        )


class TestMissingMaturityPositionMetrics:
    def test_missing_maturity_row_carries_zero_duration_and_on_bucket(self):
        metrics = build_krd_position_metrics(PORTFOLIO, report_date=REPORT_DATE)
        by_code = {m["bond_code"]: m for m in metrics}

        fund = by_code["F_FUND"]
        assert fund["duration"] == DURATION_UNAVAILABLE
        assert fund["modified_duration"] == Decimal("0")
        assert fund["convexity"] == Decimal("0")
        assert fund["dv01"] == Decimal("0")
        assert fund["tenor_bucket"] == "ON"

        assert by_code["B_5Y"]["tenor_bucket"] == "5Y"

    def test_missing_maturity_row_fabricates_no_curve_exposure(self):
        """选 0 的理由：不凭空造久期敞口/DV01/凸性。组合口径必须只由真债贡献。"""
        full = compute_krd_curve_risk(PORTFOLIO, report_date=REPORT_DATE)
        bond_only = compute_krd_curve_risk([BOND_5Y], report_date=REPORT_DATE)

        assert full["portfolio_dv01"] == bond_only["portfolio_dv01"]
        # 组合修正久期按市值加权：加入零久期的基金持仓后分母翻倍 → 恰好减半
        assert full["portfolio_modified_duration"] * 2 == bond_only["portfolio_modified_duration"]


class TestMarketValueWeightLandsInCorrectBucket:
    """展示列的回归：错分只动 ``market_value_weight``，不动 KRD / DV01。"""

    def test_weights_split_between_1y_and_5y(self):
        result = compute_krd_curve_risk(PORTFOLIO, report_date=REPORT_DATE)
        by_tenor = {row["tenor"]: row for row in result["krd_buckets"]}

        # 修复前：基金持仓被错分进 5Y → 5Y 权重 1.0、1Y 权重 0
        assert by_tenor["1Y"]["market_value_weight"] == Decimal("0.5")
        assert by_tenor["5Y"]["market_value_weight"] == Decimal("0.5")

    def test_krd_and_dv01_stay_with_the_real_bond(self):
        result = compute_krd_curve_risk(PORTFOLIO, report_date=REPORT_DATE)
        by_tenor = {row["tenor"]: row for row in result["krd_buckets"]}

        # 基金持仓归并进 1Y 桶，但修正久期与 DV01 都是 0 → 该桶不产生曲线敞口
        assert by_tenor["1Y"]["krd"] == Decimal("0")
        assert by_tenor["1Y"]["dv01"] == Decimal("0")
        assert by_tenor["5Y"]["krd"] > Decimal("0")
        assert by_tenor["5Y"]["dv01"] > Decimal("0")

    def test_merge_disclosure_reports_the_missing_maturity_row(self):
        """归并披露必须把这行显示出来，而不是让它静悄悄躺在 5Y 桶里。"""
        disclosure = compute_krd_curve_risk(PORTFOLIO, report_date=REPORT_DATE)[
            "krd_bucket_disclosure"
        ]

        assert disclosure["merged_buckets"] == {"ON": "1Y"}
        assert disclosure["merged_position_count"] == 1
        assert disclosure["merged_market_value"] == Decimal("1000000")
        assert disclosure["dropped_buckets"] == []

    def test_weights_still_sum_to_one(self):
        result = compute_krd_curve_risk(PORTFOLIO, report_date=REPORT_DATE)
        total = sum((row["market_value_weight"] for row in result["krd_buckets"]), Decimal("0"))
        assert total == Decimal("1")
