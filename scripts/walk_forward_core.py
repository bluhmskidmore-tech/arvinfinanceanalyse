"""Pure walk-forward窗口切割与统计逻辑（分析工具，不属于 core_finance 正式链路）。

本模块只做纯函数计算：窗口生成、执行历史切片、训练期净化(purge)、参数选择、
样本外聚合。不导入 duckdb、不导入回测引擎，便于在合成数据上做防泄漏断言。

防泄漏契约（`scripts/run_walk_forward_validation.py` 与 `tests/test_walk_forward_validation.py`
共同依赖）：

1. 验证窗只接收 ``valid_start <= signal_date <= valid_end`` 的执行行；
2. 训练窗只接收 ``train_start <= signal_date <= train_end`` 的执行行，且默认开启
   purge：要求该行 20d 退出日 ``<= train_end``，即选参时刻(=valid_start)其结果
   已完全实现，避免用"尚未兑现的训练期尾部"决定参数；
3. 窗口不得跨越强制切割点（两代数据边界）或数据空洞。
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

DEFAULT_FORCED_CUT_DATES: tuple[str, ...] = ("2026-01-05",)
DEFAULT_MAX_GAP_DAYS = 45
DEFAULT_MIN_WINDOWS_FOR_VERDICT = 3
DEFAULT_RISK_PER_TRADE_GRID: tuple[float, ...] = (0.0025, 0.005, 0.0075, 0.01)
SIGNAL_DATE_FIELD = "signal_date"
OUTCOME_DATE_FIELD = "exit_date_20d"
OUTCOME_RETURN_FIELD = "return_20d_net_adj"

VERDICT_INSUFFICIENT = "insufficient_windows"
VERDICT_SUPPORTED = "oos_supported"
VERDICT_WEAKENED = "oos_weakened"
VERDICT_INCONCLUSIVE = "oos_inconclusive"


class WalkForwardLeakageError(RuntimeError):
    """窗口越过段边界/强制切割点时抛出：宁可中断，也不出一份可能含跨代际取数的报告。"""


@dataclass(frozen=True)
class ScheduleConfig:
    """滚动窗口配置（按自然月对齐，便于与执行历史月度覆盖对照）。"""

    label: str
    train_months: int
    valid_months: int
    step_months: int

    def __post_init__(self) -> None:
        if self.train_months <= 0 or self.valid_months <= 0 or self.step_months <= 0:
            raise ValueError("train_months / valid_months / step_months must be positive")


@dataclass(frozen=True)
class Segment:
    """被强制切割点或数据空洞隔开的连续信号区间。"""

    segment_id: str
    start_date: str
    end_date: str
    signal_date_count: int
    start_reason: str


@dataclass(frozen=True)
class WalkForwardWindow:
    window_id: str
    segment_id: str
    train_start: str
    train_end: str
    valid_start: str
    valid_end: str
    valid_end_clamped: bool = False
    """验证末日是否被段实际边界夹短（窗口时长短于 valid_months，聚合口径需披露）。"""

    @property
    def selection_date(self) -> str:
        """参数选择时刻：验证窗第一天。此刻之后的任何信息都不得进入选参。"""
        return self.valid_start


@dataclass(frozen=True)
class ParameterSelection:
    status: str
    objective: str
    selected: float | None
    score: float | None
    scores: tuple[tuple[float, float | None], ...]


def to_date(value: object) -> date:
    return date.fromisoformat(str(value)[:10])


def date_text(value: object) -> str:
    return str(value or "")[:10]


def month_start(value: object) -> date:
    parsed = to_date(value)
    return date(parsed.year, parsed.month, 1)


def add_months(value: object, months: int) -> date:
    """自然月加法，结果落在目标月的 1 号。"""
    anchor = month_start(value)
    total = anchor.year * 12 + (anchor.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)


def month_key(value: object) -> str:
    parsed = to_date(value)
    return f"{parsed.year:04d}-{parsed.month:02d}"


def build_segments(
    signal_dates: Sequence[str],
    *,
    forced_cut_dates: Sequence[str] = DEFAULT_FORCED_CUT_DATES,
    max_gap_days: int = DEFAULT_MAX_GAP_DAYS,
) -> list[Segment]:
    """把观测到的信号日切成互不跨越强制边界/数据空洞的连续段。"""
    ordered = sorted({date_text(value) for value in signal_dates if date_text(value)})
    if not ordered:
        return []
    cuts = sorted({date_text(value) for value in forced_cut_dates if date_text(value)})

    groups: list[tuple[list[str], str]] = [([ordered[0]], "series_start")]
    for previous, current in zip(ordered, ordered[1:], strict=False):
        crossed_cuts = [cut for cut in cuts if previous < cut <= current]
        gap_days = (to_date(current) - to_date(previous)).days
        reasons: list[str] = [f"forced_cut:{cut}" for cut in crossed_cuts]
        if gap_days > max_gap_days:
            reasons.append(f"data_gap:{gap_days}d")
        if reasons:
            groups.append(([current], "+".join(reasons)))
        else:
            groups[-1][0].append(current)

    return [
        Segment(
            segment_id=f"S{index + 1}",
            start_date=dates[0],
            end_date=dates[-1],
            signal_date_count=len(dates),
            start_reason=reason,
        )
        for index, (dates, reason) in enumerate(groups)
    ]


def build_windows(
    signal_dates: Sequence[str],
    *,
    schedule: ScheduleConfig,
    forced_cut_dates: Sequence[str] = DEFAULT_FORCED_CUT_DATES,
    max_gap_days: int = DEFAULT_MAX_GAP_DAYS,
) -> tuple[list[WalkForwardWindow], list[Segment]]:
    """在每个 segment 内部独立生成滚动窗口，窗口不跨段。"""
    segments = build_segments(
        signal_dates,
        forced_cut_dates=forced_cut_dates,
        max_gap_days=max_gap_days,
    )
    cuts = sorted({date_text(value) for value in forced_cut_dates if date_text(value)})
    windows: list[WalkForwardWindow] = []
    previous_segment_end: str | None = None
    for index, segment in enumerate(segments):
        anchor = _segment_anchor_month(
            segment,
            cuts=cuts,
            previous_segment_end=previous_segment_end,
        )
        previous_segment_end = segment.end_date
        last_month = month_key(segment.end_date)
        next_segment = segments[index + 1] if index + 1 < len(segments) else None
        upper_bound = _segment_upper_bound(segment, cuts=cuts, next_segment=next_segment)
        step_index = 0
        while True:
            train_start = add_months(anchor, step_index * schedule.step_months)
            valid_start = add_months(train_start, schedule.train_months)
            valid_end_exclusive = add_months(valid_start, schedule.valid_months)
            train_end = valid_start - timedelta(days=1)
            valid_end = valid_end_exclusive - timedelta(days=1)
            step_index += 1
            if month_key(train_start) > last_month:
                break
            if month_key(valid_end) > last_month:
                break
            if upper_bound is not None and valid_start.isoformat() > upper_bound:
                break
            clamped = upper_bound is not None and valid_end.isoformat() > upper_bound
            windows.append(
                WalkForwardWindow(
                    window_id=f"{segment.segment_id}W{len(windows) + 1}",
                    segment_id=segment.segment_id,
                    train_start=train_start.isoformat(),
                    train_end=train_end.isoformat(),
                    valid_start=valid_start.isoformat(),
                    valid_end=upper_bound if clamped and upper_bound else valid_end.isoformat(),
                    valid_end_clamped=clamped,
                )
            )
    return windows, segments


def _segment_upper_bound(
    segment: Segment,
    *,
    cuts: Sequence[str],
    next_segment: Segment | None,
) -> str | None:
    """段的实际右边界：窗口的验证末日不得跨过它。

    段末信号日与强制切割点可能落在同一自然月（例：cut=2025-07-10、段末 7/9），
    此时仅用月粒度（`month_key(valid_end) <= last_month`）判断会放行 valid_end=7/31，
    验证切片就会吃进切割点之后、属于后段的行。因此这里夹住
    「下一个强制切割点的前一日」与「下一段首个信号日的前一日」，取更早者。

    注意不夹「本段最后一个信号日」：末段的 valid_end 落在最后信号日之后只是尾部截断
    （数据不存在，不会取到别段的行），把它夹短反而会缩短名义验证期、污染年化口径。
    """
    bounds: list[str] = []
    for cut in cuts:
        if cut > segment.start_date:
            bounds.append((to_date(cut) - timedelta(days=1)).isoformat())
    if next_segment is not None:
        bounds.append((to_date(next_segment.start_date) - timedelta(days=1)).isoformat())
    return min(bounds) if bounds else None


def _segment_anchor_month(
    segment: Segment,
    *,
    cuts: Sequence[str],
    previous_segment_end: str | None,
) -> date:
    """段内第一个训练窗的起锚月。

    默认对齐到段首信号日所在自然月，但该月起点不得回退到强制切割点之前，
    也不得回退到上一段的最后一个信号日——否则窗口会跨代际或跨段取数。
    """
    anchor = month_start(segment.start_date)
    while True:
        crosses_cut = any(anchor.isoformat() < cut <= segment.start_date for cut in cuts)
        reaches_previous = previous_segment_end is not None and anchor.isoformat() <= previous_segment_end
        if not crosses_cut and not reaches_previous:
            return anchor
        anchor = add_months(anchor, 1)


def window_crosses_dates(window: WalkForwardWindow, cut_dates: Sequence[str]) -> list[str]:
    """返回落在窗口内部（训练首日之后、验证末日之前）的强制切割点。"""
    return [
        cut
        for value in cut_dates
        if (cut := date_text(value)) and window.train_start < cut <= window.valid_end
    ]


def slice_rows_by_signal_date(
    rows: Sequence[Mapping[str, object]],
    start_date: str,
    end_date: str,
    *,
    signal_date_field: str = SIGNAL_DATE_FIELD,
) -> list[Mapping[str, object]]:
    """按 signal_date 闭区间切片，日期缺失的行一律排除。"""
    return [
        row
        for row in rows
        if (signal_date := date_text(row.get(signal_date_field)))
        and start_date <= signal_date <= end_date
    ]


def select_training_rows(
    rows: Sequence[Mapping[str, object]],
    window: WalkForwardWindow,
    *,
    purge: bool = True,
    signal_date_field: str = SIGNAL_DATE_FIELD,
    outcome_date_field: str = OUTCOME_DATE_FIELD,
) -> list[Mapping[str, object]]:
    """训练切片 + purge：只保留在选参时刻结果已完全兑现的行。

    purge=True 时要求 20d 退出日 <= train_end，否则该行的收益要到验证窗内才知道，
    用它选参等于把验证期信息前置到决策点。
    """
    sliced = slice_rows_by_signal_date(
        rows,
        window.train_start,
        window.train_end,
        signal_date_field=signal_date_field,
    )
    if not purge:
        return sliced
    return [
        row
        for row in sliced
        if (outcome_date := date_text(row.get(outcome_date_field)))
        and outcome_date <= window.train_end
    ]


def select_validation_rows(
    rows: Sequence[Mapping[str, object]],
    window: WalkForwardWindow,
    *,
    signal_date_field: str = SIGNAL_DATE_FIELD,
) -> list[Mapping[str, object]]:
    return slice_rows_by_signal_date(
        rows,
        window.valid_start,
        window.valid_end,
        signal_date_field=signal_date_field,
    )


def score_from_metrics(metrics: Mapping[str, object], *, objective: str) -> float | None:
    """训练窗打分：sharpe 直接取 daily_sharpe；calmar = cagr / max_drawdown。"""
    if objective == "sharpe":
        return _finite(metrics.get("daily_sharpe"))
    if objective == "calmar":
        cagr = _finite(metrics.get("cagr"))
        max_drawdown = _finite(metrics.get("max_drawdown"))
        if cagr is None or max_drawdown is None or max_drawdown <= 0:
            return None
        return cagr / max_drawdown
    raise ValueError(f"Unsupported objective: {objective}")


def select_parameter(
    scores: Mapping[float, float | None],
    *,
    objective: str,
) -> ParameterSelection:
    """取分数最高的参数；并列时取更小(更保守)的参数。"""
    ordered = tuple(sorted((float(key), value) for key, value in scores.items()))
    scored = [(key, value) for key, value in ordered if value is not None]
    if not ordered:
        return ParameterSelection("no_candidates", objective, None, None, ordered)
    if not scored:
        return ParameterSelection("no_valid_score", objective, None, None, ordered)
    best_score = max(value for _key, value in scored)
    best_key = min(key for key, value in scored if value == best_score)
    return ParameterSelection("selected", objective, best_key, best_score, ordered)


def chain_returns(returns: Sequence[float]) -> float:
    compounded = 1.0
    for value in returns:
        compounded *= 1.0 + float(value)
    return compounded - 1.0


def annualize_return(total_return: float, span_days: int) -> float | None:
    if span_days <= 0:
        return None
    growth = 1.0 + total_return
    if growth <= 0:
        return None
    return growth ** (365.0 / span_days) - 1.0


def span_days(start_date: str, end_date: str) -> int:
    return (to_date(end_date) - to_date(start_date)).days + 1


def sign_consistency(values: Sequence[float | None]) -> dict[str, object]:
    observed = [float(value) for value in values if value is not None]
    positive = sum(1 for value in observed if value > 0)
    negative = sum(1 for value in observed if value < 0)
    return {
        "observed_windows": len(observed),
        "positive_windows": positive,
        "negative_windows": negative,
        "zero_windows": len(observed) - positive - negative,
        "positive_ratio": round(positive / len(observed), 6) if observed else None,
    }


def parameter_drift(selected: Sequence[float | None]) -> dict[str, object]:
    observed = [value for value in selected if value is not None]
    if not observed:
        return {
            "observed_windows": 0,
            "distinct_values": 0,
            "mode_value": None,
            "mode_share": None,
            "switch_count": None,
            "switch_rate": None,
            "mean_abs_step": None,
        }
    counts: dict[float, int] = {}
    for value in observed:
        counts[value] = counts.get(value, 0) + 1
    mode_value = max(sorted(counts), key=lambda key: counts[key])
    steps = [
        abs(current - previous)
        for previous, current in zip(observed, observed[1:], strict=False)
    ]
    switches = sum(1 for step in steps if step > 0)
    return {
        "observed_windows": len(observed),
        "distinct_values": len(counts),
        "mode_value": mode_value,
        "mode_share": round(counts[mode_value] / len(observed), 6),
        "switch_count": switches,
        "switch_rate": round(switches / len(steps), 6) if steps else None,
        "mean_abs_step": round(sum(steps) / len(steps), 8) if steps else None,
    }


def decay_ratio(oos_value: float | None, is_value: float | None) -> dict[str, object]:
    """样本外/样本内比值。IS<=0 时比值无解释力，只给差值并标注状态。"""
    if oos_value is None or is_value is None:
        return {"ratio": None, "delta": None, "status": "unavailable"}
    delta = round(oos_value - is_value, 6)
    if is_value <= 0:
        return {"ratio": None, "delta": delta, "status": "is_non_positive"}
    return {"ratio": round(oos_value / is_value, 6), "delta": delta, "status": "ready"}


def oos_verdict(
    *,
    window_count: int,
    excess_values: Sequence[float | None],
    chain_excess: float | None,
    min_windows: int = DEFAULT_MIN_WINDOWS_FOR_VERDICT,
) -> tuple[str, str]:
    """基于窗数、逐窗超额符号一致率与链式超额给出结论，自由度不足直接判不可判。"""
    if window_count < min_windows:
        return (
            VERDICT_INSUFFICIENT,
            f"验证窗仅 {window_count} 个 (< {min_windows})，自由度不足，不下结论",
        )
    consistency = sign_consistency(excess_values)
    observed = int(consistency["observed_windows"] or 0)
    if observed < min_windows:
        return (
            VERDICT_INSUFFICIENT,
            f"可观测验证窗仅 {observed} 个 (< {min_windows})，自由度不足，不下结论",
        )
    positive_ratio = float(consistency["positive_ratio"] or 0.0)
    if chain_excess is None:
        return VERDICT_INCONCLUSIVE, "链式超额不可得"
    if positive_ratio >= 2 / 3 and chain_excess > 0:
        return (
            VERDICT_SUPPORTED,
            f"{consistency['positive_windows']}/{observed} 窗正超额且链式超额 {chain_excess:+.2%}",
        )
    if positive_ratio <= 1 / 3 or chain_excess < 0:
        return (
            VERDICT_WEAKENED,
            f"{consistency['positive_windows']}/{observed} 窗正超额，链式超额 {chain_excess:+.2%}",
        )
    return (
        VERDICT_INCONCLUSIVE,
        f"{consistency['positive_windows']}/{observed} 窗正超额，链式超额 {chain_excess:+.2%}，方向不稳定",
    )


def windows_are_disjoint(windows: Sequence[WalkForwardWindow]) -> bool:
    """验证窗是否互不重叠（step < valid 时会重叠，链式复利会重复计数）。"""
    ordered = sorted(windows, key=lambda window: window.valid_start)
    return all(
        previous.valid_end < current.valid_start
        for previous, current in zip(ordered, ordered[1:], strict=False)
    )


def schedule_diagram(
    windows: Sequence[WalkForwardWindow],
    segments: Sequence[Segment],
) -> list[str]:
    """按月渲染切割图示：T=训练月，V=验证月，.=段内未覆盖月。"""
    if not segments:
        return ["(no segments)"]
    lines: list[str] = []
    for segment in segments:
        months = _month_range(segment.start_date, segment.end_date)
        header = "".join(key[2:].replace("-", "") + " " for key in months)
        lines.append(f"{segment.segment_id} [{segment.start_date}..{segment.end_date}] ({segment.start_reason})")
        lines.append(f"{'months':>10}: {header}")
        segment_windows = [window for window in windows if window.segment_id == segment.segment_id]
        if not segment_windows:
            lines.append(f"{'(none)':>10}: 该段跨度不足，本切割下未生成任何窗口")
        for window in segment_windows:
            marks = []
            for key in months:
                if month_key(window.train_start) <= key <= month_key(window.train_end):
                    marks.append("T")
                elif month_key(window.valid_start) <= key <= month_key(window.valid_end):
                    marks.append("V")
                else:
                    marks.append(".")
            lines.append(f"{window.window_id:>10}: " + "".join(f"{mark:<5}" for mark in marks))
        lines.append("")
    return lines


def _month_range(start_date: str, end_date: str) -> list[str]:
    keys: list[str] = []
    cursor = month_start(start_date)
    last = month_start(end_date)
    while cursor <= last:
        keys.append(month_key(cursor))
        cursor = add_months(cursor, 1)
    return keys


def _finite(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
