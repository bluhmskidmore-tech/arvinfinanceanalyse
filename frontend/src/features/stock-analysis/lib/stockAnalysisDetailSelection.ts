export const STOCK_DETAIL_SOURCE_VALUES = [
  "review_queue",
  "risk_exit",
  "mean_reversion",
  "factor_screen",
  "hybrid_fusion",
  "consensus",
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
  livermoreRank?: number | null;
  meanReversionRank?: number | null;
  factorScreenRank?: number | null;
  hybridFusionRank?: number | null;
};

export type StockDetailReviewContext = {
  sourceLabel: string;
  sectorName?: string;
  reviewRank?: number;
  distanceToBreakoutPct?: string;
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
  };
  ranks: {
    livermoreRank: number | null;
    meanReversionRank: number | null;
    factorScreenRank: number | null;
    hybridFusionRank: number | null;
  };
  reviewQueueUsesHybridFusion: boolean;
};

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
  ranks: StrategyRankSnapshot;
};

export function buildRankContextDetailSelection({
  stockCode,
  stockName,
  sectorCode,
  sectorName,
  ranks,
}: RankContextDetailSelectionInput): StockDetailSelection {
  return {
    code: stockCode,
    name: stockName,
    sectorCode,
    sectorName,
    livermoreRank: ranks.livermoreRank,
    meanReversionRank: ranks.meanReversionRank,
    factorScreenRank: ranks.factorScreenRank,
    hybridFusionRank: ranks.hybridFusionRank,
  };
}
