import { useMemo } from "react";

import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { designTokens } from "../../../theme/designSystem";
import styles from "./EquityKpiCard.module.css";

/** 品牌主色描边，与 designTokens.color.primary[600] 同源 */
const SPARKLINE_STROKE = designTokens.color.primary[600];

export type EquityKpiCardProps = {
  label: string;
  value: string;
  deltaText?: string;
  deltaTone?: "up" | "down" | "flat";
  sparkline?: number[];
  testId?: string;
};

function deltaClass(tone: NonNullable<EquityKpiCardProps["deltaTone"]>): string {
  if (tone === "up") return styles.deltaUp ?? "";
  if (tone === "down") return styles.deltaDown ?? "";
  return styles.deltaFlat ?? "";
}

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
        areaStyle: { opacity: 0.12, color: SPARKLINE_STROKE },
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
  testId,
}: EquityKpiCardProps) {
  const sparklineOption = useMemo(
    () => (sparkline && sparkline.length > 0 ? buildSparklineOption(sparkline) : null),
    [sparkline],
  );

  return (
    <article className={styles.card} data-equity-kpi-card data-testid={testId}>
      <div className={styles.top}>
        <span>{label}</span>
      </div>
      <div className={styles.value}>{value}</div>
      {deltaText ? (
        <div className={`${styles.delta} ${deltaClass(deltaTone)}`}>{deltaText}</div>
      ) : (
        <div className={styles.delta} aria-hidden="true" />
      )}
      {sparklineOption ? (
        <ReactECharts
          className={styles.spark}
          option={sparklineOption}
          style={{ height: 28, width: "100%" }}
        />
      ) : (
        <div className={styles.sparkPlaceholder} aria-hidden="true" title="无序列，占位" />
      )}
    </article>
  );
}
