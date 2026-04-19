import { Button, Card, Tabs } from "antd";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";

import type { AssetStructurePayload } from "../../../api/contracts";
import { formatYi, nativeToNumber } from "../utils/format";

const PIE_COLORS = [
  "#1d39c4",
  "#13c2c2",
  "#fa8c16",
  "#69c0ff",
  "#52c41a",
  "#8c8c8c",
];

export type AssetGroupBy = "bond_type" | "rating" | "portfolio_name" | "tenor_bucket";

const TAB_ITEMS: { key: AssetGroupBy; label: string }[] = [
  { key: "bond_type", label: "按券种" },
  { key: "rating", label: "按信用等级" },
  { key: "portfolio_name", label: "按投资组合" },
  { key: "tenor_bucket", label: "按期限" },
];

export function AssetStructurePie({
  data,
  loading,
  groupBy,
  onGroupByChange,
}: {
  data: AssetStructurePayload | undefined;
  loading: boolean;
  groupBy: AssetGroupBy;
  onGroupByChange: (g: AssetGroupBy) => void;
}) {
  const items = data?.items ?? [];
  const totalYi = data ? formatYi(data.total_market_value) : "—";

  const option: EChartsOption = {
    color: PIE_COLORS,
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const x = p as { name: string; value: number; percent: number };
        return `${x.name}<br/>${x.percent.toFixed(2)}%<br/>${formatYi(x.value)} 亿`;
      },
    },
    legend: {
      orient: "vertical",
      right: "4%",
      top: "middle",
      textStyle: { fontSize: 11 },
    },
    series: [
      {
        type: "pie",
        radius: ["42%", "68%"],
        center: ["36%", "50%"],
        avoidLabelOverlap: true,
        label: { show: false },
        data: items.map((it) => ({
          name: it.category || "—",
          value: nativeToNumber(it.total_market_value),
        })),
      },
    ],
  };

  return (
    <Card
      data-testid="bond-dashboard-asset-structure-pie"
      loading={loading}
      title="债券资产结构"
      extra={<Button type="link">更多</Button>}
      styles={{ body: { minHeight: 320 } }}
      style={{ borderRadius: 8 }}
    >
      <Tabs
        size="small"
        activeKey={groupBy}
        onChange={(k) => onGroupByChange(k as AssetGroupBy)}
        items={TAB_ITEMS.map((t) => ({ key: t.key, label: t.label }))}
      />
      <div style={{ position: "relative", height: 280 }}>
        <ReactECharts option={option} style={{ height: 280 }} notMerge lazyUpdate />
        <div
          style={{
            position: "absolute",
            left: "28%",
            top: "50%",
            transform: "translate(-50%, -50%)",
            textAlign: "center",
            pointerEvents: "none",
          }}
        >
          <div style={{ fontSize: 12, color: "rgba(0,0,0,0.45)" }}>合计</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: "#1677ff" }}>{totalYi}</div>
          <div style={{ fontSize: 12, color: "rgba(0,0,0,0.45)" }}>亿元</div>
        </div>
      </div>
    </Card>
  );
}
