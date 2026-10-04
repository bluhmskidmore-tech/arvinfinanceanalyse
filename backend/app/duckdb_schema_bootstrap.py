"""Apply DuckDB DDL via versioned schema registry at process startup (idempotent)."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import duckdb
from backend.app.governance.settings import get_settings
from backend.app.repositories.duckdb_migrations import register_all
from backend.app.repositories.duckdb_schema_registry import DuckDBSchemaRegistry
from backend.app.schema_registry.duckdb_loader import (
    DeclaredControlledMigration,
    DuckDBCatalogSnapshot,
    apply_declared_readiness_requirements,
    apply_materializable_registry_ddl,
    build_governed_catalog_contract,
    capture_main_catalog,
    catalog_snapshot_sha256,
    declared_controlled_migrations,
    governed_catalog_subset,
)
from backend.app.storage_migration_flags import skip_auto_storage_migrations

logger = logging.getLogger(__name__)
_MIGRATION_COMMAND = r".\.venv\Scripts\python.exe backend\scripts\migrate_storage.py"
_RECEIPT_SCHEMA = "moss.duckdb-schema-current/v1"
_FINDING_ITEM_LIMIT = 25


class DuckDBSchemaCurrentError(RuntimeError):
    """Fail-closed current assertion with a sanitized structured receipt."""

    def __init__(self, message: str, *, receipt: dict[str, Any]) -> None:
        super().__init__(message)
        self.receipt = receipt


class DuckDBReadinessMaterializationError(RuntimeError):
    """Explicit readiness materialization failed without exposing target data."""


def _receipt_sha256(receipt: dict[str, Any]) -> str:
    payload = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _finalize_receipt(receipt: dict[str, Any], *, status: str) -> dict[str, Any]:
    finalized = dict(receipt)
    finalized["status"] = status
    finalized["receipt_sha256"] = _receipt_sha256(finalized)
    return finalized


def _base_receipt(*, expected_controlled_versions: tuple[int, ...]) -> dict[str, Any]:
    return {
        "receipt_schema": _RECEIPT_SCHEMA,
        "status": "failed",
        "target": {
            "database_role": "duckdb-main",
            "read_only": True,
        },
        "registry": {
            "expected_controlled_versions": list(expected_controlled_versions),
        },
        "historical_ledger": {
            "comparison_basis": "version_and_description_exact",
            "checksum": {
                "available": False,
                "verified": False,
                "reason": "schema_migrations_has_no_checksum_column",
            },
        },
        "catalog": {
            "comparison_scope": "governed_manifest_subset",
        },
        "findings": [],
    }


def _append_finding(
    receipt: dict[str, Any],
    code: str,
    *,
    item_key: str | None = None,
    items: Iterable[object] = (),
) -> None:
    finding: dict[str, Any] = {"code": code}
    values = sorted(str(item) for item in items)
    if item_key is not None:
        finding["count"] = len(values)
        finding[item_key] = values[:_FINDING_ITEM_LIMIT]
        if len(values) > _FINDING_ITEM_LIMIT:
            finding["truncated"] = True
    elif values:
        finding["count"] = len(values)
    receipt["findings"].append(finding)


def _current_error(receipt: dict[str, Any]) -> DuckDBSchemaCurrentError:
    finalized = _finalize_receipt(receipt, status="failed")
    codes = sorted({finding["code"] for finding in finalized["findings"]})
    code_summary = ", ".join(codes) if codes else "unknown_failure"
    return DuckDBSchemaCurrentError(
        "DuckDB schema is not current "
        f"(finding codes: {code_summary}). "
        f"Run {_MIGRATION_COMMAND} before starting the API.",
        receipt=finalized,
    )


def _catalog_findings(
    receipt: dict[str, Any],
    *,
    expected: DuckDBCatalogSnapshot,
    actual: DuckDBCatalogSnapshot,
) -> None:
    expected_objects = {(row[1], row[2]): row[0] for row in expected.objects}
    actual_objects = {(row[1], row[2]): row[0] for row in actual.objects}
    missing_objects = [
        f"{schema_name}.{object_name}" for schema_name, object_name in expected_objects.keys() - actual_objects.keys()
    ]
    mismatched_objects = [
        f"{schema_name}.{object_name}"
        for schema_name, object_name in expected_objects.keys() & actual_objects.keys()
        if expected_objects[(schema_name, object_name)] != actual_objects[(schema_name, object_name)]
    ]
    if missing_objects:
        _append_finding(
            receipt,
            "catalog_object_missing",
            item_key="objects",
            items=missing_objects,
        )
    if mismatched_objects:
        _append_finding(
            receipt,
            "catalog_object_kind_mismatch",
            item_key="objects",
            items=mismatched_objects,
        )

    expected_columns = {
        (schema_name, table_name, column_name): data_type
        for schema_name, table_name, column_name, data_type in expected.columns
    }
    actual_columns = {
        (schema_name, table_name, column_name): data_type
        for schema_name, table_name, column_name, data_type in actual.columns
    }
    missing_columns = [
        f"{schema_name}.{table_name}.{column_name}"
        for schema_name, table_name, column_name in (expected_columns.keys() - actual_columns.keys())
    ]
    mismatched_columns = [
        f"{schema_name}.{table_name}.{column_name}"
        for schema_name, table_name, column_name in (expected_columns.keys() & actual_columns.keys())
        if expected_columns[(schema_name, table_name, column_name)]
        != actual_columns[(schema_name, table_name, column_name)]
    ]
    extra_columns = actual_columns.keys() - expected_columns.keys()
    if missing_columns:
        _append_finding(
            receipt,
            "catalog_column_missing",
            item_key="columns",
            items=missing_columns,
        )
    if mismatched_columns:
        _append_finding(
            receipt,
            "catalog_column_type_mismatch",
            item_key="columns",
            items=mismatched_columns,
        )
    if extra_columns:
        _append_finding(
            receipt,
            "catalog_column_unknown_extra",
            items=extra_columns,
        )

    expected_indexes = {(row[0], row[1]): row[2:] for row in expected.indexes}
    actual_indexes = {(row[0], row[1]): row[2:] for row in actual.indexes}
    missing_indexes = [
        f"{schema_name}.{index_name}" for schema_name, index_name in expected_indexes.keys() - actual_indexes.keys()
    ]
    mismatched_indexes = [
        f"{schema_name}.{index_name}"
        for schema_name, index_name in expected_indexes.keys() & actual_indexes.keys()
        if expected_indexes[(schema_name, index_name)] != actual_indexes[(schema_name, index_name)]
    ]
    extra_indexes = actual_indexes.keys() - expected_indexes.keys()
    if missing_indexes:
        _append_finding(
            receipt,
            "catalog_index_missing",
            item_key="indexes",
            items=missing_indexes,
        )
    if mismatched_indexes:
        _append_finding(
            receipt,
            "catalog_index_definition_mismatch",
            item_key="indexes",
            items=mismatched_indexes,
        )
    if extra_indexes:
        _append_finding(
            receipt,
            "catalog_index_unknown_extra",
            items=extra_indexes,
        )


def _assert_materialization_ledger_ready(
    conn: duckdb.DuckDBPyConnection,
    *,
    db_path: str,
) -> None:
    registry = DuckDBSchemaRegistry(db_path=db_path)
    register_all(registry)
    ordinary_declarations = registry.declared_migrations
    ordinary_ledger = {declaration.version: declaration.description for declaration in ordinary_declarations}
    if len(ordinary_ledger) != len(ordinary_declarations):
        raise DuckDBReadinessMaterializationError(
            "DuckDB readiness materialization blocked (reason code: ordinary_registry_duplicate_version)."
        )

    controlled_declarations = declared_controlled_migrations()
    controlled_ledger = {declaration.version: declaration.description for declaration in controlled_declarations}
    if set(ordinary_ledger) & set(controlled_ledger):
        raise DuckDBReadinessMaterializationError(
            "DuckDB readiness materialization blocked (reason code: controlled_registry_version_collision)."
        )

    migration_table_exists = conn.execute(
        """
        select count(*)
        from duckdb_tables()
        where database_name = current_database()
          and schema_name = 'main'
          and table_name = '_schema_migrations'
          and not internal
          and not temporary
        """
    ).fetchone() == (1,)
    if not migration_table_exists:
        raise DuckDBReadinessMaterializationError(
            "DuckDB readiness materialization blocked (reason code: migration_ledger_missing)."
        )

    rows = conn.execute('select version, description from "main"."_schema_migrations" order by version').fetchall()
    applied_ledger: dict[int, str] = {}
    for version, description in rows:
        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or not isinstance(description, str)
            or version in applied_ledger
        ):
            raise DuckDBReadinessMaterializationError(
                "DuckDB readiness materialization blocked (reason code: migration_ledger_malformed)."
            )
        applied_ledger[version] = description

    allowed_ledger = ordinary_ledger | controlled_ledger
    ordinary_missing = set(ordinary_ledger) - set(applied_ledger)
    unknown_extra = set(applied_ledger) - set(allowed_ledger)
    description_mismatch = {
        version
        for version in set(applied_ledger) & set(allowed_ledger)
        if applied_ledger[version] != allowed_ledger[version]
    }
    if ordinary_missing or unknown_extra or description_mismatch:
        raise DuckDBReadinessMaterializationError(
            "DuckDB readiness materialization blocked (reason code: migration_ledger_not_ready)."
        )


def assert_duckdb_schema_current(
    *,
    duckdb_path: str | None = None,
    expected_controlled_versions: Iterable[int] = (),
) -> dict[str, Any]:
    """Validate the exact ledger and governed catalog through a read-only target."""
    requested_controlled_versions: tuple[int, ...] = ()
    controlled_expectation_invalid = False
    try:
        requested_controlled_versions = tuple(expected_controlled_versions)
    except Exception:
        controlled_expectation_invalid = True
    if controlled_expectation_invalid:
        receipt = _base_receipt(expected_controlled_versions=())
        _append_finding(receipt, "controlled_expectation_invalid")
        raise _current_error(receipt)

    receipt = _base_receipt(
        expected_controlled_versions=tuple(
            version
            for version in requested_controlled_versions
            if isinstance(version, int) and not isinstance(version, bool)
        )
    )
    catalog_contract = None
    controlled_declarations: tuple[DeclaredControlledMigration, ...] = ()
    registry_contract_invalid = False
    try:
        catalog_contract = build_governed_catalog_contract(
            expected_controlled_versions=requested_controlled_versions,
        )
        controlled_declarations = declared_controlled_migrations()
    except Exception:
        registry_contract_invalid = True
    if registry_contract_invalid or catalog_contract is None:
        _append_finding(receipt, "registry_contract_invalid")
        raise _current_error(receipt)

    path: Path | None = None
    database_target_invalid = False
    try:
        resolved_path = duckdb_path if duckdb_path is not None else get_settings().duckdb_path
        path = Path(resolved_path).expanduser()
    except Exception:
        database_target_invalid = True
    if database_target_invalid or path is None:
        _append_finding(receipt, "database_target_invalid")
        raise _current_error(receipt)

    ordinary_declarations = None
    ordinary_registry_invalid = False
    try:
        registry = DuckDBSchemaRegistry(db_path=str(path))
        register_all(registry)
        ordinary_declarations = registry.declared_migrations
    except Exception:
        ordinary_registry_invalid = True
    if ordinary_registry_invalid or ordinary_declarations is None:
        _append_finding(receipt, "ordinary_registry_invalid")
        raise _current_error(receipt)
    ordinary_versions = [declaration.version for declaration in ordinary_declarations]
    if len(ordinary_versions) != len(set(ordinary_versions)):
        _append_finding(receipt, "ordinary_registry_duplicate_version")
        raise _current_error(receipt)

    expected_ledger = {declaration.version: declaration.description for declaration in ordinary_declarations}
    controlled_by_version = {declaration.version: declaration for declaration in controlled_declarations}
    for version in catalog_contract.expected_controlled_versions:
        if version in expected_ledger:
            _append_finding(receipt, "controlled_registry_version_collision")
            raise _current_error(receipt)
        expected_ledger[version] = controlled_by_version[version].description

    receipt["registry"] = {
        "manifest_version": catalog_contract.manifest_version,
        "ordinary_migration_count": len(ordinary_declarations),
        "expected_controlled_versions": list(catalog_contract.expected_controlled_versions),
        "source_digest": {
            "kind": "registry_sources",
            "algorithm": "sha256",
            "sha256": catalog_contract.registry_source_sha256,
        },
        "schema_fingerprint": {
            "kind": "governed_catalog_subset",
            "algorithm": "sha256",
            "expected_sha256": catalog_contract.schema_fingerprint_sha256,
            "observed_sha256": None,
        },
    }
    receipt["historical_ledger"]["expected_versions"] = sorted(expected_ledger)
    receipt["catalog"].update(
        {
            "covered_manifest_paths": list(catalog_contract.covered_manifest_paths),
            "lazy_ensure_exempt_paths": list(catalog_contract.lazy_ensure_exempt_paths),
            "readiness_requirement_ids": list(catalog_contract.readiness_requirement_ids),
            "not_compared": list(catalog_contract.not_compared),
        }
    )

    if not path.is_file():
        _append_finding(receipt, "database_missing")
        raise _current_error(receipt)

    phase = "database_open"
    phase_failure: str | None = None
    conn: duckdb.DuckDBPyConnection | None = None
    try:
        conn = duckdb.connect(str(path), read_only=True)
        phase = "migration_ledger_read"
        migration_table_exists = conn.execute(
            """
            select count(*)
            from duckdb_tables()
            where database_name = current_database()
              and schema_name = 'main'
              and table_name = '_schema_migrations'
              and not internal
              and not temporary
            """
        ).fetchone() == (1,)
        ledger_rows = (
            conn.execute('select version, description from "main"."_schema_migrations" order by version').fetchall()
            if migration_table_exists
            else []
        )
        phase = "catalog_read"
        actual_catalog = capture_main_catalog(conn)
    except Exception:
        phase_failure = f"{phase}_failed"
    finally:
        if conn is not None:
            conn.close()
    if phase_failure is not None:
        _append_finding(receipt, phase_failure)
        raise _current_error(receipt)

    if not migration_table_exists:
        _append_finding(receipt, "migration_ledger_missing")

    applied_ledger: dict[int, str] = {}
    ledger_malformed = False
    for version, description in ledger_rows:
        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or not isinstance(description, str)
            or version in applied_ledger
        ):
            ledger_malformed = True
            continue
        applied_ledger[version] = description
    if ledger_malformed:
        _append_finding(receipt, "migration_ledger_malformed")

    expected_versions = set(expected_ledger)
    applied_versions = set(applied_ledger)
    missing_versions = expected_versions - applied_versions
    extra_versions = applied_versions - expected_versions
    description_mismatches = {
        version
        for version in expected_versions & applied_versions
        if expected_ledger[version] != applied_ledger[version]
    }
    if missing_versions:
        _append_finding(
            receipt,
            "migration_version_missing",
            item_key="versions",
            items=missing_versions,
        )
    if extra_versions:
        _append_finding(
            receipt,
            "migration_version_unknown_extra",
            item_key="versions",
            items=extra_versions,
        )
    if description_mismatches:
        _append_finding(
            receipt,
            "migration_description_mismatch",
            item_key="versions",
            items=description_mismatches,
        )

    receipt["historical_ledger"]["applied_versions"] = sorted(applied_versions)
    actual_governed_catalog = governed_catalog_subset(
        actual_catalog,
        catalog_contract.snapshot,
    )
    actual_schema_fingerprint = catalog_snapshot_sha256(actual_governed_catalog)
    receipt["registry"]["schema_fingerprint"]["observed_sha256"] = actual_schema_fingerprint
    finding_count_before_catalog = len(receipt["findings"])
    _catalog_findings(
        receipt,
        expected=catalog_contract.snapshot,
        actual=actual_governed_catalog,
    )
    if (
        catalog_contract.schema_fingerprint_sha256 != actual_schema_fingerprint
        and len(receipt["findings"]) == finding_count_before_catalog
    ):
        _append_finding(receipt, "catalog_fingerprint_mismatch")

    if receipt["findings"]:
        raise _current_error(receipt)
    return _finalize_receipt(receipt, status="passed")


def materialize_declared_duckdb_readiness_schema(
    *,
    duckdb_path: str | None = None,
) -> None:
    """Explicitly materialize manifest DDL after the ordinary ledger is ready."""
    resolved_path = duckdb_path if duckdb_path is not None else get_settings().duckdb_path
    path = Path(resolved_path).expanduser()
    if not path.is_file():
        raise DuckDBReadinessMaterializationError(
            "DuckDB readiness materialization blocked (reason code: database_missing)."
        )

    conn: duckdb.DuckDBPyConnection | None = None
    try:
        conn = duckdb.connect(str(path), read_only=False)
        _assert_materialization_ledger_ready(conn, db_path=str(path))
        conn.execute("BEGIN TRANSACTION")
        try:
            apply_materializable_registry_ddl(conn)
            apply_declared_readiness_requirements(conn)
            conn.execute("COMMIT")
        except Exception as exc:
            conn.execute("ROLLBACK")
            raise DuckDBReadinessMaterializationError(
                "DuckDB readiness materialization failed; no schema changes were committed."
            ) from exc
    except DuckDBReadinessMaterializationError:
        raise
    except Exception as exc:
        raise DuckDBReadinessMaterializationError(
            "DuckDB readiness materialization failed before schema commit."
        ) from exc
    finally:
        if conn is not None:
            conn.close()


def upgrade_duckdb_schema_head(*, duckdb_path: str | None = None) -> None:
    if skip_auto_storage_migrations():
        return
    settings = get_settings()
    path = str(Path(duckdb_path or settings.duckdb_path).expanduser())
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    registry = DuckDBSchemaRegistry(db_path=path)
    register_all(registry)
    applied = registry.apply_pending()
    if applied:
        logger.info("Applied %d DuckDB migrations: %s", len(applied), applied)
