import { useState, type ReactNode } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="dashboard-echarts-stub" />,
}));

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import { formatRawAsNumeric } from "../utils/format";

import { routerFuture } from "../router/routerFuture";
import { createWorkbenchMemoryRouter, renderWorkbenchApp } from "./renderWorkbenchApp";

function renderDashboard(client?: ApiClient) {
  if (!client) {
    return renderWorkbenchApp(["/"], { client: createApiClient({ mode: "mock" }) });
  }

  const router = createWorkbenchMemoryRouter(["/"]);

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
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>{children}</ApiClientProvider>
      </QueryClientProvider>
    );
  }

  return render(
    <Wrapper>
      <RouterProvider router={router} future={routerFuture} />
    </Wrapper>,
  );
}

function numericWithRawYuanDisplay(raw: number) {
  return {
    raw,
    unit: "yuan" as const,
    precision: 2,
    sign_aware: false,
    display: raw.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }),
  };
}

function createSameDayCockpitClient(): ApiClient {
  const base = createApiClient({ mode: "mock" });
  return {
    ...base,
    getResearchCalendarEvents: vi.fn(async () => []),
    getPnlByBusinessAnalysis: vi.fn(async (options) => {
      const envelope = await base.getPnlByBusinessAnalysis(options);
      return {
        ...envelope,
        result: {
          ...envelope.result,
          rows:
            options.dimension === "bond_bucket"
              ? [
                  {
                    dimension_key: "rate_bond",
                    dimension_label: "利率债",
                    interest_income: "0",
                    fair_value_change: "0",
                    capital_gain: "0",
                    manual_adjustment: "0",
                    total_pnl: "100.00",
                    avg_balance: "1000.00",
                    current_balance: "1000.00",
                    annualized_yield_pct: "117.741935",
                    ftp_rate_pct: "1.600000",
                    ftp_cost: "1.36",
                    ftp_net_pnl: "98.64",
                    ftp_net_annualized_yield_pct: "116.141935",
                    asset_count: 3,
                  },
                  {
                    dimension_key: "credit_bond",
                    dimension_label: "信用债",
                    interest_income: "0",
                    fair_value_change: "0",
                    capital_gain: "0",
                    manual_adjustment: "0",
                    total_pnl: "80.00",
                    avg_balance: "800.00",
                    current_balance: "800.00",
                    annualized_yield_pct: "98.500000",
                    ftp_rate_pct: "1.600000",
                    ftp_cost: "1.02",
                    ftp_net_pnl: "78.98",
                    ftp_net_annualized_yield_pct: "96.900000",
                    asset_count: 4,
                  },
                  {
                    dimension_key: "financial_bond",
                    dimension_label: "金融债",
                    interest_income: "0",
                    fair_value_change: "0",
                    capital_gain: "0",
                    manual_adjustment: "0",
                    total_pnl: "60.00",
                    avg_balance: "600.00",
                    current_balance: "600.00",
                    annualized_yield_pct: "73.000000",
                    ftp_rate_pct: "1.600000",
                    ftp_cost: "0.82",
                    ftp_net_pnl: "59.18",
                    ftp_net_annualized_yield_pct: "71.400000",
                    asset_count: 2,
                  },
                  {
                    dimension_key: "other_bond",
                    dimension_label: "其它债券",
                    interest_income: "0",
                    fair_value_change: "0",
                    capital_gain: "0",
                    manual_adjustment: "0",
                    total_pnl: "40.00",
                    avg_balance: "400.00",
                    current_balance: "400.00",
                    annualized_yield_pct: "36.500000",
                    ftp_rate_pct: "1.600000",
                    ftp_cost: "0.55",
                    ftp_net_pnl: "39.45",
                    ftp_net_annualized_yield_pct: "34.900000",
                    asset_count: 1,
                  },
                ]
              : [],
        },
      };
    }),
    getBondDashboardHeadlineKpis: vi.fn(async (reportDate) => {
      const envelope = await base.getBondDashboardHeadlineKpis(reportDate);
      return {
        ...envelope,
        result: {
          ...envelope.result,
          report_date: reportDate,
        },
      };
    }),
    getBondAnalyticsPortfolioHeadlines: vi.fn(async (reportDate) => {
      const envelope = await base.getBondAnalyticsPortfolioHeadlines(reportDate);
      return {
        ...envelope,
        result: {
          ...envelope.result,
          report_date: reportDate,
          total_market_value: numericWithRawYuanDisplay(235_000_000_000),
          weighted_ytm: formatRawAsNumeric({ raw: 0.026, unit: "pct", sign_aware: false }),
          weighted_duration: formatRawAsNumeric({ raw: 4.1, unit: "ratio", sign_aware: false }),
          weighted_coupon: formatRawAsNumeric({ raw: 0.021, unit: "pct", sign_aware: false }),
          total_dv01: formatRawAsNumeric({ raw: 88_000_000, unit: "dv01", sign_aware: false }),
          credit_weight: formatRawAsNumeric({ raw: 0.31, unit: "pct", sign_aware: false }),
          issuer_hhi: formatRawAsNumeric({ raw: 0.06, unit: "pct", sign_aware: false }),
          issuer_top5_weight: formatRawAsNumeric({ raw: 0.42, unit: "pct", sign_aware: false }),
          by_asset_class: [
            {
              asset_class: "rate",
              market_value: numericWithRawYuanDisplay(120_000_000_000),
              duration: formatRawAsNumeric({ raw: 5.2, unit: "ratio", sign_aware: false }),
              dv01: formatRawAsNumeric({ raw: 54_000_000, unit: "dv01", sign_aware: false }),
              weight: formatRawAsNumeric({ raw: 0.51, unit: "pct", sign_aware: false }),
            },
            {
              asset_class: "credit",
              market_value: numericWithRawYuanDisplay(73_000_000_000),
              duration: formatRawAsNumeric({ raw: 2.8, unit: "ratio", sign_aware: false }),
              dv01: formatRawAsNumeric({ raw: 21_000_000, unit: "dv01", sign_aware: false }),
              weight: formatRawAsNumeric({ raw: 0.31, unit: "pct", sign_aware: false }),
            },
            {
              asset_class: "other",
              market_value: numericWithRawYuanDisplay(42_000_000_000),
              duration: formatRawAsNumeric({ raw: 0.9, unit: "ratio", sign_aware: false }),
              dv01: formatRawAsNumeric({ raw: 13_000_000, unit: "dv01", sign_aware: false }),
              weight: formatRawAsNumeric({ raw: 0.18, unit: "pct", sign_aware: false }),
            },
          ],
        },
      };
    }),
  };
}

function coreMetricCard(totalAmount: number, rate: number, changeAmount: number, changePct: number) {
  return {
    total_amount: formatRawAsNumeric({ raw: totalAmount, unit: "yuan", sign_aware: false }),
    weighted_avg_rate: formatRawAsNumeric({ raw: rate, unit: "pct", sign_aware: false }),
    change_amount: formatRawAsNumeric({ raw: changeAmount, unit: "yuan", sign_aware: true }),
    change_pct: formatRawAsNumeric({ raw: changePct, unit: "pct", sign_aware: true }),
    top_3_details: [],
  };
}

function expectTitlesInOrder(container: HTMLElement, titles: string[]) {
  const nodes = titles.map((title) => within(container).getByText(title));
  for (let index = 0; index < nodes.length - 1; index += 1) {
    expect(nodes[index].compareDocumentPosition(nodes[index + 1])).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  }
}

function expectTestIdsInOrder(container: HTMLElement, testIds: string[]) {
  const nodes = testIds.map((testId) => within(container).getByTestId(testId));
  for (let index = 0; index < nodes.length - 1; index += 1) {
    expect(nodes[index].compareDocumentPosition(nodes[index + 1])).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  }
}

function addDaysToIsoDate(date: string, days: number): string {
  const parsed = new Date(`${date}T00:00:00Z`);
  parsed.setUTCDate(parsed.getUTCDate() + days);
  return parsed.toISOString().slice(0, 10);
}

function localTodayIsoDate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

async function openDetailDrilldown() {
  const detail = await screen.findByTestId("dashboard-detail-drilldown");
  const summary = detail.querySelector("summary");
  expect(summary).not.toBeNull();
  fireEvent.click(summary as HTMLElement);
  return detail;
}

describe("DashboardPage", () => {
  it("renders the governed dashboard shell while snapshot query is unresolved", async () => {
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

    renderDashboard(slowClient);

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    expect(await screen.findByTestId("workbench-group-nav")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-kpi-band")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
    expect(screen.queryByTestId("dashboard-governed-meta")).not.toBeInTheDocument();
  });

  it("does not promote core metrics into first-screen snapshot metrics when snapshot overview is empty", async () => {
    const base = createApiClient({ mode: "mock" });
    const fallbackClient: ApiClient = {
      ...base,
      mode: "real",
      getHomeSnapshot: async (options) => {
        const envelope = await base.getHomeSnapshot(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            overview: {
              ...envelope.result.overview,
              metrics: [],
            },
          },
        };
      },
      getCoreMetrics: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_dashboard_core_metrics_fallback",
          basis: "analytical" as const,
          result_kind: "dashboard.core_metrics",
          formal_use_allowed: false,
          source_version: "sv_core_metrics_test",
          vendor_version: "vv_core_metrics_test",
          rule_version: "rv_core_metrics_test",
          cache_version: "cv_core_metrics_test",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-08T08:00:00Z",
        },
        result: {
          report_date: "2026-04-08",
          bond_investments: coreMetricCard(12_300_000_000, 0.025, 100_000_000, 0.01),
          interbank_assets: coreMetricCard(8_800_000_000, 0.018, 0, 0),
          interbank_liabilities: coreMetricCard(6_600_000_000, 0.016, -200_000_000, -0.03),
        },
      })),
    };

    renderDashboard(fallbackClient);

    expect(await screen.findByTestId("dashboard-kpi-band")).toBeInTheDocument();

    const supplement = await screen.findByTestId("dashboard-cockpit-supplement");
    fireEvent.click(within(supplement).getByText("同报告日补充读面（展开）"));
    const metricRail = await screen.findByTestId("dashboard-cockpit-metric-rail");
    expect(
      within(metricRail).queryByTestId("dashboard-cockpit-metric-core-bond-investments"),
    ).not.toBeInTheDocument();

    await waitFor(() => {
      expect(fallbackClient.getCoreMetrics).toHaveBeenCalledWith({
        reportDate: "2026-04-18",
      });
    });
  });

  it("derives today todo items from high and medium dashboard alerts", async () => {
    renderDashboard();

    const panel = await screen.findByTestId("dashboard-tasks-calendar");
    expect(await within(panel).findByText("复核：当前处于模拟模式")).toBeInTheDocument();
    expect(within(panel).getByText("今日复核 · 来源：治理预警")).toBeInTheDocument();
    expect(
      within(panel).queryByText("暂无需要今日处理的高/中优先级事项。低优先级观察仍可在预警中心查看。"),
    ).not.toBeInTheDocument();
  });

  it("does not request excluded executive surfaces from the dashboard page", async () => {
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

    renderDashboard(guardedClient);

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-governed-meta")).not.toBeInTheDocument();
    expect(riskCalls).toBe(0);
    expect(contributionCalls).toBe(0);
    expect(alertsCalls).toBe(0);
  });

  it("renders the redesigned root cockpit structure in order", async () => {
    renderDashboard();

    const page = await screen.findByTestId("fixed-income-dashboard-page");
    const toolbar = await screen.findByTestId("dashboard-home-toolbar");
    const judgmentStrip = await screen.findByTestId("dashboard-judgment-strip");
    const kpiBand = await screen.findByTestId("dashboard-kpi-band");
    const marketPulse = await screen.findByTestId("dashboard-cockpit-market-ticker");
    const triptych = await screen.findByTestId("dashboard-main-triptych");
    const depthZone = screen.getByTestId("dashboard-depth-zone");
    const supplement = await screen.findByTestId("dashboard-cockpit-supplement");
    const detailDrilldown = await screen.findByTestId("dashboard-detail-drilldown");

    expect(page).toHaveClass("dashboard-cockpit-page");
    expect(page).toHaveClass("dashboard-cockpit-page--shell-nav");
    expect(screen.queryByTestId("dashboard-cockpit-sidebar")).not.toBeInTheDocument();
    expect(within(kpiBand).getAllByTestId(/^dashboard-kpi-card-/).length).toBe(6);
    expect(within(marketPulse).getAllByTestId(/^dashboard-market-pulse-/).length).toBe(8);
    expect(triptych).toContainElement(screen.getByTestId("dashboard-portfolio-overview"));
    expect(triptych).toContainElement(screen.getByTestId("dashboard-attribution-panel"));
    expect(triptych).toContainElement(screen.getByTestId("dashboard-risk-alert-panel"));
    expect(depthZone).not.toHaveAttribute("hidden");
    expect(screen.getByTestId("dashboard-command-deck")).toHaveAttribute("hidden");
    expect(judgmentStrip).toHaveTextContent("今日经营判断");
    expect(judgmentStrip).toHaveTextContent("估值已完成");
    expect(within(depthZone).getByTestId("dashboard-exposure-table")).toBeInTheDocument();
    expect(within(depthZone).getByTestId("dashboard-balance-summary")).toBeInTheDocument();
    expect(within(depthZone).getByTestId("dashboard-product-pnl-trend")).toBeInTheDocument();
    expect(within(depthZone).getByTestId("dashboard-quick-drilldown")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-improvement-notes")).toBeInTheDocument();
    expect(within(kpiBand).getByText("债券资产规模")).toBeInTheDocument();
    expect(within(kpiBand).getByText("风险集中度（Top5）")).toBeInTheDocument();
    expect(within(marketPulse).getByText("10年国债")).toBeInTheDocument();
    expect(within(marketPulse).getByText("信用利差 中短票AAA")).toBeInTheDocument();
    expect(screen.getByText("组合数")).toBeInTheDocument();
    expect(screen.getByText("1,256 只")).toBeInTheDocument();
    expect(screen.getByText("组合变化说明")).toBeInTheDocument();
    expect(screen.getByText("高风险预警")).toBeInTheDocument();
    expect(within(depthZone).getByText("账户与暴露摘要")).toBeInTheDocument();
    expect(screen.getByText("产品分类损益趋势图")).toBeInTheDocument();

    expectTestIdsInOrder(page, [
      "dashboard-home-toolbar",
      "dashboard-judgment-strip",
      "dashboard-kpi-band",
      "dashboard-cockpit-market-ticker",
      "dashboard-main-triptych",
      "dashboard-improvement-notes",
      "dashboard-data-warning",
      "dashboard-depth-zone",
      "dashboard-action-queue",
      "dashboard-cockpit-supplement",
      "dashboard-detail-drilldown",
    ]);

    expect(supplement).not.toHaveAttribute("open");
    expect(detailDrilldown).not.toHaveAttribute("open");
    expect(within(toolbar).getByLabelText("搜索指标 / 报表 / 功能")).toBeInTheDocument();
    expect(within(toolbar).getByRole("link", { name: "报表中心" })).toHaveAttribute("href", "/reports");
    expect(within(toolbar).getByRole("button", { name: "刷新" })).toBeInTheDocument();
    expect(marketPulse.querySelector(".dashboard-cockpit-pulse__spark")).toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-market-strip")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-product-pnl-empty")).not.toBeInTheDocument();
  });

  it("keeps the top action toolbar ordered around filters and primary routes", async () => {
    renderDashboard();

    const toolbar = await screen.findByTestId("dashboard-home-toolbar");
    const left = toolbar.querySelector(".dashboard-cockpit-header__left");
    const search = toolbar.querySelector(".dashboard-home-toolbar__search");
    const right = toolbar.querySelector(".dashboard-cockpit-header__right");

    expect(left).not.toBeNull();
    expect(search).not.toBeNull();
    expect(right).not.toBeNull();

    const toolbarNodes = [left as HTMLElement, search as HTMLElement, right as HTMLElement];
    for (let index = 0; index < toolbarNodes.length - 1; index += 1) {
      expect(toolbarNodes[index].compareDocumentPosition(toolbarNodes[index + 1])).toBe(
        Node.DOCUMENT_POSITION_FOLLOWING,
      );
    }

    expect(within(right as HTMLElement).getByRole("link", { name: "报表中心" })).toHaveAttribute(
      "href",
      "/reports",
    );
    expect(within(right as HTMLElement).getByRole("link", { name: "数据中心" })).toHaveAttribute(
      "href",
      "/platform-config",
    );
    expect(within(left as HTMLElement).getByLabelText("报告日")).toBeInTheDocument();
    expect(within(right as HTMLElement).getByRole("button", { name: "刷新" })).toBeInTheDocument();
  });

  it("keeps an empty cockpit calendar explicit while linking to observation rows", async () => {
    const client = createSameDayCockpitClient();

    renderDashboard(client);

    const supplement = await screen.findByTestId("dashboard-cockpit-supplement");
    fireEvent.click(within(supplement).getByText("同报告日补充读面（展开）"));
    const calendarPanel = await screen.findByTestId("dashboard-cockpit-calendar-panel");
    const empty = await within(calendarPanel).findByTestId("dashboard-cockpit-calendar-empty");
    expect(empty).toHaveTextContent("无同日事件");
    expect(empty).toHaveTextContent("日历仅作上下文，不写入本日判断");
    expect(await screen.findByTestId("dashboard-cockpit-portfolio-duration-band")).toBeInTheDocument();
    await waitFor(() => {
      expect(empty).toHaveTextContent("转入观察清单");
      expect(empty).toHaveTextContent("组合久期");
    });
    expect(within(empty).getByRole("link", { name: "组合久期 看久期" })).toHaveAttribute("href", "/bond-analysis");
  });

  it("reuses first-screen bond headline data when the drilldown is opened", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      mode: "real",
      getHomeSnapshot: async (options) => {
        const envelope = await base.getHomeSnapshot(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: "2026-04-30",
          },
        };
      },
      getBondDashboardHeadlineKpis: vi.fn((reportDate) =>
        base.getBondDashboardHeadlineKpis(reportDate),
      ),
    };

    renderDashboard(client);

    const supplement = await screen.findByTestId("dashboard-cockpit-supplement");
    fireEvent.click(within(supplement).getByText("同报告日补充读面（展开）"));
    await screen.findByTestId("dashboard-cockpit-metric-rail");
    await waitFor(() => {
      expect(client.getBondDashboardHeadlineKpis).toHaveBeenCalledTimes(1);
    });

    await openDetailDrilldown();
    expect(await screen.findByTestId("dashboard-bond-headline-lead")).toBeInTheDocument();

    await waitFor(() => {
      expect(client.getBondDashboardHeadlineKpis).toHaveBeenCalledTimes(1);
    });
  });

  it("keeps business income and asset-liability summary cards in the deferred depth zone", async () => {
    renderDashboard();

    const page = await screen.findByTestId("fixed-income-dashboard-page");
    const depthZone = screen.getByTestId("dashboard-depth-zone");
    expect(depthZone).not.toHaveAttribute("hidden");
    expect(within(depthZone).getByTestId("dashboard-balance-summary")).toBeInTheDocument();
    expect(within(depthZone).getByTestId("dashboard-exposure-table")).toBeInTheDocument();
    expect(within(depthZone).getByTestId("dashboard-product-pnl-trend")).toBeInTheDocument();
    expect(within(depthZone).getByTestId("dashboard-quick-drilldown")).toBeInTheDocument();

    const supplement = await screen.findByTestId("dashboard-cockpit-supplement");
    fireEvent.click(within(supplement).getByText("同报告日补充读面（展开）"));
    const summary = await screen.findByTestId("dashboard-business-balance-summary");
    const productPanel = within(summary).getByTestId("dashboard-product-category-ytd");

    expectTestIdsInOrder(page, [
      "dashboard-kpi-band",
      "dashboard-main-triptych",
      "dashboard-depth-zone",
      "dashboard-cockpit-supplement",
      "dashboard-detail-drilldown",
    ]);
    expect(within(summary).getByTestId("dashboard-overview-hero-strip")).toBeInTheDocument();
    expect(productPanel).toHaveClass("dashboard-product-category-ytd-panel");
    expect(productPanel.querySelectorAll(".dashboard-product-category-ytd-card")).toHaveLength(3);
    expect(within(summary).getByText("汇总损益与月度损益")).toBeInTheDocument();
    expect(summary).not.toHaveTextContent(/product_category|view=|grand_|report_date|intermediate_business_income/i);
  });

  it("shows the action queue and decision sidebar before drilldown opens", async () => {
    renderDashboard();

    const page = await screen.findByTestId("fixed-income-dashboard-page");
    const actionQueue = screen.getByTestId("dashboard-action-queue");
    const notes = screen.getByTestId("dashboard-improvement-notes");
    const detailDrilldown = await screen.findByTestId("dashboard-detail-drilldown");

    expect(actionQueue).toBeVisible();
    expect(notes).toBeVisible();
    expect(within(actionQueue).getByRole("table")).toBeInTheDocument();
    expect(notes).toHaveTextContent("首页改造重点");
    expect(notes).toHaveTextContent("信息分层重构");
    expect(notes).toHaveTextContent("风险预警前置");
    expect(detailDrilldown).not.toHaveAttribute("open");
    expect(await screen.findByTestId("dashboard-risk-alert-panel")).toBeInTheDocument();
    expectTestIdsInOrder(page, [
      "dashboard-main-triptych",
      "dashboard-improvement-notes",
      "dashboard-depth-zone",
      "dashboard-action-queue",
      "dashboard-detail-drilldown",
    ]);
  });

  it("turns the drilldown area into a review workspace under the summary cockpit", async () => {
    renderDashboard();

    const page = await screen.findByTestId("fixed-income-dashboard-page");
    const detail = await screen.findByTestId("dashboard-detail-drilldown");

    expect(detail).toHaveTextContent("明细穿透");
    expect(detail).toHaveTextContent("下钻复核区");
    expect(detail).toHaveTextContent("解释首屏结论");
    expect(detail).toHaveTextContent("定位数据证据");
    expect(detail).toHaveTextContent("进入专题页复核");
    expectTestIdsInOrder(page, [
      "dashboard-main-triptych",
      "dashboard-detail-drilldown",
    ]);

    fireEvent.click(within(detail).getByText("下钻复核区"));

    expect(await within(detail).findByTestId("dashboard-global-judgment")).toBeInTheDocument();
    expect(await within(detail).findByTestId("dashboard-module-snapshot")).toBeInTheDocument();
    expect(await within(detail).findByTestId("dashboard-alert-center")).toBeInTheDocument();
    expect(within(detail).queryByTestId("dashboard-business-detail-strip")).not.toBeInTheDocument();
    expect(within(detail).queryByTestId("dashboard-structure-risk-focus")).not.toBeInTheDocument();
    expect(within(detail).queryByTestId("dashboard-market-strip")).not.toBeInTheDocument();
    const governedSurface = await within(detail).findByTestId("dashboard-governed-surface");
    expect(governedSurface).toBeInTheDocument();
    expect(governedSurface).toHaveClass("dashboard-governed-surface");
    expect(await within(detail).findByTestId("dashboard-tasks-calendar")).toBeInTheDocument();
    expect(await within(detail).findByTestId("bond-analytics-overview-mid-charts")).toBeInTheDocument();
    expect(await within(detail).findByTestId("dashboard-bond-headline-lead")).toBeInTheDocument();
    expect(await within(detail).findByTestId("dashboard-news-digest-list")).toBeInTheDocument();
    expect(await within(detail).findByTestId("dashboard-bond-counterparty-section")).toBeInTheDocument();
    expect(await within(detail).findByTestId("dashboard-liability-counterparty-section")).toBeInTheDocument();
    expect(await within(detail).findByTestId("dashboard-module-entry-grid")).toBeInTheDocument();
    expect(await within(detail).findByTestId("agent-panel")).toBeInTheDocument();
  });

  it("fills drilldown review cards with status, evidence, and valid actions", async () => {
    renderDashboard();

    const detail = await screen.findByTestId("dashboard-detail-drilldown");
    const judgment = await within(detail).findByTestId("dashboard-global-judgment");
    const modules = await within(detail).findByTestId("dashboard-module-snapshot");
    const alerts = await within(detail).findByTestId("dashboard-alert-center");

    expect(within(judgment).getByText("报告日")).toBeInTheDocument();
    expect(within(judgment).getByText("快照")).toBeInTheDocument();
    expect(within(judgment).getByText("读链路")).toBeInTheDocument();
    expect(within(judgment).getByText("口径/证据")).toBeInTheDocument();

    expect(within(modules).getAllByText("回答什么").length).toBeGreaterThan(0);
    expect(within(modules).getAllByText("进去先看").length).toBeGreaterThan(0);
    expect(within(modules).getAllByText("可用状态").length).toBeGreaterThan(0);
    expect(within(modules).getAllByText("复核信号").length).toBeGreaterThan(0);
    expect(within(modules).getByText("债券分析")).toBeInTheDocument();
    expect(within(modules).getAllByText("临时开放").length).toBeGreaterThan(0);
    expect(within(modules).getByText("DV01 / NIM / 久期与利差")).toBeInTheDocument();

    expect(within(alerts).getByText("待复核事项")).toBeInTheDocument();
    expect(within(alerts).getByText("来源")).toBeInTheDocument();
    expect(within(alerts).getByText("处理入口")).toBeInTheDocument();
    expect(within(alerts).getByRole("link", { name: "打开中台配置" })).toHaveAttribute(
      "href",
      "/platform-config",
    );
  });

  it("falls back to demo market pulse when macro data is unavailable", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getMarketDataRates: vi.fn(async () => {
        throw new Error("macro source unavailable");
      }),
    };

    renderDashboard(client);

    const strip = await screen.findByTestId("dashboard-cockpit-market-ticker");
    expect(within(strip).getAllByTestId(/^dashboard-market-pulse-/).length).toBe(8);
    expect(within(strip).queryByTestId("dashboard-cockpit-market-ticker-unavailable")).not.toBeInTheDocument();
    expect(within(strip).queryByText("Failed to fetch")).not.toBeInTheDocument();
    expect(within(strip).queryByText("数据加载失败")).not.toBeInTheDocument();
  });

  it("renders the dashboard overview cockpit sections", async () => {
    renderDashboard();

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-command-deck")).toHaveAttribute("hidden");
    const kpiBand = await screen.findByTestId("dashboard-kpi-band");
    expect(within(kpiBand).getAllByTestId(/^dashboard-kpi-card-/)).toHaveLength(6);
    expect(within(kpiBand).getByText("年度损益（不扣FTP）")).toBeInTheDocument();
    expect(within(kpiBand).getByText("+29.71 亿")).toBeInTheDocument();
    expect(within(kpiBand).getByText("较昨日 +1.82 亿")).toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-data-status-strip")).not.toBeInTheDocument();

    const marketPulse = await screen.findByTestId("dashboard-cockpit-market-ticker");
    expect(within(marketPulse).getAllByTestId(/^dashboard-market-pulse-/)).toHaveLength(8);
    expect(within(marketPulse).getByText("人民币汇率")).toBeInTheDocument();
    expect(within(marketPulse).getByText("7.2431")).toBeInTheDocument();

    const triptych = await screen.findByTestId("dashboard-main-triptych");
    expect(within(triptych).getByTestId("dashboard-portfolio-overview")).toHaveTextContent("同业资产");
    expect(within(triptych).getByTestId("dashboard-attribution-panel")).toHaveTextContent("当日损益");
    expect(within(triptych).getByTestId("dashboard-risk-alert-panel")).toHaveTextContent("预警 11 项");

    const depthZone = await screen.findByTestId("dashboard-depth-zone");
    expect(within(depthZone).getByText("账户")).toBeInTheDocument();
    expect(within(depthZone).getByText("资产规模（亿）")).toBeInTheDocument();
    expect(within(depthZone).getByText("风险总计")).toBeInTheDocument();
    expect(
      within(depthZone).getByRole("link", { name: /收益归因分析/ }),
    ).toHaveAttribute("href", "/pnl-attribution");
    expect(
      within(depthZone).getByRole("link", { name: /持仓明细/ }),
    ).toHaveAttribute("href", "/positions");
    expect(await screen.findByTestId("dashboard-action-queue")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-improvement-notes")).toHaveTextContent("首页改造重点");
    expect(screen.queryByTestId("dashboard-governed-meta")).not.toBeInTheDocument();
  });

  it("requests bond counterparty stats over the YTD range for the homepage report date", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const getPositionsCounterpartyBonds = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_test_dashboard_bond_counterparty_range",
        basis: "formal" as const,
        result_kind: "positions.counterparty.bonds",
        formal_use_allowed: true,
        source_version: "sv_test",
        vendor_version: "vv_test",
        rule_version: "rv_test",
        cache_version: "cv_test",
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        scenario_flag: false,
        generated_at: "2026-04-21T08:00:00Z",
      },
      result: {
        start_date: "2026-01-01",
        end_date: "2026-03-31",
        num_days: 90,
        items: [],
        total_amount: "0",
        total_avg_daily: "0",
        total_weighted_rate: null,
        total_weighted_coupon_rate: null,
        total_customers: 0,
      },
    }));
    const governedClient: ApiClient = {
      ...base,
      getHomeSnapshot: async (...args) => {
        const envelope = await mockSnapshotSource.getHomeSnapshot(...args);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: "2026-03-31",
          },
        };
      },
      getPositionsCounterpartyBonds,
    };

    renderDashboard(governedClient);

    const detail = await openDetailDrilldown();
    expect(await within(detail).findByTestId("dashboard-bond-counterparty-section")).toBeInTheDocument();
    await waitFor(() => {
      expect(getPositionsCounterpartyBonds).toHaveBeenCalledWith({
        startDate: "2026-01-01",
        endDate: "2026-03-31",
        topN: 5,
        page: 1,
        pageSize: 5,
      });
    });
  });

  it("surfaces counterparty concentration summaries on the home page", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const governedClient: ApiClient = {
      ...base,
      getHomeSnapshot: async (...args) => {
        const envelope = await mockSnapshotSource.getHomeSnapshot(...args);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: "2026-03-31",
          },
        };
      },
      getPositionsCounterpartyBonds: async () => ({
        result_meta: {
          trace_id: "tr_test_dashboard_bond_counterparty",
          basis: "formal",
          result_kind: "positions.counterparty.bonds",
          formal_use_allowed: true,
          source_version: "sv_test",
          vendor_version: "vv_test",
          rule_version: "rv_test",
          cache_version: "cv_test",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-21T08:00:00Z",
        },
        result: {
          start_date: "2026-03-31",
          end_date: "2026-03-31",
          num_days: 1,
          items: [
            {
              customer_name: "青岛银行股份有限公司",
              total_amount: "118857000000",
              avg_daily_balance: "118857000000",
              weighted_rate: "1.9325",
              weighted_coupon_rate: "1.8125",
              transaction_count: 12,
            },
            {
              customer_name: "国家开发银行",
              total_amount: "48968000000",
              avg_daily_balance: "48968000000",
              weighted_rate: "2.0575",
              weighted_coupon_rate: "1.9440",
              transaction_count: 7,
            },
          ],
          total_amount: "167825000000",
          total_avg_daily: "167825000000",
          total_weighted_rate: "1.9691",
          total_weighted_coupon_rate: "1.8523",
          total_customers: 2,
        },
      }),
      getLiabilityCounterparty: async () => ({
        report_date: "2026-03-31",
        total_value: numericWithRawYuanDisplay(64768888887.83),
        top_10: [
          {
            name: "中国农业银行股份有限公司",
            value: numericWithRawYuanDisplay(6000000000),
            type: "Bank",
            weighted_cost: formatRawAsNumeric({ raw: 0.01, unit: "pct", sign_aware: false }),
          },
          {
            name: "浦银理财有限责任公司",
            value: numericWithRawYuanDisplay(5151033152.57),
            type: "NonBank",
            weighted_cost: formatRawAsNumeric({ raw: 0.02, unit: "pct", sign_aware: false }),
          },
        ],
        by_type: [
          {
            name: "Bank",
            value: formatRawAsNumeric({ raw: 38000000000, unit: "yuan", sign_aware: false }),
          },
          {
            name: "NonBank",
            value: formatRawAsNumeric({ raw: 26768888887.83, unit: "yuan", sign_aware: false }),
          },
        ],
      }),
    };

    renderDashboard(governedClient);

    const detail = await openDetailDrilldown();
    const bondSection = await within(detail).findByTestId("dashboard-bond-counterparty-section");
    expect(await within(bondSection).findByText("区间累计")).toBeInTheDocument();
    expect(await within(bondSection).findByText("日均合计")).toBeInTheDocument();
    expect(await within(bondSection).findByText("加权付息率")).toBeInTheDocument();
    expect(await within(bondSection).findByText("青岛银行股份有限公司")).toBeInTheDocument();
    expect(await within(bondSection).findByText("1.97%")).toBeInTheDocument();
    expect(await within(bondSection).findByText("1.85%")).toBeInTheDocument();

    const liabilitySection = await within(detail).findByTestId("dashboard-liability-counterparty-section");
    expect(await within(liabilitySection).findByText("Top1 占比")).toBeInTheDocument();
    expect(await within(liabilitySection).findByText("银行占比")).toBeInTheDocument();
    expect(await within(liabilitySection).findByText("中国农业银行股份有限公司")).toBeInTheDocument();
    expect(within(liabilitySection).getByText("647.69 亿")).toBeInTheDocument();
    expect(within(liabilitySection).getByText(/余额 60\.00 亿/)).toBeInTheDocument();
  });

  it("surfaces a gentle mock-data warning when the app is not using real APIs", async () => {
    renderDashboard();

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-data-warning")).toHaveTextContent("本地模拟数据");
  });

  it("falls back to demo data when the real home snapshot is unreachable", async () => {
    const base = createApiClient({ mode: "real" });
    const client: ApiClient = {
      ...base,
      getHomeSnapshot: vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    };

    renderDashboard(client);

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    const warning = await screen.findByTestId("dashboard-data-warning");
    expect(warning).toHaveTextContent("实时数据源当前不可用");
    expect(warning).not.toHaveTextContent("Failed to fetch");
    expect(await screen.findByText("演示回落")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "重试实时数据" })).toBeInTheDocument();
    const kpiBand = await screen.findByTestId("dashboard-kpi-band");
    expect(within(kpiBand).getAllByTestId(/^dashboard-kpi-card-/).length).toBe(6);
    expect(within(kpiBand).getByText("3,708.10 亿")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-cockpit-market-ticker")).toBeInTheDocument();
  });

  it("prefers real first-screen values over local fallback", async () => {
    const base = createApiClient({ mode: "real" });
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
                value: formatRawAsNumeric({
                  raw: 4_567_890_000_000,
                  unit: "yuan",
                  sign_aware: false,
                }),
                delta: formatRawAsNumeric({
                  raw: 12_300_000_000,
                  unit: "yuan",
                  sign_aware: true,
                }),
                tone: "positive",
                detail: "测试真实接口返回值。",
              },
            ],
          },
        },
      };
    });
    const getMarketDataRates = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_market_real_first",
        basis: "formal" as const,
        result_kind: "market_data.rates",
        formal_use_allowed: true,
        source_version: "sv_test",
        vendor_version: "vv_test",
        rule_version: "rv_test",
        cache_version: "cv_test",
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        scenario_flag: false,
        as_of_date: "2026-04-30",
        generated_at: "2026-04-30T10:40:00+08:00",
      },
      result: {
        read_target: "duckdb" as const,
        series: [
          {
            series_id: "CA.CN_GOV_10Y",
            series_name: "10年国债",
            trade_date: "2026-04-30",
            value_numeric: 2.31,
            frequency: "D",
            unit: "%",
            source_version: "sv_test",
            vendor_version: "vv_test",
            quality_flag: "ok" as const,
            latest_change: -0.04,
          },
        ],
      },
    }));
    const client: ApiClient = {
      ...base,
      getHomeSnapshot,
      getMarketDataRates,
      getResearchCalendarEvents: vi.fn(async () => []),
    };

    renderDashboard(client);

    const kpiBand = await screen.findByTestId("dashboard-kpi-band");
    await waitFor(() => {
      expect(getHomeSnapshot).toHaveBeenCalled();
      expect(within(kpiBand).getByText("45678.90 亿")).toBeInTheDocument();
    });
    expect(within(kpiBand).getByText("年度损益（不扣FTP）")).toBeInTheDocument();
    expect(within(kpiBand).queryByText("3,708.10 亿")).not.toBeInTheDocument();

    const marketPulse = await screen.findByTestId("dashboard-cockpit-market-ticker");
    await waitFor(() => {
      expect(getMarketDataRates).toHaveBeenCalled();
      expect(within(marketPulse).getByText("2.31%")).toBeInTheDocument();
    });
    expect(within(marketPulse).queryByText("1.76%")).not.toBeInTheDocument();
    expect(await screen.findByText("管理视角")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText(/数据已更新/).length).toBeGreaterThan(0);
    });
  });

  it("uses current report date for home snapshot and YTD bond counterparty range", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const snapshotOpts: Array<{ reportDate?: string; allowPartial?: boolean } | undefined> = [];
    const getPositionsCounterpartyBonds = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_test_dashboard_bond_counterparty_range",
        basis: "formal" as const,
        result_kind: "positions.counterparty.bonds",
        formal_use_allowed: true,
        source_version: "sv_test",
        vendor_version: "vv_test",
        rule_version: "rv_test",
        cache_version: "cv_test",
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        scenario_flag: false,
        generated_at: "2026-04-21T08:00:00Z",
      },
      result: {
        start_date: "2026-01-01",
        end_date: "2026-03-31",
        num_days: 90,
        items: [],
        total_amount: "0",
        total_avg_daily: "0",
        total_weighted_rate: null,
        total_weighted_coupon_rate: null,
        total_customers: 0,
      },
    }));
    const datedClient: ApiClient = {
      ...base,
      getHomeSnapshot: async (options) => {
        snapshotOpts.push(options);
        const envelope = await mockSnapshotSource.getHomeSnapshot(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: options?.reportDate || envelope.result.report_date,
          },
        };
      },
      getPositionsCounterpartyBonds,
    };

    renderDashboard(datedClient);

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();

    const reportDateInput = screen.getByLabelText("报告日");
    fireEvent.change(reportDateInput, { target: { value: "2026-03-31" } });

    await waitFor(() => {
      expect(snapshotOpts.some((o) => o?.reportDate === "2026-03-31")).toBe(true);
    });

    const reportDatePill = await screen.findByTestId("governance-pill-report-date");
    await waitFor(() => {
      expect(reportDatePill).toHaveTextContent("2026-03-31");
    });

    await openDetailDrilldown();

    await waitFor(() => {
      expect(getPositionsCounterpartyBonds).toHaveBeenCalledWith({
        startDate: "2026-01-01",
        endDate: "2026-03-31",
        topN: 5,
        page: 1,
        pageSize: 5,
      });
    });
  });

  it("prefers backend-returned snapshot report_date over the local requested date label", async () => {
    const base = createApiClient({ mode: "mock" });
    const governedClient: ApiClient = {
      ...base,
      mode: "real",
      getHomeSnapshot: async (options) => {
        const envelope = await base.getHomeSnapshot(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: "2026-02-28",
          },
          result_meta: {
            ...envelope.result_meta,
            filters_applied: {
              requested_report_date: "2026-02-28",
              effective_report_dates: {
                balance: "2026-02-28",
                pnl: "2026-02-28",
                liability: "2026-02-28",
                risk: "2026-02-28",
              },
            },
          },
        };
      },
    };

    renderDashboard(governedClient);

    const reportDatePill = await screen.findByTestId("governance-pill-report-date");
    await waitFor(() => {
      expect(reportDatePill).toHaveTextContent("2026-02-28");
    });
  });

  it("requests the real key calendar around the current date, not the stale snapshot date", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const today = localTodayIsoDate();
    const researchCalendarCalls: Array<{
      reportDate?: string;
      startDate?: string;
      endDate?: string;
    }> = [];
    const governedClient: ApiClient = {
      ...base,
      getHomeSnapshot: async (options) => {
        const envelope = await mockSnapshotSource.getHomeSnapshot(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: "2026-02-28",
          },
        };
      },
      getResearchCalendarEvents: async (options) => {
        researchCalendarCalls.push(options ?? {});
        return [
          {
            id: "cal_policy_001",
            date: "2026-03-01",
            title: "Policy bank auction",
            kind: "auction",
            severity: "high",
          },
        ];
      },
    };

    renderDashboard(governedClient);

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(researchCalendarCalls).toContainEqual({
        startDate: addDaysToIsoDate(today, -7),
        endDate: addDaysToIsoDate(today, 14),
      });
    });
  });

  it("renders total asset scale with a caliber tag on the hero card", async () => {
    const base = createApiClient({ mode: "mock" });
    const governedClient: ApiClient = {
      ...base,
      mode: "real",
      getHomeSnapshot: async (options) => {
        const envelope = await base.getHomeSnapshot(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            overview: {
              ...envelope.result.overview,
              metrics: [
                {
                  id: "aum",
                  label: "总资产规模",
                  caliber_label: "本币资产口径",
                  value: formatRawAsNumeric({ raw: 3339.26e8, unit: "yuan", sign_aware: false }),
                  delta: formatRawAsNumeric({ raw: -0.002, unit: "pct", sign_aware: true }),
                  tone: "positive",
                  detail: "在 2026-02-28 的本币资产口径市值合计。",
                  history: [3400e8, 3380e8, 3339.26e8],
                },
                ...envelope.result.overview.metrics.filter((metric) => metric.id !== "aum"),
              ],
            },
          },
        };
      },
    };

    renderDashboard(governedClient);

    const heroStrip = await screen.findByTestId("dashboard-overview-hero-strip");
    expect(await within(heroStrip).findByText("总资产规模")).toBeInTheDocument();
    expect(await within(heroStrip).findByText("本币资产口径")).toBeInTheDocument();
  });

  it("links homepage PnL metrics to the governed annual and monthly PnL pages", async () => {
    const base = createApiClient({ mode: "mock" });
    const governedClient: ApiClient = {
      ...base,
      mode: "real",
      getHomeSnapshot: async (options) => {
        const envelope = await base.getHomeSnapshot(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            overview: {
              ...envelope.result.overview,
              metrics: [
                {
                  id: "yield",
                  label: "年度损益（不扣FTP）",
                  caliber_label: "FI + 非标桥接",
                  value: formatRawAsNumeric({ raw: 2_665_696_545.67, unit: "yuan", sign_aware: true }),
                  delta: formatRawAsNumeric({ raw: 0.1, unit: "pct", sign_aware: true }),
                  tone: "positive",
                  detail:
                    "来自 fact_formal_pnl_fi + fact_nonstd_pnl_bridge，截至 2026-04-30 的年度累计 total_pnl，不扣减 FTP。",
                },
              ],
            },
            product_category_ytd: {
              view: "ytd",
              summary_pnl: formatRawAsNumeric({ raw: 1_325_482_375.99, unit: "yuan", sign_aware: true }),
              summary_pnl_detail:
                "与产品分类损益「汇总视图」（view=ytd）页脚 grand_total.business_net_income 一致。",
              operating_income: formatRawAsNumeric({ raw: 1_325_482_375.99, unit: "yuan", sign_aware: true }),
              operating_income_detail:
                "兼容字段：与产品分类损益「汇总视图」（view=ytd）页脚 grand_total.business_net_income 一致。",
              intermediate_business_income: formatRawAsNumeric({ raw: 75_149_887.09, unit: "yuan", sign_aware: true }),
              intermediate_business_income_detail:
                "与产品分类损益「中间业务收入」（intermediate_business_income）ytd 行一致。",
            },
            product_category_monthly: {
              view: "monthly",
              monthly_income: formatRawAsNumeric({ raw: 299_181_927.65, unit: "yuan", sign_aware: true }),
              monthly_income_detail:
                "与产品分类损益「月度视图」（view=monthly）页脚「全部市场科目 + 投资收益合计」一致。",
            },
          },
        };
      },
    };

    renderDashboard(governedClient);

    const heroStrip = await screen.findByTestId("dashboard-overview-hero-strip");
    const annualLink = await within(heroStrip).findByRole("link", { name: /年度损益（不扣FTP）/ });
    expect(annualLink).toHaveAttribute("href", "/pnl-by-business");

    const productCategorySummary = await screen.findByTestId("dashboard-product-category-ytd");
    expect(await within(productCategorySummary).findByText("汇总损益")).toBeInTheDocument();
    expect(await within(productCategorySummary).findByText("+13.25 亿")).toBeInTheDocument();
    expect(await within(productCategorySummary).findByText("月度损益")).toBeInTheDocument();
    expect(await within(productCategorySummary).findByText("+2.99 亿")).toBeInTheDocument();
    expect(
      within(productCategorySummary).getByRole("link", { name: /月度损益/ }),
    ).toHaveAttribute("href", "/product-category-pnl");
  });

  it("renders supply and auction calendar items from the research calendar feed", async () => {
    const base = createApiClient({ mode: "mock" });
    const researchCalendarCalls: Array<{
      reportDate?: string;
      startDate?: string;
      endDate?: string;
    }> = [];
    const client: ApiClient = {
      ...base,
      getResearchCalendarEvents: async (options) => {
        researchCalendarCalls.push(options ?? {});
        return [
          {
            id: "cal_supply_001",
            date: "2026-04-18",
            title: "国债净融资节奏",
            kind: "supply",
            severity: "medium",
            amount_label: "净融资 180 亿元",
            note: "供给节奏",
          },
          {
            id: "cal_auction_002",
            date: "2026-04-19",
            title: "政策性金融债招标",
            kind: "auction",
            severity: "high",
            amount_label: "420 亿元",
            note: "国开行",
          },
        ];
      },
    };

    renderDashboard(client);

    const calendar = await screen.findByTestId("dashboard-tasks-calendar");
    expect(await within(calendar).findByText("国债净融资节奏")).toBeInTheDocument();
    expect(await within(calendar).findByText("政策性金融债招标")).toBeInTheDocument();
    expect(within(calendar).getAllByText("供给").length).toBeGreaterThan(0);
    expect(researchCalendarCalls.some((call) => call.startDate && call.endDate)).toBe(true);
  });

  it("shows only high and medium external events in deterministic dashboard order", async () => {
    const base = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents = vi.fn(async () => [
      {
        id: "low-ignored",
        date: "2026-04-19",
        title: "Ignore low event",
        kind: "macro" as const,
        severity: "low" as const,
      },
      {
        id: "medium-beta",
        date: "2026-04-21",
        title: "Beta medium event",
        kind: "macro" as const,
        severity: "medium" as const,
      },
      {
        id: "high-delta",
        date: "2026-04-21",
        title: "Delta high event",
        kind: "auction" as const,
        severity: "high" as const,
      },
      {
        id: "medium-alpha",
        date: "2026-04-21",
        title: "Alpha medium event",
        kind: "supply" as const,
        severity: "medium" as const,
      },
      {
        id: "high-gamma",
        date: "2026-04-20",
        title: "Gamma earlier high event",
        kind: "macro" as const,
        severity: "high" as const,
      },
    ]);
    const client: ApiClient = {
      ...base,
      getResearchCalendarEvents,
    };

    renderDashboard(client);

    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalled();
    });
    const calendar = await screen.findByTestId("dashboard-tasks-calendar");
    await within(calendar).findByText("Gamma earlier high event");
    expect(within(calendar).queryByText("Ignore low event")).not.toBeInTheDocument();
    expectTitlesInOrder(calendar, [
      "Gamma earlier high event",
      "Delta high event",
      "Alpha medium event",
      "Beta medium event",
    ]);
  });

  it("keeps an explicit no-high-medium state when only low events are returned", async () => {
    const base = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents = vi.fn(async () => [
      {
        id: "low-only",
        date: "2026-04-21",
        title: "Low-only event",
        kind: "macro" as const,
        severity: "low" as const,
      },
    ]);
    const client: ApiClient = {
      ...base,
      getResearchCalendarEvents,
    };

    renderDashboard(client);

    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalled();
    });
    const calendar = await screen.findByTestId("dashboard-tasks-calendar");
    await waitFor(() => {
      expect(calendar).toHaveTextContent("近 7 天至未来 14 天暂无高/中优先级外部事件。");
    });
    expect(within(calendar).queryByText("Low-only event")).not.toBeInTheDocument();
  });

  it("sorts dashboard calendar items by date then severity then stable title", async () => {
    const base = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents = vi.fn(async () => [
      {
        id: "medium-beta",
        date: "2026-04-21",
        title: "Beta medium event",
        kind: "macro" as const,
        severity: "medium" as const,
      },
      {
        id: "high-delta",
        date: "2026-04-21",
        title: "Delta high event",
        kind: "auction" as const,
        severity: "high" as const,
      },
      {
        id: "medium-alpha",
        date: "2026-04-21",
        title: "Alpha medium event",
        kind: "supply" as const,
        severity: "medium" as const,
      },
      {
        id: "high-gamma",
        date: "2026-04-20",
        title: "Gamma earlier high event",
        kind: "macro" as const,
        severity: "high" as const,
      },
    ]);
    const client: ApiClient = {
      ...base,
      getResearchCalendarEvents,
    };

    renderDashboard(client);

    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalled();
    });
    const calendar = await screen.findByTestId("dashboard-tasks-calendar");
    await within(calendar).findByText("Gamma earlier high event");
    expectTitlesInOrder(calendar, [
      "Gamma earlier high event",
      "Delta high event",
      "Alpha medium event",
      "Beta medium event",
    ]);
  });

  it("keeps an explicit no-data state when the external event feed is empty", async () => {
    const base = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents = vi.fn(async () => []);
    const client: ApiClient = {
      ...base,
      getResearchCalendarEvents,
    };

    renderDashboard(client);

    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalled();
    });
    const calendar = await screen.findByTestId("dashboard-tasks-calendar");
    await waitFor(() => {
      expect(calendar).toHaveTextContent("近 7 天至未来 14 天暂无外部日历事件。");
    });
  });

  it("keeps an explicit error state when the external event feed fails", async () => {
    const base = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents = vi.fn(async () => {
      throw new Error("calendar backend unavailable");
    });
    const client: ApiClient = {
      ...base,
      getResearchCalendarEvents,
    };

    renderDashboard(client);

    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalled();
    });
    const calendar = await screen.findByTestId("dashboard-tasks-calendar");
    await waitFor(() => {
      expect(calendar).toHaveTextContent("关键日历外部事件加载失败。");
    });
  });

  it("shows reserved-surface guidance when home snapshot fails with executive reserved detail", async () => {
    const base = createApiClient({ mode: "mock" });
    const reservedDetail =
      "Executive route home_snapshot is reserved by the current boundary.";
    const client: ApiClient = {
      ...base,
      getHomeSnapshot: vi.fn(async () => {
        throw new Error(reservedDetail);
      }),
    };

    renderDashboard(client);

    await screen.findByTestId("fixed-income-dashboard-page");
    await screen.findByTestId("dashboard-governed-surface");
    const errorSection = await screen.findByTestId("data-section-error");
    expect(errorSection).toHaveTextContent("保留面");
    expect(errorSection).not.toHaveTextContent(
      "当前页面保留重试入口，不在浏览器端自行拼接正式口径。",
    );
  });

  it("shows clearer supplement preview cards with drilldown targets", async () => {
    renderDashboard(createSameDayCockpitClient());

    const supplement = await screen.findByTestId("dashboard-cockpit-supplement");
    const preview = within(supplement).getByTestId("dashboard-cockpit-supplement-preview");
    const coverage = within(preview).getByTestId("dashboard-cockpit-preview-coverage");
    const netChange = within(preview).getByTestId("dashboard-cockpit-preview-net-change");
    const concentration = within(preview).getByTestId("dashboard-cockpit-preview-concentration");
    const durationRisk = within(preview).getByTestId("dashboard-cockpit-preview-duration-dv01");

    expect(coverage).toHaveTextContent("补充覆盖");
    expect(within(coverage).getByRole("link")).toHaveAttribute("href", "/platform-config");
    expect(netChange).toHaveTextContent("日净变动");
    expect(within(netChange).getByRole("button")).toBeInTheDocument();
    await waitFor(() => {
      expect(concentration).toHaveTextContent("Top5");
    });
    expect(within(concentration).getByRole("button")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-cockpit-account-table")).toBeInTheDocument();
    expect(durationRisk).toHaveTextContent("利率风险");
    expect(within(durationRisk).getByRole("link")).toHaveAttribute("href", "/risk-tensor");
  });

  it("uses bond-bucket yield facts for asset-class account rows when available", async () => {
    renderDashboard(createSameDayCockpitClient());

    const creditRow = await screen.findByTestId("dashboard-cockpit-account-row-account-credit");
    const rateRow = await screen.findByTestId("dashboard-cockpit-account-row-account-rate");
    const otherRow = await screen.findByTestId("dashboard-cockpit-account-row-account-other");

    await waitFor(() => {
      expect(creditRow).not.toHaveTextContent("-- --");
    });

    expect(creditRow).toHaveTextContent("98.50%");
    expect(rateRow).toHaveTextContent("117.74%");
    expect(otherRow).toHaveTextContent("58.40%");
  });

  it("scrolls to local drilldown sections from supplement preview buttons without forcing the supplement open", async () => {
    renderDashboard(createSameDayCockpitClient());

    const supplement = await screen.findByTestId("dashboard-cockpit-supplement");
    const businessDetail = await screen.findByTestId("dashboard-business-detail-strip");
    const riskReviewRow = await screen.findByTestId(
      "dashboard-cockpit-account-row-account-risk-review",
    );
    const businessDetailScroll = vi.fn();
    const riskReviewScroll = vi.fn();

    businessDetail.scrollIntoView = businessDetailScroll;
    riskReviewRow.scrollIntoView = riskReviewScroll;
    await waitFor(() => {
      expect(riskReviewRow).toHaveTextContent("Top5");
    });
    expect(riskReviewRow).toHaveTextContent("DV01 8,800.00");

    vi.useFakeTimers();
    try {
      fireEvent.click(
        within(screen.getByTestId("dashboard-cockpit-preview-net-change")).getByRole("button"),
      );
      expect(businessDetailScroll).toHaveBeenCalled();
      expect(businessDetail).toHaveAttribute("data-drilldown-active", "true");
      expect(supplement).not.toHaveAttribute("open");

      vi.advanceTimersByTime(1600);
      expect(businessDetail).not.toHaveAttribute("data-drilldown-active");

      fireEvent.click(
        within(screen.getByTestId("dashboard-cockpit-preview-concentration")).getByRole("button"),
      );
      expect(riskReviewScroll).toHaveBeenCalled();
      expect(riskReviewRow).toHaveAttribute("data-drilldown-active", "true");
      expect(riskReviewRow).toHaveTextContent("Top5");
      expect(riskReviewRow).toHaveTextContent("DV01 8,800.00");
      expect(supplement).not.toHaveAttribute("open");

      vi.advanceTimersByTime(1600);
      expect(riskReviewRow).not.toHaveAttribute("data-drilldown-active");
    } finally {
      vi.runOnlyPendingTimers();
      vi.useRealTimers();
    }
  });
});
