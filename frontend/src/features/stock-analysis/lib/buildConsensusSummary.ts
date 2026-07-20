import type { LivermoreStrategyPayload } from "../../../api/contracts";

/**
 * T+5 共振推荐项：被趋势与多因子共同选中的股票。
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
  hybridFusionRank: number | null;
};

export type ConsensusStrategyKind = "hybrid_fusion" | "livermore" | "mean_reversion" | "factor_screen";

const STRATEGY_OUTPUT_KEYS: Record<ConsensusStrategyKind, LivermoreStrategyPayload["supported_outputs"][number]> = {
  hybrid_fusion: "hybrid_fusion",
  livermore: "stock_candidates",
  mean_reversion: "mean_reversion_candidates",
  factor_screen: "factor_screen_candidates",
};

export type ConsensusSummary = {
  /** 3 套策略共同推荐 */
  tripleCount: number;
  /** T+5 核心策略共同推荐 */
  doubleCount: number;
  /** 完整候选池（含单策略）规模 */
  totalUnion: number;
  /** T+5 核心共振推荐列表，按 consensusCount 降序 + 后端最小 rank 升序 + 股票代码字典序 */
  items: ConsensusCandidateItem[];
  /** 各策略的候选数（用于标题/空状态说明） */
  strategyCounts: Record<ConsensusStrategyKind, number>;
  /** 是否有任何一套策略产生了候选 */
  hasAnyStrategy: boolean;
};

const STRATEGY_LABELS: Record<ConsensusStrategyKind, string> = {
  hybrid_fusion: "融合策略",
  livermore: "趋势",
  mean_reversion: "超跌反弹",
  factor_screen: "多因子",
};

export function consensusStrategyLabel(kind: ConsensusStrategyKind): string {
  return STRATEGY_LABELS[kind];
}

function isConsensusStrategyPrimaryExcluded(
  payload: LivermoreStrategyPayload | null | undefined,
  kind: ConsensusStrategyKind,
): boolean {
  if (!payload) {
    return true;
  }
  const key = STRATEGY_OUTPUT_KEYS[kind];
  if (!payload.module_states || payload.module_states.length === 0) {
    return true;
  }
  const state = payload.module_states.find((item) => item.key === key);
  return !state || state.excludes_from_primary || state.render_mode !== "primary";
}

/**
 * 查询某只股票在候选策略中的排名（只被单套策略选中也会返回）。
 * 用于在详情抽屉里展示"该股票在哪些策略里、各排第几"。
 */
export function lookupStockStrategyRanks(
  payload: LivermoreStrategyPayload | null | undefined,
  stockCode: string,
): {
  livermoreRank: number | null;
  meanReversionRank: number | null;
  factorScreenRank: number | null;
  hybridFusionRank: number | null;
  hitCount: number;
} {
  if (!payload || !stockCode) {
    return {
      livermoreRank: null,
      meanReversionRank: null,
      factorScreenRank: null,
      hybridFusionRank: null,
      hitCount: 0,
    };
  }
  const hf = payload.hybrid_fusion_candidates?.items?.find((x) => x.stock_code === stockCode);
  const sc = payload.stock_candidates?.items?.find((x) => x.stock_code === stockCode);
  const mr = payload.mean_reversion_candidates?.items?.find((x) => x.stock_code === stockCode);
  const fs = payload.factor_screen_candidates?.items?.find((x) => x.stock_code === stockCode);
  const hybridFusionRank = hf?.rank ?? null;
  const livermoreRank = sc?.rank ?? null;
  const meanReversionRank = mr?.rank ?? null;
  const factorScreenRank = fs?.rank ?? null;
  const hitCount =
    (hybridFusionRank != null ? 1 : 0) +
    (livermoreRank != null ? 1 : 0) +
    (meanReversionRank != null ? 1 : 0) +
    (factorScreenRank != null ? 1 : 0);
  return { livermoreRank, meanReversionRank, factorScreenRank, hybridFusionRank, hitCount };
}

/**
 * 参与共振计数的核心策略后端 rank 中的最小值（越小越靠前）。
 * 仅使用后端已返回的 rank，不在前端发明评分。
 */
function bestBackendRank(item: {
  hybridFusionRank: number | null;
  livermoreRank: number | null;
  factorScreenRank: number | null;
}): number {
  const ranks = [item.hybridFusionRank, item.livermoreRank, item.factorScreenRank].filter(
    (rank): rank is number => rank != null,
  );
  return ranks.length > 0 ? Math.min(...ranks) : Number.POSITIVE_INFINITY;
}

/**
 * 展示用确定性排序：命中策略数（计数）降序 -> 后端最小 rank 升序 -> 股票代码字典序。
 * 只复用后端字段做字典序排序，前端不补算任何评分。
 */
function compareConsensusItems(a: ConsensusCandidateItem, b: ConsensusCandidateItem): number {
  if (b.consensusCount !== a.consensusCount) return b.consensusCount - a.consensusCount;
  const rankDiff = bestBackendRank(a) - bestBackendRank(b);
  if (rankDiff !== 0) return rankDiff;
  return a.stockCode.localeCompare(b.stockCode);
}

export function buildConsensusSummary(
  payload: LivermoreStrategyPayload | null | undefined,
): ConsensusSummary {
  const livermoreItems = isConsensusStrategyPrimaryExcluded(payload, "livermore")
    ? []
    : (payload?.stock_candidates?.items ?? []);
  const meanReversionItems = isConsensusStrategyPrimaryExcluded(payload, "mean_reversion")
    ? []
    : (payload?.mean_reversion_candidates?.items ?? []);
  const factorScreenItems = isConsensusStrategyPrimaryExcluded(payload, "factor_screen")
    ? []
    : (payload?.factor_screen_candidates?.items ?? []);
  const hybridFusionItems = isConsensusStrategyPrimaryExcluded(payload, "hybrid_fusion")
    ? []
    : (payload?.hybrid_fusion_candidates?.items ?? []);

  const strategyCounts: Record<ConsensusStrategyKind, number> = {
    hybrid_fusion: hybridFusionItems.length,
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
    hybridFusionRank: number | null;
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
        hybridFusionRank: null,
      };
      byCode.set(stockCode, entry);
    }
    entry.strategies.add(kind);
    // 优先保留更完整的名称与板块（后来的覆盖空值）
    if (!entry.stockName && stockName) entry.stockName = stockName;
    if (!entry.sectorName && sectorName) entry.sectorName = sectorName;
    if (kind === "hybrid_fusion") entry.hybridFusionRank = rank;
    if (kind === "livermore") entry.livermoreRank = rank;
    if (kind === "mean_reversion") entry.meanReversionRank = rank;
    if (kind === "factor_screen") entry.factorScreenRank = rank;
  };

  for (const item of hybridFusionItems) {
    register(item.stock_code, item.stock_name, item.sector_name, "hybrid_fusion", item.rank);
  }
  for (const item of livermoreItems) {
    register(item.stock_code, item.stock_name, item.sector_name, "livermore", item.rank);
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
  for (const item of meanReversionItems) {
    const entry = byCode.get(item.stock_code);
    if (!entry) continue;
    if (!entry.stockName && item.stock_name) entry.stockName = item.stock_name;
    if (!entry.sectorName && item.sector_name) entry.sectorName = item.sector_name;
    entry.meanReversionRank = item.rank;
  }

  const items: ConsensusCandidateItem[] = [];
  let tripleCount = 0;
  let doubleCount = 0;

  for (const entry of byCode.values()) {
    const consensusCount = entry.strategies.size;
    if (consensusCount >= 3) tripleCount += 1;
    if (consensusCount >= 2) doubleCount += 1;
    if (consensusCount < 2) continue;

    items.push({
      stockCode: entry.stockCode,
      stockName: entry.stockName || entry.stockCode,
      sectorName: entry.sectorName,
      strategies: Array.from(entry.strategies),
      consensusCount,
      livermoreRank: entry.livermoreRank,
      meanReversionRank: entry.meanReversionRank,
      factorScreenRank: entry.factorScreenRank,
      hybridFusionRank: entry.hybridFusionRank,
    });
  }

  items.sort(compareConsensusItems);

  const unionCodes = new Set<string>();
  for (const item of livermoreItems) if (item.stock_code) unionCodes.add(item.stock_code);
  for (const item of meanReversionItems) if (item.stock_code) unionCodes.add(item.stock_code);
  for (const item of factorScreenItems) if (item.stock_code) unionCodes.add(item.stock_code);
  for (const item of hybridFusionItems) if (item.stock_code) unionCodes.add(item.stock_code);
  const totalUnion = unionCodes.size;
  const hasAnyStrategy =
    strategyCounts.hybrid_fusion +
      strategyCounts.livermore +
      strategyCounts.mean_reversion +
      strategyCounts.factor_screen >
    0;

  return {
    tripleCount,
    doubleCount,
    totalUnion,
    items,
    strategyCounts,
    hasAnyStrategy,
  };
}

/**
 * 按板块分组共振推荐项。
 * 组内与组间均复用确定性字典序排序（命中数 -> 后端最小 rank -> 股票代码）。
 */
export type ConsensusSectorGroup = {
  sectorName: string;
  tripleCount: number;
  doubleCount: number;
  totalCount: number;
  items: ConsensusCandidateItem[];
};

export function groupConsensusBySector(
  items: ConsensusCandidateItem[],
): ConsensusSectorGroup[] {
  const byName = new Map<string, ConsensusSectorGroup>();
  for (const item of items) {
    const key = item.sectorName || "未分类";
    let group = byName.get(key);
    if (!group) {
      group = {
        sectorName: key,
        tripleCount: 0,
        doubleCount: 0,
        totalCount: 0,
        items: [],
      };
      byName.set(key, group);
    }
    group.items.push(item);
    group.totalCount += 1;
    if (item.consensusCount >= 3) group.tripleCount += 1;
    if (item.consensusCount >= 2) group.doubleCount += 1;
  }

  for (const group of byName.values()) {
    group.items.sort(compareConsensusItems);
  }

  return Array.from(byName.values()).sort((a, b) => {
    if (b.tripleCount !== a.tripleCount) return b.tripleCount - a.tripleCount;
    if (b.doubleCount !== a.doubleCount) return b.doubleCount - a.doubleCount;
    // 组内已排序，用组内第一名（最佳项）做组间确定性排序
    return compareConsensusItems(a.items[0], b.items[0]);
  });
}
