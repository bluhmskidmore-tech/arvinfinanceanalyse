import { useMemo } from "react";

import type { AdbMonthlyDataItem } from "../../../api/contracts/cubeAdb";
import { ChartCard } from "../../../components/charts/ChartCard";
import { CHART_CARD_HEIGHTS } from "../../../components/charts/chartCardScale";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import type { EChartsOption } from "../../../lib/echarts";
import { EM_DASH } from "../../../utils/format";

function finiteOrNull(value: number | null): number | null {
  return value === null || !Number.isFinite(value) ? null : value;
}

function monthLabel(point: AdbMonthlyDataItem): string {
  if (point.month_label.trim()) return point.month_label;
  const monthNumber = Number.parseInt(point.month.slice(5, 7), 10);
  return Number.isFinite(monthNumber) ? `${monthNumber}月` : point.month;
}

function buildYieldTrendOption(points: AdbMonthlyDataItem[]): EChartsOption {
  const colors = nocturneChartTheme.categoricalPalette;

  /* 图例位置 / 网格底边由 ChartCard 铬件统一（图例左下一行）。 */
  return nocturneChartTheme.createLineChartOption({
    color: [colors[0], colors[2], colors[1]],
    grid: { left: 6, right: 10, top: 12 },
    tooltip: {
      formatter: (params: unknown) => {
        const rows = Array.isArray(params)
          ? (params as Array<{
              axisValue?: string;
              marker?: string;
              seriesName?: string;
              value?: number | null;
            }>)
          : [];
        const date = rows[0]?.axisValue ?? "";
        return [
          date,
          ...rows.map((row) => {
            const value = typeof row.value === "number" ? `${row.value.toFixed(2)}%` : EM_DASH;
            return `${row.marker ?? ""}${row.seriesName ?? ""} ${value}`;
          }),
        ].join("<br/>");
      },
    },
    xAxis: {
      data: points.map(monthLabel),
      axisTick: { show: false },
      axisLabel: { interval: 0 },
    },
    yAxis: {
      scale: true,
      axisLabel: {
        formatter: (value: number) => `${value.toFixed(1)}%`,
      },
    },
    series: [
      {
        name: "资产收益",
        type: "line",
        data: points.map((point) => finiteOrNull(point.asset_yield)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 2 },
      },
      {
        name: "负债成本",
        type: "line",
        data: points.map((point) => finiteOrNull(point.liability_cost)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 2 },
      },
      {
        name: "NIM",
        type: "line",
        data: points.map((point) => finiteOrNull(point.net_interest_margin)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 2, type: "dashed" },
      },
    ],
  });
}

type LiabilityYieldTrendPanelProps = {
  year: number;
  months?: AdbMonthlyDataItem[];
  loading?: boolean;
  error?: boolean;
};

export function LiabilityYieldTrendPanel({ year, months, loading, error }: LiabilityYieldTrendPanelProps) {
  const points = useMemo(
    () =>
      [...(months ?? [])]
        .filter((point) => Boolean(point.month))
        .sort((left, right) => left.month.localeCompare(right.month)),
    [months],
  );
  const observationCount = points.filter(
    (point) =>
      point.asset_yield !== null || point.liability_cost !== null || point.net_interest_margin !== null,
  ).length;
  const option = useMemo(() => buildYieldTrendOption(points), [points]);

  /* 2026-09-02 迁入 ChartCard（compact 160）：五态由铬件承担，年份与口径落到 unit · asOf 元信息位。 */
  return (
    <ChartCard
      testId="liability-yield-trend"
      ariaLabel="月度日均资产收益、负债成本与净息差趋势"
      title="月度收益成本趋势"
      question="月度日均口径"
      unit="%"
      asOf={`${year} 年`}
      height={CHART_CARD_HEIGHTS.compact}
      option={observationCount >= 2 ? option : null}
      state={loading ? "loading" : error ? "error" : undefined}
      errorMessage="月度趋势读取失败。"
      emptyMessage="暂无足够月度序列，至少需要 2 个月。"
    />
  );
}
