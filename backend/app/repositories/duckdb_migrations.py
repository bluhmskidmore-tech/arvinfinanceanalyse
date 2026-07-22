"""All DuckDB schema migrations, ordered by version (baseline v1–v11)."""

from __future__ import annotations

import re

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
        "alter table fact_formal_risk_tensor_daily add column if not exists rate_risk_market_value decimal(24, 8)",
        "alter table fact_formal_risk_tensor_daily add column if not exists rate_risk_dv01 decimal(24, 8)",
        "alter table fact_formal_risk_tensor_daily add column if not exists rate_risk_modified_duration decimal(24, 8)",
        "alter table fact_formal_risk_tensor_daily add column if not exists duration_excluded_market_value decimal(24, 8)",
        "alter table fact_formal_risk_tensor_daily add column if not exists duration_excluded_count integer",
        "alter table fact_formal_risk_tensor_daily add column if not exists upstream_rule_version varchar",
        "alter table fact_formal_risk_tensor_daily add column if not exists upstream_cache_version varchar",
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


def _v31_market_breadth_daily(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "33_market_breadth_daily.sql")


_V32_DEPENDENT_READ_INDEX_NAMES: dict[str, str] = {
    "fact_formal_pnl_fi": "idx_fact_formal_pnl_fi_report_date",
    "fx_daily_mid": "idx_fx_daily_mid_trade_date_base_currency",
}

_V32_RECOVERY_SQL: dict[str, str] = {
    "fact_formal_pnl_fi": "07_pnl_materialize.sql",
    "fx_daily_mid": "10_fx_mid.sql",
}


def _v32_constraint_statements() -> list[tuple[str, str, str, tuple[str, ...]]]:
    text = (REGISTRY_DIR / "34_add_table_constraints.sql").read_text(encoding="utf-8")
    specs: list[tuple[str, str, str, tuple[str, ...]]] = []
    for statement in parse_registry_sql_text(text):
        match = re.fullmatch(
            r"\s*create\s+unique\s+index\s+if\s+not\s+exists\s+"
            r"([a-z_][a-z0-9_]*)\s+on\s+([a-z_][a-z0-9_]*)\s*\(([^()]+)\)\s*$",
            statement, re.IGNORECASE,
        )
        if not match:
            raise RuntimeError(f"Unsupported v32 constraint statement: {statement}")
        index_name = match.group(1)
        table_name = match.group(2)
        key_columns = tuple(column.strip() for column in match.group(3).split(","))
        if not key_columns or any(
            re.fullmatch(r"[a-z_][a-z0-9_]*", column, re.IGNORECASE) is None
            for column in key_columns
        ):
            raise RuntimeError(f"Unsupported v32 key columns in statement: {statement}")
        specs.append((statement, index_name, table_name, key_columns))
    return specs


def _v32_add_table_constraints(conn: duckdb.DuckDBPyConnection) -> None:
    specs = _v32_constraint_statements()
    spec_tables = [
        table_name
        for _statement, _index_name, table_name, _key_columns in specs
    ]
    expected_tables = set(_V32_RECOVERY_SQL)
    if len(spec_tables) != len(expected_tables) or set(spec_tables) != expected_tables:
        raise RuntimeError(
            "v32 constraint SQL must contain exactly the governed PnL and FX targets"
        )

    missing_tables = {
        table_name
        for _statement, _index_name, table_name, _key_columns in specs
        if not _main_table_exists(conn, table_name)
    }

    # Preflight every existing table before recovery or constraint DDL so
    # defects cannot cause any v32 data or schema mutation.
    for _statement, _index_name, table_name, key_columns in specs:
        if table_name in missing_tables:
            continue

        existing_columns = {
            row[0]
            for row in conn.execute(
                """
                select column_name
                from information_schema.columns
                where table_schema = 'main' and table_name = ?
                """,
                [table_name],
            ).fetchall()
        }
        missing_columns = [column for column in key_columns if column not in existing_columns]
        if missing_columns:
            raise RuntimeError(
                f"v32 constraint target {table_name} is missing columns: "
                f"{', '.join(missing_columns)}"
            )

        for column in key_columns:
            null_count_row = conn.execute(
                f"select count(*) from {table_name} where {column} is null"
            ).fetchone()
            null_count = int(null_count_row[0]) if null_count_row else 0
            if null_count:
                raise RuntimeError(
                    f"{table_name}.{column} contains {null_count} NULL rows; "
                    "v32 requires source cleanup before migration"
                )

        key_expression = ", ".join(key_columns)
        duplicate_count_row = conn.execute(
            f"""
            select count(*) from (
                select {key_expression}, count(*) as row_count
                from {table_name}
                group by {key_expression}
                having count(*) > 1
            )
            """
        ).fetchone()
        duplicate_count = int(duplicate_count_row[0]) if duplicate_count_row else 0
        if duplicate_count:
            raise RuntimeError(
                f"{table_name} has {duplicate_count} duplicate canonical grain groups "
                f"for ({key_expression})"
            )

    # Some legacy files recorded the baseline version without creating every
    # table. Recover only the empty target schemas after all preflight passes.
    for _statement, _index_name, table_name, _key_columns in specs:
        if table_name in missing_tables:
            _run_sql_slice(conn, _V32_RECOVERY_SQL[table_name])

    for _statement, unique_index_name, table_name, key_columns in specs:
        read_index_name = _V32_DEPENDENT_READ_INDEX_NAMES[table_name]
        conn.execute(f"drop index if exists {read_index_name}")
        conn.execute(f"drop index if exists {unique_index_name}")
        for column in key_columns:
            nullable = conn.execute(
                """
                select is_nullable
                from information_schema.columns
                where table_schema = 'main' and table_name = ? and column_name = ?
                """,
                [table_name, column],
            ).fetchone()
            if nullable and nullable[0] == "YES":
                conn.execute(f"alter table {table_name} alter column {column} set not null")

    # v30 was historically reused in an existing database, so recreate every
    # governed read-path index here as an idempotent recovery step.
    _v30_fact_snapshot_indexes(conn)
    for statement, _index_name, _table_name, _key_columns in specs:
        conn.execute(statement)


def _v33_risk_tensor_materialized_metrics(conn: duckdb.DuckDBPyConnection) -> None:
    if not _main_table_exists(conn, "fact_formal_risk_tensor_daily"):
        _run_sql_slice(conn, "04_risk_tensor.sql")
    _run_sql_slice(conn, "35_risk_tensor_materialized_metrics.sql")


def _v34_pnl_source_classification_metadata(conn: duckdb.DuckDBPyConnection) -> None:
    if not _main_table_exists(conn, "fact_formal_pnl_fi"):
        _run_sql_slice(conn, "07_pnl_materialize.sql")
    _run_sql_slice(conn, "36_pnl_source_classification_metadata.sql")


def _v35_bond_analytics_value_date(conn: duckdb.DuckDBPyConnection) -> None:
    if not _main_table_exists(conn, "fact_formal_bond_analytics_daily"):
        _run_sql_slice(conn, "02_bond_analytics.sql")
        return
    conn.execute(
        "alter table fact_formal_bond_analytics_daily "
        "add column if not exists value_date date"
    )


def _v30_fact_snapshot_indexes(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "32_fact_snapshot_indexes.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        match = re.search(r"\bon\s+([a-z_][a-z0-9_]*)\s*\(", statement, re.IGNORECASE)
        table_name = match.group(1) if match else None
        if table_name is not None and _main_table_exists(conn, table_name):
            conn.execute(statement)


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
    registry.register(30, "Formal fact and snapshot read-path indexes", _v30_fact_snapshot_indexes)
    registry.register(31, "Market breadth daily counts for Livermore gate", _v31_market_breadth_daily)
    registry.register(32, "Recover read indexes and constrain governed PnL/FX grains", _v32_add_table_constraints)
    registry.register(33, "Materialize governed Risk Tensor read metrics and upstream lineage", _v33_risk_tensor_materialized_metrics)
    registry.register(34, "Preserve formal FI source classification metadata", _v34_pnl_source_classification_metadata)
    registry.register(35, "Preserve bond analytics value date", _v35_bond_analytics_value_date)


def apply_pending_migrations_on_connection(conn: duckdb.DuckDBPyConnection) -> None:
    """Idempotent: apply any pending versioned migrations on this open connection."""
    registry = DuckDBSchemaRegistry(db_path=main_database_file_path(conn) or ":memory:")
    register_all(registry)
    registry.apply_pending(conn=conn)
