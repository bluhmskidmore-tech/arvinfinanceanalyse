"""
组合相对利率基准的超额收益（V1 benchmark_excess 的 DuckDB 可落地子集）。

- 组合收益率：区间实际 PnL / 期初债券总市值（由调用方注入）。
- 基准收益率：目标久期 × 国债曲线平行移动的一阶近似（-D × Δy），非 Wind 指数。
- 分解：久期偏离项 + 残差作为「选择/其他」；曲线/利差细分在缺少指数与 KRD 基准分布时记 0。

金额、久期为数值；收益率为小数（0.012 = 1.2%）；超额与各 effect 输出为 bp。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from .safe_decimal import safe_decimal


BENCHMARK_PROFILES: dict[str, dict[str, object]] = {
    "TREASURY_INDEX": {
        "name": "中债国债总指数（曲线代理）",
        "target_duration": Decimal("5.5"),
        "tenors": ("1Y", "3Y", "5Y", "10Y"),
    },
    "CDB_INDEX": {
        "name": "中债国开债总指数（曲线代理）",
        "target_duration": Decimal("7.0"),
        "tenors": ("1Y", "3Y", "5Y", "10Y"),
    },
    "AAA_CREDIT_INDEX": {
        "name": "中债AAA企业债指数（曲线代理）",
        "target_duration": Decimal("4.2"),
        "tenors": ("3Y", "5Y", "10Y"),
    },
}


def _avg_parallel_shift(
    gov_start: Mapping[str, Decimal],
    gov_end: Mapping[str, Decimal],
    tenors: tuple[str, ...],
) -> Decimal:
    deltas: list[Decimal] = []
    for t in tenors:
        a = gov_start.get(t)
        b = gov_end.get(t)
        if a is None or b is None:
            continue
        deltas.append(b - a)
    if not deltas:
        return Decimal("0")
    return sum(deltas, Decimal("0")) / Decimal(len(deltas))


def compute_benchmark_excess(
    *,
    period_pnl: Decimal,
    start_total_mv: Decimal,
    portfolio_mod_duration: Decimal,
    gov_curve_start: Mapping[str, Decimal],
    gov_curve_end: Mapping[str, Decimal],
    benchmark_id: str = "CDB_INDEX",
) -> dict[str, object]:
    """
    Returns dict with float/bp-friendly values for API layer.

    benchmark_return_decimal ≈ -D_bench * avg_dy
    portfolio_return_decimal = period_pnl / start_total_mv
    excess_bp = (port - bench) * 10000
    duration_effect_bp = -(D_port - D_bench) * avg_dy * 10000
    selection_effect_bp = excess_bp - duration_effect_bp - curve_effect_bp - spread_effect_bp
    """
    profile = BENCHMARK_PROFILES.get(benchmark_id) or BENCHMARK_PROFILES["CDB_INDEX"]
    bench_name = str(profile["name"])
    d_bench = safe_decimal(profile["target_duration"])
    tenors = profile["tenors"]
    if not isinstance(tenors, tuple):
        tenors = tuple(str(x) for x in tenors)  # type: ignore[arg-type]

    warnings: list[str] = []
    if start_total_mv <= 0:
        warnings.append("BENCHMARK_EXCESS_NO_START_MV")
        return _empty_payload(bench_name, benchmark_id, warnings)

    dy = _avg_parallel_shift(gov_curve_start, gov_curve_end, tenors)
    if dy == 0 and not gov_curve_start and not gov_curve_end:
        warnings.append("BENCHMARK_EXCESS_NO_GOV_CURVE")

    port_ret = period_pnl / start_total_mv
    bench_ret = -d_bench * dy
    excess_bp = (port_ret - bench_ret) * Decimal("10000")

    dur_diff = portfolio_mod_duration - d_bench
    duration_effect_bp = -dur_diff * dy * Decimal("10000")
    curve_effect_bp = Decimal("0")
    spread_effect_bp = Decimal("0")
    selection_effect_bp = excess_bp - duration_effect_bp - curve_effect_bp - spread_effect_bp
    explained_bp = duration_effect_bp + curve_effect_bp + spread_effect_bp + selection_effect_bp
    recon_bp = excess_bp - explained_bp

    return {
        "benchmark_name": bench_name,
        "benchmark_id_resolved": benchmark_id if benchmark_id in BENCHMARK_PROFILES else "CDB_INDEX",
        "portfolio_return_pct": float(port_ret * Decimal("100")),
        "benchmark_return_pct": float(bench_ret * Decimal("100")),
        "excess_return_bp": float(excess_bp),
        "duration_effect_bp": float(duration_effect_bp),
        "curve_effect_bp": float(curve_effect_bp),
        "spread_effect_bp": float(spread_effect_bp),
        "selection_effect_bp": float(selection_effect_bp),
        "explained_excess_bp": float(explained_bp),
        "recon_error_bp": float(recon_bp),
        "portfolio_duration": float(portfolio_mod_duration),
        "benchmark_duration": float(d_bench),
        "duration_diff": float(dur_diff),
        "parallel_shift_decimal": float(dy),
        "excess_sources": [
            {
                "source": "duration",
                "contribution_bp": float(duration_effect_bp),
                "description": f"久期偏离 × 曲线平移（组合久期 {float(portfolio_mod_duration):.2f} 年 vs 基准目标 {float(d_bench):.2f} 年）",
            },
            {
                "source": "curve",
                "contribution_bp": float(curve_effect_bp),
                "description": "曲线非平行项（当前未分解，占位 0）",
            },
            {
                "source": "spread",
                "contribution_bp": float(spread_effect_bp),
                "description": "信用利差相对基准（当前未分解，占位 0）",
            },
            {
                "source": "selection",
                "contribution_bp": float(selection_effect_bp),
                "description": "残差（超额 − 已解释因子，含个券选择与近似误差）",
            },
        ],
        "warnings": warnings + ["BENCHMARK_RETURN_CURVE_PROXY_NOT_WIND_INDEX"],
    }


def _empty_payload(bench_name: str, benchmark_id: str, warnings: list[str]) -> dict[str, object]:
    z = 0.0
    return {
        "benchmark_name": bench_name,
        "benchmark_id_resolved": benchmark_id,
        "portfolio_return_pct": z,
        "benchmark_return_pct": z,
        "excess_return_bp": z,
        "duration_effect_bp": z,
        "curve_effect_bp": z,
        "spread_effect_bp": z,
        "selection_effect_bp": z,
        "explained_excess_bp": z,
        "recon_error_bp": z,
        "portfolio_duration": z,
        "benchmark_duration": z,
        "duration_diff": z,
        "parallel_shift_decimal": z,
        "excess_sources": [],
        "warnings": warnings,
    }
