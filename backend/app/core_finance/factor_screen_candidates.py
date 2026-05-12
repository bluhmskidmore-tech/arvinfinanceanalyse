from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

FORMULA_VERSION = "rv_factor_screen_candidates_v1"
# 所有市场状态都运行（多因子是基本面驱动，不依赖市场趋势）
ACTIVE_MARKET_STATES = {"OFF", "WARM", "HOT", "OVERHEAT"}
TOP_PCT = 0.10  # 取前 10%，约 64 只（643 * 0.1）
MAX_CANDIDATES = 30  # 最多输出 30 只


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
    from backend.app.core_finance.macro.equity_strategies import multi_factor_selection

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

    df_clean = df[required].dropna()
    if df_clean.empty:
        return FactorScreenResult(
            payload=_build_payload(
                as_of_date=as_of_date,
                market_state=market_state,
                input_count=len(rows),
                items=[],
                coverage_note="因子数据全部为空",
            )
        )

    selected = multi_factor_selection(df_clean, top_pct=TOP_PCT)
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
        f"因子数据覆盖 {total_universe}/5201 只（{total_universe / 5201 * 100:.0f}%），"
        "仅在有因子数据的股票中选股"
    )

    return FactorScreenResult(
        payload=_build_payload(
            as_of_date=as_of_date,
            market_state=market_state,
            input_count=total_universe,
            items=items,
            coverage_note=coverage_note,
        )
    )


def _build_payload(
    *,
    as_of_date: str,
    market_state: str,
    input_count: int,
    items: list[dict[str, object]],
    coverage_note: str,
) -> dict[str, object]:
    return {
        "as_of_date": as_of_date,
        "formula_version": FORMULA_VERSION,
        "market_state": market_state,
        "input_stock_count": input_count,
        "candidate_count": len(items),
        "coverage_note": coverage_note,
        "items": items,
    }


def _safe_round(value: object, ndigits: int = 4) -> float | None:
    try:
        return round(float(value), ndigits)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
