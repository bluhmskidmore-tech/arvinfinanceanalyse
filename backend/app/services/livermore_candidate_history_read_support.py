"""Livermore 候选历史：DuckDB 只读取数与前向覆盖/成熟度推导辅助。

从 livermore_candidate_history_service 门面按行为等价逐字拆出：仓库连接、
窗口行/执行行/基线行加载与规范化、观察日历读取、前向覆盖与前向成熟度
推导、日期解析辅助、基准与组合收盘价读取。本模块不得导入门面模块。
"""

from __future__ import annotations

import duckdb
import math
from bisect import bisect_right
from datetime import date
from typing import Any
from backend.app.core_finance.field_normalization import is_tradestatus_tradable
from backend.app.core_finance.matched_baseline import MATCHED_BASELINE_TABLE
from backend.app.repositories.livermore_candidate_history_repo import (
    CANDIDATE_EXECUTION_SELECT_COLUMNS,
    CANDIDATE_HISTORY_SELECT_COLUMNS,
    LivermoreCandidateHistoryRepository,
    MATCHED_BASELINE_SELECT_COLUMNS,
    RELATION_CHOICE_MARKET_SNAPSHOT,
    RELATION_CHOICE_STOCK_DAILY_OBSERVATION,
    RELATION_FACT_CHOICE_MACRO_DAILY,
    RELATION_LIVERMORE_CANDIDATE_EXECUTION_HISTORY,
    RELATION_LIVERMORE_CANDIDATE_HISTORY,
)


TABLE_HIST = RELATION_LIVERMORE_CANDIDATE_HISTORY

TABLE_EXECUTION_HIST = RELATION_LIVERMORE_CANDIDATE_EXECUTION_HISTORY

TABLE_OBS = RELATION_CHOICE_STOCK_DAILY_OBSERVATION

BENCHMARK_SERIES_ID = "CA.CSI300"

TABLE_BENCHMARK_DAILY = RELATION_FACT_CHOICE_MACRO_DAILY

TABLE_BENCHMARK_SNAPSHOT = RELATION_CHOICE_MARKET_SNAPSHOT

_COMPLETION_HORIZONS = ("return_1d", "return_5d", "return_20d")

_FORWARD_COVERAGE_COMPLETE = "complete"

_FORWARD_COVERAGE_PENDING = "pending"

_FORWARD_COVERAGE_MISSING_BAR = "missing_bar"

_FORWARD_COVERAGE_PARTIAL_HALT = "partial_halt"

_FORWARD_COVERAGE_STATUSES = (
    _FORWARD_COVERAGE_COMPLETE,
    _FORWARD_COVERAGE_PENDING,
    _FORWARD_COVERAGE_MISSING_BAR,
    _FORWARD_COVERAGE_PARTIAL_HALT,
)

_FORWARD_COVERAGE_MATURITY_FORWARD_BARS = 20

_FORWARD_MATURITY_HORIZONS = {"1d": 1, "5d": 5, "10d": 10, "20d": 20}

_FORWARD_MATURITY_STATUSES = (
    "natural_pending",
    "complete",
    "matured_missing_bar",
    "raw_matured_adjustment_missing",
    "partial_halt",
)

_FORWARD_RETURN_KEYS = ("return_1d", "return_5d", "return_10d", "return_20d")

_SELECT_COLUMNS = CANDIDATE_HISTORY_SELECT_COLUMNS

_EXECUTION_SELECT_COLUMNS = CANDIDATE_EXECUTION_SELECT_COLUMNS

_MATCHED_BASELINE_SELECT_COLUMNS = MATCHED_BASELINE_SELECT_COLUMNS

def _candidate_history_repository_for_connection() -> LivermoreCandidateHistoryRepository:
    """Build a repository facade for an already-open read-only connection."""
    return LivermoreCandidateHistoryRepository("")

def _available_columns(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return _candidate_history_repository_for_connection().table_columns(TABLE_HIST, conn=conn)

def _available_execution_columns(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return _candidate_history_repository_for_connection().table_columns(TABLE_EXECUTION_HIST, conn=conn)

def _available_matched_baseline_columns(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return _candidate_history_repository_for_connection().table_columns(MATCHED_BASELINE_TABLE, conn=conn)

def _select_list(available_columns: set[str]) -> str:
    return LivermoreCandidateHistoryRepository.select_list(available_columns)

def _execution_select_list(available_columns: set[str]) -> str:
    return LivermoreCandidateHistoryRepository.execution_select_list(available_columns)

def _matched_baseline_select_list(available_columns: set[str]) -> str:
    return LivermoreCandidateHistoryRepository.matched_baseline_select_list(available_columns)

def _load_execution_window_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str | None,
    snapshot_from: str | None,
    snapshot_to: str | None,
) -> list[dict[str, Any]]:
    repository = _candidate_history_repository_for_connection()
    available_columns = _available_execution_columns(conn)
    rows = repository.fetch_execution_window_rows(
        stock_code=stock_code,
        snapshot_from=snapshot_from,
        snapshot_to=snapshot_to,
        available_columns=available_columns,
        conn=conn,
    )
    return [_normalize_execution_row(row) for row in rows]

def _load_matched_baseline_window_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str | None,
    snapshot_from: str | None,
    snapshot_to: str | None,
) -> list[dict[str, Any]]:
    repository = _candidate_history_repository_for_connection()
    available_columns = _available_matched_baseline_columns(conn)
    rows = repository.fetch_matched_baseline_window_rows(
        stock_code=stock_code,
        snapshot_from=snapshot_from,
        snapshot_to=snapshot_to,
        available_columns=available_columns,
        conn=conn,
    )
    return [_normalize_matched_baseline_row(row) for row in rows]

def _normalize_row(row: tuple[Any, ...]) -> dict[str, Any]:
    item = {_SELECT_COLUMNS[i]: row[i] for i in range(len(_SELECT_COLUMNS))}
    if not str(item.get("signal_kind") or "").strip():
        item["signal_kind"] = "stock_candidate"
    return item

def _normalize_execution_row(row: tuple[Any, ...]) -> dict[str, Any]:
    item = {_EXECUTION_SELECT_COLUMNS[i]: row[i] for i in range(len(_EXECUTION_SELECT_COLUMNS))}
    if not str(item.get("signal_kind") or "").strip():
        item["signal_kind"] = "stock_candidate"
    return item

def _normalize_matched_baseline_row(row: tuple[Any, ...]) -> dict[str, Any]:
    item = {_MATCHED_BASELINE_SELECT_COLUMNS[i]: row[i] for i in range(len(_MATCHED_BASELINE_SELECT_COLUMNS))}
    if not str(item.get("signal_kind") or "").strip():
        item["signal_kind"] = "stock_candidate"
    return item

def _min_snapshot_date(items: list[dict[str, Any]]) -> str | None:
    dates = [text for item in items if (text := str(item.get("snapshot_as_of_date") or "").strip()[:10])]
    return min(dates) if dates else None

def _annotate_forward_coverage(
    items: list[dict[str, Any]],
    *,
    observation_trade_dates: list[str],
) -> list[dict[str, Any]]:
    for item in items:
        item["forward_coverage"] = _derive_forward_coverage(
            item,
            observation_trade_dates=observation_trade_dates,
        )
    return items

def _derive_forward_coverage(
    item: dict[str, Any],
    *,
    observation_trade_dates: list[str],
) -> str:
    """Read-time refinement of data_status: split 'pending' into pending vs missing_bar.

    A pending row becomes missing_bar when the observation calendar already provides at least
    _FORWARD_COVERAGE_MATURITY_FORWARD_BARS trade dates after the row's snapshot date, yet
    forward returns are still absent: the forward window has matured, so the missing bars point
    to a delisting / unresumed halt / ingestion gap rather than an immature window. The stored
    data_status vocabulary is never rewritten; this marker is derived per read.
    """
    status = str(item.get("data_status") or "").strip()
    if status and status != _FORWARD_COVERAGE_PENDING:
        return status
    if not status and all(item.get(horizon) is not None for horizon in _COMPLETION_HORIZONS):
        return _FORWARD_COVERAGE_COMPLETE
    if not any(item.get(key) is None for key in _FORWARD_RETURN_KEYS):
        return _FORWARD_COVERAGE_PENDING
    snapshot_date = str(item.get("snapshot_as_of_date") or "").strip()[:10]
    if not snapshot_date or not observation_trade_dates:
        return _FORWARD_COVERAGE_PENDING
    forward_bar_count = len(observation_trade_dates) - bisect_right(observation_trade_dates, snapshot_date)
    if forward_bar_count >= _FORWARD_COVERAGE_MATURITY_FORWARD_BARS:
        return _FORWARD_COVERAGE_MISSING_BAR
    return _FORWARD_COVERAGE_PENDING

def _forward_coverage_of(item: dict[str, Any]) -> str:
    value = str(item.get("forward_coverage") or "").strip()
    if value:
        return value
    return _derive_forward_coverage(item, observation_trade_dates=[])

def _forward_coverage_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in _FORWARD_COVERAGE_STATUSES}
    for item in items:
        key = _forward_coverage_of(item)
        counts[key] = counts.get(key, 0) + 1
    return counts

def _missing_bar_count(items: list[dict[str, Any]]) -> int:
    return sum(1 for item in items if _forward_coverage_of(item) == _FORWARD_COVERAGE_MISSING_BAR)

def _forward_coverage_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = _forward_coverage_counts(items)
    return {
        "row_count": len(items),
        "counts": counts,
        "missing_bar_row_count": counts[_FORWARD_COVERAGE_MISSING_BAR],
        "maturity_forward_bars": _FORWARD_COVERAGE_MATURITY_FORWARD_BARS,
        "maturity_reference": f"distinct forward trade dates in {TABLE_OBS}",
    }

def _annotate_forward_maturity(
    conn: duckdb.DuckDBPyConnection,
    *,
    items: list[dict[str, Any]],
    tables: set[str],
    evaluation_as_of_date: str,
    rewrite_legacy_status: bool,
) -> list[dict[str, Any]]:
    stock_observations, market_dates, source_issue = _load_forward_maturity_observations(
        conn,
        tables=tables,
        min_snapshot_date=_min_snapshot_date(items),
        evaluation_as_of_date=evaluation_as_of_date,
        stock_codes={str(item.get("stock_code") or "").strip().upper() for item in items},
    )
    for item in items:
        maturity = _derive_forward_maturity(
            item,
            stock_observations=stock_observations,
            market_dates=market_dates,
            evaluation_as_of_date=evaluation_as_of_date,
            source_issue=source_issue,
        )
        item["forward_maturity"] = maturity
        _mask_unverified_forward_outcomes(
            item,
            maturity=maturity,
            rewrite_legacy_status=rewrite_legacy_status,
        )
    return items

def _mask_unverified_forward_outcomes(
    item: dict[str, Any],
    *,
    maturity: dict[str, Any],
    rewrite_legacy_status: bool,
) -> None:
    raw_horizons = maturity.get("horizons")
    horizons = raw_horizons if isinstance(raw_horizons, dict) else {}
    statuses: dict[str, str] = {}
    for horizon in _FORWARD_MATURITY_HORIZONS:
        raw_horizon = horizons.get(horizon)
        horizon_item = raw_horizon if isinstance(raw_horizon, dict) else {}
        status = str(horizon_item.get("status") or "natural_pending")
        statuses[horizon] = status
        target_verified = bool(horizon_item.get("target_observation_verified"))
        raw_return = _maturity_finite_float(item.get(f"return_{horizon}"))
        adjusted_return = _maturity_finite_float(item.get(f"return_{horizon}_adj"))
        if not target_verified:
            item[f"forward_trade_date_{horizon}"] = None
            item[f"return_{horizon}"] = None
            item[f"return_{horizon}_adj"] = None
        elif raw_return is None:
            item[f"return_{horizon}"] = None
            item[f"return_{horizon}_adj"] = None
        elif adjusted_return is None:
            item[f"return_{horizon}"] = raw_return
            item[f"return_{horizon}_adj"] = None
        else:
            item[f"return_{horizon}"] = raw_return
            item[f"return_{horizon}_adj"] = adjusted_return

    if not rewrite_legacy_status:
        stored_status = str(item.get("data_status") or "").strip()
        item["forward_coverage"] = (
            stored_status if stored_status in _FORWARD_COVERAGE_STATUSES else _FORWARD_COVERAGE_PENDING
        )
        return

    if statuses and all(status == "complete" for status in statuses.values()):
        item["data_status"] = "complete"
    elif "partial_halt" in statuses.values():
        item["data_status"] = "partial_halt"
    else:
        item["data_status"] = "pending"

    long_status = statuses.get("20d", "natural_pending")
    item["forward_coverage"] = {
        "complete": _FORWARD_COVERAGE_COMPLETE,
        "matured_missing_bar": _FORWARD_COVERAGE_MISSING_BAR,
        "partial_halt": _FORWARD_COVERAGE_PARTIAL_HALT,
    }.get(long_status, _FORWARD_COVERAGE_PENDING)

def _load_forward_maturity_observations(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    min_snapshot_date: str | None,
    evaluation_as_of_date: str,
    stock_codes: set[str],
) -> tuple[dict[str, dict[str, dict[str, Any]]], list[str], str | None]:
    stock_codes = {code for code in stock_codes if code}
    if TABLE_OBS not in tables:
        return {}, [], "observation_table_missing"
    repository = _candidate_history_repository_for_connection()
    columns = repository.table_columns(TABLE_OBS, conn=conn)
    missing_columns = sorted({"trade_date", "stock_code", "close_value"} - columns)
    if missing_columns:
        return {}, [], f"observation_required_columns_missing:{','.join(missing_columns)}"
    if not min_snapshot_date or not stock_codes:
        return {}, [], None
    has_trade_status = "tradestatus" in columns
    rows, market_rows = repository.fetch_forward_maturity_observation_rows(
        min_snapshot_date=min_snapshot_date,
        evaluation_as_of_date=evaluation_as_of_date,
        stock_codes=stock_codes,
        has_trade_status=has_trade_status,
        conn=conn,
    )
    observations: dict[str, dict[str, dict[str, Any]]] = {}
    market_dates = {
        normalized
        for row in market_rows
        if (normalized := _safe_optional_date(str(row[0] or "")))
    }
    for trade_date_raw, stock_code_raw, close_raw, trade_status_raw in rows:
        trade_date = _safe_optional_date(str(trade_date_raw or ""))
        stock_code = str(stock_code_raw or "").strip().upper()
        close_value = _maturity_positive_float(close_raw)
        if not trade_date or not stock_code:
            continue
        trade_status = str(trade_status_raw or "").strip()
        valid_close = close_value is not None and (
            not has_trade_status or is_tradestatus_tradable(trade_status)
        )
        observations.setdefault(stock_code, {})[trade_date] = {
            "close": close_value,
            "trade_status": trade_status,
            "valid_close": valid_close,
        }
    return observations, sorted(market_dates), None

def _derive_forward_maturity(
    item: dict[str, Any],
    *,
    stock_observations: dict[str, dict[str, dict[str, Any]]],
    market_dates: list[str],
    evaluation_as_of_date: str,
    source_issue: str | None = None,
) -> dict[str, Any]:
    if source_issue:
        return {
            "evaluation_as_of_date": evaluation_as_of_date,
            "horizons": {
                horizon: {
                    "status": "matured_missing_bar",
                    "reason": "observation_source_unavailable",
                    "horizon_bars": bar_count,
                    "target_trade_date": None,
                    "stock_valid_bar_count": 0,
                    "market_trade_date_count": 0,
                    "target_observation_verified": False,
                }
                for horizon, bar_count in _FORWARD_MATURITY_HORIZONS.items()
            },
            "maturity_clock": "individual_stock_valid_close_bars",
            "diagnostic_clock": "market_trade_dates",
            "source_status": "unavailable",
            "source_issue": source_issue,
            "classification_available": False,
        }
    snapshot_date = _safe_optional_date(str(item.get("snapshot_as_of_date") or ""))
    stock_code = str(item.get("stock_code") or "").strip().upper()
    stock_rows = stock_observations.get(stock_code, {})
    valid_dates = [
        trade_date
        for trade_date, row in sorted(stock_rows.items())
        if snapshot_date
        and snapshot_date < trade_date <= evaluation_as_of_date
        and bool(row.get("valid_close"))
    ]
    market_after_snapshot = [
        trade_date
        for trade_date in market_dates
        if snapshot_date and snapshot_date < trade_date <= evaluation_as_of_date
    ]
    explicit_halt = any(
        snapshot_date
        and snapshot_date < trade_date <= evaluation_as_of_date
        and not is_tradestatus_tradable(row.get("trade_status"))
        for trade_date, row in stock_rows.items()
    )
    horizons: dict[str, dict[str, Any]] = {}
    for horizon, bar_count in _FORWARD_MATURITY_HORIZONS.items():
        expected_target_date = valid_dates[bar_count - 1] if len(valid_dates) >= bar_count else None
        stored_target_date = _safe_optional_date(str(item.get(f"forward_trade_date_{horizon}") or ""))
        target_is_actual = bool(
            stored_target_date
            and stored_target_date <= evaluation_as_of_date
            and stored_target_date == expected_target_date
        )
        raw_return = _maturity_finite_float(item.get(f"return_{horizon}"))
        adjusted_return = _maturity_finite_float(item.get(f"return_{horizon}_adj"))
        if target_is_actual and raw_return is not None:
            status = "complete" if adjusted_return is not None else "raw_matured_adjustment_missing"
        elif len(market_after_snapshot) < bar_count:
            status = "natural_pending"
        elif explicit_halt and len(valid_dates) < bar_count:
            status = "partial_halt"
        else:
            status = "matured_missing_bar"
        horizons[horizon] = {
            "status": status,
            "horizon_bars": bar_count,
            "target_trade_date": stored_target_date if target_is_actual else None,
            "stock_valid_bar_count": len(valid_dates),
            "market_trade_date_count": len(market_after_snapshot),
            "target_observation_verified": target_is_actual,
        }
    return {
        "evaluation_as_of_date": evaluation_as_of_date,
        "horizons": horizons,
        "maturity_clock": "individual_stock_valid_close_bars",
        "diagnostic_clock": "market_trade_dates",
        "source_status": "available",
        "classification_available": True,
    }

def _forward_maturity_summary(
    items: list[dict[str, Any]],
    *,
    evaluation_as_of_date: str,
) -> dict[str, Any]:
    source_issues = sorted(
        {
            str(maturity.get("source_issue"))
            for item in items
            if isinstance((maturity := item.get("forward_maturity")), dict)
            and maturity.get("classification_available") is False
            and maturity.get("source_issue")
        }
    )
    classification_available = not source_issues
    horizons: dict[str, dict[str, Any]] = {}
    for horizon, bar_count in _FORWARD_MATURITY_HORIZONS.items():
        counts = {status: 0 for status in _FORWARD_MATURITY_STATUSES}
        mature_dates: list[str] = []
        pending_dates: list[str] = []
        for item in items:
            maturity = item.get("forward_maturity")
            maturity_horizons = maturity.get("horizons") if isinstance(maturity, dict) else None
            horizon_item = maturity_horizons.get(horizon) if isinstance(maturity_horizons, dict) else None
            status = str(horizon_item.get("status") if isinstance(horizon_item, dict) else "natural_pending")
            if status not in counts:
                status = "matured_missing_bar"
            counts[status] += 1
            snapshot_date = str(item.get("snapshot_as_of_date") or "")[:10]
            if status == "natural_pending":
                pending_dates.append(snapshot_date)
            else:
                mature_dates.append(snapshot_date)
        horizons[horizon] = {
            "horizon_bars": bar_count,
            "row_count": len(items),
            "counts": counts,
            "window_matured_row_count": len(items) - counts["natural_pending"],
            "natural_pending_row_count": counts["natural_pending"],
            "latest_mature_snapshot_date": max(mature_dates) if mature_dates else None,
            "latest_pending_snapshot_date": max(pending_dates) if pending_dates else None,
            "counts_authoritative": classification_available,
        }
    return {
        "scope": "returned_slice",
        "row_count": len(items),
        "evaluation_as_of_date": evaluation_as_of_date,
        "horizons": horizons,
        "maturity_clock": "individual_stock_valid_close_bars",
        "diagnostic_clock": "market_trade_dates",
        "source_status": "available" if classification_available else "unavailable",
        "classification_available": classification_available,
        "counts_authoritative": classification_available,
        **({"source_issue": source_issues[0]} if source_issues else {}),
    }

def _all_filtered_forward_maturity_summary(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    available_columns: set[str],
    sql_where: str,
    filter_bindings: list[object],
    evaluation_as_of_date: str,
) -> dict[str, Any]:
    repository = _candidate_history_repository_for_connection()
    observation_columns = _table_columns_for_service(conn, TABLE_OBS) if TABLE_OBS in tables else set()
    required_observation_columns = {"trade_date", "stock_code", "close_value"}
    if not required_observation_columns.issubset(observation_columns):
        row = repository.fetch_filtered_maturity_overview(
            available_columns=available_columns,
            sql_where=sql_where,
            filter_bindings=filter_bindings,
            conn=conn,
        )
        row_count = int(row[0] or 0) if row else 0
        latest_snapshot = _safe_optional_date(str(row[1] if row else ""))
        missing_observation_columns = sorted(required_observation_columns - observation_columns)
        source_issue = (
            "observation_table_missing"
            if TABLE_OBS not in tables
            else f"observation_required_columns_missing:{','.join(missing_observation_columns)}"
        )
        return _empty_all_filtered_maturity_summary(
            row_count=row_count,
            latest_snapshot_date=latest_snapshot,
            evaluation_as_of_date=evaluation_as_of_date,
            source_issue=source_issue,
        )

    rows = repository.fetch_all_filtered_maturity_rows(
        available_columns=available_columns,
        observation_columns=observation_columns,
        sql_where=sql_where,
        filter_bindings=filter_bindings,
        evaluation_as_of_date=evaluation_as_of_date,
        conn=conn,
    )
    return _all_filtered_summary_from_rows(rows, evaluation_as_of_date=evaluation_as_of_date)

def _all_filtered_summary_from_rows(
    rows: list[tuple[Any, ...]],
    *,
    evaluation_as_of_date: str,
) -> dict[str, Any]:
    horizons: dict[str, dict[str, Any]] = {}
    row_count = 0
    for horizon, bar_count in _FORWARD_MATURITY_HORIZONS.items():
        counts = {status: 0 for status in _FORWARD_MATURITY_STATUSES}
        latest_mature: str | None = None
        latest_pending: str | None = None
        for raw_horizon, raw_status, raw_count, raw_latest in rows:
            if str(raw_horizon) != horizon:
                continue
            status = str(raw_status)
            count = int(raw_count or 0)
            counts[status] = count
            latest = _safe_optional_date(str(raw_latest or ""))
            if status == "natural_pending":
                latest_pending = max(filter(None, [latest_pending, latest]), default=None)
            else:
                latest_mature = max(filter(None, [latest_mature, latest]), default=None)
        horizon_row_count = sum(counts.values())
        row_count = max(row_count, horizon_row_count)
        horizons[horizon] = {
            "horizon_bars": bar_count,
            "row_count": horizon_row_count,
            "counts": counts,
            "window_matured_row_count": horizon_row_count - counts["natural_pending"],
            "natural_pending_row_count": counts["natural_pending"],
            "latest_mature_snapshot_date": latest_mature,
            "latest_pending_snapshot_date": latest_pending,
            "counts_authoritative": True,
        }
    return {
        "scope": "all_filtered",
        "row_count": row_count,
        "evaluation_as_of_date": evaluation_as_of_date,
        "horizons": horizons,
        "maturity_clock": "individual_stock_valid_close_bars",
        "diagnostic_clock": "market_trade_dates",
        "source_status": "available",
        "classification_available": True,
        "counts_authoritative": True,
    }

def _empty_all_filtered_maturity_summary(
    *,
    row_count: int,
    latest_snapshot_date: str | None,
    evaluation_as_of_date: str,
    source_issue: str,
) -> dict[str, Any]:
    rows = [
        (horizon, "matured_missing_bar", row_count, latest_snapshot_date)
        for horizon in _FORWARD_MATURITY_HORIZONS
    ]
    summary = _all_filtered_summary_from_rows(rows, evaluation_as_of_date=evaluation_as_of_date)
    for horizon in summary["horizons"].values():
        horizon["counts_authoritative"] = False
    summary.update(
        {
            "source_status": "unavailable",
            "source_issue": source_issue,
            "classification_available": False,
            "counts_authoritative": False,
        }
    )
    return summary

def _table_columns_for_service(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    return _candidate_history_repository_for_connection().table_columns(table_name, conn=conn)

def _resolve_evaluation_as_of_date(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    requested_evaluation_as_of_date: str | None,
    fallback_date: str | None,
) -> str:
    if requested_evaluation_as_of_date:
        return requested_evaluation_as_of_date
    if TABLE_OBS in tables:
        repository = _candidate_history_repository_for_connection()
        columns = repository.table_columns(TABLE_OBS, conn=conn)
        if "trade_date" in columns:
            today = date.today().isoformat()
            latest_trade_date = repository.latest_observation_trade_date(
                on_or_before=today,
                conn=conn,
            )
            resolved = _safe_optional_date(str(latest_trade_date or ""))
            if resolved:
                return resolved
    return _safe_optional_date(fallback_date) or date.today().isoformat()

def _strict_optional_date(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return date.fromisoformat(text[:10]).isoformat()

def _safe_optional_date(value: str | None) -> str | None:
    try:
        return _strict_optional_date(value)
    except ValueError:
        return None

def _maturity_finite_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None

def _maturity_positive_float(value: Any) -> float | None:
    number = _maturity_finite_float(value)
    return number if number is not None and number > 0 else None

def _resolve_replay_trade_dates(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    snapshot_from: str | None,
    snapshot_to: str | None,
    row_dates: list[str],
) -> list[str]:
    if TABLE_OBS not in tables:
        return row_dates
    if not snapshot_from and not snapshot_to:
        return row_dates

    rows = _candidate_history_repository_for_connection().fetch_replay_trade_dates(
        snapshot_from=snapshot_from,
        snapshot_to=snapshot_to,
        conn=conn,
    )
    observed = [
        str(row[0])[:10]
        for row in rows
        if str(row[0] or "").strip()
    ]
    return observed or row_dates

def _load_candidate_history_portfolio_close_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    rebalances: list[dict[str, Any]],
    snapshot_to: str | None,
    has_adjustment_factor: bool | None = None,
) -> list[dict[str, Any]]:
    stock_codes = sorted(
        {
            str(item.get("stock_code") or "").strip()
            for rebalance in rebalances
            for item in rebalance["items"]
            if str(item.get("stock_code") or "").strip()
        }
    )
    if not rebalances or not stock_codes:
        return []
    if has_adjustment_factor is None:
        has_adjustment_factor = _candidate_history_portfolio_has_adjustment_factor(conn)
    start_date = str(rebalances[0]["date"])
    rows = _candidate_history_repository_for_connection().fetch_portfolio_close_rows(
        stock_codes=stock_codes,
        start_date=start_date,
        snapshot_to=snapshot_to,
        has_adjustment_factor=has_adjustment_factor,
        conn=conn,
    )
    return [
        {
            "trade_date": str(trade_date)[:10],
            "stock_code": str(stock_code),
            "close_value": float(close_value),
            "adj_close_value": float(adj_close_value) if adj_close_value is not None else None,
            "adj_factor": float(adj_factor) if adj_factor is not None else None,
        }
        for trade_date, stock_code, close_value, adj_close_value, adj_factor in rows
        if close_value is not None
    ]

def _candidate_history_portfolio_has_adjustment_factor(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str] | None = None,
) -> bool:
    return _candidate_history_repository_for_connection().has_adjustment_factor(
        tables=tables,
        conn=conn,
    )

def _load_benchmark_rows_for_nav_series(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    nav_series: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    if not nav_series:
        return [], []
    start_date = str(nav_series[0]["date"])[:10]
    end_date = str(nav_series[-1].get("exit_date") or nav_series[-1]["date"])[:10]
    return _load_benchmark_rows(conn, tables=tables, start_date=start_date, end_date=end_date)

def _load_benchmark_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    start_date: str,
    end_date: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    by_date: dict[str, dict[str, Any]] = {}
    tables_used: list[str] = []
    for table in (TABLE_BENCHMARK_SNAPSHOT, TABLE_BENCHMARK_DAILY):
        if table not in tables:
            continue
        rows = _candidate_history_repository_for_connection().fetch_benchmark_rows(
            table_name=table,
            series_id=BENCHMARK_SERIES_ID,
            start_date=start_date,
            end_date=end_date,
            conn=conn,
        )
        if not rows:
            continue
        tables_used.append(table)
        for trade_date, value in rows:
            if value is None:
                continue
            by_date[str(trade_date)[:10]] = {
                "trade_date": str(trade_date)[:10],
                "value": float(value),
            }
    return [by_date[key] for key in sorted(by_date)], sorted(tables_used, key=_benchmark_table_sort_key)

def _benchmark_table_sort_key(table: str) -> int:
    return (TABLE_BENCHMARK_DAILY, TABLE_BENCHMARK_SNAPSHOT).index(table)

def _normalize_date_text(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text[:10]

def _latest_history_snapshot_date(conn: duckdb.DuckDBPyConnection) -> str | None:
    value = _candidate_history_repository_for_connection().latest_history_snapshot_date(conn=conn)
    return _normalize_date_text(value)
