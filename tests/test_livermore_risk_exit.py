from __future__ import annotations

from typing import Any, cast

from backend.app.core_finance.livermore_risk_exit import (
    FORMULA_VERSION,
    RiskExitSnapshot,
    compute_risk_exit,
)


def test_compute_risk_exit_flags_two_consecutive_closes_below_ema10() -> None:
    result = compute_risk_exit(
        as_of_date="2026-04-29",
        snapshots=[
            RiskExitSnapshot(
                stock_code="000001.SZ",
                stock_name="Alpha",
                entry_cost=10.5,
                bars_since_entry=6,
                close_history=[10.0, 10.1, 10.2, 10.4, 10.6, 10.8, 10.9, 11.0, 11.1, 11.0, 9.8, 9.1],
            )
        ],
    )

    payload = cast(dict[str, Any], result.payload)
    assert payload["formula_version"] == FORMULA_VERSION
    assert payload["signal_count"] == 1
    items = cast(list[dict[str, Any]], payload["items"])
    item = items[0]
    assert item["stock_code"] == "000001.SZ"
    assert item["reason"] == "2d_below_ema10"
    assert item["bars_since_entry"] == 6
    assert item["latest_close"] == 9.1
    assert item["latest_ema10"] > item["latest_close"]
    assert item["prior_ema10"] > item["prior_close"]
    watch_items = cast(list[dict[str, Any]], payload["watch_items"])
    assert len(watch_items) == 1
    watch_item = watch_items[0]
    assert watch_item["stock_code"] == "000001.SZ"
    assert watch_item["triggered"] is True
    assert watch_item["exit_watch_price"] == watch_item["latest_ema10"]


def test_compute_risk_exit_keeps_position_when_only_latest_close_breaks_ema10() -> None:
    result = compute_risk_exit(
        as_of_date="2026-04-29",
        snapshots=[
            RiskExitSnapshot(
                stock_code="000001.SZ",
                stock_name="Alpha",
                entry_cost=10.5,
                bars_since_entry=6,
                close_history=[10.0, 10.1, 10.2, 10.4, 10.6, 10.8, 10.9, 11.0, 11.1, 11.0, 10.8, 9.4],
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


def test_compute_risk_exit_excludes_positions_without_required_inputs() -> None:
    result = compute_risk_exit(
        as_of_date="2026-04-29",
        snapshots=[
            RiskExitSnapshot(
                stock_code="000001.SZ",
                stock_name="Alpha",
                entry_cost=None,
                bars_since_entry=6,
                close_history=[10.0] * 12,
            ),
            RiskExitSnapshot(
                stock_code="000002.SZ",
                stock_name="Beta",
                entry_cost=8.2,
                bars_since_entry=None,
                close_history=[10.0] * 12,
            ),
            RiskExitSnapshot(
                stock_code="000003.SZ",
                stock_name="Gamma",
                entry_cost=9.1,
                bars_since_entry=2,
                close_history=[10.0, 9.9, 9.8],
            ),
        ],
    )

    assert result.payload["position_count"] == 3
    assert result.payload["signal_count"] == 0
    assert result.payload["excluded_position_count"] == 3
    assert result.payload["insufficient_history_count"] == 1
    assert result.payload["watch_items"] == []
