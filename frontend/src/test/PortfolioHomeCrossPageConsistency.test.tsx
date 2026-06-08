import { cleanup, screen, waitFor, within } from "@testing-library/react";
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

beforeAll(async () => {
  await preloadWorkbenchRouteModules("module-home");
}, 20_000);

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

    const briefing = within(page).getByTestId("module-home-briefing");
    expect(briefing).toHaveTextContent("\u7ec4\u5408");
    expect(briefing).toHaveTextContent("\u7ec4\u5408\u6458\u8981");
    expect(briefing).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.bondMarketValueYi);
    expect(briefing).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.balanceAssetYi);
    expect(briefing).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.balanceLiabilityYi);
    expect(briefing).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.pnlDriverRatio);

    const structureTerminal = within(page).getByTestId("module-home-portfolio-terminal");
    expect(structureTerminal).toHaveTextContent("\u7ed3\u6784");
    expect(structureTerminal).toHaveTextContent("\u7ed3\u6784\u62c6\u89e3");
    expect(structureTerminal).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.portfolioName);

    const riskPanel = within(page).getByTestId("module-home-portfolio-risk");
    expect(riskPanel).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.bondDv01Wan);

    const pnlPanel = within(page).getByTestId("module-home-pnl-summary");
    expect(pnlPanel).toHaveTextContent("primary_driver");
    expect(pnlPanel).toHaveTextContent(PORTFOLIO_CROSS_PAGE_EXPECTED.pnlFinding);

    const dataNote = within(page).getByTestId("module-home-data-note");
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
});
