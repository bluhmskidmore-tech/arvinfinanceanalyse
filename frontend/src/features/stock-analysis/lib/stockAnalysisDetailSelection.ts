export const STOCK_DETAIL_SOURCE_VALUES = [
  "review_queue",
  "risk_exit",
  "mean_reversion",
  "factor_screen",
  "hybrid_fusion",
  "consensus",
  "sector_constituent",
  "theme_breakout",
  "livermore",
  "fresh_trend_watchlist",
  "source_unconfirmed",
] as const;

export type StockDetailSource = (typeof STOCK_DETAIL_SOURCE_VALUES)[number];

export type StockDetailSelection = {
  code: string;
  name?: string;
  reviewRank?: number;
  sectorCode?: string;
  sectorName?: string;
  distanceToBreakoutPct?: string;
  source?: StockDetailSource;
  reviewThesis?: StockDetailReviewThesis;
  livermoreRank?: number | null;
  meanReversionRank?: number | null;
  factorScreenRank?: number | null;
  hybridFusionRank?: number | null;
};

export type StockDetailReviewThesis = {
  whySelected: string[];
  boundaries: string[];
  invalidation: string[];
  nextActions: string[];
};

export type StockDetailReviewContext = {
  sourceLabel: string;
  sectorName?: string;
  reviewRank?: number;
  distanceToBreakoutPct?: string;
  reviewThesis?: StockDetailReviewThesis;
  livermoreRank?: number | null;
  meanReversionRank?: number | null;
  factorScreenRank?: number | null;
  hybridFusionRank?: number | null;
};

const STOCK_DETAIL_SOURCE_LABELS: Record<StockDetailSource, string> = {
  risk_exit: "风险退出观察",
  mean_reversion: "超跌反弹观察",
  factor_screen: "多因子选股",
  hybrid_fusion: "融合策略",
  consensus: "多策略共振",
  sector_constituent: "板块成分",
  theme_breakout: "题材强势",
  livermore: "趋势候选",
  fresh_trend_watchlist: "新趋势观察",
  source_unconfirmed: "来源待确认",
  review_queue: "复核队列",
};

export function buildStockDetailReviewContext(
  selection: StockDetailSelection | null,
): StockDetailReviewContext | null {
  if (!selection) return null;

  return {
    sourceLabel: selection.source ? STOCK_DETAIL_SOURCE_LABELS[selection.source] : STOCK_DETAIL_SOURCE_LABELS.review_queue,
    sectorName: selection.sectorName,
    reviewRank: selection.reviewRank,
    distanceToBreakoutPct: selection.distanceToBreakoutPct,
    reviewThesis: selection.reviewThesis,
    livermoreRank: selection.livermoreRank,
    meanReversionRank: selection.meanReversionRank,
    factorScreenRank: selection.factorScreenRank,
    hybridFusionRank: selection.hybridFusionRank,
  };
}

type ConsensusDetailSelectionInput = {
  stockCode: string;
  stockName?: string;
  sectorName?: string;
  livermoreRank?: number | null;
  meanReversionRank?: number | null;
  factorScreenRank?: number | null;
  hybridFusionRank?: number | null;
};

export function buildConsensusDetailSelection(
  row: ConsensusDetailSelectionInput,
): StockDetailSelection {
  return {
    code: row.stockCode,
    name: row.stockName,
    sectorName: row.sectorName,
    source: "consensus",
    livermoreRank: row.livermoreRank,
    meanReversionRank: row.meanReversionRank,
    factorScreenRank: row.factorScreenRank,
    hybridFusionRank: row.hybridFusionRank,
  };
}

type ReviewQueueDetailSelectionInput = {
  card: {
    stockCode: string;
    stockName?: string;
    rank: number;
    sectorCode?: string;
    sectorName?: string;
    distanceToBreakoutPct?: string;
    reviewFocus?: string;
    primaryEvidence?: Array<{ label: string; value: string }>;
    supportingEvidence?: Array<{ label: string; value: string }>;
    boundaryEvidence?: string[];
    invalidationFocus?: string;
    invalidationRules?: string[];
  };
  ranks: {
    livermoreRank: number | null;
    meanReversionRank: number | null;
    factorScreenRank: number | null;
    hybridFusionRank: number | null;
  };
  reviewQueueUsesHybridFusion: boolean;
};

function cleanReviewText(value: string | null | undefined): string {
  return value?.replace(/\s+/g, " ").trim() ?? "";
}

function uniqueNonEmpty(values: Array<string | null | undefined>, limit: number): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const normalized = cleanReviewText(value);
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    result.push(normalized);
    if (result.length >= limit) break;
  }
  return result;
}

function isGenericBoundaryCopy(value: string | null | undefined): boolean {
  const normalized = cleanReviewText(value);
  return (
    normalized.startsWith("基本面因子已纳入候选排序") ||
    normalized.startsWith("基本面与估值证据未接入") ||
    normalized.startsWith("生命法庭层仍是观察线索") ||
    normalized.startsWith("代理信号仅作来源线索") ||
    normalized.startsWith("仅作观察与复核") ||
    normalized.startsWith("来源命中：") ||
    normalized.startsWith("过热门控下仅作观察补充")
  );
}

function evidenceText(item: { label: string; value: string } | null | undefined): string {
  if (!item) return "";
  const label = cleanReviewText(item.label);
  const value = cleanReviewText(item.value);
  if (!label && !value) return "";
  if (!label) return value;
  if (!value) return label;
  return `${label}：${value}`;
}

function buildReviewQueueThesis(card: ReviewQueueDetailSelectionInput["card"]): StockDetailReviewThesis {
  const visibleEvidence = [...(card.primaryEvidence ?? []), ...(card.supportingEvidence ?? [])];
  const themeEvidence = visibleEvidence.filter((item) => item.label === "题材归属").map(evidenceText);
  const evidence = visibleEvidence
    .filter((item) => item.label !== "题材归属")
    .map(evidenceText);
  const explicitBoundaries = (card.boundaryEvidence ?? []).filter((item) => !isGenericBoundaryCopy(item));
  const themeBoundaries = explicitBoundaries.filter((item) => item.includes("当前覆盖") || item.includes("非时点"));
  const otherBoundaries = explicitBoundaries.filter((item) => !themeBoundaries.includes(item));
  const boundaries = uniqueNonEmpty(
    [...themeBoundaries, ...otherBoundaries],
    Math.max(2, themeBoundaries.length + 1),
  );
  const invalidation = uniqueNonEmpty([...(card.invalidationRules ?? []), card.invalidationFocus], 2);

  return {
    whySelected: uniqueNonEmpty(
      themeEvidence.length > 0 ? [...themeEvidence, card.reviewFocus, ...evidence] : [card.reviewFocus, ...evidence],
      Math.max(3, themeEvidence.length + 2),
    ),
    boundaries: boundaries.length > 0 ? boundaries : ["边界清洁"],
    invalidation: invalidation.length > 0 ? invalidation : ["失效条件待补"],
    nextActions: [
      "看 K 线确认价格与量能",
      boundaries.length > 0 ? "查公告/新闻确认边界" : "确认题材与量能是否延续",
      "确认失效条件后再继续观察",
    ],
  };
}

export function buildReviewQueueDetailSelection({
  card,
  ranks,
  reviewQueueUsesHybridFusion,
}: ReviewQueueDetailSelectionInput): StockDetailSelection {
  return {
    code: card.stockCode,
    name: card.stockName,
    reviewRank: card.rank,
    sectorCode: card.sectorCode,
    sectorName: card.sectorName,
    distanceToBreakoutPct: card.distanceToBreakoutPct,
    source: "review_queue",
    reviewThesis: buildReviewQueueThesis(card),
    livermoreRank: reviewQueueUsesHybridFusion ? ranks.livermoreRank : card.rank,
    meanReversionRank: ranks.meanReversionRank,
    factorScreenRank: ranks.factorScreenRank,
    hybridFusionRank: reviewQueueUsesHybridFusion ? card.rank : ranks.hybridFusionRank,
  };
}

type StrategyRankSnapshot = {
  livermoreRank: number | null;
  meanReversionRank: number | null;
  factorScreenRank: number | null;
  hybridFusionRank: number | null;
};

type RiskExitDetailSelectionInput = {
  row: {
    stockCode: string;
    stockName?: string;
  };
  ranks: StrategyRankSnapshot;
};

export function buildRiskExitDetailSelection({
  row,
  ranks,
}: RiskExitDetailSelectionInput): StockDetailSelection {
  return {
    code: row.stockCode,
    name: row.stockName,
    source: "risk_exit",
    livermoreRank: ranks.livermoreRank,
    meanReversionRank: ranks.meanReversionRank,
    factorScreenRank: ranks.factorScreenRank,
    hybridFusionRank: ranks.hybridFusionRank,
  };
}

type MeanReversionDetailSelectionInput = {
  row: {
    stock_code: string;
    stock_name?: string;
    rank: number;
    sector_code?: string;
    sector_name?: string;
  };
  ranks: StrategyRankSnapshot;
};

export function buildMeanReversionDetailSelection({
  row,
  ranks,
}: MeanReversionDetailSelectionInput): StockDetailSelection {
  return {
    code: row.stock_code,
    name: row.stock_name,
    sectorCode: row.sector_code,
    sectorName: row.sector_name,
    source: "mean_reversion",
    livermoreRank: ranks.livermoreRank,
    meanReversionRank: row.rank,
    factorScreenRank: ranks.factorScreenRank,
    hybridFusionRank: ranks.hybridFusionRank,
  };
}

type FactorScreenDetailSelectionInput = {
  row: {
    stock_code: string;
    stock_name?: string;
    rank: number;
    sector_code?: string;
    sector_name?: string;
    industry?: string;
  };
  ranks: StrategyRankSnapshot;
};

export function buildFactorScreenDetailSelection({
  row,
  ranks,
}: FactorScreenDetailSelectionInput): StockDetailSelection {
  return {
    code: row.stock_code,
    name: row.stock_name,
    sectorCode: row.sector_code,
    sectorName: row.sector_name || row.industry,
    source: "factor_screen",
    livermoreRank: ranks.livermoreRank,
    meanReversionRank: ranks.meanReversionRank,
    factorScreenRank: row.rank,
    hybridFusionRank: ranks.hybridFusionRank,
  };
}

type RankContextDetailSelectionInput = {
  stockCode: string;
  stockName?: string;
  sectorCode?: string;
  sectorName?: string;
  source?: StockDetailSource;
  ranks: StrategyRankSnapshot;
};

export function buildRankContextDetailSelection({
  stockCode,
  stockName,
  sectorCode,
  sectorName,
  source,
  ranks,
}: RankContextDetailSelectionInput): StockDetailSelection {
  return {
    code: stockCode,
    name: stockName,
    sectorCode,
    sectorName,
    source,
    livermoreRank: ranks.livermoreRank,
    meanReversionRank: ranks.meanReversionRank,
    factorScreenRank: ranks.factorScreenRank,
    hybridFusionRank: ranks.hybridFusionRank,
  };
}
