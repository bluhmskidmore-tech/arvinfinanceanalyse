import { useMemo } from "react";

import {
  ChartCard,
  type ChartCardState,
} from "../../../components/charts/ChartCard";
import { CHART_CARD_HEIGHTS } from "../../../components/charts/chartCardScale";
import { type EChartsOption } from "../../../lib/echarts";
import { nocturneTokens } from "../../../theme/designSystem";
import type { MacroObservationCrisisHistoryPoint } from "../model/macroObservationPageModel";

/**
 * 04 区危机分历史折线（crisis_score_cn.result.score_history，最多 430 点）。
 *
 * 数据可信度：早期历史可能只有部分分项可用（后端记 degraded），与全分项读数
 * 不等价。起始处的连续降级段以底色段标出并注明分项数，tooltip 逐点披露覆盖，
 * 避免降级历史被当作同一口径读取；覆盖字段缺失时不标段、不补数。
 *
 * 取色：ECharts option 是 JS 常量，CSS 变量翻不动；挂载后从图表容器读取
 * `--dh-api-*` 计算值构造调色板（workbench marketChartPalette 的
 * readScopeColor 同款模式）。jsdom / 取值失败时逐槽回退 nocturneTokens
 * 静态值——本页挂 Nocturne scope，禁止回退到钢蓝 dhApiTokens。
 * resize 由 echarts-for-react 自带的 size-sensor 监听，无需手写 observer。
 */

type CrisisChartPalette = {
  line: string;
  axisLabel: string;
  splitLine: string;
  tooltipBg: string;
  tooltipBorder: string;
  tooltipInk: string;
};

const CRISIS_CHART_STATIC_PALETTE: CrisisChartPalette = {
  line: nocturneTokens.color.blue,
  axisLabel: nocturneTokens.color.inkMuted,
  splitLine: nocturneTokens.color.lineSoft,
  tooltipBg: nocturneTokens.color.panel2,
  tooltipBorder: nocturneTokens.color.line,
  tooltipInk: nocturneTokens.color.ink,
};

/** 该点是否为「部分分项可用」的降级读数；覆盖字段缺失时一律不算降级。 */
function isDegradedPoint(point: MacroObservationCrisisHistoryPoint): boolean {
  const available = point.availableComponentCount;
  const total = point.componentCount;
  return available !== null && total !== null && available < total;
}

type CrisisDegradedRun = { startIndex: number; endIndex: number };

/**
 * 全部连续降级段。降级段不一定只在开头——历史中段也可能出现部分分项可用的
 * 读数，只标起始段会漏掉后面的降级点。逐段返回，段与段之间由完整读数分隔。
 */
function crisisDegradedRuns(history: MacroObservationCrisisHistoryPoint[]): CrisisDegradedRun[] {
  const runs: CrisisDegradedRun[] = [];
  let start = -1;
  for (let index = 0; index < history.length; index += 1) {
    if (isDegradedPoint(history[index]!)) {
      if (start === -1) {
        start = index;
      }
      continue;
    }
    if (start !== -1) {
      runs.push({ startIndex: start, endIndex: index - 1 });
      start = -1;
    }
  }
  if (start !== -1) {
    runs.push({ startIndex: start, endIndex: history.length - 1 });
  }
  return runs;
}

function buildCrisisHistoryOption(
  history: MacroObservationCrisisHistoryPoint[],
  palette: CrisisChartPalette,
): EChartsOption {
  const lastIndex = history.length - 1;
  const lastPoint = history[lastIndex];
  const degradedRuns = crisisDegradedRuns(history);
  return {
    // 右缘留出末点数值标注的空间。
    grid: { top: 8, right: 52, left: 44 },
    tooltip: {
      trigger: "axis",
      extraCssText: "border-radius: 8px; box-shadow: none;",
      formatter: (params: unknown) => {
        const first = Array.isArray(params)
          ? (params[0] as { dataIndex?: number } | undefined)
          : undefined;
        const point = history[first?.dataIndex ?? -1];
        if (!point) {
          return "";
        }
        // 精度沿用工具页 CrisisScoreEvidencePanel 的 score_history 呈现（4 位）。
        const coverage =
          point.availableComponentCount !== null && point.componentCount !== null
            ? `<br/>分项 ${point.availableComponentCount}/${point.componentCount}${
                isDegradedPoint(point) ? "（降级）" : ""
              }`
            : "";
        return `${point.date}<br/>危机分 ${point.value.toFixed(4)}${coverage}`;
      },
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: history.map((point) => point.date),
      // 430 点密集类目轴：interval 交给 auto 稀疏标签。
      axisLabel: { color: palette.axisLabel, fontSize: 11 },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: { color: palette.axisLabel, fontSize: 11 },
      splitLine: { lineStyle: { color: palette.splitLine } },
    },
    series: [
      {
        name: "危机分",
        type: "line",
        data: history.map((point) => point.value),
        showSymbol: false,
        lineStyle: { color: palette.line, width: 1.6 },
        itemStyle: { color: palette.line },
        areaStyle: { color: palette.line, opacity: 0.08 },
        // 0 参考线：危机分为 z-score 型读数，正负分界是解读锚点；
        // 后端未下发警戒阈值，暂不画阈值带（不虚构业务含义）。
        markLine: {
          silent: true,
          symbol: "none",
          label: { show: false },
          lineStyle: { color: palette.axisLabel, type: "dashed", width: 1 },
          data: [{ yAxis: 0 }],
        },
        // 降级观测段：部分分项可用的历史读数与全分项读数不等价，用底色段标出
        // （DESIGN §6 数据可信度不得混同）。段可能出现在任意位置，逐段标注；
        // 段宽随点数变化，窄段放不下图内文字，改由卡头 question 披露总点数。
        ...(degradedRuns.length
          ? {
              markArea: {
                silent: true,
                itemStyle: { color: palette.axisLabel, opacity: 0.14 },
                data: degradedRuns.map((run) => [
                  { xAxis: history[run.startIndex]!.date },
                  { xAxis: history[run.endIndex]!.date },
                ]),
              },
            }
          : {}),
        // 末点标注：终值圆点 + 数值 label（两位小数，全精度在 tooltip）。
        ...(lastPoint
          ? {
              markPoint: {
                silent: true,
                symbol: "circle",
                symbolSize: 6,
                itemStyle: { color: palette.line },
                label: {
                  show: true,
                  position: "right",
                  color: palette.tooltipInk,
                  fontSize: 11,
                  formatter: lastPoint.value.toFixed(2),
                },
                data: [{ name: "latest", coord: [lastIndex, lastPoint.value] }],
              },
            }
          : {}),
      },
    ],
  };
}

export default function MacroObservationCrisisChart({
  history,
  state,
  emptyMessage,
}: {
  history: MacroObservationCrisisHistoryPoint[];
  state?: ChartCardState;
  emptyMessage?: string;
}) {
  const option = useMemo(
    () => (history.length ? buildCrisisHistoryOption(history, CRISIS_CHART_STATIC_PALETTE) : null),
    [history],
  );
  const lastPoint = history[history.length - 1];
  // 降级观测段总点数在卡头披露：段宽随点数变化，窄段放不下图内文字。
  const degradedPointCount = useMemo(
    () => history.filter(isDegradedPoint).length,
    [history],
  );
  const question = history.length
    ? degradedPointCount
      ? `${history.length} 点 · 含 ${degradedPointCount} 点降级观测`
      : `${history.length} 点`
    : undefined;

  return (
    <ChartCard
      testId="macro-observation-crisis-chart"
      title="危机分历史"
      question={question}
      asOf={lastPoint?.date}
      height={CHART_CARD_HEIGHTS.default}
      legend="none"
      option={option}
      state={state}
      emptyMessage={emptyMessage}
    />
  );
}
