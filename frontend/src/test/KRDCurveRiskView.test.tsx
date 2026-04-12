import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

/** Avoid jsdom canvas/ECharts teardown errors; contract test targets copy + tables only. */
vi.mock("../lib/echarts", () => ({
  __esModule: true,
  default: () => <div data-testid="krd-echarts-stub" />,
}));

import { KRDCurveRiskView } from "../features/bond-analytics/components/KRDCurveRiskView";

function createResultMeta(overrides: Record<string, unknown> = {}) {
  return {
    trace_id: "tr_demo",
    basis: "formal",
    result_kind: "bond_analytics.krd_curve_risk",
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

function createKRDCurveRiskResult(overrides: Record<string, unknown> = {}) {
  return {
    report_date: "2026-03-31",
    portfolio_duration: "4.25",
    portfolio_modified_duration: "3.90",
    portfolio_dv01: "150000",
    portfolio_convexity: "22.5",
    krd_buckets: [
      { tenor: "3Y", krd: "0.8", dv01: "0.02", market_value_weight: "0.2" },
    ],
    scenarios: [
      {
        scenario_name: "parallel_10bp",
        scenario_description: "收益率曲线平行 +10bp",
        shocks: {},
        pnl_economic: "-500000",
        pnl_oci: "0",
        pnl_tpl: "0",
        rate_contribution: "0",
        convexity_contribution: "0",
        by_asset_class: {},
      },
    ],
    by_asset_class: [
      {
        asset_class: "rate",
        market_value: "800000000",
        duration: "4.1",
        dv01: "120000",
        weight: "0.65",
      },
    ],
    warnings: [],
    computed_at: "2026-04-10T00:00:00Z",
    ...overrides,
  };
}

describe("KRDCurveRiskView", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads KRD curve risk with KPI cards, scenarios table, by_asset_class table, and KRD section", async () => {
    let resolvePayload!: (v: { result_meta: ReturnType<typeof createResultMeta>; result: ReturnType<typeof createKRDCurveRiskResult> }) => void;
    const payloadPromise = new Promise<{
      result_meta: ReturnType<typeof createResultMeta>;
      result: ReturnType<typeof createKRDCurveRiskResult>;
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

    render(<KRDCurveRiskView reportDate="2026-03-31" />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryByText("组合久期")).not.toBeInTheDocument();

    resolvePayload({
      result_meta: createResultMeta(),
      result: createKRDCurveRiskResult(),
    });

    expect(await screen.findByText("组合久期")).toBeInTheDocument();
    expect(screen.getByText("修正久期")).toBeInTheDocument();
    expect(screen.getByText("DV01 (万元/bp)")).toBeInTheDocument();
    expect(screen.getByText("凸性")).toBeInTheDocument();

    expect(screen.getByText("KRD 分布")).toBeInTheDocument();
    expect(screen.getByText("情景冲击")).toBeInTheDocument();
    expect(screen.getByText("收益率曲线平行 +10bp")).toBeInTheDocument();

    expect(screen.getByText("按资产类别拆分")).toBeInTheDocument();
    expect(screen.getByText("rate")).toBeInTheDocument();
  });

  it("renders warning alert when warnings exist", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({
          result_meta: createResultMeta(),
          result: createKRDCurveRiskResult({
            warnings: ["示例：KRD 桶位数据为占位"],
            scenarios: [],
            by_asset_class: [],
            krd_buckets: [],
          }),
        }),
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<KRDCurveRiskView reportDate="2026-03-31" />);

    expect(await screen.findByText("提示")).toBeInTheDocument();
    expect(screen.getByText("示例：KRD 桶位数据为占位")).toBeInTheDocument();
  });
});
