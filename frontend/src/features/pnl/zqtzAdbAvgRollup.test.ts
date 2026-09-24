import { describe, expect, it } from "vitest";

import { resolveAdbAvgYuan } from "./zqtzAdbAvgRollup";

describe("resolveAdbAvgYuan", () => {
  it("uses the direct evidence map value when present", () => {
    const map = new Map<string, number>([["政策性金融债", 1e9]]);
    expect(resolveAdbAvgYuan("政策性金融债", map)).toEqual({ valueYuan: 1e9, source: "direct" });
  });

  it("prefers the direct evidence map value over the backend row field", () => {
    const map = new Map<string, number>([["政策性金融债", 1e9]]);
    expect(resolveAdbAvgYuan("政策性金融债", map, "2000000000")).toEqual({
      valueYuan: 1e9,
      source: "direct",
    });
  });

  it("keeps direct true zero instead of falling back to the backend row field", () => {
    const map = new Map<string, number>([["zero-business", 0]]);
    expect(resolveAdbAvgYuan("zero-business", map, "500")).toEqual({ valueYuan: 0, source: "direct" });
  });

  it("consumes the backend YTD parent avg_balance field when the map misses the label", () => {
    const map = new Map<string, number>([["信托计划", 100]]);
    expect(resolveAdbAvgYuan("非底层投资资产", map, "48803364755.29")).toEqual({
      valueYuan: 48_803_364_755.29,
      source: "ytd_row",
    });
  });

  it("does not sum child categories to synthesize a parent value", () => {
    const map = new Map<string, number>([
      ["信托计划", 200],
      ["证券业资管计划", 300],
    ]);
    expect(resolveAdbAvgYuan("非底层投资资产", map)).toBeUndefined();
  });

  it("keeps backend true zero as zero with ytd_row provenance", () => {
    const map = new Map<string, number>();
    expect(resolveAdbAvgYuan("非底层投资资产", map, 0)).toEqual({ valueYuan: 0, source: "ytd_row" });
  });

  it("returns undefined when both the map and the backend field are missing or invalid", () => {
    const map = new Map<string, number>();
    expect(resolveAdbAvgYuan("非底层投资资产", map)).toBeUndefined();
    expect(resolveAdbAvgYuan("非底层投资资产", map, null)).toBeUndefined();
    expect(resolveAdbAvgYuan("非底层投资资产", map, "")).toBeUndefined();
    expect(resolveAdbAvgYuan("非底层投资资产", map, "not-a-number")).toBeUndefined();
  });
});
