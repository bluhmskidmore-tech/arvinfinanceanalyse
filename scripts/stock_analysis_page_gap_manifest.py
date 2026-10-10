#!/usr/bin/env python3
"""Persist one validated, read-only /stock-analysis page-gap manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.tasks import stock_analysis_page_gap_manifest as manifest_task  # noqa: E402

EXIT_SUCCESS = 0
EXIT_BLOCKED = 2
EXIT_RUNTIME_ERROR = 3
SUCCESS_STATUSES = frozenset({"ready", "gaps_found"})

_SAFE_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,180}$")


class _CreatedOutputIdentity(NamedTuple):
    device: int
    inode: int
    owner_path: Path


def run_stock_analysis_page_gap_manifest_cli(
    *,
    duckdb_path: str | Path,
    trusted_evidence_root: str | Path,
    output_file: str | Path,
    evaluation_as_of_date: str,
    created_at: str,
) -> dict[str, Any]:
    """Build and exclusively persist one page-gap manifest without DB writes."""

    target_db: Path | None = None
    trusted_root: Path | None = None
    target_output: Path | None = None
    database_sha256_before: str | None = None
    database_sha256_after: str | None = None
    created_output_identity: _CreatedOutputIdentity | None = None

    try:
        target_db = _normalize_existing_file(
            duckdb_path,
            field_name="duckdb_path",
        )
        trusted_root = _normalize_existing_directory(
            trusted_evidence_root,
            field_name="trusted_evidence_root",
        )
        target_output = _new_output_path(
            trusted_root=trusted_root,
            output_file=output_file,
        )
        database_sha256_before = _file_sha256(target_db)

        manifest = _mapping(
            manifest_task.build_stock_analysis_page_gap_manifest(
                duckdb_path=target_db,
                evaluation_as_of_date=evaluation_as_of_date,
                created_at=created_at,
            ),
            field_name="manifest",
        )
        manifest_valid, validation_errors = (
            manifest_task.validate_stock_analysis_page_gap_manifest(manifest)
        )
        database_sha256_after = _file_sha256(target_db)
        if database_sha256_after != database_sha256_before:
            return _result_payload(
                status="blocked",
                blockers=["duckdb_hash_changed_during_manifest_build"],
                output_file=None,
                duckdb_sha256_before=database_sha256_before,
                duckdb_sha256_after=database_sha256_after,
                manifest=manifest,
            )

        if not manifest_valid:
            return _result_payload(
                status="blocked",
                blockers=[
                    "page_gap_manifest_validation_failed",
                    *_safe_validation_error_codes(validation_errors),
                ],
                output_file=None,
                duckdb_sha256_before=database_sha256_before,
                duckdb_sha256_after=database_sha256_after,
                manifest=manifest,
            )

        manifest_status = str(manifest.get("status") or "").strip()
        if manifest_status == "blocked":
            return _result_payload(
                status="blocked",
                blockers=(
                    _safe_blockers(manifest.get("blockers"))
                    or ["page_gap_manifest_blocked"]
                ),
                output_file=None,
                duckdb_sha256_before=database_sha256_before,
                duckdb_sha256_after=database_sha256_after,
                manifest=manifest,
            )
        if manifest_status not in SUCCESS_STATUSES:
            return _result_payload(
                status="blocked",
                blockers=["page_gap_manifest_unknown_status"],
                output_file=None,
                duckdb_sha256_before=database_sha256_before,
                duckdb_sha256_after=database_sha256_after,
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
                "persisted page-gap manifest does not match generated manifest"
            )

        database_sha256_after = _file_sha256(target_db)
        if database_sha256_after != database_sha256_before:
            _remove_output_file_if_same(
                trusted_root=trusted_root,
                output_file=target_output,
                created_identity=created_output_identity,
            )
            return _result_payload(
                status="blocked",
                blockers=["duckdb_hash_changed_during_manifest_persistence"],
                output_file=None,
                duckdb_sha256_before=database_sha256_before,
                duckdb_sha256_after=database_sha256_after,
                manifest=manifest,
            )

        return _result_payload(
            status=manifest_status,
            blockers=_safe_blockers(manifest.get("blockers")),
            output_file=target_output,
            duckdb_sha256_before=database_sha256_before,
            duckdb_sha256_after=database_sha256_after,
            manifest=manifest,
        )
    except CliBlockedError as exc:
        database_sha256_after = _safe_file_sha256(target_db)
        return _result_payload(
            status="blocked",
            blockers=[str(exc)],
            output_file=None,
            duckdb_sha256_before=database_sha256_before,
            duckdb_sha256_after=database_sha256_after,
            manifest=None,
        )
    except CliUsageError as exc:
        database_sha256_after = _safe_file_sha256(target_db)
        return _result_payload(
            status="error",
            blockers=[f"page_gap_manifest_cli_failed_{type(exc).__name__}"],
            output_file=None,
            duckdb_sha256_before=database_sha256_before,
            duckdb_sha256_after=database_sha256_after,
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
        database_sha256_after = _safe_file_sha256(target_db)
        database_drifted = bool(
            database_sha256_before
            and database_sha256_after
            and database_sha256_before != database_sha256_after
        )
        return _result_payload(
            status="blocked" if database_drifted else "error",
            blockers=(
                ["duckdb_hash_changed_during_page_gap_manifest_cli"]
                if database_drifted
                else [f"page_gap_manifest_cli_failed_{type(exc).__name__}"]
            ),
            output_file=None,
            duckdb_sha256_before=database_sha256_before,
            duckdb_sha256_after=database_sha256_after,
            manifest=None,
        )
    finally:
        if created_output_identity is not None:
            try:
                _remove_output_if_same_file(
                    output_file=created_output_identity.owner_path,
                    created_identity=created_output_identity,
                )
            except OSError as cleanup_error:
                logging.getLogger(__name__).warning(
                    "Artifact ownership cleanup failed (%s)",
                    type(cleanup_error).__name__,
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build one observational /stock-analysis adjustment-factor gap "
            "manifest. This command never fetches vendors, writes DuckDB, or "
            "materializes execution history."
        )
    )
    parser.add_argument("--duckdb-path", required=True)
    parser.add_argument("--trusted-evidence-root", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--evaluation-as-of-date", required=True)
    parser.add_argument("--created-at", required=True)
    args = parser.parse_args(argv)

    result = run_stock_analysis_page_gap_manifest_cli(
        duckdb_path=args.duckdb_path,
        trusted_evidence_root=args.trusted_evidence_root,
        output_file=args.output_file,
        evaluation_as_of_date=args.evaluation_as_of_date,
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    if result.get("status") in SUCCESS_STATUSES:
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


def _normalize_existing_file(
    path_value: str | Path,
    *,
    field_name: str,
) -> Path:
    path = _absolute_without_resolve(path_value)
    _assert_no_symlink_or_junction(path, field_name=field_name)
    if not path.is_file():
        raise CliUsageError(f"{field_name} must be an existing file")
    return path.resolve(strict=True)


def _normalize_existing_directory(
    path_value: str | Path,
    *,
    field_name: str,
) -> Path:
    path = _absolute_without_resolve(path_value)
    _assert_no_symlink_or_junction(path, field_name=field_name)
    if not path.is_dir():
        raise CliUsageError(f"{field_name} must be an existing directory")
    return path.resolve(strict=True)


def _new_output_path(*, trusted_root: Path, output_file: str | Path) -> Path:
    root = _absolute_without_resolve(trusted_root)
    raw_output = Path(output_file)
    candidate = _absolute_without_resolve(
        raw_output if raw_output.is_absolute() else root / raw_output
    )
    _assert_within_trusted_root(
        trusted_root=root,
        output_file=candidate,
    )
    if candidate.suffix.lower() != ".json":
        raise CliBlockedError("output_file_must_use_json_extension")
    if os.path.lexists(candidate):
        raise CliBlockedError("output_file_must_be_new")
    if not candidate.parent.is_dir():
        raise CliBlockedError("output_file_parent_must_exist")
    return candidate


def _assert_within_trusted_root(*, trusted_root: Path, output_file: Path) -> None:
    root = _absolute_without_resolve(trusted_root)
    candidate = _absolute_without_resolve(output_file)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise CliBlockedError("output_file_outside_trusted_root") from exc

    _assert_no_symlink_or_junction(
        root,
        field_name="trusted_evidence_root",
    )
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
    *,
    trusted_root: Path,
    output_file: Path,
    payload: Mapping[str, Any],
) -> _CreatedOutputIdentity:
    _assert_within_trusted_root(
        trusted_root=trusted_root,
        output_file=output_file,
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
    created_identity: _CreatedOutputIdentity | None = None
    published = False
    try:
        # The private hard link pins this inode after close, so replacing the
        # public path cannot make cleanup mistake a recycled inode for ours.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", delete=False,
            dir=output_file.parent, prefix=f".{output_file.name}.owner-",
        ) as handle:
            created_stat = os.fstat(handle.fileno())
            created_identity = _CreatedOutputIdentity(
                created_stat.st_dev, created_stat.st_ino, Path(handle.name)
            )
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        # link() publishes complete content atomically and never overwrites.
        os.link(created_identity.owner_path, output_file, follow_symlinks=False)
        published = True
        _assert_within_trusted_root(
            trusted_root=trusted_root,
            output_file=output_file,
        )
    except Exception:
        if created_identity is not None:
            try:
                if published:
                    _remove_output_if_same_file(
                        output_file=output_file, created_identity=created_identity
                    )
            finally:
                _remove_output_if_same_file(
                    output_file=created_identity.owner_path,
                    created_identity=created_identity,
                )
        raise
    if created_identity is None:
        raise CliRuntimeError("exclusive output creation identity is unavailable")
    return created_identity


def _remove_output_if_same_file(
    *,
    output_file: Path,
    created_identity: _CreatedOutputIdentity | None,
) -> bool:
    """Remove only the exact file created by this run, never a replacement."""

    if created_identity is None:
        return False
    try:
        owner_stat = created_identity.owner_path.stat(follow_symlinks=False)
        current_stat = output_file.stat(follow_symlinks=False)
    except (FileNotFoundError, OSError):
        return False
    if output_file.is_symlink():
        return False
    expected = (created_identity.device, created_identity.inode)
    if (owner_stat.st_dev, owner_stat.st_ino) != expected:
        return False
    if (current_stat.st_dev, current_stat.st_ino) != expected:
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
    created_identity: _CreatedOutputIdentity,
) -> bool:
    _assert_within_trusted_root(
        trusted_root=trusted_root,
        output_file=output_file,
    )
    return _remove_output_if_same_file(
        output_file=output_file,
        created_identity=created_identity,
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CliRuntimeError(
            "persisted page-gap manifest must be readable UTF-8 JSON"
        ) from exc
    return _mapping(payload, field_name="persisted manifest")


def _result_payload(
    *,
    status: str,
    blockers: Sequence[object],
    output_file: Path | None,
    duckdb_sha256_before: str | None,
    duckdb_sha256_after: str | None,
    manifest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    manifest_payload = dict(manifest or {})
    return {
        "status": status,
        "blockers": _safe_blockers(blockers),
        "output_file": str(output_file) if output_file is not None else None,
        "manifest_file_sha256": (
            _safe_file_sha256(output_file) if output_file is not None else None
        ),
        "canonical_manifest_sha256": manifest_payload.get("canonical_manifest_sha256"),
        "duckdb_sha256_before": duckdb_sha256_before,
        "duckdb_sha256_after": duckdb_sha256_after,
        "database_unchanged": bool(
            duckdb_sha256_before
            and duckdb_sha256_after
            and duckdb_sha256_before == duckdb_sha256_after
        ),
        "summary": _compact_summary(manifest_payload.get("summary")),
    }


def _compact_summary(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    result = {
        str(key): item
        for key, item in value.items()
        if isinstance(item, (str, int, float, bool)) or item is None
    }
    horizon_counts = value.get("horizon_counts")
    if isinstance(horizon_counts, Sequence) and not isinstance(
        horizon_counts,
        (str, bytes, bytearray),
    ):
        safe_horizons: list[dict[str, Any]] = []
        for item in horizon_counts:
            if not isinstance(item, Mapping):
                continue
            label = str(item.get("value") or "").strip()
            count = item.get("count")
            if label and isinstance(count, int) and not isinstance(count, bool):
                safe_horizons.append({"value": label, "count": count})
        result["horizon_counts"] = safe_horizons
    return result


def _safe_validation_error_codes(value: object) -> list[str]:
    if isinstance(value, str):
        items: Sequence[object] = [value]
    elif isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        items = value
    else:
        items = []
    result: list[str] = []
    for index, item in enumerate(items, start=1):
        text = str(item).strip()
        code = (
            text
            if _SAFE_CODE_PATTERN.fullmatch(text)
            else f"validation_error_{index}_detail_redacted"
        )
        if code not in result:
            result.append(code)
    return result


def _safe_blockers(value: object) -> list[str]:
    if isinstance(value, str):
        items: Sequence[object] = [value]
    elif isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        items = value
    else:
        items = []
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        code = text if _SAFE_CODE_PATTERN.fullmatch(text) else "blocker_detail_redacted"
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
