# GS-POSITIONS-BONDS-LIST-A Approval

- Sample ID: `GS-POSITIONS-BONDS-LIST-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`
- Last reviewed: `2026-08-13`

## Capture Note

- `response.json` is captured from a deterministic fixture-backed `TestClient` call to `GET /api/positions/bonds?report_date=2026-01-10&page=1&page_size=20`.
- The fixture is the canonical positions contract seed (`tests/test_positions_api_contract.py::_seed_positions_db`): three bond rows on `2026-01-10`, one of which is issuance-like and excluded by the default `include_issued=false`.
- The sample freezes the `/positions` bonds candidate list DTO boundary and the `MTR-POS-001` record-count anchor (`result.total == evidence_rows == 2`) only.

## Caveats

- This is route-scoped candidate evidence, not a page closure approval.
- It does not approve `MTR-POS-001`, close `GAP-POS-LIST`, or promote positions list totals into formal balance, PnL, bond-dashboard headline, or risk truth.
- `formal_use_allowed=false` must remain visible until the page contract, golden approval, governance evidence, manual audit, and business-owner approval are all closed.
