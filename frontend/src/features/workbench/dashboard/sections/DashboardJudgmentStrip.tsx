import { Link } from "react-router-dom";

import { tabularNumsStyle } from "../../../../theme/designSystem";
import type { DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";

type DashboardJudgmentStripProps = {
  viewModel: DashboardCockpitHomeViewModel;
};

export function DashboardJudgmentStrip({ viewModel }: DashboardJudgmentStripProps) {
  const isMock = viewModel.dataSource === "mock";

  return (
    <section
      data-testid="dashboard-judgment-strip"
      className="dashboard-cockpit-judgment-bar"
      aria-label="今日经营判断"
    >
      <div className="dashboard-cockpit-judgment-bar__copy">
        <span className="dashboard-cockpit-judgment-bar__rail" aria-hidden="true" />
        <div>
          <h2>今日经营判断</h2>
          <p>
            利率上行拖累估值，信用利差收窄提供对冲，组合久期小幅上升，需关注 Top5
            集中度和久期超限账户。
          </p>
        </div>
      </div>
      <div className="dashboard-cockpit-judgment-bar__actions">
        <span className="dashboard-cockpit-judgment-bar__badge dashboard-cockpit-judgment-bar__badge--ok">
          估值已完成
        </span>
        <Link
          to="/decision-items"
          className="dashboard-cockpit-judgment-bar__badge dashboard-cockpit-judgment-bar__badge--warn"
        >
          风险待复核 <strong style={tabularNumsStyle}>3</strong>
        </Link>
        <span className="dashboard-cockpit-judgment-bar__badge">
          {isMock ? "数据待同步" : "数据已更新"} {viewModel.headerStatus.dataUpdatedAt}
        </span>
      </div>
    </section>
  );
}
