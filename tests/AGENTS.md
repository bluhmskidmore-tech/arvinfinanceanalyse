# AGENTS.md

## Macro Boundary Override For Tests

For the current macro-data workstream only, tests under `tests/` are allowed to validate a scoped Choice-first real-delivery thin slice.

Allowed test scope:
- live Choice fetch path behavior
- raw archive behavior
- vendor lineage metadata
- DuckDB normalization into `choice_market_snapshot`
- thin `fact_choice_macro_daily`
- one DuckDB-backed query surface

Still out of scope:
- AkShare parity
- unrelated formal finance logic expansion
- frontend-side formal metric computation
