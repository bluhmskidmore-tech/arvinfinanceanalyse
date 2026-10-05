import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import { FilterBar } from "../../../components/FilterBar";
import { SectionHead } from "../../../components/layout";
import type { ProductCategoryAttributionPayload } from "../../../api/contracts";
import { prefetchReactEChartsWhenIdle } from "./lazyReactEChartsLoader";
import { PageAsyncSection } from "../../../components/page/PageAsyncSection";
import {
  DataStatusStrip,
  PageDecisionHero,
  PageStateSurface,
} from "../../../components/page/PagePrimitives";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import MonthlyOperatingAnalysisBranch from "./MonthlyOperatingAnalysisBranch";
import { ProductCategoryPublicationHeader } from "./ProductCategoryPublicationHeader";
import "./ProductCategoryPnlPage.css";
import { ProductCategoryFormalReadinessBand } from "./ProductCategoryFormalReadinessBand";
import { ProductCategoryGovernanceStrip } from "./ProductCategoryGovernanceStrip";
import type { ProductCategoryLiabilityView } from "./ProductCategoryLiabilityViewToggle";
import { ProductCategorySpreadReadout } from "./ProductCategorySpreadReadout";
import { selectProductCategorySpreadReadoutSurface } from "./model/productCategoryPnlSpreadReadoutModel";
import { countProductCategoryComparableReportMonths } from "./ProductCategoryComparisonCharts";
import {
  type ProductCategoryAttributionCompare,
  ProductCategoryAttributionBridge,
  ProductCategoryAttributionPanel,
} from "./ProductCategoryAttributionPanels";
import { isProductCategoryAttributionDetailRow } from "./productCategoryPnlPageModel";
import {
  ProductCategoryManagementMonitoring,
  ProductCategoryOperatingActionBacktestPanel,
  ProductCategoryOperatingAnalysisPanel,
} from "./ProductCategoryOperatingPanels";
import { ProductCategoryFinancialAnalysisPanel } from "./ProductCategoryScenarioPanels";
import {
  PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY,
  PRODUCT_CATEGORY_FTP_SCENARIO_OPTIONS,
  type ProductCategoryInterestSpreadAttributionSelection,
  type ProductCategoryInterestSpreadBasis,
  type ProductCategoryCandidateMetricStatus,
  buildProductCategoryDiagnosticsSurface,
  buildProductCategoryDataHealth,
  buildProductCategoryLiabilitySideTrendSurface,
  buildProductCategoryTrendSnapshot,
  buildLedgerPnlHrefForReportDate,
  collectProductCategoryGovernanceNotices,
  defaultProductCategoryScenarioRateForReportDate,
  formatProductCategoryDualMetaDistinctLine,
  formatProductCategoryReportMonthLabel,
  formatProductCategoryValue,
  nextDefaultReportDateIfUnset,
  productCategoryReadRetryDelay,
  selectProductCategoryAttributionWaterfallSurface,
  selectProductCategoryDecisionFocusSurface,
  selectDisplayedProductCategoryGrandTotal,
  selectProductCategoryDetailRows,
  selectProductCategoryOperatingAnalysisSurface,
  selectProductCategoryOperatingActionBacktestSurface,
  selectProductCategoryRootCauseSurface,
  selectProductCategoryScenarioExplanation,
  selectProductCategoryScenarioSensitivitySurface,
  shouldRetryProductCategoryRead,
} from "./productCategoryPnlPageModel";
import {
  uniqueProductCategoryReportDates,
  useProductCategoryHistoryQueries,
} from "./useProductCategoryHistoryQueries";
import { useProductCategoryBacktestHistory } from "./useProductCategoryBacktestHistory";
import { useProductCategoryManagementMonitoring } from "./useProductCategoryManagementMonitoring";
import { useProductCategoryManualAdjustments } from "./useProductCategoryManualAdjustments";
import { useProductCategoryRefresh } from "./useProductCategoryRefresh";
import { useProductCategoryScenarioReview } from "./useProductCategoryScenarioReview";
import { ProductCategoryManualAdjustmentForm } from "./ProductCategoryManualAdjustmentForm";
import { ProductCategoryGovernanceEvidence } from "./ProductCategoryGovernanceEvidence";
import {
  ProductCategoryApiContractLedger,
  type ProductCategoryApiLedgerRow,
} from "./ProductCategoryApiContractLedger";
import { ProductCategoryDiagnosticsPanel } from "./ProductCategoryDiagnosticsPanel";
import { ProductCategoryLiabilityTrendPanel } from "./ProductCategoryLiabilityTrendPanel";
import { ProductCategoryTrendWorkspace } from "./ProductCategoryTrendWorkspace";
import { useProductCategoryTrendCharts } from "./useProductCategoryTrendCharts";
import {
  ProductCategoryFormalReportTable,
  type ProductCategoryFormalTableDisplayMode,
} from "./ProductCategoryFormalReportTable";

function ProductCategoryCandidateMetricNotice(props: {
  testId: string;
  title: string;
  status: ProductCategoryCandidateMetricStatus;
}) {
  return (
    <PageStateSurface
      variant="definition-pending"
      testId={props.testId}
      title={
        <span
          title={`status=${props.status.status}; formal_use_allowed=${props.status.formalUseAllowed}; pending_confirmation=${props.status.pendingConfirmation}`}
        >
          {props.title}
        </span>
      }
      description={`${props.status.label}：${props.status.disclaimer}`}
    />
  );
}

function formatProductCategoryRefreshStatusLine(
  snapshot: { status: string; run_id?: string } | null,
): string {
  const statusPart = snapshot ? `状态：${snapshot.status}` : "状态：启动中…";
  const runPart = snapshot?.run_id ? `；run_id：${snapshot.run_id}` : "";
  return `正在刷新产品分类损益数据。${statusPart}${runPart}。刷新期间「刷新损益数据」等部分控件将暂时不可用。`;
}

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
  testId?: string;
}) {
  return (
    <SectionHead
      title={props.title}
      category={props.eyebrow}
      note={props.description}
      numbered={false}
      contentGap="tight"
      testId={props.testId}
    />
  );
}

const PRODUCT_CATEGORY_SECTION_LINKS = [
  ["经营总览", "#product-category-overview"],
  ["差异归因", "#product-category-attribution"],
  ["产品结构", "#product-category-products"],
  ["负债结构", "#product-category-liabilities"],
  ["完整报表", "#product-category-report"],
  ["治理审计", "#product-category-governance"],
] as const;

function ProductCategorySectionNav() {
  return (
    <nav
      className="product-category-section-nav"
      aria-label="产品分类损益页面分区"
      data-testid="product-category-section-nav"
    >
      <span className="product-category-section-nav__label">分析路径</span>
      {PRODUCT_CATEGORY_SECTION_LINKS.map(([label, href], index) => (
        <a key={href} href={href}>
          <small aria-hidden="true">{String(index + 1).padStart(2, "0")}</small>
          <span>{label}</span>
        </a>
      ))}
    </nav>
  );
}


function reportDateYearMonth(
  reportDate: string,
): { year: number; month: number } | null {
  const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(reportDate);
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (
    !Number.isInteger(year) ||
    !Number.isInteger(month) ||
    month < 1 ||
    month > 12
  ) {
    return null;
  }
  return { year, month };
}

const PRODUCT_CATEGORY_TREND_WORKSPACE_STORAGE_KEY =
  "moss.product-category-pnl.trend-workspace-open";

/**
 * 图表折叠区位于页面约 1400px 处、与另外几条外观相同的折叠条并列，默认折叠会被读成
 * "图表不见了"。因此默认展开并记住读者自己的选择；展开成本很低，因为每张图仍要等进入视口才挂载。
 */
function readProductCategoryTrendWorkspacePreference(): boolean {
  try {
    const stored = globalThis.localStorage?.getItem(
      PRODUCT_CATEGORY_TREND_WORKSPACE_STORAGE_KEY,
    );
    return stored === "0" ? false : true;
  } catch {
    return true;
  }
}

function persistProductCategoryTrendWorkspacePreference(open: boolean): void {
  try {
    globalThis.localStorage?.setItem(
      PRODUCT_CATEGORY_TREND_WORKSPACE_STORAGE_KEY,
      open ? "1" : "0",
    );
  } catch {
    // 隐私模式或存储被禁用时忽略：偏好丢失不影响功能。
  }
}

function monthAnchoredInterestSpreadSelection(
  current: ProductCategoryInterestSpreadAttributionSelection,
  reportDate: string,
): ProductCategoryInterestSpreadAttributionSelection {
  const parsed = reportDateYearMonth(reportDate);
  if (!parsed || current.month === parsed.month) {
    return current;
  }
  return { ...current, month: parsed.month };
}



export default function ProductCategoryPnlPage() {
  const client = useApiClient();
  const location = useLocation();
  const publicationParams = new URLSearchParams(location.search);
  const isPublicationCapture =
    client.mode === "mock" && publicationParams.get("presentation") === "paper";
  const publicationFocus =
    publicationParams.get("focus") === "attribution"
      ? "attribution"
      : "overview";
  const [selectedBranch, setSelectedBranch] = useState<
    "product_category_pnl" | "monthly_operating_analysis"
  >("product_category_pnl");
  const [formalTableDisplayMode, setFormalTableDisplayMode] =
    useState<ProductCategoryFormalTableDisplayMode>("key");
  const [liabilityMatrixViewOverride, setLiabilityMatrixViewOverride] =
    useState<ProductCategoryLiabilityView | null>(null);
  const [selectedDate, setSelectedDate] = useState("");
  const [selectedView, setSelectedView] = useState("monthly");
  const [scenarioRate, setScenarioRate] = useState("1.75");
  const [appliedScenarioRate, setAppliedScenarioRate] = useState("");
  const [scenarioRateTouched, setScenarioRateTouched] = useState(false);
  const [attributionCompare, setAttributionCompare] =
    useState<ProductCategoryAttributionCompare>("mom");
  const [attributionDetailsOpen, setAttributionDetailsOpen] = useState(false);
  const [attributionDetailSelection, setAttributionDetailSelection] = useState<{
    contextKey: string;
    categoryId: string;
  } | null>(null);
  const attributionDetailsRef = useRef<HTMLDetailsElement>(null);
  const {
    isRefreshing,
    refreshPollSnapshot,
    refreshError,
    lastRefreshRunId,
    handleRefresh,
    runRefreshWorkflow,
  } = useProductCategoryRefresh(client);
  const [diagnosticsWorkspaceOpen, setDiagnosticsWorkspaceOpen] =
    useState(false);
  const [trendWorkspaceOpen, setTrendWorkspaceOpen] = useState(
    readProductCategoryTrendWorkspacePreference,
  );
  const [backtestWorkspaceOpen, setBacktestWorkspaceOpen] = useState(false);
  const [scenarioSensitivityRequested, setScenarioSensitivityRequested] =
    useState(false);
  const {
    selectedScenarioReviewCategoryId,
    setSelectedScenarioReviewCategoryId,
    scenarioReviewActionStatuses,
    scenarioReviewIssueReasons,
    scenarioActionClosureStatuses,
    scenarioActionClosureMemoCategoryId,
    setScenarioActionClosureMemoCategoryId,
    handleScenarioReviewActionStatus,
    handleScenarioReviewIssueReason,
    handleBulkScenarioReviewActionStatus,
    handleResetScenarioReviewActions,
    handleScenarioActionClosureStatus,
  } = useProductCategoryScenarioReview();
  const [
    interestSpreadAttributionSelection,
    setInterestSpreadAttributionSelection,
  ] = useState<ProductCategoryInterestSpreadAttributionSelection>({
    basis: "weighted",
    month: 1,
  });
  const datesQuery = useQuery({
    queryKey: ["product-category-pnl", "dates", client.mode],
    queryFn: () => client.getProductCategoryDates(),
    retry: shouldRetryProductCategoryRead,
    retryDelay: productCategoryReadRetryDelay,
  });

  useEffect(() => {
    const next = nextDefaultReportDateIfUnset(
      selectedDate,
      datesQuery.data?.result.report_dates,
    );
    if (next !== null) {
      setSelectedDate(next);
      setInterestSpreadAttributionSelection((current) =>
        monthAnchoredInterestSpreadSelection(current, next),
      );
    }
  }, [datesQuery.data, selectedDate]);

  useEffect(() => {
    prefetchReactEChartsWhenIdle();
  }, []);

  useEffect(() => {
    if (!selectedDate || scenarioRateTouched) {
      return;
    }
    const defaultRate =
      defaultProductCategoryScenarioRateForReportDate(selectedDate);
    setScenarioRate(defaultRate);
    setAppliedScenarioRate((current) => (current ? defaultRate : current));
  }, [scenarioRateTouched, selectedDate]);

  const handleReportDateChange = (nextDate: string) => {
    const defaultRate =
      defaultProductCategoryScenarioRateForReportDate(nextDate);
    setSelectedDate(nextDate);
    setInterestSpreadAttributionSelection((current) =>
      monthAnchoredInterestSpreadSelection(current, nextDate),
    );
    setScenarioRate(defaultRate);
    setScenarioRateTouched(false);
    setAppliedScenarioRate((current) => (current ? defaultRate : current));
  };

  const baselineQuery = useQuery({
    queryKey: [
      "product-category-pnl",
      "baseline",
      client.mode,
      selectedDate,
      selectedView,
    ],
    queryFn: () =>
      client.getProductCategoryPnl({
        reportDate: selectedDate,
        view: selectedView,
      }),
    enabled: Boolean(selectedDate),
    retry: shouldRetryProductCategoryRead,
    retryDelay: productCategoryReadRetryDelay,
  });

  const scenarioQuery = useQuery({
    queryKey: [
      "product-category-pnl",
      "scenario",
      client.mode,
      selectedDate,
      selectedView,
      appliedScenarioRate,
    ],
    queryFn: () =>
      client.getProductCategoryPnl({
        reportDate: selectedDate,
        view: selectedView,
        scenarioRatePct: appliedScenarioRate,
      }),
    enabled: Boolean(selectedDate && appliedScenarioRate),
    retry: false,
  });

  const scenarioSensitivityQueries = useQueries({
    queries: PRODUCT_CATEGORY_FTP_SCENARIO_OPTIONS.map((option) => ({
      queryKey: [
        "product-category-pnl",
        "scenario-sensitivity",
        client.mode,
        selectedDate,
        selectedView,
        option.value,
      ],
      queryFn: () =>
        client.getProductCategoryPnl({
          reportDate: selectedDate,
          view: selectedView,
          scenarioRatePct: option.value,
        }),
      enabled: Boolean(
        selectedDate &&
        baselineQuery.data?.result &&
        scenarioSensitivityRequested,
      ),
      retry: false,
    })),
  });

  const {
    adjustmentsQuery,
    showManualForm,
    editingAdjustmentId,
    adjustmentMutationKind,
    isSubmittingAdjustment,
    isExportingAdjustments,
    adjustmentError,
    adjustmentExportError,
    exportedAdjustmentFilename,
    lastAdjustmentId,
    adjustmentDraft,
    updateAdjustmentField,
    handleManualAdjustmentSubmit,
    handleManualAdjustmentRevoke,
    handleManualAdjustmentRestore,
    handleManualAdjustmentsExport,
    handleManualAdjustmentEdit,
    handleManualAdjustmentToggle,
    handleManualAdjustmentCancel,
    handleManualAdjustmentCreate,
  } = useProductCategoryManualAdjustments(
    client,
    selectedDate,
    runRefreshWorkflow,
  );

  const attributionQuery = useQuery({
    queryKey: [
      "product-category-pnl",
      "attribution",
      client.mode,
      selectedDate,
      attributionCompare,
    ],
    queryFn: () =>
      client.getProductCategoryAttribution({
        reportDate: selectedDate,
        compare: attributionCompare,
      }),
    enabled: Boolean(selectedDate && selectedView === "monthly"),
    retry: false,
  });
  const managementMomAttributionQuery = useQuery({
    queryKey: [
      "product-category-pnl",
      "attribution",
      client.mode,
      selectedDate,
      "mom",
    ],
    queryFn: () =>
      client.getProductCategoryAttribution({
        reportDate: selectedDate,
        compare: "mom",
      }),
    enabled: Boolean(selectedDate && selectedView === "monthly"),
    retry: false,
  });

  const baseline = baselineQuery.data?.result;
  const formalMomAttribution =
    selectedView === "monthly"
      ? managementMomAttributionQuery.data?.result
      : undefined;
  const dataHealth = buildProductCategoryDataHealth({
    datesLoading: datesQuery.isLoading,
    datesError: datesQuery.isError,
    reportDates: datesQuery.data?.result.report_dates,
    selectedDate,
    baselineLoading: baselineQuery.isLoading || baselineQuery.isFetching,
    baselineError: baselineQuery.isError,
    baseline,
    meta: baselineQuery.data?.result_meta,
  });
  const canRenderBaselineDerivedAnalysis =
    Boolean(baseline) &&
    (dataHealth.state === "ready" || dataHealth.state === "degraded");
  const scenario = scenarioQuery.data?.result;
  const displayedGrandTotal = selectDisplayedProductCategoryGrandTotal(
    scenario?.grand_total,
    baseline?.grand_total,
  );
  const baselineRate = baseline?.asset_total.baseline_ftp_rate_pct ?? "1.75";
  const currentSceneRate = scenario?.scenario_rate_pct ?? baselineRate;
  const managementScenarioDistinct = Boolean(appliedScenarioRate);
  const displayedAssetTotal = scenario?.asset_total ?? baseline?.asset_total;
  const displayedLiabilityTotal =
    scenario?.liability_total ?? baseline?.liability_total;
  const currentSelectedPayload = scenario ?? baseline;
  const currentSelectedResultMeta = scenario
    ? scenarioQuery.data?.result_meta
    : baselineQuery.data?.result_meta;
  // 利差不随 FTP 场景变化（后端口径），因此固定读正式基线 payload。
  const spreadReadoutSurface = useMemo(
    () =>
      selectProductCategorySpreadReadoutSurface({
        payload: baseline,
        reportDate: selectedDate,
        selectedView,
      }),
    [baseline, selectedDate, selectedView],
  );
  const trendDiagnosticsLoaded = Boolean(selectedDate);
  const selectedYearMonth = useMemo(
    () => reportDateYearMonth(selectedDate),
    [selectedDate],
  );
  // 经营修复监控常显，使用年初至所选月的正式月度历史，不受趋势图最近八期限制。
  // 该面板本身不是折叠区消费方，须显式纳入门控，否则历史数据永远不会为它触发加载。
  const managementMonitoringConsumesHistory =
    selectedView === "monthly" &&
    !managementScenarioDistinct &&
    Boolean(selectedYearMonth) &&
    canRenderBaselineDerivedAnalysis;
  // 无场景时，动作回测复用趋势历史；应用场景后，回测单独读取正式月度历史。
  // 趋势、诊断和经营修复监控继续消费各自选定口径的历史。
  const trendHistoryConsumerOpen =
    trendWorkspaceOpen ||
    diagnosticsWorkspaceOpen ||
    (backtestWorkspaceOpen && !appliedScenarioRate) ||
    managementMonitoringConsumesHistory;
  const attributionHistoryConsumerOpen =
    trendWorkspaceOpen || backtestWorkspaceOpen;

  const rowsToRender = useMemo(
    () => selectProductCategoryDetailRows(baseline?.rows, scenario?.rows),
    [baseline?.rows, scenario?.rows],
  );
  const operatingAnalysisSurface = useMemo(
    () =>
      selectProductCategoryOperatingAnalysisSurface({
        rows: baseline?.rows ?? [],
        grandTotal: baseline?.grand_total,
        attribution: formalMomAttribution,
      }),
    [
      baseline?.rows,
      baseline?.grand_total,
      formalMomAttribution,
    ],
  );
  const scenarioSensitivityPayloads = useMemo(
    () =>
      scenarioSensitivityQueries.flatMap((query) =>
        query.data?.result ? [query.data.result] : [],
      ),
    [scenarioSensitivityQueries],
  );
  const scenarioSensitivitySurface = useMemo(
    () =>
      selectProductCategoryScenarioSensitivitySurface({
        baseline,
        scenarios: scenarioSensitivityPayloads,
      }),
    [baseline, scenarioSensitivityPayloads],
  );
  const scenarioReviewRows =
    scenarioSensitivitySurface.pressureSummary.reviewRows;
  const selectedScenarioExplanationCategoryId =
    scenarioReviewRows.find(
      (row) => row.categoryId === selectedScenarioReviewCategoryId,
    )?.categoryId ??
    scenarioReviewRows[0]?.categoryId ??
    null;
  const scenarioExplanation = useMemo(
    () =>
      selectProductCategoryScenarioExplanation({
        categoryId: selectedScenarioExplanationCategoryId,
        baseline,
        scenarios: scenarioSensitivityPayloads,
        attribution:
          selectedView === "monthly" ? attributionQuery.data?.result : undefined,
      }),
    [
      attributionQuery.data?.result,
      baseline,
      scenarioSensitivityPayloads,
      selectedScenarioExplanationCategoryId,
      selectedView,
    ],
  );
  const attributionWaterfallSurface = useMemo(
    () =>
      selectProductCategoryAttributionWaterfallSurface(
        attributionQuery.data?.result,
      ),
    [attributionQuery.data?.result],
  );
  const rootCauseSurface = useMemo(
    () =>
      selectProductCategoryRootCauseSurface({
        rows: baseline?.rows ?? [],
        attribution: attributionQuery.data?.result,
      }),
    [attributionQuery.data?.result, baseline?.rows],
  );
  const attributionDetailContextKey = useMemo(() => {
    const attribution = attributionQuery.data?.result;
    if (
      selectedView !== "monthly" ||
      !attribution ||
      attribution.state !== "complete"
    ) {
      return null;
    }
    return [
      selectedDate,
      selectedView,
      attributionCompare,
      attribution.current_report_date,
      attribution.prior_report_date,
      scenario?.scenario_rate_pct ?? "baseline",
    ].join(":");
  }, [
    attributionCompare,
    attributionQuery.data?.result,
    scenario?.scenario_rate_pct,
    selectedDate,
    selectedView,
  ]);
  const selectedAttributionDetailCategoryId =
    attributionDetailContextKey === null
      ? null
      : attributionDetailSelection?.contextKey === attributionDetailContextKey
        ? attributionDetailSelection.categoryId
        : (rootCauseSurface.headline?.categoryId ?? null);
  const attributionDetailCategoryIds = useMemo(() => {
    const attribution = attributionQuery.data?.result;
    if (
      selectedView !== "monthly" ||
      !attribution ||
      attribution.state !== "complete"
    ) {
      return new Set<string>();
    }
    return new Set(
      attribution.rows
        .filter(isProductCategoryAttributionDetailRow)
        .map((row) => row.category_id),
    );
  }, [attributionQuery.data?.result, selectedView]);
  const handleAttributionDetailSelection = useCallback(
    (categoryId: string) => {
      if (!attributionDetailContextKey) {
        return;
      }
      setAttributionDetailSelection({
        contextKey: attributionDetailContextKey,
        categoryId,
      });
    },
    [attributionDetailContextKey],
  );
  const handleAttributionDetailDrilldown = useCallback(
    (categoryId: string) => {
      handleAttributionDetailSelection(categoryId);
      setAttributionDetailsOpen(true);
      const scrollToSelectedDetail = () => {
        const selectedDetail = document.getElementById(
          "product-category-attribution-selected-detail",
        );
        (selectedDetail ?? attributionDetailsRef.current)?.scrollIntoView?.({
          block: "center",
        });
      };
      if (typeof requestAnimationFrame === "function") {
        requestAnimationFrame(scrollToSelectedDetail);
      } else {
        scrollToSelectedDetail();
      }
    },
    [handleAttributionDetailSelection],
  );
  const handleLocateFormalRow = useCallback(
    (categoryId: string) => {
      handleAttributionDetailSelection(categoryId);
      const scrollToFormalRow = () => {
        const formalRow = document.getElementById(
          `product-category-formal-row-${categoryId}`,
        );
        const mobileFocus = document.getElementById(
          "product-category-formal-mobile-focus",
        );
        const reviewContext = document.getElementById(
          "product-category-formal-selection-context",
        );
        const scrollTarget =
          mobileFocus && mobileFocus.getClientRects().length > 0
            ? mobileFocus
            : (reviewContext ?? formalRow);
        scrollTarget?.scrollIntoView?.({ block: "center" });
        formalRow
          ?.querySelector<HTMLButtonElement>(
            "[data-product-category-formal-row-action]",
          )
          ?.focus({ preventScroll: true });
      };
      if (typeof requestAnimationFrame === "function") {
        requestAnimationFrame(scrollToFormalRow);
      } else {
        scrollToFormalRow();
      }
    },
    [handleAttributionDetailSelection],
  );
  const decisionFocusSurface = useMemo(
    () =>
      selectProductCategoryDecisionFocusSurface({
        rows: baseline?.rows ?? [],
        grandTotal: baseline?.grand_total,
        attribution: formalMomAttribution,
      }),
    [baseline?.rows, baseline?.grand_total, formalMomAttribution],
  );
  const {
    trendReportPoints,
    currentTrendPoint,
    trendHistoryPoints,
    trendHistoryReportDates,
    trendHistoryBatches,
    trendHistoryQueries,
    trendHistoryAttributionQueries,
    interestSpreadComparisonCurrentPoint,
    interestSpreadComparisonHistoryPoints,
    interestSpreadHistoryBatches,
    interestSpreadHistoryQueries,
    historyPayloadByReportDate,
  } = useProductCategoryHistoryQueries({
    client,
    selectedDate,
    reportDates: datesQuery.data?.result.report_dates,
    selectedView,
    appliedScenarioRate,
    trendWorkspaceOpen,
    trendHistoryConsumerOpen,
    attributionHistoryConsumerOpen,
  });
  const selectedLiabilityMatrixView: ProductCategoryLiabilityView =
    selectedView === "ytd" ? "ytd" : "monthly";
  const liabilityMatrixView =
    liabilityMatrixViewOverride ?? selectedLiabilityMatrixView;
  const handleLiabilityMatrixViewChange = useCallback(
    (nextView: ProductCategoryLiabilityView) => {
      setLiabilityMatrixViewOverride(
        nextView === selectedLiabilityMatrixView ? null : nextView,
      );
    },
    [selectedLiabilityMatrixView],
  );
  const liabilityMatrixReportDates = useMemo(
    () => uniqueProductCategoryReportDates(trendReportPoints),
    [trendReportPoints],
  );
  const liabilityMatrixAlternateQuery = useQuery({
    queryKey: [
      "product-category-pnl",
      "liability-matrix-history",
      client.mode,
      liabilityMatrixReportDates.join(","),
      liabilityMatrixView,
      appliedScenarioRate,
    ],
    queryFn: () =>
      client.getProductCategoryHistory({
        reportDates: liabilityMatrixReportDates,
        view: liabilityMatrixView,
        ...(appliedScenarioRate
          ? { scenarioRatePct: appliedScenarioRate }
          : {}),
      }),
    enabled: Boolean(
      trendHistoryConsumerOpen &&
        trendDiagnosticsLoaded &&
        liabilityMatrixReportDates.length > 0 &&
        liabilityMatrixView !== selectedLiabilityMatrixView,
    ),
    retry: false,
  });
  const {
    historyQueries: operatingActionBacktestHistoryQueries,
    payloads: operatingActionBacktestPayloads,
    isError: operatingActionBacktestHistoryErrored,
  } = useProductCategoryBacktestHistory({
    client,
    baseline: baselineQuery.data,
    reportDateBatches: trendHistoryBatches,
    trendHistoryQueries,
    backtestWorkspaceOpen,
    historyReady: trendDiagnosticsLoaded,
    selectedView,
    appliedScenarioRate,
  });
  const trendSnapshots = useMemo(
    () =>
      trendDiagnosticsLoaded
        ? [
            ...(currentSelectedPayload
              ? [
                  buildProductCategoryTrendSnapshot(
                    currentSelectedPayload,
                    currentTrendPoint?.label,
                    currentSelectedResultMeta,
                  ),
                ]
              : []),
            ...trendHistoryPoints.flatMap((point) => {
              const entry = historyPayloadByReportDate.get(point.reportDate);
              return entry
                ? [
                    buildProductCategoryTrendSnapshot(
                      entry.payload,
                      point.label,
                      entry.resultMeta,
                    ),
                  ]
                : [];
            }),
          ]
        : [],
    [
      currentSelectedPayload,
      currentSelectedResultMeta,
      currentTrendPoint?.label,
      historyPayloadByReportDate,
      trendDiagnosticsLoaded,
      trendHistoryPoints,
    ],
  );
  const liabilityMatrixAlternateSnapshots = useMemo(
    () =>
      liabilityMatrixAlternateQuery.data?.result.items.flatMap((item) =>
        item.status === "ok" && item.result
          ? [
              buildProductCategoryTrendSnapshot(
                item.result,
                formatProductCategoryReportMonthLabel(item.report_date),
                item.result_meta ?? undefined,
              ),
            ]
          : [],
      ) ?? [],
    [liabilityMatrixAlternateQuery.data?.result.items],
  );
  const operatingActionBacktestAttributions = useMemo(() => {
    const byReportDate = new Map<
      string,
      ProductCategoryAttributionPayload | null
    >();
    if (attributionQuery.data?.result && attributionCompare === "mom") {
      byReportDate.set(
        attributionQuery.data.result.report_date,
        attributionQuery.data.result,
      );
    }
    trendHistoryAttributionQueries.forEach((query) => {
      query.data?.result.items.forEach((item) => {
        if (item.status === "ok" && item.result) {
          byReportDate.set(item.result.report_date, item.result);
        }
      });
    });
    return byReportDate;
  }, [
    attributionCompare,
    attributionQuery.data?.result,
    trendHistoryAttributionQueries,
  ]);
  const operatingActionBacktestSurface = useMemo(
    () =>
      selectProductCategoryOperatingActionBacktestSurface({
        payloads: operatingActionBacktestPayloads,
        attributionsByReportDate: operatingActionBacktestAttributions,
      }),
    [operatingActionBacktestAttributions, operatingActionBacktestPayloads],
  );
  const managementMonitoring = useProductCategoryManagementMonitoring({
    client,
    reportDate: selectedDate,
    reportDates: datesQuery.data?.result.report_dates,
    baseline: baselineQuery.data,
    trendHistoryReportDates,
    trendHistoryQueries,
    attributionQuery: managementMomAttributionQuery,
    enabled: managementMonitoringConsumesHistory,
    scenarioDistinct: managementScenarioDistinct,
  });
  const interestSpreadComparisonSnapshots = useMemo(
    () =>
      trendDiagnosticsLoaded
        ? [
            ...(currentSelectedPayload && interestSpreadComparisonCurrentPoint
              ? [
                  buildProductCategoryTrendSnapshot(
                    currentSelectedPayload,
                    interestSpreadComparisonCurrentPoint.label,
                    currentSelectedResultMeta,
                  ),
                ]
              : []),
            ...interestSpreadComparisonHistoryPoints.flatMap((point) => {
              const entry = historyPayloadByReportDate.get(point.reportDate);
              return entry
                ? [
                    buildProductCategoryTrendSnapshot(
                      entry.payload,
                      point.label,
                      entry.resultMeta,
                    ),
                  ]
                : [];
            }),
          ]
        : [],
    [
      currentSelectedPayload,
      currentSelectedResultMeta,
      historyPayloadByReportDate,
      interestSpreadComparisonCurrentPoint,
      interestSpreadComparisonHistoryPoints,
      trendDiagnosticsLoaded,
    ],
  );
  const diagnosticsSurface = useMemo(
    () =>
      buildProductCategoryDiagnosticsSurface({
        rows: rowsToRender,
        assetTotal: displayedAssetTotal,
        liabilityTotal: displayedLiabilityTotal,
        grandTotal: displayedGrandTotal,
        interestSpread: currentSelectedPayload?.interest_spread ?? null,
        trendSnapshots,
      }),
    [
      currentSelectedPayload?.interest_spread,
      displayedAssetTotal,
      displayedGrandTotal,
      displayedLiabilityTotal,
      rowsToRender,
      trendSnapshots,
    ],
  );
  const hasDiagnosticsSurface =
    diagnosticsSurface.matrixRows.length > 0 ||
    diagnosticsSurface.matrixEmptyCopy !== null ||
    diagnosticsSurface.negativeWatchlistRows.length > 0 ||
    diagnosticsSurface.negativeWatchlistEmptyCopy !== null ||
    diagnosticsSurface.spreadAttribution.state === "ready" ||
    (diagnosticsSurface.spreadAttribution.state === "incomplete" &&
      diagnosticsSurface.spreadAttribution.reason.length > 0);
  const liabilitySideTrendSurface = useMemo(
    () => buildProductCategoryLiabilitySideTrendSurface(trendSnapshots),
    [trendSnapshots],
  );
  const liabilityMatrixUsesAlternateView =
    liabilityMatrixView !== selectedLiabilityMatrixView;
  const liabilityMatrixHasAlternateData =
    liabilityMatrixAlternateSnapshots.length > 0;
  const liabilityMatrixSnapshots =
    liabilityMatrixUsesAlternateView && liabilityMatrixHasAlternateData
      ? liabilityMatrixAlternateSnapshots
      : trendSnapshots;
  const liabilityMatrixTrendSurface = useMemo(
    () => buildProductCategoryLiabilitySideTrendSurface(liabilityMatrixSnapshots),
    [liabilityMatrixSnapshots],
  );
  const trendCharts = useProductCategoryTrendCharts({
    trendSnapshots,
    interestSpreadComparisonSnapshots,
    liabilitySideTrendSurface,
    liabilityMatrixTrendSurface,
    selectedYearMonth,
    interestSpreadAttributionSelection,
  });
  const handleInterestSpreadAttributionPointClick = useCallback(
    (
      basis: ProductCategoryInterestSpreadBasis,
      monthKeys: number[] | undefined,
      params: { dataIndex?: number },
    ) => {
      if (typeof params.dataIndex !== "number") {
        return;
      }
      const month = monthKeys?.[params.dataIndex];
      if (!month) {
        return;
      }
      setInterestSpreadAttributionSelection({ basis, month });
    },
    [],
  );
  // Per-period load state is still reported one comparison month at a time; each month
  // resolves against whichever batch carries it, and an unrequested batch counts as neither
  // loaded nor failed (same as the previously disabled per-period query).
  const comparisonHistoryStatus = useMemo(() => {
    const ownerByReportDate = new Map<
      string,
      { isError: boolean; isFetching: boolean; hasData: boolean }
    >();
    const indexOwners = (
      batches: string[][],
      queries: Array<{ isError: boolean; isFetching: boolean; data?: unknown }>,
    ) => {
      batches.forEach((batchReportDates, index) => {
        const query = queries[index];
        if (!query) {
          return;
        }
        batchReportDates.forEach((reportDate) => {
          ownerByReportDate.set(reportDate, {
            isError: query.isError,
            isFetching: query.isFetching,
            hasData: Boolean(query.data),
          });
        });
      });
    };
    indexOwners(trendHistoryBatches, trendHistoryQueries);
    indexOwners(interestSpreadHistoryBatches, interestSpreadHistoryQueries);

    let loaded = 0;
    let failed = 0;
    let loading = 0;
    interestSpreadComparisonHistoryPoints.forEach((point) => {
      if (historyPayloadByReportDate.has(point.reportDate)) {
        loaded += 1;
        return;
      }
      const owner = ownerByReportDate.get(point.reportDate);
      if (!owner) {
        return;
      }
      if (owner.isError) {
        failed += 1;
      } else if (owner.isFetching) {
        loading += 1;
      } else if (owner.hasData) {
        failed += 1;
      }
    });
    return {
      total: interestSpreadComparisonHistoryPoints.length,
      loaded,
      failed,
      loading,
    };
  }, [
    historyPayloadByReportDate,
    interestSpreadComparisonHistoryPoints,
    interestSpreadHistoryBatches,
    interestSpreadHistoryQueries,
    trendHistoryBatches,
    trendHistoryQueries,
  ]);
  const comparisonHistoryTotal = comparisonHistoryStatus.total;
  const comparisonHistoryLoaded = comparisonHistoryStatus.loaded;
  const comparisonHistoryFailed = comparisonHistoryStatus.failed;
  const comparisonHistoryLoading = comparisonHistoryStatus.loading;
  const comparisonPeriodTotal = comparisonHistoryTotal + (selectedDate ? 1 : 0);
  const comparisonPeriodLoaded =
    comparisonHistoryLoaded + (baselineQuery.data?.result ? 1 : 0);
  const comparisonPeriodFailed =
    comparisonHistoryFailed + (baselineQuery.isError ? 1 : 0);
  const comparisonPeriodLoading =
    comparisonHistoryLoading + (baselineQuery.isFetching ? 1 : 0);
  const comparisonLoadState: "loading" | "partial" | "complete" | "error" =
    comparisonPeriodFailed > 0
      ? comparisonPeriodLoaded > 0
        ? "partial"
        : "error"
      : comparisonPeriodLoading > 0
        ? "loading"
        : comparisonPeriodLoaded < comparisonPeriodTotal
          ? "partial"
          : "complete";
  const comparisonLoadLabel = [
    `对比期载入 ${comparisonPeriodLoaded}/${comparisonPeriodTotal}`,
    comparisonPeriodLoading > 0 ? `载入中 ${comparisonPeriodLoading}` : null,
    comparisonPeriodFailed > 0
      ? `失败 ${comparisonPeriodFailed}`
      : comparisonLoadState === "partial"
        ? "载入不全"
        : null,
  ]
    .filter(Boolean)
    .join("；");
  const comparisonComparableMonthCount = selectedYearMonth
    ? countProductCategoryComparableReportMonths(
        interestSpreadComparisonSnapshots,
        selectedYearMonth.year,
      )
    : 0;
  const comparisonPriorPeriodLabel = selectedYearMonth
    ? `${selectedYearMonth.year - 1}年全年`
    : "上年全年待选";
  const comparisonCurrentPeriodLabel = selectedYearMonth
    ? `${selectedYearMonth.year}年截至${selectedYearMonth.month}月`
    : "当前年截止月待选";
  const adjustmentCount =
    adjustmentsQuery.data?.adjustment_count ??
    adjustmentsQuery.data?.adjustments.length ??
    0;
  const adjustmentEventCount =
    adjustmentsQuery.data?.event_total ??
    adjustmentsQuery.data?.events.length ??
    0;
  const readEndpointRows: ProductCategoryApiLedgerRow[] = [
    {
      method: "GET",
      path: "/dates",
      status: datesQuery.isError
        ? "ERROR"
        : datesQuery.isFetching
          ? datesQuery.data
            ? "REFRESHING"
            : "LOADING"
          : `${datesQuery.data?.result.report_dates.length ?? 0} DATES`,
      tone: datesQuery.isError
        ? "error"
        : datesQuery.isFetching
          ? "loading"
          : "live",
    },
    {
      method: "GET",
      path: "/?report_date&view",
      status: !selectedDate
        ? "WAITING · REPORT DATE"
        : baselineQuery.isError
          ? "ERROR"
          : baselineQuery.isFetching
            ? baselineQuery.data
              ? "REFRESHING"
              : "LOADING"
            : baselineQuery.data
              ? `${baselineQuery.data.result.rows.length} ROWS`
              : "INTEGRATED · IDLE",
      tone: !selectedDate
        ? "contracted"
        : baselineQuery.isError
          ? "error"
          : baselineQuery.isFetching
            ? "loading"
            : baselineQuery.data
              ? "live"
              : "contracted",
    },
    {
      method: "GET",
      path: "/attribution?compare=mom|yoy",
      status:
        selectedView !== "monthly"
          ? "MONTHLY · IDLE"
          : !selectedDate
            ? "WAITING · REPORT DATE"
            : attributionQuery.isError
              ? "ERROR"
              : attributionQuery.isFetching
                ? attributionQuery.data
                  ? "REFRESHING"
                  : "LOADING"
                : (attributionQuery.data?.result.state?.toUpperCase() ??
                  "INTEGRATED · IDLE"),
      tone:
        selectedView !== "monthly" || !selectedDate
          ? "contracted"
          : attributionQuery.isError
            ? "error"
            : attributionQuery.isFetching
              ? "loading"
              : attributionQuery.data
                ? "live"
                : "contracted",
    },
    {
      method: "GET",
      path: "/manual-adjustments",
      status: !selectedDate
        ? "WAITING · REPORT DATE"
        : adjustmentsQuery.isError
          ? "ERROR"
          : adjustmentsQuery.isFetching
            ? adjustmentsQuery.data
              ? "REFRESHING"
              : "LOADING"
            : adjustmentsQuery.data
              ? `${adjustmentCount} ACTIVE`
              : "INTEGRATED · IDLE",
      tone: !selectedDate
        ? "contracted"
        : adjustmentsQuery.isError
          ? "error"
          : adjustmentsQuery.isFetching
            ? "loading"
            : adjustmentsQuery.data
              ? "live"
              : "contracted",
    },
    {
      method: "GET",
      path: "/manual-adjustments/export",
      status: !selectedDate
        ? "WAITING · REPORT DATE"
        : adjustmentExportError
          ? "ERROR"
          : isExportingAdjustments
            ? "EXPORTING"
            : exportedAdjustmentFilename
              ? "CSV EXPORTED"
              : "READY · ON DEMAND",
      tone: !selectedDate
        ? "contracted"
        : adjustmentExportError
          ? "error"
          : isExportingAdjustments
            ? "loading"
            : exportedAdjustmentFilename
              ? "live"
              : "contracted",
    },
    {
      method: "GET",
      path: "/refresh-status?run_id",
      status: refreshError
        ? "ERROR"
        : isRefreshing
          ? (refreshPollSnapshot?.status?.toUpperCase() ?? "POLLING")
          : lastRefreshRunId
            ? "RUN COMPLETE"
            : "READY · ON DEMAND",
      tone: refreshError
        ? "error"
        : isRefreshing
          ? "loading"
          : lastRefreshRunId
            ? "live"
            : "contracted",
    },
  ];
  const writeEndpointRows: ProductCategoryApiLedgerRow[] = [
    {
      method: "POST",
      path: "/refresh",
      status: isRefreshing ? "RUNNING" : "AUTH · START RUN",
      tone: isRefreshing ? "loading" : "contracted",
    },
    {
      method: "POST",
      path: "/manual-adjustments",
      status:
        adjustmentMutationKind === "create" ? "CREATING" : "AUTH · CREATE",
      tone: adjustmentMutationKind === "create" ? "loading" : "contracted",
    },
    {
      method: "POST",
      path: "/{id}/edit",
      status:
        adjustmentMutationKind === "edit"
          ? "EDITING"
          : editingAdjustmentId
            ? "READY · EDIT MODE"
            : "AUTH · EDIT",
      tone: adjustmentMutationKind === "edit" ? "loading" : "contracted",
    },
    {
      method: "POST",
      path: "/{id}/revoke",
      status:
        adjustmentMutationKind === "revoke" ? "REVOKING" : "AUTH · REVOKE",
      tone: adjustmentMutationKind === "revoke" ? "loading" : "contracted",
    },
    {
      method: "POST",
      path: "/{id}/restore",
      status:
        adjustmentMutationKind === "restore" ? "RESTORING" : "AUTH · RESTORE",
      tone: adjustmentMutationKind === "restore" ? "loading" : "contracted",
    },
  ];

  const governanceNotices = collectProductCategoryGovernanceNotices(
    baselineQuery.data?.result_meta,
  );
  const formalScenarioDistinct =
    baselineQuery.data?.result_meta && scenarioQuery.data?.result_meta
      ? formatProductCategoryDualMetaDistinctLine(
          baselineQuery.data.result_meta,
          scenarioQuery.data.result_meta,
        )
      : null;

  const reportExtra = canRenderBaselineDerivedAnalysis ? (
    <div
      data-testid="product-category-summary"
      className="product-category-summary"
    >
      <span>当前场景：{currentSceneRate}%</span>
      <span>基准场景：{baselineRate}%</span>
      <span className="product-category-summary__total">
        FTP后经营净收入：
        {formatProductCategoryValue(displayedGrandTotal?.business_net_income)}
      </span>
    </div>
  ) : null;
  const ledgerPnlHref = buildLedgerPnlHrefForReportDate(selectedDate);

  // 深色 owner 由外层 ThemedRouteBoundary 承担；两个分支页根都只声明
  // Nocturne scope（tokens.css 别名块将 --dh-api-* 重映射至 --nct-*，
  // 页内既有 --ib- / --moss-color- 重映射块随 scope 自动翻转，ledger-pnl 同款）。
  if (selectedBranch === "monthly_operating_analysis") {
    return (
      <section data-testid="product-category-page" data-moss-theme-scope="product-category-pnl">
        <FilterBar className="product-category-branch-switcher">
          <button
            type="button"
            data-testid="product-category-branch-product-category-pnl"
            aria-pressed="false"
            onClick={() => setSelectedBranch("product_category_pnl")}
          >
            产品分类损益
          </button>
          <button
            type="button"
            data-testid="product-category-branch-monthly-operating-analysis"
            aria-pressed="true"
            onClick={() => setSelectedBranch("monthly_operating_analysis")}
          >
            月度经营分析
          </button>
        </FilterBar>
        <MonthlyOperatingAnalysisBranch />
      </section>
    );
  }

  return (
    <section
      id="product-category-overview"
      data-testid="product-category-page"
      data-moss-theme-scope="product-category-pnl"
      data-publication-capture={isPublicationCapture ? "paper" : undefined}
      data-publication-focus={
        isPublicationCapture ? publicationFocus : undefined
      }
      className={`product-category-page-shell theme-dh-api${
        isPublicationCapture
          ? " product-category-page-shell--publication"
          : ""
      }`}
    >
      {isPublicationCapture ? (
        <ProductCategoryPublicationHeader focus={publicationFocus} />
      ) : null}
      <header
        data-testid="product-category-report-masthead"
        className="product-category-report-masthead"
      >
        <FilterBar className="product-category-branch-switcher">
          <button
            type="button"
            data-testid="product-category-branch-product-category-pnl"
            aria-pressed="true"
            onClick={() => setSelectedBranch("product_category_pnl")}
          >
            产品分类损益
          </button>
          <button
            type="button"
            data-testid="product-category-branch-monthly-operating-analysis"
            aria-pressed="false"
            onClick={() => setSelectedBranch("monthly_operating_analysis")}
          >
            月度经营分析
          </button>
        </FilterBar>
        <PageDecisionHero
          testId="product-category-contract-hero"
          className="product-category-contract-hero"
          titleTestId="product-category-page-title"
          questionTestId="product-category-page-subtitle"
          eyebrow=""
          title="产品分类损益"
          businessQuestion="产品类别损益与场景分析"
          reportDateSlot={
            <span
              data-testid="product-category-report-date-slot"
              title={selectedDate ? `报告日期 ${selectedDate}` : "报告日待选"}
            >
              {baselineQuery.data?.result_meta?.basis === "formal"
                ? "正式口径"
                : "口径待确认"}
              {` | ${selectedView === "monthly" ? "月度视图" : "汇总视图"}`}
            </span>
          }
          actions={
            <div className="product-category-contract-hero__actions">
              <span
                data-testid="product-category-role-badge"
                className={`product-category-contract-hero__chip product-category-contract-hero__chip--${
                  client.mode === "real" ? "real" : "mock"
                }`}
              >
                {client.mode === "real" ? "正式只读链路" : "本地离线契约回放"}
              </span>
              <Link
                data-testid="product-category-audit-link"
                to="/product-category-pnl/audit"
              >
                查看调整审计
              </Link>
              <Link
                data-testid="product-category-ledger-link"
                to={ledgerPnlHref}
              >
                总账损益
              </Link>
              <button
                type="button"
                data-testid="product-category-manual-button"
                onClick={handleManualAdjustmentToggle}
                className="product-category-contract-hero__button"
              >
                + 手工录入
              </button>
              <button
                type="button"
                data-testid="product-category-refresh-button"
                onClick={() => void handleRefresh()}
                disabled={isRefreshing}
                className="product-category-contract-hero__button"
              >
                {isRefreshing ? "刷新中..." : "刷新损益数据"}
              </button>
            </div>
          }
        >
          <div className="product-category-contract-hero__status-stack">
            {isRefreshing ? (
              <p
                data-testid="product-category-refresh-status"
                className="product-category-contract-hero__status-line"
              >
                {formatProductCategoryRefreshStatusLine(refreshPollSnapshot)}
              </p>
            ) : null}
            {lastRefreshRunId ? (
              <p className="product-category-contract-hero__status-note">
                最近刷新任务：{lastRefreshRunId}
              </p>
            ) : null}
            {lastAdjustmentId ? (
              <p className="product-category-contract-hero__status-note">
                最近录入调整：{lastAdjustmentId}
              </p>
            ) : null}
            {refreshError ? (
              <p className="product-category-contract-hero__status-error">
                {refreshError}
              </p>
            ) : null}
          </div>
        </PageDecisionHero>
      </header>

      {canRenderBaselineDerivedAnalysis ? (
        <ProductCategoryFormalReadinessBand
          reportDate={selectedDate}
          selectedView={selectedView}
          scenarioApplied={Boolean(scenario)}
          assetTotal={displayedAssetTotal}
          liabilityTotal={displayedLiabilityTotal}
          grandTotal={displayedGrandTotal}
          attribution={attributionQuery.data?.result}
        />
      ) : null}

      {canRenderBaselineDerivedAnalysis ? (
        <ProductCategorySpreadReadout surface={spreadReadoutSurface} />
      ) : null}

      <section
        data-testid="product-category-operating-command-rail"
        className="product-category-operating-command-rail"
        aria-label="报告控制与数据状态"
      >
        <section
          data-testid="product-category-unified-controls"
          className="product-category-command-surface"
          aria-label="报告口径与场景"
        >
          <div className="product-category-scenario-controls">
            <label className="product-category-scenario-controls__field">
              选择报告月份
              <select
                aria-label="选择报告月份"
                value={selectedDate}
                onChange={(event) => handleReportDateChange(event.target.value)}
                className="product-category-scenario-controls__select"
              >
                {(datesQuery.data?.result.report_dates ?? []).map(
                  (reportDate) => (
                    <option key={reportDate} value={reportDate}>
                      {formatProductCategoryReportMonthLabel(reportDate)}
                    </option>
                  ),
                )}
              </select>
            </label>

            <div className="product-category-scenario-controls__field">
              <span>视图模式</span>
              <div
                role="group"
                aria-label="视图模式"
                className="product-category-scenario-controls__view-group"
              >
                <button
                  type="button"
                  aria-pressed={selectedView === "monthly"}
                  onClick={() => setSelectedView("monthly")}
                  className={
                    selectedView === "monthly"
                      ? "product-category-scenario-controls__view-button product-category-scenario-controls__view-button--active"
                      : "product-category-scenario-controls__view-button"
                  }
                >
                  月度视图
                </button>
                <button
                  type="button"
                  aria-pressed={selectedView === "ytd"}
                  onClick={() => setSelectedView("ytd")}
                  className={
                    selectedView === "ytd"
                      ? "product-category-scenario-controls__view-button product-category-scenario-controls__view-button--active"
                      : "product-category-scenario-controls__view-button"
                  }
                >
                  汇总视图
                </button>
              </div>
            </div>

            <label className="product-category-scenario-controls__field">
              FTP 场景
              <select
                aria-label="FTP 场景"
                value={scenarioRate}
                onChange={(event) => {
                  setScenarioRateTouched(true);
                  setScenarioRate(event.target.value);
                }}
                className="product-category-scenario-controls__select"
              >
                {PRODUCT_CATEGORY_FTP_SCENARIO_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="product-category-scenario-controls__actions">
            <button
              type="button"
              data-testid="product-category-apply-scenario-button"
              onClick={() => setAppliedScenarioRate(scenarioRate.trim())}
              className="product-category-scenario-controls__apply"
            >
              应用场景
            </button>
          </div>

          {scenarioQuery.isFetching ? (
            <div
              data-testid="product-category-scenario-loading"
              className="product-category-scenario-controls__loading"
              role="status"
            >
              情景计算中，当前展示正式基线。
            </div>
          ) : null}

          {scenarioQuery.isError ? (
            <div
              data-testid="product-category-scenario-error"
              className="product-category-scenario-controls__error"
              role="alert"
            >
              <span>情景计算失败，当前展示为基线口径。</span>
              <button
                type="button"
                onClick={() => void scenarioQuery.refetch()}
              >
                重试情景计算
              </button>
            </div>
          ) : null}
        </section>

        <DataStatusStrip testId="product-category-data-status-strip">
          <ProductCategoryGovernanceStrip
            dataHealth={dataHealth}
            asOfDateGapText={PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY}
            notices={governanceNotices}
            formalScenarioDistinct={formalScenarioDistinct}
            onRetry={
              dataHealth.retryTarget === "dates"
                ? () => void datesQuery.refetch()
                : dataHealth.retryTarget === "baseline"
                  ? () => void baselineQuery.refetch()
                  : null
            }
            evidence={
              <ProductCategoryGovernanceEvidence
                reportDate={selectedDate}
                selectedView={selectedView}
                scenarioApplied={Boolean(scenario)}
                resultMeta={baselineQuery.data?.result_meta}
              />
            }
          />
        </DataStatusStrip>
      </section>

      <ProductCategorySectionNav />
      <a
        data-testid="product-category-next-analysis-preview"
        className="product-category-next-analysis-preview"
        href="#product-category-attribution"
      >
        <span>
          <small>下一分析区</small>
          <strong>归因与趋势</strong>
        </span>
        <span aria-hidden="true">↓</span>
      </a>

      {showManualForm ? (
        <ProductCategoryManualAdjustmentForm
          draft={adjustmentDraft}
          editing={Boolean(editingAdjustmentId)}
          isSubmitting={isSubmittingAdjustment}
          error={adjustmentError}
          onFieldChange={updateAdjustmentField}
          onSubmit={() => void handleManualAdjustmentSubmit()}
          onCancel={handleManualAdjustmentCancel}
        />
      ) : null}

      <section
        className="product-category-attribution-workbench"
        data-testid="product-category-attribution-workbench"
        id="product-category-attribution"
      >
        {canRenderBaselineDerivedAnalysis ? (
          <>
            {scenario ? (
              <div
                className="product-category-scenario-signing-warning"
                data-testid="product-category-scenario-signing-warning"
                role="note"
                title="formal_use_allowed=false"
              >
                当前顶部总计来自 FTP {String(scenario.scenario_rate_pct)}%
                场景预览，不可用于签批；下方归因继续使用正式基线响应，二者不得混作同一口径。
              </div>
            ) : null}
            <ProductCategoryAttributionPanel
              selectedView={selectedView}
              compare={attributionCompare}
              payload={attributionQuery.data?.result}
              resultMeta={attributionQuery.data?.result_meta}
              isLoading={attributionQuery.isLoading}
              isError={attributionQuery.isError}
              decisionReadout={
                selectedView === "monthly" &&
                attributionQuery.data?.result.state === "complete" ? (
                  <ProductCategoryAttributionBridge
                    waterfall={attributionWaterfallSurface}
                    rootCause={rootCauseSurface}
                    onOpenDetails={handleLocateFormalRow}
                  />
                ) : null
              }
              detailsOpen={attributionDetailsOpen}
              detailsRef={attributionDetailsRef}
              selectedDetailCategoryId={selectedAttributionDetailCategoryId}
              onCompareChange={setAttributionCompare}
              onDetailsOpenChange={setAttributionDetailsOpen}
              onLocateFormalRow={handleLocateFormalRow}
              onSelectDetailCategory={handleAttributionDetailSelection}
              onRetry={() => void attributionQuery.refetch()}
            />
          </>
        ) : null}
      </section>

      {canRenderBaselineDerivedAnalysis && selectedView === "monthly" ? (
        <ProductCategoryManagementMonitoring {...managementMonitoring} />
      ) : null}

      {canRenderBaselineDerivedAnalysis ? (
        <ProductCategoryTrendWorkspace
          open={trendWorkspaceOpen}
          onOpenChange={(isOpen) => {
            setTrendWorkspaceOpen(isOpen);
            persistProductCategoryTrendWorkspacePreference(isOpen);
          }}
          reportPeriodCount={trendSnapshots.length}
          charts={trendCharts}
          spreadViewLabel={spreadReadoutSurface.viewLabel}
          diagnosticsSurface={diagnosticsSurface}
          liabilityTrendSurface={liabilitySideTrendSurface}
          liabilityMatrixView={liabilityMatrixView}
          onLiabilityMatrixViewChange={handleLiabilityMatrixViewChange}
          comparisonCoverage={{
            priorPeriodLabel: comparisonPriorPeriodLabel,
            currentPeriodLabel: comparisonCurrentPeriodLabel,
            comparableMonthCount: comparisonComparableMonthCount,
            loadState: comparisonLoadState,
            loadLabel: comparisonLoadLabel,
          }}
          resultMeta={baselineQuery.data?.result_meta}
          onInterestSpreadAttributionPointClick={
            handleInterestSpreadAttributionPointClick
          }
        />
      ) : null}

      <details
        data-testid="product-category-adjustment-workspace"
        className="product-category-adjustment-workspace"
      >
        <summary>
          <span>手工调整与审计</span>
          <small>{adjustmentCount} 条当前调整</small>
        </summary>
        <div className="product-category-adjustment-workspace__body">
          <SectionLead
            eyebrow="治理"
            title="手工调整与审计"
            description="手工调整仍走既有新增、更新、撤销、恢复接口，完整事件时间线保留在独立审计视图。仅当审批通过可撤销、仅当已拒绝可恢复；其余审批状态下对应按钮为禁用。撤销、恢复、保存后均触发与全页「刷新损益数据」一致的损益刷新工作流以更新本列表。"
            testId="product-category-adjustment-lead"
          />
          <PageAsyncSection
            title="手工调整历史"
            isLoading={adjustmentsQuery.isLoading}
            isError={adjustmentsQuery.isError}
            isEmpty={
              !adjustmentsQuery.isLoading &&
              !adjustmentsQuery.isError &&
              (adjustmentsQuery.data?.adjustments.length ?? 0) === 0
            }
            fillHeight={false}
            onRetry={() => void adjustmentsQuery.refetch()}
          >
            <div
              data-testid="product-category-adjustment-history"
              className="product-category-adjustment-history"
            >
              <div className="product-category-adjustment-history__title">
                当前状态
              </div>
              {(adjustmentsQuery.data?.adjustments ?? []).map((item) => (
                <div
                  key={`current-${item.adjustment_id}`}
                  className="product-category-adjustment-history__row"
                >
                  <div>
                    <div className="product-category-adjustment-history__account-code">
                      {item.account_code}
                    </div>
                    <div className="product-category-adjustment-history__account-name">
                      {item.account_name || "未填写科目名称"}
                    </div>
                    <div className="product-category-adjustment-history__event">
                      最近事件：{item.event_type}
                    </div>
                  </div>
                  <div>{item.currency}</div>
                  <div>{item.operator}</div>
                  <div>{item.approval_status}</div>
                  <button
                    type="button"
                    data-testid={`product-category-edit-${item.adjustment_id}`}
                    disabled={isSubmittingAdjustment}
                    onClick={() =>
                      handleManualAdjustmentEdit({
                        adjustment_id: item.adjustment_id,
                        report_date: item.report_date,
                        operator: item.operator as "ADD" | "DELTA" | "OVERRIDE",
                        approval_status: item.approval_status as
                          "approved" | "pending" | "rejected",
                        account_code: item.account_code,
                        currency: item.currency as "CNX" | "CNY",
                        account_name: item.account_name,
                        beginning_balance: item.beginning_balance ?? null,
                        ending_balance: item.ending_balance ?? null,
                        monthly_pnl: item.monthly_pnl ?? null,
                        daily_avg_balance: item.daily_avg_balance ?? null,
                        annual_avg_balance: item.annual_avg_balance ?? null,
                      })
                    }
                  >
                    编辑
                  </button>
                  <button
                    type="button"
                    data-testid={`product-category-revoke-${item.adjustment_id}`}
                    disabled={
                      item.approval_status !== "approved" ||
                      isSubmittingAdjustment
                    }
                    onClick={() =>
                      void handleManualAdjustmentRevoke(item.adjustment_id)
                    }
                  >
                    撤销
                  </button>
                  <button
                    type="button"
                    data-testid={`product-category-restore-${item.adjustment_id}`}
                    disabled={
                      item.approval_status !== "rejected" ||
                      isSubmittingAdjustment
                    }
                    onClick={() =>
                      void handleManualAdjustmentRestore(item.adjustment_id)
                    }
                  >
                    恢复
                  </button>
                </div>
              ))}
              <div className="product-category-adjustment-history__audit-summary">
                <div className="product-category-adjustment-history__audit-copy">
                  <div className="product-category-adjustment-history__audit-title">
                    完整事件时间线已迁移到独立审计视图
                  </div>
                  <div className="product-category-adjustment-history__audit-note">
                    当前报表月份共有{" "}
                    {(adjustmentsQuery.data?.events ?? []).length} 条调整事件。
                  </div>
                </div>
                <Link
                  to="/product-category-pnl/audit"
                  data-testid="product-category-audit-summary-link"
                >
                  查看调整审计
                </Link>
              </div>
            </div>
          </PageAsyncSection>
        </div>
      </details>

      {canRenderBaselineDerivedAnalysis ? (
        <details
          className="product-category-secondary-workspace"
          data-testid="product-category-financial-workspace"
        >
          <summary>
            <span>财务候选分析</span>
            <small>情景敏感度与决策焦点</small>
          </summary>
          <ProductCategoryFinancialAnalysisPanel
            scenarioSensitivity={scenarioSensitivitySurface}
            scenarioExplanation={scenarioExplanation}
            selectedScenarioReviewCategoryId={
              selectedScenarioExplanationCategoryId
            }
            scenarioReviewActionStatuses={scenarioReviewActionStatuses}
            scenarioReviewIssueReasons={scenarioReviewIssueReasons}
            scenarioActionClosureStatuses={scenarioActionClosureStatuses}
            scenarioActionClosureMemoCategoryId={
              scenarioActionClosureMemoCategoryId
            }
            scenarioSensitivityRequested={scenarioSensitivityRequested}
            scenarioSensitivityLoading={scenarioSensitivityQueries.some(
              (query) => query.isLoading,
            )}
            scenarioSensitivityError={scenarioSensitivityQueries.some(
              (query) => query.isError,
            )}
            onLoadScenarioSensitivity={() => {
              setScenarioSensitivityRequested(true);
              if (scenarioSensitivityRequested) {
                scenarioSensitivityQueries.forEach(
                  (query) => void query.refetch(),
                );
              }
            }}
            onSelectScenarioReview={setSelectedScenarioReviewCategoryId}
            onBulkScenarioReviewActionStatus={
              handleBulkScenarioReviewActionStatus
            }
            onResetScenarioReviewActions={handleResetScenarioReviewActions}
            onSetScenarioReviewActionStatus={handleScenarioReviewActionStatus}
            onSetScenarioReviewIssueReason={handleScenarioReviewIssueReason}
            onSetScenarioActionClosureStatus={handleScenarioActionClosureStatus}
            onSelectScenarioActionClosureMemo={
              setScenarioActionClosureMemoCategoryId
            }
            decisionFocus={decisionFocusSurface}
            candidateNotice={
              <ProductCategoryCandidateMetricNotice
                testId="product-category-financial-analysis-candidate-notice"
                title="财务增强为候选分析"
                status={scenarioSensitivitySurface.metricStatus}
              />
            }
          />
        </details>
      ) : null}

      <span
        id="product-category-products"
        className="product-category-section-anchor"
        aria-hidden="true"
      />
      {canRenderBaselineDerivedAnalysis ? (
        <details
          className="product-category-secondary-workspace"
          data-testid="product-category-operating-workspace"
        >
          <summary>
            <span>产品经营候选分析</span>
            <small>利润结构、压力项与动作队列</small>
          </summary>
          <ProductCategoryOperatingAnalysisPanel
            surface={operatingAnalysisSurface}
            view={selectedView === "monthly" ? "monthly" : "ytd"}
            candidateNotice={
              <ProductCategoryCandidateMetricNotice
                testId="product-category-operating-analysis-candidate-notice"
                title="经营分析为候选指标"
                status={operatingAnalysisSurface.metricStatus}
              />
            }
          />
        </details>
      ) : null}
      {canRenderBaselineDerivedAnalysis ? (
        <details
          className="product-category-secondary-workspace"
          data-testid="product-category-backtest-workspace"
          open={backtestWorkspaceOpen}
          onToggle={(event) =>
            setBacktestWorkspaceOpen(event.currentTarget.open)
          }
        >
          <summary>
            <span>动作回测候选分析</span>
            <small>历史命中率、校准与复核任务</small>
          </summary>
          {operatingActionBacktestHistoryErrored ? (
            <PageStateSurface
              variant="error"
              testId="product-category-backtest-history-error"
              title="正式月度历史读取失败"
              description="回测暂未展示，请重试读取正式历史。"
              actions={
                <button
                  type="button"
                  onClick={() => {
                    operatingActionBacktestHistoryQueries
                      .filter((query) => query.isError)
                      .forEach((query) => void query.refetch());
                  }}
                >
                  重试正式历史
                </button>
              }
            />
          ) : (
            <ProductCategoryOperatingActionBacktestPanel
              surface={operatingActionBacktestSurface}
              isHistoryLoaded={trendDiagnosticsLoaded}
              historyLoading={
                selectedView === "monthly" &&
                (operatingActionBacktestHistoryQueries.some(
                  (query) => query.isLoading,
                ) ||
                  trendHistoryAttributionQueries.some((query) => query.isLoading))
              }
              candidateNotice={
                <ProductCategoryCandidateMetricNotice
                  testId="product-category-operating-action-backtest-candidate-notice"
                  title="动作回测为候选复核"
                  status={operatingActionBacktestSurface.metricStatus}
                />
              }
            />
          )}
        </details>
      ) : null}

      <span
        id="product-category-report"
        className="product-category-section-anchor"
        aria-hidden="true"
      />
      <SectionLead
        eyebrow="正式口径"
        title="正式产品类别损益表"
        description="表格继续展示后端返回的产品类别读模型，资产/负债符号展示、情景行为和合计行保持原有逻辑。"
        testId="product-category-formal-table-lead"
      />
      <PageAsyncSection
        title="产品类别损益分析表（单位：亿元）"
        isLoading={baselineQuery.isLoading}
        isError={baselineQuery.isError}
        isEmpty={
          !baselineQuery.isLoading &&
          !baselineQuery.isError &&
          rowsToRender.length === 0
        }
        fillHeight={false}
        onRetry={() => void baselineQuery.refetch()}
        extra={reportExtra}
      >
        <ProductCategoryFormalReportTable
          reportDate={selectedDate}
          selectedView={selectedView}
          scenarioRatePct={scenario?.scenario_rate_pct}
          rows={rowsToRender}
          grandTotal={displayedGrandTotal}
          displayMode={formalTableDisplayMode}
          onDisplayModeChange={setFormalTableDisplayMode}
          attribution={{
            contextAvailable: Boolean(attributionDetailContextKey),
            selectedCategoryId: selectedAttributionDetailCategoryId,
            categoryIds: attributionDetailCategoryIds,
            onOpenEvidence: handleAttributionDetailDrilldown,
          }}
        />
      </PageAsyncSection>

      <details
        data-testid="product-category-result-meta-workspace"
        className="product-category-result-meta-workspace"
      >
        <summary>
          <span>结果元信息与证据</span>
          <small>口径、版本、质量与追踪字段</small>
        </summary>
        <FormalResultMetaPanel
          testId="product-category-result-meta"
          title="产品分类结果元信息"
          sections={[
            {
              key: "baseline",
              title: "基线读模型",
              meta: baselineQuery.data?.result_meta,
            },
            {
              key: "scenario",
              title: "场景覆盖",
              meta: scenarioQuery.data?.result_meta,
            },
            {
              key: "attribution",
              title: "归因结果",
              meta: attributionQuery.data?.result_meta,
            },
          ]}
        />
      </details>

      {displayedGrandTotal && canRenderBaselineDerivedAnalysis ? (
        <div
          data-testid="product-category-footer-total"
          className="product-category-footer-total"
        >
          全部市场科目FTP后经营净收入：
          {formatProductCategoryValue(displayedGrandTotal.business_net_income)}
        </div>
      ) : null}

      <span
        id="product-category-liabilities"
        className="product-category-section-anchor"
        aria-hidden="true"
      />
      {canRenderBaselineDerivedAnalysis && hasDiagnosticsSurface ? (
        <details
          className="product-category-secondary-workspace product-category-secondary-workspace--diagnostics"
          data-testid="product-category-diagnostics-workspace"
          open={diagnosticsWorkspaceOpen}
          onToggle={(event) =>
            setDiagnosticsWorkspaceOpen(event.currentTarget.open)
          }
        >
          <summary>
            <span>诊断与负债趋势候选分析</span>
            <small>
              经营矩阵、负贡献观察、利差归因与负债结构核查；走势图已移至上方“趋势与利差候选图表”
            </small>
          </summary>
          {diagnosticsWorkspaceOpen ? (
            <div className="product-category-diagnostics-workspace__body">
              <SectionLead
                eyebrow="诊断"
                title="受治理诊断面板"
                description="仅使用当前 payload 行与趋势快照，补充产品经营诊断矩阵、负贡献观察名单和利差变动归因，不改写后端总计。"
                testId="product-category-diagnostics-lead"
              />
              <ProductCategoryCandidateMetricNotice
                testId="product-category-diagnostics-candidate-notice"
                title="诊断与趋势为候选分析"
                status={diagnosticsSurface.metricStatus}
              />
              <ProductCategoryDiagnosticsPanel surface={diagnosticsSurface} />
              <ProductCategoryLiabilityTrendPanel
                trendSurface={liabilitySideTrendSurface}
                matrixSurface={liabilityMatrixTrendSurface}
                chartOption={trendCharts.options.liabilitySideTrend}
                matrixView={liabilityMatrixView}
                onMatrixViewChange={handleLiabilityMatrixViewChange}
                alternateView={{
                  active: liabilityMatrixUsesAlternateView,
                  hasData: liabilityMatrixHasAlternateData,
                  isFetching: liabilityMatrixAlternateQuery.isFetching,
                  isError: liabilityMatrixAlternateQuery.isError,
                }}
              />
            </div>
          ) : null}
        </details>
      ) : null}

      <ProductCategoryApiContractLedger
        readRows={readEndpointRows}
        writeRows={writeEndpointRows}
        adjustmentCount={adjustmentCount}
        eventCount={adjustmentEventCount}
        canExport={Boolean(selectedDate)}
        isExporting={isExportingAdjustments}
        exportError={adjustmentExportError}
        exportedFilename={exportedAdjustmentFilename}
        onCreateAdjustment={handleManualAdjustmentCreate}
        onExport={() => void handleManualAdjustmentsExport()}
      />
    </section>
  );
}
