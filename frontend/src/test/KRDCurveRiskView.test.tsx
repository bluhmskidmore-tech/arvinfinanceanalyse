import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

/** Avoid jsdom canvas/ECharts teardown errors; contract test targets copy + tables only. */
vi.mock("../lib/echarts", () => ({
  __esModule: true,
  default: () => <div data-testid="krd-echarts-stub" />,
}));

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ResultMeta } from "../api/contracts";
import { KRDCurveRiskView } from "../features/bond-analytics/components/KRDCurveRiskView";

function createResultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
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
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsKrdCurveRisk: vi.fn(async () => ({
        result_meta: createResultMeta(),
        result: createKRDCurveRiskResult(),
      })),
    };

    render(
      <ApiClientProvider client={client}>
        <KRDCurveRiskView reportDate="2026-03-31" />
      </ApiClientProvider>,
    );

    await waitFor(() =>
      expect(client.getBondAnalyticsKrdCurveRisk).toHaveBeenCalledWith("2026-03-31"),
    );

    expect(await screen.findByTestId("krd-curve-risk-shell-lead")).toHaveTextContent(
      "曲线风险概览",
    );
    expect(screen.getByTestId("krd-curve-risk-shell-lead")).toHaveTextContent(
      "不在前端补算正式风险指标",
    );
    expect(screen.getByTestId("krd-curve-risk-buckets-lead")).toHaveTextContent(
      "KRD 桶位与情景冲击",
    );
    expect(screen.getByTestId("krd-curve-risk-asset-lead")).toHaveTextContent(
      "资产类别风险拆分",
    );
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
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsKrdCurveRisk: vi.fn(async () => ({
        result_meta: createResultMeta(),
        result: createKRDCurveRiskResult({
          warnings: ["示例：KRD 桶位数据为占位"],
          scenarios: [],
          by_asset_class: [],
          krd_buckets: [],
        }),
      })),
    };

    render(
      <ApiClientProvider client={client}>
        <KRDCurveRiskView reportDate="2026-03-31" />
      </ApiClientProvider>,
    );

    expect(await screen.findByText("提示")).toBeInTheDocument();
    expect(screen.getByText("示例：KRD 桶位数据为占位")).toBeInTheDocument();
  });
});
