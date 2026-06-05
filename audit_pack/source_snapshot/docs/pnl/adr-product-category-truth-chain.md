# ADR: Product-Category PnL Truth Chain

## Status

Accepted for documentation freeze on `2026-04-23`.

## Context

The product-category PnL page already has a real end-to-end chain:

- source pair discovery
- canonical source parsing
- `core_finance` calculation
- materialized read model
- governed service / API
- frontend consumer page

The recurring maintenance failure is not missing code. It is unstable meaning:

- people treat the page as a generic table
- AI searches nearby holdings logic or legacy snippets
- row semantics drift away from the governed source pair and formal path

## Decision

For `product-category-pnl`, the only accepted truth chain is:

`总账对账YYYYMM.xlsx + 日均YYYYMM.xlsx`
-> `backend/app/services/product_category_source_service.py`
-> `backend/app/core_finance/product_category_pnl.py`
-> `product_category_pnl_formal_read_model`
-> `backend/app/services/product_category_pnl_service.py`
-> `/ui/pnl/product-category`
-> `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`

All page-row meaning must be derived from that chain.

## Row Authority

The page rows are governed product-category rows, not holdings-side research categories.

Accepted row authority:

- the paired ledger + average source files
- the canonical mapping authority in `backend/app/core_finance/config/product_category_mapping.py`
- the formal aggregation path in `backend/app/core_finance/product_category_pnl.py`

Forbidden row authority:

- inferring categories from `zqtz` holdings-side logic
- inferring categories from research buckets such as `利率债 / 信用债`
- copying semantics from unrelated analytics pages
- letting frontend display order become business truth

## Scenario Rule

`scenario_rate_pct` is an explicit scenario overlay.

It may change scenario-owned fields such as FTP-related values and scenario totals, but it must not redefine:

- baseline row identity
- baseline report date
- baseline category tree
- the governed manual-adjustment source of record

Formal and scenario outputs must remain isolated in:

- read models
- cache identity
- `result_meta.basis`
- `result_meta.scenario_flag`

## Manual Adjustment Rule

Manual adjustments are allowed only as a governed overlay.

Only `approved` adjustments may participate in formal output. Their effect must be visible through the same governed API path rather than through client-side patching or spreadsheet-only reasoning.

## Consequences

This decision intentionally blocks "quick fixes" that rely on nearby code or intuitive category guesses.

In return, it gives the repo one stable answer to these questions:

- where product-category rows come from
- what this page is allowed to mean
- which path AI must trace before changing anything

## Verification References

- `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md`
- `tests/test_product_category_pnl_flow.py`
- `tests/test_product_category_mapping_contract.py`
- `backend/app/api/routes/product_category_pnl.py`
