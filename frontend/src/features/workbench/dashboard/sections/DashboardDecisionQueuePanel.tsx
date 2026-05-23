import { Link } from "react-router-dom";

import type { DashboardRiskTodoVM } from "../dashboardCockpitHomeModel";

type DashboardDecisionQueuePanelProps = {
  todos: readonly DashboardRiskTodoVM[];
  showDataWarning?: boolean;
  dataWarningMessages?: readonly string[];
  isLiveDataFallback?: boolean;
};

function priorityClass(priority: string): string {
  if (priority === "高") return "dashboard-cockpit-queue__pill dashboard-cockpit-queue__pill--high";
  if (priority === "中") return "dashboard-cockpit-queue__pill dashboard-cockpit-queue__pill--medium";
  return "dashboard-cockpit-queue__pill";
}

export function DashboardDecisionQueuePanel({
  todos,
  showDataWarning = false,
  dataWarningMessages = [],
  isLiveDataFallback = false,
}: DashboardDecisionQueuePanelProps) {
  const rows = todos.slice(0, 3);

  return (
    <section
      data-testid="dashboard-improvement-notes"
      className="dashboard-cockpit-panel dashboard-cockpit-panel--queue"
      aria-label="待决策事项"
    >
      <header className="dashboard-cockpit-panel__head">
        <span className="dashboard-cockpit-panel__eyebrow">待办</span>
        <h2 className="dashboard-cockpit-panel__title">待决策事项</h2>
      </header>
      <div className="dashboard-cockpit-panel__body dashboard-cockpit-panel__body--flush">
        <table className="dashboard-cockpit-queue">
          <thead>
            <tr>
              <th scope="col">等级</th>
              <th scope="col">事项</th>
              <th scope="col">状态</th>
              <th scope="col">动作</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={4} className="dashboard-cockpit-queue__empty">
                  当前无待决策事项
                </td>
              </tr>
            ) : (
              rows.map((todo) => (
                <tr key={todo.id}>
                  <td>
                    <span className={priorityClass(todo.priority)}>{todo.priority}</span>
                  </td>
                  <td>
                    <strong>{todo.title}</strong>
                  </td>
                  <td>{todo.status}</td>
                  <td>
                    <Link to={todo.path} className="dashboard-cockpit-queue__link">
                      复核
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {showDataWarning || isLiveDataFallback ? (
          <section
            data-testid="dashboard-queue-data-warning"
            className="dashboard-cockpit-queue__status"
          >
            {isLiveDataFallback ? (
              <p>实时数据源当前不可用，页面已自动切换为本地模拟数据展示。</p>
            ) : null}
            {dataWarningMessages.map((message) => (
              <p key={message}>{message}</p>
            ))}
          </section>
        ) : null}

        <div className="dashboard-cockpit-queue__foot">
          <Link to="/decision-items" className="dashboard-cockpit-queue__cta">
            进入决策工作台 →
          </Link>
        </div>
      </div>
    </section>
  );
}
