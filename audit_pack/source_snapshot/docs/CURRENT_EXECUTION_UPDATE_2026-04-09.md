# Current Execution Update (2026-04-09)

This document records the current user-authorized execution boundary for the macro-data stream.

## Status

- This is a scoped override, not a repo-wide phase change.
- The repo default boundary remains `Phase 1`.
- `Phase 1 closeout` and other planned next slices stay governed by their own boundaries unless separately authorized.

## Override

The previous "Phase 1 only" stop line is lifted for the current macro-data workstream.

## Allowed current execution

- real Choice-first macro thin slice
- live Choice fetch path
- raw response archival
- vendor lineage registration
- DuckDB normalization into `choice_market_snapshot`
- thin `fact_choice_macro_daily`
- one DuckDB-backed query surface

## Current non-goals

- AkShare feature parity
- broad frontend rollout
- unrelated formal finance expansion

## Scope guard

- This override applies only to the macro-data stream named above.
- It must not be used to justify general `Phase 2` formal-finance work.
- It must not be used to reopen Agent MVP / Phase 4A / 4B.
- It must not be used to authorize unrelated next slices, even if they are already planned in `.omx/plans/`.
