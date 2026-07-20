import { useState } from "react";
import { Button, Card, Tabs } from "antd";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";

import type { AssetStructurePayload, YieldDistributionPayload } from "../../../api/contracts";
import { ibChartTheme } from "../../../components/charts/chartTheme";
import styles from "../bondDashboard.module.css";
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
  const weightedYtm = yieldData ? nativeToNumber(yieldData.weighted_ytm) : null;
  const weightedLabel = weightedYtm === null ? "—" : `${(weightedYtm * 100).toFixed(2)}%`;

  const categories =
    mode === "yield"
      ? (yieldData?.items ?? []).map((i) => i.yield_bucket)
      : (tenorData?.items ?? []).map((i) => i.category);
  const valuesYi =
    mode === "yield"
      ? (yieldData?.items ?? []).map((i) => {
          const raw = nativeToNumber(i.total_market_value);
          return raw === null ? null : raw / 1e8;
        })
      : (tenorData?.items ?? []).map((i) => {
          const raw = nativeToNumber(i.total_market_value);
          return raw === null ? null : raw / 1e8;
        });

  const option: EChartsOption = ibChartTheme.createBarChartOption({
    grid: { left: 48, right: 24, top: 48, bottom: 32 },
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
    series: [
      {
        type: "bar",
        data: valuesYi,
        barMaxWidth: 48,
        itemStyle: { color: ibChartTheme.palette[0] },
      },
    ],
  });

  return (
    <Card
      loading={loading}
      title={mode === "yield" ? "收益率分布" : "剩余期限分布（规模）"}
      extra={<Button type="link">更多</Button>}
      classNames={{ body: styles.cardBodyTall }}
      rootClassName={styles.card}
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
        <div className={styles.yieldWeightedLabel}>加权收益率 {weightedLabel}</div>
      ) : (
        <div className={styles.yieldTenorHint}>按期限桶汇总市值（亿元）</div>
      )}
      <ReactECharts option={option} style={{ height: 260 }} notMerge lazyUpdate />
    </Card>
  );
}
