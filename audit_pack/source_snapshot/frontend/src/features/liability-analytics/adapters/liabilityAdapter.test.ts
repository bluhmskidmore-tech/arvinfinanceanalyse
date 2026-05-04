import { describe, expect, it } from "vitest";

import type { LiabilityCounterpartyPayload, Numeric } from "../../../api/contracts";
import { formatRawAsNumeric } from "../../../utils/format";
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

function governedNumeric(raw: number | null, unit: Numeric["unit"], signAware = false): Numeric {
  return formatRawAsNumeric({ raw, unit, sign_aware: signAware });
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
  it("maps payload into a Numeric-native vm", () => {
    const out = adaptLiabilityCounterparty({
      payload: payload({
        top_10: [
          {
            name: "A",
            type: "Bank",
            value: governedNumeric(100_000_000, "yuan"),
            weighted_cost: governedNumeric(0.025, "pct"),
          },
        ],
        by_type: [
          { name: "Bank", value: governedNumeric(100_000_000, "yuan") },
          { name: "Other", value: governedNumeric(100_000_000, "yuan") },
        ],
      }),
      isLoading: false,
      isError: false,
    });
    expect(out.state.kind).toBe("ok");
    expect(out.vm?.totalValue.raw).toBe(200_000_000);
    expect(out.vm?.totalValue.unit).toBe("yuan");
    expect(out.vm?.rows).toHaveLength(1);
    expect(out.vm?.rows[0]?.name).toBe("A");
    expect(out.vm?.rows[0]?.value?.raw).toBe(100_000_000);
    expect(out.vm?.rows[0]?.value?.unit).toBe("yuan");
    expect(out.vm?.rows[0]?.share?.raw).toBeCloseTo(0.5, 8);
    expect(out.vm?.rows[0]?.share?.unit).toBe("pct");
    expect(out.vm?.rows[0]?.weightedCost?.raw).toBeCloseTo(0.025, 6);
    expect(out.vm?.rows[0]?.weightedCost?.unit).toBe("pct");
    expect(out.vm?.byType).toHaveLength(2);
    expect(out.vm?.byType[0]?.value?.raw).toBe(100_000_000);
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
    expect(out.vm?.rows[0]?.share?.raw).toBe(0);
    expect(out.vm?.rows[0]?.share?.unit).toBe("pct");
    expect(out.vm?.rows[0]?.value).toBeNull();
    expect(out.vm?.rows[0]?.weightedCost).toBeNull();
  });
});
