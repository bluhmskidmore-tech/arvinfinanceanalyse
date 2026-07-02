import type {
  BacktestWindowSummary,
  BacktestWindowSummaryStatus,
  ConfluenceReplayBlockedDate,
  ConfluenceReplayStatus,
  LivermoreCandidateHistoryHorizonStats,
  LivermoreCandidateHistoryPayload,
  LivermoreCandidateHistoryPortfolioBacktestPayload,
  LivermoreCycleProxyBacktestPayload,
  LivermoreMarketGateState,
  LivermoreSignalConfluencePayload,
  LivermoreSectorRankSeriesPoint,
  LivermoreSectorRankSeriesPayload,
  LivermoreStockCandidateItem,
  LivermoreStrategyOptimizationPayload,
  LivermoreStrategyPayload,
  LivermoreStrategyScorePayload,
  HybridFusionCandidateItem,
  FreshTrendWatchlistCandidateItem,
  LivermoreThemeBreakoutReviewItem,
  LivermoreThemeEvidenceInputState,
  LivermoreThemeBreakoutItem,
  ResultMeta,
} from "../../../api/contracts";
import type { ConsensusSummary } from "./buildConsensusSummary";
import type { StockDetailSource } from "./stockAnalysisDetailSelection";

type NormalizedConfluenceReplayBlockedDate = Omit<ConfluenceReplayBlockedDate, "reason_code"> & {
  reason_code: string;
};

type NormalizedConfluenceReplayStatus = Omit<ConfluenceReplayStatus, "blocked_dates"> & {
  blocked_dates: NormalizedConfluenceReplayBlockedDate[];
  maturity_status?: string;
  matched_entry_count: number;
  has_required_horizon_stats: boolean;
};

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
};

export type StockCandidatePattern = "突破" | "回踩" | "缩量盘整" | "待补";

export type StockCandidateEvidenceBullet = {
  key: string;
  label: string;
  value: string;
};

export type StockCandidateEvidenceCard = {
  rank: number;
  stockCode: string;
  stockName: string;
  sectorCode: string;
  sectorName: string;
  headline: string;
  /** UI 辅助归类，非正式结论 */
  pattern: StockCandidatePattern;
  patternNote: string;
  distanceToBreakoutPct: string;
  evidenceBullets: StockCandidateEvidenceBullet[];
  /** @deprecated for tests — flattened narrative lines */
  evidence: string[];
  counterEvidence: string[];
  invalidationRules: string[];
  rawFields: { key: string; label: string; value: string }[];
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

export type StockMetaSegment = {
  key: string;
  text: string;
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

export function pickStockFreshnessMeta(meta: StockViewModelMeta | null | undefined): StockViewModelMeta {
  return {
    quality_flag: meta?.quality_flag,
    vendor_status: meta?.vendor_status,
    fallback_mode: meta?.fallback_mode,
  };
}

export function mergeStockClosedLoopMeta(
  hasClosedLoopState: boolean,
  strategyMeta: StockViewModelMeta | null | undefined,
  confluenceMeta: StockViewModelMeta | null | undefined,
): StockViewModelMeta {
  if (!hasClosedLoopState) return strategyMeta ?? {};
  return {
    quality_flag: confluenceMeta?.quality_flag ?? strategyMeta?.quality_flag,
    vendor_status: confluenceMeta?.vendor_status ?? strategyMeta?.vendor_status,
    fallback_mode: confluenceMeta?.fallback_mode ?? strategyMeta?.fallback_mode,
    source_version: confluenceMeta?.source_version ?? strategyMeta?.source_version,
    rule_version: confluenceMeta?.rule_version ?? strategyMeta?.rule_version,
    trace_id: confluenceMeta?.trace_id ?? strategyMeta?.trace_id,
  };
}

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

export type StockAnalysisKpiKey =
  | "market-state"
  | "review-queue"
  | "sector-strength"
  | "risk-observation"
  | "closed-loop"
  | "data-boundary";

export type StockAnalysisKpiItem = {
  key: StockAnalysisKpiKey;
  label: string;
  value: string;
  detail: string;
  tone: StockClosedLoopTone;
  gaugeValue?: number;
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

function countArrayValue(value: unknown): number | null {
  return Array.isArray(value) ? value.length : null;
}

function countArrayOrRecordValue(value: unknown): number | null {
  if (Array.isArray(value)) return value.length;
  if (value != null && typeof value === "object") return Object.keys(value as Record<string, unknown>).length;
  return null;
}

function isWorkbenchPresent(value: unknown): boolean {
  if (value == null || value === "") return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value as Record<string, unknown>).length > 0;
  return true;
}

function digestCountLabel(value: number | null | undefined, unit = "项"): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "未返回";
  return `${value} ${unit}`;
}

function digestPlainCount(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "未返回";
  return String(value);
}

function countTone(value: number | null | undefined): WorkbenchFactTone {
  if (typeof value !== "number" || !Number.isFinite(value)) return "missing";
  return value > 0 ? "read" : "empty";
}

function presenceTone(isPresent: boolean, whenMissing: WorkbenchFactTone = "missing"): WorkbenchFactTone {
  return isPresent ? "read" : whenMissing;
}

function compactRangeLabel(from: string | null | undefined, to: string | null | undefined): string {
  if (from && to) return `${from} 至 ${to}`;
  if (to) return `截至 ${to}`;
  if (from) return `起始 ${from}`;
  return "窗口未返回";
}

function makeWorkbenchFact(fact: WorkbenchFact): WorkbenchFact {
  return fact;
}

function slowFactFromState({
  id,
  label,
  state,
  sourcePath,
  successValue,
  successSubValue,
  successTone,
}: {
  id: string;
  label: string;
  state: WorkbenchSlowState;
  sourcePath: string;
  successValue: string | null;
  successSubValue: string | null;
  successTone: WorkbenchFactTone;
}): WorkbenchFact {
  if (state === "error") {
    return makeWorkbenchFact({
      id,
      label,
      value: "读取失败",
      subValue: "接口读取失败，无法纳入本次复核台账",
      sourcePath,
      tone: "error",
    });
  }

  if (successValue != null) {
    return makeWorkbenchFact({
      id,
      label,
      value: successValue,
      subValue: successSubValue ?? undefined,
      sourcePath,
      tone: successTone,
    });
  }

  if (state === "slow") {
    return makeWorkbenchFact({
      id,
      label,
      value: "读取较慢",
      subValue: "读取时间较长，暂未纳入首屏摘要",
      sourcePath,
      tone: "slow",
    });
  }

  if (state === "loading") {
    return makeWorkbenchFact({
      id,
      label,
      value: "读取中",
      subValue: `${label}：正在读取历史证据，首屏不阻塞`,
      sourcePath,
      tone: "slow",
    });
  }

  return makeWorkbenchFact({
    id,
    label,
    value: "待触发",
    subValue: "展开复核区或首屏证据请求后读取",
    sourcePath,
    tone: "neutral",
  });
}

export function buildWorkbenchDataDigest({
  main,
  signalConfluence,
  candidateHistory,
  strategyScore,
  strategyOptimization,
  cycleProxyBacktest,
  portfolioBacktest,
  sectorRankSeries,
  candidateHistoryState = "idle",
  strategyScoreState = "idle",
}: WorkbenchDataDigestInput): WorkbenchDataDigest {
  const factorCandidateCount = countArrayValue(main?.factor_screen_candidates?.items);
  const hybridCandidateCount = countArrayValue(main?.hybrid_fusion_candidates?.items);
  const sectorRankCount = countArrayValue(main?.sector_rank?.items);
  const moduleStateCount = countArrayValue(main?.module_states);
  const ruleReadinessCount = countArrayValue(main?.rule_readiness);
  const dataGapCount = main ? activeDataGaps(main).length : null;
  const diagnosticCount = main ? actionableDiagnostics(main).length : null;
  const unsupportedCount = main ? actionableUnsupportedOutputs(main).length : null;
  const supportedCount = countArrayValue(main?.supported_outputs);
  const signalContextCount = signalConfluence
    ? [
        signalConfluence.macro_context,
        signalConfluence.adversarial_context,
        signalConfluence.strategy_context,
        signalConfluence.closed_loop_state,
      ].filter(isWorkbenchPresent).length
    : null;
  const entryObservationCount = countArrayValue(signalConfluence?.entry_observations);
  const exitObservationCount = countArrayValue(signalConfluence?.exit_observations);
  const replaySampleCount = countArrayValue(signalConfluence?.replay_evidence?.sample_items);
  const replayRowCount =
    typeof signalConfluence?.replay_evidence?.row_count === "number"
      ? signalConfluence.replay_evidence.row_count
      : null;
  const sectorSeriesCount = countArrayValue(sectorRankSeries?.series);
  const strategyOptimizationCount = countArrayValue(strategyOptimization?.strategy_summaries);
  const strategySliceCount = countArrayValue(strategyOptimization?.slices);
  const cycleNavCount = countArrayValue(cycleProxyBacktest?.nav_series);
  const portfolioNavCount = countArrayValue(portfolioBacktest?.nav_series);
  const rebalanceLogCount = countArrayValue(portfolioBacktest?.rebalance_log);
  const proxyWarningCount =
    (countArrayValue(cycleProxyBacktest?.warnings) ?? 0) + (countArrayValue(portfolioBacktest?.warnings) ?? 0);
  const missingInputCount =
    (countArrayValue(cycleProxyBacktest?.missing_full_strategy_inputs) ?? 0) +
    (countArrayValue(portfolioBacktest?.missing_full_strategy_inputs) ?? 0);
  const candidateHistoryItemCount = countArrayValue(candidateHistory?.items);
  const strategyScoreRowCount = countArrayValue(strategyScore?.rows);
  const strategyScoreCurrentRowCount = countArrayValue(strategyScore?.current_market_state_rows);
  const strategyScoreScopeCount = countArrayOrRecordValue(strategyScore?.stock_candidate_state_scopes);
  const openIssueCount = (dataGapCount ?? 0) + (diagnosticCount ?? 0) + (unsupportedCount ?? 0);

  const primaryFacts: WorkbenchFact[] = [
    makeWorkbenchFact({
      id: "data-date",
      label: "数据日期",
      value: main?.as_of_date ?? "未返回",
      subValue: main?.requested_as_of_date ? `请求 ${main.requested_as_of_date}` : "使用最新可用快照",
      sourcePath: "strategy.result.as_of_date",
      tone: main?.as_of_date ? "read" : "missing",
      isPrimary: true,
    }),
    makeWorkbenchFact({
      id: "strategy-basis",
      label: "策略口径",
      value: localizeBasisLabel(main?.basis),
      subValue: main?.strategy_name ? "趋势策略只读复核" : "策略名称未返回",
      sourcePath: "strategy.result.strategy_name",
      tone: main?.strategy_name ? "read" : "missing",
      isPrimary: true,
    }),
    makeWorkbenchFact({
      id: "candidate-depth",
      label: "候选厚度",
      value: `${digestPlainCount(factorCandidateCount)} / ${digestPlainCount(hybridCandidateCount)}`,
      subValue: "多因子 / 融合候选",
      sourcePath: "strategy.result.factor_screen_candidates.items + hybrid_fusion_candidates.items",
      tone:
        factorCandidateCount == null && hybridCandidateCount == null
          ? "missing"
          : (factorCandidateCount ?? 0) + (hybridCandidateCount ?? 0) > 0
            ? "read"
            : "empty",
      isPrimary: true,
    }),
    makeWorkbenchFact({
      id: "open-issues",
      label: "证据缺口",
      value: `${openIssueCount} 项`,
      subValue: `缺口 ${digestPlainCount(dataGapCount)} / 诊断 ${digestPlainCount(diagnosticCount)} / 未支持 ${digestPlainCount(unsupportedCount)}`,
      sourcePath: "strategy.result.data_gaps + diagnostics + unsupported_outputs",
      tone: openIssueCount > 0 ? "warning" : "read",
      isPrimary: true,
    }),
  ];

  const candidateFacts: WorkbenchFact[] = [
    makeWorkbenchFact({
      id: "factor-candidates",
      label: "多因子候选",
      value: digestCountLabel(factorCandidateCount, "只"),
      subValue: main?.factor_screen_candidates?.formula_version,
      sourcePath: "strategy.result.factor_screen_candidates.items",
      tone: countTone(factorCandidateCount),
    }),
    makeWorkbenchFact({
      id: "hybrid-candidates",
      label: "融合候选",
      value: digestCountLabel(hybridCandidateCount, "只"),
      subValue: main?.hybrid_fusion_candidates?.formula_version,
      sourcePath: "strategy.result.hybrid_fusion_candidates.items",
      tone: countTone(hybridCandidateCount),
    }),
    makeWorkbenchFact({
      id: "sector-rank",
      label: "行业排名",
      value: digestCountLabel(sectorRankCount, "个"),
      subValue: sectorRankFormulaGovernanceLabel(main?.sector_rank),
      sourcePath: "strategy.result.sector_rank.items",
      tone: countTone(sectorRankCount),
    }),
    makeWorkbenchFact({
      id: "module-states",
      label: "模块状态",
      value: digestCountLabel(moduleStateCount, "组"),
      subValue: `可输出 ${digestPlainCount(supportedCount)} / 规则 ${digestPlainCount(ruleReadinessCount)}`,
      sourcePath: "strategy.result.module_states",
      tone: countTone(moduleStateCount),
    }),
  ];

  const evidenceFacts: WorkbenchFact[] = [
    makeWorkbenchFact({
      id: "gate-readiness",
      label: "门控/规则",
      value: `${isWorkbenchPresent(main?.market_gate) ? "门控已返回" : "门控未返回"} / ${digestCountLabel(ruleReadinessCount, "条")}`,
      subValue: main?.market_gate?.state ? `市场状态 ${localizeMarketDataStatus(main.market_gate.state)}` : undefined,
      sourcePath: "strategy.result.market_gate + rule_readiness",
      tone: presenceTone(isWorkbenchPresent(main?.market_gate)),
    }),
    makeWorkbenchFact({
      id: "signal-context",
      label: "信号上下文",
      value: digestCountLabel(signalContextCount, "组"),
      subValue: `进入 ${digestPlainCount(entryObservationCount)} / 退出 ${digestPlainCount(exitObservationCount)}`,
      sourcePath: "signalConfluence.result.macro_context + strategy_context + closed_loop_state",
      tone: countTone(signalContextCount),
    }),
    makeWorkbenchFact({
      id: "replay-evidence",
      label: "回放证据",
      value: replayRowCount != null ? `${replayRowCount} 行` : digestCountLabel(replaySampleCount, "条样例"),
      subValue: replaySampleCount != null ? `首屏样例 ${replaySampleCount}` : "样例未返回",
      sourcePath: "signalConfluence.result.replay_evidence",
      tone: countTone(replayRowCount ?? replaySampleCount),
    }),
    makeWorkbenchFact({
      id: "sector-series",
      label: "行业序列",
      value: digestCountLabel(sectorSeriesCount, "条"),
      subValue: sectorRankSeries
        ? `top ${sectorRankSeries.top_k} / ${sectorRankSeries.window_days}日 / ${sectorRankSeries.formula_version}`
        : "序列未返回",
      sourcePath: "sectorRankSeries.result.series",
      tone: countTone(sectorSeriesCount),
    }),
    makeWorkbenchFact({
      id: "proxy-backtest",
      label: "代理回放",
      value: `${digestPlainCount(cycleNavCount)} / ${digestPlainCount(portfolioNavCount)}`,
      subValue: `周期 NAV / 组合 NAV；再平衡 ${digestPlainCount(rebalanceLogCount)}`,
      sourcePath: "cycleProxyBacktest.result.nav_series + portfolioBacktest.result.nav_series",
      tone:
        cycleNavCount == null && portfolioNavCount == null
          ? "missing"
          : (cycleNavCount ?? 0) + (portfolioNavCount ?? 0) > 0
            ? "read"
            : "empty",
    }),
    makeWorkbenchFact({
      id: "proxy-warnings",
      label: "代理边界",
      value: `${proxyWarningCount + missingInputCount} 项`,
      subValue: `提示 ${proxyWarningCount} / 缺输入 ${missingInputCount}`,
      sourcePath: "cycleProxyBacktest.result.warnings + portfolioBacktest.result.missing_full_strategy_inputs",
      tone: proxyWarningCount + missingInputCount > 0 ? "warning" : "read",
    }),
    makeWorkbenchFact({
      id: "optimization-depth",
      label: "优化诊断",
      value: `${digestPlainCount(strategyOptimizationCount)} / ${digestPlainCount(strategySliceCount)}`,
      subValue: "策略摘要 / 切片",
      sourcePath: "strategyOptimization.result.strategy_summaries + slices",
      tone:
        strategyOptimizationCount == null && strategySliceCount == null
          ? "missing"
          : (strategyOptimizationCount ?? 0) + (strategySliceCount ?? 0) > 0
            ? "read"
            : "empty",
    }),
  ];

  const slowFacts: WorkbenchFact[] = [
    slowFactFromState({
      id: "candidate-history",
      label: "候选历史",
      state: candidateHistoryState,
      sourcePath: "candidateHistory.result.items",
      successValue: candidateHistory ? digestCountLabel(candidateHistoryItemCount, "行") : null,
      successSubValue: candidateHistory
        ? `${compactRangeLabel(candidateHistory.snapshot_from, candidateHistory.snapshot_to)}；summary ${
            candidateHistory.summary ? "已返回" : "未返回"
          } / window ${candidateHistory.backtest_window_summary ? "已返回" : "未返回"}`
        : null,
      successTone: countTone(candidateHistoryItemCount),
    }),
    slowFactFromState({
      id: "strategy-score",
      label: "优先级评分",
      state: strategyScoreState,
      sourcePath: "strategyScore.result.rows",
      successValue: strategyScore ? `${digestPlainCount(strategyScoreRowCount)} / ${digestPlainCount(strategyScoreCurrentRowCount)}` : null,
      successSubValue: strategyScore
        ? `${compactRangeLabel(strategyScore.snapshot_from, strategyScore.snapshot_to)}；scope ${digestPlainCount(
            strategyScoreScopeCount,
          )} / min ${strategyScore.min_sample}`
        : null,
      successTone: countTone(strategyScoreRowCount),
    }),
  ];

  return {
    primaryFacts,
    candidateFacts,
    evidenceFacts,
    slowFacts,
  };
}

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
  pattern: StockCandidatePattern;
  patternNote: string;
  distanceToBreakoutPct: string;
  reviewFocus: string;
  primaryEvidence: StockCandidateEvidenceBullet[];
  supportingEvidence: StockCandidateEvidenceBullet[];
  boundaryEvidence: string[];
  invalidationFocus: string;
  invalidationRules: string[];
  rawFields: { key: string; label: string; value: string }[];
};

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

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value == null || !Number.isFinite(value)) {
    return "待补";
  }
  return value.toFixed(digits);
}

function formatPercent(value: number | null | undefined, digits = 2) {
  if (value == null || !Number.isFinite(value)) {
    return "待补";
  }
  return `${value.toFixed(digits)}%`;
}

function formatRatioAsPercent(value: number | null | undefined, digits = 0) {
  if (value == null || !Number.isFinite(value)) {
    return "待补";
  }
  return `${(value * 100).toFixed(digits)}%`;
}

function finiteNumber(value: number | null | undefined): number | null {
  return value == null || !Number.isFinite(value) ? null : value;
}

function clampRatio(value: number | null | undefined): number | undefined {
  if (value == null || !Number.isFinite(value)) return undefined;
  return Math.min(1, Math.max(0, value));
}

function buildCandidateFundamentalEvidence(item: LivermoreStockCandidateItem): StockCandidateEvidenceBullet[] {
  const bullets: StockCandidateEvidenceBullet[] = [];
  const factorScore = finiteNumber(item.factor_score);
  const factorRank = finiteNumber(item.factor_overlay_rank);
  if (factorScore != null || factorRank != null) {
    bullets.push({
      key: "fundamental_overlay",
      label: "基本面因子",
      value: [
        factorScore != null ? `因子分 ${formatNumber(factorScore, 4)}` : null,
        factorRank != null ? `因子排名 #${factorRank.toFixed(0)}` : null,
      ]
        .filter((part): part is string => Boolean(part))
        .join(" / "),
    });
  }

  const valuationParts = [
    finiteNumber(item.pe) != null ? `PE ${formatNumber(item.pe, 2)}` : null,
    finiteNumber(item.pb) != null ? `PB ${formatNumber(item.pb, 2)}` : null,
    finiteNumber(item.ps) != null ? `PS ${formatNumber(item.ps, 2)}` : null,
  ].filter((part): part is string => Boolean(part));
  if (valuationParts.length > 0) {
    bullets.push({
      key: "valuation",
      label: "估值",
      value: valuationParts.join(" / "),
    });
  }

  const qualityParts = [
    finiteNumber(item.roe) != null ? `ROE ${formatRatioAsPercent(item.roe, 1)}` : null,
    finiteNumber(item.gross_margin) != null ? `毛利率 ${formatRatioAsPercent(item.gross_margin, 1)}` : null,
  ].filter((part): part is string => Boolean(part));
  if (qualityParts.length > 0) {
    bullets.push({
      key: "quality",
      label: "质量",
      value: qualityParts.join(" / "),
    });
  }

  const momentumParts = [
    finiteNumber(item.three_month_return) != null ? `3月 ${formatRatioAsPercent(item.three_month_return, 1)}` : null,
    finiteNumber(item.twelve_month_return) != null ? `12月 ${formatRatioAsPercent(item.twelve_month_return, 1)}` : null,
  ].filter((part): part is string => Boolean(part));
  if (momentumParts.length > 0) {
    bullets.push({
      key: "fundamental_momentum",
      label: "基本面动量",
      value: momentumParts.join(" / "),
    });
  }

  return bullets;
}

function candidateFundamentalCounterEvidence(item: LivermoreStockCandidateItem): string {
  const hasOverlay = finiteNumber(item.factor_score) != null || finiteNumber(item.factor_overlay_rank) != null;
  if (hasOverlay) {
    return "基本面因子已纳入候选排序，但财报口径、最新公告和一致预期仍需复核。";
  }
  return "基本面与估值证据未接入，不参与当前候选排序。";
}

function normalizeEvidence(evidence: string[] | string | null | undefined): string[] {
  if (Array.isArray(evidence)) {
    return evidence.filter((item) => item.trim().length > 0);
  }
  if (typeof evidence === "string" && evidence.trim()) {
    return [evidence.trim()];
  }
  return [];
}

type StockModuleState = {
  key: LivermoreStrategyPayload["supported_outputs"][number];
  render_mode?: string | null;
  excludes_from_primary?: boolean | null;
  reasons?: readonly string[] | null;
};

type LivermoreStrategyPayloadWithModuleStates = LivermoreStrategyPayload & {
  module_states?: readonly StockModuleState[] | null;
};

function stockModuleStates(
  payload: LivermoreStrategyPayload | null | undefined,
): readonly StockModuleState[] {
  return ((payload as LivermoreStrategyPayloadWithModuleStates | null | undefined)?.module_states ?? []);
}

export function isStockModulePrimaryExcluded(
  payload: LivermoreStrategyPayload | null | undefined,
  key: LivermoreStrategyPayload["supported_outputs"][number],
): boolean {
  if (!payload) {
    return true;
  }
  const states = stockModuleStates(payload);
  if (states.length === 0) {
    return true;
  }
  const state = states.find((item) => item.key === key);
  return !state || state.excludes_from_primary || state.render_mode !== "primary";
}

function stockModulePrimaryReason(
  payload: LivermoreStrategyPayload,
  key: LivermoreStrategyPayload["supported_outputs"][number],
): string {
  const state = stockModuleStates(payload).find((item) => item.key === key);
  const firstReason = state?.reasons?.find((reason) => reason.trim().length > 0);
  return firstReason ? localizeStockBackendText(firstReason, key) : "证据模块仅作观察，不进入主复核。";
}

function sortedCandidateItems(payload: LivermoreStrategyPayload) {
  return [...(payload.stock_candidates?.items ?? [])].sort((left, right) => left.rank - right.rank);
}

function sortedHybridFusionItems(payload: LivermoreStrategyPayload) {
  return [...(payload.hybrid_fusion_candidates?.items ?? [])].sort((left, right) => left.rank - right.rank);
}

function sortedFreshTrendWatchlistItems(payload: LivermoreStrategyPayload): FreshTrendWatchlistCandidateItem[] {
  return [...(payload.fresh_trend_watchlist?.items ?? [])].sort((left, right) => left.rank - right.rank);
}

function sortedThemeBreakoutItems(payload: LivermoreStrategyPayload): LivermoreThemeBreakoutItem[] {
  return [...(payload.theme_breakout?.items ?? [])].sort((left, right) => left.rank - right.rank);
}

function deriveCandidatePattern(item: LivermoreStockCandidateItem): StockCandidatePattern {
  const close = item.close;
  const breakout = item.breakout_level;
  if (close == null || breakout == null || !Number.isFinite(close) || !Number.isFinite(breakout)) {
    return "待补";
  }
  const ratio = close / breakout;
  const turnover = item.abnormal_turnover;
  const gap = item.gap_norm;
  const lowTurn =
    turnover != null && Number.isFinite(turnover) ? turnover < 1.08 : false;
  const tightGap =
    gap != null && Number.isFinite(gap) ? Math.abs(gap) < 0.055 : false;
  if (ratio > 1.0025) return "突破";
  if (ratio < 0.985) return "回踩";
  if (lowTurn && tightGap) return "缩量盘整";
  return "缩量盘整";
}

function formatDistanceToBreakoutPct(item: LivermoreStockCandidateItem): string {
  const close = item.close;
  const breakout = item.breakout_level;
  if (
    close == null ||
    breakout == null ||
    !Number.isFinite(close) ||
    !Number.isFinite(breakout) ||
    breakout === 0
  ) {
    return "待补";
  }
  return `${(((close - breakout) / breakout) * 100).toFixed(2)}%`;
}

function fusionConfidenceLabel(value: string | null | undefined): string {
  const normalized = value?.trim().toLowerCase();
  if (!normalized) return "待补";
  if (normalized === "high") return "高";
  if (normalized === "medium") return "中";
  if (normalized === "low") return "低";
  return "置信度待确认";
}

function fusionActionLabel(value: string | null | undefined): string {
  const action = value?.trim();
  if (!action) return "待补";
  const normalized = action.toLowerCase().replace(/[\s-]+/g, "_");
  const labels: Record<string, string> = {
    observe: "观察",
    monitor: "观察",
    monitor_only: "观察",
    review: "复核",
    pending_review: "待复核",
    observation_only: "仅观察",
    core_plus_trading: "重点复核",
    core_reduce_trading: "降权观察",
    satellite_trial: "卫星观察",
  };
  if (labels[normalized]) return labels[normalized];
  const compact = normalized.replace(/_/g, "");
  if (
    normalized.includes("external_vendor") ||
    normalized.includes("vendor_") ||
    normalized.includes("source_table") ||
    compact.includes("externalvendor") ||
    compact.includes("vendor") ||
    compact.includes("sourcetable") ||
    compact.includes("choicestock")
  ) {
    return "裁决待确认";
  }
  if (/^[a-z0-9_]+$/i.test(normalized)) return "裁决待确认";
  return action;
}

function buildHybridFusionEvidenceCards(
  payload: LivermoreStrategyPayload,
): StockCandidateEvidenceCard[] {
  const formula = payload.hybrid_fusion_candidates?.formula_version ?? "hybrid_fusion";
  return sortedHybridFusionItems(payload).map((item: HybridFusionCandidateItem) => {
    const evidenceBullets: StockCandidateEvidenceBullet[] = [
      { key: "fusion_score", label: "融合分", value: formatNumber(item.fusion_score, 4) },
      { key: "cycle_score", label: "景气周期", value: formatNumber(item.cycle_score, 4) },
      {
        key: "lifecourt_proxy_score",
        label: "生命法庭线索",
        value: formatNumber(item.lifecourt_proxy_score, 4),
      },
      { key: "attention_score", label: "关注线索", value: formatNumber(item.attention_score, 4) },
      { key: "price_confirm_score", label: "价格确认", value: formatNumber(item.price_confirm_score, 4) },
      { key: "crowding_penalty", label: "拥挤惩罚", value: formatNumber(item.crowding_penalty, 4) },
      {
        key: "life_long_pass",
        label: "生命法庭长仓门槛",
        value: item.life_long_pass == null ? "待补" : item.life_long_pass ? "通过" : "未通过",
      },
      {
        key: "fusion_action",
        label: "融合裁决",
        value: fusionActionLabel(item.fusion_action),
      },
      { key: "confidence", label: "置信度", value: fusionConfidenceLabel(item.confidence) },
      { key: "formula_version", label: "公式版本", value: formula },
    ];
    const sourceKindValues = Array.isArray(item.evidence?.source_kinds)
      ? item.evidence.source_kinds
      : [];
    const hasProxySourceKind = sourceKindValues.some((sourceKind) => {
      const normalized = sourceKind.toLowerCase().replace(/[\s-]+/g, "_");
      const compact = normalized.replace(/_/g, "");
      return (
        normalized.includes("external_vendor") ||
        normalized.includes("vendor_") ||
        normalized.includes("source_table") ||
        normalized.includes("proxy") ||
        compact.includes("externalvendor") ||
        compact.includes("sourcetable")
      );
    });
    const proxyCounterEvidence = hasProxySourceKind
      ? ["代理信号仅作来源线索，仍需人工确认与正式数据校验。"]
      : [];
    const sourceKinds = sourceKindValues.length > 0
      ? sourceKindValues.map(sectorHeavyweightSourceLabel).join(" / ")
      : "待补";
    const evidence = evidenceBullets.map((bullet) => `${bullet.label}：${bullet.value}`);

    return {
      rank: item.rank,
      stockCode: item.stock_code,
      stockName: item.stock_name,
      sectorCode: item.sector_code,
      sectorName: item.sector_name,
      headline: `融合策略 #${item.rank} · ${item.stock_name}`,
      pattern: "待补",
      patternNote: "融合策略为研究只读候选，形态标签需回看趋势与题材证据",
      distanceToBreakoutPct: "融合优先",
      evidenceBullets,
      evidence,
      counterEvidence: [
        "生命法庭层仍是观察线索，真实大V文本、OCR/ASR和社交情绪生产线仍待补。",
        ...proxyCounterEvidence,
        "仅作观察与复核，不作为执行依据。",
        `来源命中：${sourceKinds}`,
      ],
      invalidationRules: [
        "市场门控转弱、题材/趋势/因子来源失效或拥挤惩罚上升时，需要降级复核。",
        "数据质量陈旧或缺失时，不得解释为有效观察。",
      ],
      rawFields: [
        { key: "fusion_score", label: "融合分", value: formatNumber(item.fusion_score, 6) },
        { key: "cycle_score", label: "景气周期", value: formatNumber(item.cycle_score, 6) },
        {
          key: "lifecourt_proxy_score",
          label: "生命法庭线索",
          value: formatNumber(item.lifecourt_proxy_score, 6),
        },
        { key: "attention_score", label: "关注线索", value: formatNumber(item.attention_score, 6) },
        {
          key: "price_confirm_score",
          label: "价格确认",
          value: formatNumber(item.price_confirm_score, 6),
        },
        { key: "crowding_penalty", label: "拥挤惩罚", value: formatNumber(item.crowding_penalty, 6) },
        { key: "fusion_action", label: "融合裁决", value: fusionActionLabel(item.fusion_action) },
        { key: "confidence", label: "置信度", value: fusionConfidenceLabel(item.confidence) },
      ],
    };
  });
}

function buildFreshTrendEvidenceCards(
  payload: LivermoreStrategyPayload,
): StockCandidateEvidenceCard[] {
  const formula = payload.fresh_trend_watchlist?.formula_version ?? "fresh_trend_watchlist";
  return sortedFreshTrendWatchlistItems(payload).map((item) => {
    const concepts = item.concepts.length > 0 ? item.concepts.slice(0, 3).join(" / ") : "题材待补";
    const evidenceBullets: StockCandidateEvidenceBullet[] = [
      { key: "return_20d", label: "20日动量", value: formatRatioAsPercent(item.return_20d, 1) },
      { key: "return_60d", label: "60日动量", value: formatRatioAsPercent(item.return_60d, 1) },
      { key: "return_120d", label: "120日动量", value: formatRatioAsPercent(item.return_120d, 1) },
      { key: "ma20_distance", label: "MA20距离", value: formatRatioAsPercent(item.close_to_ma20, 1) },
      { key: "amount_ratio", label: "量能", value: `${formatNumber(item.amount_ratio, 2)}x` },
      {
        key: "turn_amplitude",
        label: "换手/振幅",
        value: `换手 ${formatNumber(item.turn, 2)}% / 振幅 ${formatNumber(item.amplitude, 2)}%`,
      },
      { key: "concepts", label: "题材线索", value: concepts },
      { key: "formula_version", label: "公式版本", value: formula },
    ];
    const evidence = evidenceBullets.map((bullet) => `${bullet.label}：${bullet.value}`);

    return {
      rank: item.rank,
      stockCode: item.stock_code,
      stockName: item.stock_name,
      sectorCode: item.sector_code,
      sectorName: item.sector_name,
      headline: `新趋势观察 #${item.rank} · ${item.stock_name}`,
      pattern: "突破",
      patternNote: "新趋势观察池为只读候选，需人工复核行业、题材和风险退出证据。",
      distanceToBreakoutPct: `MA20 ${formatRatioAsPercent(item.close_to_ma20, 1)}`,
      evidenceBullets,
      evidence,
      counterEvidence: [
        "过热门控下仅作观察补充，不构成趋势突破交易指令。",
        "涨停连板、公告/新闻与盘中成交顺序仍需人工复核。",
      ],
      invalidationRules: [
        "回落至 MA20 下方或量能失真时降级观察。",
        "旧经济行业、ST/停牌或数据质量异常时不得继续解释为新趋势。",
      ],
      rawFields: [
        { key: "close", label: "收盘", value: formatNumber(item.close, 4) },
        { key: "ma20", label: "20日均线", value: formatNumber(item.ma20, 4) },
        { key: "ma60", label: "60日均线", value: formatNumber(item.ma60, 4) },
        { key: "ma120", label: "120日均线", value: formatNumber(item.ma120, 4) },
        { key: "return_20d", label: "20日收益", value: formatNumber(item.return_20d, 6) },
        { key: "return_60d", label: "60日收益", value: formatNumber(item.return_60d, 6) },
        { key: "return_120d", label: "120日收益", value: formatNumber(item.return_120d, 6) },
        { key: "close_to_ma20", label: "MA20距离", value: formatNumber(item.close_to_ma20, 6) },
        { key: "amount_ratio", label: "量比", value: formatNumber(item.amount_ratio, 6) },
        { key: "hlimitedays", label: "连板天数", value: item.hlimitedays == null ? "待补" : String(item.hlimitedays) },
        { key: "score", label: "观察分", value: formatNumber(item.score, 6) },
      ],
    };
  });
}

function mapGateStateToTone(state: LivermoreMarketGateState): "进攻" | "中性" | "防御" {
  if (state === "HOT" || state === "WARM") return "进攻";
  if (
    state === "OVERHEAT" ||
    state === "OFF" ||
    state === "STALE" ||
    state === "NO_DATA" ||
    state === "PENDING_DATA"
  ) {
    return "防御";
  }
  return "中性";
}

function bucketExitDistance(params: {
  status: "triggered" | "watch";
  latest: number | null;
  exit: number | null;
}): { distanceToExitPct: string; exitDistanceBucket: StockRiskDistanceBucket } {
  const { status, latest, exit } = params;
  if (latest == null || exit == null || !Number.isFinite(latest) || !Number.isFinite(exit)) {
    return { distanceToExitPct: "待补", exitDistanceBucket: "待补" };
  }
  if (exit === 0) {
    return { distanceToExitPct: "待补", exitDistanceBucket: "待补" };
  }
  const pctRaw = ((latest - exit) / exit) * 100;
  const pctLabel = `${pctRaw >= 0 ? "+" : ""}${pctRaw.toFixed(2)}%`;
  if (status === "triggered") {
    return {
      distanceToExitPct: pctLabel,
      exitDistanceBucket: "triggered",
    };
  }
  const pct = pctRaw;
  const bucket: StockRiskDistanceBucket =
    pct <= 3 ? "0-3%" : pct <= 6 ? "3-6%" : ">6%";
  return { distanceToExitPct: pctLabel, exitDistanceBucket: bucket };
}

function numericFromDisplay(formatted: string): number | null {
  const n = Number.parseFloat(formatted);
  return Number.isFinite(n) ? n : null;
}

function metricValueForView(row: StockSectorRow, view: StockSectorViewKind): number | null {
  switch (view) {
    case "score":
      return row.scoreValue;
    case "pctchange":
      return row.pctChangeValue;
    case "turnover":
      return row.turnoverValue;
    case "amplitude":
      return row.amplitudeValue;
    default:
      return row.scoreValue;
  }
}

function formatFreshnessLabel(meta: StockViewModelMeta = {}): string {
  const quality = meta.quality_flag ?? "pending";
  const vendor = meta.vendor_status ?? "pending";
  const fallback = meta.fallback_mode && meta.fallback_mode !== "none" ? ` / ${localizeFallbackMode(meta.fallback_mode)}` : "";
  return `新鲜度 ${localizeMetaQualityFlag(quality)} / ${localizeMetaVendorStatus(vendor)}${fallback}`;
}

function localizeMetaQualityFlag(value: string | undefined): string {
  const normalized = (value ?? "pending").trim().toLowerCase();
  const labels: Record<string, string> = {
    ok: "质量正常",
    warning: "质量需复核",
    stale: "数据陈旧",
    error: "质量异常",
    pending: "质量待确认",
  };
  return labels[normalized] ?? "质量待确认";
}

function localizeMetaVendorStatus(value: string | undefined): string {
  const normalized = (value ?? "pending").trim().toLowerCase();
  const labels: Record<string, string> = {
    ok: "供数正常",
    degraded: "供数降级",
    error: "供数异常",
    pending: "供数待确认",
  };
  return labels[normalized] ?? "供数待确认";
}

function localizeFallbackMode(value: string | undefined): string {
  const normalized = (value ?? "none").trim().toLowerCase();
  if (!normalized || normalized === "none") return "数据正常";
  const labels: Record<string, string> = {
    latest_snapshot: "数据延迟",
    cache: "数据延迟",
    mock: "演示数据",
  };
  return labels[normalized] ?? "待确认";
}

export function localizeStockDataFamily(inputFamily: string | null | undefined): string {
  const value = inputFamily?.trim();
  if (!value) return "待补";
  const normalized = value.toLowerCase().replace(/[\s-]+/g, "_");
  const labels: Record<string, string> = {
    breadth: "市场宽度",
    limit_up_quality: "涨停质量",
    sector_strength: "板块强弱",
    sector_rank: "板块强弱",
    stock_universe: "股票池",
    stock_candidates: "趋势候选",
    stock_candidate: "趋势候选",
    uptrend_momentum_candidates: "上升趋势",
    uptrend_momentum: "上升趋势",
    fresh_trend_watchlist: "新趋势观察",
    mean_reversion_candidates: "超跌池",
    factor_screen_candidates: "多因子",
    factor_screen: "多因子",
    theme_breakout: "题材观察",
    hybrid_fusion: "融合池",
    risk_exit: "风险退出",
    position_risk: "持仓风险",
    market_gate: "市场门控",
    pmi: "PMI",
    credit_impulse: "信用脉冲",
    macro_score: "宏观分",
    price_spread: "价差",
  };
  return labels[normalized] ?? "输入待确认";
}

function localizeStockStrategyLabel(
  strategyLabel: string | null | undefined,
  signalKind: string | null | undefined,
): string {
  const label = strategyLabel?.trim();
  const normalizedLabel = label?.toLowerCase().replace(/[\s-]+/g, "_");
  const signalLabel = localizeStockDataFamily(signalKind);
  const fallbackLabel = signalLabel === "输入待确认" ? "策略待确认" : signalLabel;
  if (!label) return fallbackLabel;
  if (label === signalKind || normalizedLabel === signalKind?.trim().toLowerCase().replace(/[\s-]+/g, "_")) {
    return fallbackLabel;
  }
  const compactLabel = normalizedLabel?.replace(/_/g, "");
  if (
    normalizedLabel?.includes("external_vendor") ||
    normalizedLabel?.includes("vendor_") ||
    normalizedLabel?.includes("source_table") ||
    compactLabel?.includes("externalvendor") ||
    compactLabel?.includes("vendor") ||
    compactLabel?.includes("sourcetable") ||
    compactLabel?.includes("choicestock")
  ) {
    return fallbackLabel;
  }
  return label;
}

function strategyPrioritySummaryStatus(label: string | null | undefined): {
  label: string;
  badgeLabel: string;
  tone: StockClosedLoopTone;
} {
  const value = label?.trim();
  if (value === "优先复核") return { label: "优先复核", badgeLabel: "已就绪", tone: "positive" };
  if (value === "降权观察") return { label: "降权观察", badgeLabel: "降权观察", tone: "warning" };
  if (value === "继续观察") return { label: "继续观察", badgeLabel: "观察", tone: "neutral" };
  if (value === "样本不足") return { label: "样本不足", badgeLabel: "待补", tone: "warning" };
  return { label: "状态待确认", badgeLabel: "待确认", tone: "warning" };
}

function localizeDataGapStatus(status: string | null | undefined): string {
  const normalized = (status ?? "").trim().toLowerCase();
  const labels: Record<string, string> = {
    ready: "已就绪",
    missing: "缺数据",
    stale: "已陈旧",
    partial: "部分",
    blocked: "阻断",
  };
  return labels[normalized] ?? (normalized ? "状态待确认" : "待补");
}

function localizeDiagnosticScope(inputFamily: string | null | undefined): string {
  const familyLabel = localizeStockDataFamily(inputFamily);
  return familyLabel === "待补" ? "策略诊断" : `${familyLabel}诊断`;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function scrubUnknownBackendFamily(value: string, inputFamily: string | null | undefined, familyLabel: string): string {
  const rawFamily = inputFamily?.trim();
  if (!rawFamily || familyLabel !== "输入待确认") return value;
  const spacedFamily = rawFamily.replace(/[_-]+/g, " ");
  return value
    .replace(new RegExp(escapeRegExp(rawFamily), "gi"), familyLabel)
    .replace(new RegExp(escapeRegExp(spacedFamily), "gi"), familyLabel);
}

function isUnknownBackendCodeOnly(value: string, familyLabel: string): boolean {
  if (familyLabel !== "输入待确认") return false;
  return /^[A-Za-z][A-Za-z0-9_.:-]*$/.test(value) && /[_:.-]/.test(value);
}

export function localizeStockBackendText(
  text: string | null | undefined,
  inputFamily?: string | null,
): string {
  const value = text?.trim();
  if (!value) return "说明待补";
  const lower = value.toLowerCase();
  const familyLabel = inputFamily ? localizeStockDataFamily(inputFamily) : "";
  const displayValue = scrubUnknownBackendFamily(value, inputFamily, familyLabel);
  if (isUnknownBackendCodeOnly(value, familyLabel)) return "说明待确认";
  if ((lower.includes("external_vendor") || lower.includes("vendor_")) && /pending|guard|unavailable/.test(lower)) {
    return "风险待确认";
  }
  if (lower.includes("external_vendor") || lower.includes("vendor_")) {
    if (lower.includes("not landed") || lower.includes("未落地")) return `${familyLabel || "输入待确认"} 未落地`;
    return "说明待确认";
  }
  const availableSample = value.match(/\b(T\+\d+)\s+available\s+(\d+)\s*\/\s*(\d+)/i);
  const matureSnapshotSample = value.match(/\b(T\+\d+)\s+matured?\s+snapshots?\s+(\d+)\s*\/\s*(\d+)/i);
  const optimizationSample = value.match(/\b(T\+\d+)\s+sample\s+(\d+)/i);
  const optimizationAvgReturn = value.match(/\bavg(?:erage)?(?:\s+return)?\s*([+-]?\d+(?:\.\d+)?%)/i);
  const optimizationWinRate = value.match(/\bwin\s+rate\s*([+-]?\d+(?:\.\d+)?%)/i);
  if (lower.includes("current market sample") && lower.includes("insufficient")) {
    const sampleText = availableSample
      ? `${availableSample[1].toUpperCase()} ${availableSample[2]}/${availableSample[3]}`
      : "";
    return sampleText ? `样本不足 ${sampleText}` : "样本不足";
  }
  if (matureSnapshotSample) {
    const suffix = lower.includes("waiting for more mature days") ? "等待更多成熟日。" : "可作为强优先复核。";
    return `${matureSnapshotSample[1].toUpperCase()} 已成熟快照 ${matureSnapshotSample[2]}/${matureSnapshotSample[3]}，${suffix}`;
  }
  if (optimizationSample && (optimizationAvgReturn || optimizationWinRate || lower.includes("priority review ranking"))) {
    const parts = [`${optimizationSample[1].toUpperCase()} 样本 ${optimizationSample[2]}`];
    if (optimizationAvgReturn) parts.push(`均值 ${optimizationAvgReturn[1]}`);
    if (optimizationWinRate) parts.push(`胜率 ${optimizationWinRate[1]}`);
    if (lower.includes("priority review ranking")) parts.push("优先复核排序");
    return `${parts.join("，")}。`;
  }
  if (lower.includes("observation-only candidate")) {
    return `${familyLabel || "候选"}仅观察候选。`;
  }
  if (lower.includes("hybrid fusion") && lower.includes("observation-only") && lower.includes("warm/hot")) {
    return "融合策略仅在温和/偏热门控下进入候选；当前门控不满足时只保留观察。";
  }
  if (lower.includes("hybrid fusion") && lower.includes("proxy inputs")) {
    return "融合策略使用代理输入，仅作观察复核。";
  }
  if (lower.includes("stock candidate policy") && lower.includes("inactive in overheat")) {
    return "趋势突破策略在过热门控下暂停；仅在偏热/温和门控下进入候选。";
  }
  if (lower.includes("uptrend momentum watchlist is paused") && lower.includes("warm or hot")) {
    return "上升趋势策略在过热门控下暂停；仅在温和/偏热门控下进入候选。";
  }
  if (lower.includes("mean reversion watchlist is paused") && lower.includes("overheat")) {
    return "超跌反弹观察池在过热门控下暂停；当前由防守趋势候选覆盖。";
  }
  if (lower.includes("daily_limit_flags absent") && lower.includes("replay unsupported")) {
    const dateMatch = value.match(/\b(\d{4}-\d{2}-\d{2})\b/);
    return `涨停封单标记缺失；${dateMatch?.[1] ?? "该日"} 回放不可用。`;
  }
  if (lower.includes("overheat") && lower.includes("rank > 10") && lower.includes("factor")) {
    return "过热门控下 rank > 10 的多因子候选降权观察；优先复核仅覆盖前10名。";
  }
  if (lower.includes("observation-only output") && lower.includes("does not generate trading instructions")) {
    return "仅输出观察结果，不生成交易指令。";
  }
  if (lower.includes("no stock candidates available for observation")) {
    return "当前门控下暂无趋势候选进入观察。";
  }
  if (lower.includes("breadth inputs are unavailable")) {
    return "市场宽度输入不可用。";
  }
  if (
    lower.includes("choice limit-up quality catalog is confirmed") &&
    lower.includes("trend-only slice")
  ) {
    return "涨停质量目录已确认，但落地输入不可用；市场门控已限制为仅趋势切片。";
  }
  if (lower.includes("choice stock materialized input coverage is incomplete")) {
    const dateMatch = value.match(/for (\d{4}-\d{2}-\d{2})/i);
    const itemsMatch = value.match(/request items:\s*(.+)$/i);
    const datePart = dateMatch?.[1] ?? "目标日";
    const itemsPart = itemsMatch?.[1]?.replace(/:/g, "：") ?? "部分输入";
    return `Choice 股票物化输入覆盖不完整（${datePart}）；缺数据项：${itemsPart}。`;
  }
  if (lower.includes("materialized input coverage incomplete")) {
    return `${familyLabel || "策略"}物化输入覆盖不完整。`;
  }
  if (lower.includes("5-day breadth input family is not landed")) {
    return "5日市场宽度输入未落地。";
  }
  if (lower.includes("crowded leaders without breadth confirmation")) {
    return "强势样本拥挤，市场宽度未确认。";
  }
  if (lower.includes("concept membership table pending")) {
    return "概念归属待确认。";
  }
  if (lower.includes("signal confluence diagnostic") && lower.includes("pending") && lower.includes("detail")) {
    return "联动诊断待确认。";
  }
  if (lower.includes("factor_snapshot") && lower.includes("无数据")) {
    return "因子快照无数据。";
  }
  if (lower.includes("position snapshot") && lower.includes("not landed")) {
    return "持仓快照未落地。";
  }
  if (
    lower.includes("risk-exit evidence") &&
    lower.includes("position snapshot") &&
    lower.includes("stale")
  ) {
    return "持仓快照已陈旧，风险退出证据待补。";
  }
  if (
    lower.includes("livermore_position_snapshot") ||
    (lower.includes("position snapshot") && (lower.includes("active a-share") || lower.includes("missing")))
  ) {
    return "持仓快照缺失，暂无可执行风险退出样本。";
  }
  if (
    lower.includes("daily sector strength observation rank is a signed-off analytical formula") &&
    lower.includes("not trading instructions")
  ) {
    return "板块强弱观察排名已按 50% 涨跌幅分位、30% 换手率分位、20% 振幅分位签核；用于复核优先级与行业过滤，不构成交易指令；多日动量、板块资金流与拥挤度不包含在当前版本内。";
  }
  if (
    lower.includes("daily sector score is an analytical observation formula") &&
    lower.includes("metric-definition sign-off")
  ) {
    return "板块强弱为分析观察公式，仍待指标定义签核；多日动量持续性与板块资金流不包含在当前公式内。";
  }
  if (lower.includes("pending")) {
    const pendingLabel =
      lower.includes("t+5") || lower.includes("return") || lower.includes("收益") ? "待成熟" : "待确认";
    return displayValue
      .replace(/最新\s*pending\s*日期/gi, `最新${pendingLabel}日期`)
      .replace(/\bpending\b/gi, pendingLabel);
  }
  if (lower.includes("theme breakout execution is paused") && lower.includes("overheat")) {
    return "市场过热门控下暂停题材观察；历史回放显示该桶拖累。";
  }
  if (lower.includes("market gate is available") && lower.includes("pmi") && lower.includes("credit impulse")) {
    return "市场门控已有可用证据，PMI 与信用脉冲待补。";
  }
  if (lower.includes("all broad-index and supplement gate inputs are landed")) {
    return "宽基指数与补充门控输入已落地，可用于当前交易日。";
  }
  if (lower.includes("sector ranking is available from landed choice sector inputs")) {
    return "板块排名已接入 Choice 板块输入。";
  }
  if (
    lower.includes("sector rank currently uses the provisional percentile formula") &&
    lower.includes("pctchange") &&
    lower.includes("turn") &&
    lower.includes("amplitude")
  ) {
    return "板块强弱仍使用涨跌幅、换手率与振幅的临时分位公式，需按观测口径复核。";
  }
  if (lower.includes("candidate screening is available for landed choice stock inputs")) {
    return "候选筛选已接入 Choice 个股输入。";
  }
  if (lower.includes("risk and exit output is available from landed position snapshots and close history")) {
    return "风险退出已接入持仓快照与收盘历史。";
  }
  if (lower.includes("sector_rank is available")) {
    return "板块强弱已有可用证据。";
  }
  return displayValue
    .replace(/\bbreadth\b/gi, familyLabel || "市场宽度")
    .replace(/\bmarket gate\b/gi, "市场门控")
    .replace(/\binput family\b/gi, "输入")
    .replace(/\bnot landed\b/gi, "未落地")
    .replace(/\bmissing\b/gi, "缺数据")
    .replace(/\bunsupported\b/gi, "不可用")
    .replace(/\bfallback\b/gi, "回退")
    .replace(/\bproxy-only\b/gi, "仅代理观察")
    .replace(/\bproxy\b/gi, "代理观察")
    .replace(/_/g, " ");
}

function localizeBasisLabel(basis: string | null | undefined): string {
  const normalized = (basis ?? "").trim().toLowerCase();
  if (normalized === "analytical") return "分析口径（非交易）";
  if (normalized === "formal") return "正式口径";
  if (!normalized) return "口径待补";
  return "口径待确认";
}

export type StockAnalysisPagePurpose = {
  eyebrow: string;
  title: string;
  subtitle: string;
  asOfLine: string;
  dataStatusLine: string;
};

export function buildStockAnalysisPagePurpose(
  payload: LivermoreStrategyPayload,
  meta: StockViewModelMeta = {},
): StockAnalysisPagePurpose {
  const quality = meta.quality_flag ?? "pending";
  const vendor = meta.vendor_status ?? "pending";
  const fallback = meta.fallback_mode ?? "none";
  const aligned = quality === "ok" && vendor === "ok" && fallback === "none";
  const asOf = payload.as_of_date ?? "日期待补";
  return {
    eyebrow: "趋势策略 · 只读复核台",
    title: "股票策略复核台",
    subtitle: "只读复核，不生成交易指令",
    asOfLine: `观察日 ${asOf}`,
    dataStatusLine: aligned
      ? `数据状态：已对齐（${asOf}）`
      : `数据状态：待复核 · ${localizeMetaQualityFlag(quality)} / ${localizeMetaVendorStatus(vendor)}${
          fallback !== "none" ? ` / ${localizeFallbackMode(fallback)}` : ""
        }`,
  };
}

export type StockReviewQueueEmptyState = {
  headline: string;
  detail: string;
};

export function buildReviewQueueEmptyState(payload: LivermoreStrategyPayload): StockReviewQueueEmptyState {
  const factorCount = isStockModulePrimaryExcluded(payload, "factor_screen_candidates")
    ? 0
    : (payload.factor_screen_candidates?.candidate_count ?? 0);
  const hybridCount = isStockModulePrimaryExcluded(payload, "hybrid_fusion")
    ? 0
    : (payload.hybrid_fusion_candidates?.candidate_count ?? 0);
  const nextParts: string[] = [];
  if (factorCount > 0) {
    nextParts.push(`可先看多因子池 ${factorCount} 只`);
  } else if (hybridCount > 0) {
    nextParts.push(`可先看融合策略池 ${hybridCount} 只`);
  } else {
    nextParts.push("可下翻「深度分析」查看各观察池");
  }
  return {
    headline: "今天没有进入复核队列的候选",
    detail: `${nextParts.join("；")}；请先看下方「策略共振」与「多策略观察池」。`,
  };
}

export function buildDailyJudgmentStrip(payload: LivermoreStrategyPayload): StockDailyJudgmentStrip {
  const gate = payload.market_gate;
  const tone = mapGateStateToTone(gate.state);
  const headline = `今日市场状态：${tone} — 通过 ${gate.passed_conditions} / ${gate.required_conditions} 条门控`;
  const gateChip = `门控 ${gate.passed_conditions}/${gate.required_conditions}`;
  const exposureChip = `暴露 ${formatRatioAsPercent(gate.exposure)}`;
  const items = [...(payload.sector_rank?.items ?? [])].sort((a, b) => a.rank - b.rank);
  const strongest = items[0];
  const weakest = items.length ? items[items.length - 1] : undefined;
  return {
    headline,
    gateChip,
    exposureChip,
    strongestSectorChip: strongest
      ? `最强 ${strongest.sector_name} (${formatPercent(strongest.avg_pctchange)})`
      : "最强板块：待补",
    weakestSectorChip: weakest
      ? `最弱 ${weakest.sector_name} (${formatPercent(weakest.avg_pctchange)})`
      : "最弱板块：待补",
  };
}

export function buildInlineMetaSegments(
  payload: LivermoreStrategyPayload,
  extras: Partial<{
    quality_flag: string;
    vendor_status: string;
    source_version: string;
    rule_version: string;
    fallback_mode: string;
  }>,
): StockMetaSegment[] {
  const out: StockMetaSegment[] = [
    { key: "as_of", text: payload.as_of_date ?? "日期待补" },
    { key: "source_version", text: extras.source_version ?? "待补" },
    { key: "rule_version", text: extras.rule_version ?? "待补" },
    { key: "quality_flag", text: extras.quality_flag ? localizeMetaQualityFlag(extras.quality_flag) : "待补" },
    { key: "vendor_status", text: extras.vendor_status ? localizeMetaVendorStatus(extras.vendor_status) : "待补" },
    { key: "fallback_mode", text: extras.fallback_mode ? localizeFallbackMode(extras.fallback_mode) : "待补" },
  ];
  return out;
}

function countBoundaryItems(payload: LivermoreStrategyPayload): number {
  return (
    actionableDiagnostics(payload).length +
    activeDataGaps(payload).length +
    actionableUnsupportedOutputs(payload).length
  );
}

function sectorRankFormulaGovernanceLabel(
  sectorRank: LivermoreStrategyPayload["sector_rank"] | null | undefined,
): string | undefined {
  if (!sectorRank) return undefined;
  const status = String(sectorRank.formula_status ?? "").trim().toLowerCase();
  const statusLabel =
    status === "signed_off"
      ? "规则已签核"
      : status === "review_pending" || sectorRank.is_provisional
        ? "规则待签核"
        : "规则待确认";
  const formulaVersion = sectorRank.formula_version || "公式版本待补";
  return `${statusLabel} / ${formulaVersion}`;
}

export function isActionableLivermoreUnsupportedOutput(
  output: LivermoreStrategyPayload["unsupported_outputs"][number],
): boolean {
  return !isKnownLivermorePolicyPause(output.reason);
}

function activeDataGaps(payload: LivermoreStrategyPayload) {
  return payload.data_gaps.filter((gap) => gap.status !== "ready");
}

function actionableDiagnostics(payload: LivermoreStrategyPayload) {
  return payload.diagnostics.filter((item) => item.severity !== "info");
}

function actionableUnsupportedOutputs(payload: LivermoreStrategyPayload) {
  return payload.unsupported_outputs.filter(isActionableLivermoreUnsupportedOutput);
}

function isKnownLivermorePolicyPause(reason: string | null | undefined): boolean {
  const lower = (reason ?? "").trim().toLowerCase();
  return (
    (lower.includes("stock candidate policy") && lower.includes("inactive in overheat")) ||
    lower.includes("mean reversion watchlist is paused") ||
    (lower.includes("theme breakout execution is paused") && lower.includes("overheat")) ||
    (lower.includes("hybrid fusion is observation-only") && lower.includes("warm/hot")) ||
    (lower.includes("uptrend momentum watchlist is paused") && lower.includes("warm or hot"))
  );
}

const MACRO_GAP_FAMILIES = new Set(["pmi", "credit_impulse", "macro_score", "price_spread"]);

function isMacroGapFamily(inputFamily: string): boolean {
  return MACRO_GAP_FAMILIES.has(inputFamily.trim().toLowerCase());
}

function macroGapLabels(payload: LivermoreStrategyPayload): string[] {
  return payload.data_gaps
    .filter((gap) => gap.status !== "ready" && isMacroGapFamily(gap.input_family))
    .map((gap) => `${localizeStockDataFamily(gap.input_family)} ${macroGapStatusLabel(gap.status)}`);
}

function macroGapStatusLabel(status: string | null | undefined): string {
  const normalized = (status ?? "").trim().toLowerCase();
  const labels: Record<string, string> = {
    blocked: "阻断",
    missing: "缺失",
    partial: "部分",
    stale: "陈旧",
  };
  return labels[normalized] ?? "状态待确认";
}

export function buildCycleMacroLayerSummary(
  payload: LivermoreStrategyPayload,
): StockCycleMacroLayerSummary | null {
  const macroLayer = payload.cycle_rotation_framework?.macro_layer;
  if (!macroLayer) {
    return null;
  }

  const hybridFormula = payload.hybrid_fusion_candidates?.formula_version?.trim() || "";
  const formulaVersionLabel =
    hybridFormula || "rv_hybrid_fusion_candidates_v3";
  const macroScoreLabel =
    macroLayer.macro_score == null ? "待补" : formatNumber(macroLayer.macro_score, 4);
  const availableInputs = macroLayer.available_inputs ?? [];
  const missingInputs = macroLayer.missing_inputs ?? [];
  const macroGapLabelsList = macroGapLabels(payload);
  const ready = macroLayer.ready === true;

  let statusLabel: StockCycleMacroLayerSummary["statusLabel"];
  let tone: StockClosedLoopTone;
  if (ready) {
    statusLabel = "已落地";
    tone = "positive";
  } else if (availableInputs.length > 0) {
    statusLabel = "部分就绪";
    tone = "warning";
  } else {
    statusLabel = "待补";
    tone = "negative";
  }

  const detailParts = [
    `可用 ${availableInputs.map(localizeStockDataFamily).join("、") || "-"}`,
    `缺失 ${missingInputs.map(localizeStockDataFamily).join("、") || "-"}`,
  ];
  if (macroGapLabelsList.length > 0) {
    detailParts.push(`缺口 ${macroGapLabelsList.join(" / ")}`);
  }

  return {
    statusLabel,
    tone,
    macroScoreLabel,
    formulaVersionLabel,
    evidence: macroLayer.evidence?.trim() || "宏观层证据待补",
    availableInputs,
    missingInputs,
    macroGapLabels: macroGapLabelsList,
    detailLabel: detailParts.join(" · "),
  };
}

export function buildDataBoundarySummary(
  payload: LivermoreStrategyPayload,
  meta: StockViewModelMeta = {},
): StockDataBoundarySummary {
  const diagnostics = actionableDiagnostics(payload);
  const dataGaps = activeDataGaps(payload);
  const unsupported = actionableUnsupportedOutputs(payload);
  const topMessages = [
    ...diagnostics.map((item) => localizeStockBackendText(item.message, item.input_family)),
    ...dataGaps.map(
      (gap) =>
        `${localizeStockDataFamily(gap.input_family)} ${localizeDataGapStatus(gap.status)}：${localizeStockBackendText(
          gap.evidence,
          gap.input_family,
        )}`,
    ),
    ...unsupported.map(
      (item) => `${localizeStockDataFamily(item.key)}：${localizeStockBackendText(item.reason, item.key)}`,
    ),
  ].slice(0, 4);
  const freshnessLabel = formatFreshnessLabel(meta);
  const boundaryCount = diagnostics.length + dataGaps.length + unsupported.length;

  return {
    boundaryCount,
    diagnosticsCount: diagnostics.length,
    dataGapCount: dataGaps.length,
    unsupportedCount: unsupported.length,
    freshnessLabel,
    summaryLabel: boundaryCount > 0 ? `${boundaryCount} 条边界` : "边界清晰",
    detailLabel: `诊断 ${diagnostics.length} / 缺口 ${dataGaps.length} / 阻断 ${unsupported.length} / ${freshnessLabel}`,
    topMessages,
  };
}

function isMetaBoundary(meta: StockViewModelMeta = {}): boolean {
  const quality = meta.quality_flag ?? "pending";
  const vendor = meta.vendor_status ?? "pending";
  const fallback = meta.fallback_mode ?? "none";
  return quality !== "ok" || vendor !== "ok" || fallback !== "none";
}

function evidenceToneForStatus(status: string): StockClosedLoopTone {
  const normalized = status.toLowerCase();
  if (normalized === "ok" || normalized === "complete" || normalized === "analytical") {
    return "positive";
  }
  if (normalized === "error" || normalized === "blocked") {
    return "negative";
  }
  if (
    normalized === "warning" ||
    normalized === "degraded" ||
    normalized === "stale" ||
    normalized === "pending" ||
    normalized === "missing" ||
    normalized === "fallback"
  ) {
    return "warning";
  }
  return "neutral";
}

function eventLevelFromSeverity(severity: string): StockAnalysisEventMonitorRow["level"] {
  return severity === "error" ? "error" : severity === "warning" ? "warning" : "info";
}

function eventToneLevel(tone: StockClosedLoopTone): StockAnalysisEventMonitorRow["level"] {
  return tone === "negative" ? "error" : tone === "positive" ? "info" : "warning";
}

function detailFromEventEvidence(evidence: string[] | string | null | undefined, fallback: string): string {
  return normalizeEvidence(evidence)[0] ?? fallback;
}

export function buildStockAnalysisKpiStrip(
  payload: LivermoreStrategyPayload,
  confluence: LivermoreSignalConfluencePayload | null,
  meta: StockViewModelMeta = {},
): StockAnalysisKpiItem[] {
  const queue = buildCandidateReviewQueue(payload);
  const sectors = buildSectorRows(payload);
  const riskRows = buildRiskExitRows(payload, confluence);
  const boundarySummary = buildDataBoundarySummary(payload, meta);
  const closedLoopSummary = buildClosedLoopSummary(payload, confluence, meta);
  const strongest = sectors[0];
  const weakest = sectors.length ? sectors[sectors.length - 1] : null;
  const riskTriggered = riskRows.filter((row) => row.status === "triggered").length;
  const riskWatch = riskRows.filter((row) => row.status === "watch").length;
  const hasBoundary = boundarySummary.boundaryCount > 0 || isMetaBoundary(meta);

  return [
    {
      key: "market-state",
      label: "市场状态",
      value: localizeMarketDataStatus(payload.market_gate.state),
      detail: `观察暴露 ${formatRatioAsPercent(payload.market_gate.exposure)}`,
      tone: hasBoundary ? "warning" : "positive",
      gaugeValue: clampRatio(payload.market_gate.exposure),
    },
    {
      key: "review-queue",
      label: "复核队列",
      value: String(queue.length),
      detail: queue[0] ? `优先 ${queue[0].stockName} / ${queue[0].sectorName}` : "候选待补",
      tone: queue.length > 0 ? "positive" : "neutral",
      gaugeValue: clampRatio(queue.length / 6),
    },
    {
      key: "sector-strength",
      label: "板块强弱",
      value: strongest ? strongest.sectorName : "待补",
      detail: weakest ? `弱侧 ${weakest.sectorName} / ${weakest.pctChange}` : "弱侧待补",
      tone: strongest ? "positive" : "warning",
      gaugeValue: clampRatio(strongest?.scoreValue),
    },
    {
      key: "risk-observation",
      label: "风险观察",
      value: String(riskRows.length),
      detail: `触发 ${riskTriggered} / 观察 ${riskWatch}`,
      tone: riskTriggered > 0 ? "negative" : riskWatch > 0 ? "warning" : "positive",
      gaugeValue: clampRatio(riskRows.length / 4),
    },
    {
      key: "closed-loop",
      label: "闭环状态",
      value: closedLoopSummary.referenceRating.label,
      detail: closedLoopSummary.summaryLabel,
      tone: closedLoopSummary.referenceRating.tone,
      gaugeValue: closedLoopSummary.referenceRating.tone === "positive" ? 1 : closedLoopSummary.referenceRating.tone === "warning" ? 0.55 : 0.28,
    },
    {
      key: "data-boundary",
      label: "数据边界",
      value: String(boundarySummary.boundaryCount),
      detail: boundarySummary.detailLabel,
      tone: boundarySummary.boundaryCount > 0 || isMetaBoundary(meta) ? "warning" : "positive",
      gaugeValue: clampRatio(boundarySummary.boundaryCount / 6),
    },
  ];
}

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

function meanReversionMarketActiveLabel(
  marketState: LivermoreMarketGateState,
  candidateCount: number,
): string {
  if (marketState !== "WARM") return "门控暂停";
  return candidateCount > 0 ? "条件触发" : "";
}

function compactStrategyLedgerText(value: string, maxLength = 38): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength)}…`;
}

function shortStrategyBlockerLabel(value: string): string {
  if (value.includes("物化输入覆盖不完整")) {
    return "物化输入覆盖不完整，详见证据账本。";
  }
  if (value.includes("持仓快照缺失")) {
    return "持仓快照缺失，暂不生成该输出。";
  }
  return compactStrategyLedgerText(value);
}

function shortStrategyCoverageLabel(
  text: string | null | undefined,
  inputFamily: string,
  fallback: string,
): string {
  if (!text?.trim()) return fallback;
  const localized = localizeStockBackendText(text, inputFamily);
  if (/hybrid fusion/i.test(text)) return fallback;
  const firstClause = localized.split(/[。；;]/)[0] || localized;
  return compactStrategyLedgerText(firstClause, 42);
}

function strategyCandidateCountLabel(count: number): string {
  return `${count} 只候选`;
}

function strategyBlockerLabel(state: StockStrategyLensItem["state"], statusDetail: string): string {
  if (state === "ready" || state === "empty") return "无阻断";
  return statusDetail || "阻断待确认";
}

function strategyFocusLabel(params: {
  label: string;
  state: StockStrategyLensItem["state"];
  candidates: StockStrategyLensItem["candidates"];
  fallback: string;
}): string {
  const top = params.candidates[0];
  if (top) {
    return `优先核验 ${top.stockName} ${top.stockCode}，再复核${params.label}证据边界。`;
  }
  if (params.state === "blocked" || params.state === "pending") {
    return `补齐${params.label}输入后复核。`;
  }
  if (params.state === "paused") {
    return `${params.label}受门控暂停，等待市场状态重新开放。`;
  }
  return params.fallback;
}

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

export function buildThemeLeaderPreviewItems(
  cards: StockThemeBreakoutCard[],
  limit = 12,
): StockThemeLeaderPreviewItem[] {
  const items: StockThemeLeaderPreviewItem[] = [];
  for (const card of cards) {
    for (const leader of card.leaders) {
      items.push({
        stockCode: leader.stockCode,
        stockName: leader.stockName,
        themeName: card.themeName,
        themeRank: card.rank,
        pctChange: leader.pctChange,
        turn: leader.turn,
        closeStrength: leader.closeStrength,
        tags: leader.tags,
      });
      if (items.length >= limit) {
        return items;
      }
    }
  }
  return items;
}

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

function sectorHeavyweightSourceLabel(source: string) {
  const labels: Record<string, string> = {
    theme_breakout: "题材强势",
    livermore: "趋势候选",
    fresh_trend_watchlist: "新趋势观察",
    factor_screen: "多因子",
    hybrid_fusion: "融合策略",
    mean_reversion: "超跌反弹",
    review_queue: "复核队列",
    sector_constituent: "板块成分",
  };
  return labels[source] ?? "来源待确认";
}

function sectorHeavyweightDetailSource(source: string): StockDetailSource {
  const sources: Record<string, StockDetailSource> = {
    theme_breakout: "theme_breakout",
    livermore: "livermore",
    fresh_trend_watchlist: "fresh_trend_watchlist",
    factor_screen: "factor_screen",
    hybrid_fusion: "hybrid_fusion",
    mean_reversion: "mean_reversion",
    review_queue: "review_queue",
    sector_constituent: "sector_constituent",
  };
  return sources[source] ?? "source_unconfirmed";
}

export function buildSectorHeavyweightPreview(
  payload: LivermoreStrategyPayload,
  options?: { sectorLimit?: number; stocksPerSector?: number },
): StockSectorHeavyweightPreviewSummary {
  const sectorLimit = options?.sectorLimit ?? 8;
  const stocksPerSector = options?.stocksPerSector ?? 3;
  const sectorRows = buildSectorRows(payload).slice(0, sectorLimit);
  if (sectorRows.length === 0) {
    return {
      rows: [],
      sectorLimit,
      sectorsWithSamples: 0,
      totalSampleCount: 0,
      uncoveredSectorCount: 0,
    };
  }

  type PoolEntry = {
    stockCode: string;
    stockName: string;
    sectorCode: string;
    sectorName: string;
    pctChangeValue: number | null;
    turnValue: number | null;
    closeStrengthValue: number | null;
    factorScoreValue: number | null;
    rankScore: number;
    source: string;
  };

  const pool = new Map<string, PoolEntry>();

  function upsert(entry: PoolEntry) {
    const key = `${entry.sectorCode}:${entry.stockCode}`;
    const existing = pool.get(key);
    if (!existing || entry.rankScore > existing.rankScore) {
      pool.set(key, entry);
    }
  }

  for (const item of payload.theme_breakout?.items ?? []) {
    for (const stock of item.items) {
      const pctChangeValue = finiteNumber(stock.pctchange);
      const turnValue = finiteNumber(stock.turn);
      upsert({
        stockCode: stock.stock_code,
        stockName: stock.stock_name,
        sectorCode: stock.sector_code,
        sectorName: stock.sector_name,
        pctChangeValue,
        turnValue,
        closeStrengthValue: finiteNumber(stock.close_strength),
        factorScoreValue: null,
        rankScore:
          (stock.strong ? 1000 : 0) +
          (stock.closed_up_limit ? 800 : 0) +
          (pctChangeValue ?? 0) * 10 +
          (turnValue ?? 0),
        source: "theme_breakout",
      });
    }
  }

  for (const stock of payload.stock_candidates?.items ?? []) {
    const turnValue = finiteNumber(stock.abnormal_turnover);
    const closeStrengthValue = finiteNumber(stock.close_strength);
    upsert({
      stockCode: stock.stock_code,
      stockName: stock.stock_name,
      sectorCode: stock.sector_code,
      sectorName: stock.sector_name,
      pctChangeValue: null,
      turnValue,
      closeStrengthValue,
      factorScoreValue: null,
      rankScore: 500 - stock.rank + (closeStrengthValue ?? 0) * 20 + (turnValue ?? 0),
      source: "livermore",
    });
  }

  for (const stock of payload.fresh_trend_watchlist?.items ?? []) {
    const pctChangeValue = finiteNumber(stock.pctchange);
    const turnValue = finiteNumber(stock.turn);
    const closeToMa20Value = finiteNumber(stock.close_to_ma20);
    const scoreValue = finiteNumber(stock.score);
    upsert({
      stockCode: stock.stock_code,
      stockName: stock.stock_name,
      sectorCode: stock.sector_code,
      sectorName: stock.sector_name,
      pctChangeValue,
      turnValue,
      closeStrengthValue: closeToMa20Value,
      factorScoreValue: scoreValue,
      rankScore: 360 - stock.rank + (scoreValue ?? 0) * 10 + (pctChangeValue ?? 0),
      source: "fresh_trend_watchlist",
    });
  }

  for (const stock of payload.hybrid_fusion_candidates?.items ?? []) {
    upsert({
      stockCode: stock.stock_code,
      stockName: stock.stock_name,
      sectorCode: stock.sector_code,
      sectorName: stock.sector_name,
      pctChangeValue: null,
      turnValue: null,
      closeStrengthValue: null,
      factorScoreValue: null,
      rankScore: 400 - stock.rank,
      source: "hybrid_fusion",
    });
  }

  for (const stock of payload.factor_screen_candidates?.items ?? []) {
    const factorScoreValue = finiteNumber(stock.score);
    upsert({
      stockCode: stock.stock_code,
      stockName: stock.stock_name,
      sectorCode: stock.sector_code,
      sectorName: stock.sector_name,
      pctChangeValue: null,
      turnValue: null,
      closeStrengthValue: null,
      factorScoreValue,
      rankScore: 300 - stock.rank + (factorScoreValue ?? 0) * 10,
      source: "factor_screen",
    });
  }

  for (const stock of payload.mean_reversion_candidates?.items ?? []) {
    upsert({
      stockCode: stock.stock_code,
      stockName: stock.stock_name,
      sectorCode: stock.sector_code,
      sectorName: stock.sector_name,
      pctChangeValue: null,
      turnValue: null,
      closeStrengthValue: null,
      factorScoreValue: finiteNumber(stock.score),
      rankScore: 250 - stock.rank + (finiteNumber(stock.score) ?? 0),
      source: "mean_reversion",
    });
  }

  for (const card of buildCandidateReviewQueue(payload)) {
    upsert({
      stockCode: card.stockCode,
      stockName: card.stockName,
      sectorCode: card.sectorCode,
      sectorName: card.sectorName,
      pctChangeValue: null,
      turnValue: null,
      closeStrengthValue: null,
      factorScoreValue: null,
      rankScore: 600 - card.rank,
      source: "review_queue",
    });
  }

  const leaderBySector = new Map(
    (payload.sector_rank?.items ?? []).map((item) => [item.sector_code, item.leader_constituents ?? []]),
  );

  function mapPoolEntryToPreview(entry: PoolEntry): StockSectorHeavyweightStockPreview {
    return {
      stockCode: entry.stockCode,
      stockName: entry.stockName,
      pctChange: entry.pctChangeValue != null ? formatPercent(entry.pctChangeValue) : "待补",
      turn: entry.turnValue != null ? formatNumber(entry.turnValue, 2) : "待补",
      closeStrength:
        entry.closeStrengthValue != null ? formatRatioAsPercent(entry.closeStrengthValue, 0) : "待补",
      sourceLabel: sectorHeavyweightSourceLabel(entry.source),
      detailSource: sectorHeavyweightDetailSource(entry.source),
      detailLabel:
        entry.source === "factor_screen" && entry.factorScoreValue != null
          ? `因子分 ${formatNumber(entry.factorScoreValue, 4)}`
          : entry.source === "mean_reversion" && entry.factorScoreValue != null
            ? `超跌分 ${formatNumber(entry.factorScoreValue, 2)}`
            : undefined,
    };
  }

  const rows = sectorRows.map((sector) => {
    const backendLeaders = leaderBySector.get(sector.sectorCode) ?? [];
    const usedCodes = new Set<string>();
    const stocks: StockSectorHeavyweightStockPreview[] = backendLeaders
      .slice(0, stocksPerSector)
      .map((leader) => {
        usedCodes.add(leader.stock_code);
        return {
          stockCode: leader.stock_code,
          stockName: leader.stock_name,
          pctChange: formatPercent(leader.pctchange),
          turn: formatNumber(leader.turn, 2),
          closeStrength: "待补",
          sourceLabel: sectorHeavyweightSourceLabel("sector_constituent"),
          detailSource: sectorHeavyweightDetailSource("sector_constituent"),
          auxiliaryLabel: `振幅 ${formatPercent(leader.amplitude)}`,
        };
      });

    if (stocks.length < stocksPerSector) {
      const supplemental = [...pool.values()]
        .filter((entry) => entry.sectorCode === sector.sectorCode && !usedCodes.has(entry.stockCode))
        .sort((left, right) => right.rankScore - left.rankScore)
        .slice(0, stocksPerSector - stocks.length)
        .map(mapPoolEntryToPreview);
      stocks.push(...supplemental);
    }

    return {
      sectorCode: sector.sectorCode,
      sectorName: sector.sectorName,
      sectorRank: sector.rank,
      sectorPctChange: sector.pctChange,
      sectorScore: sector.score,
      stocks,
      emptyReason:
        stocks.length === 0
          ? "板块成分与策略/题材观察池均未命中（请检查 sector_rank 供数）"
          : undefined,
    };
  });

  const sectorsWithSamples = rows.filter((row) => row.stocks.length > 0).length;
  const totalSampleCount = rows.reduce((count, row) => count + row.stocks.length, 0);

  return {
    rows,
    sectorLimit,
    sectorsWithSamples,
    totalSampleCount,
    uncoveredSectorCount: rows.length - sectorsWithSamples,
  };
}

export function buildStrategyLensItems(
  payload: LivermoreStrategyPayload,
  _consensus: ConsensusSummary,
): StockStrategyLensItem[] {
  type StrategyOutputKey = LivermoreStrategyPayload["unsupported_outputs"][number]["key"];

  const unsupportedOutput = (key: StrategyOutputKey) => payload.unsupported_outputs.find((output) => output.key === key);
  const unsupportedReason = (key: StrategyOutputKey) => unsupportedOutput(key)?.reason;
  const localizedReason = (key: StrategyOutputKey) =>
    localizeStockBackendText(unsupportedReason(key), key);
  const shortReason = (key: StrategyOutputKey) => shortStrategyBlockerLabel(localizedReason(key));
  const outputState = (key: StrategyOutputKey, candidateCount: number, exists: boolean) => {
    const output = unsupportedOutput(key);
    const policyPaused = output ? !isActionableLivermoreUnsupportedOutput(output) : false;
    if (isStockModulePrimaryExcluded(payload, key)) {
      if (policyPaused) {
        return {
          state: "paused" as const,
          tone: "neutral" as const,
          statusLabel: "策略暂停",
          statusDetail: shortReason(key),
        };
      }
      return {
        state: "paused" as const,
        tone: "warning" as const,
        statusLabel: "证据区",
        statusDetail: stockModulePrimaryReason(payload, key),
      };
    }
    const reason = unsupportedReason(key);
    if (candidateCount > 0) {
      return {
        state: "ready" as const,
        tone: "positive" as const,
        statusLabel: "已返回",
        statusDetail: "已有候选，进入只读复核。",
      };
    }
    if (reason) {
      if (policyPaused) {
        return {
          state: "paused" as const,
          tone: "neutral" as const,
          statusLabel: "策略暂停",
          statusDetail: shortReason(key),
        };
      }
      return {
        state: "blocked" as const,
        tone: "warning" as const,
        statusLabel: "被阻断",
        statusDetail: shortReason(key),
      };
    }
    if (exists) {
      return {
        state: "empty" as const,
        tone: "neutral" as const,
        statusLabel: "0 候选",
        statusDetail: "策略已计算，本日没有命中标的。",
      };
    }
    return {
      state: "pending" as const,
      tone: "warning" as const,
      statusLabel: "待返回",
      statusDetail: "接口未返回该策略候选，请查看数据边界。",
    };
  };

  const stockPayload = payload.stock_candidates;
  const hybridPayload = payload.hybrid_fusion_candidates;
  const freshTrendPayload = payload.fresh_trend_watchlist;
  const factorPayload = payload.factor_screen_candidates;
  const meanReversionPayload = payload.mean_reversion_candidates;
  const strategyCandidateCounts = {
    hybrid: hybridPayload?.candidate_count ?? 0,
    livermore: stockPayload?.candidate_count ?? 0,
    fresh_trend: freshTrendPayload?.candidate_count ?? 0,
    factor: factorPayload?.candidate_count ?? 0,
    mean_reversion: meanReversionPayload?.candidate_count ?? 0,
  };
  const meanReversionBaseStatus = outputState(
    "mean_reversion_candidates",
    strategyCandidateCounts.mean_reversion,
    Boolean(meanReversionPayload),
  );
  const meanReversionGatePaused = payload.market_gate.state !== "WARM" && !meanReversionPayload;
  const meanReversionPausedDetail =
    meanReversionGatePaused && !/暂停|门控/.test(meanReversionBaseStatus.statusDetail)
      ? `${meanReversionBaseStatus.statusDetail}；门控暂停。`
      : meanReversionBaseStatus.statusDetail;
  const meanReversionStatus = unsupportedReason("mean_reversion_candidates")
    ? {
        ...meanReversionBaseStatus,
        statusDetail: meanReversionPausedDetail,
      }
    : meanReversionGatePaused
      ? {
          state: "paused" as const,
          tone: "neutral" as const,
          statusLabel: "门控暂停",
          statusDetail: `当前市场门控为${localizeMarketDataStatus(payload.market_gate.state)}，超跌观察不触发。`,
        }
      : meanReversionBaseStatus;
  const strategyStatuses = {
    hybrid: outputState("hybrid_fusion", strategyCandidateCounts.hybrid, Boolean(hybridPayload)),
    livermore: outputState("stock_candidates", strategyCandidateCounts.livermore, Boolean(stockPayload)),
    fresh_trend: outputState("fresh_trend_watchlist", strategyCandidateCounts.fresh_trend, Boolean(freshTrendPayload)),
    factor: outputState("factor_screen_candidates", strategyCandidateCounts.factor, Boolean(factorPayload)),
    mean_reversion: meanReversionStatus,
  };
  const strategyMax = Math.max(
    1,
    strategyCandidateCounts.hybrid,
    strategyCandidateCounts.livermore,
    strategyCandidateCounts.fresh_trend,
    strategyCandidateCounts.factor,
    strategyCandidateCounts.mean_reversion,
  );
  const hybridCandidates =
    hybridPayload?.items.slice(0, 3).map((item) => ({
      key: item.stock_code,
      rankLabel: `#${item.rank}`,
      stockCode: item.stock_code,
      stockName: item.stock_name,
      sectorName: item.sector_name,
      metricLabel: `融合分 ${formatNumber(item.fusion_score, 3)}`,
    })) ?? [];
  const livermoreCandidates =
    stockPayload?.items.slice(0, 3).map((item) => ({
      key: item.stock_code,
      rankLabel: `#${item.rank}`,
      stockCode: item.stock_code,
      stockName: item.stock_name,
      sectorName: item.sector_name,
      metricLabel: `收盘强度 ${formatRatioAsPercent(item.close_strength, 0)}`,
    })) ?? [];
  const factorCandidates =
    factorPayload?.items.slice(0, 3).map((item) => ({
      key: item.stock_code,
      rankLabel: `#${item.rank}`,
      stockCode: item.stock_code,
      stockName: item.stock_name,
      sectorName: item.sector_name || item.industry,
      metricLabel: `因子分 ${formatNumber(item.score, 3)}`,
    })) ?? [];
  const freshTrendCandidates =
    freshTrendPayload?.items.slice(0, 3).map((item) => ({
      key: item.stock_code,
      rankLabel: `#${item.rank}`,
      stockCode: item.stock_code,
      stockName: item.stock_name,
      sectorName: item.sector_name,
      metricLabel: `20日动量 ${formatRatioAsPercent(item.return_20d, 1)}`,
    })) ?? [];
  const meanReversionCandidates =
    meanReversionPayload?.items.slice(0, 3).map((item) => ({
      key: item.stock_code,
      rankLabel: `#${item.rank}`,
      stockCode: item.stock_code,
      stockName: item.stock_name,
      sectorName: item.sector_name,
      metricLabel: `20日回撤 ${formatRatioAsPercent(item.drawdown_20d, 1)}`,
    })) ?? [];
  const hybridDetail = hybridPayload?.coverage_note
    ? shortStrategyCoverageLabel(hybridPayload.coverage_note, "hybrid_fusion", "周期/价格/拥挤度合成，仅观察输出")
    : hybridPayload?.observation_only
      ? "只读观察候选"
      : strategyStatuses.hybrid.statusDetail;
  const livermoreDetail = stockPayload?.selection_policy
    ? localizeStockBackendText(stockPayload.selection_policy, "stock_candidates")
    : strategyStatuses.livermore.state === "blocked"
      ? "价格趋势输入未完整落地"
      : strategyStatuses.livermore.statusDetail;
  const factorDetail = factorPayload?.coverage_note
    ? shortStrategyCoverageLabel(factorPayload.coverage_note, "factor_screen_candidates", "因子覆盖已返回")
    : strategyStatuses.factor.statusDetail;
  const freshTrendDetail = freshTrendPayload?.observation_only
    ? "只读观察池，补充过热门控下的新趋势复核。"
    : strategyStatuses.fresh_trend.statusDetail;
  const meanReversionDetail =
    strategyStatuses.mean_reversion.state === "blocked"
      ? strategyStatuses.mean_reversion.statusDetail
      : meanReversionMarketActiveLabel(payload.market_gate.state, strategyCandidateCounts.mean_reversion) ||
        strategyStatuses.mean_reversion.statusDetail;

  return [
    {
      key: "hybrid",
      label: "融合策略",
      subtitle: "多策略合成",
      value: String(strategyCandidateCounts.hybrid),
      unitLabel: "候选",
      detail: hybridDetail,
      tone: strategyStatuses.hybrid.tone,
      state: strategyStatuses.hybrid.state,
      statusLabel: strategyStatuses.hybrid.statusLabel,
      statusDetail: strategyStatuses.hybrid.statusDetail,
      blockerLabel: strategyBlockerLabel(strategyStatuses.hybrid.state, strategyStatuses.hybrid.statusDetail),
      focusLabel: strategyFocusLabel({
        label: "融合策略",
        state: strategyStatuses.hybrid.state,
        candidates: hybridCandidates,
        fallback: "复核周期、趋势、拥挤度证据是否同向。",
      }),
      actionLabel: "查看复核队列",
      candidateCountLabel: strategyCandidateCountLabel(strategyCandidateCounts.hybrid),
      dateLabel: hybridPayload?.as_of_date ?? payload.as_of_date ?? "日期待补",
      formulaLabel: hybridPayload?.formula_version ?? "公式待补",
      evidence: [
        { key: "gate", label: "门控", value: localizeMarketDataStatus(hybridPayload?.market_state ?? payload.market_gate.state) },
        { key: "mode", label: "口径", value: hybridPayload?.observation_only ? "只读观察" : "复核候选" },
        { key: "count", label: "候选", value: hybridPayload ? `${hybridPayload.candidate_count} 只` : "待补" },
      ],
      candidates: hybridCandidates,
      scrollTarget: "stock-analysis-review-queue",
      progress: clampRatio(strategyCandidateCounts.hybrid / strategyMax),
    },
    {
      key: "livermore",
      label: "趋势突破",
      subtitle: "价格趋势",
      value: String(strategyCandidateCounts.livermore),
      unitLabel: "候选",
      detail: livermoreDetail,
      tone: strategyStatuses.livermore.tone,
      state: strategyStatuses.livermore.state,
      statusLabel: strategyStatuses.livermore.statusLabel,
      statusDetail: strategyStatuses.livermore.statusDetail,
      blockerLabel: strategyBlockerLabel(strategyStatuses.livermore.state, strategyStatuses.livermore.statusDetail),
      focusLabel: strategyFocusLabel({
        label: "趋势突破",
        state: strategyStatuses.livermore.state,
        candidates: livermoreCandidates,
        fallback: "复核均线结构、观察位与行业强度是否一致。",
      }),
      actionLabel: "查看复核队列",
      candidateCountLabel: strategyCandidateCountLabel(strategyCandidateCounts.livermore),
      dateLabel: stockPayload?.as_of_date ?? payload.as_of_date ?? "日期待补",
      formulaLabel: stockPayload?.formula_version ?? "公式待补",
      evidence: [
        { key: "input", label: "输入", value: stockPayload ? `${stockPayload.input_stock_count} 只` : "待补" },
        { key: "excluded", label: "剔除", value: stockPayload ? `${stockPayload.excluded_stock_count} 只` : "待补" },
        { key: "history", label: "历史不足", value: stockPayload ? `${stockPayload.insufficient_history_count} 只` : "待补" },
      ],
      candidates: livermoreCandidates,
      scrollTarget: "stock-analysis-review-queue",
      progress: clampRatio(strategyCandidateCounts.livermore / strategyMax),
    },
    {
      key: "fresh_trend",
      label: "新趋势观察",
      subtitle: "成长观察",
      value: String(strategyCandidateCounts.fresh_trend),
      unitLabel: "候选",
      detail: freshTrendDetail,
      tone: strategyStatuses.fresh_trend.tone,
      state: strategyStatuses.fresh_trend.state,
      statusLabel: strategyStatuses.fresh_trend.statusLabel,
      statusDetail: strategyStatuses.fresh_trend.statusDetail,
      blockerLabel: strategyBlockerLabel(strategyStatuses.fresh_trend.state, strategyStatuses.fresh_trend.statusDetail),
      focusLabel: strategyFocusLabel({
        label: "新趋势观察",
        state: strategyStatuses.fresh_trend.state,
        candidates: freshTrendCandidates,
        fallback: "复核成长板、均线结构、量能和题材线索是否同向。",
      }),
      actionLabel: "查看观察池",
      candidateCountLabel: strategyCandidateCountLabel(strategyCandidateCounts.fresh_trend),
      dateLabel: freshTrendPayload?.as_of_date ?? payload.as_of_date ?? "日期待补",
      formulaLabel: freshTrendPayload?.formula_version ?? "公式待补",
      evidence: [
        { key: "input", label: "输入", value: freshTrendPayload ? `${freshTrendPayload.input_stock_count} 只` : "待补" },
        { key: "gate", label: "门控", value: localizeMarketDataStatus(freshTrendPayload?.market_state ?? payload.market_gate.state) },
        { key: "mode", label: "口径", value: freshTrendPayload?.observation_only ? "只读观察" : "复核候选" },
      ],
      candidates: freshTrendCandidates,
      scrollTarget: "stock-analysis-review-queue",
      progress: clampRatio(strategyCandidateCounts.fresh_trend / strategyMax),
    },
    {
      key: "factor",
      label: "多因子",
      subtitle: "价值质量动量",
      value: String(strategyCandidateCounts.factor),
      unitLabel: "候选",
      detail: factorDetail,
      tone: strategyStatuses.factor.tone,
      state: strategyStatuses.factor.state,
      statusLabel: strategyStatuses.factor.statusLabel,
      statusDetail: strategyStatuses.factor.statusDetail,
      blockerLabel: strategyBlockerLabel(strategyStatuses.factor.state, strategyStatuses.factor.statusDetail),
      focusLabel: strategyFocusLabel({
        label: "多因子",
        state: strategyStatuses.factor.state,
        candidates: factorCandidates,
        fallback: "复核因子覆盖、估值质量与动量分位。",
      }),
      actionLabel: "查看观察池",
      candidateCountLabel: strategyCandidateCountLabel(strategyCandidateCounts.factor),
      dateLabel: factorPayload?.factor_snapshot_as_of_date ?? factorPayload?.as_of_date ?? payload.as_of_date ?? "日期待补",
      formulaLabel: factorPayload?.formula_version ?? "公式待补",
      evidence: [
        { key: "input", label: "输入", value: factorPayload ? `${factorPayload.input_stock_count} 只` : "待补" },
        { key: "gate", label: "门控", value: localizeMarketDataStatus(factorPayload?.market_state ?? payload.market_gate.state) },
        { key: "mode", label: "口径", value: factorPayload?.observation_only ? "只读观察" : "复核候选" },
      ],
      candidates: factorCandidates,
      scrollTarget: "stock-analysis-observation-preview",
      progress: clampRatio(strategyCandidateCounts.factor / strategyMax),
    },
    {
      key: "mean_reversion",
      label: "超跌反弹",
      subtitle: "回撤修复",
      value: String(strategyCandidateCounts.mean_reversion),
      unitLabel: "候选",
      detail: meanReversionDetail,
      tone: strategyStatuses.mean_reversion.tone,
      state: strategyStatuses.mean_reversion.state,
      statusLabel: strategyStatuses.mean_reversion.statusLabel,
      statusDetail: strategyStatuses.mean_reversion.statusDetail,
      blockerLabel: strategyBlockerLabel(
        strategyStatuses.mean_reversion.state,
        strategyStatuses.mean_reversion.statusDetail,
      ),
      focusLabel: strategyFocusLabel({
        label: "超跌反弹",
        state: strategyStatuses.mean_reversion.state,
        candidates: meanReversionCandidates,
        fallback: "复核回撤深度、均线距离与市场门控。",
      }),
      actionLabel: "查看观察池",
      candidateCountLabel: strategyCandidateCountLabel(strategyCandidateCounts.mean_reversion),
      dateLabel: meanReversionPayload?.as_of_date ?? payload.as_of_date ?? "日期待补",
      formulaLabel: meanReversionPayload?.formula_version ?? "公式待补",
      evidence: [
        { key: "input", label: "输入", value: meanReversionPayload ? `${meanReversionPayload.input_stock_count} 只` : "待补" },
        { key: "gate", label: "门控", value: localizeMarketDataStatus(meanReversionPayload?.market_state ?? payload.market_gate.state) },
        { key: "history", label: "历史不足", value: meanReversionPayload ? `${meanReversionPayload.insufficient_history_count} 只` : "待补" },
      ],
      candidates: meanReversionCandidates,
      scrollTarget: "stock-analysis-observation-preview",
      progress: clampRatio(strategyCandidateCounts.mean_reversion / strategyMax),
    },
  ];
}

export function buildStockAnalysisEvidenceStatus(
  payload: LivermoreStrategyPayload,
  meta: StockViewModelMeta = {},
): StockAnalysisEvidenceStatusItem[] {
  const boundarySummary = buildDataBoundarySummary(payload, meta);
  const quality = meta.quality_flag ?? "pending";
  const vendor = meta.vendor_status ?? "pending";
  const fallback = meta.fallback_mode ?? "none";
  const qualityTone = isMetaBoundary(meta) ? "warning" : "positive";
  const lineageReady = Boolean(meta.source_version);
  const ruleReady = Boolean(meta.rule_version);
  const basisLabel = localizeBasisLabel(payload.basis);

  return [
    {
      key: "as-of-date",
      label: "数据日期",
      statusLabel: payload.as_of_date ?? "日期待补",
      tone: payload.as_of_date ? "positive" : "warning",
      detail: payload.requested_as_of_date ? `请求日期 ${payload.requested_as_of_date}` : "使用最新可用交易日",
    },
    {
      key: "lineage",
      label: "来源状态",
      statusLabel: lineageReady ? "可追踪" : "待确认",
      tone: lineageReady ? "positive" : "warning",
      detail: lineageReady ? "完整追踪见诊断" : "来源追踪待确认",
    },
    {
      key: "basis",
      label: "计算口径",
      statusLabel: basisLabel,
      tone: evidenceToneForStatus(payload.basis ?? "pending"),
      detail: basisLabel,
    },
    {
      key: "rule-version",
      label: "规则版本",
      statusLabel: ruleReady ? "规则已加载" : "规则待确认",
      tone: ruleReady ? "positive" : "warning",
      detail: `可用 ${payload.supported_outputs.length} / 阻断 ${payload.unsupported_outputs.length}`,
    },
    {
      key: "quality",
      label: "数据质量",
      statusLabel: qualityTone === "positive" ? "正常" : "需复核",
      tone: qualityTone,
      detail: stockEvidenceBusinessQualityLabel(quality, vendor, fallback),
    },
    {
      key: "exceptions",
      label: "例外状态",
      statusLabel: boundarySummary.boundaryCount > 0 ? `${boundarySummary.boundaryCount} 条边界` : "无边界",
      tone: boundarySummary.boundaryCount > 0 ? "warning" : "positive",
      detail: boundarySummary.detailLabel,
    },
  ];
}

function compactEndpointTrace(value: string | null | undefined): string {
  const trace = value?.trim();
  if (!trace) return "链路待补";
  if (trace.length <= 28) return `链路：${trace}`;
  return `链路：${trace.slice(0, 10)}...${trace.slice(-8)}`;
}

function stockEvidenceBusinessQualityLabel(
  quality: string | null | undefined,
  vendor: string | null | undefined,
  fallback: string | null | undefined,
): string {
  if (quality === "error" || vendor === "vendor_unavailable") return "不可用";
  if (fallback && fallback !== "none") return "数据延迟";
  if (quality === "stale" || vendor === "vendor_stale") return "数据延迟";
  if (quality === "ok" && vendor === "ok") return "数据正常";
  return "部分缺失";
}

function normalizeEndpointCount(value: number | null | undefined): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return Math.max(0, Math.trunc(value));
}

function firstNonEmptyText(...values: Array<string | null | undefined>): string | null {
  for (const value of values) {
    const normalized = value?.trim();
    if (normalized) return normalized;
  }
  return null;
}

function endpointDateLabel(input: StockEndpointEvidenceInput): string {
  const asOfDate = firstNonEmptyText(
    input.asOfDate,
    input.meta?.as_of_date,
    input.meta?.resolved_report_date,
  );
  if (asOfDate) return `日期：${asOfDate}`;

  const snapshotFrom = firstNonEmptyText(input.snapshotFrom, input.meta?.requested_report_date);
  const snapshotTo = firstNonEmptyText(input.snapshotTo, input.meta?.resolved_report_date);
  if (snapshotFrom && snapshotTo) return `窗口：${snapshotFrom} 至 ${snapshotTo}`;
  if (snapshotTo) return `截至：${snapshotTo}`;
  if (snapshotFrom) return `起始：${snapshotFrom}`;
  return "日期待补";
}

function endpointIssueLabel(input: StockEndpointEvidenceInput): string {
  const warningCount = normalizeEndpointCount(input.warningCount);
  const unsupportedCount = normalizeEndpointCount(input.unsupportedCount);
  const missingInputCount = normalizeEndpointCount(input.missingInputCount);
  const counts = [warningCount, unsupportedCount, missingInputCount].filter(
    (value): value is number => value !== null,
  );
  if (counts.length === 0) return "提示待补";
  const parts: string[] = [];
  if ((warningCount ?? 0) > 0) parts.push(`提示 ${warningCount}`);
  if ((unsupportedCount ?? 0) > 0) parts.push(`阻断 ${unsupportedCount}`);
  if ((missingInputCount ?? 0) > 0) parts.push(`缺输入 ${missingInputCount}`);
  return parts.length > 0 ? parts.join(" / ") : "无新增提示";
}

function endpointIssueCount(input: StockEndpointEvidenceInput): number {
  return (
    (normalizeEndpointCount(input.warningCount) ?? 0) +
    (normalizeEndpointCount(input.unsupportedCount) ?? 0) +
    (normalizeEndpointCount(input.missingInputCount) ?? 0)
  );
}

function endpointMetaNeedsReview(meta: StockEndpointEvidenceMeta): boolean {
  const quality = meta.quality_flag ?? "pending";
  const vendor = meta.vendor_status ?? "pending";
  const fallback = meta.fallback_mode ?? "pending";
  return quality !== "ok" || vendor !== "ok" || fallback !== "none";
}

function endpointMetaLabel(meta: StockEndpointEvidenceMeta | null | undefined): string {
  if (!meta) return "证据待补";
  const quality = meta.quality_flag ?? "pending";
  const vendor = meta.vendor_status ?? "pending";
  const fallback = meta.fallback_mode ?? "pending";
  return stockEvidenceBusinessQualityLabel(quality, vendor, fallback);
}

export function buildStockEndpointEvidenceItems(
  inputs: StockEndpointEvidenceInput[],
): StockEndpointEvidenceItem[] {
  return inputs.map((input) => {
    const base = {
      key: input.key,
      label: input.label,
      dateLabel: endpointDateLabel(input),
      traceLabel: compactEndpointTrace(input.meta?.trace_id),
      issueLabel: endpointIssueLabel(input),
      metaLabel: endpointMetaLabel(input.meta),
    };

    if (input.queryState === "loading") {
      return {
        ...base,
        statusLabel: "读取中",
        tone: "neutral",
        detail: "正在读取证据链，暂不纳入复核判断",
      };
    }

    if (input.queryState === "error") {
      return {
        ...base,
        statusLabel: "读取失败",
        tone: "negative",
        detail: "证据读取失败，当前结论不使用该扩展证据",
      };
    }

    if (input.queryState === "idle") {
      return {
        ...base,
        statusLabel: "待触发",
        tone: "neutral",
        detail: "证据链尚未触发，展开相关复核区后读取",
      };
    }

    if (!input.meta) {
      return {
        ...base,
        statusLabel: "证据待补",
        tone: "warning",
        detail: "证据已返回，但质量状态待补",
      };
    }

    const needsReview = endpointMetaNeedsReview(input.meta) || endpointIssueCount(input) > 0;
    return {
      ...base,
      statusLabel: needsReview ? "需复核" : "接通",
      tone: needsReview ? "warning" : "positive",
      detail: needsReview ? "证据已返回，业务提示需复核" : "证据链已返回，质量可核验",
    };
  });
}

function closureReasonTone(kind: StockObservationClosureReasonKind): StockClosedLoopTone {
  if (kind === "query-error") return "negative";
  if (kind === "no-data" || kind === "meta-missing") return "neutral";
  return "warning";
}

function closureActionText(reason: StockObservationClosureReason): string {
  const source = reason.endpointLabel;
  switch (reason.kind) {
    case "query-error":
      return `修复${source}证据读取失败`;
    case "meta-missing":
      return `补齐${source}证据状态`;
    case "fallback":
      return `核对${source}回退状态与供数状态`;
    case "warning":
      return `复核${source}服务端 warning`;
    case "unsupported":
      return `确认${source}支持边界`;
    case "missing-input":
      return `补${source}完整策略输入证据`;
    case "data-gap":
      return `补${source}数据缺口证据`;
    case "diagnostic":
      return `复核${source}诊断项`;
    case "no-data":
      return `确认${source}无记录状态`;
    default:
      return `复核${source}证据`;
  }
}

function endpointLoaded(item: StockEndpointEvidenceItem): boolean {
  return !["待读取", "待读取中", "待触发", "读取中", "读取失败"].includes(item.statusLabel);
}

export function buildObservationClosureSummary({
  endpointItems,
  reasonInputs = [],
  formalUseAllowed = false,
  approvalStatus = "gap_or_observational",
}: {
  endpointItems: StockEndpointEvidenceItem[];
  reasonInputs?: StockObservationClosureReasonInput[];
  formalUseAllowed?: boolean | null;
  approvalStatus?: string | null;
}): StockObservationClosureSummary {
  const endpointReasons: StockObservationClosureReasonInput[] = endpointItems.flatMap((item): StockObservationClosureReasonInput[] => {
    if (item.statusLabel === "读取失败") {
      return [
        {
          endpointId: item.key,
          endpointLabel: item.label,
          kind: "query-error",
          fieldPath: `${item.key}.queryState`,
          displayText: `${item.label}读取失败`,
        },
      ];
    }
    if (item.statusLabel === "证据待补") {
      return [
        {
          endpointId: item.key,
          endpointLabel: item.label,
          kind: "meta-missing",
          fieldPath: `${item.key}.result_meta`,
          displayText: `${item.label}证据状态待补`,
        },
      ];
    }
    return [];
  });
  const seen = new Set<string>();
  const unresolvedReasons = [...endpointReasons, ...reasonInputs].flatMap((input, index) => {
    const key = input.key ?? `${input.endpointId}:${input.kind}:${input.fieldPath}:${index}`;
    if (seen.has(key)) return [];
    seen.add(key);
    return [
      {
        ...input,
        key,
        tone: closureReasonTone(input.kind),
      },
    ];
  });
  const endpointLoadedCount = endpointItems.filter(endpointLoaded).length;
  const endpointErrorCount = endpointItems.filter((item) => item.statusLabel === "读取失败").length;
  const metaMissingCount = endpointItems.filter((item) => item.statusLabel === "证据待补").length;
  const formalUse = formalUseAllowed === true;
  const approval = approvalStatus?.trim() || "gap_or_observational";
  const nextEvidenceActions = unresolvedReasons.slice(0, 6).map((reason) => ({
    key: `action:${reason.key}`,
    source: reason.endpointLabel,
    actionText: closureActionText(reason),
    fieldPath: reason.fieldPath,
  }));
  const tone: StockClosedLoopTone =
    endpointErrorCount > 0 ? "negative" : unresolvedReasons.length > 0 || !formalUse ? "warning" : "positive";

  return {
    formalUseAllowed: formalUse,
    approvalStatus: approval,
    approvalLabel: approval === "gap_or_observational" ? "观测缺口页" : approval,
    endpointTotal: endpointItems.length,
    endpointLoadedCount,
    endpointErrorCount,
    metaMissingCount,
    unresolvedReasons,
    nextEvidenceActions,
    headline: `证据读取覆盖 ${endpointLoadedCount}/${endpointItems.length}`,
    detail: formalUse
      ? `治理状态：${approval}`
      : `正式用途：否 · 治理状态：${approval} · 待复核项 ${unresolvedReasons.length}`,
    tone,
  };
}

export function buildStockAnalysisEventMonitorRows(
  payload: LivermoreStrategyPayload,
  confluence: LivermoreSignalConfluencePayload | null,
): StockAnalysisEventMonitorRow[] {
  const rows: StockAnalysisEventMonitorRow[] = [];

  for (const item of payload.diagnostics) {
    rows.push({
      key: `diagnostic:${item.code}`,
      source: "diagnostic",
      level: eventLevelFromSeverity(item.severity),
      event: item.code,
      impact: item.input_family ?? "strategy",
      detail: localizeStockBackendText(item.message, item.input_family),
    });
  }

  for (const gap of payload.data_gaps.filter((item) => item.status !== "ready")) {
    rows.push({
      key: `data_gap:${gap.input_family}:${gap.status}`,
      source: "data_gap",
      level: gap.status === "stale" ? "warning" : "error",
      event: localizeDataGapStatus(gap.status),
      impact: localizeStockDataFamily(gap.input_family),
      detail: localizeStockBackendText(gap.evidence, gap.input_family),
    });
  }

  for (const item of payload.unsupported_outputs) {
    rows.push({
      key: `unsupported:${item.key}`,
      source: "unsupported",
      level: isActionableLivermoreUnsupportedOutput(item) ? "warning" : "info",
      event: `${localizeStockDataFamily(item.key)}阻断`,
      impact: item.key,
      detail: localizeStockBackendText(item.reason, item.key),
    });
  }

  for (const item of confluence?.diagnostics ?? []) {
    const row =
      typeof item === "string"
        ? { severity: "warning", code: item, message: item }
        : {
            severity: item.severity ?? "warning",
            code: item.code ?? item.message ?? "signal_confluence",
            message: item.message ?? item.code ?? "Signal confluence diagnostic pending detail.",
          };
    rows.push({
      key: `signal_confluence:${row.code}`,
      source: "signal_confluence",
      level: eventLevelFromSeverity(row.severity),
      event: row.code,
      impact: "signal_confluence",
      detail: localizeStockBackendText(row.message, "signal_confluence"),
    });
  }

  for (const row of buildRiskExitRows(payload, confluence).filter((item) => item.status === "triggered")) {
    rows.push({
      key: `risk_exit:${row.stockCode}`,
      source: "risk_exit",
      level: eventToneLevel("negative"),
      event: `${row.stockCode} ${row.stockName}`,
      impact: "risk_exit",
      detail: detailFromEventEvidence(row.reason, "风险退出观察触发复核"),
    });
  }

  return rows;
}

export function buildSectorFilterSummary(
  payload: LivermoreStrategyPayload,
  sectorFilterSectorCode: string | null,
): StockSectorFilterSummary {
  const queue = buildCandidateReviewQueue(payload);
  const totalCount = queue.length;
  if (!sectorFilterSectorCode) {
    return {
      sectorCode: null,
      sectorLabel: "全部行业",
      isFiltered: false,
      visibleCount: totalCount,
      totalCount,
      summaryLabel: `行业 全部 / 显示 ${totalCount} / ${totalCount} 个候选`,
    };
  }

  const sectorName =
    queue.find((item) => item.sectorCode === sectorFilterSectorCode)?.sectorName ??
    payload.sector_rank?.items?.find((item) => item.sector_code === sectorFilterSectorCode)?.sector_name ??
    sectorFilterSectorCode;
  const visibleCount = queue.filter((item) => item.sectorCode === sectorFilterSectorCode).length;

  return {
    sectorCode: sectorFilterSectorCode,
    sectorLabel: sectorName,
    isFiltered: true,
    visibleCount,
    totalCount,
    summaryLabel: `行业 ${sectorName} (${sectorFilterSectorCode}) / 显示 ${visibleCount} / ${totalCount} 个候选`,
  };
}

export function buildReviewQueueSectorFilterView({
  reviewQueue,
  sectorFilterSectorCode,
  selectedSectorLabel,
}: {
  reviewQueue: StockCandidateReviewQueueItem[];
  sectorFilterSectorCode: string | null;
  selectedSectorLabel?: string | null;
}): StockReviewQueueSectorFilterView {
  const sectorMap = new Map<string, string>();
  for (const card of reviewQueue) {
    sectorMap.set(card.sectorCode, card.sectorName || card.sectorCode);
  }
  const sectorOptions: [string, string][] = [...sectorMap.entries()].sort(([a], [b]) =>
    a.localeCompare(b, "zh-Hans-CN"),
  );
  const filteredCandidates = sectorFilterSectorCode
    ? reviewQueue.filter((candidate) => candidate.sectorCode === sectorFilterSectorCode)
    : reviewQueue;
  const selectedSectorLeadCandidate = filteredCandidates[0] ?? null;
  const sectorLabel = selectedSectorLabel ?? sectorFilterSectorCode;
  const sectorLinkTone = sectorFilterSectorCode
    ? filteredCandidates.length > 0
      ? "active"
      : "empty"
    : "all";
  const sectorLinkSummary = sectorFilterSectorCode
    ? filteredCandidates.length > 0
      ? `${sectorLabel} · ${filteredCandidates.length} 个候选`
      : `${sectorLabel} · 无候选`
    : `全部行业 · ${reviewQueue.length} 个候选`;
  const sectorLinkFocus = selectedSectorLeadCandidate
    ? `首位 ${selectedSectorLeadCandidate.stockName} · 距观察 ${selectedSectorLeadCandidate.distanceToBreakoutPct}`
    : sectorFilterSectorCode
      ? "该行业暂无线索"
      : "按板块收敛";

  return {
    sectorOptions,
    filteredCandidates,
    selectedSectorLeadCandidate,
    sectorLinkTone,
    sectorLinkSummary,
    sectorLinkFocus,
  };
}

export function buildCandidateReviewQueue(
  payload: LivermoreStrategyPayload,
): StockCandidateReviewQueueItem[] {
  return buildCandidateEvidenceCards(payload).map((card) => ({
    rank: card.rank,
    stockCode: card.stockCode,
    stockName: card.stockName,
    sectorCode: card.sectorCode,
    sectorName: card.sectorName,
    headline: card.headline,
    pattern: card.pattern,
    patternNote: card.patternNote,
    distanceToBreakoutPct: card.distanceToBreakoutPct,
    reviewFocus: `${card.stockName} · ${card.sectorName} · 距观察位 ${card.distanceToBreakoutPct}`,
    primaryEvidence: card.evidenceBullets.slice(0, 3),
    supportingEvidence: card.evidenceBullets.slice(3),
    boundaryEvidence: card.counterEvidence,
    invalidationFocus: card.invalidationRules[0] ?? "失效条件待补。",
    invalidationRules: card.invalidationRules,
    rawFields: card.rawFields,
  }));
}

function localizeThemeName(name: string | null | undefined): string {
  const value = name?.trim();
  if (!value) return "题材待补";
  const withoutTechnicalSuffix = value
    .replace(/\bproxy\b/gi, "")
    .replace(/\breview\b/gi, "")
    .replace(/\s{2,}/g, " ")
    .trim();
  const labels: Record<string, string> = {
    semiconductor: "半导体",
    electronic: "电子",
  };
  const normalized = withoutTechnicalSuffix.toLowerCase();
  return labels[normalized] ?? (withoutTechnicalSuffix || "题材待补");
}

function localizeThemeText(text: string | null | undefined): string {
  const value = text?.trim();
  if (!value) return "原因待补";
  const lower = value.toLowerCase();
  if (lower.includes("near-miss") && lower.includes("failed gates")) return "强势样本未过门槛，保留观察。";
  if (lower.includes("observation-only") && lower.includes("leaders")) return "强势样本进入观察。";
  if (lower.includes("review-only") && lower.includes("below gate")) return "强势样本未达门槛，保留复核。";
  return value.replace(/\bproxy\b/gi, "代理观察").replace(/_/g, " ");
}

function localizeThemeGateLabel(gate: string): string {
  const labels: Record<string, string> = {
    insufficient_cluster_strength: "簇强度不足",
  };
  return labels[gate] ?? "门槛待确认";
}

export function buildThemeBreakoutCards(payload: LivermoreStrategyPayload): StockThemeBreakoutCard[] {
  const isProxy = payload.theme_breakout?.is_proxy ?? true;
  return sortedThemeBreakoutItems(payload).map((item) => {
    const leaders = [...item.items]
      .sort((left, right) => {
        if (left.closed_up_limit !== right.closed_up_limit) {
          return left.closed_up_limit ? -1 : 1;
        }
        if (right.pctchange !== left.pctchange) return right.pctchange - left.pctchange;
        return right.turn - left.turn;
      })
      .slice(0, 5)
      .map((stock) => ({
        stockCode: stock.stock_code,
        stockName: stock.stock_name,
        pctChange: formatPercent(stock.pctchange),
        turn: formatNumber(stock.turn, 2),
        closeStrength: formatRatioAsPercent(stock.close_strength, 0),
        tags: [
          stock.closed_up_limit ? "涨停" : null,
          stock.strong ? "强势" : null,
        ].filter((tag): tag is string => Boolean(tag)),
      }));

    const boundaryLabel = isProxy
      ? "代理题材观察：由日线、股票名称和申万一级行业拼接，不是概念库或盘中异动源。"
      : "真实题材观察：使用已落地概念成分和异动事件；仍只作复核观察。";
    const movementCount = item.movement_event_count ?? 0;
    const latestEventTitle = item.latest_event_title?.trim() || "暂无最新异动标题";
    const latestEventTime = item.latest_event_time?.trim() || "时间待补";

    return {
      rank: item.rank,
      themeKey: item.theme_key,
      themeName: localizeThemeName(item.theme_name),
      parentSectorLabel: `${localizeThemeName(item.parent_sector_name)} #${item.parent_sector_rank}`,
      summary: `${item.member_count} 只观察股，${item.strong_stock_count} 只强势，${item.limit_stock_count} 只涨停。`,
      reason: localizeThemeText(item.reason),
      boundaryLabel,
      strongCountLabel: `强势 ${item.strong_stock_count}`,
      limitCountLabel: `涨停 ${item.limit_stock_count}`,
      advanceRatioLabel: `上涨占比 ${formatRatioAsPercent(item.advance_ratio, 0)}`,
      avgPctChangeLabel: `均涨跌 ${formatPercent(item.avg_pctchange)}`,
      movementLabel: `异动 ${movementCount}`,
      latestEventLabel: movementCount > 0 ? `${latestEventTime} / ${latestEventTitle}` : "异动事件待补",
      leaders,
    };
  });
}

const themeEvidenceInputLabels: Record<string, string> = {
  choice_stock_intraday_movement_event: "盘中异动",
  concept_membership: "概念成分",
  intraday_movement: "盘中异动",
};

const themeEvidenceStatusLabels: Record<string, string> = {
  catalog_unconfirmed: "目录待确认",
  table_missing: "数据源缺失",
  source_table_missing: "数据源缺失",
  landed_no_rows: "已接入无行",
  matched_rows: "已匹配",
};

function localizeThemeEvidenceDetail(row: LivermoreThemeEvidenceInputState, inputFamily: string, status: string): string {
  const label = themeEvidenceInputLabels[inputFamily] ?? "题材输入";
  const statusLabel = themeEvidenceStatusLabels[status] ?? "状态待确认";
  const message = row.message?.trim().toLowerCase() ?? "";
  if (message.includes("concept membership") || status === "catalog_unconfirmed") {
    return `${label}：${statusLabel}`;
  }
  if (message.includes("intraday movement") || status === "table_missing") {
    return `${label}：${statusLabel}`;
  }
  return `${label}：${statusLabel}`;
}

function themeEvidenceInputs(payload: LivermoreStrategyPayload): LivermoreThemeEvidenceInputState[] {
  const state = payload.theme_breakout?.evidence_state;
  if (state == null) return [];

  const rows: LivermoreThemeEvidenceInputState[] = [];
  if (state.concept_membership != null) {
    rows.push({
      ...state.concept_membership,
      input_family: state.concept_membership.input_family || "concept_membership",
    });
  }
  if (state.intraday_movement != null) {
    rows.push({
      ...state.intraday_movement,
      input_family: state.intraday_movement.input_family || "intraday_movement",
    });
  }

  const seen = new Set(rows.map((row) => row.input_family));
  for (const row of state.inputs ?? []) {
    const inputFamily = row.input_family ?? "theme_input";
    if (!seen.has(inputFamily)) {
      rows.push(row);
      seen.add(inputFamily);
    }
  }
  return rows;
}

export function buildThemeEvidenceStateRows(payload: LivermoreStrategyPayload): StockThemeEvidenceStateRow[] {
  return themeEvidenceInputs(payload).map((row, index) => {
    const inputFamily = row.input_family ?? `theme_input_${index + 1}`;
    const rowCount = finiteCount(row.row_count ?? row.date_row_count);
    const matchedCount = finiteCount(row.matched_row_count);
    const status = String(row.status ?? row.state ?? "unknown");
    return {
      key: inputFamily,
      label: themeEvidenceInputLabels[inputFamily] ?? "题材输入",
      status,
      statusLabel: themeEvidenceStatusLabels[status] ?? "状态待确认",
      detail: localizeThemeEvidenceDetail(row, inputFamily, status),
      rowCountLabel: `行 ${rowCount} / 命中 ${matchedCount}`,
    };
  });
}

function themeReviewLeaders(item: LivermoreThemeBreakoutReviewItem): StockThemeBreakoutLeader[] {
  return [...(item.items ?? [])]
    .sort((left, right) => {
      if (left.closed_up_limit !== right.closed_up_limit) {
        return left.closed_up_limit ? -1 : 1;
      }
      if (right.pctchange !== left.pctchange) return right.pctchange - left.pctchange;
      return right.turn - left.turn;
    })
    .slice(0, 5)
    .map((stock) => ({
      stockCode: stock.stock_code,
      stockName: stock.stock_name,
      pctChange: formatPercent(stock.pctchange),
      turn: formatNumber(stock.turn, 2),
      closeStrength: formatRatioAsPercent(stock.close_strength, 0),
      tags: [
        stock.closed_up_limit ? "涨停" : null,
        stock.strong ? "强势" : null,
      ].filter((tag): tag is string => Boolean(tag)),
    }));
}

export function buildThemeBreakoutReviewItems(payload: LivermoreStrategyPayload): StockThemeBreakoutReviewItem[] {
  return [...(payload.theme_breakout?.review_items ?? [])]
    .sort((left, right) => (left.rank ?? 9999) - (right.rank ?? 9999))
    .map((item, index) => {
      const failedGates = item.failed_gates ?? item.failed_gate_codes ?? [];
      return {
        rank: item.rank ?? index + 1,
        themeKey: item.theme_key,
        themeName: localizeThemeName(item.theme_name),
        sourceKindLabel: localizeThemeSourceKind(
          item.source_kind,
          payload.theme_breakout?.is_proxy ?? true,
        ),
        parentSectorLabel: `${localizeThemeName(item.parent_sector_name)} #${item.parent_sector_rank}`,
        summary: `${item.member_count} 只复核样本，${item.strong_stock_count} 只强势，${
          item.limit_stock_count
        } 只涨停，均涨跌 ${formatPercent(item.avg_pctchange)}`,
        failedGateLabel:
          failedGates.length > 0 ? `未过门槛：${failedGates.map(localizeThemeGateLabel).join("、")}` : "门槛待确认",
        reason: localizeThemeText(item.reason),
        leaders: themeReviewLeaders(item),
      };
    });
}

export function buildDecisionSummary(
  payload: LivermoreStrategyPayload,
  meta: Partial<{
    quality_flag: string;
    vendor_status: string;
    fallback_mode: string;
  }> = {},
): StockDecisionSummary {
  const strip = buildDailyJudgmentStrip(payload);
  const queue = buildCandidateReviewQueue(payload);
  const firstReview = queue[0];
  const qualityFlag = meta.quality_flag ?? "待补";
  const vendorStatus = meta.vendor_status ?? "待补";
  const fallbackMode = meta.fallback_mode ?? "none";
  const isFallback = fallbackMode !== "none";
  const fallbackLabel = isFallback ? ` / ${localizeFallbackMode(fallbackMode)}` : "";
  const dataFreshnessOk = qualityFlag === "ok" && vendorStatus === "ok" && !isFallback;
  const candidateCount = queue.length;
  const boundaryCount = countBoundaryItems(payload);

  return {
    headline: strip.headline,
    gateLabel: strip.gateChip,
    exposureLabel: `观察暴露 ${formatRatioAsPercent(payload.market_gate.exposure)}`,
    strongestSectorLabel: strip.strongestSectorChip,
    weakestSectorLabel: strip.weakestSectorChip,
    candidateCountLabel: `候选 ${candidateCount}`,
    dataFreshnessLabel: `${dataFreshnessOk ? "数据正常" : "数据需复核"} ${localizeMetaQualityFlag(
      qualityFlag,
    )} / ${localizeMetaVendorStatus(vendorStatus)}${fallbackLabel}`,
    boundaryLabel: boundaryCount > 0 ? `${boundaryCount} 条边界` : "边界清晰",
    nextReviewAction: firstReview
      ? `下一步：先复核 ${firstReview.stockName}（${firstReview.stockCode}），${firstReview.sectorName}，距观察位 ${firstReview.distanceToBreakoutPct}。`
      : buildReviewQueueEmptyState(payload).detail,
    basisLabel: localizeBasisLabel(payload.basis),
    asOfLabel: payload.as_of_date ?? "日期待补",
  };
}

/** @deprecated Stage 1.5 — 已由 inline meta + Drawer 替代正文列表；保留给需要纯文本的诊断导出 */
export function buildDataBoundaryNotes(payload: LivermoreStrategyPayload): string[] {
  const notes = [`口径：${localizeBasisLabel(payload.basis)}`, `策略：${payload.strategy_name || "待补"}`];
  for (const diag of payload.diagnostics) {
    const severityLabel = diag.severity === "error" ? "错误" : diag.severity === "warning" ? "预警" : "信息";
    notes.push(
      `${severityLabel} ${localizeDiagnosticScope(diag.input_family)}：${localizeStockBackendText(
        diag.message,
        diag.input_family,
      )}`,
    );
  }
  if (payload.as_of_date) {
    notes.push(`数据日期：${payload.as_of_date}`);
  }
  if (payload.sector_rank?.formula_version) {
    notes.push(`板块强弱公式：${payload.sector_rank.formula_version}`);
    notes.push(`板块强弱规则状态：${sectorRankFormulaGovernanceLabel(payload.sector_rank)}`);
    if (payload.sector_rank.formula_note) {
      notes.push(`板块强弱说明：${localizeStockBackendText(payload.sector_rank.formula_note, "sector_strength")}`);
    }
  }
  if (payload.stock_candidates?.formula_version) {
    notes.push(`趋势候选公式：${payload.stock_candidates.formula_version}`);
  }
  if (payload.hybrid_fusion_candidates?.formula_version) {
    notes.push(`融合池公式：${payload.hybrid_fusion_candidates.formula_version}`);
  }
  if (payload.risk_exit?.formula_version) {
    notes.push(`风险退出公式：${payload.risk_exit.formula_version}`);
  }
  for (const gap of payload.data_gaps) {
    notes.push(
      `${localizeStockDataFamily(gap.input_family)} ${localizeDataGapStatus(gap.status)}：${localizeStockBackendText(
        gap.evidence,
        gap.input_family,
      )}`,
    );
  }
  for (const output of payload.unsupported_outputs) {
    notes.push(`${localizeStockDataFamily(output.key)} 阻断：${localizeStockBackendText(output.reason, output.key)}`);
  }
  notes.push(`可用输出：${payload.supported_outputs.map(localizeStockDataFamily).join("、") || "无"}`);
  return notes;
}

export function buildMarketStateCard(
  payload: LivermoreStrategyPayload,
): StockMarketStateCard {
  const gate = payload.market_gate;
  const warnings = [
    ...payload.diagnostics
      .filter((item) => item.severity !== "info")
      .map((item) => localizeStockBackendText(item.message, item.input_family)),
    ...payload.data_gaps
      .filter((gap) => gap.status !== "ready")
      .map(
        (gap) =>
          `${localizeStockDataFamily(gap.input_family)} ${localizeDataGapStatus(
            gap.status,
          )}：${localizeStockBackendText(gap.evidence, gap.input_family)}`,
      ),
  ];

  return {
    title: "市场状态",
    state: localizeMarketDataStatus(gate.state),
    exposureLabel: formatRatioAsPercent(gate.exposure),
    passedLabel: `${gate.passed_conditions} / ${gate.required_conditions} 条件通过`,
    basisLabel: localizeBasisLabel(payload.basis),
    warnings,
    conditions: gate.conditions.map((condition) => {
      const unknownVendorCondition = [
        condition.key,
        condition.label,
        condition.evidence,
        condition.source_series_id,
      ].some((value) => value && isTechnicalMarketConditionText(value));
      return {
        key: condition.key,
        label: unknownVendorCondition ? "条件待确认" : localizeMarketConditionLabel(condition.label),
        status: condition.status,
        evidence: unknownVendorCondition ? "说明待确认" : localizeMarketConditionEvidence(condition.evidence),
      };
    }),
  };
}

function localizeMarketConditionLabel(label: string): string {
  const value = label.trim();
  const normalized = value.toLowerCase().replace(/\s+/g, " ");
  const exactLabels: Record<string, string> = {
    "csi300 close > ma60": "沪深300收盘价 > MA60",
    "csi300 ma20 > ma60": "沪深300 MA20 > MA60",
    "5-day breadth > 0": "5日市场宽度 > 0",
    "limit-up seal/break quality positive": "涨停封板/破板质量为正",
  };
  if (exactLabels[normalized]) {
    return exactLabels[normalized];
  }
  if (isTechnicalMarketConditionText(value)) {
    return "条件待确认";
  }
  return value.replace(/\bCSI300\b/g, "沪深300").replace(/\bclose\b/gi, "收盘价");
}

function localizeMarketConditionEvidence(evidence: string): string {
  const value = evidence.trim();
  const normalized = value.toLowerCase().replace(/\s+/g, " ");
  const exactEvidence: Record<string, string> = {
    "close is above ma60.": "收盘价高于 MA60。",
    "close is below ma60.": "收盘价低于 MA60。",
    "ma20 is above ma60.": "MA20 高于 MA60。",
    "breadth inputs are not landed for the phase 1 slice.": "5日市场宽度输入尚未落地，当前阶段不可用。",
    "limit-up quality inputs are not landed for the phase 1 slice.": "涨停质量输入尚未落地，当前阶段不可用。",
  };
  if (exactEvidence[normalized]) {
    return exactEvidence[normalized];
  }
  if (isTechnicalMarketConditionText(value)) {
    return "说明待确认";
  }
  return value
    .replace(/\b(MA\d+)\s+is\s+above\b/gi, "$1 高于")
    .replace(/\b(MA\d+)\s+is\s+below\b/gi, "$1 低于")
    .replace(/\bclose\s+is\s+above\b/gi, "收盘价高于")
    .replace(/\bclose\s+is\s+below\b/gi, "收盘价低于")
    .replace(/\babove\b/gi, "高于")
    .replace(/\bbelow\b/gi, "低于")
    .replace(/\.$/, "。");
}

function isTechnicalMarketConditionText(value: string): boolean {
  const normalized = value.toLowerCase();
  return (
    normalized.includes("external_vendor") ||
    normalized.includes("vendor_") ||
    normalized.includes("choice_stock") ||
    normalized.includes("source_table")
  );
}

export function buildSectorRows(payload: LivermoreStrategyPayload): StockSectorRow[] {
  const items = [...(payload.sector_rank?.items ?? [])].sort((left, right) => left.rank - right.rank);
  const n = items.length;
  const scores = items
    .map((i) => i.score)
    .filter((s): s is number => s != null && Number.isFinite(s));
  const maxScore = scores.length ? Math.max(...scores) : 0;
  const pctAbs = items
    .map((i) => (i.avg_pctchange != null && Number.isFinite(i.avg_pctchange) ? Math.abs(i.avg_pctchange) : 0))
    .filter(Boolean);
  const maxPctAbs = pctAbs.length ? Math.max(...pctAbs) : 0;

  return items.map((item) => {
    const scoreNum = item.score;
    const scoreVal = scoreNum != null && Number.isFinite(scoreNum) ? scoreNum : null;
    const scoreNormalized =
      maxScore > 0 && scoreVal != null ? Math.min(1, Math.max(0, scoreVal / maxScore)) : 0;

    const pctRaw = item.avg_pctchange;
    const pctVal = pctRaw != null && Number.isFinite(pctRaw) ? pctRaw : null;

    let pctBar = 0;
    if (pctVal != null) {
      if (maxPctAbs > 0) {
        pctBar = (Math.abs(pctVal) / maxPctAbs) * 100;
      } else if (pctVal !== 0) {
        pctBar = 50;
      }
    }

    return {
      rank: item.rank,
      sectorCode: item.sector_code,
      sectorName: item.sector_name,
      score: formatNumber(scoreVal, 3),
      pctChange: formatPercent(pctVal ?? undefined),
      turnover: formatNumber(item.avg_turn, 2),
      amplitude: formatPercent(item.avg_amplitude),
      constituentCount: item.constituent_count,
      scoreValue: scoreVal,
      pctChangeValue: pctVal,
      turnoverValue: item.avg_turn != null && Number.isFinite(item.avg_turn) ? item.avg_turn : null,
      amplitudeValue:
        item.avg_amplitude != null && Number.isFinite(item.avg_amplitude) ? item.avg_amplitude : null,
      scoreNormalized,
      pctChangeBar: pctBar,
      isTop: n > 0 && item.rank <= 5,
      isBottom: n > 0 && item.rank >= n - 4,
    };
  });
}

export function buildSectorRowsFromSectorSeries(
  rows: LivermoreSectorRankSeriesPoint[],
): StockSectorRow[] {
  const items = [...rows].sort((left, right) => {
    const leftRank = finiteNumber(left.rank) ?? 9999;
    const rightRank = finiteNumber(right.rank) ?? 9999;
    if (leftRank !== rightRank) return leftRank - rightRank;
    return left.sector_code.localeCompare(right.sector_code);
  });
  const n = items.length;
  const scores = items
    .map((item) => finiteNumber(item.score))
    .filter((score): score is number => score != null);
  const maxScore = scores.length ? Math.max(...scores) : 0;
  const pctAbs = items
    .map((item) => finiteNumber(item.avg_pctchange))
    .filter((value): value is number => value != null)
    .map((value) => Math.abs(value))
    .filter(Boolean);
  const maxPctAbs = pctAbs.length ? Math.max(...pctAbs) : 0;

  return items.map((item, index) => {
    const rank = finiteNumber(item.rank) ?? index + 1;
    const scoreVal = finiteNumber(item.score);
    const pctVal = finiteNumber(item.avg_pctchange);
    const turnoverVal = finiteNumber(item.avg_turn);
    const amplitudeVal = finiteNumber(item.avg_amplitude);
    const constituentCount = finiteNumber(item.constituent_count) ?? 0;
    const scoreNormalized =
      maxScore > 0 && scoreVal != null ? Math.min(1, Math.max(0, scoreVal / maxScore)) : 0;

    let pctBar = 0;
    if (pctVal != null) {
      if (maxPctAbs > 0) {
        pctBar = (Math.abs(pctVal) / maxPctAbs) * 100;
      } else if (pctVal !== 0) {
        pctBar = 50;
      }
    }

    return {
      rank,
      sectorCode: item.sector_code,
      sectorName: item.sector_name,
      score: formatNumber(scoreVal, 3),
      pctChange: formatPercent(pctVal),
      turnover: formatNumber(turnoverVal, 2),
      amplitude: formatPercent(amplitudeVal),
      constituentCount,
      scoreValue: scoreVal,
      pctChangeValue: pctVal,
      turnoverValue: turnoverVal,
      amplitudeValue: amplitudeVal,
      scoreNormalized,
      pctChangeBar: pctBar,
      isTop: n > 0 && rank <= 5,
      isBottom: n > 0 && rank >= n - 4,
    };
  });
}

export function buildStockSectorOverviewState<TRow extends StockSectorRow>(
  rows: TRow[],
): StockSectorOverviewState<TRow> {
  return {
    leaderRow: rows[0] ?? null,
    tailRow: rows.length > 0 ? rows[rows.length - 1] : null,
    coverageCount: rows.reduce((sum, row) => sum + row.constituentCount, 0),
    topBars: rows.slice(0, 5),
    bottomBars: rows.slice(Math.max(rows.length - 5, 0)),
  };
}

export function buildSectorViewModel(
  payload: LivermoreStrategyPayload,
  view: StockSectorViewKind,
): StockSectorViewRow[] {
  return buildSectorViewRows(buildSectorRows(payload), view);
}

export function buildSectorViewRows(
  rows: StockSectorRow[],
  view: StockSectorViewKind,
): StockSectorViewRow[] {
  const sorted = [...rows].sort((a, b) => {
    const av = metricValueForView(a, view);
    const bv = metricValueForView(b, view);
    if (av == null && bv == null) return a.rank - b.rank;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (bv !== av) return bv - av;
    return a.rank - b.rank;
  });
  const values = sorted
    .map((r) => metricValueForView(r, view))
    .filter((v): v is number => v != null && Number.isFinite(v));
  let maxMag = values.length ? Math.max(...values.map((v) => Math.abs(v))) : 0;
  if (!(maxMag > 0)) maxMag = 1;
  return sorted.map((row) => {
    const v = metricValueForView(row, view);
    let metricBarNormalized = 0;
    if (v != null && Number.isFinite(v)) {
      metricBarNormalized = Math.min(1, Math.max(0, Math.abs(v) / maxMag));
    }
    return {
      ...row,
      metricBarNormalized,
    };
  });
}

export function buildSectorTableSortComparator(
  key: keyof StockSectorRow | "code" | "name" | "pctchange",
  order: "ascend" | "descend",
) {
  return (a: StockSectorRow, b: StockSectorRow) => {
    const sign = order === "ascend" ? 1 : -1;
    const num = (
      ai: StockSectorRow,
      bi: StockSectorRow,
      pick: (r: StockSectorRow) => number | null | undefined,
    ) => {
      const av = pick(ai);
      const bv = pick(bi);
      if ((av == null || !Number.isFinite(av)) && (bv == null || !Number.isFinite(bv))) return 0;
      if (av == null || !Number.isFinite(av)) return 1;
      if (bv == null || !Number.isFinite(bv)) return -1;
      if (av === bv) return 0;
      return av > bv ? sign : -sign;
    };

    switch (key) {
      case "rank":
        return num(a, b, (r) => r.rank);
      case "sectorCode":
        return sign * a.sectorCode.localeCompare(b.sectorCode, "zh-Hans-CN");
      case "sectorName":
      case "name":
        return sign * a.sectorName.localeCompare(b.sectorName, "zh-Hans-CN");
      case "score":
        return num(a, b, (r) => r.scoreValue ?? numericFromDisplay(r.score));
      case "pctChange":
      case "pctchange":
        return num(a, b, (r) => r.pctChangeValue ?? Number.NaN);
      case "turnover":
        return num(a, b, (r) => r.turnoverValue ?? numericFromDisplay(r.turnover));
      case "amplitude":
        return num(a, b, (r) => r.amplitudeValue ?? Number.NaN);
      case "constituentCount":
        return num(a, b, (r) => r.constituentCount);
      default:
        return a.rank - b.rank;
    }
  };
}

export function buildCandidateEvidenceCards(
  payload: LivermoreStrategyPayload,
): StockCandidateEvidenceCard[] {
  const hybridCards = isStockModulePrimaryExcluded(payload, "hybrid_fusion")
    ? []
    : buildHybridFusionEvidenceCards(payload);
  if (hybridCards.length > 0) return hybridCards;
  const stockCards = isStockModulePrimaryExcluded(payload, "stock_candidates")
    ? []
    : sortedCandidateItems(payload).map((item) => {
      const pattern = deriveCandidatePattern(item);
      const patternNote = "UI 辅助归类标签，不构成正式结论";
      const distanceToBreakoutPct = formatDistanceToBreakoutPct(item);

    const evidenceBullets: StockCandidateEvidenceBullet[] = [
      {
        key: "sector_rank",
        label: "行业排名",
        value: `行业排名第 ${item.sector_rank}：${item.sector_name}`,
      },
      {
        key: "close_vs_break",
        label: "收盘 vs 观察位",
        value: `收盘价 ${formatNumber(item.close)} · 观察位 ${formatNumber(item.breakout_level)}`,
      },
      {
        key: "ma_curve",
        label: "均线结构",
        value: `MA20 ${formatNumber(item.ma20)} · MA60 ${formatNumber(item.ma60)} · MA120 ${formatNumber(item.ma120)}`,
      },
      {
        key: "strength_turnover",
        label: "强度 / 换手观察",
        value: `收盘强度 ${formatRatioAsPercent(item.close_strength, 2)} · 换手观察值 ${formatNumber(item.abnormal_turnover, 3)}`,
      },
      ...buildCandidateFundamentalEvidence(item),
      {
        key: "gap_norm",
        label: "跳空归一观察",
        value:
          item.gap_norm != null && Number.isFinite(item.gap_norm)
            ? `${item.gap_norm.toFixed(4)}`
            : "待补",
      },
      {
        key: "breakout_extension_norm",
        label: "突破延展观察",
        value:
          item.breakout_extension_norm != null && Number.isFinite(item.breakout_extension_norm)
            ? `${item.breakout_extension_norm.toFixed(4)}`
            : "待补",
      },
      {
        key: "ema10_watch",
        label: "10EMA 失效观察",
        value: `当前 10EMA ${formatNumber(item.ema10)}，用于复核是否降级观察。`,
      },
    ];

    const evidence = evidenceBullets.map((bullet) => `${bullet.label}：${bullet.value}`);

    return {
      rank: item.rank,
      stockCode: item.stock_code,
      stockName: item.stock_name,
      sectorCode: item.sector_code,
      sectorName: item.sector_name,
      headline: `观察候选 #${item.rank} · ${item.stock_name}`,
      pattern,
      patternNote,
      distanceToBreakoutPct,
      evidenceBullets,
      evidence,
      counterEvidence: [
        candidateFundamentalCounterEvidence(item),
        "新闻、公告、财报事件尚未进入候选卡。",
        "ATR、真实盘中成交顺序和精确涨跌停状态未在当前只读卡片中完整验证。",
      ],
      invalidationRules: [
        `收盘跌破 10EMA ${formatNumber(item.ema10)} 或突破观察位 ${formatNumber(item.breakout_level)} 后需要降级复核。`,
        "所属行业强度跌出前列需要重新复核。",
        "涨跌停状态、停牌状态或数据质量陈旧/缺失时，不得继续解释为有效观察。",
      ],
      rawFields: [
        { key: "ema10", label: "10日均线", value: formatNumber(item.ema10) },
        { key: "ma20", label: "20日均线", value: formatNumber(item.ma20) },
        { key: "ma60", label: "60日均线", value: formatNumber(item.ma60) },
        { key: "ma120", label: "120日均线", value: formatNumber(item.ma120) },
        { key: "abnormal_turnover", label: "换手观察", value: formatNumber(item.abnormal_turnover, 4) },
        { key: "gap_norm", label: "跳空观察", value: formatNumber(item.gap_norm, 4) },
        {
          key: "breakout_extension_norm",
          label: "突破延展",
          value: formatNumber(item.breakout_extension_norm, 4),
        },
        { key: "close_strength", label: "收盘强度", value: formatNumber(item.close_strength, 4) },
        { key: "factor_score", label: "因子分", value: formatNumber(item.factor_score, 4) },
        {
          key: "factor_overlay_rank",
          label: "因子叠加排名",
          value: formatNumber(item.factor_overlay_rank, 0),
        },
        { key: "pe", label: "PE", value: formatNumber(item.pe, 4) },
        { key: "pb", label: "PB", value: formatNumber(item.pb, 4) },
        { key: "ps", label: "PS", value: formatNumber(item.ps, 4) },
        { key: "roe", label: "ROE", value: formatNumber(item.roe, 4) },
        { key: "gross_margin", label: "毛利率", value: formatNumber(item.gross_margin, 4) },
      ],
    };
  });
  if (stockCards.length > 0) return stockCards;
  const freshCards = isStockModulePrimaryExcluded(payload, "fresh_trend_watchlist")
    ? []
    : buildFreshTrendEvidenceCards(payload);
  return freshCards;
}

function localizeRiskExitReason(reason: string | null | undefined): string {
  const value = reason?.trim();
  if (!value) return "原因待补";
  const lower = value.toLowerCase();
  const normalized = value.toLowerCase().replace(/[\s-]+/g, "_");
  if (
    normalized.includes("external_vendor") ||
    normalized.includes("vendor_") ||
    lower.includes("external vendor") ||
    lower.includes("vendor ")
  ) {
    return "风险退出证据待确认";
  }
  const labels: Record<string, string> = {
    "2d_below_ema10": "连续 2 日收盘低于 10 日均线",
    "2d_below_ema10_with_volume": "连续 2 日收盘低于 10 日均线且放量",
  };
  return labels[normalized] ?? localizeStockBackendText(value, "risk_exit");
}

export function buildRiskExitRows(
  payload: LivermoreStrategyPayload,
  confluence?: LivermoreSignalConfluencePayload | null,
): StockRiskExitRow[] {
  const rows: StockRiskExitRow[] = [];
  const seen = new Set<string>();

  for (const item of payload.risk_exit?.items ?? []) {
    const key = `${item.stock_code}:triggered`;
    seen.add(key);
    const exit = item.latest_ema10;
    const latest = item.latest_close;
    const parsedExit = exit;
    const parsedLatest = latest;
    const { distanceToExitPct, exitDistanceBucket } = bucketExitDistance({
      status: "triggered",
      latest: parsedLatest,
      exit: parsedExit,
    });
    rows.push({
      stockCode: item.stock_code,
      stockName: item.stock_name,
      status: "triggered",
      latestClose: formatNumber(parsedLatest),
      exitWatchPrice: formatNumber(parsedExit),
      reason: `触发复核：${localizeRiskExitReason(item.reason)}`,
      distanceToExitPct,
      exitDistanceBucket,
    });
  }

  for (const item of payload.risk_exit?.watch_items ?? []) {
    const status = item.triggered ? "triggered" : "watch";
    const key = `${item.stock_code}:${status}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    const latest = item.latest_close;
    const exit =
      status === "triggered"
        ? (item.exit_watch_price ?? item.latest_ema10)
        : item.exit_watch_price;
    const { distanceToExitPct, exitDistanceBucket } = bucketExitDistance({
      status,
      latest,
      exit: exit ?? null,
    });
    rows.push({
      stockCode: item.stock_code,
      stockName: item.stock_name,
      status,
      latestClose: formatNumber(latest),
      exitWatchPrice: formatNumber(exit ?? undefined),
      reason: status === "triggered" ? "触发复核：跌破退出观察价" : "观察中：接近退出观察价",
      distanceToExitPct,
      exitDistanceBucket,
    });
  }

  for (const item of confluence?.exit_observations ?? []) {
    if (!item.stock_code) {
      continue;
    }
    const status = item.action === "exit_triggered" || item.triggered ? "triggered" : "watch";
    const key = `${item.stock_code}:${status}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    const latest = item.current_price;
    const exit = item.exit_watch_price ?? null;
    const { distanceToExitPct, exitDistanceBucket } = bucketExitDistance({
      status,
      latest: latest ?? null,
      exit,
    });
    const evidenceReason = normalizeEvidence(item.evidence)[0];
    rows.push({
      stockCode: item.stock_code,
      stockName: item.stock_name ?? item.stock_code,
      status,
      latestClose: formatNumber(latest),
      exitWatchPrice: formatNumber(exit ?? undefined),
      reason:
        (evidenceReason ? localizeRiskExitReason(evidenceReason) : null) ??
        (status === "triggered" ? "触发复核：联动观察命中" : "观察中：联动观察"),
      distanceToExitPct,
      exitDistanceBucket,
    });
  }

  return rows;
}

export function buildClosedLoopSummary(
  payload: LivermoreStrategyPayload,
  confluence: LivermoreSignalConfluencePayload | null,
  meta: StockViewModelMeta = {},
): StockClosedLoopSummary {
  const state = confluence?.closed_loop_state ?? null;
  const adversarial = confluence?.adversarial_context ?? null;
  const entryStatus = state?.entry_gate ?? deriveEntryGateStatus(state);
  const adversarialStatus = adversarial?.risk_gate ?? "missing";
  const exitStatus = state?.exit_gate ?? deriveExitGateStatus(payload, confluence);
  const exitCounts = closedLoopExitCounts(payload, confluence);
  const replayStatusRaw = state?.replay_status ?? "missing";
  const replayStatus = normalizeClosedLoopStatus(replayStatusRaw, "missing");
  const replayEvidence = confluence?.replay_evidence ?? null;
  const lineageStatus = state?.lineage_status ?? deriveLineageStatus(adversarial, state);
  const fallbackMode = meta.fallback_mode ?? "none";

  const items: StockClosedLoopSummaryItem[] = [
    {
      key: "entry_gate",
      label: "入场观察门",
      status: entryStatus,
      statusLabel: closedLoopStatusLabel("entry_gate", entryStatus),
      tone: closedLoopTone("entry_gate", entryStatus),
      detail:
        entryStatus === "missing"
          ? "待补：闭环入场状态未接通"
          : `市场门控 ${localizeMarketDataStatus(payload.market_gate.state)} / 宏观 ${closedLoopStatusLabel(
              "entry_gate",
              confluence?.macro_context.status ?? "missing",
            )}`,
    },
    {
      key: "adversarial_gate",
      label: "反拥挤拦截",
      status: adversarialStatus,
      statusLabel: closedLoopStatusLabel("adversarial_gate", adversarialStatus),
      tone: closedLoopTone("adversarial_gate", adversarialStatus),
      detail:
        adversarialStatus === "missing"
          ? "待补：反拥挤证据缺失，不能视为中性证明"
          : closedLoopAdversarialDetail(adversarial),
    },
    {
      key: "risk_exit",
      label: "风险退出",
      status: exitStatus,
      statusLabel: closedLoopStatusLabel("risk_exit", exitStatus),
      tone: closedLoopTone("risk_exit", exitStatus),
      detail:
        exitStatus === "missing"
          ? "待补：风险退出状态未接通"
          : `${exitCounts.watchCount} 条观察 / ${exitCounts.triggeredCount} 条触发`,
    },
    {
      key: "replay",
      label: "回放证据",
      status: replayStatus,
      statusLabel: closedLoopStatusLabel("replay", replayStatus),
      tone: closedLoopTone("replay", replayStatus),
      detail: closedLoopReplayDetail(replayStatusRaw, replayStatus, replayEvidence),
      badges: closedLoopReplayBadges(replayStatusRaw),
    },
    {
      key: "lineage",
      label: "血缘状态",
      status: lineageStatus,
      statusLabel: closedLoopStatusLabel("lineage", lineageStatus),
      tone: closedLoopTone("lineage", lineageStatus),
      detail: `质量 ${localizeMetaQualityFlag(meta.quality_flag)} / 供数状态 ${localizeMetaVendorStatus(
        meta.vendor_status,
      )}${
        fallbackMode !== "none" ? ` / ${localizeFallbackMode(fallbackMode)}` : ""
      }`,
    },
  ];

  const boundaryCount = items.filter((item) => item.tone !== "positive").length;
  const referenceRating = buildDecisionReferenceRating(items);
  return {
    summaryLabel: boundaryCount > 0 ? `${boundaryCount} 项待复核` : "全部通过",
    boundaryCount,
    referenceRating,
    verdict: buildClosedLoopVerdict(referenceRating, items),
    items,
  };
}

function buildClosedLoopVerdict(
  rating: StockDecisionReferenceRating,
  items: StockClosedLoopSummaryItem[],
): StockClosedLoopVerdict {
  const blockedItem = items.find((item) => item.key === "adversarial_gate" && item.tone === "negative");
  const negativeItem = items.find((item) => item.tone === "negative");
  const warningItem = items.find((item) => item.tone === "warning");
  const primaryItem =
    (rating.code === "blocked" ? blockedItem : undefined) ??
    negativeItem ??
    warningItem ??
    items.find((item) => item.key === "entry_gate") ??
    items[0];
  const evidence = items.slice(0, 4).map((item) => `${item.label}: ${item.statusLabel}`);

  if (rating.code === "blocked") {
    return {
      code: rating.code,
      tone: rating.tone,
      label: rating.label,
      headline: "闭环阻断，先复核约束项",
      primaryReason: primaryItem?.detail ?? rating.detail,
      nextStep: "保持仅观察输出，优先处理阻断门、退出触发和降级来源。",
      evidence,
    };
  }
  if (rating.code === "insufficient_data") {
    return {
      code: rating.code,
      tone: rating.tone,
      label: rating.label,
      headline: "证据不足，不形成有效观察结论",
      primaryReason: primaryItem?.detail ?? rating.detail,
      nextStep: "先补齐宏观反拥挤、回放窗口或血缘证据，再进入人工复核。",
      evidence,
    };
  }
  if (rating.code === "pause") {
    return {
      code: rating.code,
      tone: rating.tone,
      label: rating.label,
      headline: "暂缓复核，存在降级边界",
      primaryReason: primaryItem?.detail ?? rating.detail,
      nextStep: "保留观察队列，但先复核降级、回退、代理观察或待成熟日期。",
      evidence,
    };
  }
  return {
    code: rating.code,
    tone: rating.tone,
    label: rating.label,
    headline: "可进入人工复核队列",
    primaryReason: rating.detail,
    nextStep: "继续按仅观察口径复核候选、退出观察和回放证据，不推导策略收益。",
    evidence,
  };
}

function closedLoopReplayDetail(
  replayStatusRaw: LivermoreSignalConfluencePayload["closed_loop_state"] extends infer State
    ? State extends { replay_status?: infer ReplayStatus }
      ? ReplayStatus
      : unknown
    : unknown,
  replayStatus: string,
  replayEvidence: LivermoreSignalConfluencePayload["replay_evidence"] | null,
): string {
  const windowStatus = replayStatusWindow(replayStatusRaw);
  if (windowStatus) {
    const excludedDates = windowStatus.blocked_dates.map((item) => item.trade_date);
    const blockedReasons = windowStatus.blocked_dates.map(
      (item) => `${item.trade_date} ${localizeReplayReasonCode(item.reason_code)}`,
    );
    const detailParts = [
      windowStatus.has_decision_usable_completed_stats
        ? `已纳入完成日期：${windowStatus.included_completed_stats_dates.join("、") || "无"}`
        : "暂无可用于判断的完成回放日",
      excludedDates.length > 0
        ? `剔除日期：${excludedDates.join("、")}`
        : "无剔除日期",
      ...blockedReasons,
    ];
    if (windowStatus.completed_zero_signal_dates.length > 0) {
      detailParts.push(`完成但无信号日期：${windowStatus.completed_zero_signal_dates.join("、")}`);
    }
    detailParts.push("仅作观察，不推导策略有效性");
    return detailParts.join(" / ");
  }
  if (replayStatus === "missing") {
    return "待补：候选历史回放未接通";
  }
  if (replayEvidence) {
    const rowCount = Number.isFinite(replayEvidence.row_count) ? replayEvidence.row_count : 0;
    const matchedEntryCount = Number.isFinite(replayEvidence.matched_entry_count)
      ? replayEvidence.matched_entry_count
      : 0;
    return `候选历史回放已接通：${rowCount} 条快照 / 覆盖 ${matchedEntryCount} 个当前候选`;
  }
  return "候选历史回放已接通";
}

function closedLoopReplayBadges(
  replayStatusRaw: LivermoreSignalConfluencePayload["closed_loop_state"] extends infer State
    ? State extends { replay_status?: infer ReplayStatus }
      ? ReplayStatus
      : unknown
    : unknown,
): string[] | undefined {
  const windowStatus = replayStatusWindow(replayStatusRaw);
  if (!windowStatus) {
    return undefined;
  }
  return [
    `完成 ${windowStatus.completed_dates}日`,
    `待成熟 ${windowStatus.pending_dates}日`,
    `不可用 ${windowStatus.unsupported_dates}日`,
    `代理观察 ${windowStatus.proxy_only_dates}日`,
    `完成样本 ${windowStatus.completed_candidate_rows}`,
  ];
}

function localizeReplayReasonCode(reasonCode: string | null | undefined): string {
  const normalized = (reasonCode ?? "").trim().toLowerCase();
  const labels: Record<string, string> = {
    missing_daily_limit_flags: "涨跌停标记缺失",
    missing_required_source_table: "必需数据源缺失",
    forward_returns_pending: "远期收益待成熟",
    proxy_theme_only: "仅代理题材",
    real_theme_inputs_unconfirmed: "真实题材输入待确认",
  };
  if (!normalized) return "原因待补";
  if (normalized.includes("source_table") && normalized.includes("missing")) return "数据源缺失";
  return labels[normalized] ?? "原因待确认";
}

function normalizeClosedLoopStatus(value: unknown, defaultValue: string): string {
  if (typeof value === "string") {
    return value;
  }
  const windowStatus = replayStatusWindow(value);
  return windowStatus?.window_status ?? defaultValue;
}

function replayStatusWindow(value: unknown): NormalizedConfluenceReplayStatus | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const candidate = value as {
    window_status?: unknown;
    maturity_status?: unknown;
    has_decision_usable_completed_stats?: unknown;
    completed_dates?: unknown;
    pending_dates?: unknown;
    unsupported_dates?: unknown;
    proxy_only_dates?: unknown;
    completed_candidate_rows?: unknown;
    pending_candidate_rows?: unknown;
    unsupported_candidate_rows?: unknown;
    proxy_only_candidate_rows?: unknown;
    matched_entry_count?: unknown;
    has_required_horizon_stats?: unknown;
    included_completed_stats_dates?: unknown;
    blocked_dates?: unknown;
    completed_zero_signal_dates?: unknown;
  };
  if (!isBacktestWindowSummaryStatus(candidate.window_status)) {
    return null;
  }
  return {
    window_status: candidate.window_status,
    maturity_status: typeof candidate.maturity_status === "string" ? candidate.maturity_status : undefined,
    has_decision_usable_completed_stats: candidate.has_decision_usable_completed_stats === true,
    completed_dates: finiteCount(candidate.completed_dates),
    pending_dates: finiteCount(candidate.pending_dates),
    unsupported_dates: finiteCount(candidate.unsupported_dates),
    proxy_only_dates: finiteCount(candidate.proxy_only_dates),
    completed_candidate_rows: finiteCount(candidate.completed_candidate_rows),
    pending_candidate_rows: finiteCount(candidate.pending_candidate_rows),
    unsupported_candidate_rows: finiteCount(candidate.unsupported_candidate_rows),
    proxy_only_candidate_rows: finiteCount(candidate.proxy_only_candidate_rows),
    matched_entry_count: finiteCount(candidate.matched_entry_count),
    has_required_horizon_stats: candidate.has_required_horizon_stats === true,
    included_completed_stats_dates: stringList(candidate.included_completed_stats_dates),
    blocked_dates: blockedReplayDates(candidate.blocked_dates),
    completed_zero_signal_dates: stringList(candidate.completed_zero_signal_dates),
  };
}

function isBacktestWindowSummaryStatus(value: unknown): value is BacktestWindowSummaryStatus {
  return value === "valid" || value === "partial" || value === "unsupported";
}

function finiteCount(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string" && item.length > 0);
}

function blockedReplayDates(value: unknown): NormalizedConfluenceReplayBlockedDate[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") {
      return [];
    }
    const row = item as {
      trade_date?: unknown;
      status?: unknown;
      reason_code?: unknown;
      signal_kinds?: unknown;
    };
    if (typeof row.trade_date !== "string" || typeof row.reason_code !== "string") {
      return [];
    }
    return [
      {
        trade_date: row.trade_date,
        status: normalizeBlockedReplayDateStatus(row.status, row.reason_code),
        reason_code: row.reason_code,
        signal_kinds: stringList(row.signal_kinds),
      },
    ];
  });
}

function normalizeBlockedReplayDateStatus(
  value: unknown,
  reasonCode: string,
): ConfluenceReplayBlockedDate["status"] {
  if (value === "pending" || value === "unsupported" || value === "proxy_only") {
    return value;
  }
  if (reasonCode === "forward_returns_pending") {
    return "pending";
  }
  if (reasonCode === "proxy_theme_only" || reasonCode === "real_theme_inputs_unconfirmed") {
    return "proxy_only";
  }
  return "unsupported";
}

function buildDecisionReferenceRating(items: StockClosedLoopSummaryItem[]): StockDecisionReferenceRating {
  const negativeItems = items.filter((item) => item.tone === "negative");
  if (negativeItems.length > 0) {
    return {
      code: "blocked",
      label: "拦截",
      tone: "negative",
      detail: `${closedLoopItemLabels(negativeItems)} 已触发拦截或退出，先保留复核队列。`,
    };
  }

  const missingItems = items.filter(
    (item) => String(item.status).toLowerCase() === "missing" || item.status === "unsupported",
  );
  if (missingItems.length > 0) {
    return {
      code: "insufficient_data",
      label: "数据不足",
      tone: "warning",
      detail: `${closedLoopItemLabels(missingItems)} 待补，不能作为中性证明。`,
    };
  }

  const warningItems = items.filter((item) => item.tone === "warning");
  if (warningItems.length > 0) {
    return {
      code: "pause",
      label: "暂缓",
      tone: "warning",
      detail: `${closedLoopItemLabels(warningItems)} 仍有降级或仅观察边界。`,
    };
  }

  return {
    code: "reviewable",
    label: "可复核",
    tone: "positive",
    detail: "闭环证据完整，可进入人工复核队列。",
  };
}

function closedLoopItemLabels(items: StockClosedLoopSummaryItem[]): string {
  return items.map((item) => item.label).join("、");
}

function closedLoopStatusLabel(key: StockClosedLoopSummaryItem["key"], status: string): string {
  const normalized = String(status).toLowerCase();
  if (normalized === "valid") return "可用";
  if (normalized === "partial") return "部分有效";
  if (normalized === "unsupported") return "不可用";
  if (normalized === "missing") return "待补";
  if (normalized === "degrade" || normalized === "degraded" || normalized === "stale" || normalized === "error") {
    return "降级";
  }
  if (normalized === "observe_only") return "仅观察";
  if (normalized === "block" || normalized === "blocked") return "阻断";
  if (normalized === "triggered") return "已触发";
  if (normalized === "available") return "已接通";
  if (normalized === "complete") return "完整";
  if (normalized === "open") return "开放";
  if (normalized === "watch") return "观察中";
  if (normalized === "pass" || normalized === "allow" || normalized === "ok") return "通过";
  return key === "lineage" ? "待确认" : "状态待确认";
}

function closedLoopAdversarialDetail(
  adversarial: LivermoreSignalConfluencePayload["adversarial_context"] | null,
): string {
  const reason = adversarial?.strongest_block_reason?.trim();
  if (reason) {
    return localizeStockBackendText(reason);
  }
  const fallbackValues = [adversarial?.mode, adversarial?.status, adversarial?.risk_gate];
  if (fallbackValues.some(isTechnicalStockFallbackText)) {
    return "\u53cd\u62e5\u6324\u72b6\u6001\u5f85\u786e\u8ba4";
  }
  return `${adversarial?.mode ?? "anti-crowding"} / \u72b6\u6001 ${adversarial?.status ?? "missing"}`;
}

function isTechnicalStockFallbackText(value: string | null | undefined): boolean {
  const normalized = value?.toLowerCase() ?? "";
  return (
    normalized.includes("external_vendor") ||
    normalized.includes("vendor_") ||
    normalized.includes("choice_stock") ||
    normalized.includes("source_table")
  );
}

function closedLoopExitCounts(
  payload: LivermoreStrategyPayload,
  confluence: LivermoreSignalConfluencePayload | null,
): { watchCount: number; triggeredCount: number } {
  const observations = confluence?.exit_observations ?? [];
  if (observations.length > 0) {
    return {
      watchCount: observations.filter((item) => item.action !== "exit_triggered" && !item.triggered).length,
      triggeredCount: observations.filter((item) => item.action === "exit_triggered" || item.triggered).length,
    };
  }
  return {
    watchCount: payload.risk_exit?.watch_items?.length ?? 0,
    triggeredCount: payload.risk_exit?.items?.length ?? 0,
  };
}

function closedLoopTone(key: StockClosedLoopSummaryItem["key"], status: string): StockClosedLoopTone {
  const normalized = String(status).toLowerCase();
  if (normalized === "partial" || normalized === "unsupported") {
    return "warning";
  }
  if (
    normalized === "missing" ||
    normalized === "degrade" ||
    normalized === "degraded" ||
    normalized === "observe_only" ||
    normalized === "partial" ||
    normalized === "unsupported"
  ) {
    return "warning";
  }
  if (normalized === "block" || normalized === "blocked" || normalized === "triggered") {
    return "negative";
  }
  if (
    normalized === "pass" ||
    normalized === "allow" ||
    normalized === "ok" ||
    normalized === "open" ||
    normalized === "watch" ||
    normalized === "available" ||
    normalized === "complete"
  ) {
    return "positive";
  }
  return key === "adversarial_gate" ? "warning" : "neutral";
}

function deriveEntryGateStatus(state: LivermoreSignalConfluencePayload["closed_loop_state"] | null): string {
  const status = String((state as Record<string, unknown> | null)?.status ?? "").toLowerCase();
  const action = String((state as Record<string, unknown> | null)?.entry_observation_action ?? "").toLowerCase();
  if (status.includes("blocked") || action === "blocked") return "blocked";
  if (action === "observe_entry_setup") return "open";
  if (action === "observe_only") return "observe_only";
  if (status === "open") return "open";
  if (status === "observe_only") return "observe_only";
  return "missing";
}

function deriveExitGateStatus(
  payload: LivermoreStrategyPayload,
  confluence: LivermoreSignalConfluencePayload | null,
): string {
  const exits = confluence?.exit_observations ?? [];
  if (exits.some((item) => item.action === "exit_triggered" || item.triggered)) return "triggered";
  if (exits.length > 0 || (payload.risk_exit?.watch_items?.length ?? 0) > 0) return "watch";
  if ((payload.risk_exit?.items?.length ?? 0) > 0) return "triggered";
  return "missing";
}

function deriveLineageStatus(
  adversarial: LivermoreSignalConfluencePayload["adversarial_context"] | null | undefined,
  state: LivermoreSignalConfluencePayload["closed_loop_state"] | null,
): string {
  const stateStatus = String((state as Record<string, unknown> | null)?.status ?? "").toLowerCase();
  if (stateStatus.includes("missing")) return "missing";
  if (stateStatus.includes("degraded")) return "degraded";

  const adversarialStatus = String(adversarial?.status ?? "").toLowerCase();
  if (adversarialStatus === "missing") return "missing";
  if (adversarialStatus === "degraded" || adversarialStatus === "error") return "degraded";
  if (adversarialStatus === "ok" || adversarialStatus === "complete") return "complete";
  return "missing";
}

export type StockStrategyPanelQueryState = "idle" | "loading" | "ready" | "error";

export type StockStrategyPanelMiniStatValueTone = "up" | "down" | "flat" | "emphasis" | "warning";

export type StockStrategyPanelMiniStat = {
  key: string;
  label: string;
  value: string;
  tone?: StockClosedLoopTone;
  /** 数值着色：红涨绿跌 / 强调 / 预警 */
  valueTone?: StockStrategyPanelMiniStatValueTone;
};

export type StockStrategyPanelResultSummary = {
  headline: string;
  detail?: string;
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

export function localizeImplementationStage(stage: string): string {
  const normalized = stage.trim().toLowerCase();
  const labels: Record<string, string> = {
    verification_pending: "证据待齐",
    proxy_reconstruction: "代理重建",
    proxy_only: "仅代理观察",
    landed: "已落地",
    partial: "部分就绪",
    missing_inputs: "输入待补",
    provisional: "临时版",
    ready: "就绪",
    no_data: "暂无数据",
  };
  return labels[normalized] ?? "阶段待确认";
}

export function localizeThemeRadarBadge(isProxy: boolean, formulaVersion?: string | null): string {
  if (isProxy) {
    return "代理观察";
  }
  const version = formulaVersion?.trim();
  return version ? `概念库` : "概念库";
}

export function localizeThemeSourceKind(sourceKind: string | undefined, isProxyDefault: boolean): string {
  const normalized = (sourceKind ?? "").trim().toLowerCase();
  if (normalized === "proxy" || (!normalized && isProxyDefault)) {
    return "代理观察";
  }
  if (normalized === "real_concept" || normalized === "concept") {
    return "概念库";
  }
  if (normalized.includes("proxy")) {
    return "代理观察";
  }
  if (!normalized) {
    return isProxyDefault ? "代理观察" : "概念库";
  }
  return "来源待确认";
}

export function localizeMarketDataStatus(status: string | null | undefined): string {
  const normalized = (status ?? "").trim().toUpperCase();
  const labels: Record<string, string> = {
    NO_DATA: "暂无数据",
    STALE: "数据陈旧",
    PENDING_DATA: "数据待补",
    OFF: "关闭",
    WARM: "温和",
    HOT: "偏热",
    OVERHEAT: "过热",
    UNKNOWN: "状态待确认",
  };
  return labels[normalized] ?? (normalized ? "状态待确认" : "状态待补");
}

function localizeThemeUnsupportedSummary(reason: string): { detail: string; gateHint?: string } {
  const text = reason.trim();
  const lower = text.toLowerCase();
  if (lower.includes("overheat")) {
    return {
      detail: "市场过热门控下暂停题材执行观察；历史回放显示该桶拖累。",
      gateHint: "OVERHEAT",
    };
  }
  if (lower.includes("no_data") || lower.includes("not landed") || lower.includes("missing")) {
    return {
      detail: "题材输入未落地或门控未开放，暂不出执行结论。",
    };
  }
  if (text.length <= 48) {
    return { detail: text };
  }
  return {
    detail: "门控或数据限制导致暂未产出题材结论，展开查看英文原文。",
  };
}

function formatBacktestRate(value: number | null | undefined, digits = 1): string {
  if (value == null || !Number.isFinite(value)) {
    return "待补";
  }
  return `${(value * 100).toFixed(digits)}%`;
}

function formatBacktestSignedReturn(value: number | null | undefined, digits = 1): string {
  if (value == null || !Number.isFinite(value)) {
    return "待补";
  }
  const pct = value * 100;
  const prefix = pct > 0 ? "+" : "";
  return `${prefix}${pct.toFixed(digits)}%`;
}

function formatBacktestHorizonStatsText(stats: LivermoreCandidateHistoryHorizonStats | undefined): string {
  if (!stats || stats.available_count <= 0) {
    return "样本待补";
  }
  return `胜率 ${formatBacktestRate(stats.win_rate)} / 均收益 ${formatBacktestSignedReturn(stats.avg_return)} / ${stats.available_count}条`;
}

function pickTopPriorityRow(
  rows: LivermoreStrategyScorePayload["rows"],
): LivermoreStrategyScorePayload["rows"][number] | null {
  const ranked = rows
    .filter((row) => row.priority_score != null && Number.isFinite(row.priority_score))
    .sort((left, right) => (right.priority_score ?? 0) - (left.priority_score ?? 0));
  return ranked[0] ?? rows[0] ?? null;
}

function summarizeThemeMovementCount(payload: LivermoreStrategyPayload): number {
  return (payload.theme_breakout?.items ?? []).reduce(
    (sum, item) => sum + (item.movement_event_count ?? 0),
    0,
  );
}

export function buildDeepAnalysisGateSummary(input: {
  gateState: string | null | undefined;
  themeUnsupportedReason?: string;
  priorityStrategyLabel?: string | null;
}): StockDeepAnalysisGateSummary {
  const gateLabel = input.gateState ? localizeMarketDataStatus(input.gateState) : "门控待补";
  const parts = [`当前市场门控：${gateLabel}`];
  let tone: StockClosedLoopTone = "neutral";

  if (input.themeUnsupportedReason) {
    const localized = localizeThemeUnsupportedSummary(input.themeUnsupportedReason);
    if (localized.gateHint === "OVERHEAT" || input.gateState === "OVERHEAT") {
      parts.push("题材观察暂停");
      tone = "warning";
    } else {
      parts.push("题材未开放");
      tone = "warning";
    }
  }

  if (input.priorityStrategyLabel) {
    parts.push(`优先看${input.priorityStrategyLabel}复核`);
    if (tone === "neutral") tone = "positive";
  } else if (input.gateState === "OVERHEAT") {
    parts.push("优先看多因子复核");
    tone = "warning";
  } else if (input.gateState === "WARM") {
    parts.push("超跌池已激活");
    if (tone === "neutral") tone = "positive";
  }

  return { line: parts.join(" · "), tone };
}

export function buildDeepZoneAuditRows(input: {
  cycleRotationSummary?: Pick<StockStrategyPanelResultSummary, "badgeLabel" | "tone"> | null;
  themeBreakoutSummary?: Pick<StockStrategyPanelResultSummary, "badgeLabel" | "tone"> | null;
  strategyBacktestSummary: Pick<StockStrategyPanelResultSummary, "badgeLabel" | "tone">;
  strategyBacktestDateRangeLabel: string;
  consensusItemCount: number;
  reviewQueueCount: number;
  consensusReviewSummary: Pick<StockStrategyPanelResultSummary, "tone">;
  marketPrioritySummary: Pick<StockStrategyPanelResultSummary, "tone">;
  eventsMonitoringSummary: Pick<StockStrategyPanelResultSummary, "badgeLabel" | "tone">;
  eventMonitorCount: number;
}): StockDeepZoneAuditRow[] {
  return [
    {
      key: "supply",
      label: "供数",
      value: input.cycleRotationSummary?.badgeLabel ?? input.themeBreakoutSummary?.badgeLabel ?? "待确认",
      tone: input.cycleRotationSummary?.tone ?? input.themeBreakoutSummary?.tone ?? "neutral",
    },
    {
      key: "replay",
      label: "回放",
      value: input.strategyBacktestSummary.badgeLabel ?? input.strategyBacktestDateRangeLabel,
      tone: input.strategyBacktestSummary.tone ?? "neutral",
    },
    {
      key: "review",
      label: "候选",
      value: `${input.consensusItemCount} / ${input.reviewQueueCount}`,
      tone: input.consensusReviewSummary.tone ?? input.marketPrioritySummary.tone ?? "neutral",
    },
    {
      key: "events",
      label: "事件",
      value: input.eventsMonitoringSummary.badgeLabel ?? `${input.eventMonitorCount}`,
      tone: input.eventsMonitoringSummary.tone ?? "neutral",
    },
  ];
}

function eventMonitorPriority(row: StockAnalysisEventMonitorRow): number {
  if (row.level === "error") return 3;
  if (row.level === "warning") return 2;
  return 1;
}

function eventMonitorSourceLabel(source: StockAnalysisEventMonitorRow["source"]): string {
  const labels: Record<StockAnalysisEventMonitorRow["source"], string> = {
    diagnostic: "诊断",
    data_gap: "缺口",
    unsupported: "阻断",
    signal_confluence: "联动",
    risk_exit: "风险",
  };
  return labels[source];
}

export function buildCycleRotationPanelSummary(input: {
  framework: NonNullable<LivermoreStrategyPayload["cycle_rotation_framework"]>;
  macroLayer: StockCycleMacroLayerSummary | null;
  portfolioBacktest: LivermoreCandidateHistoryPortfolioBacktestPayload | null;
  proxyBacktest: LivermoreCycleProxyBacktestPayload | null;
  portfolioQueryState?: StockStrategyPanelQueryState;
  proxyQueryState?: StockStrategyPanelQueryState;
}): StockStrategyPanelResultSummary {
  const readyLayers = input.framework.layers.filter((layer) => layer.status === "ready").length;
  const totalLayers = input.framework.layers.length;
  const stageLabel = localizeImplementationStage(input.framework.implementation_stage);
  const proxyReturn =
    input.proxyBacktest?.status === "proxy" ? input.proxyBacktest.summary?.cumulative_return : null;
  const portfolioReturn =
    input.portfolioBacktest?.status === "portfolio_proxy"
      ? input.portfolioBacktest.summary?.cumulative_return
      : null;
  const backtestLoading =
    input.portfolioQueryState === "loading" || input.proxyQueryState === "loading";

  const stats: StockStrategyPanelMiniStat[] = [
    {
      key: "stage",
      label: "阶段",
      value: stageLabel,
      valueTone: input.framework.implementation_stage.includes("proxy") ? "warning" : "emphasis",
    },
    {
      key: "layers",
      label: "就绪",
      value: `${readyLayers}/${totalLayers}`,
      valueTone: readyLayers === totalLayers ? "emphasis" : "warning",
    },
  ];
  if (input.macroLayer) {
    stats.push({
      key: "macro",
      label: "宏观",
      value: input.macroLayer.macroScoreLabel,
      valueTone: input.macroLayer.tone === "positive" ? "emphasis" : "warning",
    });
  }
  if (!backtestLoading && portfolioReturn != null) {
    stats.push({
      key: "portfolio",
      label: "组合",
      value: formatBacktestSignedReturn(portfolioReturn),
      valueTone: portfolioReturn >= 0 ? "up" : "down",
    });
  } else if (!backtestLoading && proxyReturn != null) {
    stats.push({
      key: "proxy",
      label: "代理",
      value: formatBacktestSignedReturn(proxyReturn),
      valueTone: proxyReturn >= 0 ? "up" : "down",
    });
  } else if (!backtestLoading) {
    stats.push({ key: "backtest", label: "回测", value: "无样本", valueTone: "warning" });
  }

  const macroStatus = input.macroLayer?.statusLabel ?? "待补";
  const headline =
    macroStatus === "已落地" ? "宏观层已落地" : macroStatus === "部分就绪" ? "宏观层部分就绪" : "宏观层待补";
  const detail =
    readyLayers < totalLayers
      ? `就绪 ${readyLayers}/${totalLayers} 层；补齐缺失输入后可进入完整验证。`
      : backtestLoading
        ? "回测加载中，展开查看公式、层状态与回测明细。"
        : "各层只读证据已接入，展开查看公式、层状态与回测明细。";

  return {
    headline,
    detail,
    complianceDetail: input.framework.observation_only
      ? "研究观察口径：只读证据已接入；缺失输入补齐前，不生成收益、仓位或执行结论。"
      : "策略口径已接入；仍需结合回测和风险边界复核。",
    badgeLabel: stageLabel,
    stats,
    tone: input.macroLayer?.tone ?? "neutral",
  };
}

export function buildThemeBreakoutPanelSummary(input: {
  payload: LivermoreStrategyPayload;
  cards: StockThemeBreakoutCard[];
  reviewCount: number;
  unsupportedReason?: string;
}): StockStrategyPanelResultSummary {
  const themePayload = input.payload.theme_breakout;
  const isProxy = themePayload?.is_proxy ?? true;
  const movementTotal = summarizeThemeMovementCount(input.payload);
  const topCard = input.cards[0];
  const coverageCount = themePayload?.items?.length ?? input.cards.length;

  if (input.unsupportedReason) {
    const localized = localizeThemeUnsupportedSummary(input.unsupportedReason);
    return {
      headline: "题材雷达未开放",
      detail: localized.detail,
      complianceDetail: localized.detail,
      badgeLabel: "暂停",
      stats: [{ key: "status", label: "状态", value: "未开放", valueTone: "warning" }],
      tone: "warning",
    };
  }

  const stats: StockStrategyPanelMiniStat[] = [
    {
      key: "coverage",
      label: "覆盖",
      value: `${coverageCount} 簇`,
      valueTone: coverageCount > 0 ? "emphasis" : "flat",
    },
    {
      key: "movement",
      label: "异动",
      value: `${movementTotal} 条`,
      valueTone: movementTotal > 0 ? "warning" : "flat",
    },
  ];
  if (input.reviewCount > 0) {
    stats.push({
      key: "review",
      label: "未入选",
      value: `${input.reviewCount} 项`,
      valueTone: "warning",
    });
  }
  stats.push({
    key: "mode",
    label: "模式",
    value: isProxy ? "代理" : "概念",
    valueTone: isProxy ? "warning" : "emphasis",
  });

  const headline =
    input.cards.length > 0
      ? `#${topCard?.rank ?? 1} ${topCard?.themeName ?? "题材"}领先`
      : "暂无题材突变项";

  return {
    headline,
    detail:
      input.cards.length > 0
        ? (topCard?.summary ?? "展开查看簇内龙头与边界说明。")
        : isProxy
          ? "代理观察：日线+涨停+名称簇，非正式概念库。"
          : "真实概念观察：已落地成分与异动，仍只读复核。",
    complianceDetail: isProxy ? "代理题材口径：日线、涨停与名称簇观察；不是正式概念库。" : undefined,
    badgeLabel: input.cards.length > 0 ? "已就绪" : isProxy ? "代理观察" : "概念库",
    stats,
    tone: input.cards.length > 0 ? "positive" : "neutral",
  };
}

export function buildConsensusReviewPanelSummary(consensus: ConsensusSummary): StockStrategyPanelResultSummary {
  if (!consensus.hasAnyStrategy) {
    return {
      headline: "暂无候选",
      detail: "今天没有共振候选；先核对门控，再下翻看多因子池或各策略观察池。",
      badgeLabel: "待补",
      stats: [{ key: "sample", label: "共振", value: "0", valueTone: "warning" }],
      tone: "warning",
    };
  }
  if (consensus.doubleCount <= 0) {
    return {
      headline: "暂无 T+5 共振",
      detail: "今天没有趋势+多因子共振；可先复核单策略池，或查看多因子池排序。",
      badgeLabel: "待复核",
      stats: [
        { key: "trend", label: "趋势", value: `${consensus.strategyCounts.livermore}`, valueTone: "emphasis" },
        { key: "factor", label: "多因子", value: `${consensus.strategyCounts.factor_screen}`, valueTone: "emphasis" },
        { key: "union", label: "去重", value: `${consensus.totalUnion}`, valueTone: "flat" },
      ],
      tone: "warning",
    };
  }

  const top = consensus.items[0];
  return {
    headline: `T+5 共振 ${consensus.doubleCount} 只`,
    detail: top
      ? `下一步：优先复核 ${top.stockName}（${top.stockCode}），${top.strategies.length} 策略同选。`
      : "按共振得分排序，仅作复核先后。",
    badgeLabel: "已就绪",
    stats: [
      {
        key: "double",
        label: "共振",
        value: `${consensus.doubleCount}`,
        valueTone: "emphasis",
      },
      {
        key: "factor",
        label: "多因子",
        value: `${consensus.strategyCounts.factor_screen}`,
        valueTone: "flat",
      },
      {
        key: "trend",
        label: "趋势",
        value: `${consensus.strategyCounts.livermore}`,
        valueTone: "flat",
      },
    ],
    tone: "positive",
  };
}

export function localizeStrategyPanelErrorDetail(errorMessage: string | null | undefined): string {
  const value = errorMessage?.trim();
  if (!value) return "请求失败：错误详情待补。";
  const lower = value.toLowerCase();
  if (lower.includes("source_table") || lower.includes("source table")) {
    return "请求失败：必需数据源缺失，稍后复核供数状态。";
  }
  if (lower.includes("failed to fetch") || lower.includes("network error")) {
    return "请求失败：暂时无法连接策略分析服务。";
  }
  return `请求失败：${localizeStockBackendText(value)}。`;
}

export function buildMarketPriorityPanelSummary(input: {
  rows: LivermoreStrategyScorePayload["rows"];
  payload: LivermoreStrategyScorePayload | null;
  marketState: string | null;
  queryState: StockStrategyPanelQueryState;
  errorMessage?: string;
}): StockStrategyPanelResultSummary {
  if (input.queryState === "loading") {
    return {
      headline: "加载中…",
      loading: true,
      badgeLabel: "加载中",
      stats: [],
      tone: "neutral",
    };
  }
  if (input.queryState === "error") {
    return {
      headline: "优先级暂不可用",
      detail: localizeStrategyPanelErrorDetail(input.errorMessage),
      badgeLabel: "待补",
      stats: [],
      tone: "warning",
    };
  }
  const top = pickTopPriorityRow(input.rows);
  const sufficientCount = input.rows.filter((row) => row.sample_status === "sufficient").length;
  if (!top || sufficientCount === 0) {
    return {
      headline: "样本不足",
      detail: `阈值 ${input.payload?.min_sample ?? 30} · 只读排序`,
      badgeLabel: "待补",
      stats: [{ key: "rows", label: "策略", value: `${input.rows.length}`, tone: "neutral" }],
      tone: "warning",
    };
  }

  const horizon = input.payload?.primary_horizon ?? "return_5d";
  const horizonStats = top.stats[horizon];
  const status = strategyPrioritySummaryStatus(top.priority_label);
  return {
    headline: `${status.label} · ${localizeStockStrategyLabel(top.strategy_label, top.signal_kind)}`,
    detail: localizeStockBackendText(top.reason, top.signal_kind),
    badgeLabel: status.badgeLabel,
    stats: [
      {
        key: "score",
        label: "评分",
        value: top.priority_score?.toFixed(1) ?? "-",
        tone: status.tone,
      },
      {
        key: "t5",
        label: "T+5",
        value: formatBacktestHorizonStatsText(horizonStats),
        tone: (horizonStats?.win_rate ?? 0) >= 0.5 ? "positive" : "neutral",
      },
    ],
    tone: status.tone,
  };
}

export function buildStrategyBacktestPanelSummary(input: {
  payload: LivermoreCandidateHistoryPayload | null;
  sampleCount: number;
  window: BacktestWindowSummary | null;
  dateRangeLabel: string;
  rows: Array<{ kind: string; label: string; count: number; stats: Record<string, string> }>;
  queryState: StockStrategyPanelQueryState;
  errorMessage?: string;
}): StockStrategyPanelResultSummary {
  if (input.queryState === "loading") {
    return {
      headline: "加载中…",
      loading: true,
      badgeLabel: "加载中",
      stats: [],
      tone: "neutral",
    };
  }
  if (input.queryState === "error") {
    return {
      headline: "回溯暂不可用",
      detail: localizeStrategyPanelErrorDetail(input.errorMessage),
      badgeLabel: "待补",
      stats: [],
      tone: "warning",
    };
  }
  const topRow = [...input.rows].sort((left, right) => right.count - left.count)[0];
  const signalStats =
    input.payload?.summary?.by_signal_kind_horizon_usable_stats?.stock_candidate?.return_5d ??
    input.payload?.summary?.by_signal_kind_horizon_stats?.stock_candidate?.return_5d;
  const trendT5 =
    signalStats != null
      ? formatBacktestHorizonStatsText(signalStats)
      : topRow?.stats.return_5d ?? "样本待补";

  return {
    headline: input.sampleCount > 0 ? `有效样本 ${input.sampleCount} 条` : "暂无回溯样本",
    detail: input.dateRangeLabel,
    badgeLabel: input.sampleCount > 0 ? "已就绪" : "待补",
    stats: [
      {
        key: "trend",
        label: topRow?.label ?? "趋势",
        value: trendT5,
        tone: input.sampleCount > 0 ? "positive" : "warning",
      },
      {
        key: "pending",
        label: "待成熟",
        value: `${input.window?.replay_dates_pending ?? 0} 日`,
        tone: (input.window?.replay_dates_pending ?? 0) > 0 ? "warning" : "neutral",
      },
      {
        key: "range",
        label: "区间",
        value: input.dateRangeLabel || "待补",
        tone: "neutral",
      },
    ],
    tone: input.sampleCount > 0 ? "positive" : "warning",
  };
}

export function buildStrategyOptimizationPanelSummary(input: {
  payload: LivermoreStrategyOptimizationPayload | null;
  rows: LivermoreStrategyOptimizationPayload["strategy_summaries"];
  queryState: StockStrategyPanelQueryState;
  errorMessage?: string;
}): StockStrategyPanelResultSummary {
  if (input.queryState === "loading") {
    return {
      headline: "加载中…",
      loading: true,
      badgeLabel: "加载中",
      stats: [],
      tone: "neutral",
    };
  }
  if (input.queryState === "error") {
    return {
      headline: "优化诊断暂不可用",
      detail: localizeStrategyPanelErrorDetail(input.errorMessage),
      badgeLabel: "待补",
      stats: [],
      tone: "warning",
    };
  }

  const promoteCount = (input.payload?.recommendations ?? []).filter(
    (item) => item.action === "promote" || item.priority_label === "优先复核",
  ).length;
  const downgradeCount = (input.payload?.recommendations ?? []).filter(
    (item) => item.action === "downgrade" || item.priority_label === "降权观察",
  ).length;
  const top = input.rows[0];
  const horizon = input.payload?.primary_horizon ?? "return_5d";
  const primaryStats = top?.stats[horizon];

  if (!top) {
    return {
      headline: "优化样本不足",
      detail: input.payload?.pending_summary.message
        ? localizeStockBackendText(input.payload.pending_summary.message)
        : undefined,
      badgeLabel: "待补",
      stats: [
        {
          key: "pending",
          label: "待成熟",
          value: `${input.payload?.pending_summary.pending_rows ?? 0} 行`,
          tone: "warning",
        },
      ],
      tone: "warning",
    };
  }

  const status = strategyPrioritySummaryStatus(top.recommendation.priority_label);
  return {
    headline: `${status.label} · ${localizeStockStrategyLabel(top.strategy_label, top.signal_kind)}`,
    detail: localizeStockBackendText(top.recommendation.reason, top.signal_kind),
    badgeLabel: status.badgeLabel,
    stats: [
      {
        key: "promote",
        label: "上调",
        value: `${promoteCount}`,
        tone: promoteCount > 0 ? "positive" : "neutral",
      },
      {
        key: "downgrade",
        label: "降权",
        value: `${downgradeCount}`,
        tone: downgradeCount > 0 ? "warning" : "neutral",
      },
      {
        key: "t5",
        label: "T+5",
        value: formatBacktestHorizonStatsText(primaryStats),
        tone: "neutral",
      },
    ],
    tone: status.tone,
  };
}

export function buildObservationPoolsPanelSummary(input: {
  gateState: string | null | undefined;
  meanReversionCount: number;
  factorScreenCount: number;
  hybridFusionCount: number;
  meanReversionActive: boolean;
}): StockStrategyPanelResultSummary {
  const total = input.meanReversionCount + input.factorScreenCount + input.hybridFusionCount;
  const primaryCount = input.factorScreenCount > 0 ? input.factorScreenCount : input.hybridFusionCount;
  const primaryLabel = input.factorScreenCount > 0 ? "多因子" : input.hybridFusionCount > 0 ? "融合" : "观察池";

  const headline =
    primaryCount > 0
      ? `${primaryLabel} ${primaryCount} 只待复核`
      : total > 0
        ? `观察池合计 ${total} 只`
        : "观察池暂无候选";

  return {
    headline,
    detail:
      input.meanReversionActive && input.gateState === "WARM"
        ? "条件触发超跌反弹；融合/超跌明细见展开区。"
        : "融合/超跌明细见展开区。",
    badgeLabel: total > 0 ? "已就绪" : "待补",
    stats: [
      {
        key: "factor",
        label: "多因子",
        value: `${input.factorScreenCount}`,
        tone: input.factorScreenCount > 0 ? "positive" : "neutral",
      },
      {
        key: "mean",
        label: "超跌",
        value: input.meanReversionActive ? `${input.meanReversionCount}` : "暂停",
        tone: input.meanReversionActive ? "warning" : "neutral",
      },
      {
        key: "hybrid",
        label: "融合",
        value: `${input.hybridFusionCount}`,
        tone: input.hybridFusionCount > 0 ? "positive" : "neutral",
      },
    ],
    tone: total > 0 ? "positive" : "neutral",
  };
}

export function buildEventsMonitoringPanelSummary(
  rows: StockAnalysisEventMonitorRow[],
): StockStrategyPanelResultSummary {
  if (rows.length === 0) {
    return {
      headline: "暂无待复核事件",
      detail: "诊断、缺口与风险触发均空。",
      badgeLabel: "已就绪",
      stats: [{ key: "count", label: "事件", value: "0", tone: "positive" }],
      tone: "positive",
    };
  }

  const errorCount = rows.filter((row) => row.level === "error").length;
  const warningCount = rows.filter((row) => row.level === "warning").length;
  const top = [...rows].sort((left, right) => eventMonitorPriority(right) - eventMonitorPriority(left))[0];

  return {
    headline: `${rows.length} 条待复核`,
    detail: `最高优先：${eventMonitorSourceLabel(top.source)} / ${localizeStockDataFamily(top.impact)}`,
    badgeLabel: errorCount > 0 ? "待补" : warningCount > 0 ? "待复核" : "已就绪",
    stats: [
      { key: "error", label: "错误", value: `${errorCount}`, tone: errorCount > 0 ? "negative" : "positive" },
      { key: "warn", label: "预警", value: `${warningCount}`, tone: warningCount > 0 ? "warning" : "neutral" },
      { key: "top", label: "来源", value: eventMonitorSourceLabel(top.source), tone: "neutral" },
    ],
    tone: errorCount > 0 ? "negative" : warningCount > 0 ? "warning" : "neutral",
  };
}
