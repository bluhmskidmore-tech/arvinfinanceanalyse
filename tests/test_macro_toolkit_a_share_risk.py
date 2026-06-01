from __future__ import annotations

import pandas as pd

from backend.app.core_finance.macro.a_share_stampede_risk import (
    DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG,
    compute_a_share_stampede_risk,
)


def test_crash_day_is_red_with_position_brake() -> None:
    observations = _history_frame(
        latest_pct=[4.0] * 30 + [-1.0] * 90 + [-3.5] * 140 + [-5.8] * 70,
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
