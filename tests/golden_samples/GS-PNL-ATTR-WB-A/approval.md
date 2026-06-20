# GS-PNL-ATTR-WB-A Approval

- Sample ID: `GS-PNL-ATTR-WB-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Last reviewed: `2026-06-05`

## Capture Note

- `response.json` is captured from a deterministic fixture-backed `TestClient` call to `GET /api/pnl-attribution/volume-rate?report_date=2026-04-30&compare_type=mom`.
- The fixture seeds current and previous product/business rows through the same service boundary used by `volume_rate_attribution_envelope`.
- The sample freezes the workbench primary API DTO shape and selected MTR-PAT volume/rate values.

## Caveats

- This is a PnL Attribution Workbench primary-API sample, not a full-page approval.
- Advanced attribution, Campisi, TPL-market, and composition surfaces still rely on their route/service tests until separate samples are approved.
- Direct page/API governance record review and catalog/date review are still required before page-level closure.
