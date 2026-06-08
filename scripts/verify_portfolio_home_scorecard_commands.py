from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.portfolio_home_closure_scorecard import (  # noqa: E402
    VERIFICATION_COMMANDS,
)


def _is_safe_pytest_target(argument: str) -> bool:
    test_path_text = argument.split("::", 1)[0]
    if not test_path_text:
        return False
    test_path = (ROOT / test_path_text).resolve()
    tests_root = (ROOT / "tests").resolve()
    return test_path.suffix == ".py" and test_path.is_relative_to(tests_root)


def _allowed_argv(command: str) -> list[str]:
    argv = command.split()
    if not argv or argv[0] != "python":
        raise ValueError(
            "Portfolio-home verification command must be a controlled python invocation: "
            f"{command}"
        )
    if len(argv) < 2 or not (
        argv[1].startswith("scripts/")
        or (len(argv) >= 3 and argv[1:3] == ["-m", "pytest"])
    ):
        raise ValueError(
            "Portfolio-home verification command must target a repo script or pytest regression: "
            f"{command}"
        )
    if argv[1].startswith("scripts/"):
        script_path = (ROOT / argv[1]).resolve()
        scripts_root = (ROOT / "scripts").resolve()
        if script_path.suffix != ".py" or not script_path.is_relative_to(scripts_root):
            raise ValueError(
                "Portfolio-home verification script must stay under scripts/ and target a .py file: "
                f"{command}"
            )
    if len(argv) >= 3 and argv[1:3] == ["-m", "pytest"]:
        pytest_targets = [argument for argument in argv[3:] if not argument.startswith("-")]
        if (
            len(pytest_targets) != 1
            or "::" not in pytest_targets[0]
            or not _is_safe_pytest_target(pytest_targets[0])
        ):
            raise ValueError(
                "Portfolio-home pytest verification must target a concrete tests/*.py::test_name case: "
                f"{command}"
            )
    return argv


ALLOWED_COMMANDS: dict[str, list[str]] = {
    item["command"]: _allowed_argv(item["command"])
    for item in VERIFICATION_COMMANDS
}
RUNNER_COMMAND_NAME = "verification_command_runner"
OUTPUT_TAIL_CHARS = 4000
HANDOFF_PACKET_SCRIPT = "scripts/portfolio_home_owner_handoff_packet.py"
HANDOFF_PACKET_OUTPUT = Path("portfolio") / "portfolio-home-owner-handoff-packet.md"
OWNER_ACTION_PACKET_SCRIPT = "scripts/portfolio_home_owner_action_packet.py"
OWNER_ACTION_PACKET_OUTPUT = Path("portfolio") / "portfolio-home-owner-action-packet.json"
BUSINESS_OWNER_APPROVAL_PACKET_SCRIPT = (
    "scripts/portfolio_home_business_owner_approval_packet.py"
)
BUSINESS_OWNER_APPROVAL_PACKET_OUTPUT = (
    Path("portfolio") / "portfolio-home-business-owner-approval-packet.json"
)
EVIDENCE_SNAPSHOT_SCRIPT = "scripts/portfolio_home_evidence_snapshot.py"
EVIDENCE_SNAPSHOT_OUTPUT = Path("portfolio") / "portfolio-home-evidence-snapshot.json"
EVIDENCE_SNAPSHOT_ALIGNMENT_SCRIPT = (
    "scripts/portfolio_home_evidence_snapshot_alignment_check.py"
)
OWNER_INPUT_NEEDED_SUMMARY_SCRIPT = "scripts/portfolio_home_owner_input_needed_summary.py"
OWNER_INPUT_NEEDED_SUMMARY_OUTPUT = (
    Path("portfolio") / "portfolio-home-owner-input-needed-summary.json"
)
EXPORT_OUTPUT_DIRS = {
    "scripts/portfolio_home_krd_contract_decision_export.py": (
        Path("portfolio") / "krd-contract-decision"
    ),
    "scripts/portfolio_home_maturity_remediation_export.py": (
        Path("portfolio") / "maturity-remediation"
    ),
}
DOCS_ROOT_AWARE_SCRIPTS = {
    "scripts/portfolio_home_closure_scorecard.py",
    "scripts/portfolio_home_business_owner_approval_packet.py",
    "scripts/portfolio_home_dependency_consistency_check.py",
    "scripts/portfolio_home_evidence_snapshot.py",
    "scripts/portfolio_home_owner_input_needed_summary.py",
    "scripts/portfolio_home_owner_action_packet.py",
    "scripts/portfolio_home_blocker_closure_matrix_check.py",
    "scripts/portfolio_home_closure_artifact_presence_check.py",
    "scripts/portfolio_home_evidence_packet_guard.py",
    "scripts/portfolio_home_owner_decision_intake_check.py",
    "scripts/portfolio_home_owner_handoff_completeness_check.py",
    "scripts/portfolio_home_owner_handoff_packet.py",
    "scripts/portfolio_home_score_blocker_consistency_check.py",
}


def _non_negative_limit(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError(
            f"Portfolio-home verification limit must be non-negative: {parsed}"
        )
    return parsed


def _validated_limit(limit: int | None) -> int | None:
    if limit is not None and limit < 0:
        raise ValueError(
            f"Portfolio-home verification limit must be non-negative: {limit}"
        )
    return limit


def _resolved_docs_root(docs_root: Path | None) -> Path | None:
    if docs_root is None:
        return None
    path = Path(docs_root)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _rewrite_output_dir(argv: list[str], output_dir: Path) -> list[str]:
    try:
        output_dir_index = argv.index("--output-dir") + 1
    except ValueError:
        return argv
    if output_dir_index >= len(argv):
        return argv
    return [
        *argv[:output_dir_index],
        str(output_dir),
        *argv[output_dir_index + 1 :],
    ]


def _rewrite_output(argv: list[str], output: Path) -> list[str]:
    try:
        output_index = argv.index("--output") + 1
    except ValueError:
        return [*argv, "--output", str(output)]
    if output_index >= len(argv):
        return argv
    return [
        *argv[:output_index],
        str(output),
        *argv[output_index + 1 :],
    ]


def _matches_expectation(returncode: int, expectation: str) -> bool:
    if expectation == "exit_0":
        return returncode == 0
    if expectation == "exit_nonzero":
        return returncode != 0
    raise ValueError(f"Unsupported expectation: {expectation}")


def _output_tail(value: str) -> str:
    return value[-OUTPUT_TAIL_CHARS:]


def _command_argv(command: str, *, docs_root: Path | None = None) -> list[str]:
    argv = ALLOWED_COMMANDS.get(command)
    if argv is None:
        raise ValueError(f"Command is not in the portfolio-home verification allowlist: {command}")
    docs_root = _resolved_docs_root(docs_root)
    if argv[0] == "python":
        argv = [sys.executable, *argv[1:]]
    if docs_root is not None and len(argv) > 1 and argv[1] in DOCS_ROOT_AWARE_SCRIPTS:
        argv = [*argv, "--docs-root", str(docs_root)]
        if argv[1] == HANDOFF_PACKET_SCRIPT and "--output" not in argv:
            argv = [*argv, "--output", str(docs_root / HANDOFF_PACKET_OUTPUT)]
        if argv[1] == OWNER_ACTION_PACKET_SCRIPT:
            argv = _rewrite_output(
                argv,
                docs_root / OWNER_ACTION_PACKET_OUTPUT,
            )
        if argv[1] == BUSINESS_OWNER_APPROVAL_PACKET_SCRIPT:
            argv = _rewrite_output(
                argv,
                docs_root / BUSINESS_OWNER_APPROVAL_PACKET_OUTPUT,
            )
        if argv[1] == EVIDENCE_SNAPSHOT_SCRIPT:
            argv = _rewrite_output(
                argv,
                docs_root / EVIDENCE_SNAPSHOT_OUTPUT,
            )
        if argv[1] == OWNER_INPUT_NEEDED_SUMMARY_SCRIPT:
            argv = _rewrite_output(
                argv,
                docs_root / OWNER_INPUT_NEEDED_SUMMARY_OUTPUT,
            )
    if (
        docs_root is not None
        and len(argv) > 1
        and argv[1] == EVIDENCE_SNAPSHOT_ALIGNMENT_SCRIPT
        and "--snapshot" not in argv
    ):
        argv = [*argv, "--snapshot", str(docs_root / EVIDENCE_SNAPSHOT_OUTPUT)]
    if docs_root is not None and len(argv) > 1 and argv[1] in EXPORT_OUTPUT_DIRS:
        argv = _rewrite_output_dir(argv, docs_root / EXPORT_OUTPUT_DIRS[argv[1]])
    return argv


def _run_command(command: str, *, docs_root: Path | None = None) -> subprocess.CompletedProcess[str]:
    argv = _command_argv(command, docs_root=docs_root)
    return subprocess.run(
        argv,
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )


def _expectation_key(expected_state: str) -> str:
    if expected_state == "blocked":
        return "expected_when_blocked"
    if expected_state == "full_score":
        return "expected_when_full_score"
    raise ValueError(f"Unsupported expected state: {expected_state}")


def build_report(
    *,
    limit: int | None = None,
    expected_state: str = "blocked",
    docs_root: Path | None = None,
) -> dict[str, object]:
    limit = _validated_limit(limit)
    docs_root = _resolved_docs_root(docs_root)
    runnable_commands = [
        item for item in VERIFICATION_COMMANDS if item["name"] != RUNNER_COMMAND_NAME
    ]
    commands = runnable_commands[:limit] if limit is not None else runnable_commands
    expectation_key = _expectation_key(expected_state)
    results = []
    for item in commands:
        command = item["command"]
        argv = _command_argv(command, docs_root=docs_root)
        completed = _run_command(command, docs_root=docs_root)
        expected = item[expectation_key]
        matched = _matches_expectation(completed.returncode, expected)
        result = {
            "name": item["name"],
            "kind": item["kind"],
            "command": command,
            "expected_state": expected_state,
            "expected_exit": expected,
            "expected_when_blocked": item["expected_when_blocked"],
            "expected_when_full_score": item["expected_when_full_score"],
            "argv": argv,
            "returncode": completed.returncode,
            "matches_expected_exit": matched,
            "matches_expected_when_blocked": (
                matched if expected_state == "blocked" else None
            ),
        }
        if not matched:
            result["stdout_tail"] = _output_tail(completed.stdout)
            result["stderr_tail"] = _output_tail(completed.stderr)
        results.append(result)
    all_matched = bool(results) and all(bool(item["matches_expected_exit"]) for item in results)
    return {
        "page_id": "PAGE-PORTFOLIO-HOME-001",
        "page_slug": "portfolio",
        "docs_root": str(docs_root) if docs_root is not None else None,
        "expected_state": expected_state,
        "verification_status": (
            f"matched_expected_{expected_state}_state"
            if all_matched
            else "mismatch" if results else "empty_verification_set"
        ),
        "all_matched_expected_exit": all_matched,
        "all_matched_expected_when_blocked": (
            all_matched if expected_state == "blocked" else None
        ),
        "result_count": len(results),
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the portfolio-home scorecard verification command allowlist.",
    )
    parser.add_argument(
        "--limit",
        type=_non_negative_limit,
        default=None,
        help="Run only the first N allowlisted commands. Intended for focused tests.",
    )
    parser.add_argument(
        "--expected-state",
        choices=("blocked", "full_score"),
        default="blocked",
        help="Which scorecard state expectations to compare against.",
    )
    parser.add_argument(
        "--require-matched",
        action="store_true",
        help="Return non-zero unless every command matches the selected expected-state exit.",
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=None,
        help="Optional docs root used when running docs-root-aware verification commands.",
    )
    args = parser.parse_args(argv)

    report = build_report(
        limit=args.limit,
        expected_state=args.expected_state,
        docs_root=args.docs_root,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_matched and not report["all_matched_expected_exit"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
