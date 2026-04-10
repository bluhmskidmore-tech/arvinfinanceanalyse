# AGENTS.md

## Macro Boundary Override

For the current macro-data workstream only, execution is explicitly allowed beyond the repo's original `Phase 1` stop line.

This scoped override applies to all files under `backend/app/`.

Allowed scope in this override:
- real Choice-first macro thin slice
- live Choice HTTP fetch path
- raw vendor archival
- vendor lineage governance
- DuckDB normalization into `choice_market_snapshot`
- thin `fact_choice_macro_daily`
- one DuckDB-backed query surface

Still out of scope:
- AkShare parity with Choice
- unrelated formal finance formula changes
- frontend-side formal metric computation
- broad multi-consumer rollout before the first query surface is stable

## Non-negotiable constraints

- Keep the existing architecture direction:
  `frontend -> api -> services -> (repositories / core_finance / governance) -> storage`
- API/service paths remain DuckDB read-only.
- All DuckDB writes continue to flow through `tasks/`.
- Formal finance logic still belongs only in `backend/app/core_finance/`.
