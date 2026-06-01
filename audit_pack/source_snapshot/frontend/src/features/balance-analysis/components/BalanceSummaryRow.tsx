import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { SummaryBlock } from "../../../components/SummaryBlock";
import { useBalanceAnalysisThreeColumnGridStyle } from "./balanceAnalysisLayout";
import type { BalanceStageSummaryModel } from "../pages/balanceAnalysisPageModel";

type BalanceSummaryRowProps = {
  model: BalanceStageSummaryModel;
};

function cellBg(level: "low" | "mid" | "high") {
  if (level === "low") {
    return "#dcfce7";
  }
  if (level === "high") {
    return "#fee2e2";
  }
  return "#fef9c3";
}

function buildAllocationChartOption(model: BalanceStageSummaryModel): EChartsOption {
  const items = model.allocationItems.length
    ? model.allocationItems
    : [{ label: "无真实数据", value: 0, color: "#94a3b8" }];
  return {
    title: {
      text: "收益成本分配（真实数据）",
      left: 0,
      top: 0,
      textStyle: { fontSize: 14, fontWeight: 700, color: "#162033" },
    },
    grid: { left: 8, right: 8, top: 40, bottom: 28 },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: { type: "value", axisLabel: { formatter: "{value}" } },
    yAxis: {
      type: "category",
      data: items.map((item) => item.label),
      axisLabel: { width: 72, overflow: "truncate" },
    },
    series: [
      {
        type: "bar",
        data: items.map((item) => ({
          value: item.value,
          itemStyle: { color: item.color },
        })),
        barWidth: 18,
      },
    ],
  };
}

export function BalanceSummaryRow({ model }: BalanceSummaryRowProps) {
  const gridStyle = useBalanceAnalysisThreeColumnGridStyle();
  const allocationChartOption = buildAllocationChartOption(model);

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
          content={model.content}
          tags={model.tags}
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
        <div style={{ textAlign: "right", fontSize: 13, fontWeight: 600, color: "#15803d" }}>
          净值: {model.allocationNetValue}
        </div>
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
            {model.riskRows.map((row) => (
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
