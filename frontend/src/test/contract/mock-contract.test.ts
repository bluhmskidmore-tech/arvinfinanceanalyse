/**
 * Mock ↔ schema contract smoke tests.
 *
 * Wave 1 provides the skeleton. Wave 2/3 will add real mockClient method
 * assertions here (one `describe` block per upgraded mock method).
 *
 * Contract for future tests:
 *   describe("mockClient.<method>", () => {
 *     it("returns payload where every Numeric-shaped node passes isNumeric", () => {
 *       const client = createApiClient({ mode: "mock" });
 *       const result = await client.<method>(<params>);
 *       assertAllNumerics(result);
 *     });
 *   });
 */
import { describe, expect, it } from "vitest";

import { createApiClient } from "../../api/client";
import type { Numeric } from "../../api/contracts";
import { isNumeric } from "../../api/numeric";
import { assertAllNumerics } from "./assertAllNumerics";

describe("assertAllNumerics · smoke", () => {
  it("accepts a valid Numeric leaf", () => {
    const n: Numeric = {
      raw: 12.5,
      unit: "yuan",
      display: "+12.5",
      precision: 2,
      sign_aware: true,
    };
    expect(() => assertAllNumerics(n)).not.toThrow();
  });

  it("accepts a nested object containing valid Numerics", () => {
    const payload = {
      title: "overview",
      metrics: [
        {
          id: "aum",
          value: {
            raw: 1,
            unit: "yuan",
            display: "+1",
            precision: 0,
            sign_aware: true,
          },
        },
      ],
      total: {
        raw: null,
        unit: "yuan",
        display: "—",
        precision: 2,
        sign_aware: true,
      },
    };
    expect(() => assertAllNumerics(payload)).not.toThrow();
  });

  it("fails when a Numeric-shaped node has an invalid field", () => {
    const broken = {
      metrics: [
        {
          value: {
            raw: 1,
            unit: "bogus_unit",
            display: "1",
            precision: 2,
            sign_aware: true,
          },
        },
      ],
    };
    expect(() => assertAllNumerics(broken)).toThrow();
  });

  it("fails with path info when deeply nested Numeric is wrong", () => {
    const broken = {
      level1: {
        level2: {
          value: {
            raw: 1,
            unit: "yuan",
            display: "1",
            precision: -2,          // invalid
            sign_aware: true,
          },
        },
      },
    };
    let err: Error | null = null;
    try {
      assertAllNumerics(broken);
    } catch (e) {
      err = e as Error;
    }
    expect(err).toBeTruthy();
    expect(err?.message ?? "").toContain("level1.level2.value");
  });

  it("skips nodes that don't look like Numeric", () => {
    const payload = {
      title: "hello",
      count: 42,
      inner: { name: "x", nested: [1, 2, 3] },
    };
    expect(() => assertAllNumerics(payload)).not.toThrow();
  });

  it("integrates with isNumeric for consistent semantics", () => {
    const n: Numeric = {
      raw: 1,
      unit: "pct",
      display: "+1%",
      precision: 2,
      sign_aware: true,
    };
    expect(isNumeric(n)).toBe(true);
    expect(() => assertAllNumerics(n)).not.toThrow();
  });
});

// ------------------------------------------------------------------
// Wave 2.7 · mockClient.getOverview / getPnlAttribution 对拍
// ------------------------------------------------------------------

describe("mockClient.getOverview · W2.7 contract", () => {
  it("returns envelope where every Numeric-shaped node passes isNumeric", async () => {
    const client = createApiClient({ mode: "mock" });
    const envelope = await client.getOverview();
    expect(envelope.result).toBeDefined();
    assertAllNumerics(envelope.result, "getOverview.result");
  });

  it("each metric has Numeric value and delta", async () => {
    const client = createApiClient({ mode: "mock" });
    const envelope = await client.getOverview();
    for (const metric of envelope.result.metrics) {
      expect(isNumeric(metric.value)).toBe(true);
      expect(isNumeric(metric.delta)).toBe(true);
    }
  });
});

describe("mockClient.getPnlAttribution · W2.7 contract", () => {
  it("returns envelope where every Numeric-shaped node passes isNumeric", async () => {
    const client = createApiClient({ mode: "mock" });
    const envelope = await client.getPnlAttribution();
    assertAllNumerics(envelope.result, "getPnlAttribution.result");
  });

  it("total and every segment.amount are Numeric", async () => {
    const client = createApiClient({ mode: "mock" });
    const envelope = await client.getPnlAttribution();
    expect(isNumeric(envelope.result.total)).toBe(true);
    for (const segment of envelope.result.segments) {
      expect(isNumeric(segment.amount)).toBe(true);
    }
  });

  it("segments no longer have display_amount field", async () => {
    const client = createApiClient({ mode: "mock" });
    const envelope = await client.getPnlAttribution();
    for (const segment of envelope.result.segments) {
      expect((segment as Record<string, unknown>).display_amount).toBeUndefined();
    }
  });
});

// ------------------------------------------------------------------
// Wave 2 will add:  describe("mockClient.getOverview", () => { ... })
// Wave 2 will add:  describe("mockClient.getPnlAttribution", () => { ... })
// Wave 3 will add:  describe("mockClient.getVolumeRateAttribution", () => { ... })
// Wave 3 will add:  describe("mockClient.getPnlCompositionBreakdown", () => { ... })
// Wave 5 will add:  describe("mockClient.<bond-analytics methods>", ...)
// ------------------------------------------------------------------
