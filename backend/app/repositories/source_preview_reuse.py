"""Read-only input and stored-row checks for source-preview reuse."""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from types import CodeType, FunctionType

import duckdb
from backend.app.repositories import source_preview_repo
from backend.app.repositories.object_store_repo import read_local_archive_bytes

_FORMAT_VERSION = 1
_MANIFEST_FIELDS = (
    "archived_path",
    "ingest_batch_id",
    "source_version",
    "source_file",
    "created_at",
    "source_family",
    "report_date",
    "report_start_date",
    "report_end_date",
    "report_granularity",
)
_IMPLEMENTATION_FILES = (
    "core_finance/source_preview_parsers.py",
    "core_finance/source_rules.py",
    "schemas/source_preview.py",
    "repositories/source_preview_repo.py",
    "repositories/source_preview_reuse.py",
    "repositories/object_store_repo.py",
    "repositories/duckdb_migrations.py",
    "tasks/source_preview_refresh.py",
    "schema_registry/duckdb/06_source_preview.sql",
)
_RUNTIME_MODULES = (
    "backend.app.core_finance.source_preview_parsers",
    "backend.app.core_finance.source_rules",
    "backend.app.schemas.source_preview",
    "backend.app.repositories.source_preview_repo",
    "backend.app.repositories.object_store_repo",
    __name__,
)
_PREVIEW_COLUMN_TYPES = frozenset({"VARCHAR", "BIGINT", "INTEGER", "BOOLEAN"})


def _signature_value(value: object) -> object:
    if isinstance(value, CodeType):
        return {
            "code": value.co_code.hex(),
            "constants": value.co_consts,
            "names": value.co_names,
            "variables": value.co_varnames,
            "free_variables": value.co_freevars,
            "cell_variables": value.co_cellvars,
            "argument_count": value.co_argcount,
            "positional_only_count": value.co_posonlyargcount,
            "keyword_only_count": value.co_kwonlyargcount,
            "flags": value.co_flags,
            "exceptions": value.co_exceptiontable.hex(),
        }
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=str)
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    return str(value)


def _signature(value: object) -> str:
    serialized = json.dumps(
        value, ensure_ascii=False, sort_keys=True, default=_signature_value, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _implementation_files_signature() -> str | None:
    app_dir = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    try:
        for relative_path in _IMPLEMENTATION_FILES:
            digest.update(relative_path.encode("utf-8"))
            digest.update(hashlib.sha256((app_dir / relative_path).read_bytes()).digest())
    except OSError:
        return None
    return digest.hexdigest()


_LOADED_FILES_SIGNATURE = _implementation_files_signature()


def _function_signature(function: FunctionType) -> object:
    return (function.__code__, function.__defaults__, function.__kwdefaults__)


def _implementation_signature() -> str | None:
    current = _implementation_files_signature()
    if current is None or current != _LOADED_FILES_SIGNATURE:
        # A stale worker may still rebuild, but must not certify reuse under the
        # signature of replacement source files it has not actually loaded.
        return None
    runtime: dict[str, object] = {}
    for module_name in _RUNTIME_MODULES:
        module = sys.modules.get(module_name)
        if module is None:
            runtime[module_name] = None
            continue
        members: dict[str, object] = {}
        for name, value in sorted(vars(module).items()):
            if isinstance(value, FunctionType) and value.__module__ == module_name:
                members[name] = _function_signature(value)
            elif isinstance(value, type) and value.__module__ == module_name:
                members[name] = {
                    "methods": {
                        key: _function_signature(method)
                        for key, method in sorted(vars(value).items())
                        if isinstance(method, FunctionType)
                    },
                    "model_fields": {
                        key: (str(field.annotation), field.default)
                        for key, field in getattr(value, "model_fields", {}).items()
                    },
                }
            elif name.isupper() and name != "_LOADED_FILES_SIGNATURE" and isinstance(
                value, (str, int, float, bool, tuple, list, set, frozenset, dict)
            ):
                members[name] = value
        runtime[module_name] = members
    try:
        dependencies = {package: version(package) for package in ("duckdb", "xlrd", "openpyxl", "pydantic")}
    except PackageNotFoundError:
        return None
    return _signature({"files": current, "runtime": runtime, "dependencies": dependencies, "python": sys.version})


def build_preview_input_identity(
    *,
    governance_dir: str,
    ingest_batch_id: str | None,
    source_families: list[str],
    archive_root: str,
) -> dict[str, object] | None:
    """Describe exactly the current selection without parsing or archiving it."""
    implementation = _implementation_signature()
    if implementation is None or not (Path(governance_dir) / "source_manifest.jsonl").is_file():
        return None
    try:
        selected = source_preview_repo._select_manifest_rows(
            source_preview_repo._load_manifest_rows(governance_dir),
            ingest_batch_id=ingest_batch_id,
            source_families=source_families,
            archive_root=archive_root,
        )
        if not selected:
            return None
        selected_inputs = []
        for row in selected:
            historical_path = str(row["archived_path"])
            if not str(row.get("ingest_batch_id") or ""):
                return None
            source_file_name = str(row.get("source_file") or Path(historical_path).name)
            selected_inputs.append({
                "manifest": {key: row.get(key) for key in _MANIFEST_FIELDS},
                "archive_sha256": hashlib.sha256(read_local_archive_bytes(historical_path, archive_root)).hexdigest(),
                # Undated filenames can resolve to today's local date. Reusing
                # the old manifest date would hide that parser input change.
                "inferred_metadata": asdict(source_preview_repo.describe_source_file(source_file_name)),
            })
        return {
            "format_version": _FORMAT_VERSION,
            "rule_version": source_preview_repo.RULE_VERSION,
            "implementation_sha256": implementation,
            "batch_ids": sorted({str(row["ingest_batch_id"]) for row in selected}),
            "selected_inputs": selected_inputs,
        }
    except (OSError, ValueError, TypeError, KeyError):
        return None


def capture_preview_table_fingerprints(
    duckdb_path: str,
    batch_ids: list[str],
) -> dict[str, object] | None:
    """Hash every value and duplicate in the selected physical database batches."""
    database = Path(duckdb_path)
    if not database.is_file() or not batch_ids or any(not isinstance(value, str) or not value for value in batch_ids):
        return None
    selected_batches = sorted(set(batch_ids))
    placeholders = ", ".join("?" for _ in selected_batches)
    connection = None
    try:
        # Deliberately bypass published-read routing: this certifies the writer's
        # physical tables while its existing writer lock remains held.
        connection = duckdb.connect(str(database.resolve()), read_only=True)
        connection.execute("begin transaction")
        tables: dict[str, object] = {}
        for table in source_preview_repo.PREVIEW_TABLES:
            schema = [list(column) for column in connection.execute(f"describe main.{table}").fetchall()]
            if not any(column[0] == "ingest_batch_id" and column[1] == "VARCHAR" for column in schema):
                return None
            if any(column[1] not in _PREVIEW_COLUMN_TYPES for column in schema):
                return None
            rows = connection.execute(
                f"""
                select sha256(to_json(stored_row)) as row_hash
                from main.{table} as stored_row
                where ingest_batch_id in ({placeholders})
                order by row_hash
                """,
                selected_batches,
            )
            digest = hashlib.sha256()
            row_count = 0
            while batch := rows.fetchmany(2048):
                for (row_hash,) in batch:
                    digest.update(row_hash.encode("ascii"))
                    row_count += 1
            tables[table] = {"schema": schema, "row_count": row_count, "sha256": digest.hexdigest()}
        connection.execute("commit")
        return {"format_version": _FORMAT_VERSION, "batch_ids": selected_batches, "tables": tables}
    except (duckdb.Error, OSError, ValueError, TypeError):
        return None
    finally:
        if connection is not None:
            connection.close()
