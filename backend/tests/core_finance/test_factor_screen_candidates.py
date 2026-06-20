from __future__ import annotations

from typing import Any, cast

from backend.app.core_finance.factor_screen_candidates import (
    ACTIVE_MARKET_STATES,
    FORMULA_VERSION,
    MAX_CANDIDATES,
    compute_factor_screen_candidates,
)


def _sample_row(i: int) -> dict[str, object]:
    sector = f"行业{i % 40:02d}"
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
        "industry": sector,
        "sector_code": "801730",
        "sector_name": sector,
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


def test_factor_screen_limits_industry_concentration() -> None:
    rows = []
    for i in range(40):
        row = _sample_row(i)
        row.update(
            {
                "stock_code": f"{600000 + i:06d}.SH",
                "stock_name": f"Construction{i}",
                "pe": 4.0 + i * 0.02,
                "pb": 0.3 + i * 0.005,
                "ps": 0.01 + i * 0.001,
                "industry": "建筑装饰",
                "sector_name": "建筑装饰",
            }
        )
        rows.append(row)
    for i, sector in enumerate(["通信", "医药生物", "食品饮料", "电子", "机械设备"]):
        row = _sample_row(100 + i)
        row.update(
            {
                "stock_code": f"{300000 + i:06d}.SZ",
                "stock_name": f"WeakBalanced{i}",
                "pe": 55.0 + i,
                "pb": 4.8 + i * 0.1,
                "ps": 7.0 + i * 0.1,
                "roe": 0.04,
                "gross_margin": 0.08,
                "three_month_return": -0.18,
                "twelve_month_return": -0.28,
                "volatility": 0.55,
                "dividend_yield": 0.005,
                "industry": sector,
                "sector_name": sector,
            }
        )
        rows.append(row)

    result = compute_factor_screen_candidates(
        as_of_date="2026-04-30",
        market_state="WARM",
        rows=rows,
    )

    items = cast(list[dict[str, Any]], cast(dict[str, Any], result.payload)["items"])
    counts: dict[str, int] = {}
    for item in items:
        industry = str(item["industry"])
        counts[industry] = counts.get(industry, 0) + 1
    assert counts["建筑装饰"] <= 3


def test_factor_screen_excludes_st_and_extreme_financial_rows() -> None:
    rows = [
        {
            **_sample_row(1),
            "stock_code": "600001.SH",
            "stock_name": "Normal A",
            "industry": "电子",
            "sector_name": "电子",
            "roe": 0.18,
            "dividend_yield": 0.035,
        },
        {
            **_sample_row(2),
            "stock_code": "600002.SH",
            "stock_name": "ST Risk",
            "industry": "电子",
            "sector_name": "电子",
            "roe": 0.20,
            "dividend_yield": 0.03,
        },
        {
            **_sample_row(3),
            "stock_code": "600003.SH",
            "stock_name": "Extreme ROE",
            "industry": "汽车",
            "sector_name": "汽车",
            "roe": 0.99,
            "dividend_yield": 0.03,
        },
        {
            **_sample_row(4),
            "stock_code": "600004.SH",
            "stock_name": "Extreme Dividend",
            "industry": "通信",
            "sector_name": "通信",
            "roe": 0.18,
            "dividend_yield": 0.80,
        },
        {
            **_sample_row(5),
            "stock_code": "600005.SH",
            "stock_name": "Normal B",
            "industry": "通信",
            "sector_name": "通信",
            "roe": 0.16,
            "dividend_yield": 0.025,
        },
    ]
    rows.extend(
        {
            **_sample_row(100 + i),
            "stock_code": f"610{i:03d}.SH",
            "stock_name": f"Weak{i}",
            "industry": f"行业X{i:02d}",
            "sector_name": f"行业X{i:02d}",
            "pe": 80.0,
            "pb": 5.0,
            "ps": 8.0,
            "roe": 0.02,
            "gross_margin": 0.08,
            "three_month_return": -0.20,
            "twelve_month_return": -0.30,
            "volatility": 0.50,
            "dividend_yield": 0.005,
        }
        for i in range(30)
    )

    result = compute_factor_screen_candidates(
        as_of_date="2026-04-30",
        market_state="WARM",
        rows=rows,
    )

    codes = {
        str(item["stock_code"])
        for item in cast(list[dict[str, Any]], cast(dict[str, Any], result.payload)["items"])
    }
    assert "600002.SH" not in codes
    assert "600003.SH" not in codes
    assert "600004.SH" not in codes


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
