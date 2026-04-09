import type { OverviewPayload } from "../../../api/contracts";
import { AsyncSection } from "./AsyncSection";

type OverviewSectionProps = {
  data?: OverviewPayload;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
};

const toneColor = {
  positive: "#2f8f63",
  neutral: "#5c6b82",
  warning: "#cc7a1a",
  negative: "#b74c45",
} as const;

export function OverviewSection({
  data,
  isLoading,
  isError,
  onRetry,
}: OverviewSectionProps) {
  return (
    <AsyncSection
      title="经营总览"
      isLoading={isLoading}
      isError={isError}
      isEmpty={!data || data.metrics.length === 0}
      onRetry={onRetry}
      extra={
        <span
          style={{
            padding: "4px 10px",
            borderRadius: 999,
            background: "#dfe8ff",
            color: "#1f5eff",
            fontSize: 12,
          }}
        >
          {data?.metrics.length ?? 0} 项
        </span>
      }
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 16,
        }}
      >
        {data?.metrics.map((metric) => (
          <div
            key={metric.id}
            style={{
              display: "grid",
              gap: 8,
              padding: 18,
              borderRadius: 18,
              background: "#f7f9fc",
              border: "1px solid #e4ebf5",
            }}
          >
            <span style={{ color: "#8090a8", fontSize: 13 }}>
              {metric.label}
            </span>
            <div style={{ margin: 0, fontSize: 28, fontWeight: 600 }}>
              {metric.value}
            </div>
            <span
              style={{
                color: toneColor[metric.tone],
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              {metric.delta}
            </span>
            <p
              style={{
                margin: 0,
                color: "#5c6b82",
                fontSize: 13,
              }}
            >
              {metric.detail}
            </p>
          </div>
        ))}
      </div>
    </AsyncSection>
  );
}
