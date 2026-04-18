import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import { primaryWorkbenchNavigation } from "../mocks/navigation";
import { workbenchSections } from "../router/routes";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

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

vi.mock("../features/risk-overview/RiskOverviewPage", () => ({
  default: () => (
    <section data-testid="risk-overview-kpi-grid">
      <h1>风险总览</h1>
      <p>主指标来自正式风险张量接口</p>
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
    <section data-testid="pnl-page">
      <h1>损益明细</h1>
      <label>
        报告日
        <select aria-label="pnl-report-date" defaultValue="2026-03-31">
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

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="route-registry-echarts-stub" />,
}));

describe("RouteRegistry", () => {
  const mockClient = createApiClient({ mode: "mock" });

  it("exposes the current visible primary workbench entries", () => {
    expect(workbenchSections).toHaveLength(primaryWorkbenchNavigation.length);
  });

  it("renders the dashboard route inside the workbench shell", async () => {
    renderWorkbenchApp(["/"], { client: mockClient });

    expect(await screen.findByText("MOSS")).toBeInTheDocument();
    expect(await screen.findByRole("navigation")).toBeInTheDocument();
    expect(
      within(screen.getByRole("navigation")).getByRole("link", { name: /总览工作台/ }),
    ).toBeInTheDocument();
  });

  it("renders the operations-analysis route", async () => {
    renderWorkbenchApp(["/operations-analysis"], { client: mockClient });

    expect(await screen.findByText("MOSS")).toBeInTheDocument();
    expect(await screen.findByRole("navigation")).toBeInTheDocument();
  });

  it("renders the source-preview route", async () => {
    renderWorkbenchApp(["/source-preview"], { client: mockClient });

    expect(await screen.findByText("MOSS")).toBeInTheDocument();
    expect(await screen.findByRole("navigation")).toBeInTheDocument();
  });

  it("renders the news-events route", async () => {
    renderWorkbenchApp(["/news-events"], { client: mockClient });

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
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
  });

  it("renders the cross-asset route", async () => {
    renderWorkbenchApp(["/cross-asset"], { client: mockClient });

    expect(await screen.findByText("MOSS")).toBeInTheDocument();
    expect(await screen.findByRole("navigation")).toBeInTheDocument();
  });

  it("renders the /dashboard alias", async () => {
    renderWorkbenchApp(["/dashboard"], { client: mockClient });

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-module-snapshot")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "驾驶舱" })).toBeInTheDocument();
  });

  it("renders the positions route", async () => {
    renderWorkbenchApp(["/positions"], { client: mockClient });

    expect(await screen.findByTestId("positions-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "持仓透视" })).toBeInTheDocument();
    expect(await screen.findByLabelText("positions-report-date")).toBeInTheDocument();
  });

  it("renders the liability-analytics route as a placeholder surface", async () => {
    renderWorkbenchApp(["/liability-analytics"], { client: mockClient });

    expect(await screen.findByTestId("workbench-readiness-banner")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "负债结构分析" })).toBeInTheDocument();
    expect(
      (await screen.findAllByText(/当前仅保留 compatibility 模块入口/i)).length,
    ).toBeGreaterThan(0);
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

  it("renders the market-data route", async () => {
    renderWorkbenchApp(["/market-data"], { client: mockClient });

    expect(await screen.findByText("MOSS")).toBeInTheDocument();
    expect(await screen.findByRole("navigation")).toBeInTheDocument();
  });

  it("renders the balance-analysis route", async () => {
    renderWorkbenchApp(["/balance-analysis"], { client: mockClient });

    expect(await screen.findByTestId("balance-analysis-overview-cards")).toBeInTheDocument();
    expect(await screen.findByTestId("balance-analysis-table")).toBeInTheDocument();
  });

  it("renders the pnl-bridge route", async () => {
    renderWorkbenchApp(["/pnl-bridge"], { client: mockClient });

    expect(await screen.findByTestId("pnl-bridge-route-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "损益桥接" })).toBeInTheDocument();
    expect(await screen.findByLabelText("pnl-bridge-report-date")).toBeInTheDocument();
  });

  it("renders the pnl route", async () => {
    renderWorkbenchApp(["/pnl"], { client: mockClient });

    expect(await screen.findByTestId("pnl-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "损益明细" })).toBeInTheDocument();
    expect(await screen.findByTestId("pnl-overview-cards")).toBeInTheDocument();
    expect(await screen.findByLabelText("pnl-report-date")).toBeInTheDocument();
  });

  it("renders the pnl-attribution route", async () => {
    renderWorkbenchApp(["/pnl-attribution"], { client: mockClient });

    expect(await screen.findByTestId("pnl-attribution-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "损益归因分析" })).toBeInTheDocument();
  });

  it("renders the risk-overview route as a placeholder surface", async () => {
    renderWorkbenchApp(["/risk-overview"], { client: mockClient });

    expect(await screen.findByTestId("workbench-readiness-banner")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "风险总览" })).toBeInTheDocument();
    expect(
      (await screen.findAllByText(/executive risk overview 仍在当前 cutover 之外/i)).length,
    ).toBeGreaterThan(0);
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

  it("renders the cube-query route as a placeholder surface", async () => {
    renderWorkbenchApp(["/cube-query"], { client: mockClient });

    expect(await screen.findByTestId("workbench-readiness-banner")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "多维查询" })).toBeInTheDocument();
    expect(
      await screen.findByText(/入口保留；自由聚合查询尚未作为 Phase 2 主消费面晋升/i),
    ).toBeInTheDocument();
  });
});
