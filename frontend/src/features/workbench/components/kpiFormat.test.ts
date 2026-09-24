import { describe, expect, it } from "vitest";

import { toneFromSignedNumber } from "./kpiFormat";

describe("toneFromSignedNumber", () => {
  it("maps NaN to default (defensive null/neutral path)", () => {
    expect(toneFromSignedNumber(Number.NaN)).toBe("default");
  });

  it("maps null to default", () => {
    expect(toneFromSignedNumber(null)).toBe("default");
  });

  it("keeps signed tones for finite values", () => {
    expect(toneFromSignedNumber(1.5)).toBe("positive");
    expect(toneFromSignedNumber(-0.25)).toBe("negative");
    expect(toneFromSignedNumber(0)).toBe("default");
  });
});
