from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.schemas.release_approval import (  # noqa: E402
    ApprovalStateVector,
    canonical_sha256,
)
from scripts.refresh_calculation_p1_owner_decision_snapshot import (  # noqa: E402
    EXPECTED_OPEN_CALCULATION_P1_IDS,
    build_snapshot,
)


def build_status(decision_id: str) -> dict[str, Any]:
    """Read current owner-decision evidence without refreshing or writing snapshots."""

    if decision_id not in EXPECTED_OPEN_CALCULATION_P1_IDS:
        raise ValueError("decision_id is not an open calculation P1 decision")

    snapshot = build_snapshot()
    capture = snapshot["capture_template"]
    matrix_current = not snapshot["drift_errors"]
    captured = (
        matrix_current
        and decision_id in capture["captured_decision_ids"]
        and bool(snapshot["meeting_record"]["is_complete"])
    )
    states = ApprovalStateVector(
        evidence_captured=captured,
        machine_validated=matrix_current,
        business_approved=False,
        formal_use_allowed=False,
        closure_approved=False,
    )
    payload: dict[str, Any] = {
        "schema_version": "calculation-p1-approval-evidence/v1",
        "subject_kind": "calculation_p1",
        "subject_key": decision_id,
        "status": "captured" if captured else ("pending" if matrix_current else "drift"),
        "states": states.model_dump(mode="json"),
        "read_only": True,
        "source_kind": "calculation_p1_owner_decision_snapshot_builder",
    }
    payload["receipt_sha256"] = canonical_sha256(payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check one open calculation P1 owner-decision row without writing files.",
    )
    parser.add_argument(
        "--decision-id",
        required=True,
        choices=EXPECTED_OPEN_CALCULATION_P1_IDS,
    )
    parser.add_argument("--require-captured", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    status = build_status(args.decision_id)
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    if args.require_captured and not status["states"]["evidence_captured"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
