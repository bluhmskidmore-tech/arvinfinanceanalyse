# GS-LEDGER-PNL-NET-INTEREST-202606-A Approval

- Sample ID: `GS-LEDGER-PNL-NET-INTEREST-202606-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Last reviewed: `2026-07-13`

## Capture note

The compact response freezes the three source locks, net-interest bridge, four component totals, leading 11-digit account-code/contribution/current-locator anchors, the interbank offset boundary and a SHA-256 fingerprint of each full returned account-row set. It does not retain complete real account rows, real account names or real three-period balances. Clean CI must run the production comparison and component-detail calculation chain with a committed aggregate-preserving synthetic fixture; local governed workbooks provide an additional optional replay of the real compact snapshot.

## Caveats

- This sample is technical regression evidence only; it is not owner-approved or formal financial truth.
- Source hashes embedded in the synthetic fixture are governed identity anchors only and do not claim that synthetic rows came from those workbooks.
- The 202605 `微贷` sheet remains missing, so full 186-item replay remains unavailable.
- `formal_use_allowed=false` and `certification_effect=none` must remain unchanged until separate governance and owner approval are recorded.
