import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="dashboard-echarts-stub" />,
}));

import { createApiClient, type ApiClient } from "../api/client";
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
    expect(await within(calendar).findByText("国债净融资节奏")).toBeInTheDocument();
    expect(await within(calendar).findByText("政策性金融债招标")).toBeInTheDocument();
    expect(within(calendar).getAllByText("供给").length).toBeGreaterThan(0);
    expect(researchCalendarCalls.some((call) => call.startDate && call.endDate)).toBe(true);
  });

  it("keeps an explicit no-data state when the external event feed is empty", async () => {
    const getResearchCalendarEvents = vi.fn(async () => []);
    const client = createRealModeHomeClient({ getResearchCalendarEvents });

    renderDashboardHome(client);

    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalled();
    });
    const calendar = await screen.findByTestId("dashboard-home-research-calendar");
    await waitFor(() => {
      expect(calendar).toHaveTextContent("当前窗口暂无供给/招标事件。");
    });
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
      expect(calendar).toHaveTextContent("研究日历加载失败，请稍后刷新。");
    });
  });
});
