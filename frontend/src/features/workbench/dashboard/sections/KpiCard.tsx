import { tabularNumsStyle } from "../../../../theme/designSystem";
import type { DashboardKpiCardVM } from "../dashboardCockpitHomeModel";
import { resolveKpiDeltaClass } from "../dashboardCockpitHomeModel";
import { buildSparkPath } from "../sparklinePath";

const SPARK_W = 116;
const SPARK_H = 28;
const SPARK_BASELINE_Y = SPARK_H - 3;

type KpiCardProps = {
  card: DashboardKpiCardVM;
};

export function KpiCard({ card }: KpiCardProps) {
  const sparkPath = buildSparkPath(card.sparkline, SPARK_W, SPARK_H);
  const areaPath = `${sparkPath} L ${SPARK_W - 2} ${SPARK_BASELINE_Y} L 2 ${SPARK_BASELINE_Y} Z`;

  return (
    <article
      data-testid={`dashboard-kpi-card-${card.id}`}
      className={`dashboard-cockpit-kpi${card.pending ? " dashboard-cockpit-kpi--pending" : ""}`}
      data-sparkline-muted={card.sparklineMuted ? "true" : "false"}
    >
      <div className="dashboard-cockpit-kpi__head">
        <span className="dashboard-cockpit-kpi__label">{card.label}</span>
      </div>
      <strong className="dashboard-cockpit-kpi__value" style={tabularNumsStyle}>
        {card.value}
      </strong>
      <span
        className={`dashboard-cockpit-kpi__delta ${resolveKpiDeltaClass(card.deltaTone)}`}
        style={tabularNumsStyle}
      >
        {card.delta}
      </span>
      <svg
        className="dashboard-cockpit-kpi__spark"
        viewBox={`0 0 ${SPARK_W} ${SPARK_H}`}
        data-tone={card.deltaTone}
        aria-hidden="true"
      >
        <path
          d={`M 2 ${SPARK_BASELINE_Y} L ${SPARK_W - 2} ${SPARK_BASELINE_Y}`}
          className="dashboard-cockpit-kpi__spark-baseline"
        />
        <path d={areaPath} className="dashboard-cockpit-kpi__spark-area" stroke="none" />
        <path
          d={sparkPath}
          className="dashboard-cockpit-kpi__spark-line"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </article>
  );
}
