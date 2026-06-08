# Product-Category PnL Business Owner Approval Template

This template is not an approval until completed and signed by the business owner.

Page ID: `PAGE-PROD-CAT-001`
Page slug: `product-category-pnl`
Primary API: `/ui/pnl/product-category`
Approval check: `business_owner_approval`
Approval status: `approval_status=pending`
Formal use allowed: `formal_use_allowed=true`
Closure approved: `closure_approved=false`

## Evidence Boundary

- `formal_use_allowed=true` reflects the currently routed formal/governed readiness state.
- `closure_approved=false` must remain until manual audit review, closure checklist review, browser evidence review, and business-owner approval are all captured.
- `GS-PROD-CAT-PNL-A` must be reconciled before final certification wording because readiness reports an approved boundary while the approval artifact still says `captured-awaiting-approval`.
- `scripts/check_product_category_pnl_business_owner_approval.py --require-captured` verifies this artifact directly; setting the review line to `yes` is not enough unless `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md` itself says `Status: approved` with non-placeholder owner, approver, and approval date.
- The same checker verifies `docs/pnl/product-category-closure-checklist.md` directly; setting `Closure checklist units reviewed` to `yes` is not enough while any closure unit remains `PARTIAL` or `NOT_TRUSTED`.
- The reviewed boundary and first-certification packet paths must match the expected paths and the files must exist; a correct-looking template path is not enough if the packet artifact is missing.
- Setting `Owner decision packet reviewed` to `yes` requires `docs/pnl/product-category-pnl-owner-decision-packet.md` to exist. The packet is intake evidence only and does not capture the owner/API decision outcomes.
- `docs/pnl/product-category-pnl-owner-decision-packet.md` is the owner/API decision intake for 3 product decisions and 2 API/contract blockers; reviewing it is required before approval, but the packet itself does not capture those decisions.
- The same owner-decision packet now separates 5 formal decision items plus 4 next-review queue topics. Setting `Owner decision next-review queue acknowledged` to `yes` means the reviewer saw that queue topics are intake follow-ups and do not count as captured decisions.
- `docs/pnl/product-category-pnl-first-certification-packet.md` includes an Owner Readiness Receipt and Business Owner Action Signoff Matrix with `owner_signable=false` and `can_promote_certification=false`; reviewing these sections does not approve the page or remove human-required blockers.
- The same packet includes a Pre-Signature Verification Rerun Receipt with `packet_generator_reruns_gate=false` and `verification_commands_rerun_captured=false`; owner signature requires rerunning `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-readiness.ps1 -PageSlug product-category-pnl -Run -CheckLive`.
- Setting review fields to `yes` does not bypass golden approval, manual checklist closure, owner decisions, or strict checker failure.
- The current boundary covers `MTR-PCP-001` through `MTR-PCP-012` only.
- Additional product-category fields require a new approved matrix, dictionary row, sample assertion, and test bundle.

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`

## Required Business Decision

Business owner name: `<required>`
Business owner role: `<required>`
Approval decision: `<approve | reject | request_changes>`
Approval date: `<YYYY-MM-DD>`
Business owner signature: `<required>`
Reviewed boundary packet: `docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json`
Reviewed first-certification packet: `docs/pnl/product-category-pnl-first-certification-packet.md`

## Evidence Review

- Governance record reviewed: `<yes | no>`
- Owner decision packet reviewed: `<yes | no>`
- Owner decision next-review queue acknowledged: `<yes | no>`
- Golden sample `GS-PROD-CAT-PNL-A` approval artifact reconciled: `<yes | no>`
- Closure checklist units reviewed: `<yes | no>`
- Fallback liability branch model-boundary evidence reviewed: `<yes | no>`
- UI/API payload evidence reviewed: `<yes | no>`
- Live smoke evidence reviewed: `<yes | no>`
- Verification commands rerun before approval: `<yes | no>`
- Evidence-pending boundary accepted: `<yes | no>`

## Notes

Decision notes: `<required if reject or request_changes>`
