import { describe, expect, it } from "vitest";

import type { ActionAttributionResponse } from "../types";
import {
  deriveActionAttributionReadiness,
  hasPlaceholderWarning,
} from "./bondAnalyticsModuleReadiness";

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

describe("bondAnalyticsModuleReadiness", () => {
  it("detects placeholder warnings", () => {
    expect(
      hasPlaceholderWarning([
        "DuckDB fact tables not yet populated - returning empty attribution",
      ]),
    ).toBe(true);
    expect(hasPlaceholderWarning(["real content is available"])).toBe(false);
  });

  it("downgrades action attribution when only placeholder warnings exist", () => {
    const readiness = deriveActionAttributionReadiness({
      actionAttribution: createActionAttribution({
        warnings: ["DuckDB fact tables not yet populated - returning empty attribution"],
      }),
    });

    expect(readiness.tier).toBe("status");
    expect(readiness.statusLabel).toBe("placeholder");
    expect(readiness.summary).toBeUndefined();
  });

  it("promotes action attribution when real values exist", () => {
    const readiness = deriveActionAttributionReadiness({
      actionAttribution: createActionAttribution({
        total_actions: 3,
        total_pnl_from_actions: "2500000",
        by_action_type: [
          {
            action_type: "ADD_DURATION",
            action_type_name: "加久期",
            action_count: 3,
            total_pnl_economic: "2500000",
            total_pnl_accounting: "2500000",
            avg_pnl_per_action: "833333",
          },
        ],
      }),
    });

    expect(readiness.tier).toBe("summary");
    expect(readiness.statusLabel).toBe("real-summary");
    expect(readiness.summary?.primaryValue).toBe("3");
    expect(readiness.summary?.secondaryValue).toBe("2500000");
  });
});
