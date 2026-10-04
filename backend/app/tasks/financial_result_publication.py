from __future__ import annotations

import json
import math
import os
import re
import shutil
import uuid
from collections.abc import Callable, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.repositories.financial_result_publication_repo import (
    _PUBLICATION_LOCK_TTL_SECONDS,
    PUBLICATION_MANIFEST_TABLE,
    PUBLICATION_POINTER_FILE,
    PUBLICATION_PROTOCOL_VERSION,
    FinancialPublicationConflict,
    FinancialPublicationInvalid,
    ResolvedFinancialPublication,
    _publication_lock,
    _utc_now,
    _write_atomic_json,
    canonical_json_bytes,
    generation_database_path,
    generation_manifest_path,
    read_publication_pointer,
    resolve_financial_generation,
    sha256_bytes,
    sha256_file,
    validate_generation,
    validate_sealed_financial_generation,
)
from backend.app.repositories.financial_result_publication_repo import (
    invalidate_financial_generation as invalidate_financial_generation,
)
from backend.app.services.pretrade_qualification import normalize_pretrade_qualification

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PASSING_STATUSES = frozenset({"completed", "passed"})
_DEFAULT_CAPACITY_RESERVE_MULTIPLIER = 1.20
_EXTERNAL_RELATION_PATTERN = re.compile(
    r"(?:\b(?:read_csv|read_csv_auto|read_json|read_json_auto|read_ndjson|read_parquet|"
    r"parquet_scan|sqlite_scan|postgres_scan|mysql_scan|delta_scan|iceberg_scan|glob|read_blob)\s*\("
    r"|\bfrom\s+['\"])",
    re.IGNORECASE,
)
_CandidateConnectionInitializer = Callable[
    [duckdb.DuckDBPyConnection, Path, str], None
]


class FinancialPublicationCapacityError(FinancialPublicationInvalid):
    pass


@dataclass(frozen=True)
class FinancialTablePublicationSpec:
    name: str
    date_column: str | None = None
    required_dates: tuple[str, ...] = ()
    minimum_rows_per_date: int = 1
    minimum_total_rows: int = 1


@dataclass(frozen=True)
class FinancialPublicationPlan:
    generation: str
    expected_previous_generation: str | None
    tables: tuple[FinancialTablePublicationSpec, ...]
    required_steps: tuple[str, ...]
    step_receipts: tuple[Mapping[str, object], ...]
    required_dependency_keys: tuple[str, ...]
    dependency_versions: Mapping[str, str]
    coverage_dates: Mapping[str, Sequence[str]]
    supported_api_versions: tuple[str, ...]
    supported_schema_versions: tuple[str, ...]
    quality: Mapping[str, object]
    source_dependency_validator: Callable[
        [duckdb.DuckDBPyConnection], Mapping[str, str]
    ] = field(repr=False, compare=False)
    estimated_candidate_bytes: int | None = None
    expires_at: str | None = None
    full_database: bool = False
    system_read_bundle: Mapping[str, object] | None = None


@dataclass(frozen=True)
class FinancialPublicationReceipt:
    status: str
    generation: str
    previous_generation: str | None
    database_path: Path
    manifest_path: Path
    manifest_sha256: str
    pointer_path: Path
    recovered_after_commit: bool = False
    resource_limits: Mapping[str, object] | None = None


def publish_financial_result(
    *,
    source_duckdb_path: Path | str,
    publication_root: Path | str,
    plan: FinancialPublicationPlan,
    writer_lock_already_held: bool = False,
    source_connection: duckdb.DuckDBPyConnection | None = None,
    capacity_reserve_multiplier: float = _DEFAULT_CAPACITY_RESERVE_MULTIPLIER,
    on_stage: Callable[[str], None] | None = None,
    candidate_connection_initializer: _CandidateConnectionInitializer | None = None,
) -> FinancialPublicationReceipt:
    """Seal and atomically publish a financial result generation.

    The default path acquires the existing physical DuckDB writer lock. A caller
    that already owns that lock may pass ``writer_lock_already_held=True`` and
    optionally its open source connection, avoiding a nested acquisition deadlock.
    """

    source_path = Path(source_duckdb_path).resolve()
    root = Path(publication_root).resolve()
    _validate_plan(plan)
    if source_connection is not None and not writer_lock_already_held:
        raise FinancialPublicationInvalid(
            "An existing source connection is accepted only when the caller confirms the writer lock is held."
        )
    if not source_path.is_file():
        raise FileNotFoundError(f"Financial publication source DuckDB does not exist: {source_path}")
    if not math.isfinite(capacity_reserve_multiplier) or capacity_reserve_multiplier < 1:
        raise ValueError("capacity_reserve_multiplier must be finite and at least 1.0.")

    (root / "generations").mkdir(parents=True, exist_ok=True)
    (root / "invalidations").mkdir(parents=True, exist_ok=True)
    input_identity_sha256 = _plan_identity_sha256(plan)
    publication_lock = _publication_lock(root)
    writer_lock = resolve_duckdb_writer_lock(source_path, ttl_seconds=_PUBLICATION_LOCK_TTL_SECONDS)

    with ExitStack() as stack:
        if not writer_lock_already_held:
            stack.enter_context(acquire_lock(writer_lock, base_dir=source_path.parent))
        stack.enter_context(acquire_lock(publication_lock, base_dir=root))
        pointer = read_publication_pointer(root, require_valid=False)
        recovered = _recover_committed_generation(
            root,
            plan=plan,
            pointer=pointer,
            input_identity_sha256=input_identity_sha256,
        )
        if recovered is not None:
            return recovered

        previous_generation = str(pointer["generation"]) if pointer is not None else None
        if previous_generation != plan.expected_previous_generation:
            raise FinancialPublicationConflict(
                "Expected previous financial publication does not match the committed pointer: "
                f"expected={plan.expected_previous_generation!r}, actual={previous_generation!r}."
            )

        _validate_source_dependency_snapshot(
            source_path=source_path,
            source_connection=source_connection,
            plan=plan,
        )

        final_database_path = generation_database_path(root, plan.generation)
        final_manifest_path = generation_manifest_path(root, plan.generation)
        database_exists = final_database_path.exists()
        manifest_exists = final_manifest_path.exists()
        if manifest_exists and not database_exists:
            raise FinancialPublicationConflict(
                f"Financial publication generation {plan.generation!r} has incomplete sealed artifacts."
            )
        if database_exists and not manifest_exists:
            sealed_payload = _read_sealed_payload_from_database(
                final_database_path,
                expected_generation=plan.generation,
                expected_input_identity_sha256=input_identity_sha256,
            )
            _write_atomic_json(
                final_manifest_path,
                _external_manifest(final_database_path, sealed_payload),
                replace=False,
            )
            manifest_exists = True
        if database_exists:
            resolved = validate_sealed_financial_generation(
                root,
                generation=plan.generation,
                expected_manifest_sha256=None,
                reader_api_version=plan.supported_api_versions[0],
                reader_schema_version=plan.supported_schema_versions[0],
            )
            resolved_sealed_payload = resolved.manifest.get("sealed_payload")
            if not isinstance(resolved_sealed_payload, Mapping) or resolved_sealed_payload.get(
                "input_identity_sha256"
            ) != input_identity_sha256:
                raise FinancialPublicationConflict(
                    "Existing sealed candidate has a different publication input identity."
                )
            sealed_payload = dict(resolved_sealed_payload)
            manifest_sha256 = resolved.manifest_sha256
        else:
            _require_capacity(
                root,
                estimated_candidate_bytes=(
                    plan.estimated_candidate_bytes
                    or (
                        source_path.stat().st_size
                        if plan.full_database
                        else _estimate_candidate_bytes(
                            source_path=source_path,
                            tables=plan.tables,
                            source_connection=source_connection,
                        )
                    )
                ),
                reserve_multiplier=capacity_reserve_multiplier,
            )
            building_path = final_database_path.with_name(
                f".{final_database_path.name}.{uuid.uuid4().hex}.building"
            )
            try:
                if source_connection is None:
                    sealed_payload = _build_candidate_from_attached_source(
                        source_path=source_path,
                        candidate_path=building_path,
                        plan=plan,
                        input_identity_sha256=input_identity_sha256,
                        connection_initializer=candidate_connection_initializer,
                    )
                else:
                    sealed_payload = _build_candidate_from_existing_source_connection(
                        source_connection=source_connection,
                        candidate_path=building_path,
                        plan=plan,
                        input_identity_sha256=input_identity_sha256,
                        connection_initializer=candidate_connection_initializer,
                    )
                os.replace(building_path, final_database_path)
            except BaseException as exc:
                # Builders close/detach the candidate before propagating failures.
                # Remove only this attempt's temporary files; sealed generations
                # remain available for crash recovery after the rename.
                for temporary_path in (building_path, Path(str(building_path) + ".wal")):
                    try:
                        temporary_path.unlink(missing_ok=True)
                    except OSError as cleanup_error:
                        exc.add_note(f"Could not remove {temporary_path}: {cleanup_error}")
                raise
            _notify(on_stage, "candidate_sealed")

            manifest = _external_manifest(final_database_path, sealed_payload)
            _write_atomic_json(final_manifest_path, manifest, replace=False)
            manifest_bytes = final_manifest_path.read_bytes()
            manifest_sha256 = sha256_bytes(manifest_bytes)

            # Validation happens only after the candidate writer is closed and both
            # immutable artifacts exist. It is still before the sole commit point.
            resolved = validate_sealed_financial_generation(
                root,
                generation=plan.generation,
                expected_manifest_sha256=manifest_sha256,
                reader_api_version=plan.supported_api_versions[0],
                reader_schema_version=plan.supported_schema_versions[0],
            )
        if resolved.manifest_sha256 != manifest_sha256:
            raise FinancialPublicationInvalid("Post-seal manifest verification returned a different digest.")
        _notify(on_stage, "candidate_validated")

        # Re-read the source cut after the export has closed and immediately
        # before the sole pointer commit.  This prevents a candidate from being
        # activated when its terminal/governance evidence no longer describes
        # the current source facts.
        _validate_source_dependency_snapshot(
            source_path=source_path,
            source_connection=source_connection,
            plan=plan,
        )

        # The publication lock makes this second compare-and-swap check stable.
        latest_pointer = read_publication_pointer(root, require_valid=False)
        latest_generation = str(latest_pointer["generation"]) if latest_pointer is not None else None
        if latest_generation != plan.expected_previous_generation:
            raise FinancialPublicationConflict(
                "Committed financial publication changed before pointer commit."
            )
        pointer_payload = {
            "protocol_version": PUBLICATION_PROTOCOL_VERSION,
            "generation": plan.generation,
            "manifest_sha256": manifest_sha256,
            "retained_generations": [
                {
                    "generation": plan.generation,
                    "manifest_sha256": manifest_sha256,
                },
                *(
                    [
                        {
                            "generation": str(latest_pointer["generation"]),
                            "manifest_sha256": str(latest_pointer["manifest_sha256"]),
                        }
                    ]
                    if latest_pointer is not None
                    else []
                ),
            ],
            "validity": sealed_payload["validity"],
            "committed_at": _utc_now(),
        }
        pointer_path = root / PUBLICATION_POINTER_FILE
        _notify(on_stage, "before_pointer_commit")
        _write_atomic_json(pointer_path, pointer_payload, replace=True)
        _notify(on_stage, "pointer_committed")
        return FinancialPublicationReceipt(
            status="published",
            generation=plan.generation,
            previous_generation=previous_generation,
            database_path=final_database_path,
            manifest_path=final_manifest_path,
            manifest_sha256=manifest_sha256,
            pointer_path=pointer_path,
        )


def _build_candidate_from_attached_source(
    *,
    source_path: Path,
    candidate_path: Path,
    plan: FinancialPublicationPlan,
    input_identity_sha256: str,
    connection_initializer: _CandidateConnectionInitializer | None,
) -> dict[str, object]:
    candidate = duckdb.connect(str(candidate_path), read_only=False)
    try:
        if connection_initializer is not None:
            connection_initializer(candidate, candidate_path, "candidate_build")
        source_attached = False
        try:
            candidate.execute(
                f"ATTACH {_sql_string_literal(str(source_path))} AS source_db (READ_ONLY)"
            )
            source_attached = True
            candidate.execute("BEGIN TRANSACTION")
            try:
                if plan.full_database:
                    destination_catalog = _current_database_name(candidate)
                    candidate.execute(
                        "COPY FROM DATABASE source_db TO "
                        f"{_quote_catalog_identifier(destination_catalog)}"
                    )
                else:
                    for spec in plan.tables:
                        quoted_name = _quote_identifier(spec.name)
                        candidate.execute(
                            f"CREATE TABLE {quoted_name} AS SELECT * FROM source_db.main.{quoted_name}"
                        )
                candidate.execute("COMMIT")
            except Exception:
                candidate.execute("ROLLBACK")
                raise
        finally:
            if source_attached:
                candidate.execute("DETACH source_db")
        if plan.full_database:
            _validate_full_database_dependency_boundary(candidate)
        candidate.execute("BEGIN TRANSACTION")
        try:
            sealed_payload = _seal_candidate_payload(
                candidate,
                plan=plan,
                input_identity_sha256=input_identity_sha256,
            )
            _persist_sealed_payload(candidate, plan.generation, sealed_payload)
            candidate.execute("COMMIT")
        except Exception:
            candidate.execute("ROLLBACK")
            raise
        candidate.execute("CHECKPOINT")
        return sealed_payload
    finally:
        candidate.close()


def _build_candidate_from_existing_source_connection(
    *,
    source_connection: duckdb.DuckDBPyConnection,
    candidate_path: Path,
    plan: FinancialPublicationPlan,
    input_identity_sha256: str,
    connection_initializer: _CandidateConnectionInitializer | None,
) -> dict[str, object]:
    alias = f"publication_{uuid.uuid4().hex}"
    candidate_attached = False
    try:
        source_connection.execute(
            f"ATTACH {_sql_string_literal(str(candidate_path))} AS {_quote_identifier(alias)}"
        )
        candidate_attached = True
        source_connection.execute("BEGIN TRANSACTION")
        try:
            if plan.full_database:
                source_catalog = _current_database_name(source_connection)
                source_connection.execute(
                    f"COPY FROM DATABASE {_quote_catalog_identifier(source_catalog)} "
                    f"TO {_quote_catalog_identifier(alias)}"
                )
            else:
                for spec in plan.tables:
                    quoted_name = _quote_identifier(spec.name)
                    source_connection.execute(
                        f"CREATE TABLE {_quote_identifier(alias)}.{quoted_name} "
                        f"AS SELECT * FROM main.{quoted_name}"
                    )
            source_connection.execute("COMMIT")
        except Exception:
            source_connection.execute("ROLLBACK")
            raise
    finally:
        if candidate_attached:
            source_connection.execute(f"DETACH {_quote_identifier(alias)}")
    # The caller retains its source connection; a distinct candidate writer is
    # opened only after the attachment has been closed, to force persistence.
    candidate = duckdb.connect(str(candidate_path), read_only=False)
    try:
        if connection_initializer is not None:
            connection_initializer(candidate, candidate_path, "candidate_checkpoint")
        if plan.full_database:
            _validate_full_database_dependency_boundary(candidate)
        candidate.execute("BEGIN TRANSACTION")
        try:
            sealed_payload = _seal_candidate_payload(
                candidate,
                plan=plan,
                input_identity_sha256=input_identity_sha256,
            )
            _persist_sealed_payload(candidate, plan.generation, sealed_payload)
            candidate.execute("COMMIT")
        except Exception:
            candidate.execute("ROLLBACK")
            raise
        candidate.execute("CHECKPOINT")
    finally:
        candidate.close()
    return sealed_payload


def _seal_candidate_payload(
    conn: duckdb.DuckDBPyConnection,
    *,
    plan: FinancialPublicationPlan,
    input_identity_sha256: str,
    catalog: str = "main",
) -> dict[str, object]:
    table_results = [
        _validate_table_coverage(conn, spec=spec, catalog=catalog) for spec in plan.tables
    ]
    step_results = _validated_step_results(plan)
    validity: dict[str, object] = {"state": "valid"}
    if plan.expires_at is not None:
        validity["expires_at"] = plan.expires_at
    payload: dict[str, object] = {
        "protocol_version": PUBLICATION_PROTOCOL_VERSION,
        "generation": plan.generation,
        "sealed_at": _utc_now(),
        "input_identity_sha256": input_identity_sha256,
        "tables": table_results,
        "required_steps": list(plan.required_steps),
        "step_results": step_results,
        "required_dependency_keys": list(plan.required_dependency_keys),
        "dependency_versions": dict(sorted(plan.dependency_versions.items())),
        "coverage_dates": {
            key: sorted({str(value) for value in values})
            for key, values in sorted(plan.coverage_dates.items())
        },
        "compatibility": {
            "supported_api_versions": list(plan.supported_api_versions),
            "supported_schema_versions": list(plan.supported_schema_versions),
        },
        "quality": plan.quality,
        "validity": validity,
    }
    if plan.system_read_bundle is not None:
        payload["system_read_bundle"] = plan.system_read_bundle
    return payload


def _current_database_name(conn: duckdb.DuckDBPyConnection) -> str:
    row = conn.execute("SELECT current_database()").fetchone()
    if row is None or not str(row[0] or "").strip():
        raise FinancialPublicationInvalid("Publication database catalog is unavailable.")
    return str(row[0])


def _validate_full_database_dependency_boundary(conn: duckdb.DuckDBPyConnection) -> None:
    """Reject copied views/macros that can escape the sealed DuckDB artifact."""

    catalog = _current_database_name(conn)
    view_rows = conn.execute(
        "SELECT table_schema, table_name, view_definition "
        "FROM information_schema.views WHERE table_catalog = ? "
        "AND table_schema NOT IN ('information_schema', 'pg_catalog')",
        [catalog],
    ).fetchall()
    for schema_name, view_name, definition in view_rows:
        sql = str(definition or "")
        if _EXTERNAL_RELATION_PATTERN.search(sql):
            raise FinancialPublicationInvalid(
                f"Full-database publication view {schema_name}.{view_name} has an external dependency."
            )
        try:
            conn.execute(
                f"SELECT * FROM {_quote_catalog_identifier(str(schema_name))}."
                f"{_quote_catalog_identifier(str(view_name))} LIMIT 0"
            ).fetchall()
        except Exception as exc:
            raise FinancialPublicationInvalid(
                f"Full-database publication view {schema_name}.{view_name} is not self-contained."
            ) from exc

    macro_rows = conn.execute(
        "SELECT schema_name, function_name, macro_definition "
        "FROM duckdb_functions() WHERE database_name = ? "
        "AND function_type IN ('macro', 'table_macro')",
        [catalog],
    ).fetchall()
    for schema_name, function_name, definition in macro_rows:
        if _EXTERNAL_RELATION_PATTERN.search(str(definition or "")):
            raise FinancialPublicationInvalid(
                f"Full-database publication macro {schema_name}.{function_name} has an external dependency."
            )


def _persist_sealed_payload(
    conn: duckdb.DuckDBPyConnection,
    generation: str,
    sealed_payload: Mapping[str, object],
    *,
    catalog: str = "main",
) -> None:
    payload_json = canonical_json_bytes(sealed_payload).decode("utf-8")
    payload_sha256 = sha256_bytes(payload_json.encode("utf-8"))
    qualified_table = f"{_quote_identifier(catalog)}.{_quote_identifier(PUBLICATION_MANIFEST_TABLE)}"
    conn.execute(
        f"CREATE TABLE {qualified_table} ("
        "protocol_version VARCHAR NOT NULL, generation VARCHAR NOT NULL, "
        "sealed_payload_json VARCHAR NOT NULL, sealed_payload_sha256 VARCHAR NOT NULL)"
    )
    conn.execute(
        f"INSERT INTO {qualified_table} VALUES (?, ?, ?, ?)",
        [PUBLICATION_PROTOCOL_VERSION, generation, payload_json, payload_sha256],
    )


def _validate_table_coverage(
    conn: duckdb.DuckDBPyConnection,
    *,
    spec: FinancialTablePublicationSpec,
    catalog: str,
) -> dict[str, object]:
    qualified_table = f"{_quote_identifier(catalog)}.{_quote_identifier(spec.name)}"
    if catalog == "main":
        catalog_row = conn.execute("SELECT current_database()").fetchone()
        if catalog_row is None or catalog_row[0] is None:
            raise FinancialPublicationInvalid("Publication source catalog is unavailable.")
        catalog_name = str(catalog_row[0])
    else:
        catalog_name = catalog
    columns = conn.execute(
        "SELECT column_name, data_type, is_nullable, ordinal_position "
        "FROM information_schema.columns WHERE table_catalog = ? AND table_schema = 'main' "
        "AND table_name = ? ORDER BY ordinal_position",
        [catalog_name, spec.name],
    ).fetchall()
    if not columns:
        raise FinancialPublicationInvalid(f"Required publication table {spec.name!r} is missing.")
    total_row = conn.execute(f"SELECT count(*) FROM {qualified_table}").fetchone()
    if total_row is None or total_row[0] is None:
        raise FinancialPublicationInvalid(
            f"Required publication table {spec.name!r} row count is unavailable."
        )
    total_rows = int(total_row[0])
    if total_rows < spec.minimum_total_rows:
        raise FinancialPublicationInvalid(
            f"Required publication table {spec.name!r} has {total_rows} rows; "
            f"minimum is {spec.minimum_total_rows}."
        )
    coverage: dict[str, int] = {}
    if spec.date_column is not None:
        if spec.date_column not in {str(row[0]) for row in columns}:
            raise FinancialPublicationInvalid(
                f"Coverage column {spec.date_column!r} is missing from table {spec.name!r}."
            )
        for required_date in spec.required_dates:
            coverage_row = conn.execute(
                f"SELECT count(*) FROM {qualified_table} "
                f"WHERE try_cast({_quote_identifier(spec.date_column)} AS DATE) = cast(? AS DATE)",
                [required_date],
            ).fetchone()
            if coverage_row is None or coverage_row[0] is None:
                raise FinancialPublicationInvalid(
                    f"Required publication table {spec.name!r} coverage count is unavailable "
                    f"for {required_date}."
                )
            row_count = int(coverage_row[0])
            coverage[required_date] = row_count
            if row_count < spec.minimum_rows_per_date:
                raise FinancialPublicationInvalid(
                    f"Required publication table {spec.name!r} has {row_count} rows for "
                    f"{required_date}; minimum is {spec.minimum_rows_per_date}."
                )
    schema_payload = [
        {
            "name": str(row[0]),
            "type": str(row[1]),
            "nullable": str(row[2]),
            "ordinal": int(row[3]),
        }
        for row in columns
    ]
    return {
        "name": spec.name,
        "date_column": spec.date_column,
        "required_dates": list(spec.required_dates),
        "minimum_rows_per_date": spec.minimum_rows_per_date,
        "minimum_total_rows": spec.minimum_total_rows,
        "total_rows": total_rows,
        "coverage_row_counts": coverage,
        "schema_sha256": sha256_bytes(canonical_json_bytes(schema_payload)),
    }


def _validated_step_results(plan: FinancialPublicationPlan) -> dict[str, object]:
    results: dict[str, object] = {}
    by_name = {str(receipt.get("name") or ""): receipt for receipt in plan.step_receipts}
    for step in plan.required_steps:
        receipt = by_name[step]
        result = receipt["result"]
        assert isinstance(result, Mapping)
        results[step] = {
            "status": "completed",
            "result_sha256": sha256_bytes(canonical_json_bytes(result)),
        }
    return results


def _validate_plan(plan: FinancialPublicationPlan) -> None:
    validate_generation(plan.generation)
    if type(plan.full_database) is not bool:
        raise FinancialPublicationInvalid("Financial publication full_database must be a bool.")
    if plan.full_database:
        if plan.system_read_bundle is None:
            raise FinancialPublicationInvalid(
                "Full-database publication requires a system read bundle."
            )
        _validate_system_read_bundle(plan.system_read_bundle)
    elif plan.system_read_bundle is not None:
        raise FinancialPublicationInvalid(
            "A system read bundle is valid only for a full-database publication."
        )
    if plan.expected_previous_generation is not None:
        validate_generation(plan.expected_previous_generation)
    if not plan.tables:
        raise FinancialPublicationInvalid("Financial publication requires at least one result table.")
    if not callable(plan.source_dependency_validator):
        raise FinancialPublicationInvalid("Financial publication requires a source dependency validator.")
    table_names: set[str] = set()
    required_table_dates: set[str] = set()
    for spec in plan.tables:
        _validate_identifier(spec.name, label="table")
        if spec.name == PUBLICATION_MANIFEST_TABLE or spec.name in table_names:
            raise FinancialPublicationInvalid(f"Publication table {spec.name!r} is duplicated or reserved.")
        table_names.add(spec.name)
        if spec.minimum_total_rows < 0 or spec.minimum_rows_per_date < 1:
            raise FinancialPublicationInvalid("Publication table row thresholds are invalid.")
        if spec.date_column is None and spec.required_dates:
            raise FinancialPublicationInvalid(
                f"Publication table {spec.name!r} declares dates without a date column."
            )
        if spec.date_column is not None:
            _validate_identifier(spec.date_column, label="date column")
            if not spec.required_dates:
                raise FinancialPublicationInvalid(
                    f"Dated publication table {spec.name!r} requires explicit coverage dates."
                )
            normalized_dates = tuple(_normalize_date(value) for value in spec.required_dates)
            if len(set(normalized_dates)) != len(normalized_dates):
                raise FinancialPublicationInvalid(
                    f"Publication table {spec.name!r} contains duplicate coverage dates."
                )
            required_table_dates.update(normalized_dates)

    if not plan.required_steps or len(set(plan.required_steps)) != len(plan.required_steps):
        raise FinancialPublicationInvalid("Financial publication required steps must be non-empty and unique.")
    receipt_names = [str(receipt.get("name") or "") for receipt in plan.step_receipts]
    if len(receipt_names) != len(set(receipt_names)):
        raise FinancialPublicationInvalid("Financial publication step receipts contain duplicate names.")
    if set(receipt_names) != set(plan.required_steps):
        raise FinancialPublicationInvalid(
            "Financial publication step receipts must exactly match the required business steps."
        )
    for receipt in plan.step_receipts:
        if str(receipt.get("status") or "").lower() != "completed":
            raise FinancialPublicationInvalid(
                f"Financial publication step {receipt.get('name')!r} is incomplete."
            )
        result = receipt.get("result")
        if not isinstance(result, Mapping) or not result:
            raise FinancialPublicationInvalid(
                f"Financial publication step {receipt.get('name')!r} has no result evidence."
            )
        if str(result.get("status") or "").lower() != "completed":
            raise FinancialPublicationInvalid(
                f"Financial publication step {receipt.get('name')!r} result is not completed."
            )

    if not plan.required_dependency_keys or len(set(plan.required_dependency_keys)) != len(
        plan.required_dependency_keys
    ):
        raise FinancialPublicationInvalid(
            "Financial publication required dependency keys must be non-empty and unique."
        )
    missing_dependencies = set(plan.required_dependency_keys) - set(plan.dependency_versions)
    if missing_dependencies:
        raise FinancialPublicationInvalid(
            f"Financial publication dependency versions are incomplete: {sorted(missing_dependencies)}."
        )
    if any(not str(value or "").strip() for value in plan.dependency_versions.values()):
        raise FinancialPublicationInvalid("Financial publication dependency versions cannot be blank.")

    if not plan.coverage_dates:
        raise FinancialPublicationInvalid("Financial publication coverage dates are required.")
    declared_dates: set[str] = set()
    for key, values in plan.coverage_dates.items():
        if not str(key or "").strip() or not values:
            raise FinancialPublicationInvalid("Financial publication coverage groups must be named and non-empty.")
        declared_dates.update(_normalize_date(value) for value in values)
    if not declared_dates.issubset(required_table_dates):
        raise FinancialPublicationInvalid(
            "Every declared business coverage date must be verified by at least one published table."
        )
    if not plan.supported_api_versions or any(not str(value).strip() for value in plan.supported_api_versions):
        raise FinancialPublicationInvalid("Financial publication API compatibility is required.")
    if not plan.supported_schema_versions or any(
        not str(value).strip() for value in plan.supported_schema_versions
    ):
        raise FinancialPublicationInvalid("Financial publication schema compatibility is required.")
    quality_status = str(plan.quality.get("status") or "").lower()
    quality_checks = plan.quality.get("checks")
    if quality_status not in _PASSING_STATUSES or not isinstance(quality_checks, Sequence) or not quality_checks:
        raise FinancialPublicationInvalid("Financial publication quality evidence is missing or failed.")
    for check in quality_checks:
        if not isinstance(check, Mapping) or str(check.get("status") or "").lower() not in _PASSING_STATUSES:
            raise FinancialPublicationInvalid("Financial publication contains a failed quality check.")
    if plan.expires_at is not None:
        expires_at = _parse_utc_timestamp(plan.expires_at)
        if expires_at <= datetime.now(UTC):
            raise FinancialPublicationInvalid("Financial publication expiry must be in the future.")
    if plan.estimated_candidate_bytes is not None and plan.estimated_candidate_bytes < 1:
        raise FinancialPublicationInvalid("Financial publication size estimate must be positive.")


def _plan_identity_sha256(plan: FinancialPublicationPlan) -> str:
    receipts = {
        str(receipt["name"]): sha256_bytes(canonical_json_bytes(receipt["result"]))
        for receipt in plan.step_receipts
    }
    payload: dict[str, object] = {
        "generation": plan.generation,
        "expected_previous_generation": plan.expected_previous_generation,
        "tables": [
            {
                "name": spec.name,
                "date_column": spec.date_column,
                "required_dates": list(spec.required_dates),
                "minimum_rows_per_date": spec.minimum_rows_per_date,
                "minimum_total_rows": spec.minimum_total_rows,
            }
            for spec in plan.tables
        ],
        "required_steps": list(plan.required_steps),
        "step_result_sha256": receipts,
        "required_dependency_keys": list(plan.required_dependency_keys),
        "dependency_versions": dict(sorted(plan.dependency_versions.items())),
        "coverage_dates": {
            key: sorted(str(value) for value in values)
            for key, values in sorted(plan.coverage_dates.items())
        },
        "supported_api_versions": list(plan.supported_api_versions),
        "supported_schema_versions": list(plan.supported_schema_versions),
        "quality": plan.quality,
        "expires_at": plan.expires_at,
    }
    if plan.full_database:
        payload["full_database"] = True
        payload["system_read_bundle"] = plan.system_read_bundle
    return sha256_bytes(canonical_json_bytes(payload))


def _validate_system_read_bundle(bundle: Mapping[str, object]) -> None:
    legacy_fields = {
        "protocol_version",
        "active_database_identity",
        "full_database",
        "governance_base_identity",
        "governance_streams",
        "pnl_generation",
        "pnl_manifest_sha256",
        "data_update_run_id",
        "global_run_id",
        "workflow",
        "report_date",
    }
    extended_fields = legacy_fields | {
        "writer_run_id",
        "writer_receipt_sha256",
        "terminal_references",
        "required_table_coverage",
    }
    v2_fields = extended_fields | {"pretrade_availability"}
    bundle_fields = set(bundle)
    if bundle_fields not in {
        frozenset(legacy_fields),
        frozenset(extended_fields),
        frozenset(v2_fields),
    }:
        raise FinancialPublicationInvalid(
            "System read bundle fields do not match a supported protocol version."
        )
    protocol_version = bundle.get("protocol_version")
    v1_bundle = bundle_fields in {frozenset(legacy_fields), frozenset(extended_fields)}
    if type(protocol_version) is not int or (
        (v1_bundle and protocol_version != 1)
        or (not v1_bundle and protocol_version != 2)
    ):
        raise FinancialPublicationInvalid(
            "System read bundle protocol_version does not match its field set."
        )
    extended_bundle = bundle_fields != legacy_fields
    if bundle.get("full_database") is not True:
        raise FinancialPublicationInvalid("System read bundle must declare full_database=true.")
    for field_name in (
        "active_database_identity",
        "governance_base_identity",
        "pnl_generation",
        "pnl_manifest_sha256",
        "workflow",
        "report_date",
    ):
        if not isinstance(bundle.get(field_name), str) or not str(bundle[field_name]).strip():
            raise FinancialPublicationInvalid(
                f"System read bundle {field_name} must be a non-empty string."
            )
    workflow = str(bundle["workflow"])
    if extended_bundle:
        writer_run_id = bundle.get("writer_run_id")
        writer_receipt_sha256 = bundle.get("writer_receipt_sha256")
        if not isinstance(writer_run_id, str) or not writer_run_id.strip():
            raise FinancialPublicationInvalid(
                "System read bundle writer_run_id must be a non-empty string."
            )
        if not isinstance(writer_receipt_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", writer_receipt_sha256
        ):
            raise FinancialPublicationInvalid(
                "System read bundle writer_receipt_sha256 must be a lowercase SHA-256 digest."
            )
        data_update_run_id = bundle.get("data_update_run_id")
        global_run_id = bundle.get("global_run_id")
        for field_name, value in (
            ("data_update_run_id", data_update_run_id),
            ("global_run_id", global_run_id),
        ):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise FinancialPublicationInvalid(
                    f"System read bundle {field_name} must be null or a non-empty string."
                )
        if workflow == "core_financial" and (
            not isinstance(data_update_run_id, str)
            or not data_update_run_id.strip()
            or not isinstance(global_run_id, str)
            or not global_run_id.strip()
        ):
            raise FinancialPublicationInvalid(
                "Core financial system read bundle requires both parent run identities."
            )
        if workflow == "balance_daily" and (
            data_update_run_id != writer_run_id or global_run_id is not None
        ):
            raise FinancialPublicationInvalid(
                "Balance daily system read bundle has invalid writer identity."
            )
        if workflow == "market_daily" and (
            data_update_run_id is not None or global_run_id is not None
        ):
            raise FinancialPublicationInvalid(
                "Market daily system read bundle must use standalone writer identity."
            )
        if workflow not in {"core_financial", "balance_daily", "market_daily"}:
            raise FinancialPublicationInvalid("System read bundle workflow is unsupported.")
        for evidence_field in ("terminal_references", "required_table_coverage"):
            evidence = bundle.get(evidence_field)
            if not isinstance(evidence, list) or not evidence:
                raise FinancialPublicationInvalid(
                    f"System read bundle {evidence_field} must be a non-empty list."
                )
        if bundle_fields == v2_fields:
            pretrade_availability = bundle.get("pretrade_availability")
            normalized_pretrade = normalize_pretrade_qualification(
                pretrade_availability
            )
            if (
                not isinstance(pretrade_availability, Mapping)
                or normalized_pretrade != dict(pretrade_availability)
            ):
                raise FinancialPublicationInvalid(
                    "System read bundle pretrade_availability must be normalized qualification evidence."
                )
    else:
        for field_name in ("data_update_run_id", "global_run_id"):
            if not isinstance(bundle.get(field_name), str) or not str(
                bundle[field_name]
            ).strip():
                raise FinancialPublicationInvalid(
                    f"System read bundle {field_name} must be a non-empty string."
                )
    for path_field in ("active_database_identity", "governance_base_identity"):
        value = str(bundle[path_field])
        if not Path(value).is_absolute() or str(Path(value).resolve()) != value:
            raise FinancialPublicationInvalid(
                f"System read bundle {path_field} must be a canonical absolute path."
            )
    manifest_sha256 = str(bundle["pnl_manifest_sha256"])
    if not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256):
        raise FinancialPublicationInvalid(
            "System read bundle pnl_manifest_sha256 must be a lowercase SHA-256 digest."
        )
    report_date = bundle["report_date"]
    if not isinstance(report_date, str):
        raise FinancialPublicationInvalid("System read bundle report_date must be a non-empty string.")
    _normalize_date(report_date)
    streams = bundle.get("governance_streams")
    if not isinstance(streams, Mapping) or set(streams) != {"cache_build_run", "cache_manifest"}:
        raise FinancialPublicationInvalid(
            "System read bundle governance_streams must contain only the result-lineage allowlist."
        )
    for stream_name, rows in streams.items():
        if not isinstance(rows, list) or not rows:
            raise FinancialPublicationInvalid(
                f"System read bundle governance stream {stream_name!r} must be a non-empty list."
            )
        if any(not isinstance(row, Mapping) for row in rows):
            raise FinancialPublicationInvalid(
                f"System read bundle governance stream {stream_name!r} contains a non-object row."
            )


def _recover_committed_generation(
    root: Path,
    *,
    plan: FinancialPublicationPlan,
    pointer: Mapping[str, object] | None,
    input_identity_sha256: str,
) -> FinancialPublicationReceipt | None:
    if pointer is None or pointer.get("generation") != plan.generation:
        return None
    resolved: ResolvedFinancialPublication = resolve_financial_generation(
        root,
        generation=plan.generation,
        reader_api_version=plan.supported_api_versions[0],
        reader_schema_version=plan.supported_schema_versions[0],
    )
    sealed_payload = resolved.manifest.get("sealed_payload")
    if not isinstance(sealed_payload, Mapping) or sealed_payload.get(
        "input_identity_sha256"
    ) != input_identity_sha256:
        raise FinancialPublicationConflict(
            "The requested generation is committed with a different publication input identity."
        )
    return FinancialPublicationReceipt(
        status="already_published",
        generation=plan.generation,
        previous_generation=plan.expected_previous_generation,
        database_path=resolved.database_path,
        manifest_path=resolved.manifest_path,
        manifest_sha256=resolved.manifest_sha256,
        pointer_path=root / PUBLICATION_POINTER_FILE,
        recovered_after_commit=True,
    )


def _require_capacity(root: Path, *, estimated_candidate_bytes: int, reserve_multiplier: float) -> None:
    required_free_bytes = max(1, math.ceil(estimated_candidate_bytes * reserve_multiplier))
    available_bytes = int(shutil.disk_usage(root).free)
    if available_bytes < required_free_bytes:
        raise FinancialPublicationCapacityError(
            "Insufficient free space for a sealed financial publication candidate: "
            f"required={required_free_bytes}, available={available_bytes}."
        )


def _validate_source_dependency_snapshot(
    *,
    source_path: Path,
    source_connection: duckdb.DuckDBPyConnection | None,
    plan: FinancialPublicationPlan,
) -> None:
    owned_connection = source_connection is None
    conn = source_connection or duckdb.connect(str(source_path), read_only=True)
    try:
        actual = plan.source_dependency_validator(conn)
    finally:
        if owned_connection:
            conn.close()
    if not isinstance(actual, Mapping):
        raise FinancialPublicationInvalid("Source dependency validator returned a non-mapping result.")
    normalized_actual = {str(key): str(value) for key, value in actual.items()}
    normalized_expected = {
        str(key): str(value) for key, value in plan.dependency_versions.items()
    }
    if normalized_actual != normalized_expected:
        changed_keys = sorted(
            key
            for key in set(normalized_actual) | set(normalized_expected)
            if normalized_actual.get(key) != normalized_expected.get(key)
        )
        raise FinancialPublicationConflict(
            "Financial publication source dependencies changed after the plan was built: "
            f"{changed_keys}."
        )


def _read_sealed_payload_from_database(
    database_path: Path,
    *,
    expected_generation: str,
    expected_input_identity_sha256: str,
) -> dict[str, object]:
    conn = duckdb.connect(str(database_path), read_only=True)
    try:
        row = conn.execute(
            f'SELECT protocol_version, generation, sealed_payload_json, sealed_payload_sha256 '
            f'FROM "{PUBLICATION_MANIFEST_TABLE}"'
        ).fetchone()
    except duckdb.Error as exc:
        raise FinancialPublicationConflict(
            "Incomplete candidate has no recoverable sealed payload."
        ) from exc
    finally:
        conn.close()
    if row is None or row[0] != PUBLICATION_PROTOCOL_VERSION or row[1] != expected_generation:
        raise FinancialPublicationConflict("Incomplete candidate identity cannot be recovered safely.")
    try:
        payload = json.loads(str(row[2]))
    except json.JSONDecodeError as exc:
        raise FinancialPublicationConflict("Incomplete candidate sealed payload is invalid.") from exc
    if not isinstance(payload, dict):
        raise FinancialPublicationConflict("Incomplete candidate sealed payload is not an object.")
    if sha256_bytes(canonical_json_bytes(payload)) != str(row[3]):
        raise FinancialPublicationConflict("Incomplete candidate sealed payload digest is invalid.")
    if payload.get("input_identity_sha256") != expected_input_identity_sha256:
        raise FinancialPublicationConflict(
            "Incomplete candidate belongs to a different publication input identity."
        )
    return payload


def _external_manifest(
    database_path: Path,
    sealed_payload: Mapping[str, object],
) -> dict[str, object]:
    return {
        "protocol_version": PUBLICATION_PROTOCOL_VERSION,
        "generation": sealed_payload["generation"],
        "sealed_payload": sealed_payload,
        "sealed_payload_sha256": sha256_bytes(canonical_json_bytes(sealed_payload)),
        "database": {
            "file_name": database_path.name,
            "size_bytes": database_path.stat().st_size,
            "sha256": sha256_file(database_path),
        },
        "validity": sealed_payload["validity"],
        "compatibility": sealed_payload["compatibility"],
    }


def _estimate_candidate_bytes(
    *,
    source_path: Path,
    tables: tuple[FinancialTablePublicationSpec, ...],
    source_connection: duckdb.DuckDBPyConnection | None,
) -> int:
    owned_connection = source_connection is None
    conn = source_connection or duckdb.connect(str(source_path), read_only=True)
    try:
        size_row = conn.execute("SELECT block_size FROM pragma_database_size()").fetchone()
        block_size = int(size_row[0]) if size_row is not None else 262_144
        persistent_blocks: set[int] = set()
        transient_cells = 0
        for spec in tables:
            rows = conn.execute(
                "SELECT block_id, additional_block_ids, persistent, count "
                "FROM pragma_storage_info(?)",
                [spec.name],
            ).fetchall()
            for block_id, additional_block_ids, persistent, count in rows:
                if persistent and block_id is not None and int(block_id) >= 0:
                    persistent_blocks.add(int(block_id))
                for additional in additional_block_ids or []:
                    if int(additional) >= 0:
                        persistent_blocks.add(int(additional))
                if not persistent:
                    transient_cells += max(0, int(count or 0))
        # Persistent blocks are measured from DuckDB storage metadata. Fresh WAL
        # segments do not yet have blocks, so reserve 32 bytes per observed cell;
        # table/catalog/manifest overhead gets at least eight blocks.
        return max(
            block_size * 8,
            len(persistent_blocks) * block_size
            + transient_cells * 32
            + block_size * (len(tables) + 4),
        )
    finally:
        if owned_connection:
            conn.close()


def _notify(callback: Callable[[str], None] | None, stage: str) -> None:
    if callback is not None:
        callback(stage)


def _validate_identifier(value: str, *, label: str) -> None:
    if not _IDENTIFIER_PATTERN.fullmatch(str(value or "")):
        raise FinancialPublicationInvalid(f"Invalid publication {label} identifier: {value!r}.")


def _quote_identifier(value: str) -> str:
    _validate_identifier(value, label="SQL")
    return f'"{value}"'


def _quote_catalog_identifier(value: str) -> str:
    normalized = str(value or "")
    if not normalized:
        raise FinancialPublicationInvalid("Invalid empty publication SQL identifier.")
    return '"' + normalized.replace('"', '""') + '"'


def _sql_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _normalize_date(value: str) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise FinancialPublicationInvalid(
            f"Financial publication coverage date is invalid: {value!r}."
        ) from exc


def _parse_utc_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise FinancialPublicationInvalid("Financial publication expiry timestamp is invalid.") from exc
    if parsed.tzinfo is None:
        raise FinancialPublicationInvalid("Financial publication expiry timestamp must include a timezone.")
    return parsed.astimezone(UTC)

