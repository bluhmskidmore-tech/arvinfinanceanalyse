# Architecture

## System Shape

The system is a modular monolith with a layered analytics stack:

`frontend -> api -> services -> (repositories / core_finance / governance) -> storage`

Its system body is `Agent 可调用的分析操作系统`. Dashboards, analyst pages, management surfaces, and Agent experiences are consumers of the same governed analysis substrate.

## Compute Boundary

Formal finance logic exists only in `backend/app/core_finance/`.

- `api/` handles validation, auth, thin orchestration, and response mapping
- `services/` orchestrate reads, lineage, cache/runtime state, and envelopes
- `repositories/` isolate storage/vendor access
- `tasks/` are the only write path into DuckDB materialized formal facts
- `governance/` owns versions, manifests, run records, approvals, and audit semantics

## Storage Roles

- PostgreSQL: governance, mappings, approvals, manifests, audits, run records
- DuckDB: governed facts, read models, and materialized analytics cache
- Redis: queueing, hot cache, locks
- MinIO / S3: raw files, exports, archived source/vendor snapshots

## Current Default Boundary

The current default execution boundary is `repo-wide Phase 2 (通用正式计算)` for the formal-compute mainline only.

Included chains:

- formal balance
- formal PnL
- formal FX
- formal yield curve
- PnL bridge
- risk tensor
- core bond-analytics formal read surfaces

Executive consumer overlay currently included:

- `/ui/home/overview`
- `/ui/home/summary`
- `/ui/pnl/attribution`

Excluded from this cutover:

- the rest of `executive.*`
- Agent MVP / real `/api/agent/query` enablement
- `source_preview` / `macro-data` / `choice-news` / `market-data` preview/vendor/analytical surfaces
- `qdb_gl_monthly_analysis`
- `liability_analytics_compat`
- cube-query and other later-phase expansion items

## Data Interpretation

- standardized snapshots and governed vendor slices are canonical inputs
- formal facts are the formal source of truth for included chains
- excluded consumers may remain placeholder, analytical-only, or fail-closed
- included executive consumer overlays are management-layer read surfaces, not formal source-of-truth result families
- a landed formal-compute chain does not imply every management or workbench surface is in scope

## Governing Docs

For boundary and execution interpretation, follow:

- `AGENTS.md`
- `docs/DOCUMENT_AUTHORITY.md`
- `docs/REPO_WIDE_PHASE2_CUTOVER_DEFINITION.md`
