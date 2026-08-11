from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.app.core_finance.strategy_policy import POLICY

FORMULA_VERSION = "rv_factor_screen_candidates_v2"
# 所有市场状态都运行（多因子是基本面驱动，不依赖市场趋势）
ACTIVE_MARKET_STATES = POLICY.factor_screen_active_states
TOP_PCT = 0.10  # 取前 10%，约 64 只（643 * 0.1）
MAX_CANDIDATES = 30  # 最多输出 30 只
MAX_CANDIDATES_PER_INDUSTRY = 3
MAX_ABS_ROE = 0.60
MAX_DIVIDEND_YIELD = 0.12
MIN_POSITIVE_MARGIN = 0.03


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

    _ = market_state  # 基本面选股与市场门控解耦；保留参数便于 payload 追溯

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
    df_clean = _filter_factor_screen_universe(df_required)
    if df_clean.empty:
        # input_stock_count 语义为"进入评分池的行数"(过滤后),此处评分池为空则为 0；
        # screened_out_count 用于区分"必填字段全空"与"必填字段完整但未通过筛选"两种根因。
        screened_out_count = len(df_required)
        if screened_out_count > 0:
            coverage_note = (
                f"必填字段完整的 {screened_out_count} 只候选均未通过筛选条件"
                "(如 ST、极端 ROE/股息率、非正估值等),评分池为空"
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
            }
        )

    total_universe = len(df_clean)
    coverage_note = (
        f"本次多因子评分池为 {total_universe} 只（必填字段完整且通过当前筛选条件），"
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
) -> dict[str, object]:
    return {
        "as_of_date": as_of_date,
        "formula_version": FORMULA_VERSION,
        "market_state": market_state,
        "input_stock_count": input_count,
        "filtered_out_count": filtered_out_count,
        "candidate_count": len(items),
        "coverage_note": coverage_note,
        "items": items,
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


def _filter_factor_screen_universe(df: pd.DataFrame) -> pd.DataFrame:
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
    return df[mask]
