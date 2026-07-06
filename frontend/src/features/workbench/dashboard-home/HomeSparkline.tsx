import { useId } from "react";

import styles from "./dashboardHomeShell.module.css";

type HomeSparklineProps = {
  values: readonly number[];
  width?: number;
  height?: number;
  stroke?: string;
  className?: string;
  area?: boolean;
};

function sparkPoints(
  values: readonly (number | null | undefined)[],
  width: number,
  height: number,
): Array<{ x: number; y: number }> {
  const margin = 2.5;
  const nums = values.filter((value): value is number => (
    typeof value === "number" && !Number.isNaN(value)
  ));
  const innerW = Math.max(0, width - 2 * margin);
  const midY = height / 2;
  const x0 = margin;
  const x1 = Math.max(margin, width - margin);

  if (nums.length <= 1) {
    return [
      { x: x0, y: midY },
      { x: x1, y: midY },
    ];
  }

  const min = Math.min(...nums);
  const max = Math.max(...nums);
  if (min === max) {
    return [
      { x: x0, y: midY },
      { x: x1, y: midY },
    ];
  }

  const innerH = Math.max(0, height - 2 * margin);
  return nums.map((value, index) => {
    const t = nums.length === 1 ? 0 : index / (nums.length - 1);
    const x = margin + t * innerW;
    const normalizedY = (value - min) / (max - min);
    const y = margin + innerH * (1 - normalizedY);
    return { x, y };
  });
}

function buildSoftSparkPath(points: Array<{ x: number; y: number }>): string {
  const first = points[0];
  if (!first) {
    return "";
  }

  return points.slice(1).reduce((path, point, index) => {
    const previous = points[index] ?? first;
    const controlX = (previous.x + point.x) / 2;
    return `${path} Q ${controlX} ${previous.y} ${point.x} ${point.y}`;
  }, `M ${first.x} ${first.y}`);
}

export function HomeSparkline({
  values,
  width = 110,
  height = 30,
  stroke = "#0f58b7",
  className,
  area = false,
}: HomeSparklineProps) {
  const gradientId = useId();
  const points = sparkPoints(values, width, height);
  const linePath = buildSoftSparkPath(points);
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
              <stop offset="0%" stopColor={stroke} stopOpacity="0.08" />
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
        strokeWidth="1.05"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.76"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
