import { test, expect } from "@playwright/test";

const dataSource = process.env.VITE_DATA_SOURCE;
const shouldLogLayoutMetrics = process.env.MOSS_PLAYWRIGHT_LOG_LAYOUT === "1";
const STOCK_ANALYSIS_READY_SELECTOR = '[data-testid="stock-analysis-page"]';
const REVIEW_QUEUE_SELECTOR = '[data-testid="stock-analysis-review-queue"]';
const REVIEW_QUEUE_ROW_SELECTOR = '[data-testid^="stock-analysis-gate-ledger-row-"]';
const EXEMPT_OVERFLOW_CONTAINERS = [
  '[data-testid="workbench-market-ticker"]',
  '[data-testid="workbench-section-subnav"]',
  '[data-testid^="market-workbench-nav-"]',
];

const viewports = [
  {
    name: "1440",
    width: 1440,
    height: 1100,
    expectVisibleRows: 3,
    expectFirstViewportRowsMin: null,
  },
  {
    name: "1280",
    width: 1280,
    height: 1100,
    expectVisibleRows: 3,
    expectFirstViewportRowsMin: null,
  },
  {
    name: "1024",
    width: 1024,
    height: 1100,
    expectVisibleRows: null,
    expectFirstViewportRowsMin: 3,
  },
  {
    name: "390",
    width: 390,
    height: 844,
    expectVisibleRows: null,
    expectFirstViewportRowsMin: 2,
  },
];

function buildMeta(resultKind) {
  return {
    trace_id: `tr_playwright_${resultKind.replace(/[^a-z0-9]+/gi, "_").toLowerCase()}`,
    basis: "analytical",
    result_kind: resultKind,
    formal_use_allowed: false,
    source_version: "sv_playwright_stock_analysis_density",
    vendor_version: "vv_playwright_stock_analysis_density",
    rule_version: "rv_playwright_stock_analysis_density_v1",
    cache_version: "cv_playwright_stock_analysis_density_v1",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-06-26T00:00:00Z",
  };
}

function buildEnvelope(resultKind, result) {
  return {
    result_meta: buildMeta(resultKind),
    result,
  };
}

function buildReadyModuleState(key, asOfDate, overrides = {}) {
  return {
    key,
    state: "ready",
    render_mode: "primary",
    source_date: asOfDate,
    lag_days: 0,
    threshold_days: null,
    coverage_count: null,
    coverage_denominator: null,
    coverage_ratio: null,
    coverage_threshold: null,
    reasons: [],
    evidence_scope: "primary",
    excludes_from_primary: false,
    ...overrides,
  };
}

function buildStockCandidate(rank) {
  const sectorNumber = ((rank - 1) % 5) + 1;
  const baseClose = 18 + rank * 0.65;
  const breakoutLevel = baseClose - 0.22;
  return {
    rank,
    stock_code: `${String(rank).padStart(6, "0")}.SZ`,
    stock_name: `Candidate ${rank}`,
    sector_code: `8010${sectorNumber.toString().padStart(2, "0")}`,
    sector_name: `Sector ${sectorNumber}`,
    sector_rank: sectorNumber,
    close: Number(baseClose.toFixed(2)),
    breakout_level: Number(breakoutLevel.toFixed(2)),
    ema10: Number((baseClose - 0.54).toFixed(2)),
    ma20: Number((baseClose - 0.82).toFixed(2)),
    ma60: Number((baseClose - 1.63).toFixed(2)),
    ma120: Number((baseClose - 3.11).toFixed(2)),
    close_strength: Number((0.56 + (rank % 5) * 0.06).toFixed(6)),
    gap_norm: Number((-0.16 + rank * 0.011).toFixed(6)),
    breakout_extension_norm: Number((0.018 + (rank % 4) * 0.013).toFixed(6)),
    abnormal_turnover: Number((0.92 + rank * 0.07).toFixed(6)),
    selection_policy: "trend_breakout_primary",
    pe: Number((11.2 + rank * 0.4).toFixed(2)),
    pb: Number((1.4 + rank * 0.06).toFixed(2)),
    ps: Number((2.1 + rank * 0.05).toFixed(2)),
    roe: Number((0.12 + (rank % 4) * 0.015).toFixed(3)),
    gross_margin: Number((0.26 + (rank % 5) * 0.014).toFixed(3)),
    three_month_return: Number((0.06 + rank * 0.004).toFixed(3)),
    twelve_month_return: Number((0.15 + rank * 0.006).toFixed(3)),
    volatility: Number((0.19 + (rank % 6) * 0.01).toFixed(3)),
    dividend_yield: Number((0.008 + (rank % 5) * 0.0015).toFixed(4)),
    factor_score: Number((0.38 + rank * 0.012).toFixed(4)),
    factor_overlay_rank: rank,
  };
}

function buildDenseStrategyPayload() {
  const asOfDate = "2026-04-29";
  const items = Array.from({ length: 20 }, (_, index) => buildStockCandidate(index + 1));

  return {
    as_of_date: asOfDate,
    requested_as_of_date: null,
    strategy_name: "Livermore A-Share Defended Trend",
    basis: "analytical",
    market_gate: {
      state: "WARM",
      exposure: 0.4,
      passed_conditions: 3,
      available_conditions: 3,
      required_conditions: 4,
      conditions: [
        {
          key: "csi300_close_gt_ma60",
          label: "CSI300 close > MA60",
          status: "pass",
          evidence: "Close is above MA60.",
          source_series_id: "CA.CSI300",
        },
        {
          key: "limit_up_quality",
          label: "Limit-up quality",
          status: "pass",
          evidence: "Limit-up seal quality remains supportive.",
          source_series_id: "CA.LIMIT_UP",
        },
        {
          key: "breadth_positive",
          label: "Breadth positive",
          status: "missing",
          evidence: "Breadth input is pending confirmation.",
          source_series_id: "CA.BREADTH",
        },
      ],
    },
    rule_readiness: [
      {
        key: "market_gate",
        title: "Market gate",
        status: "partial",
        summary: "Trend-only market gate is available.",
        required_inputs: ["broad_index_history", "breadth"],
        missing_inputs: ["breadth"],
      },
      {
        key: "stock_pivot",
        title: "Stock candidates",
        status: "ready",
        summary: "Dense review queue candidates are available for observation.",
        required_inputs: ["choice_stock_daily_observation"],
        missing_inputs: [],
      },
      {
        key: "risk_exit",
        title: "Risk exit",
        status: "ready",
        summary: "Risk exit watch rows are available.",
        required_inputs: ["livermore_position_snapshot"],
        missing_inputs: [],
      },
    ],
    diagnostics: [
      {
        severity: "warning",
        code: "LIVERMORE_BREADTH_PENDING",
        message: "Breadth inputs are unavailable.",
        input_family: "breadth",
      },
    ],
    data_gaps: [
      {
        input_family: "breadth",
        status: "missing",
        evidence: "5-day breadth input family is not landed.",
      },
    ],
    supported_outputs: ["market_gate", "sector_rank", "stock_candidates", "risk_exit"],
    unsupported_outputs: [
      {
        key: "hybrid_fusion",
        reason: "Observation-only hybrid fusion is intentionally excluded from the primary queue.",
      },
    ],
    module_states: [
      buildReadyModuleState("market_gate", asOfDate),
      buildReadyModuleState("sector_rank", asOfDate),
      buildReadyModuleState("stock_candidates", asOfDate),
      buildReadyModuleState("risk_exit", asOfDate),
      buildReadyModuleState("hybrid_fusion", asOfDate, {
        state: "unsupported",
        render_mode: "hidden",
        reasons: ["Observation-only hybrid fusion is intentionally excluded from the primary queue."],
        evidence_scope: "detail_only",
        excludes_from_primary: true,
      }),
    ],
    sector_rank: {
      as_of_date: asOfDate,
      formula_version: "rv_livermore_sector_strength_observation_v1",
      is_provisional: false,
      formula_status: "signed_off",
      sector_count: 5,
      excluded_constituent_count: 0,
      excluded_sector_count: 0,
      items: Array.from({ length: 5 }, (_, index) => ({
        rank: index + 1,
        sector_code: `8010${String(index + 1).padStart(2, "0")}`,
        sector_name: `Sector ${index + 1}`,
        score: Number((1.4 - index * 0.18).toFixed(2)),
        avg_pctchange: Number((4.2 - index * 0.9).toFixed(2)),
        avg_turn: Number((3.2 + index * 0.45).toFixed(2)),
        avg_amplitude: Number((2.9 + index * 0.35).toFixed(2)),
        constituent_count: 12 + index * 4,
      })),
    },
    stock_candidates: {
      as_of_date: asOfDate,
      formula_version: "rv_livermore_stock_candidates_bundle_v1",
      market_state: "WARM",
      input_stock_count: 20,
      candidate_count: items.length,
      excluded_stock_count: 0,
      insufficient_history_count: 0,
      selection_policy: "trend_breakout_primary",
      fundamental_overlay: {
        status: "ready",
        input_candidate_count: items.length,
        valid_factor_count: items.length,
        selected_factor_count: items.length,
        top_fraction: 1,
      },
      items,
    },
    risk_exit: {
      as_of_date: asOfDate,
      formula_version: "rv_livermore_risk_exit_ema10_mvp_v1",
      position_count: 2,
      signal_count: 1,
      excluded_position_count: 0,
      insufficient_history_count: 0,
      items: [
        {
          stock_code: "000101.SZ",
          stock_name: "Exit Watch Alpha",
          reason: "2d_below_ema10",
          entry_cost: 19.6,
          bars_since_entry: 6,
          latest_close: 18.9,
          latest_ema10: 19.4,
          prior_close: 19.3,
          prior_ema10: 19.6,
        },
      ],
      watch_items: [
        {
          stock_code: "000102.SZ",
          stock_name: "Watch Beta",
          entry_cost: 16.2,
          bars_since_entry: 4,
          latest_close: 16.4,
          latest_ema10: 16.5,
          prior_close: 16.7,
          prior_ema10: 16.6,
          exit_watch_price: 16.1,
          triggered: false,
        },
      ],
    },
  };
}

function buildMinimalSignalConfluencePayload() {
  return {
    as_of_date: "2026-04-29",
    macro_context: {
      status: "supportive",
      composite_score: 0.68,
      multiplier: 1,
      description: "Macro context is supportive for observation-only review.",
    },
    strategy_context: {
      market_gate_state: "WARM",
      market_gate_exposure: 0.4,
      allows_new_entry_observations: true,
      new_entry_observation_allowed: true,
      position_size_hint: 0.4,
    },
    position_size_hint: 0.4,
    entry_observations: [
      {
        stock_code: "000001.SZ",
        stock_name: "Candidate 1",
        action: "observe_entry_setup",
        trigger_price: 18.43,
        buy_trigger_price: 18.43,
        current_price: 18.65,
        invalidation_reference_price: 18.02,
        position_size_hint: 0.4,
        evidence: ["Trend breakout remains observational only."],
      },
    ],
    exit_observations: [
      {
        stock_code: "000101.SZ",
        stock_name: "Exit Watch Alpha",
        action: "observe_exit_watch",
        current_price: 18.9,
        exit_watch_price: 18.8,
        triggered: false,
        evidence: ["10EMA watch remains active."],
      },
    ],
    adversarial_context: {
      status: "complete",
      mode: "observation_only",
      risk_gate: "pass",
      position_scale: 1,
      strongest_block_reason: null,
    },
    closed_loop_state: {
      entry_gate: "observe_only",
      exit_gate: "watch",
      replay_status: "available",
      lineage_status: "complete",
    },
    replay_evidence: {
      status: "available",
      snapshot_as_of_date: "2026-04-29",
      row_count: 20,
      matched_entry_count: 20,
      sample_items: [
        {
          stock_code: "000001.SZ",
          stock_name: "Candidate 1",
          candidate_rank: 1,
          signal_kind: "stock_candidate",
          data_status: "complete",
        },
      ],
    },
    diagnostics: [
      {
        severity: "info",
        code: "OBSERVATION_ONLY",
        message: "Observation-only output does not generate trading instructions.",
      },
    ],
    disclaimer: "Observation only. No trading instructions are generated.",
  };
}

function buildBacktestWindowSummary() {
  return {
    status: "valid",
    snapshot_from: "2026-04-19",
    snapshot_to: "2026-04-29",
    replay_dates_total: 0,
    replay_dates_completed: 0,
    replay_dates_pending: 0,
    replay_dates_unsupported: 0,
    replay_dates_proxy_only: 0,
    completed_rows: 0,
    pending_rows: 0,
    unsupported_rows: 0,
    proxy_only_rows: 0,
    included_completed_stats_dates: [],
    excluded_from_completed_stats_dates: [],
    date_reasons: [],
  };
}

function buildMinimalCandidateHistoryPayload() {
  return {
    stock_code: null,
    snapshot_from: "2026-04-19",
    snapshot_to: "2026-04-29",
    limit: 500,
    summary: null,
    backtest_window_summary: buildBacktestWindowSummary(),
    items: [],
  };
}

function buildMinimalStrategyScorePayload() {
  return {
    as_of_date: "2026-04-29",
    snapshot_from: "2026-04-19",
    snapshot_to: "2026-04-29",
    primary_horizon: "return_5d",
    min_sample: 20,
    review_thresholds: {},
    current_market_state: "WARM",
    backtest_window_summary: buildBacktestWindowSummary(),
    rows: [],
    current_market_state_rows: [],
    stock_candidate_state_scopes: {},
  };
}

function buildMinimalStrategyOptimizationPayload() {
  return {
    as_of_date: "2026-04-29",
    snapshot_from: "2026-04-19",
    snapshot_to: "2026-04-29",
    primary_horizon: "return_5d",
    min_sample: 20,
    review_thresholds: {},
    current_market_state: "WARM",
    backtest_window_summary: buildBacktestWindowSummary(),
    strategy_summaries: [],
    slices: [],
    recommendations: [],
    pending_summary: {
      primary_horizon: "return_5d",
      pending_rows: 0,
      pending_dates: [],
      latest_pending_date: null,
      message: "No pending replay dates.",
    },
    sample_maturity: {
      status: "insufficient",
      primary_horizon: "return_5d",
      min_sample: 20,
      sufficient_count: 0,
      insufficient_count: 0,
    },
  };
}

function buildMinimalCycleProxyBacktestPayload() {
  return {
    status: "proxy",
    full_strategy_status: "blocked_missing_inputs",
    proxy_signal_kind: "stock_candidate",
    proxy_rule: "playwright_density_guard",
    snapshot_from: "2026-04-19",
    snapshot_to: "2026-04-29",
    missing_full_strategy_inputs: [],
    warnings: [],
    summary: null,
    nav_series: [],
  };
}

function buildMinimalCandidateHistoryPortfolioBacktestPayload() {
  return {
    status: "portfolio_proxy",
    full_strategy_status: "blocked_missing_inputs",
    signal_kind: "stock_candidate",
    rebalance_rule: "playwright_density_guard",
    weighting_rule: "equal_weight",
    snapshot_from: "2026-04-19",
    snapshot_to: "2026-04-29",
    missing_full_strategy_inputs: [],
    warnings: [],
    summary: null,
    nav_series: [],
    rebalance_log: [],
  };
}

function buildMinimalSectorRankSeriesPayload() {
  return {
    basis: "analytical",
    state: "ok",
    as_of_date: "2026-04-29",
    window_days: 20,
    top_k: 10,
    sector_code_filter: null,
    formula_version: "rv_livermore_sector_rank_series_v1",
    series: [],
    unsupported_notes: [],
  };
}

async function installLivermoreRoutes(page) {
  await page.route("**/ui/market-data/livermore**", async (route) => {
    const url = new URL(route.request().url());
    const { pathname } = url;

    const fulfill = async (resultKind, result) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(buildEnvelope(resultKind, result)),
      });
    };

    if (pathname === "/ui/market-data/livermore") {
      await fulfill("market_data.livermore", buildDenseStrategyPayload());
      return;
    }

    if (pathname === "/ui/market-data/livermore/signal-confluence") {
      await fulfill("market_data.livermore.signal_confluence", buildMinimalSignalConfluencePayload());
      return;
    }

    if (pathname === "/ui/market-data/livermore/strategy-score") {
      await fulfill("market_data.livermore.strategy_score", buildMinimalStrategyScorePayload());
      return;
    }

    if (pathname === "/ui/market-data/livermore/strategy-optimization") {
      await fulfill(
        "market_data.livermore.strategy_optimization",
        buildMinimalStrategyOptimizationPayload(),
      );
      return;
    }

    if (pathname === "/ui/market-data/livermore/candidate-history") {
      await fulfill("market_data.livermore.candidate_history", buildMinimalCandidateHistoryPayload());
      return;
    }

    if (pathname === "/ui/market-data/livermore/cycle-proxy-backtest") {
      await fulfill(
        "market_data.livermore.cycle_proxy_backtest",
        buildMinimalCycleProxyBacktestPayload(),
      );
      return;
    }

    if (pathname === "/ui/market-data/livermore/candidate-history-portfolio-backtest") {
      await fulfill(
        "market_data.livermore.candidate_history_portfolio_backtest",
        buildMinimalCandidateHistoryPortfolioBacktestPayload(),
      );
      return;
    }

    if (pathname === "/ui/market-data/livermore/sector-rank-series") {
      await fulfill(
        "market_data.livermore.sector_rank_series",
        buildMinimalSectorRankSeriesPayload(),
      );
      return;
    }

    await route.continue();
  });
}

async function collectLayoutMetrics(page, viewportWidth) {
  return page.evaluate(
    ({
      exemptOverflowContainers,
      reviewQueueRowSelector,
      stockAnalysisReadySelector,
      reviewQueueSelector,
      viewportWidth,
    }) => {
      const exemptSelectors = exemptOverflowContainers.join(",");
      const isVisible = (element) => {
        const style = window.getComputedStyle(element);
        if (
          style.display === "none" ||
          style.visibility === "hidden" ||
          Number.parseFloat(style.opacity || "1") === 0
        ) {
          return false;
        }
        const rect = element.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
      };

      const overflow = Array.from(document.querySelectorAll("[data-testid]"))
        .filter((element) => {
          if (!(element instanceof HTMLElement)) return false;
          if (!isVisible(element)) return false;
          if (exemptSelectors && element.closest(exemptSelectors)) return false;
          return Boolean(
            element.closest(stockAnalysisReadySelector) ||
              element.closest('[data-testid="workbench-main-content"]') ||
              element.closest('[data-testid="workbench-terminal-bar"]') ||
              element.closest('[data-testid="workbench-section-subnav"]'),
          );
        })
        .map((element) => {
          const rect = element.getBoundingClientRect();
          return {
            id: element.getAttribute("data-testid"),
            left: Math.round(rect.left),
            right: Math.round(rect.right),
            top: Math.round(rect.top),
            width: Math.round(rect.width),
          };
        })
        .filter((box) => box.left < -2 || box.right > window.innerWidth + 2)
        .slice(0, 40);

      const queue = document.querySelector(reviewQueueSelector);
      const queueRect = queue?.getBoundingClientRect() ?? null;
      const rows = Array.from(document.querySelectorAll(reviewQueueRowSelector)).filter(
        (element) => element instanceof HTMLElement && isVisible(element),
      );
      const firstViewportRows = rows.filter((row) => {
        const { top } = row.getBoundingClientRect();
        return top >= 0 && top < window.innerHeight;
      });
      const documentScrollWidth = document.documentElement.scrollWidth;
      const bodyScrollWidth = document.body.scrollWidth;

      return {
        viewportWidth,
        viewportHeight: window.innerHeight,
        overflow,
        documentScrollWidth,
        bodyScrollWidth,
        queueTop: queueRect ? Math.round(queueRect.top) : null,
        queueVisible: Boolean(queueRect && queueRect.width > 0 && queueRect.height > 0),
        visibleRowCount: rows.length,
        firstViewportRowCount: firstViewportRows.length,
      };
    },
    {
      exemptOverflowContainers: EXEMPT_OVERFLOW_CONTAINERS,
      reviewQueueRowSelector: REVIEW_QUEUE_ROW_SELECTOR,
      stockAnalysisReadySelector: STOCK_ANALYSIS_READY_SELECTOR,
      reviewQueueSelector: REVIEW_QUEUE_SELECTOR,
      viewportWidth,
    },
  );
}

function metricsMeetViewportInvariants(metrics, viewport) {
  if (!metrics.queueVisible) return false;
  if (metrics.queueTop == null || metrics.queueTop < 0 || metrics.queueTop >= viewport.height) {
    return false;
  }
  if (metrics.overflow.length > 0) return false;
  if (metrics.documentScrollWidth > viewport.width + 2) return false;
  if (metrics.bodyScrollWidth > viewport.width + 2) return false;
  if (viewport.expectVisibleRows != null && metrics.visibleRowCount !== viewport.expectVisibleRows) {
    return false;
  }
  if (
    viewport.expectFirstViewportRowsMin != null &&
    metrics.firstViewportRowCount < viewport.expectFirstViewportRowsMin
  ) {
    return false;
  }
  return true;
}

async function openStockAnalysis(page, viewport) {
  await installLivermoreRoutes(page);
  await page.setViewportSize({ width: viewport.width, height: viewport.height });
  await page.goto("/stock-analysis", { waitUntil: "domcontentloaded" });
  await expect(page.locator(STOCK_ANALYSIS_READY_SELECTOR)).toBeVisible({ timeout: 60_000 });
  await expect(page.locator(REVIEW_QUEUE_SELECTOR)).toBeVisible({ timeout: 60_000 });
  await expect(page.locator(REVIEW_QUEUE_ROW_SELECTOR).first()).toBeVisible({ timeout: 60_000 });

  let settledMetrics = null;
  let stablePassCount = 0;
  await expect
    .poll(
      async () => {
        settledMetrics = await collectLayoutMetrics(page, viewport.width);
        if (metricsMeetViewportInvariants(settledMetrics, viewport)) {
          stablePassCount += 1;
        } else {
          stablePassCount = 0;
        }
        return stablePassCount >= 3;
      },
      {
        timeout: 15_000,
        intervals: [150, 300, 500, 1000],
      },
    )
    .toBe(true);

  return settledMetrics;
}

test.describe("stock analysis layout density guard", () => {
  test.skip(
    dataSource !== "real",
    "Stock analysis layout-density guard requires process.env.VITE_DATA_SOURCE === 'real' with spec-local Livermore routes.",
  );

  for (const viewport of viewports) {
    test(`keeps the stock-analysis queue dense without horizontal overflow at ${viewport.name}px`, async ({
      page,
    }) => {
      const metrics = await openStockAnalysis(page, viewport);
      if (shouldLogLayoutMetrics) {
        console.log(`[stock-analysis-density] ${viewport.name}px ${JSON.stringify(metrics)}`);
      }

      expect(metrics.queueVisible).toBe(true);
      expect(metrics.queueTop).not.toBeNull();
      expect(metrics.queueTop).toBeGreaterThanOrEqual(0);
      expect(metrics.queueTop).toBeLessThan(viewport.height);
      expect(metrics.overflow, JSON.stringify(metrics.overflow, null, 2)).toEqual([]);
      expect(metrics.documentScrollWidth).toBeLessThanOrEqual(viewport.width + 2);
      expect(metrics.bodyScrollWidth).toBeLessThanOrEqual(viewport.width + 2);

      if (viewport.expectVisibleRows != null) {
        expect(metrics.visibleRowCount).toBe(viewport.expectVisibleRows);
      }

      if (viewport.expectFirstViewportRowsMin != null) {
        expect(metrics.firstViewportRowCount).toBeGreaterThanOrEqual(viewport.expectFirstViewportRowsMin);
      }
    });
  }
});
