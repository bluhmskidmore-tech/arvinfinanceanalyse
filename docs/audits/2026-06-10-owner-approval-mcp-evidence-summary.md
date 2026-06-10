# 2026-06-10 Owner-Approval MCP Evidence Summary

## Scope

This summary covers the seven page routes that currently have business-owner approval pending in the system-wide audit:

- product-category-pnl
- balance-analysis
- average-balance
- ledger-pnl
- pnl-attribution
- bond-analysis
- stock-analysis

Evidence was collected through local read-only MOSS MCP stdio calls and the page-specific business-owner approval checkers. The direct Codex App MCP tool surface was still unavailable in this session, so this document records local MCP-server evidence only.

## Boundary

This document does not approve metrics or pages, does not write governance records, and does not capture business-owner approval. The MCP packet section records local read-only MCP evidence only; the supplemental verification section records separate page/API smoke and test evidence gathered during this audit. None of that supplemental evidence promotes any page to owner-approved closure.

## MCP Evidence Summary

| Page | Page ID | Route | Primary API | Audit Review Status | Record Status | Manual Blockers | Evidence Present For Review | Closure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| product-category-pnl | PAGE-PROD-CAT-001 | /product-category-pnl | /ui/pnl/product-category | ready_for_audit_review | direct_records_ready_for_audit_review; ready=1; direct=1; expanded=20 | ui_api_payload_review; business_owner_approval | live_smoke_evidence_review | closure_approved=false |
| balance-analysis | PAGE-BALANCE-001 | /balance-analysis | /ui/balance-analysis/overview | ready_for_audit_review | direct_records_ready_for_audit_review; ready=1; direct=1; expanded=20 | ui_api_payload_review; live_smoke_evidence_review; business_owner_approval | none | closure_approved=false |
| average-balance | GAP-AVERAGE-BALANCE-PAGE | /average-balance | /api/analysis/adb | ready_for_audit_review | direct_records_ready_for_audit_review; ready=1; direct=1; expanded=0 | ui_api_payload_review; live_smoke_evidence_review; business_owner_approval | none | closure_approved=false |
| ledger-pnl | PAGE-LEDGER-PNL-001 | not packaged; blocked row | not packaged; blocked row | blocked_by_record_gaps | blocked before ready direct-record review | direct_page_api_record_fields | none | closure_approved=false |
| pnl-attribution | PAGE-PNL-ATTR-WB-001 | /pnl-attribution | /api/pnl-attribution/volume-rate | ready_for_audit_review | direct_records_ready_for_audit_review; ready=1; direct=1; expanded=20 | business_owner_approval | ui_api_payload_review; live_smoke_evidence_review | closure_approved=false |
| bond-analysis | PAGE-BOND-ANALYSIS-001 | /bond-analysis | /api/bond-analytics/action-attribution | ready_for_audit_review | direct_records_ready_for_audit_review; ready=1; direct=1; expanded=20 | ui_api_payload_review; live_smoke_evidence_review; business_owner_approval | none | closure_approved=false |
| stock-analysis | GAP-STOCK-ANALYSIS-PAGE | /stock-analysis | /ui/market-data/livermore | ready_for_audit_review | direct_records_ready_for_audit_review; ready=1; direct=1; expanded=0 | ui_api_payload_review; live_smoke_evidence_review; business_owner_approval | none | closure_approved=false |

All seven MCP packets or blocked rows preserve the same evidence scope:

- `writes_governance_records=false`
- `approves_metric_or_page=false`
- `proves_page_execution=false`
- `runs_ui_or_api_smoke=false`
- `captures_business_owner_approval=false`
- `aggregates_mcp_evidence=true`

## Business-Owner Approval Gate Summary

| Page | Normal Check | Strict `--require-captured` | Approval Status | Captured | Formal Use Allowed | Closure Approved | Action Items |
| --- | --- | --- | --- | --- | --- | --- | ---: |
| product-category-pnl | exit 0 | exit 1 | pending | false | true | false | 15 |
| balance-analysis | exit 0 | exit 1 | pending | false | true | false | 11 |
| average-balance | exit 0 | exit 1 | pending | false | false | false | 13 |
| ledger-pnl | exit 0 | exit 1 | pending | false | false | false | 11 |
| pnl-attribution | exit 0 | exit 1 | pending | false | false | false | 11 |
| bond-analysis | exit 0 | exit 1 | pending | false | false | false | 12 |
| stock-analysis | exit 0 | exit 1 | pending | false | false | false | 11 |

Total approval action items: 84.

## Fresh Approval Action Matrix

The approval checkers were rerun after the browser smoke data-source contract audit. All seven pages still share the same owner-capture blocker set: owner identity, approval decision, approval date, and owner signature are missing. The page-specific work below is evidence review and boundary acknowledgement only; it still does not approve closure.

| Page | Missing owner fields | Pending evidence / boundary review items |
| --- | --- | --- |
| product-category-pnl | business_owner_name; business_owner_role; approval_decision; approval_date; business_owner_signature | governance_record_review; reviewed_owner_decision_packet; owner_decision_next_review_queue_acknowledgement; golden_sample_artifact_reconciliation; closure_checklist_review; fallback_liability_branch_boundary_review; ui_api_payload_review; live_smoke_evidence_review; verification_commands_rerun; evidence_pending_boundary_acceptance |
| balance-analysis | business_owner_name; business_owner_role; approval_decision; approval_date; business_owner_signature | governance_record_review; golden_sample_review; ui_api_payload_review; live_smoke_evidence_review; verification_commands_rerun; formal_balance_boundary_acceptance |
| average-balance | business_owner_name; business_owner_role; approval_decision; approval_date; business_owner_signature | governance_record_review; daily_golden_sample_review; ui_api_payload_review; live_smoke_evidence_review; verification_commands_rerun; candidate_boundary_acceptance; formal_balance_truth_boundary_acceptance; monthly_adb_nim_boundary_acceptance |
| ledger-pnl | business_owner_name; business_owner_role; approval_decision; approval_date; business_owner_signature | governance_record_review; dedicated_golden_sample_review; ui_api_payload_review; live_smoke_evidence_review; verification_commands_rerun; candidate_boundary_acceptance |
| pnl-attribution | business_owner_name; business_owner_role; approval_decision; approval_date; business_owner_signature | governance_record_review; golden_sample_review; ui_api_payload_review; live_smoke_evidence_review; verification_commands_rerun; candidate_boundary_acceptance |
| bond-analysis | business_owner_name; business_owner_role; approval_decision; approval_date; business_owner_signature | governance_record_review; golden_sample_review; fixed_income_convention_review; fixed_income_rule_review; ui_api_payload_review; live_smoke_evidence_review; verification_commands_rerun |
| stock-analysis | business_owner_name; business_owner_role; approval_decision; approval_date; business_owner_signature | governance_record_review; golden_sample_review; ui_api_payload_review; live_smoke_evidence_review; verification_commands_rerun; not_trading_instruction_review |

Fastest closure order from current evidence:

1. `pnl-attribution`: MCP packet already has UI/API payload and live-smoke evidence present for review; only owner review/signoff remains in this summary.
2. `product-category-pnl`: formal use is allowed and live-smoke evidence is present, but it has the largest approval action list and open closure-checklist review.
3. `balance-analysis`: formal use is allowed, but UI/API payload, live-smoke, golden-sample review, and formal-balance boundary acceptance still need owner review.
4. `bond-analysis`, `average-balance`, and `stock-analysis`: all need candidate/boundary acceptance plus UI/API and live-smoke review before owner signature.
5. `ledger-pnl`: keep last until the MCP `direct_page_api_record_fields` record gap is cleared; signing cannot close this page while the direct page/API record is blocked.

## Ledger PnL Direct-Record Drill-Down

A fresh Ledger PnL dry-run at `2026-06-10T19:22:49+08:00` confirms the current direct-record issue is not a missing-field problem in the candidate payload. `python scripts\emit_ledger_pnl_governance_record.py` generated a field-complete `PAGE-LEDGER-PNL-001` candidate for `/api/ledger-pnl/summary` with:

- `report_date=2026-05-31`
- `basis=ledger`
- `source_surface=ledger_pnl.summary`
- `source_version=sv_product_category_3353b116b9a6`
- `rule_version=rv_ledger_pnl_v1`
- `cache_version=cv_ledger_pnl_v1`
- `cache_key=ledger_pnl.summary:2026-05-31:ALL`
- `formal_use_allowed=false`

The same dry-run returned `record_write_status=not_requested`, `existing_record_line=null`, and `validation_status=ready_for_audit_review`. A direct search of `data/governance/cache_manifest.jsonl` found no matching `PAGE-LEDGER-PNL-001`, `/api/ledger-pnl/summary`, or `ledger_pnl.summary:2026-05-31:ALL` record.

Implication: Ledger PnL has an evidence-backed candidate record, but no written direct page/API governance record. The approved governance workflow still needs to write or locate that record, then rerun governance validation and manual audit review. This dry-run does not approve page closure, promote `MTR-LPN-001` through `MTR-LPN-003`, prove live page/API execution, or capture owner approval.

## Owner Review Implications

- Product Category PnL and Balance Analysis have `formal_use_allowed=true`, but both remain `closure_approved=false` and approval-captured=false.
- Ledger PnL is not ready for the same manual-review path as the other six pages because the local MCP packet still reports `blocked_by_record_gaps` and `direct_page_api_record_fields`.
- PnL Attribution has UI/API payload and live-smoke evidence present for manual review, leaving business-owner approval as the only MCP packet blocker in this summary.
- Product Category PnL has live-smoke evidence present for manual review, but UI/API payload review and business-owner approval remain open.
- Balance Analysis, Average Balance, Bond Analysis, and Stock Analysis still need UI/API payload review, live-smoke evidence review, and business-owner approval.

## Supplemental Page Verification

The seven pending pages were also checked through the repository's page verification surfaces. These checks increase technical confidence but do not change the owner approval gate above.

| Check | Result | Boundary |
| --- | --- | --- |
| `scripts/codex-verify-page.ps1 -PageSlug <page> -DryRun` for all seven pages | All seven expand page-specific MCP/backend/frontend/browser/global verification plans | Planning evidence only; no page approval |
| Browser a11y smoke slice for `@product-category-pnl`, `@balance-analysis`, `@average-balance`, `@bond-analysis`, `@ledger-pnl`, `@stock-analysis`, `@pnl-attribution` with `--workers=1` | 7 passed; screenshots written under `.codex-tmp/playwright-page-results/owner-pending-7-sequential-20260610072852` | Verifies ready selectors and zero critical axe violations in local frontend smoke only |
| Initial parallel browser a11y smoke slice | 3 passed; 4 failed from axe execution context destroyed during page navigation | Treated as parallel-run instability; single-worker rerun above is the stable evidence |
| Seven-page frontend page/model/component slice | 20 test files passed; 517 tests passed | Component/model evidence only |
| Seven-page backend/API/service/governance slice | 592 tests passed after the PnL Attribution empty-storage fix | Technical contract evidence only |
| PnL Attribution API contract isolated rerun | 4 passed | Confirms missing DuckDB storage now returns warning/empty envelope instead of server exception |

During this audit, PnL Attribution's service layer was narrowly adjusted so a missing DuckDB file returns an empty report-date list for Attribution workbench empty-state envelopes. Formal PnL APIs and non-missing DuckDB errors still fail closed with `Formal pnl storage is unavailable.`

## Verification Commands

- Local MCP stdio call: `moss-lineage-evidence.get_page_governance_audit_evidence_packet` for each of the seven pages.
- Approval checker normal mode for all seven pages, refreshed at `2026-06-10T19:26:44+08:00` -> exit 0 with `approval_status=pending` and `business_owner_approval_captured=false`.
- Approval checker strict mode for all seven pages, refreshed at `2026-06-10T19:26:44+08:00` -> exit 1, preserving the fail-closed owner approval gate.
- Owner approval status pytest suite, refreshed at `2026-06-10T19:26:44+08:00` -> 93 passed.
- `npm run test:a11y-smoke -- --grep '@(product-category-pnl|balance-analysis|average-balance|bond-analysis|ledger-pnl|stock-analysis|pnl-attribution)' --workers=1` -> 7 passed.
- `npm.cmd run test -- <seven-page frontend test slice>` -> 20 test files passed, 517 tests passed.
- PnL Attribution empty-storage and formal PnL storage fail-closed pytest slice -> 15 passed.
- Seven-page backend/API/service/governance pytest slice -> 592 passed in 669.70s.
