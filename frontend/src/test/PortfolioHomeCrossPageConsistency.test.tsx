import { cleanup, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { ReactNode } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import {
  PORTFOLIO_CROSS_PAGE_EXPECTED,
  PORTFOLIO_CROSS_PAGE_REPORT_DATE,
  portfolioCrossPageBalanceBasis,
  portfolioCrossPageBalanceOverview,
  portfolioCrossPageBondHomeSummary,
  portfolioCrossPageEnvelope,
  portfolioCrossPagePnlSummary,
} from "./portfolioCrossPageGoldenSample";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

const ROUTE_RENDER_TIMEOUT_MS = 20_000;
const FALSE_CLOSURE_TERMS = [
  "closure_approved=true",
  "\u5df2\u5ba1\u6279",
  "decision-ready",
  "full closure",
] as const;
const STRICT_SCORECARD_BLOCKERS = [
  "risk_tensor_quality_warning",
  "krd_contract_decision_required",
  "bond_maturity_date_remediation_required",
  "tyw_liability_maturity_date_remediation_required",
  "business_owner_approval",
] as const;
const AI_FLAVOR_TERMS = [
  "Decision Ledger",
  "Exposure Matrix",
  "Evidence Gate",
  "Action Queue",
  "Business use",
  "Candidate only",
  "Monitor only",
  "Blocked",
  "Review required",
  "core readout",
  "source / date / closure",
  "Portfolio Brief",
  "Core Metrics",
  "Read Path",
  "Holdings",
  "Risk & PnL",
  "Drilldown",
  "result_meta",
  "basis=analytical",
  "formal_use_allowed=false",
  "quality=warning",
  "report_date 缺失",
] as const;

vi.mock("../lib/echarts", () => ({
  default: ({ style }: { style?: { height?: number | string } }) => (
    <div data-testid="module-home-echarts-stub" data-chart-height={String(style?.height ?? "")} />
  ),
}));

vi.mock("../app/ThemedRouteBoundary", () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

// /portfolio 路由渲染的是 PortfolioHomePage（含 PortfolioHomeLayout 与
// usePortfolioHomeQueries 的静态链），不是 ModuleWorkbenchHomePage。这条链的
// 最大单体是 PortfolioHomeLayout 引入的 antd barrel（vitest 下会整体求值）。
// 多文件组合冷启动时 4 个 worker 并发抢 transform/求值，单个 30s hook 可能
// 不够，所以在模块 collection 阶段就发起预热（不 await），两个 beforeAll 按
// 序等待完成，各自保持 30s 超时上限。
const antdBarrelWarmup = import("antd");
const portfolioHomeWarmup = antdBarrelWarmup.then(() =>
  preloadWorkbenchRouteModules("portfolio-home"),
);

beforeAll(async () => {
  await antdBarrelWarmup;
}, 30_000);

beforeAll(async () => {
  await portfolioHomeWarmup;
}, 30_000);

afterEach(() => {
  cleanup();
});

function portfolioClient(): ApiClient {
  const base = createApiClient({ mode: "mock" });
  const bond = portfolioCrossPageBondHomeSummary();
  return {
    ...base,
    mode: "real",
    getBalanceAnalysisDates: async () =>
      portfolioCrossPageEnvelope("balance-analysis.dates", {
        report_dates: [PORTFOLIO_CROSS_PAGE_REPORT_DATE],
      }),
    getBalanceAnalysisOverview: async () =>
      portfolioCrossPageEnvelope("balance-analysis.overview", portfolioCrossPageBalanceOverview(), {
        tables_used: ["fact_formal_zqtz_balance_daily"],
        evidence_rows: 908,
      }),
    getBalanceAnalysisSummaryByBasis: async () =>
      portfolioCrossPageEnvelope("balance-analysis.summary-by-basis", portfolioCrossPageBalanceBasis(), {
        tables_used: ["fact_formal_zqtz_balance_daily"],
        evidence_rows: 908,
      }),
    getBondDashboardDates: async () =>
      portfolioCrossPageEnvelope("bond_dashboard.dates", {
        report_dates: [PORTFOLIO_CROSS_PAGE_REPORT_DATE],
      }),
    getBondDashboardHomeSummary: async () => ({
      ...portfolioCrossPageEnvelope("bond_dashboard.home_summary", bond, {
        tables_used: ["fact_formal_bond_analytics_daily"],
        evidence_rows: 908,
      }),
      data_source: "bond_analytics_facts",
    }),
    getBondDashboardRiskIndicators: async () =>
      portfolioCrossPageEnvelope("bond_dashboard.risk_indicators", bond.risk, {
        tables_used: ["fact_formal_bond_analytics_daily"],
        evidence_rows: 908,
      }),
    getPnlAttributionAnalysisSummary: async () =>
      portfolioCrossPageEnvelope("pnl-attribution.summary", portfolioCrossPagePnlSummary(), {
        tables_used: ["fact_formal_pnl_fi"],
        evidence_rows: 908,
      }),
    getRiskTensorDates: async () =>
      portfolioCrossPageEnvelope(
        "risk.tensor.dates",
        {
          report_dates: [PORTFOLIO_CROSS_PAGE_REPORT_DATE],
        },
        {
          tables_used: ["fact_risk_tensor_daily"],
          evidence_rows: 1,
        },
      ),
  };
}

function renderPortfolio(client: ApiClient) {
  return renderWorkbenchApp(["/portfolio"], { client });
}

describe("Portfolio home cross-page consistency", () => {
  it("defines every portfolio layout CSS hook used by the page component", () => {
    const component = readFileSync(
      resolve(process.cwd(), "src/features/workbench/module-home/PortfolioHomeLayout.tsx"),
      "utf8",
    );
    const css = readFileSync(
      resolve(process.cwd(), "src/features/workbench/module-home/portfolioHome.module.css"),
      "utf8",
    );

    const referencedSelectors = Array.from(component.matchAll(/styles\.([A-Za-z0-9_]+)/g))
      .map((match) => match[1])
      .filter((selector, index, selectors) => selectors.indexOf(selector) === index);

    const missingSelectors = referencedSelectors.filter(
      (selector) => !new RegExp(`\\.${selector}(?=[\\s\\{\\.#,:>\\[])`).test(css),
    );

    expect(missingSelectors).toEqual([]);
  });

  it("uses one report date across portfolio source pages and keeps risk closure date-only", async () => {
    const base = portfolioClient();
    const getBalanceAnalysisOverview = vi.fn<ApiClient["getBalanceAnalysisOverview"]>((options) =>
      base.getBalanceAnalysisOverview(options),
    );
    const getBalanceAnalysisSummaryByBasis = vi.fn<ApiClient["getBalanceAnalysisSummaryByBasis"]>((options) =>
      base.getBalanceAnalysisSummaryByBasis(options),
    );
    const getBondDashboardHomeSummary = vi.fn<ApiClient["getBondDashboardHomeSummary"]>((reportDate) =>
      base.getBondDashboardHomeSummary(reportDate),
    );
    const getBondDashboardRiskIndicators = vi.fn<ApiClient["getBondDashboardRiskIndicators"]>((reportDate) =>
      base.getBondDashboardRiskIndicators(reportDate),
    );
    const getPnlAttributionAnalysisSummary = vi.fn<ApiClient["getPnlAttributionAnalysisSummary"]>((reportDate) =>
      base.getPnlAttributionAnalysisSummary(reportDate),
    );
    const getRiskTensorDates = vi.fn<ApiClient["getRiskTensorDates"]>(() => base.getRiskTensorDates());
    const getRiskTensor = vi.fn<ApiClient["getRiskTensor"]>((reportDate) => base.getRiskTensor(reportDate));

    renderPortfolio({
      ...base,
      getBalanceAnalysisOverview,
      getBalanceAnalysisSummaryByBasis,
      getBondDashboardHomeSummary,
      getBondDashboardRiskIndicators,
      getPnlAttributionAnalysisSummary,
      getRiskTensorDates,
      getRiskTensor,
    });

    const page = await screen.findByTestId("module-workbench-home", {}, { timeout: ROUTE_RENDER_TIMEOUT_MS });
    const decision = await within(page).findByTestId("module-home-decision");
    await waitFor(() => {
      expect(getBalanceAnalysisOverview).toHaveBeenCalledWith({
        reportDate: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
        positionScope: "all",
        currencyBasis: "CNY",
      });
      expect(getBondDashboardHomeSummary).toHaveBeenCalledWith(PORTFOLIO_CROSS_PAGE_REPORT_DATE);
      expect(getBondDashboardRiskIndicators).toHaveBeenCalledWith(PORTFOLIO_CROSS_PAGE_REPORT_DATE);
      expect(getPnlAttributionAnalysisSummary).toHaveBeenCalledWith(PORTFOLIO_CROSS_PAGE_REPORT_DATE);
      expect(getRiskTensorDates).toHaveBeenCalledTimes(1);
      expect(decision).toHaveTextContent(`\u540c\u65e5\u95ed\u5408 ${PORTFOLIO_CROSS_PAGE_REPORT_DATE}`);
    });
    expect(getBalanceAnalysisSummaryByBasis).toHaveBeenCalledWith({
      reportDate: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
      positionScope: "all",
      currencyBasis: "CNY",
    });
    expect(getRiskTensor).not.toHaveBeenCalled();
  });

  it("renders portfolio headline values from the shared source-page golden sample", async () => {
    renderPortfolio(portfolioClient());

    const page = await screen.findByTestId("module-workbench-home", {}, { timeout: ROUTE_RENDER_TIMEOUT_MS });
    const kpis = within(page).getByTestId("module-home-kpi-strip");
    const decision = await within(page).findByTestId("module-home-decision");
    const exposureMatrix = within(page).getByTestId("module-home-exposure-matrix");
    const evidenceConsole = within(page).getByTestId("module-home-evidence-console");
    await waitFor(() => {
      expect(kpis).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.bondMarketValueYi);
      expect(kpis).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.balanceAssetYi);
      expect(kpis).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.balanceLiabilityYi);
      expect(kpis).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.bondDuration);
      expect(kpis).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.bondDv01Wan);
      expect(kpis).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.bondCount);
      expect(decision).toHaveTextContent(`\u540c\u65e5\u95ed\u5408 ${PORTFOLIO_CROSS_PAGE_REPORT_DATE}`);
      expect(decision).toHaveTextContent("\u7ec4\u5408\u590d\u6838");
      expect(decision).toHaveTextContent("\u4e1a\u52a1\u53ef\u7528");
      expect(exposureMatrix).toHaveTextContent("\u98ce\u9669\u66b4\u9732");
      expect(exposureMatrix).toHaveTextContent("\u6838\u5fc3\u8bfb\u6570");
      expect(exposureMatrix).toHaveTextContent(`4 \u4e2a\u6765\u6e90 / ${PORTFOLIO_CROSS_PAGE_REPORT_DATE}`);
      expect(evidenceConsole).toHaveTextContent("\u8bc1\u636e\u53e3\u5f84");
      expect(evidenceConsole).toHaveTextContent("\u6765\u6e90 / \u65e5\u671f / \u95ed\u5408");
      expect(evidenceConsole).toHaveTextContent("\u5f85\u590d\u6838");
    });
    const useLevel = within(decision).getByTestId("module-home-decision-use-level");
    expect(useLevel.textContent).toMatch(
      /\u4ec5\u4f9b\u5206\u6790|\u4ec5\u4f9b\u76d1\u63a7|\u4e0d\u53ef\u7528\u4e8e\u4e1a\u52a1\u51b3\u7b56|\u5f85\u590d\u6838/,
    );
    expect(useLevel).not.toHaveTextContent(/Approved|Full closure/i);
    const kpiScopeNote = within(kpis).getByTestId("module-home-portfolio-kpi-scope-note");
    expect(kpiScopeNote).toHaveTextContent("债券总览");
    const bondMarketDetail = within(kpis).getByTestId("module-home-portfolio-kpi-bond-market-detail");
    expect(bondMarketDetail.textContent?.length ?? 0).toBeLessThan(72);
    expect(bondMarketDetail).toHaveAttribute("title", expect.stringContaining("债券总览口径"));

    const briefing = within(page).getByTestId("module-home-briefing");
    expect(briefing).toHaveTextContent("\u7ec4\u5408");
    expect(briefing).toHaveTextContent("\u7ec4\u5408\u6458\u8981");
    expect(briefing).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.bondMarketValueYi);
    expect(briefing).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.balanceAssetYi);
    expect(briefing).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.balanceLiabilityYi);
    expect(briefing).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.pnlDriverRatio);

    const dataWorkbench = within(page).getByTestId("module-home-portfolio-data-workbench");
    const sourceWorkbench = within(dataWorkbench).getByTestId("module-home-portfolio-source-workbench");
    expect(within(sourceWorkbench).getByTestId("module-home-holdings-structure")).toBeInTheDocument();
    expect(sourceWorkbench).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.ratingName);
    expect(sourceWorkbench).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.maturityName);
    expect(sourceWorkbench).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.industryName);
    expect(within(sourceWorkbench).getByTestId("module-home-briefing")).toBe(briefing);
    expect(within(sourceWorkbench).getByTestId("module-home-status-strip")).toBeInTheDocument();
    expect(within(dataWorkbench).getByTestId("module-home-portfolio-data-nav")).toBeInTheDocument();

    const holdingsWorkbench = within(dataWorkbench).getByTestId("module-home-portfolio-holdings-workbench");
    expect(within(holdingsWorkbench).getByTestId("module-home-portfolio-holdings-hero")).toBeInTheDocument();
    expect(within(holdingsWorkbench).getByTestId("module-home-portfolio-exposure-workbench")).toHaveTextContent(
      PORTFOLIO_CROSS_PAGE_EXPECTED.bondDv01Wan,
    );

    const structureWorkbench = within(dataWorkbench).getByTestId("module-home-portfolio-structure-workbench");
    const structureTerminal = within(structureWorkbench).getByTestId("module-home-portfolio-terminal");
    expect(structureWorkbench).toHaveTextContent("\u7ed3\u6784");
    expect(structureTerminal).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.portfolioName);
    expect(structureTerminal).toHaveTextContent("banking-book");
    expect(within(structureTerminal).getByTestId("module-home-analysis-tab-portfolio-comparison")).toHaveTextContent("4");
    expect(within(structureTerminal).getByTestId("module-home-analysis-tab-yield-distribution")).toHaveTextContent("6");
    expect(within(structureTerminal).getByTestId("module-home-analysis-tab-spread-analysis")).toHaveTextContent("4");
    expect(within(structureTerminal).getByTestId("module-home-analysis-tab-business-type-metrics")).toHaveTextContent("4");
    expect(within(dataWorkbench).getByTestId("module-home-portfolio-closure-band")).toBeInTheDocument();
    expect(within(dataWorkbench).getByTestId("module-home-portfolio-action-workbench")).toBeInTheDocument();

    const riskPanel = within(page).getByTestId("module-home-portfolio-risk");
    expect(riskPanel).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.bondDv01Wan);

    const pnlPanel = within(page).getByTestId("module-home-pnl-summary");
    expect(pnlPanel).toHaveTextContent("primary_driver");
    expect(pnlPanel).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.pnlFinding);

    const basisPanel = within(page).getByTestId("module-home-balance-basis");
    expect(basisPanel).toHaveTextContent("FVOCI");
    expect(basisPanel).toHaveTextContent("FVTPL");

    const dataNote = within(page).getByTestId("module-home-data-note");
    expect(dataNote.tagName.toLowerCase()).toBe("details");
    expect(dataNote.querySelector("summary")).toHaveTextContent("来源证据摘要");
    expect(dataNote.querySelector("summary")).toHaveTextContent(`日期 ${PORTFOLIO_CROSS_PAGE_REPORT_DATE}`);
    expect(dataNote).toHaveTextContent(`report_date=${PORTFOLIO_CROSS_PAGE_REPORT_DATE}`);
    expect(dataNote).toHaveTextContent("fact_formal_bond_analytics_daily");
    expect(dataNote).toHaveTextContent("fact_formal_zqtz_balance_daily");
    expect(dataNote).toHaveTextContent("fact_formal_pnl_fi");

    const firstScreenText = [
      decision.textContent ?? "",
      exposureMatrix.textContent ?? "",
      evidenceConsole.textContent ?? "",
      briefing.textContent ?? "",
      kpis.textContent ?? "",
      structureTerminal.textContent ?? "",
      riskPanel.textContent ?? "",
      pnlPanel.textContent ?? "",
      dataNote.textContent ?? "",
    ].join(" ");
    for (const term of AI_FLAVOR_TERMS) {
      expect(firstScreenText).not.toContain(term);
    }

    for (const blocker of STRICT_SCORECARD_BLOCKERS) {
      expect(firstScreenText).not.toContain(blocker);
    }
    for (const term of FALSE_CLOSURE_TERMS) {
      expect(firstScreenText).not.toContain(term);
    }
  });

  it("keeps decision evidence before portfolio metrics and renders no undefined CSS classes", async () => {
    renderPortfolio(portfolioClient());

    const page = await screen.findByTestId("module-workbench-home", {}, { timeout: ROUTE_RENDER_TIMEOUT_MS });
    const firstScreen = within(page).getByTestId("module-home-portfolio-first-screen");

    await within(firstScreen).findByTestId("module-home-decision");

    const orderedFirstScreenSections = Array.from(
      firstScreen.querySelectorAll(
        [
          '[data-testid="module-home-decision"]',
          '[data-testid="module-home-kpi-strip"]',
          '[data-testid="module-home-portfolio-risk-ticker"]',
        ].join(", "),
      ),
    ).map((node) => node.getAttribute("data-testid"));

    expect(orderedFirstScreenSections).toEqual([
      "module-home-decision",
      "module-home-kpi-strip",
      "module-home-portfolio-risk-ticker",
    ]);
    expect(within(firstScreen).queryByTestId("module-home-portfolio-holdings-hero")).not.toBeInTheDocument();

    const dataWorkbench = within(page).getByTestId("module-home-portfolio-data-workbench");
    const orderedWorkbenchSections = Array.from(
      dataWorkbench.querySelectorAll(
        [
          '[data-testid="module-home-portfolio-source-workbench"]',
          '[data-testid="module-home-portfolio-data-nav"]',
          '[data-testid="module-home-portfolio-holdings-workbench"]',
          '[data-testid="module-home-portfolio-structure-workbench"]',
          '[data-testid="module-home-portfolio-closure-band"]',
          '[data-testid="module-home-portfolio-action-workbench"]',
        ].join(", "),
      ),
    ).map((node) => node.getAttribute("data-testid"));

    expect(orderedWorkbenchSections).toEqual([
      "module-home-portfolio-data-nav",
      "module-home-portfolio-holdings-workbench",
      "module-home-portfolio-structure-workbench",
      "module-home-portfolio-closure-band",
      "module-home-portfolio-source-workbench",
      "module-home-portfolio-action-workbench",
    ]);
    expect(within(dataWorkbench).getByTestId("module-home-portfolio-holdings-hero")).toBeInTheDocument();

    const undefinedClassNodes = Array.from(page.querySelectorAll("[class]"))
      .filter((node) => (node.getAttribute("class") ?? "").includes("undefined"))
      .map((node) => node.getAttribute("data-testid") ?? node.tagName.toLowerCase());

    expect(undefinedClassNodes).toEqual([]);
  });
});
