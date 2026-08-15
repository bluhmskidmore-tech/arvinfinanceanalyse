"""
Campisi 风格债券归因（纯函数）。

与 V1 `advanced_pnl_attribution_service.calculate_campisi_attribution` 对齐：
- 基准利率变动：国债曲线线性插值（百分数），转为小数传入 `compute_bond_four_effects`
- 信用利差变动：Market 字段 BP 差 / 10000 → 小数
- 单券四效应：`bond_four_effects.compute_bond_four_effects`（AC 类利率/利差/选券归零）

市场字典约定：`treasury_1y`…`treasury_30y` 为**百分数**（如 2.55）；
`credit_spread_aaa_3y` / `credit_spread_aa_plus_3y` / `credit_spread_aa_3y` 为 **BP**。
若国债非空正值的最大值 < 0.5，视为小数形式并整体 ×100（阈值见
`rate_units.detect_percent_unit_from_curve`；兼容部分导入数据）。

carry/income 天数口径：`num_days = (end_date - start_date).days`（不含头含尾；
同日窗口下限 1 天），`income_return = coupon × face × num_days / 365`。
与 attribution_daily 及 `bond_analytics.read_models.summarize_return_decomposition`
展示层 carry 口径一致（2026-07-19 已统一）。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from .bond_four_effects import (
    CLEAN_PRICE_FALLBACK_DIAGNOSTICS,
    compute_bond_four_effects,
    compute_bond_six_effects,
)
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
# 与 services/campisi_attribution_service._formal_maturity_bucket 的缺失桶名保持一致，
# 否则同一端点的 formal-bridge 路径与 Campisi 回退路径会给出两套桶名。
_MATURITY_BUCKET_UNKNOWN = "UNKNOWN"
_MATURITY_MISSING_FALLBACK_YEARS = 3.0
MATURITY_DATE_MISSING_DIAGNOSTIC = "maturity_date_missing_fallback_3y"

# 效应可用性状态。"ok" 表示效应是被观测出来的（哪怕数值恰好是 0）；
# "unavailable" 表示输入缺失导致的结构性 0，不能当成"市场没动"来读。
EFFECT_STATUS_OK = "ok"
EFFECT_STATUS_PARTIAL = "partial"
EFFECT_STATUS_UNAVAILABLE = "unavailable"

# 曲线两端共同正期限 < 2 时基准变动求值器退化为恒 0。
BENCHMARK_CURVE_DEGENERATE_REASON = "insufficient_shared_positive_tenors"
SPREAD_INPUT_MISSING_REASON = "credit_spread_input_missing"
ACCRUED_INTEREST_MISSING_REASON = "accrued_interest_missing"
TREASURY_EFFECT_UNAVAILABLE_DIAGNOSTIC = "treasury_effect_unavailable"
SPREAD_EFFECT_UNAVAILABLE_DIAGNOSTIC = "spread_effect_unavailable"
ACCRUED_INTEREST_FALLBACK_DIAGNOSTIC = "accrued_interest_clean_price_fallback"
_MIN_SHARED_TENORS = 2

logger = logging.getLogger(__name__)


def _coerce_percent_curve(m: dict[str, Any] | None) -> dict[str, float]:
    if not m:
        return {}
    out: dict[str, float] = {}
    for k in _TREASURY_KEYS:
        value = m.get(k)
        # 与 `value in (None, "")` 等价；拆开写以便 mypy 收窄掉 None。
        if value is None or value == "":
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


def _fit_percent_curve(curve: dict[str, float]):
    """Fit a ``FittedCurve`` once from a percent tenor curve; ``None`` if < 2 tenors.

    Split out of ``_interpolate_percent_curve`` so batch callers can build the
    (possibly cubic-spline) curve object once and evaluate it per bond.
    """
    from backend.app.core_finance.curve_engine.curve_types import (
        CurvePoint,
        FittedCurve,
        InterpolationMethod,
    )
    from backend.app.core_finance.curve_engine.interpolation import (
        build_cubic_spline as _build_spline,
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
        return None

    if len(points) >= 3:
        return _build_spline(points)
    return FittedCurve(method=InterpolationMethod.LINEAR, points=tuple(points))


def _interpolate_percent_curve(curve: dict[str, float], maturity_years: float) -> float:
    if not curve:
        return 0.0

    from backend.app.core_finance.curve_engine.interpolation import (
        interpolate as _engine_interpolate,
    )

    fitted = _fit_percent_curve(curve)
    if fitted is None:
        return 0.0
    return float(_engine_interpolate(fitted, float(maturity_years)))


class BenchmarkYieldChange:
    """基准变动求值器，自带可用性状态。

    ``available is False`` 表示两端曲线的共同正期限少于 2 个，求值恒为 0 —— 这是
    输入缺失造成的结构性 0，**不是**"基准利率没有变动"。调用方必须把它与真实的
    零变动区分开披露，否则页面上的"利率效应 0"会被读成"利率没动"。
    """

    __slots__ = ("available", "reason", "shared_tenor_count", "_evaluate")

    def __init__(
        self,
        evaluate: Callable[[float], Decimal],
        *,
        available: bool,
        shared_tenor_count: int,
        reason: str | None = None,
    ) -> None:
        self._evaluate = evaluate
        self.available = available
        self.shared_tenor_count = shared_tenor_count
        self.reason = reason

    def __call__(self, maturity_years: float) -> Decimal:
        return self._evaluate(maturity_years)


def _build_benchmark_change_evaluator(
    market_start: dict[str, Any] | None,
    market_end: dict[str, Any] | None,
) -> BenchmarkYieldChange:
    """构建一次 (start, end) 曲线对象，返回 maturity_years -> Δ小数 的求值器。

    与逐券调用 ``benchmark_yield_change_decimal`` 数值完全一致：同样的共同期限
    交集、同样的样条/线性拟合与求值；差别仅是曲线对象只构建一次。
    """
    start_curve = _coerce_percent_curve(market_start)
    end_curve = _coerce_percent_curve(market_end)
    common_keys = set(start_curve) & set(end_curve)
    if len(common_keys) < _MIN_SHARED_TENORS:
        n_common = len(common_keys)
        # 在构建处告警一次，而不是每只债券求值时各告警一次：退化是曲线级事实，
        # 逐券刷屏反而会把它淹没（正式表 1829 行曾产生 1829 条同样的 WARNING）。
        logger.warning(
            "Benchmark yield change requires at least %s shared positive tenors; got %s. "
            "treasury_effect is unavailable for this period, not an observed zero.",
            _MIN_SHARED_TENORS,
            n_common,
        )

        def _degenerate(_maturity_years: float) -> Decimal:
            return Decimal("0")

        return BenchmarkYieldChange(
            _degenerate,
            available=False,
            shared_tenor_count=n_common,
            reason=BENCHMARK_CURVE_DEGENERATE_REASON,
        )

    from backend.app.core_finance.curve_engine.interpolation import (
        interpolate as _engine_interpolate,
    )

    fitted_start = _fit_percent_curve({k: start_curve[k] for k in _TREASURY_KEYS if k in common_keys})
    fitted_end = _fit_percent_curve({k: end_curve[k] for k in _TREASURY_KEYS if k in common_keys})

    def _evaluate(maturity_years: float) -> Decimal:
        # 插值引擎本身返回 Decimal；保持 Decimal 算术，
        # 避免 float 相减/除 100 后再 Decimal(str(...)) 回转的精度损失。
        y0 = _engine_interpolate(fitted_start, float(maturity_years))
        y1 = _engine_interpolate(fitted_end, float(maturity_years))
        return (y1 - y0) / Decimal("100")

    return BenchmarkYieldChange(
        _evaluate,
        available=True,
        shared_tenor_count=len(common_keys),
    )


def benchmark_yield_change_decimal(
    market_start: dict[str, Any] | None,
    market_end: dict[str, Any] | None,
    maturity_years: float,
) -> Decimal:
    """期初期末国债收益率差（百分数点）→ 与 V1 一致的小数变动（= Δ% / 100）。"""
    return _build_benchmark_change_evaluator(market_start, market_end)(maturity_years)


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
    # 与 `value in (None, "")` 等价；拆开写以便 mypy 收窄掉 None。
    if value is None or value == "":
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


def credit_spread_change_available(
    market_start: dict[str, Any] | None,
    market_end: dict[str, Any] | None,
    rating: str,
) -> bool:
    """``credit_spread_change_decimal`` 的 0 是否为观测值。

    GOV 的 0 是口径上的结构性 0（利率债不承担信用利差），属于"可用"；
    其余评级只有两端都拿得到正利差时才算可用，否则返回的 0 是输入缺失。
    """
    if rating == "GOV":
        return True
    if not _SPREAD_FIELD.get(rating):
        return False
    return (
        usable_spread_bp(market_start, rating) is not None
        and usable_spread_bp(market_end, rating) is not None
    )


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
    # str(float) 是最短精确 repr；先逐值转 Decimal 再减/除，BP 差不再引入 float 误差。
    return (Decimal(str(s1)) - Decimal(str(s0))) / Decimal("10000")


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
    """缺到期日时回退 3Y 曲线取点。

    返回值保持 float，调用方签名不变；缺失事实由调用方以
    ``MATURITY_DATE_MISSING_DIAGNOSTIC`` 显式披露，回退不再无声。
    """
    if maturity_date is None:
        logger.warning(
            "maturity_date missing as of %s; benchmark curve point falls back to %sY (%s).",
            as_of,
            _MATURITY_MISSING_FALLBACK_YEARS,
            MATURITY_DATE_MISSING_DIAGNOSTIC,
        )
        return _MATURITY_MISSING_FALLBACK_YEARS
    days = (maturity_date - as_of).days
    y = days / 365.0
    return max(y, 0.01)


def _maturity_bucket(years: float, *, maturity_date_known: bool = True) -> str:
    """到期日缺失时归入 UNKNOWN 桶，不得按 3Y 回退值落进 1-3Y 桶。

    曲线取点仍需一个数值代理（3Y），但桶归属是纯分类，猜出来的期限落进真实桶
    会让桶级汇总失真且不可见。
    """
    if not maturity_date_known:
        return _MATURITY_BUCKET_UNKNOWN
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
class _EffectAvailabilityCounters:
    """逐券累计"效应是被观测出来的还是被输入缺失顶成 0 的"。"""

    bonds: int = 0
    market_value_start: Decimal = Decimal("0")
    spread_unavailable_bonds: int = 0
    spread_unavailable_mv_start: Decimal = Decimal("0")
    clean_price_fallback_bonds: int = 0
    clean_price_fallback_mv_start: Decimal = Decimal("0")

    def observe(
        self,
        *,
        market_value_start: Decimal,
        spread_available: bool,
        clean_price_fallback: bool,
    ) -> None:
        self.bonds += 1
        self.market_value_start += market_value_start
        if not spread_available:
            self.spread_unavailable_bonds += 1
            self.spread_unavailable_mv_start += market_value_start
        if clean_price_fallback:
            self.clean_price_fallback_bonds += 1
            self.clean_price_fallback_mv_start += market_value_start


def _resolve_spread_change(
    cache: dict[str, tuple[Decimal, bool]],
    market_start: dict[str, Any] | None,
    market_end: dict[str, Any] | None,
    rating: str,
) -> tuple[Decimal, bool]:
    """按评级缓存 (Δ利差, 是否可用)。

    ``credit_spread_change_decimal`` 是 (market_start, market_end, rating) 的纯函数，
    而前两者在一次归因内不变，所以按评级缓存与逐券调用逐字段等价；顺带把它的
    "缺利差" WARNING 从每券一条压到每评级一条。
    """
    cached = cache.get(rating)
    if cached is None:
        cached = (
            credit_spread_change_decimal(market_start, market_end, rating),
            credit_spread_change_available(market_start, market_end, rating),
        )
        cache[rating] = cached
    return cached


def coverage_status(degraded: int, total: int) -> str:
    """按"多少只债券受影响"折叠成 ok / partial / unavailable。"""
    if total <= 0 or degraded <= 0:
        return EFFECT_STATUS_OK
    return EFFECT_STATUS_UNAVAILABLE if degraded >= total else EFFECT_STATUS_PARTIAL


_coverage_status = coverage_status


def effect_availability_entry(
    *,
    status: str,
    reason: str | None,
    unavailable_bonds: int,
    unavailable_market_value_start: Decimal | float,
    **extra: Any,
) -> dict[str, Any]:
    """每个效应统一的状态块形状。

    Campisi 直算路径与 formal-bridge 路径必须给出同一组键，否则页面得按来源分两套
    渲染分支，而"哪条路径产生了这份 payload"恰恰是使用者最不该关心的事。
    """
    return {
        "status": status,
        "reason": reason,
        "unavailable_bonds": unavailable_bonds,
        "unavailable_market_value_start": float(unavailable_market_value_start),
        **extra,
    }


def accrued_interest_basis(status: str) -> str:
    if status == EFFECT_STATUS_OK:
        return "dirty_price"
    return "clean_price_fallback" if status == EFFECT_STATUS_UNAVAILABLE else "mixed"


def _build_effect_availability(
    counters: _EffectAvailabilityCounters,
    bench_change: BenchmarkYieldChange,
) -> dict[str, Any]:
    """把逐券累计折叠成页面/调用方可直接分支的显式状态块。

    三种"效应为 0"必须能被区分：曲线缺失或共同期限不足（treasury_effect）、
    利差输入缺失（spread_effect）、应计缺失导致整条归因链跑在净价退化分支上
    （accrued_interest）。任何一项非 ok 时，调用方都不得把对应的 0 当作观测值发布。
    """
    treasury_available = bench_change.available
    spread_status = coverage_status(counters.spread_unavailable_bonds, counters.bonds)
    accrued_status = coverage_status(counters.clean_price_fallback_bonds, counters.bonds)
    return {
        "bonds": counters.bonds,
        "treasury_effect": effect_availability_entry(
            status=EFFECT_STATUS_OK if treasury_available else EFFECT_STATUS_UNAVAILABLE,
            reason=bench_change.reason,
            # 曲线退化是整期事实，一旦退化就覆盖全部债券。
            unavailable_bonds=0 if treasury_available else counters.bonds,
            unavailable_market_value_start=(
                Decimal("0") if treasury_available else counters.market_value_start
            ),
            shared_positive_tenors=bench_change.shared_tenor_count,
            min_required_shared_tenors=_MIN_SHARED_TENORS,
        ),
        "spread_effect": effect_availability_entry(
            status=spread_status,
            reason=None if spread_status == EFFECT_STATUS_OK else SPREAD_INPUT_MISSING_REASON,
            unavailable_bonds=counters.spread_unavailable_bonds,
            unavailable_market_value_start=counters.spread_unavailable_mv_start,
        ),
        "accrued_interest": effect_availability_entry(
            status=accrued_status,
            reason=None if accrued_status == EFFECT_STATUS_OK else ACCRUED_INTEREST_MISSING_REASON,
            unavailable_bonds=counters.clean_price_fallback_bonds,
            unavailable_market_value_start=counters.clean_price_fallback_mv_start,
            basis=accrued_interest_basis(accrued_status),
        ),
    }


def availability_diagnostics(availability: dict[str, Any]) -> list[str]:
    """把非 ok 状态翻成人读得懂的一行披露（每种退化一条，不逐券刷屏）。"""
    out: list[str] = []
    bonds = availability["bonds"]
    treasury = availability["treasury_effect"]
    if treasury["status"] != EFFECT_STATUS_OK:
        # 期限细节只有 Campisi 直算路径有；formal-bridge 路径的成因已由桥的行级
        # 诊断给出，这里只按公共键叙述，不假设调用方一定填了细节键。
        shared = treasury.get("shared_positive_tenors")
        detail = (
            f"benchmark curve has {shared} shared positive tenors "
            f"(need >= {treasury.get('min_required_shared_tenors', _MIN_SHARED_TENORS)})"
            if shared is not None
            else f"reason={treasury['reason']}"
        )
        out.append(
            f"{TREASURY_EFFECT_UNAVAILABLE_DIAGNOSTIC}: {detail}; treasury_effect is unavailable "
            f"on {treasury['unavailable_bonds']}/{bonds} bonds "
            f"(market_value_start {treasury['unavailable_market_value_start']:.2f}) "
            'and must not be read as "rates did not move".'
        )
    spread = availability["spread_effect"]
    if spread["status"] != EFFECT_STATUS_OK:
        out.append(
            f"{SPREAD_EFFECT_UNAVAILABLE_DIAGNOSTIC}: credit spread inputs are missing for "
            f"{spread['unavailable_bonds']}/{bonds} bonds "
            f"(market_value_start {spread['unavailable_market_value_start']:.2f}); "
            "spread_effect is unavailable on those rows, not an observed zero."
        )
    accrued = availability["accrued_interest"]
    if accrued["status"] != EFFECT_STATUS_OK:
        out.append(
            f"{ACCRUED_INTEREST_FALLBACK_DIAGNOSTIC}: "
            f"{accrued['unavailable_bonds']}/{bonds} bonds carry no usable "
            f"accrued interest (market_value_start "
            f"{accrued['unavailable_market_value_start']:.2f}); total_return degrades to "
            "clean price + modeled coupon on those rows and selection_effect systematically absorbs "
            "the par/market difference."
        )
    return out


_availability_diagnostics = availability_diagnostics


@dataclass
class CampisiResult:
    num_days: int
    totals: dict[str, float]
    by_asset_class: list[dict[str, Any]] = field(default_factory=list)
    by_bond: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    effect_availability: dict[str, Any] = field(default_factory=dict)


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
    counters = _EffectAvailabilityCounters()
    # Fit the start/end treasury curves once per attribution call instead of
    # rebuilding the cubic spline for every bond; numerically identical.
    bench_change = _build_benchmark_change_evaluator(market_start, market_end)
    spread_cache: dict[str, tuple[Decimal, bool]] = {}
    for row in positions_merged:
        mat = row.get("maturity_date_start")
        # None 先行排除与 hasattr 语义等价（hasattr(None, "date") 恒为 False），便于 mypy 收窄。
        if mat is not None and hasattr(mat, "date"):
            mat_d = mat.date()
        elif isinstance(mat, date):
            mat_d = mat
        else:
            mat_d = None
        years = _years_to_maturity(mat_d, start_date)
        bench_dec = bench_change(years)
        rating = infer_credit_rating_from_asset_class(row.get("asset_class_start"))
        spread_dec, spread_available = _resolve_spread_change(
            spread_cache, market_start, market_end, rating
        )
        cf = _coupon_freq(row.get("asset_class_start"))
        bond = {
            "bond_code": row.get("bond_code") or row.get("instrument_id"),
            "market_value_start": row.get("market_value_start"),
            "market_value_end": row.get("market_value_end"),
            "face_value_start": row.get("face_value_start"),
            "coupon_rate_start": row.get("coupon_rate_start"),
            "yield_to_maturity_start": row.get("yield_to_maturity_start"),
            "asset_class_start": row.get("asset_class_start"),
            "accounting_class": row.get("accounting_class"),
            "maturity_date_start": mat_d,
            "accrued_interest_start": row.get("accrued_interest_start"),
            "accrued_interest_end": row.get("accrued_interest_end"),
        }
        fx = compute_bond_four_effects(bond, num_days, bench_dec, spread_dec, start_date, coupon_frequency=cf)
        bond_label = str(bond.get("bond_code") or bond.get("instrument_id") or "UNKNOWN")
        diagnostics = fx.get("diagnostics") or []
        for d in diagnostics:
            accrued_diagnostics.append(f"{bond_label}: {d}")
        if mat_d is None:
            accrued_diagnostics.append(f"{bond_label}: {MATURITY_DATE_MISSING_DIAGNOSTIC}")
        mv_start = Decimal(str(row.get("market_value_start") or 0))
        counters.observe(
            market_value_start=mv_start,
            spread_available=spread_available,
            clean_price_fallback=bool(CLEAN_PRICE_FALLBACK_DIAGNOSTICS.intersection(diagnostics)),
        )
        # Keep Decimal precision here; by_bond is aggregated into totals below in the
        # Decimal domain to avoid float sum() error accumulation across many bonds.
        # Converted to float only at the CampisiResult output boundary.
        rec = {
            "bond_code": bond["bond_code"],
            "asset_class": row.get("asset_class_start"),
            "maturity_bucket": _maturity_bucket(years, maturity_date_known=mat_d is not None),
            "market_value_start": mv_start,
            "income_return": fx["income_return"],
            "treasury_effect": fx["treasury_effect"],
            "spread_effect": fx["spread_effect"],
            "selection_effect": fx["selection_effect"],
            "total_return": fx["total_return"],
            "mod_duration": fx["mod_duration"],
            "has_accrued_interest": bool(fx["has_accrued_interest"]),
            "treasury_effect_available": bench_change.available,
            "spread_effect_available": spread_available,
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
    availability = _build_effect_availability(counters, bench_change)
    return CampisiResult(
        num_days=num_days,
        totals=totals,
        by_asset_class=by_class,
        by_bond=by_bond_out,
        # 退化披露排在逐券诊断之前：逐券诊断可能上千条，把"整期不可用"顶到尾部就等于没披露。
        diagnostics=[*_availability_diagnostics(availability), *accrued_diagnostics],
        effect_availability=availability,
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
    counters = _EffectAvailabilityCounters()
    # Same one-time curve fit as campisi_attribution; see comment there.
    bench_change = _build_benchmark_change_evaluator(market_start, market_end)
    spread_cache: dict[str, tuple[Decimal, bool]] = {}
    for row in positions_merged:
        mat = row.get("maturity_date_start")
        # None 先行排除与 hasattr 语义等价（hasattr(None, "date") 恒为 False），便于 mypy 收窄。
        if mat is not None and hasattr(mat, "date"):
            mat_d = mat.date()
        elif isinstance(mat, date):
            mat_d = mat
        else:
            mat_d = None
        years = _years_to_maturity(mat_d, start_date)
        bench_dec = bench_change(years)
        rating = infer_credit_rating_from_asset_class(row.get("asset_class_start"))
        spread_dec, spread_available = _resolve_spread_change(
            spread_cache, market_start, market_end, rating
        )
        cf = _coupon_freq(row.get("asset_class_start"))
        bond = {
            "bond_code": row.get("bond_code") or row.get("instrument_id"),
            "market_value_start": row.get("market_value_start"),
            "market_value_end": row.get("market_value_end"),
            "face_value_start": row.get("face_value_start"),
            "coupon_rate_start": row.get("coupon_rate_start"),
            "yield_to_maturity_start": row.get("yield_to_maturity_start"),
            "asset_class_start": row.get("asset_class_start"),
            "accounting_class": row.get("accounting_class"),
            "maturity_date_start": mat_d,
            "accrued_interest_start": row.get("accrued_interest_start"),
            "accrued_interest_end": row.get("accrued_interest_end"),
        }
        sx = compute_bond_six_effects(bond, num_days, bench_dec, spread_dec, start_date, coupon_frequency=cf)
        bond_label = str(bond.get("bond_code") or bond.get("instrument_id") or "UNKNOWN")
        diagnostics = sx.get("diagnostics") or []
        for d in diagnostics:
            accrued_diagnostics.append(f"{bond_label}: {d}")
        if mat_d is None:
            accrued_diagnostics.append(f"{bond_label}: {MATURITY_DATE_MISSING_DIAGNOSTIC}")
        mv_start = Decimal(str(row.get("market_value_start") or 0))
        counters.observe(
            market_value_start=mv_start,
            spread_available=spread_available,
            clean_price_fallback=bool(CLEAN_PRICE_FALLBACK_DIAGNOSTICS.intersection(diagnostics)),
        )
        rec = {
            "bond_code": bond["bond_code"],
            "asset_class": row.get("asset_class_start"),
            "maturity_bucket": _maturity_bucket(years, maturity_date_known=mat_d is not None),
            "market_value_start": mv_start,
            "income_return": sx["income_return"],
            "treasury_effect": sx["treasury_effect"],
            "spread_effect": sx["spread_effect"],
            "convexity_effect": sx["convexity_effect"],
            "cross_effect": sx["cross_effect"],
            "reinvestment_effect": sx["reinvestment_effect"],
            "selection_effect": sx["selection_effect"],
            "total_return": sx["total_return"],
            "mod_duration": sx["mod_duration"],
            "has_accrued_interest": bool(sx["has_accrued_interest"]),
            "treasury_effect_available": bench_change.available,
            "spread_effect_available": spread_available,
        }
        by_bond.append(rec)

    _ZERO = Decimal("0")
    totals = {
        "income_return": float(sum((r["income_return"] for r in by_bond), _ZERO)),
        "treasury_effect": float(sum((r["treasury_effect"] for r in by_bond), _ZERO)),
        "spread_effect": float(sum((r["spread_effect"] for r in by_bond), _ZERO)),
        "convexity_effect": float(sum((r["convexity_effect"] for r in by_bond), _ZERO)),
        "cross_effect": float(sum((r["cross_effect"] for r in by_bond), _ZERO)),
        "reinvestment_effect": float(sum((r["reinvestment_effect"] for r in by_bond), _ZERO)),
        "selection_effect": float(sum((r["selection_effect"] for r in by_bond), _ZERO)),
        "total_return": float(sum((r["total_return"] for r in by_bond), _ZERO)),
        "market_value_start": float(sum((r["market_value_start"] for r in by_bond), _ZERO)),
    }
    by_class = _aggregate_by_class_six(by_bond)
    _NUMERIC_BOND_KEYS = (
        "market_value_start",
        "income_return",
        "treasury_effect",
        "spread_effect",
        "convexity_effect",
        "cross_effect",
        "reinvestment_effect",
        "selection_effect",
        "total_return",
        "mod_duration",
    )
    by_bond_out = [{**r, **{k: float(r[k]) for k in _NUMERIC_BOND_KEYS}} for r in by_bond]
    availability = _build_effect_availability(counters, bench_change)
    return {
        "num_days": num_days,
        "totals": totals,
        "by_asset_class": by_class,
        "by_bond": by_bond_out,
        "diagnostics": [*_availability_diagnostics(availability), *accrued_diagnostics],
        "effect_availability": availability,
    }


def _empty_bucket_totals() -> dict[str, float]:
    return {
        "market_value_start": 0.0,
        "income_return": 0.0,
        "treasury_effect": 0.0,
        "spread_effect": 0.0,
        "selection_effect": 0.0,
        "total_return": 0.0,
    }


def aggregate_maturity_buckets(by_bond: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """将 ``campisi_attribution`` 的 ``by_bond`` 行聚合为到期桶四效应。

    输入行需含 ``maturity_bucket`` 及 float 化的四效应字段（即 CampisiResult.by_bond）。
    聚合顺序与字段与原 ``maturity_bucket_attribution`` 内联实现完全一致，
    供 service 复用已缓存的四效应逐券结果时调用，数值逐字段等价。
    """
    out: dict[str, dict[str, float]] = {lbl: _empty_bucket_totals() for lbl in _MATURITY_BUCKET_LABELS}
    for r in by_bond:
        b = r["maturity_bucket"]
        if b not in out:
            # UNKNOWN 桶按需出现（与 service 侧 `_formal_bridge_to_maturity_buckets` 同调）：
            # 无缺到期日券时输出仍是原 6 桶，有则显式多出一桶而不是被丢弃。
            if b != _MATURITY_BUCKET_UNKNOWN:
                continue
            out[b] = _empty_bucket_totals()
        out[b]["market_value_start"] += r["market_value_start"]
        for k in ("income_return", "treasury_effect", "spread_effect", "selection_effect", "total_return"):
            out[b][k] += r[k]
    return out


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
    return aggregate_maturity_buckets(base.by_bond)


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
