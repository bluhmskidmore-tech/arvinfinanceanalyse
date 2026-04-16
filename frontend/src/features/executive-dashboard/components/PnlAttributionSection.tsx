import { useMemo } from "react";
import ReactECharts from "../../../lib/echarts";
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

/** 环形图专用配色（与列表条 accentMap 独立） */
const chartToneColor = {
  positive: "#cf1322",
  negative: "#3f8600",
  neutral: "#8c8c8c",
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

  const chartOption = useMemo(() => {
    if (!data || data.segments.length === 0) {
      return null;
    }
    return {
      tooltip: {
        trigger: "item" as const,
        formatter: (params: {
          name: string;
          data?: { display_amount?: string };
        }) => {
          const display = params.data?.display_amount ?? "";
          return `${params.name}<br/>${display}`;
        },
      },
      title: {
        text: data.total,
        left: "center",
        top: "center",
        textAlign: "center" as const,
        textStyle: {
          fontSize: 14,
          fontWeight: 600,
          color: "#1f2937",
        },
      },
      series: [
        {
          type: "pie" as const,
          radius: ["48%", "78%"],
          avoidLabelOverlap: false,
          label: { show: false },
          labelLine: { show: false },
          data: data.segments.map((s) => ({
            name: s.label,
            value: Math.abs(s.amount),
            display_amount: s.display_amount,
            itemStyle: { color: chartToneColor[s.tone] },
          })),
        },
      ],
    };
  }, [data]);

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
      <div
        style={{
          display: "flex",
          gap: 20,
          alignItems: "flex-start",
          width: "100%",
        }}
      >
        {chartOption ? (
          <ReactECharts
            option={chartOption}
            style={{ width: 200, height: 200, flexShrink: 0 }}
          />
        ) : null}
        <div style={{ display: "grid", gap: 14, flex: 1, minWidth: 0 }}>
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
      </div>
    </AsyncSection>
  );
}
