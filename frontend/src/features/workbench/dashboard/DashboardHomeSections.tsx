import type { ReactNode } from "react";

import type { VerdictPayload } from "../../../api/contracts";
import type {
  DashboardAlert,
  DashboardCalendarPanelState,
  DashboardHubCalendarItem,
  DashboardHubTask,
} from "./DashboardOverviewSections";
import type { GovernancePill } from "./GovernancePills";

function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

function toneClass(tone: VerdictPayload["tone"]): string {
  return `dashboard-tone-${tone}`;
}

function governanceToneClass(tone: GovernancePill["tone"]): string {
  return `dashboard-governance-tone-${tone}`;
}

function severityClass(severity: DashboardAlert["severity"]): string {
  return `dashboard-severity-${severity}`;
}

function priorityClass(priority: DashboardHubTask["priority"]): string {
  return `dashboard-priority-${priority}`;
}

function calendarStatusClass(status: DashboardCalendarPanelState["status"]): string {
  return `dashboard-calendar-status-${status}`;
}

function severityLabel(severity: DashboardAlert["severity"]): string {
  if (severity === "high") return "高";
  if (severity === "medium") return "中";
  return "低";
}

function priorityLabel(priority: DashboardHubTask["priority"]): string {
  if (priority === "high") return "高";
  if (priority === "medium") return "中";
  return "低";
}

function calendarStatusLabel(status: DashboardCalendarPanelState["status"]): string {
  if (status === "ready") return "就绪";
  if (status === "loading") return "载入中";
  if (status === "no-high-medium") return "无高/中事件";
  if (status === "error") return "加载失败";
  return "无数据";
}

function splitHint(hint: string | undefined): { lead: string; rest: string | null } | null {
  const trimmed = hint?.trim();
  if (!trimmed) {
    return null;
  }
  const [lead, ...rest] = trimmed.split(" / ");
  return {
    lead,
    rest: rest.length > 0 ? rest.join(" / ") : null,
  };
}

function safeTaskDue(task: DashboardHubTask): string {
  return task.due?.trim() || "无到期时间";
}

function safeCalendarDate(time: string): string {
  const trimmed = time.trim();
  if (trimmed.length >= 10) {
    return trimmed.slice(5);
  }
  return trimmed;
}

function DashboardSectionHeader({
  eyebrow,
  title,
  extra,
}: {
  eyebrow: string;
  title: string;
  extra?: ReactNode;
}) {
  return (
    <div className="dashboard-home-section-header">
      <div className="dashboard-home-section-heading">
        <span className="dashboard-home-section-eyebrow">{eyebrow}</span>
        <h2 className="dashboard-home-section-title">{title}</h2>
      </div>
      {extra}
    </div>
  );
}

export type DashboardHomeSemanticSectionProps = {
  testId?: string;
  eyebrow: string;
  title: string;
  description?: ReactNode;
  className?: string;
  bodyClassName?: string;
  headerExtra?: ReactNode;
  children: ReactNode;
};

export function DashboardHomeSemanticSection({
  testId,
  eyebrow,
  title,
  description,
  className,
  bodyClassName,
  headerExtra,
  children,
}: DashboardHomeSemanticSectionProps) {
  return (
    <section
      data-testid={testId}
      className={cx("dashboard-home-semantic-section", className)}
    >
      <div className="dashboard-home-semantic-section__header">
        <DashboardSectionHeader eyebrow={eyebrow} title={title} extra={headerExtra} />
        {description ? (
          <p className="dashboard-home-muted dashboard-home-semantic-section__description">
            {description}
          </p>
        ) : null}
      </div>
      <div className={cx("dashboard-home-semantic-section__body", bodyClassName)}>{children}</div>
    </section>
  );
}

export type DashboardJudgmentBandProps = {
  verdict: VerdictPayload;
  eyebrow?: string;
  title?: string;
  className?: string;
};

export function DashboardJudgmentBand({
  verdict,
  eyebrow = "今日判断",
  title = "今日判断",
  className,
}: DashboardJudgmentBandProps) {
  return (
    <section
      data-testid="dashboard-judgment-band"
      className={cx("dashboard-home-panel dashboard-judgment-band", className)}
    >
      <DashboardSectionHeader
        eyebrow={eyebrow}
        title={title}
        extra={
          <span
            aria-label={`判断状态 ${verdict.tone}`}
            className={cx("dashboard-home-tone-dot", toneClass(verdict.tone))}
          />
        }
      />
      <p className={cx("dashboard-judgment-band__conclusion", toneClass(verdict.tone))}>
        {verdict.conclusion}
      </p>
      {verdict.reasons.length > 0 ? (
        <div className="dashboard-judgment-band__reasons">
          {verdict.reasons.map((reason) => (
            <article
              key={`${reason.label}-${reason.value}`}
              className="dashboard-home-inset dashboard-judgment-band__reason"
            >
              <span
                aria-hidden="true"
                className={cx("dashboard-home-dot", toneClass(reason.tone))}
              />
              <div className="dashboard-judgment-band__reason-body">
                <strong className="dashboard-home-strong">{reason.label}</strong>
                <span className="dashboard-home-value">{reason.value}</span>
                <p className="dashboard-home-muted">{reason.detail}</p>
              </div>
            </article>
          ))}
        </div>
      ) : null}
      {verdict.suggestions.length > 0 ? (
        <div className="dashboard-judgment-band__suggestions">
          <p className="dashboard-home-copy-strong">建议动作：</p>
          <ul className="dashboard-home-list">
            {verdict.suggestions.map((suggestion, index) => (
              <li key={`${suggestion.text}-${index}`}>
                {suggestion.link ? (
                  <a className="dashboard-home-link" href={suggestion.link}>
                    {suggestion.text}
                  </a>
                ) : (
                  suggestion.text
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

export type DashboardKpiRibbonProps = {
  items: readonly GovernancePill[];
  eyebrow?: string;
  title?: string;
  className?: string;
};

export function DashboardKpiRibbon({
  items,
  eyebrow = "关键指标",
  title = "核心状态",
  className,
}: DashboardKpiRibbonProps) {
  return (
    <section
      data-testid="dashboard-kpi-ribbon"
      className={cx("dashboard-home-panel dashboard-kpi-ribbon", className)}
    >
      <DashboardSectionHeader eyebrow={eyebrow} title={title} />
      <div data-testid="dashboard-kpi-ribbon-items" className="dashboard-kpi-ribbon__items">
        {items.map((pill) => (
          <DashboardKpiRibbonItem key={pill.id} pill={pill} />
        ))}
      </div>
    </section>
  );
}

function DashboardKpiRibbonItem({ pill }: { pill: GovernancePill }) {
  const hint = splitHint(pill.hint);

  return (
    <article
      data-testid={`dashboard-kpi-ribbon-${pill.id}`}
      className={cx("dashboard-home-inset dashboard-kpi-ribbon__item", governanceToneClass(pill.tone))}
    >
      <div className="dashboard-kpi-ribbon__item-head">
        <span className="dashboard-home-muted-label">{pill.label}</span>
        <span className="dashboard-home-badge">{pill.value}</span>
      </div>
      {hint ? (
        <p className="dashboard-home-muted">
          <span>{hint.lead}</span>
          {hint.rest ? <span> / {hint.rest}</span> : null}
        </p>
      ) : null}
    </article>
  );
}

export type DashboardAnalysisGridProps = {
  alerts: readonly DashboardAlert[];
  eyebrow?: string;
  title?: string;
  emptyMessage?: string;
  className?: string;
};

export function DashboardAnalysisGrid({
  alerts,
  eyebrow = "利率 / 曲线 / 信用 / 资金",
  title = "分析关注",
  emptyMessage = "暂无需要优先处置的关注项。",
  className,
}: DashboardAnalysisGridProps) {
  return (
    <section
      data-testid="dashboard-analysis-grid"
      className={cx("dashboard-home-panel dashboard-analysis-grid", className)}
    >
      <DashboardSectionHeader eyebrow={eyebrow} title={title} />
      {alerts.length === 0 ? (
        <p className="dashboard-home-muted">{emptyMessage}</p>
      ) : (
        <div className="dashboard-analysis-grid__items">
          {alerts.map((alert) => (
            <article
              key={alert.id}
              data-testid={`dashboard-analysis-grid-item-${alert.id}`}
              className={cx("dashboard-home-inset dashboard-analysis-grid__item", severityClass(alert.severity))}
            >
              <div className="dashboard-analysis-grid__item-head">
                <strong className="dashboard-home-strong">{alert.title}</strong>
                <span className="dashboard-home-badge">{severityLabel(alert.severity)}</span>
              </div>
              <p className="dashboard-home-muted">{alert.detail}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export type DashboardStructureRiskFocusData = {
  tasks: readonly DashboardHubTask[];
  calendarItems: readonly DashboardHubCalendarItem[];
  calendarState: DashboardCalendarPanelState;
};

export type DashboardStructureRiskFocusProps = {
  focus: DashboardStructureRiskFocusData;
  eyebrow?: string;
  title?: string;
  className?: string;
};

export function DashboardStructureRiskFocus({
  focus,
  eyebrow = "结构 / 风险 / 日程",
  title = "今日关注",
  className,
}: DashboardStructureRiskFocusProps) {
  const tasks = focus.tasks.slice(0, 4);

  return (
    <section
      data-testid="dashboard-structure-risk-focus"
      className={cx("dashboard-home-panel dashboard-structure-risk-focus", className)}
    >
      <DashboardSectionHeader eyebrow={eyebrow} title={title} />
      <div className="dashboard-structure-risk-focus__grid">
        <section className="dashboard-home-inset dashboard-structure-risk-focus__panel dashboard-structure-risk-focus__panel--tasks">
          <h3 className="dashboard-home-subtitle">交易与复核要点</h3>
          {tasks.length === 0 ? (
            <p className="dashboard-home-muted">当前暂无需要优先处置的复核事项。</p>
          ) : (
            <div className="dashboard-structure-risk-focus__task-list">
              {tasks.map((task) => (
                <article key={task.id} className="dashboard-structure-risk-focus__task">
                  <div className="dashboard-structure-risk-focus__row">
                    <strong className="dashboard-home-strong">{task.title}</strong>
                    <span className={cx("dashboard-home-rank", priorityClass(task.priority))}>
                      {priorityLabel(task.priority)}
                    </span>
                  </div>
                  <div className="dashboard-home-muted">{safeTaskDue(task)}</div>
                </article>
              ))}
            </div>
          )}
        </section>
        <section className="dashboard-home-inset dashboard-structure-risk-focus__panel dashboard-structure-risk-focus__panel--calendar">
          <div className="dashboard-structure-risk-focus__row">
            <h3 className="dashboard-home-subtitle">关键事件日历</h3>
            <span className={cx("dashboard-home-badge", calendarStatusClass(focus.calendarState.status))}>
              {calendarStatusLabel(focus.calendarState.status)}
            </span>
          </div>
          {focus.calendarState.message ? (
            <p className="dashboard-home-muted">{focus.calendarState.message}</p>
          ) : null}
          <div className="dashboard-structure-risk-focus__calendar-list">
            {focus.calendarItems.map((item) => (
              <article key={item.id} className="dashboard-structure-risk-focus__calendar-item">
                <div className="dashboard-structure-risk-focus__row">
                  <strong className="dashboard-home-strong">{item.title}</strong>
                  <span className="dashboard-home-date">{safeCalendarDate(item.time)}</span>
                </div>
                <div className="dashboard-home-muted">{item.kind}</div>
              </article>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}
