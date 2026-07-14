import type {
  BacktestWindowSummary,
  LivermoreCandidateHistoryHorizonKey,
  LivermoreCandidateHistoryHorizonStats,
  LivermoreCandidateHistoryPayload,
  LivermoreProxyCostBasis,
} from "../../../api/contracts";

const historicalSourceGapReasonCodes = new Set([
  "missing_daily_limit_flags",
  "missing_required_source_table",
]);

function replayReasonAffectsSignal(signalKinds: string[], signalKind?: string): boolean {
  return !signalKind || signalKinds.length === 0 || signalKinds.includes(signalKind);
}

export function backtestSourceGapDateCount(
  window: BacktestWindowSummary | null | undefined,
  signalKind?: string,
): number {
  if (!window) return 0;
  const classifiedCount = window.date_reasons.filter(
    (item) =>
      item.status === "unsupported" &&
      historicalSourceGapReasonCodes.has(item.reason_code) &&
      replayReasonAffectsSignal(item.signal_kinds, signalKind),
  ).length;
  return classifiedCount;
}

export function backtestPendingDateCount(
  window: BacktestWindowSummary | null | undefined,
  signalKind?: string,
): number {
  if (!window) return 0;
  const classifiedCount = window.date_reasons.filter(
    (item) =>
      item.status === "pending" && replayReasonAffectsSignal(item.signal_kinds, signalKind),
  ).length;
  if (classifiedCount > 0) return classifiedCount;
  return !signalKind && window.date_reasons.length === 0 ? window.replay_dates_pending : 0;
}

export function backtestUnsupportedDateCount(
  window: BacktestWindowSummary | null | undefined,
  signalKind?: string,
): number {
  if (!window) return 0;
  const classifiedCount = window.date_reasons.filter(
    (item) =>
      item.status === "unsupported" && replayReasonAffectsSignal(item.signal_kinds, signalKind),
  ).length;
  if (classifiedCount > 0) return classifiedCount;
  return !signalKind && window.status === "unsupported" && window.date_reasons.length === 0
    ? window.replay_dates_unsupported
    : 0;
}

export const strategyBacktestOrder = [
  "hybrid_fusion",
  "stock_candidate",
  "factor_screen",
  "theme_breakout",
  "mean_reversion",
] as const;

const strategyBacktestLabels: Record<string, string> = {
  hybrid_fusion: "融合策略",
  stock_candidate: "趋势突破",
  factor_screen: "多因子",
  theme_breakout: "题材突变",
  mean_reversion: "超跌反弹",
};

export const strategyBacktestHorizons: LivermoreCandidateHistoryHorizonKey[] = [
  "return_1d",
  "return_5d",
  "return_10d",
  "return_20d",
];

export const strategyBacktestHorizonLabels: Record<LivermoreCandidateHistoryHorizonKey, string> = {
  return_1d: "T+1 胜率 / 均值 / 样本",
  return_5d: "T+5 胜率 / 均值 / 样本",
  return_10d: "T+10 胜率 / 均值 / 样本",
  return_20d: "T+20 胜率 / 均值 / 样本",
};

export const strategyBacktestHorizonShortLabels: Record<LivermoreCandidateHistoryHorizonKey, string> = {
  return_1d: "T+1",
  return_5d: "T+5",
  return_10d: "T+10",
  return_20d: "T+20",
};

const strategyBacktestMarketStateOrder = ["OFF", "WARM", "HOT", "OVERHEAT", "PENDING_DATA", "NO_DATA", "STALE"] as const;

export const strategyBacktestExecutionBasisLabel = "T+1\u5f00\u76d8\u6210\u4ea4\u00b7\u542b\u8d39\u00b7\u590d\u6743";
export const strategyBacktestLegacyBasisLabel = "\u4fe1\u53f7\u65e5\u6536\u76d8\u00b7\u65e7forward\u6536\u76ca";

export function formatBacktestPercent(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "待补";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatBacktestSignedPercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "待补";
  const pct = value * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

/** Returns null when the backend omits cost_basis (older payloads), so callers can skip the line entirely. */
export function formatCostBasisLabel(costBasis: LivermoreProxyCostBasis | null | undefined): string | null {
  if (!costBasis || !Number.isFinite(costBasis.round_trip_cost_rate)) return null;
  return `双边成本 ${formatBacktestPercent(costBasis.round_trip_cost_rate, 2)}（含双向滑点）`;
}

export function backtestStatsText(stats: LivermoreCandidateHistoryHorizonStats | undefined): string {
  if (!stats || stats.available_count <= 0) return "待补";
  return `${formatBacktestPercent(stats.win_rate)} / ${formatBacktestSignedPercent(stats.avg_return)} / ${stats.available_count}条`;
}

const maturityHorizonByBacktestHorizon = {
  return_1d: "1d",
  return_5d: "5d",
  return_10d: "10d",
  return_20d: "20d",
} as const satisfies Record<LivermoreCandidateHistoryHorizonKey, "1d" | "5d" | "10d" | "20d">;

function strategyBacktestStatsText(input: {
  payload: LivermoreCandidateHistoryPayload | null;
  kind: string;
  horizon: LivermoreCandidateHistoryHorizonKey;
  stats: LivermoreCandidateHistoryHorizonStats | undefined;
  selectedCount: number;
}): string {
  if (input.stats && input.stats.available_count > 0) return backtestStatsText(input.stats);
  if (!input.payload) return "接口未提供";

  const maturityKey = maturityHorizonByBacktestHorizon[input.horizon];
  const matchingItems = input.payload.items.filter(
    (item) => (item.signal_kind ?? "stock_candidate") === input.kind,
  );
  const maturityUnclassified = (item: (typeof matchingItems)[number]) =>
    Boolean(
      item.forward_maturity &&
        (item.forward_maturity.classification_available === false ||
          item.forward_maturity.source_status === "unavailable"),
    );
  const unclassifiedCount = matchingItems.filter(maturityUnclassified).length;

  const statusCounts = new Map<string, number>();
  for (const item of matchingItems) {
    if (maturityUnclassified(item)) continue;
    const status = item.forward_maturity?.horizons[maturityKey]?.status;
    if (!status || status === "complete") continue;
    statusCounts.set(status, (statusCounts.get(status) ?? 0) + 1);
  }
  const statusLabels = [
    ["raw_matured_adjustment_missing", "复权待补"],
    ["matured_missing_bar", "历史行情缺口"],
    ["natural_pending", "自然待成熟"],
    ["partial_halt", "部分停牌"],
  ] as const;
  const maturityParts: Array<{ label: string; count: number }> = statusLabels.flatMap(([status, label]) => {
    const count = statusCounts.get(status) ?? 0;
    return count > 0 ? [{ label, count }] : [];
  });
  if (unclassifiedCount > 0) {
    maturityParts.push({ label: "成熟分类不可用", count: unclassifiedCount });
  }
  if (maturityParts.length === 1) {
    return `${maturityParts[0].label} · ${maturityParts[0].count}条`;
  }
  if (maturityParts.length > 1) {
    return maturityParts.map((item) => `${item.label} ${item.count}条`).join(" / ");
  }

  const window = input.payload.backtest_window_summary;
  const sourceGapDateCount = backtestSourceGapDateCount(window, input.kind);
  if (sourceGapDateCount > 0) {
    return `历史源不足 · ${sourceGapDateCount}日`;
  }
  const pendingDateCount = backtestPendingDateCount(window, input.kind);
  if (pendingDateCount > 0) {
    return `自然待成熟 · ${pendingDateCount}日`;
  }
  const unsupportedDateCount = backtestUnsupportedDateCount(window, input.kind);
  if (unsupportedDateCount > 0) {
    return `窗口不支持 · ${unsupportedDateCount}日`;
  }
  if (!input.stats && input.selectedCount <= 0) return "本窗口无样本";
  return input.stats ? "成熟度未提供" : "接口未提供";
}

function strategyBacktestMarketStateStatsText(
  payload: LivermoreCandidateHistoryPayload | null,
  stats: LivermoreCandidateHistoryHorizonStats | undefined,
): string {
  if (stats && stats.available_count > 0) return backtestStatsText(stats);
  if (!payload) return "接口未提供";
  return stats ? "市场状态成熟度未提供" : "接口未提供";
}

function resolveStrategyBacktestSignalStats(payload: LivermoreCandidateHistoryPayload | null) {
  const summary = payload?.summary ?? null;
  const decisionStats = summary?.decision_usable_stats ?? null;
  const executionStats = summary?.execution_usable_stats ?? null;
  if (executionStats) {
    return (
      executionStats.by_signal_kind_horizon_usable_stats ??
      executionStats.by_signal_kind_horizon_stats ??
      {}
    );
  }
  return (
    decisionStats?.by_signal_kind_horizon_usable_stats ??
    summary?.by_signal_kind_horizon_usable_stats ??
    decisionStats?.by_signal_kind_horizon_stats ??
    summary?.by_signal_kind_horizon_stats ??
    {}
  );
}

export function resolveStrategyBacktestMetricBasisLabel(payload: LivermoreCandidateHistoryPayload | null): string {
  const executionStats = payload?.summary?.execution_usable_stats ?? null;
  if (!executionStats) return strategyBacktestLegacyBasisLabel;
  if (executionStats.metric_basis === "net_next_open_adj") return strategyBacktestExecutionBasisLabel;
  return executionStats.basis_label?.trim() || strategyBacktestExecutionBasisLabel;
}

export function strategyDisplayLabel(label: string | null | undefined, signalKind?: string | null): string {
  const value = label?.trim() || signalKind?.trim() || "";
  const normalized = value.toLowerCase().replace(/[\s-]+/g, "_");
  if (strategyBacktestLabels[normalized]) return strategyBacktestLabels[normalized];
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
    return "策略待确认";
  }
  return value || "策略待确认";
}

export function strategyBacktestKindLabel(kind: string): string {
  return strategyDisplayLabel(kind);
}

export function buildStrategyBacktestRows(payload: LivermoreCandidateHistoryPayload | null) {
  const summary = payload?.summary ?? null;
  const decisionStats = summary?.decision_usable_stats ?? null;
  const executionStats = summary?.execution_usable_stats ?? null;
  const bySignalKind = executionStats
    ? executionStats.by_signal_kind ?? {}
    : decisionStats?.by_signal_kind ?? summary?.by_signal_kind ?? {};
  const bySignalStats = resolveStrategyBacktestSignalStats(payload);
  const discoveredKinds = Object.keys(bySignalStats).filter(
    (key) => !(strategyBacktestOrder as readonly string[]).includes(key),
  );
  return [...strategyBacktestOrder, ...discoveredKinds].map((kind) => {
    const statsByHorizon = bySignalStats[kind] ?? {};
    const selectedCount = bySignalKind[kind] ?? 0;
    return {
      kind,
      label: strategyBacktestKindLabel(kind),
      count: selectedCount,
      stats: {
        return_1d: strategyBacktestStatsText({ payload, kind, horizon: "return_1d", stats: statsByHorizon.return_1d, selectedCount }),
        return_5d: strategyBacktestStatsText({ payload, kind, horizon: "return_5d", stats: statsByHorizon.return_5d, selectedCount }),
        return_10d: strategyBacktestStatsText({ payload, kind, horizon: "return_10d", stats: statsByHorizon.return_10d, selectedCount }),
        return_20d: strategyBacktestStatsText({ payload, kind, horizon: "return_20d", stats: statsByHorizon.return_20d, selectedCount }),
      },
    };
  });
}

export function resolveStrategyBacktestSampleCount(payload: LivermoreCandidateHistoryPayload | null): number {
  const summary = payload?.summary ?? null;
  const decisionStats = summary?.decision_usable_stats ?? null;
  const executionStats = summary?.execution_usable_stats ?? null;
  const horizonStats = executionStats
    ? executionStats.horizon_usable_stats
    : decisionStats?.horizon_usable_stats ?? summary?.horizon_usable_stats ?? summary?.horizon_stats;

  if (horizonStats) {
    return Math.max(
      0,
      ...strategyBacktestHorizons.map((horizon) => horizonStats[horizon]?.available_count ?? 0),
    );
  }

  const bySignalStats = resolveStrategyBacktestSignalStats(payload);
  return Math.max(
    0,
    ...strategyBacktestHorizons.map((horizon) =>
      Object.values(bySignalStats).reduce(
        (total, statsByHorizon) => total + (statsByHorizon[horizon]?.available_count ?? 0),
        0,
      ),
    ),
  );
}

export function buildStrategyBacktestMarketStateRows(payload: LivermoreCandidateHistoryPayload | null) {
  const summary = payload?.summary ?? null;
  const decisionStats = summary?.decision_usable_stats ?? null;
  const executionStats = summary?.execution_usable_stats ?? null;
  const byMarketState = executionStats
    ? summary?.by_market_state_signal_kind_execution_stats ?? {}
    : decisionStats?.by_market_state_signal_kind_horizon_stats ??
      summary?.by_market_state_signal_kind_horizon_stats ??
      {};
  const orderedStates = strategyBacktestMarketStateOrder.filter((state) => state in byMarketState);
  const discoveredStates = Object.keys(byMarketState)
    .filter((state) => !(strategyBacktestMarketStateOrder as readonly string[]).includes(state))
    .sort();

  return [...orderedStates, ...discoveredStates].flatMap((marketState) => {
    const bySignalStats = byMarketState[marketState] ?? {};
    const discoveredKinds = Object.keys(bySignalStats).filter(
      (key) => !(strategyBacktestOrder as readonly string[]).includes(key),
    );

    return [...strategyBacktestOrder, ...discoveredKinds]
      .filter((kind) => kind in bySignalStats)
      .map((kind) => {
        const statsByHorizon = bySignalStats[kind] ?? {};
        return {
          marketState,
          kind,
          label: strategyBacktestKindLabel(kind),
          stats: {
            return_1d: strategyBacktestMarketStateStatsText(payload, statsByHorizon.return_1d),
            return_5d: strategyBacktestMarketStateStatsText(payload, statsByHorizon.return_5d),
            return_10d: strategyBacktestMarketStateStatsText(payload, statsByHorizon.return_10d),
            return_20d: strategyBacktestMarketStateStatsText(payload, statsByHorizon.return_20d),
          },
        };
      });
  });
}
