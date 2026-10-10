"""从 market_data_livermore_service 拆出的轻量口径与转换工具。

门面模块逐名 re-export；行为与拆分前完全一致。
"""

from __future__ import annotations

from datetime import date

MAINBOARD_RISK_WARNING_LIMIT_RATIO_10_START = date(2026, 7, 6)


def _parse_optional_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(str(value))


def _latest_common_trade_date_pair(
    left_points: list[tuple[str, float]],
    right_points: list[tuple[str, float]],
) -> tuple[str, float, float] | None:
    """Return (trade_date, left_value, right_value) for the latest trade_date landed in both series.

    Guards against pairing a stale point from one series with a fresher point from the other
    (e.g. lagging PE with the latest CN10Y) when the two series' most recent landed dates differ.
    """
    right_by_date = {trade_date: value for trade_date, value in right_points}
    for trade_date, left_value in sorted(left_points, key=lambda row: row[0], reverse=True):
        if trade_date in right_by_date:
            return trade_date, left_value, right_by_date[trade_date]
    return None


def _rule_derived_limit_ratio(*, stock_code: str, stock_name: str, as_of_date: str) -> float | None:
    code = stock_code.strip().upper()
    if not code:
        return None
    if code.endswith(".BJ") or code.startswith(("8", "4", "920")):
        return 0.30
    if code.endswith(".SH") and code.startswith(("688", "689")):
        return 0.20
    if code.endswith(".SZ") and code.startswith(("300", "301")):
        return 0.20
    if _is_risk_warning_stock_name(stock_name) and _date_before(
        as_of_date, MAINBOARD_RISK_WARNING_LIMIT_RATIO_10_START
    ):
        return 0.05
    if code.endswith((".SH", ".SZ")):
        return 0.10
    return None


def _is_risk_warning_stock_name(stock_name: str) -> bool:
    normalized = stock_name.strip().upper()
    return normalized.startswith("*ST") or normalized.startswith("ST")


def _date_before(value: str, threshold: date) -> bool:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return parsed < threshold


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "t", "yes", "y", "是"}


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _quality_flag_for_market_gate(state: str) -> str:
    if state == "STALE":
        return "stale"
    if state in {"NO_DATA", "PENDING_DATA"}:
        return "warning"
    return "ok"


def _vendor_status_for_state(state: str) -> str:
    if state == "STALE":
        return "vendor_stale"
    if state == "NO_DATA":
        return "vendor_unavailable"
    return "ok"


def _aggregate_lineage(values: list[str], *, empty_value: str) -> str:
    distinct = sorted({value for value in values if value})
    if not distinct:
        return empty_value
    if len(distinct) == 1:
        return distinct[0]
    return "__".join(distinct)
