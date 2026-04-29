# Choice Stock Catalog

This asset is the explicit Choice-only gate for Livermore stock inputs. It records which Choice indicators are allowed to feed sector ranking, stock candidate filters, and limit-up quality once those fields have been confirmed.

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
- `vendor_indicator`: Choice/EmQuant indicator sent to `css`, `csd`, or `ctr`.
- `call`: Choice call family, currently `css`, `csd`, or `ctr`.
- `confirmed`: must be `true` only after the indicator and entitlement have been checked.
- `required`: whether the entry gates Livermore readiness.
- `unit` and `description`: optional review metadata.

## Fail-Closed Behavior

The readiness loader reports the catalog as blocked when:

- the catalog file is missing;
- the JSON does not match the schema;
- any required input family is absent;
- a required entry has `confirmed: false`; or
- a required entry has an empty `vendor_indicator`.

Blocked readiness means Livermore must keep `stock_candidates` and `sector_rank` unsupported, emit explicit Choice dependency diagnostics, and avoid calling Choice `css` or `csd`.

## Current State

The checked-in catalog is intentionally empty. It commits no unconfirmed Choice field codes. Populate it only after confirming field names and entitlement behavior through the Choice terminal/API command generator.
