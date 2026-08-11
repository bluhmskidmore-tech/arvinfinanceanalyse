import { describe, expect, it } from "vitest";

import type { Numeric } from "../api/contracts";
import type { PageStateSurfaceVariant } from "../components/page/PagePrimitives";
import { EM_DASH as FORMAT_EM_DASH } from "../utils/format";
import type { Tone } from "../utils/tone";
import {
  EM_DASH,
  buildStateSurfaces,
  fixedOrDash,
  numericRaw,
  numericRawOrZero,
  textOrDash,
  toneFromSignedValue,
  type MetricTone,
  type StateSurfaceItem,
  type StateSurfaceVariant,
} from "./index";

function n(partial: Partial<Numeric> = {}): Numeric {
  return {
    raw: 1,
    unit: "yuan",
    display: "1.00",
    precision: 2,
    sign_aware: false,
    ...partial,
  };
}

describe("shared vocabulary alignment", () => {
  it("re-exports the canonical EM_DASH from utils/format", () => {
    expect(EM_DASH).toBe(FORMAT_EM_DASH);
    expect(EM_DASH).toBe("—");
  });

  it("keeps MetricTone assignable to utils/tone Tone and vice versa", () => {
    const asTone: Tone = "warning" as MetricTone;
    const asMetricTone: MetricTone = "negative" as Tone;
    expect(asTone).toBe("warning");
    expect(asMetricTone).toBe("negative");
  });

  it("keeps StateSurfaceVariant aligned with the PageStateSurface component contract", () => {
    const asComponentVariant: PageStateSurfaceVariant = "fallback-date" as StateSurfaceVariant;
    const asModelVariant: StateSurfaceVariant = "definition-pending" as PageStateSurfaceVariant;
    expect(asComponentVariant).toBe("fallback-date");
    expect(asModelVariant).toBe("definition-pending");
  });
});

describe("toneFromSignedValue", () => {
  it("maps sign to tone via utils/tone", () => {
    expect(toneFromSignedValue(12.5)).toBe("positive");
    expect(toneFromSignedValue(-0.01)).toBe("negative");
  });

  it("treats zero and missing values as neutral", () => {
    expect(toneFromSignedValue(0)).toBe("neutral");
    expect(toneFromSignedValue(null)).toBe("neutral");
    expect(toneFromSignedValue(undefined)).toBe("neutral");
  });
});

describe("textOrDash", () => {
  it("renders missing or empty text as EM_DASH", () => {
    expect(textOrDash(null)).toBe(EM_DASH);
    expect(textOrDash(undefined)).toBe(EM_DASH);
    expect(textOrDash("")).toBe(EM_DASH);
  });

  it("passes real text through unchanged", () => {
    expect(textOrDash("2026-04-30")).toBe("2026-04-30");
  });
});

describe("fixedOrDash", () => {
  it("renders missing or non-finite numbers as EM_DASH", () => {
    expect(fixedOrDash(null, 2)).toBe(EM_DASH);
    expect(fixedOrDash(undefined, 2)).toBe(EM_DASH);
    expect(fixedOrDash(Number.NaN, 2)).toBe(EM_DASH);
    expect(fixedOrDash(Number.POSITIVE_INFINITY, 2)).toBe(EM_DASH);
  });

  it("formats finite numbers with the requested precision", () => {
    expect(fixedOrDash(12.345, 2)).toBe("12.35");
    expect(fixedOrDash(5.6, 0)).toBe("6");
    expect(fixedOrDash(0, 2)).toBe("0.00");
  });
});

describe("numericRaw / numericRawOrZero", () => {
  it("returns the finite raw value", () => {
    expect(numericRaw(n({ raw: 42 }))).toBe(42);
    expect(numericRawOrZero(n({ raw: -7 }))).toBe(-7);
  });

  it("normalizes missing and non-finite raws", () => {
    expect(numericRaw(undefined)).toBeNull();
    expect(numericRaw(null)).toBeNull();
    expect(numericRaw(n({ raw: null }))).toBeNull();
    expect(numericRaw(n({ raw: Number.NaN }))).toBeNull();
    expect(numericRaw(n({ raw: Number.POSITIVE_INFINITY }))).toBeNull();
    expect(numericRawOrZero(n({ raw: null }))).toBe(0);
    expect(numericRawOrZero(undefined)).toBe(0);
  });
});

describe("buildStateSurfaces", () => {
  const mockSurface: StateSurfaceItem = {
    key: "mock",
    variant: "mock",
    title: "当前为演示数据",
    description: "页面可用于交互验证。",
  };
  const staleSurface: StateSurfaceItem = {
    key: "stale",
    variant: "stale",
    title: "存在供应商状态异常",
    description: "vendor_stale",
  };
  const allClear: StateSurfaceItem = {
    key: "ok",
    variant: "neutral",
    title: "状态证据已归集",
    description: "未显示兜底、过期或质量异常。",
  };

  it("keeps only matching candidates, in declaration order, without the when flag", () => {
    const surfaces = buildStateSurfaces([
      { ...mockSurface, when: true },
      { ...staleSurface, when: false },
      { key: "fallback", variant: "fallback-date", title: "存在兜底结果", description: "d", when: true },
    ]);

    expect(surfaces).toEqual([
      mockSurface,
      { key: "fallback", variant: "fallback-date", title: "存在兜底结果", description: "d" },
    ]);
  });

  it("emits the empty fallback only when nothing matched", () => {
    expect(
      buildStateSurfaces(
        [{ ...mockSurface, when: false }],
        { emptyFallback: allClear },
      ),
    ).toEqual([allClear]);

    expect(
      buildStateSurfaces(
        [{ ...staleSurface, when: true }],
        { emptyFallback: allClear },
      ),
    ).toEqual([staleSurface]);
  });

  it("returns an empty list when nothing matched and no fallback is configured", () => {
    expect(buildStateSurfaces([{ ...mockSurface, when: false }])).toEqual([]);
  });
});
