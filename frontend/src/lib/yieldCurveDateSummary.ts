import type { YieldCurveTermStructureCurvePayload } from "../api/contracts";

export type YieldCurveDateSummary = {
  kind: "none" | "shared" | "per_curve";
  requestedDate: string | null;
  sharedResolvedDate: string | null;
  hasFallback: boolean;
  hasMissing: boolean;
  curveDates: Array<{ curveType: string; resolvedDate: string | null }>;
};

const CURVE_LABELS: Record<string, string> = {
  treasury: "国债",
  cdb: "国开",
  aaa_credit: "AAA 信用",
};

export function summarizeYieldCurveDates(
  curves: readonly YieldCurveTermStructureCurvePayload[],
): YieldCurveDateSummary {
  const requestedDates = new Set(
    curves.map((curve) => curve.trade_date_requested).filter(Boolean),
  );
  const requestedDate =
    requestedDates.size === 1 ? (requestedDates.values().next().value ?? null) : null;
  const curveDates = curves.map((curve) => ({
    curveType: curve.curve_type,
    resolvedDate: curve.trade_date_resolved,
  }));
  const hasMissing = curveDates.some((curve) => curve.resolvedDate === null);
  const resolvedDates = new Set(
    curveDates
      .map((curve) => curve.resolvedDate)
      .filter((date): date is string => date !== null),
  );
  const sharedResolvedDate =
    curves.length > 0 && !hasMissing && resolvedDates.size === 1
      ? (resolvedDates.values().next().value ?? null)
      : null;
  const hasFallback = curves.some(
    (curve) =>
      curve.trade_date_resolved !== null &&
      curve.trade_date_resolved !== curve.trade_date_requested,
  );

  return {
    kind: curves.length === 0 ? "none" : sharedResolvedDate ? "shared" : "per_curve",
    requestedDate,
    sharedResolvedDate,
    hasFallback,
    hasMissing,
    curveDates,
  };
}

export function formatYieldCurveDateSummary(summary: YieldCurveDateSummary): string {
  if (summary.kind === "none") {
    return "曲线交易日：未解析。";
  }
  if (summary.kind === "shared" && summary.sharedResolvedDate) {
    if (
      summary.hasFallback &&
      summary.requestedDate &&
      summary.sharedResolvedDate !== summary.requestedDate
    ) {
      return `曲线交易日已回退至 ${summary.sharedResolvedDate}（请求日 ${summary.requestedDate}）。`;
    }
    return `曲线交易日：${summary.sharedResolvedDate}。`;
  }

  const perCurve = summary.curveDates
    .map(
      ({ curveType, resolvedDate }) =>
        `${CURVE_LABELS[curveType] ?? curveType} ${resolvedDate ?? "未解析"}`,
    )
    .join(" / ");
  return `曲线交易日不一致：${perCurve}。`;
}
