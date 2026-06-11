from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.refresh_calculation_p1_owner_decision_snapshot import (  # noqa: E402
    build_snapshot as build_calculation_snapshot,
)
from scripts.refresh_direct_app_mcp_gitnexus_tool_surface_snapshot import (  # noqa: E402
    EXPECTED_DIRECT_SERVERS,
    build_snapshot as build_direct_tool_snapshot,
)
from scripts.refresh_ledger_pnl_direct_governance_record_snapshot import (  # noqa: E402
    build_snapshot as build_ledger_snapshot,
)
from scripts.refresh_local_secret_hygiene_snapshot import (  # noqa: E402
    build_snapshot as build_secret_snapshot,
)
from scripts.system_audit_pulse import build_pulse  # noqa: E402
from scripts.verify_system_audit_completion_snapshot import (  # noqa: E402
    verify_completion_snapshot,
)
from scripts.verify_system_audit_monitoring_snapshot import (  # noqa: E402
    verify_monitoring_snapshot,
)


DEFAULT_MANIFEST = ROOT / "docs" / "audits" / "2026-06-10-system-audit-manifest.json"


def _default_generated_at() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _gate(
    *,
    gate_id: str,
    command: str,
    strict_pass: bool,
    expected_current_exit: str,
    actual_current_exit: str,
    blocker_id: str,
    blocking_detail: str,
    boundary: str,
) -> dict[str, Any]:
    expectation_met = actual_current_exit == expected_current_exit
    return {
        "gate_id": gate_id,
        "command": command,
        "strict_pass": strict_pass,
        "expected_current_exit": expected_current_exit,
        "actual_current_exit": actual_current_exit,
        "expectation_met": expectation_met,
        "blocker_id": blocker_id,
        "blocking_detail": blocking_detail,
        "boundary": boundary,
    }


def build_matrix_from_inputs(
    *,
    generated_at: str,
    manifest_path: Path,
    pulse: dict[str, Any],
    completion: dict[str, Any],
    monitoring: dict[str, Any],
    calculation: dict[str, Any],
    ledger: dict[str, Any],
    direct: dict[str, Any],
    secret: dict[str, Any],
) -> dict[str, Any]:
    calculation_capture = calculation["capture_template"]
    ledger_dry_run = ledger["dry_run_result"]
    direct_status = direct["status"]
    secret_latest = secret["latest_boundary_only_recheck"]
    secret_status = secret["status"]
    secret_ignored_status = secret_latest["boundary_checks"]["git_status_ignored"][
        "result"
    ]
    completion_order_guard_status = completion.get(
        "follow_up_completion_order_status"
    )
    completion_order_guard_error_count = completion.get(
        "follow_up_completion_order_error_count"
    )
    guard_errors = []
    if completion_order_guard_status != "pass":
        guard_errors.append(
            "completion order guard status expected 'pass', "
            f"got {completion_order_guard_status!r}"
        )
    if completion_order_guard_error_count != 0:
        guard_errors.append(
            "completion order guard error count expected 0, "
            f"got {completion_order_guard_error_count!r}"
        )

    gates = [
        _gate(
            gate_id="system-audit-full-score",
            command="python scripts\\system_audit_pulse.py --require-full-score-ready",
            strict_pass=bool(pulse["full_score_ready"]),
            expected_current_exit="non_zero",
            actual_current_exit="zero" if pulse["full_score_ready"] else "non_zero",
            blocker_id="system-audit-open-blockers",
            blocking_detail=(
                f"completion_state={pulse['completion_state']}; "
                f"open_blocker_count={pulse['open_blocker_count']}"
            ),
            boundary="This gate does not approve metrics, pages, records, secrets, or routes.",
        ),
        _gate(
            gate_id="completion-zero-open-blockers",
            command="python scripts\\verify_system_audit_completion_snapshot.py --require-complete",
            strict_pass=completion["status"] == "pass"
            and completion["open_blocker_count"] == 0,
            expected_current_exit="non_zero",
            actual_current_exit=(
                "zero"
                if completion["status"] == "pass"
                and completion["open_blocker_count"] == 0
                else "non_zero"
            ),
            blocker_id="system-audit-open-blockers",
            blocking_detail=(
                f"open_blocker_count={completion['open_blocker_count']}; "
                f"completion_gate_count={completion['completion_gate_count']}"
            ),
            boundary="This gate verifies zero open blockers; it does not close them.",
        ),
        _gate(
            gate_id="monitoring-zero-open-blockers",
            command="python scripts\\verify_system_audit_monitoring_snapshot.py --require-complete",
            strict_pass=monitoring["status"] == "pass"
            and monitoring["open_blocker_count"] == 0
            and monitoring["pulse_completion_state"] == "ready_for_completion_audit",
            expected_current_exit="non_zero",
            actual_current_exit=(
                "zero"
                if monitoring["status"] == "pass"
                and monitoring["open_blocker_count"] == 0
                and monitoring["pulse_completion_state"] == "ready_for_completion_audit"
                else "non_zero"
            ),
            blocker_id="system-audit-open-blockers",
            blocking_detail=(
                f"open_blocker_count={monitoring['open_blocker_count']}; "
                f"pulse_completion_state={monitoring['pulse_completion_state']}"
            ),
            boundary="This gate verifies monitoring alignment; it does not approve blockers.",
        ),
        _gate(
            gate_id="calculation-p1-owner-decisions-captured",
            command=(
                "python scripts\\refresh_calculation_p1_owner_decision_snapshot.py "
                "--require-owner-decisions-captured"
            ),
            strict_pass=calculation_capture["captured_decision_count"]
            == calculation_capture["row_count"],
            expected_current_exit="non_zero",
            actual_current_exit=(
                "zero"
                if calculation_capture["captured_decision_count"]
                == calculation_capture["row_count"]
                else "non_zero"
            ),
            blocker_id="calculation-display-p1-decisions",
            blocking_detail=(
                f"captured_decision_count={calculation_capture['captured_decision_count']}; "
                f"row_count={calculation_capture['row_count']}; "
                f"pending_count={calculation_capture['pending_count']}"
            ),
            boundary="This gate does not choose or approve calculation conventions.",
        ),
        _gate(
            gate_id="ledger-pnl-written-record-located",
            command=(
                "python scripts\\refresh_ledger_pnl_direct_governance_record_snapshot.py "
                "--require-written-record-located"
            ),
            strict_pass=ledger["status"]["overall"] == "written_record_located",
            expected_current_exit="non_zero",
            actual_current_exit=(
                "zero"
                if ledger["status"]["overall"] == "written_record_located"
                else "non_zero"
            ),
            blocker_id="ledger-pnl-direct-governance-record",
            blocking_detail=(
                f"status={ledger['status']['overall']}; "
                f"record_write_status={ledger_dry_run['record_write_status']}; "
                f"existing_record_line={ledger_dry_run['existing_record_line']}"
            ),
            boundary="This gate locates a record only; it never authorizes or writes one.",
        ),
        _gate(
            gate_id="direct-app-mcp-gitnexus-evidence-captured",
            command=(
                "python scripts\\refresh_direct_app_mcp_gitnexus_tool_surface_snapshot.py "
                "--require-direct-evidence-captured"
            ),
            strict_pass=not direct["missing_direct_servers"]
            and direct_status["direct_app_mcp_evidence_captured"]
            and direct_status["direct_gitnexus_evidence_captured"],
            expected_current_exit="non_zero",
            actual_current_exit=(
                "zero"
                if not direct["missing_direct_servers"]
                and direct_status["direct_app_mcp_evidence_captured"]
                and direct_status["direct_gitnexus_evidence_captured"]
                else "non_zero"
            ),
            blocker_id="direct-app-mcp-gitnexus-evidence",
            blocking_detail=(
                "missing_direct_servers="
                f"{direct['missing_direct_servers'] or []}; "
                f"expected_direct_servers={list(EXPECTED_DIRECT_SERVERS)}"
            ),
            boundary="This gate does not treat local stdio evidence as direct App closure.",
        ),
        _gate(
            gate_id="local-secret-hygiene-clean-boundary",
            command=(
                "python scripts\\refresh_local_secret_hygiene_snapshot.py "
                "--require-clean-boundary"
            ),
            strict_pass=not secret_latest["secret_values_captured"]
            and not secret_status["secret_values_captured"]
            and not secret_status["clears_secret_scan"]
            and not bool(secret_ignored_status),
            expected_current_exit="non_zero",
            actual_current_exit=(
                "zero"
                if not secret_latest["secret_values_captured"]
                and not secret_status["secret_values_captured"]
                and not secret_status["clears_secret_scan"]
                and not bool(secret_ignored_status)
                else "non_zero"
            ),
            blocker_id="local-secret-hygiene",
            blocking_detail=(
                f"ignored_status={secret_ignored_status!r}; "
                f"secret_values_captured={secret_status['secret_values_captured']}; "
                f"clears_secret_scan={secret_status['clears_secret_scan']}"
            ),
            boundary="This gate is value-free and does not read, rotate, or clear secrets.",
        ),
    ]

    unexpected = [gate for gate in gates if not gate["expectation_met"]]
    strict_passes = [gate for gate in gates if gate["strict_pass"]]
    return {
        "report_kind": "system_audit_strict_gate_matrix",
        "generated_at": generated_at,
        "repo_root": str(ROOT),
        "manifest_path": str(manifest_path),
        "status": "pass" if not unexpected and not guard_errors else "fail",
        "completion_state": pulse["completion_state"],
        "full_score_ready": pulse["full_score_ready"],
        "open_blocker_count": pulse["open_blocker_count"],
        "completion_order_guard_status": completion_order_guard_status,
        "completion_order_guard_error_count": completion_order_guard_error_count,
        "gate_count": len(gates),
        "expected_blocked_gate_count": sum(
            1 for gate in gates if gate["expected_current_exit"] == "non_zero"
        ),
        "strict_pass_gate_count": len(strict_passes),
        "unexpected_gate_count": len(unexpected),
        "guard_error_count": len(guard_errors),
        "guard_errors": guard_errors,
        "gates": gates,
        "boundary": (
            "This matrix is read-only. It reports strict-gate expectations and current "
            "blocked status; it does not approve owner decisions, pages, metrics, "
            "governance writes, direct App evidence, secret hygiene, or route certification."
        ),
    }


def build_matrix(
    *,
    generated_at: str | None = None,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    generated_at = generated_at or _default_generated_at()
    pulse = build_pulse(manifest_path=manifest_path, generated_at=generated_at)
    completion = verify_completion_snapshot(manifest_path=manifest_path)
    monitoring = verify_monitoring_snapshot(manifest_path=manifest_path)
    calculation = build_calculation_snapshot(generated_at=generated_at)
    ledger = build_ledger_snapshot(generated_at=generated_at, record_created_at=generated_at)
    direct = build_direct_tool_snapshot(generated_at=generated_at)
    secret = build_secret_snapshot(generated_at=generated_at)

    return build_matrix_from_inputs(
        generated_at=generated_at,
        manifest_path=manifest_path,
        pulse=pulse,
        completion=completion,
        monitoring=monitoring,
        calculation=calculation,
        ledger=ledger,
        direct=direct,
        secret=secret,
    )


def format_markdown_matrix(report: dict[str, Any]) -> str:
    lines = [
        "# System Audit Strict Gate Matrix",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Status: `{report['status']}`",
        f"- Completion state: `{report['completion_state']}`",
        f"- Full score ready: `{str(report['full_score_ready']).lower()}`",
        f"- Open blockers: `{report['open_blocker_count']}`",
        f"- Strict pass gates: `{report['strict_pass_gate_count']}/{report['gate_count']}`",
        (
            "- Completion order guard: "
            f"`{report['completion_order_guard_status']}` "
            f"(errors `{report['completion_order_guard_error_count']}`)"
        ),
        "",
        "| Gate | Expected Now | Actual Now | Blocker | Detail |",
        "| --- | --- | --- | --- | --- |",
    ]
    for gate in report["gates"]:
        lines.append(
            "| "
            f"`{gate['gate_id']}` | "
            f"`{gate['expected_current_exit']}` | "
            f"`{gate['actual_current_exit']}` | "
            f"`{gate['blocker_id']}` | "
            f"{gate['blocking_detail']} |"
        )
    if report["guard_errors"]:
        lines.extend(["", "## Guard Errors", ""])
        lines.extend(f"- `{error}`" for error in report["guard_errors"])
    lines.extend(["", "## Boundary", "", report["boundary"], ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a read-only matrix of system audit strict gates.",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument(
        "--require-all-expected",
        action="store_true",
        help="Exit non-zero when any strict gate does not match its expected current exit.",
    )
    args = parser.parse_args(argv)

    report = build_matrix(
        generated_at=args.generated_at,
        manifest_path=args.manifest,
    )
    payload = (
        format_markdown_matrix(report)
        if args.format == "markdown"
        else json.dumps(report, ensure_ascii=False, indent=2)
    )
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if args.require_all_expected and report["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
