# 2026-06-10 System Audit Completion Checklist

## Purpose

This checklist is the completion audit for the 2026-06-10 MOSS system-wide skills audit. It turns the current open blockers into proof requirements. It does not approve metrics, pages, governance records, route certification, formal use, direct MCP/GitNexus evidence, or business-owner signoff.

Generated at: `2026-06-10T16:00:10+08:00`.

## Current Completion State

| Completion Gate | Current Evidence | Completion Status |
| --- | --- | --- |
| Audit package consistency | `pytest tests/test_system_audit_manifest_contract.py tests/test_system_audit_completion_snapshot_verifier.py -q` -> 19 passed; `python scripts\verify_system_audit_completion_snapshot.py` -> pass with `follow_up_packet_count=5` and `follow_up_brief_blocker_count=5` | evidence guards passing |
| Page/route readiness counts | `python scripts\codex_page_readiness.py --all`; `python scripts\codex_page_readiness.py --route-scope` | counts refreshed, but 0 business-contract-certified routes |
| Business display coverage mapping | `python scripts\business_display_coverage_report.py` | 26 tracked routes, 0 route gaps |
| Full real-backend browser smoke | `docs/audits/2026-06-10-real-backend-smoke-result.md` | browser smoke evidence accepted, not business approval |
| Business-owner approval | `docs/audits/2026-06-10-owner-approval-fail-closed-snapshot.json` | not complete: 7 pending, 0 captured |
| Ledger PnL direct governance record | `docs/audits/2026-06-10-ledger-pnl-direct-governance-record-snapshot.json` | not complete: dry-run candidate only, no written direct record |
| Calculation/display P1 owner decisions | `docs/audits/2026-06-10-calculation-p1-owner-decision-matrix.md` | not complete: 10 open owner-decision rows |
| Direct App MCP/GitNexus evidence | `docs/audits/2026-06-10-direct-app-mcp-gitnexus-tool-surface-snapshot.json` | not complete: 0 direct tools discovered |
| Local secret hygiene | `docs/audits/2026-06-10-local-secret-hygiene-snapshot.json` | not complete: 2 redacted ignored/untracked local findings remain |

## Proof Requirements For Remaining Gates

| Blocker ID | Required Evidence To Prove Completion | Current Contradicting Evidence | Must Stay Fail-Closed Until |
| --- | --- | --- | --- |
| `owner-approval-7-pages` | Owner name, role, decision, approval date, signature, and page-specific evidence-review acknowledgement for all seven pages. Strict owner checkers must exit 0 with captured approvals. | Snapshot refreshed at `2026-06-10T15:17:35+08:00`: 7 pending, 0 captured, 0 closure-approved, 84 action items, strict checks rejected 7/7. | The seven owner approval packets are captured and strict checks pass. |
| `ledger-pnl-direct-governance-record` | Approved governance workflow writes or locates a direct record for `PAGE-LEDGER-PNL-001`, `/api/ledger-pnl/summary`, and `ledger_pnl.summary:2026-05-31:ALL`; downstream readiness and governance validation are rerun. | Snapshot refreshed at `2026-06-10T15:20:42+08:00`: dry-run candidate only, `record_write_status=not_requested`, `existing_record_line=null`, no written record search matches, `governance_record_validation=missing_direct_records`, `audit_review=blocked_by_record_gaps`, `formal_use_allowed=false`. | A written/located direct record exists and validation proves the page can advance without overriding owner approval. |
| `calculation-display-p1-decisions` | Business owner selects the authoritative convention for each remaining P1 row; `docs/calc_rules.md`, contracts, implementation, and tests are updated for the selected conventions. | Matrix refreshed at `2026-06-10T15:07:55+08:00`: 10 rows remain open (`P1-01` through `P1-07`, `P1-09` through `P1-11`); only P1-08 is verified closed. | All 10 owner-decision rows are moved to verified-closed evidence with targeted tests. |
| `direct-app-mcp-gitnexus-evidence` | A fresh Codex App tool surface exposes the expected MOSS MCP and GitNexus tools; direct App evidence is collected and compared against local stdio evidence. | Snapshot refreshed at `2026-06-10T15:56:52+08:00`: `tool_search` returned 0 direct tools. | Direct App MOSS/GitNexus evidence exists or the blocker is explicitly resolved by the tool owner. |
| `local-secret-hygiene` | Environment owner rotates, removes, or accepts the local-only `config/.env` findings outside the repository; clean-runner gitleaks passes or records accepted local-only findings; no secret values enter source control. | Snapshot refreshed at `2026-06-10T15:45:10+08:00`: OSV 0 vulnerabilities, redacted gitleaks 2 ignored/untracked `config/.env` findings, values not captured. | Owner action is recorded without secret values and the redacted scan result no longer contradicts the closure claim. |

## Reverification Commands

Run these after any blocker is changed:

```powershell
pytest tests/test_system_audit_manifest_contract.py tests/test_system_audit_completion_snapshot_verifier.py -q
python scripts\verify_system_audit_completion_snapshot.py
git -C F:\MOSS-V3 diff --check
```

Run these after page readiness or route scope changes:

```powershell
python scripts\codex_page_readiness.py --all
python scripts\codex_page_readiness.py --route-scope
python scripts\business_display_coverage_report.py
```

Run the relevant owner/gap-specific checks:

```powershell
python scripts\check_product_category_pnl_business_owner_approval.py --require-captured
python scripts\check_balance_analysis_business_owner_approval.py --require-captured
python scripts\check_average_balance_business_owner_approval.py --require-captured
python scripts\check_ledger_pnl_business_owner_approval.py --require-captured
python scripts\check_pnl_attribution_business_owner_approval.py --require-captured
python scripts\check_bond_analysis_business_owner_approval.py --require-captured
python scripts\check_stock_analysis_business_owner_approval.py --require-captured
```

For Ledger PnL, use `docs/audits/2026-06-10-ledger-pnl-direct-governance-record-runbook.md`; do not run `python scripts\emit_ledger_pnl_governance_record.py --write` unless governance-owner authorization is explicit.

For local secrets, use `docs/audits/2026-06-10-local-secret-hygiene-runbook.md`; do not copy credential values into docs, tests, logs, commits, screenshots, or chat.

## Non-Approval Boundary

This checklist is evidence routing only. It does not complete the audit goal by itself, does not close any blocker, and must not be cited as business approval. Completion requires the required evidence above to exist in the current worktree and the verification commands to pass after the evidence is captured.
