import type { TimeSeriesPoint } from "../../data-structures/BondModel";
import { EmptyState } from "../common/EmptyState";

export interface PerformanceSeries {
  name: string;
  points: TimeSeriesPoint[];
}

export interface HistoricalPerformanceProps {
  series: PerformanceSeries[];
}

export function HistoricalPerformance({ series }: HistoricalPerformanceProps) {
  if (series.length === 0) {
    return <EmptyState title="暂无历史表现" description="请先选择组合、基准或对比债券。" />;
  }

  return (
    <section style={{ display: "grid", gap: 16 }}>
      <h3 style={{ margin: 0 }}>历史表现对比</h3>
      {series.map((item) => (
        <div
          key={item.name}
          style={{ borderRadius: 18, border: "1px solid #d0d5dd", background: "#fff", padding: 16 }}
        >
          <strong>{item.name}</strong>
          <div style={{ display: "grid", gap: 8, gridTemplateColumns: `repeat(${item.points.length}, minmax(0, 1fr))`, marginTop: 12 }}>
            {item.points.map((point) => (
              <div key={`${item.name}-${point.date}`} style={{ textAlign: "center" }}>
                <div style={{ color: "#475467", fontSize: 12 }}>{point.date}</div>
                <div>{point.value.toFixed(2)}</div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
