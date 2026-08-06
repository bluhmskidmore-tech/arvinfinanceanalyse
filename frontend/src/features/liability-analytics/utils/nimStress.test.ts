import { describe, expect, it } from "vitest";

import type { Numeric } from "../../../api/contracts";
import type { LiabilityYieldKpi } from "../../../api/liabilityAdbContracts";
import { formatRawAsNumeric } from "../../../utils/format";
import { dailyNimStressFromKpi } from "./nimStress";

function governed(raw: number | null, unit: Numeric["unit"], signAware = false): Numeric {
  return formatRawAsNumeric({ raw, unit, sign_aware: signAware });
}

describe("dailyNimStressFromKpi", () => {
  it("keeps yield metrics Numeric-native and displays backend projected nim in governed units", () => {
    const yieldKpi: LiabilityYieldKpi = {
      asset_yield: governed(0.031, "pct"),
      liability_cost: governed(0.018, "pct"),
      market_liability_cost: governed(0.021, "pct"),
      nim: governed(0.01, "pct"),
      nim_stress: {
        nim_stressed: governed(0.005, "pct"),
        delta_bp: governed(-50, "bp", true),
      },
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

  it("uses backend nim stress instead of re-deriving projected nim from ay minus mlc", () => {
    const yieldKpi: LiabilityYieldKpi = {
      asset_yield: governed(0.05, "pct"),
      liability_cost: governed(0.01, "pct"),
      market_liability_cost: governed(0.01, "pct"),
      nim: governed(0.02, "pct"),
      nim_stress: {
        nim_stressed: governed(0.015, "pct"),
        delta_bp: governed(-50, "bp", true),
      },
    };

    const out = dailyNimStressFromKpi(yieldKpi);

    expect(out.nim?.raw).toBeCloseTo(0.02, 8);
    expect(out.projected?.raw).toBeCloseTo(0.015, 8);
    expect(out.deltaBp?.raw).toBeCloseTo(-50, 8);
  });
});
