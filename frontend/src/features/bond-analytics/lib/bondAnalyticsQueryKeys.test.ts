import { describe, expect, it } from "vitest";

import { bondAnalyticsQueryKeyRoot } from "./bondAnalyticsQueryKeys";

describe("bondAnalyticsQueryKeys", () => {
  it("uses a stable root prefix for bond analytics queries", () => {
    expect(bondAnalyticsQueryKeyRoot).toEqual(["bond-analytics"]);
    expect([...bondAnalyticsQueryKeyRoot, "overview-action-attribution"]).toEqual([
      "bond-analytics",
      "overview-action-attribution",
    ]);
  });
});
