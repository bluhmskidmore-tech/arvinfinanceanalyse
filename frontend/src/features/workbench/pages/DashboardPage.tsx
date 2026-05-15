import { lazy, Suspense, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import type { ResultMeta, VerdictPayload } from "../../../api/contracts";
import { createApiClient, useApiClient } from "../../../api/client";
import { PageSectionLead } from "../../../components/page/PagePrimitives";
import { tabularNumsStyle } from "../../../theme/designSystem";
import { adaptDashboard } from "../../executive-dashboard/adapters/executiveDashboardAdapter";
import { sanitizeMetricCopy } from "../../executive-dashboard/lib/sanitizeMetricCopy";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { DashboardBondCounterpartySection } from "../../executive-dashboard/components/DashboardBondCounterpartySection";
import {
  DashboardBondHeadlineSection,
} from "../../executive-dashboard/components/DashboardBondHeadlineSection";
import { dashboardBondHeadlineQueryKey } from "../../executive-dashboard/components/dashboardBondHeadlineQuery";
import { DashboardLiabilityCounterpartySection } from "../../executive-dashboard/components/DashboardLiabilityCounterpartySection";
import { DashboardNewsDigestSection } from "../../executive-dashboard/components/DashboardNewsDigestSection";
import { BondAnalyticsOverviewMidCharts } from "../../bond-analytics/components/BondAnalyticsOverviewMidCharts";
import {
  DashboardAlertCenterPanel,
  DashboardGlobalJudgmentPanel,
  DashboardModuleEntryGrid,
  DashboardModuleSnapshotPanel,
  DashboardOverviewHeroStrip,
  DashboardProductCategoryYtdCards,
  DashboardTasksCalendarPanels,
  type DashboardAlert,
  type DashboardModuleSnapshotItem,
  type DashboardReviewAlert,
} from "../dashboard/DashboardOverviewSections";
import {
  DashboardJudgmentBand,
} from "../dashboard/DashboardHomeSections";
import {
  DashboardCockpitAccountTable,
  DashboardCockpitLowerGrid,
  DashboardCockpitMainGrid,
  DashboardCockpitMarketTicker,
  DashboardCockpitMetricRail,
} from "../dashboard/DashboardCockpitSections";
import { DashboardCoreMetricsSection } from "../dashboard/DashboardCoreMetricsSection";
import { DashboardDailyChangesSection } from "../dashboard/DashboardDailyChangesSection";
import { GovernancePills } from "../dashboard/GovernancePills";
import {
  buildDashboardCockpitModel,
  type DashboardCockpitPreviewSignal,
} from "../dashboard/dashboardCockpitModel";
import { buildDashboardHomeModel } from "../dashboard/dashboardHomeModel";
import { workbenchNavigation } from "../../../mocks/navigation";
import { AgentPanel } from "../../agent/AgentPanel";

const PnlAttributionSection = lazy(
  () => import("../../executive-dashboard/components/PnlAttributionSection"),
);

function LazyPanelFallback({ title }: { title: string }) {
  return (
    <AsyncSection
      title={title}
      isLoading
      isError={false}
      isEmpty={false}
      onRetry={() => undefined}
    >
      <div />
    </AsyncSection>
  );
}

const DASHBOARD_KEY_CALENDAR_LOOKBACK_DAYS = 7;
const DASHBOARD_KEY_CALENDAR_FORWARD_DAYS = 14;
const DASHBOARD_DRILLDOWN_HIGHLIGHT_MS = 1600;

const MODULE_REVIEW_SIGNALS: Record<string, string> = {
  "bond-analysis": "DV01 / NIM / 久期与利差",
  "cross-asset": "利率行情 / 资金曲线 / 信用利差",
  "balance-analysis": "资产规模 / NIM / 缺域状态",
  "bank-ledger-dashboard": "as_of_date / 资产与负债敞口",
  "product-category-pnl": "YTD 收益 / 产品分类摘要",
  "risk-tensor": "DV01 / KRD / 信用利差迁移",
  "market-data": "利率 / 资金 / 信用成交上下文",
  "decision-items": "高/中优先级事项与处理状态",
  "pnl-bridge": "实际损益 / 解释效应 / 残差",
  positions: "持仓明细 / 分布 / 客户下钻",
  "platform-config": "质量 / 降级 / 供应商状态",
};

const VALID_VERDICT_LINKS = new Set([
  "/bond-analysis",
  "/balance-analysis",
  "/product-category-pnl",
  "/decision-items",
  "/platform-config",
  "/risk-tensor",
  "/market-data",
  "/cross-asset",
  "/bank-ledger-dashboard",
]);

function lookupWorkbenchSection(path: string) {
  return workbenchNavigation.find((section) => section.path === path);
}

function reviewSourceHint(path: string): string {
  const section = lookupWorkbenchSection(path);
  if (!section) {
    return "路由已配置，业务状态待确认";
  }
  return section.readinessNote || section.description || "入口状态待确认";
}

function reviewReadinessLabel(path: string): string {
  return lookupWorkbenchSection(path)?.readinessLabel ?? "待接入";
}

function sanitizeVerdictLinks(verdict: VerdictPayload): VerdictPayload {
  return {
    ...verdict,
    suggestions: verdict.suggestions.map((suggestion) => ({
      ...suggestion,
      link:
        suggestion.link && VALID_VERDICT_LINKS.has(suggestion.link)
          ? suggestion.link
          : null,
    })),
  };
}

function alertSourceLabel(alert: DashboardAlert): string {
  if (alert.id === "mock-mode") {
    return "模拟数据源";
  }
  if (alert.id.startsWith("attention-")) {
    return "治理元数据";
  }
  if (alert.id === "partial-note") {
    return "首页快照缺域";
  }
  if (alert.id.startsWith("metric-")) {
    return "首页总览指标 tone";
  }
  return "本地复核清单";
}

function alertAction(alert: DashboardAlert): { actionLabel: string; actionTo: string } {
  if (alert.id === "mock-mode" || alert.id.startsWith("attention-")) {
    return { actionLabel: "打开中台配置", actionTo: "/platform-config" };
  }
  if (alert.id === "partial-note") {
    return { actionLabel: "打开决策事项", actionTo: "/decision-items" };
  }
  if (alert.id.includes("dv01") || alert.title.toLowerCase().includes("dv01")) {
    return { actionLabel: "打开风险张量", actionTo: "/risk-tensor" };
  }
  if (alert.id.includes("yield") || alert.id.includes("nim")) {
    return { actionLabel: "打开债券分析", actionTo: "/bond-analysis" };
  }
  if (alert.severity === "low") {
    return { actionLabel: "打开模块快照", actionTo: "/decision-items" };
  }
  return { actionLabel: "打开决策事项", actionTo: "/decision-items" };
}

function buildReviewAlerts(alerts: DashboardAlert[]): DashboardReviewAlert[] {
  return alerts.map((alert) => ({
    ...alert,
    sourceLabel: alertSourceLabel(alert),
    ...alertAction(alert),
  }));
}

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

function DashboardActionQueue({
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

function DashboardCockpitSupplementPreview({
  signals,
}: {
  signals: readonly DashboardCockpitPreviewSignal[];
}) {
  const activeDrilldownTargetRef = useRef<HTMLElement | null>(null);
  const activeDrilldownTimerRef = useRef<number | null>(null);

  const clearDrilldownHighlight = () => {
    if (activeDrilldownTimerRef.current !== null) {
      window.clearTimeout(activeDrilldownTimerRef.current);
      activeDrilldownTimerRef.current = null;
    }
    if (activeDrilldownTargetRef.current) {
      activeDrilldownTargetRef.current.removeAttribute("data-drilldown-active");
      activeDrilldownTargetRef.current = null;
    }
  };

  useEffect(() => clearDrilldownHighlight, []);

  const handleSectionDrilldown = (
    event: ReactMouseEvent<HTMLButtonElement>,
    targetTestIds: readonly string[],
  ) => {
    event.preventDefault();
    event.stopPropagation();
    const target = targetTestIds
      .map((testId) => document.querySelector<HTMLElement>(`[data-testid="${testId}"]`))
      .find((element): element is HTMLElement => element !== null);
    if (!target) {
      return;
    }
    clearDrilldownHighlight();
    target.setAttribute("data-drilldown-active", "true");
    activeDrilldownTargetRef.current = target;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    activeDrilldownTimerRef.current = window.setTimeout(() => {
      target.removeAttribute("data-drilldown-active");
      if (activeDrilldownTargetRef.current === target) {
        activeDrilldownTargetRef.current = null;
      }
      activeDrilldownTimerRef.current = null;
    }, DASHBOARD_DRILLDOWN_HIGHLIGHT_MS);
  };

  return (
    <div
      data-testid="dashboard-cockpit-supplement-preview"
      className="dashboard-cockpit-supplement-preview"
    >
      {signals.map((signal) => {
        const action =
          signal.id === "coverage"
            ? {
                kind: "route" as const,
                to: "/platform-config",
                label: "查看治理与数据来源",
              }
            : signal.id === "net-change"
              ? {
                  kind: "section" as const,
                  targetTestIds: ["dashboard-business-detail-strip"],
                  label: "查看区间变动",
                }
              : signal.id === "concentration"
                ? {
                    kind: "section" as const,
                    targetTestIds: [
                      "dashboard-cockpit-account-row-account-risk-review",
                      "dashboard-cockpit-account-table",
                    ],
                    label: "查看组合结构与风险摘要",
                  }
                : {
                    kind: "route" as const,
                    to: "/risk-tensor",
                    label: "查看风险张量",
                  };

        const content = (
          <>
            <span className="dashboard-cockpit-supplement-preview__label">{signal.label}</span>
            <strong className="dashboard-cockpit-supplement-preview__value">{signal.value}</strong>
            <span className="dashboard-cockpit-supplement-preview__detail">{signal.detail}</span>
          </>
        );

        return (
          <article
            key={signal.id}
            data-testid={`dashboard-cockpit-preview-${signal.id}`}
            className="dashboard-cockpit-supplement-preview__item"
            data-status={signal.status}
            data-tone={signal.tone}
          >
            {action.kind === "route" ? (
              <Link
                to={action.to}
                className="dashboard-cockpit-supplement-preview__trigger"
                aria-label={action.label}
                title={action.label}
                onClick={(event) => event.stopPropagation()}
              >
                {content}
              </Link>
            ) : (
              <button
                type="button"
                className="dashboard-cockpit-supplement-preview__trigger"
                aria-label={action.label}
                title={action.label}
                onClick={(event) => handleSectionDrilldown(event, action.targetTestIds)}
              >
                {content}
              </button>
            )}
          </article>
        );
      })}
    </div>
  );
}

function buildReviewEvidenceLabel(input: {
  domainsEffectiveDate: Record<string, string>;
  overviewMeta: ResultMeta | null;
  attributionMeta: ResultMeta | null;
}): string {
  const dates = Object.entries(input.domainsEffectiveDate)
    .map(([domain, date]) => `${domain}=${date}`)
    .join(" / ");
  if (dates) {
    return dates;
  }
  const meta = input.overviewMeta ?? input.attributionMeta;
  if (meta) {
    return [meta.source_version, meta.rule_version, meta.cache_version]
      .filter((part) => part && part !== "unknown")
      .join(" / ");
  }
  return "首页快照返回后展示来源版本与有效日期";
}

function addDaysToIsoDate(date: string, days: number): string {
  const trimmed = date.trim();
  if (!trimmed) {
    return "";
  }
  const parsed = new Date(`${trimmed}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return trimmed;
  }
  parsed.setUTCDate(parsed.getUTCDate() + days);
  return parsed.toISOString().slice(0, 10);
}

function todayIsoDate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function reportDateMismatch(expected: string, actual: string | undefined): boolean {
  const expectedTrimmed = expected.trim();
  const actualTrimmed = actual?.trim() ?? "";
  return expectedTrimmed.length > 0 && actualTrimmed.length > 0 && expectedTrimmed !== actualTrimmed;
}

function readErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  return "unknown error";
}

function isNetworkUnavailableError(error: unknown): boolean {
  const message = readErrorMessage(error).toLowerCase();
  return [
    "failed to fetch",
    "fetch failed",
    "networkerror",
    "network request failed",
    "err_connection_refused",
    "connection refused",
    "network unavailable",
    "load failed",
  ].some((part) => message.includes(part));
}

function DashboardSupplementalBlockedSection({
  testId,
  title,
  expectedReportDate,
  actualReportDate,
}: {
  testId: string;
  title: string;
  expectedReportDate: string;
  actualReportDate: string;
}) {
  return (
    <section
      data-testid={testId}
      className="dashboard-home-panel dashboard-metric-shell dashboard-supplemental-blocked"
    >
      <header className="dashboard-metric-header">
        <span className="dashboard-home-section-eyebrow dashboard-metric-eyebrow-label">
          下钻补充
        </span>
        <div className="dashboard-metric-title-row">
          <h2 className="dashboard-business-balance-summary__title dashboard-metric-section-title">
            {title}
          </h2>
        </div>
      </header>
      <p className="dashboard-home-muted">
        该补充读面报告日 {actualReportDate} 与首页快照 {expectedReportDate}{" "}
        不一致，暂不展示为驾驶舱判断依据。
      </p>
    </section>
  );
}

export default function DashboardPage() {
  const sourceClient = useApiClient();
  const fallbackClient = useMemo(() => createApiClient({ mode: "mock" }), []);
  const [reportDate, setReportDate] = useState("");
  const [toolbarSearch, setToolbarSearch] = useState("");
  const [allowPartial, setAllowPartial] = useState(false);
  const [isDetailDrilldownOpen, setIsDetailDrilldownOpen] = useState(false);
  const [isCockpitSupplementOpen, setIsCockpitSupplementOpen] = useState(false);
  const [forceMockFallback, setForceMockFallback] = useState(false);
  const [liveFallbackReason, setLiveFallbackReason] = useState<string | null>(null);
  const dataClient = forceMockFallback ? fallbackClient : sourceClient;
  const displayMode = sourceClient.mode;
  const isLiveDataFallback = sourceClient.mode === "real" && forceMockFallback;
  const requestedDateLabel = reportDate || "latest";

  const snapshotQuery = useQuery({
    queryKey: ["home-snapshot", dataClient.mode, requestedDateLabel, allowPartial],
    queryFn: () =>
      dataClient.getHomeSnapshot({
        reportDate: reportDate || undefined,
        allowPartial,
      }),
    retry: false,
  });

  useEffect(() => {
    if (
      sourceClient.mode === "real" &&
      !forceMockFallback &&
      snapshotQuery.isError &&
      isNetworkUnavailableError(snapshotQuery.error)
    ) {
      setLiveFallbackReason(readErrorMessage(snapshotQuery.error));
      setForceMockFallback(true);
    }
  }, [
    forceMockFallback,
    snapshotQuery.error,
    snapshotQuery.isError,
    sourceClient.mode,
  ]);

  const { overviewEnv, attributionEnv } = useMemo(() => {
    const env = snapshotQuery.data;
    if (!env) return { overviewEnv: undefined, attributionEnv: undefined };
    return {
      overviewEnv: {
        result_meta: env.result_meta,
        result: env.result.overview,
      },
      attributionEnv: {
        result_meta: env.result_meta,
        result: env.result.attribution,
      },
    };
  }, [snapshotQuery.data]);

  const adapterOutput = useMemo(
    () =>
      adaptDashboard({
        overviewEnv,
        attributionEnv,
        overviewLoading: snapshotQuery.isLoading,
        overviewError: snapshotQuery.isError,
        attributionLoading: snapshotQuery.isLoading,
        attributionError: snapshotQuery.isError,
        verdictPayload: snapshotQuery.data?.result.verdict ?? null,
        snapshotFetchErrorDetail:
          snapshotQuery.error instanceof Error ? snapshotQuery.error.message : undefined,
        domainsEffectiveDate: snapshotQuery.data?.result.domains_effective_date ?? {},
        productCategoryYtd: snapshotQuery.data?.result.product_category_ytd ?? null,
        productCategoryMonthly: snapshotQuery.data?.result.product_category_monthly ?? null,
      }),
    [
      overviewEnv,
      attributionEnv,
      snapshotQuery.isLoading,
      snapshotQuery.isError,
      snapshotQuery.error,
      snapshotQuery.data?.result.verdict,
      snapshotQuery.data?.result.domains_effective_date,
      snapshotQuery.data?.result.product_category_ytd,
      snapshotQuery.data?.result.product_category_monthly,
    ],
  );

  const snapshotResult = snapshotQuery.data?.result;
  const overviewMeta = adapterOutput.overview.meta;
  const attributionMeta = adapterOutput.attribution.meta;
  const initialEffectiveReportDate =
    snapshotResult?.report_date?.trim() || reportDate.trim();

  const supplementalReportDate = initialEffectiveReportDate || undefined;

  const coreMetricsQuery = useQuery({
    queryKey: ["dashboard", "core-metrics", dataClient.mode, supplementalReportDate ?? "pending-snapshot"],
    queryFn: () => dataClient.getCoreMetrics({ reportDate: supplementalReportDate }),
    retry: false,
    staleTime: 60_000,
    enabled: Boolean(supplementalReportDate),
  });

  const dailyChangesQuery = useQuery({
    queryKey: ["dashboard", "daily-changes", dataClient.mode, supplementalReportDate ?? "pending-snapshot"],
    queryFn: () => dataClient.getDailyChanges({ reportDate: supplementalReportDate }),
    retry: false,
    staleTime: 60_000,
    enabled: Boolean(supplementalReportDate),
  });

  const marketRatesQuery = useQuery({
    queryKey: ["dashboard", "cockpit-market-rates", dataClient.mode],
    queryFn: () => dataClient.getMarketDataRates(),
    retry: false,
    staleTime: 60_000,
  });

  const bondHeadlineQuery = useQuery({
    queryKey: dashboardBondHeadlineQueryKey(
      dataClient.mode,
      supplementalReportDate ?? "pending-snapshot",
    ),
    queryFn: () => dataClient.getBondDashboardHeadlineKpis(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: Boolean(supplementalReportDate),
  });

  const portfolioHeadlinesQuery = useQuery({
    queryKey: [
      "dashboard",
      "cockpit-portfolio-headlines",
      dataClient.mode,
      supplementalReportDate ?? "pending-snapshot",
    ],
    queryFn: () => dataClient.getBondAnalyticsPortfolioHeadlines(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: Boolean(supplementalReportDate),
  });
  const bondBucketAnalysisYear = Number.parseInt((supplementalReportDate ?? "").slice(0, 4), 10);
  const bondBucketYieldQuery = useQuery({
    queryKey: [
      "dashboard",
      "bond-bucket-yield",
      dataClient.mode,
      supplementalReportDate ?? "pending-snapshot",
      Number.isFinite(bondBucketAnalysisYear) ? bondBucketAnalysisYear : "pending-year",
    ],
    queryFn: () =>
      dataClient.getPnlByBusinessAnalysis({
        year: bondBucketAnalysisYear,
        asOfDate: supplementalReportDate ?? undefined,
        dimension: "bond_bucket",
      }),
    retry: false,
    staleTime: 60_000,
    enabled: Boolean(supplementalReportDate) && Number.isFinite(bondBucketAnalysisYear),
  });

  const coreMetricsDateMismatch = reportDateMismatch(
    initialEffectiveReportDate,
    coreMetricsQuery.data?.result.report_date,
  );
  const dailyChangesDateMismatch = reportDateMismatch(
    initialEffectiveReportDate,
    dailyChangesQuery.data?.result.report_date,
  );

  const calendarAnchorDate = todayIsoDate();
  const calendarStartDate = addDaysToIsoDate(
    calendarAnchorDate,
    -DASHBOARD_KEY_CALENDAR_LOOKBACK_DAYS,
  );
  const calendarEndDate = addDaysToIsoDate(
    calendarAnchorDate,
    DASHBOARD_KEY_CALENDAR_FORWARD_DAYS,
  );

  const researchCalendarQuery = useQuery({
    queryKey: ["research-calendar", dataClient.mode, calendarStartDate, calendarEndDate],
    queryFn: () =>
      dataClient.getResearchCalendarEvents(
        dataClient.mode === "real"
          ? {
              startDate: calendarStartDate,
              endDate: calendarEndDate,
            }
          : { startDate: calendarStartDate, endDate: calendarEndDate },
      ),
    retry: false,
  });

  const sanitizedOverviewMetrics = useMemo(
    () =>
      (adapterOutput.overview.vm?.metrics ?? []).map((metric) =>
        sanitizeMetricCopy(metric),
      ),
    [adapterOutput.overview.vm?.metrics],
  );

  const dashboardHome = useMemo(
    () =>
      buildDashboardHomeModel({
        metrics: sanitizedOverviewMetrics,
        baseVerdict: adapterOutput.verdict,
        overviewMeta,
        attributionMeta,
        requestedReportDate: reportDate,
        snapshotReportDate: snapshotResult?.report_date,
        snapshotMode: snapshotResult?.mode,
        snapshotDomainsMissing: snapshotResult?.domains_missing,
        coreMetricsReportDate: coreMetricsQuery.data?.result.report_date ?? null,
        dailyChangesReportDate: dailyChangesQuery.data?.result.report_date ?? null,
        isSnapshotLoading: snapshotQuery.isLoading,
        calendarEvents: researchCalendarQuery.data,
        calendarIsLoading:
          !initialEffectiveReportDate ||
          (researchCalendarQuery.isLoading && !researchCalendarQuery.data),
        calendarIsError: researchCalendarQuery.isError,
        isMockMode: dataClient.mode !== "real",
        heroMetricFallbackDelta: "读链路",
      }),
    [
      adapterOutput.verdict,
      attributionMeta,
      dataClient.mode,
      coreMetricsQuery.data?.result.report_date,
      dailyChangesQuery.data?.result.report_date,
      initialEffectiveReportDate,
      overviewMeta,
      reportDate,
      researchCalendarQuery.data,
      researchCalendarQuery.isError,
      researchCalendarQuery.isLoading,
      snapshotQuery.isLoading,
      snapshotResult?.domains_missing,
      snapshotResult?.mode,
      snapshotResult?.report_date,
      sanitizedOverviewMetrics,
    ],
  );

  const effectiveReportDate = dashboardHome.effectiveReportDate;
  const snapshotPartialNote = dashboardHome.snapshotPartialNote;
  const attentionItems = dashboardHome.attentionItems;

  const dashboardCockpit = useMemo(
    () =>
      buildDashboardCockpitModel({
        reportDate: effectiveReportDate,
        snapshotMode: snapshotResult?.mode,
        isMockMode: dataClient.mode !== "real",
        coreMetrics: coreMetricsQuery.data?.result ?? null,
        dailyChanges: dailyChangesQuery.data?.result ?? null,
        bondHeadline: bondHeadlineQuery.data?.result ?? null,
        portfolio: portfolioHeadlinesQuery.data?.result ?? null,
        bondBucketRows: bondBucketYieldQuery.data?.result.rows ?? null,
        marketPoints: marketRatesQuery.data?.result.series ?? null,
        calendarItems: researchCalendarQuery.data ?? null,
      }),
    [
      bondHeadlineQuery.data?.result,
      dataClient.mode,
      coreMetricsQuery.data?.result,
      dailyChangesQuery.data?.result,
      effectiveReportDate,
      marketRatesQuery.data?.result.series,
      bondBucketYieldQuery.data?.result.rows,
      portfolioHeadlinesQuery.data?.result,
      researchCalendarQuery.data,
      snapshotResult?.mode,
    ],
  );

  const fallbackVerdict = useMemo<VerdictPayload>(
    () => ({
      conclusion:
        dataClient.mode !== "real" || snapshotPartialNote || attentionItems.length > 0
          ? "数据状态需先复核，再做方向性判断"
          : "当前指标平稳，等待下一组观测",
      tone:
        dataClient.mode !== "real" || snapshotPartialNote || attentionItems.length > 0
          ? "warning"
          : "neutral",
      reasons:
        dataClient.mode !== "real"
          ? [
              {
                label: "演示模式",
                value: "需复核",
                detail: "演示：首屏定调结论占位，用于展示 Pyramid 叙事结构。",
                tone: "warning",
              },
            ]
          : [],
      suggestions: [
        {
          text: "先复核数据源与治理状态",
          link: "/platform-config",
        },
      ],
    }),
    [dataClient.mode, snapshotPartialNote, attentionItems.length],
  );

  const reviewVerdict = useMemo(
    () => sanitizeVerdictLinks(adapterOutput.verdict ?? fallbackVerdict),
    [adapterOutput.verdict, fallbackVerdict],
  );

  const reviewEvidenceLabel = useMemo(
    () =>
      buildReviewEvidenceLabel({
        domainsEffectiveDate: adapterOutput.domainsEffectiveDate,
        overviewMeta,
        attributionMeta,
      }),
    [adapterOutput.domainsEffectiveDate, attributionMeta, overviewMeta],
  );

  const moduleSnapshotItems = useMemo<DashboardModuleSnapshotItem[]>(
    () => {
      const overviewById = new Map(
        sanitizedOverviewMetrics.map((metric) => [metric.id, metric.value.display]),
      );
      return [
        {
          id: "bond-analysis",
          to: "/bond-analysis",
          title: "债券分析",
          eyebrow: "看久期、利差与持仓结构",
          question: "收益率曲线、信用利差和组合暴露现在最该看哪一段？",
          output: "进入后先看久期、Top 持仓与信用利差。",
          readiness: reviewReadinessLabel("/bond-analysis"),
          sourceHint: reviewSourceHint("/bond-analysis"),
          reviewSignals: MODULE_REVIEW_SIGNALS["bond-analysis"],
          spotlight: true,
        },
        {
          id: "cross-asset",
          to: "/cross-asset",
          title: "跨资产驱动",
          eyebrow: "看外部约束和传导",
          question: "利率、汇率、油价和风险偏好如何传导到债券定价？",
          output: "进入后先看环境得分、驱动矩阵和候选动作。",
          readiness: reviewReadinessLabel("/cross-asset"),
          sourceHint: reviewSourceHint("/cross-asset"),
          reviewSignals: MODULE_REVIEW_SIGNALS["cross-asset"],
          spotlight: true,
        },
        {
          id: "balance-analysis",
          to: "/balance-analysis",
          title: "资产负债分析",
          eyebrow: "看缺口、滚续和期限错配",
          question: "短端压力、滚续节奏和错配位置具体落在哪一层？",
          output: "进入后先看净缺口、basis 与压力工作台。",
          readiness: reviewReadinessLabel("/balance-analysis"),
          sourceHint: reviewSourceHint("/balance-analysis"),
          reviewSignals: [
            MODULE_REVIEW_SIGNALS["balance-analysis"],
            overviewById.get("aum") ? `资产规模 ${overviewById.get("aum")}` : null,
          ].filter(Boolean).join(" / "),
          spotlight: true,
        },
        {
          id: "bank-ledger-dashboard",
          to: "/bank-ledger-dashboard",
          title: "银行台账",
          eyebrow: "看资产、发行负债和净敞口",
          question: "银行债券台账的资产面值、发行负债、净敞口和明细追踪是否与当前口径一致？",
          output: "进入后先看 as_of_date 快照、方向拆分和台账明细 trace。",
          readiness: reviewReadinessLabel("/bank-ledger-dashboard"),
          sourceHint: reviewSourceHint("/bank-ledger-dashboard"),
          reviewSignals: MODULE_REVIEW_SIGNALS["bank-ledger-dashboard"],
          spotlight: true,
        },
        {
          id: "product-category-pnl",
          to: "/product-category-pnl",
          title: "产品损益",
          eyebrow: "看经营贡献和正式产品行",
          question: "本期经营贡献由哪些产品分类拉动，是否需要继续追到调整审计？",
          output: "进入后先看产品分类损益、FTP 与手工调整链路。",
          readiness: reviewReadinessLabel("/product-category-pnl"),
          sourceHint: reviewSourceHint("/product-category-pnl"),
          reviewSignals: MODULE_REVIEW_SIGNALS["product-category-pnl"],
          spotlight: true,
        },
        {
          id: "risk-tensor",
          to: "/risk-tensor",
          title: "风险复核",
          eyebrow: "看 DV01、张量和下钻证据",
          question: "组合风险暴露、估值压力和重点下钻现在集中在哪些维度？",
          output: "进入后先看风险张量、KRD 曲线与信用利差迁移。",
          readiness: reviewReadinessLabel("/risk-tensor"),
          sourceHint: reviewSourceHint("/risk-tensor"),
          reviewSignals: MODULE_REVIEW_SIGNALS["risk-tensor"],
          spotlight: true,
        },
        {
          id: "market-data",
          to: "/market-data",
          title: "市场数据",
          eyebrow: "看盘中上下文",
          question: "现券、资金、存单、期货和信用成交今天发生了什么？",
          output: "进入后先看利率行情、资金曲线和信用利差。",
          readiness: reviewReadinessLabel("/market-data"),
          sourceHint: reviewSourceHint("/market-data"),
          reviewSignals: MODULE_REVIEW_SIGNALS["market-data"],
          spotlight: true,
        },
      ];
    },
    [sanitizedOverviewMetrics],
  );

  const reviewAlerts = useMemo(
    () => buildReviewAlerts(dashboardHome.alerts),
    [dashboardHome.alerts],
  );

  const agentPanelFilters = useMemo(
    () => ({
      allow_partial: allowPartial,
      requested_report_date: reportDate.trim() || null,
    }),
    [allowPartial, reportDate],
  );

  const toolbarModeLabel = isLiveDataFallback
    ? "演示回落"
    : displayMode === "real"
      ? "管理视角"
      : "演示视角";
  const shouldRenderDetailDrilldown = displayMode !== "real" || isDetailDrilldownOpen;
  const handleRefresh = () => {
    if (isLiveDataFallback) {
      setLiveFallbackReason(null);
      setForceMockFallback(false);
      return;
    }
    void snapshotQuery.refetch();
  };

  return (
    <section data-testid="fixed-income-dashboard-page" className="dashboard-home-shell">
      <header
        data-testid="dashboard-home-toolbar"
        className="dashboard-home-toolbar"
      >
        <div className="dashboard-home-toolbar__identity">
          <h1
            data-testid="dashboard-executive-hero-title"
            className="dashboard-home-toolbar__title"
          >
            经营驾驶舱
          </h1>
          <span className="dashboard-home-toolbar__eyebrow">
            报告日 {effectiveReportDate || "最新可用"}
          </span>
        </div>
        <label className="dashboard-home-search dashboard-home-toolbar__search">
          <span aria-hidden="true">⌕</span>
          <input
            aria-label="搜索债券、指标、报告"
            placeholder="搜索债券 / 指标 / 报告"
            value={toolbarSearch}
            onChange={(event) => setToolbarSearch(event.target.value)}
          />
        </label>
        <div className="dashboard-home-actions dashboard-home-toolbar__actions">
          <span
            className={
              displayMode === "real"
                ? "dashboard-home-view-pill dashboard-governance-tone-ok"
                : "dashboard-home-view-pill dashboard-governance-tone-warning"
            }
          >
            {toolbarModeLabel}
          </span>
          <label className="dashboard-home-control">
            <span>报告日</span>
            <input
              aria-label="报告日"
              type="date"
              value={reportDate || effectiveReportDate || ""}
              onChange={(event) => setReportDate(event.target.value)}
              className="dashboard-home-date-input"
              style={tabularNumsStyle}
            />
          </label>
          <label className="dashboard-home-check">
            <input
              aria-label="允许历史日（含缺域）"
              type="checkbox"
              checked={allowPartial}
              onChange={(event) => setAllowPartial(event.target.checked)}
            />
            含缺域
          </label>
          <span aria-hidden="true" className="dashboard-home-actions__divider" />
          <Link
            data-testid="dashboard-bank-ledger-header-link"
            to="/bank-ledger-dashboard"
            className="dashboard-home-action-button dashboard-home-action-button--secondary"
          >
            银行台账
          </Link>
          <Link
            to="/source-preview"
            className="dashboard-home-action-button dashboard-home-action-button--secondary"
          >
            报表中心
          </Link>
          <Link
            to="/platform-config"
            className="dashboard-home-action-button dashboard-home-action-button--secondary"
          >
            中台配置
          </Link>
          <button
            type="button"
            onClick={handleRefresh}
            className="dashboard-home-action-button dashboard-home-action-button--primary"
          >
            {isLiveDataFallback ? "重试实时数据" : "刷新"}
          </button>
        </div>
      </header>

      <section
        data-testid="dashboard-command-deck"
        className="dashboard-command-deck"
      >
        <div
          data-testid="dashboard-executive-hero"
          className="dashboard-command-deck__hero"
        >
          <DashboardJudgmentBand
            verdict={dashboardHome.judgment}
            className="dashboard-executive-hero dashboard-command-deck__judgment"
          />
        </div>

        <aside
          data-testid="dashboard-command-status-stack"
          className="dashboard-home-panel dashboard-command-status"
        >
          <div className="dashboard-home-section-heading">
            <span className="dashboard-home-section-eyebrow">状态 / 可信度</span>
            <h2 className="dashboard-home-section-title">治理状态</h2>
          </div>
          <GovernancePills pills={dashboardHome.kpiRibbon} />
          <div className="dashboard-command-status__grid">
            <article className="dashboard-home-inset dashboard-command-status__metric">
              <span className="dashboard-home-muted-label">待复核</span>
              <strong className="dashboard-home-value">{dashboardHome.reviewCount}</strong>
              <p className="dashboard-home-muted">高/中优先级事项</p>
            </article>
            <article className="dashboard-home-inset dashboard-command-status__metric">
              <span className="dashboard-home-muted-label">快照</span>
              <strong className="dashboard-home-value">
                {dashboardHome.snapshotModeLabel}
              </strong>
              <p className="dashboard-home-muted">
                {snapshotPartialNote || "覆盖状态可用于首屏判断"}
              </p>
            </article>
          </div>
        </aside>
      </section>

      {(dataClient.mode !== "real" || attentionItems.length > 0 || snapshotPartialNote) && (
        <section
          data-testid="dashboard-data-warning"
          className="dashboard-home-warning"
        >
          <div className="dashboard-home-warning__title">
            数据状态 · 需人工复核
          </div>
          {isLiveDataFallback ? (
            <div className="dashboard-home-warning__body">
              实时数据源当前不可用，页面已自动回落到演示数据，避免首页整屏失效。当前错误：
              {liveFallbackReason ?? "Failed to fetch"}
            </div>
          ) : null}
          {!isLiveDataFallback && dataClient.mode !== "real" ? (
            <div className="dashboard-home-warning__body">
              当前页面正在使用模拟数据源，首页数字仅用于界面演示，不应直接作为业务判断依据。
            </div>
          ) : null}
          {attentionItems.length > 0 ? (
            <div className="dashboard-home-warning__body">
              {attentionItems.join("；")}
            </div>
          ) : null}
          {snapshotPartialNote ? (
            <div className="dashboard-home-warning__body">
              {snapshotPartialNote}
            </div>
          ) : null}
        </section>
      )}

      <DashboardCockpitMarketTicker
        className="dashboard-warm-evidence-workspace"
        items={dashboardCockpit.marketTicker}
        isLoading={marketRatesQuery.isLoading}
        isError={marketRatesQuery.isError}
        onRetry={() => void marketRatesQuery.refetch()}
      />

      <details
        data-testid="dashboard-cockpit-supplement"
        className="dashboard-cockpit-supplement dashboard-progressive-disclosure"
        open={isCockpitSupplementOpen}
        onToggle={(event) => setIsCockpitSupplementOpen(event.currentTarget.open)}
      >
        <summary className="dashboard-progressive-disclosure__summary dashboard-cockpit-supplement__summary">
          <div className="dashboard-home-section-heading">
            <span className="dashboard-home-section-eyebrow">同报告日补充</span>
            <h2 className="dashboard-progressive-disclosure__title">债券与组合读面及市场拆解</h2>
          </div>
          <span className="dashboard-progressive-disclosure__description">
            展开查看 KPI 读面带与利率 / 持仓体感；不替代首页快照 KPI。
          </span>
          <span className="dashboard-progressive-disclosure__cue">展开</span>
          <DashboardCockpitSupplementPreview signals={dashboardCockpit.previewSignals} />
        </summary>
        <DashboardCockpitMetricRail
          className="dashboard-warm-kpi-ledger"
          items={dashboardCockpit.metricRail}
          omitHeader
        />
        <DashboardCockpitMainGrid
          className="dashboard-warm-cockpit-main"
          ticker={dashboardCockpit.marketTicker}
          cards={dashboardCockpit.analysisCards}
          waterfall={dashboardCockpit.waterfall}
        />
      </details>
      <DashboardActionQueue alerts={reviewAlerts} effectiveReportDate={effectiveReportDate} />
      <section
        data-testid="dashboard-business-detail-strip"
        className="dashboard-business-detail-strip dashboard-cockpit-business-strip"
      >
        {coreMetricsDateMismatch ? (
          <DashboardSupplementalBlockedSection
            testId="dashboard-core-metrics-blocked"
            title="债券 / 同业核心指标"
            expectedReportDate={effectiveReportDate}
            actualReportDate={coreMetricsQuery.data?.result.report_date ?? "未知"}
          />
        ) : (
          <DashboardCoreMetricsSection
            query={coreMetricsQuery}
            reportDate={effectiveReportDate}
          />
        )}
        {dailyChangesDateMismatch ? (
          <DashboardSupplementalBlockedSection
            testId="dashboard-daily-changes-blocked"
            title="日 / 周 / 月变动"
            expectedReportDate={effectiveReportDate}
            actualReportDate={dailyChangesQuery.data?.result.report_date ?? "未知"}
          />
        ) : (
          <DashboardDailyChangesSection query={dailyChangesQuery} />
        )}
      </section>
      <DashboardCockpitLowerGrid
        className="dashboard-warm-cockpit-assist"
        portfolioMix={dashboardCockpit.portfolioMix}
        riskItems={dashboardCockpit.riskItems}
        calendarItems={dashboardCockpit.calendarItems}
        watchRows={dashboardCockpit.watchRows}
      />
      <DashboardCockpitAccountTable rows={dashboardCockpit.accountRows} />
      <section
        data-testid="dashboard-business-balance-summary"
        className="dashboard-business-balance-summary dashboard-business-balance-summary--terminal dashboard-home-panel"
      >
        <div className="dashboard-business-balance-summary__header">
          <div className="dashboard-home-section-heading">
            <span className="dashboard-home-section-eyebrow">经营 / 资产负债</span>
            <h2 className="dashboard-business-balance-summary__title">经营与资产负债摘要</h2>
          </div>
          <p className="dashboard-home-muted">
            同日报告日的经营口径复核；年度看业务种类，月度看产品分类。
          </p>
        </div>
        <DashboardOverviewHeroStrip metrics={dashboardHome.heroMetrics} />
        <DashboardProductCategoryYtdCards
          state={adapterOutput.productCategoryYtd.state}
          vm={adapterOutput.productCategoryYtd.vm}
          monthlyState={adapterOutput.productCategoryMonthly.state}
          monthlyVm={adapterOutput.productCategoryMonthly.vm}
          onRetry={() => void snapshotQuery.refetch()}
        />
      </section>

      <details
        data-testid="dashboard-detail-drilldown"
        className="dashboard-detail-drilldown dashboard-progressive-disclosure"
        open={isDetailDrilldownOpen}
        onToggle={(event) => setIsDetailDrilldownOpen(event.currentTarget.open)}
      >
        <summary className="dashboard-detail-drilldown__header dashboard-progressive-disclosure__summary">
          <div className="dashboard-home-section-heading">
            <span className="dashboard-home-section-eyebrow">明细穿透</span>
            <h2 className="dashboard-detail-drilldown__title">下钻复核区</h2>
          </div>
          <span className="dashboard-progressive-disclosure__description">
            解释首屏结论、定位数据证据、进入专题页复核
          </span>
          <span className="dashboard-progressive-disclosure__cue">展开</span>
        </summary>

        {shouldRenderDetailDrilldown ? (
          <>
            <div className="dashboard-overview-command-grid">
              <DashboardGlobalJudgmentPanel
                verdict={reviewVerdict}
                metaItems={dashboardHome.reviewMetaItems}
                evidenceLabel={reviewEvidenceLabel}
              />
              <DashboardModuleSnapshotPanel items={moduleSnapshotItems} />
              <DashboardAlertCenterPanel alerts={reviewAlerts} />
            </div>

            <div className="dashboard-overview-support-grid">
              <section
                data-testid="dashboard-governed-surface"
                className="dashboard-governed-surface"
              >
                <PageSectionLead
                  eyebrow="经营贡献"
                  title="经营贡献拆解"
                  description="首页保留一个足够快的经营贡献视图，用来判断是否需要继续进入正式损益拆解工作台；不会在这里伪造未接入的业务结论。"
                  style={{ marginTop: 0 }}
                />
                <Suspense fallback={<LazyPanelFallback title="经营贡献拆解" />}>
                  <PnlAttributionSection
                    attribution={adapterOutput.attribution}
                    onRetry={() => void snapshotQuery.refetch()}
                  />
                </Suspense>
              </section>

              <DashboardTasksCalendarPanels
                tasks={dashboardHome.focus.tasks}
                calendarItems={dashboardHome.focus.calendarItems}
                calendarState={dashboardHome.focus.calendarState}
              />
            </div>

            <BondAnalyticsOverviewMidCharts
              reportDate={effectiveReportDate}
              periodType="MoM"
              assetClass="all"
              accountingClass="all"
            />

            <div className="dashboard-overview-live-grid">
              <div className="dashboard-span-wide">
                <DashboardBondHeadlineSection reportDate={effectiveReportDate} />
              </div>
              <DashboardNewsDigestSection />
              <DashboardBondCounterpartySection reportDate={effectiveReportDate} />
              <DashboardLiabilityCounterpartySection reportDate={effectiveReportDate} />
            </div>

            <DashboardModuleEntryGrid />

            <AgentPanel
              pageId="dashboard"
              reportDate={effectiveReportDate || null}
              currentFilters={agentPanelFilters}
            />
          </>
        ) : null}
      </details>

    </section>
  );
}
