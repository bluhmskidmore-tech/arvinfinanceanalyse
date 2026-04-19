import { Typography } from "antd";
import type { EChartsOption } from "../../../lib/echarts";
import ReactECharts from "../../../lib/echarts";
import { SectionCard } from "../../../components/SectionCard";
import { BORDER, panelStyle } from "./bondAnalyticsCockpitTokens";

const { Paragraph } = Typography;

const WEEKS = Array.from({ length: 12 }, (_, i) => `W-${11 - i}`);

/** Mock 序列：净敞口(亿)、负债比(%)、对手方集中度(%) */
const NET_EXPOSURE_YI = WEEKS.map((_, i) => Number((218 + i * 1.85 + (i % 4) * 0.6).toFixed(2)));
const LIABILITY_RATIO = WEEKS.map((_, i) => Number((72.1 + Math.sin(i / 2.1) * 1.35).toFixed(2)));
const COUNTERPARTY_CONC = WEEKS.map((_, i) => Number((19.2 + Math.cos(i / 2.4) * 0.95).toFixed(2)));

const option: EChartsOption = {
  grid: { left: 56, right: 56, top: 40, bottom: 28 },
  tooltip: { trigger: "axis" },
  legend: { top: 0, textStyle: { fontSize: 11 } },
  xAxis: {
    type: "category",
    data: WEEKS,
    axisLabel: { fontSize: 10, color: "#5c6b82" },
  },
  yAxis: [
    {
      type: "value",
      name: "净敞口(亿)",
      axisLabel: { color: "#5c6b82", fontSize: 10 },
      splitLine: { lineStyle: { type: "dashed", opacity: 0.35 } },
    },
    {
      type: "value",
      name: "占比(%)",
      axisLabel: { color: "#5c6b82", fontSize: 10, formatter: "{value}%" },
    },
  ],
  series: [
    {
      name: "净敞口(亿)",
      type: "bar",
      yAxisIndex: 0,
      data: NET_EXPOSURE_YI,
      itemStyle: { color: "#1f5eff", borderRadius: [4, 4, 0, 0] },
      barMaxWidth: 22,
    },
    {
      name: "负债比(%)",
      type: "line",
      smooth: true,
      yAxisIndex: 1,
      data: LIABILITY_RATIO,
      itemStyle: { color: "#ff7a45" },
    },
    {
      name: "对手方集中度(%)",
      type: "line",
      smooth: true,
      yAxisIndex: 1,
      data: COUNTERPARTY_CONC,
      itemStyle: { color: "#2f8f63" },
    },
  ],
};

export function RiskTrendChart() {
  return (
    <SectionCard
      title="风险趋势（近12周）"
      style={{ ...panelStyle("#ffffff"), border: `1px solid ${BORDER}` }}
    >
      <ReactECharts option={option} style={{ height: 280 }} opts={{ renderer: "canvas" }} />
      <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0, fontSize: 12 }}>
        正式环境需接入周频风险快照；当前为演示用合成序列。
      </Paragraph>
    </SectionCard>
  );
}

export default RiskTrendChart;
