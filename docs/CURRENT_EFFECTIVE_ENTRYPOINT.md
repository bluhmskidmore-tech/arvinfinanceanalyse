# CURRENT_EFFECTIVE_ENTRYPOINT.md

- `Role`: navigation/index only
- `Authority`: non-authorizing
- `Scope`: repo-level only
- `Last reviewed`: 2026-04-22
- `Current-state read path`: `AGENTS.md` -> `docs/DOCUMENT_AUTHORITY.md` -> `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`
- `If conflict`: follow `AGENTS.md`, `docs/DOCUMENT_AUTHORITY.md`, and the applicable dated execution update

## Purpose

Use this file as the single repo-level navigation entrypoint for current state lookup.

This file does **not**:

- grant execution scope
- override authority docs
- elevate `.omx` artifacts into repo-level authority
- apply a "latest update wins" rule

## Current Repo Boundary Source

- `docs/CURRENT_BOUNDARY_HANDOFF_2026-04-10.md`

Use it for the current code-state-vs-boundary summary.

## Active Scoped Overrides

- `Selection rule`: dated execution updates are selected by active-lane applicability, not by recency alone.
- Available named overrides:
  - `docs/CURRENT_EXECUTION_UPDATE_2026-04-09.md`
  - `docs/CURRENT_EXECUTION_UPDATE_2026-04-10.md`
  - `docs/CURRENT_EXECUTION_UPDATE_2026-04-11.md`
  - `docs/CURRENT_EXECUTION_UPDATE_2026-04-12.md`

If the active task is outside a named workstream, do not treat a dated execution update as a repo-wide override.

## Current Repo-Level Docs To Consult

- `docs/page_contracts.md`
  - Use after repo-level boundary/current-state lookup is clear.
- `docs/CODEX_HANDOFF.md`
  - Background/reference handoff only.
- `docs/IMPLEMENTATION_PLAN.md`
  - Phase and implementation reference only.

## Workflow-Local Evidence

- `.omx/context/*.md`
  - Workflow context snapshots.
- `.omx/runs/*/HANDOFF.md`
  - Workflow handoff and phase outcome evidence.

These remain supporting evidence, not repo-level authority.

## Historical / Reference Material

- `docs/CODEX_HANDOFF.md`
- `docs/IMPLEMENTATION_PLAN.md`
- older workflow-specific plans and handoffs under `.omx/`

Read them for background, not as the repo-level "start here" surface.

## Maintenance Rule

Update this file when:

- repo-wide boundary interpretation changes
- a dated execution update becomes applicable to the active lane
- the active repo-priority workflow changes
- a previously active lane is demoted to historical/reference status

Keep updates manual, links-only where possible, and bounded to repo-level navigation.
