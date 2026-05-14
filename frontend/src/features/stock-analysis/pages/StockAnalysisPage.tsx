import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Collapse, DatePicker, Drawer, Tabs, Typography } from "antd";
import dayjs from "dayjs";

import { useApiClient } from "../../../api/client";
import type {
  LivermoreCandidateHistoryHorizonKey,
  LivermoreCandidateHistoryHorizonStats,
  LivermoreCandidateHistoryPayload,
  LivermoreSectorRankSeriesPoint,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyScorePayload,
} from "../../../api/contracts";
import {
  AnalysisGrid,
  DataStatusStrip,
  KpiBand,
  PageDecisionHero,
  PageV2Shell,
} from "../../../components/page/PagePrimitives";
import { AgentPanel } from "../../agent/AgentPanel";
import {
  buildCandidateReviewQueue,
  buildClosedLoopSummary,
  buildDataBoundarySummary,
  buildDecisionSummary,
  buildInlineMetaSegments,
  buildMarketStateCard,
  buildRiskExitRows,
  buildSectorFilterSummary,
  buildSectorRows,
  buildSectorTableSortComparator,
  buildSectorViewModel,
  buildStockAnalysisEvidenceStatus,
  buildStockAnalysisEventMonitorRows,
  buildStockAnalysisKpiStrip,
  buildThemeBreakoutCards,
  buildThemeBreakoutReviewItems,
  buildThemeEvidenceStateRows,
} from "../lib/stockAnalysisPageModel";
import type { StockSectorRow, StockSectorViewKind } from "../lib/stockAnalysisPageModel";
import { buildStockAnalysisAgentPageContext } from "../lib/buildStockAnalysisAgentPageContext";
import { buildConsensusSummary, consensusStrategyLabel, lookupStockStrategyRanks } from "../lib/buildConsensusSummary";
import { StockDetailDrawer } from "../components/StockDetailDrawer";
import { stockAnalysisPageCssVars } from "../lib/stockAnalysisTokens";
import "./StockAnalysisPage.css";

const { Text } = Typography;

function errorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pass: "通过",
    fail: "未通过",
    missing: "缺数据",
    stale: "已陈旧",
  };
  return labels[status] ?? status;
}
function riskStatusLabel(status: "triggered" | "watch") {
  return status === "triggered" ? "触发复核" : "观察中";
}

const sectorViewTabs: { key: StockSectorViewKind; label: string }[] = [
  { key: "score", label: "综合得分" },
  { key: "pctchange", label: "平均涨跌幅" },
  { key: "turnover", label: "换手活跃度" },
  { key: "amplitude", label: "波动振幅" },
];

const patternRank: Record<string, number> = {
  突破: 0,
  回踩: 1,
  缩量盘整: 2,
  待补: 3,
};

type SectorSortKey =
  | "rank"
  | "sectorCode"
  | "sectorName"
  | "score"
  | "pctChange"
  | "turnover"
  | "amplitude"
  | "constituentCount";

function sectorRankUnavailable(strategyPayload: { sector_rank?: { formula_version?: string; items?: unknown[] } } | null) {
  const items = strategyPayload?.sector_rank?.items ?? [];
  const fv = strategyPayload?.sector_rank?.formula_version;
  return items.length === 0 || fv == null || String(fv).trim() === "";
}

function latestSectorSeriesTableRows(series: LivermoreSectorRankSeriesPoint[]): LivermoreSectorRankSeriesPoint[] {
  const byCode = new Map<string, LivermoreSectorRankSeriesPoint>();
  for (const row of series) {
    const cur = byCode.get(row.sector_code);
    if (!cur || row.trade_date > cur.trade_date) {
      byCode.set(row.sector_code, row);
    }
  }
  return Array.from(byCode.values()).sort((a, b) => {
    const ra = a.rank ?? 9999;
    const rb = b.rank ?? 9999;
    return ra - rb;
  });
}

const strategyBacktestOrder = ["stock_candidate", "factor_screen", "theme_breakout", "mean_reversion"] as const;

const strategyBacktestLabels: Record<string, string> = {
  stock_candidate: "趋势突破",
  factor_screen: "多因子",
  theme_breakout: "题材突变",
  mean_reversion: "超跌反弹",
};

const strategyBacktestHorizons: LivermoreCandidateHistoryHorizonKey[] = ["return_1d", "return_5d", "return_20d"];
const strategyBacktestHorizonLabels: Record<LivermoreCandidateHistoryHorizonKey, string> = {
  return_1d: "T+1 胜率 / 均值 / 样本",
  return_5d: "T+5 胜率 / 均值 / 样本",
  return_20d: "T+20 胜率 / 均值 / 样本",
};
const strategyBacktestMarketStateOrder = ["OFF", "WARM", "HOT", "OVERHEAT", "PENDING_DATA", "NO_DATA", "STALE"] as const;

function formatBacktestPercent(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "待补";
  return `${(value * 100).toFixed(digits)}%`;
}

function formatBacktestSignedPercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "待补";
  const pct = value * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

function backtestStatsText(stats: LivermoreCandidateHistoryHorizonStats | undefined): string {
  if (!stats || stats.available_count <= 0) return "待补";
  return `${formatBacktestPercent(stats.win_rate)} / ${formatBacktestSignedPercent(stats.avg_return)} / ${stats.available_count}条`;
}

function resolveStrategyBacktestSignalStats(payload: LivermoreCandidateHistoryPayload | null) {
  const summary = payload?.summary ?? null;
  const decisionStats = summary?.decision_usable_stats ?? null;
  return (
    decisionStats?.by_signal_kind_horizon_usable_stats ??
    summary?.by_signal_kind_horizon_usable_stats ??
    decisionStats?.by_signal_kind_horizon_stats ??
    summary?.by_signal_kind_horizon_stats ??
    {}
  );
}

function buildStrategyBacktestRows(payload: LivermoreCandidateHistoryPayload | null) {
  const summary = payload?.summary ?? null;
  const decisionStats = summary?.decision_usable_stats ?? null;
  const bySignalKind = summary?.by_signal_kind ?? decisionStats?.by_signal_kind ?? {};
  const bySignalStats = resolveStrategyBacktestSignalStats(payload);
  const discoveredKinds = Object.keys(bySignalStats).filter(
    (key) => !(strategyBacktestOrder as readonly string[]).includes(key),
  );
  return [...strategyBacktestOrder, ...discoveredKinds].map((kind) => {
    const statsByHorizon = bySignalStats[kind] ?? {};
    return {
      kind,
      label: strategyBacktestLabels[kind] ?? kind,
      count: bySignalKind[kind] ?? 0,
      stats: {
        return_1d: backtestStatsText(statsByHorizon.return_1d),
        return_5d: backtestStatsText(statsByHorizon.return_5d),
        return_20d: backtestStatsText(statsByHorizon.return_20d),
      },
    };
  });
}

function resolveStrategyBacktestSampleCount(payload: LivermoreCandidateHistoryPayload | null): number {
  const summary = payload?.summary ?? null;
  const decisionStats = summary?.decision_usable_stats ?? null;
  const horizonStats =
    decisionStats?.horizon_usable_stats ?? summary?.horizon_usable_stats ?? summary?.horizon_stats;

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

function buildStrategyBacktestMarketStateRows(payload: LivermoreCandidateHistoryPayload | null) {
  const summary = payload?.summary ?? null;
  const decisionStats = summary?.decision_usable_stats ?? null;
  const byMarketState =
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
          label: strategyBacktestLabels[kind] ?? kind,
          stats: {
            return_1d: backtestStatsText(statsByHorizon.return_1d),
            return_5d: backtestStatsText(statsByHorizon.return_5d),
            return_20d: backtestStatsText(statsByHorizon.return_20d),
          },
        };
      });
  });
}

type StrategyPriorityRow = LivermoreStrategyScorePayload["rows"][number];

function formatPriorityScore(value: number | null | undefined): string {
  return value == null || Number.isNaN(value) ? "-" : value.toFixed(1);
}

function buildStrategyPriorityHeadline(rows: StrategyPriorityRow[]): string {
  const sufficientRows = rows.filter((row) => row.sample_status === "sufficient");
  if (rows.length === 0 || sufficientRows.length === 0) {
    return "当前状态样本不足";
  }
  const priorityRows = sufficientRows.filter(
    (row) => row.priority_label === "优先复核" && (row.diagnostics?.risk_flags ?? []).length === 0,
  );
  if (priorityRows.length > 0) {
    return `优先复核：${priorityRows.map((row) => row.strategy_label).join("、")}`;
  }
  return "当前状态降权观察";
}

function strategyPrioritySummaryReason(rows: StrategyPriorityRow[]): string {
  const firstPriority = rows.find((row) => row.priority_label === "优先复核");
  if (firstPriority) return firstPriority.reason;
  const firstInsufficient = rows.find((row) => row.sample_status === "insufficient");
  if (firstInsufficient) return firstInsufficient.reason;
  return rows[0]?.reason ?? "暂无当前状态策略评分。";
}

function strategyPriorityDiagnosticLabels(row: StrategyPriorityRow): string[] {
  const diagnostics = row.diagnostics;
  if (!diagnostics) return [];
  const labels: string[] = [];
  if (diagnostics.priority_scope_label) {
    const scopeStats = diagnostics.priority_scope_stats?.return_5d;
    const scopeStatsText = scopeStats ? backtestStatsText(scopeStats) : null;
    labels.push(scopeStatsText ? `${diagnostics.priority_scope_label} ${scopeStatsText}` : diagnostics.priority_scope_label);
  }
  for (const bucket of diagnostics.rank_buckets ?? []) {
    if (!bucket.included_in_priority && bucket.priority_label === "降权观察") {
      labels.push(`${bucket.label} ${bucket.priority_label}`);
    }
  }
  for (const flag of diagnostics.risk_flags ?? []) {
    if (flag.label) {
      labels.push(flag.label);
    }
  }
  return Array.from(new Set(labels)).slice(0, 4);
}

export default function StockAnalysisPage() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const [asOfOverride, setAsOfOverride] = useState<string | null>(null);
  const [sectorFilterSectorCode, setSectorFilterSectorCode] = useState<string | null>(null);
  const [sectorView, setSectorView] = useState<StockSectorViewKind>("score");
  const [sectorSort, setSectorSort] = useState<{
    key: SectorSortKey;
    order: "ascend" | "descend";
  }>({ key: "rank", order: "ascend" });
  const [boundaryDrawerOpen, setBoundaryDrawerOpen] = useState(false);
  const [detailSelection, setDetailSelection] = useState<{
    code: string;
    name?: string;
    reviewRank?: number;
    sectorCode?: string;
    sectorName?: string;
    distanceToBreakoutPct?: string;
    source?: "review_queue" | "risk_exit" | "mean_reversion" | "factor_screen" | "consensus";
    livermoreRank?: number | null;
    meanReversionRank?: number | null;
    factorScreenRank?: number | null;
  } | null>(null);
  const [agentDrawerOpen, setAgentDrawerOpen] = useState(false);
  const [sectorSeriesCollapseKeys, setSectorSeriesCollapseKeys] = useState<string[]>([]);
  const [sectorSeriesWindow, setSectorSeriesWindow] = useState<5 | 20>(5);

  const strategyQueryKey = ["stock-analysis", "livermore-strategy", asOfOverride ?? "__default"] as const;

  const strategyQuery = useQuery({
    queryKey: strategyQueryKey,
    queryFn: () =>
      asOfOverride
        ? client.getLivermoreStrategy({ asOfDate: asOfOverride })
        : client.getLivermoreStrategy(),
  });

  const strategyPayload = strategyQuery.data?.result ?? null;

  const confluenceQuery = useQuery({
    queryKey: ["stock-analysis", "livermore-signal-confluence", strategyPayload?.as_of_date ?? "__none"],
    queryFn: () =>
      client.getLivermoreSignalConfluence({
        asOfDate: strategyPayload?.as_of_date ?? undefined,
      }),
    enabled: Boolean(strategyPayload?.as_of_date),
  });

  const confluencePayload: LivermoreSignalConfluencePayload | null =
    confluenceQuery.data?.result ?? null;

  const decisionSummary = useMemo(
    () =>
      strategyPayload
        ? buildDecisionSummary(strategyPayload, {
            quality_flag: strategyQuery.data?.result_meta?.quality_flag,
            vendor_status: strategyQuery.data?.result_meta?.vendor_status,
            fallback_mode: strategyQuery.data?.result_meta?.fallback_mode,
          })
        : null,
    [
      strategyPayload,
      strategyQuery.data?.result_meta?.quality_flag,
      strategyQuery.data?.result_meta?.vendor_status,
      strategyQuery.data?.result_meta?.fallback_mode,
    ],
  );

  const marketState = useMemo(
    () => (strategyPayload ? buildMarketStateCard(strategyPayload) : null),
    [strategyPayload],
  );

  const sectorRowsFull = useMemo(
    () => (strategyPayload ? buildSectorRows(strategyPayload) : []),
    [strategyPayload],
  );

  const sectorViewRows = useMemo(
    () => (strategyPayload ? buildSectorViewModel(strategyPayload, sectorView) : []),
    [strategyPayload, sectorView],
  );

  const sortedDetailRows = useMemo(() => {
    const cmp = buildSectorTableSortComparator(sectorSort.key, sectorSort.order);
    return [...sectorRowsFull].sort(cmp);
  }, [sectorRowsFull, sectorSort]);

  const reviewQueue = useMemo(() => {
    const queue = strategyPayload ? buildCandidateReviewQueue(strategyPayload) : [];
    return [...queue].sort((a, b) => (patternRank[a.pattern] ?? 99) - (patternRank[b.pattern] ?? 99));
  }, [strategyPayload]);

  const gateState = strategyPayload?.market_gate.state;
  const meanReversionPayload = strategyPayload?.mean_reversion_candidates;
  const factorScreenPayload = strategyPayload?.factor_screen_candidates;

  const consensusSummary = useMemo(
    () => buildConsensusSummary(strategyPayload),
    [strategyPayload],
  );

  const themeBreakoutCards = useMemo(
    () => (strategyPayload ? buildThemeBreakoutCards(strategyPayload) : []),
    [strategyPayload],
  );

  const themeEvidenceRows = useMemo(
    () => (strategyPayload ? buildThemeEvidenceStateRows(strategyPayload) : []),
    [strategyPayload],
  );

  const themeBreakoutReviewItems = useMemo(
    () => (strategyPayload ? buildThemeBreakoutReviewItems(strategyPayload) : []),
    [strategyPayload],
  );

  const sectorOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const card of reviewQueue) {
      map.set(card.sectorCode, card.sectorName || card.sectorCode);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b, "zh-Hans-CN"));
  }, [reviewQueue]);

  const sectorFilterSummary = useMemo(
    () => (strategyPayload ? buildSectorFilterSummary(strategyPayload, sectorFilterSectorCode) : null),
    [strategyPayload, sectorFilterSectorCode],
  );

  const selectedSectorLabel = sectorFilterSectorCode ? (sectorFilterSummary?.sectorLabel ?? sectorFilterSectorCode) : null;

  const filteredCandidates = useMemo(() => {
    if (!sectorFilterSectorCode) return reviewQueue;
    return reviewQueue.filter((c) => c.sectorCode === sectorFilterSectorCode);
  }, [reviewQueue, sectorFilterSectorCode]);

  const riskRows = useMemo(
    () => (strategyPayload ? buildRiskExitRows(strategyPayload, confluencePayload) : []),
    [strategyPayload, confluencePayload],
  );

  const riskExitUnsupported = strategyPayload?.unsupported_outputs.find((output) => output.key === "risk_exit");
  const themeBreakoutUnsupported = strategyPayload?.unsupported_outputs.find((output) => output.key === "theme_breakout");

  const boundarySummary = useMemo(
    () =>
      strategyPayload
        ? buildDataBoundarySummary(strategyPayload, {
            quality_flag: strategyQuery.data?.result_meta?.quality_flag,
            vendor_status: strategyQuery.data?.result_meta?.vendor_status,
            fallback_mode: strategyQuery.data?.result_meta?.fallback_mode,
          })
        : null,
    [
      strategyPayload,
      strategyQuery.data?.result_meta?.quality_flag,
      strategyQuery.data?.result_meta?.vendor_status,
      strategyQuery.data?.result_meta?.fallback_mode,
    ],
  );

  const firstScreenKpis = useMemo(
    () =>
      strategyPayload
        ? buildStockAnalysisKpiStrip(strategyPayload, confluencePayload, {
            quality_flag: strategyQuery.data?.result_meta?.quality_flag,
            vendor_status: strategyQuery.data?.result_meta?.vendor_status,
            fallback_mode: strategyQuery.data?.result_meta?.fallback_mode,
          })
        : [],
    [
      strategyPayload,
      confluencePayload,
      strategyQuery.data?.result_meta?.quality_flag,
      strategyQuery.data?.result_meta?.vendor_status,
      strategyQuery.data?.result_meta?.fallback_mode,
    ],
  );

  const evidenceStatusRows = useMemo(
    () =>
      strategyPayload
        ? buildStockAnalysisEvidenceStatus(strategyPayload, {
            quality_flag: strategyQuery.data?.result_meta?.quality_flag,
            vendor_status: strategyQuery.data?.result_meta?.vendor_status,
            fallback_mode: strategyQuery.data?.result_meta?.fallback_mode,
            source_version: strategyQuery.data?.result_meta?.source_version,
            rule_version: strategyQuery.data?.result_meta?.rule_version,
            trace_id: strategyQuery.data?.result_meta?.trace_id,
          })
        : [],
    [
      strategyPayload,
      strategyQuery.data?.result_meta?.quality_flag,
      strategyQuery.data?.result_meta?.vendor_status,
      strategyQuery.data?.result_meta?.fallback_mode,
      strategyQuery.data?.result_meta?.source_version,
      strategyQuery.data?.result_meta?.rule_version,
      strategyQuery.data?.result_meta?.trace_id,
    ],
  );

  const eventMonitorRows = useMemo(
    () => (strategyPayload ? buildStockAnalysisEventMonitorRows(strategyPayload, confluencePayload) : []),
    [strategyPayload, confluencePayload],
  );

  const closedLoopSummary = useMemo(
    () =>
      strategyPayload && !confluenceQuery.isLoading
        ? buildClosedLoopSummary(strategyPayload, confluencePayload, {
            quality_flag:
              confluencePayload?.closed_loop_state != null
                ? (confluenceQuery.data?.result_meta?.quality_flag ?? strategyQuery.data?.result_meta?.quality_flag)
                : strategyQuery.data?.result_meta?.quality_flag,
            vendor_status:
              confluencePayload?.closed_loop_state != null
                ? (confluenceQuery.data?.result_meta?.vendor_status ?? strategyQuery.data?.result_meta?.vendor_status)
                : strategyQuery.data?.result_meta?.vendor_status,
            fallback_mode:
              confluencePayload?.closed_loop_state != null
                ? (confluenceQuery.data?.result_meta?.fallback_mode ?? strategyQuery.data?.result_meta?.fallback_mode)
                : strategyQuery.data?.result_meta?.fallback_mode,
            source_version:
              confluencePayload?.closed_loop_state != null
                ? (confluenceQuery.data?.result_meta?.source_version ?? strategyQuery.data?.result_meta?.source_version)
                : strategyQuery.data?.result_meta?.source_version,
            rule_version:
              confluencePayload?.closed_loop_state != null
                ? (confluenceQuery.data?.result_meta?.rule_version ?? strategyQuery.data?.result_meta?.rule_version)
                : strategyQuery.data?.result_meta?.rule_version,
          })
        : null,
    [
      strategyPayload,
      confluencePayload,
      confluenceQuery.isLoading,
      confluenceQuery.data?.result_meta?.quality_flag,
      confluenceQuery.data?.result_meta?.vendor_status,
      confluenceQuery.data?.result_meta?.fallback_mode,
      confluenceQuery.data?.result_meta?.source_version,
      confluenceQuery.data?.result_meta?.rule_version,
      strategyQuery.data?.result_meta?.quality_flag,
      strategyQuery.data?.result_meta?.vendor_status,
      strategyQuery.data?.result_meta?.fallback_mode,
      strategyQuery.data?.result_meta?.source_version,
      strategyQuery.data?.result_meta?.rule_version,
    ],
  );

  const metaSegments = strategyPayload
    ? buildInlineMetaSegments(strategyPayload, {
        quality_flag: strategyQuery.data?.result_meta?.quality_flag,
        vendor_status: strategyQuery.data?.result_meta?.vendor_status,
        source_version: strategyQuery.data?.result_meta?.source_version,
        rule_version: strategyQuery.data?.result_meta?.rule_version,
        fallback_mode: strategyQuery.data?.result_meta?.fallback_mode,
      })
    : [];

  const showStaleBanner = Boolean(
    strategyQuery.data?.result_meta &&
      (strategyQuery.data.result_meta.quality_flag !== "ok" ||
        strategyQuery.data.result_meta.vendor_status !== "ok" ||
        strategyQuery.data.result_meta.fallback_mode !== "none"),
  );

  const topBars = sectorViewRows.slice(0, 5);
  const bottomBars = sectorViewRows.slice(Math.max(sectorViewRows.length - 5, 0));
  const firstScreenNextAction =
    closedLoopSummary && closedLoopSummary.verdict.code !== "reviewable"
      ? `闭环结论优先：${closedLoopSummary.verdict.nextStep}`
      : decisionSummary?.nextReviewAction;
  const firstScreenHeadline =
    closedLoopSummary && closedLoopSummary.verdict.code !== "reviewable"
      ? closedLoopSummary.verdict.headline
      : decisionSummary?.headline;

  const invalidateStockAnalysis = () => {
    queryClient.invalidateQueries({ queryKey: ["stock-analysis"] }).catch(() => undefined);
  };

  const toggleSectorFilter = (code: string | null) => {
    setSectorFilterSectorCode((prev) => (prev === code ? null : code));
  };

  const toggleSort = (key: SectorSortKey) => {
    setSectorSort((prev) =>
      prev.key === key ? { key, order: prev.order === "ascend" ? "descend" : "ascend" } : { key, order: "ascend" },
    );
  };

  function renderSortSuffix(key: SectorSortKey) {
    if (sectorSort.key !== key) return "";
    return sectorSort.order === "ascend" ? " ▲" : " ▼";
  }

  const headerDateValue =
    strategyPayload?.as_of_date != null ? dayjs(strategyPayload.as_of_date) : null;

  const pickerDisplay =
    asOfOverride != null && asOfOverride.trim() !== "" ? dayjs(asOfOverride) : headerDateValue;

  const stockDetailAsOfDate = asOfOverride ?? strategyPayload?.as_of_date ?? undefined;

  const effectiveAsOf = asOfOverride ?? strategyPayload?.as_of_date ?? null;
  const currentMarketState = strategyPayload?.market_gate.state ?? null;
  const strategyScoreQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-strategy-score",
      effectiveAsOf ?? "__none",
      currentMarketState ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreStrategyScore({
        snapshotTo: effectiveAsOf ?? undefined,
        currentMarketState: currentMarketState ?? undefined,
        minSample: 20,
        primaryHorizon: "return_5d",
      }),
    enabled: Boolean(effectiveAsOf),
  });
  const strategyScorePayload = strategyScoreQuery.data?.result ?? null;
  const strategyPriorityRows = strategyScorePayload?.current_market_state_rows ?? [];
  const strategyPriorityHeadline = buildStrategyPriorityHeadline(strategyPriorityRows);
  const strategyPriorityReason = strategyPrioritySummaryReason(strategyPriorityRows);
  const strategyBacktestSnapshotFrom = effectiveAsOf ? dayjs(effectiveAsOf).subtract(10, "day").format("YYYY-MM-DD") : null;

  const strategyBacktestQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-candidate-history-strategy-backtest",
      strategyBacktestSnapshotFrom ?? "__none",
      effectiveAsOf ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreCandidateHistory({
        snapshotFrom: strategyBacktestSnapshotFrom ?? undefined,
        snapshotTo: effectiveAsOf ?? undefined,
        limit: 500,
      }),
    enabled: Boolean(effectiveAsOf),
  });

  const strategyBacktestPayload = strategyBacktestQuery.data?.result ?? null;
  const strategyBacktestRows = useMemo(() => buildStrategyBacktestRows(strategyBacktestPayload), [strategyBacktestPayload]);
  const strategyBacktestMarketStateRows = useMemo(
    () => buildStrategyBacktestMarketStateRows(strategyBacktestPayload),
    [strategyBacktestPayload],
  );
  const strategyBacktestSampleCount = useMemo(
    () => resolveStrategyBacktestSampleCount(strategyBacktestPayload),
    [strategyBacktestPayload],
  );
  const strategyBacktestWindow = strategyBacktestPayload?.backtest_window_summary ?? null;

  const sectorSeriesExpanded = sectorSeriesCollapseKeys.includes("sector-rank-series-multi");

  const sectorRankSeriesQuery = useQuery({
    queryKey: ["stock-analysis", "livermore-sector-rank-series", effectiveAsOf ?? "__none", sectorSeriesWindow] as const,
    queryFn: () =>
      client.getLivermoreSectorRankSeries({
        asOfDate: effectiveAsOf ?? undefined,
        windowDays: sectorSeriesWindow,
        topK: 10,
      }),
    enabled: Boolean(
      sectorSeriesExpanded &&
        effectiveAsOf &&
        strategyPayload &&
        !sectorRankUnavailable(strategyPayload),
    ),
  });

  const sectorSeriesTableRows = useMemo(() => {
    const envelope = sectorRankSeriesQuery.data?.result;
    const series = envelope?.series;
    if (!series || envelope?.state !== "ok") {
      return [];
    }
    return latestSectorSeriesTableRows(series);
  }, [sectorRankSeriesQuery.data?.result]);

  const stockAnalysisAgentPageContext = useMemo(
    () =>
      buildStockAnalysisAgentPageContext({
        asOfDate: effectiveAsOf,
        sectorFilterSectorCode,
        sectorFilterLabel: selectedSectorLabel,
        sectorView,
        detailSelection,
      }),
    [detailSelection, effectiveAsOf, sectorFilterSectorCode, sectorView, selectedSectorLabel],
  );

  return (
    <PageV2Shell testId="stock-analysis-page" style={stockAnalysisPageCssVars}>
      <main className="stock-analysis-page">
        <header className="stock-analysis-page__header">
          <p className="stock-analysis-page__eyebrow">A股观察 / Evidence first</p>
          <div className="stock-analysis-page__header-main">
            <div>
              <h1>股票分析</h1>
              <p>
                复用 Livermore 与 Choice 股票只读链路，展示市场状态、板块强弱与候选证据；
                仅供研究复核，不构成执行性结论。
              </p>
            </div>
            <div className="stock-analysis-page__header-controls">
              <span className="stock-analysis-page__badge">仅观察 / 复核 / 研究</span>
              <Button
                type="default"
                className="stock-analysis-page__agent-entry"
                data-testid="stock-analysis-agent-open"
                onClick={() => setAgentDrawerOpen(true)}
                aria-expanded={agentDrawerOpen}
              >
                召唤 Agent 复核
              </Button>
              <DatePicker
                allowClear
                aria-label="as-of-date-picker"
                data-testid="stock-analysis-as-of-picker"
                value={pickerDisplay}
                onChange={(_, iso) => {
                  setAsOfOverride(Array.isArray(iso) ? (iso[0] ?? null) : iso || null);
                }}
              />
              <Button data-testid="stock-analysis-refresh" onClick={invalidateStockAnalysis}>
                刷新
              </Button>
              {strategyQuery.data?.result_meta?.generated_at ? (
                <Text type="secondary" className="stock-analysis-page__tabular">
                  最后更新 {strategyQuery.data.result_meta.generated_at}
                </Text>
              ) : null}
            </div>
          </div>
        </header>

        {strategyQuery.isLoading ? (
          <section className="stock-analysis-page__panel">
            <p className="stock-analysis-page__state">正在加载股票分析结果。</p>
          </section>
        ) : null}

        {strategyQuery.isError ? (
          <section className="stock-analysis-page__panel stock-analysis-page__panel--error">
            <h2>股票分析结果加载失败。</h2>
            <p>{errorMessage(strategyQuery.error)}</p>
          </section>
        ) : null}

        {marketState ? (
          <>
            {decisionSummary ? (
              <div className="stock-analysis-page__command-deck">
                <PageDecisionHero
                  className="stock-analysis-page__decision-panel"
                  testId="stock-analysis-decision-panel"
                  eyebrow="今日判断"
                  title={firstScreenHeadline ?? "暂无有效判断，先保持观察"}
                  businessQuestion="当前市场处于什么状态，今天该优先复核哪些只读证据？"
                  reportDateSlot={
                    <span>
                      报告日 <strong className="stock-analysis-page__tabular">{decisionSummary.asOfLabel}</strong> /{" "}
                      {decisionSummary.basisLabel} / {decisionSummary.boundaryLabel}
                    </span>
                  }
                  conclusion={firstScreenNextAction ? <span>{firstScreenNextAction}</span> : null}
                >
                  <div className="stock-analysis-page__decision-meta" aria-label="今日判断摘要">
                    <span>{decisionSummary.gateLabel}</span>
                    <span>{decisionSummary.exposureLabel}</span>
                    <span>{decisionSummary.strongestSectorLabel}</span>
                    <span>{decisionSummary.weakestSectorLabel}</span>
                    <span>{decisionSummary.candidateCountLabel}</span>
                    <span>{decisionSummary.dataFreshnessLabel}</span>
                  </div>
                  <div className="stock-analysis-page__decision-grid">
                    <div>
                      <span>数据日期</span>
                      <strong className="stock-analysis-page__tabular">{decisionSummary.asOfLabel}</strong>
                    </div>
                    <div>
                      <span>口径</span>
                      <strong>{decisionSummary.basisLabel}</strong>
                    </div>
                    <div>
                      <span>边界</span>
                      <strong>{decisionSummary.boundaryLabel}</strong>
                    </div>
                    <div>
                      <span>门控确认</span>
                      <strong>{marketState.passedLabel}</strong>
                    </div>
                  </div>
                  {closedLoopSummary ? (
                    <section
                      className="stock-analysis-page__closed-loop-summary"
                      data-testid="stock-analysis-closed-loop-summary"
                      aria-label="闭环摘要"
                    >
                      <div
                        className="stock-analysis-page__closed-loop-verdict"
                        data-tone={closedLoopSummary.verdict.tone}
                        data-testid="stock-analysis-closed-loop-verdict"
                      >
                        <div>
                          <span>{closedLoopSummary.verdict.label}</span>
                          <strong>{closedLoopSummary.verdict.headline}</strong>
                          <p>{closedLoopSummary.verdict.primaryReason}</p>
                        </div>
                        <ul aria-label="闭环结论证据">
                          {closedLoopSummary.verdict.evidence.map((item) => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                        <small>{closedLoopSummary.verdict.nextStep}</small>
                      </div>
                      <div className="stock-analysis-page__closed-loop-compact-head">
                        <strong>闭环摘要</strong>
                        <span className="stock-analysis-page__pill" data-tone={closedLoopSummary.referenceRating.tone}>
                          {closedLoopSummary.referenceRating.label}
                        </span>
                        <small>{closedLoopSummary.referenceRating.detail}</small>
                      </div>
                      <div className="stock-analysis-page__closed-loop-items">
                        {closedLoopSummary.items.map((item) => (
                          <div
                            key={item.key}
                            data-tone={item.tone}
                            data-testid={item.key === "replay" ? "stock-analysis-replay-status" : undefined}
                          >
                            <span>{item.label}</span>
                            <strong>{item.statusLabel}</strong>
                            <small className="stock-analysis-page__visually-hidden">{item.detail}</small>
                            {item.badges?.map((badge) => (
                              <small className="stock-analysis-page__visually-hidden" key={badge}>
                                {badge}
                              </small>
                            ))}
                          </div>
                        ))}
                      </div>
                    </section>
                  ) : null}
                  <details className="stock-analysis-page__decision-detail">
                    <summary>门控与边界明细</summary>
                    <div className="stock-analysis-page__decision-detail-grid">
                      <section>
                        <h3>门控条件</h3>
                        <ul className="stock-analysis-page__list stock-analysis-page__list--compact">
                          {marketState.conditions.map((condition) => (
                            <li key={condition.key}>
                              <span>
                                <strong>{condition.label}</strong>
                                <small>{condition.evidence}</small>
                              </span>
                              <em>{statusLabel(condition.status)}</em>
                            </li>
                          ))}
                        </ul>
                      </section>
                      <section>
                        <h3>需要关注边界</h3>
                        {marketState.warnings.length > 0 ? (
                          <ul className="stock-analysis-page__notes">
                            {marketState.warnings.slice(0, 4).map((warning) => (
                              <li key={warning}>{warning}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="stock-analysis-page__empty">当前无诊断预警。</p>
                        )}
                      </section>
                    </div>
                  </details>
                </PageDecisionHero>
                {evidenceStatusRows.length > 0 ? (
                  <aside className="moss-page-v2-surface stock-analysis-page__command-side">
                    <DataStatusStrip
                      testId="stock-analysis-evidence-status-panel"
                      className="stock-analysis-page__evidence-status-panel"
                    >
                      <div className="stock-analysis-page__evidence-status-head">
                        <h3>证据与状态</h3>
                        <span>只读证据</span>
                      </div>
                      <div className="stock-analysis-page__evidence-status-list">
                        {evidenceStatusRows.map((item) => (
                          <div className="stock-analysis-page__evidence-status-row" data-tone={item.tone} key={item.key}>
                            <span>{item.label}</span>
                            <strong>{item.statusLabel}</strong>
                            <small>{item.detail}</small>
                          </div>
                        ))}
                      </div>
                    </DataStatusStrip>
                  </aside>
                ) : null}
              </div>
            ) : null}

            {firstScreenKpis.length > 0 ? (
              <section aria-label="首屏 KPI">
                <KpiBand className="stock-analysis-page__kpi-strip" testId="stock-analysis-kpi-strip">
                  {firstScreenKpis.map((item) => (
                    <div
                      className="moss-page-v2-kpi-metric stock-analysis-page__kpi-tile"
                      data-tone={item.tone}
                      key={item.key}
                    >
                      <span>{item.label}</span>
                      <strong>{item.value}</strong>
                      <small>{item.detail}</small>
                    </div>
                  ))}
                </KpiBand>
              </section>
            ) : null}

            {showStaleBanner ? (
              <div className="stock-analysis-page__stale-banner" data-testid="stock-analysis-stale-banner" role="status">
                数据陈旧、通道异常或使用回退快照（quality_flag / vendor_status / fallback_mode）。下方结论仅供复核参考。
              </div>
            ) : null}

            <AnalysisGrid columns={2} className="stock-analysis-page__workspace">
              <div className="stock-analysis-page__primary">
              <section
                className="stock-analysis-page__panel stock-analysis-page__panel--compact"
                data-testid="stock-analysis-sector-strength-panel"
              >
                <div className="stock-analysis-page__section-head">
                  <div>
                    <h2>板块强弱</h2>
                    <p>Livermore sector_rank，仅用后端字段做排序视图；图示为横向对比入口。</p>
                  </div>
                  <span className="stock-analysis-page__pill">
                    {(strategyPayload?.sector_rank?.formula_version ?? "").trim() || "formula 待补"}
                  </span>
                </div>

                {!sectorRankUnavailable(strategyPayload) ? (
                  <>
                    <Tabs
                      className="stock-analysis-page__sector-tabs"
                      size="small"
                      activeKey={sectorView}
                      onChange={(key) => setSectorView(key as StockSectorViewKind)}
                      items={sectorViewTabs.map((tab) => ({ key: tab.key, label: tab.label }))}
                    />

                    <div className="stock-analysis-page__sector-bisect" data-testid="stock-analysis-sector-bars">
                      <div>
                        <h3 className="stock-analysis-page__sector-col-title">强势 Top 5</h3>
                        <div className="stock-analysis-page__bar-list">
                          {topBars.map((row) => (
                            <button
                              type="button"
                              key={`top-${row.sectorCode}-${row.rank}`}
                              className={`stock-analysis-page__bar-row${sectorFilterSectorCode === row.sectorCode ? " stock-analysis-page__bar-row--active" : ""}`}
                              aria-pressed={sectorFilterSectorCode === row.sectorCode}
                              data-testid={`sector-bar-${row.sectorCode}`}
                              onClick={() => toggleSectorFilter(row.sectorCode)}
                            >
                              <div className="stock-analysis-page__bar-meta stock-analysis-page__table-number">
                                <span>
                                  {row.rank}. {row.sectorName}{" "}
                                  <small className="stock-analysis-page__tabular">{row.sectorCode}</small>
                                </span>
                                <span>{row.score}</span>
                              </div>
                              <div className="stock-analysis-page__bar-track">
                                <div
                                  className="stock-analysis-page__bar-fill"
                                  style={{
                                    width: `${(sectorView === "score" ? row.scoreNormalized : row.metricBarNormalized) * 100}%`,
                                  }}
                                />
                                <div className="stock-analysis-page__bar-label-overlay stock-analysis-page__table-number">
                                  <span>{row.pctChange}</span>
                                  <small>成分 {row.constituentCount}</small>
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="stock-analysis-page__sector-col--bottom">
                        <h3 className="stock-analysis-page__sector-col-title">弱势 Bottom 5</h3>
                        <div className="stock-analysis-page__bar-list">
                          {bottomBars.map((row) => (
                            <button
                              type="button"
                              key={`bottom-${row.sectorCode}-${row.rank}`}
                              className={`stock-analysis-page__bar-row${sectorFilterSectorCode === row.sectorCode ? " stock-analysis-page__bar-row--active" : ""}`}
                              aria-pressed={sectorFilterSectorCode === row.sectorCode}
                              data-testid={`sector-bar-bottom-${row.sectorCode}`}
                              onClick={() => toggleSectorFilter(row.sectorCode)}
                            >
                              <div className="stock-analysis-page__bar-meta stock-analysis-page__table-number">
                                <span>
                                  {row.rank}. {row.sectorName}{" "}
                                  <small className="stock-analysis-page__tabular">{row.sectorCode}</small>
                                </span>
                                <span>{row.pctChange}</span>
                              </div>
                              <div className="stock-analysis-page__bar-track">
                                <div
                                  className="stock-analysis-page__bar-fill"
                                  style={{
                                    width: `${(sectorView === "score" ? row.scoreNormalized : row.metricBarNormalized) * 100}%`,
                                  }}
                                />
                                <div className="stock-analysis-page__bar-label-overlay stock-analysis-page__table-number">
                                  <span>{row.pctChange}</span>
                                  <small>成分 {row.constituentCount}</small>
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                    <p className="stock-analysis-page__footnote">
                      视图切换不重拉接口；条形图为单日截面，多日窗口可看下方聚合表（运行时聚合，sum 累加未复利）。
                    </p>

                    <Collapse
                      bordered={false}
                      style={{ marginTop: 12 }}
                      items={[
                        {
                          key: "sector-detail-table",
                          label: "展开看明细表格",
                          children: (
                            <div className="stock-analysis-page__table-wrap">
                              <table className="stock-analysis-page__table">
                                <thead>
                                  <tr>
                                    <th
                                      className="stock-analysis-page__sortable-head"
                                      scope="col"
                                      onClick={() => toggleSort("rank")}
                                      onKeyDown={(e) => e.key === "Enter" && toggleSort("rank")}
                                      role="columnheader"
                                    >
                                      排名
                                      {renderSortSuffix("rank")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head"
                                      scope="col"
                                      onClick={() => toggleSort("sectorName")}
                                    >
                                      行业
                                      {renderSortSuffix("sectorName")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head stock-analysis-page__table-number"
                                      scope="col"
                                      onClick={() => toggleSort("score")}
                                    >
                                      分数
                                      {renderSortSuffix("score")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head stock-analysis-page__table-number"
                                      scope="col"
                                      onClick={() => toggleSort("pctChange")}
                                    >
                                      涨跌幅
                                      {renderSortSuffix("pctChange")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head stock-analysis-page__table-number"
                                      scope="col"
                                      onClick={() => toggleSort("turnover")}
                                    >
                                      换手
                                      {renderSortSuffix("turnover")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head stock-analysis-page__table-number"
                                      scope="col"
                                      onClick={() => toggleSort("amplitude")}
                                    >
                                      振幅
                                      {renderSortSuffix("amplitude")}
                                    </th>
                                    <th
                                      className="stock-analysis-page__sortable-head stock-analysis-page__table-number"
                                      scope="col"
                                      onClick={() => toggleSort("constituentCount")}
                                    >
                                      成分数
                                      {renderSortSuffix("constituentCount")}
                                    </th>
                                    <th className="stock-analysis-page__table-number" scope="col">
                                      涨跌条
                                    </th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {sortedDetailRows.map((row: StockSectorRow) => (
                                    <tr key={row.sectorCode}>
                                      <td className="stock-analysis-page__table-number">#{row.rank}</td>
                                      <td>
                                        {row.sectorName}
                                        <small>{row.sectorCode}</small>
                                      </td>
                                      <td className="stock-analysis-page__table-number">{row.score}</td>
                                      <td className="stock-analysis-page__table-number">{row.pctChange}</td>
                                      <td className="stock-analysis-page__table-number">{row.turnover}</td>
                                      <td className="stock-analysis-page__table-number">{row.amplitude}</td>
                                      <td className="stock-analysis-page__table-number">{row.constituentCount}</td>
                                      <td className="stock-analysis-page__pct-bar-cell">
                                        <div className="stock-analysis-page__pct-bar-visual">
                                          <div
                                            className="stock-analysis-page__pct-bar-fill"
                                            style={{ width: `${row.pctChangeBar}%` }}
                                          />
                                        </div>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ),
                        },
                      ]}
                    />

                    <Collapse
                      bordered={false}
                      style={{ marginTop: 12 }}
                      activeKey={sectorSeriesCollapseKeys}
                      onChange={(keys) =>
                        setSectorSeriesCollapseKeys(Array.isArray(keys) ? keys : [keys])
                      }
                      items={[
                        {
                          key: "sector-rank-series-multi",
                          label: "多日累计强度（窗口聚合）",
                          children: (
                            <div
                              className="stock-analysis-page__sector-series-wrap"
                              data-testid="stock-analysis-sector-series-panel"
                            >
                              <p className="stock-analysis-page__sector-series-note">
                                窗口内对每日 avg_pctchange 做 sum 累加（未做复利）；动量持续度与资金流向暂不可用（见接口
                                unsupported_notes）。
                              </p>
                              <Tabs
                                size="small"
                                activeKey={String(sectorSeriesWindow)}
                                onChange={(key) => setSectorSeriesWindow(key === "20" ? 20 : 5)}
                                className="stock-analysis-page__sector-series-tabs"
                                items={[
                                  { key: "5", label: "5 交易日" },
                                  { key: "20", label: "20 交易日" },
                                ]}
                              />
                              {sectorRankSeriesQuery.isFetching ? (
                                <Text type="secondary">加载多日板块序列中。</Text>
                              ) : null}
                              {sectorRankSeriesQuery.isError ? (
                                <Alert
                                  type="warning"
                                  showIcon
                                  message="多日板块序列加载失败"
                                  description={errorMessage(sectorRankSeriesQuery.error)}
                                />
                              ) : null}
                              {!sectorRankSeriesQuery.isFetching &&
                              !sectorRankSeriesQuery.isError &&
                              sectorRankSeriesQuery.data?.result?.state === "missing" ? (
                                <Text type="secondary">暂无多日窗口可用数据。</Text>
                              ) : null}
                              {!sectorRankSeriesQuery.isFetching &&
                              !sectorRankSeriesQuery.isError &&
                              sectorRankSeriesQuery.data?.result?.state === "ok" &&
                              sectorSeriesTableRows.length === 0 ? (
                                <Text type="secondary">窗口内无表格行可展示。</Text>
                              ) : null}
                              {!sectorRankSeriesQuery.isFetching &&
                              !sectorRankSeriesQuery.isError &&
                              sectorRankSeriesQuery.data?.result?.state === "ok" &&
                              sectorSeriesTableRows.length > 0 ? (
                                <div className="stock-analysis-page__table-wrap">
                                  <table className="stock-analysis-page__table">
                                    <thead>
                                      <tr>
                                        <th scope="col">行业</th>
                                        <th scope="col">代码</th>
                                        <th className="stock-analysis-page__table-number" scope="col">
                                          score（最新）
                                        </th>
                                        <th className="stock-analysis-page__table-number" scope="col">
                                          rank（最新）
                                        </th>
                                        <th className="stock-analysis-page__table-number" scope="col">
                                          cum_pctchange_window
                                        </th>
                                        <th className="stock-analysis-page__table-number" scope="col">
                                          成分数
                                        </th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {sectorSeriesTableRows.map((row) => (
                                        <tr
                                          key={`${row.sector_code}-${row.trade_date}`}
                                          data-testid={`sector-series-row-${row.sector_code}`}
                                        >
                                          <td>{row.sector_name}</td>
                                          <td className="stock-analysis-page__tabular">{row.sector_code}</td>
                                          <td className="stock-analysis-page__table-number">
                                            {row.score ?? "-"}
                                          </td>
                                          <td className="stock-analysis-page__table-number">
                                            {row.rank ?? "-"}
                                          </td>
                                          <td className="stock-analysis-page__table-number">
                                            {row.cum_pctchange_window ?? "-"}
                                          </td>
                                          <td className="stock-analysis-page__table-number">
                                            {row.constituent_count ?? "-"}
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              ) : null}
                            </div>
                          ),
                        },
                      ]}
                    />
                  </>
                ) : (
                  <p className="stock-analysis-page__empty">
                    当前行业强弱不可用，请检查 Choice 股票目录与当日落地覆盖。
                  </p>
                )}
              </section>

              <section
                className="stock-analysis-page__panel stock-analysis-page__panel--evidence"
                data-testid="stock-analysis-theme-breakout"
              >
                <div className="stock-analysis-page__section-head">
                  <div>
                    <h2>题材突变雷达</h2>
                    <p>绕开“一线行业前三”硬门槛的观察层，只看现有日线、涨停和名称代理簇，不生成执行性结论。</p>
                  </div>
                  <span className="stock-analysis-page__pill">
                    {(strategyPayload?.theme_breakout?.formula_version ?? "").trim() || "proxy radar"}
                  </span>
                </div>

                {themeBreakoutCards.length > 0 ? (
                  <div className="stock-analysis-page__candidate-grid">
                    {themeBreakoutCards.map((card) => (
                      <article className="stock-analysis-page__candidate" key={card.themeKey}>
                        <div className="stock-analysis-page__candidate-head">
                          <div>
                            <h3>
                              #{card.rank} {card.themeName}
                            </h3>
                            <p>{card.parentSectorLabel}</p>
                            <div className="stock-analysis-page__pattern-tag">{card.summary}</div>
                          </div>
                          <span>观察</span>
                        </div>
                        <div className="stock-analysis-page__decision-meta">
                          <span>{card.strongCountLabel}</span>
                          <span>{card.limitCountLabel}</span>
                          <span>{card.advanceRatioLabel}</span>
                          <span>{card.avgPctChangeLabel}</span>
                          <span>{card.movementLabel}</span>
                        </div>
                        <p className="stock-analysis-page__review-focus">{card.reason}</p>
                        <p className="stock-analysis-page__review-focus">{card.latestEventLabel}</p>
                        <p className="stock-analysis-page__notice">{card.boundaryLabel}</p>
                        <ul className="stock-analysis-page__list stock-analysis-page__list--compact">
                          {card.leaders.map((leader) => (
                            <li key={leader.stockCode}>
                              <span>
                                <strong>{leader.stockName}</strong>
                                <small>
                                  {leader.stockCode} / {leader.pctChange} / 换手 {leader.turn} / 收盘强度{" "}
                                  {leader.closeStrength}
                                </small>
                              </span>
                              <em>{leader.tags.join(" / ") || "观察"}</em>
                            </li>
                          ))}
                        </ul>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="stock-analysis-page__empty">
                    {themeBreakoutUnsupported
                      ? themeBreakoutUnsupported.reason
                      : "当前无题材突变观察项。"}
                  </p>
                )}
              </section>

              {themeEvidenceRows.length > 0 ? (
                <section className="stock-analysis-page__panel stock-analysis-page__panel--evidence" data-testid="stock-analysis-theme-evidence-state">
                  <div className="stock-analysis-page__section-head">
                    <div>
                      <h2>Theme evidence state</h2>
                      <p>Shows whether real concept and intraday evidence is confirmed, landed, and date-matched.</p>
                    </div>
                    <span className="stock-analysis-page__pill">Evidence</span>
                  </div>
                  <ul className="stock-analysis-page__list stock-analysis-page__list--compact">
                    {themeEvidenceRows.map((row) => (
                      <li key={row.key}>
                        <span>
                          <strong>{row.label}</strong>
                          <small>
                            {row.status} / {row.rowCountLabel}
                          </small>
                        </span>
                        <em>{row.detail}</em>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {themeBreakoutReviewItems.length > 0 ? (
                <section className="stock-analysis-page__panel stock-analysis-page__panel--evidence" data-testid="stock-analysis-theme-review-items">
                  <div className="stock-analysis-page__section-head">
                    <div>
                      <h2>Theme miss review</h2>
                      <p>Review-only clusters that were strong enough to inspect but failed one or more selection gates.</p>
                    </div>
                    <span className="stock-analysis-page__pill">Review only</span>
                  </div>
                  <div className="stock-analysis-page__candidate-grid">
                    {themeBreakoutReviewItems.map((item) => (
                      <article className="stock-analysis-page__candidate" key={item.themeKey}>
                        <div className="stock-analysis-page__candidate-head">
                          <div>
                            <h3>
                              Review #{item.rank} {item.themeName}
                            </h3>
                            <p>{item.parentSectorLabel}</p>
                            <div className="stock-analysis-page__pattern-tag">{item.summary}</div>
                          </div>
                          <span>{item.sourceKindLabel}</span>
                        </div>
                        <div className="stock-analysis-page__decision-meta">
                          <span>{item.failedGateLabel}</span>
                        </div>
                        <p className="stock-analysis-page__review-focus">{item.reason}</p>
                        {item.leaders.length > 0 ? (
                          <ul className="stock-analysis-page__list stock-analysis-page__list--compact">
                            {item.leaders.map((leader) => (
                              <li key={leader.stockCode}>
                                <span>
                                  <strong>{leader.stockName}</strong>
                                  <small>
                                     {leader.stockCode} / {leader.pctChange} / 换手 {leader.turn} / 收盘强度{" "}
                                    {leader.closeStrength}
                                  </small>
                                </span>
                                <em>{leader.tags.join(" / ") || "Review"}</em>
                              </li>
                            ))}
                          </ul>
                        ) : null}
                      </article>
                    ))}
                  </div>
                </section>
              ) : null}

              <section
                className="stock-analysis-page__panel stock-analysis-page__panel--compact"
                data-testid="stock-analysis-consensus-review-panel"
                aria-label="多策略共振复核"
              >
                <Collapse
                  ghost
                  bordered={false}
                  defaultActiveKey={consensusSummary.items.length > 0 ? ["consensus"] : undefined}
                  items={[
                    {
                      key: "consensus",
                      label: `多策略共振复核 · ${consensusSummary.doubleCount} 只（3套 ${consensusSummary.tripleCount}）`,
                      children: (
                        <div className="stock-analysis-page__consensus" data-testid="stock-analysis-consensus">
                          <div className="stock-analysis-page__consensus-stats">
                            <span>
                              趋势 <strong>{consensusSummary.strategyCounts.livermore}</strong> 只
                            </span>
                            <span>
                              超跌反弹 <strong>{consensusSummary.strategyCounts.mean_reversion}</strong> 只
                            </span>
                            <span>
                              多因子 <strong>{consensusSummary.strategyCounts.factor_screen}</strong> 只
                            </span>
                            <span>
                              合计去重 <strong>{consensusSummary.totalUnion}</strong> 只
                            </span>
                          </div>

                          {!consensusSummary.hasAnyStrategy ? (
                            <p className="stock-analysis-page__empty">当前无任何策略输出候选股</p>
                          ) : consensusSummary.items.length === 0 ? (
                            <p className="stock-analysis-page__empty">
                              当前没有被 2 套及以上策略共同选中的股票
                            </p>
                          ) : (
                            <ul className="stock-analysis-page__list stock-analysis-page__list--compact">
                              {consensusSummary.items.map((row) => {
                                const isTriple = row.consensusCount >= 3;
                                const openDetail = () => {
                                  setDetailSelection({
                                    code: row.stockCode,
                                    name: row.stockName,
                                    sectorName: row.sectorName,
                                    source: "consensus",
                                    livermoreRank: row.livermoreRank,
                                    meanReversionRank: row.meanReversionRank,
                                    factorScreenRank: row.factorScreenRank,
                                  });
                                };
                                return (
                                  <li
                                    key={row.stockCode}
                                    className={`stock-analysis-page__consensus-row stock-analysis-page__row--clickable${
                                      isTriple ? " stock-analysis-page__consensus-row--triple" : ""
                                    }`}
                                    data-testid={`consensus-row-${row.stockCode}`}
                                    onClick={openDetail}
                                    role="button"
                                    tabIndex={0}
                                    onKeyDown={(e) => {
                                      if (e.key === "Enter" || e.key === " ") {
                                        e.preventDefault();
                                        openDetail();
                                      }
                                    }}
                                  >
                                    <div className="stock-analysis-page__consensus-head">
                                      <span
                                        className={`stock-analysis-page__consensus-badge${
                                          isTriple ? " stock-analysis-page__consensus-badge--triple" : ""
                                        }`}
                                      >
                                        {isTriple ? "三策略共振" : "双策略共振"}
                                      </span>
                                      <strong>
                                        <span className="stock-analysis-page__tabular">
                                          {row.stockCode}
                                        </span>{" "}
                                        {row.stockName}
                                      </strong>
                                      <small className="stock-analysis-page__tabular">
                                        {row.sectorName || "-"}
                                      </small>
                                      <span className="stock-analysis-page__consensus-strategies">
                                        {row.strategies.map((kind) => (
                                          <span key={kind} className="stock-analysis-page__consensus-badge">
                                            {consensusStrategyLabel(kind)}
                                          </span>
                                        ))}
                                      </span>
                                    </div>
                                    <div className="stock-analysis-page__consensus-ranks">
                                      {row.livermoreRank != null && (
                                        <span>趋势 #{row.livermoreRank}</span>
                                      )}
                                      {row.meanReversionRank != null && (
                                        <span>超跌反弹 #{row.meanReversionRank}</span>
                                      )}
                                      {row.factorScreenRank != null && (
                                        <span>多因子 #{row.factorScreenRank}</span>
                                      )}
                                    </div>
                                  </li>
                                );
                              })}
                            </ul>
                          )}
                          <p className="stock-analysis-page__footnote">
                            被多套策略同时选中的股票信号更强，但仍需结合板块环境与个股基本面独立复核，不构成执行建议。
                          </p>
                        </div>
                      ),
                    },
                  ]}
                />
              </section>

              <section
                className="stock-analysis-page__panel stock-analysis-page__panel--compact"
                data-testid="stock-analysis-market-priority-summary"
              >
                <div className="stock-analysis-page__section-head">
                  <div>
                    <h2>当前市场策略优先级</h2>
                    <p>按近 180 天候选快照拆分市场状态，以 T+5 为主排序；只读评分，仅用于复核先后。</p>
                  </div>
                  <span className="stock-analysis-page__pill">
                    {(strategyScorePayload?.current_market_state ?? currentMarketState ?? "状态待补")} /{" "}
                    {strategyScorePayload?.primary_horizon === "return_1d"
                      ? "T+1"
                      : strategyScorePayload?.primary_horizon === "return_20d"
                        ? "T+20"
                        : "T+5"}
                  </span>
                </div>
                {strategyScoreQuery.isLoading ? (
                  <p className="stock-analysis-page__empty">当前市场策略优先级加载中。</p>
                ) : null}
                {strategyScoreQuery.isError ? (
                  <p className="stock-analysis-page__notice">
                    当前市场策略优先级暂不可用：{errorMessage(strategyScoreQuery.error)}
                  </p>
                ) : null}
                {!strategyScoreQuery.isLoading && !strategyScoreQuery.isError ? (
                  <>
                    <div
                      className="stock-analysis-page__filter-status"
                      data-testid="stock-analysis-market-priority-current"
                    >
                      <span>{strategyScorePayload?.current_market_state ?? currentMarketState ?? "状态待补"}</span>
                      <strong>{strategyPriorityHeadline}</strong>
                      <small>
                        {strategyPriorityReason} 样本阈值 {strategyScorePayload?.min_sample ?? 20}，不输出交易动作。
                      </small>
                    </div>
                    {strategyPriorityRows.length > 0 ? (
                      <div className="stock-analysis-page__table-wrap">
                        <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                          <thead>
                            <tr>
                              <th scope="col">策略</th>
                              <th scope="col">状态</th>
                              <th className="stock-analysis-page__table-number" scope="col">
                                评分
                              </th>
                              {strategyBacktestHorizons.map((horizon) => (
                                <th scope="col" key={horizon}>
                                  {strategyBacktestHorizonLabels[horizon]}
                                </th>
                              ))}
                              <th scope="col">原因</th>
                            </tr>
                          </thead>
                          <tbody>
                            {strategyPriorityRows.map((row) => {
                              const diagnosticLabels = strategyPriorityDiagnosticLabels(row);
                              return (
                                <tr
                                  key={`${row.market_state}:${row.signal_kind}`}
                                  data-testid={`stock-analysis-market-priority-row-${row.market_state}-${row.signal_kind}`}
                                >
                                  <td>{row.strategy_label}</td>
                                  <td>{row.priority_label}</td>
                                  <td className="stock-analysis-page__table-number" data-testid="stock-analysis-market-priority-score">
                                    {formatPriorityScore(row.priority_score)}
                                  </td>
                                  {strategyBacktestHorizons.map((horizon) => (
                                    <td className="stock-analysis-page__table-number" key={horizon}>
                                      {backtestStatsText(row.stats[horizon])}
                                    </td>
                                  ))}
                                  <td>
                                    <span>{row.reason}</span>
                                    {diagnosticLabels.length > 0 ? (
                                      <div className="stock-analysis-page__strategy-diagnostic-tags">
                                        {diagnosticLabels.map((label) => (
                                          <span key={label}>{label}</span>
                                        ))}
                                      </div>
                                    ) : null}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="stock-analysis-page__empty">当前状态样本不足。</p>
                    )}
                  </>
                ) : null}
              </section>

              <section
                className="stock-analysis-page__panel stock-analysis-page__panel--compact"
                data-testid="stock-analysis-strategy-backtest"
              >
                <div className="stock-analysis-page__section-head">
                  <div>
                    <h2>策略回溯表现</h2>
                    <p>按近 10 个自然日入选快照拆分，仅使用已完成回溯日期计算胜率。</p>
                  </div>
                  <span className="stock-analysis-page__pill">
                    {strategyBacktestSnapshotFrom && effectiveAsOf
                      ? `${strategyBacktestSnapshotFrom} 至 ${effectiveAsOf}`
                      : "日期待补"}
                  </span>
                </div>
                {strategyBacktestQuery.isLoading ? (
                  <p className="stock-analysis-page__empty">策略回溯表现加载中。</p>
                ) : null}
                {strategyBacktestQuery.isError ? (
                  <p className="stock-analysis-page__notice">
                    策略回溯表现暂不可用：{errorMessage(strategyBacktestQuery.error)}
                  </p>
                ) : null}
                {!strategyBacktestQuery.isLoading && !strategyBacktestQuery.isError ? (
                  <>
                    <div className="stock-analysis-page__filter-status">
                      <span>有效样本</span>
                      <strong>{strategyBacktestSampleCount} 条</strong>
                      <small>
                        完成日期 {strategyBacktestWindow?.replay_dates_completed ?? 0} / 待成熟{" "}
                        {strategyBacktestWindow?.replay_dates_pending ?? 0} / 不支持{" "}
                        {strategyBacktestWindow?.replay_dates_unsupported ?? 0}
                      </small>
                    </div>
                    <div className="stock-analysis-page__table-wrap">
                      <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                        <thead>
                          <tr>
                            <th scope="col">策略</th>
                            <th scope="col">入选数</th>
                            {strategyBacktestHorizons.map((horizon) => (
                              <th scope="col" key={horizon}>
                                {strategyBacktestHorizonLabels[horizon]}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {strategyBacktestRows.map((row) => (
                            <tr key={row.kind} data-testid={`stock-analysis-strategy-backtest-${row.kind}`}>
                              <td>{row.label}</td>
                              <td className="stock-analysis-page__table-number">{row.count}</td>
                              {strategyBacktestHorizons.map((horizon) => (
                                <td className="stock-analysis-page__table-number" key={horizon}>
                                  {row.stats[horizon]}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {strategyBacktestMarketStateRows.length > 0 ? (
                      <div data-testid="stock-analysis-strategy-backtest-market-state">
                        <p className="stock-analysis-page__footnote">市场状态分段</p>
                        <div className="stock-analysis-page__table-wrap">
                          <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                            <thead>
                              <tr>
                                <th scope="col">市场状态</th>
                                <th scope="col">策略</th>
                                {strategyBacktestHorizons.map((horizon) => (
                                  <th scope="col" key={horizon}>
                                    {strategyBacktestHorizonLabels[horizon]}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {strategyBacktestMarketStateRows.map((row) => (
                                <tr
                                  key={`${row.marketState}:${row.kind}`}
                                  data-testid={`stock-analysis-strategy-backtest-market-state-${row.marketState}-${row.kind}`}
                                >
                                  <td>{row.marketState}</td>
                                  <td>{row.label}</td>
                                  {strategyBacktestHorizons.map((horizon) => (
                                    <td className="stock-analysis-page__table-number" key={horizon}>
                                      {row.stats[horizon]}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    ) : null}
                  </>
                ) : null}
              </section>

              <section
                className="stock-analysis-page__panel stock-analysis-page__panel--evidence"
                data-testid="stock-analysis-review-queue"
              >
                <div className="stock-analysis-page__section-head">
                  <div>
                    <h2>复核队列</h2>
                    <p>按当前只读证据排列候选，先看为什么进入观察，再看反证、待补和失效条件。</p>
                  </div>
                  <span className="stock-analysis-page__pill">候选 / 复核队列</span>
                </div>

                {reviewQueue.length > 0 ? (
                  <div className="stock-analysis-page__chip-row" data-testid="stock-sector-filter-chips">
                    <button
                      type="button"
                      className={`stock-analysis-page__pill stock-analysis-page__filter-chip${sectorFilterSectorCode === null ? " stock-analysis-page__filter-chip--active" : ""}`}
                      onClick={() => setSectorFilterSectorCode(null)}
                      aria-pressed={sectorFilterSectorCode === null}
                    >
                      全部行业
                    </button>
                    {sectorOptions.map(([code, label]) => (
                      <button
                        key={code}
                        type="button"
                        data-testid={`sector-filter-chip-${code}`}
                        className={`stock-analysis-page__pill stock-analysis-page__filter-chip${sectorFilterSectorCode === code ? " stock-analysis-page__filter-chip--active" : ""}`}
                        onClick={() => toggleSectorFilter(code)}
                        aria-pressed={sectorFilterSectorCode === code}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                ) : null}
                {reviewQueue.length > 0 ? (
                  <div className="stock-analysis-page__filter-status" data-testid="stock-review-filter-status">
                    <span>当前复核范围</span>
                    <strong>{selectedSectorLabel ?? "全部行业"}</strong>
                    <small>
                      显示 {filteredCandidates.length} / {reviewQueue.length} 个候选
                    </small>
                  </div>
                ) : null}

                {reviewQueue.length > 0 ? (
                  <div className="stock-analysis-page__candidate-grid">
                    {filteredCandidates.map((card) => (
                      <article
                        className="stock-analysis-page__candidate stock-analysis-page__review-card"
                        data-testid={`stock-candidate-${card.stockCode}`}
                        key={card.stockCode}
                      >
                        <div className="stock-analysis-page__candidate-head">
                          <div>
                            <h3>{card.headline}</h3>
                            <p>
                              {card.stockCode} / {card.stockName} / {card.sectorName}
                            </p>
                            <div className="stock-analysis-page__pattern-tag" title={card.patternNote}>
                              形态：{card.pattern} / 距观察位 {card.distanceToBreakoutPct}
                            </div>
                          </div>
                          <div className="stock-analysis-page__candidate-actions">
                            <strong>#{card.rank}</strong>
                            <Button
                              type="default"
                              size="small"
                              data-testid={`stock-candidate-review-chart-${card.stockCode}`}
                              onClick={() => {
                                const ranks = lookupStockStrategyRanks(strategyPayload ?? null, card.stockCode);
                                setDetailSelection({
                                  code: card.stockCode,
                                  name: card.stockName,
                                  reviewRank: card.rank,
                                  sectorCode: card.sectorCode,
                                  sectorName: card.sectorName,
                                  distanceToBreakoutPct: card.distanceToBreakoutPct,
                                  source: "review_queue",
                                  livermoreRank: card.rank,
                                  meanReversionRank: ranks.meanReversionRank,
                                  factorScreenRank: ranks.factorScreenRank,
                                });
                              }}
                            >
                              复核 K 线
                            </Button>
                            <span>观察</span>
                          </div>
                        </div>
                        <p className="stock-analysis-page__review-focus">{card.reviewFocus}</p>
                        <div className="stock-analysis-page__evidence-columns">
                          <div>
                            <h4>为什么先看</h4>
                            <ul>
                              {[...card.primaryEvidence, ...card.supportingEvidence].map((item) => (
                                <li key={item.key}>
                                  <strong>{item.label}</strong>：{item.value}
                                </li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <h4>反证与待补</h4>
                            <ul>
                              {card.boundaryEvidence.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <h4>失效条件</h4>
                            <p className="stock-analysis-page__review-focus">{card.invalidationFocus}</p>
                            <ul>
                              {card.invalidationRules.slice(1).map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        </div>
                        <Collapse
                          ghost
                          bordered={false}
                          items={[
                            {
                              key: "raw",
                              label: "展开原始字段",
                              children: (
                                <dl className="stock-analysis-page__raw-grid">
                                  {card.rawFields.map((field) => (
                                    <div key={field.key}>
                                      <dt>{field.label}</dt>
                                      <dd>{field.value}</dd>
                                    </div>
                                  ))}
                                </dl>
                              ),
                            },
                          ]}
                        />
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="stock-analysis-page__empty">当前无候选股复核队列。</p>
                )}
                {reviewQueue.length > 0 &&
                sectorFilterSectorCode &&
                filteredCandidates.length === 0 ? (
                  <p className="stock-analysis-page__empty">
                    该行业暂无候选复核项，可切换到其他行业复核。
                  </p>
                ) : null}
              </section>

              <section
                className="stock-analysis-page__panel stock-analysis-page__panel--compact"
                data-testid="stock-analysis-mean-reversion"
                aria-label="超跌反弹观察池"
              >
                <Collapse
                  ghost
                  bordered={false}
                  items={[
                    {
                      key: "mean-reversion",
                      label: `超跌反弹观察池 · ${meanReversionPayload?.candidate_count ?? 0} 只 · 仅在 OFF/WARM 市场激活`,
                      children: (
                        <div className="stock-analysis-page__mean-reversion">
                          {gateState === "HOT" || gateState === "OVERHEAT" ? (
                            <p className="stock-analysis-page__empty">当前市场偏热，超跌反弹策略未激活。</p>
                          ) : null}
                          {gateState !== "HOT" && gateState !== "OVERHEAT" && !meanReversionPayload ? (
                            <p className="stock-analysis-page__empty">数据未就绪。</p>
                          ) : null}
                          {gateState !== "HOT" &&
                          gateState !== "OVERHEAT" &&
                          meanReversionPayload &&
                          meanReversionPayload.items.length === 0 ? (
                            <p className="stock-analysis-page__empty">当前无符合条件的超跌反弹候选股。</p>
                          ) : null}
                          {gateState !== "HOT" &&
                          gateState !== "OVERHEAT" &&
                          meanReversionPayload &&
                          meanReversionPayload.items.length > 0 ? (
                            <ul className="stock-analysis-page__list stock-analysis-page__list--compact">
                              {meanReversionPayload.items.map((row) => (
                                <li
                                  key={row.stock_code}
                                  className="stock-analysis-page__mean-reversion-row stock-analysis-page__row--clickable"
                                  onClick={() => {
                                    const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stock_code);
                                    setDetailSelection({
                                      code: row.stock_code,
                                      name: row.stock_name,
                                      sectorCode: row.sector_code,
                                      sectorName: row.sector_name,
                                      source: "mean_reversion",
                                      livermoreRank: ranks.livermoreRank,
                                      meanReversionRank: row.rank,
                                      factorScreenRank: ranks.factorScreenRank,
                                    });
                                  }}
                                  role="button"
                                  tabIndex={0}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter" || e.key === " ") {
                                      e.preventDefault();
                                      const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stock_code);
                                      setDetailSelection({
                                        code: row.stock_code,
                                        name: row.stock_name,
                                        sectorCode: row.sector_code,
                                        sectorName: row.sector_name,
                                        source: "mean_reversion",
                                        livermoreRank: ranks.livermoreRank,
                                        meanReversionRank: row.rank,
                                        factorScreenRank: ranks.factorScreenRank,
                                      });
                                    }
                                  }}
                                >
                                  <div>
                                    <strong>#{row.rank}</strong>{" "}
                                    <span className="stock-analysis-page__tabular">{row.stock_code}</span>{" "}
                                    {row.stock_name}{" "}
                                    <small className="stock-analysis-page__tabular">
                                      {row.sector_name || row.sector_code || "-"}
                                    </small>
                                  </div>
                                  <div className="stock-analysis-page__mean-reversion-metrics stock-analysis-page__tabular">
                                    <span className="stock-analysis-page__mean-reversion-dd">
                                      20日回撤 {(row.drawdown_20d * 100).toFixed(1)}%
                                    </span>
                                    <span>收盘强度 {(row.close_strength * 100).toFixed(0)}%</span>
                                    <span>量比 {row.vol_ratio.toFixed(1)}x</span>
                                    <span>得分 {row.score.toFixed(2)}</span>
                                  </div>
                                </li>
                              ))}
                            </ul>
                          ) : null}
                          <p className="stock-analysis-page__footnote">
                            超跌反弹观察：基于价格回撤、企稳信号和放量特征的技术面筛选，仅作复核观察，不给出操作动作提示。市场状态
                            HOT/OVERHEAT 时自动停用。
                          </p>
                        </div>
                      ),
                    },
                    {
                      key: "factor-screen",
                      label: `多因子选股 · ${factorScreenPayload?.candidate_count ?? 0} 只 · ${factorScreenPayload?.coverage_note ?? "数据未就绪"}`,
                      children: (
                        <div className="stock-analysis-page__factor-screen">
                          {!factorScreenPayload ? (
                            <p className="stock-analysis-page__empty">因子数据未就绪。</p>
                          ) : factorScreenPayload.items.length === 0 ? (
                            <p className="stock-analysis-page__empty">当前无符合条件的多因子候选股。</p>
                          ) : (
                            <ul className="stock-analysis-page__list stock-analysis-page__list--compact">
                              {factorScreenPayload.items.map((row) => (
                                <li
                                  key={row.stock_code}
                                  className="stock-analysis-page__factor-screen-row stock-analysis-page__row--clickable"
                                  onClick={() => {
                                    const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stock_code);
                                    setDetailSelection({
                                      code: row.stock_code,
                                      name: row.stock_name,
                                      sectorCode: row.sector_code,
                                      sectorName: row.sector_name || row.industry,
                                      source: "factor_screen",
                                      livermoreRank: ranks.livermoreRank,
                                      meanReversionRank: ranks.meanReversionRank,
                                      factorScreenRank: row.rank,
                                    });
                                  }}
                                  role="button"
                                  tabIndex={0}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter" || e.key === " ") {
                                      e.preventDefault();
                                      const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stock_code);
                                      setDetailSelection({
                                        code: row.stock_code,
                                        name: row.stock_name,
                                        sectorCode: row.sector_code,
                                        sectorName: row.sector_name || row.industry,
                                        source: "factor_screen",
                                        livermoreRank: ranks.livermoreRank,
                                        meanReversionRank: ranks.meanReversionRank,
                                        factorScreenRank: row.rank,
                                      });
                                    }
                                  }}
                                >
                                  <div>
                                    <strong>#{row.rank}</strong>{" "}
                                    <span className="stock-analysis-page__tabular">{row.stock_code}</span>{" "}
                                    {row.stock_name}{" "}
                                    <small className="stock-analysis-page__tabular">
                                      {row.sector_name || row.industry || "-"}
                                    </small>
                                  </div>
                                  <div className="stock-analysis-page__factor-screen-metrics stock-analysis-page__tabular">
                                    <span>得分 {row.score.toFixed(3)}</span>
                                    {row.pe != null && <span>PE {row.pe.toFixed(1)}</span>}
                                    {row.roe != null && <span>ROE {(row.roe * 100).toFixed(1)}%</span>}
                                    {row.three_month_return != null && (
                                      <span>3月 {(row.three_month_return * 100).toFixed(1)}%</span>
                                    )}
                                    {row.dividend_yield != null && row.dividend_yield > 0 && (
                                      <span>股息 {(row.dividend_yield * 100).toFixed(2)}%</span>
                                    )}
                                  </div>
                                </li>
                              ))}
                            </ul>
                          )}
                          <p className="stock-analysis-page__footnote">
                            多因子选股：综合价值（PE/PB/PS 倒数）、质量（ROE/毛利率）、动量（3月/12月收益）、低波动、股息五个因子加权评分，
                            取前 10%。{factorScreenPayload?.coverage_note ?? ""}
                            仅作复核观察，不给出操作动作提示。
                          </p>
                        </div>
                      ),
                    },
                  ]}
                />
              </section>

              <section
                className="stock-analysis-page__panel stock-analysis-page__panel--compact"
                data-testid="stock-analysis-events-monitoring"
              >
                <div className="stock-analysis-page__section-head">
                  <div>
                    <h2>关键事件与监控</h2>
                    <p>汇总诊断、缺口、未支持输出和风险触发项，只作为复核队列的事件清单。</p>
                  </div>
                  <span className="stock-analysis-page__pill">Monitor</span>
                </div>
                {eventMonitorRows.length > 0 ? (
                  <div className="stock-analysis-page__table-wrap">
                    <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                      <thead>
                        <tr>
                          <th scope="col">来源</th>
                          <th scope="col">级别</th>
                          <th scope="col">影响域</th>
                          <th scope="col">事件</th>
                          <th scope="col">说明</th>
                        </tr>
                      </thead>
                      <tbody>
                        {eventMonitorRows.map((row) => (
                          <tr key={row.key} data-level={row.level}>
                            <td>{row.source}</td>
                            <td>
                              <span className="stock-analysis-page__event-level" data-level={row.level}>
                                {row.level}
                              </span>
                            </td>
                            <td>{row.impact}</td>
                            <td>{row.event}</td>
                            <td>{row.detail}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="stock-analysis-page__empty">暂无关键事件，继续以只读证据复核。</p>
                )}
              </section>
              </div>

              <aside className="stock-analysis-page__rail" aria-label="股票分析辅助信息">
              <section className="stock-analysis-page__panel stock-analysis-page__panel--rail" data-testid="stock-analysis-risk-section">
                <div className="stock-analysis-page__section-head">
                  <div>
                    <h2>风险退出观察</h2>
                    <p>展示风险退出项、观察项与可用的联动观察，不使用执行动作标签。</p>
                  </div>
                  <span className="stock-analysis-page__pill">退出观察价</span>
                </div>
                {confluenceQuery.isError ? (
                  <p className="stock-analysis-page__notice">联动观察暂不可用。</p>
                ) : null}
                {riskExitUnsupported ? (
                  <div className="stock-analysis-page__notice-block">
                    <strong>风险退出观察暂不可用。</strong>
                    <p>{riskExitUnsupported.reason}</p>
                  </div>
                ) : null}
                {riskRows.length > 0 ? (
                  <div className="stock-analysis-page__rail-list">
                    {riskRows.map((row) => (
                      <div
                        className="stock-analysis-page__rail-row stock-analysis-page__rail-row--interactive"
                        data-testid={`stock-risk-row-${row.stockCode}`}
                        key={`${row.stockCode}:${row.status}:${row.reason}`}
                        role="button"
                        tabIndex={0}
                        onClick={() => {
                          const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stockCode);
                          setDetailSelection({
                            code: row.stockCode,
                            name: row.stockName,
                            source: "risk_exit",
                            livermoreRank: ranks.livermoreRank,
                            meanReversionRank: ranks.meanReversionRank,
                            factorScreenRank: ranks.factorScreenRank,
                          });
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stockCode);
                            setDetailSelection({
                              code: row.stockCode,
                              name: row.stockName,
                              source: "risk_exit",
                              livermoreRank: ranks.livermoreRank,
                              meanReversionRank: ranks.meanReversionRank,
                              factorScreenRank: ranks.factorScreenRank,
                            });
                          }
                        }}
                      >
                        <div>
                          <strong>{row.stockName}</strong>
                          <small>{row.stockCode}</small>
                        </div>
                        <span>{riskStatusLabel(row.status)}</span>
                        <p className="stock-analysis-page__tabular">
                          最新收盘 {row.latestClose} / 退出观察价 {row.exitWatchPrice} / 距价 {row.distanceToExitPct}{" "}
                          <small>({row.exitDistanceBucket})</small>
                        </p>
                        <p>{row.reason}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="stock-analysis-page__empty">
                    {riskExitUnsupported
                      ? "等待持仓快照接入后生成风险退出观察项。"
                      : "当前无风险退出观察项。"}
                  </p>
                )}
              </section>

              <section
                className="stock-analysis-page__panel stock-analysis-page__panel--rail"
                data-testid="stock-analysis-boundary-rail"
              >
                <div className="stock-analysis-page__section-head">
                  <div>
                    <h2>数据口径与边界</h2>
                    <p>只读链路的可追溯标签；完整诊断请看抽屉分组。</p>
                  </div>
                  <span className="stock-analysis-page__pill">只读链路</span>
                </div>
                <div className="stock-analysis-page__toolbar-meta">
                  {metaSegments.map((seg, index) => (
                    <span key={seg.key} className="stock-analysis-page__toolbar-meta-code">
                      {index > 0 ? " / " : null}
                      {`${seg.key}=${seg.text}`}
                    </span>
                  ))}
                </div>
                {boundarySummary ? (
                  <p className="stock-analysis-page__boundary-summary" data-testid="stock-analysis-boundary-summary">
                    <strong>{boundarySummary.summaryLabel}</strong>
                    <span>{boundarySummary.detailLabel}</span>
                    {boundarySummary.topMessages[0] ? <small>{boundarySummary.topMessages[0]}</small> : null}
                  </p>
                ) : null}
                <Button type="link" aria-expanded={boundaryDrawerOpen} onClick={() => setBoundaryDrawerOpen(true)}>
                  查看完整诊断
                </Button>
                <Drawer
                  title="数据口径诊断"
                  open={boundaryDrawerOpen}
                  onClose={() => setBoundaryDrawerOpen(false)}
                  destroyOnClose
                  width={480}
                >
                  {strategyPayload ? (
                    <>
                      <Text strong type="danger">
                        严重 / Error
                      </Text>
                      <ul>
                        {strategyPayload.diagnostics
                          .filter((d) => d.severity === "error")
                          .map((d) => (
                            <li key={d.code}>{d.message}</li>
                          ))}
                        {strategyPayload.diagnostics.filter((d) => d.severity === "error").length === 0 ? (
                          <li>暂无</li>
                        ) : null}
                      </ul>
                      <Text strong type="warning">
                        警告 / Warning
                      </Text>
                      <ul>
                        {strategyPayload.diagnostics
                          .filter((d) => d.severity === "warning")
                          .map((d) => (
                            <li key={d.code}>{d.message}</li>
                          ))}
                        {strategyPayload.diagnostics.filter((d) => d.severity === "warning").length === 0 ? (
                          <li>暂无</li>
                        ) : null}
                      </ul>
                      <Text strong type="secondary">
                        信息 / Info
                      </Text>
                      <ul>
                        {strategyPayload.diagnostics
                          .filter((d) => d.severity === "info")
                          .map((d) => (
                            <li key={d.code}>{d.message}</li>
                          ))}
                      </ul>
                      <Typography.Title level={5}>data_gaps</Typography.Title>
                      <ul>
                        {strategyPayload.data_gaps.map((g) => (
                          <li key={`${g.input_family}-${g.status}`}>
                            <strong>{g.input_family}</strong> {g.status}: {g.evidence}
                          </li>
                        ))}
                      </ul>
                      <Typography.Title level={5}>supported_outputs</Typography.Title>
                      <p>{strategyPayload.supported_outputs.join(", ") || "无"}</p>
                      <Typography.Title level={5}>unsupported_outputs</Typography.Title>
                      <ul>
                        {strategyPayload.unsupported_outputs.map((u) => (
                          <li key={u.key}>
                            <strong>{u.key}</strong>: {u.reason}
                          </li>
                        ))}
                      </ul>
                    </>
                  ) : null}
                </Drawer>
              </section>
              </aside>
            </AnalysisGrid>
          </>
        ) : null}
        <StockDetailDrawer
          stockCode={detailSelection?.code ?? null}
          stockName={detailSelection?.name}
          asOfDate={stockDetailAsOfDate}
          reviewContext={
            detailSelection
              ? {
                  sourceLabel:
                    detailSelection.source === "risk_exit"
                      ? "风险退出观察"
                      : detailSelection.source === "mean_reversion"
                        ? "超跌反弹观察"
                        : detailSelection.source === "factor_screen"
                          ? "多因子选股"
                          : detailSelection.source === "consensus"
                            ? "多策略共振"
                            : "复核队列",
                  sectorName: detailSelection.sectorName,
                  reviewRank: detailSelection.reviewRank,
                  distanceToBreakoutPct: detailSelection.distanceToBreakoutPct,
                  livermoreRank: detailSelection.livermoreRank,
                  meanReversionRank: detailSelection.meanReversionRank,
                  factorScreenRank: detailSelection.factorScreenRank,
                }
              : null
          }
          onClose={() => setDetailSelection(null)}
        />
        <Drawer
          title="Agent 复核当前观察"
          placement="left"
          width={480}
          open={agentDrawerOpen}
          onClose={() => setAgentDrawerOpen(false)}
          destroyOnClose
          className="stock-analysis-page__agent-drawer"
          data-testid="stock-analysis-agent-drawer"
          maskClosable
        >
          <div style={stockAnalysisPageCssVars} className="stock-analysis-page__agent-drawer-body">
            <AgentPanel
              pageId="stock-analysis"
              currentFilters={stockAnalysisAgentPageContext.current_filters}
              defaultFilters={{ research_domain: "stock" }}
              selectedRows={stockAnalysisAgentPageContext.selected_rows}
              contextNote={stockAnalysisAgentPageContext.context_note ?? null}
            />
          </div>
        </Drawer>
      </main>
    </PageV2Shell>
  );
}
