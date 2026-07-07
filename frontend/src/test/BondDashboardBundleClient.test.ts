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
    expect(bundle.result.sections["headline-kpis"]).toEqual(
      await client.getBondDashboardHeadlineKpis(reportDate),
    );
    expect(bundle.result.sections["asset-structure-rating"]).toEqual(
      await client.getBondDashboardAssetStructure(reportDate, "rating"),
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

  it("supports the default deferred mock client path without relying on method this binding", async () => {
    const client = createDeferredApiClient({ mode: "mock" });

    const bundle = await client.fetchBondDashboardBundle("2026-03-31", [
      "headline-kpis",
      "risk-indicators",
    ]);

    expect(bundle.result.sections["headline-kpis"]?.result.report_date).toBe("2026-03-31");
    expect(bundle.result.sections["risk-indicators"]?.result.report_date).toBe("2026-03-31");
  });
});
