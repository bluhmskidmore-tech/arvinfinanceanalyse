"""Executive dashboard 数值格式化与通用纯工具(自 executive_service.py 门面拆分,逐字迁移)。

本模块只包含无状态纯函数与不可变常量:数值/文本格式化、日期序列小工具、
lineage token 归一化。不读仓库、不读 settings、不写日志。
门面 executive_service.py 显式 re-import 全部名字以保持既有调用方与测试不变。
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from backend.app.schemas.common_numeric import Numeric
from backend.app.schemas.executive_dashboard import ExecutiveMetric

# Yuan → 亿 conversion factor; a single named constant avoids magic-number scatter.
_YUAN_PER_YI: float = 1e8
_BASIS_POINTS_PER_PERCENT: float = 100.0


def _normalize_report_date(report_date: str | None) -> str | None:
    if report_date is None:
        return None
    return date.fromisoformat(str(report_date).strip()).isoformat()


def _safe_report_year(report_date: str | None) -> int | None:
    if not report_date:
        return None
    try:
        return date.fromisoformat(str(report_date).strip()).year
    except ValueError:
        return None


def _single_effective_report_date(*report_dates: str | None) -> str | None:
    resolved = [str(value or "").strip() for value in report_dates]
    if not resolved or any(not value for value in resolved):
        return None
    first = resolved[0]
    return first if all(value == first for value in resolved) else None


def _fmt_yi_amount(value: float | None, *, signed: bool = False) -> Numeric:
    """Format a yuan-denominated amount into a Numeric in yi display.

    Retains the original signature to minimize churn at call sites (they just
    receive a Numeric instead of str now; ExecutiveMetric etc. accept both
    thanks to W2.1 coercion, but callers building Numerics directly bypass
    the coerce path).
    """
    if value is None:
        return Numeric(
            raw=None,
            unit="yuan",
            display="—" if signed else "0.00 亿",
            precision=2,
            sign_aware=signed,
        )
    v = float(value)
    yi = v / _YUAN_PER_YI
    if signed:
        sign = "+" if yi >= 0 else ""
        display = f"{sign}{yi:,.2f} 亿"
    else:
        display = f"{yi:,.2f} 亿"
    return Numeric(
        raw=v,
        unit="yuan",
        display=display,
        precision=2,
        sign_aware=signed,
    )


def _fmt_signed_segment_yi(yi: float) -> Numeric:
    sign = "+" if yi >= 0 else ""
    return Numeric(
        raw=float(yi) * _YUAN_PER_YI,
        unit="yuan",
        display=f"{sign}{yi:.2f} 亿",
        precision=2,
        sign_aware=True,
    )


def _fmt_signed_percent(value: float | None) -> Numeric:
    if value is None:
        return Numeric(raw=None, unit="pct", display="—", precision=2, sign_aware=True)
    sign = "+" if float(value) >= 0 else ""
    return Numeric(
        raw=float(value) / 100.0,  # raw 是 decimal ratio
        unit="pct",
        display=f"{sign}{float(value):.2f}%",
        precision=2,
        sign_aware=True,
    )


def _normalize_ratio_percent_input(value: float | None) -> float:
    """Treat input as decimal-ratio (e.g. 0.035 = 3.5%).

    Upstream callers (compute_liability_yield_metrics → weighted_rate) all
    return decimal ratios.  The previous heuristic threshold ``abs(v) >= 0.1``
    caused a 100× error for NIM values at or above 10 bp decimal (0.001).
    """
    if value is None:
        return 0.0
    return float(value)


def _fmt_signed_ratio_percent(value: float | None) -> Numeric:
    if value is None:
        return Numeric(raw=None, unit="pct", display="N/A", precision=2, sign_aware=True)
    ratio = _normalize_ratio_percent_input(value)
    sign = "+" if ratio >= 0 else ""
    return Numeric(
        raw=ratio,
        unit="pct",
        display=f"{sign}{ratio * 100.0:.2f}%",
        precision=2,
        sign_aware=True,
    )


def _previous_report_date(dates: list[str], current_report_date: str | None) -> str | None:
    if not current_report_date or not dates:
        return None
    if current_report_date in dates:
        idx = dates.index(current_report_date)
        if idx + 1 < len(dates):
            return dates[idx + 1]
    return None


def _lineage_tokens(*values: object) -> list[str]:
    tokens: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        for token in text.split("__"):
            for dirty_part in token.split(","):
                normalized = dirty_part.strip()
                if normalized:
                    tokens.add(normalized)
    return sorted(tokens)


def _lineage_tokens_from_rows(rows: list[dict[str, object]], field_name: str) -> list[str]:
    return _lineage_tokens(*(row.get(field_name) for row in rows))


def _lineage_tokens_from_payload(payload: dict[str, object], field_name: str) -> list[str]:
    return _lineage_tokens(payload.get(field_name))


def _lineage_tokens_from_state(state: dict[str, object], field_name: str) -> list[str]:
    value = state.get(field_name, [])
    if isinstance(value, (list, tuple, set)):
        return _lineage_tokens(*value)
    return _lineage_tokens(value)


def _state_has_lineage_tokens(state: dict[str, object]) -> bool:
    return bool(_lineage_tokens_from_state(state, "source_versions")) and bool(
        _lineage_tokens_from_state(state, "rule_versions")
    )


def _state_missing_required_lineage(state: dict[str, object]) -> bool:
    return bool(state.get("missing_lineage")) or not _state_has_lineage_tokens(state)


def _mapping_missing_required_lineage(row: dict[str, object] | None) -> bool:
    if row is None:
        return False
    return not (
        _lineage_tokens(row.get("source_version"))
        and _lineage_tokens(row.get("rule_version"))
    )


def _join_lineage_tokens(*values: object) -> str:
    return "__".join(_lineage_tokens(*values))


def _format_percent_change(current: float | None, previous: float | None) -> Numeric:
    if current is None or previous in (None, 0):
        return Numeric(raw=None, unit="pct", display="无环比", precision=2, sign_aware=True)
    change = ((float(current) - float(previous)) / float(previous)) * 100
    sign = "+" if change >= 0 else ""
    return Numeric(
        raw=change / 100.0,
        unit="pct",
        display=f"{sign}{change:.2f}%",
        precision=2,
        sign_aware=True,
    )


def _format_point_change(current: float | None, previous: float | None) -> Numeric:
    if current is None or previous is None:
        return Numeric(raw=None, unit="bp", display="无环比", precision=2, sign_aware=True)
    change = float(current) - float(previous)
    sign = "+" if change >= 0 else ""
    return Numeric(
        raw=change * 100.0,  # bp = percent point * 100
        unit="bp",
        display=f"{sign}{change:.2f}pp",
        precision=2,
        sign_aware=True,
    )


def _format_ratio_point_change(current: float | None, previous: float | None) -> Numeric:
    if current is None or previous is None:
        return Numeric(raw=None, unit="bp", display="N/A", precision=2, sign_aware=True)
    current_ratio = _normalize_ratio_percent_input(current)
    previous_ratio = _normalize_ratio_percent_input(previous)
    change_ratio = current_ratio - previous_ratio
    sign = "+" if change_ratio >= 0 else ""
    return Numeric(
        raw=change_ratio * 10000.0,
        unit="bp",
        display=f"{sign}{change_ratio * 100.0:.2f}pp",
        precision=2,
        sign_aware=True,
    )


def _unavailable_metric(
    *,
    metric_id: str,
    label: str,
    detail: str,
    delta: str = "未接入",
    tone: Literal["positive", "neutral", "warning", "negative"] = "warning",
) -> ExecutiveMetric:
    return ExecutiveMetric(
        id=metric_id,
        label=label,
        value=Numeric(raw=None, unit="yuan", display="—", precision=2, sign_aware=False),
        delta=Numeric(raw=None, unit="pct", display=delta, precision=2, sign_aware=True),
        tone=tone,
        detail=detail,
    )


def _tone_for_signed(yi: float) -> str:
    if yi > 0:
        return "positive"
    if yi < 0:
        return "negative"
    return "neutral"


def _history_date_slice(
    report_dates: list[str],
    current_report_date: str | None,
    n: int,
) -> list[str] | None:
    if not report_dates:
        return None
    if current_report_date is None:
        return report_dates[:n]
    try:
        idx = report_dates.index(current_report_date)
    except ValueError:
        return None
    return report_dates[idx : idx + n]
