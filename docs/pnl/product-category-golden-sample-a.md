# Product-Category Golden Sample A

## 1. Goal

Define the first page-level golden sample for the product-category PnL page.

This document defines the first captured page-level sample boundary for the product-category PnL page so future AI work stops drifting.

## 2. Sample Identity

- Sample ID: `GS-PROD-CAT-PNL-A`
- Status: `capture-ready`
- Primary surface:
  - `GET /ui/pnl/product-category?report_date=2026-02-28&view=monthly`
- Companion scenario probe:
  - `GET /ui/pnl/product-category?report_date=2026-02-28&view=monthly&scenario_rate_pct=2.5`

## 3. Why This Is the First Sample

This sample is the smallest page-level artifact that freezes:

- one governed report date
- one governed view
- the totals triplet
- the category tree identity
- the scenario comparison entry point

That is enough to stop repeated re-interpretation of what the page is supposed to mean.

## 4. Authority Chain

The sample must be captured against this chain:

- `总账对账202602.xlsx`
- `日均202602.xlsx`
- `backend/app/services/product_category_source_service.py`
- `backend/app/core_finance/product_category_pnl.py`
- `product_category_pnl_formal_read_model`
- `backend/app/services/product_category_pnl_service.py`
- `/ui/pnl/product-category`

## 5. Required Assertions

### Envelope and view

- `result_meta.basis == "formal"`
- `result_meta.scenario_flag == false`
- `result.report_date == "2026-02-28"`
- `result.view == "monthly"`
- `result.asset_total.baseline_ftp_rate_pct == "1.60"` for the 2026 report-year FTP policy
- `set(result.available_views) == {"monthly", "qtd", "ytd", "year_to_report_month_end"}`

### Totals

- `asset_total.business_net_income + liability_total.business_net_income == grand_total.business_net_income`
- `asset_total.category_id == "asset_total"`
- `liability_total.category_id == "liability_total"`
- `grand_total.category_id == "grand_total"`
- This sample is now bound to the three headline `metric_id` values and the decision 3C row-level detail metric set.
- `MTR-PCP-001`: `result.asset_total.business_net_income`
- `MTR-PCP-002`: `result.liability_total.business_net_income`
- `MTR-PCP-003`: `result.grand_total.business_net_income`
- `MTR-PCP-004`: `result.rows[].cnx_scale`
- `MTR-PCP-005`: `result.rows[].cny_scale`
- `MTR-PCP-006`: `result.rows[].foreign_scale`
- `MTR-PCP-007`: `result.rows[].cny_ftp`
- `MTR-PCP-008`: `result.rows[].foreign_ftp`
- `MTR-PCP-009`: `result.rows[].cny_net`
- `MTR-PCP-010`: `result.rows[].foreign_net`
- `MTR-PCP-011`: `result.rows[].business_net_income`
- `MTR-PCP-012`: `result.rows[].weighted_yield`

### Category structure

- `rows` contains `bond_investment`
- `bond_investment.children == ["bond_tpl", "bond_ac", "bond_ac_other", "bond_fvoci", "bond_valuation_spread"]`
- `rows` contains `bond_tpl`

### Scenario comparison

- scenario companion request flips the page to `basis == "scenario"`
- scenario companion request changes governed scenario-owned FTP fields
- scenario companion request does not change baseline row identity or the category tree
- scenario companion request remains a probe until the Scenario promotion gate is met

### Scenario promotion gate

Promoting the companion probe into a second full golden matrix sample requires:

- A separate scenario `request.json` and `response.json` pair captured from the governed endpoint.
- Scenario-specific assertions that freeze row identity, category tree, scenario-owned FTP deltas, and unchanged non-scenario fields.
- No new scenario `metric_id` binding without an approved metric matrix and metric dictionary rows.
- Business-owner or delegated approval recorded in a non-placeholder scenario approval artifact.

### Reproducibility

- two identical requests return identical result payloads
- manual adjustment changes on `bond_tpl` are visible through the governed page path

## 6. Evidence Sources

- `tests/test_product_category_pnl_flow.py`
- `tests/test_product_category_mapping_contract.py`
- `tests/test_result_meta_on_all_ui_endpoints.py`

## 7. Residual Risks

This sample is now `capture-ready`, but these gaps remain visible:

- standalone outward `as_of_date` is intentionally not provided for this page under decision 1B
- additional detail fields and scenario outputs outside `MTR-PCP-004`~`MTR-PCP-012` are not active `metric_id` bindings without a new approved matrix / dictionary / sample / test bundle
- scenario comparison is defined as a companion probe, not yet a separate frozen sample, until the Scenario promotion gate is met

## 8. Expected Pack Shape

The sample pack contains:

- `request.json`
- `response.json`
- `assertions.md`
- `approval.md`

## 9. Freeze Rule

Changes that alter this sample require:

- review against the page truth contract
- review against the truth-chain ADR
- updated sample assertions when governed meaning changes
