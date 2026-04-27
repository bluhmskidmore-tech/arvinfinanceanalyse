import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import type { ApiEnvelope, YieldCurveTermStructurePayload } from "./contracts";

/** Minimal mock for mock-mode clients — keeps `client.ts` free of new payload blocks. */
export function mockBondAnalyticsYieldCurveTermStructure(
  reportDate: string,
): ApiEnvelope<YieldCurveTermStructurePayload> {
  return buildMockApiEnvelope(
    "bond_analytics.yield_curve_term_structure",
    {
      report_date: reportDate,
      curves: [],
      warnings: ["Mock: formal yield-curve term structure uses live API; mock mode has no curve facts."],
      computed_at: new Date().toISOString(),
    },
    { basis: "formal", formal_use_allowed: true },
  );
}
