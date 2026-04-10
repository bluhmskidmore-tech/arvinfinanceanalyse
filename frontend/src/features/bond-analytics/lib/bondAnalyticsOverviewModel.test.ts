import { describe, expect, it } from "vitest";

import type { ActionAttributionResponse } from "../types";
import { buildBondAnalyticsOverviewModel } from "./bondAnalyticsOverviewModel";

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

describe("buildBondAnalyticsOverviewModel", () => {
  it("promotes action attribution to summary when real content exists", () => {
    const model = buildBondAnalyticsOverviewModel({
      reportDate: "2026-03-31",
      periodType: "MoM",
      actionAttribution: createActionAttribution({
        total_actions: 4,
        total_pnl_from_actions: "1500000",
        by_action_type: [
          {
            action_type: "ADD_DURATION",
            action_type_name: "加久期",
            action_count: 4,
            total_pnl_economic: "1500000",
            total_pnl_accounting: "1500000",
            avg_pnl_per_action: "375000",
          },
        ],
      }),
    });

    const actionModule = model.currentModules.find(
      (module) => module.key === "action-attribution",
    );

    expect(actionModule?.tier).toBe("summary");
    expect(actionModule?.summary?.primaryValue).toBe("4");
    expect(actionModule?.summary?.secondaryValue).toBe("1500000");
    expect(model.futureModules.length).toBeGreaterThan(0);
  });

  it("downgrades action attribution to status when the response is placeholder-only", () => {
    const model = buildBondAnalyticsOverviewModel({
      reportDate: "2026-03-31",
      periodType: "MoM",
      actionAttribution: createActionAttribution({
        warnings: ["DuckDB fact tables not yet populated - returning empty attribution"],
      }),
    });

    const actionModule = model.currentModules.find(
      (module) => module.key === "action-attribution",
    );

    expect(actionModule?.tier).toBe("status");
    expect(actionModule?.summary).toBeUndefined();
    expect(actionModule?.statusReason).toMatch(/placeholder/i);
  });
});
