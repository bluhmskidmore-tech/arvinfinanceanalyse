from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers import load_module
from tests.test_bond_risk_shadow_candidate import _seed_source_db, _sha256


def _load_module():
    return load_module(
        "scripts.bond_risk_shadow_batch",
        "scripts/bond_risk_shadow_batch.py",
    )


def _write_report_dates_file(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _repo_batch_output_dir(module, tmp_path: Path, leaf: str) -> Path:
    # xdist reuses worker names (``popen-gw0``/``popen-gw1``) across separate
    # pytest invocations. Include the invocation's basetemp so the guarded
    # create-new-directory contract does not collide with a prior run.
    invocation_dir = f"{tmp_path.parent.parent.name}-{tmp_path.parent.name}"
    return Path(module.ROOT / ".tmp" / invocation_dir / tmp_path.name / leaf)


def _completed_child_receipt(
    module,
    *,
    report_date: str,
    run_id: str,
    source_sha: str,
    output_dir: Path,
) -> dict[str, object]:
    child_output_dir = output_dir / report_date
    child_output_dir.mkdir()
    receipt_path = child_output_dir / "bond_risk_shadow_candidate_receipt.json"
    payload = {
        "status": "completed",
        "run_id": run_id,
        "report_date": report_date,
        "expected_source_sha256": source_sha,
        "shadow_only": True,
        "release_gate_eligible": False,
        "financial_golden_validated": False,
        "wp7_eligible": False,
        "output_dir": str(child_output_dir.resolve()),
        "receipt_path": str(receipt_path.resolve()),
        "candidate_duckdb_path": str((child_output_dir / "candidate.duckdb").resolve()),
        "sealed": True,
        "receipt_persisted": True,
    }
    payload["canonical_receipt_sha256"] = module._receipt_sha256(payload)
    receipt_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def _verified_child_receipt(receipt: dict[str, object]) -> dict[str, object]:
    return {
        "status": "verified",
        "receipt_path": str(receipt["receipt_path"]),
        "receipt_sha256": str(receipt["canonical_receipt_sha256"]),
        "candidate_sha256": "c" * 64,
        "sealed_marker_sha256": "d" * 64,
    }


def _run_successful_batch(
    module,
    tmp_path: Path,
    *,
    report_dates: list[str] | None = None,
    batch_run_id: str = "batch-success",
) -> tuple[dict[str, object], Path]:
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(source_path)
    report_dates_file = _write_report_dates_file(
        tmp_path / "report-dates-success.txt",
        report_dates or ["2026-05-30", "2026-05-31"],
    )
    batch_output_dir = _repo_batch_output_dir(module, tmp_path, "batch-success-output")
    batch_output_dir.parent.mkdir(parents=True, exist_ok=True)

    def fake_worker(**kwargs: object) -> dict[str, object]:
        return _completed_child_receipt(
            module,
            report_date=str(kwargs["report_date"]),
            run_id=str(kwargs["run_id"]),
            source_sha=str(kwargs["expected_source_sha256"]),
            output_dir=batch_output_dir,
        )

    def fake_verifier(receipt_path: str | Path) -> dict[str, object]:
        payload = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
        return _verified_child_receipt(payload)

    receipt = module.run_bond_risk_shadow_batch(
        report_dates_file=report_dates_file,
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        batch_output_dir=batch_output_dir,
        batch_run_id=batch_run_id,
        worker=fake_worker,
        verifier=fake_verifier,
    )
    return receipt, batch_output_dir


def test_batch_rejects_duplicate_dates_file_entries(tmp_path: Path) -> None:
    module = _load_module()
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(source_path)
    report_dates_file = _write_report_dates_file(
        tmp_path / "report-dates.txt",
        ["2026-05-31", "2026-05-31"],
    )

    receipt = module.run_bond_risk_shadow_batch(
        report_dates_file=report_dates_file,
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        batch_output_dir=tmp_path / "outside-output",
        batch_run_id="batch-duplicate",
    )

    assert receipt["status"] == "failed"
    assert receipt["receipt_persisted"] is False
    assert receipt["error"]["code"] == "report_dates_file_duplicate_date"


def test_batch_rejects_blank_line_before_any_output_creation(tmp_path: Path) -> None:
    module = _load_module()
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(source_path)
    report_dates_file = _write_report_dates_file(
        tmp_path / "report-dates-blank.txt",
        ["2026-05-31", ""],
    )
    batch_output_dir = _repo_batch_output_dir(module, tmp_path, "batch-blank-lines")

    receipt = module.run_bond_risk_shadow_batch(
        report_dates_file=report_dates_file,
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        batch_output_dir=batch_output_dir,
        batch_run_id="batch-blank",
    )

    assert receipt["status"] == "failed"
    assert receipt["receipt_persisted"] is False
    assert receipt["error"]["code"] == "report_dates_file_blank_line"
    assert not batch_output_dir.exists()


def test_batch_uses_same_frozen_source_and_creates_isolated_output_dirs(
    tmp_path: Path,
) -> None:
    module = _load_module()
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(source_path)
    source_sha = _sha256(source_path)
    report_dates_file = _write_report_dates_file(
        tmp_path / "report-dates.txt",
        ["2026-05-30", "2026-05-31"],
    )
    batch_output_dir = _repo_batch_output_dir(module, tmp_path, "batch-isolated-output")
    batch_output_dir.parent.mkdir(parents=True, exist_ok=True)
    calls: list[dict[str, object]] = []
    verified_paths: list[str] = []

    def fake_worker(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        receipt = _completed_child_receipt(
            module,
            report_date=str(kwargs["report_date"]),
            run_id=str(kwargs["run_id"]),
            source_sha=str(kwargs["expected_source_sha256"]),
            output_dir=batch_output_dir,
        )
        return receipt

    def fake_verifier(receipt_path: str | Path) -> dict[str, object]:
        verified_paths.append(str(receipt_path))
        payload = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
        return _verified_child_receipt(payload)

    receipt = module.run_bond_risk_shadow_batch(
        report_dates_file=report_dates_file,
        source_duckdb_path=source_path,
        expected_source_sha256=source_sha,
        batch_output_dir=batch_output_dir,
        batch_run_id="batch-isolated",
        worker=fake_worker,
        verifier=fake_verifier,
    )

    assert receipt["status"] == "completed"
    assert receipt["receipt_schema"] == module.RECEIPT_SCHEMA
    assert receipt["receipt_persisted"] is True
    assert receipt["release_gate_eligible"] is False
    assert receipt["financial_golden_validated"] is False
    assert receipt["wp7_eligible"] is False
    assert (
        receipt["scope"]["history_coverage"]
        == "multi_report_date_structural_shadow_only"
    )
    assert receipt["scope"]["not_a_single_candidate_full_history_rebuild"] is True
    assert receipt["counts"] == {
        "requested": 2,
        "completed": 2,
        "failed": 0,
        "verified": 2,
    }
    assert [call["report_date"] for call in calls] == ["2026-05-30", "2026-05-31"]
    assert all(call["source_duckdb_path"] == source_path for call in calls)
    assert all(call["expected_source_sha256"] == source_sha for call in calls)
    assert calls[0]["output_dir"] != calls[1]["output_dir"]
    assert calls[0]["run_id"] == "batch-isolated__2026-05-30"
    assert calls[1]["run_id"] == "batch-isolated__2026-05-31"
    assert len(verified_paths) == 2


def test_batch_continues_after_child_failure_and_redacts_unhandled_error(
    tmp_path: Path,
) -> None:
    module = _load_module()
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(source_path)
    report_dates_file = _write_report_dates_file(
        tmp_path / "report-dates-partial.txt",
        ["2026-05-30", "2026-05-31"],
    )
    batch_output_dir = _repo_batch_output_dir(module, tmp_path, "batch-partial-output")
    batch_output_dir.parent.mkdir(parents=True, exist_ok=True)

    def fake_worker(**kwargs: object) -> dict[str, object]:
        if str(kwargs["report_date"]) == "2026-05-30":
            raise RuntimeError("secret-token-123 should not leak")
        return _completed_child_receipt(
            module,
            report_date="2026-05-31",
            run_id=str(kwargs["run_id"]),
            source_sha=str(kwargs["expected_source_sha256"]),
            output_dir=batch_output_dir,
        )

    def fake_verifier(receipt_path: str | Path) -> dict[str, object]:
        payload = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
        verified = _verified_child_receipt(payload)
        verified["candidate_sha256"] = "e" * 64
        verified["sealed_marker_sha256"] = "f" * 64
        return verified

    receipt = module.run_bond_risk_shadow_batch(
        report_dates_file=report_dates_file,
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        batch_output_dir=batch_output_dir,
        batch_run_id="batch-partial",
        worker=fake_worker,
        verifier=fake_verifier,
    )

    serialized = json.dumps(receipt, ensure_ascii=False, sort_keys=True)
    assert receipt["status"] == "partial"
    assert receipt["counts"] == {
        "requested": 2,
        "completed": 1,
        "failed": 1,
        "verified": 1,
    }
    first = receipt["child_runs"][0]
    second = receipt["child_runs"][1]
    assert first["status"] == "failed"
    assert first["error"]["code"] == "batch_unhandled_exception"
    assert "secret-token-123" not in serialized
    assert second["status"] == "completed"
    assert second["verification"]["status"] == "verified"


def test_batch_marks_child_failed_when_verifier_rejects_success_receipt(
    tmp_path: Path,
) -> None:
    module = _load_module()
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(source_path)
    report_dates_file = _write_report_dates_file(
        tmp_path / "report-dates-verify.txt",
        ["2026-05-31"],
    )
    batch_output_dir = _repo_batch_output_dir(module, tmp_path, "batch-verify-output")
    batch_output_dir.parent.mkdir(parents=True, exist_ok=True)

    def fake_worker(**kwargs: object) -> dict[str, object]:
        return _completed_child_receipt(
            module,
            report_date=str(kwargs["report_date"]),
            run_id=str(kwargs["run_id"]),
            source_sha=str(kwargs["expected_source_sha256"]),
            output_dir=batch_output_dir,
        )

    def fake_verifier(receipt_path: str | Path) -> dict[str, object]:
        raise module.single_date.ShadowCandidateError("sealed_marker_missing")

    receipt = module.run_bond_risk_shadow_batch(
        report_dates_file=report_dates_file,
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        batch_output_dir=batch_output_dir,
        batch_run_id="batch-verify",
        worker=fake_worker,
        verifier=fake_verifier,
    )

    assert receipt["status"] == "failed"
    assert receipt["counts"] == {
        "requested": 1,
        "completed": 0,
        "failed": 1,
        "verified": 0,
    }
    child = receipt["child_runs"][0]
    assert child["status"] == "failed"
    assert child["error"]["code"] == "sealed_marker_missing"


def test_batch_fails_when_child_verifier_sha_mismatches_disk_receipt(
    tmp_path: Path,
) -> None:
    module = _load_module()
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(source_path)
    report_dates_file = _write_report_dates_file(
        tmp_path / "report-dates-sha.txt",
        ["2026-05-31"],
    )
    batch_output_dir = _repo_batch_output_dir(module, tmp_path, "batch-verifier-sha")
    batch_output_dir.parent.mkdir(parents=True, exist_ok=True)

    def fake_worker(**kwargs: object) -> dict[str, object]:
        return _completed_child_receipt(
            module,
            report_date=str(kwargs["report_date"]),
            run_id=str(kwargs["run_id"]),
            source_sha=str(kwargs["expected_source_sha256"]),
            output_dir=batch_output_dir,
        )

    def fake_verifier(receipt_path: str | Path) -> dict[str, object]:
        payload = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
        verified = _verified_child_receipt(payload)
        verified["receipt_sha256"] = "0" * 64
        return verified

    receipt = module.run_bond_risk_shadow_batch(
        report_dates_file=report_dates_file,
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        batch_output_dir=batch_output_dir,
        batch_run_id="batch-verifier-sha",
        worker=fake_worker,
        verifier=fake_verifier,
    )

    assert receipt["status"] == "failed"
    assert (
        receipt["child_runs"][0]["error"]["code"]
        == "child_receipt_verifier_sha256_mismatch"
    )


def test_batch_rejects_explicit_run_id_that_cannot_fit_child_suffix(
    tmp_path: Path,
) -> None:
    module = _load_module()
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(source_path)
    report_dates_file = _write_report_dates_file(
        tmp_path / "report-dates-run-id.txt",
        ["2026-05-31"],
    )
    batch_output_dir = _repo_batch_output_dir(module, tmp_path, "batch-run-id-output")
    batch_output_dir.parent.mkdir(parents=True, exist_ok=True)

    receipt = module.run_bond_risk_shadow_batch(
        report_dates_file=report_dates_file,
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        batch_output_dir=batch_output_dir,
        batch_run_id="r" * 245,
    )

    assert receipt["status"] == "failed"
    assert receipt["receipt_persisted"] is False
    assert receipt["error"]["code"] == "batch_run_id_too_long"


def test_verify_batch_receipt_detects_aggregate_tamper(tmp_path: Path) -> None:
    module = _load_module()
    receipt, batch_output_dir = _run_successful_batch(module, tmp_path)

    assert receipt["status"] == "completed"
    receipt_path = batch_output_dir / module.RECEIPT_FILENAME
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["release_gate_eligible"] = True
    receipt_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(
        module.single_date.ShadowCandidateError,
        match="batch_receipt_sha256_mismatch|release_gate_eligible_must_be_false",
    ):
        module.verify_bond_risk_shadow_batch_receipt(receipt_path)


def test_verify_batch_receipt_rejects_rehashed_status_child_mismatch(
    tmp_path: Path,
) -> None:
    module = _load_module()
    receipt, batch_output_dir = _run_successful_batch(module, tmp_path)

    assert receipt["status"] == "completed"
    receipt_path = batch_output_dir / module.RECEIPT_FILENAME
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["status"] = "failed"
    payload["canonical_receipt_sha256"] = module._receipt_sha256(payload)
    receipt_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def fake_child_verifier(child_receipt_path: str | Path) -> dict[str, object]:
        child_payload = json.loads(Path(child_receipt_path).read_text(encoding="utf-8"))
        return _verified_child_receipt(child_payload)

    with pytest.raises(
        module.single_date.ShadowCandidateError,
        match="batch_status_child_mismatch",
    ):
        module.verify_bond_risk_shadow_batch_receipt(
            receipt_path,
            child_verifier=fake_child_verifier,
        )


def test_verify_batch_receipt_rejects_output_dir_outside_allowed_roots(
    tmp_path: Path,
) -> None:
    module = _load_module()
    receipt, batch_output_dir = _run_successful_batch(module, tmp_path)
    receipt_path = batch_output_dir / module.RECEIPT_FILENAME
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["batch_output_dir"] = str((tmp_path / "outside-batch").resolve())
    payload["canonical_receipt_sha256"] = module._receipt_sha256(payload)
    receipt_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(
        module.single_date.ShadowCandidateError,
        match="batch_output_dir_outside_allowed_roots",
    ):
        module.verify_bond_risk_shadow_batch_receipt(receipt_path)

    assert receipt["status"] == "completed"


def test_verify_batch_receipt_requires_versioned_schema(tmp_path: Path) -> None:
    module = _load_module()
    _, batch_output_dir = _run_successful_batch(module, tmp_path)
    receipt_path = batch_output_dir / module.RECEIPT_FILENAME
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload.pop("receipt_schema")
    payload["canonical_receipt_sha256"] = module._receipt_sha256(payload)
    receipt_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(
        module.single_date.ShadowCandidateError,
        match="batch_receipt_schema_unsupported",
    ):
        module.verify_bond_risk_shadow_batch_receipt(receipt_path)


def test_verify_batch_receipt_rejects_rehashed_recorded_verification_mismatch(
    tmp_path: Path,
) -> None:
    module = _load_module()
    receipt, batch_output_dir = _run_successful_batch(module, tmp_path)

    assert receipt["status"] == "completed"
    receipt_path = batch_output_dir / module.RECEIPT_FILENAME
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["child_runs"][0]["verification"]["candidate_sha256"] = "e" * 64
    payload["canonical_receipt_sha256"] = module._receipt_sha256(payload)
    receipt_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def fake_child_verifier(child_receipt_path: str | Path) -> dict[str, object]:
        child_payload = json.loads(Path(child_receipt_path).read_text(encoding="utf-8"))
        return _verified_child_receipt(child_payload)

    with pytest.raises(
        module.single_date.ShadowCandidateError,
        match="batch_child_verification_mismatch",
    ):
        module.verify_bond_risk_shadow_batch_receipt(
            receipt_path,
            child_verifier=fake_child_verifier,
        )


def test_verify_batch_receipt_detects_child_receipt_report_date_tamper(
    tmp_path: Path,
) -> None:
    module = _load_module()
    receipt, batch_output_dir = _run_successful_batch(module, tmp_path)

    assert receipt["status"] == "completed"
    child_receipt_path = (
        batch_output_dir / "2026-05-30" / "bond_risk_shadow_candidate_receipt.json"
    )
    child_payload = json.loads(child_receipt_path.read_text(encoding="utf-8"))
    child_payload["report_date"] = "2026-05-29"
    child_payload["canonical_receipt_sha256"] = module._receipt_sha256(child_payload)
    child_receipt_path.write_text(
        json.dumps(child_payload, ensure_ascii=False), encoding="utf-8"
    )

    def fake_child_verifier(receipt_path: str | Path) -> dict[str, object]:
        payload = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
        return _verified_child_receipt(payload)

    with pytest.raises(
        module.single_date.ShadowCandidateError,
        match="child_receipt_report_date_mismatch",
    ):
        module.verify_bond_risk_shadow_batch_receipt(
            batch_output_dir / module.RECEIPT_FILENAME,
            child_verifier=fake_child_verifier,
        )


def test_verify_batch_receipt_detects_child_expected_source_sha_tamper(
    tmp_path: Path,
) -> None:
    module = _load_module()
    receipt, batch_output_dir = _run_successful_batch(module, tmp_path)

    assert receipt["status"] == "completed"
    child_receipt_path = (
        batch_output_dir / "2026-05-31" / "bond_risk_shadow_candidate_receipt.json"
    )
    child_payload = json.loads(child_receipt_path.read_text(encoding="utf-8"))
    child_payload["expected_source_sha256"] = "a" * 64
    child_payload["canonical_receipt_sha256"] = module._receipt_sha256(child_payload)
    child_receipt_path.write_text(
        json.dumps(child_payload, ensure_ascii=False), encoding="utf-8"
    )

    def fake_child_verifier(receipt_path: str | Path) -> dict[str, object]:
        payload = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
        return _verified_child_receipt(payload)

    with pytest.raises(
        module.single_date.ShadowCandidateError,
        match="child_receipt_expected_source_sha256_mismatch",
    ):
        module.verify_bond_risk_shadow_batch_receipt(
            batch_output_dir / module.RECEIPT_FILENAME,
            child_verifier=fake_child_verifier,
        )


def test_verify_batch_receipt_detects_child_verifier_sha_mismatch(
    tmp_path: Path,
) -> None:
    module = _load_module()
    receipt, batch_output_dir = _run_successful_batch(module, tmp_path)

    assert receipt["status"] == "completed"

    def fake_child_verifier(receipt_path: str | Path) -> dict[str, object]:
        payload = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
        verified = _verified_child_receipt(payload)
        verified["receipt_sha256"] = "1" * 64
        return verified

    with pytest.raises(
        module.single_date.ShadowCandidateError,
        match="child_receipt_verifier_sha256_mismatch",
    ):
        module.verify_bond_risk_shadow_batch_receipt(
            batch_output_dir / module.RECEIPT_FILENAME,
            child_verifier=fake_child_verifier,
        )


def test_verify_batch_rejects_external_child_path_before_calling_verifier(
    tmp_path: Path,
) -> None:
    module = _load_module()
    receipt, batch_output_dir = _run_successful_batch(module, tmp_path)
    receipt_path = batch_output_dir / module.RECEIPT_FILENAME
    outside_receipt = tmp_path / "outside-child-receipt.json"
    outside_receipt.write_text("{}", encoding="utf-8")
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["child_runs"][0]["receipt_path"] = str(outside_receipt.resolve())
    payload["canonical_receipt_sha256"] = module._receipt_sha256(payload)
    receipt_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    verifier_called = False

    def forbidden_verifier(_: str | Path) -> dict[str, object]:
        nonlocal verifier_called
        verifier_called = True
        raise AssertionError("external child path must be rejected before verification")

    with pytest.raises(
        module.single_date.ShadowCandidateError,
        match="child_receipt_path_mismatch",
    ):
        module.verify_bond_risk_shadow_batch_receipt(
            receipt_path,
            child_verifier=forbidden_verifier,
        )

    assert receipt["status"] == "completed"
    assert verifier_called is False


def test_verify_batch_receipt_binds_child_run_id(tmp_path: Path) -> None:
    module = _load_module()
    receipt, batch_output_dir = _run_successful_batch(module, tmp_path)
    child_receipt_path = Path(receipt["child_runs"][0]["receipt_path"])
    child_payload = json.loads(child_receipt_path.read_text(encoding="utf-8"))
    child_payload["run_id"] = "another-batch__2026-05-30"
    child_payload["canonical_receipt_sha256"] = module._receipt_sha256(child_payload)
    child_receipt_path.write_text(
        json.dumps(child_payload, ensure_ascii=False), encoding="utf-8"
    )

    def fake_child_verifier(path: str | Path) -> dict[str, object]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return _verified_child_receipt(payload)

    with pytest.raises(
        module.single_date.ShadowCandidateError,
        match="child_receipt_run_id_mismatch",
    ):
        module.verify_bond_risk_shadow_batch_receipt(
            batch_output_dir / module.RECEIPT_FILENAME,
            child_verifier=fake_child_verifier,
        )


def test_batch_second_stage_write_failure_leaves_matching_fail_closed_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    original_writer = module.single_date._write_atomic_json_receipt
    write_count = 0

    def fail_second_write(*args: object, **kwargs: object) -> dict[str, object]:
        nonlocal write_count
        write_count += 1
        if write_count == 2:
            raise module.single_date.ShadowCandidateError(
                "forced_batch_receipt_finalize_failure"
            )
        return original_writer(*args, **kwargs)

    monkeypatch.setattr(
        module.single_date,
        "_write_atomic_json_receipt",
        fail_second_write,
    )
    receipt, batch_output_dir = _run_successful_batch(module, tmp_path)
    receipt_path = batch_output_dir / module.RECEIPT_FILENAME
    persisted = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert write_count == 2
    assert receipt == persisted
    assert receipt["status"] == "failed"
    assert receipt["receipt_persisted"] is False
    assert receipt["error"]["code"] == "batch_receipt_finalize_incomplete"
    assert receipt["canonical_receipt_sha256"] == module._receipt_sha256(receipt)


def test_report_dates_file_rejects_opened_identity_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    report_dates_file = _write_report_dates_file(
        tmp_path / "report-dates-identity.txt",
        ["2026-05-31"],
    )
    original_fstat = module.os.fstat

    def mismatched_fstat(descriptor: int):
        observed = original_fstat(descriptor)
        return type(
            "MismatchedStat",
            (),
            {"st_dev": observed.st_dev, "st_ino": observed.st_ino + 1},
        )()

    monkeypatch.setattr(module.os, "fstat", mismatched_fstat)

    with pytest.raises(
        module.single_date.ShadowCandidateError,
        match="report_dates_file_identity_changed_before_read",
    ):
        module._read_report_dates_file(report_dates_file)


def test_batch_cli_returns_zero_only_when_all_children_succeed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(source_path)
    report_dates_file = _write_report_dates_file(
        tmp_path / "report-dates-cli.txt",
        ["2026-05-31"],
    )
    batch_output_dir = _repo_batch_output_dir(module, tmp_path, "batch-cli-output")

    monkeypatch.setattr(
        module,
        "run_bond_risk_shadow_batch",
        lambda **kwargs: {
            "status": "completed",
            "shadow_only": True,
            "release_gate_eligible": False,
            "financial_golden_validated": False,
            "wp7_eligible": False,
            "receipt_persisted": True,
            "child_runs": [],
        },
    )

    exit_code = module.main(
        [
            "--report-dates-file",
            str(report_dates_file),
            "--source-duckdb-path",
            str(source_path),
            "--expected-source-sha256",
            _sha256(source_path),
            "--batch-output-dir",
            str(batch_output_dir),
            "--batch-run-id",
            "batch-cli",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "completed"
    assert payload["release_gate_eligible"] is False
