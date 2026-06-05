import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { mapToHomeBodyView, type MapToHomeBodyViewInput } from "./dashboardHomeBodyView";
import { TerminalHomeContent } from "./TerminalHomeContent";

describe("TerminalHomeContent research reports", () => {
  it("renders featured report plus compact rows", async () => {
    const view = mapToHomeBodyView({
      reportDate: "2026-04-30",
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
      researchReports: {
        report_date: "2026-04-30",
        source_status: "stale",
        warnings: [],
        items: [
          {
            id: "research-1",
            title: "6月利率债周报：曲线偏陡",
            category: "fixed_income",
            published_at: "2026-06-01T09:00:00+00:00",
            link: "https://example.com/june-research.pdf",
            source: "tushare_research",
            source_status: "ready",
            summary: "关注曲线陡峭化与政金债供给节奏。",
            institution: "中信固收",
          },
          {
            id: "research-2",
            title: "信用债策略周报",
            category: "信用债",
            published_at: "2026-05-31T09:00:00+00:00",
            link: "https://example.com/credit.pdf",
            source: "tushare_research",
            source_status: "ready",
            summary: "利差走阔",
            institution: "华泰固收",
          },
        ],
      },
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

    render(
      <MemoryRouter>
        <TerminalHomeContent view={view} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "券商研报" })).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-home-research-featured")).toHaveTextContent("6月利率债周报");
    expect(screen.getByTestId("dashboard-home-research-featured")).toHaveTextContent("中信固收");
    expect(screen.getByTestId("dashboard-home-research-featured")).toHaveTextContent("关注曲线陡峭化");
    expect(screen.getAllByTestId("dashboard-home-research-row")).toHaveLength(1);
    expect(screen.getByTestId("dashboard-home-research-row")).toHaveTextContent("信用债策略周报");
  });
});
