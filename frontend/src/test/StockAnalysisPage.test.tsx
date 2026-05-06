import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import type {
  ApiEnvelope,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyPayload,
} from "../api/contracts";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

function buildStrategyPayload(
  overrides: Partial<LivermoreStrategyPayload> = {},
): LivermoreStrategyPayload {
  return {
    as_of_date: "2026-04-29",
    requested_as_of_date: null,
    strategy_name: "Livermore A-Share Defended Trend",
    basis: "analytical",
    market_gate: {
      state: "WARM",
      exposure: 0.4,
      passed_conditions: 2,
      available_conditions: 2,
      required_conditions: 4,
      conditions: [
        {
          key: "csi300_close_gt_ma60",
          label: "CSI300 close > MA60",
          status: "pass",
          evidence: "Close is above MA60.",
          source_series_id: "CA.CSI300",
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
    ],
    diagnostics: [
      {
        severity: "warning",
        code: "LIVERMORE_BREADTH_MISSING",
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
    unsupported_outputs: [],
    sector_rank: {
      as_of_date: "2026-04-29",
      formula_version: "rv_livermore_sector_rank_provisional_v1",
      is_provisional: true,
      sector_count: 1,
      excluded_constituent_count: 0,
      excluded_sector_count: 0,
      items: [
        {
          rank: 1,
          sector_code: "801001",
          sector_name: "AI",
          score: 1,
          avg_pctchange: 4.8,
          avg_turn: 3,
          avg_amplitude: 3.5,
          constituent_count: 12,
        },
      ],
    },
    stock_candidates: {
      as_of_date: "2026-04-29",
      formula_version: "rv_livermore_stock_candidates_bundle_v1",
      market_state: "WARM",
      input_stock_count: 1,
      candidate_count: 1,
      excluded_stock_count: 0,
      insufficient_history_count: 0,
      items: [
        {
          rank: 1,
          stock_code: "000001.SZ",
          stock_name: "Alpha",
          sector_code: "801001",
          sector_name: "AI",
          sector_rank: 1,
          close: 21.9,
          breakout_level: 21.8,
          ema10: 20.6,
          ma20: 21.05,
          ma60: 19.05,
          ma120: 16.05,
          close_strength: 0.833333,
          gap_norm: -0.114679,
          abnormal_turnover: 1.386294,
        },
      ],
    },
    risk_exit: {
      as_of_date: "2026-04-29",
      formula_version: "rv_livermore_risk_exit_ema10_mvp_v1",
      position_count: 1,
      signal_count: 1,
      excluded_position_count: 0,
      insufficient_history_count: 0,
      items: [
        {
          stock_code: "000001.SZ",
          stock_name: "Alpha",
          reason: "2d_below_ema10",
          entry_cost: 10.5,
          bars_since_entry: 6,
          latest_close: 9.1,
          latest_ema10: 10.2,
          prior_close: 9.8,
          prior_ema10: 10.4,
        },
      ],
      watch_items: [
        {
          stock_code: "000777.SZ",
          stock_name: "Watch Alpha",
          entry_cost: 19.5,
          bars_since_entry: 4,
          latest_close: 19.8,
          latest_ema10: 20.1,
          prior_close: 20.4,
          prior_ema10: 20,
          exit_watch_price: 20.1,
          triggered: false,
        },
      ],
    },
    ...overrides,
  };
}

function buildConfluencePayload(): LivermoreSignalConfluencePayload {
  return {
    as_of_date: "2026-04-29",
    macro_context: {
      status: "neutral",
      composite_score: 0.05,
      multiplier: 0.5,
    },
    strategy_context: {
      market_gate_state: "WARM",
      market_gate_exposure: 0.4,
      allows_new_entry_observations: true,
    },
    position_size_hint: 0.2,
    entry_observations: [],
    exit_observations: [
      {
        stock_code: "000777.SZ",
        stock_name: "Watch Alpha",
        action: "observe_exit_watch",
        current_price: 19.8,
        exit_watch_price: 20.1,
        triggered: false,
        evidence: ["退出观察价来自 Livermore EMA10。"],
      },
    ],
    diagnostics: [],
    disclaimer: "Observation-only output.",
  };
}

function stockClient(options?: {
  strategy?: LivermoreStrategyPayload;
  strategyError?: Error;
  confluenceError?: Error;
}): ApiClient {
  return {
    ...createApiClient({ mode: "mock" }),
    getLivermoreStrategy: async (): Promise<ApiEnvelope<LivermoreStrategyPayload>> => {
      if (options?.strategyError) {
        throw options.strategyError;
      }
      return buildMockApiEnvelope(
        "market_data.livermore",
        options?.strategy ?? buildStrategyPayload(),
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_livermore_test",
          vendor_version: "vv_livermore_test",
          rule_version: "rv_livermore_market_gate_v1",
        },
      );
    },
    getLivermoreSignalConfluence: async (): Promise<
      ApiEnvelope<LivermoreSignalConfluencePayload>
    > => {
      if (options?.confluenceError) {
        throw options.confluenceError;
      }
      return buildMockApiEnvelope(
        "market_data.livermore.signal_confluence",
        buildConfluencePayload(),
      );
    },
  };
}

describe("StockAnalysisPage", () => {
  it("renders the five core sections and candidate evidence", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    expect(await screen.findByRole("heading", { name: "股票分析" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "市场状态" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "行业强弱" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "候选股证据卡" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "风险退出观察" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "银行股专题待补证据" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "数据口径与边界" })).toBeInTheDocument();

    const candidate = screen.getByTestId("stock-candidate-000001.SZ");
    expect(candidate).toHaveTextContent("Alpha");
    expect(candidate).toHaveTextContent("行业排名第 1");
    expect(candidate).toHaveTextContent("基本面与估值证据未接入");
    expect(candidate).toHaveTextContent("新闻、公告、财报事件尚未进入候选卡");
    expect(candidate).toHaveTextContent("10EMA");
  });

  it("shows bank fundamental evidence as pending and avoids forbidden trading copy", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    expect(await screen.findByText(/PB \/ ROE \/ 分红率 \/ NIM/)).toBeInTheDocument();
    expect(screen.getByText(/当前仅展示待补字段，不参与候选排序/)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText(/买入建议/)).not.toBeInTheDocument();
      expect(screen.queryByText(/卖出建议/)).not.toBeInTheDocument();
      expect(screen.queryByText(/下单/)).not.toBeInTheDocument();
      expect(screen.queryByText(/调仓指令/)).not.toBeInTheDocument();
    });
  });

  it("shows strategy API failure state", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({ strategyError: new Error("strategy unavailable") }),
    });

    expect(await screen.findByText("股票分析结果加载失败。")).toBeInTheDocument();
    expect(screen.getByText("strategy unavailable")).toBeInTheDocument();
  });

  it("keeps the page usable when signal confluence fails", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({ confluenceError: new Error("confluence unavailable") }),
    });

    expect(await screen.findByRole("heading", { name: "风险退出观察" })).toBeInTheDocument();
    expect(await screen.findByText("联动观察暂不可用。")).toBeInTheDocument();
  });

  it("shows an empty state when there are no candidates", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          stock_candidates: {
            as_of_date: "2026-04-29",
            formula_version: "rv_livermore_stock_candidates_bundle_v1",
            market_state: "WARM",
            input_stock_count: 0,
            candidate_count: 0,
            excluded_stock_count: 0,
            insufficient_history_count: 0,
            items: [],
          },
        }),
      }),
    });

    const section = await screen.findByTestId("stock-analysis-candidates-section");
    expect(within(section).getByText("当前无候选股证据卡。")).toBeInTheDocument();
  });
});
