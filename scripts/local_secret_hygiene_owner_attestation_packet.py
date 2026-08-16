from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


AUDIT_DATE = "2026-06-10"
DEFAULT_SNAPSHOT = (
    ROOT / "docs" / "audits" / f"{AUDIT_DATE}-local-secret-hygiene-snapshot.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "docs"
    / "audits"
    / f"{AUDIT_DATE}-local-secret-hygiene-owner-attestation-packet.md"
)

ATTESTATION_OPTIONS = [
    "rotated",
    "removed",
    "accepted-local-only",
    "deferred",
]
REQUIRED_ATTESTATION_FIELDS = [
    "environment_owner",
    "security_owner",
    "decision",
    "decision_date",
    "external_evidence_reference",
    "clean_runner_or_acceptance_result",
]
EVIDENCE_SCOPE = {
    "read_only": True,
    "reads_secret_values": False,
    "requests_secret_values": False,
    "captures_secret_values": False,
    "writes_or_rotates_secrets": False,
    "clears_secret_scan": False,
    "approves_deployment": False,
    "approves_local_secret_hygiene": False,
}
PROHIBITED_ACTIONS = [
    "read or paste config/.env values",
    "copy credential values into this packet",
    "commit config/.env or any credential value",
    "weaken gitleaks rules to make local findings disappear",
    "treat this attestation packet as security-owner approval",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_packet(*, snapshot_path: Path = DEFAULT_SNAPSHOT) -> dict[str, Any]:
    snapshot = _load_json(Path(snapshot_path))
    latest = snapshot.get("latest_boundary_only_recheck") or {}
    boundary = latest.get("boundary_checks") or {}
    ignored_status = (boundary.get("git_status_ignored") or {}).get("result")
    detected_names = list(snapshot.get("detected_secret_names") or [])

    return {
        "packet_kind": "local_secret_hygiene_owner_attestation_packet",
        "audit_date": AUDIT_DATE,
        "source_artifacts": {
            "local_secret_hygiene_snapshot": (
                f"docs/audits/{AUDIT_DATE}-local-secret-hygiene-snapshot.json"
            ),
            "local_secret_hygiene_runbook": (
                f"docs/audits/{AUDIT_DATE}-local-secret-hygiene-runbook.md"
            ),
            "owner_governance_follow_up_packet": (
                f"docs/audits/{AUDIT_DATE}-owner-governance-follow-up-packet.json"
            ),
        },
        "source_snapshot_generated_at": snapshot.get("generated_at"),
        "source_snapshot_status": snapshot.get("status", {}).get("overall"),
        "latest_boundary_only_recheck_at": latest.get("checked_at"),
        "owner_attestation_ready": bool(detected_names)
        and snapshot.get("value_handling", {}).get("names_only_recorded") is True,
        "closure_approved": False,
        "secret_value_fields_present": False,
        "detected_secret_names": detected_names,
        "attestation_options": list(ATTESTATION_OPTIONS),
        "required_attestation_fields": list(REQUIRED_ATTESTATION_FIELDS),
        "attestation_template": {
            "environment_owner": "",
            "security_owner": "",
            "decision": "",
            "decision_date": "",
            "external_evidence_reference": "",
            "clean_runner_or_acceptance_result": "",
            "notes_without_values": "",
        },
        "current_boundary_evidence": {
            "config_env_exists": boundary.get("config_env_exists"),
            "git_check_ignore_matched_rule": (
                (boundary.get("git_check_ignore") or {}).get("matched_rule")
            ),
            "git_ls_files_tracked_path_count": (
                (boundary.get("git_ls_files") or {}).get("tracked_path_count")
            ),
            "git_status_ignored_result": ignored_status,
            "gitleaks_redaction_enabled": (
                (latest.get("dry_run_plan") or {}).get("gitleaks_redaction_enabled")
            ),
        },
        "current_blockers": [
            "ignored config/.env finding remains",
            "owner attestation not captured",
            "clean-runner or accepted-local-only result not captured",
        ],
        "post_attestation_verification": [
            "rerun value-free boundary check",
            "rerun redacted gitleaks or attach accepted local-only finding record without values",
            "verify no secret values enter source control, docs, tests, logs, screenshots, commits, or chat",
            "rerun system audit monitoring and strict gate matrix",
        ],
        "evidence_scope": dict(EVIDENCE_SCOPE),
        "prohibited_actions": list(PROHIBITED_ACTIONS),
        "boundary": (
            "This packet is value-free owner-attestation intake. It does not read, "
            "request, capture, rotate, clear, or approve any secret value; it only "
            "names the local findings and the fields required from environment and "
            "security owners."
        ),
    }


def _bool_text(value: bool) -> str:
    return str(value).lower()


def _join_backtick(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "none"


def render_markdown(packet: dict[str, Any]) -> str:
    source_rows = "\n".join(
        f"- `{key}`: `{value}`" for key, value in packet["source_artifacts"].items()
    )
    scope_rows = "\n".join(
        f"- `{key}={_bool_text(value) if isinstance(value, bool) else value}`"
        for key, value in packet["evidence_scope"].items()
    )
    blocker_rows = "\n".join(f"- {item}" for item in packet["current_blockers"])
    verification_rows = "\n".join(
        f"- {item}" for item in packet["post_attestation_verification"]
    )
    prohibited_rows = "\n".join(f"- {item}" for item in packet["prohibited_actions"])
    template_rows = "\n".join(
        f"| `{key}` | `{value}` |" for key, value in packet["attestation_template"].items()
    )
    boundary = packet["current_boundary_evidence"]

    return f"""# Local Secret Hygiene Owner Attestation Packet

Source snapshot status: `source_snapshot_status={packet['source_snapshot_status']}`
Owner attestation ready: `{_bool_text(packet['owner_attestation_ready'])}`
Closure approved: `{_bool_text(packet['closure_approved'])}`
Secret value fields present: `secret_value_fields_present={_bool_text(packet['secret_value_fields_present'])}`

This packet prepares the local secret hygiene owner handoff without reading, requesting, or storing credential values.

## Summary

- Detected secret names only: {_join_backtick(packet['detected_secret_names'])}
- Allowed owner decisions: {_join_backtick(packet['attestation_options'])}
- Required attestation fields: {_join_backtick(packet['required_attestation_fields'])}
- Latest boundary-only recheck: `{packet['latest_boundary_only_recheck_at']}`

## Source Artifacts

{source_rows}

## Current Boundary Evidence

- `config_env_exists={_bool_text(bool(boundary['config_env_exists']))}`
- `git_check_ignore_matched_rule={boundary['git_check_ignore_matched_rule']}`
- `git_ls_files_tracked_path_count={boundary['git_ls_files_tracked_path_count']}`
- `git_status_ignored_result={boundary['git_status_ignored_result']}`
- `gitleaks_redaction_enabled={_bool_text(bool(boundary['gitleaks_redaction_enabled']))}`

## Owner Attestation Template

| Field | Value |
| --- | --- |
{template_rows}

## Current Blockers

{blocker_rows}

## Post-Attestation Verification

{verification_rows}

## Evidence Scope

{scope_rows}

## Prohibited Actions

- Do not read or paste `config/.env` values.
{prohibited_rows}

## Boundary

{packet['boundary']}
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a value-free local secret hygiene owner attestation packet."
        )
    )
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    packet = build_packet(snapshot_path=args.snapshot)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(packet), encoding="utf-8")
    payload = {
        "packet_kind": packet["packet_kind"],
        "packet_path": str(output_path),
        "source_snapshot_status": packet["source_snapshot_status"],
        "owner_attestation_ready": packet["owner_attestation_ready"],
        "closure_approved": packet["closure_approved"],
        "secret_value_fields_present": packet["secret_value_fields_present"],
        "detected_secret_names": packet["detected_secret_names"],
        "evidence_scope": packet["evidence_scope"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
