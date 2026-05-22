import { Link } from "react-router-dom";
import ReactECharts, { type EChartsOption } from "../../../../lib/echarts";
import { tabularNumsStyle } from "../../../../theme/designSystem";
import type { DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";
import { COCKPIT_VISUAL } from "../dashboardCockpitVisualTokens";

type RiskAlertPanelProps = {
  radar: DashboardCockpitHomeViewModel["riskRadar"];
  alertCount: number;
  alertCounts: DashboardCockpitHomeViewModel["riskAlertCounts"];
  todos: DashboardCockpitHomeViewModel["todos"];
  watchlist: DashboardCockpitHomeViewModel["watchlist"];
};

export function RiskAlertPanel({
  radar,
  alertCount,
  alertCounts,
  todos,
  watchlist,
}: RiskAlertPanelProps) {
  const radarOption: EChartsOption = {
    radar: {
      indicator: radar.dimensions.map((name) => ({ name, max: 100 })),
      radius: "62%",
      splitNumber: 4,
      axisName: { color: COCKPIT_VISUAL.text.muted, fontSize: 10 },
      splitLine: { lineStyle: { color: "#edf1f5" } },
      splitArea: { areaStyle: { color: ["#ffffff", "#f8fafc"] } },
    },
    series: [
      {
        type: "radar",
        data: [{ value: [...radar.values], name: "风险画像" }],
        areaStyle: { color: "rgba(29, 78, 137, 0.14)" },
        lineStyle: { color: COCKPIT_VISUAL.chart.primary, width: 1.5 },
        itemStyle: { color: COCKPIT_VISUAL.chart.primary },
      },
    ],
  };

  return (
    <section
      data-testid="dashboard-risk-alert-panel"
      className="dashboard-cockpit-panel dashboard-cockpit-panel--risk"
    >
      <header className="dashboard-cockpit-panel__head">
        <span className="dashboard-cockpit-panel__eyebrow">风险预警</span>
        <h2 className="dashboard-cockpit-panel__title">
          预警 <span style={tabularNumsStyle}>{alertCount}</span> 项
        </h2>
      </header>
      <div className="dashboard-cockpit-panel__body">
        <div className="dashboard-cockpit-risk-counts">
          {alertCounts.map((item) => (
            <article key={item.id}>
              <span>{item.label}</span>
              <strong className={`dashboard-cockpit-risk-counts__value ${item.tone === "warn" ? "dashboard-cockpit-delta--warn" : item.tone === "down" ? "dashboard-cockpit-delta--down" : "dashboard-cockpit-delta--flat"}`} style={tabularNumsStyle}>
                {item.count}
              </strong>
            </article>
          ))}
        </div>
        <div className="dashboard-cockpit-risk-body">
          <div data-testid="dashboard-risk-radar" className="dashboard-cockpit-radar">
            <ReactECharts option={radarOption} style={{ height: 120 }} opts={{ renderer: "canvas" }} />
          </div>
          <div className="dashboard-cockpit-risk-lists">
            <div className="dashboard-cockpit-todos">
              <h3>待办清单</h3>
              <ul>
                {todos.map((todo) => (
                  <li key={todo.id}>
                    <Link to={todo.path}>
                      <span className={`dashboard-cockpit-todo__priority priority-${todo.priority}`}>
                        {todo.priority}
                      </span>
                      <strong>{todo.title}</strong>
                      <em>{todo.status}</em>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
            <div className="dashboard-cockpit-watchlist">
              <h3>观察清单</h3>
              <ul>
                {watchlist.map((item) => (
                  <li key={item.id}>
                    <Link to={item.path}>
                      <code style={tabularNumsStyle}>{item.count}</code>
                      <span>{item.label}</span>
                      <em>{item.note}</em>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
