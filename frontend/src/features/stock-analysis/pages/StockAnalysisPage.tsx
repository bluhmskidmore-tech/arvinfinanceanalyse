import { useEffect, useMemo, useRef, useState } from "react";
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
  buildSectorHeavyweightPreview,
  buildStrategyLensItems,
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
  buildThemeLeaderPreviewItems,
  buildThemeBreakoutReviewItems,
  buildThemeEvidenceStateRows,
  buildStockAnalysisPagePurpose,
  buildReviewQueueEmptyState,
  localizeStockBackendText,
  localizeStockDataFamily,
  localizeImplementationStage,
  localizeStrategyPanelErrorDetail,
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
  const message = error instanceof Error ? error.message : String(error);
  return localizeStockErrorMessage(message);
}

function strategyPanelErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  return localizeStrategyPanelErrorDetail(message);
}

function rawErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}

function localizeStockErrorMessage(message: string) {
  const value = message.trim();
  const normalized = value.toLowerCase().replace(/\s+/g, " ");
  const exactMessages: Record<string, string> = {
    "strategy unavailable": "策略服务暂不可用，请稍后重试。",
    "confluence unavailable": "联动观察服务暂不可用，请稍后重试。",
  };
  if (exactMessages[normalized]) {
    return exactMessages[normalized];
  }
  if (normalized.includes("not allowed") || normalized.includes("permission") || normalized.includes("forbidden")) {
    return "数据权限待确认，请联系管理员。";
  }
  if (
    (normalized.includes("source_table") || normalized.includes("source table")) &&
    normalized.includes("missing")
  ) {
    return "请求失败：必需数据源缺失，稍后复核供数状态。";
  }
  if (
    normalized.includes("request failed") ||
    normalized.includes("/ui/") ||
    normalized.includes("market-data") ||
    normalized.includes("livermore")
  ) {
    return "供数暂不可用，请稍后复核。";
  }
  return localizeStockBackendText(value);
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pass: "通过",
    fail: "未通过",
    ready: "就绪",
    partial: "部分",
    blocked: "阻断",
    unsupported: "不可用",
    available: "已接入",
    complete: "完整",
    pending: "待补",
    missing: "缺数据",
    stale: "已陈旧",
    ok: "正常",
    warning: "需复核",
  };
  return labels[status] ?? "状态待确认";
}

function supplyQualityLabel(value: string | null | undefined) {
  const normalized = (value ?? "").trim().toLowerCase();
  const labels: Record<string, string> = {
    ok: "正常",
    warning: "需复核",
    stale: "陈旧",
    error: "异常",
    pending: "待确认",
  };
  return labels[normalized] ?? "质量待确认";
}

function supplyVendorLabel(value: string | null | undefined) {
  const normalized = (value ?? "").trim().toLowerCase();
  const labels: Record<string, string> = {
    ok: "正常",
    degraded: "降级",
    error: "异常",
    pending: "待确认",
  };
  return labels[normalized] ?? "通道待确认";
}

function supplyFallbackLabel(value: string | null | undefined) {
  const normalized = (value ?? "").trim().toLowerCase();
  if (!normalized || normalized === "none") return "无回退";
  const labels: Record<string, string> = {
    latest_snapshot: "回退快照",
    cache: "缓存回退",
    mock: "模拟回退",
  };
  return labels[normalized] ?? "回退待确认";
}

function supplyBasisLabel(value: string | null | undefined) {
  const normalized = (value ?? "").trim().toLowerCase();
  if (normalized === "analytical") return "分析口径";
  if (normalized === "formal") return "正式口径";
  return "口径待确认";
}

function compactText(text: string | null | undefined, maxLength = 28) {
  if (!text) return "";
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength - 1)}…`;
}

function railActionLabel(
  candidate: ReturnType<typeof buildCandidateReviewQueue>[number] | null | undefined,
  fallback: string | null | undefined,
) {
  if (candidate) return `首位 ${candidate.stockName} · ${candidate.distanceToBreakoutPct}`;
  if (!fallback) return "等待复核";
  if (fallback.includes("多因子")) return "多因子池";
  if (fallback.includes("候选")) return "候选复核";
  if (fallback.includes("风险")) return "风险复核";
  return compactText(fallback, 14) || "等待复核";
}

function StockAnalysisLoadingWorkbench() {
  const kpiLabels = ["市场状态", "复核队列", "板块强弱", "数据边界", "风险观察", "闭环状态"];
  const railLabels = ["闭环", "风险", "边界", "复核"];

  return (
    <section
      className="stock-analysis-page__loading-workbench"
      data-testid="stock-analysis-loading-workbench"
      aria-label="股票分析加载态"
    >
      <div className="stock-analysis-page__loading-hero" aria-hidden="true">
        <span className="stock-analysis-page__loading-line stock-analysis-page__loading-line--short" />
        <span className="stock-analysis-page__loading-line stock-analysis-page__loading-line--title" />
        <div className="stock-analysis-page__loading-chip-row">
          <span />
          <span />
          <span />
        </div>
        <div className="stock-analysis-page__loading-meta-grid">
          <span />
          <span />
          <span />
          <span />
        </div>
      </div>
      <aside className="stock-analysis-page__loading-rail" aria-hidden="true">
        <span className="stock-analysis-page__loading-line stock-analysis-page__loading-line--short" />
        <span className="stock-analysis-page__loading-verdict" />
        <div className="stock-analysis-page__loading-rail-grid">
          {railLabels.map((label) => (
            <span key={label} />
          ))}
        </div>
      </aside>
      <div className="stock-analysis-page__loading-kpi-grid" aria-hidden="true">
        {kpiLabels.map((label) => (
          <span key={label} />
        ))}
      </div>
      <div className="stock-analysis-page__loading-panel" aria-hidden="true">
        <span className="stock-analysis-page__loading-line stock-analysis-page__loading-line--short" />
        <span className="stock-analysis-page__loading-chart" />
      </div>
      <p className="stock-analysis-page__visually-hidden" role="status">
        股票分析加载中
      </p>
    </section>
  );
}

function StockAnalysisErrorWorkbench({ message }: { message: string }) {
  return (
    <section
      className="stock-analysis-page__error-workbench"
      data-testid="stock-analysis-error-workbench"
      aria-label="股票分析错误态"
      role="alert"
    >
      <div className="stock-analysis-page__error-hero">
        <span className="stock-analysis-page__error-icon" aria-hidden="true">
          <SafetyCertificateOutlined />
        </span>
        <div>
          <p className="stock-analysis-page__dh-purpose-eyebrow">复核阻断</p>
          <h2>股票分析暂不可用</h2>
          <p>{message}</p>
        </div>
      </div>
      <div className="stock-analysis-page__error-grid" aria-label="错误态状态摘要">
        <span>
          <DatabaseOutlined aria-hidden="true" />
          <small>供数</small>
          <strong>待恢复</strong>
        </span>
        <span>
          <SafetyCertificateOutlined aria-hidden="true" />
          <small>结论</small>
          <strong>暂停</strong>
        </span>
        <span>
          <StockOutlined aria-hidden="true" />
          <small>复核</small>
          <strong>不可用</strong>
        </span>
      </div>
    </section>
  );
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

function CompactStatusTile({
  icon,
  label,
  value,
  detail,
  tone = "neutral",
  testId,
  title,
  className = "",
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  detail?: React.ReactNode;
  tone?: string;
  testId?: string;
  title?: string;
  className?: string;
}) {
  const valueLabel = typeof value === "string" || typeof value === "number" ? String(value) : null;
  const detailLabel = typeof detail === "string" || typeof detail === "number" ? String(detail) : null;
  const ariaLabel = [label, valueLabel, detailLabel].filter(Boolean).join(" ") || undefined;

  return (
    <div
      className={`inline-flex min-h-12 items-center gap-2 rounded-md border border-neutral-200 bg-neutral-50 px-2.5 py-2 ${className}`}
      role="status"
      aria-label={ariaLabel}
      data-testid={testId}
      title={title}
    >
      <StatusIcon tone={tone}>{icon}</StatusIcon>
      <span className="min-w-0">
        <span className={`block text-[10px] font-semibold ${toneTextClass(tone)}`}>{label}</span>
        <strong className="block truncate text-sm font-semibold text-neutral-900">{value}</strong>
        {detail ? <span className="block text-xs font-medium leading-snug text-neutral-600">{detail}</span> : null}
      </span>
    </div>
  );
}

function BacktestBoundaryChips({
  label,
  missingInputs,
  testId,
}: {
  label: string;
  missingInputs: readonly string[];
  testId?: string;
}) {
  const missing = missingInputs.filter((item) => item.trim().length > 0);

  return (
    <div
      className="mb-2 flex flex-wrap items-center gap-1.5"
      role="status"
      aria-label={`${label}边界`}
      data-testid={testId}
    >
      <span className="inline-flex items-center gap-1.5 rounded-md border border-primary-100 bg-primary-50 px-2 py-1 text-[11px] font-bold text-primary-700">
        <LineChartOutlined aria-hidden="true" /> 代理口径
      </span>
      <span className="inline-flex items-center gap-1.5 rounded-md border border-warning-200 bg-warning-50 px-2 py-1 text-[11px] font-bold text-warning-700">
        <DatabaseOutlined aria-hidden="true" /> 缺口 {missing.length}
      </span>
      {missing.slice(0, 3).map((input) => {
        const labelText = cycleInputLabel(input);
        return (
          <span
            key={input}
            className="inline-flex max-w-36 items-center truncate rounded-md border border-neutral-200 bg-white px-2 py-1 text-[11px] font-semibold text-neutral-600"
            title={labelText}
          >
            {compactText(labelText, 10)}
          </span>
        );
      })}
      {missing.length > 3 ? (
        <span className="inline-flex items-center rounded-md border border-neutral-200 bg-white px-2 py-1 text-[11px] font-semibold text-neutral-600">
          +{missing.length - 3}
        </span>
      ) : null}
    </div>
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

function buildReviewQueueRankingOption(rows: CompactChartRow[]): EChartsOption {
  return {
    animation: false,
    grid: { top: 3, right: 4, bottom: 3, left: 2, containLabel: false },
    xAxis: { type: "value", show: false, splitLine: { show: false } },
    yAxis: {
      type: "category",
      inverse: true,
      data: rows.map((row) => row.label),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
    },
    series: [
      {
        type: "bar",
        data: rows.map((row) => row.value),
        barWidth: 9,
        itemStyle: { color: stockChartPalette.success, borderRadius: [2, 2, 2, 2] },
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
        const row = rows[index];
        return row ? `${row.label}<br/>${row.detail ?? ""}` : "";
      },
    },
  };
}

function buildEventSummaryOption(rows: Array<{ label: string; count: number }>): EChartsOption {
  return {
    animation: false,
    grid: { top: 4, right: 4, bottom: 4, left: 2, containLabel: false },
    xAxis: { type: "value", show: false, splitLine: { show: false } },
    yAxis: { type: "category", show: false, data: ["输出"] },
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
  const absMax = Math.max(...values.map((value) => Math.abs(value)), 0.0001);
  const xMin = view === "pctchange" ? -absMax * 1.08 : 0;
  const xMax =
    view === "score"
      ? 1
      : view === "pctchange"
        ? absMax * 1.08
        : absMax * 1.12;
  return {
    animation: false,
    grid: { top: 6, right: 12, bottom: 4, left: 78, containLabel: false },
    xAxis: {
      type: "value",
      min: xMin,
      max: xMax,
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
        barWidth: 14,
        barMaxWidth: 18,
        showBackground: true,
        backgroundStyle: { color: stockChartPalette.track, borderRadius: [0, 3, 3, 0] },
        label: {
          show: true,
          position: "insideRight",
          color: stockChartPalette.ink,
          fontSize: 10,
          fontWeight: 700,
          padding: [0, 6, 0, 0],
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

type ClosedLoopRailKey = "entry_gate" | "adversarial_gate" | "risk_exit" | "replay" | "lineage";

function closedLoopRailIcon(key: ClosedLoopRailKey) {
  if (key === "entry_gate") return <LineChartOutlined />;
  if (key === "adversarial_gate") return <ThunderboltOutlined />;
  if (key === "risk_exit") return <FireOutlined />;
  if (key === "replay") return <BarChartOutlined />;
  return <DatabaseOutlined />;
}

function isTechnicalRiskExitReason(reason: string | null | undefined) {
  const normalized = reason?.trim().toLowerCase().replace(/[\s-]+/g, "_");
  const compact = normalized?.replace(/_/g, "");
  return (
    normalized?.includes("external_vendor") ||
    normalized?.includes("vendor_") ||
    normalized?.includes("source_table") ||
    compact?.includes("externalvendor") ||
    compact?.includes("vendor") ||
    compact?.includes("sourcetable") ||
    compact?.includes("choicestock")
  );
}

function riskExitBlockedSummary(reason: string | null | undefined) {
  const normalized = reason?.trim();
  if (!normalized) return "供数状态待确认";
  if (isTechnicalRiskExitReason(normalized)) return "风险退出待确认";
  if (/position_snapshot|ACTIVE A-share/i.test(normalized)) return "持仓快照缺失";
  return compactText(normalized, 24);
}

function riskExitBlockedDetail(reason: string | null | undefined, key: string | null | undefined) {
  const normalized = reason?.trim();
  if (isTechnicalRiskExitReason(normalized)) return "风险退出待确认";
  return localizeStockBackendText(reason, key);
}

function eventSourceLabel(source: string) {
  const labels: Record<string, string> = {
    diagnostic: "诊断",
    data_gap: "缺口",
    unsupported: "阻断",
    signal_confluence: "联动",
    risk_exit: "风险",
  };
  return labels[source] ?? source;
}

function eventLevelLabel(level: string) {
  if (level === "error") return "高";
  if (level === "warning") return "中";
  return "低";
}

function eventImpactLabel(row: { source: string; impact: string }) {
  if (row.source === "data_gap") return row.impact;
  if (row.source === "unsupported" || row.source === "risk_exit") return outputKeyLabel(row.impact);
  if (row.source === "signal_confluence") return "联动观察";
  return localizeStockDataFamily(row.impact);
}

function eventNameLabel(row: { source: string; event: string; impact: string }) {
  if (row.source === "data_gap") return statusLabel(row.event);
  if (row.source === "unsupported") return compactText(row.event, 20);
  if (row.source === "risk_exit") return compactText(row.event, 18);
  if (row.source === "signal_confluence") return "联动诊断";
  if (row.source === "diagnostic") return `${eventImpactLabel(row)}诊断`;
  return compactText(row.event.replace(/_/g, " "), 20);
}

function eventDetailLabel(row: { source: string; detail: string; impact: string }) {
  if (row.source === "diagnostic") return localizeStockBackendText(row.detail, row.impact);
  return row.detail;
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
    stock_candidate: "趋势候选",
    mean_reversion_candidates: "超跌池",
    factor_screen_candidates: "多因子",
    theme_breakout: "题材观察",
    hybrid_fusion: "融合池",
    risk_exit: "风险退出",
  };
  return key ? (labels[key] ?? "输出待确认") : "待补";
}

function dataGapFamilyLabel(inputFamily: string | null | undefined) {
  return localizeStockDataFamily(inputFamily);
}

type CycleLayer = NonNullable<LivermoreStrategyPayload["cycle_rotation_framework"]>["layers"][number];

function cycleInputLabel(input: string | null | undefined) {
  if (!input) return "待补";
  const normalized = input.trim().toLowerCase().replace(/[\s-]+/g, "_");
  const labels: Record<string, string> = {
    market_gate: "市场门控",
    sector_rank: "板块强弱",
    stock_candidates: "趋势候选",
    pmi: "PMI",
    credit_impulse: "信用脉冲",
    profit_cycle: "盈利周期",
    market_flow: "市场流动",
    valuation_support: "估值支撑",
    breadth: "市场宽度",
    limit_up_quality: "涨停质量",
    macro_score: "宏观分",
    price_spread: "价差",
    factor_screen: "多因子",
    factor_screen_candidates: "多因子",
    theme_breakout: "题材观察",
    stock_candidate: "趋势候选",
    hybrid_fusion: "融合池",
    social_text_raw: "社交文本",
    ocr_asr_pipeline: "图文识别",
    bot_spam_detection: "噪声过滤",
    industry_profit: "行业盈利",
    industry_profit_cycle: "行业盈利",
    industry_revenue_cycle: "行业收入",
    turnover_persistence: "换手持续",
    turnover_proxy: "换手代理",
    valuation_percentile_history: "估值分位",
    transaction_cost: "交易成本",
    disclosure_lag: "披露滞后",
    liquidity_floor: "流动性底线",
    risk_exit: "风险退出",
    margin_balance: "两融余额",
    unlock_event_panel: "解禁事件",
    sector_rank_for_regime: "板块强弱",
    fund_flow: "资金流",
    northbound_flow: "北向资金",
    earnings_revision: "业绩修正",
    external_vendor_cycle_feed: "输入待确认",
  };
  return labels[normalized] ?? "输入待确认";
}

function compactCycleInputs(inputs: string[]) {
  return inputs.map(cycleInputLabel).slice(0, 3).join("、") || "无";
}

function cycleInputSummary(availableInputs: string[], missingInputs: string[]) {
  const parts = [];
  if (availableInputs.length > 0) {
    parts.push(`已接入 ${compactCycleInputs(availableInputs)}`);
  }
  if (missingInputs.length > 0) {
    parts.push(`待补 ${compactCycleInputs(missingInputs)}`);
  }
  return parts.join(" · ") || "输入待补";
}

function cycleLayerTitleLabel(layer: CycleLayer) {
  const labels: Record<CycleLayer["key"], string> = {
    macro_direction: "宏观方向",
    industry_cycle: "行业景气",
    market_flow: "市场流动",
    valuation_support: "估值支撑",
    execution_constraints: "执行边界",
  };
  return labels[layer.key] ?? layer.title;
}

function cycleLayerWeightLabel(layer: CycleLayer) {
  return layer.weight == null ? "边界" : `${Math.round(layer.weight * 100)}%`;
}

function cycleRuleSummary(layers: CycleLayer[]) {
  const weighted = layers.filter((layer) => layer.weight != null);
  if (weighted.length === 0) return "权重待补";
  return weighted.map((layer) => `${cycleLayerTitleLabel(layer)} ${cycleLayerWeightLabel(layer)}`).join(" · ");
}

function cycleCadenceLabel(cadence: string | null | undefined) {
  const value = cadence?.trim();
  if (!value) return "节奏待补";
  const normalized = value.toLowerCase();
  if (normalized.includes("external_vendor") || normalized.includes("external vendor")) return "节奏待确认";
  if (normalized.includes("monthly") && normalized.includes("weekly")) {
    return "月度核心复核 · 周度跟踪";
  }
  if (normalized.includes("monthly")) return "月度复核";
  if (normalized.includes("weekly")) return "周度复核";
  return "节奏待确认";
}

function cycleGapLabel(gap: string) {
  const [input, rawStatus] = gap.split("(");
  const status = rawStatus?.replace(")", "").trim();
  return `${cycleInputLabel(input)} ${statusLabel(status || "missing")}`;
}

function cycleConstraintLabel(constraint: string) {
  const industryCap = constraint.match(/industry cap\s+(\d+%)/i);
  if (industryCap) return `行业上限 ${industryCap[1]}`;
  const stockCap = constraint.match(/(?:single\s+)?stock cap\s+(\d+%)/i);
  if (stockCap) return `个股上限 ${stockCap[1]}`;
  if (/exclude st and suspended stocks/i.test(constraint)) return "排除 ST / 停牌";
  if (/monthly core review.*weekly satellite monitoring/i.test(constraint)) return "月度核心复核 · 周度跟踪";
  if (/exclude bottom\s+(\d+%).*liquidity/i.test(constraint)) {
    return `排除低流动性后 ${constraint.match(/bottom\s+(\d+%)/i)?.[1] ?? ""}`.trim();
  }
  if (/require\s+(\d+)\s+trading-day history/i.test(constraint)) {
    return `历史样本不少于 ${constraint.match(/require\s+(\d+)/i)?.[1] ?? "250"} 日`;
  }
  if (/lifecourtscore.*top\s+(\d+%)/i.test(constraint)) {
    return `生命法庭分位前 ${constraint.match(/top\s+(\d+%)/i)?.[1] ?? ""}`.trim();
  }
  if (/pconf.*top\s+(\d+%)/i.test(constraint)) {
    return `价格确认前 ${constraint.match(/top\s+(\d+%)/i)?.[1] ?? ""}`.trim();
  }
  if (/crowd.*below\s+(\d+)/i.test(constraint)) {
    const percentile = constraint.match(/below\s+(\d+)/i)?.[1] ?? "阈值";
    return percentile === "阈值" ? "拥挤度低于阈值" : `拥挤度低于 ${percentile} 分位`;
  }
  if (/hygiene\s*>\s*0/i.test(constraint)) return "数据卫生通过";
  return "约束待确认";
}

function cycleEvidenceLabel(text: string | null | undefined) {
  const value = text?.trim();
  if (!value) return "证据待补";
  const lower = value.toLowerCase();
  if (lower.includes("external_vendor") || lower.includes("external vendor")) return "证据待确认";
  if (lower.includes("market gate") && lower.includes("pmi") && lower.includes("credit impulse")) {
    return "市场门控已接入；PMI 与信用脉冲待补。";
  }
  if (lower.includes("sector_rank")) return "板块强弱已接入。";
  if (lower.includes("pricespread") || lower.includes("price_spread") || lower.includes("macroscore")) {
    return "价差与宏观分已接入。";
  }
  if (lower.includes("stock candidate review") || lower.includes("choice stock daily observation")) {
    return "候选复核与换手观察已接入。";
  }
  if (lower.includes("factor_screen_candidates") || lower.includes("valuation")) {
    return "多因子与估值支撑已接入。";
  }
  if (lower.includes("risk-exit evidence") || lower.includes("sizing") || lower.includes("liquidity controls")) {
    return "风险退出证据已接入；仓位、成本与流动性回放待补。";
  }
  if (lower.includes("not landed") || lower.includes("missing")) return "证据待确认。";
  if (lower.includes("available")) return "证据已接入。";
  return "证据待确认";
}

function cycleBoundaryLabel(text: string | null | undefined) {
  const value = text?.trim();
  if (!value) return "边界待补";
  const lower = value.toLowerCase();
  if (lower.includes("lifecourt") || lower.includes("proxy-reconstructed") || lower.includes("influencer")) {
    return "生命法庭层为量化重建口径，原始文本规则尚未完整接入。";
  }
  if (lower.includes("proxy")) return "当前为代理观察口径，需复核后使用。";
  return "边界待确认";
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
    asOfLabel: payload.as_of_date ?? "日期待补",
    requestedAsOfLabel: payload.requested_as_of_date ?? "默认",
    gateLabel: `门控 ${localizeMarketDataStatus(gate.state)}`,
    exposureLabel: `暴露 ${formatSupplyPercent(gate.exposure)}`,
    conditionLabel: `条件 ${gate.passed_conditions}/${gate.required_conditions}`,
    availableConditionLabel: `可评估 ${gate.available_conditions}`,
    readinessLabel: `就绪 ${readyRuleCount}/${readinessRows.length}`,
    readinessValueLabel: `${readyRuleCount}/${readinessRows.length}`,
    dataGapLabel: `缺口 ${notReadyGaps.length}`,
    dataGapValueLabel: `${notReadyGaps.length}`,
    supportedLabel: `可用 ${supportedOutputs.length}`,
    supportedValueLabel: `${supportedOutputs.length}`,
    unsupportedLabel: `阻断 ${unsupportedOutputs.length}`,
    unsupportedValueLabel: `${unsupportedOutputs.length}`,
    sectorSupplyLabel: `板块 ${sectorCount}`,
    sectorSupplyValueLabel: `${sectorCount}`,
    candidateSupplyLabel: `候选 ${candidateCount}`,
    candidateSupplyValueLabel: `${candidateCount}`,
    riskSupplyLabel: `风险 ${risk?.signal_count ?? 0}`,
    riskSupplyValueLabel: `${risk?.signal_count ?? 0}`,
    riskDetailLabel: `持仓 ${risk?.position_count ?? 0} / 触发 ${risk?.signal_count ?? 0} / 观察 ${watchCount}`,
    qualityLabel: `质量 ${supplyQualityLabel(meta.quality_flag)}`,
    vendorLabel: `通道 ${supplyVendorLabel(meta.vendor_status)}`,
    fallbackLabel: supplyFallbackLabel(meta.fallback_mode),
    basisLabel: supplyBasisLabel(payload.basis),
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

function strategyDisplayLabel(label: string | null | undefined, signalKind?: string | null): string {
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

function strategyBacktestKindLabel(kind: string): string {
  return strategyDisplayLabel(kind);
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
      label: strategyBacktestKindLabel(kind),
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
          label: strategyBacktestKindLabel(kind),
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
    return "样本不足";
  }
  const priorityCandidates = sufficientRows.filter(
    (row) => row.priority_label === "优先复核" && (row.diagnostics?.risk_flags ?? []).length === 0,
  );
  const priorityRows = priorityCandidates.filter((row) => row.diagnostics?.maturity?.status !== "narrow");
  if (priorityRows.length > 0) {
    return `优先复核：${priorityRows.map((row) => strategyDisplayLabel(row.strategy_label, row.signal_kind)).join("、")}`;
  }
  if (priorityCandidates.length > 0) {
    return `优先观察：${priorityCandidates
      .map((row) => strategyDisplayLabel(row.strategy_label, row.signal_kind))
      .join("、")}`;
  }
  return "当前状态降权观察";
}

function strategyPrioritySummaryReason(rows: StrategyPriorityRow[]): string {
  const firstPriority = rows.find((row) => row.priority_label === "优先复核");
  if (firstPriority) return strategyPriorityReasonLabel(firstPriority);
  const firstInsufficient = rows.find((row) => row.sample_status === "insufficient");
  if (firstInsufficient) return strategyPriorityReasonLabel(firstInsufficient);
  return rows[0] ? strategyPriorityReasonLabel(rows[0]) : "暂无当前状态策略评分。";
}

function strategyPriorityReasonLabel(row: StrategyPriorityRow): string {
  return localizeStockBackendText(row.reason, row.signal_kind);
}

function localizeRankRangeLabel(
  label: string | null | undefined,
  rankFrom?: number | null,
  rankTo?: number | null,
  fallback = "排名待补",
): string {
  if (typeof rankFrom === "number" && Number.isFinite(rankFrom) && typeof rankTo === "number" && Number.isFinite(rankTo)) {
    return `第 ${rankFrom}-${rankTo} 名`;
  }
  const value = label?.trim() ?? "";
  const rankLabel = value.match(/^(?:rank\s*)?(\d+)\s*-\s*(\d+)$/i);
  if (rankLabel) return `第 ${rankLabel[1]}-${rankLabel[2]} 名`;
  return value || fallback;
}

function strategyPriorityScopeLabel(label: string | null | undefined) {
  const value = label?.trim();
  if (!value) return "排序范围待确认";
  const normalized = value.toLowerCase().replace(/[\s-]+/g, "_");
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
    return "排序范围待确认";
  }
  return value;
}

function strategyRiskFlagLabel(label: string | null | undefined) {
  const value = label?.trim();
  if (!value) return "风险待确认";
  const normalized = value.toLowerCase().replace(/[\s-]+/g, "_");
  const lower = value.toLowerCase();
  const labels: Record<string, string> = {
    long_window_risk: "长窗口风险",
  };
  if (labels[normalized]) return labels[normalized];
  const compact = normalized.replace(/_/g, "");
  if (
    normalized.includes("external_vendor") ||
    normalized.includes("vendor_") ||
    normalized.includes("source_table") ||
    lower.includes("source table") ||
    compact.includes("externalvendor") ||
    compact.includes("vendor") ||
    compact.includes("sourcetable") ||
    compact.includes("choicestock")
  ) {
    return "风险待确认";
  }
  return value;
}

function strategyPriorityStatusLabel(label: string | null | undefined) {
  const value = label?.trim();
  if (!value) return "状态待确认";
  const normalized = value.toLowerCase().replace(/[\s-]+/g, "_");
  const labels: Record<string, string> = {
    优先复核: "优先复核",
    降权观察: "降权观察",
    继续观察: "继续观察",
    样本不足: "样本不足",
  };
  if (labels[value]) return labels[value];
  if (labels[normalized]) return labels[normalized];
  if (normalized.includes("external_vendor") || normalized.includes("vendor_")) return "状态待确认";
  return "状态待确认";
}

function strategyPriorityDiagnosticLabels(row: StrategyPriorityRow): string[] {
  const diagnostics = row.diagnostics;
  if (!diagnostics) return [];
  const labels: string[] = [];
  if (diagnostics.priority_scope_label) {
    const scopeStats = diagnostics.priority_scope_stats?.return_5d;
    const scopeStatsText = scopeStats ? backtestStatsText(scopeStats) : null;
    const scopeLabel = strategyPriorityScopeLabel(diagnostics.priority_scope_label);
    labels.push(scopeStatsText ? `${scopeLabel} ${scopeStatsText}` : scopeLabel);
  }
  if (diagnostics.maturity?.status === "narrow") {
    labels.push(`${diagnostics.maturity.label} ${localizeStockBackendText(diagnostics.maturity.reason, row.signal_kind)}`);
  }
  for (const bucket of diagnostics.rank_buckets ?? []) {
    const bucketStatusLabel = strategyPriorityStatusLabel(bucket.priority_label);
    if (!bucket.included_in_priority && (bucket.priority_label === "降权观察" || bucketStatusLabel === "状态待确认")) {
      labels.push(`${localizeRankRangeLabel(bucket.label, bucket.rank_from, bucket.rank_to)} ${bucketStatusLabel}`);
    }
  }
  for (const flag of diagnostics.risk_flags ?? []) {
    if (flag.label) {
      labels.push(strategyRiskFlagLabel(flag.label));
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

function strategyOptimizationReasonLabel(row: StrategyOptimizationSummary | StrategyOptimizationSlice): string {
  return localizeStockBackendText(row.recommendation.reason, row.signal_kind);
}

function strategyOptimizationSliceLabel(slice: StrategyOptimizationSlice): string {
  const dimension = slice.dimension.trim().toLowerCase();
  const bucket = slice.bucket.trim();
  const normalizedBucket = bucket.toLowerCase().replace(/[\s-]+/g, "_");
  const normalizedLabel = slice.label.trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (
    dimension.includes("external_vendor") ||
    dimension.includes("vendor_") ||
    normalizedBucket.includes("external_vendor") ||
    normalizedBucket.includes("vendor_") ||
    normalizedLabel.includes("external_vendor") ||
    normalizedLabel.includes("vendor_")
  ) {
    return "切片待确认";
  }
  if (dimension === "rank" && /^\d+\s*-\s*\d+$/.test(bucket)) {
    return localizeRankRangeLabel(bucket, null, null, "切片待补");
  }
  const rankLabel = localizeRankRangeLabel(slice.label, null, null, "");
  if (rankLabel) return rankLabel;
  return slice.label || "切片待补";
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
  const [firstScreenAnalyticsTab, setFirstScreenAnalyticsTab] = useState<
    "consensus" | "priority" | "optimization"
  >("consensus");
  const [firstScreenAnalyticsRequested, setFirstScreenAnalyticsRequested] = useState(false);

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
  const sectorLeaderRow = sectorRowsFull[0] ?? null;
  const sectorTailRow = sectorRowsFull.length > 0 ? sectorRowsFull[sectorRowsFull.length - 1] : null;
  const sectorCoverageCount = sectorRowsFull.reduce((sum, row) => sum + row.constituentCount, 0);

  const sectorViewRows = useMemo(
    () => (strategyPayload ? buildSectorViewModel(strategyPayload, sectorView) : []),
    [strategyPayload, sectorView],
  );

  const sortedDetailRows = useMemo(() => {
    const cmp = buildSectorTableSortComparator(sectorSort.key, sectorSort.order);
    return [...sectorRowsFull].sort(cmp);
  }, [sectorRowsFull, sectorSort]);

  const reviewQueue = useMemo(() => {
    return strategyPayload ? buildCandidateReviewQueue(strategyPayload) : [];
  }, [strategyPayload]);

  const gateState = strategyPayload?.market_gate.state;
  const meanReversionPayload = strategyPayload?.mean_reversion_candidates;
  const meanReversionMarketActive = gateState === "WARM";
  const factorScreenPayload = strategyPayload?.factor_screen_candidates;
  const factorScreenCoverageNote = factorScreenPayload?.coverage_note
    ? localizeStockBackendText(factorScreenPayload.coverage_note, "factor_screen_candidates")
    : null;
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

  const strategyLensItems = useMemo(
    () => (strategyPayload ? buildStrategyLensItems(strategyPayload, consensusSummary) : []),
    [strategyPayload, consensusSummary],
  );

  const consensusFirstScreenItems = useMemo(
    () => consensusSummary.items.slice(0, 8),
    [consensusSummary.items],
  );
  const consensusHitCount = consensusSummary.items.filter((item) => item.consensusCount >= 2).length;

  const factorPreviewItems = useMemo(
    () => factorScreenPayload?.items.slice(0, 10) ?? [],
    [factorScreenPayload?.items],
  );

  const meanReversionPreviewItems = useMemo(
    () => (meanReversionMarketActive ? meanReversionPayload?.items.slice(0, 8) ?? [] : []),
    [meanReversionMarketActive, meanReversionPayload?.items],
  );

  function scrollToStockSection(targetId: string) {
    document.getElementById(targetId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const themeBreakoutCards = useMemo(
    () => (strategyPayload ? buildThemeBreakoutCards(strategyPayload) : []),
    [strategyPayload],
  );

  const themeLeaderPreviewItems = useMemo(
    () => buildThemeLeaderPreviewItems(themeBreakoutCards, 12),
    [themeBreakoutCards],
  );

  const sectorHeavyweightPreview = useMemo(
    () => (strategyPayload ? buildSectorHeavyweightPreview(strategyPayload) : null),
    [strategyPayload],
  );

  const sectorHeavyweightRows = sectorHeavyweightPreview?.rows.filter((row) => row.stocks.length > 0) ?? [];

  function handleFirstScreenAnalyticsTabChange(key: string) {
    const tab = key as "consensus" | "priority" | "optimization";
    setFirstScreenAnalyticsTab(tab);
    if (tab === "priority" || tab === "optimization") {
      setFirstScreenAnalyticsRequested(true);
    }
  }

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
  const selectedSectorLeadCandidate = filteredCandidates[0] ?? null;
  const sectorLinkTone = sectorFilterSectorCode
    ? filteredCandidates.length > 0
      ? "active"
      : "empty"
    : "all";
  const sectorLinkSummary = sectorFilterSectorCode
    ? filteredCandidates.length > 0
      ? `${selectedSectorLabel ?? sectorFilterSectorCode} · ${filteredCandidates.length} 个候选`
      : `${selectedSectorLabel ?? sectorFilterSectorCode} · 无候选`
    : `全部行业 · ${reviewQueue.length} 个候选`;
  const sectorLinkFocus = selectedSectorLeadCandidate
    ? `首位 ${selectedSectorLeadCandidate.stockName} · 距观察 ${selectedSectorLeadCandidate.distanceToBreakoutPct}`
    : sectorFilterSectorCode
      ? "该行业暂无线索"
      : "按板块收敛";

  const reviewQueueChartRows = useMemo<CompactChartRow[]>(
    () => {
      const visible = filteredCandidates.slice(0, 6);
      return visible.map((card, index) => {
        const evidenceCount = card.primaryEvidence.length + card.supportingEvidence.length;
        return {
          key: card.stockCode,
          label: `#${card.rank} ${card.stockName}`,
          value: visible.length - index,
          detail: `${card.sectorName} · 距观察位 ${card.distanceToBreakoutPct} · 证据 ${evidenceCount}`,
        };
      });
    },
    [filteredCandidates],
  );

  const reviewQueueRankingOption = useMemo(
    () => buildReviewQueueRankingOption(reviewQueueChartRows),
    [reviewQueueChartRows],
  );

  const riskRows = useMemo(
    () => (strategyPayload ? buildRiskExitRows(strategyPayload, confluencePayload) : []),
    [strategyPayload, confluencePayload],
  );
  const riskTriggeredCount = riskRows.filter((row) => row.status === "triggered").length;
  const riskWatchCount = riskRows.filter((row) => row.status === "watch").length;
  const railNextActionFullLabel = reviewQueue[0]
    ? `${reviewQueue[0].stockName} · 距观察 ${reviewQueue[0].distanceToBreakoutPct}`
    : decisionSummary?.nextReviewAction ?? "等待复核队列";
  const railNextActionLabel = railActionLabel(reviewQueue[0], decisionSummary?.nextReviewAction);
  const railRiskTone = riskTriggeredCount > 0 ? "negative" : riskWatchCount > 0 ? "warning" : "positive";

  const riskExitUnsupported = strategyPayload?.unsupported_outputs.find((output) => output.key === "risk_exit");
  const themeBreakoutUnsupported = strategyPayload?.unsupported_outputs.find((output) => output.key === "theme_breakout");
  const themeBreakoutBlockerText = themeBreakoutUnsupported?.reason
    ? localizeStockBackendText(themeBreakoutUnsupported.reason, themeBreakoutUnsupported.key)
    : null;
  const themeBreakoutBlockerLabel = themeBreakoutBlockerText
    ? themeBreakoutBlockerText.includes("门控") || themeBreakoutBlockerText.includes("过热")
      ? "门控暂停"
      : compactText(themeBreakoutBlockerText, 10)
    : null;

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
          label: statusLabel(status),
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
      strategyPayload
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
      strategyPayload
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
  const boundaryRailIssueCount = boundaryRailItems.filter((item) => item.tone !== "positive").length;

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

  const analyticsAsOf = strategyPayload?.as_of_date ?? null;
  const stockDetailAsOfDate = analyticsAsOf ?? undefined;
  const currentMarketState = strategyPayload?.market_gate.state ?? null;
  const strategyScoreQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-strategy-score",
      analyticsAsOf ?? "__none",
      currentMarketState ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreStrategyScore({
        snapshotTo: analyticsAsOf ?? undefined,
        currentMarketState: currentMarketState ?? undefined,
        minSample: 20,
        primaryHorizon: "return_5d",
      }),
    enabled: Boolean(
      analyticsAsOf && (strategyPrioritySection.seen || firstScreenAnalyticsRequested),
    ),
    ...stockAnalysisReadQueryOptions,
  });
  const strategyScorePayload = strategyScoreQuery.data?.result ?? null;
  const strategyOptimizationQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-strategy-optimization",
      analyticsAsOf ?? "__none",
      currentMarketState ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreStrategyOptimization({
        snapshotTo: analyticsAsOf ?? undefined,
        currentMarketState: currentMarketState ?? undefined,
        minSample: 20,
        primaryHorizon: "return_5d",
      }),
    enabled: Boolean(
      analyticsAsOf && (strategyOptimizationSection.seen || firstScreenAnalyticsRequested),
    ),
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
  const strategyBacktestSnapshotFrom = analyticsAsOf ? dayjs(analyticsAsOf).subtract(10, "day").format("YYYY-MM-DD") : null;

  const strategyBacktestQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-candidate-history-strategy-backtest",
      strategyBacktestSnapshotFrom ?? "__none",
      analyticsAsOf ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreCandidateHistory({
        snapshotFrom: strategyBacktestSnapshotFrom ?? undefined,
        snapshotTo: analyticsAsOf ?? undefined,
        limit: 500,
      }),
    enabled: Boolean(analyticsAsOf && strategyBacktestSection.seen),
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
      analyticsAsOf ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreCycleProxyBacktest({
        snapshotTo: analyticsAsOf ?? undefined,
      }),
    enabled: Boolean(analyticsAsOf && cycleRotationFramework && cycleFrameworkSection.seen),
    ...stockAnalysisReadQueryOptions,
  });
  const cycleProxyBacktestPayload: LivermoreCycleProxyBacktestPayload | null =
    cycleProxyBacktestQuery.data?.result ?? null;
  const candidateHistoryPortfolioBacktestQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-candidate-history-portfolio-backtest",
      analyticsAsOf ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreCandidateHistoryPortfolioBacktest({
        snapshotTo: analyticsAsOf ?? undefined,
      }),
    enabled: Boolean(analyticsAsOf && cycleRotationFramework && cycleFrameworkSection.seen),
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
    strategyBacktestSnapshotFrom && analyticsAsOf
      ? `${strategyBacktestSnapshotFrom} 至 ${analyticsAsOf}`
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
              enabled: Boolean(analyticsAsOf && cycleRotationFramework && cycleFrameworkSection.seen),
              isLoading: candidateHistoryPortfolioBacktestQuery.isLoading,
              isError: candidateHistoryPortfolioBacktestQuery.isError,
            }),
            proxyQueryState: resolvePanelQueryState({
              enabled: Boolean(analyticsAsOf && cycleRotationFramework && cycleFrameworkSection.seen),
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
      analyticsAsOf,
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
          enabled: Boolean(analyticsAsOf && strategyPrioritySection.seen),
          isLoading: strategyScoreQuery.isLoading,
          isError: strategyScoreQuery.isError,
        }),
        errorMessage: strategyScoreQuery.isError ? rawErrorMessage(strategyScoreQuery.error) : undefined,
      }),
    [
      strategyPriorityRows,
      strategyScorePayload,
      currentMarketState,
      analyticsAsOf,
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
          enabled: Boolean(analyticsAsOf && strategyBacktestSection.seen),
          isLoading: strategyBacktestQuery.isLoading,
          isError: strategyBacktestQuery.isError,
        }),
        errorMessage: strategyBacktestQuery.isError ? rawErrorMessage(strategyBacktestQuery.error) : undefined,
      }),
    [
      strategyBacktestPayload,
      strategyBacktestSampleCount,
      strategyBacktestWindow,
      strategyBacktestDateRangeLabel,
      strategyBacktestRows,
      analyticsAsOf,
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
          enabled: Boolean(analyticsAsOf && strategyOptimizationSection.seen),
          isLoading: strategyOptimizationQuery.isLoading,
          isError: strategyOptimizationQuery.isError,
        }),
        errorMessage: strategyOptimizationQuery.isError
          ? rawErrorMessage(strategyOptimizationQuery.error)
          : undefined,
      }),
    [
      strategyOptimizationPayload,
      strategyOptimizationRows,
      analyticsAsOf,
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
      priorityStrategyLabel: topPriority
        ? strategyDisplayLabel(topPriority.strategy_label, topPriority.signal_kind)
        : null,
    });
  }, [gateState, themeBreakoutUnsupported?.reason, strategyPriorityRows]);

  const deepZoneAuditRows = useMemo(
    () => [
      {
        key: "supply",
        icon: <DatabaseOutlined aria-hidden="true" />,
        label: "供数",
        value: cycleRotationPanelSummary?.badgeLabel ?? themeBreakoutPanelSummary?.badgeLabel ?? "待确认",
        tone: cycleRotationPanelSummary?.tone ?? themeBreakoutPanelSummary?.tone ?? "neutral",
      },
      {
        key: "replay",
        icon: <BarChartOutlined aria-hidden="true" />,
        label: "回放",
        value: strategyBacktestPanelSummary.badgeLabel ?? strategyBacktestDateRangeLabel,
        tone: strategyBacktestPanelSummary.tone ?? "neutral",
      },
      {
        key: "review",
        icon: <StockOutlined aria-hidden="true" />,
        label: "候选",
        value: `${consensusSummary.items.length} / ${reviewQueue.length}`,
        tone: consensusReviewPanelSummary.tone ?? marketPriorityPanelSummary.tone ?? "neutral",
      },
      {
        key: "events",
        icon: <FireOutlined aria-hidden="true" />,
        label: "事件",
        value: eventsMonitoringPanelSummary.badgeLabel ?? `${eventMonitorRows.length}`,
        tone: eventsMonitoringPanelSummary.tone ?? "neutral",
      },
    ],
    [
      consensusReviewPanelSummary.tone,
      consensusSummary.items.length,
      cycleRotationPanelSummary?.badgeLabel,
      cycleRotationPanelSummary?.tone,
      eventMonitorRows.length,
      eventsMonitoringPanelSummary.badgeLabel,
      eventsMonitoringPanelSummary.tone,
      marketPriorityPanelSummary.tone,
      reviewQueue.length,
      strategyBacktestDateRangeLabel,
      strategyBacktestPanelSummary.badgeLabel,
      strategyBacktestPanelSummary.tone,
      themeBreakoutPanelSummary?.badgeLabel,
      themeBreakoutPanelSummary?.tone,
    ],
  );

  const sectorSeriesExpanded = sectorSeriesCollapseKeys.includes("sector-rank-series-multi");

  const sectorRankSeriesQuery = useQuery({
    queryKey: ["stock-analysis", "livermore-sector-rank-series", analyticsAsOf ?? "__none", sectorSeriesWindow] as const,
    queryFn: () =>
      client.getLivermoreSectorRankSeries({
        asOfDate: analyticsAsOf ?? undefined,
        windowDays: sectorSeriesWindow,
        topK: 10,
      }),
    enabled: Boolean(
      sectorSeriesExpanded &&
        analyticsAsOf &&
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
        asOfDate: strategyPayload?.as_of_date ?? null,
        requestedAsOfDate: strategyPayload?.requested_as_of_date ?? asOfOverride ?? null,
        sectorFilterSectorCode,
        sectorFilterLabel: selectedSectorLabel,
        sectorView,
        detailSelection,
      }),
    [
      asOfOverride,
      detailSelection,
      sectorFilterSectorCode,
      sectorView,
      selectedSectorLabel,
      strategyPayload?.as_of_date,
      strategyPayload?.requested_as_of_date,
    ],
  );

  return (
    <PageV2Shell testId="stock-analysis-page" style={stockAnalysisPageCssVars}>
      <main className="stock-analysis-page" data-layout-rev="2026-05-31e" data-data-viz-rev="2026-05-31e">
        <header
          className="stock-analysis-page__header stock-analysis-page__dh-topbar"
          data-testid="stock-analysis-toolbar"
        >
          <div className="stock-analysis-page__header-main stock-analysis-page__dh-topbar-main">
            <div className="stock-analysis-page__header-title-row">
              <h1>股票分析</h1>
              <span className="stock-analysis-page__badge">只读复核</span>
            </div>
            <div className="stock-analysis-page__toolbar-info" aria-label="复核控制状态">
              <span className="stock-analysis-page__toolbar-title">
                <SafetyCertificateOutlined aria-hidden="true" />
                <strong>复核控制</strong>
              </span>
              <span className="stock-analysis-page__toolbar-pill">
                <ClockCircleOutlined aria-hidden="true" />
                观察日 {backendSupplyOverview?.asOfLabel ?? analyticsAsOf ?? "日期待补"}
              </span>
              <span
                className="stock-analysis-page__toolbar-pill"
                data-tone={backendSupplyOverview?.qualityLabel === "质量 正常" ? "positive" : undefined}
              >
                <SafetyCertificateOutlined aria-hidden="true" />
                {backendSupplyOverview?.gateLabel ?? decisionSummary?.gateLabel ?? "门控待确认"}
              </span>
              <span className="stock-analysis-page__toolbar-pill">
                <DatabaseOutlined aria-hidden="true" />
                {backendSupplyOverview?.dataGapLabel ?? decisionSummary?.boundaryLabel ?? "边界待确认"}
              </span>
              <span className="stock-analysis-page__toolbar-pill">
                <StockOutlined aria-hidden="true" />
                复核 {reviewQueue.length}
              </span>
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
                复核助手
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
          <StockAnalysisLoadingWorkbench />
        ) : null}

        {strategyQuery.isError ? (
          <StockAnalysisErrorWorkbench message={errorMessage(strategyQuery.error)} />
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
                    数据陈旧、通道异常或使用回退快照。下方结论仅供复核参考。
                  </div>
                ) : null}

                <div
                  className="stock-analysis-page__first-screen-main"
                  data-testid="stock-analysis-first-screen-main"
                >
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
                      <div className="stock-analysis-page__dh-purpose-main">
                        <span className="stock-analysis-page__dh-purpose-eyebrow">{pagePurpose.eyebrow}</span>
                        <h2 className="stock-analysis-page__dh-purpose-title">{pagePurpose.title}</h2>
                      </div>
                      <div className="stock-analysis-page__dh-purpose-status" aria-label="页面状态">
                        <span>{pagePurpose.asOfLine}</span>
                        <span>{pagePurpose.dataStatusLine}</span>
                      </div>
                    </div>
                  ) : null}

                  <div className="flex flex-col gap-3" data-testid="stock-analysis-decision-panel">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="flex min-w-0 flex-1 flex-col gap-2">
                        <div className="stock-analysis-page__dh-hero-meta-row flex flex-wrap items-center gap-2">
                          <span className="stock-analysis-page__dh-chip">只读复核</span>
                          <span className="stock-analysis-page__dh-hero-meta">
                            观察日{" "}
                            <strong className="stock-analysis-page__tabular text-[color:var(--sa-dh-ink)]">
                              {decisionSummary.asOfLabel}
                            </strong>
                          </span>
                          {backendSupplyOverview ? (
                            <span className="stock-analysis-page__dh-hero-meta">
                              数据日 {backendSupplyOverview.asOfLabel}
                            </span>
                          ) : null}
                        </div>
                        <h1 className="stock-analysis-page__dh-hero-title">
                          {backendSupplyOverview?.gateLabel ??
                            `门控 ${localizeMarketDataStatus(strategyPayload?.market_gate.state)}`}
                          {" · "}
                          {decisionSummary.exposureLabel}
                        </h1>
                        <div
                          className="flex flex-wrap gap-1.5 font-semibold text-[color:var(--sa-dh-ink)]"
                          aria-label="下一步复核状态"
                          title={decisionSummary.nextReviewAction}
                        >
                          {reviewQueue[0] ? (
                            <>
                              <span className="inline-flex items-center gap-1.5 rounded-md border border-primary-100 bg-white px-2 py-1 text-xs">
                                <StockOutlined aria-hidden="true" /> 下一步 {reviewQueue[0].stockName}
                              </span>
                              <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-white px-2 py-1 text-xs">
                                <BarChartOutlined aria-hidden="true" /> 距观察 {reviewQueue[0].distanceToBreakoutPct}
                              </span>
                            </>
                          ) : (
                            <>
                              <span className="inline-flex items-center gap-1.5 rounded-md border border-warning-200 bg-white px-2 py-1 text-xs text-warning-700">
                                <StockOutlined aria-hidden="true" /> 复核 {reviewQueue.length}
                              </span>
                              <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-white px-2 py-1 text-xs">
                                <DatabaseOutlined aria-hidden="true" /> 多因子 {factorScreenPayload?.candidate_count ?? 0}
                              </span>
                              <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-white px-2 py-1 text-xs">
                                <ThunderboltOutlined aria-hidden="true" /> 共振 {consensusHitCount}
                              </span>
                            </>
                          )}
                        </div>
                        <div className="stock-analysis-page__dh-hero-status-strip" aria-label="市场门控状态">
                          {[
                            dailyJudgmentStrip.gateChip,
                            dailyJudgmentStrip.exposureChip,
                            dailyJudgmentStrip.strongestSectorChip,
                            dailyJudgmentStrip.weakestSectorChip,
                            decisionSummary.dataFreshnessLabel,
                            decisionSummary.boundaryLabel,
                          ].map((label) => (
                            <span key={label}>{label}</span>
                          ))}
                        </div>
                      </div>
                      <aside className="stock-analysis-page__dh-hero-side" aria-label="首屏状态摘要">
                        <span>
                          <SafetyCertificateOutlined aria-hidden="true" />
                          <small>门控</small>
                          <strong>{backendSupplyOverview?.conditionLabel ?? marketState.passedLabel}</strong>
                        </span>
                        <span>
                          <DatabaseOutlined aria-hidden="true" />
                          <small>边界</small>
                          <strong>{backendSupplyOverview?.dataGapLabel ?? decisionSummary.boundaryLabel}</strong>
                        </span>
                        <span>
                          <LineChartOutlined aria-hidden="true" />
                          <small>下一步</small>
                          <strong>{reviewQueue[0]?.stockName ?? "复核队列"}</strong>
                        </span>
                      </aside>
                    </div>

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

                    <details className="stock-analysis-page__dh-details">
                      <summary data-testid="stock-analysis-supply-details-toggle">
                        <span className="flex items-center gap-2">
                          <span className="text-[color:var(--sa-dh-blue)] group-open:rotate-90">▸</span>
                          供数闭环
                        </span>
                        {closedLoopSummary ? (
                          <strong className="stock-analysis-page__dh-pill">
                            {closedLoopSummary.referenceRating.label}
                          </strong>
                        ) : null}
                      </summary>
                      <div className="mt-3 space-y-3 px-1">
                      <div
                      className="stock-analysis-page__supply-kpi-row"
                      aria-label="供数首屏摘要"
                    >
                      <article className="stock-analysis-page__supply-kpi-card">
                        <div className="stock-analysis-page__mini-panel-head">
                          <strong>
                            <StatusIcon>{FIRST_SCREEN_ICONS[0]}</StatusIcon>
                            板块供数
                          </strong>
                          <span>{backendSupplyOverview?.sectorSupplyValueLabel ?? "0"}</span>
                        </div>
                        <div
                          className="stock-analysis-page__mini-chart"
                          data-testid="stock-analysis-sector-mini-chart"
                          aria-label="板块供数图"
                        >
                          {sectorChartRows.length > 0 ? (
                            <ReactECharts
                              option={sectorMiniChartOption}
                              className="stock-analysis-page__echart stock-analysis-page__echart--mini-bar"
                              opts={{ renderer: "canvas" }}
                              notMerge
                              lazyUpdate
                            />
                          ) : (
                            <span className="stock-analysis-page__empty stock-analysis-page__empty--signal">-</span>
                          )}
                        </div>
                      </article>
                      <article className="stock-analysis-page__supply-kpi-card">
                        <div className="stock-analysis-page__mini-panel-head">
                          <strong>
                            <StatusIcon>{FIRST_SCREEN_ICONS[1]}</StatusIcon>
                            规则就绪
                          </strong>
                          <span>{backendSupplyOverview?.readinessValueLabel ?? "0/0"}</span>
                        </div>
                        <div
                          className="stock-analysis-page__mini-chart"
                          data-testid="stock-analysis-review-mini-chart"
                          aria-label="规则就绪分布图"
                        >
                          {readinessChartRows.length > 0 ? (
                            <ReactECharts
                              option={readinessMiniChartOption}
                              className="stock-analysis-page__echart stock-analysis-page__echart--mini-bar"
                              opts={{ renderer: "canvas" }}
                              notMerge
                              lazyUpdate
                            />
                          ) : null}
                        </div>
                      </article>
                      <article className="stock-analysis-page__supply-kpi-card">
                        <div className="stock-analysis-page__mini-panel-head">
                          <strong>
                            <StatusIcon>{FIRST_SCREEN_ICONS[2]}</StatusIcon>
                            输出可用
                          </strong>
                          <span>{backendSupplyOverview?.supportedValueLabel ?? "0"}</span>
                        </div>
                        <div
                          className="stock-analysis-page__mini-chart"
                          data-testid="stock-analysis-event-mini-chart"
                          aria-label="输出可用分布图"
                        >
                          {outputChartRows.some((row) => row.value > 0) ? (
                            <ReactECharts
                              option={outputMiniChartOption}
                              className="stock-analysis-page__echart stock-analysis-page__echart--mini-stack"
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
                              <strong>{backendSupplyOverview.candidateSupplyValueLabel}</strong>
                            </div>
                            <div>
                              <span>阻断</span>
                              <strong>{backendSupplyOverview.unsupportedValueLabel}</strong>
                              {primaryUnsupportedOutput ? (
                                <small title={localizeStockBackendText(primaryUnsupportedOutput.reason, primaryUnsupportedOutput.key)}>
                                  {outputKeyLabel(primaryUnsupportedOutput.key)}
                                </small>
                              ) : null}
                            </div>
                          </div>
                        ) : null}
                      </article>
                      <article className="stock-analysis-page__supply-kpi-card">
                        <div className="stock-analysis-page__mini-panel-head">
                          <strong>
                            <StatusIcon>{FIRST_SCREEN_ICONS[3]}</StatusIcon>
                            风险供数
                          </strong>
                          <span>{backendSupplyOverview?.riskSupplyValueLabel ?? "0"}</span>
                        </div>
                        <div
                          className="stock-analysis-page__mini-chart"
                          data-testid="stock-analysis-risk-mini-chart"
                          aria-label="风险供数分布图"
                        >
                          {riskSupplyChartRows.some((row) => row.value > 0) ? (
                            <ReactECharts
                              option={riskSupplyMiniChartOption}
                              className="stock-analysis-page__echart stock-analysis-page__echart--mini-stack"
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
                                {backendSupplyOverview.risk?.position_count ?? 0}
                              </strong>
                            </div>
                            <div>
                              <span>触发</span>
                              <strong className="stock-analysis-page__tabular">
                                {backendSupplyOverview.risk?.signal_count ?? 0}
                              </strong>
                            </div>
                            <div>
                              <span>观察</span>
                              <strong className="stock-analysis-page__tabular">
                                {backendSupplyOverview.risk?.watch_items?.length ?? 0}
                              </strong>
                            </div>
                            {primaryDataGap ? (
                              <div>
                                <span>缺口</span>
                                <strong>{backendSupplyOverview.dataGapValueLabel}</strong>
                                <small title={localizeStockBackendText(primaryDataGap.evidence, primaryDataGap.input_family)}>
                                  {dataGapFamilyLabel(primaryDataGap.input_family)}
                                </small>
                              </div>
                            ) : null}
                          </div>
                        ) : null}
                      </article>
                    </div>

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
                                  {cycleInputLabel(item.key) || item.title}
                                </span>
                                <strong className="text-right text-[11px] leading-tight text-neutral-900">
                                  {statusLabel(item.status)}
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
                                  {dataGapFamilyLabel(item.input_family)}
                                </span>
                                <strong className="text-right text-[11px] leading-tight text-neutral-900">
                                  {statusLabel(item.status)}
                                </strong>
                              </div>
                            ))}
                          </div>
                        </DataStatusStrip>
                      ) : null}
                      <div
                        className="grid grid-cols-2 gap-0 overflow-hidden rounded-md border border-neutral-200 bg-neutral-50 sm:grid-cols-3 xl:grid-cols-6"
                        aria-label="供数摘要"
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
                          <strong className="stock-analysis-page__tabular col-start-2 text-sm">
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
                                  {localizeStockBackendText(warning)}
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
                  <section data-testid="stock-analysis-kpi-section" aria-label="选股快照">
                    <p className="stock-analysis-page__visually-hidden">选股快照</p>
                    <div
                      className="stock-analysis-page__dh-kpi-strip"
                      data-testid="stock-analysis-kpi-strip"
                    >
                    {kpiStrip.map((item) => (
                      <EquityKpiCard
                        key={item.key}
                        kpiKey={item.key}
                        label={item.label}
                        value={item.value}
                        deltaText={item.detail}
                        deltaTone={kpiToneToDelta(item.tone)}
                        gaugeValue={item.gaugeValue}
                        testId={`stock-analysis-kpi-${item.key}`}
                      />
                    ))}
                    </div>
                  </section>
                ) : null}

                <div
                  className="stock-analysis-page__stock-selection-stack"
                  data-testid="stock-analysis-stock-selection"
                >
                  {strategyLensItems.length > 0 ? (
                    <section
                      className="stock-analysis-page__strategy-lens"
                      aria-label="策略选股概览"
                      data-testid="stock-analysis-strategy-lens"
                    >
                      <p className="stock-analysis-page__visually-hidden">策略选股概览</p>
                      <div className="stock-analysis-page__strategy-lens-grid">
                        {strategyLensItems.map((item) => (
                          <button
                            key={item.key}
                            type="button"
                            className="stock-analysis-page__strategy-lens-card"
                            data-tone={item.tone}
                            data-testid={`stock-analysis-strategy-lens-${item.key}`}
                            onClick={() => scrollToStockSection(item.scrollTarget)}
                          >
                            <span className="stock-analysis-page__strategy-lens-label">{item.label}</span>
                            <strong className="stock-analysis-page__strategy-lens-value">{item.value}</strong>
                            <small className="stock-analysis-page__strategy-lens-detail">{item.detail}</small>
                            {item.progress != null ? (
                              <progress
                                className="stock-analysis-page__strategy-lens-meter"
                                max={100}
                                value={Math.max(4, item.progress * 100)}
                                aria-label={`${item.label} 进度`}
                              />
                            ) : null}
                          </button>
                        ))}
                      </div>
                    </section>
                  ) : null}

                  <section
                    className={SA_FIRST_CARD}
                    id="stock-analysis-review-queue"
                    data-testid="stock-analysis-review-queue"
                  >
                <div className={SA_SECTION_HEAD}>
                  <div className="min-w-0">
                    <p className={SA_SECTION_EYEBROW}>今日待复核</p>
                    <h2 className={SA_CARD_TITLE}>复核队列</h2>
                    <p className={SA_SECTION_DESC}>
                      {reviewQueueUsesHybridFusion ? "融合优先 · 边界复核" : "候选排序 · 边界复核"}
                    </p>
                  </div>
                  <span className={SA_PILL}>
                    {reviewQueueUsesHybridFusion ? "融合策略 / 复核队列" : "候选 / 复核队列"}
                  </span>
                </div>

                <div
                  className="stock-analysis-page__review-workbench-strip"
                  data-testid="stock-analysis-review-workbench-strip"
                  aria-label="复核工作台摘要"
                >
                  <div>
                    <DatabaseOutlined aria-hidden="true" />
                    <span>队列</span>
                    <strong className="stock-analysis-page__tabular">{filteredCandidates.length}/{reviewQueue.length}</strong>
                  </div>
                  <div>
                    <StockOutlined aria-hidden="true" />
                    <span>首位</span>
                    <strong>{selectedSectorLeadCandidate?.stockName ?? "待补"}</strong>
                  </div>
                  <div>
                    <BarChartOutlined aria-hidden="true" />
                    <span>距观察</span>
                    <strong className="stock-analysis-page__tabular">
                      {selectedSectorLeadCandidate?.distanceToBreakoutPct ?? "-"}
                    </strong>
                  </div>
                  <div>
                    <SafetyCertificateOutlined aria-hidden="true" />
                    <span>证据</span>
                    <strong className="stock-analysis-page__tabular">
                      {selectedSectorLeadCandidate
                        ? selectedSectorLeadCandidate.primaryEvidence.length +
                          selectedSectorLeadCandidate.supportingEvidence.length
                        : 0}
                    </strong>
                  </div>
                </div>

                {reviewQueue.length > 0 ? (
                  <div
                    className="mb-2 flex flex-wrap items-center gap-1.5 rounded-md border border-neutral-100 bg-neutral-50 px-2 py-1.5"
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
                    <div
                      className="ml-auto flex min-w-[180px] flex-wrap items-center justify-end gap-x-2 gap-y-0.5 text-xs text-neutral-500"
                      data-testid="stock-review-filter-status"
                    >
                      <span>范围</span>
                      <strong className="text-sm text-neutral-900">{selectedSectorLabel ?? "全部行业"}</strong>
                      <small>
                        显示 {filteredCandidates.length} / {reviewQueue.length} 个候选
                        {reviewQueueUsesHybridFusion ? " · 融合策略候选优先" : ""}
                      </small>
                    </div>
                  </div>
                ) : null}

                {sectorRowsFull.length > 0 ? (
                  <div
                    className="stock-analysis-page__sector-review-link"
                    aria-live="polite"
                    data-tone={sectorLinkTone}
                    data-testid="stock-analysis-sector-review-link"
                    title={`${sectorLinkSummary} ${sectorLinkFocus}`}
                  >
                    <span aria-hidden="true">
                      <BarChartOutlined />
                    </span>
                    <strong>{sectorLinkSummary}</strong>
                    <small>{sectorLinkFocus}</small>
                  </div>
                ) : null}

                {reviewQueueChartRows.length > 0 ? (
                  <div
                    className="mb-2 grid gap-2 border-y border-neutral-100 bg-neutral-50/70 px-2 py-2 md:grid-cols-[minmax(0,1fr)_minmax(160px,220px)]"
                    data-testid="stock-analysis-review-queue-ranking-chart"
                    aria-label="复核队列排名图"
                  >
                    <div className="min-w-0">
                      <div className="mb-1 flex items-center justify-between gap-2 text-xs">
                        <strong className="inline-flex items-center gap-1 text-neutral-900">
                          <BarChartOutlined aria-hidden="true" /> 队列排序
                        </strong>
                        <span className="font-semibold text-neutral-500">前 {reviewQueueChartRows.length}</span>
                      </div>
                      <ReactECharts
                        option={reviewQueueRankingOption}
                        className="stock-analysis-page__echart stock-analysis-page__echart--review-queue"
                        opts={{ renderer: "canvas" }}
                        notMerge
                        lazyUpdate
                      />
                    </div>
                    <div className="grid grid-cols-3 gap-1 md:grid-cols-1">
                      {reviewQueueChartRows.slice(0, 3).map((row) => (
                        <div key={row.key} className="min-w-0 border-l border-neutral-200 pl-2 text-xs">
                          <strong className="block truncate text-neutral-900">{row.label}</strong>
                          <span className="block truncate text-neutral-500">{row.detail}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {reviewQueue.length === 0 ? (
                  <div
                    className="stock-analysis-page__review-empty-panel"
                    role="status"
                    data-testid="stock-analysis-review-queue-empty"
                    title={reviewQueueEmptyState?.detail ?? "查看观察池与板块"}
                  >
                    <div className="grid w-full gap-2 sm:grid-cols-3">
                      <CompactStatusTile
                        icon={<StockOutlined />}
                        label="队列"
                        value="0"
                        tone="warning"
                        className="w-full bg-white"
                        title={reviewQueueEmptyState?.headline ?? "暂无主候选"}
                      />
                      <CompactStatusTile
                        icon={<DatabaseOutlined />}
                        label="多因子"
                        value={factorScreenPayload?.candidate_count ?? 0}
                        className="w-full bg-white"
                      />
                      <CompactStatusTile
                        icon={<BarChartOutlined />}
                        label="板块"
                        value={sectorRowsFull.length}
                        className="w-full bg-white"
                      />
                    </div>
                  </div>
                ) : filteredCandidates.length === 0 ? (
                  <CompactStatusTile
                    icon={<BarChartOutlined />}
                    label="行业筛选"
                    value="0 候选"
                    tone="warning"
                    testId="stock-analysis-review-queue-filter-empty"
                  />
                ) : (
                  <div className="stock-analysis-page__review-candidate-grid grid grid-cols-1 gap-2 lg:grid-cols-2">
                    {filteredCandidates.map((card) => {
                      const visibleEvidence = [...card.primaryEvidence, ...card.supportingEvidence].slice(0, 4);
                      const hiddenEvidenceCount =
                        card.primaryEvidence.length + card.supportingEvidence.length - visibleEvidence.length;

                      return (
                        <article
                          className="stock-analysis-page__review-candidate-card grid gap-2 rounded-md border border-neutral-200 bg-white px-3 py-2.5 transition-shadow hover:border-primary-200 hover:shadow-[0_0_0_1px_theme(colors.primary.200)]"
                          data-testid={`stock-candidate-${card.stockCode}`}
                          data-selected-sector={
                            sectorFilterSectorCode != null && card.sectorCode === sectorFilterSectorCode ? "true" : undefined
                          }
                          key={card.stockCode}
                        >
                          <div className="stock-analysis-page__review-row-head">
                            <strong className="stock-analysis-page__review-row-rank stock-analysis-page__tabular">
                              #{card.rank}
                            </strong>
                            <div className="min-w-0">
                              <h3 className="m-0 text-sm font-semibold text-neutral-900">{card.headline}</h3>
                              <p className="mt-0.5 text-[11px] text-neutral-500">
                                {card.stockName} · {card.stockCode} · {card.sectorName}
                              </p>
                            </div>
                            <div className="stock-analysis-page__review-row-metrics">
                              <span title={card.patternNote}>距 {card.distanceToBreakoutPct}</span>
                              <span>{card.primaryEvidence.length + card.supportingEvidence.length} 证据</span>
                              <Button
                                type="default"
                                size="small"
                                icon={<LineChartOutlined />}
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
                                <span className="sr-only">复核 </span>K 线
                              </Button>
                              <span className="rounded-full border border-primary-200 bg-primary-50 px-2 py-0.5 text-xs font-semibold text-primary-700">
                                观察
                              </span>
                            </div>
                          </div>
                          <p className="m-0 border-l-2 border-primary-500 pl-2 text-xs font-semibold leading-relaxed text-neutral-900">
                            {card.reviewFocus}
                          </p>
                          <div className="stock-analysis-page__review-candidate-evidence grid gap-1.5 sm:grid-cols-2">
                            {visibleEvidence.map((item, index) => (
                              <div
                                className="flex min-w-0 items-center gap-2 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1.5"
                                key={item.key}
                                title={`${item.label}: ${item.value}`}
                              >
                                <StatusIcon tone={index < card.primaryEvidence.length ? "positive" : "neutral"}>
                                  {index < card.primaryEvidence.length ? (
                                    <CheckCircleOutlined />
                                  ) : (
                                    <DatabaseOutlined />
                                  )}
                                </StatusIcon>
                                <span className="min-w-0 flex-1">
                                  <span className="block truncate text-[10px] font-medium text-neutral-500">
                                    {item.label}
                                  </span>
                                  <strong className="block truncate text-xs font-semibold text-neutral-900">
                                    {item.value}
                                  </strong>
                                </span>
                              </div>
                            ))}
                          </div>
                          <div className="stock-analysis-page__review-candidate-chips flex flex-wrap gap-1 text-xs">
                            <span className="inline-flex items-center gap-1 rounded-full border border-neutral-200 bg-white px-2 py-0.5 font-semibold text-neutral-600">
                              <SafetyCertificateOutlined aria-hidden="true" /> 边界 {card.boundaryEvidence.length}
                            </span>
                            <span
                              className="inline-flex min-w-0 max-w-full items-center gap-1 rounded-full border border-danger-100 bg-danger-50 px-2 py-0.5 font-semibold text-danger-700"
                              title={card.invalidationFocus}
                            >
                              <ClockCircleOutlined aria-hidden="true" />
                              <span className="truncate">失效 {compactText(card.invalidationFocus, 24)}</span>
                            </span>
                            {hiddenEvidenceCount > 0 ? (
                              <span className="inline-flex items-center rounded-full border border-neutral-200 bg-neutral-50 px-2 py-0.5 font-semibold text-neutral-500">
                                +{hiddenEvidenceCount} 证据
                              </span>
                            ) : null}
                          </div>
                          <Collapse
                            ghost
                            bordered={false}
                            destroyOnHidden
                            className="stock-analysis-page__candidate-collapse"
                            items={[
                              {
                                key: "evidence",
                                label: (
                                  <span className="inline-flex items-center gap-1">
                                    <SafetyCertificateOutlined aria-hidden="true" />
                                    <span aria-hidden="true">证据</span>
                                    <span className="sr-only">证据明细</span>
                                    <span className="rounded border border-neutral-200 bg-neutral-50 px-1 text-[10px] text-neutral-500">
                                      {card.primaryEvidence.length + card.supportingEvidence.length}
                                    </span>
                                  </span>
                                ),
                                children: (
                                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                                    <div>
                                      <h4 className="mb-2 text-sm font-semibold text-neutral-900">进入依据</h4>
                                      <ul className="m-0 grid list-none gap-1 p-0 text-sm text-neutral-600">
                                        {[...card.primaryEvidence, ...card.supportingEvidence].map((item) => (
                                          <li key={item.key}>
                                            <strong className="text-neutral-900">{item.label}</strong>：{item.value}
                                          </li>
                                        ))}
                                      </ul>
                                    </div>
                                    <div>
                                      <h4 className="mb-2 text-sm font-semibold text-neutral-900">边界待补</h4>
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
                                ),
                              },
                              {
                                key: "raw",
                                label: (
                                  <span className="inline-flex items-center gap-1">
                                    <DatabaseOutlined aria-hidden="true" />
                                    <span aria-hidden="true">指标</span>
                                    <span className="sr-only">指标明细</span>
                                    <span className="rounded border border-neutral-200 bg-neutral-50 px-1 text-[10px] text-neutral-500">
                                      {card.rawFields.length}
                                    </span>
                                  </span>
                                ),
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
                      );
                    })}
                  </div>
                )}
              </section>

                  <section
                    className={SA_FIRST_CARD}
                    id="stock-analysis-consensus-first-screen"
                    data-testid="stock-analysis-consensus-first-screen"
                  >
                    <div className={SA_SECTION_HEAD}>
                      <div className="min-w-0">
                        <p className={SA_SECTION_EYEBROW}>多策略共振</p>
                        <h2 className={SA_CARD_TITLE}>策略共振选股</h2>
                        <p className={SA_SECTION_DESC}>
                          共振命中 · 三重优先
                        </p>
                      </div>
                      <span className={SA_PILL}>
                        共振 {consensusHitCount} · 去重 {consensusSummary.totalUnion}
                      </span>
                    </div>

                    <div
                      className="stock-analysis-page__consensus-workbench-strip"
                      data-testid="stock-analysis-consensus-workbench-strip"
                      aria-label="策略共振摘要"
                    >
                      <div data-tone={consensusHitCount > 0 ? "positive" : "neutral"}>
                        <ThunderboltOutlined aria-hidden="true" />
                        <span>共振</span>
                        <strong className="stock-analysis-page__tabular">{consensusHitCount}</strong>
                      </div>
                      <div>
                        <DatabaseOutlined aria-hidden="true" />
                        <span>去重</span>
                        <strong className="stock-analysis-page__tabular">{consensusSummary.totalUnion}</strong>
                      </div>
                      <div>
                        <LineChartOutlined aria-hidden="true" />
                        <span>趋势</span>
                        <strong className="stock-analysis-page__tabular">{consensusSummary.strategyCounts.livermore}</strong>
                      </div>
                      <div>
                        <BarChartOutlined aria-hidden="true" />
                        <span>多因子</span>
                        <strong className="stock-analysis-page__tabular">{consensusSummary.strategyCounts.factor_screen}</strong>
                      </div>
                    </div>

                    {!consensusSummary.hasAnyStrategy ? (
                      <p className="stock-analysis-page__empty">{consensusReviewPanelSummary?.detail ?? "候选 0"}</p>
                    ) : consensusFirstScreenItems.length === 0 ? (
                      <div
                        className="grid gap-2 sm:grid-cols-3"
                        role="status"
                        data-testid="stock-analysis-consensus-empty-scan"
                        aria-label="暂无多策略共振"
                      >
                        <CompactStatusTile icon={<ThunderboltOutlined />} label="共振" value={consensusHitCount} />
                        <CompactStatusTile icon={<DatabaseOutlined />} label="去重" value={consensusSummary.totalUnion} />
                        <CompactStatusTile
                          icon={<LineChartOutlined />}
                          label="复核"
                          value="队列"
                          tone="positive"
                          className="border-primary-100 bg-primary-50"
                        />
                      </div>
                    ) : (
                      <div className="stock-analysis-page__consensus-first-list">
                        {consensusFirstScreenItems.map((row) => {
                          const isTriple = row.consensusCount >= 3;
                          return (
                            <button
                              key={row.stockCode}
                              type="button"
                              className={`stock-analysis-page__consensus-first-row stock-analysis-page__row--clickable${
                                isTriple ? " stock-analysis-page__consensus-first-row--triple" : ""
                              }`}
                              data-testid={`consensus-first-row-${row.stockCode}`}
                              onClick={() => {
                                setDetailSelection({
                                  code: row.stockCode,
                                  name: row.stockName,
                                  source: "consensus",
                                  livermoreRank: row.livermoreRank,
                                  meanReversionRank: row.meanReversionRank,
                                  factorScreenRank: row.factorScreenRank,
                                  hybridFusionRank: row.hybridFusionRank,
                                });
                              }}
                            >
                              <div className="stock-analysis-page__consensus-first-main">
                                <strong>
                                  {row.stockName}{" "}
                                  <small className="stock-analysis-page__tabular">{row.stockCode}</small>
                                </strong>
                                <span>{row.sectorName}</span>
                              </div>
                              <div className="stock-analysis-page__consensus-first-badges">
                                <span
                                  className={`stock-analysis-page__consensus-badge${
                                    isTriple ? " stock-analysis-page__consensus-badge--triple" : ""
                                  }`}
                                >
                                  {row.consensusCount} 策略共振
                                </span>
                                {row.strategies.map((kind) => (
                                  <span key={kind} className="stock-analysis-page__consensus-badge">
                                    {consensusStrategyLabel(kind)}
                                  </span>
                                ))}
                              </div>
                              <div className="stock-analysis-page__consensus-ranks">
                                {row.hybridFusionRank != null && <span>融合 #{row.hybridFusionRank}</span>}
                                {row.livermoreRank != null && <span>趋势 #{row.livermoreRank}</span>}
                                {row.factorScreenRank != null && <span>多因子 #{row.factorScreenRank}</span>}
                                {row.meanReversionRank != null && <span>超跌 #{row.meanReversionRank}</span>}
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </section>
                </div>
                </div>

                  <section
                    className={`${SA_FIRST_CARD} stock-analysis-page__lower-data-band`}
                    id="stock-analysis-observation-preview"
                    data-testid="stock-analysis-observation-preview"
                  >
                    <div className={SA_SECTION_HEAD}>
                      <div className="min-w-0">
                        <p className={SA_SECTION_EYEBROW}>多策略观察池</p>
                        <h2 className={SA_CARD_TITLE}>因子 / 超跌观察池</h2>
                        <div className="stock-analysis-page__lower-signal-strip" aria-label="观察池状态">
                          <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-semibold text-neutral-600">
                            <DatabaseOutlined aria-hidden="true" /> 多因子 {factorScreenPayload?.candidate_count ?? 0}
                          </span>
                          <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-semibold text-neutral-600">
                            <FireOutlined aria-hidden="true" /> 超跌{" "}
                            {meanReversionMarketActive ? meanReversionPayload?.candidate_count ?? 0 : "暂停"}
                          </span>
                        </div>
                      </div>
                      <span className={SA_PILL}>
                        多因子 {factorScreenPayload?.candidate_count ?? 0} · 超跌{" "}
                        {meanReversionMarketActive ? meanReversionPayload?.candidate_count ?? 0 : "暂停"}
                      </span>
                    </div>

                    <div className="stock-analysis-page__observation-preview-grid">
                      <div className="stock-analysis-page__observation-preview-panel">
                        <h3>多因子前 {factorPreviewItems.length || 0}</h3>
                        {!factorScreenPayload ? (
                          <CompactStatusTile
                            icon={<DatabaseOutlined />}
                            label="多因子"
                            value="未就绪"
                            tone="warning"
                            testId="stock-analysis-factor-preview-empty"
                          />
                        ) : factorPreviewItems.length === 0 ? (
                          <CompactStatusTile
                            icon={<DatabaseOutlined />}
                            label="多因子"
                            value="0 候选"
                            testId="stock-analysis-factor-preview-empty"
                          />
                        ) : (
                          <div className="stock-analysis-page__table-wrap">
                            <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                              <thead>
                                <tr>
                                  <th scope="col">#</th>
                                  <th scope="col">股票</th>
                                  <th scope="col">行业</th>
                                  <th scope="col">因子分</th>
                                </tr>
                              </thead>
                              <tbody>
                                {factorPreviewItems.map((row) => (
                                  <tr
                                    key={row.stock_code}
                                    className="stock-analysis-page__row--clickable"
                                    data-testid={`factor-preview-row-${row.stock_code}`}
                                    onClick={() => {
                                      const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stock_code);
                                      setDetailSelection({
                                        code: row.stock_code,
                                        name: row.stock_name,
                                        sectorCode: row.sector_code,
                                        sectorName: row.sector_name,
                                        source: "factor_screen",
                                        livermoreRank: ranks.livermoreRank,
                                        meanReversionRank: ranks.meanReversionRank,
                                        factorScreenRank: row.rank,
                                        hybridFusionRank: ranks.hybridFusionRank,
                                      });
                                    }}
                                  >
                                    <td className="stock-analysis-page__table-number">{row.rank}</td>
                                    <td>
                                      {row.stock_name}
                                      <small className="stock-analysis-page__tabular"> {row.stock_code}</small>
                                    </td>
                                    <td>{row.sector_name}</td>
                                    <td className="stock-analysis-page__table-number">{row.score.toFixed(4)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                        {factorScreenCoverageNote ? (
                          <p className="stock-analysis-page__footnote">{factorScreenCoverageNote}</p>
                        ) : null}
                      </div>

                      <div className="stock-analysis-page__observation-preview-panel">
                        <h3>超跌反弹{meanReversionMarketActive ? "前列" : ""}</h3>
                        {!meanReversionMarketActive ? (
                          <CompactStatusTile
                            icon={<FireOutlined />}
                            label="超跌"
                            value="暂停"
                            tone="warning"
                            testId="stock-analysis-mean-reversion-preview-empty"
                          />
                        ) : !meanReversionPayload ? (
                          <CompactStatusTile
                            icon={<FireOutlined />}
                            label="超跌"
                            value="未就绪"
                            tone="warning"
                            testId="stock-analysis-mean-reversion-preview-empty"
                          />
                        ) : meanReversionPreviewItems.length === 0 ? (
                          <CompactStatusTile
                            icon={<FireOutlined />}
                            label="超跌"
                            value="0 候选"
                            testId="stock-analysis-mean-reversion-preview-empty"
                          />
                        ) : (
                          <ul className="stock-analysis-page__list stock-analysis-page__list--compact">
                            {meanReversionPreviewItems.map((row) => (
                              <li
                                key={row.stock_code}
                                className="stock-analysis-page__mean-reversion-row stock-analysis-page__row--clickable"
                                data-testid={`mean-reversion-preview-row-${row.stock_code}`}
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
                                <span>
                                  #{row.rank} {row.stock_name}{" "}
                                  <small className="stock-analysis-page__tabular">{row.stock_code}</small>
                                </span>
                                <span className="stock-analysis-page__mean-reversion-metrics">
                                  <span>{row.sector_name}</span>
                                  <span className="stock-analysis-page__mean-reversion-dd">
                                    20日回撤 {(row.drawdown_20d * 100).toFixed(1)}%
                                  </span>
                                  <span>得分 {row.score.toFixed(2)}</span>
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  </section>

                  <section
                    className={`${SA_FIRST_CARD} stock-analysis-page__lower-data-band`}
                    id="stock-analysis-theme-leaders-first-screen"
                    data-testid="stock-analysis-theme-leaders-first-screen"
                  >
                    <div className={SA_SECTION_HEAD}>
                      <div className="min-w-0">
                        <p className={SA_SECTION_EYEBROW}>题材突变</p>
                        <h2 className={SA_CARD_TITLE}>题材突破领涨股</h2>
                        <div className="stock-analysis-page__lower-signal-strip" aria-label="题材突破状态">
                          <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-semibold text-neutral-600">
                            <FireOutlined aria-hidden="true" /> 题材 {themeBreakoutCards.length}
                          </span>
                          <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-semibold text-neutral-600">
                            <StockOutlined aria-hidden="true" /> 领涨 {themeLeaderPreviewItems.length}
                          </span>
                        </div>
                      </div>
                      <span className={SA_PILL}>
                        {themeBreakoutCards.length > 0
                          ? `${themeLeaderPreviewItems.length} 只 · ${themeBreakoutCards.length} 题材`
                          : "题材雷达待补"}
                      </span>
                    </div>

                    {themeLeaderPreviewItems.length === 0 ? (
                      <CompactStatusTile
                        icon={<FireOutlined />}
                        label="题材"
                        value={themeBreakoutUnsupported ? "待补" : "0 领涨"}
                        detail={themeBreakoutBlockerLabel ?? undefined}
                        tone={themeBreakoutUnsupported ? "warning" : "neutral"}
                        testId="stock-analysis-theme-leader-empty"
                        title={themeBreakoutBlockerText ?? "当前无题材突破领涨股"}
                      />
                    ) : (
                      <div className="stock-analysis-page__table-wrap">
                        <table className="stock-analysis-page__table stock-analysis-page__table--dense stock-analysis-page__theme-leaders-table">
                          <thead>
                            <tr>
                              <th scope="col">题材</th>
                              <th scope="col">领涨股</th>
                              <th scope="col">涨跌</th>
                              <th scope="col">换手</th>
                              <th scope="col">收盘强度</th>
                              <th scope="col">标签</th>
                            </tr>
                          </thead>
                          <tbody>
                            {themeLeaderPreviewItems.map((row) => (
                              <tr
                                key={`${row.themeName}:${row.stockCode}`}
                                className="stock-analysis-page__row--clickable"
                                data-testid={`theme-leader-first-row-${row.stockCode}`}
                                onClick={() => {
                                  const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stockCode);
                                  setDetailSelection({
                                    code: row.stockCode,
                                    name: row.stockName,
                                    livermoreRank: ranks.livermoreRank,
                                    meanReversionRank: ranks.meanReversionRank,
                                    factorScreenRank: ranks.factorScreenRank,
                                    hybridFusionRank: ranks.hybridFusionRank,
                                  });
                                }}
                              >
                                <td>
                                  #{row.themeRank} {row.themeName}
                                </td>
                                <td>
                                  {row.stockName}
                                  <small className="stock-analysis-page__tabular"> {row.stockCode}</small>
                                </td>
                                <td className="stock-analysis-page__table-number">{row.pctChange}</td>
                                <td className="stock-analysis-page__table-number">{row.turn}</td>
                                <td className="stock-analysis-page__table-number">{row.closeStrength}</td>
                                <td>{row.tags.join(" / ") || "复核"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </section>

                  <section
                    className={`${SA_FIRST_CARD} stock-analysis-page__lower-data-band`}
                    id="stock-analysis-sector-heavyweights-first-screen"
                    data-testid="stock-analysis-sector-heavyweights-first-screen"
                  >
                    <div className={SA_SECTION_HEAD}>
                      <div className="min-w-0">
                        <p className={SA_SECTION_EYEBROW}>板块结构</p>
                        <h2 className={SA_CARD_TITLE}>权重股摘要</h2>
                        <div className="stock-analysis-page__lower-signal-strip" aria-label="权重股样本状态">
                          <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-semibold text-neutral-600">
                            <BarChartOutlined aria-hidden="true" /> 前 {sectorHeavyweightPreview?.sectorLimit ?? 0}
                          </span>
                          <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-semibold text-neutral-600">
                            <StockOutlined aria-hidden="true" /> 样本{" "}
                            {sectorHeavyweightPreview?.totalSampleCount ?? 0}
                          </span>
                        </div>
                      </div>
                      <span className={SA_PILL}>
                        {sectorHeavyweightPreview
                          ? sectorHeavyweightPreview.sectorsWithSamples > 0
                            ? `${sectorHeavyweightPreview.sectorsWithSamples}/${sectorHeavyweightPreview.sectorLimit} 板块 · ${sectorHeavyweightPreview.totalSampleCount} 只样本`
                            : `前 ${sectorHeavyweightPreview.sectorLimit} 板块 · 观察池未覆盖`
                          : "板块待补"}
                      </span>
                    </div>

                    {!sectorHeavyweightPreview || sectorHeavyweightPreview.rows.length === 0 ? (
                      <CompactStatusTile
                        icon={<BarChartOutlined />}
                        label="板块强弱"
                        value="未就绪"
                        tone="warning"
                        testId="stock-analysis-sector-heavyweight-empty"
                      />
                    ) : sectorHeavyweightRows.length === 0 ? (
                      <CompactStatusTile
                        icon={<StockOutlined />}
                        label={`前 ${sectorHeavyweightPreview.sectorLimit}`}
                        value="0 命中"
                        testId="stock-analysis-sector-heavyweight-empty"
                      />
                    ) : (
                      <>
                        {sectorHeavyweightPreview.uncoveredSectorCount > 0 ? (
                          <div
                            className="mb-2 inline-flex items-center gap-2 rounded-md border border-warning-200 bg-warning-50 px-2.5 py-1.5 text-xs font-semibold text-warning-700 stock-analysis-page__sector-heavyweight-coverage"
                            data-testid="stock-analysis-sector-heavyweight-coverage"
                            role="status"
                            aria-label={`权重股样本缺口 ${sectorHeavyweightPreview.uncoveredSectorCount}`}
                          >
                            <StatusIcon tone="warning">
                              <DatabaseOutlined />
                            </StatusIcon>
                            缺口 {sectorHeavyweightPreview.uncoveredSectorCount}
                          </div>
                        ) : null}
                        <div className="stock-analysis-page__sector-heavyweight-grid">
                          {sectorHeavyweightRows.map((sector) => (
                            <article
                              key={sector.sectorCode}
                              className="stock-analysis-page__sector-heavyweight-card"
                              data-testid={`sector-heavyweight-card-${sector.sectorCode}`}
                            >
                              <header className="stock-analysis-page__sector-heavyweight-head">
                                <strong>
                                  #{sector.sectorRank} {sector.sectorName}
                                </strong>
                                <span>
                                  板块 {sector.sectorPctChange} · 得分 {sector.sectorScore} · 样本 {sector.stocks.length}
                                </span>
                              </header>
                              <ul className="stock-analysis-page__sector-heavyweight-list">
                                {sector.stocks.slice(0, 1).map((stock) => (
                                  <li
                                      key={stock.stockCode}
                                      className="stock-analysis-page__sector-heavyweight-row stock-analysis-page__row--clickable"
                                      data-testid={`sector-heavyweight-row-${sector.sectorCode}-${stock.stockCode}`}
                                      onClick={() => {
                                        const ranks = lookupStockStrategyRanks(
                                          strategyPayload ?? null,
                                          stock.stockCode,
                                        );
                                        setDetailSelection({
                                          code: stock.stockCode,
                                          name: stock.stockName,
                                          sectorCode: sector.sectorCode,
                                          sectorName: sector.sectorName,
                                          livermoreRank: ranks.livermoreRank,
                                          meanReversionRank: ranks.meanReversionRank,
                                          factorScreenRank: ranks.factorScreenRank,
                                          hybridFusionRank: ranks.hybridFusionRank,
                                        });
                                      }}
                                      role="button"
                                      tabIndex={0}
                                      onKeyDown={(event) => {
                                        if (event.key === "Enter" || event.key === " ") {
                                          event.preventDefault();
                                          const ranks = lookupStockStrategyRanks(
                                            strategyPayload ?? null,
                                            stock.stockCode,
                                          );
                                          setDetailSelection({
                                            code: stock.stockCode,
                                            name: stock.stockName,
                                            sectorCode: sector.sectorCode,
                                            sectorName: sector.sectorName,
                                            livermoreRank: ranks.livermoreRank,
                                            meanReversionRank: ranks.meanReversionRank,
                                            factorScreenRank: ranks.factorScreenRank,
                                            hybridFusionRank: ranks.hybridFusionRank,
                                          });
                                        }
                                      }}
                                    >
                                      <span className="stock-analysis-page__sector-heavyweight-main">
                                        <strong>{stock.stockName}</strong>
                                        <small className="stock-analysis-page__tabular">{stock.stockCode}</small>
                                      </span>
                                      <span className="stock-analysis-page__sector-heavyweight-metrics">
                                        <span>{stock.pctChange}</span>
                                        <span>换手 {stock.turn}</span>
                                        {stock.auxiliaryLabel ? (
                                          <span>{stock.auxiliaryLabel}</span>
                                        ) : (
                                          <span>收盘强度 {stock.closeStrength}</span>
                                        )}
                                        {stock.detailLabel ? <span>{stock.detailLabel}</span> : null}
                                      </span>
                                      <em>{stock.sourceLabel}</em>
                                    </li>
                                ))}
                              </ul>
                            </article>
                          ))}
                        </div>
                      </>
                    )}
                  </section>

                  <section
                    className={SA_FIRST_CARD}
                    id="stock-analysis-first-screen-analytics"
                    data-testid="stock-analysis-first-screen-analytics"
                  >
                    <div className={SA_SECTION_HEAD}>
                      <div className="min-w-0">
                        <p className={SA_SECTION_EYEBROW}>深度回测</p>
                        <h2 className={SA_CARD_TITLE}>回测诊断</h2>
                        <div className="mt-2 flex flex-wrap gap-1.5" aria-label="回测诊断状态">
                          <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-semibold text-neutral-600">
                            <ThunderboltOutlined aria-hidden="true" /> 共振 {consensusHitCount}
                          </span>
                          <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-semibold text-neutral-600">
                            <LineChartOutlined aria-hidden="true" /> 诊断{" "}
                            {firstScreenAnalyticsRequested ? "已载入" : "待查"}
                          </span>
                        </div>
                      </div>
                      <span className={SA_PILL}>
                        共振 {consensusHitCount} · 去重 {consensusSummary.totalUnion}
                      </span>
                    </div>

                    <Tabs
                      className="stock-analysis-page__analytics-tabs"
                      size="small"
                      activeKey={firstScreenAnalyticsTab}
                      onChange={handleFirstScreenAnalyticsTabChange}
                      items={[
                        {
                          key: "consensus",
                          label: "历史共振",
                          children: !consensusSummary.hasAnyStrategy ? (
                            <CompactStatusTile
                              icon={<ThunderboltOutlined />}
                              label="历史共振"
                              value="0"
                              testId="stock-analysis-consensus-first-screen-empty"
                            />
                          ) : consensusSummary.items.length === 0 ? (
                            <CompactStatusTile
                              icon={<ThunderboltOutlined />}
                              label="历史共振"
                              value="0"
                              testId="stock-analysis-consensus-first-screen-empty"
                            />
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
                                    data-testid={`first-screen-consensus-row-${row.stockCode}`}
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
                                        <span className="stock-analysis-page__tabular">{row.stockCode}</span>{" "}
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
                                  </li>
                                );
                              })}
                            </ul>
                          ),
                        },
                        {
                          key: "priority",
                          label: "策略优先级",
                          children: !firstScreenAnalyticsRequested ? (
                            <CompactStatusTile
                              icon={<LineChartOutlined />}
                              label="策略优先级"
                              value="待查"
                              testId="stock-analysis-priority-deferred"
                            />
                          ) : strategyScoreQuery.isLoading ? (
                            <p className="stock-analysis-page__empty">当前市场策略优先级加载中。</p>
                          ) : strategyScoreQuery.isError ? (
                            <p className="stock-analysis-page__notice">
                              当前市场策略优先级暂不可用：{strategyPanelErrorMessage(strategyScoreQuery.error)}
                            </p>
                          ) : strategyPriorityRows.length > 0 ? (
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
                                  {strategyPriorityRows.map((row) => (
                                    <tr
                                      key={`${row.market_state}:${row.signal_kind}`}
                                      data-testid={`first-screen-priority-row-${row.market_state}-${row.signal_kind}`}
                                    >
                                      <td>{strategyDisplayLabel(row.strategy_label, row.signal_kind)}</td>
                                      <td>{strategyPriorityStatusLabel(row.priority_label)}</td>
                                      <td className="stock-analysis-page__table-number">
                                        {formatPriorityScore(row.priority_score)}
                                      </td>
                                      {strategyBacktestHorizons.map((horizon) => (
                                        <td className="stock-analysis-page__table-number" key={horizon}>
                                          {backtestStatsText(row.stats[horizon])}
                                        </td>
                                      ))}
                                      <td>{strategyPriorityReasonLabel(row)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <CompactStatusTile
                              icon={<LineChartOutlined />}
                              label="策略优先级"
                              value="样本不足"
                              testId="stock-analysis-priority-empty"
                            />
                          ),
                        },
                        {
                          key: "optimization",
                          label: "优化诊断",
                          children: !firstScreenAnalyticsRequested ? (
                            <CompactStatusTile
                              icon={<SafetyCertificateOutlined />}
                              label="优化诊断"
                              value="待查"
                              testId="stock-analysis-optimization-deferred"
                            />
                          ) : strategyOptimizationQuery.isLoading ? (
                            <p className="stock-analysis-page__empty">优化诊断加载中。</p>
                          ) : strategyOptimizationQuery.isError ? (
                            <p className="stock-analysis-page__notice">
                              优化诊断暂不可用：{strategyPanelErrorMessage(strategyOptimizationQuery.error)}
                            </p>
                          ) : strategyOptimizationRows.length > 0 ? (
                            <div className="stock-analysis-page__table-wrap">
                              <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                                <thead>
                                  <tr>
                                    <th scope="col">策略</th>
                                    <th scope="col">复核状态</th>
                                    <th scope="col">T+5 收益</th>
                                    <th scope="col">按日等权</th>
                                    <th scope="col">原因</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {strategyOptimizationRows.map((row) => (
                                    <tr
                                      key={row.summary_key}
                                      data-testid={`first-screen-optimization-row-${row.summary_key}`}
                                    >
                                      <td>{strategyDisplayLabel(row.strategy_label, row.signal_kind)}</td>
                                      <td>{strategyPriorityStatusLabel(row.recommendation.priority_label)}</td>
                                      <td className="stock-analysis-page__table-number">
                                        {backtestStatsText(
                                          strategyOptimizationPrimaryStats(row, strategyOptimizationPayload),
                                        )}
                                      </td>
                                      <td className="stock-analysis-page__table-number">
                                        {strategyOptimizationDateWeightedText(row, strategyOptimizationPayload)}
                                      </td>
                                      <td>{strategyOptimizationReasonLabel(row)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <CompactStatusTile
                              icon={<SafetyCertificateOutlined />}
                              label="优化诊断"
                              value="0"
                              testId="stock-analysis-optimization-empty"
                            />
                          ),
                        },
                      ]}
                    />
                  </section>

                <div className="stock-analysis-page__dh-work-grid" data-testid="stock-analysis-first-screen-workbench">
                  <div className="flex flex-col gap-3" data-testid="stock-analysis-first-screen-primary">
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
                      {sectorRowsFull.length} 个板块 · 强弱对比
                    </p>
                  </div>
                  <span className={SA_PILL}>
                    {sectorRowsFull.length > 0 ? `${sectorRowsFull.length} 个板块` : "板块待补"}
                  </span>
                </div>

                {!sectorRankUnavailable(strategyPayload) ? (
                  <>
                    <div
                      className="stock-analysis-page__sector-workbench-strip"
                      data-testid="stock-analysis-sector-workbench-strip"
                      aria-label="板块强弱摘要"
                    >
                      <div>
                        <DatabaseOutlined aria-hidden="true" />
                        <span>板块</span>
                        <strong className="stock-analysis-page__tabular">{sectorRowsFull.length}</strong>
                      </div>
                      <div>
                        <LineChartOutlined aria-hidden="true" />
                        <span>首位</span>
                        <strong>{sectorLeaderRow?.sectorName ?? "待补"}</strong>
                      </div>
                      <div>
                        <FireOutlined aria-hidden="true" />
                        <span>尾部</span>
                        <strong>{sectorTailRow?.sectorName ?? "待补"}</strong>
                      </div>
                      <div>
                        <StockOutlined aria-hidden="true" />
                        <span>成分</span>
                        <strong className="stock-analysis-page__tabular">{sectorCoverageCount}</strong>
                      </div>
                    </div>
                    <Tabs
                      className="stock-analysis-page__sector-tabs"
                      size="small"
                      activeKey={sectorView}
                      onChange={(key) => setSectorView(key as StockSectorViewKind)}
                      items={sectorViewTabs.map((tab) => ({ key: tab.key, label: tab.label }))}
                    />

                    <div
                      className="stock-analysis-page__sector-chart-wrap"
                      data-testid="stock-analysis-sector-strength-chart"
                      aria-label="板块强弱横向图"
                    >
                      {sectorStrengthChartRows.length > 0 ? (
                        <ReactECharts
                          option={sectorStrengthChartOption}
                          className="stock-analysis-page__echart stock-analysis-page__echart--sector-strength"
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

                    <div className="stock-analysis-page__sector-rank-grid" data-testid="stock-analysis-sector-bars">
                      <div className="stock-analysis-page__sector-rank-col stock-analysis-page__sector-rank-col--top">
                        <h3>强势前 5</h3>
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
                              <div className="stock-analysis-page__sector-rank-row-head stock-analysis-page__tabular">
                                <span className="min-w-0 truncate">
                                  {row.rank}. {row.sectorName}{" "}
                                  <small>{row.sectorCode}</small>
                                </span>
                                <span>{row.score}</span>
                              </div>
                              <div className="stock-analysis-page__sector-rank-bar">
                                <progress
                                  className="stock-analysis-page__sector-rank-progress stock-analysis-page__sector-rank-progress--top"
                                  max={100}
                                  value={(sectorView === "score" ? row.scoreNormalized : row.metricBarNormalized) * 100}
                                  aria-hidden="true"
                                />
                                <div
                                  className="stock-analysis-page__sector-rank-bar-label stock-analysis-page__tabular"
                                >
                                  <span>{row.pctChange}</span>
                                  <small className="text-neutral-500">成分 {row.constituentCount}</small>
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="stock-analysis-page__sector-rank-col stock-analysis-page__sector-rank-col--bottom">
                        <h3>弱势后 5</h3>
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
                              <div className="stock-analysis-page__sector-rank-row-head stock-analysis-page__tabular">
                                <span className="min-w-0 truncate">
                                  {row.rank}. {row.sectorName}{" "}
                                  <small>{row.sectorCode}</small>
                                </span>
                                <span>{row.pctChange}</span>
                              </div>
                              <div className="stock-analysis-page__sector-rank-bar">
                                <progress
                                  className="stock-analysis-page__sector-rank-progress stock-analysis-page__sector-rank-progress--bottom"
                                  max={100}
                                  value={(sectorView === "score" ? row.scoreNormalized : row.metricBarNormalized) * 100}
                                  aria-hidden="true"
                                />
                                <div
                                  className="stock-analysis-page__sector-rank-bar-label stock-analysis-page__tabular"
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
                    <div
                      className="mt-2 flex flex-wrap gap-1.5 text-[11px] font-semibold text-neutral-600"
                      aria-label="板块筛选状态"
                    >
                      <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1">
                        <ClockCircleOutlined aria-hidden="true" /> 截面
                      </span>
                      <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1">
                        <BarChartOutlined aria-hidden="true" /> 筛选
                      </span>
                    </div>

                    <Collapse
                      bordered={false}
                      className="stock-analysis-page__sector-collapse"
                      items={[
                        {
                          key: "sector-detail-table",
                          label: "行业明细",
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
                                        <progress
                                          className="stock-analysis-page__pct-bar-progress"
                                          max={100}
                                          value={row.pctChangeBar}
                                          aria-label={`${row.sectorName} 涨跌幅条`}
                                        />
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
                      className="stock-analysis-page__sector-collapse"
                      activeKey={sectorSeriesCollapseKeys}
                      onChange={(keys) =>
                        setSectorSeriesCollapseKeys(Array.isArray(keys) ? keys : [keys])
                      }
                      items={[
                        {
                          key: "sector-rank-series-multi",
                          label: "多日强弱",
                          children: (
                            <div
                              className="stock-analysis-page__sector-series-wrap"
                              data-testid="stock-analysis-sector-series-panel"
                            >
                              <p className="stock-analysis-page__sector-series-note">
                                按交易日累计展示强弱变化；资金流向待补。
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
                                  description={strategyPanelErrorMessage(sectorRankSeriesQuery.error)}
                                />
                              ) : null}
                              {!sectorRankSeriesQuery.isFetching &&
                              !sectorRankSeriesQuery.isError &&
                              sectorRankSeriesQuery.data?.result?.state === "missing" ? (
                                <CompactStatusTile
                                  icon={<BarChartOutlined />}
                                  label="多日窗口"
                                  value="无数据"
                                  testId="stock-analysis-sector-series-empty"
                                />
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

                  </div>

                  <aside className="flex flex-col gap-3" aria-label="风险与数据可信度" data-testid="stock-analysis-first-screen-rail">
                    <p className={SA_SECTION_EYEBROW}>决策栏</p>
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
                          className="stock-analysis-page__rail-verdict"
                          data-testid="stock-analysis-closed-loop-verdict"
                          data-tone={closedLoopSummary.verdict.tone}
                        >
                          <span className="stock-analysis-page__rail-verdict-icon" aria-hidden="true">
                            {closedLoopSummary.verdict.tone === "positive" ? (
                              <CheckCircleOutlined />
                            ) : (
                              <SafetyCertificateOutlined />
                            )}
                          </span>
                          <div className="stock-analysis-page__rail-verdict-body">
                            <span className={`stock-analysis-page__rail-verdict-label ${toneTextClass(closedLoopSummary.verdict.tone)}`}>
                              {closedLoopSummary.verdict.label}
                            </span>
                            <strong>
                              {closedLoopSummary.verdict.headline}
                            </strong>
                          </div>
                          <div className="stock-analysis-page__rail-verdict-kpis">
                            <div className="stock-analysis-page__rail-kpi">
                              <span>边界</span>
                              <strong>{closedLoopSummary.boundaryCount}</strong>
                            </div>
                            <div className="stock-analysis-page__rail-kpi">
                              <span>依据</span>
                              <strong>{closedLoopSummary.verdict.evidence.length}</strong>
                            </div>
                          </div>
                          <Collapse
                            ghost
                            bordered={false}
                            destroyOnHidden
                            className="stock-analysis-page__candidate-collapse stock-analysis-page__rail-collapse"
                            items={[
                              {
                                key: "closed-loop-verdict-detail",
                                label: "依据明细",
                                children: (
                                  <div className="text-xs text-neutral-600">
                                    <p className="m-0">{closedLoopSummary.verdict.primaryReason}</p>
                                    <ul className="mt-2 space-y-1 pl-4" aria-label="闭环结论证据">
                                      {closedLoopSummary.verdict.evidence.map((item) => (
                                        <li key={item} className="list-disc" title={item}>
                                          {item}
                                        </li>
                                      ))}
                                    </ul>
                                    <p className="m-0 mt-2 text-neutral-500">{closedLoopSummary.verdict.nextStep}</p>
                                  </div>
                                ),
                              },
                            ]}
                          />
                        </div>

                        <div className="stock-analysis-page__rail-metric-grid" aria-label="首屏决策指标">
                          <div data-tone={closedLoopSummary.referenceRating.tone}>
                            <span className="stock-analysis-page__rail-stat-icon" aria-hidden="true">
                              <SafetyCertificateOutlined />
                            </span>
                            <span>
                              <span>闭环</span>
                              <strong>{closedLoopSummary.referenceRating.label}</strong>
                            </span>
                          </div>
                          <div data-tone={railRiskTone}>
                            <span className="stock-analysis-page__rail-stat-icon" aria-hidden="true">
                              <FireOutlined />
                            </span>
                            <span>
                              <span>风险</span>
                              <strong>{riskTriggeredCount} 触发</strong>
                            </span>
                          </div>
                          <div data-tone={boundaryRailIssueCount > 0 ? "warning" : "positive"}>
                            <span className="stock-analysis-page__rail-stat-icon" aria-hidden="true">
                              <DatabaseOutlined />
                            </span>
                            <span>
                              <span>边界</span>
                              <strong>{boundaryRailIssueCount}</strong>
                            </span>
                          </div>
                          <div data-tone={reviewQueue.length > 0 ? "positive" : "warning"}>
                            <span className="stock-analysis-page__rail-stat-icon" aria-hidden="true">
                              <StockOutlined />
                            </span>
                            <span>
                              <span>复核</span>
                              <strong>{reviewQueue.length}</strong>
                            </span>
                          </div>
                        </div>

                        <p className="stock-analysis-page__rail-next-action" title={railNextActionFullLabel}>
                          <StockOutlined aria-hidden="true" />
                          <span>{railNextActionLabel}</span>
                        </p>

                        <ul
                          className="stock-analysis-page__rail-check-list"
                          aria-label="闭环检查项"
                          data-testid="stock-analysis-rail-check-matrix"
                        >
                          {closedLoopSummary.items.map((item) => (
                            <li
                              key={item.key}
                              className="stock-analysis-page__rail-check-row"
                              data-tone={item.tone}
                              data-testid={
                                item.key === "replay" ? "stock-analysis-replay-status" : `stock-analysis-closed-loop-${item.key}`
                              }
                            >
                              <div className="stock-analysis-page__rail-check-main">
                                <span>
                                  <span className="stock-analysis-page__rail-check-icon" aria-hidden="true">
                                    {closedLoopRailIcon(item.key)}
                                  </span>
                                  <span>{item.label}</span>
                                </span>
                                <strong className={toneTextClass(item.tone)}>
                                  {item.statusLabel}
                                </strong>
                              </div>
                              {(item.key === "replay" || (item.key === "adversarial_gate" && item.tone !== "positive")) &&
                              item.detail ? (
                                <Collapse
                                  ghost
                                  bordered={false}
                                  destroyOnHidden
                                  className="stock-analysis-page__candidate-collapse stock-analysis-page__rail-collapse"
                                  items={[
                                    {
                                      key: `${item.key}-detail`,
                                      label: "明细",
                                      children: (
                                        <p className="m-0 text-[11px] leading-snug text-neutral-500">{item.detail}</p>
                                      ),
                                    },
                                  ]}
                                />
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
                          <p className={SA_SECTION_DESC}>
                            {riskTriggeredCount} 触发 · {riskWatchCount} 观察
                          </p>
                        </div>
                      </div>
                      <div
                        className="stock-analysis-page__rail-risk-strip"
                        aria-label="风险退出统计"
                        data-testid="stock-analysis-risk-strip"
                      >
                        <div data-tone={riskTriggeredCount > 0 ? "negative" : "positive"}>
                          <FireOutlined aria-hidden="true" />
                          <span>触发</span>
                          <strong>{riskTriggeredCount}</strong>
                        </div>
                        <div data-tone={riskWatchCount > 0 ? "warning" : "positive"}>
                          <LineChartOutlined aria-hidden="true" />
                          <span>观察</span>
                          <strong>{riskWatchCount}</strong>
                        </div>
                        <div data-tone={riskExitUnsupported ? "warning" : "positive"}>
                          <DatabaseOutlined aria-hidden="true" />
                          <span>供数</span>
                          <strong>{riskExitUnsupported ? "待补" : "接通"}</strong>
                        </div>
                      </div>
                      {confluenceQuery.isError ? (
                        <p className="text-xs font-semibold text-neutral-600">联动观察暂不可用。</p>
                      ) : null}
                      {riskExitUnsupported ? (
                        <div className="stock-analysis-page__rail-warning">
                          <div className="stock-analysis-page__rail-warning-head">
                            <span aria-hidden="true">
                              <DatabaseOutlined />
                            </span>
                            <span>
                              <strong>风险退出待补</strong>
                              <p className="m-0">{riskExitBlockedSummary(riskExitUnsupported.reason)}</p>
                            </span>
                          </div>
                          {riskExitUnsupported.reason ? (
                            <Collapse
                              ghost
                              bordered={false}
                              destroyOnHidden
                              className="stock-analysis-page__candidate-collapse stock-analysis-page__rail-collapse"
                              items={[
                                {
                                  key: "risk-exit-unsupported-reason",
                                  label: "供数原因",
                                  children: (
                                    <p className="m-0 text-xs">
                                      {riskExitBlockedDetail(riskExitUnsupported.reason, riskExitUnsupported.key)}
                                    </p>
                                  ),
                                },
                              ]}
                            />
                          ) : null}
                        </div>
                      ) : null}
                      {riskRows.length > 0 ? (
                        <div className="stock-analysis-page__rail-risk-list">
                          {riskRows.slice(0, 5).map((row) => (
                            <div
                              className="stock-analysis-page__rail-risk-row"
                              data-testid={`stock-risk-row-${row.stockCode}`}
                              data-tone={row.status === "triggered" ? "negative" : "warning"}
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
                              <div className="stock-analysis-page__rail-risk-main">
                                <span>
                                  <strong>{row.stockName}</strong>
                                  <small title={row.stockCode}>{row.stockCode}</small>
                                </span>
                                <em className={toneTextClass(row.status === "triggered" ? "negative" : "warning")}>
                                  {riskStatusLabel(row.status)}
                                </em>
                              </div>
                              <div className="stock-analysis-page__rail-risk-meta">
                                <span className="stock-analysis-page__tabular">收 {row.latestClose}</span>
                                <span className="stock-analysis-page__tabular">距 {row.distanceToExitPct}</span>
                                <span className="stock-analysis-page__tabular">线 {row.exitWatchPrice}</span>
                              </div>
                              <Collapse
                                ghost
                                bordered={false}
                                destroyOnHidden
                                className="stock-analysis-page__candidate-collapse stock-analysis-page__rail-collapse"
                                items={[
                                  {
                                    key: `${row.stockCode}-risk-reason`,
                                    label: "供数原因",
                                    children: (
                                      <div className="text-xs text-neutral-600">
                                        <p className="m-0">{row.reason}</p>
                                        <p className="m-0 mt-1 text-neutral-500">退出观察价 {row.exitWatchPrice}</p>
                                      </div>
                                    ),
                                  },
                                ]}
                              />
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="stock-analysis-page__rail-empty">
                          {riskExitUnsupported ? "持仓快照待补" : "风险 0"}
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
                              <strong className="stock-analysis-page__tabular">{item.statusLabel}</strong>
                            </div>
                          </div>
                        ))}
                      </div>
                      {boundarySummary ? (
                        <div
                          className="stock-analysis-page__boundary-summary"
                          data-testid="stock-analysis-boundary-summary"
                        >
                          <span data-tone={boundarySummary.boundaryCount > 0 ? "warning" : "positive"}>
                            <small>边界</small>
                            <strong>{boundarySummary.summaryLabel}</strong>
                          </span>
                          <span data-tone={boundarySummary.boundaryCount > 0 ? "warning" : "positive"}>
                            <small>拆分</small>
                            <strong>{boundarySummary.detailLabel}</strong>
                          </span>
                        </div>
                      ) : null}
                      <Button
                        type="link"
                        className="stock-analysis-page__rail-action"
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
                              严重
                            </Text>
                            <ul>
                              {strategyPayload.diagnostics
                                .filter((d) => d.severity === "error")
                                .map((d) => (
                                  <li key={d.code}>{localizeStockBackendText(d.message, d.input_family)}</li>
                                ))}
                              {strategyPayload.diagnostics.filter((d) => d.severity === "error").length === 0 ? (
                                <li>暂无</li>
                              ) : null}
                            </ul>
                            <Text strong type="warning">
                              警告
                            </Text>
                            <ul>
                              {strategyPayload.diagnostics
                                .filter((d) => d.severity === "warning")
                                .map((d) => (
                                  <li key={d.code}>{localizeStockBackendText(d.message, d.input_family)}</li>
                                ))}
                              {strategyPayload.diagnostics.filter((d) => d.severity === "warning").length === 0 ? (
                                <li>暂无</li>
                              ) : null}
                            </ul>
                            <Text strong type="secondary">
                              信息
                            </Text>
                            <ul>
                              {strategyPayload.diagnostics
                                .filter((d) => d.severity === "info")
                                .map((d) => (
                                  <li key={d.code}>{localizeStockBackendText(d.message, d.input_family)}</li>
                                ))}
                            </ul>
                            <Typography.Title level={5}>数据缺口</Typography.Title>
                            <ul>
                              {strategyPayload.data_gaps.map((g) => (
                                <li key={`${g.input_family}-${g.status}`}>
                                  <strong>{dataGapFamilyLabel(g.input_family)}</strong> {statusLabel(g.status)}:{" "}
                                  {localizeStockBackendText(g.evidence, g.input_family)}
                                </li>
                              ))}
                            </ul>
                            <Typography.Title level={5}>可用输出</Typography.Title>
                            <p>{strategyPayload.supported_outputs.map(outputKeyLabel).join("、") || "无"}</p>
                            <Typography.Title level={5}>阻断输出</Typography.Title>
                            <ul>
                              {strategyPayload.unsupported_outputs.map((u) => (
                                <li key={u.key}>
                                  <strong>{outputKeyLabel(u.key)}</strong>: {localizeStockBackendText(u.reason, u.key)}
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
                  <div className="stock-analysis-page__deep-zone-title">
                    <h2>供数闭环</h2>
                    <p
                      className="stock-analysis-page__deep-zone-gate-summary"
                      data-testid="stock-analysis-deep-zone-gate-summary"
                      data-tone={deepAnalysisGateSummary.tone}
                    >
                      {deepAnalysisGateSummary.line}
                    </p>
                  </div>
                  <div className="stock-analysis-page__deep-zone-audit-strip" data-testid="stock-analysis-deep-zone-audit-strip">
                    {deepZoneAuditRows.map((row) => (
                      <div
                        key={row.key}
                        className="stock-analysis-page__deep-zone-audit-item"
                        data-tone={row.tone}
                      >
                        <span className="stock-analysis-page__deep-zone-audit-icon">{row.icon}</span>
                        <span className="stock-analysis-page__deep-zone-audit-label">{row.label}</span>
                        <strong>{row.value}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              <div className="stock-analysis-strategy-card-grid">
              {cycleRotationFramework ? (
                <StrategyModuleCard
                  id="cycle-rotation"
                  title={cycleRotationFramework.display_name}
                  subtitle="周期轮动"
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
                    <strong>轮动规则</strong>
                    <span>{cycleRuleSummary(cycleRotationFramework.layers)}</span>
                    {cycleRotationFramework.observation_only ? <small>只读观察，不生成交易指令</small> : null}
                    <small>{cycleCadenceLabel(cycleRotationFramework.rebalance_cadence)}</small>
                  </div>
                  {cycleMacroLayerSummary ? (
                    <div
                      className="stock-analysis-page__cycle-macro-layer"
                      data-testid="stock-analysis-cycle-macro-layer"
                    >
                      <div className={SA_SECTION_HEAD}>
                        <strong>宏观层</strong>
                        <span className={SA_PILL}>
                          {cycleMacroLayerSummary.statusLabel}
                        </span>
                      </div>
                      <p>
                        宏观分 {cycleMacroLayerSummary.macroScoreLabel}
                      </p>
                      <p>{cycleEvidenceLabel(cycleMacroLayerSummary.evidence)}</p>
                      <small>
                        {cycleInputSummary(cycleMacroLayerSummary.availableInputs, cycleMacroLayerSummary.missingInputs)}
                      </small>
                      {cycleMacroLayerSummary.macroGapLabels.length > 0 ? (
                        <div className="stock-analysis-page__cycle-constraints">
                          {cycleMacroLayerSummary.macroGapLabels.map((gap) => (
                            <span key={gap}>{cycleGapLabel(gap)}</span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  {cycleRotationFramework.lifecourt_overlay ? (
                    <div className="stock-analysis-page__cycle-lifecourt-overlay">
                      <strong>{cycleRotationFramework.lifecourt_overlay.display_name}</strong>
                      <p>{cycleBoundaryLabel(cycleRotationFramework.lifecourt_overlay.boundary)}</p>
                      <small>
                        {cycleInputSummary(
                          cycleRotationFramework.lifecourt_overlay.available_inputs,
                          cycleRotationFramework.lifecourt_overlay.missing_inputs,
                        )}
                      </small>
                      <div className="stock-analysis-page__cycle-constraints">
                        {cycleRotationFramework.lifecourt_overlay.life_long_gates.map((gate) => (
                          <span key={gate}>{cycleConstraintLabel(gate)}</span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  <div className="stock-analysis-page__cycle-layer-grid">
                    {cycleRotationFramework.layers.map((layer) => (
                      <article className="stock-analysis-page__cycle-layer" key={layer.key}>
                        <div>
                          <span>{cycleLayerTitleLabel(layer)}</span>
                          <strong>{cycleLayerWeightLabel(layer)}</strong>
                        </div>
                        <em>{localizeImplementationStage(layer.status)}</em>
                        <p>{cycleEvidenceLabel(layer.evidence)}</p>
                        <small>
                          {cycleInputSummary(layer.available_inputs, layer.missing_inputs)}
                        </small>
                      </article>
                    ))}
                  </div>
                  <div className="stock-analysis-page__cycle-constraints">
                    {cycleRotationFramework.constraints.map((constraint) => (
                      <span key={constraint}>{cycleConstraintLabel(constraint)}</span>
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
                        组合回测暂不可用：{strategyPanelErrorMessage(candidateHistoryPortfolioBacktestQuery.error)}
                      </p>
                    ) : null}
                    {!candidateHistoryPortfolioBacktestQuery.isLoading &&
                    !candidateHistoryPortfolioBacktestQuery.isError ? (
                      candidateHistoryPortfolioBacktestPayload?.status === "portfolio_proxy" &&
                      candidateHistoryPortfolioBacktestPayload.summary ? (
                        <>
                          <BacktestBoundaryChips
                            label="组合回测"
                            missingInputs={candidateHistoryPortfolioBacktestPayload.missing_full_strategy_inputs}
                            testId="stock-analysis-portfolio-backtest-boundary"
                          />
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
                        <CompactStatusTile
                          icon={<LineChartOutlined />}
                          label="组合回测"
                          value="样本不足"
                          testId="stock-analysis-portfolio-backtest-empty"
                        />
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
                        代理回测暂不可用：{strategyPanelErrorMessage(cycleProxyBacktestQuery.error)}
                      </p>
                    ) : null}
                    {!cycleProxyBacktestQuery.isLoading && !cycleProxyBacktestQuery.isError ? (
                      cycleProxyBacktestPayload?.status === "proxy" && cycleProxyBacktestPayload.summary ? (
                        <>
                          <BacktestBoundaryChips
                            label="代理回测"
                            missingInputs={cycleProxyBacktestPayload.missing_full_strategy_inputs}
                            testId="stock-analysis-cycle-proxy-boundary"
                          />
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
                        <CompactStatusTile
                          icon={<LineChartOutlined />}
                          label="代理回测"
                          value="样本不足"
                          testId="stock-analysis-cycle-proxy-empty"
                        />
                      )
                    ) : null}
                  </div>
                </StrategyModuleCard>
              ) : null}


              <StrategyModuleCard
                id="theme-breakout"
                title="题材突变观察"
                subtitle="题材代理"
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
                              {row.statusLabel} / {row.rowCountLabel}
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
                                  <em>{leader.tags.join(" / ") || "复核"}</em>
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
                subtitle="T+5 共振"
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
                            T+5 共振 · 超跌仅观察
                          </p>
                        </div>
              </StrategyModuleCard>

              <StrategyModuleCard
                id="market-priority"
                title="当前市场策略优先级"
                subtitle="T+5 排序"
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
                    当前市场策略优先级暂不可用：{strategyPanelErrorMessage(strategyScoreQuery.error)}
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
                        {strategyPriorityReason} · 阈值 {strategyScorePayload?.min_sample ?? 20} · 只读排序
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
                                  <td>{strategyDisplayLabel(row.strategy_label, row.signal_kind)}</td>
                                  <td>{strategyPriorityStatusLabel(row.priority_label)}</td>
                                  <td className="stock-analysis-page__table-number" data-testid="stock-analysis-market-priority-score">
                                    {formatPriorityScore(row.priority_score)}
                                  </td>
                                  {strategyBacktestHorizons.map((horizon) => (
                                    <td className="stock-analysis-page__table-number" key={horizon}>
                                      {backtestStatsText(row.stats[horizon])}
                                    </td>
                                  ))}
                                  <td>
                                    <span>{strategyPriorityReasonLabel(row)}</span>
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
                      <p className="stock-analysis-page__empty">样本不足</p>
                    )}
                    {strategyMaturityRow && strategyMaturity && strategyMaturitySnapshots.length > 0 ? (
                      <div data-testid="stock-analysis-candidate-maturity">
                        <div className="stock-analysis-page__filter-status">
                          <span>当前候选成熟进度</span>
                          <strong>
                            {strategyDisplayLabel(strategyMaturityRow.strategy_label, strategyMaturityRow.signal_kind)}
                            {strategyMaturityRow.diagnostics?.priority_scope_label
                              ? ` / ${strategyPriorityScopeLabel(strategyMaturityRow.diagnostics.priority_scope_label)}`
                              : ""}
                          </strong>
                          <small>
                            {strategyMaturityRemainingText(strategyMaturity)}，
                            {localizeStockBackendText(strategyMaturity.reason, strategyMaturityRow.signal_kind)}
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
                          <strong>
                            {strategyDisplayLabel(strategyMaturityRow.strategy_label, strategyMaturityRow.signal_kind)}
                          </strong>
                          <small>快照明细 · 按排名</small>
                        </div>
                        {strategyMaturityDetailQuery.isLoading ? (
                          <p className="stock-analysis-page__empty">候选明细加载中。</p>
                        ) : null}
                        {strategyMaturityDetailQuery.isError ? (
                          <p className="stock-analysis-page__notice">
                            候选明细暂不可用：{strategyPanelErrorMessage(strategyMaturityDetailQuery.error)}
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
                subtitle="回溯胜率"
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
                    策略回溯表现暂不可用：{strategyPanelErrorMessage(strategyBacktestQuery.error)}
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
                                  <td>{localizeMarketDataStatus(row.marketState)}</td>
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
                subtitle="切片 T+5"
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
                    优化诊断暂不可用：{strategyPanelErrorMessage(strategyOptimizationQuery.error)}
                  </p>
                ) : null}
                {!strategyOptimizationQuery.isLoading && !strategyOptimizationQuery.isError ? (
                  <>
                    <div className="stock-analysis-page__filter-status">
                      <span>当前最新日期收益</span>
                      <strong>
                        {(strategyOptimizationPayload?.pending_summary.pending_rows ?? 0) > 0
                          ? "待成熟"
                          : "已成熟"}
                      </strong>
                      <small>
                        {localizeStockBackendText(
                          strategyOptimizationPayload?.pending_summary.message ?? "T+5 收益成熟状态待补。",
                        )}
                      </small>
                    </div>
                    <p className="stock-analysis-page__footnote">
                      复核排序 · 不改规则
                    </p>
                    <div className="stock-analysis-page__filter-status">
                      <span>三策略 T+5 排名</span>
                      <strong>{strategyOptimizationRows.length} 组</strong>
                      <small>阈值 {strategyOptimizationPayload?.min_sample ?? 20} · 收益/胜率/成熟度</small>
                    </div>
                    {strategyOptimizationRows.length > 0 ? (
                      <div className="stock-analysis-page__table-wrap">
                        <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                          <thead>
                            <tr>
                              <th scope="col">策略</th>
                              <th scope="col">复核状态</th>
                              <th scope="col">T+5 收益</th>
                              <th scope="col">按日等权</th>
                              <th scope="col">原因</th>
                            </tr>
                          </thead>
                          <tbody>
                            {strategyOptimizationRows.map((row) => (
                              <tr key={row.summary_key}>
                                <td>{strategyDisplayLabel(row.strategy_label, row.signal_kind)}</td>
                                <td>{strategyPriorityStatusLabel(row.recommendation.priority_label)}</td>
                                <td className="stock-analysis-page__table-number">
                                  {backtestStatsText(strategyOptimizationPrimaryStats(row, strategyOptimizationPayload))}
                                </td>
                                <td className="stock-analysis-page__table-number">
                                  {strategyOptimizationDateWeightedText(row, strategyOptimizationPayload)}
                                </td>
                                <td>{strategyOptimizationReasonLabel(row)}</td>
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
                        {strategyOptimizationSlices.strongest
                          ? strategyOptimizationSliceLabel(strategyOptimizationSlices.strongest)
                          : "最强待补"}{" "}
                        /{" "}
                        {strategyOptimizationSlices.weakest
                          ? strategyOptimizationSliceLabel(strategyOptimizationSlices.weakest)
                          : "最弱待补"}
                      </strong>
                      <small>
                        {strategyOptimizationSlices.weakest
                          ? `${strategyDisplayLabel(
                              strategyOptimizationSlices.weakest.strategy_label,
                              strategyOptimizationSlices.weakest.signal_kind,
                            )} ${strategyOptimizationSliceLabel(
                              strategyOptimizationSlices.weakest,
                            )}：${strategyPriorityStatusLabel(
                              strategyOptimizationSlices.weakest.recommendation.priority_label,
                            )}`
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
                              <th scope="col">复核状态</th>
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
                                    {label}：{strategyOptimizationSliceLabel(slice)}
                                  </td>
                                  <td>{strategyDisplayLabel(slice.strategy_label, slice.signal_kind)}</td>
                                  <td>{strategyPriorityStatusLabel(slice.recommendation.priority_label)}</td>
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
                title="多策略观察池"
                subtitle="观察池"
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
                    <span className={SA_PILL}>条件触发</span>
                  </div>
                          {gateState && !meanReversionMarketActive ? (
                            <CompactStatusTile
                              icon={<FireOutlined />}
                              label="超跌"
                              value="暂停"
                              tone="warning"
                              testId="stock-analysis-mean-reversion-empty"
                            />
                          ) : null}
                          {meanReversionMarketActive && !meanReversionPayload ? (
                            <CompactStatusTile
                              icon={<FireOutlined />}
                              label="超跌"
                              value="未就绪"
                              tone="warning"
                              testId="stock-analysis-mean-reversion-empty"
                            />
                          ) : null}
                          {meanReversionMarketActive &&
                          meanReversionPayload &&
                          meanReversionPayload.items.length === 0 ? (
                            <CompactStatusTile
                              icon={<FireOutlined />}
                              label="超跌"
                              value="0 候选"
                              testId="stock-analysis-mean-reversion-empty"
                            />
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
                          <div className="mt-2 flex flex-wrap gap-1.5" aria-label="超跌筛选规则">
                            {["价格回撤", "企稳", "放量", "门控停用"].map((label) => (
                              <span
                                key={label}
                                className="inline-flex items-center gap-1 rounded-md border border-neutral-200 bg-white px-2 py-1 text-[11px] font-semibold text-neutral-600"
                              >
                                <FireOutlined aria-hidden="true" /> {label}
                              </span>
                            ))}
                          </div>
                        </div>
                <div className="stock-analysis-page__factor-screen">
                  <div className={SA_SECTION_HEAD}>
                    <strong>多因子选股</strong>
                    <span className={SA_PILL}>
                      {factorScreenPayload?.candidate_count ?? 0} 只 ·{" "}
                      {factorScreenCoverageNote ?? "数据未就绪"}
                    </span>
                  </div>
                          {!factorScreenPayload ? (
                            <CompactStatusTile
                              icon={<DatabaseOutlined />}
                              label="多因子"
                              value="未就绪"
                              tone="warning"
                              testId="stock-analysis-factor-screen-empty"
                            />
                          ) : factorScreenPayload.items.length === 0 ? (
                            <CompactStatusTile
                              icon={<DatabaseOutlined />}
                              label="多因子"
                              value="0 候选"
                              testId="stock-analysis-factor-screen-empty"
                            />
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
                          <div className="mt-2 flex flex-wrap gap-1.5" aria-label="多因子选股因子">
                            {["价值", "质量", "动量", "低波", "股息"].map((label) => (
                              <span
                                key={label}
                                className="inline-flex items-center gap-1 rounded-md border border-neutral-200 bg-white px-2 py-1 text-[11px] font-semibold text-neutral-600"
                              >
                                <DatabaseOutlined aria-hidden="true" /> {label}
                              </span>
                            ))}
                            {factorScreenCoverageNote ? (
                              <span
                                className="inline-flex items-center gap-1 rounded-md border border-primary-100 bg-primary-50 px-2 py-1 text-[11px] font-bold text-primary-700"
                                title={factorScreenCoverageNote}
                              >
                                覆盖 {compactText(factorScreenCoverageNote, 14)}
                              </span>
                            ) : null}
                          </div>
                        </div>
              </StrategyModuleCard>

              <StrategyModuleCard
                id="events-monitoring"
                title="关键事件与监控"
                subtitle="事件风险"
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
                          <th scope="col">事件</th>
                          <th scope="col">影响</th>
                          <th scope="col">明细</th>
                        </tr>
                      </thead>
                      <tbody>
                        {eventMonitorRows.map((row) => (
                          <tr key={row.key} data-level={row.level}>
                            <td>{eventSourceLabel(row.source)}</td>
                            <td>
                              <span className="stock-analysis-page__event-level" data-level={row.level}>
                                {eventLevelLabel(row.level)}
                              </span>
                            </td>
                            <td>{eventNameLabel(row)}</td>
                            <td>{eventImpactLabel(row)}</td>
                            <td title={eventDetailLabel(row)}>{compactText(eventDetailLabel(row), 26)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                        ) : (
                  <CompactStatusTile
                    icon={<FireOutlined />}
                    label="关键事件"
                    value="0"
                    testId="stock-analysis-events-empty"
                  />
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
          title="复核助手"
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
