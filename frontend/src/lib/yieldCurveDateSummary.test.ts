import { describe, expect, it } from "vitest";

import type { YieldCurveTermStructureCurvePayload } from "../api/contracts";
import { summarizeYieldCurveDates } from "./yieldCurveDateSummary";

function curve(
  curveType: string,
  requestedDate: string,
  resolvedDate: string | null,
): YieldCurveTermStructureCurvePayload {
  return {
    curve_type: curveType,
    trade_date_requested: requestedDate,
    trade_date_resolved: resolvedDate,
    points: [],
    source_version: "test",
    rule_version: "test",
    vendor_name: "test",
    vendor_version: "test",
  };
}

describe("summarizeYieldCurveDates", () => {
  it("returns one shared exact date only when every curve resolves to it", () => {
    const summary = summarizeYieldCurveDates([
      curve("treasury", "2026-04-10", "2026-04-10"),
      curve("cdb", "2026-04-10", "2026-04-10"),
    ]);

    expect(summary).toMatchObject({
      kind: "shared",
      requestedDate: "2026-04-10",
      sharedResolvedDate: "2026-04-10",
      hasFallback: false,
      hasMissing: false,
    });
  });

  it("marks a shared earlier date as fallback", () => {
    const summary = summarizeYieldCurveDates([
      curve("treasury", "2026-04-11", "2026-04-10"),
      curve("cdb", "2026-04-11", "2026-04-10"),
    ]);

    expect(summary).toMatchObject({
      kind: "shared",
      requestedDate: "2026-04-11",
      sharedResolvedDate: "2026-04-10",
      hasFallback: true,
      hasMissing: false,
    });
  });

  it("keeps mixed and missing dates per curve instead of choosing the first one", () => {
    const summary = summarizeYieldCurveDates([
      curve("treasury", "2026-04-10", "2026-04-10"),
      curve("cdb", "2026-04-10", "2026-04-09"),
      curve("aaa_credit", "2026-04-10", null),
    ]);

    expect(summary).toMatchObject({
      kind: "per_curve",
      requestedDate: "2026-04-10",
      sharedResolvedDate: null,
      hasFallback: true,
      hasMissing: true,
    });
    expect(summary.curveDates).toEqual([
      { curveType: "treasury", resolvedDate: "2026-04-10" },
      { curveType: "cdb", resolvedDate: "2026-04-09" },
      { curveType: "aaa_credit", resolvedDate: null },
    ]);
  });
});
