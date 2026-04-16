import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type { VolumeRateAttributionPayload } from "../../../api/contracts";

const cardStyle = {
  padding: 24,
  borderRadius: 16,
  border: "1px solid #e4ebf5",
  background: "#ffffff",
} as const;

function formatYi(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const yi = value / 100_000_000;
  return `${yi >= 0 ? "+" : ""}${yi.toFixed(2)} 亿`;
}

type Props = {
  data: VolumeRateAttributionPayload | null;
};

/**
 * 损益变动“瀑布”分解柱图：上期损益 → 规模/利率/交叉效应 → 当期损益。
 * 与 V1 一致，采用独立柱高（非累计桥接），强调各分项量级。
 */
export function AttributionWaterfallChart({ data }: Props) {
  const option = useMemo<EChartsOption | null>(() => {
    if (!data?.has_previous_data) {
      return null;
    }
    const categories: string[] = [];
    const values: number[] = [];
    const colors: string[] = [];

    categories.push("上期损益");
    values.push((data.total_previous_pnl ?? 0) / 100_000_000);
    colors.push("#94a3b8");

    const vol = (data.total_volume_effect ?? 0) / 100_000_000;
    categories.push("规模效应");
    values.push(vol);
    colors.push(vol >= 0 ? "#22c55e" : "#ef4444");

    const rate = (data.total_rate_effect ?? 0) / 100_000_000;
    categories.push("利率效应");
    values.push(rate);
    colors.push(rate >= 0 ? "#3b82f6" : "#f97316");

    const cross = (data.total_interaction_effect ?? 0) / 100_000_000;
    if (Math.abs(cross) > 0.001) {
      categories.push("交叉效应");
      values.push(cross);
      colors.push("#a855f7");
    }

    categories.push("当期损益");
    values.push(data.total_current_pnl / 100_000_000);
    colors.push("#0ea5e9");

    return {
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        valueFormatter: (v) => `${Number(v).toFixed(2)} 亿元`,
      },
      grid: { left: 48, right: 24, top: 24, bottom: 32 },
      xAxis: {
        type: "category",
        data: categories,
        axisLabel: { fontSize: 11, color: "#5c6b82" },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          formatter: (v: number) => `${v.toFixed(1)}亿`,
          color: "#5c6b82",
        },
        splitLine: { lineStyle: { type: "dashed", color: "#e8edf5" } },
      },
      series: [
        {
          type: "bar",
          data: values.map((v, i) => ({
            value: v,
            itemStyle: { color: colors[i], borderRadius: [4, 4, 0, 0] },
          })),
        },
      ],
    };
  }, [data]);

  if (!data) {
    return (
      <div style={{ ...cardStyle, textAlign: "center", color: "#5c6b82" }}>暂无数据</div>
    );
  }

  if (!data.has_previous_data || !option) {
    return (
      <div style={{ ...cardStyle, textAlign: "center", color: "#5c6b82" }}>
        无上期对比数据，无法展示归因瀑布图。
      </div>
    );
  }

  return (
    <div style={cardStyle}>
      <h3 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 600, color: "#162033" }}>
        损益变动归因分解
      </h3>
      <p style={{ margin: "0 0 12px", fontSize: 13, color: "#5c6b82", lineHeight: 1.5 }}>
        规模一阶效应近似为 Δ规模×上期收益率；利率一阶效应近似为上期规模×Δ收益率；交叉效应为残差项。与
        Campisi 框架中的收入、国债、利差、选择等解释维度互补。
      </p>
      <ReactECharts option={option} style={{ height: 300 }} notMerge lazyUpdate />
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          justifyContent: "center",
          marginTop: 12,
          fontSize: 12,
          color: "#5c6b82",
        }}
      >
        <span>当期损益 {formatYi(data.total_current_pnl)}</span>
        <span>规模效应 {formatYi(data.total_volume_effect)}</span>
        <span>利率效应 {formatYi(data.total_rate_effect)}</span>
      </div>
    </div>
  );
}
