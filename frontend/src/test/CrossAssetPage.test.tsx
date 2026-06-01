import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="cross-asset-echarts-stub" />,
}));

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { LivermoreOutputKey } from "../api/contracts";
import CrossAssetPage from "../features/cross-asset/pages/CrossAssetPage";

const CROSS_ASSET_DRIVERS_CSS_PATH = resolve(
  process.cwd(),
  "src/features/cross-asset/pages/CrossAssetDriversPage.css",
);

function renderPage(client: ApiClient = createApiClient({ mode: "mock" })) {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
          },
        }),
    );

    return (
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <ApiClientProvider client={client}>{children}</ApiClientProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );
  }

  return render(
    <Wrapper>
      <CrossAssetPage />
    </Wrapper>,
  );
}

describe("CrossAssetPage", () => {
  it("keeps page-local decorative colors on the homepage blue-gray token family", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");

    expect(css).not.toMatch(/moss-color-warm-/);
    expect(css).not.toMatch(/rgba\((255, 253, 248|246, 241, 232|255, 250, 242|121, 96, 74|112, 140, 116|52, 43, 39)/);
    expect(css).not.toMatch(/#(fffdf8|f0e6d8|e4d8c8|b8a38f|342b27|6f6258|8f7e70|b85c38|708c74|7c3e46|667a96)/i);
    expect(css).toContain("var(--moss-color-primary-600)");
    expect(css).toContain("var(--moss-color-info-600)");
    expect(css).toContain("var(--moss-color-success-600)");
    expect(css).toContain("var(--moss-color-danger-600)");
    expect(css).toContain("var(--moss-color-warning-600)");
    expect(css).toContain("var(--moss-color-text-muted)");
  });

  it("scopes desktop shell compression to the cross-asset route only", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");

    expect(css).toContain("@media (min-width: 901px)");
    expect(css).toContain(
      '.workbench-shell-grid--desktop-aligned:has([data-testid="cross-asset-drivers-page"])',
    );
    expect(css).toContain('[data-testid="workbench-governance-banner"]');
    expect(css).not.toContain(
      '.workbench-shell-grid--desktop-aligned [data-testid="workbench-section-subnav"] > div:first-child {\n    display: none',
    );
  });

  it("renders dual-source stock evidence from the default mock latest-series contract", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("cross-asset-status-flags")).toHaveTextContent("双源就绪");
    });

    const evidence = await screen.findByTestId("cross-asset-equity-evidence");
    expect(evidence).toHaveTextContent("Tushare");
    expect(evidence).toHaveTextContent("CA.CSI300");
    expect(evidence).toHaveTextContent("CA.CSI300_PE");
    expect(evidence).toHaveTextContent("CA.MEGA_CAP_WEIGHT");
    expect(evidence).toHaveTextContent("CA.MEGA_CAP_TOP5_WEIGHT");

    const broadIndex = screen.getByTestId("cross-asset-equity-evidence-broad_index");
    expect(broadIndex).toHaveTextContent("index");
    expect(broadIndex).toHaveTextContent("Tushare");
  });

  it("uses the displayed cross-asset data date for linkage analysis", async () => {
    const client = createApiClient({ mode: "mock" });
    const latestPayload = await client.getChoiceMacroLatest();
    const baseCsi300 = latestPayload.result.series.find((point) => point.series_id === "CA.CSI300")!;
    const getMacroBondLinkageAnalysis = vi.spyOn(client, "getMacroBondLinkageAnalysis");

    vi.spyOn(client, "getChoiceMacroLatest").mockResolvedValue({
      ...latestPayload,
      result: {
        ...latestPayload.result,
        series: [
          ...latestPayload.result.series.map((point) =>
            ["E1000180", "E1003238", "EM1", "CA.DR007", "CA.CSI300"].includes(point.series_id)
              ? { ...point, trade_date: "2026-05-29" }
              : point,
          ),
          {
            ...baseCsi300,
            series_id: "NON_HEADLINE_MACRO",
            series_name: "非首屏宏观序列",
            trade_date: "2026-05-30",
          },
        ],
      },
    });

    renderPage(client);

    const hero = await screen.findByTestId("cross-asset-decision-hero");
    await waitFor(() => {
      expect(hero).toHaveTextContent("数据日期 2026-05-29");
      expect(getMacroBondLinkageAnalysis).toHaveBeenCalledWith({ reportDate: "2026-05-29" });
    });
    expect(getMacroBondLinkageAnalysis).not.toHaveBeenCalledWith({ reportDate: "2026-05-30" });
  });

  it("renders the compact decision cockpit before the deep evidence stack", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    const hero = await screen.findByTestId("cross-asset-decision-hero");
    const statusStrip = await screen.findByTestId("cross-asset-data-status-strip");
    const firstScreenGrid = await screen.findByTestId("cross-asset-first-screen-grid");
    const researchViews = await screen.findByTestId("cross-asset-research-views");
    const fullKpiBand = await screen.findByTestId("cross-asset-kpi-band");
    const livermoreStatus = await screen.findByTestId("cross-asset-livermore-status");
    const observationSupport = await screen.findByTestId("cross-asset-observation-support-grid");
    const waterfallEvidence = await screen.findByTestId("cross-asset-driver-waterfall-evidence");
    const momentumScoreboard = await screen.findByTestId("cross-asset-momentum-scoreboard");
    const correlationHeatmap = await screen.findByTestId("cross-asset-correlation-heatmap");
    const momentumTable = await screen.findByTestId("cross-asset-momentum-table-wrap");
    const correlationMatrix = await screen.findByTestId("cross-asset-correlation-matrix-wrap");

    expect(hero).toHaveTextContent("外部变量今天怎样传导到债券");
    expect(statusStrip).toHaveTextContent("宏观");
    expect(statusStrip).toHaveTextContent("联动");
    expect(firstScreenGrid).toContainElement(researchViews);
    expect(screen.queryByTestId("cross-asset-headline-kpis")).not.toBeInTheDocument();
    expect(observationSupport).toContainElement(momentumScoreboard);
    expect(observationSupport).toContainElement(correlationHeatmap);
    expect(momentumTable).toBeInTheDocument();
    expect(correlationMatrix).toBeInTheDocument();
    expect(waterfallEvidence).toHaveTextContent("综合");
    expect(fullKpiBand.querySelectorAll(".cross-asset-drivers-page__mini-kpi").length).toBeGreaterThanOrEqual(4);
    expect(Boolean(researchViews.compareDocumentPosition(fullKpiBand) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(fullKpiBand.compareDocumentPosition(livermoreStatus) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });

  it("renders first-screen investment research judgments from backend additive fields", async () => {
    const client = createApiClient({ mode: "mock" });
    const latestPayload = await client.getChoiceMacroLatest();
    const baseCsi300 = latestPayload.result.series.find((point) => point.series_id === "CA.CSI300")!;
    vi.spyOn(client, "getChoiceMacroLatest").mockResolvedValue({
      ...latestPayload,
      result_meta: {
        ...latestPayload.result_meta,
        vendor_status: "vendor_unavailable",
      },
      result: {
        ...latestPayload.result,
        series: [
          ...latestPayload.result.series.map((point) =>
            point.series_id === "CA.CSI300"
              ? {
                  ...point,
                  trade_date: "2026-02-28",
                }
              : point,
          ),
          {
            ...baseCsi300,
            series_id: "CA.CSI300_PE",
            series_name: "沪深300市盈率",
            value_numeric: 14.58,
            unit: "x",
            refresh_tier: "fallback",
            latest_change: 0.16,
          },
          {
            ...baseCsi300,
            series_id: "CA.MEGA_CAP_WEIGHT",
            series_name: "沪深300前十大权重",
            trade_date: "2026-04-01",
            value_numeric: 23.5367,
            unit: "%",
            latest_change: 0.2,
          },
          {
            ...baseCsi300,
            series_id: "CA.MEGA_CAP_TOP5_WEIGHT",
            series_name: "沪深300前五大权重",
            trade_date: "2026-04-01",
            value_numeric: 15.532,
            unit: "%",
            latest_change: 0.1,
          },
        ],
      },
    });
    const linkagePayload = await client.getMacroBondLinkageAnalysis({ reportDate: "2026-04-10" });

    vi.spyOn(client, "getMacroBondLinkageAnalysis").mockResolvedValue({
      ...linkagePayload,
      result: {
        ...linkagePayload.result,
        research_views: [
          {
            key: "duration",
            status: "ready",
            stance: "bullish",
            confidence: "high",
            summary: "Duration view favors adding exposure.",
            affected_targets: ["rates", "ncd", "high_grade_credit"],
            evidence: ["Liquidity remains supportive."],
          },
          {
            key: "curve",
            status: "ready",
            stance: "barbell",
            confidence: "medium",
            summary: "Curve view prefers front-end carry with selective extension.",
            affected_targets: ["rates", "ncd"],
            evidence: ["Funding stays loose."],
          },
          {
            key: "credit",
            status: "ready",
            stance: "selective",
            confidence: "medium",
            summary: "Credit view stays focused on high grade.",
            affected_targets: ["high_grade_credit"],
            evidence: ["Spread beta remains controlled."],
          },
          {
            key: "instrument",
            status: "ready",
            stance: "barbell",
            confidence: "medium",
            summary: "Instrument view prefers rates plus high-grade credit.",
            affected_targets: ["rates", "ncd", "high_grade_credit"],
            evidence: ["Cross-asset evidence is mixed but constructive."],
          },
        ],
        transmission_axes: [
          {
            axis_key: "global_rates",
            status: "ready",
            stance: "restrictive",
            summary: "Global rates cap aggressive long-end chasing.",
            impacted_views: ["duration", "curve"],
            required_series_ids: ["UST10Y"],
            warnings: [],
          },
          {
            axis_key: "equity_bond_spread",
            status: "ready",
            stance: "conflicted",
            summary: "CSI300 equity-bond spread is 5.10ppt with CSI300 move -0.35%.",
            impacted_views: ["duration", "credit"],
            required_series_ids: ["tushare.index.000300.SH.daily", "tushare.index.000300.SH.dailybasic"],
            warnings: [],
          },
          {
            axis_key: "mega_cap_equities",
            status: "ready",
            stance: "neutral",
            summary: "CSI300 top10 weight concentration is 23.54% (top5 15.53%).",
            impacted_views: ["credit", "instrument"],
            required_series_ids: ["tushare.index.000300.SH.weight"],
            warnings: [],
          },
        ],
      },
    });

    renderPage(client);

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    expect(await screen.findByTestId("cross-asset-ncd-proxy")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-ncd-proxy-warning")).toBeInTheDocument();
    await waitFor(() => {
      const warning = screen.getByTestId("cross-asset-ncd-proxy-warning");
      expect(warning).toHaveTextContent(/not actual NCD issuance matrix/i);
      expect(warning).toHaveTextContent(/landed|quote medians unavailable/i);
    });
    expect(await screen.findByText("Duration view favors adding exposure.")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-research-views")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-transmission-axes")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-research-card-duration")).toHaveTextContent(
      "Duration view favors adding exposure.",
    );
    expect(screen.getByTestId("cross-asset-research-card-instrument")).toHaveTextContent(
      "Instrument view prefers rates plus high-grade credit.",
    );
    expect(screen.getByTestId("cross-asset-transmission-axis-global_rates")).toHaveTextContent(
      "Global rates cap aggressive long-end chasing.",
    );
    expect(screen.getByTestId("cross-asset-transmission-axis-global_rates")).toHaveTextContent("已就绪");
    expect(screen.getByTestId("cross-asset-transmission-axis-global_rates")).toHaveTextContent("偏紧");
    expect(screen.getByTestId("cross-asset-transmission-axis-equity_bond_spread")).toHaveTextContent(
      "CSI300 equity-bond spread",
    );
    expect(screen.getByTestId("cross-asset-transmission-axis-mega_cap_equities")).toHaveTextContent("23.54%");
    expect(screen.getByTestId("cross-asset-asset-class-analysis")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-stock")).toHaveTextContent("股票分析");
    expect(screen.getByTestId("cross-asset-asset-analysis-commodities")).toHaveTextContent("大宗商品");
    expect(screen.getByTestId("cross-asset-asset-analysis-options")).toHaveTextContent("期权");
    expect(screen.getByTestId("cross-asset-asset-analysis-options")).toHaveTextContent("\u5f85\u63a5\u5165");
    expect(screen.getByTestId("cross-asset-asset-class-analysis")).toHaveTextContent("\u8de8\u8d44\u4ea7\u7ed3\u8bba");
    expect(screen.getByTestId("cross-asset-asset-class-analysis")).toHaveTextContent("\u5f85\u63a5\u5165\u6e05\u5355");
    expect(screen.getByTestId("cross-asset-asset-class-judgment")).toHaveTextContent("\u503a\u5238\u4f20\u5bfc\u5224\u65ad");
    expect(screen.getByTestId("cross-asset-asset-class-analysis")).toHaveTextContent("Choice");
    expect(screen.getByTestId("cross-asset-asset-class-analysis")).toHaveTextContent("Tushare");
    expect(screen.getByTestId("cross-asset-status-flags")).toHaveTextContent("来源受限");
    const stockBroadIndex = screen.getByTestId("cross-asset-asset-analysis-stock-broad_index");
    expect(stockBroadIndex).toBeInTheDocument();
    expect(stockBroadIndex).toHaveTextContent("来源受限");
    expect(stockBroadIndex).not.toHaveTextContent("EMM01843735");
    expect(stockBroadIndex.querySelector(".cross-asset-class-analysis__line-source")?.getAttribute("title")).toContain(
      "EMM01843735",
    );
    expect(screen.getByTestId("cross-asset-asset-analysis-stock-valuation_spread")).toHaveTextContent("14.58");
    expect(screen.getByTestId("cross-asset-asset-analysis-stock-mega_cap_weight")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-stock-mega_cap_weight")).toHaveTextContent("23.54%");
    expect(screen.getByTestId("cross-asset-asset-analysis-stock-mega_cap_weight")).toHaveTextContent("15.53%");
    const equityEvidence = screen.getByTestId("cross-asset-equity-evidence");
    expect(equityEvidence).toHaveTextContent("EMM01843735");
    expect(equityEvidence).toHaveTextContent("CA.CSI300_PE");
    expect(equityEvidence).toHaveTextContent("CA.MEGA_CAP_WEIGHT");
    expect(equityEvidence).toHaveTextContent("CA.MEGA_CAP_TOP5_WEIGHT");
    expect(equityEvidence).toHaveTextContent("index");
    expect(equityEvidence).toHaveTextContent("x");
    expect(equityEvidence).toHaveTextContent("%");
    expect(screen.getByTestId("cross-asset-equity-evidence-broad_index")).toHaveTextContent("来源受限");
    expect(screen.getByTestId("cross-asset-equity-evidence-csi300_pe")).toHaveTextContent("降级");
    const commoditiesEnergy = screen.getByTestId("cross-asset-asset-analysis-commodities-energy");
    expect(commoditiesEnergy).toBeInTheDocument();
    expect(commoditiesEnergy).not.toHaveTextContent("CA.BRENT");
    expect(commoditiesEnergy.querySelector(".cross-asset-class-analysis__line-source")?.getAttribute("title")).toContain(
      "CA.BRENT",
    );
    const commoditiesFerrous = screen.getByTestId("cross-asset-asset-analysis-commodities-ferrous");
    expect(commoditiesFerrous).toBeInTheDocument();
    expect(commoditiesFerrous).not.toHaveTextContent("CA.STEEL");
    expect(commoditiesFerrous.querySelector(".cross-asset-class-analysis__line-source")?.getAttribute("title")).toContain(
      "CA.STEEL",
    );
    expect(screen.getByTestId("cross-asset-asset-analysis-commodities-nonferrous")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-options-equity_options")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-options-equity_options")).toHaveTextContent("Choice");
    expect(screen.getByTestId("cross-asset-asset-analysis-options-commodity_options")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-options-rates_bond_options")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-options")).not.toHaveTextContent("Evidence:");
  });

  it("surfaces incomplete A-share Livermore strategy status on the cross-asset page", async () => {
    const client = createApiClient({ mode: "mock" });
    const livermorePayload = await client.getLivermoreStrategy({ asOfDate: "2026-04-30" });
    const resultWithoutRiskExit = {
      ...livermorePayload.result,
      rule_readiness: livermorePayload.result.rule_readiness.map((rule) =>
        rule.key === "risk_exit"
          ? {
              ...rule,
              status: "blocked" as const,
              summary: "Risk and exit output is blocked because the position snapshot has no ACTIVE rows.",
              missing_inputs: ["positions", "entry_cost", "bars_since_entry", "close_history"],
            }
          : rule,
      ),
      supported_outputs: ["market_gate", "sector_rank", "stock_candidates"] as LivermoreOutputKey[],
      unsupported_outputs: [
        {
          key: "risk_exit" as const,
          reason: "livermore_position_snapshot has no ACTIVE A-share rows for as_of_date 2026-04-30.",
        },
      ],
    };
    delete resultWithoutRiskExit.risk_exit;
    vi.spyOn(client, "getLivermoreStrategy").mockResolvedValue({
      ...livermorePayload,
      result: resultWithoutRiskExit,
    });

    renderPage(client);

    const panel = await screen.findByTestId("cross-asset-livermore-status");
    await waitFor(() => {
      expect(client.getLivermoreStrategy).toHaveBeenCalled();
      expect(panel).toHaveTextContent("市场门控");
    });
    expect(panel).toHaveTextContent("A股策略状态");
    expect(panel).toHaveTextContent("个股候选");
    expect(panel).toHaveTextContent("风险退出");
    expect(panel).toHaveTextContent("缺持仓快照");
    expect(panel).toHaveTextContent("position snapshot");
    expect(screen.getByTestId("cross-asset-livermore-risk-exit")).toHaveTextContent("未闭环");
  });

  it("submits manually entered Livermore positions from the cross-asset page", async () => {
    const client = createApiClient({ mode: "mock" });
    const livermorePayload = await client.getLivermoreStrategy({ asOfDate: "2026-04-30" });
    const blockedResult = {
      ...livermorePayload.result,
      as_of_date: "2026-04-30",
      rule_readiness: livermorePayload.result.rule_readiness.map((rule) =>
        rule.key === "risk_exit"
          ? {
              ...rule,
              status: "blocked" as const,
              summary: "Position snapshot is missing.",
              missing_inputs: ["positions"],
            }
          : rule,
      ),
      supported_outputs: ["market_gate", "sector_rank", "stock_candidates"] as LivermoreOutputKey[],
      unsupported_outputs: [{ key: "risk_exit" as const, reason: "position snapshot is missing." }],
    };
    delete blockedResult.risk_exit;
    vi.spyOn(client, "getLivermoreStrategy").mockResolvedValue({
      ...livermorePayload,
      result: blockedResult,
    });
    const confluenceSpy = vi.spyOn(client, "getLivermoreSignalConfluence");
    const manualSpy = vi.spyOn(client, "materializeLivermoreManualPositionSnapshot").mockResolvedValue({
      status: "completed",
      fact_source: "livermore_position_snapshot",
      input_mode: "manual",
      as_of_date: "2026-04-30",
      row_count: 1,
      run_id: "livermore_position_snapshot:2026-04-30:test",
      source_file_hash: "sha256:test",
      source_systems: ["livermore_position_snapshot_manual"],
      source_version: "sv_livermore_position_test",
      vendor_version: "vv_livermore_position_manual_test",
      csv_path: null,
      risk_exit_input_status: "ready",
      risk_exit_input_block_reason: "",
    });

    renderPage(client);
    await screen.findByTestId("cross-asset-livermore-status");
    await waitFor(() => {
      expect(confluenceSpy).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(screen.getByTestId("cross-asset-livermore-confluence")).toHaveTextContent("Alpha");
    });
    fireEvent.change(await screen.findByLabelText("股票代码"), { target: { value: "000001.SZ" } });
    fireEvent.change(screen.getByLabelText("股票名称"), { target: { value: "Alpha" } });
    fireEvent.change(screen.getByLabelText("入场成本"), { target: { value: "10.5" } });
    fireEvent.change(screen.getByLabelText("持有天数"), { target: { value: "6" } });
    fireEvent.change(screen.getByLabelText("持仓数量"), { target: { value: "10000" } });
    fireEvent.click(screen.getByRole("button", { name: "保存持仓" }));

    await waitFor(() => {
      expect(manualSpy).toHaveBeenCalledWith({
        asOfDate: "2026-04-30",
        positions: [
          {
            stockCode: "000001.SZ",
            stockName: "Alpha",
            entryCost: 10.5,
            barsSinceEntry: 6,
            positionQuantity: 10000,
          },
        ],
      });
    });
    expect(await screen.findByText("已写入 1 条持仓快照。")).toBeInTheDocument();
    await waitFor(() => {
      expect(confluenceSpy.mock.calls.length).toBeGreaterThanOrEqual(2);
    });
    expect(confluenceSpy.mock.calls[0]?.[0]).toEqual({ asOfDate: "2026-04-30" });
    expect(confluenceSpy.mock.calls.at(-1)?.[0]).toEqual({ asOfDate: "2026-04-30" });
  });

  it("renders observation-only Livermore confluence rows with the same strategy date", async () => {
    type SignalConfluenceClient = ApiClient & {
      getLivermoreSignalConfluence: (options?: { asOfDate?: string }) => Promise<{
        result: {
          as_of_date: string;
          macro_context: {
            status: string;
            composite_score: number | null;
            description?: string;
          };
          strategy_context: {
            market_gate_state: string;
            position_size_hint: number | null;
            new_entry_observation_allowed: boolean;
          };
          entry_observations: Array<{
            action: string;
            stock_code: string;
            stock_name: string;
            current_price: number;
            buy_trigger_price: number | null;
            invalidation_reference_price: number | null;
            position_size_hint: number | null;
            evidence: string[];
          }>;
          exit_observations: Array<{
            action: string;
            stock_code: string;
            stock_name: string;
            current_price: number;
            exit_watch_price: number | null;
            triggered: boolean;
            evidence: string[];
          }>;
          diagnostics: Array<{
            severity: string;
            code: string;
            message: string;
          }>;
        };
      }>;
    };

    const client = createApiClient({ mode: "mock" }) as SignalConfluenceClient;
    const livermoreSpy = vi.spyOn(client, "getLivermoreStrategy");
    const confluenceSpy = vi.fn().mockResolvedValue({
      result: {
        as_of_date: "2026-04-30",
        macro_context: {
          status: "supportive",
          composite_score: -0.35,
          description: "宏观环境偏支持，但该面板仅供观察。",
        },
        strategy_context: {
          market_gate_state: "HOT",
          position_size_hint: 0.75,
          new_entry_observation_allowed: true,
        },
        entry_observations: [
          {
            action: "observe_entry_setup",
            stock_code: "000001.SZ",
            stock_name: "Alpha",
            current_price: 21.9,
            buy_trigger_price: 21.8,
            invalidation_reference_price: 20.6,
            position_size_hint: 0.5,
            evidence: ["突破位贴近买点", "量价配合待确认"],
          },
        ],
        exit_observations: [
          {
            action: "observe_exit_watch",
            stock_code: "000777.SZ",
            stock_name: "Watch Alpha",
            current_price: 19.8,
            exit_watch_price: 20.1,
            triggered: false,
            evidence: ["EMA10 失守前先观察"],
          },
        ],
        diagnostics: [
          "No risk exit watch items or triggered exit items available.",
          "Observation-only output. This service does not generate trading instructions.",
          {
            severity: "info",
            code: "observation_only",
            message: "仅供观察，不构成交易指令。",
          },
        ],
      },
    });
    client.getLivermoreSignalConfluence = confluenceSpy;

    renderPage(client);

    const panel = await screen.findByTestId("cross-asset-livermore-confluence");
    await waitFor(() => {
      expect(livermoreSpy).toHaveBeenCalled();
      expect(confluenceSpy).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(panel).toHaveTextContent("Alpha");
    });
    expect(confluenceSpy.mock.calls[0]?.[0]).toEqual(livermoreSpy.mock.calls[0]?.[0]);
    expect(panel).toHaveTextContent("宏观 × 策略观察点位");
    expect(panel).toHaveTextContent("仅供观察，不构成交易指令。");
    expect(panel).not.toHaveTextContent("message-0");
    expect(panel).not.toHaveTextContent("Observation-only output. This service does not generate trading instructions.");
    expect(panel).not.toHaveTextContent("No risk exit watch items or triggered exit items available.");
    expect(panel).toHaveTextContent("当前没有可展示的退出观察点位。");
    expect(panel).toHaveTextContent("候选触发价");
    expect(panel).toHaveTextContent("21.80");
    expect(panel).toHaveTextContent("退出观察价");
    expect(panel).toHaveTextContent("20.10");
    expect(panel).toHaveTextContent("突破位贴近买点");
    expect(panel).toHaveTextContent("EMA10 失守前先观察");
  });

  it("renders Livermore confluence diagnostics and empty observations when no rows are available", async () => {
    type SignalConfluenceClient = ApiClient & {
      getLivermoreSignalConfluence: (options?: { asOfDate?: string }) => Promise<{
        result: {
          as_of_date: string;
          macro_context: {
            status: string;
            composite_score: number | null;
          };
          strategy_context: {
            market_gate_state: string;
            position_size_hint: number | null;
            new_entry_observation_allowed: boolean;
          };
          entry_observations: unknown[];
          exit_observations: unknown[];
          diagnostics: Array<{
            severity: string;
            code: string;
            message: string;
          }>;
        };
      }>;
    };

    const client = createApiClient({ mode: "mock" }) as SignalConfluenceClient;
    client.getLivermoreSignalConfluence = vi.fn().mockResolvedValue({
      result: {
        as_of_date: "2026-04-30",
        macro_context: {
          status: "unknown",
          composite_score: null,
        },
        strategy_context: {
          market_gate_state: "UNKNOWN",
          position_size_hint: 0,
          new_entry_observation_allowed: false,
        },
        entry_observations: [],
        exit_observations: [],
        diagnostics: [
          {
            severity: "warning",
            code: "missing_macro_score",
            message: "缺少宏观综合分，当前只能保留观察口径。",
          },
          {
            severity: "info",
            code: "no_observations",
            message: "当前没有可展示的入场或退出观察点位。",
          },
        ],
      },
    });

    renderPage(client);

    const panel = await screen.findByTestId("cross-asset-livermore-confluence");
    await waitFor(() => {
      expect(client.getLivermoreSignalConfluence).toHaveBeenCalled();
      expect(panel).toHaveTextContent("暂无可观察点位");
    });
    expect(panel).toHaveTextContent("暂无可观察点位");
    expect(panel).toHaveTextContent("缺少宏观综合分，当前只能保留观察口径。");
    expect(panel).toHaveTextContent("当前没有可展示的入场或退出观察点位。");
    expect(panel).not.toHaveTextContent("message-");
    expect(panel).toHaveTextContent("宏观缺数");
    expect(panel).toHaveTextContent("暂无点位");
  });

  it("keeps restrictive Livermore confluence entries in observe-only mode and marks triggered exits", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getLivermoreSignalConfluence = vi.fn().mockResolvedValue({
      result: {
        as_of_date: "2026-04-30",
        macro_context: {
          status: "restrictive",
          composite_score: 0.42,
          multiplier: 0,
        },
        strategy_context: {
          market_gate_state: "OVERHEAT",
          market_gate_exposure: 1,
          allows_new_entry_observations: false,
        },
        position_size_hint: 0,
        entry_observations: [
          {
            action: "observe_only",
            stock_code: "000002.SZ",
            stock_name: "Beta",
            current_price: 12.1,
            trigger_price: 12.4,
            invalidation_reference_price: null,
            evidence: ["候选触发价来自 Livermore breakout_level。"],
          },
        ],
        exit_observations: [
          {
            action: "exit_triggered",
            stock_code: "000003.SZ",
            stock_name: "Gamma",
            current_price: 9.1,
            exit_watch_price: 9.8,
            triggered: true,
            evidence: ["退出观察价来自 Livermore EMA10。"],
          },
        ],
        diagnostics: ["Observation-only output. This service does not generate trading instructions."],
        disclaimer: "Observation-only output. This service does not generate trading instructions.",
      },
    });

    renderPage(client);

    const panel = await screen.findByTestId("cross-asset-livermore-confluence");
    await waitFor(() => {
      expect(panel).toHaveTextContent("偏收敛");
      expect(panel).toHaveTextContent("仅保留观察，不追加新动作");
      expect(panel).toHaveTextContent("仅观察");
      expect(panel).toHaveTextContent("退出观察已触发");
      expect(panel).toHaveTextContent("0%");
    });
  });

  it("surfaces the data-driven cockpit sections and provenance flags", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getResearchCalendarEvents: vi.fn(async () => [
        {
          id: "rc_supply_001",
          date: "2026-04-10",
          title: "国债供给窗口",
          kind: "supply" as const,
          severity: "medium" as const,
          amount_label: "净融资 180 亿元",
          note: "供给节奏",
        },
      ]),
    };

    renderPage(client);

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-candidate-actions")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-event-calendar")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-watch-list")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-page-output")).toBeInTheDocument();
    expect(await screen.findByText("国债供给窗口")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-event-calendar")).not.toHaveTextContent("仅分析口径");
    expect((await screen.findAllByText("仅分析口径")).length).toBeGreaterThan(0);
  });

  it("surfaces a first-screen loading failure when the latest macro chain fails", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getChoiceMacroLatest: vi.fn(async () => {
        throw new Error("choice latest failed");
      }),
    };

    renderPage(client);

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    const firstScreenFlags = await screen.findByTestId("cross-asset-status-flags");
    await waitFor(() => {
      expect(firstScreenFlags).toHaveTextContent("加载失败");
    });
    expect(firstScreenFlags).toHaveTextContent("choice_macro.latest");
  });
});
