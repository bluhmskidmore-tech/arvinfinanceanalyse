import { Link } from "react-router-dom";

import ReactECharts, { type EChartsOption } from "../../../../lib/echarts";
import { tabularNumsStyle } from "../../../../theme/designSystem";
import type { DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";
import { COCKPIT_TYPOGRAPHY, COCKPIT_VISUAL } from "../dashboardCockpitVisualTokens";

type RiskActionStripProps = {
  viewModel: DashboardCockpitHomeViewModel;
};

export function RiskActionStrip({ viewModel }: RiskActionStripProps) {
  const strip = viewModel.riskActionStrip;
  const hasRadarData =
    !strip.radar.pending && strip.radar.dimensions.length >= 3 && strip.radar.values.length >= 3;
  const warningValues = hasRadarData
    ? strip.radar.values.map((value) => Math.min(100, value + 14))
    : [];
  const option: EChartsOption = {
    radar: {
      indicator: strip.radar.dimensions.map((name) => ({ name, max: 100 })),
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
                value: [...strip.radar.values],
                name: "当前",
                areaStyle: { color: COCKPIT_VISUAL.brand.primarySoft },
                lineStyle: { color: COCKPIT_VISUAL.chart.primary, width: 1.6 },
                itemStyle: { color: COCKPIT_VISUAL.chart.primary },
              },
              {
                value: warningValues,
                name: "预警阈值",
                areaStyle: { color: "transparent" },
                lineStyle: { color: COCKPIT_VISUAL.semantic.warn, width: 1.1, type: "dashed" },
                itemStyle: { color: COCKPIT_VISUAL.semantic.warn },
              },
            ],
          },
        ]
      : [],
  };

  return (
    <section
      data-testid="dashboard-risk-action-strip"
      className="dashboard-terminal-risk-action-strip"
      aria-label="风险处置区"
    >
      <div
        data-testid="dashboard-risk-alert-panel"
        id="dashboard-home-risk-section"
        className="dashboard-terminal-risk-action-strip__inner"
      >
        <header className="dashboard-terminal-risk-action-strip__head">
          <span className="dashboard-terminal-eyebrow">
            {strip.riskReviewOnly ? "风险待复核" : "风险处置"}
          </span>
          <h2>风险与预警</h2>
        </header>
        <div data-testid="dashboard-risk-radar" className="dashboard-terminal-risk-action-strip__radar">
          {hasRadarData ? (
            <ReactECharts option={option} style={{ height: 154 }} opts={{ renderer: "canvas" }} />
          ) : (
            <p
              className="dashboard-cockpit-panel__empty dashboard-home-muted"
              data-testid="dashboard-risk-radar-pending"
            >
              风险雷达待同步
            </p>
          )}
        </div>
        <div className="dashboard-terminal-risk-action-strip__counts">
          {strip.alertCounts.map((item) => (
            <article key={item.id}>
              <span>{item.label}</span>
              <strong style={tabularNumsStyle}>{item.count}</strong>
            </article>
          ))}
        </div>
        <div className="dashboard-terminal-risk-action-strip__work">
          <article>
            <span>待办清单</span>
            <strong style={tabularNumsStyle}>{strip.todoCount} 项</strong>
            <em>高优先级 {strip.highPriorityTodoCount} 项</em>
          </article>
          <article>
            <span>观察清单</span>
            <strong style={tabularNumsStyle}>{strip.watchCount} 项</strong>
            <em>
              {strip.usesMockRiskRadar
                ? "示意数据，非正式风控口径；虚线为示意阈值"
                : "同日风险读面"}
            </em>
          </article>
        </div>
        <Link to={strip.entryHref} className="dashboard-terminal-risk-action-strip__cta">
          进入风险处置台 →
        </Link>
      </div>
    </section>
  );
}
