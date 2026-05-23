import { describe, expect, it } from "vitest";

import type { PnlByBusinessAnalysisRow } from "../../../api/contracts";

import { buildDashboardProductPnlTrendFromBondBucketMonthly } from "./dashboardProductPnlTrendModel";

function analysisRow(partial: Partial<PnlByBusinessAnalysisRow> & Pick<PnlByBusinessAnalysisRow, "dimension_key">): PnlByBusinessAnalysisRow {
  return {
    dimension_label: partial.dimension_label ?? partial.dimension_key,
    interest_income: "0",
    fair_value_change: "0",
    capital_gain: "0",
    manual_adjustment: "0",
    total_pnl: partial.total_pnl ?? "0",
    avg_balance: "0",
    current_balance: "0",
    annualized_yield_pct: null,
    ftp_rate_pct: "1.6",
    ftp_cost: "0",
    ftp_net_pnl: "0",
    ftp_net_annualized_yield_pct: null,
    asset_count: 1,
    ...partial,
  };
}

describe("buildDashboardProductPnlTrendFromBondBucketMonthly", () => {
  it("builds month labels and bond-bucket series in 亿 from bond_bucket_monthly rows", () => {
    const trend = buildDashboardProductPnlTrendFromBondBucketMonthly(
      {
        year: 2026,
        as_of_date: "2026-04-30",
        business_key: null,
        dimension: "bond_bucket_monthly",
        period_start_date: "2026-01-01",
        period_end_date: "2026-04-30",
        source_tables: [],
        rows: [
          analysisRow({
            dimension_key: "2026-03-31::rate_bond",
            dimension_label: "2026-03-31 利率债",
            total_pnl: "50000000",
          }),
          analysisRow({
            dimension_key: "2026-03-31::credit_bond",
            dimension_label: "2026-03-31 信用债",
            total_pnl: "20000000",
          }),
          analysisRow({
            dimension_key: "2026-04-30::rate_bond",
            dimension_label: "2026-04-30 利率债",
            total_pnl: "80000000",
          }),
          analysisRow({
            dimension_key: "2026-04-30::credit_bond",
            dimension_label: "2026-04-30 信用债",
            total_pnl: "-10000000",
          }),
        ],
      },
      "2026-04-30",
    );

    expect(trend.pending).toBe(false);
    expect(trend.months).toEqual(["3月", "4月"]);
    expect(trend.series.find((item) => item.id === "rate")?.values).toEqual([0.5, 0.8]);
    expect(trend.series.find((item) => item.id === "credit")?.values).toEqual([0.2, -0.1]);
    expect(trend.series.find((item) => item.id === "total")?.values).toEqual([0.7, 0.7]);
  });

  it("returns pending when as_of_date does not match home report date", () => {
    const trend = buildDashboardProductPnlTrendFromBondBucketMonthly(
      {
        year: 2026,
        as_of_date: "2026-03-31",
        business_key: null,
        dimension: "bond_bucket_monthly",
        period_start_date: "2026-01-01",
        period_end_date: "2026-03-31",
        source_tables: [],
        rows: [
          analysisRow({
            dimension_key: "2026-03-31::rate_bond",
            total_pnl: "50000000",
          }),
        ],
      },
      "2026-04-30",
    );

    expect(trend.pending).toBe(true);
    expect(trend.series).toEqual([]);
  });

  it("returns pending when bond_bucket_monthly rows are empty", () => {
    const trend = buildDashboardProductPnlTrendFromBondBucketMonthly(
      {
        year: 2026,
        as_of_date: "2026-04-30",
        business_key: null,
        dimension: "bond_bucket_monthly",
        period_start_date: "2026-01-01",
        period_end_date: "2026-04-30",
        source_tables: [],
        rows: [],
      },
      "2026-04-30",
    );

    expect(trend.pending).toBe(true);
    expect(trend.months).toEqual([]);
    expect(trend.series).toEqual([]);
  });
});
