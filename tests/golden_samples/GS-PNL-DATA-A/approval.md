# GS-PNL-DATA-A Approval

- Sample ID: `GS-PNL-DATA-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`

## Capture note

- One deterministic `formal_fi_rows + nonstd_bridge_rows` payload has been captured.
- Approval should still avoid over-interpreting incidental ordering beyond current contracts.

## Truth note

- This sample exists to support overview-to-data reconciliation.

## Metadata-only recapture record — 2026-09-02

- Reason: commit `2ffbd848` (`fix(core-finance): govern fi_cumulative_realized_517 and bump the materialize rv to v4`) moved `rv_pnl_phase2_materialize` v3→v4 but did not re-record `response.json`, so the capture-ready gate was red at HEAD.
- Key changes: `result_meta.rule_version` / `cache_version` v3→v4 and the row-level `rule_version` on `formal_fi_rows[0]` / `nonstd_bridge_rows[0]`; `result_meta` now emits its optional fields explicitly (`as_of_date`, `requested_report_date`, `resolved_report_date`, `filters_applied`, `tables_used`, `next_drill`, `data_built_at`, …) and the envelope carries `calibration: null`. No PnL row value changed.
- Approval boundary: this records the re-capture only; final approver and approval timestamp remain pending.

## Technical recapture — 2026-09-27

Formal PnL materialization lineage v4 to v7; existing FI and non-standard amounts matched the synthetic replay. This is a deterministic technical recapture only; business-owner approval and formal-use permissions remain unchanged. Evidence: output/audits/2026-09-27/release-repair/backend/golden-diffs/ and golden-semantic-review/REPORT.md.
