# V3 Cutoff And Exit Criteria

## Status

- document type: release-governance overlay
- current repo status: `accepted at cutoff for the included scope`
- current declaration: `GO` in `docs/V3_CUTOFF_DECLARATION_2026-04-17.md`
- intended scope: current repo-wide `Phase 2` governed formal-compute release, not a whole-repo "everything is live" declaration

## Purpose

This document defines what V3 must prove before the current governed release can be treated as a stable cutoff.

It exists to answer one question clearly:

`What does "ready enough to freeze and ship" mean for the current V3 boundary?`

This document does **not** replace:

- `AGENTS.md`
- `prd-moss-agent-analytics-os.md`
- `docs/REPO_WIDE_PHASE2_CUTOVER_DEFINITION.md`
- `docs/acceptance_tests.md`

It is a release gate overlay for the currently included boundary.

## Active Cutoff Scope

This cutoff applies only to the currently included release surface:

- formal balance
- formal PnL
- formal FX
- formal yield curve
- PnL bridge
- risk tensor
- core bond-analytics formal read surfaces
- `executive-consumer cutover v1`
  - `/ui/home/overview`
  - `/ui/home/summary`
  - `/ui/pnl/attribution`

## Explicit Non-Goals

This cutoff does **not** require promotion of surfaces that are still explicitly excluded:

- `/ui/risk/overview`
- `/ui/home/alerts`
- `/ui/home/contribution`
- Agent MVP / real `/api/agent/query` enablement
- reserved `/api/cube/query` / `/api/cube/dimensions/*` public rollout
- reserved liability-analytics compatibility public rollout:
  - `/api/risk/buckets`
  - `/api/analysis/yield_metrics`
  - `/api/analysis/liabilities/counterparty`
  - `/api/liabilities/monthly`
- `source_preview`
- `macro-data`
- `choice-news`
- market-data preview/vendor/analytical promotion
- `qdb_gl_monthly_analysis`
- `liability_analytics_compat`
- cube-query broad rollout
- other `Phase 3 / Phase 4` style expansion work

Excluded surfaces may remain hidden, placeholder-only, analytical-only, or explicit `503` without blocking this cutoff.

## Cutoff Goals

### G1. Governed Formal Results Are Trustworthy

The included formal-compute chains must:

- read governed inputs only
- derive formal finance logic only in `backend/app/core_finance/`
- materialize through `backend/app/tasks/` only
- return outward envelopes with stable `result_meta`
- fail closed when required governed inputs are missing

### G2. Included Consumer Surfaces Are Stable

The included user-facing surfaces must:

- load without white-screen or infinite-spinner behavior
- show data, empty state, or governed degraded state explicitly
- avoid silently crossing into excluded surfaces
- keep route behavior stable across execution contexts

### G3. Release Evidence Is Reproducible

The repo must have a small, repeatable verification pack that a maintainer can run and understand.

### G4. Excluded Surfaces Stay Excluded

The current release is only safe if excluded surfaces do not drift into accidental promotion.

## Severity Model

### P0. Release Blocker

Examples:

- formal correctness failure
- lineage or `result_meta` corruption
- silent fallback across formal boundaries
- included route returns incorrect status or wrong governed/analytical semantics
- included chain not runnable

### P1. Must Fix Or Waive Explicitly

Examples:

- unstable execution depending on working directory
- release-gate tests fail
- included page works only in one local launch mode
- inconsistent degraded-state contract on included routes

### P2. Can Ship With Recorded Debt

Examples:

- slow but bounded verification
- non-blocking bundle-size warnings
- incomplete parity for still-excluded consumers
- maintainability debt with owner and follow-up

### P3. Improvement Track

Examples:

- visual polish
- broader rollout
- additional convenience pages
- performance tuning outside release thresholds

## Required Evidence Pack

At cutoff time, the release evidence pack must include all of the following:

1. Frontend verification
   - `npm run test`
   - `npm run build`
   - `npm run lint`

2. Backend verification
   - a bounded backend release suite that completes reliably
   - current named gate: `python scripts/backend_release_suite.py`
   - route and contract tests for the in-scope chains
   - route tests for excluded executive surfaces staying `503`
   - route tests for reserved `cube-query` / liability-analytics compatibility routes staying `503`

3. Route smoke
   - direct `TestClient` or equivalent smoke for included routes
   - same status behavior from repo root and backend working directory

4. Live audit
   - a current audit snapshot under `docs/`
   - current known yellow/red findings listed honestly

5. Parity inventory
   - a maintained matrix showing what is landed, partial, excluded, or missing

## Exit Criteria

All of the following must be true before declaring cutoff:

### E1. Included Formal Chains Are Green

At least one maintained verification suite proves the included chains are green:

- balance analysis
- formal PnL
- risk tensor
- bond analytics formal read surfaces
- ledger-facing governed read surfaces included in the current release

### E2. Included Executive E1 Surfaces Are Green

These routes must return stable `200` with correct analytical envelope semantics:

- `/ui/home/overview`
- `/ui/home/summary`
- `/ui/pnl/attribution`

### E3. Excluded Executive Surfaces Are Stable `503`

These routes must remain explicit fail-closed until a later cutover promotes them:

- `/ui/risk/overview`
- `/ui/home/alerts`
- `/ui/home/contribution`

### E3A. Reserved Query / Compat Surfaces Stay Reserved

These routes must remain explicit `503` or equivalent reserved behavior until a later cutover promotes them:

- `/api/cube/query`
- `/api/cube/dimensions/*`
- `/api/risk/buckets`
- `/api/analysis/yield_metrics`
- `/api/analysis/liabilities/counterparty`
- `/api/liabilities/monthly`

### E4. Storage Path Resolution Is Context-Stable

The same included route set must behave consistently when the app is loaded from:

- repo root
- backend working directory

No route may flip between `200` and `503` only because the current working directory changed.

### E5. A Bounded Backend Gate Exists

Either:

- full backend `pytest` is green in a practical release window

or:

- a named bounded release suite is green and accepted as the formal cutoff gate

If the full suite is too slow or too open-ended, the bounded gate must be explicit and documented.

### E6. No Open P0 In Scope

There must be no unresolved P0 issue affecting the current included release scope.

### E7. No Unowned P1 In Scope

Any remaining P1 issue must have:

- an explicit owner
- an explicit reason it is not release-blocking
- an explicit follow-up target

### E8. Current Docs Match Runtime Reality

The following must agree with actual route/test behavior:

- `docs/REPO_WIDE_PHASE2_CUTOVER_DEFINITION.md`
- `docs/CURRENT_BOUNDARY_HANDOFF_2026-04-10.md`
- `docs/V2_V3_PARITY_MATRIX.md`
- the latest V3 live audit document

## Current Gap Snapshot (2026-04-17)

Based on the current audit, route verification, and live preflight:

### Confirmed good enough now

- frontend test/build/lint gates are passing
- named bounded backend gate exists:
  - `python scripts/backend_release_suite.py`
  - current observed result: `141 passed in 228.49s (0:03:48)`
- CI workflow runs the same named bounded backend gate
- code-level excluded/reserved route tests are green:
  - `python -m pytest -q tests/test_executive_dashboard_endpoints.py tests/test_cube_query_api.py tests/test_liability_analytics_api.py tests/test_liability_analytics_envelope_contract.py`
  - current observed result: `13 passed`
- included executive E1 routes are stable
- excluded executive routes are now stable `503`
- reserved `cube-query` public routes are now stable `503`
- reserved liability-analytics compatibility public routes are now stable `503`
- core storage-path resolution is stable across repo-root and backend working directories
- product-category PnL formal read route is live again in the current workspace
- parity matrix exists
- live audit exists

### Cutoff declaration

- the included scope is now explicitly declared at cutoff:
  - `docs/V3_CUTOFF_DECLARATION_2026-04-17.md`
- live `python scripts/governed_phase2_preflight.py` now passes after reconciling the stale `7888` listener with current route code
- the canonical backend gate is additionally hardened so `cube_query` and `liability_analytics` fail-closed route tests are now part of `python scripts/backend_release_suite.py`

### Non-blocking carried debt

- full backend `python -m pytest -q` still does not complete within the current audit window; under `E5` this remains broader diagnostic debt, not the current cutoff blocker
- frontend lint currently passes with warnings; keep the warnings visible until a later cleanup slice

## Recommended Release Shape

Do **not** describe the current release as:

- "V3 fully landed"
- "all workbench surfaces shipped"
- "all executive routes promoted"

Describe it as:

- governed `Phase 2` formal-compute cutoff candidate
- plus `executive-consumer cutover v1`
- with explicit excluded surfaces still fail-closed or held at placeholder / reserved status

## Maintenance Rule

Whenever one of these changes, update this document in the same change:

- included release scope
- excluded release scope
- named backend cutoff gate
- current blocker list
- live audit verdict

If a later cutover promotes an excluded surface, update:

- this document
- `docs/REPO_WIDE_PHASE2_CUTOVER_DEFINITION.md`
- relevant tests
- parity matrix

in the same change set.
