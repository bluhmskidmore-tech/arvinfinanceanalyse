import { Link } from "react-router-dom";
import ReactECharts, { type EChartsOption } from "../../../../lib/echarts";
import { tabularNumsStyle } from "../../../../theme/designSystem";
import type { DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";
import { COCKPIT_TYPOGRAPHY, COCKPIT_VISUAL } from "../dashboardCockpitVisualTokens";

type RiskAlertPanelProps = {
  radar: DashboardCockpitHomeViewModel["riskRadar"];
  alertCount: number;
  alertCounts: DashboardCockpitHomeViewModel["riskAlertCounts"];
  todos: DashboardCockpitHomeViewModel["todos"];
  watchlist: DashboardCockpitHomeViewModel["watchlist"];
  riskReviewOnly?: boolean;
  usesMockRiskRadar?: boolean;
};

export function RiskAlertPanel({
  radar,
  alertCount,
  alertCounts,
  todos,
  watchlist,
  riskReviewOnly = false,
  usesMockRiskRadar = false,
}: RiskAlertPanelProps) {
  const hasRadarData =
    !radar.pending && radar.dimensions.length >= 3 && radar.values.length >= 3;
  const warningValues = hasRadarData
    ? radar.values.map((value) => Math.min(100, value + 14))
    : [];

  const radarOption: EChartsOption = {
    radar: {
      indicator: radar.dimensions.map((name) => ({ name, max: 100 })),
      radius: "62%",
      splitNumber: 5,
      axisName: {
        color: COCKPIT_VISUAL.text.muted,
        fontFamily: COCKPIT_TYPOGRAPHY.fontSans,
        fontSize: COCKPIT_TYPOGRAPHY.size.chartAxis,
      },
      axisLabel: { show: false },
      splitLine: { lineStyle: { color: COCKPIT_VISUAL.surface.divider } },
      splitArea: { areaStyle: { color: [COCKPIT_VISUAL.surface.card, COCKPIT_VISUAL.surface.content] } },
    },
    series: hasRadarData
      ? [
          {
            type: "radar",
            data: [
              {
                value: [...radar.values],
                name: "当前",
                areaStyle: { color: "rgba(24, 80, 161, 0.12)" },
                lineStyle: { color: COCKPIT_VISUAL.chart.primary, width: 1.75 },
                itemStyle: { color: COCKPIT_VISUAL.chart.primary },
              },
              {
                value: warningValues,
                name: "预警阈值",
                areaStyle: { color: "transparent" },
                lineStyle: {
                  color: COCKPIT_VISUAL.chart.gold,
                  width: 1.25,
                  type: "dashed",
                },
                itemStyle: { color: COCKPIT_VISUAL.chart.gold },
              },
            ],
          },
        ]
      : [],
  };

  return (
    <section
      data-testid="dashboard-risk-alert-panel"
      id="dashboard-home-risk-section"
      className="dashboard-cockpit-panel dashboard-cockpit-panel--risk"
    >
      <header className="dashboard-cockpit-panel__head">
        <span className="dashboard-cockpit-panel__eyebrow">{riskReviewOnly ? "风险关注" : "风险预警"}</span>
        <h2 className="dashboard-cockpit-panel__title">
          {riskReviewOnly ? "待复核" : "预警"}{" "}
          <span style={tabularNumsStyle}>{alertCount}</span> 项
        </h2>
        <Link to="/risk-tensor" className="dashboard-cockpit-pulse-section__more">
          进入风险处置台 →
        </Link>
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
            {hasRadarData ? (
              <ReactECharts option={radarOption} style={{ height: 132 }} opts={{ renderer: "canvas" }} />
            ) : (
              <p
                className="dashboard-cockpit-panel__empty dashboard-home-muted"
                data-testid="dashboard-risk-radar-pending"
              >
                风险雷达待同步
              </p>
            )}
            <p className="dashboard-cockpit-radar__legend">
              {usesMockRiskRadar
                ? "示意数据，非正式风控口径；虚线为示意阈值"
                : hasRadarData
                  ? "基于组合风险读面映射，虚线为示意阈值"
                  : "待接入同日风险读面"}
            </p>
          </div>
          <div className="dashboard-cockpit-risk-lists">
            <details
              data-testid="dashboard-risk-lists-drawer"
              className="dashboard-cockpit-risk-lists-drawer"
              open
            >
              <summary>
                待办与观察（{todos.length + watchlist.length}）
              </summary>
              <div className="dashboard-cockpit-risk-lists-drawer__body">
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
            </details>
          </div>
        </div>
      </div>
    </section>
  );
}
