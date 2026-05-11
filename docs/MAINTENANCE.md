# MOSS-V3 Maintenance

This note records the current maintenance boundary for local development cleanup
and task parallelism. It does not authorize business metric, API, schema, cache,
or worker architecture changes.

## Development Artifact Cleanup

Use `scripts/cleanup-dev-artifacts.ps1` from the repository root.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cleanup-dev-artifacts.ps1
```

The default mode is a dry-run. It lists old development artifacts and deletes
nothing. Pass `-Apply` only after reviewing the candidate list.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cleanup-dev-artifacts.ps1 -Apply
```

Default cleanup keeps the most recent 7 days and targets local verification
artifacts such as `.codex-tmp/pytest-*`, `.pytest-tmp*`, pytest/ruff/mypy
caches, `__pycache__`, `test_output`, `frontend/test-results`, and old root or
frontend `.log` files. Screenshot `.png` files are not included by default; use
`-IncludeScreenshots` to include old root and frontend screenshots with a
14-day retention window.

The cleanup script protects business inputs and evidence. It must not remove
`data/`, `data_input/`, `tmp-governance/`, `.git/`, `.omx/`, `.gitnexus/`,
`.venv/`, `node_modules/`, or candidate directories that contain DuckDB, CSV,
Parquet, Excel, SQLite, WAL, pickle, or governance JSONL files.

## Parallelism Boundary

Do not raise the default `MOSS_DEV_WORKER_PROCESSES` value from 1 as a broad
optimization. Keep the existing rule that DuckDB writes flow through
`backend/app/tasks/`; API and service paths remain read-oriented for business
surfaces.

Safe parallel lanes:

- Read-only checks and static audits.
- Frontend tests and type checks.
- Network/vendor fetches that do not write the same fact table or cache
  identity.
- Non-writing preview and diagnostics.

Serial or explicitly locked lanes:

- Formal materialize jobs.
- DuckDB writes.
- `cache_manifest` and cache-version publication.
- Lineage and governance writes.

Future throughput work should use queue separation instead of global worker
expansion: a `read/vendor queue` may scale out, while the
`materialize/write queue` stays single-writer or uses an explicit write lock.
