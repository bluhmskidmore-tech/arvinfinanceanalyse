import { describe, expect, it } from "vitest";

import type {
  StockHeavyweightTrendStock,
  StockHeavyweightTrendsPayload,
} from "../../../api/contracts";
import { buildHeavyweightTrendIndex } from "./stockHeavyweightTrendView";

function stock(overrides: Partial<StockHeavyweightTrendStock>): StockHeavyweightTrendStock {
  return {
    rank: 1,
    stock_code: "000001.SZ",
    stock_name: "阿尔法",
    pctchange: 1,
    turn: 2,
    trade_dates: ["2026-07-15", "2026-08-11"],
    close_values: [10, 11],
    cum_pct_changes: [0, 10],
    point_count: 2,
    missing_point_count: 0,
    trend_state: "ok",
    trend_note: null,
    window_return_pct: 10,
    ...overrides,
  };
}

function payload(stocks: StockHeavyweightTrendStock[]): StockHeavyweightTrendsPayload {
  return {
    basis: "analytical",
    state: "ok",
    contract_status: "observational_only",
    formal_use_allowed: false,
    requested_as_of_date: null,
    as_of_date: "2026-08-11",
    window_days: 20,
    sector_limit: 8,
    stocks_per_sector: 3,
    series_basis: "cum_pct_from_first_close",
    window_trade_dates: ["2026-07-15", "2026-08-11"],
    sectors: [{ sector_code: "801001", sector_name: "电子", sector_rank: 1, stocks }],
    coverage: {
      sector_count: 1,
      stock_count: stocks.length,
      stock_with_series_count: stocks.length,
      stock_missing_series_count: 0,
      window_trade_date_count: 2,
    },
    metric_notes: [],
    warnings: [],
  };
}

describe("buildHeavyweightTrendIndex", () => {
  it("keeps the backend series untouched and exposes the window in the title", () => {
    const index = buildHeavyweightTrendIndex(payload([stock({})]));
    const row = index.byStockCode.get("000001.SZ");

    expect(index.sessionCount).toBe(2);
    expect(index.windowLabel).toBe("2026-07-15 至 2026-08-11");
    expect(row?.values).toEqual([0, 10]);
    expect(row?.plottable).toBe(true);
    expect(row?.tone).toBe("positive");
    expect(row?.returnLabel).toBe("+10.0%");
    expect(row?.title).toBe("2026-07-15 至 2026-08-11 · 2 个交易日 · 区间 +10.0%");
  });

  it("flags a suspended gap in the title without dropping the line", () => {
    const index = buildHeavyweightTrendIndex(
      payload([stock({ missing_point_count: 3, trend_state: "partial" })]),
    );

    const row = index.byStockCode.get("000001.SZ");
    expect(row?.plottable).toBe(true);
    expect(row?.title).toContain("停牌缺 3 日");
  });

  it("marks a single-session stock as not plottable and explains why", () => {
    const index = buildHeavyweightTrendIndex(
      payload([
        stock({
          trade_dates: ["2026-08-11"],
          close_values: [10],
          cum_pct_changes: [0],
          point_count: 1,
          missing_point_count: 1,
          trend_state: "insufficient",
          trend_note: "single_session_only",
          window_return_pct: 0,
        }),
      ]),
    );

    const row = index.byStockCode.get("000001.SZ");
    expect(row?.plottable).toBe(false);
    expect(row?.returnLabel).toBe("—");
    expect(row?.title).toContain("仅 1 个交易日");
  });

  it("uses a neutral tone for a flat window and negative for a drawdown", () => {
    const flat = buildHeavyweightTrendIndex(
      payload([stock({ cum_pct_changes: [0, 0], window_return_pct: 0 })]),
    );
    expect(flat.byStockCode.get("000001.SZ")?.tone).toBe("neutral");

    const down = buildHeavyweightTrendIndex(
      payload([stock({ cum_pct_changes: [0, -4.25], window_return_pct: -4.25 })]),
    );
    expect(down.byStockCode.get("000001.SZ")?.tone).toBe("negative");
    expect(down.byStockCode.get("000001.SZ")?.returnLabel).toBe("-4.3%");
  });

  it("returns an empty index for a missing-state or absent payload", () => {
    expect(buildHeavyweightTrendIndex(null).byStockCode.size).toBe(0);
    expect(buildHeavyweightTrendIndex(undefined).windowLabel).toBeNull();

    const missing = { ...payload([stock({})]), state: "missing" as const };
    expect(buildHeavyweightTrendIndex(missing).byStockCode.size).toBe(0);
  });
});
