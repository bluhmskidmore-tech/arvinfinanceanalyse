import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../../../utils/choiceMacroFormat";

export type MarketHomeSparklineRow = {
  key: string;
  label: string;
  value: string;
  tradeDate: string;
  source: string;
  tone: "ok" | "watch" | "error" | "muted";
  detail?: string;
  sparkline?: readonly number[];
};

const DEFAULT_SPARKLINE_POINTS = 12;

export function choiceSeriesById(
  latestSeries: ChoiceMacroLatestPoint[],
  rateSeries: ChoiceMacroLatestPoint[],
): Map<string, ChoiceMacroLatestPoint> {
  const map = new Map<string, ChoiceMacroLatestPoint>();
  for (const point of [...rateSeries, ...latestSeries]) {
    if (!map.has(point.series_id)) {
      map.set(point.series_id, point);
    }
  }
  return map;
}

export function sparklineFromChoicePoint(
  point: ChoiceMacroLatestPoint | undefined,
  limit = DEFAULT_SPARKLINE_POINTS,
): readonly number[] | undefined {
  if (!point) {
    return undefined;
  }

  const sorted = [...(point.recent_points ?? [])].sort((left, right) =>
    left.trade_date.localeCompare(right.trade_date),
  );
  if (sorted.length >= 2) {
    return sorted.slice(-limit).map((item) => item.value_numeric);
  }

  if (point.latest_change != null && Number.isFinite(point.value_numeric) && Number.isFinite(point.latest_change)) {
    return [point.value_numeric - point.latest_change, point.value_numeric];
  }

  return undefined;
}

export function resolveMacroSnapshotDetail(
  point: ChoiceMacroLatestPoint,
  byId: Map<string, ChoiceMacroLatestPoint>,
): string | undefined {
  if (point.series_id === "CA.CSI300") {
    const pctPoint = byId.get("CA.CSI300_PCT_CHG");
    if (pctPoint) {
      const pctText = formatChoiceMacroValue(pctPoint, { spaceBeforeUnit: false });
      return pctText ? `日变动 ${pctText}` : undefined;
    }
  }

  const change = formatChoiceMacroDelta(point, { spaceBeforeUnit: false, emptyDisplay: "" });
  return change || undefined;
}

export function enrichMarketHomeRow<T extends MarketHomeSparklineRow>(
  row: T,
  byId: Map<string, ChoiceMacroLatestPoint>,
): T {
  const point = byId.get(row.source);
  const sparklinePoint =
    point?.series_id === "CA.CSI300" ? byId.get("CA.CSI300_PCT_CHG") ?? point : point;
  const detail = point && row.source === "CA.CSI300" ? resolveMacroSnapshotDetail(point, byId) ?? row.detail : row.detail;
  const sparkline = sparklineFromChoicePoint(sparklinePoint);
  if (detail === row.detail && !sparkline) {
    return row;
  }
  return {
    ...row,
    ...(detail !== row.detail ? { detail } : {}),
    ...(sparkline ? { sparkline } : {}),
  } as T;
}

export function enrichMarketHomeRows<T extends MarketHomeSparklineRow>(
  rows: T[],
  byId: Map<string, ChoiceMacroLatestPoint>,
): T[] {
  return rows.map((row) => enrichMarketHomeRow(row, byId));
}
