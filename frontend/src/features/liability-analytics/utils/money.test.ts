import { describe, expect, it } from "vitest";

import type { Numeric } from "../../../api/contracts";
import { formatRawAsNumeric } from "../../../utils/format";
import {
  bucketAmountToYi,
  bucketAmountToYiNumeric,
  nameAmountToYi,
  nameAmountToYiNumeric,
  numericToYi,
  numericToYiNumeric,
  numericYuanRaw,
  ratioToPercentNumeric,
  shareOfTotalNumeric,
} from "./money";

function governed(raw: number | null, unit: Numeric["unit"], signAware = false): Numeric {
  return formatRawAsNumeric({ raw, unit, sign_aware: signAware });
}

function unsupportedUnit(raw: number): Numeric {
  return { ...governed(raw, "yuan"), unit: "wan" as Numeric["unit"], display: `${raw} wan` };
}

describe("liability money helpers", () => {
  it("converts yuan numerics to yi numerics without flattening to plain numbers", () => {
    const out = numericToYiNumeric(governed(250_000_000, "yuan"));

    expect(out?.unit).toBe("yi");
    expect(out?.raw).toBe(2.5);
  });

  it("prefers amount_yi when it already exists", () => {
    const out = nameAmountToYiNumeric({
      amount: governed(250_000_000, "yuan"),
      amount_yi: governed(2.8, "yi"),
    });

    expect(out?.unit).toBe("yi");
    expect(out?.raw).toBe(2.8);
  });

  it("builds governed pct numerics from ratio calculations", () => {
    const out = ratioToPercentNumeric(0.125);

    expect(out?.unit).toBe("pct");
    expect(out?.raw).toBeCloseTo(0.125, 8);
  });

  it("maps bucket amounts through the same yi conversion path", () => {
    const out = bucketAmountToYiNumeric({
      amount: governed(300_000_000, "yuan"),
    });

    expect(out?.unit).toBe("yi");
    expect(out?.raw).toBe(3);
  });

  it("does not convert unsupported units into zero values", () => {
    const value = unsupportedUnit(12);

    expect(numericYuanRaw(value)).toBeNull();
    expect(numericToYiNumeric(value)).toBeNull();
    expect(nameAmountToYiNumeric({ amount: value })).toBeNull();
    expect(bucketAmountToYiNumeric({ amount: value })).toBeNull();
    expect(numericToYi(value)).toBeNull();
    expect(nameAmountToYi({ amount: value })).toBeNull();
    expect(bucketAmountToYi({ amount: value })).toBeNull();
  });

  it("keeps share unknown when value or total cannot be converted", () => {
    const unsupported = unsupportedUnit(12);

    expect(shareOfTotalNumeric(unsupported, governed(100, "yuan"))).toBeNull();
    expect(shareOfTotalNumeric(governed(12, "yuan"), unsupported)).toBeNull();

    const realZeroShare = shareOfTotalNumeric(governed(0, "yuan"), governed(100, "yuan"));
    expect(realZeroShare?.unit).toBe("pct");
    expect(realZeroShare?.raw).toBe(0);
  });
});
