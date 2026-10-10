# MOSS Agent Codebase Map

Purpose: give coding agents a fast table of contents before opening files. This is navigation help only; business authority remains in `AGENTS.md`, `docs/DOCUMENT_AUTHORITY.md`, metric contracts, and the code/tests.

## First pass

| Area | Start here | Notes |
| --- | --- | --- |
| Project rules | `AGENTS.md`; `CLAUDE.md` for architecture boundaries; `CLAUDE.local.md` for local preferences | Reuse already-loaded instructions; follow only the references needed for this task. |
| Frontend app | `frontend/AGENTS.md`, `frontend/src/router/routes.tsx`, `frontend/src/features/` | Tiered page rules, view models, adapters, mocks, and Vitest coverage; `frontend/CLAUDE.md` is a compatibility entrypoint. |
| Backend API | `backend/CLAUDE.md`, `backend/app/api/routes/`, `backend/app/services/` | FastAPI routes should stay thin; services coordinate domain work. |
| Agent and governance | `backend/app/agent/`, `backend/app/governance/` | Agent runtime/tools and governance policy, lineage, locks, and settings. |
| Formal finance logic | `backend/app/core_finance/` | Official metric calculation logic belongs here, not frontend or API routes. |
| Persistence and schema | `backend/app/repositories/`, `backend/app/schema_registry/duckdb/` | Read paths live in repositories; DuckDB writes flow through tasks. |
| Materialization tasks | `backend/app/tasks/` | Governed DuckDB writes and registered materialization actors live here. |
| Operational scripts | `backend/scripts/`, `scripts/` | Existing backfill, diagnostics, release, and MCP entry points; verify a concrete script exists before citing it. |
| Contracts and metric docs | `docs/page_contracts.md`, `docs/metric_dictionary.md`, `docs/calc_rules.md`, `docs/golden_sample_catalog.md` | Prefer MCP contract tools for targeted lookup instead of loading whole files. |
| MCP tooling | `docs/MCP_RUNBOOK.md`, `.codex/config.toml`, `.mcp.json`, `scripts/mcp/` | Read-only evidence servers for contracts, lineage, catalog, quality, and GitNexus. |
| Management report templates | `docs/report-templates/management-book/`, `.codex/skills/moss-management-book/SKILL.md` | 1280x720 HTML decision books under `output/pdf/`; never fork styles from a previous report. |
| Tests | `tests/AGENTS.md`, `tests/CLAUDE.md`, `tests/`, `backend/tests/`, `frontend/src/test/` | Pick tests that match the changed page/workflow. |

## Common task entry points

| Task | Read first | Then trace |
| --- | --- | --- |
| Input data refresh / 全局更新 | `docs/data_update_center.md` §代理代办更新的执行约定 | Select report dates and scopes from changed sources; reuse the existing request and receipt workflow. |
| Work takeover / defect acceptance | `AGENTS.md`, `docs/acceptance_tests.md` §1.1–1.3 | Verify current code and runtime claims; select the affected regression cases; distinguish isolated tests, live behavior, and business reconciliation. |
| Dashboard home trace | `frontend/src/router/routes.tsx`, `frontend/src/features/workbench/dashboard-home/DashboardHomePage.tsx` | Start from `/ui/home/snapshot`, then trace `useDashboardSnapshotBoundary`, `dashboardHomeSnapshotAdapter`, and the first-screen view model; keep supplemental data gated by the snapshot report date. |
| Frontend metric/page bug | `frontend/src/router/routes.tsx`, relevant `frontend/src/features/<domain>/` | API client -> adapter/model -> component -> chart/table -> targeted tests. |
| Backend contract/API bug | Relevant route in `backend/app/api/routes/` | schema -> service -> repository/core_finance -> tests. |
| Business metric correctness | MCP page trace bundle or metric docs | API response -> adapter -> state/selector -> component; check unit/date/null/stale data. |
| Formal finance calculation | `backend/app/core_finance/<domain>.py` | service caller -> repository inputs -> golden tests. |
| Data lineage/fallback issue | `docs/MCP_RUNBOOK.md` | lineage MCP -> data catalog/quality MCP -> service/result metadata. |
| UI layout/design change | `DESIGN.md`, `frontend/src/theme/designSystem.ts` | page CSS/module -> component tests -> browser verification if visible behavior changes. |

## Noise to avoid first

Do not start exploration from generated or runtime-heavy directories unless the task explicitly needs them: `node_modules/`, `.venv/`, `dist/`, `build/`, coverage folders, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `artifacts/`, raw `data/`, raw `data_input/`, root logs, zips, and temporary `tmp*` / `.tmp*` directories.

For large logs, read a short tail only after the task is clearly a runtime/debugging task.
