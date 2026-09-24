import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Numeric } from "../api/contracts";
import type { LiabilityYieldKpi } from "../api/liabilityAdbContracts";
import { LiabilityNimStressPanel } from "../features/liability-analytics/components/LiabilityNimStressPanel";
import { formatRawAsNumeric } from "../utils/format";

function governed(raw: number, unit: Numeric["unit"], signAware = false): Numeric {
  return formatRawAsNumeric({ raw, unit, sign_aware: signAware });
}

describe("LiabilityNimStressPanel", () => {
  it("labels the ungoverned stress threshold as a candidate instead of issuing a frontend warning", () => {
    const yieldKpi: LiabilityYieldKpi = {
      asset_yield: governed(0.01, "pct"),
      liability_cost: governed(0.011, "pct"),
      market_liability_cost: governed(0.012, "pct"),
      nim: governed(-0.002, "pct"),
      nim_stress: {
        nim_stressed: governed(-0.007, "pct"),
        delta_bp: governed(-50, "bp", true),
      },
    };

    render(<LiabilityNimStressPanel yieldKpi={yieldKpi} />);

    expect(screen.getByText("候选情景")).toBeInTheDocument();
    expect(screen.queryByText("NIM 预警")).not.toBeInTheDocument();
  });
});
