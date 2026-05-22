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
import { shellTokens } from "../theme/tokens";
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
          { path: "stock-analysis", element: <div>stock-analysis body</div> },
          { path: "operations-analysis", element: <div>operations body</div> },
          { path: "balance-analysis", element: <div>balance-analysis body</div> },
          { path: "balance-movement-analysis", element: <div>balance-movement body</div> },
          { path: "liability-analytics", element: <div>liability-analytics body</div> },
          { path: "pnl", element: <div>pnl body</div> },
          { path: "reports", element: <div>reports body</div> },
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
    expect(screen.queryByTestId("workbench-market-ticker")).not.toBeInTheDocument();
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
  });

  it("shows the Hermes Agent workbench in visible shell navigation", async () => {
    renderShellAt("/");

    const agentNav = await screen.findByTestId("workbench-agent-nav");
    const agentLink = within(agentNav).getByRole("link", { name: /智能体工作台/ });
    expect(agentLink).toHaveAttribute("href", "/agent");
    expect(agentLink).toHaveTextContent("Hermes");
    expect(screen.queryByRole("button", { name: /智能体对话/ })).not.toBeInTheDocument();
  });

  it("shows current-group section links separately from the workspace groups", async () => {
    renderShellAt("/platform-config");

    const subnav = await screen.findByTestId("workbench-section-subnav");
    const hrefs = within(subnav)
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));
    expect(hrefs).toEqual(["/platform-config", "/agent"]);
    expect(hrefs).not.toContain("/cube-query");
    expect(hrefs).not.toContain("/reports");
  });

  it("keeps live portfolio pages focused on page content instead of shell guidance", async () => {
    renderShellAt("/pnl");

    expect(await screen.findByText("pnl body")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-lead")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-flow")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-board")).not.toBeInTheDocument();

    const subnav = screen.getByTestId("workbench-section-subnav");
    expect(subnav).toHaveTextContent("全部已开放页面");
    expect(within(subnav).getByRole("link", { name: /收益分析/ })).toHaveAttribute("href", "/pnl");
  });

  it("keeps live balance-analysis focused on page content with its compact hint", async () => {
    renderShellAt("/balance-analysis");

    expect(await screen.findByText("balance-analysis body")).toBeInTheDocument();
    const hint = await screen.findByTestId("portfolio-workbench-light-hint");
    expect(hint).toHaveTextContent("先以正式余额下结论");
    expect(hint).toHaveTextContent("占位模块不混入首屏判断");

    expect(screen.queryByTestId("portfolio-workbench-lead")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-flow")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-board")).not.toBeInTheDocument();
    const subnav = screen.getByTestId("workbench-section-subnav");
    const hrefs = within(subnav)
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));
    expect(hrefs).toContain("/balance-analysis");
    expect(hrefs).toContain("/balance-movement-analysis");
  });

  it("retains shell guidance and readiness warning for placeholder routes", async () => {
    renderShellAt("/reports");

    expect(await screen.findByText("reports body")).toBeInTheDocument();
    expect(screen.getByText("当前只突出可验证的真实读链路")).toBeInTheDocument();
    expect(screen.getByTestId("workbench-readiness-banner")).toHaveTextContent("当前页面仍是占位壳层");
  });

  it("keeps portfolio page selection while hiding helper chrome on balance-movement-analysis", async () => {
    renderShellAt("/balance-movement-analysis");

    expect(await screen.findByText("balance-movement body")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-light-hint")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-lead")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-flow")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-board")).not.toBeInTheDocument();
    const subnav = screen.getByTestId("workbench-section-subnav");
    const hrefs = within(subnav)
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));
    expect(hrefs).toContain("/balance-movement-analysis");
  });

  it("keeps portfolio page selection while hiding helper chrome on liability-analytics", async () => {
    renderShellAt("/liability-analytics");

    expect(await screen.findByText("liability-analytics body")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-light-hint")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-lead")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-flow")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-board")).not.toBeInTheDocument();
    const subnav = screen.getByTestId("workbench-section-subnav");
    const hrefs = within(subnav)
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));
    expect(hrefs).toContain("/liability-analytics");
  });

  it("suppresses the portfolio decision shell chrome for bond-analysis", async () => {
    renderShellAt("/bond-analysis");

    expect(await screen.findByText("bond-analysis body")).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-terminal-bar")).not.toBeInTheDocument();
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
    const hrefs = sectionLinks.map((link) => link.getAttribute("href"));
    expect(hrefs).toEqual(
      expect.arrayContaining([
        "/market-data",
        "/macro-toolkit",
        "/cross-asset",
        "/stock-analysis",
        "/news-events",
      ]),
    );
    expect(subnav).toHaveTextContent("市场数据");
    expect(subnav).toHaveTextContent("宏观工具");
    expect(subnav).toHaveTextContent("跨资产驱动");
    expect(subnav).toHaveTextContent("股票分析");
    expect(subnav).toHaveTextContent("新闻事件");
  });

  it("renders a global terminal bar that separates page context from shell market ticker", async () => {
    renderShellAt("/cross-asset");

    expect(await screen.findByText("cross-asset body")).toBeInTheDocument();

    const terminalBar = screen.getByTestId("workbench-terminal-bar");
    const pageContext = within(terminalBar).getByTestId("workbench-page-context");
    const marketTicker = within(terminalBar).getByTestId("workbench-market-ticker");
    const operatorZone = within(terminalBar).getByTestId("workbench-operator-zone");

    expect(pageContext).toHaveTextContent("跨资产驱动");
    expect(pageContext).toHaveTextContent("默认路由");

    expect(marketTicker).toHaveTextContent("市场快讯");
    expect(marketTicker).toHaveTextContent("10年国债");
    expect(marketTicker).toHaveTextContent("DR007");
    expect(marketTicker).toHaveTextContent("美元/人民币");

    expect(operatorZone).toHaveTextContent("报表中心");
    expect(operatorZone).toHaveTextContent("中台配置");
  });

  it("keeps bond-analysis page-owned by suppressing shell date and ticker endpoints", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsDates: vi.fn(async () => ({
        result_meta: createResultMeta({
          result_kind: "bond_analytics.dates",
        }),
        result: {
          report_dates: ["2026-02-28"],
        },
      })),
      getChoiceMacroLatest: vi.fn(async () => ({
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
      })),
    };

    renderShellAt("/bond-analysis", client);

    expect(await screen.findByText("bond-analysis body")).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-terminal-bar")).not.toBeInTheDocument();
    expect(client.getBondAnalyticsDates).not.toHaveBeenCalled();
    expect(client.getChoiceMacroLatest).not.toHaveBeenCalled();
  });

  it("keeps shell ticker fallback when macro latest payload has no result", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getChoiceMacroLatest: async () => ({}),
    } as unknown as ApiClient;

    renderShellAt("/cross-asset", client);

    const marketTicker = await screen.findByTestId("workbench-market-ticker");
    expect(marketTicker).toHaveTextContent("10年国债");
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

    renderShellAt("/cross-asset", client);

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

    renderShellAt("/cross-asset", client);

    const marketTicker = await screen.findByTestId("workbench-market-ticker");

    await waitFor(() => {
      expect(marketTicker).toHaveTextContent("10年美债");
      expect(marketTicker).toHaveTextContent("中美10年利差");
      expect(marketTicker).toHaveTextContent("10年国开");
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

  it("marks the active support entry in the warm cockpit rail", async () => {
    renderShellAt("/platform-config");

    expect(await screen.findByText("platform body")).toBeInTheDocument();
    const supportNav = screen.getByTestId("workbench-support-nav");
    const platformLink = within(supportNav).getByRole("link", { name: /中台配置/ });

    expect(platformLink).toHaveAttribute("href", "/platform-config");
    expect(platformLink).toHaveAttribute("data-active", "true");
  });

  it("does not render the portfolio decision surface outside the portfolio group", async () => {
    renderShellAt("/platform-config");

    expect(await screen.findByText("platform body")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-lead")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-board")).not.toBeInTheDocument();
  });

  it("renders the reserved modules section outside the grouped workspace nav", async () => {
    renderShellAt("/");

    expect(await screen.findByText("保留模块")).toBeInTheDocument();
    for (const section of secondaryWorkbenchNavigation) {
      const link = screen
        .getAllByRole("link")
        .find((candidate) => candidate.getAttribute("href") === section.path);

      expect(link).toBeDefined();
      expect(link).toHaveTextContent(section.label);
    }
    expect(screen.queryByRole("button", { name: /智能体对话/ })).not.toBeInTheDocument();
  });

  it("does not render the overview hero card on the root dashboard route", async () => {
    renderShellAt("/");

    expect(await screen.findByText("shell body")).toBeInTheDocument();
    expect(screen.queryByText("Phase 1 Status")).not.toBeInTheDocument();
    expect(screen.queryByText("当前只突出可验证的真实读链路")).not.toBeInTheDocument();
  });

  it("keeps the /agent route reachable from the visible shell shortcuts", async () => {
    renderShellAt("/agent");

    expect(await screen.findByText("agent body")).toBeInTheDocument();
    const agentNav = screen.getByTestId("workbench-agent-nav");
    const agentLink = within(agentNav).getByRole("link", { name: /智能体工作台/ });
    expect(agentLink).toHaveAttribute("href", "/agent");
    expect(agentLink).toHaveAttribute("data-active", "true");
    expect(screen.queryByRole("button", { name: /智能体对话/ })).not.toBeInTheDocument();
  });

  it("lets /dashboard own the cockpit canvas without the group subnav", async () => {
    renderShellAt("/dashboard");

    expect(await screen.findByText("dashboard alias body")).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-section-subnav")).not.toBeInTheDocument();
  });

  it("uses the cockpit shell frame on /dashboard with stable shell chrome hooks", async () => {
    renderShellAt("/dashboard");

    expect(await screen.findByText("dashboard alias body")).toBeInTheDocument();
    const layoutRoot = screen.getByTestId("workbench-group-nav").closest(".workbench-shell-grid--cockpit");
    expect(layoutRoot).not.toBeNull();
    expect(screen.getByText("MOSS").closest("aside")).toHaveStyle({
      background: shellTokens.railBg,
    });
    expect(screen.getByTestId("workbench-support-nav")).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-terminal-bar")).not.toBeInTheDocument();
  });

  it("shows a governance banner for operations-analysis while it is a temporary exception", async () => {
    renderShellAt("/operations-analysis");

    const banner = await screen.findByTestId("workbench-governance-banner");
    expect(banner).toBeInTheDocument();
    expect(screen.getByText("operations body")).toBeInTheDocument();
    expect(banner).toHaveTextContent(/临时例外/i);
  });
});
