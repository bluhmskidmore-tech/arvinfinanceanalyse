#!/usr/bin/env python3
"""Persist one validated page-gap exact-factor-cell contract without DB writes."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.tasks import (  # noqa: E402
    stock_analysis_page_gap_factor_manifest as manifest_task,
)

EXIT_SUCCESS = 0
EXIT_BLOCKED = 2
EXIT_RUNTIME_ERROR = 3
SUCCESS_STATUS = "gaps_found"
_SAFE_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,180}$")


def run_stock_analysis_page_gap_factor_manifest_cli(
    *,
    page_manifest_path: str | Path,
    duckdb_path: str | Path,
    trusted_evidence_root: str | Path,
    output_file: str | Path,
    created_at: str,
) -> dict[str, Any]:
    """Build and exclusively persist one exact-cell contract inside a trusted root."""

    source_page: Path | None = None
    target_db: Path | None = None
    trusted_root: Path | None = None
    target_output: Path | None = None
    page_sha256_before: str | None = None
    page_sha256_after: str | None = None
    database_sha256_before: str | None = None
    database_sha256_after: str | None = None
    created_output_identity: tuple[int, int] | None = None

    try:
        trusted_root = _normalize_existing_directory(
            trusted_evidence_root, field_name="trusted_evidence_root"
        )
        source_page = _normalize_existing_trusted_json_file(
            page_manifest_path,
            trusted_root=trusted_root,
            field_name="page_manifest_path",
        )
        target_db = _normalize_existing_file(duckdb_path, field_name="duckdb_path")
        target_output = _new_output_path(
            trusted_root=trusted_root, output_file=output_file
        )
        page_sha256_before = _file_sha256(source_page)
        database_sha256_before = _file_sha256(target_db)

        manifest = _mapping(
            manifest_task.build_stock_analysis_page_gap_factor_manifest(
                page_manifest_path=source_page,
                duckdb_path=target_db,
                created_at=created_at,
            ),
            field_name="manifest",
        )
        manifest_valid, validation_errors = (
            manifest_task.validate_stock_analysis_page_gap_factor_manifest(manifest)
        )
        page_sha256_after = _file_sha256(source_page)
        database_sha256_after = _file_sha256(target_db)

        source_drift_blockers = _source_drift_blockers(
            page_sha256_before=page_sha256_before,
            page_sha256_after=page_sha256_after,
            database_sha256_before=database_sha256_before,
            database_sha256_after=database_sha256_after,
            phase="build",
        )
        if source_drift_blockers:
            return _result_payload(
                status="blocked",
                blockers=source_drift_blockers,
                output_file=None,
                page_sha256_before=page_sha256_before,
                page_sha256_after=page_sha256_after,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_after,
                manifest=manifest,
            )
        if not manifest_valid:
            return _result_payload(
                status="blocked",
                blockers=[
                    "page_gap_factor_manifest_validation_failed",
                    *_safe_validation_error_codes(validation_errors),
                ],
                output_file=None,
                page_sha256_before=page_sha256_before,
                page_sha256_after=page_sha256_after,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_after,
                manifest=manifest,
            )

        manifest_status = str(manifest.get("status") or "").strip()
        if manifest_status == "blocked":
            return _result_payload(
                status="blocked",
                blockers=(
                    _safe_blockers(manifest.get("blockers"))
                    or ["page_gap_factor_manifest_blocked"]
                ),
                output_file=None,
                page_sha256_before=page_sha256_before,
                page_sha256_after=page_sha256_after,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_after,
                manifest=manifest,
            )
        if manifest_status != SUCCESS_STATUS:
            return _result_payload(
                status="blocked",
                blockers=["page_gap_factor_manifest_unknown_status"],
                output_file=None,
                page_sha256_before=page_sha256_before,
                page_sha256_after=page_sha256_after,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_after,
                manifest=manifest,
            )

        created_output_identity = _write_json_exclusive(
            trusted_root=trusted_root,
            output_file=target_output,
            payload=manifest,
        )
        persisted = _load_json_object(target_output)
        if persisted != manifest:
            raise CliRuntimeError(
                "persisted page-gap factor manifest does not match generated manifest"
            )
        persisted_valid, _ = (
            manifest_task.validate_stock_analysis_page_gap_factor_manifest(persisted)
        )
        if not persisted_valid:
            raise CliRuntimeError("persisted page-gap factor manifest is invalid")

        page_sha256_after = _file_sha256(source_page)
        database_sha256_after = _file_sha256(target_db)
        source_drift_blockers = _source_drift_blockers(
            page_sha256_before=page_sha256_before,
            page_sha256_after=page_sha256_after,
            database_sha256_before=database_sha256_before,
            database_sha256_after=database_sha256_after,
            phase="persistence",
        )
        if source_drift_blockers:
            _remove_output_file_if_same(
                trusted_root=trusted_root,
                output_file=target_output,
                created_identity=created_output_identity,
            )
            return _result_payload(
                status="blocked",
                blockers=source_drift_blockers,
                output_file=None,
                page_sha256_before=page_sha256_before,
                page_sha256_after=page_sha256_after,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_after,
                manifest=manifest,
            )

        return _result_payload(
            status=SUCCESS_STATUS,
            blockers=[],
            output_file=target_output,
            page_sha256_before=page_sha256_before,
            page_sha256_after=page_sha256_after,
            database_sha256_before=database_sha256_before,
            database_sha256_after=database_sha256_after,
            manifest=manifest,
        )
    except CliBlockedError as exc:
        page_sha256_after = _safe_file_sha256(source_page)
        database_sha256_after = _safe_file_sha256(target_db)
        return _result_payload(
            status="blocked",
            blockers=[str(exc)],
            output_file=None,
            page_sha256_before=page_sha256_before,
            page_sha256_after=page_sha256_after,
            database_sha256_before=database_sha256_before,
            database_sha256_after=database_sha256_after,
            manifest=None,
        )
    except CliUsageError as exc:
        page_sha256_after = _safe_file_sha256(source_page)
        database_sha256_after = _safe_file_sha256(target_db)
        return _result_payload(
            status="error",
            blockers=[f"page_gap_factor_manifest_cli_failed_{type(exc).__name__}"],
            output_file=None,
            page_sha256_before=page_sha256_before,
            page_sha256_after=page_sha256_after,
            database_sha256_before=database_sha256_before,
            database_sha256_after=database_sha256_after,
            manifest=None,
        )
    except Exception as exc:
        if (
            created_output_identity is not None
            and trusted_root is not None
            and target_output is not None
        ):
            try:
                _remove_output_file_if_same(
                    trusted_root=trusted_root,
                    output_file=target_output,
                    created_identity=created_output_identity,
                )
            except Exception as cleanup_error:
                logging.getLogger(__name__).warning(
                    "Artifact cleanup failed (%s); preserving the original failure",
                    type(cleanup_error).__name__,
                )
        page_sha256_after = _safe_file_sha256(source_page)
        database_sha256_after = _safe_file_sha256(target_db)
        drift_blockers = _source_drift_blockers(
            page_sha256_before=page_sha256_before,
            page_sha256_after=page_sha256_after,
            database_sha256_before=database_sha256_before,
            database_sha256_after=database_sha256_after,
            phase="cli",
        )
        return _result_payload(
            status="blocked" if drift_blockers else "error",
            blockers=(
                drift_blockers
                or [f"page_gap_factor_manifest_cli_failed_{type(exc).__name__}"]
            ),
            output_file=None,
            page_sha256_before=page_sha256_before,
            page_sha256_after=page_sha256_after,
            database_sha256_before=database_sha256_before,
            database_sha256_after=database_sha256_after,
            manifest=None,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Derive and persist one read-only exact-date factor target contract "
            "from a validated /stock-analysis page-gap manifest."
        )
    )
    parser.add_argument("--page-manifest-path", required=True)
    parser.add_argument("--duckdb-path", required=True)
    parser.add_argument("--trusted-evidence-root", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--created-at", required=True)
    args = parser.parse_args(argv)

    result = run_stock_analysis_page_gap_factor_manifest_cli(
        page_manifest_path=args.page_manifest_path,
        duckdb_path=args.duckdb_path,
        trusted_evidence_root=args.trusted_evidence_root,
        output_file=args.output_file,
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    if result.get("status") == SUCCESS_STATUS:
        return EXIT_SUCCESS
    if result.get("status") == "blocked":
        return EXIT_BLOCKED
    return EXIT_RUNTIME_ERROR


class CliUsageError(ValueError):
    """Raised when a required local input is unavailable."""


class CliBlockedError(ValueError):
    """Raised when a path or manifest violates a fail-closed boundary."""


class CliRuntimeError(RuntimeError):
    """Raised when persistence cannot be verified."""


def _normalize_existing_file(path_value: str | Path, *, field_name: str) -> Path:
    path = _absolute_without_resolve(path_value)
    _assert_no_symlink_or_junction(path, field_name=field_name)
    if not path.is_file():
        raise CliUsageError(f"{field_name} must be an existing file")
    return path.resolve(strict=True)


def _normalize_existing_directory(path_value: str | Path, *, field_name: str) -> Path:
    path = _absolute_without_resolve(path_value)
    _assert_no_symlink_or_junction(path, field_name=field_name)
    if not path.is_dir():
        raise CliUsageError(f"{field_name} must be an existing directory")
    return path.resolve(strict=True)


def _normalize_existing_trusted_json_file(
    path_value: str | Path,
    *,
    trusted_root: Path,
    field_name: str,
) -> Path:
    path = _absolute_without_resolve(path_value)
    _assert_no_symlink_or_junction(path, field_name=field_name)
    if path.suffix.lower() != ".json":
        raise CliBlockedError(f"{field_name}_must_use_json_extension")
    if not path.is_file():
        raise CliUsageError(f"{field_name} must be an existing file")
    resolved = path.resolve(strict=True)
    _assert_existing_path_within_trusted_root(
        trusted_root=trusted_root,
        candidate=resolved,
        field_name=field_name,
    )
    return resolved


def _new_output_path(*, trusted_root: Path, output_file: str | Path) -> Path:
    root = _absolute_without_resolve(trusted_root)
    raw_output = Path(output_file)
    candidate = _absolute_without_resolve(
        raw_output if raw_output.is_absolute() else root / raw_output
    )
    _assert_output_within_trusted_root(trusted_root=root, output_file=candidate)
    if candidate.suffix.lower() != ".json":
        raise CliBlockedError("output_file_must_use_json_extension")
    if os.path.lexists(candidate):
        raise CliBlockedError("output_file_must_be_new")
    if not candidate.parent.is_dir():
        raise CliBlockedError("output_file_parent_must_exist")
    return candidate


def _assert_existing_path_within_trusted_root(
    *, trusted_root: Path, candidate: Path, field_name: str
) -> None:
    resolved_root = trusted_root.resolve(strict=True)
    try:
        candidate.resolve(strict=True).relative_to(resolved_root)
    except ValueError as exc:
        raise CliBlockedError(f"{field_name}_outside_trusted_root") from exc


def _assert_output_within_trusted_root(
    *, trusted_root: Path, output_file: Path
) -> None:
    root = _absolute_without_resolve(trusted_root)
    candidate = _absolute_without_resolve(output_file)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise CliBlockedError("output_file_outside_trusted_root") from exc
    _assert_no_symlink_or_junction(root, field_name="trusted_evidence_root")
    _assert_no_symlink_or_junction(candidate, field_name="output_file")
    if candidate.parent.is_dir():
        resolved_root = root.resolve(strict=True)
        resolved_parent = candidate.parent.resolve(strict=True)
        try:
            resolved_parent.relative_to(resolved_root)
        except ValueError as exc:
            raise CliBlockedError(
                "output_file_resolved_parent_outside_trusted_root"
            ) from exc


def _assert_no_symlink_or_junction(path: Path, *, field_name: str) -> None:
    current = Path(path.anchor) if path.is_absolute() else Path(".")
    parts = path.parts[1:] if path.is_absolute() else path.parts
    for part in parts:
        current /= part
        if not os.path.lexists(current):
            continue
        is_junction = getattr(current, "is_junction", lambda: False)()
        if current.is_symlink() or is_junction:
            raise CliBlockedError(
                f"{field_name}_contains_symlink_or_junction_component"
            )


def _write_json_exclusive(
    *, trusted_root: Path, output_file: Path, payload: Mapping[str, Any]
) -> tuple[int, int]:
    _assert_output_within_trusted_root(
        trusted_root=trusted_root, output_file=output_file
    )
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )
    created_identity: tuple[int, int] | None = None
    try:
        with output_file.open("x", encoding="utf-8", newline="\n") as handle:
            created_stat = os.fstat(handle.fileno())
            created_identity = (created_stat.st_dev, created_stat.st_ino)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        _assert_output_within_trusted_root(
            trusted_root=trusted_root, output_file=output_file
        )
    except Exception:
        _remove_output_if_same_file(
            output_file=output_file, created_identity=created_identity
        )
        raise
    if created_identity is None:
        raise CliRuntimeError("exclusive output creation identity is unavailable")
    return created_identity


def _remove_output_if_same_file(
    *, output_file: Path, created_identity: tuple[int, int] | None
) -> bool:
    if created_identity is None:
        return False
    try:
        current_stat = output_file.stat(follow_symlinks=False)
    except (FileNotFoundError, OSError):
        return False
    if output_file.is_symlink():
        return False
    if (current_stat.st_dev, current_stat.st_ino) != created_identity:
        return False
    try:
        output_file.unlink()
    except FileNotFoundError:
        return False
    return True


def _remove_output_file_if_same(
    *,
    trusted_root: Path,
    output_file: Path,
    created_identity: tuple[int, int],
) -> bool:
    _assert_output_within_trusted_root(
        trusted_root=trusted_root, output_file=output_file
    )
    return _remove_output_if_same_file(
        output_file=output_file, created_identity=created_identity
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CliRuntimeError("manifest must be readable UTF-8 JSON") from exc
    return _mapping(payload, field_name="persisted manifest")


def _source_drift_blockers(
    *,
    page_sha256_before: str | None,
    page_sha256_after: str | None,
    database_sha256_before: str | None,
    database_sha256_after: str | None,
    phase: str,
) -> list[str]:
    blockers: list[str] = []
    if (
        page_sha256_before
        and page_sha256_after
        and page_sha256_before != page_sha256_after
    ):
        blockers.append(f"page_manifest_hash_changed_during_{phase}")
    if (
        database_sha256_before
        and database_sha256_after
        and database_sha256_before != database_sha256_after
    ):
        blockers.append(f"duckdb_hash_changed_during_{phase}")
    return blockers


def _result_payload(
    *,
    status: str,
    blockers: Sequence[object],
    output_file: Path | None,
    page_sha256_before: str | None,
    page_sha256_after: str | None,
    database_sha256_before: str | None,
    database_sha256_after: str | None,
    manifest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = dict(manifest or {})
    return {
        "status": status,
        "blockers": _safe_blockers(blockers),
        "output_file": str(output_file) if output_file is not None else None,
        "manifest_file_sha256": (
            _safe_file_sha256(output_file) if output_file is not None else None
        ),
        "canonical_manifest_sha256": payload.get("canonical_manifest_sha256"),
        "page_manifest_file_sha256_before": page_sha256_before,
        "page_manifest_file_sha256_after": page_sha256_after,
        "duckdb_sha256_before": database_sha256_before,
        "duckdb_sha256_after": database_sha256_after,
        "sources_unchanged": bool(
            page_sha256_before
            and page_sha256_after
            and page_sha256_before == page_sha256_after
            and database_sha256_before
            and database_sha256_after
            and database_sha256_before == database_sha256_after
        ),
        "target_cell_count": payload.get("target_cell_count"),
        "requested_unique_date_count": payload.get("requested_unique_date_count"),
        "target_cells_sha256": payload.get("target_cells_sha256"),
        "page_manifest_binding": payload.get("page_manifest_binding"),
    }


def _safe_validation_error_codes(value: object) -> list[str]:
    if isinstance(value, str):
        items: Sequence[object] = [value]
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = value
    else:
        items = []
    result: list[str] = []
    for index, item in enumerate(items, start=1):
        detail = str(item).strip()
        code = (
            detail
            if _SAFE_CODE_PATTERN.fullmatch(detail)
            else f"validation_error_{index}_detail_redacted"
        )
        if code not in result:
            result.append(code)
    return result


def _safe_blockers(value: object) -> list[str]:
    if isinstance(value, str):
        items: Sequence[object] = [value]
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = value
    else:
        items = []
    result: list[str] = []
    for item in items:
        detail = str(item).strip()
        code = (
            detail
            if _SAFE_CODE_PATTERN.fullmatch(detail)
            else "blocker_detail_redacted"
        )
        if code not in result:
            result.append(code)
    return result


def _mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CliRuntimeError(f"{field_name} must be an object")
    return dict(value)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _safe_file_sha256(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    try:
        return _file_sha256(path)
    except OSError:
        return None


def _absolute_without_resolve(path_value: str | Path) -> Path:
    return Path(os.path.normpath(os.path.abspath(os.fspath(path_value))))


if __name__ == "__main__":
    raise SystemExit(main())
