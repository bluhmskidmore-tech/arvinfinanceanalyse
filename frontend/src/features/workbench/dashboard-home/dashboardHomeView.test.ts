import { describe, expect, it } from "vitest";

import type { CoreMetricsResult, VerdictPayload } from "../../../api/contracts";
import { mapToHomeView, stripDisplayUnit } from "./dashboardHomeView";

const verdict: VerdictPayload = {
  conclusion: "test conclusion",
  tone: "warning",
  reasons: [{ label: "rates", value: "-1", detail: "rates moved higher", tone: "warning" }],
  suggestions: [{ text: "review duration", link: "/risk-tensor" }],
};

function numeric(raw: number | null, display: string, unit: "yuan" | "pct" | "bp" | "ratio" | "dv01" | "yi" = "yuan") {
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
    returnDecomposition: null,
    campisiFourEffects: null,
    yieldCurveTermStructure: null,
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

  it("builds macro briefing from release calendar and macro news events", () => {
    const view = mapToHomeView({
      ...baseRealInput,
      todayIsoDate: "2026-05-31",
      macroNewsEvents: [
        {
          event_key: "news-1",
          received_at: "2026-05-20T09:00:00+08:00",
          group_id: "news_cmd1",
          content_type: "sectornews",
          serial_id: 1,
          request_id: 1,
          error_code: 0,
          error_msg: "",
          topic_code: "S888005004API",
          item_index: 0,
          payload_text: "国际油价直线拉升",
          payload_json: null,
        },
        {
          event_key: "news-dup",
          received_at: "2026-05-20T08:00:00+08:00",
          group_id: "news_cmd1",
          content_type: "sectornews",
          serial_id: 2,
          request_id: 2,
          error_code: 0,
          error_msg: "",
          topic_code: "S888005004API",
          item_index: 1,
          payload_text: "国际油价直线拉升",
          payload_json: null,
        },
      ],
      macroNewsLoading: false,
      macroNewsError: false,
    } as Parameters<typeof mapToHomeView>[0]);

    expect(view.macroBriefing.releaseItems[0]?.date).toBe("2026-06-01");
    expect(view.macroBriefing.releaseItems[0]?.title).toContain("ISM");
    expect(view.macroBriefing.releaseItems[0]?.daysUntilLabel).toBe("明日");
    expect(view.macroBriefing.releaseItems[0]?.importanceLabel).toBe("高优先级");
    expect(view.macroBriefing.releaseWindowLabel).toBe("未来 45 天 · 6 项");
    expect(view.macroBriefing.newsItems).toHaveLength(1);
    expect(view.macroBriefing.newsItems[0]?.title).toBe("国际油价直线拉升");
    expect(view.macroBriefing.newsStale).toBe(true);
    expect(view.macroBriefing.newsSourceLabel).toBe("来源：Choice 宏观新闻");
    expect(view.macroBriefing.newsAsOfLabel).toBe("数据截至 05-20 09:00");
    expect(view.macroBriefing.newsStatusLabel).toBe("来源状态：偏旧");
    expect(view.macroBriefing.newsRefreshLabel).toBe("刷新：随页面查询自动更新");
    expect(view.macroBriefing.supplyItems[0]?.label).toBe("供给/招标：当前窗口无事件");
  });

  it("builds market context from formal attribution, curve and credit spread data", () => {
    const view = mapToHomeView({
      ...baseRealInput,
      todayIsoDate: "2026-05-31",
      marketPoints: [
        {
          series_id: "CA.US_GOV_10Y",
          series_name: "美国10年期国债收益率",
          trade_date: "2026-05-30",
          value_numeric: 4.45,
          unit: "%",
          source_version: "choice-test",
          vendor_version: "v1",
          vendor_name: "Choice",
          latest_change: 8,
          quality_flag: "ok",
        },
      ],
      campisiFourEffects: {
        report_date: "2026-04-30",
        period_start: "2026-04-01",
        period_end: "2026-04-30",
        num_days: 30,
        totals: {
          income_return: 179_000_000,
          treasury_effect: -3_000_000,
          spread_effect: 12_000_000,
          selection_effect: -5_000_000,
          total_return: 183_000_000,
          market_value_start: 10_000_000_000,
        },
        by_asset_class: [],
        by_bond: [],
        formal_closure: {
          basis: "pnl.bridge.total_actual_pnl",
          report_date: "2026-04-30",
          status: "closed",
          campisi_total_return: 183_000_000,
          formal_actual_pnl: 183_000_000,
          residual_to_formal_pnl: 0,
          residual_ratio: 0,
          message: "closed",
        },
        warnings: [],
      },
      returnDecomposition: {
        report_date: "2026-04-30",
        period_type: "MoM",
        period_start: "2026-04-01",
        period_end: "2026-04-30",
        carry: numeric(179_000_000, "+1.79 亿"),
        roll_down: numeric(8_000_000, "+0.08 亿"),
        rate_effect: numeric(-3_000_000, "-0.03 亿"),
        spread_effect: numeric(12_000_000, "+0.12 亿"),
        trading: numeric(-5_000_000, "-0.05 亿"),
        fx_effect: numeric(0, "0.00 亿"),
        convexity_effect: numeric(0, "0.00 亿"),
        explained_pnl: numeric(191_000_000, "+1.91 亿"),
        explained_pnl_accounting: numeric(191_000_000, "+1.91 亿"),
        explained_pnl_economic: numeric(191_000_000, "+1.91 亿"),
        oci_reserve_impact: numeric(0, "0.00 亿"),
        actual_pnl: numeric(190_000_000, "+1.90 亿"),
        recon_error: numeric(-1_000_000, "-0.01 亿"),
        recon_error_pct: numeric(-0.0005, "-0.05%", "pct"),
        by_asset_class: [],
        by_accounting_class: [],
        bond_details: [],
        bond_count: 12,
        total_market_value: numeric(10_000_000_000, "100.00 亿"),
        warnings: [],
        computed_at: "2026-04-30T16:00:00Z",
      },
      yieldCurveTermStructure: {
        report_date: "2026-04-30",
        curves: [
          {
            curve_type: "cdb",
            trade_date_requested: "2026-04-30",
            trade_date_resolved: "2026-04-30",
            points: [
              { tenor: "1Y", yield_pct: numeric(0.018, "1.80%", "pct"), delta_bp_prev: numeric(1.2, "+1.20 bp", "bp") },
              { tenor: "3Y", yield_pct: numeric(0.021, "2.10%", "pct"), delta_bp_prev: numeric(2.1, "+2.10 bp", "bp") },
              { tenor: "5Y", yield_pct: numeric(0.023, "2.30%", "pct"), delta_bp_prev: numeric(2.5, "+2.50 bp", "bp") },
              { tenor: "10Y", yield_pct: numeric(0.026, "2.60%", "pct"), delta_bp_prev: numeric(3.2, "+3.20 bp", "bp") },
            ],
            source_version: "sv_cdb_curve",
            rule_version: "rv_yield_curve",
            vendor_name: "official",
            vendor_version: "v1",
          },
        ],
        warnings: [],
        computed_at: "2026-04-30T16:00:00Z",
      },
      creditSpreadMigration: {
        report_date: "2026-04-30",
        credit_bond_count: 8,
        credit_market_value: numeric(2_000_000_000, "20.00 亿"),
        credit_weight: numeric(0.2, "20.00%", "ratio"),
        rating_aa_and_below_weight: numeric(0.18, "18.00%", "ratio"),
        spread_dv01: numeric(120_000, "120,000.00", "dv01"),
        weighted_avg_spread: numeric(86, "86.00 bp", "bp"),
        weighted_avg_spread_duration: numeric(3.8, "3.80", "ratio"),
        spread_scenarios: [
          {
            scenario_name: "+25bp",
            spread_change_bp: numeric(25, "+25.00 bp", "bp"),
            pnl_impact: numeric(-3_000_000, "-0.03 亿"),
            oci_impact: numeric(-2_000_000, "-0.02 亿"),
            tpl_impact: numeric(-1_000_000, "-0.01 亿"),
          },
        ],
        migration_scenarios: [],
        oci_credit_exposure: numeric(1_000_000_000, "10.00 亿"),
        oci_spread_dv01: numeric(80_000, "80,000.00", "dv01"),
        oci_sensitivity_25bp: numeric(-2_000_000, "-0.02 亿"),
        warnings: [],
        computed_at: "2026-04-30T16:00:00Z",
      },
      macroNewsLoading: false,
      macroNewsError: false,
    } as Parameters<typeof mapToHomeView>[0]);

    expect(view.marketContext.contextBlocks.map((block) => block.label)).toEqual([
      "PnL归因",
      "曲线/利率",
      "信用利差",
    ]);
    expect(view.marketContext.contextBlocks[0]?.title).toContain("最大贡献 Carry/Income +1.79 亿");
    expect(view.marketContext.contextBlocks[0]?.detail).toContain("最大拖累 个券选择/残差 -0.05 亿");
    expect(view.marketContext.contextBlocks[1]?.title).toContain("CDB 10Y 2.60%");
    expect(view.marketContext.contextBlocks[2]?.detail).toContain("AA及以下 18.00%");
    expect(view.marketContext.aiSummary).toEqual(
      expect.arrayContaining([
        expect.stringContaining("PnL归因"),
        expect.stringContaining("CDB 10Y"),
        expect.stringContaining("信用利差"),
      ]),
    );
    expect(view.marketContext.sourceLabel).toBe("来源：收益归因 / yield_curve_term_structure / credit_spread_migration");
    expect(view.marketContext.asOfLabel).toBe("数据截至 2026-04-30");
    expect(view.marketContext.statusLabel).toBe("来源状态：正式链路");
    expect(view.decisionRail.maxContributionLabel).toBe("Carry/Income");
    expect(view.decisionRail.maxContributionValue).toBe("+1.79 亿");
    expect(view.decisionRail.maxDragLabel).toBe("个券选择/残差");
    expect(view.decisionRail.maxDragValue).toBe("-0.05 亿");
  });

  it("names missing credit spread context fields instead of showing generic dashes", () => {
    const view = mapToHomeView({
      ...baseRealInput,
      todayIsoDate: "2026-05-31",
      creditSpreadMigration: {
        report_date: "2026-04-30",
        credit_bond_count: 1065,
        credit_market_value: numeric(103_053_790_790, "1,030.54 亿"),
        credit_weight: numeric(null, "—", "ratio"),
        spread_dv01: numeric(null, "—", "dv01"),
        weighted_avg_spread: numeric(null, "—", "bp"),
        weighted_avg_spread_duration: numeric(null, "—", "ratio"),
        spread_scenarios: [],
        migration_scenarios: [],
        oci_credit_exposure: numeric(43_823_772_942, "438.24 亿"),
        oci_spread_dv01: numeric(null, "—", "dv01"),
        oci_sensitivity_25bp: numeric(null, "—"),
        warnings: ["Spread level input unavailable; weighted_avg_spread remains 0 (curves or inputs incomplete)"],
        computed_at: "2026-05-31T13:21:55Z",
      },
      macroNewsLoading: false,
      macroNewsError: false,
    } as Parameters<typeof mapToHomeView>[0]);

    const creditBlock = view.marketContext.contextBlocks.find((block) => block.id === "credit");

    expect(creditBlock?.title).toBe("加权平均利差 缺加权利差");
    expect(creditBlock?.detail).toContain("spread DV01 缺spread_dv01");
    expect(creditBlock?.detail).toContain("AA及以下 缺评级分布");
    expect(creditBlock?.detail).toContain("25bp 缺25bp情景");
    expect(creditBlock?.foot).toContain("占比 缺信用债占比");
  });

  it("maps ready income trend into portfolio benchmark and excess lines", () => {
    const view = mapToHomeView({
      ...baseRealInput,
      incomeTrend: {
        report_date: "2026-04-30",
        window: 2,
        source_status: "ready",
        missing_components: [],
        warnings: [],
        points: [
          {
            date: "2026-03-31",
            portfolio_pnl: numeric(120_000_000, "+1.20 亿"),
            benchmark_pnl: numeric(80_000_000, "+0.80 亿"),
            excess_pnl: numeric(40_000_000, "+0.40 亿"),
            basis: "product_category_pnl_monthly",
            source_status: "ready",
          },
          {
            date: "2026-04-30",
            portfolio_pnl: numeric(90_000_000, "+0.90 亿"),
            benchmark_pnl: numeric(60_000_000, "+0.60 亿"),
            excess_pnl: numeric(30_000_000, "+0.30 亿"),
            basis: "product_category_pnl_monthly",
            source_status: "ready",
          },
        ],
      },
    } as Parameters<typeof mapToHomeView>[0]);

    expect(view.incomeTrendState).toEqual({ kind: "ready", label: "已接入" });
    expect(view.incomeTrend.at(-1)).toMatchObject({
      portfolioPnl: "+0.90 亿",
      benchmarkPnl: "+0.60 亿",
      excessPnl: "+0.30 亿",
      portfolioRaw: 90_000_000,
      benchmarkRaw: 60_000_000,
      excessRaw: 30_000_000,
    });
  });

  it("maps income trend CDB benchmark gaps into explicit labels", () => {
    const view = mapToHomeView({
      ...baseRealInput,
      incomeTrend: {
        report_date: "2026-04-30",
        window: 2,
        source_status: "partial",
        missing_components: ["benchmark_pnl", "excess_pnl"],
        warnings: [
          "2026-04-30 CDB_INDEX: YIELD_CURVE_LATEST_FALLBACK: Using latest available cdb curve from trade_date=2026-03-31 for requested_trade_date=2026-04-01.",
        ],
        points: [
          {
            date: "2026-04-30",
            portfolio_pnl: numeric(90_000_000, "+0.90 亿"),
            benchmark_pnl: numeric(null, "-", "yuan"),
            excess_pnl: numeric(null, "-", "yuan"),
            basis: "product_category_pnl_monthly",
            source_status: "partial",
          },
        ],
      },
    } as Parameters<typeof mapToHomeView>[0]);

    expect(view.incomeTrendState).toEqual({ kind: "partial", label: "缺 CDB_INDEX 可核验曲线" });
    expect(view.incomeTrend[0]?.benchmarkPnl).toBe("缺CDB_INDEX");
    expect(view.incomeTrend[0]?.excessPnl).toBe("缺CDB_INDEX");
    expect(view.incomeTrend[0]?.benchmarkRaw).toBeNull();
    expect(view.incomeTrend[0]?.excessRaw).toBeNull();
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
