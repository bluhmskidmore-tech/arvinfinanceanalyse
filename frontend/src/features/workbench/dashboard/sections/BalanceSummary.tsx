import { tabularNumsStyle } from "../../../../theme/designSystem";
import type { DashboardBalanceMetricMock } from "../dashboardMockData";
import { resolveKpiDeltaClass } from "../dashboardCockpitHomeModel";

type BalanceSummaryProps = {
  metrics: readonly DashboardBalanceMetricMock[];
};

export function BalanceSummary({ metrics }: BalanceSummaryProps) {
  return (
    <section
      data-testid="dashboard-balance-summary"
      className="dashboard-cockpit-panel dashboard-cockpit-panel--balance"
    >
      <header className="dashboard-cockpit-panel__head">
        <span className="dashboard-cockpit-panel__eyebrow">资产负债</span>
        <h2 className="dashboard-cockpit-panel__title">经营与资产负债摘要</h2>
      </header>
      <div className="dashboard-cockpit-balance-grid">
        {metrics.map((metric) => (
          <article
            key={metric.id}
            data-testid={`dashboard-balance-metric-${metric.id}`}
            className="dashboard-cockpit-balance-card"
          >
            <span>{metric.label}</span>
            <strong style={tabularNumsStyle}>{metric.value}</strong>
            <em className={resolveKpiDeltaClass(metric.tone === "positive" ? "up" : metric.tone === "negative" ? "down" : metric.tone === "warning" ? "warn" : "flat")}>
              {metric.delta}
            </em>
          </article>
        ))}
      </div>
    </section>
  );
}
