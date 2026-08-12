import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: ({ option }: { option: unknown }) => (
    <pre data-testid="advanced-attribution-echarts-stub">{JSON.stringify(option)}</pre>
  ),
}));

import type {
  AdvancedAttributionSummary,
  CarryRollDownPayload,
  KRDAttributionPayload,
  Numeric,
  SpreadAttributionPayload,
} from "../api/contracts";
import type { DataSectionState } from "../components/DataSection.types";
import { AdvancedAttributionChart } from "../features/pnl-attribution/components/AdvancedAttributionChart";

const advancedChartSourcePath = resolve(
  process.cwd(),
  "src/features/pnl-attribution/components/AdvancedAttributionChart.tsx",
);
const advancedChartCssPath = resolve(
  process.cwd(),
  "src/features/pnl-attribution/components/AdvancedAttributionChart.css",
);

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

describe("AdvancedAttributionChart", () => {
  it("keeps component-level style debt from regressing", () => {
    const source = readFileSync(advancedChartSourcePath, "utf8");
    const stylesheet = readFileSync(advancedChartCssPath, "utf8");
    const inlineStylePattern = new RegExp("\\bstyle\\s*=");
    const hardcodedHexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const privateShadowPattern = /boxShadow\s*:|box-shadow\s*:\s*(?!none\b|var\()/;

    expect(source).not.toMatch(inlineStylePattern);
    expect(source).not.toMatch(hardcodedHexPattern);
    expect(source).not.toMatch(/rgba\(/);
    expect(source).not.toMatch(privateShadowPattern);
    expect(stylesheet).not.toMatch(hardcodedHexPattern);
    expect(stylesheet).not.toMatch(/rgba\(/);
    expect(stylesheet).not.toMatch(privateShadowPattern);
  });

  it("renders annualized static return without multiplying it twice", () => {
    const carryData: CarryRollDownPayload = {
      report_date: "2026-03-31",
      total_market_value: n(12_000_000_000),
      portfolio_carry: n(0.0185, "pct"),
      portfolio_rolldown: n(0.0042, "pct"),
      portfolio_static_return: n(0.0227, "pct"),
      total_carry_pnl: n(18_000_000),
      total_rolldown_pnl: n(4_000_000),
      total_static_pnl: n(22_000_000),
      ftp_rate: n(0.0215, "pct"),
      items: [],
    };
    const spreadData: SpreadAttributionPayload = {
      report_date: "2026-03-31",
      start_date: "2026-03-01",
      end_date: "2026-03-31",
      treasury_10y_start: n(0.0235, "pct"),
      treasury_10y_end: n(0.022, "pct"),
      treasury_10y_change: n(-15, "bp"),
      total_market_value: n(12_000_000_000),
      risk_coverage: riskCoverage(),
      portfolio_duration: n(3.8),
      total_treasury_effect: n(22_000_000),
      total_spread_effect: n(-4_000_000),
      total_price_change: n(18_000_000),
      primary_driver: "treasury",
      interpretation: "test",
      items: [],
    };
    const krdData: KRDAttributionPayload = {
      report_date: "2026-03-31",
      start_date: "2026-03-01",
      end_date: "2026-03-31",
      total_market_value: n(12_000_000_000),
      risk_coverage: riskCoverage(),
      portfolio_duration: n(3.8),
      portfolio_dv01: n(4_200_000),
      total_duration_effect: n(18_000_000),
      curve_shift_type: "bull_steepener",
      curve_interpretation: "test",
      max_contribution_tenor: "5Y",
      max_contribution_value: n(8_500_000),
      buckets: [],
    };
    const summary: AdvancedAttributionSummary = {
      report_date: "2026-03-31",
      portfolio_carry: n(0.0185, "pct"),
      portfolio_rolldown: n(0.0042, "pct"),
      static_return_annualized: n(0.0999, "pct"),
      treasury_effect_total: n(22_000_000),
      spread_effect_total: n(-4_000_000),
      spread_driver: "treasury",
      max_krd_tenor: "5Y",
      curve_shape_change: "bull_steepener",
      key_insights: [],
    };

    const okState: DataSectionState = { kind: "ok" };

    render(
      <AdvancedAttributionChart
        carryData={carryData}
        spreadData={spreadData}
        krdData={krdData}
        summaryData={summary}
        state={okState}
        onRetry={() => {}}
      />,
    );

    expect(screen.getByText("9.99%")).toBeInTheDocument();
    expect(screen.queryByText("326.88%")).not.toBeInTheDocument();
  });

  it("renders governed pct displays for carry and coupon fields", () => {
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
      items: [],
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
      buckets: [],
    };
    const summary: AdvancedAttributionSummary = {
      report_date: "2026-04-30",
      portfolio_carry: pct(0.00319, "+0.32%"),
      portfolio_rolldown: pct(-0.000022, "-0.00%"),
      static_return_annualized: pct(0.003168, "+0.32%"),
      treasury_effect_total: n(22_000_000),
      spread_effect_total: n(-4_000_000),
      spread_driver: "treasury",
      max_krd_tenor: "5Y",
      curve_shape_change: "bull_steepener",
      key_insights: [],
    };

    render(
      <AdvancedAttributionChart
        carryData={carryData}
        spreadData={spreadData}
        krdData={krdData}
        summaryData={summary}
        state={{ kind: "ok" }}
        onRetry={() => {}}
      />,
    );

    expect(screen.getAllByText("+0.32%").length).toBeGreaterThan(0);
    expect(screen.getByText("+2.58%")).toBeInTheDocument();
    expect(screen.getByText("-7 BP")).toBeInTheDocument();
    expect(screen.queryByText("-0 BP")).not.toBeInTheDocument();
    expect(screen.queryByText("0.03")).not.toBeInTheDocument();
  });

  it("keeps missing KRD values as null gaps and em-dash instead of zero", () => {
    const krdData: KRDAttributionPayload = {
      report_date: "2026-04-30",
      start_date: "2026-03-31",
      end_date: "2026-04-30",
      total_market_value: n(12_000_000_000),
      risk_coverage: riskCoverage(),
      portfolio_duration: n(3.8),
      portfolio_dv01: n(null),
      total_duration_effect: n(18_000_000),
      curve_shift_type: "bull_steepener",
      curve_interpretation: "test",
      max_contribution_tenor: "5Y",
      max_contribution_value: n(8_500_000),
      buckets: [
        {
          tenor: "1Y",
          tenor_years: n(1),
          market_value: n(null),
          weight: n(null),
          bond_count: 3,
          bucket_duration: n(0.9),
          krd: n(0.1),
          yield_change: n(null, "bp"),
          duration_contribution: n(null),
          contribution_pct: n(null, "pct"),
        },
        {
          tenor: "5Y",
          tenor_years: n(5),
          market_value: n(1_000_000_000),
          weight: n(40.0),
          bond_count: 5,
          bucket_duration: n(4.5),
          krd: n(1.2),
          yield_change: n(-8, "bp"),
          duration_contribution: n(18_000_000),
          contribution_pct: n(0.6, "pct"),
        },
      ],
    };

    render(
      <AdvancedAttributionChart
        carryData={null}
        spreadData={null}
        krdData={krdData}
        summaryData={null}
        state={{ kind: "ok" }}
        onRetry={() => {}}
      />,
    );

    const options = screen
      .getAllByTestId("advanced-attribution-echarts-stub")
      .map((node) => JSON.parse(node.textContent ?? "{}"));
    const krdOption = options.find((option) =>
      option.series?.some((series: { name?: string }) => series.name === "久期贡献"),
    );
    const contribSeries = krdOption.series.find(
      (series: { name?: string }) => series.name === "久期贡献",
    );
    const contribValues = contribSeries.data.map((item: { value: number | null }) => item.value);
    expect(contribValues).toEqual([null, 0.18]);

    const compareOption = options.find((option) =>
      option.series?.some((series: { name?: string }) => series.name === "市值占比"),
    );
    const weightSeries = compareOption.series.find(
      (series: { name?: string }) => series.name === "市值占比",
    );
    expect(weightSeries.data).toEqual([null, 40]);

    // DV01 raw 缺失显示 —，不显示 "0 万"。
    expect(screen.queryByText("0 万")).not.toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});
