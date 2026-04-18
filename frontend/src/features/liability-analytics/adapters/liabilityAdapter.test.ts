import { describe, expect, it } from "vitest";

import type { LiabilityCounterpartyPayload, Numeric } from "../../../api/contracts";
import { adaptLiabilityCounterparty } from "./liabilityAdapter";

function num(partial: Partial<Numeric> = {}): Numeric {
  return {
    raw: 0,
    unit: "yuan",
    display: "0.00",
    precision: 2,
    sign_aware: false,
    ...partial,
  };
}

function payload(overrides: Partial<LiabilityCounterpartyPayload> = {}): LiabilityCounterpartyPayload {
  return {
    report_date: "2025-12-31",
    total_value: num({ raw: 200_000_000, display: "2.00 亿", unit: "yuan", sign_aware: false }),
    top_10: [],
    by_type: [],
    ...overrides,
  };
}

describe("adaptLiabilityCounterparty", () => {
  it("maps payload into vm (totalValueYuan, rows, byType)", () => {
    const out = adaptLiabilityCounterparty({
      payload: payload({
        top_10: [
          {
            name: "A",
            type: "Bank",
            value: num({ raw: 100_000_000, unit: "yuan", sign_aware: false }),
            weighted_cost: {
              raw: 0.025,
              unit: "pct",
              display: "+0.03",
              precision: 4,
              sign_aware: true,
            },
          },
        ],
        by_type: [
          { name: "Bank", value: num({ raw: 100_000_000, unit: "yuan", sign_aware: false }) },
          { name: "Other", value: num({ raw: 100_000_000, unit: "yuan", sign_aware: false }) },
        ],
      }),
      isLoading: false,
      isError: false,
    });
    expect(out.state.kind).toBe("ok");
    expect(out.vm?.totalValueYuan).toBe(200_000_000);
    expect(out.vm?.rows).toHaveLength(1);
    expect(out.vm?.rows[0]?.name).toBe("A");
    expect(out.vm?.rows[0]?.valueYuan).toBe(100_000_000);
    expect(out.vm?.rows[0]?.pct).toBeCloseTo(50, 5);
    expect(out.vm?.rows[0]?.weightedCost).toBeCloseTo(0.025, 6);
    expect(out.vm?.byType).toHaveLength(2);
  });

  it("returns loading state when isLoading", () => {
    const out = adaptLiabilityCounterparty({ payload: undefined, isLoading: true, isError: false });
    expect(out.state.kind).toBe("loading");
    expect(out.vm).toBeNull();
  });

  it("returns error state when isError", () => {
    const out = adaptLiabilityCounterparty({ payload: undefined, isLoading: false, isError: true });
    expect(out.state.kind).toBe("error");
    expect(out.vm).toBeNull();
  });

  it("treats missing payload as empty", () => {
    const out = adaptLiabilityCounterparty({ payload: undefined, isLoading: false, isError: false });
    expect(out.state.kind).toBe("empty");
    expect(out.vm).toBeNull();
  });

  it("handles null counterparty value and zero total without NaN pct", () => {
    const out = adaptLiabilityCounterparty({
      payload: payload({
        total_value: num({ raw: 0, unit: "yuan", sign_aware: false }),
        top_10: [{ name: "X", type: "", value: null, weighted_cost: null }],
      }),
      isLoading: false,
      isError: false,
    });
    expect(out.vm?.rows[0]?.pct).toBe(0);
    expect(out.vm?.rows[0]?.valueYuan).toBe(0);
    expect(out.vm?.rows[0]?.weightedCost).toBeNull();
  });
});
