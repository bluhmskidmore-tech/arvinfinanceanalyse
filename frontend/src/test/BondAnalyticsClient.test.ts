import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import type { ResultMeta } from "../api/contracts";

const resultMeta: ResultMeta = {
  trace_id: "tr_credit_spread_normalize",
  basis: "formal",
  result_kind: "bond_analytics.credit_spread_migration",
  formal_use_allowed: true,
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

describe("BondAnalyticsClient", () => {
  it("normalizes flat credit spread migration numbers into governed Numeric fields", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          result_meta: resultMeta,
          result: {
            report_date: "2026-04-30",
            credit_bond_count: 1065,
            credit_market_value: "103053790790.32571000",
            credit_weight: "0.29543613",
            rating_aa_and_below_weight: "0.00627209",
            spread_dv01: "27117248.92176532",
            weighted_avg_spread: "0.37853183",
            weighted_avg_spread_duration: "2.65661441",
            spread_scenarios: [
              {
                scenario_name: "利差走阔 25bp",
                spread_change_bp: 25,
                pnl_impact: "-677931223.04413300",
                oci_impact: "-303443113.49227170",
                tpl_impact: "-39278727.02554200",
              },
            ],
            migration_scenarios: [],
            concentration_by_rating: {
              dimension: "rating",
              hhi: "0.58416106",
              top5_concentration: "1.00000000",
              top_items: [
                {
                  name: "AAA",
                  weight: "0.72212617",
                  market_value: "74417839294.38654000",
                },
              ],
            },
            oci_credit_exposure: "43823772942.12562600",
            oci_spread_dv01: "12137724.53969087",
            oci_sensitivity_25bp: "-303443113.49227170",
            computed_at: "2026-05-31T13:21:55.306232+00:00",
            warnings: [],
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const client = createApiClient({ mode: "real", baseUrl: "", fetchImpl: fetchImpl as typeof fetch });

    const envelope = await client.getBondAnalyticsCreditSpreadMigration("2026-04-30");

    expect(envelope.result.spread_dv01.raw).toBeCloseTo(27_117_248.92176532);
    expect(envelope.result.spread_dv01.display).toBe("27,117,249");
    expect(envelope.result.weighted_avg_spread.raw).toBeCloseTo(0.37853183);
    expect(envelope.result.rating_aa_and_below_weight?.raw).toBeCloseTo(0.00627209);
    expect(envelope.result.spread_scenarios[0]?.pnl_impact.raw).toBeCloseTo(-677_931_223.044133);
    expect(envelope.result.concentration_by_rating?.top_items[0]?.market_value.raw).toBeCloseTo(
      74_417_839_294.38654,
    );
  });
});
