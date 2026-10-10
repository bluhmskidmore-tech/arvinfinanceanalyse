import { type EChartsOption } from "../../../lib/echarts";

import type { MaturityStructurePayload } from "../../../api/contracts";
import { ChartCard } from "../../../components/charts/ChartCard";
import { CHART_CARD_HEIGHTS } from "../../../components/charts/chartCardScale";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import { EM_DASH } from "../../../pageModel";
import type { BondSectionDataState } from "../sectionStatus";
import { exactDecimalOrNull, formatRatioPercent, formatYi, nativeToNumber } from "../utils/format";

/** 2026-09-02 迁入 ChartCard：高度就近对齐三档阶梯（300 → hero 280），载入骨架与画布同高由铬件保证。 */
const CHART_HEIGHT = CHART_CARD_HEIGHTS.hero;

export function MaturityStructureChart({
  data,
  state,
}: {
  data: MaturityStructurePayload | undefined;
  state: BondSectionDataState;
}) {
  const items = data?.items ?? [];
  const categories = items.map((i) => i.maturity_bucket);
  const barYi = items.map((i) => {
    const exact = exactDecimalOrNull(i.total_market_value);
    if (exact !== null) return exact.dividedBy("1e8").toNumber();
    const raw = nativeToNumber(i.total_market_value);
    return raw === null ? null : raw / 1e8;
  });
  const linePct = items.map((i) => {
    const exact = exactDecimalOrNull(i.percentage);
    if (exact !== null) return exact.times(100).toNumber();
    const raw = nativeToNumber(i.percentage);
    return raw === null ? null : raw * 100;
  });
  /* 后端 items 带 bond_count、顶层带 total_market_value（此前均未消费）。 */
  const bondCounts = items.map((i) => i.bond_count);
  const barValueTexts = items.map((i) => formatYi(i.total_market_value));
  const lineValueTexts = items.map((i) => formatRatioPercent(i.percentage));
  const totalText = data ? formatYi(data.total_market_value) : EM_DASH;

  /*
   * 测试契约：series[0] 柱（规模）、series[1] 折线（占比，百分点数组）顺序
   * 不可换；占比折线是分类序列，用琥珀而非涨跌绿/红。
   */
  /* 图例位置 / tooltip 底色 / 网格边距由 ChartCard 铬件统一覆盖，这里只保留数据与轴。 */
  const option: EChartsOption = nocturneChartTheme.createBarChartOption({
    legend: { data: ["规模(亿)", "占比(%)"] },
    grid: { left: 48, right: 56, top: 24 },
    tooltip: {
      /* 只覆盖 formatter，深色底/边/字由主题基座深合并保留。 */
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : [params];
        const rows = list as Array<{
          seriesName?: string;
          name?: string;
          dataIndex?: number;
          value?: number | null;
        }>;
        const first = rows[0];
        if (!first) return "";
        const lines = rows.map((row) => {
          const isPct = row.seriesName === "占比(%)";
          const valueText =
            row.dataIndex === undefined
              ? EM_DASH
              : isPct
                ? lineValueTexts[row.dataIndex] ?? EM_DASH
                : barValueTexts[row.dataIndex] ?? EM_DASH;
          const renderedValue = valueText === EM_DASH ? EM_DASH : `${valueText}${isPct ? "%" : " 亿元"}`;
          return `${row.seriesName ?? ""}：${renderedValue}`;
        });
        const count = first.dataIndex === undefined ? undefined : bondCounts[first.dataIndex];
        if (count !== undefined) lines.push(`${count} 只`);
        return [first.name ?? "", ...lines].join("<br/>");
      },
    },
    xAxis: { type: "category", data: categories, axisLabel: { rotate: 25, fontSize: 11 } },
    yAxis: [
      { type: "value", name: "亿元", splitLine: { lineStyle: { type: "dashed" } } },
      { type: "value", name: "%", splitLine: { show: false } },
    ],
    series: [
      {
        name: "规模(亿)",
        type: "bar",
        data: barYi,
        yAxisIndex: 0,
        barMaxWidth: 40,
        itemStyle: { color: nocturneChartTheme.categoricalPalette[0] },
      },
      {
        name: "占比(%)",
        type: "line",
        smooth: true,
        data: linePct,
        yAxisIndex: 1,
        itemStyle: { color: nocturneChartTheme.categoricalPalette[2] },
        lineStyle: { color: nocturneChartTheme.categoricalPalette[2] },
      },
    ],
  });

  /* 真空时收缩为空态而不是画零值假图（DESIGN.md §12 第 13 条）：ready 且无 items 交给 ChartCard 的 empty。 */
  return (
    <ChartCard
      testId="bond-dashboard-maturity-structure-chart"
      title="期限结构"
      question="规模与占比按期限桶怎么分布"
      height={CHART_HEIGHT}
      option={items.length === 0 ? null : option}
      state={state.status === "ready" ? undefined : state.status}
      errorMessage={state.message ?? undefined}
      /* 顶层合计为后端已返回未消费字段（行业表口径注同款位置）。 */
      /* 单位随合计读数一起出现，不再单独传 unit 造成「亿元 · 合计 … 亿元」重复。 */
      actions={<span className="bond-dashboard-page__panel-head-note">合计 {totalText} 亿元</span>}
    />
  );
}
