# Calculation P1 First Priority Readiness Packet

Source snapshot status: `source_snapshot_status=owner_decision_required`
Owner intake ready: `true`
Implementation ready: `false`
Source snapshot generated at: `2026-08-06T22:30:00+08:00`

This packet prepares the current first priority group inside the calculation/display P1 blocker. It records current code anchors, existing test anchors, and the post-owner execution gates for `P1-10` and `P1-11`. P1-09 was selected and implemented previously and is not part of current owner intake. This packet does not approve a convention or change implementation code.

## Summary

- `first_priority_ids=P1-10, P1-11`
- `first_priority_count=2`
- `captured_decision_count=0`
- `post_owner_required_fields=selected_decision, owner_rationale, implementation_owner, verification_gate, status`
- `owner_intake_ready=true`
- `implementation_ready=false`

## Source Artifacts

- `calculation_owner_decision_matrix`: `docs/audits/2026-06-10-calculation-p1-owner-decision-matrix.md`
- `calculation_owner_decision_snapshot`: `docs/audits/2026-06-10-calculation-p1-owner-decision-snapshot.json`
- `calculation_owner_decision_packet`: `docs/audits/2026-06-10-calculation-p1-owner-decision-packet.md`

## Readiness Checks

- `all_first_priority_ids_still_open=true`
- `source_snapshot_is_owner_decision_required=true`
- `matrix_names_first_priority_group=true`
- `all_code_anchors_exist=true`
- `all_test_anchors_exist=true`
- `captures_owner_decisions=false`
- `chooses_or_approves_conventions=false`
- `changes_implementation_code=false`

## First Priority Items

| P1 | Area | Owner Decision Needed | Code Anchors | Test Anchors | Current Status | Missing Capture Fields | Owner Decision Gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `P1-10` | Frontend formal aggregation | Decide whether formal PnL, yield, and ADB aggregations must come from backend DTOs, or whether frontend derivations are limited to labeled non-formal helpers. | `frontend/src/features/pnl/YieldAnalysisPage.tsx`, `frontend/src/features/pnl/PnlByBusinessPage.tsx`, `frontend/src/features/pnl/pnlByBusinessPageModel.ts`, `frontend/src/features/pnl/yieldAnalysis/yieldAnalysisAggregates.ts`, `frontend/src/features/pnl/zqtzAdbAvgRollup.ts` | `frontend/src/features/pnl/yieldAnalysis/yieldAnalysisAggregates.test.ts`, `frontend/src/features/pnl/zqtzAdbAvgRollup.test.ts` | `pending_owner_decision` | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | backend DTO / frontend removal tests, or tests proving non-formal helper labeling |
| `P1-11` | Credit spread rating-tenor matrix | Decide whether the governed rating-tenor matrix is backend-provided, or frontend owns bucket aggregation and mapping rules. | `frontend/src/features/bond-analytics/components/CreditSpreadView.tsx` | `frontend/src/test/CreditSpreadView.test.tsx` | `pending_owner_decision` | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | API contract plus frontend test proving provided matrix rendering or explicit frontend ownership |

## Current Evidence And Post-Owner Gates

| P1 | Current Test Evidence | Post-Owner Actions | Known Regression Gap |
| --- | --- | --- | --- |
| `P1-10` | yieldAnalysisAggregates rejects invalid money inputs instead of coercing them to zero.<br>zqtzAdbAvgRollup tests freeze the current frontend ADB parent/child rollup behavior. | If backend DTO is authoritative, consume DTO values and remove formal frontend aggregation.<br>If frontend helpers remain, label them non-formal and keep them out of governed metric claims.<br>Update yield and ADB tests to prove DTO consumption or the explicitly non-formal boundary. | none |
| `P1-11` | CreditSpreadView keeps legacy summary visible and renders credit spread detail/fallback metadata. | If backend matrix is authoritative, render the provided matrix and fail closed when it is absent.<br>If frontend owns buckets, document bucket ownership in the contract and test boundary mapping.<br>Add rating/tenor bucket-boundary regression for the selected ownership rule. | rating/tenor bucket-boundary regression remains pending until owner selects matrix ownership |

## Prohibited Actions

- choose backend-vs-frontend ownership without business-owner and metric-governance input
- treat current frontend tests as approval for formal metric ownership
- change formal aggregation or rating-tenor bucket ownership before the selected rule is captured
- count this readiness packet as owner decision capture
- promote frontend-derived values to governed values without contract evidence

## Evidence Scope

- `read_only=true`
- `chooses_or_approves_conventions=false`
- `changes_code=false`
- `writes_duckdb=false`
- `writes_governance_records=false`
- `approves_metrics=false`
- `approves_pages=false`
- `captures_business_owner_approval=false`
- `captures_owner_decisions=false`
- `certifies_routes=false`
- `authorizes_ledger_pnl_governance_write=false`

## Boundary

This readiness packet is read-only. It maps P1-10 and P1-11 to current code/test anchors and post-owner execution gates; it does not choose or approve any calculation convention, change implementation code, capture owner decisions, approve metrics or pages, write governance records, authorize Ledger PnL --write, or certify routes.
