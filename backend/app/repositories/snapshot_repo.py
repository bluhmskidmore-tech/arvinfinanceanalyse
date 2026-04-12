"""DuckDB DDL and replace-safe writers for standardized zqtz / tyw snapshot tables."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import duckdb

ZQTZ_TABLE = "zqtz_bond_daily_snapshot"
TYW_TABLE = "tyw_interbank_daily_snapshot"


def ensure_snapshot_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        f"""
        create table if not exists {ZQTZ_TABLE} (
          report_date date,
          instrument_code varchar,
          instrument_name varchar,
          portfolio_name varchar,
          cost_center varchar,
          account_category varchar,
          asset_class varchar,
          bond_type varchar,
          issuer_name varchar,
          industry_name varchar,
          rating varchar,
          currency_code varchar,
          face_value_native decimal(24, 8),
          market_value_native decimal(24, 8),
          amortized_cost_native decimal(24, 8),
          accrued_interest_native decimal(24, 8),
          coupon_rate decimal(18, 8),
          ytm_value decimal(18, 8),
          maturity_date date,
          next_call_date date,
          overdue_days integer,
          is_issuance_like boolean,
          interest_mode varchar,
          source_version varchar,
          rule_version varchar,
          ingest_batch_id varchar,
          trace_id varchar
        )
        """
    )
    _ensure_zqtz_enrichment_columns(conn)
    conn.execute(
        f"""
        create table if not exists {TYW_TABLE} (
          report_date date,
          position_id varchar,
          product_type varchar,
          position_side varchar,
          counterparty_name varchar,
          account_type varchar,
          special_account_type varchar,
          core_customer_type varchar,
          currency_code varchar,
          principal_native decimal(24, 8),
          accrued_interest_native decimal(24, 8),
          funding_cost_rate decimal(18, 8),
          maturity_date date,
          pledged_bond_code varchar,
          source_version varchar,
          rule_version varchar,
          ingest_batch_id varchar,
          trace_id varchar
        )
        """
    )


def _snapshot_column_exists(conn: duckdb.DuckDBPyConnection, table_name: str, column_name: str) -> bool:
    row = conn.execute(
        """
        select 1
        from information_schema.columns
        where table_name = ?
          and column_name = ?
        limit 1
        """,
        [table_name, column_name],
    ).fetchone()
    return row is not None


def _ensure_zqtz_enrichment_columns(conn: duckdb.DuckDBPyConnection) -> None:
    if not _snapshot_column_exists(conn, ZQTZ_TABLE, "value_date"):
        conn.execute(f"alter table {ZQTZ_TABLE} add column value_date date")
    if not _snapshot_column_exists(conn, ZQTZ_TABLE, "customer_attribute"):
        conn.execute(f"alter table {ZQTZ_TABLE} add column customer_attribute varchar")


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
