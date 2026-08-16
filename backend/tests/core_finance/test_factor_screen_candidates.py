from __future__ import annotations

import inspect
import json
import math
from typing import Any, cast

import pandas as pd
from backend.app.core_finance import factor_screen_candidates as factor_module
from backend.app.core_finance.factor_screen_candidates import (
    ACTIVE_MARKET_STATES,
    BREAKOUT_GEOMETRY_MIN_HISTORY,
    FORMULA_VERSION,
    MAX_CANDIDATES,
    MIN_AVG_AMOUNT_20D,
    PATTERN_BREAKOUT_LABEL,
    PATTERN_CONSOLIDATION_LABEL,
    PATTERN_PULLBACK_LABEL,
    _filter_factor_screen_universe,
    attach_factor_screen_breakout_geometry,
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
        # v3 流动性地板输入(元)：i=0 恰为 2e8 地板值,覆盖 >= 边界。
        "avg_amount_20d": 2.0e8 + i * 1.0e7,
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
        market_state="WARM",
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
        market_state="WARM",
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
        market_state="WARM",
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
        "本次多因子评分池为 8 只（必填字段完整、通过基础筛选条件且近 20 日均成交额不低于 "
        "2.0 亿元），流动性过滤剔除 0 只，仅在该评分池内生成观察候选"
    )
    assert "5201" not in note
    assert "/" not in note
    assert "%" not in note
    assert "％" not in note
    # 成功型 note 不得包含服务层错误关键词,否则会被误判为降级原因。
    for keyword in ("无数据", "缺少", "缺失", "为空", "失败"):
        assert keyword not in note


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


def test_off_market_returns_inactive_empty_payload_golden_sample() -> None:
    rows = [_sample_row(i) for i in range(15)]

    payload = cast(
        dict[str, Any],
        compute_factor_screen_candidates(
            as_of_date="2026-04-30",
            market_state="OFF",
            rows=rows,
        ).payload,
    )

    assert payload == {
        "as_of_date": "2026-04-30",
        "formula_version": "rv_factor_screen_candidates_v4",
        "market_state": "OFF",
        "input_stock_count": 15,
        "filtered_out_count": 15,
        "candidate_count": 0,
        "coverage_note": (
            "Factor screen inactive for market_state OFF; "
            "active states are WARM/HOT/OVERHEAT."
        ),
        "liquidity_filter": None,
        "items": [],
    }
    for keyword in ("无数据", "缺少", "缺失", "为空", "失败"):
        assert keyword not in str(payload["coverage_note"])


def test_non_active_data_states_return_inactive_empty_payloads() -> None:
    rows = [_sample_row(i) for i in range(5)]

    for market_state in ("NO_DATA", "STALE", "PENDING_DATA"):
        payload = cast(
            dict[str, Any],
            compute_factor_screen_candidates(
                as_of_date="2026-04-30",
                market_state=market_state,
                rows=rows,
            ).payload,
        )
        assert payload["market_state"] == market_state
        assert payload["candidate_count"] == 0
        assert payload["items"] == []
        assert f"inactive for market_state {market_state}" in str(payload["coverage_note"])


def test_overheat_market_remains_active_and_produces_candidates() -> None:
    payload = cast(
        dict[str, Any],
        compute_factor_screen_candidates(
            as_of_date="2026-04-30",
            market_state="OVERHEAT",
            rows=[_sample_row(i) for i in range(15)],
        ).payload,
    )

    assert payload["formula_version"] == "rv_factor_screen_candidates_v4"
    assert payload["market_state"] == "OVERHEAT"
    assert payload["candidate_count"] >= 1
    assert payload["items"]


def test_runs_in_all_active_market_states() -> None:
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


def test_liquidity_floor_golden_sample_boundaries() -> None:
    """黄金样本(蓝本 P0)：均额恰 2e8 通过(>= 边界)、低于剔除、缺失 fail-closed 剔除并计数。"""
    assert MIN_AVG_AMOUNT_20D == 200_000_000.0
    filler = [_sample_row(i) for i in range(1, 31)]  # 均额 2.1e8 起,全部通过
    at_floor = {
        **_sample_row(200),
        "stock_code": "600100.SH",
        "stock_name": "AtFloor",
        "industry": "银行",
        "sector_name": "银行",
        "avg_amount_20d": 200_000_000.0,
    }
    below_floor = {
        **_sample_row(201),
        "stock_code": "600101.SH",
        "stock_name": "BelowFloor",
        "industry": "银行",
        "sector_name": "银行",
        "avg_amount_20d": 199_999_999.0,
    }
    missing_amount = {
        **_sample_row(202),
        "stock_code": "600102.SH",
        "stock_name": "MissingAmount",
        "industry": "银行",
        "sector_name": "银行",
        "avg_amount_20d": None,
    }
    rows = [*filler, at_floor, below_floor, missing_amount]

    result = compute_factor_screen_candidates(
        as_of_date="2026-05-27",
        market_state="WARM",
        rows=rows,
    )
    payload = cast(dict[str, Any], result.payload)

    # 评分池 = 30 只 filler + 恰在地板上的 1 只;低于/缺失各 1 只被流动性过滤剔除。
    assert payload["input_stock_count"] == 31
    assert payload["filtered_out_count"] == 2
    liquidity = cast(dict[str, Any], payload["liquidity_filter"])
    assert liquidity["basis"] == "avg_amount_20d"
    assert liquidity["min_avg_amount_20d"] == 200_000_000.0
    assert liquidity["policy_source"] == "POLICY.entry_filters.min_daily_amount"
    assert liquidity["evaluated_count"] == 33
    assert liquidity["pass_count"] == 31
    assert liquidity["below_floor_count"] == 1
    assert liquidity["missing_amount_count"] == 1

    items = cast(list[dict[str, Any]], payload["items"])
    codes = {str(item["stock_code"]) for item in items}
    assert "600101.SH" not in codes
    assert "600102.SH" not in codes
    for item in items:
        assert float(item["avg_amount_20d"]) >= 200_000_000.0


def test_formula_version_v4_payload_and_items() -> None:
    """v4 版本断言 + 候选 payload 与逐 item 补记 formula_version(治理字段)。"""
    assert FORMULA_VERSION == "rv_factor_screen_candidates_v4"
    rows = [_sample_row(i) for i in range(20)]
    result = compute_factor_screen_candidates(
        as_of_date="2026-05-27",
        market_state="WARM",
        rows=rows,
    )
    payload = cast(dict[str, Any], result.payload)
    assert payload["formula_version"] == "rv_factor_screen_candidates_v4"
    items = cast(list[dict[str, Any]], payload["items"])
    assert items
    for item in items:
        assert item["formula_version"] == "rv_factor_screen_candidates_v4"
        assert float(item["avg_amount_20d"]) >= MIN_AVG_AMOUNT_20D


def test_liquidity_floor_empties_pool_reports_error_note() -> None:
    """全部候选均额低于地板：评分池为空须走错误型 coverage_note(含"为空",触发服务层降级)。"""
    rows = []
    for i in range(6):
        row = _sample_row(i)
        row["avg_amount_20d"] = 50_000_000.0
        rows.append(row)

    result = compute_factor_screen_candidates(
        as_of_date="2026-05-27",
        market_state="WARM",
        rows=rows,
    )
    payload = cast(dict[str, Any], result.payload)
    assert payload["input_stock_count"] == 0
    assert payload["candidate_count"] == 0
    assert payload["items"] == []
    assert "为空" in str(payload["coverage_note"])
    liquidity = cast(dict[str, Any], payload["liquidity_filter"])
    assert liquidity["evaluated_count"] == 6
    assert liquidity["pass_count"] == 0
    assert liquidity["below_floor_count"] == 6
    assert liquidity["missing_amount_count"] == 0


def test_filter_universe_without_amount_column_keeps_legacy_behavior() -> None:
    """equity_shadow_portfolio 复用路径兼容：默认参数(无流动性地板)下,
    不带 avg_amount_20d 列的宇宙不受 v3 过滤影响;显式传地板则 fail-closed 全剔除。"""
    frame = pd.DataFrame(
        [{k: v for k, v in _sample_row(i).items() if k != "avg_amount_20d"} for i in range(5)]
    ).set_index("stock_code")

    assert len(_filter_factor_screen_universe(frame)) == 5
    assert _filter_factor_screen_universe(frame, min_avg_amount_20d=MIN_AVG_AMOUNT_20D).empty


# ---- 观察位几何（attach_factor_screen_breakout_geometry）golden 样本 -----------


def _computed_factor_payload(row_count: int = 40) -> dict[str, Any]:
    """跑真实 compute 生成候选 payload；40 行 / 40 个行业 -> 候选恰为 4 只。"""
    rows = [_sample_row(i) for i in range(row_count)]
    return cast(
        dict[str, Any],
        compute_factor_screen_candidates(
            as_of_date="2026-05-27",
            market_state="WARM",
            rows=rows,
        ).payload,
    )


def _flat_history(prior_close: float, last_close: float) -> list[float]:
    """55 个先导收盘全为 prior_close + 1 个信号日收盘，长度恰为最小窗口 56。"""
    return [prior_close] * (BREAKOUT_GEOMETRY_MIN_HISTORY - 1) + [last_close]


def test_breakout_geometry_golden_patterns_and_missing_history_stay_none() -> None:
    """黄金样本：突破/回踩/恰在突破位三档 + 缺 K 线候选四字段保持 None(而非 0)。"""
    payload = _computed_factor_payload()
    items = cast(list[dict[str, Any]], payload["items"])
    assert len(items) == 4
    code_breakout, code_pullback, code_at_level, code_missing = (
        str(item["stock_code"]) for item in items
    )

    attached = attach_factor_screen_breakout_geometry(
        payload,
        close_history_by_code={
            code_breakout: _flat_history(100.0, 103.0),
            code_pullback: _flat_history(100.0, 98.0),
            code_at_level: _flat_history(100.0, 100.0),
            # code_missing 故意不提供 K 线
        },
        price_as_of_date="2026-05-28",
    )

    by_code = {str(item["stock_code"]): item for item in cast(list[dict[str, Any]], attached["items"])}

    breakout_item = by_code[code_breakout]
    assert breakout_item["close"] == 103.0
    assert breakout_item["breakout_level"] == 100.0
    assert breakout_item["distance_to_breakout_pct"] == 3.0
    assert breakout_item["pattern"] == PATTERN_BREAKOUT_LABEL

    pullback_item = by_code[code_pullback]
    assert pullback_item["distance_to_breakout_pct"] == -2.0
    assert pullback_item["pattern"] == PATTERN_PULLBACK_LABEL

    # 恰好收在突破位上：距离是真实的 0.0（数据齐全），不是缺数据的 None。
    at_level_item = by_code[code_at_level]
    assert at_level_item["distance_to_breakout_pct"] == 0.0
    assert at_level_item["pattern"] == PATTERN_CONSOLIDATION_LABEL

    # 缺 K 线：四字段全部 None，禁止用 0 冒充。
    missing_item = by_code[code_missing]
    assert missing_item["close"] is None
    assert missing_item["breakout_level"] is None
    assert missing_item["distance_to_breakout_pct"] is None
    assert missing_item["pattern"] is None

    geometry = cast(dict[str, Any], attached["breakout_geometry"])
    assert geometry["price_as_of_date"] == "2026-05-28"
    assert geometry["breakout_basis"] == "prior_55d_close_high"
    assert geometry["distance_basis"] == "close_over_breakout_minus_one_pct"

    # 选择与评分口径不变：attach 不改选择结果，也不回写原 payload/items。
    assert [str(item["stock_code"]) for item in cast(list[dict[str, Any]], attached["items"])] == [
        code_breakout,
        code_pullback,
        code_at_level,
        code_missing,
    ]
    for original_item in items:
        assert "pattern" not in original_item
        assert "distance_to_breakout_pct" not in original_item
    assert "breakout_geometry" not in payload

    serialized = json.dumps(attached, allow_nan=False, ensure_ascii=False)
    assert "NaN" not in serialized


def test_breakout_geometry_discloses_stale_price_anchor_for_suspended_stocks() -> None:
    """停牌披露：历史末日早于策略日的候选带 price_as_of_date + price_stale；
    末日等于策略日的候选不加字段；无几何值的候选即使日期滞后也不加字段。"""
    payload = _computed_factor_payload()
    items = cast(list[dict[str, Any]], payload["items"])
    code_fresh, code_suspended, code_missing, _ = (str(item["stock_code"]) for item in items)

    attached = attach_factor_screen_breakout_geometry(
        payload,
        close_history_by_code={
            code_fresh: _flat_history(100.0, 103.0),
            code_suspended: _flat_history(100.0, 98.0),
            # code_missing 无 K 线：几何字段 None，滞后日期不应引入披露字段。
        },
        price_as_of_date="2026-05-28",
        last_trade_date_by_code={
            code_fresh: "2026-05-28",
            code_suspended: "2026-05-20",
            code_missing: "2026-05-20",
        },
    )
    by_code = {str(item["stock_code"]): item for item in cast(list[dict[str, Any]], attached["items"])}

    fresh_item = by_code[code_fresh]
    assert "price_as_of_date" not in fresh_item
    assert "price_stale" not in fresh_item

    suspended_item = by_code[code_suspended]
    assert suspended_item["price_as_of_date"] == "2026-05-20"
    assert suspended_item["price_stale"] is True
    assert suspended_item["pattern"] == PATTERN_PULLBACK_LABEL

    missing_item = by_code[code_missing]
    assert missing_item["close"] is None
    assert "price_as_of_date" not in missing_item
    assert "price_stale" not in missing_item


def test_breakout_geometry_threshold_boundaries_match_livermore_display_rule() -> None:
    """比值恰在 1.0025 / 0.985 边界时不判突破/回踩（沿用现行展示口径的严格不等号）。"""
    payload = _computed_factor_payload()
    items = cast(list[dict[str, Any]], payload["items"])
    code_a, code_b, code_c, code_d = (str(item["stock_code"]) for item in items)

    attached = attach_factor_screen_breakout_geometry(
        payload,
        close_history_by_code={
            code_a: _flat_history(10000.0, 10025.0),  # 比值恰 1.0025 -> 非突破
            code_b: _flat_history(10000.0, 9850.0),  # 比值恰 0.9850 -> 非回踩
            code_c: _flat_history(10000.0, 10026.0),  # 略高于阈值 -> 突破
            code_d: _flat_history(10000.0, 9849.0),  # 略低于阈值 -> 回踩
        },
        price_as_of_date="2026-05-28",
    )
    by_code = {str(item["stock_code"]): item for item in cast(list[dict[str, Any]], attached["items"])}

    assert by_code[code_a]["pattern"] == PATTERN_CONSOLIDATION_LABEL
    assert by_code[code_a]["distance_to_breakout_pct"] == 0.25
    assert by_code[code_b]["pattern"] == PATTERN_CONSOLIDATION_LABEL
    assert by_code[code_b]["distance_to_breakout_pct"] == -1.5
    assert by_code[code_c]["pattern"] == PATTERN_BREAKOUT_LABEL
    assert by_code[code_d]["pattern"] == PATTERN_PULLBACK_LABEL


def test_breakout_geometry_fails_closed_on_short_invalid_or_nonpositive_history() -> None:
    """历史不足 56 根、含 None/NaN、或突破位非正：四字段保持 None,不缩窗改算。"""
    payload = _computed_factor_payload()
    items = cast(list[dict[str, Any]], payload["items"])
    code_short, code_none, code_nan, code_zero = (str(item["stock_code"]) for item in items)

    attached = attach_factor_screen_breakout_geometry(
        payload,
        close_history_by_code={
            code_short: [100.0] * (BREAKOUT_GEOMETRY_MIN_HISTORY - 1),
            code_none: [None, *([100.0] * (BREAKOUT_GEOMETRY_MIN_HISTORY - 1))],
            code_nan: [float("nan"), *([100.0] * (BREAKOUT_GEOMETRY_MIN_HISTORY - 1))],
            code_zero: [0.0] * BREAKOUT_GEOMETRY_MIN_HISTORY,
        },
        price_as_of_date="2026-05-28",
    )

    for item in cast(list[dict[str, Any]], attached["items"]):
        assert item["close"] is None
        assert item["breakout_level"] is None
        assert item["distance_to_breakout_pct"] is None
        assert item["pattern"] is None


def test_breakout_geometry_matches_livermore_stock_candidate_fields() -> None:
    """口径一致性：同一只股票、同一份收盘序列下,因子候选的 close/breakout_level 与
    Livermore 候选逐位相等,distance 可由 Livermore 字段按同一公式复算。"""
    from backend.app.core_finance.livermore_stock_candidates import (
        StockCandidateSnapshot,
        compute_stock_candidates,
    )

    closes = [100.0 + 0.5 * i for i in range(130)]
    turns = [1.0] * 130
    snapshot = StockCandidateSnapshot(
        stock_code="600100.SH",
        stock_name="Consistency",
        sector_code="801080",
        sector_name="电子",
        sector_rank=2,
        open_value=closes[-2],
        high_value=closes[-1],
        low_value=closes[-2],
        close_value=closes[-1],
        turnover_free=4.0,
        limit_ratio=0.1,
        close_history=closes,
        turnover_history=turns,
    )
    livermore_payload = cast(
        dict[str, Any],
        compute_stock_candidates(
            as_of_date="2026-05-27",
            market_state="WARM",
            snapshots=[snapshot],
        ).payload,
    )
    livermore_items = cast(list[dict[str, Any]], livermore_payload["items"])
    assert len(livermore_items) == 1
    livermore_item = livermore_items[0]

    factor_row = {**_sample_row(0), "stock_code": "600100.SH", "stock_name": "Consistency"}
    factor_payload = cast(
        dict[str, Any],
        compute_factor_screen_candidates(
            as_of_date="2026-05-23",  # 因子快照日可滞后；价格几何锚定策略日
            market_state="WARM",
            rows=[factor_row],
        ).payload,
    )
    attached = attach_factor_screen_breakout_geometry(
        factor_payload,
        close_history_by_code={"600100.SH": closes},
        price_as_of_date="2026-05-27",
    )
    factor_item = cast(list[dict[str, Any]], attached["items"])[0]

    assert factor_item["close"] == livermore_item["close"]
    assert factor_item["breakout_level"] == livermore_item["breakout_level"]
    livermore_close = cast(float, livermore_item["close"])
    livermore_breakout = cast(float, livermore_item["breakout_level"])
    expected_distance = round(
        (livermore_close - livermore_breakout) / livermore_breakout * 100.0,
        4,
    )
    assert factor_item["distance_to_breakout_pct"] == expected_distance
    assert factor_item["pattern"] == PATTERN_BREAKOUT_LABEL
