# 2026-06-10 Ledger PnL Direct Governance Record Runbook

## Purpose

This runbook defines the approved path to close the Ledger PnL direct page/API governance-record gap. It is deliberately fail-closed: the current audit evidence has a field-complete dry-run candidate, but no written direct record in `data/governance/cache_manifest.jsonl`.

## Current Evidence

- Page: `ledger-pnl`
- Page ID: `PAGE-LEDGER-PNL-001`
- Route: `/ledger-pnl`
- Primary API: `/api/ledger-pnl/summary`
- Candidate cache key: `ledger_pnl.summary:2026-05-31:ALL`
- Dry-run command: `python scripts\emit_ledger_pnl_governance_record.py`
- Dry-run result: `record_write_status=not_requested`, `existing_record_line=null`, `validation_status=ready_for_audit_review`
- Written-record search result: no match for `PAGE-LEDGER-PNL-001`, `/api/ledger-pnl/summary`, or `ledger_pnl.summary:2026-05-31:ALL`
- Page readiness: `overall_status=static-pass`, `formal_use_allowed=false`, `business_owner_approval_captured=false`, `closure_approved=false`
- Last read-only refresh: `2026-06-10T15:20:42+08:00`; dry-run only, no `--write` command was run.

Machine-readable snapshot: `docs/audits/2026-06-10-ledger-pnl-direct-governance-record-snapshot.json`.

## Non-Closure Boundary

The current dry-run evidence does not:

- write a governance record
- approve Ledger PnL metrics or page closure
- certify `/ledger-pnl`
- prove live page/API execution
- replace data-catalog/date review
- capture business-owner approval

## Closure Procedure

1. Confirm governance-owner authorization to write or locate the direct record.
2. Rerun the dry-run:
   `python scripts\emit_ledger_pnl_governance_record.py`
3. Confirm the candidate still has:
   `existing_record_line=null` or a known existing matching line, `validation_status=ready_for_audit_review`, and `formal_use_allowed=false`.
4. If authorized to write the candidate record, run:
   `python scripts\emit_ledger_pnl_governance_record.py --write`
5. Search `data/governance/cache_manifest.jsonl` for:
   `PAGE-LEDGER-PNL-001`, `/api/ledger-pnl/summary`, and `ledger_pnl.summary:2026-05-31:ALL`.
6. Rerun:
   `python scripts\codex_page_readiness.py --page-slug ledger-pnl`
7. Rerun the Ledger PnL owner approval checks:
   `python scripts\check_ledger_pnl_business_owner_approval.py`
   `python scripts\check_ledger_pnl_business_owner_approval.py --require-captured`
8. Rerun the page-specific verification plan from:
   `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-verify-page.ps1 -PageSlug ledger-pnl -DryRun`
9. Capture live page/API evidence and owner review acknowledgements before any owner approval packet is signed.

## Acceptance Criteria

- A direct page/API record is written or located in `data/governance/cache_manifest.jsonl`.
- Governance validation no longer reports Ledger PnL as blocked only by direct page/API record fields.
- Page readiness still preserves `formal_use_allowed=false` until owner approval and page-specific review gates are captured.
- Strict owner approval mode remains failing until owner name, role, approval decision, approval date, signature, and page-specific evidence reviews are present.
- The result is recorded back into the system audit manifest and action register.

## Evidence That Still Does Not Close The Page

- Dry-run output without `--write`
- Static-pass page readiness alone
- Mock browser smoke
- Route-mocked real-client smoke
- A field-complete candidate record with no written direct record
- Owner meeting notes that have not been copied into the authoritative Ledger PnL approval template and validated by strict checks
