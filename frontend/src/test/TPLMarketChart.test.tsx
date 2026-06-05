import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: ({ option }: { option: unknown }) => (
    <pre data-testid="tpl-market-echarts-stub">{JSON.stringify(option)}</pre>
  ),
}));

import type { Numeric, ProductCategoryPnlRow, TPLMarketCorrelationPayload } from "../api/contracts";
import type { DataSectionState } from "../components/DataSection.types";
import { TPLMarketChart } from "../features/pnl-attribution/components/TPLMarketChart";

function num(raw: number | null, unit: Numeric["unit"] = "yuan", display = ""): Numeric {
  return {
    raw,
    unit,
    display,
    precision: 2,
    sign_aware: false,
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

    const option = JSON.parse(screen.getByTestId("tpl-market-echarts-stub").textContent ?? "{}");
    const rateSeries = option.series.find((series: { name: string }) => series.name === "国债收益率变动");
    expect(rateSeries.data).toEqual([null, -15]);
    expect(rateSeries.smooth).toBe(false);
    expect(screen.getByTestId("tpl-market-data-missing")).toHaveTextContent("不补 0");
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
            row: productCategoryTplRow(),
          },
        ]}
      />,
    );

    const table = screen.getByTestId("tpl-market-monthly-detail");
    expect(table).toHaveTextContent("865.07");
    expect(table).toHaveTextContent("2.11");
    expect(table).toHaveTextContent("0.98");
    expect(table).not.toHaveTextContent("132.51");
    expect(table).not.toHaveTextContent("0.06");
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
