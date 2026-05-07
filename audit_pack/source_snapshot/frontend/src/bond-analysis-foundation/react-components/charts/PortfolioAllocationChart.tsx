import { EmptyState } from "../common/EmptyState";

export interface AllocationDatum {
  label: string;
  weight: number;
}

export interface PortfolioAllocationChartProps {
  title?: string;
  allocations: AllocationDatum[];
}

export function PortfolioAllocationChart({
  title = "组合配置",
  allocations,
}: PortfolioAllocationChartProps) {
  if (allocations.length === 0) {
    return <EmptyState title="暂无配置数据" description="等待组合持仓与权重同步。" />;
  }

  return (
    <section style={{ display: "grid", gap: 16 }}>
      <h3 style={{ margin: 0 }}>{title}</h3>
      <div style={{ display: "grid", gap: 10 }}>
        {allocations.map((item) => (
          <div key={item.label} style={{ display: "grid", gap: 6 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>{item.label}</span>
              <strong>{(item.weight * 100).toFixed(1)}%</strong>
            </div>
            <div style={{ height: 10, borderRadius: 999, background: "#e4e7ec", overflow: "hidden" }}>
              <div
                style={{
                  width: `${Math.max(item.weight * 100, 4)}%`,
                  height: "100%",
                  borderRadius: 999,
                  background:
                    "linear-gradient(90deg, rgba(15, 118, 110, 0.95), rgba(45, 212, 191, 0.85))",
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
