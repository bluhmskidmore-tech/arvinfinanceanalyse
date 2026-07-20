import { Button, Card, Segmented } from "antd";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";

import type { AssetStructurePayload } from "../../../api/contracts";
import { ibChartTheme } from "../../../components/charts/chartTheme";
import styles from "../bondDashboard.module.css";
import { formatYi, nativeToNumber } from "../utils/format";

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

  const option: EChartsOption = ibChartTheme.createBaseChartOption({
    legend: {
      orient: "vertical",
      right: "4%",
      top: "middle",
      textStyle: ibChartTheme.axisLabel,
    },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const x = p as { name: string; value: number | null; percent: number };
        return `${x.name}<br/>${x.percent.toFixed(2)}%<br/>${formatYi(x.value)} 亿`;
      },
    },
    series: [
      {
        type: "pie",
        radius: ["42%", "68%"],
        center: ["36%", "50%"],
        avoidLabelOverlap: true,
        label: { show: false },
        data: items.map((it, index) => ({
          name: it.category || "—",
          value: nativeToNumber(it.total_market_value) ?? undefined,
          itemStyle: {
            color: ibChartTheme.categoricalPalette[index % ibChartTheme.categoricalPalette.length],
          },
        })),
      },
    ],
  });

  return (
    <Card
      data-testid="bond-dashboard-asset-structure-pie"
      loading={loading}
      title="债券资产结构"
      extra={<Button type="link">更多</Button>}
      classNames={{ body: styles.cardBodyTall }}
      rootClassName={styles.card}
    >
      <Segmented
        size="small"
        block
        value={groupBy}
        aria-label="bond-dashboard-asset-group"
        onChange={(value) => onGroupByChange(value as AssetGroupBy)}
        options={TAB_ITEMS.map((t) => ({ value: t.key, label: t.label }))}
        className={styles.segmented}
      />
      <div className={styles.pieChartWrap}>
        <ReactECharts option={option} style={{ height: 280 }} notMerge lazyUpdate />
        <div className={styles.pieOverlay}>
          <div className={styles.pieOverlayLabel}>合计</div>
          <div className={styles.pieOverlayValue}>{totalYi}</div>
          <div className={styles.pieOverlayLabel}>亿元</div>
        </div>
      </div>
    </Card>
  );
}
