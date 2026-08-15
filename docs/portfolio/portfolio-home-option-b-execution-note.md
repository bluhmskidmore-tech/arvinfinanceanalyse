# Portfolio Home Option B Execution Note

Run date: 2026-06-06
Plan: `.omx/plans/portfolio-home-option-b-closure-plan-20260605T160501Z.md`
Page: `portfolio` (`PAGE-PORTFOLIO-HOME-001`)
Report date: `2026-05-31`

## Scope

This note records the first execution batch for Option B: evidence gates and owner-handoff readiness. It does not approve Portfolio Home, change owner decisions, edit maturity dates, alter KRD contracts, or promote the page to decision grade.

## MCP Evidence Availability

Deferred tool discovery exposed Playwright and generic app tools, but did not expose these project MCP servers in the current Codex App session:

- `moss-metric-contracts`
- `moss-lineage-evidence`
- `moss-data-catalog`
- `gitnexus`

Fallback evidence used:

- Existing Portfolio Home scorecard scripts.
- Read-only DuckDB evidence via the portfolio closure scripts.
- Manifest consistency checks for KRD and maturity remediation exports.
- Owner decision and approval packet validators.
- Planned Playwright/browser checks for UI surfacing after any frontend changes.

Residual risk:

- Metric definitions, lineage, and catalog facts are supported by local scripts/docs in this run, not by live project MCP server responses. Do not use this note to override metric contracts, source lineage, formal-use flags, or approval status.

## Evidence Commands Run

Evidence gates:

```text
python scripts/portfolio_home_closure_scorecard.py --limit 3
python scripts/portfolio_home_full_closure_evidence.py
python scripts/portfolio_home_risk_warning_consistency.py --require-consistent
python scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent
python scripts/portfolio_home_owner_decision_intake_check.py --limit 3
python scripts/portfolio_home_business_owner_approval_packet.py --limit 3
python scripts/portfolio_home_owner_action_packet.py --limit 3
python scripts/portfolio_home_owner_handoff_packet.py --limit 3
python scripts/portfolio_home_evidence_snapshot.py --scorecard-limit 1 --verifier-limit 1 --require-verifier-matched
```

Strict gates:

```text
python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score
python scripts/portfolio_home_full_closure_evidence.py --require-clean
python scripts/portfolio_home_risk_warning_consistency.py --require-clean
python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready
python scripts/portfolio_home_business_owner_approval_packet.py --limit 3 --require-ready
```

## Current Result

The evidence gates matched the expected blocked state:

- Current score: `99.86 / 100`
- Remaining gap: `0.14`
- Score status: `blocked`
- Full score ready: `false`
- Dependency consistency: `consistent`
- Risk warning consistency: `consistent`
- Owner intake status: `pending_owner_decisions`
- Business owner approval packet status: `pending`

Strict gates failed as expected because the page is not full-closure ready and the rematerialized risk tensor still carries `quality_flag=warning`.

## Current Blockers

- `risk_tensor_quality_warning`
- `krd_contract_decision_required`
- `bond_matured_outstanding_reconciliation_required`
- `tyw_liability_maturity_date_remediation_required`
- `business_owner_approval`
- `owner_decision_intake_blocked`

## Owner Actions

Risk owner:

- Review `risk_tensor_quality_warning`; parsed and recomputed warning evidence now match after risk tensor rematerialization.
- Decide whether to approve nearest KRD bucket mapping for `20Y`, `2Y`, and `6M`, require exact bucket schema, or reject.

Data owner:

- Reconcile the `6` matured non-zero bond positions at source; a scoped exclusion cannot close this blocker.
- Remediate or approve scoped exclusion for `1455` missing TYW liability maturity rows in the risk scope.

Business owner:

- Complete and sign `docs/portfolio/portfolio-home-business-owner-approval-template.md` only after risk/data decisions and required evidence review are captured.
- Reconcile risk-owner CSV decisions, nearest-bucket approval or exact-bucket schema evidence, data-owner CSV decisions, scoped-exclusion evidence, and business-owner approval through the owner-decision intake gate before any full-score activation.

## Activation Boundary

Keep these fields false/pending until strict evidence proves otherwise:

- `approval_status=pending`
- `formal_use_allowed=false`
- `closure_approved=false`
- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_capture_ready_page_execution=false`
- `captures_business_owner_approval=false`
