import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type { VolumeRateAttributionPayload } from "../../../api/contracts";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { designTokens } from "../../../theme/designSystem";

const cardStyle = {
  padding: designTokens.space[6],
  borderRadius: designTokens.radius.lg,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.primary[50],
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
  state: DataSectionState;
  onRetry: () => void;
};

/**
 * 损益变动“瀑布”分解柱图：上期损益 → 规模/利率/交叉效应 → 当期损益。
 * 与 V1 一致，采用独立柱高（非累计桥接），强调各分项量级。
 */
export function AttributionWaterfallChart({ data, state, onRetry }: Props) {
  const option = useMemo<EChartsOption | null>(() => {
    if (!data?.has_previous_data) {
      return null;
    }
    const categories: string[] = [];
    const values: number[] = [];
    const colors: string[] = [];

    categories.push("上期损益");
    values.push((data.total_previous_pnl?.raw ?? 0) / 100_000_000);
    colors.push(designTokens.color.neutral[500]);

    const vol = (data.total_volume_effect?.raw ?? 0) / 100_000_000;
    categories.push("规模效应");
    values.push(vol);
    colors.push(vol >= 0 ? designTokens.color.semantic.profit : designTokens.color.semantic.loss);

    const rate = (data.total_rate_effect?.raw ?? 0) / 100_000_000;
    categories.push("利率效应");
    values.push(rate);
    colors.push(
      rate >= 0 ? designTokens.color.info[500] : designTokens.color.warning[500],
    );

    const cross = (data.total_interaction_effect?.raw ?? 0) / 100_000_000;
    if (Math.abs(cross) > 0.001) {
      categories.push("交叉效应");
      values.push(cross);
      colors.push(designTokens.color.primary[500]);
    }

    categories.push("当期损益");
    values.push((data.total_current_pnl.raw ?? 0) / 100_000_000);
    colors.push(designTokens.color.primary[600]);

    return {
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        valueFormatter: (v) => `${Number(v).toFixed(2)} 亿元`,
      },
      grid: { left: 48, right: designTokens.space[6], top: designTokens.space[6], bottom: designTokens.space[7] },
      xAxis: {
        type: "category",
        data: categories,
        axisLabel: { fontSize: designTokens.fontSize[11], color: designTokens.color.neutral[700] },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          formatter: (v: number) => `${v.toFixed(1)}亿`,
          color: designTokens.color.neutral[700],
        },
        splitLine: { lineStyle: { type: "dashed", color: designTokens.color.neutral[100] } },
      },
      series: [
        {
          type: "bar",
          data: values.map((v, i) => ({
            value: v,
            itemStyle: {
              color: colors[i],
              borderRadius: [designTokens.radius.sm, designTokens.radius.sm, 0, 0],
            },
          })),
        },
      ],
    };
  }, [data]);

  return (
    <DataSection title="损益变动归因分解" state={state} onRetry={onRetry}>
      {!data ? null : !data.has_previous_data || !option ? (
        <div style={{ ...cardStyle, textAlign: "center", color: designTokens.color.neutral[700] }}>
          {!data.has_previous_data ? "无上期对比数据，无法展示归因瀑布图。" : "暂无数据"}
        </div>
      ) : (
        <div style={cardStyle}>
          <p
            style={{
              margin: `0 0 ${designTokens.space[3]}px`,
              fontSize: designTokens.fontSize[13],
              color: designTokens.color.neutral[700],
              lineHeight: designTokens.lineHeight.normal,
            }}
          >
            规模一阶效应近似为 Δ规模×上期收益率；利率一阶效应近似为上期规模×Δ收益率；交叉效应为残差项。与
            Campisi 框架中的收入、国债、利差、选择等解释维度互补。
          </p>
          <ReactECharts option={option} style={{ height: 300 }} notMerge lazyUpdate />
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: designTokens.space[4],
              justifyContent: "center",
              marginTop: designTokens.space[3],
              fontSize: designTokens.fontSize[12],
              color: designTokens.color.neutral[700],
            }}
          >
            <span>当期损益 {formatYi(data.total_current_pnl.raw ?? undefined)}</span>
            <span>规模效应 {formatYi(data.total_volume_effect?.raw ?? undefined)}</span>
            <span>利率效应 {formatYi(data.total_rate_effect?.raw ?? undefined)}</span>
          </div>
        </div>
      )}
    </DataSection>
  );
}
