import { Segmented } from "antd";
import { type EChartsOption } from "../../../lib/echarts";

import type { AssetStructurePayload } from "../../../api/contracts";
import { BaseChart } from "../../../components/charts/BaseChart";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import { EM_DASH } from "../../../pageModel";
import { nocturneTokens } from "../../../theme/designSystem";
import { formatYi, nativeToNumber } from "../utils/format";

export type AssetGroupBy = "bond_type" | "rating" | "portfolio_name" | "tenor_bucket";

const GROUP_OPTIONS: { key: AssetGroupBy; label: string }[] = [
  { key: "bond_type", label: "按券种" },
  { key: "rating", label: "按信用等级" },
  { key: "portfolio_name", label: "按投资组合" },
  { key: "tenor_bucket", label: "按期限" },
];

/* 分类系列色板：首色为 Nocturne accent 紫，绿/红不用于分类序列首选位。 */
const PIE_PALETTE = nocturneChartTheme.categoricalPalette;

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
  const totalYi = data ? formatYi(data.total_market_value) : EM_DASH;

  const option: EChartsOption = nocturneChartTheme.createBaseChartOption({
    legend: {
      orient: "vertical",
      right: "4%",
      top: "middle",
      textStyle: nocturneChartTheme.axisLabel,
    },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const x = p as {
          name: string;
          value: number | null;
          percent: number;
          data?: { bondCount?: number; backendPercentage?: number | null };
        };
        /* 占比优先消费后端 percentage（口径权威）；后端 null 时回退 ECharts 自算。 */
        const backendPct = x.data?.backendPercentage;
        const pctText = backendPct !== null && backendPct !== undefined
          ? (backendPct * 100).toFixed(2)
          : x.percent.toFixed(2);
        const countText = x.data?.bondCount !== undefined ? `<br/>${x.data.bondCount} 只` : "";
        return `${x.name}<br/>${pctText}%<br/>${formatYi(x.value)} 亿${countText}`;
      },
    },
    series: [
      {
        type: "pie",
        radius: ["42%", "68%"],
        center: ["36%", "50%"],
        avoidLabelOverlap: true,
        label: { show: false },
        /* 空/错态骨架环：ECharts 默认浅灰整环刺穿深色，收敛为 Nocturne 面板底+发丝线。 */
        emptyCircleStyle: {
          color: nocturneTokens.color.panel2,
          borderColor: nocturneTokens.color.lineSoft,
          borderWidth: 1,
        },
        data: items.map((it, index) => ({
          name: it.category || EM_DASH,
          value: nativeToNumber(it.total_market_value) ?? undefined,
          /* 自定义字段随 data item 透传给 tooltip formatter。 */
          bondCount: it.bond_count,
          backendPercentage: nativeToNumber(it.percentage),
          itemStyle: {
            color: PIE_PALETTE[index % PIE_PALETTE.length],
          },
        })),
      },
    ],
  });

  return (
    <div
      data-testid="bond-dashboard-asset-structure-pie"
      className="bond-dashboard-page__panel bond-dashboard-charts__panel"
    >
      <div className="bond-dashboard-charts__head">
        <h3 className="bond-dashboard-charts__head-title">债券资产结构</h3>
      </div>
      {loading ? (
        <p className="bond-dashboard-page__surface bond-dashboard-page__surface--loading">
          载入中…
        </p>
      ) : (
        <>
          <Segmented
            size="small"
            block
            value={groupBy}
            aria-label="bond-dashboard-asset-group"
            onChange={(value) => onGroupByChange(value as AssetGroupBy)}
            options={GROUP_OPTIONS.map((t) => ({ value: t.key, label: t.label }))}
            className="bond-dashboard-charts__segmented"
          />
          {/*
           * 仅真实空 payload 收敛为暂无数据；envelope 未到达（bundle 在途或
           * 分区缺失）时维持图表骨架，等高网格 settle 前不做高度跳变（Card
           * 时代同为空画布行为）。
           */}
          {data && items.length === 0 ? (
            <p className="bond-dashboard-page__surface bond-dashboard-page__surface--empty">
              暂无数据
            </p>
          ) : (
            <div className="bond-dashboard-charts__pie-wrap bond-dashboard-charts__fill">
              <BaseChart option={option} height={280} />
              <div className="bond-dashboard-charts__pie-overlay">
                <div className="bond-dashboard-charts__pie-overlay-label">合计</div>
                <div className="bond-dashboard-charts__pie-overlay-value">{totalYi}</div>
                <div className="bond-dashboard-charts__pie-overlay-label">亿元</div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
