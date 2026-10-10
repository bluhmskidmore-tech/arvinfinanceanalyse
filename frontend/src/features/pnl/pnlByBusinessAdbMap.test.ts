import { describe, expect, it } from "vitest";

import type { AdbCategoryItem } from "../../api/contracts";
import { buildAdbAvgByBusinessTypeMap, buildYtdAvgByBusinessTypeMap } from "./pnlByBusinessAdbMap";

describe("buildAdbAvgByBusinessTypeMap", () => {
  it("preserves missing comparison average balance without hiding true zero", () => {
    const items: Array<AdbCategoryItem | Omit<AdbCategoryItem, "avg_balance">> = [
      {
        category: "null-adb",
        spot_balance: 100,
        avg_balance: null,
        proportion: 10,
        weighted_rate: null,
      },
      {
        category: "missing-adb",
        spot_balance: 200,
        proportion: 20,
        weighted_rate: null,
      },
      {
        category: "true-zero-adb",
        spot_balance: 0,
        avg_balance: 0,
        proportion: 0,
        weighted_rate: null,
      },
      {
        category: "positive-adb",
        spot_balance: 300,
        avg_balance: 123,
        proportion: 30,
        weighted_rate: null,
      },
    ];

    const map = buildAdbAvgByBusinessTypeMap(items);

    expect(map.has("null-adb")).toBe(false);
    expect(map.has("missing-adb")).toBe(false);
    expect(map.get("true-zero-adb")).toBe(0);
    expect(map.get("positive-adb")).toBe(123);
  });
});

describe("buildYtdAvgByBusinessTypeMap", () => {
  it("converts YTD yuan strings while preserving true zero and rejecting missing or invalid values", () => {
    const map = buildYtdAvgByBusinessTypeMap([
      { business_type: " 同业存单 ", avg_balance: "48803364755.29" },
      { business_type: "政策性金融债", avg_balance: "0" },
      { business_type: "空值", avg_balance: "" },
      { business_type: "非法值", avg_balance: "not-a-number" },
      { business_type: " ", avg_balance: "100" },
    ]);

    expect(map.get("同业存单")).toBe(48_803_364_755.29);
    expect(map.get("政策性金融债")).toBe(0);
    expect(map.has("空值")).toBe(false);
    expect(map.has("非法值")).toBe(false);
    expect(map.size).toBe(2);
  });
});
