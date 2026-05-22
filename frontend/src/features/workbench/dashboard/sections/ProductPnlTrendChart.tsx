import { Link } from "react-router-dom";
import { useMemo, useState } from "react";
import ReactECharts, { type EChartsOption } from "../../../../lib/echarts";
import type { DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";
import { COCKPIT_CHART_PALETTE, COCKPIT_VISUAL } from "../dashboardCockpitVisualTokens";

type ProductPnlTrendChartProps = {
  data: DashboardCockpitHomeViewModel["productPnl"];
};

export function ProductPnlTrendChart({ data }: ProductPnlTrendChartProps) {
  const [activePeriod, setActivePeriod] = useState("day");

  const hasChartData =
    !data.pending &&
    data.series.length > 0 &&
    data.series.some((item) => item.values.length > 0);

  const option: EChartsOption = useMemo(() => {
    return {
      color: [...COCKPIT_CHART_PALETTE],
      grid: { left: 42, right: 18, top: 30, bottom: 32 },
      tooltip: { trigger: "axis" },
      legend: {
        top: 0,
        right: 8,
        textStyle: { color: COCKPIT_VISUAL.text.muted, fontSize: 11 },
        itemWidth: 10,
        itemHeight: 6,
      },
      xAxis: { type: "category", data: [...data.months], boundaryGap: false },
      yAxis: { type: "value", name: "亿" },
      series: data.series.map((item) => ({
        name: item.name,
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: 4,
        data: [...item.values],
      })),
    };
  }, [data]);

  return (
    <section
      data-testid="dashboard-product-pnl-trend"
      className="dashboard-cockpit-panel dashboard-cockpit-panel--chart"
    >
      <header className="dashboard-cockpit-panel__head">
        <span className="dashboard-cockpit-panel__eyebrow">产品损益</span>
        <h2 className="dashboard-cockpit-panel__title">产品分类损益趋势图</h2>
        {data.pending ? (
          <p className="dashboard-cockpit-panel__pending" data-testid="dashboard-product-pnl-pending">
            口径待确认：产品分类月度损益序列尚未接入首页读面。
          </p>
        ) : null}
        {hasChartData ? (
          <div className="dashboard-cockpit-tabs" role="tablist" aria-label="产品损益周期">
            {[
              ["day", "日度"],
              ["week", "周度"],
              ["month", "月度"],
              ["ytd", "YTD"],
            ].map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={activePeriod === id}
                className={`dashboard-cockpit-tabs__btn${activePeriod === id ? " dashboard-cockpit-tabs__btn--active" : ""}`}
                onClick={() => setActivePeriod(id)}
              >
                {label}
              </button>
            ))}
          </div>
        ) : null}
      </header>
      {hasChartData ? (
        <ReactECharts option={option} style={{ height: 240 }} opts={{ renderer: "canvas" }} />
      ) : (
        <div
          data-testid="dashboard-product-pnl-empty"
          className="dashboard-cockpit-panel__empty dashboard-home-muted"
        >
          暂无可用月度序列；请前往
          {" "}
          <Link to="/product-category-pnl">产品损益</Link>
          {" "}
          查看正式读面。
        </div>
      )}
    </section>
  );
}
