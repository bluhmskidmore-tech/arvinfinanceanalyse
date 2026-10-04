import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useApiClient } from "../../../api/clientContext";
import { useSystemReadInteraction } from "../../../router/systemReadInteractionContext";
import type {
  LivermoreCandidateHistoryRow,
  LivermoreStrategyPayload,
  StockAnalysisWorkbenchDataGap,
} from "../../../api/contracts";
import { isAgentFrontendEnabled } from "../../../app/navigation";
import {
  buildCandidateReviewQueue,
  buildClosedLoopSummary,
  buildStockClosedLoopFreshnessIssue,
  buildDataBoundarySummary,
  buildDecisionSummary,
  buildMarketStateCard,
  buildRiskExitRows,
  buildSectorFilterSummary,
  buildSectorRows,
  buildStockAnalysisEvidenceStatus,
  buildStockSectorOverviewState,
  buildWorkbenchDataDigest,
  buildThemeTaxonomyGapSummary,
  buildReviewQueueEmptyState,
  buildReviewQueueSectorFilterView,
  localizeStockBackendText,
  isStockModulePrimaryExcluded,
  mergeStockClosedLoopMeta,
  pickStockFreshnessMeta,
} from "../lib/stockAnalysisPageModel";
import type { WorkbenchFact } from "../lib/stockAnalysisPageModel";
import {
  buildStockAnalysisRailReviewState,
  pretradeQualificationReasonLabel,
  riskExitBlockedSummary,
  stockPageErrorMessage as errorMessage,
  stockSupplyBasisLabel,
  stockStatusLabel as statusLabel,
} from "../lib/stockAnalysisPageCopy";
import {
  buildApiLedgerSourceCells,
  buildCandidateHistoryStatsByCode,
  buildGateStateVariantRows,
} from "../lib/stockAnalysisPagePresentationModel";
import { normalizeIsoCalendarDate } from "../lib/stockAnalysisDate";
import {
  buildBackendSupplyOverview,
  cycleInputLabel,
  dataGapFamilyLabel,
} from "../lib/stockAnalysisPageLabels";
import { buildStockAnalysisAgentPageContext } from "../lib/buildStockAnalysisAgentPageContext";
import { lookupStockStrategyRanks } from "../lib/buildConsensusSummary";
import {
  buildStockAnalysisWorkbenchReviewQueue,
  enrichStockAnalysisWorkbenchReviewQueue,
} from "../lib/stockAnalysisWorkbenchQueueModel";
import { attachCandidateSignalWindow } from "../lib/stockAnalysisSignalWindowModel";
import {
  buildFactorScreenDetailSelection,
  buildReviewQueueDetailSelection,
  buildRiskExitDetailSelection,
  buildStockDetailReviewContext,
  type StockDetailSelection,
} from "../lib/stockAnalysisDetailSelection";
import {
  SA_SHELL_PAGE,
} from "../lib/stockAnalysisPageChrome";
import { useFirstScreenAnalyticsTabs } from "../hooks/useFirstScreenAnalyticsTabs";
import { useResearchDeskQueries } from "../hooks/useResearchDeskQueries";
import { useResearchDeskState } from "../hooks/useResearchDeskState";
import { useSectorPanelState } from "../hooks/useSectorPanelState";
import { useSectorRankSeriesSupport } from "../hooks/useSectorRankSeriesSupport";
import {
  endpointQueryState,
  useStockAnalysisEndpointEvidence,
} from "../hooks/useStockAnalysisEndpointEvidence";
import { useStockAnalysisWorkbenchQueries } from "../hooks/useStockAnalysisWorkbenchQueries";
import { useStockSectionScroll } from "../hooks/useStockSectionScroll";
import { useStockSelectionRefresh } from "../hooks/useStockSelectionRefresh";
import { useStrategyCardExpansion } from "../hooks/useStrategyCardExpansion";
import {
  StockAnalysisErrorWorkbench,
  StockAnalysisLoadingWorkbench,
} from "../components/StockAnalysisBoundaryWorkbenches";
import { StockAnalysisDataHealthCard } from "../components/StockAnalysisDataHealthCard";
import { StockAnalysisQualificationState } from "../components/StockAnalysisQualificationState";
import { StockAnalysisEvidenceDisclosure } from "../components/StockAnalysisEvidenceDisclosure";
import { StockAnalysisEvidenceLedgerRail } from "../components/StockAnalysisEvidenceLedgerRail";
import { StockAnalysisFactorCandidatesCard } from "../components/StockAnalysisFactorCandidatesCard";
import { StockAnalysisObservationClosurePanel } from "../components/StockAnalysisObservationClosurePanel";
import { StockAnalysisWorkbenchDigest } from "../components/StockAnalysisWorkbenchDigest";
import { StockAnalysisWorkbenchActions } from "../components/StockAnalysisWorkbenchActions";
import { StockAnalysisAgentDrawer } from "../components/StockAnalysisAgentDrawer";
import { StockAnalysisStageNav } from "../components/StockAnalysisStageNav";
import { StockAnalysisResearchDesk } from "./StockAnalysisResearchDesk";
import { buildStockAnalysisResearchDeskModel } from "../lib/stockAnalysisResearchDeskModel";
import { enrichResearchDeskCandidateWithQuotes } from "../lib/stockAnalysisResearchDeskModel";
import {
  buildStockFactorScreenCard,
  buildStockFirstScreenDecisionGate,
} from "../lib/stockAnalysisFirstScreenModel";
import { stockAnalysisPageCssVars } from "../lib/stockAnalysisTokens";
import {
  MarketWorkbenchFrame,
  type MarketWorkbenchStatus,
} from "../../workbench/market-shell";
import { SectionHead } from "../../../components/layout";
import {
  DataStatusStrip,
  PageDecisionHero,
  PageV2Shell,
} from "../../../components/page/PagePrimitives";
import { StockAnalysisDeepResearchSkeleton } from "../components/StockAnalysisDeepResearchSkeleton";
import "./StockAnalysisPage.css";
import "./StockAnalysisEditorialLedger.css";

const STOCK_ANALYSIS_ENDPOINT_EVIDENCE_RAIL_ID = "stock-analysis-endpoint-evidence-rail";

const LazyStockDetailDrawer = lazy(() =>
  import("../components/StockDetailDrawer").then((module) => ({ default: module.StockDetailDrawer })),
);
const LazyStockAnalysisDeepResearchZone = lazy(() =>
  import("../components/StockAnalysisDeepResearchZone").then((module) => ({
    default: module.StockAnalysisDeepResearchZone,
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

export default function StockAnalysisPage() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const systemReadInteraction = useSystemReadInteraction();
  const [asOfOverride, setAsOfOverride] = useState<string | null>(null);
  const [detailSelection, setDetailSelection] = useState<StockDetailSelection | null>(null);
  const [agentDrawerOpen, setAgentDrawerOpen] = useState(false);
  const [deepResearchRequested, setDeepResearchRequested] = useState(false);
  const [queueSearchText, setQueueSearchText] = useState("");
  const [queueMarketFilter, setQueueMarketFilter] = useState<"all" | "SH" | "SZ">("all");
  const [queueSignalFilter, setQueueSignalFilter] = useState("");
  const [boundaryDiagnosticsOpen, setBoundaryDiagnosticsOpen] = useState(false);
  const [activeWorkbenchFactId, setActiveWorkbenchFactId] = useState<string | null>(null);
  const [focusedEndpointKey, setFocusedEndpointKey] = useState<string | null>(null);
  const [requestedEndpointKeys, setRequestedEndpointKeys] = useState<string[]>([]);
  const [researchDeskSelectedCode, setResearchDeskSelectedCode] = useState<string | null>(null);
  const {
    poolTab: researchDeskPoolTab,
    setPoolTab: setResearchDeskPoolTab,
    dossierTab: researchDeskDossierTab,
    setDossierTab: setResearchDeskDossierTab,
    watchlistCodes: researchDeskWatchlistCodes,
    noteDraft: researchDeskNoteDraft,
    setNoteDraft: setResearchDeskNoteDraft,
    savedNote: researchDeskSavedNote,
    toggleWatchlist: toggleResearchDeskWatchlist,
    openHistory: handleResearchDeskOpenHistory,
    saveNote: saveResearchDeskNote,
  } = useResearchDeskState({
    onRequestCandidateHistory: () =>
      setRequestedEndpointKeys((current) =>
        current.includes("candidate-history") ? current : [...current, "candidate-history"],
      ),
  });
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

  const {
    strategyQuery,
    isInitialWorkbenchLoading,
    strategyPayload,
    workbenchPayload,
    pretradeQualification,
    pretradeDecisionReady,
    researchDateAligned,
    researchReviewReady,
    resultMeta,
    formalUseAllowed,
    analyticsAsOf,
    cycleFrameworkSection,
    strategyPrioritySection,
    strategyBacktestSection,
    strategyOptimizationSection,
    confluenceQuery,
    confluencePayload: queriedConfluencePayload,
    cycleRotationFramework,
    currentMarketState,
    strategyScoreQuery,
    strategyScorePayload,
    strategyOptimizationQuery,
    strategyOptimizationPayload,
    strategyBacktestSnapshotFrom,
    strategyBacktestQuery,
    strategyBacktestPayload,
    strategyBacktestWindow,
    cycleProxyBacktestQuery,
    cycleProxyBacktestPayload,
    candidateHistoryPortfolioBacktestQuery,
    candidateHistoryPortfolioBacktestPayload,
    candidateHistorySlowState,
    strategyScoreSlowState,
  } = useStockAnalysisWorkbenchQueries({
    client,
    asOfOverride,
    candidateHistoryEndpointRequested,
    cycleProxyEndpointRequested,
    portfolioProxyEndpointRequested,
    firstScreenPriorityRequested,
    firstScreenOptimizationRequested,
  });
  const confluencePayload = pretradeDecisionReady ? queriedConfluencePayload : null;
  const confluenceResultMeta = pretradeDecisionReady ? confluenceQuery.data?.result_meta : undefined;
  const refetchReadView = () => {
    if (systemReadInteraction.generation) {
      systemReadInteraction.refresh();
      return;
    }
    void strategyQuery.refetch();
  };
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
  useEffect(() => {
    if (pretradeDecisionReady) return;
    setAgentDrawerOpen(false);
    setRequestedEndpointKeys((current) => current.filter((key) => key === "candidate-history"));
  }, [pretradeDecisionReady]);
  useEffect(() => {
    if (researchReviewReady) return;
    setDetailSelection(null);
    setDeepResearchRequested(false);
    setRequestedEndpointKeys([]);
    setResearchDeskSelectedCode(null);
  }, [researchReviewReady]);
  const shouldMountDeepResearch = deepResearchRequested;

  const confluenceFreshnessIssue = buildStockClosedLoopFreshnessIssue(confluenceResultMeta);
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
  const sectorSeriesPayload = sectorRankSeriesQuery.data?.result ?? null;
  const sectorSeriesMeta = sectorRankSeriesQuery.data?.result_meta;
  const sectorSeriesDataDate = sectorSeriesPayload?.as_of_date ?? sectorSeriesMeta?.as_of_date ?? null;
  const sectorSeriesLagDays = sectorSeriesPayload?.lag_days ?? null;
  const sectorSeriesIsStale =
    sectorSeriesPayload?.stale === true || sectorSeriesMeta?.fallback_mode === "latest_snapshot";
  const sectorRowsSourceLabel =
    sectorRowsSource === "series"
      ? [
          sectorSeriesIsStale ? "历史观察" : "支撑观察",
          `数据日 ${sectorSeriesDataDate ?? "待确认"}`,
          sectorSeriesIsStale && sectorSeriesLagDays != null ? `滞后 ${sectorSeriesLagDays} 天` : null,
          "非主策略快照",
        ]
          .filter(Boolean)
          .join(" · ")
      : sectorRowsSource === "snapshot"
        ? "策略快照"
        : "待补";
  const sectorOverview = useMemo(() => buildStockSectorOverviewState(sectorRowsFull), [sectorRowsFull]);
  const { leaderRow: sectorLeaderRow, tailRow: sectorTailRow, coverageCount: sectorCoverageCount } = sectorOverview;

  const reviewQueue = useMemo(() => {
    if (!researchReviewReady) return [];
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
    );
  }, [researchReviewReady, strategyPayload, workbenchPayload]);

  const factorScreenPayload = strategyPayload?.factor_screen_candidates;
  const hybridFusionPayload = strategyPayload?.hybrid_fusion_candidates;
  const queueSignalOptions = useMemo(
    () =>
      Array.from(new Map(reviewQueue.map((card) => [card.sourcePool, card.sourcePoolLabel])).entries()),
    [reviewQueue],
  );
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

  const { scrollToStockSection } = useStockSectionScroll({
    onRequestDeepResearch: () => setDeepResearchRequested(true),
  });

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
        selectedSectorLabel: selectedSectorLabel ?? "全部行业",
      }),
    [reviewQueue, sectorFilterSectorCode, selectedSectorLabel],
  );
  const {
    sectorOptions,
    filteredCandidates,
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
        const matchesMarket =
          queueMarketFilter === "all" || card.stockCode.toLocaleUpperCase().endsWith(`.${queueMarketFilter}`);
        const matchesSignal = queueSignalFilter.length === 0 || card.sourcePool === queueSignalFilter;
        return matchesSearch && matchesMarket && matchesSignal;
      }),
    [filteredCandidates, normalizedQueueSearch, queueMarketFilter, queueSignalFilter],
  );
  const queueVisibleCount = queueVisibleCandidates.length;
  const queueTotalCount = reviewQueue.length;
  const queueFiltersActive =
    normalizedQueueSearch.length > 0 ||
    sectorFilterSectorCode !== null ||
    queueMarketFilter !== "all" ||
    queueSignalFilter.length > 0;
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
  const riskRows = useMemo(
    () => (pretradeDecisionReady && strategyPayload ? buildRiskExitRows(strategyPayload, confluencePayload) : []),
    [pretradeDecisionReady, strategyPayload, confluencePayload],
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

  const closedLoopMeta = useMemo(
    () =>
      mergeStockClosedLoopMeta(
        confluencePayload?.closed_loop_state != null,
        strategyQuery.data?.result_meta,
        confluenceResultMeta,
      ),
    [confluencePayload?.closed_loop_state, confluenceResultMeta, strategyQuery.data?.result_meta],
  );

  const closedLoopSummary = useMemo(
    () =>
      strategyPayload
        ? buildClosedLoopSummary(
            strategyPayload,
            confluencePayload,
            closedLoopMeta,
            workbenchPayload?.replay_closure ?? null,
          )
        : null,
    [strategyPayload, confluencePayload, closedLoopMeta, workbenchPayload?.replay_closure],
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
  const headerDateValue = normalizeIsoCalendarDate(strategyPayload?.as_of_date);
  const pickerDisplay = normalizeIsoCalendarDate(asOfOverride) ?? headerDateValue;

  const stockDetailAsOfDate = researchReviewReady ? workbenchPayload?.as_of_date ?? undefined : undefined;
  // 信号窗口披露：给复核队列注入该来源池在当前市场状态下的 T+5/T+20 前瞻统计，
  // 明确候选的有效观察窗口（strategy-score 透传，缺统计时字段缺失不渲染）。
  const queueCandidatesWithSignalWindow = useMemo(
    () => attachCandidateSignalWindow(queueVisibleCandidates, pretradeDecisionReady ? strategyScorePayload : null),
    [pretradeDecisionReady, queueVisibleCandidates, strategyScorePayload],
  );
  const candidateHistoryItems = useMemo(
    () => strategyBacktestPayload?.items ?? [],
    [strategyBacktestPayload],
  );
  const candidateHistoryByCode = useMemo(() => {
    const map = new Map<string, LivermoreCandidateHistoryRow[]>();
    for (const item of candidateHistoryItems) {
      if (!item.stock_code) continue;
      const bucket = map.get(item.stock_code) ?? [];
      bucket.push(item);
      map.set(item.stock_code, bucket);
    }
    return map;
  }, [candidateHistoryItems]);
  const candidateHistoryStatsByCode = useMemo(
    () => buildCandidateHistoryStatsByCode(candidateHistoryByCode),
    [candidateHistoryByCode],
  );
  const historyPoolCandidates = useMemo(() => {
    const rows = queueCandidatesWithSignalWindow.filter((card) => candidateHistoryStatsByCode.has(card.stockCode));
    return [...rows].sort((left, right) => {
      const leftStats = candidateHistoryStatsByCode.get(left.stockCode);
      const rightStats = candidateHistoryStatsByCode.get(right.stockCode);
      return (rightStats?.matured ?? 0) - (leftStats?.matured ?? 0);
    });
  }, [candidateHistoryStatsByCode, queueCandidatesWithSignalWindow]);
  const watchlistCandidates = useMemo(
    () =>
      queueCandidatesWithSignalWindow.filter((card) =>
        researchDeskWatchlistCodes.includes(card.stockCode),
      ),
    [queueCandidatesWithSignalWindow, researchDeskWatchlistCodes],
  );
  const researchDeskPoolCandidates = useMemo(() => {
    if (researchDeskPoolTab === "watchlist") return watchlistCandidates;
    if (researchDeskPoolTab === "history") return historyPoolCandidates;
    return queueCandidatesWithSignalWindow;
  }, [historyPoolCandidates, queueCandidatesWithSignalWindow, researchDeskPoolTab, watchlistCandidates]);

  useEffect(() => {
    if (!researchReviewReady) return;
    if (researchDeskPoolTab !== "history" && researchDeskDossierTab !== "appendix") return;
    setRequestedEndpointKeys((current) =>
      current.includes("candidate-history") ? current : [...current, "candidate-history"],
    );
  }, [researchReviewReady, researchDeskDossierTab, researchDeskPoolTab]);

  useEffect(() => {
    if (queueCandidatesWithSignalWindow.length === 0) {
      setResearchDeskSelectedCode((current) => (current == null ? current : null));
      return;
    }
    setResearchDeskSelectedCode((current) =>
      current && queueCandidatesWithSignalWindow.some((card) => card.stockCode === current)
        ? current
        : queueCandidatesWithSignalWindow[0]?.stockCode ?? null,
    );
  }, [queueCandidatesWithSignalWindow]);

  const researchDeskSelectedCandidate =
    queueCandidatesWithSignalWindow.find((card) => card.stockCode === researchDeskSelectedCode) ??
    queueCandidatesWithSignalWindow[0] ??
    null;
  const {
    detailQuery: researchDeskDetailQuery,
    klineQuery: researchDeskKlineQuery,
    newsQuery: researchDeskNewsQuery,
    newsAsOfDate: researchDeskNewsAsOfDate,
  } = useResearchDeskQueries({
    client,
    selectedCandidate: researchDeskSelectedCandidate,
    asOfDate: stockDetailAsOfDate,
    analyticsAsOf,
  });
  const researchDeskSelectedHistoryRows = useMemo(
    () =>
      researchDeskSelectedCandidate
        ? candidateHistoryByCode.get(researchDeskSelectedCandidate.stockCode) ?? []
        : [],
    [candidateHistoryByCode, researchDeskSelectedCandidate],
  );
  const researchDeskSelectedRisk =
    researchDeskSelectedCandidate != null
      ? riskRows.find((row) => row.stockCode === researchDeskSelectedCandidate.stockCode) ?? null
      : null;
  // 选中候选的展示副本：叠加个股详情/K 线接口真实返回的行情字段（量、额、换手、振幅、区间高低）。
  const researchDeskDisplayCandidate = useMemo(
    () =>
      enrichResearchDeskCandidateWithQuotes(
        researchDeskSelectedCandidate,
        researchDeskDetailQuery.data?.result ?? null,
        researchDeskKlineQuery.data?.result ?? null,
      ),
    [
      researchDeskSelectedCandidate,
      researchDeskDetailQuery.data?.result,
      researchDeskKlineQuery.data?.result,
    ],
  );
  const researchDeskSignalWindow = researchDeskSelectedCandidate?.signalWindow ?? null;
  const researchDeskHistoryLoaded =
    candidateHistoryEndpointRequested || strategyBacktestQuery.isSuccess || candidateHistoryItems.length > 0;
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

  const { endpointEvidenceItems, observationClosureSummary } = useStockAnalysisEndpointEvidence({
    analyticsAsOf,
    cycleRotationFramework,
    formalUseAllowed,
    strategyQuery,
    strategyPayload,
    confluenceQuery,
    confluencePayload,
    sectorRankSeriesQuery,
    sectorSeriesExpanded,
    shouldLoadSectorSeriesFallback,
    strategyScoreQuery,
    strategyScorePayload,
    strategyPrioritySection,
    firstScreenPriorityRequested,
    strategyBacktestQuery,
    strategyBacktestPayload,
    strategyBacktestWindow,
    strategyBacktestSnapshotFrom,
    strategyBacktestSection,
    candidateHistoryEndpointRequested,
    strategyOptimizationQuery,
    strategyOptimizationPayload,
    strategyOptimizationSection,
    firstScreenOptimizationRequested,
    cycleProxyBacktestQuery,
    cycleProxyBacktestPayload,
    cycleFrameworkSection,
    cycleProxyEndpointRequested,
    candidateHistoryPortfolioBacktestQuery,
    candidateHistoryPortfolioBacktestPayload,
    portfolioProxyEndpointRequested,
  });

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

  const stockAnalysisAgentPageContext = useMemo(
    () =>
      buildStockAnalysisAgentPageContext({
        asOfDate: strategyPayload?.as_of_date ?? null,
        requestedAsOfDate: strategyPayload?.requested_as_of_date ?? asOfOverride ?? null,
        systemReadGeneration: systemReadInteraction.generation,
        pretradeQualificationStatus: pretradeQualification?.status ?? null,
        sectorFilterSectorCode,
        sectorFilterLabel: selectedSectorLabel,
        sectorView,
        detailSelection,
      }),
    [
      asOfOverride,
      detailSelection,
      pretradeQualification?.status,
      sectorFilterSectorCode,
      sectorView,
      selectedSectorLabel,
      strategyPayload?.as_of_date,
      strategyPayload?.requested_as_of_date,
      systemReadInteraction.generation,
    ],
  );
  const workbenchResearchAuthorityAllowsReview = workbenchPayload?.decision_summary.can_review_candidates === true;
  const workbenchCanReviewCandidates = researchReviewReady;
  const workbenchAnswerState =
    workbenchResearchAuthorityAllowsReview && !researchDateAligned
      ? "blocked"
      : workbenchPayload?.page_question.answer_state ??
        (workbenchCanReviewCandidates ? (queueTotalCount > 0 ? "review_ready" : "no_data") : "blocked");
  const workbenchPrimaryBlocker =
    workbenchResearchAuthorityAllowsReview && !researchDateAligned
      ? `工作台实际日 ${workbenchPayload?.as_of_date ?? "待确认"} 与主策略日 ${
          strategyPayload?.as_of_date ?? "待确认"
        } 不一致`
      : workbenchPayload?.decision_summary.primary_blocker ??
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
  const qualificationReason = pretradeQualificationReasonLabel(pretradeQualification?.reason);
  const researchProjectionEmpty = workbenchAnswerState === "no_data" && workbenchPayload?.first_screen.review_queue.length === 0;
  const researchDeskEmptyHeadline =
    workbenchResearchAuthorityAllowsReview && !researchDateAligned
      ? "研究日期未对齐"
      : researchProjectionEmpty
        ? "当前观察日无候选"
      : workbenchCanReviewCandidates
        ? "当前观察日无研究候选"
        : "研究队列未就绪";
  const researchDeskEmptyDetail =
    workbenchResearchAuthorityAllowsReview && !researchDateAligned
      ? `${localizedWorkbenchPrimaryBlocker ?? "研究数据日期不一致"}，当前不展示跨日候选或详情。`
      : researchProjectionEmpty
        ? "权威研究队列为 0，不从策略主包或历史结果补候选。"
      : workbenchCanReviewCandidates
        ? "权威研究队列为 0，不从策略主包或历史结果补候选。"
        : workbenchPayload?.page_question.reason ?? reviewQueueEmptyState?.detail ?? "查看观察池与板块";
  const researchDeskDecisionStatusLabel = workbenchCanReviewCandidates
    ? `${workbenchAnswerState === "limited_review" ? "有限复核" : "研究可复核"}${
        pretradeDecisionReady ? "" : " · 盘前未闭合"
      }`
    : "研究未就绪";
  const rawResearchBoundaryReason = workbenchPayload?.page_question.reason?.trim() || null;
  const researchBoundaryReason = rawResearchBoundaryReason
    ? rawResearchBoundaryReason === "Candidates are present, but at least one data quality or boundary warning remains visible."
      ? "研究候选可复核，仍有数据或边界事项待确认"
      : localizeStockBackendText(rawResearchBoundaryReason)
    : null;
  const researchDeskDecisionReason = workbenchCanReviewCandidates
    ? pretradeDecisionReady
      ? researchBoundaryReason ?? "当日研究数据与盘前资格均已闭合，仍仅供观察复核。"
      : `${researchBoundaryReason ? `${researchBoundaryReason}；` : ""}当日研究数据可用；盘前资格尚未闭合（${qualificationReason}），风险与执行结论保持关闭。`
    : localizedWorkbenchPrimaryBlocker ?? qualificationReason;
  const firstScreenDecisionGate = useMemo(
    () =>
      buildStockFirstScreenDecisionGate({
        pretradeQualificationStatus: pretradeQualification?.status ?? null,
        pretradeQualificationReason: pretradeQualificationReasonLabel(pretradeQualification?.reason),
        workbenchReviewAllowed: workbenchCanReviewCandidates,
        strategyAsOf: analyticsAsOf,
        confluenceAsOf: confluencePayload?.as_of_date ?? null,
        confluenceLoading:
          pretradeDecisionReady &&
          (confluenceQuery.isLoading || (confluenceQuery.isFetching && !confluenceQuery.data)),
        confluenceError: pretradeDecisionReady && confluenceQuery.isError,
        confluenceFreshnessIssue,
        workbenchBlockerReason: pretradeDecisionReady ? localizedWorkbenchPrimaryBlocker : qualificationReason,
        closedLoopSummary,
        entryObservationCount: confluencePayload?.entry_observations.length ?? 0,
      }),
    [
      analyticsAsOf,
      closedLoopSummary,
      confluenceFreshnessIssue,
      confluencePayload,
      confluenceQuery.data,
      confluenceQuery.isError,
      confluenceQuery.isFetching,
      confluenceQuery.isLoading,
      localizedWorkbenchPrimaryBlocker,
      pretradeDecisionReady,
      pretradeQualification?.reason,
      pretradeQualification?.status,
      qualificationReason,
      workbenchCanReviewCandidates,
    ],
  );
  const researchDeskModel = useMemo(
    () =>
      buildStockAnalysisResearchDeskModel({
        decisionStatusLabel: researchDeskDecisionStatusLabel,
        decisionReason: researchDeskDecisionReason,
        candidateProgressionAllowed: workbenchCanReviewCandidates,
        poolTab: researchDeskPoolTab,
        selectedSectorLabel: selectedSectorLabel ?? "全部行业",
        // 传行情富化后的候选：市场快照与近 60 日高低点只存在于富化后的 rawFields。
        selectedCandidate: researchDeskDisplayCandidate,
        poolCandidates: researchDeskPoolCandidates,
        signalWindow: researchDeskSignalWindow,
        selectedRisk: researchDeskSelectedRisk,
        detailQueryState: endpointQueryState({
          enabled: researchDeskSelectedCandidate != null,
          isLoading: researchDeskDetailQuery.isLoading,
          isFetching: researchDeskDetailQuery.isFetching,
          isError: researchDeskDetailQuery.isError,
          hasData: Boolean(researchDeskDetailQuery.data?.result),
        }),
        detailPayload: researchDeskDetailQuery.data?.result ?? null,
        klineQueryState: endpointQueryState({
          enabled: researchDeskSelectedCandidate != null,
          isLoading: researchDeskKlineQuery.isLoading,
          isFetching: researchDeskKlineQuery.isFetching,
          isError: researchDeskKlineQuery.isError,
          hasData: Boolean(researchDeskKlineQuery.data?.result),
        }),
        klinePayload: researchDeskKlineQuery.data?.result ?? null,
        newsQueryState: endpointQueryState({
          enabled: researchDeskSelectedCandidate != null && researchDeskNewsAsOfDate != null,
          isLoading: researchDeskNewsQuery.isLoading,
          isFetching: researchDeskNewsQuery.isFetching,
          isError: researchDeskNewsQuery.isError,
          hasData: Boolean(researchDeskNewsQuery.data?.result),
        }),
        newsPayload: researchDeskNewsQuery.data?.result ?? null,
        selectedHistoryRows: researchDeskSelectedHistoryRows,
        noteDraft: researchDeskNoteDraft,
        savedNote: researchDeskSavedNote,
        auditRows: [],
        analyticsAsOfDate: analyticsAsOf ?? strategyPayload?.as_of_date ?? null,
      }),
    [
      analyticsAsOf,
      researchDeskDecisionReason,
      researchDeskDecisionStatusLabel,
      researchDeskDetailQuery.data?.result,
      researchDeskDetailQuery.isError,
      researchDeskDetailQuery.isFetching,
      researchDeskDetailQuery.isLoading,
      researchDeskKlineQuery.data?.result,
      researchDeskKlineQuery.isError,
      researchDeskKlineQuery.isFetching,
      researchDeskKlineQuery.isLoading,
      researchDeskNewsAsOfDate,
      researchDeskNewsQuery.data?.result,
      researchDeskNewsQuery.isError,
      researchDeskNewsQuery.isFetching,
      researchDeskNewsQuery.isLoading,
      researchDeskNoteDraft,
      researchDeskDisplayCandidate,
      researchDeskPoolCandidates,
      researchDeskPoolTab,
      researchDeskSavedNote,
      researchDeskSelectedCandidate,
      researchDeskSelectedHistoryRows,
      researchDeskSelectedRisk,
      researchDeskSignalWindow,
      selectedSectorLabel,
      strategyPayload?.as_of_date,
      workbenchCanReviewCandidates,
    ],
  );
  const researchDeskDisplayModel = useMemo(() => {
    if (pretradeDecisionReady) return researchDeskModel;
    const restrictedRiskLabel = "盘前资格尚未闭合，风险退出结论未读取";
    return {
      ...researchDeskModel,
      selectedHeaderItems: researchDeskModel.selectedHeaderItems.map((item) =>
        item.key === "risk" ? { ...item, value: restrictedRiskLabel } : item,
      ),
      riskTags: workbenchCanReviewCandidates ? ["研究可复核", "盘前资格未闭合"] : researchDeskModel.riskTags,
      riskSummary: `${restrictedRiskLabel}。`,
    };
  }, [pretradeDecisionReady, researchDeskModel, workbenchCanReviewCandidates]);
  const firstScreenDecisionTone =
    firstScreenDecisionGate.status === "reviewable"
      ? "ok"
      : firstScreenDecisionGate.status === "unresolved"
        ? "muted"
        : firstScreenDecisionGate.status === "blocked" ||
            firstScreenDecisionGate.status === "workbench_blocked"
          ? "error"
          : "watch";
  const workbenchRouteLabel = "/ui/market-data/stock-analysis/workbench";
  const workbenchResultKindLabel = resultMeta?.result_kind ?? "market_data.stock_analysis.workbench";
  const stockWorkbenchStatus: MarketWorkbenchStatus = isInitialWorkbenchLoading
    ? {
        label: "读取中",
        tone: "muted" as const,
        detail: "正在读取主策略、门禁与数据边界；完成前不形成复核结论。",
      }
    : strategyQuery.isError
      ? {
          label: "读取失败",
          tone: "error" as const,
          detail: "股票分析主包读取失败，当前不形成门禁结论。",
        }
      : researchReviewReady && !pretradeDecisionReady
        ? {
            label: "研究可用",
            tone: "watch" as const,
            detail: `当日研究数据可用；盘前资格尚未闭合。权威研究候选 ${queueTotalCount} 个，风险与执行结论保持关闭。`,
          }
      : {
          label: firstScreenDecisionGate.statusLabel,
          tone: firstScreenDecisionTone,
          detail: `首屏权威结论：${firstScreenDecisionGate.primaryReason}；工作台原始依据：${workbenchAnswerLabel} / ${workbenchCandidateReviewLabel}；不可执行`,
        };
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
  const pageDataGaps = useMemo<
    Array<LivermoreStrategyPayload["data_gaps"][number] & { blocks_review?: boolean }>
  >(() => {
    const rawWorkbenchDataGaps: unknown[] = Array.from(workbenchPayload?.first_screen.data_gaps ?? []);
    const normalizedWorkbenchDataGaps = rawWorkbenchDataGaps.map(normalizeWorkbenchDataGap);
    const validWorkbenchDataGaps = normalizedWorkbenchDataGaps.every((gap) => gap !== null)
      ? (normalizedWorkbenchDataGaps as StockAnalysisWorkbenchDataGap[])
      : null;

    return rawWorkbenchDataGaps.length > 0 && validWorkbenchDataGaps
      ? validWorkbenchDataGaps
      : strategyPayload?.data_gaps ?? [];
  }, [strategyPayload?.data_gaps, workbenchPayload?.first_screen.data_gaps]);
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
  const factorScreenModuleState = useMemo(
    () =>
      strategyPayload?.module_states?.find((state) => state.key === "factor_screen_candidates") ?? null,
    [strategyPayload],
  );
  const factorScreenCard = useMemo(
    () => buildStockFactorScreenCard(factorScreenPayload, factorScreenModuleState),
    [factorScreenModuleState, factorScreenPayload],
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
        question: "工作台原始依据是否允许候选进入复核队列？",
        answerLabel: `工作台依据：${workbenchAnswerLabel}`,
        reason: `仅作为首屏闭环门禁的一个输入；${
          workbenchReviewBlocked
            ? `首要阻断：${localizedWorkbenchPrimaryBlocker ?? "阻断原因待确认"}。`
            : workbenchAnswerState === "no_data"
              ? "当前没有可进入复核队列的候选。"
              : "候选与证据已返回。"
        } 最终以页面上方首屏权威结论为准。`,
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
  const queueGateStatusLabel = isInitialWorkbenchLoading
    ? "门控读取中"
    : queueGateLabel.startsWith("门控")
      ? queueGateLabel
      : `门控 ${queueGateLabel}`;
  const queueLoopStatusLabel = isInitialWorkbenchLoading
    ? "闭环读取中"
    : `闭环 ${firstScreenDecisionGate.statusLabel}`;
  const queueLoopStatusTone = isInitialWorkbenchLoading
    ? "neutral"
    : firstScreenDecisionGate.status === "reviewable"
      ? "positive"
      : firstScreenDecisionGate.status === "blocked" ||
          firstScreenDecisionGate.status === "workbench_blocked"
        ? "negative"
        : "warning";
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
  const apiLedgerSourceCells = useMemo(
    () => buildApiLedgerSourceCells(backendTableCount, resultMeta),
    [backendTableCount, resultMeta],
  );
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
  const gateStateVariantRows = useMemo(() => buildGateStateVariantRows(), []);
  // 标题区只保留日期与口径；来源版本继续留在证据栏，避免首屏重复。
  const stockWorkbenchMetaItems = [
    {
      label: "日期",
      value: isInitialWorkbenchLoading
        ? "读取中"
        : backendSupplyOverview?.asOfLabel ?? analyticsAsOf ?? "待返回",
    },
    {
      label: "口径",
      value: isInitialWorkbenchLoading
        ? "读取中"
        : stockSupplyBasisLabel(strategyQuery.data?.result_meta?.basis ?? workbenchPayload?.basis ?? "analytical"),
    },
  ];
  const stockWorkbenchToolbarActions = (
    <StockAnalysisWorkbenchActions
      pickerDisplay={pickerDisplay}
      queueSearchText={queueSearchText}
      marketFilter={queueMarketFilter}
      onMarketFilterChange={setQueueMarketFilter}
      sectorOptions={sectorOptions}
      selectedSectorCode={sectorFilterSectorCode}
      onSelectSector={toggleSectorFilter}
      signalOptions={queueSignalOptions}
      signalFilter={queueSignalFilter}
      onSignalFilterChange={setQueueSignalFilter}
      poolTab={researchDeskPoolTab}
      onPoolTabChange={setResearchDeskPoolTab}
      queueStatusLabel={isInitialWorkbenchLoading ? "数据读取中" : queueDataStatusLabel}
      gateStatusLabel={isInitialWorkbenchLoading ? "门控读取中" : queueGateStatusLabel}
      loopStatusLabel={queueLoopStatusLabel}
      formalUseLabel={
        isInitialWorkbenchLoading ? "口径读取中" : formalUseAllowed ? "主包就绪" : "仅供观察"
      }
      agentDrawerOpen={agentDrawerOpen}
      agentEnabled={pretradeDecisionReady}
      generatedAt={strategyQuery.data?.result_meta?.generated_at}
      onAsOfOverrideChange={setAsOfOverride}
      onQueueSearchTextChange={setQueueSearchText}
      onOpenAgentDrawer={() => setAgentDrawerOpen(true)}
      onRefresh={refreshStockSelection}
      onRefetch={refetchReadView}
      isRefreshing={isRefreshingChoiceStock}
      refreshStatusMessage={stockRefreshStatusMessage}
      refreshStatusTone={stockRefreshStatusTone}
    />
  );
  const openResearchDeskDetailDrawer = (candidate = researchDeskSelectedCandidate) => {
    if (!candidate) return;
    const ranks = lookupStockStrategyRanks(strategyPayload ?? null, candidate.stockCode);
    setDetailSelection(
      buildReviewQueueDetailSelection({
        card: candidate,
        ranks,
        reviewQueueUsesHybridFusion,
      }),
    );
  };
  const handleResearchDeskSaveNote = () => saveResearchDeskNote(researchDeskSelectedCandidate);

  return (
    <MarketWorkbenchFrame
      pageKey="stock-analysis"
      chrome="body-only"
      themeScope="stock-analysis"
      title="股票分析"
      question="A 股观察工作台 / 后端口径复核"
      status={stockWorkbenchStatus}
      metaItems={stockWorkbenchMetaItems}
    >
      <PageV2Shell testId="stock-analysis-page-v2-shell" themeScope="stock-analysis">
        <section
          data-testid="stock-analysis-page"
          className={`${SA_SHELL_PAGE} theme-dh-api stock-analysis-page stock-analysis-page--market-shell dark text-foreground`}
          data-moss-theme-scope="stock-analysis"
          data-layout-rev="2026-08-31-fable-v2"
          data-data-viz-rev="2026-05-31e"
          style={stockAnalysisPageCssVars}
        >
          <PageDecisionHero
            className="stock-analysis-page__compact-chrome"
            testId="stock-analysis-page-compact-chrome"
            titleTestId="stock-analysis-page-title"
            eyebrow="研究工作台"
            title="股票研究"
            businessQuestion="今天能否继续复核、应该先看谁，当前卡在哪里？"
            reportDateSlot={
              <span className="stock-analysis-page__compact-chrome-meta">
                {stockWorkbenchMetaItems[0]?.value ?? "待返回"}
              </span>
            }
            actions={null}
          >
            <div className="stock-analysis-page__compact-control-row">
              <DataStatusStrip
                testId="stock-analysis-page-status-strip"
                className="stock-analysis-page__compact-status-strip"
              >
                <span
                  className="stock-analysis-page__compact-status-chip"
                  data-tone={queueDataStatusTone}
                >
                  {isInitialWorkbenchLoading ? "数据读取中" : queueDataStatusLabel}
                </span>
                <span
                  className="stock-analysis-page__compact-status-chip"
                  data-tone={
                    isInitialWorkbenchLoading
                      ? "neutral"
                      : boundaryRailIssueCount > 0
                        ? "warning"
                        : "positive"
                  }
                >
                  {isInitialWorkbenchLoading ? "门控读取中" : queueGateStatusLabel}
                </span>
                <span
                  className="stock-analysis-page__compact-status-chip"
                  data-tone={queueLoopStatusTone}
                >
                  {queueLoopStatusLabel}
                </span>
              </DataStatusStrip>
              <div
                className="stock-analysis-page__compact-toolbar"
                data-testid="stock-analysis-page-toolbar-owner"
              >
                {stockWorkbenchToolbarActions}
              </div>
            </div>
            <StockAnalysisStageNav variant="menu" />
          </PageDecisionHero>

        {strategyQuery.isLoading ? (
          <StockAnalysisLoadingWorkbench />
        ) : null}

        {strategyQuery.isError ? (
          <StockAnalysisErrorWorkbench
            message={errorMessage(strategyQuery.error)}
            onRetry={refetchReadView}
            isRetrying={strategyQuery.isFetching}
          />
        ) : null}

        {mainModuleUnavailable ? (
          <StockAnalysisErrorWorkbench
            message={`主策略模块状态为${statusLabel(mainModuleStatus)}。接口已返回，但没有可展示的策略主包；请重新读取或核对 workbench 主模块契约。`}
            onRetry={refetchReadView}
            isRetrying={strategyQuery.isFetching}
          />
        ) : null}

        {!strategyQuery.isLoading &&
        !strategyQuery.isError &&
        !mainModuleUnavailable &&
        workbenchPayload ? (
          <>
            <StockAnalysisQualificationState
              workbench={workbenchPayload}
              researchReviewReady={researchReviewReady}
              researchDateAligned={researchDateAligned}
              reviewQueueCount={queueTotalCount}
              marketState={marketState}
              marketAsOf={analyticsAsOf}
              sectorRows={strategySectorRows}
              sectorAsOf={strategyPayload?.sector_rank?.as_of_date ?? null}
              onRetry={() => void strategyQuery.refetch()}
              isRetrying={strategyQuery.isFetching}
            />
            <div
              className="stock-analysis-page__first-screen"
              data-testid="stock-analysis-first-screen-workbench"
            >
              <div
                className="stock-analysis-page__first-screen-main"
                data-testid="stock-analysis-first-screen-main"
              >
                <section
                className="stock-analysis-page__candidate-review"
                data-testid="stock-analysis-candidate-review"
                aria-labelledby="stock-analysis-candidate-review-title"
              >
                <StockAnalysisResearchDesk
                  model={researchDeskDisplayModel}
                  queueSearchText={queueSearchText}
                  onQueueSearchTextChange={setQueueSearchText}
                  sectorOptions={sectorOptions}
                  selectedSectorCode={sectorFilterSectorCode}
                  onSelectSector={toggleSectorFilter}
                  poolTab={researchDeskPoolTab}
                  onPoolTabChange={setResearchDeskPoolTab}
                  dossierTab={researchDeskDossierTab}
                  onDossierTabChange={setResearchDeskDossierTab}
                  poolCandidates={researchDeskPoolCandidates}
                  queueVisibleCount={queueVisibleCount}
                  queueTotalCount={queueTotalCount}
                  interactionsDisabled={!researchReviewReady}
                  restrictedActionsDisabled={!pretradeDecisionReady}
                  reviewQueueUsesHybridFusion={reviewQueueUsesHybridFusion}
                  selectedCandidate={researchDeskDisplayCandidate}
                  selectedCandidateCode={researchDeskSelectedCode}
                  onSelectCandidate={setResearchDeskSelectedCode}
                  watchlistCodes={researchDeskWatchlistCodes}
                  onToggleWatchlist={toggleResearchDeskWatchlist}
                  selectedRisk={researchDeskSelectedRisk}
                  noteDraft={researchDeskNoteDraft}
                  onNoteDraftChange={setResearchDeskNoteDraft}
                  savedNote={researchDeskSavedNote}
                  onSaveNote={handleResearchDeskSaveNote}
                  onOpenDeepResearch={() => {
                    setDeepResearchRequested(true);
                    scrollToStockSection("stock-analysis-deep-research");
                  }}
                  onJumpToEvidence={() => scrollToStockSection("stock-analysis-validation-evidence")}
                  onOpenDetailDrawer={() => openResearchDeskDetailDrawer()}
                  onOpenHistory={handleResearchDeskOpenHistory}
                  sectorLinkSummary={queueSectorLinkSummary}
                  sectorLinkFocus={queueSectorLinkFocus}
                  queueEmptyHeadline={researchDeskEmptyHeadline}
                  queueEmptyDetail={researchDeskEmptyDetail}
                  historyLoading={strategyBacktestQuery.isLoading || strategyBacktestQuery.isFetching}
                  historyLoaded={researchDeskHistoryLoaded}
                />
                </section>
              </div>
            </div>
            {!pretradeDecisionReady ? <StockAnalysisDataHealthCard /> : null}
          </>
        ) : null}

        {marketState ? (
          <>
            <section
              id="stock-analysis-validation-evidence"
              className="stock-analysis-page__validation-evidence"
              data-testid="stock-analysis-validation-evidence"
              aria-labelledby="stock-analysis-validation-evidence-title"
            >
              <SectionHead
                category="按需验证"
                title="策略验证与治理证据"
                titleId="stock-analysis-validation-evidence-title"
                contentGap="tight"
                numbered={false}
              />
              <div className="stock-analysis-page__validation-evidence-stack">
                {pretradeDecisionReady && factorScreenPayload ? (
                  <details
                    className="stock-analysis-page__factor-disclosure"
                    data-testid="stock-analysis-factor-disclosure"
                  >
                    <summary className="stock-analysis-page__factor-disclosure-summary">
                      <span>信号验证</span>
                      <strong>完整因子初筛候选</strong>
                      <small>默认收起 · 只读观察，不参与首屏门禁</small>
                    </summary>
                    <StockAnalysisFactorCandidatesCard
                      model={factorScreenCard}
                      items={factorScreenPayload.items.slice(0, 15)}
                      onOpenDetail={(row) => {
                        const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stock_code);
                        setDetailSelection(buildFactorScreenDetailSelection({ row, ranks }));
                      }}
                    />
                  </details>
                ) : null}

                {researchReviewReady ? <details
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
                <strong>{pretradeDecisionReady ? "共振、K线、因子、题材与回测" : "个股详情、K线与当前行业观察"}</strong>
                <small>{pretradeDecisionReady ? "默认收起 · 按需展开完整研究工作台" : "只读研究 · 正式评分、代理回测、风险与执行仍受限"}</small>
              </summary>
              {shouldMountDeepResearch ? (
                <Suspense fallback={<StockAnalysisDeepResearchSkeleton />}>
                  <LazyStockAnalysisDeepResearchZone
                      strategyPayload={strategyPayload}
                      confluencePayload={confluencePayload}
                      decisionGate={firstScreenDecisionGate}
                      client={client}
                      analyticsAsOf={analyticsAsOf}
                      currentMarketState={currentMarketState}
                      queueTotalCount={queueTotalCount}
                      setDetailSelection={setDetailSelection}
                      scrollToStockSection={scrollToStockSection}
                      strategyScoreQuery={strategyScoreQuery}
                      strategyScorePayload={strategyScorePayload}
                      strategyOptimizationQuery={strategyOptimizationQuery}
                      strategyOptimizationPayload={strategyOptimizationPayload}
                      strategyBacktestQuery={strategyBacktestQuery}
                      strategyBacktestPayload={strategyBacktestPayload}
                      strategyBacktestWindow={strategyBacktestWindow}
                      strategyBacktestSnapshotFrom={strategyBacktestSnapshotFrom}
                      cycleProxyBacktestQuery={cycleProxyBacktestQuery}
                      cycleProxyBacktestPayload={cycleProxyBacktestPayload}
                      candidateHistoryPortfolioBacktestQuery={candidateHistoryPortfolioBacktestQuery}
                      candidateHistoryPortfolioBacktestPayload={candidateHistoryPortfolioBacktestPayload}
                      sectorRankSeriesQuery={sectorRankSeriesQuery}
                      cycleFrameworkSection={cycleFrameworkSection}
                      strategyPrioritySection={strategyPrioritySection}
                      strategyBacktestSection={strategyBacktestSection}
                      strategyOptimizationSection={strategyOptimizationSection}
                      cycleProxyEndpointRequested={cycleProxyEndpointRequested}
                      portfolioProxyEndpointRequested={portfolioProxyEndpointRequested}
                      candidateHistoryEndpointRequested={candidateHistoryEndpointRequested}
                      firstScreenAnalyticsTab={firstScreenAnalyticsTab}
                      firstScreenAnalyticsRequested={firstScreenAnalyticsRequested}
                      firstScreenPriorityRequested={firstScreenPriorityRequested}
                      firstScreenOptimizationRequested={firstScreenOptimizationRequested}
                      handleFirstScreenAnalyticsTabChange={handleFirstScreenAnalyticsTabChange}
                      isStrategyCardExpanded={isStrategyCardExpanded}
                      toggleStrategyCard={toggleStrategyCard}
                      sectorView={sectorView}
                      handleSectorViewChange={handleSectorViewChange}
                      sectorFilterSectorCode={sectorFilterSectorCode}
                      toggleSectorFilter={toggleSectorFilter}
                      sectorRowsFull={sectorRowsFull}
                      sectorRowsSourceLabel={sectorRowsSourceLabel}
                      sectorLeaderRow={sectorLeaderRow}
                      sectorTailRow={sectorTailRow}
                      sectorCoverageCount={sectorCoverageCount}
                      sectorSeriesCollapseKeys={sectorSeriesCollapseKeys}
                      handleSectorSeriesCollapseChange={handleSectorSeriesCollapseChange}
                      sectorSeriesWindow={sectorSeriesWindow}
                      handleSectorSeriesWindowChange={handleSectorSeriesWindowChange}
                      sectorSeriesUnsupportedNotes={sectorSeriesUnsupportedNotes}
                      sectorSeriesTrendLines={sectorSeriesTrendLines}
                      sectorSeriesTrendChartOption={sectorSeriesTrendChartOption}
                      sectorSeriesTableRows={sectorSeriesTableRows}
                      readOnlyResearch={pretradeDecisionReady ? null : { model: researchDeskDisplayModel, selectedCandidate: researchDeskDisplayCandidate }}
                  />
                </Suspense>
              ) : null}
                </details> : null}
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
                          ? "规则版本已返回"
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
                      statusLabel={`工作台依据 ${workbenchAnswerLabel}`}
                      gateStatusLabel={queueGateStatusLabel}
                      evidenceCount={
                        typeof resultMeta?.evidence_rows === "number"
                          ? resultMeta.evidence_rows
                          : queueLeadEvidenceCount
                      }
                      boundaryCount={dataGapCount || queueLeadBoundaryCount}
                      gapCountLabel={dataGapDisplay}
                      availableOutputsLabel="主策略已返回，扩展诊断按需加载"
                      primaryGapLabel={primaryGapLedgerLabel}
                      leadCandidateName={queueLeadCandidate?.stockName}
                      boundaryIssueCount={boundaryRailIssueCount}
                      sourceVersionSummary={sourceVersionSummary}
                      basisLabel={strategyBasisLabel}
                      qualityLabel={backendSupplyOverview?.qualityLabel ?? "正常"}
                      updatedAtLabel={
                        backendSupplyOverview?.asOfLabel ??
                        decisionSummary?.asOfLabel ??
                        analyticsAsOf ??
                        "—"
                      }
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
              </div>
            </section>

          </>
        ) : null}
        {researchReviewReady && detailSelection ? (
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
        {isAgentFrontendEnabled() && pretradeDecisionReady ? (
          <StockAnalysisAgentDrawer
            open={agentDrawerOpen}
            context={stockAnalysisAgentPageContext}
            onClose={() => setAgentDrawerOpen(false)}
          />
        ) : null}
        </section>
      </PageV2Shell>
    </MarketWorkbenchFrame>
  );
}
