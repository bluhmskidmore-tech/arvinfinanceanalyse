from __future__ import annotations

import pandas as pd
import pytest

from backend.app.core_finance.macro.a_share_stampede_risk import (
    DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG,
    compute_a_share_stampede_risk,
)

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_macro_toolkit,
]


def test_crash_day_is_red_with_position_brake() -> None:
    # 指数日内 high/low 不可得后，reversal 维度不再计分，red 只能由宽度 +
    # 跌停压力 + 放量下跌证明，因此崩盘样本的跌停家数需真正越过 80 只红线。
    observations = _history_frame(
        latest_pct=[4.0] * 30 + [-1.0] * 90 + [-3.5] * 120 + [-5.8] * 90,
        latest_amount_multiplier=1.65,
        latest_close_location=0.12,
    )

    payload = compute_a_share_stampede_risk(observations, config=DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG)

    assert payload["risk_level"] == "red"
    assert payload["risk_score"] >= 70
    assert "只减不加" in payload["position_rule"]
    assert "上涨家数低于" in " / ".join(payload["triggered_rules"])
    assert payload["metrics"]["limit_down_count"] >= 60


def test_index_mask_day_is_at_least_yellow() -> None:
    observations = _history_frame(
        latest_pct=[0.4] * 70 + [-0.8] * 210 + [-1.8] * 50,
        latest_amount_multiplier=1.05,
        latest_close_location=0.8,
    )

    payload = compute_a_share_stampede_risk(observations, config=DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG)

    assert payload["risk_level"] in {"yellow", "orange", "red"}
    assert any("指数与宽度背离" in item for item in payload["triggered_rules"])


def test_st_limit_down_does_not_pollute_core_red_risk() -> None:
    regular = _history_frame(latest_pct=[1.0] * 240 + [-1.0] * 30, prefix="R")
    st_rows = _history_frame(latest_pct=[-5.0] * 80, prefix="ST")
    st_rows["is_st"] = True
    observations = pd.concat([regular, st_rows], ignore_index=True)

    payload = compute_a_share_stampede_risk(observations, config=DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG)

    assert payload["risk_level"] != "red"
    assert payload["metrics"]["st_limit_down_count"] == 80
    assert any("ST" in item for item in payload["warnings"])


def test_no_limit_new_stock_rows_are_excluded_from_core_risk() -> None:
    regular = _history_frame(latest_pct=[1.0] * 220 + [-0.5] * 40, prefix="R")
    new_rows = _history_frame(latest_pct=[-24.0] * 70, prefix="N")
    new_rows["has_price_limit"] = False
    observations = pd.concat([regular, new_rows], ignore_index=True)

    payload = compute_a_share_stampede_risk(observations, config=DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG)

    assert payload["risk_level"] != "red"
    assert payload["metrics"]["no_limit_stock_count"] == 70
    assert any("无涨跌幅限制" in item for item in payload["warnings"])


def test_strong_broad_rally_does_not_trigger_turnover_stagnation() -> None:
    observations = _history_frame(
        latest_pct=[2.2] * 260 + [-0.3] * 20,
        latest_amount_multiplier=1.7,
        latest_close_location=0.88,
    )

    payload = compute_a_share_stampede_risk(observations, config=DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG)

    assert payload["risk_level"] in {"green", "yellow"}
    assert not any("放量滞涨" in item for item in payload["triggered_rules"])


def test_missing_limit_quality_flags_do_not_count_as_limit_down() -> None:
    observations = _history_frame(latest_pct=[1.0] * 220 + [-0.8] * 60)
    latest_date = observations["trade_date"].max()
    latest_mask = observations["trade_date"] == latest_date
    observations.loc[latest_mask, "is_limit_down_flag"] = pd.NA
    observations.loc[latest_mask, "is_limit_up_flag"] = pd.NA
    observations.loc[latest_mask, "highlimit"] = pd.NA
    observations.loc[latest_mask, "lowlimit"] = pd.NA

    payload = compute_a_share_stampede_risk(observations, config=DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG)

    assert payload["metrics"]["limit_down_count"] == 0
    assert payload["metrics"]["limit_up_count"] == 0
    assert payload["status"] == "degraded"


def test_calm_day_without_index_reversal_does_not_score_the_reversal_dimension() -> None:
    """每只股票各自从盘中高点回落 2.5%（A股常态振幅），指数等权收涨 1%。

    横截面均价代理会把"全市场平均 (最高价-收盘价)/收盘价"当成指数回落，于是
    常态交易日就触发按指数标定的 1%/1.5%/2% 阈值。没有真实指数日内序列时，该
    维度必须不计分并显式披露。
    """
    observations = _history_frame(latest_pct=[1.0] * 300)
    latest_mask = observations["trade_date"] == observations["trade_date"].max()
    latest_close = observations.loc[latest_mask, "close_value"]
    observations.loc[latest_mask, "high_value"] = latest_close * 1.025
    observations.loc[latest_mask, "low_value"] = latest_close * 0.995

    payload = compute_a_share_stampede_risk(observations, config=DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG)

    assert payload["category_scores"]["reversal"] == 0
    assert not any("日内高点回落" in rule for rule in payload["triggered_rules"])
    assert payload["metrics"]["index_drawdown_from_high"] is None
    assert payload["metrics"]["close_location"] is None
    assert any("INDEX_INTRADAY_PROXY_UNAVAILABLE" in warning for warning in payload["warnings"])
    assert payload["status"] == "degraded"


def test_index_return_is_immune_to_universe_composition_change() -> None:
    """新上市股票只在最新日出现时，横截面均价会跳升，被记成指数大涨。

    等权逐股涨跌幅不受成分变动影响：全部股票当日 -1%，指数口径就是 -1%。
    """
    incumbents = _history_frame(latest_pct=[-1.0] * 200, prefix="R")
    newcomers = _history_frame(latest_pct=[-1.0] * 20, prefix="N")
    latest_date = newcomers["trade_date"].max()
    newcomers = newcomers[newcomers["trade_date"] == latest_date].copy()
    # 高价新股，放大横截面均价代理的成分变动偏差。
    for column in ("open_value", "high_value", "low_value", "close_value", "highlimit", "lowlimit"):
        newcomers[column] = newcomers[column] * 5.0
    observations = pd.concat([incumbents, newcomers], ignore_index=True)

    payload = compute_a_share_stampede_risk(observations, config=DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG)

    assert payload["metrics"]["core_stock_count"] == 220
    assert payload["metrics"]["index_return"] == pytest.approx(-0.01)


def test_amount_ma20_excludes_the_current_day() -> None:
    observations = _history_frame(latest_pct=[1.0] * 200, latest_amount_multiplier=2.0)

    payload = compute_a_share_stampede_risk(observations, config=DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG)

    assert payload["metrics"]["amount_ma20"] == pytest.approx(200 * 1_000_000.0)
    assert payload["metrics"]["turnover_ratio_ma20"] == pytest.approx(2.0)


def test_short_history_fails_closed_instead_of_scoring_turnover() -> None:
    frame = _history_frame(latest_pct=[1.0] * 200, latest_amount_multiplier=2.0)
    kept_dates = sorted(frame["trade_date"].unique())[-5:]
    frame = frame[frame["trade_date"].isin(kept_dates)].copy()

    payload = compute_a_share_stampede_risk(frame, config=DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG)

    assert payload["metrics"]["amount_ma20"] is None
    assert payload["metrics"]["turnover_ratio_ma20"] is None
    assert payload["category_scores"]["turnover_stress"] == 0
    assert any("TURNOVER_MA20_HISTORY_INSUFFICIENT" in warning for warning in payload["warnings"])
    assert payload["status"] == "degraded"


def test_category_weight_config_scales_the_category_score() -> None:
    observations = _history_frame(
        latest_pct=[0.4] * 70 + [-0.8] * 210 + [-1.8] * 50,
        latest_amount_multiplier=1.05,
    )

    default_payload = compute_a_share_stampede_risk(observations, config=DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG)
    doubled_payload = compute_a_share_stampede_risk(observations, config={"weights": {"breadth": 60}})

    assert default_payload["category_scores"]["breadth"] == 30
    assert default_payload["risk_score"] == 30
    assert default_payload["risk_level"] == "yellow"
    assert doubled_payload["category_scores"]["breadth"] == 60
    assert doubled_payload["risk_score"] == 60
    assert doubled_payload["risk_level"] == "orange"
    assert doubled_payload["category_weights"]["breadth"] == 60


def test_risk_level_boundaries_come_from_config() -> None:
    observations = _history_frame(
        latest_pct=[0.4] * 70 + [-0.8] * 210 + [-1.8] * 50,
        latest_amount_multiplier=1.05,
    )

    payload = compute_a_share_stampede_risk(
        observations,
        config={"risk_levels": {"yellow": [10, 24], "orange": [25, 69]}},
    )

    assert payload["risk_score"] == 30
    assert payload["risk_level"] == "orange"
    assert payload["risk_level_policy"]["orange"] == 25


def test_red_requires_severe_categories_is_configurable_and_disclosed() -> None:
    """risk_score 落在声明的 red 区间但只有 1 个 severe 类别时仍报 orange。

    这个附加条件原先硬编码在 `_risk_level` 里，与配置声明的 `red: [70, 100]`
    不一致，必须变成显式配置键并在 payload 中披露。
    """
    observations = _history_frame(latest_pct=[1.0] * 240 + [-1.0] * 30)

    strict_payload = compute_a_share_stampede_risk(observations, config={"weights": {"breadth": 90}})
    relaxed_payload = compute_a_share_stampede_risk(
        observations,
        config={
            "weights": {"breadth": 90},
            "risk_levels": {"red_requires_severe_categories": 1},
        },
    )

    assert strict_payload["risk_score"] == 90
    assert strict_payload["severe_categories"] == ["breadth_severe"]
    assert strict_payload["risk_level"] == "orange"
    assert strict_payload["risk_level_policy"]["red_requires_severe_categories"] == 2
    assert relaxed_payload["risk_level"] == "red"
    assert relaxed_payload["risk_level_policy"]["red_requires_severe_categories"] == 1


def _history_frame(
    *,
    latest_pct: list[float],
    prefix: str = "S",
    latest_amount_multiplier: float = 1.0,
    latest_close_location: float = 0.55,
) -> pd.DataFrame:
    dates = pd.date_range("2026-04-01", periods=21, freq="D")
    rows: list[dict[str, object]] = []
    for stock_no, latest_change in enumerate(latest_pct):
        stock_code = f"{stock_no:06d}.{prefix}"
        close = 100.0 + stock_no * 0.01
        for day_no, trade_date in enumerate(dates):
            is_latest = day_no == len(dates) - 1
            pctchange = latest_change if is_latest else 0.2
            previous_close = close
            close = previous_close * (1 + pctchange / 100)
            high = close * (1 + max(0.02, (1 - latest_close_location) * 0.04 if is_latest else 0.02))
            low = close * (1 - max(0.02, latest_close_location * 0.02 if is_latest else 0.02))
            amount_multiplier = latest_amount_multiplier if is_latest else 1.0
            lowlimit = close if is_latest and pctchange <= -5.0 else previous_close * 0.9
            highlimit = close if is_latest and pctchange >= 9.5 else previous_close * 1.1
            rows.append(
                {
                    "trade_date": trade_date.date().isoformat(),
                    "stock_code": stock_code,
                    "open_value": previous_close,
                    "high_value": high,
                    "low_value": low,
                    "close_value": close,
                    "amount": 1_000_000.0 * amount_multiplier,
                    "pctchange": pctchange,
                    "highlimit": highlimit,
                    "lowlimit": lowlimit,
                    "is_st": False,
                    "has_price_limit": True,
                    "is_bse": False,
                }
            )
    return pd.DataFrame(rows)
