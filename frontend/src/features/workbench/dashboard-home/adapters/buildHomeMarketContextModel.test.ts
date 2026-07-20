import { describe, expect, it } from "vitest";

import type {
  YieldCurveTermStructureCurvePayload,
  YieldCurveTermStructurePayload,
} from "../../../../api/contracts";
import { buildHomeMarketContextModel } from "./buildHomeMarketContextModel";

function curve(
  curveType: string,
  resolvedDate: string | null,
): YieldCurveTermStructureCurvePayload {
  return {
    curve_type: curveType,
    trade_date_requested: "2026-04-10",
    trade_date_resolved: resolvedDate,
    points: [],
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

    const curveBlock = model.contextBlocks.find((block) => block.id === "curve");
    expect(curveBlock?.foot).toContain("2026-04-10");
    expect(curveBlock?.foot).toContain("2026-04-09");
    expect(model.asOfLabel).not.toContain("2026-04-10");
  });
});
