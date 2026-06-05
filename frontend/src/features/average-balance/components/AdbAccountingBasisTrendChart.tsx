import ReactECharts from "../../../lib/echarts";
import type { AdbAccountingBasisDailyAvgTrendItem } from "../../../api/contracts";

const YI = 100_000_000;

export type AdbAccountingBasisTrendChartProps = {
  trend: AdbAccountingBasisDailyAvgTrendItem[];
  height?: number;
};

function collectBuckets(trend: AdbAccountingBasisDailyAvgTrendItem[]): string[] {
  const set = new Set<string>();
  for (const item of trend) {
    for (const row of item.rows) {
      const b = (row.basis_bucket || "").trim() || "—";
      set.add(b);
    }
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b));
}

function buildOption(trend: AdbAccountingBasisDailyAvgTrendItem[]) {
  const labels = trend.map((t) => t.report_month || t.report_date?.slice(0, 7) || "—");
  const buckets = collectBuckets(trend);
  const series = buckets.map((bucket) => ({
    name: bucket,
    type: "line" as const,
    symbol: "circle",
    symbolSize: 4,
    data: trend.map((t) => {
      const row = t.rows.find((r) => (r.basis_bucket || "").trim() === bucket);
      if (!row) return null;
      return row.daily_avg_balance / YI;
    }),
  }));

  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter: (items: { seriesName: string; value: number | null; dataIndex: number }[]) => {
        if (!items.length) return "";
        const idx = items[0].dataIndex;
        const header = `<strong>${labels[idx]}</strong>`;
        const lines = items
          .filter((item) => item.value !== null && item.value !== undefined && !Number.isNaN(item.value))
          .map((item) => `${item.seriesName}：${Number(item.value).toFixed(2)} 亿元`);
        return [header, ...lines].join("<br/>");
      },
    },
    legend: { data: buckets, top: 0, type: "scroll" },
    grid: { left: 56, right: 24, top: 48, bottom: 36 },
    xAxis: {
      type: "category",
      data: labels,
      axisLabel: { fontSize: 11 },
      boundaryGap: false,
    },
    yAxis: {
      type: "value",
      axisLabel: { formatter: (v: number) => `${v.toFixed(0)}亿` },
      splitLine: { lineStyle: { type: "dashed", color: "#e5e7eb" } },
    },
    series,
  };
}

/** 会计分桶日均余额按月的走势；数据来自后端 trend。 */
export default function AdbAccountingBasisTrendChart({
  trend,
  height = 300,
}: AdbAccountingBasisTrendChartProps) {
  if (!trend.length) return null;
  return <ReactECharts option={buildOption(trend)} style={{ width: "100%", height }} notMerge lazyUpdate />;
}
