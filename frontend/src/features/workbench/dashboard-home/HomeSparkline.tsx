import { useId } from "react";

import { buildSparkPath } from "../dashboard/sparklinePath";
import styles from "./dashboardHome.module.css";

type HomeSparklineProps = {
  values: readonly number[];
  width?: number;
  height?: number;
  stroke?: string;
  className?: string;
  area?: boolean;
};

export function HomeSparkline({
  values,
  width = 110,
  height = 30,
  stroke = "#0f58b7",
  className,
  area = false,
}: HomeSparklineProps) {
  const gradientId = useId();
  const linePath = buildSparkPath(values, width, height);
  const areaPath = area ? `${linePath} L ${width},${height} L 0,${height} Z` : "";

  return (
    <svg
      className={className ?? styles.dhMiniLine}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {area ? (
        <>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity="0.22" />
              <stop offset="100%" stopColor={stroke} stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={areaPath} fill={`url(#${gradientId})`} stroke="none" />
        </>
      ) : null}
      <path
        d={linePath}
        fill="none"
        stroke={stroke}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
