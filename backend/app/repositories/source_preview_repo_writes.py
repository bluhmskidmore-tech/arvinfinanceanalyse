from __future__ import annotations

from collections.abc import Callable

import duckdb

from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.source_preview_repo_constants import PREVIEW_TABLES


def ensure_source_preview_schema_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Baseline DDL is versioned in `duckdb_migrations` (also run at API/worker startup)."""
    apply_pending_migrations_on_connection(conn)


def snapshot_preview_tables(duckdb_path: str) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        for table_name in PREVIEW_TABLES:
            backup_name = f"{table_name}__backup"
            if _table_exists(conn, table_name):
                conn.execute(f"drop table if exists {backup_name}")
                conn.execute(f"create table {backup_name} as select * from {table_name}")
            else:
                conn.execute(f"drop table if exists {backup_name}")
    finally:
        conn.close()


def restore_preview_tables(duckdb_path: str) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        for table_name in PREVIEW_TABLES:
            backup_name = f"{table_name}__backup"
            if _table_exists(conn, backup_name):
                conn.execute(f"drop table if exists {table_name}")
                conn.execute(f"create table {table_name} as select * from {backup_name}")
            else:
                conn.execute(f"drop table if exists {table_name}")
    finally:
        conn.close()


def cleanup_preview_backups(duckdb_path: str) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        for table_name in PREVIEW_TABLES:
            conn.execute(f"drop table if exists {table_name}__backup")
    finally:
        conn.close()


def clear_preview_tables(duckdb_path: str) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        for table_name in PREVIEW_TABLES:
            conn.execute(f"drop table if exists {table_name}")
    finally:
        conn.close()


def write_preview_tables(
    duckdb_path: str,
    summaries: list[dict[str, object]],
    row_records: list[dict[str, object]],
    trace_records: list[dict[str, object]],
    *,
    ensure_source_preview_schema_tables_fn: Callable[[duckdb.DuckDBPyConnection], None],
) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
    transaction_started = False
    try:
        ensure_source_preview_schema_tables_fn(conn)
        conn.execute("begin transaction")
        transaction_started = True

        if summaries:
            current_batch_ids = sorted({summary["ingest_batch_id"] for summary in summaries})
            for ingest_batch_id in current_batch_ids:
                conn.execute(
                    "delete from phase1_source_preview_summary where ingest_batch_id = ?",
                    [ingest_batch_id],
                )
                conn.execute(
                    "delete from phase1_source_preview_groups where ingest_batch_id = ?",
                    [ingest_batch_id],
                )
                conn.execute(
                    "delete from phase1_zqtz_preview_rows where ingest_batch_id = ?",
                    [ingest_batch_id],
                )
                conn.execute(
                    "delete from phase1_tyw_preview_rows where ingest_batch_id = ?",
                    [ingest_batch_id],
                )
                conn.execute(
                    "delete from phase1_pnl_preview_rows where ingest_batch_id = ?",
                    [ingest_batch_id],
                )
                conn.execute(
                    "delete from phase1_nonstd_pnl_preview_rows where ingest_batch_id = ?",
                    [ingest_batch_id],
                )
                conn.execute(
                    "delete from phase1_zqtz_rule_traces where ingest_batch_id = ?",
                    [ingest_batch_id],
                )
                conn.execute(
                    "delete from phase1_tyw_rule_traces where ingest_batch_id = ?",
                    [ingest_batch_id],
                )
                conn.execute(
                    "delete from phase1_pnl_rule_traces where ingest_batch_id = ?",
                    [ingest_batch_id],
                )
                conn.execute(
                    "delete from phase1_nonstd_pnl_rule_traces where ingest_batch_id = ?",
                    [ingest_batch_id],
                )
            conn.executemany(
                "insert into phase1_source_preview_summary values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        summary["ingest_batch_id"],
                        summary["batch_created_at"],
                        summary["source_family"],
                        summary["report_date"],
                        summary["report_start_date"],
                        summary["report_end_date"],
                        summary["report_granularity"],
                        summary["source_file"],
                        summary["total_rows"],
                        summary["manual_review_count"],
                        summary["source_version"],
                        summary["rule_version"],
                        summary["preview_mode"],
                    )
                    for summary in summaries
                ],
            )
            group_rows = [
                (
                    summary["ingest_batch_id"],
                    summary["source_family"],
                    group_label,
                    row_count,
                    summary["source_version"],
                )
                for summary in summaries
                for group_label, row_count in summary["group_counts"].items()
            ]
            if group_rows:
                conn.executemany(
                    "insert into phase1_source_preview_groups values (?, ?, ?, ?, ?)",
                    group_rows,
                )
        else:
            for table_name in PREVIEW_TABLES:
                conn.execute(f"delete from {table_name}")

        zqtz_rows = [
            (
                row["ingest_batch_id"],
                row["row_locator"],
                row["report_date"],
                row["business_type_primary"],
                row["business_type_final"],
                row["asset_group"],
                row["instrument_code"],
                row["instrument_name"],
                row["account_category"],
                row["manual_review_needed"],
                row["source_version"],
                row["rule_version"],
            )
            for row in row_records
            if "asset_group" in row
        ]
        if zqtz_rows:
            conn.executemany(
                "insert into phase1_zqtz_preview_rows values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                zqtz_rows,
            )

        tyw_rows = [
            (
                row["ingest_batch_id"],
                row["row_locator"],
                row["report_date"],
                row["business_type_primary"],
                row["product_group"],
                row["institution_category"],
                row["special_nature"],
                row["counterparty_name"],
                row["investment_portfolio"],
                row["manual_review_needed"],
                row["source_version"],
                row["rule_version"],
            )
            for row in row_records
            if "product_group" in row
        ]
        if tyw_rows:
            conn.executemany(
                "insert into phase1_tyw_preview_rows values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                tyw_rows,
            )

        pnl_rows = [
            (
                row["source_family"],
                row["ingest_batch_id"],
                row["row_locator"],
                row["report_date"],
                row["instrument_code"],
                row["invest_type_raw"],
                row["portfolio_name"],
                row["cost_center"],
                row["currency"],
                row["manual_review_needed"],
                row["source_version"],
                row["rule_version"],
            )
            for row in row_records
            if "invest_type_raw" in row
        ]
        if pnl_rows:
            conn.executemany(
                "insert into phase1_pnl_preview_rows values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                pnl_rows,
            )

        nonstd_pnl_rows = [
            (
                row["source_family"],
                row["ingest_batch_id"],
                row["row_locator"],
                row["report_date"],
                row["journal_type"],
                row["product_type"],
                row["asset_code"],
                row["account_code"],
                row["dc_flag_raw"],
                row["raw_amount"],
                row["manual_review_needed"],
                row["source_version"],
                row["rule_version"],
            )
            for row in row_records
            if "journal_type" in row
        ]
        if nonstd_pnl_rows:
            conn.executemany(
                "insert into phase1_nonstd_pnl_preview_rows values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                nonstd_pnl_rows,
            )

        zqtz_traces = [
            (
                trace["ingest_batch_id"],
                trace["row_locator"],
                trace["trace_step"],
                trace["field_name"],
                trace["field_value"],
                trace["derived_label"],
                trace["manual_review_needed"],
            )
            for trace in trace_records
            if trace.get("source_family") == "zqtz"
        ]
        if zqtz_traces:
            conn.executemany(
                "insert into phase1_zqtz_rule_traces values (?, ?, ?, ?, ?, ?, ?)",
                zqtz_traces,
            )

        tyw_traces = [
            (
                trace["ingest_batch_id"],
                trace["row_locator"],
                trace["trace_step"],
                trace["field_name"],
                trace["field_value"],
                trace["derived_label"],
                trace["manual_review_needed"],
            )
            for trace in trace_records
            if trace.get("source_family") == "tyw"
        ]
        if tyw_traces:
            conn.executemany(
                "insert into phase1_tyw_rule_traces values (?, ?, ?, ?, ?, ?, ?)",
                tyw_traces,
            )

        pnl_traces = [
            (
                trace["source_family"],
                trace["ingest_batch_id"],
                trace["row_locator"],
                trace["trace_step"],
                trace["field_name"],
                trace["field_value"],
                trace["derived_label"],
                trace["manual_review_needed"],
            )
            for trace in trace_records
            if trace.get("source_family") == "pnl"
        ]
        if pnl_traces:
            conn.executemany(
                "insert into phase1_pnl_rule_traces values (?, ?, ?, ?, ?, ?, ?, ?)",
                pnl_traces,
            )

        nonstd_pnl_traces = [
            (
                trace["source_family"],
                trace["ingest_batch_id"],
                trace["row_locator"],
                trace["trace_step"],
                trace["field_name"],
                trace["field_value"],
                trace["derived_label"],
                trace["manual_review_needed"],
            )
            for trace in trace_records
            if trace.get("source_family") in {"pnl_514", "pnl_516", "pnl_517"}
        ]
        if nonstd_pnl_traces:
            conn.executemany(
                "insert into phase1_nonstd_pnl_rule_traces values (?, ?, ?, ?, ?, ?, ?, ?)",
                nonstd_pnl_traces,
            )
        conn.execute("commit")
        transaction_started = False
    except Exception:
        if transaction_started:
            try:
                conn.execute("rollback")
            except Exception:
                pass
        raise
    finally:
        conn.close()


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    return bool(
        conn.execute(
            """
            select count(*)
            from information_schema.tables
            where table_name = ?
            """,
            [table_name],
        ).fetchone()[0]
    )
