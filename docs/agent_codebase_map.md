# MOSS Agent Codebase Map

Purpose: give coding agents a fast table of contents before opening files. This is navigation help only; business authority remains in `AGENTS.md`, `docs/DOCUMENT_AUTHORITY.md`, metric contracts, and the code/tests.

## First pass

| Area | Start here | Notes |
| --- | --- | --- |
| Project rules | `AGENTS.md`, `CLAUDE.md`, `CLAUDE.local.md` | Root discipline, user preferences, and task reporting shape. |
| Frontend app | `frontend/CLAUDE.md`, `frontend/src/router/routes.tsx`, `frontend/src/features/` | Pages, view models, adapters, mocks, and Vitest coverage. |
| Backend API | `backend/CLAUDE.md`, `backend/app/api/routes/`, `backend/app/services/` | FastAPI routes should stay thin; services coordinate domain work. |
| Formal finance logic | `backend/app/core_finance/` | Official metric calculation logic belongs here, not frontend or API routes. |
| Persistence and schema | `backend/app/repositories/`, `backend/app/schema_registry/duckdb/` | Read paths live in repositories; DuckDB writes flow through tasks. |
| Materialization tasks | `backend/app/tasks/`, `backend/scripts/`, `scripts/` | Data writes and backfills belong to task/script workflows. |
| Contracts and metric docs | `docs/page_contracts.md`, `docs/metric_dictionary.md`, `docs/calc_rules.md`, `docs/golden_sample_catalog.md` | Prefer MCP contract tools for targeted lookup instead of loading whole files. |
| MCP tooling | `docs/MCP_RUNBOOK.md`, `.codex/config.toml`, `.mcp.json`, `scripts/mcp/` | Read-only evidence servers for contracts, lineage, catalog, quality, and GitNexus. |
| Tests | `tests/CLAUDE.md`, `tests/`, `backend/tests/`, `frontend/src/test/` | Pick tests that match the changed page/workflow. |

## Common task entry points

| Task | Read first | Then trace |
| --- | --- | --- |
| Frontend metric/page bug | `frontend/src/router/routes.tsx`, relevant `frontend/src/features/<domain>/` | API client -> adapter/model -> component -> chart/table -> targeted tests. |
| Backend contract/API bug | Relevant route in `backend/app/api/routes/` | schema -> service -> repository/core_finance -> tests. |
| Business metric correctness | MCP page trace bundle or metric docs | API response -> adapter -> state/selector -> component; check unit/date/null/stale data. |
| Formal finance calculation | `backend/app/core_finance/<domain>.py` | service caller -> repository inputs -> golden tests. |
| Data lineage/fallback issue | `docs/MCP_RUNBOOK.md` | lineage MCP -> data catalog/quality MCP -> service/result metadata. |
| UI layout/design change | `DESIGN.md`, `frontend/src/theme/designSystem.ts` | page CSS/module -> component tests -> browser verification if visible behavior changes. |

## Noise to avoid first

Do not start exploration from generated or runtime-heavy directories unless the task explicitly needs them: `node_modules/`, `.venv/`, `dist/`, `build/`, coverage folders, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `artifacts/`, raw `data/`, raw `data_input/`, root logs, zips, and temporary `tmp*` / `.tmp*` directories.

For large logs, read a short tail only after the task is clearly a runtime/debugging task.
