import { describe, expect, it } from "vitest";

import type { PnlByBusinessMonthlyBucket, PnlByBusinessMonthlyItem } from "../../api/contracts";
import { buildSelectedBusinessMonthlyTrend } from "./pnlByBusinessMonthlyTrend";

function monthlyItem(overrides: Partial<PnlByBusinessMonthlyItem> = {}): PnlByBusinessMonthlyItem {
  return {
    row_key: "asset_zqtz_policy_financial_bond",
    sort_order: 66,
    business_type: "政策性金融债",
    interest_income: "0",
    fair_value_change: "0",
    capital_gain: "0",
    manual_adjustment: "0",
    total_pnl: "1300000",
    avg_balance: "100000000",
    current_balance: "120000000",
    annualized_yield_pct: "1.530645",
    ftp_rate_pct: "1.600000",
    ftp_cost: "135890.41",
    ftp_net_pnl: "-5890.41",
    ftp_net_annualized_yield_pct: "-0.069355",
    proportion: "1",
    asset_count: 1,
    ...overrides,
  };
}

function monthlyBucket(
  monthKey: string,
  items: PnlByBusinessMonthlyItem[],
  overrides: Partial<PnlByBusinessMonthlyBucket> = {},
): PnlByBusinessMonthlyBucket {
  const periodEndDate = `${monthKey}-28`;
  const summaryItem = items[0] ?? monthlyItem();
  return {
    month_key: monthKey,
    period_start_date: `${monthKey}-01`,
    period_end_date: periodEndDate,
    calendar_days: 28,
    coverage_days: 28,
    expected_days: 28,
    sample_filled: false,
    sample_fill_method: null,
    summary: {
      interest_income: summaryItem.interest_income,
      fair_value_change: summaryItem.fair_value_change,
      capital_gain: summaryItem.capital_gain,
      manual_adjustment: summaryItem.manual_adjustment,
      total_pnl: summaryItem.total_pnl,
      avg_balance: summaryItem.avg_balance,
      current_balance: summaryItem.current_balance,
      annualized_yield_pct: summaryItem.annualized_yield_pct,
      ftp_rate_pct: summaryItem.ftp_rate_pct,
      ftp_cost: summaryItem.ftp_cost,
      ftp_net_pnl: summaryItem.ftp_net_pnl,
      ftp_net_annualized_yield_pct: summaryItem.ftp_net_annualized_yield_pct,
      asset_count: summaryItem.asset_count,
    },
    items,
    ...overrides,
  };
}

describe("buildSelectedBusinessMonthlyTrend", () => {
  it("sorts by actual period end, converts display units, and preserves percentage-point values", () => {
    const target = monthlyItem();
    const result = buildSelectedBusinessMonthlyTrend(
      [
        monthlyBucket("2026-03", [target]),
        monthlyBucket("2026-01", [
          monthlyItem({
            total_pnl: "0",
            avg_balance: "0",
            current_balance: "bad-value",
            ftp_net_pnl: null,
            annualized_yield_pct: "0",
            ftp_net_annualized_yield_pct: null,
          }),
        ]),
        monthlyBucket("2026-02", []),
        monthlyBucket("2026-04", [target], {
          calendar_days: 30,
          coverage_days: 5,
          expected_days: 30,
          sample_filled: true,
        }),
      ],
      { row_key: target.row_key, business_type: target.business_type },
    );

    expect(result.points.map((point) => point.monthKey)).toEqual([
      "2026-01",
      "2026-02",
      "2026-03",
      "2026-04",
    ]);
    expect(result.points[0]).toMatchObject({
      totalPnlWan: 0,
      avgBalanceYi: 0,
      currentBalanceYi: null,
      ftpNetPnlWan: null,
      annualizedYieldPct: 0,
      ftpRatePct: 1.6,
      ftpNetAnnualizedYieldPct: null,
    });
    expect(result.points[1]).toMatchObject({ rowAvailable: false, totalPnlWan: null, avgBalanceYi: null });
    expect(result.points[2]).toMatchObject({
      totalPnlWan: 130,
      avgBalanceYi: 1,
      currentBalanceYi: 1.2,
      ftpNetPnlWan: -0.589041,
      annualizedYieldPct: 1.530645,
      ftpRatePct: 1.6,
      ftpNetAnnualizedYieldPct: -0.069355,
    });
    expect(result.missingRowMonths).toEqual(["2026-02"]);
    expect(result.missingBucketMonths).toEqual([]);
    expect(result.coverageWarningMonths).toEqual(["2026-04"]);
    expect(result.availablePointCount).toBe(3);
  });

  it("returns an explicit empty model when no business is selected", () => {
    expect(buildSelectedBusinessMonthlyTrend([monthlyBucket("2026-01", [monthlyItem()])], undefined)).toEqual({
      businessKey: null,
      businessLabel: "未选择业务",
      points: [],
      availablePointCount: 0,
      missingBucketMonths: [],
      missingRowMonths: [],
      coverageWarningMonths: [],
    });
  });

  it("inserts a null breakpoint when an entire interior month bucket is missing", () => {
    const target = monthlyItem();
    const result = buildSelectedBusinessMonthlyTrend(
      [monthlyBucket("2026-01", [target]), monthlyBucket("2026-03", [target])],
      { row_key: target.row_key, business_type: target.business_type },
    );

    expect(result.points.map((point) => point.monthKey)).toEqual(["2026-01", "2026-02", "2026-03"]);
    expect(result.points[1]).toMatchObject({
      bucketAvailable: false,
      rowAvailable: false,
      avgBalanceYi: null,
      totalPnlWan: null,
      annualizedYieldPct: null,
    });
    expect(result.missingBucketMonths).toEqual(["2026-02"]);
    expect(result.missingRowMonths).toEqual([]);
  });

  it("uses the YTD period boundaries to preserve missing leading and trailing month buckets", () => {
    const target = monthlyItem();
    const result = buildSelectedBusinessMonthlyTrend(
      [monthlyBucket("2026-02", [target])],
      { row_key: target.row_key, business_type: target.business_type },
      { periodStartDate: "2026-01-01", periodEndDate: "2026-03-31" },
    );

    expect(result.points.map((point) => point.monthKey)).toEqual(["2026-01", "2026-02", "2026-03"]);
    expect(result.points[0]).toMatchObject({ bucketAvailable: false, totalPnlWan: null });
    expect(result.points[2]).toMatchObject({ bucketAvailable: false, totalPnlWan: null });
    expect(result.missingBucketMonths).toEqual(["2026-01", "2026-03"]);
  });
});
