from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from backend.app.schemas.adb_analysis import AdbAnalysisEnvelope
import scripts.capture_average_balance_monthly_golden_candidate as capture_module
from scripts.capture_average_balance_monthly_golden_candidate import (
    AUTHORITATIVE_GOLDEN_ROOT,
    BOUNDARY_FLAGS,
    CAPTURE_TIMESTAMP,
    CURRENT_RESPONSE_PATH,
    CaptureCandidateError,
    capture_candidate,
    main,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_capture_writes_valid_non_authoritative_candidate_without_touching_golden(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_before = CURRENT_RESPONSE_PATH.read_bytes()
    configured_duckdb = tmp_path / "configured-production-like.duckdb"
    configured_governance = tmp_path / "configured-production-like-governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(configured_duckdb))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(configured_governance))

    output_dir = tmp_path / "candidate"
    receipt = capture_candidate(output_dir)

    assert receipt == {
        "status": "candidate_written",
        "output_dir": str(output_dir.resolve()),
        "files": ["candidate-response.json", "diff.json", "README.md"],
        "current_sha256": hashlib.sha256(current_before).hexdigest(),
        "candidate_sha256": _sha256(output_dir / "candidate-response.json"),
        **BOUNDARY_FLAGS,
    }
    assert CURRENT_RESPONSE_PATH.read_bytes() == current_before
    assert not configured_duckdb.exists()
    assert not configured_governance.exists()
    assert not list(output_dir.rglob("*.duckdb"))

    candidate = json.loads(
        (output_dir / "candidate-response.json").read_text(encoding="utf-8")
    )
    validated = AdbAnalysisEnvelope.model_validate(candidate)
    assert validated.result_meta.generated_at.isoformat().replace("+00:00", "Z") == (
        CAPTURE_TIMESTAMP
    )
    assert candidate["result_meta"]["trace_id"] == "tr_adb_monthly"
    assert candidate["calibration"]["data_basis"] == "formal_facts"

    diff = json.loads((output_dir / "diff.json").read_text(encoding="utf-8"))
    for field, value in BOUNDARY_FLAGS.items():
        assert diff[field] is value
    assert diff["current_sha256"] == hashlib.sha256(current_before).hexdigest()
    assert diff["candidate_sha256"] == _sha256(output_dir / "candidate-response.json")
    current = json.loads(current_before)
    assert (
        "calibration" in diff["added_paths"]
        or "calibration" in current
    )
    assert (
        "result_meta.trace_id" in diff["added_paths"]
        or "trace_id" in current.get("result_meta", {})
    )

    readme = (output_dir / "README.md").read_text(encoding="utf-8")
    for field in BOUNDARY_FLAGS:
        assert f"`{field}=false`" in readme
    assert diff["current_sha256"] in readme
    assert diff["candidate_sha256"] in readme


def test_capture_rejects_existing_output_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "already-exists"
    output_dir.mkdir()

    with pytest.raises(CaptureCandidateError, match="output_dir_must_not_exist"):
        capture_candidate(output_dir)


def test_capture_accepts_old_golden_fixture_when_migration_fields_are_added(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_response = json.loads(CURRENT_RESPONSE_PATH.read_text(encoding="utf-8"))
    old_response.pop("calibration", None)
    old_response["result_meta"].pop("trace_id", None)
    old_path = tmp_path / "old-response.json"
    old_path.write_text(json.dumps(old_response), encoding="utf-8")
    monkeypatch.setattr(capture_module, "CURRENT_RESPONSE_PATH", old_path)

    output_dir = tmp_path / "candidate-from-old-golden"
    capture_candidate(output_dir)

    diff = json.loads((output_dir / "diff.json").read_text(encoding="utf-8"))
    assert "calibration" in diff["added_paths"]
    assert "result_meta.trace_id" in diff["added_paths"]


def test_capture_rejects_authoritative_golden_tree() -> None:
    current_before = CURRENT_RESPONSE_PATH.read_bytes()
    forbidden = AUTHORITATIVE_GOLDEN_ROOT / f"_candidate_forbidden_{uuid4().hex}"
    assert not forbidden.exists()

    with pytest.raises(
        CaptureCandidateError,
        match="output_dir_is_authoritative_golden_tree",
    ):
        capture_candidate(forbidden)

    assert not forbidden.exists()
    assert CURRENT_RESPONSE_PATH.read_bytes() == current_before


def test_capture_rejects_symlink_or_reparse_output_component(tmp_path: Path) -> None:
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    try:
        linked_parent.symlink_to(real_parent, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"directory symlink capability unavailable: {type(exc).__name__}")

    with pytest.raises(
        CaptureCandidateError,
        match="output_dir_parent_contains_symlink_junction_or_reparse",
    ):
        capture_candidate(linked_parent / "candidate")

    assert not (real_parent / "candidate").exists()


def test_cli_requires_explicit_output_dir() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2


def test_cli_writes_valid_candidate_from_real_subprocess(tmp_path: Path) -> None:
    output_dir = tmp_path / "subprocess-candidate"
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "capture_average_balance_monthly_golden_candidate.py"
    )

    completed = subprocess.run(
        [sys.executable, str(script), "--output-dir", str(output_dir)],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr
    receipt = json.loads(completed.stdout)
    assert receipt["status"] == "candidate_written"
    AdbAnalysisEnvelope.model_validate_json(
        (output_dir / "candidate-response.json").read_text(encoding="utf-8")
    )


def test_candidate_bytes_are_deterministic_across_distinct_output_directories(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    capture_candidate(first)
    capture_candidate(second)

    assert (first / "candidate-response.json").read_bytes() == (
        second / "candidate-response.json"
    ).read_bytes()
    assert (first / "diff.json").read_bytes() == (second / "diff.json").read_bytes()
    assert (first / "README.md").read_bytes() == (second / "README.md").read_bytes()
