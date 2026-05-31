import { useMemo, type CSSProperties } from "react";

import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { designTokens } from "../../../theme/designSystem";

/** 品牌主色描边，与 designTokens.color.primary[600] 同源 */
const SPARKLINE_STROKE = designTokens.color.primary[600];

export type EquityKpiCardProps = {
  label: string;
  value: string;
  deltaText?: string;
  deltaTone?: "up" | "down" | "flat";
  sparkline?: number[];
};

const tabularValueStyle: CSSProperties = {
  fontVariantNumeric: "tabular-nums",
  fontFamily: "var(--moss-font-mono)",
};

const deltaToneClass: Record<NonNullable<EquityKpiCardProps["deltaTone"]>, string> = {
  up: "text-success-600",
  down: "text-danger-600",
  flat: "text-neutral-600",
};

function buildSparklineOption(values: number[]): EChartsOption {
  return {
    animation: false,
    grid: { left: 0, right: 0, top: 2, bottom: 2 },
    xAxis: {
      type: "category",
      show: false,
      boundaryGap: false,
      data: values.map((_, index) => String(index)),
    },
    yAxis: { type: "value", show: false, scale: true },
    series: [
      {
        type: "line",
        data: values,
        smooth: true,
        symbol: "none",
        lineStyle: { color: SPARKLINE_STROKE, width: 1.5 },
      },
    ],
  };
}

export function EquityKpiCard({
  label,
  value,
  deltaText,
  deltaTone = "flat",
  sparkline,
}: EquityKpiCardProps) {
  const sparklineOption = useMemo(
    () => (sparkline && sparkline.length > 0 ? buildSparklineOption(sparkline) : null),
    [sparkline],
  );

  return (
    <article
      className="flex flex-col gap-2 rounded-md border border-neutral-200 bg-white p-3 shadow-sm transition-shadow duration-200 hover:-translate-y-px hover:shadow-md"
      data-equity-kpi-card
    >
      <header className="flex items-start justify-between gap-2">
        <span className="text-xs font-medium text-neutral-600">{label}</span>
        <div className="h-8 w-20 shrink-0" aria-hidden={sparklineOption ? undefined : true}>
          {sparklineOption ? (
            <ReactECharts option={sparklineOption} style={{ height: 32, width: 80 }} />
          ) : (
            <div className="mt-3 h-px w-full rounded-full bg-neutral-200" title="无序列，占位" />
          )}
        </div>
      </header>
      <p className="text-lg font-semibold leading-tight text-neutral-900" style={tabularValueStyle}>
        {value}
      </p>
      {deltaText ? (
        <p className={`text-xs leading-snug ${deltaToneClass[deltaTone]}`}>{deltaText}</p>
      ) : null}
    </article>
  );
}
