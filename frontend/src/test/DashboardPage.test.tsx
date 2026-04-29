import { useState, type ReactNode } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import { formatRawAsNumeric } from "../utils/format";

vi.mock("../features/executive-dashboard/components/PnlAttributionSection", () => ({
  default: () => null,
}));
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
    expect(screen.getByTestId("dashboard-overview-hero-strip")).toBeInTheDocument();
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

  it("renders the dashboard overview cockpit sections", async () => {
    renderDashboard();

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
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
      within(moduleSnapshot).getByRole("link", { name: /风险总览/ }),
    ).toHaveAttribute("href", "/risk-overview");
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

  it("uses one selected report date for the home snapshot query", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const snapshotOpts: Array<{ reportDate?: string; allowPartial?: boolean } | undefined> = [];
    const datedClient: ApiClient = {
      ...base,
      getHomeSnapshot: async (options) => {
        snapshotOpts.push(options);
        return mockSnapshotSource.getHomeSnapshot(options);
      },
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
      expect(reportDatePill).toHaveTextContent("2026-04-18");
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

  it("renders a dedicated no-high-medium state when only low events are returned", async () => {
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

  it("renders a dedicated no-data state when the external event feed is empty", async () => {
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

  it("renders an explicit error state when the external event feed fails", async () => {
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
});
