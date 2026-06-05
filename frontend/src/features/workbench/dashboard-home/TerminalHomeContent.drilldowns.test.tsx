import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { mapToHomeBodyView, type MapToHomeBodyViewInput } from "./dashboardHomeBodyView";
import { TerminalHomeContent } from "./TerminalHomeContent";

function buildView(reportDate = "2026-04-30") {
  return mapToHomeBodyView({
    reportDate,
    useMockFallback: false,
    attribution: null,
    creditSpreadMigration: null,
    returnDecomposition: null,
    campisiFourEffects: null,
    yieldCurveTermStructure: null,
    marketPoints: [],
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
    calendarEvents: null,
    calendarLoading: false,
    calendarError: false,
    calendarStartDate: "2026-04-23",
    calendarEndDate: "2026-05-14",
    macroNewsEvents: null,
    macroNewsFallbackEvents: null,
    macroNewsLoading: false,
    macroNewsError: false,
  } satisfies MapToHomeBodyViewInput);
}

describe("TerminalHomeContent drilldowns", () => {
  it("exposes evidence links with the active report date", async () => {
    render(
      <MemoryRouter>
        <TerminalHomeContent view={buildView()} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("link", { name: /归因明细/ })).toHaveAttribute(
      "href",
      "/pnl-attribution?report_date=2026-04-30",
    );
    expect(screen.getByRole("link", { name: /曲线\/利差/ })).toHaveAttribute(
      "href",
      "/bond-analysis?report_date=2026-04-30",
    );
  });

  it("does not pass placeholder report dates into evidence links", async () => {
    render(
      <MemoryRouter>
        <TerminalHomeContent view={buildView("—")} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("link", { name: /归因明细/ })).toHaveAttribute("href", "/pnl-attribution");
    expect(screen.getByRole("link", { name: /曲线\/利差/ })).toHaveAttribute("href", "/bond-analysis");
  });
});
