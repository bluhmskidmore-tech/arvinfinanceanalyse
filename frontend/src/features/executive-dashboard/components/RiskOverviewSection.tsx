import type { RiskOverviewPayload } from "../../../api/contracts";
import { AsyncSection } from "./AsyncSection";

type RiskOverviewSectionProps = {
  data?: RiskOverviewPayload;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
};

const statusMap = {
  stable: { bg: "#e8f6ee", fg: "#2f8f63", label: "稳定" },
  watch: { bg: "#fff3dd", fg: "#cc7a1a", label: "关注" },
  warning: { bg: "#fde8e6", fg: "#b74c45", label: "预警" },
} as const;

export function RiskOverviewSection({
  data,
  isLoading,
  isError,
  onRetry,
}: RiskOverviewSectionProps) {
  return (
    <AsyncSection
      title="风险全景"
      isLoading={isLoading}
      isError={isError}
      isEmpty={!data || data.signals.length === 0}
      onRetry={onRetry}
    >
      <div style={{ display: "grid", gap: 16 }}>
        {data?.signals.map((signal) => (
          <div key={signal.id} style={{ display: "grid", width: "100%", gap: 6 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 12,
              }}
            >
              <span style={{ fontWeight: 600 }}>{signal.label}</span>
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <span>{signal.value}</span>
                <span
                  style={{
                    padding: "4px 10px",
                    borderRadius: 999,
                    background: statusMap[signal.status].bg,
                    color: statusMap[signal.status].fg,
                    fontSize: 12,
                  }}
                >
                  {statusMap[signal.status].label}
                </span>
              </div>
            </div>
            <span style={{ color: "#5c6b82" }}>{signal.detail}</span>
          </div>
        ))}
      </div>
    </AsyncSection>
  );
}
