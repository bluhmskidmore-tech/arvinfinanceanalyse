"""Controlled import of one date's three native Choice point-in-time inputs."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, SupportsIndex, SupportsInt, TypedDict, cast

import duckdb
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.tasks.choice_stock_materialize import (
    _is_choice_historical_pit_audit,
    load_choice_stock_materialization_coverage,
)

IMPORT_SCHEMA = "choice_stock_pit_import/v1"
SOURCE_VERSION_PATTERN = re.compile(r"^sv_choice_stock_[0-9a-f]{12}$")
VENDOR_VERSION_PATTERN = re.compile(
    r"^vv_choice_(?:tushare_)?stock_\d{8}_[0-9a-f]{12}$"
)


class _TableEvidence(TypedDict):
    row_count: int
    rows_sha256: str
    natural_keys_sha256: str


class _SourceScope(TypedDict):
    source_sha256: str
    rows_by_table: dict[str, list[dict[str, object]]]
    audits: list[dict[str, object]]
    audits_sha256: str
    table_evidence: dict[str, _TableEvidence]
    stock_code_count: int
    stock_codes_sha256: str
    lineage: dict[str, str]


class _PlanBody(TypedDict):
    schema: str
    as_of_date: str
    source_sha256: str
    source_table_evidence: dict[str, _TableEvidence]
    source_audits_sha256: str
    source_stock_code_count: int
    source_stock_codes_sha256: str
    source_lineage: dict[str, str]
    insert_counts: dict[str, int]
    insert_rows_sha256: dict[str, str]
    identical_counts: dict[str, int]
    audit_insert_count: int
    audit_insert_sha256: str
    audit_identical_count: int
    target_scope_before_sha256: dict[str, str]
    protected_before_sha256: dict[str, str]
    target_missing_request_items_before: list[str]


class _ImportPlan(_PlanBody):
    plan_sha256: str
    _insert_rows_by_table: dict[str, list[dict[str, object]]]
    _insert_audits: list[dict[str, object]]


class _WriteMetadata(TypedDict):
    inserted_counts: dict[str, int]
    audit_inserted_count: int
    inserted_total: int
    post_write_validation: dict[str, object]


@dataclass(frozen=True)
class PitTableSpec:
    table: str
    input_family: str
    field_key: str
    columns: tuple[str, ...]

    @property
    def item(self) -> tuple[str, str]:
        return (self.input_family, self.field_key)


PIT_SPECS = (
    PitTableSpec(
        table="choice_stock_universe",
        input_family="stock_universe",
        field_key="a_share_universe_sector_001004",
        columns=(
            "as_of_date",
            "stock_code",
            "stock_name",
            "field_key",
            "source_version",
            "vendor_version",
            "rule_version",
            "run_id",
        ),
    ),
    PitTableSpec(
        table="choice_stock_sector_membership",
        input_family="sector_membership",
        field_key="sw2021_industry_membership",
        columns=(
            "as_of_date",
            "stock_code",
            "sw2021",
            "sw2021code",
            "field_key",
            "source_version",
            "vendor_version",
            "rule_version",
            "run_id",
        ),
    ),
    PitTableSpec(
        table="choice_stock_limit_quality",
        input_family="limit_up_quality",
        field_key="point_in_time_limit_streaks",
        columns=(
            "as_of_date",
            "stock_code",
            "issurgedlimit",
            "isdeclinelimit",
            "hlimitedays",
            "llimitedays",
            "field_key",
            "source_version",
            "vendor_version",
            "rule_version",
            "run_id",
        ),
    ),
)
PIT_ITEMS = tuple(spec.item for spec in PIT_SPECS)
PIT_ITEM_NAMES = frozenset(f"{family}:{field_key}" for family, field_key in PIT_ITEMS)
AUDIT_COLUMNS = (
    "run_id",
    "as_of_date",
    "input_family",
    "field_key",
    "call",
    "vendor_indicator",
    "request_arguments_json",
    "request_options_json",
    "status",
    "row_count",
    "error_code",
    "error_msg",
    "source_version",
    "vendor_version",
    "rule_version",
)


def import_choice_stock_pit_snapshot(
    duckdb_path: str | Path,
    *,
    source_duckdb_path: str | Path,
    as_of_date: str | date,
    expected_source_sha256: str,
    receipt_path: str | Path,
    apply_changes: bool = False,
    expected_plan_sha256: str | None = None,
    target_backup_path: str | Path | None = None,
) -> dict[str, object]:
    """Preview or import exactly three native Choice PIT items for one date."""

    started_at = datetime.now(UTC)
    changes_committed = False
    target_path = Path(duckdb_path).resolve(strict=True)
    source_path = Path(source_duckdb_path).resolve(strict=True)
    resolved_receipt_path = Path(receipt_path).resolve()
    resolved_date = _normalize_date(as_of_date)
    try:
        if source_path == target_path or source_path.samefile(target_path):
            raise ValueError("source and target DuckDB paths must be different")
        source = _load_source_scope(
            source_path,
            as_of_date=resolved_date,
            expected_source_sha256=expected_source_sha256,
        )
        if not apply_changes:
            with duckdb.connect(str(target_path), read_only=True) as conn:
                plan = _build_plan(conn, source=source, as_of_date=resolved_date)
            result = _build_result(
                status="dry_run",
                target_path=target_path,
                source_path=source_path,
                as_of_date=resolved_date,
                plan=plan,
                source=source,
            )
            result.update(_timing_fields(started_at))
            _write_json_atomic(resolved_receipt_path, result)
            return result

        expected_plan = _normalize_sha256(
            expected_plan_sha256,
            field_name="expected_plan_sha256",
        )
        writer_lock = resolve_duckdb_writer_lock(target_path, ttl_seconds=900)
        with acquire_lock(writer_lock, base_dir=target_path.parent, timeout_seconds=30):
            backup = _verify_byte_identical_backup(
                target_path,
                target_backup_path=target_backup_path,
                source_path=source_path,
            )
            if source_path.samefile(target_path):
                raise ValueError("source and target DuckDB paths must be different")
            source = _load_source_scope(
                source_path,
                as_of_date=resolved_date,
                expected_source_sha256=expected_source_sha256,
            )
            with duckdb.connect(str(target_path), read_only=False) as conn:
                plan = _build_plan(conn, source=source, as_of_date=resolved_date)
                if plan["plan_sha256"] != expected_plan:
                    raise RuntimeError(
                        "PIT import plan changed after dry-run; rerun dry-run and review plan_sha256"
                    )
                write_metadata = _apply_plan(
                    conn,
                    plan=plan,
                    source=source,
                    as_of_date=resolved_date,
                )
                changes_committed = int(write_metadata["inserted_total"]) > 0

        result = _build_result(
            status="completed",
            target_path=target_path,
            source_path=source_path,
            as_of_date=resolved_date,
            plan=plan,
            source=source,
        )
        result.update(backup)
        result.update(write_metadata)
        result.update(_timing_fields(started_at))
        _write_json_atomic(resolved_receipt_path, result)
        return result
    except Exception as exc:
        failure = {
            "schema": IMPORT_SCHEMA,
            "status": "failed",
            "duckdb_path": str(target_path),
            "source_duckdb_path": str(source_path),
            "as_of_date": resolved_date,
            "duckdb_written": changes_committed,
            "production_duckdb_written": (
                changes_committed and _is_production_target(target_path)
            ),
            "no_changes_committed": not changes_committed,
            "error_type": type(exc).__name__,
            "error": " ".join(str(exc).split())[:1000],
            **_timing_fields(started_at),
        }
        try:
            _write_json_atomic(resolved_receipt_path, failure)
        except OSError:
            pass
        raise


def _load_source_scope(
    source_path: Path,
    *,
    as_of_date: str,
    expected_source_sha256: str,
) -> _SourceScope:
    expected_hash = _normalize_sha256(
        expected_source_sha256,
        field_name="expected_source_sha256",
    )
    source_hash = _file_sha256(source_path)
    if source_hash != expected_hash:
        raise RuntimeError("source DuckDB SHA256 does not match expected_source_sha256")

    with duckdb.connect(str(source_path), read_only=True) as conn:
        _assert_required_schema(conn)
        rows_by_table = {
            spec.table: _load_scope_rows(conn, spec=spec, as_of_date=as_of_date)
            for spec in PIT_SPECS
        }
        audits = _load_source_audits(conn, as_of_date=as_of_date)
        coverage = load_choice_stock_materialization_coverage(
            duckdb_path=str(source_path),
            as_of_date=as_of_date,
            required_items=PIT_ITEMS,
            conn=conn,
        )
    if _file_sha256(source_path) != source_hash:
        raise RuntimeError("source DuckDB changed while the PIT import scope was being read")

    counts = {table: len(rows) for table, rows in rows_by_table.items()}
    if not counts or 0 in counts.values() or len(set(counts.values())) != 1:
        raise RuntimeError(f"source PIT row counts must be equal and nonzero: {counts}")
    stock_sets = {
        table: {str(row["stock_code"]) for row in rows}
        for table, rows in rows_by_table.items()
    }
    first_codes = next(iter(stock_sets.values()))
    if any(codes != first_codes for codes in stock_sets.values()):
        raise RuntimeError("source PIT stock-code coverage differs across the three tables")
    if not coverage.full_coverage:
        raise RuntimeError(f"source does not have qualified native Choice PIT evidence: {coverage.message}")

    lineage_values = {
        (
            str(row["source_version"] or ""),
            str(row["vendor_version"] or ""),
            str(row["rule_version"] or ""),
            str(row["run_id"] or ""),
        )
        for rows in rows_by_table.values()
        for row in rows
    }
    if len(lineage_values) != 1:
        raise RuntimeError("source PIT rows do not share one materializer lineage")
    lineage = next(iter(lineage_values))
    _validate_lineage(lineage, as_of_date=as_of_date)
    _validate_source_audits(
        audits,
        as_of_date=as_of_date,
        lineage=lineage,
        row_counts=counts,
        stock_codes=first_codes,
    )

    table_evidence: dict[str, _TableEvidence] = {
        spec.table: {
            "row_count": len(rows_by_table[spec.table]),
            "rows_sha256": _canonical_sha256(rows_by_table[spec.table]),
            "natural_keys_sha256": _canonical_sha256(
                [
                    [row["as_of_date"], row["stock_code"], row["field_key"]]
                    for row in rows_by_table[spec.table]
                ]
            ),
        }
        for spec in PIT_SPECS
    }
    return {
        "source_sha256": source_hash,
        "rows_by_table": rows_by_table,
        "audits": audits,
        "audits_sha256": _canonical_sha256(audits),
        "table_evidence": table_evidence,
        "stock_code_count": len(first_codes),
        "stock_codes_sha256": _canonical_sha256(sorted(first_codes)),
        "lineage": {
            "source_version": lineage[0],
            "vendor_version": lineage[1],
            "rule_version": lineage[2],
            "run_id": lineage[3],
        },
    }


def _build_plan(
    conn: duckdb.DuckDBPyConnection,
    *,
    source: _SourceScope,
    as_of_date: str,
) -> _ImportPlan:
    _assert_required_schema(conn)
    target_coverage = load_choice_stock_materialization_coverage(
        duckdb_path="",
        as_of_date=as_of_date,
        conn=conn,
    )
    unexpected_missing = set(target_coverage.missing_request_items) - PIT_ITEM_NAMES
    if unexpected_missing:
        raise RuntimeError(
            "target is missing inputs outside the approved PIT scope: "
            + ", ".join(sorted(unexpected_missing))
        )

    inserts_by_table: dict[str, list[dict[str, object]]] = {}
    identical_counts: dict[str, int] = {}
    target_scope_before: dict[str, str] = {}
    for spec in PIT_SPECS:
        source_rows = list(dict(source["rows_by_table"])[spec.table])
        target_rows = _load_scope_rows(conn, spec=spec, as_of_date=as_of_date)
        target_by_key = {_row_key(row): row for row in target_rows}
        source_by_key = {_row_key(row): row for row in source_rows}
        extra_keys = sorted(set(target_by_key) - set(source_by_key))
        if extra_keys:
            raise RuntimeError(
                f"target {spec.table} has keys absent from the reviewed source: {extra_keys[0]}"
            )
        inserts: list[dict[str, object]] = []
        identical = 0
        for key, source_row in source_by_key.items():
            target_row = target_by_key.get(key)
            if target_row is None:
                inserts.append(source_row)
            elif target_row == source_row:
                identical += 1
            else:
                raise RuntimeError(f"conflicting nonempty target PIT row: {spec.table} {key}")
        inserts_by_table[spec.table] = inserts
        identical_counts[spec.table] = identical
        target_scope_before[spec.table] = _canonical_sha256(target_rows)

    source_audits = list(source["audits"])
    audit_inserts: list[dict[str, object]] = []
    audit_identical = 0
    for source_audit in source_audits:
        existing = _load_exact_audit(conn, source_audit)
        if len(existing) > 1:
            raise RuntimeError(f"duplicate target audit natural key: {_audit_key(source_audit)}")
        if not existing:
            audit_inserts.append(source_audit)
        elif existing[0] == source_audit:
            audit_identical += 1
        else:
            raise RuntimeError(f"conflicting target audit natural key: {_audit_key(source_audit)}")

    protected = _protected_slice_hashes(
        conn,
        as_of_date=as_of_date,
        source_run_id=str(dict(source["lineage"])["run_id"]),
    )
    plan_body: _PlanBody = {
        "schema": IMPORT_SCHEMA,
        "as_of_date": as_of_date,
        "source_sha256": source["source_sha256"],
        "source_table_evidence": source["table_evidence"],
        "source_audits_sha256": source["audits_sha256"],
        "source_stock_code_count": source["stock_code_count"],
        "source_stock_codes_sha256": source["stock_codes_sha256"],
        "source_lineage": source["lineage"],
        "insert_counts": {table: len(rows) for table, rows in inserts_by_table.items()},
        "insert_rows_sha256": {
            table: _canonical_sha256(rows) for table, rows in inserts_by_table.items()
        },
        "identical_counts": identical_counts,
        "audit_insert_count": len(audit_inserts),
        "audit_insert_sha256": _canonical_sha256(audit_inserts),
        "audit_identical_count": audit_identical,
        "target_scope_before_sha256": target_scope_before,
        "protected_before_sha256": protected,
        "target_missing_request_items_before": sorted(target_coverage.missing_request_items),
    }
    plan_sha256 = _canonical_sha256(plan_body)
    return {
        **plan_body,
        "plan_sha256": plan_sha256,
        "_insert_rows_by_table": inserts_by_table,
        "_insert_audits": audit_inserts,
    }


def _apply_plan(
    conn: duckdb.DuckDBPyConnection,
    *,
    plan: _ImportPlan,
    source: _SourceScope,
    as_of_date: str,
) -> _WriteMetadata:
    inserted_counts: dict[str, int] = {}
    with repository_task_write_scope(__name__):
        conn.execute("begin transaction")
        try:
            for spec in PIT_SPECS:
                rows = list(dict(plan["_insert_rows_by_table"])[spec.table])
                if rows:
                    column_list = ", ".join(spec.columns)
                    placeholders = ", ".join("?" for _ in spec.columns)
                    conn.executemany(
                        f"insert into {spec.table} ({column_list}) values ({placeholders})",
                        [[row[column] for column in spec.columns] for row in rows],
                    )
                inserted_counts[spec.table] = len(rows)

            audits = list(plan["_insert_audits"])
            if audits:
                columns = ", ".join(AUDIT_COLUMNS)
                placeholders = ", ".join("?" for _ in AUDIT_COLUMNS)
                conn.executemany(
                    f"insert into choice_stock_request_audit ({columns}) values ({placeholders})",
                    [[row[column] for column in AUDIT_COLUMNS] for row in audits],
                )
            validation = _post_write_validate(
                conn,
                plan=plan,
                source=source,
                as_of_date=as_of_date,
            )
            conn.execute("commit")
        except Exception:
            conn.execute("rollback")
            raise
    inserted_total = sum(inserted_counts.values()) + len(audits)
    return {
        "inserted_counts": inserted_counts,
        "audit_inserted_count": len(audits),
        "inserted_total": inserted_total,
        "post_write_validation": validation,
    }


def _post_write_validate(
    conn: duckdb.DuckDBPyConnection,
    *,
    plan: _ImportPlan,
    source: _SourceScope,
    as_of_date: str,
) -> dict[str, object]:
    for spec in PIT_SPECS:
        target_rows = _load_scope_rows(conn, spec=spec, as_of_date=as_of_date)
        source_rows = list(dict(source["rows_by_table"])[spec.table])
        if target_rows != source_rows:
            raise RuntimeError(f"post-write PIT rows do not match source for {spec.table}")
    for source_audit in list(source["audits"]):
        exact = _load_exact_audit(conn, source_audit)
        if exact != [source_audit]:
            raise RuntimeError(f"post-write audit does not match source: {_audit_key(source_audit)}")

    protected_after = _protected_slice_hashes(
        conn,
        as_of_date=as_of_date,
        source_run_id=str(dict(source["lineage"])["run_id"]),
    )
    if protected_after != plan["protected_before_sha256"]:
        raise RuntimeError("PIT import changed data outside its approved scope")
    coverage = load_choice_stock_materialization_coverage(
        duckdb_path="",
        as_of_date=as_of_date,
        conn=conn,
    )
    if not coverage.full_coverage:
        raise RuntimeError(f"post-write coverage is incomplete: {coverage.message}")
    return {
        "coverage_status": coverage.status,
        "coverage_full": coverage.full_coverage,
        "missing_request_items": list(coverage.missing_request_items),
        "protected_after_sha256": protected_after,
    }


def _load_scope_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    spec: PitTableSpec,
    as_of_date: str,
) -> list[dict[str, object]]:
    columns = ", ".join(spec.columns)
    raw_rows = conn.execute(
        f"select {columns} from {spec.table} where as_of_date = ? and field_key = ? "
        "order by stock_code, field_key",
        [as_of_date, spec.field_key],
    ).fetchall()
    rows = [dict(zip(spec.columns, row, strict=True)) for row in raw_rows]
    keys = [_row_key(row) for row in rows]
    if len(keys) != len(set(keys)):
        raise RuntimeError(f"duplicate natural keys in {spec.table} for {as_of_date}")
    return rows


def _load_source_audits(
    conn: duckdb.DuckDBPyConnection,
    *,
    as_of_date: str,
) -> list[dict[str, object]]:
    columns = ", ".join(AUDIT_COLUMNS)
    clauses = " or ".join("(input_family = ? and field_key = ?)" for _ in PIT_SPECS)
    params: list[object] = [as_of_date]
    for spec in PIT_SPECS:
        params.extend(spec.item)
    raw_rows = conn.execute(
        f"select {columns} from choice_stock_request_audit where as_of_date = ? "
        f"and ({clauses}) order by input_family, field_key, run_id",
        params,
    ).fetchall()
    return [dict(zip(AUDIT_COLUMNS, row, strict=True)) for row in raw_rows]


def _validate_source_audits(
    audits: list[dict[str, object]],
    *,
    as_of_date: str,
    lineage: tuple[str, str, str, str],
    row_counts: dict[str, int],
    stock_codes: set[str],
) -> None:
    if len(audits) != len(PIT_SPECS):
        raise RuntimeError("source must contain exactly one audit for each approved PIT item")
    by_item = {(str(row["input_family"]), str(row["field_key"])): row for row in audits}
    if set(by_item) != set(PIT_ITEMS):
        raise RuntimeError("source PIT audits do not match the approved three items")
    if len({_audit_key(row) for row in audits}) != len(audits):
        raise RuntimeError("source PIT audits contain duplicate natural keys")

    for spec in PIT_SPECS:
        audit = by_item[spec.item]
        if (
            str(audit["status"]) != "completed"
            or int(cast(str | bytes | bytearray | SupportsInt | SupportsIndex, audit["row_count"] or 0)) != row_counts[spec.table]
            or int(cast(str | bytes | bytearray | SupportsInt | SupportsIndex, audit["error_code"] or 0)) != 0
            or str(audit["error_msg"] or "").strip()
        ):
            raise RuntimeError(f"source audit is not an exact successful Choice request: {spec.item}")
        audit_lineage = (
            str(audit["source_version"] or ""),
            str(audit["vendor_version"] or ""),
            str(audit["rule_version"] or ""),
            str(audit["run_id"] or ""),
        )
        if audit_lineage != lineage:
            raise RuntimeError(f"source audit lineage differs from landed rows: {spec.item}")
        if not _is_choice_historical_pit_audit(
            item=f"{spec.input_family}:{spec.field_key}",
            as_of_date=as_of_date,
            call=audit["call"],
            vendor_indicator=audit["vendor_indicator"],
            request_arguments_json=audit["request_arguments_json"],
            request_options_json=audit["request_options_json"],
            status=str(audit["status"]),
            source_version=audit["source_version"],
            vendor_version=audit["vendor_version"],
        ):
            raise RuntimeError(f"source audit lacks qualified Choice PIT request evidence: {spec.item}")
        if str(audit["call"]).lower() == "css":
            try:
                request_arguments = json.loads(str(audit["request_arguments_json"]))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"source CSS audit arguments are invalid: {spec.item}") from exc
            if not isinstance(request_arguments, list) or not request_arguments:
                raise RuntimeError(f"source CSS audit arguments are invalid: {spec.item}")
            requested_codes = [
                code.strip().upper()
                for code in str(request_arguments[0] or "").split(",")
                if code.strip()
            ]
            if len(requested_codes) != len(set(requested_codes)) or set(requested_codes) != stock_codes:
                raise RuntimeError(f"source CSS request code scope differs from landed rows: {spec.item}")


def _validate_lineage(lineage: tuple[str, str, str, str], *, as_of_date: str) -> None:
    source_version, vendor_version, rule_version, run_id = lineage
    if not SOURCE_VERSION_PATTERN.fullmatch(source_version):
        raise RuntimeError("source PIT source_version is not a Choice materializer generation")
    if not VENDOR_VERSION_PATTERN.fullmatch(vendor_version):
        raise RuntimeError("source PIT vendor_version is not an accepted Choice materializer generation")
    if not rule_version:
        raise RuntimeError("source PIT rule_version is empty")
    if not run_id.startswith(f"choice_stock_materialize:{as_of_date}:"):
        raise RuntimeError("source PIT run_id is not the target-date Choice materializer run")


def _load_exact_audit(
    conn: duckdb.DuckDBPyConnection,
    source_audit: dict[str, object],
) -> list[dict[str, object]]:
    columns = ", ".join(AUDIT_COLUMNS)
    rows = conn.execute(
        f"select {columns} from choice_stock_request_audit "
        "where run_id = ? and as_of_date = ? and input_family = ? and field_key = ?",
        list(_audit_key(source_audit)),
    ).fetchall()
    return [dict(zip(AUDIT_COLUMNS, row, strict=True)) for row in rows]


def _protected_slice_hashes(
    conn: duckdb.DuckDBPyConnection,
    *,
    as_of_date: str,
    source_run_id: str,
) -> dict[str, str]:
    daily_columns = [row[0] for row in conn.execute("describe choice_stock_daily_observation").fetchall()]
    daily_rows = conn.execute(
        f"select {', '.join(daily_columns)} from choice_stock_daily_observation "
        "where trade_date = ? order by stock_code",
        [as_of_date],
    ).fetchall()
    audit_rows = conn.execute(
        f"select {', '.join(AUDIT_COLUMNS)} from choice_stock_request_audit "
        "where as_of_date = ? and run_id <> ? order by run_id, input_family, field_key",
        [as_of_date, source_run_id],
    ).fetchall()
    return {
        "daily_observation": _canonical_sha256(daily_rows),
        "preexisting_request_audits": _canonical_sha256(audit_rows),
    }


def _assert_required_schema(conn: duckdb.DuckDBPyConnection) -> None:
    required = {spec.table: set(spec.columns) for spec in PIT_SPECS}
    required["choice_stock_request_audit"] = set(AUDIT_COLUMNS)
    required["choice_stock_daily_observation"] = {"trade_date", "stock_code"}
    for table, columns in required.items():
        try:
            actual = {str(row[0]) for row in conn.execute(f"describe {table}").fetchall()}
        except duckdb.Error as exc:
            raise RuntimeError(f"required table is missing: {table}") from exc
        missing = columns - actual
        if missing:
            raise RuntimeError(f"required columns are missing from {table}: {sorted(missing)}")


def _build_result(
    *,
    status: str,
    target_path: Path,
    source_path: Path,
    as_of_date: str,
    plan: _ImportPlan,
    source: _SourceScope,
) -> dict[str, object]:
    return {
        "schema": IMPORT_SCHEMA,
        "status": status,
        "duckdb_path": str(target_path),
        "source_duckdb_path": str(source_path),
        "as_of_date": as_of_date,
        "duckdb_written": status == "completed"
        and (
            sum(int(value) for value in dict(plan["insert_counts"]).values())
            + int(plan["audit_insert_count"])
            > 0
        ),
        "production_duckdb_written": status == "completed"
        and _is_production_target(target_path)
        and (
            sum(int(value) for value in dict(plan["insert_counts"]).values())
            + int(plan["audit_insert_count"])
            > 0
        ),
        "plan_sha256": plan["plan_sha256"],
        "source_sha256": source["source_sha256"],
        "source_table_evidence": source["table_evidence"],
        "source_audits_sha256": source["audits_sha256"],
        "source_stock_code_count": source["stock_code_count"],
        "source_stock_codes_sha256": source["stock_codes_sha256"],
        "source_lineage": source["lineage"],
        "insert_counts": plan["insert_counts"],
        "identical_counts": plan["identical_counts"],
        "audit_insert_count": plan["audit_insert_count"],
        "audit_identical_count": plan["audit_identical_count"],
        "target_missing_request_items_before": plan["target_missing_request_items_before"],
        "protected_before_sha256": plan["protected_before_sha256"],
        "write_scope": {
            "tables": [spec.table for spec in PIT_SPECS],
            "field_keys": [spec.field_key for spec in PIT_SPECS],
            "request_audit": "exact source run and three PIT items only",
            "choice_stock_daily_observation": "no_write",
            "choice_stock_materialize_run": "no_write",
        },
    }


def _verify_byte_identical_backup(
    target_path: Path,
    *,
    target_backup_path: str | Path | None,
    source_path: Path | None = None,
) -> dict[str, object]:
    if target_backup_path is None:
        raise ValueError("target_backup_path is required when apply_changes is true")
    backup_path = Path(target_backup_path).resolve(strict=True)
    if (
        backup_path == target_path
        or backup_path.samefile(target_path)
        or (source_path is not None and backup_path.samefile(source_path))
    ):
        raise ValueError("target backup must be a distinct file")
    target_size = target_path.stat().st_size
    backup_size = backup_path.stat().st_size
    target_sha256 = _file_sha256(target_path)
    backup_sha256 = _file_sha256(backup_path)
    if target_size != backup_size or target_sha256 != backup_sha256:
        raise RuntimeError("target backup is not byte-identical to the current target DuckDB")
    return {
        "target_size_bytes_before": target_size,
        "target_sha256_before": target_sha256,
        "backup_path": str(backup_path),
        "backup_size_bytes": backup_size,
        "backup_sha256": backup_sha256,
    }


def _verify_target_unchanged(target_path: Path, *, expected_sha256: str) -> None:
    if _file_sha256(target_path) != expected_sha256:
        raise RuntimeError("target DuckDB changed after backup verification")


def _normalize_date(value: str | date) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(str(value or "").strip()[:10]).isoformat()


def _normalize_sha256(value: object, *, field_name: str) -> str:
    normalized = str(value or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise ValueError(f"{field_name} must be a 64-character lowercase SHA256")
    return normalized


def _row_key(row: dict[str, object]) -> tuple[str, str, str]:
    return (str(row["as_of_date"]), str(row["stock_code"]), str(row["field_key"]))


def _audit_key(row: dict[str, object]) -> tuple[str, str, str, str]:
    return (
        str(row["run_id"]),
        str(row["as_of_date"]),
        str(row["input_family"]),
        str(row["field_key"]),
    )


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_production_target(path: Path) -> bool:
    return path == (Path(__file__).resolve().parents[3] / "data" / "moss.duckdb").resolve()


def _timing_fields(started_at: datetime) -> dict[str, str]:
    return {
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
    }


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    os.replace(temp, path)
