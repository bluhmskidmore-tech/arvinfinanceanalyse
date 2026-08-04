# CLAUDE.md

`AGENTS.md` is the authoritative project policy. This file adds only concise Claude Code workflow guidance.

## Workflow

- Scan `docs/agent_codebase_map.md`, then read the closest `CLAUDE.md` / `AGENTS.md`.
- Work on one page or workflow at a time; do not search the whole repository before locating the relevant route, service, metric contract, or test.
- State material assumptions and ask only when ambiguity would materially change the result.
- Prefer the smallest implementation and avoid unrelated cleanup, speculative configuration, and one-use abstractions.
- Use targeted MCP/GitNexus evidence instead of loading large documents, datasets, or logs.

## Architecture boundaries

Preserve:

`frontend -> api -> services -> (repositories / core_finance / governance) -> storage`

- Official finance calculations belong only in `backend/app/core_finance/`.
- Frontend code must not recreate official finance metrics.
- API routes stay thin: validate, authorize, call services, and return responses.
- API/service DuckDB access is read-only; writes flow through tasks.
- Changes to H/A/T mapping, issued-bond exclusion, FX mid-price conversion, 514/516/517 merging, or Formal/Scenario separation require targeted tests and an impact report.

## Change discipline

- For a bug, reproduce it with the smallest useful test before fixing when practical.
- For a feature, define observable acceptance criteria before implementation.
- For a refactor, verify behavior equivalence before and after.
- Do not modify adjacent files, naming, formatting, or dead code unless the current change requires it.
- Follow the GitNexus impact and pre-commit change-detection rules in `AGENTS.md`.

## Validation and reporting

- Run the narrowest relevant tests/checks first and widen only for shared boundaries or demonstrated risk.
- Report changed files, test/check results, impact on formal finance paths, and remaining risks.
- If a command or evidence source is unavailable, say why and identify the residual risk.

## Design

Before changing interface layout, color, typography, or spacing, read `DESIGN.md` and use `frontend/src/theme/designSystem.ts` plus existing page-local primitives.
