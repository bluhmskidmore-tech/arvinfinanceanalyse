import { describe, expect, it } from "vitest";

import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import {
  enrichMarketHomeRow,
  resolveMacroSnapshotDetail,
  sparklineFromChoicePoint,
  type MarketHomeSparklineRow,
} from "./marketHomeRowEnrichment";

function macroPoint(overrides: Partial<ChoiceMacroLatestPoint>): ChoiceMacroLatestPoint {
  return {
    series_id: "TEST",
    series_name: "测试序列",
    trade_date: "2026-05-29",
    value_numeric: 0,
    frequency: "daily",
    unit: "",
    source_version: "sv_test",
    vendor_version: "vv_test",
    ...overrides,
  };
}

describe("marketHomeRowEnrichment", () => {
  it("builds sparkline values from recent_points in trade-date order", () => {
    const point = macroPoint({
      recent_points: [
        { trade_date: "2026-05-27", value_numeric: 1.7, source_version: "sv", vendor_version: "vv", quality_flag: "ok" },
        { trade_date: "2026-05-28", value_numeric: 1.71, source_version: "sv", vendor_version: "vv", quality_flag: "ok" },
        { trade_date: "2026-05-29", value_numeric: 1.72, source_version: "sv", vendor_version: "vv", quality_flag: "ok" },
      ],
    });

    expect(sparklineFromChoicePoint(point)).toEqual([1.7, 1.71, 1.72]);
  });

  it("prefers percent change detail for CSI300 when the companion pct series exists", () => {
    const byId = new Map<string, ChoiceMacroLatestPoint>([
      [
        "CA.CSI300",
        macroPoint({
          series_id: "CA.CSI300",
          unit: "index",
          value_numeric: 4892.12,
          latest_change: -22.09,
        }),
      ],
      [
        "CA.CSI300_PCT_CHG",
        macroPoint({
          series_id: "CA.CSI300_PCT_CHG",
          unit: "%",
          value_numeric: -0.45,
        }),
      ],
    ]);

    expect(resolveMacroSnapshotDetail(byId.get("CA.CSI300")!, byId)).toBe("日变动 -0.45%");
  });

  it("enriches CSI300 rows with percent detail and sparkline history", () => {
    const byId = new Map<string, ChoiceMacroLatestPoint>([
      [
        "CA.CSI300",
        macroPoint({
          series_id: "CA.CSI300",
          unit: "index",
          value_numeric: 4892.12,
          latest_change: -22.09,
          recent_points: [
            { trade_date: "2026-05-28", value_numeric: 4914.21, source_version: "sv", vendor_version: "vv", quality_flag: "ok" },
            { trade_date: "2026-05-29", value_numeric: 4892.12, source_version: "sv", vendor_version: "vv", quality_flag: "ok" },
          ],
        }),
      ],
      [
        "CA.CSI300_PCT_CHG",
        macroPoint({
          series_id: "CA.CSI300_PCT_CHG",
          unit: "%",
          value_numeric: -0.45,
        }),
      ],
    ]);

    const row: MarketHomeSparklineRow = {
      key: "CA.CSI300",
      label: "沪深300指数收盘价",
      value: "4892.12",
      tradeDate: "2026-05-29",
      source: "CA.CSI300",
      tone: "ok",
      detail: "-22.09",
    };

    expect(enrichMarketHomeRow(row, byId)).toEqual({
      ...row,
      detail: "日变动 -0.45%",
      sparkline: [4914.21, 4892.12],
    });
  });
});
