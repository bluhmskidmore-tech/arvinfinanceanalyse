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
  LivermoreStockCandidateItem,
  LivermoreStrategyOptimizationPayload,
  LivermoreStrategyPayload,
  LivermoreStrategyScorePayload,
  HybridFusionCandidateItem,
  LivermoreThemeBreakoutReviewItem,
  LivermoreThemeEvidenceInputState,
  LivermoreThemeBreakoutItem,
  ResultMeta,
} from "../../../api/contracts";
import type { ConsensusSummary } from "./buildConsensusSummary";

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

function buildCandidateFundamentalEvidence(item: LivermoreStockCandidateItem): StockCandidateEvidenceBullet[] {
  const bullets: StockCandidateEvidenceBullet[] = [];
  const factorScore = finiteNumber(item.factor_score);
  const factorRank = finiteNumber(item.factor_overlay_rank);
  if (factorScore != null || factorRank != null) {
    bullets.push({
      key: "fundamental_overlay",
      label: "基本面 overlay",
      value: [
        factorScore != null ? `因子分 ${formatNumber(factorScore, 4)}` : null,
        factorRank != null ? `overlay #${factorRank.toFixed(0)}` : null,
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
    return "基本面 overlay 已接入候选排序，但财报口径、最新公告和一致预期仍需复核。";
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

function sortedCandidateItems(payload: LivermoreStrategyPayload) {
  return [...(payload.stock_candidates?.items ?? [])].sort((left, right) => left.rank - right.rank);
}

function sortedHybridFusionItems(payload: LivermoreStrategyPayload) {
  return [...(payload.hybrid_fusion_candidates?.items ?? [])].sort((left, right) => left.rank - right.rank);
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
  if (value === "high") return "高";
  if (value === "medium") return "中";
  if (value === "low") return "低";
  return value?.trim() || "待补";
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
        label: "生命法庭代理",
        value: formatNumber(item.lifecourt_proxy_score, 4),
      },
      { key: "attention_score", label: "关注代理", value: formatNumber(item.attention_score, 4) },
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
        value: item.fusion_action?.trim() || "待补",
      },
      { key: "confidence", label: "置信度", value: fusionConfidenceLabel(item.confidence) },
      { key: "formula_version", label: "公式版本", value: formula },
    ];
    const sourceKinds = Array.isArray(item.evidence?.source_kinds)
      ? item.evidence.source_kinds.map((value) => String(value)).join(" / ")
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
        "生命法庭层为代理信号，未接入真实大V文本、OCR/ASR或社交情绪生产线。",
        "仅作观察与复核，不生成实盘订单或仓位建议。",
        `来源命中：${sourceKinds}`,
      ],
      invalidationRules: [
        "市场状态离开 WARM/HOT、题材/趋势/因子来源失效或拥挤惩罚上升时，需要降级复核。",
        "数据质量为 stale / missing 时，不得解释为有效观察。",
      ],
      rawFields: [
        { key: "fusion_score", label: "fusion_score", value: formatNumber(item.fusion_score, 6) },
        { key: "cycle_score", label: "cycle_score", value: formatNumber(item.cycle_score, 6) },
        {
          key: "lifecourt_proxy_score",
          label: "lifecourt_proxy_score",
          value: formatNumber(item.lifecourt_proxy_score, 6),
        },
        { key: "attention_score", label: "attention_score", value: formatNumber(item.attention_score, 6) },
        {
          key: "price_confirm_score",
          label: "price_confirm_score",
          value: formatNumber(item.price_confirm_score, 6),
        },
        { key: "crowding_penalty", label: "crowding_penalty", value: formatNumber(item.crowding_penalty, 6) },
        { key: "confidence", label: "confidence", value: item.confidence },
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
  const fallback = meta.fallback_mode && meta.fallback_mode !== "none" ? ` / 回退 ${meta.fallback_mode}` : "";
  return `新鲜度 ${quality} / ${vendor}${fallback}`;
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
    ok: "通道正常",
    degraded: "通道降级",
    error: "通道异常",
    pending: "通道待确认",
  };
  return labels[normalized] ?? "通道待确认";
}

function localizeBasisLabel(basis: string | null | undefined): string {
  const normalized = (basis ?? "").trim().toLowerCase();
  if (normalized === "analytical") return "分析口径（非交易）";
  if (normalized === "formal") return "正式口径";
  if (!normalized) return "口径待补";
  return `口径 ${basis}`;
}

export type StockAnalysisPagePurpose = {
  eyebrow: string;
  title: string;
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
  const asOf = payload.as_of_date ?? "待补";
  return {
    eyebrow: "Livermore 策略 · 只读复核台",
    title: "股票策略复核台",
    asOfLine: `观察日 ${asOf}`,
    dataStatusLine: aligned
      ? `数据状态：已对齐（${asOf}）`
      : `数据状态：待复核 · ${localizeMetaQualityFlag(quality)} / ${localizeMetaVendorStatus(vendor)}${
          fallback !== "none" ? ` / 回退 ${fallback}` : ""
        }`,
  };
}

export type StockReviewQueueEmptyState = {
  headline: string;
  detail: string;
};

export function buildReviewQueueEmptyState(payload: LivermoreStrategyPayload): StockReviewQueueEmptyState {
  const factorCount = payload.factor_screen_candidates?.candidate_count ?? 0;
  const hybridCount = payload.hybrid_fusion_candidates?.candidate_count ?? 0;
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
    { key: "as_of", text: payload.as_of_date ?? "待补日期" },
    { key: "source_version", text: extras.source_version ?? "待补" },
    { key: "rule_version", text: extras.rule_version ?? "待补" },
    { key: "quality_flag", text: extras.quality_flag ?? "待补" },
    { key: "vendor_status", text: extras.vendor_status ?? "待补" },
    { key: "fallback_mode", text: extras.fallback_mode ?? "待补" },
  ];
  return out;
}

function countBoundaryItems(payload: LivermoreStrategyPayload): number {
  return (
    payload.diagnostics.filter((item) => item.severity !== "info").length +
    payload.data_gaps.filter((gap) => gap.status !== "ready").length +
    payload.unsupported_outputs.length
  );
}

const MACRO_GAP_FAMILIES = new Set(["pmi", "credit_impulse", "macro_score", "price_spread"]);

function isMacroGapFamily(inputFamily: string): boolean {
  return MACRO_GAP_FAMILIES.has(inputFamily.trim().toLowerCase());
}

function macroGapLabels(payload: LivermoreStrategyPayload): string[] {
  return payload.data_gaps
    .filter((gap) => gap.status !== "ready" && isMacroGapFamily(gap.input_family))
    .map((gap) => `${gap.input_family} (${gap.status})`);
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
    `可用 ${availableInputs.join(", ") || "-"}`,
    `缺失 ${missingInputs.join(", ") || "-"}`,
  ];
  if (macroGapLabelsList.length > 0) {
    detailParts.push(`gaps ${macroGapLabelsList.join(" / ")}`);
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
  const diagnostics = payload.diagnostics.filter((item) => item.severity !== "info");
  const dataGaps = payload.data_gaps.filter((gap) => gap.status !== "ready");
  const unsupported = payload.unsupported_outputs;
  const topMessages = [
    ...diagnostics.map((item) => item.message),
    ...dataGaps.map((gap) => `${gap.input_family} ${gap.status}: ${gap.evidence}`),
    ...unsupported.map((item) => `${item.key}: ${item.reason}`),
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
    detailLabel: `诊断 ${diagnostics.length} / 缺口 ${dataGaps.length} / 未支持 ${unsupported.length} / ${freshnessLabel}`,
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
      value: payload.market_gate.state,
      detail: `观察暴露 ${formatRatioAsPercent(payload.market_gate.exposure)}`,
      tone: hasBoundary ? "warning" : "positive",
    },
    {
      key: "review-queue",
      label: "复核队列",
      value: String(queue.length),
      detail: queue[0] ? `优先 ${queue[0].stockName} / ${queue[0].sectorName}` : "候选待补",
      tone: queue.length > 0 ? "positive" : "neutral",
    },
    {
      key: "sector-strength",
      label: "板块强弱",
      value: strongest ? strongest.sectorName : "待补",
      detail: weakest ? `弱侧 ${weakest.sectorName} / ${weakest.pctChange}` : "弱侧待补",
      tone: strongest ? "positive" : "warning",
    },
    {
      key: "risk-observation",
      label: "风险观察",
      value: String(riskRows.length),
      detail: `触发 ${riskTriggered} / 观察 ${riskWatch}`,
      tone: riskTriggered > 0 ? "negative" : riskWatch > 0 ? "warning" : "positive",
    },
    {
      key: "closed-loop",
      label: "闭环状态",
      value: closedLoopSummary.referenceRating.label,
      detail: closedLoopSummary.summaryLabel,
      tone: closedLoopSummary.referenceRating.tone,
    },
    {
      key: "data-boundary",
      label: "数据边界",
      value: String(boundarySummary.boundaryCount),
      detail: boundarySummary.detailLabel,
      tone: boundarySummary.boundaryCount > 0 || isMetaBoundary(meta) ? "warning" : "positive",
    },
  ];
}

export type StockStrategyLensItem = {
  key: string;
  label: string;
  value: string;
  detail: string;
  tone: "positive" | "warning" | "negative" | "neutral";
  scrollTarget: string;
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
    factor_screen: "多因子",
    hybrid_fusion: "融合策略",
    mean_reversion: "超跌反弹",
    review_queue: "复核队列",
    sector_constituent: "板块成分",
  };
  return labels[source] ?? source;
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
  consensus: ConsensusSummary,
): StockStrategyLensItem[] {
  const reviewCount = buildCandidateReviewQueue(payload).length;
  const resonanceCount = consensus.items.filter((item) => item.consensusCount >= 2).length;
  const themeCards = buildThemeBreakoutCards(payload);
  const themeLeaderCount = buildThemeLeaderPreviewItems(themeCards).length;
  const sectorHeavyweightPreview = buildSectorHeavyweightPreview(payload);

  return [
    {
      key: "review",
      label: "复核队列",
      value: String(reviewCount),
      detail: reviewCount > 0 ? "优先人工复核" : "暂无主候选",
      tone: reviewCount > 0 ? "positive" : "warning",
      scrollTarget: "stock-analysis-review-queue",
    },
    {
      key: "resonance",
      label: "策略共振",
      value: String(resonanceCount),
      detail: consensus.tripleCount > 0 ? `${consensus.tripleCount} 只三重共振` : "双策略及以上",
      tone: resonanceCount > 0 ? "positive" : "neutral",
      scrollTarget: "stock-analysis-consensus-first-screen",
    },
    {
      key: "hybrid",
      label: "融合策略",
      value: String(consensus.strategyCounts.hybrid_fusion),
      detail: "观察池",
      tone: consensus.strategyCounts.hybrid_fusion > 0 ? "positive" : "neutral",
      scrollTarget: "stock-analysis-observation-preview",
    },
    {
      key: "livermore",
      label: "趋势突破",
      value: String(consensus.strategyCounts.livermore),
      detail: "Livermore",
      tone: consensus.strategyCounts.livermore > 0 ? "positive" : "neutral",
      scrollTarget: "stock-analysis-observation-preview",
    },
    {
      key: "factor",
      label: "多因子",
      value: String(consensus.strategyCounts.factor_screen),
      detail: "因子池",
      tone: consensus.strategyCounts.factor_screen > 0 ? "positive" : "neutral",
      scrollTarget: "stock-analysis-observation-preview",
    },
    {
      key: "mean_reversion",
      label: "超跌反弹",
      value: String(consensus.strategyCounts.mean_reversion),
      detail: payload.market_gate.state === "WARM" ? "WARM 激活" : "门控暂停",
      tone:
        payload.market_gate.state === "WARM" && consensus.strategyCounts.mean_reversion > 0
          ? "positive"
          : "neutral",
      scrollTarget: "stock-analysis-observation-preview",
    },
    {
      key: "theme",
      label: "题材龙头",
      value: String(themeLeaderCount),
      detail: `${themeCards.length} 个题材簇`,
      tone: themeCards.length > 0 ? "positive" : "neutral",
      scrollTarget: "stock-analysis-theme-leaders-first-screen",
    },
    {
      key: "sector_heavyweight",
      label: "板块权重",
      value: String(sectorHeavyweightPreview.totalSampleCount),
      detail: `${sectorHeavyweightPreview.sectorsWithSamples} 个板块有样本`,
      tone: sectorHeavyweightPreview.totalSampleCount > 0 ? "positive" : "neutral",
      scrollTarget: "stock-analysis-sector-heavyweights-first-screen",
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
  const lineageLabel = meta.source_version ?? "待补";
  const ruleVersion =
    meta.rule_version ??
    payload.hybrid_fusion_candidates?.formula_version ??
    payload.sector_rank?.formula_version ??
    payload.stock_candidates?.formula_version ??
    payload.risk_exit?.formula_version ??
    "待补";

  return [
    {
      key: "as-of-date",
      label: "数据日期",
      statusLabel: payload.as_of_date ?? "待补",
      tone: payload.as_of_date ? "positive" : "warning",
      detail: payload.requested_as_of_date ? `请求日期 ${payload.requested_as_of_date}` : "使用接口返回日期",
    },
    {
      key: "lineage",
      label: "来源版本",
      statusLabel: lineageLabel,
      tone: lineageLabel === "待补" ? "warning" : "positive",
      detail: meta.trace_id ? `trace ${meta.trace_id}` : "trace 待补",
    },
    {
      key: "basis",
      label: "计算口径",
      statusLabel: payload.basis ?? "待补",
      tone: evidenceToneForStatus(payload.basis ?? "pending"),
      detail: payload.strategy_name,
    },
    {
      key: "rule-version",
      label: "规则版本",
      statusLabel: ruleVersion,
      tone: ruleVersion === "待补" ? "warning" : "positive",
      detail: `supported ${payload.supported_outputs.length} / unsupported ${payload.unsupported_outputs.length}`,
    },
    {
      key: "quality",
      label: "数据质量",
      statusLabel: qualityTone === "positive" ? "正常" : "需复核",
      tone: qualityTone,
      detail: `${quality} / ${vendor}${fallback !== "none" ? ` / fallback ${fallback}` : ""}`,
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
      detail: item.message,
    });
  }

  for (const gap of payload.data_gaps.filter((item) => item.status !== "ready")) {
    rows.push({
      key: `data_gap:${gap.input_family}:${gap.status}`,
      source: "data_gap",
      level: gap.status === "stale" ? "warning" : "error",
      event: gap.status,
      impact: gap.input_family,
      detail: gap.evidence,
    });
  }

  for (const item of payload.unsupported_outputs) {
    rows.push({
      key: `unsupported:${item.key}`,
      source: "unsupported",
      level: "warning",
      event: `${item.key}: ${item.reason}`,
      impact: item.key,
      detail: item.reason,
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
      detail: row.message,
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
      sectorLabel: "all sectors",
      isFiltered: false,
      visibleCount: totalCount,
      totalCount,
      summaryLabel: `sector all sectors / showing ${totalCount} of ${totalCount}`,
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
    summaryLabel: `sector ${sectorName} (${sectorFilterSectorCode}) / showing ${visibleCount} of ${totalCount}`,
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
      themeName: item.theme_name,
      parentSectorLabel: `${item.parent_sector_name} #${item.parent_sector_rank}`,
      summary: `${item.member_count} 只观察股，${item.strong_stock_count} 只强势，${item.limit_stock_count} 只涨停。`,
      reason: item.reason,
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
  concept_membership: "Concept membership",
  intraday_movement: "Intraday movement",
};

const themeEvidenceStatusLabels: Record<string, string> = {
  catalog_unconfirmed: "catalog unconfirmed",
  table_missing: "table missing",
  landed_no_rows: "landed no rows",
  matched_rows: "matched rows",
};

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
    const tableText = row.table ?? row.table_name ? ` / ${row.table ?? row.table_name}` : "";
    return {
      key: inputFamily,
      label: themeEvidenceInputLabels[inputFamily] ?? inputFamily,
      status,
      statusLabel: themeEvidenceStatusLabels[status] ?? status,
      detail: row.message?.trim() || `${inputFamily}${tableText} status ${status}.`,
      rowCountLabel: `rows ${rowCount} / matched ${matchedCount}`,
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
        themeName: item.theme_name,
        sourceKindLabel: localizeThemeSourceKind(
          item.source_kind,
          payload.theme_breakout?.is_proxy ?? true,
        ),
        parentSectorLabel: `${item.parent_sector_name} #${item.parent_sector_rank}`,
        summary: `${item.member_count} review rows, ${item.strong_stock_count} strong, ${
          item.limit_stock_count
        } limit-up, avg ${formatPercent(item.avg_pctchange)}`,
        failedGateLabel:
          failedGates.length > 0 ? `未过门槛：${failedGates.join("、")}` : "门槛待确认",
        reason: item.reason,
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
  const fallbackLabel = isFallback ? ` / 回退 ${fallbackMode}` : "";
  const dataFreshnessOk = qualityFlag === "ok" && vendorStatus === "ok" && !isFallback;
  const candidateCount =
    payload.hybrid_fusion_candidates?.candidate_count ??
    payload.stock_candidates?.candidate_count ??
    queue.length;
  const boundaryCount = countBoundaryItems(payload);

  return {
    headline: strip.headline,
    gateLabel: strip.gateChip,
    exposureLabel: `观察暴露 ${formatRatioAsPercent(payload.market_gate.exposure)}`,
    strongestSectorLabel: strip.strongestSectorChip,
    weakestSectorLabel: strip.weakestSectorChip,
    candidateCountLabel: `候选 ${candidateCount}`,
    dataFreshnessLabel: `${dataFreshnessOk ? "数据正常" : "数据需复核"} ${qualityFlag} / ${vendorStatus}${fallbackLabel}`,
    boundaryLabel: boundaryCount > 0 ? `${boundaryCount} 条边界` : "边界清晰",
    nextReviewAction: firstReview
      ? `下一步：先复核 ${firstReview.stockName}（${firstReview.stockCode}），${firstReview.sectorName}，距观察位 ${firstReview.distanceToBreakoutPct}。`
      : buildReviewQueueEmptyState(payload).detail,
    basisLabel: localizeBasisLabel(payload.basis),
    asOfLabel: payload.as_of_date ?? "待补日期",
  };
}

/** @deprecated Stage 1.5 — 已由 inline meta + Drawer 替代正文列表；保留给需要纯文本的诊断导出 */
export function buildDataBoundaryNotes(payload: LivermoreStrategyPayload): string[] {
  const notes = [`basis: ${payload.basis}`, `strategy: ${payload.strategy_name}`];
  for (const diag of payload.diagnostics) {
    notes.push(`${diag.severity} [${diag.code}]: ${diag.message}`);
  }
  if (payload.as_of_date) {
    notes.push(`as_of_date: ${payload.as_of_date}`);
  }
  if (payload.sector_rank?.formula_version) {
    notes.push(`sector_rank formula: ${payload.sector_rank.formula_version}`);
  }
  if (payload.stock_candidates?.formula_version) {
    notes.push(`stock_candidates formula: ${payload.stock_candidates.formula_version}`);
  }
  if (payload.hybrid_fusion_candidates?.formula_version) {
    notes.push(`hybrid_fusion formula: ${payload.hybrid_fusion_candidates.formula_version}`);
  }
  if (payload.risk_exit?.formula_version) {
    notes.push(`risk_exit formula: ${payload.risk_exit.formula_version}`);
  }
  for (const gap of payload.data_gaps) {
    notes.push(`${gap.input_family} ${gap.status}: ${gap.evidence}`);
  }
  for (const output of payload.unsupported_outputs) {
    notes.push(`${output.key} unsupported: ${output.reason}`);
  }
  notes.push(`supported_outputs: ${payload.supported_outputs.join(", ") || "none"}`);
  return notes;
}

export function buildMarketStateCard(
  payload: LivermoreStrategyPayload,
): StockMarketStateCard {
  const gate = payload.market_gate;
  const warnings = [
    ...payload.diagnostics
      .filter((item) => item.severity !== "info")
      .map((item) => item.message),
    ...payload.data_gaps
      .filter((gap) => gap.status !== "ready")
      .map((gap) => `${gap.input_family} ${gap.status}: ${gap.evidence}`),
  ];

  return {
    title: "市场状态",
    state: gate.state,
    exposureLabel: formatRatioAsPercent(gate.exposure),
    passedLabel: `${gate.passed_conditions} / ${gate.required_conditions} 条件通过`,
    basisLabel: `basis: ${payload.basis}`,
    warnings,
    conditions: gate.conditions.map((condition) => ({
      key: condition.key,
      label: condition.label,
      status: condition.status,
      evidence: condition.evidence,
    })),
  };
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

export function buildSectorViewModel(
  payload: LivermoreStrategyPayload,
  view: StockSectorViewKind,
): StockSectorViewRow[] {
  const rows = buildSectorRows(payload);
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
  const hybridCards = buildHybridFusionEvidenceCards(payload);
  if (hybridCards.length > 0) return hybridCards;

  return sortedCandidateItems(payload).map((item) => {
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
        "涨跌停状态、停牌状态或数据质量为 stale / missing 时，不得继续解释为有效观察。",
      ],
      rawFields: [
        { key: "ema10", label: "ema10", value: formatNumber(item.ema10) },
        { key: "ma20", label: "ma20", value: formatNumber(item.ma20) },
        { key: "ma60", label: "ma60", value: formatNumber(item.ma60) },
        { key: "ma120", label: "ma120", value: formatNumber(item.ma120) },
        { key: "abnormal_turnover", label: "abnormal_turnover", value: formatNumber(item.abnormal_turnover, 4) },
        { key: "gap_norm", label: "gap_norm", value: item.gap_norm != null ? String(item.gap_norm) : "待补" },
        {
          key: "breakout_extension_norm",
          label: "breakout_extension_norm",
          value: formatNumber(item.breakout_extension_norm, 4),
        },
        { key: "close_strength", label: "close_strength", value: formatNumber(item.close_strength, 4) },
        { key: "factor_score", label: "factor_score", value: formatNumber(item.factor_score, 4) },
        {
          key: "factor_overlay_rank",
          label: "factor_overlay_rank",
          value: item.factor_overlay_rank != null ? String(item.factor_overlay_rank) : "待补",
        },
        { key: "pe", label: "pe", value: formatNumber(item.pe, 4) },
        { key: "pb", label: "pb", value: formatNumber(item.pb, 4) },
        { key: "ps", label: "ps", value: formatNumber(item.ps, 4) },
        { key: "roe", label: "roe", value: formatNumber(item.roe, 4) },
        { key: "gross_margin", label: "gross_margin", value: formatNumber(item.gross_margin, 4) },
      ],
    };
  });
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
      reason: `触发复核：${item.reason}`,
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
    rows.push({
      stockCode: item.stock_code,
      stockName: item.stock_name ?? item.stock_code,
      status,
      latestClose: formatNumber(latest),
      exitWatchPrice: formatNumber(exit ?? undefined),
      reason:
        normalizeEvidence(item.evidence)[0] ??
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
          : `市场门控 ${payload.market_gate.state} / 宏观 ${confluence?.macro_context.status ?? "missing"}`,
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
          : adversarial?.strongest_block_reason ||
            `${adversarial?.mode ?? "anti-crowding"} / 状态 ${adversarial?.status ?? "missing"}`,
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
      detail: `质量 ${meta.quality_flag ?? "pending"} / 供应 ${meta.vendor_status ?? "pending"}${
        fallbackMode !== "none" ? ` / fallback ${fallbackMode}` : ""
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
      nextStep: "保留观察队列，但先复核降级、fallback、proxy-only 或 pending 日期。",
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
    const blockedReasons = windowStatus.blocked_dates.map((item) => `${item.trade_date} ${item.reason_code}`);
    const detailParts = [
      windowStatus.has_decision_usable_completed_stats
        ? `included completed stats dates: ${windowStatus.included_completed_stats_dates.join(", ") || "none"}`
        : "no decision-usable completed replay dates",
      excludedDates.length > 0
        ? `excluded from completed stats: ${excludedDates.join(", ")}`
        : "no dates excluded from completed stats",
      ...blockedReasons,
    ];
    if (windowStatus.completed_zero_signal_dates.length > 0) {
      detailParts.push(`completed zero-signal dates: ${windowStatus.completed_zero_signal_dates.join(", ")}`);
    }
    detailParts.push("observation only: do not infer strategy efficacy");
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
    `completed dates ${windowStatus.completed_dates}`,
    `pending dates ${windowStatus.pending_dates}`,
    `unsupported dates ${windowStatus.unsupported_dates}`,
    `proxy-only dates ${windowStatus.proxy_only_dates}`,
    `completed rows ${windowStatus.completed_candidate_rows}`,
  ];
}

function normalizeClosedLoopStatus(value: unknown, defaultValue: string): string {
  if (typeof value === "string") {
    return value;
  }
  const windowStatus = replayStatusWindow(value);
  return windowStatus?.window_status ?? defaultValue;
}

function replayStatusWindow(value: unknown): ConfluenceReplayStatus | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const candidate = value as {
    window_status?: unknown;
    has_decision_usable_completed_stats?: unknown;
    completed_dates?: unknown;
    pending_dates?: unknown;
    unsupported_dates?: unknown;
    proxy_only_dates?: unknown;
    completed_candidate_rows?: unknown;
    pending_candidate_rows?: unknown;
    unsupported_candidate_rows?: unknown;
    proxy_only_candidate_rows?: unknown;
    included_completed_stats_dates?: unknown;
    blocked_dates?: unknown;
    completed_zero_signal_dates?: unknown;
  };
  if (!isBacktestWindowSummaryStatus(candidate.window_status)) {
    return null;
  }
  return {
    window_status: candidate.window_status,
    has_decision_usable_completed_stats: candidate.has_decision_usable_completed_stats === true,
    completed_dates: finiteCount(candidate.completed_dates),
    pending_dates: finiteCount(candidate.pending_dates),
    unsupported_dates: finiteCount(candidate.unsupported_dates),
    proxy_only_dates: finiteCount(candidate.proxy_only_dates),
    completed_candidate_rows: finiteCount(candidate.completed_candidate_rows),
    pending_candidate_rows: finiteCount(candidate.pending_candidate_rows),
    unsupported_candidate_rows: finiteCount(candidate.unsupported_candidate_rows),
    proxy_only_candidate_rows: finiteCount(candidate.proxy_only_candidate_rows),
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

function blockedReplayDates(value: unknown): ConfluenceReplayBlockedDate[] {
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
    if (typeof row.trade_date !== "string" || !isBlockedReplayReasonCode(row.reason_code)) {
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

function isBlockedReplayReasonCode(value: unknown): value is ConfluenceReplayBlockedDate["reason_code"] {
  return (
    value === "missing_daily_limit_flags" ||
    value === "missing_required_source_table" ||
    value === "forward_returns_pending" ||
    value === "real_theme_inputs_unconfirmed" ||
    value === "proxy_theme_only"
  );
}

function normalizeBlockedReplayDateStatus(
  value: unknown,
  reasonCode: ConfluenceReplayBlockedDate["reason_code"],
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
  return key === "lineage" ? "待确认" : status;
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
  return labels[normalized] ?? stage.replace(/_/g, " ");
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
  return normalized.replace(/_/g, " ");
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
  };
  return labels[normalized] ?? status ?? "状态待补";
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
    complianceDetail: input.framework.boundary,
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
      complianceDetail: input.unsupportedReason,
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
    complianceDetail: isProxy
      ? "Proxy theme radar: daily bars, limit-up flags and name clustering; not a formal concept catalog."
      : undefined,
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
      detail: input.errorMessage,
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
      detail: `样本阈值 ${input.payload?.min_sample ?? 20}，不输出交易动作。`,
      badgeLabel: "待补",
      stats: [{ key: "rows", label: "策略", value: `${input.rows.length}`, tone: "neutral" }],
      tone: "warning",
    };
  }

  const horizon = input.payload?.primary_horizon ?? "return_5d";
  const horizonStats = top.stats[horizon];
  return {
    headline: `优先 ${top.strategy_label}`,
    detail: top.reason,
    badgeLabel: top.priority_label === "优先复核" ? "已就绪" : "降权观察",
    stats: [
      {
        key: "score",
        label: "评分",
        value: top.priority_score?.toFixed(1) ?? "-",
        tone: top.priority_label === "优先复核" ? "positive" : "warning",
      },
      {
        key: "t5",
        label: "T+5",
        value: formatBacktestHorizonStatsText(horizonStats),
        tone: (horizonStats?.win_rate ?? 0) >= 0.5 ? "positive" : "neutral",
      },
    ],
    tone: top.priority_label === "优先复核" ? "positive" : "warning",
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
      detail: input.errorMessage,
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
      detail: input.errorMessage,
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
      detail: input.payload?.pending_summary.message,
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

  return {
    headline: `${top.recommendation.priority_label} · ${top.strategy_label}`,
    detail: top.recommendation.reason,
    badgeLabel: top.recommendation.priority_label === "优先复核" ? "已就绪" : "降权观察",
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
    tone: top.recommendation.priority_label === "优先复核" ? "positive" : "warning",
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
        ? "WARM 激活超跌反弹；融合/超跌明细见展开区。"
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
    detail: `最高优先：${eventMonitorSourceLabel(top.source)} / ${top.impact.replace(/_/g, " ")}`,
    badgeLabel: errorCount > 0 ? "待补" : warningCount > 0 ? "待复核" : "已就绪",
    stats: [
      { key: "error", label: "错误", value: `${errorCount}`, tone: errorCount > 0 ? "negative" : "positive" },
      { key: "warn", label: "预警", value: `${warningCount}`, tone: warningCount > 0 ? "warning" : "neutral" },
      { key: "top", label: "来源", value: eventMonitorSourceLabel(top.source), tone: "neutral" },
    ],
    tone: errorCount > 0 ? "negative" : warningCount > 0 ? "warning" : "neutral",
  };
}
