import { describe, expect, it } from "vitest";

import {
  EM_DASH,
  formatBp,
  formatPercent,
  formatRawAsNumeric,
  formatWanAmountAsYiPlain,
  formatYi,
  formatYuanAmountAsYiPlain,
} from "./format";

// 共享格式化层语义固化（E3，2026-08-12）。口径：
// 1) 缺失（null/undefined/NaN）→ EM_DASH（"—"），缺失与真零必须不同形；
// 2) 真零 → "0.00"（按各函数追加 "亿"/"%" 等后缀）；
// 3) 负数千分位 "-1,234.56"（最终样式仍有 owner 闸门，若裁决调整允许同步调整断言）；
// 4) 空串输入不得被 Number("") 折叠成 0，必须显示 EM_DASH。

describe("EM_DASH", () => {
  it("is the canonical em dash (U+2014), not hyphen variants", () => {
    expect(EM_DASH).toBe("—");
    expect(EM_DASH).toBe("\u2014");
    expect(EM_DASH).not.toBe("-");
    expect(EM_DASH).not.toBe("--");
  });
});

describe("missing values render EM_DASH", () => {
  it("formatYi maps null/undefined/NaN to EM_DASH", () => {
    expect(formatYi(null, false)).toBe(EM_DASH);
    expect(formatYi(undefined, false)).toBe(EM_DASH);
    expect(formatYi(Number.NaN, false)).toBe(EM_DASH);
    expect(formatYi(Number.NaN, true)).toBe(EM_DASH);
  });

  it("formatPercent maps null/undefined/NaN to EM_DASH", () => {
    expect(formatPercent(null, false)).toBe(EM_DASH);
    expect(formatPercent(undefined, false)).toBe(EM_DASH);
    expect(formatPercent(Number.NaN, false)).toBe(EM_DASH);
  });

  it("formatBp maps null/undefined/NaN to EM_DASH", () => {
    expect(formatBp(null, false)).toBe(EM_DASH);
    expect(formatBp(undefined, false)).toBe(EM_DASH);
    expect(formatBp(Number.NaN, false)).toBe(EM_DASH);
  });

  it("formatRawAsNumeric treats NaN raw as missing (display EM_DASH, raw null)", () => {
    const numeric = formatRawAsNumeric({
      raw: Number.NaN,
      unit: "yuan",
      sign_aware: false,
    });
    expect(numeric.display).toBe(EM_DASH);
    expect(numeric.raw).toBeNull();
  });

  it("*AsYiPlain map null/undefined and non-finite numbers to EM_DASH", () => {
    expect(formatYuanAmountAsYiPlain(null)).toBe(EM_DASH);
    expect(formatYuanAmountAsYiPlain(undefined)).toBe(EM_DASH);
    expect(formatYuanAmountAsYiPlain(Number.NaN)).toBe(EM_DASH);
    expect(formatYuanAmountAsYiPlain(Number.POSITIVE_INFINITY)).toBe(EM_DASH);
    expect(formatWanAmountAsYiPlain(Number.NaN)).toBe(EM_DASH);
  });
});

describe("true zero is distinct from missing", () => {
  it("renders true zero as 0.00-styled labels, never EM_DASH", () => {
    expect(formatYi(0, false)).toBe("0.00 亿");
    expect(formatPercent(0, false)).toBe("0.00%");
    expect(formatYuanAmountAsYiPlain(0)).toBe("0.00");
    expect(formatWanAmountAsYiPlain(0)).toBe("0.00");
    expect(
      formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }).display,
    ).toBe("0.00 亿");
  });
});

describe("negative amounts keep thousands separators", () => {
  // 最终样式（负号形态/千分位分组）含 owner 闸门；若口径裁决调整，允许同步调整断言。
  it("formatYuanAmountAsYiPlain renders -1,234.56", () => {
    expect(formatYuanAmountAsYiPlain(-123_456_000_000)).toBe("-1,234.56");
  });

  it("formatWanAmountAsYiPlain renders -1,234.56", () => {
    expect(formatWanAmountAsYiPlain(-12_345_600)).toBe("-1,234.56");
  });
});

describe("empty-string input is missing, not zero", () => {
  it('does not let Number("") coerce empty input to 0', () => {
    // 风险来源示意：空串在 Number() 下是 0，格式化层必须在此之前拦截。
    expect(Number("")).toBe(0);
    expect(formatYuanAmountAsYiPlain("")).toBe(EM_DASH);
    expect(formatWanAmountAsYiPlain("")).toBe(EM_DASH);
    expect(formatYuanAmountAsYiPlain("")).not.toBe("0.00");
  });
});

describe("existing correct behavior stays pinned", () => {
  it("keeps comma-grouped string inputs parseable (yuan → yi)", () => {
    expect(formatYuanAmountAsYiPlain("123,456,000,000")).toBe("1,234.56");
  });

  it("keeps sign-aware positive prefix on governed helpers", () => {
    expect(formatYi(123_000_000, true)).toBe("+1.23 亿");
    expect(formatPercent(0.0255, true)).toBe("+2.55%");
  });
});
