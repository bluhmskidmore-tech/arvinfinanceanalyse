import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BarChartOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  FireOutlined,
  LineChartOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  StockOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Alert, Button, Collapse, DatePicker, Drawer, Tabs, Typography } from "antd";
import dayjs from "dayjs";

import { useApiClient } from "../../../api/client";
import type {
  LivermoreCandidateHistoryHorizonKey,
  LivermoreCandidateHistoryHorizonStats,
  LivermoreCandidateHistoryPayload,
  LivermoreCandidateHistoryPortfolioBacktestPayload,
  LivermoreCycleProxyBacktestPayload,
  LivermoreStrategyPayload,
  LivermoreSectorRankSeriesPoint,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyOptimizationPayload,
  LivermoreStrategyScorePayload,
  ResultMeta,
} from "../../../api/contracts";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import {
  AnalysisGrid,
  DataStatusStrip,
  PageV2Shell,
} from "../../../components/page/PagePrimitives";
import { AgentPanel } from "../../agent/AgentPanel";
import {
  buildCandidateReviewQueue,
  buildClosedLoopSummary,
  buildCycleMacroLayerSummary,
  buildDailyJudgmentStrip,
  buildDataBoundarySummary,
  buildDecisionSummary,
  buildMarketStateCard,
  buildRiskExitRows,
  buildSectorFilterSummary,
  buildSectorRows,
  buildSectorTableSortComparator,
  buildSectorViewModel,
  buildStockAnalysisEventMonitorRows,
  buildStockAnalysisEvidenceStatus,
  buildStockAnalysisKpiStrip,
  buildConsensusReviewPanelSummary,
  buildCycleRotationPanelSummary,
  buildDeepAnalysisGateSummary,
  buildEventsMonitoringPanelSummary,
  buildMarketPriorityPanelSummary,
  buildObservationPoolsPanelSummary,
  buildStrategyBacktestPanelSummary,
  buildStrategyOptimizationPanelSummary,
  buildThemeBreakoutPanelSummary,
  buildThemeBreakoutCards,
  buildThemeBreakoutReviewItems,
  buildThemeEvidenceStateRows,
  buildStockAnalysisPagePurpose,
  buildReviewQueueEmptyState,
  localizeImplementationStage,
  localizeMarketDataStatus,
  localizeThemeRadarBadge,
  type StockStrategyPanelQueryState,
} from "../lib/stockAnalysisPageModel";
import type {
  StockSectorRow,
  StockSectorViewKind,
  StockSectorViewRow,
} from "../lib/stockAnalysisPageModel";
import { buildStockAnalysisAgentPageContext } from "../lib/buildStockAnalysisAgentPageContext";
import { buildConsensusSummary, consensusStrategyLabel, lookupStockStrategyRanks } from "../lib/buildConsensusSummary";
import { EquityKpiCard } from "../components/EquityKpiCard";
import { StrategyModuleCard } from "../components/StrategyModuleCard";
import { StrategyPanelComplianceDetails } from "../components/StrategyPanelResultStrip";
import { StockDetailDrawer } from "../components/StockDetailDrawer";
import { stockAnalysisPageCssVars } from "../lib/stockAnalysisTokens";
import "./StockAnalysisPage.css";

const { Text } = Typography;

const STOCK_ANALYSIS_STALE_TIME_MS = 5 * 60_000;
const STOCK_ANALYSIS_GC_TIME_MS = 15 * 60_000;
const STOCK_ANALYSIS_DEFERRED_SECTION_FALLBACK_MS = 1_000;

const stockAnalysisReadQueryOptions = {
  staleTime: STOCK_ANALYSIS_STALE_TIME_MS,
  gcTime: STOCK_ANALYSIS_GC_TIME_MS,
  refetchOnWindowFocus: false,
} as const;
const EMPTY_STRATEGY_PRIORITY_ROWS: LivermoreStrategyScorePayload["rows"] = [];

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

function compactText(text: string | null | undefined, maxLength = 28) {
  if (!text) return "";
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength - 1)}…`;
}

function formatGeneratedAtLabel(value: string | null | undefined) {
  if (!value) return "";
  const parsed = dayjs(value);
  return parsed.isValid() ? parsed.format("MM-DD HH:mm") : compactText(value, 12);
}

function iconTone(tone?: string) {
  if (tone === "positive") return "positive";
  if (tone === "negative") return "negative";
  if (tone === "warning") return "warning";
  return "neutral";
}

function useDeferredSectionSeen<TElement extends HTMLElement>(
  enabled: boolean,
  delayMs = STOCK_ANALYSIS_DEFERRED_SECTION_FALLBACK_MS,
) {
  const ref = useRef<TElement | null>(null);
  const [seen, setSeen] = useState(false);

  useEffect(() => {
    if (seen || !enabled) return undefined;

    if (typeof IntersectionObserver === "undefined") {
      const timer = window.setTimeout(() => setSeen(true), delayMs);
      return () => window.clearTimeout(timer);
    }

    const node = ref.current;
    if (!node) return undefined;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setSeen(true);
          observer.disconnect();
        }
      },
      { rootMargin: "240px 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [delayMs, enabled, seen]);

  return { ref, seen };
}

const tabularNumStyle: CSSProperties = {
  fontVariantNumeric: "tabular-nums",
  fontFamily: "var(--moss-font-mono)",
};

/** 首屏卡片与标题 — 对齐 dashboard-home 终端视觉 */
const SA_FIRST_CARD = "stock-analysis-page__dh-card stock-analysis-page__dh-panel bg-white";
const SA_FIRST_HERO = "stock-analysis-page__dh-card stock-analysis-page__dh-hero bg-white";
const SA_CARD_TITLE = "m-0";
const SA_SECTION_HEAD = "stock-analysis-page__dh-section-head";
const SA_SECTION_DESC = "stock-analysis-page__dh-section-desc";
const SA_SECTION_EYEBROW = "stock-analysis-page__dh-section-eyebrow";
const SA_PILL = "stock-analysis-page__dh-pill";
/** 首屏以下深度折叠区 — 白底卡片 + 16px 内边距 */
const _SA_DEEP_CARD =
  "stock-analysis-page__dh-card stock-analysis-page__dh-panel stock-analysis-page__dh-deep-section bg-white";

function kpiToneToDelta(tone?: string): "up" | "down" | "flat" {
  if (tone === "positive") return "up";
  if (tone === "negative") return "down";
  return "flat";
}

function filterChipClass(active: boolean): string {
  const base =
    "inline-flex min-h-7 cursor-pointer items-center whitespace-nowrap rounded-full border px-2.5 text-xs font-semibold transition-colors";
  return active
    ? `${base} border-primary-500 bg-primary-50 text-primary-800`
    : `${base} border-neutral-200 bg-neutral-50 text-neutral-700 hover:bg-neutral-100`;
}

function statusIconClass(tone?: string): string {
  const base = "inline-grid h-5 w-5 shrink-0 place-items-center rounded border text-xs leading-none";
  if (tone === "positive") return `${base} border-success-200 bg-success-50 text-success-700`;
  if (tone === "warning") return `${base} border-warning-200 bg-warning-50 text-warning-700`;
  if (tone === "negative") return `${base} border-danger-200 bg-danger-50 text-danger-700`;
  return `${base} border-primary-200 bg-primary-50 text-primary-700`;
}

function toneDotClass(tone?: string): string {
  if (tone === "positive") return "bg-success-600";
  if (tone === "warning") return "bg-warning-600";
  if (tone === "negative") return "bg-danger-600";
  return "bg-neutral-400";
}

function toneTextClass(tone?: string): string {
  if (tone === "positive") return "text-success-600";
  if (tone === "warning") return "text-warning-600";
  if (tone === "negative") return "text-danger-600";
  return "text-neutral-600";
}

function tonePillClass(tone?: string): string {
  if (tone === "positive") return "border border-success-200 bg-success-50 text-success-700";
  if (tone === "warning") return "border border-warning-200 bg-warning-50 text-warning-700";
  if (tone === "negative") return "border border-danger-200 bg-danger-50 text-danger-700";
  return "border border-neutral-200 bg-neutral-50 text-neutral-600";
}

function closedLoopItemSurfaceClass(tone?: string): string {
  if (tone === "positive") return "border-neutral-200 bg-success-50/40";
  if (tone === "warning") return "border-neutral-200 bg-warning-50/50";
  if (tone === "negative") return "border-neutral-200 bg-danger-50/40";
  return "border-neutral-200 bg-neutral-50/80";
}

function StatusIcon({
  tone = "neutral",
  children,
}: {
  tone?: string;
  children: React.ReactNode;
}) {
  return (
    <span aria-hidden="true" className={statusIconClass(iconTone(tone))}>
      {children}
    </span>
  );
}

const DECISION_GRID_ICONS = [
  <ClockCircleOutlined key="date" />,
  <DatabaseOutlined key="basis" />,
  <SafetyCertificateOutlined key="boundary" />,
  <CheckCircleOutlined key="gate" />,
];

const FIRST_SCREEN_ICONS = [
  <BarChartOutlined key="sectors" />,
  <ThunderboltOutlined key="consensus" />,
  <StockOutlined key="queue" />,
  <FireOutlined key="events" />,
];

const SECTION_HEAD_ICONS = [
  <LineChartOutlined key="sector" />,
  <SafetyCertificateOutlined key="risk" />,
  <DatabaseOutlined key="boundary" />,
];

/** 图表色 — 对齐 dashboard-home 蓝灰机构台（非旧版绿色主题） */
const stockChartPalette = {
  ink: "#0c1c33",
  muted: "#6b7d95",
  grid: "#e4e9f0",
  track: "#eef2f7",
  primary: "#1850a1",
  primaryLight: "#4d84cc",
  accent: "#2f68b8",
  success: "#1f7a55",
  successLight: "#86acdb",
  danger: "#b94743",
};

const miniBarChartStyle: CSSProperties = { height: 54, width: "100%" };
const miniStackChartStyle: CSSProperties = { height: 40, width: "100%" };
const sectorStrengthChartStyle: CSSProperties = { height: 190, width: "100%" };

type CompactChartRow = {
  key: string;
  label: string;
  value: number;
  detail?: string;
};

function resolveSectorMetricValue(row: StockSectorRow, view: StockSectorViewKind): number | null {
  if (view === "pctchange") return row.pctChangeValue;
  if (view === "turnover") return row.turnoverValue;
  if (view === "amplitude") return row.amplitudeValue;
  return row.scoreValue;
}

function sectorViewLabel(view: StockSectorViewKind): string {
  const tab = sectorViewTabs.find((item) => item.key === view);
  return tab?.label ?? "综合得分";
}

function buildCompactBarOption({
  labels,
  values,
  color = stockChartPalette.primary,
  valueSuffix = "",
}: {
  labels: string[];
  values: number[];
  color?: string;
  valueSuffix?: string;
}): EChartsOption {
  return {
    animation: false,
    grid: { top: 2, right: 4, bottom: 2, left: 2, containLabel: false },
    xAxis: { type: "value", show: false, splitLine: { show: false } },
    yAxis: {
      type: "category",
      inverse: true,
      data: labels,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
    },
    series: [
      {
        type: "bar",
        data: values,
        barWidth: 8,
        itemStyle: { color, borderRadius: [2, 2, 2, 2] },
        backgroundStyle: { color: stockChartPalette.track, borderRadius: 2 },
        showBackground: true,
      },
    ],
    tooltip: {
      trigger: "axis",
      confine: true,
      formatter: (params) => {
        const item = Array.isArray(params) ? params[0] : params;
        const index = Number(item?.dataIndex ?? 0);
        return `${labels[index] ?? ""}: ${Number(item?.value ?? 0).toFixed(2)}${valueSuffix}`;
      },
    },
  };
}

function buildEventSummaryOption(rows: Array<{ label: string; count: number }>): EChartsOption {
  return {
    animation: false,
    grid: { top: 4, right: 4, bottom: 4, left: 2, containLabel: false },
    xAxis: { type: "value", show: false, splitLine: { show: false } },
    yAxis: { type: "category", show: false, data: ["events"] },
    series: rows.map((row, index) => ({
      name: row.label,
      type: "bar",
      stack: "events",
      data: [row.count],
      barWidth: 10,
      itemStyle: {
        color: [
          stockChartPalette.primary,
          stockChartPalette.accent,
          stockChartPalette.danger,
          stockChartPalette.primaryLight,
        ][index],
        borderRadius: index === 0 ? [2, 0, 0, 2] : index === rows.length - 1 ? [0, 2, 2, 0] : 0,
      },
    })),
    tooltip: { trigger: "item", confine: true },
  };
}

function buildSectorStrengthOption({
  rows,
  view,
  activeSectorCode,
}: {
  rows: StockSectorViewRow[];
  view: StockSectorViewKind;
  activeSectorCode: string | null;
}): EChartsOption {
  const values = rows.map((row) => resolveSectorMetricValue(row, view) ?? 0);
  return {
    animation: false,
    grid: { top: 8, right: 52, bottom: 6, left: 86, containLabel: false },
    xAxis: {
      type: "value",
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: stockChartPalette.muted,
        fontSize: 10,
      },
      splitLine: {
        lineStyle: { color: stockChartPalette.grid, type: "dashed" },
      },
    },
    yAxis: {
      type: "category",
      inverse: true,
      data: rows.map((row) => row.sectorName),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: stockChartPalette.ink,
        fontSize: 11,
        width: 74,
        overflow: "truncate",
      },
    },
    series: [
      {
        type: "bar",
        data: rows.map((row, index) => ({
          value: values[index],
          itemStyle: {
            color:
              row.sectorCode === activeSectorCode
                ? stockChartPalette.primary
                : stockChartPalette.primaryLight,
            borderRadius: [0, 3, 3, 0],
          },
        })),
        barWidth: 12,
        label: {
          show: true,
          position: "right",
          color: stockChartPalette.muted,
          fontSize: 10,
          formatter: (params) => {
            const row = rows[Number(params.dataIndex ?? 0)];
            if (!row) return "";
            if (view === "score") return row.score;
            if (view === "pctchange") return row.pctChange;
            if (view === "turnover") return row.turnover;
            return row.amplitude;
          },
        },
      },
    ],
    tooltip: {
      trigger: "axis",
      confine: true,
      formatter: (params) => {
        const item = Array.isArray(params) ? params[0] : params;
        const row = rows[Number(item?.dataIndex ?? 0)];
        if (!row) return "";
        return `${row.rank}. ${row.sectorName}<br/>${sectorViewLabel(view)}: ${
          view === "score" ? row.score : view === "pctchange" ? row.pctChange : view === "turnover" ? row.turnover : row.amplitude
        }<br/>成分 ${row.constituentCount}`;
      },
    },
  };
}
function riskStatusLabel(status: "triggered" | "watch") {
  return status === "triggered" ? "触发复核" : "观察中";
}

function formatSupplyPercent(value: number | null | undefined, digits = 0) {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${(value * 100).toFixed(digits)}%`;
}

function readinessTone(status: string) {
  if (status === "ready") return "positive";
  if (status === "partial" || status === "stale") return "warning";
  if (status === "missing" || status === "blocked") return "negative";
  return "neutral";
}

function gapTone(status: string) {
  if (status === "ready") return "positive";
  if (status === "partial" || status === "stale") return "warning";
  return "negative";
}

function buildStatusCounts(rows: Array<{ status: string }>) {
  return rows.reduce<Record<string, number>>((acc, row) => {
    acc[row.status] = (acc[row.status] ?? 0) + 1;
    return acc;
  }, {});
}

function outputKeyLabel(key: string | null | undefined) {
  const labels: Record<string, string> = {
    market_gate: "市场门控",
    sector_rank: "板块排序",
    stock_candidates: "趋势候选",
    mean_reversion_candidates: "超跌池",
    factor_screen_candidates: "多因子",
    theme_breakout: "题材观察",
    hybrid_fusion: "融合池",
    risk_exit: "风险退出",
  };
  return key ? (labels[key] ?? key.replace(/_/g, " ")) : "待补";
}

function dataGapFamilyLabel(inputFamily: string | null | undefined) {
  const labels: Record<string, string> = {
    breadth: "市场宽度",
    limit_up_quality: "涨停质量",
    sector_strength: "板块强度",
    stock_universe: "股票池",
    position_risk: "持仓风险",
    PMI: "PMI",
    credit_impulse: "信用脉冲",
  };
  return inputFamily ? (labels[inputFamily] ?? inputFamily.replace(/_/g, " ")) : "待补";
}

function buildBackendSupplyOverview(
  payload: LivermoreStrategyPayload,
  meta: Partial<ResultMeta> = {},
) {
  const gate = payload.market_gate;
  const readinessRows = payload.rule_readiness ?? [];
  const dataGaps = payload.data_gaps ?? [];
  const unsupportedOutputs = payload.unsupported_outputs ?? [];
  const supportedOutputs = payload.supported_outputs ?? [];
  const readyRuleCount = readinessRows.filter((row) => row.status === "ready").length;
  const notReadyGaps = dataGaps.filter((row) => row.status !== "ready");
  const risk = payload.risk_exit;
  const candidateCount =
    payload.stock_candidates?.candidate_count ??
    payload.hybrid_fusion_candidates?.candidate_count ??
    0;
  const sectorCount = payload.sector_rank?.sector_count ?? payload.sector_rank?.items.length ?? 0;
  const watchCount = risk?.watch_items?.length ?? 0;

  return {
    asOfLabel: payload.as_of_date ?? payload.requested_as_of_date ?? "日期待补",
    requestedAsOfLabel: payload.requested_as_of_date ?? "默认",
    gateLabel: `门控 ${gate.state}`,
    exposureLabel: `暴露 ${formatSupplyPercent(gate.exposure)}`,
    conditionLabel: `条件 ${gate.passed_conditions}/${gate.required_conditions}`,
    availableConditionLabel: `可评估 ${gate.available_conditions}`,
    readinessLabel: `就绪 ${readyRuleCount}/${readinessRows.length}`,
    dataGapLabel: `缺口 ${notReadyGaps.length}`,
    supportedLabel: `可用 ${supportedOutputs.length}`,
    unsupportedLabel: `阻断 ${unsupportedOutputs.length}`,
    sectorSupplyLabel: `板块 ${sectorCount}`,
    candidateSupplyLabel: `候选 ${candidateCount}`,
    riskSupplyLabel: `风险 ${risk?.signal_count ?? 0}`,
    riskDetailLabel: `持仓 ${risk?.position_count ?? 0} / 触发 ${risk?.signal_count ?? 0} / 观察 ${watchCount}`,
    qualityLabel: `质量 ${meta.quality_flag ?? "待补"}`,
    vendorLabel: `通道 ${meta.vendor_status ?? "待补"}`,
    fallbackLabel: `回退 ${meta.fallback_mode ?? "待补"}`,
    basisLabel: payload.basis,
    strategyName: payload.strategy_name,
    readinessRows,
    dataGapRows: dataGaps,
    supportedOutputs,
    unsupportedOutputs,
    risk,
  };
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

const strategyBacktestOrder = ["hybrid_fusion", "stock_candidate", "factor_screen", "theme_breakout", "mean_reversion"] as const;

const strategyBacktestLabels: Record<string, string> = {
  hybrid_fusion: "融合策略",
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
const strategyBacktestHorizonShortLabels: Record<LivermoreCandidateHistoryHorizonKey, string> = {
  return_1d: "T+1",
  return_5d: "T+5",
  return_20d: "T+20",
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
type StrategyMaturity = NonNullable<NonNullable<StrategyPriorityRow["diagnostics"]>["maturity"]>;
type StrategyTrackedSnapshot = StrategyMaturity["tracked_snapshots"][number];
type StrategyMaturityCandidate = LivermoreCandidateHistoryPayload["items"][number];

function formatPriorityScore(value: number | null | undefined): string {
  return value == null || Number.isNaN(value) ? "-" : value.toFixed(1);
}

function resolvePanelQueryState(input: {
  enabled: boolean;
  isLoading: boolean;
  isError: boolean;
}): StockStrategyPanelQueryState {
  if (!input.enabled) return "idle";
  if (input.isLoading) return "loading";
  if (input.isError) return "error";
  return "ready";
}

function buildStrategyPriorityHeadline(rows: StrategyPriorityRow[]): string {
  const sufficientRows = rows.filter((row) => row.sample_status === "sufficient");
  if (rows.length === 0 || sufficientRows.length === 0) {
    return "当前状态样本不足";
  }
  const priorityCandidates = sufficientRows.filter(
    (row) => row.priority_label === "优先复核" && (row.diagnostics?.risk_flags ?? []).length === 0,
  );
  const priorityRows = priorityCandidates.filter((row) => row.diagnostics?.maturity?.status !== "narrow");
  if (priorityRows.length > 0) {
    return `优先复核：${priorityRows.map((row) => row.strategy_label).join("、")}`;
  }
  if (priorityCandidates.length > 0) {
    return `优先观察：${priorityCandidates.map((row) => row.strategy_label).join("、")}`;
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
  if (diagnostics.maturity?.status === "narrow") {
    labels.push(`${diagnostics.maturity.label} ${diagnostics.maturity.reason}`);
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

function resolveStrategyMaturityRow(rows: StrategyPriorityRow[]): StrategyPriorityRow | null {
  return (
    rows.find(
      (row) =>
        row.diagnostics?.priority_scope === "rank<=10" &&
        (row.diagnostics?.maturity?.tracked_snapshots ?? []).length > 0,
    ) ??
    rows.find((row) => (row.diagnostics?.maturity?.tracked_snapshots ?? []).length > 0) ??
    null
  );
}

function strategyMaturityRemainingText(maturity: StrategyMaturity): string {
  const remaining = Math.max(maturity.min_mature_snapshot_count - maturity.mature_snapshot_count, 0);
  return remaining > 0 ? `还差 ${remaining} 个成熟快照` : "成熟快照已达标";
}

function strategyMaturityHorizonText(
  snapshot: StrategyTrackedSnapshot,
  horizon: LivermoreCandidateHistoryHorizonKey,
): string {
  const stats = snapshot.horizons[horizon];
  const label = strategyBacktestHorizonShortLabels[horizon];
  if (!stats || stats.status === "pending" || stats.available_count <= 0) {
    return `${label} 待成熟`;
  }
  const statusText = stats.status === "partial" ? "部分成熟" : "已成熟";
  return `${label} ${statusText} ${backtestStatsText(stats)}`;
}

function strategyCandidateReturnText(value: number | null | undefined): string {
  return value == null || Number.isNaN(value) ? "待成熟" : formatBacktestSignedPercent(value);
}

type StrategyOptimizationSummary = LivermoreStrategyOptimizationPayload["strategy_summaries"][number];
type StrategyOptimizationSlice = LivermoreStrategyOptimizationPayload["slices"][number];

const strategyOptimizationCoreKinds = ["hybrid_fusion", "stock_candidate", "factor_screen", "theme_breakout"] as const;

function buildStrategyOptimizationRows(
  payload: LivermoreStrategyOptimizationPayload | null,
): StrategyOptimizationSummary[] {
  if (!payload) return [];
  const coreKinds = new Set<string>(strategyOptimizationCoreKinds);
  const coreRows = payload.strategy_summaries.filter((row) => coreKinds.has(row.signal_kind));
  return (coreRows.length > 0 ? coreRows : payload.strategy_summaries).slice(0, 3);
}

function strategyOptimizationPrimaryStats(
  row: StrategyOptimizationSummary | StrategyOptimizationSlice,
  payload: LivermoreStrategyOptimizationPayload | null,
): LivermoreCandidateHistoryHorizonStats | undefined {
  const horizon = payload?.primary_horizon ?? "return_5d";
  return row.stats[horizon] ?? row.stats.return_5d;
}

function strategyOptimizationDateWeightedText(
  row: StrategyOptimizationSummary | StrategyOptimizationSlice,
  payload: LivermoreStrategyOptimizationPayload | null,
): string {
  const horizon = payload?.primary_horizon ?? "return_5d";
  const stats = row.date_weighted_stats[horizon] ?? row.date_weighted_stats.return_5d;
  if (!stats || stats.available_day_count <= 0) return "待补";
  return `${stats.available_day_count}日等权 ${formatBacktestSignedPercent(stats.avg_return)} / 正收益日 ${formatBacktestPercent(
    stats.positive_day_rate,
  )}`;
}

function strategyOptimizationSlicePair(
  payload: LivermoreStrategyOptimizationPayload | null,
): { strongest: StrategyOptimizationSlice | null; weakest: StrategyOptimizationSlice | null } {
  if (!payload) return { strongest: null, weakest: null };
  const matureSlices = payload.slices.filter((slice) => slice.recommendation.action !== "pending_more_history");
  const strongest =
    [...matureSlices]
      .filter((slice) => slice.recommendation.action === "promote")
      .sort((left, right) => (right.recommendation.score ?? -1) - (left.recommendation.score ?? -1))[0] ??
    [...matureSlices].sort((left, right) => (right.recommendation.score ?? -1) - (left.recommendation.score ?? -1))[0] ??
    null;
  const weakest =
    [...matureSlices]
      .filter((slice) => slice.recommendation.action === "downgrade")
      .sort((left, right) => {
        const leftReturn = left.recommendation.avg_return ?? Number.POSITIVE_INFINITY;
        const rightReturn = right.recommendation.avg_return ?? Number.POSITIVE_INFINITY;
        return leftReturn - rightReturn;
      })[0] ??
    [...matureSlices].sort((left, right) => {
      const leftReturn = left.recommendation.avg_return ?? Number.POSITIVE_INFINITY;
      const rightReturn = right.recommendation.avg_return ?? Number.POSITIVE_INFINITY;
      return leftReturn - rightReturn;
    })[0] ??
    null;
  return { strongest, weakest };
}

function buildStrategyMaturityCandidates(
  payload: LivermoreCandidateHistoryPayload | null,
  row: StrategyPriorityRow | null,
  snapshots: StrategyTrackedSnapshot[],
): StrategyMaturityCandidate[] {
  if (!payload || !row || snapshots.length === 0) return [];
  const visibleSnapshotDates = new Set(snapshots.map((snapshot) => snapshot.snapshot_as_of_date));
  const maxRank = row.diagnostics?.priority_scope === "rank<=10" ? 10 : null;
  return payload.items
    .filter((item) => visibleSnapshotDates.has(item.snapshot_as_of_date))
    .filter((item) => (item.signal_kind ?? "stock_candidate") === row.signal_kind)
    .filter((item) => maxRank == null || item.candidate_rank <= maxRank)
    .sort((left, right) => {
      const dateOrder = right.snapshot_as_of_date.localeCompare(left.snapshot_as_of_date);
      if (dateOrder !== 0) return dateOrder;
      return left.candidate_rank - right.candidate_rank;
    });
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
    source?: "review_queue" | "risk_exit" | "mean_reversion" | "factor_screen" | "hybrid_fusion" | "consensus";
    livermoreRank?: number | null;
    meanReversionRank?: number | null;
    factorScreenRank?: number | null;
    hybridFusionRank?: number | null;
  } | null>(null);
  const [agentDrawerOpen, setAgentDrawerOpen] = useState(false);
  const [sectorSeriesCollapseKeys, setSectorSeriesCollapseKeys] = useState<string[]>([]);
  const [sectorSeriesWindow, setSectorSeriesWindow] = useState<5 | 20>(5);
  const [expandedStrategyCardIds, setExpandedStrategyCardIds] = useState<string[]>([]);

  const toggleStrategyCard = (id: string) => {
    setExpandedStrategyCardIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id],
    );
  };

  const isStrategyCardExpanded = (id: string) => expandedStrategyCardIds.includes(id);

  const strategyQueryKey = ["stock-analysis", "livermore-strategy", asOfOverride ?? "__default"] as const;

  const strategyQuery = useQuery({
    queryKey: strategyQueryKey,
    queryFn: () =>
      asOfOverride
        ? client.getLivermoreStrategy({ asOfDate: asOfOverride })
        : client.getLivermoreStrategy(),
    ...stockAnalysisReadQueryOptions,
  });

  const strategyPayload = strategyQuery.data?.result ?? null;
  const deferredSectionsEnabled = Boolean(strategyPayload?.as_of_date);
  const cycleFrameworkSection = useDeferredSectionSeen<HTMLElement>(deferredSectionsEnabled);
  const strategyPrioritySection = useDeferredSectionSeen<HTMLElement>(deferredSectionsEnabled);
  const strategyBacktestSection = useDeferredSectionSeen<HTMLElement>(deferredSectionsEnabled);
  const strategyOptimizationSection = useDeferredSectionSeen<HTMLElement>(deferredSectionsEnabled);

  const confluenceQuery = useQuery({
    queryKey: ["stock-analysis", "livermore-signal-confluence", strategyPayload?.as_of_date ?? "__none"],
    queryFn: () =>
      client.getLivermoreSignalConfluence({
        asOfDate: strategyPayload?.as_of_date ?? undefined,
      }),
    enabled: Boolean(strategyPayload?.as_of_date),
    ...stockAnalysisReadQueryOptions,
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

  const pagePurpose = useMemo(
    () =>
      strategyPayload
        ? buildStockAnalysisPagePurpose(strategyPayload, {
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

  const reviewQueueEmptyState = useMemo(
    () => (strategyPayload ? buildReviewQueueEmptyState(strategyPayload) : null),
    [strategyPayload],
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
  const meanReversionMarketActive = gateState === "WARM";
  const factorScreenPayload = strategyPayload?.factor_screen_candidates;
  const hybridFusionPayload = strategyPayload?.hybrid_fusion_candidates;
  const reviewQueueUsesHybridFusion = (hybridFusionPayload?.items?.length ?? 0) > 0;
  const cycleRotationFramework = strategyPayload?.cycle_rotation_framework;
  const cycleMacroLayerSummary = useMemo(
    () => (strategyPayload ? buildCycleMacroLayerSummary(strategyPayload) : null),
    [strategyPayload],
  );

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

  const eventMonitorRows = useMemo(
    () => (strategyPayload ? buildStockAnalysisEventMonitorRows(strategyPayload, confluencePayload) : []),
    [strategyPayload, confluencePayload],
  );

  const backendSupplyOverview = useMemo(
    () =>
      strategyPayload
        ? buildBackendSupplyOverview(strategyPayload, {
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

  const sectorChartRows = useMemo<CompactChartRow[]>(
    () =>
      sectorRowsFull.slice(0, 5).map((row) => ({
        key: row.sectorCode,
        label: `${row.rank}. ${row.sectorName}`,
        value: row.scoreValue ?? 0,
        detail: `${row.score} / ${row.pctChange}`,
      })),
    [sectorRowsFull],
  );

  const readinessChartRows = useMemo<CompactChartRow[]>(
    () => {
      const counts = buildStatusCounts(backendSupplyOverview?.readinessRows ?? []);
      return ["ready", "partial", "blocked", "missing", "stale"]
        .map((status) => ({
          key: status,
          label: status,
          value: counts[status] ?? 0,
        }))
        .filter((row) => row.value > 0);
    },
    [backendSupplyOverview?.readinessRows],
  );

  const outputChartRows = useMemo<CompactChartRow[]>(
    () =>
      backendSupplyOverview
        ? [
            { key: "supported", label: "可用", value: backendSupplyOverview.supportedOutputs.length },
            { key: "unsupported", label: "阻断", value: backendSupplyOverview.unsupportedOutputs.length },
          ]
        : [],
    [backendSupplyOverview],
  );

  const primaryUnsupportedOutput = backendSupplyOverview?.unsupportedOutputs[0] ?? null;
  const primaryDataGap = backendSupplyOverview?.dataGapRows.find((row) => row.status !== "ready") ?? null;

  const riskSupplyChartRows = useMemo<CompactChartRow[]>(
    () => {
      const risk = backendSupplyOverview?.risk;
      if (!risk) {
        return [
          { key: "position", label: "持仓", value: 0 },
          { key: "signal", label: "触发", value: 0 },
          { key: "watch", label: "观察", value: 0 },
        ];
      }
      return [
        { key: "position", label: "持仓", value: risk.position_count },
        { key: "signal", label: "触发", value: risk.signal_count },
        { key: "watch", label: "观察", value: risk.watch_items?.length ?? 0 },
      ];
    },
    [backendSupplyOverview?.risk],
  );

  const sectorStrengthChartRows = useMemo(() => sectorViewRows.slice(0, 10), [sectorViewRows]);

  const sectorMiniChartOption = useMemo(
    () =>
      buildCompactBarOption({
        labels: sectorChartRows.map((row) => row.label),
        values: sectorChartRows.map((row) => row.value),
        color: stockChartPalette.primary,
      }),
    [sectorChartRows],
  );

  const readinessMiniChartOption = useMemo(
    () =>
      buildCompactBarOption({
        labels: readinessChartRows.map((row) => row.label),
        values: readinessChartRows.map((row) => row.value),
        color: stockChartPalette.accent,
      }),
    [readinessChartRows],
  );

  const outputMiniChartOption = useMemo(
    () =>
      buildEventSummaryOption(
        outputChartRows.map((row) => ({
          label: row.label,
          count: row.value,
        })),
      ),
    [outputChartRows],
  );

  const riskSupplyMiniChartOption = useMemo(
    () =>
      buildEventSummaryOption(
        riskSupplyChartRows.map((row) => ({
          label: row.label,
          count: row.value,
        })),
      ),
    [riskSupplyChartRows],
  );

  const sectorStrengthChartOption = useMemo(
    () =>
      buildSectorStrengthOption({
        rows: sectorStrengthChartRows,
        view: sectorView,
        activeSectorCode: sectorFilterSectorCode,
      }),
    [sectorFilterSectorCode, sectorStrengthChartRows, sectorView],
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

  const dailyJudgmentStrip = useMemo(
    () => (strategyPayload ? buildDailyJudgmentStrip(strategyPayload) : null),
    [strategyPayload],
  );

  const kpiStrip = useMemo(
    () =>
      strategyPayload && !confluenceQuery.isLoading
        ? buildStockAnalysisKpiStrip(strategyPayload, confluencePayload, {
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
        : [],
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

  const evidenceStatusItems = useMemo(
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
  const boundaryRailItems = useMemo(
    () =>
      evidenceStatusItems.filter((item) =>
        ["as-of-date", "rule-version", "quality", "exceptions"].includes(item.key),
      ),
    [evidenceStatusItems],
  );

  const showStaleBanner = Boolean(
    strategyQuery.data?.result_meta &&
      (strategyQuery.data.result_meta.quality_flag !== "ok" ||
        strategyQuery.data.result_meta.vendor_status !== "ok" ||
        strategyQuery.data.result_meta.fallback_mode !== "none"),
  );

  const topBars = sectorViewRows.slice(0, 5);
  const bottomBars = sectorViewRows.slice(Math.max(sectorViewRows.length - 5, 0));
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
    enabled: Boolean(effectiveAsOf && strategyPrioritySection.seen),
    ...stockAnalysisReadQueryOptions,
  });
  const strategyScorePayload = strategyScoreQuery.data?.result ?? null;
  const strategyOptimizationQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-strategy-optimization",
      effectiveAsOf ?? "__none",
      currentMarketState ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreStrategyOptimization({
        snapshotTo: effectiveAsOf ?? undefined,
        currentMarketState: currentMarketState ?? undefined,
        minSample: 20,
        primaryHorizon: "return_5d",
      }),
    enabled: Boolean(effectiveAsOf && strategyOptimizationSection.seen),
    ...stockAnalysisReadQueryOptions,
  });
  const strategyOptimizationPayload = strategyOptimizationQuery.data?.result ?? null;
  const strategyOptimizationRows = useMemo(
    () => buildStrategyOptimizationRows(strategyOptimizationPayload),
    [strategyOptimizationPayload],
  );
  const strategyOptimizationSlices = useMemo(
    () => strategyOptimizationSlicePair(strategyOptimizationPayload),
    [strategyOptimizationPayload],
  );
  const strategyPriorityRows = strategyScorePayload?.current_market_state_rows ?? EMPTY_STRATEGY_PRIORITY_ROWS;
  const strategyPriorityHeadline = buildStrategyPriorityHeadline(strategyPriorityRows);
  const strategyPriorityReason = strategyPrioritySummaryReason(strategyPriorityRows);
  const strategyMaturityRow = resolveStrategyMaturityRow(strategyPriorityRows);
  const strategyMaturity = strategyMaturityRow?.diagnostics?.maturity ?? null;
  const strategyMaturitySnapshots = [...(strategyMaturity?.tracked_snapshots ?? [])].slice(-6).reverse();
  const strategyMaturityDetailSnapshotFrom =
    strategyMaturitySnapshots[strategyMaturitySnapshots.length - 1]?.snapshot_as_of_date ?? null;
  const strategyMaturityDetailSnapshotTo = strategyMaturitySnapshots[0]?.snapshot_as_of_date ?? null;
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
    enabled: Boolean(effectiveAsOf && strategyBacktestSection.seen),
    ...stockAnalysisReadQueryOptions,
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
  const cycleProxyBacktestQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-cycle-proxy-backtest",
      effectiveAsOf ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreCycleProxyBacktest({
        snapshotTo: effectiveAsOf ?? undefined,
      }),
    enabled: Boolean(effectiveAsOf && cycleRotationFramework && cycleFrameworkSection.seen),
    ...stockAnalysisReadQueryOptions,
  });
  const cycleProxyBacktestPayload: LivermoreCycleProxyBacktestPayload | null =
    cycleProxyBacktestQuery.data?.result ?? null;
  const candidateHistoryPortfolioBacktestQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-candidate-history-portfolio-backtest",
      effectiveAsOf ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreCandidateHistoryPortfolioBacktest({
        snapshotTo: effectiveAsOf ?? undefined,
      }),
    enabled: Boolean(effectiveAsOf && cycleRotationFramework && cycleFrameworkSection.seen),
    ...stockAnalysisReadQueryOptions,
  });
  const candidateHistoryPortfolioBacktestPayload: LivermoreCandidateHistoryPortfolioBacktestPayload | null =
    candidateHistoryPortfolioBacktestQuery.data?.result ?? null;
  const strategyMaturityDetailQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-candidate-history-maturity-detail",
      strategyMaturityRow?.signal_kind ?? "__none",
      strategyMaturityDetailSnapshotFrom ?? "__none",
      strategyMaturityDetailSnapshotTo ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreCandidateHistory({
        snapshotFrom: strategyMaturityDetailSnapshotFrom ?? undefined,
        snapshotTo: strategyMaturityDetailSnapshotTo ?? undefined,
        limit: 500,
      }),
    enabled: Boolean(
      strategyPrioritySection.seen &&
        strategyMaturityRow &&
        strategyMaturityDetailSnapshotFrom &&
        strategyMaturityDetailSnapshotTo,
    ),
    ...stockAnalysisReadQueryOptions,
  });
  const strategyMaturityCandidateRows = useMemo(
    () =>
      buildStrategyMaturityCandidates(
        strategyMaturityDetailQuery.data?.result ?? null,
        strategyMaturityRow,
        strategyMaturitySnapshots,
      ),
    [strategyMaturityDetailQuery.data, strategyMaturityRow, strategyMaturitySnapshots],
  );

  const strategyBacktestDateRangeLabel =
    strategyBacktestSnapshotFrom && effectiveAsOf
      ? `${strategyBacktestSnapshotFrom} 至 ${effectiveAsOf}`
      : "日期待补";

  const cycleRotationPanelSummary = useMemo(
    () =>
      cycleRotationFramework
        ? buildCycleRotationPanelSummary({
            framework: cycleRotationFramework,
            macroLayer: cycleMacroLayerSummary,
            portfolioBacktest: candidateHistoryPortfolioBacktestPayload,
            proxyBacktest: cycleProxyBacktestPayload,
            portfolioQueryState: resolvePanelQueryState({
              enabled: Boolean(effectiveAsOf && cycleRotationFramework && cycleFrameworkSection.seen),
              isLoading: candidateHistoryPortfolioBacktestQuery.isLoading,
              isError: candidateHistoryPortfolioBacktestQuery.isError,
            }),
            proxyQueryState: resolvePanelQueryState({
              enabled: Boolean(effectiveAsOf && cycleRotationFramework && cycleFrameworkSection.seen),
              isLoading: cycleProxyBacktestQuery.isLoading,
              isError: cycleProxyBacktestQuery.isError,
            }),
          })
        : null,
    [
      cycleRotationFramework,
      cycleMacroLayerSummary,
      candidateHistoryPortfolioBacktestPayload,
      cycleProxyBacktestPayload,
      effectiveAsOf,
      cycleFrameworkSection.seen,
      candidateHistoryPortfolioBacktestQuery.isLoading,
      candidateHistoryPortfolioBacktestQuery.isError,
      cycleProxyBacktestQuery.isLoading,
      cycleProxyBacktestQuery.isError,
    ],
  );

  const themeBreakoutPanelSummary = useMemo(
    () =>
      strategyPayload
        ? buildThemeBreakoutPanelSummary({
            payload: strategyPayload,
            cards: themeBreakoutCards,
            reviewCount: themeBreakoutReviewItems.length,
            unsupportedReason: themeBreakoutUnsupported?.reason,
          })
        : null,
    [strategyPayload, themeBreakoutCards, themeBreakoutReviewItems.length, themeBreakoutUnsupported?.reason],
  );

  const consensusReviewPanelSummary = useMemo(
    () => buildConsensusReviewPanelSummary(consensusSummary),
    [consensusSummary],
  );

  const marketPriorityPanelSummary = useMemo(
    () =>
      buildMarketPriorityPanelSummary({
        rows: strategyPriorityRows,
        payload: strategyScorePayload,
        marketState: currentMarketState,
        queryState: resolvePanelQueryState({
          enabled: Boolean(effectiveAsOf && strategyPrioritySection.seen),
          isLoading: strategyScoreQuery.isLoading,
          isError: strategyScoreQuery.isError,
        }),
        errorMessage: strategyScoreQuery.isError ? errorMessage(strategyScoreQuery.error) : undefined,
      }),
    [
      strategyPriorityRows,
      strategyScorePayload,
      currentMarketState,
      effectiveAsOf,
      strategyPrioritySection.seen,
      strategyScoreQuery.isLoading,
      strategyScoreQuery.isError,
      strategyScoreQuery.error,
    ],
  );

  const strategyBacktestPanelSummary = useMemo(
    () =>
      buildStrategyBacktestPanelSummary({
        payload: strategyBacktestPayload,
        sampleCount: strategyBacktestSampleCount,
        window: strategyBacktestWindow,
        dateRangeLabel: strategyBacktestDateRangeLabel,
        rows: strategyBacktestRows,
        queryState: resolvePanelQueryState({
          enabled: Boolean(effectiveAsOf && strategyBacktestSection.seen),
          isLoading: strategyBacktestQuery.isLoading,
          isError: strategyBacktestQuery.isError,
        }),
        errorMessage: strategyBacktestQuery.isError ? errorMessage(strategyBacktestQuery.error) : undefined,
      }),
    [
      strategyBacktestPayload,
      strategyBacktestSampleCount,
      strategyBacktestWindow,
      strategyBacktestDateRangeLabel,
      strategyBacktestRows,
      effectiveAsOf,
      strategyBacktestSection.seen,
      strategyBacktestQuery.isLoading,
      strategyBacktestQuery.isError,
      strategyBacktestQuery.error,
    ],
  );

  const strategyOptimizationPanelSummary = useMemo(
    () =>
      buildStrategyOptimizationPanelSummary({
        payload: strategyOptimizationPayload,
        rows: strategyOptimizationRows,
        queryState: resolvePanelQueryState({
          enabled: Boolean(effectiveAsOf && strategyOptimizationSection.seen),
          isLoading: strategyOptimizationQuery.isLoading,
          isError: strategyOptimizationQuery.isError,
        }),
        errorMessage: strategyOptimizationQuery.isError
          ? errorMessage(strategyOptimizationQuery.error)
          : undefined,
      }),
    [
      strategyOptimizationPayload,
      strategyOptimizationRows,
      effectiveAsOf,
      strategyOptimizationSection.seen,
      strategyOptimizationQuery.isLoading,
      strategyOptimizationQuery.isError,
      strategyOptimizationQuery.error,
    ],
  );

  const observationPoolsPanelSummary = useMemo(
    () =>
      buildObservationPoolsPanelSummary({
        gateState,
        meanReversionCount: meanReversionPayload?.candidate_count ?? 0,
        factorScreenCount: factorScreenPayload?.candidate_count ?? 0,
        hybridFusionCount: hybridFusionPayload?.candidate_count ?? 0,
        meanReversionActive: meanReversionMarketActive,
      }),
    [
      gateState,
      meanReversionPayload?.candidate_count,
      factorScreenPayload?.candidate_count,
      hybridFusionPayload?.candidate_count,
      meanReversionMarketActive,
    ],
  );

  const eventsMonitoringPanelSummary = useMemo(
    () => buildEventsMonitoringPanelSummary(eventMonitorRows),
    [eventMonitorRows],
  );

  const deepAnalysisGateSummary = useMemo(() => {
    const topPriority =
      strategyPriorityRows.find(
        (row) => row.priority_label === "优先复核" && row.sample_status === "sufficient",
      ) ?? strategyPriorityRows.find((row) => row.sample_status === "sufficient");
    return buildDeepAnalysisGateSummary({
      gateState,
      themeUnsupportedReason: themeBreakoutUnsupported?.reason,
      priorityStrategyLabel: topPriority?.strategy_label ?? null,
    });
  }, [gateState, themeBreakoutUnsupported?.reason, strategyPriorityRows]);

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
    ...stockAnalysisReadQueryOptions,
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
      <main className="stock-analysis-page" data-layout-rev="2026-05-16b" data-data-viz-rev="2026-05-16c">
        <header
          className="stock-analysis-page__header stock-analysis-page__dh-topbar"
          data-testid="stock-analysis-toolbar"
        >
          <div className="stock-analysis-page__header-main stock-analysis-page__dh-topbar-main">
            <div className="stock-analysis-page__header-title-row">
              <h1>股票分析</h1>
              <span className="stock-analysis-page__badge">只读复核</span>
            </div>
            <div className="stock-analysis-page__header-controls stock-analysis-page__dh-topbar-controls">
              <Button
                type="default"
                className="stock-analysis-page__agent-entry stock-analysis-page__dh-topbar-btn"
                data-testid="stock-analysis-agent-open"
                icon={<SafetyCertificateOutlined />}
                onClick={() => setAgentDrawerOpen(true)}
                aria-expanded={agentDrawerOpen}
              >
                Agent
              </Button>
              <DatePicker
                allowClear
                aria-label="as-of-date-picker"
                className="stock-analysis-page__dh-date-picker"
                data-testid="stock-analysis-as-of-picker"
                value={pickerDisplay}
                onChange={(_, iso) => {
                  setAsOfOverride(Array.isArray(iso) ? (iso[0] ?? null) : iso || null);
                }}
              />
              <Button
                data-testid="stock-analysis-refresh"
                className="stock-analysis-page__dh-topbar-btn"
                icon={<ReloadOutlined />}
                onClick={invalidateStockAnalysis}
              >
                刷新
              </Button>
              {strategyQuery.data?.result_meta?.generated_at ? (
                <Text
                  type="secondary"
                  className="stock-analysis-page__tabular stock-analysis-page__generated-at"
                  title={strategyQuery.data.result_meta.generated_at}
                >
                  <ClockCircleOutlined /> {formatGeneratedAtLabel(strategyQuery.data.result_meta.generated_at)}
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
            {decisionSummary && dailyJudgmentStrip ? (
              <div className="stock-analysis-page__first-screen">
                {showStaleBanner ? (
                  <div
                    className="stock-analysis-page__stale-banner rounded-lg border border-warning-200 bg-warning-50 px-4 py-2 text-sm text-warning-800"
                    data-testid="stock-analysis-stale-banner"
                    role="status"
                  >
                    数据陈旧、通道异常或使用回退快照（quality_flag / vendor_status / fallback_mode）。下方结论仅供复核参考。
                  </div>
                ) : null}

                <section
                  data-testid="stock-analysis-tailwind-cockpit"
                  className={SA_FIRST_HERO}
                  aria-label="策略复核决策"
                >
                  {pagePurpose ? (
                    <div
                      className="stock-analysis-page__dh-purpose"
                      data-testid="stock-analysis-page-purpose"
                    >
                      <p className="stock-analysis-page__dh-purpose-eyebrow">{pagePurpose.eyebrow}</p>
                      <h2 className="stock-analysis-page__dh-purpose-title">{pagePurpose.title}</h2>
                      <p className="stock-analysis-page__dh-purpose-copy">{pagePurpose.subtitle}</p>
                      <p className="stock-analysis-page__dh-purpose-foot">
                        {pagePurpose.asOfLine} · {pagePurpose.dataStatusLine}
                      </p>
                    </div>
                  ) : null}

                  <div className="flex flex-col gap-3" data-testid="stock-analysis-decision-panel">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="flex min-w-0 flex-1 flex-col gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="stock-analysis-page__dh-chip">只读复核</span>
                          <span className="stock-analysis-page__dh-hero-meta">
                            观察日{" "}
                            <strong className="stock-analysis-page__tabular text-[color:var(--sa-dh-ink)]">
                              {decisionSummary.asOfLabel}
                            </strong>
                          </span>
                          {backendSupplyOverview ? (
                            <span className="stock-analysis-page__dh-hero-meta">
                              后端供数 {backendSupplyOverview.asOfLabel}
                            </span>
                          ) : null}
                        </div>
                        <h1 className="stock-analysis-page__dh-hero-title">
                          {backendSupplyOverview?.gateLabel ?? `门控 ${strategyPayload?.market_gate.state}`}
                          {" · "}
                          {decisionSummary.exposureLabel}
                        </h1>
                        <p className="stock-analysis-page__dh-hero-copy">{decisionSummary.headline}</p>
                        <p className="stock-analysis-page__dh-hero-copy font-semibold text-[color:var(--sa-dh-ink)]">
                          {decisionSummary.nextReviewAction}
                        </p>
                        <p className="stock-analysis-page__dh-hero-meta">
                          {decisionSummary.dataFreshnessLabel} · {decisionSummary.boundaryLabel}
                        </p>
                      </div>
                    </div>

                    <p className="stock-analysis-page__dh-hero-meta" aria-label="市场门控状态">
                      {[
                        dailyJudgmentStrip.gateChip,
                        dailyJudgmentStrip.exposureChip,
                        dailyJudgmentStrip.strongestSectorChip,
                        dailyJudgmentStrip.weakestSectorChip,
                      ].join(" · ")}
                    </p>

                    <div className="stock-analysis-page__visually-hidden" aria-hidden="true">
                      {backendSupplyOverview
                        ? [
                            backendSupplyOverview.gateLabel,
                            backendSupplyOverview.exposureLabel,
                            backendSupplyOverview.readinessLabel,
                            backendSupplyOverview.dataGapLabel,
                            backendSupplyOverview.supportedLabel,
                            backendSupplyOverview.unsupportedLabel,
                            backendSupplyOverview.qualityLabel,
                          ].join(" ")
                        : null}
                    </div>

                    <details className="stock-analysis-page__dh-details border-t border-[color:var(--sa-dh-line-soft)] pt-3">
                      <summary>
                        <span className="flex items-center gap-2">
                          <span className="text-[color:var(--sa-dh-blue)] group-open:rotate-90">▸</span>
                          供数明细与闭环
                        </span>
                        {closedLoopSummary ? (
                          <strong className="stock-analysis-page__dh-pill">
                            {closedLoopSummary.referenceRating.label}
                          </strong>
                        ) : null}
                      </summary>
                      <div className="mt-3 space-y-3 px-1">
                      {backendSupplyOverview ? (
                        <DataStatusStrip
                          testId="stock-analysis-backend-supply-status"
                          className="grid content-start gap-1.5 border-l border-neutral-200 bg-neutral-50 p-3"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <h3 className="m-0 text-sm font-semibold text-neutral-900">规则就绪</h3>
                            <span className="whitespace-nowrap rounded border border-primary-200 bg-primary-50 px-2 py-0.5 text-[11px] font-bold text-primary-700">
                              只读
                            </span>
                          </div>
                          <div className="grid gap-0.5">
                            {backendSupplyOverview.readinessRows.map((item) => (
                              <div
                                className="flex min-h-[23px] items-center justify-between gap-2 border-b border-neutral-200/80 py-0.5"
                                data-tone={readinessTone(item.status)}
                                key={item.key}
                              >
                                <span className="flex min-w-0 items-center gap-1.5 overflow-hidden whitespace-nowrap text-[10px] font-bold text-neutral-500">
                                  <StatusIcon tone={readinessTone(item.status)}>
                                    <SafetyCertificateOutlined />
                                  </StatusIcon>
                                  {item.title}
                                </span>
                                <strong className="text-right text-[11px] leading-tight text-neutral-900">
                                  {item.status}
                                </strong>
                              </div>
                            ))}
                            {backendSupplyOverview.dataGapRows.slice(0, 3).map((item) => (
                              <div
                                className="flex min-h-[23px] items-center justify-between gap-2 border-b border-neutral-200/80 py-0.5"
                                data-tone={gapTone(item.status)}
                                key={`gap:${item.input_family}`}
                              >
                                <span className="flex min-w-0 items-center gap-1.5 overflow-hidden whitespace-nowrap text-[10px] font-bold text-neutral-500">
                                  <StatusIcon tone={gapTone(item.status)}>
                                    <DatabaseOutlined />
                                  </StatusIcon>
                                  {item.input_family}
                                </span>
                                <strong className="text-right text-[11px] leading-tight text-neutral-900">
                                  {item.status}
                                </strong>
                              </div>
                            ))}
                          </div>
                        </DataStatusStrip>
                      ) : null}
                      <div
                        className="grid grid-cols-2 gap-0 overflow-hidden rounded-md border border-neutral-200 bg-neutral-50 sm:grid-cols-3 xl:grid-cols-6"
                        aria-label="后端供数摘要"
                      >
                        {[
                          backendSupplyOverview?.gateLabel ?? decisionSummary.gateLabel,
                          backendSupplyOverview?.exposureLabel ?? decisionSummary.exposureLabel,
                          backendSupplyOverview?.readinessLabel ?? "就绪 0/0",
                          backendSupplyOverview?.dataGapLabel ?? "缺口 0",
                          backendSupplyOverview?.supportedLabel ?? "可用 0",
                          backendSupplyOverview?.unsupportedLabel ?? "阻断 0",
                        ].map((label) => {
                          const shortLabel = compactText(label, 20);
                          return (
                            <span
                              key={label}
                              title={label}
                              className="flex min-h-[46px] min-w-0 items-center gap-2 border-b border-r border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-900 last:border-r-0 sm:[&:nth-child(3n)]:border-r-0 xl:border-b-0 xl:[&:nth-child(6n)]:border-r-0"
                            >
                              <strong className="min-w-0 truncate">{shortLabel}</strong>
                              {shortLabel !== label ? (
                                <small className="sr-only">{label}</small>
                              ) : null}
                            </span>
                          );
                        })}
                      </div>
                      <div className="grid grid-cols-2 gap-0 overflow-hidden rounded-md border border-neutral-200 bg-white sm:grid-cols-4">
                        <div
                          className="grid min-h-[50px] grid-cols-[auto_minmax(0,1fr)] items-center gap-x-2 gap-y-0.5 border-b border-r border-neutral-200 px-3 py-2 sm:[&:nth-child(2n)]:border-r-0 sm:[&:nth-child(-n+2)]:border-b sm:[&:nth-child(n+3)]:border-b-0 sm:odd:border-r"
                          title={`数据日期 ${backendSupplyOverview?.asOfLabel ?? decisionSummary.asOfLabel}`}
                        >
                          <StatusIcon>{DECISION_GRID_ICONS[0]}</StatusIcon>
                          <span className="text-xs text-neutral-500">数据日期</span>
                          <strong className="col-start-2 text-sm" style={tabularNumStyle}>
                            {backendSupplyOverview?.asOfLabel ?? decisionSummary.asOfLabel}
                          </strong>
                        </div>
                        <div
                          className="grid min-h-[50px] grid-cols-[auto_minmax(0,1fr)] items-center gap-x-2 gap-y-0.5 border-b border-r border-neutral-200 px-3 py-2 sm:border-r-0 sm:[&:nth-child(-n+2)]:border-b"
                          title={`口径 ${backendSupplyOverview?.basisLabel ?? decisionSummary.basisLabel}`}
                        >
                          <StatusIcon>{DECISION_GRID_ICONS[1]}</StatusIcon>
                          <span className="text-xs text-neutral-500">口径</span>
                          <strong className="col-start-2 break-words text-sm">
                            {backendSupplyOverview?.basisLabel ?? decisionSummary.basisLabel}
                          </strong>
                        </div>
                        <div
                          className="grid min-h-[50px] grid-cols-[auto_minmax(0,1fr)] items-center gap-x-2 gap-y-0.5 border-b border-r border-neutral-200 px-3 py-2 sm:odd:border-r sm:[&:nth-child(n+3)]:border-b-0"
                          title={`请求日期 ${backendSupplyOverview?.requestedAsOfLabel ?? "默认"}`}
                        >
                          <StatusIcon>{DECISION_GRID_ICONS[2]}</StatusIcon>
                          <span className="text-xs text-neutral-500">请求日期</span>
                          <strong className="col-start-2 text-sm">
                            {backendSupplyOverview?.requestedAsOfLabel ?? "默认"}
                          </strong>
                        </div>
                        <div
                          className="grid min-h-[50px] grid-cols-[auto_minmax(0,1fr)] items-center gap-x-2 gap-y-0.5 border-neutral-200 px-3 py-2 sm:border-r-0"
                          title={`门控确认 ${backendSupplyOverview?.conditionLabel ?? marketState.passedLabel}`}
                        >
                          <StatusIcon>{DECISION_GRID_ICONS[3]}</StatusIcon>
                          <span className="text-xs text-neutral-500">门控确认</span>
                          <strong className="col-start-2 break-words text-sm">
                            {backendSupplyOverview?.conditionLabel ?? marketState.passedLabel}
                          </strong>
                        </div>
                      </div>
                      <div className="grid gap-4 md:grid-cols-2">
                        <section>
                          <h3 className="mb-2 text-sm font-semibold text-neutral-900">门控条件</h3>
                          <ul className="grid gap-1.5 p-0">
                            {marketState.conditions.map((condition) => (
                              <li
                                key={condition.key}
                                className="flex items-center justify-between gap-3 rounded-md border border-neutral-100 bg-neutral-50 px-2.5 py-2"
                              >
                                <span>
                                  <strong className="text-sm text-neutral-900">{condition.label}</strong>
                                  <small className="block text-xs text-neutral-500">{condition.evidence}</small>
                                </span>
                                <em className="not-italic rounded-full border border-primary-200 bg-primary-50 px-2 py-0.5 text-xs font-semibold text-primary-700">
                                  {statusLabel(condition.status)}
                                </em>
                              </li>
                            ))}
                          </ul>
                        </section>
                        <section>
                          <h3 className="mb-2 text-sm font-semibold text-neutral-900">需要关注边界</h3>
                          {marketState.warnings.length > 0 ? (
                            <ul className="grid gap-2 p-0">
                              {marketState.warnings.slice(0, 4).map((warning) => (
                                <li
                                  key={warning}
                                  className="border-l-[3px] border-warning-300 py-1 pl-2.5 text-sm leading-relaxed text-neutral-500"
                                >
                                  {warning}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="text-sm text-neutral-500">当前无诊断预警。</p>
                          )}
                        </section>
                      </div>
                      </div>
                    </details>
                  </div>
                </section>

                {kpiStrip.length > 0 ? (
                  <section data-testid="stock-analysis-kpi-section" aria-label="门控与敞口">
                    <p className={SA_SECTION_EYEBROW}>门控与敞口</p>
                    <div
                      className="stock-analysis-page__dh-kpi-strip"
                      data-testid="stock-analysis-kpi-strip"
                    >
                    {kpiStrip.map((item) => (
                      <EquityKpiCard
                        key={item.key}
                        label={item.label}
                        value={item.value}
                        deltaText={item.detail}
                        deltaTone={kpiToneToDelta(item.tone)}
                      />
                    ))}
                    </div>
                  </section>
                ) : null}

                <div className="stock-analysis-page__dh-work-grid" data-testid="stock-analysis-first-screen-workbench">
                  <div className="flex flex-col gap-3" data-testid="stock-analysis-first-screen-primary">
                    <div
                      className="stock-analysis-page__supply-mini-grid"
                      aria-label="后端供数首屏摘要"
                    >
                      <article className="stock-analysis-page__mini-panel">
                        <div className="stock-analysis-page__mini-panel-head">
                          <strong>
                            <StatusIcon>{FIRST_SCREEN_ICONS[0]}</StatusIcon>
                            板块供数
                          </strong>
                          <span>{backendSupplyOverview?.sectorSupplyLabel ?? "板块 0"}</span>
                        </div>
                        <div
                          className="stock-analysis-page__mini-chart"
                          data-testid="stock-analysis-sector-mini-chart"
                          aria-label="板块供数图"
                        >
                          {sectorChartRows.length > 0 ? (
                            <ReactECharts
                              option={sectorMiniChartOption}
                              className="stock-analysis-page__echart"
                              style={miniBarChartStyle}
                              opts={{ renderer: "canvas" }}
                              notMerge
                              lazyUpdate
                            />
                          ) : (
                            <span className="stock-analysis-page__empty stock-analysis-page__empty--signal">-</span>
                          )}
                        </div>
                      </article>
                      <article className="stock-analysis-page__mini-panel">
                        <div className="stock-analysis-page__mini-panel-head">
                          <strong>
                            <StatusIcon>{FIRST_SCREEN_ICONS[1]}</StatusIcon>
                            规则就绪
                          </strong>
                          <span>{backendSupplyOverview?.readinessLabel ?? "就绪 0/0"}</span>
                        </div>
                        <div
                          className="stock-analysis-page__mini-chart"
                          data-testid="stock-analysis-review-mini-chart"
                          aria-label="规则就绪分布图"
                        >
                          {readinessChartRows.length > 0 ? (
                            <ReactECharts
                              option={readinessMiniChartOption}
                              className="stock-analysis-page__echart"
                              style={miniBarChartStyle}
                              opts={{ renderer: "canvas" }}
                              notMerge
                              lazyUpdate
                            />
                          ) : null}
                        </div>
                      </article>
                      <article className="stock-analysis-page__mini-panel">
                        <div className="stock-analysis-page__mini-panel-head">
                          <strong>
                            <StatusIcon>{FIRST_SCREEN_ICONS[2]}</StatusIcon>
                            输出可用
                          </strong>
                          <span>{backendSupplyOverview?.supportedLabel ?? "可用 0"}</span>
                        </div>
                        <div
                          className="stock-analysis-page__mini-chart"
                          data-testid="stock-analysis-event-mini-chart"
                          aria-label="输出可用分布图"
                        >
                          {outputChartRows.some((row) => row.value > 0) ? (
                            <ReactECharts
                              option={outputMiniChartOption}
                              className="stock-analysis-page__echart"
                              style={miniStackChartStyle}
                              opts={{ renderer: "canvas" }}
                              notMerge
                              lazyUpdate
                            />
                          ) : null}
                        </div>
                        {backendSupplyOverview ? (
                          <div className="stock-analysis-page__mini-table" aria-label="输出可用首屏摘要">
                            <div>
                              <span>候选</span>
                              <strong>{backendSupplyOverview.candidateSupplyLabel}</strong>
                            </div>
                            <div>
                              <span>阻断</span>
                              <strong>{backendSupplyOverview.unsupportedLabel}</strong>
                              {primaryUnsupportedOutput ? (
                                <small title={primaryUnsupportedOutput.reason}>
                                  {outputKeyLabel(primaryUnsupportedOutput.key)}
                                </small>
                              ) : null}
                            </div>
                          </div>
                        ) : null}
                      </article>
                      <article className="stock-analysis-page__mini-panel">
                        <div className="stock-analysis-page__mini-panel-head">
                          <strong>
                            <StatusIcon>{FIRST_SCREEN_ICONS[3]}</StatusIcon>
                            风险供数
                          </strong>
                          <span>{backendSupplyOverview?.riskSupplyLabel ?? "风险 0"}</span>
                        </div>
                        <div
                          className="stock-analysis-page__mini-chart"
                          data-testid="stock-analysis-risk-mini-chart"
                          aria-label="风险供数分布图"
                        >
                          {riskSupplyChartRows.some((row) => row.value > 0) ? (
                            <ReactECharts
                              option={riskSupplyMiniChartOption}
                              className="stock-analysis-page__echart"
                              style={miniStackChartStyle}
                              opts={{ renderer: "canvas" }}
                              notMerge
                              lazyUpdate
                            />
                          ) : null}
                        </div>
                        {backendSupplyOverview ? (
                          <div className="stock-analysis-page__mini-table" aria-label="风险供数首屏摘要">
                            <div>
                              <span>持仓</span>
                              <strong className="stock-analysis-page__tabular">
                                持仓 {backendSupplyOverview.risk?.position_count ?? 0}
                              </strong>
                            </div>
                            <div>
                              <span>触发</span>
                              <strong className="stock-analysis-page__tabular">
                                触发 {backendSupplyOverview.risk?.signal_count ?? 0}
                              </strong>
                            </div>
                            <div>
                              <span>观察</span>
                              <strong className="stock-analysis-page__tabular">
                                观察 {backendSupplyOverview.risk?.watch_items?.length ?? 0}
                              </strong>
                            </div>
                            {primaryDataGap ? (
                              <div>
                                <span>缺口</span>
                                <strong>{backendSupplyOverview.dataGapLabel}</strong>
                                <small title={primaryDataGap.evidence}>
                                  {dataGapFamilyLabel(primaryDataGap.input_family)}
                                </small>
                              </div>
                            ) : null}
                          </div>
                        ) : null}
                      </article>
                    </div>

              <section
                className={SA_FIRST_CARD}
                data-testid="stock-analysis-sector-strength-panel"
              >
                <div className={SA_SECTION_HEAD}>
                  <div className="min-w-0">
                    <p className={SA_SECTION_EYEBROW}>行业相对强弱</p>
                    <h2 className={SA_CARD_TITLE}>
                      <StatusIcon>{SECTION_HEAD_ICONS[0]}</StatusIcon>
                      板块强弱
                    </h2>
                    <p className={SA_SECTION_DESC}>
                      {sectorRowsFull.length} 个板块 / Top-Bottom 对比 / 点击筛选候选。
                    </p>
                  </div>
                  <span className={SA_PILL}>
                    {sectorRowsFull.length > 0 ? `${sectorRowsFull.length} 个板块` : "板块待补"}
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

                    <div
                      className="mb-2 h-[190px] w-full min-w-0 overflow-hidden rounded-md border border-neutral-200 bg-neutral-50"
                      data-testid="stock-analysis-sector-strength-chart"
                      aria-label="板块强弱横向图"
                    >
                      {sectorStrengthChartRows.length > 0 ? (
                        <ReactECharts
                          option={sectorStrengthChartOption}
                          className="min-w-0"
                          style={sectorStrengthChartStyle}
                          opts={{ renderer: "canvas" }}
                          notMerge
                          lazyUpdate
                        />
                      ) : (
                        <span className="grid min-h-[54px] place-items-center font-mono text-2xl font-bold text-neutral-300">
                          -
                        </span>
                      )}
                    </div>

                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2" data-testid="stock-analysis-sector-bars">
                      <div className="rounded-md border border-neutral-200 bg-neutral-50 p-2.5">
                        <h3 className="mb-2 text-sm font-semibold text-neutral-500">强势 Top 5</h3>
                        <div className="grid gap-1.5">
                          {topBars.map((row) => (
                            <button
                              type="button"
                              key={`top-${row.sectorCode}-${row.rank}`}
                              className={`grid w-full gap-1 rounded-md border border-transparent bg-transparent p-0.5 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-500${
                                sectorFilterSectorCode === row.sectorCode
                                  ? " shadow-[inset_3px_0_0_0_theme(colors.primary.600)] pl-2"
                                  : ""
                              }`}
                              aria-pressed={sectorFilterSectorCode === row.sectorCode}
                              data-testid={`sector-bar-${row.sectorCode}`}
                              onClick={() => toggleSectorFilter(row.sectorCode)}
                            >
                              <div className="flex items-baseline justify-between gap-2 text-xs text-neutral-900" style={tabularNumStyle}>
                                <span className="min-w-0 truncate">
                                  {row.rank}. {row.sectorName}{" "}
                                  <small style={tabularNumStyle}>{row.sectorCode}</small>
                                </span>
                                <span>{row.score}</span>
                              </div>
                              <div className="relative h-[18px] overflow-hidden rounded border border-neutral-200 bg-neutral-100">
                                <div
                                  className="absolute inset-y-0 left-0 bg-primary-600/20 transition-[width] duration-150 ease-out"
                                  style={{
                                    width: `${(sectorView === "score" ? row.scoreNormalized : row.metricBarNormalized) * 100}%`,
                                  }}
                                />
                                <div
                                  className="pointer-events-none absolute inset-0 flex items-center gap-1.5 px-2 text-[11px] font-semibold"
                                  style={tabularNumStyle}
                                >
                                  <span>{row.pctChange}</span>
                                  <small className="text-neutral-500">成分 {row.constituentCount}</small>
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="rounded-md border border-danger-100 bg-danger-50/30 p-2.5">
                        <h3 className="mb-2 text-sm font-semibold text-neutral-500">弱势 Bottom 5</h3>
                        <div className="grid gap-1.5">
                          {bottomBars.map((row) => (
                            <button
                              type="button"
                              key={`bottom-${row.sectorCode}-${row.rank}`}
                              className={`grid w-full gap-1 rounded-md border border-transparent bg-transparent p-0.5 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-500${
                                sectorFilterSectorCode === row.sectorCode
                                  ? " shadow-[inset_3px_0_0_0_theme(colors.primary.600)] pl-2"
                                  : ""
                              }`}
                              aria-pressed={sectorFilterSectorCode === row.sectorCode}
                              data-testid={`sector-bar-bottom-${row.sectorCode}`}
                              onClick={() => toggleSectorFilter(row.sectorCode)}
                            >
                              <div className="flex items-baseline justify-between gap-2 text-xs text-neutral-900" style={tabularNumStyle}>
                                <span className="min-w-0 truncate">
                                  {row.rank}. {row.sectorName}{" "}
                                  <small style={tabularNumStyle}>{row.sectorCode}</small>
                                </span>
                                <span>{row.pctChange}</span>
                              </div>
                              <div className="relative h-[18px] overflow-hidden rounded border border-neutral-200 bg-neutral-100">
                                <div
                                  className="absolute inset-y-0 left-0 bg-danger-600/15 transition-[width] duration-150 ease-out"
                                  style={{
                                    width: `${(sectorView === "score" ? row.scoreNormalized : row.metricBarNormalized) * 100}%`,
                                  }}
                                />
                                <div
                                  className="pointer-events-none absolute inset-0 flex items-center gap-1.5 px-2 text-[11px] font-semibold"
                                  style={tabularNumStyle}
                                >
                                  <span>{row.pctChange}</span>
                                  <small className="text-neutral-500">成分 {row.constituentCount}</small>
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                    <p className="mt-2 text-[11px] leading-relaxed text-neutral-500">
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
                  <div
                    className="flex min-h-[120px] items-center justify-center rounded-md border border-dashed border-neutral-200 bg-neutral-50 text-sm text-neutral-500"
                    role="status"
                  >
                    板块数据不足，待补
                  </div>
                )}
              </section>

              <section className={SA_FIRST_CARD} data-testid="stock-analysis-review-queue">
                <div className={SA_SECTION_HEAD}>
                  <div className="min-w-0">
                    <p className={SA_SECTION_EYEBROW}>今日待复核</p>
                    <h2 className={SA_CARD_TITLE}>复核队列</h2>
                    <p className={SA_SECTION_DESC}>
                      {reviewQueueUsesHybridFusion
                        ? "融合策略候选优先进入队列，先看融合分、代理证据、反证和失效条件。"
                        : "按当前只读证据排列候选，先看为什么进入观察，再看反证、待补和失效条件。"}
                    </p>
                  </div>
                  <span className={SA_PILL}>
                    {reviewQueueUsesHybridFusion ? "融合策略 / 复核队列" : "候选 / 复核队列"}
                  </span>
                </div>

                {reviewQueue.length > 0 ? (
                  <div
                    className="mb-2 flex max-h-[68px] flex-wrap gap-1.5 overflow-y-auto pb-0.5"
                    data-testid="stock-sector-filter-chips"
                  >
                    <button
                      type="button"
                      className={filterChipClass(sectorFilterSectorCode === null)}
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
                        className={filterChipClass(sectorFilterSectorCode === code)}
                        onClick={() => toggleSectorFilter(code)}
                        aria-pressed={sectorFilterSectorCode === code}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                ) : null}
                {reviewQueue.length > 0 ? (
                  <div
                    className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md border border-neutral-100 bg-neutral-50 px-3 py-2 text-xs text-neutral-500"
                    data-testid="stock-review-filter-status"
                  >
                    <span>当前复核范围</span>
                    <strong className="text-sm text-neutral-900">{selectedSectorLabel ?? "全部行业"}</strong>
                    <small>
                      显示 {filteredCandidates.length} / {reviewQueue.length} 个候选
                      {reviewQueueUsesHybridFusion ? " · 融合策略候选优先" : ""}
                    </small>
                  </div>
                ) : null}

                {reviewQueue.length > 0 ? (
                  <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                    {filteredCandidates.map((card) => (
                      <article
                        className="grid gap-2.5 rounded-md border border-neutral-200 bg-white p-3.5 transition-shadow hover:border-primary-200 hover:shadow-[0_0_0_1px_theme(colors.primary.200)]"
                        data-testid={`stock-candidate-${card.stockCode}`}
                        key={card.stockCode}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <h3 className="m-0 text-base font-semibold text-neutral-900">{card.headline}</h3>
                            <p className="mt-1 text-xs text-neutral-500">
                              {card.stockCode} / {card.stockName} / {card.sectorName}
                            </p>
                            <div
                              className="mt-1.5 inline-block rounded-full border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-[11px] font-semibold text-neutral-500"
                              title={card.patternNote}
                            >
                              形态：{card.pattern} / 距观察位 {card.distanceToBreakoutPct}
                            </div>
                          </div>
                          <div className="flex shrink-0 flex-col items-end gap-1.5">
                            <strong className="text-lg text-primary-700" style={tabularNumStyle}>
                              #{card.rank}
                            </strong>
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
                            livermoreRank: reviewQueueUsesHybridFusion ? ranks.livermoreRank : card.rank,
                            meanReversionRank: ranks.meanReversionRank,
                            factorScreenRank: ranks.factorScreenRank,
                            hybridFusionRank: reviewQueueUsesHybridFusion ? card.rank : ranks.hybridFusionRank,
                          });
                              }}
                            >
                              复核 K 线
                            </Button>
                            <span className="rounded-full border border-primary-200 bg-primary-50 px-2 py-0.5 text-xs font-semibold text-primary-700">
                              观察
                            </span>
                          </div>
                        </div>
                        <p className="border-l-[3px] border-primary-500 pl-2.5 text-sm font-semibold leading-relaxed text-neutral-900">
                          {card.reviewFocus}
                        </p>
                        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                          <div>
                            <h4 className="mb-2 text-sm font-semibold text-neutral-900">为什么先看</h4>
                            <ul className="m-0 grid list-none gap-1 p-0 text-sm text-neutral-600">
                              {[...card.primaryEvidence, ...card.supportingEvidence].map((item) => (
                                <li key={item.key}>
                                  <strong className="text-neutral-900">{item.label}</strong>：{item.value}
                                </li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <h4 className="mb-2 text-sm font-semibold text-neutral-900">反证与待补</h4>
                            <ul className="m-0 grid list-none gap-1 p-0 text-sm text-neutral-600">
                              {card.boundaryEvidence.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <h4 className="mb-2 text-sm font-semibold text-neutral-900">失效条件</h4>
                            <p className="border-l-[3px] border-primary-500 pl-2.5 text-sm font-semibold text-neutral-900">
                              {card.invalidationFocus}
                            </p>
                            <ul className="m-0 mt-1 grid list-none gap-1 p-0 text-sm text-neutral-600">
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
                  <div
                    className="flex min-h-[120px] flex-col items-center justify-center gap-1 rounded-md border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-600"
                    role="status"
                    data-testid="stock-analysis-review-queue-empty"
                  >
                    <strong className="text-neutral-900">
                      {reviewQueueEmptyState?.headline ?? "今天没有进入复核队列的候选"}
                    </strong>
                    <p className="m-0 max-w-md text-xs leading-relaxed text-neutral-500">
                      {reviewQueueEmptyState?.detail ??
                        "可下翻查看多因子或融合观察池，并核对门控与板块强弱。"}
                    </p>
                  </div>
                )}
                {reviewQueue.length > 0 &&
                sectorFilterSectorCode &&
                filteredCandidates.length === 0 ? (
                  <p className="stock-analysis-page__empty">
                    该行业暂无候选复核项，可切换到其他行业复核。
                  </p>
                ) : null}
              </section>


                  </div>

                  <aside className="flex flex-col gap-3" aria-label="风险与数据可信度" data-testid="stock-analysis-first-screen-rail">
                    <p className={SA_SECTION_EYEBROW}>闭环 / 风险 / 边界</p>
                    {closedLoopSummary ? (
                      <section
                        className={SA_FIRST_CARD}
                        data-testid="stock-analysis-closed-loop-summary"
                        aria-label="闭环摘要"
                      >
                        <div className={SA_SECTION_HEAD}>
                          <h2 className={SA_CARD_TITLE}>闭环摘要</h2>
                          <span
                            className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${tonePillClass(closedLoopSummary.referenceRating.tone)}`}
                          >
                            {closedLoopSummary.referenceRating.label}
                          </span>
                        </div>

                        <div
                          className={`mt-3 rounded-md border px-3 py-2.5 ${closedLoopItemSurfaceClass(closedLoopSummary.verdict.tone)}`}
                          data-testid="stock-analysis-closed-loop-verdict"
                          data-tone={closedLoopSummary.verdict.tone}
                        >
                          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                            <span className={`text-xs font-semibold ${toneTextClass(closedLoopSummary.verdict.tone)}`}>
                              {closedLoopSummary.verdict.label}
                            </span>
                            <span className="text-sm font-medium text-neutral-900">
                              {closedLoopSummary.verdict.headline}
                            </span>
                          </div>
                          <p className="mt-1.5 text-xs leading-relaxed text-neutral-600">
                            {closedLoopSummary.verdict.primaryReason}
                          </p>
                          <details className="mt-2 text-xs text-neutral-600">
                            <summary className="cursor-pointer select-none text-primary-600 hover:text-primary-700">
                              查看依据与下一步
                            </summary>
                            <ul className="mt-2 space-y-1 pl-4" aria-label="闭环结论证据">
                              {closedLoopSummary.verdict.evidence.map((item) => (
                                <li key={item} className="list-disc" title={item}>
                                  {item}
                                </li>
                              ))}
                            </ul>
                            <p className="mt-2 text-neutral-500">{closedLoopSummary.verdict.nextStep}</p>
                          </details>
                          <span className="stock-analysis-page__visually-hidden">{closedLoopSummary.referenceRating.detail}</span>
                        </div>

                        <ul className="mt-3 space-y-1.5" aria-label="闭环检查项">
                          {closedLoopSummary.items.map((item) => (
                            <li
                              key={item.key}
                              className={`rounded-md border px-2.5 py-2 ${closedLoopItemSurfaceClass(item.tone)}`}
                              data-tone={item.tone}
                              data-testid={item.key === "replay" ? "stock-analysis-replay-status" : undefined}
                            >
                              <div className="flex items-center justify-between gap-2 text-xs">
                                <span className="flex min-w-0 items-center gap-1.5 text-neutral-600">
                                  <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${toneDotClass(item.tone)}`} />
                                  <span className="truncate font-medium">{item.label}</span>
                                </span>
                                <strong className={`shrink-0 font-semibold ${toneTextClass(item.tone)}`}>
                                  {item.statusLabel}
                                </strong>
                              </div>
                              {item.detail ? (
                                <p className="mt-1 pl-3 text-[11px] leading-snug text-neutral-500">{item.detail}</p>
                              ) : null}
                              {item.badges?.map((badge) => (
                                <span className="stock-analysis-page__visually-hidden" key={badge}>
                                  {badge}
                                </span>
                              ))}
                            </li>
                          ))}
                        </ul>
                      </section>
                    ) : null}

                    <section className={SA_FIRST_CARD} data-testid="stock-analysis-risk-section">
                      <div className={SA_SECTION_HEAD}>
                        <div className="min-w-0">
                          <h2 className={SA_CARD_TITLE}>风险退出观察</h2>
                          <p className={SA_SECTION_DESC}>{riskRows.length} 项 · 触发与观察分层</p>
                        </div>
                      </div>
                      {confluenceQuery.isError ? (
                        <p className="text-xs text-warning-700">联动观察暂不可用。</p>
                      ) : null}
                      {riskExitUnsupported ? (
                        <div className="mt-2 grid gap-1.5 rounded-md border border-warning-200 bg-warning-50 px-3 py-2 text-xs text-warning-800">
                          <strong>风险退出观察暂不可用。</strong>
                          <p className="m-0">{riskExitUnsupported.reason}</p>
                        </div>
                      ) : null}
                      {riskRows.length > 0 ? (
                        <div className="space-y-2">
                          {riskRows.slice(0, 5).map((row) => (
                            <div
                              className="cursor-pointer rounded-md border border-neutral-100 bg-neutral-50 p-2 text-xs transition-colors hover:border-primary-200 hover:shadow-[0_0_0_1px_theme(colors.primary.200)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-500"
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
                                  hybridFusionRank: ranks.hybridFusionRank,
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
                                    hybridFusionRank: ranks.hybridFusionRank,
                                  });
                                }
                              }}
                            >
                              <div className="flex items-center justify-between gap-2">
                                <strong className="text-neutral-900">{row.stockName}</strong>
                                <span className={toneTextClass(row.status === "triggered" ? "negative" : "warning")}>
                                  {riskStatusLabel(row.status)}
                                </span>
                              </div>
                              <small className="text-neutral-500">{row.stockCode}</small>
                              <p className="mt-1 text-neutral-600">{row.reason}</p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-neutral-500">
                          {riskExitUnsupported ? "等待持仓快照接入后生成风险退出观察项。" : "当前无风险退出观察项。"}
                        </p>
                      )}
                    </section>

                    <section className={SA_FIRST_CARD} data-testid="stock-analysis-boundary-rail">
                      <div className={SA_SECTION_HEAD}>
                        <h2 className={SA_CARD_TITLE}>数据口径与边界</h2>
                      </div>
                      <div className="stock-analysis-page__boundary-compact-grid">
                        {boundaryRailItems.map((item) => (
                          <div key={item.key} data-tone={item.tone}>
                            <span aria-hidden="true">
                              {item.key === "as-of-date" ? (
                                <ClockCircleOutlined />
                              ) : item.key === "rule-version" ? (
                                <SafetyCertificateOutlined />
                              ) : item.key === "quality" ? (
                                <CheckCircleOutlined />
                              ) : (
                                <DatabaseOutlined />
                              )}
                            </span>
                            <div>
                              <small>{item.label}</small>
                              <strong style={tabularNumStyle}>{item.statusLabel}</strong>
                            </div>
                          </div>
                        ))}
                      </div>
                      {boundarySummary ? (
                        <p
                          className="stock-analysis-page__boundary-summary"
                          data-testid="stock-analysis-boundary-summary"
                        >
                          <strong>{boundarySummary.summaryLabel}</strong>
                          <span>{boundarySummary.detailLabel}</span>
                        </p>
                      ) : null}
                      <Button
                        type="link"
                        className="mt-1 px-0"
                        aria-expanded={boundaryDrawerOpen}
                        onClick={() => setBoundaryDrawerOpen(true)}
                      >
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
                </div>
              </div>
            ) : null}

            <AnalysisGrid columns={2} className="stock-analysis-page__workspace">
              <div className="stock-analysis-page__deep-zone" data-testid="stock-analysis-deep-zone">
                <div className="stock-analysis-page__deep-zone-head">
                  <h2 className="m-0 text-base font-extrabold text-[color:var(--sa-dh-blue-deep)]">供数闭环</h2>
                  <p
                    className="stock-analysis-page__deep-zone-gate-summary"
                    data-testid="stock-analysis-deep-zone-gate-summary"
                    data-tone={deepAnalysisGateSummary.tone}
                  >
                    {deepAnalysisGateSummary.line}
                  </p>
                  <p className="m-0 text-xs text-neutral-500">后端字段 / 历史复核 / 风险边界</p>
                </div>
              <div className="stock-analysis-strategy-card-grid">
              {cycleRotationFramework ? (
                <StrategyModuleCard
                  id="cycle-rotation"
                  title={cycleRotationFramework.display_name}
                  subtitle="周期轮动 · 只读观察"
                  badgeLabel={
                    cycleRotationPanelSummary?.badgeLabel ??
                    localizeImplementationStage(cycleRotationFramework.implementation_stage)
                  }
                  summary={cycleRotationPanelSummary}
                  summaryTestId="stock-analysis-cycle-panel-summary"
                  expanded={isStrategyCardExpanded("cycle-rotation")}
                  onToggleExpand={() => toggleStrategyCard("cycle-rotation")}
                  mountDetail
                  sectionRef={cycleFrameworkSection.ref}
                  sectionTestId="stock-analysis-cycle-rotation-framework"
                  className="stock-analysis-page__cycle-framework"
                >
                  <StrategyPanelComplianceDetails
                    complianceDetail={cycleRotationPanelSummary?.complianceDetail}
                    testId="stock-analysis-cycle-panel-compliance"
                  />
                  <div className="stock-analysis-page__cycle-formulas">
                    <strong>{cycleRotationFramework.score_formula}</strong>
                    {cycleRotationFramework.macro_formula ? (
                      <span>{cycleRotationFramework.macro_formula}</span>
                    ) : null}
                    {cycleRotationFramework.lifecourt_formula ? (
                      <span>{cycleRotationFramework.lifecourt_formula}</span>
                    ) : null}
                    {cycleRotationFramework.fusion_formula ? (
                      <span>{cycleRotationFramework.fusion_formula}</span>
                    ) : null}
                    <small>{cycleRotationFramework.rebalance_cadence}</small>
                  </div>
                  {cycleMacroLayerSummary ? (
                    <div
                      className="stock-analysis-page__cycle-macro-layer"
                      data-testid="stock-analysis-cycle-macro-layer"
                    >
                      <div className={SA_SECTION_HEAD}>
                        <strong>宏观层 MacroScore</strong>
                        <span className={SA_PILL}>
                          {cycleMacroLayerSummary.statusLabel}
                        </span>
                      </div>
                      <p>
                        MacroScore {cycleMacroLayerSummary.macroScoreLabel} · 融合公式{" "}
                        {cycleMacroLayerSummary.formulaVersionLabel}
                      </p>
                      <p>{cycleMacroLayerSummary.evidence}</p>
                      <small>{cycleMacroLayerSummary.detailLabel}</small>
                      {cycleMacroLayerSummary.macroGapLabels.length > 0 ? (
                        <div className="stock-analysis-page__cycle-constraints">
                          {cycleMacroLayerSummary.macroGapLabels.map((gap) => (
                            <span key={gap}>{gap}</span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  {cycleRotationFramework.lifecourt_overlay ? (
                    <div className="stock-analysis-page__cycle-lifecourt-overlay">
                      <strong>{cycleRotationFramework.lifecourt_overlay.display_name}</strong>
                      <p>{cycleRotationFramework.lifecourt_overlay.boundary}</p>
                      <small>
                        Available: {cycleRotationFramework.lifecourt_overlay.available_inputs.join(", ") || "-"} /
                        Missing: {cycleRotationFramework.lifecourt_overlay.missing_inputs.join(", ") || "-"}
                      </small>
                      <div className="stock-analysis-page__cycle-constraints">
                        {cycleRotationFramework.lifecourt_overlay.life_long_gates.map((gate) => (
                          <span key={gate}>{gate}</span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  <div className="stock-analysis-page__cycle-layer-grid">
                    {cycleRotationFramework.layers.map((layer) => (
                      <article className="stock-analysis-page__cycle-layer" key={layer.key}>
                        <div>
                          <span>{layer.title}</span>
                          <strong>{layer.weight == null ? "guardrail" : `${Math.round(layer.weight * 100)}%`}</strong>
                        </div>
                        <em>{layer.status}</em>
                        <p>{layer.evidence}</p>
                        <small>
                          Available: {layer.available_inputs.join(", ") || "-"} / Missing:{" "}
                          {layer.missing_inputs.join(", ") || "-"}
                        </small>
                      </article>
                    ))}
                  </div>
                  <div className="stock-analysis-page__cycle-constraints">
                    {cycleRotationFramework.constraints.map((constraint) => (
                      <span key={constraint}>{constraint}</span>
                    ))}
                  </div>
                  <div
                    className="stock-analysis-page__cycle-proxy-backtest"
                    data-testid="stock-analysis-candidate-history-portfolio-backtest"
                  >
                    {candidateHistoryPortfolioBacktestQuery.isLoading ? (
                      <p className="stock-analysis-page__empty">组合回测加载中。</p>
                    ) : null}
                    {candidateHistoryPortfolioBacktestQuery.isError ? (
                      <p className="stock-analysis-page__notice">
                        组合回测暂不可用：{errorMessage(candidateHistoryPortfolioBacktestQuery.error)}
                      </p>
                    ) : null}
                    {!candidateHistoryPortfolioBacktestQuery.isLoading &&
                    !candidateHistoryPortfolioBacktestQuery.isError ? (
                      candidateHistoryPortfolioBacktestPayload?.status === "portfolio_proxy" &&
                      candidateHistoryPortfolioBacktestPayload.summary ? (
                        <>
                          <p className="stock-analysis-page__footnote">
                            当前更接近执行层的是候选历史组合回测；完整策略仍缺少{" "}
                            {candidateHistoryPortfolioBacktestPayload.missing_full_strategy_inputs.join("、")}。
                          </p>
                          <div className="stock-analysis-page__cycle-proxy-grid">
                            <div>
                              <span>组合回测收益</span>
                              <strong>
                                {formatBacktestSignedPercent(
                                  candidateHistoryPortfolioBacktestPayload.summary.cumulative_return,
                                )}
                              </strong>
                            </div>
                            <div>
                              <span>最大上涨区间</span>
                              <strong>
                                {formatBacktestSignedPercent(
                                  candidateHistoryPortfolioBacktestPayload.summary.max_gain.return,
                                )}
                              </strong>
                              <small>
                                {candidateHistoryPortfolioBacktestPayload.summary.max_gain.start_date} 至{" "}
                                {candidateHistoryPortfolioBacktestPayload.summary.max_gain.end_date}
                              </small>
                            </div>
                            <div>
                              <span>最大回撤区间</span>
                              <strong>
                                {formatBacktestSignedPercent(
                                  candidateHistoryPortfolioBacktestPayload.summary.max_drawdown.return,
                                )}
                              </strong>
                              <small>
                                {candidateHistoryPortfolioBacktestPayload.summary.max_drawdown.peak_date} 至{" "}
                                {candidateHistoryPortfolioBacktestPayload.summary.max_drawdown.trough_date}
                              </small>
                            </div>
                          </div>
                        </>
                      ) : (
                        <p className="stock-analysis-page__footnote">
                          候选历史组合回测暂无可用样本，完整策略仍处于待验证状态。
                        </p>
                      )
                    ) : null}
                  </div>
                  <div
                    className="stock-analysis-page__cycle-proxy-backtest"
                    data-testid="stock-analysis-cycle-proxy-backtest"
                  >
                    {cycleProxyBacktestQuery.isLoading ? (
                      <p className="stock-analysis-page__empty">代理回测加载中。</p>
                    ) : null}
                    {cycleProxyBacktestQuery.isError ? (
                      <p className="stock-analysis-page__notice">
                        代理回测暂不可用：{errorMessage(cycleProxyBacktestQuery.error)}
                      </p>
                    ) : null}
                    {!cycleProxyBacktestQuery.isLoading && !cycleProxyBacktestQuery.isError ? (
                      cycleProxyBacktestPayload?.status === "proxy" && cycleProxyBacktestPayload.summary ? (
                        <>
                          <p className="stock-analysis-page__footnote">
                            当前仅能输出代理回测；完整策略仍缺少{" "}
                            {cycleProxyBacktestPayload.missing_full_strategy_inputs.join("、")}。
                          </p>
                          <div className="stock-analysis-page__cycle-proxy-grid">
                            <div>
                              <span>累计收益</span>
                              <strong>{formatBacktestSignedPercent(cycleProxyBacktestPayload.summary.cumulative_return)}</strong>
                            </div>
                            <div>
                              <span>最大上涨区间</span>
                              <strong>
                                {formatBacktestSignedPercent(cycleProxyBacktestPayload.summary.max_gain.return)}
                              </strong>
                              <small>
                                {cycleProxyBacktestPayload.summary.max_gain.start_date} 至{" "}
                                {cycleProxyBacktestPayload.summary.max_gain.end_date}
                              </small>
                            </div>
                            <div>
                              <span>最大回撤区间</span>
                              <strong>
                                {formatBacktestSignedPercent(cycleProxyBacktestPayload.summary.max_drawdown.return)}
                              </strong>
                              <small>
                                {cycleProxyBacktestPayload.summary.max_drawdown.peak_date} 至{" "}
                                {cycleProxyBacktestPayload.summary.max_drawdown.trough_date}
                              </small>
                            </div>
                          </div>
                        </>
                      ) : (
                        <p className="stock-analysis-page__footnote">
                          代理回测暂无可用样本，完整策略仍处于待验证状态。
                        </p>
                      )
                    ) : null}
                  </div>
                </StrategyModuleCard>
              ) : null}


              <StrategyModuleCard
                id="theme-breakout"
                title="题材突变观察"
                subtitle="代理/概念簇 · 不生成执行结论"
                badgeLabel={
                  themeBreakoutPanelSummary?.badgeLabel ??
                  `${localizeThemeRadarBadge(
                    strategyPayload?.theme_breakout?.is_proxy ?? true,
                    strategyPayload?.theme_breakout?.formula_version,
                  )}${themeBreakoutCards.length > 0 ? ` · ${themeBreakoutCards.length} 项` : ""}`
                }
                summary={themeBreakoutPanelSummary}
                summaryTestId="stock-analysis-theme-panel-summary"
                expanded={isStrategyCardExpanded("theme-breakout")}
                onToggleExpand={() => toggleStrategyCard("theme-breakout")}
                mountDetail
                sectionTestId="stock-analysis-theme-breakout"
              >
                <StrategyPanelComplianceDetails
                            complianceDetail={themeBreakoutPanelSummary?.complianceDetail}
                            testId="stock-analysis-theme-panel-compliance"
                          />
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
                      ? themeBreakoutPanelSummary?.detail ?? "当前无题材突变观察项。"
                      : "当前无题材突变观察项。"}
                  </p>
                          )}
                {themeEvidenceRows.length > 0 ? (
                  <div data-testid="stock-analysis-theme-evidence-state">
                    <div className={SA_SECTION_HEAD}>
                      <strong>题材证据就绪</strong>
                      <span className={SA_PILL}>{themeEvidenceRows.length} 项证据</span>
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
                  </div>
                ) : null}
                {themeBreakoutReviewItems.length > 0 ? (
                  <div data-testid="stock-analysis-theme-review-items">
                    <div className={SA_SECTION_HEAD}>
                      <strong>题材未入选复核</strong>
                      <span className={SA_PILL}>待排查 {themeBreakoutReviewItems.length} 项</span>
                    </div>
                    <div className="stock-analysis-page__candidate-grid">
                      {themeBreakoutReviewItems.map((item) => (
                        <article className="stock-analysis-page__candidate" key={item.themeKey}>
                          <div className="stock-analysis-page__candidate-head">
                            <div>
                              <h3>
                                复核 #{item.rank} {item.themeName}
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
                  </div>
                ) : null}
              </StrategyModuleCard>

              <StrategyModuleCard
                id="consensus-review"
                title="历史复核 / T+5 共振"
                subtitle="趋势 + 多因子同选 · 超跌仅作背景"
                badgeLabel={
                  consensusReviewPanelSummary.badgeLabel ??
                  (consensusReviewPanelSummary.tone === "positive" ? "已就绪" : "待复核")
                }
                summary={consensusReviewPanelSummary}
                summaryTestId="stock-analysis-consensus-panel-summary"
                expanded={isStrategyCardExpanded("consensus-review")}
                onToggleExpand={() => toggleStrategyCard("consensus-review")}
                mountDetail
                sectionTestId="stock-analysis-consensus-review-panel"
              >
                <div
                  className="stock-analysis-page__historical-review-label"
                  data-testid="stock-analysis-historical-review-section"
                >
                  <strong>历史复核摘要</strong>
                  <span>T+5 共振 · 候选历史与评分</span>
                </div>
                <div className="stock-analysis-page__consensus" data-testid="stock-analysis-consensus">
                          <div className="stock-analysis-page__consensus-stats">
                            <span>
                              趋势 <strong>{consensusSummary.strategyCounts.livermore}</strong> 只
                            </span>
                            <span>
                              融合策略 <strong>{consensusSummary.strategyCounts.hybrid_fusion}</strong> 只
                            </span>
                            <span>
                              超跌反弹观察 <strong>{consensusSummary.strategyCounts.mean_reversion}</strong> 只
                            </span>
                            <span>
                              多因子 <strong>{consensusSummary.strategyCounts.factor_screen}</strong> 只
                            </span>
                            <span>
                              合计去重 <strong>{consensusSummary.totalUnion}</strong> 只
                            </span>
                          </div>

                          {!consensusSummary.hasAnyStrategy ? (
                            <p className="stock-analysis-page__empty">
                              {consensusReviewPanelSummary.detail}
                            </p>
                          ) : consensusSummary.items.length === 0 ? (
                            <p className="stock-analysis-page__empty">
                              {consensusReviewPanelSummary.detail}
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
                                    hybridFusionRank: row.hybridFusionRank,
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
                                        {isTriple ? "三策略共振" : "核心共振"}
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
                                      {row.hybridFusionRank != null && (
                                        <span>融合策略 #{row.hybridFusionRank}</span>
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
                            这里仅统计趋势与多因子的 T+5 共振；超跌反弹作为更长周期观察背景展示，不自动抬高复核排序。
                          </p>
                        </div>
              </StrategyModuleCard>

              <StrategyModuleCard
                id="market-priority"
                title="当前市场策略优先级"
                subtitle="近 180 天快照 · T+5 排序 · 只读复核"
                badgeLabel={
                  marketPriorityPanelSummary.badgeLabel ??
                  (strategyScorePayload?.primary_horizon === "return_1d"
                    ? "T+1"
                    : strategyScorePayload?.primary_horizon === "return_20d"
                      ? "T+20"
                      : "T+5")
                }
                summary={marketPriorityPanelSummary}
                summaryTestId="stock-analysis-market-priority-panel-summary"
                expanded={isStrategyCardExpanded("market-priority")}
                onToggleExpand={() => toggleStrategyCard("market-priority")}
                mountDetail
                sectionRef={strategyPrioritySection.ref}
                sectionTestId="stock-analysis-market-priority-summary"
              >
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
                      <span>
                        {localizeMarketDataStatus(
                          strategyScorePayload?.current_market_state ?? currentMarketState,
                        )}
                      </span>
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
                    {strategyMaturityRow && strategyMaturity && strategyMaturitySnapshots.length > 0 ? (
                      <div data-testid="stock-analysis-candidate-maturity">
                        <div className="stock-analysis-page__filter-status">
                          <span>当前候选成熟进度</span>
                          <strong>
                            {strategyMaturityRow.strategy_label}
                            {strategyMaturityRow.diagnostics?.priority_scope_label
                              ? ` / ${strategyMaturityRow.diagnostics.priority_scope_label}`
                              : ""}
                          </strong>
                          <small>
                            {strategyMaturityRemainingText(strategyMaturity)}，{strategyMaturity.reason}
                          </small>
                        </div>
                        <div className="stock-analysis-page__table-wrap">
                          <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                            <thead>
                              <tr>
                                <th scope="col">快照</th>
                                <th className="stock-analysis-page__table-number" scope="col">
                                  候选
                                </th>
                                {strategyBacktestHorizons.map((horizon) => (
                                  <th scope="col" key={horizon}>
                                    {strategyBacktestHorizonShortLabels[horizon]}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {strategyMaturitySnapshots.map((snapshot) => (
                                <tr key={snapshot.snapshot_as_of_date}>
                                  <td>{snapshot.snapshot_as_of_date}</td>
                                  <td className="stock-analysis-page__table-number">{snapshot.candidate_count}</td>
                                  {strategyBacktestHorizons.map((horizon) => (
                                    <td key={horizon}>{strategyMaturityHorizonText(snapshot, horizon)}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        <div className="stock-analysis-page__filter-status">
                          <span>候选明细</span>
                          <strong>{strategyMaturityRow.strategy_label}</strong>
                          <small>仅展开当前成熟进度表内可见快照，按快照日期和候选排名排序。</small>
                        </div>
                        {strategyMaturityDetailQuery.isLoading ? (
                          <p className="stock-analysis-page__empty">候选明细加载中。</p>
                        ) : null}
                        {strategyMaturityDetailQuery.isError ? (
                          <p className="stock-analysis-page__notice">
                            候选明细暂不可用：{errorMessage(strategyMaturityDetailQuery.error)}
                          </p>
                        ) : null}
                        {!strategyMaturityDetailQuery.isLoading && !strategyMaturityDetailQuery.isError ? (
                          strategyMaturityCandidateRows.length > 0 ? (
                            <div className="stock-analysis-page__table-wrap">
                              <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                                <thead>
                                  <tr>
                                    <th scope="col">快照</th>
                                    <th scope="col">排名</th>
                                    <th scope="col">候选</th>
                                    <th scope="col">板块</th>
                                    <th className="stock-analysis-page__table-number" scope="col">
                                      T+1
                                    </th>
                                    <th className="stock-analysis-page__table-number" scope="col">
                                      T+5
                                    </th>
                                    <th className="stock-analysis-page__table-number" scope="col">
                                      T+20
                                    </th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {strategyMaturityCandidateRows.map((candidate) => (
                                    <tr key={`${candidate.snapshot_as_of_date}:${candidate.stock_code}:${candidate.candidate_rank}`}>
                                      <td>{candidate.snapshot_as_of_date}</td>
                                      <td>#{candidate.candidate_rank}</td>
                                      <td>
                                        <span>{candidate.stock_name ?? candidate.stock_code}</span>
                                        <small> {candidate.stock_code}</small>
                                      </td>
                                      <td>{candidate.sector_name ?? "-"}</td>
                                      <td className="stock-analysis-page__table-number">
                                        {strategyCandidateReturnText(candidate.return_1d)}
                                      </td>
                                      <td className="stock-analysis-page__table-number">
                                        {strategyCandidateReturnText(candidate.return_5d)}
                                      </td>
                                      <td className="stock-analysis-page__table-number">
                                        {strategyCandidateReturnText(candidate.return_20d)}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <p className="stock-analysis-page__empty">当前可见快照暂无候选明细。</p>
                          )
                        ) : null}
                      </div>
                    ) : null}
                  </>
                ) : null}
              </StrategyModuleCard>

              <StrategyModuleCard
                id="strategy-backtest"
                title="策略回溯表现"
                subtitle="近 10 日快照 · 已完成日计胜率"
                badgeLabel={strategyBacktestPanelSummary.badgeLabel ?? strategyBacktestDateRangeLabel}
                summary={strategyBacktestPanelSummary}
                summaryTestId="stock-analysis-strategy-backtest-panel-summary"
                expanded={isStrategyCardExpanded("strategy-backtest")}
                onToggleExpand={() => toggleStrategyCard("strategy-backtest")}
                mountDetail
                sectionRef={strategyBacktestSection.ref}
                sectionTestId="stock-analysis-strategy-backtest"
              >
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
              </StrategyModuleCard>

              <StrategyModuleCard
                id="strategy-optimization"
                title="优化诊断"
                subtitle="切片回测 T+5 · 复核排序建议"
                badgeLabel={
                  strategyOptimizationPanelSummary.badgeLabel ??
                  (strategyOptimizationPayload?.primary_horizon === "return_1d"
                    ? "T+1"
                    : strategyOptimizationPayload?.primary_horizon === "return_10d"
                      ? "T+10"
                      : strategyOptimizationPayload?.primary_horizon === "return_20d"
                        ? "T+20"
                        : "T+5")
                }
                summary={strategyOptimizationPanelSummary}
                summaryTestId="stock-analysis-strategy-optimization-panel-summary"
                expanded={isStrategyCardExpanded("strategy-optimization")}
                onToggleExpand={() => toggleStrategyCard("strategy-optimization")}
                mountDetail
                sectionRef={strategyOptimizationSection.ref}
                sectionTestId="stock-analysis-strategy-optimization"
              >
                {strategyOptimizationQuery.isLoading ? (
                  <p className="stock-analysis-page__empty">优化诊断加载中。</p>
                ) : null}
                {strategyOptimizationQuery.isError ? (
                  <p className="stock-analysis-page__notice">
                    优化诊断暂不可用：{errorMessage(strategyOptimizationQuery.error)}
                  </p>
                ) : null}
                {!strategyOptimizationQuery.isLoading && !strategyOptimizationQuery.isError ? (
                  <>
                    <div className="stock-analysis-page__filter-status">
                      <span>当前最新日期收益</span>
                      <strong>
                        {(strategyOptimizationPayload?.pending_summary.pending_rows ?? 0) > 0
                          ? "pending"
                          : "已成熟"}
                      </strong>
                      <small>
                        {strategyOptimizationPayload?.pending_summary.message ?? "T+5 收益成熟状态待补。"}
                      </small>
                    </div>
                    <p className="stock-analysis-page__footnote">
                      建议只用于复核排序，不自动改交易规则。
                    </p>
                    <div className="stock-analysis-page__filter-status">
                      <span>三策略 T+5 排名</span>
                      <strong>{strategyOptimizationRows.length} 组</strong>
                      <small>样本阈值 {strategyOptimizationPayload?.min_sample ?? 20}，按收益、胜率和样本成熟度展示。</small>
                    </div>
                    {strategyOptimizationRows.length > 0 ? (
                      <div className="stock-analysis-page__table-wrap">
                        <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                          <thead>
                            <tr>
                              <th scope="col">策略</th>
                              <th scope="col">建议</th>
                              <th scope="col">T+5 收益</th>
                              <th scope="col">按日等权</th>
                              <th scope="col">原因</th>
                            </tr>
                          </thead>
                          <tbody>
                            {strategyOptimizationRows.map((row) => (
                              <tr key={row.summary_key}>
                                <td>{row.strategy_label}</td>
                                <td>{row.recommendation.priority_label}</td>
                                <td className="stock-analysis-page__table-number">
                                  {backtestStatsText(strategyOptimizationPrimaryStats(row, strategyOptimizationPayload))}
                                </td>
                                <td className="stock-analysis-page__table-number">
                                  {strategyOptimizationDateWeightedText(row, strategyOptimizationPayload)}
                                </td>
                                <td>{row.recommendation.reason}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="stock-analysis-page__empty">优化诊断样本不足。</p>
                    )}
                    <div className="stock-analysis-page__filter-status">
                      <span>各策略最强/最弱切片</span>
                      <strong>
                        {strategyOptimizationSlices.strongest?.label ?? "最强待补"} /{" "}
                        {strategyOptimizationSlices.weakest?.label ?? "最弱待补"}
                      </strong>
                      <small>
                        {strategyOptimizationSlices.weakest
                          ? `${strategyOptimizationSlices.weakest.strategy_label} ${strategyOptimizationSlices.weakest.label}：${strategyOptimizationSlices.weakest.recommendation.priority_label}`
                          : "切片样本不足，暂不做降权判断。"}
                      </small>
                    </div>
                    {strategyOptimizationSlices.strongest || strategyOptimizationSlices.weakest ? (
                      <div className="stock-analysis-page__table-wrap">
                        <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                          <thead>
                            <tr>
                              <th scope="col">切片</th>
                              <th scope="col">策略</th>
                              <th scope="col">建议</th>
                              <th scope="col">T+5 收益</th>
                            </tr>
                          </thead>
                          <tbody>
                            {([
                              ["最强", strategyOptimizationSlices.strongest],
                              ["最弱", strategyOptimizationSlices.weakest],
                            ] as Array<[string, StrategyOptimizationSlice | null]>).map(([label, slice]) =>
                              slice ? (
                                <tr key={`${label}:${slice.slice_key}`}>
                                  <td>
                                    {label}：{slice.label}
                                  </td>
                                  <td>{slice.strategy_label}</td>
                                  <td>{slice.recommendation.priority_label}</td>
                                  <td className="stock-analysis-page__table-number">
                                    {backtestStatsText(strategyOptimizationPrimaryStats(slice, strategyOptimizationPayload))}
                                  </td>
                                </tr>
                              ) : null,
                            )}
                          </tbody>
                        </table>
                      </div>
                    ) : null}
                  </>
                ) : null}
              </StrategyModuleCard>

              <StrategyModuleCard
                id="observation-pools"
                title="Observation Pools"
                subtitle="超跌 / 多因子 / 融合 · WARM 激活观察"
                badgeLabel={observationPoolsPanelSummary.badgeLabel ?? "观察池"}
                summary={observationPoolsPanelSummary}
                summaryTestId="stock-analysis-observation-pools-panel-summary"
                expanded={isStrategyCardExpanded("observation-pools")}
                onToggleExpand={() => toggleStrategyCard("observation-pools")}
                mountDetail
                sectionTestId="stock-analysis-mean-reversion"
              >
                <div className="stock-analysis-page__mean-reversion">
                  <div className={SA_SECTION_HEAD}>
                    <strong>超跌反弹观察池</strong>
                    <span className={SA_PILL}>WARM 激活</span>
                  </div>
                          {gateState && !meanReversionMarketActive ? (
                            <p className="stock-analysis-page__empty">当前不是 WARM 市场，超跌反弹观察池暂停。</p>
                          ) : null}
                          {meanReversionMarketActive && !meanReversionPayload ? (
                            <p className="stock-analysis-page__empty">数据未就绪。</p>
                          ) : null}
                          {meanReversionMarketActive &&
                          meanReversionPayload &&
                          meanReversionPayload.items.length === 0 ? (
                            <p className="stock-analysis-page__empty">当前无符合条件的超跌反弹候选股。</p>
                          ) : null}
                          {meanReversionMarketActive &&
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
                                      hybridFusionRank: ranks.hybridFusionRank,
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
                                        hybridFusionRank: ranks.hybridFusionRank,
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
                <div className="stock-analysis-page__factor-screen">
                  <div className={SA_SECTION_HEAD}>
                    <strong>多因子选股</strong>
                    <span className={SA_PILL}>
                      {factorScreenPayload?.candidate_count ?? 0} 只 ·{" "}
                      {factorScreenPayload?.coverage_note ?? "数据未就绪"}
                    </span>
                  </div>
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
                                      hybridFusionRank: ranks.hybridFusionRank,
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
                                        hybridFusionRank: ranks.hybridFusionRank,
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
              </StrategyModuleCard>

              <StrategyModuleCard
                id="events-monitoring"
                title="关键事件与监控"
                subtitle="诊断 / 缺口 / 风险触发复核队列"
                badgeLabel={eventsMonitoringPanelSummary.badgeLabel ?? "事件"}
                summary={eventsMonitoringPanelSummary}
                summaryTestId="stock-analysis-events-panel-summary"
                expanded={isStrategyCardExpanded("events-monitoring")}
                onToggleExpand={() => toggleStrategyCard("events-monitoring")}
                mountDetail
                sectionTestId="stock-analysis-events-monitoring"
              >
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
              </StrategyModuleCard>
              </div>
              </div>
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
                          : detailSelection.source === "hybrid_fusion"
                            ? "融合策略"
                          : detailSelection.source === "consensus"
                            ? "多策略共振"
                            : "复核队列",
                  sectorName: detailSelection.sectorName,
                  reviewRank: detailSelection.reviewRank,
                  distanceToBreakoutPct: detailSelection.distanceToBreakoutPct,
                  livermoreRank: detailSelection.livermoreRank,
                  meanReversionRank: detailSelection.meanReversionRank,
                  factorScreenRank: detailSelection.factorScreenRank,
                  hybridFusionRank: detailSelection.hybridFusionRank,
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
