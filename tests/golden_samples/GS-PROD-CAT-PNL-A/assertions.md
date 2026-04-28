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

## Reconciliation

- Reconcile this page-level sample with `docs/pnl/product-category-golden-sample-a.md`.
- Do not reinterpret page rows through holdings-side categories.
