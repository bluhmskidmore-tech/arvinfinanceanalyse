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

## Current Certification Blockers

- `golden_sample_approval_artifact_status=captured-awaiting-approval`
- `golden_sample_approval_artifact_mismatch=true`
- `approval_action_item_count=14`
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
| `business_owner_approval` | `pending; 14 action items` | `docs/pnl/product-category-pnl-business-owner-approval-template.md` | `false` | Complete and sign the approval template after reviewing all prior gates. |

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
