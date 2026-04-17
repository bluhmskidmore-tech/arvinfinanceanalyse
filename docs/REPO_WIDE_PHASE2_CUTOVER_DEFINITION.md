# Repo-wide Phase 2 Cutover Definition

## Status

This is the active definition for repo-wide `Phase 2` generic formal-compute cutover.

It defines:

- what repo-wide `Phase 2` means
- which formal-compute chains are included
- which consumers and surfaces are explicitly excluded
- how to interpret the current default execution boundary

## Meaning

Repo-wide `Phase 2` does not mean every page, every workbench, and every later-phase analytical surface is now open.

It means the repository default execution boundary has shifted from:

- `Phase 1 + named scoped override`

to:

- `repo-wide Phase 2` for the governed formal-compute mainline

The formal-compute mainline includes governed inputs, formal derivation in `backend/app/core_finance/`, task-only materialization in `backend/app/tasks/`, governed facts/read models, and outward formal result envelopes with stable `result_meta`, basis, and lineage semantics.

## Included Chains

- formal balance
- formal PnL
- formal FX
- formal yield curve
- PnL bridge
- risk tensor
- core bond-analytics formal read surfaces

## Executive Consumer Overlay

In addition to the formal-compute mainline, the active boundary now includes `executive-consumer cutover v1`:

- `/ui/home/overview`
- `/ui/home/summary`
- `/ui/pnl/attribution`

These are executive consumer routes, not formal source-of-truth result surfaces.

## Explicit Exclusions

The following are outside the current active boundary:

- the rest of `executive.*`, including:
  - `/ui/risk/overview`
  - `/ui/home/alerts`
  - `/ui/home/contribution`
- Agent MVP / real `/api/agent/query` enablement / `/agent`
- `source_preview`
- `macro-data`
- `choice-news`
- `market-data` preview/vendor/analytical surfaces
- `qdb_gl_monthly_analysis`
- `liability_analytics_compat`
- analytical-only compatibility surfaces
- cube-query
- broad frontend rollout
- other `Phase 3 / Phase 4` style expansion items

An excluded surface may still expose placeholder, explicit `503`, hidden-route, or analytical-only behavior without contradicting repo-wide `Phase 2`, as long as the exclusion remains documented.

## Invariants

1. `frontend -> api -> services -> (repositories / core_finance / governance) -> storage`
2. formal finance logic exists only in `backend/app/core_finance/`
3. API/service paths remain DuckDB read-only
4. DuckDB writes happen only through `backend/app/tasks/`
5. `Formal` / `Scenario` / `Analytical` remain isolated in semantics, tables, cache identity, and `result_meta`
6. outward formal results always include `result_meta`
7. standardized snapshots remain inputs, not outward formal source-of-truth results

## Ongoing Conditions

For this cutover definition to remain healthy:

- authority docs must stay aligned with this scope
- excluded surfaces must not be silently treated as included
- backend and frontend verification must remain green
- if a new surface is promoted into the formal mainline, docs and tests must be updated together

## Current State

As of `2026-04-17`:

- key active boundary documents are aligned to repo-wide `Phase 2`
- `executive-consumer cutover v1` is adopted for overview / summary / pnl-attribution
- excluded surfaces are explicitly called out
- backend `pytest tests -q` is green
- future inclusion of the remaining `executive.*` routes, Agent, or other excluded surfaces requires a new explicit cutover update
