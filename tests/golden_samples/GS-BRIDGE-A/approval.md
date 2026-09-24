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
