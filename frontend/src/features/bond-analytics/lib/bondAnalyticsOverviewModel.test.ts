import { describe, expect, it } from "vitest";

import type { ApiEnvelope, ResultMeta } from "../../../api/contracts";
import type { ActionAttributionResponse } from "../types";
import { buildBondAnalyticsOverviewModel } from "./bondAnalyticsOverviewModel";

function createResultMeta(
  overrides: Partial<ResultMeta> = {},
): ResultMeta {
  return {
    trace_id: "tr_demo",
    basis: "formal",
    result_kind: "bond_analytics.action_attribution",
    formal_use_allowed: true,
    source_version: "sv_demo",
    vendor_version: "vv_demo",
    rule_version: "rv_demo",
    cache_version: "cv_demo",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-10T00:00:00Z",
    ...overrides,
  };
}

function createActionAttribution(
  overrides: Partial<ActionAttributionResponse> = {},
): ActionAttributionResponse {
  return {
    report_date: "2026-03-31",
    period_type: "MoM",
    period_start: "2026-03-01",
    period_end: "2026-03-31",
    total_actions: 0,
    total_pnl_from_actions: "0",
    by_action_type: [],
    action_details: [],
    period_start_duration: "3.10",
    period_end_duration: "3.05",
    duration_change_from_actions: "-0.05",
    period_start_dv01: "120000",
    period_end_dv01: "115000",
    warnings: [],
    computed_at: "2026-04-10T00:00:00Z",
    ...overrides,
  };
}

function createActionAttributionEnvelope(
  resultOverrides: Partial<ActionAttributionResponse> = {},
  metaOverrides: Partial<ResultMeta> = {},
): ApiEnvelope<ActionAttributionResponse> {
  return {
    result_meta: createResultMeta(metaOverrides),
    result: createActionAttribution(resultOverrides),
  };
}

describe("buildBondAnalyticsOverviewModel", () => {
  it("builds a provenance-driven truth strip and promotes only eligible action attribution", () => {
    const model = buildBondAnalyticsOverviewModel({
      reportDate: "2026-03-31",
      periodType: "MoM",
      activeModuleKey: "action-attribution",
      actionAttributionEnvelope: createActionAttributionEnvelope({
        total_actions: 4,
        total_pnl_from_actions: "1500000",
        by_action_type: [
          {
            action_type: "ADD_DURATION",
            action_type_name: "Add duration",
            action_count: 4,
            total_pnl_economic: "1500000",
            total_pnl_accounting: "1500000",
            avg_pnl_per_action: "375000",
          },
        ],
      }),
    });

    expect(model.truthStrip.items.map((item) => item.key)).toEqual([
      "basis",
      "freshness",
      "quality",
      "coverage",
    ]);
    expect(model.truthStrip.items.find((item) => item.key === "basis")?.value).toBe(
      "Formal",
    );
    expect(model.headlineTiles).toHaveLength(1);
    expect(model.headlineTiles[0]?.key).toBe("action-attribution");
    expect(model.headlineTiles[0]?.value).toBe("4");
    expect(model.readinessItems).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "return-decomposition",
          statusLabel: "not-fetched-in-overview",
          promotionDestination: "readiness-only",
        }),
        expect.objectContaining({
          key: "accounting-audit",
          statusLabel: "not-fetched-in-overview",
          promotionDestination: "readiness-only",
        }),
      ]),
    );
    expect(model.futureVisibilityItems).toHaveLength(4);
    expect(model.activeModuleContext.key).toBe("action-attribution");
  });

  it("blocks promotion when provenance is degraded even if action content exists", () => {
    const model = buildBondAnalyticsOverviewModel({
      reportDate: "2026-03-31",
      periodType: "MoM",
      activeModuleKey: "action-attribution",
      actionAttributionEnvelope: createActionAttributionEnvelope(
        {
          total_actions: 4,
          total_pnl_from_actions: "1500000",
          by_action_type: [
            {
              action_type: "ADD_DURATION",
              action_type_name: "Add duration",
              action_count: 4,
              total_pnl_economic: "1500000",
              total_pnl_accounting: "1500000",
              avg_pnl_per_action: "375000",
            },
          ],
        },
        {
          quality_flag: "warning",
          fallback_mode: "latest_snapshot",
        },
      ),
    });

    expect(model.headlineTiles).toHaveLength(0);
    expect(model.readinessItems).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "action-attribution",
          statusLabel: "warning",
          promotionDestination: "readiness-only",
        }),
      ]),
    );
    expect(model.topAnomalies).toEqual(
      expect.arrayContaining([
        expect.stringMatching(/latest snapshot/i),
      ]),
    );
  });
});
