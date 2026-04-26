import { describe, expect, it } from "vitest";

import type { ChoiceMacroLatestPoint } from "../../../api/contracts";

import {
  CROSS_ASSET_TREND_WINDOW_DAYS,
  buildCrossAssetTrendOption,
  locfForward,
} from "./crossAssetTrendChart";

function point(
  seriesId: string,
  recent: [string, number][],
): ChoiceMacroLatestPoint {
  return {
    series_id: seriesId,
    series_name: seriesId,
    trade_date: recent[recent.length - 1][0],
    value_numeric: recent[recent.length - 1][1],
    unit: "%",
    source_version: "sv",
    vendor_version: "vv",
    latest_change: 0,
    recent_points: recent.map(([trade_date, value_numeric]) => ({
      trade_date,
      value_numeric,
      source_version: "sv",
      vendor_version: "vv",
      quality_flag: "ok" as const,
    })),
  };
}

describe("buildCrossAssetTrendOption", () => {
  it("keeps the x axis to the last N trading days (matches 近 20 日 copy)", () => {
    const days: [string, number][] = [];
    for (let i = 0; i < 35; i += 1) {
      const d = new Date(Date.UTC(2025, 9, 1 + i));
      const s = d.toISOString().slice(0, 10);
      days.push([s, 1.5 + i * 0.001]);
    }
    const opt = buildCrossAssetTrendOption([point("E1000180", days)]);
    expect(opt).not.toBeNull();
    const xs = (opt!.xAxis as { data: string[] }).data;
    expect(xs.length).toBe(CROSS_ASSET_TREND_WINDOW_DAYS);
    expect(xs[0]!.localeCompare(xs[1]!)).toBeLessThan(0);
  });

  it("uses connectNulls after LOCF so lines are drawable (only leading nulls before first print)", () => {
    const opt = buildCrossAssetTrendOption([point("E1000180", [
      ["2026-01-01", 1.9],
      ["2026-01-02", 1.88],
    ])]);
    const s = (opt!.series as { connectNulls: boolean }[])[0]!;
    expect(s.connectNulls).toBe(true);
  });

  it("locfForward carries the last level across missing calendar slots", () => {
    expect(locfForward([null, null, 2, null, 3, null])).toEqual([null, null, 2, 2, 3, 3]);
  });

  it("deduplicates same-date upstream points and keeps the last value", () => {
    const opt = buildCrossAssetTrendOption([
      point("E1000180", [
        ["2026-01-01", 1],
        ["2026-01-01", 2],
        ["2026-01-02", 4],
      ]),
    ]);
    const xs = (opt!.xAxis as { data: string[] }).data;
    const s = (opt!.series as { data: number[] }[])[0]!;
    expect(xs).toEqual(["2026-01-01", "2026-01-02"]);
    expect(s.data).toEqual([100, 200]);
  });

  it("keeps tooltip position inside narrow chart viewports", () => {
    const opt = buildCrossAssetTrendOption([
      point("E1000180", [
        ["2026-01-01", 1],
        ["2026-01-02", 2],
      ]),
    ]);
    const position = (opt!.tooltip as {
      position: (point: [number, number], params: unknown, dom: unknown, rect: unknown, size: { viewSize: [number, number] }) => [number, number];
    }).position;
    expect(position([20, 30], null, null, null, { viewSize: [240, 180] })).toEqual([8, 8]);
  });
});
