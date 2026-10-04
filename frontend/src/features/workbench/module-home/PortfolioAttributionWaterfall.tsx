import DeferredChart, { type EChartsOption } from "../../../lib/echarts";
import { ChartCard } from "../../../components/charts/ChartCard";
import { PageStateSurface } from "../../../components/page/PagePrimitives";
import type { Numeric, VolumeRateAttributionPayload } from "../../../api/contracts";
import { nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH, numericRaw, type StateSurfaceItem } from "../../../pageModel";
import { hasDirectPnlAttribution } from "../../pnl-attribution/components/pnlAttributionViewModel";
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
  state?: StateSurfaceItem[];
};

/**
 * 损益变动分解柱图与归因页同源，完整列示利息量价、非利息直接变动及残差。
 * 数据不足时保留来源状态，不用占位数据补图。
 */
export function PortfolioAttributionWaterfall({ payload, state = [] }: PortfolioAttributionWaterfallProps) {
  if (!payload?.has_previous_data && state.length === 0) return null;
  return (
    <div className={styles.attributionWaterfall} data-testid="module-home-portfolio-pnl-waterfall">
      {state.map((item) => (
        <PageStateSurface key={item.key} variant={item.variant} title={item.title} description={item.description} />
      ))}
      <PortfolioAttributionChart payload={payload} />
    </div>
  );
}

function PortfolioAttributionChart({ payload }: Pick<PortfolioAttributionWaterfallProps, "payload">) {
  const { containerRef, ready, onChartReady } = useDeferredChartMount<HTMLDivElement>();

  if (!payload?.has_previous_data) {
    return null;
  }

  const previous = toYi(payload.total_previous_pnl);
  const volume = toYi(payload.total_volume_effect);
  const rate = toYi(payload.total_rate_effect);
  const interaction = toYi(payload.total_interaction_effect);
  const includesDirectPnl = hasDirectPnlAttribution(payload);
  const unexplained = toYi(payload.total_recon_error);
  const current = toYi(payload.total_current_pnl);

  const categories = [
    "上期损益",
    includesDirectPnl ? "利息规模效应" : "规模效应",
    includesDirectPnl ? "利息收益率效应" : "利率效应",
    "交叉效应",
  ];
  const values: Array<number | null> = [previous, volume, rate, interaction];
  const colors = [nocturneTokens.color.inkMuted, effectColor(volume), effectColor(rate), nocturneTokens.color.inkMuted];
  if (includesDirectPnl) {
    const directEffects = [
      toYi(payload.total_fair_value_effect),
      toYi(payload.total_capital_gain_effect),
      toYi(payload.total_manual_adjustment_effect),
    ];
    categories.push("公允价值变动", "投资收益变动", "手工调整变动");
    values.push(...directEffects);
    colors.push(...directEffects.map(effectColor));
  }
  categories.push("未解释差额");
  values.push(unexplained);
  colors.push(nocturneTokens.color.inkMuted);
  categories.push("当期损益");
  values.push(current);
  colors.push(nocturneTokens.color.blue);

  if (values.every((value) => value === null)) {
    return null;
  }

  const option: EChartsOption = {
    animationDuration: 320,
    grid: { left: 52, right: 14, top: 12 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow", shadowStyle: { color: "rgba(145, 132, 217, 0.08)" } },
      padding: [8, 10],
      valueFormatter: (value: unknown) =>
        typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(2)} 亿元` : EM_DASH,
    },
    xAxis: {
      type: "category",
      data: categories,
      axisLabel: { fontSize: 11, color: nocturneTokens.color.inkMuted, fontWeight: 600, interval: 0, ...(includesDirectPnl ? { rotate: 20 } : {}) },
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
          itemStyle: { color: colors[index] },
        })),
      },
    ],
  };

  return (
    <div ref={containerRef}>
      <ChartCard
        flat
        title="损益变动分解"
        question={`${payload.previous_period} 至 ${payload.current_period}${includesDirectPnl ? "；利息收益率按期末市值、非年化" : ""}`}
        unit="亿元"
        option={option}
        height={160}
        legend="none"
        chartRenderer={({ option: chromedOption, height }) =>
          ready ? (
            <DeferredChart
              option={chromedOption}
              style={{ height, width: "100%" }}
              notMerge
              lazyUpdate
              onChartReady={onChartReady}
            />
          ) : null
        }
      />
    </div>
  );
}
