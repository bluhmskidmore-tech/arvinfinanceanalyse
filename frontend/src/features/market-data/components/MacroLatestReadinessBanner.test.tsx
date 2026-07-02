import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ExternalDataWatermarkLedger, ResultMeta } from "../../../api/contracts";
import { MacroLatestReadinessBanner } from "./MacroLatestReadinessBanner";

function makeMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_macro_readiness_test",
    basis: "analytical",
    result_kind: "macro.choice.latest",
    formal_use_allowed: false,
    source_version: "sv_macro_readiness_test",
    vendor_version: "vv_macro_readiness_test",
    rule_version: "rv_macro_readiness_test",
    cache_version: "cv_macro_readiness_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-10T09:00:00Z",
    ...overrides,
  };
}

function makeLedger(): ExternalDataWatermarkLedger {
  return {
    summary: {
      catalog_count: 4,
      available_count: 3,
      no_data_count: 1,
      unavailable_count: 0,
      oldest_available_business_date: "2026-02-07",
      newest_available_business_date: "2026-04-10",
      last_successful_ingest: "2026-04-10T09:05:00Z",
    },
    entries: [
      {
        series_id: "M002",
        series_name: "DR007",
        vendor_name: "choice",
        source_family: "choice_macro",
        domain: "macro",
        row_count: 20,
        age_days: 48,
        freshness_tier: "stale",
        data_status: "available",
      },
      {
        series_id: "CA.BRENT",
        series_name: "Brent crude oil futures close",
        vendor_name: "choice",
        source_family: "choice_macro",
        domain: "macro",
        row_count: 20,
        age_days: 62,
        freshness_tier: "expired",
        data_status: "available",
      },
      {
        series_id: "CA.USDCNY",
        series_name: "USD/CNY spot",
        vendor_name: "choice",
        source_family: "choice_macro",
        domain: "macro",
        row_count: 0,
        age_days: null,
        freshness_tier: "unknown",
        data_status: "no_data",
      },
      {
        series_id: "FX.USDCNH",
        series_name: "USD/CNH offshore",
        vendor_name: "choice",
        source_family: "choice_fx",
        domain: "fx",
        row_count: 20,
        age_days: 99,
        freshness_tier: "expired",
        data_status: "available",
      },
      {
        series_id: "M999",
        series_name: "Macro series outside latest response",
        vendor_name: "choice",
        source_family: "choice_macro",
        domain: "macro",
        row_count: 20,
        age_days: 88,
        freshness_tier: "expired",
        data_status: "available",
      },
    ],
  };
}

describe("MacroLatestReadinessBanner", () => {
  it("summarizes the stalest current macro series and ignores unknown or out-of-scope rows", () => {
    render(
      <MacroLatestReadinessBanner
        testId="macro-readiness"
        isLoading={false}
        isError={false}
        hasSeries
        meta={makeMeta()}
        watermarkLedger={makeLedger()}
        maxStaleItems={2}
        seriesIds={["M002", "CA.BRENT", "CA.USDCNY"]}
      />,
    );

    const text = screen.getByTestId("macro-readiness").textContent ?? "";
    expect(text.indexOf("Brent crude oil futures close")).toBeLessThan(
      text.indexOf("DR007"),
    );
    expect(text).not.toContain("USD/CNY spot 数据 T+");
    expect(text).not.toContain("USD/CNH offshore");
    expect(text).not.toContain("Macro series outside latest response");
    expect(text).toContain("2026-04-10T09:05:00Z");
  });

  it("renders lagging series age and last successful ingest", () => {
    render(
      <MacroLatestReadinessBanner
        testId="macro-readiness"
        isLoading={false}
        isError={false}
        hasSeries
        meta={makeMeta()}
        watermarkLedger={makeLedger()}
        maxStaleItems={2}
        seriesIds={["M002", "CA.BRENT", "CA.USDCNY"]}
      />,
    );

    const banner = screen.getByTestId("macro-readiness");
    expect(banner).toHaveTextContent("Brent crude oil futures close");
    expect(banner).toHaveTextContent("T+62");
    expect(banner).toHaveTextContent("expired");
    expect(banner).toHaveTextContent("DR007");
    expect(banner).toHaveTextContent("T+48");
    expect(banner).toHaveTextContent("stale");
    expect(banner).toHaveTextContent("2026-04-10T09:05:00Z");
    expect(banner).not.toHaveTextContent("USD/CNY spot 数据 T+");
    expect(banner).not.toHaveTextContent("USD/CNH offshore");
    expect(banner).not.toHaveTextContent("Macro series outside latest response");
  });
});
