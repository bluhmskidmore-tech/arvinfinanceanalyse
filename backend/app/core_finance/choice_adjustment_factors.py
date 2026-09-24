"""Derive stock adjustment factors from Choice backward-adjusted (后复权) closes.

口径说明（证据：D:/ChoiceRoadshow/EMQuantAPI_Python/EMQuantAPI_Python.pdf p13，
AdjustFlag 1=不复权/2=后复权/3=前复权）：

- Tushare ``adj_factor`` 满足 ``hfq_price = raw_price * adj_factor``。
- Choice ``csd CLOSE`` 在 ``AdjustFlag=2`` 与 ``AdjustFlag=1`` 下的比值
  ``rel(d) = hfq_close(d) / raw_close(d)`` 与真实累计复权因子成正比，
  比例常数由 Choice 的后复权基期决定，且仅在除权除息日发生跳变。
- ``adjusted_returns.adjusted_return`` 只消费同一股票两个日期因子之比，
  常数比例本身不影响收益；但 ``stock_adjustment_factor`` 表内同一股票会
  混合 tushare 行与 choice 推导行（执行历史 entry/exit、成熟任务
  signal/forward 会跨行取因子），因此 choice 相对因子必须先用重叠日期
  锚定到既有 tushare 尺度再落表，否则跨源因子之比会引入基期常数误差。

锚定与一致性：
- ``scale = median(reference(d) / rel(d))`` 对全部重叠日期取中位数；
- 重叠日数低于 ``min_anchor_overlap`` 时容差/收益一致性校验退化为空
  （单日重叠 ``scale_max_rel_deviation ≡ 0``），fail-closed 拒绝锚定并
  返回 ``insufficient_overlap``，不输出任何因子；
- 任一重叠日 ``|scale_i / scale - 1|`` 超过容差，即两源在重叠段内的
  复权收益不一致（等价于相邻重叠日收益比偏差），拒绝落表并报差异率。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import median

ANCHOR_SCALE_MODE = "median_overlap_ratio"
DEFAULT_CONSISTENCY_TOLERANCE = 2e-3
DEFAULT_MIN_ANCHOR_OVERLAP = 3

STATUS_ANCHORED = "anchored"
STATUS_UNANCHORED = "unanchored"
STATUS_INCONSISTENT_OVERLAP = "inconsistent_overlap"
STATUS_INSUFFICIENT_DATA = "insufficient_data"
STATUS_INSUFFICIENT_OVERLAP = "insufficient_overlap"


@dataclass(frozen=True)
class ChoiceFactorDerivation:
    stock_code: str
    status: str
    factors: dict[str, float] = field(default_factory=dict)
    missing_requested_dates: tuple[str, ...] = ()
    scale: float | None = None
    anchor_overlap_count: int = 0
    scale_max_rel_deviation: float | None = None
    return_consistency_max_rel_diff: float | None = None
    return_consistency_breach_count: int = 0
    return_consistency_pair_count: int = 0
    overlap_event_pair_count: int = 0
    overlap_event_matched_count: int = 0


def derive_relative_factors(
    raw_close_by_date: dict[str, float | None],
    adjusted_close_by_date: dict[str, float | None],
) -> dict[str, float]:
    """rel(d) = 后复权收盘 / 不复权收盘，仅保留两侧同时为正且有限的日期。"""
    relative: dict[str, float] = {}
    for trade_date, raw_close in raw_close_by_date.items():
        adjusted_close = adjusted_close_by_date.get(trade_date)
        if not _is_positive_finite(raw_close) or not _is_positive_finite(adjusted_close):
            continue
        assert raw_close is not None and adjusted_close is not None
        relative[trade_date] = adjusted_close / raw_close
    return relative


def derive_choice_adjustment_factors(
    *,
    stock_code: str,
    raw_close_by_date: dict[str, float | None],
    adjusted_close_by_date: dict[str, float | None],
    reference_factors_by_date: dict[str, float],
    requested_dates: list[str],
    consistency_tolerance: float = DEFAULT_CONSISTENCY_TOLERANCE,
    allow_unanchored: bool = False,
    min_anchor_overlap: int = DEFAULT_MIN_ANCHOR_OVERLAP,
) -> ChoiceFactorDerivation:
    """把 Choice 相对因子锚定到 reference（既有 tushare）尺度并输出请求日期的因子。

    - ``reference_factors_by_date``：该股票在取数窗口内既有的 ``adj_factor`` 行。
    - ``requested_dates``：需要落表的缺失日期；返回值只包含这些日期。
    - 重叠日数低于 ``min_anchor_overlap`` 时返回 ``insufficient_overlap``，
      不输出任何因子（``allow_unanchored`` 不豁免：该股票已有 reference 行，
      混入 scale=1 相对因子会失义）。
    - 重叠段一致性不达标时返回 ``inconsistent_overlap``，不输出任何因子。
    """
    if min_anchor_overlap < 1:
        raise ValueError(f"min_anchor_overlap must be >= 1, got {min_anchor_overlap}")
    relative = derive_relative_factors(raw_close_by_date, adjusted_close_by_date)
    requested_unique = sorted(dict.fromkeys(requested_dates))
    if not relative:
        return ChoiceFactorDerivation(
            stock_code=stock_code,
            status=STATUS_INSUFFICIENT_DATA,
            missing_requested_dates=tuple(requested_unique),
        )

    reference = {
        trade_date: value
        for trade_date, value in reference_factors_by_date.items()
        if _is_positive_finite(value)
    }
    overlap_dates = sorted(set(relative) & set(reference))

    if not overlap_dates:
        missing = tuple(d for d in requested_unique if d not in relative)
        factors = (
            {d: relative[d] for d in requested_unique if d in relative}
            if allow_unanchored
            else {}
        )
        return ChoiceFactorDerivation(
            stock_code=stock_code,
            status=STATUS_UNANCHORED,
            factors=factors,
            missing_requested_dates=missing,
            scale=1.0 if allow_unanchored else None,
        )

    scales = [reference[d] / relative[d] for d in overlap_dates]
    anchor_scale = median(scales)
    scale_max_rel_deviation = max(abs(s / anchor_scale - 1.0) for s in scales)

    consistency = _overlap_return_consistency(
        relative=relative,
        reference=reference,
        overlap_dates=overlap_dates,
        tolerance=consistency_tolerance,
    )

    if len(overlap_dates) < min_anchor_overlap:
        # 重叠样本不足时容差校验退化（单日重叠恒为 0），fail-closed 不锚定。
        return ChoiceFactorDerivation(
            stock_code=stock_code,
            status=STATUS_INSUFFICIENT_OVERLAP,
            missing_requested_dates=tuple(d for d in requested_unique if d not in relative),
            scale=anchor_scale,
            anchor_overlap_count=len(overlap_dates),
            scale_max_rel_deviation=scale_max_rel_deviation,
            **consistency,
        )

    if scale_max_rel_deviation > consistency_tolerance:
        return ChoiceFactorDerivation(
            stock_code=stock_code,
            status=STATUS_INCONSISTENT_OVERLAP,
            missing_requested_dates=tuple(d for d in requested_unique if d not in relative),
            scale=anchor_scale,
            anchor_overlap_count=len(overlap_dates),
            scale_max_rel_deviation=scale_max_rel_deviation,
            **consistency,
        )

    factors = {
        trade_date: relative[trade_date] * anchor_scale
        for trade_date in requested_unique
        if trade_date in relative
    }
    missing = tuple(d for d in requested_unique if d not in relative)
    return ChoiceFactorDerivation(
        stock_code=stock_code,
        status=STATUS_ANCHORED,
        factors=factors,
        missing_requested_dates=missing,
        scale=anchor_scale,
        anchor_overlap_count=len(overlap_dates),
        scale_max_rel_deviation=scale_max_rel_deviation,
        **consistency,
    )


def _overlap_return_consistency(
    *,
    relative: dict[str, float],
    reference: dict[str, float],
    overlap_dates: list[str],
    tolerance: float,
) -> dict[str, object]:
    """相邻重叠日期对的复权收益一致性：两源因子比之比应为 1。

    ``event pair`` 指 reference 因子在该日期对上发生跳变（除权除息事件），
    是验证 Choice 与 Tushare 除权比率是否一致的直接样本。
    """
    max_rel_diff: float | None = None
    breach_count = 0
    pair_count = 0
    event_pair_count = 0
    event_matched_count = 0
    for previous_date, current_date in zip(overlap_dates, overlap_dates[1:], strict=False):
        reference_ratio = reference[current_date] / reference[previous_date]
        relative_ratio = relative[current_date] / relative[previous_date]
        rel_diff = abs(relative_ratio / reference_ratio - 1.0)
        pair_count += 1
        if max_rel_diff is None or rel_diff > max_rel_diff:
            max_rel_diff = rel_diff
        if rel_diff > tolerance:
            breach_count += 1
        if abs(reference_ratio - 1.0) > tolerance:
            event_pair_count += 1
            if rel_diff <= tolerance:
                event_matched_count += 1
    return {
        "return_consistency_max_rel_diff": max_rel_diff,
        "return_consistency_breach_count": breach_count,
        "return_consistency_pair_count": pair_count,
        "overlap_event_pair_count": event_pair_count,
        "overlap_event_matched_count": event_matched_count,
    }


def _is_positive_finite(value: float | None) -> bool:
    return value is not None and math.isfinite(value) and value > 0
