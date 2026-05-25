import { describe, expect, it } from "vitest";

import type { CoreMetricsResult } from "../../../api/contracts";
import type { DashboardOverviewMetricVM } from "../../executive-dashboard/adapters/executiveDashboardAdapter";
import { formatRawAsNumeric } from "../../../utils/format";
import { buildDashboardCockpitModel } from "./dashboardCockpitModel";
import { buildDashboardHomeModel } from "./dashboardHomeModel";
import {
  buildDashboardCockpitHeaderStatus,
  buildDashboardCockpitHomeViewModel,
  buildDecisionSidebarSections,
  buildDecisionSpine,
  buildRiskRadarFromRiskItems,
  formatWaterfallValueDisplay,
} from "./dashboardCockpitHomeModel";

function overviewMetric(partial: Partial<DashboardOverviewMetricVM>): DashboardOverviewMetricVM {
  return {
    id: partial.id ?? "aum",
    label: partial.label ?? "债券资产规模",
    caliberLabel: partial.caliberLabel ?? null,
    value: partial.value ?? { raw: 1, unit: "yuan", display: "1.00 亿", precision: 2, sign_aware: false },
    delta: partial.delta ?? { raw: -0.05, unit: "pct", display: "-5.80%", precision: 2, sign_aware: true },
    tone: partial.tone ?? "positive",
    detail: partial.detail ?? "",
    history: partial.history ?? null,
    ...partial,
  };
}

function coreMetricCard(totalAmount: number, rate: number, changeAmount: number, changePct: number) {
  return {
    total_amount: formatRawAsNumeric({ raw: totalAmount, unit: "yuan", sign_aware: false }),
    weighted_avg_rate: formatRawAsNumeric({ raw: rate, unit: "pct", sign_aware: false }),
    change_amount: formatRawAsNumeric({ raw: changeAmount, unit: "yuan", sign_aware: true }),
    change_pct: formatRawAsNumeric({ raw: changePct, unit: "pct", sign_aware: true }),
    top_3_details: [],
  };
}

function buildRealModeView(input?: {
  metrics?: DashboardOverviewMetricVM[];
  coreMetrics?: CoreMetricsResult | null;
  reportDate?: string;
  bondHeadline?: Parameters<typeof buildDashboardCockpitHomeViewModel>[0]["bondHeadline"];
  portfolio?: Parameters<typeof buildDashboardCockpitHomeViewModel>[0]["portfolio"];
  portfolioComparison?: Parameters<typeof buildDashboardCockpitHomeViewModel>[0]["portfolioComparison"];
  creditSpreadMigration?: Parameters<typeof buildDashboardCockpitHomeViewModel>[0]["creditSpreadMigration"];
  bondBucketMonthly?: Parameters<typeof buildDashboardCockpitHomeViewModel>[0]["bondBucketMonthly"];
  decisionItems?: Parameters<typeof buildDashboardCockpitHomeViewModel>[0]["decisionItems"];
  attribution?: Parameters<typeof buildDashboardCockpitHomeViewModel>[0]["attribution"];
}) {
  const reportDate = input?.reportDate ?? "2026-04-30";
  const home = buildDashboardHomeModel({
    metrics: input?.metrics ?? [],
    snapshotReportDate: reportDate,
    isSnapshotLoading: false,
    calendarIsLoading: false,
    calendarIsError: false,
    isMockMode: false,
  });
  const cockpit = buildDashboardCockpitModel({
    reportDate,
    isMockMode: false,
  });
  return buildDashboardCockpitHomeViewModel({
    home,
    cockpit,
    metrics: input?.metrics ?? [],
    coreMetrics: input?.coreMetrics ?? null,
    bondHeadline: input?.bondHeadline ?? null,
    portfolio: input?.portfolio ?? null,
    portfolioComparison: input?.portfolioComparison ?? null,
    creditSpreadMigration: input?.creditSpreadMigration ?? null,
    decisionItems: input?.decisionItems ?? null,
    attribution: input?.attribution ?? null,
    bondBucketMonthly: input?.bondBucketMonthly ?? null,
  });
}

describe("buildDashboardCockpitHomeViewModel", () => {
  it("builds six KPI cards and eight market pulse slots", () => {
    const home = buildDashboardHomeModel({
      metrics: [
        overviewMetric({ id: "aum", label: "债券资产规模（zqtz）", value: { raw: 1, unit: "yuan", display: "3,708.10 亿", precision: 2, sign_aware: false } }),
        overviewMetric({ id: "yield", label: "年度损益", value: { raw: 1, unit: "yuan", display: "+29.71 亿", precision: 2, sign_aware: false } }),
      ],
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const cockpit = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      isMockMode: false,
      marketPoints: [
        {
          series_id: "CA.CN_GOV_10Y",
          series_name: "10年国债",
          trade_date: "2026-04-30",
          value_numeric: 1.94,
          unit: "%",
          source_version: "sv",
          vendor_version: "vv",
          quality_flag: "ok",
          latest_change: 0.02,
          recent_points: [
            { trade_date: "2026-04-25", value_numeric: 1.9, source_version: "sv", vendor_version: "vv", quality_flag: "ok" },
            { trade_date: "2026-04-26", value_numeric: 1.91, source_version: "sv", vendor_version: "vv", quality_flag: "ok" },
            { trade_date: "2026-04-29", value_numeric: 1.92, source_version: "sv", vendor_version: "vv", quality_flag: "ok" },
            { trade_date: "2026-04-30", value_numeric: 1.94, source_version: "sv", vendor_version: "vv", quality_flag: "ok" },
          ],
          refresh_tier: "stable",
        },
      ],
    });

    const view = buildDashboardCockpitHomeViewModel({
      home,
      cockpit,
      metrics: home.heroMetrics.length ? undefined : [
        overviewMetric({ id: "aum" }),
      ],
    });

    expect(view.kpiCards).toHaveLength(6);
    expect(view.marketPulse).toHaveLength(8);
    expect(view.kpiCards[0]?.label).toContain("债券资产规模");
    expect(view.decisionSidebarSections).toHaveLength(6);
    expect(view.decisionSidebarSections[0]?.title).toBe("今日主线");
    expect(view.executiveOverview.coreMetrics.map((card) => card.id)).toEqual([
      "aum",
      "yield",
      "nim",
    ]);
    expect(view.executiveOverview.riskConstraints.map((card) => card.id)).toEqual([
      "dv01",
      "duration",
      "concentration",
    ]);
    expect(view.executiveOverview.summary).toContain("待同步或复核");
    expect(view.executiveOverview.healthText).toBe("数据链路待复核，核心指标不生成正式结论。");
    expect(view.aiDecisionSummary.map((item) => item.id)).toEqual([
      "mainline",
      "max-drag",
      "max-contribution",
      "key-risk",
      "suggested-actions",
      "pending-todos",
    ]);
    expect(view.riskActionStrip.todoCount).toBe(view.todos.length);
    expect(view.riskActionStrip.watchCount).toBe(view.watchlist.length);
  });

  it("prefers real KPI and market pulse values over local mock fillers", () => {
    const home = buildDashboardHomeModel({
      metrics: [
        overviewMetric({
          id: "aum",
          label: "债券资产规模",
          value: { raw: 4_567_890_000_000, unit: "yuan", display: "45678.90 亿", precision: 2, sign_aware: false },
        }),
        overviewMetric({
          id: "nim",
          label: "净息差（年化）",
          value: { raw: 0.0023, unit: "pct", display: "+0.23%", precision: 2, sign_aware: false },
          delta: { raw: 0.0001, unit: "pct", display: "较昨日 +0.01bp", precision: 2, sign_aware: true },
        }),
      ],
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const cockpit = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      isMockMode: false,
      marketPoints: [
        {
          series_id: "E1000180",
          series_name: "10年国债",
          trade_date: "2026-04-30",
          value_numeric: 2.31,
          unit: "%",
          source_version: "sv",
          vendor_version: "vv",
          quality_flag: "ok",
          latest_change: -0.04,
          recent_points: [],
          refresh_tier: "stable",
        },
      ],
    });

    const view = buildDashboardCockpitHomeViewModel({
      home,
      cockpit,
      metrics: [
        overviewMetric({
          id: "aum",
          value: {
            raw: 4_567_890_000_000,
            unit: "yuan",
            display: "45678.90 亿",
            precision: 2,
            sign_aware: false,
          },
        }),
        overviewMetric({
          id: "nim",
          value: { raw: 0.0023, unit: "pct", display: "+0.23%", precision: 2, sign_aware: false },
        }),
      ],
    });

    expect(view.dataSource).toBe("real");
    expect(view.kpiCards.find((card) => card.id === "aum")?.value).toBe("45678.90 亿");
    expect(view.kpiCards.find((card) => card.id === "nim")?.value).toBe("+0.23%");
    expect(view.kpiCards.find((card) => card.id === "nim")?.value).not.toBe("1.76%");
    expect(view.marketPulse.find((item) => item.id === "cgb10y")?.value).toBe("2.31%");
    expect(view.marketPulse.find((item) => item.id === "cgb10y")?.value).not.toBe("1.76%");
    expect(view.dataWarningMessages.join(" ")).not.toContain("本地模拟数据");
  });

  it("uses available real market inputs for all first-screen market pulse slots", () => {
    const home = buildDashboardHomeModel({
      metrics: [],
      snapshotReportDate: "2026-04-30",
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const marketPoint = (series_id: string, value_numeric: number, latest_change: number | null, unit = "%") => ({
      series_id,
      series_name: series_id,
      trade_date: "2026-04-30",
      value_numeric,
      unit,
      source_version: "sv",
      vendor_version: "vv",
      quality_flag: "ok" as const,
      latest_change,
      recent_points: [],
      refresh_tier: "stable" as const,
    });
    const cockpit = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      isMockMode: false,
      marketPoints: [
        marketPoint("EMM00166458", 1.2057, 0.0112),
        marketPoint("EMM00166466", 1.7514, -0.0078),
        marketPoint("CA.DR007", 1.29, -0.01),
        marketPoint("EMG00001310", 4.38, -0.03),
        marketPoint("EMM00058124", 6.8502, 0.0015, "CNY/USD"),
        marketPoint("CA.BRENT", 118.26, -5.98, "USD/bbl"),
        marketPoint("CA.CSI300", 4998.3417, 50.2952, "index"),
        marketPoint("CA.CSI300_PCT_CHG", 1.0165, 1.093),
        marketPoint("EMM00166655", 1.5417, null, "unknown"),
      ],
    });

    const view = buildDashboardCockpitHomeViewModel({ home, cockpit, metrics: [] });

    expect(view.marketPulse).toHaveLength(8);
    expect(view.marketPulse.map((item) => [item.id, item.value])).toEqual([
      ["cgb10y", "1.75%"],
      ["dr007", "1.29%"],
      ["slope", "-54bp"],
      ["us10y", "4.38%"],
      ["usdcny", "6.85"],
      ["brent", "118.26"],
      ["csi300", "4,998.34"],
      ["credit-spread", "33bp"],
    ]);
    expect(view.marketPulse.every((item) => item.value !== "—")).toBe(true);
    expect(view.dataWarningMessages.join(" ")).not.toContain("本地模拟数据");
  });

  it("ranks market focus by live move magnitude instead of tape display order", () => {
    const reportDate = "2026-04-30";
    const home = buildDashboardHomeModel({
      metrics: [],
      snapshotReportDate: reportDate,
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const marketPoint = (series_id: string, value_numeric: number, latest_change: number | null, unit = "%") => ({
      series_id,
      series_name: series_id,
      trade_date: reportDate,
      value_numeric,
      unit,
      source_version: "sv",
      vendor_version: "vv",
      quality_flag: "ok" as const,
      latest_change,
      recent_points: [],
      refresh_tier: "stable" as const,
    });
    const cockpit = buildDashboardCockpitModel({
      reportDate,
      isMockMode: false,
      marketPoints: [
        marketPoint("CA.CN_GOV_10Y", 1.76, 0.02),
        marketPoint("CA.BRENT", 118.26, -5.98, "USD/bbl"),
      ],
    });

    const view = buildDashboardCockpitHomeViewModel({ home, cockpit, metrics: [] });

    expect(view.marketPulse[0]?.id).toBe("cgb10y");
    expect(view.decisionSpine.marketFocus).toContain("原油 Brent");
    expect(view.decisionSpine.marketFocus).not.toContain("10年国债 1.76%");
  });

  it("uses governed judgment in the executive overview when real data is complete", () => {
    const reportDate = "2026-04-30";
    const metrics = [
      overviewMetric({ id: "aum", value: { raw: 3_708.1, unit: "yi", display: "3,708.10 亿", precision: 2, sign_aware: false } }),
      overviewMetric({ id: "yield", value: { raw: 29.71, unit: "yi", display: "+29.71 亿", precision: 2, sign_aware: true } }),
      overviewMetric({ id: "nim", value: { raw: 1.76, unit: "pct", display: "1.76%", precision: 2, sign_aware: false } }),
      overviewMetric({ id: "dv01", value: { raw: 10615.59, unit: "dv01", display: "10,615.59 万", precision: 2, sign_aware: false } }),
      overviewMetric({ id: "duration", value: { raw: 4.14, unit: "ratio", display: "4.14", precision: 2, sign_aware: false } }),
      overviewMetric({ id: "concentration", value: { raw: 41.35, unit: "pct", display: "41.35%", precision: 2, sign_aware: false } }),
    ];
    const home = buildDashboardHomeModel({
      metrics,
      baseVerdict: {
        conclusion: "正式经营判断来自受治理快照。",
        tone: "neutral",
        reasons: [],
        suggestions: [],
      },
      snapshotReportDate: reportDate,
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const marketPoint = (series_id: string, value_numeric: number, latest_change: number | null, unit = "%") => ({
      series_id,
      series_name: series_id,
      trade_date: reportDate,
      value_numeric,
      unit,
      source_version: "sv",
      vendor_version: "vv",
      quality_flag: "ok" as const,
      latest_change,
      recent_points: [],
      refresh_tier: "stable" as const,
    });
    const cockpit = buildDashboardCockpitModel({
      reportDate,
      isMockMode: false,
      marketPoints: [
        marketPoint("EMM00166458", 1.2057, 0.0112),
        marketPoint("EMM00166466", 1.7514, -0.0078),
        marketPoint("CA.DR007", 1.29, -0.01),
        marketPoint("EMG00001310", 4.38, -0.03),
        marketPoint("EMM00058124", 6.8502, 0.0015, "CNY/USD"),
        marketPoint("CA.BRENT", 118.26, -5.98, "USD/bbl"),
        marketPoint("CA.CSI300", 4998.3417, 50.2952, "index"),
        marketPoint("EMM00166655", 1.5417, null, "unknown"),
      ],
    });
    const numeric = (raw: number, unit: Parameters<typeof formatRawAsNumeric>[0]["unit"] = "yuan") =>
      formatRawAsNumeric({ raw, unit, sign_aware: false });
    const view = buildDashboardCockpitHomeViewModel({
      home,
      cockpit,
      metrics,
      bondHeadline: {
        report_date: reportDate,
        prev_report_date: null,
        kpis: {
          total_market_value: numeric(3708.1, "yi"),
          unrealized_pnl: numeric(29.71, "yi"),
          weighted_ytm: numeric(2.85, "pct"),
          weighted_duration: numeric(4.14, "ratio"),
          weighted_coupon: numeric(2.85, "pct"),
          credit_spread_median: numeric(69.8, "bp"),
          total_dv01: numeric(10615.59, "dv01"),
          bond_count: 1256,
        },
        prev_kpis: null,
      },
      portfolioComparison: {
        report_date: reportDate,
        items: [
          {
            portfolio_name: "组合A",
            total_market_value: numeric(3708.1, "yi"),
            weighted_ytm: numeric(2.85, "pct"),
            weighted_duration: numeric(4.14, "ratio"),
            total_dv01: numeric(10615.59, "dv01"),
            bond_count: 1256,
          },
        ],
      },
      creditSpreadMigration: {
        report_date: reportDate,
        credit_bond_count: 1,
        credit_market_value: numeric(1, "yi"),
        credit_weight: numeric(1, "pct"),
        spread_dv01: numeric(1, "dv01"),
        weighted_avg_spread: numeric(69.8, "bp"),
        weighted_avg_spread_duration: numeric(1, "ratio"),
        spread_scenarios: [],
        migration_scenarios: [],
        concentration_by_rating: {
          dimension: "rating",
          hhi: numeric(1, "pct"),
          top5_concentration: numeric(1, "pct"),
          top_items: [{ name: "AAA", weight: numeric(1, "pct"), market_value: numeric(1, "yi") }],
        },
        oci_credit_exposure: numeric(1, "yi"),
        oci_spread_dv01: numeric(1, "dv01"),
        oci_sensitivity_25bp: numeric(1, "yuan"),
        warnings: [],
        computed_at: "2026-04-30T09:15:00+08:00",
      },
    });

    expect(view.dataWarningMessages).toEqual([]);
    expect(view.executiveOverview.summary).toBe("正式经营判断来自受治理快照。");
    expect(view.executiveOverview.healthText).toBe("核心指标已进入可复核区间。");
  });

  it("keeps the first-screen judgment usable when only secondary portfolio fields are pending", () => {
    const reportDate = "2026-04-30";
    const metrics = [
      overviewMetric({ id: "aum", value: { raw: 3_708.1, unit: "yi", display: "3,708.10 亿", precision: 2, sign_aware: false } }),
      overviewMetric({ id: "yield", value: { raw: 29.71, unit: "yi", display: "+29.71 亿", precision: 2, sign_aware: true } }),
      overviewMetric({ id: "nim", value: { raw: 1.76, unit: "pct", display: "1.76%", precision: 2, sign_aware: false } }),
      overviewMetric({ id: "dv01", value: { raw: 10615.59, unit: "dv01", display: "10,615.59 万", precision: 2, sign_aware: false } }),
      overviewMetric({ id: "duration", value: { raw: 4.14, unit: "ratio", display: "4.14", precision: 2, sign_aware: false } }),
      overviewMetric({ id: "concentration", value: { raw: 41.35, unit: "pct", display: "41.35%", precision: 2, sign_aware: false } }),
    ];
    const home = buildDashboardHomeModel({
      metrics,
      baseVerdict: {
        conclusion: "正式经营判断来自首屏核心指标。",
        tone: "neutral",
        reasons: [],
        suggestions: [],
      },
      snapshotReportDate: reportDate,
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const marketPoint = (series_id: string, value_numeric: number, latest_change: number | null, unit = "%") => ({
      series_id,
      series_name: series_id,
      trade_date: reportDate,
      value_numeric,
      unit,
      source_version: "sv",
      vendor_version: "vv",
      quality_flag: "ok" as const,
      latest_change,
      recent_points: [],
      refresh_tier: "stable" as const,
    });
    const cockpit = buildDashboardCockpitModel({
      reportDate,
      isMockMode: false,
      marketPoints: [
        marketPoint("EMM00166458", 1.2057, 0.0112),
        marketPoint("EMM00166466", 1.7514, -0.0078),
        marketPoint("CA.DR007", 1.29, -0.01),
        marketPoint("EMG00001310", 4.38, -0.03),
        marketPoint("EMM00058124", 6.8502, 0.0015, "CNY/USD"),
        marketPoint("CA.BRENT", 118.26, -5.98, "USD/bbl"),
        marketPoint("CA.CSI300", 4998.3417, 50.2952, "index"),
        marketPoint("EMM00166655", 1.5417, null, "unknown"),
      ],
    });

    const view = buildDashboardCockpitHomeViewModel({
      home,
      cockpit,
      metrics,
    });

    expect(view.portfolioStats.some((stat) => stat.value === "待同步")).toBe(true);
    expect(view.dataWarningMessages).toContain("资产分布缺少 portfolio-comparison.items 字段");
    expect(view.dataWarningMessages).toContain(
      "资产分布缺少 credit-spread-migration.concentration_by_rating.top_items[0].name 字段",
    );
    expect(view.executiveOverview.summary).toBe("正式经营判断来自首屏核心指标。");
    expect(view.executiveOverview.healthText).toBe("首屏核心指标已进入可复核区间；下方缺口保留局部空态。");
    expect(view.executiveOverview.summary).not.toContain("待同步或复核");
  });

  it("marks missing KPI slots as pending in real mode instead of injecting mock numbers", () => {
    const home = buildDashboardHomeModel({
      metrics: [],
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const cockpit = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      isMockMode: false,
    });

    const view = buildDashboardCockpitHomeViewModel({ home, cockpit, metrics: [] });

    expect(view.dataSource).toBe("real");
    expect(view.kpiCards).toHaveLength(6);
    expect(view.kpiCards.some((card) => card.pending)).toBe(true);
    expect(view.kpiCards.find((card) => card.id === "aum")?.value).toBe("—");
    expect(view.kpiCards.find((card) => card.id === "aum")?.value).not.toBe("3,708.10 亿");
    expect(view.dataWarningMessages.join(" ")).toContain("部分指标待同步");
    expect(view.dataWarningMessages.join(" ")).not.toContain("本地模拟数据");
  });

  it("builds portfolio center AUM from KPI aum card in mock fallback", () => {
    const home = buildDashboardHomeModel({
      metrics: [],
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const cockpit = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      isMockMode: false,
    });

    const view = buildDashboardCockpitHomeViewModel({
      home,
      cockpit,
      metrics: [],
      useMockFallback: true,
    });

    expect(view.portfolioCenterAum).toEqual({
      value: "3,708.10 亿",
      label: "债券资产规模",
    });
    expect(view.kpiCards.find((card) => card.id === "aum")?.value).toBe("3,708.10 亿");
  });

  it("shows gap portfolio center AUM when real mode has no aum KPI", () => {
    const view = buildRealModeView({ metrics: [] });

    expect(view.portfolioCenterAum).toEqual({
      value: "—",
      label: "债券资产规模",
    });
    expect(view.kpiCards.find((card) => card.id === "aum")?.value).toBe("—");
  });

  it("falls back to mock KPI and market pulse when useMockFallback is set", () => {
    const home = buildDashboardHomeModel({
      metrics: [],
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const cockpit = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      isMockMode: false,
    });

    const view = buildDashboardCockpitHomeViewModel({
      home,
      cockpit,
      metrics: [],
      useMockFallback: true,
    });

    expect(view.dataSource).toBe("mock");
    expect(view.kpiCards).toHaveLength(6);
    expect(view.kpiCards.every((card) => !card.pending)).toBe(true);
    expect(view.kpiCards[0]?.value).toBe("3,708.10 亿");
    expect(view.marketPulse).toHaveLength(8);
    expect(view.marketPulse.every((item) => item.value !== "--")).toBe(true);
    expect(view.marketPulse[0]?.statusLabel).toBe("演示");
    expect(view.showDataWarning).toBe(true);
    expect(view.dataWarningMessages[0]).toContain("本地模拟数据");
    expect(view.reportDate).toBe("2026-04-30");
  });

  it("formats header status from snapshot result_meta when available", () => {
    const status = buildDashboardCockpitHeaderStatus({
      snapshotMeta: {
        trace_id: "tr",
        basis: "analytical",
        result_kind: "home.snapshot",
        formal_use_allowed: false,
        source_version: "sv",
        vendor_version: "vv",
        rule_version: "rv",
        cache_version: "cv",
        quality_flag: "ok",
        vendor_status: "ok",
        fallback_mode: "none",
        scenario_flag: false,
        generated_at: "2026-04-30T09:15:00+08:00",
      },
      marketMeta: {
        trace_id: "tr-m",
        basis: "formal",
        result_kind: "market.rates",
        formal_use_allowed: true,
        source_version: "sv",
        vendor_version: "vv",
        rule_version: "rv",
        cache_version: "cv",
        quality_flag: "ok",
        vendor_status: "ok",
        fallback_mode: "none",
        scenario_flag: false,
        as_of_date: "2026-04-29",
        generated_at: "2026-04-30T09:00:00+08:00",
      },
      reportDate: "2026-04-30",
      alertCount: 3,
    });

    expect(status.dataUpdatedAt).toMatch(/09:15/);
    expect(status.marketStatus).toBe("市场已收盘");
    expect(status.notificationCount).toBe(3);
    expect(status.dataSyncPrefix).toBe("数据已更新");
    expect(status.valuationLabel).toBe("估值已完成");
    expect(status.valuationTone).toBe("ok");
    expect(status.dataFreshnessState).toBe("fresh");
    expect(status.riskReviewCount).toBe(3);
    expect(status.showRiskReview).toBe(true);
  });

  it("keeps mock header status explicit while sidebar still explains local data", () => {
    const status = buildDashboardCockpitHeaderStatus({
      useMockFallback: true,
      alertCount: 11,
    });

    expect(status.dataUpdatedAt).toBe("09:15");
    expect(status.dataSyncPrefix).toBe("数据使用本地模拟数据");
    expect(status.valuationLabel).toBe("估值待同步");
    expect(status.valuationTone).toBe("muted");
    expect(status.dataFreshnessState).toBe("mock-fallback");
    expect(status.riskReviewCount).toBe(11);
    expect(status.showRiskReview).toBe(true);
  });

  it("marks real header status as pending when snapshot time is missing", () => {
    const status = buildDashboardCockpitHeaderStatus({
      reportDate: "2026-04-30",
      alertCount: 0,
      useMockFallback: false,
    });

    expect(status.dataUpdatedAt).toBe("待同步");
    expect(status.dataSyncPrefix).toBe("数据时间待同步");
    expect(status.valuationLabel).toBe("估值待同步");
    expect(status.valuationTone).toBe("muted");
    expect(status.dataFreshnessState).toBe("missing-snapshot-time");
    expect(status.showRiskReview).toBe(false);
  });

  it("does not mark live market pulse slots as estimated", () => {
    const home = buildDashboardHomeModel({
      metrics: [],
      snapshotReportDate: "2026-04-30",
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const cockpit = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      isMockMode: false,
      marketPoints: [
        {
          series_id: "E1000180",
          series_name: "10年国债",
          trade_date: "2026-04-30",
          value_numeric: 2.31,
          unit: "%",
          source_version: "sv",
          vendor_version: "vv",
          quality_flag: "ok",
          latest_change: -0.04,
          recent_points: [],
          refresh_tier: "stable",
        },
      ],
    });

    const view = buildDashboardCockpitHomeViewModel({ home, cockpit, metrics: [] });
    const live = view.marketPulse.find((item) => item.id === "cgb10y");

    expect(live?.value).toBe("2.31%");
    expect(live?.isEstimated).not.toBe(true);
  });

  it("marks derived market pulse spreads as estimated with flat sparklines", () => {
    const home = buildDashboardHomeModel({
      metrics: [],
      snapshotReportDate: "2026-04-30",
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const cockpit = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      isMockMode: false,
      marketPoints: [
        {
          series_id: "EMM00166458",
          series_name: "1Y国债",
          trade_date: "2026-04-30",
          value_numeric: 1.2057,
          unit: "%",
          source_version: "sv",
          vendor_version: "vv",
          quality_flag: "ok",
          latest_change: 0.01,
          recent_points: [],
          refresh_tier: "stable",
        },
        {
          series_id: "EMM00166466",
          series_name: "10Y国债",
          trade_date: "2026-04-30",
          value_numeric: 1.7514,
          unit: "%",
          source_version: "sv",
          vendor_version: "vv",
          quality_flag: "ok",
          latest_change: -0.01,
          recent_points: [],
          refresh_tier: "stable",
        },
      ],
    });

    const view = buildDashboardCockpitHomeViewModel({ home, cockpit, metrics: [] });
    const slope = view.marketPulse.find((item) => item.id === "slope");

    expect(slope?.isEstimated).toBe(true);
    expect(slope?.sparkline.every((point) => point === slope?.sparkline[0])).toBe(true);
  });

  it("does not mark gap market pulse slots as estimated", () => {
    const view = buildRealModeView({ metrics: [] });
    const gapSlots = view.marketPulse.filter((item) => item.value === "—");

    expect(gapSlots.length).toBeGreaterThan(0);
    expect(gapSlots.every((item) => item.isEstimated !== true)).toBe(true);
    expect(gapSlots.every((item) => item.statusLabel === "待同步")).toBe(true);
  });

  it("uses partial snapshot missing domains as first-screen decision evidence", () => {
    const home = buildDashboardHomeModel({
      metrics: [],
      snapshotReportDate: "2026-04-30",
      snapshotMode: "partial",
      snapshotDomainsMissing: ["pnl"],
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const cockpit = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      isMockMode: false,
    });

    const view = buildDashboardCockpitHomeViewModel({ home, cockpit, metrics: [] });
    const mainline = view.decisionSidebarSections.find((section) => section.id === "mainline");

    expect(view.dataWarningMessages).toContain("部分指标待同步");
    expect(view.dataWarningMessages).toContain("该日部分业务域不可用: pnl");
    expect(view.decisionSpine.evidenceState).toBe("该日部分业务域不可用: pnl");
    expect(view.executiveOverview.summary).toContain("待同步或复核");
    expect(view.executiveOverview.summary).not.toContain("利率上行拖累估值");
    expect(view.executiveOverview.healthText).toBe("数据链路待复核，核心指标不生成正式结论。");
    expect(mainline?.sourceType).toBe("pending");
    expect(mainline?.sourceLabel).toBe("待复核");
    expect(mainline?.evidenceLabel).toBe("该日部分业务域不可用: pnl");
    expect(view.aiDecisionSummary.find((item) => item.id === "mainline")?.sourceType).toBe(
      "pending",
    );
    expect(view.decisionSpine.rail.every((item) => item.sourceType !== "governed")).toBe(true);
  });

  it("adds decision spine relationship hints without changing the first-screen card counts", () => {
    const home = buildDashboardHomeModel({
      metrics: [],
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const cockpit = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      isMockMode: false,
    });

    const view = buildDashboardCockpitHomeViewModel({
      home,
      cockpit,
      metrics: [],
      useMockFallback: true,
    });

    expect(view.kpiCards).toHaveLength(6);
    expect(view.marketPulse).toHaveLength(8);
    expect(view.kpiCards.every((card) => Boolean(card.relationLabel))).toBe(true);
    expect(view.marketPulse.every((item) => Boolean(item.impactLabel))).toBe(true);
    expect(view.decisionSpine.rail.map((item) => item.label)).toEqual([
      "市场关注",
      "组合影响",
      "需处置项",
    ]);
    expect(
      view.decisionSpine.rail.map((item) => ({
        id: item.id,
        href: item.href,
        targetId: item.targetId,
        sourceType: item.sourceType,
        sourceLabel: item.sourceLabel,
      })),
    ).toEqual([
      {
        id: "market-focus",
        href: "#dashboard-home-market-section",
        targetId: "dashboard-home-market-section",
        sourceType: "mock-fallback",
        sourceLabel: "本地模拟",
      },
      {
        id: "portfolio-impact",
        href: "#dashboard-home-portfolio-section",
        targetId: "dashboard-home-portfolio-section",
        sourceType: "mock-fallback",
        sourceLabel: "本地模拟",
      },
      {
        id: "risk-focus",
        href: "#dashboard-home-risk-section",
        targetId: "dashboard-home-risk-section",
        sourceType: "mock-fallback",
        sourceLabel: "本地模拟",
      },
    ]);
    expect(view.decisionSpine.marketFocus).toContain("1Y-10Y利差");
    expect(view.decisionSpine.marketFocus).toContain("演示");
    expect(view.decisionSpine.evidenceState).toContain("本地模拟数据");
    expect(view.executiveOverview.summary).toContain("本地模拟数据");
    expect(view.executiveOverview.summary).not.toContain("利率上行拖累估值");
  });

  it("keeps estimated market focus out of the real-mode decision spine", () => {
    const reportDate = "2026-04-30";
    const home = buildDashboardHomeModel({
      metrics: [],
      snapshotReportDate: reportDate,
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const marketPoint = (series_id: string, value_numeric: number, latest_change: number | null) => ({
      series_id,
      series_name: series_id,
      trade_date: reportDate,
      value_numeric,
      unit: "%",
      source_version: "sv",
      vendor_version: "vv",
      quality_flag: "ok" as const,
      latest_change,
      recent_points: [],
      refresh_tier: "stable" as const,
    });
    const cockpit = buildDashboardCockpitModel({
      reportDate,
      isMockMode: false,
      marketPoints: [
        marketPoint("EMM00166458", 1.2057, 0.02),
        marketPoint("EMM00166466", 1.7514, -0.01),
      ],
    });

    const view = buildDashboardCockpitHomeViewModel({ home, cockpit, metrics: [] });
    const spine = buildDecisionSpine({
      headerStatus: view.headerStatus,
      judgment: view.judgment,
      kpiCards: [
        {
          id: "dv01",
          label: "组合DV01",
          value: "10,615.59 万",
          delta: "较昨日 +4.97 万",
          deltaTone: "up",
          iconLabel: "久",
          sparkline: [1, 2],
          group: "risk",
          groupLabel: "风险约束",
          signalLabel: "敞口上升",
          relationLabel: "关联利率风险",
        },
        {
          id: "duration",
          label: "久期（年）",
          value: "4.14",
          delta: "较昨日 -0.01",
          deltaTone: "down",
          iconLabel: "期",
          sparkline: [2, 1],
          group: "risk",
          groupLabel: "风险约束",
          signalLabel: "久期下降",
          relationLabel: "关联久期约束",
        },
      ],
      marketPulse: [
        {
          id: "slope",
          label: "1Y-10Y利差",
          value: "-54bp",
          delta: "+3bp",
          deltaTone: "up",
          sparkline: [-54, -54],
          statusLabel: "最近交易日",
          impactLabel: "期限结构",
          isEstimated: true,
        },
      ],
      attributionWaterfall: view.attributionWaterfall,
      alertCount: view.alertCount,
      riskAlertCounts: view.riskAlertCounts,
      todos: view.todos,
      dataSource: view.dataSource,
      dataWarningMessages: view.dataWarningMessages,
      useMockFallback: false,
    });

    expect(spine.marketFocus).toBe("待同步");
    expect(spine.rail.find((item) => item.id === "market-focus")?.value).toBe("待同步");
    expect(spine.marketFocus).not.toContain("-54bp");
    expect(spine.marketFocus).not.toContain("估算");
    expect(spine.portfolioImpact).toBe("久期（年） 4.14");
  });

  it("uses softer review wording in real-mode key risk sidebar when tier breakdown is unavailable", () => {
    const sections = buildDecisionSidebarSections({
      judgment: { conclusion: "测试", tone: "neutral", reasons: [], suggestions: [] },
      kpiCards: [],
      attributionWaterfall: [],
      attributionNote: [],
      alertCount: 5,
      riskAlertCounts: [
        { id: "high", label: "高风险预警", count: 5, tone: "warn" },
        { id: "medium", label: "中风险预警", count: 0, tone: "flat" },
        { id: "low", label: "低风险预警", count: 0, tone: "flat" },
      ],
      todos: [],
      useMockFallback: false,
    });
    const keyRisk = sections.find((section) => section.id === "key-risk");

    expect(keyRisk?.body).toBe("待复核 5 项");
    expect(keyRisk?.evidenceLabel).toBe("待复核口径");
    expect(keyRisk?.href).toBe("#dashboard-home-risk-section");
    expect(keyRisk?.targetId).toBe("dashboard-home-risk-section");
    expect(keyRisk?.body).not.toContain("高风险 5");
  });

  it("derives positive interbank net position tone from coreMetrics yuan raw", () => {
    const view = buildRealModeView({
      reportDate: "2026-04-08",
      coreMetrics: {
        report_date: "2026-04-08",
        bond_investments: coreMetricCard(0, 0, 0, 0),
        interbank_assets: coreMetricCard(8_800_000_000, 0.018, 0, 0),
        interbank_liabilities: coreMetricCard(6_600_000_000, 0.016, -200_000_000, -0.03),
      },
    });

    expect(view.interbankNetPosition).toBe("+22.00 亿");
    expect(view.interbankNetPositionTone).toBe("up");
  });

  it("does not inject mock balance metrics in real mode when overview metrics are missing", () => {
    const view = buildRealModeView({ metrics: [] });

    expect(view.dataSource).toBe("real");
    expect(view.balanceMetrics.every((metric) => metric.value === "—")).toBe(true);
    expect(view.balanceMetrics.every((metric) => metric.delta === "待同步")).toBe(true);
    expect(view.balanceMetrics.some((metric) => metric.value === "3,708.10 亿")).toBe(false);
    expect(view.balanceMetrics.some((metric) => metric.value === "+29.71 亿")).toBe(false);
  });

  it("does not inject mock attribution tabs when real mode has no attribution or waterfall", () => {
    const view = buildRealModeView({ metrics: [] });

    expect(view.dataSource).toBe("real");
    expect(view.attributionTabs.every((tab) => tab.pnl === "—")).toBe(true);
    expect(view.attributionTabs.every((tab) => tab.change === "待同步")).toBe(true);
    expect(view.attributionTabs.some((tab) => tab.pnl === "-368.09 万")).toBe(false);
    expect(view.attributionWaterfall).toEqual([]);
  });

  it("shows the exact missing attribution yield field instead of a generic caliber gap", () => {
    const view = buildRealModeView({
      attribution: {
        title: "真实归因",
        total: formatRawAsNumeric({ raw: -368_0900, unit: "yuan", sign_aware: true }),
        segments: [
          {
            id: "rate",
            label: "利率变动",
            amount: formatRawAsNumeric({ raw: -512_3400, unit: "yuan", sign_aware: true }),
            tone: "negative",
          },
        ],
      },
    });

    const dayTab = view.attributionTabs.find((tab) => tab.id === "day");
    expect(dayTab?.yield).toBe("—");
    expect(dayTab?.yield).not.toBe("口径待确认");
    expect(view.dataWarningMessages).toContain("归因收益率缺少 pnl-attribution.daily_yield 字段");
  });

  it("derives interbank net position from coreMetrics yuan raw, not display-only values", () => {
    const view = buildRealModeView({
      reportDate: "2026-04-08",
      coreMetrics: {
        report_date: "2026-04-08",
        bond_investments: coreMetricCard(0, 0, 0, 0),
        interbank_assets: coreMetricCard(8_800_000_000, 0.018, 0, 0),
        interbank_liabilities: coreMetricCard(6_600_000_000, 0.016, -200_000_000, -0.03),
      },
    });

    expect(view.interbankAssets).toBe("88.00 亿");
    expect(view.interbankLiabilities).toBe("66.00 亿");
    expect(view.interbankNetPosition).toBe("+22.00 亿");
  });

  it("shows pending interbank net position when yuan raw is unavailable", () => {
    const view = buildRealModeView({
      reportDate: "2026-04-08",
      coreMetrics: {
        report_date: "2026-04-08",
        bond_investments: coreMetricCard(0, 0, 0, 0),
        interbank_assets: {
          ...coreMetricCard(8_800_000_000, 0.018, 0, 0),
          total_amount: { raw: null, unit: "yuan", display: "88.00 亿", precision: 2, sign_aware: false },
        },
        interbank_liabilities: coreMetricCard(6_600_000_000, 0.016, -200_000_000, -0.03),
      },
    });

    expect(view.interbankAssets).toBe("88.00 亿");
    expect(view.interbankNetPosition).toBe("待同步");
  });

  it("builds business decision sidebar sections in mock fallback without refactor notes", () => {
    const home = buildDashboardHomeModel({
      metrics: [],
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const cockpit = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      isMockMode: false,
    });

    const view = buildDashboardCockpitHomeViewModel({
      home,
      cockpit,
      metrics: [],
      useMockFallback: true,
    });

    const titles = view.decisionSidebarSections.map((section) => section.title);
    expect(titles).toEqual([
      "今日主线",
      "关键风险",
      "最大拖累",
      "最大贡献",
      "待处理事项",
      "建议动作",
    ]);
    expect(view.decisionSidebarSections.some((section) => section.body.includes("信息分层重构"))).toBe(
      false,
    );
    expect(view.decisionSidebarSections.find((section) => section.id === "mainline")?.body.length).toBeGreaterThan(
      0,
    );
    expect(view.decisionSidebarSections.find((section) => section.id === "max-drag")?.body).toContain(
      "利率变动",
    );
    expect(view.decisionSidebarSections.find((section) => section.id === "max-contribution")?.body).toContain(
      "信用利差",
    );
    expect(view.decisionSidebarSections.find((section) => section.id === "pending-todos")?.body).toContain(
      "组合久期超限处理",
    );
    expect(view.decisionSidebarSections.find((section) => section.id === "suggested-actions")?.body).toContain(
      "利率上行",
    );
    expect(view.aiDecisionSummary.map((item) => item.title)).toEqual([
      "今日结论",
      "最大拖累",
      "最大贡献",
      "关键风险",
      "建议动作",
      "待处理事项",
    ]);
  });

  it("shows pending sync for attribution extremes in real mode without waterfall", () => {
    const view = buildRealModeView({ metrics: [] });
    const drag = view.decisionSidebarSections.find((section) => section.id === "max-drag");
    const contribution = view.decisionSidebarSections.find((section) => section.id === "max-contribution");

    expect(drag?.body).toBe("待同步");
    expect(contribution?.body).toBe("待同步");
  });

  it("uses real attribution extremes in the AI decision rail when waterfall data is available", () => {
    const view = buildRealModeView({
      metrics: [
        overviewMetric({
          id: "aum",
          value: { raw: 4_567_890_000_000, unit: "yuan", display: "45678.90 亿", precision: 2, sign_aware: false },
        }),
      ],
      attribution: {
        title: "真实归因",
        total: formatRawAsNumeric({ raw: 200_000_000, unit: "yuan", sign_aware: true }),
        segments: [
          {
            id: "rate",
            label: "利率变动",
            amount: formatRawAsNumeric({ raw: -30_000_000, unit: "yuan", sign_aware: true }),
            tone: "negative",
          },
          {
            id: "credit",
            label: "信用利差",
            amount: formatRawAsNumeric({ raw: 50_000_000, unit: "yuan", sign_aware: true }),
            tone: "positive",
          },
        ],
      },
    });
    const drag = view.decisionSidebarSections.find((section) => section.id === "max-drag");
    const contribution = view.decisionSidebarSections.find((section) => section.id === "max-contribution");

    expect(view.attributionWaterfall.some((item) => item.label === "利率变动")).toBe(true);
    expect(view.attributionWaterfall.some((item) => item.label === "信用利差")).toBe(true);
    expect(view.decisionSpine.pnlDriver).toContain("拖累 利率变动");
    expect(view.decisionSpine.pnlDriver).toContain("贡献 信用利差");
    expect(drag?.body).toBe("利率变动 -0.30 亿");
    expect(drag?.evidenceLabel).toBe("归因瀑布");
    expect(drag?.sourceType).toBe("derived");
    expect(drag?.sourceLabel).toBe("前端衍生");
    expect(contribution?.body).toBe("信用利差 +0.50 亿");
    expect(contribution?.evidenceLabel).toBe("归因瀑布");
    expect(contribution?.sourceType).toBe("derived");
    expect(contribution?.sourceLabel).toBe("前端衍生");
  });

  it("formats waterfall values with known units as-is and avoids blind 万 suffix", () => {
    expect(formatWaterfallValueDisplay("-368.09 万")).toBe("-368.09 万");
    expect(formatWaterfallValueDisplay("+29.71 亿")).toBe("+29.71 亿");
    expect(formatWaterfallValueDisplay("-512.34")).toBe("口径待确认");
    expect(formatWaterfallValueDisplay("—")).toBe("—");
    expect(formatWaterfallValueDisplay("待同步")).toBe("待同步");
  });

  it("uses tiered risk alert labels in real mode and keeps riskReviewOnly when medium/low are zero", () => {
    const view = buildRealModeView({ metrics: [] });

    expect(view.riskReviewOnly).toBe(true);
    expect(view.riskAlertCounts.find((item) => item.id === "high")?.label).toBe("高风险预警");
    expect(view.riskAlertCounts.find((item) => item.id === "medium")?.label).toBe("中风险预警");
    expect(view.riskAlertCounts.find((item) => item.id === "low")?.label).toBe("低风险预警");
  });

  it("aggregates risk alert counts by severity from home alerts in real mode", () => {
    const reportDate = "2026-04-30";
    const home = buildDashboardHomeModel({
      metrics: [
        overviewMetric({ id: "aum", tone: "negative" }),
        overviewMetric({ id: "yield", tone: "warning" }),
      ],
      snapshotReportDate: reportDate,
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const cockpit = buildDashboardCockpitModel({ reportDate, isMockMode: false });
    const view = buildDashboardCockpitHomeViewModel({
      home,
      cockpit,
      metrics: [
        overviewMetric({ id: "aum", tone: "negative" }),
        overviewMetric({ id: "yield", tone: "warning" }),
      ],
    });

    expect(view.riskReviewOnly).toBe(false);
    expect(view.riskAlertCounts.find((item) => item.id === "high")?.count).toBeGreaterThan(0);
    expect(view.riskAlertCounts.find((item) => item.id === "medium")?.count).toBeGreaterThan(0);
  });

  it("derives portfolio book count and dominant rating from supplemental APIs", () => {
    const view = buildRealModeView({
      reportDate: "2026-04-30",
      portfolioComparison: {
        report_date: "2026-04-30",
        items: [
          {
            portfolio_name: "自营组合 A",
            total_market_value: formatRawAsNumeric({ raw: 1, unit: "yuan", sign_aware: false }),
            weighted_ytm: formatRawAsNumeric({ raw: 0.02, unit: "pct", sign_aware: false }),
            weighted_duration: formatRawAsNumeric({ raw: 4, unit: "ratio", sign_aware: false }),
            total_dv01: formatRawAsNumeric({ raw: 1, unit: "dv01", sign_aware: false }),
            bond_count: 10,
          },
          {
            portfolio_name: "自营组合 B",
            total_market_value: formatRawAsNumeric({ raw: 2, unit: "yuan", sign_aware: false }),
            weighted_ytm: formatRawAsNumeric({ raw: 0.02, unit: "pct", sign_aware: false }),
            weighted_duration: formatRawAsNumeric({ raw: 3, unit: "ratio", sign_aware: false }),
            total_dv01: formatRawAsNumeric({ raw: 1, unit: "dv01", sign_aware: false }),
            bond_count: 8,
          },
        ],
      },
      creditSpreadMigration: {
        report_date: "2026-04-30",
        credit_bond_count: 1,
        credit_market_value: formatRawAsNumeric({ raw: 1, unit: "yuan", sign_aware: false }),
        credit_weight: formatRawAsNumeric({ raw: 0.3, unit: "pct", sign_aware: false }),
        spread_dv01: formatRawAsNumeric({ raw: 1, unit: "dv01", sign_aware: false }),
        weighted_avg_spread: formatRawAsNumeric({ raw: 0.01, unit: "pct", sign_aware: false }),
        weighted_avg_spread_duration: formatRawAsNumeric({ raw: 3, unit: "ratio", sign_aware: false }),
        spread_scenarios: [],
        migration_scenarios: [],
        concentration_by_rating: {
          dimension: "rating",
          hhi: formatRawAsNumeric({ raw: 0.1, unit: "pct", sign_aware: false }),
          top5_concentration: formatRawAsNumeric({ raw: 0.5, unit: "pct", sign_aware: false }),
          top_items: [
            {
              name: "AAA",
              weight: formatRawAsNumeric({ raw: 0.4, unit: "pct", sign_aware: false }),
              market_value: formatRawAsNumeric({ raw: 1, unit: "yuan", sign_aware: false }),
            },
          ],
        },
        oci_credit_exposure: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }),
        oci_spread_dv01: formatRawAsNumeric({ raw: 0, unit: "dv01", sign_aware: false }),
        oci_sensitivity_25bp: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }),
        warnings: [],
        computed_at: "2026-04-30T08:00:00Z",
      },
    });

    expect(view.portfolioStats.find((stat) => stat.id === "books")?.value).toBe("2 个");
    expect(view.portfolioStats.find((stat) => stat.id === "rating")?.value).toBe("AAA");
  });

  it("builds risk radar from cockpit risk items when at least three axes are available", () => {
    const radar = buildRiskRadarFromRiskItems(
      [
        { id: "dv01", label: "DV01", value: "8800", hint: "", level: 62, status: "supplemental", tone: "warning" },
        { id: "duration", label: "久期", value: "4.1", hint: "", level: 55, status: "supplemental", tone: "neutral" },
        { id: "issuer-top5", label: "Top5", value: "42%", hint: "", level: 48, status: "supplemental", tone: "warning" },
        { id: "credit-weight", label: "信用", value: "31%", hint: "", level: 40, status: "supplemental", tone: "neutral" },
      ],
      false,
    );

    expect(radar.usesMock).toBe(false);
    expect(radar.radar.pending).toBe(false);
    expect(radar.radar.dimensions).toEqual(["利率风险", "久期风险", "集中度风险", "信用风险"]);
    expect(radar.radar.values).toEqual([62, 55, 48, 40]);
  });

  it("marks risk radar pending in real mode when fewer than three risk axes are usable", () => {
    const radar = buildRiskRadarFromRiskItems(
      [{ id: "portfolio-risk-blocked", label: "风险摘要", value: "—", hint: "", level: 0, status: "blocked", tone: "warning" }],
      false,
    );

    expect(radar.usesMock).toBe(false);
    expect(radar.radar.pending).toBe(true);
    expect(radar.radar.dimensions).toEqual([]);
  });

  it("shows attribution note pending copy in real mode without judgment reasons", () => {
    const view = buildRealModeView({ metrics: [] });

    expect(view.attributionNote).toEqual(["归因说明待同步"]);
  });

  it("keeps product pnl trend pending in real mode without bond bucket monthly rows", () => {
    const view = buildRealModeView({ metrics: [] });

    expect(view.productPnl.pending).toBe(true);
    expect(view.productPnl.months).toEqual([]);
    expect(view.productPnl.series).toEqual([]);
  });

  it("builds product pnl trend from bond bucket monthly analysis in real mode", () => {
    const view = buildRealModeView({
      metrics: [],
      bondBucketMonthly: {
        year: 2026,
        as_of_date: "2026-04-30",
        business_key: null,
        dimension: "bond_bucket_monthly",
        period_start_date: "2026-01-01",
        period_end_date: "2026-04-30",
        source_tables: [],
        rows: [
          {
            dimension_key: "2026-04-30::rate_bond",
            dimension_label: "2026-04-30 利率债",
            interest_income: "0",
            fair_value_change: "0",
            capital_gain: "0",
            manual_adjustment: "0",
            total_pnl: "100000000",
            avg_balance: "0",
            current_balance: "0",
            annualized_yield_pct: null,
            ftp_rate_pct: "1.6",
            ftp_cost: "0",
            ftp_net_pnl: "0",
            ftp_net_annualized_yield_pct: null,
            asset_count: 1,
          },
        ],
      },
    });

    expect(view.productPnl.pending).toBe(false);
    expect(view.productPnl.series.find((item) => item.id === "rate")?.values).toEqual([1]);
  });

  it("uses same-day bond payloads to close portfolio stats without mock fallback", () => {
    const numeric = (raw: number, unit: Parameters<typeof formatRawAsNumeric>[0]["unit"] = "yuan") =>
      formatRawAsNumeric({ raw, unit, sign_aware: false });
    const view = buildRealModeView({
      reportDate: "2026-04-30",
      bondHeadline: {
        report_date: "2026-04-30",
        prev_report_date: null,
        kpis: {
          total_market_value: numeric(3708.1, "yi"),
          unrealized_pnl: numeric(29.71, "yi"),
          weighted_ytm: numeric(2.85, "pct"),
          weighted_duration: numeric(4.14, "ratio"),
          weighted_coupon: numeric(0.0285, "pct"),
          credit_spread_median: numeric(69.8, "bp"),
          total_dv01: numeric(10615.59, "dv01"),
          bond_count: 1256,
        },
        prev_kpis: null,
      },
      portfolioComparison: {
        report_date: "2026-04-30",
        items: [
          {
            portfolio_name: "组合A",
            total_market_value: numeric(100, "yi"),
            weighted_ytm: numeric(0.025, "pct"),
            weighted_duration: numeric(4, "ratio"),
            total_dv01: numeric(1, "dv01"),
            bond_count: 2,
          },
          {
            portfolio_name: "组合B",
            total_market_value: numeric(200, "yi"),
            weighted_ytm: numeric(0.026, "pct"),
            weighted_duration: numeric(4.2, "ratio"),
            total_dv01: numeric(2, "dv01"),
            bond_count: 3,
          },
        ],
      },
      creditSpreadMigration: {
        report_date: "2026-04-30",
        credit_bond_count: 1,
        credit_market_value: numeric(1, "yi"),
        credit_weight: numeric(0.3, "pct"),
        spread_dv01: numeric(1, "dv01"),
        weighted_avg_spread: numeric(69.8, "bp"),
        weighted_avg_spread_duration: numeric(3, "ratio"),
        spread_scenarios: [],
        migration_scenarios: [],
        concentration_by_rating: {
          dimension: "rating",
          hhi: numeric(0.1, "pct"),
          top5_concentration: numeric(0.5, "pct"),
          top_items: [{ name: "AAA", weight: numeric(0.4, "pct"), market_value: numeric(1, "yi") }],
        },
        oci_credit_exposure: numeric(0, "yuan"),
        oci_spread_dv01: numeric(0, "dv01"),
        oci_sensitivity_25bp: numeric(0, "yuan"),
        warnings: [],
        computed_at: "2026-04-30T08:00:00Z",
      },
    });

    expect(view.portfolioStats).toEqual([
      { id: "books", label: "组合数", value: "2 个" },
      { id: "positions", label: "持仓债券", value: "1,256 只" },
      { id: "coupon", label: "平均票面利率", value: "2.85%" },
      { id: "rating", label: "主导评级（Top1）", value: "AAA" },
    ]);
    expect(view.dataWarningMessages.join(" ")).not.toContain("资产分布缺少");
  });

  it("reports exact secondary portfolio fields when only those stats are pending", () => {
    const view = buildRealModeView({ metrics: [] });

    expect(view.dataWarningMessages).toContain("资产分布缺少 portfolio-comparison.items 字段");
    expect(view.dataWarningMessages).toContain(
      "资产分布缺少 credit-spread-migration.concentration_by_rating.top_items[0].name 字段",
    );
    expect(view.dataWarningMessages.join(" ")).not.toContain(
      "资产分布缺少 portfolio-comparison/credit-spread-migration 字段",
    );
  });

  it("labels dominant portfolio rating as Top1 instead of average", () => {
    const view = buildRealModeView({
      reportDate: "2026-04-30",
      creditSpreadMigration: {
        report_date: "2026-04-30",
        credit_bond_count: 1,
        credit_market_value: formatRawAsNumeric({ raw: 1, unit: "yuan", sign_aware: false }),
        credit_weight: formatRawAsNumeric({ raw: 0.3, unit: "pct", sign_aware: false }),
        spread_dv01: formatRawAsNumeric({ raw: 1, unit: "dv01", sign_aware: false }),
        weighted_avg_spread: formatRawAsNumeric({ raw: 0.01, unit: "pct", sign_aware: false }),
        weighted_avg_spread_duration: formatRawAsNumeric({ raw: 3, unit: "ratio", sign_aware: false }),
        spread_scenarios: [],
        migration_scenarios: [],
        concentration_by_rating: {
          dimension: "rating",
          hhi: formatRawAsNumeric({ raw: 0.1, unit: "pct", sign_aware: false }),
          top5_concentration: formatRawAsNumeric({ raw: 0.5, unit: "pct", sign_aware: false }),
          top_items: [
            {
              name: "AAA",
              weight: formatRawAsNumeric({ raw: 0.4, unit: "pct", sign_aware: false }),
              market_value: formatRawAsNumeric({ raw: 1, unit: "yuan", sign_aware: false }),
            },
          ],
        },
        oci_credit_exposure: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }),
        oci_spread_dv01: formatRawAsNumeric({ raw: 0, unit: "dv01", sign_aware: false }),
        oci_sensitivity_25bp: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }),
        warnings: [],
        computed_at: "2026-04-30T08:00:00Z",
      },
    });

    expect(view.portfolioStats.find((stat) => stat.id === "rating")?.label).toBe("主导评级（Top1）");
  });

  it("prefers pending decision items for todos over home alerts", () => {
    const view = buildRealModeView({
      metrics: [overviewMetric({ id: "aum", tone: "negative" })],
      decisionItems: [
        {
          decision_key: "decision-001",
          title: "复核久期超限",
          action_label: "进入处置",
          severity: "high",
          reason: "测试",
          source_section: "risk",
          rule_id: "r1",
          rule_version: "v1",
          latest_status: {
            decision_key: "decision-001",
            status: "pending",
            updated_at: "2026-04-30T08:00:00Z",
            updated_by: "tester",
            comment: "",
          },
        },
      ],
    });

    expect(view.todos[0]?.title).toBe("复核久期超限");
    expect(view.todos[0]?.status).toBe("待复核");
  });

  it("shows pending watchlist row in real mode when cockpit watch rows are empty", () => {
    const view = buildRealModeView({ metrics: [] });

    expect(view.watchlist).toHaveLength(1);
    expect(view.watchlist[0]?.label).toBe("观察清单");
    expect(view.watchlist[0]?.count).toBe("待同步");
  });

  it("uses each watch row's risk metric in the home watchlist instead of daily PnL", () => {
    const home = buildDashboardHomeModel({
      metrics: [],
      snapshotReportDate: "2026-04-30",
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const cockpit = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      isMockMode: false,
      dailyChanges: {
        report_date: "2026-04-30",
        periods: [
          {
            period: "day",
            bond_investments_change: formatRawAsNumeric({ raw: -512_000_000, unit: "yuan", sign_aware: true }),
            interbank_assets_change: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: true }),
            interbank_liabilities_change: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: true }),
            net_change: formatRawAsNumeric({ raw: -368_090_000, unit: "yuan", sign_aware: true }),
          },
        ],
      },
      bondHeadline: {
        report_date: "2026-04-30",
        prev_report_date: "2026-04-29",
        kpis: {
          total_market_value: formatRawAsNumeric({ raw: 370_810_000_000, unit: "yuan", sign_aware: false }),
          unrealized_pnl: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: true }),
          weighted_ytm: formatRawAsNumeric({ raw: 0.0257, unit: "pct", sign_aware: false }),
          weighted_duration: formatRawAsNumeric({ raw: 4.14, unit: "ratio", sign_aware: false }),
          weighted_coupon: formatRawAsNumeric({ raw: 0.0204, unit: "pct", sign_aware: false }),
          credit_spread_median: formatRawAsNumeric({ raw: 239, unit: "bp", sign_aware: false }),
          total_dv01: formatRawAsNumeric({ raw: 106_155_944.31, unit: "dv01", sign_aware: false }),
          bond_count: 1256,
        },
        prev_kpis: null,
      },
      portfolio: {
        report_date: "2026-04-30",
        total_market_value: formatRawAsNumeric({ raw: 370_810_000_000, unit: "yuan", sign_aware: false }),
        weighted_ytm: formatRawAsNumeric({ raw: 0.0257, unit: "pct", sign_aware: false }),
        weighted_duration: formatRawAsNumeric({ raw: 4.14, unit: "ratio", sign_aware: false }),
        weighted_coupon: formatRawAsNumeric({ raw: 0.0207, unit: "pct", sign_aware: false }),
        total_dv01: formatRawAsNumeric({ raw: 106_155_944.31, unit: "dv01", sign_aware: false }),
        bond_count: 1256,
        credit_weight: formatRawAsNumeric({ raw: 0.2925, unit: "pct", sign_aware: false }),
        issuer_hhi: formatRawAsNumeric({ raw: 0.0509, unit: "pct", sign_aware: false }),
        issuer_top5_weight: formatRawAsNumeric({ raw: 0.4135, unit: "pct", sign_aware: false }),
        by_asset_class: [],
        warnings: [],
        computed_at: "2026-04-30T09:15:00Z",
      },
    });

    const view = buildDashboardCockpitHomeViewModel({ home, cockpit, metrics: [] });

    expect(view.watchlist.find((item) => item.id === "portfolio-duration-watch")?.count).toBe("4.14");
    expect(view.watchlist.map((item) => item.count)).not.toContain("-3.68 亿");
  });

  it("keeps tiered risk alert labels in mock fallback", () => {
    const home = buildDashboardHomeModel({
      metrics: [],
      isSnapshotLoading: false,
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });
    const cockpit = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      isMockMode: false,
    });
    const view = buildDashboardCockpitHomeViewModel({
      home,
      cockpit,
      metrics: [],
      useMockFallback: true,
    });

    expect(view.riskReviewOnly).toBe(false);
    expect(view.riskAlertCounts.find((item) => item.id === "high")?.label).toBe("高风险预警");
    expect(view.usesMockRiskRadar).toBe(true);
    expect(view.usesStaticQuickDrilldown).toBe(true);
  });
});
