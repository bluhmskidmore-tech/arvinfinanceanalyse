import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import { createDeferredApiClient } from "../api/clientContext";
import type {
  ApiEnvelope,
  BondDashboardBundlePayload,
  BondDashboardBundleSectionId,
  ResultMeta,
} from "../api/contracts";

const resultMeta: ResultMeta = {
  trace_id: "tr_bond_dashboard_bundle",
  basis: "analytical",
  result_kind: "bond_dashboard.bundle",
  formal_use_allowed: false,
  source_version: "sv_test",
  vendor_version: "vv_test",
  rule_version: "rv_test",
  cache_version: "cv_test",
  quality_flag: "ok",
  vendor_status: "ok",
  fallback_mode: "none",
  scenario_flag: false,
  generated_at: "2026-05-31T00:00:00Z",
};

function expectHealthyAnalyticalMockMeta(
  envelope: ApiEnvelope<unknown> | undefined,
  reportDate: string,
): void {
  expect(envelope).toBeDefined();
  expect(envelope?.data_source).toBe("bond_analytics_facts");
  expect(envelope?.result_meta).toMatchObject({
    basis: "analytical",
    formal_use_allowed: false,
    cache_key: null,
    quality_flag: "ok",
    requested_report_date: reportDate,
    resolved_report_date: reportDate,
    as_of_date: reportDate,
    date_basis: "bond_dashboard_report_date",
    fallback_date: null,
    filters_applied: { report_date: reportDate },
    tables_used: ["fact_formal_bond_analytics_daily"],
    next_drill: [],
    source_surface: "mock",
  });
  expect(envelope?.result_meta).toHaveProperty("amount_currency_basis", null);
  expect(envelope?.result_meta).toHaveProperty("amount_currency_basis_note", null);
  expect(envelope?.result_meta.evidence_rows).toBeGreaterThan(0);
}

describe("BondDashboard bundle client", () => {
  it("calls the real bundle endpoint with sections, report_date, and industry_top_n", async () => {
    const sections: BondDashboardBundleSectionId[] = [
      "headline-kpis",
      "industry-distribution",
    ];
    const responseBody: ApiEnvelope<BondDashboardBundlePayload> = {
      data_source: "bond_analytics_facts",
      result_meta: resultMeta,
      result: {
        report_date: "2026-04-30",
        requested_sections: sections,
        sections: {},
      },
    };
    const fetchImpl = vi.fn(async (_input: Parameters<typeof fetch>[0], _init?: Parameters<typeof fetch>[1]) =>
      new Response(JSON.stringify(responseBody), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = createApiClient({
      mode: "real",
      baseUrl: "https://moss.test",
      fetchImpl: fetchImpl as typeof fetch,
    });

    const envelope = await client.fetchBondDashboardBundle("2026-04-30", sections, {
      industryTopN: 12,
      analyticsTopN: 5,
      dv01TopN: 1,
      dv01ShockBps: "1",
      dv01AccountingClass: "all",
      curveTypes: "treasury,cdb",
    });

    expect(envelope).toEqual(responseBody);
    const url = new URL(String(fetchImpl.mock.calls[0]?.[0]));
    expect(url.pathname).toBe("/api/bond-dashboard/bundle");
    expect(url.searchParams.get("sections")).toBe("headline-kpis,industry-distribution");
    expect(url.searchParams.get("report_date")).toBe("2026-04-30");
    expect(url.searchParams.get("industry_top_n")).toBe("12");
    expect(url.searchParams.get("analytics_top_n")).toBe("5");
    expect(url.searchParams.get("dv01_top_n")).toBe("1");
    expect(url.searchParams.get("dv01_shock_bps")).toBe("1");
    expect(url.searchParams.get("dv01_accounting_class")).toBe("all");
    expect(url.searchParams.get("curve_types")).toBe("treasury,cdb");
  });

  it("assembles mock bundle sections from the existing single-section mock envelopes", async () => {
    const client = createApiClient({ mode: "mock" });
    const reportDate = "2026-03-31";
    const sections: BondDashboardBundleSectionId[] = [
      "headline-kpis",
      "asset-structure-rating",
      "maturity-structure",
      "risk-indicators",
      "business-type-metrics",
      "top-holdings",
      "portfolio-headlines",
      "dv01-risk-ac",
      "yield-curve-term-structure",
    ];

    const bundle = await client.fetchBondDashboardBundle(reportDate, sections, {
      industryTopN: 10,
      analyticsTopN: 5,
      dv01TopN: 1,
      dv01ShockBps: "1",
      curveTypes: "treasury,cdb",
    });

    expect(bundle.data_source).toBe("bond_analytics_facts");
    expect(bundle.result.report_date).toBe(reportDate);
    expect(bundle.result.requested_sections).toEqual(sections);
    for (const section of [
      "headline-kpis",
      "asset-structure-rating",
      "maturity-structure",
      "risk-indicators",
      "business-type-metrics",
    ] as const) {
      expect(bundle.result.sections[section]?.result_meta).toMatchObject({
        basis: "analytical",
        formal_use_allowed: false,
        quality_flag: "ok",
        requested_report_date: reportDate,
        resolved_report_date: reportDate,
        as_of_date: reportDate,
        date_basis: "bond_dashboard_report_date",
      });
    }
    expect(bundle.result.sections["headline-kpis"]).toEqual(
      await client.getBondDashboardHeadlineKpis(reportDate),
    );
    expect(bundle.result.sections["asset-structure-rating"]).toEqual(
      await client.getBondDashboardAssetStructure(reportDate, "rating"),
    );
    expect(bundle.result.sections["maturity-structure"]).toEqual(
      await client.getBondDashboardMaturityStructure(reportDate),
    );
    expect(bundle.result.sections["risk-indicators"]).toEqual(
      await client.getBondDashboardRiskIndicators(reportDate),
    );
    expect(bundle.result.sections["business-type-metrics"]).toEqual(
      await client.getBondBusinessTypeMetrics({ reportDate }),
    );
    expect(bundle.result.sections["top-holdings"]).toEqual(
      await client.getBondAnalyticsTopHoldings(reportDate, 5),
    );
    expect(bundle.result.sections["portfolio-headlines"]).toEqual(
      await client.getBondAnalyticsPortfolioHeadlines(reportDate),
    );
    expect(bundle.result.sections["dv01-risk-ac"]).toEqual(
      await client.getBondAnalyticsDv01Risk(reportDate, {
        accountingClass: "AC",
        topN: 1,
        shockBps: "1",
      }),
    );
    const bundledCurve = bundle.result.sections["yield-curve-term-structure"];
    const singleCurve = await client.getBondAnalyticsYieldCurveTermStructure(reportDate, {
      curveTypes: "treasury,cdb",
    });
    expect(bundledCurve?.result_meta.result_kind).toBe(singleCurve.result_meta.result_kind);
    expect(bundledCurve?.result.report_date).toBe(singleCurve.result.report_date);
    expect(bundledCurve?.result.curves).toEqual(singleCurve.result.curves);
    expect(bundledCurve?.result.warnings).toEqual(singleCurve.result.warnings);
    expect(bundle.result.failed_sections).toEqual([]);
    expect(bundle.result.section_statuses?.["yield-curve-term-structure"]?.status).toBe("ok");

    const maturity = bundle.result.sections["maturity-structure"]?.result;
    expect(maturity?.total_market_value.raw).toBe(328_709_000_000);
    expect(maturity?.items[0]?.bond_count).toBe(8);
    expect(maturity?.items[0]?.percentage?.raw).toBeCloseTo(
      2_100_000_000 / 328_709_000_000,
    );

    expect(
      bundle.result.sections["risk-indicators"]?.result.weighted_convexity_coverage_ratio?.raw,
    ).toBe(0.91);
    const businessItem = bundle.result.sections["business-type-metrics"]?.result.items[0];
    expect(businessItem?.weighted_avg_ytm_coverage_ratio?.raw).toBe(0.98);
    expect(businessItem?.weighted_avg_duration_coverage_ratio?.raw).toBe(0.97);
  });

  it("keeps mock core sections shape- and semantics-compatible with the live bundle", async () => {
    const client = createApiClient({ mode: "mock" });
    const reportDate = "2026-03-31";
    const sections: BondDashboardBundleSectionId[] = [
      "dates",
      "headline-kpis",
      "home-summary",
      "asset-structure",
      "asset-structure-rating",
      "asset-structure-portfolio-name",
      "asset-structure-tenor-bucket",
      "yield-distribution",
      "portfolio-comparison",
      "spread-analysis",
      "maturity-structure",
      "industry-distribution",
      "risk-indicators",
      "business-type-metrics",
    ];

    const bundle = await client.fetchBondDashboardBundle(reportDate, sections, {
      industryTopN: 2,
    });

    expect(bundle.data_source).toBe("bond_analytics_facts");
    expect(bundle.result.report_date).toBe(reportDate);
    expect(bundle.result.requested_sections).toEqual(sections);
    expect(bundle.result.failed_sections).toEqual([]);
    expect(bundle.result_meta).toMatchObject({
      basis: "analytical",
      formal_use_allowed: false,
      cache_key: null,
      quality_flag: "ok",
      requested_report_date: reportDate,
      resolved_report_date: reportDate,
      as_of_date: reportDate,
      date_basis: "bond_dashboard_report_date",
      fallback_date: null,
      filters_applied: {
        report_date: reportDate,
        sections,
        industry_top_n: 2,
      },
      tables_used: ["fact_formal_bond_analytics_daily"],
      next_drill: [],
      source_surface: "mock",
    });
    expect(bundle.result_meta).toHaveProperty("amount_currency_basis", null);
    expect(bundle.result_meta).toHaveProperty("amount_currency_basis_note", null);
    expect(bundle.result_meta.evidence_rows).toBeGreaterThan(0);

    expect(Object.keys(bundle.result.section_statuses ?? {})).toEqual(sections);
    for (const section of sections) {
      expect(bundle.result.section_statuses?.[section]).toEqual({
        status: "ok",
        message: null,
        duration_ms: 0,
      });
    }

    const expectedResultKeys: Partial<Record<BondDashboardBundleSectionId, string[]>> = {
      dates: ["report_dates"],
      "headline-kpis": ["report_date", "prev_report_date", "kpis", "prev_kpis"],
      "home-summary": [
        "report_date",
        "headline",
        "risk",
        "asset_type",
        "asset_rating",
        "maturity",
        "industry",
        "yield_distribution",
        "portfolio_comparison",
        "spread",
        "business_type",
      ],
      "asset-structure": ["report_date", "group_by", "items", "total_market_value"],
      "asset-structure-rating": ["report_date", "group_by", "items", "total_market_value"],
      "asset-structure-portfolio-name": ["report_date", "group_by", "items", "total_market_value"],
      "asset-structure-tenor-bucket": ["report_date", "group_by", "items", "total_market_value"],
      "yield-distribution": ["report_date", "items", "weighted_ytm"],
      "portfolio-comparison": ["report_date", "items"],
      "spread-analysis": ["report_date", "items"],
      "maturity-structure": ["report_date", "items", "total_market_value"],
      "industry-distribution": ["report_date", "items"],
      "risk-indicators": [
        "report_date",
        "total_market_value",
        "total_dv01",
        "weighted_duration",
        "credit_ratio",
        "weighted_convexity",
        "total_spread_dv01",
        "reinvestment_ratio_1y",
        "weighted_convexity_coverage_ratio",
      ],
      "business-type-metrics": ["report_date", "items"],
    };
    for (const section of sections) {
      const envelope = bundle.result.sections[section] as ApiEnvelope<unknown> | undefined;
      const result = envelope?.result as Record<string, unknown> | undefined;
      expect(Object.keys(result ?? {}).sort()).toEqual(
        [...(expectedResultKeys[section] ?? [])].sort(),
      );
      if (section === "dates") {
        expect(envelope?.data_source).toBe("bond_analytics_facts");
        expect(envelope?.result_meta).toMatchObject({
          basis: "formal",
          formal_use_allowed: true,
          quality_flag: "ok",
          requested_report_date: null,
          resolved_report_date: null,
          as_of_date: null,
          date_basis: null,
          filters_applied: {},
          tables_used: [],
          next_drill: [],
          source_surface: "mock",
        });
        expect(envelope?.result_meta).toHaveProperty("amount_currency_basis", null);
        expect(envelope?.result_meta).toHaveProperty("amount_currency_basis_note", null);
        expect(envelope?.result_meta).toHaveProperty("evidence_rows", null);
      } else {
        expectHealthyAnalyticalMockMeta(envelope, reportDate);
      }
    }

    const headline = bundle.result.sections["headline-kpis"];
    expect(headline?.result.prev_report_date).toBe("2026-02-28");
    expect(headline?.result.prev_kpis).not.toBeNull();

    const oldestHeadline = await client.getBondDashboardHeadlineKpis("2025-12-31");
    expect(oldestHeadline.result.prev_report_date).toBeNull();
    expect(oldestHeadline.result.prev_kpis).toBeNull();

    expect(bundle.result.sections["asset-structure"]?.result.group_by).toBe("bond_type");
    expect(bundle.result.sections["asset-structure-rating"]?.result.group_by).toBe("rating");
    expect(
      bundle.result.sections["asset-structure-portfolio-name"]?.result.group_by,
    ).toBe("portfolio_name");
    expect(
      bundle.result.sections["asset-structure-tenor-bucket"]?.result.group_by,
    ).toBe("tenor_bucket");

    const industry = bundle.result.sections["industry-distribution"]?.result.items ?? [];
    expect(industry).toHaveLength(2);
    expect(industry.reduce((sum, item) => sum + (item.percentage?.raw ?? 0), 0)).toBeCloseTo(1, 8);

    const risk = bundle.result.sections["risk-indicators"]?.result;
    expect(risk?.weighted_convexity_coverage_ratio).toMatchObject({
      unit: "ratio",
      sign_aware: false,
    });

    const businessItems = bundle.result.sections["business-type-metrics"]?.result.items ?? [];
    expect(businessItems[0]?.weighted_avg_ytm_coverage_ratio).toMatchObject({
      unit: "ratio",
      sign_aware: false,
    });
    expect(businessItems[0]?.weighted_avg_duration_coverage_ratio).toMatchObject({
      unit: "ratio",
      sign_aware: false,
    });
    expect(businessItems.find((item) => item.name === "无覆盖样例")).toMatchObject({
      market_value: "0.00000000",
      weighted_avg_ytm_pct: "",
      weighted_avg_duration: "",
      duration_source: "",
      weighted_avg_ytm_coverage_ratio: null,
      weighted_avg_duration_coverage_ratio: null,
    });

    expect(
      bundle.result.sections["spread-analysis"]?.result.items.find(
        (item) => item.bond_type === "无收益率覆盖样例",
      ),
    ).toMatchObject({
      median_yield: null,
      total_market_value: { raw: 0, unit: "yuan" },
    });
  });

  it("matches live dates-only and partial-failure bundle status semantics", async () => {
    const client = createApiClient({ mode: "mock" });

    const datesOnly = await client.fetchBondDashboardBundle(null, ["dates"]);
    expect(datesOnly.result).toMatchObject({
      report_date: null,
      requested_sections: ["dates"],
      failed_sections: [],
      section_statuses: {
        dates: { status: "ok", message: null, duration_ms: 0 },
      },
    });
    expect(datesOnly.result_meta).toMatchObject({
      basis: "formal",
      formal_use_allowed: true,
      quality_flag: "warning",
      requested_report_date: null,
      resolved_report_date: null,
      as_of_date: null,
      date_basis: "bond_dashboard_dates",
      filters_applied: { sections: ["dates"] },
      tables_used: [],
      evidence_rows: 0,
      source_surface: "mock",
    });
    expect(datesOnly.result_meta).toHaveProperty("amount_currency_basis", null);
    expect(datesOnly.result_meta).toHaveProperty("amount_currency_basis_note", null);

    vi.spyOn(client, "getBondDashboardRiskIndicators").mockRejectedValue(
      new Error("risk fixture unavailable"),
    );
    vi.spyOn(client, "getBondDashboardSpreadAnalysis").mockRejectedValue(
      new Error("spread fixture unavailable"),
    );
    const partial = await client.fetchBondDashboardBundle(
      "2026-03-31",
      ["risk-indicators", "headline-kpis", "spread-analysis"],
    );

    expect(partial.result.failed_sections).toEqual([
      "risk-indicators",
      "spread-analysis",
    ]);
    expect(partial.result.sections["headline-kpis"]).toBeDefined();
    expect(partial.result.sections["risk-indicators"]).toBeUndefined();
    expect(partial.result.sections["spread-analysis"]).toBeUndefined();
    expect(partial.result.section_statuses).toMatchObject({
      "risk-indicators": {
        status: "error",
        message: "risk fixture unavailable",
        duration_ms: 0,
      },
      "headline-kpis": { status: "ok", message: null, duration_ms: 0 },
      "spread-analysis": {
        status: "error",
        message: "spread fixture unavailable",
        duration_ms: 0,
      },
    });
    expect(partial.result_meta.quality_flag).toBe("warning");
    expect(partial.result_meta.evidence_rows).toBeGreaterThan(0);

    await expect(
      client.fetchBondDashboardBundle(null, ["headline-kpis"]),
    ).rejects.toThrow("report_date is required for the requested bundle sections");
    await expect(client.fetchBondDashboardBundle(null, [])).rejects.toThrow(
      "sections must include at least one supported section id",
    );
  });

  it("assembles mock bundle sections through dynamically bound client methods", async () => {
    const client = createApiClient({ mode: "mock" });
    const reportDate = "2026-03-31";
    const replacement = await client.getBondDashboardHeadlineKpis(reportDate);
    const spy = vi.spyOn(client, "getBondDashboardHeadlineKpis").mockResolvedValue({
      ...replacement,
      result_meta: {
        ...replacement.result_meta,
        trace_id: "tr_dynamic_override",
      },
    });

    const bundle = await client.fetchBondDashboardBundle(reportDate, ["headline-kpis"]);

    expect(spy).toHaveBeenCalledWith(reportDate);
    expect(bundle.result.sections["headline-kpis"]?.result_meta.trace_id).toBe(
      "tr_dynamic_override",
    );
  });

  it("preserves the deferred mock client receiver for analytics bundle sections", async () => {
    const client = createDeferredApiClient({ mode: "mock" });

    const bundle = await client.fetchBondDashboardBundle("2026-03-31", [
      "headline-kpis",
      "risk-indicators",
      "top-holdings",
      "yield-curve-term-structure",
    ], {
      analyticsTopN: 10,
      curveTypes: "treasury,cdb",
    });

    expect(bundle.result.sections["headline-kpis"]?.result.report_date).toBe("2026-03-31");
    expect(bundle.result.sections["risk-indicators"]?.result.report_date).toBe("2026-03-31");
    expect(
      bundle.result.sections["top-holdings"]?.result.items[0]?.instrument_code,
    ).toBe("230210.IB");
    expect(
      bundle.result.sections["yield-curve-term-structure"]?.result.report_date,
    ).toBe("2026-03-31");
    expect(bundle.result.failed_sections).toEqual([]);
  });
});
