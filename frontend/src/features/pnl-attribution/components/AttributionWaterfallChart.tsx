import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type { Numeric, VolumeRateAttributionPayload } from "../../../api/contracts";
import { PageDataSection } from "../../../components/page/PageDataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { designTokens, ibTokens } from "../../../theme/designSystem";
import { numericRaw } from "../../../pageModel";
import "./AttributionWaterfallChart.css";

function formatYi(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const yi = value / 100_000_000;
  return `${yi >= 0 ? "+" : ""}${yi.toFixed(2)} 亿`;
}

function rawOrNull(value: Numeric | null | undefined): number | null {
  return numericRaw(value);
}

function formatTooltipYi(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? `${value.toFixed(2)} 亿元`
    : "—";
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
    const values: Array<number | null> = [];
    const colors: string[] = [];

    categories.push("上期损益");
    const previousRaw = rawOrNull(data.total_previous_pnl);
    values.push(previousRaw === null ? null : previousRaw / 100_000_000);
    colors.push(ibTokens.color.inkMuted);

    const volumeRaw = rawOrNull(data.total_volume_effect);
    const vol = volumeRaw === null ? null : volumeRaw / 100_000_000;
    categories.push("规模效应");
    values.push(vol);
    colors.push(
      vol === null
        ? ibTokens.color.inkMuted
        : vol >= 0
          ? ibTokens.color.down
          : ibTokens.color.up,
    );

    const rateRaw = rawOrNull(data.total_rate_effect);
    const rate = rateRaw === null ? null : rateRaw / 100_000_000;
    categories.push("利率效应");
    values.push(rate);
    colors.push(
      rate === null
        ? ibTokens.color.inkMuted
        : rate >= 0
          ? ibTokens.color.down
          : ibTokens.color.up,
    );

    const crossRaw = rawOrNull(data.total_interaction_effect);
    const cross = crossRaw === null ? null : crossRaw / 100_000_000;
    if (cross !== null && Math.abs(cross) > 0.001) {
      categories.push("交叉效应");
      values.push(cross);
      colors.push(ibTokens.color.inkMuted);
    }

    categories.push("当期损益");
    const currentRaw = rawOrNull(data.total_current_pnl);
    values.push(currentRaw === null ? null : currentRaw / 100_000_000);
    colors.push(ibTokens.color.accent);

    return {
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        valueFormatter: formatTooltipYi,
      },
      grid: {
        left: 48,
        right: designTokens.space[6],
        top: designTokens.space[6],
        bottom: designTokens.space[7],
      },
      xAxis: {
        type: "category",
        data: categories,
        axisLabel: {
          fontSize: ibTokens.kicker.fontSize,
          color: ibTokens.color.inkMuted,
        },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          formatter: (v: number) => `${v.toFixed(1)}亿`,
          color: ibTokens.color.inkMuted,
        },
        splitLine: {
          lineStyle: { type: "solid", color: ibTokens.color.hairline },
        },
      },
      series: [
        {
          type: "bar",
          data: values.map((v, i) => ({
            value: v,
            itemStyle: {
              color: colors[i],
              borderRadius: [
                designTokens.radius.sm,
                designTokens.radius.sm,
                0,
                0,
              ],
            },
          })),
        },
      ],
    };
  }, [data]);
  const unexplainedEffect =
    data?.has_previous_data && data.total_recon_error?.raw != null
      ? data.total_recon_error.raw
      : undefined;

  return (
    <PageDataSection title="损益变动归因分解" state={state} onRetry={onRetry}>
      {!data ? null : !data.has_previous_data || !option ? (
        <div className="attribution-waterfall-chart__card attribution-waterfall-chart__empty">
          {!data.has_previous_data
            ? "无上期对比数据，无法展示归因瀑布图。"
            : "暂无数据"}
        </div>
      ) : (
        <div className="attribution-waterfall-chart__card">
          <p className="attribution-waterfall-chart__copy">
            规模一阶效应近似为
            Δ规模×上期收益率；利率一阶效应近似为上期规模×Δ收益率；交叉效应为规模与收益率同时变化的二阶联动项；
            未解释差额为损益变动扣除三项效应后的归因残差。与 Campisi
            框架中的收入、国债、利差、选择等解释维度互补。
          </p>
          <ReactECharts
            option={option}
            className="attribution-waterfall-chart__chart"
            notMerge
            lazyUpdate
          />
          <div className="attribution-waterfall-chart__legend">
            <span>
              当期损益 {formatYi(data.total_current_pnl.raw ?? undefined)}
            </span>
            <span>
              规模效应 {formatYi(data.total_volume_effect?.raw ?? undefined)}
            </span>
            <span>
              利率效应 {formatYi(data.total_rate_effect?.raw ?? undefined)}
            </span>
            <span>
              交叉效应{" "}
              {formatYi(data.total_interaction_effect?.raw ?? undefined)}
            </span>
            {unexplainedEffect != null ? (
              <span>未解释差额 {formatYi(unexplainedEffect)}</span>
            ) : null}
          </div>
        </div>
      )}
    </PageDataSection>
  );
}
