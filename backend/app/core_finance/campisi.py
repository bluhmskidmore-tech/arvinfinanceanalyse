"""
Campisi 风格债券归因（纯函数）。

与 V1 `advanced_pnl_attribution_service.calculate_campisi_attribution` 对齐：
- 基准利率变动：国债曲线线性插值（百分数），转为小数传入 `compute_bond_four_effects`
- 信用利差变动：Market 字段 BP 差 / 10000 → 小数
- 单券四效应：`bond_four_effects.compute_bond_four_effects`（AC 类利率/利差/选券归零）

市场字典约定：`treasury_1y`…`treasury_30y` 为**百分数**（如 2.55）；
`credit_spread_aaa_3y` / `credit_spread_aa_plus_3y` / `credit_spread_aa_3y` 为 **BP**。
若国债值均 < 2 且 > 0，视为小数形式并整体 ×100（兼容部分导入数据）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from .bond_four_effects import compute_bond_four_effects, compute_bond_six_effects
from .rate_units import detect_percent_unit_from_curve

_TENORS = [1, 3, 5, 7, 10, 30]
_TREASURY_KEYS = [
    "treasury_1y",
    "treasury_3y",
    "treasury_5y",
    "treasury_7y",
    "treasury_10y",
    "treasury_30y",
]

_MATURITY_BUCKET_LABELS = ("0-1Y", "1-3Y", "3-5Y", "5-7Y", "7-10Y", "10Y+")
logger = logging.getLogger(__name__)


def _coerce_percent_curve(m: dict[str, Any] | None) -> dict[str, float]:
    if not m:
        return {}
    out: dict[str, float] = {}
    for k in _TREASURY_KEYS:
        value = m.get(k)
        if value in (None, ""):
            continue
        numeric = float(value)
        if numeric > 0:
            out[k] = numeric
    # Keep the threshold in rate_units so curve-unit heuristics stay consistent.
    if out and not detect_percent_unit_from_curve(list(out.values())):
        for k in out:
            out[k] = out[k] * 100.0
    return out


def interpolate_treasury_yield_pct(market: dict[str, Any] | None, maturity_years: float) -> float:
    """在国债关键期限（年）间插值，输入/输出均为收益率百分数。

    Delegates to ``curve_engine`` cubic spline for ≥ 3 tenor points;
    falls back to piecewise linear otherwise.  Signature unchanged.
    """
    curve = _coerce_percent_curve(market)
    if not curve:
        return 0.0
    return _interpolate_percent_curve(curve, maturity_years)


def _interpolate_percent_curve(curve: dict[str, float], maturity_years: float) -> float:
    if not curve:
        return 0.0

    from backend.app.core_finance.curve_engine.curve_types import (
        CurvePoint,
        FittedCurve,
        InterpolationMethod,
    )
    from backend.app.core_finance.curve_engine.interpolation import (
        build_cubic_spline as _build_spline,
    )
    from backend.app.core_finance.curve_engine.interpolation import (
        interpolate as _engine_interpolate,
    )

    points = [
        CurvePoint(years=float(t), rate=Decimal(str(curve[k])))
        for k, t in zip(_TREASURY_KEYS, _TENORS, strict=False)
        if k in curve
    ]
    points.sort(key=lambda p: p.years)
    if len(points) < 2:
        logger.warning(
            "Treasury curve interpolation requires at least 2 positive tenors; got %s.",
            len(points),
        )
        return 0.0

    if len(points) >= 3:
        fitted = _build_spline(points)
    else:
        fitted = FittedCurve(method=InterpolationMethod.LINEAR, points=tuple(points))
    return float(_engine_interpolate(fitted, float(maturity_years)))


def benchmark_yield_change_decimal(
    market_start: dict[str, Any] | None,
    market_end: dict[str, Any] | None,
    maturity_years: float,
) -> Decimal:
    """期初期末国债收益率差（百分数点）→ 与 V1 一致的小数变动（= Δ% / 100）。"""
    start_curve = _coerce_percent_curve(market_start)
    end_curve = _coerce_percent_curve(market_end)
    common_keys = set(start_curve) & set(end_curve)
    if len(common_keys) < 2:
        logger.warning(
            "Benchmark yield change requires at least 2 shared positive tenors; got %s.",
            len(common_keys),
        )
        return Decimal("0")
    start_common = {k: start_curve[k] for k in _TREASURY_KEYS if k in common_keys}
    end_common = {k: end_curve[k] for k in _TREASURY_KEYS if k in common_keys}
    y0 = _interpolate_percent_curve(start_common, maturity_years)
    y1 = _interpolate_percent_curve(end_common, maturity_years)
    return Decimal(str((y1 - y0) / 100.0))


SPREAD_FIELD = {
    "AAA": "credit_spread_aaa_3y",
    "AA+": "credit_spread_aa_plus_3y",
    "AA": "credit_spread_aa_3y",
}

# Private alias for backward compatibility with any internal callers.
_SPREAD_FIELD = SPREAD_FIELD


def usable_spread_bp(market: dict[str, Any] | None, rating: str) -> float | None:
    """Return the rating's 3Y spread in bp when present, parseable, and positive."""
    key = _SPREAD_FIELD.get(rating)
    if not key or not market:
        return None
    value = market.get(key)
    if value in (None, ""):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        logger.warning(
            "Unparseable credit spread value for %s: %r; treated as unavailable.",
            key,
            value,
        )
        return None
    return numeric if numeric > 0 else None


def credit_spread_change_decimal(
    market_start: dict[str, Any] | None,
    market_end: dict[str, Any] | None,
    rating: str,
) -> Decimal:
    if rating == "GOV":
        return Decimal("0")
    key = _SPREAD_FIELD.get(rating)
    if not key:
        return Decimal("0")
    s0 = usable_spread_bp(market_start, rating)
    s1 = usable_spread_bp(market_end, rating)
    if s0 is None or s1 is None:
        logger.warning(
            "Credit spread change requires positive %s on both sides; start=%s, end=%s. Returning 0.",
            key,
            "present" if s0 is not None else "unavailable",
            "present" if s1 is not None else "unavailable",
        )
        return Decimal("0")
    return Decimal(str((s1 - s0) / 10000.0))


def treasury_tenor_coverage(
    market_start: dict[str, Any] | None,
    market_end: dict[str, Any] | None,
) -> dict[str, Any]:
    start_curve = _coerce_percent_curve(market_start)
    end_curve = _coerce_percent_curve(market_end)
    shared = [k for k in _TREASURY_KEYS if k in start_curve and k in end_curve]
    return {
        "required_keys": list(_TREASURY_KEYS),
        "start_missing": [k for k in _TREASURY_KEYS if k not in start_curve],
        "end_missing": [k for k in _TREASURY_KEYS if k not in end_curve],
        "shared_positive_tenors": len(shared),
    }


def infer_credit_rating_from_asset_class(asset_class: str | None) -> str:
    s = str(asset_class or "")
    rate_types = ("国债", "地方政府债", "政策性金融债", "央行票据", "国开债", "农发债", "进出口债")
    if any(t in s for t in rate_types):
        return "GOV"
    high = ("AAA", "国企", "央企", "大型银行", "政策性银行")
    if any(k in s for k in high):
        return "AAA"
    med = ("AA+", "上市公司", "城投债", "银行")
    if any(k in s for k in med):
        return "AA+"
    return "AA"


def _coupon_freq(asset_class: str | None) -> int:
    s = str(asset_class or "")
    if any(k in s for k in ("超短融", "SCP", "短期融资", "商业票据")):
        return 1
    return 2


def _years_to_maturity(maturity_date: date | None, as_of: date) -> float:
    if maturity_date is None:
        return 3.0
    days = (maturity_date - as_of).days
    y = days / 365.0
    return max(y, 0.01)


def _maturity_bucket(years: float) -> str:
    if years <= 1:
        return _MATURITY_BUCKET_LABELS[0]
    if years <= 3:
        return _MATURITY_BUCKET_LABELS[1]
    if years <= 5:
        return _MATURITY_BUCKET_LABELS[2]
    if years <= 7:
        return _MATURITY_BUCKET_LABELS[3]
    if years <= 10:
        return _MATURITY_BUCKET_LABELS[4]
    return _MATURITY_BUCKET_LABELS[5]


@dataclass
class CampisiResult:
    num_days: int
    totals: dict[str, float]
    by_asset_class: list[dict[str, Any]] = field(default_factory=list)
    by_bond: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)


def _aggregate_by_class(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    _ZERO = Decimal("0")
    _HUNDRED = Decimal("100")
    for r in rows:
        ac = str(r.get("asset_class") or "未分类")
        b = buckets.setdefault(
            ac,
            {
                "asset_class": ac,
                "market_value_start": _ZERO,
                "income_return": _ZERO,
                "treasury_effect": _ZERO,
                "spread_effect": _ZERO,
                "selection_effect": _ZERO,
                "total_return": _ZERO,
            },
        )
        b["market_value_start"] += Decimal(str(r.get("market_value_start") or 0))
        for k in ("income_return", "treasury_effect", "spread_effect", "selection_effect", "total_return"):
            b[k] += Decimal(str(r.get(k) or 0))
    out = list(buckets.values())
    total_mv = sum(b["market_value_start"] for b in out) or _ZERO
    for b in out:
        mv = b["market_value_start"]
        b["weight_pct"] = (b["market_value_start"] / total_mv * _HUNDRED) if total_mv > _ZERO else _ZERO
        for k in ("total_return", "income_return", "treasury_effect", "spread_effect", "selection_effect"):
            b[f"{k}_pct"] = (b[k] / mv * _HUNDRED) if mv and mv > _ZERO else _ZERO
    return sorted(out, key=lambda x: -abs(x["total_return"]))


def _aggregate_by_class_six(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    _ZERO = Decimal("0")
    _HUNDRED = Decimal("100")
    keys = (
        "income_return",
        "treasury_effect",
        "spread_effect",
        "convexity_effect",
        "cross_effect",
        "reinvestment_effect",
        "selection_effect",
        "total_return",
    )
    for r in rows:
        ac = str(r.get("asset_class") or "未分类")
        b = buckets.setdefault(
            ac,
            {
                "asset_class": ac,
                "market_value_start": _ZERO,
                **{k: _ZERO for k in keys},
            },
        )
        b["market_value_start"] += Decimal(str(r.get("market_value_start") or 0))
        for k in keys:
            b[k] += Decimal(str(r.get(k) or 0))
    out = list(buckets.values())
    total_mv = sum(b["market_value_start"] for b in out) or _ZERO
    for b in out:
        mv = b["market_value_start"]
        b["weight_pct"] = (b["market_value_start"] / total_mv * _HUNDRED) if total_mv > _ZERO else _ZERO
        for k in keys:
            if k == "total_return":
                continue
            b[f"{k}_pct"] = (b[k] / mv * _HUNDRED) if mv and mv > _ZERO else _ZERO
    return sorted(out, key=lambda x: -abs(x["total_return"]))


def campisi_attribution(
    positions_merged: list[dict[str, Any]],
    market_start: dict[str, Any] | None,
    market_end: dict[str, Any] | None,
    start_date: date,
    end_date: date,
) -> CampisiResult:
    """
    positions_merged: 每期已按 instrument 合并后的行，需含
    market_value_start/end, face_value_start, coupon_rate_start,
    yield_to_maturity_start, asset_class_start, maturity_date_start, bond_code。
    """
    num_days = max((end_date - start_date).days, 1)
    by_bond: list[dict[str, Any]] = []
    accrued_diagnostics: list[str] = []
    for row in positions_merged:
        mat = row.get("maturity_date_start")
        if hasattr(mat, "date"):
            mat_d = mat.date()
        elif isinstance(mat, date):
            mat_d = mat
        else:
            mat_d = None
        years = _years_to_maturity(mat_d, start_date)
        bench_dec = benchmark_yield_change_decimal(market_start, market_end, years)
        rating = infer_credit_rating_from_asset_class(row.get("asset_class_start"))
        spread_dec = credit_spread_change_decimal(market_start, market_end, rating)
        cf = _coupon_freq(row.get("asset_class_start"))
        bond = {
            "bond_code": row.get("bond_code") or row.get("instrument_id"),
            "market_value_start": row.get("market_value_start"),
            "market_value_end": row.get("market_value_end"),
            "face_value_start": row.get("face_value_start"),
            "coupon_rate_start": row.get("coupon_rate_start"),
            "yield_to_maturity_start": row.get("yield_to_maturity_start"),
            "asset_class_start": row.get("asset_class_start"),
            "maturity_date_start": mat_d,
            "accrued_interest_start": row.get("accrued_interest_start"),
            "accrued_interest_end": row.get("accrued_interest_end"),
        }
        fx = compute_bond_four_effects(bond, num_days, bench_dec, spread_dec, start_date, coupon_frequency=cf)
        bond_label = str(bond.get("bond_code") or bond.get("instrument_id") or "UNKNOWN")
        for d in fx.get("diagnostics") or []:
            accrued_diagnostics.append(f"{bond_label}: {d}")
        # Keep Decimal precision here; by_bond is aggregated into totals below in the
        # Decimal domain to avoid float sum() error accumulation across many bonds.
        # Converted to float only at the CampisiResult output boundary.
        rec = {
            "bond_code": bond["bond_code"],
            "asset_class": row.get("asset_class_start"),
            "maturity_bucket": _maturity_bucket(years),
            "market_value_start": Decimal(str(row.get("market_value_start") or 0)),
            "income_return": fx["income_return"],
            "treasury_effect": fx["treasury_effect"],
            "spread_effect": fx["spread_effect"],
            "selection_effect": fx["selection_effect"],
            "total_return": fx["total_return"],
            "mod_duration": fx["mod_duration"],
            "has_accrued_interest": bool(fx["has_accrued_interest"]),
        }
        by_bond.append(rec)

    _ZERO = Decimal("0")
    totals = {
        "income_return": float(sum((r["income_return"] for r in by_bond), _ZERO)),
        "treasury_effect": float(sum((r["treasury_effect"] for r in by_bond), _ZERO)),
        "spread_effect": float(sum((r["spread_effect"] for r in by_bond), _ZERO)),
        "selection_effect": float(sum((r["selection_effect"] for r in by_bond), _ZERO)),
        "total_return": float(sum((r["total_return"] for r in by_bond), _ZERO)),
        "market_value_start": float(sum((r["market_value_start"] for r in by_bond), _ZERO)),
    }
    by_class = _aggregate_by_class(by_bond)
    _NUMERIC_BOND_KEYS = (
        "market_value_start",
        "income_return",
        "treasury_effect",
        "spread_effect",
        "selection_effect",
        "total_return",
        "mod_duration",
    )
    by_bond_out = [{**r, **{k: float(r[k]) for k in _NUMERIC_BOND_KEYS}} for r in by_bond]
    return CampisiResult(
        num_days=num_days,
        totals=totals,
        by_asset_class=by_class,
        by_bond=by_bond_out,
        diagnostics=accrued_diagnostics,
    )


def campisi_enhanced(
    positions_merged: list[dict[str, Any]],
    market_start: dict[str, Any] | None,
    market_end: dict[str, Any] | None,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """
    Campisi 六效应：票息、利率、利差、凸性、交叉、再投资（再投资项当前为 0）+ 选券残差。

    与 V1 `campisi_attribution_enhanced` 文档口径一致；V1 实现将凸性/交叉/再投资并入选券，
    此处将二阶项显式拆出，残差更小。
    """
    num_days = max((end_date - start_date).days, 1)
    by_bond: list[dict[str, Any]] = []
    accrued_diagnostics: list[str] = []
    for row in positions_merged:
        mat = row.get("maturity_date_start")
        if hasattr(mat, "date"):
            mat_d = mat.date()
        elif isinstance(mat, date):
            mat_d = mat
        else:
            mat_d = None
        years = _years_to_maturity(mat_d, start_date)
        bench_dec = benchmark_yield_change_decimal(market_start, market_end, years)
        rating = infer_credit_rating_from_asset_class(row.get("asset_class_start"))
        spread_dec = credit_spread_change_decimal(market_start, market_end, rating)
        cf = _coupon_freq(row.get("asset_class_start"))
        bond = {
            "bond_code": row.get("bond_code") or row.get("instrument_id"),
            "market_value_start": row.get("market_value_start"),
            "market_value_end": row.get("market_value_end"),
            "face_value_start": row.get("face_value_start"),
            "coupon_rate_start": row.get("coupon_rate_start"),
            "yield_to_maturity_start": row.get("yield_to_maturity_start"),
            "asset_class_start": row.get("asset_class_start"),
            "maturity_date_start": mat_d,
            "accrued_interest_start": row.get("accrued_interest_start"),
            "accrued_interest_end": row.get("accrued_interest_end"),
        }
        sx = compute_bond_six_effects(bond, num_days, bench_dec, spread_dec, start_date, coupon_frequency=cf)
        bond_label = str(bond.get("bond_code") or bond.get("instrument_id") or "UNKNOWN")
        for d in sx.get("diagnostics") or []:
            accrued_diagnostics.append(f"{bond_label}: {d}")
        rec = {
            "bond_code": bond["bond_code"],
            "asset_class": row.get("asset_class_start"),
            "maturity_bucket": _maturity_bucket(years),
            "market_value_start": float(row.get("market_value_start") or 0),
            "income_return": float(sx["income_return"]),
            "treasury_effect": float(sx["treasury_effect"]),
            "spread_effect": float(sx["spread_effect"]),
            "convexity_effect": float(sx["convexity_effect"]),
            "cross_effect": float(sx["cross_effect"]),
            "reinvestment_effect": float(sx["reinvestment_effect"]),
            "selection_effect": float(sx["selection_effect"]),
            "total_return": float(sx["total_return"]),
            "mod_duration": float(sx["mod_duration"]),
            "has_accrued_interest": bool(sx["has_accrued_interest"]),
        }
        by_bond.append(rec)

    totals = {
        "income_return": sum(r["income_return"] for r in by_bond),
        "treasury_effect": sum(r["treasury_effect"] for r in by_bond),
        "spread_effect": sum(r["spread_effect"] for r in by_bond),
        "convexity_effect": sum(r["convexity_effect"] for r in by_bond),
        "cross_effect": sum(r["cross_effect"] for r in by_bond),
        "reinvestment_effect": sum(r["reinvestment_effect"] for r in by_bond),
        "selection_effect": sum(r["selection_effect"] for r in by_bond),
        "total_return": sum(r["total_return"] for r in by_bond),
        "market_value_start": sum(r["market_value_start"] for r in by_bond),
    }
    by_class = _aggregate_by_class_six(by_bond)
    return {
        "num_days": num_days,
        "totals": totals,
        "by_asset_class": by_class,
        "by_bond": by_bond,
        "diagnostics": accrued_diagnostics,
    }


def maturity_bucket_attribution(
    positions_merged: list[dict[str, Any]],
    market_start: dict[str, Any] | None,
    market_end: dict[str, Any] | None,
    start_date: date,
    end_date: date,
) -> dict[str, dict[str, float]]:
    base = campisi_attribution(
        positions_merged, market_start, market_end, start_date, end_date
    )
    out: dict[str, dict[str, float]] = {lbl: {} for lbl in _MATURITY_BUCKET_LABELS}
    for lbl in _MATURITY_BUCKET_LABELS:
        out[lbl] = {
            "market_value_start": 0.0,
            "income_return": 0.0,
            "treasury_effect": 0.0,
            "spread_effect": 0.0,
            "selection_effect": 0.0,
            "total_return": 0.0,
        }
    for r in base.by_bond:
        b = r["maturity_bucket"]
        if b not in out:
            continue
        out[b]["market_value_start"] += r["market_value_start"]
        for k in ("income_return", "treasury_effect", "spread_effect", "selection_effect", "total_return"):
            out[b][k] += r[k]
    return out


def classify_primary_driver(
    income: float,
    treasury: float,
    spread: float,
    selection: float,
    tie_threshold: float = 0.10,
) -> str:
    """
    从四个效应中选出主驱动；若前两名 abs 差 < tie_threshold * 第一名 abs，返回 'mixed'。

    返回 'income' | 'treasury' | 'spread' | 'selection' | 'mixed' | 'unknown'。

    参数：
    - income / treasury / spread / selection：四个效应的数值（正负均可，比较基于绝对值）
    - tie_threshold：接近度阈值，默认 0.10 表示前两名 abs 差 < 10% * 第一名 abs 判为 mixed
    """
    ranked = sorted(
        [
            ("income", abs(float(income))),
            ("treasury", abs(float(treasury))),
            ("spread", abs(float(spread))),
            ("selection", abs(float(selection))),
        ],
        key=lambda kv: kv[1],
        reverse=True,
    )
    top_name, top_val = ranked[0]
    if top_val <= 0:
        return "unknown"
    second_val = ranked[1][1]
    if second_val >= (1.0 - tie_threshold) * top_val:
        return "mixed"
    return top_name
