"""宏观 M-1 / M10：领先指标缺月诚实性 + 共同月对齐。

锁定行为：
- 稀疏月度序列中缺失字段保留为 None（不 zero-fill）
- `_history_mean` / 分项得分只对可用月求均值
- 主窗 12 个完整日历月；`history_samples` 披露 used/total
- 缺失月触发 `*_HISTORY_MISSING_MONTHS` 警告
- 严格 6/6 共同月；无共同月时禁止部分重归一主结论
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd

import backend.app.api.routes.macro_toolkit as macro_toolkit_route
from backend.app.core_finance.macro.leading_indicator import (
    _history_mean,
    _monthly_series,
    compute_leading_indicator,
)


def _row(
    trade_date: date,
    *,
    pmi: float | None = 50.0,
    m2_yoy: float | None = 8.0,
    social_financing_yoy: float | None = 8.0,
    term_spread_10y_1y: float | None = 60.0,
    credit_spread_aaa_3y: float | None = 40.0,
    brent_oil: float | None = 80.0,
    source_month: date | None = None,
) -> dict[str, object]:
    """默认六腿齐全；source_date 默认落在 trade_date 所在月（真实观测）。"""
    src = source_month or date(trade_date.year, trade_date.month, 1)
    row: dict[str, object] = {"trade_date": trade_date}
    for field, value in (
        ("pmi", pmi),
        ("m2_yoy", m2_yoy),
        ("social_financing_yoy", social_financing_yoy),
        ("term_spread_10y_1y", term_spread_10y_1y),
        ("credit_spread_aaa_3y", credit_spread_aaa_3y),
        ("brent_oil", brent_oil),
    ):
        row[field] = value
        row[f"{field}_source_date"] = src if value is not None else None
    # 日频腿用 trade_date 作为 source_date，便于“月内最后一笔”语义。
    if term_spread_10y_1y is not None:
        row["term_spread_10y_1y_source_date"] = trade_date
    if credit_spread_aaa_3y is not None:
        row["credit_spread_aaa_3y_source_date"] = trade_date
    if brent_oil is not None:
        row["brent_oil_source_date"] = trade_date
    return row


def test_history_mean_skips_none_months() -> None:
    mean, used, total = _history_mean([Decimal("10"), None, Decimal("20"), None])
    assert mean == Decimal("15")
    assert used == 2
    assert total == 4

    zero_filled = (Decimal("10") + Decimal("0") + Decimal("20") + Decimal("0")) / Decimal("4")
    assert mean != zero_filled
    assert mean > zero_filled


def test_monthly_series_keeps_missing_as_none() -> None:
    rows = [
        _row(date(2026, 3, 31), pmi=50.0, m2_yoy=None, social_financing_yoy=8.0, brent_oil=80.0),
        _row(date(2026, 2, 28), pmi=None, m2_yoy=9.0, social_financing_yoy=None, brent_oil=None),
    ]
    # History-only window: 12 complete months strictly before as_of_month.
    series = _monthly_series(
        rows,
        report_date=date(2026, 3, 31),
        as_of_month=(2026, 3),
        lookback_months=12,
    )

    assert len(series["m2"]) == 12
    assert series["m2"][0] == Decimal("9")  # 2026-02
    assert series["sf"][0] is None
    assert series["pmi"][0] is None
    assert series["oil"][0] is None


def test_absent_calendar_month_is_disclosed_and_not_zero_filled() -> None:
    rows = [
        _row(date(2026, 1, 31), m2_yoy=12.0, social_financing_yoy=10.0, brent_oil=84.0),
        _row(date(2025, 11, 30), m2_yoy=8.0, social_financing_yoy=6.0, brent_oil=80.0),
    ]

    result = compute_leading_indicator(rows, date(2026, 1, 31))

    assert result["as_of_month"] == "2026-01"
    assert result["history_samples"] == {
        "m2_yoy": {"used": 1, "total": 12},
        "social_financing_yoy": {"used": 1, "total": 12},
        "commodity": {"used": 1, "total": 12},
    }
    assert {
        "M2_HISTORY_MISSING_MONTHS",
        "SOCIAL_FINANCING_HISTORY_MISSING_MONTHS",
        "COMMODITY_HISTORY_MISSING_MONTHS",
    }.issubset(set(result["warnings"]))
    assert result["data_status"] == "degraded"
    assert Decimal(str(result["m2_score"])) == Decimal("70")
    assert "LEI_LOOKBACK_UNGOVERNED" not in result["warnings"]
    assert "PIT_METADATA_UNAVAILABLE" in result["warnings"]
    assert "LEI_UNIT_CONTRACT_UNFROZEN" in result["warnings"]


def test_api_loader_ffill_is_not_counted_as_a_new_monthly_observation() -> None:
    frames = {
        alias: pd.DataFrame(columns=["date", "value"])
        for _, alias in macro_toolkit_route._WIDE_SERIES_ALIASES
    }
    frames["M0001385"] = pd.DataFrame(
        [
            {"date": date(2025, 12, 1), "value": 8.0},
            {"date": date(2026, 1, 1), "value": 9.0},
            {"date": date(2026, 3, 1), "value": 12.0},
        ]
    )
    frames["M5525763"] = pd.DataFrame(
        [
            {"date": date(2025, 12, 1), "value": 6.0},
            {"date": date(2026, 1, 1), "value": 7.0},
            {"date": date(2026, 3, 1), "value": 10.0},
        ]
    )
    frames["M0017126"] = pd.DataFrame(
        [
            {"date": date(2025, 12, 1), "value": 49.0},
            {"date": date(2026, 1, 1), "value": 50.0},
            {"date": date(2026, 3, 1), "value": 51.0},
        ]
    )
    frames["CA.BRENT"] = pd.DataFrame(
        [
            {"date": date(2025, 12, 15), "value": 80.0},
            {"date": date(2026, 1, 15), "value": 81.0},
            {"date": date(2026, 2, 15), "value": 82.0},
            {"date": date(2026, 3, 15), "value": 84.0},
        ]
    )
    frames["S0059670"] = pd.DataFrame(
        [
            {"date": date(2025, 12, 15), "value": 40.0},
            {"date": date(2026, 1, 15), "value": 40.0},
            {"date": date(2026, 2, 15), "value": 40.0},
            {"date": date(2026, 3, 15), "value": 40.0},
        ]
    )

    wide_rows = macro_toolkit_route._load_macro_wide_rows(
        "unused.duckdb",
        date(2026, 3, 31),
        [
            {"biz_date": date(2026, 1, 31)},
            {"biz_date": date(2026, 2, 28)},
            {"biz_date": date(2026, 3, 31)},
        ],
        frames_by_alias=frames,
    )
    february = next(row for row in wide_rows if row["trade_date"] == date(2026, 2, 28))
    assert february["m2_yoy"] == 9.0
    assert february["m2_yoy_source_date"] == date(2026, 1, 1)

    # Task 3：曲线派生 term/credit 由 loader 挂同源 *_source_date；无曲线日则注入同日腿。
    for row in wide_rows:
        trade = row["trade_date"]
        assert isinstance(trade, date)
        if row.get("term_spread_10y_1y") is None:
            row["term_spread_10y_1y"] = 60.0
            row["term_spread_10y_1y_source_date"] = trade
        else:
            assert row.get("term_spread_10y_1y_source_date") == trade
        if row.get("credit_spread_aaa_3y") is not None and row.get("credit_spread_aaa_3y_source_date") is None:
            row["credit_spread_aaa_3y_source_date"] = trade

    result = compute_leading_indicator(wide_rows, date(2026, 3, 31))

    assert result["as_of_month"] == "2026-03"
    assert result["available_component_count"] == 6
    assert result["component_count"] == 6
    assert result["history_samples"]["m2_yoy"]["total"] == 12
    assert result["history_samples"]["m2_yoy"]["used"] == 2
    assert "M2_HISTORY_MISSING_MONTHS" in result["warnings"]
    assert "SOCIAL_FINANCING_HISTORY_MISSING_MONTHS" in result["warnings"]
    assert result["observation_only"] is True
    assert result["formal_use_allowed"] is False
    assert "LEI_LOOKBACK_UNGOVERNED" not in result["warnings"]

def test_zero_yoy_and_commodity_values_are_scored_not_defaulted() -> None:
    rows = [
        _row(date(2026, 1, 31), m2_yoy=0.0, social_financing_yoy=0.0, brent_oil=0.0),
        _row(date(2025, 12, 31), m2_yoy=10.0, social_financing_yoy=10.0, brent_oil=80.0),
    ]

    result = compute_leading_indicator(rows, date(2026, 1, 31))

    assert result["as_of_month"] == "2026-01"
    assert result["m2_score"] == 0.0
    assert result["social_financing_score"] == 0.0
    assert result["commodity_score"] == 0.0
    assert result["available_component_count"] == 6
    assert result["component_coverage_pct"] == 100.0
    assert result["observation_only"] is True
    assert result["formal_use_allowed"] is False
    assert result["lookback_months"] == 12
    assert result["history_window"]["start_month"] == "2025-01"
    assert result["history_window"]["end_month"] == "2025-12"
    assert "LEI_LOOKBACK_UNGOVERNED" not in result["warnings"]
    assert "PIT_METADATA_UNAVAILABLE" in result["warnings"]
    assert result["shadow_24m"]["shadow"] is True
    assert result["shadow_24m"]["lookback_months"] == 24


def test_no_common_month_is_unavailable_not_partially_renormalized() -> None:
    rows = [
        _row(
            date(2026, 1, 31),
            pmi=None,
            m2_yoy=None,
            social_financing_yoy=None,
            term_spread_10y_1y=None,
            credit_spread_aaa_3y=None,
            brent_oil=None,
        ),
        _row(date(2025, 12, 31)),
    ]

    result = compute_leading_indicator(rows, date(2026, 1, 31))

    # December is a full common month → as_of should be 2025-12, not partial Jan.
    assert result["as_of_month"] == "2025-12"
    assert result["available_component_count"] == 6
    assert result["lei_index"] is not None

    # Pure missing month with no 6/6 anywhere:
    emptyish = [
        _row(
            date(2026, 1, 31),
            pmi=None,
            m2_yoy=8.0,
            social_financing_yoy=8.0,
            term_spread_10y_1y=60.0,
            credit_spread_aaa_3y=40.0,
            brent_oil=80.0,
        )
    ]
    unavailable = compute_leading_indicator(emptyish, date(2026, 1, 31))
    assert unavailable["data_status"] == "unavailable"
    assert unavailable["lei_index"] is None
    assert unavailable["economic_state"] == "数据不足"
    assert unavailable["trend"] == "数据不足"
    assert "LEI_NO_COMMON_COMPUTABLE_MONTH" in unavailable["warnings"]
    assert unavailable["pmi_score"] is None
    assert unavailable["available_component_count"] == 0


def test_empty_result_has_no_neutral_score_and_keeps_governance_flags() -> None:
    result = compute_leading_indicator([], date(2026, 3, 31))

    assert result["data_status"] == "unavailable"
    assert result["lei_index"] is None
    assert result["economic_state"] == "数据不足"
    assert result["trend"] == "数据不足"
    assert result["observation_only"] is True
    assert result["formal_use_allowed"] is False
    assert result["as_of_month"] is None
    assert result["alignment_policy"] == "latest_common_computable_month"
    assert macro_toolkit_route._capability_result_score("leading_indicator", result) is None
    assert macro_toolkit_route._capability_primary_metric("leading_indicator", result) is None
    assert (
        macro_toolkit_route._capability_result_headline("leading_indicator", result)
        == "暂无可用宏观数据，无法计算领先指标。"
    )


def test_compute_leading_indicator_missing_months_do_not_zero_fill_mean() -> None:
    """稀疏历史月：均值只用可用月；得分不得被缺失月的假 0 拉偏。"""
    rows = [
        _row(
            date(2026, 3, 31),
            pmi=51.0,
            m2_yoy=12.0,
            social_financing_yoy=10.0,
            brent_oil=84.0,
        ),
        _row(
            date(2026, 2, 28),
            pmi=None,
            m2_yoy=None,
            social_financing_yoy=None,
            term_spread_10y_1y=None,
            credit_spread_aaa_3y=None,
            brent_oil=None,
        ),
        _row(
            date(2026, 1, 31),
            pmi=50.0,
            m2_yoy=8.0,
            social_financing_yoy=6.0,
            brent_oil=80.0,
        ),
        _row(
            date(2025, 12, 31),
            pmi=49.0,
            m2_yoy=None,
            social_financing_yoy=None,
            term_spread_10y_1y=None,
            credit_spread_aaa_3y=None,
            brent_oil=None,
        ),
    ]

    result = compute_leading_indicator(rows, date(2026, 3, 31))

    assert result["as_of_month"] == "2026-03"
    assert result["history_samples"] == {
        "m2_yoy": {"used": 1, "total": 12},
        "social_financing_yoy": {"used": 1, "total": 12},
        "commodity": {"used": 1, "total": 12},
    }
    assert "M2_HISTORY_MISSING_MONTHS" in result["warnings"]
    assert "SOCIAL_FINANCING_HISTORY_MISSING_MONTHS" in result["warnings"]
    assert "COMMODITY_HISTORY_MISSING_MONTHS" in result["warnings"]
    assert result["data_status"] == "degraded"

    honest_m2_score = Decimal("50") + (Decimal("12") - Decimal("8")) * Decimal("5")  # 70
    honest_sf_score = Decimal("50") + (Decimal("10") - Decimal("6")) * Decimal("5")  # 70
    honest_commodity = Decimal("50") + (Decimal("84") - Decimal("80")) / Decimal("80") * Decimal(
        "500"
    )  # 75
    honest_commodity = max(Decimal("0"), min(Decimal("100"), honest_commodity))

    assert Decimal(str(result["m2_score"])) == honest_m2_score
    assert Decimal(str(result["social_financing_score"])) == honest_sf_score
    assert Decimal(str(result["commodity_score"])) == honest_commodity

    zero_fill_m2_avg = Decimal("8") / Decimal("12")
    zero_fill_m2_score = Decimal("50") + (Decimal("12") - zero_fill_m2_avg) * Decimal("5")
    zero_fill_m2_score = max(Decimal("0"), min(Decimal("100"), zero_fill_m2_score))
    assert Decimal(str(result["m2_score"])) != zero_fill_m2_score
    assert Decimal(str(result["m2_score"])) < zero_fill_m2_score


def test_compute_leading_indicator_discloses_history_sample_counts_when_all_history_missing() -> None:
    rows = [
        _row(date(2026, 3, 31), m2_yoy=10.0, social_financing_yoy=8.0, brent_oil=80.0),
        _row(
            date(2026, 2, 28),
            m2_yoy=None,
            social_financing_yoy=7.0,
            brent_oil=70.0,
            # Keep other legs so Feb is NOT a competing common month with incomplete m2;
            # as_of remains March; Feb contributes sf/oil history only.
            pmi=50.0,
            term_spread_10y_1y=60.0,
            credit_spread_aaa_3y=40.0,
        ),
    ]
    result = compute_leading_indicator(rows, date(2026, 3, 31))

    assert result["as_of_month"] == "2026-03"
    assert result["history_samples"]["m2_yoy"] == {"used": 0, "total": 12}
    assert result["history_samples"]["social_financing_yoy"] == {"used": 1, "total": 12}
    assert result["history_samples"]["commodity"] == {"used": 1, "total": 12}
    assert "M2_HISTORY_MISSING_MONTHS" in result["warnings"]
    assert "SOCIAL_FINANCING_HISTORY_MISSING_MONTHS" in result["warnings"]
    assert "COMMODITY_HISTORY_MISSING_MONTHS" in result["warnings"]
    assert Decimal(str(result["m2_score"])) == Decimal("50")


def test_common_month_alignment_fields_present_on_success() -> None:
    rows = [_row(date(2026, 6, 30)), _row(date(2026, 5, 31))]
    result = compute_leading_indicator(rows, date(2026, 7, 20))
    assert result["as_of_month"] == "2026-06"
    assert result["alignment_policy"] == "latest_common_computable_month"
    assert result["alignment_lag_months"] == 1
    assert isinstance(result["component_evidence"], list)
    assert isinstance(result["latest_available_component_evidence"], list)
    assert result["lookback_months"] == 12
    assert result["shadow_24m"]["lookback_months"] == 24
