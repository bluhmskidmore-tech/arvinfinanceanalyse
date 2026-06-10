import { useId } from "react";

import { buildSparkPath } from "../dashboard/sparklinePath";
import type { MarketChangeDirection } from "./marketHomeChangeTone";
import marketStyles from "./marketHome.module.css";

type MarketHomeKpiSparklineProps = {
  values: readonly number[];
  tone?: "ok" | "watch" | "error" | "muted";
  changeDirection?: MarketChangeDirection;
  variant?: "kpi" | "ticker";
  className?: string;
};

function sparkStroke(
  tone: MarketHomeKpiSparklineProps["tone"],
  changeDirection: MarketChangeDirection | undefined,
) {
  if (changeDirection === "up") return "#ef4444";
  if (changeDirection === "down") return "#2d8a5e";
  if (tone === "error") return "#ef4444";
  if (tone === "watch") return "#d97706";
  return "#1850a1";
}

export function MarketHomeKpiSparkline({
  values,
  tone = "ok",
  changeDirection,
  variant = "kpi",
  className,
}: MarketHomeKpiSparklineProps) {
  const gradientId = useId();
  const width = variant === "ticker" ? 64 : 88;
  const height = variant === "ticker" ? 22 : 28;

  if (values.length < 2) {
    return null;
  }

  const stroke = sparkStroke(tone, changeDirection);
  const linePath = buildSparkPath(values, width, height);
  const areaPath = `${linePath} L ${width},${height} L 0,${height} Z`;

  return (
    <svg
      className={`${variant === "ticker" ? marketStyles.macroTickerSparkline : marketStyles.marketKpiSparkline} ${className ?? ""}`.trim()}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.22" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${gradientId})`} stroke="none" />
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
