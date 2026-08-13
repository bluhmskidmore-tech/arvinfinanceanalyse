import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type { Numeric, VolumeRateAttributionPayload } from "../../../api/contracts";
import { nocturneTokens } from "../../../theme/designSystem";
import { numericRaw } from "../../../pageModel";
import { useDeferredChartMount } from "./useDeferredChartMount";
import styles from "./portfolioHome.module.css";

const YI = 100_000_000;

function toYi(value: Numeric | null | undefined): number | null {
  const raw = numericRaw(value ?? null);
  return raw === null ? null : raw / YI;
}

/** 正负按 DESIGN.md §4 语义色（up=green / down=red），端点柱用中性蓝灰。 */
function effectColor(value: number | null): string {
  if (value === null) return nocturneTokens.color.inkMuted;
  return value >= 0 ? nocturneTokens.color.green : nocturneTokens.color.red;
}

type PortfolioAttributionWaterfallProps = {
  payload: VolumeRateAttributionPayload | undefined;
};

/**
 * 损益变动「规模/利率/交叉」分解柱图（与归因摘要 primary_driver 同源）。
 * 数据不足（无上期对比）时不渲染，不用占位数据补图。
 */
export function PortfolioAttributionWaterfall({ payload }: PortfolioAttributionWaterfallProps) {
  const { containerRef, ready, onChartReady } = useDeferredChartMount<HTMLDivElement>();

  if (!payload?.has_previous_data) {
    return null;
  }

  const previous = toYi(payload.total_previous_pnl);
  const volume = toYi(payload.total_volume_effect);
  const rate = toYi(payload.total_rate_effect);
  const interaction = toYi(payload.total_interaction_effect);
  const current = toYi(payload.total_current_pnl);

  const categories = ["上期损益", "规模效应", "利率效应"];
  const values: Array<number | null> = [previous, volume, rate];
  const colors = [nocturneTokens.color.inkMuted, effectColor(volume), effectColor(rate)];
  if (interaction !== null && Math.abs(interaction) > 0.001) {
    categories.push("交叉效应");
    values.push(interaction);
    colors.push(nocturneTokens.color.inkMuted);
  }
  categories.push("当期损益");
  values.push(current);
  colors.push(nocturneTokens.color.blue);

  if (values.every((value) => value === null)) {
    return null;
  }

  const option: EChartsOption = {
    animationDuration: 320,
    grid: { left: 52, right: 14, top: 12, bottom: 26 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow", shadowStyle: { color: "rgba(145, 132, 217, 0.08)" } },
      backgroundColor: nocturneTokens.color.panel2,
      borderColor: nocturneTokens.color.line,
      borderWidth: 1,
      padding: [8, 10],
      textStyle: { color: nocturneTokens.color.ink, fontSize: 11, fontWeight: 650 },
      valueFormatter: (value: unknown) =>
        typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(2)} 亿元` : "—",
    },
    xAxis: {
      type: "category",
      data: categories,
      axisLabel: { fontSize: 11, color: nocturneTokens.color.inkMuted, fontWeight: 600, interval: 0 },
      axisTick: { show: false },
      axisLine: { show: false },
    },
    yAxis: {
      type: "value",
      axisLabel: {
        formatter: (value: number) => `${value.toFixed(1)}亿`,
        fontSize: 10,
        color: nocturneTokens.color.inkMuted,
      },
      splitLine: { lineStyle: { type: "dashed", color: nocturneTokens.color.lineSoft, opacity: 0.6 } },
    },
    series: [
      {
        type: "bar",
        barMaxWidth: 26,
        data: values.map((value, index) => ({
          value,
          itemStyle: { color: colors[index], borderRadius: [3, 3, 0, 0] },
        })),
      },
    ],
  };

  return (
    <div
      className={styles.attributionWaterfall}
      ref={containerRef}
      data-testid="module-home-portfolio-pnl-waterfall"
    >
      <div className={styles.attributionWaterfallHead}>
        <span>损益变动分解</span>
        <em>
          {payload.previous_period} → {payload.current_period} · 亿元
        </em>
      </div>
      {ready ? (
        <ReactECharts
          option={option}
          style={{ height: 176, width: "100%" }}
          notMerge
          lazyUpdate
          onChartReady={onChartReady}
        />
      ) : null}
    </div>
  );
}
