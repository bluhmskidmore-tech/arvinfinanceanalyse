import { useMemo } from "react";
import { type EChartsOption } from "../../../lib/echarts";
import { ChartCard } from "../../../components/charts/ChartCard";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type { ConcentrationMetrics } from "../types";
import { formatYi } from "../utils/formatters";

function concentrationPieOption(metrics: ConcentrationMetrics): EChartsOption {
  return nocturneChartTheme.createBaseChartOption({
    tooltip: {
      trigger: "item",
      formatter: (p) => {
        const item = p as { name: string; value: number; percent: number };
        return `${item.name}: ${formatYi(item.value)} (${item.percent}%)`;
      },
    },
    legend: { show: false },
    series: [
      {
        type: "pie",
        radius: "55%",
        center: ["50%", "56%"],
        data: metrics.top_items.map((it) => ({
          name: it.name,
          value: bondNumericRaw(it.market_value) ?? undefined,
        })),
      },
    ],
  });
}

export function ConcentrationPieCell({ metrics }: { metrics: ConcentrationMetrics | undefined }) {
  const option = useMemo(() => {
    if (!metrics?.top_items?.length) return null;
    return concentrationPieOption(metrics);
  }, [metrics]);

  return (
    <ChartCard
      flat
      title={metrics?.dimension}
      question={
        metrics
          ? `HHI ${metrics.hhi.display} · 前五 ${metrics.top5_concentration.display}`
          : undefined
      }
      ariaLabel={metrics?.dimension ?? "集中度分布"}
      option={option}
      height={220}
      legend="none"
      emptyMessage="暂无数据"
    />
  );
}
