# Product-Category PnL First Certification Packet

Page ID: `PAGE-PROD-CAT-001`
Page slug: `product-category-pnl`
Primary API: `/ui/pnl/product-category`
Business contract status: `evidence-pending`
Business contract certified: `false`
Formal use allowed: `formal_use_allowed=true`
Closure approved: `closure_approved=false`
Business owner approval captured: `false`
Handoff status: `owner_actions_required`

This packet does not approve page closure, write governance records, prove page execution, capture business-owner approval, or grant final certification.

## Packet Freshness Guard

- `packet_generator=script-owned`
- `source_artifacts=readiness_report, approval_template, closure_blocker_triage`
- Boundary: Manual edits to this packet must be followed by rerunning the generator.

## Current Certification Blockers

- `golden_sample_approval_artifact_status=captured-awaiting-approval`
- `golden_sample_approval_artifact_mismatch=true`
- `approval_action_item_count=15`
- `business_owner_approval_captured=false`
- `closure_blocker_triage.blocker_count=15`

## Latest Readiness/Live Gate Evidence

- Command: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-readiness.ps1 -PageSlug product-category-pnl -Run -CheckLive`
- Evidence basis: `recorded_prior_gate_output`
- Packet generator reruns gate: `false`
- Status: `passed`
- Static readiness: `passed`
- Live smoke: `passed`
- MCP contract tests: `175 passed`
- Product-category backend flow/mapping tests: `59 passed`
- Product-category frontend tests: `155 passed`
- Browser a11y smoke: `1 passed`
- Frontend typecheck: `passed`
- Frontend debt audit: `passed`
- Frontend production build: `passed`
- Boundary: This evidence proves the verification gate passed; it does not capture business-owner approval, manual audit closure, or golden approval artifact reconciliation.
- Rerun boundary: Regenerating this packet only records the latest available gate evidence; the pre-approval runbook must rerun the gate before owner signature.

## Closure Blocker Triage

- Artifact: `docs/pnl/product-category-remaining-blockers.md`
- Machine readable: `true`
- Class 1 product decisions: `3`
- Class 2 API/contract blockers: `2`
- Class 4 evidence/test/documentation blockers: `9`
- Class 5 out-of-scope blockers: `1`
- Cursor-safe blockers: `1`
- Partially cursor-safe blockers: `0`
- Partially complete blockers: `9`
- Non-cursor-safe blockers: `5`

## Owner Closure Gate Matrix

| Gate | Current status | Evidence | Can be closed by code | Required owner action |
| --- | --- | --- | --- | --- |
| `machine_verification` | `passed` | `latest_readiness_gate_evidence` | `false` | Review evidence; no approval is captured by this gate. |
| `owner_decisions` | `pending_owner_decisions` | `docs/pnl/product-category-pnl-owner-decision-packet.md` | `false` | Resolve 3 product decisions and 2 backend/API contract decisions. |
| `golden_sample_approval` | `captured-awaiting-approval; mismatch=true` | `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md` | `false` | Approve GS-PROD-CAT-PNL-A with non-placeholder owner, approver, and approval date. |
| `manual_closure_checklist` | `10 partial units remain` | `docs/pnl/product-category-closure-checklist.md` | `false` | Review and close each checklist unit from PARTIAL to CLOSED only when evidence and decisions support it. |
| `business_owner_approval` | `pending; 15 action items` | `docs/pnl/product-category-pnl-business-owner-approval-template.md` | `false` | Complete and sign the approval template after reviewing all prior gates. |

## Owner Readiness Receipt

- Receipt kind: `pre_signature_owner_readiness_receipt`
- `owner_signable=false`
- `machine_evidence_ready=true`
- `business_decisions_ready=false`
- `golden_sample_ready=false`
- `manual_audit_ready=false`
- `business_owner_signature_ready=false`
- `can_promote_certification=false`
- `human_required_item_count=15`
- Boundary: Receipt is an owner-review intake aid only; it does not approve the page, write governance records, close manual audit, approve the golden sample, or capture business-owner approval.

Machine-prepared evidence:

- `latest_readiness_gate_evidence`
- `source_to_screen_trace:MTR-PCP-001..MTR-PCP-012`
- `owner_decision_packet_artifact_exists`
- `approval_template_artifact_exists`

Human-required evidence:

- `business_owner_name`
- `business_owner_role`
- `approval_decision`
- `approval_date`
- `business_owner_signature`
- `governance_record_review`
- `reviewed_owner_decision_packet`
- `owner_decision_next_review_queue_acknowledgement`
- `golden_sample_artifact_reconciliation`
- `closure_checklist_review`
- `fallback_liability_branch_boundary_review`
- `ui_api_payload_review`
- `live_smoke_evidence_review`
- `verification_commands_rerun`
- `evidence_pending_boundary_acceptance`

Promotion blockers:

- `business_owner_approval_captured=false`
- `closure_approved=false`
- `golden_sample_approval_artifact_mismatch=true`
- `manual_closure_checklist_has_partial_units=10`
- `owner_decisions_pending=5`

## Owner Review Intake Checklist

- Checklist kind: `owner_review_intake_artifact_checklist`
- `review_intake_ready=true`
- `owner_signable=false`
- `captures_business_owner_approval=false`
- `freshness_guarded_artifact_count=2`
- `missing_freshness_guard_artifacts=0`
- `missing_required_artifacts=0`
- Boundary: All required owner-review artifacts exist, but this checklist does not approve the page, capture signature, close manual audit, approve the golden sample, or make the route owner-signable.

| Artifact | Path | Exists | Required before owner review | Freshness guard present |
| --- | --- | --- | --- | --- |
| `boundary_status` | `docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json` | `true` | `true` | `n/a` |
| `first_certification_packet` | `docs/pnl/product-category-pnl-first-certification-packet.md` | `true` | `true` | `true` |
| `owner_decision_packet` | `docs/pnl/product-category-pnl-owner-decision-packet.md` | `true` | `true` | `true` |
| `approval_template` | `docs/pnl/product-category-pnl-business-owner-approval-template.md` | `true` | `true` | `n/a` |
| `closure_checklist` | `docs/pnl/product-category-closure-checklist.md` | `true` | `true` | `n/a` |
| `closure_blocker_triage` | `docs/pnl/product-category-remaining-blockers.md` | `true` | `true` | `n/a` |
| `golden_sample_approval_artifact` | `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md` | `true` | `true` | `n/a` |

Missing freshness guard artifacts:

- `none`

Missing required artifacts:

- `none`

## Approval Checker Generated Artifact Freshness

| Artifact | Path | Exists | Freshness status | Missing markers |
| --- | --- | --- | --- | ---: |
| `first_certification_packet` | `docs/pnl/product-category-pnl-first-certification-packet.md` | `true` | `freshness_status=valid` | `missing_markers=0` |
| `owner_decision_packet` | `docs/pnl/product-category-pnl-owner-decision-packet.md` | `true` | `freshness_status=valid` | `missing_markers=0` |

## Owner Decision Packet Bridge

- Bridge kind: `owner_decision_packet_bridge`
- Packet path: `docs/pnl/product-category-pnl-owner-decision-packet.md`
- `packet_exists=true`
- `formal_decision_item_count=5`
- `next_review_queue_item_count=5`
- `counts_next_review_as_decision=false`
- `captures_product_or_api_decisions=false`
- Required owner action: Review 5 formal decision items plus 5 next-review queue topics; the queue topics are intake follow-ups and do not capture decisions.

## Pre-Signature Verification Rerun Receipt

- Receipt kind: `pre_signature_verification_rerun_receipt`
- `packet_generator_reruns_gate=false`
- `latest_recorded_gate_status=passed`
- `approval_template_requires_rerun=true`
- `verification_commands_rerun_captured=false`
- Boundary: Recorded gate evidence is useful intake evidence, but owner signature requires a fresh pre-signature rerun and still cannot bypass golden, manual-audit, owner decisions, or owner approval.

Pre-signature required commands:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-readiness.ps1 -PageSlug product-category-pnl -Run -CheckLive`
- `python scripts\check_product_category_pnl_business_owner_approval.py`
- `python scripts\check_product_category_pnl_business_owner_approval.py --require-captured`

Current recorded evidence:

- static_readiness: `passed`
- live_smoke: `passed`
- mcp_contract_tests: `175 passed`
- backend_flow_mapping_tests: `59 passed`
- frontend_tests: `155 passed`
- browser_a11y_smoke: `1 passed`
- frontend_typecheck: `passed`
- frontend_debt_audit: `passed`
- frontend_production_build: `passed`

Still blocking after rerun:

- `business_owner_approval_captured=false`
- `golden_sample_approval_artifact_mismatch=true`
- `manual_closure_checklist_has_partial_units=10`
- `owner_decisions_pending=5`

## Source-To-Screen Trace

| Metric | API field | Client/model path | Component anchor | Formatter | Unit | Boundary |
| --- | --- | --- | --- | --- | --- | --- |
| `MTR-PCP-001` | result.asset_total.business_net_income | getProductCategoryPnl -> ProductCategoryPnlPage -> assetTotal | `product-category-formal-headline-totals` | `formatProductCategoryValue` | `yi_yuan` | formal/governed evidence-pending; owner approval not captured |
| `MTR-PCP-002` | result.liability_total.business_net_income | getProductCategoryPnl -> ProductCategoryPnlPage -> liabilityTotal | `product-category-formal-headline-totals` | `formatProductCategoryValue` | `yi_yuan` | formal/governed evidence-pending; owner approval not captured |
| `MTR-PCP-003` | result.grand_total.business_net_income | getProductCategoryPnl -> ProductCategoryPnlPage -> displayedGrandTotal | `product-category-formal-headline-totals` | `formatProductCategoryValue` | `yi_yuan` | backend total wins; frontend must not recompute asset + liability |
| `MTR-PCP-004` | result.rows[].cnx_scale | getProductCategoryPnl -> selectProductCategoryDetailRows -> row.cnx_scale | `product-category-table` | `formatProductCategoryRowDisplayValue` | `yi_yuan` | row-scoped detail metric; category_id/side/view/report_date are dimensions |
| `MTR-PCP-005` | result.rows[].cny_scale | getProductCategoryPnl -> selectProductCategoryDetailRows -> row.cny_scale | `product-category-table` | `formatProductCategoryRowDisplayValue` | `yi_yuan` | row-scoped detail metric; category_id/side/view/report_date are dimensions |
| `MTR-PCP-006` | result.rows[].foreign_scale | getProductCategoryPnl -> selectProductCategoryDetailRows -> row.foreign_scale | `product-category-table` | `formatProductCategoryRowDisplayValue` | `yi_yuan` | row-scoped detail metric; category_id/side/view/report_date are dimensions |
| `MTR-PCP-007` | result.rows[].cny_ftp | getProductCategoryPnl -> selectProductCategoryDetailRows -> row.cny_ftp | `product-category-table` | `formatProductCategoryRowDisplayValue` | `yi_yuan` | scenario may change backend FTP payload; frontend must not recompute |
| `MTR-PCP-008` | result.rows[].foreign_ftp | getProductCategoryPnl -> selectProductCategoryDetailRows -> row.foreign_ftp | `product-category-table` | `formatProductCategoryRowDisplayValue` | `yi_yuan` | scenario may change backend FTP payload; frontend must not recompute |
| `MTR-PCP-009` | result.rows[].cny_net | getProductCategoryPnl -> selectProductCategoryDetailRows -> row.cny_net | `product-category-table` | `formatProductCategoryRowDisplayValue` | `yi_yuan` | backend payload wins; liability sign normalization is display-only |
| `MTR-PCP-010` | result.rows[].foreign_net | getProductCategoryPnl -> selectProductCategoryDetailRows -> row.foreign_net | `product-category-table` | `formatProductCategoryRowDisplayValue` | `yi_yuan` | backend payload wins; liability sign normalization is display-only |
| `MTR-PCP-011` | result.rows[].business_net_income | getProductCategoryPnl -> selectProductCategoryDetailRows -> row.business_net_income | `product-category-table` | `formatProductCategoryRowDisplayValue` | `yi_yuan` | backend payload wins; liability sign normalization is display-only |
| `MTR-PCP-012` | result.rows[].weighted_yield | getProductCategoryPnl -> selectProductCategoryDetailRows -> row.weighted_yield | `product-category-table` | `formatProductCategoryYieldValue` | `percent` | not money-scaled; null remains explicit |

## Evidence Anchors

- truth_contract: `docs/pnl/product-category-page-truth-contract.md`
- metric_dictionary: `docs/metric_dictionary.md`
- golden_sample: `tests/golden_samples/GS-PROD-CAT-PNL-A`
- boundary_status: `docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json`
- approval_template: `docs/pnl/product-category-pnl-business-owner-approval-template.md`
- owner_decision_packet: `docs/pnl/product-category-pnl-owner-decision-packet.md`
- model_tests: `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts`
- page_tests: `frontend/src/test/ProductCategoryPnlPage.test.tsx`

## Reviewer Checklist

- Confirm current UI/API payload matches MTR-PCP-001 through MTR-PCP-012 source-to-screen trace rows.
- Review docs/pnl/product-category-pnl-owner-decision-packet.md for the 3 product decisions and 2 API/contract blockers.
- Review docs/pnl/product-category-pnl-owner-decision-packet.md for 5 formal decision items and 5 next-review queue topics; queue topics do not count as captured decisions.
- Confirm reviewed boundary, first-certification, and owner-decision packet artifacts exist before marking template review fields yes.
- Resolve golden_sample_approval_artifact_mismatch before certification wording.
- Review closure checklist units that remain PARTIAL.
- Review liability fallback model-boundary evidence without synthetic production proof.
- Run live smoke/browser evidence review before signature.
- Complete and sign docs/pnl/product-category-pnl-business-owner-approval-template.md.

## Business Owner Action Items

- Business owner name: `Business owner legal or operating name` (`missing`)
- Business owner role: `Business owner accountability role` (`missing`)
- Approval decision: `approve` (`missing`)
- Approval date: `YYYY-MM-DD` (`missing`)
- Business owner signature: `Business owner signature` (`missing`)
- Governance record reviewed: `yes` (`pending`)
- Owner decision packet reviewed: `yes` (`pending`)
- Owner decision next-review queue acknowledged: `yes` (`pending`)
- Golden sample `GS-PROD-CAT-PNL-A` approval artifact reconciled: `yes` (`pending`)
- Closure checklist units reviewed: `yes` (`pending`)
- Fallback liability branch model-boundary evidence reviewed: `yes` (`pending`)
- UI/API payload evidence reviewed: `yes` (`pending`)
- Live smoke evidence reviewed: `yes` (`pending`)
- Verification commands rerun before approval: `yes` (`pending`)
- Evidence-pending boundary accepted: `yes` (`pending`)

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
