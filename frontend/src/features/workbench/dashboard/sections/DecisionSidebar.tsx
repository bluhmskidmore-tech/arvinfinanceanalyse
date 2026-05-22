import { tabularNumsStyle } from "../../../../theme/designSystem";
import type { DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";

type DecisionSidebarProps = {
  viewModel: DashboardCockpitHomeViewModel;
};

function splitImprovementNote(note: string): { title: string; body: string } {
  const [title, ...rest] = note.split("：");
  return {
    title: title?.trim() || note,
    body: rest.join("：").trim(),
  };
}

export function DecisionSidebar({ viewModel }: DecisionSidebarProps) {
  const dataStatus =
    viewModel.dataSource === "mock" ? "数据使用本地模拟数据" : "部分指标使用本地模拟数据兜底";

  return (
    <aside
      data-testid="dashboard-improvement-notes"
      className="dashboard-cockpit-decision-sidebar"
      aria-label="首页改造重点"
    >
      <header className="dashboard-cockpit-decision-sidebar__head">
        <span>优化说明</span>
        <h2>首页改造重点</h2>
      </header>

      <div className="dashboard-cockpit-decision-sidebar__cards">
        {viewModel.improvementNotes.map((note, index) => {
          const item = splitImprovementNote(note);
          return (
            <article
              key={note}
              className="dashboard-cockpit-decision-card"
              data-tone={index === 2 ? "warning" : "neutral"}
            >
              <span className="dashboard-cockpit-decision-card__index" style={tabularNumsStyle}>
                {index + 1}
              </span>
              <div>
                <strong>{item.title}</strong>
                {item.body ? <p>{item.body}</p> : null}
              </div>
            </article>
          );
        })}
      </div>

      <section className="dashboard-cockpit-decision-sidebar__todo">
        <h3>首屏状态</h3>
        <p>
          已固定核心 KPI、市场脉搏、组合概览、今日归因和风险预警。
        </p>
      </section>

      <section className="dashboard-cockpit-decision-sidebar__data">
        <h3>数据说明</h3>
        <p>数据来源：交易系统、估值系统、风控系统。</p>
        <p>
          更新时间：{viewModel.reportDate} {viewModel.headerStatus.dataUpdatedAt}
        </p>
        <span>{dataStatus}</span>
      </section>
    </aside>
  );
}
