import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useApiClient } from "../../api/client";
import { type PnlByBusinessAnalysisDimension } from "../../api/contracts";
import { FilterBar } from "../../components/FilterBar";
import { KpiCard } from "../../components/KpiCard";
import { KpiStrip, SectionHead, type KpiCell } from "../../components/layout";
import { PageAsyncSection } from "../../components/page/PageAsyncSection";
import { FormalResultMetaPanel } from "../../components/page/FormalResultMetaPanel";
import { AnalysisGrid, DataStatusStrip, EvidencePanel, PageDecisionHero, PageFilterTray, PageStateSurface, PageV2Shell } from "../../components/page/PagePrimitives";
import { formatAnnualizedYieldPctDisplay } from "./pnlByBusinessAnnualizedYield";
import { buildYtdAvgByBusinessTypeMap } from "./pnlByBusinessAdbMap";
import { downloadPnlByBusinessExcel } from "./pnlByBusinessExport";
import { PnlByBusinessManagementChangePanel } from "./PnlByBusinessManagementChangePanel";
import { PnlByBusinessMonthlyTrendPanel } from "./PnlByBusinessMonthlyTrendPanel";
import { PnlByBusinessInsightsLeadershipPanel } from "./PnlByBusinessInsightsLeadershipPanel";
import { VIEW_MODE_SUBTITLES, buildPnlByBusinessMonthlyAdjustmentBridge, buildPnlByBusinessPageModel, resolvePnlByBusinessActiveMonthlyBucket, type PnlByBusinessAdbEvidenceStatus, formatAvgBalanceYi, formatYuanAsWanUnit, toneFromSigned, type PnlByBusinessViewMode } from "./pnlByBusinessPageModel";
import { EM_DASH } from "../../utils/format";
import { formatYuanAsYiCell } from "./pnlByBusinessDisplay";
import { ANALYSIS_DIMENSION_LABELS, MAIN_BREAKDOWN_DIMENSION_LABELS, type MainBreakdownDimension } from "./pnlByBusinessAnalysisOptions";
import { UnallocatedPnlPanel } from "./PnlByBusinessUnallocatedPanel";
import { AnalysisRowsTable } from "./PnlByBusinessAnalysisRowsTable";
import { PnlByBusinessPrecomputeStatusPanel } from "./PnlByBusinessPrecomputeStatusPanel";
import { PnlByBusinessInsightStrip, PnlByBusinessDrilldownRecommendationStrip } from "./PnlByBusinessInsightStrips";
import { BusinessRowsTable } from "./PnlByBusinessRowsTable";
import { MonthlyBusinessBreakdownPanel } from "./PnlByBusinessMonthlyBreakdownPanel";
import { PnlByBusinessManualAdjustmentPanel } from "./PnlByBusinessManualAdjustmentPanel";
import { FormalBusinessRowsTable } from "./PnlByBusinessFormalRowsTable";
import { DriverOverviewPanel } from "./PnlByBusinessDriverOverviewPanel";
import { SelectedBusinessDrilldownPanel } from "./PnlByBusinessSelectedDrilldownPanel";
import { BondBucketAnalysisPanel, FtpBridgePanel, BondBucketMonthlyPanel, NegativeFtpListPanel } from "./PnlByBusinessFtpAnalysisPanels";
import { MonthlyAdjustmentFtpBridgePanel } from "./PnlByBusinessMonthlyAdjustmentBridgePanel";
import { usePnlByBusinessPrecompute, usePnlByBusinessPublishedInsights } from "./usePnlByBusinessPublication";
import { usePnlByBusinessAnalysisQueries } from "./usePnlByBusinessAnalysisQueries";
import { usePnlByBusinessManualAdjustments } from "./usePnlByBusinessManualAdjustments";
import "./PnlByBusinessPage.css";

export { resolveApprovedPnlByBusinessInsightsEnvelope } from "./pnlByBusinessPublicationModel";

export default function PnlByBusinessPage() {
  const client = useApiClient();
  const [selectedReportDate, setSelectedReportDate] = useState("");
  const [viewMode, setViewMode] = useState<PnlByBusinessViewMode>("monthly");
  const [selectedBusinessKey, setSelectedBusinessKey] = useState<string | null>(null);
  const [analysisDimension, setAnalysisDimension] = useState<PnlByBusinessAnalysisDimension>("monthly");
  const [mainBreakdownDimension, setMainBreakdownDimension] = useState<MainBreakdownDimension>("currency");
  const [openMonthlyKeys, setOpenMonthlyKeys] = useState<Set<string>>(() => new Set());
  const [exportError, setExportError] = useState("");
  const [exportingExcel, setExportingExcel] = useState(false);

  const datesQuery = useQuery({
    queryKey: ["pnl-by-business", "dates", client.mode],
    queryFn: () => client.getFormalPnlDates(),
    retry: false,
  });

  const reportDates = useMemo(
    () => datesQuery.data?.result.formal_fi_report_dates ?? datesQuery.data?.result.report_dates ?? [],
    [datesQuery.data?.result.formal_fi_report_dates, datesQuery.data?.result.report_dates],
  );

  useEffect(() => {
    const firstDate = reportDates[0];
    if (!firstDate) {
      return;
    }
    if (!selectedReportDate || !reportDates.includes(selectedReportDate)) {
      setSelectedReportDate(firstDate);
    }
  }, [reportDates, selectedReportDate]);

  const selectedYear = selectedReportDate ? Number(selectedReportDate.slice(0, 4)) : new Date().getFullYear();
  const { precomputeStatusQuery, rebuildPrecomputeMutation } = usePnlByBusinessPrecompute({
    client,
    selectedYear,
    selectedReportDate,
    viewMode,
  });

  const businessQuery = useQuery({
    queryKey: ["pnl-by-business", "ytd", client.mode, selectedYear, selectedReportDate],
    enabled: Boolean(selectedReportDate && selectedYear && viewMode === "ytd"),
    queryFn: () => client.getPnlByBusinessYtd(selectedYear, selectedReportDate),
    retry: false,
  });
  const ytdResult = businessQuery.data?.result;

  const { approvedBusinessInsightsEnvelope, businessInsightsLeadershipModel } = usePnlByBusinessPublishedInsights({
    client,
    selectedYear,
    selectedReportDate,
    viewMode,
    precomputeStatusQuery,
  });
  const businessInsightsHref = `/pnl-by-business-insights?year=${encodeURIComponent(String(selectedYear))}&as_of_date=${encodeURIComponent(selectedReportDate)}`;

  const formalBusinessQuery = useQuery({
    queryKey: ["pnl-by-business", "formal", client.mode, selectedReportDate],
    enabled: Boolean(selectedReportDate && viewMode === "formal"),
    queryFn: () => client.getPnlByBusiness(selectedReportDate),
    retry: false,
  });

  const adbEvidenceStatus: PnlByBusinessAdbEvidenceStatus = "pnl_primary";
  const adbAvgByBusinessType = useMemo(
    () => buildYtdAvgByBusinessTypeMap(ytdResult?.items),
    [ytdResult?.items],
  );

  const formalResult = formalBusinessQuery.data?.result;
  const pageModel = useMemo(
    () =>
      buildPnlByBusinessPageModel({
        viewMode,
        selectedReportDate,
        selectedYear,
        selectedBusinessKey,
        clientMode: client.mode,
        datesState: { isLoading: datesQuery.isLoading, isError: datesQuery.isError },
        monthlyState: { isLoading: false, isError: false },
        ytdState: { isLoading: businessQuery.isLoading, isError: businessQuery.isError },
        formalState: { isLoading: formalBusinessQuery.isLoading, isError: formalBusinessQuery.isError },
        ytdResult,
        ytdMeta: businessQuery.data?.result_meta,
        formalResult,
        formalMeta: formalBusinessQuery.data?.result_meta,
        adbAvgByBusinessType,
        adbEvidenceStatus,
      }),
    [
      viewMode,
      selectedReportDate,
      selectedYear,
      selectedBusinessKey,
      client.mode,
      datesQuery.isLoading,
      datesQuery.isError,
      businessQuery.isLoading,
      businessQuery.isError,
      businessQuery.data?.result_meta,
      formalBusinessQuery.isLoading,
      formalBusinessQuery.isError,
      formalBusinessQuery.data?.result_meta,
      adbAvgByBusinessType,
      adbEvidenceStatus,
      ytdResult,
      formalResult,
    ],
  );
  const {
    ytdRows,
    parentYtdRows,
    defaultBusinessRow,
    selectedBusinessRow,
    formalRows,
  } = pageModel;
  const analysisBaseReady = Boolean(
    selectedReportDate &&
      selectedYear &&
      selectedBusinessRow?.row_key &&
      viewMode === "ytd" &&
      businessQuery.isSuccess,
  );

  useEffect(() => {
    if (viewMode !== "ytd" || !defaultBusinessRow) {
      return;
    }
    if (!selectedBusinessKey || !ytdRows.some((row) => row.row_key === selectedBusinessKey)) {
      setSelectedBusinessKey(defaultBusinessRow.row_key);
    }
  }, [defaultBusinessRow, selectedBusinessKey, viewMode, ytdRows]);


  useEffect(() => {
    setOpenMonthlyKeys(new Set());
  }, [selectedReportDate, viewMode]);

  const {
    analysisLoadStage,
    setAnalysisLoadStage,
    monthlyBusinessQuery,
    mainBreakdownQuery,
    mainBreakdownRows,
    analysisQuery,
    analysisRows,
    bondBucketQuery,
    bondBucketRows,
    bondBucketMonthlyQuery,
    bondBucketMonthlyRows,
    instrumentAnalysisQuery,
    instrumentAnalysisRows,
  } = usePnlByBusinessAnalysisQueries({
    client,
    selectedYear,
    selectedReportDate,
    viewMode,
    selectedBusinessRow,
    analysisDimension,
    mainBreakdownDimension,
    analysisBaseReady,
  });

  const monthlyAdjustmentBucket = resolvePnlByBusinessActiveMonthlyBucket(
    monthlyBusinessQuery.data?.result.months ?? [],
    selectedReportDate,
    monthlyBusinessQuery.data?.result.as_of_date,
  );
  const manualAdjustmentReportDate =
    viewMode === "monthly" ? (monthlyAdjustmentBucket?.period_end_date ?? "") : selectedReportDate;
  const {
    manualAdjustmentQuery,
    manualAdjustmentDateMismatch,
    manualAdjustmentReadError,
    currentAdjustments,
    adjustmentEvents,
    approvedAdjustmentCount,
    adjustmentDraft,
    editingAdjustmentId,
    adjustmentError,
    saveAdjustmentMutation,
    adjustmentActionMutation,
    resetAdjustmentDraft,
    updateAdjustmentDraft,
    handleSubmitAdjustment,
    handleEditAdjustment,
  } = usePnlByBusinessManualAdjustments({
    client,
    selectedReportDate,
    manualAdjustmentReportDate,
    viewMode,
    selectedBusinessRow,
    setSelectedBusinessKey,
    setAnalysisLoadStage,
  });


  const toggleMonthlyBucket = (monthKey: string) => {
    setOpenMonthlyKeys((current) => {
      const next = new Set(current);
      if (next.has(monthKey)) {
        next.delete(monthKey);
      } else {
        next.add(monthKey);
      }
      return next;
    });
  };


  const completePageModel = useMemo(
    () =>
      buildPnlByBusinessPageModel({
        viewMode,
        selectedReportDate,
        selectedYear,
        selectedBusinessKey,
        clientMode: client.mode,
        datesState: { isLoading: datesQuery.isLoading, isError: datesQuery.isError },
        monthlyState: { isLoading: monthlyBusinessQuery.isLoading, isError: monthlyBusinessQuery.isError },
        ytdState: { isLoading: businessQuery.isLoading, isError: businessQuery.isError },
        formalState: { isLoading: formalBusinessQuery.isLoading, isError: formalBusinessQuery.isError },
        monthlyResult: monthlyBusinessQuery.data?.result,
        monthlyMeta: monthlyBusinessQuery.data?.result_meta,
        ytdResult,
        ytdMeta: businessQuery.data?.result_meta,
        formalResult,
        formalMeta: formalBusinessQuery.data?.result_meta,
        adbAvgByBusinessType,
        adbEvidenceStatus,
        manualAdjustmentCount: approvedAdjustmentCount,
      }),
    [
      viewMode,
      selectedReportDate,
      selectedYear,
      selectedBusinessKey,
      client.mode,
      datesQuery.isLoading,
      datesQuery.isError,
      monthlyBusinessQuery.isLoading,
      monthlyBusinessQuery.isError,
      monthlyBusinessQuery.data?.result,
      monthlyBusinessQuery.data?.result_meta,
      businessQuery.isLoading,
      businessQuery.isError,
      businessQuery.data?.result_meta,
      formalBusinessQuery.isLoading,
      formalBusinessQuery.isError,
      formalBusinessQuery.data?.result_meta,
      adbAvgByBusinessType,
      adbEvidenceStatus,
      approvedAdjustmentCount,
      ytdResult,
      formalResult,
    ],
  );
  const {
    monthlyBusinessMonths,
    activeMonthlyBucket,
    loading,
    error,
    empty,
    statusStrip,
    summaryCards,
    insight,
    hero,
    stateSurfaces,
  } = completePageModel;
  const pnlSummaryKpiCells: KpiCell[] = summaryCards.map((card, index) => ({
    key: card.label ?? `summary-${index}`,
    label: card.label ?? EM_DASH,
    value: card.value,
    valueVariant: card.valueVariant,
    note: card.detail,
    noteTitle: card.detailTitle ?? card.detail,
  }));
  const monthlyAdjustmentBridge = buildPnlByBusinessMonthlyAdjustmentBridge(activeMonthlyBucket);
  const monthlyBridgeRowKey = monthlyAdjustmentBridge?.row.row_key;
  const monthlyBridgeApprovedAdjustments = monthlyBridgeRowKey
    ? currentAdjustments.filter(
        (adjustment) =>
          adjustment.row_key === monthlyBridgeRowKey && adjustment.approval_status === "approved",
      )
    : [];
  const monthlyBridgeApprovedReasons = Array.from(
    new Set(monthlyBridgeApprovedAdjustments.map((adjustment) => adjustment.reason.trim()).filter(Boolean)),
  );
  const monthlyBridgePendingAdjustmentCount = monthlyBridgeRowKey
    ? currentAdjustments.filter(
        (adjustment) =>
          adjustment.row_key === monthlyBridgeRowKey && adjustment.approval_status === "pending",
      ).length
    : 0;

  useEffect(() => {
    if (viewMode !== "monthly" || !activeMonthlyBucket?.month_key) {
      return;
    }
    setOpenMonthlyKeys((current) => {
      if (current.has(activeMonthlyBucket.month_key)) {
        return current;
      }
      const next = new Set(current);
      next.add(activeMonthlyBucket.month_key);
      return next;
    });
  }, [activeMonthlyBucket?.month_key, viewMode]);

  const handleExportExcel = async () => {
    if (!selectedReportDate || exportingExcel) {
      return;
    }
    setExportError("");
    setExportingExcel(true);
    try {
      const exportMonths =
        viewMode === "monthly"
          ? monthlyBusinessQuery.isSuccess
            ? monthlyBusinessMonths
            : []
          : monthlyBusinessQuery.isSuccess
            ? monthlyBusinessMonths
            : [];
      await downloadPnlByBusinessExcel({
        viewMode,
        reportDate: selectedReportDate,
        year: selectedYear,
        periodStart: ytdResult?.period_start_date,
        periodEnd: ytdResult?.period_end_date,
        periodLabel: ytdResult?.period_label,
        balanceQualityIssues: viewMode === "ytd" ? ytdResult?.balance_quality_issues
          : monthlyBusinessQuery.data?.result.balance_quality_issues,
        ytdQuality: ytdResult,
        bondBucketQuality: bondBucketQuery.data?.result,
        bondBucketMonthlyQuality: bondBucketMonthlyQuery.data?.result,
        negativeFtpQuality: instrumentAnalysisQuery.data?.result,
        analysisQuality: analysisQuery.data?.result,
        ytdRows: viewMode === "ytd" && businessQuery.isSuccess ? ytdRows : [],
        ytdSummary: viewMode === "ytd" && businessQuery.isSuccess ? ytdResult?.summary : undefined,
        unallocatedBreakdown:
          viewMode === "ytd" && businessQuery.isSuccess ? ytdResult?.unallocated_breakdown ?? [] : [],
        unallocatedItems:
          viewMode === "ytd" && businessQuery.isSuccess ? ytdResult?.unallocated_items ?? [] : [],
        adbAvgByBusinessType,
        formalRows: viewMode === "formal" && formalBusinessQuery.isSuccess ? formalRows : [],
        formalSummary: viewMode === "formal" && formalBusinessQuery.isSuccess ? formalResult?.summary : undefined,
        months: exportMonths,
        adjustments: viewMode === "ytd" && manualAdjustmentQuery.isSuccess ? currentAdjustments : [],
        adjustmentEvents: viewMode === "ytd" && manualAdjustmentQuery.isSuccess ? adjustmentEvents : [],
        bondBucketRows: viewMode === "ytd" && bondBucketQuery.isSuccess ? bondBucketRows : [],
        bondBucketMonthlyRows: viewMode === "ytd" && bondBucketMonthlyQuery.isSuccess ? bondBucketMonthlyRows : [],
        negativeFtpRows: viewMode === "ytd" && instrumentAnalysisQuery.isSuccess ? instrumentAnalysisRows : [],
        analysisDimension: viewMode === "ytd" && analysisQuery.isSuccess ? analysisDimension : undefined,
        analysisRows: viewMode === "ytd" && analysisQuery.isSuccess ? analysisRows : [],
        selectedBusinessLabel: viewMode === "ytd" ? selectedBusinessRow?.business_type : undefined,
      });
    } catch (error) {
      setExportError(error instanceof Error ? error.message : "导出 Excel 失败");
    } finally {
      setExportingExcel(false);
    }
  };

  const exportExcelDisabled =
    !selectedReportDate ||
    loading ||
    error ||
    empty ||
    exportingExcel ||
    (viewMode === "ytd" && !businessQuery.isSuccess) ||
    (viewMode === "monthly" && !monthlyBusinessQuery.isSuccess) ||
    (viewMode === "formal" && !formalBusinessQuery.isSuccess);

  const evidenceMetaSections = (() => {
    if (viewMode === "monthly" && monthlyBusinessQuery.data) {
      return [
        { key: "by-business-monthly", title: "业务种类月报", meta: monthlyBusinessQuery.data.result_meta },
      ];
    }
    if (viewMode === "ytd" && businessQuery.data) {
      const sections = [
        { key: "by-business-ytd", title: "业务种类损益", meta: businessQuery.data.result_meta },
      ];
      if (monthlyBusinessQuery.data) {
        sections.push({
          key: "by-business-monthly-change",
          title: "月度经营环比",
          meta: monthlyBusinessQuery.data.result_meta,
        });
      }
      if (mainBreakdownQuery.data) {
        sections.push({
          key: "by-business-main-breakdown",
          title: "总表分项拆解",
          meta: mainBreakdownQuery.data.result_meta,
        });
      }
      if (approvedBusinessInsightsEnvelope) {
        sections.push({
          key: "by-business-insights",
          title: "正式结构分析",
          meta: approvedBusinessInsightsEnvelope.result_meta,
        });
      }
      return sections;
    }
    if (viewMode === "formal" && formalBusinessQuery.data) {
      return [
        {
          key: "by-business-formal",
          title: "业务种类损益（formal）",
          meta: formalBusinessQuery.data.result_meta,
        },
      ];
    }
    return [];
  })();

  return (
    <section
      data-testid="pnl-by-business-page"
      data-moss-theme-scope="pnl-by-business"
      className="pnl-by-business-page"
    >
      <PageV2Shell testId="pnl-by-business-page-shell">
        <PageDecisionHero
          testId="pnl-by-business-contract-hero"
          className="pnl-by-business-hero"
          title="业务种类损益"
          titleTestId="pnl-by-business-page-title"
          questionTestId="pnl-by-business-page-subtitle"
          eyebrow="组合工作台"
          businessQuestion={hero.businessQuestion}
          reportDateSlot={
            <span className="pnl-by-business-hero-report-date" data-testid="pnl-by-business-report-date-slot">
              <strong>
                {hero.reportDateLabel} {hero.requestedReportDate}
              </strong>
              <span>{hero.reportDateNote}</span>
            </span>
          }
          conclusion={
            <span className="pnl-by-business-hero-conclusion">
              <strong>{hero.conclusionTitle}</strong>
              <span>{hero.conclusionDetail}</span>
              <span className="pnl-by-business-hero-conclusion__mode">{VIEW_MODE_SUBTITLES[viewMode]}</span>
            </span>
          }
          actions={
            <div className="pnl-by-business-hero-actions">
              <span
                className={`pnl-by-business-mode-pill ${client.mode === "real" ? "pnl-by-business-mode-pill--real" : "pnl-by-business-mode-pill--mock"}`}
              >
                {client.mode === "real" ? "正式读路径" : "Mock 回放"}
              </span>
              <Link to={businessInsightsHref} className="pnl-by-business-candidate-insights-link">
                业务结构与FTP后收益分析 →
              </Link>
              <Link to="/product-category-pnl" className="pnl-by-business-candidate-insights-link">
                全行生息资产利差 →
              </Link>
            </div>
          }
        />

        {!loading && !error && !empty ? (
          <section
            className="pnl-by-business-leadership-summary"
            data-testid="pnl-by-business-leadership-summary"
          >
            <KpiStrip
              testId="pnl-by-business-summary-cards"
              cellTestIdPrefix="pnl-by-business-kpi"
              cells={pnlSummaryKpiCells}
            />

            <PnlByBusinessInsightStrip
              insight={insight}
              viewMode={viewMode}
              balanceSourcePending={Boolean(viewMode === "ytd" ? ytdResult?.balance_quality_issues?.length
                : viewMode === "monthly" ? activeMonthlyBucket?.balance_quality_issues?.length : 0)}
              manualAdjustmentAuditLoading={
                viewMode !== "formal" && (manualAdjustmentQuery.isLoading || manualAdjustmentQuery.isFetching)
              }
              manualAdjustmentAuditUnavailable={
                viewMode !== "formal" && (manualAdjustmentQuery.isError || manualAdjustmentDateMismatch)
              }
            />
            {viewMode === "ytd" ? (
              <PnlByBusinessInsightsLeadershipPanel
                model={businessInsightsLeadershipModel}
                year={selectedYear}
                asOfDate={selectedReportDate}
                onSelectRow={setSelectedBusinessKey}
              />
            ) : null}
            {viewMode !== "formal" ? (
              <PnlByBusinessManagementChangePanel
                managementChange={monthlyBusinessQuery.data?.result.management_change}
                expectedCurrentMonthKey={
                  viewMode === "monthly"
                    ? activeMonthlyBucket?.month_key ?? null
                    : ytdResult?.period_end_date.slice(0, 7) ?? null
                }
                selectedRowKey={viewMode === "ytd" ? selectedBusinessRow?.row_key ?? null : null}
                isLoading={monthlyBusinessQuery.isLoading}
                isError={monthlyBusinessQuery.isError}
              />
            ) : null}
          </section>
        ) : null}

        <DataStatusStrip testId="pnl-by-business-data-status-strip" className="pnl-by-business-data-status-strip">
          <span><strong>口径</strong>{statusStrip.viewModeLabel}</span>
          <span><strong>状态</strong>{statusStrip.dataStatus}</span>
          <span><strong>截至</strong>{statusStrip.asOfDate}</span>
          <span><strong>降级</strong>{statusStrip.fallbackMode}</span>
          <span><strong>供应商</strong>{statusStrip.vendorStatus}</span>
          <span><strong>证据行</strong>{statusStrip.evidenceRows}</span>
          <span><strong>生成</strong>{statusStrip.generatedAt}</span>
          <span><strong>Trace</strong>{statusStrip.traceId}</span>
        </DataStatusStrip>

        {viewMode !== "formal" ? (
          <PnlByBusinessPrecomputeStatusPanel
            status={precomputeStatusQuery.data}
            isLoading={precomputeStatusQuery.isLoading || precomputeStatusQuery.isFetching}
            isError={precomputeStatusQuery.isError}
            isRebuilding={rebuildPrecomputeMutation.isPending}
            rebuildError={
              rebuildPrecomputeMutation.isError
                ? rebuildPrecomputeMutation.error instanceof Error
                  ? rebuildPrecomputeMutation.error.message
                  : "预计算重建请求失败"
                : null
            }
            onRebuild={() => {
              rebuildPrecomputeMutation.mutate({
                year: selectedYear,
                reportDate: selectedReportDate,
              });
            }}
          />
        ) : null}

        <PageFilterTray testId="pnl-by-business-filter-tray">
          <FilterBar className="pnl-by-business-filter">
            <label className="pnl-by-business-filter-label">
              {viewMode === "monthly" ? "报表月份" : "分析截止日"}
              <select
                aria-label="pnl-by-business-report-date"
                value={selectedReportDate}
                onChange={(event) => setSelectedReportDate(event.target.value)}
                className="pnl-by-business-control"
              >
                {reportDates.map((date) => (
                  <option key={date} value={date}>
                    {date}
                  </option>
                ))}
              </select>
            </label>
            <label className="pnl-by-business-filter-label">
              视图口径
              <select
                aria-label="pnl-by-business-view-mode"
                value={viewMode}
                onChange={(event) => setViewMode(event.target.value as PnlByBusinessViewMode)}
                className="pnl-by-business-control"
              >
                <option value="monthly">月报（ZQTZ）</option>
                <option value="ytd">年累计（YTD）</option>
                <option value="formal">primary 对账（/api/pnl/by-business）</option>
              </select>
            </label>
            <div className="pnl-by-business-filter-export-slot">
              <button
                type="button"
                className="pnl-by-business-action-button pnl-by-business-action-button-primary"
                aria-label="pnl-by-business-export-excel"
                disabled={exportExcelDisabled}
                onClick={handleExportExcel}
              >
                {exportingExcel ? "导出中..." : "导出 Excel"}
              </button>
              {exportError ? (
                <p className="pnl-by-business-export-error" role="alert">
                  {exportError}
                </p>
              ) : null}
            </div>
          </FilterBar>
        </PageFilterTray>

        {stateSurfaces.length > 0 ? (
          <div className="pnl-by-business-state-stack" data-testid="pnl-by-business-state-surfaces">
            {stateSurfaces.map((surface) => (
              <PageStateSurface
                key={surface.key}
                testId={`pnl-by-business-state-${surface.key}`}
                variant={surface.variant}
                className={
                  surface.key === "definition-pending"
                    ? "pnl-by-business-state-surface--compact-governance"
                    : undefined
                }
                title={surface.title}
                description={
                  surface.descriptionTitle ? (
                    <span title={surface.descriptionTitle}>{surface.description}</span>
                  ) : (
                    surface.description
                  )
                }
              />
            ))}
          </div>
        ) : null}

        {(viewMode === "ytd" ? ytdResult?.balance_quality_issues : viewMode === "monthly"
          ? monthlyBusinessQuery.data?.result.balance_quality_issues : [])?.map((issue) => (
          <PageStateSurface
            key={issue.issue_id}
            testId={`pnl-by-business-balance-quality-${issue.report_date}`}
            variant="stale"
            title={`${issue.report_date} 余额来源待核实`}
            description={`${issue.reason} 受影响期间的日均、年化收益率和 FTP 结果为暂列值，取得正确源表后重算。`}
          />
        ))}

        <PageAsyncSection
          title="业务种类损益"
          isLoading={loading}
          isError={error}
          isEmpty={empty}
          fillHeight={false}
          onRetry={() => {
            setAnalysisLoadStage(0);
            const chain = [
              datesQuery.refetch(),
              businessQuery.refetch(),
              formalBusinessQuery.refetch(),
              monthlyBusinessQuery.refetch(),
              manualAdjustmentQuery.refetch(),
            ];
            void Promise.all(chain);
          }}
        >
        <section className="pnl-by-business-content">
          {viewMode !== "ytd" ? (
            <PnlByBusinessDrilldownRecommendationStrip recommendation={insight.recommendedDrilldown} />
          ) : null}

          <AnalysisGrid columns={1} testId="pnl-by-business-analysis-grid" className="pnl-by-business-analysis-grid">
            {viewMode === "monthly" ? (
            <>
              <SectionHead
                title={`${selectedYear} 月报（截至 ${
                  activeMonthlyBucket?.month_key ?? selectedReportDate.slice(0, 7)
                }）`}
                note="月报与累计视图使用同一套 ZQTZ 管理披露分类：金额列为万元，日均与期末余额为亿元，收益率按各月自然日数年化；占比以含未分类项的来源总损益为分母。该视图列出截至当前报表日已加载的月报；切换到「年累计」可查看这些月报的累计结果。"
                numbered={false}
                contentGap="flush"
                testId="pnl-by-business-monthly-section-head"
              />
              <MonthlyAdjustmentFtpBridgePanel
                bridge={monthlyAdjustmentBridge}
                approvedAdjustmentCount={monthlyBridgeApprovedAdjustments.length}
                approvedReasons={monthlyBridgeApprovedReasons}
                pendingAdjustmentCount={monthlyBridgePendingAdjustmentCount}
                auditLoading={manualAdjustmentQuery.isLoading || manualAdjustmentQuery.isFetching}
                auditError={manualAdjustmentQuery.isError}
                auditDateMismatch={manualAdjustmentDateMismatch}
                auditReturnedReportDate={manualAdjustmentQuery.data?.report_date}
                requestedReportDate={selectedReportDate}
                auditReportDate={manualAdjustmentReportDate}
              />
              <MonthlyBusinessBreakdownPanel
                months={monthlyBusinessMonths}
                isLoading={monthlyBusinessQuery.isLoading || monthlyBusinessQuery.isFetching}
                isError={monthlyBusinessQuery.isError}
                openMonthKeys={openMonthlyKeys}
                onToggleMonth={toggleMonthlyBucket}
                title="月报业务种类明细"
                description="按月份展开 ZQTZ 管理披露分类，查看各月损益、月度日均、期末余额与 FTP 后收益。"
                forceOpenSingleMonth
              />
            </>
          ) : viewMode === "ytd" ? (
            <>
              <SectionHead
                title={`${selectedYear} 年累计明细`}
                note="金额列为万元，日均为亿元。日均与期末账面余额口径一致：H 用摊余成本，A/T 用公允价值，凭证式国债用面值兜底，均加应计利息。年化收益率、FTP 后结果及父级汇总使用后端字段；占比以含未分类项的来源总损益为分母。父级与「其中项」重叠，不可简单相加。"
                numbered={false}
                contentGap="flush"
                testId="pnl-by-business-ytd-section-head"
              />
              <BusinessRowsTable
                rows={ytdRows}
                selectedRowKey={selectedBusinessRow?.row_key ?? null}
                inlineCurrencyRows={
                  mainBreakdownDimension === "currency" &&
                  mainBreakdownQuery.data?.result.business_key === selectedBusinessRow?.row_key
                    ? mainBreakdownRows
                    : []
                }
                summary={ytdResult?.summary}
                unallocatedPnl={ytdResult?.unallocated_pnl}
                unallocatedRowCount={ytdResult?.unallocated_row_count}
                onSelectRow={(row) => setSelectedBusinessKey(row.row_key)}
              />
              <section
                className="pnl-by-business-analysis-block"
                data-testid="pnl-by-business-main-breakdown"
              >
                <div className="pnl-by-business-analysis-heading">
                  <div>
                    <h2>总表分项拆解</h2>
                    <p>
                      {selectedBusinessRow?.business_type ?? EM_DASH} · 子项仅拆分当前父级，不与其他父级重复
                    </p>
                  </div>
                  <label className="pnl-by-business-filter-label">
                    拆分维度
                    <select
                      aria-label="pnl-by-business-main-breakdown-dimension"
                      value={mainBreakdownDimension}
                      onChange={(event) =>
                        setMainBreakdownDimension(event.target.value as MainBreakdownDimension)
                      }
                      className="pnl-by-business-control"
                    >
                      {(Object.keys(MAIN_BREAKDOWN_DIMENSION_LABELS) as MainBreakdownDimension[]).map((key) => (
                        <option key={key} value={key}>
                          {MAIN_BREAKDOWN_DIMENSION_LABELS[key]}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                {mainBreakdownDimension === "currency" ? (
                  <div className="pnl-by-business-detail-warning">
                    原币种仅用于拆分，损益、日均、余额及 FTP 金额均为折人民币口径。
                  </div>
                ) : null}
                {mainBreakdownQuery.isLoading || mainBreakdownQuery.isFetching ? (
                  <div className="pnl-by-business-analysis-state">正在拆分当前父级</div>
                ) : mainBreakdownQuery.isError ? (
                  <div className="pnl-by-business-analysis-state">总表分项读取失败</div>
                ) : mainBreakdownRows.length === 0 ? (
                  <div className="pnl-by-business-analysis-state">当前维度暂无分项数据</div>
                ) : (
                  <AnalysisRowsTable
                    rows={mainBreakdownRows}
                    dimension={mainBreakdownDimension}
                    testId="pnl-by-business-main-breakdown-table"
                  />
                )}
              </section>
              <PnlByBusinessMonthlyTrendPanel
                months={monthlyBusinessMonths}
                selectedBusiness={selectedBusinessRow}
                periodStartDate={ytdResult?.period_start_date}
                periodEndDate={ytdResult?.period_end_date}
                isLoading={monthlyBusinessQuery.isLoading || monthlyBusinessQuery.isFetching}
                isError={monthlyBusinessQuery.isError}
              />
              <FtpBridgePanel selectedRow={selectedBusinessRow} />
              <PnlByBusinessDrilldownRecommendationStrip recommendation={insight.recommendedDrilldown} />
              <details className="pnl-by-business-deep-dive" data-testid="pnl-by-business-deep-dive">
                <summary className="pnl-by-business-deep-dive__summary" data-testid="pnl-by-business-deep-dive-toggle">
                  <span>
                    <strong>展开底层分析与核对工具</strong>
                    <small>未分类证据、证券级驱动、手工调整、逐月核对、投资资产四类与多维下钻</small>
                  </span>
                  <span className="pnl-by-business-deep-dive__action" aria-hidden="true">展开</span>
                </summary>
                <div className="pnl-by-business-deep-dive__content">
                  <UnallocatedPnlPanel
                    breakdown={ytdResult?.unallocated_breakdown}
                    items={ytdResult?.unallocated_items}
                    totalPnl={ytdResult?.unallocated_pnl}
                    totalAbsPnl={ytdResult?.unallocated_abs_pnl}
                    rowCount={ytdResult?.unallocated_row_count}
                  />
                  <SelectedBusinessDrilldownPanel
                    selectedRow={selectedBusinessRow}
                    rows={instrumentAnalysisRows}
                    isLoading={analysisBaseReady && (instrumentAnalysisQuery.isLoading || instrumentAnalysisQuery.isFetching)}
                    isError={instrumentAnalysisQuery.isError}
                  />
                  <DriverOverviewPanel
                    rows={parentYtdRows}
                    adbAvgByBusinessType={adbAvgByBusinessType}
                    adbEvidenceStatus={adbEvidenceStatus}
                  />
                  <PnlByBusinessManualAdjustmentPanel
                    rows={ytdRows}
                    selectedReportDate={selectedReportDate}
                    selectedBusinessRow={selectedBusinessRow}
                    selectedRowKey={selectedBusinessRow?.row_key ?? ""}
                    draft={adjustmentDraft}
                    editingAdjustmentId={editingAdjustmentId}
                    adjustmentError={adjustmentError}
                    readError={manualAdjustmentReadError}
                    isLoading={manualAdjustmentQuery.isLoading || manualAdjustmentQuery.isFetching}
                    isSaving={saveAdjustmentMutation.isPending}
                    isActionBusy={adjustmentActionMutation.isPending}
                    adjustments={currentAdjustments}
                    events={adjustmentEvents}
                    onSelectRowKey={(rowKey) => setSelectedBusinessKey(rowKey)}
                    onDraftChange={updateAdjustmentDraft}
                    onSubmit={handleSubmitAdjustment}
                    onEdit={handleEditAdjustment}
                    onCancelEdit={resetAdjustmentDraft}
                    onRevoke={(adjustmentId) => adjustmentActionMutation.mutate({ adjustmentId, action: "revoke" })}
                    onRestore={(adjustmentId) => adjustmentActionMutation.mutate({ adjustmentId, action: "restore" })}
                  />
                  <MonthlyBusinessBreakdownPanel
                    months={monthlyBusinessMonths}
                    isLoading={
                      analysisBaseReady &&
                      (analysisLoadStage < 1 || monthlyBusinessQuery.isLoading || monthlyBusinessQuery.isFetching)
                    }
                    isError={monthlyBusinessQuery.isError}
                    openMonthKeys={openMonthlyKeys}
                    onToggleMonth={toggleMonthlyBucket}
                    title="月报业务种类明细"
                    description="逐月展开已发布月报，YTD 金额可用父级行与这些月报合计核对。"
                  />
                  <BondBucketAnalysisPanel
                    rows={bondBucketRows}
                    isLoading={analysisBaseReady && (analysisLoadStage < 2 || bondBucketQuery.isLoading || bondBucketQuery.isFetching)}
                    isError={bondBucketQuery.isError}
                  />
                  <BondBucketMonthlyPanel
                    rows={bondBucketMonthlyRows}
                    isLoading={
                      analysisBaseReady &&
                      (analysisLoadStage < 3 || bondBucketMonthlyQuery.isLoading || bondBucketMonthlyQuery.isFetching)
                    }
                    isError={bondBucketMonthlyQuery.isError}
                  />
                  <NegativeFtpListPanel
                    rows={instrumentAnalysisRows}
                    isLoading={analysisBaseReady && (instrumentAnalysisQuery.isLoading || instrumentAnalysisQuery.isFetching)}
                    isError={instrumentAnalysisQuery.isError}
                  />
                  <section className="pnl-by-business-analysis-block" data-testid="pnl-by-business-analysis-panel">
                <div className="pnl-by-business-analysis-heading">
                  <div>
                    <h2>多维下钻</h2>
                    <p>{selectedBusinessRow?.business_type ?? EM_DASH}</p>
                  </div>
                  <label className="pnl-by-business-filter-label">
                    维度
                    <select
                      aria-label="pnl-by-business-analysis-dimension"
                      value={analysisDimension}
                      onChange={(event) => setAnalysisDimension(event.target.value as PnlByBusinessAnalysisDimension)}
                      className="pnl-by-business-control"
                    >
                      {(Object.keys(ANALYSIS_DIMENSION_LABELS) as PnlByBusinessAnalysisDimension[]).map((key) => (
                        <option key={key} value={key}>
                          {ANALYSIS_DIMENSION_LABELS[key]}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="pnl-by-business-analysis-kpis">
                  <KpiCard
                    label="选中业务损益"
                    value={formatYuanAsWanUnit(selectedBusinessRow?.total_pnl)}
                    detail={selectedBusinessRow?.business_type ?? EM_DASH}
                    tone={toneFromSigned(selectedBusinessRow?.total_pnl)}
                  />
                  <KpiCard
                    label="日均（亿元）"
                    value={formatAvgBalanceYi(selectedBusinessRow?.avg_balance)}
                    detail="ADB 同区间"
                  />
                  <KpiCard
                    label="期末余额（亿元）"
                    value={formatYuanAsYiCell(selectedBusinessRow?.current_balance)}
                    detail={ytdResult?.period_end_date ?? selectedReportDate}
                  />
                  <KpiCard
                    label="年化收益率"
                    value={formatAnnualizedYieldPctDisplay(selectedBusinessRow?.annualized_yield_pct)}
                    detail="YTD 损益 / 日均"
                  />
                </div>
                {analysisBaseReady && (analysisLoadStage < 4 || analysisQuery.isLoading || analysisQuery.isFetching) ? (
                  <div className="pnl-by-business-analysis-state">加载中</div>
                ) : analysisQuery.isError ? (
                  <div className="pnl-by-business-analysis-state">维度数据读取失败</div>
                ) : analysisRows.length === 0 ? (
                  <div className="pnl-by-business-analysis-state">暂无维度数据</div>
                ) : (
                  <AnalysisRowsTable rows={analysisRows} dimension={analysisDimension} />
                )}
                  </section>
                </div>
              </details>
            </>
          ) : (
            <>
              <SectionHead
                title={`${selectedReportDate} primary 对账明细`}
                note="这是对账证据，不是业务贡献主分析；与 GET /api/pnl/by-business 一致，来自 fact_formal_pnl_fi / fact_nonstd_pnl_bridge 与 fact_formal_zqtz_balance_daily 的 join 聚合。这里按 primary 分类展示，用于源数据追溯；月报和累计按 ZQTZ 管理披露分类展示，二者不要混加。"
                numbered={false}
                contentGap="flush"
                titleWrap="wrap"
                testId="pnl-by-business-formal-section-head"
              />
              <FormalBusinessRowsTable rows={formalRows} summary={formalResult?.summary} />
            </>
          )}
          </AnalysisGrid>

          {evidenceMetaSections.length > 0 ? (
            <details className="pnl-by-business-evidence-disclosure" data-testid="pnl-by-business-evidence-disclosure">
              <summary
                className="pnl-by-business-evidence-disclosure__summary"
                data-testid="pnl-by-business-evidence-disclosure-toggle"
              >
                <span>
                  <strong>数据来源、口径与血缘</strong>
                  <small>首屏状态条已保留截至日、降级、生成时间与 Trace；此处展开查看完整证据。</small>
                </span>
                <span className="pnl-by-business-evidence-disclosure__action" aria-hidden="true">
                  <span className="pnl-by-business-evidence-disclosure__action-closed">查看证据</span>
                  <span className="pnl-by-business-evidence-disclosure__action-open">收起证据</span>
                </span>
              </summary>
              <EvidencePanel
                testId="pnl-by-business-evidence-panel"
                className="pnl-by-business-evidence-panel"
              >
                <FormalResultMetaPanel
                  testId="pnl-by-business-result-meta-panel"
                  sections={evidenceMetaSections}
                />
              </EvidencePanel>
            </details>
          ) : null}
        </section>
      </PageAsyncSection>
      </PageV2Shell>
    </section>
  );
}
