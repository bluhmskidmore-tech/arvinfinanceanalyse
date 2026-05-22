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


def _ensure_zqtz_patch_target_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Recover legacy DBs that recorded baseline migrations before these tables existed."""
    if not _main_table_exists(conn, "zqtz_bond_daily_snapshot"):
        _run_sql_slice(conn, "01_snapshot.sql")
    if not _main_table_exists(conn, "fact_formal_zqtz_balance_daily"):
        _run_sql_slice(conn, "05_balance_analysis.sql")


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
        "alter table fact_formal_zqtz_balance_daily add column if not exists sub_type varchar",
    ):
        conn.execute(statement)


def ensure_risk_tensor_legacy_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Align risk tensor tables whose v4 migration was recorded before later additive columns."""
    if not _main_table_exists(conn, "fact_formal_risk_tensor_daily"):
        return
    for statement in (
        "alter table fact_formal_risk_tensor_daily add column if not exists asset_cashflow_30d decimal(24, 8)",
        "alter table fact_formal_risk_tensor_daily add column if not exists asset_cashflow_90d decimal(24, 8)",
        "alter table fact_formal_risk_tensor_daily add column if not exists liability_cashflow_30d decimal(24, 8)",
        "alter table fact_formal_risk_tensor_daily add column if not exists liability_cashflow_90d decimal(24, 8)",
        "alter table fact_formal_risk_tensor_daily add column if not exists liability_source_version varchar",
        "alter table fact_formal_risk_tensor_daily add column if not exists liability_rule_version varchar",
        "alter table fact_formal_risk_tensor_daily add column if not exists regulatory_dv01 decimal(24, 8)",
    ):
        conn.execute(statement)


def _v18_zqtz_business_type_primary(conn: duckdb.DuckDBPyConnection) -> None:
    _ensure_zqtz_patch_target_tables(conn)
    for table_name in (
        "zqtz_bond_daily_snapshot",
        "fact_formal_zqtz_balance_daily",
    ):
        if _main_table_exists(conn, table_name):
            conn.execute(
                f"alter table {table_name} add column if not exists business_type_primary varchar"
            )


def _v19_ledger_import(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "19_ledger_import.sql")


def _v20_ledger_analytics(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "20_ledger_analytics.sql")


def _v21_choice_stock(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "21_choice_stock.sql")


def _v22_livermore_position_snapshot(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "22_livermore_position_snapshot.sql")


def _v23_livermore_gate_supplement(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "23_livermore_gate_supplement.sql")


def _v24_zqtz_accounting_sub_type(conn: duckdb.DuckDBPyConnection) -> None:
    """Persist accounting/data-dictionary sub_type on ZQTZ snapshot + formal facts; backfill from 业务种类1."""
    _ensure_zqtz_patch_target_tables(conn)
    if _main_table_exists(conn, "zqtz_bond_daily_snapshot"):
        conn.execute("alter table zqtz_bond_daily_snapshot add column if not exists sub_type varchar")
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set sub_type = business_type_primary
            where sub_type is null or trim(coalesce(sub_type, '')) = ''
            """
        )
    if _main_table_exists(conn, "fact_formal_zqtz_balance_daily"):
        conn.execute("alter table fact_formal_zqtz_balance_daily add column if not exists sub_type varchar")
        conn.execute(
            """
            update fact_formal_zqtz_balance_daily
            set sub_type = business_type_primary
            where sub_type is null or trim(coalesce(sub_type, '')) = ''
            """
        )


def _v25_cffex_member_rank(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "24_cffex_member_rank.sql")


def _v26_pnl_by_business_precompute(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "25_pnl_by_business_precompute.sql")


def _v27_choice_stock_factor_snapshot(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "27_choice_stock_factor_snapshot.sql")


def _v28_livermore_candidate_history(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "28_livermore_candidate_history.sql")


def _v29_commodity_futures_daily(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "29_commodity_futures_daily.sql")


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
    registry.register(20, "bank ledger analytics read models", _v20_ledger_analytics)
    registry.register(21, "Choice stock materialization front layer", _v21_choice_stock)
    registry.register(22, "Livermore position snapshot read model", _v22_livermore_position_snapshot)
    registry.register(23, "Livermore gate supplement daily (breadth/limit-up)", _v23_livermore_gate_supplement)
    registry.register(24, "ZQTZ accounting sub_type on snapshot + formal facts", _v24_zqtz_accounting_sub_type)
    registry.register(25, "CFFEX member-rank daily from Choice/Tushare", _v25_cffex_member_rank)
    registry.register(26, "PnL by-business page precompute read model", _v26_pnl_by_business_precompute)
    registry.register(27, "Choice stock factor snapshot for equity strategies", _v27_choice_stock_factor_snapshot)
    registry.register(28, "Livermore candidate history analytical replay", _v28_livermore_candidate_history)
    registry.register(29, "Commodity futures main-contract daily ingest", _v29_commodity_futures_daily)


def apply_pending_migrations_on_connection(conn: duckdb.DuckDBPyConnection) -> None:
    """Idempotent: apply any pending versioned migrations on this open connection."""
    registry = DuckDBSchemaRegistry(db_path=main_database_file_path(conn) or ":memory:")
    register_all(registry)
    registry.apply_pending(conn=conn)
