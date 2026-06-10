import { describe, expect, it } from "vitest";

import type { ChoiceMacroLatestPoint, ChoiceMacroRecentPoint, ResultMeta } from "../../../api/contracts";
import {
  buildCatalogVendorNameMap,
  buildMarketDataActiveFilterSummary,
  buildMarketDataTerminalModel,
  buildTerminalSparklineValues,
  buildTerminalTickerItems,
  classifyTerminalSource,
  filterMoneyMarketRows,
  filterRateQuoteRows,
  filterTerminalTickerItems,
  matchesSourceFilter,
} from "./marketDataTerminalModel";

function meta(partial: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_terminal_model",
    basis: "formal",
    result_kind: "market_data.rates",
    formal_use_allowed: true,
    source_version: "sv_market_rates",
    vendor_version: "vv_market_rates",
    rule_version: "rv_market_rates",
    cache_version: "cv_market_rates",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-30T09:00:00Z",
    ...partial,
  };
}

function point(partial: Partial<ChoiceMacroLatestPoint> & Pick<ChoiceMacroLatestPoint, "series_id">): ChoiceMacroLatestPoint {
  return {
    series_name: partial.series_id,
    trade_date: "2026-04-30",
    value_numeric: 1.94,
    unit: "%",
    source_version: "sv_market_rates",
    vendor_version: "vv_market_rates",
    refresh_tier: "stable",
    fetch_mode: "date_slice",
    fetch_granularity: "batch",
    quality_flag: "ok",
    latest_change: 0.012,
    recent_points: [],
    ...partial,
  };
}

function recentPoint(trade_date: string, value_numeric: number): ChoiceMacroRecentPoint {
  return {
    trade_date,
    value_numeric,
    source_version: "sv_market_rates",
    vendor_version: "vv_market_rates",
    quality_flag: "ok",
  };
}

describe("buildMarketDataTerminalModel", () => {
  it("builds rate and money rows only from explicit market-data series", () => {
    const model = buildMarketDataTerminalModel({
      ratesEnvelope: {
        result_meta: meta(),
        result: {
          read_target: "duckdb",
          series: [
            point({
              series_id: "EMM00166466",
              series_name: "中债国债到期收益率:10年",
              value_numeric: 1.94,
              latest_change: -0.012,
            }),
            point({
              series_id: "EMM00166502",
              series_name: "中债政策性金融债到期收益率(国开行)10年",
              value_numeric: 2.05,
              latest_change: 0.004,
            }),
            point({
              series_id: "CA.DR007",
              series_name: "存款类机构质押式回购加权利率:DR007",
              value_numeric: 1.82,
              latest_change: -0.006,
              fetch_mode: "latest",
            }),
            point({
              series_id: "M001",
              series_name: "公开市场7天逆回购利率",
              value_numeric: 1.75,
              latest_change: 0.001,
            }),
          ],
        },
      },
    });

    expect(model.rateQuotes.status).toBe("ready");
    expect(model.rateQuotes.rows.map((row) => row.seriesId)).toEqual([
      "EMM00166466",
      "EMM00166502",
    ]);
    expect(model.rateQuotes.rows[0]).toMatchObject({
      variety: "国债",
      tenor: "10Y",
      rateText: "1.94%",
      deltaText: "-1bp",
      tradeDate: "2026-04-30",
      sourceVersion: "sv_market_rates",
      qualityFlag: "ok",
    });
    expect(model.moneyMarket.status).toBe("ready");
    expect(model.moneyMarket.rows.map((row) => row.seriesId)).toEqual(["M001", "CA.DR007"]);
    expect(model.moneyMarket.rows[1]).toMatchObject({
      name: "DR007",
      rateText: "1.82%",
      deltaText: "-0.6bp",
      sourceMode: "latest",
    });
  });

  it("marks unsupported terminal panels source-pending instead of returning demo rows", () => {
    const model = buildMarketDataTerminalModel({
      ratesEnvelope: {
        result_meta: meta(),
        result: {
          read_target: "duckdb",
          series: [],
        },
      },
    });

    expect(model.bondFutures.status).toBe("source-pending");
    expect(model.bondTrades.status).toBe("source-pending");
    expect(model.creditTrades.status).toBe("source-pending");
    expect(model.bondFutures.rows).toEqual([]);
    expect(model.bondTrades.rows).toEqual([]);
    expect(model.creditTrades.rows).toEqual([]);
  });

  it("builds terminal ticker items from formal/latest rows without recomputing values", () => {
    const model = buildMarketDataTerminalModel({
      ratesEnvelope: {
        result_meta: meta(),
        result: {
          read_target: "duckdb",
          series: [
            point({
              series_id: "EMM00166466",
              series_name: "中债国债到期收益率:10年",
              value_numeric: 1.94,
              latest_change: -0.012,
              recent_points: [
                recentPoint("2026-04-28", 1.96),
                recentPoint("2026-04-29", 1.952),
              ],
            }),
            point({
              series_id: "EMM00166502",
              series_name: "中债政策性金融债到期收益率(国开行)10年",
              value_numeric: 2.05,
              latest_change: 0.004,
            }),
            point({
              series_id: "CA.DR007",
              series_name: "存款类机构质押式回购加权利率:DR007",
              value_numeric: 1.82,
              latest_change: -0.006,
              fetch_mode: "latest",
            }),
          ],
        },
      },
    });

    const items = buildTerminalTickerItems(model);
    expect(items.map((item) => item.key)).toEqual(["cgb10y", "cdb10y", "dr007"]);
    expect(items[0]).toMatchObject({
      label: "10年国债",
      value: "1.94%",
      delta: "-1bp",
      seriesId: "EMM00166466",
      tone: "down",
      sparklineValues: [1.96, 1.952, 1.94],
    });
    expect(items[1]).toMatchObject({
      label: "10年国开",
      value: "2.05%",
      delta: "+0.4bp",
      tone: "up",
    });
  });

  it("builds sparkline values from recent_points without inventing extra samples", () => {
    const values = buildTerminalSparklineValues(
      point({
        series_id: "EMM00166466",
        value_numeric: 1.94,
        recent_points: [
          recentPoint("2026-04-28", 1.96),
          recentPoint("2026-04-29", 1.952),
        ],
      }),
    );
    expect(values).toEqual([1.96, 1.952, 1.94]);
  });

  it("filters rate quote rows by hero curve selection", () => {
    const rows = buildMarketDataTerminalModel({
      ratesEnvelope: {
        result_meta: meta(),
        result: {
          read_target: "duckdb",
          series: [
            point({ series_id: "EMM00166466", series_name: "中债国债到期收益率:10年" }),
            point({ series_id: "EMM00166502", series_name: "中债政策性金融债到期收益率(国开行)10年" }),
          ],
        },
      },
    }).rateQuotes.rows;

    expect(filterRateQuoteRows(rows, "treasury").every((row) => row.variety === "国债")).toBe(true);
    expect(filterRateQuoteRows(rows, "cdb").every((row) => row.variety === "国开")).toBe(true);
    expect(filterRateQuoteRows(rows, "both")).toHaveLength(2);
  });

  it("builds active filter summary labels for hero strip", () => {
    expect(
      buildMarketDataActiveFilterSummary({
        curveFilter: "both",
        creditSegment: "both",
        sourceFilter: "all",
      }),
    ).toBe("全部");
    expect(
      buildMarketDataActiveFilterSummary({
        curveFilter: "treasury",
        creditSegment: "both",
        sourceFilter: "choice",
      }),
    ).toBe("国债 + Choice");
    expect(
      buildMarketDataActiveFilterSummary({
        curveFilter: "both",
        creditSegment: "urban",
        sourceFilter: "internal",
      }),
    ).toBe("城投 + 内部");
  });

  it("classifies choice vs internal sources from lineage tokens and catalog vendor_name", () => {
    expect(classifyTerminalSource("sv_choice_macro", "vv_public_repo")).toBe("choice");
    expect(classifyTerminalSource("sv_public_bond", "vv_public_repo")).toBe("internal");
    expect(classifyTerminalSource("sv_public_funding", "vv_public_repo", "choice")).toBe("choice");
    expect(classifyTerminalSource("sv_public_bond", "vv_public_repo", "internal")).toBe("internal");
    const catalogVendorNames = buildCatalogVendorNameMap([
      { series_id: "M002", vendor_name: "choice" },
      { series_id: "EMM00166466", vendor_name: "choice" },
    ]);
    expect(
      matchesSourceFilter(
        {
          seriesId: "M002",
          sourceVersion: "sv_public_funding",
          vendorVersion: "vv_public_repo",
        },
        "choice",
        catalogVendorNames,
      ),
    ).toBe(true);
    expect(
      matchesSourceFilter(
        {
          seriesId: "EMM00166466",
          sourceVersion: "sv_public_bond",
          vendorVersion: "vv_public_repo",
        },
        "choice",
        catalogVendorNames,
      ),
    ).toBe(true);
    expect(
      matchesSourceFilter(
        {
          seriesId: "EMM00166466",
          sourceVersion: "sv_public_bond",
          vendorVersion: "vv_public_repo",
        },
        "choice",
      ),
    ).toBe(false);
  });

  it("filters ticker items by hero curve and source without recomputing values", () => {
    const model = buildMarketDataTerminalModel({
      ratesEnvelope: {
        result_meta: meta(),
        result: {
          read_target: "duckdb",
          series: [
            point({
              series_id: "EMM00166466",
              series_name: "中债国债到期收益率:10年",
              source_version: "sv_choice_macro",
              vendor_version: "vv_choice_macro",
            }),
            point({
              series_id: "EMM00166502",
              series_name: "中债政策性金融债到期收益率(国开行)10年",
              source_version: "sv_public_bond",
              vendor_version: "vv_public_repo",
            }),
            point({
              series_id: "CA.DR007",
              series_name: "存款类机构质押式回购加权利率:DR007",
              source_version: "sv_choice_macro",
              vendor_version: "vv_choice_macro",
            }),
          ],
        },
      },
    });

    const items = buildTerminalTickerItems(model);
    expect(
      filterTerminalTickerItems(items, "treasury", "choice", model).map((item) => item.key),
    ).toEqual(["cgb10y", "dr007"]);
    expect(filterMoneyMarketRows(model.moneyMarket.rows, "internal")).toHaveLength(0);
    expect(
      filterRateQuoteRows(model.rateQuotes.rows, "cdb", "internal").map((row) => row.seriesId),
    ).toEqual(["EMM00166502"]);
  });
});
