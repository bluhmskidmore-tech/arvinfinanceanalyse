import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CampisiFourEffectsPayload, CampisiTreasuryCurveDateCoverage } from "../../../api/contracts";
import { mockCampisiFourEffectsModelPath } from "../../../mocks/campisiMocks";
import { buildHomeMarketContextModel } from "../../workbench/dashboard-home/adapters/buildHomeMarketContextModel";
import { CampisiAttributionPanel } from "./CampisiAttributionPanel";

vi.mock("../../../lib/echarts", () => ({
  default: () => <div data-testid="campisi-curve-date-chart" />,
}));

function payload(curve?: CampisiTreasuryCurveDateCoverage): CampisiFourEffectsPayload {
  return {
    ...mockCampisiFourEffectsModelPath,
    report_date: "2026-08-31",
    period_start: "2026-08-01",
    period_end: "2026-08-31",
    effect_availability: {
      bonds: 1,
      position_change: {
        status: "ok", reason: null, unavailable_bonds: 0,
        covered_bonds: 1, unavailable_market_value_start: 0,
      },
      treasury_effect: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
      spread_effect: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
      accrued_interest: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
    },
    ...(curve ? { input_quality: { market_curve_coverage: { treasury_effect: curve } } } : {}),
  };
}

function home(data: CampisiFourEffectsPayload, expectedReportDate = "2026-08-31") {
  return buildHomeMarketContextModel({
    marketTape: [], marketPoints: null, macroNewsEvents: null,
    todayIsoDate: expectedReportDate, expectedReportDate,
    campisiFourEffects: data,
    returnDecomposition: null, yieldCurveTermStructure: null,
    creditSpreadMigration: null,
    attribution: { maxDragLabel: "", maxContributionLabel: "" },
  }).attributionCoverage;
}

function detail(data: CampisiFourEffectsPayload) {
  render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);
}

describe("Campisi treasury curve observation dates", () => {
  it("discloses adopted July 31 and August 31 curves beside the unchanged holding window", () => {
    const data = payload({
      start_requested_date: "2026-08-01", start_resolved_date: "2026-07-31", start_curve_used: true,
      end_requested_date: "2026-08-31", end_resolved_date: "2026-08-31", end_curve_used: true,
    });
    const coverage = home(data);
    expect(coverage.state).toBe("complete");
    expect(coverage.periodLabel).toBe("归因区间 2026-08-01 至 2026-08-31");
    expect(coverage.effectNotices).toContain(
      "持仓归因区间 2026-08-01 至 2026-08-31；国债曲线实际观测日 2026-07-31 至 2026-08-31。",
    );
    expect(coverage.detailPath).toContain("campisi_start_date=2026-08-01");
    expect(coverage.detailPath).toContain("campisi_end_date=2026-08-31");

    detail(data);
    expect(screen.getByTestId("campisi-treasury-curve-dates")).toHaveTextContent(
      "持仓归因区间 2026-08-01 至 2026-08-31；国债曲线实际观测日 2026-07-31 至 2026-08-31。",
    );
  });

  it("shows a resolved but unadopted curve without calling it an observation", () => {
    const data = payload({
      start_requested_date: "2026-08-01", start_resolved_date: "2026-07-20", start_curve_used: false,
      end_requested_date: "2026-08-31", end_resolved_date: "2026-08-31", end_curve_used: true,
    });
    const coverage = home(data);
    expect(coverage.effectNotices.join(" ")).toContain("2026-07-20，未采用");
    expect(coverage.effectNotices.join(" ")).not.toContain("实际观测日 2026-07-20");

    detail(data);
    const notice = screen.getByTestId("campisi-treasury-curve-dates");
    expect(notice).toHaveTextContent("2026-07-20，未采用");
    expect(notice).not.toHaveTextContent("实际观测日 2026-07-20");
    expect(notice).not.toHaveTextContent("超期");
  });

  it("keeps old payloads without curve date fields compatible", () => {
    const data = payload();
    expect(home(data).effectNotices).toEqual([]);
    detail(data);
    expect(screen.queryByTestId("campisi-treasury-curve-dates")).not.toBeInTheDocument();
  });

  it("ignores an old strict HTTP payload whose optional curve dates and usage flags are all null", () => {
    const data = payload({
      start_requested_date: null, start_resolved_date: null, start_curve_used: null,
      end_requested_date: null, end_resolved_date: null, end_curve_used: null,
    });
    expect(home(data).effectNotices).toEqual([]);
    detail(data);
    expect(screen.queryByTestId("campisi-treasury-curve-dates")).not.toBeInTheDocument();
  });

  it("uses a short notice when both curves are observed on the requested dates", () => {
    const data = payload({
      start_requested_date: "2026-08-01", start_resolved_date: "2026-08-01", start_curve_used: true,
      end_requested_date: "2026-08-31", end_resolved_date: "2026-08-31", end_curve_used: true,
    });
    expect(home(data).effectNotices).toContain("国债曲线实际观测日 2026-08-01 至 2026-08-31。");
  });

  it("does not publish another report date's curve dates or a drill-down link", () => {
    const data = payload({
      start_requested_date: "2026-08-01", start_resolved_date: "2026-07-31", start_curve_used: true,
      end_requested_date: "2026-08-31", end_resolved_date: "2026-08-31", end_curve_used: true,
    });
    const coverage = home(data, "2026-09-01");
    expect(coverage.state).toBe("date-mismatch");
    expect(coverage.effectNotices).toEqual([]);
    expect(coverage.detailPath).toBeNull();
  });
});
