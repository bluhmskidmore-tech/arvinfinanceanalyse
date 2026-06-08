import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BarChartOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  FireOutlined,
  LineChartOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  StockOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Alert, Button, Collapse, DatePicker, Drawer, Tabs, Typography } from "antd";
import dayjs from "dayjs";

import { useApiClient } from "../../../api/client";
import type {
  LivermoreCandidateHistoryPortfolioBacktestPayload,
  LivermoreCycleProxyBacktestPayload,
  LivermoreSignalConfluencePayload,
} from "../../../api/contracts";
import ReactECharts from "../../../lib/echarts";
import { AnalysisGrid, DataStatusStrip, PageV2Shell } from "../../../components/page/PagePrimitives";
import { AgentPanel } from "../../agent/AgentPanel";
import {
  buildCandidateReviewQueue,
  buildClosedLoopSummary,
  buildCycleMacroLayerSummary,
  buildDailyJudgmentStrip,
  buildDataBoundarySummary,
  buildDeepZoneAuditRows,
  buildDecisionSummary,
  buildMarketStateCard,
  buildRiskExitRows,
  buildSectorFilterSummary,
  buildSectorRows,
  buildSectorTableSortComparator,
  buildSectorViewModel,
  buildStockAnalysisEventMonitorRows,
  buildStockAnalysisEvidenceStatus,
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
  mergeStockClosedLoopMeta,
  pickStockFreshnessMeta,
} from "../lib/stockAnalysisPageModel";
import type { StockSectorRow } from "../lib/stockAnalysisPageModel";
import {
  buildCompactBarOption,
  buildEventSummaryOption,
  buildOutputChartRows,
  buildReviewQueueChartRows,
  buildReviewQueueRankingOption,
  buildRiskSupplyChartRows,
  buildSectorChartRows,
  buildSectorStrengthOption,
  sectorViewTabs,
  stockChartPalette,
  type CompactChartRow,
} from "../lib/stockAnalysisChartModel";
import {
  buildStockAnalysisRailReviewState,
  buildThemeBreakoutBlockerCopy,
  compactStockText as compactText,
  filterChipClass,
  formatGeneratedAtLabel,
  kpiToneToDelta,
  rawStockErrorMessage as rawErrorMessage,
  stockPageErrorMessage as errorMessage,
  stockStatusLabel as statusLabel,
  stockStrategyPanelErrorMessage as strategyPanelErrorMessage,
} from "../lib/stockAnalysisPageCopy";
import {
  buildBackendSupplyOverview,
  buildStatusCounts,
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
  outputKeyLabel,
  readinessTone,
} from "../lib/stockAnalysisPageLabels";
import {
  backtestStatsText,
  buildStrategyBacktestMarketStateRows,
  buildStrategyBacktestRows,
  formatBacktestSignedPercent,
  resolveStrategyBacktestSampleCount,
  strategyBacktestHorizonLabels,
  strategyBacktestHorizonShortLabels,
  strategyBacktestHorizons,
  strategyDisplayLabel,
} from "../lib/stockAnalysisBacktestModel";
import {
  buildStrategyMaturityCandidates,
  buildStrategyMaturityWindow,
  buildStrategyPriorityHeadline,
  formatPriorityScore,
  resolvePanelQueryState,
  resolveStrategyMaturityRow,
  strategyCandidateReturnText,
  strategyMaturityHorizonText,
  strategyMaturityRemainingText,
  strategyPriorityDiagnosticLabels,
  strategyPriorityReasonLabel,
  strategyPriorityScopeLabel,
  strategyPriorityStatusLabel,
  strategyPrioritySummaryReason,
} from "../lib/stockAnalysisPriorityModel";
import {
  buildStrategyOptimizationRows,
  strategyOptimizationDateWeightedText,
  strategyOptimizationPrimaryStats,
  strategyOptimizationReasonLabel,
  strategyOptimizationSliceLabel,
  strategyOptimizationSlicePair,
  type StrategyOptimizationSlice,
} from "../lib/stockAnalysisOptimizationModel";
import { latestSectorSeriesTableRows, sectorRankUnavailable } from "../lib/stockAnalysisSectorSeriesModel";
import { buildStockAnalysisAgentPageContext } from "../lib/buildStockAnalysisAgentPageContext";
import { buildConsensusSummary, consensusStrategyLabel, lookupStockStrategyRanks } from "../lib/buildConsensusSummary";
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
  FIRST_SCREEN_ICONS,
  SA_CARD_TITLE,
  SA_FIRST_CARD,
  SA_FIRST_HERO,
  SA_PILL,
  SA_SECTION_DESC,
  SA_SECTION_EYEBROW,
  SA_SECTION_HEAD,
  SECTION_HEAD_ICONS,
} from "../lib/stockAnalysisPageChrome";
import { useDeferredSectionSeen } from "../hooks/useDeferredSectionSeen";
import { useFirstScreenAnalyticsTabs } from "../hooks/useFirstScreenAnalyticsTabs";
import { useSectorPanelState } from "../hooks/useSectorPanelState";
import { useSectorSortState } from "../hooks/useSectorSortState";
import { useStrategyCardExpansion } from "../hooks/useStrategyCardExpansion";
import { EquityKpiCard } from "../components/EquityKpiCard";
import { BacktestBoundaryChips } from "../components/StockAnalysisBacktestBoundaryChips";
import {
  StockAnalysisErrorWorkbench,
  StockAnalysisLoadingWorkbench,
} from "../components/StockAnalysisBoundaryWorkbenches";
import { StockAnalysisBoundaryRail } from "../components/StockAnalysisBoundaryRail";
import { StockAnalysisClosedLoopSummaryRail } from "../components/StockAnalysisClosedLoopRail";
import { StockAnalysisCycleRuleSummary } from "../components/StockAnalysisCycleRuleSummary";
import { StockAnalysisDeepZoneHeader } from "../components/StockAnalysisDeepZoneHeader";
import { StockAnalysisThemeBreakoutPanel } from "../components/StockAnalysisThemeBreakoutPanel";
import { StockAnalysisObservationPreview } from "../components/StockAnalysisObservationPreview";
import { CompactStatusTile, StatusIcon } from "../components/StockAnalysisStatusPrimitives";
import { StockAnalysisReviewCandidateCard } from "../components/StockAnalysisReviewCandidateCard";
import { StockAnalysisRiskExitSection } from "../components/StockAnalysisRiskExitRows";
import { StrategyModuleCard } from "../components/StrategyModuleCard";
import { StrategyPanelComplianceDetails } from "../components/StrategyPanelResultStrip";
import { StockDetailDrawer } from "../components/StockDetailDrawer";
import { stockAnalysisPageCssVars } from "../lib/stockAnalysisTokens";
import { EMPTY_STRATEGY_PRIORITY_ROWS, stockAnalysisReadQueryOptions } from "../lib/stockAnalysisQueryOptions";
import "./StockAnalysisPage.css";

const { Text } = Typography;

export default function StockAnalysisPage() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const [asOfOverride, setAsOfOverride] = useState<string | null>(null);
  const [detailSelection, setDetailSelection] = useState<StockDetailSelection | null>(null);
  const [agentDrawerOpen, setAgentDrawerOpen] = useState(false);
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

  const sectorRowsFull = useMemo(
    () => (strategyPayload ? buildSectorRows(strategyPayload) : []),
    [strategyPayload],
  );
  const sectorOverview = useMemo(() => buildStockSectorOverviewState(sectorRowsFull), [sectorRowsFull]);
  const { leaderRow: sectorLeaderRow, tailRow: sectorTailRow, coverageCount: sectorCoverageCount } = sectorOverview;

  const sectorViewRows = useMemo(
    () => (strategyPayload ? buildSectorViewModel(strategyPayload, sectorView) : []),
    [strategyPayload, sectorView],
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
  const factorScreenCoverageNote = factorScreenPayload?.coverage_note
    ? localizeStockBackendText(factorScreenPayload.coverage_note, "factor_screen_candidates")
    : null;
  const hybridFusionPayload = strategyPayload?.hybrid_fusion_candidates;
  const reviewQueueUsesHybridFusion = (hybridFusionPayload?.items?.length ?? 0) > 0;
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
    selectedSectorLeadCandidate,
    sectorLinkTone,
    sectorLinkSummary,
    sectorLinkFocus,
  } = sectorFilterView;

  const reviewQueueChartRows = useMemo<CompactChartRow[]>(
    () => buildReviewQueueChartRows(filteredCandidates),
    [filteredCandidates],
  );

  const reviewQueueRankingOption = useMemo(
    () => buildReviewQueueRankingOption(reviewQueueChartRows),
    [reviewQueueChartRows],
  );

  const riskRows = useMemo(
    () => (strategyPayload ? buildRiskExitRows(strategyPayload, confluencePayload) : []),
    [strategyPayload, confluencePayload],
  );
  const {
    riskTriggeredCount,
    riskWatchCount,
    railRiskTone,
    railNextActionFullLabel,
    railNextActionLabel,
  } = buildStockAnalysisRailReviewState({
    reviewQueue,
    riskRows,
    nextReviewAction: decisionSummary?.nextReviewAction,
  });

  const riskExitUnsupported = strategyPayload?.unsupported_outputs.find((output) => output.key === "risk_exit");
  const themeBreakoutUnsupported = strategyPayload?.unsupported_outputs.find((output) => output.key === "theme_breakout");
  const themeBreakoutBlockerCopy = buildThemeBreakoutBlockerCopy(themeBreakoutUnsupported);
  const themeBreakoutBlockerText = themeBreakoutBlockerCopy.text;
  const themeBreakoutBlockerLabel = themeBreakoutBlockerCopy.label;

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

  const sectorChartRows = useMemo<CompactChartRow[]>(
    () => buildSectorChartRows(sectorViewRows),
    [sectorViewRows],
  );

  const readinessChartRows = useMemo<CompactChartRow[]>(
    () => {
      const counts = buildStatusCounts(backendSupplyOverview?.readinessRows ?? []);
      return ["ready", "partial", "blocked", "missing", "stale"]
        .map((status) => ({
          key: status,
          label: statusLabel(status),
          value: counts[status] ?? 0,
        }))
        .filter((row) => row.value > 0);
    },
    [backendSupplyOverview?.readinessRows],
  );

  const outputChartRows = useMemo<CompactChartRow[]>(
    () =>
      buildOutputChartRows(
        backendSupplyOverview
          ? {
              supportedCount: backendSupplyOverview.supportedOutputs.length,
              unsupportedCount: backendSupplyOverview.unsupportedOutputs.length,
            }
          : null,
      ),
    [backendSupplyOverview],
  );

  const primaryUnsupportedOutput = backendSupplyOverview?.unsupportedOutputs[0] ?? null;
  const primaryDataGap = backendSupplyOverview?.dataGapRows.find((row) => row.status !== "ready") ?? null;

  const riskSupplyChartRows = useMemo<CompactChartRow[]>(
    () => buildRiskSupplyChartRows(backendSupplyOverview?.risk ?? null),
    [backendSupplyOverview?.risk],
  );

  const sectorStrengthChartRows = useMemo(() => sectorViewRows.slice(0, 10), [sectorViewRows]);

  const sectorMiniChartOption = useMemo(
    () =>
      buildCompactBarOption({
        labels: sectorChartRows.map((row) => row.label),
        values: sectorChartRows.map((row) => row.value),
        color: stockChartPalette.primary,
      }),
    [sectorChartRows],
  );

  const readinessMiniChartOption = useMemo(
    () =>
      buildCompactBarOption({
        labels: readinessChartRows.map((row) => row.label),
        values: readinessChartRows.map((row) => row.value),
        color: stockChartPalette.accent,
      }),
    [readinessChartRows],
  );

  const outputMiniChartOption = useMemo(
    () =>
      buildEventSummaryOption(
        outputChartRows.map((row) => ({
          label: row.label,
          count: row.value,
        })),
      ),
    [outputChartRows],
  );

  const riskSupplyMiniChartOption = useMemo(
    () =>
      buildEventSummaryOption(
        riskSupplyChartRows.map((row) => ({
          label: row.label,
          count: row.value,
        })),
      ),
    [riskSupplyChartRows],
  );

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

  const dailyJudgmentStrip = useMemo(
    () => (strategyPayload ? buildDailyJudgmentStrip(strategyPayload) : null),
    [strategyPayload],
  );

  const kpiStrip = useMemo(
    () =>
      strategyPayload ? buildStockAnalysisKpiStrip(strategyPayload, confluencePayload, closedLoopMeta) : [],
    [strategyPayload, confluencePayload, closedLoopMeta],
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
  const invalidateStockAnalysis = () => {
    queryClient.invalidateQueries({ queryKey: ["stock-analysis"] }).catch(() => undefined);
  };

  const headerDateValue =
    strategyPayload?.as_of_date != null ? dayjs(strategyPayload.as_of_date) : null;

  const pickerDisplay =
    asOfOverride != null && asOfOverride.trim() !== "" ? dayjs(asOfOverride) : headerDateValue;

  const analyticsAsOf = strategyPayload?.as_of_date ?? null;
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
  const strategyOptimizationSlices = useMemo(
    () => strategyOptimizationSlicePair(strategyOptimizationPayload),
    [strategyOptimizationPayload],
  );
  const strategyPriorityRows = strategyScorePayload?.current_market_state_rows ?? EMPTY_STRATEGY_PRIORITY_ROWS;
  const strategyPriorityHeadline = buildStrategyPriorityHeadline(strategyPriorityRows);
  const strategyPriorityReason = strategyPrioritySummaryReason(strategyPriorityRows);
  const strategyMaturityRow = resolveStrategyMaturityRow(strategyPriorityRows);
  const strategyMaturityWindow = buildStrategyMaturityWindow(strategyMaturityRow);
  const strategyMaturity = strategyMaturityWindow.maturity;
  const strategyMaturitySnapshots = strategyMaturityWindow.snapshots;
  const strategyMaturityDetailSnapshotFrom = strategyMaturityWindow.snapshotFrom;
  const strategyMaturityDetailSnapshotTo = strategyMaturityWindow.snapshotTo;
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
    enabled: Boolean(analyticsAsOf && strategyBacktestSection.seen),
    ...stockAnalysisReadQueryOptions,
  });

  const strategyBacktestPayload = strategyBacktestQuery.data?.result ?? null;
  const strategyBacktestRows = useMemo(() => buildStrategyBacktestRows(strategyBacktestPayload), [strategyBacktestPayload]);
  const strategyBacktestMarketStateRows = useMemo(
    () => buildStrategyBacktestMarketStateRows(strategyBacktestPayload),
    [strategyBacktestPayload],
  );
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
  const strategyMaturityDetailQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-candidate-history-maturity-detail",
      strategyMaturityRow?.signal_kind ?? "__none",
      strategyMaturityDetailSnapshotFrom ?? "__none",
      strategyMaturityDetailSnapshotTo ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreCandidateHistory({
        snapshotFrom: strategyMaturityDetailSnapshotFrom ?? undefined,
        snapshotTo: strategyMaturityDetailSnapshotTo ?? undefined,
        limit: 500,
      }),
    enabled: Boolean(
      strategyPrioritySection.seen &&
        strategyMaturityRow &&
        strategyMaturityDetailSnapshotFrom &&
        strategyMaturityDetailSnapshotTo,
    ),
    ...stockAnalysisReadQueryOptions,
  });
  const strategyMaturityCandidateRows = useMemo(
    () =>
      buildStrategyMaturityCandidates(
        strategyMaturityDetailQuery.data?.result ?? null,
        strategyMaturityRow,
        strategyMaturitySnapshots,
      ),
    [strategyMaturityDetailQuery.data, strategyMaturityRow, strategyMaturitySnapshots],
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
        factorScreenCount: factorScreenPayload?.candidate_count ?? 0,
        hybridFusionCount: hybridFusionPayload?.candidate_count ?? 0,
        meanReversionActive: meanReversionMarketActive,
      }),
    [
      gateState,
      meanReversionPayload?.candidate_count,
      factorScreenPayload?.candidate_count,
      hybridFusionPayload?.candidate_count,
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
        reviewQueueCount: reviewQueue.length,
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
      reviewQueue.length,
      strategyBacktestDateRangeLabel,
      strategyBacktestPanelSummary,
      themeBreakoutPanelSummary,
    ],
  );

  const sectorRankSeriesQuery = useQuery({
    queryKey: ["stock-analysis", "livermore-sector-rank-series", analyticsAsOf ?? "__none", sectorSeriesWindow] as const,
    queryFn: () =>
      client.getLivermoreSectorRankSeries({
        asOfDate: analyticsAsOf ?? undefined,
        windowDays: sectorSeriesWindow,
        topK: 10,
      }),
    enabled: Boolean(
      sectorSeriesExpanded &&
        analyticsAsOf &&
        strategyPayload &&
        !sectorRankUnavailable(strategyPayload),
    ),
    ...stockAnalysisReadQueryOptions,
  });

  const sectorSeriesTableRows = useMemo(() => {
    const envelope = sectorRankSeriesQuery.data?.result;
    const series = envelope?.series;
    if (!series || envelope?.state !== "ok") {
      return [];
    }
    return latestSectorSeriesTableRows(series);
  }, [sectorRankSeriesQuery.data?.result]);

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

  return (
    <PageV2Shell testId="stock-analysis-page" style={stockAnalysisPageCssVars}>
      <main className="stock-analysis-page" data-layout-rev="2026-05-31e" data-data-viz-rev="2026-05-31e">
        <header
          className="stock-analysis-page__header stock-analysis-page__dh-topbar"
          data-testid="stock-analysis-toolbar"
        >
          <div className="stock-analysis-page__header-main stock-analysis-page__dh-topbar-main">
            <div className="stock-analysis-page__header-title-row">
              <h1>股票分析</h1>
              <span className="stock-analysis-page__badge">只读复核</span>
            </div>
            <div className="stock-analysis-page__toolbar-info" aria-label="复核控制状态">
              <span className="stock-analysis-page__toolbar-title">
                <SafetyCertificateOutlined aria-hidden="true" />
                <strong>复核控制</strong>
              </span>
              <span className="stock-analysis-page__toolbar-pill">
                <ClockCircleOutlined aria-hidden="true" />
                观察日 {backendSupplyOverview?.asOfLabel ?? analyticsAsOf ?? "日期待补"}
              </span>
              <span
                className="stock-analysis-page__toolbar-pill"
                data-tone={backendSupplyOverview?.qualityLabel === "质量 正常" ? "positive" : undefined}
              >
                <SafetyCertificateOutlined aria-hidden="true" />
                {backendSupplyOverview?.gateLabel ?? decisionSummary?.gateLabel ?? "门控待确认"}
              </span>
              <span className="stock-analysis-page__toolbar-pill">
                <DatabaseOutlined aria-hidden="true" />
                {backendSupplyOverview?.dataGapLabel ?? decisionSummary?.boundaryLabel ?? "边界待确认"}
              </span>
              <span className="stock-analysis-page__toolbar-pill">
                <StockOutlined aria-hidden="true" />
                复核 {reviewQueue.length}
              </span>
            </div>
            <div className="stock-analysis-page__header-controls stock-analysis-page__dh-topbar-controls">
              <Button
                type="default"
                className="stock-analysis-page__agent-entry stock-analysis-page__dh-topbar-btn"
                data-testid="stock-analysis-agent-open"
                icon={<SafetyCertificateOutlined />}
                onClick={() => setAgentDrawerOpen(true)}
                aria-expanded={agentDrawerOpen}
              >
                复核助手
              </Button>
              <DatePicker
                allowClear
                aria-label="as-of-date-picker"
                className="stock-analysis-page__dh-date-picker"
                data-testid="stock-analysis-as-of-picker"
                value={pickerDisplay}
                onChange={(_, iso) => {
                  setAsOfOverride(Array.isArray(iso) ? (iso[0] ?? null) : iso || null);
                }}
              />
              <Button
                data-testid="stock-analysis-refresh"
                className="stock-analysis-page__dh-topbar-btn"
                icon={<ReloadOutlined />}
                onClick={invalidateStockAnalysis}
              >
                刷新
              </Button>
              {strategyQuery.data?.result_meta?.generated_at ? (
                <Text
                  type="secondary"
                  className="stock-analysis-page__tabular stock-analysis-page__generated-at"
                  title={strategyQuery.data.result_meta.generated_at}
                >
                  <ClockCircleOutlined /> {formatGeneratedAtLabel(strategyQuery.data.result_meta.generated_at)}
                </Text>
              ) : null}
            </div>
          </div>
        </header>

        {strategyQuery.isLoading ? (
          <StockAnalysisLoadingWorkbench />
        ) : null}

        {strategyQuery.isError ? (
          <StockAnalysisErrorWorkbench message={errorMessage(strategyQuery.error)} />
        ) : null}

        {marketState ? (
          <>
            {decisionSummary && dailyJudgmentStrip ? (
              <div className="stock-analysis-page__first-screen">
                {showStaleBanner ? (
                  <div
                    className="stock-analysis-page__stale-banner rounded-lg border border-warning-200 bg-warning-50 px-4 py-2 text-sm text-warning-800"
                    data-testid="stock-analysis-stale-banner"
                    role="status"
                  >
                    数据陈旧、供数异常或使用回退快照。下方结论仅供复核参考。
                  </div>
                ) : null}

                <div
                  className="stock-analysis-page__first-screen-main"
                  data-testid="stock-analysis-first-screen-main"
                >
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
                        <span className="stock-analysis-page__dh-purpose-eyebrow">{pagePurpose.eyebrow}</span>
                        <h2 className="stock-analysis-page__dh-purpose-title">{pagePurpose.title}</h2>
                      </div>
                      <div className="stock-analysis-page__dh-purpose-status" aria-label="页面状态">
                        <span>{pagePurpose.asOfLine}</span>
                        <span>{pagePurpose.dataStatusLine}</span>
                      </div>
                    </div>
                  ) : null}

                  <div className="flex flex-col gap-3" data-testid="stock-analysis-decision-panel">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="flex min-w-0 flex-1 flex-col gap-2">
                        <div className="stock-analysis-page__dh-hero-meta-row flex flex-wrap items-center gap-2">
                          <span className="stock-analysis-page__dh-chip">只读复核</span>
                          <span className="stock-analysis-page__dh-hero-meta">
                            观察日{" "}
                            <strong className="stock-analysis-page__tabular text-[color:var(--sa-dh-ink)]">
                              {decisionSummary.asOfLabel}
                            </strong>
                          </span>
                          {backendSupplyOverview ? (
                            <span className="stock-analysis-page__dh-hero-meta">
                              数据日 {backendSupplyOverview.asOfLabel}
                            </span>
                          ) : null}
                        </div>
                        <h1 className="stock-analysis-page__dh-hero-title">
                          {backendSupplyOverview?.gateLabel ??
                            `门控 ${localizeMarketDataStatus(strategyPayload?.market_gate.state)}`}
                          {" · "}
                          {decisionSummary.exposureLabel}
                        </h1>
                        <div
                          className="flex flex-wrap gap-1.5 font-semibold text-[color:var(--sa-dh-ink)]"
                          aria-label="下一步复核状态"
                          title={decisionSummary.nextReviewAction}
                        >
                          {reviewQueue[0] ? (
                            <>
                              <span className="inline-flex items-center gap-1.5 rounded-md border border-primary-100 bg-white px-2 py-1 text-xs">
                                <StockOutlined aria-hidden="true" /> 下一步 {reviewQueue[0].stockName}
                              </span>
                              <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-white px-2 py-1 text-xs">
                                <BarChartOutlined aria-hidden="true" /> 距观察 {reviewQueue[0].distanceToBreakoutPct}
                              </span>
                            </>
                          ) : (
                            <>
                              <span className="inline-flex items-center gap-1.5 rounded-md border border-warning-200 bg-white px-2 py-1 text-xs text-warning-700">
                                <StockOutlined aria-hidden="true" /> 复核 {reviewQueue.length}
                              </span>
                              <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-white px-2 py-1 text-xs">
                                <DatabaseOutlined aria-hidden="true" /> 多因子 {factorScreenPayload?.candidate_count ?? 0}
                              </span>
                              <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-white px-2 py-1 text-xs">
                                <ThunderboltOutlined aria-hidden="true" /> 共振 {consensusHitCount}
                              </span>
                            </>
                          )}
                        </div>
                        <div className="stock-analysis-page__dh-hero-status-strip" aria-label="市场门控状态">
                          {[
                            dailyJudgmentStrip.gateChip,
                            dailyJudgmentStrip.exposureChip,
                            dailyJudgmentStrip.strongestSectorChip,
                            dailyJudgmentStrip.weakestSectorChip,
                            decisionSummary.dataFreshnessLabel,
                            decisionSummary.boundaryLabel,
                          ].map((label) => (
                            <span key={label}>{label}</span>
                          ))}
                        </div>
                      </div>
                      <aside className="stock-analysis-page__dh-hero-side" aria-label="首屏状态摘要">
                        <span>
                          <SafetyCertificateOutlined aria-hidden="true" />
                          <small>门控</small>
                          <strong>{backendSupplyOverview?.conditionLabel ?? marketState.passedLabel}</strong>
                        </span>
                        <span>
                          <DatabaseOutlined aria-hidden="true" />
                          <small>边界</small>
                          <strong>{backendSupplyOverview?.dataGapLabel ?? decisionSummary.boundaryLabel}</strong>
                        </span>
                        <span>
                          <LineChartOutlined aria-hidden="true" />
                          <small>下一步</small>
                          <strong>{reviewQueue[0]?.stockName ?? "复核队列"}</strong>
                        </span>
                      </aside>
                    </div>

                    <div className="stock-analysis-page__visually-hidden" aria-hidden="true">
                      {backendSupplyOverview
                        ? [
                            backendSupplyOverview.gateLabel,
                            backendSupplyOverview.exposureLabel,
                            backendSupplyOverview.readinessLabel,
                            backendSupplyOverview.dataGapLabel,
                            backendSupplyOverview.supportedLabel,
                            backendSupplyOverview.unsupportedLabel,
                            backendSupplyOverview.qualityLabel,
                          ].join(" ")
                        : null}
                    </div>

                    <details className="stock-analysis-page__dh-details">
                      <summary data-testid="stock-analysis-supply-details-toggle">
                        <span className="flex items-center gap-2">
                          <span className="text-[color:var(--sa-dh-blue)] group-open:rotate-90">▸</span>
                          供数闭环
                        </span>
                        {closedLoopSummary ? (
                          <strong className="stock-analysis-page__dh-pill">
                            {closedLoopSummary.referenceRating.label}
                          </strong>
                        ) : null}
                      </summary>
                      <div className="mt-3 space-y-3 px-1">
                      <div
                      className="stock-analysis-page__supply-kpi-row"
                      aria-label="供数首屏摘要"
                    >
                      <article className="stock-analysis-page__supply-kpi-card">
                        <div className="stock-analysis-page__mini-panel-head">
                          <strong>
                            <StatusIcon>{FIRST_SCREEN_ICONS[0]}</StatusIcon>
                            板块供数
                          </strong>
                          <span>{backendSupplyOverview?.sectorSupplyValueLabel ?? "0"}</span>
                        </div>
                        <div
                          className="stock-analysis-page__mini-chart"
                          data-testid="stock-analysis-sector-mini-chart"
                          aria-label="板块供数图"
                        >
                          {sectorChartRows.length > 0 ? (
                            <ReactECharts
                              option={sectorMiniChartOption}
                              className="stock-analysis-page__echart stock-analysis-page__echart--mini-bar"
                              opts={{ renderer: "canvas" }}
                              notMerge
                              lazyUpdate
                            />
                          ) : (
                            <span className="stock-analysis-page__empty stock-analysis-page__empty--signal">-</span>
                          )}
                        </div>
                      </article>
                      <article className="stock-analysis-page__supply-kpi-card">
                        <div className="stock-analysis-page__mini-panel-head">
                          <strong>
                            <StatusIcon>{FIRST_SCREEN_ICONS[1]}</StatusIcon>
                            规则就绪
                          </strong>
                          <span>{backendSupplyOverview?.readinessValueLabel ?? "0/0"}</span>
                        </div>
                        <div
                          className="stock-analysis-page__mini-chart"
                          data-testid="stock-analysis-review-mini-chart"
                          aria-label="规则就绪分布图"
                        >
                          {readinessChartRows.length > 0 ? (
                            <ReactECharts
                              option={readinessMiniChartOption}
                              className="stock-analysis-page__echart stock-analysis-page__echart--mini-bar"
                              opts={{ renderer: "canvas" }}
                              notMerge
                              lazyUpdate
                            />
                          ) : null}
                        </div>
                      </article>
                      <article className="stock-analysis-page__supply-kpi-card">
                        <div className="stock-analysis-page__mini-panel-head">
                          <strong>
                            <StatusIcon>{FIRST_SCREEN_ICONS[2]}</StatusIcon>
                            输出可用
                          </strong>
                          <span>{backendSupplyOverview?.supportedValueLabel ?? "0"}</span>
                        </div>
                        <div
                          className="stock-analysis-page__mini-chart"
                          data-testid="stock-analysis-event-mini-chart"
                          aria-label="输出可用分布图"
                        >
                          {outputChartRows.some((row) => row.value > 0) ? (
                            <ReactECharts
                              option={outputMiniChartOption}
                              className="stock-analysis-page__echart stock-analysis-page__echart--mini-stack"
                              opts={{ renderer: "canvas" }}
                              notMerge
                              lazyUpdate
                            />
                          ) : null}
                        </div>
                        {backendSupplyOverview ? (
                          <div className="stock-analysis-page__mini-table" aria-label="输出可用首屏摘要">
                            <div>
                              <span>候选</span>
                              <strong>{backendSupplyOverview.candidateSupplyValueLabel}</strong>
                            </div>
                            <div>
                              <span>阻断</span>
                              <strong>{backendSupplyOverview.unsupportedValueLabel}</strong>
                              {primaryUnsupportedOutput ? (
                                <small title={localizeStockBackendText(primaryUnsupportedOutput.reason, primaryUnsupportedOutput.key)}>
                                  {outputKeyLabel(primaryUnsupportedOutput.key)}
                                </small>
                              ) : null}
                            </div>
                          </div>
                        ) : null}
                      </article>
                      <article className="stock-analysis-page__supply-kpi-card">
                        <div className="stock-analysis-page__mini-panel-head">
                          <strong>
                            <StatusIcon>{FIRST_SCREEN_ICONS[3]}</StatusIcon>
                            风险供数
                          </strong>
                          <span>{backendSupplyOverview?.riskSupplyValueLabel ?? "0"}</span>
                        </div>
                        <div
                          className="stock-analysis-page__mini-chart"
                          data-testid="stock-analysis-risk-mini-chart"
                          aria-label="风险供数分布图"
                        >
                          {riskSupplyChartRows.some((row) => row.value > 0) ? (
                            <ReactECharts
                              option={riskSupplyMiniChartOption}
                              className="stock-analysis-page__echart stock-analysis-page__echart--mini-stack"
                              opts={{ renderer: "canvas" }}
                              notMerge
                              lazyUpdate
                            />
                          ) : null}
                        </div>
                        {backendSupplyOverview ? (
                          <div className="stock-analysis-page__mini-table" aria-label="风险供数首屏摘要">
                            <div>
                              <span>持仓</span>
                              <strong className="stock-analysis-page__tabular">
                                {backendSupplyOverview.risk?.position_count ?? 0}
                              </strong>
                            </div>
                            <div>
                              <span>触发</span>
                              <strong className="stock-analysis-page__tabular">
                                {backendSupplyOverview.risk?.signal_count ?? 0}
                              </strong>
                            </div>
                            <div>
                              <span>观察</span>
                              <strong className="stock-analysis-page__tabular">
                                {backendSupplyOverview.risk?.watch_items?.length ?? 0}
                              </strong>
                            </div>
                            {primaryDataGap ? (
                              <div>
                                <span>缺口</span>
                                <strong>{backendSupplyOverview.dataGapValueLabel}</strong>
                                <small title={localizeStockBackendText(primaryDataGap.evidence, primaryDataGap.input_family)}>
                                  {dataGapFamilyLabel(primaryDataGap.input_family)}
                                </small>
                              </div>
                            ) : null}
                          </div>
                        ) : null}
                      </article>
                    </div>

                      {backendSupplyOverview ? (
                        <DataStatusStrip
                          testId="stock-analysis-backend-supply-status"
                          className="grid content-start gap-1.5 border-l border-neutral-200 bg-neutral-50 p-3"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <h3 className="m-0 text-sm font-semibold text-neutral-900">规则就绪</h3>
                            <span className="whitespace-nowrap rounded border border-primary-200 bg-primary-50 px-2 py-0.5 text-[11px] font-bold text-primary-700">
                              只读
                            </span>
                          </div>
                          <div className="grid gap-0.5">
                            {backendSupplyOverview.readinessRows.map((item) => (
                              <div
                                className="flex min-h-[23px] items-center justify-between gap-2 border-b border-neutral-200/80 py-0.5"
                                data-tone={readinessTone(item.status)}
                                key={item.key}
                              >
                                <span className="flex min-w-0 items-center gap-1.5 overflow-hidden whitespace-nowrap text-[10px] font-bold text-neutral-500">
                                  <StatusIcon tone={readinessTone(item.status)}>
                                    <SafetyCertificateOutlined />
                                  </StatusIcon>
                                  {cycleInputLabel(item.key) || item.title}
                                </span>
                                <strong className="text-right text-[11px] leading-tight text-neutral-900">
                                  {statusLabel(item.status)}
                                </strong>
                              </div>
                            ))}
                            {backendSupplyOverview.dataGapRows.slice(0, 3).map((item) => (
                              <div
                                className="flex min-h-[23px] items-center justify-between gap-2 border-b border-neutral-200/80 py-0.5"
                                data-tone={gapTone(item.status)}
                                key={`gap:${item.input_family}`}
                              >
                                <span className="flex min-w-0 items-center gap-1.5 overflow-hidden whitespace-nowrap text-[10px] font-bold text-neutral-500">
                                  <StatusIcon tone={gapTone(item.status)}>
                                    <DatabaseOutlined />
                                  </StatusIcon>
                                  {dataGapFamilyLabel(item.input_family)}
                                </span>
                                <strong className="text-right text-[11px] leading-tight text-neutral-900">
                                  {statusLabel(item.status)}
                                </strong>
                              </div>
                            ))}
                          </div>
                        </DataStatusStrip>
                      ) : null}
                      <div
                        className="grid grid-cols-2 gap-0 overflow-hidden rounded-md border border-neutral-200 bg-neutral-50 sm:grid-cols-3 xl:grid-cols-6"
                        aria-label="供数摘要"
                      >
                        {[
                          backendSupplyOverview?.gateLabel ?? decisionSummary.gateLabel,
                          backendSupplyOverview?.exposureLabel ?? decisionSummary.exposureLabel,
                          backendSupplyOverview?.readinessLabel ?? "就绪 0/0",
                          backendSupplyOverview?.dataGapLabel ?? "缺口 0",
                          backendSupplyOverview?.supportedLabel ?? "可用 0",
                          backendSupplyOverview?.unsupportedLabel ?? "阻断 0",
                        ].map((label) => {
                          const shortLabel = compactText(label, 20);
                          return (
                            <span
                              key={label}
                              title={label}
                              className="flex min-h-[46px] min-w-0 items-center gap-2 border-b border-r border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-900 last:border-r-0 sm:[&:nth-child(3n)]:border-r-0 xl:border-b-0 xl:[&:nth-child(6n)]:border-r-0"
                            >
                              <strong className="min-w-0 truncate">{shortLabel}</strong>
                              {shortLabel !== label ? (
                                <small className="sr-only">{label}</small>
                              ) : null}
                            </span>
                          );
                        })}
                      </div>
                      <div className="grid grid-cols-2 gap-0 overflow-hidden rounded-md border border-neutral-200 bg-white sm:grid-cols-4">
                        <div
                          className="grid min-h-[50px] grid-cols-[auto_minmax(0,1fr)] items-center gap-x-2 gap-y-0.5 border-b border-r border-neutral-200 px-3 py-2 sm:[&:nth-child(2n)]:border-r-0 sm:[&:nth-child(-n+2)]:border-b sm:[&:nth-child(n+3)]:border-b-0 sm:odd:border-r"
                          title={`数据日期 ${backendSupplyOverview?.asOfLabel ?? decisionSummary.asOfLabel}`}
                        >
                          <StatusIcon>{DECISION_GRID_ICONS[0]}</StatusIcon>
                          <span className="text-xs text-neutral-500">数据日期</span>
                          <strong className="stock-analysis-page__tabular col-start-2 text-sm">
                            {backendSupplyOverview?.asOfLabel ?? decisionSummary.asOfLabel}
                          </strong>
                        </div>
                        <div
                          className="grid min-h-[50px] grid-cols-[auto_minmax(0,1fr)] items-center gap-x-2 gap-y-0.5 border-b border-r border-neutral-200 px-3 py-2 sm:border-r-0 sm:[&:nth-child(-n+2)]:border-b"
                          title={`口径 ${backendSupplyOverview?.basisLabel ?? decisionSummary.basisLabel}`}
                        >
                          <StatusIcon>{DECISION_GRID_ICONS[1]}</StatusIcon>
                          <span className="text-xs text-neutral-500">口径</span>
                          <strong className="col-start-2 break-words text-sm">
                            {backendSupplyOverview?.basisLabel ?? decisionSummary.basisLabel}
                          </strong>
                        </div>
                        <div
                          className="grid min-h-[50px] grid-cols-[auto_minmax(0,1fr)] items-center gap-x-2 gap-y-0.5 border-b border-r border-neutral-200 px-3 py-2 sm:odd:border-r sm:[&:nth-child(n+3)]:border-b-0"
                          title={`请求日期 ${backendSupplyOverview?.requestedAsOfLabel ?? "默认"}`}
                        >
                          <StatusIcon>{DECISION_GRID_ICONS[2]}</StatusIcon>
                          <span className="text-xs text-neutral-500">请求日期</span>
                          <strong className="col-start-2 text-sm">
                            {backendSupplyOverview?.requestedAsOfLabel ?? "默认"}
                          </strong>
                        </div>
                        <div
                          className="grid min-h-[50px] grid-cols-[auto_minmax(0,1fr)] items-center gap-x-2 gap-y-0.5 border-neutral-200 px-3 py-2 sm:border-r-0"
                          title={`门控确认 ${backendSupplyOverview?.conditionLabel ?? marketState.passedLabel}`}
                        >
                          <StatusIcon>{DECISION_GRID_ICONS[3]}</StatusIcon>
                          <span className="text-xs text-neutral-500">门控确认</span>
                          <strong className="col-start-2 break-words text-sm">
                            {backendSupplyOverview?.conditionLabel ?? marketState.passedLabel}
                          </strong>
                        </div>
                      </div>
                      <div className="grid gap-4 md:grid-cols-2">
                        <section>
                          <h3 className="mb-2 text-sm font-semibold text-neutral-900">门控条件</h3>
                          <ul className="grid gap-1.5 p-0">
                            {marketState.conditions.map((condition) => (
                              <li
                                key={condition.key}
                                className="flex items-center justify-between gap-3 rounded-md border border-neutral-100 bg-neutral-50 px-2.5 py-2"
                              >
                                <span>
                                  <strong className="text-sm text-neutral-900">{condition.label}</strong>
                                  <small className="block text-xs text-neutral-500">{condition.evidence}</small>
                                </span>
                                <em className="not-italic rounded-full border border-primary-200 bg-primary-50 px-2 py-0.5 text-xs font-semibold text-primary-700">
                                  {statusLabel(condition.status)}
                                </em>
                              </li>
                            ))}
                          </ul>
                        </section>
                        <section>
                          <h3 className="mb-2 text-sm font-semibold text-neutral-900">需要关注边界</h3>
                          {marketState.warnings.length > 0 ? (
                            <ul className="grid gap-2 p-0">
                              {marketState.warnings.slice(0, 4).map((warning) => (
                                <li
                                  key={warning}
                                  className="border-l-[3px] border-warning-300 py-1 pl-2.5 text-sm leading-relaxed text-neutral-500"
                                >
                                  {localizeStockBackendText(warning)}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="text-sm text-neutral-500">当前无诊断预警。</p>
                          )}
                        </section>
                      </div>
                      </div>
                    </details>
                  </div>
                </section>

                {kpiStrip.length > 0 ? (
                  <section data-testid="stock-analysis-kpi-section" aria-label="选股快照">
                    <p className="stock-analysis-page__visually-hidden">选股快照</p>
                    <div
                      className="stock-analysis-page__dh-kpi-strip"
                      data-testid="stock-analysis-kpi-strip"
                    >
                    {kpiStrip.map((item) => (
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
                  className="stock-analysis-page__stock-selection-stack"
                  data-testid="stock-analysis-stock-selection"
                >
                  {strategyLensItems.length > 0 ? (
                    <section
                      className="stock-analysis-page__strategy-lens"
                      aria-label="策略选股概览"
                      data-testid="stock-analysis-strategy-lens"
                    >
                      <p className="stock-analysis-page__visually-hidden">策略选股概览</p>
                      <div className="stock-analysis-page__strategy-lens-grid">
                        {strategyLensItems.map((item) => (
                          <button
                            key={item.key}
                            type="button"
                            className="stock-analysis-page__strategy-lens-card"
                            data-tone={item.tone}
                            data-testid={`stock-analysis-strategy-lens-${item.key}`}
                            onClick={() => scrollToStockSection(item.scrollTarget)}
                          >
                            <span className="stock-analysis-page__strategy-lens-label">{item.label}</span>
                            <strong className="stock-analysis-page__strategy-lens-value">{item.value}</strong>
                            <small className="stock-analysis-page__strategy-lens-detail">{item.detail}</small>
                            {item.progress != null ? (
                              <progress
                                className="stock-analysis-page__strategy-lens-meter"
                                max={100}
                                value={Math.max(4, item.progress * 100)}
                                aria-label={`${item.label} 进度`}
                              />
                            ) : null}
                          </button>
                        ))}
                      </div>
                    </section>
                  ) : null}

                  <section
                    className={SA_FIRST_CARD}
                    id="stock-analysis-review-queue"
                    data-testid="stock-analysis-review-queue"
                  >
                <div className={SA_SECTION_HEAD}>
                  <div className="min-w-0">
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

                <div
                  className="stock-analysis-page__review-workbench-strip"
                  data-testid="stock-analysis-review-workbench-strip"
                  aria-label="复核工作台摘要"
                >
                  <div>
                    <DatabaseOutlined aria-hidden="true" />
                    <span>队列</span>
                    <strong className="stock-analysis-page__tabular">{filteredCandidates.length}/{reviewQueue.length}</strong>
                  </div>
                  <div>
                    <StockOutlined aria-hidden="true" />
                    <span>首位</span>
                    <strong>{selectedSectorLeadCandidate?.stockName ?? "待补"}</strong>
                  </div>
                  <div>
                    <BarChartOutlined aria-hidden="true" />
                    <span>距观察</span>
                    <strong className="stock-analysis-page__tabular">
                      {selectedSectorLeadCandidate?.distanceToBreakoutPct ?? "-"}
                    </strong>
                  </div>
                  <div>
                    <SafetyCertificateOutlined aria-hidden="true" />
                    <span>证据</span>
                    <strong className="stock-analysis-page__tabular">
                      {selectedSectorLeadCandidate
                        ? selectedSectorLeadCandidate.primaryEvidence.length +
                          selectedSectorLeadCandidate.supportingEvidence.length
                        : 0}
                    </strong>
                  </div>
                </div>

                {reviewQueue.length > 0 ? (
                  <div
                    className="mb-2 flex flex-wrap items-center gap-1.5 rounded-md border border-neutral-100 bg-neutral-50 px-2 py-1.5"
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
                      className="ml-auto flex min-w-[180px] flex-wrap items-center justify-end gap-x-2 gap-y-0.5 text-xs text-neutral-500"
                      data-testid="stock-review-filter-status"
                    >
                      <span>范围</span>
                      <strong className="text-sm text-neutral-900">{selectedSectorLabel ?? "全部行业"}</strong>
                      <small>
                        显示 {filteredCandidates.length} / {reviewQueue.length} 个候选
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

                {reviewQueueChartRows.length > 0 ? (
                  <div
                    className="mb-2 grid gap-2 border-y border-neutral-100 bg-neutral-50/70 px-2 py-2 md:grid-cols-[minmax(0,1fr)_minmax(160px,220px)]"
                    data-testid="stock-analysis-review-queue-ranking-chart"
                    aria-label="复核队列排名图"
                  >
                    <div className="min-w-0">
                      <div className="mb-1 flex items-center justify-between gap-2 text-xs">
                        <strong className="inline-flex items-center gap-1 text-neutral-900">
                          <BarChartOutlined aria-hidden="true" /> 队列排序
                        </strong>
                        <span className="font-semibold text-neutral-500">前 {reviewQueueChartRows.length}</span>
                      </div>
                      <ReactECharts
                        option={reviewQueueRankingOption}
                        className="stock-analysis-page__echart stock-analysis-page__echart--review-queue"
                        opts={{ renderer: "canvas" }}
                        notMerge
                        lazyUpdate
                      />
                    </div>
                    <div className="grid grid-cols-3 gap-1 md:grid-cols-1">
                      {reviewQueueChartRows.slice(0, 3).map((row) => (
                        <div key={row.key} className="min-w-0 border-l border-neutral-200 pl-2 text-xs">
                          <strong className="block truncate text-neutral-900">{row.label}</strong>
                          <span className="block truncate text-neutral-500">{row.detail}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {reviewQueue.length === 0 ? (
                  <div
                    className="stock-analysis-page__review-empty-panel"
                    role="status"
                    data-testid="stock-analysis-review-queue-empty"
                    title={reviewQueueEmptyState?.detail ?? "查看观察池与板块"}
                  >
                    <div className="grid w-full gap-2 sm:grid-cols-3">
                      <CompactStatusTile
                        icon={<StockOutlined />}
                        label="队列"
                        value="0"
                        tone="warning"
                        className="w-full bg-white"
                        title={reviewQueueEmptyState?.headline ?? "暂无主候选"}
                      />
                      <CompactStatusTile
                        icon={<DatabaseOutlined />}
                        label="多因子"
                        value={factorScreenPayload?.candidate_count ?? 0}
                        className="w-full bg-white"
                      />
                      <CompactStatusTile
                        icon={<BarChartOutlined />}
                        label="板块"
                        value={sectorRowsFull.length}
                        className="w-full bg-white"
                      />
                    </div>
                  </div>
                ) : filteredCandidates.length === 0 ? (
                  <CompactStatusTile
                    icon={<BarChartOutlined />}
                    label="行业筛选"
                    value="0 候选"
                    tone="warning"
                    testId="stock-analysis-review-queue-filter-empty"
                  />
                ) : (
                  <div className="stock-analysis-page__review-candidate-grid grid grid-cols-1 gap-2 lg:grid-cols-2">
                    {filteredCandidates.map((card) => (
                      <StockAnalysisReviewCandidateCard
                        key={card.stockCode}
                        card={card}
                        selectedSectorCode={sectorFilterSectorCode}
                        onReviewChart={() => {
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
                    ))}
                  </div>
                )}
              </section>

                  <section
                    className={SA_FIRST_CARD}
                    id="stock-analysis-consensus-first-screen"
                    data-testid="stock-analysis-consensus-first-screen"
                  >
                    <div className={SA_SECTION_HEAD}>
                      <div className="min-w-0">
                        <p className={SA_SECTION_EYEBROW}>多策略共振</p>
                        <h2 className={SA_CARD_TITLE}>策略共振选股</h2>
                        <p className={SA_SECTION_DESC}>
                          共振命中 · 三重优先
                        </p>
                      </div>
                      <span className={SA_PILL}>
                        共振 {consensusHitCount} · 去重 {consensusSummary.totalUnion}
                      </span>
                    </div>

                    <div
                      className="stock-analysis-page__consensus-workbench-strip"
                      data-testid="stock-analysis-consensus-workbench-strip"
                      aria-label="策略共振摘要"
                    >
                      <div data-tone={consensusHitCount > 0 ? "positive" : "neutral"}>
                        <ThunderboltOutlined aria-hidden="true" />
                        <span>共振</span>
                        <strong className="stock-analysis-page__tabular">{consensusHitCount}</strong>
                      </div>
                      <div>
                        <DatabaseOutlined aria-hidden="true" />
                        <span>去重</span>
                        <strong className="stock-analysis-page__tabular">{consensusSummary.totalUnion}</strong>
                      </div>
                      <div>
                        <LineChartOutlined aria-hidden="true" />
                        <span>趋势</span>
                        <strong className="stock-analysis-page__tabular">{consensusSummary.strategyCounts.livermore}</strong>
                      </div>
                      <div>
                        <BarChartOutlined aria-hidden="true" />
                        <span>多因子</span>
                        <strong className="stock-analysis-page__tabular">{consensusSummary.strategyCounts.factor_screen}</strong>
                      </div>
                    </div>

                    {!consensusSummary.hasAnyStrategy ? (
                      <p className="stock-analysis-page__empty">{consensusReviewPanelSummary?.detail ?? "候选 0"}</p>
                    ) : consensusFirstScreenItems.length === 0 ? (
                      <div
                        className="grid gap-2 sm:grid-cols-3"
                        role="status"
                        data-testid="stock-analysis-consensus-empty-scan"
                        aria-label="暂无多策略共振"
                      >
                        <CompactStatusTile icon={<ThunderboltOutlined />} label="共振" value={consensusHitCount} />
                        <CompactStatusTile icon={<DatabaseOutlined />} label="去重" value={consensusSummary.totalUnion} />
                        <CompactStatusTile
                          icon={<LineChartOutlined />}
                          label="复核"
                          value="队列"
                          tone="positive"
                          className="border-primary-100 bg-primary-50"
                        />
                      </div>
                    ) : (
                      <div className="stock-analysis-page__consensus-first-list">
                        {consensusFirstScreenItems.map((row) => {
                          const isTriple = row.consensusCount >= 3;
                          return (
                            <button
                              key={row.stockCode}
                              type="button"
                              className={`stock-analysis-page__consensus-first-row stock-analysis-page__row--clickable${
                                isTriple ? " stock-analysis-page__consensus-first-row--triple" : ""
                              }`}
                              data-testid={`consensus-first-row-${row.stockCode}`}
                              onClick={() => {
                                setDetailSelection(buildConsensusDetailSelection(row));
                              }}
                            >
                              <div className="stock-analysis-page__consensus-first-main">
                                <strong>
                                  {row.stockName}{" "}
                                  <small className="stock-analysis-page__tabular">{row.stockCode}</small>
                                </strong>
                                <span>{row.sectorName}</span>
                              </div>
                              <div className="stock-analysis-page__consensus-first-badges">
                                <span
                                  className={`stock-analysis-page__consensus-badge${
                                    isTriple ? " stock-analysis-page__consensus-badge--triple" : ""
                                  }`}
                                >
                                  {row.consensusCount} 策略共振
                                </span>
                                {row.strategies.map((kind) => (
                                  <span key={kind} className="stock-analysis-page__consensus-badge">
                                    {consensusStrategyLabel(kind)}
                                  </span>
                                ))}
                              </div>
                              <div className="stock-analysis-page__consensus-ranks">
                                {row.hybridFusionRank != null && <span>融合 #{row.hybridFusionRank}</span>}
                                {row.livermoreRank != null && <span>趋势 #{row.livermoreRank}</span>}
                                {row.factorScreenRank != null && <span>多因子 #{row.factorScreenRank}</span>}
                                {row.meanReversionRank != null && <span>超跌 #{row.meanReversionRank}</span>}
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </section>
                </div>
                </div>
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
                      <div className="min-w-0">
                        <p className={SA_SECTION_EYEBROW}>题材突变</p>
                        <h2 className={SA_CARD_TITLE}>题材突破领涨股</h2>
                        <div className="stock-analysis-page__lower-signal-strip" aria-label="题材突破状态">
                          <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-semibold text-neutral-600">
                            <FireOutlined aria-hidden="true" /> 题材 {themeBreakoutCards.length}
                          </span>
                          <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-semibold text-neutral-600">
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
                      <div className="min-w-0">
                        <p className={SA_SECTION_EYEBROW}>板块结构</p>
                        <h2 className={SA_CARD_TITLE}>权重股摘要</h2>
                        <div className="stock-analysis-page__lower-signal-strip" aria-label="权重股样本状态">
                          <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-semibold text-neutral-600">
                            <BarChartOutlined aria-hidden="true" /> 前 {sectorHeavyweightPreview?.sectorLimit ?? 0}
                          </span>
                          <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-semibold text-neutral-600">
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
                            className="mb-2 inline-flex items-center gap-2 rounded-md border border-warning-200 bg-warning-50 px-2.5 py-1.5 text-xs font-semibold text-warning-700 stock-analysis-page__sector-heavyweight-coverage"
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
                      <div className="min-w-0">
                        <p className={SA_SECTION_EYEBROW}>深度回测</p>
                        <h2 className={SA_CARD_TITLE}>回测诊断</h2>
                        <div className="mt-2 flex flex-wrap gap-1.5" aria-label="回测诊断状态">
                          <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-semibold text-neutral-600">
                            <ThunderboltOutlined aria-hidden="true" /> 共振 {consensusHitCount}
                          </span>
                          <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-semibold text-neutral-600">
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

                <div className="stock-analysis-page__dh-work-grid" data-testid="stock-analysis-first-screen-workbench">
                  <div className="flex flex-col gap-3" data-testid="stock-analysis-first-screen-primary">
                    <section
                className={SA_FIRST_CARD}
                data-testid="stock-analysis-sector-strength-panel"
              >
                <div className={SA_SECTION_HEAD}>
                  <div className="min-w-0">
                    <p className={SA_SECTION_EYEBROW}>行业相对强弱</p>
                    <h2 className={SA_CARD_TITLE}>
                      <StatusIcon>{SECTION_HEAD_ICONS[0]}</StatusIcon>
                      板块强弱
                    </h2>
                    <p className={SA_SECTION_DESC}>
                      {sectorRowsFull.length} 个板块 · 强弱对比
                    </p>
                  </div>
                  <span className={SA_PILL}>
                    {sectorRowsFull.length > 0 ? `${sectorRowsFull.length} 个板块` : "板块待补"}
                  </span>
                </div>

                {!sectorRankUnavailable(strategyPayload) ? (
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
                        <span className="grid min-h-[54px] place-items-center font-mono text-2xl font-bold text-neutral-300">
                          -
                        </span>
                      )}
                    </div>

                    <div className="stock-analysis-page__sector-rank-grid" data-testid="stock-analysis-sector-bars">
                      <div className="stock-analysis-page__sector-rank-col stock-analysis-page__sector-rank-col--top">
                        <h3>强势前 5</h3>
                        <div className="grid gap-1.5">
                          {topBars.map((row) => (
                            <button
                              type="button"
                              key={`top-${row.sectorCode}-${row.rank}`}
                              className={`grid w-full gap-1 rounded-md border border-transparent bg-transparent p-0.5 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-500${
                                sectorFilterSectorCode === row.sectorCode
                                  ? " shadow-[inset_3px_0_0_0_theme(colors.primary.600)] pl-2"
                                  : ""
                              }`}
                              aria-pressed={sectorFilterSectorCode === row.sectorCode}
                              data-testid={`sector-bar-${row.sectorCode}`}
                              onClick={() => toggleSectorFilter(row.sectorCode)}
                            >
                              <div className="stock-analysis-page__sector-rank-row-head stock-analysis-page__tabular">
                                <span className="min-w-0 truncate">
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
                                  <small className="text-neutral-500">成分 {row.constituentCount}</small>
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="stock-analysis-page__sector-rank-col stock-analysis-page__sector-rank-col--bottom">
                        <h3>弱势后 5</h3>
                        <div className="grid gap-1.5">
                          {bottomBars.map((row) => (
                            <button
                              type="button"
                              key={`bottom-${row.sectorCode}-${row.rank}`}
                              className={`grid w-full gap-1 rounded-md border border-transparent bg-transparent p-0.5 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-500${
                                sectorFilterSectorCode === row.sectorCode
                                  ? " shadow-[inset_3px_0_0_0_theme(colors.primary.600)] pl-2"
                                  : ""
                              }`}
                              aria-pressed={sectorFilterSectorCode === row.sectorCode}
                              data-testid={`sector-bar-bottom-${row.sectorCode}`}
                              onClick={() => toggleSectorFilter(row.sectorCode)}
                            >
                              <div className="stock-analysis-page__sector-rank-row-head stock-analysis-page__tabular">
                                <span className="min-w-0 truncate">
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
                                  <small className="text-neutral-500">成分 {row.constituentCount}</small>
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                    <div
                      className="mt-2 flex flex-wrap gap-1.5 text-[11px] font-semibold text-neutral-600"
                      aria-label="板块筛选状态"
                    >
                      <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1">
                        <ClockCircleOutlined aria-hidden="true" /> 截面
                      </span>
                      <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1">
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
                                按交易日累计展示强弱变化；资金流向待补。
                              </p>
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
                                          cum_pctchange_window
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
                                            {row.score ?? "-"}
                                          </td>
                                          <td className="stock-analysis-page__table-number">
                                            {row.rank ?? "-"}
                                          </td>
                                          <td className="stock-analysis-page__table-number">
                                            {row.cum_pctchange_window ?? "-"}
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
                    className="flex min-h-[120px] items-center justify-center rounded-md border border-dashed border-neutral-200 bg-neutral-50 text-sm text-neutral-500"
                    role="status"
                  >
                    板块数据不足，待补
                  </div>
                )}
              </section>

                  </div>

                  <aside className="flex flex-col gap-3" aria-label="风险与数据可信度" data-testid="stock-analysis-first-screen-rail">
                    <p className={SA_SECTION_EYEBROW}>决策栏</p>
                    {closedLoopSummary ? (
                      <StockAnalysisClosedLoopSummaryRail
                        summary={closedLoopSummary}
                        riskTone={railRiskTone}
                        riskTriggeredCount={riskTriggeredCount}
                        boundaryIssueCount={boundaryRailIssueCount}
                        reviewQueueCount={reviewQueue.length}
                        nextActionLabel={railNextActionLabel}
                        nextActionFullLabel={railNextActionFullLabel}
                      />
                    ) : null}

                    <StockAnalysisRiskExitSection
                      rows={riskRows}
                      riskTriggeredCount={riskTriggeredCount}
                      riskWatchCount={riskWatchCount}
                      confluenceError={confluenceQuery.isError}
                      unsupportedOutput={riskExitUnsupported}
                      onOpenRiskDetail={(row) => {
                        const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stockCode);
                        setDetailSelection(buildRiskExitDetailSelection({ row, ranks }));
                      }}
                    />

                    <StockAnalysisBoundaryRail
                      boundaryItems={boundaryRailItems}
                      boundarySummary={boundarySummary}
                      strategyPayload={strategyPayload}
                    />

                  </aside>
                </div>
              </div>
            ) : null}

            <AnalysisGrid columns={2} className="stock-analysis-page__workspace">
              <div className="stock-analysis-page__deep-zone" data-testid="stock-analysis-deep-zone">
                <StockAnalysisDeepZoneHeader
                  gateSummary={deepAnalysisGateSummary}
                  auditRows={deepZoneAuditRows}
                />
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

              <StrategyModuleCard
                id="market-priority"
                title="当前市场策略优先级"
                subtitle="T+5 排序"
                badgeLabel={
                  marketPriorityPanelSummary.badgeLabel ??
                  (strategyScorePayload?.primary_horizon === "return_1d"
                    ? "T+1"
                    : strategyScorePayload?.primary_horizon === "return_20d"
                      ? "T+20"
                      : "T+5")
                }
                summary={marketPriorityPanelSummary}
                summaryTestId="stock-analysis-market-priority-panel-summary"
                expanded={isStrategyCardExpanded("market-priority")}
                onToggleExpand={() => toggleStrategyCard("market-priority")}
                mountDetail
                sectionRef={strategyPrioritySection.ref}
                sectionTestId="stock-analysis-market-priority-summary"
              >
                {strategyScoreQuery.isLoading ? (
                  <p className="stock-analysis-page__empty">当前市场策略优先级加载中。</p>
                ) : null}
                {strategyScoreQuery.isError ? (
                  <p className="stock-analysis-page__notice">
                    当前市场策略优先级暂不可用：{strategyPanelErrorMessage(strategyScoreQuery.error)}
                  </p>
                ) : null}
                {!strategyScoreQuery.isLoading && !strategyScoreQuery.isError ? (
                  <>
                    <div
                      className="stock-analysis-page__filter-status"
                      data-testid="stock-analysis-market-priority-current"
                    >
                      <span>
                        {localizeMarketDataStatus(
                          strategyScorePayload?.current_market_state ?? currentMarketState,
                        )}
                      </span>
                      <strong>{strategyPriorityHeadline}</strong>
                      <small>
                        {strategyPriorityReason} · 阈值 {strategyScorePayload?.min_sample ?? 20} · 只读排序
                      </small>
                    </div>
                    {strategyPriorityRows.length > 0 ? (
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
                            {strategyPriorityRows.map((row) => {
                              const diagnosticLabels = strategyPriorityDiagnosticLabels(row);
                              return (
                                <tr
                                  key={`${row.market_state}:${row.signal_kind}`}
                                  data-testid={`stock-analysis-market-priority-row-${row.market_state}-${row.signal_kind}`}
                                >
                                  <td>{strategyDisplayLabel(row.strategy_label, row.signal_kind)}</td>
                                  <td>{strategyPriorityStatusLabel(row.priority_label)}</td>
                                  <td className="stock-analysis-page__table-number" data-testid="stock-analysis-market-priority-score">
                                    {formatPriorityScore(row.priority_score)}
                                  </td>
                                  {strategyBacktestHorizons.map((horizon) => (
                                    <td className="stock-analysis-page__table-number" key={horizon}>
                                      {backtestStatsText(row.stats[horizon])}
                                    </td>
                                  ))}
                                  <td>
                                    <span>{strategyPriorityReasonLabel(row)}</span>
                                    {diagnosticLabels.length > 0 ? (
                                      <div className="stock-analysis-page__strategy-diagnostic-tags">
                                        {diagnosticLabels.map((label) => (
                                          <span key={label}>{label}</span>
                                        ))}
                                      </div>
                                    ) : null}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="stock-analysis-page__empty">样本不足</p>
                    )}
                    {strategyMaturityRow && strategyMaturity && strategyMaturitySnapshots.length > 0 ? (
                      <div data-testid="stock-analysis-candidate-maturity">
                        <div className="stock-analysis-page__filter-status">
                          <span>当前候选成熟进度</span>
                          <strong>
                            {strategyDisplayLabel(strategyMaturityRow.strategy_label, strategyMaturityRow.signal_kind)}
                            {strategyMaturityRow.diagnostics?.priority_scope_label
                              ? ` / ${strategyPriorityScopeLabel(strategyMaturityRow.diagnostics.priority_scope_label)}`
                              : ""}
                          </strong>
                          <small>
                            {strategyMaturityRemainingText(strategyMaturity)}，
                            {localizeStockBackendText(strategyMaturity.reason, strategyMaturityRow.signal_kind)}
                          </small>
                        </div>
                        <div className="stock-analysis-page__table-wrap">
                          <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                            <thead>
                              <tr>
                                <th scope="col">快照</th>
                                <th className="stock-analysis-page__table-number" scope="col">
                                  候选
                                </th>
                                {strategyBacktestHorizons.map((horizon) => (
                                  <th scope="col" key={horizon}>
                                    {strategyBacktestHorizonShortLabels[horizon]}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {strategyMaturitySnapshots.map((snapshot) => (
                                <tr key={snapshot.snapshot_as_of_date}>
                                  <td>{snapshot.snapshot_as_of_date}</td>
                                  <td className="stock-analysis-page__table-number">{snapshot.candidate_count}</td>
                                  {strategyBacktestHorizons.map((horizon) => (
                                    <td key={horizon}>{strategyMaturityHorizonText(snapshot, horizon)}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        <div className="stock-analysis-page__filter-status">
                          <span>候选明细</span>
                          <strong>
                            {strategyDisplayLabel(strategyMaturityRow.strategy_label, strategyMaturityRow.signal_kind)}
                          </strong>
                          <small>快照明细 · 按排名</small>
                        </div>
                        {strategyMaturityDetailQuery.isLoading ? (
                          <p className="stock-analysis-page__empty">候选明细加载中。</p>
                        ) : null}
                        {strategyMaturityDetailQuery.isError ? (
                          <p className="stock-analysis-page__notice">
                            候选明细暂不可用：{strategyPanelErrorMessage(strategyMaturityDetailQuery.error)}
                          </p>
                        ) : null}
                        {!strategyMaturityDetailQuery.isLoading && !strategyMaturityDetailQuery.isError ? (
                          strategyMaturityCandidateRows.length > 0 ? (
                            <div className="stock-analysis-page__table-wrap">
                              <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                                <thead>
                                  <tr>
                                    <th scope="col">快照</th>
                                    <th scope="col">排名</th>
                                    <th scope="col">候选</th>
                                    <th scope="col">板块</th>
                                    <th className="stock-analysis-page__table-number" scope="col">
                                      T+1
                                    </th>
                                    <th className="stock-analysis-page__table-number" scope="col">
                                      T+5
                                    </th>
                                    <th className="stock-analysis-page__table-number" scope="col">
                                      T+20
                                    </th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {strategyMaturityCandidateRows.map((candidate) => (
                                    <tr key={`${candidate.snapshot_as_of_date}:${candidate.stock_code}:${candidate.candidate_rank}`}>
                                      <td>{candidate.snapshot_as_of_date}</td>
                                      <td>#{candidate.candidate_rank}</td>
                                      <td>
                                        <span>{candidate.stock_name ?? candidate.stock_code}</span>
                                        <small> {candidate.stock_code}</small>
                                      </td>
                                      <td>{candidate.sector_name ?? "-"}</td>
                                      <td className="stock-analysis-page__table-number">
                                        {strategyCandidateReturnText(candidate.return_1d)}
                                      </td>
                                      <td className="stock-analysis-page__table-number">
                                        {strategyCandidateReturnText(candidate.return_5d)}
                                      </td>
                                      <td className="stock-analysis-page__table-number">
                                        {strategyCandidateReturnText(candidate.return_20d)}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <p className="stock-analysis-page__empty">当前可见快照暂无候选明细。</p>
                          )
                        ) : null}
                      </div>
                    ) : null}
                  </>
                ) : null}
              </StrategyModuleCard>

              <StrategyModuleCard
                id="strategy-backtest"
                title="策略回溯表现"
                subtitle="回溯胜率"
                badgeLabel={strategyBacktestPanelSummary.badgeLabel ?? strategyBacktestDateRangeLabel}
                summary={strategyBacktestPanelSummary}
                summaryTestId="stock-analysis-strategy-backtest-panel-summary"
                expanded={isStrategyCardExpanded("strategy-backtest")}
                onToggleExpand={() => toggleStrategyCard("strategy-backtest")}
                mountDetail
                sectionRef={strategyBacktestSection.ref}
                sectionTestId="stock-analysis-strategy-backtest"
              >
                {strategyBacktestQuery.isLoading ? (
                  <p className="stock-analysis-page__empty">策略回溯表现加载中。</p>
                ) : null}
                {strategyBacktestQuery.isError ? (
                  <p className="stock-analysis-page__notice">
                    策略回溯表现暂不可用：{strategyPanelErrorMessage(strategyBacktestQuery.error)}
                  </p>
                ) : null}
                {!strategyBacktestQuery.isLoading && !strategyBacktestQuery.isError ? (
                  <>
                    <div className="stock-analysis-page__filter-status">
                      <span>有效样本</span>
                      <strong>{strategyBacktestSampleCount} 条</strong>
                      <small>
                        完成日期 {strategyBacktestWindow?.replay_dates_completed ?? 0} / 待成熟{" "}
                        {strategyBacktestWindow?.replay_dates_pending ?? 0} / 不支持{" "}
                        {strategyBacktestWindow?.replay_dates_unsupported ?? 0}
                      </small>
                    </div>
                    <div className="stock-analysis-page__table-wrap">
                      <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                        <thead>
                          <tr>
                            <th scope="col">策略</th>
                            <th scope="col">入选数</th>
                            {strategyBacktestHorizons.map((horizon) => (
                              <th scope="col" key={horizon}>
                                {strategyBacktestHorizonLabels[horizon]}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {strategyBacktestRows.map((row) => (
                            <tr key={row.kind} data-testid={`stock-analysis-strategy-backtest-${row.kind}`}>
                              <td>{row.label}</td>
                              <td className="stock-analysis-page__table-number">{row.count}</td>
                              {strategyBacktestHorizons.map((horizon) => (
                                <td className="stock-analysis-page__table-number" key={horizon}>
                                  {row.stats[horizon]}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {strategyBacktestMarketStateRows.length > 0 ? (
                      <div data-testid="stock-analysis-strategy-backtest-market-state">
                        <p className="stock-analysis-page__footnote">市场状态分段</p>
                        <div className="stock-analysis-page__table-wrap">
                          <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                            <thead>
                              <tr>
                                <th scope="col">市场状态</th>
                                <th scope="col">策略</th>
                                {strategyBacktestHorizons.map((horizon) => (
                                  <th scope="col" key={horizon}>
                                    {strategyBacktestHorizonLabels[horizon]}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {strategyBacktestMarketStateRows.map((row) => (
                                <tr
                                  key={`${row.marketState}:${row.kind}`}
                                  data-testid={`stock-analysis-strategy-backtest-market-state-${row.marketState}-${row.kind}`}
                                >
                                  <td>{localizeMarketDataStatus(row.marketState)}</td>
                                  <td>{row.label}</td>
                                  {strategyBacktestHorizons.map((horizon) => (
                                    <td className="stock-analysis-page__table-number" key={horizon}>
                                      {row.stats[horizon]}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    ) : null}
                  </>
                ) : null}
              </StrategyModuleCard>

              <StrategyModuleCard
                id="strategy-optimization"
                title="优化诊断"
                subtitle="切片 T+5"
                badgeLabel={
                  strategyOptimizationPanelSummary.badgeLabel ??
                  (strategyOptimizationPayload?.primary_horizon === "return_1d"
                    ? "T+1"
                    : strategyOptimizationPayload?.primary_horizon === "return_10d"
                      ? "T+10"
                      : strategyOptimizationPayload?.primary_horizon === "return_20d"
                        ? "T+20"
                        : "T+5")
                }
                summary={strategyOptimizationPanelSummary}
                summaryTestId="stock-analysis-strategy-optimization-panel-summary"
                expanded={isStrategyCardExpanded("strategy-optimization")}
                onToggleExpand={() => toggleStrategyCard("strategy-optimization")}
                mountDetail
                sectionRef={strategyOptimizationSection.ref}
                sectionTestId="stock-analysis-strategy-optimization"
              >
                {strategyOptimizationQuery.isLoading ? (
                  <p className="stock-analysis-page__empty">优化诊断加载中。</p>
                ) : null}
                {strategyOptimizationQuery.isError ? (
                  <p className="stock-analysis-page__notice">
                    优化诊断暂不可用：{strategyPanelErrorMessage(strategyOptimizationQuery.error)}
                  </p>
                ) : null}
                {!strategyOptimizationQuery.isLoading && !strategyOptimizationQuery.isError ? (
                  <>
                    <div className="stock-analysis-page__filter-status">
                      <span>当前最新日期收益</span>
                      <strong>
                        {(strategyOptimizationPayload?.pending_summary.pending_rows ?? 0) > 0
                          ? "待成熟"
                          : "已成熟"}
                      </strong>
                      <small>
                        {localizeStockBackendText(
                          strategyOptimizationPayload?.pending_summary.message ?? "T+5 收益成熟状态待补。",
                        )}
                      </small>
                    </div>
                    <p className="stock-analysis-page__footnote">
                      复核排序 · 不改规则
                    </p>
                    <div className="stock-analysis-page__filter-status">
                      <span>三策略 T+5 排名</span>
                      <strong>{strategyOptimizationRows.length} 组</strong>
                      <small>阈值 {strategyOptimizationPayload?.min_sample ?? 20} · 收益/胜率/成熟度</small>
                    </div>
                    {strategyOptimizationRows.length > 0 ? (
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
                              <tr key={row.summary_key}>
                                <td>{strategyDisplayLabel(row.strategy_label, row.signal_kind)}</td>
                                <td>{strategyPriorityStatusLabel(row.recommendation.priority_label)}</td>
                                <td className="stock-analysis-page__table-number">
                                  {backtestStatsText(strategyOptimizationPrimaryStats(row, strategyOptimizationPayload))}
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
                      <p className="stock-analysis-page__empty">优化诊断样本不足。</p>
                    )}
                    <div className="stock-analysis-page__filter-status">
                      <span>各策略最强/最弱切片</span>
                      <strong>
                        {strategyOptimizationSlices.strongest
                          ? strategyOptimizationSliceLabel(strategyOptimizationSlices.strongest)
                          : "最强待补"}{" "}
                        /{" "}
                        {strategyOptimizationSlices.weakest
                          ? strategyOptimizationSliceLabel(strategyOptimizationSlices.weakest)
                          : "最弱待补"}
                      </strong>
                      <small>
                        {strategyOptimizationSlices.weakest
                          ? `${strategyDisplayLabel(
                              strategyOptimizationSlices.weakest.strategy_label,
                              strategyOptimizationSlices.weakest.signal_kind,
                            )} ${strategyOptimizationSliceLabel(
                              strategyOptimizationSlices.weakest,
                            )}：${strategyPriorityStatusLabel(
                              strategyOptimizationSlices.weakest.recommendation.priority_label,
                            )}`
                          : "切片样本不足，暂不做降权判断。"}
                      </small>
                    </div>
                    {strategyOptimizationSlices.strongest || strategyOptimizationSlices.weakest ? (
                      <div className="stock-analysis-page__table-wrap">
                        <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                          <thead>
                            <tr>
                              <th scope="col">切片</th>
                              <th scope="col">策略</th>
                              <th scope="col">复核状态</th>
                              <th scope="col">T+5 收益</th>
                            </tr>
                          </thead>
                          <tbody>
                            {([
                              ["最强", strategyOptimizationSlices.strongest],
                              ["最弱", strategyOptimizationSlices.weakest],
                            ] as Array<[string, StrategyOptimizationSlice | null]>).map(([label, slice]) =>
                              slice ? (
                                <tr key={`${label}:${slice.slice_key}`}>
                                  <td>
                                    {label}：{strategyOptimizationSliceLabel(slice)}
                                  </td>
                                  <td>{strategyDisplayLabel(slice.strategy_label, slice.signal_kind)}</td>
                                  <td>{strategyPriorityStatusLabel(slice.recommendation.priority_label)}</td>
                                  <td className="stock-analysis-page__table-number">
                                    {backtestStatsText(strategyOptimizationPrimaryStats(slice, strategyOptimizationPayload))}
                                  </td>
                                </tr>
                              ) : null,
                            )}
                          </tbody>
                        </table>
                      </div>
                    ) : null}
                  </>
                ) : null}
              </StrategyModuleCard>

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
                          <div className="mt-2 flex flex-wrap gap-1.5" aria-label="超跌筛选规则">
                            {["价格回撤", "企稳", "放量", "门控停用"].map((label) => (
                              <span
                                key={label}
                                className="inline-flex items-center gap-1 rounded-md border border-neutral-200 bg-white px-2 py-1 text-[11px] font-semibold text-neutral-600"
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
                          <div className="mt-2 flex flex-wrap gap-1.5" aria-label="多因子选股因子">
                            {["价值", "质量", "动量", "低波", "股息"].map((label) => (
                              <span
                                key={label}
                                className="inline-flex items-center gap-1 rounded-md border border-neutral-200 bg-white px-2 py-1 text-[11px] font-semibold text-neutral-600"
                              >
                                <DatabaseOutlined aria-hidden="true" /> {label}
                              </span>
                            ))}
                            {factorScreenCoverageNote ? (
                              <span
                                className="inline-flex items-center gap-1 rounded-md border border-primary-100 bg-primary-50 px-2 py-1 text-[11px] font-bold text-primary-700"
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
      </main>
    </PageV2Shell>
  );
}
