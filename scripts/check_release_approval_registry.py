from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.governance.release_approval import (  # noqa: E402
    DEFAULT_REGISTRY_PATH,
    execute_registry_evidence,
    load_release_approval_registry,
    validate_registry_structure,
)
from backend.app.schemas.release_approval import canonical_sha256  # noqa: E402
from scripts.verify_system_audit_completion_snapshot import (  # noqa: E402
    EXPECTED_OPEN_CALCULATION_P1_IDS,
)


def _live_page_checker_paths() -> tuple[str, ...]:
    scripts_dir = ROOT / "scripts"
    return tuple(
        sorted(
            path.relative_to(ROOT).as_posix()
            for path in scripts_dir.glob("check_*_business_owner_approval.py")
        )
    )


def build_report(*, execute_evidence: bool = False) -> dict[str, Any]:
    registry = load_release_approval_registry(DEFAULT_REGISTRY_PATH)
    reasons = list(
        validate_registry_structure(
            registry,
            repo_root=ROOT,
            expected_page_scripts=_live_page_checker_paths(),
            expected_calculation_ids=EXPECTED_OPEN_CALCULATION_P1_IDS,
        )
    )
    evidence_captured_count: int | None = None
    if execute_evidence and not reasons:
        evidence = execute_registry_evidence(registry, repo_root=ROOT)
        evidence_captured_count = sum(
            1 for status in evidence if status.states.evidence_captured
        )
        if evidence_captured_count != len(registry.entries):
            reasons.append("approval_evidence_not_fully_captured")

    page_count = sum(1 for entry in registry.entries if entry.subject_kind == "page")
    calculation_count = sum(
        1 for entry in registry.entries if entry.subject_kind == "calculation_p1"
    )
    payload: dict[str, Any] = {
        "schema_version": "release-approval-registry-check/v1",
        "status": "structure_passed" if not reasons else "blocked",
        "reason_codes": list(dict.fromkeys(reasons)),
        "registry_sha256": registry.registry_sha256,
        "entry_count": len(registry.entries),
        "page_checker_count": page_count,
        "calculation_p1_count": calculation_count,
        "pending_authority_policy_count": sum(
            1 for entry in registry.entries if entry.authority_policy_id == "PENDING"
        ),
        "pending_scope_mapping_count": sum(
            1 for entry in registry.entries if entry.scope_mapping.status == "PENDING"
        ),
        "structure_only": not execute_evidence,
        "gate_scope": "structure_only" if not execute_evidence else "evidence_only",
        "approval_decision": "not_evaluated",
        "fail_closed_for_release_approval": True,
        "release_gate_eligible": False,
        "operational_approval_ready": (
            not reasons
            and all(entry.authority_policy_id != "PENDING" for entry in registry.entries)
            and all(entry.scope_mapping.status == "mapped" for entry in registry.entries)
        ),
        "evidence_captured_count": evidence_captured_count,
    }
    payload["receipt_sha256"] = canonical_sha256(payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the fixed release approval registry and optional evidence gates.",
    )
    parser.add_argument("--execute-evidence", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_report(execute_evidence=args.execute_evidence)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "structure_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
