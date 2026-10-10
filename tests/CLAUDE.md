# Test Agent Notes

Use this file for work under `tests/` and `backend/tests/`.

## Test selection

- Prefer the smallest test target that proves the changed page, workflow, adapter, service, or formula.
- For business metric work, include cases for units, precision, date semantics, `null` vs `0`, fallback/stale metadata, and golden samples when applicable.
- Use [tests/AGENTS.md](AGENTS.md) for markers and scope authorization. An existing task instruction covering an excluded legacy or analytical-only workflow applies to its necessary tests; it does not promote the workflow to formal financial truth.

## Verification

- Never invoke a bare `python`: on developer machines it is frequently shadowed by an unrelated venv.
  Use the repo interpreter — Windows `.\backend\.venv\Scripts\python.exe`, POSIX `backend/.venv/bin/python`. In CI the
  `uv sync --frozen` venv is prepended to `PATH`, which is why the workflow files can use plain `python`.
- From the repository root, run targeted pytest as `.\backend\.venv\Scripts\python.exe -m pytest tests/<target>.py -q`.
- For larger multi-file runs, `pytest-xdist` is available: add `-n 4` (or `-n auto`) to parallelize. Tests isolate DuckDB/sqlite state per test via `tmp_path`, so parallel workers are safe for the mainline suites; drop `-n` if a suite shows cross-test file contention.
- For the default MCP feedback loop, run `.\backend\.venv\Scripts\python.exe -m pytest -q -m mcp_fast tests/test_project_mcp_fast_contracts.py`; it uses isolated governance and DuckDB paths.
- Run `.\backend\.venv\Scripts\python.exe scripts\backend_release_suite.py --mcp-profile full` only when shared MCP behavior changes or when performing the scheduled/full release check.
- For frontend tests, run from `frontend/` with `npm run test -- <pattern>`.
- Keep fixtures small and explicit. Do not read raw `data/` files directly unless the task is about data ingestion or catalog validation.
