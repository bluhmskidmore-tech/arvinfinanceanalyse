import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type { ConcentrationMetrics } from "../types";
import { designTokens, nocturneTokens } from "../../../theme/designSystem";
import { formatYi } from "../utils/formatters";

const dt = designTokens;

function concentrationPieOption(metrics: ConcentrationMetrics): EChartsOption {
  return {
    title: {
      text: `${metrics.dimension}  HHI ${metrics.hhi.display}  前五 ${metrics.top5_concentration.display}`,
      left: "center",
      top: dt.space[1],
      textStyle: { fontSize: dt.fontSize[11], color: nocturneTokens.color.inkMuted },
    },
    tooltip: {
      trigger: "item",
      formatter: (p) => {
        const item = p as { name: string; value: number; percent: number };
        return `${item.name}: ${formatYi(item.value)} (${item.percent}%)`;
      },
    },
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
  };
}

export function ConcentrationPieCell({ metrics }: { metrics: ConcentrationMetrics | undefined }) {
  const option = useMemo(() => {
    if (!metrics?.top_items?.length) return null;
    return concentrationPieOption(metrics);
  }, [metrics]);

  if (!option) {
    return (
      <div
        style={{
          height: 200,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--dh-api-muted)",
        }}
      >
        暂无数据
      </div>
    );
  }

  return <ReactECharts option={option} style={{ height: 200 }} />;
}
