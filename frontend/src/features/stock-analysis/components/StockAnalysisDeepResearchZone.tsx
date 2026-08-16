import { lazy, Suspense, useMemo, useState, type Dispatch, type SetStateAction } from "react";

import type { ApiClient } from "../../../api/client";
import type {
  BacktestWindowSummary,
  LivermoreCandidateHistoryPayload,
  LivermoreCandidateHistoryPortfolioBacktestPayload,
  LivermoreCycleProxyBacktestPayload,
  LivermoreSectorRankSeriesPoint,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyOptimizationPayload,
  LivermoreStrategyPayload,
  LivermoreStrategyScorePayload,
} from "../../../api/contracts";
import { AnalysisGrid } from "../../../components/page/PagePrimitives";
import { TableSkeleton, TextSkeleton } from "../../../components/Skeletons";
import type { EChartsOption } from "../../../lib/echarts";
import { EM_DASH } from "../../../utils/format";
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

import { StockAnalysisBacktestCaliberDisclosure } from "./StockAnalysisBacktestCaliberDisclosure";
import {
  StockAnalysisAccordion as Accordion,
  StockAnalysisAccordionItem as AccordionItem,
} from "./StockAnalysisAccordion";
import { CompactStatusTile } from "./StockAnalysisStatusPrimitives";
import { StockAnalysisStrategyLensSection } from "./StockAnalysisStrategyLensSection";
import { StockAnalysisWalkForwardPanel } from "./StockAnalysisWalkForwardPanel";
import { useStockHeavyweightSection } from "../hooks/useStockHeavyweightSection";
import { buildConsensusSummary, consensusStrategyLabel, lookupStockStrategyRanks } from "../lib/buildConsensusSummary";
import {
  buildBacktestCaliberDisclosure,
  buildStrategyBacktestRows,
  formatBacktestSignedPercent,
  resolveStrategyBacktestSampleCount,
  strategyBacktestHorizonLabels,
  strategyBacktestHorizons,
  strategyDisplayLabel,
} from "../lib/stockAnalysisBacktestModel";
import { buildSectorStrengthOption, sectorViewTabs } from "../lib/stockAnalysisChartModel";
import {
  buildConsensusDetailSelection,
  buildFactorScreenDetailSelection,
  buildMeanReversionDetailSelection,
  buildRankContextDetailSelection,
  type StockDetailSelection,
} from "../lib/stockAnalysisDetailSelection";
import {
  buildConsensusReviewPanelSummary,
  buildCycleRotationPanelSummary,
  buildDeepAnalysisGateSummary,
  buildDeepZoneAuditRows,
  buildEventsMonitoringPanelSummary,
  buildMarketPriorityPanelSummary,
  buildObservationPoolsPanelSummary,
  buildStrategyBacktestPanelSummary,
  buildStrategyOptimizationPanelSummary,
  buildThemeBreakoutCards,
  buildThemeBreakoutPanelSummary,
  buildThemeBreakoutReviewItems,
  buildThemeEvidenceStateRows,
  buildThemeLeaderPreviewItems,
} from "../lib/stockAnalysisDeepResearchPanelsModel";
import {
  buildCycleMacroLayerSummary,
  buildSectorTableSortComparator,
  buildSectorViewRows,
  buildStockAnalysisEventMonitorRows,
  buildStockSectorOverviewState,
  buildStrategyLensItems,
  isStockModulePrimaryExcluded,
  localizeImplementationStage,
  localizeStockBackendText,
  localizeThemeRadarBadge,
  type StockSectorRow,
  type StockSectorViewKind,
} from "../lib/stockAnalysisPageModel";
import {
  buildThemeBreakoutBlockerCopy,
  compactStockText as compactText,
  rawStockErrorMessage as rawErrorMessage,
  stockStrategyPanelErrorMessage as strategyPanelErrorMessage,
} from "../lib/stockAnalysisPageCopy";
import {
  cycleBoundaryLabel,
  cycleConstraintLabel,
  cycleEvidenceLabel,
  cycleGapLabel,
  cycleInputSummary,
  cycleLayerTitleLabel,
  cycleLayerWeightLabel,
  eventDetailLabel,
  eventImpactLabel,
  eventLevelLabel,
  eventNameLabel,
  eventSourceLabel,
} from "../lib/stockAnalysisPageLabels";
import {
  SA_CARD_TITLE,
  SA_FIRST_CARD,
  SA_PILL,
  SA_SECTION_DESC,
  SA_SECTION_EYEBROW,
  SA_SECTION_HEAD,
} from "../lib/stockAnalysisPageChrome";
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
  type SectorSeriesTrendLine,
} from "../lib/stockAnalysisSectorSeriesModel";
import { EMPTY_STRATEGY_PRIORITY_ROWS } from "../lib/stockAnalysisQueryOptions";
import type { SectorSeriesWindow } from "../hooks/useSectorPanelState";
import { useSectorSortState } from "../hooks/useSectorSortState";
import type { StockAnalysisKlineRadarItem } from "../lib/stockAnalysisKlineRadarModel";

const SECTOR_STRENGTH_DEFAULT_TOP_COUNT = 3;

const LazyReactECharts = lazy(() => import("../../../lib/echarts"));
const LazyStockAnalysisDeepZoneHeader = lazy(() =>
  import("./StockAnalysisDeepZoneHeader").then((module) => ({
    default: module.StockAnalysisDeepZoneHeader,
  })),
);
const LazyStockAnalysisConsensusFirstScreen = lazy(() =>
  import("./StockAnalysisConsensusFirstScreen").then((module) => ({
    default: module.StockAnalysisConsensusFirstScreen,
  })),
);
const LazyStockAnalysisKlineRadarPanel = lazy(() =>
  import("./StockAnalysisKlineRadarPanel").then((module) => ({
    default: module.StockAnalysisKlineRadarPanel,
  })),
);
const LazyStockAnalysisObservationPreview = lazy(() =>
  import("./StockAnalysisObservationPreview").then((module) => ({
    default: module.StockAnalysisObservationPreview,
  })),
);
const LazyStockAnalysisDeepSelectionOverview = lazy(() =>
  import("./StockAnalysisDeepSelectionOverview").then((module) => ({
    default: module.StockAnalysisDeepSelectionOverview,
  })),
);
const LazyStockAnalysisStrategyReviewCards = lazy(() =>
  import("./StockAnalysisStrategyReviewCards").then((module) => ({
    default: module.StockAnalysisStrategyReviewCards,
  })),
);
const LazyStockAnalysisThemeGroupedView = lazy(() =>
  import("./StockAnalysisThemeGroupedView").then((module) => ({
    default: module.StockAnalysisThemeGroupedView,
  })),
);
const loadStockAnalysisDeepResearchPrimitives = () =>
  import("./StockAnalysisDeepResearchPrimitives");
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

type PanelQuerySlice = {
  isLoading: boolean;
  isFetching: boolean;
  isError: boolean;
  error: unknown;
};

type SectorSeriesQuerySlice = PanelQuerySlice & {
  data?: { result?: { state?: string } | null } | null;
};

type DeferredSectionSlice = {
  ref: (node: HTMLElement | null) => void;
  seen: boolean;
};

export type StockAnalysisDeepResearchZoneProps = {
  strategyPayload: LivermoreStrategyPayload | null;
  confluencePayload: LivermoreSignalConfluencePayload | null;
  client: ApiClient;
  analyticsAsOf: string | null;
  currentMarketState: string | null;
  queueTotalCount: number;
  setDetailSelection: Dispatch<SetStateAction<StockDetailSelection | null>>;
  scrollToStockSection: (targetId: string) => void;
  strategyScoreQuery: PanelQuerySlice;
  strategyScorePayload: LivermoreStrategyScorePayload | null;
  strategyOptimizationQuery: PanelQuerySlice;
  strategyOptimizationPayload: LivermoreStrategyOptimizationPayload | null;
  strategyBacktestQuery: PanelQuerySlice;
  strategyBacktestPayload: LivermoreCandidateHistoryPayload | null;
  strategyBacktestWindow: BacktestWindowSummary | null;
  strategyBacktestSnapshotFrom: string | null;
  cycleProxyBacktestQuery: PanelQuerySlice;
  cycleProxyBacktestPayload: LivermoreCycleProxyBacktestPayload | null;
  candidateHistoryPortfolioBacktestQuery: PanelQuerySlice;
  candidateHistoryPortfolioBacktestPayload: LivermoreCandidateHistoryPortfolioBacktestPayload | null;
  sectorRankSeriesQuery: SectorSeriesQuerySlice;
  cycleFrameworkSection: DeferredSectionSlice;
  strategyPrioritySection: DeferredSectionSlice;
  strategyBacktestSection: DeferredSectionSlice;
  strategyOptimizationSection: DeferredSectionSlice;
  cycleProxyEndpointRequested: boolean;
  portfolioProxyEndpointRequested: boolean;
  candidateHistoryEndpointRequested: boolean;
  firstScreenAnalyticsTab: string;
  firstScreenAnalyticsRequested: boolean;
  firstScreenPriorityRequested: boolean;
  firstScreenOptimizationRequested: boolean;
  handleFirstScreenAnalyticsTabChange: (key: string) => void;
  isStrategyCardExpanded: (id: string) => boolean;
  toggleStrategyCard: (id: string) => void;
  sectorView: StockSectorViewKind;
  handleSectorViewChange: (key: string) => void;
  sectorFilterSectorCode: string | null;
  toggleSectorFilter: (code: string | null) => void;
  sectorRowsFull: StockSectorRow[];
  sectorRowsSourceLabel: string;
  sectorLeaderRow: StockSectorRow | null;
  sectorTailRow: StockSectorRow | null;
  sectorCoverageCount: number;
  sectorSeriesCollapseKeys: string[];
  handleSectorSeriesCollapseChange: (keys: string | string[]) => void;
  sectorSeriesWindow: SectorSeriesWindow;
  handleSectorSeriesWindowChange: (key: string) => void;
  sectorSeriesUnsupportedNotes: string[];
  sectorSeriesTrendLines: SectorSeriesTrendLine[];
  sectorSeriesTrendChartOption: EChartsOption;
  sectorSeriesTableRows: LivermoreSectorRankSeriesPoint[];
};

export function StockAnalysisDeepResearchZone({
  strategyPayload,
  confluencePayload,
  client,
  analyticsAsOf,
  currentMarketState,
  queueTotalCount,
  setDetailSelection,
  scrollToStockSection,
  strategyScoreQuery,
  strategyScorePayload,
  strategyOptimizationQuery,
  strategyOptimizationPayload,
  strategyBacktestQuery,
  strategyBacktestPayload,
  strategyBacktestWindow,
  strategyBacktestSnapshotFrom,
  cycleProxyBacktestQuery,
  cycleProxyBacktestPayload,
  candidateHistoryPortfolioBacktestQuery,
  candidateHistoryPortfolioBacktestPayload,
  sectorRankSeriesQuery,
  cycleFrameworkSection,
  strategyPrioritySection,
  strategyBacktestSection,
  strategyOptimizationSection,
  cycleProxyEndpointRequested,
  portfolioProxyEndpointRequested,
  candidateHistoryEndpointRequested,
  firstScreenAnalyticsTab,
  firstScreenAnalyticsRequested,
  firstScreenPriorityRequested,
  firstScreenOptimizationRequested,
  handleFirstScreenAnalyticsTabChange,
  isStrategyCardExpanded,
  toggleStrategyCard,
  sectorView,
  handleSectorViewChange,
  sectorFilterSectorCode,
  toggleSectorFilter,
  sectorRowsFull,
  sectorRowsSourceLabel,
  sectorLeaderRow,
  sectorTailRow,
  sectorCoverageCount,
  sectorSeriesCollapseKeys,
  handleSectorSeriesCollapseChange,
  sectorSeriesWindow,
  handleSectorSeriesWindowChange,
  sectorSeriesUnsupportedNotes,
  sectorSeriesTrendLines,
  sectorSeriesTrendChartOption,
  sectorSeriesTableRows,
}: StockAnalysisDeepResearchZoneProps) {
  const gateState = strategyPayload?.market_gate.state;
  const meanReversionPayload = strategyPayload?.mean_reversion_candidates;
  const meanReversionMarketActive = gateState === "WARM";
  const factorScreenPayload = strategyPayload?.factor_screen_candidates;
  const factorScreenPrimaryExcluded = isStockModulePrimaryExcluded(strategyPayload, "factor_screen_candidates");
  const factorScreenCoverageNote =
    !factorScreenPrimaryExcluded && factorScreenPayload?.coverage_note
      ? localizeStockBackendText(factorScreenPayload.coverage_note, "factor_screen_candidates")
      : null;
  const hybridFusionPayload = strategyPayload?.hybrid_fusion_candidates;
  const hybridFusionObservationCandidateCount = hybridFusionPayload?.candidate_count ?? 0;
  const factorScreenObservationCandidateCount = factorScreenPayload?.candidate_count ?? 0;
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
  const [sectorDetailOpen, setSectorDetailOpen] = useState(false);
  const { sectorSort, toggleSort, renderSortSuffix } = useSectorSortState();
  const sectorViewRows = useMemo(
    () => buildSectorViewRows(sectorRowsFull, sectorView),
    [sectorRowsFull, sectorView],
  );
  const sortedDetailRows = useMemo(() => {
    const cmp = buildSectorTableSortComparator(sectorSort.key, sectorSort.order);
    return [...sectorRowsFull].sort(cmp);
  }, [sectorRowsFull, sectorSort]);
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
  const sectorViewOverview = useMemo(() => buildStockSectorOverviewState(sectorViewRows), [sectorViewRows]);
  const { topBars, bottomBars } = sectorViewOverview;
  const visibleSectorTopBars = topBars.slice(0, SECTOR_STRENGTH_DEFAULT_TOP_COUNT);
  const backgroundSectorTopBars = topBars.slice(SECTOR_STRENGTH_DEFAULT_TOP_COUNT);
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
  const themeBreakoutCards = useMemo(
    () =>
      strategyPayload ? buildThemeBreakoutCards(strategyPayload) : [],
    [strategyPayload],
  );

  const themeLeaderPreviewItems = useMemo(
    () => buildThemeLeaderPreviewItems(themeBreakoutCards, 12),
    [themeBreakoutCards],
  );

  const heavyweight = useStockHeavyweightSection({ strategyPayload, deepResearchOpen: true });

  const themeEvidenceRows = useMemo(
    () =>
      strategyPayload ? buildThemeEvidenceStateRows(strategyPayload) : [],
    [strategyPayload],
  );

  const themeBreakoutReviewItems = useMemo(
    () =>
      strategyPayload ? buildThemeBreakoutReviewItems(strategyPayload) : [],
    [strategyPayload],
  );
  const themeBreakoutUnsupported = strategyPayload?.unsupported_outputs.find((output) => output.key === "theme_breakout");
  const themeBreakoutBlockerCopy = buildThemeBreakoutBlockerCopy(themeBreakoutUnsupported);
  const themeBreakoutBlockerText = themeBreakoutBlockerCopy.text;
  const themeBreakoutBlockerLabel = themeBreakoutBlockerCopy.label;

  const eventMonitorRows = useMemo(
    () => (strategyPayload ? buildStockAnalysisEventMonitorRows(strategyPayload, confluencePayload) : []),
    [strategyPayload, confluencePayload],
  );
  const strategyOptimizationPrimaryHorizonLabel = strategyOptimizationHorizonLabel(
    strategyOptimizationPayload,
  );
  const strategyOptimizationRows = useMemo(
    () => buildStrategyOptimizationRows(strategyOptimizationPayload),
    [strategyOptimizationPayload],
  );
  const strategyPriorityRows = strategyScorePayload?.current_market_state_rows ?? EMPTY_STRATEGY_PRIORITY_ROWS;
  const strategyBacktestRows = useMemo(() => buildStrategyBacktestRows(strategyBacktestPayload), [strategyBacktestPayload]);
  const strategyBacktestSampleCount = useMemo(
    () => resolveStrategyBacktestSampleCount(strategyBacktestPayload),
    [strategyBacktestPayload],
  );
  const cycleProxyBacktestCaliberDisclosure = useMemo(
    () => buildBacktestCaliberDisclosure(cycleProxyBacktestPayload),
    [cycleProxyBacktestPayload],
  );
  const candidateHistoryPortfolioBacktestCaliberDisclosure = useMemo(
    () => buildBacktestCaliberDisclosure(candidateHistoryPortfolioBacktestPayload),
    [candidateHistoryPortfolioBacktestPayload],
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
      strategyPayload
        ? buildThemeBreakoutPanelSummary({
            payload: strategyPayload,
            cards: themeBreakoutCards,
            reviewCount: themeBreakoutReviewItems.length,
            unsupportedReason: themeBreakoutUnsupported?.reason,
          })
        : null,
    [
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

  return (
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
                                        {row.sectorName || EM_DASH}
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
                                            {row.rank ?? EM_DASH}
                                          </td>
                                          <td className="stock-analysis-page__table-number">
                                            {formatSectorSeriesCumPctChange(row.cum_pctchange_window)}
                                          </td>
                                          <td className="stock-analysis-page__table-number">
                                            {row.constituent_count ?? EM_DASH}
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
                                        {row.sectorName || EM_DASH}
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
                                        {row.sector_name || row.sector_code || EM_DASH}
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
                                      {row.sector_name || row.industry || EM_DASH}
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
  );
}
