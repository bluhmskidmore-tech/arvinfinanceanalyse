# Test Agent Notes

Use this file for work under `tests/` and `backend/tests/`.

## Test selection

- Prefer the smallest test target that proves the changed page, workflow, adapter, service, or formula.
- For business metric work, include cases for units, precision, date semantics, `null` vs `0`, fallback/stale metadata, and golden samples when applicable.
- Respect `tests/AGENTS.md`; do not expand excluded legacy or analytical-only surfaces unless the current task explicitly enters that scope.

## Verification

- From the repository root, run targeted pytest as `python -m pytest tests/<target>.py -q`.
- For larger multi-file runs, `pytest-xdist` is available: add `-n 4` (or `-n auto`) to parallelize. Tests isolate DuckDB/sqlite state per test via `tmp_path`, so parallel workers are safe for the mainline suites; drop `-n` if a suite shows cross-test file contention.
- For the default MCP feedback loop, run `python -m pytest -q -m mcp_fast tests/test_project_mcp_fast_contracts.py`; it uses isolated governance and DuckDB paths.
- Run `python scripts/backend_release_suite.py --mcp-profile full` only when shared MCP behavior changes or when performing the scheduled/full release check.
- For frontend tests, run from `frontend/` with `npm run test -- <pattern>`.
- Keep fixtures small and explicit. Do not read raw `data/` files directly unless the task is about data ingestion or catalog validation.
