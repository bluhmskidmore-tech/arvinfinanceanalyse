import { Link } from "react-router-dom";

import type { DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";
import { BalanceSummary } from "./BalanceSummary";
import { ExposureTable } from "./ExposureTable";

type SecondaryAnalysisSectionProps = {
  viewModel: DashboardCockpitHomeViewModel;
};

export function SecondaryAnalysisSection({ viewModel }: SecondaryAnalysisSectionProps) {
  return (
    <section
      data-testid="dashboard-secondary-analysis"
      className="dashboard-terminal-secondary-analysis"
      aria-label="下方二级分析区"
    >
      <ExposureTable rows={viewModel.exposureRows} />
      <BalanceSummary metrics={viewModel.balanceMetrics} />
      <section
        data-testid="dashboard-terminal-action-bar"
        className="dashboard-terminal-action-bar"
        aria-label="终端快捷动作"
      >
        <header>
          <span className="dashboard-terminal-eyebrow">Terminal Actions</span>
          <h2>快速钻取</h2>
        </header>
        <div data-testid="dashboard-terminal-quick-drilldown" className="dashboard-terminal-action-bar__items">
          {viewModel.quickDrilldowns.map((item) => {
            const pending = item.path === "#";
            const testId =
              item.id === "trades" ? "dashboard-drill-trades" : `dashboard-drill-${item.id}`;
            if (pending) {
              return (
                <a
                  key={item.id}
                  href="#"
                  data-testid={testId}
                  className="dashboard-terminal-action"
                  onClick={(event) => event.preventDefault()}
                >
                  <strong>{item.label}</strong>
                  <span>待开放</span>
                </a>
              );
            }
            return (
              <Link
                key={item.id}
                to={item.path}
                data-testid={testId}
                className="dashboard-terminal-action"
              >
                <strong>{item.label}</strong>
                <span>Enter →</span>
              </Link>
            );
          })}
        </div>
        {viewModel.usesStaticQuickDrilldown ? (
          <p>固定导航入口；同日摘要数字请进入专题页查看。</p>
        ) : null}
      </section>
    </section>
  );
}
