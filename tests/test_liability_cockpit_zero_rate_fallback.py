# 回归：liability_cockpit 中 ytm=0 时必须视为"未采集"，回退到 coupon/interest_rate 下一候选，
# 与 liability_analytics_compat.compute_liability_yield_metrics 的显式回退链语义保持一致。
#
# 同时固化 H/A 账户判定的数据来源语义（对齐 liability_analytics_repo.fetch_zqtz_rows 的真实输出）：
# - formal 表可用时，asset_type 字段来自 fact_formal_zqtz_balance_daily.invest_type_std（"H"/"A"/"T"）。
# - formal 表不可用、回退 zqtz_bond_daily_snapshot 时，asset_type 恒为 None（生产不会出现手工填充的
#   "H"/"A" 字符串），此时 H/A 判定退回 asset_class 子串匹配兜底。
# fixture 不再手工塞入生产不会出现的 asset_type，而是用真实两种取值路径建模。
from __future__ import annotations

from backend.app.core_finance.liability_cockpit import (
    compute_cockpit_warnings,
    compute_contribution_split,
)


def _asset_row(*, ytm_value, coupon_rate, asset_type=None) -> dict:
    return {
        "is_issuance_like": False,
        "asset_type": asset_type,
        # 「持有至到期」子串命中 asset_class 子串兜底规则的 H 分类，
        # 用于建模 snapshot 回退（asset_type=None）时的真实判定路径。
        "asset_class": "持有至到期投资-债券",
        "market_value_native": "100000000",
        "ytm_value": ytm_value,
        "coupon_rate": coupon_rate,
    }


def _liability_row(*, coupon_rate) -> dict:
    return {
        "is_issuance_like": True,
        "amortized_cost_native": "100000000",
        "coupon_rate": coupon_rate,
    }


def test_cockpit_warnings_ytm_zero_falls_back_to_coupon_not_zero_rate() -> None:
    # ZQTZ 利率字段落库口径为百分点（normalize_bond_rate_decimal 无条件 pct_to_decimal），
    # 5% 票息写作 "5"，归一化后为小数 0.05。
    asset_row = _asset_row(ytm_value="0", coupon_rate="5")
    liability_row = _liability_row(coupon_rate="2")

    result = compute_cockpit_warnings("2026-06-30", [asset_row, liability_row], [])

    alert_ids = {item["id"] for item in result["alert_events"]}
    watch_ids = {item["id"] for item in result["watch_items"]}
    # asset_yield 应取 coupon=5%（ytm=0 视为未采集），NIM = 0.05-0.02 = 0.03，
    # 高于关注/告警阈值；若 ytm=0 被误当作真实零利率，asset_yield 会变成 0，
    # NIM 会跌到 -0.02 并触发"净息差为负"告警。
    assert "alert_nim_negative" not in alert_ids
    assert "watch_nim_thin" not in watch_ids


def test_contribution_split_ytm_zero_falls_back_to_coupon_not_zero_rate() -> None:
    asset_row = _asset_row(ytm_value="0", coupon_rate="5")

    result = compute_contribution_split("2026-06-30", [asset_row], [])

    entry = next(row for row in result["contributions"] if row["side"] == "asset")
    assert entry["yield_or_cost"] == 0.05


def test_asset_h_classification_prefers_formal_invest_type_then_asset_class_fallback() -> None:
    """固化两种 H 判定路径，并排除既不命中 asset_type 也不命中 asset_class 子串的行。

    - formal_h_row: 模拟 fetch_zqtz_rows 的 formal 分支，asset_type="H" 直接来自
      fact_formal_zqtz_balance_daily.invest_type_std，即使 asset_class 是不含任何
      H/A 关键字的通用标签也应判定为计息资产。
    - snapshot_fallback_row: 模拟 fetch_zqtz_rows 的 snapshot 回退分支，asset_type
      恒为 None，此时必须靠 asset_class 子串（"持有至到期"）兜底判定为 H。
    - unclassified_row: asset_type 为 None 且 asset_class 不含任何 H/A/应收投资 子串，
      两条路径都不命中，应被完全排除在计息资产之外。
    """
    formal_h_row = {
        "is_issuance_like": False,
        "asset_type": "H",
        "asset_class": "国债",  # 通用利率债标签，不含 H/A 子串关键字
        "market_value_native": "100000000",
        "ytm_value": "4",
        "coupon_rate": "3",
    }
    snapshot_fallback_row = {
        "is_issuance_like": False,
        "asset_type": None,
        "asset_class": "持有至到期投资-债券",
        "market_value_native": "200000000",
        "ytm_value": "5",
        "coupon_rate": "4.5",
    }
    unclassified_row = {
        "is_issuance_like": False,
        "asset_type": None,
        "asset_class": "其他资产投资",
        "market_value_native": "300000000",
        "ytm_value": "10",
        "coupon_rate": "9",
    }

    result = compute_contribution_split(
        "2026-06-30",
        [formal_h_row, snapshot_fallback_row, unclassified_row],
        [],
    )

    asset_rows = {row["category"]: row["amount_yi"] for row in result["contributions"] if row["side"] == "asset"}
    assert asset_rows == {"利率债": 1.0, "信用债": 2.0}
