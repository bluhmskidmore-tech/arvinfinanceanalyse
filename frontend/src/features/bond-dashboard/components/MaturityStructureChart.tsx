import { type EChartsOption } from "../../../lib/echarts";

import type { MaturityStructurePayload } from "../../../api/contracts";
import { BaseChart } from "../../../components/charts/BaseChart";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import { EM_DASH } from "../../../pageModel";
import { formatYi, nativeToNumber } from "../utils/format";

export function MaturityStructureChart({
  data,
  loading,
}: {
  data: MaturityStructurePayload | undefined;
  loading: boolean;
}) {
  const items = data?.items ?? [];
  const categories = items.map((i) => i.maturity_bucket);
  const barYi = items.map((i) => {
    const raw = nativeToNumber(i.total_market_value);
    return raw === null ? null : raw / 1e8;
  });
  const linePct = items.map((i) => {
    const raw = nativeToNumber(i.percentage);
    return raw === null ? null : raw * 100;
  });
  /* 后端 items 带 bond_count、顶层带 total_market_value（此前均未消费）。 */
  const bondCounts = items.map((i) => i.bond_count);
  const totalText = data ? formatYi(data.total_market_value) : EM_DASH;

  /*
   * 测试契约：series[0] 柱（规模）、series[1] 折线（占比，百分点数组）顺序
   * 不可换；占比折线是分类序列，用琥珀而非涨跌绿/红。
   */
  const option: EChartsOption = nocturneChartTheme.createBarChartOption({
    legend: { data: ["规模(亿)", "占比(%)"], bottom: 4 },
    grid: { left: 48, right: 56, top: 40, bottom: 68 },
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
          const value = row.value;
          const isPct = row.seriesName === "占比(%)";
          const valueText =
            value === null || value === undefined
              ? EM_DASH
              : `${Number(value).toLocaleString("zh-CN", {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}${isPct ? "%" : " 亿元"}`;
          return `${row.seriesName ?? ""}：${valueText}`;
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

  return (
    <div
      data-testid="bond-dashboard-maturity-structure-chart"
      className="bond-dashboard-page__panel bond-dashboard-charts__panel"
    >
      <div className="bond-dashboard-charts__head">
        <h3 className="bond-dashboard-charts__head-title">期限结构</h3>
        {/* 顶层合计为后端已返回未消费字段（行业表口径注同款位置）。 */}
        <span className="bond-dashboard-charts__head-note">合计 {totalText} 亿元</span>
      </div>
      {loading ? (
        <p className="bond-dashboard-page__surface bond-dashboard-page__surface--loading">
          载入中…
        </p>
      ) : data && items.length === 0 ? (
        /* 仅真实空 payload 收敛为暂无数据；envelope 未到达时维持图表骨架防高度跳变。 */
        <p className="bond-dashboard-page__surface bond-dashboard-page__surface--empty">
          暂无数据
        </p>
      ) : (
        <BaseChart option={option} height={300} />
      )}
    </div>
  );
}
