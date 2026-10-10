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

## Metadata-only recapture record — 2026-09-02

- Reason: fixed-income caliber version set moved to `rv_bond_analytics_formal_materialize_v3`.
- Key changes: `result_meta.rule_version` / `cache_version` v2→v3 and `result_meta.data_built_at`; all concentration values unchanged.
- Approval boundary: this records the re-capture only; final approver and approval timestamp remain pending.

## Isolated technical recapture — 2026-09-05, full-worktree acceptance

The existing capture-ready fixture was executed against a fresh temporary database using `rv_bond_analytics_formal_materialize_v4`. Every business field in result is unchanged. Only rule/cache metadata and per-run identifiers or timestamps differ. No production database was read or written.

Before SHA-256: `3bfe5b371811d1c9558aeeba9a9b8cae8b1362562343fc5e0a629393481b2e2f`. Captured response SHA-256: `4a7cecc0f9189f7343d16a4803f9a69dabd815e494e77bcd2959fd83114cc9a7`. The before/after payloads, isolation receipt and semantic diff are retained under `.codex-tmp/full-worktree-acceptance-2026-09-05/golden-recapture/GS-CONCENTRATION-MONITOR-A/`. This is technical recapture evidence only; business-owner approval remains PENDING and no formal-use permission is added.

## Technical recapture — 2026-09-27

Bond materialization lineage v4 to v6; all frozen business values matched the synthetic replay. This is a deterministic technical recapture only; business-owner approval and formal-use permissions remain unchanged. Evidence: output/audits/2026-09-27/release-repair/backend/golden-diffs/ and golden-semantic-review/REPORT.md.
