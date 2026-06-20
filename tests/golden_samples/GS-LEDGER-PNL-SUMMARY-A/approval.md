# GS-LEDGER-PNL-SUMMARY-A Approval

- Sample ID: `GS-LEDGER-PNL-SUMMARY-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Last reviewed: `2026-06-06`

## Capture Note

- `response.json` is captured from a deterministic fixture-backed `TestClient` call to `GET /api/ledger-pnl/summary?date=2026-04-30`.
- The fixture feeds `ledger_pnl_service._load_facts_for_date` with canonical ledger rows through the same summary service boundary used by the API route.
- The sample freezes the page-level ledger summary DTO shape and selected `MTR-LPN` candidate display values.

## Caveats

- This is a Ledger PnL page-level summary sample, not formal PnL truth.
- `formal_use_allowed=false` is intentional and must remain false until contracts, metric dictionary approval, governance records, and business-owner approval authorize a different state.
- It does not approve `GS-LEDGER-PNL-FIN-IND-202603-B`; that fixture remains limited to formal financial indicator source-contract evidence.
- Direct page/API governance record review, catalog/date review, manual audit closure, and business-owner approval are still required before page-level closure.
