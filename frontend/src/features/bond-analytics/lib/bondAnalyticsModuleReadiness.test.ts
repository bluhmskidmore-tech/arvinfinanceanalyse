import { describe, expect, it } from "vitest";

import type { ResultMeta } from "../../../api/contracts";
import { formatRawAsNumeric } from "../../../utils/format";
import type { ActionAttributionResponse } from "../types";
import {
  classifyWarningSignals,
  deriveActionAttributionReadiness,
  hasPlaceholderWarning,
} from "./bondAnalyticsModuleReadiness";

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

const yuan = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: true });
const ratio = (raw: number, signAware = true) =>
  formatRawAsNumeric({ raw, unit: "ratio", sign_aware: signAware });
const dv01 = (raw: number) => formatRawAsNumeric({ raw, unit: "dv01", sign_aware: false });

function createActionAttribution(
  overrides: Partial<ActionAttributionResponse> = {},
): ActionAttributionResponse {
  return {
    report_date: "2026-03-31",
    period_type: "MoM",
    period_start: "2026-03-01",
    period_end: "2026-03-31",
    total_actions: 0,
    total_pnl_from_actions: yuan(0),
    by_action_type: [],
    action_details: [],
    period_start_duration: ratio(3.1, false),
    period_end_duration: ratio(3.05, false),
    duration_change_from_actions: ratio(-0.05),
    period_start_dv01: dv01(120000),
    period_end_dv01: dv01(115000),
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

  it("classifies partial warning signals", () => {
    expect(
      classifyWarningSignals([
        "roll_down / rate_effect / spread_effect / trading require Phase 3 curve and trade data",
      ]),
    ).toEqual({
      hasPlaceholderSignals: false,
      hasPartialSignals: true,
      hasAnyWarnings: true,
    });
  });

  it("keeps action attribution readiness-only when provenance is degraded", () => {
    const readiness = deriveActionAttributionReadiness({
      actionAttribution: createActionAttribution({
        total_actions: 3,
        total_pnl_from_actions: yuan(2500000),
        by_action_type: [
          {
            action_type: "ADD_DURATION",
            action_type_name: "Add duration",
            action_count: 3,
            total_pnl_economic: yuan(2500000),
            total_pnl_accounting: yuan(2500000),
            avg_pnl_per_action: yuan(833333),
          },
        ],
      }),
      actionAttributionMeta: createResultMeta({
        quality_flag: "warning",
        fallback_mode: "latest_snapshot",
      }),
    });

    expect(readiness.tier).toBe("status");
    expect(readiness.statusLabel).toBe("warning");
    expect(readiness.summary).toBeUndefined();
  });

  it("promotes action attribution only when payload and provenance are both clean", () => {
    const readiness = deriveActionAttributionReadiness({
      actionAttribution: createActionAttribution({
        total_actions: 3,
        total_pnl_from_actions: yuan(2500000),
        by_action_type: [
          {
            action_type: "ADD_DURATION",
            action_type_name: "Add duration",
            action_count: 3,
            total_pnl_economic: yuan(2500000),
            total_pnl_accounting: yuan(2500000),
            avg_pnl_per_action: yuan(833333),
          },
        ],
      }),
      actionAttributionMeta: createResultMeta(),
    });

    expect(readiness.tier).toBe("summary");
    expect(readiness.statusLabel).toBe("eligible");
    expect(readiness.summary?.primaryValue).toBe("3");
    expect(readiness.summary?.secondaryValue).toBe("2500000");
  });
});
