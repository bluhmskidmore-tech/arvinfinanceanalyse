import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

let lastChartOption: unknown = null;

vi.mock("../lib/echarts", () => ({
  default: ({ option }: { option: unknown }) => {
    lastChartOption = option;
    return <pre data-testid="tpl-market-echarts-stub">echarts</pre>;
  },
}));

import type { Numeric, ProductCategoryPnlRow, TPLMarketCorrelationPayload } from "../api/contracts";
import type { DataSectionState } from "../components/DataSection.types";
import { TPLMarketChart } from "../features/pnl-attribution/components/TPLMarketChart";

function num(
  raw: number | null,
  unit: Numeric["unit"] = "yuan",
  display = "",
  overrides: Partial<Numeric> = {},
): Numeric {
  return {
    raw,
    unit,
    display,
    precision: 2,
    sign_aware: false,
    ...overrides,
  };
}

function productCategoryTplRow(partial: Partial<ProductCategoryPnlRow> = {}): ProductCategoryPnlRow {
  return {
    category_id: "bond_tpl",
    category_name: "TPL",
    side: "asset",
    level: 1,
    view: "monthly",
    report_date: "2026-03-31",
    baseline_ftp_rate_pct: "1.60",
    cnx_scale: "86507000000",
    cny_scale: "86605000000",
    foreign_scale: "-98000000",
    cnx_cash: "211000000",
    cny_cash: "211000000",
    foreign_cash: "0",
    cny_ftp: "114000000",
    foreign_ftp: "0",
    cny_net: "97000000",
    foreign_net: "1000000",
    business_net_income: "98000000",
    weighted_yield: "2.97",
    is_total: false,
    children: [],
    ...partial,
  };
}

function chartOption(): {
  tooltip?: { formatter?: (params: Array<{ dataIndex: number; seriesName: string }>) => string };
  series: Array<{ name: string; data: Array<number | null>; smooth?: boolean }>;
} {
  return lastChartOption as {
    tooltip?: { formatter?: (params: Array<{ dataIndex: number; seriesName: string }>) => string };
    series: Array<{ name: string; data: Array<number | null>; smooth?: boolean }>;
  };
}

describe("TPLMarketChart", () => {
  it("renders cumulative treasury change in bp", () => {
    const data = {
      start_period: "2026-02",
      end_period: "2026-03",
      num_periods: 2,
      correlation_coefficient: num(-0.62, "ratio"),
      correlation_interpretation: "test",
      total_tpl_fv_change: num(42_000_000),
      avg_treasury_10y_change: num(-7.5, "bp"),
      treasury_10y_total_change_bp: num(-15.0, "bp"),
      analysis_summary: "summary",
      data_points: [
        {
          period: "2026-02",
          period_label: "2026年02月",
          tpl_fair_value_change: num(10_000_000),
          tpl_total_pnl: num(10_000_000),
          tpl_scale: num(1_000_000_000),
          treasury_10y: num(0.0235, "pct", "+2.35%"),
          treasury_10y_change: num(null, "bp"),
          dr007: num(null, "pct"),
        },
        {
          period: "2026-03",
          period_label: "2026年03月",
          tpl_fair_value_change: num(32_000_000),
          tpl_total_pnl: num(32_000_000),
          tpl_scale: num(1_100_000_000),
          treasury_10y: num(0.022, "pct", "+2.20%"),
          treasury_10y_change: num(-15.0, "bp"),
          dr007: num(null, "pct"),
        },
      ],
    } as unknown as TPLMarketCorrelationPayload;

    const okState: DataSectionState = { kind: "ok" };

    render(<TPLMarketChart data={data} state={okState} onRetry={() => {}} />);

    expect(screen.getByText("-15.0 BP")).toBeInTheDocument();
    expect(screen.getByText("+2.20%")).toBeInTheDocument();
    expect(screen.getByTestId("tpl-market-echarts-stub")).toBeInTheDocument();
  });

  it("prefers raw_text for cumulative tpl display and direction while keeping chart scaling on raw", () => {
    const data = {
      start_period: "2026-03",
      end_period: "2026-03",
      num_periods: 1,
      correlation_coefficient: num(-0.62, "ratio"),
      correlation_interpretation: "test",
      total_tpl_fv_change: num(42_000_000, "yuan", "+42,000,000.00", {
        raw_text: "-100500000",
        sign_aware: true,
      }),
      avg_treasury_10y_change: num(-7.5, "bp"),
      treasury_10y_total_change_bp: num(-7.5, "bp"),
      analysis_summary: "summary",
      data_points: [
        {
          period: "2026-03",
          period_label: "2026年03月",
          tpl_fair_value_change: num(100_400_000, "yuan", "+100,400,000.00", {
            raw_text: "100500000",
            sign_aware: true,
          }),
          tpl_total_pnl: num(100_400_000, "yuan", "+100,400,000.00", {
            raw_text: "100500000",
            sign_aware: true,
          }),
          tpl_scale: num(1_100_000_000),
          treasury_10y: num(0.022, "pct", "+2.20%"),
          treasury_10y_change: num(-7.5, "bp"),
          dr007: num(0.017, "pct", "+1.70%"),
        },
      ],
    } as unknown as TPLMarketCorrelationPayload;

    render(<TPLMarketChart data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    const totalValue = screen.getByText("-1.01 亿");
    expect(totalValue).toBeInTheDocument();
    expect(totalValue).toHaveAttribute("data-direction", "negative");

    const option = chartOption();
    const tplSeries = option.series.find((series: { name: string }) => series.name === "FVTPL公允价值变动");
    expect(tplSeries).toBeDefined();
    if (!tplSeries) throw new Error("missing FVTPL series");
    expect(tplSeries.data).toEqual([1.004]);
  });

  it("uses exact raw_text in tooltip text while keeping series coordinate on raw", () => {
    const data = {
      start_period: "2026-03",
      end_period: "2026-03",
      num_periods: 1,
      correlation_coefficient: num(-0.62, "ratio"),
      correlation_interpretation: "test",
      total_tpl_fv_change: num(42_000_000, "yuan", "+42,000,000.00", {
        raw_text: "-100500000",
        sign_aware: true,
      }),
      avg_treasury_10y_change: num(-7.5, "bp"),
      treasury_10y_total_change_bp: num(-7.5, "bp"),
      analysis_summary: "summary",
      data_points: [
        {
          period: "2026-03",
          period_label: "2026年03月",
          tpl_fair_value_change: num(100_400_000, "yuan", "+100,400,000.00", {
            raw_text: "100500000",
            sign_aware: true,
          }),
          tpl_total_pnl: num(100_400_000),
          tpl_scale: num(1_100_000_000),
          treasury_10y: num(0.022, "pct", "+2.20%"),
          treasury_10y_change: num(-7.5, "bp"),
          dr007: num(0.017, "pct", "+1.70%"),
        },
      ],
    } as unknown as TPLMarketCorrelationPayload;

    render(<TPLMarketChart data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    const option = chartOption();
    expect(option.tooltip?.formatter).toBeDefined();
    expect(option.series[0].data).toEqual([1.004]);
    expect(
      option.tooltip!.formatter!([
        { dataIndex: 0, seriesName: "FVTPL公允价值变动" },
        { dataIndex: 0, seriesName: "国债收益率变动" },
      ]),
    ).toContain("FVTPL公允价值变动: +1.01 亿");
    expect(
      option.tooltip!.formatter!([
        { dataIndex: 0, seriesName: "FVTPL公允价值变动" },
        { dataIndex: 0, seriesName: "国债收益率变动" },
      ]),
    ).toContain("国债收益率变动: -7.5 BP");
  });

  it("falls back to legacy raw tooltip text when raw_text is absent", () => {
    const data = {
      start_period: "2026-03",
      end_period: "2026-03",
      num_periods: 1,
      correlation_coefficient: num(-0.62, "ratio"),
      correlation_interpretation: "test",
      total_tpl_fv_change: num(42_000_000, "yuan", "", { sign_aware: true }),
      avg_treasury_10y_change: num(-7.5, "bp"),
      treasury_10y_total_change_bp: num(-7.5, "bp"),
      analysis_summary: "summary",
      data_points: [
        {
          period: "2026-03",
          period_label: "2026年03月",
          tpl_fair_value_change: num(42_000_000, "yuan", "", { sign_aware: true }),
          tpl_total_pnl: num(42_000_000),
          tpl_scale: num(1_100_000_000),
          treasury_10y: num(0.022, "pct", "+2.20%"),
          treasury_10y_change: num(-7.5, "bp"),
          dr007: num(0.017, "pct", "+1.70%"),
        },
      ],
    } as unknown as TPLMarketCorrelationPayload;

    render(<TPLMarketChart data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    const option = chartOption();
    expect(option.tooltip?.formatter).toBeDefined();
    expect(
      option.tooltip!.formatter!([{ dataIndex: 0, seriesName: "FVTPL公允价值变动" }]),
    ).toContain("FVTPL公允价值变动: +0.42 亿");
  });

  it("falls back to legacy raw-only cumulative tpl display when raw_text is absent", () => {
    const data = {
      start_period: "2026-03",
      end_period: "2026-03",
      num_periods: 1,
      correlation_coefficient: num(-0.62, "ratio"),
      correlation_interpretation: "test",
      total_tpl_fv_change: num(42_000_000, "yuan", "", { sign_aware: true }),
      avg_treasury_10y_change: num(-7.5, "bp"),
      treasury_10y_total_change_bp: num(-7.5, "bp"),
      analysis_summary: "summary",
      data_points: [
        {
          period: "2026-03",
          period_label: "2026年03月",
          tpl_fair_value_change: num(42_000_000),
          tpl_total_pnl: num(42_000_000),
          tpl_scale: num(1_100_000_000),
          treasury_10y: num(0.022, "pct", "+2.20%"),
          treasury_10y_change: num(-7.5, "bp"),
          dr007: num(0.017, "pct", "+1.70%"),
        },
      ],
    } as unknown as TPLMarketCorrelationPayload;

    render(<TPLMarketChart data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    expect(screen.getByText("+0.42 亿")).toBeInTheDocument();
  });

  it("keeps missing cumulative tpl totals blank instead of backfilling zero", () => {
    const data = {
      start_period: "2026-03",
      end_period: "2026-03",
      num_periods: 1,
      correlation_coefficient: num(-0.62, "ratio"),
      correlation_interpretation: "test",
      total_tpl_fv_change: num(null, "yuan", "", { sign_aware: true }),
      avg_treasury_10y_change: num(-7.5, "bp"),
      treasury_10y_total_change_bp: num(-7.5, "bp"),
      analysis_summary: "summary",
      data_points: [],
    } as unknown as TPLMarketCorrelationPayload;

    render(<TPLMarketChart data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    expect(screen.queryByText("+0.00 亿")).not.toBeInTheDocument();
  });

  it("does not draw missing market changes as zero", () => {
    const data = {
      start_period: "2026-02",
      end_period: "2026-03",
      num_periods: 2,
      correlation_coefficient: num(-0.62, "ratio"),
      correlation_interpretation: "test",
      total_tpl_fv_change: num(42_000_000),
      avg_treasury_10y_change: num(-15.0, "bp"),
      treasury_10y_total_change_bp: num(-15.0, "bp"),
      analysis_summary: "summary",
      data_points: [
        {
          period: "2026-02",
          period_label: "2026年2月",
          tpl_fair_value_change: num(10_000_000),
          tpl_total_pnl: num(10_000_000),
          tpl_scale: num(1_000_000_000),
          treasury_10y: num(0.0235, "pct", "+2.35%"),
          treasury_10y_change: null,
          dr007: num(0.018, "pct", "+1.80%"),
        },
        {
          period: "2026-03",
          period_label: "2026年3月",
          tpl_fair_value_change: num(32_000_000),
          tpl_total_pnl: num(32_000_000),
          tpl_scale: num(1_100_000_000),
          treasury_10y: num(0.022, "pct", "+2.20%"),
          treasury_10y_change: num(-15.0, "bp"),
          dr007: num(0.017, "pct", "+1.70%"),
        },
      ],
    } as unknown as TPLMarketCorrelationPayload;

    render(<TPLMarketChart data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    const option = chartOption();
    const rateSeries = option.series.find((series: { name: string }) => series.name === "国债收益率变动");
    expect(rateSeries).toBeDefined();
    if (!rateSeries) throw new Error("missing treasury series");
    expect(rateSeries.data).toEqual([null, -15]);
    expect(rateSeries.smooth).toBe(false);
    expect(screen.getByTestId("tpl-market-data-missing")).toHaveTextContent("不补 0");
  });

  it("treats NaN Numeric raw as a null chart gap (mixed numericRaw defensive path)", () => {
    const data = {
      start_period: "2026-02",
      end_period: "2026-03",
      num_periods: 2,
      correlation_coefficient: num(null, "ratio"),
      correlation_interpretation: "test",
      total_tpl_fv_change: num(32_000_000),
      avg_treasury_10y_change: num(-15.0, "bp"),
      treasury_10y_total_change_bp: num(-15.0, "bp"),
      analysis_summary: "summary",
      data_points: [
        {
          period: "2026-02",
          period_label: "2026年2月",
          tpl_fair_value_change: num(Number.NaN),
          tpl_total_pnl: num(null),
          tpl_scale: num(null),
          treasury_10y: num(0.0235, "pct", "+2.35%"),
          treasury_10y_change: num(Number.NaN, "bp"),
          dr007: num(0.018, "pct", "+1.80%"),
        },
        {
          period: "2026-03",
          period_label: "2026年3月",
          tpl_fair_value_change: num(32_000_000),
          tpl_total_pnl: num(32_000_000),
          tpl_scale: num(1_100_000_000),
          treasury_10y: num(0.022, "pct", "+2.20%"),
          treasury_10y_change: num(-15.0, "bp"),
          dr007: num(0.017, "pct", "+1.70%"),
        },
      ],
    } as unknown as TPLMarketCorrelationPayload;

    render(<TPLMarketChart data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    const option = chartOption();
    const tplSeries = option.series.find((series: { name: string }) => series.name === "FVTPL公允价值变动");
    expect(tplSeries).toBeDefined();
    if (!tplSeries) throw new Error("missing FVTPL series");
    expect(tplSeries.data).toEqual([null, 0.32]);
  });

  it("keeps missing tpl fair value changes as null gaps instead of zero bars", () => {
    const data = {
      start_period: "2026-02",
      end_period: "2026-03",
      num_periods: 2,
      correlation_coefficient: num(null, "ratio"),
      correlation_interpretation: "test",
      total_tpl_fv_change: num(32_000_000),
      avg_treasury_10y_change: num(-15.0, "bp"),
      treasury_10y_total_change_bp: num(-15.0, "bp"),
      analysis_summary: "summary",
      data_points: [
        {
          period: "2026-02",
          period_label: "2026年2月",
          tpl_fair_value_change: num(null),
          tpl_total_pnl: num(null),
          tpl_scale: num(null),
          treasury_10y: num(0.0235, "pct", "+2.35%"),
          treasury_10y_change: num(null, "bp"),
          dr007: num(0.018, "pct", "+1.80%"),
        },
        {
          period: "2026-03",
          period_label: "2026年3月",
          tpl_fair_value_change: num(32_000_000),
          tpl_total_pnl: num(32_000_000),
          tpl_scale: num(1_100_000_000),
          treasury_10y: num(0.022, "pct", "+2.20%"),
          treasury_10y_change: num(-15.0, "bp"),
          dr007: num(0.017, "pct", "+1.70%"),
        },
      ],
    } as unknown as TPLMarketCorrelationPayload;

    render(<TPLMarketChart data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    const option = chartOption();
    const tplSeries = option.series.find((series: { name: string }) => series.name === "FVTPL公允价值变动");
    expect(tplSeries).toBeDefined();
    if (!tplSeries) throw new Error("missing FVTPL series");
    expect(tplSeries.data).toEqual([null, 0.32]);

    // 相关系数 raw 缺失显示 —，不显示 0.000。
    expect(screen.queryByText("0.000")).not.toBeInTheDocument();
    // 利率变动 raw 缺失显示 —，不显示 +0.0。
    const row = screen.getByTestId("tpl-market-monthly-row-2026-02");
    expect(row).not.toHaveTextContent("+0.0");
  });

  it("uses product-category bond_tpl cnx_scale and cnx_cash for the monthly detail", () => {
    const data = {
      start_period: "2026-03",
      end_period: "2026-03",
      num_periods: 1,
      correlation_coefficient: num(-0.62, "ratio"),
      correlation_interpretation: "test",
      total_tpl_fv_change: num(6_000_000),
      avg_treasury_10y_change: num(-7.5, "bp"),
      treasury_10y_total_change_bp: num(-7.5, "bp"),
      analysis_summary: "summary",
      data_points: [
        {
          period: "2026-03",
          period_label: "2026年3月",
          tpl_fair_value_change: num(6_000_000),
          tpl_total_pnl: num(6_000_000),
          tpl_scale: num(13_251_000_000),
          treasury_10y: num(0.022, "pct", "+2.20%"),
          treasury_10y_change: num(-7.5, "bp"),
          dr007: num(null, "pct"),
        },
      ],
    } as unknown as TPLMarketCorrelationPayload;

    render(
      <TPLMarketChart
        data={data}
        state={{ kind: "ok" }}
        onRetry={() => {}}
        productCategoryTplMonthlyPoints={[
          {
            period: "2026-03",
            reportDate: "2026-03-31",
            row: productCategoryTplRow({
              cnx_scale: "100500000",
              cnx_cash: "267500000",
              business_net_income: "100500000",
            }),
          },
        ]}
      />,
    );

    const table = screen.getByTestId("tpl-market-monthly-detail");
    expect(table).toHaveTextContent("1.01");
    expect(table).toHaveTextContent("2.68");
    expect(table).not.toHaveTextContent("132.51");
    expect(table).not.toHaveTextContent("0.06");
  });

  it("keeps DecimalLike number inputs on the legacy compatibility path for monthly detail", () => {
    const data = {
      start_period: "2026-03",
      end_period: "2026-03",
      num_periods: 1,
      correlation_coefficient: num(-0.62, "ratio"),
      correlation_interpretation: "test",
      total_tpl_fv_change: num(6_000_000),
      avg_treasury_10y_change: num(-7.5, "bp"),
      treasury_10y_total_change_bp: num(-7.5, "bp"),
      analysis_summary: "summary",
      data_points: [
        {
          period: "2026-03",
          period_label: "2026年3月",
          tpl_fair_value_change: num(6_000_000),
          tpl_total_pnl: num(6_000_000),
          tpl_scale: num(13_251_000_000),
          treasury_10y: num(0.022, "pct", "+2.20%"),
          treasury_10y_change: num(-7.5, "bp"),
          dr007: num(null, "pct"),
        },
      ],
    } as unknown as TPLMarketCorrelationPayload;

    render(
      <TPLMarketChart
        data={data}
        state={{ kind: "ok" }}
        onRetry={() => {}}
        productCategoryTplMonthlyPoints={[
          {
            period: "2026-03",
            reportDate: "2026-03-31",
            row: productCategoryTplRow({
              cnx_scale: 100_500_000,
              cnx_cash: 267_500_000,
              business_net_income: 100_500_000,
            }),
          },
        ]}
      />,
    );

    const row = screen.getByTestId("tpl-market-monthly-row-2026-03");
    expect(row).toHaveTextContent("1.00");
    expect(row).toHaveTextContent("2.67");
    expect(row).not.toHaveTextContent("1.01");
    expect(row).not.toHaveTextContent("2.68");
  });

  it("shows blanks and a visible warning when product-category bond_tpl is missing", () => {
    const data = {
      start_period: "2026-03",
      end_period: "2026-03",
      num_periods: 1,
      correlation_coefficient: num(-0.62, "ratio"),
      correlation_interpretation: "test",
      total_tpl_fv_change: num(6_000_000),
      avg_treasury_10y_change: num(-7.5, "bp"),
      treasury_10y_total_change_bp: num(-7.5, "bp"),
      analysis_summary: "summary",
      data_points: [
        {
          period: "2026-03",
          period_label: "2026年3月",
          tpl_fair_value_change: num(6_000_000),
          tpl_total_pnl: num(6_000_000),
          tpl_scale: num(13_251_000_000),
          treasury_10y: num(0.022, "pct", "+2.20%"),
          treasury_10y_change: num(-7.5, "bp"),
          dr007: num(null, "pct"),
        },
      ],
    } as unknown as TPLMarketCorrelationPayload;

    render(
      <TPLMarketChart
        data={data}
        state={{ kind: "ok" }}
        onRetry={() => {}}
        productCategoryTplMonthlyPoints={[
          {
            period: "2026-03",
            reportDate: "2026-03-31",
            row: null,
          },
        ]}
      />,
    );

    expect(screen.getByTestId("tpl-market-product-category-missing")).toHaveTextContent("未回退");
    const row = screen.getByTestId("tpl-market-monthly-row-2026-03");
    expect(within(row).getAllByText("—")).toHaveLength(3);
    expect(row).not.toHaveTextContent("132.51");
    expect(row).not.toHaveTextContent("0.06");
  });
});
