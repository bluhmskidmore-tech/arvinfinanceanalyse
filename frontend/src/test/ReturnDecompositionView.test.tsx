import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

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
        asset_class: "Rates",
        carry: yuan(1_000_000),
        roll_down: yuan(2_000_000),
        rate_effect: yuan(0),
        spread_effect: yuan(0),
        convexity_effect: yuan(10_000),
        trading: yuan(0),
        total: yuan(3_000_000),
        bond_count: 3,
        market_value: yuan(100_000_000),
      },
    ],
    by_accounting_class: [
      {
        asset_class: "FVTPL",
        carry: yuan(500_000),
        roll_down: yuan(0),
        rate_effect: yuan(0),
        spread_effect: yuan(0),
        convexity_effect: yuan(0),
        trading: yuan(0),
        total: yuan(500_000),
        bond_count: 1,
        market_value: yuan(50_000_000),
      },
    ],
    bond_details: [
      {
        bond_code: "019547",
        bond_name: null,
        asset_class: "Rates",
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

  it("renders governed content and provenance for the default payload", async () => {
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

    expect(await screen.findByText("Return Decomposition")).toBeInTheDocument();
    expect(screen.getByText("Effects")).toBeInTheDocument();
    expect(screen.getByText("Reconciliation")).toBeInTheDocument();
    expect(screen.getByTestId("return-decomposition-period")).toHaveTextContent("2026-03-31");
    expect(screen.getByTestId("return-decomposition-period")).toHaveTextContent("MoM");
    expect(screen.getByTestId("return-decomposition-computed-at")).toHaveTextContent("2026-04-10T00:00:00Z");
    expect(screen.getByTestId("return-decomposition-bond-count")).toHaveTextContent("3");
    expect(screen.getByTestId("return-decomposition-total-mv")).toBeInTheDocument();
    expect(screen.getByTestId("return-decomposition-by-accounting-class")).toHaveTextContent("FVTPL");
    expect(screen.getByTestId("return-decomposition-result-meta")).toHaveTextContent("vendor_status");
    expect(screen.getAllByText("Rates").length).toBeGreaterThan(0);
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

  it("renders bond details after expanding the collapse", async () => {
    const user = userEvent.setup();
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

    expect(await screen.findByTestId("return-decomposition-bond-details-collapse")).toBeInTheDocument();
    await user.click(screen.getByText("鍒哥骇鎷嗚В锛堟寜鍒告槑缁嗭級"));

    const table = await screen.findByTestId("return-decomposition-bond-details-table");
    expect(within(table).getByText("019547")).toBeInTheDocument();
    expect(within(table).getByText("Rates")).toBeInTheDocument();
    expect(within(table).getByText("AC")).toBeInTheDocument();
  });

  it("renders backend warnings when present", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsReturnDecomposition: vi.fn(async () => ({
        result_meta: createResultMeta({ quality_flag: "warning" }),
        result: createReturnDecompositionResult({
          warnings: ["recon gap warning"],
        }),
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
    expect(await screen.findByText("recon gap warning")).toBeInTheDocument();
  });

  it("surfaces degraded provenance when result_meta is stale or fallback-backed", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsReturnDecomposition: vi.fn(async () => ({
        result_meta: createResultMeta({
          quality_flag: "warning",
          vendor_status: "vendor_stale",
          fallback_mode: "latest_snapshot",
        }),
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
    expect(await screen.findByTestId("return-decomposition-result-meta-alert")).toHaveTextContent(
      "vendor_status=vendor_stale",
    );
    expect(screen.getByTestId("return-decomposition-result-meta-alert")).toHaveTextContent(
      "fallback_mode=latest_snapshot",
    );
    expect(screen.getByTestId("return-decomposition-result-meta")).toHaveTextContent("vendor_stale");
  });
});
