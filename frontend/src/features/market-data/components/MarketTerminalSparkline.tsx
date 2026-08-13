import { nocturneTokens } from "../../../theme/designSystem";
import { buildSparkPath } from "../../workbench/dashboard/sparklinePath";

type MarketTerminalSparklineProps = {
  values: readonly number[];
  tone?: "up" | "down" | "flat";
  variant?: "kpi" | "ticker";
};

// 与页面 ticker delta 的 data-tone 配色语义一致（绿涨红跌，DESIGN 2026-08-11 决策），中性走蓝紫。
function sparkStroke(tone: MarketTerminalSparklineProps["tone"]) {
  if (tone === "up") return nocturneTokens.color.green;
  if (tone === "down") return nocturneTokens.color.red;
  return nocturneTokens.color.blue;
}

export function MarketTerminalSparkline({
  values,
  tone = "flat",
  variant = "kpi",
}: MarketTerminalSparklineProps) {
  const width = variant === "ticker" ? 64 : 88;
  const height = variant === "ticker" ? 17 : 21;

  if (values.length < 2) {
    return null;
  }

  const linePath = buildSparkPath(values, width, height);

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
      <path
        d={linePath}
        fill="none"
        stroke={sparkStroke(tone)}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
