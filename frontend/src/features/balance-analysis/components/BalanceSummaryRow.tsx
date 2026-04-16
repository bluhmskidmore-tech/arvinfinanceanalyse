import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { SummaryBlock } from "../../../components/SummaryBlock";
import { useBalanceAnalysisThreeColumnGridStyle } from "./balanceAnalysisLayout";

const summaryContent = [
  "资产以债券投资为主，占市场资产 93.3%；中长端配置偏稳，资产收益率 2.07%。",
  "负债以发行类债务为主，占市场负债 66.3%；其中国金存单占发行 81.8%。",
  "1年内净缺口 -373.0 亿，91天-1年缺口最大；需回购补量关注滚续节奏与成本。",
].join("\n");

const allocationChartOption: EChartsOption = {
  title: {
    text: "收益成本分配（静态口径）",
    left: 0,
    top: 0,
    textStyle: { fontSize: 14, fontWeight: 700, color: "#162033" },
  },
  grid: { left: 8, right: 8, top: 40, bottom: 28 },
  tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
  xAxis: { type: "value", axisLabel: { formatter: "{value}" } },
  yAxis: {
    type: "category",
    data: ["债券投资", "同业资产", "发行负债", "同业负债"],
    axisLabel: { width: 72, overflow: "truncate" },
  },
  series: [
    {
      type: "bar",
      data: [
        { value: 23.11, itemStyle: { color: "#2563eb" } },
        { value: 6.8, itemStyle: { color: "#3b82f6" } },
        { value: -9.4, itemStyle: { color: "#dc2626" } },
        { value: -4.2, itemStyle: { color: "#f97316" } },
      ],
      barWidth: 18,
    },
  ],
};

const riskRows: { dim: string; current: string; stress: string; scenario: string; level: "low" | "mid" | "high" }[] =
  [
    { dim: "期限错配", current: "偏高", stress: "中性", scenario: "压力测试", level: "high" },
    { dim: "流动性压力", current: "中性", stress: "中性", scenario: "压力测试", level: "mid" },
    { dim: "负债滚续", current: "偏高", stress: "关注", scenario: "压力测试", level: "high" },
    { dim: "对手方集中度", current: "中性", stress: "中性", scenario: "压力测试", level: "mid" },
    { dim: "异常资产", current: "低", stress: "低", scenario: "压力测试", level: "low" },
  ];

function cellBg(level: "low" | "mid" | "high") {
  if (level === "low") {
    return "#dcfce7";
  }
  if (level === "high") {
    return "#fee2e2";
  }
  return "#fef9c3";
}

export function BalanceSummaryRow() {
  const gridStyle = useBalanceAnalysisThreeColumnGridStyle();

  return (
    <div data-testid="balance-analysis-summary-row" style={gridStyle}>
      <div
        style={{
          borderRadius: 16,
          border: "1px solid #e4ebf5",
          background: "#ffffff",
          padding: 16,
        }}
      >
        <SummaryBlock
          title="本期资产负债摘要"
          content={summaryContent}
          tags={[
            { label: "资产特征", color: "blue" },
            { label: "负债特征", color: "geekblue" },
            { label: "缺口压力", color: "orange" },
          ]}
        />
      </div>
      <div
        style={{
          borderRadius: 16,
          border: "1px solid #e4ebf5",
          background: "#ffffff",
          padding: 12,
          minHeight: 260,
        }}
      >
        <ReactECharts option={allocationChartOption} style={{ height: 240 }} opts={{ renderer: "canvas" }} />
        <div style={{ textAlign: "right", fontSize: 13, fontWeight: 600, color: "#15803d" }}>净值: +16.31</div>
      </div>
      <div
        style={{
          borderRadius: 16,
          border: "1px solid #e4ebf5",
          background: "#ffffff",
          padding: 16,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 700, color: "#162033", marginBottom: 10 }}>风险全景</div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ color: "#5c6b82", textAlign: "left" }}>
              <th style={{ padding: "6px 4px", fontWeight: 600 }}>维度</th>
              <th style={{ padding: "6px 4px", fontWeight: 600 }}>当前</th>
              <th style={{ padding: "6px 4px", fontWeight: 600 }}>压力</th>
              <th style={{ padding: "6px 4px", fontWeight: 600 }}>情景</th>
            </tr>
          </thead>
          <tbody>
            {riskRows.map((row) => (
              <tr key={row.dim}>
                <td style={{ padding: "6px 4px", color: "#162033", fontWeight: 600 }}>{row.dim}</td>
                <td style={{ padding: 4, background: cellBg(row.level), borderRadius: 6 }}>{row.current}</td>
                <td style={{ padding: 4, background: cellBg("mid"), borderRadius: 6 }}>{row.stress}</td>
                <td style={{ padding: 4, background: cellBg("mid"), borderRadius: 6 }}>{row.scenario}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
