import { describe, expect, it } from "vitest";

import type { CoreMetricsResult } from "../../../api/contracts";
import type { DashboardOverviewMetricVM } from "../../executive-dashboard/adapters/executiveDashboardAdapter";
import { formatRawAsNumeric } from "../../../utils/format";
import { buildDashboardCockpitModel } from "./dashboardCockpitModel";
import { buildDashboardHomeModel } from "./dashboardHomeModel";
import { buildDashboardCockpitHomeViewModel, buildDashboardCockpitHeaderStatus } from "./dashboardCockpitHomeModel";

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
    expect(view.improvementNotes).toHaveLength(5);
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
          value: { raw: 4_567_890_000_000, unit: "yuan", display: "45678.90 亿", precision: 2, sign_aware: false },
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
});
