# Golden Samples

This directory stores first-batch governed golden-sample packs.

Current rule:

- every checked-in capture-ready sample pack includes:
  - `request.json`
  - `response.json`
  - `assertions.md`
  - `approval.md`
- `response.json` must come from an explicit capture step against a verified
  environment or a deterministic fixture-backed run.
- specialized compact captures may pair aggregate-and-digest real evidence with a
  mandatory aggregate-preserving synthetic production-chain replay; synthetic
  source hashes are identity anchors only, never source-provenance claims.

Reason:

- avoid freezing guessed or partially inferred payloads as business truth
- keep sample packs aligned with `docs/golden_sample_catalog.md`

Current capture-ready sample packs (27 total):

- `GS-BAL-OVERVIEW-A`
- `GS-BAL-WORKBOOK-A`
- `GS-PNL-OVERVIEW-A`
- `GS-PNL-DATA-A`
- `GS-PNL-ATTR-WB-A`
- `GS-BOND-HEADLINE-A`
- `GS-BOND-ANALYSIS-ACTION-ATTR-A`
- `GS-CONCENTRATION-MONITOR-A`
- `GS-STOCK-ANALYSIS-OBS-A`
- `GS-MKT-RATES-FRAGMENT-A`
- `GS-AVERAGE-BALANCE-A`
- `GS-AVERAGE-BALANCE-MONTHLY-A`
- `GS-BRIDGE-A`
- `GS-RISK-A`
- `GS-EXEC-OVERVIEW-A`
- `GS-EXEC-PNL-ATTR-A`
- `GS-EXEC-SUMMARY-A`
- `GS-LEDGER-PNL-SUMMARY-A`
- `GS-LEDGER-PNL-NET-INTEREST-202606-A`
- `GS-BANK-LEDGER-CLASSIFICATION-A`
- `GS-CASHFLOW-PROJECTION-A`
- `GS-PNL-BUSINESS-INSIGHTS-A`
- `GS-POSITIONS-BONDS-LIST-A`
- `GS-POSITIONS-INTERBANK-LIST-A`
- `GS-PROD-CAT-PNL-A`
- `GS-BRIDGE-WARN-B`
- `GS-RISK-WARN-B`

Supporting-only governance sample packs (1 total):

- `GS-PORTFOLIO-HOME-A` - `/portfolio` module-home evidence boundary. This pack is not capture-ready, does not prove page execution, and does not approve page-level formal use.
