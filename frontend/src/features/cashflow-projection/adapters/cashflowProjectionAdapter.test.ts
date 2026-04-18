import { describe, expect, it } from "vitest";

import type { ApiEnvelope, CashflowProjectionPayload, Numeric, ResultMeta } from "../../../api/contracts";
import { adaptCashflowProjection } from "./cashflowProjectionAdapter";

function n(partial: Partial<Numeric> = {}): Numeric {
  return {
    raw: 1,
    unit: "yuan",
    display: "+1.00 亿",
    precision: 2,
    sign_aware: true,
    ...partial,
  };
}

function meta(partial: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_test",
    basis: "formal",
    result_kind: "cashflow_projection.overview",
    formal_use_allowed: true,
    source_version: "sv_test",
    vendor_version: "vv_test",
    rule_version: "rv_test",
    cache_version: "cv_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-18T00:00:00",
    filters_applied: {},
    tables_used: [],
    ...partial,
  };
}

function env(overrides: Partial<CashflowProjectionPayload> = {}, metaOverride: Partial<ResultMeta> = {}): ApiEnvelope<CashflowProjectionPayload> {
  const base: CashflowProjectionPayload = {
    report_date: "2025-04-30",
    duration_gap: n({ raw: 1.25, unit: "ratio" }),
    asset_duration: n({ raw: 3.8, unit: "ratio", sign_aware: false }),
    liability_duration: n({ raw: 2.55, unit: "ratio", sign_aware: false }),
    equity_duration: n({ raw: 5.2, unit: "ratio" }),
    rate_sensitivity_1bp: n({ raw: 125000, unit: "yuan" }),
    reinvestment_risk_12m: n({ raw: 0.185, unit: "pct", sign_aware: false }),
    monthly_buckets: [],
    top_maturing_assets_12m: [],
    warnings: [],
    computed_at: "2026-04-18T00:00:00",
  };
  return {
    result_meta: meta(metaOverride),
    result: { ...base, ...overrides },
  };
}

describe("adaptCashflowProjection", () => {
  it("maps a normal payload into a view-model", () => {
    const out = adaptCashflowProjection({ envelope: env(), isLoading: false, isError: false });
    expect(out.state.kind).toBe("empty"); // lists empty so state="empty"
    // With non-empty lists it's "ok":
    const out2 = adaptCashflowProjection({
      envelope: env({
        monthly_buckets: [
          {
            year_month: "2025-05",
            asset_inflow: n({ raw: 1e8, unit: "yuan", sign_aware: false }),
            liability_outflow: n({ raw: 5e7, unit: "yuan", sign_aware: false }),
            net_cashflow: n({ raw: 5e7, unit: "yuan" }),
            cumulative_net: n({ raw: 5e7, unit: "yuan" }),
          },
        ],
      }),
      isLoading: false,
      isError: false,
    });
    expect(out2.state.kind).toBe("ok");
    expect(out2.vm?.kpis.durationGap.raw).toBe(1.25);
    expect(out2.vm?.monthlyBuckets[0].assetInflow.raw).toBe(1e8);
  });

  it("returns loading state when isLoading", () => {
    const out = adaptCashflowProjection({ envelope: undefined, isLoading: true, isError: false });
    expect(out.state.kind).toBe("loading");
    expect(out.vm).toBeNull();
  });

  it("returns error state when isError", () => {
    const out = adaptCashflowProjection({ envelope: undefined, isLoading: false, isError: true });
    expect(out.state.kind).toBe("error");
  });

  it("preserves sign_aware = true display on negative raw", () => {
    const out = adaptCashflowProjection({
      envelope: env({
        duration_gap: n({ raw: -0.75, unit: "ratio", display: "-0.75", sign_aware: true }),
        monthly_buckets: [
          {
            year_month: "2025-05",
            asset_inflow: n({ raw: 1e8, unit: "yuan", sign_aware: false }),
            liability_outflow: n({ raw: 5e7, unit: "yuan", sign_aware: false }),
            net_cashflow: n({ raw: 5e7, unit: "yuan" }),
            cumulative_net: n({ raw: 5e7, unit: "yuan" }),
          },
        ],
      }),
      isLoading: false,
      isError: false,
    });
    expect(out.vm?.kpis.durationGap.raw).toBe(-0.75);
    expect(out.vm?.kpis.durationGap.display).toBe("-0.75");
  });

  it("raises fallback state on fallback_mode=latest_snapshot", () => {
    const out = adaptCashflowProjection({
      envelope: env({}, { fallback_mode: "latest_snapshot", filters_applied: { report_date: "2025-03-31" } }),
      isLoading: false,
      isError: false,
    });
    expect(out.state.kind).toBe("fallback");
  });

  it("raises explicit_miss state on source_version tag", () => {
    const out = adaptCashflowProjection({
      envelope: env({}, { source_version: "sv_explicit_miss", filters_applied: { report_date: "2099-01-01" } }),
      isLoading: false,
      isError: false,
    });
    expect(out.state.kind).toBe("explicit_miss");
  });
});
