import { useId } from "react";

import { buildSparkPath } from "../../workbench/dashboard/sparklinePath";

type MarketTerminalSparklineProps = {
  values: readonly number[];
  tone?: "up" | "down" | "flat";
  variant?: "kpi" | "ticker";
};

function sparkStroke(tone: MarketTerminalSparklineProps["tone"]) {
  if (tone === "up") return "#ef4444";
  if (tone === "down") return "#2d8a5e";
  return "#1850a1";
}

export function MarketTerminalSparkline({
  values,
  tone = "flat",
  variant = "kpi",
}: MarketTerminalSparklineProps) {
  const gradientId = useId();
  const width = variant === "ticker" ? 64 : 88;
  const height = variant === "ticker" ? 22 : 28;

  if (values.length < 2) {
    return null;
  }

  const stroke = sparkStroke(tone);
  const linePath = buildSparkPath(values, width, height);
  const areaPath = `${linePath} L ${width},${height} L 0,${height} Z`;

  return (
    <svg
      className={
        variant === "ticker"
          ? "market-data-terminal-sparkline market-data-terminal-sparkline--ticker"
          : "market-data-terminal-sparkline market-data-terminal-sparkline--kpi"
      }
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
