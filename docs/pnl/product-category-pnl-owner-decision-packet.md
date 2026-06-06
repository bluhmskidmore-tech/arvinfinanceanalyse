# Product-Category PnL Owner Decision Packet

Page ID: `PAGE-PROD-CAT-001`
Page slug: `product-category-pnl`
Primary API: `/ui/pnl/product-category`
Decision status: `decision_status=pending_owner_decisions`
Owner decision ready: `false`

This packet does not approve page closure, write governance records, prove page execution, capture business-owner approval, capture product/API decisions, or grant final certification.

## Decision Summary

- Source artifact: `docs/pnl/product-category-remaining-blockers.md`
- `decision_item_count=5`
- Class 1 product decisions: `3`
- Class 2 API/contract decisions: `2`

## Packet Freshness Guard

- `packet_generator=script-owned`
- `source_artifact=docs/pnl/product-category-remaining-blockers.md`
- Boundary: Manual edits to this packet must be followed by rerunning the generator.

## Decision Intake Checklist

- Checklist kind: `owner_decision_intake_checklist`
- `decision_intake_ready=true`
- `owner_decision_ready=false`
- `captures_product_or_api_decisions=false`
- `decision_item_count=5`
- `pending_decision_count=5`
- `source_artifact_exists=true`
- Required owner types: `product_owner`, `backend_api_contract_owner`
- Boundary: Decision intake is ready for owner review, but every decision item remains pending; this checklist does not capture product/API decisions or approve certification.

## Next Review Queue

- Source section: `Next cursor-safe tasks`
- `next_review_queue_item_count=5`
- `counts_as_owner_decision=false`
- `captures_product_or_api_decisions=false`

| Review key | Rank | Topic | Required review | Review owner type | Evidence path | Blocker reason | Pre-signature action | Current status |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| `next_1_outward_as_of_date` | 1 | outward `as_of_date` | decide whether the page should expose `as_of_date` separately from the selected `report_date`. | `product_owner` | `docs/pnl/product-category-page-truth-contract.md` | The page currently preserves selected report_date and resolved report_date semantics, but no owner-approved outward as_of_date field exists. | Owner must either approve no standalone outward as_of_date or specify the exact API/UI field before signature. | `pending_review` |
| `next_2_refresh_timeout_stale_copy` | 2 | refresh timeout/stale copy | specify the copy shown when refresh exceeds the current UI polling window. | `product_owner` | `frontend/src/test/ProductCategoryPnlPage.test.tsx` | Queued/running/failed states are tested, but timeout-specific stale copy is not product-frozen. | Owner must approve timeout and stale-state copy or defer it explicitly before signature. | `pending_review` |
| `next_3_unit_4_extended_validation_copy` | 3 | Unit 4 extended validation copy | freeze any additional backend validation wording beyond the two covered empty-payload cases. | `product_owner` | `docs/pnl/product-category-closure-checklist.md` | The two primary empty-payload cases are covered, but extended validation wording remains outside the frozen checklist scope. | Owner must approve the extended validation copy scope or confirm the current two-case scope is sufficient. | `pending_review` |
| `next_4_dual_sort_rationale` | 4 | dual-sort rationale | record the product intent for keeping current and event sort controls independent. | `product_owner` | `docs/pnl/product-category-remaining-blockers.md` | The dual-sort behavior is visible, but the product rationale for two independent controls is not recorded. | Owner must record the product rationale for dual sort or approve a single-sort model before signature. | `pending_review` |
| `next_5_revoke_confirmation_policy` | 5 | revoke confirmation policy | freeze whether destructive revoke needs policy beyond the already tested browser confirmation gate. | `product_owner` | `frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx` | Browser confirmation behavior is tested, but no owner policy states whether that is sufficient for destructive revoke. | Owner must approve browser confirmation as sufficient or specify an additional revoke policy gate. | `pending_review` |

## Decision Items

| Decision key | Unit | Class | Owner type | Blocker | Required decision | Current decision |
| --- | --- | --- | --- | --- | --- | --- |
| `unit_3_long_running_refresh_timeout_messaging` | Unit 3 | `product_decision_required` | `product_owner` | long-running refresh UX ... timeout messaging vs `runPollingTask` generic timeout | Decide timeout user messaging and whether to surface run_id after timeout | `pending` |
| `unit_4_extended_validation_copy_policy` | Unit 4 | `product_decision_required` | `product_owner` | long copy/UX for validation beyond the two primary empty-payload cases is not exhaustively specified | Approve validation messages and edge-case rules | `pending` |
| `unit_5_dual_sort_rationale` | Unit 5 | `product_decision_required` | `product_owner` | product rationale for two independent sort controls ... narrative gap | Document product "why" for dual sort vs single model | `pending` |
| `unit_6_backend_global_utf_8_bom_policy_for_generated_csv` | Unit 6 | `backend_api_contract_required` | `backend_api_contract_owner` | backend/global UTF-8 BOM policy for generated CSV not specified | Record server BOM rule; align tests | `pending` |
| `unit_6_large_export_behavior_policy` | Unit 6 | `backend_api_contract_required` | `backend_api_contract_owner` | no frozen behavior for very large exports | Define limits/streaming/timeouts; implement + test | `pending` |

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `captures_product_or_api_decisions=false`
