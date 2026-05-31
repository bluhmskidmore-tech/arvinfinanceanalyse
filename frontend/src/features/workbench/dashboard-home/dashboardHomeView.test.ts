import { describe, expect, it } from "vitest";

import type { CoreMetricsResult, VerdictPayload } from "../../../api/contracts";
import { mapToHomeView, stripDisplayUnit } from "./dashboardHomeView";

const verdict: VerdictPayload = {
  conclusion: "test conclusion",
  tone: "warning",
  reasons: [{ label: "rates", value: "-1", detail: "rates moved higher", tone: "warning" }],
  suggestions: [{ text: "review duration", link: "/risk-tensor" }],
};

function numeric(raw: number, display: string, unit: "yuan" | "pct" | "bp" | "ratio" | "dv01" | "yi" = "yuan") {
  return {
    raw,
    unit,
    display,
    precision: 2,
    sign_aware: false,
  };
}

describe("stripDisplayUnit", () => {
  it("strips spaced display units", () => {
    expect(stripDisplayUnit("3,708.10 bp")).toEqual({ value: "3,708.10", unit: "bp" });
  });

  it("strips tight percent displays", () => {
    expect(stripDisplayUnit("1.76%")).toEqual({ value: "1.76", unit: "%" });
  });

  it("returns empty unit when no suffix", () => {
    expect(stripDisplayUnit("12,345")).toEqual({ value: "12,345", unit: "" });
  });
});

describe("mapToHomeView", () => {
  const baseRealInput = {
    reportDate: "2026-04-30",
    useMockFallback: false as const,
    verdict,
    metrics: [] as const,
    attribution: null,
    coreMetrics: null,
    dailyChanges: null,
    bondHeadline: null,
    portfolio: null,
    portfolioComparison: null,
    creditSpreadMigration: null,
    decisionItems: null,
    marketPoints: [] as const,
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
  };

  it("returns mock-shaped view when useMockFallback is true", () => {
    const view = mapToHomeView({
      ...baseRealInput,
      useMockFallback: true,
      marketPoints: null,
      alertCount: 3,
    });

    expect(view.useMockFallback).toBe(true);
    expect(view.coreKpis).toHaveLength(3);
    expect(view.marketTape.length).toBeGreaterThan(0);
    expect(view.decisionRail.maxDragLabel).toBeTruthy();
  });

  it("returns gap placeholders when real data is missing", () => {
    const view = mapToHomeView(baseRealInput);

    expect(view.useMockFallback).toBe(false);
    expect(view.coreKpis.every((kpi) => kpi.pending)).toBe(true);
    expect(view.marketTape).toHaveLength(0);
    expect(view.aiJudge.conclusion).toBe("test conclusion");
    expect(view.attributionTabs).toHaveLength(4);
    expect(view.assetBarsPlaceholder).toBe(true);
    expect(view.riskRadar.placeholder).toBe(true);
  });

  it("maps landed home backend blocks without keeping their backend-gap cards", () => {
    const view = mapToHomeView({
      ...baseRealInput,
      positionChanges: {
        report_date: "2026-04-30",
        prev_report_date: "2026-04-29",
        top_n: 5,
        source_status: "ready",
        total_market_value: numeric(1_000_000_000, "10.00 yi"),
        prev_total_market_value: numeric(900_000_000, "9.00 yi"),
        warnings: [],
        computed_at: "2026-04-30T10:00:00Z",
        items: [
          {
            instrument_code: "240001.IB",
            instrument_name: "test bond",
            issuer_name: null,
            rating: "AAA",
            asset_class: "rate",
            previous_market_value: numeric(100_000_000, "1.00 yi"),
            current_market_value: numeric(160_000_000, "1.60 yi"),
            change_market_value: numeric(60_000_000, "+0.60 yi"),
            previous_weight: numeric(0.1, "10.00%", "ratio"),
            current_weight: numeric(0.16, "16.00%", "ratio"),
            change_weight: numeric(0.06, "+6.00pp", "ratio"),
            direction: "increase",
            reason_label: "增持",
            source_status: "ready",
          },
        ],
      },
      researchReports: {
        report_date: "2026-04-30",
        source_status: "ready",
        warnings: [],
        items: [
          {
            id: "r1",
            title: "利率债周报",
            category: "fixed_income",
            published_at: "2026-04-29T09:00:00",
            link: "https://example.com/report.pdf",
            source: "tushare_research",
            source_status: "ready",
            summary: "关注久期和曲线",
          },
        ],
      },
      incomeTrend: {
        report_date: "2026-04-30",
        window: 2,
        source_status: "partial",
        missing_components: ["benchmark_pnl", "excess_pnl"],
        warnings: ["Benchmark and excess PnL are not available."],
        points: [
          {
            date: "2026-03-31",
            portfolio_pnl: numeric(120_000_000, "+1.20 yi"),
            benchmark_pnl: { ...numeric(0, "-"), raw: null },
            excess_pnl: { ...numeric(0, "-"), raw: null },
            basis: "product_category_pnl_monthly",
            source_status: "partial",
          },
          {
            date: "2026-04-30",
            portfolio_pnl: numeric(90_000_000, "+0.90 yi"),
            benchmark_pnl: { ...numeric(0, "-"), raw: null },
            excess_pnl: { ...numeric(0, "-"), raw: null },
            basis: "product_category_pnl_monthly",
            source_status: "partial",
          },
        ],
      },
    });

    expect(view.positionChanges[0]?.code).toBe("240001.IB");
    expect(view.researchReports[0]?.title).toBe("利率债周报");
    expect(view.incomeTrend[0]?.portfolioPnl).toBe("1.20 亿");
    expect(view.incomeTrendState.kind).toBe("partial");
    expect(view.backendGaps.some((gap) => gap.id === "position-changes")).toBe(false);
    expect(view.backendGaps.some((gap) => gap.id === "research-reports")).toBe(false);
    expect(view.backendGaps.some((gap) => gap.id === "income-trend")).toBe(false);
  });

  it("maps attribution waterfall extremes from segments", () => {
    const view = mapToHomeView({
      ...baseRealInput,
      attribution: {
        title: "attribution",
        total: numeric(-100, "-100 wan"),
        segments: [
          { id: "rate", label: "rate move", amount: numeric(-512.34, "-512.34 wan"), tone: "negative" },
          { id: "credit", label: "credit spread", amount: numeric(286.21, "+286.21 wan"), tone: "positive" },
        ],
      },
      alertCount: 1,
    });

    expect(view.attributionInsights.maxDragLabel).toBe("rate move");
    expect(view.attributionInsights.maxContributionLabel).toBe("credit spread");
  });

  it("computes interbank net from core metrics raw yuan fields", () => {
    const coreMetrics: CoreMetricsResult = {
      report_date: "2026-04-30",
      bond_investments: {
        total_amount: numeric(0, "0"),
        weighted_avg_rate: numeric(0, "0", "pct"),
        change_amount: numeric(0, "0"),
        change_pct: numeric(0, "0", "pct"),
        top_3_details: [],
      },
      interbank_assets: {
        total_amount: numeric(21_991_000_000, "219.91 yi"),
        weighted_avg_rate: numeric(0, "0", "pct"),
        change_amount: numeric(0, "0"),
        change_pct: numeric(0, "0", "pct"),
        top_3_details: [],
      },
      interbank_liabilities: {
        total_amount: numeric(67_907_000_000, "679.07 yi"),
        weighted_avg_rate: numeric(0, "0", "pct"),
        change_amount: numeric(0, "0"),
        change_pct: numeric(0, "0", "pct"),
        top_3_details: [],
      },
    };
    const view = mapToHomeView({ ...baseRealInput, coreMetrics });

    expect(view.interbank.net).toContain("-459.16");
    expect(view.interbank.netTone).toBe("up");
  });

  it("builds dv01 foot delta from bond headline prev_kpis", () => {
    const view = mapToHomeView({
      ...baseRealInput,
      bondHeadline: {
        report_date: "2026-04-30",
        prev_report_date: "2026-04-29",
        kpis: {
          total_market_value: numeric(1, "1 yi", "yi"),
          unrealized_pnl: numeric(0, "0", "yi"),
          weighted_ytm: numeric(3, "3%", "pct"),
          weighted_duration: numeric(4.15, "4.15", "ratio"),
          weighted_coupon: numeric(3, "3%", "pct"),
          credit_spread_median: numeric(50, "50bp", "bp"),
          total_dv01: numeric(10620.56, "10,620.56 wan", "dv01"),
          bond_count: 100,
        },
        prev_kpis: {
          total_market_value: numeric(1, "1 yi", "yi"),
          unrealized_pnl: numeric(0, "0", "yi"),
          weighted_ytm: numeric(3, "3%", "pct"),
          weighted_duration: numeric(4.14, "4.14", "ratio"),
          weighted_coupon: numeric(3, "3%", "pct"),
          credit_spread_median: numeric(50, "50bp", "bp"),
          total_dv01: numeric(10625.53, "10,625.53 wan", "dv01"),
          bond_count: 100,
        },
      },
    });

    const dv01Mini = view.riskMinis.find((mini) => mini.id === "dv01");
    expect(dv01Mini?.value).toBe("10,620.56 wan");
    expect(dv01Mini?.foot).toContain("-4.97");
    expect(dv01Mini?.footTone).toBe("down");
    expect(view.riskMinis.find((mini) => mini.id === "concentration")?.foot).toBe("—");
  });
});
