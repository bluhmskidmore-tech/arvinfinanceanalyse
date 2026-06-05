import { describe, expect, it } from "vitest";

import type { ApiEnvelope, Numeric, PnlBridgePayload, PnlBridgeSummary, ResultMeta } from "../../../api/contracts";
import { adaptPnlBridge } from "./pnlBridgeAdapter";

function num(partial: Partial<Numeric> = {}): Numeric {
  return {
    raw: 0,
    unit: "yuan",
    display: "0.00",
    precision: 2,
    sign_aware: true,
    ...partial,
  };
}

function summaryEmpty(): PnlBridgeSummary {
  return {
    row_count: 0,
    ok_count: 0,
    warning_count: 0,
    error_count: 0,
    total_beginning_dirty_mv: num({ raw: 0, sign_aware: false }),
    total_ending_dirty_mv: num({ raw: 0, sign_aware: false }),
    total_carry: num({ raw: 0 }),
    total_roll_down: num({ raw: 0 }),
    total_treasury_curve: num({ raw: 0 }),
    total_credit_spread: num({ raw: 0 }),
    total_fx_translation: num({ raw: 0 }),
    total_realized_trading: num({ raw: 0 }),
    total_unrealized_fv: num({ raw: 0 }),
    total_manual_adjustment: num({ raw: 0 }),
    total_explained_pnl: num({ raw: 0 }),
    total_actual_pnl: num({ raw: 0 }),
    total_residual: num({ raw: 0 }),
    quality_flag: "ok",
  };
}

function summaryWithRows(): PnlBridgeSummary {
  return {
    ...summaryEmpty(),
    row_count: 1,
    ok_count: 1,
    total_explained_pnl: num({ raw: 1.5, display: "+1.50 亿", sign_aware: true }),
  };
}

function meta(partial: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_pnl_bridge",
    basis: "formal",
    result_kind: "pnl.bridge",
    formal_use_allowed: true,
    source_version: "sv_test",
    vendor_version: "vv_test",
    rule_version: "rv_test",
    cache_version: "cv_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-18T00:00:00Z",
    filters_applied: {},
    tables_used: [],
    ...partial,
  };
}

function envelope(overrides: Partial<PnlBridgePayload> = {}, metaOverride: Partial<ResultMeta> = {}): ApiEnvelope<PnlBridgePayload> {
  const base: PnlBridgePayload = {
    report_date: "2025-12-31",
    rows: [],
    summary: summaryEmpty(),
    warnings: [],
    ...overrides,
  };
  return {
    result_meta: meta(metaOverride),
    result: base,
  };
}

describe("adaptPnlBridge", () => {
  it("maps a non-empty payload into vm (reportDate, summary, rows, warnings)", () => {
    const out = adaptPnlBridge({
      envelope: envelope({
        report_date: "2025-11-30",
        summary: summaryWithRows(),
        rows: [
          {
            instrument_code: "X",
            portfolio_name: "P",
            accounting_basis: "AC",
            carry: num({ raw: 1 }),
            roll_down: num({ raw: 0 }),
            treasury_curve: num({ raw: 0 }),
            credit_spread: num({ raw: 0 }),
            fx_translation: num({ raw: 0 }),
            realized_trading: num({ raw: 0 }),
            unrealized_fv: num({ raw: 0 }),
            manual_adjustment: num({ raw: 0 }),
            explained_pnl: num({ raw: 0 }),
            actual_pnl: num({ raw: 0 }),
            residual: num({ raw: 0 }),
            residual_ratio: num({ raw: 0.02, unit: "ratio", display: "0.02", sign_aware: true }),
            quality_flag: "ok",
          },
        ],
        warnings: ["w1"],
      }),
      isLoading: false,
      isError: false,
    });
    expect(out.state.kind).toBe("ok");
    expect(out.vm?.reportDate).toBe("2025-11-30");
    expect(out.vm?.summary.row_count).toBe(1);
    expect(out.vm?.rows).toHaveLength(1);
    expect(out.vm?.rows[0]?.instrument_code).toBe("X");
    expect(out.vm?.warnings).toEqual(["w1"]);
  });

  it("returns loading state when isLoading", () => {
    const out = adaptPnlBridge({ envelope: undefined, isLoading: true, isError: false });
    expect(out.state.kind).toBe("loading");
    expect(out.vm).toBeNull();
  });

  it("returns error state when isError", () => {
    const out = adaptPnlBridge({ envelope: undefined, isLoading: false, isError: true });
    expect(out.state.kind).toBe("error");
    expect(out.vm).toBeNull();
  });

  it("raises fallback state on fallback_mode=latest_snapshot", () => {
    const out = adaptPnlBridge({
      envelope: envelope({}, { fallback_mode: "latest_snapshot", filters_applied: { report_date: "2025-03-31" } }),
      isLoading: false,
      isError: false,
    });
    expect(out.state.kind).toBe("fallback");
    if (out.state.kind === "fallback") {
      expect(out.state.effective_date).toBe("2025-03-31");
    }
  });

  it("raises explicit_miss state on source_version tag", () => {
    const out = adaptPnlBridge({
      envelope: envelope({}, { source_version: "sv_explicit_miss", filters_applied: { report_date: "2099-01-01" } }),
      isLoading: false,
      isError: false,
    });
    expect(out.state.kind).toBe("explicit_miss");
    if (out.state.kind === "explicit_miss") {
      expect(out.state.requested_date).toBe("2099-01-01");
    }
  });

  it("raises stale state on vendor_stale", () => {
    const out = adaptPnlBridge({
      envelope: envelope({}, { vendor_status: "vendor_stale", filters_applied: { report_date: "2025-01-31" } }),
      isLoading: false,
      isError: false,
    });
    expect(out.state.kind).toBe("stale");
    if (out.state.kind === "stale") {
      expect(out.state.effective_date).toBe("2025-01-31");
    }
  });
});
