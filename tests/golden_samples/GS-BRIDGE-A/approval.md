# GS-BRIDGE-A Approval

- Sample ID: `GS-BRIDGE-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`

## Capture note

- `response.json` has been captured from the current deterministic fixture-backed bridge API run.
- Preserve the current warning-profile semantics during approval; do not rewrite it into a fake green sample.
- 2026-08-11 recapture: bridge decomposition switched to mutually-exclusive explained
  (516 removed from explained; market effects FVTPL-gated) per calc audit PNL-01/PNL-02.
  Explained 11.50→14.75, residual 0→−3.25, quality ok→error under the same fixture.

## Truth note

- This sample protects the current governed bridge behavior, not an idealized future bridge.

## Metadata-only recapture record — 2026-09-02

- Reason: commit `2ffbd848` (`fix(core-finance): govern fi_cumulative_realized_517 and bump the materialize rv to v4`) moved `rv_pnl_phase2_materialize` v3→v4 but did not re-record `response.json`, so the capture-ready gate was red at HEAD.
- Key changes: `result_meta.rule_version` / `cache_version` v3→v4; Numeric fields now carry the exact-decimal `raw_text` sidecar; `result_meta.data_built_at` is emitted explicitly. No bridge amount changed (diffed field-by-field against the previous file before replacement).
- Approval boundary: this records the re-capture only; final approver and approval timestamp remain pending.

## Technical recapture — 2026-09-27

The monthly PnL window now discloses missing exact beginning balance and a mismatch warning; frozen bridge amounts did not change. This is a deterministic technical recapture only; business-owner approval and formal-use permissions remain unchanged. Evidence: output/audits/2026-09-27/release-repair/backend/golden-diffs/ and golden-semantic-review/REPORT.md.

## Cache metadata synchronization — 2026-10-05

The deterministic bridge API now reports `cv_pnl_bridge_formal_monthly_v6` and the yield-curve lineage suffix `cv_source_nodes_v2`. Only `result_meta.cache_version` is synchronized with the current service contract. All financial values, warning text, quality flags, and approval fields remain unchanged. The capture-ready test in `tests/test_golden_samples_capture_ready.py` verifies the current fixture response; this record does not grant business-owner approval.
