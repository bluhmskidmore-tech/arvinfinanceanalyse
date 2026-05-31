import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="dashboard-echarts-stub" />,
}));

import { createApiClient, type ApiClient } from "../api/client";
import type { DashboardHomeView } from "../features/workbench/dashboard-home/dashboardHomeView";
import { TerminalHomeContent } from "../features/workbench/dashboard-home/TerminalHomeContent";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

afterEach(() => {
  vi.unstubAllGlobals();
});

function createRealModeHomeClient(overrides: Partial<ApiClient> = {}): ApiClient {
  const base = createApiClient({ mode: "real" });
  const mockSnapshotSource = createApiClient({ mode: "mock" });
  return {
    ...base,
    getHomeSnapshot: (...args) => mockSnapshotSource.getHomeSnapshot(...args),
    ...overrides,
  };
}

function renderDashboardHome(client?: ApiClient) {
  return renderWorkbenchApp(["/"], {
    client: client ?? createApiClient({ mode: "mock" }),
  });
}

function createTerminalStateView(overrides: Partial<DashboardHomeView> = {}): DashboardHomeView {
  const baseState = { kind: "empty" as const, label: "暂无数据" };
  return {
    reportDate: "2026-04-30",
    useMockFallback: false,
    headerStatus: {
      dataStatusKind: "ok",
      dataUpdatedAt: "09:15",
      marketStatus: "市场已收盘",
      valuationLabel: "估值已完成",
      valuationTone: "ok",
      riskReviewCount: 0,
      showRiskReview: false,
      dataSyncPrefix: "数据已更新",
    },
    aiJudge: {
      conclusion: "测试结论",
      healthLabel: "中性",
      healthScore: 70,
      healthTone: "green",
      impact: "等待下一组观测",
      sparkline: [],
    },
    coreKpis: [],
    riskMinis: [],
    marketTape: [],
    portfolioStats: [],
    assetBars: [],
    assetBarsPlaceholder: true,
    centerAum: { label: "总资产", value: "—" },
    interbank: { assets: "—", liabilities: "—", net: "—", netTone: "muted" },
    attributionTabs: [],
    attributionWaterfall: [],
    attributionInsights: {
      maxDragLabel: "—",
      maxDragValue: "—",
      maxContributionLabel: "—",
      maxContributionValue: "—",
    },
    attributionNote: [],
    riskCards: [],
    riskCardsPlaceholder: true,
    riskRadar: { dimensions: [], values: [], placeholder: true },
    todos: [],
    watchlist: [],
    watchlistPlaceholder: true,
    exposureRows: [],
    balanceMetrics: [],
    quickDrilldowns: [],
    researchCalendar: {
      items: [],
      status: "empty",
      windowLabel: "2026-04-23 至 2026-05-14",
      message: "当前窗口暂无供给/招标事件。",
    },
    macroBriefing: {
      releaseItems: [],
      releaseWindowLabel: "未来 45 天",
      releaseMessage: "暂无已维护发布日期，请补充配置清单。",
      newsItems: [],
      newsMessage: "暂无可展示的宏观新闻。",
      newsStale: false,
      newsFreshnessLabel: "暂无更新",
      newsSourceLabel: "来源：Choice 宏观新闻",
      newsAsOfLabel: "数据截至：暂无",
      newsStatusLabel: "来源状态：暂无数据",
      newsRefreshLabel: "刷新：随页面查询自动更新",
      supplyItems: [{ id: "supply-empty", label: "供给/招标：当前窗口无事件" }],
    },
    marketContext: {
      temperatureLabel: "市场温度：中性",
      temperatureScore: 50,
      temperatureTone: "neutral",
      drivers: ["外部市场暂无明显方向"],
      contextBlocks: [
        {
          id: "pnl",
          label: "PnL归因",
          title: "等待正式归因数据",
          detail: "未收到 return-decomposition 正式 payload",
          foot: "不从总 PnL 反推归因",
        },
        {
          id: "curve",
          label: "曲线/利率",
          title: "等待曲线期限结构",
          detail: "未收到 yield_curve_term_structure 正式 payload",
          foot: "默认曲线 treasury,cdb,aaa_credit",
        },
        {
          id: "credit",
          label: "信用利差",
          title: "等待信用利差上下文",
          detail: "未收到 credit_spread_migration 正式 payload",
          foot: "只作解释变量，不改变 PnL 计算",
        },
      ],
      aiSummary: [
        "PnL归因：等待正式归因数据；未收到 return-decomposition 正式 payload。",
        "曲线/利率：等待曲线期限结构；未收到 yield_curve_term_structure 正式 payload。",
      ],
      sourceLabel: "来源：收益归因 / yield_curve_term_structure / credit_spread_migration",
      asOfLabel: "数据截至：暂无",
      statusLabel: "来源状态：等待正式数据",
      refreshLabel: "刷新：随报告日查询自动更新",
    },
    liabilityWatchBasisNote: null,
    decisionRail: {
      conclusion: "测试结论",
      maxDragLabel: "—",
      maxDragValue: "—",
      maxContributionLabel: "—",
      maxContributionValue: "—",
      keyRisk: "—",
      suggestions: [],
      pendingSummary: "0 项",
      reportDate: "2026-04-30",
      dataUpdatedAt: "09:15",
      dataSyncPrefix: "数据已更新",
    },
    terminalKpis: [],
    keyRiskStrip: [],
    holdingRows: [],
    holdingsState: { kind: "empty", label: "重仓券暂无数据" },
    assetDistribution: [],
    assetDistributionState: baseState,
    ratingDistribution: [],
    ratingDistributionState: baseState,
    maturityDistribution: [],
    maturityDistributionState: { kind: "empty", label: "久期分布暂无数据" },
    industryDistribution: [],
    industryDistributionState: { kind: "error", label: "行业分布加载失败" },
    riskExposureMetrics: [],
    riskExposureState: { kind: "empty", label: "风险指标暂无数据" },
    positionChanges: [],
    positionChangesState: { kind: "error", label: "增减仓加载失败" },
    researchReports: [],
    researchReportsState: { kind: "error", label: "研究报告加载失败" },
    incomeTrend: [],
    incomeTrendState: { kind: "partial", label: "缺 CDB_INDEX 可核验曲线" },
    backendGaps: [],
    ...overrides,
  };
}

describe("DashboardHomePage", () => {
  it("renders the home shell while snapshot query is unresolved", async () => {
    const base = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const slowClient: ApiClient = {
      ...base,
      getHomeSnapshot: async () => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return base.getHomeSnapshot();
      },
    };

    renderDashboardHome(slowClient);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    expect(await screen.findByTestId("workbench-group-nav")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
  });

  it("uses mock-shaped first-screen content when the app is not using real APIs", async () => {
    renderDashboardHome();

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    const hero = await screen.findByTestId("dashboard-home-hero");
    expect(within(hero).getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("3,708.10");
  });

  it("does not request excluded executive surfaces from the home page", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let riskCalls = 0;
    let contributionCalls = 0;
    let alertsCalls = 0;

    const guardedClient: ApiClient = {
      ...base,
      getHomeSnapshot: (...args) => mockSnapshotSource.getHomeSnapshot(...args),
      getRiskOverview: async () => {
        riskCalls += 1;
        throw new Error("risk-overview should not be requested");
      },
      getContribution: async () => {
        contributionCalls += 1;
        throw new Error("contribution should not be requested");
      },
      getAlerts: async () => {
        alertsCalls += 1;
        throw new Error("alerts should not be requested");
      },
    };

    renderDashboardHome(guardedClient);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(riskCalls).toBe(0);
      expect(contributionCalls).toBe(0);
      expect(alertsCalls).toBe(0);
    });
  });

  it("prefers real first-screen values over local fallback", async () => {
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const getHomeSnapshot = vi.fn(async (options) => {
      const envelope = await mockSnapshotSource.getHomeSnapshot(options);
      return {
        ...envelope,
        result_meta: {
          ...envelope.result_meta,
          generated_at: "2026-04-30T10:45:00+08:00",
        },
        result: {
          ...envelope.result,
          report_date: "2026-04-30",
          overview: {
            ...envelope.result.overview,
            metrics: [
              {
                id: "aum",
                label: "债券资产规模",
                caliber_label: "真实接口口径",
                value: {
                  raw: 4_567_890_000_000,
                  unit: "yuan" as const,
                  display: "4,567.89 亿",
                  precision: 2,
                  sign_aware: false,
                },
                delta: {
                  raw: 12_300_000_000,
                  unit: "yuan" as const,
                  display: "+12.30 亿",
                  precision: 2,
                  sign_aware: true,
                },
                tone: "positive" as const,
                detail: "测试真实接口返回值。",
              },
            ],
          },
        },
      };
    });
    const client = createRealModeHomeClient({
      getHomeSnapshot,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    renderDashboardHome(client);

    const hero = await screen.findByTestId("dashboard-home-hero");
    await waitFor(() => {
      expect(getHomeSnapshot).toHaveBeenCalled();
      expect(within(hero).getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("4,567.89");
    });
  });

  it("renders terminal holdings and newly landed home backend blocks", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    const getHomeSnapshot = vi.fn<ApiClient["getHomeSnapshot"]>(async (options) => {
      const envelope = await mockSource.getHomeSnapshot(options);
      return {
        ...envelope,
        result: {
          ...envelope.result,
          report_date: "2026-04-30",
        },
      };
    });
    const yuan = (raw: number, display: string) => ({
      raw,
      unit: "yuan" as const,
      display,
      precision: 2,
      sign_aware: false,
    });
    const ratio = (raw: number, display: string) => ({
      raw,
      unit: "ratio" as const,
      display,
      precision: 2,
      sign_aware: false,
    });
    const pct = (raw: number, display: string) => ({
      raw,
      unit: "pct" as const,
      display,
      precision: 2,
      sign_aware: false,
    });
    const signedYuan = (raw: number, display: string) => ({
      raw,
      unit: "yuan" as const,
      display,
      precision: 2,
      sign_aware: true,
    });
    const missingYuan = {
      raw: null,
      unit: "yuan" as const,
      display: "-",
      precision: 2,
      sign_aware: true,
    };
    const getBondAnalyticsTopHoldings = vi.fn<ApiClient["getBondAnalyticsTopHoldings"]>(
      async (...args) => {
        const envelope = await mockSource.getBondAnalyticsTopHoldings(...args);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            items: [
              {
                instrument_code: "240001.IB",
                instrument_name: "测试国债01",
                issuer_name: "财政部",
                rating: "AAA",
                asset_class: "利率债",
                market_value: yuan(12_350_000_000, "123.50 亿"),
                face_value: yuan(12_000_000_000, "120.00 亿"),
                ytm: pct(0.0236, "2.36%"),
                modified_duration: ratio(4.21, "4.21"),
                weight: pct(0.0961, "9.61%"),
              },
            ],
          },
        };
      },
    );
    const getBondAnalyticsPositionChanges = vi.fn<ApiClient["getBondAnalyticsPositionChanges"]>(
      async (...args) => {
        const envelope = await mockSource.getBondAnalyticsPositionChanges(...args);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: "2026-04-30",
            prev_report_date: "2026-04-29",
            source_status: "ready",
            items: [
              {
                instrument_code: "240002.IB",
                instrument_name: "测试增持债",
                issuer_name: "财政部",
                rating: "AAA",
                asset_class: "rate",
                previous_market_value: yuan(10_000_000_000, "100.00 亿"),
                current_market_value: yuan(13_000_000_000, "130.00 亿"),
                change_market_value: signedYuan(3_000_000_000, "+30.00 亿"),
                previous_weight: ratio(0.08, "8.00%"),
                current_weight: ratio(0.1, "10.00%"),
                change_weight: ratio(0.02, "+2.00pp"),
                direction: "increase" as const,
                reason_label: "增持",
                source_status: "ready" as const,
              },
            ],
          },
        };
      },
    );
    const getHomeResearchReports = vi.fn<ApiClient["getHomeResearchReports"]>(
      async (...args) => {
        const envelope = await mockSource.getHomeResearchReports(...args);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: "2026-04-30",
            source_status: "ready",
            items: [
              {
                id: "research-1",
                title: "利率债周报",
                category: "fixed_income",
                published_at: "2026-04-29T09:00:00",
                link: "https://example.com/report.pdf",
                source: "tushare_research",
                source_status: "ready" as const,
                summary: "关注久期和曲线",
              },
            ],
          },
        };
      },
    );
    const getHomeIncomeTrend = vi.fn<ApiClient["getHomeIncomeTrend"]>(
      async (reportDate, window = 7) => {
        const envelope = await mockSource.getHomeSnapshot({ reportDate });
        return {
          ...envelope,
          result_meta: {
            ...envelope.result_meta,
            result_kind: "home.income_trend",
          },
          result: {
            report_date: "2026-04-30",
            window,
            source_status: "partial",
            missing_components: ["benchmark_pnl", "excess_pnl"],
            warnings: ["Benchmark and excess PnL are not available."],
            points: [
              {
                date: "2026-03-31",
                portfolio_pnl: signedYuan(120_000_000, "+1.20 yi"),
                benchmark_pnl: missingYuan,
                excess_pnl: missingYuan,
                basis: "product_category_pnl_monthly" as const,
                source_status: "partial" as const,
              },
              {
                date: "2026-04-30",
                portfolio_pnl: signedYuan(90_000_000, "+0.90 yi"),
                benchmark_pnl: missingYuan,
                excess_pnl: missingYuan,
                basis: "product_category_pnl_monthly" as const,
                source_status: "partial" as const,
              },
            ],
          },
        };
      },
    );
    const client = createRealModeHomeClient({
      getHomeSnapshot,
      getBondAnalyticsTopHoldings,
      getBondAnalyticsPositionChanges,
      getHomeResearchReports,
      getHomeIncomeTrend,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    renderDashboardHome(client);

    await waitFor(() => {
      expect(getBondAnalyticsTopHoldings).toHaveBeenCalledWith(
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        8,
      );
      expect(getBondAnalyticsPositionChanges).toHaveBeenCalledWith(
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        5,
      );
      expect(getHomeResearchReports).toHaveBeenCalledWith(
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        5,
      );
      expect(getHomeIncomeTrend).toHaveBeenCalledWith(
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        7,
      );
    });
    await waitFor(() => {
      const holdingsTable = screen.getByTestId("dashboard-home-holdings-table");
      expect(within(holdingsTable).getAllByTestId("dashboard-home-holding-row").length).toBeGreaterThan(0);
    });
    const positionChanges = await screen.findByTestId("dashboard-home-position-changes");
    expect(positionChanges).toHaveTextContent("240002.IB");
    expect(positionChanges).toHaveTextContent("+2.00pp");
    expect(positionChanges).toHaveTextContent("现值");
    const incomeTrend = await screen.findByTestId("dashboard-home-income-trend");
    expect(incomeTrend).toHaveTextContent("组合");
    expect(incomeTrend).toHaveTextContent("基准");
    expect(incomeTrend).toHaveTextContent("超额");
    expect(incomeTrend).toHaveTextContent("+1.20");
    expect(await screen.findByTestId("dashboard-home-research-reports")).toHaveTextContent("利率债周报");
    expect(screen.queryByTestId("dashboard-home-backend-gap-research-reports")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-home-backend-gap-position-changes")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-home-backend-gap-income-trend")).not.toBeInTheDocument();
  });

  it("renders compact explicit states instead of blank terminal cards", () => {
    render(
      <MemoryRouter>
        <TerminalHomeContent
          view={createTerminalStateView({
            backendGaps: [
              {
                id: "leverage",
                title: "杠杆率",
                neededEndpoint: "GET /ui/home/leverage?report_date=",
                reason: "开发缺口不应出现在业务首页。",
              },
            ],
          })}
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("dashboard-home-market")).toHaveTextContent("关键风险暂无数据");
    expect(screen.getByTestId("dashboard-home-market")).toHaveTextContent("当前口径没有可展示记录");
    expect(screen.getByTestId("dashboard-home-holdings-table")).toHaveTextContent("重仓券暂无数据");
    expect(screen.getByTestId("dashboard-home-position-changes")).toHaveTextContent("增减仓加载失败");
    expect(screen.getByTestId("dashboard-home-research-reports")).toHaveTextContent("研究报告加载失败");
    expect(screen.getByTestId("dashboard-home-income-trend")).toHaveTextContent("缺 CDB_INDEX 可核验曲线");
    expect(screen.getByTestId("dashboard-home-income-trend")).toHaveTextContent("缺少部分受管字段");
    expect(screen.getByTestId("dashboard-home-market-context")).toHaveTextContent("今日市场解释");
    expect(screen.getByTestId("dashboard-home-market-context")).toHaveTextContent("市场温度：中性");
    expect(screen.getByTestId("dashboard-home-market-context")).toHaveTextContent("PnL归因");
    expect(screen.getByTestId("dashboard-home-market-context")).toHaveTextContent("曲线/利率");
    expect(screen.getByTestId("dashboard-home-market-context")).toHaveTextContent("信用利差");
    expect(screen.queryByText("后端工单")).not.toBeInTheDocument();
    expect(screen.queryByText("杠杆率")).not.toBeInTheDocument();
  });

  it("renders income trend as portfolio benchmark and excess context", () => {
    render(
      <MemoryRouter>
        <TerminalHomeContent
          view={createTerminalStateView({
            incomeTrendState: { kind: "ready", label: "已接入" },
            incomeTrend: [
              {
                id: "2026-03-31",
                date: "2026-03-31",
                portfolioPnl: "+1.20 亿",
                benchmarkPnl: "+0.80 亿",
                excessPnl: "+0.40 亿",
                portfolioRaw: 120_000_000,
                benchmarkRaw: 80_000_000,
                excessRaw: 40_000_000,
              },
              {
                id: "2026-04-30",
                date: "2026-04-30",
                portfolioPnl: "+0.90 亿",
                benchmarkPnl: "+0.60 亿",
                excessPnl: "+0.30 亿",
                portfolioRaw: 90_000_000,
                benchmarkRaw: 60_000_000,
                excessRaw: 30_000_000,
              },
            ],
          })}
        />
      </MemoryRouter>,
    );

    const incomeTrend = screen.getByTestId("dashboard-home-income-trend");
    expect(incomeTrend).toHaveTextContent("数据截至 2026-04-30");
    expect(incomeTrend).toHaveTextContent("CDB_INDEX / MoM");
    expect(incomeTrend).toHaveTextContent("组合");
    expect(incomeTrend).toHaveTextContent("CDB基准");
    expect(incomeTrend).toHaveTextContent("超额");
    expect(incomeTrend).toHaveTextContent("基准 +0.60 亿 · 超额 +0.30 亿");
  });
    /*
    expect(screen.getByTestId("dashboard-home-backend-gap-research-reports")).toHaveTextContent(
      "后端待接入",
    );
    expect(screen.getByTestId("dashboard-home-backend-gap-position-changes")).toHaveTextContent(
      "后端待接入",
    );
  });

    */
  it("renders supply and auction calendar items from the research calendar feed", async () => {
    const researchCalendarCalls: Array<{
      reportDate?: string;
      startDate?: string;
      endDate?: string;
    }> = [];
    const client = createRealModeHomeClient({
      getResearchCalendarEvents: async (options) => {
        researchCalendarCalls.push(options ?? {});
        return [
          {
            id: "cal_supply_001",
            date: "2026-04-18",
            title: "国债净融资节奏",
            kind: "supply" as const,
            severity: "medium" as const,
            amount_label: "净融资 180 亿元",
            note: "供给节奏",
          },
          {
            id: "cal_auction_002",
            date: "2026-04-19",
            title: "政策性金融债招标",
            kind: "auction" as const,
            severity: "high" as const,
            amount_label: "420 亿元",
            note: "国开行",
          },
        ];
      },
    });

    renderDashboardHome(client);

    const calendar = await screen.findByTestId("dashboard-home-research-calendar");
    await waitFor(() => {
      expect(calendar).toHaveTextContent("国债净融资节奏");
      expect(calendar).toHaveTextContent("政策性金融债招标");
    });
    expect(calendar).toHaveTextContent("供给/招标：");
    expect(researchCalendarCalls.some((call) => call.startDate && call.endDate)).toBe(true);
  });

  it("keeps an explicit no-data state when the external event feed is empty", async () => {
    const getResearchCalendarEvents = vi.fn(async () => []);
    const mockNewsClient = createApiClient({ mode: "mock" });
    const getChoiceNewsEvents = vi.fn((options) => mockNewsClient.getChoiceNewsEvents(options));
    const client = createRealModeHomeClient({ getResearchCalendarEvents, getChoiceNewsEvents });

    renderDashboardHome(client);

    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalled();
      expect(getChoiceNewsEvents).toHaveBeenCalled();
    });
    const calendar = await screen.findByTestId("dashboard-home-research-calendar");
    await waitFor(() => {
      expect(calendar).toHaveTextContent("重大信息发布日期前瞻");
      expect(calendar).toHaveTextContent("国内外宏观新闻");
      expect(calendar).toHaveTextContent("来源：Choice 宏观新闻");
      expect(calendar).toHaveTextContent("数据截至");
      expect(calendar).toHaveTextContent("来源状态");
      expect(calendar).toHaveTextContent("刷新：");
      expect(calendar).toHaveTextContent("供给/招标：当前窗口无事件");
      expect(calendar).not.toHaveTextContent("当前窗口暂无供给/招标事件。");
    });
    const topicCodes = getChoiceNewsEvents.mock.calls.map(([options]) => options.topicCode);
    expect(topicCodes).toEqual(
      expect.arrayContaining([
        "S888010007API",
        "S888010003API",
        "S888010005API",
        "S888005004API",
        "C000003006",
        "C000003002",
      ]),
    );
  });

  it("keeps an explicit error state when the external event feed fails", async () => {
    const getResearchCalendarEvents = vi.fn(async () => {
      throw new Error("calendar backend unavailable");
    });
    const client = createRealModeHomeClient({ getResearchCalendarEvents });

    renderDashboardHome(client);

    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalled();
    });
    const calendar = await screen.findByTestId("dashboard-home-research-calendar");
    await waitFor(() => {
      expect(calendar).toHaveTextContent("供给/招标：加载失败");
    });
  });
});
