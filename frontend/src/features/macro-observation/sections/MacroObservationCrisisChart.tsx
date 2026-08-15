import { useLayoutEffect, useMemo, useRef, useState } from "react";

import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { nocturneTokens } from "../../../theme/designSystem";
import type { MacroObservationCrisisHistoryPoint } from "../model/macroObservationPageModel";

/**
 * 04 区危机分历史折线（crisis_score_cn.result.score_history，最多 430 点）。
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

const CONCRETE_COLOR_PATTERN = /^(#|rgb|hsl)/i;

/**
 * color-mix() 等函数式取值 zrender 解析不了；借一次性探针让浏览器把它
 * 算成 rgb()（探针挂 body，取值串在自定义属性计算后已不含 var()）。
 */
function resolveColorExpression(expression: string): string {
  if (CONCRETE_COLOR_PATTERN.test(expression)) {
    return expression;
  }
  if (typeof document === "undefined" || !document.body) {
    return "";
  }
  const probe = document.createElement("span");
  probe.style.display = "none";
  probe.style.color = expression;
  document.body.appendChild(probe);
  const resolved = getComputedStyle(probe).color.trim();
  probe.remove();
  return CONCRETE_COLOR_PATTERN.test(resolved) ? resolved : "";
}

function readScopeColor(host: Element, name: string): string {
  const raw = getComputedStyle(host).getPropertyValue(name).trim();
  return raw ? resolveColorExpression(raw) : "";
}

function resolveCrisisChartPalette(host: Element | null): CrisisChartPalette {
  if (!host || typeof getComputedStyle !== "function") {
    return CRISIS_CHART_STATIC_PALETTE;
  }
  const fallback = CRISIS_CHART_STATIC_PALETTE;
  const read = (name: string, fallbackValue: string) =>
    readScopeColor(host, name) || fallbackValue;
  const palette: CrisisChartPalette = {
    line: read("--dh-api-blue", fallback.line),
    axisLabel: read("--dh-api-ink-muted", fallback.axisLabel),
    splitLine: read("--dh-api-line-soft", fallback.splitLine),
    tooltipBg: read("--dh-api-panel-2", fallback.tooltipBg),
    tooltipBorder: read("--dh-api-line", fallback.tooltipBorder),
    tooltipInk: read("--dh-api-ink", fallback.tooltipInk),
  };
  const unchanged = (Object.keys(palette) as Array<keyof CrisisChartPalette>).every(
    (key) => palette[key] === fallback[key],
  );
  // 全部回退时返回同一实例，setState 可直接跳过更新。
  return unchanged ? fallback : palette;
}

function buildCrisisHistoryOption(
  history: MacroObservationCrisisHistoryPoint[],
  palette: CrisisChartPalette,
): EChartsOption {
  const lastIndex = history.length - 1;
  const lastPoint = history[lastIndex];
  return {
    // 右缘留出末点数值标注的空间。
    grid: { top: 8, right: 52, bottom: 24, left: 44 },
    tooltip: {
      trigger: "axis",
      backgroundColor: palette.tooltipBg,
      borderColor: palette.tooltipBorder,
      borderWidth: 1,
      textStyle: { color: palette.tooltipInk, fontSize: 11 },
      extraCssText: "border-radius: 8px; box-shadow: none;",
      formatter: (params: unknown) => {
        const first = Array.isArray(params)
          ? (params[0] as { dataIndex?: number } | undefined)
          : undefined;
        const point = history[first?.dataIndex ?? -1];
        // 精度沿用工具页 CrisisScoreEvidencePanel 的 score_history 呈现（4 位）。
        return point ? `${point.date}<br/>危机分 ${point.value.toFixed(4)}` : "";
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
}: {
  history: MacroObservationCrisisHistoryPoint[];
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [palette, setPalette] = useState(CRISIS_CHART_STATIC_PALETTE);

  useLayoutEffect(() => {
    setPalette(resolveCrisisChartPalette(hostRef.current));
  }, []);

  const option = useMemo(() => buildCrisisHistoryOption(history, palette), [history, palette]);

  return (
    <div ref={hostRef} className="macro-observation-crisis-chart-host">
      <ReactECharts
        option={option}
        className="macro-observation-crisis-chart-canvas"
        notMerge
        lazyUpdate
      />
    </div>
  );
}
