import { Segmented } from "antd";
import { type EChartsOption } from "../../../lib/echarts";

import type { AssetStructurePayload } from "../../../api/contracts";
import { ChartCard } from "../../../components/charts/ChartCard";
import { CHART_CARD_HEIGHTS } from "../../../components/charts/chartCardScale";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import { EM_DASH } from "../../../pageModel";
import { nocturneTokens } from "../../../theme/designSystem";
import type { BondSectionDataState } from "../sectionStatus";
import { computeFallbackPercentages, formatYi, nativeToNumber } from "../utils/format";

export type AssetGroupBy = "bond_type" | "rating" | "portfolio_name" | "tenor_bucket";

const GROUP_OPTIONS: { key: AssetGroupBy; label: string }[] = [
  { key: "bond_type", label: "按券种" },
  { key: "rating", label: "按信用等级" },
  { key: "portfolio_name", label: "按投资组合" },
  { key: "tenor_bucket", label: "按期限" },
];

/* 分类系列色板：首色为 Nocturne accent 紫，绿/红不用于分类序列首选位。 */
const PIE_PALETTE = nocturneChartTheme.categoricalPalette;

/** 2026-09-02 迁入 ChartCard：高度取阶梯 hero 档，载入骨架与画布同高由铬件保证。 */
const CHART_HEIGHT = CHART_CARD_HEIGHTS.hero;

export function AssetStructurePie({
  data,
  state,
  groupBy,
  onGroupByChange,
}: {
  data: AssetStructurePayload | undefined;
  state: BondSectionDataState;
  groupBy: AssetGroupBy;
  onGroupByChange: (g: AssetGroupBy) => void;
}) {
  const items = data?.items ?? [];
  const totalYi = data ? formatYi(data.total_market_value) : EM_DASH;
  /* 仅供后端百分比缺失的降级路径消费：让各类别份额恰好合计 100.00%，避免独立截断漂移。 */
  const fallbackPercentages = computeFallbackPercentages(items);

  /* 图例位置 / tooltip 底色由 ChartCard 铬件统一（图例左下，多分类预留两行），环心留给中心读数叠层。 */
  const option: EChartsOption = nocturneChartTheme.createBaseChartOption({
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const x = p as {
          name: string;
          value: number | null;
          percent: number;
          data?: {
            bondCount?: number;
            backendPercentage?: number | null;
            fallbackPercentage?: number | null;
          };
        };
        /* 占比优先消费后端 percentage（口径权威）；后端 null 时回退到已补差的份额，
         * 保证降级路径下各分类合计恰为 100.00%（不使用未补差的 ECharts 自算 x.percent）。 */
        const backendPct = x.data?.backendPercentage;
        const fallbackPct = x.data?.fallbackPercentage;
        const pctText = backendPct !== null && backendPct !== undefined
          ? (backendPct * 100).toFixed(2)
          : (fallbackPct ?? x.percent).toFixed(2);
        const content = document.createElement("div");
        content.append(x.name, document.createElement("br"), `${pctText}%`, document.createElement("br"), `${formatYi(x.value)} 亿`);
        if (x.data?.bondCount !== undefined) {
          content.append(document.createElement("br"), `${x.data.bondCount} 只`);
        }
        return content;
      },
    },
    series: [
      {
        type: "pie",
        radius: ["42%", "68%"],
        /* 图例移到左下后环居中；overlay 锚点同步为 50%（见 BondDashboardChartSections.css）。 */
        center: ["50%", "46%"],
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
          fallbackPercentage: fallbackPercentages[index],
          itemStyle: {
            color: PIE_PALETTE[index % PIE_PALETTE.length],
          },
        })),
      },
    ],
  });

  /*
   * 分组控件在真空态仍要可用（用户得能切到有数据的分组），所以它放在标题行 actions；
   * 载入与失败态下与重构前一致地不渲染。真空时收缩为空态而不是画空环（DESIGN.md §12 第 13 条）。
   */
  return (
    <ChartCard
      testId="bond-dashboard-asset-structure-pie"
      title="债券资产结构"
      height={CHART_HEIGHT}
      legendRows={2}
      option={items.length === 0 ? null : option}
      state={state.status === "ready" ? undefined : state.status}
      errorMessage={state.message ?? undefined}
      actions={
        state.status === "ready" ? (
          <Segmented
            size="small"
            value={groupBy}
            aria-label="bond-dashboard-asset-group"
            onChange={(value) => onGroupByChange(value as AssetGroupBy)}
            options={GROUP_OPTIONS.map((t) => ({ value: t.key, label: t.label }))}
            className="bond-dashboard-charts__segmented"
          />
        ) : undefined
      }
      canvasOverlay={
        <div className="bond-dashboard-charts__pie-overlay">
          <div className="bond-dashboard-charts__pie-overlay-label">合计</div>
          <div className="bond-dashboard-charts__pie-overlay-value">{totalYi}</div>
          <div className="bond-dashboard-charts__pie-overlay-label">亿元</div>
        </div>
      }
    />
  );
}
