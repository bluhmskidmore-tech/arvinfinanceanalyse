import type { SummaryPayload } from "../../../api/contracts";
import { cardVariants, chipVariants } from "@heroui/styles";
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
  positive: "success",
  neutral: "default",
  warning: "warning",
} as const;
const summaryCardSlots = cardVariants({ variant: "default" });

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
            className={summaryCardSlots.base({
              className: "bg-background/40 border-default-100 backdrop-blur-md shadow-sm",
            })}
            data-slot="card"
          >
            <div className={summaryCardSlots.content({ className: "grid gap-2 p-3.5" })} data-slot="card-content">
              <div className="w-fit">
                <span
                  className={chipVariants({ size: "sm", variant: "soft", color: toneMap[item.tone] }).base()}
                  data-slot="chip"
                >
                  <span className={chipVariants().label()}>{item.label}</span>
                </span>
              </div>
              <span className="text-default-500 leading-relaxed">{item.text}</span>
            </div>
          </div>
        ))}
      </div>
    </AsyncSection>
  );
}
