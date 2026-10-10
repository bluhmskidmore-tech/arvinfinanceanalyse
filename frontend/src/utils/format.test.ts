import { describe, expect, it } from "vitest";

import {
  EM_DASH,
  formatBp,
  formatPercent,
  formatRawAsNumeric,
  formatWan,
  formatWanAmountAsYiPlain,
  formatYi,
  formatYuanAmountAsWanPlain,
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

  it("formatYi/formatWan/formatPercent/formatBp map +/-Infinity to EM_DASH (审计 F02 #1)", () => {
    expect(formatYi(Number.POSITIVE_INFINITY, false)).toBe(EM_DASH);
    expect(formatYi(Number.NEGATIVE_INFINITY, true)).toBe(EM_DASH);
    expect(formatWan(Number.POSITIVE_INFINITY, false)).toBe(EM_DASH);
    expect(formatPercent(Number.POSITIVE_INFINITY, false)).toBe(EM_DASH);
    expect(formatBp(Number.POSITIVE_INFINITY, false)).toBe(EM_DASH);
  });

  it("formatRawAsNumeric treats Infinity raw as missing for every unit (审计 F02 #1)", () => {
    const yuan = formatRawAsNumeric({ raw: Number.POSITIVE_INFINITY, unit: "yuan", sign_aware: false });
    expect(yuan.display).toBe(EM_DASH);
    expect(yuan.raw).toBeNull();

    const yi = formatRawAsNumeric({ raw: Number.NEGATIVE_INFINITY, unit: "yi", sign_aware: false });
    expect(yi.display).toBe(EM_DASH);
    expect(yi.raw).toBeNull();
  });

  it("*AsYiPlain/*AsWanPlain map an 'Infinity' string or fully non-numeric garbage to EM_DASH, not the literal token (审计 F02 #1)", () => {
    // 非有限值及不完整金额 token 统一走 EM_DASH，不回显或截取数字前缀。
    expect(formatYuanAmountAsYiPlain("Infinity")).toBe(EM_DASH);
    expect(formatYuanAmountAsWanPlain("Infinity")).toBe(EM_DASH);
    expect(formatWanAmountAsYiPlain("abc")).toBe(EM_DASH);
  });
});

describe("千分位统一（审计 F02 #3）：formatYi/formatWan 与 *AsYiPlain 同用 zh-CN 千分位", () => {
  it("formatYi groups thousands once |值| ≥ 1000 亿", () => {
    // 123_456_000_000_000 元 = 1,234,560.00 亿
    expect(formatYi(123_456_000_000_000, false)).toBe("1,234,560.00 亿");
    expect(formatYi(-123_456_000_000_000, true)).toBe("-1,234,560.00 亿");
  });

  it("formatWan groups thousands once |值| ≥ 1000 万", () => {
    // 12_345_600_000 元 = 1,234,560.00 万
    expect(formatWan(12_345_600_000, false)).toBe("1,234,560.00 万");
  });

  it("formatRawAsNumeric's yuan (→formatYi) and yi units agree on thousands grouping", () => {
    const viaYuan = formatRawAsNumeric({ raw: 123_456_000_000_000, unit: "yuan", sign_aware: false });
    const viaYi = formatRawAsNumeric({ raw: 1_234_560, unit: "yi", sign_aware: false });
    expect(viaYuan.display).toBe("1,234,560.00 亿");
    expect(viaYi.display).toBe("1,234,560.00 亿");
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

describe("万元系（2026-08-13 增补，与亿元系对称）", () => {
  it("formatWan maps null/undefined/NaN to EM_DASH", () => {
    expect(formatWan(null, false)).toBe(EM_DASH);
    expect(formatWan(undefined, true)).toBe(EM_DASH);
    expect(formatWan(Number.NaN, false)).toBe(EM_DASH);
  });

  it("formatWan converts yuan to 万 with sign-aware prefix", () => {
    expect(formatWan(123_400, true)).toBe("+12.34 万");
    expect(formatWan(-50_000, true)).toBe("-5.00 万");
    expect(formatWan(123_400, false)).toBe("12.34 万");
    expect(formatWan(0, false)).toBe("0.00 万");
  });

  it("formatYuanAmountAsWanPlain maps missing to EM_DASH, true zero to 0.00", () => {
    expect(formatYuanAmountAsWanPlain(null)).toBe(EM_DASH);
    expect(formatYuanAmountAsWanPlain(undefined)).toBe(EM_DASH);
    expect(formatYuanAmountAsWanPlain("")).toBe(EM_DASH);
    expect(formatYuanAmountAsWanPlain(Number.NaN)).toBe(EM_DASH);
    expect(formatYuanAmountAsWanPlain(Number.POSITIVE_INFINITY)).toBe(EM_DASH);
    expect(formatYuanAmountAsWanPlain(0)).toBe("0.00");
  });

  it("formatYuanAmountAsWanPlain keeps thousands separators and parses comma-grouped strings", () => {
    expect(formatYuanAmountAsWanPlain(-12_345_600)).toBe("-1,234.56");
    expect(formatYuanAmountAsWanPlain("12,345,600")).toBe("1,234.56");
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

describe("tie rounding is half-up on the written decimal", () => {
  // 口径固化（2026-09-28）。修复前 formatPercent / formatBp 走 Number.prototype.toFixed，
  // 它按 double 的**精确二进制值**取整：本意为 0.015% 时 double 实为 0.014999999999999999，
  // 于是渲染成 0.01%。formatYi / formatWan 一直走 toLocaleString（按最短十进制表示 + half-up），
  // 同一文件内两套口径互相矛盾。现在四条路径统一为「对调用者书写的十进制 half-up」。
  // 量化：各 20000 个 tie 取值，修复前 formatPercent 错 4823 例、formatBp 错 4000 例，修复后均 0 例。
  it("formatPercent rounds a percent tie up instead of truncating", () => {
    expect(formatPercent(0.00015, false)).toBe("0.02%");
    expect(formatPercent(0.00045, false)).toBe("0.05%");
    expect(formatPercent(0.01005, false)).toBe("1.01%");
    expect(formatPercent(0.00005, false)).toBe("0.01%");
  });

  it("formatBp rounds a basis-point tie up instead of truncating", () => {
    expect(formatBp(0.15, false)).toBe("0.2 bp");
    expect(formatBp(0.95, false)).toBe("1.0 bp");
    expect(formatBp(2.05, false)).toBe("2.1 bp");
    expect(formatBp(1.45, false)).toBe("1.5 bp");
  });

  it("negative ties round away from zero, matching ROUND_HALF_UP", () => {
    expect(formatBp(-0.95, true)).toBe("-1.0 bp");
    expect(formatPercent(-0.00015, true)).toBe("-0.02%");
  });

  it("all four formatters agree on the same 1.005 tie", () => {
    // 修复前：formatYi → "1.01 亿"，而 formatPercent → "1.00%"，同文件自相矛盾。
    expect(formatYi(100_500_000, false)).toBe("1.01 亿");
    expect(formatWan(10_050, false)).toBe("1.01 万");
    expect(formatPercent(0.01005, false)).toBe("1.01%");
  });

  it("tie rounding does not introduce thousands grouping", () => {
    // 修复只改舍入，不改分组：formatBp 仍无千分位（formatYi/formatWan 的千分位另有断言）。
    expect(formatBp(1234.55, false)).toBe("1234.6 bp");
    expect(formatPercent(1234.565, false)).toBe("123456.50%");
  });
});
