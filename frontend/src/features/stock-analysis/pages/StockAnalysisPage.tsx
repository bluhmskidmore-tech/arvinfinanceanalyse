import { useEffect, useMemo, useState } from "react";
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
import { Alert, Button, Collapse, Drawer, Tabs, Typography } from "antd";
import dayjs from "dayjs";

import { useApiClient } from "../../../api/client";
import type {
  BacktestWindowSummary,
  LivermoreCandidateHistoryPortfolioBacktestPayload,
  LivermoreCycleProxyBacktestPayload,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyPayload,
  ResultMeta,
} from "../../../api/contracts";
import ReactECharts from "../../../lib/echarts";
import { AnalysisGrid, DataStatusStrip } from "../../../components/page/PagePrimitives";
import { AgentPanel } from "../../agent/AgentPanel";
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
  buildStockAnalysisKpiStrip,
  buildStockSectorOverviewState,
  buildSectorHeavyweightPreview,
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
  buildStockAnalysisPagePurpose,
  buildReviewQueueEmptyState,
  buildReviewQueueSectorFilterView,
  localizeStockBackendText,
  localizeImplementationStage,
  localizeMarketDataStatus,
  localizeThemeRadarBadge,
  isActionableLivermoreUnsupportedOutput,
  isStockModulePrimaryExcluded,
  mergeStockClosedLoopMeta,
  pickStockFreshnessMeta,
} from "../lib/stockAnalysisPageModel";
import type {
  StockCandidateReviewQueueItem,
  StockEndpointEvidenceQueryState,
  StockObservationClosureReasonInput,
  StockSectorRow,
  WorkbenchFact,
  WorkbenchSlowState,
} from "../lib/stockAnalysisPageModel";
import {
  buildSectorStrengthOption,
  sectorViewTabs,
} from "../lib/stockAnalysisChartModel";
import {
  buildStockAnalysisRailReviewState,
  buildThemeBreakoutBlockerCopy,
  compactStockText as compactText,
  filterChipClass,
  kpiToneToDelta,
  rawStockErrorMessage as rawErrorMessage,
  stockPageErrorMessage as errorMessage,
  stockSupplyFallbackLabel,
  stockSupplyBasisLabel,
  stockSupplyQualityLabel,
  stockSupplyVendorLabel,
  stockStatusLabel as statusLabel,
  stockStrategyPanelErrorMessage as strategyPanelErrorMessage,
} from "../lib/stockAnalysisPageCopy";
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
  gapTone,
  readinessTone,
} from "../lib/stockAnalysisPageLabels";
import {
  backtestStatsText,
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
  strategyPriorityReasonLabel,
  strategyPriorityStatusLabel,
} from "../lib/stockAnalysisPriorityModel";
import {
  buildStrategyOptimizationRows,
  strategyOptimizationDateWeightedText,
  strategyOptimizationPrimaryStats,
  strategyOptimizationReasonLabel,
} from "../lib/stockAnalysisOptimizationModel";
import {
  formatSectorSeriesCumPctChange,
  formatSectorSeriesScore,
} from "../lib/stockAnalysisSectorSeriesModel";
import { buildStockAnalysisAgentPageContext } from "../lib/buildStockAnalysisAgentPageContext";
import { buildConsensusSummary, consensusStrategyLabel, lookupStockStrategyRanks } from "../lib/buildConsensusSummary";
import { stockGateContextTone, stockGateDecisionTone, stockSourceGateTone } from "../lib/stockAnalysisPageTones";
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
  DECISION_GRID_ICONS,
  SA_CARD_TITLE,
  SA_FIRST_CARD,
  SA_FIRST_HERO,
  SA_PILL,
  SA_SECTION_DESC,
  SA_SECTION_EYEBROW,
  SA_SECTION_HEAD,
  SA_SHELL_LAYOUT,
  SA_SHELL_MAIN,
  SA_SHELL_PAGE,
} from "../lib/stockAnalysisPageChrome";
import { useDeferredSectionSeen } from "../hooks/useDeferredSectionSeen";
import { useFirstScreenAnalyticsTabs } from "../hooks/useFirstScreenAnalyticsTabs";
import { useSectorPanelState } from "../hooks/useSectorPanelState";
import { useSectorRankSeriesSupport } from "../hooks/useSectorRankSeriesSupport";
import { useSectorSortState } from "../hooks/useSectorSortState";
import { useStockSelectionRefresh } from "../hooks/useStockSelectionRefresh";
import { useStrategyCardExpansion } from "../hooks/useStrategyCardExpansion";
import { EquityKpiCard } from "../components/EquityKpiCard";
import { BacktestBoundaryChips } from "../components/StockAnalysisBacktestBoundaryChips";
import {
  StockAnalysisErrorWorkbench,
  StockAnalysisLoadingWorkbench,
} from "../components/StockAnalysisBoundaryWorkbenches";
import { StockAnalysisCycleRuleSummary } from "../components/StockAnalysisCycleRuleSummary";
import { StockAnalysisDeepZoneHeader } from "../components/StockAnalysisDeepZoneHeader";
import { StockAnalysisCandidateLedgerTable } from "../components/StockAnalysisCandidateLedgerTable";
import { StockAnalysisConsensusFirstScreen } from "../components/StockAnalysisConsensusFirstScreen";
import { StockAnalysisEvidenceLedgerRail } from "../components/StockAnalysisEvidenceLedgerRail";
import {
  StockAnalysisReviewLedgerFirstScreen,
  type StockAnalysisLedgerCell,
} from "../components/StockAnalysisReviewLedgerFirstScreen";
import { StockAnalysisStrategyLensSection } from "../components/StockAnalysisStrategyLensSection";
import { StockAnalysisStrategyReviewCards } from "../components/StockAnalysisStrategyReviewCards";
import { StockAnalysisThemeBreakoutPanel } from "../components/StockAnalysisThemeBreakoutPanel";
import { StockAnalysisObservationPreview } from "../components/StockAnalysisObservationPreview";
import { CompactStatusTile, StatusIcon } from "../components/StockAnalysisStatusPrimitives";
import { StrategyModuleCard } from "../components/StrategyModuleCard";
import { StrategyPanelComplianceDetails } from "../components/StrategyPanelResultStrip";
import { StockDetailDrawer } from "../components/StockDetailDrawer";
import { StockAnalysisWorkbenchActions } from "../components/StockAnalysisWorkbenchActions";
import { stockAnalysisPageCssVars } from "../lib/stockAnalysisTokens";
import { EMPTY_STRATEGY_PRIORITY_ROWS, stockAnalysisReadQueryOptions } from "../lib/stockAnalysisQueryOptions";
import { MarketWorkbenchFrame } from "../../workbench/market-shell";
import "./StockAnalysisPage.css";

const { Text } = Typography;

const STOCK_ANALYSIS_ENDPOINT_EVIDENCE_RAIL_ID = "stock-analysis-endpoint-evidence-rail";

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

function candidateEvidenceValue(card: StockCandidateReviewQueueItem, key: string, fallback = "待补"): string {
  const value =
    card.rawFields.find((field) => field.key === key)?.value ??
    [...card.primaryEvidence, ...card.supportingEvidence].find((field) => field.key === key)?.value;
  return value?.trim() ? value : fallback;
}

function confidenceTone(label: string): "positive" | "neutral" | "warning" {
  const normalized = label.trim().toLowerCase();
  if (normalized === "高" || normalized === "high") return "positive";
  if (normalized === "低" || normalized === "low") return "warning";
  return "neutral";
}

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

function supportedOutputLabel(key: string): string {
  const labels: Record<string, string> = {
    market_gate: "市场门控",
    sector_rank: "板块强弱",
    stock_candidates: "趋势候选",
    uptrend_momentum_candidates: "上升趋势",
    fresh_trend_watchlist: "新趋势观察",
    mean_reversion_candidates: "均值回归",
    factor_screen_candidates: "多因子",
    theme_breakout: "题材突破",
    hybrid_fusion: "融合观察",
    risk_exit: "风险退出",
  };
  return labels[key] ?? "输出待确认";
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
  const [queueSearchText, setQueueSearchText] = useState("");
  const [completeEvidenceOnly, setCompleteEvidenceOnly] = useState(false);
  const [boundaryDiagnosticsOpen, setBoundaryDiagnosticsOpen] = useState(false);
  const [activeWorkbenchFactId, setActiveWorkbenchFactId] = useState<string | null>(null);
  const [focusedEndpointKey, setFocusedEndpointKey] = useState<string | null>(null);
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
    handleFirstScreenAnalyticsTabChange,
  } = useFirstScreenAnalyticsTabs();

  const strategyQueryKey = ["stock-analysis", "livermore-strategy", asOfOverride ?? "__default"] as const;

  const strategyQuery = useQuery({
    queryKey: strategyQueryKey,
    queryFn: () =>
      asOfOverride
        ? client.getLivermoreStrategy({ asOfDate: asOfOverride })
        : client.getLivermoreStrategy(),
    ...stockAnalysisReadQueryOptions,
  });

  const strategyPayload = strategyQuery.data?.result ?? null;
  const analyticsAsOf = strategyPayload?.as_of_date ?? null;
  const {
    isRefreshing: isRefreshingChoiceStock,
    refreshStatusMessage: stockRefreshStatusMessage,
    refreshStatusTone: stockRefreshStatusTone,
    refreshStockSelection,
  } = useStockSelectionRefresh({
    client,
    queryClient,
    asOfDate: asOfOverride ?? analyticsAsOf ?? undefined,
  });
  const deferredSectionsEnabled = Boolean(strategyPayload?.as_of_date);
  const cycleFrameworkSection = useDeferredSectionSeen<HTMLElement>(deferredSectionsEnabled);
  const strategyPrioritySection = useDeferredSectionSeen<HTMLElement>(deferredSectionsEnabled);
  const strategyBacktestSection = useDeferredSectionSeen<HTMLElement>(deferredSectionsEnabled);
  const strategyOptimizationSection = useDeferredSectionSeen<HTMLElement>(deferredSectionsEnabled);

  const confluenceQuery = useQuery({
    queryKey: ["stock-analysis", "livermore-signal-confluence", strategyPayload?.as_of_date ?? "__none"],
    queryFn: () =>
      client.getLivermoreSignalConfluence({
        asOfDate: strategyPayload?.as_of_date ?? undefined,
      }),
    enabled: Boolean(strategyPayload?.as_of_date),
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

  const pagePurpose = useMemo(
    () =>
      strategyPayload ? buildStockAnalysisPagePurpose(strategyPayload, strategyFreshnessMeta) : null,
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
    return strategyPayload ? buildCandidateReviewQueue(strategyPayload) : [];
  }, [strategyPayload]);

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
  const hybridFusionSupported = strategyPayload?.supported_outputs.includes("hybrid_fusion") ?? false;
  const hybridFusionObservationCandidateCount = hybridFusionPayload?.candidate_count ?? 0;
  const factorScreenObservationCandidateCount = factorScreenPayload?.candidate_count ?? 0;
  const reviewQueueUsesHybridFusion = hybridFusionSupported && (hybridFusionPayload?.items?.length ?? 0) > 0;
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

  function scrollToStockSection(targetId: string) {
    document.getElementById(targetId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const themeBreakoutCards = useMemo(
    () => (strategyPayload ? buildThemeBreakoutCards(strategyPayload) : []),
    [strategyPayload],
  );

  const themeLeaderPreviewItems = useMemo(
    () => buildThemeLeaderPreviewItems(themeBreakoutCards, 12),
    [themeBreakoutCards],
  );

  const sectorHeavyweightPreview = useMemo(
    () => (strategyPayload ? buildSectorHeavyweightPreview(strategyPayload) : null),
    [strategyPayload],
  );

  const sectorHeavyweightRows = sectorHeavyweightPreview?.rows.filter((row) => row.stocks.length > 0) ?? [];

  const themeEvidenceRows = useMemo(
    () => (strategyPayload ? buildThemeEvidenceStateRows(strategyPayload) : []),
    [strategyPayload],
  );

  const themeBreakoutReviewItems = useMemo(
    () => (strategyPayload ? buildThemeBreakoutReviewItems(strategyPayload) : []),
    [strategyPayload],
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
    sectorLinkSummary,
    sectorLinkFocus,
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
        const hasCompleteEvidence = card.boundaryEvidence.length === 0;
        return matchesSearch && (!completeEvidenceOnly || hasCompleteEvidence);
      }),
    [completeEvidenceOnly, filteredCandidates, normalizedQueueSearch],
  );
  const queueVisibleCount = queueVisibleCandidates.length;
  const queueTotalCount = reviewQueue.length;
  const queueFiltersActive =
    normalizedQueueSearch.length > 0 || completeEvidenceOnly || sectorFilterSectorCode !== null;
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

  const kpiStrip = useMemo(
    () =>
      strategyPayload ? buildStockAnalysisKpiStrip(strategyPayload, confluencePayload, closedLoopMeta) : [],
    [strategyPayload, confluencePayload, closedLoopMeta],
  );
  const decisionKpiStrip = kpiStrip.filter((item) =>
    ["market-state", "review-queue", "closed-loop", "data-boundary"].includes(item.key),
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

  const showStaleBanner = Boolean(
    strategyQuery.data?.result_meta &&
      (strategyQuery.data.result_meta.quality_flag !== "ok" ||
        strategyQuery.data.result_meta.vendor_status !== "ok" ||
        strategyQuery.data.result_meta.fallback_mode !== "none"),
  );

  const sectorViewOverview = useMemo(() => buildStockSectorOverviewState(sectorViewRows), [sectorViewRows]);
  const { topBars, bottomBars } = sectorViewOverview;
  const strongestSectorChip =
    sectorLeaderRow != null
      ? `最强 ${sectorLeaderRow.sectorName} (${sectorLeaderRow.pctChange})`
      : dailyJudgmentStrip?.strongestSectorChip ?? "强势待确认";
  const weakestSectorChip =
    sectorTailRow != null
      ? `最弱 ${sectorTailRow.sectorName} (${sectorTailRow.pctChange})`
      : dailyJudgmentStrip?.weakestSectorChip ?? "弱势待确认";
  const headerDateValue =
    strategyPayload?.as_of_date != null ? dayjs(strategyPayload.as_of_date) : null;

  const pickerDisplay =
    asOfOverride != null && asOfOverride.trim() !== "" ? dayjs(asOfOverride) : headerDateValue;

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
      analyticsAsOf && (strategyPrioritySection.seen || firstScreenAnalyticsRequested),
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
      analyticsAsOf && (strategyOptimizationSection.seen || firstScreenAnalyticsRequested),
    ),
    ...stockAnalysisReadQueryOptions,
  });
  const strategyOptimizationPayload = strategyOptimizationQuery.data?.result ?? null;
  const strategyOptimizationRows = useMemo(
    () => buildStrategyOptimizationRows(strategyOptimizationPayload),
    [strategyOptimizationPayload],
  );
  const strategyPriorityRows = strategyScorePayload?.current_market_state_rows ?? EMPTY_STRATEGY_PRIORITY_ROWS;
  const strategyBacktestSnapshotFrom = analyticsAsOf ? dayjs(analyticsAsOf).subtract(10, "day").format("YYYY-MM-DD") : null;

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
    enabled: Boolean(analyticsAsOf && (strategyBacktestSection.seen || firstScreenAnalyticsRequested)),
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
    enabled: Boolean(analyticsAsOf && cycleRotationFramework && cycleFrameworkSection.seen),
    ...stockAnalysisReadQueryOptions,
  });
  const cycleProxyBacktestPayload: LivermoreCycleProxyBacktestPayload | null =
    cycleProxyBacktestQuery.data?.result ?? null;
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
    enabled: Boolean(analyticsAsOf && cycleRotationFramework && cycleFrameworkSection.seen),
    ...stockAnalysisReadQueryOptions,
  });
  const candidateHistoryPortfolioBacktestPayload: LivermoreCandidateHistoryPortfolioBacktestPayload | null =
    candidateHistoryPortfolioBacktestQuery.data?.result ?? null;

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
          enabled: Boolean(strategyPayload?.as_of_date),
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
          enabled: Boolean(analyticsAsOf && (strategyPrioritySection.seen || firstScreenAnalyticsRequested)),
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
          enabled: Boolean(analyticsAsOf && (strategyBacktestSection.seen || firstScreenAnalyticsRequested)),
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
          enabled: Boolean(analyticsAsOf && (strategyOptimizationSection.seen || firstScreenAnalyticsRequested)),
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
          enabled: Boolean(analyticsAsOf && cycleRotationFramework && cycleFrameworkSection.seen),
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
          enabled: Boolean(analyticsAsOf && cycleRotationFramework && cycleFrameworkSection.seen),
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
    cycleRotationFramework,
    firstScreenAnalyticsRequested,
    sectorRankSeriesQuery.data,
    sectorRankSeriesQuery.isError,
    sectorRankSeriesQuery.isFetching,
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
        formalUseAllowed: strategyQuery.data?.result_meta?.formal_use_allowed ?? false,
        approvalStatus: "gap_or_observational",
      }),
    [
      endpointEvidenceItems,
      observationClosureReasonInputs,
      strategyQuery.data?.result_meta?.formal_use_allowed,
    ],
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
              enabled: Boolean(analyticsAsOf && cycleRotationFramework && cycleFrameworkSection.seen),
              isLoading: candidateHistoryPortfolioBacktestQuery.isLoading,
              isError: candidateHistoryPortfolioBacktestQuery.isError,
            }),
            proxyQueryState: resolvePanelQueryState({
              enabled: Boolean(analyticsAsOf && cycleRotationFramework && cycleFrameworkSection.seen),
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
      candidateHistoryPortfolioBacktestQuery.isLoading,
      candidateHistoryPortfolioBacktestQuery.isError,
      cycleProxyBacktestQuery.isLoading,
      cycleProxyBacktestQuery.isError,
    ],
  );

  const themeBreakoutPanelSummary = useMemo(
    () =>
      strategyPayload
        ? buildThemeBreakoutPanelSummary({
            payload: strategyPayload,
            cards: themeBreakoutCards,
            reviewCount: themeBreakoutReviewItems.length,
            unsupportedReason: themeBreakoutUnsupported?.reason,
          })
        : null,
    [strategyPayload, themeBreakoutCards, themeBreakoutReviewItems.length, themeBreakoutUnsupported?.reason],
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
          enabled: Boolean(analyticsAsOf && strategyPrioritySection.seen),
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
          enabled: Boolean(analyticsAsOf && strategyBacktestSection.seen),
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
          enabled: Boolean(analyticsAsOf && strategyOptimizationSection.seen),
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
  }, [gateState, themeBreakoutUnsupported?.reason, strategyPriorityRows]);

  const deepZoneAuditRows = useMemo(
    () =>
      buildDeepZoneAuditRows({
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
      }),
    [
      consensusReviewPanelSummary,
      consensusSummary.items.length,
      cycleRotationPanelSummary,
      eventMonitorRows.length,
      eventsMonitoringPanelSummary,
      marketPriorityPanelSummary,
      queueTotalCount,
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
  const stockWorkbenchStatus = {
    label: strategyQuery.isError
      ? "读取异常"
      : strategyQuery.isLoading
        ? "读取中"
        : showStaleBanner || boundaryRailIssueCount > 0
          ? "只读复核"
          : "只读观察",
    tone: strategyQuery.isError
      ? "error"
      : strategyQuery.isLoading
        ? "muted"
        : showStaleBanner || boundaryRailIssueCount > 0
          ? "watch"
          : "ok",
    detail: "A股观察证据仅用于复核，不生成交易指令",
  } as const;
  const resultMeta = strategyQuery.data?.result_meta;
  const sourceVersion = resultMeta?.source_version ?? "来源待返回";
  const sourceVersionSummary = sourceVersion.length > 36 ? "来源明细" : sourceVersion;
  const sourceGateTone = stockSourceGateTone({
    isError: strategyQuery.isError,
    isLoading: strategyQuery.isLoading,
    quality: resultMeta?.quality_flag,
    vendor: resultMeta?.vendor_status,
    fallback: resultMeta?.fallback_mode,
  });
  const sourceGateStatusLabel =
    sourceGateTone === "negative"
      ? "来源阻断"
      : sourceGateTone === "watch"
        ? "来源需复核"
        : sourceGateTone === "neutral"
          ? "数据读取中"
          : "来源已核验";
  const strategyBasisLabel = stockSupplyBasisLabel(strategyPayload?.basis ?? resultMeta?.basis);
  const sourceGateDetailLabel = `${sourceVersionSummary} · ${strategyBasisLabel} · 质量 ${stockSupplyQualityLabel(
    resultMeta?.quality_flag,
  )} · 通道 ${stockSupplyVendorLabel(resultMeta?.vendor_status)} · ${stockSupplyFallbackLabel(resultMeta?.fallback_mode)}`;
  const apiEvidenceItems = [
    {
      key: "tables",
      label: "后端表",
      value: resultMeta?.tables_used?.length ? `${resultMeta.tables_used.length} 张` : "待返回",
      detail: resultMeta?.tables_used?.slice(0, 4).join(" / ") ?? "后端表待返回",
    },
    {
      key: "evidence",
      label: "证据行",
      value:
        typeof resultMeta?.evidence_rows === "number"
          ? resultMeta.evidence_rows.toLocaleString("zh-CN")
          : "待返回",
      detail: "接口元信息记录的证据行数",
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
      detail = `持仓 ${formatApiCount(strategyPayload?.risk_exit?.position_count)} · ${asOfDetail}`;
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
  const apiSupportedOutputs = strategyPayload?.supported_outputs ?? [];
  const supportedOutputsLabel =
    apiSupportedOutputs.length > 0
      ? apiSupportedOutputs.slice(0, 3).map(supportedOutputLabel).join(" / ")
      : "待返回";
  const primaryGapLabel =
    strategyPayload?.data_gaps
      ?.filter((gap) => gap.status !== "ready")
      .map((gap) => dataGapFamilyLabel(gap.input_family))
      .slice(0, 3)
      .join(" / ") || "无新增缺口";
  const backendTableCount = resultMeta?.tables_used?.length ?? 0;
  const dataGapCount = strategyPayload?.data_gaps?.filter((gap) => gap.status !== "ready").length ?? 0;
  const supportedOutputCount = apiSupportedOutputs.length;
  const unsupportedOutputCount = activeUnsupportedOutputCount(strategyPayload) ?? 0;
  const queueLeadCandidate = queueVisibleCandidates[0] ?? null;
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
  const queueGateLabel = backendSupplyOverview?.gateLabel ?? decisionSummary?.gateLabel ?? "门控待确认";
  const queueGateStatusLabel = queueGateLabel.startsWith("门控") ? queueGateLabel : `门控 ${queueGateLabel}`;
  const observationClosureIssueCount = observationClosureSummary.unresolvedReasons.length;
  const observationClosureLabel = observationClosureIssueCount > 0 ? "待复核" : "只读";
  const observationClosureDetail =
    observationClosureIssueCount > 0 ? `${observationClosureIssueCount} 项待复核` : "无新增待复核项";
  const observationClosureTone = observationClosureIssueCount > 0 ? "warning" : "positive";
  const queueLoopStatusLabel = `闭环${observationClosureLabel}`;
  const queueDataStatusLabel = strategyQuery.isError
    ? "数据异常"
    : strategyQuery.isLoading
      ? "数据读取中"
      : "数据已更新";
  const gateDecisionTone = stockGateDecisionTone(currentMarketState, boundaryRailIssueCount > 0);
  const gateContextTone = stockGateContextTone(gateDecisionTone);
  const apiLedgerMetrics = [
    {
      label: "候选",
      value: `${queueVisibleCount}/${queueTotalCount}`,
      detail: `${queueVisibleCount}只候选进入只读复核队列`,
    },
    { label: "暴露", value: decisionSummary?.exposureLabel ?? "待确认" },
    {
      label: "条件",
      value: backendSupplyOverview?.conditionLabel ?? marketState?.passedLabel ?? "待确认",
      detail: `${backendSupplyOverview?.readinessLabel ?? "就绪待确认"} · ${
        backendSupplyOverview?.supportedLabel ?? `可用 ${supportedOutputCount}`
      } · ${backendSupplyOverview?.unsupportedLabel ?? `阻断 ${unsupportedOutputCount}`}`,
    },
  ];
  const apiLedgerConditionCells: StockAnalysisLedgerCell[] = [
    {
      key: "gate",
      label: "门控",
      value: backendSupplyOverview?.gateLabel ?? decisionSummary?.gateLabel ?? "待确认",
      detail: dailyJudgmentStrip?.gateChip ?? "门控待确认",
      tone: gateContextTone,
    },
    {
      key: "conditions",
      label: "已通过条件",
      value: backendSupplyOverview?.conditionLabel ?? marketState?.passedLabel ?? "待确认",
      detail: `可用条件 ${strategyPayload?.market_gate.available_conditions ?? "待确认"}`,
      tone: gateDecisionTone,
    },
    {
      key: "outputs",
      label: "支持输出",
      value: `${supportedOutputCount}`,
      detail: supportedOutputsLabel,
      tone: supportedOutputCount > 0 ? "positive" : "warning",
    },
    {
      key: "inputs",
      label: "缺口",
      value: `${dataGapCount}`,
      detail: primaryGapLabel,
      tone: dataGapCount > 0 ? "warning" : "positive",
    },
    {
      key: "risk",
      label: "风险退出",
      value: riskExitUnsupported ? "阻断" : riskTriggeredCount > 0 ? `触发 ${riskTriggeredCount}` : "未触发",
      detail: riskExitUnsupported ? "持仓等缺失" : riskWatchCount > 0 ? `观察 ${riskWatchCount}` : "边界待确认",
      tone: riskExitUnsupported || riskTriggeredCount > 0 ? "negative" : riskWatchCount > 0 ? "warning" : "positive",
    },
    {
      key: "evidence",
      label: "证据行",
      value:
        typeof resultMeta?.evidence_rows === "number"
          ? resultMeta.evidence_rows.toLocaleString("zh-CN")
          : "待返回",
      detail: "接口元信息记录的证据行数",
      tone: "neutral",
    },
  ];
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
  const apiLedgerRailRows = [
    {
      label: "结论",
      value: `${stockWorkbenchStatus.label}，${queueGateStatusLabel}`,
    },
    {
      label: "关键证据",
      value: `证据 ${queueLeadEvidenceCount}，边界缺口 ${queueLeadBoundaryCount}`,
    },
    {
      label: "可用输出",
      value: supportedOutputsLabel,
    },
    {
      label: "主要缺口",
      value: primaryGapLabel,
    },
    {
      label: "下一步",
      value: queueNextActionLabel,
      detail: riskExitUnsupported ? "风险退出阻断" : queueNextActionFullLabel,
    },
  ];
  const apiDecisionSupplementItems = [
    {
      label: "队列",
      value: "今日复核队列",
      detail: `${queueVisibleCount}/${queueTotalCount}`,
    },
    {
      label: "首位",
      value: queueLeadCandidate?.stockName ?? "待补",
      detail: `${queueVisibleCount}/${queueTotalCount} · ${queueVisibleCount}只候选进入只读复核队列`,
    },
    {
      label: "供数",
      value: backendSupplyOverview?.readinessLabel ?? "就绪待确认",
      detail: `${backendSupplyOverview?.supportedLabel ?? `可用 ${supportedOutputCount}`} · ${
        backendSupplyOverview?.unsupportedLabel ?? `阻断 ${unsupportedOutputCount}`
      }`,
    },
    {
      label: "边界",
      value: backendSupplyOverview?.dataGapLabel ?? `缺口 ${dataGapCount}`,
      detail: primaryGapLabel,
    },
    {
      label: "闭环",
      value: "供数闭环",
      detail: observationClosureLabel,
    },
  ];
  const apiSupplyStatusRows = [
    ...(backendSupplyOverview?.readinessRows ?? []).map((item) => ({
      key: item.key,
      label: cycleInputLabel(item.key) || item.title,
      value: statusLabel(item.status),
      tone: readinessTone(item.status),
    })),
    ...(backendSupplyOverview?.dataGapRows ?? [])
      .filter((item) => dataGapFamilyLabel(item.input_family) !== "输入待确认")
      .slice(0, 3)
      .map((item) => ({
        key: `gap:${item.input_family}`,
        label: dataGapFamilyLabel(item.input_family),
        value: statusLabel(item.status),
        tone: gapTone(item.status),
      })),
  ];
  const queueReportHeadline = queueLeadCandidate
    ? `${queueGateStatusLabel}下的 ${queueVisibleCount} 个观察候选；风险退出${riskExitUnsupported ? "仍为阻断" : "未触发"}。`
    : queueFiltersActive && queueTotalCount > 0
      ? "筛选后暂无候选；请调整行业、搜索或证据条件。"
      : "复核队列暂无候选；等待证据闭环。";
  const queueReportLead = queueFiltersActive
    ? `当前显示 ${queueVisibleCount} / ${queueTotalCount} 个候选；排名、证据、边界和复核入口集中在同一张表内。`
    : "候选来自融合观察与多因子观察池；当前页面只做复核与证据追踪，不表达交易建议。";
  const decisionMemoTiles = [
    {
      key: "gate",
      testId: "stock-analysis-decision-gate-tile",
      icon: <SafetyCertificateOutlined />,
      label: "门控",
      value: backendSupplyOverview?.gateLabel ?? decisionSummary?.gateLabel ?? "待确认",
      detail: backendSupplyOverview?.conditionLabel ?? marketState?.passedLabel ?? "条件待确认",
      tone: gateDecisionTone,
    },
    {
      key: "closed-loop",
      testId: "stock-analysis-decision-closed-loop-tile",
      icon: <ClockCircleOutlined />,
      label: "闭环",
      value: observationClosureLabel,
      detail: observationClosureDetail,
      tone: observationClosureTone,
    },
    {
      key: "boundary",
      testId: "stock-analysis-decision-boundary-tile",
      icon: <DatabaseOutlined />,
      label: "边界",
      value: backendSupplyOverview?.dataGapLabel ?? decisionSummary?.boundaryLabel ?? "待确认",
      detail: boundaryRailIssueCount > 0 ? `${boundaryRailIssueCount} 条证据提示` : "无新增提示",
      tone: boundaryRailIssueCount > 0 ? "watch" : "ok",
    },
    {
      key: "risk",
      testId: "stock-analysis-decision-risk-tile",
      icon: <FireOutlined />,
      label: "风险",
      value:
        riskTriggeredCount > 0
          ? `触发 ${riskTriggeredCount}`
          : riskWatchCount > 0
            ? `观察 ${riskWatchCount}`
            : "未触发",
      detail: queueNextActionLabel,
      tone: riskTriggeredCount > 0 ? "negative" : riskWatchCount > 0 ? "watch" : "ok",
    },
  ];
  const marketContextItems = [
    {
      key: "gate",
      icon: <SafetyCertificateOutlined />,
      label: "门控",
      value: queueGateStatusLabel,
      detail: backendSupplyOverview?.conditionLabel ?? marketState?.passedLabel ?? "门控待确认",
      tone: gateContextTone,
    },
    {
      key: "exposure",
      icon: <LineChartOutlined />,
      label: "观察暴露",
      value: decisionSummary?.exposureLabel ?? "暴露待确认",
      detail: dailyJudgmentStrip?.exposureChip ?? "观察待确认",
      tone: "neutral",
    },
    {
      key: "strong-sector",
      icon: <BarChartOutlined />,
      label: "强势板块",
      value: strongestSectorChip,
      detail: topBars[0] ? `${topBars[0].sectorName} · ${topBars[0].pctChange}` : "板块待确认",
      tone: "positive",
    },
    {
      key: "weak-sector",
      icon: <BarChartOutlined />,
      label: "弱势板块",
      value: weakestSectorChip,
      detail: bottomBars[0] ? `${bottomBars[0].sectorName} · ${bottomBars[0].pctChange}` : "板块待确认",
      tone: "watch",
    },
    {
      key: "confluence",
      icon: <ThunderboltOutlined />,
      label: "策略共振",
      value: `${consensusHitCount}`,
      detail: `去重 ${consensusSummary.totalUnion}`,
      tone: consensusHitCount > 0 ? "positive" : "neutral",
    },
    {
      key: "risk",
      icon: <FireOutlined />,
      label: "风险退出",
      value:
        riskTriggeredCount > 0
          ? `触发 ${riskTriggeredCount}`
          : riskWatchCount > 0
            ? `观察 ${riskWatchCount}`
            : "未触发",
      detail: `边界 ${boundaryRailIssueCount}`,
      tone: riskTriggeredCount > 0 ? "negative" : riskWatchCount > 0 || boundaryRailIssueCount > 0 ? "watch" : "positive",
    },
  ];
  const stockWorkbenchMetaItems = [
    { label: "日期", value: backendSupplyOverview?.asOfLabel ?? analyticsAsOf ?? "待返回" },
    {
      label: "来源",
      value: sourceVersionSummary,
      hint: sourceVersion.length > 36 ? sourceVersion : undefined,
    },
    { label: "口径", value: strategyQuery.data?.result_meta?.basis ?? "analytical" },
  ];
  const stockWorkbenchToolbarActions = (
    <StockAnalysisWorkbenchActions
      pickerDisplay={pickerDisplay}
      queueSearchText={queueSearchText}
      dataStatusLabel={queueDataStatusLabel}
      dataStatusTone={strategyQuery.isError ? "negative" : strategyQuery.isLoading ? "neutral" : "positive"}
      gateStatusLabel={queueGateStatusLabel}
      gateStatusTone={boundaryRailIssueCount > 0 ? "warning" : "positive"}
      loopStatusLabel={queueLoopStatusLabel}
      loopStatusTone={observationClosureTone}
      completeEvidenceOnly={completeEvidenceOnly}
      agentDrawerOpen={agentDrawerOpen}
      generatedAt={strategyQuery.data?.result_meta?.generated_at}
      onAsOfOverrideChange={setAsOfOverride}
      onQueueSearchTextChange={setQueueSearchText}
      onCompleteEvidenceOnlyChange={setCompleteEvidenceOnly}
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
      title="股票分析"
      question="A股观察证据今天支持哪些只读复核结论？"
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
        className={`${SA_SHELL_PAGE} stock-analysis-page stock-analysis-page--market-shell`}
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
          <StockAnalysisErrorWorkbench message={errorMessage(strategyQuery.error)} />
        ) : null}

        {marketState ? (
          <>
            {decisionSummary && dailyJudgmentStrip ? (
              <div
                className={`${SA_SHELL_LAYOUT} stock-analysis-page__first-screen stock-analysis-page__uses-home-shell`}
                data-testid="stock-analysis-first-screen-workbench"
                data-design-target="product-design-option-1"
              >
                <main
                  className={`${SA_SHELL_MAIN} stock-analysis-page__first-screen-main`}
                  data-testid="stock-analysis-first-screen-main"
                >
                {showStaleBanner ? (
                  <div
                    className="stock-analysis-page__stale-banner stock-analysis-page__stale-banner--compressed"
                    data-testid="stock-analysis-stale-banner"
                    role="status"
                  >
                    数据陈旧、供数异常或使用回退快照。下方结论仅供复核参考。
                  </div>
                ) : null}
                <StockAnalysisReviewLedgerFirstScreen
                  asOfLabel={decisionSummary?.asOfLabel ?? "待确认"}
                  requestedAsOfLabel={backendSupplyOverview?.requestedAsOfLabel}
                  kicker="今日复核队列"
                  headline={queueReportHeadline}
                  lead={queueReportLead}
                  metrics={apiLedgerMetrics}
                  conditionCells={apiLedgerConditionCells}
                  sourceCells={apiLedgerSourceCells}
                  railRows={apiLedgerRailRows}
                  pagePurposeText={
                    pagePurpose
                      ? `${pagePurpose.eyebrow} ${pagePurpose.title} ${pagePurpose.asOfLine} ${pagePurpose.dataStatusLine}`
                      : undefined
                  }
                  supplementItems={apiDecisionSupplementItems}
                  decisionMemoTiles={decisionMemoTiles}
                  supplyStatusRows={apiSupplyStatusRows}
                  sourceGateTone={sourceGateTone}
                  sourceGateLabel={sourceGateStatusLabel}
                  sourceGateDetail={sourceGateDetailLabel}
                  sourceVersion={sourceVersion}
                  digest={workbenchDigest}
                  onFactSelect={handleWorkbenchFactSelect}
                  activeFactId={activeWorkbenchFactId}
                  factControlsId={STOCK_ANALYSIS_ENDPOINT_EVIDENCE_RAIL_ID}
                  closureSummary={observationClosureSummary}
                  railContent={
                    <StockAnalysisEvidenceLedgerRail
                      asOfLabel={decisionSummary?.asOfLabel ?? analyticsAsOf ?? "—"}
                      statusLabel={stockWorkbenchStatus.label}
                      gateStatusLabel={queueGateStatusLabel}
                      evidenceCount={queueLeadEvidenceCount}
                      boundaryCount={queueLeadBoundaryCount}
                      availableOutputsLabel={supportedOutputsLabel}
                      primaryGapLabel={primaryGapLabel}
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
                    />
                  }
                />
                {false ? (() => {
                  if (
                    !pagePurpose ||
                    !decisionSummary ||
                    !backendSupplyOverview ||
                    !dailyJudgmentStrip ||
                    !marketState ||
                    !closedLoopSummary
                  ) {
                    return null;
                  }

                  return (
                <section
                  data-testid="stock-analysis-tailwind-cockpit"
                  className={SA_FIRST_HERO}
                  aria-label="策略复核决策"
                >
                  {pagePurpose ? (
                    <div
                      className="stock-analysis-page__dh-purpose"
                      data-testid="stock-analysis-page-purpose"
                    >
                      <div className="stock-analysis-page__dh-purpose-main">
                        <span className="stock-analysis-page__dh-purpose-eyebrow">{pagePurpose!.eyebrow}</span>
                        <h2 className="stock-analysis-page__dh-purpose-title">{pagePurpose!.title}</h2>
                      </div>
                      <div className="stock-analysis-page__dh-purpose-status" aria-label="页面状态">
                        <span>{pagePurpose!.asOfLine}</span>
                        <span>{pagePurpose!.dataStatusLine}</span>
                      </div>
                    </div>
                  ) : null}

                  <div className="stock-analysis-page__dh-hero-panel" data-testid="stock-analysis-decision-panel">
                    <div
                      className="stock-analysis-page__queue-report-head"
                      data-testid="stock-analysis-queue-report-head"
                    >
                      <div className="stock-analysis-page__queue-report-copy">
                        <span className="stock-analysis-page__queue-report-kicker">今日复核队列</span>
                        <strong className="stock-analysis-page__queue-report-title">{queueReportHeadline}</strong>
                        <p>{queueReportLead}</p>
                      </div>
                      <dl className="stock-analysis-page__queue-report-meta">
                        <div>
                          <dt>候选</dt>
                          <dd className="stock-analysis-page__tabular">
                            {queueVisibleCount}/{queueTotalCount}
                          </dd>
                        </div>
                        <div>
                          <dt>证据数</dt>
                          <dd className="stock-analysis-page__tabular">{queueLeadEvidenceCount}</dd>
                        </div>
                        <div>
                          <dt>边界缺口</dt>
                          <dd className="stock-analysis-page__tabular">{queueLeadBoundaryCount}</dd>
                        </div>
                      </dl>
                    </div>
                    <div
                      className="stock-analysis-page__market-context-strip"
                      data-testid="stock-analysis-market-context-strip"
                      aria-label="市场复核信号"
                    >
                      {marketContextItems.map((item) => (
                        <div
                          key={item.key}
                          data-tone={item.tone}
                          data-testid={`stock-analysis-market-context-${item.key}`}
                          title={`${item.label}: ${item.value} / ${item.detail}`}
                        >
                          <StatusIcon>{item.icon}</StatusIcon>
                          <span>{item.label}</span>
                          <strong>{item.value}</strong>
                          <small>{item.detail}</small>
                        </div>
                      ))}
                    </div>
                    <div
                      className="stock-analysis-page__source-gate-strip"
                      data-tone={sourceGateTone}
                      data-testid="stock-analysis-source-gate-strip"
                      title={sourceVersion}
                    >
                      <span>来源核验</span>
                      <strong>{sourceGateStatusLabel}</strong>
                      <small>{sourceGateDetailLabel}</small>
                    </div>
                    <div
                      className="stock-analysis-page__api-evidence-strip"
                      data-testid="stock-analysis-api-evidence-strip"
                      aria-label="真实后端 API 证据"
                    >
                      {apiEvidenceItems.map((item) => (
                        <div key={item.key} title={`${item.label}: ${item.detail}`}>
                          <span>{item.label}</span>
                          <strong>{item.value}</strong>
                          <small>{item.detail}</small>
                        </div>
                      ))}
                    </div>
                    <div className="stock-analysis-page__dh-hero-row">
                      <div className="stock-analysis-page__dh-hero-main">
                        <div className="stock-analysis-page__dh-hero-meta-row">
                          <span className="stock-analysis-page__dh-chip">只读复核</span>
                          <span className="stock-analysis-page__dh-hero-meta">
                            观察日{" "}
                            <strong className="stock-analysis-page__tabular">
                              {decisionSummary!.asOfLabel}
                            </strong>
                          </span>
                          {backendSupplyOverview ? (
                            <span className="stock-analysis-page__dh-hero-meta">
                              数据日 {backendSupplyOverview!.asOfLabel}
                            </span>
                          ) : null}
                        </div>
                        <h1 className="stock-analysis-page__dh-hero-title">
                          {backendSupplyOverview?.gateLabel ??
                            `门控 ${localizeMarketDataStatus(strategyPayload?.market_gate.state)}`}
                          {" · "}
                          {decisionSummary!.exposureLabel}
                        </h1>
                        <div
                          className="stock-analysis-page__dh-hero-actions"
                          aria-label="下一步复核状态"
                          title={queueNextReviewAction}
                        >
                          {queueLeadCandidate ? (
                            <>
                              <span className="stock-analysis-page__dh-hero-chip">
                                <StockOutlined aria-hidden="true" /> 下一步 {queueLeadCandidate.stockName}
                              </span>
                              <span className="stock-analysis-page__dh-hero-chip">
                                <BarChartOutlined aria-hidden="true" /> 距观察 {queueLeadCandidate.distanceToBreakoutPct}
                              </span>
                            </>
                          ) : (
                            <>
                              <span className="stock-analysis-page__dh-hero-chip stock-analysis-page__dh-hero-chip--warn">
                                <StockOutlined aria-hidden="true" /> 复核 {queueVisibleCount}
                              </span>
                              <span className="stock-analysis-page__dh-hero-chip">
                                <DatabaseOutlined aria-hidden="true" /> 多因子 {primaryFactorScreenCandidateCount}
                              </span>
                              <span className="stock-analysis-page__dh-hero-chip">
                                <ThunderboltOutlined aria-hidden="true" /> 共振 {consensusHitCount}
                              </span>
                            </>
                          )}
                        </div>
                        <div className="stock-analysis-page__dh-hero-status-strip" aria-label="市场门控状态">
                          {[
                            dailyJudgmentStrip!.gateChip,
                            dailyJudgmentStrip!.exposureChip,
                            strongestSectorChip,
                            weakestSectorChip,
                            decisionSummary!.dataFreshnessLabel,
                            decisionSummary!.boundaryLabel,
                          ].map((label) => (
                            <span key={label}>{label}</span>
                          ))}
                        </div>
                      </div>
                      <aside className="stock-analysis-page__dh-hero-side" aria-label="首屏状态摘要">
                        <span>
                          <SafetyCertificateOutlined aria-hidden="true" />
                          <small>门控</small>
                          <strong>{backendSupplyOverview?.conditionLabel ?? marketState!.passedLabel}</strong>
                        </span>
                        <span>
                          <DatabaseOutlined aria-hidden="true" />
                          <small>边界</small>
                          <strong>{backendSupplyOverview?.dataGapLabel ?? decisionSummary!.boundaryLabel}</strong>
                        </span>
                        <span>
                          <LineChartOutlined aria-hidden="true" />
                          <small>下一步</small>
                          <strong>{queueLeadCandidate?.stockName ?? "复核队列"}</strong>
                        </span>
                      </aside>
                    </div>

                    <div
                      className="stock-analysis-page__decision-memo"
                      data-testid="stock-analysis-decision-memo"
                      aria-label="只读复核决策备忘"
                    >
                      <div className="stock-analysis-page__decision-memo-copy">
                        <span>Decision Memo</span>
                        <strong>{stockWorkbenchStatus.label}</strong>
                        <small title={queueNextReviewAction}>
                          {queueNextReviewAction}
                        </small>
                      </div>
                      <div
                        className="stock-analysis-page__decision-memo-grid"
                        data-testid="stock-analysis-decision-memo-status-grid"
                      >
                        {decisionMemoTiles.map((tile) => (
                          <div
                            key={tile.key}
                            className="stock-analysis-page__decision-memo-tile"
                            data-tone={tile.tone}
                            data-testid={tile.testId}
                            title={`${tile.label}: ${tile.value} / ${tile.detail}`}
                          >
                            <StatusIcon>{tile.icon}</StatusIcon>
                            <span>{tile.label}</span>
                            <strong>{tile.value}</strong>
                            <small>{tile.detail}</small>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="stock-analysis-page__visually-hidden" aria-hidden="true">
                      {backendSupplyOverview
                        ? [
                            backendSupplyOverview!.gateLabel,
                            backendSupplyOverview!.exposureLabel,
                            backendSupplyOverview!.readinessLabel,
                            backendSupplyOverview!.dataGapLabel,
                            backendSupplyOverview!.supportedLabel,
                            backendSupplyOverview!.unsupportedLabel,
                            backendSupplyOverview!.qualityLabel,
                          ].join(" ")
                        : null}
                    </div>


                    <div
                      className="stock-analysis-page__supply-audit-summary"
                      data-testid="stock-analysis-supply-audit-summary"
                    >
                      <div className="stock-analysis-page__supply-audit-summary-head">
                        <span>供数闭环</span>
                        {closedLoopSummary ? (
                          <strong className="stock-analysis-page__dh-pill">
                            {closedLoopSummary!.referenceRating.label}
                          </strong>
                        ) : null}
                      </div>
                      {backendSupplyOverview ? (
                        <DataStatusStrip
                          testId="stock-analysis-backend-supply-status"
                          className="stock-analysis-page__readiness-strip"
                        >
                          <div className="stock-analysis-page__readiness-strip-head">
                            <h3 className="stock-analysis-page__readiness-strip-title">规则就绪</h3>
                            <span className="stock-analysis-page__signal-pill stock-analysis-page__signal-pill--accent">
                              只读
                            </span>
                          </div>
                          <div className="stock-analysis-page__readiness-rows">
                            {backendSupplyOverview!.readinessRows.map((item) => (
                              <div
                                className="stock-analysis-page__readiness-row"
                                data-tone={readinessTone(item.status)}
                                key={item.key}
                              >
                                <span className="stock-analysis-page__readiness-row-label">
                                  <StatusIcon tone={readinessTone(item.status)}>
                                    <SafetyCertificateOutlined />
                                  </StatusIcon>
                                  {cycleInputLabel(item.key) || item.title}
                                </span>
                                <strong className="stock-analysis-page__readiness-row-value">
                                  {statusLabel(item.status)}
                                </strong>
                              </div>
                            ))}
                            {backendSupplyOverview!.dataGapRows.slice(0, 3).map((item) => (
                              <div
                                className="stock-analysis-page__readiness-row"
                                data-tone={gapTone(item.status)}
                                key={`gap:${item.input_family}`}
                              >
                                <span className="stock-analysis-page__readiness-row-label">
                                  <StatusIcon tone={gapTone(item.status)}>
                                    <DatabaseOutlined />
                                  </StatusIcon>
                                  {dataGapFamilyLabel(item.input_family)}
                                </span>
                                <strong className="stock-analysis-page__readiness-row-value">
                                  {statusLabel(item.status)}
                                </strong>
                              </div>
                            ))}
                          </div>
                        </DataStatusStrip>
                      ) : null}
                      <div className="stock-analysis-page__supply-meta-grid">
                        <div
                          className="stock-analysis-page__supply-meta-cell"
                          title={`数据日期 ${backendSupplyOverview?.asOfLabel ?? decisionSummary!.asOfLabel}`}
                        >
                          <StatusIcon>{DECISION_GRID_ICONS[0]}</StatusIcon>
                          <span className="stock-analysis-page__supply-meta-label">数据日期</span>
                          <strong className="stock-analysis-page__tabular stock-analysis-page__supply-meta-value">
                            {backendSupplyOverview?.asOfLabel ?? decisionSummary!.asOfLabel}
                          </strong>
                        </div>
                        <div
                          className="stock-analysis-page__supply-meta-cell"
                          title={`口径 ${backendSupplyOverview?.basisLabel ?? decisionSummary!.basisLabel}`}
                        >
                          <StatusIcon>{DECISION_GRID_ICONS[1]}</StatusIcon>
                          <span className="stock-analysis-page__supply-meta-label">口径</span>
                          <strong className="stock-analysis-page__supply-meta-value stock-analysis-page__supply-meta-value--break">
                            {backendSupplyOverview?.basisLabel ?? decisionSummary!.basisLabel}
                          </strong>
                        </div>
                        <div
                          className="stock-analysis-page__supply-meta-cell"
                          title={`请求日期 ${backendSupplyOverview?.requestedAsOfLabel ?? "默认"}`}
                        >
                          <StatusIcon>{DECISION_GRID_ICONS[2]}</StatusIcon>
                          <span className="stock-analysis-page__supply-meta-label">请求日期</span>
                          <strong className="stock-analysis-page__supply-meta-value">
                            {backendSupplyOverview?.requestedAsOfLabel ?? "默认"}
                          </strong>
                        </div>
                        <div
                          className="stock-analysis-page__supply-meta-cell"
                          title={`门控确认 ${backendSupplyOverview?.conditionLabel ?? marketState!.passedLabel}`}
                        >
                          <StatusIcon>{DECISION_GRID_ICONS[3]}</StatusIcon>
                          <span className="stock-analysis-page__supply-meta-label">门控确认</span>
                          <strong className="stock-analysis-page__supply-meta-value stock-analysis-page__supply-meta-value--break">
                            {backendSupplyOverview?.conditionLabel ?? marketState!.passedLabel}
                          </strong>
                        </div>
                      </div>
                    </div>
                  </div>
                </section>
                  );
                })() : null}

                {false && decisionKpiStrip.length > 0 ? (
                  <section data-testid="stock-analysis-kpi-section" aria-label="选股快照">
                    <p className="stock-analysis-page__visually-hidden">选股快照</p>
                    <div
                      className="stock-analysis-page__dh-kpi-strip"
                      data-testid="stock-analysis-kpi-strip"
                    >
                    {decisionKpiStrip.map((item) => (
                      <EquityKpiCard
                        key={item.key}
                        kpiKey={item.key}
                        label={item.label}
                        value={item.value}
                        deltaText={item.detail}
                        deltaTone={kpiToneToDelta(item.tone)}
                        gaugeValue={item.gaugeValue}
                        testId={`stock-analysis-kpi-${item.key}`}
                      />
                    ))}
                    </div>
                  </section>
                ) : null}

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
                    <p className={SA_SECTION_EYEBROW}>今日待复核</p>
                    <h2 className={SA_CARD_TITLE}>复核队列</h2>
                    <p className={SA_SECTION_DESC}>
                      {reviewQueueUsesHybridFusion ? "融合优先 · 边界复核" : "候选排序 · 边界复核"}
                    </p>
                  </div>
                  <span className={SA_PILL}>
                    {reviewQueueUsesHybridFusion ? "融合策略 / 复核队列" : "候选 / 复核队列"}
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
                  <CompactStatusTile
                    icon={<BarChartOutlined />}
                    label="行业筛选"
                    value="0 候选"
                    tone="warning"
                    testId="stock-analysis-review-queue-filter-empty"
                  />
                ) : (
                  <>
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
                  {false ? (
                  <div className="stock-analysis-page__review-table-wrap">
                    <table
                      className="stock-analysis-page__table stock-analysis-page__review-queue-table"
                      data-testid="stock-analysis-review-queue-table"
                    >
                      <thead>
                        <tr>
                          <th scope="col">排名</th>
                          <th scope="col">股票</th>
                          <th scope="col">行业</th>
                          {reviewQueueUsesHybridFusion ? (
                            <>
                              <th scope="col">Fusion</th>
                              <th scope="col">Cycle</th>
                              <th scope="col">Lifecourt</th>
                              <th scope="col">Confidence</th>
                              <th scope="col">Action</th>
                            </>
                          ) : (
                            <>
                              <th scope="col">形态</th>
                              <th scope="col">距观察</th>
                              <th scope="col">证据</th>
                              <th scope="col">边界</th>
                              <th scope="col">失效</th>
                            </>
                          )}
                          <th scope="col">复核</th>
                        </tr>
                      </thead>
                      <tbody>
                        {queueVisibleCandidates.map((card) => {
                          const evidenceCount = card.primaryEvidence.length + card.supportingEvidence.length;
                          const rowStatus =
                            card.boundaryEvidence.length > 0
                              ? { label: "边界待补", tone: "warning" as const }
                              : evidenceCount >= 3
                                ? { label: "可复核", tone: "positive" as const }
                                : evidenceCount > 0
                                  ? { label: "证据不全", tone: "warning" as const }
                                  : { label: "待补", tone: "neutral" as const };
                          const fusionScore = reviewQueueUsesHybridFusion
                            ? candidateEvidenceValue(card, "fusion_score")
                            : null;
                          const cycleScore = reviewQueueUsesHybridFusion
                            ? candidateEvidenceValue(card, "cycle_score")
                            : null;
                          const lifecourtScore = reviewQueueUsesHybridFusion
                            ? candidateEvidenceValue(card, "lifecourt_proxy_score")
                            : null;
                          const confidenceLabel = reviewQueueUsesHybridFusion
                            ? candidateEvidenceValue(card, "confidence")
                            : null;
                          const fusionAction = reviewQueueUsesHybridFusion
                            ? candidateEvidenceValue(card, "fusion_action")
                            : null;
                          const primaryEvidencePreview = card.primaryEvidence[0] ?? card.supportingEvidence[0];
                          const openReviewDetail = () => {
                            const ranks = lookupStockStrategyRanks(strategyPayload ?? null, card.stockCode);
                            setDetailSelection(
                              buildReviewQueueDetailSelection({
                                card,
                                ranks,
                                reviewQueueUsesHybridFusion,
                              }),
                            );
                          };

                          return (
                            <tr
                              key={card.stockCode}
                              className="stock-analysis-page__review-candidate-card"
                              data-testid={`stock-candidate-${card.stockCode}`}
                              data-selected-sector={
                                sectorFilterSectorCode != null && card.sectorCode === sectorFilterSectorCode
                                  ? "true"
                                  : undefined
                              }
                            >
                              <td className="stock-analysis-page__table-number">#{card.rank}</td>
                              <td>
                                <strong>{card.stockName}</strong>
                                <small className="stock-analysis-page__tabular">{card.stockCode}</small>
                              </td>
                              <td>
                                <strong>{card.sectorName}</strong>
                                <small className="stock-analysis-page__tabular">{card.sectorCode}</small>
                              </td>
                              {reviewQueueUsesHybridFusion ? (
                                <>
                                  <td data-mobile-label="Fusion">
                                    <strong className="stock-analysis-page__tabular">{fusionScore}</strong>
                                    <small title={card.headline}>{compactText(card.headline, 28)}</small>
                                  </td>
                                  <td data-mobile-label="Cycle">
                                    <strong className="stock-analysis-page__tabular">{cycleScore}</strong>
                                    <small>{evidenceCount} 证据</small>
                                  </td>
                                  <td data-mobile-label="Lifecourt">
                                    <strong className="stock-analysis-page__tabular">{lifecourtScore}</strong>
                                    <small>边界 {card.boundaryEvidence.length}</small>
                                  </td>
                                  <td data-mobile-label="Confidence">
                                    <span
                                      className="stock-analysis-page__review-row-status"
                                      data-tone={confidenceTone(confidenceLabel ?? "待补")}
                                      title={confidenceLabel ?? "待补"}
                                    >
                                      {confidenceLabel ?? "待补"}
                                    </span>
                                  </td>
                                  <td data-mobile-label="Action">
                                    <strong>{fusionAction}</strong>
                                    <small title={card.invalidationFocus}>{compactText(card.invalidationFocus, 24)}</small>
                                  </td>
                                </>
                              ) : (
                                <>
                                  <td data-mobile-label="形态">
                                    <strong>{card.pattern}</strong>
                                    <small title={card.patternNote}>{compactText(card.patternNote, 28)}</small>
                                  </td>
                                  <td data-mobile-label="距观察">
                                    <strong className="stock-analysis-page__tabular">{card.distanceToBreakoutPct}</strong>
                                    <small title={card.headline}>{compactText(card.headline, 28)}</small>
                                  </td>
                                  <td data-mobile-label="证据">
                                    <strong>{evidenceCount} 证据</strong>
                                    <small title={primaryEvidencePreview?.value}>
                                      {primaryEvidencePreview
                                        ? `${primaryEvidencePreview.label}：${compactText(primaryEvidencePreview.value, 24)}`
                                        : "证据待补"}
                                    </small>
                                  </td>
                                  <td data-mobile-label="边界">
                                    <span className="stock-analysis-page__review-row-status" data-tone={rowStatus.tone}>
                                      {card.boundaryEvidence.length > 0 ? `边界 ${card.boundaryEvidence.length}` : "边界清洁"}
                                    </span>
                                  </td>
                                  <td data-mobile-label="失效">
                                    <strong>失效</strong>
                                    <small title={card.invalidationFocus}>{compactText(card.invalidationFocus, 24)}</small>
                                  </td>
                                </>
                              )}
                              <td>
                                <Button
                                  type="default"
                                  size="small"
                                  icon={<LineChartOutlined />}
                                  data-testid={`stock-candidate-review-chart-${card.stockCode}`}
                                  onClick={openReviewDetail}
                                  aria-label={`复核 ${card.stockName} K 线`}
                                >
                                  <span className="sr-only">复核 </span>K 线
                                </Button>
                                <small title={rowStatus.label}>{rowStatus.label}</small>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  ) : null}
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
                    data-tone={sectorLinkTone}
                    data-testid="stock-analysis-sector-review-link"
                    title={`${sectorLinkSummary} ${sectorLinkFocus}`}
                  >
                    <span aria-hidden="true">
                      <BarChartOutlined />
                    </span>
                    <strong>{sectorLinkSummary}</strong>
                    <small>{sectorLinkFocus}</small>
                  </div>
                ) : null}
                {false && apiAccurateReadinessItems.length > 0 ? (
                  <div
                    className="stock-analysis-page__api-readiness-strip"
                    data-testid="stock-analysis-api-readiness-strip"
                    aria-label="API readiness boundary"
                  >
                    {apiAccurateReadinessItems.map((item) => (
                      <div key={item.key} data-status={item.status}>
                        <h3>
                          <span>{item.label}</span>
                          <b>{readinessStatusLabel(item.status)}</b>
                        </h3>
                        <p title={item.summary}>{compactText(item.summary, 94)}</p>
                        <small>
                          {item.missingInputs.length > 0 ? item.missingInputs.slice(0, 3).join(" / ") : "输入就绪"}
                        </small>
                      </div>
                    ))}
                  </div>
                ) : null}
              </section>
                </div>

                </main>

              </div>
            ) : null}

            {apiAccurateReadinessItems.length > 0 ? (
              <section
                className="stock-analysis-page__api-readiness-section"
                aria-label="规则准备度与数据缺口"
              >
                <div className={SA_SECTION_HEAD}>
                  <div className="stock-analysis-page__min-w-0">
                    <p className={SA_SECTION_EYEBROW}>真实 API 边界</p>
                    <h2 className={SA_CARD_TITLE}>规则准备度与数据缺口</h2>
                  </div>
                </div>
                <div
                  className="stock-analysis-page__api-readiness-strip"
                  data-testid="stock-analysis-api-readiness-strip"
                  aria-label="API readiness boundary"
                >
                  {apiAccurateReadinessItems.map((item) => (
                    <div key={item.key} data-status={item.status}>
                      <h3>
                        <span>{item.label}</span>
                        <b>{readinessStatusLabel(item.status)}</b>
                      </h3>
                      <strong className="stock-analysis-page__api-readiness-metric" title={item.metric}>
                        {item.metric}
                      </strong>
                      <p title={item.summary}>{compactText(item.summary, 94)}</p>
                      <small title={`${item.inputsLabel} · ${item.detail}`}>
                        <span>{item.inputsLabel}</span>
                        <em>{item.detail}</em>
                      </small>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}

            <AnalysisGrid columns={2} className="stock-analysis-page__workspace">
              <div className="stock-analysis-page__deep-zone" data-testid="stock-analysis-deep-zone">
                <StockAnalysisDeepZoneHeader
                  gateSummary={deepAnalysisGateSummary}
                  auditRows={deepZoneAuditRows}
                />
                <div
                  className="stock-analysis-page__stock-selection-stack stock-analysis-page__deep-review-workspace"
                  data-testid="stock-analysis-stock-selection"
                >
                  <StockAnalysisStrategyLensSection
                    items={strategyLensItems}
                    onScrollToSection={scrollToStockSection}
                  />

                  <StockAnalysisConsensusFirstScreen
                    consensusSummary={consensusSummary}
                    consensusHitCount={consensusHitCount}
                    firstScreenItems={consensusFirstScreenItems}
                    emptyDetail={consensusReviewPanelSummary?.detail}
                    onOpenConsensusDetail={(row) => setDetailSelection(buildConsensusDetailSelection(row))}
                  />

                  <StockAnalysisObservationPreview
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
                  <section
                    className={`${SA_FIRST_CARD} stock-analysis-page__lower-data-band`}
                    id="stock-analysis-theme-leaders-first-screen"
                    data-testid="stock-analysis-theme-leaders-first-screen"
                  >
                    <div className={SA_SECTION_HEAD}>
                      <div className="stock-analysis-page__min-w-0">
                        <p className={SA_SECTION_EYEBROW}>题材突变</p>
                        <h2 className={SA_CARD_TITLE}>题材突破领涨股</h2>
                        <div className="stock-analysis-page__lower-signal-strip" aria-label="题材突破状态">
                          <span className="stock-analysis-page__signal-pill">
                            <FireOutlined aria-hidden="true" /> 题材 {themeBreakoutCards.length}
                          </span>
                          <span className="stock-analysis-page__signal-pill">
                            <StockOutlined aria-hidden="true" /> 领涨 {themeLeaderPreviewItems.length}
                          </span>
                        </div>
                      </div>
                      <span className={SA_PILL}>
                        {themeBreakoutCards.length > 0
                          ? `${themeLeaderPreviewItems.length} 只 · ${themeBreakoutCards.length} 题材`
                          : "题材雷达待补"}
                      </span>
                    </div>

                    {themeLeaderPreviewItems.length === 0 ? (
                      <CompactStatusTile
                        icon={<FireOutlined />}
                        label="题材"
                        value={themeBreakoutUnsupported ? "待补" : "0 领涨"}
                        detail={themeBreakoutBlockerLabel ?? undefined}
                        tone={themeBreakoutUnsupported ? "warning" : "neutral"}
                        testId="stock-analysis-theme-leader-empty"
                        title={themeBreakoutBlockerText ?? "当前无题材突破领涨股"}
                      />
                    ) : (
                      <div className="stock-analysis-page__table-wrap">
                        <table className="stock-analysis-page__table stock-analysis-page__table--dense stock-analysis-page__theme-leaders-table">
                          <thead>
                            <tr>
                              <th scope="col">题材</th>
                              <th scope="col">领涨股</th>
                              <th scope="col">涨跌</th>
                              <th scope="col">换手</th>
                              <th scope="col">收盘强度</th>
                              <th scope="col">标签</th>
                            </tr>
                          </thead>
                          <tbody>
                            {themeLeaderPreviewItems.map((row) => (
                              <tr
                                key={`${row.themeName}:${row.stockCode}`}
                                className="stock-analysis-page__row--clickable"
                                data-testid={`theme-leader-first-row-${row.stockCode}`}
                                onClick={() => {
                                  const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stockCode);
                                  setDetailSelection(
                                    buildRankContextDetailSelection({
                                      stockCode: row.stockCode,
                                      stockName: row.stockName,
                                      ranks,
                                    }),
                                  );
                                }}
                              >
                                <td>
                                  #{row.themeRank} {row.themeName}
                                </td>
                                <td>
                                  {row.stockName}
                                  <small className="stock-analysis-page__tabular"> {row.stockCode}</small>
                                </td>
                                <td className="stock-analysis-page__table-number">{row.pctChange}</td>
                                <td className="stock-analysis-page__table-number">{row.turn}</td>
                                <td className="stock-analysis-page__table-number">{row.closeStrength}</td>
                                <td>{row.tags.join(" / ") || "复核"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </section>

                  <section
                    className={`${SA_FIRST_CARD} stock-analysis-page__lower-data-band`}
                    id="stock-analysis-sector-heavyweights-first-screen"
                    data-testid="stock-analysis-sector-heavyweights-first-screen"
                  >
                    <div className={SA_SECTION_HEAD}>
                      <div className="stock-analysis-page__min-w-0">
                        <p className={SA_SECTION_EYEBROW}>板块结构</p>
                        <h2 className={SA_CARD_TITLE}>权重股摘要</h2>
                        <div className="stock-analysis-page__lower-signal-strip" aria-label="权重股样本状态">
                          <span className="stock-analysis-page__signal-pill">
                            <BarChartOutlined aria-hidden="true" /> 前 {sectorHeavyweightPreview?.sectorLimit ?? 0}
                          </span>
                          <span className="stock-analysis-page__signal-pill">
                            <StockOutlined aria-hidden="true" /> 样本{" "}
                            {sectorHeavyweightPreview?.totalSampleCount ?? 0}
                          </span>
                        </div>
                      </div>
                      <span className={SA_PILL}>
                        {sectorHeavyweightPreview
                          ? sectorHeavyweightPreview.sectorsWithSamples > 0
                            ? `${sectorHeavyweightPreview.sectorsWithSamples}/${sectorHeavyweightPreview.sectorLimit} 板块 · ${sectorHeavyweightPreview.totalSampleCount} 只样本`
                            : `前 ${sectorHeavyweightPreview.sectorLimit} 板块 · 观察池未覆盖`
                          : "板块待补"}
                      </span>
                    </div>

                    {!sectorHeavyweightPreview || sectorHeavyweightPreview.rows.length === 0 ? (
                      <CompactStatusTile
                        icon={<BarChartOutlined />}
                        label="板块强弱"
                        value="未就绪"
                        tone="warning"
                        testId="stock-analysis-sector-heavyweight-empty"
                      />
                    ) : sectorHeavyweightRows.length === 0 ? (
                      <CompactStatusTile
                        icon={<StockOutlined />}
                        label={`前 ${sectorHeavyweightPreview.sectorLimit}`}
                        value="0 命中"
                        testId="stock-analysis-sector-heavyweight-empty"
                      />
                    ) : (
                      <>
                        {sectorHeavyweightPreview.uncoveredSectorCount > 0 ? (
                          <div
                            className="stock-analysis-page__signal-pill stock-analysis-page__signal-pill--warn stock-analysis-page__sector-heavyweight-coverage"
                            data-testid="stock-analysis-sector-heavyweight-coverage"
                            role="status"
                            aria-label={`权重股样本缺口 ${sectorHeavyweightPreview.uncoveredSectorCount}`}
                          >
                            <StatusIcon tone="warning">
                              <DatabaseOutlined />
                            </StatusIcon>
                            缺口 {sectorHeavyweightPreview.uncoveredSectorCount}
                          </div>
                        ) : null}
                        <div className="stock-analysis-page__sector-heavyweight-grid">
                          {sectorHeavyweightRows.map((sector) => (
                            <article
                              key={sector.sectorCode}
                              className="stock-analysis-page__sector-heavyweight-card"
                              data-testid={`sector-heavyweight-card-${sector.sectorCode}`}
                            >
                              <header className="stock-analysis-page__sector-heavyweight-head">
                                <strong>
                                  #{sector.sectorRank} {sector.sectorName}
                                </strong>
                                <span>
                                  板块 {sector.sectorPctChange} · 得分 {sector.sectorScore} · 样本 {sector.stocks.length}
                                </span>
                              </header>
                              <ul className="stock-analysis-page__sector-heavyweight-list">
                                {sector.stocks.slice(0, 1).map((stock) => (
                                  <li
                                      key={stock.stockCode}
                                      className="stock-analysis-page__sector-heavyweight-row stock-analysis-page__row--clickable"
                                      data-testid={`sector-heavyweight-row-${sector.sectorCode}-${stock.stockCode}`}
                                      onClick={() => {
                                        const ranks = lookupStockStrategyRanks(
                                          strategyPayload ?? null,
                                          stock.stockCode,
                                        );
                                        setDetailSelection(
                                          buildRankContextDetailSelection({
                                            stockCode: stock.stockCode,
                                            stockName: stock.stockName,
                                            sectorCode: sector.sectorCode,
                                            sectorName: sector.sectorName,
                                            ranks,
                                          }),
                                        );
                                      }}
                                      role="button"
                                      tabIndex={0}
                                      onKeyDown={(event) => {
                                        if (event.key === "Enter" || event.key === " ") {
                                          event.preventDefault();
                                          const ranks = lookupStockStrategyRanks(
                                            strategyPayload ?? null,
                                            stock.stockCode,
                                          );
                                          setDetailSelection(
                                            buildRankContextDetailSelection({
                                              stockCode: stock.stockCode,
                                              stockName: stock.stockName,
                                              sectorCode: sector.sectorCode,
                                              sectorName: sector.sectorName,
                                              ranks,
                                            }),
                                          );
                                        }
                                      }}
                                    >
                                      <span className="stock-analysis-page__sector-heavyweight-main">
                                        <strong>{stock.stockName}</strong>
                                        <small className="stock-analysis-page__tabular">{stock.stockCode}</small>
                                      </span>
                                      <span className="stock-analysis-page__sector-heavyweight-metrics">
                                        <span>{stock.pctChange}</span>
                                        <span>换手 {stock.turn}</span>
                                        {stock.auxiliaryLabel ? (
                                          <span>{stock.auxiliaryLabel}</span>
                                        ) : (
                                          <span>收盘强度 {stock.closeStrength}</span>
                                        )}
                                        {stock.detailLabel ? <span>{stock.detailLabel}</span> : null}
                                      </span>
                                      <em>{stock.sourceLabel}</em>
                                    </li>
                                ))}
                              </ul>
                            </article>
                          ))}
                        </div>
                      </>
                    )}
                  </section>

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

                    <Tabs
                      className="stock-analysis-page__analytics-tabs"
                      size="small"
                      activeKey={firstScreenAnalyticsTab}
                      onChange={handleFirstScreenAnalyticsTabChange}
                      items={[
                        {
                          key: "consensus",
                          label: "历史共振",
                          children: !consensusSummary.hasAnyStrategy ? (
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
                          ),
                        },
                        {
                          key: "priority",
                          label: "策略优先级",
                          children: !firstScreenAnalyticsRequested ? (
                            <CompactStatusTile
                              icon={<LineChartOutlined />}
                              label="策略优先级"
                              value="待查"
                              testId="stock-analysis-priority-deferred"
                            />
                          ) : strategyScoreQuery.isLoading ? (
                            <p className="stock-analysis-page__empty">当前市场策略优先级加载中。</p>
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
                                          {backtestStatsText(row.stats[horizon])}
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
                          ),
                        },
                        {
                          key: "optimization",
                          label: "优化诊断",
                          children: !firstScreenAnalyticsRequested ? (
                            <CompactStatusTile
                              icon={<SafetyCertificateOutlined />}
                              label="优化诊断"
                              value="待查"
                              testId="stock-analysis-optimization-deferred"
                            />
                          ) : strategyOptimizationQuery.isLoading ? (
                            <p className="stock-analysis-page__empty">优化诊断加载中。</p>
                          ) : strategyOptimizationQuery.isError ? (
                            <p className="stock-analysis-page__notice">
                              优化诊断暂不可用：{strategyPanelErrorMessage(strategyOptimizationQuery.error)}
                            </p>
                          ) : strategyOptimizationRows.length > 0 ? (
                            <div className="stock-analysis-page__table-wrap">
                              <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                                <thead>
                                  <tr>
                                    <th scope="col">策略</th>
                                    <th scope="col">复核状态</th>
                                    <th scope="col">T+5 收益</th>
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
                                        {backtestStatsText(
                                          strategyOptimizationPrimaryStats(row, strategyOptimizationPayload),
                                        )}
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
                              value="0"
                              testId="stock-analysis-optimization-empty"
                            />
                          ),
                        },
                      ]}
                    />
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
                    <Tabs
                      className="stock-analysis-page__sector-tabs"
                      size="small"
                      activeKey={sectorView}
                      onChange={handleSectorViewChange}
                      items={sectorViewTabs.map((tab) => ({ key: tab.key, label: tab.label }))}
                    />

                    <div
                      className="stock-analysis-page__sector-chart-wrap"
                      data-testid="stock-analysis-sector-strength-chart"
                      aria-label="板块强弱横向图"
                    >
                      {sectorStrengthChartRows.length > 0 ? (
                        <ReactECharts
                          option={sectorStrengthChartOption}
                          className="stock-analysis-page__echart stock-analysis-page__echart--sector-strength"
                          opts={{ renderer: "canvas" }}
                          notMerge
                          lazyUpdate
                        />
                      ) : (
                        <span className="stock-analysis-page__sector-empty-chart">
                          -
                        </span>
                      )}
                    </div>

                    <div className="stock-analysis-page__sector-rank-grid" data-testid="stock-analysis-sector-bars">
                      <div className="stock-analysis-page__sector-rank-col stock-analysis-page__sector-rank-col--top">
                        <h3>强势前 5</h3>
                        <div className="stock-analysis-page__sector-rank-list">
                          {topBars.map((row) => (
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

                    <Collapse
                      bordered={false}
                      className="stock-analysis-page__sector-collapse"
                      items={[
                        {
                          key: "sector-detail-table",
                          label: "行业明细",
                          children: (
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
                          ),
                        },
                      ]}
                    />

                    <Collapse
                      bordered={false}
                      className="stock-analysis-page__sector-collapse"
                      activeKey={sectorSeriesCollapseKeys}
                      onChange={handleSectorSeriesCollapseChange}
                      items={[
                        {
                          key: "sector-rank-series-multi",
                          label: "多日强弱",
                          children: (
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
                              <Tabs
                                size="small"
                                activeKey={String(sectorSeriesWindow)}
                                onChange={handleSectorSeriesWindowChange}
                                className="stock-analysis-page__sector-series-tabs"
                                items={[
                                  { key: "5", label: "5 交易日" },
                                  { key: "20", label: "20 交易日" },
                                ]}
                              />
                              {sectorRankSeriesQuery.isFetching ? (
                                <Text type="secondary">加载多日板块序列中。</Text>
                              ) : null}
                              {sectorRankSeriesQuery.isError ? (
                                <Alert
                                  type="warning"
                                  showIcon
                                  message="多日板块序列加载失败"
                                  description={strategyPanelErrorMessage(sectorRankSeriesQuery.error)}
                                />
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
                                  <ReactECharts
                                    option={sectorSeriesTrendChartOption}
                                    className="stock-analysis-page__echart stock-analysis-page__echart--sector-series"
                                    opts={{ renderer: "canvas" }}
                                    notMerge
                                    lazyUpdate
                                  />
                                </div>
                              ) : null}
                              {!sectorRankSeriesQuery.isFetching &&
                              !sectorRankSeriesQuery.isError &&
                              sectorRankSeriesQuery.data?.result?.state === "ok" &&
                              sectorSeriesTableRows.length === 0 ? (
                                <Text type="secondary">窗口内无表格行可展示。</Text>
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
                          ),
                        },
                      ]}
                    />
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
              <div className="stock-analysis-strategy-card-grid">
              {cycleRotationFramework ? (
                <StrategyModuleCard
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
                  <StrategyPanelComplianceDetails
                    complianceDetail={cycleRotationPanelSummary?.complianceDetail}
                    testId="stock-analysis-cycle-panel-compliance"
                  />
                  <StockAnalysisCycleRuleSummary framework={cycleRotationFramework} />
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
                      <p className="stock-analysis-page__empty">组合回测加载中。</p>
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
                          <BacktestBoundaryChips
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
                      <p className="stock-analysis-page__empty">代理回测加载中。</p>
                    ) : null}
                    {cycleProxyBacktestQuery.isError ? (
                      <p className="stock-analysis-page__notice">
                        代理回测暂不可用：{strategyPanelErrorMessage(cycleProxyBacktestQuery.error)}
                      </p>
                    ) : null}
                    {!cycleProxyBacktestQuery.isLoading && !cycleProxyBacktestQuery.isError ? (
                      cycleProxyBacktestPayload?.status === "proxy" && cycleProxyBacktestPayload.summary ? (
                        <>
                          <BacktestBoundaryChips
                            label="代理回测"
                            missingInputs={cycleProxyBacktestPayload.missing_full_strategy_inputs}
                            testId="stock-analysis-cycle-proxy-boundary"
                          />
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
                </StrategyModuleCard>
              ) : null}


              <StrategyModuleCard
                id="theme-breakout"
                title="题材突变观察"
                subtitle="题材代理"
                badgeLabel={
                  themeBreakoutPanelSummary?.badgeLabel ??
                  `${localizeThemeRadarBadge(
                    strategyPayload?.theme_breakout?.is_proxy ?? true,
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
                <StrategyPanelComplianceDetails
                            complianceDetail={themeBreakoutPanelSummary?.complianceDetail}
                            testId="stock-analysis-theme-panel-compliance"
                          />
                <StockAnalysisThemeBreakoutPanel
                  cards={themeBreakoutCards}
                  evidenceRows={themeEvidenceRows}
                  reviewItems={themeBreakoutReviewItems}
                  emptyMessage={
                    themeBreakoutUnsupported
                      ? themeBreakoutPanelSummary?.detail ?? "No theme breakout observations."
                      : "No theme breakout observations."
                  }
                />
              </StrategyModuleCard>

              <StrategyModuleCard
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
              </StrategyModuleCard>

                            <StockAnalysisStrategyReviewCards
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

              <StrategyModuleCard
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
                                        20日回撤 {(row.drawdown_20d * 100).toFixed(1)}%
                                      </span>
                                      <span>收盘强度 {(row.close_strength * 100).toFixed(0)}%</span>
                                      <span>量比 {row.vol_ratio.toFixed(1)}x</span>
                                      <span>得分 {row.score.toFixed(2)}</span>
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
              </StrategyModuleCard>

              <StrategyModuleCard
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
              </StrategyModuleCard>
              </div>
              </div>
            </AnalysisGrid>
          </>
        ) : null}
        <StockDetailDrawer
          stockCode={detailSelection?.code ?? null}
          stockName={detailSelection?.name}
          asOfDate={stockDetailAsOfDate}
          reviewContext={buildStockDetailReviewContext(detailSelection)}
          onClose={() => setDetailSelection(null)}
        />
        <Drawer
          title="复核助手"
          placement="left"
          width={480}
          open={agentDrawerOpen}
          onClose={() => setAgentDrawerOpen(false)}
          destroyOnClose
          className="stock-analysis-page__agent-drawer"
          data-testid="stock-analysis-agent-drawer"
          maskClosable
        >
          <div style={stockAnalysisPageCssVars} className="stock-analysis-page__agent-drawer-body">
            <AgentPanel
              pageId="stock-analysis"
              currentFilters={stockAnalysisAgentPageContext.current_filters}
              defaultFilters={{ research_domain: "stock" }}
              selectedRows={stockAnalysisAgentPageContext.selected_rows}
              contextNote={stockAnalysisAgentPageContext.context_note ?? null}
            />
          </div>
        </Drawer>
      </section>
    </MarketWorkbenchFrame>
  );
}
