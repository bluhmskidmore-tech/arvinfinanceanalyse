import { Link } from "react-router-dom";

import { tabularNumsStyle } from "../../../theme/designSystem";
import type { DashboardReviewAlert } from "../dashboard/DashboardOverviewSections";

function actionQueueTypeLabel(alert: DashboardReviewAlert): string {
  if (alert.id === "mock-mode" || alert.id.startsWith("attention-")) {
    return "治理管理";
  }
  if (alert.id === "partial-note") {
    return "数据完整性";
  }
  if (alert.id.startsWith("metric-")) {
    return "经营监控";
  }
  return "风险预警";
}

function actionQueuePriorityLabel(severity: DashboardReviewAlert["severity"]): string {
  if (severity === "high") {
    return "高";
  }
  if (severity === "medium") {
    return "中";
  }
  return "低";
}

function actionQueueOwnerLabel(alert: DashboardReviewAlert): string {
  if (alert.id === "mock-mode" || alert.id.startsWith("attention-")) {
    return "治理负责人";
  }
  if (alert.id.startsWith("metric-")) {
    return "经营分析";
  }
  return "值班复核";
}

function actionQueueStatus(alert: DashboardReviewAlert): {
  label: string;
  status: "blocked" | "pending" | "ready";
} {
  if (alert.severity === "high") {
    return { label: "需处理", status: "blocked" };
  }
  if (alert.severity === "medium") {
    return { label: "待复核", status: "pending" };
  }
  return { label: "观察中", status: "ready" };
}

export function DashboardActionQueue({
  alerts,
  effectiveReportDate,
}: {
  alerts: readonly DashboardReviewAlert[];
  effectiveReportDate: string;
}) {
  const queueRows = alerts.slice(0, 5);
  const highCount = alerts.filter((alert) => alert.severity === "high").length;
  const mediumCount = alerts.filter((alert) => alert.severity === "medium").length;
  const lowCount = alerts.filter((alert) => alert.severity === "low").length;
  const dueLabel = effectiveReportDate || "最新报告日";

  return (
    <section
      data-testid="dashboard-action-queue"
      className="dashboard-action-queue dashboard-home-panel"
      aria-label="待处理事项"
    >
      <header className="dashboard-action-queue__toolbar">
        <div className="dashboard-home-section-heading">
          <span className="dashboard-home-section-eyebrow">复核队列</span>
          <h2 className="dashboard-home-section-title">待处理事项</h2>
        </div>
        <div className="dashboard-action-queue__filters" role="list" aria-label="事项优先级">
          <span className="dashboard-action-queue__filter" role="listitem" data-active="true">
            全部 {alerts.length}
          </span>
          <span className="dashboard-action-queue__filter" role="listitem">
            高优先级 {highCount}
          </span>
          <span className="dashboard-action-queue__filter" role="listitem">
            中优先级 {mediumCount}
          </span>
          <span className="dashboard-action-queue__filter" role="listitem">
            观察 {lowCount}
          </span>
        </div>
      </header>
      <div
        className="dashboard-action-queue__table"
        data-testid="dashboard-action-queue-table"
        role="table"
        aria-label="待处理事项列表"
      >
        <div className="dashboard-action-queue__row" role="row">
          <span role="columnheader">#</span>
          <span role="columnheader">事项标题</span>
          <span role="columnheader">类型</span>
          <span role="columnheader">优先级</span>
          <span role="columnheader">来源</span>
          <span role="columnheader">责任人</span>
          <span role="columnheader">截至日期</span>
          <span role="columnheader">状态</span>
          <span role="columnheader">操作</span>
        </div>
        {queueRows.length > 0 ? (
          queueRows.map((alert, index) => {
            const status = actionQueueStatus(alert);
            return (
              <div key={alert.id} className="dashboard-action-queue__row" role="row">
                <span role="cell" style={tabularNumsStyle}>
                  {String(index + 1).padStart(2, "0")}
                </span>
                <strong role="cell" title={alert.title}>
                  {alert.title}
                </strong>
                <span role="cell">{actionQueueTypeLabel(alert)}</span>
                <span
                  className="dashboard-action-queue__priority"
                  data-priority={alert.severity}
                  role="cell"
                >
                  {actionQueuePriorityLabel(alert.severity)}
                </span>
                <span role="cell">{alert.sourceLabel}</span>
                <span role="cell">{actionQueueOwnerLabel(alert)}</span>
                <span role="cell" style={tabularNumsStyle}>
                  {alert.severity === "high" ? "今日" : dueLabel}
                </span>
                <span
                  className="dashboard-action-queue__status"
                  data-status={status.status}
                  role="cell"
                >
                  {status.label}
                </span>
                <span role="cell">
                  <Link className="dashboard-action-queue__action" to={alert.actionTo}>
                    {alert.actionLabel}
                  </Link>
                </span>
              </div>
            );
          })
        ) : (
          <div className="dashboard-action-queue__row" role="row">
            <span role="cell" style={tabularNumsStyle}>
              00
            </span>
            <strong role="cell">暂无待处理事项</strong>
            <span role="cell">经营监控</span>
            <span className="dashboard-action-queue__priority" data-priority="low" role="cell">
              低
            </span>
            <span role="cell">首页快照</span>
            <span role="cell">值班复核</span>
            <span role="cell" style={tabularNumsStyle}>
              {dueLabel}
            </span>
            <span className="dashboard-action-queue__status" data-status="ready" role="cell">
              已清空
            </span>
            <span role="cell">
              <Link className="dashboard-action-queue__action" to="/decision-items">
                查看
              </Link>
            </span>
          </div>
        )}
      </div>
    </section>
  );
}
