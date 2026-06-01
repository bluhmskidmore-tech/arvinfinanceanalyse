import { PriceChangeIndicator, type PriceChangeDirection } from "../common/PriceChangeIndicator";

export interface MetricTrend {
  direction: PriceChangeDirection;
  value: string;
}

export interface MetricCardProps {
  label: string;
  value: string;
  helperText?: string;
  trend?: MetricTrend;
}

export function MetricCard({ label, value, helperText, trend }: MetricCardProps) {
  return (
    <article
      style={{
        borderRadius: 20,
        border: "1px solid rgba(148, 163, 184, 0.24)",
        padding: 18,
        background: "rgba(255, 255, 255, 0.86)",
        display: "grid",
        gap: 8,
      }}
    >
      <span style={{ fontSize: 12, color: "#475467", textTransform: "uppercase" }}>{label}</span>
      <strong style={{ fontSize: 28 }}>{value}</strong>
      {helperText ? <span style={{ color: "#475467" }}>{helperText}</span> : null}
      {trend ? <PriceChangeIndicator direction={trend.direction} value={trend.value} /> : null}
    </article>
  );
}
