# AGENTS.md

## Default Backend Boundary

The default backend execution boundary is now `repo-wide Phase 2` for the governed formal-compute mainline.

This default applies to files under `backend/app/` only for these formal-compute chains:

- formal balance
- formal PnL
- formal FX
- formal yield curve
- PnL bridge
- risk tensor
- core bond-analytics formal read surfaces

For these chains, backend work no longer needs to rely on historical per-stream scoped overrides as its main authorization basis.

## Explicit Exclusions

The following backend surfaces are still outside the current repo-wide `Phase 2` cutover:

- `backend/app/api/routes/executive.py` except the E1 surfaces:
  - `/ui/home/overview`
  - `/ui/home/summary`
  - `/ui/pnl/attribution`
- `backend/app/services/executive_service.py` except:
  - `executive_overview`
  - `executive_summary`
  - `executive_pnl_attribution`
- `backend/app/api/routes/agent.py`
- Agent MVP / real agent query enablement
- `source_preview`
- `macro-data`
- `choice-news`
- market-data preview / vendor / analytical surfaces
- `qdb_gl_monthly_analysis`
- `liability_analytics_compat`
- cube-query and other `Phase 3 / Phase 4` style expansion items

Historical scoped overrides remain useful only for excluded or legacy streams. They should not be reinterpreted as limiting the formal-compute mainline back to `Phase 1`.

## Snapshot And Preview Semantics

- `zqtz_bond_daily_snapshot` and `tyw_interbank_daily_snapshot` remain standardized inputs, not outward formal source-of-truth results.
- Preview tables remain explanatory surfaces and must not become formal inputs.
- Formal-facing services and workbench consumers must continue reading governed formal facts rather than snapshot / preview shortcuts.

## Non-negotiable constraints

- Keep the existing architecture direction:
  `frontend -> api -> services -> (repositories / core_finance / governance) -> storage`
- API/service paths remain DuckDB read-only.
- All DuckDB writes continue to flow through `tasks/`.
- Formal finance logic still belongs only in `backend/app/core_finance/`.
