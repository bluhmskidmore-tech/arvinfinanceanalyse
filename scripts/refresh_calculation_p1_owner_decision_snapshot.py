from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_system_audit_completion_snapshot import (  # noqa: E402
    EXPECTED_OPEN_CALCULATION_P1_IDS,
)


AUDIT_DATE = "2026-06-10"
DEFAULT_MATRIX = (
    ROOT / "docs" / "audits" / f"{AUDIT_DATE}-calculation-p1-owner-decision-matrix.md"
)
DEFAULT_CAPTURE_TEMPLATE = (
    ROOT / "docs" / "audits" / f"{AUDIT_DATE}-owner-decision-capture-template.zh.md"
)
DEFAULT_OUTPUT = (
    ROOT / "docs" / "audits" / f"{AUDIT_DATE}-calculation-p1-owner-decision-snapshot.json"
)
REFRESH_COMMAND = "python scripts\\refresh_calculation_p1_owner_decision_snapshot.py"
P1_ROW_RE = re.compile(r"^\|\s*(P1-\d{2})\s*\|")
PREWORK_RE = re.compile(r"^-\s+\*\*(P1-\d{2})\b")
TIMESTAMP_RE = re.compile(r"Refreshed at `([^`]+)`")
P108_TEST_RE = re.compile(r"`(npm\.cmd test -- [^`]+)` was rerun at `([^`]+)`")


def _now_shanghai() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def _section(text: str, start_marker: str, end_marker: str | None = None) -> str:
    if start_marker not in text:
        return ""
    section = text.split(start_marker, maxsplit=1)[1]
    if end_marker is not None and end_marker in section:
        section = section.split(end_marker, maxsplit=1)[0]
    return section


def _markdown_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _decision_rows(section: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in section.splitlines():
        match = P1_ROW_RE.match(line)
        if match is None:
            continue
        cells = _markdown_cells(line)
        rows.append(
            {
                "id": cells[0],
                "cells": cells,
                "raw": line,
            }
        )
    return rows


def _capture_rows(section: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in section.splitlines():
        match = P1_ROW_RE.match(line)
        if match is None:
            continue
        cells = _markdown_cells(line)
        rows.append(
            {
                "id": cells[0],
                "decision_topic": cells[1] if len(cells) > 1 else "",
                "selected_decision": cells[2] if len(cells) > 2 else "",
                "owner_rationale": cells[3] if len(cells) > 3 else "",
                "implementation_owner": cells[4] if len(cells) > 4 else "",
                "verification_gate": cells[5] if len(cells) > 5 else "",
                "status": cells[6] if len(cells) > 6 else "",
                "raw": line,
            }
        )
    return rows


def _prework_ids(prework_section: str) -> list[str]:
    ids: list[str] = []
    for line in prework_section.splitlines():
        match = PREWORK_RE.match(line)
        if match is not None:
            ids.append(match.group(1))
    return ids


def _timestamp(text: str) -> str | None:
    match = TIMESTAMP_RE.search(text)
    return match.group(1) if match else None


def _p108_test_evidence(text: str) -> dict[str, str | None]:
    match = P108_TEST_RE.search(text)
    return {
        "command": match.group(1) if match else None,
        "rerun_at": match.group(2) if match else None,
    }


def _missing_ids(actual_ids: list[str]) -> list[str]:
    actual = set(actual_ids)
    return [p1_id for p1_id in EXPECTED_OPEN_CALCULATION_P1_IDS if p1_id not in actual]


def _unexpected_ids(actual_ids: list[str]) -> list[str]:
    expected = set(EXPECTED_OPEN_CALCULATION_P1_IDS)
    return [p1_id for p1_id in actual_ids if p1_id not in expected]


def build_snapshot(
    *,
    generated_at: str | None = None,
    matrix_path: Path = DEFAULT_MATRIX,
    capture_template_path: Path = DEFAULT_CAPTURE_TEMPLATE,
) -> dict[str, Any]:
    generated_at = generated_at or _now_shanghai()
    matrix_text = Path(matrix_path).read_text(encoding="utf-8")
    capture_text = Path(capture_template_path).read_text(encoding="utf-8")

    decision_section = _section(
        matrix_text,
        "## Decision Matrix",
        "## Suggested Review Order",
    )
    verified_closed_section = _section(
        matrix_text,
        "## Verified Closed Before Owner Review",
        "## Engineering Prework / Impact Slice Map",
    )
    prework_section = _section(
        matrix_text,
        "## Engineering Prework / Impact Slice Map",
    )
    capture_section = _section(
        capture_text,
        "## 10",
        "## 7",
    )

    open_rows = _decision_rows(decision_section)
    open_ids = [row["id"] for row in open_rows]
    verified_closed_rows = _decision_rows(verified_closed_section)
    verified_closed_ids = [row["id"] for row in verified_closed_rows]
    prework_ids = _prework_ids(prework_section)
    capture_rows = _capture_rows(capture_section)
    capture_ids = [row["id"] for row in capture_rows]
    captured_decision_rows = [
        row
        for row in capture_rows
        if row["selected_decision"]
        or row["owner_rationale"]
        or row["implementation_owner"]
        or row["status"] not in {"", "pending"}
    ]

    boundary_checks = {
        "does_not_choose_or_approve_convention": (
            "does not choose or approve any convention" in prework_section
        ),
        "does_not_change_code": "does not change code" in prework_section,
        "does_not_certify_routes_pages": "does not certify routes/pages" in prework_section,
        "matrix_non_approval_boundary": "This matrix does not approve any calculation convention."
        in matrix_text,
        "capture_template_non_approval_boundary": "不批准任何计算口径" in capture_text
        or "涓嶆壒鍑嗕换浣曡绠楀彛寰" in capture_text,
    }

    drift_errors: list[str] = []
    if open_ids != EXPECTED_OPEN_CALCULATION_P1_IDS:
        drift_errors.append("open P1 decision IDs do not match the expected order")
    if "P1-08" in open_ids:
        drift_errors.append("P1-08 appears in open owner-decision rows")
    if "P1-08" not in verified_closed_ids:
        drift_errors.append("P1-08 verified-closed row is missing")
    if _missing_ids(prework_ids):
        drift_errors.append("engineering prework map is missing open P1 IDs")
    if _unexpected_ids(prework_ids):
        drift_errors.append("engineering prework map contains unexpected P1 IDs")
    if capture_ids != EXPECTED_OPEN_CALCULATION_P1_IDS:
        drift_errors.append("owner decision capture template P1 IDs do not match the expected order")
    for name, passed in boundary_checks.items():
        if not passed:
            drift_errors.append(f"boundary check failed: {name}")

    return {
        "report_kind": "calculation_p1_owner_decision_snapshot",
        "generated_at": generated_at,
        "repo_root": str(ROOT),
        "audit_date": AUDIT_DATE,
        "refresh_command": REFRESH_COMMAND,
        "status": {
            "overall": "owner_decision_required" if not drift_errors else "matrix_drift",
            "fail_closed": True,
            "chooses_or_approves_conventions": False,
            "changes_code": False,
            "approves_metrics": False,
            "approves_pages": False,
            "captures_business_owner_approval": False,
            "certifies_routes": False,
        },
        "matrix": {
            "path": str(Path(matrix_path)),
            "latest_verification_refresh": _timestamp(matrix_text),
            "open_decision_ids": open_ids,
            "open_decision_count": len(open_ids),
            "expected_open_decision_ids": list(EXPECTED_OPEN_CALCULATION_P1_IDS),
            "expected_open_decision_count": len(EXPECTED_OPEN_CALCULATION_P1_IDS),
            "missing_open_decision_ids": _missing_ids(open_ids),
            "unexpected_open_decision_ids": _unexpected_ids(open_ids),
            "p1_08_in_open_rows": "P1-08" in open_ids,
            "verified_closed_ids": verified_closed_ids,
            "p1_08_verified_closed": "P1-08" in verified_closed_ids,
            "p1_08_regression": _p108_test_evidence(matrix_text),
        },
        "engineering_prework_map": {
            "mapped_ids": prework_ids,
            "mapped_count": len(prework_ids),
            "missing_ids": _missing_ids(prework_ids),
            "unexpected_ids": _unexpected_ids(prework_ids),
            "boundary_checks": boundary_checks,
        },
        "capture_template": {
            "path": str(Path(capture_template_path)),
            "row_ids": capture_ids,
            "row_count": len(capture_ids),
            "missing_ids": _missing_ids(capture_ids),
            "unexpected_ids": _unexpected_ids(capture_ids),
            "pending_count": sum(1 for row in capture_rows if row["status"] == "pending"),
            "captured_decision_count": len(captured_decision_rows),
            "captured_decision_ids": [row["id"] for row in captured_decision_rows],
        },
        "drift_errors": drift_errors,
        "closure_gate": (
            "Business owner and metric governance must select the authoritative convention "
            "for P1-01 through P1-07 and P1-09 through P1-11 before implementation closure. "
            "After that, docs/calc_rules.md, contracts, implementation, and targeted tests must "
            "move each selected row to verified-closed evidence without reopening P1-08."
        ),
        "boundary": (
            "This snapshot is read-only owner-decision intake evidence. It does not choose or "
            "approve any calculation convention, change implementation code, approve metrics or "
            "pages, capture business-owner approval, or certify routes."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh the calculation/display P1 owner-decision snapshot without choosing "
            "business conventions or changing implementation code."
        ),
    )
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--capture-template", type=Path, default=DEFAULT_CAPTURE_TEMPLATE)
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    snapshot = build_snapshot(
        generated_at=args.generated_at,
        matrix_path=Path(args.matrix),
        capture_template_path=Path(args.capture_template),
    )
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if snapshot["status"]["overall"] != "matrix_drift" else 1


if __name__ == "__main__":
    raise SystemExit(main())
