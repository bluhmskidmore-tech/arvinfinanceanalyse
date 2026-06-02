import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { CalendarList } from "../../../components/CalendarList";
import { useBalanceAnalysisThreeColumnGridStyle } from "./balanceAnalysisLayout";
import type { BalanceStageBottomModel } from "../pages/balanceAnalysisPageModel";

type BalanceBottomRowProps = {
  model: BalanceStageBottomModel;
};

function buildMaturityOption(model: BalanceStageBottomModel): EChartsOption {
  const categories = model.maturityCategories.length ? model.maturityCategories : ["无真实数据"];
  const assetSeries = model.maturityCategories.length ? model.assetSeries : [0];
  const liabilitySeries = model.maturityCategories.length ? model.liabilitySeries : [0];
  const gapSeries = model.maturityCategories.length ? model.gapSeries : [0];
  return {
    title: {
      text: "期限结构（资产/负债/净缺口）",
      left: 0,
      top: 0,
      textStyle: { fontSize: 14, fontWeight: 700, color: "#162033" },
    },
    legend: { top: 28, textStyle: { fontSize: 11 } },
    grid: { left: 48, right: 16, top: 56, bottom: 28 },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: categories, axisLabel: { rotate: 28, fontSize: 10 } },
    yAxis: { type: "value", name: "亿" },
    series: [
      {
        name: "资产",
        type: "bar",
        data: assetSeries,
        itemStyle: { color: "#2563eb" },
      },
      {
        name: "负债",
        type: "bar",
        data: liabilitySeries,
        itemStyle: { color: "#dc2626" },
      },
      {
        name: "净缺口",
        type: "bar",
        data: gapSeries.map((value) => ({
          value,
          itemStyle: { color: value < 0 ? "#fb923c" : "#16a34a" },
        })),
      },
    ],
  };
}

export function BalanceBottomRow({ model }: BalanceBottomRowProps) {
  const gridStyle = useBalanceAnalysisThreeColumnGridStyle();
  const maturityOption = buildMaturityOption(model);

  return (
    <div data-testid="balance-analysis-bottom-row" style={gridStyle}>
      <div
        style={{
          borderRadius: 16,
          border: "1px solid #e4ebf5",
          background: "#ffffff",
          padding: 12,
          minHeight: 320,
        }}
      >
        <ReactECharts option={maturityOption} style={{ height: 300 }} opts={{ renderer: "canvas" }} />
      </div>
      <div
        style={{
          borderRadius: 16,
          border: "1px solid #e4ebf5",
          background: "#ffffff",
          padding: 16,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 700, color: "#162033", marginBottom: 14 }}>风险指标</div>
        <div style={{ display: "grid", gap: 12 }}>
          {model.riskMetrics.map((m) => (
            <div
              key={m.label}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                gap: 12,
                paddingBottom: 10,
                borderBottom: "1px solid #f1f5f9",
              }}
            >
              <span style={{ fontSize: 13, color: "#5c6b82" }}>{m.label}</span>
              <span style={{ fontSize: 15, fontWeight: 700, color: "#162033", fontVariantNumeric: "tabular-nums" }}>
                {m.value}
              </span>
            </div>
          ))}
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
        <div style={{ fontSize: 14, fontWeight: 700, color: "#162033", marginBottom: 12 }}>关键日历（负债到期关注）</div>
        <CalendarList items={model.calendarItems} />
      </div>
    </div>
  );
}
