# GS-BAL-WORKBOOK-A Approval

- Sample ID: `GS-BAL-WORKBOOK-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `arvin`
- Approver: `TBD`
- Approved at: `TBD`

## Capture note

- Workbook payload has been captured.
- Before approval, confirm section inventory against:
  - `GOVERNED_WORKBOOK_SUPPORTED_TABLE_KEYS`
  - `NOT_GOVERNED_OR_NOT_SUPPORTED_KEYS`

## Truth note

- This sample protects governed workbook structure and right-rail governance sections.
- Do not treat it as proof that every workbook table is numerically frozen.

## Recapture record — 2026-07-20

- Owner authorization: `arvin` authorized this recapture in-session.
- Reason: balance H-2 `currency_basis` remediation from the calculation-audit
  sequence (`fa074e13f` / `f9697fe4b`; direct service fetch wiring in
  `d440c11a3`) now uses CNY-projected facts for CNY workbook requests.
- Key changes: bond assets `0.01000000 → 0.07200000`, interbank liabilities
  `0.00100000 → 0.00720000`, and net position
  `0.00900000 → 0.06480000`; dependent table and operational-section values
  were recaptured consistently.
- Approval boundary: this records owner authorization to recapture; final
  approver and approval timestamp remain pending.
