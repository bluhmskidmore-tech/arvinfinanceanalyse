# Stock Analysis Performance Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `/stock-analysis` show the primary business conclusion quickly while preserving traceable, read-only Livermore diagnostics.

**Architecture:** Split the page into a fast first-screen path and deferred diagnostic paths. Then add safe process-local caching around repeated DuckDB read-only computations, keyed by request parameters and DuckDB file version so data correctness remains ahead of raw speed.

**Tech Stack:** React, TanStack Query, Vite, FastAPI, DuckDB, Vitest, pytest, Playwright.

---

## Baseline Evidence

Measured on `http://localhost:5888/stock-analysis` on 2026-05-31:

- `/ui/market-data/livermore`: about 4.7s warm-ish, one direct backend run observed at 23.8s.
- `/ui/market-data/livermore/signal-confluence?as_of_date=2026-05-27`: about 17.2s during page-style concurrent load.
- `/ui/market-data/livermore/strategy-score?...`: about 19.5s during page-style concurrent load.
- `/ui/market-data/livermore/strategy-optimization?...`: about 19.4s during page-style concurrent load.
- `/ui/market-data/livermore/candidate-history?...limit=500`: about 2.9s during page-style concurrent load.
- `/cycle-proxy-backtest` and `/candidate-history-portfolio-backtest`: sub-second individually, but still add concurrency pressure.

Root causes observed:

- `StockAnalysisPage.tsx` waits on the main strategy query before first screen can render.
- After the main strategy payload resolves, the page eagerly starts multiple diagnostics and backtest queries.
- `signal-confluence` recomputes `livermore_strategy_envelope` inside the backend route.
- `strategy-score` and `strategy-optimization` both read the same candidate-history window and both classify replay coverage date-by-date.
- No stock-analysis-specific cache options are set; default query stale time is only 60s.

## Non-Goals

- Do not change metric definitions, formulas, units, dates, or trading decision semantics.
- Do not change database schema.
- Do not refactor global API client architecture or app-wide state.
- Do not hide stale, fallback, no-data, or loading-failure states.
- Do not raise frontend debt baselines.

## Performance Targets

- First screen should request only the data needed for the main conclusion.
- First visible cockpit should render after the main strategy result, without waiting for strategy score, optimization, candidate-history, or portfolio backtest requests.
- Heavy diagnostics should load on section visibility or explicit expansion.
- Warm repeat calls for the same as-of date should avoid recomputing identical read-only envelopes.
- Repeated page refreshes should not produce 502s under the current local dev server.

## Task 1: Confirm Contracts And Evidence Before Code

**Files:**
- Read: `docs/MCP_RUNBOOK.md`
- Read: `docs/page_contracts.md`
- Read: `docs/metric_dictionary.md`
- Read: `docs/calc_rules.md`
- Read: `docs/golden_sample_catalog.md`

**Step 1: Check project MCP evidence**

Use the project MCPs before changing business display or backend read paths:

- `moss-metric-contracts`: stock-analysis page contract, units, definitions, golden samples.
- `moss-lineage-evidence`: Livermore source versions, rule/cache lineage, fallback/stale status.
- `moss-data-catalog`: DuckDB tables and report dates used by Livermore endpoints.
- `gitnexus`: call paths and cross-page impact for changed symbols.

Expected: record the available evidence in the implementation notes.

**Step 2: If any MCP is unavailable**

Record:

- Which server was unavailable.
- Which local docs or tests were used instead.
- Residual risk.

Expected: no metric definition is guessed.

## Task 2: Add A Frontend Regression Test For Eager Query Fan-Out

**Files:**
- Modify: `frontend/src/test/StockAnalysisPage.test.tsx`

**Step 1: Write a failing test**

Add a test near the existing `StockAnalysisPage` tests that wraps the heavy client methods in `vi.fn`.

Behavior to assert:

- Initial render calls `getLivermoreStrategy`.
- Initial first-screen render does not immediately call:
  - `getLivermoreStrategyScore`
  - `getLivermoreStrategyOptimization`
  - `getLivermoreCandidateHistory`
  - `getLivermoreCycleProxyBacktest`
  - `getLivermoreCandidateHistoryPortfolioBacktest`
- The page still renders `stock-analysis-tailwind-cockpit`.

Suggested shape:

```ts
it("does not fan out lower-page diagnostics before the first screen", async () => {
  const client = stockClient();
  const strategyScoreSpy = vi.spyOn(client, "getLivermoreStrategyScore");
  const strategyOptimizationSpy = vi.spyOn(client, "getLivermoreStrategyOptimization");
  const candidateHistorySpy = vi.spyOn(client, "getLivermoreCandidateHistory");
  const cycleProxySpy = vi.spyOn(client, "getLivermoreCycleProxyBacktest");
  const portfolioBacktestSpy = vi.spyOn(client, "getLivermoreCandidateHistoryPortfolioBacktest");

  renderWorkbenchApp(["/stock-analysis"], { client });

  expect(await screen.findByTestId("stock-analysis-tailwind-cockpit")).toBeInTheDocument();
  expect(strategyScoreSpy).not.toHaveBeenCalled();
  expect(strategyOptimizationSpy).not.toHaveBeenCalled();
  expect(candidateHistorySpy).not.toHaveBeenCalled();
  expect(cycleProxySpy).not.toHaveBeenCalled();
  expect(portfolioBacktestSpy).not.toHaveBeenCalled();
});
```

**Step 2: Run the failing test**

Run:

```bash
cd frontend
npm run test -- StockAnalysisPage.test.tsx
```

Expected: the new test fails because current page eagerly enables the heavy queries once `effectiveAsOf` exists.

## Task 3: Defer Lower-Page Diagnostics In The Frontend

**Files:**
- Modify: `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
- Modify: `frontend/src/test/StockAnalysisPage.test.tsx`

**Step 1: Define query priority**

Keep immediate:

- `getLivermoreStrategy`

Keep non-blocking but separate from first render:

- `getLivermoreSignalConfluence`, because closed-loop and replay status are useful on the first page but should not block the primary conclusion.

Defer until the user reaches or opens the relevant section:

- `getLivermoreStrategyScore`
- `getLivermoreStrategyOptimization`
- `getLivermoreCandidateHistory`
- `getLivermoreCycleProxyBacktest`
- `getLivermoreCandidateHistoryPortfolioBacktest`
- `getLivermoreCandidateHistory` for maturity detail
- `getLivermoreSectorRankSeries` already defers behind expansion; keep that behavior.

**Step 2: Add a tiny page-local visibility helper**

Add a small page-local hook in `StockAnalysisPage.tsx` or a page-local helper file only if it keeps the huge page readable.

Preferred minimal helper:

```ts
function useSectionSeen<TElement extends HTMLElement>() {
  const [seen, setSeen] = useState(false);
  const ref = useRef<TElement | null>(null);

  useEffect(() => {
    if (seen) return undefined;
    const node = ref.current;
    if (!node) return undefined;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setSeen(true);
          observer.disconnect();
        }
      },
      { rootMargin: "240px 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [seen]);

  return { ref, seen };
}
```

Fallback for test/jsdom:

- If `IntersectionObserver` is absent, keep first-screen behavior deterministic by requiring explicit expansion/click for deferred sections, or provide a small test shim in `StockAnalysisPage.test.tsx`.

**Step 3: Gate query `enabled` flags**

Add booleans such as:

- `historicalReviewSeen`
- `cycleFrameworkSeen`
- `strategyPrioritySeen`
- `strategyOptimizationSeen`

Then update query `enabled` fields:

```ts
enabled: Boolean(effectiveAsOf && strategyPrioritySeen)
```

For confluence:

- Set `enabled: Boolean(strategyPayload?.as_of_date && confluenceRequested)`.
- Flip `confluenceRequested` in `useEffect` after the strategy payload arrives, so first-screen strategy content can paint first.

**Step 4: Preserve page-level closure states**

For each deferred section, render one of:

- Not reached yet: neutral pending state.
- Loading after reached: existing loading copy.
- Error: existing error copy.
- Empty/no data/stale/fallback: existing status from the endpoint.

Expected: no section silently disappears.

**Step 5: Run frontend tests**

Run:

```bash
cd frontend
npm run test -- StockAnalysisPage.test.tsx
```

Expected: existing tests pass after updating assertions that assumed eager loading.

## Task 4: Add Stock-Analysis Query Defaults

**Files:**
- Modify: `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
- Test: `frontend/src/test/StockAnalysisPage.test.tsx`

**Step 1: Add local query options**

Add a local constant:

```ts
const STOCK_ANALYSIS_STALE_TIME_MS = 5 * 60_000;
const STOCK_ANALYSIS_GC_TIME_MS = 15 * 60_000;
```

Apply to read-only stock-analysis queries:

```ts
staleTime: STOCK_ANALYSIS_STALE_TIME_MS,
gcTime: STOCK_ANALYSIS_GC_TIME_MS,
refetchOnWindowFocus: false,
```

Do not apply to write actions or refresh mutations.

**Step 2: Keep manual refresh authoritative**

Keep:

```ts
queryClient.invalidateQueries({ queryKey: ["stock-analysis"] })
```

Expected: the refresh button still invalidates all stock-analysis data.

**Step 3: Run tests**

Run:

```bash
cd frontend
npm run test -- StockAnalysisPage.test.tsx
```

Expected: tests pass.

## Task 5: Cache Livermore Strategy Envelopes Safely

**Files:**
- Modify: `backend/app/services/market_data_livermore_service.py`
- Test: `tests/test_market_data_livermore_api.py` or create a focused service test.

**Step 1: Use existing runtime cache**

Import:

```py
from backend.app.services.runtime_cache import get_runtime_cache, clear_runtime_cache
```

Add a small cache with a short TTL, for example 120 seconds:

```py
_LIVERMORE_STRATEGY_CACHE_TTL_SECONDS = 120.0
_LIVERMORE_STRATEGY_CACHE = get_runtime_cache("market_data_livermore.strategy", ttl_seconds=_LIVERMORE_STRATEGY_CACHE_TTL_SECONDS)
```

**Step 2: Key the cache by data version**

Build the key from:

- resolved DuckDB path
- DuckDB file `st_mtime_ns`
- requested `as_of_date`
- `stock_candidate_policy`
- choice stock catalog file mtime if needed by caller path

Do not key by `trace_id`; trace IDs can be regenerated in the envelope if needed.

**Step 3: Cache the expensive payload/meta producer**

Prefer caching `load_livermore_strategy_payload(...)` result before wrapping, so result metadata remains correct and trace IDs can stay request-specific.

Expected: `/livermore` and `/signal-confluence` can share the same expensive strategy payload when called for the same as-of date and DuckDB version.

**Step 4: Add a test**

Use monkeypatch to count calls to `_load_choice_stock_outputs` or `_load_sector_rank_inputs`.

Expected:

- First call computes.
- Second call with same key hits cache.
- Changing `as_of_date` or DuckDB mtime misses cache.

**Step 5: Run backend tests**

Run:

```bash
pytest tests/test_market_data_livermore_api.py -q
```

Expected: pass.

## Task 6: Cache Candidate-History Coverage And Diagnostics

**Files:**
- Modify: `backend/app/services/livermore_candidate_history_service.py`
- Modify: `backend/app/tasks/choice_stock_materialize.py` only if the cache belongs closer to the coverage function.
- Test: `tests/test_livermore_candidate_history_efficiency.py`

**Step 1: Cache replay coverage lookups**

The hot loop is:

```py
for trade_date in trade_dates:
    coverage = load_choice_stock_materialization_coverage(...)
```

Add a process-local cache for coverage keyed by:

- resolved DuckDB path
- DuckDB file `st_mtime_ns`
- `as_of_date`
- `required_items`

The cache can live inside `choice_stock_materialize.py` if all callers benefit.

**Step 2: Avoid duplicate window diagnostics**

Add a cached helper for the candidate-history diagnostic window:

- `_load_backtest_window_rows`
- `_resolve_replay_trade_dates`
- `_build_backtest_window_summary_from_rows`

Key by:

- DuckDB path
- DuckDB file `st_mtime_ns`
- stock code
- snapshot from/to

Expected: `strategy-score` and `strategy-optimization` no longer independently redo the same window read and coverage classification when called close together.

**Step 3: Add efficiency tests**

Extend `tests/test_livermore_candidate_history_efficiency.py`:

- Count `load_choice_stock_materialization_coverage` calls for repeated same-date diagnostics.
- Assert repeated same-key calls reuse cached coverage.
- Assert changing DuckDB content/version invalidates the cached result.

**Step 4: Run tests**

Run:

```bash
pytest tests/test_livermore_candidate_history_efficiency.py -q
pytest tests/test_market_data_livermore_candidate_history.py -q
```

Expected: pass.

## Task 7: Consider A Combined Diagnostics Endpoint After P0

**Files:**
- Potentially modify: `backend/app/api/routes/market_data_livermore.py`
- Potentially modify: `backend/app/services/livermore_candidate_history_service.py`
- Potentially modify: `frontend/src/api/marketDataClient.ts`
- Potentially modify: `frontend/src/api/contracts.ts`
- Potentially modify: `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`

**Decision gate:**

Only do this if Tasks 3-6 do not meet the target. This is more invasive.

**Approach:**

Create a single read-only endpoint like:

```text
GET /ui/market-data/livermore/strategy-diagnostics
```

Return:

- strategy score
- strategy optimization
- candidate-history backtest summary
- maturity detail summary if needed

Expected benefit: one DuckDB window scan instead of multiple endpoint-level scans.

## Task 8: Browser And Performance Verification

**Files:**
- No source changes required.

**Step 1: Restart or confirm local services**

Expected:

- frontend on `http://localhost:5888`
- backend on `http://127.0.0.1:7888`

**Step 2: Measure endpoint timings**

Use the same page-style sequence:

1. Request `/ui/market-data/livermore`.
2. Use returned `as_of_date` and `market_gate.state`.
3. Request the remaining diagnostics concurrently.

Record before/after:

- first strategy ms
- confluence ms
- strategy-score ms
- strategy-optimization ms
- candidate-history ms
- total page-style sequence ms

**Step 3: Verify browser behavior**

Open:

```text
http://localhost:5888/stock-analysis
```

Expected:

- The main conclusion appears without waiting for lower-page diagnostics.
- Deferred panels show explicit pending/loading/error/no-data states.
- Scrolling to a deferred section triggers its query.
- Manual refresh invalidates and reloads the relevant data.
- No console errors.

**Step 4: Run frontend checks**

Run:

```bash
cd frontend
npm run test -- StockAnalysisPage.test.tsx
npm run debt:audit
npm run lint
npm run typecheck
```

Expected: all pass.

**Step 5: Run backend checks**

Run:

```bash
pytest tests/test_livermore_candidate_history_efficiency.py -q
pytest tests/test_market_data_livermore_candidate_history.py -q
pytest tests/test_market_data_livermore_api.py -q
```

Expected: all pass.

## Recommended Implementation Order

1. Frontend fan-out regression test.
2. Frontend deferred query gating.
3. Frontend stock-analysis query defaults.
4. Backend strategy payload cache.
5. Backend candidate-history coverage/window cache.
6. Browser timing verification.
7. Combined diagnostics endpoint only if still needed.

## Remaining Risks

- Process-local cache is per worker; multi-worker deployment would still compute once per worker.
- DuckDB mtime-based invalidation is safe for file changes but may miss exotic write paths that do not update mtime.
- Deferring diagnostics changes when secondary panels populate; tests must prove first-screen business closure still surfaces loading/fallback/error explicitly.
- A combined diagnostics endpoint improves throughput but increases contract surface, so it should stay behind the P0/P1 optimizations.
