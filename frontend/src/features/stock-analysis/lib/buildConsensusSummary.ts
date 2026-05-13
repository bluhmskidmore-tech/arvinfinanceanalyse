import type { LivermoreStrategyPayload } from "../../../api/contracts";

/**
 * 共振推荐项：至少被 2 套策略共同选中的股票。
 */
export type ConsensusCandidateItem = {
  stockCode: string;
  stockName: string;
  sectorName: string;
  strategies: ConsensusStrategyKind[];
  /** 被多少套策略选中（2 或 3） */
  consensusCount: number;
  /** 各策略内的排名（越小越靠前） */
  livermoreRank: number | null;
  meanReversionRank: number | null;
  factorScreenRank: number | null;
  /** 综合得分：排名越靠前得分越高 */
  consensusScore: number;
};

export type ConsensusStrategyKind = "livermore" | "mean_reversion" | "factor_screen";

export type ConsensusSummary = {
  /** 3 套策略共同推荐 */
  tripleCount: number;
  /** 至少 2 套策略共同推荐 */
  doubleCount: number;
  /** 完整候选池（含单策略）规模 */
  totalUnion: number;
  /** 共振推荐列表（2+ 套策略重合），按 consensusScore 降序 */
  items: ConsensusCandidateItem[];
  /** 各策略的候选数（用于标题/空状态说明） */
  strategyCounts: Record<ConsensusStrategyKind, number>;
  /** 是否有任何一套策略产生了候选 */
  hasAnyStrategy: boolean;
};

const STRATEGY_LABELS: Record<ConsensusStrategyKind, string> = {
  livermore: "趋势",
  mean_reversion: "超跌反弹",
  factor_screen: "多因子",
};

export function consensusStrategyLabel(kind: ConsensusStrategyKind): string {
  return STRATEGY_LABELS[kind];
}

/**
 * 查询某只股票在三套策略中的排名（只被单套策略选中也会返回）。
 * 用于在详情抽屉里展示"该股票在哪些策略里、各排第几"。
 */
export function lookupStockStrategyRanks(
  payload: LivermoreStrategyPayload | null | undefined,
  stockCode: string,
): {
  livermoreRank: number | null;
  meanReversionRank: number | null;
  factorScreenRank: number | null;
  hitCount: number;
} {
  if (!payload || !stockCode) {
    return {
      livermoreRank: null,
      meanReversionRank: null,
      factorScreenRank: null,
      hitCount: 0,
    };
  }
  const sc = payload.stock_candidates?.items?.find((x) => x.stock_code === stockCode);
  const mr = payload.mean_reversion_candidates?.items?.find((x) => x.stock_code === stockCode);
  const fs = payload.factor_screen_candidates?.items?.find((x) => x.stock_code === stockCode);
  const livermoreRank = sc?.rank ?? null;
  const meanReversionRank = mr?.rank ?? null;
  const factorScreenRank = fs?.rank ?? null;
  const hitCount =
    (livermoreRank != null ? 1 : 0) +
    (meanReversionRank != null ? 1 : 0) +
    (factorScreenRank != null ? 1 : 0);
  return { livermoreRank, meanReversionRank, factorScreenRank, hitCount };
}

export function buildConsensusSummary(
  payload: LivermoreStrategyPayload | null | undefined,
): ConsensusSummary {
  const livermoreItems = payload?.stock_candidates?.items ?? [];
  const meanReversionItems = payload?.mean_reversion_candidates?.items ?? [];
  const factorScreenItems = payload?.factor_screen_candidates?.items ?? [];

  const strategyCounts: Record<ConsensusStrategyKind, number> = {
    livermore: livermoreItems.length,
    mean_reversion: meanReversionItems.length,
    factor_screen: factorScreenItems.length,
  };

  type Entry = {
    stockCode: string;
    stockName: string;
    sectorName: string;
    strategies: Set<ConsensusStrategyKind>;
    livermoreRank: number | null;
    meanReversionRank: number | null;
    factorScreenRank: number | null;
  };

  const byCode = new Map<string, Entry>();

  const register = (
    stockCode: string,
    stockName: string,
    sectorName: string,
    kind: ConsensusStrategyKind,
    rank: number,
  ) => {
    if (!stockCode) return;
    let entry = byCode.get(stockCode);
    if (!entry) {
      entry = {
        stockCode,
        stockName,
        sectorName,
        strategies: new Set(),
        livermoreRank: null,
        meanReversionRank: null,
        factorScreenRank: null,
      };
      byCode.set(stockCode, entry);
    }
    entry.strategies.add(kind);
    // 优先保留更完整的名称与板块（后来的覆盖空值）
    if (!entry.stockName && stockName) entry.stockName = stockName;
    if (!entry.sectorName && sectorName) entry.sectorName = sectorName;
    if (kind === "livermore") entry.livermoreRank = rank;
    if (kind === "mean_reversion") entry.meanReversionRank = rank;
    if (kind === "factor_screen") entry.factorScreenRank = rank;
  };

  for (const item of livermoreItems) {
    register(item.stock_code, item.stock_name, item.sector_name, "livermore", item.rank);
  }
  for (const item of meanReversionItems) {
    register(item.stock_code, item.stock_name, item.sector_name, "mean_reversion", item.rank);
  }
  for (const item of factorScreenItems) {
    register(
      item.stock_code,
      item.stock_name,
      item.sector_name || item.industry || "",
      "factor_screen",
      item.rank,
    );
  }

  const items: ConsensusCandidateItem[] = [];
  let tripleCount = 0;
  let doubleCount = 0;

  for (const entry of byCode.values()) {
    const consensusCount = entry.strategies.size;
    if (consensusCount >= 3) tripleCount += 1;
    if (consensusCount >= 2) doubleCount += 1;
    if (consensusCount < 2) continue;

    // 共振得分：每套策略贡献 (1 / (rank + 1))；命中策略数量作为主权重
    const rankScore =
      (entry.livermoreRank != null ? 1 / (entry.livermoreRank + 1) : 0) +
      (entry.meanReversionRank != null ? 1 / (entry.meanReversionRank + 1) : 0) +
      (entry.factorScreenRank != null ? 1 / (entry.factorScreenRank + 1) : 0);
    const consensusScore = consensusCount * 10 + rankScore;

    items.push({
      stockCode: entry.stockCode,
      stockName: entry.stockName || entry.stockCode,
      sectorName: entry.sectorName,
      strategies: Array.from(entry.strategies),
      consensusCount,
      livermoreRank: entry.livermoreRank,
      meanReversionRank: entry.meanReversionRank,
      factorScreenRank: entry.factorScreenRank,
      consensusScore,
    });
  }

  items.sort((a, b) => b.consensusScore - a.consensusScore);

  const totalUnion = byCode.size;
  const hasAnyStrategy =
    strategyCounts.livermore + strategyCounts.mean_reversion + strategyCounts.factor_screen > 0;

  return {
    tripleCount,
    doubleCount,
    totalUnion,
    items,
    strategyCounts,
    hasAnyStrategy,
  };
}
