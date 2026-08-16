import type { EChartsOption } from "../../lib/echarts";
import type { PnlByBusinessUntracedTrendRow } from "../../api/contracts";
// 本页为 Nocturne scope：canvas 不消费 CSS 变量，取色走 nocturneTokens 常量组
// （原 ibTokens 为 IB 浅色主题，在深色底上呈浅灰白孤岛）。
import { nocturneTokens } from "../../theme/designSystem";

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
 * Deliberately uses only the neutral Nocturne ink scale (no red/amber/accent
 * colors): this chart is a data-lineage-completeness observation, not a
 * business warning that calls for immediate action.
 *
 * Rows with a `null` `untraced_share_pct` are mapped to `null` data points
 * (a rendered gap via `connectNulls: false`), never coerced to `0`.
 *
 * The tooltip reuses the same normalized `values` as the line series: a raw
 * string the series treats as missing (`null`/empty/non-numeric) must read
 * "无数据" in the tooltip too, never `NaN%` or a fabricated `0.00%`.
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
      backgroundColor: nocturneTokens.color.panel2,
      borderColor: nocturneTokens.color.lineSoft,
      textStyle: { color: nocturneTokens.color.ink, fontSize: 12 },
      formatter: (params: unknown) => {
        const items = params as Array<{ dataIndex: number }>;
        if (!items.length) return "";
        const dataIndex = items[0].dataIndex;
        const row = rows[dataIndex];
        if (!row) return "";
        const value = values[dataIndex];
        const pctText = value === null ? "无数据" : `${value.toFixed(2)}%`;
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
      axisLine: { lineStyle: { color: nocturneTokens.color.lineSoft } },
      axisLabel: { fontSize: 11, color: nocturneTokens.color.inkMuted },
    },
    yAxis: {
      type: "value" as const,
      axisLabel: {
        formatter: (value: number) => `${value}%`,
        color: nocturneTokens.color.inkMuted,
      },
      splitLine: { lineStyle: { color: nocturneTokens.color.lineSoft } },
    },
    series: [
      {
        name: "未追溯占比",
        type: "line" as const,
        data: values,
        connectNulls: false,
        symbol: "circle",
        symbolSize: 6,
        lineStyle: { width: 2, color: nocturneTokens.color.inkSoft },
        itemStyle: { color: nocturneTokens.color.inkSoft },
        // 面积仅作趋势衬底：中性墨阶低透明度，禁用 warning/danger/accent。
        areaStyle: { color: nocturneTokens.color.inkSoft, opacity: 0.12 },
      },
    ],
  };
}
