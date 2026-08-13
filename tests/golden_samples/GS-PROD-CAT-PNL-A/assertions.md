# GS-PROD-CAT-PNL-A Assertions

## Source

- `tests/test_product_category_pnl_flow.py`
- `tests/test_product_category_mapping_contract.py`
- `docs/pnl/product-category-page-truth-contract.md`
- `docs/pnl/adr-product-category-truth-chain.md`

## Required assertions

- HTTP status is `200`.
- `result_meta.basis == "formal"`.
- `result_meta.result_kind == "product_category_pnl.detail"`.
- `result_meta.rule_version == "rv_product_category_pnl_v1"`.
- `result_meta.cache_version == "cv_product_category_pnl_v1"`.
- `result_meta.quality_flag == "ok"`.
- `result_meta.fallback_mode == "none"`.
- `result.report_date == "2026-02-28"`.
- `result.view == "monthly"`.
- `result.asset_total.baseline_ftp_rate_pct == "1.60"` for the 2026 report-year FTP policy.
- `available_views` exactly match `monthly/qtd/ytd/year_to_report_month_end`.
- `bond_investment` row remains the parent of:
  - `bond_tpl`
  - `bond_ac`
  - `bond_ac_other`
  - `bond_fvoci`
  - `bond_valuation_spread`
- `asset_total.business_net_income + liability_total.business_net_income == grand_total.business_net_income`.

## Approved metric bindings

The approved sample-to-metric bindings include the three headline totals:

- `MTR-PCP-001`: `result.asset_total.business_net_income`.
- `MTR-PCP-002`: `result.liability_total.business_net_income`.
- `MTR-PCP-003`: `result.grand_total.business_net_income`.

Decision 3C activates these row-level detail metric bindings for `result.rows[]`; the row identity dimensions (`category_id`, `side`, `view`, `report_date`) remain dimensions, not separate metrics:

- `MTR-PCP-004`: `result.rows[].cnx_scale`.
- `MTR-PCP-005`: `result.rows[].cny_scale`.
- `MTR-PCP-006`: `result.rows[].foreign_scale`.
- `MTR-PCP-007`: `result.rows[].cny_ftp`.
- `MTR-PCP-008`: `result.rows[].foreign_ftp`.
- `MTR-PCP-009`: `result.rows[].cny_net`.
- `MTR-PCP-010`: `result.rows[].foreign_net`.
- `MTR-PCP-011`: `result.rows[].business_net_income`.
- `MTR-PCP-012`: `result.rows[].weighted_yield`.

The 2026-08-13 interest-spread promotion activates these payload-section metric bindings. They are section-level metrics on `result.interest_earning_spread`, `result.interest_spread`, and `result.liability_cost_decomposition`, not `result.rows[]` detail fields:

- `MTR-PCP-013`: `result.interest_earning_spread.all_currency_asset_yield_pct`.
- `MTR-PCP-014`: `result.interest_earning_spread.all_currency_liability_yield_pct`.
- `MTR-PCP-015`: `result.interest_earning_spread.all_currency_spread_pct`.
- `MTR-PCP-016`: `result.interest_earning_spread.cny_asset_yield_pct`.
- `MTR-PCP-017`: `result.interest_earning_spread.cny_liability_yield_pct`.
- `MTR-PCP-018`: `result.interest_earning_spread.cny_spread_pct`.
- `MTR-PCP-019`: `result.interest_spread.all_currency_asset_yield_pct`.
- `MTR-PCP-020`: `result.interest_spread.all_currency_liability_yield_pct`.
- `MTR-PCP-021`: `result.interest_spread.all_currency_spread_pct`.
- `MTR-PCP-022`: `result.interest_spread.cny_asset_yield_pct`.
- `MTR-PCP-023`: `result.interest_spread.cny_liability_yield_pct`.
- `MTR-PCP-024`: `result.interest_spread.cny_spread_pct`.
- `MTR-PCP-025`: `result.liability_cost_decomposition.liability_yield_pct`.
- `MTR-PCP-026`: `result.liability_cost_decomposition.liability_yield_ex_cln_pct`.
- `MTR-PCP-027`: `result.liability_cost_decomposition.cln_yield_pct`.
- `MTR-PCP-028`: `result.liability_cost_decomposition.cln_drag_bp`.
- `MTR-PCP-029`: `result.liability_cost_decomposition.cln_scale`.

Scenario outputs remain analytical scenario payloads unless a future decision explicitly promotes them.

## Interest-spread and CLN drag assertions

Structural assertions frozen by this sample and replayed by `tests/test_golden_samples_capture_ready.py::_validate_product_category`:

- `result.interest_earning_spread`, `result.interest_spread`, and `result.liability_cost_decomposition` are always present on the payload and match the recorded response exactly.
- Both spread sections carry exactly `all_currency_asset_yield_pct`, `all_currency_liability_yield_pct`, `all_currency_spread_pct`, `cny_asset_yield_pct`, `cny_liability_yield_pct`, and `cny_spread_pct`.
- Every populated percent field is a `{raw, display, unit}` value with `unit == "percent"` and a two-decimal `display` suffixed by `%`.
- `all_currency_spread_pct == all_currency_asset_yield_pct - all_currency_liability_yield_pct` within display precision, and likewise for the `cny_*` triple.
- `result.interest_earning_spread.all_currency_liability_yield_pct` and `result.interest_spread.all_currency_liability_yield_pct` are same-source mirrors of `result.liability_total.weighted_yield` and must stay numerically identical.
- The two spread sections use different asset-side sources: `interest_earning_spread` reads the `interest_earning_assets` row (no TPL, no derivatives, no intermediate-business income) and `interest_spread` reads `result.asset_total` (includes them). They must never be presented under the same series name.
- A missing denominator or a missing `credit_linked_notes` row yields `null`, never `0`.
- Scenario payloads do not change these sections; only FTP and net fields move.

`result.liability_cost_decomposition` (`MTR-PCP-025`~`MTR-PCP-029`) landed on 2026-08-13, so
`pending_backend_landing` in `docs/metric_dictionary.md` section 12.3.2 is now empty, the section is
recorded in `response.json`, and `_validate_product_category` compares it. The section satisfies:

- exactly `liability_yield_pct`, `liability_yield_ex_cln_pct`, `cln_yield_pct`, `cln_drag_bp`, `cln_scale`;
- `cln_drag_bp` uses `unit == "bp"` with a one-decimal `display` suffixed by ` bp` (lowercase, space-separated), the only non-percent `ProductCategoryMetricValue` on this payload; `raw` keeps 8 decimals;
- `cln_scale` is a bare decimal amount in yuan, not a `{raw, display, unit}` value;
- `liability_yield_pct` mirrors `result.liability_total.weighted_yield`;
- all five fields are `null` together when the `credit_linked_notes` row is missing or the denominator is zero.

The recorded fixture values for this section are synthetic. The fixture's liability rows carry a
positive-scale sign profile, so its `liability_yield_pct` is negative and its `cln_scale` is positive,
which is the inverse of the production profile documented below. Read the fixture as structural and
unit evidence only; the sign and magnitude interpretation ("positive `cln_drag_bp` means CLN raises
the liability cost") is stated against the production profile, not against this fixture.

## Report-caliber reference values (not fixture values)

The capture-ready fixture under `tests/golden_samples/GS-PROD-CAT-PNL-A/response.json` is synthetic
month-pair data for `2026-02-28`. Its magnitudes and its liability sign profile are structural
evidence only; they do **not** certify production caliber. The approved production readings for the
2026-08 report to the supervising bank leader were run and certified by the main agent and are frozen
here for reconciliation, not recomputed by this sample:

| 口径 | 生息资产 | 资产端(含TPL) | 负债端 | 生息资产利差 (`MTR-PCP-015`) | 资产负债(含TPL)利差 (`MTR-PCP-021`) |
| --- | --- | --- | --- | --- | --- |
| 累计 YTD（1–7月，`report_date=2026-07-31`, `view=ytd`） | 2,936.23亿 @ 2.36% | 3,779.38亿 @ 2.51% | 1,758.17亿 @ 1.58% | 0.78%（78BP） | 0.93%（93BP） |
| 单月（7月，`report_date=2026-07-31`, `view=monthly`） | 3,003.82亿 @ 2.29% | 3,871.49亿 @ 2.17% | 1,759.90亿 @ 1.53% | 0.76%（76BP） | 0.64%（64BP） |
| 参考：6月末 YTD（领导引用，`report_date=2026-06-30`, `view=ytd`） | 2,924.65亿 @ 2.37% | 3,763.60亿 @ 2.57% | 1,757.88亿 @ 1.59% | 0.78%（78BP） | 0.98%（98BP） |

CLN drag reference values (`MTR-PCP-025`~`MTR-PCP-029`):

| 口径 | `liability_yield_pct` | `liability_yield_ex_cln_pct` | `cln_yield_pct` | `cln_drag_bp` | `cln_scale` |
| --- | --- | --- | --- | --- | --- |
| `2026-06-30` / `ytd` | 1.59% | 1.57% | 2.81% | ≈1.4 | −19.35亿 |
| `2026-07-31` / `ytd` | 1.58% | 1.57% | 2.79% | ≈1.4 | −19.47亿 |
| `2026-07-31` / `monthly` | 1.53% | 1.52% | 2.67% | ≈1.3 | −20.21亿 |

Reference-value rules:

- These numbers come from the approved cross-stream contract for this change; do not recompute and
  overwrite them from a local run. If a re-run disagrees, report the discrepancy instead of editing.
- The 78BP vs 93BP gap at `2026-07-31` / `ytd` is the caliber difference between the two spreads
  (TPL, derivatives, and intermediate-business income are inside the asset-side caliber only), not a
  calculation defect.
- `monthly` and `ytd` differ because `days_for_view` differs; both must be reportable.

## Companion scenario probe

The companion scenario probe is `GET /ui/pnl/product-category?report_date=2026-02-28&view=monthly&scenario_rate_pct=2.5`.

Required scenario assertions:

- HTTP status is `200`.
- `result_meta.basis == "scenario"`.
- `result_meta.scenario_flag == true`.
- `result.report_date == "2026-02-28"`.
- `result.view == "monthly"`.
- `result.scenario_rate_pct == 2.5`.
- scenario-owned FTP fields change versus the formal baseline, including `asset_total.cny_ftp`.
- baseline row identity and category tree are preserved:
  - baseline and scenario row `category_id` sequences match.
  - `bond_investment.children` remains exactly `bond_tpl/bond_ac/bond_ac_other/bond_fvoci/bond_valuation_spread`.

This is page/sample truth for the existing companion probe, not a second formal `metric_id` binding set and not a second full golden matrix sample.

### Scenario promotion gate

Promoting this companion probe into a second full golden matrix sample requires all of the following evidence:

- A separate scenario `request.json` and `response.json` pair captured from the governed endpoint.
- Scenario-specific assertions that freeze row identity, category tree, scenario-owned FTP deltas, and unchanged non-scenario fields.
- No new scenario `metric_id` binding without an approved metric matrix and metric dictionary rows.
- Business-owner or delegated approval recorded in a non-placeholder scenario approval artifact.

## Reconciliation

- Reconcile this page-level sample with `docs/pnl/product-category-golden-sample-a.md`.
- Do not reinterpret page rows through holdings-side categories.
