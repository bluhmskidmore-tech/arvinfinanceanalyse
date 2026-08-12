# AGENTS.md

## Mission and scope

Priority order:
1. business metric correctness
2. page/workflow closure
3. traceability and validation
4. minimal, reviewable changes

- Fix one page or workflow at a time and prefer the smallest effective change.
- Do not refactor unrelated modules or add speculative abstractions.
- Never guess an ambiguous metric definition, unit, date, or lineage; report the ambiguity with evidence.
- Business correctness outranks architectural elegance.
- Platform refactors, generic infrastructure, base-layer rebuilds, framework beautification, and unrelated performance work are out of scope unless the current task proves they are the root cause.

## Navigation and local instructions

- Before broad exploration, scan `docs/agent_codebase_map.md`, then work from the relevant subtree.
- Read the closest applicable `AGENTS.md` / `CLAUDE.md`; path-specific rules override general workflow guidance.
- Frontend work must follow `frontend/AGENTS.md`.
- Backend application work must follow `backend/app/AGENTS.md` and `backend/CLAUDE.md`.
- Test work must follow `tests/AGENTS.md` and `tests/CLAUDE.md`.
- Avoid broad searches through generated data, dependencies, caches, logs, build outputs, and temporary directories.
- Prefer targeted MCP/GitNexus evidence over loading whole governance documents, raw datasets, or logs into context.

## Business evidence

- Inspect only the business paths affected by the current change.
- For an affected displayed metric, verify the relevant path from API response through transformation/state to the rendered value or visualization.
- Check units, precision, null semantics, date basis, stale/fallback state, mocks, and filters only where material to the affected path.
- Use project metric-contract, lineage, catalog, and quality evidence according to the nearest path rules and demonstrated risk.
- If required evidence tooling is unavailable, identify the unavailable source, the local substitute, and the residual risk. Do not invent business meaning.

## Protected boundaries

Do not proactively modify these without explicit instruction or direct root-cause evidence:

- database schema
- authentication or permission frameworks
- queue, scheduler, or cache foundations
- global SDK wrappers
- shared infrastructure layers
- app-wide state architecture
- unrelated backend services

## GitNexus

The indexed project for this working tree (`F:\MOSS-V3`) is `moss-v3-main-current-20260809`.

Do not use `moss-v3-codex-v1`: despite the name, that index points at a separate worktree
(`~/.codex/worktrees/772c/MOSS-V3`) and will return callers and risk levels for a different tree.

- Before changing a function, class, or method, run upstream impact analysis for that symbol and report direct callers, affected processes, and risk.
- Warn before editing when impact is HIGH or CRITICAL.
- Use process queries for unfamiliar flows and symbol context for callers/callees.
- Use semantic rename tooling instead of search-and-replace for symbol renames.
- Run change detection before committing.
- Treat the index as stale when `.gitnexus/meta.json`'s `lastCommit` differs from `git rev-parse HEAD`. Impact analysis run against a stale index reports callers that no longer exist and misses new ones.
- When the index is stale, run `npx gitnexus analyze --skip-agents-md` so re-indexing does not expand the root instruction files.
- Impact analysis is not required for documentation, copy, styles, or configuration edits that do not change code symbols.

Detailed GitNexus workflows live under `.claude/skills/gitnexus/`; load only the workflow needed by the task.

## Work and validation protocol

Before editing, state:

- the page or workflow in scope
- the first files to inspect
- what will not be touched

After editing, report:

- root cause
- changed files
- validation commands and results
- remaining risks

Run the narrowest relevant lint, typecheck, targeted tests, and browser checks first. Widen only when a shared boundary is crossed or a narrow check reveals a broader issue. If a command cannot run, explain why.
