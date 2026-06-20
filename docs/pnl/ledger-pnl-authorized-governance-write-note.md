# Ledger PnL Authorized Governance Write Note

This note records the current authorization boundary for `/ledger-pnl`.

## Current State

- Page ID: `PAGE-LEDGER-PNL-001`
- Page slug: `ledger-pnl`
- Primary API: `/api/ledger-pnl/summary`
- Current business-contract status: `evidence-pending`
- Current governance dry-run status: `ready_for_audit_review`
- Current governance record write status: `not_requested`
- Current written direct record evidence from the dry-run command: none
- Current business-owner approval status: `business_owner_approval_captured=false`

## Safe Command

This command is allowed as evidence collection:

```powershell
python scripts/emit_ledger_pnl_governance_record.py
```

It performs a dry-run candidate preflight. It does not write governance records, approve closure, promote candidate metrics, prove live page/API execution, or capture business-owner approval.

## Restricted Command

This command must be treated as workflow-authorized only:

```powershell
python scripts/emit_ledger_pnl_governance_record.py --write
```

Do not run it as a routine verification command. It may append or locate governance-stream records and should only be used after the responsible governance workflow has authorized the write.

## Approval Boundary

Even an authorized governance write would not by itself certify the page. `/ledger-pnl` still requires:

- manual governance-record review
- dedicated ledger summary golden sample review
- UI/API payload review
- live smoke evidence review
- verification rerun
- candidate-boundary acceptance
- completed business-owner approval template

The approval checker remains the final local gate:

```powershell
python scripts/check_ledger_pnl_business_owner_approval.py --require-captured
```
