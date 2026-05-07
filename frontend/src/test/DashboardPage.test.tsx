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
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    const summary = screen.getByTestId("dashboard-business-balance-summary");
    expect(within(summary).getByTestId("dashboard-overview-hero-strip")).toBeInTheDocument();
    expect(within(summary).getByTestId("dashboard-overview-hero-empty")).toHaveTextContent(
      "资产负债小卡片",
    );
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
    expect(screen.queryByTestId("dashboard-governed-meta")).not.toBeInTheDocument();
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
    const marketStrip = await screen.findByTestId("dashboard-market-strip");
    const judgmentBand = await screen.findByTestId("dashboard-judgment-band");
    const kpiRibbon = await screen.findByTestId("dashboard-kpi-ribbon");
    const businessBalanceSummary = await screen.findByTestId("dashboard-business-balance-summary");
    const analysisGrid = await screen.findByTestId("dashboard-analysis-grid");
    const structureRiskFocus = await screen.findByTestId("dashboard-structure-risk-focus");

    expectTestIdsInOrder(page, [
      "dashboard-market-strip",
      "dashboard-judgment-band",
      "dashboard-kpi-ribbon",
      "dashboard-business-balance-summary",
      "dashboard-analysis-grid",
      "dashboard-structure-risk-focus",
      "dashboard-detail-drilldown",
    ]);

    const pills = await screen.findByTestId("dashboard-governance-pills");
    expect(pills).toBeInTheDocument();
    expect(within(pills).getByTestId("governance-pill-report-date")).toBeInTheDocument();
    expect(within(pills).getByTestId("governance-pill-snapshot")).toBeInTheDocument();
    expect(within(pills).getByTestId("governance-pill-attention")).toBeInTheDocument();
    expect(within(pills).getByTestId("governance-pill-source")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-data-warning")).toBeInTheDocument();

    expect(marketStrip).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-market-ticker")).not.toBeInTheDocument();
    expect(judgmentBand).toBeInTheDocument();
    expect(kpiRibbon).toBeInTheDocument();
    expect(businessBalanceSummary).toBeInTheDocument();
    expect(analysisGrid).toBeInTheDocument();
    expect(structureRiskFocus).toBeInTheDocument();
  });

  it("keeps business income and asset-liability summary cards visible before drilldown", async () => {
    renderDashboard();

    const page = await screen.findByTestId("fixed-income-dashboard-page");
    const summary = await screen.findByTestId("dashboard-business-balance-summary");

    expectTestIdsInOrder(page, [
      "dashboard-kpi-ribbon",
      "dashboard-business-balance-summary",
      "dashboard-analysis-grid",
    ]);
    expect(within(summary).getByTestId("dashboard-overview-hero-strip")).toBeInTheDocument();
    expect(within(summary).getByTestId("dashboard-product-category-ytd")).toBeInTheDocument();
    expect(within(summary).getByText("汇总损益与月度损益")).toBeInTheDocument();
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
    expectTestIdsInOrder(page, ["dashboard-structure-risk-focus", "dashboard-detail-drilldown"]);

    expect(await within(detail).findByTestId("dashboard-global-judgment")).toBeInTheDocument();
    expect(await within(detail).findByTestId("dashboard-module-snapshot")).toBeInTheDocument();
    expect(await within(detail).findByTestId("dashboard-alert-center")).toBeInTheDocument();
    expect(await within(detail).findByTestId("dashboard-governed-surface")).toBeInTheDocument();
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

  it("renders a quiet degraded market strip when macro data is unavailable", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getChoiceMacroLatest: vi.fn(async () => {
        throw new Error("macro source unavailable");
      }),
    };

    renderDashboard(client);

    const strip = await screen.findByTestId("dashboard-market-strip");
    const unavailable = await within(strip).findByTestId("dashboard-market-strip-unavailable");

    expect(unavailable).toHaveTextContent("市场数据暂不可用");
    expect(unavailable).toHaveTextContent("下方明细穿透仍可继续查看");
    expect(within(strip).getByRole("button", { name: "重试" })).toBeEnabled();
    expect(within(strip).queryByText("数据加载失败")).not.toBeInTheDocument();
  });

  it("renders the dashboard overview cockpit sections", async () => {
    renderDashboard();

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-executive-hero")).toHaveClass("dashboard-executive-hero");
    expect(screen.getByTestId("dashboard-bank-ledger-header-link")).toHaveAttribute(
      "href",
      "/bank-ledger-dashboard",
    );
    const pills = await screen.findByTestId("dashboard-governance-pills");
    expect(pills).toBeInTheDocument();
    expect(within(pills).getByTestId("governance-pill-report-date")).toBeInTheDocument();
    expect(within(pills).getByTestId("governance-pill-snapshot")).toBeInTheDocument();
    expect(within(pills).getByTestId("governance-pill-attention")).toBeInTheDocument();
    expect(within(pills).getByTestId("governance-pill-source")).toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-data-status-strip")).not.toBeInTheDocument();
    const judgment = await screen.findByTestId("dashboard-global-judgment");
    expect(judgment).toBeInTheDocument();
    expect(
      await within(judgment).findByText("演示：首屏定调结论占位，用于展示 Pyramid 叙事结构。"),
    ).toBeInTheDocument();
    const moduleSnapshot = await screen.findByTestId("dashboard-module-snapshot");
    expect(moduleSnapshot).toBeInTheDocument();
    const moduleSnapshotLinks = within(moduleSnapshot).getAllByRole("link");
    expect(moduleSnapshotLinks).toHaveLength(7);
    expect(
      moduleSnapshotLinks.some((link) => link.getAttribute("href") === "/bank-ledger-dashboard"),
    ).toBe(true);
    expect(
      within(moduleSnapshot).getByRole("link", { name: /产品损益/ }),
    ).toHaveAttribute("href", "/product-category-pnl");
    expect(
      within(moduleSnapshot).getByRole("link", { name: /风险复核/ }),
    ).toHaveAttribute("href", "/risk-tensor");
    expect(
      within(moduleSnapshot).queryByRole("link", { name: /决策事项/ }),
    ).not.toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-alert-center")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-tasks-calendar")).toBeInTheDocument();
    const moduleEntryGrid = await screen.findByTestId("dashboard-module-entry-grid");
    expect(moduleEntryGrid).toBeInTheDocument();
    expect(
      within(moduleEntryGrid).getByRole("link", { name: /决策事项/ }),
    ).toHaveAttribute("href", "/decision-items");
    expect(
      within(moduleEntryGrid).getByRole("link", { name: /损益解释/ }),
    ).toHaveAttribute("href", "/pnl-bridge");
    expect(
      within(moduleEntryGrid).getByRole("link", { name: /持仓透视/ }),
    ).toHaveAttribute("href", "/positions");
    expect(
      within(moduleEntryGrid).getByRole("link", { name: /中台配置/ }),
    ).toHaveAttribute("href", "/platform-config");
    expect(await screen.findByTestId("dashboard-bond-headline-lead")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-macro-spot-grid")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-news-digest-list")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-bond-counterparty-section")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-liability-counterparty-section")).toBeInTheDocument();
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

    expect(await screen.findByTestId("dashboard-bond-counterparty-section")).toBeInTheDocument();
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

    const bondSection = await screen.findByTestId("dashboard-bond-counterparty-section");
    expect(await within(bondSection).findByText("区间累计")).toBeInTheDocument();
    expect(await within(bondSection).findByText("日均合计")).toBeInTheDocument();
    expect(await within(bondSection).findByText("加权付息率")).toBeInTheDocument();
    expect(await within(bondSection).findByText("青岛银行股份有限公司")).toBeInTheDocument();
    expect(await within(bondSection).findByText("1.97%")).toBeInTheDocument();
    expect(await within(bondSection).findByText("1.85%")).toBeInTheDocument();

    const liabilitySection = await screen.findByTestId("dashboard-liability-counterparty-section");
    expect(await within(liabilitySection).findByText("Top1 占比")).toBeInTheDocument();
    expect(await within(liabilitySection).findByText("银行占比")).toBeInTheDocument();
    expect(await within(liabilitySection).findByText("中国农业银行股份有限公司")).toBeInTheDocument();
    expect(within(liabilitySection).getByText("647.69 亿")).toBeInTheDocument();
    expect(within(liabilitySection).getByText(/余额 60\.00 亿/)).toBeInTheDocument();
  });

  it("surfaces a strong mock-data warning when the app is not using real APIs", async () => {
    renderDashboard();

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-data-warning")).toHaveTextContent("模拟数据源");
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
});
