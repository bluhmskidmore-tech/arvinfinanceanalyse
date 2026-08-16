# GS-MKT-RATES-FRAGMENT-A Assertions

## Scope

- Endpoint: `GET /ui/market-data/rates`
- Page fragment: `PAGE-MKT-001` formal rates slice (Market Tape, `RateQuoteTable`, `MoneyMarketTable`)
- Sample type: `capture-ready` **fragment-only** (does not close `GAP-MKT-DATA`)

## Envelope

- `result_meta.basis` = `formal`
- `result_meta.formal_use_allowed` = `true`
- `result_meta.result_kind` = `market_data.rates`
- `result_meta.rule_version` = `rv_market_data_rates_formal_v1`
- `result_meta.cache_version` = `cv_market_data_rates_formal_v1`
- `result_meta.source_version` = `sv_market_data_rates_gs_a__sv_public_funding` (aggregated lineage)
- `result_meta.vendor_version` = `vv_choice_macro_gs_a__vv_public_repo` (aggregated lineage)
- `result_meta.quality_flag` = `ok`
- `result_meta.source_surface` = `market_data`

## Series boundary

- Only `refresh_tier=stable` (or default-stable) series appear in `result.series`.
- Frozen headline series (by `series_id`):
  - `EMM00166466` — 10Y treasury, `value_numeric=1.71`, `trade_date=2026-04-10`
  - `EMM00166462` — 5Y treasury, `value_numeric=1.58`, `trade_date=2026-04-10`
  - `EMM00166498` — 5Y CDB, `value_numeric=2.05`, `trade_date=2026-04-10`
  - `EMM00166502` — 10Y CDB, `value_numeric=2.18`, `trade_date=2026-04-10`
  - `M001` — 7D OMO, `value_numeric=1.75`, `trade_date=2026-04-10`
  - `M002` — DR007, `value_numeric=1.83`, `trade_date=2026-04-10` (lineage tokens neutral; catalog `vendor_name=choice`)

## Frontend tie-out (no recomputation)

- `buildMarketDataTerminalModel({ ratesEnvelope })` must render Market Tape labels:
  - `10年国债` → `1.71%`
  - `5年国债` → `1.58%`
  - `10年国开` → `2.18%`
  - `5年国开` → `2.05%`
  - `DR007` → `1.83%`
- Source filter uses catalog `vendor_name` when lineage tokens omit `choice` (see `classifyTerminalSource`).

## Regression anchors

- `tests/test_golden_samples_capture_ready.py` (`GS-MKT-RATES-FRAGMENT-A`)
- `frontend/src/features/market-data/lib/marketDataRatesFragmentGolden.test.ts`
- `frontend/tests/playwright/market-data-terminal-smoke.spec.mjs`
