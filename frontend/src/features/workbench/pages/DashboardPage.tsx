import { lazy, Suspense, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { VerdictPayload } from "../../../api/contracts";
import { PageSectionLead } from "../../../components/page/PagePrimitives";
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
  DashboardCockpitMetricRail,
} from "../dashboard/DashboardCockpitSections";
import { DashboardCoreMetricsSection } from "../dashboard/DashboardCoreMetricsSection";
import { DashboardDailyChangesSection } from "../dashboard/DashboardDailyChangesSection";
import { GovernancePills } from "../dashboard/GovernancePills";
import {
  buildDashboardCockpitModel,
} from "../dashboard/dashboardCockpitModel";
import { buildDashboardHomeModel } from "../dashboard/dashboardHomeModel";
import { buildDashboardCockpitHomeViewModel } from "../dashboard/dashboardCockpitHomeModel";
import "../dashboard/DashboardCockpitPage.css";
import "../dashboard/dashboardCockpitTheme.css";
import { DashboardCockpitHeader } from "../dashboard/sections/DashboardCockpitHeader";
import { KpiCard } from "../dashboard/sections/KpiCard";
import { MarketPulseStrip } from "../dashboard/sections/MarketPulseStrip";
import { PortfolioOverview } from "../dashboard/sections/PortfolioOverview";
import { AttributionPanel } from "../dashboard/sections/AttributionPanel";
import { RiskAlertPanel } from "../dashboard/sections/RiskAlertPanel";
import { ExposureTable } from "../dashboard/sections/ExposureTable";
import { BalanceSummary } from "../dashboard/sections/BalanceSummary";
import { ProductPnlTrendChart } from "../dashboard/sections/ProductPnlTrendChart";
import { QuickDrilldown } from "../dashboard/sections/QuickDrilldown";
import { DashboardJudgmentStrip } from "../dashboard/sections/DashboardJudgmentStrip";
import { DecisionSidebar } from "../dashboard/sections/DecisionSidebar";
import { DashboardDecisionQueuePanel } from "../dashboard/sections/DashboardDecisionQueuePanel";
import { workbenchNavigation } from "../../../mocks/navigation";
import { AgentPanel } from "../../agent/AgentPanel";
import {
  buildReviewEvidenceLabel,
  reportDateMismatch,
} from "./dashboardPageHelpers";
import { DashboardActionQueue } from "./DashboardActionQueue";
import { DashboardCockpitSupplementPreview } from "./DashboardCockpitSupplementPreview";
import { useDashboardResearchCalendarQuery } from "./useDashboardResearchCalendarQuery";
import { useDashboardSnapshotBoundary } from "./useDashboardSnapshotBoundary";

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
  const [reportDate, setReportDate] = useState("");
  const [toolbarSearch, setToolbarSearch] = useState("");
  const [allowPartial, setAllowPartial] = useState(false);
  const [isDetailDrilldownOpen, setIsDetailDrilldownOpen] = useState(false);
  const [isCockpitSupplementOpen, setIsCockpitSupplementOpen] = useState(false);
  const [isDepthDrawerOpen, setIsDepthDrawerOpen] = useState(false);
  const {
    dataClient,
    displayMode,
    snapshotQuery,
    isLiveDataFallback,
    adapterOutput,
    snapshotResult,
    overviewMeta,
    attributionMeta,
    initialEffectiveReportDate,
    supplementalReportDate,
    refreshSnapshot,
  } = useDashboardSnapshotBoundary({
    reportDate,
    allowPartial,
  });

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

  const portfolioComparisonQuery = useQuery({
    queryKey: [
      "dashboard",
      "cockpit-portfolio-comparison",
      dataClient.mode,
      supplementalReportDate ?? "pending-snapshot",
    ],
    queryFn: () => dataClient.getBondDashboardPortfolioComparison(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: Boolean(supplementalReportDate),
  });

  const creditSpreadMigrationQuery = useQuery({
    queryKey: [
      "dashboard",
      "cockpit-credit-spread-migration",
      dataClient.mode,
      supplementalReportDate ?? "pending-snapshot",
    ],
    queryFn: () => dataClient.getBondAnalyticsCreditSpreadMigration(supplementalReportDate ?? ""),
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

  const bondBucketMonthlyTrendQuery = useQuery({
    queryKey: [
      "dashboard",
      "bond-bucket-monthly-trend",
      dataClient.mode,
      supplementalReportDate ?? "pending-snapshot",
      Number.isFinite(bondBucketAnalysisYear) ? bondBucketAnalysisYear : "pending-year",
    ],
    queryFn: () =>
      dataClient.getPnlByBusinessAnalysis({
        year: bondBucketAnalysisYear,
        asOfDate: supplementalReportDate ?? undefined,
        dimension: "bond_bucket_monthly",
      }),
    retry: false,
    staleTime: 60_000,
    enabled:
      Boolean(supplementalReportDate) &&
      Number.isFinite(bondBucketAnalysisYear) &&
      !isLiveDataFallback &&
      dataClient.mode === "real",
  });

  const coreMetricsDateMismatch = reportDateMismatch(
    initialEffectiveReportDate,
    coreMetricsQuery.data?.result.report_date,
  );
  const dailyChangesDateMismatch = reportDateMismatch(
    initialEffectiveReportDate,
    dailyChangesQuery.data?.result.report_date,
  );

  const { researchCalendarQuery } = useDashboardResearchCalendarQuery({ dataClient });

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
        isMockMode: dataClient.mode !== "real" || isLiveDataFallback,
        heroMetricFallbackDelta: "读链路",
      }),
    [
      adapterOutput.verdict,
      attributionMeta,
      dataClient.mode,
      isLiveDataFallback,
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

  const decisionItemsQuery = useQuery({
    queryKey: [
      "dashboard",
      "cockpit-decision-items",
      dataClient.mode,
      effectiveReportDate || "pending-snapshot",
    ],
    queryFn: () =>
      dataClient.getBalanceAnalysisDecisionItems({
        reportDate: effectiveReportDate,
        positionScope: "all",
        currencyBasis: "CNY",
      }),
    retry: false,
    staleTime: 60_000,
    enabled: Boolean(effectiveReportDate) && !isLiveDataFallback,
  });

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

  const cockpitHome = useMemo(
    () =>
      buildDashboardCockpitHomeViewModel({
        home: dashboardHome,
        cockpit: dashboardCockpit,
        metrics: sanitizedOverviewMetrics,
        snapshotMeta: snapshotQuery.data?.result_meta ?? null,
        marketMeta: marketRatesQuery.data?.result_meta ?? null,
        coreMetrics: coreMetricsQuery.data?.result ?? null,
        bondHeadline: bondHeadlineQuery.data?.result ?? null,
        portfolio: portfolioHeadlinesQuery.data?.result ?? null,
        portfolioComparison: portfolioComparisonQuery.data?.result ?? null,
        creditSpreadMigration: creditSpreadMigrationQuery.data?.result ?? null,
        decisionItems: decisionItemsQuery.data?.result.rows ?? null,
        attribution: adapterOutput.attribution.vm,
        bondBucketMonthly: bondBucketMonthlyTrendQuery.data?.result ?? null,
        useMockFallback: isLiveDataFallback || dataClient.mode !== "real",
      }),
    [
      adapterOutput.attribution.vm,
      bondBucketMonthlyTrendQuery.data?.result,
      bondHeadlineQuery.data?.result,
      coreMetricsQuery.data?.result,
      creditSpreadMigrationQuery.data?.result,
      dashboardCockpit,
      dashboardHome,
      dataClient.mode,
      decisionItemsQuery.data?.result.rows,
      isLiveDataFallback,
      marketRatesQuery.data?.result_meta,
      portfolioComparisonQuery.data?.result,
      portfolioHeadlinesQuery.data?.result,
      sanitizedOverviewMetrics,
      snapshotQuery.data?.result_meta,
    ],
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
    : cockpitHome.dataSource === "mock"
      ? "数据待同步"
      : displayMode === "real"
        ? "管理视角"
        : "演示视角";
  const shouldRenderDetailDrilldown = displayMode !== "real" || isDetailDrilldownOpen;
  return (
    <section
      data-testid="fixed-income-dashboard-page"
      className="dashboard-cockpit-page dashboard-cockpit-page--shell-nav dashboard-home-shell"
    >
      {/* 左侧导航由 WorkbenchShell 统一提供，避免与页面内 DashboardCockpitSidebar 重复 */}
      <div className="dashboard-cockpit-page__frame">
        <div className="dashboard-cockpit-page__main">
          <DashboardCockpitHeader
            viewModel={cockpitHome}
            toolbarSearch={toolbarSearch}
            onSearchChange={setToolbarSearch}
            reportDateInput={reportDate || effectiveReportDate || ""}
            onReportDateChange={setReportDate}
            allowPartial={allowPartial}
            onAllowPartialChange={setAllowPartial}
            modeLabel={toolbarModeLabel}
            onRefresh={refreshSnapshot}
            refreshLabel={isLiveDataFallback ? "重试实时数据" : "刷新"}
          />

          <DashboardJudgmentStrip viewModel={cockpitHome} />

          <section data-testid="dashboard-kpi-band" className="dashboard-cockpit-kpi-band">
            <section
              data-testid="dashboard-kpi-core-group"
              aria-label="经营核心指标"
              className="dashboard-cockpit-kpi-band__group"
            >
              <header className="dashboard-home-section-heading">
                <span className="dashboard-home-section-eyebrow">KPI Zone</span>
                <h2 className="dashboard-home-section-title">经营核心指标</h2>
              </header>
              <div className="dashboard-cockpit-kpi-band__group-cards">
                {cockpitHome.kpiCards.slice(0, 3).map((card) => (
                  <KpiCard key={card.id} card={card} />
                ))}
              </div>
            </section>
            <section
              data-testid="dashboard-kpi-risk-group"
              aria-label="风险约束指标"
              className="dashboard-cockpit-kpi-band__group"
            >
              <header className="dashboard-home-section-heading">
                <span className="dashboard-home-section-eyebrow">KPI Zone</span>
                <h2 className="dashboard-home-section-title">风险约束指标</h2>
              </header>
              <div className="dashboard-cockpit-kpi-band__group-cards">
                {cockpitHome.kpiCards.slice(3).map((card) => (
                  <KpiCard key={card.id} card={card} />
                ))}
              </div>
            </section>
          </section>

          <MarketPulseStrip items={cockpitHome.marketPulse} />

          <section
            data-testid="dashboard-command-deck"
            className="dashboard-command-deck dashboard-cockpit-judgment-strip dashboard-cockpit-deferred"
            hidden
          >
            <div data-testid="dashboard-executive-hero" className="dashboard-command-deck__hero">
              <DashboardJudgmentBand
                verdict={cockpitHome.judgment}
                className="dashboard-executive-hero dashboard-command-deck__judgment"
              />
            </div>
            <aside
              data-testid="dashboard-command-status-stack"
              className="dashboard-home-panel dashboard-command-status"
            >
              <GovernancePills pills={dashboardHome.kpiRibbon} />
            </aside>
          </section>

          <section data-testid="dashboard-operating-layout" className="dashboard-cockpit-home-layout">
            <div
              data-testid="dashboard-operating-main"
              className="dashboard-cockpit-home-layout__main"
            >
              <section data-testid="dashboard-primary-analysis" className="dashboard-cockpit-page__bottom">
                <section data-testid="dashboard-main-triptych" className="dashboard-cockpit-triptych">
                  <PortfolioOverview
                    stats={cockpitHome.portfolioStats}
                    assetBars={cockpitHome.assetBars}
                    centerAum={cockpitHome.portfolioCenterAum}
                    interbankAssets={cockpitHome.interbankAssets}
                    interbankLiabilities={cockpitHome.interbankLiabilities}
                    interbankNetPosition={cockpitHome.interbankNetPosition}
                    interbankNetPositionTone={cockpitHome.interbankNetPositionTone}
                  />
                  <AttributionPanel
                    tabs={cockpitHome.attributionTabs}
                    waterfall={cockpitHome.attributionWaterfall}
                    note={cockpitHome.attributionNote}
                  />
                  <RiskAlertPanel
                    radar={cockpitHome.riskRadar}
                    alertCount={cockpitHome.alertCount}
                    alertCounts={cockpitHome.riskAlertCounts}
                    todos={cockpitHome.todos}
                    watchlist={cockpitHome.watchlist}
                    riskReviewOnly={cockpitHome.riskReviewOnly}
                    usesMockRiskRadar={cockpitHome.usesMockRiskRadar}
                  />
                </section>

                <section data-testid="dashboard-depth-zone" className="dashboard-cockpit-depth">
                  <div className="dashboard-cockpit-depth__charts">
                    <ExposureTable rows={cockpitHome.exposureRows} />
                    <ProductPnlTrendChart data={cockpitHome.productPnl} />
                  </div>
                  <div className="dashboard-cockpit-depth__side">
                    <BalanceSummary metrics={cockpitHome.balanceMetrics} />
                    <QuickDrilldown
                      items={cockpitHome.quickDrilldowns}
                      showStaticNavigationNote={cockpitHome.usesStaticQuickDrilldown}
                    />
                    <DashboardActionQueue
                      alerts={reviewAlerts}
                      effectiveReportDate={effectiveReportDate}
                    />
                  </div>
                </section>

              </section>
            </div>

            <aside
              data-testid="dashboard-decision-rail"
              className="dashboard-cockpit-home-layout__rail"
            >
              <DecisionSidebar viewModel={cockpitHome} isLiveDataFallback={isLiveDataFallback} />
            </aside>
          </section>

          <details
            data-testid="dashboard-depth-drawer"
            className="dashboard-cockpit-depth-drawer dashboard-progressive-disclosure"
            open={isDepthDrawerOpen}
            onToggle={(event) => setIsDepthDrawerOpen(event.currentTarget.open)}
          >
            <summary className="dashboard-progressive-disclosure__summary">
              深钻读面（次级补充）
            </summary>
            <div className="dashboard-cockpit-page__bottom">
              <p className="dashboard-home-muted">
                首屏已展示经营驾驶舱主结构。此处仅保留次级补充入口，避免与首屏判断重复。
              </p>
              {isDepthDrawerOpen ? (
                <section className="dashboard-cockpit-triptych">
                  <DashboardDecisionQueuePanel
                    todos={cockpitHome.todos}
                    showDataWarning={cockpitHome.showDataWarning}
                    dataWarningMessages={cockpitHome.dataWarningMessages}
                    isLiveDataFallback={isLiveDataFallback}
                  />
                </section>
              ) : null}
            </div>
          </details>

          <details
            data-testid="dashboard-cockpit-supplement"
            className="dashboard-cockpit-supplement dashboard-progressive-disclosure"
            open={isCockpitSupplementOpen}
            onToggle={(event) => setIsCockpitSupplementOpen(event.currentTarget.open)}
          >
            <summary className="dashboard-progressive-disclosure__summary">
              同报告日补充读面（展开）
            </summary>
            <DashboardCockpitSupplementPreview signals={dashboardCockpit.previewSignals} />
            <DashboardCockpitMetricRail
              className="dashboard-warm-kpi-ledger"
              items={dashboardCockpit.metricRail}
            />
            <DashboardCockpitMainGrid
              className="dashboard-warm-cockpit-main"
              ticker={dashboardCockpit.marketTicker}
              cards={dashboardCockpit.analysisCards}
              waterfall={dashboardCockpit.waterfall}
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
              className="dashboard-business-balance-summary dashboard-home-panel"
            >
              <DashboardOverviewHeroStrip metrics={dashboardHome.heroMetrics} />
              <DashboardProductCategoryYtdCards
                state={adapterOutput.productCategoryYtd.state}
                vm={adapterOutput.productCategoryYtd.vm}
                monthlyState={adapterOutput.productCategoryMonthly.state}
                monthlyVm={adapterOutput.productCategoryMonthly.vm}
                onRetry={() => void snapshotQuery.refetch()}
              />
            </section>
          </details>

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
        </div>
      </div>
    </section>
  );
}
