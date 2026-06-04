import { describe, expect, it, vi } from "vitest";

import { createDeferredApiClient } from "../api/clientContext";

describe("home startup deferred client", () => {
  it("routes home supplemental reads through the lightweight home supplemental client", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const result = url.includes("/api/bond-analytics/portfolio-headlines")
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

    const portfolio = await client.getBondAnalyticsPortfolioHeadlines("2026-04-30");
    const creditSpread = await client.getBondAnalyticsCreditSpreadMigration("2026-04-30");

    expect(fetchImpl).toHaveBeenCalledTimes(2);
    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://backend.local/api/bond-analytics/portfolio-headlines?report_date=2026-04-30",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://backend.local/api/bond-analytics/credit-spread-migration?report_date=2026-04-30",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
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
});
