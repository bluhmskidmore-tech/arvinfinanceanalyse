import { tabularNumsStyle } from "../../../../theme/designSystem";
import type { DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";

type PortfolioOverviewProps = {
  stats: DashboardCockpitHomeViewModel["portfolioStats"];
  assetBars: DashboardCockpitHomeViewModel["assetBars"];
  interbankAssets: string;
  interbankLiabilities: string;
  interbankNetPosition: string;
};

function buildDonutGradient(bars: PortfolioOverviewProps["assetBars"]): string {
  let cursor = 0;
  const segments = bars.map((bar) => {
    const start = cursor;
    const end = cursor + bar.pct * 3.6;
    cursor = end;
    return `${bar.color} ${start}deg ${end}deg`;
  });
  return segments.length > 0 ? `conic-gradient(${segments.join(", ")})` : "conic-gradient(#e5e7eb 0 360deg)";
}

export function PortfolioOverview({
  stats,
  assetBars,
  interbankAssets,
  interbankLiabilities,
  interbankNetPosition,
}: PortfolioOverviewProps) {
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
            className="dashboard-cockpit-donut"
            style={{ background: buildDonutGradient(assetBars) }}
            aria-label="总资产规模 3,708.10 亿"
          >
            <span style={tabularNumsStyle}>3,708.10 亿</span>
            <em>总资产规模</em>
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
            <strong className="dashboard-cockpit-delta--down" style={tabularNumsStyle}>
              {interbankNetPosition}
            </strong>
          </article>
        </div>
      </div>
    </section>
  );
}
