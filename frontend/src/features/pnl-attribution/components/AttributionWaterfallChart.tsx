import { useMemo } from "react";
import type { EChartsOption } from "../../../lib/echarts";
import type { Numeric, VolumeRateAttributionPayload } from "../../../api/contracts";
import { ChartCard } from "../../../components/charts/ChartCard";
import { PageDataSection } from "../../../components/page/PageDataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { designTokens, nocturneTokens } from "../../../theme/designSystem";
import { numericRaw } from "../../../pageModel";
import { EM_DASH } from "../../../utils/format";
import {
  type AttributionBridgeTone,
  buildAttributionBridge,
  formatYi,
  hasDirectPnlAttribution,
} from "./pnlAttributionViewModel";
import "./AttributionWaterfallChart.css";

function rawOrNull(value: Numeric | null | undefined): number | null {
  return numericRaw(value);
}

function yiOrNull(value: Numeric | null | undefined): number | null {
  const raw = rawOrNull(value);
  return raw === null ? null : raw / 100_000_000;
}

function formatTooltipYi(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? `${value.toFixed(2)} 亿元`
    : EM_DASH;
}

function signedYiLabel(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

// ECharts canvas 读不到 CSS 变量，按 tone.ts 指南使用 Nocturne TS 镜像 token。
const BRIDGE_TONE_COLOR: Record<AttributionBridgeTone, string> = {
  "total-prev": nocturneTokens.color.inkMuted,
  "total-current": nocturneTokens.color.blue,
  positive: nocturneTokens.color.green,
  negative: nocturneTokens.color.red,
  neutral: nocturneTokens.color.inkMuted,
};

type Props = {
  data: VolumeRateAttributionPayload | null;
  state: DataSectionState;
  onRetry: () => void;
};

/**
 * 损益变动归因桥逐项展示利息量价、非利息直接变动和未解释差额。
 * 柱间虚线标累计位，柱顶标带符号数值。
 * 任一总值/效应缺失时回退为独立柱形态（缺口保持断点，不补 0 参与累计定位）。
 */
export function AttributionWaterfallChart({ data, state, onRetry }: Props) {
  const option = useMemo<EChartsOption | null>(() => {
    if (!data?.has_previous_data) {
      return null;
    }
    const previous = yiOrNull(data.total_previous_pnl);
    const volume = yiOrNull(data.total_volume_effect);
    const rate = yiOrNull(data.total_rate_effect);
    // 交叉效应恒列示（含小值与缺失断点），不做阈值静默省略。
    const interaction = yiOrNull(data.total_interaction_effect);
    const includesDirectPnl = hasDirectPnlAttribution(data);
    const fairValue = yiOrNull(data.total_fair_value_effect);
    const capitalGain = yiOrNull(data.total_capital_gain_effect);
    const manualAdjustment = yiOrNull(data.total_manual_adjustment_effect);
    const unexplained = yiOrNull(data.total_recon_error);
    const current = yiOrNull(data.total_current_pnl);

    const axisLabelStyle = {
      fontSize: designTokens.fontSize[11],
      color: nocturneTokens.color.inkMuted,
      ...(includesDirectPnl ? { interval: 0, rotate: 20 } : {}),
    };
    const valueAxis = {
      type: "value" as const,
      axisLabel: {
        formatter: (v: number) => `${v.toFixed(1)}亿`,
        color: nocturneTokens.color.inkMuted,
      },
      splitLine: {
        lineStyle: { type: "solid" as const, color: nocturneTokens.color.lineSoft },
      },
    };
    const grid = {
      left: 48,
      right: designTokens.space[6],
      top: designTokens.space[7],
    };

    const bridge = buildAttributionBridge({
      previous,
      volume,
      rate,
      interaction,
      ...(includesDirectPnl ? { fairValue, capitalGain, manualAdjustment } : {}),
      unexplained,
      current,
    });

    if (bridge) {
      // 柱间累计连线：用 null 断点的 line 序列画不相连的水平虚线段
      //（lib/echarts 按需注册无 MarkLineComponent，markLine 不可用）。
      const connectorData: Array<[number, number] | null> = [];
      bridge.connectors.forEach((connector, index) => {
        if (index > 0) {
          connectorData.push(null);
        }
        connectorData.push([connector.from, connector.level]);
        connectorData.push([connector.to, connector.level]);
      });
      return {
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow" },
          formatter: (params: unknown) => {
            const entries = Array.isArray(params) ? params : [params];
            const visible =
              entries.find(
                (entry) =>
                  (entry as { seriesId?: string } | null)?.seriesId ===
                  "bridge-bars",
              ) ?? entries[0];
            const dataIndex =
              (visible as { dataIndex?: number } | null)?.dataIndex ?? -1;
            const bar = bridge.bars[dataIndex];
            if (!bar) {
              return "";
            }
            return `${bar.category}<br/>${signedYiLabel(bar.value)} 亿元`;
          },
        },
        grid,
        xAxis: {
          type: "category",
          data: bridge.bars.map((bar) => bar.category),
          axisLabel: axisLabelStyle,
        },
        yAxis: valueAxis,
        series: [
          {
            // 透明垫柱：把效应柱抬到累计位起画（标准归因桥）。
            id: "bridge-pad",
            type: "bar",
            stack: "bridge",
            silent: true,
            emphasis: { disabled: true },
            itemStyle: { color: "transparent" },
            data: bridge.bars.map((bar) => bar.base),
          },
          {
            id: "bridge-bars",
            type: "bar",
            stack: "bridge",
            data: bridge.bars.map((bar) => ({
              value: bar.size,
              itemStyle: {
                color: BRIDGE_TONE_COLOR[bar.tone],
              },
              label: {
                show: true,
                position: "top" as const,
                formatter: () => signedYiLabel(bar.value),
                color: nocturneTokens.color.ink,
                fontSize: designTokens.fontSize[11],
              },
            })),
          },
          {
            id: "bridge-connectors",
            type: "line",
            silent: true,
            symbol: "none",
            connectNulls: false,
            lineStyle: {
              type: "dashed" as const,
              width: 1,
              color: nocturneTokens.color.inkMuted,
            },
            emphasis: { disabled: true },
            data: connectorData,
          },
        ],
      };
    }

    // 回退形态：存在缺失值时无法累计定位，退回独立柱高（缺口断点、不补 0）。
    const fallbackBars: Array<{
      category: string;
      value: number | null;
      color: string;
    }> = [
      {
        category: "上期损益",
        value: previous,
        color: BRIDGE_TONE_COLOR["total-prev"],
      },
      {
        category: includesDirectPnl ? "利息规模效应" : "规模效应",
        value: volume,
        color:
          volume === null
            ? BRIDGE_TONE_COLOR.neutral
            : BRIDGE_TONE_COLOR[volume >= 0 ? "positive" : "negative"],
      },
      {
        category: includesDirectPnl ? "利息收益率效应" : "利率效应",
        value: rate,
        color:
          rate === null
            ? BRIDGE_TONE_COLOR.neutral
            : BRIDGE_TONE_COLOR[rate >= 0 ? "positive" : "negative"],
      },
      {
        category: "交叉效应",
        value: interaction,
        color: BRIDGE_TONE_COLOR.neutral,
      },
      ...(includesDirectPnl ? [
        { category: "公允价值变动", value: fairValue },
        { category: "投资收益变动", value: capitalGain },
        { category: "手工调整变动", value: manualAdjustment },
      ].map(({ category, value }) => ({
        category,
        value,
        color: value === null ? BRIDGE_TONE_COLOR.neutral :
          BRIDGE_TONE_COLOR[value >= 0 ? "positive" : "negative"],
      })) : []),
      {
        category: "未解释差额",
        value: unexplained,
        color: BRIDGE_TONE_COLOR.neutral,
      },
      {
        category: "当期损益",
        value: current,
        color: BRIDGE_TONE_COLOR["total-current"],
      },
    ];
    return {
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        valueFormatter: formatTooltipYi,
      },
      grid,
      xAxis: {
        type: "category",
        data: fallbackBars.map((bar) => bar.category),
        axisLabel: axisLabelStyle,
      },
      yAxis: valueAxis,
      series: [
        {
          type: "bar",
          data: fallbackBars.map((bar) => ({
            value: bar.value,
            itemStyle: { color: bar.color },
            label: {
              show: bar.value !== null,
              position: "top" as const,
              formatter: () =>
                bar.value === null ? "" : signedYiLabel(bar.value),
              color: nocturneTokens.color.ink,
              fontSize: designTokens.fontSize[11],
            },
          })),
        },
      ],
    };
  }, [data]);
  const includesDirectPnl = data !== null && hasDirectPnlAttribution(data);

  return (
    <PageDataSection title="损益变动归因分解" state={state} onRetry={onRetry}>
      {data ? (
        <>
          <p className="attribution-waterfall-chart__copy">
            {includesDirectPnl
              ? "利息量价以期末市值和当月利息收益率拆分，收益率为当月利息收入除以期末市值，非年化；公允价值损益、投资收益和手工调整按两期变动单列。未解释差额为损益变动扣除六项已知效应后的归因残差，缺失字段保留断点。"
              : "规模一阶效应近似为 Δ规模×上期收益率；利率一阶效应近似为上期规模×Δ收益率；交叉效应为规模与收益率同时变化的二阶联动项；未解释差额为损益变动扣除三项效应后的归因残差，缺失字段保留断点。"}
          </p>
          <ChartCard
            flat
            ariaLabel="损益变动归因分解"
            unit="亿元"
            height={280}
            option={option}
            legend="none"
            emptyMessage={
              !data.has_previous_data
                ? "无上期对比数据，无法展示归因瀑布图。"
                : "暂无数据"
            }
          >
            {data.has_previous_data && option ? (
              <div className="attribution-waterfall-chart__legend">
                <span>
                  当期损益 {formatYi(data.total_current_pnl.raw ?? undefined)}
                </span>
                <span>
                  {includesDirectPnl ? "利息规模效应" : "规模效应"}{" "}
                  {formatYi(data.total_volume_effect?.raw ?? undefined)}
                </span>
                <span>
                  {includesDirectPnl ? "利息收益率效应" : "利率效应"}{" "}
                  {formatYi(data.total_rate_effect?.raw ?? undefined)}
                </span>
                <span>
                  交叉效应{" "}
                  {formatYi(data.total_interaction_effect?.raw ?? undefined)}
                </span>
                {includesDirectPnl ? (
                  <>
                    <span>公允价值变动 {formatYi(data.total_fair_value_effect?.raw ?? undefined)}</span>
                    <span>投资收益变动 {formatYi(data.total_capital_gain_effect?.raw ?? undefined)}</span>
                    <span>手工调整变动 {formatYi(data.total_manual_adjustment_effect?.raw ?? undefined)}</span>
                  </>
                ) : null}
                <span>未解释差额 {formatYi(data.total_recon_error?.raw ?? undefined)}</span>
              </div>
            ) : null}
          </ChartCard>
        </>
      ) : null}
    </PageDataSection>
  );
}
