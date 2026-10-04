# GS-BAL-OVERVIEW-A Approval

- Sample ID: `GS-BAL-OVERVIEW-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`

## Capture note

- `request.json` is frozen.
- `response.json` has been captured from a deterministic fixture-backed run.
- Approval is still pending.
- 2026-08-14 metadata-only deterministic fixture recapture added explicit report-date,
  filter, source-table, and evidence-row fields; no business metric value changed.
- Approval boundary is unchanged: owner and approver remain pending.

## Truth note

- This is the governed formal balance overview sample for `report_date=2025-12-31`.
- Do not update values without also reviewing:
  - `docs/metric_dictionary.md`
  - `docs/page_contracts.md`
  - `tests/test_balance_analysis_api.py`

## Metadata-only recapture record — 2026-09-02

- Reason: the previous file predated `result_meta.source_surface`, `data_source`, `calibration`, and `result.metric_definitions`, so `BalanceAnalysisOverviewEnvelope` rejected it (`tests/test_api_response_model_field_preservation.py`).
- Key changes: those fields plus explicit optional `result_meta` fields (`data_built_at`, `next_drill`, `cache_key`, …). Every overview amount is unchanged.
- Approval boundary: this records the re-capture only; final approver and approval timestamp remain pending.
