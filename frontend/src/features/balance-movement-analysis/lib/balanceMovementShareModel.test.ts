import { describe, expect, it } from "vitest";

import { nullableNumber, resolveBucketSharePct } from "./balanceMovementShareModel";

describe("resolveBucketSharePct", () => {
  it("prefers backend current_balance_pct when present", () => {
    expect(resolveBucketSharePct("42.44")).toBe(42.44);
  });

  it("keeps missing backend share missing instead of recomputing it", () => {
    expect(resolveBucketSharePct(null)).toBeNull();
    expect(resolveBucketSharePct(undefined)).toBeNull();
    expect(resolveBucketSharePct("")).toBeNull();
    expect(resolveBucketSharePct("   ")).toBeNull();
  });

  it("returns null for an invalid backend share", () => {
    expect(resolveBucketSharePct("not-a-number")).toBeNull();
  });

  it("does not treat backend zero as missing", () => {
    expect(resolveBucketSharePct("0")).toBe(0);
  });
});

describe("nullableNumber", () => {
  it("returns null for empty or non-finite inputs", () => {
    expect(nullableNumber(null)).toBeNull();
    expect(nullableNumber(undefined)).toBeNull();
    expect(nullableNumber("")).toBeNull();
    expect(nullableNumber("   ")).toBeNull();
    expect(nullableNumber("NaN")).toBeNull();
  });
});
