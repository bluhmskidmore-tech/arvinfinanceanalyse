# Business Closure Optimization Audit - 2026-05-16

Role: execution checklist only. This document does not define metrics, page contracts, or data authority.

Authority remains: `AGENTS.md` -> `docs/DOCUMENT_AUTHORITY.md` -> `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md` -> page contracts / MCP evidence for the specific page.

## Current Guard Baseline

- Frontend debt guard: keep `npm run debt:audit` at or below the current baseline.
- Finance logic guards: route/API/frontend display code may show backend-provided labels and values, but formal calculation terms must stay out of API routing logic and frontend computation.
- MCP availability guard: `tests/test_project_mcp_servers.py` is the basic server availability check. For any concrete metric-page change, query the relevant MCP server before deciding implementation shape.
- Public interface rule: no route, parameter, response shape, database schema, auth, queue, cache, or app-wide state change is part of this optimization slice.

## Phase 2 Mainline Closure Queue

| Route / workflow | Primary business question | Source and model trace to verify | Display closure checks | Smallest next action |
| --- | --- | --- | --- | --- |
| `/` executive cockpit | What is the management conclusion today? | Dashboard API -> cockpit model -> section components | no data, stale/fallback date, blocked sections, cross-page drilldowns | Verify all first-screen metrics have source/date/status text and one targeted model test. |
| `/pnl` | What drove current period PnL? | PnL API -> page model -> KPI/cards/tables | unit, precision, null vs 0, formal-vs-placeholder table status | Reconcile visible KPI definitions against contracts before any UI cleanup. |
| `/pnl-bridge` | How did balance/rate/curve effects bridge PnL? | bridge API -> adapter/model -> chart/table | curve fallback warning, report/prior dates, missing curve data | Keep fallback warning single-sourced and add a focused regression if changed. |
| `/pnl-attribution` | Which market/rate/spread effects explain PnL? | attribution API -> service envelope -> attribution view | date default, available-date copy, no API-layer formula text | Keep route thin; service owns semantics. |
| `/risk-tensor` | What is the current governed risk exposure? | risk tensor API -> page model -> KPI/control deck | backend-provided DV01, limit unavailable, stale/fallback evidence | Do not infer limits in frontend; surface pending configuration explicitly. |
| `/balance-analysis` | What is the governed balance sheet position? | balance API -> page model -> tables/charts | unit consistency, stale/fallback date, decision items | Pay down inline-style debt only inside page-local primitives. |
| `/balance-movement-analysis` | Which accounting categories moved and why? | movement API -> page model -> movement views | report/prior dates, controlled account visibility, no-data | Keep CNX control-account semantics backed by backend/test evidence. |
| `/bond-analysis` | What is the governed bond portfolio picture? | bond analytics API -> model -> cockpit/modules | module readiness, no-data, backend-provided risk labels | Treat DV01/KRD/CS01 changes as high-risk contract changes. |
| `/bond-dashboard` | What is the bond overview conclusion? | bond dashboard API -> component panels | empty portfolio, stale headline, rating/spread buckets | Verify pie/table/chart units before visual cleanup. |
| `/positions` | What positions are visible and governed? | positions API -> formatter -> table | empty table, source date, currency/unit formatting | Keep formatter tests as the first edit point. |

## Live Routes Outside The First Closure Queue

These routes are live or temporarily visible, but should not pull the system into broad refactor work unless their specific page is selected.

| Route / workflow | Current handling |
| --- | --- |
| `/product-category-pnl`, `/pnl-by-business`, `/pnl-formal-v1` | Business PnL surfaces; touch only with contract-backed PnL evidence and targeted tests. |
| `/ledger-pnl`, `/bank-ledger-dashboard`, `/average-balance`, `/liability-analytics` | Read-model surfaces; keep compatibility wording explicit and avoid new frontend aggregation logic. |
| `/cashflow-projection`, `/concentration-monitor` | Risk-support views; verify backend ownership of calculations before display edits. |
| `/cross-asset`, `/market-data`, `/macro-toolkit`, `/stock-analysis`, `/news-events` | Market / analytical surfaces; do not promote preview semantics into Phase 2 formal mainline by cleanup alone. |
| `/operations-analysis`, `/decision-items`, `/team-performance`, `/kpi`, `/platform-config`, `/agent` | Temporary or operational surfaces; keep changes page-local and evidence-led. |

## Page Slice Definition Of Done

- State the single page/workflow being fixed and the first files inspected.
- Trace each displayed metric through API response -> adapter/model -> state/selector -> component -> chart/table.
- Check units, precision, Decimal/string/number handling, `null` vs `0`, report date, fallback date, stale flag, mock fallback, and no-data/error display.
- Add the smallest useful formatter, adapter/model, selector, component, service, or contract test for the changed behavior.
- Run the narrowest relevant test first, then `npm run debt:audit` for frontend page/API/model changes, and backend release suite only for cross-mainline backend changes.

## Debt Reduction Rules During Closure

- Do not grow `frontend/src/api/client.ts`; move endpoint work into domain clients.
- Do not add repeated inline layout styles; use page-local CSS/modules or existing primitives when touching the page anyway.
- Do not split large services or pages just because they are large. Extract only when the current page slice has an immediate duplicate or testability problem.
- Do not touch schema/auth/queue/cache/global wrappers/global state unless direct evidence shows they are the root cause.
