import { describe, expect, it } from "vitest";

import type { ResultMeta } from "../../../api/contracts";
import { derivePnlDataSectionState } from "./pnlAttributionAdapter";

function makeMeta(partial: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_test",
    basis: "formal",
    result_kind: "pnl_attribution.volume_rate",
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
    ...partial,
  };
}

describe("derivePnlDataSectionState", () => {
  it("loading flag -> loading state", () => {
    const s = derivePnlDataSectionState({
      meta: null,
      isLoading: true,
      isError: false,
      errorMessage: null,
      isEmpty: false,
    });
    expect(s.kind).toBe("loading");
  });

  it("error flag -> error state with message", () => {
    const s = derivePnlDataSectionState({
      meta: null,
      isLoading: false,
      isError: true,
      errorMessage: "fetch failed",
      isEmpty: false,
    });
    expect(s.kind).toBe("error");
    if (s.kind === "error") expect(s.message).toBe("fetch failed");
  });

  it("meta null + no flags -> loading", () => {
    const s = derivePnlDataSectionState({
      meta: null,
      isLoading: false,
      isError: false,
      errorMessage: null,
      isEmpty: false,
    });
    expect(s.kind).toBe("loading");
  });

  it("vendor_unavailable meta -> vendor_unavailable state", () => {
    const s = derivePnlDataSectionState({
      meta: makeMeta({ vendor_status: "vendor_unavailable", quality_flag: "warning" }),
      isLoading: false,
      isError: false,
      errorMessage: null,
      isEmpty: false,
    });
    expect(s.kind).toBe("vendor_unavailable");
  });

  it("explicit_miss source_version -> explicit_miss state", () => {
    const s = derivePnlDataSectionState({
      meta: makeMeta({
        source_version: "sv_exec_dashboard_explicit_miss_v1",
        quality_flag: "warning",
        filters_applied: { report_date: "2025-11-30" },
      }),
      isLoading: false,
      isError: false,
      errorMessage: null,
      isEmpty: false,
    });
    expect(s.kind).toBe("explicit_miss");
    if (s.kind === "explicit_miss") expect(s.requested_date).toBe("2025-11-30");
  });

  it("fallback_mode=latest_snapshot -> fallback state", () => {
    const s = derivePnlDataSectionState({
      meta: makeMeta({
        fallback_mode: "latest_snapshot",
        filters_applied: { report_date: "2025-12-30" },
      }),
      isLoading: false,
      isError: false,
      errorMessage: null,
      isEmpty: false,
    });
    expect(s.kind).toBe("fallback");
    if (s.kind === "fallback") expect(s.effective_date).toBe("2025-12-30");
  });

  it("vendor_stale -> stale state", () => {
    const s = derivePnlDataSectionState({
      meta: makeMeta({ vendor_status: "vendor_stale", quality_flag: "stale" }),
      isLoading: false,
      isError: false,
      errorMessage: null,
      isEmpty: false,
    });
    expect(s.kind).toBe("stale");
  });

  it("isEmpty flag (and meta ok) -> empty", () => {
    const s = derivePnlDataSectionState({
      meta: makeMeta(),
      isLoading: false,
      isError: false,
      errorMessage: null,
      isEmpty: true,
    });
    expect(s.kind).toBe("empty");
  });

  it("all ok -> ok", () => {
    const s = derivePnlDataSectionState({
      meta: makeMeta(),
      isLoading: false,
      isError: false,
      errorMessage: null,
      isEmpty: false,
    });
    expect(s.kind).toBe("ok");
  });

  it("effective_date mixed when multiple effective_report_dates diverge", () => {
    const s = derivePnlDataSectionState({
      meta: makeMeta({
        fallback_mode: "latest_snapshot",
        filters_applied: {
          effective_report_dates: {
            pnl: "2026-04-08",
            bond: "2026-04-07",
          },
        },
      }),
      isLoading: false,
      isError: false,
      errorMessage: null,
      isEmpty: false,
    });
    expect(s.kind).toBe("fallback");
    if (s.kind === "fallback") expect(s.effective_date).toBe("mixed");
  });
});
