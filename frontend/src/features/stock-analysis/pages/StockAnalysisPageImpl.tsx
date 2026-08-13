import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BarChartOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  FireOutlined,
  LineChartOutlined,
  SafetyCertificateOutlined,
  StockOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Button as AntButton, Drawer as AntDrawer } from "antd";

import { useApiClient } from "../../../api/clientContext";
import type {
  BacktestWindowSummary,
  LivermoreCandidateHistoryPortfolioBacktestPayload,
  LivermoreCycleProxyBacktestPayload,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyPayload,
  ResultMeta,
  StockAnalysisWorkbenchDataGap,
  StockAnalysisWorkbenchPayload,
} from "../../../api/contracts";
import { AnalysisGrid } from "../../../components/page/PagePrimitives";
import { isAgentFrontendEnabled } from "../../../mocks/navigation";
import {
  buildCandidateReviewQueue,
  buildClosedLoopSummary,
  buildCycleMacroLayerSummary,
  buildDataBoundarySummary,
  buildDailyJudgmentStrip,
  buildDeepZoneAuditRows,
  buildDecisionSummary,
  buildMarketStateCard,
  buildRiskExitRows,
  buildSectorFilterSummary,
  buildSectorRows,
  buildSectorTableSortComparator,
  buildSectorViewRows,
  buildStockAnalysisEventMonitorRows,
  buildStockAnalysisEvidenceStatus,
  buildStockEndpointEvidenceItems,
  buildStockSectorOverviewState,
  buildStrategyLensItems,
  buildConsensusReviewPanelSummary,
  buildCycleRotationPanelSummary,
  buildDeepAnalysisGateSummary,
  buildEventsMonitoringPanelSummary,
  buildMarketPriorityPanelSummary,
  buildObservationPoolsPanelSummary,
  buildObservationClosureSummary,
  buildWorkbenchDataDigest,
  buildStrategyBacktestPanelSummary,
  buildStrategyOptimizationPanelSummary,
  buildThemeBreakoutPanelSummary,
  buildThemeBreakoutCards,
  buildThemeLeaderPreviewItems,
  buildThemeBreakoutReviewItems,
  buildThemeEvidenceStateRows,
  buildThemeTaxonomyGapSummary,
  buildReviewQueueEmptyState,
  buildReviewQueueSectorFilterView,
  localizeStockBackendText,
  localizeImplementationStage,
  localizeThemeRadarBadge,
  isActionableLivermoreUnsupportedOutput,
  isStockModulePrimaryExcluded,
  mergeStockClosedLoopMeta,
  pickStockFreshnessMeta,
} from "../lib/stockAnalysisPageModel";
import type {
  StockEndpointEvidenceQueryState,
  StockObservationClosureReasonInput,
  StockSectorRow,
  WorkbenchFact,
  WorkbenchSlowState,
} from "../lib/stockAnalysisPageModel";
import {
  buildSectorStrengthCardModel,
  buildSectorStrengthOption,
  sectorViewTabs,
} from "../lib/stockAnalysisChartModel";
import { buildCandidatePositionSizeHintNotice } from "../lib/stockAnalysisPositionSizeHintModel";
import {
  buildStockAnalysisRailReviewState,
  buildThemeBreakoutBlockerCopy,
  compactStockText as compactText,
  filterChipClass,
  rawStockErrorMessage as rawErrorMessage,
  riskExitBlockedSummary,
  stockPageErrorMessage as errorMessage,
  stockSupplyFallbackLabel,
  stockSupplyBasisLabel,
  stockSupplyQualityLabel,
  stockSupplyVendorLabel,
  stockStatusLabel as statusLabel,
  stockStrategyPanelErrorMessage as strategyPanelErrorMessage,
} from "../lib/stockAnalysisPageCopy";
import {
  normalizeIsoCalendarDate,
  subtractIsoCalendarDays,
} from "../lib/stockAnalysisDate";
import {
  buildBackendSupplyOverview,
  cycleBoundaryLabel,
  cycleConstraintLabel,
  cycleEvidenceLabel,
  cycleGapLabel,
  cycleInputLabel,
  cycleInputSummary,
  cycleLayerTitleLabel,
  cycleLayerWeightLabel,
  dataGapFamilyLabel,
  eventDetailLabel,
  eventImpactLabel,
  eventLevelLabel,
  eventNameLabel,
  eventSourceLabel,
} from "../lib/stockAnalysisPageLabels";
import {
  buildBacktestCaliberDisclosure,
  buildStrategyBacktestRows,
  formatBacktestSignedPercent,
  resolveStrategyBacktestSampleCount,
  strategyBacktestHorizonLabels,
  strategyBacktestHorizons,
  strategyDisplayLabel,
} from "../lib/stockAnalysisBacktestModel";
import {
  formatPriorityScore,
  resolvePanelQueryState,
  strategyPriorityHorizonStatsText,
  strategyPriorityReasonLabel,
  strategyPriorityStatusLabel,
} from "../lib/stockAnalysisPriorityModel";
import {
  buildStrategyOptimizationRows,
  strategyOptimizationDateWeightedText,
  strategyOptimizationHorizonLabel,
  strategyOptimizationPrimaryStatsText,
  strategyOptimizationReasonLabel,
} from "../lib/stockAnalysisOptimizationModel";
import {
  formatSectorSeriesCumPctChange,
  formatSectorSeriesScore,
} from "../lib/stockAnalysisSectorSeriesModel";
import { buildStockAnalysisAgentPageContext } from "../lib/buildStockAnalysisAgentPageContext";
import { buildConsensusSummary, consensusStrategyLabel, lookupStockStrategyRanks } from "../lib/buildConsensusSummary";
import type { StockAnalysisKlineRadarItem } from "../lib/stockAnalysisKlineRadarModel";
import {
  buildStockAnalysisWorkbenchReviewQueue,
  enrichStockAnalysisWorkbenchReviewQueue,
  resolveStockAnalysisFormalUseAllowed,
} from "../lib/stockAnalysisWorkbenchQueueModel";
import {
  buildConsensusDetailSelection,
  buildFactorScreenDetailSelection,
  buildMeanReversionDetailSelection,
  buildRankContextDetailSelection,
  buildReviewQueueDetailSelection,
  buildRiskExitDetailSelection,
  buildStockDetailReviewContext,
  type StockDetailSelection,
} from "../lib/stockAnalysisDetailSelection";
import {
  SA_CARD_TITLE,
  SA_FIRST_CARD,
  SA_PILL,
  SA_SECTION_DESC,
  SA_SECTION_EYEBROW,
  SA_SECTION_HEAD,
  SA_SHELL_PAGE,
} from "../lib/stockAnalysisPageChrome";
import { useDeferredSectionSeen } from "../../../hooks/useDeferredSectionSeen";
import { useStockHeavyweightSection } from "../hooks/useStockHeavyweightSection";
import { useFirstScreenAnalyticsTabs } from "../hooks/useFirstScreenAnalyticsTabs";
import { useSectorPanelState } from "../hooks/useSectorPanelState";
import { useSectorRankSeriesSupport } from "../hooks/useSectorRankSeriesSupport";
import { useSectorSortState } from "../hooks/useSectorSortState";
import { useStockSelectionRefresh } from "../hooks/useStockSelectionRefresh";
import { useStrategyCardExpansion } from "../hooks/useStrategyCardExpansion";
import {
  StockAnalysisErrorWorkbench,
  StockAnalysisLoadingWorkbench,
} from "../components/StockAnalysisBoundaryWorkbenches";
import { StockAnalysisCandidateLedgerTable } from "../components/StockAnalysisCandidateLedgerTable";
import { StockAnalysisCandidateComparison } from "../components/StockAnalysisCandidateComparison";
import { StockAnalysisDecisionFirstScreen } from "../components/StockAnalysisDecisionFirstScreen";
import { StockAnalysisEvidenceDisclosure } from "../components/StockAnalysisEvidenceDisclosure";
import { StockAnalysisEvidenceLedgerRail } from "../components/StockAnalysisEvidenceLedgerRail";
import { StockAnalysisObservationClosurePanel } from "../components/StockAnalysisObservationClosurePanel";
import { StockAnalysisStrategyLensSection } from "../components/StockAnalysisStrategyLensSection";
import { StockAnalysisWorkbenchDigest } from "../components/StockAnalysisWorkbenchDigest";
import { CompactStatusTile } from "../components/StockAnalysisStatusPrimitives";
import { StockAnalysisBacktestCaliberDisclosure } from "../components/StockAnalysisBacktestCaliberDisclosure";
import { StockAnalysisWalkForwardPanel } from "../components/StockAnalysisWalkForwardPanel";
import { StockAnalysisWorkbenchActions } from "../components/StockAnalysisWorkbenchActions";
import {
  buildStockDataGapOverview,
  buildStockFactorScreenCard,
  buildStockFirstScreenHero,
  buildStockMacroCycleCard,
} from "../lib/stockAnalysisFirstScreenModel";
import {
  StockAnalysisAccordion as Accordion,
  StockAnalysisAccordionItem as AccordionItem,
} from "../components/StockAnalysisAccordion";
import { stockAnalysisPageCssVars } from "../lib/stockAnalysisTokens";
import { EMPTY_STRATEGY_PRIORITY_ROWS, stockAnalysisReadQueryOptions } from "../lib/stockAnalysisQueryOptions";
import { MarketWorkbenchFrame } from "../../workbench/market-shell";
import { TableSkeleton, TextSkeleton } from "../../../components/Skeletons";
import "./StockAnalysisPage.css";



const STOCK_ANALYSIS_ENDPOINT_EVIDENCE_RAIL_ID = "stock-analysis-endpoint-evidence-rail";
const SECTOR_STRENGTH_DEFAULT_TOP_COUNT = 3;

const LazyReactECharts = lazy(() => import("../../../lib/echarts"));
const LazyAgentPanel = lazy(() =>
  import("../../agent/AgentPanel").then((module) => ({ default: module.AgentPanel })),
);
const LazyStockDetailDrawer = lazy(() =>
  import("../components/StockDetailDrawer").then((module) => ({ default: module.StockDetailDrawer })),
);
const LazyStockAnalysisDeepZoneHeader = lazy(() =>
  import("../components/StockAnalysisDeepZoneHeader").then((module) => ({
    default: module.StockAnalysisDeepZoneHeader,
  })),
);
const LazyStockAnalysisConsensusFirstScreen = lazy(() =>
  import("../components/StockAnalysisConsensusFirstScreen").then((module) => ({
    default: module.StockAnalysisConsensusFirstScreen,
  })),
);
const LazyStockAnalysisKlineRadarPanel = lazy(() =>
  import("../components/StockAnalysisKlineRadarPanel").then((module) => ({
    default: module.StockAnalysisKlineRadarPanel,
  })),
);
const LazyStockAnalysisObservationPreview = lazy(() =>
  import("../components/StockAnalysisObservationPreview").then((module) => ({
    default: module.StockAnalysisObservationPreview,
  })),
);
const LazyStockAnalysisDeepSelectionOverview = lazy(() =>
  import("../components/StockAnalysisDeepSelectionOverview").then((module) => ({
    default: module.StockAnalysisDeepSelectionOverview,
  })),
);
const LazyStockAnalysisStrategyReviewCards = lazy(() =>
  import("../components/StockAnalysisStrategyReviewCards").then((module) => ({
    default: module.StockAnalysisStrategyReviewCards,
  })),
);
const LazyStockAnalysisThemeGroupedView = lazy(() =>
  import("../components/StockAnalysisThemeGroupedView").then((module) => ({
    default: module.StockAnalysisThemeGroupedView,
  })),
);
const loadStockAnalysisDeepResearchPrimitives = () =>
  import("../components/StockAnalysisDeepResearchPrimitives");
const LazyBacktestBoundaryChips = lazy(() =>
  loadStockAnalysisDeepResearchPrimitives().then((module) => ({ default: module.BacktestBoundaryChips })),
);
const LazyStockAnalysisCycleRuleSummary = lazy(() =>
  loadStockAnalysisDeepResearchPrimitives().then((module) => ({
    default: module.StockAnalysisCycleRuleSummary,
  })),
);
const LazyStockAnalysisTab = lazy(() =>
  loadStockAnalysisDeepResearchPrimitives().then((module) => ({ default: module.StockAnalysisTab })),
);
const LazyStockAnalysisTabs = lazy(() =>
  loadStockAnalysisDeepResearchPrimitives().then((module) => ({ default: module.StockAnalysisTabs })),
);
const LazyStrategyModuleCard = lazy(() =>
  loadStockAnalysisDeepResearchPrimitives().then((module) => ({ default: module.StrategyModuleCard })),
);
const LazyStrategyPanelComplianceDetails = lazy(() =>
  loadStockAnalysisDeepResearchPrimitives().then((module) => ({
    default: module.StrategyPanelComplianceDetails,
  })),
);

const WORKBENCH_FACT_ENDPOINT_MAP: Record<string, string> = {
  "data-date": "strategy",
  "strategy-basis": "strategy",
  "candidate-depth": "strategy",
  "factor-candidates": "strategy",
  "hybrid-candidates": "strategy",
  "module-states": "strategy",
  "gate-readiness": "strategy",
  "open-issues": "strategy",
  "signal-context": "signal-confluence",
  "replay-evidence": "signal-confluence",
  "sector-rank": "sector-series",
  "sector-series": "sector-series",
  "optimization-depth": "strategy-optimization",
  "candidate-history": "candidate-history",
  "strategy-score": "strategy-score",
  "proxy-backtest": "cycle-proxy",
  "proxy-warnings": "portfolio-proxy",
};

type SlowEvidenceQuery = {
  isLoading: boolean;
  isFetching: boolean;
  isError: boolean;
  isSuccess: boolean;
};

function useSlowEvidenceState(query: SlowEvidenceQuery, timeoutMs = 8000): WorkbenchSlowState {
  const [isSlow, setIsSlow] = useState(false);

  useEffect(() => {
    if (!query.isLoading && !query.isFetching) {
      setIsSlow(false);
      return undefined;
    }

    const timer = window.setTimeout(() => setIsSlow(true), timeoutMs);
    return () => window.clearTimeout(timer);
  }, [query.isLoading, query.isFetching, timeoutMs]);

  if (query.isError) return "error";
  if (query.isSuccess) return "success";
  if (isSlow) return "slow";
  if (query.isLoading || query.isFetching) return "loading";
  return "idle";
}

function readinessLabel(key: string): string {
  const labels: Record<string, string> = {
    market_gate: "市场门控",
    sector_rank: "板块强弱",
    stock_pivot: "个股候选",
    risk_exit: "风险退出",
  };
  return labels[key] ?? key;
}

function readinessStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    ready: "就绪",
    partial: "部分就绪",
    missing: "缺失",
    stale: "陈旧",
    blocked: "阻断",
    degraded: "降级",
  };
  return labels[status] ?? statusLabel(status);
}

function formatApiCount(value: number | null | undefined, fallback = "待确认"): string {
  return typeof value === "number" ? value.toLocaleString("zh-CN") : fallback;
}

function endpointQueryState({
  enabled,
  isLoading,
  isFetching,
  isError,
  hasData,
}: {
  enabled: boolean;
  isLoading: boolean;
  isFetching?: boolean;
  isError: boolean;
  hasData: boolean;
}): StockEndpointEvidenceQueryState {
  if (isError) return "error";
  if (hasData) return "success";
  if (!enabled) return "idle";
  if (isLoading || isFetching) return "loading";
  return "idle";
}

function activeStrategyDiagnosticCount(payload: LivermoreStrategyPayload | null): number | null {
  if (!payload) return null;
  return payload.diagnostics.filter((item) => item.severity !== "info").length;
}

function activeDataGapCount(payload: LivermoreStrategyPayload | null): number | null {
  if (!payload) return null;
  return payload.data_gaps.filter((item) => item.status !== "ready").length;
}

function activeUnsupportedOutputCount(payload: LivermoreStrategyPayload | null): number | null {
  if (!payload) return null;
  return payload.unsupported_outputs.filter(isActionableLivermoreUnsupportedOutput).length;
}

function isLivermoreStrategyPayload(value: unknown): value is LivermoreStrategyPayload {
  if (value == null || typeof value !== "object") return false;
  const payload = value as Partial<LivermoreStrategyPayload>;
  return payload.basis === "analytical" && payload.market_gate != null && Array.isArray(payload.supported_outputs);
}

function extractWorkbenchStrategyPayload(
  payload: StockAnalysisWorkbenchPayload | null | undefined,
): LivermoreStrategyPayload | null {
  const mainResult = payload?.modules.main?.result;
  return isLivermoreStrategyPayload(mainResult) ? mainResult : null;
}

const REQUIRED_WORKBENCH_GAP_FAMILIES = new Set([
  "broad_index_history",
  "breadth",
  "limit_up_quality",
  "sector_strength",
  "stock_universe",
  "position_risk",
]);

function normalizeWorkbenchDataGap(value: unknown): StockAnalysisWorkbenchDataGap | null {
  if (value == null || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  if (
    typeof row.input_family !== "string" ||
    typeof row.status !== "string" ||
    typeof row.evidence !== "string"
  ) {
    return null;
  }
  return {
    ...(row as Omit<StockAnalysisWorkbenchDataGap, "blocks_review">),
    blocks_review: typeof row.blocks_review === "boolean" ? row.blocks_review : true,
  };
}

function confluenceDiagnosticCount(payload: LivermoreSignalConfluencePayload | null): number | null {
  if (!payload) return null;
  return payload.diagnostics.filter(isActionableConfluenceDiagnostic).length;
}

function replayEvidenceMissingCount(payload: LivermoreSignalConfluencePayload | null): number | null {
  if (!payload?.replay_evidence) return payload ? 0 : null;
  return payload.replay_evidence.status === "available" ? 0 : 1;
}

function backtestWindowPendingDateCount(window: BacktestWindowSummary | null | undefined): number | null {
  if (!window) return null;
  return window.replay_dates_pending > 0 ? window.replay_dates_pending : 0;
}

function backtestWindowUnsupportedDateCount(window: BacktestWindowSummary | null | undefined): number | null {
  if (!window) return null;
  return window.replay_dates_unsupported > 0 ? window.replay_dates_unsupported : 0;
}

function pushFallbackReason(
  reasons: StockObservationClosureReasonInput[],
  {
    endpointId,
    endpointLabel,
    meta,
  }: {
    endpointId: string;
    endpointLabel: string;
    meta?: ResultMeta | null;
  },
) {
  const fallback = meta?.fallback_mode;
  if (!fallback || fallback === "none") return;
  reasons.push({
    key: `${endpointId}:fallback:${fallback}`,
    endpointId,
    endpointLabel,
    kind: "fallback",
    fieldPath: `${endpointId}.result_meta.fallback_mode`,
    displayText: `${endpointLabel}声明${stockSupplyFallbackLabel(fallback)}`,
    rawValueLabel: fallback,
  });
}

function confluenceDiagnosticText(item: LivermoreSignalConfluencePayload["diagnostics"][number]): string {
  if (typeof item === "string") return item;
  return item.message ?? item.code ?? "信号闭环诊断待复核";
}

function isActionableConfluenceDiagnostic(item: LivermoreSignalConfluencePayload["diagnostics"][number]): boolean {
  const message = confluenceDiagnosticText(item).trim().toLowerCase();
  if (!message) return false;
  if (message.includes("no stock candidates available for observation")) return false;
  if (
    message.includes("observation-only output") &&
    message.includes("does not generate trading instructions")
  ) {
    return false;
  }
  if (typeof item === "string") return true;
  return (item.severity ?? "warning") !== "info";
}

export default function StockAnalysisPage() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const [asOfOverride, setAsOfOverride] = useState<string | null>(null);
  const [detailSelection, setDetailSelection] = useState<StockDetailSelection | null>(null);
  const [agentDrawerOpen, setAgentDrawerOpen] = useState(false);
  const [deepResearchRequested, setDeepResearchRequested] = useState(false);
  const [queueSearchText, setQueueSearchText] = useState("");
  const [queueLedgerOpen, setQueueLedgerOpen] = useState(false);
  const [boundaryDiagnosticsOpen, setBoundaryDiagnosticsOpen] = useState(false);
  const [activeWorkbenchFactId, setActiveWorkbenchFactId] = useState<string | null>(null);
  const [focusedEndpointKey, setFocusedEndpointKey] = useState<string | null>(null);
  const [requestedEndpointKeys, setRequestedEndpointKeys] = useState<string[]>([]);
  const [sectorDetailOpen, setSectorDetailOpen] = useState(false);
  const {
    sectorFilterSectorCode,
    sectorView,
    sectorSeriesCollapseKeys,
    sectorSeriesWindow,
    sectorSeriesExpanded,
    toggleSectorFilter,
    handleSectorViewChange,
    handleSectorSeriesCollapseChange,
    handleSectorSeriesWindowChange,
  } = useSectorPanelState();
  const { sectorSort, toggleSort, renderSortSuffix } = useSectorSortState();
  const { toggleStrategyCard, isStrategyCardExpanded } = useStrategyCardExpansion();
  const {
    firstScreenAnalyticsTab,
    firstScreenAnalyticsRequested,
    firstScreenPriorityRequested,
    firstScreenOptimizationRequested,
    handleFirstScreenAnalyticsTabChange,
  } = useFirstScreenAnalyticsTabs();
  const candidateHistoryEndpointRequested = requestedEndpointKeys.includes("candidate-history");
  const cycleProxyEndpointRequested = requestedEndpointKeys.includes("cycle-proxy");
  const portfolioProxyEndpointRequested = requestedEndpointKeys.includes("portfolio-proxy");

  const strategyQueryKey = ["stock-analysis", "workbench", asOfOverride ?? "__default"] as const;

  const strategyQuery = useQuery({
    queryKey: strategyQueryKey,
    queryFn: () =>
      client.getStockAnalysisWorkbench({
        ...(asOfOverride ? { asOfDate: asOfOverride } : {}),
        topK: 10,
      }),
    ...stockAnalysisReadQueryOptions,
  });

  const strategyPayload = extractWorkbenchStrategyPayload(strategyQuery.data?.result);
  const workbenchPayload: StockAnalysisWorkbenchPayload | null = strategyQuery.data?.result ?? null;
  const resultMeta = strategyQuery.data?.result_meta;
  const formalUseAllowed = resolveStockAnalysisFormalUseAllowed(
    workbenchPayload?.formal_use_allowed,
    resultMeta?.formal_use_allowed,
  );
  const analyticsAsOf = strategyPayload?.as_of_date ?? null;
  const {
    isRefreshing: isRefreshingChoiceStock,
    refreshStatusMessage: stockRefreshStatusMessage,
    refreshStatusTone: stockRefreshStatusTone,
    refreshStockSelection,
  } = useStockSelectionRefresh({
    client,
    queryClient,
    asOfDate: analyticsAsOf ?? undefined,
  });
  const deferredSectionsEnabled = Boolean(strategyPayload?.as_of_date);
  const cycleFrameworkSection = useDeferredSectionSeen<HTMLElement>(deferredSectionsEnabled);
  const strategyPrioritySection = useDeferredSectionSeen<HTMLElement>(deferredSectionsEnabled);
  const strategyBacktestSection = useDeferredSectionSeen<HTMLElement>(deferredSectionsEnabled);
  const strategyOptimizationSection = useDeferredSectionSeen<HTMLElement>(deferredSectionsEnabled);
  const shouldMountDeepResearch = deepResearchRequested;

  const confluenceQuery = useQuery({
    queryKey: ["stock-analysis", "livermore-signal-confluence", strategyPayload?.as_of_date ?? "__none"],
    queryFn: () =>
      client.getLivermoreSignalConfluence({
        asOfDate: strategyPayload?.as_of_date ?? undefined,
      }),
    enabled: Boolean(strategyPayload?.as_of_date) && shouldMountDeepResearch,
    ...stockAnalysisReadQueryOptions,
  });

  const confluencePayload: LivermoreSignalConfluencePayload | null =
    confluenceQuery.data?.result ?? null;
  const strategyFreshnessMeta = useMemo(
    () => pickStockFreshnessMeta(strategyQuery.data?.result_meta),
    [strategyQuery.data?.result_meta],
  );

  const decisionSummary = useMemo(
    () =>
      strategyPayload ? buildDecisionSummary(strategyPayload, strategyFreshnessMeta) : null,
    [strategyPayload, strategyFreshnessMeta],
  );


  const reviewQueueEmptyState = useMemo(
    () => (strategyPayload ? buildReviewQueueEmptyState(strategyPayload) : null),
    [strategyPayload],
  );

  const marketState = useMemo(
    () => (strategyPayload ? buildMarketStateCard(strategyPayload) : null),
    [strategyPayload],
  );

  const strategySectorRows = useMemo(
    () => (strategyPayload ? buildSectorRows(strategyPayload) : []),
    [strategyPayload],
  );
  const shouldLoadSectorSeriesFallback = Boolean(
    analyticsAsOf &&
      strategyPayload &&
      strategySectorRows.length === 0,
  );
  const {
    sectorRankSeriesQuery,
    sectorSeriesFallbackRows,
    sectorSeriesTableRows,
    sectorSeriesTrendChartOption,
    sectorSeriesTrendLines,
    sectorSeriesUnsupportedNotes,
  } = useSectorRankSeriesSupport({
    client,
    analyticsAsOf,
    sectorSeriesWindow,
    sectorSeriesExpanded,
    shouldLoadFallback: shouldLoadSectorSeriesFallback,
  });

  const sectorRowsFull = useMemo(
    () => (strategySectorRows.length > 0 ? strategySectorRows : sectorSeriesFallbackRows),
    [sectorSeriesFallbackRows, strategySectorRows],
  );
  const sectorRowsSource =
    strategySectorRows.length > 0 ? "snapshot" : sectorSeriesFallbackRows.length > 0 ? "series" : "empty";
  const sectorRowsSourceLabel =
    sectorRowsSource === "series" ? "支撑序列补全" : sectorRowsSource === "snapshot" ? "策略快照" : "待补";
  const sectorOverview = useMemo(() => buildStockSectorOverviewState(sectorRowsFull), [sectorRowsFull]);
  const { leaderRow: sectorLeaderRow, tailRow: sectorTailRow, coverageCount: sectorCoverageCount } = sectorOverview;

  const sectorViewRows = useMemo(
    () => buildSectorViewRows(sectorRowsFull, sectorView),
    [sectorRowsFull, sectorView],
  );

  const sortedDetailRows = useMemo(() => {
    const cmp = buildSectorTableSortComparator(sectorSort.key, sectorSort.order);
    return [...sectorRowsFull].sort(cmp);
  }, [sectorRowsFull, sectorSort]);

  const reviewQueue = useMemo(() => {
    const strategyQueueSourceModule =
      strategyPayload &&
      !isStockModulePrimaryExcluded(strategyPayload, "hybrid_fusion") &&
      (strategyPayload.hybrid_fusion_candidates?.items.length ?? 0) > 0
        ? "hybrid_fusion_candidates"
        : strategyPayload &&
            !isStockModulePrimaryExcluded(strategyPayload, "stock_candidates") &&
            (strategyPayload.stock_candidates?.items.length ?? 0) > 0
          ? "stock_candidates"
          : strategyPayload &&
              !isStockModulePrimaryExcluded(strategyPayload, "fresh_trend_watchlist") &&
              (strategyPayload.fresh_trend_watchlist?.items.length ?? 0) > 0
            ? "fresh_trend_watchlist"
            : null;
    const strategyQueue = strategyPayload
      ? buildCandidateReviewQueue(strategyPayload)
      : [];
    const workbenchRows = workbenchPayload?.first_screen.review_queue ?? [];
    const workbenchQueue = buildStockAnalysisWorkbenchReviewQueue(workbenchRows);
    return enrichStockAnalysisWorkbenchReviewQueue(
      workbenchQueue,
      strategyQueue,
      strategyQueueSourceModule,
      strategyPayload?.stock_candidates?.position_size_hint,
    );
  }, [strategyPayload, workbenchPayload]);

  const gateState = strategyPayload?.market_gate.state;
  const meanReversionPayload = strategyPayload?.mean_reversion_candidates;
  const meanReversionMarketActive = gateState === "WARM";
  const factorScreenPayload = strategyPayload?.factor_screen_candidates;
  const factorScreenPrimaryExcluded = isStockModulePrimaryExcluded(strategyPayload, "factor_screen_candidates");
  const primaryFactorScreenCandidateCount = factorScreenPrimaryExcluded ? 0 : (factorScreenPayload?.candidate_count ?? 0);
  const factorScreenCoverageNote =
    !factorScreenPrimaryExcluded && factorScreenPayload?.coverage_note
      ? localizeStockBackendText(factorScreenPayload.coverage_note, "factor_screen_candidates")
      : null;
  const hybridFusionPayload = strategyPayload?.hybrid_fusion_candidates;
  const hybridFusionObservationCandidateCount = hybridFusionPayload?.candidate_count ?? 0;
  const factorScreenObservationCandidateCount = factorScreenPayload?.candidate_count ?? 0;
  const authoritativeQueueSourceModules = reviewQueue.flatMap((card) => {
    const sourceModule = card.rawFields.find((field) => field.key === "source_module_key")?.value.trim();
    return sourceModule ? [sourceModule] : [];
  });
  const hasCompleteAuthoritativeQueueSources =
    reviewQueue.length > 0 && authoritativeQueueSourceModules.length === reviewQueue.length;
  const reviewQueueUsesHybridFusion = hasCompleteAuthoritativeQueueSources
    ? authoritativeQueueSourceModules.every((sourceModule) => sourceModule === "hybrid_fusion_candidates")
    : Boolean(strategyPayload) &&
      !isStockModulePrimaryExcluded(strategyPayload!, "hybrid_fusion") &&
      reviewQueue.some((card) => card.rawFields.some((field) => field.key === "fusion_score"));
  const cycleRotationFramework = strategyPayload?.cycle_rotation_framework;
  const cycleMacroLayerSummary = useMemo(
    () => (strategyPayload ? buildCycleMacroLayerSummary(strategyPayload) : null),
    [strategyPayload],
  );

  const consensusSummary = useMemo(
    () => buildConsensusSummary(strategyPayload),
    [strategyPayload],
  );

  const strategyLensItems = useMemo(
    () => (strategyPayload ? buildStrategyLensItems(strategyPayload, consensusSummary) : []),
    [strategyPayload, consensusSummary],
  );

  const consensusFirstScreenItems = useMemo(
    () => consensusSummary.items.slice(0, 8),
    [consensusSummary.items],
  );
  const consensusHitCount = consensusSummary.items.filter((item) => item.consensusCount >= 2).length;

  const factorPreviewItems = useMemo(
    () => factorScreenPayload?.items.slice(0, 10) ?? [],
    [factorScreenPayload?.items],
  );

  const meanReversionPreviewItems = useMemo(
    () => (meanReversionMarketActive ? meanReversionPayload?.items.slice(0, 8) ?? [] : []),
    [meanReversionMarketActive, meanReversionPayload?.items],
  );

  function openKlineRadarItem(item: StockAnalysisKlineRadarItem) {
    const ranks = lookupStockStrategyRanks(strategyPayload ?? null, item.stockCode);
    setDetailSelection(
      buildRankContextDetailSelection({
        stockCode: item.stockCode,
        stockName: item.stockName,
        sectorCode: item.sectorCode,
        sectorName: item.sectorName,
        source: item.detailSource,
        ranks,
      }),
    );
  }

  function scrollToStockSection(targetId: string) {
    const maxAttempts = 150;
    let attempt = 0;

    function scrollWhenReady() {
      const target =
        document.getElementById(targetId) ??
        document.querySelector<HTMLElement>(`[data-testid="${targetId}"]`);
      if (!target) {
        if (attempt === 0) {
          setDeepResearchRequested(true);
        }
        attempt += 1;
        if (attempt < maxAttempts) {
          window.setTimeout(scrollWhenReady, 20);
        }
        return;
      }

      let disclosure = target.closest("details");
      while (disclosure) {
        disclosure.open = true;
        disclosure = disclosure.parentElement?.closest("details") ?? null;
      }

      target.scrollIntoView?.({ behavior: "smooth", block: "start" });
    }

    window.setTimeout(scrollWhenReady, 0);
  }

  const themeBreakoutCards = useMemo(
    () =>
      shouldMountDeepResearch && strategyPayload ? buildThemeBreakoutCards(strategyPayload) : [],
    [shouldMountDeepResearch, strategyPayload],
  );

  const themeLeaderPreviewItems = useMemo(
    () => (shouldMountDeepResearch ? buildThemeLeaderPreviewItems(themeBreakoutCards, 12) : []),
    [shouldMountDeepResearch, themeBreakoutCards],
  );

  const heavyweight = useStockHeavyweightSection({ strategyPayload, deepResearchOpen: shouldMountDeepResearch });

  const themeEvidenceRows = useMemo(
    () =>
      shouldMountDeepResearch && strategyPayload
        ? buildThemeEvidenceStateRows(strategyPayload)
        : [],
    [shouldMountDeepResearch, strategyPayload],
  );

  const themeBreakoutReviewItems = useMemo(
    () =>
      shouldMountDeepResearch && strategyPayload
        ? buildThemeBreakoutReviewItems(strategyPayload)
        : [],
    [shouldMountDeepResearch, strategyPayload],
  );

  const sectorFilterSummary = useMemo(
    () => (strategyPayload ? buildSectorFilterSummary(strategyPayload, sectorFilterSectorCode) : null),
    [strategyPayload, sectorFilterSectorCode],
  );

  const selectedSectorLabel = sectorFilterSectorCode ? (sectorFilterSummary?.sectorLabel ?? sectorFilterSectorCode) : null;

  const sectorFilterView = useMemo(
    () =>
      buildReviewQueueSectorFilterView({
        reviewQueue,
        sectorFilterSectorCode,
        selectedSectorLabel,
      }),
    [reviewQueue, sectorFilterSectorCode, selectedSectorLabel],
  );
  const {
    sectorOptions,
    filteredCandidates,
    sectorLinkTone,
  } = sectorFilterView;
  const normalizedQueueSearch = queueSearchText.trim().toLocaleLowerCase();
  const queueVisibleCandidates = useMemo(
    () =>
      filteredCandidates.filter((card) => {
        const haystack = [
          card.stockName,
          card.stockCode,
          card.sectorName,
          card.sectorCode,
          card.headline,
          card.patternNote,
          card.reviewFocus,
          card.invalidationFocus,
        ]
          .join(" ")
          .toLocaleLowerCase();
        const matchesSearch = normalizedQueueSearch.length === 0 || haystack.includes(normalizedQueueSearch);
        return matchesSearch;
      }),
    [filteredCandidates, normalizedQueueSearch],
  );
  const queueVisibleCount = queueVisibleCandidates.length;
  const queueTotalCount = reviewQueue.length;
  const queueFiltersActive = normalizedQueueSearch.length > 0 || sectorFilterSectorCode !== null;
  const queueFilterEmptyLabel = normalizedQueueSearch
    ? `搜索“${queueSearchText.trim()}”无匹配候选`
    : sectorFilterSectorCode
      ? `${selectedSectorLabel ?? sectorFilterSectorCode}暂无候选`
      : "当前筛选无匹配候选";
  const queueSectorLinkSummary = sectorFilterSectorCode
    ? queueVisibleCount > 0
      ? `${selectedSectorLabel ?? sectorFilterSectorCode} · ${queueVisibleCount} 个候选`
      : `${selectedSectorLabel ?? sectorFilterSectorCode} · 无候选`
    : `全部行业 · ${queueVisibleCount} 个候选`;
  const queueSectorLinkFocus = queueVisibleCandidates[0]
    ? `首位 ${queueVisibleCandidates[0].stockName} · 距观察 ${queueVisibleCandidates[0].distanceToBreakoutPct}`
    : sectorFilterSectorCode
      ? "该行业暂无线索"
      : normalizedQueueSearch
        ? "当前搜索无匹配线索"
        : "按板块收敛";
  const queueSectorLinkTone = queueVisibleCount === 0 ? "empty" : sectorLinkTone;
  const queueTablePageSize = 10;
  const queueTablePageStart = queueVisibleCount > 0 ? 1 : 0;
  const queueTablePageEnd = Math.min(queueTablePageSize, queueVisibleCount);

  const riskRows = useMemo(
    () => (strategyPayload ? buildRiskExitRows(strategyPayload, confluencePayload) : []),
    [strategyPayload, confluencePayload],
  );
  const {
    riskTriggeredCount,
    riskWatchCount,
    railNextActionFullLabel,
    railNextActionLabel,
  } = buildStockAnalysisRailReviewState({
    reviewQueue,
    riskRows,
    nextReviewAction: decisionSummary?.nextReviewAction,
  });

  const riskExitUnsupported = strategyPayload?.unsupported_outputs.find((output) => output.key === "risk_exit");
  const riskExitBlockerLabel = riskExitUnsupported
    ? riskExitBlockedSummary(riskExitUnsupported.reason)
    : null;
  const railRiskTone =
    riskTriggeredCount > 0
      ? "negative"
      : riskWatchCount > 0 || riskExitUnsupported
        ? "warning"
        : "positive";
  const themeBreakoutUnsupported = strategyPayload?.unsupported_outputs.find((output) => output.key === "theme_breakout");
  const themeBreakoutBlockerCopy = buildThemeBreakoutBlockerCopy(themeBreakoutUnsupported);
  const themeBreakoutBlockerText = themeBreakoutBlockerCopy.text;
  const themeBreakoutBlockerLabel = themeBreakoutBlockerCopy.label;

  const eventMonitorRows = useMemo(
    () => (strategyPayload ? buildStockAnalysisEventMonitorRows(strategyPayload, confluencePayload) : []),
    [strategyPayload, confluencePayload],
  );

  const backendSupplyOverview = useMemo(
    () =>
      strategyPayload
        ? buildBackendSupplyOverview(strategyPayload, {
            quality_flag: strategyQuery.data?.result_meta?.quality_flag,
            vendor_status: strategyQuery.data?.result_meta?.vendor_status,
            fallback_mode: strategyQuery.data?.result_meta?.fallback_mode,
          })
        : null,
    [
      strategyPayload,
      strategyQuery.data?.result_meta?.quality_flag,
      strategyQuery.data?.result_meta?.vendor_status,
      strategyQuery.data?.result_meta?.fallback_mode,
    ],
  );

  const sectorStrengthChartRows = useMemo(() => sectorViewRows.slice(0, 10), [sectorViewRows]);

  const sectorStrengthChartOption = useMemo(
    () =>
      buildSectorStrengthOption({
        rows: sectorStrengthChartRows,
        view: sectorView,
        activeSectorCode: sectorFilterSectorCode,
      }),
    [sectorFilterSectorCode, sectorStrengthChartRows, sectorView],
  );

  const closedLoopMeta = useMemo(
    () =>
      mergeStockClosedLoopMeta(
        confluencePayload?.closed_loop_state != null,
        strategyQuery.data?.result_meta,
        confluenceQuery.data?.result_meta,
      ),
    [confluencePayload?.closed_loop_state, confluenceQuery.data?.result_meta, strategyQuery.data?.result_meta],
  );

  const closedLoopSummary = useMemo(
    () =>
      strategyPayload ? buildClosedLoopSummary(strategyPayload, confluencePayload, closedLoopMeta) : null,
    [strategyPayload, confluencePayload, closedLoopMeta],
  );

  const boundarySummary = useMemo(
    () =>
      strategyPayload
        ? buildDataBoundarySummary(strategyPayload, {
            quality_flag: strategyQuery.data?.result_meta?.quality_flag,
            vendor_status: strategyQuery.data?.result_meta?.vendor_status,
            fallback_mode: strategyQuery.data?.result_meta?.fallback_mode,
          })
        : null,
    [
      strategyPayload,
      strategyQuery.data?.result_meta?.quality_flag,
      strategyQuery.data?.result_meta?.vendor_status,
      strategyQuery.data?.result_meta?.fallback_mode,
    ],
  );

  const dailyJudgmentStrip = useMemo(
    () => (strategyPayload ? buildDailyJudgmentStrip(strategyPayload) : null),
    [strategyPayload],
  );

  const evidenceStatusItems = useMemo(
    () =>
      strategyPayload
        ? buildStockAnalysisEvidenceStatus(strategyPayload, {
            quality_flag: strategyQuery.data?.result_meta?.quality_flag,
            vendor_status: strategyQuery.data?.result_meta?.vendor_status,
            fallback_mode: strategyQuery.data?.result_meta?.fallback_mode,
            source_version: strategyQuery.data?.result_meta?.source_version,
            rule_version: strategyQuery.data?.result_meta?.rule_version,
            trace_id: strategyQuery.data?.result_meta?.trace_id,
          })
        : [],
    [
      strategyPayload,
      strategyQuery.data?.result_meta?.quality_flag,
      strategyQuery.data?.result_meta?.vendor_status,
      strategyQuery.data?.result_meta?.fallback_mode,
      strategyQuery.data?.result_meta?.source_version,
      strategyQuery.data?.result_meta?.rule_version,
      strategyQuery.data?.result_meta?.trace_id,
    ],
  );
  const boundaryRailItems = useMemo(
    () =>
      evidenceStatusItems.filter((item) =>
        ["as-of-date", "rule-version", "quality", "exceptions"].includes(item.key),
      ),
    [evidenceStatusItems],
  );
  const boundaryRailIssueCount = boundaryRailItems.filter((item) => item.tone !== "positive").length;
  const workbenchFallbackLabel =
    workbenchPayload?.stale && workbenchPayload.fallback_date
      ? workbenchPayload.requested_as_of_date &&
        workbenchPayload.requested_as_of_date !== workbenchPayload.fallback_date
        ? `请求日 ${workbenchPayload.requested_as_of_date} 回退至 ${workbenchPayload.fallback_date}`
        : `使用回退快照 ${workbenchPayload.fallback_date}`
      : workbenchPayload?.stale
        ? "页面数据已标记陈旧"
        : null;

  const showStaleBanner = Boolean(
    workbenchFallbackLabel ||
      backendSupplyOverview?.staleSourceRows.length ||
      (strategyQuery.data?.result_meta &&
        (strategyQuery.data.result_meta.quality_flag !== "ok" ||
          strategyQuery.data.result_meta.vendor_status !== "ok" ||
          strategyQuery.data.result_meta.fallback_mode !== "none")),
  );
  const staleBannerLabel = [
    workbenchFallbackLabel,
    backendSupplyOverview?.staleSourceRows.length
      ? `页面数据日 ${backendSupplyOverview.asOfLabel}；${backendSupplyOverview.staleSourceDetailLabel}`
      : null,
    strategyQuery.data?.result_meta && strategyQuery.data.result_meta.quality_flag !== "ok" ? "供数异常" : null,
    strategyQuery.data?.result_meta && strategyQuery.data.result_meta.vendor_status !== "ok" ? "通道异常" : null,
    strategyQuery.data?.result_meta && strategyQuery.data.result_meta.fallback_mode !== "none"
      ? "使用回退快照"
      : null,
  ]
    .filter((item): item is string => Boolean(item))
    .join("；");

  const sectorViewOverview = useMemo(() => buildStockSectorOverviewState(sectorViewRows), [sectorViewRows]);
  const { topBars, bottomBars } = sectorViewOverview;
  const visibleSectorTopBars = topBars.slice(0, SECTOR_STRENGTH_DEFAULT_TOP_COUNT);
  const backgroundSectorTopBars = topBars.slice(SECTOR_STRENGTH_DEFAULT_TOP_COUNT);
  const headerDateValue = normalizeIsoCalendarDate(strategyPayload?.as_of_date);
  const pickerDisplay = normalizeIsoCalendarDate(asOfOverride) ?? headerDateValue;

  const stockDetailAsOfDate = analyticsAsOf ?? undefined;
  const currentMarketState = strategyPayload?.market_gate.state ?? null;
  const strategyScoreQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-strategy-score",
      analyticsAsOf ?? "__none",
      currentMarketState ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreStrategyScore({
        snapshotTo: analyticsAsOf ?? undefined,
        currentMarketState: currentMarketState ?? undefined,
        minSample: 20,
        primaryHorizon: "return_5d",
      }),
    enabled: Boolean(
      analyticsAsOf && (strategyPrioritySection.seen || firstScreenPriorityRequested),
    ),
    ...stockAnalysisReadQueryOptions,
  });
  const strategyScorePayload = strategyScoreQuery.data?.result ?? null;
  const strategyOptimizationQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-strategy-optimization",
      analyticsAsOf ?? "__none",
      currentMarketState ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreStrategyOptimization({
        snapshotTo: analyticsAsOf ?? undefined,
        currentMarketState: currentMarketState ?? undefined,
        minSample: 20,
        primaryHorizon: "return_5d",
      }),
    enabled: Boolean(
      analyticsAsOf && (strategyOptimizationSection.seen || firstScreenOptimizationRequested),
    ),
    ...stockAnalysisReadQueryOptions,
  });
  const strategyOptimizationPayload = strategyOptimizationQuery.data?.result ?? null;
  const strategyOptimizationPrimaryHorizonLabel = strategyOptimizationHorizonLabel(
    strategyOptimizationPayload,
  );
  const strategyOptimizationRows = useMemo(
    () => buildStrategyOptimizationRows(strategyOptimizationPayload),
    [strategyOptimizationPayload],
  );
  const strategyPriorityRows = strategyScorePayload?.current_market_state_rows ?? EMPTY_STRATEGY_PRIORITY_ROWS;
  const strategyBacktestSnapshotFrom = subtractIsoCalendarDays(analyticsAsOf, 10);

  const strategyBacktestQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-candidate-history-strategy-backtest",
      strategyBacktestSnapshotFrom ?? "__none",
      analyticsAsOf ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreCandidateHistory({
        snapshotFrom: strategyBacktestSnapshotFrom ?? undefined,
        snapshotTo: analyticsAsOf ?? undefined,
        limit: 500,
      }),
    enabled: Boolean(
      analyticsAsOf && (strategyBacktestSection.seen || candidateHistoryEndpointRequested),
    ),
    ...stockAnalysisReadQueryOptions,
  });

  const strategyBacktestPayload = strategyBacktestQuery.data?.result ?? null;
  const strategyBacktestRows = useMemo(() => buildStrategyBacktestRows(strategyBacktestPayload), [strategyBacktestPayload]);
  const strategyBacktestSampleCount = useMemo(
    () => resolveStrategyBacktestSampleCount(strategyBacktestPayload),
    [strategyBacktestPayload],
  );
  const strategyBacktestWindow = strategyBacktestPayload?.backtest_window_summary ?? null;
  const cycleProxyBacktestQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-cycle-proxy-backtest",
      analyticsAsOf ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreCycleProxyBacktest({
        snapshotTo: analyticsAsOf ?? undefined,
      }),
    enabled: Boolean(
      analyticsAsOf &&
        cycleRotationFramework &&
        (cycleFrameworkSection.seen || cycleProxyEndpointRequested),
    ),
    ...stockAnalysisReadQueryOptions,
  });
  const cycleProxyBacktestPayload: LivermoreCycleProxyBacktestPayload | null =
    cycleProxyBacktestQuery.data?.result ?? null;
  const cycleProxyBacktestCaliberDisclosure = useMemo(
    () => buildBacktestCaliberDisclosure(cycleProxyBacktestPayload),
    [cycleProxyBacktestPayload],
  );
  const candidateHistoryPortfolioBacktestQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-candidate-history-portfolio-backtest",
      analyticsAsOf ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreCandidateHistoryPortfolioBacktest({
        snapshotTo: analyticsAsOf ?? undefined,
      }),
    enabled: Boolean(
      analyticsAsOf &&
        cycleRotationFramework &&
        (cycleFrameworkSection.seen || portfolioProxyEndpointRequested),
    ),
    ...stockAnalysisReadQueryOptions,
  });
  const candidateHistoryPortfolioBacktestPayload: LivermoreCandidateHistoryPortfolioBacktestPayload | null =
    candidateHistoryPortfolioBacktestQuery.data?.result ?? null;
  const candidateHistoryPortfolioBacktestCaliberDisclosure = useMemo(
    () => buildBacktestCaliberDisclosure(candidateHistoryPortfolioBacktestPayload),
    [candidateHistoryPortfolioBacktestPayload],
  );

  const candidateHistorySlowState = useSlowEvidenceState(strategyBacktestQuery);
  const strategyScoreSlowState = useSlowEvidenceState(strategyScoreQuery);
  const workbenchDigest = useMemo(
    () =>
      buildWorkbenchDataDigest({
        main: strategyPayload,
        signalConfluence: confluencePayload,
        candidateHistory: strategyBacktestPayload,
        strategyScore: strategyScorePayload,
        strategyOptimization: strategyOptimizationPayload,
        cycleProxyBacktest: cycleProxyBacktestPayload,
        portfolioBacktest: candidateHistoryPortfolioBacktestPayload,
        sectorRankSeries: sectorRankSeriesQuery.data?.result ?? null,
        candidateHistoryState: candidateHistorySlowState,
        strategyScoreState: strategyScoreSlowState,
      }),
    [
      candidateHistoryPortfolioBacktestPayload,
      candidateHistorySlowState,
      confluencePayload,
      cycleProxyBacktestPayload,
      sectorRankSeriesQuery.data?.result,
      strategyBacktestPayload,
      strategyOptimizationPayload,
      strategyPayload,
      strategyScorePayload,
      strategyScoreSlowState,
    ],
  );

  const endpointEvidenceItems = useMemo(() => {
    const sectorSeriesPayload = sectorRankSeriesQuery.data?.result ?? null;
    const strategyBacktestMissingInputCount =
      strategyBacktestWindow?.date_reasons.filter((item) => item.reason_code.startsWith("missing_")).length ?? null;

    return buildStockEndpointEvidenceItems([
      {
        key: "strategy",
        label: "主策略快照",
        queryState: endpointQueryState({
          enabled: true,
          isLoading: strategyQuery.isLoading,
          isFetching: strategyQuery.isFetching,
          isError: strategyQuery.isError,
          hasData: Boolean(strategyQuery.data),
        }),
        meta: strategyQuery.data?.result_meta,
        asOfDate: strategyPayload?.as_of_date,
        warningCount: activeStrategyDiagnosticCount(strategyPayload),
        unsupportedCount: activeUnsupportedOutputCount(strategyPayload),
        missingInputCount: activeDataGapCount(strategyPayload),
      },
      {
        key: "signal-confluence",
        label: "信号闭环",
        queryState: endpointQueryState({
          enabled: Boolean(strategyPayload?.as_of_date) && shouldMountDeepResearch,
          isLoading: confluenceQuery.isLoading,
          isFetching: confluenceQuery.isFetching,
          isError: confluenceQuery.isError,
          hasData: Boolean(confluenceQuery.data),
        }),
        meta: confluenceQuery.data?.result_meta,
        asOfDate: confluencePayload?.as_of_date ?? strategyPayload?.as_of_date,
        warningCount: confluenceDiagnosticCount(confluencePayload),
        missingInputCount: replayEvidenceMissingCount(confluencePayload),
        unsupportedCount: 0,
      },
      {
        key: "sector-series",
        label: "板块支撑序列",
        queryState: endpointQueryState({
          enabled: Boolean((sectorSeriesExpanded || shouldLoadSectorSeriesFallback) && analyticsAsOf),
          isLoading: sectorRankSeriesQuery.isLoading,
          isFetching: sectorRankSeriesQuery.isFetching,
          isError: sectorRankSeriesQuery.isError,
          hasData: Boolean(sectorRankSeriesQuery.data),
        }),
        meta: sectorRankSeriesQuery.data?.result_meta,
        asOfDate: sectorSeriesPayload?.as_of_date ?? analyticsAsOf,
        warningCount: sectorSeriesPayload ? sectorSeriesPayload.unsupported_notes.length : null,
        missingInputCount: sectorSeriesPayload?.state === "missing" ? 1 : 0,
        unsupportedCount: 0,
      },
      {
        key: "strategy-score",
        label: "优先级评分",
        queryState: endpointQueryState({
          enabled: Boolean(analyticsAsOf && (strategyPrioritySection.seen || firstScreenPriorityRequested)),
          isLoading: strategyScoreQuery.isLoading,
          isFetching: strategyScoreQuery.isFetching,
          isError: strategyScoreQuery.isError,
          hasData: Boolean(strategyScoreQuery.data),
        }),
        meta: strategyScoreQuery.data?.result_meta,
        asOfDate: strategyScorePayload?.as_of_date ?? analyticsAsOf,
        snapshotFrom: strategyScorePayload?.snapshot_from,
        snapshotTo: strategyScorePayload?.snapshot_to,
        warningCount: strategyScorePayload
          ? strategyScorePayload.rows.filter((row) => row.sample_status !== "sufficient").length
          : null,
        missingInputCount: backtestWindowPendingDateCount(strategyScorePayload?.backtest_window_summary),
        unsupportedCount: backtestWindowUnsupportedDateCount(strategyScorePayload?.backtest_window_summary),
      },
      {
        key: "candidate-history",
        label: "策略回溯窗口",
        queryState: endpointQueryState({
          enabled: Boolean(
            analyticsAsOf && (strategyBacktestSection.seen || candidateHistoryEndpointRequested),
          ),
          isLoading: strategyBacktestQuery.isLoading,
          isFetching: strategyBacktestQuery.isFetching,
          isError: strategyBacktestQuery.isError,
          hasData: Boolean(strategyBacktestQuery.data),
        }),
        meta: strategyBacktestQuery.data?.result_meta,
        snapshotFrom: strategyBacktestPayload?.snapshot_from ?? strategyBacktestSnapshotFrom,
        snapshotTo: strategyBacktestPayload?.snapshot_to ?? analyticsAsOf,
        warningCount: backtestWindowPendingDateCount(strategyBacktestWindow),
        unsupportedCount: backtestWindowUnsupportedDateCount(strategyBacktestWindow),
        missingInputCount: strategyBacktestMissingInputCount,
      },
      {
        key: "strategy-optimization",
        label: "策略优化",
        queryState: endpointQueryState({
          enabled: Boolean(analyticsAsOf && (strategyOptimizationSection.seen || firstScreenOptimizationRequested)),
          isLoading: strategyOptimizationQuery.isLoading,
          isFetching: strategyOptimizationQuery.isFetching,
          isError: strategyOptimizationQuery.isError,
          hasData: Boolean(strategyOptimizationQuery.data),
        }),
        meta: strategyOptimizationQuery.data?.result_meta,
        asOfDate: strategyOptimizationPayload?.as_of_date ?? analyticsAsOf,
        snapshotFrom: strategyOptimizationPayload?.snapshot_from,
        snapshotTo: strategyOptimizationPayload?.snapshot_to,
        warningCount: strategyOptimizationPayload?.sample_maturity?.insufficient_count ?? null,
        missingInputCount: strategyOptimizationPayload?.pending_summary.pending_rows ?? null,
        unsupportedCount: backtestWindowUnsupportedDateCount(strategyOptimizationPayload?.backtest_window_summary),
      },
      {
        key: "cycle-proxy",
        label: "周期代理回溯",
        queryState: endpointQueryState({
          enabled: Boolean(
            analyticsAsOf &&
              cycleRotationFramework &&
              (cycleFrameworkSection.seen || cycleProxyEndpointRequested),
          ),
          isLoading: cycleProxyBacktestQuery.isLoading,
          isFetching: cycleProxyBacktestQuery.isFetching,
          isError: cycleProxyBacktestQuery.isError,
          hasData: Boolean(cycleProxyBacktestQuery.data),
        }),
        meta: cycleProxyBacktestQuery.data?.result_meta,
        snapshotFrom: cycleProxyBacktestPayload?.snapshot_from,
        snapshotTo: cycleProxyBacktestPayload?.snapshot_to ?? analyticsAsOf,
        warningCount: cycleProxyBacktestPayload?.warnings.length ?? null,
        missingInputCount: cycleProxyBacktestPayload?.missing_full_strategy_inputs.length ?? null,
        unsupportedCount: cycleProxyBacktestPayload?.status === "unsupported" ? 1 : 0,
      },
      {
        key: "portfolio-proxy",
        label: "组合代理回溯",
        queryState: endpointQueryState({
          enabled: Boolean(
            analyticsAsOf &&
              cycleRotationFramework &&
              (cycleFrameworkSection.seen || portfolioProxyEndpointRequested),
          ),
          isLoading: candidateHistoryPortfolioBacktestQuery.isLoading,
          isFetching: candidateHistoryPortfolioBacktestQuery.isFetching,
          isError: candidateHistoryPortfolioBacktestQuery.isError,
          hasData: Boolean(candidateHistoryPortfolioBacktestQuery.data),
        }),
        meta: candidateHistoryPortfolioBacktestQuery.data?.result_meta,
        snapshotFrom: candidateHistoryPortfolioBacktestPayload?.snapshot_from,
        snapshotTo: candidateHistoryPortfolioBacktestPayload?.snapshot_to ?? analyticsAsOf,
        warningCount: candidateHistoryPortfolioBacktestPayload?.warnings.length ?? null,
        missingInputCount: candidateHistoryPortfolioBacktestPayload?.missing_full_strategy_inputs.length ?? null,
        unsupportedCount: candidateHistoryPortfolioBacktestPayload?.status === "unsupported" ? 1 : 0,
      },
    ]);
  }, [
    analyticsAsOf,
    candidateHistoryPortfolioBacktestPayload,
    candidateHistoryPortfolioBacktestQuery.data,
    candidateHistoryPortfolioBacktestQuery.isError,
    candidateHistoryPortfolioBacktestQuery.isFetching,
    candidateHistoryPortfolioBacktestQuery.isLoading,
    candidateHistoryEndpointRequested,
    confluencePayload,
    confluenceQuery.data,
    confluenceQuery.isError,
    confluenceQuery.isFetching,
    confluenceQuery.isLoading,
    cycleFrameworkSection.seen,
    cycleProxyBacktestPayload,
    cycleProxyBacktestQuery.data,
    cycleProxyBacktestQuery.isError,
    cycleProxyBacktestQuery.isFetching,
    cycleProxyBacktestQuery.isLoading,
    cycleProxyEndpointRequested,
    cycleRotationFramework,
    firstScreenPriorityRequested,
    firstScreenOptimizationRequested,
    portfolioProxyEndpointRequested,
    sectorRankSeriesQuery.data,
    sectorRankSeriesQuery.isError,
    sectorRankSeriesQuery.isFetching,
    shouldMountDeepResearch,
    sectorRankSeriesQuery.isLoading,
    sectorSeriesExpanded,
    shouldLoadSectorSeriesFallback,
    strategyBacktestPayload,
    strategyBacktestQuery.data,
    strategyBacktestQuery.isError,
    strategyBacktestQuery.isFetching,
    strategyBacktestQuery.isLoading,
    strategyBacktestSection.seen,
    strategyBacktestSnapshotFrom,
    strategyBacktestWindow,
    strategyOptimizationPayload,
    strategyOptimizationQuery.data,
    strategyOptimizationQuery.isError,
    strategyOptimizationQuery.isFetching,
    strategyOptimizationQuery.isLoading,
    strategyOptimizationSection.seen,
    strategyPayload,
    strategyPrioritySection.seen,
    strategyQuery.data,
    strategyQuery.isError,
    strategyQuery.isFetching,
    strategyQuery.isLoading,
    strategyScorePayload,
    strategyScoreQuery.data,
    strategyScoreQuery.isError,
    strategyScoreQuery.isFetching,
    strategyScoreQuery.isLoading,
  ]);

  const handleWorkbenchFactSelect = (fact: WorkbenchFact) => {
    setActiveWorkbenchFactId(fact.id);

    const endpointKey = WORKBENCH_FACT_ENDPOINT_MAP[fact.id];
    const endpointExists = endpointKey
      ? endpointEvidenceItems.some((item) => item.key === endpointKey)
      : false;
    setFocusedEndpointKey(endpointExists ? endpointKey : null);

    if (fact.id === "open-issues") {
      setBoundaryDiagnosticsOpen(true);
    }
  };

  const handleEndpointSelect = (key: string) => {
    setFocusedEndpointKey(key);
    setActiveWorkbenchFactId(null);
    setBoundaryDiagnosticsOpen(false);
    setRequestedEndpointKeys((current) =>
      current.includes(key) ? current : [...current, key],
    );

    switch (key) {
      case "strategy":
        scrollToStockSection("stock-analysis-review-queue");
        break;
      case "signal-confluence":
        scrollToStockSection("stock-analysis-risk-section");
        break;
      case "sector-series":
        handleSectorSeriesCollapseChange("sector-rank-series-multi");
        scrollToStockSection("stock-analysis-sector-series-panel");
        break;
      case "strategy-score":
        handleFirstScreenAnalyticsTabChange("priority");
        if (!isStrategyCardExpanded("market-priority")) {
          toggleStrategyCard("market-priority");
        }
        scrollToStockSection("stock-analysis-market-priority-summary");
        break;
      case "candidate-history":
        if (!isStrategyCardExpanded("strategy-backtest")) {
          toggleStrategyCard("strategy-backtest");
        }
        scrollToStockSection("stock-analysis-strategy-backtest");
        break;
      case "strategy-optimization":
        handleFirstScreenAnalyticsTabChange("optimization");
        if (!isStrategyCardExpanded("strategy-optimization")) {
          toggleStrategyCard("strategy-optimization");
        }
        scrollToStockSection("stock-analysis-strategy-optimization");
        break;
      case "cycle-proxy":
        if (!isStrategyCardExpanded("cycle-rotation")) {
          toggleStrategyCard("cycle-rotation");
        }
        scrollToStockSection("stock-analysis-cycle-proxy-backtest");
        break;
      case "portfolio-proxy":
        if (!isStrategyCardExpanded("cycle-rotation")) {
          toggleStrategyCard("cycle-rotation");
        }
        scrollToStockSection("stock-analysis-candidate-history-portfolio-backtest");
        break;
      default:
        break;
    }
  };

  const observationClosureReasonInputs = useMemo(() => {
    const reasons: StockObservationClosureReasonInput[] = [];
    const addReason = (reason: StockObservationClosureReasonInput | null | undefined) => {
      if (reason) reasons.push(reason);
    };
    const addListReasons = ({
      endpointId,
      endpointLabel,
      kind,
      fieldRoot,
      values,
      textForValue,
    }: {
      endpointId: string;
      endpointLabel: string;
      kind: StockObservationClosureReasonInput["kind"];
      fieldRoot: string;
      values: unknown[] | null | undefined;
      textForValue: (value: unknown, index: number) => string;
    }) => {
      values?.forEach((value, index) => {
        addReason({
          key: `${endpointId}:${kind}:${fieldRoot}:${index}`,
          endpointId,
          endpointLabel,
          kind,
          fieldPath: `${fieldRoot}.${index}`,
          displayText: textForValue(value, index),
        });
      });
    };

    pushFallbackReason(reasons, {
      endpointId: "strategy",
      endpointLabel: "主策略快照",
      meta: strategyQuery.data?.result_meta,
    });
    pushFallbackReason(reasons, {
      endpointId: "signal-confluence",
      endpointLabel: "信号闭环",
      meta: confluenceQuery.data?.result_meta,
    });
    pushFallbackReason(reasons, {
      endpointId: "sector-series",
      endpointLabel: "板块支撑序列",
      meta: sectorRankSeriesQuery.data?.result_meta,
    });
    pushFallbackReason(reasons, {
      endpointId: "strategy-score",
      endpointLabel: "优先级评分",
      meta: strategyScoreQuery.data?.result_meta,
    });
    pushFallbackReason(reasons, {
      endpointId: "candidate-history",
      endpointLabel: "策略回溯窗口",
      meta: strategyBacktestQuery.data?.result_meta,
    });
    pushFallbackReason(reasons, {
      endpointId: "strategy-optimization",
      endpointLabel: "策略优化",
      meta: strategyOptimizationQuery.data?.result_meta,
    });
    pushFallbackReason(reasons, {
      endpointId: "cycle-proxy",
      endpointLabel: "周期代理回溯",
      meta: cycleProxyBacktestQuery.data?.result_meta,
    });
    pushFallbackReason(reasons, {
      endpointId: "portfolio-proxy",
      endpointLabel: "组合代理回溯",
      meta: candidateHistoryPortfolioBacktestQuery.data?.result_meta,
    });

    addListReasons({
      endpointId: "strategy",
      endpointLabel: "主策略快照",
      kind: "data-gap",
      fieldRoot: "main.result.data_gaps",
      values: strategyPayload?.data_gaps.filter((item) => item.status !== "ready"),
      textForValue: (value) => {
        const gap = value as NonNullable<LivermoreStrategyPayload["data_gaps"]>[number];
        return `${dataGapFamilyLabel(gap.input_family)}：${localizeStockBackendText(gap.evidence, gap.input_family)}`;
      },
    });
    addListReasons({
      endpointId: "strategy",
      endpointLabel: "主策略快照",
      kind: "diagnostic",
      fieldRoot: "main.result.diagnostics",
      values: strategyPayload?.diagnostics.filter((item) => item.severity !== "info"),
      textForValue: (value) => {
        const diagnostic = value as NonNullable<LivermoreStrategyPayload["diagnostics"]>[number];
        return localizeStockBackendText(diagnostic.message, diagnostic.input_family);
      },
    });
    addListReasons({
      endpointId: "strategy",
      endpointLabel: "主策略快照",
      kind: "unsupported",
      fieldRoot: "main.result.unsupported_outputs",
      values: strategyPayload?.unsupported_outputs.filter(isActionableLivermoreUnsupportedOutput),
      textForValue: (value) => {
        const output = value as NonNullable<LivermoreStrategyPayload["unsupported_outputs"]>[number];
        return `${dataGapFamilyLabel(output.key)}：${localizeStockBackendText(output.reason, output.key)}`;
      },
    });
    addListReasons({
      endpointId: "signal-confluence",
      endpointLabel: "信号闭环",
      kind: "diagnostic",
      fieldRoot: "signalConfluence.result.diagnostics",
      values: confluencePayload?.diagnostics.filter(isActionableConfluenceDiagnostic),
      textForValue: (value) =>
        localizeStockBackendText(
          confluenceDiagnosticText(value as LivermoreSignalConfluencePayload["diagnostics"][number]),
          "signal_confluence",
        ),
    });
    addListReasons({
      endpointId: "sector-series",
      endpointLabel: "板块支撑序列",
      kind: "unsupported",
      fieldRoot: "sectorRankSeries.result.unsupported_notes",
      values: sectorRankSeriesQuery.data?.result?.unsupported_notes,
      textForValue: (value) => localizeStockBackendText(String(value), "sector_rank"),
    });
    addListReasons({
      endpointId: "cycle-proxy",
      endpointLabel: "周期代理回溯",
      kind: "warning",
      fieldRoot: "cycleProxyBacktest.result.warnings",
      values: cycleProxyBacktestPayload?.warnings,
      textForValue: (value) => localizeStockBackendText(String(value), "cycle_proxy_backtest"),
    });
    addListReasons({
      endpointId: "cycle-proxy",
      endpointLabel: "周期代理回溯",
      kind: "missing-input",
      fieldRoot: "cycleProxyBacktest.result.missing_full_strategy_inputs",
      values: cycleProxyBacktestPayload?.missing_full_strategy_inputs,
      textForValue: (value) => `缺完整策略输入：${dataGapFamilyLabel(String(value))}`,
    });
    addListReasons({
      endpointId: "portfolio-proxy",
      endpointLabel: "组合代理回溯",
      kind: "warning",
      fieldRoot: "portfolioBacktest.result.warnings",
      values: candidateHistoryPortfolioBacktestPayload?.warnings,
      textForValue: (value) => localizeStockBackendText(String(value), "portfolio_proxy_backtest"),
    });
    addListReasons({
      endpointId: "portfolio-proxy",
      endpointLabel: "组合代理回溯",
      kind: "missing-input",
      fieldRoot: "portfolioBacktest.result.missing_full_strategy_inputs",
      values: candidateHistoryPortfolioBacktestPayload?.missing_full_strategy_inputs,
      textForValue: (value) => `缺完整策略输入：${dataGapFamilyLabel(String(value))}`,
    });
    if ((strategyOptimizationPayload?.pending_summary.pending_rows ?? 0) > 0) {
      addReason({
        key: "strategy-optimization:pending-summary",
        endpointId: "strategy-optimization",
        endpointLabel: "策略优化",
        kind: "missing-input",
        fieldPath: "strategyOptimization.result.pending_summary",
        displayText: `优化待处理 ${strategyOptimizationPayload?.pending_summary.pending_rows ?? 0} 行`,
      });
    }
    if ((strategyOptimizationPayload?.sample_maturity?.insufficient_count ?? 0) > 0) {
      addReason({
        key: "strategy-optimization:sample-maturity",
        endpointId: "strategy-optimization",
        endpointLabel: "策略优化",
        kind: "warning",
        fieldPath: "strategyOptimization.result.sample_maturity",
        displayText: `样本成熟度不足 ${strategyOptimizationPayload?.sample_maturity?.insufficient_count ?? 0} 项`,
      });
    }
    return reasons;
  }, [
    candidateHistoryPortfolioBacktestPayload,
    candidateHistoryPortfolioBacktestQuery.data?.result_meta,
    confluencePayload,
    confluenceQuery.data?.result_meta,
    cycleProxyBacktestPayload,
    cycleProxyBacktestQuery.data?.result_meta,
    sectorRankSeriesQuery.data?.result,
    sectorRankSeriesQuery.data?.result_meta,
    strategyBacktestQuery.data?.result_meta,
    strategyOptimizationPayload,
    strategyOptimizationQuery.data?.result_meta,
    strategyPayload,
    strategyQuery.data?.result_meta,
    strategyScoreQuery.data?.result_meta,
  ]);

  const observationClosureSummary = useMemo(
    () =>
      buildObservationClosureSummary({
        endpointItems: endpointEvidenceItems,
        reasonInputs: observationClosureReasonInputs,
        formalUseAllowed,
        approvalStatus: "gap_or_observational",
      }),
    [endpointEvidenceItems, formalUseAllowed, observationClosureReasonInputs],
  );

  const strategyBacktestDateRangeLabel =
    strategyBacktestSnapshotFrom && analyticsAsOf
      ? `${strategyBacktestSnapshotFrom} 至 ${analyticsAsOf}`
      : "日期待补";

  const cycleRotationPanelSummary = useMemo(
    () =>
      cycleRotationFramework
        ? buildCycleRotationPanelSummary({
            framework: cycleRotationFramework,
            macroLayer: cycleMacroLayerSummary,
            portfolioBacktest: candidateHistoryPortfolioBacktestPayload,
            proxyBacktest: cycleProxyBacktestPayload,
            portfolioQueryState: resolvePanelQueryState({
              enabled: Boolean(
                analyticsAsOf &&
                  cycleRotationFramework &&
                  (cycleFrameworkSection.seen || portfolioProxyEndpointRequested),
              ),
              isLoading: candidateHistoryPortfolioBacktestQuery.isLoading,
              isError: candidateHistoryPortfolioBacktestQuery.isError,
            }),
            proxyQueryState: resolvePanelQueryState({
              enabled: Boolean(
                analyticsAsOf &&
                  cycleRotationFramework &&
                  (cycleFrameworkSection.seen || cycleProxyEndpointRequested),
              ),
              isLoading: cycleProxyBacktestQuery.isLoading,
              isError: cycleProxyBacktestQuery.isError,
            }),
          })
        : null,
    [
      cycleRotationFramework,
      cycleMacroLayerSummary,
      candidateHistoryPortfolioBacktestPayload,
      cycleProxyBacktestPayload,
      analyticsAsOf,
      cycleFrameworkSection.seen,
      cycleProxyEndpointRequested,
      portfolioProxyEndpointRequested,
      candidateHistoryPortfolioBacktestQuery.isLoading,
      candidateHistoryPortfolioBacktestQuery.isError,
      cycleProxyBacktestQuery.isLoading,
      cycleProxyBacktestQuery.isError,
    ],
  );

  const themeBreakoutPanelSummary = useMemo(
    () =>
      shouldMountDeepResearch && strategyPayload
        ? buildThemeBreakoutPanelSummary({
            payload: strategyPayload,
            cards: themeBreakoutCards,
            reviewCount: themeBreakoutReviewItems.length,
            unsupportedReason: themeBreakoutUnsupported?.reason,
          })
        : null,
    [
      shouldMountDeepResearch,
      strategyPayload,
      themeBreakoutCards,
      themeBreakoutReviewItems.length,
      themeBreakoutUnsupported?.reason,
    ],
  );

  const consensusReviewPanelSummary = useMemo(
    () => buildConsensusReviewPanelSummary(consensusSummary),
    [consensusSummary],
  );

  const marketPriorityPanelSummary = useMemo(
    () =>
      buildMarketPriorityPanelSummary({
        rows: strategyPriorityRows,
        payload: strategyScorePayload,
        marketState: currentMarketState,
        queryState: resolvePanelQueryState({
          enabled: Boolean(
            analyticsAsOf && (strategyPrioritySection.seen || firstScreenPriorityRequested),
          ),
          isLoading: strategyScoreQuery.isLoading,
          isError: strategyScoreQuery.isError,
        }),
        errorMessage: strategyScoreQuery.isError ? rawErrorMessage(strategyScoreQuery.error) : undefined,
      }),
    [
      strategyPriorityRows,
      strategyScorePayload,
      currentMarketState,
      analyticsAsOf,
      firstScreenPriorityRequested,
      strategyPrioritySection.seen,
      strategyScoreQuery.isLoading,
      strategyScoreQuery.isError,
      strategyScoreQuery.error,
    ],
  );

  const strategyBacktestPanelSummary = useMemo(
    () =>
      buildStrategyBacktestPanelSummary({
        payload: strategyBacktestPayload,
        sampleCount: strategyBacktestSampleCount,
        window: strategyBacktestWindow,
        dateRangeLabel: strategyBacktestDateRangeLabel,
        rows: strategyBacktestRows,
        queryState: resolvePanelQueryState({
          enabled: Boolean(
            analyticsAsOf && (strategyBacktestSection.seen || candidateHistoryEndpointRequested),
          ),
          isLoading: strategyBacktestQuery.isLoading,
          isError: strategyBacktestQuery.isError,
        }),
        errorMessage: strategyBacktestQuery.isError ? rawErrorMessage(strategyBacktestQuery.error) : undefined,
      }),
    [
      strategyBacktestPayload,
      strategyBacktestSampleCount,
      strategyBacktestWindow,
      strategyBacktestDateRangeLabel,
      strategyBacktestRows,
      analyticsAsOf,
      candidateHistoryEndpointRequested,
      strategyBacktestSection.seen,
      strategyBacktestQuery.isLoading,
      strategyBacktestQuery.isError,
      strategyBacktestQuery.error,
    ],
  );

  const strategyOptimizationPanelSummary = useMemo(
    () =>
      buildStrategyOptimizationPanelSummary({
        payload: strategyOptimizationPayload,
        rows: strategyOptimizationRows,
        queryState: resolvePanelQueryState({
          enabled: Boolean(
            analyticsAsOf &&
              (strategyOptimizationSection.seen || firstScreenOptimizationRequested),
          ),
          isLoading: strategyOptimizationQuery.isLoading,
          isError: strategyOptimizationQuery.isError,
        }),
        errorMessage: strategyOptimizationQuery.isError
          ? rawErrorMessage(strategyOptimizationQuery.error)
          : undefined,
      }),
    [
      strategyOptimizationPayload,
      strategyOptimizationRows,
      analyticsAsOf,
      firstScreenOptimizationRequested,
      strategyOptimizationSection.seen,
      strategyOptimizationQuery.isLoading,
      strategyOptimizationQuery.isError,
      strategyOptimizationQuery.error,
    ],
  );

  const observationPoolsPanelSummary = useMemo(
    () =>
      buildObservationPoolsPanelSummary({
        gateState,
        meanReversionCount: meanReversionPayload?.candidate_count ?? 0,
        factorScreenCount: factorScreenObservationCandidateCount,
        hybridFusionCount: hybridFusionObservationCandidateCount,
        meanReversionActive: meanReversionMarketActive,
      }),
    [
      gateState,
      meanReversionPayload?.candidate_count,
      factorScreenObservationCandidateCount,
      hybridFusionObservationCandidateCount,
      meanReversionMarketActive,
    ],
  );

  const eventsMonitoringPanelSummary = useMemo(
    () => buildEventsMonitoringPanelSummary(eventMonitorRows),
    [eventMonitorRows],
  );

  const deepAnalysisGateSummary = useMemo(() => {
    if (!shouldMountDeepResearch) return null;
    const topPriority =
      strategyPriorityRows.find(
        (row) => row.priority_label === "优先复核" && row.sample_status === "sufficient",
      ) ?? strategyPriorityRows.find((row) => row.sample_status === "sufficient");
    return buildDeepAnalysisGateSummary({
      gateState,
      themeUnsupportedReason: themeBreakoutUnsupported?.reason,
      priorityStrategyLabel: topPriority
        ? strategyDisplayLabel(topPriority.strategy_label, topPriority.signal_kind)
        : null,
    });
  }, [gateState, shouldMountDeepResearch, themeBreakoutUnsupported?.reason, strategyPriorityRows]);

  const deepZoneAuditRows = useMemo(
    () =>
      shouldMountDeepResearch
        ? buildDeepZoneAuditRows({
            cycleRotationSummary: cycleRotationPanelSummary,
            themeBreakoutSummary: themeBreakoutPanelSummary,
            strategyBacktestSummary: strategyBacktestPanelSummary,
            strategyBacktestDateRangeLabel,
            consensusItemCount: consensusSummary.items.length,
            reviewQueueCount: queueTotalCount,
            consensusReviewSummary: consensusReviewPanelSummary,
            marketPrioritySummary: marketPriorityPanelSummary,
            eventsMonitoringSummary: eventsMonitoringPanelSummary,
            eventMonitorCount: eventMonitorRows.length,
          })
        : [],
    [
      consensusReviewPanelSummary,
      consensusSummary.items.length,
      cycleRotationPanelSummary,
      eventMonitorRows.length,
      eventsMonitoringPanelSummary,
      marketPriorityPanelSummary,
      queueTotalCount,
      shouldMountDeepResearch,
      strategyBacktestDateRangeLabel,
      strategyBacktestPanelSummary,
      themeBreakoutPanelSummary,
    ],
  );

  const stockAnalysisAgentPageContext = useMemo(
    () =>
      buildStockAnalysisAgentPageContext({
        asOfDate: strategyPayload?.as_of_date ?? null,
        requestedAsOfDate: strategyPayload?.requested_as_of_date ?? asOfOverride ?? null,
        sectorFilterSectorCode,
        sectorFilterLabel: selectedSectorLabel,
        sectorView,
        detailSelection,
      }),
    [
      asOfOverride,
      detailSelection,
      sectorFilterSectorCode,
      sectorView,
      selectedSectorLabel,
      strategyPayload?.as_of_date,
      strategyPayload?.requested_as_of_date,
    ],
  );
  const workbenchCanReviewCandidates =
    workbenchPayload?.decision_summary.can_review_candidates ?? (queueTotalCount > 0 && boundaryRailIssueCount === 0);
  const workbenchAnswerState =
    workbenchPayload?.page_question.answer_state ??
    (workbenchCanReviewCandidates ? (queueTotalCount > 0 ? "review_ready" : "no_data") : "blocked");
  const workbenchPrimaryBlocker =
    workbenchPayload?.decision_summary.primary_blocker ??
    (workbenchCanReviewCandidates ? null : "data_gap_missing");
  const workbenchReviewBlocked =
    workbenchAnswerState === "blocked" || workbenchCanReviewCandidates === false;
  const workbenchAnswerLabel =
    workbenchAnswerState === "blocked"
      ? "阻断"
      : workbenchAnswerState === "review_ready"
        ? "可复核"
        : workbenchAnswerState === "limited_review"
          ? "有限复核"
        : workbenchAnswerState === "no_data"
          ? "暂无候选"
          : "待确认";
  const workbenchCandidateReviewLabel = workbenchCanReviewCandidates ? "可复核" : "只读观察";
  const localizedWorkbenchPrimaryBlocker = workbenchPrimaryBlocker
    ? /data.?gap|数据缺口/i.test(workbenchPrimaryBlocker)
      ? "数据缺口状态未闭合"
      : (() => {
          const localized = localizeStockBackendText(workbenchPrimaryBlocker);
          return /[A-Za-z]{3,}/.test(localized) ? "阻断原因待确认" : localized;
        })()
    : null;
  const workbenchRouteLabel = "/ui/market-data/stock-analysis/workbench";
  const workbenchResultKindLabel = resultMeta?.result_kind ?? "market_data.stock_analysis.workbench";
  const stockWorkbenchStatus = {
    label: strategyQuery.isError
      ? "读取异常"
      : strategyQuery.isLoading
        ? "读取中"
        : workbenchReviewBlocked
          ? "复核阻断"
          : showStaleBanner || boundaryRailIssueCount > 0
          ? "只读复核"
          : "只读观察",
    tone: strategyQuery.isError
      ? "error"
      : strategyQuery.isLoading
        ? "muted"
        : workbenchReviewBlocked
          ? "error"
          : showStaleBanner || boundaryRailIssueCount > 0
          ? "watch"
          : "ok",
    detail: `结论状态：${workbenchAnswerLabel}；候选复核：${workbenchCandidateReviewLabel}；不输出买卖建议或未经核验的正式结论`,
  } as const;
  const sourceVersion = resultMeta?.source_version ?? "来源待返回";
  const sourceVersionSummary = sourceVersion.length > 36 ? "来源明细" : sourceVersion;
  const strategyBasisLabel = stockSupplyBasisLabel(strategyPayload?.basis ?? resultMeta?.basis);
  const apiAccurateReadinessItems = (strategyPayload?.rule_readiness ?? []).slice(0, 4).map((item) => {
    const asOfDetail = `数据日 ${backendSupplyOverview?.asOfLabel ?? strategyPayload?.as_of_date ?? "待确认"}`;
    const stockCandidateCount = strategyPayload?.stock_candidates?.candidate_count;
    const stockInputCount = strategyPayload?.stock_candidates?.input_stock_count ?? factorScreenPayload?.input_stock_count;
    const inputsLabel =
      item.missing_inputs.length > 0 ? item.missing_inputs.slice(0, 3).map(dataGapFamilyLabel).join(" / ") : "输入就绪";
    let metric = "数据待确认";
    let detail = asOfDetail;

    if (item.key === "market_gate") {
      metric = `${backendSupplyOverview?.gateLabel ?? decisionSummary?.gateLabel ?? "门控待确认"} · ${
        backendSupplyOverview?.conditionLabel ?? marketState?.passedLabel ?? "条件待确认"
      }`;
      detail = `${decisionSummary?.exposureLabel ?? "暴露待确认"} · ${asOfDetail}`;
    } else if (item.key === "sector_rank") {
      metric = `${formatApiCount(strategyPayload?.sector_rank?.sector_count ?? sectorRowsFull.length)} 个板块`;
      detail =
        sectorLeaderRow != null
          ? `首位 ${sectorLeaderRow.sectorName} · ${asOfDetail}`
          : `样本 ${formatApiCount(strategyPayload?.sector_rank?.items.length ?? sectorRowsFull.length)} · ${asOfDetail}`;
    } else if (item.key === "stock_pivot") {
      metric = `融合 ${formatApiCount(hybridFusionPayload?.candidate_count)} / 多因子 ${formatApiCount(
        factorScreenPayload?.candidate_count,
      )} / 趋势 ${formatApiCount(stockCandidateCount)}`;
      detail = `输入 ${formatApiCount(stockInputCount)} · ${asOfDetail}`;
    } else if (item.key === "risk_exit") {
      metric = riskExitUnsupported
        ? "退出规则阻断"
        : `触发 ${formatApiCount(strategyPayload?.risk_exit?.signal_count ?? riskTriggeredCount, "0")} / 观察 ${formatApiCount(
            strategyPayload?.risk_exit?.watch_items?.length ?? riskWatchCount,
            "0",
          )}`;
      detail = riskExitBlockerLabel
        ? `${riskExitBlockerLabel} · ${asOfDetail}`
        : `持仓 ${formatApiCount(strategyPayload?.risk_exit?.position_count)} · ${asOfDetail}`;
    }

    return {
      key: item.key,
      label: readinessLabel(item.key),
      status: item.status,
      metric,
      detail,
      summary: localizeStockBackendText(item.summary, item.key),
      missingInputs: item.missing_inputs.map(dataGapFamilyLabel),
      inputsLabel,
    };
  });
  const rawWorkbenchDataGaps: unknown[] = Array.from(workbenchPayload?.first_screen.data_gaps ?? []);
  const normalizedWorkbenchDataGaps = rawWorkbenchDataGaps.map(normalizeWorkbenchDataGap);
  const validWorkbenchDataGaps = normalizedWorkbenchDataGaps.every((gap) => gap !== null)
    ? (normalizedWorkbenchDataGaps as StockAnalysisWorkbenchDataGap[])
    : null;
  const pageDataGaps: Array<LivermoreStrategyPayload["data_gaps"][number] & { blocks_review?: boolean }> =
    rawWorkbenchDataGaps.length > 0 && validWorkbenchDataGaps
      ? validWorkbenchDataGaps
      : strategyPayload?.data_gaps ?? [];
  const themeTaxonomyGapSummary = buildThemeTaxonomyGapSummary(pageDataGaps);
  const activeDataGaps = pageDataGaps.filter(
    (gap) => gap.status !== "ready" || gap.tier === "stale" || gap.tier === "expired",
  );
  const gapBlocksReview = (gap: (typeof activeDataGaps)[number]) =>
    typeof gap.blocks_review === "boolean"
      ? gap.blocks_review
      : (REQUIRED_WORKBENCH_GAP_FAMILIES.has(gap.input_family) && gap.status !== "ready") ||
        gap.tier === "stale" ||
        gap.tier === "expired" ||
        ["stale", "look_ahead", "blocked", "error", "unsupported"].includes(
          String(gap.status).trim().toLowerCase(),
        ) ||
        (typeof gap.age_days === "number" && gap.age_days < 0);
  const orderedDataGaps = activeDataGaps
    .map((gap, index) => ({ gap, index, blocksReview: gapBlocksReview(gap) }))
    .sort(
      (left, right) => Number(right.blocksReview) - Number(left.blocksReview) || left.index - right.index,
    );
  const gapReleaseCards = orderedDataGaps.slice(0, 3);
  const gapOverview = useMemo(() => buildStockDataGapOverview(pageDataGaps), [pageDataGaps]);
  const factorScreenModuleState = useMemo(
    () =>
      strategyPayload?.module_states?.find((state) => state.key === "factor_screen_candidates") ?? null,
    [strategyPayload],
  );
  const factorScreenCard = useMemo(
    () => buildStockFactorScreenCard(factorScreenPayload, factorScreenModuleState),
    [factorScreenModuleState, factorScreenPayload],
  );
  const macroCycleModel = useMemo(
    () => (strategyPayload ? buildStockMacroCycleCard(strategyPayload) : null),
    [strategyPayload],
  );
  const heroModel = useMemo(() => {
    if (!strategyPayload) return null;
    return buildStockFirstScreenHero({
      marketGate: strategyPayload.market_gate,
      reviewBlocked: workbenchReviewBlocked,
      reviewQueueCount: queueTotalCount,
      primaryBlockerLabel: localizedWorkbenchPrimaryBlocker,
      factorScreen: factorScreenCard,
      gapOverview,
    });
  }, [
    factorScreenCard,
    gapOverview,
    localizedWorkbenchPrimaryBlocker,
    queueTotalCount,
    strategyPayload,
    workbenchReviewBlocked,
  ]);
  const sectorCard = useMemo(
    () =>
      buildSectorStrengthCardModel({
        rows: sectorViewRows,
        view: sectorView,
        activeSectorCode: sectorFilterSectorCode,
        sourceLabel: sectorRowsSourceLabel,
        leaderName: sectorLeaderRow ? sectorLeaderRow.sectorName : null,
        seriesLoading: sectorRankSeriesQuery.isLoading,
        seriesErrored: sectorRankSeriesQuery.isError,
        seriesErrorMessage: sectorRankSeriesQuery.isError
          ? errorMessage(sectorRankSeriesQuery.error)
          : null,
      }),
    [sectorFilterSectorCode, sectorLeaderRow, sectorRankSeriesQuery.error, sectorRankSeriesQuery.isError, sectorRankSeriesQuery.isLoading, sectorRowsSourceLabel, sectorView, sectorViewRows],
  );
  const evidenceGapReleaseCards = gapReleaseCards.map(({ gap, index, blocksReview }) => ({
    key: `${gap.input_family}-${gap.status}-${index}`,
    label: dataGapFamilyLabel(gap.input_family),
    statusLabel: statusLabel(gap.tier === "stale" || gap.tier === "expired" ? "stale" : gap.status),
    tone: (blocksReview ? "negative" : gap.status === "partial" ? "neutral" : "warning") as
      | "negative"
      | "warning"
      | "neutral",
    releaseLabel: blocksReview ? "阻断复核释放" : "补证警告",
    evidence: gap.evidence,
  }));
  const evidenceReadinessItems = apiAccurateReadinessItems.map((item) => ({
    ...item,
    statusLabel: readinessStatusLabel(item.status),
  }));
  const backendTableCount = resultMeta?.tables_used?.length ?? 0;
  const dataGapCount = activeDataGaps.length;
  const missingGapCount = activeDataGaps.filter((gap) =>
    ["missing", "blocked", "error", "unsupported"].includes(String(gap.status)),
  ).length;
  const partialGapCount = activeDataGaps.filter(
    (gap) =>
      ["partial", "stale", "warning", "degraded", "deferred"].includes(String(gap.status)) ||
      gap.tier === "stale" ||
      gap.tier === "expired",
  ).length;
  const dataGapDisplay =
    missingGapCount > 0 && partialGapCount > 0
      ? `${missingGapCount}+${partialGapCount}`
      : `${dataGapCount}`;
  const primaryGapLedgerLabel =
    orderedDataGaps.map(({ gap }) => cycleInputLabel(gap.input_family)).slice(0, 3).join(" / ") || "无新增缺口";
  const evidenceRowsLabel =
    typeof resultMeta?.evidence_rows === "number" ? resultMeta.evidence_rows.toLocaleString("zh-CN") : "待返回";
  const queueLeadCandidate = queueVisibleCandidates[0] ?? null;
  const backendTopReviewStockName = workbenchPayload?.decision_summary.top_review_stock_name?.trim() ?? "";
  const backendTopReviewStockCode = workbenchPayload?.decision_summary.top_review_stock_code?.trim() ?? "";
  const workbenchTopReviewStock = [backendTopReviewStockName, backendTopReviewStockCode].filter(Boolean).join(" ") || null;
  const workbenchTopReviewCandidate = backendTopReviewStockCode
    ? reviewQueue.find((candidate) => candidate.stockCode === backendTopReviewStockCode) ?? null
    : queueLeadCandidate;
  const workbenchContractSummary = workbenchPayload
    ? {
        question: "今天是否具备继续复核候选的条件？",
        answerLabel: workbenchAnswerLabel,
        reason: workbenchReviewBlocked
          ? `首要阻断：${localizedWorkbenchPrimaryBlocker ?? "阻断原因待确认"}。`
          : workbenchAnswerState === "no_data"
            ? "当前没有可进入复核队列的候选。"
            : "候选与证据已返回，可继续只读复核。",
        canReviewCandidates: workbenchCanReviewCandidates,
        topReviewStock: workbenchTopReviewStock,
        primaryBlocker: localizedWorkbenchPrimaryBlocker,
        formalUseAllowed,
        routeLabel: workbenchRouteLabel,
        resultKindLabel: workbenchResultKindLabel,
        includeLabel: `请求模块 ${
          workbenchPayload.include.requested
            .map((item) => (item === "evidence_summary" ? "证据摘要" : item === "main" ? "主策略" : "扩展模块"))
            .join(" / ") || "无"
        } · 候选上限 ${workbenchPayload.include.top_k} · 未识别模块 ${
          workbenchPayload.include.unknown.length > 0 ? `${workbenchPayload.include.unknown.length} 项` : "无"
        }`,
      }
    : undefined;
  const queueLeadEvidenceCount = queueLeadCandidate
    ? queueLeadCandidate.primaryEvidence.length + queueLeadCandidate.supportingEvidence.length
    : 0;
  const queueLeadBoundaryCount = queueLeadCandidate?.boundaryEvidence.length ?? boundaryRailIssueCount;
  const queueNextReviewAction = queueLeadCandidate
    ? `下一步：先复核 ${queueLeadCandidate.stockName}（${queueLeadCandidate.stockCode}），${queueLeadCandidate.sectorName}，距观察位 ${queueLeadCandidate.distanceToBreakoutPct}。`
    : queueFiltersActive && queueTotalCount > 0
      ? "当前筛选暂无候选；请调整行业、搜索或证据条件。"
      : (decisionSummary?.nextReviewAction ?? "等待候选");
  const queueNextActionLabel = queueLeadCandidate ? `先复核${queueLeadCandidate.stockName}` : railNextActionLabel;
  const queueNextActionFullLabel = queueLeadCandidate ? queueNextReviewAction : railNextActionFullLabel;
  const queueGateLabel =
    workbenchPayload?.decision_summary.gate_state ??
    workbenchPayload?.decision_summary.gate_label ??
    backendSupplyOverview?.gateLabel ??
    decisionSummary?.gateLabel ??
    "门控待确认";
  const queueGateStatusLabel = queueGateLabel.startsWith("门控") ? queueGateLabel : `门控 ${queueGateLabel}`;
  const observationClosureIssueCount = observationClosureSummary.unresolvedReasons.length;
  const observationClosureLabel = observationClosureIssueCount > 0 ? "待复核" : "只读";
  const observationClosureTone = observationClosureIssueCount > 0 ? "warning" : "positive";
  const queueLoopStatusLabel = workbenchReviewBlocked ? "复核阻断" : `闭环${observationClosureLabel}`;
  const mainModuleStatus = workbenchPayload?.modules?.main?.status ?? (strategyPayload ? "ready" : "missing");
  const mainModuleUnavailable = strategyQuery.isSuccess && strategyPayload == null;
  const queueDataStatusLabel = strategyQuery.isError
    ? "数据异常"
    : strategyQuery.isLoading
      ? "数据读取中"
      : `主包 ${statusLabel(mainModuleStatus)}`;
  const queueDataStatusTone = strategyQuery.isError
    ? "negative"
    : strategyQuery.isLoading
      ? "neutral"
      : mainModuleUnavailable
        ? "negative"
        : "positive";
  const reviewQueueLedgerCount =
    workbenchPayload?.decision_summary.review_queue_count ?? Math.min(queueVisibleCount || queueTotalCount, 3);
  const apiLedgerSourceCells = [
    {
      key: "tables",
      label: "后端表",
      value: backendTableCount > 0 ? `${backendTableCount} 张` : "待返回",
      detail: resultMeta?.tables_used?.slice(0, 4).join(" / ") ?? "后端表待返回",
    },
    {
      key: "evidence",
      label: "证据行",
      value:
        typeof resultMeta?.evidence_rows === "number"
          ? resultMeta.evidence_rows.toLocaleString("zh-CN")
          : "待返回",
      detail: `质量 ${stockSupplyQualityLabel(resultMeta?.quality_flag)} / 通道 ${stockSupplyVendorLabel(
        resultMeta?.vendor_status,
      )} / ${stockSupplyFallbackLabel(resultMeta?.fallback_mode)}`,
    },
    {
      key: "rule",
      label: "规则版本",
      value: compactText(resultMeta?.rule_version ?? "规则待返回", 24),
      detail: resultMeta?.rule_version ?? "规则版本待返回",
    },
    {
      key: "trace",
      label: "链路",
      value: compactText(resultMeta?.trace_id ?? "链路待返回", 18),
      detail: resultMeta?.trace_id ?? "链路待返回",
    },
  ];
  const mainEndpointEvidence = workbenchPayload?.endpoint_evidence?.find((item) => item.key === "main");
  const endpointLedgerItems = [
    {
      key: "main",
      label: "主策略快照",
      status: mainEndpointEvidence?.status ?? mainModuleStatus,
      tone: "positive",
      detail:
        mainEndpointEvidence?.rows != null
          ? `rows=${mainEndpointEvidence.rows.toLocaleString("zh-CN")} / as_of=${
              mainEndpointEvidence.as_of_date ?? strategyPayload?.as_of_date ?? "待确认"
            }`
          : `rows=${evidenceRowsLabel} / as_of=${strategyPayload?.as_of_date ?? "待确认"}`,
    },
    {
      key: "signal-confluence",
      label: "信号共振",
      status: "deferred",
      tone: "neutral",
      detail: "deferred，抽屉按需读取",
    },
    {
      key: "candidate-history",
      label: "候选历史",
      status: "deferred",
      tone: "neutral",
      detail: "deferred，保留接口入口",
    },
    {
      key: "risk-exit",
      label: "风险退出",
      status: riskExitUnsupported || primaryGapLedgerLabel.includes("持仓") ? "unsupported" : "deferred",
      tone: riskExitUnsupported || primaryGapLedgerLabel.includes("持仓") ? "negative" : "neutral",
      detail:
        riskExitBlockerLabel ??
        (primaryGapLedgerLabel.includes("持仓") ? "position_risk missing，退出结论阻断" : "退出诊断按需读取"),
    },
    {
      key: "strategy-optimization",
      label: "策略优化",
      status: "deferred",
      tone: "neutral",
      detail: "诊断页保留，首屏不抢加载",
    },
    {
      key: "data-catalog",
      label: "数据目录",
      status: themeTaxonomyGapSummary.state === "ready" ? "ready" : "watch",
      tone: themeTaxonomyGapSummary.state === "ready" ? "positive" : "warning",
      detail: themeTaxonomyGapSummary.detail,
    },
  ];
  const gateStateVariantRows = [
    {
      key: "blocked",
      title: "blocked",
      tone: "warning",
      detail: "有候选但 data_gaps 未闭合，主操作禁用，只允许只读排查。",
    },
    {
      key: "limited_review",
      title: "limited_review",
      tone: "neutral",
      detail: "存在 warning 时允许阅读证据，但复核动作需二次确认。",
    },
    {
      key: "no_data",
      title: "no_data",
      tone: "negative",
      detail: "候选队列为空时，不把 0 包装成正常，直接显示 no_data。",
    },
    {
      key: "stale-fallback",
      title: "stale/fallback",
      tone: "warning",
      detail: "回退日期或缓存口径不一致时，顶部和证据栏同步提示。",
    },
  ];
  const stockWorkbenchMetaItems = [
    { label: "日期", value: backendSupplyOverview?.asOfLabel ?? analyticsAsOf ?? "待返回" },
    {
      label: "来源",
      value: sourceVersionSummary,
    },
    {
      label: "口径",
      value: stockSupplyBasisLabel(strategyQuery.data?.result_meta?.basis ?? workbenchPayload?.basis ?? "analytical"),
    },
  ];
  const stockWorkbenchToolbarActions = (
    <StockAnalysisWorkbenchActions
      pickerDisplay={pickerDisplay}
      queueSearchText={queueSearchText}
      dataStatusLabel={queueDataStatusLabel}
      dataStatusTone={queueDataStatusTone}
      gateStatusLabel={queueGateStatusLabel}
      gateStatusTone={boundaryRailIssueCount > 0 ? "warning" : "positive"}
      loopStatusLabel={queueLoopStatusLabel}
      loopStatusTone={workbenchReviewBlocked ? "negative" : observationClosureTone}
      formalUseAllowed={formalUseAllowed}
      routeLabel={workbenchRouteLabel}
      agentDrawerOpen={agentDrawerOpen}
      generatedAt={strategyQuery.data?.result_meta?.generated_at}
      onAsOfOverrideChange={setAsOfOverride}
      onQueueSearchTextChange={setQueueSearchText}
      onOpenAgentDrawer={() => setAgentDrawerOpen(true)}
      onRefresh={refreshStockSelection}
      isRefreshing={isRefreshingChoiceStock}
      refreshStatusMessage={stockRefreshStatusMessage}
      refreshStatusTone={stockRefreshStatusTone}
    />
  );

  return (
    <MarketWorkbenchFrame
      pageKey="stock-analysis"
      title="股票分析门禁"
      question="A 股观察工作台 / 后端口径复核"
      status={stockWorkbenchStatus}
      metaItems={stockWorkbenchMetaItems}
      actions={stockWorkbenchToolbarActions}
      auditContent={
        <div className="stock-analysis-page__supply-meta-grid">
          <span>门控 {backendSupplyOverview?.gateLabel ?? decisionSummary?.gateLabel ?? "待确认"}</span>
          <span>边界 {backendSupplyOverview?.dataGapLabel ?? decisionSummary?.boundaryLabel ?? "待确认"}</span>
          <span>
            复核 {queueVisibleCount}/{queueTotalCount}
          </span>
          <span>证据提示 {boundaryRailIssueCount}</span>
        </div>
      }
    >
      <section
        data-testid="stock-analysis-page"
        className={`${SA_SHELL_PAGE} theme-dh-api stock-analysis-page stock-analysis-page--market-shell dark text-foreground`}
        data-layout-rev="2026-05-31e"
        data-data-viz-rev="2026-05-31e"
        style={stockAnalysisPageCssVars}
      >
        <div className="stock-analysis-page__toolbar-anchor" data-testid="stock-analysis-toolbar">
          <div
            className="stock-analysis-page__visually-hidden stock-analysis-page__toolbar-info"
            aria-label="复核控制状态"
          >
            <span>
              观察日 {backendSupplyOverview?.asOfLabel ?? analyticsAsOf ?? "日期待补"}
            </span>
          </div>
        </div>

        {strategyQuery.isLoading ? (
          <StockAnalysisLoadingWorkbench />
        ) : null}

        {strategyQuery.isError ? (
          <StockAnalysisErrorWorkbench
            message={errorMessage(strategyQuery.error)}
            onRetry={() => {
              void strategyQuery.refetch();
            }}
            isRetrying={strategyQuery.isFetching}
          />
        ) : null}

        {mainModuleUnavailable ? (
          <StockAnalysisErrorWorkbench
            message={`主策略模块状态为${statusLabel(mainModuleStatus)}。接口已返回，但没有可展示的策略主包；请重新读取或核对 workbench 主模块契约。`}
            onRetry={() => {
              void strategyQuery.refetch();
            }}
            isRetrying={strategyQuery.isFetching}
          />
        ) : null}

        {marketState ? (
          <>
            {decisionSummary && dailyJudgmentStrip ? (
              <div
                className="stock-analysis-page__first-screen"
                data-testid="stock-analysis-first-screen-workbench"
              >
                <div
                  className="stock-analysis-page__first-screen-main"
                  data-testid="stock-analysis-first-screen-main"
                >
                {heroModel ? (
                  <StockAnalysisDecisionFirstScreen
                    asOfLabel={decisionSummary?.asOfLabel ?? "待确认"}
                    requestedAsOfLabel={backendSupplyOverview?.requestedAsOfLabel}
                    staleBannerLabel={showStaleBanner ? staleBannerLabel : null}
                    heroModel={heroModel}
                    marketState={marketState}
                    macroCycleModel={macroCycleModel}
                    sectorCard={sectorCard}
                    factorModel={factorScreenCard}
                    factorItems={(factorScreenPayload?.items ?? []).slice(0, 15)}
                    onOpenFactorDetail={(row) => {
                      const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stock_code);
                      setDetailSelection(buildFactorScreenDetailSelection({ row, ranks }));
                    }}
                    queueTotalCount={queueTotalCount}
                    queueVisibleCount={queueVisibleCount}
                    canReviewCandidates={workbenchCanReviewCandidates}
                    emptyState={reviewQueueEmptyState}
                    primaryBlockerLabel={localizedWorkbenchPrimaryBlocker}
                    topCandidates={queueVisibleCandidates.slice(0, 5)}
                    onOpenCandidate={(card) => {
                      const ranks = lookupStockStrategyRanks(strategyPayload ?? null, card.stockCode);
                      setDetailSelection(
                        buildReviewQueueDetailSelection({
                          card,
                          ranks,
                          reviewQueueUsesHybridFusion,
                        }),
                      );
                    }}
                    onJumpToQueue={() => scrollToStockSection("stock-analysis-review-queue")}
                    gapOverview={gapOverview}
                  />
                ) : null}

                <StockAnalysisEvidenceDisclosure
                  contract={workbenchContractSummary}
                  onOpenTopReviewStock={
                    workbenchTopReviewCandidate
                      ? () => {
                          const ranks = lookupStockStrategyRanks(
                            strategyPayload ?? null,
                            workbenchTopReviewCandidate.stockCode,
                          );
                          setDetailSelection(
                            buildReviewQueueDetailSelection({
                              card: workbenchTopReviewCandidate,
                              ranks,
                              reviewQueueUsesHybridFusion,
                            }),
                          );
                        }
                      : undefined
                  }
                  sourceCells={apiLedgerSourceCells.map((item) => ({
                    key: item.key,
                    label:
                      item.key === "tables"
                        ? "来源覆盖"
                        : item.key === "evidence"
                          ? "证据覆盖"
                          : item.key === "rule"
                            ? "规则状态"
                            : item.key === "trace"
                              ? "追踪状态"
                              : item.label,
                    value:
                      (item.key === "rule" || item.key === "trace") && item.value !== "待返回"
                        ? item.key === "rule"
                          ? "已签核"
                          : "已追踪"
                        : item.value,
                    detail:
                      (item.key === "rule" || item.key === "trace") && item.value !== "待返回"
                        ? "完整来源见诊断"
                        : item.detail,
                  }))}
                  endpointLedgerItems={endpointLedgerItems}
                  gateStateVariantRows={gateStateVariantRows}
                  readinessItems={evidenceReadinessItems}
                  gapReleaseCards={evidenceGapReleaseCards}
                  digestContent={
                    <StockAnalysisWorkbenchDigest
                      digest={workbenchDigest}
                      onFactSelect={handleWorkbenchFactSelect}
                      activeFactId={activeWorkbenchFactId}
                      factControlsId={STOCK_ANALYSIS_ENDPOINT_EVIDENCE_RAIL_ID}
                    />
                  }
                  closureContent={
                    <StockAnalysisObservationClosurePanel closureSummary={observationClosureSummary} />
                  }
                  railContent={
                    <StockAnalysisEvidenceLedgerRail
                      asOfLabel={decisionSummary?.asOfLabel ?? analyticsAsOf ?? "—"}
                      statusLabel={workbenchAnswerLabel}
                      gateStatusLabel={queueGateStatusLabel}
                      evidenceCount={typeof resultMeta?.evidence_rows === "number" ? resultMeta.evidence_rows : queueLeadEvidenceCount}
                      boundaryCount={dataGapCount || queueLeadBoundaryCount}
                      gapCountLabel={dataGapDisplay}
                      availableOutputsLabel="主策略已返回，扩展诊断按需加载"
                      primaryGapLabel={primaryGapLedgerLabel}
                      leadCandidateName={queueLeadCandidate?.stockName}
                      boundaryIssueCount={boundaryRailIssueCount}
                      sourceVersionSummary={sourceVersionSummary}
                      basisLabel={strategyBasisLabel}
                      qualityLabel={backendSupplyOverview?.qualityLabel ?? "正常"}
                      updatedAtLabel={backendSupplyOverview?.asOfLabel ?? decisionSummary?.asOfLabel ?? analyticsAsOf ?? "—"}
                      endpointItems={endpointEvidenceItems}
                      focusedEndpointKey={focusedEndpointKey}
                      onEndpointSelect={handleEndpointSelect}
                      diagnosticsOpen={boundaryDiagnosticsOpen}
                      onOpenDiagnostics={() => setBoundaryDiagnosticsOpen(true)}
                      onCloseDiagnostics={() => setBoundaryDiagnosticsOpen(false)}
                      closedLoopSummary={closedLoopSummary}
                      railRiskTone={railRiskTone}
                      riskTriggeredCount={riskTriggeredCount}
                      riskWatchCount={riskWatchCount}
                      reviewQueueCount={queueVisibleCount}
                      nextActionLabel={queueNextActionLabel}
                      nextActionFullLabel={queueNextActionFullLabel}
                      riskRows={riskRows}
                      confluenceError={confluenceQuery.isError}
                      riskExitUnsupported={riskExitUnsupported}
                      onOpenRiskDetail={(row) => {
                        const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stockCode);
                        setDetailSelection(buildRiskExitDetailSelection({ row, ranks }));
                      }}
                      boundaryItems={boundaryRailItems}
                      boundarySummary={boundarySummary}
                      strategyPayload={strategyPayload}
                      routeLabel={workbenchRouteLabel}
                      resultKindLabel={workbenchResultKindLabel}
                      formalUseAllowed={formalUseAllowed}
                    />
                  }
                />

                <div
                  className="stock-analysis-page__review-summary-stack"
                  data-testid="stock-analysis-review-summary"
                >
                  <section
                    className={SA_FIRST_CARD}
                    id="stock-analysis-review-queue"
                    data-testid="stock-analysis-review-queue"
                  >
                <div className={SA_SECTION_HEAD}>
                  <div className="stock-analysis-page__min-w-0">
                    <p className={SA_SECTION_EYEBROW}>观察池队列</p>
                    <h2 className={SA_CARD_TITLE}>观察池队列</h2>
                    <p className={SA_SECTION_DESC}>
                      只读排序，待补证后才允许进入复核动作
                    </p>
                  </div>
                  <span className={SA_PILL}>
                    {reviewQueueLedgerCount} 条
                  </span>
                  <h2 className="sr-only">复核队列</h2>
                  <span className="sr-only">
                    {reviewQueueUsesHybridFusion ? "融合策略 / 复核队列" : "候选/ 复核队列"}
                  </span>
                </div>

                {queueTotalCount === 0 ? (
                  <div
                    className="stock-analysis-page__review-empty-panel"
                    role="status"
                    data-testid="stock-analysis-review-queue-empty"
                    title={reviewQueueEmptyState?.detail ?? "查看观察池与板块"}
                  >
                    <div className="stock-analysis-page__empty-status-grid">
                      <CompactStatusTile
                        icon={<StockOutlined />}
                        label="队列"
                        value="0"
                        tone="warning"
                        className="stock-analysis-page__compact-status-tile--surface"
                        title={reviewQueueEmptyState?.headline ?? "暂无主候选"}
                      />
                      <CompactStatusTile
                        icon={<DatabaseOutlined />}
                        label="多因子"
                        value={primaryFactorScreenCandidateCount}
                        className="stock-analysis-page__compact-status-tile--surface"
                      />
                      <CompactStatusTile
                        icon={<BarChartOutlined />}
                        label="板块"
                        value={sectorRowsFull.length}
                        className="stock-analysis-page__compact-status-tile--surface"
                      />
                    </div>
                  </div>
                ) : queueVisibleCount === 0 ? (
                  <div
                    className="stock-analysis-page__review-filter-empty"
                    data-testid="stock-analysis-review-queue-filter-empty"
                    role="status"
                  >
                    <CompactStatusTile
                      icon={<BarChartOutlined />}
                      label="筛选结果"
                      value="0 候选"
                      tone="warning"
                      title={queueFilterEmptyLabel}
                    />
                    <p>{queueFilterEmptyLabel}</p>
                    <AntButton
                      type="text"
                      onClick={() => {
                        setQueueSearchText("");
                        toggleSectorFilter(null);
                      }}
                    >
                      清除筛选
                    </AntButton>
                  </div>
                ) : (
                  <>
                  <StockAnalysisCandidateComparison
                    candidates={queueVisibleCandidates}
                    usesHybridFusion={reviewQueueUsesHybridFusion}
                    asOfLabel={decisionSummary?.asOfLabel ?? analyticsAsOf}
                    canReviewCandidates={workbenchCanReviewCandidates}
                    positionSizeHint={buildCandidatePositionSizeHintNotice(strategyPayload?.stock_candidates?.position_size_hint)}
                    onReviewCandidate={(card) => {
                      const ranks = lookupStockStrategyRanks(strategyPayload ?? null, card.stockCode);
                      setDetailSelection(
                        buildReviewQueueDetailSelection({
                          card,
                          ranks,
                          reviewQueueUsesHybridFusion,
                        }),
                      );
                    }}
                  />
                  <section
                    className="stock-analysis-page__queue-ledger-details"
                    data-testid="stock-analysis-review-queue-details"
                    data-open={queueLedgerOpen ? "true" : "false"}
                  >
                    <button
                      type="button"
                      aria-expanded={queueLedgerOpen}
                      aria-controls="stock-analysis-review-queue-table-panel"
                      onClick={() => setQueueLedgerOpen((current) => !current)}
                    >
                      <span>候选队列预览</span>
                      <small>已返回 {queueTotalCount} 条 · 展开看排序明细</small>
                    </button>
                    {queueLedgerOpen ? (
                      <div id="stock-analysis-review-queue-table-panel">
                        <StockAnalysisCandidateLedgerTable
                          candidates={queueVisibleCandidates}
                          usesHybridFusion={reviewQueueUsesHybridFusion}
                          selectedSectorCode={sectorFilterSectorCode}
                          visibleCount={10}
                          onReviewCandidate={(card) => {
                            const ranks = lookupStockStrategyRanks(strategyPayload ?? null, card.stockCode);
                            setDetailSelection(
                              buildReviewQueueDetailSelection({
                                card,
                                ranks,
                                reviewQueueUsesHybridFusion,
                              }),
                            );
                          }}
                        />
                      </div>
                    ) : null}
                  </section>
                  <div
                    className="stock-analysis-page__review-table-footer"
                    data-testid="stock-analysis-review-queue-table-footer"
                    aria-label="队列分页摘要"
                  >
                    <span className="stock-analysis-page__review-table-pagination">
                      显示 {queueTablePageStart}-{queueTablePageEnd} / {queueVisibleCount}
                    </span>
                  </div>
                  </>
                )}

                {queueTotalCount > 0 ? (
                  <div
                    className="stock-analysis-page__review-workbench-strip"
                    data-testid="stock-analysis-review-workbench-strip"
                    aria-label="复核工作台摘要"
                  >
                    <div>
                      <DatabaseOutlined aria-hidden="true" />
                      <span>队列</span>
                      <strong className="stock-analysis-page__tabular">
                        {queueVisibleCount}/{queueTotalCount}
                      </strong>
                    </div>
                    <div>
                      <StockOutlined aria-hidden="true" />
                      <span>首位</span>
                      <strong>{queueLeadCandidate?.stockName ?? "待补"}</strong>
                    </div>
                    <div>
                      <BarChartOutlined aria-hidden="true" />
                      <span>距观察</span>
                      <strong className="stock-analysis-page__tabular">
                        {queueLeadCandidate?.distanceToBreakoutPct ?? "-"}
                      </strong>
                    </div>
                    <div>
                      <SafetyCertificateOutlined aria-hidden="true" />
                      <span>证据</span>
                      <strong className="stock-analysis-page__tabular">
                        {queueLeadEvidenceCount}
                      </strong>
                    </div>
                  </div>
                ) : null}

                {queueTotalCount > 0 ? (
                  <div
                    className="stock-analysis-page__sector-filter-bar"
                    data-testid="stock-sector-filter-chips"
                  >
                    <button
                      type="button"
                      className={filterChipClass(sectorFilterSectorCode === null)}
                      onClick={() => toggleSectorFilter(null)}
                      aria-pressed={sectorFilterSectorCode === null}
                    >
                      全部行业
                    </button>
                    {sectorOptions.map(([code, label]) => (
                      <button
                        key={code}
                        type="button"
                        data-testid={`sector-filter-chip-${code}`}
                        className={filterChipClass(sectorFilterSectorCode === code)}
                        onClick={() => toggleSectorFilter(code)}
                        aria-pressed={sectorFilterSectorCode === code}
                      >
                        {label}
                      </button>
                    ))}
                    <div
                      className="stock-analysis-page__sector-filter-status"
                      data-testid="stock-review-filter-status"
                    >
                      <span>范围</span>
                      <strong className="stock-analysis-page__gate-row-label">{selectedSectorLabel ?? "全部行业"}</strong>
                      <small>
                        显示 {queueVisibleCount} / {queueTotalCount} 个候选
                        {reviewQueueUsesHybridFusion ? " · 融合策略候选优先" : ""}
                      </small>
                    </div>
                  </div>
                ) : null}

                {sectorRowsFull.length > 0 ? (
                  <div
                    className="stock-analysis-page__sector-review-link"
                    aria-live="polite"
                    data-tone={queueSectorLinkTone}
                    data-testid="stock-analysis-sector-review-link"
                    title={`${queueSectorLinkSummary} ${queueSectorLinkFocus}`}
                  >
                    <span aria-hidden="true">
                      <BarChartOutlined />
                    </span>
                    <strong>{queueSectorLinkSummary}</strong>
                    <small>{queueSectorLinkFocus}</small>
                  </div>
                ) : null}
              </section>
                </div>

                </div>

              </div>
            ) : null}

            <details
              className="stock-analysis-page__deep-research"
              data-testid="stock-analysis-deep-research"
              onToggle={(event) => {
                if (event.currentTarget.open) {
                  setDeepResearchRequested(true);
                }
              }}
            >
              <summary
                className="stock-analysis-page__deep-research-summary"
                data-testid="stock-analysis-deep-research-summary"
              >
                <span>深度研究</span>
                <strong>共振、K线、因子、题材与回测</strong>
                <small>默认收起 · 按需展开完整研究工作台</small>
              </summary>
              {shouldMountDeepResearch ? (
                <Suspense
                  fallback={
                    <div
                      className="stock-analysis-page__workspace stock-analysis-page__deep-research-loading"
                      role="status"
                      aria-label="正在加载深度研究"
                    >
                      <TextSkeleton className="w-full" />
                    </div>
                  }
                >
              <AnalysisGrid columns={2} className="stock-analysis-page__workspace">
              <div className="stock-analysis-page__deep-zone" data-testid="stock-analysis-deep-zone">
                <LazyStockAnalysisDeepZoneHeader
                  gateSummary={deepAnalysisGateSummary!}
                  auditRows={deepZoneAuditRows}
                />
                <StockAnalysisStrategyLensSection
                  items={strategyLensItems}
                  onScrollToSection={scrollToStockSection}
                />
                <div
                  className="stock-analysis-page__stock-selection-stack stock-analysis-page__deep-review-workspace"
                  data-testid="stock-analysis-stock-selection"
                >
                  <LazyStockAnalysisConsensusFirstScreen
                    consensusSummary={consensusSummary}
                    consensusHitCount={consensusHitCount}
                    firstScreenItems={consensusFirstScreenItems}
                    emptyDetail={consensusReviewPanelSummary?.detail}
                    onOpenConsensusDetail={(row) => setDetailSelection(buildConsensusDetailSelection(row))}
                  />

                  <LazyStockAnalysisKlineRadarPanel
                    strategyPayload={strategyPayload}
                    onOpenRadarItem={openKlineRadarItem}
                  />

                  <LazyStockAnalysisObservationPreview
                    factorScreenPayload={factorScreenPayload}
                    factorPreviewItems={factorPreviewItems}
                    factorScreenCoverageNote={factorScreenCoverageNote}
                    meanReversionMarketActive={meanReversionMarketActive}
                    meanReversionPayload={meanReversionPayload}
                    meanReversionPreviewItems={meanReversionPreviewItems}
                    onOpenFactorDetail={(row) => {
                      const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stock_code);
                      setDetailSelection(buildFactorScreenDetailSelection({ row, ranks }));
                    }}
                    onOpenMeanReversionDetail={(row) => {
                      const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stock_code);
                      setDetailSelection(buildMeanReversionDetailSelection({ row, ranks }));
                    }}
                  />
                  <LazyStockAnalysisDeepSelectionOverview
                    themeBreakoutCount={themeBreakoutCards.length}
                    themeLeaderPreviewItems={themeLeaderPreviewItems}
                    themeBreakoutUnsupported={Boolean(themeBreakoutUnsupported)}
                    themeBreakoutBlockerLabel={themeBreakoutBlockerLabel}
                    themeBreakoutBlockerText={themeBreakoutBlockerText}
                    sectorHeavyweightPreview={heavyweight.preview}
                    sectorHeavyweightRows={heavyweight.rows}
                    heavyweightTrends={heavyweight.trends}
                    heavyweightSectionRef={heavyweight.sectionRef}
                    strategyPayload={strategyPayload}
                    setDetailSelection={setDetailSelection}
                  />

                  <section
                    className={SA_FIRST_CARD}
                    id="stock-analysis-first-screen-analytics"
                    data-testid="stock-analysis-first-screen-analytics"
                  >
                    <div className={SA_SECTION_HEAD}>
                      <div className="stock-analysis-page__min-w-0">
                        <p className={SA_SECTION_EYEBROW}>深度回测</p>
                        <h2 className={SA_CARD_TITLE}>回测诊断</h2>
                        <div className="stock-analysis-page__signal-pill-row" aria-label="回测诊断状态">
                          <span className="stock-analysis-page__signal-pill">
                            <ThunderboltOutlined aria-hidden="true" /> 共振 {consensusHitCount}
                          </span>
                          <span className="stock-analysis-page__signal-pill">
                            <LineChartOutlined aria-hidden="true" /> 诊断{" "}
                            {firstScreenAnalyticsRequested ? "已载入" : "待查"}
                          </span>
                        </div>
                      </div>
                      <span className={SA_PILL}>
                        共振 {consensusHitCount} · 去重 {consensusSummary.totalUnion}
                      </span>
                    </div>

                    <LazyStockAnalysisTabs
                      aria-label="首屏分析视图"
                      className="stock-analysis-page__analytics-tabs"
                      size="sm"
                      selectedKey={firstScreenAnalyticsTab}
                      onSelectionChange={(k) => handleFirstScreenAnalyticsTabChange(String(k))}
                    >
                      <LazyStockAnalysisTab key="consensus" title="历史共振">
                        {!consensusSummary.hasAnyStrategy ? (
                            <CompactStatusTile
                              icon={<ThunderboltOutlined />}
                              label="历史共振"
                              value="0"
                              testId="stock-analysis-consensus-first-screen-empty"
                            />
                          ) : consensusSummary.items.length === 0 ? (
                            <CompactStatusTile
                              icon={<ThunderboltOutlined />}
                              label="历史共振"
                              value="0"
                              testId="stock-analysis-consensus-first-screen-empty"
                            />
                          ) : (
                            <ul className="stock-analysis-page__list stock-analysis-page__list--compact">
                              {consensusSummary.items.map((row) => {
                                const isTriple = row.consensusCount >= 3;
                                const openDetail = () => {
                                  setDetailSelection(buildConsensusDetailSelection(row));
                                };
                                return (
                                  <li
                                    key={row.stockCode}
                                    className={`stock-analysis-page__consensus-row stock-analysis-page__row--clickable${
                                      isTriple ? " stock-analysis-page__consensus-row--triple" : ""
                                    }`}
                                    data-testid={`first-screen-consensus-row-${row.stockCode}`}
                                    onClick={openDetail}
                                    role="button"
                                    tabIndex={0}
                                    onKeyDown={(e) => {
                                      if (e.key === "Enter" || e.key === " ") {
                                        e.preventDefault();
                                        openDetail();
                                      }
                                    }}
                                  >
                                    <div className="stock-analysis-page__consensus-head">
                                      <span
                                        className={`stock-analysis-page__consensus-badge${
                                          isTriple ? " stock-analysis-page__consensus-badge--triple" : ""
                                        }`}
                                      >
                                        {isTriple ? "三策略共振" : "核心共振"}
                                      </span>
                                      <strong>
                                        <span className="stock-analysis-page__tabular">{row.stockCode}</span>{" "}
                                        {row.stockName}
                                      </strong>
                                      <small className="stock-analysis-page__tabular">
                                        {row.sectorName || "-"}
                                      </small>
                                      <span className="stock-analysis-page__consensus-strategies">
                                        {row.strategies.map((kind) => (
                                          <span key={kind} className="stock-analysis-page__consensus-badge">
                                            {consensusStrategyLabel(kind)}
                                          </span>
                                        ))}
                                      </span>
                                    </div>
                                  </li>
                                );
                              })}
                            </ul>
                          )}
                      </LazyStockAnalysisTab>
                      <LazyStockAnalysisTab key="priority" title="策略优先级">
                        {!firstScreenPriorityRequested ? (
                            <CompactStatusTile
                              icon={<LineChartOutlined />}
                              label="策略优先级"
                              value="待查"
                              testId="stock-analysis-priority-deferred"
                            />
                          ) : strategyScoreQuery.isLoading ? (
                            <TableSkeleton />
                          ) : strategyScoreQuery.isError ? (
                            <p className="stock-analysis-page__notice">
                              当前市场策略优先级暂不可用：{strategyPanelErrorMessage(strategyScoreQuery.error)}
                            </p>
                          ) : strategyPriorityRows.length > 0 ? (
                            <div className="stock-analysis-page__table-wrap">
                              <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                                <thead>
                                  <tr>
                                    <th scope="col">策略</th>
                                    <th scope="col">状态</th>
                                    <th className="stock-analysis-page__table-number" scope="col">
                                      评分
                                    </th>
                                    {strategyBacktestHorizons.map((horizon) => (
                                      <th scope="col" key={horizon}>
                                        {strategyBacktestHorizonLabels[horizon]}
                                      </th>
                                    ))}
                                    <th scope="col">原因</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {strategyPriorityRows.map((row) => (
                                    <tr
                                      key={`${row.market_state}:${row.signal_kind}`}
                                      data-testid={`first-screen-priority-row-${row.market_state}-${row.signal_kind}`}
                                    >
                                      <td>{strategyDisplayLabel(row.strategy_label, row.signal_kind)}</td>
                                      <td>{strategyPriorityStatusLabel(row.priority_label)}</td>
                                      <td className="stock-analysis-page__table-number">
                                        {formatPriorityScore(row.priority_score)}
                                      </td>
                                      {strategyBacktestHorizons.map((horizon) => (
                                        <td className="stock-analysis-page__table-number" key={horizon}>
                                          {strategyPriorityHorizonStatsText(
                                            row,
                                            horizon,
                                            strategyScorePayload?.backtest_window_summary,
                                          )}
                                        </td>
                                      ))}
                                      <td>{strategyPriorityReasonLabel(row)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <CompactStatusTile
                              icon={<LineChartOutlined />}
                              label="策略优先级"
                              value="样本不足"
                              testId="stock-analysis-priority-empty"
                            />
                          )}
                      </LazyStockAnalysisTab>
                      <LazyStockAnalysisTab key="optimization" title="优化诊断">
                        {!firstScreenOptimizationRequested ? (
                            <CompactStatusTile
                              icon={<SafetyCertificateOutlined />}
                              label="优化诊断"
                              value="待查"
                              testId="stock-analysis-optimization-deferred"
                            />
                          ) : strategyOptimizationQuery.isLoading ? (
                            <TableSkeleton />
                          ) : strategyOptimizationQuery.isError ? (
                            <p className="stock-analysis-page__notice">
                              优化诊断暂不可用：{strategyPanelErrorMessage(strategyOptimizationQuery.error)}
                            </p>
                          ) : !strategyOptimizationPayload ? (
                            <CompactStatusTile
                              icon={<SafetyCertificateOutlined />}
                              label="优化诊断"
                              value="接口未提供"
                              testId="stock-analysis-optimization-empty"
                            />
                          ) : strategyOptimizationRows.length > 0 ? (
                            <div className="stock-analysis-page__table-wrap">
                              <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                                <thead>
                                  <tr>
                                    <th scope="col">策略</th>
                                    <th scope="col">复核状态</th>
                                    <th scope="col">{strategyOptimizationPrimaryHorizonLabel} 收益</th>
                                    <th scope="col">按日等权</th>
                                    <th scope="col">原因</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {strategyOptimizationRows.map((row) => (
                                    <tr
                                      key={row.summary_key}
                                      data-testid={`first-screen-optimization-row-${row.summary_key}`}
                                    >
                                      <td>{strategyDisplayLabel(row.strategy_label, row.signal_kind)}</td>
                                      <td>{strategyPriorityStatusLabel(row.recommendation.priority_label)}</td>
                                      <td className="stock-analysis-page__table-number">
                                        {strategyOptimizationPrimaryStatsText(row, strategyOptimizationPayload)}
                                      </td>
                                      <td className="stock-analysis-page__table-number">
                                        {strategyOptimizationDateWeightedText(row, strategyOptimizationPayload)}
                                      </td>
                                      <td>{strategyOptimizationReasonLabel(row)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <CompactStatusTile
                              icon={<SafetyCertificateOutlined />}
                              label="优化诊断"
                              value="样本不足"
                              testId="stock-analysis-optimization-empty"
                            />
                          )}
                      </LazyStockAnalysisTab>
                    </LazyStockAnalysisTabs>
                  </section>

                    <section
                className={SA_FIRST_CARD}
                data-testid="stock-analysis-sector-strength-panel"
              >
                <div className={SA_SECTION_HEAD}>
                  <div className="stock-analysis-page__min-w-0">
                    <p className={SA_SECTION_EYEBROW}>行业相对强弱</p>
                    <h2 className={SA_CARD_TITLE}>
                      板块强弱
                    </h2>
                    <p className={SA_SECTION_DESC}>
                      {sectorRowsFull.length} 个板块 · {sectorRowsSourceLabel}
                    </p>
                  </div>
                  <span className={SA_PILL}>
                    {sectorRowsFull.length > 0
                      ? `${sectorRowsFull.length} 个板块 · ${sectorRowsSourceLabel}`
                      : "板块待补"}
                  </span>
                </div>

                {sectorRowsFull.length > 0 ? (
                  <>
                    <div
                      className="stock-analysis-page__sector-workbench-strip"
                      data-testid="stock-analysis-sector-workbench-strip"
                      aria-label="板块强弱摘要"
                    >
                      <div>
                        <DatabaseOutlined aria-hidden="true" />
                        <span>板块</span>
                        <strong className="stock-analysis-page__tabular">{sectorRowsFull.length}</strong>
                      </div>
                      <div>
                        <LineChartOutlined aria-hidden="true" />
                        <span>首位</span>
                        <strong>{sectorLeaderRow?.sectorName ?? "待补"}</strong>
                      </div>
                      <div>
                        <FireOutlined aria-hidden="true" />
                        <span>尾部</span>
                        <strong>{sectorTailRow?.sectorName ?? "待补"}</strong>
                      </div>
                      <div>
                        <StockOutlined aria-hidden="true" />
                        <span>成分</span>
                        <strong className="stock-analysis-page__tabular">{sectorCoverageCount}</strong>
                      </div>
                    </div>
                    <LazyStockAnalysisTabs
                      aria-label="板块排行视图"
                      className="stock-analysis-page__sector-tabs"
                      size="sm"
                      selectedKey={sectorView}
                      onSelectionChange={(k) => handleSectorViewChange(String(k))}
                    >
                      {sectorViewTabs.map((tab) => (
                        <LazyStockAnalysisTab key={tab.key} title={tab.label} />
                      ))}
                    </LazyStockAnalysisTabs>

                    <div className="stock-analysis-page__sector-rank-grid" data-testid="stock-analysis-sector-bars">
                      <div className="stock-analysis-page__sector-rank-col stock-analysis-page__sector-rank-col--top">
                        <h3>强势前 {SECTOR_STRENGTH_DEFAULT_TOP_COUNT}</h3>
                        <div className="stock-analysis-page__sector-rank-list">
                          {visibleSectorTopBars.map((row) => (
                            <button
                              type="button"
                              key={`top-${row.sectorCode}-${row.rank}`}
                              className={`stock-analysis-page__sector-rank-row${
                                sectorFilterSectorCode === row.sectorCode
                                  ? " stock-analysis-page__sector-rank-row--selected"
                                  : ""
                              }`}
                              aria-pressed={sectorFilterSectorCode === row.sectorCode}
                              data-testid={`sector-bar-${row.sectorCode}`}
                              onClick={() => toggleSectorFilter(row.sectorCode)}
                            >
                              <div className="stock-analysis-page__sector-rank-row-head stock-analysis-page__tabular">
                                <span className="stock-analysis-page__min-w-0 stock-analysis-page__sector-rank-row-label">
                                  {row.rank}. {row.sectorName}{" "}
                                  <small>{row.sectorCode}</small>
                                </span>
                                <span>{row.score}</span>
                              </div>
                              <div className="stock-analysis-page__sector-rank-bar">
                                <progress
                                  className="stock-analysis-page__sector-rank-progress stock-analysis-page__sector-rank-progress--top"
                                  max={100}
                                  value={(sectorView === "score" ? row.scoreNormalized : row.metricBarNormalized) * 100}
                                  aria-hidden="true"
                                />
                                <div
                                  className="stock-analysis-page__sector-rank-bar-label stock-analysis-page__tabular"
                                >
                                  <span>{row.pctChange}</span>
                                  <small className="stock-analysis-page__sector-rank-row-meta">成分 {row.constituentCount}</small>
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>

                    <details
                      className="stock-analysis-page__sector-detail-more"
                      data-testid="stock-analysis-sector-detail-more"
                      onToggle={(event) => setSectorDetailOpen(event.currentTarget.open)}
                    >
                      <summary className="stock-analysis-page__sector-detail-more-summary">
                        <span>背景明细</span>
                        <small>
                          图表 / 强势余 {backgroundSectorTopBars.length} / 弱势后 5 / 行业明细
                        </small>
                      </summary>
                      <div className="stock-analysis-page__sector-detail-more-body">
                        <div
                          className="stock-analysis-page__sector-chart-wrap"
                          data-testid="stock-analysis-sector-strength-chart"
                          aria-label="板块强弱横向图"
                        >
                          {sectorDetailOpen ? (
                            sectorStrengthChartRows.length > 0 ? (
                              <Suspense fallback={<TextSkeleton className="w-full" />}>
                                <LazyReactECharts
                                  option={sectorStrengthChartOption}
                                  className="stock-analysis-page__echart stock-analysis-page__echart--sector-strength"
                                  opts={{ renderer: "canvas" }}
                                  notMerge
                                  lazyUpdate
                                />
                              </Suspense>
                            ) : (
                              <span className="stock-analysis-page__sector-empty-chart">
                                -
                              </span>
                            )
                          ) : null}
                        </div>

                        <div
                          className="stock-analysis-page__sector-rank-grid stock-analysis-page__sector-rank-grid--secondary"
                          data-testid="stock-analysis-sector-bars-secondary"
                        >
                      {backgroundSectorTopBars.length > 0 ? (
                        <div className="stock-analysis-page__sector-rank-col stock-analysis-page__sector-rank-col--top">
                          <h3>强势余下</h3>
                          <div className="stock-analysis-page__sector-rank-list">
                            {backgroundSectorTopBars.map((row) => (
                              <button
                                type="button"
                                key={`top-extra-${row.sectorCode}-${row.rank}`}
                                className={`stock-analysis-page__sector-rank-row${
                                  sectorFilterSectorCode === row.sectorCode
                                    ? " stock-analysis-page__sector-rank-row--selected"
                                    : ""
                                }`}
                                aria-pressed={sectorFilterSectorCode === row.sectorCode}
                                data-testid={`sector-bar-${row.sectorCode}`}
                                onClick={() => toggleSectorFilter(row.sectorCode)}
                              >
                                <div className="stock-analysis-page__sector-rank-row-head stock-analysis-page__tabular">
                                  <span className="stock-analysis-page__min-w-0 stock-analysis-page__sector-rank-row-label">
                                    {row.rank}. {row.sectorName}{" "}
                                    <small>{row.sectorCode}</small>
                                  </span>
                                  <span>{row.score}</span>
                                </div>
                                <div className="stock-analysis-page__sector-rank-bar">
                                  <progress
                                    className="stock-analysis-page__sector-rank-progress stock-analysis-page__sector-rank-progress--top"
                                    max={100}
                                    value={(sectorView === "score" ? row.scoreNormalized : row.metricBarNormalized) * 100}
                                    aria-hidden="true"
                                  />
                                  <div
                                    className="stock-analysis-page__sector-rank-bar-label stock-analysis-page__tabular"
                                  >
                                    <span>{row.pctChange}</span>
                                    <small className="stock-analysis-page__sector-rank-row-meta">成分 {row.constituentCount}</small>
                                  </div>
                                </div>
                              </button>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      <div className="stock-analysis-page__sector-rank-col stock-analysis-page__sector-rank-col--bottom">
                        <h3>弱势后 5</h3>
                        <div className="stock-analysis-page__sector-rank-list">
                          {bottomBars.map((row) => (
                            <button
                              type="button"
                              key={`bottom-${row.sectorCode}-${row.rank}`}
                              className={`stock-analysis-page__sector-rank-row${
                                sectorFilterSectorCode === row.sectorCode
                                  ? " stock-analysis-page__sector-rank-row--selected"
                                  : ""
                              }`}
                              aria-pressed={sectorFilterSectorCode === row.sectorCode}
                              data-testid={`sector-bar-bottom-${row.sectorCode}`}
                              onClick={() => toggleSectorFilter(row.sectorCode)}
                            >
                              <div className="stock-analysis-page__sector-rank-row-head stock-analysis-page__tabular">
                                <span className="stock-analysis-page__min-w-0 stock-analysis-page__sector-rank-row-label">
                                  {row.rank}. {row.sectorName}{" "}
                                  <small>{row.sectorCode}</small>
                                </span>
                                <span>{row.pctChange}</span>
                              </div>
                              <div className="stock-analysis-page__sector-rank-bar">
                                <progress
                                  className="stock-analysis-page__sector-rank-progress stock-analysis-page__sector-rank-progress--bottom"
                                  max={100}
                                  value={(sectorView === "score" ? row.scoreNormalized : row.metricBarNormalized) * 100}
                                  aria-hidden="true"
                                />
                                <div
                                  className="stock-analysis-page__sector-rank-bar-label stock-analysis-page__tabular"
                                >
                                  <span>{row.pctChange}</span>
                                  <small className="stock-analysis-page__sector-rank-row-meta">成分 {row.constituentCount}</small>
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                    <div
                      className="stock-analysis-page__signal-pill-row"
                      aria-label="板块筛选状态"
                    >
                      <span className="stock-analysis-page__signal-pill">
                        <ClockCircleOutlined aria-hidden="true" /> 截面
                      </span>
                      <span className="stock-analysis-page__signal-pill">
                        <BarChartOutlined aria-hidden="true" /> 筛选
                      </span>
                    </div>

                    <Accordion
                      className="stock-analysis-page__sector-collapse"
                    >
                      <AccordionItem
                        key="sector-detail-table"
                        aria-label="行业明细"
                        title="行业明细"
                      >
                        <div className="stock-analysis-page__table-wrap">
                              <table className="stock-analysis-page__table">
                                <thead>
                                  <tr>
                                    <th
                                      className="stock-analysis-page__sortable-head"
                                      scope="col"
                                      onClick={() => toggleSort("rank")}
                                      onKeyDown={(e) => e.key === "Enter" && toggleSort("rank")}
                                      role="columnheader"
                                    >
                                      排名
                                      {renderSortSuffix("rank")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head"
                                      scope="col"
                                      onClick={() => toggleSort("sectorName")}
                                    >
                                      行业
                                      {renderSortSuffix("sectorName")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head stock-analysis-page__table-number"
                                      scope="col"
                                      onClick={() => toggleSort("score")}
                                    >
                                      分数
                                      {renderSortSuffix("score")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head stock-analysis-page__table-number"
                                      scope="col"
                                      onClick={() => toggleSort("pctChange")}
                                    >
                                      涨跌幅
                                      {renderSortSuffix("pctChange")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head stock-analysis-page__table-number"
                                      scope="col"
                                      onClick={() => toggleSort("turnover")}
                                    >
                                      换手
                                      {renderSortSuffix("turnover")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head stock-analysis-page__table-number"
                                      scope="col"
                                      onClick={() => toggleSort("amplitude")}
                                    >
                                      振幅
                                      {renderSortSuffix("amplitude")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head stock-analysis-page__table-number"
                                      scope="col"
                                      onClick={() => toggleSort("constituentCount")}
                                    >
                                      成分数
                                      {renderSortSuffix("constituentCount")}
                                    </th>
                                    <th className="stock-analysis-page__table-number" scope="col">
                                      涨跌条
                                    </th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {sortedDetailRows.map((row: StockSectorRow) => (
                                    <tr key={row.sectorCode}>
                                      <td className="stock-analysis-page__table-number">#{row.rank}</td>
                                      <td>
                                        {row.sectorName}
                                        <small>{row.sectorCode}</small>
                                      </td>
                                      <td className="stock-analysis-page__table-number">{row.score}</td>
                                      <td className="stock-analysis-page__table-number">{row.pctChange}</td>
                                      <td className="stock-analysis-page__table-number">{row.turnover}</td>
                                      <td className="stock-analysis-page__table-number">{row.amplitude}</td>
                                      <td className="stock-analysis-page__table-number">{row.constituentCount}</td>
                                      <td className="stock-analysis-page__pct-bar-cell">
                                        <progress
                                          className="stock-analysis-page__pct-bar-progress"
                                          max={100}
                                          value={row.pctChangeBar}
                                          aria-label={`${row.sectorName} 涨跌幅条`}
                                        />
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </AccordionItem>
                    </Accordion>

                    <Accordion
                      className="stock-analysis-page__sector-collapse"
                      selectedKeys={new Set(sectorSeriesCollapseKeys)}
                      onSelectionChange={(keys) => {
                        const newKeys = Array.from(keys).map(String);
                        handleSectorSeriesCollapseChange(newKeys);
                      }}
                    >
                      <AccordionItem
                        key="sector-rank-series-multi"
                        aria-label="多日强弱"
                        title="多日强弱"
                      >
                        <div
                              className="stock-analysis-page__sector-series-wrap"
                              data-testid="stock-analysis-sector-series-panel"
                            >
                              <p className="stock-analysis-page__sector-series-note">
                                按交易日展示 Top 板块综合得分走势；窗口累计涨跌幅见下表。
                              </p>
                              {sectorSeriesUnsupportedNotes.length > 0 ? (
                                <ul
                                  className="stock-analysis-page__sector-series-pending"
                                  data-testid="stock-analysis-sector-series-pending"
                                  aria-label="多日板块待补项"
                                >
                                  {sectorSeriesUnsupportedNotes.map((note) => (
                                    <li key={note}>{note}</li>
                                  ))}
                                </ul>
                              ) : null}
                              <LazyStockAnalysisTabs
                                aria-label="板块序列周期"
                                size="sm"
                                selectedKey={String(sectorSeriesWindow)}
                                onSelectionChange={(k) => handleSectorSeriesWindowChange(String(k))}
                                className="stock-analysis-page__sector-series-tabs"
                              >
                                <LazyStockAnalysisTab key="5" title="5 交易日" />
                                <LazyStockAnalysisTab key="20" title="20 交易日" />
                              </LazyStockAnalysisTabs>
                              {sectorRankSeriesQuery.isFetching ? (
                                <TextSkeleton className="w-full" />
                              ) : null}
                              {sectorRankSeriesQuery.isError ? (
                                <div
                                  className="p-4 mb-4 text-sm text-warning-800 rounded-lg bg-warning-50 flex items-start gap-3 border border-warning-200"
                                  role="alert"
                                >
                                  <div className="flex flex-col gap-1">
                                    <span className="font-semibold text-warning-900">多日板块序列加载失败</span>
                                    <span>{strategyPanelErrorMessage(sectorRankSeriesQuery.error)}</span>
                                  </div>
                                </div>
                              ) : null}
                              {!sectorRankSeriesQuery.isFetching &&
                              !sectorRankSeriesQuery.isError &&
                              sectorRankSeriesQuery.data?.result?.state === "missing" ? (
                                <CompactStatusTile
                                  icon={<BarChartOutlined />}
                                  label="多日窗口"
                                  value="无数据"
                                  testId="stock-analysis-sector-series-empty"
                                />
                              ) : null}
                              {!sectorRankSeriesQuery.isFetching &&
                              !sectorRankSeriesQuery.isError &&
                              sectorRankSeriesQuery.data?.result?.state === "ok" &&
                              sectorSeriesTrendLines.length > 0 ? (
                                <div
                                  className="stock-analysis-page__sector-series-chart-wrap"
                                  data-testid="stock-analysis-sector-series-chart"
                                  aria-label="多日板块得分走势"
                                >
                                  <Suspense fallback={<TextSkeleton className="w-full" />}>
                                    <LazyReactECharts
                                      option={sectorSeriesTrendChartOption}
                                      className="stock-analysis-page__echart stock-analysis-page__echart--sector-series"
                                      opts={{ renderer: "canvas" }}
                                      notMerge
                                      lazyUpdate
                                    />
                                  </Suspense>
                                </div>
                              ) : null}
                              {!sectorRankSeriesQuery.isFetching &&
                              !sectorRankSeriesQuery.isError &&
                              sectorRankSeriesQuery.data?.result?.state === "ok" &&
                              sectorSeriesTableRows.length === 0 ? (
                                <span className="text-default-500">窗口内无表格行可展示。</span>
                              ) : null}
                              {!sectorRankSeriesQuery.isFetching &&
                              !sectorRankSeriesQuery.isError &&
                              sectorRankSeriesQuery.data?.result?.state === "ok" &&
                              sectorSeriesTableRows.length > 0 ? (
                                <div className="stock-analysis-page__table-wrap">
                                  <table className="stock-analysis-page__table">
                                    <thead>
                                      <tr>
                                        <th scope="col">行业</th>
                                        <th scope="col">代码</th>
                                        <th className="stock-analysis-page__table-number" scope="col">
                                          score（最新）
                                        </th>
                                        <th className="stock-analysis-page__table-number" scope="col">
                                          rank（最新）
                                        </th>
                                        <th className="stock-analysis-page__table-number" scope="col">
                                          窗口累计涨跌
                                        </th>
                                        <th className="stock-analysis-page__table-number" scope="col">
                                          成分数
                                        </th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {sectorSeriesTableRows.map((row) => (
                                        <tr
                                          key={`${row.sector_code}-${row.trade_date}`}
                                          data-testid={`sector-series-row-${row.sector_code}`}
                                        >
                                          <td>{row.sector_name}</td>
                                          <td className="stock-analysis-page__tabular">{row.sector_code}</td>
                                          <td className="stock-analysis-page__table-number">
                                            {formatSectorSeriesScore(row.score)}
                                          </td>
                                          <td className="stock-analysis-page__table-number">
                                            {row.rank ?? "-"}
                                          </td>
                                          <td className="stock-analysis-page__table-number">
                                            {formatSectorSeriesCumPctChange(row.cum_pctchange_window)}
                                          </td>
                                          <td className="stock-analysis-page__table-number">
                                            {row.constituent_count ?? "-"}
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              ) : null}
                            </div>
                          </AccordionItem>
                    </Accordion>
                      </div>
                    </details>
                  </>
                ) : (
                  <div
                    className="stock-analysis-page__analytics-empty"
                    role="status"
                  >
                    板块数据不足，待补
                  </div>
                )}
              </section>

                </div>
              <details
                className="stock-analysis-page__strategy-research-more"
                data-testid="stock-analysis-strategy-research-more"
              >
                <summary
                  className="stock-analysis-page__strategy-research-more-summary"
                  data-testid="stock-analysis-strategy-research-more-summary"
                >
                  <span>策略研究背景</span>
                  <small>回测 / 事件 / 题材 / 规则</small>
                </summary>
                <div className="stock-analysis-strategy-card-grid" data-testid="stock-analysis-strategy-card-grid">
              {cycleRotationFramework ? (
                <LazyStrategyModuleCard
                  id="cycle-rotation"
                  title={cycleRotationFramework.display_name}
                  subtitle="周期轮动"
                  badgeLabel={
                    cycleRotationPanelSummary?.badgeLabel ??
                    localizeImplementationStage(cycleRotationFramework.implementation_stage)
                  }
                  summary={cycleRotationPanelSummary}
                  summaryTestId="stock-analysis-cycle-panel-summary"
                  expanded={isStrategyCardExpanded("cycle-rotation")}
                  onToggleExpand={() => toggleStrategyCard("cycle-rotation")}
                  mountDetail
                  sectionRef={cycleFrameworkSection.ref}
                  sectionTestId="stock-analysis-cycle-rotation-framework"
                  className="stock-analysis-page__cycle-framework"
                >
                  <LazyStrategyPanelComplianceDetails
                    complianceDetail={cycleRotationPanelSummary?.complianceDetail}
                    testId="stock-analysis-cycle-panel-compliance"
                  />
                  <LazyStockAnalysisCycleRuleSummary framework={cycleRotationFramework} />
                  {cycleMacroLayerSummary ? (
                    <div
                      className="stock-analysis-page__cycle-macro-layer"
                      data-testid="stock-analysis-cycle-macro-layer"
                    >
                      <div className={SA_SECTION_HEAD}>
                        <strong>宏观层</strong>
                        <span className={SA_PILL}>
                          {cycleMacroLayerSummary.statusLabel}
                        </span>
                      </div>
                      <p>
                        宏观分 {cycleMacroLayerSummary.macroScoreLabel}
                      </p>
                      <p>{cycleEvidenceLabel(cycleMacroLayerSummary.evidence)}</p>
                      <small>
                        {cycleInputSummary(cycleMacroLayerSummary.availableInputs, cycleMacroLayerSummary.missingInputs)}
                      </small>
                      {cycleMacroLayerSummary.macroGapLabels.length > 0 ? (
                        <div className="stock-analysis-page__cycle-constraints">
                          {cycleMacroLayerSummary.macroGapLabels.map((gap) => (
                            <span key={gap}>{cycleGapLabel(gap)}</span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  {cycleRotationFramework.lifecourt_overlay ? (
                    <div className="stock-analysis-page__cycle-lifecourt-overlay">
                      <strong>{cycleRotationFramework.lifecourt_overlay.display_name}</strong>
                      <p>{cycleBoundaryLabel(cycleRotationFramework.lifecourt_overlay.boundary)}</p>
                      <small>
                        {cycleInputSummary(
                          cycleRotationFramework.lifecourt_overlay.available_inputs,
                          cycleRotationFramework.lifecourt_overlay.missing_inputs,
                        )}
                      </small>
                      <div className="stock-analysis-page__cycle-constraints">
                        {cycleRotationFramework.lifecourt_overlay.life_long_gates.map((gate) => (
                          <span key={gate}>{cycleConstraintLabel(gate)}</span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  <div className="stock-analysis-page__cycle-layer-grid">
                    {cycleRotationFramework.layers.map((layer) => (
                      <article className="stock-analysis-page__cycle-layer" key={layer.key}>
                        <div>
                          <span>{cycleLayerTitleLabel(layer)}</span>
                          <strong>{cycleLayerWeightLabel(layer)}</strong>
                        </div>
                        <em>{localizeImplementationStage(layer.status)}</em>
                        <p>{cycleEvidenceLabel(layer.evidence)}</p>
                        <small>
                          {cycleInputSummary(layer.available_inputs, layer.missing_inputs)}
                        </small>
                      </article>
                    ))}
                  </div>
                  <div className="stock-analysis-page__cycle-constraints">
                    {cycleRotationFramework.constraints.map((constraint) => (
                      <span key={constraint}>{cycleConstraintLabel(constraint)}</span>
                    ))}
                  </div>
                  <div
                    className="stock-analysis-page__cycle-proxy-backtest"
                    data-testid="stock-analysis-candidate-history-portfolio-backtest"
                  >
                    {candidateHistoryPortfolioBacktestQuery.isLoading ? (
                      <TableSkeleton />
                    ) : null}
                    {candidateHistoryPortfolioBacktestQuery.isError ? (
                      <p className="stock-analysis-page__notice">
                        组合回测暂不可用：{strategyPanelErrorMessage(candidateHistoryPortfolioBacktestQuery.error)}
                      </p>
                    ) : null}
                    {!candidateHistoryPortfolioBacktestQuery.isLoading &&
                    !candidateHistoryPortfolioBacktestQuery.isError ? (
                      candidateHistoryPortfolioBacktestPayload?.status === "portfolio_proxy" &&
                      candidateHistoryPortfolioBacktestPayload.summary ? (
                        <>
                          <LazyBacktestBoundaryChips
                            label="组合回测"
                            missingInputs={candidateHistoryPortfolioBacktestPayload.missing_full_strategy_inputs}
                            testId="stock-analysis-portfolio-backtest-boundary"
                          />
                          <div className="stock-analysis-page__cycle-proxy-grid">
                            <div>
                              <span>组合回测收益</span>
                              <strong>
                                {formatBacktestSignedPercent(
                                  candidateHistoryPortfolioBacktestPayload.summary.cumulative_return,
                                )}
                              </strong>
                            </div>
                            <div>
                              <span>最大上涨区间</span>
                              <strong>
                                {formatBacktestSignedPercent(
                                  candidateHistoryPortfolioBacktestPayload.summary.max_gain.return,
                                )}
                              </strong>
                              <small>
                                {candidateHistoryPortfolioBacktestPayload.summary.max_gain.start_date} 至{" "}
                                {candidateHistoryPortfolioBacktestPayload.summary.max_gain.end_date}
                              </small>
                            </div>
                            <div>
                              <span>最大回撤区间</span>
                              <strong>
                                {formatBacktestSignedPercent(
                                  candidateHistoryPortfolioBacktestPayload.summary.max_drawdown.return,
                                )}
                              </strong>
                              <small>
                                {candidateHistoryPortfolioBacktestPayload.summary.max_drawdown.peak_date} 至{" "}
                                {candidateHistoryPortfolioBacktestPayload.summary.max_drawdown.trough_date}
                              </small>
                            </div>
                          </div>
                          <StockAnalysisBacktestCaliberDisclosure
                            model={candidateHistoryPortfolioBacktestCaliberDisclosure}
                          />
                        </>
                      ) : (
                        <CompactStatusTile
                          icon={<LineChartOutlined />}
                          label="组合回测"
                          value="样本不足"
                          testId="stock-analysis-portfolio-backtest-empty"
                        />
                      )
                    ) : null}
                  </div>
                  <div
                    className="stock-analysis-page__cycle-proxy-backtest"
                    data-testid="stock-analysis-cycle-proxy-backtest"
                  >
                    {cycleProxyBacktestQuery.isLoading ? (
                      <TableSkeleton />
                    ) : null}
                    {cycleProxyBacktestQuery.isError ? (
                      <p className="stock-analysis-page__notice">
                        代理回测暂不可用：{strategyPanelErrorMessage(cycleProxyBacktestQuery.error)}
                      </p>
                    ) : null}
                    {!cycleProxyBacktestQuery.isLoading && !cycleProxyBacktestQuery.isError ? (
                      cycleProxyBacktestPayload?.status === "proxy" && cycleProxyBacktestPayload.summary ? (
                        <>
                          <LazyBacktestBoundaryChips
                            label="代理回测"
                            missingInputs={cycleProxyBacktestPayload.missing_full_strategy_inputs}
                            testId="stock-analysis-cycle-proxy-boundary"
                          />
                          {cycleRotationPanelSummary?.proxyBacktestBasisDisclosure ? (
                            <p
                              className="stock-analysis-page__footnote"
                              data-testid="stock-analysis-cycle-proxy-basis-disclosure"
                            >
                              {cycleRotationPanelSummary.proxyBacktestBasisDisclosure}
                            </p>
                          ) : null}
                          <div className="stock-analysis-page__cycle-proxy-grid">
                            <div>
                              <span>累计收益</span>
                              <strong>{formatBacktestSignedPercent(cycleProxyBacktestPayload.summary.cumulative_return)}</strong>
                            </div>
                            <div>
                              <span>最大上涨区间</span>
                              <strong>
                                {formatBacktestSignedPercent(cycleProxyBacktestPayload.summary.max_gain.return)}
                              </strong>
                              <small>
                                {cycleProxyBacktestPayload.summary.max_gain.start_date} 至{" "}
                                {cycleProxyBacktestPayload.summary.max_gain.end_date}
                              </small>
                            </div>
                            <div>
                              <span>最大回撤区间</span>
                              <strong>
                                {formatBacktestSignedPercent(cycleProxyBacktestPayload.summary.max_drawdown.return)}
                              </strong>
                              <small>
                                {cycleProxyBacktestPayload.summary.max_drawdown.peak_date} 至{" "}
                                {cycleProxyBacktestPayload.summary.max_drawdown.trough_date}
                              </small>
                            </div>
                          </div>
                          <StockAnalysisBacktestCaliberDisclosure model={cycleProxyBacktestCaliberDisclosure} />
                        </>
                      ) : (
                        <CompactStatusTile
                          icon={<LineChartOutlined />}
                          label="代理回测"
                          value="样本不足"
                          testId="stock-analysis-cycle-proxy-empty"
                        />
                      )
                    ) : null}
                  </div>
                  <StockAnalysisWalkForwardPanel />
                </LazyStrategyModuleCard>
              ) : null}


              <LazyStrategyModuleCard
                id="theme-breakout"
                title="题材突变观察"
                subtitle="题材代理"
                badgeLabel={
                  themeBreakoutPanelSummary?.badgeLabel ??
                  `${localizeThemeRadarBadge(
                    strategyPayload?.theme_breakout?.is_proxy === true,
                    strategyPayload?.theme_breakout?.formula_version,
                  )}${themeBreakoutCards.length > 0 ? ` · ${themeBreakoutCards.length} 项` : ""}`
                }
                summary={themeBreakoutPanelSummary}
                summaryTestId="stock-analysis-theme-panel-summary"
                expanded={isStrategyCardExpanded("theme-breakout")}
                onToggleExpand={() => toggleStrategyCard("theme-breakout")}
                mountDetail
                sectionTestId="stock-analysis-theme-breakout"
              >
                <LazyStrategyPanelComplianceDetails
                            complianceDetail={themeBreakoutPanelSummary?.complianceDetail}
                            testId="stock-analysis-theme-panel-compliance"
                          />
                <LazyStockAnalysisThemeGroupedView
                  cards={themeBreakoutCards}
                  evidenceRows={themeEvidenceRows}
                  reviewItems={themeBreakoutReviewItems}
                  emptyMessage={
                    themeBreakoutUnsupported
                      ? themeBreakoutPanelSummary?.detail ?? "题材观察暂不可用，请先核对缺失证据。"
                      : "当前没有题材观察样本。"
                  }
                />
              </LazyStrategyModuleCard>

              <LazyStrategyModuleCard
                id="consensus-review"
                title="历史复核 / T+5 共振"
                subtitle="T+5 共振"
                badgeLabel={
                  consensusReviewPanelSummary.badgeLabel ??
                  (consensusReviewPanelSummary.tone === "positive" ? "已就绪" : "待复核")
                }
                summary={consensusReviewPanelSummary}
                summaryTestId="stock-analysis-consensus-panel-summary"
                expanded={isStrategyCardExpanded("consensus-review")}
                onToggleExpand={() => toggleStrategyCard("consensus-review")}
                mountDetail
                sectionTestId="stock-analysis-consensus-review-panel"
              >
                <div
                  className="stock-analysis-page__historical-review-label"
                  data-testid="stock-analysis-historical-review-section"
                >
                  <strong>历史复核摘要</strong>
                  <span>T+5 共振 · 候选历史与评分</span>
                </div>
                <div className="stock-analysis-page__consensus" data-testid="stock-analysis-consensus">
                          <div className="stock-analysis-page__consensus-stats">
                            <span>
                              趋势 <strong>{consensusSummary.strategyCounts.livermore}</strong> 只
                            </span>
                            <span>
                              融合策略 <strong>{consensusSummary.strategyCounts.hybrid_fusion}</strong> 只
                            </span>
                            <span>
                              超跌反弹观察 <strong>{consensusSummary.strategyCounts.mean_reversion}</strong> 只
                            </span>
                            <span>
                              多因子 <strong>{consensusSummary.strategyCounts.factor_screen}</strong> 只
                            </span>
                            <span>
                              合计去重 <strong>{consensusSummary.totalUnion}</strong> 只
                            </span>
                          </div>

                          {!consensusSummary.hasAnyStrategy ? (
                            <p className="stock-analysis-page__empty">
                              {consensusReviewPanelSummary.detail}
                            </p>
                          ) : consensusSummary.items.length === 0 ? (
                            <p className="stock-analysis-page__empty">
                              {consensusReviewPanelSummary.detail}
                            </p>
                          ) : (
                            <ul className="stock-analysis-page__list stock-analysis-page__list--compact">
                              {consensusSummary.items.map((row) => {
                                const isTriple = row.consensusCount >= 3;
                                const openDetail = () => {
                                  setDetailSelection(buildConsensusDetailSelection(row));
                                };
                                return (
                                  <li
                                    key={row.stockCode}
                                    className={`stock-analysis-page__consensus-row stock-analysis-page__row--clickable${
                                      isTriple ? " stock-analysis-page__consensus-row--triple" : ""
                                    }`}
                                    data-testid={`consensus-row-${row.stockCode}`}
                                    onClick={openDetail}
                                    role="button"
                                    tabIndex={0}
                                    onKeyDown={(e) => {
                                      if (e.key === "Enter" || e.key === " ") {
                                        e.preventDefault();
                                        openDetail();
                                      }
                                    }}
                                  >
                                    <div className="stock-analysis-page__consensus-head">
                                      <span
                                        className={`stock-analysis-page__consensus-badge${
                                          isTriple ? " stock-analysis-page__consensus-badge--triple" : ""
                                        }`}
                                      >
                                        {isTriple ? "三策略共振" : "核心共振"}
                                      </span>
                                      <strong>
                                        <span className="stock-analysis-page__tabular">
                                          {row.stockCode}
                                        </span>{" "}
                                        {row.stockName}
                                      </strong>
                                      <small className="stock-analysis-page__tabular">
                                        {row.sectorName || "-"}
                                      </small>
                                      <span className="stock-analysis-page__consensus-strategies">
                                        {row.strategies.map((kind) => (
                                          <span key={kind} className="stock-analysis-page__consensus-badge">
                                            {consensusStrategyLabel(kind)}
                                          </span>
                                        ))}
                                      </span>
                                    </div>
                                    <div className="stock-analysis-page__consensus-ranks">
                                      {row.livermoreRank != null && (
                                        <span>趋势 #{row.livermoreRank}</span>
                                      )}
                                      {row.hybridFusionRank != null && (
                                        <span>融合策略 #{row.hybridFusionRank}</span>
                                      )}
                                      {row.meanReversionRank != null && (
                                        <span>超跌反弹 #{row.meanReversionRank}</span>
                                      )}
                                      {row.factorScreenRank != null && (
                                        <span>多因子 #{row.factorScreenRank}</span>
                                      )}
                                    </div>
                                  </li>
                                );
                              })}
                            </ul>
                          )}
                          <p className="stock-analysis-page__footnote">
                            T+5 共振 · 超跌仅观察
                          </p>
                        </div>
              </LazyStrategyModuleCard>

                            <LazyStockAnalysisStrategyReviewCards
                client={client}
                analyticsAsOf={analyticsAsOf}
                currentMarketState={currentMarketState}
                strategyPrioritySeen={strategyPrioritySection.seen}
                strategyScorePayload={strategyScorePayload}
                strategyScoreLoading={strategyScoreQuery.isLoading}
                strategyScoreError={strategyScoreQuery.isError}
                strategyScoreErrorValue={strategyScoreQuery.error}
                strategyPriorityRows={strategyPriorityRows}
                marketPriorityPanelSummary={marketPriorityPanelSummary}
                marketPriorityExpanded={isStrategyCardExpanded("market-priority")}
                onToggleMarketPriority={() => toggleStrategyCard("market-priority")}
                marketPrioritySectionRef={strategyPrioritySection.ref}
                strategyBacktestPayload={strategyBacktestPayload}
                strategyBacktestRows={strategyBacktestRows}
                strategyBacktestSampleCount={strategyBacktestSampleCount}
                strategyBacktestWindow={strategyBacktestWindow}
                strategyBacktestDateRangeLabel={strategyBacktestDateRangeLabel}
                strategyBacktestLoading={strategyBacktestQuery.isLoading}
                strategyBacktestError={strategyBacktestQuery.isError}
                strategyBacktestErrorValue={strategyBacktestQuery.error}
                strategyBacktestPanelSummary={strategyBacktestPanelSummary}
                strategyBacktestExpanded={isStrategyCardExpanded("strategy-backtest")}
                onToggleStrategyBacktest={() => toggleStrategyCard("strategy-backtest")}
                strategyBacktestSectionRef={strategyBacktestSection.ref}
                strategyOptimizationPayload={strategyOptimizationPayload}
                strategyOptimizationRows={strategyOptimizationRows}
                strategyOptimizationLoading={strategyOptimizationQuery.isLoading}
                strategyOptimizationError={strategyOptimizationQuery.isError}
                strategyOptimizationErrorValue={strategyOptimizationQuery.error}
                strategyOptimizationPanelSummary={strategyOptimizationPanelSummary}
                strategyOptimizationExpanded={isStrategyCardExpanded("strategy-optimization")}
                onToggleStrategyOptimization={() => toggleStrategyCard("strategy-optimization")}
                strategyOptimizationSectionRef={strategyOptimizationSection.ref}
              />

              <LazyStrategyModuleCard
                id="observation-pools"
                title="多策略观察池"
                subtitle="观察池"
                badgeLabel={observationPoolsPanelSummary.badgeLabel ?? "观察池"}
                summary={observationPoolsPanelSummary}
                summaryTestId="stock-analysis-observation-pools-panel-summary"
                expanded={isStrategyCardExpanded("observation-pools")}
                onToggleExpand={() => toggleStrategyCard("observation-pools")}
                mountDetail
                sectionTestId="stock-analysis-mean-reversion"
              >
                <div className="stock-analysis-page__mean-reversion">
                  <div className={SA_SECTION_HEAD}>
                    <strong>超跌反弹观察池</strong>
                    <span className={SA_PILL}>条件触发</span>
                  </div>
                          {gateState && !meanReversionMarketActive ? (
                            <CompactStatusTile
                              icon={<FireOutlined />}
                              label="超跌"
                              value="暂停"
                              tone="warning"
                              testId="stock-analysis-mean-reversion-empty"
                            />
                          ) : null}
                          {meanReversionMarketActive && !meanReversionPayload ? (
                            <CompactStatusTile
                              icon={<FireOutlined />}
                              label="超跌"
                              value="未就绪"
                              tone="warning"
                              testId="stock-analysis-mean-reversion-empty"
                            />
                          ) : null}
                          {meanReversionMarketActive &&
                          meanReversionPayload &&
                          meanReversionPayload.items.length === 0 ? (
                            <CompactStatusTile
                              icon={<FireOutlined />}
                              label="超跌"
                              value="0 候选"
                              testId="stock-analysis-mean-reversion-empty"
                            />
                          ) : null}
                          {meanReversionMarketActive &&
                          meanReversionPayload &&
                          meanReversionPayload.items.length > 0 ? (
                            <ul className="stock-analysis-page__list stock-analysis-page__list--compact">
                              {meanReversionPayload.items.map((row) => {
                                const openMeanReversionDetail = () => {
                                  const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stock_code);
                                  setDetailSelection(buildMeanReversionDetailSelection({ row, ranks }));
                                };

                                return (
                                  <li
                                    key={row.stock_code}
                                    className="stock-analysis-page__mean-reversion-row stock-analysis-page__row--clickable"
                                    onClick={openMeanReversionDetail}
                                    role="button"
                                    tabIndex={0}
                                    onKeyDown={(e) => {
                                      if (e.key === "Enter" || e.key === " ") {
                                        e.preventDefault();
                                        openMeanReversionDetail();
                                      }
                                    }}
                                  >
                                    <div>
                                      <strong>#{row.rank}</strong>{" "}
                                      <span className="stock-analysis-page__tabular">{row.stock_code}</span>{" "}
                                      {row.stock_name}{" "}
                                      <small className="stock-analysis-page__tabular">
                                        {row.sector_name || row.sector_code || "-"}
                                      </small>
                                    </div>
                                    <div className="stock-analysis-page__mean-reversion-metrics stock-analysis-page__tabular">
                                      <span className="stock-analysis-page__mean-reversion-dd">
                                        20日回撤{" "}
                                        {row.drawdown_20d != null && Number.isFinite(row.drawdown_20d)
                                          ? `${(row.drawdown_20d * 100).toFixed(1)}%`
                                          : "待补"}
                                      </span>
                                      <span>
                                        收盘强度{" "}
                                        {row.close_strength != null && Number.isFinite(row.close_strength)
                                          ? `${(row.close_strength * 100).toFixed(0)}%`
                                          : "待补"}
                                      </span>
                                      <span>
                                        量比{" "}
                                        {row.vol_ratio != null && Number.isFinite(row.vol_ratio)
                                          ? `${row.vol_ratio.toFixed(1)}x`
                                          : "待补"}
                                      </span>
                                      <span>
                                        得分{" "}
                                        {row.score != null && Number.isFinite(row.score)
                                          ? row.score.toFixed(2)
                                          : "待补"}
                                      </span>
                                    </div>
                                  </li>
                                );
                              })}
                            </ul>
                          ) : null}
                          <div className="stock-analysis-page__signal-pill-row" aria-label="超跌筛选规则">
                            {["价格回撤", "企稳", "放量", "门控停用"].map((label) => (
                              <span
                                key={label}
                                className="stock-analysis-page__boundary-chip"
                              >
                                <FireOutlined aria-hidden="true" /> {label}
                              </span>
                            ))}
                          </div>
                        </div>
                <div className="stock-analysis-page__factor-screen">
                  <div className={SA_SECTION_HEAD}>
                    <strong>多因子选股</strong>
                    <span className={SA_PILL}>
                      {factorScreenPayload?.candidate_count ?? 0} 只 ·{" "}
                      {factorScreenCoverageNote ?? "数据未就绪"}
                    </span>
                  </div>
                          {!factorScreenPayload ? (
                            <CompactStatusTile
                              icon={<DatabaseOutlined />}
                              label="多因子"
                              value="未就绪"
                              tone="warning"
                              testId="stock-analysis-factor-screen-empty"
                            />
                          ) : factorScreenPayload.items.length === 0 ? (
                            <CompactStatusTile
                              icon={<DatabaseOutlined />}
                              label="多因子"
                              value="0 候选"
                              testId="stock-analysis-factor-screen-empty"
                            />
                          ) : (
                            <ul className="stock-analysis-page__list stock-analysis-page__list--compact">
                              {factorScreenPayload.items.map((row) => (
                                <li
                                  key={row.stock_code}
                                  className="stock-analysis-page__factor-screen-row stock-analysis-page__row--clickable"
                                  onClick={() => {
                                    const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stock_code);
                                    setDetailSelection(buildFactorScreenDetailSelection({ row, ranks }));
                                  }}
                                  role="button"
                                  tabIndex={0}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter" || e.key === " ") {
                                      e.preventDefault();
                                      const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stock_code);
                                      setDetailSelection(buildFactorScreenDetailSelection({ row, ranks }));
                                    }
                                  }}
                                >
                                  <div>
                                    <strong>#{row.rank}</strong>{" "}
                                    <span className="stock-analysis-page__tabular">{row.stock_code}</span>{" "}
                                    {row.stock_name}{" "}
                                    <small className="stock-analysis-page__tabular">
                                      {row.sector_name || row.industry || "-"}
                                    </small>
                                  </div>
                                  <div className="stock-analysis-page__factor-screen-metrics stock-analysis-page__tabular">
                                    <span>得分 {row.score.toFixed(3)}</span>
                                    {row.pe != null && <span>PE {row.pe.toFixed(1)}</span>}
                                    {row.roe != null && <span>ROE {(row.roe * 100).toFixed(1)}%</span>}
                                    {row.three_month_return != null && (
                                      <span>3月 {(row.three_month_return * 100).toFixed(1)}%</span>
                                    )}
                                    {row.dividend_yield != null && row.dividend_yield > 0 && (
                                      <span>股息 {(row.dividend_yield * 100).toFixed(2)}%</span>
                                    )}
                                  </div>
                                </li>
                              ))}
                            </ul>
                          )}
                          <div className="stock-analysis-page__signal-pill-row" aria-label="多因子选股因子">
                            {["价值", "质量", "动量", "低波", "股息"].map((label) => (
                              <span
                                key={label}
                                className="stock-analysis-page__boundary-chip"
                              >
                                <DatabaseOutlined aria-hidden="true" /> {label}
                              </span>
                            ))}
                            {factorScreenCoverageNote ? (
                              <span
                                className="stock-analysis-page__boundary-chip stock-analysis-page__boundary-chip--accent"
                                title={factorScreenCoverageNote}
                              >
                                覆盖 {compactText(factorScreenCoverageNote, 14)}
                              </span>
                            ) : null}
                          </div>
                        </div>
              </LazyStrategyModuleCard>

              <LazyStrategyModuleCard
                id="events-monitoring"
                title="关键事件与监控"
                subtitle="事件风险"
                badgeLabel={eventsMonitoringPanelSummary.badgeLabel ?? "事件"}
                summary={eventsMonitoringPanelSummary}
                summaryTestId="stock-analysis-events-panel-summary"
                expanded={isStrategyCardExpanded("events-monitoring")}
                onToggleExpand={() => toggleStrategyCard("events-monitoring")}
                mountDetail
                sectionTestId="stock-analysis-events-monitoring"
              >
                {eventMonitorRows.length > 0 ? (
                  <div className="stock-analysis-page__table-wrap">
                    <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                      <thead>
                        <tr>
                          <th scope="col">来源</th>
                          <th scope="col">级别</th>
                          <th scope="col">事件</th>
                          <th scope="col">影响</th>
                          <th scope="col">明细</th>
                        </tr>
                      </thead>
                      <tbody>
                        {eventMonitorRows.map((row) => (
                          <tr key={row.key} data-level={row.level}>
                            <td>{eventSourceLabel(row.source)}</td>
                            <td>
                              <span className="stock-analysis-page__event-level" data-level={row.level}>
                                {eventLevelLabel(row.level)}
                              </span>
                            </td>
                            <td>{eventNameLabel(row)}</td>
                            <td>{eventImpactLabel(row)}</td>
                            <td title={eventDetailLabel(row)}>{compactText(eventDetailLabel(row), 26)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                        ) : (
                  <CompactStatusTile
                    icon={<FireOutlined />}
                    label="关键事件"
                    value="0"
                    testId="stock-analysis-events-empty"
                  />
                )}
              </LazyStrategyModuleCard>
                </div>
              </details>
              </div>
              </AnalysisGrid>
                </Suspense>
              ) : null}
            </details>

          </>
        ) : null}
        {detailSelection ? (
          <Suspense fallback={null}>
            <LazyStockDetailDrawer
              stockCode={detailSelection.code}
              stockName={detailSelection.name}
              asOfDate={stockDetailAsOfDate}
              asOfDateIsResolved={stockDetailAsOfDate != null}
              reviewContext={buildStockDetailReviewContext(detailSelection)}
              onClose={() => setDetailSelection(null)}
            />
          </Suspense>
        ) : null}
        {isAgentFrontendEnabled() ? (
          <AntDrawer
            placement="left"
            width={560}
            open={agentDrawerOpen}
            onClose={() => setAgentDrawerOpen(false)}
            className="stock-analysis-page__agent-drawer"
            data-testid="stock-analysis-agent-drawer"
            title="复核助手"
            extra={
              <AntButton
                type="text"
                onClick={() => setAgentDrawerOpen(false)}
                aria-label="关闭抽屉"
              >
                关闭
              </AntButton>
            }
          >
            <div style={stockAnalysisPageCssVars} className="theme-dh-api stock-analysis-page__agent-drawer-body">
              {agentDrawerOpen ? (
                <Suspense fallback={<TextSkeleton className="w-full" />}>
                  <LazyAgentPanel
                    pageId="stock-analysis"
                    currentFilters={stockAnalysisAgentPageContext.current_filters}
                    defaultFilters={{ research_domain: "stock" }}
                    selectedRows={stockAnalysisAgentPageContext.selected_rows}
                    contextNote={stockAnalysisAgentPageContext.context_note ?? null}
                  />
                </Suspense>
              ) : null}
            </div>
          </AntDrawer>
        ) : null}
      </section>
    </MarketWorkbenchFrame>
  );
}
