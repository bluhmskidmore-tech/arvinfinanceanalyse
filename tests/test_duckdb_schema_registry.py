"""Verify DuckDB schema registry applies versioned migrations correctly."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest
from backend.app.repositories.duckdb_migrations import (
    ensure_fx_daily_mid_schema_if_missing,
    _v32_add_table_constraints,
    _v36_risk_tensor_projection_quality,
    _v37_bond_payment_frequency_fallback_provenance,
    register_all,
)
from backend.app.repositories.duckdb_schema_registry import DuckDBSchemaRegistry

_BASELINE_VERSION_COUNT = 39
_RISK_PROJECTION_QUALITY_COLUMNS = {
    "missing_maturity_market_value",
    "missing_maturity_count",
    "floating_rate_proxy_market_value",
    "floating_rate_proxy_count",
    "payment_frequency_fallback_market_value",
    "payment_frequency_fallback_count",
    "bullet_value_date_fallback_market_value",
    "bullet_value_date_fallback_count",
}


def test_apply_pending_on_fresh_db(tmp_path) -> None:
    """All baseline migrations apply to an empty DuckDB file."""
    db_path = tmp_path / "registry_fresh.duckdb"
    registry = DuckDBSchemaRegistry(db_path=str(db_path))
    register_all(registry)
    applied = registry.apply_pending()
    assert len(applied) == _BASELINE_VERSION_COUNT

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        names = {
            row[0]
            for row in conn.execute(
                "select table_name from information_schema.tables where table_schema = 'main'"
            ).fetchall()
        }
        indexes = {
            row[0]
            for row in conn.execute(
                "select index_name from duckdb_indexes() "
                "where table_name = 'fact_stock_official_disclosure'"
            ).fetchall()
        }
    finally:
        conn.close()

    assert "zqtz_bond_daily_snapshot" in names
    assert "fact_formal_bond_analytics_daily" in names
    assert "fx_daily_mid" in names
    assert "fact_commodity_futures_daily" in names
    assert "fact_stock_official_disclosure" in names
    assert "stock_official_disclosure_sync_status" in names
    assert "_schema_migrations" in names

    assert indexes == {
        "idx_fact_stock_official_disclosure_code_publish_date",
        "idx_fact_stock_official_disclosure_code_type_publish_date",
        "idx_fact_stock_official_disclosure_type_period_publish_date",
    }


def test_idempotent_apply(tmp_path) -> None:
    """Running apply_pending twice produces no errors; second run applies nothing."""
    db_path = tmp_path / "registry_idempotent.duckdb"
    registry = DuckDBSchemaRegistry(db_path=str(db_path))
    register_all(registry)
    assert len(registry.apply_pending()) == _BASELINE_VERSION_COUNT

    registry2 = DuckDBSchemaRegistry(db_path=str(db_path))
    register_all(registry2)
    assert registry2.apply_pending() == []


def test_stock_official_disclosure_upgrade_from_v37_is_idempotent(tmp_path) -> None:
    db_path = tmp_path / "registry_stock_official_upgrade.duckdb"
    registry = DuckDBSchemaRegistry(db_path=str(db_path))
    register_all(registry)
    assert len(registry.apply_pending()) == _BASELINE_VERSION_COUNT

    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute("drop table fact_stock_official_disclosure")
        conn.execute("drop table stock_official_disclosure_sync_status")
        conn.execute("delete from _schema_migrations where version in (38, 39)")
    finally:
        conn.close()

    upgraded = DuckDBSchemaRegistry(db_path=str(db_path))
    register_all(upgraded)
    assert upgraded.apply_pending() == [
        "v38: Stock official disclosure fact + sync status",
        "v39: Repair stock official disclosure timestamp timezone",
    ]
    assert upgraded.apply_pending() == []
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        assert conn.execute(
            "select count(*) from information_schema.tables "
            "where table_name in ('fact_stock_official_disclosure', 'stock_official_disclosure_sync_status')"
        ).fetchone() == (2,)
    finally:
        conn.close()


def test_v39_repairs_pre_recorded_v38_plain_timestamps_as_shanghai_wall_clock(tmp_path) -> None:
    """A v38-recorded legacy table gets only the v39 timezone repair."""
    db_path = tmp_path / "registry_stock_official_timestamp_upgrade.duckdb"
    registry = DuckDBSchemaRegistry(db_path=str(db_path))
    register_all(registry)
    assert len(registry.apply_pending()) == _BASELINE_VERSION_COUNT

    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute("delete from _schema_migrations where version = 39")
        conn.execute("drop index idx_fact_stock_official_disclosure_code_publish_date")
        conn.execute("drop index idx_fact_stock_official_disclosure_code_type_publish_date")
        conn.execute("drop index idx_fact_stock_official_disclosure_type_period_publish_date")
        for table_name, column_name in (
            ("fact_stock_official_disclosure", "received_at"),
            ("fact_stock_official_disclosure", "ingested_at"),
            ("stock_official_disclosure_sync_status", "last_attempt_at"),
            ("stock_official_disclosure_sync_status", "last_success_at"),
        ):
            conn.execute(
                f"alter table {table_name} alter column {column_name} "
                "set data type timestamp using "
                f"{column_name} at time zone 'Asia/Shanghai'"
            )
        conn.execute(
            """
            insert into fact_stock_official_disclosure (
              disclosure_key, stock_code, stock_name, evidence_type,
              publish_date, report_period, title, document_url, source_id,
              source_label, source_version, vendor_version, received_at,
              ingested_at, run_id, raw_json
            ) values (
              'legacy-key', '688072.SH', '拓荆科技', 'official_announcement',
              '2026-04-20', null, 'legacy', 'https://example.com/legacy.pdf',
              'legacy-source', '上市公司公告原文（Tushare）', 'sv_old', 'vv_old',
              '2026-04-20 18:00:00', '2026-04-20 18:00:00', 'run-old', '{}'
            )
            """
        )
        conn.execute(
            """
            insert into stock_official_disclosure_sync_status (
              stock_code, requested_from_date, covered_through_date,
              last_attempt_at, last_success_at, status, fetched_count,
              upserted_count, error, run_id, source_version
            ) values (
              '688072.SH', '2026-01-01', '2026-06-30',
              '2026-04-20 18:00:00', '2026-04-20 18:00:00', 'success',
              1, 1, null, 'run-old', 'sv_old'
            )
            """
        )
    finally:
        conn.close()

    upgraded = DuckDBSchemaRegistry(db_path=str(db_path))
    register_all(upgraded)
    assert upgraded.apply_pending() == ["v39: Repair stock official disclosure timestamp timezone"]
    assert upgraded.apply_pending() == []

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        types = {
            (row[0], row[1]): row[2]
            for row in conn.execute(
                """
                select table_name, column_name, data_type
                from information_schema.columns
                where table_schema = 'main'
                  and (
                    (table_name = 'fact_stock_official_disclosure' and column_name in ('received_at', 'ingested_at'))
                    or (table_name = 'stock_official_disclosure_sync_status' and column_name in ('last_attempt_at', 'last_success_at'))
                  )
                """
            ).fetchall()
        }
        instants = conn.execute(
            """
            select
              epoch(received_at), epoch(ingested_at)
            from fact_stock_official_disclosure
            where disclosure_key = 'legacy-key'
            """
        ).fetchone()
        sync_instants = conn.execute(
            """
            select epoch(last_attempt_at), epoch(last_success_at)
            from stock_official_disclosure_sync_status
            where stock_code = '688072.SH'
            """
        ).fetchone()
    finally:
        conn.close()

    expected_epoch = datetime(2026, 4, 20, 10, 0, tzinfo=UTC).timestamp()
    assert set(types.values()) == {"TIMESTAMP WITH TIME ZONE"}
    assert instants == (expected_epoch, expected_epoch)
    assert sync_instants == (expected_epoch, expected_epoch)


def test_existing_autocommit_connection_rolls_back_failed_migration() -> None:
    conn = duckdb.connect(":memory:")
    try:
        registry = DuckDBSchemaRegistry(db_path=":memory:")

        def broken_migration(open_conn: duckdb.DuckDBPyConnection) -> None:
            open_conn.execute("create table partial_v1 (value integer)")
            raise RuntimeError("forced migration failure")

        registry.register(1, "broken migration", broken_migration)
        with pytest.raises(RuntimeError, match="forced migration failure"):
            registry.apply_pending(conn=conn)

        tables = {
            row[0]
            for row in conn.execute(
                "select table_name from information_schema.tables where table_schema = 'main'"
            ).fetchall()
        }
        assert "partial_v1" not in tables
        assert conn.execute(
            "select count(*) from _schema_migrations where version = 1"
        ).fetchone() == (0,)
    finally:
        conn.close()


def test_existing_explicit_transaction_failed_migration_rolls_back_caller_work() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute("create table caller_state (value integer)")
        conn.execute(
            """
            create table _schema_migrations (
              version integer primary key,
              description text not null
            )
            """
        )
        registry = DuckDBSchemaRegistry(db_path=":memory:")
        migration_ran = False

        def broken_migration(open_conn: duckdb.DuckDBPyConnection) -> None:
            nonlocal migration_ran
            migration_ran = True
            open_conn.execute("create table partial_v1 (value integer)")
            raise RuntimeError("forced migration failure")

        registry.register(1, "broken migration", broken_migration)

        conn.execute("begin transaction")
        conn.execute("insert into caller_state values (1)")
        with pytest.raises(RuntimeError) as exc_info:
            registry.apply_pending(conn=conn)
        conn.execute("commit")

        assert migration_ran is True
        assert str(exc_info.value) == "forced migration failure"
        tables = {
            row[0]
            for row in conn.execute(
                "select table_name from information_schema.tables where table_schema = 'main'"
            ).fetchall()
        }
        assert "partial_v1" not in tables
        assert conn.execute("select * from caller_state").fetchall() == []
        assert conn.execute(
            "select count(*) from _schema_migrations where version = 1"
        ).fetchone() == (0,)
    finally:
        conn.close()


def test_existing_explicit_transaction_success_remains_owned_by_caller() -> None:
    conn = duckdb.connect(":memory:")
    try:
        registry = DuckDBSchemaRegistry(db_path=":memory:")
        registry.register(
            1,
            "caller-owned migration",
            lambda open_conn: open_conn.execute("create table caller_owned_v1 (value integer)"),
        )

        conn.execute("begin transaction")
        assert registry.apply_pending(conn=conn) == ["v1: caller-owned migration"]
        assert conn.execute(
            "select count(*) from information_schema.tables where table_name = 'caller_owned_v1'"
        ).fetchone() == (1,)
        conn.execute("rollback")

        assert conn.execute(
            "select count(*) from information_schema.tables where table_name = 'caller_owned_v1'"
        ).fetchone() == (0,)
    finally:
        conn.close()


def test_existing_explicit_transaction_with_no_pending_migration_remains_owned_by_caller() -> None:
    conn = duckdb.connect(":memory:")
    try:
        registry = DuckDBSchemaRegistry(db_path=":memory:")
        registry.register(
            1,
            "caller-owned migration",
            lambda open_conn: open_conn.execute("create table caller_owned_v1 (value integer)"),
        )
        assert registry.apply_pending(conn=conn) == ["v1: caller-owned migration"]

        conn.execute("begin transaction")
        conn.execute("insert into caller_owned_v1 values (1)")
        assert registry.apply_pending(conn=conn) == []
        conn.execute("rollback")

        assert conn.execute("select count(*) from caller_owned_v1").fetchone() == (0,)
    finally:
        conn.close()


def test_migration_tracking(tmp_path) -> None:
    """Applied migrations are recorded in _schema_migrations table."""
    db_path = tmp_path / "registry_tracking.duckdb"
    registry = DuckDBSchemaRegistry(db_path=str(db_path))
    register_all(registry)
    registry.apply_pending()

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute(
            "select version, description from _schema_migrations order by version"
        ).fetchall()
        versions = [row[0] for row in rows]
    finally:
        conn.close()

    assert versions == list(range(1, _BASELINE_VERSION_COUNT + 1))
    assert len(rows) == _BASELINE_VERSION_COUNT
    assert any("snapshot" in str(row[1]).lower() for row in rows)
    assert rows[-1] == (39, "Repair stock official disclosure timestamp timezone")


def test_v36_adds_projection_quality_columns_without_backfilling_legacy_rows() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute("create table fact_formal_risk_tensor_daily (report_date varchar)")
        conn.execute("insert into fact_formal_risk_tensor_daily values ('2026-03-31')")

        _v36_risk_tensor_projection_quality(conn)

        columns = {
            str(row[1])
            for row in conn.execute(
                "pragma table_info('fact_formal_risk_tensor_daily')"
            ).fetchall()
        }
        legacy_values = conn.execute(
            "select "
            + ", ".join(sorted(_RISK_PROJECTION_QUALITY_COLUMNS))
            + " from fact_formal_risk_tensor_daily"
        ).fetchone()
    finally:
        conn.close()

    assert _RISK_PROJECTION_QUALITY_COLUMNS <= columns
    assert legacy_values == (None,) * len(_RISK_PROJECTION_QUALITY_COLUMNS)


def test_v37_adds_frequency_provenance_without_backfilling_legacy_rows() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(
            "create table fact_formal_bond_analytics_daily "
            "(report_date varchar, instrument_code varchar)"
        )
        conn.execute(
            "insert into fact_formal_bond_analytics_daily values ('2026-03-31', 'BOND-1')"
        )

        _v37_bond_payment_frequency_fallback_provenance(conn)

        columns = {
            str(row[1])
            for row in conn.execute(
                "pragma table_info('fact_formal_bond_analytics_daily')"
            ).fetchall()
        }
        legacy_value = conn.execute(
            "select interest_payment_frequency_fallback_used "
            "from fact_formal_bond_analytics_daily"
        ).fetchone()
    finally:
        conn.close()

    assert "interest_payment_frequency_fallback_used" in columns
    assert legacy_value == (None,)


def test_legacy_missing_zqtz_tables_can_still_recover_current_schema(tmp_path) -> None:
    """A macro-only legacy DB may record ZQTZ patch migrations before ZQTZ tables exist."""
    db_path = tmp_path / "legacy_macro_only.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table _schema_migrations (
              version integer primary key,
              description text not null,
              applied_at timestamp default current_timestamp
            )
            """
        )
        for version in range(1, 17):
            conn.execute(
                "insert into _schema_migrations (version, description) values (?, ?)",
                [version, "applied"],
            )
    finally:
        conn.close()

    registry = DuckDBSchemaRegistry(db_path=str(db_path))
    register_all(registry)
    registry.apply_pending()

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        zqtz_columns = {
            row[0]
            for row in conn.execute(
                """
                select column_name
                from information_schema.columns
                where table_schema = 'main' and table_name = 'zqtz_bond_daily_snapshot'
                """
            ).fetchall()
        }
        formal_columns = {
            row[0]
            for row in conn.execute(
                """
                select column_name
                from information_schema.columns
                where table_schema = 'main' and table_name = 'fact_formal_zqtz_balance_daily'
                """
            ).fetchall()
        }
    finally:
        conn.close()

    assert {"business_type_primary", "sub_type"} <= zqtz_columns
    assert {"business_type_primary", "sub_type"} <= formal_columns


def test_duckdb_migration_registry_keeps_explicit_latest_version_contract() -> None:
    source = Path(__file__).resolve().parents[1] / "backend" / "app" / "repositories" / "duckdb_migrations.py"
    versions = [int(match) for match in re.findall(r"registry\.register\((\d+),", source.read_text(encoding="utf-8"))]

    assert versions == list(range(1, _BASELINE_VERSION_COUNT + 1))


def _index_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {row[0] for row in conn.execute("select index_name from duckdb_indexes()").fetchall()}


def _create_pnl_constraint_fixture(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table fact_formal_pnl_fi (
          report_date varchar,
          instrument_code varchar,
          portfolio_name varchar,
          cost_center varchar,
          accounting_basis varchar,
          currency_basis varchar
        )
        """
    )
    conn.execute(
        "create index idx_fact_formal_pnl_fi_report_date "
        "on fact_formal_pnl_fi (report_date)"
    )


def test_v32_uses_full_pnl_grain_and_preserves_read_index() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _create_pnl_constraint_fixture(conn)
        conn.execute(
            """
            create table fx_daily_mid (
              trade_date date,
              base_currency varchar,
              quote_currency varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi values
              ('2026-06-30', 'BOND-001', 'P1', 'C1', 'AC', 'CNY'),
              ('2026-06-30', 'BOND-001', 'P1', 'C1', 'AC', 'CNX')
            """
        )

        _v32_add_table_constraints(conn)

        assert {
            "idx_fact_formal_pnl_fi_report_date",
            "uq_fact_formal_pnl_fi_natural_key",
        } <= _index_names(conn)
        nullable = {
            row[0]: row[1]
            for row in conn.execute(
                """
                select column_name, is_nullable
                from information_schema.columns
                where table_schema = 'main'
                  and table_name = 'fact_formal_pnl_fi'
                """
            ).fetchall()
        }
        assert all(nullable[column] == "NO" for column in nullable)

        with pytest.raises(duckdb.ConstraintException):
            conn.execute(
                """
                insert into fact_formal_pnl_fi values
                  ('2026-06-30', 'BOND-001', 'P1', 'C1', 'AC', 'CNY')
                """
            )
    finally:
        conn.close()


def test_v32_preflights_all_tables_before_schema_changes() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _create_pnl_constraint_fixture(conn)
        conn.execute(
            """
            insert into fact_formal_pnl_fi values
              ('2026-06-30', 'BOND-001', 'P1', 'C1', 'AC', 'CNY')
            """
        )
        conn.execute(
            """
            create table fx_daily_mid (
              trade_date date,
              base_currency varchar,
              quote_currency varchar
            )
            """
        )
        conn.execute(
            "create index idx_fx_daily_mid_trade_date_base_currency "
            "on fx_daily_mid (trade_date, base_currency)"
        )
        conn.execute("insert into fx_daily_mid values ('2026-06-30', null, 'CNY')")

        with pytest.raises(RuntimeError, match=r"fx_daily_mid\.base_currency.*NULL"):
            _v32_add_table_constraints(conn)

        assert "idx_fact_formal_pnl_fi_report_date" in _index_names(conn)
        assert "uq_fact_formal_pnl_fi_natural_key" not in _index_names(conn)
        assert conn.execute(
            """
            select is_nullable
            from information_schema.columns
            where table_schema = 'main'
              and table_name = 'fact_formal_pnl_fi'
              and column_name = 'report_date'
            """
        ).fetchone() == ("YES",)
        assert conn.execute(
            "select count(*) from fx_daily_mid where base_currency is null"
        ).fetchone() == (1,)
    finally:
        conn.close()


def test_v32_preflight_failure_does_not_recover_missing_table_in_caller_transaction() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _create_pnl_constraint_fixture(conn)
        conn.execute(
            """
            insert into fact_formal_pnl_fi values
              ('2026-06-30', 'BOND-001', 'P1', 'C1', 'AC', null)
            """
        )
        conn.execute(
            """
            create table _schema_migrations (
              version integer primary key,
              description text not null
            )
            """
        )

        conn.execute("begin transaction")
        try:
            with pytest.raises(
                RuntimeError,
                match=r"fact_formal_pnl_fi\.currency_basis.*NULL",
            ):
                _v32_add_table_constraints(conn)

            assert conn.execute(
                "select count(*) from information_schema.tables "
                "where table_schema = 'main' and table_name = 'fx_daily_mid'"
            ).fetchone() == (0,)
            assert conn.execute(
                "select count(*) from _schema_migrations where version = 32"
            ).fetchone() == (0,)
        finally:
            conn.execute("rollback")
    finally:
        conn.close()


def test_v32_duplicate_grain_fails_without_recording_migration(tmp_path) -> None:
    db_path = tmp_path / "registry_v32_duplicate.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _create_pnl_constraint_fixture(conn)
        conn.execute(
            """
            insert into fact_formal_pnl_fi values
              ('2026-06-30', 'BOND-001', 'P1', 'C1', 'AC', 'CNY'),
              ('2026-06-30', 'BOND-001', 'P1', 'C1', 'AC', 'CNY')
            """
        )
    finally:
        conn.close()

    registry = DuckDBSchemaRegistry(db_path=str(db_path))
    registry.register(32, "Constrain governed PnL and FX canonical grains", _v32_add_table_constraints)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        with pytest.raises(RuntimeError, match=r"fact_formal_pnl_fi.*duplicate"):
            registry.apply_pending(conn=conn)

        assert conn.execute(
            "select count(*) from _schema_migrations where version = 32"
        ).fetchone() == (0,)
        assert "idx_fact_formal_pnl_fi_report_date" in _index_names(conn)
        assert conn.execute("select count(*) from fact_formal_pnl_fi").fetchone() == (2,)
        assert conn.execute(
            "select count(*) from information_schema.tables where table_name = 'fx_daily_mid'"
        ).fetchone() == (0,)
    finally:
        conn.close()


def test_v32_existing_connection_rolls_back_constraint_ddl_failure() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _create_pnl_constraint_fixture(conn)
        conn.execute(
            """
            create table fx_daily_mid (
              trade_date date,
              base_currency varchar,
              quote_currency varchar
            )
            """
        )
        conn.execute(
            "create table fact_formal_zqtz_balance_daily (legacy_value varchar)"
        )
        registry = DuckDBSchemaRegistry(db_path=":memory:")
        registry.register(
            32,
            "Constrain governed PnL and FX canonical grains",
            _v32_add_table_constraints,
        )

        with pytest.raises(duckdb.BinderException):
            registry.apply_pending(conn=conn)

        assert conn.execute(
            """
            select is_nullable
            from information_schema.columns
            where table_name = 'fact_formal_pnl_fi' and column_name = 'report_date'
            """
        ).fetchone() == ("YES",)
        assert "idx_fact_formal_pnl_fi_report_date" in _index_names(conn)
        assert "uq_fact_formal_pnl_fi_natural_key" not in _index_names(conn)
        assert conn.execute(
            "select count(*) from _schema_migrations where version = 32"
        ).fetchone() == (0,)
    finally:
        conn.close()


def test_v32_recovers_v30_read_indexes_and_enforces_fx_grain() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _create_pnl_constraint_fixture(conn)
        conn.execute("drop index idx_fact_formal_pnl_fi_report_date")
        conn.execute("create table fact_formal_zqtz_balance_daily (report_date varchar)")
        conn.execute("create table fact_formal_bond_analytics_daily (report_date varchar)")
        conn.execute("create table zqtz_bond_daily_snapshot (report_date date)")
        conn.execute(
            """
            create table fx_daily_mid (
              trade_date date,
              base_currency varchar,
              quote_currency varchar
            )
            """
        )
        conn.execute("insert into fx_daily_mid values ('2026-06-30', 'USD', 'CNY')")

        _v32_add_table_constraints(conn)

        assert {
            "idx_fact_formal_pnl_fi_report_date",
            "idx_fact_formal_zqtz_balance_daily_report_date",
            "idx_fact_formal_bond_analytics_daily_report_date",
            "idx_zqtz_bond_daily_snapshot_report_date",
            "idx_fx_daily_mid_trade_date_base_currency",
            "uq_fx_daily_mid_natural_key",
        } <= _index_names(conn)
        with pytest.raises(duckdb.ConstraintException):
            conn.execute("insert into fx_daily_mid values ('2026-06-30', 'USD', 'CNY')")
    finally:
        conn.close()


def test_v32_replaces_same_name_legacy_pnl_unique_index() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _create_pnl_constraint_fixture(conn)
        conn.execute(
            """
            create unique index uq_fact_formal_pnl_fi_natural_key
            on fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center, accounting_basis
            )
            """
        )
        conn.execute(
            """
            create table fx_daily_mid (
              trade_date date,
              base_currency varchar,
              quote_currency varchar
            )
            """
        )

        _v32_add_table_constraints(conn)
        conn.execute(
            """
            insert into fact_formal_pnl_fi values
              ('2026-06-30', 'BOND-001', 'P1', 'C1', 'AC', 'CNY'),
              ('2026-06-30', 'BOND-001', 'P1', 'C1', 'AC', 'CNX')
            """
        )

        assert conn.execute("select count(*) from fact_formal_pnl_fi").fetchone() == (2,)
        with pytest.raises(duckdb.ConstraintException):
            conn.execute(
                """
                insert into fact_formal_pnl_fi values
                  ('2026-06-30', 'BOND-001', 'P1', 'C1', 'AC', 'CNY')
                """
            )
    finally:
        conn.close()


def test_v32_defers_unique_indexes_without_enforceable_grain_contract() -> None:
    sql_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "app"
        / "schema_registry"
        / "duckdb"
        / "34_add_table_constraints.sql"
    )
    sql = sql_path.read_text(encoding="utf-8")

    assert "uq_fact_formal_pnl_fi_natural_key" in sql
    assert (
        "on fact_formal_pnl_fi (report_date, instrument_code, portfolio_name, "
        "cost_center, accounting_basis, currency_basis)"
    ) in sql
    assert "uq_fx_daily_mid_natural_key" in sql
    assert "uq_fact_formal_zqtz_balance_daily_natural_key" not in sql
    assert "uq_zqtz_bond_daily_snapshot_natural_key" not in sql
    assert "uq_fact_formal_bond_analytics_daily_natural_key" not in sql


def test_ensure_fx_daily_mid_schema_if_missing_restores_indexes_after_drop() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(
            """
            create table fx_daily_mid (
              trade_date date,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(24, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              source_version varchar,
              vendor_name varchar,
              vendor_version varchar,
              vendor_series_code varchar,
              observed_trade_date date
            )
            """
        )
        conn.execute("drop table fx_daily_mid")

        ensure_fx_daily_mid_schema_if_missing(conn)

        columns = {
            row[0]: row[1]
            for row in conn.execute(
                """
                select column_name, is_nullable
                from information_schema.columns
                where table_schema = 'main' and table_name = 'fx_daily_mid'
                """
            ).fetchall()
        }
        assert {
            "idx_fx_daily_mid_trade_date_base_currency",
            "uq_fx_daily_mid_natural_key",
        } <= _index_names(conn)
        assert columns["trade_date"] == "NO"
        assert columns["base_currency"] == "NO"
        assert columns["quote_currency"] == "NO"

        conn.execute(
            """
            insert or replace into fx_daily_mid (
              trade_date,
              base_currency,
              quote_currency,
              mid_rate,
              source_name,
              is_business_day,
              is_carry_forward,
              source_version,
              vendor_name,
              vendor_version,
              vendor_series_code,
              observed_trade_date
            ) values (
              '2026-06-30',
              'USD',
              'CNY',
              7.2,
              'CFETS',
              true,
              false,
              'sv_fx_test',
              'choice',
              'v1',
              'EMM00058124',
              '2026-06-30'
            )
            """
        )

        with pytest.raises(duckdb.ConstraintException):
            conn.execute(
                """
                insert into fx_daily_mid (
                  trade_date,
                  base_currency,
                  quote_currency,
                  mid_rate,
                  source_name,
                  is_business_day,
                  is_carry_forward,
                  source_version,
                  vendor_name,
                  vendor_version,
                  vendor_series_code,
                  observed_trade_date
                ) values (
                  null,
                  'USD',
                  'CNY',
                  7.2,
                  'CFETS',
                  true,
                  false,
                  'sv_fx_test',
                  'choice',
                  'v1',
                  'EMM00058124',
                  '2026-06-30'
                )
                """
            )

        with pytest.raises(duckdb.ConstraintException):
            conn.execute(
                """
                insert into fx_daily_mid (
                  trade_date,
                  base_currency,
                  quote_currency,
                  mid_rate,
                  source_name,
                  is_business_day,
                  is_carry_forward,
                  source_version,
                  vendor_name,
                  vendor_version,
                  vendor_series_code,
                  observed_trade_date
                ) values (
                  '2026-06-30',
                  'USD',
                  'CNY',
                  7.2,
                  'CFETS',
                  true,
                  false,
                  'sv_fx_test',
                  'choice',
                  'v1',
                  'EMM00058124',
                  '2026-06-30'
                )
                """
            )

        assert conn.execute("select count(*) from fx_daily_mid").fetchone() == (1,)
    finally:
        conn.close()
