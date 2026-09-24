import type {
  FreshTrendWatchlistCandidateItem,
  HybridFusionCandidateItem,
  LivermoreRiskExitItem,
  LivermoreRiskExitWatchItem,
  LivermoreStockCandidateItem,
  LivermoreStrategyPayload,
  MeanReversionCandidateItem,
  UptrendMomentumCandidateItem,
} from "../../../api/contracts";
import type { StockDetailSource } from "./stockAnalysisDetailSelection";
import { riskExitBlockedSummary } from "./stockAnalysisPageCopy";

export type StockAnalysisKlineRadarQueueKey =
  | "breakout"
  | "trend_continuation"
  | "mean_reversion"
  | "risk_exit";

export type StockAnalysisKlineRadarTone = "positive" | "warning" | "negative" | "neutral";

export type StockAnalysisKlineRadarSourceModule =
  | "stock_candidates"
  | "fresh_trend_watchlist"
  | "uptrend_momentum_candidates"
  | "hybrid_fusion_candidates"
  | "mean_reversion_candidates"
  | "risk_exit.items"
  | "risk_exit.watch_items";

export type StockAnalysisKlineRadarTopologyNodeKind = "gate" | "module" | "queue" | "stock";

export type StockAnalysisKlineRadarTopologyNode = {
  id: string;
  kind: StockAnalysisKlineRadarTopologyNodeKind;
  label: string;
  tone: StockAnalysisKlineRadarTone;
  count?: number;
  stockCode?: string;
};

export type StockAnalysisKlineRadarTopologyEdgeKind = "gates" | "feeds" | "routes";

export type StockAnalysisKlineRadarTopologyEdge = {
  id: string;
  from: string;
  to: string;
  kind: StockAnalysisKlineRadarTopologyEdgeKind;
  label: string;
  weight: number;
};

export type StockAnalysisKlineRadarTopology = {
  nodes: StockAnalysisKlineRadarTopologyNode[];
  edges: StockAnalysisKlineRadarTopologyEdge[];
  moduleCount: number;
  stockCount: number;
  edgeCount: number;
  multiSignalStockCount: number;
};

export type StockAnalysisKlineRadarItem = {
  key: string;
  queueKey: StockAnalysisKlineRadarQueueKey;
  stockCode: string;
  stockName: string;
  sectorCode?: string;
  sectorName?: string;
  rank?: number;
  signalLabel: string;
  sourceLabel: string;
  sourceModule: StockAnalysisKlineRadarSourceModule;
  detailSource: StockDetailSource;
  tone: StockAnalysisKlineRadarTone;
  scoreLabel?: string;
  evidence: string[];
};

export type StockAnalysisKlineRadarQueue = {
  key: StockAnalysisKlineRadarQueueKey;
  label: string;
  shortLabel: string;
  tone: StockAnalysisKlineRadarTone;
  count: number;
  items: StockAnalysisKlineRadarItem[];
  emptyDetail: string;
};

export type StockAnalysisKlineRadarSummary = {
  asOfDate: string | null;
  marketGateState: string | null;
  totalCount: number;
  opportunityCount: number;
  riskTriggerCount: number | null;
  riskWatchCount: number | null;
  riskUnavailableReason: string | null;
  pendingEvidenceItems: StockAnalysisKlineRadarItem[];
  focusItems: StockAnalysisKlineRadarItem[];
  queues: StockAnalysisKlineRadarQueue[];
  topology: StockAnalysisKlineRadarTopology;
};

const QUEUE_META: Record<
  StockAnalysisKlineRadarQueueKey,
  Pick<StockAnalysisKlineRadarQueue, "label" | "shortLabel" | "tone" | "emptyDetail">
> = {
  breakout: {
    label: "突破复核",
    shortLabel: "突破",
    tone: "positive",
    emptyDetail: "趋势候选未返回可复核突破样本。",
  },
  trend_continuation: {
    label: "续涨/回踩",
    shortLabel: "续涨",
    tone: "positive",
    emptyDetail: "新趋势与融合候选暂未返回样本。",
  },
  mean_reversion: {
    label: "超跌反转",
    shortLabel: "反转",
    tone: "warning",
    emptyDetail: "市场门控未进入 WARM 或超跌候选为空。",
  },
  risk_exit: {
    label: "风险预警",
    shortLabel: "风险",
    tone: "negative",
    emptyDetail: "当前未命中风险退出观察。",
  },
};

const SOURCE_MODULE_LABELS: Record<StockAnalysisKlineRadarSourceModule, string> = {
  stock_candidates: "Livermore 候选",
  fresh_trend_watchlist: "新趋势观察",
  uptrend_momentum_candidates: "上行动量",
  hybrid_fusion_candidates: "融合策略",
  mean_reversion_candidates: "超跌候选",
  "risk_exit.items": "风险退出",
  "risk_exit.watch_items": "风险观察",
};

function topologySourceNodeId(sourceModule: StockAnalysisKlineRadarSourceModule): string {
  return `module:${sourceModule}`;
}

function topologyQueueNodeId(queueKey: StockAnalysisKlineRadarQueueKey): string {
  return `queue:${queueKey}`;
}

function topologyStockNodeId(stockCode: string): string {
  return `stock:${stockCode}`;
}

function topologyEdgeId(from: string, to: string, kind: StockAnalysisKlineRadarTopologyEdgeKind): string {
  return `${kind}:${from}->${to}`;
}

function upsertTopologyNode(
  nodes: Map<string, StockAnalysisKlineRadarTopologyNode>,
  node: StockAnalysisKlineRadarTopologyNode,
): void {
  const current = nodes.get(node.id);
  if (!current) {
    nodes.set(node.id, node);
    return;
  }
  nodes.set(node.id, {
    ...current,
    count: Math.max(current.count ?? 0, node.count ?? 0),
    tone: current.tone === "negative" || node.tone === "negative" ? "negative" : current.tone,
  });
}

function upsertTopologyEdge(
  edges: Map<string, StockAnalysisKlineRadarTopologyEdge>,
  edge: StockAnalysisKlineRadarTopologyEdge,
): void {
  const current = edges.get(edge.id);
  if (!current) {
    edges.set(edge.id, edge);
    return;
  }
  edges.set(edge.id, {
    ...current,
    weight: current.weight + edge.weight,
  });
}

function finiteNumber(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatNumber(value: number | null | undefined, digits = 2): string | null {
  const parsed = finiteNumber(value);
  if (parsed == null) return null;
  return parsed.toFixed(digits);
}

function formatSignedRatio(value: number | null | undefined, digits = 1): string | null {
  const parsed = finiteNumber(value);
  if (parsed == null) return null;
  const pct = parsed * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(digits)}%`;
}

function appendEvidence(target: string[], label: string, value: string | null | undefined): void {
  if (!value) return;
  target.push(`${label} ${value}`);
}

function buildBreakoutItem(item: LivermoreStockCandidateItem): StockAnalysisKlineRadarItem {
  const distanceToBreakout =
    finiteNumber(item.breakout_level) && item.breakout_level !== 0
      ? formatSignedRatio((item.close - item.breakout_level) / item.breakout_level)
      : null;
  const evidence: string[] = [];
  appendEvidence(evidence, "距突破", distanceToBreakout);
  appendEvidence(evidence, "MA20", formatNumber(item.ma20));
  appendEvidence(evidence, "量能", formatNumber(item.abnormal_turnover));
  appendEvidence(evidence, "强度", formatSignedRatio(item.close_strength, 0));

  return {
    key: `breakout:${item.stock_code}`,
    queueKey: "breakout",
    stockCode: item.stock_code,
    stockName: item.stock_name,
    sectorCode: item.sector_code,
    sectorName: item.sector_name,
    rank: item.rank,
    signalLabel: distanceToBreakout && distanceToBreakout.startsWith("+") ? "平台突破" : "临近突破",
    sourceLabel: "Livermore 候选",
    sourceModule: "stock_candidates",
    detailSource: "livermore",
    tone: "positive",
    scoreLabel: item.factor_score != null ? `因子 ${formatNumber(item.factor_score, 3)}` : undefined,
    evidence,
  };
}

function buildFreshTrendItem(item: FreshTrendWatchlistCandidateItem): StockAnalysisKlineRadarItem {
  const evidence: string[] = [];
  appendEvidence(evidence, "20日", formatSignedRatio(item.return_20d));
  appendEvidence(evidence, "60日", formatSignedRatio(item.return_60d));
  appendEvidence(evidence, "距MA20", formatSignedRatio(item.close_to_ma20));
  appendEvidence(evidence, "量比", formatNumber(item.amount_ratio));

  return {
    key: `fresh:${item.stock_code}`,
    queueKey: "trend_continuation",
    stockCode: item.stock_code,
    stockName: item.stock_name,
    sectorCode: item.sector_code,
    sectorName: item.sector_name,
    rank: item.rank,
    signalLabel: item.close_to_ma20 >= 0 ? "续涨确认" : "回踩观察",
    sourceLabel: "新趋势观察",
    sourceModule: "fresh_trend_watchlist",
    detailSource: "fresh_trend_watchlist",
    tone: "positive",
    scoreLabel: `评分 ${formatNumber(item.score) ?? "待补"}`,
    evidence,
  };
}

function buildUptrendItem(item: UptrendMomentumCandidateItem): StockAnalysisKlineRadarItem {
  const evidence: string[] = [];
  appendEvidence(evidence, "20日", formatSignedRatio(item.return_20d));
  appendEvidence(evidence, "120日", formatSignedRatio(item.return_120d));
  appendEvidence(evidence, "距MA20", formatSignedRatio(item.close_to_ma20));
  appendEvidence(evidence, "量比", formatNumber(item.amount_ratio));

  return {
    key: `uptrend:${item.stock_code}`,
    queueKey: "trend_continuation",
    stockCode: item.stock_code,
    stockName: item.stock_name,
    sectorCode: item.sector_code,
    sectorName: item.sector_name,
    rank: item.rank,
    signalLabel: "趋势延续",
    sourceLabel: "上行动量",
    sourceModule: "uptrend_momentum_candidates",
    detailSource: "livermore",
    tone: "positive",
    scoreLabel: `评分 ${formatNumber(item.score) ?? "待补"}`,
    evidence,
  };
}

function hasHybridEvidenceSource(item: HybridFusionCandidateItem, acceptedSources: string[]): boolean {
  const sourceKinds = item.evidence?.source_kinds;
  if (!Array.isArray(sourceKinds)) return false;
  return sourceKinds.some(
    (sourceKind) => typeof sourceKind === "string" && acceptedSources.includes(sourceKind),
  );
}

function buildHybridFusionItem(item: HybridFusionCandidateItem): StockAnalysisKlineRadarItem {
  const evidence: string[] = [];
  const hasPriceEvidence = hasHybridEvidenceSource(item, ["stock_candidate", "theme_breakout"]);
  const hasAttentionEvidence = hasHybridEvidenceSource(item, ["theme_breakout"]);

  appendEvidence(evidence, "价格确认", hasPriceEvidence ? formatNumber(item.price_confirm_score) : "待补证");
  appendEvidence(evidence, "关注度", hasAttentionEvidence ? formatNumber(item.attention_score) : "待补证");
  appendEvidence(evidence, "拥挤惩罚", hasPriceEvidence ? formatNumber(item.crowding_penalty) : "待补证");

  return {
    key: `fusion:${item.stock_code}`,
    queueKey: "trend_continuation",
    stockCode: item.stock_code,
    stockName: item.stock_name,
    sectorCode: item.sector_code,
    sectorName: item.sector_name,
    rank: item.rank,
    signalLabel: item.fusion_action === "watch" ? "融合观察" : "复核观察",
    sourceLabel: "融合策略",
    sourceModule: "hybrid_fusion_candidates",
    detailSource: "hybrid_fusion",
    tone: "positive",
    scoreLabel: `融合 ${formatNumber(item.fusion_score) ?? "待补"}`,
    evidence,
  };
}

function buildMeanReversionItem(item: MeanReversionCandidateItem): StockAnalysisKlineRadarItem {
  const evidence: string[] = [];
  appendEvidence(evidence, "20日回撤", formatSignedRatio(item.drawdown_20d));
  appendEvidence(evidence, "60日回撤", formatSignedRatio(item.drawdown_60d));
  appendEvidence(evidence, "量比", formatNumber(item.vol_ratio));
  appendEvidence(evidence, "强度", formatSignedRatio(item.close_strength, 0));

  return {
    key: `mean-reversion:${item.stock_code}`,
    queueKey: "mean_reversion",
    stockCode: item.stock_code,
    stockName: item.stock_name,
    sectorCode: item.sector_code,
    sectorName: item.sector_name,
    rank: item.rank,
    signalLabel: "超跌反转",
    sourceLabel: "超跌候选",
    sourceModule: "mean_reversion_candidates",
    detailSource: "mean_reversion",
    tone: "warning",
    scoreLabel: `评分 ${formatNumber(item.score) ?? "待补"}`,
    evidence,
  };
}

function buildRiskExitItem(item: LivermoreRiskExitItem): StockAnalysisKlineRadarItem {
  const evidence: string[] = [];
  appendEvidence(evidence, "收盘", formatNumber(item.latest_close));
  appendEvidence(evidence, "EMA10", formatNumber(item.latest_ema10));
  appendEvidence(evidence, "持有", `${item.bars_since_entry} 根`);

  return {
    key: `risk-triggered:${item.stock_code}`,
    queueKey: "risk_exit",
    stockCode: item.stock_code,
    stockName: item.stock_name,
    signalLabel: "退出触发",
    sourceLabel: "风险退出",
    sourceModule: "risk_exit.items",
    detailSource: "risk_exit",
    tone: "negative",
    scoreLabel: item.reason || undefined,
    evidence,
  };
}

function buildRiskWatchItem(item: LivermoreRiskExitWatchItem): StockAnalysisKlineRadarItem {
  const evidence: string[] = [];
  appendEvidence(evidence, "收盘", formatNumber(item.latest_close));
  appendEvidence(evidence, "观察价", formatNumber(item.exit_watch_price));
  appendEvidence(evidence, "EMA10", formatNumber(item.latest_ema10));

  return {
    key: `risk-watch:${item.stock_code}`,
    queueKey: "risk_exit",
    stockCode: item.stock_code,
    stockName: item.stock_name,
    signalLabel: item.triggered ? "退出触发" : "接近退出",
    sourceLabel: "风险观察",
    sourceModule: "risk_exit.watch_items",
    detailSource: "risk_exit",
    tone: item.triggered ? "negative" : "warning",
    evidence,
  };
}

function limitUniqueByStock<T extends StockAnalysisKlineRadarItem>(items: T[], limit: number): T[] {
  const seen = new Set<string>();
  const result: T[] = [];
  for (const item of items) {
    if (seen.has(item.stockCode)) continue;
    seen.add(item.stockCode);
    result.push(item);
    if (result.length >= limit) break;
  }
  return result;
}

function makeQueue(
  key: StockAnalysisKlineRadarQueueKey,
  items: StockAnalysisKlineRadarItem[],
): StockAnalysisKlineRadarQueue {
  const meta = QUEUE_META[key];
  return {
    key,
    ...meta,
    count: items.length,
    items,
  };
}

export function buildStockAnalysisKlineRadarTopology(
  payload: LivermoreStrategyPayload | null | undefined,
  queues: StockAnalysisKlineRadarQueue[],
): StockAnalysisKlineRadarTopology {
  const nodes = new Map<string, StockAnalysisKlineRadarTopologyNode>();
  const edges = new Map<string, StockAnalysisKlineRadarTopologyEdge>();
  const stockSignalCounts = new Map<string, number>();

  if (payload) {
    upsertTopologyNode(nodes, {
      id: "gate:market",
      kind: "gate",
      label: `market_gate:${payload.market_gate.state}`,
      tone: payload.market_gate.state === "WARM" ? "positive" : "warning",
    });
  }

  for (const queue of queues) {
    const queueNodeId = topologyQueueNodeId(queue.key);
    upsertTopologyNode(nodes, {
      id: queueNodeId,
      kind: "queue",
      label: queue.label,
      tone: queue.tone,
      count: queue.count,
    });

    if (payload && queue.key === "mean_reversion") {
      const edgeId = topologyEdgeId("gate:market", queueNodeId, "gates");
      upsertTopologyEdge(edges, {
        id: edgeId,
        from: "gate:market",
        to: queueNodeId,
        kind: "gates",
        label: payload.market_gate.state === "WARM" ? "enabled" : `blocked:${payload.market_gate.state}`,
        weight: 1,
      });
    }

    for (const item of queue.items) {
      const moduleNodeId = topologySourceNodeId(item.sourceModule);
      const stockNodeId = topologyStockNodeId(item.stockCode);
      upsertTopologyNode(nodes, {
        id: moduleNodeId,
        kind: "module",
        label: SOURCE_MODULE_LABELS[item.sourceModule],
        tone: item.tone,
      });
      upsertTopologyNode(nodes, {
        id: stockNodeId,
        kind: "stock",
        label: item.stockName,
        tone: item.tone,
        stockCode: item.stockCode,
      });
      upsertTopologyEdge(edges, {
        id: topologyEdgeId(moduleNodeId, queueNodeId, "feeds"),
        from: moduleNodeId,
        to: queueNodeId,
        kind: "feeds",
        label: item.sourceModule,
        weight: 1,
      });
      upsertTopologyEdge(edges, {
        id: topologyEdgeId(queueNodeId, stockNodeId, "routes"),
        from: queueNodeId,
        to: stockNodeId,
        kind: "routes",
        label: item.signalLabel,
        weight: 1,
      });
      stockSignalCounts.set(item.stockCode, (stockSignalCounts.get(item.stockCode) ?? 0) + 1);
    }
  }

  const topologyNodes = [...nodes.values()];
  const topologyEdges = [...edges.values()];

  return {
    nodes: topologyNodes,
    edges: topologyEdges,
    moduleCount: topologyNodes.filter((node) => node.kind === "module").length,
    stockCount: topologyNodes.filter((node) => node.kind === "stock").length,
    edgeCount: topologyEdges.length,
    multiSignalStockCount: [...stockSignalCounts.values()].filter((count) => count > 1).length,
  };
}

export function buildStockAnalysisKlineRadar(
  payload: LivermoreStrategyPayload | null | undefined,
): StockAnalysisKlineRadarSummary {
  if (!payload) {
    const queues = (Object.keys(QUEUE_META) as StockAnalysisKlineRadarQueueKey[]).map((key) => makeQueue(key, []));
    return {
      asOfDate: null,
      marketGateState: null,
      totalCount: 0,
      opportunityCount: 0,
      riskTriggerCount: 0,
      riskWatchCount: 0,
      riskUnavailableReason: null,
      pendingEvidenceItems: [],
      focusItems: [],
      queues,
      topology: buildStockAnalysisKlineRadarTopology(payload, queues),
    };
  }

  const breakoutItems = limitUniqueByStock(
    (payload.stock_candidates?.items ?? []).map(buildBreakoutItem),
    5,
  );
  const hybridModuleState = payload.module_states?.find((state) => state.key === "hybrid_fusion");
  const hybridIsEvidenceOnly = Boolean(
    hybridModuleState &&
      (hybridModuleState.render_mode === "evidence_only" || hybridModuleState.excludes_from_primary),
  );
  const hybridItems = (payload.hybrid_fusion_candidates?.items ?? []).map(buildHybridFusionItem);
  const pendingEvidenceItems = hybridIsEvidenceOnly
    ? limitUniqueByStock(
        hybridItems.map((item) => ({
          ...item,
          signalLabel: "待补证观察",
          tone: "warning" as const,
          evidence: [],
        })),
        5,
      )
    : [];
  const trendItems = limitUniqueByStock(
    [
      ...(payload.fresh_trend_watchlist?.items ?? []).map(buildFreshTrendItem),
      ...(payload.uptrend_momentum_candidates?.items ?? []).map(buildUptrendItem),
      ...(hybridIsEvidenceOnly ? [] : hybridItems),
    ],
    5,
  );
  const meanReversionItems =
    payload.market_gate.state === "WARM"
      ? limitUniqueByStock((payload.mean_reversion_candidates?.items ?? []).map(buildMeanReversionItem), 5)
      : [];
  const riskUnsupported = payload.unsupported_outputs?.find((output) => output.key === "risk_exit");
  const triggeredRiskItems = (payload.risk_exit?.items ?? []).map(buildRiskExitItem);
  const watchRiskItems = (payload.risk_exit?.watch_items ?? []).map(buildRiskWatchItem);
  const riskItems = riskUnsupported ? [] : [...triggeredRiskItems, ...watchRiskItems].slice(0, 5);

  const queues = [
    makeQueue("breakout", breakoutItems),
    makeQueue("trend_continuation", trendItems),
    makeQueue("mean_reversion", meanReversionItems),
    makeQueue("risk_exit", riskItems),
  ];
  const totalCount = queues.reduce((sum, queue) => sum + queue.count, 0);

  return {
    asOfDate: payload.as_of_date,
    marketGateState: payload.market_gate.state,
    totalCount,
    opportunityCount: Math.max(totalCount - riskItems.length, 0),
    riskTriggerCount: riskUnsupported
      ? null
      : (payload.risk_exit?.signal_count ?? triggeredRiskItems.length),
    riskWatchCount: riskUnsupported ? null : watchRiskItems.length,
    riskUnavailableReason: riskUnsupported ? riskExitBlockedSummary(riskUnsupported.reason) : null,
    pendingEvidenceItems,
    focusItems: [...riskItems, ...breakoutItems, ...trendItems, ...meanReversionItems].slice(0, 6),
    queues,
    topology: buildStockAnalysisKlineRadarTopology(payload, queues),
  };
}
