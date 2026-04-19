import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

/** Avoid jsdom canvas/ECharts teardown flakiness; assertions use titles + tables + KPIs. */
vi.mock("../lib/echarts", () => ({
  __esModule: true,
  default: () => <div data-testid="return-decomp-echarts-stub" />,
}));

import { ReturnDecompositionView } from "../features/bond-analytics/components/ReturnDecompositionView";
import { ApiClientProvider, createApiClient } from "../api/client";
import type { Numeric, ResultMeta } from "../api/contracts";
import type { ReturnDecompositionResponse } from "../features/bond-analytics/types";
import { formatRawAsNumeric } from "../utils/format";

function numeric(
  raw: number | null,
  unit: Numeric["unit"],
  signAware = false,
  precision?: number,
): Numeric {
  return formatRawAsNumeric({
    raw,
    unit,
    sign_aware: signAware,
    ...(precision === undefined ? {} : { precision }),
  });
}

const yuan = (raw: number | null) => numeric(raw, "yuan", true);
const pct = (raw: number | null) => numeric(raw, "pct");

function createResultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
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
    carry: yuan(1_000_000),
    roll_down: yuan(2_000_000),
    rate_effect: yuan(0),
    spread_effect: yuan(0),
    trading: yuan(0),
    fx_effect: yuan(0),
    convexity_effect: yuan(0),
    explained_pnl: yuan(3_000_000),
    explained_pnl_accounting: yuan(2_800_000),
    explained_pnl_economic: yuan(3_200_000),
    oci_reserve_impact: yuan(500_000),
    actual_pnl: yuan(3_000_000),
    recon_error: yuan(0),
    recon_error_pct: pct(0),
    by_asset_class: [
      {
        asset_class: "利率债",
        carry: yuan(1_000_000),
        roll_down: yuan(2_000_000),
        rate_effect: yuan(0),
        spread_effect: yuan(0),
        fx_effect: yuan(0),
        convexity_effect: yuan(10_000),
        trading: yuan(0),
        total: yuan(3_000_000),
        bond_count: 3,
        market_value: yuan(100_000_000),
      },
    ],
    by_accounting_class: [],
    bond_details: [
      {
        bond_code: "019547",
        bond_name: null,
        asset_class: "利率债",
        accounting_class: "AC",
        market_value: yuan(100_000_000),
        carry: yuan(1_000_000),
        roll_down: yuan(2_000_000),
        rate_effect: yuan(0),
        spread_effect: yuan(0),
        convexity_effect: yuan(10_000),
        trading: yuan(0),
        total: yuan(3_000_000),
        explained_for_recon: yuan(3_000_000),
        economic_only_effects: yuan(2_010_000),
      },
    ],
    bond_count: 3,
    total_market_value: yuan(100_000_000),
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

    expect(await screen.findByTestId("return-decomposition-shell-lead")).toHaveTextContent(
      "收益分解概览",
    );
    expect(screen.getByTestId("return-decomposition-shell-lead")).toHaveTextContent(
      "不在前端重算正式损益",
    );
    expect(screen.getByTestId("return-decomposition-effects-lead")).toHaveTextContent(
      "收益效果瀑布",
    );
    expect(screen.getByTestId("return-decomposition-recon-lead")).toHaveTextContent(
      "收益分解对账",
    );
    expect(await screen.findByText("经济口径合计")).toBeInTheDocument();
    expect(screen.getByText("OCI 未入表影响")).toBeInTheDocument();
    expect(screen.getByText("会计口径（损益表）")).toBeInTheDocument();

    expect(screen.getByText("收益效应分解")).toBeInTheDocument();
    expect(screen.getByText("按资产类别拆分")).toBeInTheDocument();
    expect(screen.getByText("利率债")).toBeInTheDocument();
  });

  it("forwards non-default asset/accounting filters as the optional API options bag", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsReturnDecomposition: vi.fn(async () => ({
        result_meta: createResultMeta(),
        result: createReturnDecompositionResult(),
      })),
    };

    render(
      <ApiClientProvider client={client}>
        <ReturnDecompositionView
          reportDate="2026-03-31"
          periodType="MoM"
          assetClass="rate"
          accountingClass="OCI"
        />
      </ApiClientProvider>,
    );

    await waitFor(() =>
      expect(client.getBondAnalyticsReturnDecomposition).toHaveBeenCalledWith("2026-03-31", "MoM", {
        assetClass: "rate",
        accountingClass: "OCI",
      }),
    );
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
