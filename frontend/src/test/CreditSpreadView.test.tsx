import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

/** Avoid jsdom canvas/ECharts teardown errors; do not assert chart pixels. */
vi.mock("../lib/echarts", () => ({
  __esModule: true,
  default: () => <div data-testid="credit-spread-echarts-stub" />,
}));

import { CreditSpreadView } from "../features/bond-analytics/components/CreditSpreadView";

function createResultMeta(overrides: Record<string, unknown> = {}) {
  return {
    trace_id: "tr_demo",
    basis: "formal",
    result_kind: "bond_analytics.credit_spread_migration",
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

function createCreditSpreadResult(overrides: Record<string, unknown> = {}) {
  return {
    report_date: "2026-03-31",
    credit_bond_count: 42,
    credit_market_value: "5000000000",
    credit_weight: "0.35",
    spread_dv01: "80000",
    weighted_avg_spread: "0.0085",
    weighted_avg_spread_duration: "3.2",
    spread_scenarios: [
      {
        scenario_name: "spr_25w",
        spread_change_bp: 25,
        pnl_impact: "-1200000",
        oci_impact: "-400000",
        tpl_impact: "-800000",
      },
    ],
    migration_scenarios: [
      {
        scenario_name: "mig_aa_to_a",
        from_rating: "AA",
        to_rating: "A",
        affected_bonds: 2,
        affected_market_value: "200000000",
        pnl_impact: "-500000",
      },
    ],
    oci_credit_exposure: "3000000000",
    oci_spread_dv01: "50000",
    oci_sensitivity_25bp: "-750000",
    warnings: [],
    computed_at: "2026-04-10T00:00:00Z",
    ...overrides,
  };
}

describe("CreditSpreadView", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads credit spread view with KPI cards, spread and migration tables, and concentration when present", async () => {
    let resolvePayload!: (v: { result_meta: ReturnType<typeof createResultMeta>; result: ReturnType<typeof createCreditSpreadResult> }) => void;
    const payloadPromise = new Promise<{
      result_meta: ReturnType<typeof createResultMeta>;
      result: ReturnType<typeof createCreditSpreadResult>;
    }>((resolve) => {
      resolvePayload = resolve;
    });

    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => payloadPromise,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<CreditSpreadView reportDate="2026-03-31" />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const firstUrl = String(
      fetchMock.mock.calls[0]?.[0] instanceof Request
        ? fetchMock.mock.calls[0][0].url
        : fetchMock.mock.calls[0]?.[0],
    );
    expect(firstUrl).toContain("/api/bond-analytics/credit-spread-migration");

    expect(screen.queryByText("信用债数量")).not.toBeInTheDocument();

    resolvePayload({
      result_meta: createResultMeta(),
      result: createCreditSpreadResult({
        concentration_by_issuer: {
          dimension: "发行人",
          hhi: "0.12",
          top5_concentration: "0.45",
          top_items: [{ name: "发行人A", weight: "0.2", market_value: "1000000000" }],
        },
      }),
    });

    expect(await screen.findByText("信用债数量")).toBeInTheDocument();
    expect(screen.getByText("信用债市值")).toBeInTheDocument();
    expect(screen.getByText("Spread DV01 (万元/bp)")).toBeInTheDocument();
    expect(screen.getByText("加权平均利差")).toBeInTheDocument();

    expect(screen.getByText("利差情景冲击")).toBeInTheDocument();
    expect(screen.getByText("信用债分布")).toBeInTheDocument();
    expect(screen.getByText("spr_25w")).toBeInTheDocument();

    expect(screen.getByText("评级迁徙情景")).toBeInTheDocument();
    expect(screen.getByText("mig_aa_to_a")).toBeInTheDocument();

    expect(screen.getByText("信用集中度")).toBeInTheDocument();
  });

  it("renders warning alert when warnings exist", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({
          result_meta: createResultMeta(),
          result: createCreditSpreadResult({
            warnings: ["示例：利差情景为分析占位"],
            spread_scenarios: [],
            migration_scenarios: [],
          }),
        }),
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<CreditSpreadView reportDate="2026-03-31" />);

    expect(await screen.findByText("提示")).toBeInTheDocument();
    expect(screen.getByText("示例：利差情景为分析占位")).toBeInTheDocument();
  });
});
