import { describe, expect, it } from "vitest";

import type { ChoiceMacroLatestPoint, ResultMeta } from "../../../api/contracts";
import { buildMarketDataTerminalModel } from "./marketDataTerminalModel";

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
});
