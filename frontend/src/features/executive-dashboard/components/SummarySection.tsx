import type { SummaryPayload } from "../../../api/contracts";
import { AsyncSection } from "./AsyncSection";

type SummarySectionProps = {
  data?: SummaryPayload;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  /** Override card title (e.g. 全局判断 on fixed-income dashboard). */
  sectionTitle?: string;
};

const toneMap = {
  positive: { bg: "#e8f6ee", fg: "#2f8f63" },
  neutral: { bg: "#edf1f5", fg: "#5c6b82" },
  warning: { bg: "#fff3dd", fg: "#cc7a1a" },
} as const;

export function SummarySection({
  data,
  isLoading,
  isError,
  onRetry,
  sectionTitle = "本周管理摘要",
}: SummarySectionProps) {
  return (
    <AsyncSection
      title={sectionTitle}
      isLoading={isLoading}
      isError={isError}
      isEmpty={!data || data.points.length === 0}
      onRetry={onRetry}
    >
      <p
        style={{
          color: "#425269",
          fontSize: 14,
          lineHeight: 1.8,
          marginTop: 0,
          marginBottom: 18,
        }}
      >
        {data?.narrative}
      </p>
      <div style={{ display: "grid", gap: 16 }}>
        {data?.points.map((item) => (
          <div
            key={item.id}
            style={{
              display: "grid",
              gap: 8,
              padding: 14,
              borderRadius: 16,
              background: "#ffffff",
              border: "1px solid #e8edf5",
            }}
          >
            <span
              style={{
                width: "fit-content",
                padding: "4px 10px",
                borderRadius: 999,
                background: toneMap[item.tone].bg,
                color: toneMap[item.tone].fg,
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              {item.label}
            </span>
            <span style={{ color: "#5c6b82", lineHeight: 1.7 }}>{item.text}</span>
          </div>
        ))}
      </div>
    </AsyncSection>
  );
}
