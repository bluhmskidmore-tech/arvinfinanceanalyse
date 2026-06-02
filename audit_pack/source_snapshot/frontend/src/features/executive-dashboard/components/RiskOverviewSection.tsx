import type { RiskOverviewPayload } from "../../../api/contracts";
import { designTokens } from "../../../theme/designSystem";
import { AsyncSection } from "./AsyncSection";

type RiskOverviewSectionProps = {
  data?: RiskOverviewPayload;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
};

const statusMap = {
  stable: { bg: designTokens.color.success[50], fg: designTokens.color.success[600], label: "稳定" },
  watch: { bg: designTokens.color.warning[50], fg: designTokens.color.warning[700], label: "关注" },
  warning: { bg: designTokens.color.danger[50], fg: designTokens.color.danger[600], label: "预警" },
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
                <span>{signal.value.display}</span>
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
