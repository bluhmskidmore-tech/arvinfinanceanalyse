# Portfolio Home Business Owner Approval Template

This template is not an approval until completed and signed by the business owner and risk owner.

Page ID: `PAGE-PORTFOLIO-HOME-001`
Page slug: `portfolio`
Primary API: `frontend aggregation: module-home/portfolio`
Approval check: `business_owner_approval`
Approval status: `approval_status=pending`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`

## Candidate Boundary

- Do not promote `/portfolio` to decision-grade page closure.
- Do not restate risk-date closure as full risk-tensor closure.
- Do not convert risk `quality_flag=warning` to `ok` without rematerialized evidence.
- Do not approve frontend-filled, inferred, or synthetic maturity evidence.

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_capture_ready_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`

## Full-Closure Activation Guard

The default values above keep this template candidate-only. Do not change any field in this section unless the full evidence packet has been reviewed and the strict scorecard gate is expected to pass.

To activate full page approval, all of the following fields must be changed together:

- `approval_status=approved`
- `formal_use_allowed=true`
- `closure_approved=true`
- `approves_metric_or_page=true`
- `writes_governance_records=true`
- `proves_capture_ready_page_execution=true`
- `captures_business_owner_approval=true`

Partial activation is invalid. For example, setting `formal_use_allowed=true` while leaving `approves_metric_or_page=false`, or setting `approves_metric_or_page=true` while leaving `closure_approved=false`, must remain blocked by `scripts/check_portfolio_home_business_owner_approval.py`.

Before signing a full page approval, rerun:

```text
python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score
python scripts/portfolio_home_evidence_snapshot.py --scorecard-limit 1 --verifier-limit 1 --require-verifier-matched
python scripts/portfolio_home_owner_action_packet.py --limit 3 --require-clean
python scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent
python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready
```

## Required Business Decision

Business owner name: `<required>`
Business owner role: `<required>`
Risk owner name: `<required>`
Risk owner role: `<required>`
Approval decision: `<approve | reject | request_changes>`
Approval date: `<YYYY-MM-DD>`
Business owner signature: `<required>`
Risk owner signature: `<required>`
Reviewed sign-off packet: `docs/portfolio/portfolio-home-full-closure-sign-off-packet.md`
Reviewed audit packet: `docs/audits/2026-06-05-portfolio-readiness-gate-audit.md`

## Required Risk Decisions

KRD contract decision: `<approve_nearest_bucket | require_exact_bucket_schema | reject>`
Maturity data decision: `<remediate_source | approve_scoped_exclusion | reject>`
Risk tensor warning decision: `<keep_warning | approve_after_clean_rerun | request_changes>`

If `approve_nearest_bucket` is selected, document why `2Y -> 3Y`, `6M -> 1Y`, and `20Y -> 30Y` are acceptable for the page's decision scope.

If `approve_scoped_exclusion` is selected, document the exact excluded rows, market value or principal, metric impact, and whether the page must continue to show a warning.

## Evidence Review

- Governance record reviewed: `<yes | no>`
- Supporting sample `GS-PORTFOLIO-HOME-A` reviewed: `<yes | no>`
- Risk warning sample `GS-RISK-WARN-B` reviewed: `<yes | no>`
- Live proof reviewed: `<yes | no>`
- DuckDB maturity-gap evidence reviewed: `<yes | no>`
- KRD remap evidence reviewed: `<yes | no>`
- Verification commands rerun before approval: `<yes | no>`
- Candidate-only boundary accepted: `<yes | no>`

## Notes

Decision notes: `<required if reject, request_changes, approve_nearest_bucket, or approve_scoped_exclusion>`
