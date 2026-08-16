import { describe, expect, it } from "vitest";

import { marketDrillIconLabel } from "./marketHomeDrillIcon";

describe("marketDrillIconLabel", () => {
  it("maps known drilldown keys to short labels", () => {
    expect(marketDrillIconLabel("market-overview")).toBe("HO");
    expect(marketDrillIconLabel("market-data")).toBe("MD");
  });
});
