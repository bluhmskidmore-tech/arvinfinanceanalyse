import { describe, expect, it } from "vitest";

import { resolveMarketChangeDirection } from "./marketHomeChangeTone";

describe("resolveMarketChangeDirection", () => {
  it("reads bp moves from key-rate detail text", () => {
    expect(resolveMarketChangeDirection("-1bp / 2026-05-29")).toBe("down");
    expect(resolveMarketChangeDirection("+3bp / 2026-05-29")).toBe("up");
  });

  it("reads percent daily moves from cross-asset detail text", () => {
    expect(resolveMarketChangeDirection("日变动 -0.45% / 2026-05-29")).toBe("down");
    expect(resolveMarketChangeDirection("日变动 +0.42%")).toBe("up");
  });

  it("falls back to sparkline slope when detail has no signed move", () => {
    expect(resolveMarketChangeDirection("2026-05-29", [1.7, 1.71, 1.72])).toBe("up");
    expect(resolveMarketChangeDirection(undefined, [4892.12, 4868.03])).toBe("down");
  });
});
