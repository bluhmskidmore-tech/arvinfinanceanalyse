import { ibTokens } from "../../../theme/designSystem";
import { buildSparkPath } from "../../workbench/dashboard/sparklinePath";

type MarketTerminalSparklineProps = {
  values: readonly number[];
  tone?: "up" | "down" | "flat";
  variant?: "kpi" | "ticker";
};

function sparkStroke(tone: MarketTerminalSparklineProps["tone"]) {
  if (tone === "up") return ibTokens.color.down;
  if (tone === "down") return ibTokens.color.up;
  return ibTokens.color.accent;
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
      <path d={areaPath} fill={stroke} fillOpacity="0.06" stroke="none" />
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
