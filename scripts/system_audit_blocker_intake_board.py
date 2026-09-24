from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "docs" / "audits" / "2026-06-10-system-audit-manifest.json"

EVIDENCE_SCOPE = {
    "read_only": True,
    "approves_metrics": False,
    "approves_pages": False,
    "captures_business_owner_approval": False,
    "writes_governance_records": False,
    "authorizes_ledger_pnl_governance_write": False,
    "captures_direct_app_mcp_gitnexus_evidence": False,
    "requests_or_captures_secret_values": False,
    "clears_secret_scan": False,
    "certifies_routes": False,
}

STRICT_GATE_BY_BLOCKER = {
    "owner-approval-7-pages": "python scripts\\check_*_business_owner_approval.py --require-captured",
    "ledger-pnl-direct-governance-record": (
        "python scripts\\refresh_ledger_pnl_direct_governance_record_snapshot.py "
        "--require-written-record-located"
    ),
    "calculation-display-p1-decisions": (
        "python scripts\\refresh_calculation_p1_owner_decision_snapshot.py "
        "--require-owner-decisions-captured"
    ),
    "direct-app-mcp-gitnexus-evidence": (
        "python scripts\\refresh_direct_app_mcp_gitnexus_tool_surface_snapshot.py "
        "--require-direct-evidence-captured"
    ),
    "local-secret-hygiene": (
        "python scripts\\refresh_local_secret_hygiene_snapshot.py "
        "--require-clean-boundary"
    ),
}


def _default_generated_at() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(repo_root: Path, path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else repo_root / path


def _first(items: Any) -> str | None:
    return items[0] if isinstance(items, list) and items else None


def build_board(
    *,
    generated_at: str | None = None,
    manifest_path: Path = DEFAULT_MANIFEST,
    repo_root: Path = ROOT,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    packet_path = _resolve(
        repo_root,
        manifest["artifacts"]["owner_governance_follow_up_packet"],
    )
    packet = _load_json(packet_path)

    blockers_by_id = {item["id"]: item for item in manifest["open_blockers"]}
    packet_by_id = {item["blocker_id"]: item for item in packet["blocker_packets"]}
    completion_order = list(packet["completion_order"])
    rows: list[dict[str, Any]] = []
    for index, blocker_id in enumerate(completion_order, start=1):
        blocker = blockers_by_id[blocker_id]
        follow_up = packet_by_id[blocker_id]
        external_inputs = list(follow_up.get("external_input_required_for_closure") or [])
        required_outputs = list(
            follow_up.get("required_meeting_or_governance_output") or []
        )
        prohibited_actions = list(follow_up.get("prohibited_actions") or [])
        rows.append(
            {
                "sequence": index,
                "blocker_id": blocker_id,
                "severity": blocker.get("severity"),
                "manifest_status": blocker.get("status"),
                "current_status": follow_up.get("current_status"),
                "last_checked_at": blocker.get("last_checked_at"),
                "responsible_owner_type": follow_up.get("responsible_owner_type"),
                "strict_gate_command": STRICT_GATE_BY_BLOCKER.get(blocker_id),
                "required_input_artifacts": list(
                    follow_up.get("required_input_artifacts") or []
                ),
                "required_external_input_count": len(external_inputs),
                "first_required_external_input": _first(external_inputs),
                "required_output_count": len(required_outputs),
                "first_required_output": _first(required_outputs),
                "prohibited_action_count": len(prohibited_actions),
                "first_prohibited_action": _first(prohibited_actions),
                "authorization_required_commands_not_preapproved": list(
                    follow_up.get("authorization_required_commands_not_preapproved") or []
                ),
                "fail_closed_until": follow_up.get("fail_closed_until"),
                "explicit_non_approval_boundary": follow_up.get(
                    "explicit_non_approval_boundary"
                ),
            }
        )

    return {
        "report_kind": "system_audit_blocker_intake_board",
        "generated_at": generated_at or _default_generated_at(),
        "repo_root": str(repo_root),
        "manifest_path": str(manifest_path),
        "follow_up_packet_path": str(packet_path),
        "status": "open_external_input_required" if rows else "no_open_blockers",
        "blocker_count": len(rows),
        "completion_order": completion_order,
        "next_blocker_id": rows[0]["blocker_id"] if rows else None,
        "evidence_scope": dict(EVIDENCE_SCOPE),
        "blockers": rows,
        "boundary": (
            "This blocker intake board is read-only. It does not approve metrics, pages, "
            "business-owner signoff, governance records, route certification, direct App "
            "MCP/GitNexus evidence, local secret hygiene, or Ledger PnL --write execution."
        ),
    }


def format_markdown_board(report: dict[str, Any]) -> str:
    lines = [
        "# System Audit Blocker Intake Board",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Status: `{report['status']}`",
        f"- Open blockers: `{report['blocker_count']}`",
        f"- Next blocker: `{report['next_blocker_id']}`",
        "",
        "| Seq | Blocker | Owner | Strict Gate | First External Input |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in report["blockers"]:
        lines.append(
            "| "
            f"{item['sequence']} | "
            f"`{item['blocker_id']}` | "
            f"`{item['responsible_owner_type']}` | "
            f"`{item['strict_gate_command']}` | "
            f"{item['first_required_external_input']} |"
        )
    lines.extend(["", "## Boundary", "", report["boundary"], ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a read-only intake board for the open system audit blockers.",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    report = build_board(
        generated_at=args.generated_at,
        manifest_path=args.manifest,
    )
    payload = (
        format_markdown_board(report)
        if args.format == "markdown"
        else json.dumps(report, ensure_ascii=False, indent=2)
    )
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
