from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "docs" / "portfolio" / "portfolio-home-full-closure-sign-off-packet.md"
TEMPLATE = ROOT / "docs" / "portfolio" / "portfolio-home-business-owner-approval-template.md"
AUDIT = ROOT / "docs" / "audits" / "2026-06-05-portfolio-readiness-gate-audit.md"
SNAPSHOT = ROOT / "docs" / "portfolio" / "portfolio-home-evidence-snapshot.json"
OPTION_B_NOTE = ROOT / "docs" / "portfolio" / "portfolio-home-option-b-execution-note.md"
KRD_OWNER_SUMMARY = "docs/portfolio/krd-contract-decision/2026-05-31/owner_summary.md"
MATURITY_OWNER_SUMMARY = "docs/portfolio/maturity-remediation/2026-05-31/owner_summary.md"
CURRENT_SCORE_BLOCKERS = (
    "risk_tensor_quality_warning",
    "krd_contract_decision_required",
    "bond_matured_outstanding_reconciliation_required",
    "tyw_liability_maturity_date_remediation_required",
    "business_owner_approval",
    "owner_decision_intake_blocked",
)
CURRENT_SCORE_BLOCKERS_MARKDOWN = ", ".join(
    f"`{blocker}`" for blocker in CURRENT_SCORE_BLOCKERS
)


def test_portfolio_home_signoff_packet_preserves_candidate_boundary() -> None:
    text = PACKET.read_text(encoding="utf-8")

    assert "# Portfolio Home Full-Closure Sign-Off Packet" in text
    assert "PAGE-PORTFOLIO-HOME-001" in text
    assert "`portfolio`" in text
    assert "`frontend aggregation: module-home/portfolio`" in text
    assert "`candidate_or_pending`" in text
    assert "Formal use allowed: `formal_use_allowed=false`" in text
    assert "Closure approved: `closure_approved=false`" in text
    assert "Current closure score: `99.86 / 100`" in text
    assert "Remaining full-score gap: `0.14`" in text
    assert "Do not promote `/portfolio` to decision-grade page closure." in text
    assert "Do not restate same-day risk-date closure as full risk-tensor closure." in text
    assert "Do not turn `quality_flag=warning` into `quality_flag=ok` without rematerialized evidence." in text
    assert "Do not use frontend fill, inferred maturity dates, or synthetic KRD buckets as approval evidence." in text
    assert "## Evidence Scope" in text
    assert "- `approves_metric_or_page=false`" in text
    assert "- `writes_governance_records=false`" in text
    assert "- `proves_capture_ready_page_execution=false`" in text
    assert "- `captures_business_owner_approval=false`" in text
    assert "- `certification_effect=none`" in text


def test_portfolio_home_signoff_packet_documents_real_data_blockers() -> None:
    text = PACKET.read_text(encoding="utf-8")

    for required in (
        "quality_flag=warning",
        "portfolio_dv01=106224411.96420395",
        "krd_sum=106224411.96420395",
        "Non-standard tenor buckets remapped to nearest KRD bucket: 20Y, 2Y, 6M",
        "missing_maturity_rows=114",
        "missing_maturity_market_value=37622164239.83000008",
        "position_scope=liability",
        "currency_basis=CNY",
        "row_count=3071",
        "missing_maturity_rows=1455",
        "missing_maturity_principal=43822652393.01000002",
        "2Y: all_rows=301, nonzero_dv01_rows=301, all_market_value=48919869887.65000000",
        "KRD remap scope, non-zero DV01 rows:",
        "6M: all_rows=282, nonzero_dv01_rows=160, all_market_value=62550571662.68000010",
        "20Y: all_rows=39, nonzero_dv01_rows=39, all_market_value=22035562498.29000004",
        "200004, dv01=8246445.66600614, tenor_bucket=20Y, mapped_to=krd_30y",
        "Risk warning consistency: `warning_consistency_status=consistent`",
        "Risk warning decision status: `decision_status=blocked`",
        "consistency_blockers=none",
        "decision_blockers=risk_tensor_quality_warning",
        "duration_exclusion parsed row_count=120, market_value_sum=39109594105.50000008",
        "duration_exclusion recomputed row_count=120, market_value_sum=39109594105.50000008",
        "Bond matured-outstanding sample, order by market_value desc:",
        "J12006190202, maturity_date=2023-06-19, days_past_maturity=1077, market_value=463596800.00000000",
    ):
        assert required in text
    assert "Bond missing maturity sample, order by market_value desc:" not in text


def test_portfolio_home_signoff_packet_lists_full_score_gates_without_approval() -> None:
    text = PACKET.read_text(encoding="utf-8")

    assert "## Full-Score Closure Gates" in text
    assert "Gate 1: KRD contract decision." in text
    assert "Gate 2: maturity data remediation and matured-outstanding reconciliation." in text
    assert "Gate 3: capture-ready page governance." in text
    assert "Gate 4: business-owner approval." in text
    assert "Handoff status: `ready_for_risk_and_business_owner_review_pending_signature`" in text
    assert "Approval action item count: `19`" in text
    assert "This handoff does not capture approval" in text
    assert "Full closure still requires KRD contract decision" in text
    assert (
        "Full closure still requires KRD contract decision, TYW maturity remediation or signed exclusion scope, "
        "matured-bond source reconciliation, risk-warning reconciliation/rematerialization, capture-ready page "
        "evidence, business-owner approval, and owner-decision intake reconciliation."
    ) in text
    assert "python scripts/portfolio_home_full_closure_evidence.py" in text
    assert "python scripts/portfolio_home_full_closure_evidence.py --require-clean" in text
    assert "python scripts/portfolio_home_risk_warning_consistency.py --require-consistent" in text
    assert "python scripts/portfolio_home_risk_warning_consistency.py --require-clean" in text
    assert "python scripts/portfolio_home_krd_remap_review_queue.py" in text
    assert "python scripts/portfolio_home_krd_remap_review_queue.py --require-clean" in text
    assert "python scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision" in text
    assert "python scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision --require-clean" in text
    assert "python scripts/portfolio_home_maturity_remediation_queue.py" in text
    assert "python scripts/portfolio_home_maturity_remediation_queue.py --require-empty" in text
    assert "python scripts/portfolio_home_matured_outstanding_queue.py" in text
    assert "python scripts/portfolio_home_maturity_remediation_export.py --output-dir docs/portfolio/maturity-remediation" in text
    assert "python scripts/portfolio_home_maturity_remediation_export.py --output-dir docs/portfolio/maturity-remediation --require-clean" in text
    assert "python scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current" in text
    assert "python scripts/portfolio_home_evidence_packet_guard.py --require-clean" in text
    assert "python scripts/portfolio_home_closure_scorecard.py --limit 3" in text
    assert "python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score" in text
    assert "python scripts/portfolio_home_evidence_snapshot.py --scorecard-limit 1 --verifier-limit 1 --require-verifier-matched" in text
    assert "python scripts/portfolio_home_owner_action_packet.py --limit 3" in text
    assert "python scripts/portfolio_home_owner_action_packet.py --limit 3 --require-clean" in text
    assert "python scripts/portfolio_home_business_owner_approval_packet.py --limit 3" in text
    assert "python scripts/portfolio_home_business_owner_approval_packet.py --limit 3 --require-ready" in text
    assert "python scripts/portfolio_home_dependency_consistency_check.py --limit 3" in text
    assert "python scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent" in text
    assert "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3" in text
    assert "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready" in text
    assert "Score methodology is `discrete_full_closure_gate`; the `0.14` gap is not allocated across blockers as linear weights." in text
    assert "Closure scorecard reports `score_status=blocked` and `full_score_ready=false`." in text
    assert "Closure scorecard strict full-score gate exits non-zero while score blockers remain." in text
    assert f"Closure scorecard blockers: {CURRENT_SCORE_BLOCKERS_MARKDOWN}." in text
    assert "Closure scorecard action map records `owner`, `next_action`, `evidence_command`, and `exit_criteria` for every score blocker." in text
    assert "Closure scorecard gates carry `score_blocker_action_coverage.status=clean`; unknown or unassigned score blockers prevent strict activation." in text
    assert "Closure scorecard emits `verification_commands` with evidence, strict-gate, and regression commands plus expected blocked-state exits." in text
    assert "Scorecard command verifier supports both `--expected-state blocked` and `--expected-state full_score`; current evidence should match only the blocked-state strict-gate expectations." in text
    assert "Closure scorecard gates carry KRD `decision_options`/`review_actions` and maturity `remediation_scope`/`remediation_actions`." in text
    assert "Closure scorecard gates carry risk tensor quality/source summary, KRD remap scale, and maturity missing-row amount summaries." in text
    assert "Closure scorecard gates now carry `owner_decision_intake` with intake status, owner statuses, decision alignment, decision gaps, note/comment gaps, and nearest-bucket approval or exact-bucket schema evidence." in text
    assert "Closure scorecard owner-decision intake gate now exposes `owner_input_boundary`, and `owner_decision_intake_alignment.compared_fields` includes it to prevent generated-owner boundaries drifting from direct intake evidence." in text
    assert "Closure scorecard gates carry `approval_dependency_consistency`; stale or mismatched KRD/maturity manifests add `approval_dependency_consistency_blocked` and prevent `full_score_ready=true`." in text
    assert "Closure scorecard `approval_dependency_consistency` gate also exposes `generated_owner_fields_boundaries` so missing manifest acceptance criteria is visible without opening manifest details." in text
    assert "Closure scorecard treats owner-decision intake as the final full-score guard: if all upstream gates are clean but intake is not ready, `owner_decision_intake_blocked` prevents `full_score_ready=true`." in text
    assert "Closure scorecard has a positive full-score regression path, but the current real template keeps full-closure scope disabled." in text
    assert "Evidence snapshot reports `snapshot_kind=portfolio_home_closure_evidence`, `score_status=blocked`, `full_score_ready=false`, and an embedded verifier status of `matched_expected_blocked_state`." in text
    assert "Evidence snapshot summarizes the current gate statuses without changing the score: full closure blocked, risk warning decision blocked, KRD contract decision required, maturity remediation blocked, and business-owner approval pending." in text
    assert "Evidence snapshot gate summary now exposes `owner_decision_intake_status=pending`, `owner_decision_intake_ready=false`, and the current owner-decision blockers." in text
    assert "Evidence snapshot gate summary now exposes `approval_dependency_consistency_status=consistent`, dependency blockers, and `generated_owner_fields_boundaries` from the scorecard gate." in text
    assert "Evidence snapshot now embeds `business_owner_approval_packet_summary` with `packet_status=pending`, `activation_ready=false`, `approval_action_item_count=19`, and `dependency_consistency_status=consistent`." in text
    assert "Evidence snapshot also exposes `csv_check_summary` with KRD summary/detail row counts, maturity queue row counts, and blank owner/proposed-field status." in text
    assert "Evidence snapshot now exposes `owner_decision_intake_summary` with `intake_status=pending_owner_decisions`, three pending owner statuses, and the current owner-decision blockers." in text
    assert "Evidence snapshot owner-decision intake summary also exposes `csv_check_summary` and `generated_owner_fields_boundaries`, so intake reviewers see queue row counts and generated-owner boundaries without opening the dependency check." in text
    assert "Evidence snapshot owner-decision intake summary also exposes `owner_input_boundary`, so filled owner CSV fields are visible as owner input rather than generated approval evidence." in text
    assert "Evidence snapshot now exposes `scorecard_owner_decision_intake_gate_summary` and `owner_decision_intake_alignment` so direct intake evidence is checked against the full-score gate view." in text
    assert "Evidence snapshot scorecard owner-decision gate summary now carries `owner_input_boundary`, and the alignment comparison includes it." in text
    assert "Evidence snapshot now exposes `score_blocker_action_coverage` in the gate summary and business-owner approval summary." in text
    assert "Evidence snapshot now exposes `owner_summary_paths` with the KRD contract decision owner summary and maturity remediation owner summary." in text
    assert "Evidence snapshot now exposes `generated_owner_fields_boundaries` so reviewers can see both KRD and maturity export manifests require `generated_owner_fields_must_be_blank=true`." in text
    assert "Evidence snapshot now exposes `decision_gap_counts` with KRD owner decision gaps of 503 rows (summary 3, detail 500) and maturity owner decision gaps of 1455 rows (bond 0, TYW liability 1455)." in text
    assert "Evidence snapshot now exposes `note_gap_counts`; current real CSVs have blank owner decisions, so note/comment gaps are empty until a decision is filled without rationale." in text
    assert "Evidence snapshot now exposes `exact_bucket_schema_evidence` so reviewers can see whether the exact-bucket schema path has metric-contract, API-schema, rematerialization, and verifier evidence." in text
    assert "Owner action packet reports `handoff_status=owner_actions_required` and groups the current blockers into `risk_owner`, `data_owner`, and `business_owner` packets." in text
    assert "Owner action packet reports `assignment_coverage.status=clean`; `unassigned_blockers`, `duplicate_assigned_blockers`, and `unexpected_assigned_blockers` are empty." in text
    assert "Owner action packet strict clean gate also requires `score_blocker_action_coverage.status=clean`." in text
    assert "Owner action packet carries `dependency_consistency_status=consistent` and the same `csv_check_summary` into risk-owner, data-owner, and business-owner packets." in text
    assert "Owner handoff Markdown summary surfaces the same CSV row counts, blank owner-field status, generated-owner manifest boundaries, and export-current system-field gate before the checklist." in text
    assert "Owner handoff Markdown summary states export-current system fields prove package freshness only; they do not approve KRD decisions, maturity remediation, signed exclusions, or business-owner closure." in text
    assert "Owner action packet carries KRD `note_gap_counts`, maturity `comment_gap_counts`, and `exact_bucket_schema_evidence` into the owner packets without changing approval status." in text
    assert "Owner action packet carries `owner_decision_intake_alignment.status=consistent` into the owner packets so owners can see activation evidence alignment before signing." in text
    assert "Owner action packet assigns `risk_tensor_quality_warning` and `krd_contract_decision_required` to the risk-owner packet, the maturity and matured-outstanding blockers to the data-owner packet, and `owner_decision_intake_blocked` to the business-owner packet so no score blocker is left unowned." in text
    assert "Owner action packet strict clean gate exits non-zero while any owner packet remains blocked." in text
    assert "Business owner approval packet reports `packet_status=pending`, `activation_ready=false`, and `approval_action_item_count=19`." in text
    assert "Business owner approval packet lists sign-off, audit, evidence snapshot, owner action, KRD decision export, maturity remediation export, scorecard strict gate, and approval strict gate dependencies." in text
    assert "Business owner approval packet lists the KRD and maturity owner summaries as evidence dependencies, but does not treat them as approvals." in text
    assert "Business owner approval packet activation guard also requires dependency consistency and owner decision intake strict gates before full activation." in text
    assert "Business owner approval packet reports `dependency_consistency_status=consistent` only when the KRD and maturity manifests match the current scorecard report date, blocked status, row counts, and amount totals." in text
    assert "Business owner approval packet also checks the exported CSV row counts and keeps KRD `risk_owner_decision`/`decision_notes` plus maturity `proposed_maturity_date`/`owner_decision`/`owner_comment` fields blank." in text
    assert "Business owner approval packet also carries `note_gap_counts` and `exact_bucket_schema_evidence` into the approval review payload without treating them as approvals." in text
    assert "Business owner approval packet also exposes the scorecard `gates.owner_decision_intake` summary, so approval review can compare direct intake evidence with the full-score gate view." in text
    assert "Business owner approval packet scorecard gate summary also carries `owner_input_boundary`, and activation alignment compares it before approval." in text
    assert "Business owner approval packet also enforces `owner_decision_intake_alignment.status=consistent` before activation." in text
    assert "Business owner approval packet also enforces `score_blocker_action_coverage.status=clean` before activation." in text
    assert "Business owner approval packet also exposes `generated_owner_fields_boundaries`, so the approval entry point itself shows that KRD and maturity exports must keep generated owner fields blank." in text
    assert "Dependency consistency check strict gate exits 0 only when the KRD and maturity manifests plus CSV queues match the current scorecard evidence." in text
    assert "Dependency consistency check also exposes `generated_owner_fields_boundaries` directly, matching the scorecard and business-owner approval packet boundary summary." in text
    assert "CSV summary currently reports `krd_summary_row_count=3`, `krd_detail_row_count=500`, `bond_missing_maturity_row_count=0`, `tyw_liability_missing_maturity_row_count=1455`, and blank owner/proposed fields." in text
    assert "Owner decision intake check reports `intake_status=pending_owner_decisions` and `intake_ready=false` until risk-owner CSV decisions, conditional KRD evidence, data-owner CSV decisions, scoped-exclusion evidence, and business-owner approval are all filled." in text
    assert "Owner decision intake check also exposes `csv_check_summary` and `generated_owner_fields_boundaries` at the top level before owner decisions are accepted." in text
    assert "Owner decision intake check also exposes `owner_input_boundary` so allowed pre-intake owner-field blockers are separated from active dependency blockers." in text
    assert "Owner decision intake strict ready gate exits non-zero in the current real-data state." in text
    assert "KRD manifest consistency checks `remap_tenor_count=3`, `nonzero_dv01_rows=500`, and `dv01_sum=33180977.63634484`." in text
    assert "Maturity manifest consistency checks `bond_missing_maturity_rows=0`, `tyw_liability_missing_maturity_rows=1455`, `bond_missing_maturity_market_value=0`, and `tyw_liability_missing_maturity_principal=43822652393.01000002`." in text
    assert "Business owner approval packet strict ready gate exits non-zero while the template is pending or any full-score blocker remains." in text
    assert "Full-closure evidence script reports `data_quality_status=blocked`." in text
    assert "Full-closure evidence strict clean gate exits non-zero while risk tensor and maturity blockers remain." in text
    assert "Risk warning consistency strict gate exits 0 now that parsed and recomputed duration-exclusion evidence match." in text
    assert "Risk warning clean gate exits non-zero while `quality_flag=warning` remains." in text
    assert "KRD remap review queue reports `review_status=decision_required`." in text
    assert "KRD remap review queue exposes `decision_options=approve_nearest_bucket|require_exact_bucket_schema|reject` and `review_actions` for risk-owner decision." in text
    assert "KRD remap review queue strict clean gate exits non-zero while nearest-bucket approval is pending." in text
    assert "KRD contract decision export writes full risk-owner CSV queues plus a manifest under `docs/portfolio/krd-contract-decision/2026-05-31/`." in text
    assert f"KRD contract decision export also writes the risk-owner summary `{KRD_OWNER_SUMMARY}`." in text
    assert "KRD contract decision owner summary shows `generated_owner_fields_must_be_blank=true` so generated CSV fields cannot be mistaken for captured owner decisions." in text
    assert "KRD contract decision export reports `export_status=decision_required`, `remap_tenor_count=3`, `nonzero_dv01_rows=500`, and `dv01_sum=33180977.63634484`." in text
    assert "KRD contract decision export strict clean gate exits non-zero until the risk-owner decision is captured in the metric contract or exact-bucket schema is implemented." in text
    assert (
        "Maturity remediation queue reports `remediation_status=blocked` because the TYW liability "
        "queue remains non-empty; the bond missing-maturity queue is empty."
    ) in text
    assert "Maturity remediation queue exposes `remediation_scope` and `remediation_actions` for data-owner remediation or signed exclusion." in text
    assert "Maturity remediation queue strict empty gate exits non-zero while missing maturity rows remain." in text
    assert "Maturity remediation export writes full data-owner CSV queues plus a manifest under `docs/portfolio/maturity-remediation/2026-05-31/`." in text
    assert f"Maturity remediation export also writes the data-owner summary `{MATURITY_OWNER_SUMMARY}`." in text
    assert "Maturity remediation owner summary shows `generated_owner_fields_must_be_blank=true` so generated proposed dates or owner decisions cannot be mistaken for remediation evidence." in text
    assert "Maturity remediation export reports `export_status=blocked`, `bond_missing_maturity_rows=0`, `tyw_liability_missing_maturity_rows=1455`, and blank `proposed_maturity_date` fields." in text
    assert "Matured-outstanding queue reports six non-zero matured bond positions" in text
    assert "Maturity remediation export strict clean gate exits non-zero until the source remediation queue is empty or a signed scoped exclusion is captured." in text
    assert "Closure artifact presence check reports `status=current`, `current=true`, and no blockers." in text
    assert "Evidence packet guard requires the evidence snapshot, owner handoff packet, and this sign-off packet to carry the closure artifact presence command and currentness summary." in text
    assert "python scripts/check_portfolio_home_business_owner_approval.py" in text
    assert "python scripts/check_portfolio_home_business_owner_approval.py --require-captured" in text
    assert "python scripts/verify_portfolio_home_scorecard_commands.py --require-matched" in text
    assert "Approval checker supports explicit full-page approval only when `formal_use_allowed=true`, `closure_approved=true`, `approves_metric_or_page=true`, `writes_governance_records=true`, and `proves_capture_ready_page_execution=true` are all captured together." in text
    assert "Approval checker strict captured gate exits non-zero while the template is pending." in text
    assert "Scorecard verification command runner reports `verification_status=matched_expected_blocked_state`." in text


def test_portfolio_home_approval_template_is_pending_only() -> None:
    packet = PACKET.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")

    assert "`docs/portfolio/portfolio-home-business-owner-approval-template.md`" in packet
    assert "# Portfolio Home Business Owner Approval Template" in template
    assert "`PAGE-PORTFOLIO-HOME-001`" in template
    assert "`approval_status=pending`" in template
    assert "Formal use allowed: `formal_use_allowed=false`" in template
    assert "Closure approved: `closure_approved=false`" in template
    assert "This template is not an approval until completed and signed by the business owner and risk owner." in template
    assert "- `approves_metric_or_page=false`" in template
    assert "- `writes_governance_records=false`" in template
    assert "- `proves_capture_ready_page_execution=false`" in template
    assert "- `captures_business_owner_approval=false`" in template
    assert "## Full-Closure Activation Guard" in template
    assert "The default values above keep this template candidate-only." in template
    assert "- `approval_status=approved`" in template
    assert "- `formal_use_allowed=true`" in template
    assert "- `closure_approved=true`" in template
    assert "- `approves_metric_or_page=true`" in template
    assert "- `writes_governance_records=true`" in template
    assert "- `proves_capture_ready_page_execution=true`" in template
    assert "Partial activation is invalid." in template
    assert "python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score" in template
    assert "python scripts/portfolio_home_evidence_snapshot.py --scorecard-limit 1 --verifier-limit 1 --require-verifier-matched" in template
    assert "python scripts/portfolio_home_owner_action_packet.py --limit 3 --require-clean" in template
    assert "python scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent" in template
    assert "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready" in template
    assert "KRD contract decision: `<approve_nearest_bucket | require_exact_bucket_schema | reject>`" in template
    assert "Maturity data decision: `<remediate_source | approve_scoped_exclusion | reject>`" in template
    assert "Risk tensor warning decision: `<keep_warning | approve_after_clean_rerun | request_changes>`" in template
    assert "Business owner signature: `<required>`" in template
    assert "Risk owner signature: `<required>`" in template


def test_portfolio_audit_references_signoff_packet_and_score_boundary() -> None:
    audit = AUDIT.read_text(encoding="utf-8")
    packet = PACKET.read_text(encoding="utf-8")
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    assert "Current score: 99.86 / 100." in audit
    assert "Remaining gap to full score: 0.14." in audit
    assert "Authoritative score blockers from the scorecard:" in audit
    assert (
        "`risk_tensor_quality_warning`, `krd_contract_decision_required`, "
        "`bond_matured_outstanding_reconciliation_required`, "
        "`tyw_liability_maturity_date_remediation_required`, "
        "`business_owner_approval`, and `owner_decision_intake_blocked`"
    ) in audit
    assert "Residual evidence risks, not independent score blockers:" in audit
    assert (
        "GitNexus evidence was unavailable through this Codex App pass and should be rerun "
        "when the MCP surface is exposed; it does not replace or add to the current six score blockers."
    ) in audit
    assert (
        "`GS-PORTFOLIO-HOME-A` remains supporting-only; it proves neither capture-ready "
        "payload parity nor owner approval."
    ) in audit
    assert "docs/portfolio/portfolio-home-full-closure-sign-off-packet.md" in audit
    assert "docs/portfolio/portfolio-home-business-owner-approval-template.md" in audit
    assert "scripts/portfolio_home_full_closure_evidence.py" in audit
    assert "scripts/portfolio_home_risk_warning_consistency.py" in audit
    assert "scripts/portfolio_home_krd_remap_review_queue.py" in audit
    assert "scripts/portfolio_home_krd_contract_decision_export.py" in audit
    assert "scripts/portfolio_home_maturity_remediation_queue.py" in audit
    assert "scripts/portfolio_home_maturity_remediation_export.py" in audit
    assert "scripts/portfolio_home_closure_artifact_presence_check.py" in audit
    assert "scripts/portfolio_home_evidence_packet_guard.py" in audit
    assert "scripts/portfolio_home_closure_scorecard.py" in audit
    assert "scripts/portfolio_home_evidence_snapshot.py" in audit
    assert "scripts/portfolio_home_owner_action_packet.py" in audit
    assert "scripts/portfolio_home_business_owner_approval_packet.py" in audit
    assert "scripts/portfolio_home_dependency_consistency_check.py" in audit
    assert "scripts/portfolio_home_owner_decision_intake_check.py" in audit
    assert (
        "The scorecard combines the full-closure evidence, risk-warning consistency gate, "
        "KRD review queue, maturity remediation queue, matured-outstanding reconciliation gate, "
        "business-owner approval status, "
        "owner-decision intake, approval-dependency consistency, and verification command coverage."
    ) in audit
    assert "The score method is `discrete_full_closure_gate`." in audit
    assert "not a linear sum of blocker weights" in audit
    assert "must not be allocated" in audit
    assert (
        "must not be allocated across `risk_tensor_quality_warning`, "
        "`krd_contract_decision_required`, `bond_matured_outstanding_reconciliation_required`, "
        "`tyw_liability_maturity_date_remediation_required`, "
        "`business_owner_approval`, or `owner_decision_intake_blocked` "
        "as pseudo-precision"
    ) in audit
    assert "The scorecard also emits a machine-readable `verification_commands` list." in audit
    assert "score_blocker_action_coverage.status=clean" in audit
    assert "unknown or unassigned score blockers prevent strict activation" in audit
    assert "portfolio_home_closure_scorecard.py --require-full-score" in audit
    assert "scripts/verify_portfolio_home_scorecard_commands.py --require-matched" in audit
    assert "verification_status=matched_expected_blocked_state" in audit
    assert "portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current" in audit
    assert "portfolio_home_evidence_packet_guard.py --require-clean" in audit
    assert "This proves packet freshness only; it does not approve KRD decisions, maturity remediation, signed exclusions, or business-owner closure." in audit
    assert "The same runner also supports `--expected-state full_score` for future closure reviews." in audit
    assert "full-score strict-gate expectations intentionally mismatch" in audit
    assert "scripts/portfolio_home_evidence_snapshot.py --scorecard-limit 1 --verifier-limit 1 --require-verifier-matched" in audit
    assert "is the compact review entry point" in audit
    assert "snapshot_kind=portfolio_home_closure_evidence" in audit
    assert "it does not approve full closure or change the `99.86 / 100` score" in audit
    assert "business_owner_approval_packet_summary" in audit
    assert "compact snapshot also exposes the business-owner packet status, activation readiness, action-item count, and dependency-consistency status" in audit
    assert "compact snapshot also exposes CSV row-count and blank owner-field status" in audit
    assert "compact snapshot gate summary now exposes `owner_decision_intake_status=pending`, `owner_decision_intake_ready=false`, and the current owner-decision blockers" in audit
    assert "compact snapshot gate summary now exposes `approval_dependency_consistency_status=consistent`, dependency blockers, and `generated_owner_fields_boundaries` from the scorecard gate" in audit
    assert "compact snapshot now exposes `owner_decision_intake_summary` so reviewers can see owner-decision blockers from the first JSON artifact" in audit
    assert "compact snapshot owner-decision intake summary now exposes `csv_check_summary` and `generated_owner_fields_boundaries`, so intake reviewers see queue row counts and generated-owner boundaries without opening the dependency check" in audit
    assert "compact snapshot owner-decision intake summary now exposes `owner_input_boundary`, so filled owner CSV fields are visible as owner input rather than generated approval evidence" in audit
    assert "compact snapshot now exposes `scorecard_owner_decision_intake_gate_summary` and `owner_decision_intake_alignment` so direct intake evidence is checked against the full-score gate view" in audit
    assert "compact snapshot scorecard owner-decision gate summary now carries `owner_input_boundary`, and the alignment comparison includes it" in audit
    assert "compact snapshot now exposes `decision_gap_counts` so reviewers can see KRD owner decision gaps of 503 rows and maturity owner decision gaps of 1455 rows (bond 0, TYW liability 1455) without opening the CSV queues" in audit
    assert "compact snapshot now exposes `note_gap_counts`; current real CSVs have blank owner decisions, so note/comment gaps are empty until a decision is filled without rationale" in audit
    assert "compact snapshot now exposes `exact_bucket_schema_evidence` so reviewers can see whether the exact-bucket schema path has metric-contract, API-schema, rematerialization, and verifier evidence" in audit
    assert "compact snapshot now exposes `score_blocker_action_coverage` in both the gate summary and business-owner approval packet summary" in audit
    assert "compact snapshot now exposes `owner_summary_paths` so reviewers can find KRD and maturity owner summaries without opening the full approval packet" in audit
    assert "compact snapshot now exposes `generated_owner_fields_boundaries`; both KRD and maturity export manifests must carry `generated_owner_fields_must_be_blank=true`" in audit
    assert snapshot["business_owner_approval_packet_summary"]["owner_summary_paths"] == {
        "krd_contract_decision_owner_summary": KRD_OWNER_SUMMARY,
        "maturity_remediation_owner_summary": MATURITY_OWNER_SUMMARY,
    }
    assert "scripts/portfolio_home_owner_action_packet.py --limit 3" in audit
    assert "is the owner handoff entry point" in audit
    assert "groups the remaining blockers into `risk_owner`, `data_owner`, and `business_owner` packets" in audit
    assert "handoff_status=owner_actions_required" in audit
    assert "assignment_coverage.status=clean" in audit
    assert "with no unassigned, duplicate-assigned, or unexpected-assigned blockers" in audit
    assert "owner packets now carry `dependency_consistency_status=consistent` plus the shared CSV summary" in audit
    assert "owner handoff Markdown now surfaces CSV row counts, blank owner-field status, generated-owner manifest boundaries, and export-current system-field gate in the summary before the checklist" in audit
    assert "owner handoff Markdown now states export-current system fields prove package freshness only and do not approve KRD decisions, maturity remediation, signed exclusions, or business-owner closure" in audit
    assert "owner packets now carry KRD `note_gap_counts`, maturity `comment_gap_counts`, and `exact_bucket_schema_evidence` without changing approval status" in audit
    assert "owner packets now carry `owner_decision_intake_alignment.status=consistent` so owners can see activation evidence alignment before signing" in audit
    assert "current owner packets assign `owner_decision_intake_blocked` to the business owner; if dependency drift appears, they also assign `approval_dependency_consistency_blocked`" in audit
    assert "strict clean mode exits non-zero until every owner packet is clean" in audit
    assert "strict clean mode also requires `score_blocker_action_coverage.status=clean`" in audit
    assert "scripts/portfolio_home_business_owner_approval_packet.py --limit 3" in audit
    assert "is the business-owner approval packet entry point" in audit
    assert "packet_status=pending" in audit
    assert "activation_ready=false" in audit
    assert "approval_action_item_count=19" in audit
    assert "dependency_consistency_status=consistent" in audit
    assert "manifest consistency checks block stale or mismatched KRD and maturity exports" in audit
    assert "CSV consistency checks block row-count drift and any prefilled owner/proposed fields in the KRD or maturity export files" in audit
    assert "business-owner approval packet now carries `note_gap_counts` and `exact_bucket_schema_evidence` as review evidence, not approval evidence" in audit
    assert "business-owner approval packet now lists the KRD and maturity owner summaries as dependencies without treating either summary as signed approval" in audit
    assert "business-owner approval packet now exposes the scorecard `gates.owner_decision_intake` summary so approval review can compare direct intake evidence with the full-score gate view" in audit
    assert "business-owner approval packet scorecard gate summary also carries `owner_input_boundary`, and activation alignment compares it before approval" in audit
    assert "business-owner approval packet now enforces `owner_decision_intake_alignment.status=consistent` before activation" in audit
    assert "business-owner approval packet now enforces `score_blocker_action_coverage.status=clean` before activation" in audit
    assert "business-owner approval packet now exposes `generated_owner_fields_boundaries` directly so the approval entry point shows the generated-owner-field blank boundary without relying on the compact snapshot" in audit
    assert "scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent" in audit
    assert "is the standalone approval-dependency consistency gate" in audit
    assert "It now exposes `generated_owner_fields_boundaries` directly, matching the scorecard and business-owner approval packet boundary summary." in audit
    assert "CSV summary currently reports `krd_summary_row_count=3`, `krd_detail_row_count=500`, `bond_missing_maturity_row_count=0`, and `tyw_liability_missing_maturity_row_count=1455`" in audit
    assert "scripts/portfolio_home_owner_decision_intake_check.py --limit 3" in audit
    assert "is the post-owner-entry intake preflight" in audit
    assert "intake_status=pending_owner_decisions" in audit
    assert "It now exposes `csv_check_summary` and `generated_owner_fields_boundaries` at the top level before owner decisions are accepted." in audit
    assert "It now exposes `owner_input_boundary`, separating allowed pre-intake owner-field blockers from active dependency blockers." in audit
    assert "its `--require-ready` mode exits non-zero until all owner decisions are filled and dependency drift is absent" in audit
    assert "KRD report date, export status, remap tenor count, nonzero DV01 row count, and DV01 sum" in audit
    assert "maturity report date, export status, missing row counts, market value, and principal totals" in audit
    assert "no automatic approval, invalid partial activation, and strict scorecard approval gates" in audit
    assert "business-owner activation guard also requires dependency consistency and owner decision intake strict gates" in audit
    assert "scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision" in audit
    assert "is the risk-owner KRD contract decision export entry point" in audit
    assert "docs/portfolio/krd-contract-decision/2026-05-31/" in audit
    assert KRD_OWNER_SUMMARY in audit
    assert "KRD owner summary now shows `generated_owner_fields_must_be_blank=true`" in audit
    assert "export_status=decision_required" in audit
    assert "remap_tenor_count=3" in audit
    assert "nonzero_dv01_rows=500" in audit
    assert "dv01_sum=33180977.63634484" in audit
    assert "risk_owner_decision` fields remain blank" in audit
    assert "scripts/portfolio_home_maturity_remediation_export.py --output-dir docs/portfolio/maturity-remediation" in audit
    assert "is the data-owner remediation export entry point" in audit
    assert "docs/portfolio/maturity-remediation/2026-05-31/" in audit
    assert MATURITY_OWNER_SUMMARY in audit
    assert "maturity owner summary now shows `generated_owner_fields_must_be_blank=true`" in audit
    assert "export_status=blocked" in audit
    assert "current manifest reports `export_status=blocked`, `bond_missing_maturity_rows=0`, and `tyw_liability_missing_maturity_rows=1455`" in audit
    assert "tyw_liability_missing_maturity_rows=1455" in audit
    assert "proposed_maturity_date` fields remain blank" in audit
    assert "Its `score_blocker_actions` output maps each blocker to an owner, next action, evidence command, and exit criteria" in audit
    assert "Its `gates.krd_contract` and `gates.maturity_remediation` entries also carry the queue-level action maps and scope fields." in audit
    assert "Its `gates.owner_decision_intake` entry carries intake status, owner statuses, owner-input boundary, decision alignment, decision gaps, note/comment gaps, and nearest-bucket approval or exact-bucket schema evidence." in audit
    assert "Its owner-decision intake alignment now compares `owner_input_boundary` so scorecard gate summaries cannot silently drop generated-owner-field boundaries." in audit
    assert "Owner-decision intake is also the final full-score guard: if all upstream gates are clean but intake is not ready, `owner_decision_intake_blocked` prevents `full_score_ready=true`." in audit
    assert "Its `gates.approval_dependency_consistency` entry blocks full-score readiness when KRD or maturity export manifests are stale, missing, or mismatched against the current scorecard." in audit
    assert "approval_dependency_consistency_blocked" in audit
    assert "Its `gates.approval_dependency_consistency` entry now exposes `generated_owner_fields_boundaries` so missing or false manifest acceptance criteria is visible from the scorecard gate itself." in audit
    assert "The scorecard now carries the material scale evidence directly in its gate payloads" in audit
    assert "stale 114-row bond warning" in audit
    assert "six-row matured-outstanding bond queue" in audit
    assert "TYW liability missing-maturity principal" in audit
    assert "The full-score path is now test-covered" in audit
    assert "current_score=100.00 / 100" in audit
    assert "full_score_ready=true" in audit
    assert "The KRD and maturity queues also expose their own action maps." in audit
    assert "decision_options=approve_nearest_bucket|require_exact_bucket_schema|reject" in audit
    assert "remediation_scope" in audit
    assert "current_score=99.86 / 100" in audit
    assert "remaining_gap=0.14" in audit
    assert "scripts/check_portfolio_home_business_owner_approval.py" in audit
    assert "docs/audits/2026-06-05-portfolio-readiness-gate-audit.md" in packet


def test_portfolio_option_b_execution_note_lists_current_score_blockers() -> None:
    note = OPTION_B_NOTE.read_text(encoding="utf-8")

    assert "## Current Blockers" in note
    for blocker in CURRENT_SCORE_BLOCKERS:
        assert f"- `{blocker}`" in note
    assert "owner_decision_intake_blocked" in note
    assert "Reconcile the `6` matured non-zero bond positions at source" in note
    assert "Remediate or approve scoped exclusion for `114` missing bond maturity rows" not in note
    assert "risk-owner CSV decisions, nearest-bucket approval or exact-bucket schema evidence, data-owner CSV decisions, scoped-exclusion evidence, and business-owner approval" in note
