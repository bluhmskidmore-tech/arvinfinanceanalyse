# Portfolio Home KRD Contract Decision Summary

This summary is not an approval.

- Page: `portfolio` (`PAGE-PORTFOLIO-HOME-001`)
- Report date: `2026-05-31`
- Export status: `decision_required`
- Required fields: `risk_owner_decision`, `decision_notes`
- Allowed decisions: `approve_nearest_bucket`, `require_exact_bucket_schema`, `reject`
- Strict gate: `python scripts/portfolio_home_krd_remap_review_queue.py --require-clean`
- Remap tenor count: `3`
- Mapped tenor count: `3`
- Unsupported tenor count: `0`
- Non-zero DV01 rows: `500`
- DV01 sum: `33365026.29780176`
- Decision queue: `krd_remap_summary.csv`, `krd_remap_detail.csv`
- Generated owner fields must be blank: `true`
- Boundary: generated CSV fields are blank and do not approve nearest-bucket mapping.

## Owner Instructions

- Fill `risk_owner_decision` on every summary and detail row.
- Fill `decision_notes` on every summary and detail row for every decision value; include the contract rationale or rejection reason.
- Do not edit `manifest.json`; rerun the export after owner decisions are captured.

## Post-Decision Verification

- `python scripts/portfolio_home_krd_remap_review_queue.py --require-clean`
- `python scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent`
- `python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready`
- `python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score`

A filled CSV is still not approval until the business-owner approval template is completed and the strict scorecard gate passes.
