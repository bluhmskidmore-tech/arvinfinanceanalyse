import { describe, expect, it, vi } from "vitest";

import { createDeferredApiClient } from "../api/clientContext";
import { formatRawAsNumeric } from "../utils/format";

describe("home startup deferred client", () => {
  it("routes portfolio startup reads through the lightweight home clients", async () => {
    const requestedUrls: string[] = [];
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      requestedUrls.push(String(input));
      return new Response(
        JSON.stringify({
          result_meta: { basis: "formal" },
          result: {},
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }) as unknown as typeof fetch;
    const client = createDeferredApiClient({
      mode: "real",
      baseUrl: "http://backend.local",
      fetchImpl,
    });

    await client.getBondDashboardDates();
    await client.getRiskTensorDates();
    await client.getBalanceAnalysisDates();
    await client.getBalanceAnalysisOverview({
      reportDate: "2026-04-30",
      positionScope: "all",
      currencyBasis: "CNY",
    });
    await client.getBalanceAnalysisSummaryByBasis({
      reportDate: "2026-04-30",
      positionScope: "all",
      currencyBasis: "CNY",
    });
    await client.getBalanceMovementDates("CNX");
    await client.getBalanceMovementAnalysis({
      reportDate: "2026-04-30",
      currencyBasis: "CNX",
    });
    await client.getAdbComparison("2026-01-01", "2026-04-30");
    await client.getPnlAttributionAnalysisSummary("2026-04-30");

    expect(requestedUrls).toEqual([
      "http://backend.local/api/bond-dashboard/dates",
      "http://backend.local/api/risk/tensor/dates",
      "http://backend.local/ui/balance-analysis/dates",
      "http://backend.local/ui/balance-analysis/overview?report_date=2026-04-30&position_scope=all&currency_basis=CNY",
      "http://backend.local/ui/balance-analysis/summary-by-basis?report_date=2026-04-30&position_scope=all&currency_basis=CNY",
      "http://backend.local/ui/balance-movement-analysis/dates?currency_basis=CNX",
      "http://backend.local/ui/balance-movement-analysis?report_date=2026-04-30&currency_basis=CNX",
      "http://backend.local/api/analysis/adb/comparison?start_date=2026-01-01&end_date=2026-04-30",
      "http://backend.local/api/pnl-attribution/summary?report_date=2026-04-30",
    ]);
  });

  it("preserves the governed risk-date envelope in lightweight mock mode", async () => {
    const client = createDeferredApiClient({ mode: "mock" });

    const envelope = await client.getRiskTensorDates();

    expect(envelope.result.report_dates).toEqual([
      "2026-02-28",
      "2026-01-31",
      "2025-12-31",
    ]);
    expect(envelope.result_meta).toMatchObject({
      basis: "formal",
      formal_use_allowed: true,
      source_version: "sv_risk_tensor_fact_mock_v3",
      rule_version: "rv_risk_tensor_formal_materialize_v6",
      cache_version: "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v6",
    });
  });

  it("preserves balance-analysis automatic hydration reads in lightweight mock mode", async () => {
    const client = createDeferredApiClient({ mode: "mock" });

    const movementDates = await client.getBalanceMovementDates("CNX");
    const movement = await client.getBalanceMovementAnalysis({
      reportDate: "2026-02-28",
      currencyBasis: "CNX",
    });
    const adbComparison = await client.getAdbComparison(
      "2026-01-01",
      "2026-02-28",
    );

    expect(movementDates.result).toMatchObject({
      currency_basis: "CNX",
      report_dates: ["2026-02-28"],
    });
    expect(movement.result).toMatchObject({
      currency_basis: "CNX",
      report_date: "2026-02-28",
    });
    expect(adbComparison).toMatchObject({
      adb_denominator_basis: "snapshot_calendar",
      assets_breakdown: [],
      liabilities_breakdown: [],
      simulated: false,
    });
  });

  it("routes home supplemental reads through the lightweight home supplemental client", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const result = url.includes("/api/bond-dashboard/home-summary")
        ? {
            report_date: "2026-04-30",
            headline: { report_date: "2026-04-30", prev_report_date: null, kpis: {}, prev_kpis: null },
            risk: { report_date: "2026-04-30" },
            asset_type: { report_date: "2026-04-30", group_by: "bond_type", items: [] },
            asset_rating: { report_date: "2026-04-30", group_by: "rating", items: [] },
            maturity: { report_date: "2026-04-30", items: [] },
            industry: { report_date: "2026-04-30", items: [] },
            yield_distribution: { report_date: "2026-04-30", items: [] },
            portfolio_comparison: { report_date: "2026-04-30", items: [] },
            spread: { report_date: "2026-04-30", items: [] },
            business_type: { report_date: "2026-04-30", items: [] },
          }
        : url.includes("/api/bond-analytics/portfolio-headlines")
          ? {
              report_date: "2026-04-30",
              total_market_value: "332281921064.45000000",
            weighted_ytm: "0.02561294",
            weighted_duration: "4.44842730",
            weighted_coupon: "0.01906003",
            total_dv01: "105628442.39590558",
            bond_count: 1710,
            credit_weight: "0.29955411",
            issuer_hhi: "0.05312225",
            issuer_top5_weight: "0.42432973",
            by_asset_class: [
              {
                asset_class: "credit",
                market_value: "99536414280.77000000",
                duration: "2.69704353",
                dv01: "25862175.57270329",
                weight: "0.29955411",
              },
            ],
            warnings: [],
            computed_at: "2026-04-30T00:00:00Z",
          }
        : {
            report_date: "2026-04-30",
            credit_market_value: "1500000000",
            credit_weight: "0.25",
            spread_dv01: "25000",
            weighted_avg_spread: "80",
            weighted_avg_spread_duration: "4.2",
            spread_scenarios: [],
            migration_scenarios: [],
          };

      return new Response(
        JSON.stringify({
          result_meta: { basis: "formal" },
          result,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }) as unknown as typeof fetch;
    const client = createDeferredApiClient({
      mode: "real",
      baseUrl: "http://backend.local",
      fetchImpl,
    });

    const summary = await client.getBondDashboardHomeSummary("2026-04-30");
    const portfolio = await client.getBondAnalyticsPortfolioHeadlines("2026-04-30");
    const creditSpread = await client.getBondAnalyticsCreditSpreadMigration("2026-04-30");

    expect(fetchImpl).toHaveBeenCalledTimes(3);
    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://backend.local/api/bond-dashboard/home-summary?report_date=2026-04-30",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://backend.local/api/bond-analytics/portfolio-headlines?report_date=2026-04-30",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      3,
      "http://backend.local/api/bond-analytics/credit-spread-migration?report_date=2026-04-30",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
    expect(summary.result.report_date).toBe("2026-04-30");
    expect(portfolio.result.total_market_value).toMatchObject({
      raw: 332281921064.45,
      unit: "yuan",
      sign_aware: false,
      display: expect.any(String),
    });
    expect(portfolio.result.weighted_ytm).toMatchObject({
      raw: 0.02561294,
      unit: "pct",
      sign_aware: true,
      display: expect.any(String),
    });
    expect(portfolio.result.by_asset_class[0]?.weight).toMatchObject({
      raw: 0.29955411,
      unit: "ratio",
      sign_aware: false,
      display: expect.any(String),
    });
    expect(creditSpread.result.credit_market_value).toMatchObject({
      raw: 1500000000,
      unit: "yuan",
      sign_aware: false,
      display: expect.any(String),
    });
  });

  it("preserves governed Numeric spread_change_bp through the deferred home supplemental client", async () => {
    const spreadChange = formatRawAsNumeric({ raw: 25, unit: "bp", sign_aware: true });
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          result_meta: { basis: "formal" },
          result: {
            report_date: "2026-04-30",
            credit_market_value: "1500000000",
            credit_weight: "0.25",
            spread_dv01: "25000",
            weighted_avg_spread: "80",
            weighted_avg_spread_duration: "4.2",
            spread_scenarios: [
              {
                scenario_name: "+25bp",
                spread_change_bp: spreadChange,
                pnl_impact: "-1200000",
                oci_impact: "-800000",
                tpl_impact: "-100000",
              },
            ],
            migration_scenarios: [],
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;
    const client = createDeferredApiClient({
      mode: "real",
      baseUrl: "http://backend.local",
      fetchImpl,
    });

    const creditSpread = await client.getBondAnalyticsCreditSpreadMigration("2026-04-30");

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://backend.local/api/bond-analytics/credit-spread-migration?report_date=2026-04-30",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
    expect(creditSpread.result.spread_scenarios[0]?.spread_change_bp).toEqual(spreadChange);
    expect(creditSpread.result.spread_scenarios[0]?.pnl_impact).toMatchObject({
      raw: -1200000,
      unit: "yuan",
      sign_aware: true,
      display: expect.any(String),
    });
  });

  it("serializes explicit include_payload_json for deferred home market ticker choice news reads", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          result_meta: { basis: "analytical" },
          result: {
            total_rows: 0,
            limit: 2,
            offset: 0,
            as_of_date: "2026-04-23",
            excluded_future_rows: 0,
            payload_json_included: false,
            events: [],
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;
    const client = createDeferredApiClient({
      mode: "real",
      baseUrl: "http://backend.local",
      fetchImpl,
    });

    await client.getChoiceNewsEvents({
      limit: 2,
      offset: 0,
      includePayloadJson: false,
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://backend.local/ui/news/choice-events/latest?limit=2&offset=0&include_payload_json=false",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
  });

  it("routes compact Choice News through the deferred mock home ticker client", async () => {
    const client = createDeferredApiClient({ mode: "mock" });

    const payload = await client.getChoiceNewsEvents({
      limit: 1,
      offset: 1,
      includePayloadJson: false,
    });
    const returnedEventId = payload.result.events[0]?.event_key;

    expect(payload.result.payload_json_included).toBe(false);
    expect(payload.result.events[0]?.payload_json).toBeNull();
    expect(payload.result.compare?.same_direction[0]?.source_event_ids).toEqual([
      returnedEventId,
    ]);
  });

  it("passes return decomposition detail through the deferred home supplemental client", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          result_meta: { basis: "formal" },
          result: {
            report_date: "2026-04-30",
            computed_at: "2026-04-30T00:00:00Z",
            warnings: [],
            bond_details: [],
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;
    const client = createDeferredApiClient({
      mode: "real",
      baseUrl: "http://backend.local",
      fetchImpl,
    });

    await client.getBondAnalyticsReturnDecomposition("2026-04-30", "MoM", {
      assetClass: "all",
      accountingClass: "all",
      detail: "summary",
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://backend.local/api/bond-analytics/return-decomposition?report_date=2026-04-30&period_type=MoM&asset_class=all&accounting_class=all&detail=summary",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
  });
});
