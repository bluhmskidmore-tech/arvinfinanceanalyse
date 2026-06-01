import { describe, expect, it } from "vitest";

import type {
  BondDashboardHeadlinePayload,
  BondPortfolioHeadlinesPayload,
  ChoiceMacroLatestPoint,
  CoreMetricsResult,
  DailyChangesResult,
  Numeric,
  PnlByBusinessAnalysisRow,
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
      total_dv01: numeric("106,155,944", 106_155_944.31),
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
    total_dv01: numeric("106,155,944", 106_155_944.31),
    bond_count: 1740,
    credit_weight: numeric("29.25%"),
    issuer_hhi: numeric("5.09%"),
    issuer_top5_weight: numeric("41.35%"),
    by_asset_class: [
      {
        asset_class: "rate",
        market_value: numeric("1,344.90 亿"),
        duration: numeric("5.63"),
        dv01: numeric("73,667,216", 73_667_216.08),
        weight: numeric("39.12%"),
      },
      {
        asset_class: "credit",
        market_value: numeric("1,005.70 亿"),
        duration: numeric("2.40"),
        dv01: numeric("23,572,093", 23_572_092.66),
        weight: numeric("29.25%"),
      },
    ],
    warnings: [],
    computed_at: "2026-05-10T00:00:00Z",
  };
}

function backendScalarPortfolio(reportDate = "2026-04-30"): BondPortfolioHeadlinesPayload {
  return {
    report_date: reportDate,
    total_market_value: "343822795478.69000000",
    weighted_ytm: "0.02565621",
    weighted_duration: "4.13678311",
    weighted_coupon: "0.02069003",
    total_dv01: "106155944.30769531",
    bond_count: 1740,
    credit_weight: "0.29250449",
    issuer_hhi: "0.05088252",
    issuer_top5_weight: "0.41354965",
    by_asset_class: [
      {
        asset_class: "credit",
        market_value: "100569711455.34000000",
        duration: "2.40294438",
        dv01: "23572092.66263087",
        weight: "0.29250449",
      },
      {
        asset_class: "rate",
        market_value: "134490494185.69000000",
        duration: "5.62782976",
        dv01: "73667216.08117440",
        weight: "0.39116224",
      },
    ],
    warnings: [],
    computed_at: "2026-05-10T00:00:00Z",
  } as unknown as BondPortfolioHeadlinesPayload;
}

function backendScalarHeadline(reportDate = "2026-04-30"): BondDashboardHeadlinePayload {
  return {
    report_date: reportDate,
    prev_report_date: "2026-03-31",
    kpis: {
      total_market_value: "343822795478.68999970",
      unrealized_pnl: "8012857242.10999940",
      weighted_ytm: "0.02565621",
      weighted_duration: "4.13678311",
      weighted_coupon: "0.02043630",
      credit_spread_median: "0.02390000",
      total_dv01: "106155944.30769532",
      bond_count: 1740,
    },
    prev_kpis: null,
  } as unknown as BondDashboardHeadlinePayload;
}

function bondBucketRows(): PnlByBusinessAnalysisRow[] {
  return [
    {
      dimension_key: "rate_bond",
      dimension_label: "利率债",
      interest_income: "0",
      fair_value_change: "0",
      capital_gain: "0",
      manual_adjustment: "0",
      total_pnl: "100.00",
      avg_balance: "1000.00",
      current_balance: "1000.00",
      annualized_yield_pct: "117.741935",
      ftp_rate_pct: "1.600000",
      ftp_cost: "1.36",
      ftp_net_pnl: "98.64",
      ftp_net_annualized_yield_pct: "116.141935",
      asset_count: 3,
    },
    {
      dimension_key: "credit_bond",
      dimension_label: "信用债",
      interest_income: "0",
      fair_value_change: "0",
      capital_gain: "0",
      manual_adjustment: "0",
      total_pnl: "80.00",
      avg_balance: "800.00",
      current_balance: "800.00",
      annualized_yield_pct: "98.500000",
      ftp_rate_pct: "1.600000",
      ftp_cost: "1.02",
      ftp_net_pnl: "78.98",
      ftp_net_annualized_yield_pct: "96.900000",
      asset_count: 4,
    },
    {
      dimension_key: "financial_bond",
      dimension_label: "金融债",
      interest_income: "0",
      fair_value_change: "0",
      capital_gain: "0",
      manual_adjustment: "0",
      total_pnl: "60.00",
      avg_balance: "600.00",
      current_balance: "600.00",
      annualized_yield_pct: "73.000000",
      ftp_rate_pct: "1.600000",
      ftp_cost: "0.82",
      ftp_net_pnl: "59.18",
      ftp_net_annualized_yield_pct: "71.400000",
      asset_count: 2,
    },
    {
      dimension_key: "other_bond",
      dimension_label: "其它债券",
      interest_income: "0",
      fair_value_change: "0",
      capital_gain: "0",
      manual_adjustment: "0",
      total_pnl: "40.00",
      avg_balance: "400.00",
      current_balance: "400.00",
      annualized_yield_pct: "36.500000",
      ftp_rate_pct: "1.600000",
      ftp_cost: "0.55",
      ftp_net_pnl: "39.45",
      ftp_net_annualized_yield_pct: "34.900000",
      asset_count: 1,
    },
  ];
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
    expect(model.watchRows.map((row) => row.code)).toEqual(["久期", "信用", "DV01"]);
    expect(model.watchRows.map((row) => row.actionLabel)).toEqual(["看久期", "看信用", "看风险"]);
    expect(model.watchRows.map((row) => row.route)).toEqual(["/bond-analysis", "/bond-analysis", "/risk-tensor"]);
    expect(model.accountRows.map((row) => row.accountName)).toEqual([
      "债券组合",
      "信用债",
      "利率债",
      "风险复核",
    ]);
    expect(model.accountRows.map((row) => row.route)).toEqual([
      "/bond-analysis",
      "/bond-analysis",
      "/bond-analysis",
      "/risk-tensor",
    ]);
    expect(model.watchRows.map((row) => row.code).join(" ")).not.toMatch(/PORT-/i);
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
        macroPoint({
          series_id: "CA.CSI300",
          series_name: "沪深300",
          trade_date: "2026-04-27",
          value_numeric: 4871.91,
          latest_change: -28.6,
          unit: "index",
        }),
      ],
      calendarItems: [],
    });

    expect(statusById(model.sections, "core_metrics")).toBe("blocked");
    expect(statusById(model.sections, "daily_changes")).toBe("blocked");
    expect(statusById(model.sections, "bond_headline")).toBe("blocked");
    expect(statusById(model.sections, "portfolio_headline")).toBe("blocked");
    expect(model.firstScreenSections.map((section) => section.id)).not.toContain("core_metrics");
    expect(model.marketTicker[0]).toMatchObject({
      id: "CA.BRENT",
      value: "113.89",
      delta: "+0.01",
      unitLabel: "USD/bbl",
      status: "stale",
    });
    expect(model.marketTicker.find((item) => item.id === "CA.CSI300")).toMatchObject({
      unitLabel: "指数",
      delta: "-28.6",
    });
    expect(model.waterfall.every((item) => item.status === "blocked")).toBe(true);
    expect(model.portfolioMix).toEqual([
      expect.objectContaining({
        id: "portfolio-blocked",
        status: "blocked",
        value: "--",
      }),
    ]);
    expect(model.riskItems).toEqual([
      expect.objectContaining({
        id: "portfolio-risk-blocked",
        status: "blocked",
        value: "--",
      }),
    ]);
    expect(model.watchRows).toEqual([
      expect.objectContaining({
        id: "watch-blocked",
        status: "blocked",
        route: "/platform-config",
        actionLabel: "治理字段",
      }),
    ]);
    expect(model.accountRows).toEqual([
      expect.objectContaining({
        id: "account-blocked",
        status: "blocked",
        route: "/platform-config",
        source: "组合结构读面未返回同日报告日。",
      }),
    ]);
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

  it("formats backend scalar strings for portfolio, risk, and watch rows", () => {
    const model = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      snapshotMode: "strict",
      isMockMode: false,
      coreMetrics: coreMetrics(),
      dailyChanges: dailyChanges(),
      bondHeadline: backendScalarHeadline(),
      portfolio: backendScalarPortfolio(),
      marketPoints: [],
      calendarItems: [],
    });

    expect(model.portfolioMix[0]).toMatchObject({
      label: "信用债",
      value: "29.25%",
      marketValue: "1,005.70 亿",
      duration: "2.40",
      detail: "1,005.70 亿 / 久期 2.40",
      status: "supplemental",
    });
    expect(model.portfolioMix[1]).toMatchObject({
      label: "利率债",
      value: "39.12%",
      detail: "1,344.90 亿 / 久期 5.63",
    });
    expect(model.riskItems.map((item) => item.value)).toEqual([
      "10,615.59 万",
      "4.14",
      "41.35%",
      "29.25%",
    ]);
    expect(model.riskItems.map((item) => item.level)).toEqual([71, 59, 41, 29]);
    expect(model.watchRows[0]).toMatchObject({
      code: "久期",
      name: "组合久期",
      maturity: "4.14",
      yieldValue: "2.57%",
      dailyChange: "+2.95 亿",
      route: "/bond-analysis",
      actionLabel: "看久期",
    });
    expect(model.watchRows[1]).toMatchObject({
      code: "信用",
      name: "信用仓位",
      maturity: "29.25%",
      yieldValue: "239bp",
      dailyChange: "41.35%",
      route: "/bond-analysis",
      actionLabel: "看信用",
    });
    expect(model.accountRows[0]).toMatchObject({
      weight: "100.00%",
      duration: "4.14",
      ytm: "2.57%",
      dailyChange: expect.stringContaining("3.21"),
      risk: expect.stringContaining("10,615.59"),
      route: "/bond-analysis",
      status: "supplemental",
    });
    expect(model.accountRows[1]).toMatchObject({
      weight: "29.25%",
      duration: "2.40",
      ytm: "--",
      dailyChange: "--",
      risk: expect.stringContaining("2,357.21"),
      route: "/bond-analysis",
    });

    expect(model.accountRows.find((row) => row.id === "account-risk-review")).toMatchObject({
      weight: "41.35%",
      ytm: "--",
      dailyChange: "--",
      risk: expect.stringContaining("10,615.59"),
      source: expect.stringMatching(/Top5.*41\.35%.*29\.25%.*DV01/),
      route: "/risk-tensor",
    });

    const cockpitCopy = [
      ...model.metricRail.map((item) => item.hint),
      ...model.portfolioMix.map((item) => item.detail),
      ...model.riskItems.map((item) => item.hint),
      ...model.watchRows.map((row) => row.reason),
      ...model.accountRows.map((row) => row.source),
    ].join(" ");
    expect(cockpitCopy).not.toMatch(/headline|portfolio headlines|daily changes|adapter|mock/i);
  });

  it("renders compact blocked placeholders when same-day portfolio rows are unusable", () => {
    const emptyPortfolio = {
      ...backendScalarPortfolio(),
      by_asset_class: [],
      total_dv01: null,
      weighted_duration: null,
      issuer_top5_weight: null,
      credit_weight: null,
    } as unknown as BondPortfolioHeadlinesPayload;

    const model = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      snapshotMode: "strict",
      isMockMode: false,
      coreMetrics: null,
      dailyChanges: null,
      bondHeadline: null,
      portfolio: emptyPortfolio,
      marketPoints: [],
      calendarItems: [],
    });

    expect(model.portfolioMix).toEqual([
      expect.objectContaining({
        id: "portfolio-empty",
        status: "blocked",
        value: "--",
      }),
    ]);
    expect(model.riskItems).toEqual([
      expect.objectContaining({
        id: "portfolio-risk-empty",
        status: "blocked",
        value: "--",
      }),
    ]);
  });

  it("builds compact supplement preview signals from same-day coverage, daily move, and risk reads", () => {
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

    expect(model.previewSignals).toEqual([
      expect.objectContaining({
        id: "coverage",
        label: "补充覆盖",
        value: "4/4",
        status: "supplemental",
      }),
      expect.objectContaining({
        id: "net-change",
        value: expect.stringContaining("2.95"),
        detail: expect.stringMatching(/3\.21.*1\.08|1\.08.*3\.21/),
        status: "supplemental",
      }),
      expect.objectContaining({
        id: "concentration",
        value: "41.35%",
        detail: expect.stringMatching(/Top5 41\.35%.*29\.25%/),
        status: "supplemental",
      }),
      expect.objectContaining({
        id: "duration-dv01",
        value: expect.stringContaining("10,615.59"),
        detail: expect.stringContaining("4.14"),
        status: "supplemental",
      }),
    ]);
  });

  it("maps bond-bucket analysis yields onto asset-class account rows", () => {
    const model = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      snapshotMode: "strict",
      isMockMode: false,
      coreMetrics: coreMetrics(),
      dailyChanges: dailyChanges(),
      bondHeadline: bondHeadline(),
      portfolio: portfolio(),
      bondBucketRows: bondBucketRows(),
      marketPoints: [],
      calendarItems: [],
    });

    expect(model.accountRows.find((row) => row.id === "account-credit")).toMatchObject({
      ytm: "98.50%",
      dailyChange: "--",
    });
    expect(model.accountRows.find((row) => row.id === "account-rate")).toMatchObject({
      ytm: "117.74%",
      dailyChange: "--",
    });
    expect(model.accountRows.find((row) => row.id === "account-other")).toBeUndefined();
  });

  it("keeps supplement preview signals explicit when same-day supplement reads are blocked", () => {
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

    expect(model.previewSignals).toEqual([
      expect.objectContaining({
        id: "coverage",
        value: "0/4",
        detail: expect.stringContaining("strict"),
        status: "blocked",
      }),
      expect.objectContaining({
        id: "net-change",
        value: "--",
        status: "blocked",
      }),
      expect.objectContaining({
        id: "concentration",
        value: "--",
        status: "blocked",
      }),
      expect.objectContaining({
        id: "duration-dv01",
        value: "--",
        status: "blocked",
      }),
    ]);
  });
});
