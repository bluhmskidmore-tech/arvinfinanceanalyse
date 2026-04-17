# AGENTS.md

## Default Test Boundary

Tests under `tests/` may validate the current repo-wide `Phase 2` formal-compute mainline.

Allowed default test scope:
- formal balance
- formal PnL
- formal FX
- formal yield curve
- PnL bridge
- risk tensor
- core bond-analytics formal read surfaces
- outward `result_meta` / `basis` / lineage semantics for the above

Explicitly excluded from the current default test boundary:
- `executive.*` governed rollout beyond the currently landed stable surfaces
- Agent MVP / real `/api/agent/query` enablement
- `source_preview` / `macro-data` / `choice-news` / `market-data` preview/vendor/analytical expansion
- `qdb_gl_monthly_analysis`、`liability_analytics_compat` 等 analytical-only / compatibility 模块的范围扩张
- broad frontend rollout

Historical scoped overrides remain relevant for legacy or excluded streams, but should not be used to reinterpret the formal-compute mainline back to a `Phase 1`-only test boundary.
