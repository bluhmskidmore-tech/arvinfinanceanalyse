#!/usr/bin/env python3
"""Dry-run or execute governed page-gap adjusted-return materialization."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.tasks import (  # noqa: E402
    stock_analysis_page_gap_execution_materialize as materialize_task,
)

EXIT_SUCCESS = 0
EXIT_BLOCKED = 2
EXIT_RUNTIME_ERROR = 3
SUCCESS_STATUSES = frozenset(
    {
        materialize_task.READY_STATUS,
        materialize_task.ALREADY_COMPLETE_STATUS,
        materialize_task.COMPLETED_STATUS,
    }
)
_SAFE_CODE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,180}$")


def run_stock_analysis_page_gap_execution_materialize_cli(
    *,
    duckdb_path: str | Path,
    trusted_evidence_root: str | Path,
    page_manifest_file: str | Path,
    factor_write_receipt_file: str | Path,
    output_file: str | Path,
    executed_at: str,
    allow_write: bool = False,
    approval_reference: str | None = None,
    expected_materialization_approval_scope_sha256: str | None = None,
) -> dict[str, Any]:
    """Run the default read-only plan or the explicitly approved live write."""

    target_db: Path | None = None
    output_path: Path | None = None
    created_identity: tuple[int, int] | None = None
    database_sha256_before: str | None = None
    try:
        target_db = materialize_task._existing_file_no_links(  # noqa: SLF001
            duckdb_path,
            field_name="duckdb_path",
        )
        trusted_root = materialize_task._existing_directory_no_links(  # noqa: SLF001
            trusted_evidence_root,
            field_name="trusted_evidence_root",
        )
        database_sha256_before = _file_sha256(target_db)
        if allow_write:
            if not approval_reference or not approval_reference.strip():
                raise materialize_task.PageGapExecutionMaterializeError(
                    "approval_reference is required with allow_write"
                )
            if not expected_materialization_approval_scope_sha256:
                raise materialize_task.PageGapExecutionMaterializeError(
                    "expected materialization approval scope SHA is required with allow_write"
                )
            # Resolve the expected new path before entering the writer so a
            # post-pending failure can report the reconcile artifact without
            # deleting it.
            output_path = materialize_task._new_json_path_within_root(  # noqa: SLF001
                trusted_root=trusted_root,
                path=output_file,
                field_name="output_file",
            )
            receipt = (
                materialize_task.materialize_stock_analysis_page_gap_execution_history(
                    duckdb_path=target_db,
                    trusted_evidence_root=trusted_root,
                    page_manifest_file=page_manifest_file,
                    factor_write_receipt_file=factor_write_receipt_file,
                    write_receipt_file=output_file,
                    executed_at=executed_at,
                    approval_reference=approval_reference,
                    expected_materialization_approval_scope_sha256=(
                        expected_materialization_approval_scope_sha256
                    ),
                    allow_write=True,
                )
            )
            output_path = materialize_task._existing_json_path_within_root(  # noqa: SLF001
                trusted_root=trusted_root,
                path=output_path,
                field_name="output_file",
            )
            return _result_payload(
                payload=receipt,
                mode="live",
                output_file=output_path,
                database_sha256_before=database_sha256_before,
                database_sha256_after=_file_sha256(target_db),
                blockers=[],
            )

        if (
            approval_reference is not None
            or expected_materialization_approval_scope_sha256 is not None
        ):
            raise materialize_task.PageGapExecutionMaterializeError(
                "approval arguments require allow_write"
            )
        output_path = materialize_task._new_json_path_within_root(  # noqa: SLF001
            trusted_root=trusted_root,
            path=output_file,
            field_name="output_file",
        )
        plan = materialize_task.build_stock_analysis_page_gap_execution_materialization_plan_from_files(
            duckdb_path=target_db,
            trusted_evidence_root=trusted_root,
            page_manifest_file=page_manifest_file,
            factor_write_receipt_file=factor_write_receipt_file,
            created_at=executed_at,
        )
        if _file_sha256(target_db) != database_sha256_before:
            raise CliRuntimeError("DuckDB changed during read-only dry-run")
        created_identity = _write_json_exclusive(output_path, payload=plan)
        if _load_json_object(output_path) != plan:
            raise CliRuntimeError("persisted dry-run plan readback mismatch")
        database_sha256_after = _file_sha256(target_db)
        if database_sha256_after != database_sha256_before:
            _remove_if_same_file(output_path, created_identity=created_identity)
            raise CliRuntimeError("DuckDB changed during dry-run persistence")
        return _result_payload(
            payload=plan,
            mode="dry_run",
            output_file=output_path,
            database_sha256_before=database_sha256_before,
            database_sha256_after=database_sha256_after,
            blockers=[],
        )
    except materialize_task.PageGapExecutionMaterializeError as exc:
        return _result_payload(
            payload=None,
            mode="live" if allow_write else "dry_run",
            output_file=(
                output_path
                if output_path is not None and output_path.is_file()
                else None
            ),
            database_sha256_before=database_sha256_before,
            database_sha256_after=_safe_file_sha256(target_db),
            blockers=[
                _safe_error_code(exc, fallback="materialization_preflight_blocked")
            ],
            status="blocked",
        )
    except Exception as exc:
        if created_identity is not None and output_path is not None:
            _remove_if_same_file(output_path, created_identity=created_identity)
        return _result_payload(
            payload=None,
            mode="live" if allow_write else "dry_run",
            output_file=(
                output_path
                if output_path is not None and output_path.is_file()
                else None
            ),
            database_sha256_before=database_sha256_before,
            database_sha256_after=_safe_file_sha256(target_db),
            blockers=[f"materialization_cli_failed_{type(exc).__name__}"],
            status="error",
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a read-only exact page-gap materialization plan by default. "
            "With --allow-write, require an independent approval scope and update "
            "only the approved missing adjusted-return fields."
        )
    )
    parser.add_argument("--duckdb-path", required=True)
    parser.add_argument("--trusted-evidence-root", required=True)
    parser.add_argument("--page-manifest-file", required=True)
    parser.add_argument("--factor-write-receipt-file", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--executed-at", required=True)
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--approval-reference")
    parser.add_argument("--expected-materialization-approval-scope-sha256")
    args = parser.parse_args(argv)

    result = run_stock_analysis_page_gap_execution_materialize_cli(
        duckdb_path=args.duckdb_path,
        trusted_evidence_root=args.trusted_evidence_root,
        page_manifest_file=args.page_manifest_file,
        factor_write_receipt_file=args.factor_write_receipt_file,
        output_file=args.output_file,
        executed_at=args.executed_at,
        allow_write=args.allow_write,
        approval_reference=args.approval_reference,
        expected_materialization_approval_scope_sha256=(
            args.expected_materialization_approval_scope_sha256
        ),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    if result.get("status") in SUCCESS_STATUSES:
        return EXIT_SUCCESS
    if result.get("status") == "blocked":
        return EXIT_BLOCKED
    return EXIT_RUNTIME_ERROR


class CliRuntimeError(RuntimeError):
    """Raised when local evidence persistence cannot be verified."""


def _result_payload(
    *,
    payload: Mapping[str, Any] | None,
    mode: str,
    output_file: Path | None,
    database_sha256_before: str | None,
    database_sha256_after: str | None,
    blockers: list[str],
    status: str | None = None,
) -> dict[str, Any]:
    body = dict(payload or {})
    summary = body.get("summary")
    verification = body.get("verification")
    return {
        "status": status or body.get("status") or "error",
        "mode": mode,
        "blockers": blockers,
        "output_file": str(output_file) if output_file is not None else None,
        "output_file_sha256": _safe_file_sha256(output_file),
        "canonical_plan_sha256": body.get("canonical_plan_sha256"),
        "canonical_materialization_receipt_sha256": body.get(
            "canonical_materialization_receipt_sha256"
        ),
        "approval_scope_sha256": body.get("approval_scope_sha256"),
        "database_sha256_before": database_sha256_before,
        "database_sha256_after": database_sha256_after,
        "database_unchanged": bool(
            database_sha256_before
            and database_sha256_after
            and database_sha256_before == database_sha256_after
        ),
        "summary": _compact_mapping(summary),
        "verification": _compact_mapping(verification),
    }


def _compact_mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): item
        for key, item in value.items()
        if isinstance(item, (str, int, float, bool)) or item is None
    }


def _safe_error_code(exc: Exception, *, fallback: str) -> str:
    text = str(exc).strip().replace(" ", "_")
    return text if _SAFE_CODE_RE.fullmatch(text) else fallback


def _write_json_exclusive(
    path: Path,
    *,
    payload: Mapping[str, Any],
) -> tuple[int, int]:
    identity: tuple[int, int] | None = None
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            stat = os.fstat(handle.fileno())
            identity = (stat.st_dev, stat.st_ino)
            handle.write(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        _remove_if_same_file(path, created_identity=identity)
        raise
    if identity is None:
        raise CliRuntimeError("exclusive output identity unavailable")
    return identity


def _remove_if_same_file(
    path: Path,
    *,
    created_identity: tuple[int, int] | None,
) -> bool:
    if created_identity is None:
        return False
    try:
        stat = path.stat(follow_symlinks=False)
    except (FileNotFoundError, OSError):
        return False
    if path.is_symlink() or (stat.st_dev, stat.st_ino) != created_identity:
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise CliRuntimeError("output must contain a JSON object")
    return dict(payload)


def _file_sha256(path: Path) -> str:
    return materialize_task._file_sha256(path)  # noqa: SLF001


def _safe_file_sha256(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    try:
        return _file_sha256(path)
    except OSError:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
