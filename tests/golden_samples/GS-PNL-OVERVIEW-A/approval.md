# GS-PNL-OVERVIEW-A Approval

- Sample ID: `GS-PNL-OVERVIEW-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`

## Capture note

- `response.json` has been captured from a deterministic fixture-backed run.
- Approval is still pending.

## Truth note

- This sample protects governed formal PnL overview semantics.
- Updating any of the 514/516/517/manual-adjustment/total fields requires contract review.

## Metadata-only recapture record — 2026-09-02

- Reason: commit `2ffbd848` (`fix(core-finance): govern fi_cumulative_realized_517 and bump the materialize rv to v4`) moved `rv_pnl_phase2_materialize` v3→v4 but did not re-record `response.json`, so the capture-ready gate was red at HEAD.
- Key changes: `result_meta.rule_version` / `cache_version` v3→v4; `result_meta` optional fields emitted explicitly; envelope carries `calibration: null`. No overview value changed.
- Approval boundary: this records the re-capture only; final approver and approval timestamp remain pending.

## Technical recapture — 2026-09-27

Internal arithmetic closes at 111.50 while independent-ledger reconciliation remains pending; controlled FI and non-standard rows support CNY disclosure. This is a deterministic technical recapture only; business-owner approval and formal-use permissions remain unchanged. Evidence: output/audits/2026-09-27/release-repair/backend/golden-diffs/ and golden-semantic-review/REPORT.md.
