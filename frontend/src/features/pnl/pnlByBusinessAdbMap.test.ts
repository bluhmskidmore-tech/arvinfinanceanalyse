import { describe, expect, it } from "vitest";

import type { AdbCategoryItem } from "../../api/contracts";
import { buildAdbAvgByBusinessTypeMap } from "./pnlByBusinessAdbMap";

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
