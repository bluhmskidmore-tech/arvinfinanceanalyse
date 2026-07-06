import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

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

const WORKBENCH_INSTITUTIONAL_CONSOLE_CSS_PATH = resolve(
  process.cwd(),
  "src/styles/workbenchInstitutionalConsole.css",
);

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
          { path: "portfolio", element: <div>portfolio home body</div> },
          { path: "market-overview", element: <div>market home body</div> },
          { path: "risk-overview", element: <div>risk home body</div> },
          { path: "performance", element: <div>performance home body</div> },
          { path: "bond-analysis", element: <div>bond-analysis body</div> },
          { path: "cross-asset", element: <div>cross-asset body</div> },
          { path: "stock-analysis", element: <div>stock-analysis body</div> },
          { path: "operations-analysis", element: <div>operations body</div> },
          { path: "balance-analysis", element: <div>balance-analysis body</div> },
          { path: "balance-movement-analysis", element: <div>balance-movement body</div> },
          { path: "liability-analytics", element: <div>liability-analytics body</div> },
          { path: "ledger-pnl", element: <div>ledger-pnl body</div> },
          { path: "product-category-pnl", element: <div>product-category-pnl body</div> },
          { path: "pnl-attribution", element: <div>pnl-attribution body</div> },
          { path: "pnl", element: <div>pnl body</div> },
          { path: "reports", element: <div>reports body</div> },
          { path: "platform-config", element: <div>platform body</div> },
          { path: "cube-query", element: <div>cube-query body</div> },
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

  it("lets keyboard users skip shell chrome and focus the main page content", async () => {
    renderShellAt("/cross-asset");

    expect(await screen.findByText("cross-asset body")).toBeInTheDocument();
    const skipLink = screen.getByRole("link", { name: "Skip to main content" });
    const main = screen.getByRole("main", { name: "Main content" });

    expect(skipLink).toHaveAttribute("href", "#workbench-main-content");
    expect(skipLink.compareDocumentPosition(main) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    fireEvent.click(skipLink);

    expect(main).toHaveFocus();
  });

  it("applies the institutional console visual scope to the shared shell root", async () => {
    renderShellAt("/cross-asset");

    expect(await screen.findByText("cross-asset body")).toBeInTheDocument();
    const layoutRoot = screen
      .getByTestId("workbench-group-nav")
      .closest(".workbench-shell-root");

    expect(layoutRoot).toHaveClass("workbench-shell-grid--institutional-console");
  });

  it("keeps the dashboard cockpit shell out of the institutional console scope", async () => {
    renderShellAt("/dashboard");

    expect(await screen.findByText("dashboard alias body")).toBeInTheDocument();
    const layoutRoot = screen
      .getByTestId("workbench-group-nav")
      .closest(".workbench-shell-root");

    expect(layoutRoot).toHaveClass("workbench-shell-grid--cockpit");
    expect(layoutRoot).not.toHaveClass("workbench-shell-grid--institutional-console");
  });

  it("keeps ordinary non-dashboard pages out of the institutional console scope", async () => {
    renderShellAt("/stock-analysis");

    expect(await screen.findByText("stock-analysis body")).toBeInTheDocument();
    const layoutRoot = screen
      .getByTestId("workbench-group-nav")
      .closest(".workbench-shell-root");

    expect(layoutRoot).toHaveClass("workbench-shell-grid--stock-analysis");
    expect(layoutRoot).not.toHaveClass("workbench-shell-grid--institutional-console");
  });

  it("removes the institutional console scope when navigating back to the dashboard cockpit", async () => {
    renderShellAt("/cross-asset");

    expect(await screen.findByText("cross-asset body")).toBeInTheDocument();
    const groupNav = screen.getByTestId("workbench-group-nav");
    const initialLayoutRoot = groupNav.closest(".workbench-shell-root");
    expect(initialLayoutRoot).toHaveClass("workbench-shell-grid--institutional-console");

    const dashboardLink = groupNav.querySelector('a[href="/"]');
    expect(dashboardLink).not.toBeNull();
    fireEvent.click(dashboardLink as HTMLAnchorElement);

    expect(await screen.findByText("shell body")).toBeInTheDocument();
    const returnedLayoutRoot = screen
      .getByTestId("workbench-group-nav")
      .closest(".workbench-shell-root");
    expect(returnedLayoutRoot).toHaveClass("workbench-shell-grid--cockpit");
    expect(returnedLayoutRoot).not.toHaveClass("workbench-shell-grid--institutional-console");
  });

  it("exposes a stable shell scope for the cross-asset flagship layout", async () => {
    renderShellAt("/cross-asset");

    expect(await screen.findByText("cross-asset body")).toBeInTheDocument();
    const layoutRoot = screen
      .getByTestId("workbench-group-nav")
      .closest(".workbench-shell-root");

    expect(layoutRoot).toHaveClass("workbench-shell-grid--cross-asset");
    expect(layoutRoot).toHaveClass("workbench-shell-grid--desktop-aligned");
  });

  it("exposes a stable shell scope for the ledger pnl first-screen layout", async () => {
    renderShellAt("/ledger-pnl");

    expect(await screen.findByText("ledger-pnl body")).toBeInTheDocument();
    const layoutRoot = screen
      .getByTestId("workbench-group-nav")
      .closest(".workbench-shell-root");

    expect(layoutRoot).toHaveClass("workbench-shell-grid--ledger-pnl");
    expect(layoutRoot).toHaveClass("workbench-shell-grid--desktop-aligned");
  });

  it("exposes a stable shell scope for the product-category pnl first-screen layout", async () => {
    renderShellAt("/product-category-pnl");

    expect(await screen.findByText("product-category-pnl body")).toBeInTheDocument();
    const layoutRoot = screen
      .getByTestId("workbench-group-nav")
      .closest(".workbench-shell-root");

    expect(layoutRoot).toHaveClass("workbench-shell-grid--product-category-pnl");
    expect(layoutRoot).toHaveClass("workbench-shell-grid--cockpit");
  });

  it("exposes a stable shell scope for the pnl attribution first-screen layout", async () => {
    renderShellAt("/pnl-attribution");

    expect(await screen.findByText("pnl-attribution body")).toBeInTheDocument();
    const layoutRoot = screen
      .getByTestId("workbench-group-nav")
      .closest(".workbench-shell-root");

    expect(layoutRoot).toHaveClass("workbench-shell-grid--pnl-attribution");
    expect(layoutRoot).toHaveClass("workbench-shell-grid--desktop-aligned");
  });

  it("keeps cross-asset shell compression in the final institutional console layer", () => {
    const css = readFileSync(WORKBENCH_INSTITUTIONAL_CONSOLE_CSS_PATH, "utf8");
    const mobileCss = css.slice(css.indexOf("@media (max-width: 720px)"));
    const desktopBannerBlock =
      css.match(
        /\.workbench-shell-grid--institutional-console\.workbench-shell-grid--cross-asset \[data-testid="workbench-governance-banner"\] \{[\s\S]*?\n  \}/,
      )?.[0] ?? "";
    const desktopBannerHintBlock =
      css.match(
        /\.workbench-shell-grid--institutional-console\.workbench-shell-grid--cross-asset \[data-testid="workbench-governance-banner"\] \.workbench-notice__hint \{[\s\S]*?\n  \}/,
      )?.[0] ?? "";
    const desktopTerminalBlock =
      css.match(
        /\.workbench-shell-grid--institutional-console\.workbench-shell-grid--cross-asset \[data-testid="workbench-terminal-bar"\] \{[\s\S]*?\n  \}/,
      )?.[0] ?? "";
    const desktopTitleBlock =
      css.match(
        /\.workbench-shell-grid--institutional-console\.workbench-shell-grid--cross-asset \.workbench-page-title-display \{[\s\S]*?\n  \}/,
      )?.[0] ?? "";
    const desktopContextTitleBlock =
      css.match(
        /\.workbench-shell-grid--institutional-console\.workbench-shell-grid--cross-asset \[data-testid="workbench-page-context"\] > \.workbench-page-title-display \{[\s\S]*?\n  \}/,
      )?.[0] ?? "";
    const desktopTickerBlock =
      css.match(
        /\.workbench-shell-grid--institutional-console\.workbench-shell-grid--cross-asset \.workbench-market-ticker-shell \{[\s\S]*?\n  \}/,
      )?.[0] ?? "";
    const desktopUtilityBlock =
      css.match(
        /\.workbench-shell-grid--institutional-console\.workbench-shell-grid--cross-asset \.workbench-terminal-utility-navlink \{[\s\S]*?\n  \}/,
      )?.[0] ?? "";

    expect(css).toContain(".workbench-shell-grid--institutional-console.workbench-shell-grid--cross-asset .workbench-main-column");
    expect(css).toContain(
      '.workbench-shell-grid--institutional-console.workbench-shell-grid--cross-asset [data-testid="workbench-section-subnav"]',
    );
    expect(desktopTerminalBlock).toContain("min-height: 40px;");
    expect(desktopTerminalBlock).toContain("padding: 4px 8px !important;");
    expect(desktopTerminalBlock).toContain("box-shadow: none !important;");
    expect(desktopTitleBlock).toContain("font-size: 25px !important;");
    expect(desktopTitleBlock).toContain("line-height: 0.98 !important;");
    expect(desktopContextTitleBlock).toContain("font-size: 25px !important;");
    expect(desktopContextTitleBlock).toContain("line-height: 0.98 !important;");
    expect(desktopTickerBlock).toContain("padding: 1px 4px 3px !important;");
    expect(desktopTickerBlock).toContain("gap: 6px !important;");
    expect(desktopUtilityBlock).toContain("padding: 2px 1px !important;");
    expect(desktopUtilityBlock).toContain("font-size: 11px;");
    expect(desktopBannerBlock).toContain("grid-template-columns: auto minmax(0, 1fr) minmax(210px, 0.42fr);");
    expect(desktopBannerBlock).toContain("align-items: center;");
    expect(desktopBannerBlock).toContain("min-height: 36px;");
    expect(desktopBannerBlock).toContain("padding: 5px 10px !important;");
    expect(desktopBannerBlock).toContain("border-color: rgba(184, 138, 45, 0.28) !important;");
    expect(desktopBannerBlock).toContain("background:");
    expect(desktopBannerBlock).toContain("rgba(184, 138, 45, 0.07)");
    expect(desktopBannerHintBlock).toContain("grid-column: auto;");
    expect(desktopBannerHintBlock).toContain("overflow: hidden;");
    expect(desktopBannerHintBlock).toContain("text-overflow: ellipsis;");
    expect(desktopBannerHintBlock).toContain("white-space: nowrap;");
    expect(css).toContain(".workbench-section-subnav__header {\n    display: none !important;");
    expect(mobileCss).not.toContain("workbench-shell-grid--cross-asset");
    expect(css).not.toContain(':has([data-testid="cross-asset-drivers-page"])');
    expect(css).not.toMatch(/workbench-shell-grid--cross-asset[\s\S]{0,180}> div/);
  });

  it("keeps ledger pnl shell compression in the final institutional console layer", () => {
    const css = readFileSync(WORKBENCH_INSTITUTIONAL_CONSOLE_CSS_PATH, "utf8");
    const mobileCss = css.slice(css.indexOf("@media (max-width: 720px)"));

    expect(css).toContain(".workbench-shell-grid--institutional-console.workbench-shell-grid--ledger-pnl .workbench-main-column");
    expect(css).toContain(
      '.workbench-shell-grid--institutional-console.workbench-shell-grid--ledger-pnl [data-testid="workbench-section-subnav"]',
    );
    expect(mobileCss).not.toContain("workbench-shell-grid--ledger-pnl");
    expect(css).not.toContain(':has([data-testid="ledger-pnl-page"])');
    expect(css).not.toMatch(/workbench-shell-grid--ledger-pnl[\s\S]{0,180}> div/);
  });

  it("keeps product-category pnl shell compression in the final institutional console layer", () => {
    const css = readFileSync(WORKBENCH_INSTITUTIONAL_CONSOLE_CSS_PATH, "utf8");
    const mobileCss = css.slice(css.indexOf("@media (max-width: 720px)"));

    expect(css).toContain(".workbench-shell-grid--institutional-console.workbench-shell-grid--product-category-pnl .workbench-main-column");
    expect(css).toContain(
      '.workbench-shell-grid--institutional-console.workbench-shell-grid--product-category-pnl [data-testid="workbench-section-subnav"]',
    );
    expect(mobileCss).not.toContain("workbench-shell-grid--product-category-pnl");
    expect(css).not.toContain(':has([data-testid="product-category-page"])');
    expect(css).not.toMatch(/workbench-shell-grid--product-category-pnl[\s\S]{0,180}> div/);
  });

  it("keeps pnl attribution shell compression in the final institutional console layer", () => {
    const css = readFileSync(WORKBENCH_INSTITUTIONAL_CONSOLE_CSS_PATH, "utf8");
    const mobileCss = css.slice(css.indexOf("@media (max-width: 720px)"));

    expect(css).toContain(".workbench-shell-grid--institutional-console.workbench-shell-grid--pnl-attribution .workbench-main-column");
    expect(css).toContain(
      '.workbench-shell-grid--institutional-console.workbench-shell-grid--pnl-attribution [data-testid="workbench-section-subnav"]',
    );
    expect(mobileCss).not.toContain("workbench-shell-grid--pnl-attribution");
    expect(css).not.toContain(':has([data-testid="pnl-attribution-page-title"])');
    expect(css).not.toMatch(/workbench-shell-grid--pnl-attribution[\s\S]{0,180}> div/);
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

  it("shows MOSS Chat in visible shell navigation", async () => {
    renderShellAt("/");

    const agentNav = await screen.findByTestId("workbench-agent-nav");
    const agentLink = within(agentNav).getByRole("link", { name: /MOSS Chat/ });
    expect(agentLink).toHaveAttribute("href", "/agent");
    expect(agentNav).toHaveTextContent("对话");
    expect(agentLink).toHaveTextContent("可用");
    expect(agentNav).toHaveTextContent("直接提问");
    expect(screen.queryByRole("button", { name: /智能体对话/ })).not.toBeInTheDocument();
  });

  it("uses stock-analysis shell labels without exposing Agent wording in the rail", async () => {
    renderShellAt("/stock-analysis");

    expect(await screen.findByText("stock-analysis body")).toBeInTheDocument();
    const layoutRoot = screen.getByTestId("workbench-group-nav").closest(".workbench-shell-grid--stock-analysis");
    expect(layoutRoot).not.toBeNull();

    const agentNav = screen.getByTestId("workbench-agent-nav");
    const agentLink = within(agentNav).getByRole("link", { name: /复核助手/ });
    expect(agentLink).toHaveAttribute("href", "/agent");
    expect(agentNav).toHaveTextContent("复核");
    expect(agentNav).toHaveTextContent("跨页证据");
    expect(agentNav).not.toHaveTextContent("Agent");
    expect(agentNav).not.toHaveTextContent("Hermes");
  });

  it("shows current-group section links separately from the workspace groups", async () => {
    renderShellAt("/platform-config");

    const subnav = await screen.findByTestId("workbench-section-subnav");
    const hrefs = within(subnav)
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));
    expect(hrefs).toEqual(["/platform-config", "/reports", "/cube-query", "/agent"]);
    expect(hrefs).toContain("/reports");
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

  it("keeps live balance-analysis focused on page content without shell guidance", async () => {
    renderShellAt("/balance-analysis");

    expect(await screen.findByText("balance-analysis body")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-light-hint")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-lead")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-flow")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-board")).not.toBeInTheDocument();
    expect(screen.queryByTestId("workbench-section-subnav")).not.toBeInTheDocument();
  });

  it("uses the live reports home without old placeholder guidance", async () => {
    renderShellAt("/reports");

    expect(await screen.findByText("reports body")).toBeInTheDocument();
    expect(screen.queryByText("当前只突出可验证的真实读链路")).not.toBeInTheDocument();
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
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
    expect(screen.queryByTestId("workbench-governance-banner")).not.toBeInTheDocument();
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
      .find((candidate) => candidate.getAttribute("href") === "/portfolio");

    expect(portfolioLink).toBeDefined();
    expect(portfolioLink).toHaveAttribute("data-active", "true");

    const supportNav = screen.getByTestId("workbench-support-nav");
    const supportHrefs = within(supportNav)
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));

    expect(supportHrefs).toContain("/platform-config");
    expect(supportHrefs).toContain("/reports");
  });

  it("marks the active support entry in the homepage-aligned cockpit rail", async () => {
    renderShellAt("/platform-config");

    expect(await screen.findByText("platform body")).toBeInTheDocument();
    const supportNav = screen.getByTestId("workbench-support-nav");
    const platformLink = within(supportNav).getByRole("link", { name: /中台配置/ });

    expect(platformLink).toHaveAttribute("href", "/platform-config");
    expect(platformLink).toHaveAttribute("data-active", "true");
    expect(within(supportNav).getByRole("link", { name: /报表中心/ })).toHaveAttribute(
      "href",
      "/reports",
    );
    expect(within(supportNav).getByRole("link", { name: /帮助文档/ })).toHaveAttribute("href", "/");

    const operatorZone = screen.getByTestId("workbench-operator-zone");
    const operatorPlatformLink = within(operatorZone).getByRole("link", { name: /中台配置/ });
    expect(operatorPlatformLink).toHaveAttribute("href", "/platform-config");
    expect(operatorPlatformLink).toHaveAttribute("data-active", "true");
  });

  it("does not render the portfolio decision surface outside the portfolio group", async () => {
    renderShellAt("/platform-config");

    expect(await screen.findByText("platform body")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-lead")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-board")).not.toBeInTheDocument();
  });

  it("hides the planned modules section when no visible placeholders remain", async () => {
    renderShellAt("/");

    expect(await screen.findByText("shell body")).toBeInTheDocument();
    expect(screen.queryByText("规划入口")).not.toBeInTheDocument();
    expect(screen.queryByText("保留模块")).not.toBeInTheDocument();
    expect(screen.queryByText("Reserved")).not.toBeInTheDocument();
    expect(secondaryWorkbenchNavigation).toHaveLength(0);
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
    const agentLink = within(agentNav).getByRole("link", { name: /MOSS Chat/ });
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
    expect(screen.getByText("MOSS").closest("aside")).toHaveClass("workbench-shell-rail");
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
  it("uses dedicated home routes for primary workspace group links", async () => {
    renderShellAt("/portfolio");

    expect(await screen.findByText("portfolio home body")).toBeInTheDocument();
    const navigation = screen.getByTestId("workbench-group-nav");
    const hrefs = within(navigation)
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));

    expect(hrefs).toEqual(
      expect.arrayContaining([
        "/",
        "/portfolio",
        "/market-overview",
        "/risk-overview",
        "/performance",
        "/reports",
      ]),
    );
    const groupBadges = Array.from(
      navigation.querySelectorAll(".workbench-shell-group-count"),
    ).map((badge) => badge.textContent);
    expect(groupBadges).toEqual(["首页", "首页", "首页", "首页", "首页", "首页"]);
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
  });
});
