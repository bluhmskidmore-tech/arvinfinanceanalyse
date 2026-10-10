import { useEffect, useState } from "react";
import { Collapse } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import "./BalanceAnalysisPage.css";

import { useApiClient } from "../../../api/clientContext";
import type {
  BalanceAnalysisBasisBreakdownRow,
  BalanceAnalysisDecisionItemStatusRow,
  BalanceAnalysisSeverity,
  BalanceAnalysisTableRow,
} from "../../../api/contracts";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import {
  AnalysisGrid,
  DataStatusStrip,
  EvidencePanel,
  PageStateSurface,
} from "../../../components/page/PagePrimitives";
import { PageAsyncSection } from "../../../components/page/PageAsyncSection";
import AdbAnalyticalPreview from "../components/AdbAnalyticalPreview";
import BalanceAnalysisCockpit from "../cockpit/BalanceAnalysisCockpit";
import { BalanceAnalysisToolbar } from "../cockpit/BalanceAnalysisToolbar";
import { SectionHead } from "../../../components/layout";
import { BALANCE_SECTION_NUMBERING } from "../components/balanceSectionNumbering";
import { DeferredBalanceAnalysisGrid } from "../components/DeferredBalanceAnalysisGrid";
import {
  renderDistributionEvidence,
  renderWorkbookEmptyState,
  renderWorkbookPrimaryPanel,
  renderWorkbookSecondaryPanel,
} from "../components/BalanceWorkbookAnalysisPanels";
import {
  renderDecisionItemsPanel,
  renderEventCalendarPanel,
  renderRiskAlertsPanel,
  renderWorkbookRightRailPanel,
} from "../components/BalanceWorkbookGovernancePanels";
import { renderBalanceReconciliationLinkPanel } from "../components/BalanceReconciliationLinkPanel";
import { useBalanceAnalysisData } from "../hooks/useBalanceAnalysisData";
import {
  formatOperationIssueDisplay,
  useBalanceAnalysisActions,
} from "../hooks/useBalanceAnalysisActions";
import { actionButtonStyle } from "./BalanceAnalysisPage.styles";
import {
  type BalanceStateSentinel,
  buildBalanceAnalysisPageModel,
  buildBalanceCockpitViewModel,
  formatBalanceBusinessTextDisplay,
  formatBalanceDecisionWorkflowStatusDisplay,
  formatBalanceGovernedSeverityDisplay,
  formatBalanceWorkbookOperationalSectionKeyDisplay,
  buildBalanceReconciliationLinkModel,
} from "./balanceAnalysisPageModel";
import {
  getBalanceSummaryGridRowId,
  type BalanceAnalysisDetailGridRow,
  type BalanceAnalysisSummaryGridRow,
} from "./balanceAnalysisGridRows";
import {
  balanceBasisBreakdownColDefs,
  balanceDetailColDefs,
  balanceDetailSummaryColDefs,
  balanceSummaryColDefs,
  buildWorkbookGridColumnDefs,
} from "./balanceAnalysisGridColumns";

import { EM_DASH } from "../../../utils/format";
const primaryWorkbookTableKeys = [
  "bond_business_types",
  "rating_analysis",
  "maturity_gap",
  "issuance_business_types",
] as const;

const secondaryWorkbookPanelKeys = [
  "industry_distribution",
  "rate_distribution",
  "counterparty_types",
] as const;

type RightRailWorkbookKey = "event_calendar" | "risk_alerts";

const workbookPanelNotes: Record<(typeof primaryWorkbookTableKeys)[number], string> = {
  bond_business_types: "债券分类优先沿用余额变动的 ZQTZ 资产分类 CNX 期末余额；无联动数据时退回 Workbook 原币面值。",
  rating_analysis: "评级映射与余额变动集中度一致：空评级利率债归 AAA，其他空评级归未映射；金额仍为 Workbook 原币面值，CNY/CNX 控制数看上方联动核对。",
  maturity_gap: "用期限桶直接看资产负债缺口，不再只给纯表格。",
  issuance_business_types: "发行类单独成块，避免和资产端视图混在一起。",
};

const workbookSecondaryPanelNotes: Record<(typeof secondaryWorkbookPanelKeys)[number], string> = {
  industry_distribution: "行业分布优先沿用余额变动集中度的 CNX 期末余额；无联动数据时退回 Workbook 原币面值。",
  rate_distribution: "同一利率桶里并排看债券、同业资产和同业负债。",
  counterparty_types: "按对手方类型看资产、负债和净头寸。",
};

const workbookRightRailNotes: Record<RightRailWorkbookKey, string> = {
  event_calendar: "依据正式结果和工作簿，查看资产、负债到期等事件及其影响。",
  risk_alerts: "查看触及预警阈值的项目，结合相关数据复核风险。",
};

const decisionRailNote = "逐项核对处理建议，记录确认或忽略结果，并跟踪办理进度；处理记录不改变正式业务数据。";

type BalanceAttentionSentinelKey = "stale" | "fallback" | "error";

type BalanceAttentionReason = {
  key: string;
  sentinel: BalanceAttentionSentinelKey;
  detail: string;
};

function firstAttentionDetail(
  reasons: readonly BalanceAttentionReason[],
  sentinel: BalanceAttentionSentinelKey,
  fallback: string,
): string {
  return (
    reasons.find(
      (reason) => reason.sentinel === sentinel && !reason.key.startsWith("status-badge-"),
    )?.detail ??
    reasons.find((reason) => reason.sentinel === sentinel)?.detail ??
    fallback
  );
}

function formatAttentionBasis(value: string | undefined): string {
  if (value === "formal") return "正式口径";
  if (value === "analytical") return "分析口径";
  if (value === "scenario") return "情景口径";
  if (value === "mock") return "模拟口径";
  return "未知口径";
}

function formatAttentionQuality(value: string | undefined): string {
  if (value === "ok") return "正常";
  if (value === "warning") return "预警";
  if (value === "error") return "错误";
  if (value === "stale") return "已过期";
  if (value === "missing") return "缺失";
  return "未提供";
}

function formatAttentionFallback(value: string | undefined): string {
  if (value === "none") return "所选日期的数据";
  if (value === "latest_snapshot") return "最近可用日期的数据";
  return "未提供";
}

function formatEvidenceTraceDisplay(value: string): string {
  if (!value || value === "未提供") {
    return "未提供";
  }
  return "已记录";
}

function formatCurrentUserRoleDisplay(role: string | undefined): string {
  if (role === "viewer") return "查看者";
  if (role === "reviewer") return "复核人";
  if (role === "admin") return "管理员";
  return role || "未识别角色";
}

function formatCurrentUserDisplay(userId: string | undefined): string {
  if (!userId || userId === "anonymous") return "默认提交人";
  return userId;
}

function formatIdentitySourceDisplay(source: string | undefined): string {
  if (source === "fallback") return "兜底身份";
  if (source === "header") return "请求头身份";
  if (source === "session") return "会话身份";
  return source || "未知来源";
}

function formatAdvancedAttributionStatusDisplay(status: string | undefined): string {
  if (status === "not_ready") return "未就绪";
  if (status === "partial") return "部分可用";
  if (status === "ready") return "可用";
  return status ? "已有反馈" : "待返回";
}

function formatAdvancedAttributionModeDisplay(mode: string | undefined): string {
  if (mode === "analytical") return "分析口径";
  if (mode === "scenario") return "情景口径";
  if (mode === "formal") return "正式口径";
  return mode ? "补充口径" : "未提供";
}

function formatAdvancedAttributionInputDisplay(input: string): string {
  if (/yield_curves/i.test(input)) return "收益曲线对齐";
  if (/trade|position|cashflow/i.test(input)) return "成交、持仓与现金流明细";
  if (/benchmark|index/i.test(input)) return "基准指数收益序列";
  if (/pnl/i.test(input)) return "损益实绩对齐";
  return "上游治理输入";
}

function formatAdvancedAttributionWarningDisplay(warning: string): string {
  if (/advanced_attribution_bundle|partial/i.test(warning)) return "高阶归因仅返回部分分析材料。";
  if (/bond_analytics|phase3/i.test(warning)) return "债券分析三阶段结果尚未完整对齐。";
  if (/pnl|bridge|return_decomposition/i.test(warning)) return "归因材料来自已治理摘要，仍需底稿补齐。";
  return "补充提示已记录。";
}

export default function BalanceAnalysisPage() {
  const client = useApiClient();
  const [summaryOffset, setSummaryOffset] = useState(0);
  const [decisionActionError, setDecisionActionError] = useState<string | null>(null);
  const [updatingDecisionKey, setUpdatingDecisionKey] = useState<string | null>(null);
  const [eventTypeFilter, setEventTypeFilter] = useState("all");
  const [riskSeverityFilter, setRiskSeverityFilter] = useState<"all" | BalanceAnalysisSeverity>("all");
  const [selectedDecisionKey, setSelectedDecisionKey] = useState<string | null>(null);
  const [selectedEventCalendarKey, setSelectedEventCalendarKey] = useState<string | null>(null);
  const [selectedRiskAlertKey, setSelectedRiskAlertKey] = useState<string | null>(null);
  const [decisionStatusComment, setDecisionStatusComment] = useState("");
  const {
    selectedReportDate,
    unavailableRequestedReportDate,
    positionScope,
    currencyBasis,
    setSelectedReportDate,
    setPositionScope,
    datesQuery,
    publicationStatusQuery,
    publicationStatus,
    availableReportDates,
    overviewGeneration,
    overviewQuery,
    detailQuery,
    workbookQuery,
    currentUserQuery,
    decisionItemsQuery,
    summaryQuery,
    basisBreakdownQuery,
    adbComparisonQuery,
    advancedAttributionQuery,
    movementDatesQuery,
    movementLinkQuery,
    overview,
    overviewMeta,
    detailMeta,
    decisionItemsMeta,
    workbookMeta,
    summaryMeta,
    movementMeta,
    distributionEvidence,
    currentUser,
    decisionRows,
    workbook,
    summaryTable,
    detailSummaryRows,
    workbookTables,
    primaryWorkbookTables,
    secondaryWorkbookPanelTables,
    filteredRightRailWorkbookTables,
    eventTypeOptions,
    eventCalendarRows,
    riskAlertRows,
    workbookDecisionRows,
    detailSummaryGridRows,
    detailGridRows,
    selectedDecision,
    selectedEventCalendar,
    selectedRiskAlert,
    isBondBusinessLinkedToMovement,
    isIndustryLinkedToMovement,
    movementDateAvailable,
    deferredAnalysisQueriesPending,
    totalPages,
    currentPage,
    adbHref,
    PAGE_SIZE: pageSize,
  } = useBalanceAnalysisData({
    summaryOffset,
    eventTypeFilter,
    riskSeverityFilter,
    selectedDecisionKey,
    selectedEventCalendarKey,
    selectedRiskAlertKey,
  });

  const {
    isRefreshing,
    isExportingCsv,
    isExportingWorkbook,
    refreshStatus,
    refreshError,
    refreshAwaitingPublication,
    handleRefresh,
    handleExport,
    handleWorkbookExport,
  } = useBalanceAnalysisActions(
    { selectedReportDate, positionScope, currencyBasis },
    () =>
      Promise.all([
        datesQuery.refetch(),
        overviewQuery.refetch(),
        decisionItemsQuery.refetch(),
        workbookQuery.refetch(),
        detailQuery.refetch(),
        summaryQuery.refetch(),
        basisBreakdownQuery.refetch(),
        movementDatesQuery.refetch(),
        movementDateAvailable ? movementLinkQuery.refetch() : Promise.resolve(),
        adbComparisonQuery.refetch(),
        advancedAttributionQuery.refetch(),
      ]),
  );

  useEffect(() => {
    setSummaryOffset(0);
  }, [selectedReportDate, positionScope, currencyBasis]);

  useEffect(() => {
    setDecisionActionError(null);
    setSelectedDecisionKey(null);
    setSelectedEventCalendarKey(null);
    setSelectedRiskAlertKey(null);
    setDecisionStatusComment("");
  }, [selectedReportDate, positionScope, currencyBasis]);

  const secondaryWorkbookTables = workbookTables.filter(
    (table) =>
      !primaryWorkbookTableKeys.includes(table.key as (typeof primaryWorkbookTableKeys)[number]) &&
      !secondaryWorkbookPanelKeys.includes(table.key as (typeof secondaryWorkbookPanelKeys)[number]),
  );
  const resultMetaSections = [
    overviewMeta ? { key: "overview", title: "总览", meta: overviewMeta } : null,
    decisionItemsMeta
      ? { key: "decision-items", title: "决策事项", meta: decisionItemsMeta }
      : null,
    workbookMeta ? { key: "workbook", title: "工作簿", meta: workbookMeta } : null,
    summaryMeta ? { key: "summary", title: "汇总", meta: summaryMeta } : null,
    detailMeta ? { key: "detail", title: "明细", meta: detailMeta } : null,
    movementMeta ? { key: "movement", title: "余额变动", meta: movementMeta } : null,
  ].filter(
    (
      section,
    ): section is { key: string; title: string; meta: NonNullable<typeof overviewMeta> } =>
      section !== null,
  );
  const pageModel = buildBalanceAnalysisPageModel({
    clientMode: client.mode,
    selectedReportDate,
    positionScope,
    currencyBasis,
    overview,
    summary: summaryTable,
    decisionItems: decisionItemsQuery.data?.result,
    workbook,
    summaryRows: detailSummaryRows,
    decisionRows,
    workbookDecisionRows,
    eventCalendarRows,
    riskAlertRows,
    metaSections: resultMetaSections,
  });
  const topRiskTitle = riskAlertRows[0]
    ? formatBalanceBusinessTextDisplay(riskAlertRows[0].title)
    : null;
  const topDecisionTitle = decisionRows[0]
    ? formatBalanceBusinessTextDisplay(decisionRows[0].title)
    : null;
  const cockpitViewModel = buildBalanceCockpitViewModel({
    overview,
    workbook,
    stageModel: pageModel.stageModel,
    positionScope,
    decisionCount: decisionRows.length,
    topRiskTitle,
    topDecisionTitle,
  });
  const pageReadModel = pageModel.readModel;
  const hasPublicationDiagnostics = Boolean(
    overviewGeneration || publicationStatus?.reason || publicationStatusQuery.isError,
  );
  const evidenceMetas = resultMetaSections.map((section) => section.meta);
  const balanceAttentionReasons: BalanceAttentionReason[] = [
    ...(publicationStatus?.enabled && selectedReportDate && !overviewGeneration
      ? [
          {
            key: "overview-publication-unavailable",
            sentinel: "stale" as const,
            detail: `所选报告日 ${selectedReportDate} 暂无可用的已发布总览数据，请联系数据负责人核对。`,
          },
        ]
      : []),
    ...(pageReadModel.dateStatus === "mismatch"
      ? [
          {
            key: "date-mismatch",
            sentinel: "error" as const,
            detail: `所选报告日为 ${pageReadModel.requestedReportDate}，实际数据日期为 ${pageReadModel.resolvedReportDate}，请按实际数据日期使用。`,
          },
        ]
      : []),
    // The date badge is excluded unless it is a real mismatch (already raised above);
    // a still-unconfirmed report date is a loading/no-data state, not an anomaly.
    ...pageReadModel.statusBadges
      .filter(
        (badge) =>
          ["danger", "warning"].includes(badge.tone) &&
          (badge.key !== "date" || pageReadModel.dateStatus === "mismatch"),
      )
      .map((badge): BalanceAttentionReason => ({
        key: `status-badge-${badge.key}`,
        sentinel: badge.key === "stale" ? "stale" : badge.key === "fallback" ? "fallback" : "error",
        detail: `数据需核对：${badge.label}`,
      })),
    ...resultMetaSections.flatMap((section): BalanceAttentionReason[] => {
      const reasons: BalanceAttentionReason[] = [];
      if (section.meta.basis !== "formal") {
        reasons.push({
          key: `meta-basis-${section.key}`,
          sentinel: "error",
          detail: `${section.title} 当前为${formatAttentionBasis(section.meta.basis)}，需复核。`,
        });
      }
      if (section.meta.quality_flag === "stale") {
        reasons.push({
          key: `meta-stale-${section.key}`,
          sentinel: "stale",
          detail: `${section.title}数据已过期，请核对后使用。`,
        });
      } else if (section.meta.quality_flag !== "ok") {
        reasons.push({
          key: `meta-quality-${section.key}`,
          sentinel: "error",
          detail: `${section.title}数据${formatAttentionQuality(section.meta.quality_flag)}，请联系数据负责人核对。`,
        });
      }
      if (section.meta.fallback_mode !== "none") {
        reasons.push({
          key: `meta-fallback-${section.key}`,
          sentinel: "fallback",
          detail: `${section.title}使用${formatAttentionFallback(section.meta.fallback_mode)}，实际数据日期为 ${section.meta.as_of_date || "未提供"}，请核对后使用。`,
        });
      }
      return reasons;
    }),
    ...pageReadModel.stateSurfaces
      .filter((state) => ["error", "stale", "fallback-date"].includes(state.variant))
      .map((state): BalanceAttentionReason => ({
        key: `state-surface-${state.key}`,
        sentinel: state.variant === "stale" ? "stale" : state.variant === "fallback-date" ? "fallback" : "error",
        detail: `${state.title}：${state.description}`,
      })),
    ...(refreshError
      ? [
          {
            key: "refresh-error",
            sentinel: "error" as const,
            detail: refreshError,
          },
        ]
      : []),
    ...(decisionActionError
      ? [
          {
            key: "decision-action-error",
            sentinel: "error" as const,
            detail: decisionActionError,
          },
        ]
      : []),
    ...[
      { key: "dates-query", label: "报告日暂不可用，请稍后重试。", query: datesQuery },
      {
        key: "publication-status-query",
        label: "总览数据暂不可用，请稍后重试或联系数据负责人。",
        query: publicationStatusQuery,
      },
      { key: "overview-query", label: "首屏总览暂未返回", query: overviewQuery },
      { key: "workbook-query", label: "工作簿图谱暂未返回", query: workbookQuery },
      { key: "decision-items-query", label: "治理队列暂未返回", query: decisionItemsQuery },
      { key: "summary-query", label: "汇总分页暂未返回", query: summaryQuery },
      { key: "detail-query", label: "明细底稿暂未返回", query: detailQuery },
      { key: "basis-query", label: "口径拆解暂未返回", query: basisBreakdownQuery },
      { key: "adb-query", label: "日均对比暂未返回", query: adbComparisonQuery },
      { key: "advanced-attribution-query", label: "高阶归因暂未返回", query: advancedAttributionQuery },
      { key: "movement-dates-query", label: "余额变动报告日暂未返回", query: movementDatesQuery },
      { key: "movement-link-query", label: "余额变动联动暂未返回", query: movementLinkQuery },
      { key: "current-user-query", label: "当前权限暂未返回", query: currentUserQuery },
    ].flatMap(({ key, label, query }): BalanceAttentionReason[] =>
      query.isError
        ? [
            {
              key,
              sentinel: "error",
              detail: label,
            },
          ]
        : [],
    ),
  ];
  const evidenceLedgerNeedsAttention = balanceAttentionReasons.length > 0;
  const evidenceLedgerSummary =
    evidenceMetas.length > 0
      ? evidenceLedgerNeedsAttention
        ? [
            `${evidenceMetas.length} 组数据`,
            evidenceMetas.every((meta) => meta.basis === "formal") ? "正式口径" : "混合口径",
            evidenceMetas.every((meta) => meta.quality_flag === "ok")
              ? "质量正常"
              : "质量需复核",
            evidenceMetas.every((meta) => meta.fallback_mode === "none")
              ? "未使用替代数据"
              : "存在替代日期",
            evidenceMetas.every((meta) => Boolean(meta.trace_id))
              ? "链路可追溯"
              : "链路待补齐",
          ].join(" · ")
        : [
            `${evidenceMetas.length} 组数据`,
            evidenceMetas.every((meta) => Boolean(meta.trace_id))
              ? "链路可追溯"
              : "链路待补齐",
          ].join(" · ")
      : "等待数据来源与日期信息";
  const attentionStatusBadges = [
    ...pageReadModel.statusBadges.filter(
      (badge) =>
        ["danger", "warning"].includes(badge.tone) &&
        (badge.key !== "date" || pageReadModel.dateStatus === "mismatch"),
    ),
    ...(resultMetaSections.some((section) => section.meta.quality_flag === "warning")
      ? [
          {
            key: "quality-warning",
            label: "数据质量需复核",
            tone: "warning" as const,
          },
        ]
      : []),
  ];
  const latestAvailableReportDate = availableReportDates[0] ?? "";
  const hasUnavailableRequestedReportDate = Boolean(unavailableRequestedReportDate);
  const reportDateUnavailable =
    hasUnavailableRequestedReportDate ||
    (!selectedReportDate && !datesQuery.isLoading && availableReportDates.length === 0);
  const reportDateUnavailableTitle = hasUnavailableRequestedReportDate
    ? "请求的报告日不可用"
    : datesQuery.isError
      ? "报告日暂未接入"
      : "当前没有可用报告日";
  const reportDateUnavailableDescription = hasUnavailableRequestedReportDate
    ? `请求 ${unavailableRequestedReportDate} 不在当前正式报告日列表中，未回退到 ${latestAvailableReportDate}。请重新选择报告日。`
    : datesQuery.isError
      ? "页面暂时拿不到报告日，先收起空指标和底稿区；重新读取后会展示缺口、规模和治理动作。"
      : "等报告日返回后，会自动展示缺口、规模和治理动作；当前先保留筛选和读取入口。";
  const reconciliationLinkModel = buildBalanceReconciliationLinkModel({
    reportDate: selectedReportDate,
    workbook,
    basisRows: basisBreakdownQuery.data?.result.rows ?? [],
    movement: movementLinkQuery.data?.result ?? null,
    movementAvailableForDate: movementDateAvailable,
    isPending:
      deferredAnalysisQueriesPending ||
      basisBreakdownQuery.isLoading ||
      movementDatesQuery.isLoading ||
      (movementDateAvailable && movementLinkQuery.isLoading),
  });

  const hasStaleAttention = balanceAttentionReasons.some((reason) => reason.sentinel === "stale");
  const hasFallbackAttention = balanceAttentionReasons.some((reason) => reason.sentinel === "fallback");
  const hasErrorAttention = balanceAttentionReasons.some((reason) => reason.sentinel === "error");
  const stateSentinels: BalanceStateSentinel[] = [
    {
      key: "stale",
      label: "已过期",
      active: hasStaleAttention,
      status: hasStaleAttention ? "error" : "ready",
      detail: firstAttentionDetail(balanceAttentionReasons, "stale", "未发现过期数据。"),
    },
    {
      key: "fallback",
      label: "替代日期",
      active: hasFallbackAttention,
      status: hasFallbackAttention ? "error" : "ready",
      detail: firstAttentionDetail(balanceAttentionReasons, "fallback", "未使用替代日期的数据。"),
    },
    {
      key: "error",
      label: "需处理",
      active: hasErrorAttention,
      status: hasErrorAttention ? "error" : "ready",
      detail: firstAttentionDetail(balanceAttentionReasons, "error", "未发现待处理事项。"),
    },
  ];

  async function handleDecisionStatusUpdate(
    row: BalanceAnalysisDecisionItemStatusRow,
    status: "confirmed" | "dismissed",
  ) {
    if (!selectedReportDate) {
      return;
    }
    setDecisionActionError(null);
    setUpdatingDecisionKey(row.decision_key);
    setSelectedEventCalendarKey(null);
    setSelectedRiskAlertKey(null);
    setSelectedDecisionKey(row.decision_key);
    try {
      await client.updateBalanceAnalysisDecisionStatus({
        reportDate: selectedReportDate,
        positionScope: "all",
        currencyBasis,
        decisionKey: row.decision_key,
        status,
        comment: decisionStatusComment.trim() || undefined,
      });
      await Promise.all([decisionItemsQuery.refetch(), currentUserQuery.refetch()]);
    } catch {
      setDecisionActionError(formatOperationIssueDisplay("decision"));
    } finally {
      setUpdatingDecisionKey(null);
    }
  }

  return (
    <section
      data-testid="balance-analysis-page"
      data-moss-theme-scope="balance-analysis"
      className="balance-analysis-page"
    >
      <BalanceAnalysisToolbar
        reportDates={availableReportDates}
        selectedReportDate={selectedReportDate}
        positionScope={positionScope}
        sourceBadge={pageReadModel.sourceBadge}
        calibration={overview?.calibration}
        isRefreshing={isRefreshing}
        isExportingCsv={isExportingCsv}
        isExportingWorkbook={isExportingWorkbook}
        onReportDateChange={setSelectedReportDate}
        onPositionScopeChange={setPositionScope}
        onRefresh={() => void handleRefresh()}
        onExportCsv={() => void handleExport()}
        onExportWorkbook={() => void handleWorkbookExport()}
      />

      {attentionStatusBadges.length > 0 ? (
        <DataStatusStrip
          testId="balance-analysis-data-status"
          className="balance-analysis-data-status"
        >
          {attentionStatusBadges.map((badge) => (
            <span key={badge.key} className="balance-analysis-status-badge" data-tone={badge.tone}>
              {badge.label}
            </span>
          ))}
        </DataStatusStrip>
      ) : null}

      {(refreshStatus || refreshError) && (
        <PageStateSurface
          variant={
            refreshError
              ? "error"
              : isRefreshing
                ? "loading"
                : refreshAwaitingPublication
                  ? "stale"
                  : "neutral"
          }
          title={refreshError ? "刷新未完成" : isRefreshing ? "刷新进行中" : "计算任务完成"}
          description={
            refreshError ??
            (refreshAwaitingPublication
              ? "当前页面仍显示已发布的数据。请在数据中心完成发布后重新进入本页。"
              : refreshStatus)
          }
          testId="balance-analysis-refresh-state"
          className="balance-analysis-refresh-state"
        />
      )}

      {publicationStatusQuery.isError ? (
        <PageStateSurface
          variant="error"
          title="总览数据暂不可用"
          description="请稍后重试或联系数据负责人；其他分析结果请按各自数据日期核对。"
          className="balance-analysis-refresh-state"
        />
      ) : publicationStatus?.enabled && selectedReportDate && !overviewGeneration ? (
        <PageStateSurface
          variant="stale"
          title="所选报告日暂无可用的已发布总览数据"
          description={`报告日 ${selectedReportDate} 的总览暂不可用，请联系数据负责人核对；其他分析结果请按各自数据日期核对。`}
          className="balance-analysis-refresh-state"
        />
      ) : overviewGeneration ? (
        <p className="balance-analysis-topbar__subtitle">
          总览采用已发布数据，其他分析结果请按各自数据日期核对。
        </p>
      ) : null}

      {reportDateUnavailable ? (
        <section
          data-testid="balance-analysis-report-date-empty"
          className="balance-analysis-empty"
          data-state="empty"
        >
          <b>{reportDateUnavailableTitle}</b>
          <small>{reportDateUnavailableDescription}</small>
          <button
            type="button"
            className="balance-analysis-btn"
            onClick={() => void datesQuery.refetch()}
          >
            <ReloadOutlined aria-hidden />
            重新读取报告日
          </button>
        </section>
      ) : (
        <>
          <BalanceAnalysisCockpit
            model={cockpitViewModel}
            stageModel={pageModel.stageModel}
            headlineCards={pageModel.headlineAmountCards}
          />

          {stateSentinels.some((sentinel) => sentinel.active) ? (
            <div
              data-testid="balance-analysis-abnormal-sentinels"
              className="balance-analysis-abnormal-sentinels"
            >
              <div className="balance-analysis-abnormal-sentinels__head">
                <strong>需处理事项</strong>
              </div>
              <div className="balance-analysis-abnormal-sentinels__list">
                {stateSentinels
                  .filter((sentinel) => sentinel.active)
                  .map((sentinel) => (
                    <span
                      key={sentinel.key}
                      className="balance-analysis-abnormal-sentinels__item"
                      data-status={sentinel.status}
                    >
                      <b>{sentinel.label}</b>
                      <small>{sentinel.detail}</small>
                    </span>
                  ))}
              </div>
            </div>
          ) : null}

          <details
            className="balance-analysis-details balance-analysis-details--sec balance-analysis-evidence-details"
            data-testid="balance-analysis-evidence-details"
            open={evidenceLedgerNeedsAttention}
          >
        <summary className="balance-analysis-details__summary">
          <h2 className="balance-analysis-details__title">证据链路</h2>
          <strong className="balance-analysis-details__meta">{evidenceLedgerSummary}</strong>
          <span className="balance-analysis-details__hint">
            查看数据来源、口径与日期；需要处理的问题在此展开。
          </span>
        </summary>
        <AnalysisGrid columns={2} className="balance-analysis-ledger-grid">
          <EvidencePanel heading="数据依据" className="balance-analysis-ledger-panel">
            <p className="balance-analysis-ledger-copy">{pageReadModel.conclusionDetail}</p>
            <div className="balance-analysis-state-stack">
              {pageReadModel.stateSurfaces.map((state) => (
                <PageStateSurface
                  key={state.key}
                  variant={state.variant}
                  title={state.title}
                  description={state.description}
                />
              ))}
            </div>
          </EvidencePanel>
          <EvidencePanel heading="证据账本" className="balance-analysis-ledger-panel">
            <div className="balance-analysis-evidence-ledger">
              {pageReadModel.evidenceCards.length > 0 ? (
                pageReadModel.evidenceCards.map((card) => (
                  <article key={card.key} className="balance-analysis-evidence-card">
                    <div className="balance-analysis-evidence-card__top">
                      <strong>{card.title}</strong>
                      <span>{card.basisLabel}</span>
                    </div>
                    <dl>
                      <div>
                        <dt>结果类型</dt>
                        <dd>{card.resultKind}</dd>
                      </div>
                      <div>
                        <dt>质量</dt>
                        <dd>{card.qualityLabel}</dd>
                      </div>
                      <div>
                        <dt>日期替代情况</dt>
                        <dd>{card.fallbackLabel}</dd>
                      </div>
                      <div>
                        <dt>数据日</dt>
                        <dd>{card.asOfDate}</dd>
                      </div>
                      <div>
                        <dt>追踪记录</dt>
                        <dd title={card.traceId}>{formatEvidenceTraceDisplay(card.traceId)}</dd>
                      </div>
                    </dl>
                  </article>
                ))
              ) : (
                <PageStateSurface
                  variant="loading"
                  title="证据账本等待数据"
                  description="数据依据暂未齐备，取得后将在这里展示来源、质量及实际数据日期。"
                />
              )}
            </div>
          </EvidencePanel>
        </AnalysisGrid>
      </details>

      <div data-testid="balance-analysis-summary" className="balance-analysis-hidden-summary">
        {String(overview?.detail_row_count ?? 0)} {String(overview?.summary_row_count ?? 0)}{" "}
        {pageModel.headlineAmountCards.map((card) => card.value).join(" ")}
      </div>

      <details
        data-testid="balance-analysis-formal-summary-details"
        className="balance-analysis-details balance-analysis-details--sec"
      >
        <summary className="balance-analysis-details__summary">
          <h2 className="balance-analysis-details__title">资产负债汇总与明细</h2>
          <span className="balance-analysis-details__hint">
            查看资产负债规模汇总，并逐项核对组合、分类及持仓明细。
          </span>
        </summary>
        <div className="balance-analysis-details__content">
        <PageAsyncSection
          title="资产负债汇总"
          isLoading={
            datesQuery.isLoading ||
            overviewQuery.isLoading ||
            summaryQuery.isLoading
          }
          isError={
            datesQuery.isError ||
            overviewQuery.isError ||
            summaryQuery.isError
          }
          isEmpty={!summaryQuery.isLoading && (summaryTable?.rows.length ?? 0) === 0}
          onRetry={() => {
            void Promise.all([
              datesQuery.refetch(),
              overviewQuery.refetch(),
              workbookQuery.refetch(),
              detailQuery.refetch(),
              summaryQuery.refetch(),
            ]);
          }}
        >
          <DeferredBalanceAnalysisGrid<BalanceAnalysisTableRow>
            data-testid="balance-analysis-summary-table"
            height={360}
            rowData={summaryTable?.rows ?? []}
            columnDefs={balanceSummaryColDefs}
            getRowId={(p) => getBalanceSummaryGridRowId(p.data)}
          />
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-end",
              gap: 10,
              marginTop: 12,
            }}
          >
            <button
              type="button"
              onClick={() => setSummaryOffset((current) => Math.max(0, current - pageSize))}
              disabled={summaryOffset === 0}
              style={actionButtonStyle}
            >
              上一页
            </button>
            <span>{`第 ${currentPage} / ${totalPages} 页`}</span>
            <button
              type="button"
              onClick={() => setSummaryOffset((current) => current + pageSize)}
              disabled={summaryOffset + pageSize >= (summaryTable?.total_rows ?? 0)}
              style={actionButtonStyle}
            >
              下一页
            </button>
          </div>
          <div className="balance-analysis-detail-drilldown">
            <div className="balance-analysis-detail-drilldown__eyebrow">明细下钻预留</div>
            {deferredAnalysisQueriesPending ? (
              <div>正在加载资产负债明细…</div>
            ) : !detailQuery.isLoading &&
            !detailQuery.isError &&
            detailSummaryGridRows.length > 0 ? (
              <div className="balance-analysis-detail-drilldown__summary">
                <div className="balance-analysis-detail-drilldown__eyebrow">
                  明细底稿返回的汇总切片
                </div>
                <DeferredBalanceAnalysisGrid<BalanceAnalysisSummaryGridRow>
                  data-testid="balance-analysis-detail-summary-grid"
                  height={200}
                  rowData={detailSummaryGridRows}
                  columnDefs={balanceDetailSummaryColDefs}
                  getRowId={(p) => p.data.__gridId}
                />
              </div>
            ) : null}
            {deferredAnalysisQueriesPending ? null : detailQuery.isError ? (
              <div className="balance-analysis-detail-drilldown__error">
                明细下钻暂时不可用，汇总驾驶舱仍可继续使用。
              </div>
            ) : detailQuery.isLoading ? (
              <div className="balance-analysis-detail-drilldown__loading">明细下钻加载中…</div>
            ) : (
              <DeferredBalanceAnalysisGrid<BalanceAnalysisDetailGridRow>
                data-testid="balance-analysis-table"
                className="balance-analysis-detail-grid"
                height={320}
                rowData={detailGridRows}
                columnDefs={balanceDetailColDefs}
                getRowId={(p) => p.data.__gridId}
              />
            )}
          </div>
        </PageAsyncSection>
        </div>
      </details>

      <details
        data-testid="balance-analysis-supplemental-panels"
        className="balance-analysis-details balance-analysis-details--sec"
      >
        <summary className="balance-analysis-details__summary">
          <h2 className="balance-analysis-details__title">辅助分析口径</h2>
          <span className="balance-analysis-details__hint">
            通过日均分析、会计口径拆解和高阶归因解释变化，仅供分析参考，不替代正式结论。
          </span>
        </summary>
        <div className="balance-analysis-details__content balance-analysis-supplemental__grid">
          <PageAsyncSection
            title="日均分析预览"
            isLoading={deferredAnalysisQueriesPending || adbComparisonQuery.isLoading}
            isError={adbComparisonQuery.isError}
            isEmpty={false}
            onRetry={() => void adbComparisonQuery.refetch()}
          >
            {adbComparisonQuery.data ? <AdbAnalyticalPreview comparison={adbComparisonQuery.data} href={adbHref} /> : null}
          </PageAsyncSection>
          <PageAsyncSection
            title="按会计口径分解"
            isLoading={deferredAnalysisQueriesPending || basisBreakdownQuery.isLoading}
            isError={basisBreakdownQuery.isError}
            isEmpty={false}
            onRetry={() => void basisBreakdownQuery.refetch()}
          >
            <DeferredBalanceAnalysisGrid<BalanceAnalysisBasisBreakdownRow>
              data-testid="balance-analysis-basis-breakdown-grid"
              height={240}
              rowData={basisBreakdownQuery.data?.result.rows ?? []}
              columnDefs={balanceBasisBreakdownColDefs}
              getRowId={(p) =>
                `${p.data.source_family}-${p.data.invest_type_std}-${p.data.accounting_basis}-${p.data.position_scope}-${p.data.currency_basis}`
              }
            />
          </PageAsyncSection>
          <PageAsyncSection
            title="高阶归因"
            isLoading={deferredAnalysisQueriesPending || advancedAttributionQuery.isLoading}
            isError={advancedAttributionQuery.isError}
            isEmpty={false}
            onRetry={() => void advancedAttributionQuery.refetch()}
          >
            {advancedAttributionQuery.data?.result ? (
              (() => {
                const attribution = advancedAttributionQuery.data.result;
                const inputLabels = Array.from(
                  new Set(attribution.missing_inputs.map(formatAdvancedAttributionInputDisplay)),
                );
                const warningLabels = Array.from(
                  new Set(attribution.warnings.map(formatAdvancedAttributionWarningDisplay)),
                );

                return (
                  <div className="balance-analysis-advanced-attribution-summary">
                    <div>
                      <strong>归因可用性</strong>：
                      {formatAdvancedAttributionStatusDisplay(attribution.status)} ·{" "}
                      {formatAdvancedAttributionModeDisplay(attribution.mode)}
                    </div>
                    <div>
                      <strong>缺口材料</strong>：缺 {attribution.missing_inputs.length} 项输入
                      {inputLabels.length > 0 ? (
                        <ul className="balance-analysis-advanced-attribution-summary__list">
                          {inputLabels.slice(0, 4).map((label) => (
                            <li key={label}>{label}</li>
                          ))}
                        </ul>
                      ) : (
                        <span>，关键输入已齐备。</span>
                      )}
                    </div>
                    <div>
                      <strong>提示</strong>：{attribution.warnings.length} 条
                      {warningLabels.length > 0 ? (
                        <ul className="balance-analysis-advanced-attribution-summary__list">
                          {warningLabels.slice(0, 4).map((label) => (
                            <li key={label}>{label}</li>
                          ))}
                        </ul>
                      ) : (
                        <span>，暂无补充提示。</span>
                      )}
                    </div>
                  </div>
                );
              })()
            ) : null}
          </PageAsyncSection>
        </div>
      </details>

      <div className="balance-analysis-sec balance-analysis-governance-workbench-section">
        <SectionHead
          title="待处理事项与工作簿"
          numbered={BALANCE_SECTION_NUMBERING}
          note="核对待处理事项、到期事件和风险预警，并在工作簿中查看相关数据。"
        />
        <PageAsyncSection
          title="待处理事项"
          isLoading={
            datesQuery.isLoading ||
            workbookQuery.isLoading ||
            decisionItemsQuery.isLoading
          }
          isError={
            datesQuery.isError ||
            workbookQuery.isError ||
            decisionItemsQuery.isError
          }
          isEmpty={!workbookQuery.isLoading && (workbook?.tables.length ?? 0) === 0}
          onRetry={() => {
            void Promise.all([
              datesQuery.refetch(),
              workbookQuery.refetch(),
              currentUserQuery.refetch(),
              decisionItemsQuery.refetch(),
            ]);
          }}
        >
          <div data-testid="balance-analysis-workbook-cockpit" className="balance-analysis-workbook-cockpit">
            <details className="balance-analysis-details balance-analysis-details--sub balance-analysis-workbook-main-details">
              <summary className="balance-analysis-details__summary">
                <h3 className="balance-analysis-details__title">资产负债结构与分布</h3>
                <span className="balance-analysis-details__hint">
                  查看债券分类、评级分布和期限缺口，分析资产负债结构。
                </span>
              </summary>
              <div className="balance-analysis-workbook-main">
                {renderBalanceReconciliationLinkPanel(reconciliationLinkModel)}
                <div
                  data-testid="balance-analysis-workbook-primary-grid"
                  className="balance-analysis-workbook-primary-grid"
                >
                  {primaryWorkbookTables.map((table) => (
                    <article
                      key={table.key}
                      data-testid={`balance-analysis-workbook-panel-${table.key}`}
                      className="balance-analysis-workbook-panel"
                    >
                      <div className="balance-analysis-workbook-panel__header">
                        <div>
                          <div className="balance-analysis-workbook-panel__title">
                            {formatBalanceBusinessTextDisplay(table.title)}
                          </div>
                          <p className="balance-analysis-workbook-panel__note">
                            {workbookPanelNotes[table.key as (typeof primaryWorkbookTableKeys)[number]]}
                          </p>
                        </div>
                        <span className="balance-analysis-workbook-panel__badge">
                          {table.key === "bond_business_types" && isBondBusinessLinkedToMovement ? "movement" : "workbook"}
                        </span>
                      </div>
                      {table.key === "bond_business_types"
                        ? renderDistributionEvidence(distributionEvidence.bond_business_types, table.key)
                        : null}
                      {renderWorkbookPrimaryPanel(table)}
                    </article>
                  ))}
                </div>

                <div
                  data-testid="balance-analysis-workbook-secondary-panels"
                  className="balance-analysis-workbook-secondary-panels"
                >
                  {secondaryWorkbookPanelTables.map((table) => (
                    <article
                      key={table.key}
                      data-testid={`balance-analysis-workbook-panel-${table.key}`}
                      className="balance-analysis-workbook-panel"
                    >
                      <div className="balance-analysis-workbook-panel__header">
                        <div>
                          <div className="balance-analysis-workbook-panel__title">
                            {formatBalanceBusinessTextDisplay(table.title)}
                          </div>
                          <p className="balance-analysis-workbook-panel__note">
                            {workbookSecondaryPanelNotes[table.key as (typeof secondaryWorkbookPanelKeys)[number]]}
                          </p>
                        </div>
                        <span className="balance-analysis-workbook-panel__badge">
                          {table.key === "industry_distribution" && isIndustryLinkedToMovement ? "movement" : "supporting"}
                        </span>
                      </div>
                      {table.key === "industry_distribution"
                        ? renderDistributionEvidence(distributionEvidence.industry_distribution, table.key)
                        : null}
                      {renderWorkbookSecondaryPanel(table)}
                    </article>
                  ))}
                </div>
              </div>
            </details>

            <aside
              data-testid="balance-analysis-right-rail"
              className="balance-analysis-right-rail"
              aria-label="资产负债治理闭环"
            >
              <article
                data-testid="balance-analysis-right-rail-panel-decision_items"
                className="balance-analysis-right-rail__panel balance-analysis-right-rail__panel--decision"
              >
                <div className="balance-analysis-governance-panel__header">
                  <div>
                    <div className="balance-analysis-governance-panel__title">决策事项</div>
                    <p className="balance-analysis-governance-panel__note">
                      {decisionRailNote}
                    </p>
                  </div>
                  <span className="balance-analysis-governance-panel__badge">{decisionRows.length} 项</span>
                </div>
                {decisionActionError ? (
                  <div
                    data-testid="balance-analysis-decision-error"
                    style={{
                      marginBottom: 12,
                      borderRadius: 2,
                      border: "1px solid var(--ib-hairline)",
                      borderLeft: "2px solid var(--ib-warn)",
                      background: "var(--ib-paper)",
                      color: "var(--ib-ink)",
                      padding: 12,
                      fontSize: 13,
                    }}
                  >
                    {decisionActionError}
                  </div>
                ) : null}
                <label
                  className="balance-analysis-decision-note"
                >
                  <span>决策备注（可选，随确认/忽略提交）</span>
                  <textarea
                    value={decisionStatusComment}
                    onChange={(event) => setDecisionStatusComment(event.target.value)}
                    rows={2}
                    className="balance-analysis-decision-note__input"
                  />
                </label>
                {currentUser ? (
                  <div
                    data-testid="balance-analysis-current-user"
                    className="balance-analysis-current-user"
                    title={`身份来源：${formatIdentitySourceDisplay(currentUser.identity_source)}`}
                  >
                    <span>提交人</span>
                    <strong>{formatCurrentUserDisplay(currentUser.user_id)}</strong>
                    <span>{formatCurrentUserRoleDisplay(currentUser.role)}</span>
                  </div>
                ) : null}
                {renderDecisionItemsPanel(decisionRows, {
                  selectedKey: selectedDecisionKey,
                  updatingKey: updatingDecisionKey,
                  onSelect: (row) => {
                    setSelectedEventCalendarKey(null);
                    setSelectedRiskAlertKey(null);
                    setSelectedDecisionKey(row.decision_key);
                  },
                  onUpdateStatus: (row, status) => {
                    void handleDecisionStatusUpdate(row, status);
                  },
                })}
              </article>
              {filteredRightRailWorkbookTables.map((table) => (
                <article
                  key={table.key}
                  data-testid={`balance-analysis-right-rail-panel-${table.key}`}
                  className={`balance-analysis-right-rail__panel ${
                    table.section_kind === "event_calendar"
                      ? "balance-analysis-right-rail__panel--event"
                      : table.section_kind === "risk_alerts"
                        ? "balance-analysis-right-rail__panel--risk"
                        : "balance-analysis-right-rail__panel--support"
                  }`}
                >
                  <div className="balance-analysis-governance-panel__header">
                    <div>
                      <div className="balance-analysis-governance-panel__title">
                        {formatBalanceBusinessTextDisplay(table.title)}
                      </div>
                      <p className="balance-analysis-governance-panel__note">
                        {workbookRightRailNotes[table.key as RightRailWorkbookKey]}
                      </p>
                    </div>
                    <span className="balance-analysis-governance-panel__badge">
                      {table.rows.length}
                      {table.section_kind === "event_calendar" ? " 件" : " 条"}
                    </span>
                  </div>
                  {table.section_kind === "event_calendar" ? (
                    <>
                      <div className="balance-analysis-governance-filter-row">
                        <label>
                          <span className="balance-analysis-governance-filter-row__label">
                            事件类型
                          </span>
                          <select
                            aria-label="balance-event-type-filter"
                            value={eventTypeFilter}
                            onChange={(event) => setEventTypeFilter(event.target.value)}
                            className="balance-analysis-governance-select"
                          >
                            <option value="all">全部</option>
                            {eventTypeOptions.map((eventType) => (
                              <option key={eventType} value={eventType}>
                                {formatBalanceBusinessTextDisplay(eventType)}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                      {renderEventCalendarPanel(table, {
                        onSelect: (row) => {
                          setSelectedDecisionKey(null);
                          setSelectedRiskAlertKey(null);
                          setSelectedEventCalendarKey(`${row.event_date}:${row.title}`);
                        },
                        selectedKey: selectedEventCalendarKey,
                      })}
                    </>
                  ) : table.section_kind === "risk_alerts" ? (
                    <>
                      <div className="balance-analysis-governance-filter-row">
                        <label>
                          <span className="balance-analysis-governance-filter-row__label">
                            预警等级
                          </span>
                          <select
                            aria-label="balance-risk-severity-filter"
                            value={riskSeverityFilter}
                            onChange={(event) =>
                              setRiskSeverityFilter(event.target.value as "all" | BalanceAnalysisSeverity)
                            }
                            className="balance-analysis-governance-select"
                          >
                            <option value="all">全部</option>
                            <option value="high">高</option>
                            <option value="medium">中</option>
                            <option value="low">低</option>
                          </select>
                        </label>
                      </div>
                      {renderRiskAlertsPanel(table, {
                        onSelect: (row) => {
                          setSelectedDecisionKey(null);
                          setSelectedEventCalendarKey(null);
                          setSelectedRiskAlertKey(`${row.severity}:${row.title}`);
                        },
                        selectedKey: selectedRiskAlertKey,
                      })}
                    </>
                  ) : (
                    renderWorkbookRightRailPanel(table)
                  )}
                </article>
              ))}
              <article
                data-testid="balance-analysis-right-rail-drilldown"
                className="balance-analysis-right-rail__panel balance-analysis-right-rail__panel--drilldown"
              >
                <div className="balance-analysis-governance-panel__header">
                  <div>
                    <div className="balance-analysis-governance-panel__title">详情下钻</div>
                    <p className="balance-analysis-governance-panel__note">
                      选择决策、事件或预警后，在这里查看完整说明和证据。
                    </p>
                  </div>
                  <span className="balance-analysis-governance-panel__badge">详情</span>
                </div>
                {selectedDecision ? (
                  <div
                    data-testid="balance-analysis-right-rail-drilldown-decision"
                    className="balance-analysis-right-rail-drilldown-detail"
                  >
                    <div className="balance-analysis-right-rail-drilldown-detail__title">
                      {formatBalanceBusinessTextDisplay(selectedDecision.title)}
                    </div>
                    <div className="balance-analysis-right-rail-drilldown-detail__status">
                      处理进度：{formatBalanceDecisionWorkflowStatusDisplay(selectedDecision.latest_status.status)}
                    </div>
                    <div className="balance-analysis-right-rail-drilldown-detail__body balance-analysis-right-rail-drilldown-detail__body--relaxed">
                      {formatBalanceBusinessTextDisplay(selectedDecision.reason)}
                    </div>
                    <div className="balance-analysis-right-rail-drilldown-detail__meta">
                      <span>{formatBalanceWorkbookOperationalSectionKeyDisplay(selectedDecision.source_section)}</span>
                      <span>{selectedDecision.rule_id}</span>
                      <span>{selectedDecision.rule_version}</span>
                    </div>
                    <div className="balance-analysis-right-rail-drilldown-detail__audit">
                      <span>
                        更新人：{" "}
                        {selectedDecision.latest_status.updated_by
                          ? selectedDecision.latest_status.updated_by
                          : "未更新"}
                      </span>
                      <span>
                        更新时间：{" "}
                        {selectedDecision.latest_status.updated_at
                          ? selectedDecision.latest_status.updated_at
                          : "暂无"}
                      </span>
                      {selectedDecision.latest_status.comment ? (
                        <span>{selectedDecision.latest_status.comment}</span>
                      ) : null}
                    </div>
                  </div>
                ) : selectedEventCalendar ? (
                  <div
                    data-testid="balance-analysis-right-rail-drilldown-event"
                    className="balance-analysis-right-rail-drilldown-detail"
                  >
                    <div className="balance-analysis-right-rail-drilldown-detail__title">
                      {formatBalanceBusinessTextDisplay(selectedEventCalendar.title)}
                    </div>
                    <div className="balance-analysis-right-rail-drilldown-detail__status">
                      {selectedEventCalendar.event_date}
                    </div>
                    <div className="balance-analysis-right-rail-drilldown-detail__body">
                      {formatBalanceBusinessTextDisplay(selectedEventCalendar.impact_hint)}
                    </div>
                    <div className="balance-analysis-right-rail-drilldown-detail__meta">
                      <span>{formatBalanceBusinessTextDisplay(selectedEventCalendar.event_type)}</span>
                      <span>{formatBalanceBusinessTextDisplay(selectedEventCalendar.source)}</span>
                      <span>{formatBalanceWorkbookOperationalSectionKeyDisplay(selectedEventCalendar.source_section)}</span>
                    </div>
                  </div>
                ) : selectedRiskAlert ? (
                  <div
                    data-testid="balance-analysis-right-rail-drilldown-risk"
                    className="balance-analysis-right-rail-drilldown-detail"
                  >
                    <div className="balance-analysis-right-rail-drilldown-detail__title">
                      {formatBalanceBusinessTextDisplay(selectedRiskAlert.title)}
                    </div>
                    <div className="balance-analysis-right-rail-drilldown-detail__status balance-analysis-right-rail-drilldown-detail__body--warning">
                      {formatBalanceGovernedSeverityDisplay(selectedRiskAlert.severity)}
                    </div>
                    <div className="balance-analysis-right-rail-drilldown-detail__body balance-analysis-right-rail-drilldown-detail__body--relaxed balance-analysis-right-rail-drilldown-detail__body--warning">
                      {formatBalanceBusinessTextDisplay(selectedRiskAlert.reason)}
                    </div>
                    <div className="balance-analysis-right-rail-drilldown-detail__meta balance-analysis-right-rail-drilldown-detail__meta--warning">
                      <span>{formatBalanceWorkbookOperationalSectionKeyDisplay(selectedRiskAlert.source_section)}</span>
                      <span>{selectedRiskAlert.rule_id}</span>
                      <span>{selectedRiskAlert.rule_version}</span>
                    </div>
                  </div>
                ) : (
                  renderWorkbookEmptyState(
                    "请选择一条决策事项、事件日历或风险预警后查看详情。",
                  )
                )}
              </article>
            </aside>
          </div>

          <details
            data-testid="balance-analysis-workbook-full-details"
            className="balance-analysis-details balance-analysis-details--sub balance-analysis-workbook-full-details"
          >
            <summary className="balance-analysis-details__summary">
              <h3 className="balance-analysis-details__title">完整工作簿明细</h3>
              <span className="balance-analysis-details__hint">
                查看各项指标及分类明细，用于核对汇总结果。
              </span>
            </summary>
            <div
              data-testid="balance-analysis-workbook-secondary-grid"
              className="balance-analysis-workbook-secondary-grid"
            >
              {secondaryWorkbookTables.map((table) => (
                <div key={table.key} data-testid={`balance-analysis-workbook-table-${table.key}`}>
                  <div className="balance-analysis-workbook-secondary-grid__title">
                    {formatBalanceBusinessTextDisplay(table.title)}
                  </div>
                  <DeferredBalanceAnalysisGrid
                    height={280}
                    rowData={table.rows.map((row, index) =>
                      Object.assign({}, row as object, { __gridId: `${table.key}-${index}` }),
                    )}
                    columnDefs={buildWorkbookGridColumnDefs(table.columns)}
                    getRowId={(p) => String((p.data as { __gridId: string }).__gridId)}
                  />
                </div>
              ))}
            </div>
          </details>
        </PageAsyncSection>
      </div>

      <details
        data-testid="balance-analysis-stage-details"
        className="balance-analysis-details balance-analysis-details--sec"
      >
        <summary className="balance-analysis-details__summary">
          <h2 className="balance-analysis-details__title">场景核对</h2>
          <strong className="balance-analysis-details__meta">数据日期与口径</strong>
          <span className="balance-analysis-details__hint">
            查看资产负债摘要、贡献、期限与风险分析所用的数据日期和口径。
          </span>
        </summary>
        <div className="balance-analysis-details__content">
          <div className="balance-analysis-stage-warning">
            本区与上方概览采用相同数据，报告日为{" "}
            {pageModel.stageModel.summary.tags[0]?.label ?? EM_DASH}。正式判断请结合总览、汇总、明细和相关风险提示。
            {pageModel.stageModel.hasRealData ? "" : " 当前筛选条件下暂无可用数据。"}
          </div>
        </div>
      </details>

          {(resultMetaSections.length > 0 || hasPublicationDiagnostics) && (
            <Collapse
              data-testid="balance-analysis-result-meta-collapse"
              defaultActiveKey={[]}
              items={[
                {
                  key: "result-meta",
                  label: "技术诊断",
                  forceRender: true,
                  children: (
                    <>
                      {hasPublicationDiagnostics ? (
                        <div className="balance-analysis-publication-diagnostics">
                          {overviewGeneration ? <p>发布代次：{overviewGeneration}</p> : null}
                          {publicationStatus?.reason ? <p>原始发布诊断：{publicationStatus.reason}</p> : null}
                          {publicationStatusQuery.isError ? <p>发布状态请求失败。</p> : null}
                        </div>
                      ) : null}
                      <FormalResultMetaPanel
                        testId="balance-analysis-result-meta"
                        sections={resultMetaSections}
                      />
                    </>
                  ),
                },
              ]}
              style={{ marginTop: 20 }}
            />
          )}
        </>
      )}
    </section>
  );
}
