# Current Execution Update (2026-04-11)

This document records the current user-authorized execution boundary for the `zqtz / tyw` formal-balance-compute workstream.

## Status

- This is a scoped override, not a repo-wide phase change.
- The repo default boundary remains `Phase 1` outside this named workstream.
- This override supersedes the earlier "docs-only" stop line for `zqtz / tyw` formal balance work.

## Override

The previous stop line is lifted for the `zqtz / tyw` formal-balance-compute workstream.

## Allowed current execution

- formal-balance contract and schema alignment
- `backend/app/core_finance/` formal balance derivation for `zqtz / tyw`
- formal fact/table contract implementation for:
  - `fact_formal_zqtz_balance_daily`
  - `fact_formal_tyw_balance_daily`
- task/worker-only materialization path for formal balance facts
- balance-analysis repository / service / API work that consumes only governed formal facts
- internal-only verification seam
- formal-balance-specific tests and boundary guards

## Current non-goals

- broad frontend rollout beyond the first governed balance-analysis consumer
- `executive.*` consumption
- Agent MVP / Phase 4A / 4B
- unrelated formal-finance expansions outside the `zqtz / tyw` balance workstream

## Scope guard

- This override applies only to the `zqtz / tyw` formal-balance-compute stream named above.
- It must not be used to justify unrelated `Phase 2` work.
- Preview tables remain explanatory surfaces and must not become formal source-of-truth inputs.
- Snapshot tables remain standardized inputs, not direct formal outward responses.
