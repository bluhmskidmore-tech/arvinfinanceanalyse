import { describe, expect, it } from "vitest";

import {
  buildComparisonDisplayRows,
  computeComparisonDeviationPct,
  isComparisonDeviationAlert,
  type AdbComparisonChartRow,
} from "./adbComparisonMetrics";

describe("computeComparisonDeviationPct", () => {
  it("computes the signed deviation for a positive average denominator", () => {
    expect(computeComparisonDeviationPct(550, 500)).toBeCloseTo(10, 10);
    expect(computeComparisonDeviationPct(450, 500)).toBeCloseTo(-10, 10);
    expect(computeComparisonDeviationPct(500, 500)).toBe(0);
  });

  it("returns null instead of 0 when the average denominator is zero or negative", () => {
    // 字典未登记偏离度条目 → 按 null-vs-0 纪律：分母无效即“无法计算”，
    // 返回 null（渲染 EM_DASH），不得伪造 0% 读数、也不得触发/抑制阈值预警。
    expect(computeComparisonDeviationPct(550, 0)).toBeNull();
    expect(computeComparisonDeviationPct(550, -1)).toBeNull();
  });

  it("returns null when either side is missing or not a number", () => {
    expect(computeComparisonDeviationPct(null, 500)).toBeNull();
    expect(computeComparisonDeviationPct(550, null)).toBeNull();
    expect(computeComparisonDeviationPct(Number.NaN, 500)).toBeNull();
    expect(computeComparisonDeviationPct(550, Number.NaN)).toBeNull();
  });
});

describe("isComparisonDeviationAlert", () => {
  it("flags both positive and negative deviations beyond 5% and skips null", () => {
    expect(isComparisonDeviationAlert(5.01)).toBe(true);
    expect(isComparisonDeviationAlert(-9.45)).toBe(true);
    expect(isComparisonDeviationAlert(5)).toBe(false);
    expect(isComparisonDeviationAlert(-4.99)).toBe(false);
    expect(isComparisonDeviationAlert(null)).toBe(false);
  });
});

describe("buildComparisonDisplayRows", () => {
  const makeRow = (
    label: string,
    avg: number | null,
    spot: number | null = avg,
  ): AdbComparisonChartRow => ({
    label,
    spot,
    avg,
    deviationPct: computeComparisonDeviationPct(spot, avg),
  });

  it("returns rows unchanged at or below the display budget (no 1-member aggregation)", () => {
    const rows = Array.from({ length: 11 }, (_, index) => makeRow(`cat-${index}`, (index + 1) * 100));
    expect(buildComparisonDisplayRows(rows, 10)).toEqual(rows);
  });

  it("aggregates the tail beyond top N into an 其他 row with recomputed deviation", () => {
    const rows = Array.from({ length: 12 }, (_, index) =>
      makeRow(`cat-${index}`, (12 - index) * 100, (12 - index) * 110),
    );
    const display = buildComparisonDisplayRows(rows, 10);
    expect(display).toHaveLength(11);
    expect(display[0].label).toBe("cat-0");
    const other = display[10];
    expect(other.label).toBe("其他（2 类合计）");
    expect(other.avg).toBe(100 + 200);
    expect(other.spot).toBe(110 + 220);
    expect(other.deviationPct).toBeCloseTo(10, 6);
  });

  it("keeps aggregated fields null when any tail member is missing (no zero-filling)", () => {
    const rows = [
      ...Array.from({ length: 10 }, (_, index) => makeRow(`cat-${index}`, (20 - index) * 100)),
      makeRow("tail-a", 100),
      { label: "tail-b", spot: 50, avg: null, deviationPct: null },
    ];
    const display = buildComparisonDisplayRows(rows, 10);
    const other = display[10];
    expect(other.label).toBe("其他（2 类合计）");
    expect(other.avg).toBeNull();
    expect(other.deviationPct).toBeNull();
    expect(other.spot).toBe(100 + 50);
  });
});
