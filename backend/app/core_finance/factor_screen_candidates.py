from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from backend.app.core_finance.strategy_policy import POLICY

# v3：宇宙预过滤新增流动性地板（近 20 日均成交额 >= entry_filters.min_daily_amount），
# 均额缺失/无法定标的行 fail-closed 剔除并计数。
# v4：执行 POLICY 声明的市场状态门控；OFF 与非活跃数据态返回 inactive 空候选，
# WARM/HOT/OVERHEAT 保持 v3 评分与流动性过滤语义。
FORMULA_VERSION = "rv_factor_screen_candidates_v4"
ACTIVE_MARKET_STATES = POLICY.factor_screen_active_states
TOP_PCT = 0.10  # 取评分池前 10%（实际输出另受 MAX_CANDIDATES=30 截断）
MAX_CANDIDATES = 30  # 最多输出 30 只
MAX_CANDIDATES_PER_INDUSTRY = 3
MAX_ABS_ROE = 0.60
MAX_DIVIDEND_YIELD = 0.12
MIN_POSITIVE_MARGIN = 0.03
# 近 20 日均成交额列（元口径，由服务装载层经 choice_stock_units.amount_rmb_sql 归一化后传入）。
AVG_AMOUNT_20D_COLUMN = "avg_amount_20d"
# 流动性地板与动量族入场过滤同源（POLICY.entry_filters.min_daily_amount，元），
# 禁止在本模块另写阈值字面量。
MIN_AVG_AMOUNT_20D = float(POLICY.entry_filters.min_daily_amount)

# ---- 观察位几何（复用 Livermore 候选现行口径，观察展示字段，非正式交易结论） ----
# breakout_level 完全复用 Livermore 候选的现行公式：先导 55 个收盘的最高值，
# 剔除信号日，即 max(closes[-56:-1])
# （backend/app/core_finance/livermore_stock_candidates.py `_candidate_row`）。
# distance_to_breakout_pct 复用前端对 Livermore 候选的现行展示公式
# ((close - breakout_level) / breakout_level) * 100
# （frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts
#  `formatDistanceToBreakoutPct`），单位为百分数（3.0 表示 +3.00%）。
# pattern 复用同文件 `deriveCandidatePattern` 的现行有效映射：其换手/跳空分支
# 两侧输出相同标签，等效为仅按 close/breakout 比值分档；标签沿用「（参考）」
# 后缀的观察降级语义。fail-closed：K 线缺失/长度不足/含非有限值/突破位非正时
# 四个字段保持 None，禁止输出 0 或近似值。
BREAKOUT_GEOMETRY_PRIOR_WINDOW = 55
# 55 个先导收盘 + 1 个信号日收盘；不足时不得缩窗改算（那会变成另一种口径）。
BREAKOUT_GEOMETRY_MIN_HISTORY = BREAKOUT_GEOMETRY_PRIOR_WINDOW + 1
PATTERN_BREAKOUT_MIN_RATIO = 1.0025
PATTERN_PULLBACK_MAX_RATIO = 0.985
PATTERN_BREAKOUT_LABEL = "突破（参考）"
PATTERN_PULLBACK_LABEL = "回踩（参考）"
PATTERN_CONSOLIDATION_LABEL = "缩量盘整（参考）"


@dataclass(frozen=True)
class FactorScreenResult:
    payload: dict[str, object]


def compute_factor_screen_candidates(
    *,
    as_of_date: str,
    market_state: str,
    rows: list[dict[str, object]],
) -> FactorScreenResult:
    """
    rows 每条字段：
      stock_code, stock_name, pe, pb, ps, roe, gross_margin,
      three_month_return, twelve_month_return, volatility,
      dividend_yield, industry, sector_code, sector_name
    """

    raw_state = market_state.strip()
    if raw_state not in ACTIVE_MARKET_STATES:
        resolved_state = raw_state or market_state
        return FactorScreenResult(
            payload=_build_payload(
                as_of_date=as_of_date,
                market_state=resolved_state,
                input_count=len(rows),
                items=[],
                coverage_note=(
                    f"Factor screen inactive for market_state {resolved_state}; "
                    "active states are WARM/HOT/OVERHEAT."
                ),
                filtered_out_count=len(rows),
            )
        )
    market_state = raw_state

    if not rows:
        return FactorScreenResult(
            payload=_build_payload(
                as_of_date=as_of_date,
                market_state=market_state,
                input_count=0,
                items=[],
                coverage_note="factor_snapshot 无数据",
            )
        )

    df = pd.DataFrame(rows)
    df = df.set_index("stock_code")

    required = [
        "pe",
        "pb",
        "ps",
        "roe",
        "gross_margin",
        "three_month_return",
        "twelve_month_return",
        "volatility",
        "dividend_yield",
        "industry",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return FactorScreenResult(
            payload=_build_payload(
                as_of_date=as_of_date,
                market_state=market_state,
                input_count=len(rows),
                items=[],
                coverage_note=f"缺少字段: {', '.join(missing)}",
            )
        )

    meta_cols = ["stock_name", "sector_code", "sector_name"]
    for col in meta_cols:
        if col not in df.columns:
            df[col] = ""

    df_required = df.dropna(subset=required)
    # 两段过滤：df_base 仅基础条件(ST/财务极值/正估值),df_clean 追加流动性地板；
    # 差值用于如实上报流动性过滤规模(低于地板 vs 均额缺失 fail-closed)。
    df_base = _filter_factor_screen_universe(df_required)
    df_clean = _filter_factor_screen_universe(df_required, min_avg_amount_20d=MIN_AVG_AMOUNT_20D)
    avg_amount_base = _avg_amount_20d_numeric(df_base)
    liquidity_missing_count = int((~np.isfinite(avg_amount_base)).sum())
    liquidity_below_count = len(df_base) - len(df_clean) - liquidity_missing_count
    liquidity_filter: dict[str, object] = {
        "basis": AVG_AMOUNT_20D_COLUMN,
        "min_avg_amount_20d": MIN_AVG_AMOUNT_20D,
        "policy_source": "POLICY.entry_filters.min_daily_amount",
        "evaluated_count": len(df_base),
        "pass_count": len(df_clean),
        "below_floor_count": liquidity_below_count,
        "missing_amount_count": liquidity_missing_count,
    }
    if df_clean.empty:
        # input_stock_count 语义为"进入评分池的行数"(过滤后),此处评分池为空则为 0；
        # screened_out_count 用于区分"必填字段全空"与"必填字段完整但未通过筛选"两种根因。
        screened_out_count = len(df_required)
        if screened_out_count > 0:
            coverage_note = (
                f"必填字段完整的 {screened_out_count} 只候选均未通过筛选条件"
                "(如 ST、极端 ROE/股息率、非正估值、近 20 日均成交额低于流动性地板或均额无法核定等),评分池为空"
            )
        else:
            coverage_note = "因子必填字段全部缺失,评分池为空"
        return FactorScreenResult(
            payload=_build_payload(
                as_of_date=as_of_date,
                market_state=market_state,
                input_count=0,
                items=[],
                coverage_note=coverage_note,
                filtered_out_count=len(rows),
                liquidity_filter=liquidity_filter,
            )
        )

    selected = _multi_factor_selection(
        df_clean,
        top_pct=TOP_PCT,
        max_per_industry=MAX_CANDIDATES_PER_INDUSTRY,
    )
    selected = selected.head(MAX_CANDIDATES)

    meta = df[meta_cols].reindex(selected.index)

    items = []
    for rank, (stock_code, row) in enumerate(selected.iterrows(), start=1):
        mloc = meta.loc[stock_code] if stock_code in meta.index else None
        stock_name_val = stock_code
        sector_code_val = ""
        sector_name_val = ""
        if mloc is not None:
            sn = mloc["stock_name"]
            sc = mloc["sector_code"]
            snm = mloc["sector_name"]
            if pd.notna(sn) and str(sn).strip():
                stock_name_val = str(sn)
            if pd.notna(sc):
                sector_code_val = str(sc)
            if pd.notna(snm):
                sector_name_val = str(snm)

        items.append(
            {
                "rank": rank,
                "stock_code": str(stock_code),
                "stock_name": stock_name_val,
                "sector_code": sector_code_val,
                "sector_name": sector_name_val,
                "industry": str(row.get("industry", "")),
                "score": round(float(row["score"]), 4),
                "pe": _safe_round(row.get("pe")),
                "pb": _safe_round(row.get("pb")),
                "roe": _safe_round(row.get("roe")),
                "gross_margin": _safe_round(row.get("gross_margin")),
                "three_month_return": _safe_round(row.get("three_month_return")),
                "twelve_month_return": _safe_round(row.get("twelve_month_return")),
                "dividend_yield": _safe_round(row.get("dividend_yield")),
                # 元口径；候选经流动性地板筛选,该值恒为有限且 >= MIN_AVG_AMOUNT_20D。
                "avg_amount_20d": _safe_round(row.get(AVG_AMOUNT_20D_COLUMN), 2),
                # 逐候选补记选股公式版本,随既有 signal_evidence_json 物化路径落库(治理字段)。
                "formula_version": FORMULA_VERSION,
            }
        )

    total_universe = len(df_clean)
    liquidity_dropped = liquidity_below_count + liquidity_missing_count
    # 注意:成功型 coverage_note 不得包含服务层错误关键词(无数据/缺少/缺失/为空/失败),
    # 否则会被 _is_factor_screen_error_note 误判为降级原因。
    coverage_note = (
        f"本次多因子评分池为 {total_universe} 只（必填字段完整、通过基础筛选条件且近 20 日均成交额不低于 "
        f"{MIN_AVG_AMOUNT_20D / 1e8:.1f} 亿元），流动性过滤剔除 {liquidity_dropped} 只，"
        "仅在该评分池内生成观察候选"
    )

    return FactorScreenResult(
        payload=_build_payload(
            as_of_date=as_of_date,
            market_state=market_state,
            input_count=total_universe,
            items=items,
            coverage_note=coverage_note,
            filtered_out_count=len(rows) - total_universe,
            liquidity_filter=liquidity_filter,
        )
    )


def _build_payload(
    *,
    as_of_date: str,
    market_state: str,
    input_count: int,
    items: list[dict[str, object]],
    coverage_note: str,
    filtered_out_count: int = 0,
    liquidity_filter: dict[str, object] | None = None,
) -> dict[str, object]:
    # liquidity_filter=None 表示宇宙过滤尚未执行(无数据/缺字段的早退路径),
    # 与"已评估但剔除 0 只"显式区分。
    return {
        "as_of_date": as_of_date,
        "formula_version": FORMULA_VERSION,
        "market_state": market_state,
        "input_stock_count": input_count,
        "filtered_out_count": filtered_out_count,
        "candidate_count": len(items),
        "coverage_note": coverage_note,
        "liquidity_filter": liquidity_filter,
        "items": items,
    }


def attach_factor_screen_breakout_geometry(
    payload: dict[str, object],
    *,
    close_history_by_code: Mapping[str, Sequence[object]],
    price_as_of_date: str,
    last_trade_date_by_code: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """为多因子候选补充观察位几何字段（close/breakout_level/distance_to_breakout_pct/pattern）。

    - close_history_by_code 必须与 Livermore 候选同源同序：升序收盘序列，
      锚定 price_as_of_date（策略日，而非因子快照日），服务层复用
      fetch_stock_candidate_history_rows 装载，保证同一只股票在
      stock_candidates 与 factor_screen_candidates 两个来源下几何值一致。
    - 因子候选入选不要求策略日当天有 K 线（不同于 Livermore 候选）：停牌股的
      close 实际锚定最近可得交易日。当 last_trade_date_by_code 给出的末日早于
      price_as_of_date 时，item 级补充 price_as_of_date（实际价格日）与
      price_stale=True，防止消费方把旧价当作策略日价格。
    - 不修改传入 payload/items（返回新对象）；候选选择与评分口径不变。
    """
    last_dates = last_trade_date_by_code or {}

    def _item_with_geometry(item: dict[str, object]) -> dict[str, object]:
        stock_code = str(item.get("stock_code") or "")
        fields = _breakout_geometry_fields(close_history_by_code.get(stock_code))
        if fields["close"] is not None:
            actual_price_date = str(last_dates.get(stock_code) or "").strip()
            if actual_price_date and actual_price_date != price_as_of_date:
                fields = {
                    **fields,
                    "price_as_of_date": actual_price_date,
                    "price_stale": True,
                }
        return {**item, **fields}

    items = [_item_with_geometry(item) for item in _payload_item_dicts(payload)]
    return {
        **payload,
        "items": items,
        "breakout_geometry": {
            # 几何锚定日：与 Livermore 候选相同的策略 as_of_date；因子快照日
            # 滞后时两者不同，须以本字段核对价格证据日期。
            "price_as_of_date": price_as_of_date,
            "breakout_basis": "prior_55d_close_high",
            "distance_basis": "close_over_breakout_minus_one_pct",
        },
    }


def _payload_item_dicts(payload: dict[str, object]) -> list[dict[str, object]]:
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _breakout_geometry_fields(
    close_history: Sequence[object] | None,
) -> dict[str, float | str | None]:
    empty: dict[str, float | str | None] = {
        "close": None,
        "breakout_level": None,
        "distance_to_breakout_pct": None,
        "pattern": None,
    }
    if close_history is None or len(close_history) < BREAKOUT_GEOMETRY_MIN_HISTORY:
        return empty
    closes: list[float] = []
    for value in close_history:
        try:
            as_float = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            # 与 livermore_stock_candidates._float_series 同口径：序列中任一
            # 元素无效即整体视为不可用，不做局部剔除后的缩窗改算。
            return empty
        if not math.isfinite(as_float):
            return empty
        closes.append(as_float)
    breakout_level = max(closes[-BREAKOUT_GEOMETRY_MIN_HISTORY:-1])
    close = closes[-1]
    if breakout_level <= 0:
        # 突破位非正（脏数据）时距离无定义，fail-closed 保持 None。
        return empty
    ratio = close / breakout_level
    if ratio > PATTERN_BREAKOUT_MIN_RATIO:
        pattern = PATTERN_BREAKOUT_LABEL
    elif ratio < PATTERN_PULLBACK_MAX_RATIO:
        pattern = PATTERN_PULLBACK_LABEL
    else:
        pattern = PATTERN_CONSOLIDATION_LABEL
    return {
        # 6 位小数与 Livermore 候选 item 的 close/breakout_level 舍入一致。
        "close": round(close, 6),
        "breakout_level": round(breakout_level, 6),
        "distance_to_breakout_pct": round((close - breakout_level) / breakout_level * 100.0, 4),
        "pattern": pattern,
    }


def _safe_round(value: object, ndigits: int = 4) -> float | None:
    try:
        as_float = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    # +-inf/NaN 若透传到 JSON 输出会产生非法 token(Infinity/NaN);展示字段一律
    # 退化为 None,而非把脏数据伪装成数值。评分权重已由 _rank_score 处理(NA -> 0)。
    if not math.isfinite(as_float):
        return None
    return round(as_float, ndigits)


def _multi_factor_selection(
    df: pd.DataFrame,
    *,
    top_pct: float,
    max_per_industry: int,
) -> pd.DataFrame:
    if not 0 < top_pct <= 1:
        raise ValueError("top_pct must be in the (0, 1] range")
    if max_per_industry <= 0:
        raise ValueError("max_per_industry must be positive")

    scored = df.copy()
    scored["pe_score"] = _rank_low_is_good(scored["pe"])
    scored["pb_score"] = _rank_low_is_good(scored["pb"])
    scored["ps_score"] = _rank_low_is_good(scored["ps"])
    scored["roe_score"] = _rank_high_is_good(scored["roe"])
    scored["margin_score"] = _rank_high_is_good(scored["gross_margin"])
    scored["mom_3m_score"] = _rank_high_is_good(scored["three_month_return"])
    scored["mom_12m_score"] = _rank_high_is_good(scored["twelve_month_return"])
    scored["vol_score"] = _rank_low_is_good(scored["volatility"])
    scored["div_score"] = _rank_high_is_good(scored["dividend_yield"])
    scored["score"] = (
        0.16 * scored["roe_score"]
        + 0.14 * scored["margin_score"]
        + 0.12 * scored["pe_score"]
        + 0.10 * scored["pb_score"]
        + 0.08 * scored["ps_score"]
        + 0.14 * scored["mom_3m_score"]
        + 0.10 * scored["mom_12m_score"]
        + 0.10 * scored["vol_score"]
        + 0.06 * scored["div_score"]
    )

    selected = (
        scored.sort_values("score", ascending=False)
        .groupby("industry", group_keys=False, sort=False)
        .head(max_per_industry)
    )
    candidate_count = max(1, int(len(scored) * top_pct))
    return selected.sort_values("score", ascending=False).head(candidate_count)


def _rank_low_is_good(series: pd.Series) -> pd.Series:
    return _rank_score(series, ascending=False)


def _rank_high_is_good(series: pd.Series) -> pd.Series:
    return _rank_score(series, ascending=True)


def _rank_score(series: pd.Series, *, ascending: bool) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce").replace([float("inf"), float("-inf")], pd.NA)
    return clean.rank(pct=True, ascending=ascending).fillna(0.0).astype("float64")


def _avg_amount_20d_numeric(df: pd.DataFrame) -> pd.Series:
    """近 20 日均成交额列的数值视图(元)；列不存在时按全缺失处理(fail-closed)。"""
    if AVG_AMOUNT_20D_COLUMN in df.columns:
        return pd.to_numeric(df[AVG_AMOUNT_20D_COLUMN], errors="coerce")
    return pd.Series(np.nan, index=df.index, dtype="float64")


def _filter_factor_screen_universe(
    df: pd.DataFrame,
    *,
    min_avg_amount_20d: float | None = None,
) -> pd.DataFrame:
    stock_name = df.get("stock_name", pd.Series("", index=df.index)).fillna("").astype(str).str.upper()
    mask = ~stock_name.str.match(r"^\*?ST")
    mask &= pd.to_numeric(df["roe"], errors="coerce").abs() <= MAX_ABS_ROE
    mask &= pd.to_numeric(df["dividend_yield"], errors="coerce") <= MAX_DIVIDEND_YIELD
    mask &= pd.to_numeric(df["gross_margin"], errors="coerce") >= MIN_POSITIVE_MARGIN
    # 估值因子按"低者优"排名打分：负/零 pe/pb/ps（亏损或异常数据）会被排到
    # 最优档，必须先排除。摄入层（stock_factor_refresh / choice_stock_materialize
    # 的 _positive_float_or_none）已保证非正值写为 NULL，此处为口径防护，
    # 与 livermore_stock_candidates 基本面 overlay 的正值口径一致。
    # 同时要求有限：+inf > 0 为真，若不显式排除会绕过"正值"过滤混入候选
    # （且后续 JSON 输出会产生非法的 Infinity token）。
    for column in ("pe", "pb", "ps"):
        numeric = pd.to_numeric(df[column], errors="coerce")
        mask &= np.isfinite(numeric) & (numeric > 0)
    # v3 流动性地板(可选参数)：默认 None 保持旧行为，equity_shadow_portfolio 等
    # 未提供均额列的复用方不受影响；factor_screen 主路径显式传入地板。
    # fail-closed：均额缺失/无法定标(NaN)与非有限值一律不通过。
    if min_avg_amount_20d is not None:
        avg_amount = _avg_amount_20d_numeric(df)
        mask &= np.isfinite(avg_amount) & (avg_amount >= min_avg_amount_20d)
    return df[mask]
