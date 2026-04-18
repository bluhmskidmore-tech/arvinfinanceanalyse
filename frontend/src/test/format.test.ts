import { describe, expect, it } from "vitest";

import {
  formatBp,
  formatNumeric,
  formatPercent,
  formatRawAsNumeric,
  formatYi,
} from "../utils/format";
import { isNumeric } from "../api/numeric";
import type { Numeric } from "../api/contracts";

describe("formatYi", () => {
  it("formats positive with leading + when signed", () => {
    expect(formatYi(12_345_678_900, true)).toBe("+123.46 亿");
  });

  it("formats negative with minus when signed", () => {
    expect(formatYi(-5_000_000_000, true)).toBe("-50.00 亿");
  });

  it("formats positive without sign when unsigned", () => {
    expect(formatYi(12_345_678_900, false)).toBe("123.46 亿");
  });

  it("returns dash when raw is null", () => {
    expect(formatYi(null, true)).toBe("—");
  });

  it("returns dash when raw is undefined", () => {
    expect(formatYi(undefined, true)).toBe("—");
  });
});

describe("formatPercent", () => {
  it("formats ratio-as-percent with signed prefix", () => {
    expect(formatPercent(0.0255, true)).toBe("+2.55%");
  });

  it("formats negative ratio", () => {
    expect(formatPercent(-0.02, true)).toBe("-2.00%");
  });

  it("returns dash on null", () => {
    expect(formatPercent(null, true)).toBe("—");
  });
});

describe("formatBp", () => {
  it("formats bp with signed prefix", () => {
    expect(formatBp(12.5, true)).toBe("+12.5 bp");
  });

  it("formats negative bp", () => {
    expect(formatBp(-7.0, true)).toBe("-7.0 bp");
  });

  it("returns dash on null", () => {
    expect(formatBp(null, true)).toBe("—");
  });
});

describe("formatNumeric", () => {
  it("returns the display string already baked in by adapter", () => {
    const n: Numeric = {
      raw: 1,
      unit: "yuan",
      display: "+123.45 亿",
      precision: 2,
      sign_aware: true,
    };
    expect(formatNumeric(n)).toBe("+123.45 亿");
  });

  it("handles null Numeric (raw=null) by returning its display as-is", () => {
    const n: Numeric = {
      raw: null,
      unit: "pct",
      display: "—",
      precision: 2,
      sign_aware: true,
    };
    expect(formatNumeric(n)).toBe("—");
  });
});

describe("formatRawAsNumeric", () => {
  it("builds yuan Numeric with signed display for positive", () => {
    const n = formatRawAsNumeric({
      raw: 12_345_678_900,
      unit: "yuan",
      sign_aware: true,
    });
    expect(isNumeric(n)).toBe(true);
    expect(n.raw).toBe(12_345_678_900);
    expect(n.unit).toBe("yuan");
    expect(n.display).toBe("+123.46 亿");
    expect(n.sign_aware).toBe(true);
  });

  it("builds pct Numeric", () => {
    const n = formatRawAsNumeric({
      raw: 0.0255,
      unit: "pct",
      sign_aware: true,
    });
    expect(n.display).toBe("+2.55%");
    expect(n.unit).toBe("pct");
  });

  it("builds bp Numeric", () => {
    const n = formatRawAsNumeric({
      raw: 12.5,
      unit: "bp",
      sign_aware: true,
    });
    expect(n.display).toBe("+12.5 bp");
    expect(n.precision).toBe(1);
  });

  it("builds count Numeric unsigned", () => {
    const n = formatRawAsNumeric({
      raw: 1234,
      unit: "count",
      sign_aware: false,
    });
    expect(n.display).toBe("1,234");
    expect(n.sign_aware).toBe(false);
    expect(n.precision).toBe(0);
  });

  it("returns null Numeric with display '—' for raw = null", () => {
    const n = formatRawAsNumeric({
      raw: null,
      unit: "yuan",
      sign_aware: true,
    });
    expect(n.raw).toBeNull();
    expect(n.display).toBe("—");
  });

  it("builds ratio Numeric (不强制带符号)", () => {
    const n = formatRawAsNumeric({
      raw: 0.42,
      unit: "ratio",
      sign_aware: false,
    });
    expect(n.display).toBe("0.42");
    expect(n.sign_aware).toBe(false);
  });

  it("allows precision override", () => {
    const n = formatRawAsNumeric({
      raw: 0.00123456,
      unit: "pct",
      sign_aware: false,
      precision: 4,
    });
    expect(n.display).toBe("0.1235%");
  });
});

describe("legacy fmt* helpers still exported", () => {
  it("fmtYi, fmtBp, fmtPct, fmtChange, fmtRate, fmtCount 仍然可以 import", async () => {
    const mod = await import("../utils/format");
    expect(typeof mod.fmtYi).toBe("function");
    expect(typeof mod.fmtBp).toBe("function");
    expect(typeof mod.fmtPct).toBe("function");
    expect(typeof mod.fmtChange).toBe("function");
    expect(typeof mod.fmtRate).toBe("function");
    expect(typeof mod.fmtCount).toBe("function");
  });
});
