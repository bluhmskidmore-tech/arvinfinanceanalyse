# GS-BOND-ANALYSIS-ACTION-ATTR-A Approval

- Sample ID: `GS-BOND-ANALYSIS-ACTION-ATTR-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`
- Last reviewed: `2026-08-14`

## Capture Note

- `response.json` is captured from a deterministic fixture-backed service call for `GET /api/bond-analytics/action-attribution?report_date=2026-03-31&period_type=MoM`.
- The fixture seeds one prior and one current bond snapshot plus matching 517 capital-gain allocation.
- The sample freezes the `/bond-analysis` action-attribution DTO boundary only.
- Re-captured `2026-08-14` to replace uncomputed DV01 pseudo-zeroes with `null`, mark DV01 and independent accounting-PnL reconciliation as blocked, and disclose that accounting PnL is currently copied from economic PnL. Status remains `captured-awaiting-approval`; no metric or page approval is asserted.
- Re-recorded `2026-08-13` because `e8fbafa6` (`fix(convexity): replace the zero-coupon approximation with cash-flow convexity`) moved the bond-analytics materialization rule version to `rv_bond_analytics_formal_materialize_v2`. The re-capture was diffed against the previous file first: besides `rule_version`/`cache_version` v1→v2, the payload had grown keys since the original `2026-06-06` capture — the full `ResultMeta` envelope (`trace_id`, `amount_currency_basis`/`_note` per `874b20c8a`, `cache_key`, date/filters/tables/evidence keys) and result-side `by_action_type`, `action_details`, `computed_at`, `warnings_detail` (payload shaping per `f80e2ce6f`/`b7afc047c`/`382677cbd`). These are additions only: no key was lost and every previously frozen value (`MTR-BOND-ACT-001`~`006`, components, warnings) is bit-identical; no value change originates from the convexity calculation itself.

## Caveats

- This is route-scoped candidate evidence, not a page closure approval.
- It does not approve fixed-income formulas, direct governance records, manual audit closure, business-owner approval, or formal-use promotion.
- `formal_use_allowed=false` must remain visible until the direct page contract, golden approval, governance evidence, manual audit, and owner approval are all closed.
