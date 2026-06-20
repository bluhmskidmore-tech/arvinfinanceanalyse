from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from tests.test_portfolio_home_business_owner_approval_status import _filled_template_text
from tests.test_portfolio_home_owner_decision_intake_check import (
    _rewrite_csv,
    _write_exact_bucket_schema_evidence,
)

from scripts.portfolio_home_owner_handoff_packet import (
    build_markdown,
    _current_status,
    _markdown_sha256,
    _render_packet_markdown,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_owner_handoff_packet.py"
DUCKDB = ROOT / "data" / "moss.duckdb"
TEMPLATE = ROOT / "docs" / "portfolio" / "portfolio-home-business-owner-approval-template.md"


def _risk_tensor_preview_boundary_lines() -> list[str]:
    return [
        "- Risk tensor rematerialization preview: `would_remain_blocked`",
        "- Risk tensor preview writes database: `false`",
        "- Risk tensor preview approves metric or page: `false`",
        "- Risk tensor preview certification effect: `none`",
    ]


def test_portfolio_home_owner_handoff_packet_renders_owner_intake_alignment_blocker() -> None:
    markdown = _render_packet_markdown(
        {
            "page_slug": "portfolio",
            "page_id": "PAGE-PORTFOLIO-HOME-001",
            "report_date": "2026-05-31",
            "current_score": "99.86 / 100",
            "remaining_gap": "0.14",
            "handoff_status": "owner_actions_required",
            "score_blockers": ["owner_decision_intake_alignment_blocked"],
            "score_blocker_action_coverage": {
                "status": "blocked",
                "blockers": ["score_blocker_action_missing:owner_decision_intake_alignment_blocked"],
                "unassigned_blockers": ["owner_decision_intake_alignment_blocked"],
                "covered_blockers": [],
            },
            "blocker_closure_matrix_coverage": {
                "status": "blocked",
                "expected_blockers": ["owner_decision_intake_alignment_blocked"],
                "covered_blockers": ["unexpected_blocker", "unexpected_blocker"],
                "missing_blockers": ["owner_decision_intake_alignment_blocked"],
                "unexpected_blockers": ["unexpected_blocker"],
                "duplicate_blockers": ["unexpected_blocker"],
            },
            "owner_decision_intake_command": (
                "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready"
            ),
            "owner_decision_intake_summary": {
                "intake_status": "ready_for_intake",
                "intake_ready": True,
                "owner_decision_blockers": [],
                "decision_alignment": {"status": "consistent"},
            },
            "owner_decision_intake_alignment": {
                "status": "blocked",
                "blockers": ["owner_decision_intake_alignment_intake_ready_mismatch"],
            },
            "rerun_evidence_status": {
                "status": "valid",
                "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
            },
            "risk_warning_clean_status": {
                "status": "clean",
                "decision_blockers": [],
            },
            "strict_gate_expectations": {
                "summary": "Current strict gates: expected to fail until owner decisions are captured.",
                "full_score_rule": "After owner updates: each strict gate below must exit 0.",
                "commands": [
                    {
                        "command": "python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score",
                        "current_expected_exit": "exit_nonzero",
                        "expected_when_full_score": "exit_0",
                    }
                ],
            },
            "owner_packets": {
                "risk_owner": {"status": "clean", "blockers": [], "actions": [], "decision_intake_artifacts": []},
                "data_owner": {"status": "clean", "blockers": [], "actions": [], "decision_intake_artifacts": []},
                "business_owner": {
                    "status": "blocked",
                    "blockers": ["owner_decision_intake_alignment_blocked"],
                    "actions": [
                        {
                            "blocker": "owner_decision_intake_alignment_blocked",
                            "next_action": (
                                "Reconcile the direct owner-intake evidence and scorecard gate summary "
                                "before full-score activation."
                            ),
                            "evidence_command": (
                                "python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score"
                            ),
                            "exit_criteria": (
                                "Scorecard owner_decision_intake_alignment gate reports status=consistent "
                                "with no blockers."
                            ),
                        }
                    ],
                    "decision_intake_artifacts": [],
                    "approval_field_status": {
                        "approval_date": "captured",
                        "verification_commands_rerun": "captured",
                    },
                },
            },
        }
    )

    assert "- Owner intake evidence alignment: `blocked`" in markdown
    assert (
        "- Owner intake evidence alignment blockers: "
        "`owner_decision_intake_alignment_intake_ready_mismatch`"
    ) in markdown
    assert "- Score blocker action coverage: `blocked`" in markdown
    assert (
        "- Score blocker action coverage blockers: "
        "`score_blocker_action_missing:owner_decision_intake_alignment_blocked`"
    ) in markdown
    assert (
        "- Score blocker action coverage unassigned blockers: "
        "`owner_decision_intake_alignment_blocked`"
    ) in markdown
    assert "- Score blocker action coverage covered blockers: `none`" in markdown
    assert "- Blocker closure matrix coverage: `blocked`" in markdown
    assert (
        "- Blocker closure matrix missing blockers: "
        "`owner_decision_intake_alignment_blocked`"
    ) in markdown
    assert "- Blocker closure matrix unexpected blockers: `unexpected_blocker`" in markdown
    assert "- Blocker closure matrix duplicate blockers: `unexpected_blocker`" in markdown
    assert "- [ ] Business Owner: close `owner_decision_intake_alignment_blocked`" in markdown
    assert (
        "  - Evidence commands: "
        "`python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score`"
    ) in markdown
    assert (
        "  - Exit criteria: Scorecard owner_decision_intake_alignment gate reports status=consistent "
        "with no blockers."
    ) in markdown


def test_portfolio_home_owner_handoff_packet_builds_owner_ready_markdown() -> None:
    markdown = build_markdown(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        docs_root=ROOT / "docs",
        limit=2,
    )

    assert "# Portfolio Home Owner Handoff Packet" in markdown
    assert "- Page: `portfolio` (`PAGE-PORTFOLIO-HOME-001`)" in markdown
    assert "- Report date: `2026-05-31`" in markdown
    assert "- Current score: `99.86 / 100`" in markdown
    assert "- Remaining gap: `0.14`" in markdown
    assert "- Score status: `blocked`" in markdown
    assert "- Handoff status: `owner_actions_required`" in markdown
    assert "- Intake status: `pending_owner_decisions`" in markdown
    assert "- Owner intake ready: `False`" in markdown
    assert (
        "- Owner intake blockers: `krd_owner_decision_missing`, "
        "`maturity_owner_decision_missing`, `business_owner_approval_missing`"
    ) in markdown
    assert "- Approval date status: `missing`" in markdown
    assert "- Verification rerun status: `pending`" in markdown
    assert "- Rerun evidence status: `valid`" in markdown
    assert "- Rerun evidence artifact: `docs/portfolio/portfolio-home-evidence-snapshot.json`" in markdown
    assert "- Risk warning clean status: `blocked`" in markdown
    assert (
        "- Risk warning blockers: `risk_tensor_quality_warning`, "
        "`risk_tensor_warning_mismatch`"
    ) in markdown
    assert "- Risk tensor rematerialization preview: `would_remain_blocked`" in markdown
    assert "- Risk tensor preview would clear: `duration_exclusion_warning_mismatch`" in markdown
    assert "- Risk tensor preview decision status: `blocked`" in markdown
    assert "- Risk tensor preview decision blockers: `risk_tensor_quality_warning`" in markdown
    assert "- Risk tensor preview writes database: `false`" in markdown
    assert "- Risk tensor preview approves metric or page: `false`" in markdown
    assert "- Risk tensor preview certification effect: `none`" in markdown
    assert "- Business owner approval boundary: `pending_owner_input`" in markdown
    assert "- Template approval captured: `false`" in markdown
    assert "- Formal authorization allowed: `false`" in markdown
    assert "- Governance write allowed: `false`" in markdown
    assert "- Page execution proven: `false`" in markdown
    assert "- Full score closure ready: `false`" in markdown
    assert "- Certification effect: `none`" in markdown
    assert "- Handoff approves metric or page: `false`" in markdown
    assert "- Handoff writes governance records: `false`" in markdown
    assert "- Handoff captures business-owner approval: `false`" in markdown
    assert (
        "- Business owner approval boundary blockers: `business_owner_approval_not_captured`, "
        "`scorecard_full_score_not_ready`, `scorecard_score_status_not_ready`, "
        "`owner_decision_intake_not_ready`, `risk_warning_not_clean`"
    ) in markdown
    assert "- Decision alignment: `consistent`" in markdown
    assert "- Owner intake evidence alignment: `consistent`" in markdown
    assert "- Owner intake evidence alignment blockers: `none`" in markdown
    assert "- Score blocker action coverage: `clean`" in markdown
    assert "- Score blocker action coverage blockers: `none`" in markdown
    assert "- Score blocker action coverage unassigned blockers: `none`" in markdown
    assert (
        "- Score blocker action coverage covered blockers: `risk_tensor_quality_warning`, "
        "`krd_contract_decision_required`, `bond_maturity_date_remediation_required`, "
        "`tyw_liability_maturity_date_remediation_required`, "
        "`duration_exclusion_warning_mismatch`, `risk_tensor_warning_mismatch`, "
        "`business_owner_approval`, `owner_decision_intake_blocked`"
    ) in markdown
    assert "- Blocker closure matrix coverage: `clean`" in markdown
    assert "- Blocker closure matrix missing blockers: `none`" in markdown
    assert "- Blocker closure matrix unexpected blockers: `none`" in markdown
    assert "- Blocker closure matrix duplicate blockers: `none`" in markdown
    assert "- Activation boundary: no automatic approval; owner decisions must be captured and rechecked." in markdown
    assert (
        "- Generated owner fields boundary: KRD and maturity export manifests require "
        "`generated_owner_fields_must_be_blank=true`; dependency consistency blocks missing, false, "
        "or pre-filled generated owner fields."
    ) in markdown
    assert (
        "- Owner intake CSV summary: `krd_summary_row_count=3`, "
        "`krd_detail_row_count=500`, `bond_missing_maturity_row_count=114`, "
        "`tyw_liability_missing_maturity_row_count=1455`."
    ) in markdown
    assert (
        "- Owner intake blank-field status: `krd_owner_decision_fields_blank=true`, "
        "`maturity_owner_fields_blank=true`."
    ) in markdown
    assert (
        "- Manifest generated-owner boundary status: "
        "`krd_contract_decision_manifest=true`, `maturity_remediation_manifest=true`."
    ) in markdown
    assert (
        "- Generated export system-field current gate: "
        "`generated_export_system_fields_must_be_current=true`."
    ) in markdown
    assert (
        "- Export current summary: `krd_status=current`, `krd_current=true`, "
        "`maturity_status=current`, `maturity_current=true`."
    ) in markdown
    assert "- Export current blockers: `none`." in markdown
    assert (
        "- Export current boundary: current export system fields prove package freshness only; "
        "they do not approve KRD decisions, maturity remediation, signed exclusions, "
        "or business-owner closure."
    ) in markdown
    assert (
        "- Closure artifact presence check reports `status=current`, `current=true`, and no blockers."
    ) in markdown
    assert "## Owner Quickstart" in markdown
    assert (
        "- Quickstart boundary: fill owner-controlled fields only; do not edit generated system fields."
    ) in markdown
    assert "- Risk Owner quickstart:" in markdown
    assert (
        "  - Close: `risk_tensor_quality_warning`, `risk_tensor_warning_mismatch`, "
        "`krd_contract_decision_required`"
    ) in markdown
    assert (
        "  - Fill/review: `docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_summary.csv`; "
        "`docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv`; "
        "`docs/portfolio/krd-contract-decision/2026-05-31/nearest_bucket_approval_evidence.json`; "
        "`docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json`"
    ) in markdown
    assert "  - Required fields: `risk_owner_decision`, `decision_notes`" in markdown
    assert (
        "  - Conditional fields (`approve_nearest_bucket` only): "
        "`risk_owner_name`, `risk_owner_approval_date`, `risk_owner_approved`, "
        "`business_owner_name`, `business_owner_acknowledgement_date`, `business_owner_acknowledged`, "
        "`metric_contract_decision_recorded`, `verification_rerun_matched`"
    ) in markdown
    assert (
        "  - Conditional fields (`require_exact_bucket_schema` only): "
        "`metric_contract_owner_name`, `metric_contract_update_date`, `metric_contract_updated`, "
        "`api_schema_owner_name`, `api_schema_update_date`, `api_schema_updated`, "
        "`risk_tensor_owner_name`, `risk_tensor_rematerialization_date`, `risk_tensor_rematerialized`, "
        "`verifier_name`, `verification_rerun_date`, `verification_rerun_matched`"
    ) in markdown
    assert "- Data Owner quickstart:" in markdown
    assert (
        "  - Close: `bond_maturity_date_remediation_required`, "
        "`tyw_liability_maturity_date_remediation_required`, "
        "`duration_exclusion_warning_mismatch`"
    ) in markdown
    assert (
        "  - Fill/review: `docs/portfolio/maturity-remediation/2026-05-31/bond_missing_maturity.csv`; "
        "`docs/portfolio/maturity-remediation/2026-05-31/tyw_liability_missing_maturity.csv`; "
        "`docs/portfolio/maturity-remediation/2026-05-31/maturity_scoped_exclusion_evidence.json`"
    ) in markdown
    assert "  - Required fields: `proposed_maturity_date`, `owner_decision`, `owner_comment`" in markdown
    assert (
        "  - Conditional fields (`approve_scoped_exclusion` only): "
        "`data_owner_name`, `data_owner_approval_date`, `data_owner_approved`, "
        "`risk_owner_name`, `risk_owner_countersign_date`, `risk_owner_countersigned`, "
        "`business_owner_name`, `business_owner_acknowledgement_date`, "
        "`business_owner_acknowledged`, `verification_rerun_matched`"
    ) in markdown
    assert "- Business Owner quickstart:" in markdown
    assert "  - Close: `business_owner_approval`, `owner_decision_intake_blocked`" in markdown
    assert "## Blocker Closure Matrix" in markdown
    assert "| Blocker | Owner | Fill / Evidence | Recheck | Exit Signal |" in markdown
    assert (
        "| `risk_tensor_quality_warning` | `risk_owner` | "
        "`risk_warning_consistency` (`parsed_warnings`, `recomputed_warnings`, "
        "`duration_exclusion_delta_detail`, `warning_resolution_matrix`, "
        "`decision_blockers`) | "
        "`python scripts/portfolio_home_risk_warning_consistency.py --require-clean`; "
        "`python scripts/portfolio_home_full_closure_evidence.py --require-clean` | "
        "Risk tensor quality is clean for report_date 2026-05-31 and strict "
        "full-closure evidence no longer reports this blocker. |"
    ) in markdown
    assert (
        "| `krd_contract_decision_required` | `risk_owner` | "
        "`docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_summary.csv`; "
        "`docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv`; "
        "`docs/portfolio/krd-contract-decision/2026-05-31/nearest_bucket_approval_evidence.json`; "
        "`docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json` | "
        "`python scripts/portfolio_home_krd_remap_review_queue.py --require-clean`; "
        "`python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready` | "
        "Risk-owner KRD decision is captured with notes for every scoped row, "
        "conditional nearest-bucket or exact-bucket evidence is valid when selected, "
        "and the KRD strict gate exits 0. |"
    ) in markdown
    assert (
        "| `bond_maturity_date_remediation_required` | `data_owner` | "
        "`docs/portfolio/maturity-remediation/2026-05-31/bond_missing_maturity.csv`; "
        "`docs/portfolio/maturity-remediation/2026-05-31/maturity_scoped_exclusion_evidence.json` | "
        "`python scripts/portfolio_home_maturity_remediation_queue.py --require-empty`; "
        "`python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready` | "
        "Bond missing-maturity rows are remediated at source or covered by a signed scoped exclusion "
        "evidence file, and the maturity strict gate exits 0. |"
    ) in markdown
    assert (
        "| `tyw_liability_maturity_date_remediation_required` | `data_owner` | "
        "`docs/portfolio/maturity-remediation/2026-05-31/tyw_liability_missing_maturity.csv`; "
        "`docs/portfolio/maturity-remediation/2026-05-31/maturity_scoped_exclusion_evidence.json` | "
        "`python scripts/portfolio_home_maturity_remediation_queue.py --require-empty`; "
        "`python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready` | "
        "TYW liability missing-maturity rows are remediated at source or covered by a signed scoped "
        "exclusion evidence file, and the maturity strict gate exits 0. |"
    ) in markdown
    assert (
        "| `business_owner_approval` | `business_owner` | "
        "`docs/portfolio/portfolio-home-business-owner-approval-template.md` | "
        "`python scripts/check_portfolio_home_business_owner_approval.py --require-captured`; "
        "`python scripts/portfolio_home_business_owner_approval_packet.py --limit 3 --require-ready`; "
        "`python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score` | "
        "Business-owner approval is signed, risk-owner countersignature is present, "
        "evidence scope approves the page, and the full scorecard strict gate exits 0. |"
    ) in markdown
    assert (
        "| `owner_decision_intake_blocked` | `business_owner` | "
        "`docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_summary.csv`; "
        "`docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv`; "
        "`docs/portfolio/krd-contract-decision/2026-05-31/nearest_bucket_approval_evidence.json`; "
        "`docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json`; "
        "`docs/portfolio/maturity-remediation/2026-05-31/bond_missing_maturity.csv`; "
        "`docs/portfolio/maturity-remediation/2026-05-31/tyw_liability_missing_maturity.csv`; "
        "`docs/portfolio/maturity-remediation/2026-05-31/maturity_scoped_exclusion_evidence.json`; "
        "`docs/portfolio/portfolio-home-business-owner-approval-template.md` | "
        "`python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready` | "
        "Risk-owner CSV decisions, nearest-bucket or exact-bucket evidence, "
        "data-owner CSV decisions, scoped-exclusion evidence, and business-owner approval "
        "are reconciled, and the owner decision intake strict gate exits 0. |"
    ) in markdown
    assert "## Owner Checklist" in markdown
    assert (
        "- [ ] Risk Owner: close `risk_tensor_quality_warning`, "
        "`risk_tensor_warning_mismatch`, `krd_contract_decision_required`"
    ) in markdown
    assert (
        "  - Evidence commands: `python scripts/portfolio_home_risk_warning_consistency.py --require-clean`; "
        "`python scripts/portfolio_home_krd_remap_review_queue.py --require-clean`"
    ) in markdown
    assert (
        "  - Exit criteria: Risk warning clean gate exits 0 and full-closure evidence no longer reports "
        "risk_tensor_quality_warning; Risk warning clean gate exits 0 with no risk tensor warning mismatch; "
        "KRD review queue exits 0 under the approved contract and the metric contract records the decision."
    ) in markdown
    assert (
        "  - Artifacts: `docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_summary.csv`; "
        "`docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv`; "
        "`docs/portfolio/krd-contract-decision/2026-05-31/nearest_bucket_approval_evidence.json`; "
        "`docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json`"
    ) in markdown
    assert "  - Workload: KRD owner decision fields across 503 rows (summary 3, detail 500)." in markdown
    assert "  - Current gaps: KRD owner decision missing on 503 rows (summary 3, detail 500)." in markdown
    assert "  - Artifact fields to review/fill: `risk_owner_decision`, `decision_notes`" in markdown
    assert (
        "  - Conditional artifact fields (`approve_nearest_bucket` only): "
        "`risk_owner_name`, `risk_owner_approval_date`, `risk_owner_approved`, "
        "`business_owner_name`, `business_owner_acknowledgement_date`, `business_owner_acknowledged`, "
        "`metric_contract_decision_recorded`, `verification_rerun_matched`"
    ) in markdown
    assert (
        "  - Conditional artifact fields (`require_exact_bucket_schema` only): "
        "`metric_contract_owner_name`, `metric_contract_update_date`, `metric_contract_updated`, "
        "`api_schema_owner_name`, `api_schema_update_date`, `api_schema_updated`, "
        "`risk_tensor_owner_name`, `risk_tensor_rematerialization_date`, `risk_tensor_rematerialized`, "
        "`verifier_name`, `verification_rerun_date`, `verification_rerun_matched`"
    ) in markdown
    assert (
        "  - Allowed decisions: `approve_nearest_bucket`, `require_exact_bucket_schema`, `reject`"
    ) in markdown
    assert (
        "  - Notes required for: `approve_nearest_bucket`, "
        "`require_exact_bucket_schema`, `reject`"
    ) in markdown
    assert (
        "- [ ] Data Owner: close `bond_maturity_date_remediation_required`, "
        "`tyw_liability_maturity_date_remediation_required`, "
        "`duration_exclusion_warning_mismatch`"
    ) in markdown
    assert (
        "  - Evidence commands: `python scripts/portfolio_home_maturity_remediation_queue.py --require-empty`; "
        "`python scripts/portfolio_home_risk_warning_consistency.py --require-consistent`\n"
        "  - Exit criteria: Bond maturity remediation queue is empty or signed exclusion evidence is captured "
        "and surfaced as a boundary; TYW liability maturity remediation queue is empty or signed exclusion "
        "evidence is captured and surfaced as a boundary; Risk warning consistency reports matching parsed "
        "and recomputed duration-exclusion evidence.\n"
        "  - Artifacts: `docs/portfolio/maturity-remediation/2026-05-31/bond_missing_maturity.csv`; "
        "`docs/portfolio/maturity-remediation/2026-05-31/tyw_liability_missing_maturity.csv`; "
        "`docs/portfolio/maturity-remediation/2026-05-31/maturity_scoped_exclusion_evidence.json`"
    ) in markdown
    assert "  - Workload: maturity remediation fields across 1569 rows (bond 114, TYW liability 1455)." in markdown
    assert (
        "  - Current gaps: maturity owner decision missing on 1569 rows "
        "(bond 114, TYW liability 1455)."
    ) in markdown
    assert (
        "  - Artifact fields to review/fill: `proposed_maturity_date`, `owner_decision`, `owner_comment`"
    ) in markdown
    assert (
        "  - Conditional artifact fields (`approve_scoped_exclusion` only): "
        "`data_owner_name`, `data_owner_approval_date`, `data_owner_approved`, "
        "`risk_owner_name`, `risk_owner_countersign_date`, `risk_owner_countersigned`, "
        "`business_owner_name`, `business_owner_acknowledgement_date`, "
        "`business_owner_acknowledged`, `verification_rerun_matched`"
    ) in markdown
    assert (
        "  - Allowed decisions: `remediate_source`, `approve_scoped_exclusion`, `reject`"
    ) in markdown
    assert (
        "  - Notes required for: `remediate_source`, "
        "`approve_scoped_exclusion`, `reject`"
    ) in markdown
    assert "- [ ] Business Owner: close `business_owner_approval`, `owner_decision_intake_blocked`" in markdown
    assert (
        "  - Exit criteria: Approval checker exits 0 and evidence_scope.approves_metric_or_page is true; "
        "Owner decision intake strict gate exits 0 and reports intake_ready=true."
    ) in markdown
    assert (
        "  - Artifact fields to review/fill: `approval_status`, `business_owner_name`, `risk_owner_name`, "
        "`approval_decision`, `approval_date`, `business_owner_signature`, `risk_owner_signature`, "
        "`krd_contract_decision`, `maturity_data_decision`, `risk_tensor_warning_decision`, `evidence_scope`"
    ) in markdown
    assert "  - Allowed decisions: `approve`" in markdown
    assert (
        "  - Dependent decision notes required for: `approve_nearest_bucket`, "
        "`approve_scoped_exclusion`, `reject`, `request_changes`"
    ) in markdown
    assert "- [ ] Re-run intake and strict scorecard commands after owner updates are captured." in markdown
    assert "## Strict Gate Expectations" in markdown
    assert "- Activation boundary state: `pending_owner_input`" in markdown
    assert (
        "- Current strict gates: expected to fail until owner decisions, maturity remediation/exclusion, "
        "and business approval are captured."
    ) in markdown
    assert (
        "- After owner updates: each strict gate below must exit 0 before `/portfolio` can claim full closure."
    ) in markdown
    assert (
        "- `python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready`: "
        "currently `exit_nonzero`; after updates `exit_0`."
    ) in markdown
    assert (
        "- `python scripts/portfolio_home_business_owner_approval_packet.py --limit 3 --require-ready`: "
        "currently `exit_nonzero`; after updates `exit_0`."
    ) in markdown
    assert (
        "- `python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score`: "
        "currently `exit_nonzero`; after updates `exit_0`."
    ) in markdown
    assert "## Risk Owner" in markdown
    assert "`risk_tensor_quality_warning`" in markdown
    assert "`krd_contract_decision_required`" in markdown
    assert (
        "- KRD decision scale: `20Y` maps to `krd_30y` across 39 rows with "
        "DV01 23598290.06912522; `2Y` maps to `krd_3y` across 301 rows with "
        "DV01 9195343.60983627; `6M` maps to `krd_1y` across 282 rows "
        "(160 non-zero DV01 rows) with DV01 571392.61874547."
    ) in markdown
    assert "docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_summary.csv" in markdown
    assert "Allowed decisions: `approve_nearest_bucket`, `require_exact_bucket_schema`, `reject`" in markdown
    assert "## Data Owner" in markdown
    assert "`bond_maturity_date_remediation_required`" in markdown
    assert "`tyw_liability_maturity_date_remediation_required`" in markdown
    assert (
        "- Maturity decision scale: bond queue has 114 missing maturity rows "
        "with market value 37622164239.83000008; TYW liability queue has "
        "1455 missing maturity rows with principal 43822652393.01000002."
    ) in markdown
    assert "docs/portfolio/maturity-remediation/2026-05-31/bond_missing_maturity.csv" in markdown
    assert "Allowed decisions: `remediate_source`, `approve_scoped_exclusion`, `reject`" in markdown
    assert "## Business Owner" in markdown
    assert "`business_owner_approval`" in markdown
    assert "docs/portfolio/portfolio-home-business-owner-approval-template.md" in markdown
    assert "## Recheck Commands" in markdown
    assert "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready" in markdown
    assert "python scripts/portfolio_home_business_owner_approval_packet.py --limit 3 --require-ready" in markdown
    assert "python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score" in markdown
    assert "python scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current" in markdown


def test_portfolio_home_owner_handoff_packet_cli_writes_markdown(tmp_path: Path) -> None:
    output = tmp_path / "owner-handoff.md"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--limit",
            "1",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 0
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "# Portfolio Home Owner Handoff Packet" in content
    assert "`99.86 / 100`" in content
    assert "owner_actions_required" in content
    assert str(output) in completed.stdout


def test_portfolio_home_owner_handoff_packet_cli_check_current_passes_matching_markdown(
    tmp_path: Path,
) -> None:
    output = tmp_path / "owner-handoff.md"
    expected_markdown = build_markdown(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        docs_root=ROOT / "docs",
        limit=1,
    )
    output.write_text(expected_markdown, encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--limit",
            "1",
            "--output",
            str(output),
            "--docs-root",
            str(ROOT / "docs"),
            "--check-current",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload == {
        "artifact": str(output),
        "status": "current",
        "expected_length": len(expected_markdown),
        "actual_length": len(expected_markdown),
        "expected_sha256": _markdown_sha256(expected_markdown),
        "actual_sha256": _markdown_sha256(expected_markdown),
    }


def test_portfolio_home_owner_handoff_packet_current_status_requires_boundary_lines(
    tmp_path: Path,
) -> None:
    output = tmp_path / "owner-handoff.md"
    markdown_without_boundary = "\n".join(
        [
            "# Portfolio Home Owner Handoff Packet",
            "",
            "## Summary",
            "- Page: `portfolio` (`PAGE-PORTFOLIO-HOME-001`)",
            "- Report date: `2026-05-31`",
        ],
    )
    output.write_text(markdown_without_boundary, encoding="utf-8")

    status = _current_status(output, markdown_without_boundary)

    assert status == {
        "artifact": str(output),
        "status": "invalid_semantics",
        "expected_length": len(markdown_without_boundary),
        "actual_length": len(markdown_without_boundary),
        "expected_sha256": _markdown_sha256(markdown_without_boundary),
        "actual_sha256": _markdown_sha256(markdown_without_boundary),
        "semantic_status": "blocked",
        "missing_required_fragments": [
            "- Business owner approval boundary: `",
            "- Template approval captured: `",
            "- Formal authorization allowed: `",
            "- Governance write allowed: `",
            "- Page execution proven: `",
            "- Full score closure ready: `",
            "- Certification effect: `",
            "- Handoff approves metric or page: `",
            "- Handoff writes governance records: `",
            "- Handoff captures business-owner approval: `",
            "- Risk tensor rematerialization preview: `",
            "- Risk tensor preview writes database: `",
            "- Risk tensor preview approves metric or page: `",
            "- Risk tensor preview certification effect: `",
            "- Business owner approval boundary blockers: ",
            "- Activation boundary: no automatic approval; owner decisions must be captured and rechecked.",
            "- Generated owner fields boundary: ",
            "- Generated export system-field current gate: ",
            "- Export current summary: ",
            "- Export current blockers: ",
            "- Export current boundary: ",
            "- Activation boundary state: `",
            "- Owner intake evidence alignment: `",
            "- Score blocker action coverage: `",
            "- Blocker closure matrix coverage: `",
            "- Closure artifact presence check reports `status=current`, `current=true`, and no blockers.",
            "- `python scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current`",
            "## Owner Quickstart",
            "- Quickstart boundary: fill owner-controlled fields only; do not edit generated system fields.",
            "- Risk Owner quickstart:",
            "- Data Owner quickstart:",
            "- Business Owner quickstart:",
        ],
    }


def test_portfolio_home_owner_handoff_packet_current_status_rejects_activation_ready_conflict(
    tmp_path: Path,
) -> None:
    output = tmp_path / "owner-handoff.md"
    contradictory_markdown = "\n".join(
        [
            "# Portfolio Home Owner Handoff Packet",
            "- Business owner approval boundary: `pending_owner_input`",
            "- Template approval captured: `false`",
            "- Formal authorization allowed: `false`",
            "- Governance write allowed: `false`",
            "- Page execution proven: `false`",
            "- Full score closure ready: `false`",
            "- Certification effect: `none`",
            "- Handoff approves metric or page: `false`",
            "- Handoff writes governance records: `false`",
            "- Handoff captures business-owner approval: `false`",
            *_risk_tensor_preview_boundary_lines(),
            "- Business owner approval boundary blockers: `business_owner_approval_not_captured`",
            "- Activation boundary: no automatic approval; owner decisions must be captured and rechecked.",
            "- Generated owner fields boundary: `generated_owner_fields_must_be_blank=true`",
            "- Generated export system-field current gate: `generated_export_system_fields_must_be_current=true`",
            "- Export current summary: `krd_status=current`, `krd_current=true`, `maturity_status=current`, `maturity_current=true`",
            "- Export current blockers: `none`",
            "- Export current boundary: current export system fields prove package freshness only; they do not approve KRD decisions, maturity remediation, signed exclusions, or business-owner closure.",
            "## Owner Quickstart",
            "- Quickstart boundary: fill owner-controlled fields only; do not edit generated system fields.",
            "- Risk Owner quickstart:",
            "- Data Owner quickstart:",
            "- Business Owner quickstart:",
            "- Activation boundary state: `pending_owner_input`",
            "- Current strict gates: expected to exit 0; full closure evidence is ready.",
            "- Owner intake evidence alignment: `consistent`",
            "- Score blocker action coverage: `clean`",
            "- Blocker closure matrix coverage: `clean`",
            "- Closure artifact presence check reports `status=current`, `current=true`, and no blockers.",
            "- `python scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current`",
        ],
    )
    output.write_text(contradictory_markdown, encoding="utf-8")

    status = _current_status(output, contradictory_markdown)

    assert status == {
        "artifact": str(output),
        "status": "invalid_semantics",
        "expected_length": len(contradictory_markdown),
        "actual_length": len(contradictory_markdown),
        "expected_sha256": _markdown_sha256(contradictory_markdown),
        "actual_sha256": _markdown_sha256(contradictory_markdown),
        "semantic_status": "blocked",
        "semantic_conflicts": [
            "activation_state_not_activated_but_summary_claims_ready",
        ],
    }


def test_portfolio_home_owner_handoff_packet_current_status_rejects_ambiguous_activation_state(
    tmp_path: Path,
) -> None:
    output = tmp_path / "owner-handoff.md"
    ambiguous_markdown = "\n".join(
        [
            "# Portfolio Home Owner Handoff Packet",
            "- Business owner approval boundary: `pending_owner_input`",
            "- Template approval captured: `false`",
            "- Formal authorization allowed: `false`",
            "- Governance write allowed: `false`",
            "- Page execution proven: `false`",
            "- Full score closure ready: `false`",
            "- Certification effect: `none`",
            "- Handoff approves metric or page: `false`",
            "- Handoff writes governance records: `false`",
            "- Handoff captures business-owner approval: `false`",
            *_risk_tensor_preview_boundary_lines(),
            "- Business owner approval boundary blockers: `business_owner_approval_not_captured`",
            "- Activation boundary: no automatic approval; owner decisions must be captured and rechecked.",
            "- Generated owner fields boundary: `generated_owner_fields_must_be_blank=true`",
            "- Generated export system-field current gate: `generated_export_system_fields_must_be_current=true`",
            "- Export current summary: `krd_status=current`, `krd_current=true`, `maturity_status=current`, `maturity_current=true`",
            "- Export current blockers: `none`",
            "- Export current boundary: current export system fields prove package freshness only; they do not approve KRD decisions, maturity remediation, signed exclusions, or business-owner closure.",
            "## Owner Quickstart",
            "- Quickstart boundary: fill owner-controlled fields only; do not edit generated system fields.",
            "- Risk Owner quickstart:",
            "- Data Owner quickstart:",
            "- Business Owner quickstart:",
            "- Activation boundary state: `activated`",
            "- Activation boundary state: `pending_owner_input`",
            "- Current strict gates: expected to fail until rerun evidence and business-owner activation boundary are both clean.",
            "- Owner intake evidence alignment: `consistent`",
            "- Score blocker action coverage: `clean`",
            "- Blocker closure matrix coverage: `clean`",
            "- Closure artifact presence check reports `status=current`, `current=true`, and no blockers.",
            "- `python scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current`",
        ],
    )
    output.write_text(ambiguous_markdown, encoding="utf-8")

    status = _current_status(output, ambiguous_markdown)

    assert status == {
        "artifact": str(output),
        "status": "invalid_semantics",
        "expected_length": len(ambiguous_markdown),
        "actual_length": len(ambiguous_markdown),
        "expected_sha256": _markdown_sha256(ambiguous_markdown),
        "actual_sha256": _markdown_sha256(ambiguous_markdown),
        "semantic_status": "blocked",
        "semantic_conflicts": [
            "activation_state_ambiguous",
        ],
    }


def test_portfolio_home_owner_handoff_packet_current_status_rejects_conflicting_strict_gate_summaries(
    tmp_path: Path,
) -> None:
    output = tmp_path / "owner-handoff.md"
    conflicting_markdown = "\n".join(
        [
            "# Portfolio Home Owner Handoff Packet",
            "- Business owner approval boundary: `pending_owner_input`",
            "- Template approval captured: `false`",
            "- Formal authorization allowed: `false`",
            "- Governance write allowed: `false`",
            "- Page execution proven: `false`",
            "- Full score closure ready: `false`",
            "- Certification effect: `none`",
            "- Handoff approves metric or page: `false`",
            "- Handoff writes governance records: `false`",
            "- Handoff captures business-owner approval: `false`",
            *_risk_tensor_preview_boundary_lines(),
            "- Business owner approval boundary blockers: `business_owner_approval_not_captured`",
            "- Activation boundary: no automatic approval; owner decisions must be captured and rechecked.",
            "- Generated owner fields boundary: `generated_owner_fields_must_be_blank=true`",
            "- Generated export system-field current gate: `generated_export_system_fields_must_be_current=true`",
            "- Export current summary: `krd_status=current`, `krd_current=true`, `maturity_status=current`, `maturity_current=true`",
            "- Export current blockers: `none`",
            "- Export current boundary: current export system fields prove package freshness only; they do not approve KRD decisions, maturity remediation, signed exclusions, or business-owner closure.",
            "## Owner Quickstart",
            "- Quickstart boundary: fill owner-controlled fields only; do not edit generated system fields.",
            "- Risk Owner quickstart:",
            "- Data Owner quickstart:",
            "- Business Owner quickstart:",
            "- Activation boundary state: `pending_owner_input`",
            "- Current strict gates: expected to exit 0; full closure evidence is ready.",
            "- Current strict gates: expected to fail until rerun evidence and business-owner activation boundary are both clean.",
            "- Owner intake evidence alignment: `consistent`",
            "- Score blocker action coverage: `clean`",
            "- Blocker closure matrix coverage: `clean`",
            "- Closure artifact presence check reports `status=current`, `current=true`, and no blockers.",
            "- `python scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current`",
        ],
    )
    output.write_text(conflicting_markdown, encoding="utf-8")

    status = _current_status(output, conflicting_markdown)

    assert status == {
        "artifact": str(output),
        "status": "invalid_semantics",
        "expected_length": len(conflicting_markdown),
        "actual_length": len(conflicting_markdown),
        "expected_sha256": _markdown_sha256(conflicting_markdown),
        "actual_sha256": _markdown_sha256(conflicting_markdown),
        "semantic_status": "blocked",
        "semantic_conflicts": [
            "strict_gate_summary_ambiguous",
            "activation_state_not_activated_but_summary_claims_ready",
        ],
    }


def test_portfolio_home_owner_handoff_packet_cli_check_current_fails_stale_markdown(
    tmp_path: Path,
) -> None:
    output = tmp_path / "owner-handoff.md"
    expected_markdown = build_markdown(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        docs_root=ROOT / "docs",
        limit=1,
    )
    output.write_text("# stale packet\n", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--limit",
            "1",
            "--output",
            str(output),
            "--docs-root",
            str(ROOT / "docs"),
            "--check-current",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload == {
        "artifact": str(output),
        "status": "stale",
        "expected_length": len(expected_markdown),
        "actual_length": len("# stale packet\n"),
        "expected_sha256": _markdown_sha256(expected_markdown),
        "actual_sha256": _markdown_sha256("# stale packet\n"),
    }


def test_portfolio_home_owner_handoff_packet_current_status_hashes_same_length_stale_content(
    tmp_path: Path,
) -> None:
    output = tmp_path / "owner-handoff.md"
    expected_markdown = "abc"
    output.write_text("abd", encoding="utf-8")

    status = _current_status(output, expected_markdown)

    assert status == {
        "artifact": str(output),
        "status": "stale",
        "expected_length": 3,
        "actual_length": 3,
        "expected_sha256": _markdown_sha256("abc"),
        "actual_sha256": _markdown_sha256("abd"),
    }
    assert status["expected_sha256"] != status["actual_sha256"]


def test_portfolio_home_owner_handoff_packet_rejects_negative_limit() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--limit", "-1"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 2
    assert "Portfolio-home owner handoff packet limit must be non-negative: -1" in completed.stderr


def test_portfolio_home_owner_handoff_packet_build_rejects_negative_limit() -> None:
    try:
        build_markdown(
            duckdb_path=DUCKDB,
            report_date="2026-05-31",
            template_path=TEMPLATE,
            docs_root=ROOT / "docs",
            limit=-1,
        )
    except ValueError as exc:
        assert str(exc) == "Portfolio-home owner handoff packet limit must be non-negative: -1"
    else:
        raise AssertionError("negative owner handoff packet limit should be rejected")


def test_portfolio_home_owner_handoff_packet_reports_krd_note_gaps(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="approve_nearest_bucket",
            maturity_decision="approve_scoped_exclusion",
            decision_notes=(
                "Risk owner accepts nearest-bucket mapping; data owner signs scoped exclusion for "
                "current candidate review only."
            ),
        ),
        encoding="utf-8",
    )

    krd_dir = docs_root / "portfolio" / "krd-contract-decision" / "2026-05-31"
    _rewrite_csv(
        krd_dir / "krd_remap_summary.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "approve_nearest_bucket",
            "decision_notes": "",
        },
    )
    _rewrite_csv(
        krd_dir / "krd_remap_detail.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "approve_nearest_bucket",
            "decision_notes": "",
        },
    )

    maturity_dir = docs_root / "portfolio" / "maturity-remediation" / "2026-05-31"
    _rewrite_csv(
        maturity_dir / "bond_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "approve_scoped_exclusion",
            "owner_comment": "Signed exclusion for current candidate review only.",
        },
    )
    _rewrite_csv(
        maturity_dir / "tyw_liability_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "approve_scoped_exclusion",
            "owner_comment": "Signed exclusion for current candidate review only.",
        },
    )

    markdown = build_markdown(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert "  - Current note gaps: KRD `approve_nearest_bucket` decision notes missing on 503 rows." in markdown


def test_portfolio_home_owner_handoff_packet_reports_maturity_comment_gaps(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="require_exact_bucket_schema",
            maturity_decision="approve_scoped_exclusion",
            decision_notes="Data owner signs scoped exclusion for current candidate review only.",
        ),
        encoding="utf-8",
    )

    krd_dir = docs_root / "portfolio" / "krd-contract-decision" / "2026-05-31"
    _rewrite_csv(
        krd_dir / "krd_remap_summary.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "require_exact_bucket_schema",
        },
    )
    _rewrite_csv(
        krd_dir / "krd_remap_detail.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "require_exact_bucket_schema",
        },
    )
    _write_exact_bucket_schema_evidence(docs_root)

    maturity_dir = docs_root / "portfolio" / "maturity-remediation" / "2026-05-31"
    _rewrite_csv(
        maturity_dir / "bond_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "approve_scoped_exclusion",
            "owner_comment": "",
        },
    )
    _rewrite_csv(
        maturity_dir / "tyw_liability_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "approve_scoped_exclusion",
            "owner_comment": "",
        },
    )

    markdown = build_markdown(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert (
        "  - Current comment gaps: maturity `approve_scoped_exclusion` owner comments "
        "missing on 1569 rows."
    ) in markdown


def test_portfolio_home_owner_handoff_packet_reports_multi_decision_krd_note_gaps(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="approve_nearest_bucket",
            maturity_decision="approve_scoped_exclusion",
            decision_notes="Data owner signs scoped exclusion for current candidate review only.",
        ),
        encoding="utf-8",
    )

    row_number = 0

    def mixed_krd(row: dict[str, str]) -> dict[str, str]:
        nonlocal row_number
        decision = "approve_nearest_bucket" if row_number % 2 == 0 else "reject"
        row_number += 1
        return {
            **row,
            "risk_owner_decision": decision,
            "decision_notes": "",
        }

    krd_dir = docs_root / "portfolio" / "krd-contract-decision" / "2026-05-31"
    _rewrite_csv(krd_dir / "krd_remap_summary.csv", mixed_krd)
    _rewrite_csv(krd_dir / "krd_remap_detail.csv", mixed_krd)

    maturity_dir = docs_root / "portfolio" / "maturity-remediation" / "2026-05-31"
    _rewrite_csv(
        maturity_dir / "bond_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "approve_scoped_exclusion",
            "owner_comment": "Signed exclusion for current candidate review only.",
        },
    )
    _rewrite_csv(
        maturity_dir / "tyw_liability_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "approve_scoped_exclusion",
            "owner_comment": "Signed exclusion for current candidate review only.",
        },
    )

    markdown = build_markdown(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert (
        "  - Current note gaps: KRD `approve_nearest_bucket` decision notes missing "
        "on 252 rows; KRD `reject` decision notes missing on 251 rows."
    ) in markdown


def test_portfolio_home_owner_handoff_packet_reports_multi_decision_maturity_comment_gaps(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="require_exact_bucket_schema",
            maturity_decision="approve_scoped_exclusion",
            decision_notes="Data owner signs scoped exclusion for current candidate review only.",
        ),
        encoding="utf-8",
    )

    krd_dir = docs_root / "portfolio" / "krd-contract-decision" / "2026-05-31"
    _rewrite_csv(
        krd_dir / "krd_remap_summary.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "require_exact_bucket_schema",
        },
    )
    _rewrite_csv(
        krd_dir / "krd_remap_detail.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "require_exact_bucket_schema",
        },
    )
    _write_exact_bucket_schema_evidence(docs_root)

    row_number = 0

    def mixed_maturity(row: dict[str, str]) -> dict[str, str]:
        nonlocal row_number
        decision = "approve_scoped_exclusion" if row_number % 2 == 0 else "reject"
        row_number += 1
        return {
            **row,
            "owner_decision": decision,
            "owner_comment": "",
        }

    maturity_dir = docs_root / "portfolio" / "maturity-remediation" / "2026-05-31"
    _rewrite_csv(maturity_dir / "bond_missing_maturity.csv", mixed_maturity)
    _rewrite_csv(maturity_dir / "tyw_liability_missing_maturity.csv", mixed_maturity)

    markdown = build_markdown(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert (
        "  - Current comment gaps: maturity `approve_scoped_exclusion` owner comments "
        "missing on 785 rows; maturity `reject` owner comments missing on 784 rows."
    ) in markdown


def test_portfolio_home_owner_handoff_packet_surfaces_rejected_owner_decisions(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="reject",
            maturity_decision="reject",
            decision_notes="Risk owner and data owner reject the current closure boundary.",
        ),
        encoding="utf-8",
    )

    krd_dir = docs_root / "portfolio" / "krd-contract-decision" / "2026-05-31"
    _rewrite_csv(
        krd_dir / "krd_remap_summary.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "reject",
            "decision_notes": "Rejected current nearest-bucket KRD contract.",
        },
    )
    _rewrite_csv(
        krd_dir / "krd_remap_detail.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "reject",
            "decision_notes": "Rejected current nearest-bucket KRD contract.",
        },
    )

    maturity_dir = docs_root / "portfolio" / "maturity-remediation" / "2026-05-31"
    _rewrite_csv(
        maturity_dir / "bond_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "reject",
            "owner_comment": "Rejected current maturity remediation boundary.",
        },
    )
    _rewrite_csv(
        maturity_dir / "tyw_liability_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "reject",
            "owner_comment": "Rejected current maturity remediation boundary.",
        },
    )

    markdown = build_markdown(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert "- Owner intake blockers: `krd_owner_decision_rejected`, `maturity_owner_decision_rejected`" in markdown
    assert (
        "- Blockers: `risk_tensor_quality_warning`, `risk_tensor_warning_mismatch`, "
        "`krd_contract_decision_required`, `krd_owner_decision_rejected`"
    ) in markdown
    assert (
        "- Blockers: `bond_maturity_date_remediation_required`, "
        "`tyw_liability_maturity_date_remediation_required`, "
        "`duration_exclusion_warning_mismatch`, `maturity_owner_decision_rejected`"
    ) in markdown
