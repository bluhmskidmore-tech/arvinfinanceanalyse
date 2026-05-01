# Choice Stock Catalog

This asset is the explicit gate for Livermore stock inputs. It records the Choice indicators that are allowed to feed the stock universe, sector membership, sector ranking, stock candidate filters, and limit-up quality once those fields have been confirmed.

The current runtime is evidence-driven but not Choice-only for daily bars: if Choice `csd` returns entitlement error `10001012`, `backend/app/tasks/choice_stock_materialize.py` can fill daily OHLCV, free-float turnover, trading status, and limit prices from the localized Tushare stock fallback. Those rows are auditable through `choice_stock_request_audit.status = 'completed_tushare_fallback'` and a `vv_choice_tushare_stock_*` vendor version.

## Location

- Structured source: `config/choice_stock_catalog.json`
- Settings key: `MOSS_CHOICE_STOCK_CATALOG_FILE`
- Runtime readiness loader: `backend/app/repositories/choice_stock_adapter.py`

## Required Input Families

The Livermore stock slice is blocked until the catalog has confirmed entries for every required family:

- `sector_membership`
- `sector_strength`
- `stock_universe`
- `stock_ohlcv`
- `stock_status`
- `limit_up_quality`

## Entry Shape

Each `fields[]` entry uses:

- `input_family`: one of the required families above.
- `field_key`: internal stable name for the field.
- `vendor_indicator`: Choice/EmQuant indicator sent to `sector`, `css`, `csd`, or `ctr`.
- `call`: Choice call family in this repo: `sector` (e.g. A-share universe), `css`, `csd`, or `ctr` when used.
- `confirmed`: must be `true` only after the indicator and entitlement have been checked.
- `confirmation_source`: non-empty evidence pointer for confirmed entries, such as the Choice terminal command generator export, entitlement ticket, or captured API smoke result.
- `confirmed_at`: non-empty confirmation date or timestamp for confirmed entries.
- `required`: whether the entry gates Livermore readiness.
- `unit` and `description`: optional review metadata.

`confirmed: true` alone is not enough to unlock readiness. A required entry only counts after `vendor_indicator`, `confirmation_source`, and `confirmed_at` are all non-empty. This keeps locally guessed field names from accidentally enabling stock analysis.

## Fail-Closed Behavior

The readiness loader reports the catalog as blocked when:

- the catalog file is missing;
- the JSON does not match the schema;
- any required input family is absent;
- a required entry has `confirmed: false`; or
- a required entry has an empty `vendor_indicator`, `confirmation_source`, or `confirmed_at`.

Blocked readiness means Livermore must keep `stock_candidates` and `sector_rank` unsupported, emit explicit dependency diagnostics, and avoid calling Choice `sector`, `css`, or `csd`.

## Current State

The checked-in catalog is populated with live-probed fields from 2026-05-01:

- Choice `sector('001004', as_of_date)` for the A-share universe.
- Choice `css(..., 'SW2021,SW2021CODE', EndDate=..., ClassiFication=1)` for SW2021 level-1 sector membership.
- Choice `csd` field definitions for return, turnover, amplitude, OHLCV, trading status, and limit flags.
- Choice `css(..., 'ISSURGEDLIMIT,ISDECLINELIMIT,HLIMITEDAYS,LLIMITEDDAYS', TradeDate=...)` for point-in-time limit streak quality.

Important evidence boundary: Choice `HIGHLIMIT` / `LOWLIMIT` are yes/no limit **flags**, not limit **prices**. The Tushare stock fallback maps `stk_limit.up_limit` / `down_limit` into the same `HIGHLIMIT` / `LOWLIMIT` observation slots as **numeric prices** so downstream `limit_ratio` can use actual limits; interpret those cells as prices only when the row is under `completed_tushare_fallback` (or when values are clearly price-like), not as Choice flag encodings.

## Confirmation Workflow

1. Generate the exact Choice command from the terminal/API tool for the required stock input.
2. Run a one-symbol or one-date smoke query under the production entitlement.
3. Record the stable internal `field_key`, the exact `vendor_indicator`, `call`, `unit`, and a short `description`.
4. Set `confirmed: true`, fill `confirmation_source`, and fill `confirmed_at`.
5. If a `csd` entitlement blocks daily data, verify Tushare fallback with `python -m pytest -q tests/test_choice_stock_materialize.py`.
6. Run `python -m pytest -q tests/test_choice_stock_adapter.py tests/test_market_data_livermore_api.py`.
