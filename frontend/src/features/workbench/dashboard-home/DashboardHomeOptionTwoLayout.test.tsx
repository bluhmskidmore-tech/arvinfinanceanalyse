import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { createApiClient } from "../../../api/client";

import { EM_DASH } from "../../../utils/format";
import { buildBondTradingDeskPath } from "../../bond-trading-desk/lib/bondTradingDeskPageModel";
import { createMockHomeFirstScreenView } from "./dashboardHomeFirstScreenMockView";
import {
  mapToHomeBodyView,
  type MapToHomeBodyViewInput,
} from "./dashboardHomeBodyView";
import {
  DashboardHomeOptionTwoBody,
} from "./DashboardHomeOptionTwoLayout";
import { DashboardHomeOptionTwoOverview } from "./DashboardHomeOptionTwoOverview";
import { buildDashboardHomeAvailability } from "./dashboardHomeAvailability";

describe("DashboardHomeOptionTwoBody", () => {
  it("separates governed tasks from observations in the overview", () => {
    const baseView = createMockHomeFirstScreenView();
    const view = {
      ...baseView,
      headerStatus: {
        ...baseView.headerStatus,
        formalUseAllowed: false,
        governanceFeedAvailable: false,
        riskReviewCount: 0,
        showRiskReview: false,
      },
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoOverview view={view} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "今日需处理" })).toBeInTheDocument();
    expect(screen.getByText("治理待办未接入")).toBeInTheDocument();
    expect(screen.getByText("暂无正式待办源")).toBeInTheDocument();
    expect(screen.getByText("暂无正式待办源")).toHaveAttribute("data-tone", "warn");
    expect(screen.getByRole("link", { name: "打开治理入口" })).toBeInTheDocument();
    expect(screen.getByText("分析快照，非正式报表")).toBeInTheDocument();
    expect(screen.getByText("数据质量")).toBeInTheDocument();
    expect(screen.queryByText("治理待办 0 项")).not.toBeInTheDocument();
    expect(screen.getByText("观察与数据状态 · 不计入治理待办")).toBeInTheDocument();
    // 结论只在 01 区出现一次，且不再被包装成「趋势判断」；02 区只留归因要点（§6 状态去重、§7）。
    const conclusionHeadline = view.decisionRail.conclusion.replace(/[。；;]+$/u, "");
    expect(screen.getAllByText(conclusionHeadline)).toHaveLength(1);
    expect(
      screen.queryByRole("heading", { name: /趋势判断/, level: 3 }),
    ).not.toBeInTheDocument();
    const attributionPane = screen.getByTestId("dashboard-home-morning-hero");
    expect(within(attributionPane).getByText("归因要点")).toBeInTheDocument();
    expect(within(attributionPane).queryByText(conclusionHeadline)).not.toBeInTheDocument();
  });

  it("binds the four overview KPI slots by id and preserves a missing slot", () => {
    const baseView = createMockHomeFirstScreenView();
    const [aum, yieldKpi, nim, dv01] = baseView.terminalKpis;
    if (!aum || !nim || !dv01) {
      throw new Error("Mock first-screen KPI fixture is incomplete");
    }
    const view = {
      ...baseView,
      terminalKpis: [
        nim,
        {
          ...dv01,
          id: "dv01-wan",
          value: "10,695.00",
          unit: "万元/bp",
          delta: "变动 -0.05万",
        },
        { ...dv01, delta: "变动 -500.00" },
        aum,
      ],
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoOverview view={view} />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("3,708.10");
    expect(screen.getByTestId("dashboard-home-kpi-yield")).toHaveAttribute(
      "data-state",
      "empty",
    );
    expect(screen.getByTestId("dashboard-home-kpi-yield")).not.toHaveTextContent(
      yieldKpi?.value ?? "",
    );
    expect(screen.getByTestId("dashboard-home-kpi-nim")).toHaveTextContent("1.82");
    expect(screen.getByTestId("dashboard-home-kpi-dv01-wan")).toHaveTextContent(
      "10,695.00万元/bp",
    );
    expect(screen.getByTestId("dashboard-home-kpi-dv01-wan")).toHaveTextContent(
      "变动 -0.05万",
    );
    expect(screen.getByTestId("dashboard-home-kpi-dv01-wan")).not.toHaveTextContent(
      "变动 -500.00",
    );
  });

  it("keeps available KPI values visible when another snapshot section is partial", () => {
    const baseView = createMockHomeFirstScreenView();
    const view = {
      ...baseView,
      headerStatus: {
        ...baseView.headerStatus,
        dataStatusKind: "partial" as const,
      },
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoOverview view={view} />
      </MemoryRouter>,
    );

    const aumCard = screen.getByTestId("dashboard-home-kpi-aum");
    expect(aumCard).toHaveAttribute("data-state", "ready");
    expect(aumCard).toHaveTextContent("3,708.10");
    expect(screen.getByTestId("dashboard-home-kpi-yield")).toHaveTextContent("+12.40");
    expect(screen.getByTestId("dashboard-home-kpi-nim")).toHaveTextContent("1.82");
    expect(screen.getByTestId("dashboard-home-kpi-dv01-wan")).toHaveTextContent("10.62");
  });

  it("uses compact typography when the DV01 value and unit need the narrow KPI cell", () => {
    const baseView = createMockHomeFirstScreenView();
    const view = {
      ...baseView,
      terminalKpis: baseView.terminalKpis.map((kpi, index) =>
        index === 3 ? { ...kpi, value: "106,950,000", unit: "元/bp" } : kpi,
      ),
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoOverview view={view} />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("dashboard-home-kpi-dv01-wan")).toHaveAttribute(
      "data-compact-value",
      "true",
    );
  });

  it("renders the standalone product strip with exact headline metrics", () => {
    const baseView = createMockHomeFirstScreenView();
    const view = {
      ...baseView,
      productCategoryHeadline: {
        state: "partial" as const,
        metrics: [
          { id: "metric-a", label: "Alpha", value: "100", detail: "source-a" },
          { id: "metric-b", label: "Beta", value: "200", detail: "source-b" },
        ],
      },
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoOverview view={view} />
      </MemoryRouter>,
    );

    const section = screen.getByTestId("dashboard-home-product-category-headline");
    const strip = screen.getByTestId("dashboard-home-product-category-strip");
    const metricCells = strip.querySelectorAll("article");
    expect(section).toHaveAttribute("data-state", "partial");
    expect(strip).toHaveAttribute("data-state", "partial");
    expect(metricCells).toHaveLength(3);
    expect(strip).toHaveTextContent("Alpha");
    expect(strip).toHaveTextContent("100");
    expect(strip).toHaveTextContent("Beta");
    expect(strip).toHaveTextContent("200");
    expect(metricCells[1]).toHaveAttribute("title", "source-a");
    expect(metricCells[2]).toHaveAttribute("title", "source-b");
    expect(strip.querySelectorAll("small")).toHaveLength(0);
  });

  it("renders an explicit empty product strip state", () => {
    const baseView = createMockHomeFirstScreenView();
    const view = {
      ...baseView,
      productCategoryHeadline: { state: "empty" as const, metrics: [] },
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoOverview view={view} />
      </MemoryRouter>,
    );

    const section = screen.getByTestId("dashboard-home-product-category-headline");
    const strip = screen.getByTestId("dashboard-home-product-category-strip");
    expect(section).toHaveAttribute("data-state", "empty");
    expect(strip).toHaveAttribute("data-state", "empty");
    expect(strip.querySelector("p")).not.toBeNull();
    expect(strip.querySelectorAll("article")).toHaveLength(1);
  });

  it.each([
    { kind: "fallback" as const, label: "回退数据" },
    { kind: "stale" as const, label: "数据偏旧" },
  ])("makes the effective $kind product state visible", ({ kind, label }) => {
    const baseView = createMockHomeFirstScreenView();
    const view = {
      ...baseView,
      headerStatus: {
        ...baseView.headerStatus,
        dataStatusKind: kind,
      },
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoOverview view={view} />
      </MemoryRouter>,
    );

    const strip = screen.getByTestId("dashboard-home-product-category-strip");
    expect(within(strip).getByText(label)).toHaveAttribute("data-tone", "warn");
  });

  it("keeps data-as-of and missing-domain summaries visible in overview status", () => {
    const baseView = createMockHomeFirstScreenView();
    const view = {
      ...baseView,
      headerStatus: {
        ...baseView.headerStatus,
        dataStatusKind: "partial" as const,
      },
      reportDateContext: {
        ...baseView.reportDateContext,
        dataAsOfDate: "2026-06-30 16:00",
      },
      missingDomains: [
        { id: "pnl", label: "pnl" },
        { id: "valuation", label: "valuation" },
      ],
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoOverview view={view} />
      </MemoryRouter>,
    );

    const hero = screen.getByTestId("dashboard-home-hero");
    const status = hero.querySelector("aside");
    if (!status) {
      throw new Error("Expected overview status aside");
    }
    expect(status.textContent).toContain("2026-06-30 16:00");
    expect(status.textContent).toContain("pnl");
    expect(status.textContent).toContain("valuation");
  });

  it("shows the mock-data banner on the first screen when useMockFallback is true", () => {
    const view = createMockHomeFirstScreenView();
    expect(view.useMockFallback).toBe(true);

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoOverview view={view} />
      </MemoryRouter>,
    );

    const banner = screen.getByTestId("dashboard-home-mock-banner");
    expect(banner).toHaveTextContent("演示数据");
    expect(banner).toHaveTextContent("不作正式判断");
  });

  it("hides the mock-data banner when the view is not on the mock fallback", () => {
    const view = {
      ...createMockHomeFirstScreenView(),
      useMockFallback: false,
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoOverview view={view} />
      </MemoryRouter>,
    );

    expect(screen.queryByTestId("dashboard-home-mock-banner")).not.toBeInTheDocument();
    expect(screen.queryByText("演示数据")).not.toBeInTheDocument();
  });

  it("treats distribution pctRaw as display-percent points for sub-one-percent rows", () => {
    const baseView = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: true,
    } as MapToHomeBodyViewInput);
    const view = {
      ...baseView,
      assetDistribution: [
        {
          id: "small-allocation",
          label: "小额配置",
          value: "1.16 亿",
          pct: "0.62%",
          pctRaw: 0.62,
        },
      ],
      assetDistributionState: { kind: "ready" as const, label: "已接入" },
      ratingDistribution: [],
      ratingDistributionState: { kind: "empty" as const, label: "暂无评级分布" },
      maturityDistribution: [],
      maturityDistributionState: { kind: "empty" as const, label: "暂无限期分布" },
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody
          firstScreenView={createMockHomeFirstScreenView()}
          view={view}
        />
      </MemoryRouter>,
    );

    const board = screen.getByTestId("dashboard-home-structure-board");
    expect(within(board).getByRole("progressbar")).toHaveAttribute("value", "0.62");
    expect(within(board).getByText("可见合计").parentElement).toHaveTextContent("0.62%");
  });

  it("renders same-date warning distributions beside their Chinese quality disclosure", async () => {
    const reportDate = "2026-06-30";
    const summary = await createApiClient({ mode: "mock" }).getBondDashboardHomeSummary(reportDate);
    const view = mapToHomeBodyView({
      reportDate, useMockFallback: false,
      homeSummaryMeta: { ...summary.result_meta, quality_flag: "warning", vendor_status: "ok",
        fallback_mode: "none", as_of_date: reportDate, resolved_report_date: reportDate, fallback_date: null },
      assetStructure: { ...summary.result.asset_type, report_date: reportDate },
      ratingStructure: { ...summary.result.asset_rating, report_date: reportDate },
      maturityStructure: { ...summary.result.maturity, report_date: reportDate },
    } as MapToHomeBodyViewInput);
    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody firstScreenView={createMockHomeFirstScreenView()} view={view} />
      </MemoryRouter>,
    );
    const board = screen.getByTestId("dashboard-home-structure-board");
    expect(within(board).getAllByRole("progressbar").length).toBeGreaterThan(0);
    expect(within(board).getAllByText("数据质量需复核")).toHaveLength(3);
    expect(board).not.toHaveTextContent("quality warning");
  });

  it("withholds an unavailable distribution even when stale rows remain in the view", () => {
    const baseView = mapToHomeBodyView({ useMockFallback: true } as MapToHomeBodyViewInput);
    const view = { ...baseView, assetDistributionState: { kind: "error" as const, label: "数据质量错误，未展示" } };
    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody firstScreenView={createMockHomeFirstScreenView()} view={view} />
      </MemoryRouter>,
    );
    const column = within(screen.getByTestId("dashboard-home-structure-board"))
      .getByRole("heading", { name: "资产分布（按市值口径）" }).parentElement!;
    expect(within(column).queryByRole("progressbar")).not.toBeInTheDocument();
    expect(column).toHaveTextContent("数据质量错误，未展示");
  });

  it("withholds summary risk values with no evidence while retaining the independent snapshot Top5", async () => {
    const reportDate = "2026-06-30";
    const summary = await createApiClient({ mode: "mock" }).getBondDashboardHomeSummary(reportDate);
    const view = mapToHomeBodyView({
      reportDate, useMockFallback: false,
      homeSummaryMeta: { ...summary.result_meta, quality_flag: "warning", evidence_rows: 0,
        vendor_status: "ok", fallback_mode: "none", as_of_date: reportDate, resolved_report_date: reportDate },
      riskIndicators: { ...summary.result.risk, report_date: reportDate },
    } as MapToHomeBodyViewInput);
    const baseFirstScreenView = createMockHomeFirstScreenView();
    const firstScreenView = { ...baseFirstScreenView, keyRiskStrip: [
      { id: "risk-top5", label: "Top5集中度", value: "31.00%", delta: "来自独立主快照", deltaTone: "flat" as const },
    ] };
    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody firstScreenView={firstScreenView} view={view} />
      </MemoryRouter>,
    );
    const riskStrip = screen.getByTestId("dashboard-home-risk-metric-strip");
    expect(riskStrip).toHaveTextContent("Top5集中度");
    expect(riskStrip).toHaveTextContent("31.00%");
    expect(riskStrip).not.toHaveTextContent(/加权久期|加权凸性|总市值|信用债占比|DV01|1年再投资/);
  });

  it("withholds the visible total when the backend gave no share percentages", () => {
    const baseView = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: true,
    } as MapToHomeBodyViewInput);
    // 后端缺 percentage 时 pctRaw 退化成「占最大档的比例」，最大档恒为 100。
    // 把这些值当百分比求和曾在收益归因列算出 253.91%。
    const view = {
      ...baseView,
      assetDistribution: [
        {
          id: "bucket-mid",
          label: "1.5%-2.0%",
          value: "1,104.98 亿",
          pct: "465只",
          pctRaw: 100,
          pctIsFallback: true,
        },
        {
          id: "bucket-low",
          label: "<1.5%",
          value: "91.29 亿",
          pct: "35只",
          pctRaw: 8.26,
          pctIsFallback: true,
        },
      ],
      assetDistributionState: { kind: "ready" as const, label: "已接入" },
      ratingDistribution: [],
      ratingDistributionState: { kind: "empty" as const, label: "暂无评级分布" },
      maturityDistribution: [],
      maturityDistributionState: { kind: "empty" as const, label: "暂无限期分布" },
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody
          firstScreenView={createMockHomeFirstScreenView()}
          view={view}
        />
      </MemoryRouter>,
    );

    const board = screen.getByTestId("dashboard-home-structure-board");
    const total = within(board).getByText("可见合计").parentElement;
    expect(total).toHaveTextContent("占比未提供");
    expect(total).not.toHaveTextContent("108.26%");
    // 条形仍按相对长度绘制，但读屏不能把「465只」念成占比。
    expect(
      within(board).getByLabelText(
        "1.5%-2.0% 465只（后端未提供占比，条形按最大档相对长度绘制）",
      ),
    ).toBeInTheDocument();
  });

  it("renders the complete evidence area without labeling auxiliary freshness as core completeness", () => {
    const baseFirstScreenView = createMockHomeFirstScreenView();
    const firstScreenView = {
      ...baseFirstScreenView,
      headerStatus: {
        ...baseFirstScreenView.headerStatus,
        riskReviewCount: 0,
        showRiskReview: false,
      },
    };
    const view = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: true,
    } as MapToHomeBodyViewInput);

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody firstScreenView={firstScreenView} view={view} />
      </MemoryRouter>,
    );

    const evidence = screen.getByTestId("dashboard-home-data-tasks");
    expect(within(evidence).getByText(/^核心模块 \d+$/)).toBeInTheDocument();
    expect(within(evidence).getByText(/^就绪率 \d+%$/)).toBeInTheDocument();
    expect(within(evidence).queryByText(/^完整率/)).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "研究与资讯证据" }),
    ).toBeInTheDocument();
    // §7 微元句：区块范围说明收进标题 title，不再占区块头正文。
    expect(
      screen.getByRole("heading", { name: "研究与资讯证据" }),
    ).toHaveAttribute("title", "事件、政策与债券新闻");
    expect(screen.queryByText("事件、政策与债券新闻")).not.toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-research-calendar")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-bond-news")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-option-two-support-band")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-market-curve-table")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-liquidity-panel")).toBeInTheDocument();
    expect(
      within(screen.getByTestId("dashboard-home-bottom-grid")).getAllByRole("link"),
    ).toHaveLength(8);
    expect(screen.getByTestId("dashboard-home-governance-ledger")).toBeInTheDocument();
    expect(screen.getAllByTestId("dashboard-home-source-gate-row")).toHaveLength(6);
    expect(screen.getByTestId("dashboard-home-risk-exposure")).toHaveTextContent(
      /观测.*治理待办未接入/,
    );
    expect(screen.getByTestId("dashboard-home-risk-exposure")).not.toHaveTextContent(
      "暂无复核入口",
    );
  });

  it("surfaces stale news alongside a full core-module readiness rate", () => {
    const firstScreenView = createMockHomeFirstScreenView();
    const baseView = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: true,
    } as MapToHomeBodyViewInput);
    const view = {
      ...baseView,
      macroBriefing: { ...baseView.macroBriefing, newsStale: true },
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody firstScreenView={firstScreenView} view={view} />
      </MemoryRouter>,
    );

    const evidence = screen.getByTestId("dashboard-home-data-tasks");
    // 就绪率照旧只算核心模块，但不能让读者以为整页数据都新鲜。
    expect(within(evidence).getByText(/^就绪率 \d+%$/)).toBeInTheDocument();
    expect(within(evidence).getByText("新闻源偏旧")).toHaveAttribute("data-tone", "warn");
  });

  it("keeps the evidence strip free of a stale-news signal when news is fresh", () => {
    const firstScreenView = createMockHomeFirstScreenView();
    const baseView = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: true,
    } as MapToHomeBodyViewInput);
    const view = {
      ...baseView,
      macroBriefing: { ...baseView.macroBriefing, newsStale: false },
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody firstScreenView={firstScreenView} view={view} />
      </MemoryRouter>,
    );

    expect(
      within(screen.getByTestId("dashboard-home-data-tasks")).queryByText("新闻源偏旧"),
    ).not.toBeInTheDocument();
  });

  it("tones the auxiliary-source signal by state kind instead of always warning", () => {
    const firstScreenView = createMockHomeFirstScreenView();
    const view = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: true,
    } as MapToHomeBodyViewInput);

    const { rerender } = render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody
          firstScreenView={firstScreenView}
          view={view}
          supplementalStateLabel="补充查询已完成"
          supplementalStateKind="ready"
        />
      </MemoryRouter>,
    );

    // 完成态不该亮琥珀：文案说成功、颜色说告警会让人以为辅助来源出了问题。
    expect(
      within(screen.getByTestId("dashboard-home-data-tasks")).getByText(
        "辅助来源 · 补充查询已完成",
      ),
    ).toHaveAttribute("data-tone", "muted");

    rerender(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody
          firstScreenView={firstScreenView}
          view={view}
          supplementalStateLabel="补充查询部分失败"
          supplementalStateKind="partial"
        />
      </MemoryRouter>,
    );

    expect(
      within(screen.getByTestId("dashboard-home-data-tasks")).getByText(
        "辅助来源 · 补充查询部分失败",
      ),
    ).toHaveAttribute("data-tone", "warn");
  });

  it("discloses stale supplemental data beside the risk metrics under a healthy snapshot", () => {
    const baseView = createMockHomeFirstScreenView();
    const stateLabel = "组合风险摘要数据偏旧（数据日 2026-06-30）";
    const firstScreenView = {
      ...baseView,
      headerStatus: { ...baseView.headerStatus, dataStatusKind: "ok" as const },
      decisionRail: { ...baseView.decisionRail, actions: [], suggestions: [] },
      keyRiskStrip: [{ id: "risk-top5", label: "Top5集中度", value: "31.00%", delta: stateLabel, deltaTone: "warn" as const }],
    };
    const view = mapToHomeBodyView({
      reportDate: "2026-06-30", useMockFallback: true,
    } as MapToHomeBodyViewInput);

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody
          firstScreenView={firstScreenView}
          view={view}
          supplementalStateLabel={stateLabel}
          supplementalStateKind="stale"
        />
      </MemoryRouter>,
    );

    const riskSection = screen.getByTestId("dashboard-home-risk-exposure");
    expect(within(riskSection).getByText(stateLabel)).toBeVisible();
    expect(within(riskSection).getByText(stateLabel).parentElement).toHaveAttribute("data-tone", "warn");
    expect(riskSection).not.toHaveTextContent("当前值");
    expect(screen.getByTestId("dashboard-home-risk-metric-strip")).toHaveTextContent("31.00%");
    expect(within(screen.getByTestId("dashboard-home-data-tasks")).getByText(`辅助来源 · ${stateLabel}`)).toHaveAttribute("data-tone", "warn");
  });

  it("keeps the risk header count aligned with the three visible observation rows", () => {
    const baseFirstScreenView = createMockHomeFirstScreenView();
    const seedAction = baseFirstScreenView.decisionRail.actions[0]!;
    const firstScreenView = {
      ...baseFirstScreenView,
      decisionRail: {
        ...baseFirstScreenView.decisionRail,
        actions: Array.from({ length: 4 }, (_, index) => ({
          ...seedAction,
          id: `risk-review-${index + 1}`,
        })),
      },
    };
    const view = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: true,
    } as MapToHomeBodyViewInput);

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody firstScreenView={firstScreenView} view={view} />
      </MemoryRouter>,
    );

    const riskPanel = screen.getByTestId("dashboard-home-risk-exposure");
    expect(riskPanel).toHaveTextContent(/观测 3 · 治理待办/);
    expect(riskPanel.querySelectorAll("[data-priority]")).toHaveLength(3);
  });

  it("lets pending decision previews take recommendation slots and keeps the count honest", () => {
    const baseFirstScreenView = createMockHomeFirstScreenView();
    const seedAction = baseFirstScreenView.decisionRail.actions[0]!;
    const firstScreenView = {
      ...baseFirstScreenView,
      decisionRail: {
        ...baseFirstScreenView.decisionRail,
        actions: Array.from({ length: 4 }, (_, index) => ({
          ...seedAction,
          id: `risk-review-${index + 1}`,
        })),
      },
    };
    const baseView = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: true,
    } as MapToHomeBodyViewInput);
    const view = {
      ...baseView,
      decisionItemsPreview: [
        {
          id: "gap-review",
          title: "复核期限缺口",
          severity: "high" as const,
          actionLabel: "去复核",
          reason: "3-5 年缺口扩大",
        },
        {
          id: "concentration-review",
          title: "关注集中度",
          severity: "medium" as const,
          actionLabel: "去复核",
          reason: "",
        },
      ],
      decisionItemsState: { kind: "ready" as const, label: "2 项待处理" },
      decisionItemsReportDate: "2026-07-31",
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody firstScreenView={firstScreenView} view={view} />
      </MemoryRouter>,
    );

    const riskPanel = screen.getByTestId("dashboard-home-risk-exposure");
    // 2 条待复核预览挤占建议槽位后仍保持总量 3，计数与可见行一致。
    expect(screen.getAllByTestId("dashboard-home-decision-preview-row")).toHaveLength(2);
    expect(riskPanel).toHaveTextContent(/观测 3 · 治理待办/);
    expect(riskPanel.querySelectorAll("[data-priority]")).toHaveLength(3);
    // 跨域来源标注只在首行出现一次；截至日期收 title 不占正文（§6 全页去重）。
    const previewRows = screen.getAllByTestId("dashboard-home-decision-preview-row");
    expect(previewRows[0]).toHaveTextContent("余额分析台账");
    expect(previewRows[0]).not.toHaveTextContent("截至 2026-07-31");
    expect(
      within(previewRows[0]).getByTitle("余额分析台账 · 截至 2026-07-31"),
    ).toBeInTheDocument();
    expect(previewRows[1]).not.toHaveTextContent("截至 2026-07-31");
  });

  it("counts loading and empty core modules as attention states", () => {
    const baseView = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: true,
    } as MapToHomeBodyViewInput);
    const readyState = { kind: "ready" as const, label: "已接入" };
    const view = {
      ...baseView,
      holdingsState: readyState,
      positionChangesState: { kind: "loading" as const, label: "加载中" },
      riskExposureState: { kind: "empty" as const, label: "暂无数据" },
      assetDistributionState: readyState,
      researchReportsState: readyState,
      incomeTrendState: readyState,
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody
          firstScreenView={createMockHomeFirstScreenView()}
          view={view}
        />
      </MemoryRouter>,
    );

    const evidence = screen.getByTestId("dashboard-home-data-tasks");
    expect(evidence).toHaveTextContent("就绪 4/6");
    expect(within(evidence).getByText("关注 2 项")).toHaveAttribute(
      "data-tone",
      "warn",
    );
  });

  it("gives position and risk drilldowns descriptive accessible names", () => {
    const firstScreenView = createMockHomeFirstScreenView();
    const baseView = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: true,
    } as MapToHomeBodyViewInput);
    const view = {
      ...baseView,
      reportDate: "2026-06-30",
      positionChanges: [
        {
          id: "position-240002",
          code: " 240002.ib ",
          name: "24附息国债02",
          reason: "较前日",
          currentValue: "20.00 亿",
          changeValue: "+3.00 亿",
          weightDelta: "+0.20pp",
          direction: "increase" as const,
          tone: "up" as const,
          barPct: 100,
        },
      ],
      positionChangesState: { kind: "ready" as const, label: "已接入" },
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody firstScreenView={firstScreenView} view={view} />
      </MemoryRouter>,
    );

    const detailLink = screen.getByRole("link", { name: /查看 24附息国债02（.+）明细/ });
    expect(detailLink).toHaveAttribute(
      "href",
      buildBondTradingDeskPath("240002.IB", "2026-06-30"),
    );
    for (const link of screen.getAllByRole("link", { name: /查看(?:风险项|建议|风险观测)：/ })) {
      expect(link).toHaveTextContent("查看");
    }
  });

  it.each([
    { code: "", reportDate: "2026-06-30" },
    { code: "—", reportDate: "2026-06-30" },
    { code: "240002.IB", reportDate: "2026-6-30" },
  ])("does not create a position link for invalid route input %#", ({ code, reportDate }) => {
    const baseView = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: true,
    } as MapToHomeBodyViewInput);
    const view = {
      ...baseView,
      reportDate,
      positionChanges: [
        {
          id: "invalid-position",
          code,
          name: "待核验债券",
          reason: "较前日",
          currentValue: "—",
          changeValue: "—",
          weightDelta: "—",
          direction: "flat" as const,
          tone: "flat" as const,
          barPct: 4,
        },
      ],
      positionChangesState: { kind: "ready" as const, label: "已接入" },
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody
          firstScreenView={createMockHomeFirstScreenView()}
          view={view}
        />
      </MemoryRouter>,
    );

    expect(screen.queryByRole("link", { name: /查看 待核验债券/ })).not.toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-position-operation")).toHaveAttribute(
      "data-state",
      "unavailable",
    );
  });

  it("renders only validated research links and publication dates", () => {
    const baseView = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: true,
    } as MapToHomeBodyViewInput);
    const view = {
      ...baseView,
      researchReports: [
        {
          id: "valid-report",
          title: "有效利率债周报",
          category: "fixed_income",
          publishedAt: "2026-06-30",
          source: "research",
          institution: "研究机构",
          summary: "—",
          link: "https://example.com/rates.pdf",
          isNewsFallback: false,
        },
        {
          id: "unsafe-report",
          title: "待核验信用债周报",
          category: "fixed_income",
          publishedAt: "2026-02-30",
          source: "research",
          institution: "研究机构",
          summary: "—",
          link: "javascript:alert(1)",
          isNewsFallback: false,
        },
      ],
      researchReportsState: { kind: "ready" as const, label: "已接入" },
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody
          firstScreenView={createMockHomeFirstScreenView()}
          view={view}
        />
      </MemoryRouter>,
    );

    const researchTable = screen.getByTestId("dashboard-home-research-reports");
    expect(within(researchTable).getByRole("link", { name: "有效利率债周报" })).toHaveAttribute(
      "href",
      "https://example.com/rates.pdf",
    );
    expect(within(researchTable).queryByRole("link", { name: "待核验信用债周报" })).toBeNull();
    expect(within(researchTable).getByText("06-30").closest("time")).toHaveAttribute(
      "datetime",
      "2026-06-30",
    );
    expect(within(researchTable).queryByText("02-30")).toBeNull();

    fireEvent.click(screen.getByRole("tab", { name: "研究报告" }));
    const governedResearch = screen.getByTestId("dashboard-home-research-reports");
    expect(
      within(governedResearch).getByRole("link", {
        name: "打开PDF原文：有效利率债周报",
      }),
    ).toHaveAttribute("href", "https://example.com/rates.pdf");
    expect(within(governedResearch).queryByRole("link", { name: /待核验信用债周报/ })).toBeNull();
    expect(within(governedResearch).queryByText("2026-02-30")).toBeNull();
  });

  it("keeps the income-trend heading text free of the sparkline caption and quiets the ready comparison row", () => {
    const baseView = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: true,
    } as MapToHomeBodyViewInput);
    const point = (id: string, date: string, raw: number) => ({
      id,
      date,
      portfolioPnl: `${(raw / 1e8).toFixed(2)} 亿`,
      benchmarkPnl: "—",
      excessPnl: "—",
      portfolioRaw: raw,
      benchmarkRaw: null,
      excessRaw: null,
      missingReason: null,
    });
    const view = {
      ...baseView,
      incomeTrend: [
        point("i-1", "2026-04-30", 1.0e8),
        point("i-2", "2026-05-31", 1.1e8),
        point("i-3", "2026-06-30", 1.2e8),
      ],
      incomeTrendState: { kind: "ready" as const, label: "已接入" },
      portfolioComparisonState: { kind: "ready" as const, label: "已接入" },
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody
          firstScreenView={createMockHomeFirstScreenView()}
          view={view}
        />
      </MemoryRouter>,
    );

    const incomeTrend = screen.getByTestId("dashboard-home-income-trend");
    const heading = within(incomeTrend).getByRole("heading", { level: 3 });
    // §7 微元句：口径说明只在 title，标题文本（含 SVG <title>）不夹带它。
    expect(heading.textContent).toBe("收益趋势（组合 / 基准 / 超额）");
    expect(heading).toHaveAttribute(
      "title",
      "组合损益走势（全序列 3 个月度点，表格列近 3 期）",
    );
    expect(heading.querySelector("svg title")).toBeNull();
    // §12 结论 17：就绪态不再显示「已就绪」完成徽标词。
    const comparison = screen.getByTestId("dashboard-home-position-comparison");
    expect(comparison).toHaveAttribute("data-state", "ready");
    expect(comparison).not.toHaveTextContent("已就绪");
    expect(comparison).toHaveTextContent("正常");
  });

  it("collapses the market-tab research table to a single state line when there are no reports", () => {
    const baseView = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: true,
    } as MapToHomeBodyViewInput);
    const view = {
      ...baseView,
      researchReports: [],
      researchReportsState: { kind: "empty" as const, label: "债券/宏观研报暂无数据" },
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody
          firstScreenView={createMockHomeFirstScreenView()}
          view={view}
        />
      </MemoryRouter>,
    );

    const researchTable = screen.getByTestId("dashboard-home-research-reports");
    // §5 空态收缩：不渲染只剩表头的空表，状态词与上游文案不重复。
    expect(researchTable.querySelector("table")).toBeNull();
    expect(researchTable).toHaveTextContent("债券/宏观研报暂无数据");
    expect(researchTable.textContent).not.toMatch(/暂无数据.*暂无数据/);
  });

  it("keeps degraded research disclosure visible on the default market tab", () => {
    const baseView = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: true,
    } as MapToHomeBodyViewInput);
    const view = {
      ...baseView,
      researchReports: [
        {
          id: "news-fallback",
          title: "政策资金面快讯",
          category: "新闻补位 · 宏观",
          publishedAt: "—",
          source: "Tushare",
          institution: "Tushare",
          summary: "Tushare · 数据偏旧",
          link: null,
          isNewsFallback: true,
        },
      ],
      researchReportsState: {
        kind: "partial" as const,
        label: "研报源暂缺 · 新闻补位",
      },
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody
          firstScreenView={createMockHomeFirstScreenView()}
          view={view}
        />
      </MemoryRouter>,
    );

    const researchTable = screen.getByTestId("dashboard-home-research-reports");
    expect(
      within(researchTable).getByTestId("dashboard-home-research-disclosure"),
    ).toHaveTextContent("研报源暂缺 · 新闻补位");
    expect(within(researchTable).getByText("政策资金面快讯")).toBeInTheDocument();
  });

  it("cleans raw research filenames in the visible title while keeping href and title raw", () => {
    const baseView = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: true,
    } as MapToHomeBodyViewInput);
    const view = {
      ...baseView,
      researchReports: [
        {
          id: "raw-file-report",
          title: "华源证券_公司动态研究报告_20260712.pdf",
          category: "fixed_income",
          publishedAt: "2026-07-12",
          source: "research",
          institution: "华源证券",
          summary: EM_DASH,
          link: "https://example.com/hy.pdf",
          isNewsFallback: false,
        },
      ],
      researchReportsState: { kind: "ready" as const, label: "已接入" },
    };

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody
          firstScreenView={createMockHomeFirstScreenView()}
          view={view}
        />
      </MemoryRouter>,
    );

    const researchTable = screen.getByTestId("dashboard-home-research-reports");
    // 与来源列重复的机构名前缀在可见标题剥离，原文保留在 td title 与 href。
    const cleanedLink = within(researchTable).getByRole("link", {
      name: "公司动态研究报告",
    });
    expect(cleanedLink).toHaveAttribute("href", "https://example.com/hy.pdf");
    expect(cleanedLink.closest("td")).toHaveAttribute(
      "title",
      "华源证券_公司动态研究报告_20260712.pdf",
    );
    expect(within(researchTable).queryByText(/\.pdf/)).toBeNull();
    const sourceCell = within(researchTable).getByRole("cell", { name: "华源证券" });
    expect(sourceCell).toBeInTheDocument();
  });

  it("offers the latest-report recovery action for an unavailable report date", () => {
    const firstScreenView = createMockHomeFirstScreenView();
    const view = mapToHomeBodyView({
      reportDate: "2026-08-28",
      useMockFallback: true,
    } as MapToHomeBodyViewInput);
    const availability = buildDashboardHomeAvailability({
      dataStatusKind: "error",
      dataSyncPrefix: "快照状态",
      reportDateContext: {
        ...firstScreenView.reportDateContext,
        requestedDate: "2026-08-28",
        actualDataDate: "",
      },
      snapshotMeta: null,
      snapshotErrorDetail:
        "报告日 2026-08-28 缺少正式损益数据，暂不能生成完整首页。最新可用报告日为 2026-08-31。 [code=home_report_date_unavailable]",
    });
    const onViewLatestReport = vi.fn();

    render(
      <MemoryRouter>
        <DashboardHomeOptionTwoBody
          firstScreenView={firstScreenView}
          view={view}
          homeAvailability={availability}
          onRefresh={vi.fn()}
          onViewLatestReport={onViewLatestReport}
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("dashboard-home-data-availability")).toHaveAttribute(
      "data-state",
      "dateUnavailable",
    );
    expect(screen.getByTestId("dashboard-home-data-availability")).toHaveTextContent(
      "最新可用报告日为 2026-08-31",
    );
    expect(screen.getByTestId("dashboard-home-data-availability")).not.toHaveTextContent(
      "home_report_date_unavailable",
    );
    expect(screen.queryByTestId("dashboard-home-data-availability-retry")).toBeNull();

    fireEvent.click(screen.getByTestId("dashboard-home-view-latest-report"));
    expect(onViewLatestReport).toHaveBeenCalledOnce();
  });
});
