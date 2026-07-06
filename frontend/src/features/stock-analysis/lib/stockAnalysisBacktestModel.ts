import type {
  LivermoreCandidateHistoryHorizonKey,
  LivermoreCandidateHistoryHorizonStats,
  LivermoreCandidateHistoryPayload,
} from "../../../api/contracts";

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

export function backtestStatsText(stats: LivermoreCandidateHistoryHorizonStats | undefined): string {
  if (!stats || stats.available_count <= 0) return "待补";
  return `${formatBacktestPercent(stats.win_rate)} / ${formatBacktestSignedPercent(stats.avg_return)} / ${stats.available_count}条`;
}

function resolveStrategyBacktestSignalStats(payload: LivermoreCandidateHistoryPayload | null) {
  const summary = payload?.summary ?? null;
  const decisionStats = summary?.decision_usable_stats ?? null;
  const executionStats = summary?.execution_usable_stats ?? null;
  return (
    executionStats?.by_signal_kind_horizon_usable_stats ??
    executionStats?.by_signal_kind_horizon_stats ??
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
  const bySignalKind = executionStats?.by_signal_kind ?? decisionStats?.by_signal_kind ?? summary?.by_signal_kind ?? {};
  const bySignalStats = resolveStrategyBacktestSignalStats(payload);
  const discoveredKinds = Object.keys(bySignalStats).filter(
    (key) => !(strategyBacktestOrder as readonly string[]).includes(key),
  );
  return [...strategyBacktestOrder, ...discoveredKinds].map((kind) => {
    const statsByHorizon = bySignalStats[kind] ?? {};
    return {
      kind,
      label: strategyBacktestKindLabel(kind),
      count: bySignalKind[kind] ?? 0,
      stats: {
        return_1d: backtestStatsText(statsByHorizon.return_1d),
        return_5d: backtestStatsText(statsByHorizon.return_5d),
        return_10d: backtestStatsText(statsByHorizon.return_10d),
        return_20d: backtestStatsText(statsByHorizon.return_20d),
      },
    };
  });
}

export function resolveStrategyBacktestSampleCount(payload: LivermoreCandidateHistoryPayload | null): number {
  const summary = payload?.summary ?? null;
  const decisionStats = summary?.decision_usable_stats ?? null;
  const executionStats = summary?.execution_usable_stats ?? null;
  const horizonStats =
    executionStats?.horizon_usable_stats ??
    decisionStats?.horizon_usable_stats ??
    summary?.horizon_usable_stats ??
    summary?.horizon_stats;

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
  const byMarketState =
    summary?.by_market_state_signal_kind_execution_stats ??
    decisionStats?.by_market_state_signal_kind_horizon_stats ??
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
            return_1d: backtestStatsText(statsByHorizon.return_1d),
            return_5d: backtestStatsText(statsByHorizon.return_5d),
            return_10d: backtestStatsText(statsByHorizon.return_10d),
            return_20d: backtestStatsText(statsByHorizon.return_20d),
          },
        };
      });
  });
}
