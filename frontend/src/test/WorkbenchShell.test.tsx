import { screen, waitFor, within } from "@testing-library/react";

import { createApiClient, type ApiClient } from "../api/client";
import type { ResultMeta } from "../api/contracts";
import { WorkbenchShell } from "../layouts/WorkbenchShell";
import { buildShellTickerItems } from "../layouts/workbenchShellTicker";
import {
  primaryWorkbenchNavigation,
  primaryWorkbenchNavigationGroups,
  secondaryWorkbenchNavigation,
} from "../mocks/navigation";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

function createResultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_shell",
    basis: "formal",
    result_kind: "workbench.shell",
    formal_use_allowed: true,
    source_version: "sv_shell",
    vendor_version: "vv_shell",
    rule_version: "rv_shell",
    cache_version: "cv_shell",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-19T00:00:00Z",
    ...overrides,
  };
}

function renderShellAt(path: string, client?: ApiClient) {
  return renderWorkbenchApp([path], {
    routes: [
      {
        path: "/",
        element: <WorkbenchShell />,
        children: [
          { index: true, element: <div>shell body</div> },
          { path: "dashboard", element: <div>dashboard alias body</div> },
          { path: "bond-analysis", element: <div>bond-analysis body</div> },
          { path: "cross-asset", element: <div>cross-asset body</div> },
          { path: "operations-analysis", element: <div>operations body</div> },
          { path: "balance-analysis", element: <div>balance-analysis body</div> },
          { path: "pnl", element: <div>pnl body</div> },
          { path: "platform-config", element: <div>platform body</div> },
          { path: "agent", element: <div>agent body</div> },
        ],
      },
    ],
    client,
  });
}

describe("WorkbenchShell", () => {
  it("renders shell chrome and grouped workspace navigation", async () => {
    renderShellAt("/");

    expect(await screen.findByText("MOSS")).toBeInTheDocument();
    expect(screen.getByTestId("workbench-group-nav")).toBeInTheDocument();
    expect(screen.getByText("shell body")).toBeInTheDocument();
  });

  it("renders a smaller set of grouped workspaces than live route entries", async () => {
    renderShellAt("/");

    const navigation = await screen.findByTestId("workbench-group-nav");
    expect(within(navigation).getAllByRole("link")).toHaveLength(
      primaryWorkbenchNavigationGroups.length,
    );
    expect(primaryWorkbenchNavigationGroups.length).toBeLessThan(
      primaryWorkbenchNavigation.length,
    );
    expect(
      within(navigation).queryByRole("link", { name: "Agent Workbench" }),
    ).not.toBeInTheDocument();
  });

  it("shows current-group section links separately from the workspace groups", async () => {
    renderShellAt("/platform-config");

    const subnav = await screen.findByTestId("workbench-section-subnav");
    const hrefs = within(subnav)
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));
    expect(hrefs).toEqual(["/platform-config"]);
    expect(hrefs).not.toContain("/cube-query");
    expect(hrefs).not.toContain("/reports");
  });

  it("renders a portfolio-specific decision surface when browsing the portfolio workbench", async () => {
    renderShellAt("/pnl");

    const lead = await screen.findByTestId("portfolio-workbench-lead");
    expect(lead).toHaveTextContent("组合状态先看错配，再看损益，最后定位仓位与归因");
    expect(lead).toHaveTextContent("资产负债分析");

    const flow = screen.getByTestId("portfolio-workbench-flow");
    expect(flow).toHaveTextContent("先看资产负债");
    expect(flow).toHaveTextContent("最后做原因解释");

    const board = screen.getByTestId("portfolio-workbench-board");
    expect(board).toHaveTextContent("状态判断");
    expect(board).toHaveTextContent("仓位与结构");
    expect(board).toHaveTextContent("原因解释");
    expect(board).toHaveTextContent("债券总览");
    expect(board).toHaveTextContent("持仓透视");
    expect(board).toHaveTextContent("损益桥接");
  });

  it("shows only a compact portfolio hint on balance-analysis (not the full lead, flow, or board)", async () => {
    renderShellAt("/balance-analysis");

    expect(await screen.findByText("balance-analysis body")).toBeInTheDocument();
    const hint = await screen.findByTestId("portfolio-workbench-light-hint");
    expect(hint).toHaveTextContent("先以正式余额下结论");
    expect(hint).toHaveTextContent("占位模块不混入首屏判断");

    expect(screen.queryByTestId("portfolio-workbench-lead")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-flow")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-board")).not.toBeInTheDocument();
  });

  it("suppresses the portfolio decision shell chrome for bond-analysis", async () => {
    renderShellAt("/bond-analysis");

    expect(await screen.findByText("bond-analysis body")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-lead")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-board")).not.toBeInTheDocument();
    expect(screen.queryByTestId("workbench-section-subnav")).not.toBeInTheDocument();
    expect(screen.queryByTestId("workbench-sidebar-sections")).not.toBeInTheDocument();
  });

  it("uses transparent main surface for cross-asset and keeps market workbench subnav", async () => {
    renderShellAt("/cross-asset");

    expect(await screen.findByText("cross-asset body")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-lead")).not.toBeInTheDocument();
    const subnav = await screen.findByTestId("workbench-section-subnav");
    const sectionLinks = within(subnav).getAllByRole("link");
    expect(sectionLinks.length).toBeGreaterThanOrEqual(1);
    const hrefs = sectionLinks.map((link) => link.getAttribute("href"));
    expect(hrefs).toContain("/cross-asset");
  });

  it("renders a global terminal bar that separates page context from shell market ticker", async () => {
    renderShellAt("/bond-analysis?report_date=2026-03-31");

    expect(await screen.findByText("bond-analysis body")).toBeInTheDocument();

    const terminalBar = screen.getByTestId("workbench-terminal-bar");
    const pageContext = within(terminalBar).getByTestId("workbench-page-context");
    const marketTicker = within(terminalBar).getByTestId("workbench-market-ticker");
    const operatorZone = within(terminalBar).getByTestId("workbench-operator-zone");

    expect(pageContext).toHaveTextContent("债券分析");
    expect(pageContext).toHaveTextContent("2026-03-31");

    expect(marketTicker).toHaveTextContent("Shell Market Ticker");
    expect(marketTicker).toHaveTextContent("10Y");
    expect(marketTicker).toHaveTextContent("DR007");
    expect(marketTicker).toHaveTextContent("USD/CNY");

    expect(operatorZone).toHaveTextContent("报表中心");
    expect(operatorZone).toHaveTextContent("中台配置");
  });

  it("uses backend bond dates and macro latest endpoints for shell report date and ticker values", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsDates: async () => ({
        result_meta: createResultMeta({
          result_kind: "bond_analytics.dates",
        }),
        result: {
          report_dates: ["2026-02-28"],
        },
      }),
      getChoiceMacroLatest: async () => ({
        result_meta: createResultMeta({
          result_kind: "macro.choice.latest",
        }),
        result: {
          read_target: "duckdb" as const,
          series: [
            {
              series_id: "E1000180",
              series_name: "中债国债到期收益率:10年",
              trade_date: "2026-02-28",
              value_numeric: 1.88,
              unit: "%",
              source_version: "sv_macro",
              vendor_version: "vv_macro",
              latest_change: -0.02,
            },
            {
              series_id: "M002",
              series_name: "DR007",
              trade_date: "2026-02-28",
              value_numeric: 1.81,
              unit: "%",
              source_version: "sv_macro",
              vendor_version: "vv_macro",
              latest_change: -0.05,
            },
            {
              series_id: "M001",
              series_name: "公开市场7天逆回购利率",
              trade_date: "2026-02-28",
              value_numeric: 1.75,
              unit: "%",
              source_version: "sv_macro",
              vendor_version: "vv_macro",
              latest_change: 0.01,
            },
            {
              series_id: "CA.USDCNY",
              series_name: "即期汇率:美元兑人民币",
              trade_date: "2026-02-28",
              value_numeric: 7.18,
              unit: "CNY/USD",
              source_version: "sv_macro",
              vendor_version: "vv_macro",
              latest_change: 0.02,
            },
          ],
        },
      }),
    };

    renderShellAt("/bond-analysis", client);

    expect(await screen.findByText("bond-analysis body")).toBeInTheDocument();
    const terminalBar = screen.getByTestId("workbench-terminal-bar");
    const pageContext = within(terminalBar).getByTestId("workbench-page-context");
    const marketTicker = within(terminalBar).getByTestId("workbench-market-ticker");

    await waitFor(() => {
      expect(pageContext).toHaveTextContent("2026-02-28");
      expect(marketTicker).toHaveTextContent("1.88%");
      expect(marketTicker).toHaveTextContent("-2bp");
      expect(marketTicker).toHaveTextContent("1.81%");
      expect(marketTicker).toHaveTextContent("-5bp");
      expect(marketTicker).toHaveTextContent("1.75%");
      expect(marketTicker).toHaveTextContent("+1bp");
      expect(marketTicker).toHaveTextContent("7.18");
      expect(marketTicker).toHaveTextContent("+0.02CNY/USD");
    });
  });

  it("keeps shell ticker fallback when macro latest payload has no result", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getChoiceMacroLatest: async () => ({}),
    } as unknown as ApiClient;

    renderShellAt("/", client);

    const marketTicker = await screen.findByTestId("workbench-market-ticker");
    expect(marketTicker).toHaveTextContent("10Y CGB");
    expect(marketTicker).toHaveTextContent("DR007");
    expect(screen.queryByText("Unexpected Application Error!")).not.toBeInTheDocument();
  });

  it("prefers stable series_id matching for shell tickers before falling back to series_name", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getChoiceMacroLatest: async () => ({
        result_meta: createResultMeta({
          result_kind: "macro.choice.latest",
        }),
        result: {
          read_target: "duckdb" as const,
          series: [
            {
              series_id: "E1000180",
              series_name: "custom ten-year label",
              trade_date: "2026-02-28",
              value_numeric: 1.91,
              unit: "%",
              source_version: "sv_macro",
              vendor_version: "vv_macro",
              latest_change: 0.02,
            },
            {
              series_id: "M002",
              series_name: "custom dr label",
              trade_date: "2026-02-28",
              value_numeric: 1.79,
              unit: "%",
              source_version: "sv_macro",
              vendor_version: "vv_macro",
              latest_change: -0.04,
            },
            {
              series_id: "M001",
              series_name: "custom omo label",
              trade_date: "2026-02-28",
              value_numeric: 1.74,
              unit: "%",
              source_version: "sv_macro",
              vendor_version: "vv_macro",
              latest_change: 0.01,
            },
            {
              series_id: "CA.USDCNY",
              series_name: "custom fx label",
              trade_date: "2026-02-28",
              value_numeric: 7.16,
              unit: "CNY/USD",
              source_version: "sv_macro",
              vendor_version: "vv_macro",
              latest_change: 0.03,
            },
          ],
        },
      }),
    };

    renderShellAt("/bond-analysis?report_date=2026-02-28", client);

    const marketTicker = await screen.findByTestId("workbench-market-ticker");

    await waitFor(() => {
      expect(marketTicker).toHaveTextContent("1.91%");
      expect(marketTicker).toHaveTextContent("1.79%");
      expect(marketTicker).toHaveTextContent("1.74%");
      expect(marketTicker).toHaveTextContent("7.16");
    });
  });

  it("includes stable series_id aliases for future shell ticker concepts", () => {
    const items = buildShellTickerItems(
      [
        {
          series_id: "EMM00166502",
          series_name: "custom policy label",
          trade_date: "2026-02-28",
          value_numeric: 2.09,
          unit: "%",
          source_version: "sv_macro",
          vendor_version: "vv_macro",
          latest_change: 0.01,
        },
        {
          series_id: "CA.US_GOV_10Y",
          series_name: "custom us label",
          trade_date: "2026-02-28",
          value_numeric: 4.12,
          unit: "%",
          source_version: "sv_macro",
          vendor_version: "vv_macro",
          latest_change: 0.03,
        },
        {
          series_id: "CA.CN_US_SPREAD",
          series_name: "custom spread label",
          trade_date: "2026-02-28",
          value_numeric: -205,
          unit: "bp",
          source_version: "sv_macro",
          vendor_version: "vv_macro",
          latest_change: -4,
        },
      ],
      ["policyBank10y", "us10y", "cnUs10ySpread"],
    );

    expect(items).toEqual([
      expect.objectContaining({ key: "policyBank10y", value: "2.09%", delta: "+1bp" }),
      expect.objectContaining({ key: "us10y", value: "4.12%", delta: "+3bp" }),
      expect.objectContaining({ key: "cnUs10ySpread", value: "-205bp", delta: "-4bp" }),
    ]);
  });

  it("renders future shell ticker concepts in the topbar once they are in the display set", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getChoiceMacroLatest: async () => ({
        result_meta: createResultMeta({
          result_kind: "macro.choice.latest",
        }),
        result: {
          read_target: "duckdb" as const,
          series: [
            {
              series_id: "CA.CN_GOV_10Y",
              series_name: "中债国债到期收益率:10年",
              trade_date: "2026-02-28",
              value_numeric: 1.91,
              unit: "%",
              source_version: "sv_macro",
              vendor_version: "vv_macro",
              latest_change: 0.02,
            },
            {
              series_id: "CA.US_GOV_10Y",
              series_name: "美国10年期国债收益率",
              trade_date: "2026-02-28",
              value_numeric: 4.12,
              unit: "%",
              source_version: "sv_macro",
              vendor_version: "vv_macro",
              latest_change: 0.03,
            },
            {
              series_id: "CA.CN_US_SPREAD",
              series_name: "中美国债利差(10Y)",
              trade_date: "2026-02-28",
              value_numeric: -205,
              unit: "bp",
              source_version: "sv_macro",
              vendor_version: "vv_macro",
              latest_change: -4,
            },
            {
              series_id: "EMM00166502",
              series_name: "中债政策性金融债到期收益率(国开行)10年",
              trade_date: "2026-02-28",
              value_numeric: 2.09,
              unit: "%",
              source_version: "sv_macro",
              vendor_version: "vv_macro",
              latest_change: 0.01,
            },
            {
              series_id: "CA.DR007",
              series_name: "存款类机构质押式回购加权利率:DR007",
              trade_date: "2026-02-28",
              value_numeric: 1.79,
              unit: "%",
              source_version: "sv_macro",
              vendor_version: "vv_macro",
              latest_change: -0.04,
            },
            {
              series_id: "M001",
              series_name: "公开市场7天逆回购利率",
              trade_date: "2026-02-28",
              value_numeric: 1.74,
              unit: "%",
              source_version: "sv_macro",
              vendor_version: "vv_macro",
              latest_change: 0.01,
            },
            {
              series_id: "CA.USDCNY",
              series_name: "即期汇率:美元兑人民币",
              trade_date: "2026-02-28",
              value_numeric: 7.16,
              unit: "CNY/USD",
              source_version: "sv_macro",
              vendor_version: "vv_macro",
              latest_change: 0.03,
            },
          ],
        },
      }),
    };

    renderShellAt("/bond-analysis?report_date=2026-02-28", client);

    const marketTicker = await screen.findByTestId("workbench-market-ticker");

    await waitFor(() => {
      expect(marketTicker).toHaveTextContent("US 10Y");
      expect(marketTicker).toHaveTextContent("CN-US 10Y");
      expect(marketTicker).toHaveTextContent("Policy 10Y");
      expect(marketTicker).toHaveTextContent("4.12%");
      expect(marketTicker).toHaveTextContent("-205bp");
      expect(marketTicker).toHaveTextContent("2.09%");
    });
  });

  it("marks the active workspace and keeps auxiliary shell links in a lower-priority support area", async () => {
    renderShellAt("/bond-analysis");

    const navigation = await screen.findByTestId("workbench-group-nav");
    const portfolioLink = within(navigation)
      .getAllByRole("link")
      .find((candidate) => candidate.getAttribute("href") === "/balance-analysis");

    expect(portfolioLink).toBeDefined();
    expect(portfolioLink).toHaveAttribute("data-active", "true");

    const supportNav = screen.getByTestId("workbench-support-nav");
    const supportHrefs = within(supportNav)
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));

    expect(supportHrefs).toContain("/platform-config");
    expect(supportHrefs).toContain("/reports");
  });

  it("does not render the portfolio decision surface outside the portfolio group", async () => {
    renderShellAt("/platform-config");

    expect(await screen.findByText("platform body")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-lead")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-board")).not.toBeInTheDocument();
  });

  it("renders the reserved modules section outside the grouped workspace nav", async () => {
    renderShellAt("/");

    expect(await screen.findByText("Reserved Modules")).toBeInTheDocument();
    for (const section of secondaryWorkbenchNavigation) {
      const link = screen
        .getAllByRole("link")
        .find((candidate) => candidate.getAttribute("href") === section.path);

      expect(link).toBeDefined();
      expect(link).toHaveTextContent(section.label);
    }
  });

  it("does not render the overview hero card on the root dashboard route", async () => {
    renderShellAt("/");

    expect(await screen.findByText("shell body")).toBeInTheDocument();
    expect(screen.queryByText("Phase 1 Status")).not.toBeInTheDocument();
    expect(screen.queryByText("当前只突出可验证的真实读链路")).not.toBeInTheDocument();
  });

  it("shows a readiness banner for gated routes", async () => {
    renderShellAt("/agent");

    expect(await screen.findByTestId("workbench-readiness-banner")).toBeInTheDocument();
    expect(screen.getByText("当前页面尚未物化真实数据链路")).toBeInTheDocument();
    expect(screen.getByText("agent body")).toBeInTheDocument();
  });

  it("treats /dashboard as the dashboard section inside the current group subnav", async () => {
    renderShellAt("/dashboard");

    expect(await screen.findByText("dashboard alias body")).toBeInTheDocument();
    const subnav = screen.getByTestId("workbench-section-subnav");
    const dashLink = within(subnav)
      .getAllByRole("link")
      .find((candidate) => candidate.getAttribute("href") === "/");
    expect(dashLink).toBeDefined();
    expect(dashLink).toHaveAttribute("href", "/");
  });

  it("shows a governance banner for operations-analysis while it is a temporary exception", async () => {
    renderShellAt("/operations-analysis");

    const banner = await screen.findByTestId("workbench-governance-banner");
    expect(banner).toBeInTheDocument();
    expect(screen.getByText("operations body")).toBeInTheDocument();
    expect(banner).toHaveTextContent(/temporary exception/i);
  });
});
