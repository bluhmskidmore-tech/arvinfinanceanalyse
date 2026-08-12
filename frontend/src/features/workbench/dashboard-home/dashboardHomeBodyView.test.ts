import { describe, expect, it } from "vitest";

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
