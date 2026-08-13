# GS-POSITIONS-INTERBANK-LIST-A Approval

- Sample ID: `GS-POSITIONS-INTERBANK-LIST-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`
- Last reviewed: `2026-08-13`

## Capture Note

- `response.json` is captured from a deterministic fixture-backed `TestClient` call to `GET /api/positions/interbank?report_date=2026-01-10&page=1&page_size=20`.
- The fixture is the canonical positions contract seed (`tests/test_positions_api_contract.py::_seed_positions_db`): one interbank asset row on `2026-01-10`; the liability row sits on `2026-01-12` and freezes the single-report-date slice semantics by exclusion.
- The sample freezes the `/positions` interbank candidate list DTO boundary and the `MTR-POS-002` record-count anchor (`result.total == evidence_rows == 1`) only.

## Caveats

- This is route-scoped candidate evidence, not a page closure approval.
- It does not approve `MTR-POS-002`, close `GAP-POS-LIST`, or promote positions list totals into formal balance, liability, PnL, or risk truth.
- `formal_use_allowed=false` must remain visible until the page contract, golden approval, governance evidence, manual audit, and business-owner approval are all closed.
