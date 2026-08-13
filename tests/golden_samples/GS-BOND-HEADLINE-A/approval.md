# GS-BOND-HEADLINE-A Approval

- Sample ID: `GS-BOND-HEADLINE-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Last reviewed: `2026-08-13`

## Capture note

- `response.json` is captured from a deterministic fixture-backed `TestClient` call to `GET /api/bond-dashboard/headline-kpis?report_date=2026-03-31`.
- The capture seeds a prior snapshot on `2026-03-30` and a current snapshot on `2026-03-31` in `fact_formal_bond_analytics_daily`.
- Re-recorded `2026-08-13` because `ResultMeta` had grown `amount_currency_basis`, `amount_currency_basis_note` and `cache_key` since the original capture. The re-capture was diffed against the previous file first: those three governance keys are the only additions, no key was lost, and no business value changed (`trace_id` and `generated_at` are per-run by construction).

## Caveats

- This is a bond-dashboard page-truth sample, not a new formal `MTR-*` approval.
- Empty/null behavior is verified by contract tests and documented in `assertions.md`; `response.json` records the non-empty capture profile.
