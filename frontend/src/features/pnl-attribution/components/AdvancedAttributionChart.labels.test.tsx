import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../../lib/echarts", () => ({
  default: () => <div data-testid="advanced-attribution-echarts-stub" />,
}));

import type {
  CarryRollDownPayload,
  KRDAttributionPayload,
  Numeric,
  SpreadAttributionPayload,
} from "../../../api/contracts";
import { AdvancedAttributionChart } from "./AdvancedAttributionChart";

function n(raw: number | null, unit: Numeric["unit"] = "yuan"): Numeric {
  return {
    raw,
    unit,
    display: "",
    precision: 2,
    sign_aware: false,
  };
}

function pct(raw: number | null, display: string): Numeric {
  return {
    raw,
    unit: "pct",
    display,
    precision: 2,
    sign_aware: true,
  };
}

function riskCoverage() {
  return {
    total_row_count: 100,
    covered_row_count: 100,
    excluded_row_count: 0,
    total_market_value: n(12_000_000_000),
    covered_market_value: n(12_000_000_000),
    excluded_market_value: n(0),
    coverage_pct: pct(1, "100.00%"),
    excluded_pct: pct(0, "0.00%"),
    exclusions: [],
  };
}

const CONTRIBUTION_PCT_NOTE =
  "占比按各效应绝对值计算，方向相反时合计可能超过 100%";

describe("AdvancedAttributionChart caliber labels", () => {
  it("surfaces monthly and annualized carry/rolldown labels", () => {
    const carryData: CarryRollDownPayload = {
      report_date: "2026-04-30",
      total_market_value: n(12_000_000_000),
      portfolio_carry: pct(0.00319, "+0.32%"),
      portfolio_rolldown: pct(-0.000022, "-0.00%"),
      portfolio_static_return: pct(0.003168, "+0.32%"),
      total_carry_pnl: n(18_000_000),
      total_rolldown_pnl: n(4_000_000),
      total_static_pnl: n(22_000_000),
      ftp_rate: pct(0.0175, "+1.75%"),
      items: [
        {
          category: "credit",
          category_type: "asset",
          market_value: n(1_000_000_000),
          weight: n(0.1),
          coupon_rate: pct(0.025801, "+2.58%"),
          ytm: pct(0.026, "+2.60%"),
          funding_cost: pct(0.0175, "+1.75%"),
          carry: pct(0.008301, "+0.83%"),
          carry_pnl: n(6_900_000),
          duration: n(3.2),
          curve_slope: n(0.02, "bp"),
          rolldown: pct(-0.000016, "-0.00%"),
          rolldown_pnl: n(-13_000),
          static_return: pct(0.008285, "+0.83%"),
          static_pnl: n(6_887_000),
        },
      ],
    };

    render(
      <AdvancedAttributionChart
        carryData={carryData}
        spreadData={null}
        krdData={null}
        state={{ kind: "ok" }}
        onRetry={() => {}}
      />,
    );

    expect(screen.getByText("组合 Carry（年化）")).toBeInTheDocument();
    expect(screen.getByText("组合 Roll-down（年化）")).toBeInTheDocument();
    expect(screen.getByText("静态收益（年化）")).toBeInTheDocument();
    expect(screen.getByText("Carry 合计（月度估算）")).toBeInTheDocument();
    expect(screen.getByText("Roll-down 合计（月度估算）")).toBeInTheDocument();
    expect(screen.getByText("Static 合计（月度估算）")).toBeInTheDocument();
    expect(screen.getByText("Carry%（年化）")).toBeInTheDocument();
    expect(screen.getByText("Roll%（年化）")).toBeInTheDocument();
    expect(screen.getByText("Carry（月度估算）")).toBeInTheDocument();
    expect(screen.getByText("Roll（月度估算）")).toBeInTheDocument();
    expect(screen.getByText("Static（月度估算）")).toBeInTheDocument();
  });

  it("surfaces contribution_pct caliber notes for spread and krd", () => {
    const spreadData: SpreadAttributionPayload = {
      report_date: "2026-04-30",
      start_date: "2026-03-31",
      end_date: "2026-04-30",
      treasury_10y_start: pct(0.018, "+1.80%"),
      treasury_10y_end: pct(0.0179, "+1.79%"),
      treasury_10y_change: n(-6.98, "bp"),
      total_market_value: n(12_000_000_000),
      risk_coverage: riskCoverage(),
      portfolio_duration: n(3.8),
      total_treasury_effect: n(22_000_000),
      total_spread_effect: n(-4_000_000),
      total_price_change: n(18_000_000),
      primary_driver: "treasury",
      interpretation: "test",
      items: [
        {
          category: "credit",
          category_type: "asset",
          market_value: n(1_000_000_000),
          duration: n(3.2),
          weight: n(0.1),
          yield_change: n(-5, "bp"),
          treasury_change: n(-4, "bp"),
          spread_change: n(-1, "bp"),
          treasury_effect: n(12_000_000),
          spread_effect: n(-2_000_000),
          total_price_effect: n(10_000_000),
          treasury_contribution_pct: pct(0.6, "60.0%"),
          spread_contribution_pct: pct(0.4, "40.0%"),
        },
      ],
    };
    const krdData: KRDAttributionPayload = {
      report_date: "2026-04-30",
      start_date: "2026-03-31",
      end_date: "2026-04-30",
      total_market_value: n(12_000_000_000),
      risk_coverage: riskCoverage(),
      portfolio_duration: n(3.8),
      portfolio_dv01: n(4_200_000),
      total_duration_effect: n(18_000_000),
      curve_shift_type: "bull_steepener",
      curve_interpretation: "test",
      max_contribution_tenor: "5Y",
      max_contribution_value: n(8_500_000),
      buckets: [
        {
          tenor: "3-5Y",
          tenor_years: n(4),
          market_value: n(4_500_000_000),
          weight: n(37.5),
          bond_count: 55,
          bucket_duration: n(4.1),
          krd: n(3.6),
          yield_change: n(-9, "bp"),
          duration_contribution: n(8_500_000),
          contribution_pct: pct(0.472, "47.2%"),
        },
      ],
    };

    render(
      <AdvancedAttributionChart
        carryData={null}
        spreadData={spreadData}
        krdData={krdData}
        state={{ kind: "ok" }}
        onRetry={() => {}}
      />,
    );

    expect(screen.getAllByText(CONTRIBUTION_PCT_NOTE)).toHaveLength(2);
    expect(screen.getByTestId("spread-contribution-pct-caliber-note")).toHaveTextContent(
      CONTRIBUTION_PCT_NOTE,
    );
    expect(screen.getByTestId("krd-contribution-pct-caliber-note")).toHaveTextContent(
      CONTRIBUTION_PCT_NOTE,
    );
    expect(screen.getByText("国债贡献占比%")).toBeInTheDocument();
    expect(screen.getByText("利差贡献占比%")).toBeInTheDocument();
    expect(screen.getByText("贡献占比%")).toBeInTheDocument();
  });

  it("renders krd bucket weight as percent points from decimal-ratio raw", () => {
    const krdData: KRDAttributionPayload = {
      report_date: "2026-04-30",
      start_date: "2026-03-31",
      end_date: "2026-04-30",
      total_market_value: n(12_000_000_000),
      risk_coverage: riskCoverage(),
      portfolio_duration: n(3.8),
      portfolio_dv01: n(4_200_000),
      total_duration_effect: n(18_000_000),
      curve_shift_type: "bull_steepener",
      curve_interpretation: "test",
      max_contribution_tenor: "5Y",
      max_contribution_value: n(8_500_000),
      buckets: [
        {
          tenor: "3-5Y",
          tenor_years: n(4),
          market_value: n(4_500_000_000),
          // weight 契约：unit="pct"，raw 为小数比率；display 置空以覆盖 raw×100 回退路径。
          weight: pct(0.235, ""),
          bond_count: 55,
          bucket_duration: n(4.1),
          krd: n(3.6),
          yield_change: n(-9, "bp"),
          duration_contribution: n(8_500_000),
          contribution_pct: pct(0.472, "47.2%"),
        },
      ],
    };

    render(
      <AdvancedAttributionChart
        carryData={null}
        spreadData={null}
        krdData={krdData}
        state={{ kind: "ok" }}
        onRetry={() => {}}
      />,
    );

    expect(screen.getByText("23.50%")).toBeInTheDocument();
    // 回归保护：raw=0.235 不得按旧写法 toFixed(1) 渲染成缩小 100 倍的 "0.2"。
    expect(screen.queryByText("0.2")).not.toBeInTheDocument();
    expect(screen.getByText("占比")).toBeInTheDocument();
    expect(screen.getByText("Δyield(bp)")).toBeInTheDocument();
  });
});
