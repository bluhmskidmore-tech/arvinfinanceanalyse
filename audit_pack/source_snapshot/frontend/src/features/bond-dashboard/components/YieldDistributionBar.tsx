import { useState } from "react";
import { Button, Card, Tabs } from "antd";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";

import type { AssetStructurePayload, YieldDistributionPayload } from "../../../api/contracts";
import { nativeToNumber } from "../utils/format";

export function YieldDistributionBar({
  yieldData,
  tenorData,
  loadingYield,
  loadingTenor,
}: {
  yieldData: YieldDistributionPayload | undefined;
  tenorData: AssetStructurePayload | undefined;
  loadingYield: boolean;
  loadingTenor: boolean;
}) {
  const [mode, setMode] = useState<"yield" | "tenor">("yield");

  const loading = mode === "yield" ? loadingYield : loadingTenor;
  const weightedLabel = yieldData
    ? `${(nativeToNumber(yieldData.weighted_ytm) * 100).toFixed(2)}%`
    : "—";

  const categories =
    mode === "yield"
      ? (yieldData?.items ?? []).map((i) => i.yield_bucket)
      : (tenorData?.items ?? []).map((i) => i.category);
  const valuesYi =
    mode === "yield"
      ? (yieldData?.items ?? []).map((i) => nativeToNumber(i.total_market_value) / 1e8)
      : (tenorData?.items ?? []).map((i) => nativeToNumber(i.total_market_value) / 1e8);

  const option: EChartsOption = {
    color: ["#1677ff"],
    grid: { left: 48, right: 24, top: 48, bottom: 32 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
    },
    xAxis: {
      type: "category",
      data: categories,
      axisLabel: { rotate: mode === "tenor" ? 30 : 0, fontSize: 11 },
    },
    yAxis: {
      type: "value",
      name: "亿元",
      splitLine: { lineStyle: { type: "dashed" } },
    },
    series: [{ type: "bar", data: valuesYi, barMaxWidth: 48 }],
  };

  return (
    <Card
      loading={loading}
      title={mode === "yield" ? "收益率分布" : "剩余期限分布（规模）"}
      extra={<Button type="link">更多</Button>}
      styles={{ body: { minHeight: 320 } }}
      style={{ borderRadius: 8 }}
    >
      <Tabs
        size="small"
        activeKey={mode}
        onChange={(k) => setMode(k as "yield" | "tenor")}
        items={[
          { key: "yield", label: "收益率" },
          { key: "tenor", label: "期限" },
        ]}
      />
      {mode === "yield" ? (
        <div style={{ textAlign: "center", marginBottom: 8, fontSize: 13, color: "#1677ff" }}>
          加权收益率 {weightedLabel}
        </div>
      ) : (
        <div style={{ textAlign: "center", marginBottom: 8, fontSize: 13, color: "rgba(0,0,0,0.45)" }}>
          按期限桶汇总市值（亿元）
        </div>
      )}
      <ReactECharts option={option} style={{ height: 260 }} notMerge lazyUpdate />
    </Card>
  );
}
