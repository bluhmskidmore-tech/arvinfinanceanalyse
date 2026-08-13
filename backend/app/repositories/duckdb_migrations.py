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


def _connection_has_explicit_transaction(conn: duckdb.DuckDBPyConnection) -> bool:
    """Detect whether the caller already owns the active DuckDB transaction."""
    first_id = conn.execute("select txid_current()").fetchone()[0]
    second_id = conn.execute("select txid_current()").fetchone()[0]
    return first_id == second_id


def _ensure_fx_daily_mid_head_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Restore the FX head schema and constraints using the governed registry DDL."""
    caller_owns_transaction = _connection_has_explicit_transaction(conn)
    transaction_started = False
    try:
        if not caller_owns_transaction:
            conn.execute("begin transaction")
            transaction_started = True

        _run_sql_slice(conn, "10_fx_mid.sql")
        if _main_table_exists(conn, "fx_daily_mid"):
            key_columns = ("trade_date", "base_currency", "quote_currency")
            nullable_columns = [
                column
                for column in key_columns
                if (
                    conn.execute(
                        """
                        select is_nullable
                        from information_schema.columns
                        where table_schema = 'main' and table_name = 'fx_daily_mid' and column_name = ?
                        """,
                        [column],
                    ).fetchone()
                    or (None,)
                )[0]
                == "YES"
            ]
            if nullable_columns:
                conn.execute("drop index if exists idx_fx_daily_mid_trade_date_base_currency")
                conn.execute("drop index if exists uq_fx_daily_mid_natural_key")
                for column in nullable_columns:
                    conn.execute(f"alter table fx_daily_mid alter column {column} set not null")
            _v30_fact_snapshot_indexes(conn)
            conn.execute(
                """
                create unique index if not exists uq_fx_daily_mid_natural_key
                on fx_daily_mid (trade_date, base_currency, quote_currency)
                """
            )

        if transaction_started:
            conn.execute("commit")
            transaction_started = False
    except Exception:
        if transaction_started:
            conn.execute("rollback")
        raise


def ensure_fx_daily_mid_schema_if_missing(conn: duckdb.DuckDBPyConnection) -> None:
    """Re-apply fx DDL when the table is missing (e.g. dropped) but migrations are already recorded."""
    _ensure_fx_daily_mid_head_schema(conn)


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
        "alter table fact_formal_risk_tensor_daily add column if not exists missing_maturity_market_value decimal(24, 8)",
        "alter table fact_formal_risk_tensor_daily add column if not exists missing_maturity_count integer",
        "alter table fact_formal_risk_tensor_daily add column if not exists floating_rate_proxy_market_value decimal(24, 8)",
        "alter table fact_formal_risk_tensor_daily add column if not exists floating_rate_proxy_count integer",
        "alter table fact_formal_risk_tensor_daily add column if not exists payment_frequency_fallback_market_value decimal(24, 8)",
        "alter table fact_formal_risk_tensor_daily add column if not exists payment_frequency_fallback_count integer",
        "alter table fact_formal_risk_tensor_daily add column if not exists bullet_value_date_fallback_market_value decimal(24, 8)",
        "alter table fact_formal_risk_tensor_daily add column if not exists bullet_value_date_fallback_count integer",
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


def _v36_risk_tensor_projection_quality(conn: duckdb.DuckDBPyConnection) -> None:
    if not _main_table_exists(conn, "fact_formal_risk_tensor_daily"):
        _run_sql_slice(conn, "04_risk_tensor.sql")
        return
    _run_sql_slice(conn, "37_risk_tensor_projection_quality.sql")



def _v37_bond_payment_frequency_fallback_provenance(conn: duckdb.DuckDBPyConnection) -> None:
    if not _main_table_exists(conn, "fact_formal_bond_analytics_daily"):
        _run_sql_slice(conn, "02_bond_analytics.sql")
        return
    _run_sql_slice(conn, "38_bond_analytics_payment_frequency_provenance.sql")


def _v38_stock_official_disclosure(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "39_stock_official_disclosure.sql")


def _v39_stock_official_disclosure_timestamp_tz(conn: duckdb.DuckDBPyConnection) -> None:
    """Repair v38 tables created with plain TIMESTAMP wall-clock columns.

    The v38 DDL now declares TIMESTAMPTZ for all four operational timestamps,
    but a database that already recorded v38 may still have the earlier plain
    TIMESTAMP shape. Interpret those legacy values in the project's
    Asia/Shanghai business timezone exactly once; fresh v38 tables and already
    repaired columns are left untouched.
    """
    _v38_stock_official_disclosure(conn)
    targets = (
        ("fact_stock_official_disclosure", "received_at"),
        ("fact_stock_official_disclosure", "ingested_at"),
        ("stock_official_disclosure_sync_status", "last_attempt_at"),
        ("stock_official_disclosure_sync_status", "last_success_at"),
    )
    legacy_targets: list[tuple[str, str]] = []
    for table_name, column_name in targets:
        row = conn.execute(
            """
            select data_type
            from information_schema.columns
            where table_schema = 'main' and table_name = ? and column_name = ?
            """,
            [table_name, column_name],
        ).fetchone()
        if row is None:
            continue
        data_type = " ".join(str(row[0]).upper().split())
        if data_type not in {"TIMESTAMP", "TIMESTAMP WITHOUT TIME ZONE"}:
            continue
        legacy_targets.append((table_name, column_name))

    if not legacy_targets:
        return

    # DuckDB treats indexes as dependencies of ALTER COLUMN. Drop and rebuild
    # the v38 indexes only for the legacy repair path; fresh TIMESTAMPTZ tables
    # stay a true no-op.
    for index_name in (
        "idx_fact_stock_official_disclosure_code_publish_date",
        "idx_fact_stock_official_disclosure_code_type_publish_date",
        "idx_fact_stock_official_disclosure_type_period_publish_date",
    ):
        conn.execute(f"drop index if exists {index_name}")
    for table_name, column_name in legacy_targets:
        conn.execute(
            f"alter table {table_name} alter column {column_name} "
            "set data type timestamptz "
            f"using {column_name} at time zone 'Asia/Shanghai'"
        )
    _v38_stock_official_disclosure(conn)


def _v40_stock_limit_price_daily(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "40_stock_limit_price_daily.sql")


def _v41_livermore_gate_history(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "41_livermore_gate_history.sql")


def _v42_accounting_movement_control_conclusion(conn: duckdb.DuckDBPyConnection) -> None:
    if not _main_table_exists(conn, "fact_accounting_asset_movement_monthly"):
        _run_sql_slice(conn, "18_accounting_asset_movement.sql")
    _run_sql_slice(conn, "42_accounting_movement_control_conclusion.sql")


_V43_RECOVERY_SQL: dict[str, str] = {
    "fact_formal_bond_analytics_daily": "02_bond_analytics.sql",
    "fact_formal_zqtz_balance_daily": "05_balance_analysis.sql",
    "fact_formal_tyw_balance_daily": "05_balance_analysis.sql",
    "fact_formal_risk_tensor_daily": "04_risk_tensor.sql",
    "fact_nonstd_pnl_bridge": "07_pnl_materialize.sql",
}

_V43_STATEMENT = re.compile(
    r"\s*create\s+unique\s+index\s+if\s+not\s+exists\s+"
    r"([a-z_][a-z0-9_]*)\s+on\s+([a-z_][a-z0-9_]*)\s*\((.+)\)\s*$",
    re.IGNORECASE | re.DOTALL,
)
_V43_BARE_COLUMN = re.compile(r"^[a-z_][a-z0-9_]*$", re.IGNORECASE)
# coalesce(cast(<column> as varchar), '<sentinel>'): the cast keeps one sentinel
# literal valid for both the DATE and VARCHAR flavours of maturity_date that
# different database vintages carry.
_V43_COALESCE_PART = re.compile(
    r"^coalesce\(\s*(cast\(\s*([a-z_][a-z0-9_]*)\s+as\s+varchar\s*\))\s*,\s*(.+?)\s*\)$",
    re.IGNORECASE | re.DOTALL,
)


def _v43_split_key_parts(key_text: str) -> list[str]:
    """Split an index key list on top-level commas (coalesce(...) contains commas)."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for character in key_text:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        if character == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(character)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _v43_constraint_statements() -> list[tuple[str, str, str, tuple[tuple[str, str, str], ...]]]:
    """Parse slice 43 into (statement, index_name, table_name, key_parts).

    Each key part is ``(column, index_expression, collision_predicate)``. The
    predicate is the SQL that finds rows already carrying the sentinel value; a
    bare column yields an empty predicate and is rejected downstream.
    """
    text = (REGISTRY_DIR / "43_core_fact_natural_key_constraints.sql").read_text(encoding="utf-8")
    specs: list[tuple[str, str, str, tuple[tuple[str, str, str], ...]]] = []
    for statement in parse_registry_sql_text(text):
        body = "\n".join(
            line for line in statement.splitlines() if not line.lstrip().startswith("--")
        ).strip()
        match = _V43_STATEMENT.fullmatch(body)
        if not match:
            raise RuntimeError(f"Unsupported v43 constraint statement: {statement}")
        index_name = match.group(1)
        table_name = match.group(2)
        key_parts: list[tuple[str, str, str]] = []
        for part in _v43_split_key_parts(match.group(3)):
            if _V43_BARE_COLUMN.fullmatch(part):
                key_parts.append((part, part, ""))
                continue
            coalesced = _V43_COALESCE_PART.fullmatch(part)
            if coalesced is None:
                raise RuntimeError(f"Unsupported v43 key expression: {part!r}")
            inner, column, sentinel = coalesced.groups()
            key_parts.append((column, part, f"{inner} = {sentinel}"))
        if not key_parts:
            raise RuntimeError(f"v43 constraint statement without key columns: {statement}")
        specs.append((body, index_name, table_name, tuple(key_parts)))
    return specs


def _v43_add_core_fact_natural_key_constraints(conn: duckdb.DuckDBPyConnection) -> None:
    """Constrain the core ALM fact grains that only had delete-then-insert protection.

    Deliberate deviation from the v32 pattern: v32 promoted its key columns to
    NOT NULL and aborted on any NULL. These facts are declared fully nullable and
    ``maturity_date`` is legitimately unknown for 7.5% of bond rows, so instead of
    demanding cleanup the key folds every column onto a sentinel. That is not
    cosmetic — DuckDB treats NULL as DISTINCT inside a unique index, so an
    unwrapped nullable column would exempt its NULL rows from the constraint
    entirely. The duplicate preflight below runs over the same folded expressions,
    which makes it strictly stronger than the v32 check it is modelled on.
    """
    specs = _v43_constraint_statements()
    spec_tables = [table_name for _statement, _index_name, table_name, _parts in specs]
    if len(spec_tables) != len(set(spec_tables)) or set(spec_tables) != set(_V43_RECOVERY_SQL):
        raise RuntimeError(
            "v43 constraint SQL must contain exactly one statement per governed core fact table"
        )

    missing_tables = {
        table_name
        for _statement, _index_name, table_name, _parts in specs
        if not _main_table_exists(conn, table_name)
    }

    # Preflight every existing table before any DDL so a defect cannot leave the
    # database half-constrained.
    for _statement, _index_name, table_name, key_parts in specs:
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
        missing_columns = [
            column for column, _expression, _sentinel in key_parts if column not in existing_columns
        ]
        if missing_columns:
            raise RuntimeError(
                f"v43 constraint target {table_name} is missing columns: "
                f"{', '.join(missing_columns)}"
            )

        for column, _expression, collision_predicate in key_parts:
            if not collision_predicate:
                raise RuntimeError(
                    f"v43 key column {table_name}.{column} is indexed bare; a nullable column "
                    "must be folded onto a sentinel or its NULL rows escape the constraint"
                )
            # A sentinel that already occurs as real data would merge a genuine
            # value with "unknown" and reject a legitimate row.
            collision_row = conn.execute(
                f"select count(*) from {table_name} where {collision_predicate}"
            ).fetchone()
            collision_count = int(collision_row[0]) if collision_row else 0
            if collision_count:
                raise RuntimeError(
                    f"{table_name}.{column} contains {collision_count} rows matching the v43 "
                    f"NULL sentinel ({collision_predicate}); pick a value outside the domain"
                )

        key_expression = ", ".join(expression for _column, expression, _predicate in key_parts)
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
                f"{table_name} has {duplicate_count} duplicate natural-key groups "
                f"for ({key_expression}); do NOT deduplicate — investigate the grain first"
            )

    for _statement, _index_name, table_name, _parts in specs:
        if table_name in missing_tables:
            _run_sql_slice(conn, _V43_RECOVERY_SQL[table_name])

    for statement, _index_name, _table_name, _parts in specs:
        conn.execute(statement)


def _v44_choice_stock_concept_membership_interval(conn: duckdb.DuckDBPyConnection) -> None:
    _run_sql_slice(conn, "44_choice_stock_concept_membership_interval.sql")


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


# --- Schema ledger note (three-way alignment; enforced by
# --- tests/test_schema_registry_consistency.py) -------------------------------
#
# Migration version numbers and registry slice file numbers drifted
# historically and BOTH numbering sequences are now frozen. Do not renumber
# either side retroactively: existing databases already recorded the current
# version numbers in _schema_migrations, and v30 was once reused in an
# existing database (see the recovery note inside _v32_add_table_constraints).
# Known offsets, for example: _v25 runs slice 24 (cffex member rank), _v26
# runs slice 25 (pnl by business precompute), _v30 runs slice 32 (fact
# snapshot indexes), _v31 runs slice 33 (market breadth daily), and slice
# number 26 was never issued.
#
# Lazy-ensure exemptions (slices intentionally NOT registered below):
#   * slice 30 (stock adjustment factor), ensured lazily by
#     backend.app.core_finance.adjusted_returns.ensure_stock_adjustment_factor_schema;
#     production callsites: backend/app/tasks/livermore_candidate_history_materialize.py
#     and scripts/backfill_stock_adjustment_factor.py.
#   * slice 31 (livermore matched baseline), ensured lazily by
#     backend.app.core_finance.matched_baseline.ensure_livermore_matched_baseline_schema;
#     called inside the matched-baseline generate and materialize paths of
#     backend/app/core_finance/matched_baseline.py.
# Reason: the baseline is frozen at v39 and appending new versions solely for
# registration would mutate production migration history for schemas that
# every runtime path already ensures. The authoritative exemption records are
# the lazy_ensure_exempt entries in backend/app/schema_registry/duckdb/manifest.json.
# ------------------------------------------------------------------------------


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
    registry.register(36, "Disclose risk tensor projection quality proxies", _v36_risk_tensor_projection_quality)
    registry.register(37, "Preserve bond payment-frequency fallback provenance", _v37_bond_payment_frequency_fallback_provenance)
    registry.register(38, "Stock official disclosure fact + sync status", _v38_stock_official_disclosure)
    registry.register(39, "Repair stock official disclosure timestamp timezone", _v39_stock_official_disclosure_timestamp_tz)
    registry.register(40, "Numeric daily limit prices from tushare stk_limit", _v40_stock_limit_price_daily)
    registry.register(41, "Livermore market-gate realtime label anchor", _v41_livermore_gate_history)
    registry.register(42, "Persist movement chain-continuity and position-source conclusions", _v42_accounting_movement_control_conclusion)
    registry.register(43, "Constrain core ALM fact natural-key grains", _v43_add_core_fact_natural_key_constraints)
    registry.register(44, "Point-in-time concept membership SCD intervals", _v44_choice_stock_concept_membership_interval)


def apply_pending_migrations_on_connection(conn: duckdb.DuckDBPyConnection) -> None:
    """Idempotent: apply any pending versioned migrations on this open connection."""
    registry = DuckDBSchemaRegistry(db_path=main_database_file_path(conn) or ":memory:")
    register_all(registry)
    registry.apply_pending(conn=conn)
