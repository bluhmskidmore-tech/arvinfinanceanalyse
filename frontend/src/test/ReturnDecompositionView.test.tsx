import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

/** Avoid jsdom canvas/ECharts teardown flakiness; assertions use titles + tables + KPIs. */
vi.mock("../lib/echarts", () => ({
  __esModule: true,
  default: () => <div data-testid="return-decomp-echarts-stub" />,
}));

import { ReturnDecompositionView } from "../features/bond-analytics/components/ReturnDecompositionView";
import { ApiClientProvider, createApiClient } from "../api/client";
import type { ReturnDecompositionResponse } from "../features/bond-analytics/types";

function createResultMeta(overrides: Record<string, unknown> = {}) {
  return {
    trace_id: "tr_demo",
    basis: "formal",
    result_kind: "bond_analytics.return_decomposition",
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

function createReturnDecompositionResult(
  overrides: Partial<ReturnDecompositionResponse> = {},
): ReturnDecompositionResponse {
  return {
    report_date: "2026-03-31",
    period_type: "MoM",
    period_start: "2026-03-01",
    period_end: "2026-03-31",
    carry: "1000000",
    roll_down: "2000000",
    rate_effect: "0",
    spread_effect: "0",
    trading: "0",
    fx_effect: "0",
    convexity_effect: "0",
    explained_pnl: "3000000",
    explained_pnl_accounting: "2800000",
    explained_pnl_economic: "3200000",
    oci_reserve_impact: "500000",
    actual_pnl: "3000000",
    recon_error: "0",
    recon_error_pct: "0",
    by_asset_class: [
      {
        asset_class: "利率债",
        carry: "1000000",
        roll_down: "2000000",
        rate_effect: "0",
        spread_effect: "0",
        fx_effect: "0",
        convexity_effect: "10000",
        trading: "0",
        total: "3000000",
        bond_count: 3,
        market_value: "100000000",
      },
    ],
    by_accounting_class: [],
    bond_details: [
      {
        bond_code: "019547",
        bond_name: null,
        asset_class: "利率债",
        accounting_class: "AC",
        market_value: "100000000",
        carry: "1000000",
        roll_down: "2000000",
        rate_effect: "0",
        spread_effect: "0",
        convexity_effect: "10000",
        trading: "0",
        total: "3000000",
        explained_for_recon: "3000000",
        economic_only_effects: "2010000",
      },
    ],
    bond_count: 3,
    total_market_value: "100000000",
    warnings: [],
    computed_at: "2026-04-10T00:00:00Z",
    ...overrides,
  };
}

describe("ReturnDecompositionView", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("transitions from loading to content, shows key statistics, by_asset_class table, and chart section", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsReturnDecomposition: vi.fn(async () => ({
        result_meta: createResultMeta(),
        result: createReturnDecompositionResult(),
      })),
    };

    render(
      <ApiClientProvider client={client}>
        <ReturnDecompositionView reportDate="2026-03-31" periodType="MoM" />
      </ApiClientProvider>,
    );

    await waitFor(() =>
      expect(client.getBondAnalyticsReturnDecomposition).toHaveBeenCalledWith("2026-03-31", "MoM"),
    );

    expect(await screen.findByText("经济口径合计")).toBeInTheDocument();
    expect(screen.getByText("OCI 未入表影响")).toBeInTheDocument();
    expect(screen.getByText("会计口径（损益表）")).toBeInTheDocument();

    expect(screen.getByText("收益效应分解")).toBeInTheDocument();
    expect(screen.getByText("按资产类别拆分")).toBeInTheDocument();
    expect(screen.getByText("利率债")).toBeInTheDocument();
  });

  it("renders warning alert when warnings exist", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsReturnDecomposition: vi.fn(async () => ({
        result_meta: createResultMeta({ quality_flag: "warning" }),
        result: createReturnDecompositionResult({
          warnings: ["示例：对账口径存在缺口"],
        }),
      })),
    };

    render(
      <ApiClientProvider client={client}>
        <ReturnDecompositionView reportDate="2026-03-31" periodType="MoM" />
      </ApiClientProvider>,
    );

    expect(await screen.findByText("提示")).toBeInTheDocument();
    expect(screen.getByText("示例：对账口径存在缺口")).toBeInTheDocument();
  });
});
