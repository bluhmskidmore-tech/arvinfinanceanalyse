import { useMemo } from "react";

import ReactECharts, { type EChartsOption } from "../../../../lib/echarts";
import { tabularNumsStyle } from "../../../../theme/designSystem";
import type {
  DashboardCockpitHomeViewModel,
  DashboardPortfolioCenterAumVM,
} from "../dashboardCockpitHomeModel";
import { resolveKpiDeltaClass } from "../dashboardCockpitHomeModel";
import { buildCockpitChartTooltip } from "../dashboardCockpitChartTheme";
import { COCKPIT_VISUAL } from "../dashboardCockpitVisualTokens";

type PortfolioOverviewProps = {
  stats: DashboardCockpitHomeViewModel["portfolioStats"];
  assetBars: DashboardCockpitHomeViewModel["assetBars"];
  centerAum: DashboardPortfolioCenterAumVM;
  interbankAssets: string;
  interbankLiabilities: string;
  interbankNetPosition: string;
  interbankNetPositionTone: DashboardCockpitHomeViewModel["interbankNetPositionTone"];
};

function buildDonutOption(
  assetBars: PortfolioOverviewProps["assetBars"],
): EChartsOption {
  return {
    color: assetBars.map((bar) => bar.color),
    tooltip: {
      ...buildCockpitChartTooltip(),
      trigger: "item",
      formatter: (params) => {
        if (!params || typeof params !== "object" || !("name" in params)) return "";
        const pct = assetBars.find((bar) => bar.label === params.name)?.pct;
        return pct != null ? `${String(params.name)}<br/>${pct.toFixed(1)}%` : String(params.name);
      },
    },
    series: [
      {
        type: "pie",
        radius: ["56%", "78%"],
        center: ["50%", "50%"],
        padAngle: 1.5,
        itemStyle: {
          borderColor: COCKPIT_VISUAL.surface.card,
          borderWidth: 2,
        },
        label: { show: false },
        labelLine: { show: false },
        data: assetBars.map((bar) => ({
          name: bar.label,
          value: bar.pct,
        })),
      },
    ],
  };
}

export function PortfolioOverview({
  stats,
  assetBars,
  centerAum,
  interbankAssets,
  interbankLiabilities,
  interbankNetPosition,
  interbankNetPositionTone,
}: PortfolioOverviewProps) {
  const donutOption = useMemo(() => buildDonutOption(assetBars), [assetBars]);

  return (
    <section
      data-testid="dashboard-portfolio-overview"
      className="dashboard-cockpit-panel dashboard-cockpit-panel--portfolio"
    >
      <header className="dashboard-cockpit-panel__head">
        <span className="dashboard-cockpit-panel__eyebrow">债券组合概览</span>
        <h2 className="dashboard-cockpit-panel__title">持仓与资产分布</h2>
      </header>
      <div className="dashboard-cockpit-panel__body">
        <div className="dashboard-cockpit-portfolio-stats">
          {stats.map((stat) => (
            <article key={stat.id} className="dashboard-cockpit-portfolio-stat">
              <span>{stat.label}</span>
              <strong style={tabularNumsStyle}>{stat.value}</strong>
            </article>
          ))}
        </div>
        <div className="dashboard-cockpit-asset-mix">
          <div className="dashboard-cockpit-asset-bars">
            {assetBars.map((bar) => (
              <div key={bar.id} className="dashboard-cockpit-asset-bar-row">
                <span className="dashboard-cockpit-asset-bar-row__label">{bar.label}</span>
                <div className="dashboard-cockpit-asset-bar-row__track">
                  <i style={{ width: `${bar.pct}%`, background: bar.color }} />
                </div>
                <strong style={tabularNumsStyle}>{bar.value}</strong>
                <strong style={tabularNumsStyle}>{bar.pct.toFixed(1)}%</strong>
              </div>
            ))}
          </div>
          <div
            data-testid="dashboard-cockpit-portfolio-donut"
            className="dashboard-cockpit-donut-chart"
            aria-label={`${centerAum.label} ${centerAum.value}`}
          >
            <ReactECharts option={donutOption} style={{ height: 148, width: "100%" }} opts={{ renderer: "canvas" }} />
            <div className="dashboard-cockpit-donut-chart__center" aria-hidden="true">
              <span style={tabularNumsStyle}>{centerAum.value}</span>
              <em>{centerAum.label}</em>
            </div>
          </div>
        </div>
        <div className="dashboard-cockpit-interbank">
          <article>
            <span>同业资产</span>
            <strong style={tabularNumsStyle}>{interbankAssets}</strong>
          </article>
          <article>
            <span>同业负债</span>
            <strong style={tabularNumsStyle}>{interbankLiabilities}</strong>
          </article>
          <article>
            <span>净头寸</span>
            <strong
              className={resolveKpiDeltaClass(interbankNetPositionTone)}
              style={tabularNumsStyle}
            >
              {interbankNetPosition}
            </strong>
          </article>
        </div>
      </div>
    </section>
  );
}
