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

from scripts.business_display_coverage_report import (
    build_report as build_business_display_coverage_report,
)
from scripts.codex_page_readiness import (
    build_all_page_readiness_report,
    build_route_scope_classification_report,
)
from scripts.verify_system_audit_completion_snapshot import verify_completion_snapshot


DEFAULT_MANIFEST = ROOT / "docs" / "audits" / "2026-06-10-system-audit-manifest.json"

EVIDENCE_SCOPE = {
    "read_only": True,
    "writes_duckdb": False,
    "writes_governance_records": False,
    "approves_metrics": False,
    "approves_pages": False,
    "captures_business_owner_approval": False,
    "certifies_routes": False,
    "clears_secret_scan": False,
    "promotes_candidate_data": False,
}


def _default_generated_at() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fresh_command_summary(manifest: dict[str, Any], command: str) -> dict[str, Any] | None:
    for item in manifest.get("fresh_verification", {}).get("commands", []):
        if item.get("command") == command:
            return dict(item.get("summary") or {})
    return None


def _append_mismatch(
    errors: list[str],
    *,
    field: str,
    expected: Any,
    actual: Any,
) -> None:
    if actual != expected:
        errors.append(f"{field} expected {expected!r}, got {actual!r}")


def _route_scope_summary(route_scope: dict[str, Any]) -> dict[str, Any]:
    summary = dict(route_scope.get("summary") or {})
    return {
        "route_count": summary.get("route_count"),
        "seeded_trace_bundle_count": summary.get("seeded_trace_bundle_count"),
        "visible_navigation_route_count": summary.get("visible_navigation_route_count"),
        "visible_unseeded_route_count": summary.get("visible_unseeded_route_count"),
        "business_contract_certified_count": summary.get("business_contract_certified_count"),
        "evidence_pending_count": summary.get("evidence_pending_count"),
        "gate_i_gap_count": summary.get("gate_i_gap_count"),
        "frontend_ready_count": summary.get("frontend_ready_count"),
        "frontend_only_count": summary.get("frontend_only_count"),
        "unclassified_count": summary.get("unclassified_count"),
    }


def _completion_summary(completion: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": completion.get("status"),
        "open_blocker_count": completion.get("open_blocker_count"),
        "completion_gate_count": completion.get("completion_gate_count"),
        "follow_up_packet_count": completion.get("follow_up_packet_count"),
        "follow_up_brief_blocker_count": completion.get("follow_up_brief_blocker_count"),
        "calculation_prework_p1_count": completion.get("calculation_prework_p1_count"),
        "error_count": len(completion.get("errors") or []),
    }


def _display_coverage_summary(coverage: dict[str, Any]) -> dict[str, Any]:
    summary = dict(coverage.get("summary") or {})
    return {
        "tracked_route_count": summary.get("tracked_route_count"),
        "route_gap_count": summary.get("route_gap_count"),
        "browser_smoke_a11y_configured_route_count": summary.get(
            "browser_smoke_a11y_configured_route_count"
        ),
        "browser_smoke_a11y_gap_count": summary.get("browser_smoke_a11y_gap_count"),
        "coverage_status": summary.get("coverage_status"),
    }


def _all_page_readiness_summary(
    *,
    manifest: dict[str, Any],
    include_full_readiness: bool,
) -> dict[str, Any]:
    if include_full_readiness:
        report = build_all_page_readiness_report()
        pages = list(report.get("pages") or [])
        missing_direct_records_count = sum(
            1
            for page in pages
            if (page.get("governance_record_validation") or {}).get("status")
            == "missing_direct_records"
        )
        direct_ready_count = sum(
            1
            for page in pages
            if (page.get("governance_record_validation") or {}).get("status")
            == "direct_records_ready_for_audit_review"
        )
        catalog_incomplete_count = sum(
            1
            for page in pages
            if (page.get("catalog_date_evidence") or {}).get("status") == "incomplete"
        )
        return {
            "source": "live_full_readiness",
            "page_count": report["summary"]["page_count"],
            "static_pass_count": report["summary"]["static_pass_count"],
            "run_supported_count": report["summary"]["run_supported_count"],
            "owner_approval_pending_count": report["summary"][
                "business_owner_approval_pending_count"
            ],
            "owner_approval_action_item_sum": report["summary"][
                "business_owner_approval_action_item_count"
            ],
            "direct_evidence_null_count": sum(
                1 for page in pages if page.get("governance_record_validation") is None
            ),
            "audit_review_null_count": sum(
                1 for page in pages if page.get("audit_review") is None
            ),
            "missing_direct_records_count": missing_direct_records_count,
            "direct_records_ready_for_audit_review_count": direct_ready_count,
            "catalog_date_incomplete_count": catalog_incomplete_count,
        }

    summary = _fresh_command_summary(
        manifest,
        "python scripts\\codex_page_readiness.py --all",
    )
    return {
        "source": "manifest_last_full_readiness",
        **(summary or {}),
    }


def build_pulse(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    repo_root: Path = ROOT,
    generated_at: str | None = None,
    include_full_readiness: bool = False,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    counts = dict(manifest.get("counts") or {})
    route_scope = build_route_scope_classification_report()
    coverage = build_business_display_coverage_report(repo_root=repo_root)
    completion = verify_completion_snapshot(manifest_path=manifest_path, repo_root=repo_root)

    route_summary = _route_scope_summary(route_scope)
    coverage_summary = _display_coverage_summary(coverage)
    completion_status = _completion_summary(completion)
    readiness_summary = _all_page_readiness_summary(
        manifest=manifest,
        include_full_readiness=include_full_readiness,
    )

    drift_errors: list[str] = []
    if completion.get("status") != "pass":
        drift_errors.extend(str(error) for error in completion.get("errors") or [])
    _append_mismatch(
        drift_errors,
        field="route_scope.seeded_trace_bundle_count",
        expected=counts.get("seeded_pages"),
        actual=route_summary["seeded_trace_bundle_count"],
    )
    _append_mismatch(
        drift_errors,
        field="route_scope.business_contract_certified_count",
        expected=counts.get("business_contract_certified_routes"),
        actual=route_summary["business_contract_certified_count"],
    )
    _append_mismatch(
        drift_errors,
        field="route_scope.visible_unseeded_route_count",
        expected=0,
        actual=route_summary["visible_unseeded_route_count"],
    )
    _append_mismatch(
        drift_errors,
        field="route_scope.unclassified_count",
        expected=0,
        actual=route_summary["unclassified_count"],
    )
    _append_mismatch(
        drift_errors,
        field="business_display.tracked_route_count",
        expected=counts.get("business_display_tracked_routes"),
        actual=coverage_summary["tracked_route_count"],
    )
    _append_mismatch(
        drift_errors,
        field="business_display.route_gap_count",
        expected=counts.get("business_display_route_gaps"),
        actual=coverage_summary["route_gap_count"],
    )
    _append_mismatch(
        drift_errors,
        field="business_display.browser_smoke_a11y_configured_route_count",
        expected=counts.get("browser_smoke_a11y_configured_routes"),
        actual=coverage_summary["browser_smoke_a11y_configured_route_count"],
    )
    if readiness_summary.get("page_count") is not None:
        _append_mismatch(
            drift_errors,
            field="readiness.page_count",
            expected=counts.get("seeded_pages"),
            actual=readiness_summary.get("page_count"),
        )
    if readiness_summary.get("static_pass_count") is not None:
        _append_mismatch(
            drift_errors,
            field="readiness.static_pass_count",
            expected=counts.get("static_pass_pages"),
            actual=readiness_summary.get("static_pass_count"),
        )
    if readiness_summary.get("direct_evidence_null_count") is not None:
        _append_mismatch(
            drift_errors,
            field="readiness.direct_evidence_null_count",
            expected=0,
            actual=readiness_summary.get("direct_evidence_null_count"),
        )
    if readiness_summary.get("audit_review_null_count") is not None:
        _append_mismatch(
            drift_errors,
            field="readiness.audit_review_null_count",
            expected=0,
            actual=readiness_summary.get("audit_review_null_count"),
        )

    open_blockers = list(manifest.get("open_blockers") or [])
    return {
        "report_kind": "system_audit_pulse",
        "generated_at": generated_at or _default_generated_at(),
        "repo_root": str(repo_root),
        "manifest_path": str(manifest_path),
        "status": "pass" if not drift_errors else "fail",
        "full_score_ready": False,
        "completion_state": "not_complete" if open_blockers else "ready_for_completion_audit",
        "open_blocker_count": len(open_blockers),
        "open_blockers": [
            {
                "id": blocker.get("id"),
                "status": blocker.get("status"),
                "last_checked_at": blocker.get("last_checked_at"),
            }
            for blocker in open_blockers
        ],
        "evidence_scope": dict(EVIDENCE_SCOPE),
        "route_scope": route_summary,
        "business_display": coverage_summary,
        "completion_snapshot": completion_status,
        "all_page_readiness": readiness_summary,
        "drift_errors": drift_errors,
        "claim_boundary": (
            "This pulse is a read-only monitoring aggregate. It does not approve metrics, "
            "pages, owner signoff, governance records, secret hygiene, direct App MCP/GitNexus "
            "evidence, or route certification."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a read-only pulse for system audit readiness and closure drift.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the system audit manifest.",
    )
    parser.add_argument(
        "--generated-at",
        default=None,
        help="Stable timestamp for reproducible tests.",
    )
    parser.add_argument(
        "--include-full-readiness",
        action="store_true",
        help="Run the slower all-page readiness scan instead of using the manifest's last full scan.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path. The script never writes DuckDB or governance records.",
    )
    args = parser.parse_args(argv)

    report = build_pulse(
        manifest_path=args.manifest,
        generated_at=args.generated_at,
        include_full_readiness=args.include_full_readiness,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
