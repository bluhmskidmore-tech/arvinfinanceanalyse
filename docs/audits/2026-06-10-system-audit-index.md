# 2026-06-10 System Audit Index

## Read First

Use this index as the entry point for the 2026-06-10 MOSS system-wide skills audit. The audit is evidence-oriented and fail-closed: it documents technical confidence, open blockers, and next actions, but it does not approve metrics, pages, governance records, or business-owner signoff.

## Current State

| Gate | Current Evidence | Status |
| --- | --- | --- |
| Executive summary | `2026-06-10-system-audit-executive-summary.zh.md` | Chinese one-page summary for owner/management review |
| Owner review brief | `2026-06-10-owner-review-brief.zh.md` | Chinese meeting brief for owner decisions, page approval sequencing, and Ledger PnL gap handling |
| Owner decision capture template | `2026-06-10-owner-decision-capture-template.zh.md` | Chinese fill-in template for owner meeting outputs and post-meeting gate intake |
| Machine-readable manifest | `2026-06-10-system-audit-manifest.json` | fail-closed status, artifact map, counts, open blockers, and verification evidence |
| System-wide audit report | `2026-06-10-system-wide-skills-audit.md` | report assembled with closed findings, open findings, verification, and residual risks |
| Execution queue | `2026-06-10-system-audit-action-register.md` | 10 prioritized action rows |
| Calculation/display decisions | `2026-06-10-calculation-p1-owner-decision-matrix.md` | 10 remaining P1 owner-decision rows; P1-08 bond-dashboard null handling verified closed |
| Owner approvals | `2026-06-10-owner-approval-mcp-evidence-summary.md` | 7 pages pending approval, strict gate still fail-closed |
| Owner approval fail-closed snapshot | `2026-06-10-owner-approval-fail-closed-snapshot.json` | 7 pending, 0 captured, 0 closure-approved, 84 action items, strict gate rejected 7/7 |
| Direct App MCP/GitNexus tool surface | `2026-06-10-direct-app-mcp-gitnexus-tool-surface-snapshot.json`; `2026-06-10-direct-app-mcp-gitnexus-tool-surface-runbook.md` | current App tool discovery found 0 direct MOSS/GitNexus tools; local registration exists but direct evidence remains open |
| Ledger PnL direct governance record | `2026-06-10-ledger-pnl-direct-governance-record-snapshot.json`; `2026-06-10-ledger-pnl-direct-governance-record-runbook.md` | dry-run candidate is field-complete, but no written direct record exists |
| Local secret hygiene | `2026-06-10-local-secret-hygiene-snapshot.json`; `2026-06-10-local-secret-hygiene-runbook.md` | ignored/untracked `config/.env` contains local findings by secret name only; values are not captured |
| Business display coverage | `business-display-coverage-report.json` | 26 tracked routes, 0 route gaps |
| Real backend smoke runbook | `2026-06-10-real-backend-smoke-runbook.md` | exact commands, exclusions, and acceptance criteria for the still-open live backend smoke gate |
| Audit package contract test | `tests/test_system_audit_manifest_contract.py` | `pytest tests/test_system_audit_manifest_contract.py -q` checks artifact links, fail-closed flags, direct App MCP/GitNexus gap boundaries, and coverage/fresh-verification counts |
| Route/page certification | readiness and MCP queues cited in main report | 0 business-contract-certified routes |

## Artifact Map

| Artifact | Use It For | Do Not Use It For |
| --- | --- | --- |
| `2026-06-10-system-audit-executive-summary.zh.md` | Chinese first-read summary of what is fixed, what is blocked, and what to do next. | Formal approval or replacing the evidence reports. |
| `2026-06-10-owner-review-brief.zh.md` | Business-owner meeting agenda: 10 remaining P1 decisions, seven page approval sequence, and Ledger PnL direct-record handling. | Approving calculations, pages, governance records, or owner signatures. |
| `2026-06-10-owner-decision-capture-template.zh.md` | Capturing owner meeting outputs before they are copied into authoritative page templates, calc rules, or governance workflows. | Acting as a signed approval, governance record, route certification, or strict checker result. |
| `2026-06-10-system-audit-manifest.json` | Machine-readable audit status for automation, handoff, and quick gate checks. | Replacing owner approval, governance records, route certification, or source-backed evidence. |
| `2026-06-10-system-wide-skills-audit.md` | Main narrative audit, closed findings, open findings, verification evidence, residual risks. | Final business certification or owner approval. |
| `2026-06-10-system-audit-action-register.md` | Current execution queue: priority, owner/decision source, next evidence, verification gate. | Replacing the underlying evidence files. |
| `2026-06-10-calculation-logic-audit.md` | Read-only deep calculation/display review across formal finance modules and frontend display chains. | Immediate code changes before business-rule decisions. |
| `2026-06-10-calculation-p1-owner-decision-matrix.md` | Owner review of 10 remaining P1 calculation/display decisions, with P1-08 recorded as verified closed. | Approving any convention by itself. |
| `2026-06-10-owner-approval-mcp-evidence-summary.md` | Seven pending owner-approval pages, MCP packet status, missing owner fields, Ledger PnL direct-record drill-down. | Capturing owner signature or approving page closure. |
| `2026-06-10-owner-approval-fail-closed-snapshot.json` | Machine-readable current owner-approval gate status across the seven pending pages. | Capturing approval, replacing owner templates, or certifying routes. |
| `2026-06-10-direct-app-mcp-gitnexus-tool-surface-snapshot.json` | Machine-readable direct App tool discovery result, local MCP/GitNexus registration presence, and fail-closed interpretation. | Replacing direct App MCP/GitNexus evidence, approving metrics/pages, or certifying routes. |
| `2026-06-10-direct-app-mcp-gitnexus-tool-surface-runbook.md` | Fresh-session retry procedure for collecting direct Codex App MCP/GitNexus evidence and comparing it to local stdio evidence. | Treating local stdio MCP checks as direct App-surface closure. |
| `2026-06-10-ledger-pnl-direct-governance-record-snapshot.json` | Machine-readable Ledger PnL direct-record gap status, dry-run candidate key, written-record search result, and readiness boundary. | Writing the governance record, proving live execution, or approving Ledger PnL. |
| `2026-06-10-ledger-pnl-direct-governance-record-runbook.md` | Authorized follow-up procedure for writing or locating the Ledger PnL direct page/API record and rerunning downstream gates. | Substituting dry-run evidence for an approved write or owner approval. |
| `2026-06-10-local-secret-hygiene-snapshot.json` | Machine-readable local secret boundary status: secret names only, ignored/untracked file checks, redacted scan plan. | Reading, rotating, clearing, approving, or committing secret values. |
| `2026-06-10-local-secret-hygiene-runbook.md` | Environment-owner procedure for rotating/removing/accepting local-only secret findings and rerunning redacted scans. | Weakening scan rules, exposing values, or replacing clean-runner evidence. |
| `business-display-coverage-report.json` | Machine-readable route coverage and smoke/a11y mapping. | Proving business correctness or running browser smoke. |
| `2026-06-10-real-backend-smoke-runbook.md` | Running and recording the full real-backend browser smoke once a live backend target is ready. | Substituting mock, route-mocked, or dry-run evidence for live backend closure. |
| `tests/test_system_audit_manifest_contract.py` | Re-running the audit package consistency guard after edits to the manifest, coverage report, owner brief, or capture template. | Proving business correctness, running browser smoke, or replacing owner/governance evidence. |
| `2026-06-10-average-balance-candidate-verification.md` | Average Balance candidate verification context. | Formal page certification without owner approval. |

## Fast Path For The Next Reviewer

1. Start with `2026-06-10-system-wide-skills-audit.md` for the full picture.
2. For owner/management review, read `2026-06-10-system-audit-executive-summary.zh.md`.
3. For the owner decision meeting, use `2026-06-10-owner-review-brief.zh.md`.
4. During or after that meeting, record outputs in `2026-06-10-owner-decision-capture-template.zh.md`.
5. For automation or quick status checks, read `2026-06-10-system-audit-manifest.json`.
6. After audit package edits, run `pytest tests/test_system_audit_manifest_contract.py -q`.
7. Use `2026-06-10-system-audit-action-register.md` as the current work queue.
8. For calculation decisions, review `2026-06-10-calculation-p1-owner-decision-matrix.md` with the business owner.
9. For page closure, review `2026-06-10-owner-approval-mcp-evidence-summary.md` and keep Ledger PnL last until its direct record gap is cleared.
10. For a machine-readable owner gate check, read `2026-06-10-owner-approval-fail-closed-snapshot.json`.
11. For the direct App MCP/GitNexus gap, read `2026-06-10-direct-app-mcp-gitnexus-tool-surface-snapshot.json`, then use `2026-06-10-direct-app-mcp-gitnexus-tool-surface-runbook.md` in a fresh session.
12. For the Ledger PnL direct-record gap, read `2026-06-10-ledger-pnl-direct-governance-record-snapshot.json`, then use `2026-06-10-ledger-pnl-direct-governance-record-runbook.md` only under approved governance-owner authorization.
13. For local secret hygiene, read `2026-06-10-local-secret-hygiene-snapshot.json`, then use `2026-06-10-local-secret-hygiene-runbook.md` without exposing values.
14. For the live browser gate, use `2026-06-10-real-backend-smoke-runbook.md` when a real backend target is ready.
15. For route coverage, regenerate `business-display-coverage-report.json` after any browser-smoke scope change.

## Standing Boundaries

- `closure_approved=false` remains authoritative for pending pages.
- `formal_use_allowed=false` remains authoritative for candidate/pending pages unless an approved governance workflow changes it.
- Dry-run governance records are evidence, not written records.
- Local stdio MCP evidence is fallback evidence, not direct App MCP/GitNexus evidence.
- Mock smoke and route-mocked real-client smoke are not a substitute for full real-backend smoke.
- Local ignored/untracked secrets must not be committed into any audit artifact.
