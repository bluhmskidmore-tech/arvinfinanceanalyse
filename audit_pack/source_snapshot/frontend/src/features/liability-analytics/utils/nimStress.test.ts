import { describe, expect, it } from "vitest";

import type { LiabilityYieldKpi, Numeric } from "../../../api/contracts";
import { formatRawAsNumeric } from "../../../utils/format";
import { dailyNimStressFromKpi } from "./nimStress";

function governed(raw: number | null, unit: Numeric["unit"], signAware = false): Numeric {
  return formatRawAsNumeric({ raw, unit, sign_aware: signAware });
}

describe("dailyNimStressFromKpi", () => {
  it("keeps yield metrics Numeric-native and derives projected nim in governed units", () => {
    const yieldKpi: LiabilityYieldKpi = {
      asset_yield: governed(0.031, "pct"),
      liability_cost: governed(0.018, "pct"),
      market_liability_cost: governed(0.021, "pct"),
      nim: null,
    };

    const out = dailyNimStressFromKpi(yieldKpi);

    expect(out.ay?.unit).toBe("pct");
    expect(out.ay?.raw).toBeCloseTo(0.031, 8);
    expect(out.nim?.unit).toBe("pct");
    expect(out.nim?.raw).toBeCloseTo(0.01, 8);
    expect(out.projected?.unit).toBe("pct");
    expect(out.projected?.raw).toBeCloseTo(0.005, 8);
    expect(out.deltaBp?.unit).toBe("bp");
    expect(out.deltaBp?.raw).toBeCloseTo(-50, 8);
    expect(out.isCritical).toBe(false);
  });
});
