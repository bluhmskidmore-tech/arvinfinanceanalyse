from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

AUDIT_DATE = "2026-06-10"
FIRST_PRIORITY_IDS = ["P1-10", "P1-11"]
POST_OWNER_REQUIRED_FIELDS = [
    "selected_decision",
    "owner_rationale",
    "implementation_owner",
    "verification_gate",
    "status",
]
DEFAULT_MATRIX = (
    ROOT / "docs" / "audits" / f"{AUDIT_DATE}-calculation-p1-owner-decision-matrix.md"
)
DEFAULT_SNAPSHOT = (
    ROOT / "docs" / "audits" / f"{AUDIT_DATE}-calculation-p1-owner-decision-snapshot.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "docs"
    / "audits"
    / f"{AUDIT_DATE}-calculation-p1-first-priority-readiness-packet.md"
)

EVIDENCE_SCOPE = {
    "read_only": True,
    "chooses_or_approves_conventions": False,
    "changes_code": False,
    "writes_duckdb": False,
    "writes_governance_records": False,
    "approves_metrics": False,
    "approves_pages": False,
    "captures_business_owner_approval": False,
    "captures_owner_decisions": False,
    "certifies_routes": False,
    "authorizes_ledger_pnl_governance_write": False,
}

PROHIBITED_ACTIONS = [
    "choose backend-vs-frontend ownership without business-owner and metric-governance input",
    "treat current frontend tests as approval for formal metric ownership",
    "change formal aggregation or rating-tenor bucket ownership before the selected rule is captured",
    "count this readiness packet as owner decision capture",
    "promote frontend-derived values to governed values without contract evidence",
]

FIRST_PRIORITY_ITEMS: list[dict[str, Any]] = [
    {
        "p1_id": "P1-10",
        "area": "Frontend formal aggregation",
        "owner_decision_needed": (
            "Decide whether formal PnL, yield, and ADB aggregations must come from backend DTOs, "
            "or whether frontend derivations are limited to labeled non-formal helpers."
        ),
        "current_risk": (
            "Frontend aggregation converts Decimal-shaped strings to floats and duplicates "
            "category-tree ownership that can diverge from governed rules."
        ),
        "code_anchors": [
            "frontend/src/features/pnl/YieldAnalysisPage.tsx",
            "frontend/src/features/pnl/PnlByBusinessPage.tsx",
            "frontend/src/features/pnl/pnlByBusinessPageModel.ts",
            "frontend/src/features/pnl/yieldAnalysis/yieldAnalysisAggregates.ts",
            "frontend/src/features/pnl/zqtzAdbAvgRollup.ts",
        ],
        "test_anchors": [
            "frontend/src/features/pnl/yieldAnalysis/yieldAnalysisAggregates.test.ts",
            "frontend/src/features/pnl/zqtzAdbAvgRollup.test.ts",
        ],
        "current_test_evidence": [
            "yieldAnalysisAggregates rejects invalid money inputs instead of coercing them to zero.",
            "zqtzAdbAvgRollup tests freeze the current frontend ADB parent/child rollup behavior.",
        ],
        "post_owner_actions": [
            "If backend DTO is authoritative, consume DTO values and remove formal frontend aggregation.",
            "If frontend helpers remain, label them non-formal and keep them out of governed metric claims.",
            "Update yield and ADB tests to prove DTO consumption or the explicitly non-formal boundary.",
        ],
        "owner_decision_gate": (
            "backend DTO / frontend removal tests, or tests proving non-formal helper labeling"
        ),
    },
    {
        "p1_id": "P1-11",
        "area": "Credit spread rating-tenor matrix",
        "owner_decision_needed": (
            "Decide whether the governed rating-tenor matrix is backend-provided, or frontend "
            "owns bucket aggregation and mapping rules."
        ),
        "current_risk": (
            "Credit spread view currently maps rating and tenor buckets in the frontend, so "
            "hard-coded buckets can drift from backend tenor/rating rules."
        ),
        "code_anchors": [
            "frontend/src/features/bond-analytics/components/CreditSpreadView.tsx",
        ],
        "test_anchors": [
            "frontend/src/test/CreditSpreadView.test.tsx",
        ],
        "current_test_evidence": [
            "CreditSpreadView keeps legacy summary visible and renders credit spread detail/fallback metadata.",
        ],
        "post_owner_actions": [
            "If backend matrix is authoritative, render the provided matrix and fail closed when it is absent.",
            "If frontend owns buckets, document bucket ownership in the contract and test boundary mapping.",
            "Add rating/tenor bucket-boundary regression for the selected ownership rule.",
        ],
        "owner_decision_gate": (
            "API contract plus frontend test proving provided matrix rendering or explicit frontend ownership"
        ),
        "known_regression_gap": (
            "rating/tenor bucket-boundary regression remains pending until owner selects matrix ownership"
        ),
    },
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _path_status(paths: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "exists": (ROOT / path).exists(),
        }
        for path in paths
    ]


def _open_ids_from_snapshot(snapshot: dict[str, Any]) -> list[str]:
    return list(snapshot.get("matrix", {}).get("open_decision_ids") or [])


def _first_priority_matrix_present(matrix_text: str) -> bool:
    return "P1-10 and P1-11" in matrix_text


def build_packet(
    *,
    matrix_path: Path = DEFAULT_MATRIX,
    snapshot_path: Path = DEFAULT_SNAPSHOT,
) -> dict[str, Any]:
    matrix_text = Path(matrix_path).read_text(encoding="utf-8")
    snapshot = _load_json(Path(snapshot_path))
    open_ids = _open_ids_from_snapshot(snapshot)
    capture = snapshot.get("capture_template", {})
    incomplete_by_id = capture.get("incomplete_fields_by_id", {})

    items = []
    for item in FIRST_PRIORITY_ITEMS:
        code_status = _path_status(item["code_anchors"])
        test_status = _path_status(item["test_anchors"])
        items.append(
            {
                **item,
                "current_status": "pending_owner_decision",
                "implementation_ready": False,
                "missing_capture_fields": incomplete_by_id.get(item["p1_id"], []),
                "code_anchor_status": code_status,
                "test_anchor_status": test_status,
                "missing_code_anchors": [
                    path_item["path"] for path_item in code_status if not path_item["exists"]
                ],
                "missing_test_anchors": [
                    path_item["path"] for path_item in test_status if not path_item["exists"]
                ],
            }
        )

    missing_code_anchors = [
        path
        for item in items
        for path in item["missing_code_anchors"]
    ]
    missing_test_anchors = [
        path
        for item in items
        for path in item["missing_test_anchors"]
    ]
    source_status = snapshot.get("status", {}).get("overall")
    captured_ids = set(capture.get("captured_decision_ids") or [])
    first_priority_captured_ids = [
        p1_id for p1_id in FIRST_PRIORITY_IDS if p1_id in captured_ids
    ]

    return {
        "packet_kind": "calculation_p1_first_priority_readiness_packet",
        "audit_date": AUDIT_DATE,
        "source_artifacts": {
            "calculation_owner_decision_matrix": (
                f"docs/audits/{AUDIT_DATE}-calculation-p1-owner-decision-matrix.md"
            ),
            "calculation_owner_decision_snapshot": (
                f"docs/audits/{AUDIT_DATE}-calculation-p1-owner-decision-snapshot.json"
            ),
            "calculation_owner_decision_packet": (
                f"docs/audits/{AUDIT_DATE}-calculation-p1-owner-decision-packet.md"
            ),
        },
        "source_snapshot_generated_at": snapshot.get("generated_at"),
        "source_snapshot_status": source_status,
        "first_priority_ids": list(FIRST_PRIORITY_IDS),
        "first_priority_count": len(FIRST_PRIORITY_IDS),
        "first_priority_matrix_present": _first_priority_matrix_present(matrix_text),
        "first_priority_ids_in_open_snapshot": [
            p1_id for p1_id in FIRST_PRIORITY_IDS if p1_id in open_ids
        ],
        "owner_intake_ready": (
            source_status == "owner_decision_required"
            and _first_priority_matrix_present(matrix_text)
            and not missing_code_anchors
            and not missing_test_anchors
        ),
        "implementation_ready": False,
        "captured_decision_count": len(first_priority_captured_ids),
        "captured_decision_ids": first_priority_captured_ids,
        "post_owner_required_fields": list(POST_OWNER_REQUIRED_FIELDS),
        "items": items,
        "readiness_checks": {
            "all_first_priority_ids_still_open": all(
                p1_id in open_ids for p1_id in FIRST_PRIORITY_IDS
            ),
            "source_snapshot_is_owner_decision_required": (
                source_status == "owner_decision_required"
            ),
            "matrix_names_first_priority_group": _first_priority_matrix_present(matrix_text),
            "all_code_anchors_exist": not missing_code_anchors,
            "all_test_anchors_exist": not missing_test_anchors,
            "captures_owner_decisions": False,
            "chooses_or_approves_conventions": False,
            "changes_implementation_code": False,
        },
        "missing_code_anchors": missing_code_anchors,
        "missing_test_anchors": missing_test_anchors,
        "evidence_scope": dict(EVIDENCE_SCOPE),
        "prohibited_actions": list(PROHIBITED_ACTIONS),
        "boundary": (
            "This readiness packet is read-only. It maps P1-10 and P1-11 "
            "to current code/test anchors and post-owner execution gates; it does not "
            "choose or approve any calculation convention, change implementation code, "
            "capture owner decisions, approve metrics or pages, write governance records, "
            "authorize Ledger PnL --write, or certify routes."
        ),
    }


def _join_backtick(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "none"


def render_markdown(packet: dict[str, Any]) -> str:
    source_rows = "\n".join(
        f"- `{key}`: `{value}`" for key, value in packet["source_artifacts"].items()
    )
    check_rows = "\n".join(
        f"- `{key}={str(value).lower() if isinstance(value, bool) else value}`"
        for key, value in packet["readiness_checks"].items()
    )
    item_rows = "\n".join(
        (
            f"| `{item['p1_id']}` | {item['area']} | {item['owner_decision_needed']} | "
            f"{_join_backtick(item['code_anchors'])} | {_join_backtick(item['test_anchors'])} | "
            f"`{item['current_status']}` | {_join_backtick(item['missing_capture_fields'])} | "
            f"{item['owner_decision_gate']} |"
        )
        for item in packet["items"]
    )
    evidence_rows = "\n".join(
        (
            f"| `{item['p1_id']}` | {'<br>'.join(item['current_test_evidence'])} | "
            f"{'<br>'.join(item['post_owner_actions'])} | {item.get('known_regression_gap', 'none')} |"
        )
        for item in packet["items"]
    )
    prohibited = "\n".join(f"- {action}" for action in packet["prohibited_actions"])
    scope = "\n".join(
        f"- `{key}={str(value).lower() if isinstance(value, bool) else value}`"
        for key, value in packet["evidence_scope"].items()
    )

    return f"""# Calculation P1 First Priority Readiness Packet

Source snapshot status: `source_snapshot_status={packet['source_snapshot_status']}`
Owner intake ready: `{str(packet['owner_intake_ready']).lower()}`
Implementation ready: `{str(packet['implementation_ready']).lower()}`
Source snapshot generated at: `{packet['source_snapshot_generated_at']}`

This packet prepares the current first priority group inside the calculation/display P1 blocker. It records current code anchors, existing test anchors, and the post-owner execution gates for `P1-10` and `P1-11`. P1-09 was selected and implemented previously and is not part of current owner intake. This packet does not approve a convention or change implementation code.

## Summary

- `first_priority_ids={', '.join(packet['first_priority_ids'])}`
- `first_priority_count={packet['first_priority_count']}`
- `captured_decision_count={packet['captured_decision_count']}`
- `post_owner_required_fields={', '.join(packet['post_owner_required_fields'])}`
- `owner_intake_ready={str(packet['owner_intake_ready']).lower()}`
- `implementation_ready={str(packet['implementation_ready']).lower()}`

## Source Artifacts

{source_rows}

## Readiness Checks

{check_rows}

## First Priority Items

| P1 | Area | Owner Decision Needed | Code Anchors | Test Anchors | Current Status | Missing Capture Fields | Owner Decision Gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
{item_rows}

## Current Evidence And Post-Owner Gates

| P1 | Current Test Evidence | Post-Owner Actions | Known Regression Gap |
| --- | --- | --- | --- |
{evidence_rows}

## Prohibited Actions

{prohibited}

## Evidence Scope

{scope}

## Boundary

{packet['boundary']}
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the read-only P1-10/P1-11 calculation readiness packet.",
    )
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    packet = build_packet(matrix_path=args.matrix, snapshot_path=args.snapshot)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(packet), encoding="utf-8")
    payload = {
        "packet_kind": packet["packet_kind"],
        "packet_path": str(output_path),
        "source_snapshot_status": packet["source_snapshot_status"],
        "owner_intake_ready": packet["owner_intake_ready"],
        "implementation_ready": packet["implementation_ready"],
        "first_priority_count": packet["first_priority_count"],
        "first_priority_ids": packet["first_priority_ids"],
        "captured_decision_count": packet["captured_decision_count"],
        "readiness_checks": packet["readiness_checks"],
        "evidence_scope": packet["evidence_scope"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
