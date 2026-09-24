# GS-BANK-LEDGER-CLASSIFICATION-A Approval

- Sample ID: `GS-BANK-LEDGER-CLASSIFICATION-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approval date: `TBD`
- Last reviewed: `2026-07-12`

## Capture note

- `response.json` is captured from a deterministic fixture-backed `TestClient` request to `GET /api/ledger/dashboard?as_of_date=2026-03-17`.
- The fixture imports all five asset allowlist pairs, the liability pair, and three fail-closed cases through the production Ledger import path.
- The sample freezes DTO, unit, date, null/zero, coverage, source-version, and rule-version behavior.

## Non-approval boundary

- This artifact is not business-owner approval.
- `formal_use_allowed=false` remains mandatory.
- A non-placeholder owner, approver, approval date, signed classification decision, and authorized real-page UAT are required before any approval claim.
