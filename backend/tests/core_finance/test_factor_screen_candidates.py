from __future__ import annotations

from typing import Any, cast

from backend.app.core_finance.factor_screen_candidates import (
    ACTIVE_MARKET_STATES,
    FORMULA_VERSION,
    MAX_CANDIDATES,
    compute_factor_screen_candidates,
)


def _sample_row(i: int) -> dict[str, object]:
    return {
        "stock_code": f"{100000 + i:06d}.SH",
        "stock_name": f"Co{i}",
        "pe": 10.0 + i * 0.7,
        "pb": 1.2 + i * 0.05,
        "ps": 0.8 + i * 0.03,
        "roe": 0.06 + (i % 7) * 0.005,
        "gross_margin": 0.2 + (i % 4) * 0.02,
        "three_month_return": -0.01 + i * 0.0003,
        "twelve_month_return": 0.02 + i * 0.0005,
        "volatility": 0.22 + (i % 5) * 0.01,
        "dividend_yield": 0.015 + (i % 3) * 0.003,
        "industry": "电力设备",
        "sector_code": "801730",
        "sector_name": "电力设备",
    }


def test_valid_rows_produce_candidates() -> None:
    rows = [_sample_row(i) for i in range(25)]
    result = compute_factor_screen_candidates(
        as_of_date="2026-04-30",
        market_state="WARM",
        rows=rows,
    )
    payload = cast(dict[str, Any], result.payload)
    assert FORMULA_VERSION in str(payload["formula_version"])
    assert payload["candidate_count"] >= 1
    assert payload["input_stock_count"] == 25


def test_empty_rows_returns_empty() -> None:
    result = compute_factor_screen_candidates(
        as_of_date="2026-04-30",
        market_state="OFF",
        rows=[],
    )
    payload = cast(dict[str, Any], result.payload)
    assert payload["candidate_count"] == 0
    assert payload["items"] == []
    assert "无数据" in str(payload["coverage_note"])


def test_missing_required_field_returns_empty() -> None:
    rows = [{k: v for k, v in _sample_row(i).items() if k != "pb"} for i in range(5)]
    result = compute_factor_screen_candidates(
        as_of_date="2026-04-30",
        market_state="OFF",
        rows=rows,
    )
    payload = cast(dict[str, Any], result.payload)
    assert payload["candidate_count"] == 0
    assert "缺少字段" in str(payload["coverage_note"])
    assert "pb" in str(payload["coverage_note"])


def test_sorted_by_score_descending() -> None:
    rows = [_sample_row(i) for i in range(30)]
    result = compute_factor_screen_candidates(
        as_of_date="2026-04-30",
        market_state="HOT",
        rows=rows,
    )
    items = cast(list[dict[str, Any]], cast(dict[str, Any], result.payload)["items"])
    scores = [float(item["score"]) for item in items]
    assert scores == sorted(scores, reverse=True)


def test_max_30_candidates() -> None:
    rows = [_sample_row(i) for i in range(350)]
    result = compute_factor_screen_candidates(
        as_of_date="2026-04-30",
        market_state="OFF",
        rows=rows,
    )
    items = cast(list[dict[str, Any]], cast(dict[str, Any], result.payload)["items"])
    assert len(items) == MAX_CANDIDATES


def test_coverage_note_present() -> None:
    rows = [_sample_row(i) for i in range(8)]
    result = compute_factor_screen_candidates(
        as_of_date="2026-04-30",
        market_state="WARM",
        rows=rows,
    )
    note = str(cast(dict[str, Any], result.payload)["coverage_note"])
    assert "5201" in note
    assert "覆盖" in note


def test_runs_in_all_market_states() -> None:
    rows = [_sample_row(i) for i in range(15)]
    payloads = []
    for state in ACTIVE_MARKET_STATES:
        r = compute_factor_screen_candidates(
            as_of_date="2026-04-30",
            market_state=state,
            rows=rows,
        )
        payloads.append(cast(dict[str, Any], r.payload))
    counts = {p["candidate_count"] for p in payloads}
    assert len(counts) == 1
    gates = {str(p["market_state"]) for p in payloads}
    assert gates == ACTIVE_MARKET_STATES
