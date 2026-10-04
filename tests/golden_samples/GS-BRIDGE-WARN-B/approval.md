# GS-BRIDGE-WARN-B Approval

- Sample ID: `GS-BRIDGE-WARN-B`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`

## Capture note

- `response.json` has been captured from a deterministic fixture-backed warning path.
- Approval is still pending.
- 2026-08-11 recapture: bridge decomposition switched to mutually-exclusive explained
  (516 removed from explained; market effects FVTPL-gated) per calc audit PNL-01/PNL-02.
  Explained 11.50→14.75, residual 0→−3.25, summary quality ok→error; the frozen
  invariant `result_meta.quality_flag == summary.quality_flag` under vendor_unavailable
  is unchanged.

## Truth note

- This sample protects current bridge warning and fallback semantics.
- Do not “clean up” warning text or fallback lineage behavior without updating this sample and its tests.

## Metadata-only recapture record — 2026-09-02

- Reason: commit `2ffbd848` (`fix(core-finance): govern fi_cumulative_realized_517 and bump the materialize rv to v4`) moved `rv_pnl_phase2_materialize` v3→v4 but did not re-record `response.json`, so the capture-ready gate was red at HEAD.
- Key changes: `result_meta.rule_version` / `cache_version` v3→v4; Numeric fields now carry the exact-decimal `raw_text` sidecar; `result_meta.data_built_at` is emitted explicitly. Warning-profile amounts and warnings are unchanged.
- Approval boundary: this records the re-capture only; final approver and approval timestamp remain pending.

## Technical recapture — 2026-09-27

The available 2025-10-31 balance is not the required 2025-11-30 baseline; the new mismatch warning and filters preserve frozen amounts. This is a deterministic technical recapture only; business-owner approval and formal-use permissions remain unchanged. Evidence: output/audits/2026-09-27/release-repair/backend/golden-diffs/ and golden-semantic-review/REPORT.md.
