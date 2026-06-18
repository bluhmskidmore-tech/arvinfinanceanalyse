import { describe, expect, it } from "vitest";

import { adaptRateQuoteRowsToTermStructureCurves } from "./marketDataTermStructureAdapter";
import type { MarketDataRateQuoteRow } from "../marketDataTerminalModel";

const sampleRows: MarketDataRateQuoteRow[] = [
  {
    key: "t10",
    seriesId: "EMM00166466",
    seriesName: "国债 10Y",
    variety: "国债",
    tenor: "10Y",
    rateText: "1.71%",
    deltaText: "-1bp",
    tradeDate: "2026-06-13",
    sourceVersion: "sv_test",
    vendorVersion: "vv_test",
    qualityFlag: "ok",
    sourceMode: "latest",
    sparklineValues: [1.72, 1.71],
  },
  {
    key: "c5",
    seriesId: "EMM00166498",
    seriesName: "国开 5Y",
    variety: "国开",
    tenor: "5Y",
    rateText: "1.83%",
    deltaText: "+2bp",
    tradeDate: "2026-06-13",
    sourceVersion: "sv_test",
    vendorVersion: "vv_test",
    qualityFlag: "ok",
    sourceMode: "latest",
    sparklineValues: [1.81, 1.83],
  },
];

describe("adaptRateQuoteRowsToTermStructureCurves", () => {
  it("maps treasury and cdb rows into curve payloads", () => {
    const curves = adaptRateQuoteRowsToTermStructureCurves(sampleRows, null, "both");
    expect(curves).toHaveLength(2);
    expect(curves[0]?.curve_type).toBe("treasury");
    expect(curves[0]?.points[0]?.tenor).toBe("10Y");
    expect(curves[0]?.points[0]?.yield_pct?.raw).toBe(1.71);
    expect(curves[0]?.points[0]?.delta_bp_prev?.raw).toBe(-1);
    expect(curves[1]?.curve_type).toBe("cdb");
  });

  it("returns only the active curve when requested", () => {
    const curves = adaptRateQuoteRowsToTermStructureCurves(sampleRows, null, "treasury");
    expect(curves).toHaveLength(1);
    expect(curves[0]?.curve_type).toBe("treasury");
  });
});
