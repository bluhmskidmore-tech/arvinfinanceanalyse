from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_REPORT = Path("test_output/security-scans/osv-report.json")
DEFAULT_SCAN_RECEIPT = Path("test_output/security-scans/osv-scan-receipt.json")
DEFAULT_RECORDS = Path("docs/audits/osv-reconciliation-records.json")
DEFAULT_OUTPUT = Path("test_output/security-scans/osv-adjudication.json")
EXACT_FIELDS = ("advisory_id", "ecosystem", "package", "version", "lockfile")
EXPECTED_LOCKFILES = ("backend/uv.lock", "frontend/package-lock.json")
EXPECTED_SCANNER_NAME = "osv-scanner"
EXPECTED_SCANNER_VERSION = "2.3.0"
EXPECTED_SCANNER_SHA256 = (
    "e774e5770c31d60745c067be5f69bf3b46641b6d0e0ed87fd65e569cda35dc50"
)
PLACEHOLDER_IDENTITIES = {"", "<required>", "none", "null", "pending", "tbd", "unknown"}
ALLOWED_DISPOSITIONS = {"upstream_metadata_false_positive_patched"}
REQUIRED_SOURCE_KINDS = {"maintainer_advisory", "maintainer_backport"}
ALLOWED_SOURCE_KINDS = {
    "maintainer_advisory",
    "maintainer_backport",
    "maintainer_release",
    "advisory_database_correction",
}
TRUSTED_MAINTAINER_REPOSITORIES = {
    ("npm", "react-router"): "remix-run/react-router",
}


class GateInputError(ValueError):
    pass


def _resolved_path(path: str | Path, *, root: Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root / candidate


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise GateInputError(f"{label} does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GateInputError(
            f"{label} is not valid UTF-8 JSON: {path}: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise GateInputError(f"{label} must contain a JSON object: {path}")
    return payload


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").removeprefix("./")


def _safe_repo_path(
    value: object, *, root: Path, field: str
) -> tuple[Path | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return None, f"{field} is required"
    normalized = _normalize_path(value.strip())
    relative = Path(normalized)
    if relative.is_absolute() or ".." in relative.parts:
        return None, f"{field} must be a repo-relative path"
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        return None, f"{field} must stay inside the repository"
    return resolved, None


def _repo_relative_path(path: Path, *, root: Path, field: str) -> str:
    resolved_root = root.resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(resolved_root).as_posix()
    except ValueError as error:
        raise GateInputError(f"{field} must stay inside the repository") from error


def _sha256_is_valid(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _parse_timestamp(
    value: object, *, field: str
) -> tuple[datetime | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return None, f"{field} is required"
    normalized = value.strip().replace("Z", "+00:00")
    try:
        timestamp = datetime.fromisoformat(normalized)
    except ValueError:
        return None, f"{field} must be an ISO-8601 timestamp"
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return None, f"{field} must include a timezone"
    return timestamp, None


def _identity_is_filled(value: object) -> bool:
    return (
        isinstance(value, str) and value.strip().lower() not in PLACEHOLDER_IDENTITIES
    )


def _identity_key(value: object) -> str | None:
    return value.strip().casefold() if _identity_is_filled(value) else None


def _validate_source_url(
    *, kind: str, url: object, record: dict[str, Any]
) -> str | None:
    if not isinstance(url, str) or not url.strip():
        return "must be an HTTPS URL"
    try:
        parsed = urlparse(url.strip())
        port = parsed.port
    except ValueError:
        return "must be a valid HTTPS URL"
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        return "must be a canonical github.com HTTPS URL without credentials, port, query, or fragment"

    repository = TRUSTED_MAINTAINER_REPOSITORIES.get(
        (record.get("ecosystem"), record.get("package"))
    )
    if repository is None:
        return "has no trusted maintainer repository configured for this package"
    path = unquote(parsed.path).rstrip("/")
    advisory_id = record.get("advisory_id")

    if kind == "maintainer_advisory":
        expected = f"/{repository}/security/advisories/{advisory_id}"
        if path != expected:
            return f"must be the exact {repository} GitHub security advisory URL"
        return None
    if kind == "maintainer_backport":
        prefix = f"/{repository}/"
        suffix = path.removeprefix(prefix)
        valid_pull = (
            suffix.startswith("pull/") and suffix.removeprefix("pull/").isdigit()
        )
        valid_commit = (
            suffix.startswith("commit/")
            and len(suffix.removeprefix("commit/")) == 40
            and all(
                character in "0123456789abcdef"
                for character in suffix.removeprefix("commit/")
            )
        )
        if not path.startswith(prefix) or not (valid_pull or valid_commit):
            return (
                f"must be a pull or commit URL in the trusted {repository} repository"
            )
        return None
    if kind == "maintainer_release":
        prefix = f"/{repository}/releases/tag/"
        if (
            not path.startswith(prefix)
            or not path.removeprefix(prefix)
            or "/" in path.removeprefix(prefix)
        ):
            return f"must be a release-tag URL in the trusted {repository} repository"
        return None
    if kind == "advisory_database_correction":
        prefix = "/github/advisory-database/"
        suffix = path.removeprefix(prefix)
        valid_pull = (
            suffix.startswith("pull/") and suffix.removeprefix("pull/").isdigit()
        )
        valid_commit = (
            suffix.startswith("commit/")
            and len(suffix.removeprefix("commit/")) == 40
            and all(
                character in "0123456789abcdef"
                for character in suffix.removeprefix("commit/")
            )
        )
        if not path.startswith(prefix) or not (valid_pull or valid_commit):
            return "must be a pull or commit URL in github/advisory-database"
        return None
    return "uses an unsupported evidence kind"


def _exact_string_error(record: dict[str, Any], field: str) -> str | None:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        return f"{field} is required"
    if any(marker in value for marker in ("*", "?", "[", "]")):
        return f"{field} must be exact; wildcards and patterns are forbidden"
    return None


def _extract_findings(raw_report: dict[str, Any]) -> list[dict[str, str]]:
    results = raw_report.get("results")
    if not isinstance(results, list):
        raise GateInputError("raw OSV report must contain a results array")

    findings: list[dict[str, str]] = []
    for result_index, result in enumerate(results):
        if not isinstance(result, dict):
            raise GateInputError(f"raw OSV result {result_index} must be an object")
        source = result.get("source")
        packages = result.get("packages", [])
        if not isinstance(source, dict) or not isinstance(source.get("path"), str):
            raise GateInputError(
                f"raw OSV result {result_index} is missing source.path"
            )
        if not isinstance(packages, list):
            raise GateInputError(
                f"raw OSV result {result_index} packages must be an array"
            )
        source_path = _normalize_path(source["path"])

        for package_index, package_result in enumerate(packages):
            if not isinstance(package_result, dict):
                raise GateInputError(
                    f"raw OSV result {result_index} package {package_index} must be an object"
                )
            package = package_result.get("package")
            vulnerabilities = package_result.get("vulnerabilities", [])
            if not isinstance(package, dict):
                raise GateInputError(
                    f"raw OSV result {result_index} package {package_index} is missing package metadata"
                )
            if not isinstance(vulnerabilities, list):
                raise GateInputError(
                    f"raw OSV result {result_index} package {package_index} vulnerabilities must be an array"
                )
            values = {
                field: package.get(field) for field in ("ecosystem", "name", "version")
            }
            if not all(isinstance(value, str) and value for value in values.values()):
                raise GateInputError(
                    f"raw OSV result {result_index} package {package_index} has incomplete identity"
                )
            for vulnerability_index, vulnerability in enumerate(vulnerabilities):
                if not isinstance(vulnerability, dict) or not isinstance(
                    vulnerability.get("id"), str
                ):
                    raise GateInputError(
                        "raw OSV vulnerability identity is missing at "
                        f"result {result_index}, package {package_index}, vulnerability {vulnerability_index}"
                    )
                findings.append(
                    {
                        "source": source_path,
                        "ecosystem": values["ecosystem"],
                        "package": values["name"],
                        "version": values["version"],
                        "advisory_id": vulnerability["id"],
                    }
                )
    return findings


def _record_key(record: dict[str, Any]) -> tuple[object, ...]:
    return tuple(record.get(field) for field in EXACT_FIELDS)


def _record_matches(record: dict[str, Any], finding: dict[str, str]) -> bool:
    source = _normalize_path(finding["source"])
    lockfile = _normalize_path(str(record.get("lockfile", "")))
    source_matches = source == lockfile or source.endswith(f"/{lockfile}")
    return source_matches and all(
        record.get(field) == finding[field]
        for field in ("advisory_id", "ecosystem", "package", "version")
    )


def _validate_record(record: dict[str, Any], *, root: Path, now: datetime) -> list[str]:
    errors: list[str] = []
    record_id = record.get("record_id")
    if not isinstance(record_id, str) or not record_id.strip():
        errors.append("record_id is required")
    elif any(marker in record_id for marker in ("*", "?", "[", "]")):
        errors.append("record_id must be exact; wildcards and patterns are forbidden")

    for field in EXACT_FIELDS:
        error = _exact_string_error(record, field)
        if error:
            errors.append(error)

    if record.get("status") != "active":
        errors.append("status must be active")
    if record.get("disposition") not in ALLOWED_DISPOSITIONS:
        errors.append("disposition is not an allowed reconciliation disposition")
    if (
        not isinstance(record.get("responsible_owner_type"), str)
        or not record["responsible_owner_type"].strip()
    ):
        errors.append("responsible_owner_type is required")
    if not _identity_is_filled(record.get("owner")):
        errors.append("owner identity is required and must not be a placeholder")
    if not _identity_is_filled(record.get("approver")):
        errors.append("approver identity is required and must not be a placeholder")
    owner_key = _identity_key(record.get("owner"))
    approver_key = _identity_key(record.get("approver"))
    if owner_key is not None and approver_key is not None and owner_key == approver_key:
        errors.append("owner and approver must be different identities")

    approved_at, approved_error = _parse_timestamp(
        record.get("approved_at"), field="approved_at"
    )
    if approved_error:
        errors.append(approved_error)
    elif approved_at and approved_at > now:
        errors.append("approved_at must not be in the future")

    expires_at, expires_error = _parse_timestamp(
        record.get("expires_at"), field="expires_at"
    )
    if expires_error:
        errors.append(expires_error)
    elif expires_at and expires_at <= now:
        errors.append("record is expired")

    lockfile_path, path_error = _safe_repo_path(
        record.get("lockfile"), root=root, field="lockfile"
    )
    if path_error:
        errors.append(path_error)
    elif lockfile_path and not lockfile_path.is_file():
        errors.append("lockfile does not exist")
    elif lockfile_path:
        expected_hash = record.get("lockfile_sha256")
        if not _sha256_is_valid(expected_hash):
            errors.append("lockfile_sha256 must be a 64-character SHA-256 digest")
        elif _sha256(lockfile_path).lower() != expected_hash.lower():
            errors.append("lockfile sha256 mismatch")

    boundary = record.get("boundary_test")
    if not isinstance(boundary, dict):
        errors.append("boundary_test object is required")
    else:
        boundary_path, boundary_path_error = _safe_repo_path(
            boundary.get("path"), root=root, field="boundary_test.path"
        )
        if boundary_path_error:
            errors.append(boundary_path_error)
        elif boundary_path and not boundary_path.is_file():
            errors.append("boundary test does not exist")
        elif boundary_path:
            expected_hash = boundary.get("sha256")
            if not _sha256_is_valid(expected_hash):
                errors.append(
                    "boundary_test.sha256 must be a 64-character SHA-256 digest"
                )
            elif _sha256(boundary_path).lower() != expected_hash.lower():
                errors.append("boundary test sha256 mismatch")

    reason = record.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        errors.append("reason is required")
    sources = record.get("sources")
    source_kinds: set[str] = set()
    if not isinstance(sources, list) or not sources:
        errors.append("sources must contain maintainer evidence")
    else:
        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                errors.append(f"sources[{index}] must be an object")
                continue
            kind = source.get("kind")
            url = source.get("url")
            if isinstance(kind, str):
                if kind in source_kinds:
                    errors.append(f"sources[{index}].kind must not be duplicated")
                source_kinds.add(kind)
            if not isinstance(kind, str) or not kind.strip():
                errors.append(f"sources[{index}].kind is required")
            elif kind not in ALLOWED_SOURCE_KINDS:
                errors.append(f"sources[{index}].kind is not supported")
            else:
                source_url_error = _validate_source_url(
                    kind=kind, url=url, record=record
                )
                if source_url_error:
                    errors.append(f"sources[{index}].url {source_url_error}")
            retrieved_at, retrieved_error = _parse_timestamp(
                source.get("retrieved_at"), field=f"sources[{index}].retrieved_at"
            )
            if retrieved_error:
                errors.append(retrieved_error)
            elif retrieved_at and retrieved_at > now:
                errors.append(
                    f"sources[{index}].retrieved_at must not be in the future"
                )
        missing_kinds = sorted(REQUIRED_SOURCE_KINDS - source_kinds)
        if missing_kinds:
            errors.append("sources missing required kinds: " + ", ".join(missing_kinds))
    return errors


def _validate_records_payload(
    payload: dict[str, Any], *, root: Path, now: datetime
) -> tuple[list[dict[str, Any]], dict[str, list[str]], list[str]]:
    ledger_errors: list[str] = []
    if payload.get("schema_version") != 1:
        ledger_errors.append("records schema_version must equal 1")
    records = payload.get("records")
    if not isinstance(records, list):
        return [], {}, [*ledger_errors, "records must be an array"]
    if any(not isinstance(record, dict) for record in records):
        return [], {}, [*ledger_errors, "every reconciliation record must be an object"]

    typed_records = list(records)
    record_errors: dict[str, list[str]] = {}
    seen_ids: set[str] = set()
    seen_keys: set[tuple[object, ...]] = set()
    for index, record in enumerate(typed_records):
        record_id = record.get("record_id")
        label = (
            record_id
            if isinstance(record_id, str) and record_id
            else f"record[{index}]"
        )
        errors = _validate_record(record, root=root, now=now)
        if label in seen_ids:
            errors.append("duplicate record_id")
        seen_ids.add(label)
        key = _record_key(record)
        if key in seen_keys:
            errors.append("duplicate exact reconciliation tuple")
        seen_keys.add(key)
        if errors:
            record_errors[label] = errors
    return typed_records, record_errors, ledger_errors


def _expected_scan_arguments(raw_report_path: str) -> list[str]:
    return [
        "scan",
        "source",
        f"--output={raw_report_path}",
        "--format=json",
        *(f"--lockfile={lockfile}" for lockfile in EXPECTED_LOCKFILES),
    ]


def _validate_scan_receipt(
    payload: dict[str, Any],
    *,
    root: Path,
    raw_report_path: Path,
    now: datetime,
) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("scan receipt schema_version must equal 1")
    if payload.get("status") != "completed" or payload.get("completed") is not True:
        errors.append("scan receipt must prove a completed scan")
    receipt_errors = payload.get("errors")
    if not isinstance(receipt_errors, list) or receipt_errors:
        errors.append("scan receipt errors must be an empty array")

    scanner = payload.get("scanner")
    if not isinstance(scanner, dict):
        errors.append("scan receipt scanner object is required")
        scanner = {}
    if scanner.get("name") != EXPECTED_SCANNER_NAME:
        errors.append(f"scanner name must equal {EXPECTED_SCANNER_NAME}")
    if scanner.get("version") != EXPECTED_SCANNER_VERSION:
        errors.append(f"scanner version must equal {EXPECTED_SCANNER_VERSION}")
    if scanner.get("binary_sha256") != EXPECTED_SCANNER_SHA256:
        errors.append(
            "scanner binary sha256 does not match the pinned release artifact"
        )
    scanner_exit_code = scanner.get("exit_code")
    if (
        isinstance(scanner_exit_code, bool)
        or not isinstance(scanner_exit_code, int)
        or scanner_exit_code not in {0, 1}
    ):
        errors.append("scanner exit_code must be 0 (clean) or 1 (findings)")

    started_at, started_error = _parse_timestamp(
        payload.get("started_at"), field="started_at"
    )
    completed_at, completed_error = _parse_timestamp(
        payload.get("completed_at"), field="completed_at"
    )
    if started_error:
        errors.append(started_error)
    if completed_error:
        errors.append(completed_error)
    if started_at and completed_at and completed_at < started_at:
        errors.append("completed_at must not precede started_at")
    if completed_at and completed_at > now:
        errors.append("completed_at must not be in the future")

    raw_report = payload.get("raw_report")
    expected_raw_relative: str | None = None
    if not isinstance(raw_report, dict):
        errors.append("scan receipt raw_report object is required")
    else:
        receipt_raw_path, raw_path_error = _safe_repo_path(
            raw_report.get("path"), root=root, field="scan receipt raw_report.path"
        )
        if raw_path_error:
            errors.append(raw_path_error)
        elif (
            receipt_raw_path and receipt_raw_path.resolve() != raw_report_path.resolve()
        ):
            errors.append(
                "scan receipt raw_report.path does not match the evaluated raw report"
            )
        elif receipt_raw_path:
            expected_raw_relative = _repo_relative_path(
                receipt_raw_path, root=root, field="raw report"
            )
        raw_hash = raw_report.get("sha256")
        if not _sha256_is_valid(raw_hash):
            errors.append("scan receipt raw_report.sha256 must be a SHA-256 digest")
        elif raw_report_path.is_file() and _sha256(raw_report_path) != raw_hash.lower():
            errors.append("scan receipt raw_report sha256 mismatch")

    lockfiles = payload.get("lockfiles")
    lockfile_paths: list[str] = []
    if not isinstance(lockfiles, list):
        errors.append("scan receipt lockfiles must be an array")
    else:
        for index, item in enumerate(lockfiles):
            if not isinstance(item, dict):
                errors.append(f"scan receipt lockfiles[{index}] must be an object")
                continue
            lockfile_path, lockfile_error = _safe_repo_path(
                item.get("path"),
                root=root,
                field=f"scan receipt lockfiles[{index}].path",
            )
            normalized = _normalize_path(str(item.get("path", "")))
            lockfile_paths.append(normalized)
            if lockfile_error:
                errors.append(lockfile_error)
            elif lockfile_path and not lockfile_path.is_file():
                errors.append(f"scan receipt lockfile does not exist: {normalized}")
            else:
                digest = item.get("sha256")
                if not _sha256_is_valid(digest):
                    errors.append(
                        f"scan receipt lockfiles[{index}].sha256 must be a SHA-256 digest"
                    )
                elif lockfile_path and _sha256(lockfile_path) != digest.lower():
                    errors.append(
                        f"scan receipt lockfile sha256 mismatch: {normalized}"
                    )
        if lockfile_paths != list(EXPECTED_LOCKFILES):
            errors.append(
                "scan receipt lockfiles must exactly cover, in order: "
                + ", ".join(EXPECTED_LOCKFILES)
            )

    arguments = payload.get("arguments")
    expected_arguments = (
        _expected_scan_arguments(expected_raw_relative)
        if expected_raw_relative
        else None
    )
    if expected_arguments is None or arguments != expected_arguments:
        errors.append(
            "scan receipt arguments do not prove the exact expected scan command"
        )
    return errors


def run_raw_scan_with_receipt(
    *,
    scanner: str | Path,
    raw_report_path: str | Path = DEFAULT_RAW_REPORT,
    scan_receipt_path: str | Path = DEFAULT_SCAN_RECEIPT,
    root: Path = ROOT,
    now: datetime | None = None,
) -> tuple[int, dict[str, Any]]:
    resolved_root = root.resolve()
    started_at = now or datetime.now(timezone.utc)
    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise GateInputError("scan time must include a timezone")
    raw_path = _resolved_path(raw_report_path, root=resolved_root).resolve()
    receipt_path = _resolved_path(scan_receipt_path, root=resolved_root).resolve()
    records_path = _resolved_path(DEFAULT_RECORDS, root=resolved_root).resolve()
    raw_relative = _repo_relative_path(raw_path, root=resolved_root, field="raw report")
    _repo_relative_path(receipt_path, root=resolved_root, field="scan receipt")
    if raw_path == receipt_path:
        raise GateInputError("scan receipt path must not overwrite the raw OSV report")
    if raw_path == records_path or receipt_path == records_path:
        raise GateInputError(
            "scan outputs must not overwrite the reconciliation records ledger"
        )

    lockfile_paths = [resolved_root / lockfile for lockfile in EXPECTED_LOCKFILES]
    if raw_path in lockfile_paths or receipt_path in lockfile_paths:
        raise GateInputError("scan outputs must not overwrite an expected lockfile")

    errors: list[str] = []
    scanner_value = str(scanner)
    scanner_location = (
        shutil.which(scanner_value)
        if Path(scanner_value).name == scanner_value
        else str(_resolved_path(scanner_value, root=resolved_root).resolve())
    )
    scanner_path = Path(scanner_location).resolve() if scanner_location else None
    scanner_hash: str | None = None
    if scanner_path is None or not scanner_path.is_file():
        errors.append(f"scanner executable does not exist: {scanner_value}")
    else:
        scanner_hash = _sha256(scanner_path)
        if scanner_hash != EXPECTED_SCANNER_SHA256:
            errors.append(
                "scanner binary sha256 does not match the pinned v2.3.0 release artifact"
            )

    before_hashes: dict[str, str] = {}
    for relative, lockfile_path in zip(EXPECTED_LOCKFILES, lockfile_paths, strict=True):
        if not lockfile_path.is_file():
            errors.append(f"expected lockfile does not exist: {relative}")
        else:
            before_hashes[relative] = _sha256(lockfile_path)

    arguments = _expected_scan_arguments(raw_relative)
    scanner_exit_code: int | None = None
    if not errors and scanner_path:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.unlink(missing_ok=True)
        try:
            completed = subprocess.run(
                [str(scanner_path), *arguments],
                cwd=resolved_root,
                check=False,
            )
            scanner_exit_code = int(completed.returncode)
        except OSError as error:
            errors.append(f"scanner execution failed: {error}")
        if scanner_exit_code not in {0, 1}:
            errors.append(
                "scanner did not complete with a documented result code (expected 0 or 1, "
                f"got {scanner_exit_code})"
            )

    lockfile_evidence: list[dict[str, str]] = []
    for relative, lockfile_path in zip(EXPECTED_LOCKFILES, lockfile_paths, strict=True):
        if not lockfile_path.is_file():
            continue
        current_hash = _sha256(lockfile_path)
        if relative in before_hashes and current_hash != before_hashes[relative]:
            errors.append(f"lockfile changed while scanning: {relative}")
        lockfile_evidence.append({"path": relative, "sha256": current_hash})

    raw_hash: str | None = None
    if raw_path.is_file():
        raw_hash = _sha256(raw_path)
        try:
            raw_payload = _load_json_object(raw_path, label="raw OSV report")
            if not isinstance(raw_payload.get("results"), list):
                errors.append("raw OSV report must contain a results array")
        except GateInputError as error:
            errors.append(str(error))
    elif scanner_exit_code is not None:
        errors.append("scanner completed without writing the raw OSV report")

    finished_at = now or datetime.now(timezone.utc)
    receipt = {
        "schema_version": 1,
        "status": "completed" if not errors else "failed",
        "completed": not errors,
        "started_at": started_at.astimezone(timezone.utc).isoformat(),
        "completed_at": finished_at.astimezone(timezone.utc).isoformat(),
        "scanner": {
            "name": EXPECTED_SCANNER_NAME,
            "version": EXPECTED_SCANNER_VERSION,
            "binary_sha256": scanner_hash,
            "exit_code": scanner_exit_code,
        },
        "arguments": arguments,
        "lockfiles": lockfile_evidence,
        "raw_report": {"path": raw_relative, "sha256": raw_hash},
        "errors": errors,
    }
    _write_result(receipt_path, receipt)
    return (0 if not errors else 2), receipt


def evaluate_reconciliation(
    *,
    raw_report: dict[str, Any],
    records_payload: dict[str, Any],
    root: Path,
    now: datetime,
    scanner_exit_code: int | None,
    scan_receipt_errors: list[str],
) -> dict[str, Any]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise GateInputError("evaluation time must include a timezone")
    findings = _extract_findings(raw_report)
    records, record_errors, ledger_errors = _validate_records_payload(
        records_payload, root=root, now=now
    )
    input_errors = list(scan_receipt_errors)
    if scanner_exit_code == 0 and findings:
        input_errors.append(
            "scanner exit code 0 contradicts raw vulnerability findings"
        )
    elif scanner_exit_code == 1 and not findings:
        input_errors.append(
            "scanner exit code 1 has no corresponding raw vulnerability finding"
        )

    reconciled: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    used_record_ids: set[str] = set()
    matched_record_ids: set[str] = set()
    for finding in findings:
        matches = [record for record in records if _record_matches(record, finding)]
        matched_record_ids.update(
            str(record.get("record_id", "")) for record in matches
        )
        if not matches:
            unresolved.append(
                {"finding": finding, "reason": "no exact reconciliation record"}
            )
            continue
        if len(matches) != 1:
            unresolved.append(
                {"finding": finding, "reason": "multiple exact reconciliation records"}
            )
            continue
        record = matches[0]
        record_id = str(record.get("record_id", ""))
        errors = record_errors.get(record_id, [])
        if errors:
            unresolved.append(
                {
                    "finding": finding,
                    "reason": "reconciliation record is invalid",
                    "record_id": record_id,
                    "record_errors": errors,
                }
            )
            continue
        used_record_ids.add(record_id)
        reconciled.append(
            {
                "finding": finding,
                "record_id": record_id,
                "disposition": record["disposition"],
                "owner": record["owner"],
                "approver": record["approver"],
                "expires_at": record["expires_at"],
            }
        )

    unused_active_records = sorted(
        str(record.get("record_id", ""))
        for record in records
        if record.get("status") == "active"
        and str(record.get("record_id", "")) not in matched_record_ids
    )
    if unused_active_records:
        ledger_errors.append(
            "active reconciliation records are unused and must be removed: "
            + ", ".join(unused_active_records)
        )

    status = (
        "pass"
        if not input_errors
        and not ledger_errors
        and not record_errors
        and not unresolved
        else "fail"
    )
    return {
        "schema_version": 1,
        "status": status,
        "evaluated_at": now.astimezone(timezone.utc).isoformat(),
        "scanner_exit_code": scanner_exit_code,
        "counts": {
            "raw": len(findings),
            "reconciled": len(reconciled),
            "unresolved": len(unresolved),
        },
        "raw": findings,
        "reconciled": reconciled,
        "unresolved": unresolved,
        "unused_records": sorted(
            str(record.get("record_id", ""))
            for record in records
            if str(record.get("record_id", "")) not in used_record_ids
        ),
        "unused_active_records": unused_active_records,
        "input_errors": input_errors,
        "ledger_errors": ledger_errors,
        "record_errors": record_errors,
    }


def _write_result(output_path: Path, result: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_gate(
    *,
    raw_report_path: str | Path = DEFAULT_RAW_REPORT,
    scan_receipt_path: str | Path = DEFAULT_SCAN_RECEIPT,
    records_path: str | Path = DEFAULT_RECORDS,
    output_path: str | Path = DEFAULT_OUTPUT,
    root: Path = ROOT,
    now: datetime | None = None,
) -> tuple[int, dict[str, Any]]:
    resolved_root = root.resolve()
    evaluated_at = now or datetime.now(timezone.utc)
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise GateInputError("evaluation time must include a timezone")
    raw_path = _resolved_path(raw_report_path, root=resolved_root).resolve()
    receipt_file = _resolved_path(scan_receipt_path, root=resolved_root).resolve()
    records_file = _resolved_path(records_path, root=resolved_root).resolve()
    adjudication_path = _resolved_path(output_path, root=resolved_root).resolve()
    _repo_relative_path(
        adjudication_path, root=resolved_root, field="adjudication output"
    )
    if adjudication_path == raw_path:
        raise GateInputError("output path must not overwrite the raw OSV report")
    if adjudication_path == receipt_file:
        raise GateInputError("output path must not overwrite the scan receipt")
    if adjudication_path == records_file:
        raise GateInputError(
            "output path must not overwrite the reconciliation records ledger"
        )

    try:
        raw_report = _load_json_object(raw_path, label="raw OSV report")
        scan_receipt = _load_json_object(receipt_file, label="OSV scan receipt")
        records_payload = _load_json_object(
            records_file, label="reconciliation records"
        )
        scan_receipt_errors = _validate_scan_receipt(
            scan_receipt,
            root=resolved_root,
            raw_report_path=raw_path,
            now=evaluated_at,
        )
        scanner = scan_receipt.get("scanner")
        scanner_exit_code = (
            scanner.get("exit_code") if isinstance(scanner, dict) else None
        )
        result = evaluate_reconciliation(
            raw_report=raw_report,
            records_payload=records_payload,
            root=resolved_root,
            now=evaluated_at,
            scanner_exit_code=scanner_exit_code,
            scan_receipt_errors=scan_receipt_errors,
        )
        result["raw_report_path"] = raw_path.as_posix()
        result["raw_report_sha256"] = _sha256(raw_path)
        result["records_path"] = records_file.as_posix()
        result["records_sha256"] = _sha256(records_file)
        result["scan_receipt_path"] = receipt_file.as_posix()
        result["scan_receipt_sha256"] = _sha256(receipt_file)
        result["scan_receipt"] = scan_receipt
        exit_code = 0 if result["status"] == "pass" else 1
    except GateInputError as error:
        result = {
            "schema_version": 1,
            "status": "fail",
            "evaluated_at": evaluated_at.astimezone(timezone.utc).isoformat(),
            "scanner_exit_code": None,
            "counts": {"raw": 0, "reconciled": 0, "unresolved": 0},
            "raw": [],
            "reconciled": [],
            "unresolved": [],
            "unused_records": [],
            "unused_active_records": [],
            "input_errors": [str(error)],
            "ledger_errors": [],
            "record_errors": {},
            "raw_report_path": raw_path.as_posix(),
            "scan_receipt_path": receipt_file.as_posix(),
            "records_path": records_file.as_posix(),
        }
        exit_code = 2
    _write_result(adjudication_path, result)
    return exit_code, result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create complete OSV scan evidence and apply fail-closed exact-tuple reconciliation."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan_parser = subparsers.add_parser(
        "scan", help="run the pinned scanner and write a receipt"
    )
    scan_parser.add_argument("--scanner", required=True)
    scan_parser.add_argument("--raw-report", default=str(DEFAULT_RAW_REPORT))
    scan_parser.add_argument("--scan-receipt", default=str(DEFAULT_SCAN_RECEIPT))

    gate_parser = subparsers.add_parser(
        "evaluate", help="evaluate raw findings and receipt"
    )
    gate_parser.add_argument("--raw-report", default=str(DEFAULT_RAW_REPORT))
    gate_parser.add_argument("--scan-receipt", default=str(DEFAULT_SCAN_RECEIPT))
    gate_parser.add_argument("--records", default=str(DEFAULT_RECORDS))
    gate_parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)
    try:
        if args.command == "scan":
            exit_code, result = run_raw_scan_with_receipt(
                scanner=args.scanner,
                raw_report_path=args.raw_report,
                scan_receipt_path=args.scan_receipt,
            )
        else:
            exit_code, result = run_gate(
                raw_report_path=args.raw_report,
                scan_receipt_path=args.scan_receipt,
                records_path=args.records,
                output_path=args.output,
            )
    except GateInputError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
