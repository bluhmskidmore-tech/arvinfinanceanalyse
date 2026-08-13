import type { EChartsOption } from "../../lib/echarts";
import type { PnlByBusinessUntracedTrendRow } from "../../api/contracts";
import { ibTokens } from "../../theme/designSystem";

function toNullableNumber(value: string | null | undefined): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

/**
 * Builds the trend chart option for `reconciliation_diagnostics.rows`.
 *
 * Deliberately uses only the neutral gray scale (no red/yellow/KPI accent
 * colors): this chart is a data-lineage-completeness observation, not a
 * business warning that calls for immediate action.
 *
 * Rows with a `null` `untraced_share_pct` are mapped to `null` data points
 * (a rendered gap via `connectNulls: false`), never coerced to `0`.
 */
export function buildUntracedReconciliationTrendOption(
  rows: PnlByBusinessUntracedTrendRow[],
): EChartsOption {
  const dates = rows.map((row) => row.report_date);
  const values = rows.map((row) => toNullableNumber(row.untraced_share_pct));

  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line" },
      formatter: (params: unknown) => {
        const items = params as Array<{ dataIndex: number }>;
        if (!items.length) return "";
        const row = rows[items[0].dataIndex];
        if (!row) return "";
        const pctText =
          row.untraced_share_pct === null ? "无数据" : `${Number(row.untraced_share_pct).toFixed(2)}%`;
        return [
          `<strong>${row.report_date}</strong>`,
          `未追溯占比：${pctText}`,
          `未追溯行数 / 总行数：${row.untraced_row_count} / ${row.total_row_count}`,
        ].join("<br/>");
      },
    },
    grid: { left: 56, right: 24, top: 24, bottom: 36, containLabel: true },
    xAxis: {
      type: "category" as const,
      data: dates,
      axisLine: { lineStyle: { color: ibTokens.color.hairline } },
      axisLabel: { fontSize: 11, color: ibTokens.color.inkMuted },
    },
    yAxis: {
      type: "value" as const,
      axisLabel: {
        formatter: (value: number) => `${value}%`,
        color: ibTokens.color.inkMuted,
      },
      splitLine: { lineStyle: { color: ibTokens.color.hairline } },
    },
    series: [
      {
        name: "未追溯占比",
        type: "line" as const,
        data: values,
        connectNulls: false,
        symbol: "circle",
        symbolSize: 6,
        lineStyle: { width: 2, color: ibTokens.color.inkSecondary },
        itemStyle: { color: ibTokens.color.inkSecondary },
        areaStyle: { color: ibTokens.color.surfaceMuted },
      },
    ],
  };
}
