import type { TimeSeriesPoint } from "../../data-structures/BondModel";
import { EmptyState } from "../common/EmptyState";

export interface PriceChartProps {
  title?: string;
  series: TimeSeriesPoint[];
  mode?: "price" | "yield";
}

export function PriceChart({
  title = "债券走势",
  series,
  mode = "price",
}: PriceChartProps) {
  if (series.length === 0) {
    return <EmptyState title="暂无历史序列" description="等待后端返回价格/收益率历史点位。" />;
  }

  const values = series.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  return (
    <section style={{ display: "grid", gap: 16 }}>
      <h3 style={{ margin: 0 }}>{title}</h3>
      <div style={{ display: "grid", gap: 8, gridTemplateColumns: `repeat(${series.length}, minmax(0, 1fr))` }}>
        {series.map((point) => (
          <div key={point.date} style={{ display: "grid", gap: 8 }}>
            <div
              style={{
                height: `${((point.value - min) / range) * 140 + 24}px`,
                borderRadius: 14,
                background:
                  mode === "price"
                    ? "linear-gradient(180deg, rgba(37, 99, 235, 0.85), rgba(37, 99, 235, 0.22))"
                    : "linear-gradient(180deg, rgba(194, 65, 12, 0.85), rgba(194, 65, 12, 0.22))",
              }}
            />
            <div style={{ fontSize: 12, color: "#475467" }}>{point.date}</div>
            <div>{point.value.toFixed(2)}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
