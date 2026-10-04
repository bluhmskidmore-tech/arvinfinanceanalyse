import { describe, expect, it } from "vitest";

import type { Numeric } from "../../api/contracts";
import { EM_DASH } from "../../utils/format";
import {
  formatConcentrationIndex,
  formatConcentrationPercent,
  formatLimitThresholdPercent,
  formatLimitUsagePercent,
  parseRatio,
} from "./concentrationFormat";

function ratioNumeric(raw: number | null, display = EM_DASH): Numeric {
  return { raw, unit: "ratio", display, precision: 2, sign_aware: false };
}

describe("formatConcentrationPercent", () => {
  it("converts contract ratio raw (decimal ratio) with a fixed x100", () => {
    // top5_concentration / credit_weight / rating_aa_and_below_weight / weight
    // 为占比；HHI 是指数，不得走本函数。
    expect(formatConcentrationPercent(ratioNumeric(0.41354965))).toBe("41.35%");
    expect(formatConcentrationPercent(ratioNumeric(0.05088252))).toBe("5.09%");
    // 100% 与 0% 边界不再被 [0,1] 区间启发式区别对待。
    expect(formatConcentrationPercent(ratioNumeric(1))).toBe("100.00%");
    expect(formatConcentrationPercent(ratioNumeric(0))).toBe("0.00%");
  });

  it("parses legacy Q8 ratio strings the same way", () => {
    expect(formatConcentrationPercent("0.29250449")).toBe("29.25%");
  });

  it("falls back to display for null raw and em-dash for undefined", () => {
    expect(formatConcentrationPercent(ratioNumeric(null, EM_DASH))).toBe(EM_DASH);
    expect(formatConcentrationPercent(undefined)).toBe(EM_DASH);
    expect(formatConcentrationPercent("")).toBe(EM_DASH);
  });
});

describe("formatConcentrationIndex", () => {
  it("formats HHI as a four-decimal index and never appends percent", () => {
    expect(formatConcentrationIndex(ratioNumeric(0.12))).toBe("0.1200");
    expect(formatConcentrationIndex(ratioNumeric(0.15))).toBe("0.1500");
    expect(formatConcentrationIndex("0.184")).toBe("0.1840");
    expect(formatConcentrationIndex(0.15)).toBe("0.1500");
    expect(formatConcentrationIndex(ratioNumeric(0.12))).not.toContain("%");
  });

  it("returns EM_DASH for missing or non-finite values", () => {
    expect(formatConcentrationIndex(ratioNumeric(null, EM_DASH))).toBe(EM_DASH);
    expect(formatConcentrationIndex(undefined)).toBe(EM_DASH);
    expect(formatConcentrationIndex("")).toBe(EM_DASH);
    expect(formatConcentrationIndex(Number.NaN)).toBe(EM_DASH);
  });
});

describe("parseRatio", () => {
  it("reads Numeric raw or parses plain strings, never re-scales", () => {
    expect(parseRatio(ratioNumeric(0.1))).toBe(0.1);
    expect(parseRatio("0.15")).toBe(0.15);
    expect(parseRatio(ratioNumeric(null))).toBeNull();
    expect(parseRatio(undefined)).toBeNull();
  });
});

describe("formatLimitThresholdPercent", () => {
  it("formats backend ratio limits with the same two-decimal percent scale as current values", () => {
    expect(formatLimitThresholdPercent(0.1)).toBe("10.00%");
    expect(formatLimitThresholdPercent(0.85)).toBe("85.00%");
    expect(formatLimitThresholdPercent(Number.NaN)).toBe(EM_DASH);
  });
});

describe("formatLimitUsagePercent", () => {
  it("computes current/limit as a one-decimal percent for scanability", () => {
    expect(formatLimitUsagePercent(0.0374, 0.1)).toBe("37.4%");
    expect(formatLimitUsagePercent(0.12, 0.1)).toBe("120.0%");
  });

  it("returns EM_DASH when current value missing or limit non-positive", () => {
    expect(formatLimitUsagePercent(null, 0.1)).toBe(EM_DASH);
    expect(formatLimitUsagePercent(0.1, 0)).toBe(EM_DASH);
  });
});
