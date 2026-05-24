import type { DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";

type DashboardJudgmentStripProps = {
  viewModel: DashboardCockpitHomeViewModel;
};

function usefulDecisionText(value: string): string | null {
  const text = value.trim();
  if (!text || text === "—" || text === "待同步" || text === "口径待确认") {
    return null;
  }
  return text;
}

export function DashboardJudgmentStrip({ viewModel }: DashboardJudgmentStripProps) {
  const { headerStatus, judgment, decisionSpine } = viewModel;
  const evidenceSummary = [
    usefulDecisionText(decisionSpine.portfolioImpact),
    usefulDecisionText(decisionSpine.riskConstraint),
  ]
    .filter(Boolean)
    .join("；");
  const actionSummary = usefulDecisionText(decisionSpine.nextAction);
  const valuationToneClass =
    headerStatus.valuationTone === "ok"
      ? "dashboard-cockpit-judgment-hero__badge--ok"
      : "dashboard-cockpit-judgment-hero__badge--muted";

  return (
    <section
      data-testid="dashboard-judgment-strip"
      className="dashboard-cockpit-judgment-hero"
      aria-label="今日经营判断"
    >
      <div className="dashboard-cockpit-judgment-hero__copy">
        <span className="dashboard-cockpit-judgment-hero__eyebrow">今日经营判断</span>
        <p className="dashboard-cockpit-judgment-hero__conclusion">{judgment.conclusion}</p>
        {evidenceSummary || actionSummary ? (
          <p className="dashboard-cockpit-judgment-hero__directive">
            {evidenceSummary ? `证据：${evidenceSummary}` : null}
            {evidenceSummary && actionSummary ? "；" : null}
            {actionSummary ? `动作：${actionSummary}` : null}
          </p>
        ) : null}
      </div>
      <div className="dashboard-cockpit-judgment-hero__evidence" aria-label="经营判断证据链">
        {decisionSpine.rail.map((item) => (
          <a
            key={item.id}
            href={item.href}
            className="dashboard-cockpit-judgment-hero__evidence-item"
            data-tone={item.tone}
            data-testid={`dashboard-judgment-evidence-link-${item.id}`}
            aria-label={`${item.label}，定位到${
              item.id === "market-focus"
                ? "市场数据区"
                : item.id === "portfolio-impact"
                  ? "组合概览或暴露证据"
                  : "风险与预警处理区"
            }`}
          >
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </a>
        ))}
      </div>
      <div className="dashboard-cockpit-judgment-hero__actions" aria-label="经营状态">
        {headerStatus.valuationLabel ? (
          <span className={`dashboard-cockpit-judgment-hero__badge ${valuationToneClass}`}>
            {headerStatus.valuationLabel}
          </span>
        ) : null}
        {headerStatus.showRiskReview ? (
          <span className="dashboard-cockpit-judgment-hero__badge dashboard-cockpit-judgment-hero__badge--warn dashboard-cockpit-tabular">
            风险待复核 {headerStatus.riskReviewCount}
          </span>
        ) : null}
        <span className="dashboard-cockpit-judgment-hero__badge dashboard-cockpit-judgment-hero__badge--info dashboard-cockpit-tabular">
          {headerStatus.dataSyncPrefix} {headerStatus.dataUpdatedAt}
        </span>
      </div>
    </section>
  );
}
