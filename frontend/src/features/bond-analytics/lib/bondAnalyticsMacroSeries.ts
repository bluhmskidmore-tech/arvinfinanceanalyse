import type { ChoiceMacroLatestPoint } from "../../../api/contracts";

/**
 * 债券分析首屏「宏观条」与中段曲线用序列。
 * 与 `MarketDataPage` 利率走势（RATE_TREND）及国开 10Y 对齐；标签为业务简称。
 */
export const BOND_ANALYTICS_MACRO_BAR_SERIES = [
  { series_id: "EMM00166466", shortLabel: "10年国债" },
  { series_id: "EMM00166502", shortLabel: "10年国开" },
  { series_id: "CA.CN_US_SPREAD", shortLabel: "中美10年利差" },
  { series_id: "M002", shortLabel: "DR007" },
  { series_id: "CA.USDCNY", shortLabel: "美元/人民币" },
  { series_id: "CA.BRENT", shortLabel: "原油" },
  { series_id: "CA.CSI300", shortLabel: "沪深300" },
] as const;

/** 中段「曲线走势」时间序列：国债 10Y + 国开长端 + 国开 5Y（与宏观走势一致、偏期限结构链） */
export const BOND_ANALYTICS_OVERVIEW_RATE_CHART_SERIES = [
  { series_id: "EMM00166466", name: "国债 10Y" },
  { series_id: "EMM00166502", name: "国开 10Y" },
  { series_id: "EMM00166462", name: "国开 5Y" },
] as const;

export function coalesceMacroSeriesDelta(point: ChoiceMacroLatestPoint | undefined): number | null {
  if (!point) return null;
  if (point.latest_change != null && Number.isFinite(point.latest_change)) {
    return point.latest_change;
  }
  const sorted = [...(point.recent_points ?? [])].sort((a, b) => a.trade_date.localeCompare(b.trade_date));
  if (sorted.length < 2) return null;
  const last = sorted[sorted.length - 1]?.value_numeric;
  const prev = sorted[sorted.length - 2]?.value_numeric;
  if (!Number.isFinite(last) || !Number.isFinite(prev)) return null;
  return (last as number) - (prev as number);
}

export function buildMacroPointForDeltaDisplay(
  point: ChoiceMacroLatestPoint,
  delta: number | null,
): ChoiceMacroLatestPoint {
  if (delta == null) {
    return point;
  }
  return { ...point, latest_change: delta };
}
