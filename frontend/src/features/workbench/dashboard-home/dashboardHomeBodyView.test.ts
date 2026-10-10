import { describe, expect, it } from "vitest";
import type { ResultMeta } from "../../../api/contracts";

import {
  mapToHomeBodyView,
  percentageDisplayRaw,
  type MapToHomeBodyViewInput,
} from "./dashboardHomeBodyView";

describe("percentageDisplayRaw", () => {
  it("converts contract pct raw (decimal ratio) to 0-100 percent with a fixed x100", () => {
    // 后端 percentage 字段为 unit="pct" 的 Numeric，raw 恒为小数比率（0.6 → 60%）。
    expect(percentageDisplayRaw(0.6)).toBeCloseTo(60);
    expect(percentageDisplayRaw(0.0486)).toBeCloseTo(4.86);
    // 100% 边界（raw=1）不再被启发式误判。
    expect(percentageDisplayRaw(1)).toBeCloseTo(100);
    expect(percentageDisplayRaw(0)).toBe(0);
  });

  it("returns null for missing or non-finite raw", () => {
    expect(percentageDisplayRaw(null)).toBeNull();
    expect(percentageDisplayRaw(undefined)).toBeNull();
    expect(percentageDisplayRaw(Number.NaN)).toBeNull();
  });
});

describe("mapToHomeBodyView home-summary trust", () => {
  const reportDate = "2026-06-30";
  const meta: ResultMeta = {
    trace_id: "synthetic-home-summary", basis: "analytical", result_kind: "synthetic",
    formal_use_allowed: false, source_version: "synthetic", vendor_version: "synthetic",
    rule_version: "synthetic", cache_version: "synthetic", quality_flag: "ok",
    vendor_status: "ok", fallback_mode: "none", scenario_flag: false,
    as_of_date: reportDate, resolved_report_date: reportDate, generated_at: reportDate,
  };
  const metric = (raw: number, unit: "yuan" | "pct" | "ratio" = "yuan") => ({
    raw, unit, display: String(raw), precision: 2, sign_aware: false,
  });
  const mapSummary = (sourceMeta: ResultMeta | null = meta, zeroRisk = false) => mapToHomeBodyView({
    reportDate, useMockFallback: false, homeSummaryMeta: sourceMeta,
    assetStructure: {
      report_date: reportDate, group_by: "asset_type", total_market_value: metric(100),
      items: [{ category: "合成资产", total_market_value: metric(100), percentage: metric(1, "pct"), bond_count: 1 }],
    },
    ratingStructure: {
      report_date: reportDate, group_by: "asset_rating", total_market_value: metric(100),
      items: [{ category: "合成评级", total_market_value: metric(100), percentage: metric(1, "pct"), bond_count: 1 }],
    },
    maturityStructure: {
      report_date: reportDate, total_market_value: metric(100),
      items: [{ maturity_bucket: "合成期限", total_market_value: metric(100), percentage: metric(1, "pct"), bond_count: 1 }],
    },
    industryDistribution: {
      report_date: reportDate, total_market_value: metric(100),
      items: [{ industry_name: "合成行业", total_market_value: metric(100), percentage: metric(1, "pct"), bond_count: 1 }],
    },
    yieldDistribution: {
      report_date: reportDate, weighted_ytm: metric(0.02, "pct"),
      items: [{ yield_bucket: "合成收益档", total_market_value: metric(100), bond_count: 1 }],
    },
    portfolioComparison: {
      report_date: reportDate,
      items: [{ portfolio_name: "合成组合", total_market_value: metric(100), weighted_ytm: metric(0.02, "pct"),
        weighted_duration: metric(2, "ratio"), total_dv01: metric(1), bond_count: 1 }],
    },
    riskIndicators: {
      report_date: reportDate, total_market_value: metric(zeroRisk ? 0 : 100), total_dv01: metric(zeroRisk ? 0 : 1),
      weighted_duration: metric(zeroRisk ? 0 : 2, "ratio"), credit_ratio: metric(zeroRisk ? 0 : 0.5, "ratio"),
      weighted_convexity: metric(zeroRisk ? 0 : 3, "ratio"), total_spread_dv01: metric(zeroRisk ? 0 : 1),
      reinvestment_ratio_1y: metric(zeroRisk ? 0 : 0.1, "ratio"),
    },
  } as MapToHomeBodyViewInput);
  const distributions = (view: ReturnType<typeof mapSummary>) => [
    view.assetDistribution, view.ratingDistribution, view.maturityDistribution,
    view.industryDistribution, view.yieldDistribution, view.portfolioComparison,
  ];

  it("keeps same-date warning data usable and explains the warning in Chinese", () => {
    const view = mapSummary({ ...meta, quality_flag: "warning" });
    expect(distributions(view).every((rows) => rows.length === 1)).toBe(true);
    expect(view.riskExposureMetrics).toHaveLength(7);
    expect(view.assetDistributionState).toMatchObject({ kind: "partial", label: "数据质量需复核" });
    expect(view.riskExposureState).toMatchObject({ kind: "partial", label: "数据质量需复核" });
  });

  it.each([0, -1])("withholds zero-filled risk and distributions when evidence_rows is %s", (evidenceRows) => {
    const view = mapSummary({ ...meta, quality_flag: "warning", evidence_rows: evidenceRows }, true);
    expect(view.riskExposureMetrics).toHaveLength(0);
    expect(distributions(view).every((rows) => rows.length === 0)).toBe(true);
    expect(view.assetDistributionState.kind).toBe("empty");
    expect(view.riskExposureState).toMatchObject({ kind: "empty", label: "暂无持仓证据，未展示" });
  });

  it.each([
    ["missing metadata", null],
    ["quality error", { ...meta, quality_flag: "error" }],
    ["missing data", { ...meta, quality_flag: "missing" }],
    ["unavailable vendor", { ...meta, vendor_status: "vendor_unavailable" }],
    ["missing quality flag", { ...meta, quality_flag: undefined }],
    ["missing vendor status", { ...meta, vendor_status: undefined }],
    ["missing fallback mode", { ...meta, fallback_mode: undefined }],
  ])("withholds distributions and risk values for %s", (_name, sourceMeta) => {
    const view = mapSummary(sourceMeta as ResultMeta | null);
    expect(distributions(view).every((rows) => rows.length === 0)).toBe(true);
    expect(view.riskExposureMetrics).toHaveLength(0);
    expect(view.assetDistributionState.kind).toBe("error");
    expect(view.riskExposureState.kind).toBe("error");
  });

  it.each(["as_of_date", "resolved_report_date", "fallback_date"] as const)(
    "withholds same-date payloads when metadata %s conflicts with the snapshot",
    (field) => {
      const view = mapSummary({ ...meta, [field]: "2026-05-31" });
      expect(distributions(view).every((rows) => rows.length === 0)).toBe(true);
      expect(view.riskExposureMetrics).toHaveLength(0);
      expect(view.assetDistributionState.label).toContain("2026-05-31");
      expect(view.assetDistributionState.label).toContain("未展示");
    },
  );

  it("allows disclosed stale and fallback data only when all effective dates agree", () => {
    const view = mapSummary({ ...meta, quality_flag: "stale", vendor_status: "vendor_stale",
      fallback_mode: "latest_snapshot", fallback_date: reportDate, requested_report_date: "2026-07-31" });
    expect(distributions(view).every((rows) => rows.length === 1)).toBe(true);
    expect(view.assetDistributionState.kind).toBe("stale");
    expect(view.assetDistributionState.label).toContain("使用回退数据");
    expect(view.assetDistributionState.label).toContain("数据偏旧");
  });
});

describe("mapToHomeBodyView portfolio profile", () => {
  it("maps the governed overview AUM metric without substituting other profile metrics", () => {
    const view = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: false,
      overviewMetrics: [
        {
          id: "aum",
          label: "债券资产规模（zqtz）",
          caliberLabel: "债券资产口径",
          value: {
            raw: 373_429_443_608.13525,
            unit: "yuan",
            display: "3,734.29 亿",
            precision: 2,
            sign_aware: false,
          },
          delta: {
            raw: -0.029862688708304174,
            unit: "pct",
            display: "-2.99%",
            precision: 2,
            sign_aware: true,
          },
          tone: "positive",
          detail: "来自正式债券资产余额日表。",
          history: null,
        },
      ],
      attribution: null,
      creditSpreadMigration: null,
      returnDecomposition: null,
      campisiFourEffects: null,
      yieldCurveTermStructure: null,
      marketPoints: null,
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
      calendarStartDate: "2026-07-31",
      calendarEndDate: "2026-09-14",
      todayIsoDate: "2026-07-31",
    } as MapToHomeBodyViewInput);

    expect(view.portfolioAum).toBe("3,734.29 亿");
  });
});

describe("mapToHomeBodyView research contracts", () => {
  it("keeps only strict publication dates and absolute http links", () => {
    const view = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: false,
      researchReportsLoading: false,
      researchReportsError: false,
      researchReports: {
        report_date: "2026-06-30",
        source_status: "ready",
        warnings: [],
        items: [
          {
            id: "valid",
            title: "利率债周报",
            category: "fixed_income",
            published_at: " 2026-06-30T09:00:00+08:00 ",
            link: " https://example.com/rates.pdf ",
            source: "research",
            institution: "研究机构",
            source_status: "ready",
          },
          {
            id: "unsafe",
            title: "信用债日期待核验",
            category: "fixed_income",
            published_at: "2026-02-30",
            link: "javascript:alert(1)",
            source: "research",
            institution: "研究机构",
            source_status: "ready",
          },
          {
            id: "relative",
            title: "宏观债市展望",
            category: "macro",
            published_at: "not-a-date",
            link: "/reports/macro",
            source: "research",
            institution: "研究机构",
            source_status: "ready",
          },
          {
            id: "data-url",
            title: "债市数据链接待核验",
            category: "fixed_income",
            published_at: "2026-06-29",
            link: "data:text/html,unsafe",
            source: "research",
            institution: "研究机构",
            source_status: "ready",
          },
        ],
      },
    } as unknown as MapToHomeBodyViewInput);

    expect(view.researchReports).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "valid",
          publishedAt: "2026-06-30",
          link: "https://example.com/rates.pdf",
        }),
        expect.objectContaining({ id: "unsafe", publishedAt: "—", link: null }),
        expect.objectContaining({ id: "relative", publishedAt: "—", link: null }),
        expect.objectContaining({ id: "data-url", publishedAt: "2026-06-29", link: null }),
      ]),
    );
  });
});

const numeric = (raw: number) => ({
  raw,
  unit: "yuan",
  display: String(raw),
  precision: 2,
  sign_aware: true,
});

describe("mapToHomeBodyView income trend missing benchmark", () => {
  it("renders em dash cells and carries the full gap reason for titles", () => {
    const view = mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: false,
      incomeTrendLoading: false,
      incomeTrendError: false,
      incomeTrend: {
        report_date: "2026-06-30",
        source_status: "partial",
        warnings: ["CDB_INDEX yield curve missing"],
        missing_components: ["benchmark_pnl", "excess_pnl"],
        points: [
          {
            date: "2026-06-30",
            portfolio_pnl: numeric(90_000_000),
            benchmark_pnl: null,
            excess_pnl: null,
          },
        ],
      },
    } as unknown as MapToHomeBodyViewInput);

    const row = view.incomeTrend[0]!;
    // 缺值单元格用 em dash（§6），证据码不进窄列。
    expect(row.benchmarkPnl).toBe("—");
    expect(row.excessPnl).toBe("—");
    expect(row.missingReason).toBe("缺 CDB_INDEX 曲线");
    expect(view.incomeTrendState.kind).toBe("partial");
    expect(view.incomeTrendState.label).toBe("缺 CDB_INDEX 曲线");
  });
});

describe("mapToHomeBodyView krd buckets", () => {
  const mapKrd = (payload: unknown) =>
    mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: false,
      krdCurveRisk: payload,
    } as unknown as MapToHomeBodyViewInput);

  it("keeps every bucket, sorts by tenor and converts yuan/bp to wan/bp", () => {
    const view = mapKrd({
      report_date: "2026-06-30",
      krd_buckets: [
        { tenor: "30Y", dv01: numeric(9_000_000) },
        { tenor: "6M", dv01: numeric(120_000) },
        { tenor: "10Y", dv01: numeric(18_000_000) },
        { tenor: "1Y", dv01: numeric(null as unknown as number) },
      ],
    });

    expect(view.krdState.kind).toBe("ready");
    expect(view.krdBuckets.map((row) => row.tenor)).toEqual(["6M", "1Y", "10Y", "30Y"]);
    // 元/bp ÷ 1e4 → 万元/bp，两位小数。
    expect(view.krdBuckets.at(-1)?.dv01Display).toBe("900.00");
    expect(view.krdBuckets[2]?.dv01Display).toBe("1,800.00");
    // 条宽相对最大桶（10Y），无数值的桶不给条宽。
    expect(view.krdBuckets[2]?.barWidthPct).toBeCloseTo(100);
    expect(view.krdBuckets.at(-1)?.barWidthPct).toBeCloseTo(50);
    expect(view.krdBuckets[1]?.barWidthPct).toBeNull();
    expect(view.krdBuckets[1]?.dv01Display).toBe("—");
  });

  it("marks the section stale when the payload report date mismatches", () => {
    const view = mapKrd({
      report_date: "2026-05-31",
      krd_buckets: [{ tenor: "10Y", dv01: numeric(18_000_000) }],
    });

    expect(view.krdState.kind).not.toBe("ready");
    expect(view.krdBuckets).toHaveLength(0);
  });
});

describe("mapToHomeBodyView decision item preview", () => {
  const mapDecisions = (rows: unknown[]) =>
    mapToHomeBodyView({
      reportDate: "2026-06-30",
      useMockFallback: false,
      decisionItems: { report_date: "2026-07-31", rows },
    } as unknown as MapToHomeBodyViewInput);

  it("keeps pending rows only, sorts by severity then key, and caps at two", () => {
    const view = mapDecisions([
      {
        decision_key: "b-medium",
        title: "关注集中度",
        severity: "medium",
        latest_status: { status: "pending" },
      },
      {
        decision_key: "resolved-high",
        title: "已处理事项",
        severity: "high",
        latest_status: { status: "resolved" },
      },
      {
        decision_key: "a-medium",
        title: "复核期限缺口",
        severity: "medium",
        latest_status: { status: "pending" },
      },
      {
        decision_key: "c-high",
        title: "高优先事项",
        severity: "high",
        latest_status: { status: "pending" },
      },
    ]);

    expect(view.decisionItemsState.kind).toBe("ready");
    expect(view.decisionItemsPreview.map((row) => row.id)).toEqual(["c-high", "a-medium"]);
    expect(view.decisionItemsReportDate).toBe("2026-07-31");
  });

  it("reports an honest empty state when nothing is pending", () => {
    const view = mapDecisions([
      {
        decision_key: "done",
        title: "已处理",
        severity: "high",
        latest_status: { status: "resolved" },
      },
    ]);

    expect(view.decisionItemsPreview).toHaveLength(0);
    expect(view.decisionItemsState.kind).toBe("ready");
    expect(view.decisionItemsState.label).toBe("暂无待处理事项");
  });
});
