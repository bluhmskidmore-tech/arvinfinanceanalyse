# Current Execution Update (2026-04-10)

This document records the current user-authorized execution boundary for the `zqtz / tyw` snapshot-materialization stream.

## Status

- This is a scoped override, not a repo-wide phase change.
- The repo default boundary remains `Phase 1`.
- `Phase 1 closeout` and other planned next slices stay governed by their own boundaries unless separately authorized.

## Override

The previous stop line is lifted only for the `zqtz / tyw` standardized snapshot-materialization workstream.

## Allowed current execution

- manifest-selected source binding for `zqtz` / `tyw`
- archive reopen/read helper(s) for governed `archived_path` inputs
- snapshot-specific DuckDB DDL for:
  - `zqtz_bond_daily_snapshot`
  - `tyw_interbank_daily_snapshot`
- task/worker-only snapshot materialization path
- snapshot-specific governance records:
  - `snapshot_build_run`
  - `snapshot_manifest`
- internal-only verification seam
- snapshot-specific tests and rerun semantics

## Current non-goals

- formal compute
- monthly average
- FX conversion
- issuance exclusion
- H/A/T derivation
- workbench or `executive.*` consumption
- public snapshot read API

## Scope guard

- This override applies only to the `zqtz / tyw` snapshot-materialization stream named above.
- It must not be used to justify general `Phase 2` formal-finance work.
- It must not be used to authorize workbench rollout or `executive.*` consumption.
- It must not be used to reopen Agent MVP / Phase 4A / 4B.
- It must not be used to authorize unrelated next slices, even if they are already planned in `.omx/plans/`.
- Any fallback to direct unmanaged `data_input` scan remains out of bounds.
- Preview tables remain explanatory surfaces and must not become snapshot source-of-truth input.
