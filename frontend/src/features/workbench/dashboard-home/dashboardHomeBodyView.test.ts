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
