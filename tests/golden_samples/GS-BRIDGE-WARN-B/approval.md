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
