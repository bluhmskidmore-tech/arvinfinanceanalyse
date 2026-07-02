# Stock Analysis Workbench API Contract Draft

Date: 2026-06-30

Route: `/stock-analysis`

Recommended endpoint: `GET /ui/market-data/stock-analysis/workbench`

Status: draft, observational only

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
- `frontend/src/features/stock-analysis/components/StockDetailDrawer.tsx`
- `frontend/src/features/stock-analysis/hooks/useSectorRankSeriesSupport.ts`
- `backend/app/api/routes/market_data_livermore.py`
- `backend/app/services/market_data_livermore_service.py`
- `docs/plans/2026-05-06-stock-analysis-workbench.md`
- `docs/handoff/2026-05-06-stock-analysis-workbench-codex.md`
- `docs/audits/2026-06-06-stock-analysis-gate-i-lane.md`

Unavailable evidence:

- `moss-metric-contracts`
- `moss-lineage-evidence`
- `moss-data-catalog`
- `gitnexus`

Those MCP tools were not exposed in the current Codex tool surface, so this draft uses local code evidence only. Metric definitions, catalog dates, and official lineage remain residual risks until those tools or equivalent records are available.

Live API note:

- The page at `http://localhost:5888/stock-analysis` reached full business state in browser after waiting.
- Direct read-only sampling of `/ui/market-data/livermore` and `/ui/market-data/livermore/signal-confluence` timed out at 20 seconds in this session.
- That supports keeping the proposed endpoint lightweight by default and leaving heavy diagnostics behind explicit `include` options.

## Current Data Path

Existing frontend path:

1. `StockAnalysisPage.tsx`
2. TanStack Query state
3. `marketDataClient.ts`
4. `/ui/market-data/livermore*`
5. `market_data_livermore.py`
6. Livermore service / result envelopes
7. Page models, cards, rails, tables, charts

Existing endpoint map:

| Frontend method | Backend path | Current role |
| --- | --- | --- |
| `getLivermoreStrategy` | `/ui/market-data/livermore` | Main market gate, sector rank, candidates, diagnostics, data gaps |
| `getLivermoreSignalConfluence` | `/ui/market-data/livermore/signal-confluence` | Signal confluence, macro/adversarial/replay evidence |
| `getLivermoreSectorRankSeries` | `/ui/market-data/livermore/sector-rank-series` | Sector trend and fallback rows |
| `getLivermoreStrategyScore` | `/ui/market-data/livermore/strategy-score` | Strategy priority diagnostics |
| `getLivermoreStrategyOptimization` | `/ui/market-data/livermore/strategy-optimization` | Strategy optimization diagnostics |
| `getLivermoreCandidateHistory` | `/ui/market-data/livermore/candidate-history` | Candidate replay/history and drawer history |
| `getLivermoreCycleProxyBacktest` | `/ui/market-data/livermore/cycle-proxy-backtest` | Cycle proxy backtest |
| `getLivermoreCandidateHistoryPortfolioBacktest` | `/ui/market-data/livermore/candidate-history-portfolio-backtest` | Portfolio proxy backtest |
| `getLivermoreStockDetail` | `/ui/market-data/livermore/stock-detail` | Drawer-only stock detail |

The page already consumes multiple endpoints. The new endpoint should not replace all drilldowns; it should give the first screen and evidence boundary a single stable source.

## Proposed Endpoint

```http
GET /ui/market-data/stock-analysis/workbench?as_of_date=2026-06-26&include=main,signal_confluence
```

Parameters:

| Name | Type | Default | Notes |
| --- | --- | --- | --- |
| `as_of_date` | `YYYY-MM-DD` | latest resolved date | Must preserve requested date and resolved date separately |
| `include` | comma-separated keys | `main,signal_confluence,evidence_summary` | Optional heavy modules stay lazy |
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

The backend should be a thin aggregator:

1. Call existing Livermore service functions.
2. Reuse existing result envelopes and `workbench_summary` fields.
3. Normalize module status and meta into one page-level shape.
4. Build the first-screen answer from existing fields only.
5. Return warnings for missing, stale, fallback, unsupported, or deferred modules.

Do not add new finance math in the frontend to compensate for missing backend evidence.

## Frontend Consumption Rule

Add a domain client method in `frontend/src/api/marketDataClient.ts`, for example:

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

## Minimal Implementation Plan

1. Add backend route `GET /ui/market-data/stock-analysis/workbench` in the existing market-data route layer.
2. Add a small service aggregator that composes existing Livermore envelopes.
3. Add backend tests for default response, missing/deferred modules, date handling, and no-trading wording.
4. Add TypeScript contracts and `marketDataClient` method.
5. Move first-screen page query to the new endpoint.
6. Keep existing detailed queries for drawers and expanded/lazy panels.
7. Add focused frontend tests for the new adapter/view model path.

## Remaining Risks

- Project MCP contract and lineage tools were unavailable, so this draft cannot certify official metric definitions or catalog lineage.
- Direct API sampling timed out at 20 seconds, so implementation should avoid making the default workbench endpoint call all heavy modules.
- The current worktree has many unrelated dirty files, including stock-analysis files. Implementation should isolate this contract work carefully and avoid rewriting unrelated changes.
- `/stock-analysis` remains observational until a standalone page contract, golden samples, metric dictionary rows, lineage evidence, and business-owner approval are complete.
