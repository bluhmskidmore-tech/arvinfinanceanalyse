import { describe, expect, it } from "vitest";

import { EM_DASH } from "../../../utils/format";
import {
  formatMarketSeriesDelta,
  formatMarketSeriesValueParts,
  formatPct,
  formatSignedCompactAmount,
  formatSignedNumber,
  seriesDisplayName,
} from "./marketDataFormat";

describe("seriesDisplayName", () => {
  it("prefers the cleaned display_name and falls back to series_name", () => {
    expect(
      seriesDisplayName({ display_name: "布伦特原油现货", series_name: "Brent spot price" }),
    ).toBe("布伦特原油现货");
    expect(seriesDisplayName({ display_name: null, series_name: "DR007" })).toBe("DR007");
    expect(seriesDisplayName({ display_name: "  ", series_name: "DR007" })).toBe("DR007");
    expect(seriesDisplayName({ series_name: "DR007" })).toBe("DR007");
  });
});

describe("formatSignedNumber", () => {
  it("formats numeric values with sign and suffix", () => {
    expect(formatSignedNumber(1.2, " bp")).toBe("+1.20 bp");
    expect(formatSignedNumber(-0.5)).toBe("-0.50");
  });

  it("clamps values that round to zero to an unsigned 0.00", () => {
    expect(formatSignedNumber(-0.001)).toBe("0.00");
    expect(formatSignedNumber(-0.001, " bp")).toBe("0.00 bp");
    expect(formatSignedNumber(0.004)).toBe("0.00");
    expect(formatSignedNumber(0)).toBe("0.00");
  });

  it("returns 不可用 for nullish", () => {
    expect(formatSignedNumber(null)).toBe("不可用");
    expect(formatSignedNumber("")).toBe("不可用");
  });
});

describe("formatSignedCompactAmount", () => {
  it("abbreviates yuan amounts to 亿 / 万 tiers with sign", () => {
    expect(formatSignedCompactAmount("1082495420.80")).toBe("+10.82 亿");
    expect(formatSignedCompactAmount(-1295506312.56)).toBe("-12.96 亿");
    expect(formatSignedCompactAmount("1820000.50")).toBe("+182.00 万");
    expect(formatSignedCompactAmount(12)).toBe("+12.00");
    expect(formatSignedCompactAmount(0)).toBe("0.00");
  });

  it("keeps formatSignedNumber empty/passthrough semantics", () => {
    expect(formatSignedCompactAmount(null)).toBe("不可用");
    expect(formatSignedCompactAmount("")).toBe("不可用");
    expect(formatSignedCompactAmount("n/a")).toBe("n/a");
  });

  it("clamps sub-precision values to an unsigned 0.00", () => {
    expect(formatSignedCompactAmount(-0.004)).toBe("0.00");
    expect(formatSignedCompactAmount(0.004)).toBe("0.00");
  });
});

describe("formatMarketSeriesValueParts", () => {
  it("scales 亿元-unit values at or above 1e4 to 万亿元 with two decimals", () => {
    expect(formatMarketSeriesValueParts({ unit: "亿元", value_numeric: 3567108.43 })).toEqual({
      value: "356.71",
      unit: "万亿元",
    });
    expect(formatMarketSeriesValueParts({ unit: "亿元", value_numeric: 1401879.2 })).toEqual({
      value: "140.19",
      unit: "万亿元",
    });
    expect(formatMarketSeriesValueParts({ unit: "亿", value_numeric: 147364.79 })).toEqual({
      value: "14.74",
      unit: "万亿",
    });
  });

  it("keeps sub-万亿 amounts in the original unit with zh-CN grouping", () => {
    expect(formatMarketSeriesValueParts({ unit: "亿元", value_numeric: 3000 })).toEqual({
      value: "3,000",
      unit: "亿元",
    });
    expect(formatMarketSeriesValueParts({ unit: "CNY/t", value_numeric: 24055 })).toEqual({
      value: "24,055",
      unit: "CNY/t",
    });
  });

  it("keeps percent/bp/unitless series in the value segment", () => {
    expect(formatMarketSeriesValueParts({ unit: "%", value_numeric: 1.83 })).toEqual({
      value: "1.83%",
      unit: "",
    });
    expect(formatMarketSeriesValueParts({ unit: "bp", value_numeric: 12.4 })).toEqual({
      value: "12 bp",
      unit: "",
    });
    expect(formatMarketSeriesValueParts({ unit: "index", value_numeric: 4102.25 })).toEqual({
      value: "4,102.25",
      unit: "",
    });
  });
});

describe("formatMarketSeriesDelta", () => {
  it("renders percent-unit changes as percentage points, not bp", () => {
    expect(formatMarketSeriesDelta({ unit: "%", value_numeric: 5.3, latest_change: 0.8 })).toBe(
      "+0.8pct",
    );
    expect(formatMarketSeriesDelta({ unit: "%", value_numeric: 5.3, latest_change: -0.25 })).toBe(
      "-0.25pct",
    );
  });

  it("keeps bp only for bp-unit spread series", () => {
    expect(formatMarketSeriesDelta({ unit: "bp", value_numeric: 35, latest_change: 2 })).toBe(
      "+2 bp",
    );
    expect(formatMarketSeriesDelta({ unit: "bp", value_numeric: 35, latest_change: -0.6 })).toBe(
      "-0.6 bp",
    );
  });

  it("never signs changes that format to zero", () => {
    expect(
      formatMarketSeriesDelta({ unit: "CNY/USD", value_numeric: 7.13, latest_change: -0.0001 }),
    ).toBe("0 CNY/USD");
    expect(formatMarketSeriesDelta({ unit: "CNY", value_numeric: 7.85, latest_change: 0.0001 })).toBe(
      "0 CNY",
    );
    expect(formatMarketSeriesDelta({ unit: "%", value_numeric: 5.3, latest_change: -0.001 })).toBe(
      "0pct",
    );
  });

  it("scales huge 亿元-unit changes to 万亿元 and groups the rest", () => {
    expect(
      formatMarketSeriesDelta({ unit: "亿元", value_numeric: 3567108, latest_change: 48000 }),
    ).toBe("+4.80 万亿元");
    expect(
      formatMarketSeriesDelta({ unit: "亿元", value_numeric: 3567108, latest_change: -1500 }),
    ).toBe("-1,500 亿元");
  });

  it("falls back to EM_DASH or the caller placeholder when change is missing", () => {
    expect(formatMarketSeriesDelta({ unit: "%", value_numeric: 5.3, latest_change: null })).toBe(
      EM_DASH,
    );
    expect(
      formatMarketSeriesDelta(
        { unit: "%", value_numeric: 5.3, latest_change: undefined },
        { emptyDisplay: "无前值" },
      ),
    ).toBe("无前值");
  });
});

describe("formatPct", () => {
  it("formats to two decimals with percent suffix", () => {
    expect(formatPct(3.456)).toBe("3.46%");
    expect(formatPct(-0.5)).toBe("-0.50%");
  });

  it("returns EM_DASH for missing values", () => {
    expect(formatPct(null)).toBe(EM_DASH);
    expect(formatPct(undefined)).toBe(EM_DASH);
    expect(formatPct(Number.NaN)).toBe(EM_DASH);
    // 委托 pageModel pctOrDash 后与共享基元对齐：非有限数也回退 EM_DASH。
    expect(formatPct(Number.POSITIVE_INFINITY)).toBe(EM_DASH);
  });
});
