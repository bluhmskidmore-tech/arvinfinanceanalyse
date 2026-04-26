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

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from .bond_four_effects import compute_bond_four_effects, compute_bond_six_effects

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


def _coerce_percent_curve(m: dict[str, Any] | None) -> dict[str, float]:
    if not m:
        return {}
    out = {k: float(m.get(k) or 0) for k in _TREASURY_KEYS}
    vals = [v for v in out.values() if v and v > 0]
    if vals and max(vals) < 0.5:
        for k in out:
            out[k] = out[k] * 100.0
    return out


def interpolate_treasury_yield_pct(market: dict[str, Any] | None, maturity_years: float) -> float:
    """在国债关键期限（年）间线性插值，输入/输出均为收益率百分数。"""
    curve = _coerce_percent_curve(market)
    if not curve:
        return 0.0
    yields = [curve.get(k, 0.0) for k in _TREASURY_KEYS]
    y = float(maturity_years)
    if y <= _TENORS[0]:
        return yields[0]
    if y >= _TENORS[-1]:
        return yields[-1]
    for i in range(len(_TENORS) - 1):
        if _TENORS[i] <= y <= _TENORS[i + 1]:
            t0, t1 = _TENORS[i], _TENORS[i + 1]
            y0, y1 = yields[i], yields[i + 1]
            if t1 == t0:
                return y0
            return y0 + (y1 - y0) * (y - t0) / (t1 - t0)
    return yields[-1]


def benchmark_yield_change_decimal(
    market_start: dict[str, Any] | None,
    market_end: dict[str, Any] | None,
    maturity_years: float,
) -> Decimal:
    """期初期末国债收益率差（百分数点）→ 与 V1 一致的小数变动（= Δ% / 100）。"""
    y0 = interpolate_treasury_yield_pct(market_start, maturity_years)
    y1 = interpolate_treasury_yield_pct(market_end, maturity_years)
    return Decimal(str((y1 - y0) / 100.0))


_SPREAD_FIELD = {
    "AAA": "credit_spread_aaa_3y",
    "AA+": "credit_spread_aa_plus_3y",
    "AA": "credit_spread_aa_3y",
}


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
    s0 = float((market_start or {}).get(key) or 0)
    s1 = float((market_end or {}).get(key) or 0)
    return Decimal(str((s1 - s0) / 10000.0))


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


def _aggregate_by_class(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, float]] = {}
    for r in rows:
        ac = str(r.get("asset_class") or "未分类")
        b = buckets.setdefault(
            ac,
            {
                "asset_class": ac,
                "market_value_start": 0.0,
                "income_return": 0.0,
                "treasury_effect": 0.0,
                "spread_effect": 0.0,
                "selection_effect": 0.0,
                "total_return": 0.0,
            },
        )
        b["market_value_start"] += float(r.get("market_value_start") or 0)
        for k in ("income_return", "treasury_effect", "spread_effect", "selection_effect", "total_return"):
            b[k] += float(r.get(k) or 0)
    out = list(buckets.values())
    total_mv = sum(b["market_value_start"] for b in out) or 1.0
    for b in out:
        mv = b["market_value_start"] or 1.0
        b["weight_pct"] = b["market_value_start"] / total_mv * 100.0
        for k in ("total_return", "income_return", "treasury_effect", "spread_effect", "selection_effect"):
            b[f"{k}_pct"] = (b[k] / mv * 100.0) if mv else 0.0
    return sorted(out, key=lambda x: -abs(x["total_return"]))


def _aggregate_by_class_six(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, float]] = {}
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
                "market_value_start": 0.0,
                **{k: 0.0 for k in keys},
            },
        )
        b["market_value_start"] += float(r.get("market_value_start") or 0)
        for k in keys:
            b[k] += float(r.get(k) or 0)
    out = list(buckets.values())
    total_mv = sum(b["market_value_start"] for b in out) or 1.0
    for b in out:
        mv = b["market_value_start"] or 1.0
        b["weight_pct"] = b["market_value_start"] / total_mv * 100.0
        for k in keys:
            if k == "total_return":
                continue
            b[f"{k}_pct"] = (b[k] / mv * 100.0) if mv else 0.0
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
        }
        fx = compute_bond_four_effects(bond, num_days, bench_dec, spread_dec, start_date, coupon_frequency=cf)
        rec = {
            "bond_code": bond["bond_code"],
            "asset_class": row.get("asset_class_start"),
            "maturity_bucket": _maturity_bucket(years),
            "market_value_start": float(row.get("market_value_start") or 0),
            "income_return": float(fx["income_return"]),
            "treasury_effect": float(fx["treasury_effect"]),
            "spread_effect": float(fx["spread_effect"]),
            "selection_effect": float(fx["selection_effect"]),
            "total_return": float(fx["total_return"]),
            "mod_duration": float(fx["mod_duration"]),
        }
        by_bond.append(rec)

    totals = {
        "income_return": sum(r["income_return"] for r in by_bond),
        "treasury_effect": sum(r["treasury_effect"] for r in by_bond),
        "spread_effect": sum(r["spread_effect"] for r in by_bond),
        "selection_effect": sum(r["selection_effect"] for r in by_bond),
        "total_return": sum(r["total_return"] for r in by_bond),
        "market_value_start": sum(r["market_value_start"] for r in by_bond),
    }
    by_class = _aggregate_by_class(by_bond)
    return CampisiResult(num_days=num_days, totals=totals, by_asset_class=by_class, by_bond=by_bond)


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
        }
        sx = compute_bond_six_effects(bond, num_days, bench_dec, spread_dec, start_date, coupon_frequency=cf)
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
