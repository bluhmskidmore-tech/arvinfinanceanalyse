import { Link } from "react-router-dom";

import { tabularNumsStyle } from "../../../../theme/designSystem";
import type { DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";

type DecisionSidebarProps = {
  viewModel: DashboardCockpitHomeViewModel;
  isLiveDataFallback?: boolean;
};

export function DecisionSidebar({ viewModel, isLiveDataFallback = false }: DecisionSidebarProps) {
  return (
    <aside
      data-testid="dashboard-decision-sidebar"
      className="dashboard-cockpit-panel dashboard-cockpit-decision-sidebar"
      aria-label="今日决策侧舱"
    >
      <header className="dashboard-cockpit-panel__head dashboard-cockpit-decision-sidebar__head">
        <span className="dashboard-cockpit-panel__eyebrow">决策侧舱</span>
        <h2 className="dashboard-cockpit-panel__title">今日决策侧舱</h2>
      </header>

      <div className="dashboard-cockpit-panel__body dashboard-cockpit-decision-sidebar__body">
        <div className="dashboard-cockpit-decision-sidebar__cards">
        {viewModel.decisionSidebarSections.map((section, index) => (
          <article
            key={section.id}
            className="dashboard-cockpit-decision-card"
            data-tone={section.tone ?? "neutral"}
          >
            <span className="dashboard-cockpit-decision-card__index" style={tabularNumsStyle}>
              {index + 1}
            </span>
            <div>
              <div className="dashboard-cockpit-decision-card__title-row">
                <strong>{section.title}</strong>
                {section.badge ? (
                  <span className="dashboard-cockpit-decision-card__badge">{section.badge}</span>
                ) : null}
              </div>
              {section.body ? <p>{section.body}</p> : null}
            </div>
          </article>
        ))}
        </div>

        {viewModel.showDataWarning || isLiveDataFallback ? (
          <section
            data-testid="dashboard-sidebar-data-warning"
            className="dashboard-cockpit-decision-sidebar__todo"
          >
            <h3>首屏状态</h3>
            {isLiveDataFallback ? (
              <p>实时数据源当前不可用，页面已自动切换为本地模拟数据展示。</p>
            ) : null}
            {viewModel.dataWarningMessages.map((message) => (
              <p key={message}>{message}</p>
            ))}
          </section>
        ) : null}

        <Link to="/decision-items" className="dashboard-cockpit-decision-sidebar__cta">
          进入决策工作台 →
        </Link>
      </div>
    </aside>
  );
}
