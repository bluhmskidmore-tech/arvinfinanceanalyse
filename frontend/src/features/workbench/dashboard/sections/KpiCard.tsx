import { tabularNumsStyle } from "../../../../theme/designSystem";
import type { DashboardKpiCardVM } from "../dashboardCockpitHomeModel";
import { resolveKpiDeltaClass } from "../dashboardCockpitHomeModel";

type KpiCardProps = {
  card: DashboardKpiCardVM;
};

export function KpiCard({ card }: KpiCardProps) {
  return (
    <article
      data-testid={`dashboard-kpi-card-${card.id}`}
      className={`dashboard-cockpit-kpi${card.pending ? " dashboard-cockpit-kpi--pending" : ""}`}
    >
      <div className="dashboard-cockpit-kpi__head">
        <span className="dashboard-cockpit-kpi__label">{card.label}</span>
        <span className="dashboard-cockpit-kpi__icon" aria-hidden="true">
          {card.iconLabel}
        </span>
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
    </article>
  );
}
