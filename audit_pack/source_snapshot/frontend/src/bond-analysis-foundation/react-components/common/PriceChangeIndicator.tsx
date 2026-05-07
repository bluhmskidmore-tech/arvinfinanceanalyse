export type PriceChangeDirection = "up" | "down" | "flat";

export interface PriceChangeIndicatorProps {
  value: string | number;
  direction?: PriceChangeDirection;
}

export function PriceChangeIndicator({
  value,
  direction = "flat",
}: PriceChangeIndicatorProps) {
  const color =
    direction === "up" ? "#0b7a4f" : direction === "down" ? "#b42318" : "#475467";
  const symbol = direction === "up" ? "▲" : direction === "down" ? "▼" : "■";

  return (
    <span style={{ color, display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span aria-hidden="true">{symbol}</span>
      <span>{value}</span>
    </span>
  );
}
