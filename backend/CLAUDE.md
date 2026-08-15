# Backend Agent Notes

Use this file for work under `backend/`.

## Navigation

- Route handlers live in `app/api/routes/` and should stay thin.
- Request/response contracts live in `app/schemas/`.
- Business orchestration lives in `app/services/`.
- Read access belongs in `app/repositories/`.
- Official finance calculations belong only in `app/core_finance/`.
- DuckDB schema definitions live in `app/schema_registry/duckdb/`.
- DuckDB writes and materialization flows belong in `app/tasks/` or explicit scripts.

## Boundaries

- Keep the architecture direction: frontend -> api -> services -> repositories/core_finance/governance -> storage.
- API and service paths should be read-only with respect to DuckDB.
- Do not move formula logic into API routes or frontend helpers.
- For metric definitions, lineage, source version, fallback/stale status, or available report dates, use the project MCP servers documented in `../docs/MCP_RUNBOOK.md`.

## Verification

- Use the repo venv explicitly; a bare `python` is often shadowed by an unrelated venv on developer
  machines (Windows: `.\.venv\Scripts\python.exe`, POSIX: `.venv/bin/python`). A shadowing venv that
  happens to have pytest installed will report green against a different dependency set.
- From the repository root, run the narrowest relevant pytest target first:
  `.\.venv\Scripts\python.exe -m pytest tests/<target>.py -q` or
  `.\.venv\Scripts\python.exe -m pytest backend/tests/<target>.py -q`.
- Add or update focused tests when changing adapters, schemas, services, repositories, or `core_finance` calculations.
- Use wider backend release checks only after cross-cutting changes.
