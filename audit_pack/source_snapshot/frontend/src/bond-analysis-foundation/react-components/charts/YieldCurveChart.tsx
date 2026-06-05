import type { YieldCurve } from "../../data-structures/MarketModel";
import { EmptyState } from "../common/EmptyState";

export interface YieldCurveChartProps {
  curve?: YieldCurve;
  onSelectTenor?: (tenor: string) => void;
}

export function YieldCurveChart({ curve, onSelectTenor }: YieldCurveChartProps) {
  if (!curve || curve.points.length === 0) {
    return <EmptyState title="暂无收益率曲线" description="等待行情服务推送可用曲线点位。" />;
  }

  const maxYield = Math.max(...curve.points.map((point) => point.yieldValue), 1);

  return (
    <section style={{ display: "grid", gap: 16 }}>
      <div>
        <h3 style={{ margin: 0 }}>{curve.curveName}</h3>
        <p style={{ margin: "6px 0 0", color: "#475467" }}>数据日期 {curve.asOfDate}</p>
      </div>
      <div
        style={{
          display: "grid",
          gap: 12,
          gridTemplateColumns: `repeat(${curve.points.length}, minmax(0, 1fr))`,
          alignItems: "end",
          minHeight: 220,
        }}
      >
        {curve.points.map((point) => (
          <button
            key={point.tenor}
            type="button"
            onClick={() => onSelectTenor?.(point.tenor)}
            style={{
              display: "grid",
              gap: 8,
              border: "none",
              background: "transparent",
              padding: 0,
              alignItems: "end",
            }}
          >
            <div
              style={{
                height: `${(point.yieldValue / maxYield) * 160}px`,
                borderRadius: 16,
                background:
                  "linear-gradient(180deg, rgba(14, 116, 144, 0.9), rgba(14, 165, 233, 0.4))",
              }}
            />
            <div style={{ textAlign: "center" }}>
              <strong>{point.tenor}</strong>
              <div style={{ color: "#475467" }}>{point.yieldValue.toFixed(2)}%</div>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
