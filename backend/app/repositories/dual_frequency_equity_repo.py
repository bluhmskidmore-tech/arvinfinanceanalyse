from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb
from backend.app.repositories.choice_stock_units import amount_rmb_sql, scale_unknown_sql

INDEX_TABLE = "fact_choice_macro_daily"
MARKET_AMOUNT_TABLE = "choice_stock_daily_observation"
INDEX_SERIES_ID = "CA.CSI300"
DEFAULT_LOOKBACK_ROWS = 260
MAX_LOOKBACK_ROWS = 520
DATE_BASIS = "CA.CSI300_trade_date_lte_requested_as_of_date"

_INDEX_REQUIRED_COLUMNS = frozenset({"series_id", "trade_date", "value_numeric"})
_INDEX_EVIDENCE_COLUMNS = (
    "source_version",
    "vendor_version",
    "rule_version",
    "quality_flag",
    "run_id",
)
_MARKET_AMOUNT_REQUIRED_COLUMNS = frozenset({"trade_date", "stock_code", "amount"})
_MARKET_AMOUNT_EVIDENCE_COLUMNS = (
    "source_version",
    "vendor_version",
    "rule_version",
    "run_id",
)
_ACCEPTED_QUALITY_FLAGS = frozenset({"ok", "ready", "complete", "good", "pass", "valid"})


def load_dual_frequency_equity_history(
    *,
    duckdb_path: str | Path,
    as_of_date: date | str | None = None,
    lookback_rows: int = DEFAULT_LOOKBACK_ROWS,
) -> dict[str, Any]:
    """Load the bounded, read-only history needed by the dual-frequency equity signal.

    The CSI300 observation dates are the left-side trading calendar. Market-wide
    amount is aggregated only for those dates. Missing amount is represented as
    ``None`` rather than zero so downstream calculations cannot silently treat a
    data gap as a dry-liquidity signal.
    """

    requested_as_of = _normalize_as_of_date(as_of_date)
    requested_lookback = _normalize_lookback_rows(lookback_rows)
    effective_lookback = min(requested_lookback, MAX_LOOKBACK_ROWS)
    result = _empty_result(
        requested_as_of=requested_as_of,
        lookback_rows=effective_lookback,
    )
    if requested_lookback > MAX_LOOKBACK_ROWS:
        result["warnings"].append(f"lookback_capped_to_{MAX_LOOKBACK_ROWS}")

    path = Path(duckdb_path)
    if not path.is_file():
        result["warnings"].append("missing_database")
        return result

    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        result["warnings"].append("unreadable_database")
        return result

    try:
        try:
            index_columns = _table_columns(conn, INDEX_TABLE)
        except duckdb.Error:
            result["warnings"].append(f"table_inspection_failed:{INDEX_TABLE}")
            return result

        if not index_columns:
            result["warnings"].append(f"missing_table:{INDEX_TABLE}")
            return result

        missing_index_columns = sorted(_INDEX_REQUIRED_COLUMNS - index_columns)
        if missing_index_columns:
            result["warnings"].append(
                f"missing_columns:{INDEX_TABLE}:{','.join(missing_index_columns)}"
            )
            return result

        result["tables_used"].append(INDEX_TABLE)
        missing_index_evidence = [
            column for column in _INDEX_EVIDENCE_COLUMNS if column not in index_columns
        ]
        if missing_index_evidence:
            result["warnings"].append(
                f"missing_evidence_columns:{INDEX_TABLE}:{','.join(missing_index_evidence)}"
            )

        try:
            index_records = _load_index_records(
                conn,
                columns=index_columns,
                requested_as_of=requested_as_of,
                lookback_rows=effective_lookback,
            )
        except duckdb.Error:
            result["warnings"].append("index_history_query_failed")
            return result

        if not index_records:
            result["warnings"].append("no_index_history")
            return result

        index_rows: list[dict[str, Any]] = []
        index_source_versions: set[str] = set()
        index_vendor_versions: set[str] = set()
        index_rule_versions: set[str] = set()
        index_quality_flags: set[str] = set()
        index_run_ids: set[str] = set()
        for record in index_records:
            close_value = _finite_float(record[1])
            if close_value is None:
                continue
            trade_date_text = _date_text(record[0])
            if not trade_date_text:
                continue
            index_rows.append(
                {
                    "trade_date": trade_date_text,
                    "close": close_value,
                    "amount": None,
                }
            )
            _add_text(index_source_versions, record[2])
            _add_text(index_vendor_versions, record[3])
            _add_text(index_rule_versions, record[4])
            _add_text(index_quality_flags, record[5])
            _add_text(index_run_ids, record[6])

        if not index_rows:
            result["warnings"].append("no_valid_index_history")
            return result

        result["sources"]["index"] = {
            "status": "ready",
            "table": INDEX_TABLE,
            "series_id": INDEX_SERIES_ID,
            "field": "value_numeric",
            "source_versions": sorted(index_source_versions),
            "vendor_versions": sorted(index_vendor_versions),
            "rule_versions": sorted(index_rule_versions),
            "quality_flags": sorted(index_quality_flags),
            "run_ids": sorted(index_run_ids),
        }
        non_ok_quality_flags = sorted(
            flag
            for flag in index_quality_flags
            if flag.strip().lower() not in _ACCEPTED_QUALITY_FLAGS
        )
        if non_ok_quality_flags:
            result["warnings"].append(
                f"non_ok_index_quality_flags:{','.join(non_ok_quality_flags)}"
            )

        amount_by_date: dict[str, float | None] = {}
        amount_stats = _empty_amount_source()
        try:
            amount_columns = _table_columns(conn, MARKET_AMOUNT_TABLE)
        except duckdb.Error:
            amount_columns = set()
            result["warnings"].append(f"table_inspection_failed:{MARKET_AMOUNT_TABLE}")

        if not amount_columns:
            if not any(
                warning == f"table_inspection_failed:{MARKET_AMOUNT_TABLE}"
                for warning in result["warnings"]
            ):
                result["warnings"].append(f"missing_table:{MARKET_AMOUNT_TABLE}")
        else:
            missing_amount_columns = sorted(
                _MARKET_AMOUNT_REQUIRED_COLUMNS - amount_columns
            )
            if missing_amount_columns:
                result["warnings"].append(
                    f"missing_columns:{MARKET_AMOUNT_TABLE}:{','.join(missing_amount_columns)}"
                )
            else:
                result["tables_used"].append(MARKET_AMOUNT_TABLE)
                missing_amount_evidence = [
                    column
                    for column in _MARKET_AMOUNT_EVIDENCE_COLUMNS
                    if column not in amount_columns
                ]
                if missing_amount_evidence:
                    result["warnings"].append(
                        f"missing_evidence_columns:{MARKET_AMOUNT_TABLE}:"
                        f"{','.join(missing_amount_evidence)}"
                    )
                try:
                    amount_records = _load_market_amount_records(
                        conn,
                        columns=amount_columns,
                        trade_dates=[row["trade_date"] for row in index_rows],
                    )
                except duckdb.Error:
                    result["warnings"].append("market_amount_query_failed")
                else:
                    (
                        amount_by_date,
                        amount_stats,
                    ) = _market_amount_result_from_records(
                        amount_records,
                        vendor_version_available="vendor_version" in amount_columns,
                    )
                    if amount_stats.get("scale_unknown_row_count"):
                        result["warnings"].append(
                            "market_amount_vendor_unscalable_rows_ignored"
                        )
                    if (
                        amount_stats.get("unit_normalization")
                        == "skipped_vendor_version_column_missing"
                    ):
                        # 缺 vendor_version 列时无法定标,fail-closed 输出 NULL;
                        # 监控上需要与"仅缺证据列"区分开(单位归一化被跳过更严重)。
                        result["warnings"].append(
                            "market_amount_unit_normalization_skipped"
                        )

        missing_amount_date_count = 0
        for row in index_rows:
            amount = amount_by_date.get(str(row["trade_date"]))
            row["amount"] = amount
            if amount is None:
                missing_amount_date_count += 1

        amount_stats["missing_trade_date_count"] = missing_amount_date_count
        if missing_amount_date_count:
            result["warnings"].append("market_amount_missing_dates")
        null_amount_count = int(
            amount_stats.get("null_amount_observation_count") or 0
        )
        if null_amount_count:
            result["warnings"].append("market_amount_null_values_ignored")

        result["sources"]["market_amount"] = amount_stats
        result["rows"] = index_rows
        result["row_count"] = len(index_rows)
        result["earliest_trade_date"] = index_rows[0]["trade_date"]
        result["latest_trade_date"] = index_rows[-1]["trade_date"]
        result["effective_as_of_date"] = index_rows[-1]["trade_date"]
        if result["warnings"]:
            result["status"] = "partial"
            result["quality"] = "degraded"
        else:
            result["status"] = "ready"
            result["quality"] = "ok"
        return result
    finally:
        conn.close()


def _load_index_records(
    conn: duckdb.DuckDBPyConnection,
    *,
    columns: set[str],
    requested_as_of: date | None,
    lookback_rows: int,
) -> list[tuple[Any, ...]]:
    evidence_select = [
        column if column in columns else f"null as {column}"
        for column in _INDEX_EVIDENCE_COLUMNS
    ]
    order_expression = _latest_record_order(columns)
    cutoff_clause = ""
    params: list[Any] = [INDEX_SERIES_ID]
    if requested_as_of is not None:
        cutoff_clause = "and try_cast(trade_date as date) <= ?"
        params.append(requested_as_of)
    params.append(lookback_rows)
    return conn.execute(
        f"""
        with ranked as (
          select
            try_cast(trade_date as date) as trade_day,
            try_cast(value_numeric as double) as close_value,
            {", ".join(evidence_select)},
            row_number() over (
              partition by try_cast(trade_date as date)
              order by {order_expression}
            ) as canonical_rank
          from {INDEX_TABLE}
          where series_id = ?
            and try_cast(trade_date as date) is not null
            {cutoff_clause}
        ),
        recent as (
          select
            trade_day,
            close_value,
            source_version,
            vendor_version,
            rule_version,
            quality_flag,
            run_id
          from ranked
          where canonical_rank = 1
            and close_value is not null
          order by trade_day desc
          limit ?
        )
        select *
        from recent
        order by trade_day asc
        """,
        params,
    ).fetchall()


def _load_market_amount_records(
    conn: duckdb.DuckDBPyConnection,
    *,
    columns: set[str],
    trade_dates: list[str],
) -> list[tuple[Any, ...]]:
    if not trade_dates:
        return []
    date_values = ", ".join("(cast(? as date))" for _ in trade_dates)
    evidence_select = [
        column if column in columns else f"null as {column}"
        for column in _MARKET_AMOUNT_EVIDENCE_COLUMNS
    ]
    stock_code_select = (
        "cast(stock_code as varchar) as stock_code"
        if "stock_code" in columns
        else "null as stock_code"
    )
    # Two vendor generations disagree on amount units (docs/data_contracts.md
    # §4.10): tushare-era rows are RMB thousands, choice_native-era rows are
    # RMB. A raw sum(amount) mixes units across the 2025-12-31/2026-01-05
    # boundary. Normalize to RMB via vendor_version before aggregating; when
    # the column itself is missing (older schema/synthetic table, not reachable
    # in production), the amount cannot be scaled and is fail-closed to NULL,
    # surfaced through amount_stats/unit_normalization instead of guessing units.
    has_vendor_version = "vendor_version" in columns
    if has_vendor_version:
        amount_value_select = amount_rmb_sql(table_alias="stock", alias=None)
        scale_unknown_select = scale_unknown_sql("amount", table_alias="stock")
    else:
        amount_value_select = "cast(null as double)"
        scale_unknown_select = "cast(false as boolean)"
    normalized_cte = f"""
        normalized as (
          select
            try_cast(stock.trade_date as date) as trade_day,
            {stock_code_select},
            {amount_value_select} as amount_value,
            {scale_unknown_select} as scale_unknown,
            {", ".join(evidence_select)}
          from {MARKET_AMOUNT_TABLE} as stock
          inner join requested_dates as requested
            on try_cast(stock.trade_date as date) = requested.trade_day
        )
    """
    if "stock_code" in columns:
        canonical_cte = f""",
        ranked as (
          select
            *,
            row_number() over (
              partition by trade_day, stock_code
              order by {_latest_record_order(columns)}
            ) as canonical_rank
          from normalized
        ),
        canonical as (
          select *
          from ranked
          where canonical_rank = 1
        )
        """
    else:
        canonical_cte = """,
        canonical as (
          select *
          from normalized
        )
        """
    return conn.execute(
        f"""
        with requested_dates(trade_day) as (
          values {date_values}
        ),
        {normalized_cte}
        {canonical_cte}
        select
          trade_day,
          sum(amount_value) as total_amount,
          count(*) as canonical_row_count,
          count(amount_value) as amount_value_row_count,
          count(*) filter (where amount_value is null) as null_amount_row_count,
          count(*) filter (where scale_unknown) as scale_unknown_row_count,
          list(distinct source_version)
            filter (where source_version is not null) as source_versions,
          list(distinct vendor_version)
            filter (where vendor_version is not null) as vendor_versions,
          list(distinct rule_version)
            filter (where rule_version is not null) as rule_versions,
          list(distinct run_id)
            filter (where run_id is not null) as run_ids
        from canonical
        group by trade_day
        order by trade_day asc
        """,
        trade_dates,
    ).fetchall()


def _market_amount_result_from_records(
    records: list[tuple[Any, ...]],
    *,
    vendor_version_available: bool,
) -> tuple[dict[str, float | None], dict[str, Any]]:
    amount_by_date: dict[str, float | None] = {}
    stats = _empty_amount_source()
    stats["unit_normalization"] = (
        "applied_via_vendor_generation" if vendor_version_available
        else "skipped_vendor_version_column_missing"
    )
    if not vendor_version_available:
        stats["unit"] = "source_native_unit_unconfirmed"
    source_versions: set[str] = set()
    vendor_versions: set[str] = set()
    rule_versions: set[str] = set()
    run_ids: set[str] = set()
    for record in records:
        trade_date_text = _date_text(record[0])
        if not trade_date_text:
            continue
        amount_by_date[trade_date_text] = _finite_float(record[1])
        stats["date_count"] += 1
        stats["canonical_row_count"] += int(record[2] or 0)
        stats["amount_value_row_count"] += int(record[3] or 0)
        stats["null_amount_row_count"] += int(record[4] or 0)
        stats["scale_unknown_row_count"] += int(record[5] or 0)
        stats["valid_amount_observation_count"] += int(record[3] or 0)
        stats["null_amount_observation_count"] += int(record[4] or 0)
        _add_texts(source_versions, record[6])
        _add_texts(vendor_versions, record[7])
        _add_texts(rule_versions, record[8])
        _add_texts(run_ids, record[9])
    stats["status"] = "ready" if records else "unavailable"
    stats["quality"] = (
        "degraded"
        if stats["null_amount_observation_count"]
        else ("ok" if records else "unavailable")
    )
    stats["source_versions"] = sorted(source_versions)
    stats["vendor_versions"] = sorted(vendor_versions)
    stats["rule_versions"] = sorted(rule_versions)
    stats["run_ids"] = sorted(run_ids)
    return amount_by_date, stats


def _latest_record_order(columns: set[str]) -> str:
    parts: list[str] = []
    if "run_id" in columns:
        parts.extend(
            [
                "regexp_extract(coalesce(run_id, ''), '([0-9]{8}T[0-9]{6}Z)$', 1) desc",
                "coalesce(run_id, '') desc",
            ]
        )
    if "vendor_version" in columns:
        parts.append("coalesce(vendor_version, '') desc")
    if "source_version" in columns:
        parts.append("coalesce(source_version, '') desc")
    return ", ".join(parts) if parts else "1"


def _table_columns(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
) -> set[str]:
    rows = conn.execute(
        """
        select column_name
        from information_schema.columns
        where table_schema = 'main' and table_name = ?
        """,
        [table_name],
    ).fetchall()
    return {str(row[0]).strip().lower() for row in rows}


def _normalize_as_of_date(value: date | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("as_of_date must use ISO YYYY-MM-DD format") from exc


def _normalize_lookback_rows(value: int) -> int:
    if isinstance(value, bool):
        raise ValueError("lookback_rows must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("lookback_rows must be a positive integer") from exc
    if normalized <= 0:
        raise ValueError("lookback_rows must be a positive integer")
    return normalized


def _empty_result(
    *,
    requested_as_of: date | None,
    lookback_rows: int,
) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "quality": "unavailable",
        "series_id": INDEX_SERIES_ID,
        "date_basis": DATE_BASIS,
        "requested_as_of_date": requested_as_of.isoformat() if requested_as_of else None,
        "effective_as_of_date": None,
        "earliest_trade_date": None,
        "latest_trade_date": None,
        "lookback_rows": lookback_rows,
        "row_count": 0,
        "rows": [],
        "tables_used": [],
        "sources": {
            "index": {
                "status": "unavailable",
                "table": INDEX_TABLE,
                "series_id": INDEX_SERIES_ID,
                "field": "value_numeric",
                "source_versions": [],
                "vendor_versions": [],
                "rule_versions": [],
                "quality_flags": [],
                "run_ids": [],
            },
            "market_amount": _empty_amount_source(),
        },
        "warnings": [],
    }


def _empty_amount_source() -> dict[str, Any]:
    return {
        "status": "unavailable",
        "quality": "unavailable",
        "table": MARKET_AMOUNT_TABLE,
        "field": "amount",
        "unit": "rmb_normalized_by_vendor_generation_see_data_contracts_4_10",
        "unit_normalization": "not_applicable",
        "aggregation": "sum_by_trade_date_after_latest_stock_date_deduplication",
        "date_count": 0,
        "canonical_row_count": 0,
        "amount_value_row_count": 0,
        "null_amount_row_count": 0,
        "valid_amount_observation_count": 0,
        "null_amount_observation_count": 0,
        "scale_unknown_row_count": 0,
        "missing_trade_date_count": 0,
        "source_versions": [],
        "vendor_versions": [],
        "rule_versions": [],
        "run_ids": [],
    }


def _date_text(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10]).isoformat()
    except ValueError:
        return None


def _finite_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def _add_text(target: set[str], value: Any) -> None:
    if value is None:
        return
    text = str(value).strip()
    if text:
        target.add(text)


def _add_texts(target: set[str], values: Iterable[Any] | None) -> None:
    if values is None:
        return
    for value in values:
        _add_text(target, value)
