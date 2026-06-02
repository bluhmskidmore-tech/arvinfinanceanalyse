import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiEnvelope, ResultMeta } from "../api/contracts";
import { createApiClient, type ApiClient } from "../api/client";
import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitStrategySummariesPayload,
} from "../api/macroToolkitClient";
import { renderWorkbenchApp } from "./renderWorkbenchApp";
import { PORTFOLIO_MODULE_DRILLDOWN_COUNT } from "../features/workbench/module-home/portfolioModuleDrilldowns";
import { MARKET_MODULE_DRILLDOWN_COUNT } from "../features/workbench/module-home/marketModuleDrilldowns";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="module-home-echarts-stub" />,
}));

function renderAt(path: string, client?: ApiClient) {
  return renderWorkbenchApp([path], {
    client: client ?? createApiClient({ mode: "mock" }),
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((innerResolve, innerReject) => {
    resolve = innerResolve;
    reject = innerReject;
  });
  return { promise, resolve, reject };
}

function testMeta(resultKind: string): ResultMeta {
  return {
    trace_id: `${resultKind}_trace`,
    basis: "analytical",
    result_kind: resultKind,
    formal_use_allowed: false,
    source_version: "sv_test",
    vendor_version: "vv_test",
    rule_version: "rv_test",
    cache_version: "cv_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-06-01T00:00:00Z",
  };
}

function coreMacroAnalysisEnvelope(): ApiEnvelope<MacroToolkitAnalysisPayload> {
  return {
    result_meta: testMeta("macro_toolkit.analysis"),
    result: {
      default_data_sources: ["choice"],
      as_of_date: "2026-04-30",
      conclusion: {
        stance: "中性观察",
        tone: "neutral",
        summary: "核心宏观信号已返回。",
        recommended_action: "等待候选策略摘要补齐。",
      },
      coverage: {
        indicator_count: 8,
        hit_count: 7,
        hit_rate: 0.875,
        script_count: 24,
        output_file_count: 0,
      },
      indicators: [],
      signal_cards: [],
      capability_results: [],
      strategy_summaries: [],
      output_files: [],
      source_checks: [],
      capabilities: [],
      warnings: [],
    },
  };
}

function strategySummariesEnvelope(): ApiEnvelope<MacroToolkitStrategySummariesPayload> {
  return {
    result_meta: testMeta("macro_toolkit.analysis.strategy_summaries"),
    result: {
      strategy_summaries: [],
    },
  };
}

describe("ModuleWorkbenchHomePage", () => {
  it.each([
    ["/market-overview", "市场工作台"],
    ["/risk-overview", "风险工作台"],
    ["/performance", "绩效工作台"],
    ["/reports", "报表与数据"],
  ])("renders the dedicated module home for %s", async (path, title) => {
    renderAt(path);

    const page = await screen.findByTestId("module-workbench-home");
    expect(page).toHaveTextContent(title);
    expect(within(page).getByTestId("module-home-kpi-strip")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-status-strip")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-briefing")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-drilldowns")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-data-note")).toBeInTheDocument();
  });

  it("shows explicit fallback states when a source query fails", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getRiskTensorDates: async () => {
        throw new Error("risk dates unavailable");
      },
    };

    renderAt("/risk-overview", client);

    const page = await screen.findByTestId("module-workbench-home");
    expect(page).toHaveTextContent("读取失败");
    expect(page).toHaveTextContent("不使用前端补数");
  });

  it("renders market key rate snapshot from choice and market-data reads", async () => {
    renderAt("/market-overview");

    const page = await screen.findByTestId("module-workbench-home");
    expect(within(page).getByTestId("module-home-rate-snapshot")).toBeInTheDocument();
    expect(page).toHaveTextContent("关键利率快照");
    expect(page).toHaveTextContent("正式利率序列");
    await waitFor(() => {
      expect(page).toHaveTextContent("DR007");
    });
  });

  it("renders risk tensor and cashflow detail cards from backend reads", async () => {
    renderAt("/risk-overview");

    const page = await screen.findByTestId("module-workbench-home");
    expect(within(page).getByTestId("module-home-risk-tensor")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-cashflow")).toBeInTheDocument();
    expect(page).toHaveTextContent("风险张量明细");
    expect(page).toHaveTextContent("现金流与缺口");
    await waitFor(() => {
      expect(page).toHaveTextContent("KRD 5Y");
      expect(page).toHaveTextContent("CS01");
      expect(page).toHaveTextContent("久期缺口");
    });
    expect(page).toHaveTextContent("来源 risk-tensor");
    expect(page).toHaveTextContent("来源 cashflow-projection");
  });

  it("renders performance kpi detail and business pnl cards from backend reads", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getKpiValuesSummary: async () => ({
        owner_id: 1,
        owner_name: "固定收益部",
        year: 2026,
        period_type: "YEAR",
        period_label: "2026年度",
        period_start_date: "2026-01-01",
        period_end_date: "2026-05-31",
        metrics: [
          {
            metric_id: 101,
            metric_code: "KPI_BOND_YIELD",
            metric_name: "债券投资收益率",
            major_category: "收益类",
            target_value: "4.50",
            unit: "%",
            score_weight: "15.00",
            period_actual_value: "4.20",
            period_score_value: "12.50",
            period_start_date: "2026-01-01",
            period_end_date: "2026-05-31",
            data_date: "2026-05-31",
          },
        ],
        total: 1,
        total_weight: "100.00",
        total_score: "12.50",
      }),
      getPnlByBusinessYtd: async (year) => ({
        result_meta: {
          trace_id: "perf_home_pnl",
          basis: "formal",
          result_kind: "pnl.by_business_ytd",
          formal_use_allowed: true,
          source_version: "sv_test",
          vendor_version: "vv_test",
          rule_version: "rv_test",
          cache_version: "cv_test",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-06-01T00:00:00Z",
        },
        result: {
          year,
          period_type: "yearly",
          period_label: "2026年累计",
          period_start_date: "2026-01-01",
          period_end_date: "2026-05-31",
          total_pnl: "100000000",
          source_tables: ["fact_formal_pnl_fi"],
          items: [
            {
              row_key: "zqtz",
              sort_order: 1,
              business_type: "债券投资",
              interest_income: "80000000",
              fair_value_change: "10000000",
              capital_gain: "10000000",
              manual_adjustment: "0",
              total_pnl: "100000000",
              current_balance: "5000000000",
              balance_yield_pct: "0.02",
              proportion: "0.65",
              assets_count: 120,
            },
          ],
        },
      }),
    };

    renderAt("/performance", client);

    const page = await screen.findByTestId("module-workbench-home");
    expect(within(page).getByTestId("module-home-kpi-detail")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-business-pnl")).toBeInTheDocument();
    expect(page).toHaveTextContent("KPI 指标明细");
    expect(page).toHaveTextContent("业务种类损益");
    await waitFor(() => {
      expect(page).toHaveTextContent("债券投资收益率");
      expect(page).toHaveTextContent("债券投资");
      expect(page).toHaveTextContent("1 亿元");
    });
    expect(page).toHaveTextContent("来源 kpi");
    expect(page).toHaveTextContent("来源 pnl/by-business");
  });

  it("renders governance source status and cube dimension cards from backend reads", async () => {
    renderAt("/reports");

    const page = await screen.findByTestId("module-workbench-home");
    expect(within(page).getByTestId("module-home-source-status")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-cube-dimensions")).toBeInTheDocument();
    expect(page).toHaveTextContent("数据源状态");
    expect(page).toHaveTextContent("Cube 维度与度量");
    expect(page).toHaveTextContent("规划中");
    await waitFor(() => {
      expect(page).toHaveTextContent("ZQTZ");
      expect(page).toHaveTextContent("asset_class_std");
      expect(page).toHaveTextContent("bond_analytics");
    });
    expect(page).toHaveTextContent("来源 source-foundation");
    expect(page).toHaveTextContent("来源 cube / bond_analytics");
  });
});

describe("PortfolioHomePage", () => {
  it("renders portfolio-specific home content, not dashboard-home blocks", async () => {
    renderAt("/portfolio");

    const page = await screen.findByTestId("module-workbench-home");
    expect(page).toHaveTextContent("组合工作台");
    expect(within(page).getByTestId("module-home-toolbar")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-kpi-strip")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-briefing")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-status-strip")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-drilldowns")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-data-note")).toBeInTheDocument();
    expect(within(page).queryByTestId("dashboard-home-hero")).not.toBeInTheDocument();
    expect(within(page).queryByTestId("dashboard-home-work-grid")).not.toBeInTheDocument();
  });

  it("renders portfolio balance and bond read summaries", async () => {
    renderAt("/portfolio");

    const page = await screen.findByTestId("module-workbench-home");
    await waitFor(() => {
      expect(page).toHaveTextContent("规模与错配");
      expect(page).toHaveTextContent("风险敏感度");
      expect(page).toHaveTextContent("资产侧");
      expect(page).toHaveTextContent("负债侧");
    });
  });

  it("renders portfolio holdings structure and depth panels", async () => {
    renderAt("/portfolio");

    const page = await screen.findByTestId("module-workbench-home");
    expect(within(page).getByTestId("module-home-holdings-structure")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-portfolio-terminal")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-portfolio-risk")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-pnl-summary")).toBeInTheDocument();
    await waitFor(() => {
      expect(page).toHaveTextContent("券种分布");
      expect(page).toHaveTextContent("评级分布");
      expect(page).toHaveTextContent("行业分布");
      expect(page).toHaveTextContent("期限分布");
      expect(page).toHaveTextContent("收益率分布");
    });
    const holdings = within(page).getByTestId("module-home-holdings-structure");
    expect(within(holdings).getByTestId("module-home-distribution-yield")).toBeInTheDocument();
    expect(within(holdings).getAllByRole("link", { name: "查看全部" }).length).toBeGreaterThanOrEqual(5);
    expect(within(holdings).getByRole("link", { name: "持仓透视" })).toHaveAttribute("href", "/positions");
  });

  it("renders structure tab chart beside portfolio comparison list", async () => {
    renderAt("/portfolio");

    const page = await screen.findByTestId("module-workbench-home");
    const terminal = within(page).getByTestId("module-home-portfolio-terminal");
    await waitFor(() => {
      expect(within(terminal).getByTestId("module-home-structure-chart")).toBeInTheDocument();
    });
  });

  it("renders all portfolio module drilldown links", async () => {
    renderAt("/portfolio");

    const page = await screen.findByTestId("module-workbench-home");
    const drilldowns = within(page).getByTestId("module-home-drilldowns");
    const links = within(drilldowns).getAllByRole("link");
    expect(links).toHaveLength(PORTFOLIO_MODULE_DRILLDOWN_COUNT);
    expect(page).toHaveTextContent("债券分析");
    expect(page).toHaveTextContent("余额变动分析");
    expect(page).toHaveTextContent("负债结构分析");
    expect(page).toHaveTextContent("日均分析");
    expect(page).toHaveTextContent("总账损益");
    expect(page).toHaveTextContent("银行台账");
    expect(page).toHaveTextContent("产品分析");
    expect(page).toHaveTextContent("收益分析");
    expect(page).toHaveTextContent("损益桥接");
    expect(page).toHaveTextContent("业务种类损益");
  });

  it("renders portfolio drilldown links to balance and attribution pages", async () => {
    renderAt("/portfolio");

    const page = await screen.findByTestId("module-workbench-home");
    expect(page).toHaveTextContent("资产负债分析");
    expect(page).toHaveTextContent("收益归因");
    expect(page).toHaveTextContent("持仓透视");
  });
});

describe("MarketHomePage", () => {
  it("requests core macro analysis before deferred strategy summaries", async () => {
    const base = createApiClient({ mode: "mock" });
    const analysis = deferred<ApiEnvelope<MacroToolkitAnalysisPayload>>();
    const getMacroToolkitAnalysis = vi.fn(() => analysis.promise);
    const getMacroToolkitStrategySummaries = vi.fn(async () => strategySummariesEnvelope());
    const client: ApiClient = {
      ...base,
      getMacroToolkitAnalysis,
      getMacroToolkitStrategySummaries,
    };

    renderAt("/market-overview", client);

    await waitFor(() => {
      expect(getMacroToolkitAnalysis).toHaveBeenCalledWith({ detail: "core" });
    });
    expect(getMacroToolkitStrategySummaries).not.toHaveBeenCalled();

    analysis.resolve(coreMacroAnalysisEnvelope());

    await waitFor(() => {
      expect(getMacroToolkitStrategySummaries).toHaveBeenCalledTimes(1);
    });
  });

  it("renders market-specific home content with portfolio-style layout", async () => {
    renderAt("/market-overview");

    const page = await screen.findByTestId("module-workbench-home");
    expect(page).toHaveTextContent("市场工作台");
    expect(within(page).getByTestId("module-home-toolbar")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-kpi-strip")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-briefing")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-status-strip")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-drilldowns")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-data-note")).toBeInTheDocument();
    expect(within(page).queryByTestId("dashboard-home-hero")).not.toBeInTheDocument();
  });

  it("renders market key rate snapshot and terminal tabs from market-data reads", async () => {
    renderAt("/market-overview");

    const page = await screen.findByTestId("module-workbench-home");
    expect(within(page).getByTestId("module-home-rate-snapshot")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-market-terminal")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-yield-curve")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-macro-snapshot")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-macro-toolkit")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-observation")).toBeInTheDocument();
    expect(page).toHaveTextContent("关键利率快照");
    expect(page).toHaveTextContent("正式利率序列");
    expect(page).toHaveTextContent("跨资产快讯");
    expect(page).toHaveTextContent("国债与国开曲线");
    await waitFor(() => {
      expect(page).toHaveTextContent("DR007");
      expect(within(page).getByTestId("module-home-macro-signals")).toBeInTheDocument();
      expect(page).toHaveTextContent("中性观察");
      expect(page).toHaveTextContent("流动性");
      expect(within(page).getByTestId("module-home-macro-a-share-risk")).toBeInTheDocument();
      expect(within(page).getByTestId("module-home-macro-hason")).toBeInTheDocument();
      expect(within(page).getByTestId("module-home-macro-shadow")).toBeInTheDocument();
      expect(within(page).getByTestId("module-home-macro-runtime")).toBeInTheDocument();
      expect(page).toHaveTextContent("橙色风险");
      expect(page).toHaveTextContent("影子组合报告");
    });
  });

  it("renders all market module drilldown links", async () => {
    renderAt("/market-overview");

    const page = await screen.findByTestId("module-workbench-home");
    const drilldowns = within(page).getByTestId("module-home-drilldowns");
    const links = within(drilldowns).getAllByRole("link");
    expect(links).toHaveLength(MARKET_MODULE_DRILLDOWN_COUNT);
    expect(page).toHaveTextContent("宏观工具");
    expect(page).toHaveTextContent("股票分析");
  });
});
