"""M12 跨市场联动（cross_market_linkage）纯函数 + 能力接线测试。"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

import backend.app.api.routes.macro_toolkit as macro_toolkit_route
from backend.app.core_finance.macro import analyze_cross_market_linkage

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
