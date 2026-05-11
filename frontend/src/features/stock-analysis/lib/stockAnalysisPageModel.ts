import type {
  BacktestWindowSummaryStatus,
  ConfluenceReplayBlockedDate,
  ConfluenceReplayStatus,
  LivermoreMarketGateState,
  LivermoreSignalConfluencePayload,
  LivermoreStockCandidateItem,
  LivermoreStrategyPayload,
  LivermoreThemeBreakoutItem,
  ResultMeta,
} from "../../../api/contracts";

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

export type StockClosedLoopSummary = {
  summaryLabel: string;
  boundaryCount: number;
  referenceRating: StockDecisionReferenceRating;
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
  const fallbackLabel = isFallback ? ` / fallback ${fallbackMode}` : "";
  const dataFreshnessOk = qualityFlag === "ok" && vendorStatus === "ok" && !isFallback;
  const candidateCount = payload.stock_candidates?.candidate_count ?? queue.length;
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
      : "暂无候选股，先核对门控、板块强弱和数据边界。",
    basisLabel: `basis: ${payload.basis}`,
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
      {
        key: "gap_norm",
        label: "跳空归一观察",
        value:
          item.gap_norm != null && Number.isFinite(item.gap_norm)
            ? `${item.gap_norm.toFixed(4)}`
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
        "基本面与估值证据未接入，不参与当前候选排序。",
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
        { key: "close_strength", label: "close_strength", value: formatNumber(item.close_strength, 4) },
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
  return {
    summaryLabel: boundaryCount > 0 ? `${boundaryCount} 项待复核` : "全部通过",
    boundaryCount,
    referenceRating: buildDecisionReferenceRating(items),
    items,
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
