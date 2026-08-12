import { describe, expect, it } from "vitest";

import type {
  ChoiceMacroLatestPoint,
  YieldCurveTermPointPayload,
  YieldCurveTermStructureCurvePayload,
  YieldCurveTermStructurePayload,
} from "../../../../api/contracts";
import { buildHomeMarketContextModel } from "./buildHomeMarketContextModel";

function curve(
  curveType: string,
  resolvedDate: string | null,
  points: YieldCurveTermPointPayload[] = [],
): YieldCurveTermStructureCurvePayload {
  return {
    curve_type: curveType,
    trade_date_requested: "2026-04-10",
    trade_date_resolved: resolvedDate,
    points,
    source_version: "test",
    rule_version: "test",
    vendor_name: "test",
    vendor_version: "test",
  };
}

function mixedCurvePayload(): YieldCurveTermStructurePayload {
  return {
    report_date: "2026-04-10",
    curves: [
      curve("treasury", "2026-04-10"),
      curve("cdb", "2026-04-09"),
      curve("aaa_credit", null),
    ],
    warnings: [],
    computed_at: "2026-04-10T16:00:00Z",
  };
}

describe("buildHomeMarketContextModel yield curve dates", () => {
  it("keeps mixed dates in the curve block and excludes them from the global as-of date", () => {
    const model = buildHomeMarketContextModel({
      marketTape: [],
      marketPoints: null,
      macroNewsEvents: null,
      todayIsoDate: "2026-04-10",
      campisiFourEffects: null,
      returnDecomposition: null,
      yieldCurveTermStructure: mixedCurvePayload(),
      creditSpreadMigration: null,
      attribution: {
        maxDragLabel: "",
        maxContributionLabel: "",
      },
    });

    const curveBlock = model.contextBlocks.find(
      (block) => block.id === "curve",
    );
    expect(curveBlock?.foot).toContain("2026-04-10");
    expect(curveBlock?.foot).toContain("2026-04-09");
    expect(model.curveTable.title).toBe("国债收益率");
    expect(model.asOfLabel).not.toContain("2026-04-10");
  });

  it("keeps the panel title stable when no curve is available", () => {
    const model = buildHomeMarketContextModel({
      marketTape: [],
      marketPoints: null,
      macroNewsEvents: null,
      todayIsoDate: "2026-04-10",
      campisiFourEffects: null,
      returnDecomposition: null,
      yieldCurveTermStructure: null,
      creditSpreadMigration: null,
      attribution: {
        maxDragLabel: "",
        maxContributionLabel: "",
      },
    });

    // 失败态与成功态同名，避免标题跳变；vendor 源名不进标题。
    expect(model.curveTable.title).toBe("国债收益率");
  });

  it("exposes governed key-tenor rows for the compact market table", () => {
    const payload: YieldCurveTermStructurePayload = {
      report_date: "2026-04-10",
      curves: [
        curve("cdb", "2026-04-10", [
          {
            tenor: "1Y",
            yield_pct: {
              raw: 0.016,
              unit: "pct",
              display: "1.60%",
              precision: 2,
              sign_aware: false,
            },
            delta_bp_prev: {
              raw: -1.2,
              unit: "bp",
              display: "-1.20",
              precision: 2,
              sign_aware: true,
            },
          },
          {
            tenor: "3Y",
            yield_pct: {
              raw: 0.0178,
              unit: "pct",
              display: "1.78%",
              precision: 2,
              sign_aware: false,
            },
            delta_bp_prev: {
              raw: 0,
              unit: "bp",
              display: "0.00",
              precision: 2,
              sign_aware: true,
            },
          },
          {
            tenor: "5Y",
            yield_pct: {
              raw: 0.0192,
              unit: "pct",
              display: "undefined",
              precision: 2,
              sign_aware: false,
            },
            delta_bp_prev: {
              raw: -1.5,
              unit: "bp",
              display: "",
              precision: 2,
              sign_aware: true,
            },
          },
        ]),
      ],
      warnings: [],
      computed_at: "2026-04-10T16:00:00Z",
    };
    const model = buildHomeMarketContextModel({
      marketTape: [],
      marketPoints: null,
      macroNewsEvents: null,
      todayIsoDate: "2026-04-10",
      campisiFourEffects: null,
      returnDecomposition: null,
      yieldCurveTermStructure: payload,
      creditSpreadMigration: null,
      attribution: {
        maxDragLabel: "",
        maxContributionLabel: "",
      },
    });

    expect(model.curveTable.title).toBe("国开债收益率");
    expect(model.curveTable.asOfLabel).toBe("2026-04-10");
    expect(model.curveTable.rows).toEqual([
      {
        tenor: "1Y",
        yieldLabel: "1.60%",
        deltaLabel: "-1.20",
        deltaTone: "down",
      },
      {
        tenor: "3Y",
        yieldLabel: "1.78%",
        deltaLabel: "0.00",
        deltaTone: "flat",
      },
      {
        tenor: "5Y",
        yieldLabel: "—",
        deltaLabel: "—",
        deltaTone: "muted",
      },
      {
        tenor: "10Y",
        yieldLabel: "—",
        deltaLabel: "—",
        deltaTone: "muted",
      },
    ]);
    expect(model.curveTable.emptyMessage).toBeNull();
  });

  it("preserves the full formal rate series independently from the market-temperature tape", () => {
    const marketPoint: ChoiceMacroLatestPoint = {
      series_id: "EMM00166502",
      series_name: "10年国开债",
      trade_date: "2026-07-17",
      value_numeric: 1.7875,
      unit: "%",
      latest_change: -0.0035,
      source_version: "sv_choice",
      vendor_version: "vv_choice",
      vendor_name: "Choice",
      refresh_tier: "stable",
      quality_flag: "ok",
      recent_points: [],
    };
    const model = buildHomeMarketContextModel({
      marketTape: [],
      marketPoints: [
        marketPoint,
        {
          ...marketPoint,
          series_id: "TEST.ISOLATED",
          refresh_tier: "isolated",
        },
      ],
      macroNewsEvents: null,
      todayIsoDate: "2026-07-31",
      campisiFourEffects: null,
      returnDecomposition: null,
      yieldCurveTermStructure: null,
      creditSpreadMigration: null,
      attribution: {
        maxDragLabel: "",
        maxContributionLabel: "",
      },
    });

    expect(model.rateSeries).toHaveLength(1);
    expect(model.rateSeries[0]).toMatchObject({
      id: "EMM00166502",
      tradeDate: "2026-07-17",
      vendorName: "Choice",
    });
  });
});
