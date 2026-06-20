import {
  AlertOutlined,
  AppstoreOutlined,
  CheckCircleOutlined,
  DatabaseOutlined,
  SafetyCertificateOutlined,
  StockOutlined,
} from "@ant-design/icons";
import { useMemo, type CSSProperties, type ReactNode } from "react";

import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { designTokens } from "../../../theme/designSystem";
import styles from "./EquityKpiCard.module.css";

/** 品牌主色描边，与 designTokens.color.primary[600] 同源 */
const SPARKLINE_STROKE = designTokens.color.primary[600];

export type EquityKpiCardProps = {
  kpiKey?: string;
  label: string;
  value: string;
  deltaText?: string;
  deltaTone?: "up" | "down" | "flat";
  sparkline?: number[];
  gaugeValue?: number;
  testId?: string;
};

const kpiIcons: Record<string, ReactNode> = {
  "market-state": <StockOutlined />,
  "review-queue": <CheckCircleOutlined />,
  "sector-strength": <AppstoreOutlined />,
  "risk-observation": <AlertOutlined />,
  "closed-loop": <SafetyCertificateOutlined />,
  "data-boundary": <DatabaseOutlined />,
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
  kpiKey,
  label,
  value,
  deltaText,
  deltaTone = "flat",
  sparkline,
  gaugeValue,
  testId,
}: EquityKpiCardProps) {
  const sparklineOption = useMemo(
    () => (sparkline && sparkline.length > 0 ? buildSparklineOption(sparkline) : null),
    [sparkline],
  );
  const normalizedGauge =
    gaugeValue == null || !Number.isFinite(gaugeValue)
      ? null
      : Math.min(1, Math.max(0, gaugeValue));
  const gaugeStyle =
    normalizedGauge == null
      ? undefined
      : ({ "--equity-kpi-gauge": `${Math.max(4, normalizedGauge * 100)}%` } as CSSProperties);

  return (
    <article className={styles.card} data-equity-kpi-card data-testid={testId}>
      <div className={styles.top}>
        {kpiKey ? (
          <span className={styles.icon} aria-hidden="true">
            {kpiIcons[kpiKey] ?? <StockOutlined />}
          </span>
        ) : null}
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
          style={{ height: 18, width: "100%" }}
        />
      ) : normalizedGauge != null ? (
        <div className={styles.gaugeTrack} aria-hidden="true" style={gaugeStyle}>
          <span />
        </div>
      ) : (
        <div className={styles.metricSlot} aria-hidden="true" />
      )}
    </article>
  );
}
