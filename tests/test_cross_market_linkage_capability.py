"""M12 跨市场联动（cross_market_linkage）纯函数 + 能力接线测试。"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

import backend.app.api.routes.macro_toolkit as macro_toolkit_route
from backend.app.core_finance.macro import analyze_cross_market_linkage
from backend.app.core_finance.macro.helpers import pearson_corr

_REPORT_DATE = date(2026, 7, 10)


def _wide_rows(*, with_fx: bool = True, with_oil: bool = True, with_vix: bool = False, days: int = 30) -> list[dict]:
    rows: list[dict] = []
    for i in range(days):
        sample = _REPORT_DATE - timedelta(days=i)
        row: dict = {
            "trade_date": sample,
            "treasury_10y": 1.80 + i * 0.01,
        }
        if with_fx:
            row["usdcny"] = 7.10 + i * 0.002
        if with_oil:
            row["brent_oil"] = 80.0 + i * 0.3
        if with_vix:
            row["vix"] = 18.0 + i * 0.1
        rows.append(row)
    return rows


def test_cross_market_capability_definition_is_wired_visible() -> None:
    definition = next(
        item for item in macro_toolkit_route._CAPABILITY_DEFINITIONS if item["key"] == "cross_market_linkage"
    )
    assert definition["route_status"] == "wired"
    assert definition["frontend_status"] == "visible"
    assert "fact_formal_yield_curve_daily" in definition["data_tables"]
    assert "fact_choice_macro_daily" in definition["data_tables"]
    assert set(definition["data_aliases"]) == {"CA.BRENT", "M0067855", "S0059749", "CA.US_GOV_10Y"}
    assert ("us_treasury_10y", "CA.US_GOV_10Y") in macro_toolkit_route._WIDE_SERIES_ALIASES
    assert ("CA.US_GOV_10Y", "US_GOVT", "10Y") in macro_toolkit_route._CURVE_ALIAS_POINTS
    assert "cross_market_linkage" in macro_toolkit_route._DECISION_SUMMARY_OBSERVATION_KEYS


def test_cross_market_linkage_complete_with_fx_and_oil() -> None:
    payload = analyze_cross_market_linkage(_wide_rows(), _REPORT_DATE)

    assert payload["observation_only"] is True
    assert payload["formal_use_allowed"] is False
    assert payload["data_status"] in {"complete", "degraded"}
    assert payload["overall_risk"] in {"LOW", "MEDIUM", "HIGH"}
    assert payload["bond_fx_corr"] is not None
    assert payload["bond_commodity_corr"] is not None
    # VIX 系统源仍未准入；美债腿由宽表/曲线 enrich 注入后才有相关
    assert "BOND_EQUITY_CORR_UNAVAILABLE" in payload["warnings"]
    assert "BOND_US_CORR_UNAVAILABLE" in payload["warnings"]


def test_cross_market_linkage_us_leg_available_when_wide_has_us10y() -> None:
    rows = _wide_rows()
    for i, row in enumerate(rows):
        row["us_treasury_10y"] = 4.2 + i * 0.01
    payload = analyze_cross_market_linkage(rows, _REPORT_DATE)
    assert payload["bond_us_corr"] is not None
    assert "BOND_US_CORR_UNAVAILABLE" not in payload["warnings"]
    assert "BOND_EQUITY_CORR_UNAVAILABLE" in payload["warnings"]
    assert payload["formal_use_allowed"] is False


def test_cross_market_linkage_unavailable_without_counterpart_series() -> None:
    # 仅有国债、无可算相关腿时，不得声称「常态」LOW。
    payload = analyze_cross_market_linkage(
        [{"trade_date": _REPORT_DATE, "treasury_10y": 1.85}],
        _REPORT_DATE,
    )
    assert payload["data_status"] == "unavailable"
    assert payload["overall_risk"] == "UNKNOWN"
    assert "常态" not in payload["recommendation"]
    assert payload["formal_use_allowed"] is False


def test_cross_market_linkage_unavailable_without_treasury() -> None:
    payload = analyze_cross_market_linkage(
        [{"trade_date": _REPORT_DATE, "usdcny": 7.2, "brent_oil": 80.0}],
        _REPORT_DATE,
    )
    assert payload["data_status"] == "unavailable"
    assert "TREASURY_10Y_MISSING" in payload["warnings"]
    assert payload["overall_risk"] == "UNKNOWN"


def test_cross_market_linkage_correlation_golden_samples() -> None:
    """相关系数数值黄金样本：完全正/负线性 → ±1；缺失序列 → None。"""
    bond = [2.5, 2.4, 2.3, 2.2, 2.1, 2.0]
    rows = [
        {
            "trade_date": _REPORT_DATE - timedelta(days=i),
            "treasury_10y": bond[i],
            "vix": 2.0 * bond[i] - 1.0,  # 完全正线性 → +1
            "brent_oil": 100.0 - 10.0 * bond[i],  # 完全负线性 → -1
            "us_treasury_10y": bond[i] + 1.8,  # 完全正线性 → +1
            # 无 usdcny：fx 腿无对齐样本 → corr None
        }
        for i in range(len(bond))
    ]

    payload = analyze_cross_market_linkage(rows, _REPORT_DATE)

    assert payload["bond_equity_corr"] == 1.0
    assert payload["bond_commodity_corr"] == -1.0
    assert payload["bond_us_corr"] == 1.0
    assert payload["bond_fx_corr"] is None
    assert "BOND_FX_CORR_UNAVAILABLE" in payload["warnings"]
    assert payload["linkages"]["bond_equity"]["correlation"] == 1.0
    assert payload["linkages"]["bond_commodity"]["correlation"] == -1.0
    # 3 条 |corr|>0.6 的联动腿 → HIGH
    assert payload["overall_risk"] == "HIGH"


def test_pearson_corr_constant_and_near_constant_series_return_none() -> None:
    """常数/近常数序列方差无定义：浮点抵消残留极小正值时不得伪装成数值相关。"""
    varying = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]

    assert pearson_corr([7.2] * 6, varying) is None
    assert pearson_corr(varying, [0.1] * 6) is None
    # 近常数（相对波动 ~1e-10）：方差项被浮点误差淹没，视为退化
    near_constant = [7.2 + i * 1e-9 for i in range(6)]
    assert pearson_corr(near_constant, varying) is None
    # 正常序列不受容差影响
    assert pearson_corr(varying, [2.0 * v for v in varying]) == 1.0
    assert pearson_corr(varying, [-1.0 * v for v in varying]) == -1.0


def test_pearson_corr_nan_or_inf_inputs_return_none() -> None:
    """NaN/inf 输入不得经 clamp 伪装成 1.0(min(1.0, nan) 按 CPython 语义返回 1.0)。"""
    varying = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]
    nan = float("nan")
    inf = float("inf")

    assert pearson_corr([1.0, 2.0, 3.0, 4.0, nan, 6.0], varying) is None
    assert pearson_corr([nan] * 6, varying) is None
    assert pearson_corr([1.0, 2.0, 3.0, 4.0, inf, 6.0], varying) is None
    assert pearson_corr(varying, [1.0, 2.0, 3.0, -inf, 5.0, 6.0]) is None


def test_pearson_corr_none_entries_return_none_without_raising() -> None:
    """共享工具 fail-safe：全 None / 含 None 序列不得在 sum() 阶段抛 TypeError。"""
    varying = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]

    assert pearson_corr([None] * 6, varying) is None
    assert pearson_corr(varying, [None] * 6) is None
    assert pearson_corr([1.0, 2.0, 3.0, None, 5.0, 6.0], varying) is None
    assert pearson_corr(varying, [1.0, 2.0, None, 4.0, 5.0, 6.0]) is None


def test_cross_market_linkage_constant_fx_series_corr_none() -> None:
    """FX 序列为常数时相关退化：corr 输出 None + 专属 warning，而非伪装的「零相关」。"""
    rows = _wide_rows(with_fx=False)
    for row in rows:
        row["usdcny"] = 7.2

    payload = analyze_cross_market_linkage(rows, _REPORT_DATE)

    assert payload["bond_fx_corr"] is None
    assert payload["linkages"]["bond_fx"]["correlation"] is None
    assert "BOND_FX_CORR_UNAVAILABLE" in payload["warnings"]
    # 油价腿仍可算，整体不至于 unavailable
    assert payload["bond_commodity_corr"] is not None


def test_cross_market_linkage_cn_us_spread_unit_bp() -> None:
    """cn_us_spread 单位样本：输入为百分点，输出为 bp（(2.48-4.28)*100 = -180bp）。"""
    rows = _wide_rows()
    for i, row in enumerate(rows):
        row["us_treasury_10y"] = 4.28 + i * 0.01
    rows[0]["treasury_10y"] = 2.48

    payload = analyze_cross_market_linkage(rows, _REPORT_DATE)

    assert payload["linkages"]["bond_us"]["cn_us_spread"] == -180.0


def test_cross_market_card_surfaces_risk_metric() -> None:
    raw = analyze_cross_market_linkage(_wide_rows(with_vix=True), _REPORT_DATE)
    definition = next(
        item for item in macro_toolkit_route._CAPABILITY_DEFINITIONS if item["key"] == "cross_market_linkage"
    )
    card = macro_toolkit_route._capability_result_card(definition, raw)
    assert card["key"] == "cross_market_linkage"
    assert card["primary_metric"]["label"] == "联动风险"
    assert card["primary_metric"]["value"] == raw["overall_risk"]
    assert card["status"] in {"complete", "degraded", "unavailable"}
