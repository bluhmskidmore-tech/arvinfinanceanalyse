# Stock Analysis Workbench API Contract

Date: 2026-07-16

Route: `/stock-analysis`

Primary endpoint: `GET /ui/market-data/stock-analysis/workbench`

Status: implemented, observational only; governance closure pending

## Plain Answer

这页最好先让后端给前端一个“整理好的盒子”。

前端不要再自己到处拼很多接口来回答首屏问题。后端应该一次告诉页面：

- 今天观察日是哪天。
- 市场门控是冷、温和还是可观察。
- 当前最该复核哪几只股票。
- 为什么它们进入复核队列。
- 证据够不够，哪里缺口最大。
- 哪些模块是真有数据，哪些只是暂时不可用。

这个接口不做交易指令，不写数据库，不改变股票策略算法。它只是把现有 Livermore / Choice 只读结果包装成页面能直接读懂的工作台数据。

## Business Question

`/stock-analysis` 第一屏要先回答一个问题：

> 今天 A 股观察工作台能不能继续复核候选股？如果能，先看谁；如果不能，卡在哪里？

它不是正式投资建议页，也不是已认证交易指标页。现有治理口径里，`docs/audits/2026-06-06-stock-analysis-gate-i-lane.md` 已明确该页是 observational only，不能升级成正式交易指令或已认证业务指标。

## Scope Exclusions

本契约不触碰：

- 数据库 schema。
- 认证、权限框架。
- 队列、调度、缓存底座。
- Choice / Tushare 凭据与权限。
- 自动交易、调仓、下单、买卖建议。
- `frontend/src/api/client.ts` 的通用客户端扩张。
- 现有 `/ui/market-data/livermore/*` 明细接口的删除或重命名。

## Evidence Used

Local code and docs inspected:

- `frontend/src/router/routes.tsx`
- `frontend/src/api/marketDataClient.ts`
- `frontend/src/api/contracts.ts`
- `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
- `frontend/src/features/stock-analysis/pages/StockAnalysisPageImpl.tsx`
- `frontend/src/features/stock-analysis/lib/stockAnalysisWorkbenchQueueModel.ts`
- `frontend/src/features/stock-analysis/components/StockDetailDrawer.tsx`
- `frontend/src/features/stock-analysis/hooks/useSectorRankSeriesSupport.ts`
- `backend/app/api/routes/market_data_livermore.py`
- `backend/app/services/stock_analysis_workbench_service.py`
- `backend/app/services/market_data_livermore_service.py`
- `docs/plans/2026-05-06-stock-analysis-workbench.md`
- `docs/handoff/2026-05-06-stock-analysis-workbench-codex.md`
- `docs/audits/2026-06-06-stock-analysis-gate-i-lane.md`

Governance evidence:

- The local `moss-metric-contracts` provider now exposes this document and resolves the workbench endpoint to `GAP-STOCK-ANALYSIS-PAGE`.
- The local `moss-lineage-evidence` query expansion includes the workbench endpoint, result kind, rule version, and cache version.
- `moss-data-catalog` remains bound to the four underlying observational tables; no new formal table or metric binding is claimed.
- GitNexus impact evidence was checked before changing the shared reader and contract provider paths.

These records provide route and evidence discoverability only. They do not create `PAGE-STOCK-*`, `MTR-STOCK-*`, formal use, trading approval, or business-owner approval.

Live API note:

- The page at `http://localhost:5888/stock-analysis` renders its first-screen business state from the workbench endpoint.
- A live `GET /ui/market-data/stock-analysis/workbench?top_k=10` read returned HTTP 200 and preserved `formal_use_allowed=false`.
- Heavy diagnostics remain deferred behind explicit include/detail paths, and deep research content mounts lazily in the browser.

## Current Data Path

Existing frontend path:

1. `StockAnalysisPage.tsx` lazy-loads `StockAnalysisPageImpl.tsx`.
2. TanStack Query calls `marketDataClient.getStockAnalysisWorkbench(...)`.
3. `GET /ui/market-data/stock-analysis/workbench` enters `market_data_livermore.py`.
4. `stock_analysis_workbench_service.py` composes the page envelope from the underlying Livermore strategy envelope.
5. `stockAnalysisWorkbenchQueueModel.ts` and page-local selectors render the first-screen decision, queue, status, and evidence boundaries.
6. Existing Livermore detail endpoints remain lazy drilldowns for stock detail and deeper diagnostics.

Existing endpoint map:

| Frontend method | Backend path | Current role |
| --- | --- | --- |
| `getStockAnalysisWorkbench` | `/ui/market-data/stock-analysis/workbench` | Primary first-screen decision, review queue, status, evidence, and module boundaries |
| `getLivermoreStrategy` | `/ui/market-data/livermore` | Main market gate, sector rank, candidates, diagnostics, data gaps |
| `getLivermoreSignalConfluence` | `/ui/market-data/livermore/signal-confluence` | Signal confluence, macro/adversarial/replay evidence |
| `getLivermoreSectorRankSeries` | `/ui/market-data/livermore/sector-rank-series` | Sector trend and fallback rows |
| `getLivermoreStrategyScore` | `/ui/market-data/livermore/strategy-score` | Strategy priority diagnostics |
| `getLivermoreStrategyOptimization` | `/ui/market-data/livermore/strategy-optimization` | Strategy optimization diagnostics |
| `getLivermoreCandidateHistory` | `/ui/market-data/livermore/candidate-history` | Candidate replay/history and drawer history |
| `getLivermoreCycleProxyBacktest` | `/ui/market-data/livermore/cycle-proxy-backtest` | Cycle proxy backtest |
| `getLivermoreCandidateHistoryPortfolioBacktest` | `/ui/market-data/livermore/candidate-history-portfolio-backtest` | Portfolio proxy backtest |
| `getLivermoreStockDetail` | `/ui/market-data/livermore/stock-detail` | Drawer-only stock detail |

The workbench endpoint is the page primary source. It intentionally does not replace drilldowns; stock detail and heavy diagnostics remain separate lazy reads.

## Implemented Endpoint

```http
GET /ui/market-data/stock-analysis/workbench?as_of_date=2026-06-26&include=main,signal_confluence
```

Parameters:

| Name | Type | Default | Notes |
| --- | --- | --- | --- |
| `as_of_date` | `YYYY-MM-DD` | latest resolved date | Must preserve requested date and resolved date separately |
| `include` | comma-separated keys | `main,evidence_summary` | Optional heavy modules stay deferred/lazy |
| `sector_window_days` | integer | `20` | Used only when `sector_rank_series` is included |
| `top_k` | integer | `10` | Used for compact page summaries |

Default include set:

- `main`
- `evidence_summary`

Lazy include keys:

- `signal_confluence`
- `sector_rank_series`
- `strategy_score`
- `strategy_optimization`
- `candidate_history_backtest`
- `cycle_proxy_backtest`
- `portfolio_backtest`

Excluded from this endpoint:

- Stock detail drawer. Keep using `/ui/market-data/livermore/stock-detail`.
- News detail drawer. Keep using the existing news/event client path.
- Position materialization writes.

## Response Shape

```ts
type StockAnalysisWorkbenchEnvelope = {
  result: StockAnalysisWorkbenchPayload;
  result_meta: WorkbenchResultMeta;
};

type StockAnalysisWorkbenchPayload = {
  page_id: "GAP-STOCK-ANALYSIS-PAGE";
  route: "/stock-analysis";
  basis: "analytical";
  contract_status: "observational_only";
  formal_use_allowed: false;

  requested_as_of_date: string | null;
  as_of_date: string | null;
  fallback_date: string | null;
  stale: boolean;

  page_question: {
    question: string;
    answer_state: "review_ready" | "limited_review" | "blocked" | "no_data";
    answer_label: string;
    reason: string;
  };

  decision_summary: {
    gate_state: string | null;
    gate_label: string;
    can_review_candidates: boolean;
    top_review_stock_code: string | null;
    top_review_stock_name: string | null;
    review_queue_count: number;
    evidence_closure_label: string;
    primary_blocker: string | null;
  };

  data_status: {
    quality_flag: string | null;
    vendor_status: string | null;
    fallback_mode: string | null;
    source_version: string | null;
    rule_version: string | null;
    cache_version: string | null;
    tables_used: string[];
    evidence_rows: number | null;
  };

  first_screen: {
    market_gate: unknown | null;
    review_queue: unknown[];
    sector_snapshot: unknown[];
    risk_exit_snapshot: unknown[];
    data_gaps: unknown[];
    diagnostics: unknown[];
    supported_outputs: string[];
    unsupported_outputs: string[];
  };

  modules: {
    main: WorkbenchModule<unknown>;
    signal_confluence?: WorkbenchModule<unknown>;
    sector_rank_series?: WorkbenchModule<unknown>;
    strategy_score?: WorkbenchModule<unknown>;
    strategy_optimization?: WorkbenchModule<unknown>;
    candidate_history_backtest?: WorkbenchModule<unknown>;
    cycle_proxy_backtest?: WorkbenchModule<unknown>;
    portfolio_backtest?: WorkbenchModule<unknown>;
  };

  endpoint_evidence: EndpointEvidenceItem[];
  issues: WorkbenchIssue[];
  links: WorkbenchLinks;
};

type WorkbenchModule<T> = {
  key: string;
  status: "ready" | "deferred" | "missing" | "error" | "unsupported" | "stale";
  result: T | null;
  summary: Record<string, unknown>;
  meta: WorkbenchResultMeta;
  issues: WorkbenchIssue[];
};

type WorkbenchResultMeta = {
  trace_id: string | null;
  source_version: string | null;
  rule_version: string | null;
  cache_version: string | null;
  quality_flag: string | null;
  vendor_status: string | null;
  fallback_mode: string | null;
  tables_used: string[];
  evidence_rows: number | null;
};

type EndpointEvidenceItem = {
  key: string;
  label: string;
  endpoint: string;
  status: "ready" | "deferred" | "missing" | "error" | "unsupported" | "stale";
  as_of_date: string | null;
  rows: number | null;
  warning: string | null;
};

type WorkbenchIssue = {
  severity: "info" | "warning" | "blocking";
  code: string;
  message: string;
  source_module: string | null;
};

type WorkbenchLinks = {
  stock_detail: "/ui/market-data/livermore/stock-detail";
  candidate_history: "/ui/market-data/livermore/candidate-history";
  sector_rank_series: "/ui/market-data/livermore/sector-rank-series";
  strategy_score: "/ui/market-data/livermore/strategy-score";
  strategy_optimization: "/ui/market-data/livermore/strategy-optimization";
  cycle_proxy_backtest: "/ui/market-data/livermore/cycle-proxy-backtest";
  portfolio_backtest: "/ui/market-data/livermore/candidate-history-portfolio-backtest";
};
```

`unknown` above means: reuse the existing payload contracts first, do not invent new metric fields in this draft. The aggregator may pass through selected existing results while adding page-level summary, status, and issue fields.

## Implementability Matrix

| Page need | Existing support | Status | Handling |
| --- | --- | --- | --- |
| Observation date | Main Livermore payload `as_of_date` | direct | Return `requested_as_of_date`, resolved `as_of_date`, and `fallback_date` |
| Market gate | `/livermore` `market_gate` | direct | Include in `first_screen.market_gate` |
| Review queue | `/livermore` candidates and page model | adapter | Backend should return compact top queue summary, frontend keeps cards |
| Sector snapshot | `/livermore` `sector_rank` | direct | Include compact first-screen rows |
| Sector trend | `/sector-rank-series` | direct but heavier | Lazy `include=sector_rank_series` |
| Signal confluence | `/signal-confluence` | direct but can be slow | Lazy include; first implementation may mark `deferred` and link to the existing endpoint |
| Strategy score | `/strategy-score` | direct but diagnostic | Lazy include |
| Strategy optimization | `/strategy-optimization` | direct but diagnostic | Lazy include |
| Candidate replay | `/candidate-history` | direct but historical | Lazy include or drilldown |
| Proxy backtests | `/cycle-proxy-backtest`, `/candidate-history-portfolio-backtest` | direct but not formal validation | Lazy include with proxy warning |
| Stock detail drawer | `/stock-detail` | direct | Keep separate from workbench endpoint |
| News/events | Existing news client path | partial | Keep separate; show missing linkage if not joined |
| Bank fundamentals | Existing docs mark missing or pending | unsupported | Show as missing, never mock |
| Formal trading approval | Governance says forbidden | unsupported | Always return `formal_use_allowed: false` |

## Backend Construction Rule

The backend is a thin aggregator and must remain one:

1. Call existing Livermore service functions.
2. Reuse existing result envelopes and `workbench_summary` fields.
3. Normalize module status and meta into one page-level shape.
4. Build the first-screen answer from existing fields only.
5. Return warnings for missing, stale, fallback, unsupported, or deferred modules.

Do not add new finance math in the frontend to compensate for missing backend evidence.

## Frontend Consumption Rule

The domain client method lives in `frontend/src/api/marketDataClient.ts`:

```ts
getStockAnalysisWorkbench(options?: StockAnalysisWorkbenchOptions)
```

Do not add endpoint logic to `frontend/src/api/client.ts`.

The page should be able to render first screen from one query:

```ts
["stock-analysis", "workbench", asOfDate ?? "__default", includeKey]
```

Existing endpoints remain useful for drawer, expanded diagnostics, and lazy detail panels.

## Acceptance Criteria

- First screen can render from `GET /ui/market-data/stock-analysis/workbench` without waiting for every heavy diagnostic endpoint.
- Every visible card has a source module, status, and date.
- `null`, `0`, missing, stale, fallback, and deferred states remain visually distinct.
- Heavy modules can be requested explicitly through `include`.
- Existing `/ui/market-data/livermore/*` endpoints keep working.
- No static demo values are introduced in real mode.
- The page keeps observational wording: observation, review, evidence, invalidation, boundary.
- The response never implies buy, sell, order, allocation, or execution approval.

## Implemented Surface

1. The existing market-data route exposes `GET /ui/market-data/stock-analysis/workbench` with bounded defaults and server timing.
2. The service aggregator composes existing Livermore evidence and returns analytical, observation-only page status.
3. Backend tests cover response shape, default/deferred modules, date handling, review blocking, queue exclusions, and first-screen boundaries.
4. TypeScript contracts and `marketDataClient.getStockAnalysisWorkbench` bind the frontend request.
5. The first screen loads from the workbench endpoint; deep research and detail endpoints remain lazy.
6. Page and model tests cover queue semantics, loading/error states, null handling, and observational boundaries.

## Remaining Risks

- `GS-STOCK-ANALYSIS-OBS-A` freezes the underlying `/ui/market-data/livermore` DTO only; it is not an independent golden sample for the workbench wrapper.
- The workbench endpoint has no direct execution governance record, manual audit closure, or business-owner approval.
- Current theme overlay availability depends on an overlay archive matching the latest Choice observation date; missing overlays must stay explicit and fail closed.
- `/stock-analysis` remains `GAP-STOCK-ANALYSIS-PAGE`, observational, and `formal_use_allowed=false`; no standalone `PAGE-STOCK-*` or `MTR-STOCK-*` promotion is implied.
