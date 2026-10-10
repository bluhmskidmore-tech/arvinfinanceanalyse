from __future__ import annotations

import importlib
from pathlib import Path

import duckdb
import pytest

from backend.app.duckdb_schema_bootstrap import upgrade_duckdb_schema_head
from backend.app.repositories.duckdb_migrations import (
    apply_pending_migrations_on_connection,
    apply_stock_analysis_current_rule_cohort_schema_on_connection,
)
from backend.app.schema_registry.duckdb_loader import (
    REGISTRY_DIR,
    load_manifest,
    parse_registry_sql_text,
)

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]

_CONTROLLED_PATH = (
    REGISTRY_DIR / "controlled" / "45_stock_analysis_current_rule_cohort.sql"
)
_EXPECTED_TABLES = {
    "stock_analysis_current_rule_cohort_manifest",
    "stock_analysis_current_rule_replay_fact",
    "stock_analysis_current_rule_date_certificate",
}
_EXPECTED_INDEXES = {
    "idx_sa_cr_manifest_page_mode_status",
    "idx_sa_cr_manifest_run",
    "idx_sa_cr_manifest_plan_digest",
    "uq_sa_cr_manifest_cohort_id",
    "uq_sa_cr_manifest_page_mode_idempotency",
    "idx_sa_cr_fact_cohort_date",
    "uq_sa_cr_fact_logical_key",
    "uq_sa_cr_cert_logical_key",
    "idx_sa_cr_cert_status",
}
_EXPECTED_NOT_NULL_COLUMNS = {
    "stock_analysis_current_rule_cohort_manifest": {
        "cohort_id",
        "page_id",
        "cohort_mode",
        "cohort_status",
        "run_id",
        "idempotency_key",
    },
    "stock_analysis_current_rule_replay_fact": {
        "cohort_id",
        "signal_date",
        "stock_code",
        "signal_kind",
    },
    "stock_analysis_current_rule_date_certificate": {
        "cohort_id",
        "trade_date",
        "certificate_status",
    },
}


def _main_table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "select table_name from information_schema.tables where table_schema = 'main'"
        ).fetchall()
    }


def _migration_versions(conn: duckdb.DuckDBPyConnection) -> list[int]:
    return [
        int(row[0])
        for row in conn.execute(
            "select version from _schema_migrations order by version"
        ).fetchall()
    ]


def _initialize_v45(conn: duckdb.DuckDBPyConnection) -> None:
    apply_pending_migrations_on_connection(conn)
    assert _migration_versions(conn) == list(range(1, 46))


def test_controlled_manifest_entry_is_explicit_and_not_auto_registered() -> None:
    manifest = load_manifest()
    controlled = manifest["controlled_migrations"]

    assert controlled == [
        {
            "migration_version": 46,
            "path": "controlled/45_stock_analysis_current_rule_cohort.sql",
            "ensure_module": "backend.app.repositories.duckdb_migrations",
            "ensure_symbol": "apply_stock_analysis_current_rule_cohort_schema_on_connection",
            "governance_state": "approved_controlled_only",
            "auto_registered": False,
            "required_predecessor_version": 45,
            "predecessor_ledger_must_be_complete": True,
        }
    ]
    entry = controlled[0]
    assert (REGISTRY_DIR / entry["path"]).is_file()
    target = getattr(
        importlib.import_module(entry["ensure_module"]), entry["ensure_symbol"]
    )
    assert target is apply_stock_analysis_current_rule_cohort_schema_on_connection


def test_controlled_sql_has_statement_boundaries_and_no_proposal_copy() -> None:
    statements = parse_registry_sql_text(_CONTROLLED_PATH.read_text(encoding="utf-8"))

    assert (
        len([statement for statement in statements if statement.startswith("create ")])
        == 12
    )
    assert not (
        REGISTRY_DIR / "proposals" / "45_stock_analysis_current_rule_cohort.sql"
    ).exists()


def test_default_connection_migration_stops_at_v45_without_controlled_tables() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _initialize_v45(conn)
        tables = _main_table_names(conn)
    finally:
        conn.close()

    assert _EXPECTED_TABLES.isdisjoint(tables)


def test_default_startup_bootstrap_stops_at_v45_without_controlled_tables(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "controlled_bootstrap_guard.duckdb"
    monkeypatch.delenv("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", raising=False)
    monkeypatch.delenv("MOSS_SKIP_POSTGRES_MIGRATIONS", raising=False)

    upgrade_duckdb_schema_head(duckdb_path=str(db_path))

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        versions = _migration_versions(conn)
        tables = _main_table_names(conn)
    finally:
        conn.close()

    assert versions == list(range(1, 46))
    assert _EXPECTED_TABLES.isdisjoint(tables)


def test_controlled_entry_applies_v46_idempotently_with_governed_keys() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _initialize_v45(conn)

        assert (
            apply_stock_analysis_current_rule_cohort_schema_on_connection(conn) is True
        )
        assert (
            apply_stock_analysis_current_rule_cohort_schema_on_connection(conn) is False
        )

        tables = _main_table_names(conn)
        versions = _migration_versions(conn)
        description = conn.execute(
            "select description from _schema_migrations where version = 46"
        ).fetchone()[0]
        indexes = {
            str(row[0])
            for row in conn.execute(
                """
                select index_name
                from duckdb_indexes()
                where schema_name = 'main'
                  and table_name like 'stock_analysis_current_rule_%'
                """
            ).fetchall()
        }
        nullability = {
            table_name: {
                str(column_name): str(is_nullable)
                for column_name, is_nullable in conn.execute(
                    """
                    select column_name, is_nullable
                    from information_schema.columns
                    where table_schema = 'main' and table_name = ?
                    """,
                    [table_name],
                ).fetchall()
            }
            for table_name in _EXPECTED_NOT_NULL_COLUMNS
        }
    finally:
        conn.close()

    assert _EXPECTED_TABLES <= tables
    assert _EXPECTED_INDEXES <= indexes
    assert versions == list(range(1, 47))
    assert description == "Controlled stock-analysis current-rule cohort storage"
    for table_name, columns in _EXPECTED_NOT_NULL_COLUMNS.items():
        assert all(nullability[table_name][column] == "NO" for column in columns)


def test_controlled_entry_fails_closed_without_complete_v45_ledger() -> None:
    conn = duckdb.connect(":memory:")
    try:
        with pytest.raises(RuntimeError, match="existing _schema_migrations"):
            apply_stock_analysis_current_rule_cohort_schema_on_connection(conn)
        assert "_schema_migrations" not in _main_table_names(conn)

        _initialize_v45(conn)
        conn.execute("delete from _schema_migrations where version = 23")
        with pytest.raises(RuntimeError, match="missing predecessor versions 23"):
            apply_stock_analysis_current_rule_cohort_schema_on_connection(conn)
        versions = _migration_versions(conn)
        tables = _main_table_names(conn)
    finally:
        conn.close()

    assert 46 not in versions
    assert _EXPECTED_TABLES.isdisjoint(tables)


def test_controlled_entry_rejects_unexpected_future_ledger_versions() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _initialize_v45(conn)
        conn.execute(
            "insert into _schema_migrations(version, description) values (47, 'unknown future')"
        )

        with pytest.raises(RuntimeError, match="unexpected versions 47"):
            apply_stock_analysis_current_rule_cohort_schema_on_connection(conn)

        assert 46 not in _migration_versions(conn)
        assert _EXPECTED_TABLES.isdisjoint(_main_table_names(conn))
    finally:
        conn.close()


def test_controlled_entry_rolls_back_v46_with_caller_transaction() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _initialize_v45(conn)
        conn.execute("begin transaction")
        assert (
            apply_stock_analysis_current_rule_cohort_schema_on_connection(conn) is True
        )
        assert 46 in _migration_versions(conn)
        conn.execute("rollback")

        assert 46 not in _migration_versions(conn)
        assert _EXPECTED_TABLES.isdisjoint(_main_table_names(conn))
        assert (
            apply_stock_analysis_current_rule_cohort_schema_on_connection(conn) is True
        )
    finally:
        conn.close()


def test_controlled_entry_does_not_certify_a_preexisting_partial_table() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _initialize_v45(conn)
        conn.execute(
            "create table stock_analysis_current_rule_cohort_manifest (cohort_id varchar)"
        )

        with pytest.raises(RuntimeError, match="partial preexisting schema"):
            apply_stock_analysis_current_rule_cohort_schema_on_connection(conn)

        assert 46 not in _migration_versions(conn)
        tables = _main_table_names(conn)
    finally:
        conn.close()

    assert "stock_analysis_current_rule_cohort_manifest" in tables
    assert "stock_analysis_current_rule_replay_fact" not in tables
    assert "stock_analysis_current_rule_date_certificate" not in tables


def test_controlled_entry_rejects_preexisting_schema_missing_business_column() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _initialize_v45(conn)
        sql_text = _CONTROLLED_PATH.read_text(encoding="utf-8")
        incomplete_sql_text = sql_text.replace(
            "  receipt_sha256 varchar,\n",
            "",
            1,
        )
        assert incomplete_sql_text != sql_text
        for statement in parse_registry_sql_text(incomplete_sql_text):
            conn.execute(statement)

        with pytest.raises(RuntimeError, match="missing columns: receipt_sha256"):
            apply_stock_analysis_current_rule_cohort_schema_on_connection(conn)

        assert 46 not in _migration_versions(conn)
        assert _EXPECTED_TABLES <= _main_table_names(conn)
    finally:
        conn.close()


def test_controlled_entry_rejects_preexisting_schema_with_wrong_business_type() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _initialize_v45(conn)
        sql_text = _CONTROLLED_PATH.read_text(encoding="utf-8")
        incompatible_sql_text = sql_text.replace(
            "  receipt_sha256 varchar,\n",
            "  receipt_sha256 integer,\n",
            1,
        )
        assert incompatible_sql_text != sql_text
        for statement in parse_registry_sql_text(incompatible_sql_text):
            conn.execute(statement)

        with pytest.raises(
            RuntimeError,
            match=r"incompatible column types: .*receipt_sha256 .*expected VARCHAR, got INTEGER",
        ):
            apply_stock_analysis_current_rule_cohort_schema_on_connection(conn)

        assert 46 not in _migration_versions(conn)
        assert _EXPECTED_TABLES <= _main_table_names(conn)
    finally:
        conn.close()


def test_controlled_entry_rejects_wrong_preexisting_unique_index_definitions() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _initialize_v45(conn)
        for statement in parse_registry_sql_text(_CONTROLLED_PATH.read_text(encoding="utf-8")):
            conn.execute(statement)

        for index_name in (
            "uq_sa_cr_manifest_cohort_id",
            "uq_sa_cr_manifest_page_mode_idempotency",
            "uq_sa_cr_fact_logical_key",
            "uq_sa_cr_cert_logical_key",
        ):
            conn.execute(f"drop index {index_name}")
        conn.execute(
            "create unique index uq_sa_cr_manifest_cohort_id "
            "on stock_analysis_current_rule_cohort_manifest(page_id)"
        )
        conn.execute(
            "create unique index uq_sa_cr_manifest_page_mode_idempotency "
            "on stock_analysis_current_rule_cohort_manifest(cohort_status)"
        )
        conn.execute(
            "create unique index uq_sa_cr_fact_logical_key "
            "on stock_analysis_current_rule_replay_fact(signal_kind)"
        )
        conn.execute(
            "create unique index uq_sa_cr_cert_logical_key "
            "on stock_analysis_current_rule_date_certificate(certificate_status)"
        )

        with pytest.raises(RuntimeError, match="mismatched unique natural-key indexes"):
            apply_stock_analysis_current_rule_cohort_schema_on_connection(conn)

        assert 46 not in _migration_versions(conn)
    finally:
        conn.close()


def test_controlled_natural_keys_reject_nulls_and_duplicates() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _initialize_v45(conn)
        apply_stock_analysis_current_rule_cohort_schema_on_connection(conn)

        conn.execute(
            """
            insert into stock_analysis_current_rule_cohort_manifest (
              cohort_id, page_id, cohort_mode, cohort_status, run_id, idempotency_key
            ) values ('cohort-1', 'stock-analysis', 'current_rule', 'draft', 'run-1', 'idem-1')
            """
        )
        with pytest.raises(duckdb.ConstraintException):
            conn.execute(
                """
                insert into stock_analysis_current_rule_cohort_manifest (
                  cohort_id, page_id, cohort_mode, cohort_status, run_id, idempotency_key
                ) values ('cohort-1', 'stock-analysis', 'current_rule', 'draft', 'run-2', 'idem-2')
                """
            )
        with pytest.raises(duckdb.ConstraintException):
            conn.execute(
                """
                insert into stock_analysis_current_rule_cohort_manifest (
                  cohort_id, page_id, cohort_mode, cohort_status, run_id, idempotency_key
                ) values ('cohort-2', 'stock-analysis', 'current_rule', 'draft', 'run-2', 'idem-1')
                """
            )
        with pytest.raises(duckdb.ConstraintException):
            conn.execute(
                """
                insert into stock_analysis_current_rule_cohort_manifest (
                  cohort_id, page_id, cohort_mode, cohort_status, run_id, idempotency_key
                ) values (NULL, 'stock-analysis', 'current_rule', 'draft', 'run-3', 'idem-3')
                """
            )

        conn.execute(
            """
            insert into stock_analysis_current_rule_replay_fact (
              cohort_id, signal_date, stock_code, signal_kind
            ) values ('cohort-1', '2026-08-18', '000001.SZ', 'breakout')
            """
        )
        with pytest.raises(duckdb.ConstraintException):
            conn.execute(
                """
                insert into stock_analysis_current_rule_replay_fact (
                  cohort_id, signal_date, stock_code, signal_kind
                ) values ('cohort-1', '2026-08-18', '000001.SZ', 'breakout')
                """
            )

        conn.execute(
            """
            insert into stock_analysis_current_rule_date_certificate (
              cohort_id, trade_date, certificate_status
            ) values ('cohort-1', '2026-08-18', 'certified')
            """
        )
        with pytest.raises(duckdb.ConstraintException):
            conn.execute(
                """
                insert into stock_analysis_current_rule_date_certificate (
                  cohort_id, trade_date, certificate_status
                ) values ('cohort-1', '2026-08-18', 'failed')
                """
            )
    finally:
        conn.close()


def test_recorded_v46_with_missing_table_fails_closed_instead_of_repairing() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _initialize_v45(conn)
        apply_stock_analysis_current_rule_cohort_schema_on_connection(conn)
        conn.execute("drop table stock_analysis_current_rule_date_certificate")

        with pytest.raises(RuntimeError, match="missing tables"):
            apply_stock_analysis_current_rule_cohort_schema_on_connection(conn)

        assert 46 in _migration_versions(conn)
        assert "stock_analysis_current_rule_date_certificate" not in _main_table_names(
            conn
        )
    finally:
        conn.close()
