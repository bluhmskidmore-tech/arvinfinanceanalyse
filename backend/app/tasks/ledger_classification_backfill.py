from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
from backend.app.governance.ledger_classification import LEDGER_CLASSIFICATION_RULE_VERSION
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.repositories.ledger_import_repo import (
    LEDGER_IMPORT_LOCK,
    SNAPSHOT_COLUMNS,
    LedgerImportRepository,
    classification_immutable_evidence,
)
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.services.ledger_import_service import SUPPORTED_SUFFIXES, parse_ledger_file

ALLOWED_LEGACY_RULE_VERSIONS = frozenset({"position_key_contract_v1"})
TASK_MODULE = "backend.app.tasks.ledger_classification_backfill"


def file_fingerprint(path: Path | str) -> dict[str, Any]:
    resolved = Path(path).resolve()
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = resolved.stat()
    return {"sha256": digest.hexdigest(), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _values_equal(stored: object, replayed: object) -> bool:
    if isinstance(stored, Decimal) or isinstance(replayed, Decimal):
        if stored is None or replayed is None:
            return stored is replayed
        return Decimal(str(stored)) == Decimal(str(replayed))
    return _json_value(stored) == _json_value(replayed)


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_value)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _source_index(source_dir: Path) -> dict[str, list[Path]]:
    if not source_dir.is_dir():
        raise ValueError(f"source directory does not exist: {source_dir}")
    index: dict[str, list[Path]] = {}
    for path in sorted(source_dir.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        digest = file_fingerprint(path)["sha256"]
        index.setdefault(f"sha256:{digest}", []).append(path)
    return index


def _fetch_rows(conn: duckdb.DuckDBPyConnection, query: str, params: list[object]) -> list[tuple[object, ...]]:
    return list(conn.execute(query, params).fetchall())


def _immutable_evidence(conn: duckdb.DuckDBPyConnection, batch_ids: list[int]) -> dict[str, Any]:
    return classification_immutable_evidence(conn, batch_ids)

def build_backfill_plan(
    db_path: Path | str,
    batch_ids: list[int],
    source_dir: Path | str,
) -> dict[str, Any]:
    ordered_ids = sorted(int(value) for value in batch_ids)
    if not ordered_ids:
        raise ValueError("At least one explicit batch id is required.")
    if len(set(ordered_ids)) != len(ordered_ids):
        raise ValueError("Duplicate batch ids are not allowed.")
    source_root = Path(source_dir).resolve()
    sources = _source_index(source_root)
    target = Path(db_path).resolve()
    if not target.is_file():
        raise ValueError(f"DuckDB target does not exist: {target}")
    preimage = file_fingerprint(target)
    conn = duckdb.connect(str(target), read_only=True)
    try:
        placeholders = ", ".join("?" for _ in ordered_ids)
        batches = _fetch_rows(
            conn,
            f"select batch_id, file_name, file_hash, as_of_date, status, row_count, error_count, source_version, rule_version from ledger_import_batch where batch_id in ({placeholders}) order by batch_id",
            list(ordered_ids),
        )
        if [int(row[0]) for row in batches] != ordered_ids:
            found = {int(row[0]) for row in batches}
            raise ValueError(f"Missing batch ids: {sorted(set(ordered_ids) - found)}")
        batch_rule_states: set[str] = set()
        details: list[dict[str, Any]] = []
        total_direction = Counter[str]()
        total_transitions = Counter[str]()
        total_rows = 0
        planned_updates = {"batches": 0, "raw_rows": 0, "snapshot_rows": 0}
        for row in batches:
            batch_id, file_name, file_hash, as_of_date, status, row_count, error_count, source_version, rule_version = row
            batch_id = int(batch_id)
            row_count = int(row_count)
            rule_version = str(rule_version or "")
            if str(status) != "success" or int(error_count) != 0:
                raise ValueError(f"Batch {batch_id} is not an error-free successful import.")
            if rule_version == LEDGER_CLASSIFICATION_RULE_VERSION:
                batch_rule_states.add("current")
            elif rule_version in ALLOWED_LEGACY_RULE_VERSIONS:
                batch_rule_states.add("legacy")
            else:
                raise ValueError(f"Batch {batch_id} has disallowed rule version {rule_version!r}.")
            expected_source = f"sv_ledger_{str(file_hash).removeprefix('sha256:')[:12]}"
            if str(source_version) != expected_source:
                raise ValueError(f"Batch {batch_id} source version does not match its file hash.")
            matches = sources.get(str(file_hash), [])
            if len(matches) != 1:
                raise ValueError(f"Batch {batch_id} requires exactly one source hash match; found {len(matches)}.")
            parsed = parse_ledger_file(file_name=matches[0].name, content=matches[0].read_bytes())
            if parsed.file_hash != str(file_hash) or parsed.source_version != str(source_version):
                raise ValueError(f"Batch {batch_id} source replay hash/version mismatch.")
            if parsed.as_of_date != str(as_of_date) or len(parsed.rows) != row_count:
                raise ValueError(f"Batch {batch_id} source replay date/row count mismatch.")
            raw_rows = _fetch_rows(
                conn,
                "select row_no, raw_json, source_version, rule_version from ledger_raw_row where batch_id = ? order by row_no",
                [batch_id],
            )
            snapshot_columns = tuple(column for column in SNAPSHOT_COLUMNS if column != "batch_id")
            snapshots = _fetch_rows(
                conn,
                f"select {', '.join(snapshot_columns)} from position_snapshot where batch_id = ? order by row_no",
                [batch_id],
            )
            if len(raw_rows) != row_count or len(snapshots) != row_count:
                raise ValueError(f"Batch {batch_id} three-table row counts do not tie.")
            parsed_by_row = {int(item["row_no"]): item for item in parsed.rows}
            raw_by_row = {int(item[0]): item for item in raw_rows}
            snapshot_by_row = {int(item[0]): item for item in snapshots}
            expected_keys = set(range(1, row_count + 1))
            if set(parsed_by_row) != expected_keys or set(raw_by_row) != expected_keys or set(snapshot_by_row) != expected_keys:
                raise ValueError(f"Batch {batch_id} (batch,row) key sets do not tie.")
            directions = Counter[str]()
            transitions = Counter[str]()
            for row_no in sorted(expected_keys):
                parsed_row = parsed_by_row[row_no]
                raw_row = raw_by_row[row_no]
                snapshot_row = snapshot_by_row[row_no]
                if str(raw_row[1]) != str(parsed_row["raw_json"]):
                    raise ValueError(f"Batch {batch_id} row {row_no} raw replay mismatch.")
                if str(raw_row[2]) != str(source_version) or str(raw_row[3]) != rule_version:
                    raise ValueError(f"Batch {batch_id} row {row_no} raw lineage mismatch.")
                stored = dict(zip(snapshot_columns, snapshot_row, strict=True))
                for column in snapshot_columns:
                    if column in {"rule_version", "direction"}:
                        continue
                    if not _values_equal(stored[column], parsed_row.get(column)):
                        raise ValueError(f"Batch {batch_id} row {row_no} replay mismatch in {column}.")
                if str(stored["rule_version"]) != rule_version:
                    raise ValueError(f"Batch {batch_id} row {row_no} snapshot rule lineage mismatch.")
                replay_direction = str(parsed_row["direction"])
                stored_direction = str(stored["direction"])
                if replay_direction == "UNCLASSIFIED":
                    raise ValueError(f"Batch {batch_id} row {row_no} has unknown or conflicting classification.")
                transitions[f"{stored_direction}->{replay_direction}"] += 1
                directions[replay_direction] += 1
                if stored_direction != replay_direction:
                    raise ValueError(f"Batch {batch_id} row {row_no} direction would change.")
            duplicate_groups = int(conn.execute(
                "select count(*) from (select position_key from position_snapshot where batch_id = ? group by position_key having count(*) > 1)",
                [batch_id],
            ).fetchone()[0])
            state = "already_current" if rule_version == LEDGER_CLASSIFICATION_RULE_VERSION else "eligible"
            if state == "eligible":
                planned_updates["batches"] += 1
                planned_updates["raw_rows"] += row_count
                planned_updates["snapshot_rows"] += row_count
            total_rows += row_count
            total_direction.update(directions)
            total_transitions.update(transitions)
            details.append({
                "batch_id": batch_id,
                "as_of_date": str(as_of_date),
                "file_hash": str(file_hash),
                "source_file": matches[0].relative_to(source_root).as_posix(),
                "source_fingerprint": file_fingerprint(matches[0]),
                "from_rule_version": rule_version,
                "status": state,
                "counts": {"batch": 1, "raw_rows": len(raw_rows), "snapshot_rows": len(snapshots)},
                "direction_counts": dict(sorted(directions.items())),
                "transition_matrix": dict(sorted(transitions.items())),
                "direction_changes": 0,
                "trace_complete": True,
                "source_replay_complete": True,
                "position_key_duplicate_groups": duplicate_groups,
            })
        if len(batch_rule_states) > 1:
            raise ValueError("Mixed legacy/current selections are blocked; plan homogeneous batches separately.")
        immutable_evidence = _immutable_evidence(conn, ordered_ids)
    finally:
        conn.close()
    plan: dict[str, Any] = {
        "schema_version": "ledger_classification_backfill_plan_v1",
        "target_rule_version": LEDGER_CLASSIFICATION_RULE_VERSION,
        "db_preimage": preimage,
        "batch_ids": ordered_ids,
        "batch_count": len(ordered_ids),
        "row_count": total_rows,
        "direction_counts": dict(sorted(total_direction.items())),
        "transition_matrix": dict(sorted(total_transitions.items())),
        "direction_changes": 0,
        "trace_complete": True,
        "source_replay_complete": True,
        "immutable_evidence_digest": immutable_evidence["digest"],
        "position_snapshot_agg_evidence": immutable_evidence["position_snapshot_agg"],
        "planned_updates": planned_updates,
        "batches": details,
    }
    plan["plan_digest"] = _canonical_digest(plan)
    return plan


def _write_prepared_receipt(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0))
    failure: BaseException | None = None
    try:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written == 0:
                raise OSError(errno.EIO, "Prepared receipt write returned zero bytes.")
            offset += written
        os.fsync(descriptor)
    except BaseException as exc:
        failure = exc
    finally:
        os.close(descriptor)
    if failure is not None:
        failed_payload = {
            "schema_version": "ledger_classification_backfill_receipt_v1",
            "status": "prepared_write_failed",
            "error": "receipt_write_failed",
        }
        try:
            with path.open("wb") as handle:
                handle.write(
                    json.dumps(failed_payload, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
                )
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            pass
        raise failure

def _replace_receipt(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _verify_frozen_sources(plan: dict[str, Any], source_dir: Path) -> None:
    for batch in plan["batches"]:
        source_path = (source_dir / str(batch["source_file"])).resolve()
        try:
            current = file_fingerprint(source_path)
        except OSError as exc:
            raise RuntimeError(f"Source file drifted after planning for batch {batch['batch_id']}.") from exc
        if current != batch["source_fingerprint"]:
            raise RuntimeError(f"Source file drifted after planning for batch {batch['batch_id']}.")
def apply_backfill_plan(
    *,
    db_path: Path | str,
    batch_ids: list[int],
    source_dir: Path | str,
    expected_plan_digest: str,
    target_backup_path: Path | str,
    receipt_path: Path | str,
) -> dict[str, Any]:
    if not expected_plan_digest:
        raise ValueError("An expected plan digest is required for apply.")
    if not batch_ids:
        raise ValueError("Explicit batch ids are required for apply.")
    target = Path(db_path).resolve()
    backup = Path(target_backup_path).resolve()
    receipt = Path(receipt_path).resolve()
    if target == backup:
        raise ValueError("Backup path must not be the target database.")
    if not backup.is_file():
        raise ValueError("Target backup must already exist.")
    if os.path.samefile(target, backup):
        raise ValueError("Backup must not be the target database or a hard link to it.")
    if receipt.exists():
        raise ValueError("Receipt path must not already exist.")
    writer_lock = resolve_duckdb_writer_lock(target)
    with acquire_lock(writer_lock, base_dir=target.parent, timeout_seconds=30):
        with acquire_lock(LEDGER_IMPORT_LOCK, base_dir=target.parent, timeout_seconds=30):
            plan = build_backfill_plan(target, batch_ids, source_dir)
            if plan["plan_digest"] != expected_plan_digest:
                raise RuntimeError("Expected plan digest does not match the locked re-plan.")
            current = file_fingerprint(target)
            if current != plan["db_preimage"]:
                raise RuntimeError("Database preimage drifted during apply planning.")
            backup_fingerprint = file_fingerprint(backup)
            if backup_fingerprint["sha256"] != current["sha256"] or backup_fingerprint["size"] != current["size"]:
                raise ValueError("Backup hash and size must match the target preimage.")
            prepared = {
                "schema_version": "ledger_classification_backfill_receipt_v1",
                "status": "prepared",
                "plan_digest": plan["plan_digest"],
                "target_rule_version": plan["target_rule_version"],
                "batch_ids": plan["batch_ids"],
                "db_before": current,
                "backup": backup_fingerprint,
                "planned_updates": plan["planned_updates"],
                "immutable_evidence_digest": plan["immutable_evidence_digest"],
                "position_snapshot_agg_evidence": plan["position_snapshot_agg_evidence"],
                "rollback_instruction": "Stop writers and restore the verified backup manually; no automatic rollback is provided.",
            }
            _write_prepared_receipt(receipt, prepared)
            _verify_frozen_sources(plan, Path(source_dir).resolve())
            from_rules = {int(item["batch_id"]): str(item["from_rule_version"]) for item in plan["batches"]}
            with repository_task_write_scope(TASK_MODULE):
                applied = LedgerImportRepository(str(target)).attest_classification_rule_versions(
                    batch_ids=list(plan["batch_ids"]),
                    from_rule_versions=from_rules,
                    target_rule_version=LEDGER_CLASSIFICATION_RULE_VERSION,
                    expected_immutable_evidence_digest=plan["immutable_evidence_digest"],
                )
            after = file_fingerprint(target)
            completed = {
                **prepared,
                "status": "completed",
                "db_after": after,
                "applied_updates": applied,
                "immutable_fields_unchanged": True,
                "position_snapshot_agg_unchanged": applied["position_snapshot_agg_unchanged"],
                "direction_unchanged": True,
            }
            _replace_receipt(receipt, completed)
            return completed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Attest replay-proven Ledger classification rule lineage.")
    parser.add_argument("--db-path", default="data/moss.duckdb")
    parser.add_argument("--batch-id", action="append", type=int, required=True)
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-plan-digest")
    parser.add_argument("--target-backup-path")
    parser.add_argument("--receipt-path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.apply:
        plan = build_backfill_plan(args.db_path, args.batch_id, args.source_dir)
        print(json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    if not args.target_backup_path or not args.receipt_path:
        raise ValueError("Apply requires target backup and receipt paths.")
    receipt = apply_backfill_plan(
        db_path=args.db_path,
        batch_ids=args.batch_id,
        source_dir=args.source_dir,
        expected_plan_digest=str(args.expected_plan_digest or ""),
        target_backup_path=args.target_backup_path,
        receipt_path=args.receipt_path,
    )
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
