# AGENTS.md

## Default Backend Boundary

For work under `backend/app/`, use [DOCUMENT_AUTHORITY.md — 阶段边界规则](../../docs/DOCUMENT_AUTHORITY.md#阶段边界规则) for the default formal-compute scope and authorization rules. These mainline chains do not require historical per-stream overrides.

## Explicit Exclusions

The [current surface boundaries](../../docs/DOCUMENT_AUTHORITY.md#current-surface-boundaries) distinguish included executive E1 routes, reserved routes, and landed query/analytical compatibility surfaces. An open compatibility endpoint does not promote it to formal financial truth. Use the task's existing authorization for scoped work; do not infer broader feature enablement from route availability.

In `executive_service.py`, E1 implementation includes `executive_overview`, `executive_summary`, `executive_pnl_attribution`, and the `/ui/home/snapshot` helpers `home_snapshot_envelope`, `_compute_home_snapshot_envelope`, and `_build_product_category_ytd_headline`. The snapshot uses `product_category_pnl_service.resolve_product_category_ytd_payload_for_home_snapshot` to recompute from canonical facts when the read model lacks YTD data.

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
