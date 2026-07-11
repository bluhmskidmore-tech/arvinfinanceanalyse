import { screen, waitFor, within } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { Outlet } from "react-router-dom";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import { primaryWorkbenchNavigation } from "../mocks/navigation";
import { workbenchRoutes, workbenchSections } from "../router/routes";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

const AGENT_QUESTION_INPUT_LABEL = "向 Agent 提问";

vi.mock("../features/agent/AgentWorkbenchPage", () => ({
  default: () => (
    <section data-testid="agent-workbench-page">
      <label>
        向 Agent 提问
        <textarea aria-label="向 Agent 提问" />
      </label>
    </section>
  ),
}));

vi.mock("../features/decision-items/pages/DecisionItemsPage", () => ({
  default: () => (
    <section data-testid="decision-items-page">
      <h1>决策事项</h1>
    </section>
  ),
}));

vi.mock("../features/news-events/NewsEventsPage", () => ({
  default: () => (
    <section>
      <h1 data-testid="news-events-page-title">新闻事件</h1>
      <label>
        topic
        <select aria-label="news-events-topic-code" defaultValue="all">
          <option value="all">all</option>
        </select>
      </label>
      <div data-testid="news-events-table" />
    </section>
  ),
}));

vi.mock("../features/workbench/dashboard-home/DashboardHomePage", () => ({
  default: () => (
    <section data-testid="dashboard-home-page">
      <div data-testid="dashboard-home-hero" />
    </section>
  ),
}));

vi.mock("../features/bond-analytics/components/BondAnalyticsDetailSection", () => ({
  BondAnalyticsDetailSection: ({ activeTab }: { activeTab: string }) => (
    <section data-testid="bond-analysis-detail-section" data-module-key={activeTab}>
      模拟详情
    </section>
  ),
}));

vi.mock("../features/bond-analytics/components/BondAnalyticsView", () => ({
  default: () => (
    <section data-testid="bond-analysis-route-shell">
      <h1>债券分析</h1>
    </section>
  ),
}));

vi.mock("../features/bond-dashboard/pages/BondDashboardPage", () => ({
  default: () => (
    <section data-testid="bond-dashboard-route-shell">
      <h1>债券看板</h1>
    </section>
  ),
}));

vi.mock("../features/kpi-performance/pages/KpiPerformancePage", () => ({
  default: () => (
    <section data-testid="kpi-performance-page">
      <h1>绩效考核</h1>
    </section>
  ),
}));

vi.mock("../features/team-performance/TeamPerformancePage", () => ({
  default: () => (
    <section data-testid="team-performance-page">
      <h1>团队绩效</h1>
    </section>
  ),
}));

vi.mock("../features/platform-config/PlatformConfigPage", () => ({
  default: () => (
    <section data-testid="platform-config-page">
      <h1>平台配置</h1>
    </section>
  ),
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

vi.mock("../features/workbench/module-home/ModuleWorkbenchHomePage", () => ({
  default: ({ kind }: { kind: string }) => (
    <section data-testid="module-workbench-home">
      <h1>
        {kind === "portfolio"
          ? "组合工作台"
          : kind === "market"
            ? "市场工作台"
            : kind === "risk"
              ? "风险工作台"
              : kind === "performance"
                ? "绩效工作台"
                : "报表与数据"}
      </h1>
    </section>
  ),
}));

vi.mock("../features/risk-tensor/RiskTensorPage", () => ({
  default: () => (
    <section data-testid="risk-tensor-kpi-grid">
      <h1>风险张量</h1>
    </section>
  ),
}));

vi.mock("../features/pnl/PnlPage", () => ({
  default: () => (
    <section data-testid="yield-analysis-page">
      <h1>收益分析</h1>
      <label>
        选择报表月份
        <select aria-label="选择报表月份" defaultValue="2026-03-31">
          <option value="2026-03-31">2026-03-31</option>
        </select>
      </label>
      <div data-testid="pnl-overview-cards" />
    </section>
  ),
}));

vi.mock("../features/pnl/PnlBridgePage", () => ({
  default: () => (
    <section data-testid="pnl-bridge-route-page">
      <h1>损益桥接</h1>
      <label>
        报告日
        <select aria-label="pnl-bridge-report-date" defaultValue="2026-03-31">
          <option value="2026-03-31">2026-03-31</option>
        </select>
      </label>
    </section>
  ),
}));

vi.mock("../features/pnl-attribution/pages/PnlAttributionPage", () => ({
  default: () => (
    <section data-testid="pnl-attribution-page">
      <h1>损益归因分析</h1>
    </section>
  ),
}));

vi.mock("../features/product-category-pnl/pages/ProductCategoryAdjustmentAuditPage", () => ({
  default: () => (
    <section data-testid="product-category-adjustment-audit-page">
      <h1>产品损益调整审计</h1>
      <label>
        审计-报表月份
        <select aria-label="审计-报表月份" defaultValue="2026-03">
          <option value="2026-03">2026-03</option>
        </select>
      </label>
    </section>
  ),
}));

vi.mock("../features/average-balance/pages/AverageBalancePage", () => ({
  default: () => (
    <section data-testid="average-balance-page">
      <h1>日均分析</h1>
    </section>
  ),
}));

vi.mock("../features/balance-analysis/pages/BalanceAnalysisPage", () => ({
  default: () => (
    <section data-testid="balance-analysis-page">
      <div data-testid="balance-analysis-overview-cards" />
      <div data-testid="balance-analysis-table" />
    </section>
  ),
}));

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="route-registry-echarts-stub" />,
}));

vi.mock("../features/market-data/pages/MarketDataPage", () => ({
  default: () => (
    <section data-testid="market-data-page">
      <h1 data-testid="market-data-page-title">市场数据</h1>
    </section>
  ),
}));

vi.mock("../features/macro-toolkit/pages/MacroToolkitPage", () => ({
  default: ({ mode }: { mode?: "toolkit" | "observation" }) => (
    <section data-testid={`macro-toolkit-route-${mode ?? "toolkit"}`}>
      <h1>{mode === "observation" ? "宏观观察" : "宏观工具"}</h1>
    </section>
  ),
}));

vi.mock("../features/stock-analysis/pages/StockAnalysisPage", () => ({
  default: () => (
    <section data-testid="stock-analysis-page">
      <h1>股票分析</h1>
    </section>
  ),
}));

vi.mock("../app/ThemedRouteBoundary", () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

beforeAll(async () => {
  await preloadWorkbenchRouteModules("agent", "dashboard-home", "decision-items", "news-events");
}, 20_000);

function ThrowingRoute(): ReactElement {
  throw new Error("route exploded");
}

describe("RouteRegistry", () => {
  const mockClient = createApiClient({ mode: "mock" });

  it("exposes the current visible primary workbench entries", () => {
    expect(workbenchSections).toHaveLength(primaryWorkbenchNavigation.length);
  });

  it("declares a root error boundary and wildcard workbench 404 route", () => {
    const rootRoute = workbenchRoutes.find((route) => route.path === "/");
    const wildcardRoute = rootRoute?.children?.find((route) => route.path === "*");

    expect(rootRoute?.errorElement).toBeDefined();
    expect(wildcardRoute?.element).toBeDefined();
  });

  it("renders a controlled 404 page for unknown workbench paths", async () => {
    renderWorkbenchApp(["/definitely-not-a-workbench-page"], { client: mockClient });

    const notFound = await screen.findByTestId("workbench-not-found-page");
    expect(notFound).toHaveTextContent("/definitely-not-a-workbench-page");
    expect(screen.queryByTestId("dashboard-home-page")).not.toBeInTheDocument();

    const activeGroupLinks = within(await screen.findByTestId("workbench-group-nav"))
      .getAllByRole("link")
      .filter((link) => link.getAttribute("data-active") === "true");
    expect(activeGroupLinks).toHaveLength(0);
  });

  it("renders the route error boundary when a route render fails", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const preventExpectedRouteError = (event: ErrorEvent) => {
      if (event.error instanceof Error && event.error.message === "route exploded") {
        event.preventDefault();
      }
    };
    window.addEventListener("error", preventExpectedRouteError);

    try {
      renderWorkbenchApp(["/boom"], {
        client: mockClient,
        routes: [
          {
            path: "/",
            element: <Outlet />,
            errorElement: workbenchRoutes.find((route) => route.path === "/")?.errorElement,
            children: [{ path: "boom", element: <ThrowingRoute /> }],
          },
        ],
      });

      const errorPage = await screen.findByTestId("workbench-route-error-page");
      expect(errorPage).toHaveTextContent("route exploded");
    } finally {
      window.removeEventListener("error", preventExpectedRouteError);
      consoleError.mockRestore();
    }
  });

  it("renders a permission boundary for route-level 403 errors", async () => {
    renderWorkbenchApp(["/restricted"], {
      client: mockClient,
      routes: [
        {
          path: "/",
          element: <Outlet />,
          errorElement: workbenchRoutes.find((route) => route.path === "/")?.errorElement,
          children: [
            {
              path: "restricted",
              loader: () => {
                throw new Response("not allowed", {
                  status: 403,
                  statusText: "Forbidden",
                });
              },
              element: <div>restricted body</div>,
            },
          ],
        },
      ],
    });

    expect(await screen.findByTestId("workbench-route-permission-page")).toBeInTheDocument();
    expect(screen.queryByText("restricted body")).not.toBeInTheDocument();
  });

  it("renders the dashboard route inside the workbench shell", async () => {
    renderWorkbenchApp(["/"], { client: mockClient });

    expect(await screen.findByText("MOSS")).toBeInTheDocument();
    expect(await screen.findByRole("navigation")).toBeInTheDocument();
    expect(
      within(screen.getByRole("navigation")).getByRole("link", { name: /经营日报/ }),
    ).toBeInTheDocument();
  });

  it("renders the operations-analysis route", async () => {
    renderWorkbenchApp(["/operations-analysis"], { client: mockClient });

    expect(await screen.findByText("MOSS")).toBeInTheDocument();
    expect(await screen.findByRole("navigation")).toBeInTheDocument();
    expect(await screen.findByTestId("workbench-governance-banner")).toBeInTheDocument();
  });

  it("renders the source-preview route as a hidden reserved placeholder", async () => {
    renderWorkbenchApp(["/source-preview"], { client: mockClient });

    expect(await screen.findByTestId("workbench-readiness-banner")).toBeInTheDocument();
    expect(screen.queryByTestId("source-preview-page-title")).not.toBeInTheDocument();
  });

  it("renders the news-events route with NewsEventsPage and governance banner", async () => {
    renderWorkbenchApp(["/news-events"], { client: mockClient });

    expect(await screen.findByTestId("news-events-page-title")).toHaveTextContent("新闻事件");
    expect(await screen.findByTestId("workbench-governance-banner")).toBeInTheDocument();
    expect(await screen.findByTestId("news-events-table")).toBeInTheDocument();
    expect(await screen.findByLabelText("news-events-topic-code")).toBeInTheDocument();
  });

  it("renders the bond-dashboard route", async () => {
    renderWorkbenchApp(["/bond-dashboard"], { client: mockClient });

    expect(await screen.findByTestId("bond-dashboard-route-shell")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "债券看板" })).toBeInTheDocument();
  });

  it("renders the bond-analysis route", async () => {
    renderWorkbenchApp(["/bond-analysis"], { client: mockClient });

    expect(await screen.findByTestId("bond-analysis-route-shell")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "债券分析" })).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-governance-banner")).not.toBeInTheDocument();
  });

  it("renders the cross-asset route", async () => {
    renderWorkbenchApp(["/cross-asset"], { client: mockClient });

    expect(await screen.findByText("MOSS")).toBeInTheDocument();
    expect(await screen.findByRole("navigation")).toBeInTheDocument();
  });

  it("renders the decision-items route", async () => {
    renderWorkbenchApp(["/decision-items"], { client: mockClient });

    expect(await screen.findByTestId("decision-items-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "决策事项" })).toBeInTheDocument();
  });

  it("renders the /dashboard alias", async () => {
    renderWorkbenchApp(["/dashboard"], { client: mockClient });

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
    expect(
      within(await screen.findByTestId("workbench-group-nav")).getByRole("link", {
        name: /经营日报/,
      }),
    ).toBeInTheDocument();
  });

  it("routes the policy funding direct Chinese path to the dashboard home", async () => {
    renderWorkbenchApp(["/政策与资金面"], { client: mockClient });

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
  });

  it("renders the positions route", async () => {
    renderWorkbenchApp(["/positions"], { client: mockClient });

    expect(await screen.findByTestId("positions-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "持仓透视" })).toBeInTheDocument();
    expect(await screen.findByLabelText("positions-report-date")).toBeInTheDocument();
  });

  it("renders the liability-analytics route as a real page", async () => {
    renderWorkbenchApp(["/liability-analytics"], { client: mockClient });

    expect(await screen.findByTestId("liability-analytics-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "负债结构分析" })).toBeInTheDocument();
  });

  it("renders the cashflow-projection route", async () => {
    renderWorkbenchApp(["/cashflow-projection"], { client: mockClient });

    expect(await screen.findByTestId("cashflow-projection-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "现金流预测" })).toBeInTheDocument();
  });

  it("renders the product-category adjustment audit route", async () => {
    renderWorkbenchApp(["/product-category-pnl/audit"], { client: mockClient });

    expect(await screen.findByRole("heading", { name: "产品损益调整审计" })).toBeInTheDocument();
    expect(await screen.findByLabelText("审计-报表月份")).toBeInTheDocument();
  });

  it("renders the market-data route as a live page", async () => {
    renderWorkbenchApp(["/market-data"], { client: mockClient });

    expect(await screen.findByTestId("market-data-page")).toBeInTheDocument();
    expect(await screen.findByTestId("market-data-page-title")).toHaveTextContent("市场数据");
  });

  it("renders the macro-observation route as the read-only macro page", async () => {
    renderWorkbenchApp(["/macro-observation"], { client: mockClient });

    expect(await screen.findByTestId("macro-toolkit-route-observation")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "宏观观察" })).toBeInTheDocument();
  });

  it("renders the stock-analysis route", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: mockClient });

    expect(await screen.findByTestId("stock-analysis-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "股票分析" })).toBeInTheDocument();
  });

  it("redirects V1 bookmark /market to the live market-data page", async () => {
    renderWorkbenchApp(["/market"], { client: mockClient });

    expect(await screen.findByTestId("market-data-page")).toBeInTheDocument();
    expect(await screen.findByTestId("market-data-page-title")).toHaveTextContent("市场数据");
  });

  it("redirects V1 bookmark /assets to bond-dashboard", async () => {
    renderWorkbenchApp(["/assets"], { client: mockClient });

    expect(await screen.findByTestId("bond-dashboard-route-shell")).toBeInTheDocument();
  });

  it("redirects legacy /adb to the average-balance page", async () => {
    renderWorkbenchApp(["/adb"], { client: mockClient });

    expect(await screen.findByTestId("average-balance-page")).toBeInTheDocument();
  });

  it("redirects legacy /macro-analysis to the live market-data page", async () => {
    renderWorkbenchApp(["/macro-analysis"], { client: mockClient });

    expect(await screen.findByTestId("market-data-page")).toBeInTheDocument();
    expect(await screen.findByTestId("market-data-page-title")).toHaveTextContent("市场数据");
  });

  it("renders the balance-analysis route", async () => {
    renderWorkbenchApp(["/balance-analysis"], { client: mockClient });

    expect(
      await screen.findByTestId("balance-analysis-overview-cards", {}, { timeout: 5_000 }),
    ).toBeInTheDocument();
    expect(await screen.findByTestId("balance-analysis-table", {}, { timeout: 8_000 })).toBeInTheDocument();
  }, 20_000);

  it("renders the pnl-bridge route", async () => {
    renderWorkbenchApp(["/pnl-bridge"], { client: mockClient });

    expect(await screen.findByTestId("pnl-bridge-route-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "损益桥接" })).toBeInTheDocument();
    expect(await screen.findByLabelText("pnl-bridge-report-date")).toBeInTheDocument();
  });

  it("renders the pnl route", async () => {
    renderWorkbenchApp(["/pnl"], { client: mockClient });

    expect(await screen.findByTestId("yield-analysis-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "收益分析" })).toBeInTheDocument();
    expect(await screen.findByTestId("pnl-overview-cards")).toBeInTheDocument();
    expect(await screen.findByLabelText("选择报表月份")).toBeInTheDocument();
  });

  it("renders the pnl-attribution route", async () => {
    renderWorkbenchApp(["/pnl-attribution"], { client: mockClient });

    expect(await screen.findByTestId("pnl-attribution-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "损益归因分析" })).toBeInTheDocument();
  });

  it("renders the bank-ledger-dashboard route", async () => {
    renderWorkbenchApp(["/bank-ledger-dashboard"], { client: mockClient });

    expect(await screen.findByTestId("ledger-dashboard-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("ledger-dashboard-kpis")).toHaveTextContent("3289.07 原币合计/1亿");
      expect(screen.getByTestId("ledger-dashboard-kpi-alerts")).toHaveTextContent("--");
      expect(screen.getByTestId("ledger-dashboard-governance-boundary")).toHaveTextContent(
        "source-blocked",
      );
    });
  });

  it("renders the risk-overview route as a live module home page", async () => {
    renderWorkbenchApp(["/risk-overview"], { client: mockClient });

    expect(await screen.findByTestId("module-workbench-home")).toHaveTextContent("风险工作台");
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
  });

  it("renders the reports route as a live module home page", async () => {
    renderWorkbenchApp(["/reports"], { client: mockClient });

    expect(await screen.findByTestId("module-workbench-home")).toHaveTextContent("报表与数据");
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
  });

  it("renders the risk-tensor route", async () => {
    renderWorkbenchApp(["/risk-tensor"], { client: mockClient });

    expect(await screen.findByTestId("risk-tensor-kpi-grid")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "风险张量" })).toBeInTheDocument();
  });

  it("renders the team-performance route", async () => {
    renderWorkbenchApp(["/team-performance"], { client: mockClient });

    expect(await screen.findByTestId("team-performance-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "团队绩效" })).toBeInTheDocument();
  });

  it("renders the kpi route", async () => {
    renderWorkbenchApp(["/kpi"], { client: mockClient });

    expect(await screen.findByTestId("kpi-performance-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "绩效考核" })).toBeInTheDocument();
  });

  it("renders the platform-config route", async () => {
    renderWorkbenchApp(["/platform-config"], { client: mockClient });

    expect(await screen.findByTestId("platform-config-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "平台配置" })).toBeInTheDocument();
  });

  it("renders the cube-query route as a real query page", async () => {
    renderWorkbenchApp(["/cube-query"], { client: mockClient });

    expect(await screen.findByTestId("cube-query-page")).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
  });

  it("routes the hidden /agent path to the agent workbench module", async () => {
    renderWorkbenchApp(["/agent"], { client: mockClient });

    expect(await screen.findByLabelText(AGENT_QUESTION_INPUT_LABEL)).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
  });
});
