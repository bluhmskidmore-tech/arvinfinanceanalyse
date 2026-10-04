import { Spin } from "antd";
import type { EChartsOption } from "echarts";
import type { EChartsInstance } from "echarts-for-react/lib/types";
import { useEffect, useRef } from "react";

import ReactECharts from "../../lib/echarts";
import { nocturneChartTheme } from "./chartTheme";

/*
 * 全部 BaseChart 消费方都在 Nocturne 深色 scope 下（DESIGN.md 结论 1/12）。空态与加载
 * 遮罩此前沿用 IB 浅色别名（白底 + 2px 圆角），series 一空就在深色面板里弹出白块；
 * 常规走查看不到，只有数据为空时才暴露（结论 18 点名的非常态界面）。
 */
const { emptyStateStyle, loadingMaskStyle } = nocturneChartTheme;

export type BaseChartProps = {
  option: EChartsOption;
  height?: number;
  loading?: boolean;
};

function isSeriesEmpty(option: EChartsOption): boolean {
  const s = option.series;
  if (s === undefined || s === null) return true;
  if (Array.isArray(s)) return s.length === 0;
  return false;
}

export function BaseChart({ option, height = 320, loading }: BaseChartProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<EChartsInstance | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const RO = globalThis.ResizeObserver;
    if (!RO) {
      return;
    }
    const ro = new RO(() => chartRef.current?.resize());
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const empty = !loading && isSeriesEmpty(option);

  return (
    <div ref={wrapRef} style={{ position: "relative", width: "100%", minHeight: height }}>
      {loading ? (
        <div style={loadingMaskStyle}>
          <Spin />
        </div>
      ) : null}
      {empty ? (
        <div
          data-testid="base-chart-empty"
          style={{
            ...emptyStateStyle,
            height,
          }}
        >
          暂无数据
        </div>
      ) : (
        <ReactECharts
          option={option}
          style={{ height, width: "100%" }}
          notMerge
          lazyUpdate
          onChartReady={(instance) => {
            chartRef.current = instance;
          }}
        />
      )}
    </div>
  );
}
