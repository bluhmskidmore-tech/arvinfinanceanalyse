from __future__ import annotations

import hashlib
import json
import traceback
from pathlib import Path

import duckdb
import pytest

import backend.app.duckdb_schema_bootstrap as duckdb_schema_bootstrap
import backend.app.schema_registry.duckdb_loader as duckdb_loader
from backend.app.duckdb_schema_bootstrap import (
    DuckDBReadinessMaterializationError,
    DuckDBSchemaCurrentError,
    assert_duckdb_schema_current,
    materialize_declared_duckdb_readiness_schema,
    upgrade_duckdb_schema_head,
)
from backend.app.repositories.duckdb_migrations import (
    apply_stock_analysis_current_rule_cohort_schema_on_connection,
    register_all,
)
from backend.app.repositories.duckdb_schema_registry import DuckDBSchemaRegistry
from backend.app.schema_registry.duckdb_loader import (
    apply_declared_readiness_requirements,
    apply_registry_sql,
    load_materializable_registry_ddl_statements,
)


def _enable_storage_migrations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", raising=False)
    monkeypatch.delenv("MOSS_SKIP_POSTGRES_MIGRATIONS", raising=False)


def _create_current_database(
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    controlled_v46: bool = False,
) -> None:
    _enable_storage_migrations(monkeypatch)
    upgrade_duckdb_schema_head(duckdb_path=str(db_path))
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        apply_registry_sql(conn)
        apply_declared_readiness_requirements(conn)
        if controlled_v46:
            assert apply_stock_analysis_current_rule_cohort_schema_on_connection(conn)
    finally:
        conn.close()


def _finding_codes(error: DuckDBSchemaCurrentError) -> set[str]:
    return {finding["code"] for finding in error.receipt["findings"]}


def _assert_receipt_hash(receipt: dict) -> None:
    payload = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    assert receipt["receipt_sha256"] == hashlib.sha256(encoded).hexdigest()


def test_duckdb_bootstrap_creates_expected_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "boot.duckdb"
    _enable_storage_migrations(monkeypatch)

    upgrade_duckdb_schema_head(duckdb_path=str(db_path))

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        names = {
            row[0]
            for row in conn.execute(
                "select table_name from information_schema.tables where table_schema = 'main'"
            ).fetchall()
        }
    finally:
        conn.close()

    assert "zqtz_bond_daily_snapshot" in names
    assert "fact_formal_bond_analytics_daily" in names
    assert "phase1_source_preview_summary" in names
    assert "fact_formal_pnl_fi" in names
    assert "phase1_materialize_runs" in names
    assert "fx_daily_mid" in names
    assert "market_data_series_category" in names
    assert "choice_news_event" in names
    assert "choice_stock_factor_snapshot" in names


def test_duckdb_bootstrap_skipped_when_flag_set(tmp_path, monkeypatch):
    db_path = tmp_path / "skip.duckdb"
    monkeypatch.setenv("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", "1")
    upgrade_duckdb_schema_head(duckdb_path=str(db_path))
    assert not db_path.exists()


def test_registry_exposes_immutable_declared_migration_metadata() -> None:
    registry = DuckDBSchemaRegistry(db_path=":memory:")
    register_all(registry)

    declarations = registry.declared_migrations

    assert isinstance(declarations, tuple)
    assert [declaration.version for declaration in declarations] == list(range(1, 46))
    assert declarations[0].description == "baseline snapshot tables"
    assert declarations[-1].description == (
        "Persist ZQTZ interest receivable/payable on the standardized snapshot"
    )


def test_current_assertion_returns_distinct_registry_and_ledger_evidence(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "current.duckdb"
    _create_current_database(db_path, monkeypatch)

    receipt = assert_duckdb_schema_current(duckdb_path=str(db_path))

    assert receipt["status"] == "passed"
    assert receipt["findings"] == []
    assert receipt["registry"]["source_digest"]["kind"] == "registry_sources"
    fingerprint = receipt["registry"]["schema_fingerprint"]
    assert fingerprint["kind"] == "governed_catalog_subset"
    assert fingerprint["expected_sha256"] == fingerprint["observed_sha256"]
    assert receipt["historical_ledger"]["comparison_basis"] == (
        "version_and_description_exact"
    )
    assert receipt["historical_ledger"]["checksum"] == {
        "available": False,
        "verified": False,
        "reason": "schema_migrations_has_no_checksum_column",
    }
    assert set(receipt["catalog"]["lazy_ensure_exempt_paths"]) == {
        "30_stock_adjustment_factor.sql",
        "31_livermore_matched_baseline.sql",
        "45_snapshot_natural_key_constraints.sql",
    }
    _assert_receipt_hash(receipt)


def test_current_assertion_opens_target_read_only_and_leaves_file_unchanged(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "readonly.duckdb"
    _create_current_database(db_path, monkeypatch)
    before_bytes_sha256 = hashlib.sha256(db_path.read_bytes()).hexdigest()
    before_stat = db_path.stat()
    connect_calls: list[tuple[str, object]] = []
    real_connect = duckdb.connect

    def tracked_connect(database: str = ":memory:", *args, **kwargs):
        connect_calls.append((str(database), kwargs.get("read_only")))
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(duckdb_schema_bootstrap.duckdb, "connect", tracked_connect)

    receipt = assert_duckdb_schema_current(duckdb_path=str(db_path))

    target_calls = [call for call in connect_calls if call[0] == str(db_path)]
    assert target_calls == [(str(db_path), True)]
    assert receipt["target"]["read_only"] is True
    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == before_bytes_sha256
    after_stat = db_path.stat()
    assert after_stat.st_size == before_stat.st_size
    assert after_stat.st_mtime_ns == before_stat.st_mtime_ns


def test_explicit_materializer_closes_migration_command_readiness_gap(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "materialize.duckdb"
    _enable_storage_migrations(monkeypatch)
    upgrade_duckdb_schema_head(duckdb_path=str(db_path))

    with pytest.raises(DuckDBSchemaCurrentError):
        assert_duckdb_schema_current(duckdb_path=str(db_path))

    materialize_declared_duckdb_readiness_schema(duckdb_path=str(db_path))

    receipt = assert_duckdb_schema_current(duckdb_path=str(db_path))
    assert receipt["status"] == "passed"
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        applied_versions = {
            row[0]
            for row in conn.execute("select version from _schema_migrations").fetchall()
        }
        controlled_table_exists = conn.execute(
            """
            select count(*)
            from duckdb_tables()
            where database_name = current_database()
              and schema_name = 'main'
              and table_name = 'stock_analysis_current_rule_cohort_manifest'
            """
        ).fetchone() == (1,)
    finally:
        conn.close()
    assert applied_versions == set(range(1, 46))
    assert controlled_table_exists is False


def test_explicit_materializer_requires_complete_ordinary_ledger(
    tmp_path,
) -> None:
    db_path = tmp_path / "missing-ledger.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    conn.close()

    with pytest.raises(
        DuckDBReadinessMaterializationError,
        match="migration_ledger_missing",
    ):
        materialize_declared_duckdb_readiness_schema(duckdb_path=str(db_path))

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "select table_name from information_schema.tables "
                "where table_catalog = current_database() and table_schema = 'main'"
            ).fetchall()
        }
    finally:
        conn.close()
    assert "stock_adjustment_factor" not in tables


def test_explicit_materializer_rolls_back_all_ddl_on_failure(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "rollback.duckdb"
    _enable_storage_migrations(monkeypatch)
    upgrade_duckdb_schema_head(duckdb_path=str(db_path))

    def fail_readiness(_conn) -> None:
        raise RuntimeError("injected readiness failure")

    monkeypatch.setattr(
        duckdb_schema_bootstrap,
        "apply_declared_readiness_requirements",
        fail_readiness,
    )

    with pytest.raises(
        DuckDBReadinessMaterializationError,
        match="no schema changes were committed",
    ):
        materialize_declared_duckdb_readiness_schema(duckdb_path=str(db_path))

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        lazy_table_exists = conn.execute(
            """
            select count(*)
            from duckdb_tables()
            where database_name = current_database()
              and schema_name = 'main'
              and table_name = 'stock_adjustment_factor'
            """
        ).fetchone() == (1,)
    finally:
        conn.close()
    assert lazy_table_exists is False


def test_materializable_registry_rejects_dml_before_execution(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "dml-guard.duckdb"
    _enable_storage_migrations(monkeypatch)
    upgrade_duckdb_schema_head(duckdb_path=str(db_path))
    injected_path = tmp_path / "injected.sql"
    injected_path.write_text(
        "create table should_not_persist(id integer); "
        "insert into should_not_persist values (1)",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        duckdb_loader,
        "iter_registry_sql_files",
        lambda: [injected_path],
    )

    with pytest.raises(
        DuckDBReadinessMaterializationError,
        match="no schema changes were committed",
    ):
        materialize_declared_duckdb_readiness_schema(duckdb_path=str(db_path))

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        table_exists = conn.execute(
            """
            select count(*)
            from duckdb_tables()
            where database_name = current_database()
              and schema_name = 'main'
              and table_name = 'should_not_persist'
            """
        ).fetchone() == (1,)
    finally:
        conn.close()
    assert table_exists is False


def test_materializable_registry_has_only_create_alter_and_skips_comments() -> None:
    statements = load_materializable_registry_ddl_statements()

    assert len(statements) == 216
    for field in (
        "fund_no_maturity_market_value",
        "fund_no_maturity_count",
        "unknown_maturity_market_value",
        "unknown_maturity_count",
        "matured_outstanding_market_value",
        "matured_outstanding_count",
        "nonpositive_duration_market_value",
        "nonpositive_duration_count",
    ):
        assert any(
            f"alter table fact_formal_risk_tensor_daily add column if not exists {field} " in sql
            for sql in statements
        )
    assert {
        statement.type
        for sql in statements
        for statement in duckdb.extract_statements(sql)
    } <= {duckdb.StatementType.CREATE, duckdb.StatementType.ALTER}


def test_current_assertion_rejects_missing_ledger_version(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "missing.duckdb"
    _create_current_database(db_path, monkeypatch)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute("delete from _schema_migrations where version = 23")
    finally:
        conn.close()

    with pytest.raises(DuckDBSchemaCurrentError) as exc_info:
        assert_duckdb_schema_current(duckdb_path=str(db_path))

    assert "migration_version_missing" in _finding_codes(exc_info.value)
    missing = next(
        finding
        for finding in exc_info.value.receipt["findings"]
        if finding["code"] == "migration_version_missing"
    )
    assert "23" in missing["versions"]


def test_current_assertion_rejects_unknown_extra_without_leaking_description(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "customer-secret-name.duckdb"
    _create_current_database(db_path, monkeypatch)
    secret_description = "private-customer-migration-description"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            "insert into _schema_migrations(version, description) values (99, ?)",
            [secret_description],
        )
    finally:
        conn.close()

    with pytest.raises(DuckDBSchemaCurrentError) as exc_info:
        assert_duckdb_schema_current(duckdb_path=str(db_path))

    error = exc_info.value
    serialized_receipt = json.dumps(error.receipt, sort_keys=True)
    assert "migration_version_unknown_extra" in _finding_codes(error)
    assert secret_description not in str(error)
    assert secret_description not in serialized_receipt
    assert str(db_path) not in str(error)
    assert str(db_path) not in serialized_receipt
    assert error.receipt["status"] == "failed"
    _assert_receipt_hash(error.receipt)


def test_current_assertion_suppresses_registry_failure_traceback_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_path = "C:/secret/customer/schema.sql"

    def _fail_registry_contract(**_kwargs: object) -> object:
        raise RuntimeError(f"invalid registry at {secret_path}")

    monkeypatch.setattr(
        duckdb_schema_bootstrap,
        "build_governed_catalog_contract",
        _fail_registry_contract,
    )

    with pytest.raises(DuckDBSchemaCurrentError) as exc_info:
        assert_duckdb_schema_current()

    error = exc_info.value
    assert _finding_codes(error) == {"registry_contract_invalid"}
    assert error.__context__ is None
    assert secret_path not in "".join(traceback.format_exception(error))


def test_current_assertion_rejects_description_mismatch(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "description.duckdb"
    _create_current_database(db_path, monkeypatch)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            "update _schema_migrations set description = 'wrong' where version = 12"
        )
    finally:
        conn.close()

    with pytest.raises(DuckDBSchemaCurrentError) as exc_info:
        assert_duckdb_schema_current(duckdb_path=str(db_path))

    assert "migration_description_mismatch" in _finding_codes(exc_info.value)


def test_current_assertion_rejects_extra_column_inside_governed_object(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "extra-column.duckdb"
    _create_current_database(db_path, monkeypatch)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            "alter table fact_formal_bond_analytics_daily "
            "add column unauthorized_probe varchar"
        )
    finally:
        conn.close()

    with pytest.raises(DuckDBSchemaCurrentError) as exc_info:
        assert_duckdb_schema_current(duckdb_path=str(db_path))

    error = exc_info.value
    assert "catalog_column_unknown_extra" in _finding_codes(error)
    assert "unauthorized_probe" not in json.dumps(error.receipt, sort_keys=True)


def test_current_assertion_rejects_extra_index_inside_governed_object(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "extra-index.duckdb"
    _create_current_database(db_path, monkeypatch)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            "create index unauthorized_probe_index "
            "on fact_formal_bond_analytics_daily(instrument_code)"
        )
    finally:
        conn.close()

    with pytest.raises(DuckDBSchemaCurrentError) as exc_info:
        assert_duckdb_schema_current(duckdb_path=str(db_path))

    error = exc_info.value
    assert "catalog_index_unknown_extra" in _finding_codes(error)
    assert "unauthorized_probe_index" not in json.dumps(error.receipt, sort_keys=True)


def test_current_assertion_ignores_manifest_external_objects(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "external-object.duckdb"
    _create_current_database(db_path, monkeypatch)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute("create table local_extension_probe(id integer, payload varchar)")
        conn.execute(
            "create index local_extension_probe_index on local_extension_probe(id)"
        )
    finally:
        conn.close()

    receipt = assert_duckdb_schema_current(duckdb_path=str(db_path))

    assert receipt["status"] == "passed"
    assert (
        "manifest_external_objects_and_their_columns_or_indexes"
        in receipt["catalog"]["not_compared"]
    )


@pytest.mark.parametrize(
    ("drift_sql", "expected_code", "expected_item"),
    [
        (
            "drop table stock_adjustment_factor",
            "catalog_object_missing",
            "main.stock_adjustment_factor",
        ),
        (
            "drop index uq_zqtz_bond_daily_snapshot_natural_key",
            "catalog_index_missing",
            "main.uq_zqtz_bond_daily_snapshot_natural_key",
        ),
    ],
)
def test_current_assertion_covers_lazy_ensure_exempt_schema(
    tmp_path,
    monkeypatch,
    drift_sql,
    expected_code,
    expected_item,
) -> None:
    db_path = tmp_path / "lazy.duckdb"
    _create_current_database(db_path, monkeypatch)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(drift_sql)
    finally:
        conn.close()

    with pytest.raises(DuckDBSchemaCurrentError) as exc_info:
        assert_duckdb_schema_current(duckdb_path=str(db_path))

    finding = next(
        item
        for item in exc_info.value.receipt["findings"]
        if item["code"] == expected_code
    )
    item_key = "objects" if expected_code == "catalog_object_missing" else "indexes"
    assert expected_item in finding[item_key]


def test_current_assertion_requires_ledger_neutral_bond_columns(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "bond-readiness.duckdb"
    _create_current_database(db_path, monkeypatch)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        index_names = conn.execute(
            """
            select index_name
            from duckdb_indexes()
            where database_name = current_database()
              and schema_name = 'main'
              and table_name = 'fact_formal_bond_analytics_daily'
            """
        ).fetchall()
        for (index_name,) in index_names:
            conn.execute(f'drop index "{index_name}"')
        conn.execute(
            "alter table fact_formal_bond_analytics_daily "
            "drop column duration_quality_flag"
        )
    finally:
        conn.close()

    with pytest.raises(DuckDBSchemaCurrentError) as exc_info:
        assert_duckdb_schema_current(duckdb_path=str(db_path))

    finding = next(
        item
        for item in exc_info.value.receipt["findings"]
        if item["code"] == "catalog_column_missing"
    )
    assert (
        "main.fact_formal_bond_analytics_daily.duration_quality_flag"
        in finding["columns"]
    )


def test_controlled_v46_requires_explicit_expected_version(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "controlled.duckdb"
    _create_current_database(db_path, monkeypatch, controlled_v46=True)

    with pytest.raises(DuckDBSchemaCurrentError) as exc_info:
        assert_duckdb_schema_current(duckdb_path=str(db_path))

    assert "migration_version_unknown_extra" in _finding_codes(exc_info.value)

    receipt = assert_duckdb_schema_current(
        duckdb_path=str(db_path),
        expected_controlled_versions=(46,),
    )
    assert receipt["status"] == "passed"
    assert receipt["registry"]["expected_controlled_versions"] == [46]


def test_expected_controlled_version_must_be_manifest_declared(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "ordinary.duckdb"
    _create_current_database(db_path, monkeypatch)

    with pytest.raises(DuckDBSchemaCurrentError) as exc_info:
        assert_duckdb_schema_current(
            duckdb_path=str(db_path),
            expected_controlled_versions=(47,),
        )

    assert _finding_codes(exc_info.value) == {"registry_contract_invalid"}
