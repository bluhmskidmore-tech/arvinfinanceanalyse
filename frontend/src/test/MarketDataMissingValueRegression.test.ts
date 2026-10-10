import { describe, expect, it } from "vitest";
import type { ApiEnvelope, ChoiceMacroLatestPoint, MacroBondLinkagePayload } from "../api/contracts";
import { EM_DASH } from "../utils/format";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../utils/choiceMacroFormat";
import { formatMarketSeriesDelta, formatMarketSeriesValueParts } from "../features/market-data/lib/marketDataFormat";
import { buildMarketDataSeriesTimeChartOption } from "../features/market-data/lib/charts/marketDataSeriesTimeChartOption";
import { buildTerminalSparklineValues } from "../features/market-data/lib/marketDataTerminalModel";
import { buildMarketDataPageModel } from "../features/market-data/pages/marketDataPageModel";
import { sparklineFromChoicePoint } from "../features/workbench/module-home/marketHomeRowEnrichment";

function point(value: number | null): ChoiceMacroLatestPoint {
  return {
    series_id: "SYNTHETIC_SWAP", series_name: "Synthetic swap", trade_date: "2026-10-06",
    value_numeric: value, unit: "bp", source_version: "synthetic", vendor_version: "synthetic", quality_flag: "warning",
    latest_change: Number.POSITIVE_INFINITY,
    recent_points: [0, value, -1].map((value_numeric, index) => ({
      trade_date: `2026-10-0${index + 4}`, value_numeric,
      source_version: "synthetic", vendor_version: "synthetic", quality_flag: "warning" as const,
    })),
  };
}

describe("market missing observation boundaries", () => {
  it.each([null, Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY])("keeps invalid observation %s unavailable in formats and sparklines", (value) => {
    const source = point(value);
    expect(formatChoiceMacroValue(source)).toBe(EM_DASH);
    expect(formatChoiceMacroDelta(source)).toBe(EM_DASH);
    expect(formatMarketSeriesValueParts(source).value).toBe(EM_DASH);
    expect(formatMarketSeriesDelta(source)).toBe(EM_DASH);
    expect(buildTerminalSparklineValues(source)).toEqual([]);
    expect(sparklineFromChoicePoint(source)).toBeUndefined();
    expect(buildMarketDataSeriesTimeChartOption(source)).toMatchObject({ series: [{ data: [0, null, -1], connectNulls: false }] });
  });

  it.each([Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY])("keeps an invalid delta %s unavailable beside a valid negative swap", (latest_change) => {
    const source = { ...point(-1), latest_change };
    expect(formatChoiceMacroValue(source)).toBe("-1 bp");
    expect(formatMarketSeriesValueParts(source).value).toBe("-1 bp");
    expect(formatChoiceMacroDelta(source)).toBe(EM_DASH);
    expect(formatMarketSeriesDelta(source)).toBe(EM_DASH);
  });

  it.each([null, 0, "0"])("distinguishes missing impact %s from observed zero", (value) => {
    const envelope = { result: { portfolio_impact: { total_estimated_impact: value } } } as ApiEnvelope<MacroBondLinkagePayload>;
    expect(buildMarketDataPageModel({ macroBondLinkageEnvelope: envelope }).hasPortfolioImpact).toBe(value != null);
  });
});
