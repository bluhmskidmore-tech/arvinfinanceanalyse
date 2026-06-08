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

Scenario outputs remain analytical scenario payloads unless a future decision explicitly promotes them.

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
