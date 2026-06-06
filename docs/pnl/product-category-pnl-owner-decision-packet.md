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
