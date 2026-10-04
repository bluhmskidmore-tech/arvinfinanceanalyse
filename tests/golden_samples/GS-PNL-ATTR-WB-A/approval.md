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

## Recapture record — 2026-09-02

- Reason: `core_finance/pnl_attribution/workbench.py` moved its internal arithmetic from float to `Decimal`, removing binary-float accumulation artifacts from the volume/rate decomposition.
- Key changes: `total_rate_effect` / `items[0].rate_effect` `15.999999999999993 → 16`, `total_interaction_effect` / `items[0].interaction_effect` `3.9999999999999982 → 4`, `items[0].attrib_sum` `39.99999999999999 → 40`, `items[0].rate_contribution_pct` `0.3999999999999998 → 0.4`, `total_recon_error` / `items[0].recon_error` `7.105427357601002e-15 → 0`. These are the exact values of the same fixture (`(Qc − Qp)·yp`, `(yc − yp)·Qp`, cross term); no caliber changed. `result_meta` optional fields emitted explicitly.
- Approval boundary: this records the re-capture only; final approver and approval timestamp remain pending.

## Technical recapture — 2026-09-27

The reviewed interest basis gives yields 10% and 8.75%, volume/rate/interaction 17.5/10/2.5, and direct 516/517 effects 7/3; the 40 total closes with zero residual. This is a deterministic technical recapture only; business-owner approval and formal-use permissions remain unchanged. Evidence: output/audits/2026-09-27/release-repair/backend/golden-diffs/ and golden-semantic-review/REPORT.md.
