# 2026-06-10 System Audit Action Register

## Purpose

This register turns the system-wide audit into an execution queue. It does not approve metrics, pages, governance records, or business-owner signoff. It records what can move next, who must decide, what evidence is needed, and which command or artifact should prove closure.

## Status Summary

| Lane | Current Status | Closure State |
| --- | --- | --- |
| Business-owner approvals | 7 high-risk pages remain pending | blocked on owner identity, decision, date, signature, and page-specific evidence review |
| Ledger PnL governance record | dry-run candidate is field-complete, but no written direct record exists | blocked until approved governance workflow writes or locates direct page/API record |
| Calculation/display P1s | 10 open P1 items; P1-08 bond-dashboard null handling is verified closed | blocked on owner rule decisions for contradictory conventions, then implementation/test updates |
| Browser smoke | full mock first-screen/a11y gate passes; monthly operating real-client route-mocked gate passes | full real-backend all-suite smoke still open |
| MCP/GitNexus tool surface | local MOSS MCP stdio works; direct Codex App MCP/GitNexus tools unavailable in this session | blocked on session/tool exposure for direct App-surface evidence; snapshot and fresh-session runbook now attached |
| Secret hygiene | OSV clean; local gitleaks still detects ignored/untracked `config/.env` secrets | blocked on local secret rotation/owner acceptance outside repository commit path |

## Priority Queue

| Priority | Action | Owner / Decision Source | Evidence Already Available | Next Evidence To Capture | Verification / Gate |
| --- | --- | --- | --- | --- | --- |
| P0-gate | Keep all page and metric closure fail-closed until owner approval and governance evidence exist. | System governance | Main audit, owner summary, readiness output all preserve `closure_approved=false` where pending. | None; this is a standing guardrail. | Owner checkers strict mode must continue to fail until real approval is captured. |
| P1-01 | Resolve the 10 remaining calculation/display P1 decisions. | Business owner plus metric governance | `2026-06-10-calculation-logic-audit.md`; `2026-06-10-calculation-p1-owner-decision-matrix.md`; P1-08 is verified by bond-dashboard formatter/page tests. | Owner-selected convention for each remaining P1 row. | Update `docs/calc_rules.md`, contracts, implementation, and tests for the selected convention. |
| P1-02 | Clear Ledger PnL direct page/API governance record gap. | Approved governance workflow | `emit_ledger_pnl_governance_record.py` dry-run returns `ready_for_audit_review`, `existing_record_line=null`; `2026-06-10-ledger-pnl-direct-governance-record-snapshot.json` records no written direct record search matches; runbook defines the authorized closure procedure. | Written or located direct record for `PAGE-LEDGER-PNL-001` and `/api/ledger-pnl/summary`. | Rerun governance validation; keep `formal_use_allowed=false` unless owner closure later changes it. |
| P1-03 | Complete owner-review packets for seven pending pages. | Page business owners | Owner summary lists missing fields and review items for all seven pages; `2026-06-10-owner-approval-fail-closed-snapshot.json` records 7 pending, 0 captured, 0 closure-approved, 84 action items, and strict rejection for 7/7 pages. | Owner name, role, decision, approval date, signature, and page-specific evidence review acknowledgements. | `scripts/check_*_business_owner_approval.py --require-captured` exits 0 only after valid capture. |
| P1-04 | Re-run direct App MCP and GitNexus evidence when tool surface is available. | Engineering/tooling | Local MCP stdio handshakes and contract tests pass; fresh tool discovery at 2026-06-10T13:05:58+08:00 found 0 direct MOSS/GitNexus tools; `2026-06-10-direct-app-mcp-gitnexus-tool-surface-snapshot.json` records local `.codex/config.toml` and `.mcp.json` declarations. | Direct Codex App tool evidence for MOSS MCP and GitNexus impact/call-path checks, using `2026-06-10-direct-app-mcp-gitnexus-tool-surface-runbook.md`. | Record direct-tool result in audit appendix; compare against local stdio evidence; keep local stdio evidence from being promoted to direct App-surface closure. |
| P1-05 | Run full real-backend browser smoke once backend/MCP authority target is ready. | Engineering QA | Mock full smoke: 50 passed, 2 skipped; monthly operating real-client route-mocked smoke: 1 passed; `2026-06-10-real-backend-smoke-runbook.md` defines the closure run. | Live backend target, real frontend data source, output directory, and result capture following the runbook. | `npm.cmd run test:a11y-smoke -- tests/playwright/a11y-visual-smoke.spec.mjs --workers=1` with real backend target and no mixed data-source skips. |
| P1-06 | Resolve local secret scan findings. | Environment owner | OSV reports 0 vulnerabilities; gitleaks detects two ignored/untracked `config/.env` secret names with values redacted; `2026-06-10-local-secret-hygiene-snapshot.json` records ignored/untracked boundary checks and the redacted scan plan. | Confirm rotation or owner acceptance for local secrets; do not commit values. | Clean-runner gitleaks should pass or produce accepted local-only findings outside source boundary. |
| P2-00 | Keep the audit package consistency guard green after audit artifact edits. | Engineering QA | `tests/test_system_audit_manifest_contract.py` checks manifest artifact links, fail-closed flags, owner non-approval boundaries, and coverage/fresh-verification count alignment. | Rerun after manifest, coverage report, owner brief, or capture template changes. | `pytest tests/test_system_audit_manifest_contract.py -q` must pass. |
| P2-01 | Convert remaining calculation/display P1 owner decisions into implementation phases. | Engineering after owner rulings | Decision matrix provides proposed order and closure evidence; P1-08 already has formatter/page regression evidence. | One scoped phase per remaining decision group. | Targeted formatter/model/API tests, then page smoke/debt audit where UI changes occur. |
| P2-02 | Maintain business display coverage at 26 tracked routes. | Frontend QA | `business-display-coverage-report.json` reports 26 tracked routes and 0 route gaps. | Update coverage report whenever browser-smoke scope changes. | `python scripts\business_display_coverage_report.py` plus scaffold tests. |

## Recommended Execution Order

1. Protect gates: keep strict owner checks and page-readiness certification fail-closed.
2. Get business-owner decisions for the 10 remaining calculation/display P1s.
3. Run the approved Ledger PnL governance workflow or explicitly defer it with owner acknowledgement.
4. Capture owner approval packets for the seven pending pages, with Ledger PnL last.
5. Re-run direct App MCP/GitNexus with `2026-06-10-direct-app-mcp-gitnexus-tool-surface-runbook.md`, then run full real-backend smoke when those surfaces are available.
6. Resolve local secret hygiene in the environment, not by committing secret values.

## Non-Approvals

- This register does not certify any route.
- This register does not approve any metric.
- This register does not write any governance record.
- This register does not capture business-owner approval.
- This register does not replace source-backed MCP or GitNexus evidence.
