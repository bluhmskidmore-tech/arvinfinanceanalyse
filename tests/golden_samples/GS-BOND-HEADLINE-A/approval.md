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

## Metadata-only recapture record — 2026-09-02

- Reason: fixed-income caliber version set moved to `rv_bond_analytics_formal_materialize_v3`; Numeric fields now carry the exact-decimal `raw_text` sidecar (`preserve_decimal` exact-numeric work).
- Key changes: `result_meta.rule_version` / `cache_version` v2→v3, `raw_text` added on every Numeric KPI, `result_meta.data_built_at`. Every `raw` / `display` value is unchanged.
- Approval boundary: this records the re-capture only; final approver and approval timestamp remain pending.

## Isolated technical recapture — 2026-09-05, full-worktree acceptance

The existing capture-ready fixture was executed against a fresh temporary database using `rv_bond_analytics_formal_materialize_v4`. Every business field in result is unchanged. Only rule/cache metadata and per-run identifiers or timestamps differ. No production database was read or written.

Before SHA-256: `3d87d5eb989eabb687223881cbec8b814530f65d273e60d2eee5a1be2235607a`. Captured response SHA-256: `1f13b6a0b4e452b567ca89be4ccbf335f162d5afa8d63ebf4eb435d71b832ea8`. The before/after payloads, isolation receipt and semantic diff are retained under `.codex-tmp/full-worktree-acceptance-2026-09-05/golden-recapture/GS-BOND-HEADLINE-A/`. This is technical recapture evidence only; business-owner approval remains PENDING and no formal-use permission is added.

## Technical recapture — 2026-09-27

Weighted-YTM coverage is 400/400 and 300/300 for eligible rate/credit holdings; Other holdings remain outside this denominator and prior KPI values did not change. This is a deterministic technical recapture only; business-owner approval and formal-use permissions remain unchanged. Evidence: output/audits/2026-09-27/release-repair/backend/golden-diffs/ and golden-semantic-review/REPORT.md.
