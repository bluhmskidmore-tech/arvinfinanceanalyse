import { EmptyState } from "../common/EmptyState";

export interface RiskMatrixBubble {
  id: string;
  label: string;
  xLabel: string;
  yLabel: string;
  size: number;
  tone?: "stable" | "warning" | "critical";
}

export interface RiskMatrixProps {
  items: RiskMatrixBubble[];
  onSelect?: (item: RiskMatrixBubble) => void;
}

function bubbleColor(tone: RiskMatrixBubble["tone"]) {
  if (tone === "critical") {
    return "rgba(180, 35, 24, 0.78)";
  }

  if (tone === "warning") {
    return "rgba(217, 119, 6, 0.74)";
  }

  return "rgba(15, 118, 110, 0.74)";
}

export function RiskMatrix({ items, onSelect }: RiskMatrixProps) {
  if (items.length === 0) {
    return <EmptyState title="暂无风险矩阵" description="风险暴露可通过 analytics 或 stress test 数据填充。" />;
  }

  return (
    <section style={{ display: "grid", gap: 16 }}>
      <h3 style={{ margin: 0 }}>风险矩阵</h3>
      <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelect?.(item)}
            style={{
              borderRadius: 20,
              border: "1px solid #d0d5dd",
              background: "#fff",
              padding: 18,
              display: "grid",
              gap: 10,
              justifyItems: "center",
            }}
          >
            <div
              style={{
                width: `${Math.max(item.size, 48)}px`,
                height: `${Math.max(item.size, 48)}px`,
                borderRadius: "50%",
                background: bubbleColor(item.tone),
              }}
            />
            <strong>{item.label}</strong>
            <div style={{ color: "#475467" }}>
              {item.xLabel} / {item.yLabel}
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
