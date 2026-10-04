from __future__ import annotations

import argparse
import hashlib
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import bond_risk_shadow_candidate as single_date  # noqa: E402

OUTPUT_ROOTS = (ROOT / "output", ROOT / ".tmp")
RECEIPT_FILENAME = "bond_risk_shadow_batch_receipt.json"
RECEIPT_SCHEMA = "moss.bond-risk-shadow-batch-receipt/v1"
MAX_REPORT_DATES_FILE_BYTES = 64 * 1024
CHILD_RUN_ID_SUFFIX_LENGTH = 12
MAX_BATCH_RUN_ID_LENGTH = 256 - CHILD_RUN_ID_SUFFIX_LENGTH


def _stable_json_dumps(payload: dict[str, object]) -> str:
    return single_date._stable_json_dumps(payload)


def _receipt_sha256(receipt: dict[str, object]) -> str:
    payload = dict(receipt)
    payload.pop("canonical_receipt_sha256", None)
    return single_date._sha256_json(payload)


def _normalize_allowed_output_dir(path: str | Path) -> Path:
    output_dir = single_date._absolute_input_path(path, field_name="batch_output_dir")
    single_date._assert_no_symlink_or_junction(
        output_dir, field_name="batch_output_dir"
    )
    for allowed_root in OUTPUT_ROOTS:
        allowed_abs = single_date._absolute_input_path(
            allowed_root, field_name="batch_output_root"
        )
        single_date._assert_no_symlink_or_junction(
            allowed_abs, field_name="batch_output_root"
        )
        try:
            output_dir.relative_to(allowed_abs)
            break
        except ValueError:
            continue
    else:
        raise single_date.ShadowCandidateError("batch_output_dir_outside_allowed_roots")
    if output_dir in OUTPUT_ROOTS:
        raise single_date.ShadowCandidateError("batch_output_dir_must_not_be_root")
    return output_dir


def _read_report_dates_file(path: str | Path) -> tuple[list[str], dict[str, object]]:
    report_dates_file = single_date._existing_file_no_links(
        single_date._absolute_input_path(path, field_name="report_dates_file"),
        field_name="report_dates_file",
    )
    expected_identity = single_date._path_identity(
        report_dates_file, field_name="report_dates_file"
    )
    try:
        with report_dates_file.open("rb") as handle:
            opened_stat = os.fstat(handle.fileno())
            opened_identity = (opened_stat.st_dev, opened_stat.st_ino)
            if opened_identity != expected_identity:
                raise single_date.ShadowCandidateError(
                    "report_dates_file_identity_changed_before_read"
                )
            encoded = handle.read(MAX_REPORT_DATES_FILE_BYTES + 1)
            completed_stat = os.fstat(handle.fileno())
            if (completed_stat.st_dev, completed_stat.st_ino) != opened_identity:
                raise single_date.ShadowCandidateError(
                    "report_dates_file_identity_changed_during_read"
                )
    except OSError as exc:
        raise single_date.ShadowCandidateError("report_dates_file_read_failed") from exc
    single_date._assert_path_matches_identity(
        report_dates_file,
        expected_identity=expected_identity,
        field_name="report_dates_file",
        code="report_dates_file_identity_changed_after_read",
    )
    if len(encoded) > MAX_REPORT_DATES_FILE_BYTES:
        raise single_date.ShadowCandidateError("report_dates_file_too_large")
    try:
        text = encoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise single_date.ShadowCandidateError(
            "report_dates_file_invalid_utf8"
        ) from exc
    lines = text.splitlines()
    if not lines:
        raise single_date.ShadowCandidateError("report_dates_file_empty")
    report_dates: list[str] = []
    seen: set[str] = set()
    for index, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            raise single_date.ShadowCandidateError(
                "report_dates_file_blank_line", detail=str(index)
            )
        normalized = single_date._validate_report_date(line)
        if normalized in seen:
            raise single_date.ShadowCandidateError(
                "report_dates_file_duplicate_date", detail=normalized
            )
        seen.add(normalized)
        report_dates.append(normalized)
    return report_dates, {
        "path": str(report_dates_file),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "bytes": len(encoded),
        "line_count": len(lines),
        "file_identity": single_date._identity_payload(expected_identity),
    }


def _create_batch_child_output_dir(batch_output_dir: Path, report_date: str) -> Path:
    child_dir = batch_output_dir / report_date
    if child_dir == batch_output_dir:
        raise single_date.ShadowCandidateError("child_output_dir_invalid")
    return child_dir


def _validate_batch_run_id(value: str | None) -> str:
    normalized = single_date._validate_run_id(value)
    if len(normalized) > MAX_BATCH_RUN_ID_LENGTH:
        raise single_date.ShadowCandidateError("batch_run_id_too_long")
    return normalized


def _safe_error_payload(exc: BaseException) -> dict[str, object]:
    if isinstance(exc, single_date.ShadowCandidateError):
        detail = exc.detail
        return {
            "type": exc.__class__.__name__,
            "code": exc.code,
            "detail_sha256": hashlib.sha256(str(detail).encode("utf-8")).hexdigest(),
        }
    detail = f"{exc.__class__.__name__}:{exc}"
    return {
        "type": exc.__class__.__name__,
        "code": "batch_unhandled_exception",
        "detail_sha256": hashlib.sha256(detail.encode("utf-8")).hexdigest(),
    }


def _required_false_flag(receipt: dict[str, object], field_name: str) -> None:
    if receipt.get(field_name) is not False:
        raise single_date.ShadowCandidateError(f"{field_name}_must_be_false")


def _validate_batch_scope(scope: object) -> None:
    if not isinstance(scope, dict):
        raise single_date.ShadowCandidateError("batch_scope_invalid")
    expected = {
        "mode": "multi_report_date_structural_shadow_batch",
        "history_coverage": "multi_report_date_structural_shadow_only",
        "financial_correctness_validated": False,
        "candidate_model": "per_report_date_isolated_candidates",
        "not_a_single_candidate_full_history_rebuild": True,
    }
    for field_name, expected_value in expected.items():
        if scope.get(field_name) != expected_value:
            raise single_date.ShadowCandidateError(f"batch_scope_{field_name}_mismatch")


def _child_summary_from_receipt(
    *,
    report_date: str,
    output_dir: Path,
    receipt: dict[str, object],
) -> dict[str, object]:
    child: dict[str, object] = {
        "report_date": report_date,
        "output_dir": str(output_dir),
        "status": str(receipt.get("status") or "failed"),
        "receipt_persisted": bool(receipt.get("receipt_persisted")),
        "sealed": bool(receipt.get("sealed")),
    }
    if isinstance(receipt.get("error"), dict):
        error = receipt["error"]
        child["error"] = {
            "type": str(error.get("type") or ""),
            "code": str(error.get("code") or ""),
            "detail_sha256": str(error.get("detail_sha256") or ""),
        }
    receipt_path = str(receipt.get("receipt_path") or "").strip()
    if receipt_path:
        child["receipt_path"] = receipt_path
    canonical_sha = str(receipt.get("canonical_receipt_sha256") or "").strip()
    if canonical_sha:
        child["receipt_sha256"] = canonical_sha
    return child


def _validate_child_receipt_binding(
    *,
    report_date: str,
    expected_child_run_id: str,
    receipt: dict[str, object],
    batch_output_dir: Path,
    expected_source_sha256: str,
) -> None:
    if receipt.get("shadow_only") is not True:
        raise single_date.ShadowCandidateError("child_receipt_shadow_only_invalid")
    if receipt.get("release_gate_eligible") is not False:
        raise single_date.ShadowCandidateError("child_receipt_release_gate_invalid")
    if receipt.get("financial_golden_validated") is not False:
        raise single_date.ShadowCandidateError(
            "child_receipt_financial_golden_validated_invalid"
        )
    if receipt.get("wp7_eligible") is not False:
        raise single_date.ShadowCandidateError("child_receipt_wp7_eligible_invalid")
    if str(receipt.get("report_date") or "") != report_date:
        raise single_date.ShadowCandidateError("child_receipt_report_date_mismatch")
    if str(receipt.get("run_id") or "") != expected_child_run_id:
        raise single_date.ShadowCandidateError("child_receipt_run_id_mismatch")
    if str(receipt.get("expected_source_sha256") or "") != expected_source_sha256:
        raise single_date.ShadowCandidateError(
            "child_receipt_expected_source_sha256_mismatch"
        )
    expected_output_dir = _create_batch_child_output_dir(batch_output_dir, report_date)
    child_output_dir = single_date._absolute_input_path(
        receipt.get("output_dir") or "",
        field_name="child_output_dir",
    )
    try:
        child_output_dir.relative_to(batch_output_dir)
    except ValueError as exc:
        raise single_date.ShadowCandidateError(
            "child_output_dir_outside_batch_output_dir"
        ) from exc
    if child_output_dir != expected_output_dir:
        raise single_date.ShadowCandidateError("child_output_dir_mismatch")


def _load_and_verify_child_receipt(
    *,
    report_date: str,
    expected_child_run_id: str,
    receipt_path: str,
    batch_output_dir: Path,
    expected_source_sha256: str,
    verifier: Callable[[str | Path], dict[str, object]],
) -> dict[str, object]:
    expected_receipt_path = (
        _create_batch_child_output_dir(batch_output_dir, report_date)
        / single_date.RECEIPT_FILENAME
    )
    child_receipt_file = single_date._existing_file_no_links(
        single_date._absolute_input_path(receipt_path, field_name="child_receipt_path"),
        field_name="child_receipt_path",
    )
    if child_receipt_file != expected_receipt_path:
        raise single_date.ShadowCandidateError("child_receipt_path_mismatch")
    verified = verifier(child_receipt_file)
    if verified.get("status") != "verified":
        raise single_date.ShadowCandidateError("child_receipt_verifier_status_invalid")
    for digest_field in (
        "receipt_sha256",
        "candidate_sha256",
        "sealed_marker_sha256",
    ):
        if not single_date._SHA256_RE.fullmatch(str(verified.get(digest_field) or "")):
            raise single_date.ShadowCandidateError(
                f"child_receipt_verifier_{digest_field}_invalid"
            )
    child_receipt = single_date._load_json_object(
        child_receipt_file,
        field_name="child_receipt",
        max_bytes=single_date._MAX_RECEIPT_BYTES,
    )
    if str(child_receipt.get("canonical_receipt_sha256") or "") != _receipt_sha256(
        child_receipt
    ):
        raise single_date.ShadowCandidateError("child_receipt_sha256_mismatch")
    if str(verified.get("receipt_sha256") or "") != str(
        child_receipt["canonical_receipt_sha256"]
    ):
        raise single_date.ShadowCandidateError("child_receipt_verifier_sha256_mismatch")
    _validate_child_receipt_binding(
        report_date=report_date,
        expected_child_run_id=expected_child_run_id,
        receipt=child_receipt,
        batch_output_dir=batch_output_dir,
        expected_source_sha256=expected_source_sha256,
    )
    if str(child_receipt.get("receipt_path") or "") != str(expected_receipt_path):
        raise single_date.ShadowCandidateError("child_receipt_internal_path_mismatch")
    return {
        "status": "verified",
        "receipt_path": str(child_receipt["receipt_path"]),
        "receipt_sha256": str(child_receipt["canonical_receipt_sha256"]),
        "candidate_sha256": str(verified.get("candidate_sha256") or ""),
        "sealed_marker_sha256": str(verified.get("sealed_marker_sha256") or ""),
    }


def _validate_counts_against_child_runs(
    *,
    receipt: dict[str, object],
    child_runs: list[dict[str, object]],
) -> None:
    counts = receipt.get("counts")
    if not isinstance(counts, dict):
        raise single_date.ShadowCandidateError("batch_counts_invalid")
    completed = sum(1 for child in child_runs if child.get("status") == "completed")
    failed = sum(1 for child in child_runs if child.get("status") == "failed")
    verified = sum(
        1
        for child in child_runs
        if child.get("status") == "completed"
        and isinstance(child.get("verification"), dict)
        and child["verification"].get("status") == "verified"
    )
    expected = {
        "requested": len(child_runs),
        "completed": completed,
        "failed": failed,
        "verified": verified,
    }
    if counts != expected:
        raise single_date.ShadowCandidateError("batch_counts_mismatch")
    status = str(receipt.get("status") or "")
    if failed == 0 and completed == len(child_runs):
        expected_status = "completed"
    elif completed > 0 and failed > 0:
        expected_status = "partial"
    else:
        expected_status = "failed"
    if status != expected_status:
        raise single_date.ShadowCandidateError("batch_status_child_mismatch")


def verify_bond_risk_shadow_batch_receipt(
    receipt_path: str | Path,
    *,
    child_verifier: Callable[[str | Path], dict[str, object]] | None = None,
) -> dict[str, object]:
    receipt_file = single_date._existing_file_no_links(
        single_date._absolute_input_path(receipt_path, field_name="batch_receipt_path"),
        field_name="batch_receipt_path",
    )
    receipt = single_date._load_json_object(
        receipt_file,
        field_name="batch_receipt",
        max_bytes=single_date._MAX_RECEIPT_BYTES,
    )
    if str(receipt.get("canonical_receipt_sha256") or "") != _receipt_sha256(receipt):
        raise single_date.ShadowCandidateError("batch_receipt_sha256_mismatch")
    if receipt.get("receipt_schema") != RECEIPT_SCHEMA:
        raise single_date.ShadowCandidateError("batch_receipt_schema_unsupported")
    if receipt.get("receipt_persisted") is not True:
        raise single_date.ShadowCandidateError("batch_receipt_not_persisted")
    if receipt.get("shadow_only") is not True:
        raise single_date.ShadowCandidateError("batch_receipt_shadow_only_invalid")
    _required_false_flag(receipt, "release_gate_eligible")
    _required_false_flag(receipt, "financial_golden_validated")
    _required_false_flag(receipt, "wp7_eligible")
    _validate_batch_scope(receipt.get("scope"))
    batch_output_dir = _normalize_allowed_output_dir(
        receipt.get("batch_output_dir") or ""
    )
    if receipt_file != batch_output_dir / RECEIPT_FILENAME:
        raise single_date.ShadowCandidateError("batch_receipt_path_mismatch")
    report_dates = receipt.get("report_dates")
    child_runs = receipt.get("child_runs")
    if not isinstance(report_dates, list) or not all(
        isinstance(item, str) for item in report_dates
    ):
        raise single_date.ShadowCandidateError("batch_report_dates_invalid")
    if not report_dates:
        raise single_date.ShadowCandidateError("batch_report_dates_empty")
    normalized_report_dates = [
        single_date._validate_report_date(report_date) for report_date in report_dates
    ]
    if normalized_report_dates != report_dates:
        raise single_date.ShadowCandidateError("batch_report_dates_not_normalized")
    if len(set(report_dates)) != len(report_dates):
        raise single_date.ShadowCandidateError("batch_report_dates_duplicate")
    if not isinstance(child_runs, list):
        raise single_date.ShadowCandidateError("batch_child_runs_invalid")
    if len(report_dates) != len(child_runs):
        raise single_date.ShadowCandidateError("batch_child_run_count_mismatch")
    expected_source_sha256 = str(receipt.get("expected_source_sha256") or "")
    if not expected_source_sha256:
        raise single_date.ShadowCandidateError("batch_expected_source_sha256_missing")
    raw_batch_run_id = str(receipt.get("batch_run_id") or "").strip()
    if not raw_batch_run_id:
        raise single_date.ShadowCandidateError("batch_run_id_missing")
    batch_run_id = _validate_batch_run_id(raw_batch_run_id)
    if batch_run_id != receipt.get("batch_run_id"):
        raise single_date.ShadowCandidateError("batch_run_id_not_normalized")
    child_verifier_fn = child_verifier or single_date.verify_shadow_candidate_receipt
    for expected_report_date, child in zip(report_dates, child_runs, strict=True):
        if not isinstance(child, dict):
            raise single_date.ShadowCandidateError("batch_child_run_invalid")
        if str(child.get("report_date") or "") != expected_report_date:
            raise single_date.ShadowCandidateError("batch_child_report_date_mismatch")
        if str(child.get("output_dir") or "") != str(
            _create_batch_child_output_dir(batch_output_dir, expected_report_date)
        ):
            raise single_date.ShadowCandidateError("batch_child_output_dir_mismatch")
        child_status = str(child.get("status") or "")
        if child_status not in {"completed", "failed"}:
            raise single_date.ShadowCandidateError("batch_child_status_invalid")
        if child_status == "completed":
            receipt_path_value = str(child.get("receipt_path") or "")
            if not receipt_path_value:
                raise single_date.ShadowCandidateError(
                    "batch_child_receipt_path_missing"
                )
            verified = _load_and_verify_child_receipt(
                report_date=expected_report_date,
                expected_child_run_id=f"{batch_run_id}__{expected_report_date}",
                receipt_path=receipt_path_value,
                batch_output_dir=batch_output_dir,
                expected_source_sha256=expected_source_sha256,
                verifier=child_verifier_fn,
            )
            if str(child.get("receipt_sha256") or "") != verified["receipt_sha256"]:
                raise single_date.ShadowCandidateError(
                    "batch_child_receipt_sha256_mismatch"
                )
            if child.get("verification") != verified:
                raise single_date.ShadowCandidateError(
                    "batch_child_verification_mismatch"
                )
            if (
                child.get("receipt_persisted") is not True
                or child.get("sealed") is not True
            ):
                raise single_date.ShadowCandidateError(
                    "batch_child_completion_flags_invalid"
                )
        else:
            if not isinstance(child.get("error"), dict):
                raise single_date.ShadowCandidateError("batch_child_error_missing")
    _validate_counts_against_child_runs(receipt=receipt, child_runs=child_runs)
    return {
        "status": "verified",
        "receipt_path": str(receipt_file),
        "receipt_sha256": str(receipt["canonical_receipt_sha256"]),
        "child_count": len(child_runs),
    }


def run_bond_risk_shadow_batch(
    *,
    report_dates_file: str | Path,
    source_duckdb_path: str | Path,
    expected_source_sha256: str,
    batch_output_dir: str | Path,
    batch_run_id: str | None = None,
    worker: Callable[..., dict[str, object]] | None = None,
    verifier: Callable[[str | Path], dict[str, object]] | None = None,
) -> dict[str, object]:
    receipt: dict[str, object] = {
        "receipt_schema": RECEIPT_SCHEMA,
        "status": "failed",
        "batch_run_id": None,
        "shadow_only": True,
        "release_gate_eligible": False,
        "financial_golden_validated": False,
        "wp7_eligible": False,
        "evidence_class": "multi-report-date-structural-shadow",
        "source_duckdb_path": None,
        "expected_source_sha256": None,
        "report_dates_file": None,
        "report_dates": [],
        "batch_output_dir": None,
        "receipt_path": None,
        "scope": {
            "mode": "multi_report_date_structural_shadow_batch",
            "history_coverage": "multi_report_date_structural_shadow_only",
            "financial_correctness_validated": False,
            "candidate_model": "per_report_date_isolated_candidates",
            "not_a_single_candidate_full_history_rebuild": True,
        },
        "pending_blockers": [
            "single_candidate_full_history_rebuild_not_proven",
            "financial_golden_validation_not_performed",
            "wp7_release_gate_not_applicable",
        ],
        "child_runs": [],
        "counts": {
            "requested": 0,
            "completed": 0,
            "failed": 0,
            "verified": 0,
        },
        "receipt_persisted": False,
    }
    output_owned = False
    output_identity: tuple[int, int] | None = None
    receipt_parent_identity: tuple[int, int] | None = None
    worker_fn = worker or single_date.run_bond_risk_shadow_candidate
    verifier_fn = verifier or single_date.verify_shadow_candidate_receipt

    try:
        normalized_run_id = _validate_batch_run_id(batch_run_id)
        normalized_expected_sha = single_date._validate_expected_source_sha256(
            expected_source_sha256
        )
        source_path = single_date._existing_file_no_links(
            single_date._absolute_input_path(
                source_duckdb_path, field_name="source_duckdb_path"
            ),
            field_name="source_duckdb_path",
        )
        report_dates, report_dates_binding = _read_report_dates_file(report_dates_file)
        batch_output_path = _normalize_allowed_output_dir(batch_output_dir)
        receipt["batch_run_id"] = normalized_run_id
        receipt["source_duckdb_path"] = str(source_path)
        receipt["expected_source_sha256"] = normalized_expected_sha
        receipt["report_dates_file"] = report_dates_binding
        receipt["report_dates"] = report_dates
        receipt["batch_output_dir"] = str(batch_output_path)
        receipt["receipt_path"] = str(batch_output_path / RECEIPT_FILENAME)
        receipt["counts"]["requested"] = len(report_dates)

        output_info = single_date._create_new_directory(
            batch_output_path, field_name="batch_output_dir"
        )
        output_owned = True
        output_identity = single_date._payload_identity(
            output_info["file_identity"], field_name="batch_output_dir"
        )
        receipt_parent_identity = output_identity
        receipt["batch_output_dir_identity"] = output_info["file_identity"]

        child_runs: list[dict[str, object]] = []
        completed = 0
        failed = 0
        verified = 0
        for report_date in report_dates:
            child_output_dir = _create_batch_child_output_dir(
                batch_output_path, report_date
            )
            try:
                child_receipt = worker_fn(
                    report_date=report_date,
                    source_duckdb_path=source_path,
                    expected_source_sha256=normalized_expected_sha,
                    output_dir=child_output_dir,
                    run_id=f"{normalized_run_id}__{report_date}",
                )
                child_summary = _child_summary_from_receipt(
                    report_date=report_date,
                    output_dir=child_output_dir,
                    receipt=child_receipt,
                )
                if child_receipt.get("status") == "completed":
                    if child_receipt.get("receipt_persisted") is not True:
                        raise single_date.ShadowCandidateError(
                            "child_receipt_not_persisted_for_success"
                        )
                    receipt_path = str(child_receipt.get("receipt_path") or "")
                    if not receipt_path:
                        raise single_date.ShadowCandidateError(
                            "child_receipt_path_missing_for_success"
                        )
                    child_summary["verification"] = _load_and_verify_child_receipt(
                        report_date=report_date,
                        expected_child_run_id=f"{normalized_run_id}__{report_date}",
                        receipt_path=receipt_path,
                        batch_output_dir=batch_output_path,
                        expected_source_sha256=normalized_expected_sha,
                        verifier=verifier_fn,
                    )
                    verified += 1
                    completed += 1
                else:
                    failed += 1
                child_runs.append(child_summary)
            except BaseException as exc:
                failed += 1
                child_runs.append(
                    {
                        "report_date": report_date,
                        "output_dir": str(child_output_dir),
                        "status": "failed",
                        "receipt_persisted": False,
                        "sealed": False,
                        "error": _safe_error_payload(exc),
                    }
                )
        receipt["child_runs"] = child_runs
        receipt["counts"] = {
            "requested": len(report_dates),
            "completed": completed,
            "failed": failed,
            "verified": verified,
        }
        if failed == 0:
            receipt["status"] = "completed"
        elif completed > 0:
            receipt["status"] = "partial"
        else:
            receipt["status"] = "failed"
    except BaseException as exc:
        receipt["status"] = "failed"
        receipt["error"] = _safe_error_payload(exc)
    finally:
        receipt["canonical_receipt_sha256"] = _receipt_sha256(receipt)
        if (
            output_owned
            and receipt_parent_identity is not None
            and output_identity is not None
        ):
            phase1_receipt: dict[str, object] | None = None
            try:
                single_date._assert_path_matches_identity(
                    batch_output_path,
                    expected_identity=output_identity,
                    field_name="batch_output_dir",
                    code="batch_output_dir_identity_changed_before_receipt_write",
                )
                final_receipt = dict(receipt)
                phase1_payload = dict(final_receipt)
                phase1_payload["status"] = "failed"
                phase1_payload["receipt_persisted"] = False
                phase1_payload["error"] = _safe_error_payload(
                    single_date.ShadowCandidateError(
                        "batch_receipt_finalize_incomplete"
                    )
                )
                phase1_receipt = single_date._write_atomic_json_receipt(
                    batch_output_path / RECEIPT_FILENAME,
                    phase1_payload,
                    parent_identity=receipt_parent_identity,
                )
                final_receipt["receipt_persisted"] = True
                final_receipt["canonical_receipt_sha256"] = _receipt_sha256(
                    final_receipt
                )
                previous_identity = phase1_receipt.get("receipt_file_identity")
                if not isinstance(previous_identity, dict):
                    raise single_date.ShadowCandidateError(
                        "batch_receipt_identity_missing"
                    )
                receipt = single_date._write_atomic_json_receipt(
                    batch_output_path / RECEIPT_FILENAME,
                    final_receipt,
                    parent_identity=receipt_parent_identity,
                    allow_existing_identity=single_date._payload_identity(
                        previous_identity, field_name="batch_receipt"
                    ),
                )
            except BaseException as exc:
                if phase1_receipt is not None:
                    receipt = phase1_receipt
                else:
                    receipt["status"] = "failed"
                    receipt["receipt_persisted"] = False
                    receipt["error"] = _safe_error_payload(exc)
                    receipt["canonical_receipt_sha256"] = _receipt_sha256(receipt)
        else:
            receipt["receipt_persisted"] = False
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run multi-report-date structural shadow evidence on isolated per-date DuckDB copies."
    )
    parser.add_argument("--report-dates-file", required=True)
    parser.add_argument("--source-duckdb-path", required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--batch-output-dir", required=True)
    parser.add_argument("--batch-run-id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = run_bond_risk_shadow_batch(
            report_dates_file=args.report_dates_file,
            source_duckdb_path=args.source_duckdb_path,
            expected_source_sha256=args.expected_source_sha256,
            batch_output_dir=args.batch_output_dir,
            batch_run_id=args.batch_run_id,
        )
    except BaseException as exc:
        receipt = {
            "status": "failed",
            "shadow_only": True,
            "release_gate_eligible": False,
            "financial_golden_validated": False,
            "wp7_eligible": False,
            "evidence_class": "multi-report-date-structural-shadow",
            "receipt_persisted": False,
            "error": _safe_error_payload(exc),
        }
    sys.stdout.write(_stable_json_dumps(receipt))
    return 0 if receipt.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
