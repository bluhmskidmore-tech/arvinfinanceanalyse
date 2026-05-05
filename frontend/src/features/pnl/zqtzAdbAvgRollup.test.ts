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
});
