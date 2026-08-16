# GS-CONCENTRATION-MONITOR-A Approval

- Sample ID: `GS-CONCENTRATION-MONITOR-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`
- Last reviewed: `2026-08-13`

## Capture Note

- `response.json` is captured from a deterministic fixture-backed service call for `GET /api/bond-analytics/credit-spread-migration?report_date=2026-03-31&spread_scenarios=10,25`.
- The fixture provides two credit bond rows and one non-credit portfolio row to freeze concentration ratios and candidate metadata.
- The sample freezes the `/concentration-monitor` candidate concentration DTO boundary only.
- Re-recorded `2026-08-13` because `e8fbafa6` (`fix(convexity): replace the zero-coupon approximation with cash-flow convexity`) moved the bond-analytics materialization rule version to `rv_bond_analytics_formal_materialize_v2`. The re-capture was diffed against the previous file first: besides `rule_version`/`cache_version` v1→v2, the payload had grown `result.display_limits` (backend-issued display limits per `b70585a32`) and the `amount_currency_basis_note` wording moved to the CNY-closure fail-closed text per `874b20c8a`. These are additions/wording only: no key was lost and every frozen concentration, spread-scenario, and OCI value is bit-identical; no value change originates from the convexity calculation itself (this fixture stubs analytics rows, so no engine convexity flows into this DTO).

## Caveats

- This is route-scoped candidate evidence, not a page closure approval.
- It does not approve MTR-CON metrics, formal risk truth, fixed-income metric truth, concentration-limit decisions, manual audit closure, or business-owner approval.
- `formal_use_allowed=false` must remain visible until the dedicated page contract, golden approval, governance evidence, manual audit, and owner approval are all closed.
