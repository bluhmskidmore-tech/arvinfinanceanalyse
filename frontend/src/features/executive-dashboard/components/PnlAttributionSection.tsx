import { useMemo, type CSSProperties } from "react";

import ReactECharts from "../../../lib/echarts";
import { DataSection } from "../../../components/DataSection";
import { TONE_COLOR } from "../../../utils/tone";
import type { DashboardAdapterOutput } from "../adapters/executiveDashboardAdapter";
import {
  selectPnlMaxAbsAmount,
  selectPnlSegmentsForChart,
  selectPnlSegmentsForList,
  selectPnlTotal,
} from "../selectors/executiveDashboardSelectors";

type PnlAttributionSectionProps = {
  attribution: DashboardAdapterOutput["attribution"];
  onRetry: () => void;
};

const SECTION_EXTRA_STYLE = { color: "#5c6b82" } as const;

const CONTENT_ROW_STYLE = {
  display: "flex",
  gap: 20,
  alignItems: "flex-start",
  width: "100%",
} as const;

const CHART_CONTAINER_STYLE = { width: 240, height: 220, flexShrink: 0 } as const;

const LIST_COLUMN_STYLE = { display: "grid", gap: 14, flex: 1, minWidth: 0 } as const;

const ROW_HEADER_STYLE = {
  display: "flex",
  justifyContent: "space-between",
  marginBottom: 6,
  gap: 12,
} as const;

const BAR_TRACK_STYLE = {
  position: "relative" as const,
  height: 12,
  borderRadius: 999,
  background: "#ecf1f6",
  overflow: "hidden",
};

const BAR_CENTER_LINE_STYLE = {
  position: "absolute" as const,
  left: "50%",
  top: 0,
  bottom: 0,
  width: 1,
  background: "#c4cedc",
};

export default function PnlAttributionSection({
  attribution,
  onRetry,
}: PnlAttributionSectionProps) {
  const total = selectPnlTotal(attribution.vm);
  const chartSegments = selectPnlSegmentsForChart(attribution.vm);
  const listSegments = selectPnlSegmentsForList(attribution.vm);
  const maxAbs = selectPnlMaxAbsAmount(attribution.vm);

  const chartOption = useMemo(() => {
    if (chartSegments.length === 0) return null;
    // Labels in reverse so the first segment in data order renders at the top
    const reversed = [...chartSegments].reverse();
    return {
      tooltip: {
        trigger: "axis" as const,
        axisPointer: { type: "shadow" as const },
        formatter: (params: unknown) => {
          const entries = params as Array<{
            axisValue: string;
            data: { display?: string };
          }>;
          if (!entries || entries.length === 0) return "";
          const head = entries[0];
          return `${head?.axisValue ?? ""}<br/>${head?.data?.display ?? ""}`;
        },
      },
      grid: { left: 80, right: 16, top: 10, bottom: 10, containLabel: true },
      xAxis: {
        type: "value" as const,
        axisLine: { show: true, lineStyle: { color: "#c4cedc" } },
        splitLine: { lineStyle: { type: "dashed" as const, color: "#e4ebf5" } },
      },
      yAxis: {
        type: "category" as const,
        data: reversed.map((s) => s.label),
        axisTick: { show: false },
        axisLine: { show: false },
      },
      series: [
        {
          type: "bar" as const,
          data: reversed.map((s) => ({
            value: s.amount.raw ?? 0,
            display: s.amount.display,
            itemStyle: { color: TONE_COLOR[s.tone] },
          })),
          barWidth: 14,
          label: { show: false },
        },
      ],
    };
  }, [chartSegments]);

  const extra = total ? <span style={SECTION_EXTRA_STYLE}>{total.display}</span> : null;

  return (
    <DataSection
      title={attribution.vm?.title ?? "收益归因"}
      extra={extra}
      state={attribution.state}
      onRetry={onRetry}
    >
      <div style={CONTENT_ROW_STYLE}>
        {chartOption ? (
          <ReactECharts option={chartOption} style={CHART_CONTAINER_STYLE} />
        ) : null}
        <div style={LIST_COLUMN_STYLE}>
          {listSegments.map((segment) => (
            <div key={segment.id}>
              <div style={ROW_HEADER_STYLE}>
                <span>{segment.label}</span>
                <span style={{ color: TONE_COLOR[segment.tone], fontWeight: 600 }}>
                  {segment.amount.display}
                </span>
              </div>
              <div style={BAR_TRACK_STYLE}>
                <div style={BAR_CENTER_LINE_STYLE} />
                {renderBipolarFill({
                  raw: segment.amount.raw,
                  maxAbs,
                  color: TONE_COLOR[segment.tone],
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </DataSection>
  );
}

function renderBipolarFill(opts: {
  raw: number | null;
  maxAbs: number;
  color: string;
}) {
  const { raw, maxAbs, color } = opts;
  if (raw === null || maxAbs === 0) return null;

  const widthPct = Math.min(100, Math.round((Math.abs(raw) / maxAbs) * 50));
  // raw > 0: bar grows from center to the right
  // raw < 0: bar grows from center to the left
  const style: CSSProperties = {
    position: "absolute",
    top: 0,
    bottom: 0,
    background: color,
    borderRadius: 999,
  };
  if (raw >= 0) {
    style.left = "50%";
    style.width = `${widthPct}%`;
  } else {
    style.right = "50%";
    style.width = `${widthPct}%`;
  }
  return <div style={style} />;
}
