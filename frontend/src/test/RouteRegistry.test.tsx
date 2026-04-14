import { screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import { primaryWorkbenchNavigation } from "../mocks/navigation";
import { workbenchSections } from "../router/routes";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

vi.mock("../features/bond-analytics/components/BondAnalyticsDetailSection", () => ({
  BondAnalyticsDetailSection: ({
    activeTab,
  }: {
    activeTab: string;
  }) => (
    <section data-testid="bond-analysis-detail-section" data-module-key={activeTab}>
      mocked detail
    </section>
  ),
}));

vi.mock("../features/bond-analytics/components/BondAnalyticsView", () => ({
  default: () => <section data-testid="bond-analysis-route-shell">mocked bond analytics route</section>,
}));

vi.mock("../features/bond-dashboard/pages/BondDashboardPage", () => ({
  default: () => <section data-testid="bond-dashboard-route-shell">mocked bond dashboard</section>,
}));

vi.mock("../features/kpi-performance/pages/KpiPerformancePage", () => ({
  default: () => (
    <section data-testid="kpi-performance-page">
      <h1>绩效考核</h1>
    </section>
  ),
}));

vi.mock("../features/team-performance/TeamPerformancePage", () => ({
  default: () => <div data-testid="team-performance-page" />,
}));

vi.mock("../features/platform-config/PlatformConfigPage", () => ({
  default: () => <div data-testid="platform-config-page" />,
}));

vi.mock("../features/cube-query/pages/CubeQueryPage", () => ({
  default: () => (
    <section data-testid="cube-query-page">
      <h1>多维查询</h1>
    </section>
  ),
}));

vi.mock("../features/positions/pages/PositionsPage", () => ({
  default: () => (
    <section data-testid="positions-page">
      <h1>持仓透视</h1>
      <label>
        报告日
        <select aria-label="positions-report-date" defaultValue="2025-12-31">
          <option value="2025-12-31">2025-12-31</option>
        </select>
      </label>
    </section>
  ),
}));

vi.mock("../features/liability-analytics/pages/LiabilityAnalyticsPage", () => ({
  default: () => (
    <section data-testid="liability-analytics-page">
      <h1>负债结构分析</h1>
      <label>
        报告日
        <select aria-label="liability-report-date" defaultValue="2025-12-31">
          <option value="2025-12-31">2025-12-31</option>
        </select>
      </label>
    </section>
  ),
}));

vi.mock("../features/cashflow-projection/pages/CashflowProjectionPage", () => ({
  default: () => (
    <section data-testid="cashflow-projection-page">
      <h1>现金流预测</h1>
    </section>
  ),
}));

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="route-registry-echarts-stub" />,
}));

vi.mock("../features/pnl/PnlBridgePage", () => ({
  default: function MockPnlBridgePage() {
    return (
      <section data-testid="pnl-bridge-route-page">
        <h1>损益桥接</h1>
        <div>
          <label>
            <span>报告日</span>
            <select aria-label="pnl-bridge-report-date" defaultValue="2026-03-31">
              <option value="2026-03-31">2026-03-31</option>
            </select>
          </label>
        </div>
      </section>
    );
  },
}));

describe("RouteRegistry", () => {
  describe("risk-overview route", () => {
    beforeEach(() => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async (input: string | URL | Request) => {
          const url =
            typeof input === "string"
              ? input
              : input instanceof URL
                ? input.toString()
                : input.url;
          if (url.includes("/api/bond-analytics/krd-curve-risk")) {
            return {
              ok: true,
              json: async () => ({
                result: {
                  report_date: "2025-12-31",
                  portfolio_duration: "3",
                  portfolio_modified_duration: "3.1",
                  portfolio_dv01: "100",
                  portfolio_convexity: "0.5",
                  krd_buckets: [],
                  scenarios: [],
                  by_asset_class: [],
                  warnings: [],
                  computed_at: "2026-04-12T00:00:00Z",
                },
              }),
            };
          }
          if (url.includes("/api/bond-analytics/credit-spread-migration")) {
            return {
              ok: true,
              json: async () => ({
                result: {
                  report_date: "2025-12-31",
                  credit_bond_count: 10,
                  credit_market_value: "1",
                  credit_weight: "0.1",
                  spread_dv01: "2",
                  weighted_avg_spread: "100",
                  weighted_avg_spread_duration: "4",
                  spread_scenarios: [],
                  migration_scenarios: [],
                  oci_credit_exposure: "0",
                  oci_spread_dv01: "0",
                  oci_sensitivity_25bp: "0",
                  warnings: [],
                  computed_at: "2026-04-12T00:00:00Z",
                },
              }),
            };
          }
          if (url.includes("/api/bond-analytics/action-attribution")) {
            return {
              ok: true,
              json: async () => ({
                result_meta: {
                  trace_id: "tr_action_attr",
                  basis: "formal",
                  result_kind: "bond_analytics.action_attribution",
                  formal_use_allowed: true,
                  source_version: "sv_action_attr",
                  vendor_version: "vv_none",
                  rule_version: "rv_action_attr",
                  cache_version: "cv_action_attr",
                  quality_flag: "ok",
                  vendor_status: "ok",
                  fallback_mode: "none",
                  scenario_flag: false,
                  generated_at: "2026-04-12T00:00:00Z",
                },
                result: {
                  report_date: "2025-12-31",
                  period_type: "MoM",
                  period_start: "2025-12-01",
                  period_end: "2025-12-31",
                  total_actions: 2,
                  total_pnl_from_actions: "100",
                  by_action_type: [],
                  action_details: [],
                  period_start_duration: "3.1",
                  period_end_duration: "3.0",
                  duration_change_from_actions: "-0.1",
                  period_start_dv01: "10",
                  period_end_dv01: "9",
                  warnings: [],
                  computed_at: "2026-04-12T00:00:00Z",
                },
              }),
            };
          }
          return { ok: false, status: 404, json: async () => ({}) };
        }),
      );
    });

    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it("renders the risk-overview route as the live governed page", async () => {
      renderWorkbenchApp(["/risk-overview"], {
        client: createApiClient({ mode: "mock" }),
      });

      expect(
        await screen.findByRole("heading", { name: "风险总览" }, { timeout: 10000 }),
      ).toBeInTheDocument();
      expect(
        await screen.findByText(/主指标来自正式风险张量接口/),
      ).toBeInTheDocument();
      expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
    });
  });

  it("exposes the current visible primary workbench entries", () => {
    expect(workbenchSections).toHaveLength(primaryWorkbenchNavigation.length);
  });

  it("renders the dashboard route inside the workbench shell", async () => {
    renderWorkbenchApp(["/"]);

    expect(await screen.findByText("MOSS")).toBeInTheDocument();
    expect(await screen.findByRole("navigation")).toBeInTheDocument();
    expect(
      within(screen.getByRole("navigation")).getByRole("link", { name: /驾驶舱/ }),
    ).toBeInTheDocument();
  });

  it("renders the operations-analysis route as the consolidated read-only entry", async () => {
    renderWorkbenchApp(["/operations-analysis"]);

    expect(
      await screen.findByRole("heading", { name: "经营分析" }),
    ).toBeInTheDocument();
    expect(await screen.findByTestId("operations-entry-source-count")).toBeInTheDocument();
  });

  it("renders the source-preview route as the canonical source workbench page", async () => {
    renderWorkbenchApp(["/source-preview"]);

    expect(
      await screen.findByRole("heading", { name: "数据源规则预览" }),
    ).toBeInTheDocument();
    expect(await screen.findByLabelText("source-family")).toBeInTheDocument();
  });

  it("renders the news-events route with the read-only news workbench", async () => {
    renderWorkbenchApp(["/news-events"]);

    expect(await screen.findByRole("heading", { name: "新闻事件" })).toBeInTheDocument();
    expect(await screen.findByTestId("news-events-table")).toBeInTheDocument();
    expect(await screen.findByLabelText("news-events-topic-code")).toBeInTheDocument();
  });

  it("renders the bond-dashboard route", async () => {
    renderWorkbenchApp(["/bond-dashboard"], {
      client: createApiClient({ mode: "mock" }),
    });

    expect(await screen.findByTestId("bond-dashboard-route-shell")).toBeInTheDocument();
  });

  it("renders the bond-analysis route as the live governed cockpit", async () => {
    renderWorkbenchApp(["/bond-analysis"]);

    expect(await screen.findByTestId("bond-analysis-route-shell")).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
  });

  it("renders the cross-asset route", async () => {
    renderWorkbenchApp(["/cross-asset"], {
      client: createApiClient({ mode: "mock" }),
    });

    expect(await screen.findByTestId("cross-asset-page")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "跨资产驱动" }),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
  });

  it("renders the /dashboard alias as the fixed-income cockpit", async () => {
    renderWorkbenchApp(["/dashboard"], {
      client: createApiClient({ mode: "mock" }),
    });

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "驾驶舱" }),
    ).toBeInTheDocument();
  });

  it("renders the positions route", async () => {
    renderWorkbenchApp(["/positions"], {
      client: createApiClient({ mode: "mock" }),
    });

    expect(await screen.findByTestId("positions-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "持仓透视" })).toBeInTheDocument();
    expect(await screen.findByLabelText("positions-report-date")).toBeInTheDocument();
  });

  it("renders the liability-analytics route", async () => {
    renderWorkbenchApp(["/liability-analytics"], {
      client: createApiClient({ mode: "mock" }),
    });

    expect(await screen.findByTestId("liability-analytics-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "负债结构分析" })).toBeInTheDocument();
    expect(await screen.findByLabelText("liability-report-date")).toBeInTheDocument();
    expect(
      within(screen.getByRole("navigation")).getByRole("link", { name: /负债结构分析/ }),
    ).toHaveAttribute("href", "/liability-analytics");
  });

  it("renders the cashflow-projection route", async () => {
    renderWorkbenchApp(["/cashflow-projection"], {
      client: createApiClient({ mode: "mock" }),
    });

    expect(await screen.findByTestId("cashflow-projection-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "现金流预测" })).toBeInTheDocument();
    expect(
      within(screen.getByRole("navigation")).getByRole("link", { name: /现金流预测/ }),
    ).toHaveAttribute("href", "/cashflow-projection");
  });

  it("renders the product-category adjustment audit route", async () => {
    renderWorkbenchApp(["/product-category-pnl/audit"]);

    expect(
      await screen.findByRole("heading", { name: "产品损益调整审计" }),
    ).toBeInTheDocument();
    expect(await screen.findByLabelText("审计-报表月份")).toBeInTheDocument();
  });

  it("renders the market-data route with backend-backed content", async () => {
    renderWorkbenchApp(["/market-data"]);

    expect(
      await screen.findByRole("heading", { name: "市场数据工作台" }),
    ).toBeInTheDocument();
    expect(await screen.findByTestId("market-data-catalog-count")).toBeInTheDocument();
  });

  it("renders the hidden balance-analysis route as the first governed balance consumer", async () => {
    renderWorkbenchApp(["/balance-analysis"]);

    expect(
      await screen.findByRole("heading", { name: "资产负债分析" }),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("navigation")).getByRole("link", {
        name: /资产负债分析/,
      }),
    ).toHaveAttribute("href", "/balance-analysis");
    expect(await screen.findByTestId("balance-analysis-table")).toBeInTheDocument();
  });

  it("renders the pnl-bridge route with the governed bridge shell", async () => {
    renderWorkbenchApp(["/pnl-bridge"], {
      client: createApiClient({ mode: "mock" }),
    });

    expect(
      await screen.findByRole("heading", { name: "损益桥接" }),
    ).toBeInTheDocument();
    expect(await screen.findByLabelText("pnl-bridge-report-date")).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
  });

  it("renders the pnl route with the formal PnL workbench shell", async () => {
    renderWorkbenchApp(["/pnl"], {
      client: createApiClient({ mode: "mock" }),
    });

    expect(await screen.findByRole("heading", { name: "损益明细" })).toBeInTheDocument();
    expect(await screen.findByLabelText("pnl-report-date")).toBeInTheDocument();
  });

  it("renders the pnl-attribution route as live", async () => {
    renderWorkbenchApp(["/pnl-attribution"], {
      client: createApiClient({ mode: "mock" }),
    });

    expect(await screen.findByRole("heading", { name: "损益归因分析" })).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
  });

  it("renders the risk-tensor route", async () => {
    renderWorkbenchApp(["/risk-tensor"], {
      client: createApiClient({ mode: "mock" }),
    });

    expect(await screen.findByRole("heading", { name: "风险张量" })).toBeInTheDocument();
    expect(await screen.findByText("组合风险张量")).toBeInTheDocument();
  });

  it("renders the team-performance route as the live team page", async () => {
    renderWorkbenchApp(["/team-performance"], {
      client: createApiClient({ mode: "mock" }),
    });

    expect(await screen.findByTestId("team-performance-page")).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
  });

  it("renders the kpi performance route as live", async () => {
    renderWorkbenchApp(["/kpi"], {
      client: createApiClient({ mode: "mock" }),
    });
    expect(await screen.findByTestId("kpi-performance-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "绩效考核" })).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
  });

  it("renders the platform-config route as the live config page", async () => {
    renderWorkbenchApp(["/platform-config"], {
      client: createApiClient({ mode: "mock" }),
    });

    expect(await screen.findByTestId("platform-config-page")).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
  });

  it("renders the cube-query route", async () => {
    renderWorkbenchApp(["/cube-query"], {
      client: createApiClient({ mode: "mock" }),
    });

    expect(await screen.findByTestId("cube-query-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "多维查询" })).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
  });
});
