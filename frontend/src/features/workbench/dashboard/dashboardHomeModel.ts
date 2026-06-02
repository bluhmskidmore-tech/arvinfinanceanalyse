import type { ResultMeta, ResearchCalendarEvent, VerdictPayload } from "../../../api/contracts";
import type { DashboardOverviewMetricVM } from "../../executive-dashboard/adapters/executiveDashboardAdapter";
import type {
  DashboardAlert,
  DashboardCalendarPanelState,
  DashboardHeroMetric,
  DashboardHubCalendarItem,
  DashboardHubTask,
  DashboardReviewMetaItem,
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
  coreMetricsReportDate?: string | null;
  dailyChangesReportDate?: string | null;
  isSnapshotLoading: boolean;
  calendarEvents?: readonly ResearchCalendarEvent[] | null;
  calendarIsLoading: boolean;
  calendarIsError: boolean;
  isMockMode: boolean;
  heroMetricLimit?: number;
  heroMetricFallbackDelta?: string;
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

export type DashboardHomeSectionStatus =
  | "landed"
  | "supplemental"
  | "reserved"
  | "demo"
  | "blocked";

export type DashboardHomeSection = {
  id: string;
  label: string;
  status: DashboardHomeSectionStatus;
  firstScreenAllowed: boolean;
  reason: string;
};

export type DashboardHomeMeta = {
  reportDate: string;
  snapshotMode: string;
  sourceMode: "real" | "mock";
  attentionCount: number;
  snapshotPartialNote: string | null;
};

export type DashboardHomeModel = {
  meta: DashboardHomeMeta;
  effectiveReportDate: string;
  attentionItems: string[];
  snapshotPartialNote: string | null;
  snapshotModeLabel: string;
  kpiRibbon: DashboardHomeKpiRibbonItem[];
  judgment: VerdictPayload;
  heroMetrics: DashboardHeroMetric[];
  alerts: DashboardAlert[];
  reviewCount: number;
  reviewMetaItems: DashboardReviewMetaItem[];
  focus: DashboardHomeFocus;
  sections: DashboardHomeSection[];
  hiddenOrReservedSections: DashboardHomeSection[];
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
  scopeLabel: string,
): string | null {
  if (
    !meta ||
    (meta.quality_flag === "ok" && meta.fallback_mode === "none" && meta.vendor_status === "ok")
  ) {
    return null;
  }

  const parts = [scopeLabel];
  if (meta.quality_flag !== "ok") {
    parts.push(metaQualityLabel(meta.quality_flag));
  }
  if (meta.fallback_mode !== "none") {
    parts.push(`降级=${metaFallbackLabel(meta.fallback_mode)}`);
  }
  if (meta.vendor_status !== "ok") {
    parts.push(`供应商=${metaVendorLabel(meta.vendor_status)}`);
  }
  return parts.join(" / ");
}

function metaQualityLabel(value: ResultMeta["quality_flag"]): string {
  if (value === "ok") return "正常";
  if (value === "warning") return "预警";
  if (value === "error") return "错误";
  if (value === "stale") return "陈旧";
  return value;
}

function metaVendorLabel(value: ResultMeta["vendor_status"]): string {
  if (value === "ok") return "正常";
  if (value === "vendor_stale") return "供应商数据陈旧";
  if (value === "vendor_unavailable") return "供应商不可用";
  return value;
}

function metaFallbackLabel(value: ResultMeta["fallback_mode"]): string {
  if (value === "none") return "未降级";
  if (value === "latest_snapshot") return "最新快照降级";
  return value;
}

export function collectDashboardAttentionItems(input: {
  overviewMeta?: ResultMeta | null;
  attributionMeta?: ResultMeta | null;
}): string[] {
  const items: string[] = [];

  const overview = buildMetaAttentionText(input.overviewMeta, "总览");
  const attribution = buildMetaAttentionText(input.attributionMeta, "贡献拆解");

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
    return `该日部分业务域不可用: ${missing.join(", ")}`;
  }

  return "该日部分业务域不可用";
}

export function formatDashboardHomeDelta(display: string | undefined, fallback: string): string {
  const trimmed = display?.trim() ?? "";
  const missingDisplayValues = new Set(["—", "-", "N/A", "不可用"]);
  if (!trimmed || missingDisplayValues.has(trimmed)) {
    return fallback;
  }
  return display ?? "";
}

export function formatDashboardHomeSnapshotMode(
  mode: string | undefined,
  isLoading: boolean,
): string {
  if (isLoading) return "载入中";
  if (!mode) return "待定";
  if (mode === "partial") return "部分可用";
  if (mode === "complete") return "完整";
  return mode;
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
    linkTo: metric.id === "yield" ? "/pnl-by-business" : null,
  }));
}

function resolveSnapshotStatus(input: {
  snapshotLoading: boolean;
  snapshotMode?: string;
  snapshotPartialNote: string | null;
}): {
  value: string;
  tone: DashboardHomeKpiRibbonItem["tone"];
} {
  if (input.snapshotLoading) {
    return {
      value: "载入中",
      tone: "warning",
    };
  }

  if (input.snapshotPartialNote) {
    return {
      value: "含缺域",
      tone: "warning",
    };
  }

  if (input.snapshotMode === "partial") {
    return {
      value: "含缺域",
      tone: "warning",
    };
  }

  return {
    value: "完整",
    tone: "ok",
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
      value: input.effectiveReportDate || "最新可用",
      tone: input.effectiveReportDate ? "info" : "warning",
      hint: input.effectiveReportDate
        ? `归属日期 ${input.effectiveReportDate}`
        : "用户选择 / 默认日期",
    },
    {
      id: "snapshot",
      label: "快照",
      value: snapshot.value,
      tone: snapshot.tone,
      hint: input.snapshotPartialNote ?? "首页首屏只保留已落地的受治理结果",
    },
    {
      id: "attention",
      label: "治理",
      value: input.attentionCount > 0 ? `${input.attentionCount} 项关注` : "通过",
      tone: attentionTone,
      hint:
        input.attentionCount > 0
          ? "做业务判断前先复核治理关注项。"
          : "无质量、降级或供应商警示",
    },
    {
      id: "source",
      label: "读链路",
      value: input.isMockMode ? "模拟演示" : "真实链路",
      tone: input.isMockMode ? "warning" : "ok",
      hint: input.isMockMode
        ? "仅用于界面演示，不应作为业务判断依据"
        : "正式接口",
    },
  ];
}

export function buildDashboardHomeReviewMetaItems(input: {
  reportDate: string;
  snapshotMode?: string;
  snapshotPartialNote: string | null;
  isSnapshotLoading: boolean;
  isMockMode: boolean;
}): DashboardReviewMetaItem[] {
  const snapshotValue = formatDashboardHomeSnapshotMode(
    input.snapshotMode,
    input.isSnapshotLoading,
  );
  return [
    {
      id: "report-date",
      label: "报告日",
      value: input.reportDate || "待定",
      tone: input.reportDate ? "ok" : "warning",
    },
    {
      id: "snapshot",
      label: "快照",
      value: input.snapshotPartialNote ? "含缺域" : snapshotValue,
      tone: input.snapshotPartialNote ? "warning" : "ok",
    },
    {
      id: "source",
      label: "读链路",
      value: input.isMockMode ? "模拟" : "真实",
      tone: input.isMockMode ? "warning" : "ok",
    },
  ];
}

function isSameReportDate(expected: string, actual: string | null | undefined): boolean {
  const left = expected.trim();
  const right = actual?.trim() ?? "";
  return left.length > 0 && right.length > 0 && left === right;
}

function supplementalSection(input: {
  id: string;
  label: string;
  effectiveReportDate: string;
  actualReportDate?: string | null;
}): DashboardHomeSection {
  if (!input.effectiveReportDate.trim()) {
    return {
      id: input.id,
      label: input.label,
      status: "blocked",
      firstScreenAllowed: false,
      reason: "等待首页快照报告日后才能请求同日补充读面。",
    };
  }

  if (!input.actualReportDate?.trim()) {
    return {
      id: input.id,
      label: input.label,
      status: "supplemental",
      firstScreenAllowed: false,
      reason: "仅作为下钻补充；数据返回前不参与首屏判断。",
    };
  }

  if (!isSameReportDate(input.effectiveReportDate, input.actualReportDate)) {
    return {
      id: input.id,
      label: input.label,
      status: "blocked",
      firstScreenAllowed: false,
      reason: `补充读面报告日 ${input.actualReportDate} 与首页快照 ${input.effectiveReportDate} 不一致。`,
    };
  }

  return {
    id: input.id,
    label: input.label,
    status: "supplemental",
    firstScreenAllowed: false,
    reason: "同报告日补充读面，只能在下钻区展示，不提升为首屏主结论。",
  };
}

export function buildDashboardHomeSections(input: {
  effectiveReportDate: string;
  metricsCount: number;
  coreMetricsReportDate?: string | null;
  dailyChangesReportDate?: string | null;
}): DashboardHomeSection[] {
  const overviewStatus: DashboardHomeSectionStatus =
    input.metricsCount > 0 ? "landed" : "blocked";

  return [
    {
      id: "judgment",
      label: "今日判断",
      status: "landed",
      firstScreenAllowed: true,
      reason: "来自 /ui/home/snapshot verdict 或快照状态确定性降级。",
    },
    {
      id: "governance",
      label: "治理状态",
      status: "landed",
      firstScreenAllowed: true,
      reason: "来自首页快照 result_meta 与 domains_effective_date。",
    },
    {
      id: "overview_metrics",
      label: "核心经营指标",
      status: overviewStatus,
      firstScreenAllowed: true,
      reason:
        overviewStatus === "landed"
          ? "来自首页快照 overview.metrics。"
          : "首页快照没有返回可展示指标；首屏只能显示空态，不能用补充接口替代。",
    },
    {
      id: "product_category_headline",
      label: "经营贡献摘要",
      status: "landed",
      firstScreenAllowed: true,
      reason: "随首页快照返回；前端仅展示，不在页面重算。",
    },
    supplementalSection({
      id: "core_metrics",
      label: "债券 / 同业核心指标",
      effectiveReportDate: input.effectiveReportDate,
      actualReportDate: input.coreMetricsReportDate,
    }),
    supplementalSection({
      id: "daily_changes",
      label: "日 / 周 / 月变动",
      effectiveReportDate: input.effectiveReportDate,
      actualReportDate: input.dailyChangesReportDate,
    }),
    {
      id: "market_context",
      label: "市场上下文",
      status: "supplemental",
      firstScreenAllowed: false,
      reason: "市场/宏观数据不绑定首页严格报告日，只能作为下钻上下文。",
    },
    {
      id: "research_calendar",
      label: "关键事件日历",
      status: "supplemental",
      firstScreenAllowed: false,
      reason: "事件日历按自然日期窗口展示，不参与首页报告日判断。",
    },
    {
      id: "risk_overview",
      label: "executive 风险概览",
      status: "reserved",
      firstScreenAllowed: false,
      reason: "当前边界为 reserved/excluded surface，不发 live 首页请求。",
    },
    {
      id: "contribution",
      label: "executive 贡献",
      status: "reserved",
      firstScreenAllowed: false,
      reason: "当前边界为 reserved/excluded surface，不发 live 首页请求。",
    },
    {
      id: "alerts",
      label: "executive 告警",
      status: "reserved",
      firstScreenAllowed: false,
      reason: "当前边界为 reserved/excluded surface，不发 live 首页请求。",
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
      id: "mock-mode",
      title: "当前处于模拟模式",
      detail: "首屏数字仅用于界面演示，不应直接作为业务判断依据。",
      severity: "high",
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
      id: "partial-note",
      title: "快照含缺域",
      detail: input.snapshotPartialNote,
      severity: "medium",
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
  const snapshotModeLabel = formatDashboardHomeSnapshotMode(
    input.snapshotMode,
    input.isSnapshotLoading,
  );

  const attentionItems = collectDashboardAttentionItems({
    overviewMeta: input.overviewMeta,
    attributionMeta: input.attributionMeta,
  });

  const heroMetrics = buildDashboardHomeHeroMetrics({
    metrics: input.metrics,
    limit: input.heroMetricLimit ?? DASHBOARD_HOME_HERO_METRIC_LIMIT,
    fallbackDelta: input.heroMetricFallbackDelta,
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
  const reviewCount = alerts.filter(
    (alert) => alert.severity === "high" || alert.severity === "medium",
  ).length;
  const reviewMetaItems = buildDashboardHomeReviewMetaItems({
    reportDate: effectiveReportDate,
    snapshotMode: input.snapshotMode,
    snapshotPartialNote,
    isSnapshotLoading: input.isSnapshotLoading,
    isMockMode: input.isMockMode,
  });

  const focus = buildDashboardHomeFocusItems({
    alerts,
    calendarEvents: input.calendarEvents,
    calendarIsLoading: input.calendarIsLoading,
    calendarIsError: input.calendarIsError,
    calendarLimit: input.calendarLimit ?? DASHBOARD_HOME_CALENDAR_LIMIT,
    focusTaskLimit: input.focusTaskLimit ?? DASHBOARD_HOME_FOCUS_TASK_LIMIT,
  });

  const sections = buildDashboardHomeSections({
    effectiveReportDate,
    metricsCount: input.metrics?.length ?? 0,
    coreMetricsReportDate: input.coreMetricsReportDate,
    dailyChangesReportDate: input.dailyChangesReportDate,
  });
  const hiddenOrReservedSections = sections.filter(
    (section) =>
      !section.firstScreenAllowed ||
      section.status === "blocked" ||
      section.status === "reserved" ||
      section.status === "demo",
  );

  return {
    meta: {
      reportDate: effectiveReportDate,
      snapshotMode: input.snapshotMode ?? "unknown",
      sourceMode: input.isMockMode ? "mock" : "real",
      attentionCount: attentionItems.length,
      snapshotPartialNote,
    },
    effectiveReportDate,
    attentionItems,
    snapshotPartialNote,
    snapshotModeLabel,
    kpiRibbon,
    judgment,
    heroMetrics,
    alerts,
    reviewCount,
    reviewMetaItems,
    focus,
    sections,
    hiddenOrReservedSections,
  };
}
