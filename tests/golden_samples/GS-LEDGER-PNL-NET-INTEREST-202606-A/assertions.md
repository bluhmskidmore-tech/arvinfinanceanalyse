# GS-LEDGER-PNL-NET-INTEREST-202606-A Assertions

## Source and scope

- The parent source is the 202606 ledger-only period comparison under `qdb-finance-2026-v1.0.1`.
- The three exact main-ledger files for 202604, 202605 and 202606 must all be `locked_match`.
- The scope is limited to `综本`, CNX, ending balances, the net-interest bridge and its four component-detail reads.
- The missing 202605 `微贷` sheet remains outside this ledger-only sample and keeps the complete 186-item replay unavailable.

## Frozen bridge values

- Net-interest change is `-2.5631215418` 亿元.
- The four signed contributions are `-0.3473924741`, `0.0830909629`, `-1.7260319538` and `-0.5727880768` 亿元.
- Their unrounded Decimal sum equals the parent net-interest change and every reconciliation delta is zero.
- Bridge and detail quality is `standard_candidate`; every foot is `passed`.

## Frozen 11-digit account evidence

- Contributing account counts are `21 / 14 / 18 / 19` in the fixed component order.
- `rows_sha256` fingerprints each complete returned row set, including 11-digit account identity, weights, Decimal values and three-period source locators, without duplicating the full sensitive row payload in this sample.
- The largest investment drag is `51402010003 = -1.3160266974` 亿元 at `综本!G1041` for 202606.
- The interbank row `50206000001` remains `excluded_offset` with component and net weights both zero.

## Replay gate

- Clean CI must execute the production parent comparison and all four component-detail calculations with the committed `synthetic_aggregate_preserving` fixture; this mandatory test is not allowed to carry `skip` or `skipif`.
- The fixture retains no real account names or real three-period row balances. It reuses only the compact account-code, contribution and current-locator anchors already frozen above; remaining accounts and balances are synthetic. Its governed source hashes are identity anchors for the source-lock branch, not evidence that the synthetic rows were extracted from those workbooks.
- The fixture byte SHA-256 and its four synthetic row-set fingerprints are frozen. The compact real capture continues to freeze aggregate values, source locators and real row-set fingerprints without retaining the real account-level payload.
- Governed local workbooks provide an additional optional end-to-end replay; their absence must not turn the clean-CI production calculation gate into a skipped test.

## Governance boundary

- This is a capture-ready replay sample with status `captured-awaiting-approval`.
- `metric_status=candidate`, `formal_use_allowed=false`, `driver_status=unclear` and `certification_effect=none` are invariant.
- A matched capture does not mean owner approval, formal PnL truth, causal attribution or certification.
