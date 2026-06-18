import { describe, expect, it } from "vitest";

import { marketDataPageHref } from "./marketDataDeskBridgeLinks";

describe("marketDataPageHref", () => {
  it("appends date query when watch date is provided", () => {
    expect(marketDataPageHref("/market-data", "2026-06-11")).toBe("/market-data?date=2026-06-11");
  });

  it("returns plain path when watch date is missing", () => {
    expect(marketDataPageHref("/market-data")).toBe("/market-data");
    expect(marketDataPageHref("/market-data", "—")).toBe("/market-data");
  });
});
