import type { DashboardAlert, DashboardHubTask } from "./DashboardOverviewSections";

const priorityRank: Record<DashboardHubTask["priority"], number> = {
  high: 0,
  medium: 1,
  low: 2,
};

function mapAlertToTodo(alert: DashboardAlert): DashboardHubTask {
  const action = alert.severity === "high" ? "复核" : "确认";
  const due = alert.severity === "high" ? "今日复核" : "今日确认";

  return {
    id: `todo-${alert.id}`,
    title: `${action}：${alert.title}`,
    due: `${due} · 来源：治理预警`,
    priority: alert.severity,
  };
}

export function buildDashboardTodoTasksFromAlerts(
  alerts: DashboardAlert[],
  limit = 4,
): DashboardHubTask[] {
  return alerts
    .filter((alert) => alert.severity === "high" || alert.severity === "medium")
    .map((alert, index) => ({
      task: mapAlertToTodo(alert),
      index,
    }))
    .sort(
      (left, right) =>
        priorityRank[left.task.priority] - priorityRank[right.task.priority] ||
        left.index - right.index,
    )
    .map(({ task }) => task)
    .slice(0, limit);
}
