import { Button, Card } from "antd";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";

import type { MaturityStructurePayload } from "../../../api/contracts";
import { nativeToNumber } from "../utils/format";

export function MaturityStructureChart({
  data,
  loading,
}: {
  data: MaturityStructurePayload | undefined;
  loading: boolean;
}) {
  const items = data?.items ?? [];
  const categories = items.map((i) => i.maturity_bucket);
  const barYi = items.map((i) => nativeToNumber(i.total_market_value) / 1e8);
  const linePct = items.map((i) => nativeToNumber(i.percentage));

  const option: EChartsOption = {
    color: ["#1677ff", "#ff7a45"],
    tooltip: { trigger: "axis" },
    legend: { data: ["规模(亿)", "占比(%)"] },
    grid: { left: 48, right: 56, top: 40, bottom: 40 },
    xAxis: { type: "category", data: categories, axisLabel: { rotate: 25, fontSize: 11 } },
    yAxis: [
      { type: "value", name: "亿元", splitLine: { lineStyle: { type: "dashed" } } },
      { type: "value", name: "%", splitLine: { show: false } },
    ],
    series: [
      { name: "规模(亿)", type: "bar", data: barYi, yAxisIndex: 0, barMaxWidth: 40 },
      { name: "占比(%)", type: "line", smooth: true, data: linePct, yAxisIndex: 1 },
    ],
  };

  return (
    <Card
      data-testid="bond-dashboard-maturity-structure-chart"
      loading={loading}
      title="期限结构"
      extra={<Button type="link">更多</Button>}
      style={{ borderRadius: 8 }}
    >
      <ReactECharts option={option} style={{ height: 300 }} notMerge lazyUpdate />
    </Card>
  );
}
