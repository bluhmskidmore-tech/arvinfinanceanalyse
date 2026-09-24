import type { YieldCurveTermStructureCurvePayload } from "../../../api/contracts";
import { bondNumericRawOrNull } from "../adapters/bondAnalyticsAdapter";

export function curvePointHasReadout(point: YieldCurveTermStructureCurvePayload["points"][number]) {
  return bondNumericRawOrNull(point.yield_pct) !== null || bondNumericRawOrNull(point.delta_bp_prev) !== null;
}

export function curveHasReadout(curve: YieldCurveTermStructureCurvePayload) {
  return curve.points.some(curvePointHasReadout);
}
