import { describe, expect, it } from "vitest";

import type { Numeric } from "../../../api/contracts";
import {
  formatDv01Wan,
  formatMomRatio,
  formatRatePercent,
  formatYears,
  formatYi,
  nativeToNumber,
} from "./format";

function num(raw: number | null): Numeric {
  return {
    raw,
    unit: "ratio",
    display: raw === null ? "—" : String(raw),
    precision: 2,
    sign_aware: false,
  };
}

describe("bond dashboard numeric formatters", () => {
  it("preserves missing governed numerics instead of rendering zero", () => {
    expect(nativeToNumber(num(null))).toBeNull();
    expect(nativeToNumber(undefined)).toBeNull();
    expect(formatYi(num(null))).toBe("—");
    expect(formatRatePercent(num(null))).toBe("—");
    expect(formatDv01Wan(num(null))).toBe("—");
    expect(formatYears(num(null))).toBe("—");
  });

  it("does not emit a fake -100% MoM when the current value is missing", () => {
    expect(formatMomRatio(num(null), num(100))).toBeNull();
  });
});
