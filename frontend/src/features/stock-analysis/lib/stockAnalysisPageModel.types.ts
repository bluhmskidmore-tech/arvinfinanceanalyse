// Shared view-model types for the stock-analysis page model.
import type {
  LivermoreCandidateHistoryPayload,
  LivermoreCandidateHistoryPortfolioBacktestPayload,
  LivermoreCycleProxyBacktestPayload,
  LivermoreSectorRankSeriesPayload,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyOptimizationPayload,
  LivermoreStrategyPayload,
  LivermoreStrategyScorePayload,
  ResultMeta,
} from "../../../api/contracts";
import type { StockDetailSource } from "./stockAnalysisDetailSelection";
import type { StockCandidateSignalWindowFields } from "./stockAnalysisSignalWindowModel";
import type { MarketGateMacroDisclosure } from "../../market-data/lib/livermoreStrategyModel";

export type StockMarketConditionRow = {
  key: string;
  label: string;
  status: string;
  evidence: string;
};

export type StockMarketStateCard = {
  title: string;
  state: string;
  exposureLabel: string;
  passedLabel: string;
  basisLabel: string;
  warnings: string[];
  conditions: StockMarketConditionRow[];
  macroDisclosure: MarketGateMacroDisclosure | null;
  macroDisclosureDetail: string | null;
};

/** 后端 pattern 展示文案；机器分类由 LivermoreStockCandidateItem.pattern_code 决定。 */
export type StockCandidatePattern = string;

export type StockCandidateEvidenceBullet = {
  key: string;
  label: string;
  value: string;
  /**
   * 后端原始数值（后端单位，未经格式化）。只有数值来源字段才带；文本字段缺省。
   * 下游需要数值时优先读它，禁止从 `value` 字符串反解析。
   */
  numeric?: number | null;
};

/** 候选原始字段：与证据条目同形，`numeric` 是唯一可用于计算的数值来源。 */
export type StockCandidateRawField = StockCandidateEvidenceBullet;

/** 复核队列候选的来源池；决定卡片上的来源标签与 walk-forward 判定。
 * workbench_review_queue 是后端首屏队列的兜底来源（该接口不返回池级 walk_forward）。 */
export type StockCandidateSourcePool =
  | "theme_breakout"
  | "hybrid_fusion"
  | "stock_candidates"
  | "fresh_trend_watchlist"
  | "factor_screen_candidates"
  | "uptrend_momentum_candidates"
  | "mean_reversion_candidates"
  | "workbench_review_queue";

export type StockCandidateEvidenceCard = {
  rank: number;
  stockCode: string;
  stockName: string;
  sectorCode: string;
  sectorName: string;
  headline: string;
  /** 候选来自哪个策略池；队列按 walk-forward 证据强度择池。 */
  sourcePool: StockCandidateSourcePool;
  sourcePoolLabel: string;
  /** 该来源池的样本外判定；后端未返回 walk_forward 时为 null 且不渲染徽章。 */
  walkForward: StockStrategyLensVerdict | null;
  /** UI 辅助归类，非正式结论 */
  pattern: StockCandidatePattern;
  patternNote: string;
  distanceToBreakoutPct: string;
  evidenceBullets: StockCandidateEvidenceBullet[];
  /** @deprecated for tests — flattened narrative lines */
  evidence: string[];
  counterEvidence: string[];
  invalidationRules: string[];
  rawFields: StockCandidateRawField[];
  /** 流动性口径披露：低流动徽章判据；undefined/null = 后端未提供或数据缺失，不展示徽章。 */
  liquidityFloorPass?: boolean | null;
  /** 亿元格式化辅助文案，如"日成交 0.80 亿"；无成交额数据时为 null。 */
  dailyAmountLabel?: string | null;
};

export type StockRiskDistanceBucket =
  | "triggered"
  | "0-3%"
  | "3-6%"
  | ">6%"
  | "待补";

export type StockRiskExitRow = {
  stockCode: string;
  stockName: string;
  status: "triggered" | "watch";
  latestClose: string;
  exitWatchPrice: string;
  reason: string;
  distanceToExitPct: string;
  exitDistanceBucket: StockRiskDistanceBucket;
  /** false when the backend reports the position's entry cost basis as missing. */
  entryCostAvailable: boolean;
};

export type StockSectorRow = {
  rank: number;
  sectorCode: string;
  sectorName: string;
  score: string;
  pctChange: string;
  turnover: string;
  amplitude: string;
  constituentCount: number;
  scoreValue: number | null;
  pctChangeValue: number | null;
  turnoverValue: number | null;
  amplitudeValue: number | null;
  /** 条形图宽度用，相对本批最高分归一（无业务语义） */
  scoreNormalized: number;
  pctChangeBar: number;
  isTop: boolean;
  isBottom: boolean;
};

export type StockSectorViewKind = "score" | "pctchange" | "turnover" | "amplitude";

export type StockSectorViewRow = StockSectorRow & {
  /** 当前视图用于水平条长度的 0–1 归一化 */
  metricBarNormalized: number;
};

export type StockSectorOverviewState<TRow extends StockSectorRow> = {
  leaderRow: TRow | null;
  tailRow: TRow | null;
  coverageCount: number;
  topBars: TRow[];
  bottomBars: TRow[];
};

export type StockDailyJudgmentStrip = {
  headline: string;
  gateChip: string;
  exposureChip: string;
  strongestSectorChip: string;
  weakestSectorChip: string;
};

export type StockDecisionSummary = {
  headline: string;
  gateLabel: string;
  exposureLabel: string;
  strongestSectorLabel: string;
  weakestSectorLabel: string;
  candidateCountLabel: string;
  dataFreshnessLabel: string;
  boundaryLabel: string;
  nextReviewAction: string;
  basisLabel: string;
  asOfLabel: string;
};

export type StockClosedLoopTone = "positive" | "warning" | "negative" | "neutral";

export type StockClosedLoopSummaryItem = {
  key: "entry_gate" | "adversarial_gate" | "risk_exit" | "replay" | "lineage";
  label: string;
  status: string;
  statusLabel: string;
  tone: StockClosedLoopTone;
  detail: string;
  badges?: string[];
};

export type StockDecisionReferenceRatingCode =
  | "reviewable"
  | "pause"
  | "blocked"
  | "insufficient_data";

export type StockDecisionReferenceRating = {
  code: StockDecisionReferenceRatingCode;
  label: "可复核" | "暂缓" | "拦截" | "数据不足";
  tone: StockClosedLoopTone;
  detail: string;
};

export type StockClosedLoopVerdict = {
  code: StockDecisionReferenceRatingCode;
  tone: StockClosedLoopTone;
  label: string;
  headline: string;
  primaryReason: string;
  nextStep: string;
  evidence: string[];
};

export type StockClosedLoopSummary = {
  summaryLabel: string;
  boundaryCount: number;
  referenceRating: StockDecisionReferenceRating;
  verdict: StockClosedLoopVerdict;
  items: StockClosedLoopSummaryItem[];
};

export type StockViewModelMeta = Partial<
  Pick<
    ResultMeta,
    "quality_flag" | "vendor_status" | "source_version" | "rule_version" | "trace_id" | "fallback_mode"
  >
>;

export type StockDataBoundarySummary = {
  boundaryCount: number;
  diagnosticsCount: number;
  dataGapCount: number;
  unsupportedCount: number;
  freshnessLabel: string;
  summaryLabel: string;
  detailLabel: string;
  topMessages: string[];
};

export type StockCycleMacroLayerSummary = {
  statusLabel: "已落地" | "待补" | "部分就绪";
  tone: StockClosedLoopTone;
  macroScoreLabel: string;
  formulaVersionLabel: string;
  evidence: string;
  availableInputs: string[];
  missingInputs: string[];
  macroGapLabels: string[];
  detailLabel: string;
};

export type StockAnalysisEvidenceStatusKey =
  | "as-of-date"
  | "lineage"
  | "basis"
  | "rule-version"
  | "quality"
  | "exceptions";

export type StockAnalysisEvidenceStatusItem = {
  key: StockAnalysisEvidenceStatusKey;
  label: string;
  statusLabel: string;
  tone: StockClosedLoopTone;
  detail: string;
};

export type StockEndpointEvidenceQueryState = "idle" | "loading" | "error" | "success";

export type StockEndpointEvidenceMeta = {
  trace_id?: string | null;
  quality_flag?: string | null;
  vendor_status?: string | null;
  fallback_mode?: string | null;
  source_version?: string | null;
  rule_version?: string | null;
  requested_report_date?: string | null;
  resolved_report_date?: string | null;
  as_of_date?: string | null;
  generated_at?: string | null;
};

export type StockEndpointEvidenceInput = {
  key: string;
  label: string;
  queryState: StockEndpointEvidenceQueryState;
  meta?: StockEndpointEvidenceMeta | null;
  asOfDate?: string | null;
  snapshotFrom?: string | null;
  snapshotTo?: string | null;
  warningCount?: number | null;
  unsupportedCount?: number | null;
  missingInputCount?: number | null;
};

export type StockEndpointEvidenceItem = {
  key: string;
  label: string;
  statusLabel: string;
  tone: StockClosedLoopTone;
  detail: string;
  dateLabel: string;
  traceLabel: string;
  issueLabel: string;
  metaLabel: string;
};

export type StockObservationClosureReasonKind =
  | "query-error"
  | "meta-missing"
  | "fallback"
  | "warning"
  | "unsupported"
  | "missing-input"
  | "data-gap"
  | "diagnostic"
  | "no-data";

export type StockObservationClosureReasonInput = {
  key?: string;
  endpointId: string;
  endpointLabel: string;
  kind: StockObservationClosureReasonKind;
  fieldPath: string;
  displayText: string;
  rawValueLabel?: string | null;
};

export type StockObservationClosureReason = StockObservationClosureReasonInput & {
  key: string;
  tone: StockClosedLoopTone;
};

export type StockObservationClosureAction = {
  key: string;
  source: string;
  actionText: string;
  fieldPath: string;
};

export type StockObservationClosureSummary = {
  formalUseAllowed: boolean;
  approvalStatus: string;
  approvalLabel: string;
  endpointTotal: number;
  endpointLoadedCount: number;
  endpointErrorCount: number;
  metaMissingCount: number;
  unresolvedReasons: StockObservationClosureReason[];
  nextEvidenceActions: StockObservationClosureAction[];
  headline: string;
  detail: string;
  tone: StockClosedLoopTone;
};

export type WorkbenchFactTone =
  | "neutral"
  | "read"
  | "empty"
  | "warning"
  | "missing"
  | "unsupported"
  | "slow"
  | "error";

export type WorkbenchFact = {
  id: string;
  label: string;
  value: string;
  subValue?: string;
  sourcePath: string;
  tone: WorkbenchFactTone;
  isPrimary?: boolean;
};

export type WorkbenchDataDigest = {
  primaryFacts: WorkbenchFact[];
  candidateFacts: WorkbenchFact[];
  evidenceFacts: WorkbenchFact[];
  slowFacts: WorkbenchFact[];
};

export type WorkbenchSlowState = "idle" | "loading" | "slow" | "success" | "error";

export type WorkbenchDataDigestInput = {
  main?: LivermoreStrategyPayload | null;
  signalConfluence?: LivermoreSignalConfluencePayload | null;
  candidateHistory?: LivermoreCandidateHistoryPayload | null;
  strategyScore?: LivermoreStrategyScorePayload | null;
  strategyOptimization?: LivermoreStrategyOptimizationPayload | null;
  cycleProxyBacktest?: LivermoreCycleProxyBacktestPayload | null;
  portfolioBacktest?: LivermoreCandidateHistoryPortfolioBacktestPayload | null;
  sectorRankSeries?: LivermoreSectorRankSeriesPayload | null;
  candidateHistoryState?: WorkbenchSlowState;
  strategyScoreState?: WorkbenchSlowState;
};

export type StockAnalysisEventMonitorRow = {
  key: string;
  source: "diagnostic" | "data_gap" | "unsupported" | "signal_confluence" | "risk_exit";
  level: "info" | "warning" | "error";
  event: string;
  impact: string;
  detail: string;
};

export type StockSectorFilterSummary = {
  sectorCode: string | null;
  sectorLabel: string;
  isFiltered: boolean;
  visibleCount: number;
  totalCount: number;
  summaryLabel: string;
};

export type StockCandidateReviewQueueItem = {
  rank: number;
  stockCode: string;
  stockName: string;
  sectorCode: string;
  sectorName: string;
  headline: string;
  /** 候选来自哪个策略池；队列按 walk-forward 证据强度择池。 */
  sourcePool: StockCandidateSourcePool;
  sourcePoolLabel: string;
  /** 该来源池的样本外判定；后端未返回 walk_forward 时为 null 且不渲染徽章。 */
  walkForward: StockStrategyLensVerdict | null;
  pattern: StockCandidatePattern;
  patternNote: string;
  distanceToBreakoutPct: string;
  reviewFocus: string;
  primaryEvidence: StockCandidateEvidenceBullet[];
  supportingEvidence: StockCandidateEvidenceBullet[];
  boundaryEvidence: string[];
  invalidationFocus: string;
  invalidationRules: string[];
  rawFields: StockCandidateRawField[];
  /** 流动性口径披露：低流动徽章判据；undefined/null = 后端未提供或数据缺失，不展示徽章。 */
  liquidityFloorPass?: boolean | null;
  /** 亿元格式化辅助文案，如"日成交 0.80 亿"；无成交额数据时为 null。 */
  dailyAmountLabel?: string | null;
} & { sizeHintLabel?: string | null; sizeHintDetail?: string | null } & // 建议仓位透传：由 stockAnalysisPositionSizeHintModel 在队列富化时注入
  StockCandidateSignalWindowFields; // 信号窗口透传：由 stockAnalysisSignalWindowModel 在队列富化时注入

export type StockReviewQueueSectorFilterView = {
  sectorOptions: [string, string][];
  filteredCandidates: StockCandidateReviewQueueItem[];
  selectedSectorLeadCandidate: StockCandidateReviewQueueItem | null;
  sectorLinkTone: "active" | "empty" | "all";
  sectorLinkSummary: string;
  sectorLinkFocus: string;
};

export type StockThemeBreakoutLeader = {
  stockCode: string;
  stockName: string;
  pctChange: string;
  turn: string;
  closeStrength: string;
  tags: string[];
  sourceKindLabel?: string;
};

export type StockThemeBreakoutCard = {
  rank: number;
  themeKey: string;
  themeName: string;
  parentSectorLabel: string;
  summary: string;
  reason: string;
  boundaryLabel: string;
  strongCountLabel: string;
  limitCountLabel: string;
  advanceRatioLabel: string;
  avgPctChangeLabel: string;
  movementLabel: string;
  latestEventLabel: string;
  sourceKindLabel?: string;
  leaders: StockThemeBreakoutLeader[];
};

export type StockThemeEvidenceStateRow = {
  key: string;
  label: string;
  status: string;
  statusLabel: string;
  detail: string;
  rowCountLabel: string;
};

export type StockThemeBreakoutReviewItem = {
  rank: number;
  themeKey: string;
  themeName: string;
  sourceKindLabel: string;
  parentSectorLabel: string;
  summary: string;
  failedGateLabel: string;
  reason: string;
  leaders: StockThemeBreakoutLeader[];
};

export type StockThemeTaxonomyGapSummary = {
  state: "ready" | "partial" | "unavailable";
  detail: string;
};

export type StockReviewQueueEmptyState = {
  headline: string;
  detail: string;
};

export type StockStrategyLensVerdict = {
  key: "supported" | "weakened" | "not_assessable";
  label: string;
  detail: string;
};

export type StockStrategyLensItem = {
  key: string;
  label: string;
  subtitle: string;
  value: string;
  unitLabel: string;
  detail: string;
  tone: "positive" | "warning" | "negative" | "neutral";
  state: "ready" | "blocked" | "empty" | "paused" | "pending";
  statusLabel: string;
  statusDetail: string;
  /** walk-forward 样本外判定徽章；老响应缺字段时为 null 且不渲染。 */
  verdict: StockStrategyLensVerdict | null;
  blockerLabel: string;
  focusLabel: string;
  actionLabel: string;
  candidateCountLabel: string;
  dateLabel: string;
  formulaLabel: string;
  evidence: Array<{ key: string; label: string; value: string }>;
  candidates: Array<{
    key: string;
    rankLabel: string;
    stockCode: string;
    stockName: string;
    sectorName: string;
    metricLabel: string;
  }>;
  scrollTarget: string;
  progress?: number;
};

export type StockThemeLeaderPreviewItem = {
  stockCode: string;
  stockName: string;
  themeName: string;
  themeRank: number;
  pctChange: string;
  turn: string;
  closeStrength: string;
  tags: string[];
};

export type StockSectorHeavyweightStockPreview = {
  stockCode: string;
  stockName: string;
  pctChange: string;
  turn: string;
  closeStrength: string;
  sourceLabel: string;
  detailSource: StockDetailSource;
  detailLabel?: string;
  auxiliaryLabel?: string;
};

export type StockSectorHeavyweightPreviewRow = {
  sectorCode: string;
  sectorName: string;
  sectorRank: number;
  sectorPctChange: string;
  sectorScore: string;
  stocks: StockSectorHeavyweightStockPreview[];
  emptyReason?: string;
};

export type StockSectorHeavyweightPreviewSummary = {
  rows: StockSectorHeavyweightPreviewRow[];
  sectorLimit: number;
  sectorsWithSamples: number;
  totalSampleCount: number;
  uncoveredSectorCount: number;
};

export type StockStrategyPanelQueryState = "idle" | "loading" | "ready" | "error";

export type StockStrategyPanelMiniStatValueTone = "up" | "down" | "flat" | "emphasis" | "warning";

export type StockStrategyPanelMiniStat = {
  key: string;
  label: string;
  value: string;
  tone?: StockClosedLoopTone;
  /**
   * 数值着色：绿涨红跌（渲染端 StrategyPanelResultStrip 将 up→success 绿、
   * down→danger 红）/ 强调 / 预警。方向色两套体系的全站裁决未定，此注释仅
   * 如实描述现行实现，不构成方向色决议。
   */
  valueTone?: StockStrategyPanelMiniStatValueTone;
};

export type StockStrategyPanelResultSummary = {
  headline: string;
  detail?: string;
  /** 周期代理回测的 execution-first 构成披露。 */
  proxyBacktestBasisDisclosure?: string;
  /** 英文合规/边界原文，默认折叠在展开区 */
  complianceDetail?: string;
  badgeLabel?: string;
  stats: StockStrategyPanelMiniStat[];
  tone?: StockClosedLoopTone;
  /** 懒加载卡：卡面仅显示加载态，不渲染 KPI */
  loading?: boolean;
};

export type StockDeepAnalysisGateSummary = {
  line: string;
  tone: StockClosedLoopTone;
};

export type StockDeepZoneAuditRow = {
  key: "supply" | "replay" | "review" | "events";
  label: string;
  value: string;
  tone: StockClosedLoopTone;
};
