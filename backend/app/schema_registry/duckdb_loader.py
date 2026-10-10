"""Load and apply `duckdb/*.sql` registry slices (MOSS:STMT boundaries)."""

from __future__ import annotations

import hashlib
import importlib
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import duckdb

REGISTRY_DIR = Path(__file__).resolve().parent / "duckdb"
MANIFEST_PATH = REGISTRY_DIR / "manifest.json"

_STMT_BOUNDARY = re.compile(r"^\s*--\s*MOSS:STMT\s*$", re.MULTILINE)
_SQL_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SQL_DATA_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\([0-9, ]+\))?$")
_MATERIALIZABLE_STATEMENT_TYPES = frozenset(
    {
        duckdb.StatementType.ALTER,
        duckdb.StatementType.CREATE,
    }
)


@dataclass(frozen=True, slots=True)
class DeclaredControlledMigration:
    version: int
    description: str
    path: str


@dataclass(frozen=True, slots=True)
class DeclaredReadinessColumn:
    requirement_id: str
    table_schema: str
    table_name: str
    column_name: str
    data_type: str


@dataclass(frozen=True, slots=True)
class DuckDBCatalogSnapshot:
    objects: tuple[tuple[str, str, str], ...]
    columns: tuple[tuple[str, str, str, str], ...]
    indexes: tuple[tuple[str, str, str, bool, bool, str], ...]

    def as_payload(self) -> dict[str, tuple[tuple[Any, ...], ...]]:
        return {
            "objects": self.objects,
            "columns": self.columns,
            "indexes": self.indexes,
        }


@dataclass(frozen=True, slots=True)
class GovernedDuckDBCatalogContract:
    manifest_version: int
    registry_source_sha256: str
    schema_fingerprint_sha256: str
    snapshot: DuckDBCatalogSnapshot
    covered_manifest_paths: tuple[str, ...]
    lazy_ensure_exempt_paths: tuple[str, ...]
    readiness_requirement_ids: tuple[str, ...]
    expected_controlled_versions: tuple[int, ...]
    not_compared: tuple[str, ...]


def parse_registry_sql_text(text: str) -> list[str]:
    parts = _STMT_BOUNDARY.split(text)
    return [part.strip() for part in parts if part.strip()]


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _resolve_registry_path(relative_path: object) -> Path:
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError("DuckDB registry entry path must be a non-empty string")
    registry_root = REGISTRY_DIR.resolve()
    path = (registry_root / relative_path).resolve()
    try:
        path.relative_to(registry_root)
    except ValueError as exc:
        raise ValueError("DuckDB registry entry path escapes the registry root") from exc
    if not path.is_file():
        raise ValueError("DuckDB registry entry path does not name a file")
    return path


def iter_registry_sql_files() -> list[Path]:
    manifest = load_manifest()
    return [_resolve_registry_path(entry["path"]) for entry in manifest["files"]]


def _execute_registry_paths(
    conn: duckdb.DuckDBPyConnection,
    paths: Iterable[Path],
) -> None:
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for statement in parse_registry_sql_text(text):
            conn.execute(statement)


def apply_registry_sql(conn: duckdb.DuckDBPyConnection) -> None:
    _execute_registry_paths(conn, iter_registry_sql_files())


def load_materializable_registry_ddl_statements() -> tuple[str, ...]:
    """Return parsed CREATE/ALTER statements and reject future registry DML."""
    statements: list[str] = []
    for registry_chunk in load_manifest_ddl_statements():
        for statement in duckdb.extract_statements(registry_chunk):
            if statement.type not in _MATERIALIZABLE_STATEMENT_TYPES:
                raise ValueError("DuckDB readiness materialization only permits CREATE/ALTER DDL")
            statements.append(statement.query.strip())
    return tuple(statements)


def apply_materializable_registry_ddl(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply prevalidated registry DDL while skipping comment-only chunks."""
    statements = load_materializable_registry_ddl_statements()
    for statement in statements:
        conn.execute(statement)


def declared_controlled_migrations(
    manifest: dict[str, Any] | None = None,
) -> tuple[DeclaredControlledMigration, ...]:
    source = load_manifest() if manifest is None else manifest
    raw_entries = source.get("controlled_migrations", [])
    if not isinstance(raw_entries, list):
        raise ValueError("DuckDB controlled_migrations must be a list")
    descriptions = source.get("controlled_migration_descriptions", {})
    if not isinstance(descriptions, dict):
        raise ValueError("DuckDB controlled_migration_descriptions must be an object")

    declarations: list[DeclaredControlledMigration] = []
    seen_versions: set[int] = set()
    for entry in raw_entries:
        if not isinstance(entry, dict):
            raise ValueError("DuckDB controlled migration entry must be an object")
        version = entry.get("migration_version")
        description = entry.get("description")
        if description is None and isinstance(version, int):
            description = descriptions.get(str(version))
        relative_path = entry.get("path")
        if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
            raise ValueError("DuckDB controlled migration version must be a positive integer")
        if version in seen_versions:
            raise ValueError("DuckDB controlled migration versions must be unique")
        if not isinstance(description, str) or not description.strip():
            raise ValueError("DuckDB controlled migration description must be non-empty")
        path = _resolve_registry_path(relative_path)
        seen_versions.add(version)
        declarations.append(
            DeclaredControlledMigration(
                version=version,
                description=description,
                path=path.relative_to(REGISTRY_DIR.resolve()).as_posix(),
            )
        )
    return tuple(sorted(declarations, key=lambda item: item.version))


def declared_readiness_columns(
    manifest: dict[str, Any] | None = None,
) -> tuple[DeclaredReadinessColumn, ...]:
    source = load_manifest() if manifest is None else manifest
    readiness = source.get("readiness_requirements", {})
    if not isinstance(readiness, dict):
        raise ValueError("DuckDB readiness_requirements must be an object")
    raw_columns = readiness.get("columns", [])
    if not isinstance(raw_columns, list):
        raise ValueError("DuckDB readiness requirement columns must be a list")

    declarations: list[DeclaredReadinessColumn] = []
    seen_requirement_ids: set[str] = set()
    seen_columns: set[tuple[str, str, str]] = set()
    for entry in raw_columns:
        if not isinstance(entry, dict):
            raise ValueError("DuckDB readiness column entry must be an object")
        requirement_id = entry.get("requirement_id")
        table_schema = entry.get("table_schema")
        table_name = entry.get("table_name")
        column_name = entry.get("column_name")
        data_type = entry.get("data_type")
        if not isinstance(requirement_id, str) or not requirement_id.strip():
            raise ValueError("DuckDB readiness requirement_id must be non-empty")
        if requirement_id in seen_requirement_ids:
            raise ValueError("DuckDB readiness requirement_id values must be unique")
        identifiers = (table_schema, table_name, column_name)
        if any(
            not isinstance(identifier, str) or _SQL_IDENTIFIER.fullmatch(identifier) is None
            for identifier in identifiers
        ):
            raise ValueError("DuckDB readiness column identifiers are invalid")
        if table_schema != "main":
            raise ValueError("DuckDB readiness columns must belong to the main schema")
        if not isinstance(data_type, str) or _SQL_DATA_TYPE.fullmatch(data_type) is None:
            raise ValueError("DuckDB readiness column data_type is invalid")
        column_key = (table_schema, cast(str, table_name), cast(str, column_name))
        if column_key in seen_columns:
            raise ValueError("DuckDB readiness columns must be unique")
        seen_requirement_ids.add(requirement_id)
        seen_columns.add(column_key)
        declarations.append(
            DeclaredReadinessColumn(
                requirement_id=requirement_id,
                table_schema=table_schema,
                table_name=cast(str, table_name),
                column_name=cast(str, column_name),
                data_type=data_type.upper(),
            )
        )
    return tuple(declarations)


def _apply_readiness_columns(
    conn: duckdb.DuckDBPyConnection,
    requirements: Iterable[DeclaredReadinessColumn],
) -> None:
    for requirement in requirements:
        conn.execute(
            f'ALTER TABLE "{requirement.table_schema}"."{requirement.table_name}" '
            f'ADD COLUMN IF NOT EXISTS "{requirement.column_name}" {requirement.data_type}'
        )


def apply_declared_readiness_requirements(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply manifest-declared, ledger-neutral readiness columns."""
    _apply_readiness_columns(conn, declared_readiness_columns())


def _normalize_controlled_versions(
    expected_versions: Iterable[int],
    declarations: tuple[DeclaredControlledMigration, ...],
) -> tuple[int, ...]:
    requested = tuple(expected_versions)
    if any(isinstance(version, bool) or not isinstance(version, int) or version <= 0 for version in requested):
        raise ValueError("Expected controlled migration versions must be positive integers")
    if len(requested) != len(set(requested)):
        raise ValueError("Expected controlled migration versions must be unique")
    declared_versions = {declaration.version for declaration in declarations}
    if not set(requested) <= declared_versions:
        raise ValueError("Expected controlled migration version is not declared in the manifest")
    return tuple(sorted(requested))


def registry_source_sha256(manifest: dict[str, Any] | None = None) -> str:
    """Hash registry sources; this is not a historical migration-ledger checksum."""
    source = load_manifest() if manifest is None else manifest
    raw_entries = source.get("files", [])
    if not isinstance(raw_entries, list):
        raise ValueError("DuckDB manifest files must be a list")
    controlled = declared_controlled_migrations(source)
    relative_paths = [entry["path"] for entry in raw_entries]
    relative_paths.extend(declaration.path for declaration in controlled)
    digest_entries: list[tuple[str, str]] = [("manifest.json", hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest())]
    for relative_path in relative_paths:
        path = _resolve_registry_path(relative_path)
        digest_entries.append(
            (
                path.relative_to(REGISTRY_DIR.resolve()).as_posix(),
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    payload = json.dumps(
        digest_entries,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def capture_main_catalog(conn: duckdb.DuckDBPyConnection) -> DuckDBCatalogSnapshot:
    """Capture current-database main objects needed by the governed subset check."""
    objects = conn.execute(
        """
        select 'table' as object_kind, schema_name, table_name as object_name
        from duckdb_tables()
        where database_name = current_database()
          and schema_name = 'main'
          and not internal
          and not temporary
        union all
        select 'view', schema_name, view_name
        from duckdb_views()
        where database_name = current_database()
          and schema_name = 'main'
          and not internal
          and not temporary
        order by 1, 2, 3
        """
    ).fetchall()
    columns = conn.execute(
        """
        select table_schema, table_name, column_name, data_type
        from information_schema.columns
        where table_catalog = current_database()
          and table_schema = 'main'
        order by table_schema, table_name, column_name
        """
    ).fetchall()
    indexes = conn.execute(
        """
        select schema_name, index_name, table_name,
               is_unique, is_primary, coalesce(expressions, '')
        from duckdb_indexes()
        where database_name = current_database()
          and schema_name = 'main'
        order by schema_name, table_name, index_name
        """
    ).fetchall()
    return DuckDBCatalogSnapshot(
        objects=tuple(cast(tuple[str, str, str], tuple(str(value) for value in row)) for row in objects),
        columns=tuple(cast(tuple[str, str, str, str], tuple(str(value) for value in row)) for row in columns),
        indexes=tuple(
            (
                str(schema_name),
                str(index_name),
                str(table_name),
                bool(is_unique),
                bool(is_primary),
                str(expressions),
            )
            for schema_name, index_name, table_name, is_unique, is_primary, expressions in indexes
        ),
    )


def catalog_snapshot_sha256(snapshot: DuckDBCatalogSnapshot) -> str:
    payload = json.dumps(
        snapshot.as_payload(),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def governed_catalog_subset(
    actual: DuckDBCatalogSnapshot,
    expected: DuckDBCatalogSnapshot,
) -> DuckDBCatalogSnapshot:
    """Project an observed catalog onto manifest-governed object identities."""
    expected_object_keys = {(schema_name, object_name) for _, schema_name, object_name in expected.objects}
    return DuckDBCatalogSnapshot(
        objects=tuple(row for row in actual.objects if (row[1], row[2]) in expected_object_keys),
        columns=tuple(row for row in actual.columns if (row[0], row[1]) in expected_object_keys),
        indexes=tuple(row for row in actual.indexes if (row[0], row[2]) in expected_object_keys),
    )


def build_governed_catalog_contract(
    *,
    expected_controlled_versions: Iterable[int] = (),
) -> GovernedDuckDBCatalogContract:
    """Build the governed schema subset from static DDL in an isolated database."""
    manifest = load_manifest()
    raw_files = manifest.get("files", [])
    if not isinstance(raw_files, list):
        raise ValueError("DuckDB manifest files must be a list")
    ordinary_paths = tuple(_resolve_registry_path(entry["path"]) for entry in raw_files)
    controlled = declared_controlled_migrations(manifest)
    selected_versions = _normalize_controlled_versions(
        expected_controlled_versions,
        controlled,
    )
    controlled_by_version = {declaration.version: declaration for declaration in controlled}
    selected_controlled_paths = tuple(
        _resolve_registry_path(controlled_by_version[version].path) for version in selected_versions
    )
    readiness_columns = declared_readiness_columns(manifest)

    conn = duckdb.connect(":memory:")
    try:
        _execute_registry_paths(conn, ordinary_paths)
        _execute_registry_paths(conn, selected_controlled_paths)
        _apply_readiness_columns(conn, readiness_columns)
        snapshot = capture_main_catalog(conn)
    finally:
        conn.close()

    covered_paths = tuple(
        path.relative_to(REGISTRY_DIR.resolve()).as_posix() for path in (*ordinary_paths, *selected_controlled_paths)
    )
    lazy_paths = tuple(str(entry["path"]) for entry in raw_files if entry.get("lazy_ensure_exempt") is True)
    return GovernedDuckDBCatalogContract(
        manifest_version=int(manifest["version"]),
        registry_source_sha256=registry_source_sha256(manifest),
        schema_fingerprint_sha256=catalog_snapshot_sha256(snapshot),
        snapshot=snapshot,
        covered_manifest_paths=covered_paths,
        lazy_ensure_exempt_paths=lazy_paths,
        readiness_requirement_ids=tuple(requirement.requirement_id for requirement in readiness_columns),
        expected_controlled_versions=selected_versions,
        not_compared=(
            "column_default_nullability_and_ordinal",
            "constraints_not_materialized_as_explicit_indexes",
            "manifest_external_objects_and_their_columns_or_indexes",
            "view_definition_sql",
        ),
    )


def resolve_ensure(entry: dict[str, Any]) -> Callable[[duckdb.DuckDBPyConnection], None]:
    module = importlib.import_module(entry["ensure_module"])
    target = getattr(module, entry["ensure_symbol"])
    return target


_META_TABLES = frozenset({"_schema_migrations"})


def main_schema_fingerprint(
    conn: duckdb.DuckDBPyConnection,
    *,
    exclude_meta_tables: bool = False,
) -> tuple[tuple[Any, ...], ...]:
    """Stable-ish schema shape: omit table_catalog/data_type to reduce DuckDB metadata drift."""
    tables = conn.execute(
        """
        select table_name, table_type
        from information_schema.tables
        where table_schema = 'main'
        order by table_name, table_type
        """
    ).fetchall()
    columns = conn.execute(
        """
        select table_name, column_name, ordinal_position
        from information_schema.columns
        where table_schema = 'main'
        order by table_name, ordinal_position, column_name
        """
    ).fetchall()
    if exclude_meta_tables:
        tables = tuple(t for t in tables if t[0] not in _META_TABLES)
        columns = tuple(c for c in columns if c[0] not in _META_TABLES)
    return (tuple(tables), tuple(columns))


def normalize_sql(text: str) -> str:
    return " ".join(text.split())


def is_ddl_statement(sql: str) -> bool:
    head = sql.lstrip().lower()
    return head.startswith("create ") or head.startswith("alter ") or head.startswith("create or replace ")


class _SqlCaptureConnection:
    """Wrap DuckDB connection: C-extension connections cannot take arbitrary attributes."""

    __slots__ = ("_conn", "_statements")

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_statements", [])

    @property
    def captured_statements(self) -> list[str]:
        return self._statements

    def execute(self, sql: str, *args: Any, **kwargs: Any):
        self._statements.append(sql.strip())
        return self._conn.execute(sql, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


def collect_ensure_sql_calls(ensure: Callable[..., None]) -> list[str]:
    raw = duckdb.connect(":memory:")
    try:
        capture = _SqlCaptureConnection(raw)
        ensure(capture)
        return list(capture.captured_statements)
    finally:
        raw.close()


def collect_ensure_ddl_calls(ensure: Callable[[duckdb.DuckDBPyConnection], None]) -> list[str]:
    return [stmt for stmt in collect_ensure_sql_calls(ensure) if is_ddl_statement(stmt)]


def load_manifest_ddl_statements() -> list[str]:
    statements: list[str] = []
    for path in iter_registry_sql_files():
        statements.extend(parse_registry_sql_text(path.read_text(encoding="utf-8")))
    return statements
