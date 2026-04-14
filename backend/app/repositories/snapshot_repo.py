"""DuckDB DDL and replace-safe writers for standardized zqtz / tyw snapshot tables."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import duckdb

from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection

ZQTZ_TABLE = "zqtz_bond_daily_snapshot"
TYW_TABLE = "tyw_interbank_daily_snapshot"


def ensure_snapshot_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Baseline DDL is versioned in `duckdb_migrations` (also run at API/worker startup)."""
    apply_pending_migrations_on_connection(conn)


def delete_zqtz_snapshots_for_batches(
    conn: duckdb.DuckDBPyConnection,
    ingest_batch_ids: list[str],
    *,
    report_dates: list[object] | None = None,
) -> None:
    if not ingest_batch_ids:
        return
    placeholders = ",".join(["?"] * len(ingest_batch_ids))
    params: list[object] = list(ingest_batch_ids)
    where_clause = f"ingest_batch_id in ({placeholders})"
    if report_dates:
        report_placeholders = ",".join(["?"] * len(report_dates))
        where_clause += f" and report_date in ({report_placeholders})"
        params.extend(report_dates)
    conn.execute(f"delete from {ZQTZ_TABLE} where {where_clause}", params)


def delete_tyw_snapshots_for_batches(
    conn: duckdb.DuckDBPyConnection,
    ingest_batch_ids: list[str],
    *,
    report_dates: list[object] | None = None,
) -> None:
    if not ingest_batch_ids:
        return
    placeholders = ",".join(["?"] * len(ingest_batch_ids))
    params: list[object] = list(ingest_batch_ids)
    where_clause = f"ingest_batch_id in ({placeholders})"
    if report_dates:
        report_placeholders = ",".join(["?"] * len(report_dates))
        where_clause += f" and report_date in ({report_placeholders})"
        params.extend(report_dates)
    conn.execute(f"delete from {TYW_TABLE} where {where_clause}", params)


def _sql_value(value: object) -> object:
    if isinstance(value, Decimal):
        return float(value)
    return value


def replace_zqtz_snapshot_rows(
    conn: duckdb.DuckDBPyConnection,
    rows: list[dict[str, Any]],
    *,
    ingest_batch_ids: list[str],
    report_dates: list[object] | None = None,
) -> int:
    delete_zqtz_snapshots_for_batches(conn, ingest_batch_ids, report_dates=report_dates)
    if not rows:
        return 0
    conn.executemany(
        f"""
        insert into {ZQTZ_TABLE} values (
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            (
                _sql_value(r["report_date"]),
                r["instrument_code"],
                r["instrument_name"],
                r["portfolio_name"],
                r["cost_center"],
                r["account_category"],
                r["asset_class"],
                r["bond_type"],
                r["issuer_name"],
                r["industry_name"],
                r["rating"],
                r["currency_code"],
                _sql_value(r["face_value_native"]),
                _sql_value(r["market_value_native"]),
                _sql_value(r["amortized_cost_native"]),
                _sql_value(r["accrued_interest_native"]),
                _sql_value(r["coupon_rate"]),
                _sql_value(r["ytm_value"]),
                _sql_value(r["maturity_date"]),
                _sql_value(r["next_call_date"]),
                r["overdue_days"],
                r["is_issuance_like"],
                r["interest_mode"],
                r["source_version"],
                r["rule_version"],
                r["ingest_batch_id"],
                r["trace_id"],
                _sql_value(r.get("value_date")),
                r.get("customer_attribute") or "",
            )
            for r in rows
        ],
    )
    return len(rows)


def replace_tyw_snapshot_rows(
    conn: duckdb.DuckDBPyConnection,
    rows: list[dict[str, Any]],
    *,
    ingest_batch_ids: list[str],
    report_dates: list[object] | None = None,
) -> int:
    delete_tyw_snapshots_for_batches(conn, ingest_batch_ids, report_dates=report_dates)
    if not rows:
        return 0
    conn.executemany(
        f"""
        insert into {TYW_TABLE} values (
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            (
                _sql_value(r["report_date"]),
                r["position_id"],
                r["product_type"],
                r["position_side"],
                r["counterparty_name"],
                r["account_type"],
                r["special_account_type"],
                r["core_customer_type"],
                r["currency_code"],
                _sql_value(r["principal_native"]),
                _sql_value(r["accrued_interest_native"]),
                _sql_value(r["funding_cost_rate"]),
                _sql_value(r["maturity_date"]),
                r["pledged_bond_code"],
                r["source_version"],
                r["rule_version"],
                r["ingest_batch_id"],
                r["trace_id"],
            )
            for r in rows
        ],
    )
    return len(rows)


def zqtz_grain_key(row: dict[str, Any]) -> tuple[object, ...]:
    return (
        row["report_date"],
        row["instrument_code"],
        row["portfolio_name"],
        row["cost_center"],
        row["currency_code"],
    )


def tyw_grain_key(row: dict[str, Any]) -> tuple[object, ...]:
    return (row["report_date"], row["position_id"])


def merge_rows_by_grain(
    rows_in_order: list[dict[str, Any]],
    grain_fn,
) -> list[dict[str, Any]]:
    merged: dict[tuple[object, ...], dict[str, Any]] = {}
    for row in rows_in_order:
        merged[grain_fn(row)] = row
    return list(merged.values())
