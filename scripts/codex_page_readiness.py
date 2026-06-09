from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_pnl_attribution_business_owner_approval import (  # noqa: E402
    build_status as build_pnl_attribution_approval_status,
)
from scripts.check_balance_analysis_business_owner_approval import (  # noqa: E402
    build_status as build_balance_analysis_approval_status,
)
from scripts.check_ledger_pnl_business_owner_approval import (  # noqa: E402
    build_status as build_ledger_pnl_approval_status,
)
from scripts.check_product_category_pnl_business_owner_approval import (  # noqa: E402
    build_status as build_product_category_pnl_approval_status,
)
from scripts.check_bond_analysis_business_owner_approval import (  # noqa: E402
    build_status as build_bond_analysis_approval_status,
)
from scripts.check_stock_analysis_business_owner_approval import (  # noqa: E402
    build_status as build_stock_analysis_approval_status,
)
from scripts.mcp.moss_project_mcp import (  # noqa: E402
    DEFAULT_DUCKDB_PATH,
    DEFAULT_GOVERNANCE_DIR,
    page_catalog_date_evidence,
    page_evidence_readiness,
    page_governance_audit_review_checklist,
    page_governance_record_validation,
    page_trace_bundle,
    product_page_trace_bundles,
    resolve_path_env,
)


RUN_SUPPORTED_PAGE_SLUGS = (
    "dashboard-home",
    "product-category-pnl",
    "balance-analysis",
    "decision-items",
    "pnl",
    "pnl-bridge",
    "risk-tensor",
    "bond-dashboard",
    "bond-analysis",
    "balance-movement-analysis",
    "ledger-pnl",
    "bank-ledger-dashboard",
    "cashflow-projection",
    "concentration-monitor",
    "team-performance",
    "platform-config",
    "news-events",
    "positions",
    "operations-analysis",
    "liability-analytics",
    "market-data",
    "cross-asset",
    "macro-toolkit",
    "stock-analysis",
    "kpi-performance",
    "average-balance",
    "pnl-attribution",
)
DIRECT_EVIDENCE_PAGE_SLUGS = (
    "product-category-pnl",
    "balance-analysis",
    "risk-tensor",
    "bond-dashboard",
    "bond-analysis",
    "balance-movement-analysis",
)
OPTIONAL_DIRECT_EVIDENCE_PAGE_SLUGS = (
    "pnl-attribution",
    "stock-analysis",
    "cashflow-projection",
    "concentration-monitor",
    "team-performance",
    "news-events",
    "platform-config",
)
GOVERNANCE_STREAM_NAMES = (
    "agent_audit",
    "cache_build_run",
    "cache_manifest",
    "snapshot_manifest",
    "source_manifest",
    "source_manifest_latest",
    "vendor_version_registry",
)


def _gate(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "outcome": "pass" if passed else "block",
        "detail": detail,
    }


def _first_readiness_page(page_slug: str) -> dict[str, Any]:
    bundles = product_page_trace_bundles()
    readiness = page_evidence_readiness(bundles, [page_slug])
    pages = readiness.get("pages") or []
    if not pages:
        raise ValueError(f"No readiness row returned for page slug: {page_slug}")
    return dict(pages[0])


def _governance_stream_paths() -> dict[str, Path]:
    governance_dir = resolve_path_env("MOSS_GOVERNANCE_PATH", DEFAULT_GOVERNANCE_DIR)
    return {
        "agent_audit": governance_dir / "agent_audit.jsonl",
        "cache_build_run": governance_dir / "cache_build_run.jsonl",
        "cache_manifest": governance_dir / "cache_manifest.jsonl",
        "snapshot_manifest": governance_dir / "snapshot_manifest.jsonl",
        "source_manifest": governance_dir / "source_manifest.jsonl",
        "source_manifest_latest": governance_dir / "source_manifest_latest.jsonl",
        "vendor_version_registry": governance_dir / "vendor_version_registry.jsonl",
    }


def _first_payload_page(payload: dict[str, Any], page_slug: str) -> dict[str, Any]:
    pages = payload.get("pages") or []
    if not pages:
        raise ValueError(f"No evidence row returned for page slug: {page_slug}")
    return dict(pages[0])


def _direct_catalog_date_summary(page: dict[str, Any]) -> dict[str, Any]:
    table_evidence = list(page.get("table_evidence") or [])
    present_count = sum(1 for row in table_evidence if row.get("status") in {"present", "present_no_date_column"})
    sampled_count = sum(
        1
        for row in table_evidence
        if row.get("status") == "present" and row.get("available_dates")
    )
    status = (
        "sampled"
        if table_evidence and present_count == len(table_evidence) and sampled_count == len(table_evidence)
        else "incomplete"
    )
    return {
        "status": status,
        "sampled_table_names": list(page.get("sampled_table_names") or []),
        "table_count": len(table_evidence),
        "present_table_count": present_count,
        "date_sampled_table_count": sampled_count,
        "table_evidence": table_evidence,
    }


def _direct_governance_summary(validation_page: dict[str, Any], audit_page: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": validation_page["validation_status"],
        "ready_record_count": int(audit_page.get("ready_record_count") or 0),
        "incomplete_record_count": int(audit_page.get("incomplete_record_count") or 0),
        "direct_record_count": int(audit_page.get("direct_record_count") or 0),
        "expanded_anchor_record_count": int(audit_page.get("expanded_anchor_record_count") or 0),
    }


def _audit_review_summary(audit_page: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": audit_page["audit_review_status"],
        "closure_approved": bool(audit_page["closure_approved"]),
        "checks": list(audit_page.get("checks") or []),
        "next_actions": list(audit_page.get("next_actions") or []),
    }


def _balance_movement_read_model_freshness_gate(duckdb_path: Path) -> dict[str, str]:
    import duckdb

    gate_name = "balance_movement_read_model_freshness"
    path = Path(duckdb_path)
    if not path.exists():
        return _gate(gate_name, False, f"duckdb_missing={path}")

    try:
        conn = duckdb.connect(str(path), read_only=True)
        try:
            movement_latest = _scalar_date(
                conn,
                """
                select max(cast(report_date as varchar))
                from fact_accounting_asset_movement_monthly
                where currency_basis = 'CNX'
                """,
            )
            control_latest = _scalar_date(
                conn,
                """
                select max(cast(report_date as varchar))
                from product_category_pnl_canonical_fact
                where currency = 'CNX'
                  and account_code not like '144020%'
                  and (
                    account_code like '141%'
                    or account_code like '142%'
                    or account_code like '143%'
                    or account_code like '1440101%'
                  )
                """,
            )
        finally:
            conn.close()
    except duckdb.Error as exc:
        return _gate(gate_name, False, f"duckdb_read_failed={exc}")

    detail = (
        f"movement_latest={movement_latest or 'none'}; "
        f"control_latest={control_latest or 'none'}; currency_basis=CNX"
    )
    if control_latest is None:
        return _gate(gate_name, True, f"{detail}; no upstream control-account rows")
    return _gate(
        gate_name,
        movement_latest is not None and movement_latest >= control_latest,
        detail,
    )


def _scalar_date(conn: Any, sql: str) -> str | None:
    row = conn.execute(sql).fetchone()
    if not row or row[0] is None:
        return None
    return str(row[0])


def _governance_record_commands(page_slug: str) -> list[str]:
    commands_by_page = {
        "balance-analysis": [
            "python scripts/emit_balance_analysis_governance_record.py",
            "python scripts/emit_balance_analysis_governance_record.py --write",
        ],
        "ledger-pnl": [
            "python scripts/emit_ledger_pnl_governance_record.py",
            "python scripts/emit_ledger_pnl_governance_record.py --write",
        ],
        "pnl-attribution": [
            "python scripts/emit_pnl_attribution_governance_record.py",
            "python scripts/emit_pnl_attribution_governance_record.py --write",
        ],
        "bond-analysis": [
            "python scripts/emit_bond_analysis_governance_record.py",
            "python scripts/emit_bond_analysis_governance_record.py --write",
        ],
        "stock-analysis": [
            "python scripts/emit_stock_analysis_governance_record.py",
            "python scripts/emit_stock_analysis_governance_record.py --write",
        ],
        "cashflow-projection": [
            "python scripts/emit_cashflow_projection_governance_record.py",
            "python scripts/emit_cashflow_projection_governance_record.py --write",
        ],
        "concentration-monitor": [
            "python scripts/emit_concentration_monitor_governance_record.py",
            "python scripts/emit_concentration_monitor_governance_record.py --write",
        ],
        "team-performance": [
            "python scripts/emit_team_performance_governance_record.py",
            "python scripts/emit_team_performance_governance_record.py --write",
        ],
        "news-events": [
            "python scripts/emit_news_events_governance_record.py",
            "python scripts/emit_news_events_governance_record.py --write",
        ],
        "platform-config": [
            "python scripts/emit_platform_config_governance_record.py",
            "python scripts/emit_platform_config_governance_record.py --write",
        ],
    }
    return commands_by_page.get(page_slug, [])


def _approval_status_commands(page_slug: str) -> list[str]:
    commands_by_page = {
        "balance-analysis": [
            "python scripts/check_balance_analysis_business_owner_approval.py",
            "python scripts/check_balance_analysis_business_owner_approval.py --require-captured",
            "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 "
            "-PageSlug balance-analysis -RequireApprovalCaptured",
        ],
        "ledger-pnl": [
            "python scripts/check_ledger_pnl_business_owner_approval.py",
            "python scripts/check_ledger_pnl_business_owner_approval.py --require-captured",
            "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 "
            "-PageSlug ledger-pnl -RequireApprovalCaptured",
        ],
        "pnl-attribution": [
            "python scripts/check_pnl_attribution_business_owner_approval.py",
            "python scripts/check_pnl_attribution_business_owner_approval.py --require-captured",
            "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 "
            "-PageSlug pnl-attribution -RequireApprovalCaptured",
        ],
        "product-category-pnl": [
            "python scripts/check_product_category_pnl_business_owner_approval.py",
            "python scripts/check_product_category_pnl_business_owner_approval.py --require-captured",
            "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 "
            "-PageSlug product-category-pnl -RequireApprovalCaptured",
        ],
        "bond-analysis": [
            "python scripts/check_bond_analysis_business_owner_approval.py",
            "python scripts/check_bond_analysis_business_owner_approval.py --require-captured",
            "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 "
            "-PageSlug bond-analysis -RequireApprovalCaptured",
        ],
        "stock-analysis": [
            "python scripts/check_stock_analysis_business_owner_approval.py",
            "python scripts/check_stock_analysis_business_owner_approval.py --require-captured",
            "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 "
            "-PageSlug stock-analysis -RequireApprovalCaptured",
        ],
    }
    return commands_by_page.get(page_slug, [])


def _required_commands(page_slug: str) -> list[str]:
    if page_slug not in RUN_SUPPORTED_PAGE_SLUGS:
        return []

    smoke_command = f"powershell -ExecutionPolicy Bypass -File scripts/codex-page-smoke.ps1 -PageSlug {page_slug}"
    if page_slug == "balance-movement-analysis":
        smoke_command = f"{smoke_command} -CheckLive"

    commands = [
        smoke_command,
        f"powershell -ExecutionPolicy Bypass -File scripts/codex-verify-page.ps1 -PageSlug {page_slug} -Run",
    ]
    if page_slug == "pnl-attribution":
        commands.append(
            "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 "
            "-PageSlug pnl-attribution -Run",
        )
    return commands


def _business_owner_approval_status(page_slug: str) -> dict[str, Any] | None:
    if page_slug == "product-category-pnl":
        return build_product_category_pnl_approval_status(
            ROOT / "docs" / "pnl" / "product-category-pnl-business-owner-approval-template.md",
        )
    if page_slug == "balance-analysis":
        return build_balance_analysis_approval_status(
            ROOT / "docs" / "pnl" / "balance-analysis-business-owner-approval-template.md",
        )
    if page_slug == "ledger-pnl":
        return build_ledger_pnl_approval_status(
            ROOT / "docs" / "pnl" / "ledger-pnl-business-owner-approval-template.md",
        )
    if page_slug == "pnl-attribution":
        return build_pnl_attribution_approval_status(
            ROOT / "docs" / "pnl" / "pnl-attribution-business-owner-approval-template.md",
        )
    if page_slug == "bond-analysis":
        return build_bond_analysis_approval_status(
            ROOT / "docs" / "pnl" / "bond-analysis-business-owner-approval-template.md",
        )
    if page_slug == "stock-analysis":
        return build_stock_analysis_approval_status(
            ROOT / "docs" / "pnl" / "stock-analysis-business-owner-approval-template.md",
        )
    return None


def _owner_action_status_count(
    signoff_summary: dict[str, Any],
    canonical_field: str,
    legacy_field: str,
) -> Any:
    return signoff_summary.get(canonical_field, signoff_summary.get(legacy_field))


def _optional_bool(mapping: dict[str, Any], field: str) -> bool | None:
    if field not in mapping:
        return None
    return bool(mapping[field])


def _approval_certification_effect(approval_status: dict[str, Any]) -> Any:
    evidence_scope = approval_status.get("evidence_scope") or {}
    owner_action_scope = approval_status.get("owner_action_status_scope") or {}
    pre_signature_scope = approval_status.get("owner_pre_signature_blocker_scope") or {}
    return evidence_scope.get(
        "certification_effect",
        owner_action_scope.get(
            "certification_effect",
            pre_signature_scope.get("certification_effect"),
        ),
    )


def _captures_product_or_api_decisions(approval_status: dict[str, Any]) -> bool:
    evidence_scope = approval_status.get("evidence_scope") or {}
    owner_action_scope = approval_status.get("owner_action_status_scope") or {}
    pre_signature_scope = approval_status.get("owner_pre_signature_blocker_scope") or {}
    return bool(
        evidence_scope.get(
            "captures_product_or_api_decisions",
            owner_action_scope.get(
                "captures_product_or_api_decisions",
                pre_signature_scope.get("captures_product_or_api_decisions", False),
            ),
        )
    )


def _owner_action_status_scope(approval_status: dict[str, Any]) -> dict[str, Any]:
    scope = approval_status.get("owner_action_status_scope") or {}
    return {
        field: scope[field]
        for field in (
            "scope_kind",
            "missing_or_invalid_item_count",
            "pending_review_item_count",
            "owner_signable",
            "captures_business_owner_approval",
            "captures_product_or_api_decisions",
            "can_promote_certification",
            "certification_effect",
            "boundary",
        )
        if field in scope
    }


def _owner_pre_signature_blocker_scope(approval_status: dict[str, Any]) -> dict[str, Any]:
    return dict(approval_status.get("owner_pre_signature_blocker_scope") or {})


def _generated_artifact_freshness_scope(approval_status: dict[str, Any]) -> dict[str, Any]:
    scope = approval_status.get("generated_artifact_freshness_scope") or {}
    return {
        field: scope[field]
        for field in (
            "scope_kind",
            "artifact_count",
            "valid_artifact_count",
            "stale_or_missing_artifact_count",
            "freshness_check_effect",
            "captures_business_owner_approval",
            "captures_product_or_api_decisions",
            "captures_golden_sample_approval",
            "captures_closure_approval",
            "writes_governance_records",
            "certification_effect",
            "boundary",
        )
        if field in scope
    }


def _golden_sample_approval_artifacts(
    golden_sample_paths: list[str],
    *,
    readiness_boundary_status: str,
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for sample_path in golden_sample_paths:
        approval_path = ROOT / sample_path / "approval.md"
        if not approval_path.exists():
            continue
        text = approval_path.read_text(encoding="utf-8")
        artifact_status = _markdown_code_value(text, "Status") or "unknown"
        artifacts.append(
            {
                "sample_id": _markdown_code_value(text, "Sample ID") or Path(sample_path).name,
                "status": artifact_status,
                "sample_type": _markdown_code_value(text, "Sample type") or "unknown",
                "owner": _markdown_code_value(text, "Owner") or "unknown",
                "approver": _markdown_code_value(text, "Approver") or "unknown",
                "approved_at": _markdown_code_value(text, "Approved at") or "unknown",
                "readiness_boundary_status": readiness_boundary_status,
                "mismatch": (
                    readiness_boundary_status == "approved"
                    and artifact_status != "approved"
                ),
                "artifact_path": f"{sample_path}/approval.md",
            }
        )
    return artifacts


def _golden_sample_boundary_detail(
    readiness_boundary_status: str,
    approval_artifacts: list[dict[str, Any]],
) -> str:
    if readiness_boundary_status != "approved":
        return readiness_boundary_status
    if not approval_artifacts:
        return readiness_boundary_status
    approved = _artifacts_have_full_approval(approval_artifacts)
    statuses = sorted({str(artifact["status"]) for artifact in approval_artifacts})
    return (
        f"{readiness_boundary_status}; "
        f"artifact_status={','.join(statuses)}; "
        f"artifact_approved={str(approved).lower()}"
    )


def _artifacts_have_full_approval(approval_artifacts: list[dict[str, Any]]) -> bool:
    return all(
        artifact.get("status") == "approved"
        and artifact.get("owner") not in {None, "", "TBD", "unknown"}
        and artifact.get("approver") not in {None, "", "TBD", "unknown"}
        and artifact.get("approved_at") not in {None, "", "TBD", "unknown"}
        for artifact in approval_artifacts
    )


def _markdown_code_value(text: str, label: str) -> str | None:
    prefix = f"- {label}: `"
    for line in text.splitlines():
        if line.startswith(prefix) and line.endswith("`"):
            return line[len(prefix) : -1]
    return None


def _direct_evidence_report(page_slug: str) -> dict[str, Any] | None:
    if page_slug not in DIRECT_EVIDENCE_PAGE_SLUGS and page_slug not in OPTIONAL_DIRECT_EVIDENCE_PAGE_SLUGS:
        return None
    bundles = product_page_trace_bundles()
    duckdb_path = resolve_path_env("MOSS_DUCKDB_PATH", DEFAULT_DUCKDB_PATH)
    streams = _governance_stream_paths()
    catalog_page = _first_payload_page(
        page_catalog_date_evidence(bundles, duckdb_path, [page_slug], limit=20),
        page_slug,
    )
    validation_page = _first_payload_page(
        page_governance_record_validation(
            bundles,
            streams,
            [page_slug],
            list(GOVERNANCE_STREAM_NAMES),
            max_results=20,
        ),
        page_slug,
    )
    audit_page = _first_payload_page(
        page_governance_audit_review_checklist(
            bundles,
            streams,
            [page_slug],
            list(GOVERNANCE_STREAM_NAMES),
            max_results=20,
        ),
        page_slug,
    )
    return {
        "catalog_date_evidence": _direct_catalog_date_summary(catalog_page),
        "governance_record_validation": _direct_governance_summary(validation_page, audit_page),
        "audit_review": _audit_review_summary(audit_page),
    }


def seeded_page_slugs() -> tuple[str, ...]:
    slugs_by_page_id: dict[str, str] = {}
    for bundle in product_page_trace_bundles().values():
        slugs_by_page_id.setdefault(str(bundle["page_id"]), str(bundle["page_slug"]))
    return tuple(slugs_by_page_id.values())


def build_page_readiness_report(page_slug: str) -> dict[str, Any]:
    all_page_slugs = seeded_page_slugs()
    if page_slug not in all_page_slugs:
        supported = ", ".join(all_page_slugs)
        raise ValueError(f"Unsupported page slug: {page_slug}. Supported pages: {supported}")

    bundles = product_page_trace_bundles()
    bundle = page_trace_bundle(bundles, page_slug)
    readiness_page = _first_readiness_page(page_slug)
    checks = readiness_page["checks"]
    golden_status = str(checks["golden_sample"]["status"])
    approval_status = str(readiness_page["approval_status"])
    formal_use_allowed = bool(readiness_page["formal_use_allowed"])
    direct_evidence = _direct_evidence_report(page_slug)
    business_owner_approval_status = _business_owner_approval_status(page_slug)
    golden_samples = list(bundle.get("golden_samples", []))
    golden_sample_approval_artifacts = _golden_sample_approval_artifacts(
        golden_samples,
        readiness_boundary_status=golden_status,
    )
    primary_golden_sample_artifact = (
        golden_sample_approval_artifacts[0]
        if golden_sample_approval_artifacts
        else None
    )

    static_gates = [
        _gate(
            "trace_bundle_present",
            checks["trace_bundle"]["status"] == "present",
            str(checks["trace_bundle"]["status"]),
        ),
        _gate(
            "evidence_readiness_explicit",
            readiness_page["approval_status_source"] == "explicit_status_map",
            str(readiness_page["approval_status_source"]),
        ),
        _gate(
            "lineage_mapping_present",
            checks["lineage_mapping"]["status"] == "query_mapping_present",
            str(checks["lineage_mapping"]["status"]),
        ),
        _gate(
            "catalog_date_review_routed",
            checks["catalog_date"]["status"] == "direct_review_required",
            str(checks["catalog_date"]["status"]),
        ),
    ]
    if direct_evidence is not None:
        direct_ready = (
            direct_evidence["governance_record_validation"]["status"]
            == "direct_records_ready_for_audit_review"
        )
        include_direct_gates = page_slug in DIRECT_EVIDENCE_PAGE_SLUGS or direct_ready
    else:
        include_direct_gates = False
    if direct_evidence is not None and include_direct_gates:
        static_gates.extend(
            [
                _gate(
                    "catalog_date_evidence_sampled",
                    direct_evidence["catalog_date_evidence"]["status"] == "sampled",
                    (
                        f"{direct_evidence['catalog_date_evidence']['date_sampled_table_count']}/"
                        f"{direct_evidence['catalog_date_evidence']['table_count']} table date samples"
                    ),
                ),
                _gate(
                    "direct_governance_record_ready",
                    direct_evidence["governance_record_validation"]["status"]
                    == "direct_records_ready_for_audit_review",
                    (
                        f"{direct_evidence['governance_record_validation']['ready_record_count']} ready direct "
                        "record(s)"
                    ),
                ),
            ]
        )
    if page_slug == "balance-movement-analysis":
        static_gates.append(
            _balance_movement_read_model_freshness_gate(
                resolve_path_env("MOSS_DUCKDB_PATH", DEFAULT_DUCKDB_PATH)
            )
        )
    static_gates.extend(
        [
            _gate(
                "golden_sample_boundary",
                _golden_sample_boundary_passes(golden_status, formal_use_allowed),
                _golden_sample_boundary_detail(golden_status, golden_sample_approval_artifacts),
            ),
            _gate(
                "formal_promotion_boundary",
                _formal_promotion_boundary_passes(approval_status, formal_use_allowed),
                f"{approval_status}; formal_use_allowed={str(formal_use_allowed).lower()}",
            ),
        ]
    )
    if business_owner_approval_status is not None:
        approval_captured = bool(business_owner_approval_status["business_owner_approval_captured"])
        static_gates.append(
            _gate(
                "business_owner_approval_status",
                not approval_captured,
                (
                    f"{business_owner_approval_status['approval_status']}; "
                    f"captured={str(approval_captured).lower()}"
                ),
            )
        )
    blocking_gates = [gate["name"] for gate in static_gates if gate["outcome"] != "pass"]
    residual_gaps = _residual_gaps_with_direct_evidence(
        list(readiness_page.get("residual_gaps") or []),
        direct_evidence,
    )
    direct_fields = direct_evidence or {
        "catalog_date_evidence": None,
        "governance_record_validation": None,
        "audit_review": None,
    }
    certification_packet_consistency = (
        business_owner_approval_status.get("certification_packet_consistency")
        if business_owner_approval_status is not None
        else None
    )
    return {
        "page_slug": readiness_page["page_slug"],
        "page_id": readiness_page["page_id"],
        "page_name": readiness_page["page_name"],
        "route": readiness_page["frontend_route"],
        "primary_api": readiness_page["primary_api"],
        "approval_status": approval_status,
        "formal_use_allowed": formal_use_allowed,
        "overall_status": "static-pass" if not blocking_gates else "blocked",
        "static_gates": static_gates,
        "blocking_gates": blocking_gates,
        "catalog_date_evidence": direct_fields["catalog_date_evidence"],
        "governance_record_validation": direct_fields["governance_record_validation"],
        "audit_review": direct_fields["audit_review"],
        "business_owner_approval_status": business_owner_approval_status,
        "certification_packet_consistency": certification_packet_consistency,
        "golden_sample_approval_artifacts": golden_sample_approval_artifacts,
        "golden_sample_approval_artifact_status": (
            primary_golden_sample_artifact["status"]
            if primary_golden_sample_artifact is not None
            else None
        ),
        "golden_sample_approval_artifact_owner": (
            primary_golden_sample_artifact["owner"]
            if primary_golden_sample_artifact is not None
            else None
        ),
        "golden_sample_approval_artifact_approver": (
            primary_golden_sample_artifact["approver"]
            if primary_golden_sample_artifact is not None
            else None
        ),
        "golden_sample_approval_artifact_approved_at": (
            primary_golden_sample_artifact["approved_at"]
            if primary_golden_sample_artifact is not None
            else None
        ),
        "golden_sample_approval_artifact_mismatch": any(
            artifact["mismatch"] for artifact in golden_sample_approval_artifacts
        ),
        "golden_samples": golden_samples,
        "contract_docs": bundle.get("contract_docs", []),
        "supporting_apis": bundle.get("supporting_apis", []),
        "truth_chain": bundle.get("truth_chain", []),
        "verification_focus": bundle.get("verification_focus", []),
        "guardrails": readiness_page.get("guardrails", []),
        "residual_gaps": residual_gaps,
        "required_commands": _required_commands(page_slug),
        "governance_record_commands": _governance_record_commands(page_slug),
        "approval_status_commands": _approval_status_commands(page_slug),
        "run_supported": page_slug in RUN_SUPPORTED_PAGE_SLUGS,
        "boundary": (
            "Static-pass means contract/readiness evidence is routed. Page closure still requires running "
            "the required commands and reviewing browser-visible states when UI behavior changed."
        ),
    }


def _residual_gaps_with_direct_evidence(
    gaps: list[str],
    direct_evidence: dict[str, Any] | None,
) -> list[str]:
    if direct_evidence is None:
        return gaps
    filtered = list(gaps)
    if direct_evidence["catalog_date_evidence"]["status"] == "sampled":
        filtered = [
            gap for gap in filtered
            if gap != "full data-catalog/date review required before page-level closure."
        ]
    if direct_evidence["governance_record_validation"]["status"] == "direct_records_ready_for_audit_review":
        filtered = [
            gap for gap in filtered
            if gap != (
                "direct page-keyed governance records are still required before treating this as proof of a "
                "specific page/API execution."
            )
        ]
    audit_review = direct_evidence["audit_review"]
    if audit_review["status"] == "ready_for_audit_review" and not audit_review["closure_approved"]:
        filtered.append("Business owner approval is still required before closure.")
    return filtered


def build_route_scope_classification_report(
    pages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    seeded_pages = pages if pages is not None else [
        build_page_readiness_report(page_slug) for page_slug in seeded_page_slugs()
    ]
    navigation_routes = _visible_navigation_routes()
    seeded_by_route = _seeded_pages_by_unique_route(seeded_pages)
    navigation_slugs = {_navigation_page_slug(row, seeded_by_route) for row in navigation_routes}
    route_rows = [
        _route_scope_row_from_page(page, page["page_slug"] in navigation_slugs)
        for page in seeded_pages
    ]
    seeded_slugs = {row["page_slug"] for row in route_rows}

    for navigation_route in navigation_routes:
        page_slug = _navigation_page_slug(navigation_route, seeded_by_route)
        if page_slug not in seeded_slugs:
            route_rows.append(_route_scope_row_from_navigation(navigation_route))

    counts = _route_scope_counts(route_rows)
    evidence_pending = [
        row["page_slug"] for row in route_rows if row["classification"] == "evidence-pending"
    ]
    gate_i_gaps = [
        row["page_slug"] for row in route_rows if row["classification"] == "gate-i-gap"
    ]
    certified = [
        row["page_slug"] for row in route_rows if row["classification"] == "business-contract-certified"
    ]
    business_owner_action_signoff_missing_or_invalid_item_count = sum(
        int(row.get("business_owner_action_missing_or_invalid_item_count") or 0)
        for row in route_rows
    )
    business_owner_action_signoff_pending_review_item_count = sum(
        int(row.get("business_owner_action_pending_review_item_count") or 0)
        for row in route_rows
    )

    return {
        "scope": "route-scope-classification",
        "routes": route_rows,
        "summary": {
            "route_count": len(route_rows),
            "seeded_trace_bundle_count": len(seeded_pages),
            "visible_navigation_route_count": len(navigation_routes),
            "visible_unseeded_route_count": sum(
                1 for row in route_rows if row["source"] == "visible_navigation_unseeded"
            ),
            "business_contract_certified_count": counts["business-contract-certified"],
            "evidence_pending_count": counts["evidence-pending"],
            "gate_i_gap_count": counts["gate-i-gap"],
            "frontend_ready_count": counts["frontend-ready"],
            "frontend_only_count": counts["frontend-only"],
            "not_started_count": counts["not-started"],
            "out_of_scope_count": counts["out-of-scope"],
            "unclassified_count": sum(
                1 for row in route_rows if row["classification"] not in _route_scope_labels()
            ),
            "business_owner_action_signoff_missing_or_invalid_item_count": (
                business_owner_action_signoff_missing_or_invalid_item_count
            ),
            "business_owner_action_signoff_pending_review_item_count": (
                business_owner_action_signoff_pending_review_item_count
            ),
        },
        "classification_counts": counts,
        "certification_ready_routes": certified,
        "next_evidence_pending_routes": evidence_pending,
        "next_gate_i_gap_routes": gate_i_gaps,
        "claim_boundary": (
            "No seeded route is business-contract-certified until direct golden approval, "
            "manual audit closure, and captured business-owner approval all exist."
        ),
    }


def _visible_navigation_routes() -> list[dict[str, str]]:
    navigation_path = ROOT / "frontend" / "src" / "mocks" / "navigation.ts"
    text = navigation_path.read_text(encoding="utf-8")
    start = text.index("export const workbenchNavigation")
    end = text.index("export function pathMatchesWorkbenchSection", start)
    navigation_text = text[start:end]
    routes: list[dict[str, str]] = []
    for match in re.finditer(r"\{\s*key:\s*\"(?P<key>[^\"]+)\"(?P<body>.*?)\n\s*\}", navigation_text, re.S):
        body = match.group("body")
        path_match = re.search(r"path:\s*\"([^\"]+)\"", body)
        readiness_match = re.search(r"readiness:\s*\"([^\"]+)\"", body)
        if path_match is None or readiness_match is None:
            continue
        if re.search(r"navigationVisibility:\s*\"hidden\"", body):
            continue
        routes.append(
            {
                "key": match.group("key"),
                "route": path_match.group(1),
                "readiness": readiness_match.group(1),
            }
        )
    return routes


def _navigation_page_slug(
    navigation_route: dict[str, str],
    seeded_by_route: dict[str, dict[str, Any]],
) -> str:
    key = navigation_route["key"]
    mapped = {
        "dashboard": "dashboard-home",
        "market-overview": "market-home",
        "risk-overview": "risk-home",
        "performance-home": "performance-home",
        "reports-center": "reports-home",
    }.get(key)
    if mapped is not None:
        return mapped
    seeded = seeded_by_route.get(navigation_route["route"])
    if seeded is not None:
        return str(seeded["page_slug"])
    return key


def _seeded_pages_by_unique_route(pages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_route: dict[str, list[dict[str, Any]]] = {}
    for page in pages:
        by_route.setdefault(str(page["route"]), []).append(page)
    return {
        route: route_pages[0]
        for route, route_pages in by_route.items()
        if len(route_pages) == 1
    }


def _route_scope_row_from_navigation(navigation_route: dict[str, str]) -> dict[str, Any]:
    return {
        "page_slug": navigation_route["key"],
        "page_id": None,
        "page_name": navigation_route["key"],
        "route": navigation_route["route"],
        "source": "visible_navigation_unseeded",
        "classification": "not-started",
        "blocking_reason": "no_seeded_trace_bundle",
        "approval_status": None,
        "formal_use_allowed": False,
        "overall_status": "unseeded",
        "run_supported": False,
        "visible_navigation_route": True,
        "has_page_contract": False,
        "has_metric_dictionary_evidence": False,
        "has_golden_samples": False,
        "golden_sample_approved": False,
        "golden_sample_boundary_status": "missing",
        "golden_sample_artifact_status": None,
        "golden_sample_artifact_approved": False,
        "golden_sample_artifact_mismatch": False,
        "has_direct_governance_evidence": False,
        "has_governance_record_command": False,
        "audit_review_closure_approved": False,
        "has_approval_checker": False,
        "business_owner_approval_captured": False,
        "certification_packet_consistency_status": None,
        "certification_packet_consistency_missing_marker_count": None,
        "certification_packet_consistency_business_owner_action_signed_item_count": None,
        "certification_packet_consistency_business_owner_action_pending_or_missing_item_count": None,
        "certification_packet_consistency_approves_metric_or_page": False,
        "certification_packet_consistency_owner_signable": False,
        "certification_packet_consistency_can_promote": False,
        "certification_packet_consistency_captures_business_owner_approval": False,
        "certification_packet_consistency_captures_business_owner_signature": False,
        "certification_packet_consistency_captures_product_or_api_decisions": False,
        "certification_packet_consistency_captures_golden_sample_approval": False,
        "certification_packet_consistency_captures_closure_approval": False,
        "certification_packet_consistency_writes_governance_records": False,
        "certification_packet_consistency_verification_commands_rerun_captured": False,
        "certification_packet_consistency_certification_effect": None,
        "business_owner_action_signoff_group_counts": {},
        "business_owner_action_signed_group_counts": {},
        "business_owner_action_pending_or_missing_group_counts": {},
        "business_owner_action_missing_or_invalid_item_count": None,
        "business_owner_action_pending_review_item_count": None,
        "evidence_scope": {},
        "certification_effect": None,
        "captures_product_or_api_decisions": None,
        "owner_action_status_scope": {},
        "generated_artifact_freshness_scope": {},
        "owner_pre_signature_blocker_scope": {},
        "required_commands": [],
        "approval_status_commands": [],
        "residual_gap_count": 1,
    }


def _route_scope_row_from_page(page: dict[str, Any], visible_navigation_route: bool) -> dict[str, Any]:
    golden_sample_approved = _route_scope_golden_sample_approved(page)
    audit_review_closure_approved = bool((page.get("audit_review") or {}).get("closure_approved"))
    approval_status = page.get("business_owner_approval_status") or {}
    business_owner_approval_captured = bool(approval_status.get("business_owner_approval_captured"))
    consistency = page.get("certification_packet_consistency") or {}
    signoff_summary = approval_status.get("business_owner_action_signoff_summary") or {}
    classification, blocking_reason = _classify_route_scope(
        page,
        golden_sample_approved=golden_sample_approved,
        audit_review_closure_approved=audit_review_closure_approved,
        business_owner_approval_captured=business_owner_approval_captured,
    )
    return {
        "page_slug": page["page_slug"],
        "page_id": page["page_id"],
        "page_name": page["page_name"],
        "route": page["route"],
        "source": "seeded_trace_bundle",
        "classification": classification,
        "blocking_reason": blocking_reason,
        "approval_status": page["approval_status"],
        "formal_use_allowed": page["formal_use_allowed"],
        "overall_status": page["overall_status"],
        "run_supported": page["run_supported"],
        "visible_navigation_route": visible_navigation_route,
        "has_page_contract": bool(page.get("contract_docs")),
        "has_metric_dictionary_evidence": _has_metric_dictionary_evidence(page),
        "has_golden_samples": bool(page.get("golden_samples")),
        "golden_sample_approved": golden_sample_approved,
        "golden_sample_boundary_status": _route_scope_golden_sample_boundary_status(page),
        "golden_sample_artifact_status": page.get("golden_sample_approval_artifact_status"),
        "golden_sample_artifact_approved": golden_sample_approved,
        "golden_sample_artifact_mismatch": bool(page.get("golden_sample_approval_artifact_mismatch")),
        "has_direct_governance_evidence": (
            (page.get("governance_record_validation") or {}).get("status")
            == "direct_records_ready_for_audit_review"
        ),
        "has_governance_record_command": bool(page.get("governance_record_commands")),
        "audit_review_closure_approved": audit_review_closure_approved,
        "has_approval_checker": page.get("business_owner_approval_status") is not None,
        "business_owner_approval_captured": business_owner_approval_captured,
        "certification_packet_consistency_status": consistency.get("status"),
        "certification_packet_consistency_missing_marker_count": (
            len(consistency.get("missing_markers") or [])
            if consistency
            else None
        ),
        "certification_packet_consistency_business_owner_action_signed_item_count": consistency.get(
            "business_owner_action_signed_item_count"
        ),
        "certification_packet_consistency_business_owner_action_pending_or_missing_item_count": consistency.get(
            "business_owner_action_pending_or_missing_item_count"
        ),
        "certification_packet_consistency_approves_metric_or_page": _optional_bool(
            consistency,
            "approves_metric_or_page",
        ),
        "certification_packet_consistency_owner_signable": _optional_bool(consistency, "owner_signable"),
        "certification_packet_consistency_can_promote": _optional_bool(consistency, "can_promote_certification"),
        "certification_packet_consistency_captures_business_owner_approval": _optional_bool(
            consistency,
            "captures_business_owner_approval",
        ),
        "certification_packet_consistency_captures_business_owner_signature": _optional_bool(
            consistency,
            "captures_business_owner_signature",
        ),
        "certification_packet_consistency_captures_product_or_api_decisions": _optional_bool(
            consistency,
            "captures_product_or_api_decisions",
        ),
        "certification_packet_consistency_captures_golden_sample_approval": _optional_bool(
            consistency,
            "captures_golden_sample_approval",
        ),
        "certification_packet_consistency_captures_closure_approval": _optional_bool(
            consistency,
            "captures_closure_approval",
        ),
        "certification_packet_consistency_writes_governance_records": _optional_bool(
            consistency,
            "writes_governance_records",
        ),
        "certification_packet_consistency_verification_commands_rerun_captured": _optional_bool(
            consistency,
            "verification_commands_rerun_captured",
        ),
        "certification_packet_consistency_certification_effect": consistency.get("certification_effect"),
        "business_owner_action_signoff_group_counts": dict(signoff_summary.get("signoff_group_counts") or {}),
        "business_owner_action_signed_group_counts": dict(signoff_summary.get("signed_group_counts") or {}),
        "business_owner_action_pending_or_missing_group_counts": dict(
            signoff_summary.get("unsigned_group_counts") or {}
        ),
        "business_owner_action_missing_or_invalid_item_count": _owner_action_status_count(
            signoff_summary,
            "missing_or_invalid_item_count",
            "invalid_or_missing_item_count",
        ),
        "business_owner_action_pending_review_item_count": _owner_action_status_count(
            signoff_summary,
            "pending_review_item_count",
            "pending_item_count",
        ),
        "evidence_scope": dict(approval_status.get("evidence_scope") or {}),
        "certification_effect": _approval_certification_effect(approval_status),
        "captures_product_or_api_decisions": _captures_product_or_api_decisions(approval_status),
        "owner_action_status_scope": _owner_action_status_scope(approval_status),
        "generated_artifact_freshness_scope": _generated_artifact_freshness_scope(approval_status),
        "owner_pre_signature_blocker_scope": _owner_pre_signature_blocker_scope(approval_status),
        "required_commands": list(page.get("required_commands") or []),
        "approval_status_commands": list(page.get("approval_status_commands") or []),
        "residual_gap_count": len(page.get("residual_gaps") or []),
    }


def _route_scope_golden_sample_boundary_status(page: dict[str, Any]) -> str:
    for gate in page.get("static_gates") or []:
        if gate.get("name") == "golden_sample_boundary":
            detail = str(gate.get("detail") or "missing")
            return detail.split(";", 1)[0].strip() or "missing"
    return "missing"


def _route_scope_golden_sample_approved(page: dict[str, Any]) -> bool:
    artifacts = list(page.get("golden_sample_approval_artifacts") or [])
    if not artifacts:
        return False
    return all(
        artifact.get("status") == "approved"
        and artifact.get("owner") not in {None, "", "TBD", "unknown"}
        and artifact.get("approver") not in {None, "", "TBD", "unknown"}
        and artifact.get("approved_at") not in {None, "", "TBD", "unknown"}
        for artifact in artifacts
    )


def _has_metric_dictionary_evidence(page: dict[str, Any]) -> bool:
    evidence_items = (
        list(page.get("contract_docs") or [])
        + list(page.get("truth_chain") or [])
        + list(page.get("verification_focus") or [])
    )
    if any("metric_dictionary" in str(item) or "MTR-" in str(item) for item in evidence_items):
        return True
    for doc_path in page.get("contract_docs") or []:
        path = ROOT / str(doc_path)
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if "metric_dictionary" in text or "MTR-" in text:
            return True
    return False


def _classify_route_scope(
    page: dict[str, Any],
    *,
    golden_sample_approved: bool,
    audit_review_closure_approved: bool,
    business_owner_approval_captured: bool,
) -> tuple[str, str]:
    if _is_business_contract_certified(
        page,
        golden_sample_approved=golden_sample_approved,
        audit_review_closure_approved=audit_review_closure_approved,
        business_owner_approval_captured=business_owner_approval_captured,
    ):
        return "business-contract-certified", "certification_evidence_complete"

    approval_status = str(page["approval_status"])
    if page.get("business_owner_approval_status") is not None and not business_owner_approval_captured:
        return "evidence-pending", "business_owner_approval_pending"
    if approval_status == "gap_or_observational":
        return "gate-i-gap", "route_specific_gate_i_gap"
    if approval_status in {"formal_or_governed", "candidate_or_pending"}:
        return "evidence-pending", "golden_or_manual_audit_or_owner_approval_pending"
    if page["run_supported"]:
        return "frontend-ready", "analysis_surface_not_formal_business_truth"
    return "frontend-only", "home_or_summary_surface_not_page_certification"


def _is_business_contract_certified(
    page: dict[str, Any],
    *,
    golden_sample_approved: bool,
    audit_review_closure_approved: bool,
    business_owner_approval_captured: bool,
) -> bool:
    return (
        page["approval_status"] == "formal_or_governed"
        and page["formal_use_allowed"] is True
        and page["overall_status"] == "static-pass"
        and not page["blocking_gates"]
        and golden_sample_approved
        and audit_review_closure_approved
        and business_owner_approval_captured
    )


def _route_scope_labels() -> tuple[str, ...]:
    return (
        "business-contract-certified",
        "evidence-pending",
        "gate-i-gap",
        "frontend-ready",
        "frontend-only",
        "not-started",
        "out-of-scope",
    )


def _route_scope_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        label: sum(1 for row in rows if row["classification"] == label)
        for label in _route_scope_labels()
    }


def build_all_page_readiness_report() -> dict[str, Any]:
    pages = [build_page_readiness_report(page_slug) for page_slug in seeded_page_slugs()]
    blocked_pages = [page for page in pages if page["blocking_gates"]]
    formal_pages = [page for page in pages if page["approval_status"] == "formal_or_governed"]
    route_scope_classification = build_route_scope_classification_report(pages)
    business_owner_approval_pending_pages = [
        _business_owner_approval_pending_page_summary(page)
        for page in pages
        if (
            page.get("business_owner_approval_status") is not None
            and not page["business_owner_approval_status"]["business_owner_approval_captured"]
        )
    ]
    business_owner_approval_action_item_count = sum(
        len(page["approval_action_items"])
        for page in business_owner_approval_pending_pages
    )
    business_owner_action_signoff_missing_or_invalid_item_count = sum(
        int(page.get("business_owner_action_missing_or_invalid_item_count") or 0)
        for page in business_owner_approval_pending_pages
    )
    business_owner_action_signoff_pending_review_item_count = sum(
        int(page.get("business_owner_action_pending_review_item_count") or 0)
        for page in business_owner_approval_pending_pages
    )
    return {
        "scope": "all-page-readiness",
        "pages": pages,
        "summary": {
            "page_count": len(pages),
            "static_pass_count": sum(1 for page in pages if page["overall_status"] == "static-pass"),
            "blocked_count": len(blocked_pages),
            "formal_or_governed_count": len(formal_pages),
            "mixed_or_candidate_count": len(pages) - len(formal_pages),
            "run_supported_count": sum(1 for page in pages if page["run_supported"]),
            "business_owner_approval_pending_count": len(business_owner_approval_pending_pages),
            "business_owner_approval_action_item_count": business_owner_approval_action_item_count,
            "business_owner_action_signoff_missing_or_invalid_item_count": (
                business_owner_action_signoff_missing_or_invalid_item_count
            ),
            "business_owner_action_signoff_pending_review_item_count": (
                business_owner_action_signoff_pending_review_item_count
            ),
            "route_scope_business_contract_certified_count": (
                route_scope_classification["summary"]["business_contract_certified_count"]
            ),
            "route_scope_evidence_pending_count": (
                route_scope_classification["summary"]["evidence_pending_count"]
            ),
            "route_scope_gate_i_gap_count": (
                route_scope_classification["summary"]["gate_i_gap_count"]
            ),
            "route_scope_unclassified_count": (
                route_scope_classification["summary"]["unclassified_count"]
            ),
        },
        "blocking_pages": [page["page_slug"] for page in blocked_pages],
        "route_scope_classification": route_scope_classification,
        "business_owner_approval_pending_pages": business_owner_approval_pending_pages,
        "approval_status_commands": [
            "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 "
            "-All -RequireApprovalCaptured",
        ],
        "boundary": (
            "All-page readiness covers static contract/readiness evidence for every seeded trace bundle. "
            "Only pages with run_supported=true have local smoke and page-verification commands wired today."
        ),
    }


def _business_owner_approval_pending_page_summary(page: dict[str, Any]) -> dict[str, Any]:
    status = page["business_owner_approval_status"]
    signoff_summary = status.get("business_owner_action_signoff_summary") or {}
    summary = {
        "page_slug": page["page_slug"],
        "page_id": page["page_id"],
        "approval_status": status["approval_status"],
        "business_owner_approval_captured": status["business_owner_approval_captured"],
        "approval_action_item_count": status["approval_action_item_count"],
        "remaining_blockers": list(status["remaining_blockers"]),
        "approval_field_status": dict(status["approval_field_status"]),
        "evidence_scope": dict(status["evidence_scope"]),
        "approval_action_items": list(status["approval_action_items"]),
        "certification_packet_consistency": page.get("certification_packet_consistency"),
        "business_owner_action_signoff_summary": dict(signoff_summary),
        "business_owner_action_signoff_group_counts": dict(signoff_summary.get("signoff_group_counts") or {}),
        "business_owner_action_signed_group_counts": dict(signoff_summary.get("signed_group_counts") or {}),
        "business_owner_action_pending_or_missing_group_counts": dict(
            signoff_summary.get("unsigned_group_counts") or {}
        ),
        "business_owner_action_missing_or_invalid_item_count": _owner_action_status_count(
            signoff_summary,
            "missing_or_invalid_item_count",
            "invalid_or_missing_item_count",
        ),
        "business_owner_action_pending_review_item_count": _owner_action_status_count(
            signoff_summary,
            "pending_review_item_count",
            "pending_item_count",
        ),
        "certification_effect": _approval_certification_effect(status),
        "captures_product_or_api_decisions": _captures_product_or_api_decisions(status),
        "owner_action_status_scope": _owner_action_status_scope(status),
        "generated_artifact_freshness_scope": _generated_artifact_freshness_scope(status),
        "owner_pre_signature_blocker_scope": _owner_pre_signature_blocker_scope(status),
        "golden_sample_boundary_status": _route_scope_golden_sample_boundary_status(page),
        "golden_sample_artifact_status": page.get("golden_sample_approval_artifact_status"),
        "golden_sample_artifact_approved": _route_scope_golden_sample_approved(page),
        "golden_sample_artifact_mismatch": bool(page.get("golden_sample_approval_artifact_mismatch")),
    }
    if "golden_sample_approval_artifact" in status:
        summary["golden_sample_approval_artifact"] = dict(status["golden_sample_approval_artifact"])
    if "closure_checklist_artifact" in status:
        summary["closure_checklist_artifact"] = dict(status["closure_checklist_artifact"])
    if "closure_blocker_triage" in status:
        summary["closure_blocker_triage"] = dict(status["closure_blocker_triage"])
    return summary


def _golden_sample_boundary_passes(status: str, formal_use_allowed: bool) -> bool:
    if formal_use_allowed:
        return status == "approved"
    return status in {"approved", "page_dto_only", "supporting_or_fragment_only", "missing"}


def _formal_promotion_boundary_passes(approval_status: str, formal_use_allowed: bool) -> bool:
    if approval_status == "formal_or_governed":
        return formal_use_allowed
    return not formal_use_allowed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a static MOSS page-readiness gate report.")
    parser.add_argument("--page-slug", choices=seeded_page_slugs(), default="product-category-pnl")
    parser.add_argument("--all", action="store_true", help="Build a batch report for every seeded page.")
    parser.add_argument(
        "--route-scope",
        action="store_true",
        help="Classify seeded and visible navigation routes by certification scope.",
    )
    args = parser.parse_args(argv)

    if args.route_scope:
        report = build_route_scope_classification_report()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.all:
        report = build_all_page_readiness_report()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    report = build_page_readiness_report(args.page_slug)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report["blocking_gates"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
