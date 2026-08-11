from __future__ import annotations

import inspect
import json
import math
from typing import Any, cast

from backend.app.core_finance import factor_screen_candidates as factor_module
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


def test_factor_screen_selection_is_local_to_module() -> None:
    source = inspect.getsource(factor_module)
    assert "macro.equity_strategies" not in source
    assert "def _multi_factor_selection" in source


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


def test_factor_screen_excludes_non_positive_valuation_rows() -> None:
    """负/零 pe/pb/ps（亏损股或异常数据）不得因"低者优"排名获得最高估值分进入候选。"""
    rows = [_sample_row(i) for i in range(30)]
    loss_maker = {
        **_sample_row(200),
        "stock_code": "688001.SH",
        "stock_name": "LossMaker",
        "industry": "半导体",
        "sector_name": "半导体",
        # 负 PE 若不过滤，会在低者优排名中排到最优档
        "pe": -3.5,
        "pb": 0.9,
        "ps": 0.5,
        "roe": 0.25,
        "gross_margin": 0.45,
        "three_month_return": 0.30,
        "twelve_month_return": 0.60,
        "volatility": 0.10,
        "dividend_yield": 0.05,
    }
    zero_pe = {
        **loss_maker,
        "stock_code": "688002.SH",
        "stock_name": "ZeroPe",
        "pe": 0.0,
    }
    negative_pb = {
        **loss_maker,
        "stock_code": "688003.SH",
        "stock_name": "NegativePb",
        "pe": 8.0,
        "pb": -1.2,
    }
    negative_ps = {
        **loss_maker,
        "stock_code": "688004.SH",
        "stock_name": "NegativePs",
        "pe": 8.0,
        "ps": -0.4,
    }
    all_rows = [*rows, loss_maker, zero_pe, negative_pb, negative_ps]

    result = compute_factor_screen_candidates(
        as_of_date="2026-04-30",
        market_state="WARM",
        rows=all_rows,
    )

    payload = cast(dict[str, Any], result.payload)
    codes = {str(item["stock_code"]) for item in cast(list[dict[str, Any]], payload["items"])}
    assert "688001.SH" not in codes
    assert "688002.SH" not in codes
    assert "688003.SH" not in codes
    assert "688004.SH" not in codes
    # 非正估值行也不得计入评分池规模
    assert payload["input_stock_count"] == 30


def test_coverage_note_present() -> None:
    rows = [_sample_row(i) for i in range(8)]
    result = compute_factor_screen_candidates(
        as_of_date="2026-04-30",
        market_state="WARM",
        rows=rows,
    )
    payload = cast(dict[str, Any], result.payload)
    note = str(payload["coverage_note"])
    assert payload["input_stock_count"] == 8
    assert note == (
        "本次多因子评分池为 8 只（必填字段完整且通过当前筛选条件），"
        "仅在该评分池内生成观察候选"
    )
    assert "5201" not in note
    assert "/" not in note
    assert "%" not in note
    assert "％" not in note


def test_infinite_pe_pb_ps_excluded_and_payload_json_safe() -> None:
    """+inf pe/pb/ps 不得因"low is good"排名穿透正值过滤混入候选，且输出须可 JSON 序列化。"""
    rows = [_sample_row(i) for i in range(30)]
    inf_pe_row = {
        **_sample_row(200),
        "stock_code": "900001.SH",
        "stock_name": "InfPe",
        "industry": "半导体",
        "sector_name": "半导体",
        "pe": float("inf"),
        "roe": 0.30,
        "gross_margin": 0.50,
        "three_month_return": 0.40,
        "twelve_month_return": 0.70,
        "dividend_yield": 0.01,
    }
    inf_pb_row = {**inf_pe_row, "stock_code": "900002.SH", "stock_name": "InfPb", "pe": 8.0, "pb": float("inf")}
    inf_ps_row = {**inf_pe_row, "stock_code": "900003.SH", "stock_name": "InfPs", "pe": 8.0, "ps": float("-inf")}

    result = compute_factor_screen_candidates(
        as_of_date="2026-04-30",
        market_state="WARM",
        rows=[*rows, inf_pe_row, inf_pb_row, inf_ps_row],
    )
    payload = cast(dict[str, Any], result.payload)
    codes = {str(item["stock_code"]) for item in cast(list[dict[str, Any]], payload["items"])}

    assert "900001.SH" not in codes
    assert "900002.SH" not in codes
    assert "900003.SH" not in codes
    # JSON 输出不得包含 Infinity/NaN 非法 token（json.dumps 默认 allow_nan=True 会写出字面量，
    # 必须先确认 payload 里不存在非有限 float，再走 dumps 才算真正验证）。
    serialized = json.dumps(payload, allow_nan=False)
    assert "Infinity" not in serialized
    assert "NaN" not in serialized


def test_non_pe_pb_ps_infinite_factor_not_leaked_to_output() -> None:
    """roe/dividend_yield 等其余因子出现 inf 时：_rank_score 已把该分项判 0 分，行仍可能保留，
    但展示字段不得把 inf 泄漏到候选输出（JSON 必须可序列化）。"""
    rows = [_sample_row(i) for i in range(10)]
    inf_dividend_row = {
        **_sample_row(300),
        "stock_code": "900010.SH",
        "stock_name": "InfDividend",
        "industry": "银行",
        "sector_name": "银行",
        "dividend_yield": float("inf"),
    }
    result = compute_factor_screen_candidates(
        as_of_date="2026-04-30",
        market_state="WARM",
        rows=[*rows, inf_dividend_row],
    )
    payload = cast(dict[str, Any], result.payload)
    for item in cast(list[dict[str, Any]], payload["items"]):
        for key in ("pe", "pb", "roe", "gross_margin", "three_month_return", "twelve_month_return", "dividend_yield"):
            value = item[key]
            assert value is None or math.isfinite(float(value))
    serialized = json.dumps(payload, allow_nan=False)
    assert "Infinity" not in serialized


def test_all_rows_filtered_out_reports_empty_pool_with_zero_input_count() -> None:
    """全部行必填字段完整但均未通过筛选(如全部 ST)：input_stock_count 须为 0（进入评分池的行数），
    而非过滤前的原始行数；coverage_note 须反映"未通过筛选"而非"数据全部为空"。"""
    rows = []
    for i in range(5):
        row = _sample_row(i)
        row["stock_name"] = f"*ST Risk{i}"
        rows.append(row)

    result = compute_factor_screen_candidates(
        as_of_date="2026-04-30",
        market_state="WARM",
        rows=rows,
    )
    payload = cast(dict[str, Any], result.payload)

    assert payload["input_stock_count"] == 0
    assert payload["candidate_count"] == 0
    assert payload["items"] == []
    assert payload["filtered_out_count"] == 5
    assert "未通过筛选" in str(payload["coverage_note"])
    assert "全部为空" not in str(payload["coverage_note"])


def test_all_rows_missing_required_values_reports_empty_pool_distinct_note() -> None:
    """必填字段列存在但取值全部缺失(NaN)：coverage_note 应区别于"未通过筛选"，
    明确指向字段缺失这一根因。"""
    rows = [_sample_row(i) for i in range(5)]
    for row in rows:
        row["pe"] = None

    result = compute_factor_screen_candidates(
        as_of_date="2026-04-30",
        market_state="WARM",
        rows=rows,
    )
    payload = cast(dict[str, Any], result.payload)

    assert payload["input_stock_count"] == 0
    assert payload["candidate_count"] == 0
    assert payload["filtered_out_count"] == 5
    assert "缺失" in str(payload["coverage_note"])
    assert "未通过筛选" not in str(payload["coverage_note"])


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
