import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { BondPortfolioHeadlinesPayload, ResultMeta } from "../api/contracts";
import { PortfolioHeadlinesView } from "../features/bond-analytics/components/PortfolioHeadlinesView";
import { formatRawAsNumeric } from "../utils/format";

function resultMeta(): ResultMeta {
  return {
    trace_id: "tr_portfolio",
    basis: "formal",
    result_kind: "bond_analytics.portfolio_headlines",
    formal_use_allowed: true,
    source_version: "sv",
    vendor_version: "vv",
    rule_version: "rv",
    cache_version: "cv",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T00:00:00Z",
  };
}

const yuan = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
const ratio = (raw: number) => formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false });
const pct = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });
const dv01 = (raw: number) => formatRawAsNumeric({ raw, unit: "dv01", sign_aware: false });

function payload(): BondPortfolioHeadlinesPayload {
  return {
    report_date: "2026-03-31",
    total_market_value: yuan(10_000_000_000),
    weighted_ytm: pct(0.03),
    weighted_duration: ratio(3.1),
    total_dv01: dv01(80_000),
    weighted_coupon: pct(0.028),
    credit_weight: ratio(0.4),
    issuer_hhi: ratio(0.12),
    issuer_top5_weight: ratio(0.5),
    bond_count: 20,
    by_asset_class: [
      {
        asset_class: "Rate",
        market_value: yuan(2_500_000_000),
        duration: ratio(3.2),
        dv01: dv01(10_000),
        weight: ratio(0.25),
      },
    ],
    warnings: [],
    computed_at: "2026-04-12T00:00:00Z",
  };
}

describe("PortfolioHeadlinesView", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders portfolio market values in yi yuan", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsPortfolioHeadlines: vi.fn(async () => ({
        result_meta: resultMeta(),
        result: payload(),
      })),
    };

    render(
      <ApiClientProvider client={client}>
        <PortfolioHeadlinesView reportDate="2026-03-31" />
      </ApiClientProvider>,
    );

    await waitFor(() =>
      expect(client.getBondAnalyticsPortfolioHeadlines).toHaveBeenCalledWith("2026-03-31"),
    );
    expect(await screen.findByText("100.00 亿")).toBeInTheDocument();
    expect(screen.getByText("25.00 亿")).toBeInTheDocument();
  });
});
