import { describe, expect, it } from "vitest";

import type {
  BondDashboardHeadlinePayload,
  BondPortfolioHeadlinesPayload,
  ChoiceMacroLatestPoint,
  CoreMetricsResult,
  DailyChangesResult,
  Numeric,
} from "../../../api/contracts";
import {
  buildDashboardCockpitModel,
  type DashboardCockpitSectionStatus,
} from "./dashboardCockpitModel";

function numeric(display: string, raw = 1): Numeric {
  return {
    raw,
    unit: "ratio",
    display,
    precision: 2,
    sign_aware: false,
  };
}

function macroPoint(partial: Partial<ChoiceMacroLatestPoint>): ChoiceMacroLatestPoint {
  return {
    series_id: partial.series_id ?? "CA.DR007",
    series_name: partial.series_name ?? "DR007",
    trade_date: partial.trade_date ?? "2026-04-30",
    value_numeric: partial.value_numeric ?? 1.39,
    unit: partial.unit ?? "%",
    source_version: partial.source_version ?? "sv_macro",
    vendor_version: partial.vendor_version ?? "vv_macro",
    quality_flag: partial.quality_flag ?? "ok",
    latest_change: partial.latest_change ?? 0.01,
    recent_points: partial.recent_points ?? [],
    refresh_tier: partial.refresh_tier ?? "stable",
  };
}

function coreMetrics(reportDate = "2026-04-30"): CoreMetricsResult {
  const card = {
    total_amount: numeric("3,438.23 亿"),
    weighted_avg_rate: numeric("2.02%"),
    change_amount: numeric("+32.10 亿"),
    change_pct: numeric("+0.92%"),
    top_3_details: [],
  };
  return {
    report_date: reportDate,
    bond_investments: card,
    interbank_assets: { ...card, total_amount: numeric("219.91 亿") },
    interbank_liabilities: { ...card, total_amount: numeric("139.83 亿") },
  };
}

function dailyChanges(reportDate = "2026-04-30"): DailyChangesResult {
  return {
    report_date: reportDate,
    periods: [
      {
        period: "day",
        bond_investments_change: numeric("+3.21 亿"),
        interbank_assets_change: numeric("-1.08 亿", -1),
        interbank_liabilities_change: numeric("+0.82 亿"),
        net_change: numeric("+2.95 亿"),
      },
    ],
  };
}

function bondHeadline(reportDate = "2026-04-30"): BondDashboardHeadlinePayload {
  return {
    report_date: reportDate,
    prev_report_date: "2026-03-31",
    kpis: {
      total_market_value: numeric("3,438.23 亿"),
      unrealized_pnl: numeric("+80.13 亿"),
      weighted_ytm: numeric("2.57%"),
      weighted_duration: numeric("4.14"),
      weighted_coupon: numeric("2.04%"),
      credit_spread_median: numeric("239bp"),
      total_dv01: numeric("106,155,944"),
      bond_count: 1740,
    },
    prev_kpis: null,
  };
}

function portfolio(reportDate = "2026-04-30"): BondPortfolioHeadlinesPayload {
  return {
    report_date: reportDate,
    total_market_value: numeric("3,438.23 亿"),
    weighted_ytm: numeric("2.57%"),
    weighted_duration: numeric("4.14"),
    weighted_coupon: numeric("2.07%"),
    total_dv01: numeric("106,155,944"),
    bond_count: 1740,
    credit_weight: numeric("29.25%"),
    issuer_hhi: numeric("5.09%"),
    issuer_top5_weight: numeric("41.35%"),
    by_asset_class: [
      {
        asset_class: "rate",
        market_value: numeric("1,344.90 亿"),
        duration: numeric("5.63"),
        dv01: numeric("73,667,216"),
        weight: numeric("39.12%"),
      },
      {
        asset_class: "credit",
        market_value: numeric("1,005.70 亿"),
        duration: numeric("2.40"),
        dv01: numeric("23,572,093"),
        weight: numeric("29.25%"),
      },
    ],
    warnings: [],
    computed_at: "2026-05-10T00:00:00Z",
  };
}

function statusById(
  sections: ReturnType<typeof buildDashboardCockpitModel>["sections"],
  id: string,
): DashboardCockpitSectionStatus | undefined {
  return sections.find((section) => section.id === id)?.status;
}

describe("buildDashboardCockpitModel", () => {
  it("allows same-report supplemental data onto the first screen", () => {
    const model = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      snapshotMode: "strict",
      isMockMode: false,
      coreMetrics: coreMetrics(),
      dailyChanges: dailyChanges(),
      bondHeadline: bondHeadline(),
      portfolio: portfolio(),
      marketPoints: [macroPoint({ series_id: "CA.DR007", series_name: "DR007" })],
      calendarItems: [],
    });

    expect(statusById(model.sections, "core_metrics")).toBe("supplemental");
    expect(statusById(model.sections, "daily_changes")).toBe("supplemental");
    expect(statusById(model.sections, "bond_headline")).toBe("supplemental");
    expect(statusById(model.sections, "portfolio_headline")).toBe("supplemental");
    expect(model.firstScreenSections.map((section) => section.id)).toContain("core_metrics");
    expect(model.metricRail.map((item) => item.label)).toContain("组合DV01");
    expect(model.analysisCards).toHaveLength(4);
  });

  it("blocks mismatched report-date sections and marks stale market context", () => {
    const model = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      snapshotMode: "strict",
      isMockMode: false,
      coreMetrics: coreMetrics("2026-03-31"),
      dailyChanges: dailyChanges("2026-03-31"),
      bondHeadline: bondHeadline("2026-03-31"),
      portfolio: portfolio("2026-03-31"),
      marketPoints: [
        macroPoint({
          series_id: "CA.BRENT",
          series_name: "Brent",
          trade_date: "2026-04-27",
          value_numeric: 113.89,
          unit: "USD/bbl",
        }),
      ],
      calendarItems: [],
    });

    expect(statusById(model.sections, "core_metrics")).toBe("blocked");
    expect(statusById(model.sections, "daily_changes")).toBe("blocked");
    expect(statusById(model.sections, "bond_headline")).toBe("blocked");
    expect(statusById(model.sections, "portfolio_headline")).toBe("blocked");
    expect(model.firstScreenSections.map((section) => section.id)).not.toContain("core_metrics");
    expect(model.marketTicker[0]).toMatchObject({ id: "CA.BRENT", status: "stale" });
  });

  it("keeps reserved/demo surfaces out of the first-screen sections", () => {
    const model = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      snapshotMode: "strict",
      isMockMode: true,
      coreMetrics: coreMetrics(),
      dailyChanges: dailyChanges(),
      bondHeadline: bondHeadline(),
      portfolio: portfolio(),
      marketPoints: [],
      calendarItems: [],
    });

    expect(model.sections.find((section) => section.id === "executive_risk_overview")).toMatchObject({
      status: "reserved",
      firstScreenAllowed: false,
    });
    expect(model.firstScreenSections.some((section) => section.status === "reserved")).toBe(false);
    expect(model.firstScreenSections.some((section) => section.status === "demo")).toBe(false);
  });
});
