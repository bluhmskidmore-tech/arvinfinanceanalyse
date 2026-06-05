import { describe, expect, it } from "vitest";

import { resolveAdbAvgYuan } from "./zqtzAdbAvgRollup";

describe("resolveAdbAvgYuan", () => {
  it("uses direct category when present", () => {
    const map = new Map<string, number>([["政策性金融债", 1e9]]);
    expect(resolveAdbAvgYuan("政策性金融债", map)).toBe(1e9);
  });

  it("sums known children for 非底层投资资产 when parent key missing", () => {
    const map = new Map<string, number>([
      ["信托计划", 100],
      ["其中：外币委外", 300],
    ]);
    expect(resolveAdbAvgYuan("非底层投资资产", map)).toBe(400);
  });

  it("prefers direct parent value when both parent and children could apply", () => {
    const map = new Map<string, number>([
      ["非底层投资资产", 999],
      ["信托计划", 100],
    ]);
    expect(resolveAdbAvgYuan("非底层投资资产", map)).toBe(999);
  });

  it("sums detail rows for 证券业资管计划 when parent key missing", () => {
    const map = new Map<string, number>([
      ["其中：结构化融资（券商）", 10],
      ["其中：外币委外", 20],
      ["其中：本币委外（市值法）", 30],
      ["其中：本币专户（成本法）", 40],
    ]);
    expect(resolveAdbAvgYuan("证券业资管计划", map)).toBe(100);
  });

  it("rolls 非底层投资资产 through 证券业资管计划 without double counting detail rows", () => {
    const map = new Map<string, number>([
      ["信托计划", 100],
      ["证券业资管计划", 400],
      ["其中：外币委外", 300],
    ]);
    expect(resolveAdbAvgYuan("非底层投资资产", map)).toBe(500);
  });
});
