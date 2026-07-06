import { describe, expect, it } from "vitest";

import rollupFixture from "./__fixtures__/zqtzAdbAvgRollupChildren.fixture.json";
import { ADB_AVG_ROLLUP_CHILDREN_BY_PARENT, resolveAdbAvgYuan } from "./zqtzAdbAvgRollup";

describe("resolveAdbAvgYuan", () => {
  it("keeps the frontend ADB rollup tree aligned with the backend ZQTZ category fixture", () => {
    expect(ADB_AVG_ROLLUP_CHILDREN_BY_PARENT).toEqual(rollupFixture.parents);
  });

  it("uses direct category when present", () => {
    const map = new Map<string, number>([["政策性金融债", 1e9]]);
    expect(resolveAdbAvgYuan("政策性金融债", map)).toBe(1e9);
  });

  it("returns direct zero when the category explicitly has true zero ADB", () => {
    const map = new Map<string, number>([["zero-business", 0]]);
    expect(resolveAdbAvgYuan("zero-business", map)).toBe(0);
  });

  it("keeps parent rollup undefined when any required child is missing", () => {
    const map = new Map<string, number>([
      ["信托计划", 100],
      ["其中：外币委外", 300],
    ]);
    expect(resolveAdbAvgYuan("非底层投资资产", map)).toBeUndefined();
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

  it("returns rolled-up zero when child categories explicitly resolve to zero", () => {
    const map = new Map<string, number>([
      ["信托计划", 0],
      ["证券业资管计划", 0],
    ]);
    expect(resolveAdbAvgYuan("非底层投资资产", map)).toBe(0);
  });

  it("keeps missing rollup undefined when neither parent nor children are present", () => {
    const map = new Map<string, number>();
    expect(resolveAdbAvgYuan("非底层投资资产", map)).toBeUndefined();
  });

  it("rolls 非底层投资资产 through 证券业资管计划 without double counting detail rows", () => {
    const map = new Map<string, number>([
      ["信托计划", 100],
      ["证券业资管计划", 400],
      ["其中：外币委外", 300],
    ]);
    expect(resolveAdbAvgYuan("非底层投资资产", map)).toBe(500);
  });

  it("rolls parent through a fully resolved nested child tree", () => {
    const map = new Map<string, number>([
      ["信托计划", 100],
      ["其中：结构化融资（券商）", 10],
      ["其中：外币委外", 20],
      ["其中：本币委外（市值法）", 30],
      ["其中：本币专户（成本法）", 40],
    ]);
    expect(resolveAdbAvgYuan("非底层投资资产", map)).toBe(200);
  });
});
