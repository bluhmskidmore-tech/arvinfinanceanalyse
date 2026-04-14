import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { CalendarList } from "../../../components/CalendarList";
import { useBalanceAnalysisThreeColumnGridStyle } from "./balanceAnalysisLayout";

const maturityCategories = [
  "7天内",
  "8-30天",
  "31-90天",
  "91天-1年",
  "1-3年",
  "3-5年",
  "5年以上",
  "无固定到期",
];

const maturityOption: EChartsOption = {
  title: {
    text: "期限结构（资产/负债/净缺口）",
    left: 0,
    top: 0,
    textStyle: { fontSize: 14, fontWeight: 700, color: "#162033" },
  },
  legend: { top: 28, textStyle: { fontSize: 11 } },
  grid: { left: 48, right: 16, top: 56, bottom: 28 },
  tooltip: { trigger: "axis" },
  xAxis: { type: "category", data: maturityCategories, axisLabel: { rotate: 28, fontSize: 10 } },
  yAxis: { type: "value", name: "亿" },
  series: [
    {
      name: "资产",
      type: "bar",
      data: [120, 210, 380, 920, 1100, 420, 310, 65],
      itemStyle: { color: "#2563eb" },
    },
    {
      name: "负债",
      type: "bar",
      data: [280, 410, 520, 680, 190, 85, 40, 12],
      itemStyle: { color: "#dc2626" },
    },
    {
      name: "净缺口",
      type: "bar",
      data: [
        { value: -160, itemStyle: { color: "#fb923c" } },
        { value: -200, itemStyle: { color: "#fb923c" } },
        { value: -140, itemStyle: { color: "#fb923c" } },
        { value: 240, itemStyle: { color: "#16a34a" } },
        { value: 910, itemStyle: { color: "#16a34a" } },
        { value: 335, itemStyle: { color: "#16a34a" } },
        { value: 270, itemStyle: { color: "#16a34a" } },
        { value: 53, itemStyle: { color: "#16a34a" } },
      ],
    },
  ],
};

const calendarMock = [
  { date: "04-02", event: "NCD 大额到期", amount: "180亿", level: "high" as const, note: "滚续询价" },
  { date: "04-05", event: "回购集中到期", amount: "95亿", level: "medium" as const, note: "关注利率" },
  { date: "04-08", event: "同业负债续作", amount: "42亿", level: "medium" as const, note: "额度复核" },
  { date: "04-12", event: "中长期债付息", amount: "6.2亿", level: "low" as const, note: "现金流" },
  { date: "04-18", event: "存单发行窗口", amount: "待定", level: "high" as const, note: "定价敏感" },
  { date: "04-22", event: "跨季流动性准备", amount: "—", level: "medium" as const, note: "预案" },
];

const riskMetrics: { label: string; value: string }[] = [
  { label: "资产/负债比", value: "1.94x" },
  { label: "短期负债占比", value: "72.6%" },
  { label: "发行负债集中度", value: "81.8%" },
  { label: "异常资产占比", value: "0.21%" },
  { label: "浮盈覆盖率", value: "18.4%" },
];

export function BalanceBottomRow() {
  const gridStyle = useBalanceAnalysisThreeColumnGridStyle();

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
          {riskMetrics.map((m) => (
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
        <CalendarList items={calendarMock} />
      </div>
    </div>
  );
}
