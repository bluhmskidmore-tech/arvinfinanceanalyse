import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { VerdictPayload } from "../../../api/contracts";
import { mapToHomeView } from "./dashboardHomeView";
import { TerminalHomeContent } from "./TerminalHomeContent";

const verdict: VerdictPayload = {
  conclusion: "test conclusion",
  tone: "warning",
  reasons: [{ label: "rates", value: "-1", detail: "rates moved higher", tone: "warning" }],
  suggestions: [{ text: "review duration", link: "/risk-tensor" }],
};

function buildView(reportDate = "2026-04-30") {
  return mapToHomeView({
    reportDate,
    useMockFallback: false,
    verdict,
    metrics: [],
    attribution: null,
    coreMetrics: null,
    dailyChanges: null,
    bondHeadline: null,
    portfolio: null,
    portfolioComparison: null,
    creditSpreadMigration: null,
    returnDecomposition: null,
    campisiFourEffects: null,
    yieldCurveTermStructure: null,
    decisionItems: null,
    marketPoints: [],
    productCategoryYtd: null,
    productCategoryMonthly: null,
    assetStructure: null,
    ratingStructure: null,
    maturityStructure: null,
    industryDistribution: null,
    riskIndicators: null,
    topHoldings: null,
    topHoldingsLoading: false,
    topHoldingsError: false,
    positionChanges: null,
    positionChangesLoading: false,
    positionChangesError: false,
    researchReports: null,
    researchReportsLoading: false,
    researchReportsError: false,
    incomeTrend: null,
    incomeTrendLoading: false,
    incomeTrendError: false,
    cockpitWarnings: null,
    calendarEvents: null,
    calendarLoading: false,
    calendarError: false,
    calendarStartDate: "2026-04-23",
    calendarEndDate: "2026-05-14",
    snapshotMeta: null,
    marketMeta: null,
    alertCount: 0,
    snapshotUnavailable: false,
    snapshotStale: false,
    macroNewsEvents: null,
    macroNewsFallbackEvents: null,
    macroNewsLoading: false,
    macroNewsError: false,
  });
}

describe("TerminalHomeContent drilldowns", () => {
  it("exposes evidence links with the active report date", () => {
    render(
      <MemoryRouter>
        <TerminalHomeContent view={buildView()} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: /归因明细/ })).toHaveAttribute(
      "href",
      "/pnl-attribution?report_date=2026-04-30",
    );
    expect(screen.getByRole("link", { name: /曲线\/利差/ })).toHaveAttribute(
      "href",
      "/bond-analysis?report_date=2026-04-30",
    );
  });

  it("does not pass placeholder report dates into evidence links", () => {
    render(
      <MemoryRouter>
        <TerminalHomeContent view={buildView("—")} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: /归因明细/ })).toHaveAttribute("href", "/pnl-attribution");
    expect(screen.getByRole("link", { name: /曲线\/利差/ })).toHaveAttribute("href", "/bond-analysis");
  });
});
