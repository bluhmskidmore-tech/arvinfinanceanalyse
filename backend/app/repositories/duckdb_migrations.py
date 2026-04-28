"""All DuckDB schema migrations, ordered by version (baseline v1–v11)."""

from __future__ import annotations

import duckdb
from backend.app.repositories.duckdb_schema_registry import (
    DuckDBSchemaRegistry,
    main_database_file_path,
)
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text


def _run_sql_slice(conn: duckdb.DuckDBPyConnection, relative_path: str) -> None:
    """Execute MOSS:STMT-delimited DDL from the static registry (single source of truth)."""
    text = (REGISTRY_DIR / relative_path).read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


def _main_table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_schema = 'main' and table_name = ?
        limit 1
        """,
        [table_name],
    ).fetchone()
    return row is not None


def ensure_fx_daily_mid_schema_if_missing(conn: duckdb.DuckDBPyConnection) -> None:
    """Re-apply fx DDL when the table is missing (e.g. dropped) but migrations are already recorded."""
    if _main_table_exists(conn, "fx_daily_mid"):
        return
    _run_sql_slice(conn, "10_fx_mid.sql")


def ensure_choice_macro_schema_if_missing(conn: duckdb.DuckDBPyConnection) -> None:
    """Re-apply Choice macro DDL when an older DuckDB file lacks post-baseline tables."""
    if _main_table_exists(conn, "market_data_series_category"):
        return
    _run_sql_slice(conn, "11_choice_macro.sql")


def ensure_balance_zqtz_legacy_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Align pre-registry / hand-rolled `fact_formal_zqtz_balance_daily` tables with current head columns."""
    if not _main_table_exists(conn, "fact_formal_zqtz_balance_daily"):
        return
    for statement in (
        "alter table fact_formal_zqtz_balance_daily add column if not exists account_category varchar",
        "alter table fact_formal_zqtz_balance_daily add column if not exists business_type_primary varchar",
        "alter table fact_formal_zqtz_balance_daily add column if not exists overdue_principal_days integer",
        "alter table fact_formal_zqtz_balance_daily add column if not exists overdue_interest_days integer",
        "alter table fact_formal_zqtz_balance_daily add column if not exists value_date varchar",
        "alter table fact_formal_zqtz_balance_daily add column if not exists customer_attribute varchar",
    ):
        conn.execute(statement)


def _v18_zqtz_business_type_primary(conn: duckdb.DuckDBPyConnection) -> None:
    for statement in (
        "alter table zqtz_bond_daily_snapshot add column if not exists business_type_primary varchar",
        "alter table fact_formal_zqtz_balance_daily add column if not exists business_type_primary varchar",
    ):
        conn.execute(statement)


def _v19_ledger_import(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "19_ledger_import.sql")


def _v1_snapshot_tables(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "01_snapshot.sql")


def _v2_bond_analytics(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "02_bond_analytics.sql")


def _v3_yield_curve(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "03_yield_curve.sql")


def _v4_risk_tensor(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "04_risk_tensor.sql")


def _v5_balance_analysis(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "05_balance_analysis.sql")


def _v6_pnl(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "07_pnl_materialize.sql")


def _v7_product_category_pnl(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "08_product_category_pnl.sql")


def _v8_fx_and_macro(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "10_fx_mid.sql")
    _run_sql_slice(conn, "11_choice_macro.sql")


def _v9_source_preview(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "06_source_preview.sql")


def _v10_materialize_runs(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "09_phase1_materialize_runs.sql")


def _v11_choice_news(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "12_choice_news.sql")


def _v12_news_warehouse(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "13_news_warehouse.sql")


def _v13_external_data_catalog(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "14_external_data_catalog.sql")


def _v14_std_external_macro(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "15_external_std_macro.sql")


def _v15_external_vw_legacy(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "16_external_vw_legacy.sql")


def _v16_external_supply_auction_calendar(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "17_external_supply_auction_calendar.sql")


def _v17_accounting_asset_movement(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "18_accounting_asset_movement.sql")


def register_all(registry: DuckDBSchemaRegistry) -> None:
    registry.register(1, "baseline snapshot tables", _v1_snapshot_tables)
    registry.register(2, "baseline bond analytics", _v2_bond_analytics)
    registry.register(3, "baseline yield curve", _v3_yield_curve)
    registry.register(4, "baseline risk tensor", _v4_risk_tensor)
    registry.register(5, "baseline balance analysis", _v5_balance_analysis)
    registry.register(6, "baseline PnL tables", _v6_pnl)
    registry.register(7, "baseline product category PnL", _v7_product_category_pnl)
    registry.register(8, "baseline FX and Choice macro", _v8_fx_and_macro)
    registry.register(9, "baseline source preview", _v9_source_preview)
    registry.register(10, "baseline materialize runs", _v10_materialize_runs)
    registry.register(11, "baseline Choice news", _v11_choice_news)
    registry.register(12, "news warehouse fact_news_event", _v12_news_warehouse)
    registry.register(13, "external data catalog", _v13_external_data_catalog)
    registry.register(14, "std external macro + vw_external_macro_daily", _v14_std_external_macro)
    registry.register(15, "legacy read views (choice macro/news, yield, fx)", _v15_external_vw_legacy)
    registry.register(16, "supply auction research calendar read model", _v16_external_supply_auction_calendar)
    registry.register(17, "accounting asset movement monthly read model", _v17_accounting_asset_movement)
    registry.register(18, "ZQTZ business type 1 lineage for balance analysis", _v18_zqtz_business_type_primary)
    registry.register(19, "bank ledger import traceability tables", _v19_ledger_import)


def apply_pending_migrations_on_connection(conn: duckdb.DuckDBPyConnection) -> None:
    """Idempotent: apply any pending versioned migrations on this open connection."""
    registry = DuckDBSchemaRegistry(db_path=main_database_file_path(conn) or ":memory:")
    register_all(registry)
    registry.apply_pending(conn=conn)
