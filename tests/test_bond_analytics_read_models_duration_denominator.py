"""聚合层久期分母过滤回归护栏：bond_analytics/read_models.py（B7 审计第 1 项）。

背景：``common.DURATION_UNAVAILABLE``（0）是「久期不可用」标记，不是观测到的
零久期。缺到期日的基金/ETF 行（engine 打 ``duration_quality_flag=
maturity_unavailable``、``years_to_maturity=0`` 落 ``get_tenor_bucket(0)=="6M"``
桶）与已到期未清算行此前混进 6M 桶：市值计入桶权重、把
``avg_modified_duration`` 稀释向 0（2026-07-31 实证 127 笔基金 / 12.6786%
组合市值）。``summarize_portfolio_risk`` 已用 ``_duration_denominator_rows``
正确剔除，但 ``build_krd_distribution`` / ``build_asset_class_risk_summary`` /
``summarize_credit`` 三处漏了同一过滤。

本文件钉住修复后的口径（对齐 ``risk_tensor.duration_excluded_*`` 披露模式）：

- ``build_krd_distribution``：无久期行整行移出桶（市值 + 久期分母），由
  ``duration_excluded_market_value`` / ``duration_excluded_count`` 单独披露；
  dv01 仍为全桶合计（被剔除行 dv01=0，数值不变）。
- ``build_asset_class_risk_summary``：market_value / weight / dv01 保持资产
  配置口径（全量行），仅 ``duration`` 加权分母剔除 + 披露。
- ``summarize_credit``：仅 ``weighted_avg_spread_duration`` 分母剔除 + 披露，
  credit_market_value 等保持全量。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.bond_analytics.read_models import (
    build_asset_class_risk_summary,
    build_krd_distribution,
    summarize_credit,
)

# 真债：6M 桶，有到期日、有正修正久期。
BOND_6M = {
    "instrument_code": "B_6M",
    "asset_class_std": "rate",
    "accounting_class": "AC",
    "tenor_bucket": "6M",
    "maturity_date": date(2026, 12, 31),
    "years_to_maturity": Decimal("0.42"),
    "market_value": Decimal("1000"),
    "macaulay_duration": Decimal("0.42"),
    "modified_duration": Decimal("0.40"),
    "dv01": Decimal("0.04"),
    "spread_dv01": Decimal("0"),
}

# 真债：5Y 桶，用于验证不受影响的桶披露为 0。
BOND_5Y = {
    "instrument_code": "B_5Y",
    "asset_class_std": "rate",
    "accounting_class": "AC",
    "tenor_bucket": "5Y",
    "maturity_date": date(2031, 6, 30),
    "years_to_maturity": Decimal("5.0"),
    "market_value": Decimal("1000"),
    "macaulay_duration": Decimal("4.6"),
    "modified_duration": Decimal("4.4"),
    "dv01": Decimal("0.44"),
    "spread_dv01": Decimal("0"),
}

# 缺到期日的基金持仓：engine 打 years_to_maturity=0 → tenor_bucket="6M"，
# 久期族全部为 DURATION_UNAVAILABLE(0)，duration_quality_flag=maturity_unavailable。
FUND_NO_MATURITY = {
    "instrument_code": "F_FUND",
    "asset_class_std": "rate",
    "accounting_class": "TPL",
    "tenor_bucket": "6M",
    "maturity_date": None,
    "years_to_maturity": Decimal("0"),
    "market_value": Decimal("2000"),
    "macaulay_duration": Decimal("0"),
    "modified_duration": Decimal("0"),
    "convexity": Decimal("0"),
    "dv01": Decimal("0"),
    "spread_dv01": Decimal("0"),
    "duration_quality_flag": "maturity_unavailable",
}

# 已到期未清算行：有到期日但 <= 报告日，engine 同样打 0 久期（no_remaining_term）。
MATURED_OUTSTANDING = {
    "instrument_code": "B_MATURED",
    "asset_class_std": "rate",
    "accounting_class": "AC",
    "tenor_bucket": "6M",
    "maturity_date": date(2025, 6, 30),
    "years_to_maturity": Decimal("0"),
    "market_value": Decimal("500"),
    "macaulay_duration": Decimal("0"),
    "modified_duration": Decimal("0"),
    "convexity": Decimal("0"),
    "dv01": Decimal("0"),
    "spread_dv01": Decimal("0"),
    "duration_quality_flag": "no_remaining_term",
}

PORTFOLIO = [BOND_6M, BOND_5Y, FUND_NO_MATURITY, MATURED_OUTSTANDING]


class TestBuildKrdDistribution:
    def test_6m_bucket_average_duration_is_not_diluted(self):
        by_bucket = {row["tenor_bucket"]: row for row in build_krd_distribution(PORTFOLIO)}

        # 修复前：avg = (0.40*1000)/(1000+2000+500) ≈ 0.1143（被稀释）
        assert by_bucket["6M"]["avg_modified_duration"] == Decimal("0.40")
        assert by_bucket["6M"]["krd"] == Decimal("0.40")

    def test_6m_bucket_market_value_excludes_unusable_duration_rows(self):
        by_bucket = {row["tenor_bucket"]: row for row in build_krd_distribution(PORTFOLIO)}

        assert by_bucket["6M"]["market_value"] == Decimal("1000")
        assert by_bucket["6M"]["duration_excluded_market_value"] == Decimal("2500")
        assert by_bucket["6M"]["duration_excluded_count"] == 2

    def test_6m_bucket_dv01_remains_whole_bucket_sum(self):
        by_bucket = {row["tenor_bucket"]: row for row in build_krd_distribution(PORTFOLIO)}

        # 被剔除行 dv01=0（engine 按 DURATION_UNAVAILABLE 构造），合计不变。
        assert by_bucket["6M"]["dv01"] == Decimal("0.04")

    def test_clean_bucket_disclosure_is_zero(self):
        by_bucket = {row["tenor_bucket"]: row for row in build_krd_distribution(PORTFOLIO)}

        assert by_bucket["5Y"]["market_value"] == Decimal("1000")
        assert by_bucket["5Y"]["avg_modified_duration"] == Decimal("4.4")
        assert by_bucket["5Y"]["duration_excluded_market_value"] == Decimal("0")
        assert by_bucket["5Y"]["duration_excluded_count"] == 0

    def test_bucket_with_only_excluded_rows_reports_zero_exposure(self):
        rows = [FUND_NO_MATURITY, MATURED_OUTSTANDING]
        by_bucket = {row["tenor_bucket"]: row for row in build_krd_distribution(rows)}

        bucket = by_bucket["6M"]
        assert bucket["market_value"] == Decimal("0")
        assert bucket["avg_modified_duration"] == Decimal("0")
        assert bucket["dv01"] == Decimal("0")
        assert bucket["duration_excluded_market_value"] == Decimal("2500")
        assert bucket["duration_excluded_count"] == 2

    def test_total_market_value_is_conserved_across_bucket_and_disclosure(self):
        distribution = build_krd_distribution(PORTFOLIO)
        total = sum(
            (row["market_value"] + row["duration_excluded_market_value"] for row in distribution),
            Decimal("0"),
        )
        assert total == Decimal("4500")


class TestBuildAssetClassRiskSummary:
    def test_duration_denominator_excludes_unusable_rows(self):
        by_class = {row["asset_class"]: row for row in build_asset_class_risk_summary(PORTFOLIO)}
        rate = by_class["rate"]

        # 修复前：duration = (0.42*1000 + 4.6*1000)/(4500) ≈ 1.1156（被稀释）
        expected = (
            Decimal("0.42") * Decimal("1000") + Decimal("4.6") * Decimal("1000")
        ) / Decimal("2000")
        assert rate["duration"] == expected

    def test_allocation_facts_keep_all_rows(self):
        by_class = {row["asset_class"]: row for row in build_asset_class_risk_summary(PORTFOLIO)}
        rate = by_class["rate"]

        # market_value / weight 是资产配置事实：基金市值真实属于该资产类。
        assert rate["market_value"] == Decimal("4500")
        assert rate["weight"] == Decimal("1")
        assert rate["duration_excluded_market_value"] == Decimal("2500")
        assert rate["duration_excluded_count"] == 2


class TestSummarizeCredit:
    def test_spread_duration_denominator_excludes_unusable_rows(self):
        credit_bond = {
            **BOND_5Y,
            "instrument_code": "C_5Y",
            "asset_class_std": "credit",
            "modified_duration": Decimal("3"),
            "spread_dv01": Decimal("0.3"),
        }
        credit_fund = {
            **FUND_NO_MATURITY,
            "instrument_code": "C_FUND",
            "asset_class_std": "credit",
        }
        rows = [credit_bond, credit_fund]

        summary = summarize_credit(rows, total_rows=rows)

        # 修复前：weighted = (3*1000)/(1000+2000) = 1（被稀释）
        assert summary["weighted_avg_spread_duration"] == Decimal("3")
        assert summary["duration_excluded_market_value"] == Decimal("2000")
        assert summary["duration_excluded_count"] == 1
        # 信用敞口口径保持全量。
        assert summary["credit_market_value"] == Decimal("3000")
        assert summary["credit_bond_count"] == 2
