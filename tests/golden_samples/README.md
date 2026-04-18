# Golden Samples

This directory stores first-batch governed golden-sample packs.

Current rule:

- phase 1 of sample onboarding creates:
  - `request.json`
  - `assertions.md`
  - `approval.md`
- `response.json` is intentionally deferred until an explicit capture step
  against a verified environment or a deterministic fixture-backed run.

Reason:

- avoid freezing guessed or partially inferred payloads as business truth
- keep sample packs aligned with `docs/golden_sample_catalog.md`

Current first-batch sample packs:

- `GS-BAL-OVERVIEW-A`
- `GS-BAL-WORKBOOK-A`
- `GS-PNL-OVERVIEW-A`
- `GS-PNL-DATA-A`
- `GS-BRIDGE-A`
- `GS-RISK-A`
- `GS-EXEC-OVERVIEW-A`
- `GS-EXEC-PNL-ATTR-A`
- `GS-EXEC-SUMMARY-A`
- `GS-BRIDGE-WARN-B`
- `GS-RISK-WARN-B`
