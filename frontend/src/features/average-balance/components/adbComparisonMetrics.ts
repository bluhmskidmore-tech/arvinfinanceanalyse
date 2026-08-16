/**
 * 期末时点 vs 区间日均的偏离度（%）。
 * 字典查证：docs/metric_dictionary.md §15.2.3 的 MTR-ADB-001~007 未登记“偏离度”条目，
 * 本值属前端展示派生（非正式指标）。按仓库 null-vs-0 纪律（“无法计算”≠ 0）：
 * 分母（日均余额）≤ 0 或缺失时返回 null，由渲染层显示 EM_DASH，预警逻辑跳过 null；
 * 禁止返回 0 伪造“无偏离”读数。
 */
export function computeComparisonDeviationPct(
  spotBalance: number | null,
  avgBalance: number | null,
): number | null {
  if (spotBalance === null || Number.isNaN(spotBalance)) return null;
  if (avgBalance === null || Number.isNaN(avgBalance)) return null;
  return avgBalance > 0 ? ((spotBalance - avgBalance) / avgBalance) * 100 : null;
}

/**
 * 偏离预警阈值（双侧）：|偏离| > 5%。KPI 警示与对比图标签着色共用同一判据；
 * 指标字典未登记单侧警戒口径，正偏离（期末冲高）与负偏离（期末压降）同等预警。
 */
export const COMPARISON_DEVIATION_ALERT_THRESHOLD_PCT = 5;

export function isComparisonDeviationAlert(pct: number | null): boolean {
  return pct !== null && Math.abs(pct) > COMPARISON_DEVIATION_ALERT_THRESHOLD_PCT;
}

export type AdbComparisonChartRow = {
  label: string;
  /** null 表示缺数：系列不画柱，tooltip 显示 EM_DASH */
  spot: number | null;
  avg: number | null;
  deviationPct: number | null;
};

/**
 * 对比图展示层聚合：按日均（缺则期末）规模降序取 Top N，其余合并为「其他」。
 * 全量分类直接进坐标轴会把轴标签压成墨团，聚合仅改变图上呈现，
 * 全量明细仍在下方分类明细表中。「其他」任一成员缺数即置 null
 * （缺数不当 0 相加），其偏离度用与逐行一致的展示层派生公式重算。
 */
export function buildComparisonDisplayRows(
  rows: AdbComparisonChartRow[],
  topN = 10,
): AdbComparisonChartRow[] {
  if (rows.length <= topN + 1) return rows;
  const magnitude = (row: AdbComparisonChartRow): number => {
    const value = row.avg ?? row.spot;
    return value === null || Number.isNaN(value) ? Number.NEGATIVE_INFINITY : Math.abs(value);
  };
  const sorted = rows.slice().sort((left, right) => magnitude(right) - magnitude(left));
  const top = sorted.slice(0, topN);
  const rest = sorted.slice(topN);
  const sumOrNull = (values: Array<number | null>): number | null =>
    values.some((value) => value === null || Number.isNaN(value))
      ? null
      : values.reduce<number>((acc, value) => acc + (value as number), 0);
  const spot = sumOrNull(rest.map((row) => row.spot));
  const avg = sumOrNull(rest.map((row) => row.avg));
  return [
    ...top,
    {
      label: `其他（${rest.length} 类合计）`,
      spot,
      avg,
      deviationPct: computeComparisonDeviationPct(spot, avg),
    },
  ];
}
