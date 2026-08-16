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
    EXPECTED_OWNER_DECISION_CLOSED_P1_IDS,
    HISTORICAL_OPEN_CALCULATION_P1_IDS,
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
OPEN_CAPTURE_SECTION_MARKER = "## 待处理 P1 口径裁决"
CLOSED_CAPTURE_SECTION_MARKER = "## 已选并实现的 P1 决定"
CAPTURE_TEMPLATE_NON_APPROVAL_BOUNDARY = (
    "Boundary: this template does not approve calculation conventions, pages, "
    "governance records, owner approvals, direct MCP/GitNexus evidence, or strict checker results."
)
CAPTURE_TEMPLATE_CANDIDATE_CONTRACT_PHRASES = (
    "### Candidate Option Contract",
    "`Option <letter> - <copied option description>`",
    "Required capture format, not a recommendation",
    "`Option <allowed letter> - <copied option description>`",
    "允许的 Option 字母是逐行限定的",
    "approved 行只写 evidence-only 文本",
    "verification_gate` 必须写明",
)
CAPTURED_DECISION_STATUSES = {
    "approved-for-implementation",
    "deferred",
    "rejected",
}
SELECTED_DECISION_OPTION_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:(?:[Oo]ption|[Cc]andidate)\s*[A-Ca-c]|[ABC])(?![A-Za-z0-9])",
)
CANDIDATE_OPTION_RE = re.compile(r"(?<![A-Za-z0-9])([A-C]):")
STOP_WORDS = {
    "a",
    "all",
    "and",
    "are",
    "as",
    "be",
    "both",
    "but",
    "by",
    "can",
    "current",
    "for",
    "from",
    "if",
    "in",
    "is",
    "must",
    "only",
    "or",
    "source",
    "the",
    "to",
    "values",
    "with",
}
SELECTED_DECISION_EVIDENCE_PHRASES = (
    "source evidence",
    "source-data evidence",
    "source data evidence",
    "source contract",
    "source metadata",
    "unit metadata",
    "evidence required",
    "requires evidence",
    "need evidence",
    "needs evidence",
    "pending evidence",
    "defer",
    "deferred",
    "reject",
    "rejected",
)
PLACEHOLDER_VALUE_RE = re.compile(
    r"^(?:tbd|todo|pending|draft|n/?a|na|none|owner_decision|待定|占位|未定)$",
    re.IGNORECASE,
)
SUGGESTED_VALUE_RE = re.compile(r"^suggested\s*:", re.IGNORECASE)
EXPECTED_MEETING_FIELD_COUNT = 8
MEETING_STATUS_PLACEHOLDER = "draft / approved-for-implementation / deferred / rejected"
P1_ROW_RE = re.compile(r"^\|\s*(P1-\d{2})\s*\|")
PREWORK_RE = re.compile(r"^-\s+\*\*(P1-\d{2})\b")
TIMESTAMP_RE = re.compile(r"Refreshed at `([^`]+)`")
P108_TEST_RE = re.compile(r"`(npm\.cmd test -- [^`]+)` was rerun at `([^`]+)`")
EXPECTED_OWNER_DECISION_CLOSED_ACCEPTANCE = {
    "P1-07": {
        "selected_option": "B",
        "status": "implemented-and-verified",
        "matrix_evidence_anchors": (
            "-0.3*liquidity_score",
            "build_macro_context_v1",
        ),
        "capture_evidence_anchors": (
            "tests/test_macro_bond_linkage.py",
            "build_macro_context_v1",
        ),
    },
    "P1-09": {
        "selected_option": "A",
        "status": "implemented-and-verified",
        "matrix_evidence_anchors": (
            "MTR-BMV-005",
            "current_balance_pct",
            "resolveBucketSharePct",
        ),
        "capture_evidence_anchors": (
            "MTR-BMV-005",
            "balanceMovementShareModel.test.ts",
            "BalanceMovementAnalysisPage.test.tsx",
        ),
    },
}


def _now_shanghai() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def _section(text: str, start_marker: str, end_marker: str | None = None) -> str:
    if start_marker not in text:
        return ""
    section = text.split(start_marker, maxsplit=1)[1]
    if end_marker is not None and end_marker in section:
        section = section.split(end_marker, maxsplit=1)[0]
    return section


def _section_to_next_heading(text: str, start_marker: str) -> str:
    section = _section(text, start_marker)
    next_heading = re.search(r"^##\s+", section, re.MULTILINE)
    return section[: next_heading.start()] if next_heading else section


def _repo_relative_identifier(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _markdown_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _table_body_cells(section: str) -> list[list[str]]:
    rows: list[list[str]] = []
    in_body = False
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = _markdown_cells(line)
        if all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            in_body = True
            continue
        if in_body:
            rows.append(cells)
    return rows


def _meeting_record_section(capture_text: str) -> str:
    before_decisions = capture_text.split(OPEN_CAPTURE_SECTION_MARKER, maxsplit=1)[0]
    headers = list(re.finditer(r"^##\s+", before_decisions, re.MULTILINE))
    if not headers:
        return ""
    return before_decisions[headers[-1].start() :]


def _meeting_record_rows(section: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for cells in _table_body_cells(section):
        if len(cells) < 2:
            continue
        rows.append({"field": cells[0], "value": cells[1]})
    return rows


def _is_missing_meeting_value(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        not normalized
        or bool(PLACEHOLDER_VALUE_RE.fullmatch(normalized))
        or normalized == MEETING_STATUS_PLACEHOLDER
        or ("approved-for-implementation" in normalized and "/" in normalized)
    )


def _missing_meeting_fields(rows: list[dict[str, str]]) -> list[str]:
    missing = [
        row["field"]
        for row in rows
        if _is_missing_meeting_value(row.get("value", ""))
    ]
    if len(rows) < EXPECTED_MEETING_FIELD_COUNT:
        missing.extend(
            f"missing_meeting_row_{index}"
            for index in range(len(rows) + 1, EXPECTED_MEETING_FIELD_COUNT + 1)
        )
    return missing


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
                "candidate_decisions": cells[3] if len(cells) > 3 else "",
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


def _closed_capture_rows(section: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for cells in _table_body_cells(section):
        if len(cells) < 6:
            continue
        p1_id = cells[0].strip().strip("`")
        if not re.fullmatch(r"P1-\d{2}", p1_id):
            continue
        rows.append(
            {
                "id": p1_id,
                "selected_decision": cells[2],
                "capture_evidence": cells[3],
                "status": cells[4],
            }
        )
    return rows


def _is_blank(value: str) -> bool:
    return not value.strip()


def _is_placeholder(value: str) -> bool:
    normalized = value.strip()
    return bool(PLACEHOLDER_VALUE_RE.fullmatch(normalized)) or bool(
        SUGGESTED_VALUE_RE.match(normalized)
    )


def _is_pending_status(value: str) -> bool:
    return value.strip().lower() in {"", "pending", "draft"}


def _is_captured_status(value: str) -> bool:
    return value.strip().lower() in CAPTURED_DECISION_STATUSES


def _candidate_options_by_id(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        row["id"]: CANDIDATE_OPTION_RE.findall(str(row.get("candidate_decisions", "")))
        for row in rows
    }


def _candidate_option_descriptions_by_id(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    options_by_id: dict[str, dict[str, str]] = {}
    for row in rows:
        options_by_id[row["id"]] = _candidate_options_from_text(
            str(row.get("candidate_decisions", ""))
        )
    return options_by_id


def _candidate_options_from_text(text: str) -> dict[str, str]:
    options: dict[str, str] = {}
    for letter, description in re.findall(
        r"([A-C]):\s*(.*?)(?=(?:;\s*[A-C]:)|$)",
        text,
    ):
        options[letter] = description.strip().rstrip(".")
    return options


def _capture_template_candidate_contract_options(
    capture_text: str,
) -> dict[str, dict[str, str]]:
    contract_section = _section(
        capture_text,
        "### Candidate Option Contract",
        "| P1 | 决策主题",
    )
    options_by_id: dict[str, dict[str, str]] = {}
    for cells in _table_body_cells(contract_section):
        if len(cells) < 2:
            continue
        p1_id = cells[0].strip().strip("`")
        if not re.fullmatch(r"P1-\d{2}", p1_id):
            continue
        options_by_id[p1_id] = _candidate_options_from_text(cells[1])
    return options_by_id


def _selected_option_letter(value: str) -> str | None:
    match = SELECTED_DECISION_OPTION_RE.search(value)
    if match is None:
        return None
    letter_match = re.search(r"[A-Ca-c]", match.group(0))
    return letter_match.group(0).upper() if letter_match else None


def _option_anchor_remainder(value: str) -> str:
    match = SELECTED_DECISION_OPTION_RE.search(value)
    if match is None:
        return ""
    remainder = f"{value[: match.start()]} {value[match.end() :]}"
    remainder = re.sub(r"\bP1-\d{2}\b", " ", remainder, flags=re.IGNORECASE)
    remainder = re.sub(r"[\s:,;|/\\()\[\]{}._-]+", " ", remainder).strip()
    return remainder


def _has_option_anchor(value: str) -> bool:
    remainder = _option_anchor_remainder(value)
    return bool(remainder) and not _is_placeholder(remainder)


def _keyword_set(value: str) -> set[str]:
    tokens = re.findall(r"[A-Za-z0-9_]+", value.lower())
    return {token for token in tokens if len(token) > 2 and token not in STOP_WORDS}


def _option_description_matches(value: str, description: str) -> bool:
    selected_keywords = _keyword_set(_option_anchor_remainder(value))
    candidate_keywords = _keyword_set(description)
    if not selected_keywords or not candidate_keywords:
        return False
    return bool(selected_keywords & candidate_keywords)


def _has_allowed_option_anchor(
    value: str,
    *,
    allowed_options: dict[str, str],
) -> bool:
    option = _selected_option_letter(value)
    if option is None or option not in allowed_options or not _has_option_anchor(value):
        return False
    return _option_description_matches(value, allowed_options[option])


def _has_selected_decision_anchor(
    value: str,
    *,
    status: str = "",
    allowed_options: dict[str, str] | None = None,
) -> bool:
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    if not normalized:
        return False
    if _has_allowed_option_anchor(value, allowed_options=allowed_options or []):
        return True
    if _selected_option_letter(value) is not None:
        return False
    if _is_captured_status(status) and status.strip().lower() == "approved-for-implementation":
        return False
    for phrase in SELECTED_DECISION_EVIDENCE_PHRASES:
        if phrase not in normalized:
            continue
        remainder = normalized.replace(phrase, " ")
        remainder = re.sub(r"[\s:：,，;；|/\\()\[\]{}._-]+", " ", remainder).strip()
        if remainder and not _is_placeholder(remainder):
            return True
    return False


def _incomplete_capture_fields(
    row: dict[str, Any],
    *,
    allowed_options: dict[str, str] | None = None,
) -> list[str]:
    missing: list[str] = []
    selected_decision = str(row["selected_decision"])
    if _is_blank(selected_decision) or not _has_selected_decision_anchor(
        selected_decision,
        status=str(row["status"]),
        allowed_options=allowed_options,
    ):
        missing.append("selected_decision")
    for field in ("owner_rationale", "implementation_owner", "verification_gate"):
        if _is_blank(str(row[field])) or _is_placeholder(str(row[field])):
            missing.append(field)
    if not _is_captured_status(str(row["status"])):
        missing.append("status")
    return missing


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


def _owner_decision_closed_acceptance(
    *,
    matrix_rows: list[dict[str, Any]],
    capture_rows: list[dict[str, str]],
) -> tuple[dict[str, Any], list[str]]:
    matrix_by_id = {row["id"]: row for row in matrix_rows}
    capture_by_id = {row["id"]: row for row in capture_rows}
    records: dict[str, Any] = {}
    errors: list[str] = []

    for p1_id, expected in EXPECTED_OWNER_DECISION_CLOSED_ACCEPTANCE.items():
        matrix_row = matrix_by_id.get(p1_id) or {}
        matrix_cells = matrix_row.get("cells") or []
        matrix_evidence = str(matrix_cells[2]) if len(matrix_cells) > 2 else ""
        capture_row = capture_by_id.get(p1_id) or {}
        selected_decision = str(capture_row.get("selected_decision") or "")
        capture_evidence = str(capture_row.get("capture_evidence") or "")
        status = str(capture_row.get("status") or "")
        selected_option = _selected_option_letter(selected_decision)
        matrix_selected_option = _selected_option_letter(matrix_evidence)
        checks = {
            "matrix_row_present": bool(matrix_row),
            "capture_row_present": bool(capture_row),
            "matrix_selected_option_matches": (
                matrix_selected_option == expected["selected_option"]
            ),
            "capture_selected_option_matches": (
                selected_option == expected["selected_option"]
            ),
            "status_matches": status == expected["status"],
            "matrix_evidence_complete": all(
                anchor in matrix_evidence
                for anchor in expected["matrix_evidence_anchors"]
            ),
            "capture_evidence_complete": all(
                anchor in capture_evidence
                for anchor in expected["capture_evidence_anchors"]
            ),
        }
        for check_name, passed in checks.items():
            if not passed:
                errors.append(
                    f"owner-decision closure acceptance failed: {p1_id} {check_name}"
                )
        records[p1_id] = {
            "selected_option": selected_option,
            "selected_decision": selected_decision,
            "status": status,
            "matrix_evidence": matrix_evidence,
            "capture_evidence": capture_evidence,
            "checks": checks,
        }

    return {
        "expected_ids": list(EXPECTED_OWNER_DECISION_CLOSED_ACCEPTANCE),
        "records_by_id": records,
        "all_accepted": not errors,
    }, errors


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
        "## Verified Closed After Owner Decision",
    )
    owner_decision_closed_section = _section(
        matrix_text,
        "## Verified Closed After Owner Decision",
        "## Engineering Prework / Impact Slice Map",
    )
    prework_section = _section(
        matrix_text,
        "## Engineering Prework / Impact Slice Map",
    )
    capture_section = _section(
        capture_text,
        OPEN_CAPTURE_SECTION_MARKER,
        CLOSED_CAPTURE_SECTION_MARKER,
    )
    closed_capture_section = _section_to_next_heading(
        capture_text,
        CLOSED_CAPTURE_SECTION_MARKER,
    )

    open_rows = _decision_rows(decision_section)
    open_ids = [row["id"] for row in open_rows]
    candidate_options_by_id = _candidate_option_descriptions_by_id(open_rows)
    template_candidate_options_by_id = _capture_template_candidate_contract_options(
        capture_text
    )
    verified_closed_rows = _decision_rows(verified_closed_section)
    verified_closed_ids = [row["id"] for row in verified_closed_rows]
    owner_decision_closed_rows = _decision_rows(owner_decision_closed_section)
    owner_decision_closed_ids = [row["id"] for row in owner_decision_closed_rows]
    owner_decision_closed_acceptance, owner_decision_acceptance_errors = (
        _owner_decision_closed_acceptance(
            matrix_rows=owner_decision_closed_rows,
            capture_rows=_closed_capture_rows(closed_capture_section),
        )
    )
    prework_ids = _prework_ids(prework_section)
    capture_rows = _capture_rows(capture_section)
    capture_ids = [row["id"] for row in capture_rows]
    meeting_rows = _meeting_record_rows(_meeting_record_section(capture_text))
    missing_meeting_fields = _missing_meeting_fields(meeting_rows)
    incomplete_capture_by_id = {
        row["id"]: _incomplete_capture_fields(
            row,
            allowed_options=candidate_options_by_id.get(row["id"], []),
        )
        for row in capture_rows
        if _incomplete_capture_fields(
            row,
            allowed_options=candidate_options_by_id.get(row["id"], []),
        )
    }
    invalid_selected_decision_by_id = {
        row["id"]: row["selected_decision"]
        for row in capture_rows
        if not _is_blank(str(row["selected_decision"]))
        and not _has_selected_decision_anchor(
            str(row["selected_decision"]),
            status=str(row["status"]),
            allowed_options=candidate_options_by_id.get(row["id"], []),
        )
    }
    captured_decision_rows = [
        row for row in capture_rows if row["id"] not in incomplete_capture_by_id
    ]
    invalid_status_by_id = {
        row["id"]: row["status"]
        for row in capture_rows
        if not _is_pending_status(str(row["status"]))
        and not _is_captured_status(str(row["status"]))
    }

    boundary_checks = {
        "does_not_choose_or_approve_convention": (
            "does not choose or approve any convention" in prework_section
        ),
        "does_not_change_code": "does not change code" in prework_section,
        "does_not_certify_routes_pages": "does not certify routes/pages" in prework_section,
        "matrix_non_approval_boundary": "This matrix does not approve any calculation convention."
        in matrix_text,
        "capture_template_non_approval_boundary": CAPTURE_TEMPLATE_NON_APPROVAL_BOUNDARY
        in capture_text,
        "capture_template_candidate_option_contract": all(
            phrase in capture_text
            for phrase in CAPTURE_TEMPLATE_CANDIDATE_CONTRACT_PHRASES
        ),
        "capture_template_candidate_options_match_matrix": (
            template_candidate_options_by_id == candidate_options_by_id
        ),
    }

    drift_errors: list[str] = []
    if open_ids != EXPECTED_OPEN_CALCULATION_P1_IDS:
        drift_errors.append("open P1 decision IDs do not match the expected order")
    if "P1-08" in open_ids:
        drift_errors.append("P1-08 appears in open owner-decision rows")
    if "P1-08" not in verified_closed_ids:
        drift_errors.append("P1-08 verified-closed row is missing")
    if owner_decision_closed_ids != EXPECTED_OWNER_DECISION_CLOSED_P1_IDS:
        drift_errors.append(
            "owner-decision closed P1 IDs do not match the expected order"
        )
    drift_errors.extend(owner_decision_acceptance_errors)
    if _missing_ids(prework_ids):
        drift_errors.append("engineering prework map is missing open P1 IDs")
    if _unexpected_ids(prework_ids):
        drift_errors.append("engineering prework map contains unexpected P1 IDs")
    if capture_ids != EXPECTED_OPEN_CALCULATION_P1_IDS:
        drift_errors.append("owner decision capture template P1 IDs do not match the expected order")
    if len(meeting_rows) != EXPECTED_MEETING_FIELD_COUNT:
        drift_errors.append("owner decision capture template meeting field count drifted")
    for name, passed in boundary_checks.items():
        if not passed:
            drift_errors.append(f"boundary check failed: {name}")

    return {
        "report_kind": "calculation_p1_owner_decision_snapshot",
        "generated_at": generated_at,
        "repo_root": ".",
        "audit_date": AUDIT_DATE,
        "state_as_of": "2026-08-06",
        "historical_baseline": {
            "as_of": "2026-06-10T21:25:00+08:00",
            "open_decision_ids": list(HISTORICAL_OPEN_CALCULATION_P1_IDS),
            "open_decision_count": len(HISTORICAL_OPEN_CALCULATION_P1_IDS),
            "scope": (
                "Historical source snapshot only; current owner intake is represented "
                "by matrix.open_decision_ids and capture_template.row_ids."
            ),
        },
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
            "path": _repo_relative_identifier(Path(matrix_path)),
            "latest_verification_refresh": _timestamp(matrix_text),
            "open_decision_ids": open_ids,
            "open_decision_count": len(open_ids),
            "expected_open_decision_ids": list(EXPECTED_OPEN_CALCULATION_P1_IDS),
            "expected_open_decision_count": len(EXPECTED_OPEN_CALCULATION_P1_IDS),
            "missing_open_decision_ids": _missing_ids(open_ids),
            "unexpected_open_decision_ids": _unexpected_ids(open_ids),
            "candidate_options_by_id": candidate_options_by_id,
            "candidate_option_letters_by_id": _candidate_options_by_id(open_rows),
            "capture_template_candidate_options_match_matrix": (
                template_candidate_options_by_id == candidate_options_by_id
            ),
            "p1_08_in_open_rows": "P1-08" in open_ids,
            "verified_closed_ids": verified_closed_ids,
            "owner_decision_closed_ids": owner_decision_closed_ids,
            "owner_decision_closed_acceptance": owner_decision_closed_acceptance,
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
            "path": _repo_relative_identifier(Path(capture_template_path)),
            "row_ids": capture_ids,
            "row_count": len(capture_ids),
            "missing_ids": _missing_ids(capture_ids),
            "unexpected_ids": _unexpected_ids(capture_ids),
            "pending_count": sum(1 for row in capture_rows if row["status"] == "pending"),
            "captured_statuses": sorted(CAPTURED_DECISION_STATUSES),
            "candidate_contract_options_by_id": template_candidate_options_by_id,
            "invalid_status_by_id": invalid_status_by_id,
            "invalid_selected_decision_by_id": invalid_selected_decision_by_id,
            "invalid_selected_decision_count": len(invalid_selected_decision_by_id),
            "captured_decision_count": len(captured_decision_rows),
            "captured_decision_ids": [row["id"] for row in captured_decision_rows],
            "incomplete_decision_count": len(incomplete_capture_by_id),
            "incomplete_decision_ids": list(incomplete_capture_by_id),
            "incomplete_fields_by_id": incomplete_capture_by_id,
        },
        "meeting_record": {
            "required_field_count": EXPECTED_MEETING_FIELD_COUNT,
            "field_count": len(meeting_rows),
            "filled_required_field_count": len(meeting_rows)
            - len([field for field in missing_meeting_fields if not field.startswith("missing_meeting_row_")]),
            "missing_required_fields": missing_meeting_fields,
            "is_complete": not missing_meeting_fields
            and len(meeting_rows) == EXPECTED_MEETING_FIELD_COUNT,
        },
        "drift_errors": drift_errors,
        "closure_gate": (
            "Business owner and metric governance must select the authoritative convention "
            "for the remaining P1-01 through P1-06, P1-10, and P1-11 rows before "
            "implementation closure. P1-07 and P1-09 are already verified closed after "
            "their recorded owner decisions. "
            "After that, docs/calc_rules.md, contracts, implementation, and targeted tests must "
            "move each selected row to verified-closed evidence without reopening P1-07, "
            "P1-08, or P1-09."
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
    parser.add_argument(
        "--require-owner-decisions-captured",
        action="store_true",
        help=(
            "Exit non-zero unless every open P1 row has an owner decision captured. "
            "The default refresh remains a read-only pending-decision snapshot."
        ),
    )
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
    if snapshot["status"]["overall"] == "matrix_drift":
        return 1
    if args.require_owner_decisions_captured:
        capture = snapshot["capture_template"]
        meeting_record = snapshot["meeting_record"]
        if capture["captured_decision_count"] != capture["row_count"] or not meeting_record[
            "is_complete"
        ]:
            print(
                (
                    "Calculation P1 owner decisions are not fully captured: "
                    f"captured_decision_count={capture['captured_decision_count']}, "
                    f"row_count={capture['row_count']}, "
                    f"pending_count={capture['pending_count']}, "
                    "invalid_selected_decision_count="
                    f"{capture['invalid_selected_decision_count']}, "
                    f"meeting_record_complete={str(meeting_record['is_complete']).lower()}"
                ),
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
