# Gate J Route-Scope Classification

**Date:** 2026-06-06

**Command:** `python scripts/codex_page_readiness.py --route-scope`

**Purpose:** Prevent the seven-route flagship frontend claim from becoming an accidental whole-system or business-contract certification claim.

## Verdict

No route is currently `business-contract-certified`.

Allowed claim:

> MOSS has strong flagship frontend surfaces and controlled business-contract closure lanes. Full top-investment-bank business certification is still open and route-scoped.

Forbidden claim:

> MOSS, or any route below, is top-investment-bank business-certified.

The certification blocker is not visual polish. The blocker is missing direct golden approval, manual audit closure, captured business-owner approval, or route-specific Gate I evidence.

## Summary

| Measure | Count |
| --- | ---: |
| Total classified routes | 39 |
| Seeded trace bundles | 39 |
| Visible navigation routes | 36 |
| Visible routes without seeded trace bundles | 0 |
| `business-contract-certified` | 0 |
| `evidence-pending` | 23 |
| `gate-i-gap` | 0 |
| `frontend-ready` | 6 |
| `frontend-only` | 10 |
| `not-started` | 0 |
| `out-of-scope` | 0 |
| Unclassified | 0 |

## Classification Definitions

| Classification | Meaning |
| --- | --- |
| `business-contract-certified` | Static readiness passes, direct golden approval is non-placeholder, manual audit is closed, and business-owner approval is captured. |
| `evidence-pending` | A page has a trace bundle or candidate/formal evidence, but at least one certification gate remains open. |
| `gate-i-gap` | The route is visible or seeded but lacks a direct route-specific Gate I certification lane. |
| `frontend-ready` | The route has frontend/browser readiness evidence, but it is an analytical or mixed-source surface, not formal business truth. |
| `frontend-only` | The route is a home, summary, operational, or support surface and must not be used as page certification. |
| `not-started` | The visible route has no seeded trace bundle in the current readiness ledger. |
| `out-of-scope` | The route is intentionally outside the current business certification scope. |

## Route Ledger

| Route slug | Frontend route | Classification | Blocking reason | Run-supported | Visible nav | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `product-category-pnl` | `/product-category-pnl` | `evidence-pending` | `business_owner_approval_pending` | yes | yes | seeded trace bundle |
| `dashboard-home` | `/` | `frontend-ready` | `analysis_surface_not_formal_business_truth` | yes | yes | seeded trace bundle |
| `executive-overview` | `/dashboard` | `frontend-only` | `home_or_summary_surface_not_page_certification` | no | no | seeded trace bundle |
| `executive-summary` | `/dashboard` | `frontend-only` | `home_or_summary_surface_not_page_certification` | no | no | seeded trace bundle |
| `balance-analysis` | `/balance-analysis` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | yes | yes | seeded trace bundle |
| `average-balance` | `/average-balance` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | yes | yes | seeded trace bundle |
| `bank-ledger-dashboard` | `/bank-ledger-dashboard` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | yes | yes | seeded trace bundle |
| `cashflow-projection` | `/cashflow-projection` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | yes | yes | seeded trace bundle |
| `concentration-monitor` | `/concentration-monitor` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | yes | yes | seeded trace bundle |
| `decision-items` | `/decision-items` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | yes | yes | seeded trace bundle |
| `balance-movement-analysis` | `/balance-movement-analysis` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | yes | yes | seeded trace bundle |
| `pnl` | `/pnl` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | yes | yes | seeded trace bundle |
| `ledger-pnl` | `/ledger-pnl` | `evidence-pending` | `business_owner_approval_pending` | yes | yes | seeded trace bundle |
| `pnl-by-business` | `/pnl-by-business` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | no | yes | seeded trace bundle |
| `executive-pnl-attribution` | `/dashboard` | `frontend-only` | `home_or_summary_surface_not_page_certification` | no | no | seeded trace bundle |
| `pnl-attribution` | `/pnl-attribution` | `evidence-pending` | `business_owner_approval_pending` | yes | yes | seeded trace bundle |
| `operations-analysis` | `/operations-analysis` | `frontend-ready` | `analysis_surface_not_formal_business_truth` | yes | yes | seeded trace bundle |
| `liability-analytics` | `/liability-analytics` | `frontend-ready` | `analysis_surface_not_formal_business_truth` | yes | yes | seeded trace bundle |
| `pnl-bridge` | `/pnl-bridge` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | yes | yes | seeded trace bundle |
| `risk-tensor` | `/risk-tensor` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | yes | yes | seeded trace bundle |
| `bond-dashboard` | `/bond-dashboard` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | yes | yes | seeded trace bundle |
| `bond-analysis` | `/bond-analysis` | `evidence-pending` | `business_owner_approval_pending` | yes | yes | seeded trace bundle |
| `positions` | `/positions` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | yes | yes | seeded trace bundle |
| `market-data` | `/market-data` | `frontend-ready` | `analysis_surface_not_formal_business_truth` | yes | yes | seeded trace bundle |
| `stock-analysis` | `/stock-analysis` | `evidence-pending` | `business_owner_approval_pending` | yes | yes | seeded trace bundle |
| `macro-toolkit` | `/macro-toolkit` | `frontend-ready` | `analysis_surface_not_formal_business_truth` | yes | yes | seeded trace bundle |
| `macro-observation` | `/macro-observation` | `frontend-only` | `home_or_summary_surface_not_page_certification` | no | yes | seeded trace bundle |
| `agent` | `/agent` | `frontend-only` | `home_or_summary_surface_not_page_certification` | no | yes | seeded trace bundle |
| `cube-query` | `/cube-query` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | no | yes | seeded trace bundle |
| `portfolio-home` | `/portfolio` | `frontend-only` | `home_or_summary_surface_not_page_certification` | no | yes | seeded trace bundle |
| `market-home` | `/market-overview` | `frontend-only` | `home_or_summary_surface_not_page_certification` | no | yes | seeded trace bundle |
| `risk-home` | `/risk-overview` | `frontend-only` | `home_or_summary_surface_not_page_certification` | no | yes | seeded trace bundle |
| `performance-home` | `/performance` | `frontend-only` | `home_or_summary_surface_not_page_certification` | no | yes | seeded trace bundle |
| `reports-home` | `/reports` | `frontend-only` | `home_or_summary_surface_not_page_certification` | no | yes | seeded trace bundle |
| `cross-asset` | `/cross-asset` | `frontend-ready` | `analysis_surface_not_formal_business_truth` | yes | yes | seeded trace bundle |
| `team-performance` | `/team-performance` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | yes | yes | seeded trace bundle |
| `platform-config` | `/platform-config` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | yes | yes | seeded trace bundle |
| `kpi-performance` | `/kpi` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | yes | yes | seeded trace bundle |
| `news-events` | `/news-events` | `evidence-pending` | `golden_or_manual_audit_or_owner_approval_pending` | yes | yes | seeded trace bundle |

## Priority Queues

### Evidence-Pending

These routes already have candidate or formal evidence, but cannot be certified until direct golden approval, manual audit closure, and business-owner approval are all resolved as applicable:

- `product-category-pnl`
- `balance-analysis`
- `average-balance`
- `bank-ledger-dashboard`
- `cashflow-projection`
- `concentration-monitor`
- `decision-items`
- `balance-movement-analysis`
- `pnl`
- `ledger-pnl`
- `pnl-by-business`
- `team-performance`
- `pnl-attribution`
- `pnl-bridge`
- `risk-tensor`
- `bond-dashboard`
- `bond-analysis`
- `positions`
- `stock-analysis`
- `cube-query`
- `platform-config`
- `kpi-performance`
- `news-events`

### Gate I Gap

No visible seeded route currently lacks a direct Gate I lane.

- None

### Visible Routes Without Seeded Trace Bundles

No visible navigation route is currently missing a seeded trace bundle.

- None

## Next Actions

1. Close the first true certification candidate: `/product-category-pnl`.
   - Reconcile `GS-PROD-CAT-PNL-A/approval.md`.
   - Close or explicitly retain the 10 partial checklist units.
   - Capture real business-owner approval only through the strict checker path.

2. Keep `/ledger-pnl` and `/pnl-attribution` in `evidence-pending`.
    - Do not promote either page from dry-run or DTO-only evidence.
   - Treat `GS-LEDGER-PNL-SUMMARY-A` as capture-ready pending approval, not as certified formal use.
    - Keep governance writes authorization-safe.
    - Use approval checkers as blockers, not certification generators.

3. Keep `/bond-analysis` in `evidence-pending`.
   - Treat `GS-BOND-ANALYSIS-ACTION-ATTR-A` as capture-ready page DTO evidence only.
   - Do not borrow `/bond-dashboard` evidence or promote fixed-income formulas without owner/golden/manual audit closure.

4. Keep `/stock-analysis` in `evidence-pending`.
   - Treat `GS-STOCK-ANALYSIS-OBS-A` as capture-ready observational DTO evidence only.
   - Do not turn stock-analysis observations into trading-instruction or formal metric claims.

5. Keep newly seeded candidate, diagnostic, and analytical routes in `evidence-pending`.
   - `/average-balance` is now seeded as a candidate ADB analytical lane.
   - `/bank-ledger-dashboard` is now seeded as a candidate ledger read-model lane for `/api/ledger/dashboard`; it has no golden sample, no standalone PAGE/MTR approval, and is not formal PnL or formal balance truth.
   - `/cashflow-projection` is now seeded as a candidate liquidity projection lane for `/api/cashflow-projection`; it has no golden sample, no standalone PAGE/MTR approval, and is not formal liquidity, risk, balance, or PnL truth.
   - `/concentration-monitor` is now seeded as a candidate concentration-monitor lane for `/api/bond-analytics/credit-spread-migration`; it has no golden sample, no standalone PAGE/MTR approval, and is not formal risk truth or certified concentration-limit approval.
   - `/team-performance` is now seeded as a candidate team-performance mapping lane for `/api/pnl/by-business-ytd` with product-category context; it has no golden sample, no standalone PAGE/MTR approval, and is not formal KPI truth, formal PnL truth, or owner-approved performance allocation.
   - `/platform-config` is now seeded as a candidate diagnostics lane for `/ui/preview/source-foundation` and health endpoints; it has no golden sample, no standalone approval, and is not data-quality approval.
   - `/news-events` is now seeded as an analytical event-context lane for `/ui/news/choice-events/latest`; it has no formal `MTR-NEWS-*` metric, no golden sample, no standalone approval, and is not business truth, trading instruction, or source data-quality approval.

## Verification

Fresh checks to rerun after changing the classification logic:

```powershell
python scripts/codex_page_readiness.py --route-scope
python scripts/codex_page_readiness.py --all
python -m pytest tests/test_codex_page_readiness_gate.py -q
```

## Boundaries

- This document does not approve any golden sample.
- This document does not capture business-owner approval.
- This document does not write governance records.
- This document does not change `formal_use_allowed`.
- This document does not change metric definitions, units, precision, dates, or formulas.

## Backend API Router Grouping Boundary

Current backend route registration is grouped in `backend/app/api/__init__.py` through `ROUTE_REGISTRY` and `ROUTE_GROUP_METADATA`.
The controlled route groups are `formal_mainline`, `preview`, `macro_market`, `agent_experimental`, and `support`.

- `formal_mainline`: governed business workflow routes; registration alone is not route certification.
- `preview`: source preview and source-inspection routes; not formal business certification.
- `macro_market`: macro, market, vendor-data, and decision-support routes; not books-and-records truth or trading instructions.
- `agent_experimental`: agent workbench and external-provider surfaces; requires tool isolation, evidence strength separation, and confirmation-token controls.
- `support`: health, dashboard, query, executive-support, and operational surfaces; not standalone metric certification.

Route grouping is a classification and risk-boundary control only. Moving a route between groups, adding a new route module, or claiming a route is formal requires route-specific page contracts, metric dictionary alignment, source lineage evidence, and owner approval.

## Repository Writer Task Scope Boundary

High-risk repository writers now require an explicit task write scope at runtime. The current guarded writers are:

- `backend.app.repositories.cffex_member_rank_repo.replace_member_rank_rows`
- `backend.app.repositories.news_warehouse_repo.upsert_news_event`
- `backend.app.repositories.news_warehouse_repo.purge_expired_news_events`
- `backend.app.repositories.news_warehouse_repo.backfill_from_choice_news_event`

Only `backend.app.tasks.*` code may open `repository_task_write_scope(...)`; API and service modules must keep delegating these writes to task modules. The guard is intentionally runtime-enforced, not only documented, so accidental service-layer or route-layer direct writer calls fail closed.

Verification anchors:

- `tests/test_repository_task_write_guard.py`
- `tests/test_service_storage_boundaries.py::test_api_and_service_layers_do_not_open_repository_task_write_scope`
- `tests/test_tushare_news_ingest.py`

## Frontend WSL Optional Dependency Boundary

The native frontend startup script repairs the WSL/Linux Vite/Rolldown optional native binding before starting dev mode. `scripts/dev-frontend.ps1` now checks `process.platform`, verifies `@rolldown/binding-linux-x64-gnu` through `require.resolve(...)`, and runs `npm install --include=optional` only when the Linux binding is missing.

This keeps the Windows native path unchanged while preventing WSL/Linux dev startup from failing because npm optional dependencies were installed under a different platform.

Verification anchor:

- `tests/test_native_dev_script_contents.py::test_dev_frontend_repairs_missing_wsl_rolldown_binding`
