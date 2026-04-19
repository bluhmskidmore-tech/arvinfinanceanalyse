import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

/** Avoid jsdom canvas/ECharts teardown errors; do not assert chart pixels. */
vi.mock("../lib/echarts", () => ({
  __esModule: true,
  default: () => <div data-testid="credit-spread-echarts-stub" />,
}));

import { ApiClientProvider, createApiClient } from "../api/client";
import type { Numeric, ResultMeta } from "../api/contracts";
import { CreditSpreadView } from "../features/bond-analytics/components/CreditSpreadView";
import type {
  CreditSpreadAnalysisResponse,
  CreditSpreadMigrationResponse,
} from "../features/bond-analytics/types";
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
const ratio = (raw: number | null, precision?: number) => numeric(raw, "ratio", false, precision);
const bp = (raw: number | null, precision?: number) => numeric(raw, "bp", false, precision);
const dv01 = (raw: number | null, precision?: number) => numeric(raw, "dv01", false, precision);
const ratioAsBp = (raw: number | null, precision?: number) =>
  bp(raw === null ? null : raw * 10_000, precision);

function createResultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
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

function createCreditSpreadResult(
  overrides: Partial<CreditSpreadMigrationResponse> = {},
): CreditSpreadMigrationResponse {
  return {
    report_date: "2026-03-31",
    credit_bond_count: 42,
    credit_market_value: yuan(5_000_000_000),
    credit_weight: ratio(0.35, 2),
    spread_dv01: dv01(80_000),
    weighted_avg_spread: ratioAsBp(0.0085, 2),
    weighted_avg_spread_duration: ratio(3.2, 1),
    spread_scenarios: [
      {
        scenario_name: "spr_25w",
        spread_change_bp: bp(25, 0),
        pnl_impact: yuan(-1_200_000),
        oci_impact: yuan(-400_000),
        tpl_impact: yuan(-800_000),
      },
    ],
    migration_scenarios: [
      {
        scenario_name: "mig_aa_to_a",
        from_rating: "AA",
        to_rating: "A",
        affected_bonds: 2,
        affected_market_value: yuan(200_000_000),
        pnl_impact: yuan(-500_000),
      },
    ],
    oci_credit_exposure: yuan(3_000_000_000),
    oci_spread_dv01: dv01(50_000),
    oci_sensitivity_25bp: yuan(-750_000),
    warnings: [],
    computed_at: "2026-04-10T00:00:00Z",
    ...overrides,
  };
}

function createCreditSpreadDetailResult(
  overrides: Partial<CreditSpreadAnalysisResponse> = {},
): CreditSpreadAnalysisResponse {
  return {
    report_date: "2026-03-31",
    credit_bond_count: 42,
    total_credit_market_value: "5000000000",
    weighted_avg_spread_bps: "85.25",
    spread_term_structure: [
      {
        tenor_bucket: "3Y",
        avg_spread_bps: "72.50",
        min_spread_bps: "50.00",
        max_spread_bps: "95.00",
        bond_count: 12,
        total_market_value: "2200000000",
      },
      {
        tenor_bucket: "5Y",
        avg_spread_bps: "96.30",
        min_spread_bps: "70.00",
        max_spread_bps: "120.00",
        bond_count: 8,
        total_market_value: "1800000000",
      },
    ],
    top_spread_bonds: [
      {
        instrument_code: "CB-900",
        instrument_name: "高利差债A",
        rating: "AA",
        tenor_bucket: "5Y",
        ytm: "4.25000000",
        benchmark_yield: "3.10000000",
        credit_spread: "115.00000000",
        spread_duration: "4.20000000",
        spread_dv01: "42.00000000",
        market_value: "1000000000.00000000",
        weight: "0.20000000",
      },
    ],
    bottom_spread_bonds: [
      {
        instrument_code: "CB-100",
        instrument_name: "低利差债B",
        rating: "AAA",
        tenor_bucket: "3Y",
        ytm: "3.10000000",
        benchmark_yield: "3.00000000",
        credit_spread: "10.00000000",
        spread_duration: "2.10000000",
        spread_dv01: "10.00000000",
        market_value: "800000000.00000000",
        weight: "0.16000000",
      },
    ],
    historical_context: {
      current_spread_bps: "85.25000000",
      percentile_1y: "72.50000000",
      percentile_3y: "81.20000000",
      median_1y: "79.80000000",
      median_3y: "76.40000000",
      min_1y: "40.00000000",
      max_1y: "120.00000000",
    },
    warnings: [],
    computed_at: "2026-04-13T00:00:00Z",
    ...overrides,
  };
}

describe("CreditSpreadView", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads credit spread view with both legacy summary and detail sections", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsCreditSpreadMigration: vi.fn(async () => ({
        result_meta: createResultMeta(),
        result: createCreditSpreadResult({
          concentration_by_issuer: {
            dimension: "发行人",
            hhi: ratio(0.12, 2),
            top5_concentration: ratio(0.45, 2),
            top_items: [{ name: "发行人A", weight: ratio(0.2, 1), market_value: yuan(1_000_000_000) }],
          },
        }),
      })),
      getCreditSpreadAnalysisDetail: vi.fn(async () => ({
        result_meta: createResultMeta({
          result_kind: "credit_spread_analysis.detail",
        }),
        result: createCreditSpreadDetailResult(),
      })),
    };

    render(
      <ApiClientProvider client={client}>
        <CreditSpreadView reportDate="2026-03-31" />
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("credit-spread-shell-lead")).toHaveTextContent(
      "信用利差概览",
    );
    expect(screen.getByTestId("credit-spread-shell-lead")).toHaveTextContent(
      "不在前端补算正式风险指标",
    );
    expect(screen.getByTestId("credit-spread-scenario-lead")).toHaveTextContent(
      "利差冲击与信用分布",
    );
    expect(screen.getByTestId("credit-spread-detail-lead")).toHaveTextContent(
      "期限结构与集中度明细",
    );
    expect(await screen.findByText("信用债数量")).toBeInTheDocument();
    await waitFor(() =>
      expect(client.getBondAnalyticsCreditSpreadMigration).toHaveBeenCalledWith("2026-03-31"),
    );
    expect(client.getCreditSpreadAnalysisDetail).toHaveBeenCalledWith("2026-03-31");

    expect(screen.getByText("信用债市值")).toBeInTheDocument();
    expect(screen.getByText("Spread DV01 (万元/bp)")).toBeInTheDocument();
    expect(screen.getByText("加权平均利差（个券）")).toBeInTheDocument();

    expect(screen.getByText("利差情景冲击")).toBeInTheDocument();
    expect(screen.getByText("信用债分布")).toBeInTheDocument();
    expect(screen.getByText("spr_25w")).toBeInTheDocument();

    expect(screen.getByText("利差期限结构")).toBeInTheDocument();
    expect(screen.getByText("历史分位")).toBeInTheDocument();
    expect(screen.getByText("高利差债券")).toBeInTheDocument();
    expect(screen.getByText("低利差债券")).toBeInTheDocument();
    expect(screen.getByText("高利差债A")).toBeInTheDocument();
    expect(screen.getByText("低利差债B")).toBeInTheDocument();
    expect(screen.getByText("1年历史分位")).toBeInTheDocument();

    expect(screen.getByText("评级迁徙情景")).toBeInTheDocument();
    expect(screen.getByText("mig_aa_to_a")).toBeInTheDocument();

    expect(screen.getByText("信用集中度")).toBeInTheDocument();
  });

  it("keeps legacy summary visible and shows warning when detail endpoint is unavailable", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsCreditSpreadMigration: vi.fn(async () => ({
        result_meta: createResultMeta(),
        result: createCreditSpreadResult({
          warnings: ["示例：利差情景为分析占位"],
          spread_scenarios: [],
          migration_scenarios: [],
        }),
      })),
      getCreditSpreadAnalysisDetail: vi.fn(async () => {
        throw new Error(
          "Request failed: /api/credit-spread-analysis/detail?report_date=2026-03-31 (503)",
        );
      }),
    };

    render(
      <ApiClientProvider client={client}>
        <CreditSpreadView reportDate="2026-03-31" />
      </ApiClientProvider>,
    );

    expect(await screen.findByText("信用债数量")).toBeInTheDocument();
    expect(await screen.findByText("提示")).toBeInTheDocument();
    expect(screen.getByText("示例：利差情景为分析占位")).toBeInTheDocument();
    expect(screen.getByText("深度利差明细暂不可用：HTTP 503")).toBeInTheDocument();
  });
});
