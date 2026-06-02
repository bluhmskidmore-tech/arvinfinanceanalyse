import { Spin } from "antd";
import type { EChartsOption } from "echarts";
import type { EChartsInstance } from "echarts-for-react/lib/types";
import { useEffect, useRef } from "react";

import ReactECharts from "../../lib/echarts";
import { shellTokens } from "../../theme/tokens";

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
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(251, 252, 254, 0.72)",
            zIndex: 1,
          }}
        >
          <Spin />
        </div>
      ) : null}
      {empty ? (
        <div
          style={{
            height,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: shellTokens.colorTextMuted,
            fontSize: 13,
            border: `1px dashed ${shellTokens.colorBorderSoft}`,
            borderRadius: 12,
            background: shellTokens.colorBgSurface,
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
