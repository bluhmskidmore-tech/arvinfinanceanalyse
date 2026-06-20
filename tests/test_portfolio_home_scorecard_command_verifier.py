from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.verify_portfolio_home_scorecard_commands import (
    ALLOWED_COMMANDS,
    _allowed_argv,
    _command_argv,
    build_report,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_portfolio_home_scorecard_commands.py"


def _run_verifier(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_portfolio_home_scorecard_command_verifier_uses_allowlist() -> None:
    assert "python scripts/portfolio_home_closure_scorecard.py --limit 3" in ALLOWED_COMMANDS
    assert "python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score" in ALLOWED_COMMANDS
    assert "python scripts/portfolio_home_owner_action_packet.py --limit 3" in ALLOWED_COMMANDS
    assert (
        "python scripts/portfolio_home_owner_action_packet.py --limit 3 --output docs/portfolio/portfolio-home-owner-action-packet.json --check-current"
        in ALLOWED_COMMANDS
    )
    assert "python scripts/portfolio_home_owner_action_packet.py --limit 3 --require-clean" in ALLOWED_COMMANDS
    assert "python scripts/portfolio_home_business_owner_approval_packet.py --limit 3" in ALLOWED_COMMANDS
    assert (
        "python scripts/portfolio_home_business_owner_approval_packet.py --limit 3 --output docs/portfolio/portfolio-home-business-owner-approval-packet.json --check-current"
        in ALLOWED_COMMANDS
    )
    assert (
        "python scripts/portfolio_home_business_owner_approval_packet.py --limit 3 --require-ready"
        in ALLOWED_COMMANDS
    )
    assert "python scripts/portfolio_home_owner_handoff_packet.py --limit 3" in ALLOWED_COMMANDS
    assert (
        "python scripts/portfolio_home_owner_handoff_packet.py --limit 3 --check-current"
        in ALLOWED_COMMANDS
    )
    assert (
        "python scripts/portfolio_home_owner_handoff_completeness_check.py --limit 3 --require-clean"
        in ALLOWED_COMMANDS
    )
    assert (
        "python scripts/portfolio_home_evidence_snapshot.py --scorecard-limit 1 --verifier-limit 1 --output docs/portfolio/portfolio-home-evidence-snapshot.json --check-current"
        in ALLOWED_COMMANDS
    )
    assert (
        "python scripts/portfolio_home_evidence_snapshot_alignment_check.py --require-clean"
        in ALLOWED_COMMANDS
    )
    assert "python scripts/portfolio_home_owner_input_needed_summary.py --limit 3" in ALLOWED_COMMANDS
    assert (
        "python scripts/portfolio_home_owner_input_needed_summary.py --limit 3 --output docs/portfolio/portfolio-home-owner-input-needed-summary.json --check-current"
        in ALLOWED_COMMANDS
    )
    assert "python scripts/portfolio_home_dependency_consistency_check.py --limit 3" in ALLOWED_COMMANDS
    assert (
        "python scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent"
        in ALLOWED_COMMANDS
    )
    assert "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3" in ALLOWED_COMMANDS
    assert (
        "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready"
        in ALLOWED_COMMANDS
    )
    assert (
        "python scripts/portfolio_home_score_blocker_consistency_check.py --require-consistent"
        in ALLOWED_COMMANDS
    )
    assert (
        "python scripts/portfolio_home_blocker_closure_matrix_check.py --require-clean"
        in ALLOWED_COMMANDS
    )
    assert (
        "python scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current"
        in ALLOWED_COMMANDS
    )
    assert "python scripts/portfolio_home_evidence_packet_guard.py --require-clean" in ALLOWED_COMMANDS
    assert (
        "python scripts/portfolio_home_maturity_remediation_export.py --output-dir docs/portfolio/maturity-remediation"
        in ALLOWED_COMMANDS
    )
    assert (
        "python scripts/portfolio_home_maturity_remediation_export.py --output-dir docs/portfolio/maturity-remediation --require-clean"
        in ALLOWED_COMMANDS
    )
    assert (
        "python scripts/portfolio_home_maturity_remediation_export.py --output-dir docs/portfolio/maturity-remediation --check-current"
        in ALLOWED_COMMANDS
    )
    assert (
        "python scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision"
        in ALLOWED_COMMANDS
    )
    assert (
        "python scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision --require-clean"
        in ALLOWED_COMMANDS
    )
    assert (
        "python scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision --check-current"
        in ALLOWED_COMMANDS
    )
    assert all(";" not in command for command in ALLOWED_COMMANDS)
    assert all("|" not in command for command in ALLOWED_COMMANDS)


def test_portfolio_home_scorecard_command_verifier_rewrites_snapshot_output_to_docs_root(
    tmp_path: Path,
) -> None:
    argv = _command_argv(
        "python scripts/portfolio_home_evidence_snapshot.py --scorecard-limit 1 --verifier-limit 1 --output docs/portfolio/portfolio-home-evidence-snapshot.json --check-current",
        docs_root=tmp_path / "docs",
    )

    assert argv[argv.index("--docs-root") + 1] == str(tmp_path / "docs")
    assert argv[argv.index("--output") + 1] == str(
        tmp_path / "docs" / "portfolio" / "portfolio-home-evidence-snapshot.json"
    )


def test_portfolio_home_scorecard_command_verifier_rewrites_snapshot_alignment_to_docs_root(
    tmp_path: Path,
) -> None:
    argv = _command_argv(
        "python scripts/portfolio_home_evidence_snapshot_alignment_check.py --require-clean",
        docs_root=tmp_path / "docs",
    )

    assert argv == [
        sys.executable,
        "scripts/portfolio_home_evidence_snapshot_alignment_check.py",
        "--require-clean",
        "--snapshot",
        str(tmp_path / "docs" / "portfolio" / "portfolio-home-evidence-snapshot.json"),
    ]


def test_portfolio_home_scorecard_command_verifier_rewrites_owner_input_summary_output_to_docs_root(
    tmp_path: Path,
) -> None:
    argv = _command_argv(
        "python scripts/portfolio_home_owner_input_needed_summary.py --limit 3 --output docs/portfolio/portfolio-home-owner-input-needed-summary.json --check-current",
        docs_root=tmp_path / "docs",
    )

    assert argv[argv.index("--docs-root") + 1] == str(tmp_path / "docs")
    assert argv[argv.index("--output") + 1] == str(
        tmp_path / "docs" / "portfolio" / "portfolio-home-owner-input-needed-summary.json"
    )


def test_portfolio_home_scorecard_command_verifier_rewrites_owner_action_packet_output_to_docs_root(
    tmp_path: Path,
) -> None:
    argv = _command_argv(
        "python scripts/portfolio_home_owner_action_packet.py --limit 3 --output docs/portfolio/portfolio-home-owner-action-packet.json --check-current",
        docs_root=tmp_path / "docs",
    )

    assert argv[argv.index("--docs-root") + 1] == str(tmp_path / "docs")
    assert argv[argv.index("--output") + 1] == str(
        tmp_path / "docs" / "portfolio" / "portfolio-home-owner-action-packet.json"
    )


def test_portfolio_home_scorecard_command_verifier_rewrites_business_owner_approval_packet_output_to_docs_root(
    tmp_path: Path,
) -> None:
    argv = _command_argv(
        "python scripts/portfolio_home_business_owner_approval_packet.py --limit 3 --output docs/portfolio/portfolio-home-business-owner-approval-packet.json --check-current",
        docs_root=tmp_path / "docs",
    )

    assert argv[argv.index("--docs-root") + 1] == str(tmp_path / "docs")
    assert argv[argv.index("--output") + 1] == str(
        tmp_path / "docs" / "portfolio" / "portfolio-home-business-owner-approval-packet.json"
    )


def test_portfolio_home_scorecard_command_verifier_passes_docs_root_to_artifact_presence_check(
    tmp_path: Path,
) -> None:
    argv = _command_argv(
        "python scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current",
        docs_root=tmp_path / "docs",
    )

    assert argv == [
        sys.executable,
        "scripts/portfolio_home_closure_artifact_presence_check.py",
        "--limit",
        "3",
        "--require-current",
        "--docs-root",
        str(tmp_path / "docs"),
    ]


def test_portfolio_home_scorecard_command_verifier_passes_docs_root_to_evidence_packet_guard(
    tmp_path: Path,
) -> None:
    argv = _command_argv(
        "python scripts/portfolio_home_evidence_packet_guard.py --require-clean",
        docs_root=tmp_path / "docs",
    )

    assert argv == [
        sys.executable,
        "scripts/portfolio_home_evidence_packet_guard.py",
        "--require-clean",
        "--docs-root",
        str(tmp_path / "docs"),
    ]


def test_portfolio_home_scorecard_command_verifier_passes_docs_root_to_handoff_completeness_check(
    tmp_path: Path,
) -> None:
    argv = _command_argv(
        "python scripts/portfolio_home_owner_handoff_completeness_check.py --limit 3 --require-clean",
        docs_root=tmp_path / "docs",
    )

    assert argv == [
        sys.executable,
        "scripts/portfolio_home_owner_handoff_completeness_check.py",
        "--limit",
        "3",
        "--require-clean",
        "--docs-root",
        str(tmp_path / "docs"),
    ]


def test_portfolio_home_scorecard_command_verifier_rejects_non_python_allowlist_command() -> None:
    assert _allowed_argv("python scripts/portfolio_home_closure_scorecard.py --limit 3") == [
        "python",
        "scripts/portfolio_home_closure_scorecard.py",
        "--limit",
        "3",
    ]
    assert _allowed_argv(
        "python -m pytest tests/test_golden_samples_capture_ready.py::test_supporting_only_golden_sample_files_exist_without_capture_ready_claim -q"
    ) == [
        "python",
        "-m",
        "pytest",
        "tests/test_golden_samples_capture_ready.py::test_supporting_only_golden_sample_files_exist_without_capture_ready_claim",
        "-q",
    ]

    try:
        _allowed_argv("cmd /c echo unsafe")
    except ValueError as error:
        assert str(error) == (
            "Portfolio-home verification command must be a controlled python invocation: "
            "cmd /c echo unsafe"
        )
    else:
        raise AssertionError("non-python verification command was accepted")

    try:
        _allowed_argv("python -c print(1)")
    except ValueError as error:
        assert str(error) == (
            "Portfolio-home verification command must target a repo script or pytest regression: "
            "python -c print(1)"
        )
    else:
        raise AssertionError("inline python verification command was accepted")

    try:
        _allowed_argv("python scripts/../tests/test_golden_samples_capture_ready.py")
    except ValueError as error:
        assert str(error) == (
            "Portfolio-home verification script must stay under scripts/ and target a .py file: "
            "python scripts/../tests/test_golden_samples_capture_ready.py"
        )
    else:
        raise AssertionError("escaping scripts path was accepted")

    try:
        _allowed_argv("python scripts/portfolio_home_closure_scorecard.ps1")
    except ValueError as error:
        assert str(error) == (
            "Portfolio-home verification script must stay under scripts/ and target a .py file: "
            "python scripts/portfolio_home_closure_scorecard.ps1"
        )
    else:
        raise AssertionError("non-python script path was accepted")

    for unsafe_command in (
        "python -m pytest -q",
        "python -m pytest tests",
        "python -m pytest tests/../scripts/portfolio_home_closure_scorecard.py::test_name -q",
    ):
        try:
            _allowed_argv(unsafe_command)
        except ValueError as error:
            assert str(error) == (
                "Portfolio-home pytest verification must target a concrete tests/*.py::test_name case: "
                f"{unsafe_command}"
            )
        else:
            raise AssertionError(f"unsafe pytest verification command was accepted: {unsafe_command}")


def test_portfolio_home_scorecard_command_verifier_reports_first_evidence_command() -> None:
    report = build_report(limit=1)

    assert report["verification_status"] == "matched_expected_blocked_state"
    assert report["expected_state"] == "blocked"
    assert report["all_matched_expected_exit"] is True
    assert report["all_matched_expected_when_blocked"] is True
    assert report["result_count"] == 1
    assert report["results"][0]["name"] == "full_closure_evidence"
    assert report["results"][0]["expected_exit"] == "exit_0"
    assert report["results"][0]["returncode"] == 0
    assert "stdout_tail" not in report["results"][0]
    assert "stderr_tail" not in report["results"][0]


def test_portfolio_home_scorecard_command_verifier_passes_docs_root_to_supported_scripts(
    tmp_path: Path,
) -> None:
    assert _command_argv(
        "python scripts/portfolio_home_closure_scorecard.py --limit 3",
        docs_root=tmp_path / "docs",
    ) == [
        sys.executable,
        "scripts/portfolio_home_closure_scorecard.py",
        "--limit",
        "3",
        "--docs-root",
        str(tmp_path / "docs"),
    ]


def test_portfolio_home_scorecard_command_verifier_reports_docs_root(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"

    report = build_report(limit=1, docs_root=docs_root)

    assert report["docs_root"] == str(docs_root)


def test_portfolio_home_scorecard_command_verifier_resolves_relative_docs_root() -> None:
    docs_root = Path("docs")

    expected_docs_root = str((ROOT / docs_root).resolve())
    report = build_report(limit=1, docs_root=docs_root)
    argv = _command_argv(
        "python scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision",
        docs_root=docs_root,
    )

    assert report["docs_root"] == expected_docs_root
    assert argv == [
        sys.executable,
        "scripts/portfolio_home_krd_contract_decision_export.py",
        "--output-dir",
        str(Path(expected_docs_root) / "portfolio" / "krd-contract-decision"),
    ]


def test_portfolio_home_scorecard_command_verifier_isolates_handoff_current_output(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"

    assert _command_argv(
        "python scripts/portfolio_home_owner_handoff_packet.py --limit 3 --check-current",
        docs_root=docs_root,
    ) == [
        sys.executable,
        "scripts/portfolio_home_owner_handoff_packet.py",
        "--limit",
        "3",
        "--check-current",
        "--docs-root",
        str(docs_root),
        "--output",
        str(docs_root / "portfolio" / "portfolio-home-owner-handoff-packet.md"),
    ]


def test_portfolio_home_scorecard_command_verifier_isolates_export_output_dirs(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"

    assert _command_argv(
        "python scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision",
        docs_root=docs_root,
    ) == [
        sys.executable,
        "scripts/portfolio_home_krd_contract_decision_export.py",
        "--output-dir",
        str(docs_root / "portfolio" / "krd-contract-decision"),
    ]

    assert _command_argv(
        "python scripts/portfolio_home_maturity_remediation_export.py --output-dir docs/portfolio/maturity-remediation --require-clean",
        docs_root=docs_root,
    ) == [
        sys.executable,
        "scripts/portfolio_home_maturity_remediation_export.py",
        "--output-dir",
        str(docs_root / "portfolio" / "maturity-remediation"),
        "--require-clean",
    ]

    assert _command_argv(
        "python scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision --check-current",
        docs_root=docs_root,
    ) == [
        sys.executable,
        "scripts/portfolio_home_krd_contract_decision_export.py",
        "--output-dir",
        str(docs_root / "portfolio" / "krd-contract-decision"),
        "--check-current",
    ]

    assert _command_argv(
        "python scripts/portfolio_home_maturity_remediation_export.py --output-dir docs/portfolio/maturity-remediation --check-current",
        docs_root=docs_root,
    ) == [
        sys.executable,
        "scripts/portfolio_home_maturity_remediation_export.py",
        "--output-dir",
        str(docs_root / "portfolio" / "maturity-remediation"),
        "--check-current",
    ]


def test_portfolio_home_scorecard_command_verifier_cli_accepts_docs_root(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--limit",
            "7",
            "--docs-root",
            str(docs_root),
            "--require-matched",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["result_count"] == 7
    assert payload["results"][6]["name"] == "krd_contract_decision_export"
    assert payload["results"][6]["argv"] == [
        sys.executable,
        "scripts/portfolio_home_krd_contract_decision_export.py",
        "--output-dir",
        str(docs_root / "portfolio" / "krd-contract-decision"),
    ]


def test_portfolio_home_scorecard_command_verifier_supports_full_score_expectations() -> None:
    report = build_report(limit=1, expected_state="full_score")

    assert report["verification_status"] == "matched_expected_full_score_state"
    assert report["expected_state"] == "full_score"
    assert report["all_matched_expected_exit"] is True
    assert report["all_matched_expected_when_blocked"] is None
    assert report["results"][0]["expected_when_full_score"] == "exit_0"
    assert report["results"][0]["matches_expected_exit"] is True


def test_portfolio_home_scorecard_command_verifier_cli_require_matched() -> None:
    returncode, payload = _run_verifier("--limit", "1", "--require-matched")

    assert returncode == 0
    assert payload["verification_status"] == "matched_expected_blocked_state"
    assert payload["results"][0]["matches_expected_when_blocked"] is True


def test_portfolio_home_scorecard_command_verifier_rejects_empty_verification_set() -> None:
    report = build_report(limit=0)

    assert report["verification_status"] == "empty_verification_set"
    assert report["all_matched_expected_exit"] is False
    assert report["all_matched_expected_when_blocked"] is False
    assert report["result_count"] == 0
    assert report["results"] == []

    returncode, payload = _run_verifier("--limit", "0", "--require-matched")

    assert returncode == 1
    assert payload["verification_status"] == "empty_verification_set"
    assert payload["all_matched_expected_exit"] is False


def test_portfolio_home_scorecard_command_verifier_rejects_negative_limit() -> None:
    try:
        build_report(limit=-1)
    except ValueError as error:
        assert str(error) == "Portfolio-home verification limit must be non-negative: -1"
    else:
        raise AssertionError("negative verification limit was accepted")

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--limit", "-1", "--require-matched"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 2
    assert "Portfolio-home verification limit must be non-negative: -1" in completed.stderr


def test_portfolio_home_scorecard_command_verifier_full_score_strict_mismatches_current_blocked_state() -> None:
    returncode, payload = _run_verifier(
        "--limit",
        "2",
        "--expected-state",
        "full_score",
        "--require-matched",
    )

    assert returncode == 1
    assert payload["verification_status"] == "mismatch"
    assert payload["results"][1]["name"] == "full_closure_strict"
    assert payload["results"][1]["expected_exit"] == "exit_0"
    assert payload["results"][1]["returncode"] == 1
    assert payload["results"][1]["matches_expected_exit"] is False
    assert "risk_tensor_quality_warning" in payload["results"][1]["stdout_tail"]
    assert payload["results"][1]["stderr_tail"] == ""
