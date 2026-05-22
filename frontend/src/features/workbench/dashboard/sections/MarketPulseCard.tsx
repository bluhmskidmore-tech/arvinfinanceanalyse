import { tabularNumsStyle } from "../../../../theme/designSystem";
import { buildSparkPath } from "../sparklinePath";
import type { DashboardMarketPulseVM } from "../dashboardCockpitHomeModel";
import { resolveKpiDeltaClass } from "../dashboardCockpitHomeModel";

const SPARK_W = 88;
const SPARK_H = 28;
const SPARK_BASELINE_Y = SPARK_H - 2;

type MarketPulseCardProps = {
  item: DashboardMarketPulseVM;
};

export function MarketPulseCard({ item }: MarketPulseCardProps) {
  const path = buildSparkPath(item.sparkline, SPARK_W, SPARK_H);
  const areaPath = `${path} L ${SPARK_W - 2} ${SPARK_BASELINE_Y} L 2 ${SPARK_BASELINE_Y} Z`;

  return (
    <article
      data-testid={`dashboard-market-pulse-${item.id}`}
      className="dashboard-cockpit-pulse"
      data-tone={item.deltaTone}
    >
      <div className="dashboard-cockpit-pulse__head">
        <span className="dashboard-cockpit-pulse__label">{item.label}</span>
        <span className="dashboard-cockpit-pulse__status">{item.statusLabel}</span>
      </div>
      <div className="dashboard-cockpit-pulse__body">
        <div className="dashboard-cockpit-pulse__values">
          <strong style={tabularNumsStyle}>{item.value}</strong>
          <span className={resolveKpiDeltaClass(item.deltaTone)} style={tabularNumsStyle}>
            {item.delta}
          </span>
        </div>
        <svg
          className="dashboard-cockpit-pulse__spark"
          viewBox={`0 0 ${SPARK_W} ${SPARK_H}`}
          aria-hidden="true"
        >
          <path d={`M 2 ${SPARK_BASELINE_Y} L ${SPARK_W - 2} ${SPARK_BASELINE_Y}`} className="dashboard-cockpit-pulse__spark-baseline" />
          <path d={areaPath} className="dashboard-cockpit-pulse__spark-area" stroke="none" />
          <path d={path} className="dashboard-cockpit-pulse__spark-line" fill="none" strokeLinejoin="round" strokeLinecap="round" />
        </svg>
      </div>
    </article>
  );
}
