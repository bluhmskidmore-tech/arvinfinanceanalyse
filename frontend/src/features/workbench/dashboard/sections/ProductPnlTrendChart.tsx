import { Link } from "react-router-dom";
import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../../lib/echarts";
import type { DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";
import {
  buildCockpitCategoryAxis,
  buildCockpitChartGrid,
  buildCockpitChartTooltip,
  buildCockpitValueAxis,
} from "../dashboardCockpitChartTheme";
import {
  COCKPIT_CHART_PALETTE,
  COCKPIT_TYPOGRAPHY,
  COCKPIT_VISUAL,
} from "../dashboardCockpitVisualTokens";

type ProductPnlTrendChartProps = {
  data: DashboardCockpitHomeViewModel["productPnl"];
};

export function ProductPnlTrendChart({ data }: ProductPnlTrendChartProps) {
  const hasChartData =
    !data.pending &&
    data.series.length > 0 &&
    data.series.some((item) => item.values.length > 0);

  const option: EChartsOption = useMemo(() => {
    return {
      color: [...COCKPIT_CHART_PALETTE],
      grid: buildCockpitChartGrid({ left: 42, right: 18, top: 30, bottom: 32 }),
      tooltip: buildCockpitChartTooltip(),
      legend: {
        top: 0,
        right: 8,
        textStyle: {
          color: COCKPIT_VISUAL.text.muted,
          fontFamily: COCKPIT_TYPOGRAPHY.fontSans,
          fontSize: COCKPIT_TYPOGRAPHY.size.chartAxis,
        },
        itemWidth: 10,
        itemHeight: 6,
      },
      xAxis: {
        ...buildCockpitCategoryAxis(data.months),
        boundaryGap: false,
      },
      yAxis: {
        ...buildCockpitValueAxis(),
        name: "亿",
      },
      series: data.series.map((item) => {
        const isTotal = item.id === "total" || item.name === "合计";
        return {
          name: item.name,
          type: "line",
          smooth: true,
          symbol: "circle",
          symbolSize: isTotal ? 5 : 3,
          lineStyle: {
            width: isTotal ? 2.5 : 1,
            opacity: isTotal ? 1 : 0.42,
          },
          emphasis: { focus: "series" },
          data: [...item.values],
        };
      }),
    };
  }, [data]);

  return (
    <section
      data-testid="dashboard-product-pnl-trend"
      className="dashboard-cockpit-panel dashboard-cockpit-panel--chart"
    >
      <header className="dashboard-cockpit-panel__head">
        <span className="dashboard-cockpit-panel__eyebrow">债券损益</span>
        <h2 className="dashboard-cockpit-panel__title">四类债券月度损益趋势</h2>
        {data.pending ? (
          <p className="dashboard-cockpit-panel__pending" data-testid="dashboard-product-pnl-pending">
            四类债券月度趋势待同步
          </p>
        ) : null}
      </header>
      {hasChartData ? (
        <ReactECharts option={option} style={{ height: 240 }} opts={{ renderer: "canvas" }} />
      ) : (
        <div
          data-testid="dashboard-product-pnl-empty"
          className="dashboard-cockpit-panel__empty dashboard-home-muted"
        >
          四类债券月度趋势待同步；请前往
          {" "}
          <Link to="/pnl-by-business">业务损益</Link>
          {" "}
          查看正式读面。
        </div>
      )}
    </section>
  );
}
