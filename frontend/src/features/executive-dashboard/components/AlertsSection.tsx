import type { AlertsPayload } from "../../../api/contracts";
import { AsyncSection } from "./AsyncSection";

type AlertsSectionProps = {
  data?: AlertsPayload;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  sectionTitle?: string;
};

const severityColor = {
  high: { bg: "#fde8e6", fg: "#b74c45" },
  medium: { bg: "#fff3dd", fg: "#cc7a1a" },
  low: { bg: "#e6f0ff", fg: "#1f5eff" },
} as const;

const severityLabel = {
  high: "高",
  medium: "中",
  low: "低",
} as const;

export function AlertsSection({
  data,
  isLoading,
  isError,
  onRetry,
  sectionTitle = "预警与事件",
}: AlertsSectionProps) {
  return (
    <AsyncSection
      title={sectionTitle}
      isLoading={isLoading}
      isError={isError}
      isEmpty={!data || data.items.length === 0}
      onRetry={onRetry}
    >
      <div style={{ display: "grid", gap: 16 }}>
        {data?.items.map((item) => (
          <div
            key={item.id}
            style={{
              display: "grid",
              gap: 8,
              width: "100%",
              padding: 14,
              borderRadius: 16,
              background: "#ffffff",
              border: "1px solid #e8edf5",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 12,
                alignItems: "center",
              }}
            >
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span
                  style={{
                    padding: "4px 10px",
                    borderRadius: 999,
                    background: severityColor[item.severity].bg,
                    color: severityColor[item.severity].fg,
                    fontSize: 12,
                    fontWeight: 600,
                  }}
                >
                  {severityLabel[item.severity]}
                </span>
                <span style={{ fontWeight: 600 }}>{item.title}</span>
              </div>
              <span style={{ color: "#8090a8", fontSize: 12 }}>{item.occurred_at}</span>
            </div>
            <span style={{ color: "#5c6b82", lineHeight: 1.7 }}>{item.detail}</span>
          </div>
        ))}
      </div>
    </AsyncSection>
  );
}
