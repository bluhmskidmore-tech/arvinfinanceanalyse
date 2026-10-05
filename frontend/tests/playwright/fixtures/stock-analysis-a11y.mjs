import { loadMock } from "./mock-module.mjs";

const { createMockMarketDataClient } = loadMock(new URL("../../../src/mocks/marketDataMockClient.ts", import.meta.url));

// Exercise both qualification states through the real HTTP client. The ready
// response is synthetic accessibility coverage, never a production fallback.
export async function interceptStockAnalysisA11y(page) {
  const client = createMockMarketDataClient();
  const fixture = { ready: false, workbenchReads: 0, paths: [] };
  const methods = {
    "/ui/market-data/stock-analysis/workbench": "getStockAnalysisWorkbench",
    "/ui/market-data/livermore/stock-detail": "getLivermoreStockDetail",
    "/ui/market-data/stock-analysis/kline-analysis": "getStockKlineAnalysis",
    "/ui/market-data/livermore/candidate-history": "getLivermoreCandidateHistory",
    "/ui/market-data/livermore/strategy-score": "getLivermoreStrategyScore",
    "/ui/market-data/livermore/strategy-optimization": "getLivermoreStrategyOptimization",
    "/ui/market-data/livermore/cycle-proxy-backtest": "getLivermoreCycleProxyBacktest",
    "/ui/market-data/livermore/candidate-history-portfolio-backtest": "getLivermoreCandidateHistoryPortfolioBacktest",
    "/ui/market-data/livermore/signal-confluence": "getLivermoreSignalConfluence",
    "/ui/market-data/livermore/sector-rank-series": "getLivermoreSectorRankSeries",
  };
  await page.route("**/*", async route => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/system-read-publication") {
      return route.fulfill({ json: { enabled: false, generation: null, coverage_dates: {} } });
    }
    const method = methods[url.pathname];
    if (method) {
      fixture.paths.push(url.pathname);
      const options = {
        asOfDate: url.searchParams.get("as_of_date") ?? undefined,
        stockCode: url.searchParams.get("stock_code") ?? "600000.SH",
        lookback: Number(url.searchParams.get("lookback") ?? 60),
        topK: Number(url.searchParams.get("top_k") ?? 10),
      };
      const json = await client[method](options);
      if (method === "getStockAnalysisWorkbench") {
        fixture.workbenchReads++;
        if (fixture.ready) {
          json.result.pretrade_qualification = {
            ...json.result.pretrade_qualification,
            status: "ready",
            reason: "synthetic_accessibility_fixture",
          };
        }
      }
      return route.fulfill({ json });
    }
    if (/^\/(api|ui|health)(\/|$)/.test(url.pathname)) {
      return route.fulfill({ status: 503, json: { detail: "Not part of the stock accessibility fixture" } });
    }
    return route.continue();
  });
  return fixture;
}
