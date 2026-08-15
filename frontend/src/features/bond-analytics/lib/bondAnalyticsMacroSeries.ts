import type { ChoiceMacroLatestPoint } from "../../../api/contracts";

/**
 * 债券分析首屏「宏观条」与中段曲线用序列。
 * 与 `MarketDataPage` 利率走势（RATE_TREND）及国开 10Y 对齐；标签为业务简称。
 * `series_ids` 为候选 ID 回退列表（与 workbenchShellTicker/dashboardHomeMarket 同模式）：
 * 真实数据集与 mock 数据集的同一指标 ID 不同（如 DR007 真实为 CA.DR007、mock 为 M002），
 * 渲染时取第一个命中的序列，两套数据集都能点亮。
 */
export const BOND_ANALYTICS_MACRO_BAR_SERIES = [
  { series_ids: ["EMM00166466"], shortLabel: "10年国债" },
  { series_ids: ["EMM00166502"], shortLabel: "10年国开" },
  { series_ids: ["EM1", "CA.CN_US_SPREAD"], shortLabel: "中美10年利差" },
  { series_ids: ["CA.DR007", "M002", "EMM00167613"], shortLabel: "DR007" },
  { series_ids: ["EMM00058124", "CA.USDCNY"], shortLabel: "美元/人民币" },
  { series_ids: ["CA.BRENT"], shortLabel: "原油" },
  { series_ids: ["CA.CSI300"], shortLabel: "沪深300" },
] as const;

export function resolveMacroSeriesPoint(
  byId: ReadonlyMap<string, ChoiceMacroLatestPoint>,
  seriesIds: readonly string[],
): ChoiceMacroLatestPoint | undefined {
  for (const seriesId of seriesIds) {
    const point = byId.get(seriesId);
    if (point) {
      return point;
    }
  }
  return undefined;
}

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
