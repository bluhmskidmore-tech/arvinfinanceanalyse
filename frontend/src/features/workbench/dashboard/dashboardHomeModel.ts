import type { ResultMeta, ResearchCalendarEvent, VerdictPayload } from "../../../api/contracts";
import type { DashboardOverviewMetricVM } from "../../executive-dashboard/adapters/executiveDashboardAdapter";
import type {
  DashboardAlert,
  DashboardCalendarPanelState,
  DashboardHeroMetric,
  DashboardHubCalendarItem,
  DashboardHubTask,
} from "./DashboardOverviewSections";
import type { GovernancePill } from "./GovernancePills";
import { buildDashboardTodoTasksFromAlerts } from "./dashboardTodoModel";
import { buildDashboardKeyCalendarModel } from "./keyCalendarModel";

export const DASHBOARD_HOME_HERO_METRIC_LIMIT = 4;
export const DASHBOARD_HOME_ALERT_LIMIT = 4;
export const DASHBOARD_HOME_METRIC_ALERT_LIMIT = 3;
export const DASHBOARD_HOME_CALENDAR_LIMIT = 4;
export const DASHBOARD_HOME_FOCUS_TASK_LIMIT = 4;

export type DashboardHomeModelInput = {
  metrics?: readonly DashboardOverviewMetricVM[] | null;
  baseVerdict?: VerdictPayload | null;
  overviewMeta?: ResultMeta | null;
  attributionMeta?: ResultMeta | null;
  requestedReportDate?: string;
  snapshotReportDate?: string;
  snapshotMode?: string;
  snapshotDomainsMissing?: readonly string[] | null;
  isSnapshotLoading: boolean;
  calendarEvents?: readonly ResearchCalendarEvent[] | null;
  calendarIsLoading: boolean;
  calendarIsError: boolean;
  isMockMode: boolean;
  heroMetricLimit?: number;
  alertLimit?: number;
  metricAlertLimit?: number;
  calendarLimit?: number;
  focusTaskLimit?: number;
};

export type DashboardHomeKpiRibbonItem = GovernancePill;

export type DashboardHomeFocus = {
  tasks: DashboardHubTask[];
  calendarItems: DashboardHubCalendarItem[];
  calendarState: DashboardCalendarPanelState;
};

export type DashboardHomeModel = {
  effectiveReportDate: string;
  attentionItems: string[];
  snapshotPartialNote: string | null;
  kpiRibbon: DashboardHomeKpiRibbonItem[];
  judgment: VerdictPayload;
  heroMetrics: DashboardHeroMetric[];
  alerts: DashboardAlert[];
  focus: DashboardHomeFocus;
};

export function resolveDashboardHomeEffectiveReportDate(input: {
  snapshotReportDate?: string;
  requestedReportDate?: string;
}): string {
  const snapshot = input.snapshotReportDate?.trim() ?? "";
  if (snapshot.length > 0) {
    return snapshot;
  }
  return input.requestedReportDate?.trim() ?? "";
}

function buildMetaAttentionText(
  meta: ResultMeta | null | undefined,
  scope: string,
): string | null {
  if (
    !meta ||
    (meta.quality_flag === "ok" && meta.fallback_mode === "none" && meta.vendor_status === "ok")
  ) {
    return null;
  }

  const parts = [scope];
  if (meta.quality_flag !== "ok") {
    parts.push(`quality=${meta.quality_flag}`);
  }
  if (meta.fallback_mode !== "none") {
    parts.push(`fallback=${meta.fallback_mode}`);
  }
  if (meta.vendor_status !== "ok") {
    parts.push(`vendor=${meta.vendor_status}`);
  }
  return parts.join(" / ");
}

export function collectDashboardAttentionItems(input: {
  overviewMeta?: ResultMeta | null;
  attributionMeta?: ResultMeta | null;
}): string[] {
  const items: string[] = [];

  const overview = buildMetaAttentionText(input.overviewMeta, "overview");
  const attribution = buildMetaAttentionText(input.attributionMeta, "attribution");

  if (overview) {
    items.push(overview);
  }
  if (attribution) {
    items.push(attribution);
  }

  return items;
}

export function buildDashboardHomeSnapshotPartialNote(input: {
  snapshotMode?: string;
  domainsMissing?: readonly string[] | null;
}): string | null {
  if (input.snapshotMode !== "partial" && !(input.domainsMissing?.length)) {
    return null;
  }

  const missing = input.domainsMissing?.filter(
    (domain) => typeof domain === "string" && domain.trim().length > 0,
  );
  if (missing && missing.length > 0) {
    return `快照含缺域：${missing.join(", ")}`;
  }

  return "快照覆盖不完整";
}

export function formatDashboardHomeDelta(display: string | undefined, fallback: string): string {
  if (!display || !display.trim()) {
    return fallback;
  }
  return display;
}

export function buildDashboardHomeHeroMetrics(input: {
  metrics?: readonly DashboardOverviewMetricVM[] | null;
  limit?: number;
  fallbackDelta?: string;
}): DashboardHeroMetric[] {
  const source = input.metrics ?? [];
  const limit = input.limit ?? DASHBOARD_HOME_HERO_METRIC_LIMIT;

  return source.slice(0, Math.max(0, limit)).map((metric) => ({
    id: metric.id,
    label: metric.label,
    caliberLabel: metric.caliberLabel,
    value: metric.value?.display ?? "",
    note: metric.detail,
    delta: formatDashboardHomeDelta(metric.delta?.display, input.fallbackDelta ?? "N/A"),
    tone: metric.tone,
    history: metric.history ?? null,
  }));
}

function resolveSnapshotStatus(input: {
  snapshotLoading: boolean;
  snapshotMode?: string;
  snapshotPartialNote: string | null;
}): {
  value: string;
  tone: DashboardHomeKpiRibbonItem["tone"];
  hint: string;
} {
  if (input.snapshotLoading) {
    return {
      value: "载入中",
      tone: "warning",
      hint: "首页快照仍在载入。",
    };
  }

  if (input.snapshotPartialNote) {
    return {
      value: "含缺域",
      tone: "warning",
      hint: input.snapshotPartialNote,
    };
  }

  if (input.snapshotMode === "partial") {
    return {
      value: "含缺域",
      tone: "warning",
      hint: "首页快照覆盖不完整。",
    };
  }

  return {
    value: "完整",
    tone: "ok",
    hint: "首页快照完整。",
  };
}

export function buildDashboardHomeKpiRibbon(input: {
  effectiveReportDate: string;
  snapshotMode?: string;
  snapshotLoading: boolean;
  snapshotPartialNote: string | null;
  attentionCount: number;
  isMockMode: boolean;
}): DashboardHomeKpiRibbonItem[] {
  const snapshot = resolveSnapshotStatus({
    snapshotLoading: input.snapshotLoading,
    snapshotMode: input.snapshotMode,
    snapshotPartialNote: input.snapshotPartialNote,
  });
  const attentionTone: DashboardHomeKpiRibbonItem["tone"] =
    input.attentionCount > 0 ? "warning" : "ok";

  return [
    {
      id: "report-date",
      label: "报告日",
      value: input.effectiveReportDate || "待定",
      tone: input.effectiveReportDate ? "ok" : "warning",
      hint: input.effectiveReportDate
        ? "使用请求日或后端返回的快照报告日。"
        : "尚未解析到可用报告日。",
    },
    {
      id: "snapshot",
      label: "快照",
      value: snapshot.value,
      tone: snapshot.tone,
      hint: snapshot.hint,
    },
    {
      id: "attention",
      label: "治理",
      value: input.attentionCount > 0 ? `${input.attentionCount} 项关注` : "通过",
      tone: attentionTone,
      hint:
        input.attentionCount > 0
          ? "做业务判断前先复核治理关注项。"
          : "未检测到显式质量警示。",
    },
    {
      id: "source",
      label: "读链路",
      value: input.isMockMode ? "模拟" : "真实",
      tone: input.isMockMode ? "warning" : "ok",
      hint: input.isMockMode
        ? "当前为模拟数据源，不能直接作为业务判断。"
        : "数据来自正式服务链路。",
    },
  ];
}

function normalizeVerdictFallback(input: VerdictPayload | null | undefined): VerdictPayload {
  return (
    input ?? {
      conclusion: "尚无有效判断载荷，先保持观察。",
      tone: "neutral",
      reasons: [],
      suggestions: [],
    }
  );
}

export function buildDashboardHomeJudgment(input: {
  baseVerdict: VerdictPayload | null;
  isMockMode: boolean;
  hasAttention: boolean;
  hasSnapshotPartial: boolean;
}): VerdictPayload {
  if (input.isMockMode || input.hasAttention || input.hasSnapshotPartial) {
    return {
      conclusion: "数据状态需先复核，再做方向性判断。",
      tone: "warning",
      reasons: [],
      suggestions: [],
    };
  }

  return normalizeVerdictFallback(input.baseVerdict);
}

function metricToAlert(metric: DashboardOverviewMetricVM): DashboardAlert {
  return {
    id: `metric-${metric.id}`,
    title: metric.label,
    detail: `${metric.value?.display ?? ""} / ${metric.detail}`,
    severity: metric.tone === "negative" ? "high" : "medium",
  };
}

export function buildDashboardHomeAlerts(input: {
  metrics?: readonly DashboardOverviewMetricVM[] | null;
  isMockMode: boolean;
  attentionItems: readonly string[];
  snapshotPartialNote: string | null;
  maxAlerts?: number;
  metricAlertLimit?: number;
}): DashboardAlert[] {
  const maxAlerts = input.maxAlerts ?? DASHBOARD_HOME_ALERT_LIMIT;
  const metricLimit = input.metricAlertLimit ?? DASHBOARD_HOME_METRIC_ALERT_LIMIT;
  const alerts: DashboardAlert[] = [];

  if (input.isMockMode) {
    alerts.push({
      id: "mock-source",
      title: "当前处于模拟模式",
      detail: "首屏数字仅用于界面演示，不应直接作为业务判断依据。",
      severity: "medium",
    });
  }

  input.attentionItems.forEach((attention, index) => {
    alerts.push({
      id: `attention-${index}`,
      title: "治理状态待复核",
      detail: attention,
      severity: "high",
    });
  });

  if (input.snapshotPartialNote) {
    alerts.push({
      id: "partial-snapshot",
      title: "快照含缺域",
      detail: input.snapshotPartialNote,
      severity: "high",
    });
  }

  const metricAlerts = (input.metrics ?? [])
    .filter((metric) => metric.tone === "warning" || metric.tone === "negative")
    .slice(0, metricLimit)
    .map((metric) => metricToAlert(metric));

  alerts.push(...metricAlerts);

  return alerts.slice(0, Math.max(0, maxAlerts));
}

export function buildDashboardHomeFocusItems(input: {
  alerts: readonly DashboardAlert[];
  calendarEvents?: readonly ResearchCalendarEvent[] | null;
  calendarIsLoading: boolean;
  calendarIsError: boolean;
  calendarLimit?: number;
  focusTaskLimit?: number;
}): DashboardHomeFocus {
  const calendar = buildDashboardKeyCalendarModel({
    events: input.calendarEvents ? [...input.calendarEvents] : undefined,
    isLoading: input.calendarIsLoading,
    isError: input.calendarIsError,
    limit: input.calendarLimit ?? DASHBOARD_HOME_CALENDAR_LIMIT,
  });

  return {
    tasks: buildDashboardTodoTasksFromAlerts([...input.alerts], input.focusTaskLimit ?? DASHBOARD_HOME_FOCUS_TASK_LIMIT),
    calendarItems: calendar.items,
    calendarState: {
      status: calendar.status,
      message: calendar.message,
    },
  };
}

export function buildDashboardHomeModel(input: DashboardHomeModelInput): DashboardHomeModel {
  const effectiveReportDate = resolveDashboardHomeEffectiveReportDate({
    snapshotReportDate: input.snapshotReportDate,
    requestedReportDate: input.requestedReportDate,
  });

  const snapshotPartialNote = buildDashboardHomeSnapshotPartialNote({
    snapshotMode: input.snapshotMode,
    domainsMissing: input.snapshotDomainsMissing,
  });

  const attentionItems = collectDashboardAttentionItems({
    overviewMeta: input.overviewMeta,
    attributionMeta: input.attributionMeta,
  });

  const heroMetrics = buildDashboardHomeHeroMetrics({
    metrics: input.metrics,
    limit: input.heroMetricLimit ?? DASHBOARD_HOME_HERO_METRIC_LIMIT,
  });

  const judgment = buildDashboardHomeJudgment({
    baseVerdict: input.baseVerdict ?? null,
    isMockMode: input.isMockMode,
    hasAttention: attentionItems.length > 0,
    hasSnapshotPartial: Boolean(snapshotPartialNote),
  });

  const kpiRibbon = buildDashboardHomeKpiRibbon({
    effectiveReportDate,
    snapshotMode: input.snapshotMode,
    snapshotLoading: input.isSnapshotLoading,
    snapshotPartialNote,
    attentionCount: attentionItems.length,
    isMockMode: input.isMockMode,
  });

  const alerts = buildDashboardHomeAlerts({
    metrics: input.metrics,
    isMockMode: input.isMockMode,
    attentionItems,
    snapshotPartialNote,
    maxAlerts: input.alertLimit ?? DASHBOARD_HOME_ALERT_LIMIT,
    metricAlertLimit: input.metricAlertLimit ?? DASHBOARD_HOME_METRIC_ALERT_LIMIT,
  });

  const focus = buildDashboardHomeFocusItems({
    alerts,
    calendarEvents: input.calendarEvents,
    calendarIsLoading: input.calendarIsLoading,
    calendarIsError: input.calendarIsError,
    calendarLimit: input.calendarLimit ?? DASHBOARD_HOME_CALENDAR_LIMIT,
    focusTaskLimit: input.focusTaskLimit ?? DASHBOARD_HOME_FOCUS_TASK_LIMIT,
  });

  return {
    effectiveReportDate,
    attentionItems,
    snapshotPartialNote,
    kpiRibbon,
    judgment,
    heroMetrics,
    alerts,
    focus,
  };
}
