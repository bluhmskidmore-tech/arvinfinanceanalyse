import { lazy, Suspense, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import type { ResultMeta, VerdictPayload } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { PageSectionLead } from "../../../components/page/PagePrimitives";
import { tabularNumsStyle } from "../../../theme/designSystem";
import { adaptDashboard } from "../../executive-dashboard/adapters/executiveDashboardAdapter";
import { sanitizeMetricCopy } from "../../executive-dashboard/lib/sanitizeMetricCopy";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { DashboardBondCounterpartySection } from "../../executive-dashboard/components/DashboardBondCounterpartySection";
import { DashboardBondHeadlineSection } from "../../executive-dashboard/components/DashboardBondHeadlineSection";
import { DashboardLiabilityCounterpartySection } from "../../executive-dashboard/components/DashboardLiabilityCounterpartySection";
import { DashboardNewsDigestSection } from "../../executive-dashboard/components/DashboardNewsDigestSection";
import { BondAnalyticsOverviewMidCharts } from "../../bond-analytics/components/BondAnalyticsOverviewMidCharts";
import {
  DashboardAlertCenterPanel,
  type DashboardCalendarPanelState,
  DashboardGlobalJudgmentPanel,
  DashboardModuleEntryGrid,
  DashboardModuleSnapshotPanel,
  DashboardOverviewHeroStrip,
  DashboardProductCategoryYtdCards,
  DashboardTasksCalendarPanels,
  type DashboardAlert,
  type DashboardHeroMetric,
  type DashboardModuleSnapshotItem,
  type DashboardReviewAlert,
  type DashboardReviewMetaItem,
} from "../dashboard/DashboardOverviewSections";
import {
  DashboardJudgmentBand,
} from "../dashboard/DashboardHomeSections";
import {
  DashboardCockpitLowerGrid,
  DashboardCockpitMainGrid,
  DashboardCockpitMarketTicker,
  DashboardCockpitMetricRail,
} from "../dashboard/DashboardCockpitSections";
import { DashboardCoreMetricsSection } from "../dashboard/DashboardCoreMetricsSection";
import { DashboardDailyChangesSection } from "../dashboard/DashboardDailyChangesSection";
import { GovernancePills, type GovernancePill } from "../dashboard/GovernancePills";
import { buildDashboardCockpitModel } from "../dashboard/dashboardCockpitModel";
import { buildDashboardHomeModel } from "../dashboard/dashboardHomeModel";
import { buildDashboardKeyCalendarModel } from "../dashboard/keyCalendarModel";
import { buildDashboardTodoTasksFromAlerts } from "../dashboard/dashboardTodoModel";
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

function isAttentionMeta(meta: ResultMeta | null | undefined) {
  if (!meta) {
    return false;
  }
  return (
    meta.quality_flag !== "ok" ||
    meta.fallback_mode !== "none" ||
    meta.vendor_status !== "ok"
  );
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

function describeAttention(meta: ResultMeta | null | undefined, title: string) {
  if (!meta || !isAttentionMeta(meta)) {
    return null;
  }

  const parts = [title, metaQualityLabel(meta.quality_flag)];
  if (meta.fallback_mode !== "none") {
    parts.push(`降级=${metaFallbackLabel(meta.fallback_mode)}`);
  }
  if (meta.vendor_status !== "ok") {
    parts.push(`供应商=${metaVendorLabel(meta.vendor_status)}`);
  }
  return parts.join(" / ");
}

function formatSnapshotMode(
  mode: string | undefined,
  isLoading: boolean,
): string {
  if (isLoading) return "载入中";
  if (!mode) return "待定";
  if (mode === "partial") return "部分可用";
  if (mode === "complete") return "完整";
  return mode;
}

function formatHeroDelta(display: string | undefined, fallbackLabel: string) {
  if (display && display.trim() && display.trim() !== "—") {
    return display;
  }
  return fallbackLabel;
}

const DASHBOARD_KEY_CALENDAR_LOOKBACK_DAYS = 7;
const DASHBOARD_KEY_CALENDAR_FORWARD_DAYS = 14;

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

function buildDashboardReviewMetaItems(input: {
  reportDate: string;
  snapshotMode?: string;
  snapshotPartialNote: string | null;
  isSnapshotLoading: boolean;
  isMockMode: boolean;
}): DashboardReviewMetaItem[] {
  const snapshotValue = formatSnapshotMode(input.snapshotMode, input.isSnapshotLoading);
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
  const client = useApiClient();
  const [reportDate, setReportDate] = useState("");
  const [toolbarSearch, setToolbarSearch] = useState("");
  const [allowPartial, setAllowPartial] = useState(false);
  const [isDetailDrilldownOpen, setIsDetailDrilldownOpen] = useState(false);
  const requestedDateLabel = reportDate || "latest";

  const snapshotQuery = useQuery({
    queryKey: ["home-snapshot", client.mode, requestedDateLabel, allowPartial],
    queryFn: () =>
      client.getHomeSnapshot({
        reportDate: reportDate || undefined,
        allowPartial,
      }),
    retry: false,
  });

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

  const overviewMeta = adapterOutput.overview.meta;
  const attributionMeta = adapterOutput.attribution.meta;
  const attentionItems = [
    describeAttention(overviewMeta, "总览"),
    describeAttention(attributionMeta, "贡献拆解"),
  ].filter((item): item is string => Boolean(item));

  const snapshotResult = snapshotQuery.data?.result;
  const effectiveReportDate = useMemo(() => {
    const snap = snapshotResult?.report_date?.trim();
    const manual = reportDate.trim();
    return snap || manual || "";
  }, [reportDate, snapshotResult?.report_date]);

  const snapshotPartialNote = useMemo(() => {
    if (!snapshotResult) return null;
    if (snapshotResult.mode === "partial" || snapshotResult.domains_missing.length > 0) {
      const missing = snapshotResult.domains_missing.length
        ? snapshotResult.domains_missing.join(", ")
        : "";
      return `该日部分业务域不可用${missing ? `: ${missing}` : ""}`;
    }
    return null;
  }, [snapshotResult]);

  const supplementalReportDate = effectiveReportDate || undefined;

  const coreMetricsQuery = useQuery({
    queryKey: ["dashboard", "core-metrics", client.mode, supplementalReportDate ?? "pending-snapshot"],
    queryFn: () => client.getCoreMetrics({ reportDate: supplementalReportDate }),
    retry: false,
    staleTime: 60_000,
    enabled: Boolean(supplementalReportDate),
  });

  const dailyChangesQuery = useQuery({
    queryKey: ["dashboard", "daily-changes", client.mode, supplementalReportDate ?? "pending-snapshot"],
    queryFn: () => client.getDailyChanges({ reportDate: supplementalReportDate }),
    retry: false,
    staleTime: 60_000,
    enabled: Boolean(supplementalReportDate),
  });

  const marketRatesQuery = useQuery({
    queryKey: ["dashboard", "cockpit-market-rates", client.mode],
    queryFn: () => client.getMarketDataRates(),
    retry: false,
    staleTime: 60_000,
  });

  const bondHeadlineQuery = useQuery({
    queryKey: [
      "dashboard",
      "cockpit-bond-headline",
      client.mode,
      supplementalReportDate ?? "pending-snapshot",
    ],
    queryFn: () => client.getBondDashboardHeadlineKpis(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: Boolean(supplementalReportDate),
  });

  const portfolioHeadlinesQuery = useQuery({
    queryKey: [
      "dashboard",
      "cockpit-portfolio-headlines",
      client.mode,
      supplementalReportDate ?? "pending-snapshot",
    ],
    queryFn: () => client.getBondAnalyticsPortfolioHeadlines(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: Boolean(supplementalReportDate),
  });

  const coreMetricsDateMismatch = reportDateMismatch(
    effectiveReportDate,
    coreMetricsQuery.data?.result.report_date,
  );
  const dailyChangesDateMismatch = reportDateMismatch(
    effectiveReportDate,
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
    queryKey: ["research-calendar", client.mode, calendarStartDate, calendarEndDate],
    queryFn: () =>
      client.getResearchCalendarEvents(
        client.mode === "real"
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
          !effectiveReportDate ||
          (researchCalendarQuery.isLoading && !researchCalendarQuery.data),
        calendarIsError: researchCalendarQuery.isError,
        isMockMode: client.mode !== "real",
      }),
    [
      adapterOutput.verdict,
      attributionMeta,
      client.mode,
      coreMetricsQuery.data?.result.report_date,
      dailyChangesQuery.data?.result.report_date,
      effectiveReportDate,
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

  const dashboardCockpit = useMemo(
    () =>
      buildDashboardCockpitModel({
        reportDate: effectiveReportDate,
        snapshotMode: snapshotResult?.mode,
        isMockMode: client.mode !== "real",
        coreMetrics: coreMetricsQuery.data?.result ?? null,
        dailyChanges: dailyChangesQuery.data?.result ?? null,
        bondHeadline: bondHeadlineQuery.data?.result ?? null,
        portfolio: portfolioHeadlinesQuery.data?.result ?? null,
        marketPoints: marketRatesQuery.data?.result.series ?? null,
        calendarItems: researchCalendarQuery.data ?? null,
      }),
    [
      bondHeadlineQuery.data?.result,
      client.mode,
      coreMetricsQuery.data?.result,
      dailyChangesQuery.data?.result,
      effectiveReportDate,
      marketRatesQuery.data?.result.series,
      portfolioHeadlinesQuery.data?.result,
      researchCalendarQuery.data,
      snapshotResult?.mode,
    ],
  );

  const businessBalanceMetrics = useMemo<DashboardHeroMetric[]>(
    () =>
      sanitizedOverviewMetrics.map((metric) => ({
        id: metric.id,
        label: metric.label,
        caliberLabel: metric.caliberLabel,
        value: metric.value.display,
        note: metric.detail,
        delta: formatHeroDelta(metric.delta.display, "读链路"),
        tone: metric.tone,
        history: metric.history,
        linkTo: metric.id === "yield" ? "/pnl-by-business" : null,
      })),
    [sanitizedOverviewMetrics],
  );

  const governancePills = useMemo<GovernancePill[]>(() => {
    const dateValue = effectiveReportDate || "最新可用";
    const dateHint = snapshotResult?.report_date
      ? `归属日期 ${snapshotResult.report_date}`
      : "用户选择 / 默认日期";

    const snapshotMode = formatSnapshotMode(
      snapshotResult?.mode,
      snapshotQuery.isLoading,
    );
    const snapshotValue = snapshotPartialNote ? "含缺域" : snapshotMode;
    const snapshotHint =
      snapshotPartialNote ?? "首页首屏只保留已落地的受治理结果";

    const attentionValue =
      attentionItems.length > 0 ? `${attentionItems.length} 项关注` : "通过";
    const attentionHint =
      attentionItems.length > 0
        ? attentionItems.join(" / ")
        : "无质量、降级或供应商警示";

    const sourceValue = client.mode === "real" ? "真实链路" : "模拟演示";
    const sourceHint =
      client.mode === "real" ? "正式接口" : "仅用于界面演示，不应作为业务判断依据";

    return [
      { id: "report-date", label: "报告日", value: dateValue, tone: "info", hint: dateHint },
      {
        id: "snapshot",
        label: "快照",
        value: snapshotValue,
        tone: snapshotPartialNote ? "warning" : "ok",
        hint: snapshotHint,
      },
      {
        id: "attention",
        label: "治理",
        value: attentionValue,
        tone: attentionItems.length > 0 ? "warning" : "ok",
        hint: attentionHint,
      },
      {
        id: "source",
        label: "读链路",
        value: sourceValue,
        tone: client.mode === "real" ? "ok" : "warning",
        hint: sourceHint,
      },
    ];
  }, [
    attentionItems,
    client.mode,
    effectiveReportDate,
    snapshotPartialNote,
    snapshotQuery.isLoading,
    snapshotResult?.mode,
    snapshotResult?.report_date,
  ]);

  const fallbackVerdict = useMemo<VerdictPayload>(
    () => ({
      conclusion:
        client.mode !== "real" || snapshotPartialNote || attentionItems.length > 0
          ? "数据状态需先复核，再做方向性判断"
          : "当前指标平稳，等待下一组观测",
      tone:
        client.mode !== "real" || snapshotPartialNote || attentionItems.length > 0
          ? "warning"
          : "neutral",
      reasons:
        client.mode !== "real"
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
    [client.mode, snapshotPartialNote, attentionItems.length],
  );

  const reviewVerdict = useMemo(
    () => sanitizeVerdictLinks(adapterOutput.verdict ?? fallbackVerdict),
    [adapterOutput.verdict, fallbackVerdict],
  );

  const reviewMetaItems = useMemo(
    () =>
      buildDashboardReviewMetaItems({
        reportDate: effectiveReportDate,
        snapshotMode: snapshotResult?.mode,
        snapshotPartialNote,
        isSnapshotLoading: snapshotQuery.isLoading,
        isMockMode: client.mode !== "real",
      }),
    [
      client.mode,
      effectiveReportDate,
      snapshotPartialNote,
      snapshotQuery.isLoading,
      snapshotResult?.mode,
    ],
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

  const dashboardAlerts = useMemo<DashboardAlert[]>(() => {
    const alerts: DashboardAlert[] = [];
    const metrics = sanitizedOverviewMetrics;

    if (client.mode !== "real") {
      alerts.push({
        id: "mock-mode",
        title: "当前处于模拟模式",
        detail: "首屏数字仅用于界面演示，不应直接作为业务判断依据。",
        severity: "high",
      });
    }

    attentionItems.forEach((item, index) => {
      alerts.push({
        id: `attention-${index}`,
        title: "治理状态待复核",
        detail: item,
        severity: "high",
      });
    });

    if (snapshotPartialNote) {
      alerts.push({
        id: "partial-note",
        title: "快照含缺域",
        detail: snapshotPartialNote,
        severity: "medium",
      });
    }

    metrics
      .filter((metric) => metric.tone === "warning" || metric.tone === "negative")
      .slice(0, 3)
      .forEach((metric) => {
        alerts.push({
          id: `metric-${metric.id}`,
          title: metric.label,
          detail: `${metric.value.display} / ${metric.detail}`,
          severity: metric.tone === "negative" ? "high" : "medium",
        });
      });

    if (alerts.length === 0) {
      alerts.push({
        id: "no-strong-alert",
        title: "当前无强治理预警",
        detail: "可以先基于首屏指标做方向性判断，再按模块下钻核实来源。",
        severity: "low",
      });
    }

    return alerts.slice(0, 4);
  }, [
    sanitizedOverviewMetrics,
    attentionItems,
    client.mode,
    snapshotPartialNote,
  ]);

  const reviewAlerts = useMemo(
    () => buildReviewAlerts(dashboardAlerts),
    [dashboardAlerts],
  );

  const dashboardCalendar = useMemo(
    () =>
      buildDashboardKeyCalendarModel({
        events: researchCalendarQuery.data,
        isLoading:
          !effectiveReportDate ||
          (researchCalendarQuery.isLoading && !researchCalendarQuery.data),
        isError: researchCalendarQuery.isError,
      }),
    [
      effectiveReportDate,
      researchCalendarQuery.data,
      researchCalendarQuery.isError,
      researchCalendarQuery.isLoading,
    ],
  );

  const dashboardCalendarState = useMemo<DashboardCalendarPanelState>(
    () => ({
      status: dashboardCalendar.status,
      message: dashboardCalendar.message,
    }),
    [dashboardCalendar.message, dashboardCalendar.status],
  );

  const dashboardTasks = useMemo(
    () => buildDashboardTodoTasksFromAlerts(dashboardAlerts),
    [dashboardAlerts],
  );

  const agentPanelFilters = useMemo(
    () => ({
      allow_partial: allowPartial,
      requested_report_date: reportDate.trim() || null,
    }),
    [allowPartial, reportDate],
  );

  const statusReviewCount = dashboardAlerts.filter(
    (alert) => alert.severity === "high" || alert.severity === "medium",
  ).length;
  const toolbarModeLabel = client.mode === "real" ? "管理视角" : "演示视角";
  const shouldRenderDetailDrilldown = client.mode !== "real" || isDetailDrilldownOpen;

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
            债券分析
          </h1>
          <span className="dashboard-home-toolbar__eyebrow">
            报告日 {effectiveReportDate || "最新可用"}
          </span>
        </div>
        <label className="dashboard-home-search">
          <span aria-hidden="true">⌕</span>
          <input
            aria-label="搜索债券、指标、报告"
            placeholder="搜索债券 / 指标 / 报告"
            value={toolbarSearch}
            onChange={(event) => setToolbarSearch(event.target.value)}
          />
        </label>
        <div className="dashboard-home-actions">
          <span
            className={
              client.mode === "real"
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
            onClick={() => void snapshotQuery.refetch()}
            className="dashboard-home-action-button dashboard-home-action-button--primary"
          >
            刷新
          </button>
          <button
            type="button"
            disabled
            className="dashboard-home-action-button dashboard-home-action-button--disabled"
          >
            导出
          </button>
        </div>
      </header>

      <DashboardCockpitMarketTicker
        items={dashboardCockpit.marketTicker}
        isLoading={marketRatesQuery.isLoading}
        isError={marketRatesQuery.isError}
        onRetry={() => void marketRatesQuery.refetch()}
      />

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
          <GovernancePills pills={governancePills} />
          <div className="dashboard-command-status__grid">
            <article className="dashboard-home-inset dashboard-command-status__metric">
              <span className="dashboard-home-muted-label">待复核</span>
              <strong className="dashboard-home-value">{statusReviewCount}</strong>
              <p className="dashboard-home-muted">高/中优先级事项</p>
            </article>
            <article className="dashboard-home-inset dashboard-command-status__metric">
              <span className="dashboard-home-muted-label">快照</span>
              <strong className="dashboard-home-value">
                {formatSnapshotMode(snapshotResult?.mode, snapshotQuery.isLoading)}
              </strong>
              <p className="dashboard-home-muted">
                {snapshotPartialNote || "覆盖状态可用于首屏判断"}
              </p>
            </article>
          </div>
        </aside>
      </section>

      {(client.mode !== "real" || attentionItems.length > 0 || snapshotPartialNote) && (
        <section
          data-testid="dashboard-data-warning"
          className="dashboard-home-warning"
        >
          <div className="dashboard-home-warning__title">
            数据状态 · 需人工复核
          </div>
          {client.mode !== "real" ? (
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

      <DashboardCockpitMetricRail items={dashboardCockpit.metricRail} />
      <DashboardCockpitMainGrid
        ticker={dashboardCockpit.marketTicker}
        cards={dashboardCockpit.analysisCards}
        waterfall={dashboardCockpit.waterfall}
      />
      <DashboardCockpitLowerGrid
        portfolioMix={dashboardCockpit.portfolioMix}
        riskItems={dashboardCockpit.riskItems}
        calendarItems={dashboardCockpit.calendarItems}
        watchRows={dashboardCockpit.watchRows}
      />
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
        <DashboardOverviewHeroStrip metrics={businessBalanceMetrics} />
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
                metaItems={reviewMetaItems}
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
                tasks={dashboardTasks}
                calendarItems={dashboardCalendar.items}
                calendarState={dashboardCalendarState}
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
