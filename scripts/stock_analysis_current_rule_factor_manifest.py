#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.tasks import stock_analysis_current_rule_factor_manifest as manifest_task  # noqa: E402
from scripts import stock_analysis_current_rule_cohort_bundle as cohort_bundle_cli  # noqa: E402
from scripts.stock_analysis_current_rule_replay_dry_run import (  # noqa: E402
    build_current_rule_replay_dry_run,
)

EXIT_SUCCESS = 0
EXIT_BLOCKED = 2
SUCCESS_STATUSES = frozenset({"ready", "gaps_found"})

_SAFE_BLOCKER_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,160}$")


def run_current_rule_factor_manifest_cli(
    *,
    duckdb_path: str | Path,
    trusted_evidence_root: str | Path,
    approved_calendar_receipt: str | Path,
    source_availability_receipts: list[str | Path],
    version_tuple_file: str | Path,
    choice_stock_catalog_file: str | Path,
    output_file: str | Path,
    evaluation_as_of_date: str,
    max_workers: int,
    created_at: str,
) -> dict[str, Any]:
    """Build and exclusively persist one governed, read-only factor manifest."""

    target_db = Path(duckdb_path).resolve()
    database_sha256_before: str | None = None
    database_sha256_after: str | None = None
    governed_run_id: str | None = None
    trusted_root_path: Path | None = None
    target_output: Path | None = None
    output_created_by_this_run = False

    try:
        target_db = cohort_bundle_cli._require_existing_duckdb_path(duckdb_path)
        database_sha256_before = _file_sha256(target_db)
        inputs = cohort_bundle_cli._load_governed_inputs(
            trusted_evidence_root=trusted_evidence_root,
            approved_calendar_receipt=approved_calendar_receipt,
            source_availability_receipts=source_availability_receipts,
            version_tuple_file=version_tuple_file,
            evaluation_as_of_date=evaluation_as_of_date,
        )
        governed_run_id = str(inputs["governed_run_id"])
        trusted_root_path = Path(inputs["trusted_root"])
        target_output = _new_manifest_output_path(
            trusted_root=trusted_root_path,
            output_file=output_file,
        )

        replay_report = build_current_rule_replay_dry_run(
            duckdb_path=target_db,
            start_date=str(inputs["start_date"]),
            end_date=str(inputs["end_date"]),
            choice_stock_catalog_file=choice_stock_catalog_file,
            max_workers=max(1, int(max_workers)),
        )
        database_sha256_after_replay = _file_sha256(target_db)
        if database_sha256_after_replay != database_sha256_before:
            return _result_payload(
                status="blocked",
                blockers=["duckdb_hash_changed_during_replay"],
                governed_run_id=governed_run_id,
                output_file=None,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_after_replay,
                manifest=None,
            )

        runner_results = _mapping_rows(replay_report.get("date_results"))
        governed_open_dates = _text_rows(
            inputs.get("open_dates"),
            field_name="governed open_dates",
        )
        runner_dates = [
            _required_text(
                row.get("trade_date"),
                field_name=f"runner_results[{index}].trade_date",
            )
            for index, row in enumerate(runner_results)
        ]
        if runner_dates != governed_open_dates:
            return _result_payload(
                status="blocked",
                blockers=["runner_dates_do_not_match_governed_open_dates"],
                governed_run_id=governed_run_id,
                output_file=None,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_after_replay,
                manifest=None,
            )

        calendar_receipt = _mapping(
            inputs.get("calendar_receipt"),
            field_name="calendar_receipt",
        )
        manifest = manifest_task.build_stock_analysis_current_rule_factor_manifest(
            duckdb_path=target_db,
            evaluation_as_of_date=str(inputs["evaluation_as_of_date"]),
            governed_run_id=governed_run_id,
            runner_results=runner_results,
            source_availability_receipts=_mapping_rows(inputs.get("source_receipts")),
            frozen_version_tuple=_mapping(
                inputs.get("version_tuple"),
                field_name="version_tuple",
            ),
            calendar_receipt_sha256=_required_text(
                calendar_receipt.get("canonical_receipt_sha256"),
                field_name="calendar_receipt.canonical_receipt_sha256",
            ),
            replay_plan_digest_version=_required_text(
                replay_report.get("plan_digest_version"),
                field_name="replay.plan_digest_version",
            ),
            replay_plan_digest=_required_text(
                replay_report.get("plan_digest"),
                field_name="replay.plan_digest",
            ),
            created_at=created_at,
        )
        manifest_payload = _mapping(manifest, field_name="manifest")
        manifest_status = _required_text(
            manifest_payload.get("status"),
            field_name="manifest.status",
        )
        manifest_valid, _manifest_validation_errors = (
            manifest_task.validate_stock_analysis_current_rule_factor_manifest(
                manifest_payload
            )
        )
        database_sha256_after_manifest = _file_sha256(target_db)
        if database_sha256_after_manifest != database_sha256_before:
            return _result_payload(
                status="blocked",
                blockers=["duckdb_hash_changed_during_manifest_build"],
                governed_run_id=governed_run_id,
                output_file=None,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_after_manifest,
                manifest=manifest_payload,
            )
        if not manifest_valid:
            return _result_payload(
                status="blocked",
                blockers=["factor_manifest_validation_failed"],
                governed_run_id=governed_run_id,
                output_file=None,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_after_manifest,
                manifest=manifest_payload,
            )
        if manifest_status not in SUCCESS_STATUSES:
            return _result_payload(
                status="blocked" if manifest_status == "blocked" else "error",
                blockers=(
                    _safe_blocker_codes(manifest_payload.get("blockers"))
                    or ["factor_manifest_not_remediation_usable"]
                ),
                governed_run_id=governed_run_id,
                output_file=None,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_after_manifest,
                manifest=manifest_payload,
            )

        _write_json_exclusive(
            trusted_root=trusted_root_path,
            output_file=target_output,
            payload=manifest_payload,
        )
        output_created_by_this_run = True
        persisted = _load_json_object(target_output)
        if persisted != manifest_payload:
            raise FactorManifestCliError(
                "persisted factor manifest does not match the generated manifest"
            )

        database_sha256_after = _file_sha256(target_db)
        if database_sha256_after != database_sha256_before:
            _remove_new_manifest_file(
                trusted_root=trusted_root_path,
                output_file=target_output,
            )
            output_created_by_this_run = False
            return _result_payload(
                status="blocked",
                blockers=["duckdb_hash_changed_during_manifest_persistence"],
                governed_run_id=governed_run_id,
                output_file=None,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_after,
                manifest=manifest_payload,
            )

        return _result_payload(
            status=manifest_status,
            blockers=_safe_blocker_codes(manifest_payload.get("blockers")),
            governed_run_id=governed_run_id,
            output_file=target_output,
            database_sha256_before=database_sha256_before,
            database_sha256_after=database_sha256_after,
            manifest=manifest_payload,
        )
    except Exception as exc:
        if (
            output_created_by_this_run
            and target_output is not None
            and trusted_root_path is not None
        ):
            try:
                _remove_new_manifest_file(
                    trusted_root=trusted_root_path,
                    output_file=target_output,
                )
            except Exception as cleanup_error:
                logging.getLogger(__name__).warning(
                    "Artifact cleanup failed (%s); preserving the original failure",
                    type(cleanup_error).__name__,
                )
        if database_sha256_before is not None and target_db.is_file():
            try:
                database_sha256_after = _file_sha256(target_db)
            except OSError:
                database_sha256_after = None
        database_drifted = bool(
            database_sha256_before
            and database_sha256_after
            and database_sha256_before != database_sha256_after
        )
        return _result_payload(
            status="blocked" if database_drifted else "error",
            blockers=(
                ["duckdb_hash_changed_during_factor_manifest_cli"]
                if database_drifted
                else [f"factor_manifest_cli_failed_{type(exc).__name__}"]
            ),
            governed_run_id=governed_run_id,
            output_file=None,
            database_sha256_before=database_sha256_before,
            database_sha256_after=database_sha256_after,
            manifest=None,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build one governed current-rule adjustment-factor gap manifest in "
            "read-only mode. This command never calls data vendors or writes DuckDB."
        )
    )
    parser.add_argument("--duckdb-path", required=True)
    parser.add_argument("--trusted-evidence-root", required=True)
    parser.add_argument("--approved-calendar-receipt", required=True)
    parser.add_argument(
        "--source-availability-receipt",
        action="append",
        dest="source_availability_receipts",
        required=True,
    )
    parser.add_argument("--version-tuple-file", required=True)
    parser.add_argument("--choice-stock-catalog-file", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--evaluation-as-of-date", required=True)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument(
        "--created-at",
        default=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    args = parser.parse_args(argv)

    result = run_current_rule_factor_manifest_cli(
        duckdb_path=args.duckdb_path,
        trusted_evidence_root=args.trusted_evidence_root,
        approved_calendar_receipt=args.approved_calendar_receipt,
        source_availability_receipts=list(args.source_availability_receipts),
        version_tuple_file=args.version_tuple_file,
        choice_stock_catalog_file=args.choice_stock_catalog_file,
        output_file=args.output_file,
        evaluation_as_of_date=args.evaluation_as_of_date,
        max_workers=max(1, int(args.max_workers)),
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return EXIT_SUCCESS if result.get("status") in SUCCESS_STATUSES else EXIT_BLOCKED


class FactorManifestCliError(ValueError):
    """Raised when the CLI cannot safely persist a factor manifest."""


def _new_manifest_output_path(
    *,
    trusted_root: Path,
    output_file: str | Path,
) -> Path:
    normalized_root = _absolute_without_resolve(trusted_root)
    raw_output = Path(output_file)
    candidate = _absolute_without_resolve(
        raw_output if raw_output.is_absolute() else normalized_root / raw_output
    )
    _assert_output_path_within_trusted_root(
        trusted_root=normalized_root,
        output_file=candidate,
    )
    if candidate.suffix.lower() != ".json":
        raise FactorManifestCliError("output_file must use a .json extension")
    if os.path.lexists(candidate):
        raise FactorManifestCliError(
            "output_file must be new; existing evidence is never overwritten"
        )
    if not candidate.parent.is_dir():
        raise FactorManifestCliError(
            "output_file parent must be an existing directory"
        )
    return candidate


def _assert_output_path_within_trusted_root(
    *,
    trusted_root: Path,
    output_file: Path,
) -> None:
    root = _absolute_without_resolve(trusted_root)
    candidate = _absolute_without_resolve(output_file)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise FactorManifestCliError(
            "output_file must stay within trusted_evidence_root"
        ) from exc
    cohort_bundle_cli.producer_task._assert_no_symlink_in_raw_path(  # type: ignore[attr-defined]
        candidate,
        field_name="output_file",
    )


def _write_json_exclusive(
    *,
    trusted_root: Path,
    output_file: Path,
    payload: Mapping[str, Any],
) -> None:
    _assert_output_path_within_trusted_root(
        trusted_root=trusted_root,
        output_file=output_file,
    )
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    with output_file.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    _assert_output_path_within_trusted_root(
        trusted_root=trusted_root,
        output_file=output_file,
    )


def _remove_new_manifest_file(
    *,
    trusted_root: Path,
    output_file: Path,
) -> None:
    _assert_output_path_within_trusted_root(
        trusted_root=trusted_root,
        output_file=output_file,
    )
    output_file.unlink(missing_ok=True)


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FactorManifestCliError(
            "persisted factor manifest must be readable UTF-8 JSON"
        ) from exc
    return _mapping(payload, field_name="persisted manifest")


def _result_payload(
    *,
    status: str,
    blockers: list[str],
    governed_run_id: str | None,
    output_file: Path | None,
    database_sha256_before: str | None,
    database_sha256_after: str | None,
    manifest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    manifest_payload = dict(manifest or {})
    summary = manifest_payload.get("summary")
    compact_summary = (
        {
            str(key): value
            for key, value in summary.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        }
        if isinstance(summary, Mapping)
        else {}
    )
    payload: dict[str, Any] = {
        "status": status,
        "blockers": _safe_blocker_codes(blockers),
        "governed_run_id": governed_run_id,
        "output_file": str(output_file) if output_file is not None else None,
        "manifest_file_sha256": (
            _file_sha256(output_file)
            if output_file is not None and output_file.is_file()
            else None
        ),
        "canonical_manifest_sha256": manifest_payload.get(
            "canonical_manifest_sha256"
        ),
        "duckdb_sha256_before": database_sha256_before,
        "duckdb_sha256_after": database_sha256_after,
        "database_unchanged": bool(
            database_sha256_before
            and database_sha256_after
            and database_sha256_before == database_sha256_after
        ),
        "summary": compact_summary,
    }
    return payload


def _safe_blocker_codes(value: object) -> list[str]:
    if isinstance(value, str):
        items: Sequence[object] = [value]
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        items = value
    else:
        items = []
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        safe = text if _SAFE_BLOCKER_PATTERN.fullmatch(text) else "blocker_detail_redacted"
        if safe and safe not in result:
            result.append(safe)
    return result


def _mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FactorManifestCliError(f"{field_name} must be an object")
    return dict(value)


def _mapping_rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise FactorManifestCliError("runner/source evidence rows must be an array")
    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise FactorManifestCliError("runner/source evidence rows must contain objects")
        rows.append(dict(item))
    return rows


def _text_rows(value: object, *, field_name: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise FactorManifestCliError(f"{field_name} must be an array")
    return [
        _required_text(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(value)
    ]


def _required_text(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise FactorManifestCliError(f"{field_name} is required")
    return text


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _absolute_without_resolve(path: str | Path) -> Path:
    return Path(os.path.normpath(os.path.abspath(os.fspath(path))))


if __name__ == "__main__":
    raise SystemExit(main())
