import type {
  DashboardCockpitHomeViewModel,
  DashboardKpiCardVM,
} from "../dashboardCockpitHomeModel";
import { resolveKpiDeltaClass } from "../dashboardCockpitHomeModel";
import { buildSparkPath } from "../sparklinePath";

const OVERVIEW_SPARK_W = 132;
const OVERVIEW_SPARK_H = 34;
const HEALTH_SPARK_W = 184;
const HEALTH_SPARK_H = 32;

type ExecutiveOverviewPanelProps = {
  overview: DashboardCockpitHomeViewModel["executiveOverview"];
};

function MetricSparkline({
  values,
  width = OVERVIEW_SPARK_W,
  height = OVERVIEW_SPARK_H,
}: {
  values: readonly number[];
  width?: number;
  height?: number;
}) {
  return (
    <svg
      className="dashboard-terminal-sparkline"
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden="true"
    >
      <path
        className="dashboard-terminal-sparkline__baseline"
        d={`M 2 ${height - 4} L ${width - 2} ${height - 4}`}
      />
      <path
        className="dashboard-terminal-sparkline__line"
        d={buildSparkPath(values, width, height)}
      />
    </svg>
  );
}

function CoreMetric({ card }: { card: DashboardKpiCardVM }) {
  return (
    <article
      data-testid={`dashboard-kpi-card-${card.id}`}
      className="dashboard-terminal-core-metric"
      data-tone={card.deltaTone}
    >
      <span className="dashboard-terminal-core-metric__label">{card.label}</span>
      <strong className="dashboard-cockpit-tabular">{card.value}</strong>
      <span className={resolveKpiDeltaClass(card.deltaTone)}>{card.delta}</span>
      <MetricSparkline values={card.sparkline} />
    </article>
  );
}

function RiskConstraint({ card }: { card: DashboardKpiCardVM }) {
  const hasDirectionalDelta = /[+-]\d|较|待|口径/.test(card.delta);
  const helperText = hasDirectionalDelta ? card.delta : card.relationLabel ?? card.delta;

  return (
    <article
      data-testid={`dashboard-kpi-card-${card.id}`}
      className="dashboard-terminal-risk-constraint"
      data-tone={card.deltaTone}
    >
      <div className="dashboard-terminal-risk-constraint__head">
        <span>{card.label}</span>
        {card.signalLabel ? <em>{card.signalLabel}</em> : null}
      </div>
      <strong className="dashboard-cockpit-tabular">{card.value}</strong>
      <span className={resolveKpiDeltaClass(card.deltaTone)}>{helperText}</span>
    </article>
  );
}

export function ExecutiveOverviewPanel({ overview }: ExecutiveOverviewPanelProps) {
  return (
    <section
      data-testid="dashboard-executive-overview"
      className="dashboard-terminal-overview"
      aria-label="经营决策总览"
    >
      <article className="dashboard-terminal-overview__main">
        <header className="dashboard-terminal-overview__header">
          <span className="dashboard-terminal-eyebrow">经营决策总览</span>
          <h2>今日经营判断</h2>
        </header>
        <p className="dashboard-terminal-overview__summary">{overview.summary}</p>
        <div
          data-testid="dashboard-kpi-core-group"
          className="dashboard-terminal-core-metrics"
          aria-label="经营核心指标"
        >
          <span className="dashboard-terminal-core-metrics__title">经营核心指标</span>
          {overview.coreMetrics.map((card) => (
            <CoreMetric key={card.id} card={card} />
          ))}
        </div>
        <div className="dashboard-terminal-health-row">
          <div>
            <span>{overview.healthLabel}</span>
            <strong>{overview.healthText}</strong>
          </div>
          <MetricSparkline
            values={overview.healthSparkline}
            width={HEALTH_SPARK_W}
            height={HEALTH_SPARK_H}
          />
        </div>
      </article>

      <aside
        data-testid="dashboard-kpi-risk-group"
        className="dashboard-terminal-risk-stack"
        aria-label="风险约束指标"
      >
        <header>
          <span className="dashboard-terminal-eyebrow">风险约束</span>
          <h3>风险约束指标</h3>
        </header>
        <div className="dashboard-terminal-risk-stack__items">
          {overview.riskConstraints.map((card) => (
            <RiskConstraint key={card.id} card={card} />
          ))}
        </div>
      </aside>
    </section>
  );
}
