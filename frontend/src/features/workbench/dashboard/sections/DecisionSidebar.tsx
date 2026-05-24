import { Link } from "react-router-dom";

import type { DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";

type DecisionSidebarProps = {
  viewModel: DashboardCockpitHomeViewModel;
  isLiveDataFallback?: boolean;
};

export function DecisionSidebar({ viewModel, isLiveDataFallback = false }: DecisionSidebarProps) {
  return (
    <aside
      data-testid="dashboard-ai-decision-cabin"
      className="dashboard-cockpit-panel dashboard-cockpit-decision-sidebar dashboard-terminal-ai-cabin"
      aria-label="AI 决策舱"
    >
      <div data-testid="dashboard-decision-sidebar" className="dashboard-terminal-ai-cabin__inner">
      <header className="dashboard-cockpit-panel__head dashboard-cockpit-decision-sidebar__head">
        <span className="dashboard-cockpit-panel__eyebrow">AI 辅助决策</span>
        <h2 className="dashboard-cockpit-panel__title">AI 决策舱</h2>
      </header>

      <div className="dashboard-cockpit-panel__body dashboard-cockpit-decision-sidebar__body">
        <div className="dashboard-cockpit-decision-sidebar__cards">
        {viewModel.aiDecisionSummary.map((section, index) => (
          <a
            key={section.id}
            href={section.href ?? "#"}
            className="dashboard-cockpit-decision-card"
            data-tone={section.tone ?? "neutral"}
            data-testid={`dashboard-decision-card-link-${section.id}`}
            aria-label={`${section.title}，定位到${
              section.targetId === "dashboard-home-market-section"
                ? "市场数据区"
                : section.targetId === "dashboard-home-portfolio-section"
                  ? "组合概览或暴露证据"
                  : "风险与预警处理区"
            }`}
          >
            <span className="dashboard-cockpit-decision-card__index dashboard-cockpit-tabular">
              {index + 1}
            </span>
            <div className="dashboard-cockpit-decision-card__content">
              <div className="dashboard-cockpit-decision-card__title-row">
                <strong>{section.title}</strong>
                {section.badge ? (
                  <span className="dashboard-cockpit-decision-card__badge">{section.badge}</span>
                ) : null}
              </div>
              {section.evidenceLabel || section.sourceLabel || section.statusLabel ? (
                <div className="dashboard-cockpit-decision-card__meta">
                  {section.evidenceLabel ? <span>{section.evidenceLabel}</span> : null}
                  {section.sourceLabel ? <span>{section.sourceLabel}</span> : null}
                  {section.statusLabel ? <em>{section.statusLabel}</em> : null}
                </div>
              ) : null}
              {section.body ? <p>{section.body}</p> : null}
            </div>
          </a>
        ))}
        </div>

        {viewModel.showDataWarning || isLiveDataFallback ? (
          <details
            data-testid="dashboard-sidebar-data-warning"
            className="dashboard-cockpit-decision-sidebar__todo"
            open={isLiveDataFallback || viewModel.dataWarningMessages.length > 0}
          >
            <summary>
              <span>首屏状态</span>
              <em>
                {isLiveDataFallback
                  ? "已回落到本地模拟数据"
                  : `${viewModel.dataWarningMessages.length} 条提示`}
              </em>
            </summary>
            <div className="dashboard-cockpit-decision-sidebar__todo-body">
              {isLiveDataFallback ? (
                <p>实时数据源当前不可用，页面已自动切换为本地模拟数据展示。</p>
              ) : null}
              {viewModel.dataWarningMessages.map((message) => (
                <p key={message}>{message}</p>
              ))}
            </div>
          </details>
        ) : null}

        <Link to="/decision-items" className="dashboard-cockpit-decision-sidebar__cta">
          生成完整经营报告 →
        </Link>
      </div>
      </div>
    </aside>
  );
}
