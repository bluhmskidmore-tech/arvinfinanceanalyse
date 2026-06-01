# Golden Samples

This directory stores first-batch governed golden-sample packs.

Current rule:

- every checked-in capture-ready sample pack includes:
  - `request.json`
  - `response.json`
  - `assertions.md`
  - `approval.md`
- `response.json` must come from an explicit capture step against a verified
  environment or a deterministic fixture-backed run.

Reason:

- avoid freezing guessed or partially inferred payloads as business truth
- keep sample packs aligned with `docs/golden_sample_catalog.md`

Current capture-ready sample packs (13 total):

- `GS-BAL-OVERVIEW-A`
- `GS-BAL-WORKBOOK-A`
- `GS-PNL-OVERVIEW-A`
- `GS-PNL-DATA-A`
- `GS-BOND-HEADLINE-A`
- `GS-BRIDGE-A`
- `GS-RISK-A`
- `GS-EXEC-OVERVIEW-A`
- `GS-EXEC-PNL-ATTR-A`
- `GS-EXEC-SUMMARY-A`
- `GS-PROD-CAT-PNL-A`
- `GS-BRIDGE-WARN-B`
- `GS-RISK-WARN-B`
