"""M13 利率拐点判断（rate_turning_point）纯函数 + 能力接线测试。"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

import backend.app.api.routes.macro_toolkit as macro_toolkit_route
from backend.app.core_finance.macro import compute_rate_turning_point

_REPORT_DATE = date(2026, 7, 10)


def _curve_rows(days: int) -> list[dict[str, object]]:
    """构造确定性的国债曲线历史（i=0 为最新交易日，往前 days 天）。

    形态设计为"筑底"：当前 10Y 处于低分位、近 5 日反弹、20 日内曲线走陡。
    """
    rows: list[dict[str, object]] = []
    for i in range(days):
        sample_date = _REPORT_DATE - timedelta(days=i)
        if i == 0:
            ten_year = 1.75
        elif i <= 4:
            ten_year = 1.70
        elif i <= 9:
            ten_year = 1.68
        else:
            ten_year = 2.20
        one_year = 1.30 if i <= 4 else 1.95
        rows.append(
            {"biz_date": sample_date, "curve_id": "CN_GOVT", "tenor": "10Y", "rate_value": ten_year}
        )
        rows.append(
            {"biz_date": sample_date, "curve_id": "CN_GOVT", "tenor": "1Y", "rate_value": one_year}
        )
    return rows


def test_rate_turning_point_deterministic_bottoming_on_seed_curve() -> None:
    payload = compute_rate_turning_point(_curve_rows(300), report_date=_REPORT_DATE)

    assert payload["data_status"] == "complete"
    assert payload["warnings"] == []
    assert payload["observation_only"] is True
    assert payload["formal_use_allowed"] is False
    assert payload["direction"] == "bottoming"
    assert payload["conviction"] == "HIGH"
    assert payload["recommended_duration_stance"] == "shorten"
    assert payload["current_10y"] == pytest.approx(1.75)
    # slope = (1.75 - 1.30) * 100
    assert payload["current_slope_10y_1y_bp"] == pytest.approx(45.0)
    # (1.75 - 1.68) * 100
    assert payload["change_5d_bp"] == pytest.approx(7.0)
    # (1.75 - 2.20) * 100
    assert payload["change_20d_bp"] == pytest.approx(-45.0)
    # 251 个历史观测里 9 个低于当前值
    assert payload["percentile_1y"] == pytest.approx(9 / 251 * 100, abs=0.01)
    assert {item["key"] for item in payload["signals"]} == {"level", "five_day_move", "slope"}


def test_rate_turning_point_degrades_when_medium_window_short() -> None:
    payload = compute_rate_turning_point(_curve_rows(12), report_date=_REPORT_DATE)

    assert payload["data_status"] == "degraded"
    assert "TURNING_POINT_MEDIUM_WINDOW_SHORT" in payload["warnings"]
    assert payload["change_20d_bp"] is None
    assert payload["formal_use_allowed"] is False
    # 方向仍可基于水平分位 + 5 日动量给出，但不得声称 complete
    assert payload["direction"] in {"bottoming", "topping", "range"}


def test_rate_turning_point_unavailable_on_short_history() -> None:
    payload = compute_rate_turning_point(_curve_rows(5), report_date=_REPORT_DATE)

    assert payload["data_status"] == "unavailable"
    assert payload["direction"] == "unavailable"
    assert "TURNING_POINT_HISTORY_SHORT" in payload["warnings"]
    assert payload["recommended_duration_stance"] is None
    assert payload["observation_only"] is True
    assert payload["formal_use_allowed"] is False


def test_rate_turning_point_unavailable_without_curve_rows() -> None:
    payload = compute_rate_turning_point([], report_date=_REPORT_DATE)

    assert payload["data_status"] == "unavailable"
    assert "NO_GOVERNMENT_CURVE_HISTORY" in payload["warnings"]
    assert payload["observation_only"] is True
    assert payload["formal_use_allowed"] is False


def test_rate_turning_point_capability_definition_is_wired_observation() -> None:
    definition = next(
        item
        for item in macro_toolkit_route._CAPABILITY_DEFINITIONS
        if item["key"] == "rate_turning_point"
    )

    assert definition["legacy_module"] == "M13"
    assert definition["implementation_status"] == "library_ready"
    assert definition["route_status"] == "wired"
    assert definition["frontend_status"] == "visible"
    assert "fact_formal_yield_curve_daily" in definition["data_tables"]
    assert set(definition["data_aliases"]) == {"S0059743", "S0059749"}


def test_rate_turning_point_capability_card_surfaces_direction_and_level() -> None:
    raw = compute_rate_turning_point(_curve_rows(300), report_date=_REPORT_DATE)
    definition = next(
        item
        for item in macro_toolkit_route._CAPABILITY_DEFINITIONS
        if item["key"] == "rate_turning_point"
    )
    card = macro_toolkit_route._capability_result_card(definition, raw)

    assert card["key"] == "rate_turning_point"
    assert card["status"] == "complete"
    assert card["primary_metric"]["label"] == "10Y国债"
    assert card["primary_metric"]["value"] == pytest.approx(1.75)
    assert card["score"] == pytest.approx(raw["percentile_1y"], abs=1e-6)
    assert any(item == "direction=bottoming" for item in card["evidence"])
    assert raw["headline"] in str(card["headline"])


def test_rate_turning_point_degraded_card_keeps_warning_visible() -> None:
    raw = compute_rate_turning_point(_curve_rows(12), report_date=_REPORT_DATE)
    definition = next(
        item
        for item in macro_toolkit_route._CAPABILITY_DEFINITIONS
        if item["key"] == "rate_turning_point"
    )
    card = macro_toolkit_route._capability_result_card(definition, raw)

    assert card["status"] == "degraded"
    assert "TURNING_POINT_MEDIUM_WINDOW_SHORT" in card["warnings"]
