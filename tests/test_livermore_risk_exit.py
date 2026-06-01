from __future__ import annotations

from typing import Any, cast

from backend.app.core_finance.livermore_risk_exit import (
    FORMULA_VERSION,
    RiskExitSnapshot,
    compute_risk_exit,
)


# 21 根 K 线最少；触发日量 > 1.3x 前 20 日均量
def _high_volume_history(quiet: float = 1_000_000.0, surge_ratio: float = 2.0) -> list[float]:
    return [quiet] * 20 + [quiet * surge_ratio]


def _quiet_volume_history(volume: float = 1_000_000.0) -> list[float]:
    return [volume] * 21


def test_compute_risk_exit_flags_two_consecutive_closes_below_ema10_with_volume_confirmation() -> None:
    closes = [
        10.0, 10.1, 10.2, 10.4, 10.6, 10.8, 10.9, 11.0, 11.1, 11.0,
        10.9, 11.0, 11.1, 11.2, 11.0, 10.9, 10.8, 11.0, 11.1, 9.8, 9.1,
    ]
    result = compute_risk_exit(
        as_of_date="2026-04-29",
        snapshots=[
            RiskExitSnapshot(
                stock_code="000001.SZ",
                stock_name="Alpha",
                entry_cost=10.5,
                bars_since_entry=6,
                close_history=closes,
                volume_history=_high_volume_history(surge_ratio=2.0),
            )
        ],
    )

    payload = cast(dict[str, Any], result.payload)
    assert payload["formula_version"] == FORMULA_VERSION
    assert payload["signal_count"] == 1
    items = cast(list[dict[str, Any]], payload["items"])
    item = items[0]
    assert item["stock_code"] == "000001.SZ"
    assert item["reason"] == "2d_below_ema10_with_volume"
    assert item["bars_since_entry"] == 6
    assert item["latest_close"] == 9.1
    assert item["latest_ema10"] > item["latest_close"]
    assert item["prior_ema10"] > item["prior_close"]
    assert item["volume_ratio"] >= 1.3
    watch_items = cast(list[dict[str, Any]], payload["watch_items"])
    assert len(watch_items) == 1
    watch_item = watch_items[0]
    assert watch_item["stock_code"] == "000001.SZ"
    assert watch_item["triggered"] is True
    assert watch_item["price_below_ema"] is True
    assert watch_item["volume_confirmed"] is True
    assert watch_item["exit_watch_price"] == watch_item["latest_ema10"]


def test_compute_risk_exit_does_not_trigger_when_price_breaks_but_volume_is_low() -> None:
    """量能未确认 — 价格虽跌破 EMA10 但量能不放大，不触发退出。"""
    closes = [
        10.0, 10.1, 10.2, 10.4, 10.6, 10.8, 10.9, 11.0, 11.1, 11.0,
        10.9, 11.0, 11.1, 11.2, 11.0, 10.9, 10.8, 11.0, 11.1, 9.8, 9.1,
    ]
    result = compute_risk_exit(
        as_of_date="2026-04-29",
        snapshots=[
            RiskExitSnapshot(
                stock_code="000001.SZ",
                stock_name="Alpha",
                entry_cost=10.5,
                bars_since_entry=6,
                close_history=closes,
                volume_history=_quiet_volume_history(),
            )
        ],
    )

    payload = cast(dict[str, Any], result.payload)
    assert payload["signal_count"] == 0
    assert payload["items"] == []
    watch_items = cast(list[dict[str, Any]], payload["watch_items"])
    assert len(watch_items) == 1
    watch_item = watch_items[0]
    assert watch_item["price_below_ema"] is True
    assert watch_item["volume_confirmed"] is False
    assert watch_item["triggered"] is False


def test_compute_risk_exit_keeps_position_when_only_latest_close_breaks_ema10() -> None:
    closes = [
        10.0, 10.1, 10.2, 10.4, 10.6, 10.8, 10.9, 11.0, 11.1, 11.0,
        10.9, 11.0, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 9.4,
    ]
    result = compute_risk_exit(
        as_of_date="2026-04-29",
        snapshots=[
            RiskExitSnapshot(
                stock_code="000001.SZ",
                stock_name="Alpha",
                entry_cost=10.5,
                bars_since_entry=6,
                close_history=closes,
                volume_history=_high_volume_history(surge_ratio=2.0),
            )
        ],
    )

    assert result.payload["signal_count"] == 0
    assert result.payload["excluded_position_count"] == 0
    assert result.payload["items"] == []
    watch_items = cast(list[dict[str, Any]], result.payload["watch_items"])
    assert len(watch_items) == 1
    assert watch_items[0]["stock_code"] == "000001.SZ"
    assert watch_items[0]["triggered"] is False
    assert watch_items[0]["price_below_ema"] is False


def test_compute_risk_exit_excludes_positions_without_required_inputs() -> None:
    result = compute_risk_exit(
        as_of_date="2026-04-29",
        snapshots=[
            RiskExitSnapshot(
                stock_code="000001.SZ",
                stock_name="Alpha",
                entry_cost=None,
                bars_since_entry=6,
                close_history=[10.0] * 21,
                volume_history=_quiet_volume_history(),
            ),
            RiskExitSnapshot(
                stock_code="000002.SZ",
                stock_name="Beta",
                entry_cost=8.2,
                bars_since_entry=None,
                close_history=[10.0] * 21,
                volume_history=_quiet_volume_history(),
            ),
            RiskExitSnapshot(
                stock_code="000003.SZ",
                stock_name="Gamma",
                entry_cost=9.1,
                bars_since_entry=2,
                close_history=[10.0, 9.9, 9.8],
                volume_history=[1_000_000.0, 1_100_000.0, 1_200_000.0],
            ),
            RiskExitSnapshot(
                stock_code="000004.SZ",
                stock_name="Delta",
                entry_cost=9.1,
                bars_since_entry=2,
                close_history=[10.0] * 21,
                volume_history=[],
            ),
        ],
    )

    assert result.payload["position_count"] == 4
    assert result.payload["signal_count"] == 0
    assert result.payload["excluded_position_count"] == 4
    assert result.payload["insufficient_history_count"] == 2
    assert result.payload["watch_items"] == []
