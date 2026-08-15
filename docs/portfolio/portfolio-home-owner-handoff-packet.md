# Portfolio Home Owner Handoff Packet

## Summary
- Page: `portfolio` (`PAGE-PORTFOLIO-HOME-001`)
- Report date: `2026-05-31`
- Current score: `99.86 / 100`
- Remaining gap: `0.14`
- Score status: `blocked`
- Handoff status: `owner_actions_required`
- Intake status: `pending_owner_decisions`
- Owner intake ready: `False`
- Owner intake blockers: `krd_owner_decision_missing`, `maturity_owner_decision_missing`, `business_owner_approval_missing`
- Approval date status: `missing`
- Verification rerun status: `pending`
- Rerun evidence status: `valid`
- Rerun evidence artifact: `docs/portfolio/portfolio-home-evidence-snapshot.json`
- Risk warning clean status: `blocked`
- Risk warning blockers: `risk_tensor_quality_warning`
- Risk tensor rematerialization preview: `would_remain_blocked`
- Risk tensor preview would clear: `none`
- Risk tensor preview decision status: `blocked`
- Risk tensor preview decision blockers: `risk_tensor_quality_warning`
- Risk tensor preview writes database: `false`
- Risk tensor preview approves metric or page: `false`
- Risk tensor preview certification effect: `none`
- Business owner approval boundary: `pending_owner_input`
- Template approval captured: `false`
- Formal authorization allowed: `false`
- Governance write allowed: `false`
- Page execution proven: `false`
- Full score closure ready: `false`
- Certification effect: `none`
- Handoff approves metric or page: `false`
- Handoff writes governance records: `false`
- Handoff captures business-owner approval: `false`
- Business owner approval boundary blockers: `business_owner_approval_not_captured`, `scorecard_full_score_not_ready`, `scorecard_score_status_not_ready`, `owner_decision_intake_not_ready`, `risk_warning_not_clean`
- Decision alignment: `consistent`
- Owner intake evidence alignment: `consistent`
- Owner intake evidence alignment blockers: `none`
- Score blocker action coverage: `clean`
- Score blocker action coverage blockers: `none`
- Score blocker action coverage unassigned blockers: `none`
- Score blocker action coverage covered blockers: `risk_tensor_quality_warning`, `krd_contract_decision_required`, `bond_matured_outstanding_reconciliation_required`, `tyw_liability_maturity_date_remediation_required`, `business_owner_approval`, `owner_decision_intake_blocked`
- Blocker closure matrix coverage: `clean`
- Blocker closure matrix missing blockers: `none`
- Blocker closure matrix unexpected blockers: `none`
- Blocker closure matrix duplicate blockers: `none`
- Activation boundary: no automatic approval; owner decisions must be captured and rechecked.
- Generated owner fields boundary: KRD and maturity export manifests require `generated_owner_fields_must_be_blank=true`; dependency consistency blocks missing, false, or pre-filled generated owner fields.
- Owner intake CSV summary: `krd_summary_row_count=3`, `krd_detail_row_count=500`, `bond_missing_maturity_row_count=0`, `tyw_liability_missing_maturity_row_count=1455`.
- Owner intake blank-field status: `krd_owner_decision_fields_blank=true`, `maturity_owner_fields_blank=true`.
- Manifest generated-owner boundary status: `krd_contract_decision_manifest=true`, `maturity_remediation_manifest=true`.
- Generated export system-field current gate: `generated_export_system_fields_must_be_current=true`.
- Export current summary: `krd_status=current`, `krd_current=true`, `maturity_status=current`, `maturity_current=true`.
- Export current blockers: `none`.
- Export current boundary: current export system fields prove package freshness only; they do not approve KRD decisions, maturity remediation, signed exclusions, or business-owner closure.
- Closure artifact presence check reports `status=current`, `current=true`, and no blockers.

## Owner Quickstart
- Quickstart boundary: fill owner-controlled fields only; do not edit generated system fields.
- Risk Owner quickstart:
  - Close: `risk_tensor_quality_warning`, `krd_contract_decision_required`
  - Fill/review: `docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_summary.csv`; `docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv`; `docs/portfolio/krd-contract-decision/2026-05-31/nearest_bucket_approval_evidence.json`; `docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json`
  - Required fields: `risk_owner_decision`, `decision_notes`
  - Conditional fields (`approve_nearest_bucket` only): `risk_owner_name`, `risk_owner_approval_date`, `risk_owner_approved`, `business_owner_name`, `business_owner_acknowledgement_date`, `business_owner_acknowledged`, `metric_contract_decision_recorded`, `verification_rerun_matched`
  - Conditional fields (`require_exact_bucket_schema` only): `metric_contract_owner_name`, `metric_contract_update_date`, `metric_contract_updated`, `api_schema_owner_name`, `api_schema_update_date`, `api_schema_updated`, `risk_tensor_owner_name`, `risk_tensor_rematerialization_date`, `risk_tensor_rematerialized`, `verifier_name`, `verification_rerun_date`, `verification_rerun_matched`
  - Recheck: `python scripts/portfolio_home_risk_warning_consistency.py --report-date 2026-05-31 --require-clean`; `python scripts/portfolio_home_krd_remap_review_queue.py --report-date 2026-05-31 --require-clean`
- Data Owner quickstart:
  - Close: `tyw_liability_maturity_date_remediation_required`, `bond_matured_outstanding_reconciliation_required`
  - Fill/review: `docs/portfolio/maturity-remediation/2026-05-31/tyw_liability_missing_maturity.csv`; `docs/portfolio/maturity-remediation/2026-05-31/maturity_scoped_exclusion_evidence.json`
  - Required fields: `proposed_maturity_date`, `owner_decision`, `owner_comment`
  - Conditional fields (`approve_scoped_exclusion` only): `data_owner_name`, `data_owner_approval_date`, `data_owner_approved`, `risk_owner_name`, `risk_owner_countersign_date`, `risk_owner_countersigned`, `business_owner_name`, `business_owner_acknowledgement_date`, `business_owner_acknowledged`, `verification_rerun_matched`
  - Recheck: `python scripts/portfolio_home_maturity_remediation_queue.py --report-date 2026-05-31 --require-empty`; `python scripts/portfolio_home_matured_outstanding_queue.py --report-date 2026-05-31 --require-empty`
- Business Owner quickstart:
  - Close: `business_owner_approval`, `owner_decision_intake_blocked`
  - Fill/review: `docs/portfolio/portfolio-home-business-owner-approval-template.md`
  - Required fields: `approval_status`, `business_owner_name`, `risk_owner_name`, `approval_decision`, `approval_date`, `business_owner_signature`, `risk_owner_signature`, `krd_contract_decision`, `maturity_data_decision`, `risk_tensor_warning_decision`, `evidence_scope`
  - Recheck: `python scripts/check_portfolio_home_business_owner_approval.py --report-date 2026-05-31 --require-captured`; `python scripts/portfolio_home_owner_decision_intake_check.py --report-date 2026-05-31 --limit 3 --require-ready`

## Current Blockers
- `risk_tensor_quality_warning`
- `krd_contract_decision_required`
- `bond_matured_outstanding_reconciliation_required`
- `tyw_liability_maturity_date_remediation_required`
- `business_owner_approval`
- `owner_decision_intake_blocked`

## Blocker Closure Matrix
| Blocker | Owner | Fill / Evidence | Recheck | Exit Signal |
| --- | --- | --- | --- | --- |
| `risk_tensor_quality_warning` | `risk_owner` | `risk_warning_consistency` (`parsed_warnings`, `recomputed_warnings`, `duration_exclusion_delta_detail`, `warning_resolution_matrix`, `decision_blockers`) | `python scripts/portfolio_home_risk_warning_consistency.py --report-date 2026-05-31 --require-clean`; `python scripts/portfolio_home_full_closure_evidence.py --report-date 2026-05-31 --require-clean` | Risk tensor quality is clean for report_date 2026-05-31 and strict full-closure evidence no longer reports this blocker. |
| `krd_contract_decision_required` | `risk_owner` | `docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_summary.csv`; `docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv`; `docs/portfolio/krd-contract-decision/2026-05-31/nearest_bucket_approval_evidence.json`; `docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json` | `python scripts/portfolio_home_krd_remap_review_queue.py --report-date 2026-05-31 --require-clean`; `python scripts/portfolio_home_owner_decision_intake_check.py --report-date 2026-05-31 --limit 3 --require-ready` | Risk-owner KRD decision is captured with notes for every scoped row, conditional nearest-bucket or exact-bucket evidence is valid when selected, and the KRD strict gate exits 0. |
| `bond_matured_outstanding_reconciliation_required` | `data_owner` | `matured_outstanding_queue` (`summary`, `rows`) | `python scripts/portfolio_home_matured_outstanding_queue.py --report-date 2026-05-31 --require-empty`; `python scripts/portfolio_home_full_closure_evidence.py --report-date 2026-05-31 --require-clean` | Matured or unparseable non-zero bond positions are reconciled at source, and the matured-outstanding strict queue exits 0. |
| `tyw_liability_maturity_date_remediation_required` | `data_owner` | `docs/portfolio/maturity-remediation/2026-05-31/tyw_liability_missing_maturity.csv`; `docs/portfolio/maturity-remediation/2026-05-31/maturity_scoped_exclusion_evidence.json` | `python scripts/portfolio_home_maturity_remediation_queue.py --report-date 2026-05-31 --require-empty`; `python scripts/portfolio_home_owner_decision_intake_check.py --report-date 2026-05-31 --limit 3 --require-ready` | TYW liability missing-maturity rows are remediated at source or covered by a signed scoped exclusion evidence file, and the maturity strict gate exits 0. |
| `business_owner_approval` | `business_owner` | `docs/portfolio/portfolio-home-business-owner-approval-template.md` | `python scripts/check_portfolio_home_business_owner_approval.py --report-date 2026-05-31 --require-captured`; `python scripts/portfolio_home_business_owner_approval_packet.py --report-date 2026-05-31 --limit 3 --require-ready`; `python scripts/portfolio_home_closure_scorecard.py --report-date 2026-05-31 --limit 3 --require-full-score` | Business-owner approval is signed, risk-owner countersignature is present, evidence scope approves the page, and the full scorecard strict gate exits 0. |
| `owner_decision_intake_blocked` | `business_owner` | `docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_summary.csv`; `docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv`; `docs/portfolio/krd-contract-decision/2026-05-31/nearest_bucket_approval_evidence.json`; `docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json`; `docs/portfolio/maturity-remediation/2026-05-31/tyw_liability_missing_maturity.csv`; `docs/portfolio/maturity-remediation/2026-05-31/maturity_scoped_exclusion_evidence.json`; `docs/portfolio/portfolio-home-business-owner-approval-template.md` | `python scripts/portfolio_home_owner_decision_intake_check.py --report-date 2026-05-31 --limit 3 --require-ready` | Risk-owner CSV decisions, nearest-bucket or exact-bucket evidence, data-owner CSV decisions, scoped-exclusion evidence, and business-owner approval are reconciled, and the owner decision intake strict gate exits 0. |

## Owner Checklist
- [ ] Risk Owner: close `risk_tensor_quality_warning`, `krd_contract_decision_required`
  - Evidence commands: `python scripts/portfolio_home_risk_warning_consistency.py --report-date 2026-05-31 --require-clean`; `python scripts/portfolio_home_krd_remap_review_queue.py --report-date 2026-05-31 --require-clean`
  - Exit criteria: Risk warning clean gate exits 0 and full-closure evidence no longer reports risk_tensor_quality_warning; KRD review queue exits 0 under the approved contract and the metric contract records the decision.
  - Artifacts: `docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_summary.csv`; `docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv`; `docs/portfolio/krd-contract-decision/2026-05-31/nearest_bucket_approval_evidence.json`; `docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json`
  - Workload: KRD owner decision fields across 503 rows (summary 3, detail 500).
  - Current gaps: KRD owner decision missing on 503 rows (summary 3, detail 500).
  - Artifact fields to review/fill: `risk_owner_decision`, `decision_notes`
  - Conditional artifact fields (`approve_nearest_bucket` only): `risk_owner_name`, `risk_owner_approval_date`, `risk_owner_approved`, `business_owner_name`, `business_owner_acknowledgement_date`, `business_owner_acknowledged`, `metric_contract_decision_recorded`, `verification_rerun_matched`
  - Conditional artifact fields (`require_exact_bucket_schema` only): `metric_contract_owner_name`, `metric_contract_update_date`, `metric_contract_updated`, `api_schema_owner_name`, `api_schema_update_date`, `api_schema_updated`, `risk_tensor_owner_name`, `risk_tensor_rematerialization_date`, `risk_tensor_rematerialized`, `verifier_name`, `verification_rerun_date`, `verification_rerun_matched`
  - Allowed decisions: `approve_nearest_bucket`, `require_exact_bucket_schema`, `reject`
  - Notes required for: `approve_nearest_bucket`, `require_exact_bucket_schema`, `reject`
- [ ] Data Owner: close `tyw_liability_maturity_date_remediation_required`, `bond_matured_outstanding_reconciliation_required`
  - Evidence commands: `python scripts/portfolio_home_maturity_remediation_queue.py --report-date 2026-05-31 --require-empty`; `python scripts/portfolio_home_matured_outstanding_queue.py --report-date 2026-05-31 --require-empty`
  - Exit criteria: TYW liability maturity remediation queue is empty or signed exclusion evidence is captured and surfaced as a boundary; Matured outstanding strict queue exits 0 with no matured or unparseable non-zero bond positions.
  - Artifacts: `docs/portfolio/maturity-remediation/2026-05-31/tyw_liability_missing_maturity.csv`; `docs/portfolio/maturity-remediation/2026-05-31/maturity_scoped_exclusion_evidence.json`
  - Workload: maturity remediation fields across 1455 rows (bond 0, TYW liability 1455).
  - Current gaps: maturity owner decision missing on 1455 rows (bond 0, TYW liability 1455).
  - Artifact fields to review/fill: `proposed_maturity_date`, `owner_decision`, `owner_comment`
  - Conditional artifact fields (`approve_scoped_exclusion` only): `data_owner_name`, `data_owner_approval_date`, `data_owner_approved`, `risk_owner_name`, `risk_owner_countersign_date`, `risk_owner_countersigned`, `business_owner_name`, `business_owner_acknowledgement_date`, `business_owner_acknowledged`, `verification_rerun_matched`
  - Allowed decisions: `remediate_source`, `approve_scoped_exclusion`, `reject`
  - Notes required for: `remediate_source`, `approve_scoped_exclusion`, `reject`
- [ ] Business Owner: close `business_owner_approval`, `owner_decision_intake_blocked`
  - Evidence commands: `python scripts/check_portfolio_home_business_owner_approval.py --report-date 2026-05-31 --require-captured`; `python scripts/portfolio_home_owner_decision_intake_check.py --report-date 2026-05-31 --limit 3 --require-ready`
  - Exit criteria: Approval checker exits 0 and evidence_scope.approves_metric_or_page is true; Owner decision intake strict gate exits 0 and reports intake_ready=true.
  - Artifacts: `docs/portfolio/portfolio-home-business-owner-approval-template.md`
  - Artifact fields to review/fill: `approval_status`, `business_owner_name`, `risk_owner_name`, `approval_decision`, `approval_date`, `business_owner_signature`, `risk_owner_signature`, `krd_contract_decision`, `maturity_data_decision`, `risk_tensor_warning_decision`, `evidence_scope`
  - Allowed decisions: `approve`
  - Dependent decision notes required for: `approve_nearest_bucket`, `approve_scoped_exclusion`, `reject`, `request_changes`
- [ ] Re-run intake and strict scorecard commands after owner updates are captured.

## Strict Gate Expectations
- Activation boundary state: `pending_owner_input`
- Current strict gates: expected to fail until owner decisions, maturity remediation/exclusion, and business approval are captured.
- After owner updates: each strict gate below must exit 0 before `/portfolio` can claim full closure.
- `python scripts/portfolio_home_owner_decision_intake_check.py --report-date 2026-05-31 --limit 3 --require-ready`: currently `exit_nonzero`; after updates `exit_0`.
- `python scripts/portfolio_home_business_owner_approval_packet.py --report-date 2026-05-31 --limit 3 --require-ready`: currently `exit_nonzero`; after updates `exit_0`.
- `python scripts/portfolio_home_closure_scorecard.py --report-date 2026-05-31 --limit 3 --require-full-score`: currently `exit_nonzero`; after updates `exit_0`.

## Risk Owner
- Status: `blocked`
- Blockers: `risk_tensor_quality_warning`, `krd_contract_decision_required`
- KRD decision scale: `20Y` maps to `krd_30y` across 39 rows with DV01 23598290.06912522; `2Y` maps to `krd_3y` across 301 rows with DV01 9195343.60983627; `6M` maps to `krd_1y` across 282 rows (160 non-zero DV01 rows) with DV01 571392.61884027.
- Required actions:
  - `risk_tensor_quality_warning`: Review the warning-consistency evidence, then rematerialize a clean risk tensor or keep the page candidate-only.
    Evidence command: `python scripts/portfolio_home_risk_warning_consistency.py --report-date 2026-05-31 --require-clean`
  - `krd_contract_decision_required`: Approve nearest-bucket mappings for 2Y, 6M, and 20Y, or require an exact-bucket KRD schema/API update.
    Evidence command: `python scripts/portfolio_home_krd_remap_review_queue.py --report-date 2026-05-31 --require-clean`
- Decision intake artifacts:
  - Artifact: `docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_summary.csv`
    Required fields: `risk_owner_decision`, `decision_notes`
    Allowed decisions: `approve_nearest_bucket`, `require_exact_bucket_schema`, `reject`
    Note required for: `approve_nearest_bucket`, `require_exact_bucket_schema`, `reject`
  - Artifact: `docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv`
    Required fields: `risk_owner_decision`, `decision_notes`
    Allowed decisions: `approve_nearest_bucket`, `require_exact_bucket_schema`, `reject`
    Note required for: `approve_nearest_bucket`, `require_exact_bucket_schema`, `reject`
  - Artifact: `docs/portfolio/krd-contract-decision/2026-05-31/nearest_bucket_approval_evidence.json`
    Required fields: `risk_owner_name`, `risk_owner_approval_date`, `risk_owner_approved`, `business_owner_name`, `business_owner_acknowledgement_date`, `business_owner_acknowledged`, `metric_contract_decision_recorded`, `verification_rerun_matched`
    Allowed decisions: `approve_nearest_bucket`
  - Artifact: `docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json`
    Required fields: `metric_contract_owner_name`, `metric_contract_update_date`, `metric_contract_updated`, `api_schema_owner_name`, `api_schema_update_date`, `api_schema_updated`, `risk_tensor_owner_name`, `risk_tensor_rematerialization_date`, `risk_tensor_rematerialized`, `verifier_name`, `verification_rerun_date`, `verification_rerun_matched`
    Allowed decisions: `require_exact_bucket_schema`

## Data Owner
- Status: `blocked`
- Blockers: `tyw_liability_maturity_date_remediation_required`, `bond_matured_outstanding_reconciliation_required`
- Maturity decision scale: bond queue has 0 missing maturity rows with market value 0; TYW liability queue has 1455 missing maturity rows with principal 43822652393.01000002.
- Required actions:
  - `tyw_liability_maturity_date_remediation_required`: Remediate missing TYW liability maturity_date values or capture a signed scoped exclusion before rematerialization.
    Evidence command: `python scripts/portfolio_home_maturity_remediation_queue.py --report-date 2026-05-31 --require-empty`
  - `bond_matured_outstanding_reconciliation_required`: Reconcile matured or unparseable non-zero bond positions at source; this read-only gate does not accept an exception as closure evidence.
    Evidence command: `python scripts/portfolio_home_matured_outstanding_queue.py --report-date 2026-05-31 --require-empty`
- Decision intake artifacts:
  - Artifact: `docs/portfolio/maturity-remediation/2026-05-31/tyw_liability_missing_maturity.csv`
    Required fields: `proposed_maturity_date`, `owner_decision`, `owner_comment`
    Allowed decisions: `remediate_source`, `approve_scoped_exclusion`, `reject`
    Note required for: `remediate_source`, `approve_scoped_exclusion`, `reject`
  - Artifact: `docs/portfolio/maturity-remediation/2026-05-31/maturity_scoped_exclusion_evidence.json`
    Required fields: `data_owner_name`, `data_owner_approval_date`, `data_owner_approved`, `risk_owner_name`, `risk_owner_countersign_date`, `risk_owner_countersigned`, `business_owner_name`, `business_owner_acknowledgement_date`, `business_owner_acknowledged`, `verification_rerun_matched`
    Allowed decisions: `approve_scoped_exclusion`

## Business Owner
- Status: `blocked`
- Blockers: `business_owner_approval`, `owner_decision_intake_blocked`
- Required actions:
  - `business_owner_approval`: Complete and sign the portfolio-home business owner approval template with risk-owner countersignature.
    Evidence command: `python scripts/check_portfolio_home_business_owner_approval.py --report-date 2026-05-31 --require-captured`
  - `owner_decision_intake_blocked`: Reconcile risk-owner CSV decisions, nearest-bucket or exact-bucket evidence, data-owner CSV decisions, scoped-exclusion evidence, and business-owner approval before full-score activation.
    Evidence command: `python scripts/portfolio_home_owner_decision_intake_check.py --report-date 2026-05-31 --limit 3 --require-ready`
- Decision intake artifacts:
  - Artifact: `docs/portfolio/portfolio-home-business-owner-approval-template.md`
    Required fields: `approval_status`, `business_owner_name`, `risk_owner_name`, `approval_decision`, `approval_date`, `business_owner_signature`, `risk_owner_signature`, `krd_contract_decision`, `maturity_data_decision`, `risk_tensor_warning_decision`, `evidence_scope`
    Allowed decisions: `approve`
    Note required for: `approve_nearest_bucket`, `approve_scoped_exclusion`, `reject`, `request_changes`

## Recheck Commands
- `python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready --report-date 2026-05-31`
- `python scripts/portfolio_home_business_owner_approval_packet.py --limit 3 --require-ready`
- `python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score`
- `python scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current`
