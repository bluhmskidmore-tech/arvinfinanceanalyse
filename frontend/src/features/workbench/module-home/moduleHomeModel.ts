import type {
  ModuleHomeTone,
  ModuleHomeDetailPanel,
} from "./moduleHomeDetailTypes";
import type { ModuleWorkbenchHomeKind } from "./moduleHomeConfig";
import type {
  VolumeRateAttributionPayload,
  ApiEnvelope,
  BalanceAnalysisDatesPayload,
  BalanceAnalysisPublicationStatusPayload,
  BalanceAnalysisOverviewPayload,
  BondAnalyticsDatesPayload,
  BondDashboardHeadlinePayload,
  RiskIndicatorsPayload,
  AssetStructurePayload,
  MaturityStructurePayload,
  IndustryDistPayload,
  YieldDistributionPayload,
  PortfolioComparisonPayload,
  SpreadAnalysisPayload,
  BondBusinessTypeMetricsPayload,
  BalanceAnalysisBasisBreakdownPayload,
  PnlAttributionAnalysisSummary,
  ChoiceMacroLatestPayload,
  MarketOverviewSnapshotPayload,
  MacroVendorPayload,
  RiskTensorDatesPayload,
  RiskTensorPayload,
  CashflowProjectionPayload,
  KpiOwnerListResponse,
  KpiPeriodSummaryResponse,
  PnlByBusinessYtdPayload,
  HealthStatusResponse,
  SourcePreviewPayload,
  CubeDimensionsPayload,
  ChoiceNewsEventsPayload,
} from "../../../api/contracts";
import type { StateSurfaceItem } from "../../../pageModel";
import type {
  MarketCrisisExplainView,
  MarketDeskIntelView,
} from "./marketDeskIntelModel";
import type { UseQueryResult } from "@tanstack/react-query";
import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitStrategySummariesPayload,
} from "../../../api/macroToolkitClient";
import type { ApiClient } from "../../../api/client";
import { moduleWorkbenchHomeConfigs } from "./moduleHomeConfig";
import { guardMockPortfolioHomeView } from "./portfolioDecisionModel";
import { portfolioView } from "./portfolioHomeViewModel";
import { marketView } from "./marketHomeViewModel";
import { riskView } from "./riskHomeViewModel";
import { performanceView } from "./performanceHomeViewModel";
import { governanceView } from "./governanceHomeViewModel";

export { formatPanelMetaForHome } from "./moduleHomePresentation";
export {
  MARKET_CURVE_TERM_SPREAD_KEYS,
  findMarketCreditSpreadRow,
  buildMarketCurveSpreadRows,
} from "./marketHomeDetailModel";
export { MARKET_HOME_MACRO_SIGNAL_ORDER } from "./marketMacroToolkitHomeModel";
export type {
  ModuleHomeTone,
  ModuleHomeDetailRow,
  ModuleHomeDetailChart,
  ModuleHomeDetailSection,
  ModuleHomeDetailPanel,
} from "./moduleHomeDetailTypes";
export type {
  MarketCrisisExplainComponent,
  MarketCrisisExplainView,
  MarketCrisisHistoryPoint,
  MarketCrisisRiskGateView,
  MarketCrisisTrendView,
  MarketDeskIndicatorHighlight,
  MarketDeskIntelView,
} from "./marketDeskIntelModel";
export {
  buildMarketCrisisExplain,
  buildMarketDeskIntel,
} from "./marketDeskIntelModel";

export type ModuleHomeDataState = "loading" | "empty" | "error" | "partial" | "stale" | "ready";

export type ModuleHomeKpi = {
  key: string;
  label: string;
  value: string;
  detail: string;
  /** 端点/函数名等证据引用收进 tooltip（§7），不占正文版面。 */
  detailTitle?: string;
  coverageNote?: string;
  tone: ModuleHomeTone;
  /** 近两期读数，仅用于迷你走势展示（数据来自 API prev_kpis / recent_points） */
  sparkline?: readonly number[];
};

export type ModuleHomeStatus = {
  key: string;
  label: string;
  value: string;
  detail: string;
  tone: ModuleHomeTone;
};

export type ModuleHomeBriefing = {
  title: string;
  conclusion: string;
  evidence: string;
  tone: ModuleHomeTone;
};

export type ModuleHomeDataNote = {
  title: string;
  lines: string[];
  tone: ModuleHomeTone;
};

export type ModuleHomeDecision = {
  title: string;
  conclusion: string;
  detail: string;
  tone: ModuleHomeTone;
  facts: Array<{
    label: string;
    value: string;
    tone: ModuleHomeTone;
  }>;
  actions?: Array<{
    title: string;
    evidence: string;
    path: string;
    tone: ModuleHomeTone;
    label?: string;
  }>;
  readiness?: {
    decisionReady: boolean;
    riskClosureReady: boolean;
    blockingReasons: string[];
    warningReasons: string[];
    sourceFacts: string[];
    sourceDates: string;
    riskClosureFact: string;
  };
};

export type ModuleHomeDistributionRow = {
  key: string;
  label: string;
  marketValue: string;
  share: string;
  barPct: number;
  tone: ModuleHomeTone;
};

export type ModuleHomeDistributionPanel = {
  key: string;
  title: string;
  meta: string;
  stateLabel: string;
  stateDetail: string;
  rows: ModuleHomeDistributionRow[];
  tone: ModuleHomeTone;
  totalDisplay?: string;
  subtitle?: string;
  viewAllPath?: string;
};

export type ModuleHomeView = {
  kind: ModuleWorkbenchHomeKind;
  title: string;
  question: string;
  summary: string;
  sourceScope: string;
  /**
   * 页面级读链路状态。市场总览与绩效首页先行接入；其余存量首页未接入时
   * 继续由既有 stateLabel/stateDetail 驱动，避免跨页扩大本次改动。
   */
  dataState?: ModuleHomeDataState;
  stateLabel: string;
  stateDetail: string;
  kpis: ModuleHomeKpi[];
  statuses: ModuleHomeStatus[];
  briefings: ModuleHomeBriefing[];
  decision?: ModuleHomeDecision;
  distributionPanels?: ModuleHomeDistributionPanel[];
  detailPanels?: ModuleHomeDetailPanel[];
  /** 同源损益变动分解，包含利息量价、非利息直接变动与未解释差额。 */
  pnlWaterfall?: VolumeRateAttributionPayload;
  pnlWaterfallState?: StateSurfaceItem[];
  marketCrisisExplain?: MarketCrisisExplainView | null;
  marketDeskIntel?: MarketDeskIntelView | null;
  dataNote: ModuleHomeDataNote;
};

export type ModuleHomeViewBody = Omit<ModuleHomeView, "kind" | "title" | "question" | "summary" | "sourceScope">;

export type ModuleHomeSourceQueries = {
  balanceDates?: UseQueryResult<ApiEnvelope<BalanceAnalysisDatesPayload>>;
  balancePublicationStatus?: UseQueryResult<BalanceAnalysisPublicationStatusPayload>;
  balanceOverview?: UseQueryResult<ApiEnvelope<BalanceAnalysisOverviewPayload>>;
  bondDates?: UseQueryResult<ApiEnvelope<BondAnalyticsDatesPayload>>;
  bondHeadline?: UseQueryResult<ApiEnvelope<BondDashboardHeadlinePayload>>;
  bondRisk?: UseQueryResult<ApiEnvelope<RiskIndicatorsPayload>>;
  bondAssetType?: UseQueryResult<ApiEnvelope<AssetStructurePayload>>;
  bondAssetRating?: UseQueryResult<ApiEnvelope<AssetStructurePayload>>;
  bondMaturity?: UseQueryResult<ApiEnvelope<MaturityStructurePayload>>;
  bondIndustry?: UseQueryResult<ApiEnvelope<IndustryDistPayload>>;
  bondYield?: UseQueryResult<ApiEnvelope<YieldDistributionPayload>>;
  bondPortfolioComparison?: UseQueryResult<ApiEnvelope<PortfolioComparisonPayload>>;
  bondSpread?: UseQueryResult<ApiEnvelope<SpreadAnalysisPayload>>;
  bondBusinessType?: UseQueryResult<BondBusinessTypeMetricsPayload>;
  balanceBasis?: UseQueryResult<ApiEnvelope<BalanceAnalysisBasisBreakdownPayload>>;
  pnlSummary?: UseQueryResult<ApiEnvelope<PnlAttributionAnalysisSummary>>;
  pnlVolumeRate?: UseQueryResult<ApiEnvelope<VolumeRateAttributionPayload>>;
  choiceLatest?: UseQueryResult<ApiEnvelope<ChoiceMacroLatestPayload>>;
  marketSnapshot?: UseQueryResult<ApiEnvelope<MarketOverviewSnapshotPayload>>;
  marketRates?: UseQueryResult<ApiEnvelope<ChoiceMacroLatestPayload>>;
  marketCatalog?: UseQueryResult<ApiEnvelope<MacroVendorPayload>>;
  riskDates?: UseQueryResult<ApiEnvelope<RiskTensorDatesPayload>>;
  riskTensor?: UseQueryResult<ApiEnvelope<RiskTensorPayload>>;
  cashflow?: UseQueryResult<ApiEnvelope<CashflowProjectionPayload>>;
  kpiOwners?: UseQueryResult<KpiOwnerListResponse>;
  kpiSummary?: UseQueryResult<KpiPeriodSummaryResponse>;
  pnlYtd?: UseQueryResult<ApiEnvelope<PnlByBusinessYtdPayload>>;
  healthLive?: UseQueryResult<HealthStatusResponse>;
  healthSummary?: UseQueryResult<HealthStatusResponse>;
  sourceFoundation?: UseQueryResult<ApiEnvelope<SourcePreviewPayload>>;
  cubeDimensions?: UseQueryResult<CubeDimensionsPayload>;
  macroToolkitAnalysis?: UseQueryResult<ApiEnvelope<MacroToolkitAnalysisPayload>>;
  macroToolkitStrategySummaries?: UseQueryResult<ApiEnvelope<MacroToolkitStrategySummariesPayload>>;
  newsEvents?: UseQueryResult<ApiEnvelope<ChoiceNewsEventsPayload>>;
};

export function buildModuleHomeView(
  kind: ModuleWorkbenchHomeKind,
  client: Pick<ApiClient, "mode">,
  queries: ModuleHomeSourceQueries,
): ModuleHomeView {
  const config = moduleWorkbenchHomeConfigs[kind];
  const view =
    kind === "portfolio"
      ? client.mode === "mock"
        ? guardMockPortfolioHomeView(portfolioView(queries))
        : portfolioView(queries)
      : kind === "market"
        ? marketView(queries)
        : kind === "risk"
          ? riskView(queries)
          : kind === "performance"
            ? performanceView(queries)
            : governanceView(queries);

  return {
    kind,
    title: config.title,
    question: config.question,
    summary: config.summary,
    sourceScope: `${config.sourceScope} / ${client.mode === "real" ? "real" : "mock"}`,
    ...view,
  };
}
