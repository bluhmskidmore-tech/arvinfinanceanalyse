import type { DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";

type DashboardJudgmentStripProps = {
  viewModel: DashboardCockpitHomeViewModel;
};

export function DashboardJudgmentStrip({ viewModel }: DashboardJudgmentStripProps) {
  const { reportDate, judgment } = viewModel;
  const question = reportDate
    ? `报告日 ${reportDate}：组合规模与收益方向是否支持当前配置？`
    : "组合规模与收益方向是否支持当前配置？";

  return (
    <section
      data-testid="dashboard-judgment-strip"
      className="dashboard-cockpit-judgment-hero"
      aria-label="今日经营判断"
    >
      <div className="dashboard-cockpit-judgment-hero__top">
        <div className="dashboard-cockpit-judgment-hero__copy">
          <span className="dashboard-cockpit-judgment-hero__eyebrow">本日判断</span>
          <h2 className="dashboard-cockpit-judgment-hero__title">
            {reportDate ? `报告日 ${reportDate} 经营快照` : "今日经营快照"}
          </h2>
          <p className="dashboard-cockpit-judgment-hero__question">{question}</p>
        </div>
        {reportDate ? (
          <div className="dashboard-cockpit-judgment-hero__meta">
            报告日 <strong>{reportDate}</strong>
          </div>
        ) : null}
      </div>
      <p className="dashboard-cockpit-judgment-hero__conclusion">{judgment.conclusion}</p>
    </section>
  );
}
