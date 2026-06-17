import { describe, expect, it } from "vitest";

import { nullableNumber, resolveBucketSharePct } from "./balanceMovementShareModel";

describe("resolveBucketSharePct", () => {
  it("prefers backend current_balance_pct when present", () => {
    expect(resolveBucketSharePct("42.44", "142000000000", "335873000000")).toBe(42.44);
  });

  it("falls back to balance over total when backend pct is missing", () => {
    expect(resolveBucketSharePct(null, "100", "400")).toBe(25);
    expect(resolveBucketSharePct(undefined, 50, 200)).toBe(25);
    expect(resolveBucketSharePct("", "75", "300")).toBe(25);
  });

  it("returns null when backend and frontend fallback both fail", () => {
    expect(resolveBucketSharePct(null, null, "400")).toBeNull();
    expect(resolveBucketSharePct(null, "100", null)).toBeNull();
    expect(resolveBucketSharePct(null, "100", "0")).toBeNull();
    expect(resolveBucketSharePct("not-a-number", null, "400")).toBeNull();
  });

  it("does not treat backend zero as missing", () => {
    expect(resolveBucketSharePct("0", "100", "400")).toBe(0);
  });
});

describe("nullableNumber", () => {
  it("returns null for empty or non-finite inputs", () => {
    expect(nullableNumber(null)).toBeNull();
    expect(nullableNumber(undefined)).toBeNull();
    expect(nullableNumber("")).toBeNull();
    expect(nullableNumber("NaN")).toBeNull();
  });
});
