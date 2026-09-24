from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any, cast

import pytest
from backend.app.core_finance import mean_reversion_candidates as mean_module
from backend.app.core_finance.breakout_geometry import (
    PATTERN_PULLBACK_LABEL,
    attach_breakout_geometry,
)
from backend.app.core_finance.mean_reversion_candidates import (
    FORMULA_VERSION,
    MeanReversionSnapshot,
    compute_mean_reversion_candidates,
)


def test_mean_reversion_float_series_reuses_finite_float_history() -> None:
    history = [10.0, 10.5, 11.0]

    assert mean_module._float_series(history) is history
    assert mean_module._float_series([1, "2.5"]) == [1.0, 2.5]
    assert mean_module._float_series([10.0, float("nan")]) is None


def _float_hist(base: float, tail: list[float]) -> list[float]:
    length = len(tail)
    pad = MIN_LEN - length
    return [base] * pad + tail


MIN_LEN = 70


def _base_valid_snapshot(market_hot: bool = False) -> MeanReversionSnapshot:
    """合成满足全部门控的 70 根收盘价 + 成交量序列。"""
    plateau = [100.0] * 44
    glide = [max(72.0, 100.0 - i * 0.35) for i in range(14)]
    rebound = [76.0 + 0.55 * i + (0.08 * i) ** 1.05 for i in range(12)]
    closes = plateau + glide + rebound
    assert len(closes) == MIN_LEN
    closes[-15] = 100.0
    closes[-14] = 99.2
    closes[-11] = 100.0
    closes[-10] = 88.1
    closes[-1] = 84.52
    closes[-2] = 80.5
    closes[-3] = 79.1
    closes[-4] = 78.05
    closes[-5] = 77.05
    closes[-6] = 76.05
    closes[-7] = 75.05
    closes[-8] = 74.05
    closes[-9] = 73.05
    closes[-10] = 72.05
    close_price = closes[-1]
    low_today = 70.4
    high_today = 93.80
    vols = [1_480_000.0] * (MIN_LEN - 1) + [1_480_000.0 * 2.05]
    return MeanReversionSnapshot(
        stock_code="000099.SZ" if market_hot else "000001.SZ",
        stock_name="ValidCo",
        sector_code="801001",
        sector_name="SectorA",
        close_value=closes[-1],
        low_value=low_today,
        high_value=high_today,
        volume=vols[-1],
        close_history=closes,
        volume_history=vols,
    )


def test_valid_candidate_is_included() -> None:
    result = compute_mean_reversion_candidates(
        as_of_date="2026-05-09",
        market_state="WARM",
        snapshots=[_base_valid_snapshot()],
    )
    payload = cast(dict[str, Any], result.payload)
    assert payload["candidate_count"] == 1
    items = cast(list[dict[str, Any]], payload["items"])
    assert items[0]["stock_code"] == "000001.SZ"
    assert items[0]["rank"] == 1
    assert FORMULA_VERSION in str(payload["formula_version"])


def test_insufficient_history_excluded() -> None:
    short_close = ([100.0] * 50) + [90.0] * 9
    short_vol = ([1.0] * len(short_close))
    snap = MeanReversionSnapshot(
        stock_code="000002.SZ",
        stock_name="Short",
        sector_code="801002",
        sector_name="S2",
        close_value=short_close[-1],
        low_value=88.0,
        high_value=92.0,
        volume=2.5,
        close_history=short_close,
        volume_history=short_vol,
    )
    result = compute_mean_reversion_candidates(
        as_of_date="2026-05-09",
        market_state="WARM",
        snapshots=[snap],
    )
    payload = cast(dict[str, Any], result.payload)
    assert payload["candidate_count"] == 0
    assert payload["insufficient_history_count"] == 1
    assert payload["excluded_stock_count"] >= 1


def test_no_drawdown_excluded() -> None:
    snap = _base_valid_snapshot()
    closes = cast(list[float], list(map(float, snap.close_history)))  # type: ignore[arg-type]
    for i in range(-25, -1):
        closes[i] = min(closes[i], 99.0)
    closes[-1] = 99.98
    bad = MeanReversionSnapshot(
        stock_code=snap.stock_code,
        stock_name=snap.stock_name,
        sector_code=snap.sector_code,
        sector_name=snap.sector_name,
        close_value=closes[-1],
        low_value=99.70,
        high_value=99.92,
        volume=snap.volume,
        close_history=closes,
        volume_history=list(snap.volume_history),
    )
    payload = compute_mean_reversion_candidates(
        as_of_date="2026-05-09",
        market_state="WARM",
        snapshots=[bad],
    ).payload
    assert cast(dict[str, Any], payload)["candidate_count"] == 0


def test_no_stabilization_excluded() -> None:
    snap = _base_valid_snapshot()
    closes = cast(list[float], list(map(float, snap.close_history)))
    closes[-1] = 70.0
    closes[-2] = 85.95
    bad = MeanReversionSnapshot(
        stock_code=snap.stock_code,
        stock_name=snap.stock_name,
        sector_code=snap.sector_code,
        sector_name=snap.sector_name,
        close_value=closes[-1],
        low_value=69.0,
        high_value=86.0,
        volume=snap.volume,
        close_history=closes,
        volume_history=list(snap.volume_history),
    )
    payload = compute_mean_reversion_candidates(
        as_of_date="2026-05-09",
        market_state="WARM",
        snapshots=[bad],
    ).payload
    assert cast(dict[str, Any], payload)["candidate_count"] == 0


def test_low_volume_excluded() -> None:
    snap = _base_valid_snapshot()
    volumes = cast(list[float], list(map(float, snap.volume_history)))
    for i in range(-21, -1):
        volumes[i] = volumes[-3]
    volumes[-1] = volumes[-21] * 1.08
    bad = MeanReversionSnapshot(
        stock_code=snap.stock_code,
        stock_name=snap.stock_name,
        sector_code=snap.sector_code,
        sector_name=snap.sector_name,
        close_value=snap.close_value,
        low_value=snap.low_value,
        high_value=snap.high_value,
        volume=volumes[-1],
        close_history=list(snap.close_history),
        volume_history=volumes,
    )
    payload = compute_mean_reversion_candidates(
        as_of_date="2026-05-09",
        market_state="WARM",
        snapshots=[bad],
    ).payload
    assert cast(dict[str, Any], payload)["candidate_count"] == 0


def test_hot_market_returns_empty() -> None:
    result = compute_mean_reversion_candidates(
        as_of_date="2026-05-09",
        market_state="HOT",
        snapshots=[_base_valid_snapshot()],
    )
    payload = cast(dict[str, Any], result.payload)
    assert payload["items"] == []
    assert payload["candidate_count"] == 0
    assert payload["excluded_stock_count"] >= 1


def test_off_market_returns_empty() -> None:
    """OFF 状态下样本胜率 36% / -1.16%，不再放行。"""
    result = compute_mean_reversion_candidates(
        as_of_date="2026-05-09",
        market_state="OFF",
        snapshots=[_base_valid_snapshot()],
    )
    payload = cast(dict[str, Any], result.payload)
    assert payload["items"] == []
    assert payload["candidate_count"] == 0
    assert payload["excluded_stock_count"] >= 1



def test_sorted_by_score_descending() -> None:
    base = _base_valid_snapshot()
    quiet_volumes = list(map(float, base.volume_history))
    loud_volumes = list(quiet_volumes)
    loud_volumes[-1] = quiet_volumes[-1] * 1.95

    quiet = MeanReversionSnapshot(
        stock_code="000010.SZ",
        stock_name="QuietVol",
        sector_code=base.sector_code,
        sector_name=base.sector_name,
        close_value=base.close_value,
        low_value=base.low_value,
        high_value=base.high_value,
        volume=quiet_volumes[-1],
        close_history=list(base.close_history),
        volume_history=quiet_volumes,
    )
    loud = MeanReversionSnapshot(
        stock_code="000020.SZ",
        stock_name="LoudVol",
        sector_code=base.sector_code,
        sector_name=base.sector_name,
        close_value=base.close_value,
        low_value=base.low_value,
        high_value=base.high_value,
        volume=loud_volumes[-1],
        close_history=list(base.close_history),
        volume_history=loud_volumes,
    )

    result = compute_mean_reversion_candidates(
        as_of_date="2026-05-09",
        market_state="WARM",
        snapshots=[quiet, loud],
    )
    items = cast(list[dict[str, Any]], cast(dict[str, Any], result.payload)["items"])
    assert len(items) == 2
    assert items[0]["stock_code"] == "000020.SZ"
    assert cast(float, items[0]["score"]) > cast(float, items[1]["score"]) + 1e-9


def test_max_20_candidates() -> None:
    snaps = [_base_valid_snapshot() for _ in range(25)]
    for index, snapshot in enumerate(snaps):
        code = f"{600000 + index:06d}"
        patched = MeanReversionSnapshot(
            stock_code=f"{code}.SZ",
            stock_name=snapshot.stock_name,
            sector_code=snapshot.sector_code,
            sector_name=snapshot.sector_name,
            close_value=snapshot.close_value,
            low_value=snapshot.low_value,
            high_value=snapshot.high_value,
            volume=snapshot.volume + float(index),
            close_history=list(snapshot.close_history),
            volume_history=list(snapshot.volume_history),
        )
        snaps[index] = patched
    payload = compute_mean_reversion_candidates(
        as_of_date="2026-05-09",
        market_state="WARM",
        snapshots=snaps,
    ).payload
    p = cast(dict[str, Any], payload)
    assert len(cast(list[Any], p["items"])) <= 20


def test_mean_reversion_length_mismatch_is_not_counted_as_insufficient_history() -> None:
    snapshot = _base_valid_snapshot()
    result = compute_mean_reversion_candidates(
        as_of_date="2026-05-09",
        market_state="WARM",
        snapshots=[replace(snapshot, volume_history=[*snapshot.volume_history, 1.0])],
    )

    assert result.payload["candidate_count"] == 0
    assert result.payload["excluded_stock_count"] == 1
    assert result.payload["insufficient_history_count"] == 0


def test_mean_reversion_normalizes_history_once_for_late_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_float_series = mean_module._float_series
    call_count = 0

    def counted_float_series(values: Sequence[object]) -> list[float] | None:
        nonlocal call_count
        call_count += 1
        return original_float_series(values)

    monkeypatch.setattr(mean_module, "_float_series", counted_float_series)
    snapshot = replace(
        _base_valid_snapshot(),
        close_value=100.0,
        low_value=99.0,
        high_value=101.0,
        close_history=[100.0] * MIN_LEN,
    )
    result = compute_mean_reversion_candidates(
        as_of_date="2026-05-09",
        market_state="WARM",
        snapshots=[snapshot],
    )

    assert result.payload["candidate_count"] == 0
    assert result.payload["excluded_stock_count"] == 1
    assert result.payload["insufficient_history_count"] == 0
    assert call_count == 2


# ---- 观察位几何（attach_breakout_geometry）golden 样本 -----------------------


def _computed_reversion_payload() -> dict[str, Any]:
    """跑真实 compute 生成 2 只超跌候选（同一序列，close 均为 84.52）。"""
    first = _base_valid_snapshot()
    second = replace(first, stock_code="000002.SZ")
    return cast(
        dict[str, Any],
        compute_mean_reversion_candidates(
            as_of_date="2026-05-09",
            market_state="WARM",
            snapshots=[first, second],
        ).payload,
    )


def test_mean_reversion_breakout_geometry_golden_keeps_own_close_and_fills_missing() -> None:
    """golden：超跌候选自带策略日 close(84.52)不被覆盖，几何只补
    breakout_level/distance/pattern(回踩档)；缺 K 线候选三字段保持 None(而非 0)
    且 close 仍保留自身值；原 payload 不被回写。"""
    payload = _computed_reversion_payload()
    assert payload["candidate_count"] == 2

    attached = attach_breakout_geometry(
        payload,
        close_history_by_code={"000001.SZ": [100.0] * 55 + [84.52]},
        price_as_of_date="2026-05-09",
        last_trade_date_by_code={"000001.SZ": "2026-05-09"},
    )
    by_code = {
        str(item["stock_code"]): item
        for item in cast(list[dict[str, Any]], attached["items"])
    }

    geometry_item = by_code["000001.SZ"]
    assert geometry_item["close"] == 84.52
    assert geometry_item["breakout_level"] == 100.0
    assert geometry_item["distance_to_breakout_pct"] == -15.48
    assert geometry_item["pattern"] == PATTERN_PULLBACK_LABEL
    assert "price_as_of_date" not in geometry_item
    assert "price_stale" not in geometry_item

    missing_item = by_code["000002.SZ"]
    assert missing_item["close"] == 84.52
    assert missing_item["breakout_level"] is None
    assert missing_item["distance_to_breakout_pct"] is None
    assert missing_item["pattern"] is None

    original_by_code = {
        str(item["stock_code"]): item
        for item in cast(list[dict[str, Any]], payload["items"])
    }
    for stock_code, item in by_code.items():
        assert item["score"] == original_by_code[stock_code]["score"]
        assert item["drawdown_20d"] == original_by_code[stock_code]["drawdown_20d"]
    for original_item in cast(list[dict[str, Any]], payload["items"]):
        assert "pattern" not in original_item
        assert "breakout_level" not in original_item
    assert "breakout_geometry" not in payload
    assert cast(dict[str, Any], attached["breakout_geometry"])["price_as_of_date"] == "2026-05-09"


def test_mean_reversion_breakout_geometry_golden_fails_closed_on_close_conflict() -> None:
    """golden：几何 close 与候选自带 close 不等(同股同日不同价)时该行几何
    fail-closed 保持 None，close 保留原值，不加停牌披露字段。"""
    payload = _computed_reversion_payload()

    attached = attach_breakout_geometry(
        payload,
        close_history_by_code={"000001.SZ": [100.0] * 55 + [84.00]},
        price_as_of_date="2026-05-09",
    )
    item = {
        str(row["stock_code"]): row
        for row in cast(list[dict[str, Any]], attached["items"])
    }["000001.SZ"]

    assert item["close"] == 84.52
    assert item["breakout_level"] is None
    assert item["distance_to_breakout_pct"] is None
    assert item["pattern"] is None
    assert "price_as_of_date" not in item
    assert "price_stale" not in item
