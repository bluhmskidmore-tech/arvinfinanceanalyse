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
- Re-recorded again `2026-08-13` because `e8fbafa6` (`fix(convexity): replace the zero-coupon approximation with cash-flow convexity`) moved the bond-analytics materialization rule version to `rv_bond_analytics_formal_materialize_v2`. The re-capture was diffed against the previous file first: `rule_version`/`cache_version` v1→v2 are the only changes; every KPI value is bit-identical (this fixture seeds `fact_formal_bond_analytics_daily` rows directly, so no engine-computed convexity flows into the headline KPIs).
- Re-recorded `2026-08-14` after headline metadata aligned `quality_flag` with evidence health: this three-row fixture now emits `ok`; analytical/candidate status remains frozen independently through `basis="analytical"` and `formal_use_allowed=false`. No KPI, date, unit, precision, lineage version, or fallback value changed.

## Caveats

- This is a bond-dashboard page-truth sample, not a new formal `MTR-*` approval.
- Empty/null behavior is verified by contract tests and documented in `assertions.md`; `response.json` records the non-empty capture profile.
