import type { PnlAttributionPayload } from "../../../api/contracts";
import { AsyncSection } from "./AsyncSection";

type PnlAttributionSectionProps = {
  data?: PnlAttributionPayload;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
};

const accentMap = {
  positive: "#2f8f63",
  neutral: "#6d7f99",
  negative: "#c1554b",
} as const;

export default function PnlAttributionSection({
  data,
  isLoading,
  isError,
  onRetry,
}: PnlAttributionSectionProps) {
  const maxAbsAmount = Math.max(
    ...(data?.segments.map((item) => Math.abs(item.amount)) ?? [1]),
  );

  return (
    <AsyncSection
      title="收益归因"
      extra={
        <span style={{ color: "#5c6b82" }}>
          {data?.total}
        </span>
      }
      isLoading={isLoading}
      isError={isError}
      isEmpty={!data || data.segments.length === 0}
      onRetry={onRetry}
    >
      <div style={{ display: "grid", gap: 14, width: "100%" }}>
        {data?.segments.map((segment) => (
          <div key={segment.id}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: 6,
                gap: 12,
              }}
            >
              <span>{segment.label}</span>
              <span
                style={{ color: accentMap[segment.tone], fontWeight: 600 }}
              >
                {segment.display_amount}
              </span>
            </div>
            <div
              style={{
                height: 10,
                borderRadius: 999,
                background: "#ecf1f6",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${Math.round((Math.abs(segment.amount) / maxAbsAmount) * 100)}%`,
                  borderRadius: 999,
                  background: accentMap[segment.tone],
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </AsyncSection>
  );
}
