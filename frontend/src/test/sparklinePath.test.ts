import { describe, expect, it } from "vitest";

import { buildSparkPath } from "../features/workbench/dashboard/sparklinePath";

function parseFirstLastY(d: string): { firstY: number; lastY: number } {
  const nums = d.match(/-?\d+(?:\.\d+)?/g);
  expect(nums).toBeTruthy();
  const parsed = nums!.map(Number);
  // M x y ... L x y — y 坐标为偶数位索引 1,3,5...
  expect(parsed.length).toBeGreaterThanOrEqual(4);
  return { firstY: parsed[1]!, lastY: parsed[parsed.length - 1]! };
}

describe("buildSparkPath", () => {
  it("空数组 → 水平中线", () => {
    const d = buildSparkPath([], 78, 22);
    expect(d.startsWith("M ")).toBe(true);
    const { firstY, lastY } = parseFirstLastY(d);
    expect(firstY).toBe(11);
    expect(lastY).toBe(11);
  });

  it("单点 → 水平中线", () => {
    const d = buildSparkPath([42], 78, 22);
    const { firstY, lastY } = parseFirstLastY(d);
    expect(firstY).toBe(lastY);
    expect(firstY).toBe(11);
  });

  it("全相同值 → 水平中线", () => {
    const d = buildSparkPath([3, 3, 3], 78, 22);
    const { firstY, lastY } = parseFirstLastY(d);
    expect(firstY).toBe(lastY);
  });

  it("上升趋势 [1,2,3,4,5] → 末点 y 小于首点 y（SVG y 向下）", () => {
    const d = buildSparkPath([1, 2, 3, 4, 5], 78, 22);
    const { firstY, lastY } = parseFirstLastY(d);
    expect(lastY).toBeLessThan(firstY);
  });

  it("含 null/NaN → 跳过无效点不报错", () => {
    const d = buildSparkPath([1, null, NaN, undefined, 5], 78, 22);
    const { firstY, lastY } = parseFirstLastY(d);
    expect(lastY).toBeLessThan(firstY);
  });
});
