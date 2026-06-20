# Product-Category PnL Approval Runbook

This runbook makes the owner review path executable. It does not approve the page, write governance records, reconcile golden-sample approval, set `closure_approved=true`, or capture business-owner approval.

## Current Status

- Page: `product-category-pnl`
- Page ID: `PAGE-PROD-CAT-001`
- Primary API: `/ui/pnl/product-category`
- Current certification state: `evidence-pending`
- Current approval state: `business_owner_approval_captured=false`
- Current closure state: `closure_approved=false`
- Current golden approval artifact: `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md`
- Current golden approval artifact status: `captured-awaiting-approval`
- Current readiness golden boundary: `golden_boundary_status=approved`
- Current golden artifact approval: `golden_artifact_status=captured-awaiting-approval`; `golden_artifact_approved=false`; `golden_sample_approval_artifact_mismatch=true`
- Boundary: readiness boundary pass is not golden approval; the approval artifact still requires non-placeholder owner, approver, and approval date.
- Current closure checklist: `docs/pnl/product-category-closure-checklist.md`
- Current closure checklist state: 10 units remain `PARTIAL`
- Current business contract certified count: `business_contract_certified_count=0`

## Owner Review Consistency Receipt

The current packet/template consistency receipt is valid for owner review only:

- `certification_packet_consistency.status=valid`
- `certification_packet_consistency.missing_marker_count=0`
- `certification_packet_consistency.approval_action_item_count=15`
- `certification_packet_consistency.business_owner_action_signoff_item_count=15`
- `certification_packet_consistency.business_owner_action_signed_item_count=0`
- `certification_packet_consistency.business_owner_action_pending_or_missing_item_count=15`
- `business_owner_action_signoff_group_counts.owner_identity=2`
- `business_owner_action_signoff_group_counts.owner_decision=3`
- `business_owner_action_signoff_group_counts.evidence_review=7`
- `business_owner_action_signoff_group_counts.pre_signature_verification=2`
- `business_owner_action_signoff_group_counts.boundary_acceptance=1`
- `business_owner_action_signed_group_counts.none=0`
- `business_owner_action_pending_group_counts.owner_identity=2`
- `business_owner_action_pending_group_counts.owner_decision=3`
- `business_owner_action_pending_group_counts.evidence_review=7`
- `business_owner_action_pending_group_counts.pre_signature_verification=2`
- `business_owner_action_pending_group_counts.boundary_acceptance=1`
- `business_owner_action_missing_or_invalid_item_count=5`
- `business_owner_action_pending_review_item_count=10`
- Grouped owner-action distribution is owner-review intake evidence only; it does not sign, approve, or certify any item.
- `certification_packet_consistency.owner_signable=false`
- `certification_packet_consistency.can_promote_certification=false`
- `certification_packet_consistency.approves_metric_or_page=false`
- `certification_packet_consistency.captures_business_owner_approval=false`
- `certification_packet_consistency.captures_business_owner_signature=false`
- `certification_packet_consistency.captures_product_or_api_decisions=false`
- `certification_packet_consistency.captures_golden_sample_approval=false`
- `certification_packet_consistency.captures_closure_approval=false`
- `certification_packet_consistency.writes_governance_records=false`
- `certification_packet_consistency.verification_commands_rerun_captured=false`
- `certification_packet_consistency.certification_effect=none`

This receipt means the first-certification packet, owner-decision packet, and approval template agree on counts and non-approval boundaries. It does not approve the page, capture approval, or certify the route.

## Generated Artifact Freshness Scope

- `generated_artifact_freshness_scope.artifact_count=2`
- `generated_artifact_freshness_scope.valid_artifact_count=2`
- `generated_artifact_freshness_scope.stale_or_missing_artifact_count=0`
- `generated_artifact_freshness_scope.freshness_check_effect=none`
- `generated_artifact_freshness_scope.captures_business_owner_approval=false`
- `generated_artifact_freshness_scope.captures_product_or_api_decisions=false`
- `generated_artifact_freshness_scope.captures_golden_sample_approval=false`
- `generated_artifact_freshness_scope.captures_closure_approval=false`
- `generated_artifact_freshness_scope.writes_governance_records=false`
- `generated_artifact_freshness_scope.certification_effect=none`

The freshness scope proves generated packet alignment only. It does not approve, sign, write governance records, capture decisions, or certify the route.

## Owner Action Status Scope

- Scope kind: `owner_action_status_scope`
- `missing_or_invalid_item_count=5`
- `pending_review_item_count=10`
- `owner_signable=false`
- `captures_business_owner_approval=false`
- `captures_product_or_api_decisions=false`
- `can_promote_certification=false`
- `certification_effect=none`
- Boundary: Owner-action status split is reviewer intake evidence only; it does not capture business-owner approval, product/API decisions, or route certification.

## Owner Pre-Signature Blocker Scope

- Scope kind: `owner_pre_signature_blocker_scope`
- `remaining_blocker_count=16`
- `approval_action_item_count=15`
- `signed_item_count=0`
- `unsigned_item_count=15`
- `missing_or_invalid_item_count=5`
- `pending_review_item_count=10`
- Pre-signature group counts: `owner_identity=2`, `owner_decision=3`, `evidence_review=7`, `pre_signature_verification=2`, `boundary_acceptance=1`
- `owner_signable=false`
- `captures_business_owner_approval=false`
- `captures_product_or_api_decisions=false`
- `can_promote_certification=false`
- `certification_effect=none`
- Boundary: Owner pre-signature blocker scope is a checklist boundary only; it does not approve, sign, certify, or capture product/API decisions.

Machine-readable blockers now include the full remaining blocker list, approval action blocker list, and checklist rows with signoff group, template field, required value, current status, owner-signature blocking flag, and certification effect. Required blockers still include `owner_decision_next_review_queue_acknowledgement`, `verification_commands_rerun`, and `evidence_pending_boundary_acceptance`.

## Review Packets

The owner or delegated reviewer must review these artifacts before any approval can be captured:

| Required artifact | Purpose | Approval effect |
| --- | --- | --- |
| `docs/pnl/product-category-pnl-first-certification-packet.md` | Source-to-screen trace and evidence-pending boundary for `MTR-PCP-001` through `MTR-PCP-012` | None |
| `docs/pnl/product-category-pnl-owner-decision-packet.md` | Class 1 product decisions and Class 2 API/contract decisions still pending | None |
| `docs/pnl/product-category-pnl-business-owner-approval-template.md` | The only owner template checked by the approval checker | Captures approval only after all required fields are real |
| `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md` | Direct golden-sample approval artifact | Blocks approval while status/owner/approver/date are placeholders |
| `docs/pnl/product-category-closure-checklist.md` | Unit-level closure state | Blocks approval while any unit remains `PARTIAL` or `NOT_TRUSTED` |
| `docs/pnl/product-category-remaining-blockers.md` | Owner/API/evidence blocker triage | None |

## Fields Codex Must Not Fill

Codex must not invent or fill these values:

- business owner name
- business owner role
- approval decision
- approval date
- business owner signature
- golden-sample owner
- golden-sample approver
- golden-sample approved-at date
- product decision outcomes
- backend/API contract decision outcomes

These fields require a real accountable owner or authorized governance workflow.

## Approval Template Review Fields

The approval checker requires the owner template to include real identity fields and the following review confirmations:

| Template field | Required value before approval can pass |
| --- | --- |
| `- Governance record reviewed` | `yes` |
| `- Owner decision packet reviewed` | `yes` |
| `- Owner decision next-review queue acknowledged` | `yes` |
| `- Golden sample `GS-PROD-CAT-PNL-A` approval artifact reconciled` | `yes` |
| `- Closure checklist units reviewed` | `yes` |
| `- Fallback liability branch model-boundary evidence reviewed` | `yes` |
| `- UI/API payload evidence reviewed` | `yes` |
| `- Live smoke evidence reviewed` | `yes` |
| `- Verification commands rerun before approval` | `yes` |
| `- Evidence-pending boundary accepted` | `yes` |

The checker also requires:

- `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md` to say `Status: approved`
- golden owner, approver, and approved-at fields to be non-placeholder
- `docs/pnl/product-category-closure-checklist.md` to have no `PARTIAL` or `NOT_TRUSTED` units
- the reviewed boundary packet path to match `docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json` and the file to exist
- the reviewed first-certification packet path to match `docs/pnl/product-category-pnl-first-certification-packet.md` and the file to exist
- `docs/pnl/product-category-pnl-owner-decision-packet.md` to exist when `- Owner decision packet reviewed` is set to `yes`
- next-review queue topics are intake follow-ups and do not count as captured decisions

## Pre-Approval Commands

Run these commands immediately before an approval review:

```powershell
python scripts/product_category_pnl_first_certification_packet.py
python scripts/product_category_pnl_owner_decision_packet.py
python scripts/check_product_category_pnl_business_owner_approval.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-readiness.ps1 -PageSlug product-category-pnl -Run -CheckLive
```

Pre-approval command receipt:

- `pre_approval_command_receipt.status=pending_rerun`
- `pre_approval_command_receipt.required_command_count=5`
- Required command count includes the two packet refresh commands, approval checker, fresh live readiness command, and the strict negative-control command below.
- `pre_approval_command_receipt.business_owner_approval_captured=false`
- `pre_approval_command_receipt.strict_negative_control_expected_exit=non_zero`
- `pre_approval_command_receipt.certification_effect=none`

Expected before real approval:

- first-certification packet is regenerated
- owner-decision packet is regenerated
- approval checker reports `approval_status=pending`
- fresh live readiness completes without changing `business_owner_approval_captured=false`

Run this command as a negative control:

```powershell
python scripts/check_product_category_pnl_business_owner_approval.py --require-captured
```

Expected before real approval:

- command exits non-zero
- output lists the remaining approval action items
- this strict negative control must continue to fail until real owner approval is captured

## Frontend And Route Verification

Run these checks if any visible product-category page behavior changed:

```powershell
cd frontend
npm run test -- src/test/ProductCategoryPnlPage.test.tsx
npm run test -- src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts
npm run debt:audit
```

Then run browser/page verification from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-page-smoke.ps1 -PageSlug product-category-pnl
powershell -ExecutionPolicy Bypass -File scripts/codex-verify-page.ps1 -PageSlug product-category-pnl -Run
```

## Final Approval Gate

Only after real owner and governance evidence exists, run:

```powershell
python scripts/check_product_category_pnl_business_owner_approval.py --require-captured
```

The page can be described as business-owner approved only if this command exits `0` and the current artifacts prove every required field. A passing frontend test, browser smoke, or generated packet is not enough.
