import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { Collapse, Select } from "antd";
import { useApiClient } from "../../../api/client";
import { LightIcon } from "../../../components/LightIcon";
import {
  DataQualityPill,
  DataSourceBadge,
  DiagnosticDisclosure,
  SystemAccessBadge,
} from "../../../components/StatusPill";
import type { DataQualityStatus } from "../../../components/StatusContract";
import { externalDataQueryOptions } from "../../../app/externalDataRefreshPolicy";
import { nonCancellingRefetchOptions } from "../../../app/externalDataRefreshPolicy";
import { PageSectionLead, type PageSectionLeadProps } from "../../../components/page/PagePrimitives";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import type {
  ChoiceMacroLatestPoint,
  ChoiceMacroRecentPoint,
  ChoiceNewsEventsPayload,
  FxAnalyticalPayload,
  FxFormalStatusPayload,
  LivermoreCandidateHistoryPayload,
  LivermoreCandidateHistoryPortfolioBacktestPayload,
  LivermoreCycleProxyBacktestPayload,
  LivermoreSectorRankSeriesPayload,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyOptimizationPayload,
  LivermoreStrategyScorePayload,
  MacroVendorPayload,
  MarketDataCoverageSection,
  MarketDataCoverageSummaryPayload,
  NcdFundingProxyPayload,
  ResearchCalendarEvent,
  ResultMeta,
  TushareSupplementPayload,
} from "../../../api/contracts";
import type { MacroToolkitAnalysisPayload } from "../../../api/macroToolkitClient";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { BondFuturesTable } from "../components/BondFuturesTable";
import { BondTradeDetail } from "../components/BondTradeDetail";
import { CreditBondTradesTable } from "../components/CreditBondTradesTable";
import { MarketDataDeskBridgeBand } from "../components/MarketDataDeskBridgeBand";
import { MarketDataExtendedTerminalSection } from "../components/MarketDataExtendedTerminalSection";
import { MarketDataFxFormalSection } from "../components/MarketDataFxFormalSection";
import { MarketDataFxSeriesDeck } from "../components/MarketDataFxSeriesDeck";
import { MarketDataLiquidityDeck } from "../components/MarketDataLiquidityDeck";
import { MarketDataMacroSeriesDeck } from "../components/MarketDataMacroSeriesDeck";
import { MarketDataSupplementarySeriesSection } from "../components/MarketDataSupplementarySeriesSection";
import { MarketDataLinkageSection } from "../components/MarketDataLinkageSection";
import { MarketDataLivermoreSection } from "../components/MarketDataLivermoreSection";
import { MarketTerminalTicker } from "../components/MarketTerminalTicker";
import { MoneyMarketTable } from "../components/MoneyMarketTable";
import { NcdMatrix } from "../components/NcdMatrix";
import {
  type NewsAndCalendarCalendarState,
  type NewsAndCalendarNewsState,
} from "../components/NewsAndCalendar";
import { MarketDataSeriesCategoryCard } from "../components/MarketDataSeriesCategoryCard";
import { MarketDataTushareSupplementSection } from "../components/MarketDataTushareSupplementSection";
import {
  marketCatalogRefreshTier,
  marketSeriesRefreshTier,
  type MarketObservationPoint,
} from "../lib/marketDataCategoryStore";
import { designTokens } from "../../../theme/designSystem";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../../../utils/choiceMacroFormat";
import {
  buildCatalogVendorNameMap,
  buildMarketDataActiveFilterSummary,
  filterRateQuoteRows,
  filterTerminalTickerItems,
  type MarketDataRateQuoteSection,
  type MarketDataTerminalModel,
  type MarketTerminalTickerItem,
} from "../lib/marketDataTerminalModel";
import { useMarketDataPageData } from "../hooks/useMarketDataPageData";
import { type MarketOverviewMetric, MarketPipelineKpiStrip } from "./MarketDataHeroSection";
import { MarketDataMacroDepthTabs } from "./MarketDataMacroDepthTabs";
import { MarketDataSeriesTimeChart } from "../components/MarketDataSeriesTimeChart";
import { MarketDataTermStructureChart } from "../components/MarketDataTermStructureChart";
import type { LivermoreStrategyModel } from "../lib/livermoreStrategyModel";
import { buildSpreadSlots, buildBridgeKpiMetrics, buildMarketDataBasisChipLabel, buildTerminalKpiMetricsFromTickerItems, formatMarketWorkbenchSourceSummary } from "./marketDataPageModel";
import { buildMarketDataTapeCockpitModel } from "./marketDataTapeCockpitModel";
import { useLazyMount } from "../lib/useLazyMount";
import { MarketWorkbenchFrame } from "../../workbench/market-shell";
import "./MarketDataPage.css";

/** 外汇分析观察区块顶部元数据蓝条（本区块·外汇分析）；默认隐藏。 */
const _MARKET_DATA_SHOW_FX_ANALYSIS_META_STRIP = false;

/** 展示已拉取的宏观稳定/降级序列（不含页尾目录运维面板）。 */
const MARKET_DATA_SHOW_MACRO_SERIES_DECK = true;

/** 展示已拉取的外汇分析序列分组。 */
const MARKET_DATA_SHOW_FX_ANALYSIS_SECTION = true;

/** 页尾目录与元数据运维面板（默认关）。 */
const MARKET_DATA_SHOW_MACRO_OBSERVATION_AND_CATALOG_EVIDENCE = false;

const s = designTokens.space;

const marketDataSectionLeadStyle: CSSProperties = {
  marginTop: 0,
  marginBottom: s[2],
};

function MarketSectionLead({
  flushTop: _flushTop = false,
  ...props
}: Omit<PageSectionLeadProps, "style"> & { flushTop?: boolean }) {
  return <PageSectionLead {...props} style={marketDataSectionLeadStyle} />;
}

function formatRecentPoint(point: ChoiceMacroRecentPoint) {
  return `${point.trade_date} ${point.value_numeric.toFixed(2)}`;
}

function seriesRecentPoints(point: MarketObservationPoint) {
  return point.recent_points ?? [];
}

function seriesPolicyNote(point: MarketObservationPoint) {
  const note = point.policy_note?.trim();
  if (!note) return "分析口径读链路";
  const knownNotes: Record<string, string> = {
    "analytical middle-rate observation only": "仅分析口径中间价观察",
    "analytical index observation only": "仅分析口径指数观察",
    "main refresh date-slice lane": "主刷新日期切片链路",
  };
  return knownNotes[note] ?? note;
}

function seriesFetchModeLabel(point: { fetch_mode?: string | null; fetch_granularity?: string | null }) {
  const fetchMode = point.fetch_mode ?? "date_slice";
  const granularity = point.fetch_granularity ?? "batch";
  const fetchModeLabels: Record<string, string> = {
    date_slice: "日期切片",
    latest: "最新值",
    single_fetch: "单次抓取",
  };
  const granularityLabels: Record<string, string> = {
    batch: "批量",
    single: "单项",
  };
  return `${fetchModeLabels[fetchMode] ?? fetchMode} / ${granularityLabels[granularity] ?? granularity}`;
}

function refreshTierLabel(tier: string) {
  const labels: Record<string, string> = {
    stable: "数据正常",
    fallback: "数据延迟",
    isolated: "单点观察",
  };
  return labels[tier] ?? tier;
}

function fxAnalyticalGroupTitle(title: string) {
  const labels: Record<string, string> = {
    "Analytical FX: middle-rates": "外汇分析：中间价",
    "Analytical FX: indices": "外汇分析：指数",
    "Analytical FX: swap curves": "外汇分析：掉期曲线",
    "Analytical FX: event calendar": "外汇分析：事件日历",
  };
  return labels[title] ?? title;
}

function fxAnalyticalObservationCount(groups: FxAnalyticalPayload["groups"]): number {
  return groups.reduce((total, group) => total + group.series.length + (group.events?.length ?? 0), 0);
}

function _renderSeriesCards(
  series: MarketObservationPoint[],
  options?: { testIdPrefix?: string; hideSeriesProvenance?: boolean },
) {
  const testIdPrefix = options?.testIdPrefix ?? "market-data-series";
  const hideSeriesProvenance = options?.hideSeriesProvenance ?? false;

  return (
    <div className="market-data-stack-gap-3">
      {series.map((point) => (
        <div
          key={point.series_id}
          data-testid={`${testIdPrefix}-${point.series_id}`}
          className="market-data-inset-card market-data-inset-card--surface"
        >
          <div className="market-data-series-card-header">
            <div>
              <div className="market-data-series-title">{point.series_name}</div>
              {!hideSeriesProvenance ? (
                <div className="market-data-dim-label">{point.series_id}</div>
              ) : null}
            </div>
            <div className="market-data-tier-pill">
              <span>{`层级 ${refreshTierLabel(marketSeriesRefreshTier(point))}`}</span>
              <span>·</span>
              <span>质量 {resultMetaQualityLabel(point.quality_flag)}</span>
            </div>
          </div>

          <div className="market-data-series-metrics">
            <div>
              <div className="market-data-dim-label">交易日</div>
              <div>{point.trade_date}</div>
            </div>
            <div>
              <div className="market-data-dim-label">最新值</div>
              <div className="market-data-series-value">
                {formatChoiceMacroValue(point)}
              </div>
            </div>
            <div>
              <div className="market-data-dim-label">变动</div>
              <div className="market-data-tabular">{formatChoiceMacroDelta(point, { emptyDisplay: "无" })}</div>
            </div>
            <div>
              <div className="market-data-dim-label">抓取</div>
              <div>{seriesFetchModeLabel(point)}</div>
            </div>
          </div>

          {!hideSeriesProvenance ? (
            <>
              <div className="market-data-meta-muted-sm">
                来源 {point.source_version} 路供应商 {point.vendor_version}
              </div>
              <div className="market-data-meta-body">{seriesPolicyNote(point)}</div>
            </>
          ) : null}

          <div className="market-data-chip-row">
            {seriesRecentPoints(point).map((recentPoint) => (
              <span
                key={`${point.series_id}:${recentPoint.trade_date}:${recentPoint.vendor_version}`}
                className="market-data-series-chip"
              >
                {formatRecentPoint(recentPoint)}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function resultMetaQualityLabel(value: ResultMeta["quality_flag"] | undefined): string {
  if (value === "ok") return "数据正常";
  if (value === "warning" || value === "missing") return "部分缺失";
  if (value === "error") return "不可用";
  if (value === "stale") return "数据延迟";
  return "部分缺失";
}

function coverageStatusLabel(status: MarketDataCoverageSection["status"]): string {
  const labels: Record<MarketDataCoverageSection["status"], string> = {
    ready: "数据正常",
    empty: "部分缺失",
    warning: "部分缺失",
    stale: "数据延迟",
    error: "不可用",
    source_pending: "未接入",
    proxy_only: "代理数据",
    deferred: "接入中",
  };
  return labels[status];
}

function dataQualityStatusForReadiness(label: string): DataQualityStatus {
  if (label.includes("正常")) return "fresh";
  if (label.includes("延迟")) return "stale";
  if (label.includes("不可用") || label.includes("异常")) return "unavailable";
  return "partial";
}

function marketDataBasisLabel(value: string | null | undefined): string {
  const normalized = value ?? "";
  if (normalized.includes("formal")) return normalized.includes("blocked") ? "暂不可正式使用" : "正式可用";
  if (normalized.includes("analytical")) return "仅分析使用";
  if (normalized.includes("proxy")) return "代理数据";
  if (normalized.includes("mock")) return "演示数据";
  if (normalized.includes("source-pending")) return "未接入";
  if (normalized === "unknown" || normalized === "pending") return "待确认";
  return normalized || "--";
}

function marketDataSourceLabel(value: string | null | undefined): string {
  if (!value || value === "unknown") return "待确认";
  if (value === "source-pending" || value === "source_pending") return "未接入";
  return value;
}

function marketDataEvidenceLineLabel(line: string): string {
  return line
    .replace("formal rates:", "正式利率：")
    .replace("macro latest:", "宏观最新：")
    .replace("FX formal:", "外汇正式：")
    .replace("FX analytical:", "外汇分析：")
    .replace("NCD proxy:", "存单代理：")
    .replace("Livermore:", "利弗莫尔：")
    .replace("macro-bond linkage:", "宏观债券联动：")
    .replaceAll("basis=", "口径=")
    .replaceAll("formal_use_allowed=", "允许正式使用=")
    .replaceAll("quality=", "质量=")
    .replaceAll("fallback=", "数据状态=")
    .replaceAll("vendor_status=", "供应商=")
    .replaceAll("source=", "来源版本=")
    .replace(/=formal\b/g, "=正式")
    .replace(/=analytical\b/g, "=分析")
    .replace(/=pending\b/g, "=未接入")
    .replace(/=false\b/g, "=否")
    .replace(/=true\b/g, "=是")
    .replace(/=ok\b/g, "=数据正常")
    .replace(/=warning\b/g, "=部分缺失")
    .replace(/=stale\b/g, "=数据延迟")
    .replace(/=error\b/g, "=不可用")
    .replace(/=none\b/g, "=数据正常")
    .replace(/=latest_snapshot\b/g, "=数据延迟");
}

function coverageActionLabel(section: MarketDataCoverageSection): string {
  if (section.source_pending) return "接入数据源";
  if (section.proxy_only) return "确认正式口径";
  if (section.status === "deferred") return "按需展开";
  if (section.fallback_mode !== "none") return "查看数据延迟";
  return "查看详情";
}

function endpointCoverageStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    live: "已接入",
    loading: "接入中",
    error: "技术异常",
    "not read": "未接入",
    "source-pending": "未接入",
  };
  return labels[status] ?? status;
}

function coverageFallbackMode(value: ResultMeta["fallback_mode"] | undefined): "none" | "latest_snapshot" {
  return value === "latest_snapshot" ? "latest_snapshot" : "none";
}

function weekChangeBpText(sparklineValues: readonly number[]): string {
  if (sparklineValues.length < 6) {
    return "—";
  }
  const latest = sparklineValues[sparklineValues.length - 1];
  const weekAgo = sparklineValues[sparklineValues.length - 6];
  const bp = Math.round((latest - weekAgo) * 100);
  if (bp === 0) {
    return "0bp";
  }
  return `${bp > 0 ? "+" : ""}${bp}bp`;
}

function buildLedgerTickerStatusLabel(formalUseBlocked: boolean, isFormalBasis: boolean): string {
  if (formalUseBlocked) {
    return "正式禁用";
  }
  if (isFormalBasis) {
    return "正常";
  }
  return "混合来源";
}

const MARKET_DATA_LEDGER_TABS = [
  { key: "rates-macro", label: "利率与宏观", targetId: "market-data-ledger-first-grid" },
  { key: "funds-ncd", label: "资金/存单", targetId: "market-data-liquidity-deck" },
  { key: "fx", label: "外汇", targetId: "market-data-fx-formal-collapse" },
  { key: "trades-futures", label: "成交与期货", targetId: "market-data-extended-terminal-collapse" },
  { key: "evidence", label: "证据口径", targetId: "market-data-evidence-gate" },
] as const;

function MarketDataLedgerPageTabs({
  activeTab,
  onTabChange,
}: {
  activeTab: (typeof MARKET_DATA_LEDGER_TABS)[number]["key"];
  onTabChange: (key: (typeof MARKET_DATA_LEDGER_TABS)[number]["key"]) => void;
}) {
  return (
    <nav className="market-data-ledger-page-tabs" data-testid="market-data-ledger-page-tabs" aria-label="市场数据分区">
      {MARKET_DATA_LEDGER_TABS.map((tab) => (
        <button
          key={tab.key}
          type="button"
          data-testid={`market-data-ledger-tab-${tab.key}`}
          className={activeTab === tab.key ? "is-active" : undefined}
          aria-current={activeTab === tab.key ? "page" : undefined}
          onClick={() => {
            onTabChange(tab.key);
            document.getElementById(tab.targetId)?.scrollIntoView({ behavior: "smooth", block: "start" });
          }}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}

function countCoverageSections(
  sections: MarketDataCoverageSection[],
  predicate: (section: MarketDataCoverageSection) => boolean,
) {
  return sections.filter(predicate).length;
}

function MarketDataLedgerToolbar({
  clientMode: _clientMode,
  watchDate,
  tickerStatusDate,
  onWatchDateChange,
  isFormalBasis,
  readinessVerdict,
  overviewReadinessLabel,
  secondaryLabel,
  refreshStatus,
  refreshError,
  isRefreshing,
  onRefresh,
  curveFilter,
  onCurveFilterChange,
  creditSegment,
  onCreditSegmentChange,
  sourceFilter,
  onSourceFilterChange,
  activeFilterSummary,
  terminalTickerItems,
  terminalTickerEmptyReason,
  formalUseBlocked,
  ledgerPageTab,
  onLedgerPageTabChange,
  viewMode,
  onViewModeChange,
  catalogCount: _catalogCount,
}: {
  clientMode: "real" | "mock";
  watchDate: string;
  tickerStatusDate?: string | null;
  onWatchDateChange: (value: string) => void;
  isFormalBasis: boolean;
  readinessVerdict: string;
  overviewReadinessLabel: string;
  secondaryLabel: string;
  refreshStatus: string;
  refreshError: string;
  isRefreshing: boolean;
  onRefresh: () => void;
  curveFilter: "treasury" | "cdb" | "both";
  onCurveFilterChange: (value: "treasury" | "cdb" | "both") => void;
  creditSegment: "mtn" | "urban" | "both";
  onCreditSegmentChange: (value: "mtn" | "urban" | "both") => void;
  sourceFilter: "all" | "choice" | "internal";
  onSourceFilterChange: (value: "all" | "choice" | "internal") => void;
  activeFilterSummary: string;
  terminalTickerItems: readonly MarketTerminalTickerItem[];
  terminalTickerEmptyReason?: string;
  formalUseBlocked: boolean;
  ledgerPageTab: (typeof MARKET_DATA_LEDGER_TABS)[number]["key"];
  onLedgerPageTabChange: (key: (typeof MARKET_DATA_LEDGER_TABS)[number]["key"]) => void;
  viewMode: "default" | "compact";
  onViewModeChange: (value: "default" | "compact") => void;
  catalogCount: number;
}) {
  const tickerStatusLabel = buildLedgerTickerStatusLabel(formalUseBlocked, isFormalBasis);
  const formalBasisChipLabel = formalUseBlocked ? "暂不可正式使用" : isFormalBasis ? "正式" : "仅分析使用";

  return (
    <div className="market-data-ledger-chrome" data-testid="market-data-ledger-toolbar">
      <MarketTerminalTicker
        compact
        items={[...terminalTickerItems]}
        emptyReason={terminalTickerEmptyReason}
        statusDate={tickerStatusDate ?? undefined}
        statusLabel={tickerStatusLabel}
      />
      <header className="market-data-ledger-header">
        <div className="market-data-ledger-toolbar__title">
          <h1 data-testid="market-data-page-title">市场数据</h1>
          <span>MOSS</span>
          <p>利率、资金、外汇与成交数据总览与证据口径</p>
        </div>
        <div className="market-data-ledger-header__controls">
          <label className="market-data-filter-label">
            日期
            <input
              type="date"
              value={watchDate}
              onChange={(event) => onWatchDateChange(event.currentTarget.value)}
            />
          </label>
          <label className="market-data-filter-label">
            视图
            <Select
              value={viewMode}
              onChange={(value) => onViewModeChange(value)}
              options={[
                { value: "default", label: "默认视图" },
                { value: "compact", label: "紧凑视图" },
              ]}
              className="market-data-filter-select"
              data-testid="market-data-view-select"
            />
          </label>
          <button
            type="button"
            data-testid="market-data-export-button"
            disabled
            title="导出链路尚未接入，当前仅保留页面占位。"
          >
            导出
          </button>
          <button
            type="button"
            data-testid="market-data-refresh-button"
            disabled={isRefreshing}
            onClick={() => void onRefresh()}
          >
            {isRefreshing ? "刷新中" : "刷新"}
          </button>
        </div>
      </header>
      <MarketDataLedgerPageTabs activeTab={ledgerPageTab} onTabChange={onLedgerPageTabChange} />
      <div className="market-data-ledger-filter-row" data-testid="market-data-filter-strip">
        <label className="market-data-filter-label">
          国债 / 国开
          <Select
            value={curveFilter}
            onChange={(value) => onCurveFilterChange(value)}
            options={[
              { value: "treasury", label: "国债" },
              { value: "cdb", label: "国开" },
              { value: "both", label: "全部" },
            ]}
            className="market-data-filter-select"
          />
        </label>
        <label className="market-data-filter-label">
          中票 / 城投
          <Select
            value={creditSegment}
            onChange={(value) => onCreditSegmentChange(value)}
            options={[
              { value: "mtn", label: "中票" },
              { value: "urban", label: "城投" },
              { value: "both", label: "全部" },
            ]}
            className="market-data-filter-select"
          />
        </label>
        <label className="market-data-filter-label">
          来源
          <Select
            value={sourceFilter}
            onChange={(value) => onSourceFilterChange(value)}
            options={[
              { value: "all", label: "全部" },
              { value: "choice", label: "Choice" },
              { value: "internal", label: "内部" },
            ]}
            className="market-data-filter-select"
          />
        </label>
      </div>
      <div className="market-data-active-filter-summary" data-testid="market-data-active-filter-summary">
        当前生效：{activeFilterSummary}
      </div>
      <div className="market-data-ledger-status-strip" data-testid="market-data-data-status-strip">
        <span className="market-data-ledger-status-chip" data-testid="market-data-watch-date-slot">
          观察日期 {watchDate}
        </span>
        <span className="market-data-ledger-status-chip" data-testid="market-data-hero-readiness-chip">
          读面结论：{readinessVerdict}
        </span>
        <span className="market-data-ledger-status-chip" data-testid="market-data-formal-basis-chip">
          利率主表口径：{formalBasisChipLabel}
        </span>
        <span className="market-data-sr-only" data-testid="market-data-readiness-verdict">
          {readinessVerdict}
        </span>
        <span className="market-data-sr-only" data-testid="market-data-overview-readiness-label">
          {overviewReadinessLabel}
        </span>
        <span className="market-data-sr-only" data-testid="market-data-overview-secondary-label">
          {secondaryLabel}
        </span>
      </div>
      {refreshStatus || refreshError ? (
        <p className="market-data-ledger-refresh-note">{refreshError || refreshStatus}</p>
      ) : null}
    </div>
  );
}

function MarketDataSupplyEvidenceRail({
  summary,
  sections,
  watchDate,
}: {
  summary: MarketDataCoverageSummaryPayload | null;
  sections: MarketDataCoverageSection[];
  watchDate: string;
}) {
  const formalCount = countCoverageSections(
    sections,
    (section) => section.basis === "formal" && section.formal_use_allowed,
  );
  const analyticalCount = countCoverageSections(
    sections,
    (section) => section.basis === "analytical" && !section.proxy_only && !section.source_pending,
  );
  const proxyCount =
    summary?.headline.proxy_only_count ??
    countCoverageSections(sections, (section) => section.proxy_only || section.status === "proxy_only");
  const sourcePendingCount =
    summary?.headline.source_pending_count ??
    countCoverageSections(sections, (section) => section.source_pending || section.status === "source_pending");
  const staleCount = countCoverageSections(sections, (section) => section.status === "stale");
  const errorCount = countCoverageSections(sections, (section) => section.status === "error");
  const nextActions = sections
    .filter((section) => section.source_pending || section.proxy_only || section.status === "source_pending")
    .slice(0, 3);

  if (sections.length === 0) {
    return (
      <aside className="market-data-supply-evidence-rail" data-testid="market-data-supply-evidence-rail">
        <div className="market-data-rail-skeleton">
          <div className="market-data-rail-skeleton-item" />
          <div className="market-data-rail-skeleton-item" />
          <div className="market-data-rail-skeleton-item" />
          <div className="market-data-rail-skeleton-item" />
        </div>
      </aside>
    );
  }

  return (
    <aside className="market-data-supply-evidence-rail" data-testid="market-data-supply-evidence-rail">
      <section className="market-data-supply-panel">
        <header className="market-data-panel-head">
          <span>证据口径总览</span>
          <strong>供给证据</strong>
        </header>
        <div className="market-data-supply-evidence-list">
          <article data-testid="market-data-coverage-bucket-formal-ready" data-tone="formal">
            <span>正式口径</span>
            <strong>{formalCount}</strong>
            <small>可正式使用</small>
          </article>
          <article data-testid="market-data-coverage-bucket-analytical-usable" data-tone="analytical">
            <span>分析口径</span>
            <strong>{analyticalCount}</strong>
            <small>用于辅助观察</small>
          </article>
          <article data-testid="market-data-coverage-bucket-proxy-only" data-tone="proxy">
            <span>代理数据</span>
            <strong>{proxyCount}</strong>
            <small>不作正式结论</small>
          </article>
          <article data-testid="market-data-coverage-bucket-source-pending" data-tone="pending">
            <span>未接入</span>
            <strong>{sourcePendingCount}</strong>
            <small>数据源未闭合</small>
          </article>
          <article data-tone="stale">
            <span>数据延迟</span>
            <strong>{staleCount}</strong>
          </article>
          <article data-tone="error">
            <span>不可用</span>
            <strong>{errorCount}</strong>
          </article>
        </div>
      </section>
      <section className="market-data-supply-panel market-data-supply-meta">
        <div>
          <span>报告日期</span>
          <strong>{summary?.as_of_date ?? watchDate}</strong>
        </div>
        <div>
          <span>数据时间</span>
          <strong>{summary?.as_of_date ?? watchDate}</strong>
        </div>
        <div>
          <span>生成时间</span>
          <strong>{summary?.generated_at?.replace("T", " ").slice(0, 19) ?? "--"}</strong>
        </div>
      </section>
      <section className="market-data-supply-panel">
        <header className="market-data-panel-head">
          <span>下一步行动</span>
          <strong>下一步动作</strong>
        </header>
        <ol className="market-data-next-action-list">
          {nextActions.map((section) => (
            <li key={section.key}>
              <span>{coverageActionLabel(section)}</span>
              <DataQualityPill raw={section.status} label={coverageStatusLabel(section.status)} />
            </li>
          ))}
        </ol>
        <p className="market-data-supply-note">
          提示：本页为混合来源；正式使用以“允许正式使用”且“质量正常”的数据区块为准。
        </p>
      </section>
    </aside>
  );
}

function MarketDataFormalRatesBoard({
  model,
  curveFilter,
  sourceFilter,
  catalogVendorNames,
  keyMetrics,
  ratesBasisLabel,
  formalUseBlocked,
}: {
  model: MarketDataRateQuoteSection;
  curveFilter: "treasury" | "cdb" | "both";
  sourceFilter: "all" | "choice" | "internal";
  catalogVendorNames: ReadonlyMap<string, string>;
  keyMetrics: readonly MarketOverviewMetric[];
  ratesBasisLabel: string;
  formalUseBlocked: boolean;
}) {
  const rows = filterRateQuoteRows(model.rows, curveFilter, sourceFilter, catalogVendorNames).slice(0, 8);
  const hasRows = model.status === "ready" && rows.length > 0;
  return (
    <section
      id="market-data-term-structure"
      className="market-data-formal-rates-board"
      data-testid="market-data-formal-rates-board"
    >
      <header className="market-data-formal-rates-head">
        <div>
          <span>利率行情</span>
          <h2>正式利率</h2>
          <small>利率曲线与宏观深度</small>
        </div>
        <a href="#market-data-evidence-gate">查看完整曲线</a>
      </header>
      <div className="market-data-workbench-shared-meta" data-testid="market-data-workbench-shared-meta">
        <span>口径摘要 {marketDataBasisLabel(ratesBasisLabel)}</span>
        {formalUseBlocked ? <span>禁止作为正式口径</span> : null}
        {curveFilter !== "both" && (
          <span className="market-data-sr-only" data-testid="market-data-rate-curve-lock">
            {curveFilter === "treasury" ? "国债曲线" : "国开曲线"}
          </span>
        )}
      </div>
      <div className="market-data-formal-rates-grid" data-testid="market-data-rate-quote-card">
        <section className="market-data-formal-rate-panel" data-testid="market-data-rate-quote-table">
          <header>
            <strong>国债收益率曲线（中债）</strong>
            <span data-testid="market-data-rate-quote-view-toggle">并列 / 表格 / 曲线</span>
          </header>
          <table data-testid="market-data-formal-rates-table">
            <thead>
              <tr>
                <th>期限</th>
                <th>最新（%）</th>
                <th>日变动 bp</th>
                <th>周变动 bp</th>
              </tr>
            </thead>
            <tbody>
              {hasRows
                ? rows.map((row) => (
                    <tr key={row.key}>
                      <td>
                        <strong>{row.tenor}</strong>
                        <small>{row.variety}</small>
                      </td>
                      <td>{row.rateText}</td>
                      <td>{row.deltaText}</td>
                      <td>{weekChangeBpText(row.sparklineValues)}</td>
                    </tr>
                  ))
                : (
                    <tr>
                      <td colSpan={4}>
                        <div data-testid="market-data-rate-quotes-empty" className="market-data-terminal-empty">
                          {model.emptyReason}
                        </div>
                      </td>
                    </tr>
                  )}
            </tbody>
          </table>
        </section>
        <section className="market-data-formal-rate-panel" data-testid="market-data-formal-rates-curve">
          <header>
            <strong>国债收益率曲线（中债）</strong>
            <span>单位：%</span>
          </header>
          <MarketDataTermStructureChart
            model={model}
            curveFilter={curveFilter}
            sourceFilter={sourceFilter}
            catalogVendorNames={catalogVendorNames}
            activeCurve={curveFilter}
            height={210}
          />
        </section>
        <section className="market-data-formal-rate-panel" data-testid="market-data-key-rate-list">
          <header>
            <strong>关键利率 / 资金指标</strong>
            <span>最新</span>
          </header>
          <div className="market-data-key-rate-list">
            {keyMetrics.slice(0, 7).map((metric) => (
              <article key={metric.testId} data-testid={`market-data-key-rate-${metric.testId}`}>
                <span>{metric.title}</span>
                <strong>{metric.value}</strong>
                <em>{metric.detail.split(" · ")[0]}</em>
              </article>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}

function MarketDataSurfacePreviewBand({
  clientMode,
  catalog,
  latestSeries,
  latestSeriesIsLoading,
  latestSeriesIsError,
  formalRateSeries,
  terminalModel,
  fxFormalStatus,
  fxAnalyticalGroups,
  watchDate,
  readinessVerdict,
  ratesBasisLabel,
  formalRatesSeriesCount,
  formalRatesMeta,
  fxFormalMeta,
  fxAnalyticalMeta,
  ncdFundingProxy,
  ncdFundingProxyMeta,
  livermoreStrategy,
  livermoreMeta,
  livermoreIsLoading,
  livermoreIsError,
  livermoreSignalConfluence,
  livermoreSignalConfluenceMeta,
  livermoreSignalConfluenceIsLoading,
  livermoreSignalConfluenceIsError,
  livermoreStrategyScore,
  livermoreStrategyScoreMeta,
  livermoreStrategyScoreIsLoading,
  livermoreStrategyScoreIsError,
  livermoreSectorRankSeries,
  livermoreSectorRankSeriesMeta,
  livermoreSectorRankSeriesIsLoading,
  livermoreSectorRankSeriesIsError,
  livermoreCandidateHistory,
  livermoreCandidateHistoryMeta,
  livermoreCandidateHistoryIsLoading,
  livermoreCandidateHistoryIsError,
  livermoreStrategyOptimization,
  livermoreStrategyOptimizationMeta,
  livermoreStrategyOptimizationIsLoading,
  livermoreStrategyOptimizationIsError,
  livermoreCycleProxyBacktest,
  livermoreCycleProxyBacktestMeta,
  livermoreCycleProxyBacktestIsLoading,
  livermoreCycleProxyBacktestIsError,
  livermorePortfolioBacktest,
  livermorePortfolioBacktestMeta,
  livermorePortfolioBacktestIsLoading,
  livermorePortfolioBacktestIsError,
  tushareSupplement,
  tushareSupplementMeta,
  tushareSupplementIsLoading,
  tushareSupplementIsError,
  macroToolkitAnalysis,
  macroToolkitAnalysisMeta,
  macroToolkitAnalysisIsLoading,
  macroToolkitAnalysisIsError,
  coverageSummary,
  coverageSummaryMeta,
  coverageSummaryIsLoading,
  coverageSummaryIsError,
  sourceFilter,
  catalogVendorNames,
  newsPayload,
  newsIsLoading,
  newsIsError,
  calendarRows,
  calendarIsLoading,
  calendarIsError,
}: {
  clientMode: string;
  catalog: MacroVendorPayload["series"];
  latestSeries: ChoiceMacroLatestPoint[];
  latestSeriesIsLoading?: boolean;
  latestSeriesIsError?: boolean;
  formalRateSeries: ChoiceMacroLatestPoint[];
  terminalModel: MarketDataTerminalModel;
  fxFormalStatus: FxFormalStatusPayload | null;
  fxAnalyticalGroups: FxAnalyticalPayload["groups"];
  watchDate: string;
  readinessVerdict: string;
  ratesBasisLabel: string;
  formalRatesSeriesCount: number | null;
  formalRatesMeta?: ResultMeta;
  fxFormalMeta?: ResultMeta;
  fxAnalyticalMeta?: ResultMeta;
  ncdFundingProxy?: NcdFundingProxyPayload | null;
  ncdFundingProxyMeta?: ResultMeta;
  livermoreStrategy?: LivermoreStrategyModel | null;
  livermoreMeta?: ResultMeta;
  livermoreIsLoading: boolean;
  livermoreIsError: boolean;
  livermoreSignalConfluence?: LivermoreSignalConfluencePayload | null;
  livermoreSignalConfluenceMeta?: ResultMeta;
  livermoreSignalConfluenceIsLoading?: boolean;
  livermoreSignalConfluenceIsError?: boolean;
  livermoreStrategyScore?: LivermoreStrategyScorePayload | null;
  livermoreStrategyScoreMeta?: ResultMeta;
  livermoreStrategyScoreIsLoading?: boolean;
  livermoreStrategyScoreIsError?: boolean;
  livermoreSectorRankSeries?: LivermoreSectorRankSeriesPayload | null;
  livermoreSectorRankSeriesMeta?: ResultMeta;
  livermoreSectorRankSeriesIsLoading?: boolean;
  livermoreSectorRankSeriesIsError?: boolean;
  livermoreCandidateHistory?: LivermoreCandidateHistoryPayload | null;
  livermoreCandidateHistoryMeta?: ResultMeta;
  livermoreCandidateHistoryIsLoading?: boolean;
  livermoreCandidateHistoryIsError?: boolean;
  livermoreStrategyOptimization?: LivermoreStrategyOptimizationPayload | null;
  livermoreStrategyOptimizationMeta?: ResultMeta;
  livermoreStrategyOptimizationIsLoading?: boolean;
  livermoreStrategyOptimizationIsError?: boolean;
  livermoreCycleProxyBacktest?: LivermoreCycleProxyBacktestPayload | null;
  livermoreCycleProxyBacktestMeta?: ResultMeta;
  livermoreCycleProxyBacktestIsLoading?: boolean;
  livermoreCycleProxyBacktestIsError?: boolean;
  livermorePortfolioBacktest?: LivermoreCandidateHistoryPortfolioBacktestPayload | null;
  livermorePortfolioBacktestMeta?: ResultMeta;
  livermorePortfolioBacktestIsLoading?: boolean;
  livermorePortfolioBacktestIsError?: boolean;
  tushareSupplement?: TushareSupplementPayload | null;
  tushareSupplementMeta?: ResultMeta;
  tushareSupplementIsLoading?: boolean;
  tushareSupplementIsError?: boolean;
  macroToolkitAnalysis?: MacroToolkitAnalysisPayload | null;
  macroToolkitAnalysisMeta?: ResultMeta;
  macroToolkitAnalysisIsLoading?: boolean;
  macroToolkitAnalysisIsError?: boolean;
  coverageSummary?: MarketDataCoverageSummaryPayload | null;
  coverageSummaryMeta?: ResultMeta;
  coverageSummaryIsLoading?: boolean;
  coverageSummaryIsError?: boolean;
  sourceFilter: "all" | "choice" | "internal";
  catalogVendorNames: ReadonlyMap<string, string>;
  newsPayload: ChoiceNewsEventsPayload | null;
  newsIsLoading: boolean;
  newsIsError: boolean;
  calendarRows: readonly ResearchCalendarEvent[];
  calendarIsLoading: boolean;
  calendarIsError: boolean;
}) {
  const cockpit = buildMarketDataTapeCockpitModel({
    catalog,
    latestSeries,
    latestSeriesIsLoading,
    latestSeriesIsError,
    formalRateSeries,
    terminalModel,
    fxFormalStatus,
    fxAnalyticalGroups,
    watchDate,
    ratesBasisLabel,
    formalRatesSeriesCount,
    formalRatesMeta,
    fxFormalMeta,
    fxAnalyticalMeta,
    ncdFundingProxy,
    ncdFundingProxyMeta,
    livermoreStrategy,
    livermoreMeta,
    livermoreIsLoading,
    livermoreIsError,
    livermoreSignalConfluence,
    livermoreSignalConfluenceMeta,
    livermoreSignalConfluenceIsLoading,
    livermoreSignalConfluenceIsError,
    livermoreStrategyScore,
    livermoreStrategyScoreMeta,
    livermoreStrategyScoreIsLoading,
    livermoreStrategyScoreIsError,
    livermoreSectorRankSeries,
    livermoreSectorRankSeriesMeta,
    livermoreSectorRankSeriesIsLoading,
    livermoreSectorRankSeriesIsError,
    livermoreCandidateHistory,
    livermoreCandidateHistoryMeta,
    livermoreCandidateHistoryIsLoading,
    livermoreCandidateHistoryIsError,
    livermoreStrategyOptimization,
    livermoreStrategyOptimizationMeta,
    livermoreStrategyOptimizationIsLoading,
    livermoreStrategyOptimizationIsError,
    livermoreCycleProxyBacktest,
    livermoreCycleProxyBacktestMeta,
    livermoreCycleProxyBacktestIsLoading,
    livermoreCycleProxyBacktestIsError,
    livermorePortfolioBacktest,
    livermorePortfolioBacktestMeta,
    livermorePortfolioBacktestIsLoading,
    livermorePortfolioBacktestIsError,
    tushareSupplement,
    tushareSupplementMeta,
    tushareSupplementIsLoading,
    tushareSupplementIsError,
    macroToolkitAnalysis,
    macroToolkitAnalysisMeta,
    macroToolkitAnalysisIsLoading,
    macroToolkitAnalysisIsError,
    coverageSummary,
    coverageSummaryMeta,
    coverageSummaryIsLoading,
    coverageSummaryIsError,
    newsPayload,
    newsIsLoading,
    newsIsError,
    calendarRows,
    calendarIsLoading,
    calendarIsError,
  });
  const {
    topbarUpdatedAt,
    overviewStats,
    formalDomainRows,
    analyticalRows,
    sourceGapRows,
    newsEventRows,
    calendarEventRows,
    sourceLedgerRows,
    keyRateTiles,
    moneyRows,
    fundingCurveSeries,
    fxRows,
    macroLatestRows,
    ncdProxyRows,
    livermoreDeepRows,
    tushareSupplementRows,
    tushareSignalTiles,
    externalComparisonPlacements,
    macroToolkitRows,
    endpointCoverageRows,
  } = cockpit;

  return (
    <section
      className="market-data-surface-preview-band market-data-overview-board"
      data-variant="data-overview"
      data-testid="market-data-surface-preview-band"
    >
      <div className="market-data-overview-board__topbar" aria-label="市场数据全览工具栏">
        <div className="market-data-overview-board__brand">
          <LightIcon name="unordered-list" aria-hidden="true" />
          <strong>MOSS</strong>
          <span>市场数据 / Market Data</span>
        </div>
        <dl className="market-data-overview-board__meta">
          <div>
            <dt>观察日</dt>
            <dd><LightIcon name="calendar" aria-hidden="true" />{watchDate || "--"}</dd>
          </div>
          <div>
            <dt>来源模式</dt>
            <dd>
              <LightIcon name="database" aria-hidden="true" />
              <DataSourceBadge raw={clientMode === "mock" ? "mock" : "formal"} />
            </dd>
          </div>
          <div>
            <dt>状态</dt>
            <dd>
              <LightIcon name="safety-certificate" aria-hidden="true" />
              <DataQualityPill
                status={dataQualityStatusForReadiness(readinessVerdict)}
                label={readinessVerdict}
              />
            </dd>
          </div>
          <div>
            <dt>刷新</dt>
            <dd><LightIcon name="reload" aria-hidden="true" />{topbarUpdatedAt}</dd>
          </div>
        </dl>
      </div>

      <header className="market-data-overview-board__head">
        <div className="market-data-overview-board__title">
          <span>数据全览</span>
          <strong>数据源健康</strong>
        </div>
        <div className="market-data-overview-board__stats" aria-label="市场数据全览指标">
          {overviewStats.map((item) => (
            <article key={item.key} data-key={item.key} data-tone={item.tone}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
              {item.unit ? <em>{item.unit}</em> : null}
              {item.detail ? <small>{item.detail}</small> : null}
            </article>
          ))}
        </div>
      </header>

      <div className="market-data-overview-board__primary" data-testid="market-data-primary-cockpit">
        <div className="market-data-overview-board__grid">
          <section className="market-data-overview-card market-data-overview-card--formal">
          <header>
            <strong>1. 正式可用</strong>
          </header>
          <div className="market-data-overview-domain-table">
            <div className="market-data-overview-domain-table__head">
              <span>数据域 / Data Domain</span>
              <span>状态</span>
              <span>规模 / Count</span>
              <span>最新日期</span>
            </div>
            {formalDomainRows.map((row) => (
              <article key={row.key} data-tone={row.tone} data-testid={row.key === "formal-rates" ? "market-data-preview-formal-rates" : row.key === "fx-formal" ? "market-data-preview-fx-formal" : undefined}>
                <div>
                  <strong>{row.lane}</strong>
                  <small>{row.subLabel}</small>
                </div>
                <b>{row.status}</b>
                <em>{row.count}</em>
                <time>{row.date}</time>
                <p>{row.note}</p>
              </article>
            ))}
          </div>
          <footer>
            <LightIcon name="check-circle" aria-hidden="true" />
            <span>以上数据可用于正式分析与报告（部分维度可能带回退）。</span>
          </footer>
        </section>

          <section className="market-data-overview-card market-data-overview-card--market" data-testid="market-data-market-canvas">
          <header>
            <strong>2. 市场速览 / Market Tape & Curves</strong>
            <span>{watchDate || "--"}</span>
          </header>
          <div className="market-data-overview-rate-strip">
            {keyRateTiles.map((tile) => (
              <div key={tile.key}>
                <span>{tile.label}</span>
                <strong>{tile.value}</strong>
                <em>{tile.delta}</em>
              </div>
            ))}
          </div>
          <div className="market-data-overview-curve-grid">
            <section className="market-data-overview-curve-card" data-testid="market-data-preview-money-market">
              <h3>资金利率曲线（关键期限，%）</h3>
              {fundingCurveSeries ? (
                <MarketDataSeriesTimeChart
                  series={fundingCurveSeries}
                  height={142}
                  testId="market-data-funding-curve-chart"
                  variant="sheet"
                />
              ) : (
                <div className="market-data-overview-empty-chart">资金曲线暂无可绘制时间序列</div>
              )}
              <ul>
                {moneyRows.length > 0 ? (
                  moneyRows.slice(0, 3).map((row) => (
                    <li key={row.key}>
                      <span>{row.name}</span>
                      <strong>{row.rateText}</strong>
                      <em>{row.deltaText}</em>
                    </li>
                  ))
                ) : (
                  <li>
                    <span>资金利率</span>
                    <strong>{terminalModel.moneyMarket.emptyReason}</strong>
                    <em>--</em>
                  </li>
                )}
              </ul>
            </section>
            <section className="market-data-overview-curve-card">
              <h3>国债收益率曲线（中债，%）</h3>
              <MarketDataTermStructureChart
                model={terminalModel.rateQuotes}
                curveFilter="treasury"
                sourceFilter={sourceFilter}
                catalogVendorNames={catalogVendorNames}
                activeCurve="treasury"
                height={142}
                variant="sheet"
                testId="market-data-government-bond-curve-chart"
                emptyTestId="market-data-government-bond-curve-empty"
              />
              <ul>
                {keyRateTiles.slice(0, 3).map((tile) => (
                  <li key={tile.key}>
                    <span>{tile.label}</span>
                    <strong>{tile.value}</strong>
                    <em>{tile.delta}</em>
                  </li>
                ))}
              </ul>
            </section>
          </div>
          <div className="market-data-overview-events" data-testid="market-data-preview-news-calendar">
            <section>
              <header>
                <strong>市场资讯（最新 3 条）</strong>
                <span>查看全部 {newsPayload?.total_rows ?? 0} 条</span>
              </header>
              <ol>
                {newsEventRows.length > 0 ? (
                  newsEventRows.map((event) => (
                    <li key={event.key}>
                      <time>{event.time}</time>
                      <span>{event.label}</span>
                      <strong>{event.text}</strong>
                    </li>
                  ))
                ) : (
                  <li><time>--</time><span>空</span><strong>资讯暂未返回</strong></li>
                )}
              </ol>
            </section>
            <section>
              <header>
                <strong>供给 / 招标日历（未来 3 条）</strong>
                <span>查看全部 {calendarRows.length} 条</span>
              </header>
              <ol>
                {calendarEventRows.length > 0 ? (
                  calendarEventRows.map((event) => (
                    <li key={event.key}>
                      <time>{event.time}</time>
                      <span>{event.label}</span>
                      <strong>{event.text}</strong>
                    </li>
                  ))
                ) : (
                  <li><time>--</time><span>空</span><strong>日历暂未返回</strong></li>
                )}
              </ol>
            </section>
          </div>
          <section className="market-data-overview-tushare-signals" data-testid="market-data-tushare-signal-strip">
            <header>
              <strong>Tushare 外部信号</strong>
              <span>分析口径 · 非正式指标</span>
            </header>
            <div className="market-data-overview-tushare-signals__grid">
              {tushareSignalTiles.map((tile) => (
                <article key={tile.key} data-tone={tile.tone} data-testid={`market-data-tushare-signal-${tile.key}`}>
                  <span>{tile.label}</span>
                  <strong>{tile.value}</strong>
                  <em>{tile.detail}</em>
                </article>
              ))}
            </div>
          </section>
          <section className="market-data-overview-external-map" data-testid="market-data-external-comparison-map">
            <header>
              <strong>External Comparison Map</strong>
              <span>Analytical placement only</span>
            </header>
            <div className="market-data-overview-external-map__rows">
              {externalComparisonPlacements.map((row) => (
                <article key={row.key} data-tone={row.tone} data-testid={`market-data-external-map-${row.key}`}>
                  <div>
                    <strong>{row.dataset}</strong>
                    <small>{row.targetSurface}</small>
                  </div>
                  <span>{row.compareWith}</span>
                  <em>{row.evidence}</em>
                  <time>{row.dateText}</time>
                  <b>{row.statusText}</b>
                </article>
              ))}
            </div>
          </section>
        </section>

          <aside className="market-data-overview-side">
          <section className="market-data-overview-card market-data-overview-card--side" data-testid="market-data-preview-macro-inventory">
            <header>
              <strong>3. 分析与代理数据</strong>
            </header>
            <ul className="market-data-overview-side-list">
              {analyticalRows.map((row) => (
                <li key={row.key} data-tone={row.tone}>
                  <div>
                    <strong>{row.label}</strong>
                    <small>{row.subLabel}</small>
                  </div>
                  <b>{row.badge}</b>
                  <em>{row.count}</em>
                  <time>{row.date}</time>
                  <p>{row.note}</p>
                </li>
              ))}
            </ul>
          </section>

          <section className="market-data-overview-card market-data-overview-card--side market-data-overview-card--gaps" data-testid="market-data-preview-trades-futures">
            <header>
              <strong>4. 数据缺口</strong>
            </header>
            <ul className="market-data-overview-gap-list">
              {sourceGapRows.map((row) => (
                <li key={row.key}>
                  <div>
                    <strong>{row.label}</strong>
                    <small>{row.subLabel}</small>
                  </div>
                  <b>{row.badge}</b>
                  <em>{row.code}</em>
                  <span>{row.status}</span>
                </li>
              ))}
            </ul>
            <p>以上数据源暂未接入，后续上线将进入正式数据链路。</p>
          </section>
          </aside>
        </div>
      </div>

      <DiagnosticDisclosure
        className="market-data-overview-diagnostic"
        summary="查看数据诊断"
        testId="market-data-endpoint-diagnostic"
      >
      <section className="market-data-overview-api-surface" data-testid="market-data-endpoint-coverage">
        <header>
          <strong>数据端点覆盖</strong>
          <span>{endpointCoverageRows.filter((row) => row.status === "已接入").length} / {endpointCoverageRows.length} 已接入</span>
        </header>
        <div>
          {endpointCoverageRows.map((row) => (
            <article key={row.key} data-tone={row.tone} data-status={row.status}>
              <div>
                <strong>{row.label}</strong>
                <span>{row.endpoint}</span>
              </div>
              <SystemAccessBadge raw={row.status} label={endpointCoverageStatusLabel(row.status)} />
              <em>{row.count}</em>
              <time>{row.date}</time>
              <p>{row.note}</p>
            </article>
          ))}
        </div>
      </section>
      </DiagnosticDisclosure>

      <div className="market-data-overview-tape-grid" data-testid="market-data-cross-market-tape">
        <section data-testid="market-data-preview-fx-tape">
          <header>
            <strong>6. FX Spot</strong>
            <span>{fxRows.length} 对</span>
          </header>
          <ol>
            {fxRows.length > 0 ? (
              fxRows.map((row) => (
                <li key={row.key}>
                  <span>{row.pairLabel}</span>
                  <strong>{row.rateText}</strong>
                  <em>{row.statusText}</em>
                  <time>{row.dateText}</time>
                </li>
              ))
            ) : (
              <li><span>FX</span><strong>--</strong><em>无</em><time>--</time></li>
            )}
          </ol>
        </section>
        <section data-testid="market-data-preview-macro-tape">
          <header>
            <strong>7. Macro Latest</strong>
            <span>{macroLatestRows.length} / {latestSeries.length}</span>
          </header>
          <ol>
            {macroLatestRows.length > 0 ? (
              macroLatestRows.map((row) => (
                <li key={row.key}>
                  <span>{row.name}</span>
                  <strong>{row.valueText}</strong>
                  <em>{row.deltaText}</em>
                  <time>{row.tierText}</time>
                </li>
              ))
            ) : (
              <li><span>Macro</span><strong>--</strong><em>无</em><time>--</time></li>
            )}
          </ol>
        </section>
        <section data-testid="market-data-preview-ncd-tape">
          <header>
            <strong>8. NCD / Funding Proxy</strong>
            <span>{ncdProxyRows.length} 行</span>
          </header>
          <ol>
            {ncdProxyRows.length > 0 ? (
              ncdProxyRows.map((row) => (
                <li key={row.key}>
                  <span>{row.label}</span>
                  <strong>{row.threeMonthText}</strong>
                  <em>{row.oneYearText}</em>
                  <time>{row.quoteCountText}</time>
                </li>
              ))
            ) : (
              <li><span>NCD</span><strong>--</strong><em>--</em><time>--</time></li>
            )}
          </ol>
        </section>
        <section data-testid="market-data-preview-livermore-deep-tape">
          <header>
            <strong>9. Livermore Deep Reads</strong>
            <span>
              {livermoreDeepRows.filter((row) => row.statusText === "已接入").length} / {livermoreDeepRows.length}
            </span>
          </header>
          <ol>
            {livermoreDeepRows.map((row) => (
              <li key={row.key} data-tone={row.tone}>
                <span>{row.label}</span>
                <strong>{row.countText}</strong>
                <em>{endpointCoverageStatusLabel(row.statusText)}</em>
                <time>{row.dateText}</time>
              </li>
            ))}
          </ol>
        </section>
        <section data-testid="market-data-preview-tushare-tape">
          <header>
            <strong>10. Tushare Macro</strong>
            <span>
              {tushareSupplementRows.filter((row) => row.statusText === "已接入").length} / {tushareSupplementRows.length}
            </span>
          </header>
          <ol>
            {tushareSupplementRows.map((row) => (
              <li key={row.key} data-tone={row.tone}>
                <span>{row.label}</span>
                <strong>{row.countText}</strong>
                <em>{endpointCoverageStatusLabel(row.statusText)}</em>
                <time>{row.dateText}</time>
              </li>
            ))}
          </ol>
        </section>
        <section data-testid="market-data-preview-macro-toolkit-tape">
          <header>
            <strong>11. Macro Toolkit</strong>
            <span>
              {macroToolkitRows.filter((row) => row.tone === "analytical").length} / {macroToolkitRows.length}
            </span>
          </header>
          <ol>
            {macroToolkitRows.map((row) => (
              <li key={row.key} data-tone={row.tone}>
                <span>{row.label}</span>
                <strong>{row.countText}</strong>
                <em>{row.statusText}</em>
                <time>{row.dateText}</time>
              </li>
            ))}
          </ol>
        </section>
      </div>

      <div className="market-data-overview-ledger-row">
        <section className="market-data-overview-ledger">
          <header>
            <strong>12. 数据来源与证据台账</strong>
          </header>
          <table>
            <thead>
              <tr>
                <th>来源</th>
                <th>数据域</th>
                <th>技术路径</th>
                <th>基础</th>
                <th>正式使用允许</th>
                <th>质量</th>
                <th>回退说明</th>
                <th>最新数据时间</th>
                <th>观察日</th>
                <th>备注</th>
              </tr>
            </thead>
            <tbody>
              {sourceLedgerRows.map((row) => (
                <tr key={row.key}>
                  <td>{row.source}</td>
                  <td>{row.domain}</td>
                  <td>{row.endpoint}</td>
                  <td>{row.basis}</td>
                  <td>{row.formalAllowed}</td>
                  <td>{row.quality}</td>
                  <td>{row.fallback}</td>
                  <td>{row.latest}</td>
                  <td>{row.date}</td>
                  <td>{row.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>

      <span className="market-data-sr-only" data-testid="market-data-preview-source-summary">
        数据全览：正式可用 6；仅分析使用；代理数据；未接入 2；覆盖指标 {overviewStats.find((item) => item.key === "coverage")?.value}
      </span>
    </section>
  );
}
export default function MarketDataPage() {
  const client = useApiClient();
  const [, setLivermoreExpanded] = useState(false);
  const [linkageCollapseExpanded, setLinkageCollapseExpanded] = useState(false);
  const lazyExtended = useLazyMount({ rootMargin: "300px", fallbackDelayMs: 0 });
  const lazySupplementary = useLazyMount({ rootMargin: "300px", fallbackDelayMs: 0 });
  const [macroDepthTab, setMacroDepthTab] = useState<"curve" | "spreads" | "linkage">("curve");
  const [ledgerPageTab, setLedgerPageTab] = useState<(typeof MARKET_DATA_LEDGER_TABS)[number]["key"]>("rates-macro");
  const [viewMode, setViewMode] = useState<"default" | "compact">("default");
  const [curveFilter, setCurveFilter] = useState<"treasury" | "cdb" | "both">("both");
  const [creditSegment, setCreditSegment] = useState<"mtn" | "urban" | "both">("both");
  const [sourceFilter, setSourceFilter] = useState<"all" | "choice" | "internal">("all");
  const linkageFetchEnabled =
    linkageCollapseExpanded ||
    macroDepthTab === "spreads" ||
    macroDepthTab === "linkage" ||
    creditSegment !== "both";
  const {
    clientMode,
    watchDate,
    setWatchDate,
    isRefreshing,
    refreshStatus,
    refreshError,
    handleRefresh,
    pageModel,
    catalogQuery,
    latestQuery,
    fxAnalyticalQuery,
    fxFormalStatusQuery,
    ncdFundingProxyQuery,
    coverageSummaryQuery,
    livermoreStrategyQuery,
    formalRatesQuery,
    macroBondLinkageQuery,
    ncdFundingProxy,
    refreshGateSupplement,
  } = useMarketDataPageData({
    livermoreEnabled: true,
    linkageEnabled: linkageFetchEnabled,
  });
  const calendarQuery = useQuery({
    queryKey: ["market-data", "calendar", "supply-auctions", client.mode],
    queryFn: () => client.getResearchCalendarEvents({}),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "stable", fetch_mode: "date_slice" }),
  });
  const newsQuery = useQuery({
    queryKey: ["market-data", "headlines", "choice-events", client.mode],
    queryFn: () => client.getChoiceNewsEvents({ limit: 12, offset: 0 }),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "stable", fetch_mode: "date_slice" }),
  });
  const livermoreSignalConfluenceQuery = useQuery({
    queryKey: ["market-data", "livermore-signal-confluence", client.mode, watchDate],
    queryFn: () => client.getLivermoreSignalConfluence({ asOfDate: watchDate }),
    enabled: Boolean(watchDate),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
  });
  const livermoreStrategyScoreQuery = useQuery({
    queryKey: ["market-data", "livermore-strategy-score", client.mode],
    queryFn: () => client.getLivermoreStrategyScore(),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
  });
  const livermoreSectorRankSeriesQuery = useQuery({
    queryKey: ["market-data", "livermore-sector-rank-series", client.mode, watchDate],
    queryFn: () => client.getLivermoreSectorRankSeries({ asOfDate: watchDate, topK: 5 }),
    enabled: Boolean(watchDate),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
  });
  const livermoreCandidateHistoryQuery = useQuery({
    queryKey: ["market-data", "livermore-candidate-history", client.mode],
    queryFn: () => client.getLivermoreCandidateHistory({ limit: 40 }),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
  });
  const livermoreStrategyOptimizationQuery = useQuery({
    queryKey: ["market-data", "livermore-strategy-optimization", client.mode],
    queryFn: () => client.getLivermoreStrategyOptimization(),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
  });
  const livermoreCycleProxyBacktestQuery = useQuery({
    queryKey: ["market-data", "livermore-cycle-proxy-backtest", client.mode],
    queryFn: () => client.getLivermoreCycleProxyBacktest(),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
  });
  const livermorePortfolioBacktestQuery = useQuery({
    queryKey: ["market-data", "livermore-portfolio-backtest", client.mode],
    queryFn: () => client.getLivermoreCandidateHistoryPortfolioBacktest(),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
  });
  const tushareSupplementQuery = useQuery({
    queryKey: ["market-data", "tushare-supplement", client.mode],
    queryFn: () => client.getTushareSupplement({ moneySupplyLimit: 12, ecoCalLimit: 30 }),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
  });
  const macroToolkitAnalysisQuery = useQuery({
    queryKey: ["market-data", "macro-toolkit-analysis-core", client.mode],
    queryFn: () => client.getMacroToolkitAnalysis({ detail: "core" }),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
  });
  const {
    catalog,
    stableSeries,
    fallbackSeries,
    missingStableSeries,
    linkageReportDate,
    vendorVersions,
    terminalModel,
    coverageSummary,
    coverageSections,
    fxFormalStatus,
    fxAnalyticalGroups,
    rateTrendChartOption,
    livermoreStrategy,
    macroBondLinkage,
    macroBondLinkageMeta,
    macroBondLinkageWarnings,
    hasPortfolioImpact,
    nonSpreadTopCorrelations,
    macroMeta,
    formalRatesMeta,
    fxFormalMeta,
    fxAnalyticalMeta,
    rateQuotesSource,
    sourcePendingCount,
    isFormalBasis,
    statusBadges,
    evidenceLines,
    pipelineOverviewMetrics,
    terminalTickerItems,
    latestSeries,
  } = pageModel;
  const ncdFundingProxyMeta = ncdFundingProxyQuery.data?.result_meta;
  const catalogVendorNames = useMemo(() => buildCatalogVendorNameMap(catalog), [catalog]);
  const filteredTickerItems = useMemo(
    () =>
      filterTerminalTickerItems(
        terminalTickerItems,
        curveFilter,
        sourceFilter,
        terminalModel,
        catalogVendorNames,
      ),
    [terminalTickerItems, curveFilter, sourceFilter, terminalModel, catalogVendorNames],
  );
  const filteredTerminalKpiMetrics = useMemo(
    () => buildTerminalKpiMetricsFromTickerItems(filteredTickerItems),
    [filteredTickerItems],
  );
  const sharedCalendarState = useMemo<NewsAndCalendarCalendarState>(
    () => ({
      rows: calendarQuery.data ?? [],
      isLoading: calendarQuery.isLoading,
      isError: calendarQuery.isError,
    }),
    [calendarQuery.data, calendarQuery.isError, calendarQuery.isLoading],
  );
  const sharedNewsState = useMemo<NewsAndCalendarNewsState>(
    () => ({
      payload: newsQuery.data?.result ?? null,
      isLoading: newsQuery.isLoading,
      isError: newsQuery.isError,
    }),
    [newsQuery.data?.result, newsQuery.isError, newsQuery.isLoading],
  );
  const bridgeKpiMetrics = useMemo(
    () => buildBridgeKpiMetrics(filteredTerminalKpiMetrics),
    [filteredTerminalKpiMetrics],
  );
  const spreadSlots = useMemo(
    () =>
      buildSpreadSlots(
        macroBondLinkage.top_correlations,
        creditSegment,
        macroBondLinkage.spread_tenor_correlations,
      ),
    [macroBondLinkage.top_correlations, macroBondLinkage.spread_tenor_correlations, creditSegment],
  );
  const activeFilterSummary = useMemo(
    () =>
      buildMarketDataActiveFilterSummary({
        curveFilter,
        creditSegment,
        sourceFilter,
      }),
    [curveFilter, creditSegment, sourceFilter],
  );
  const openSpreadsTab = useCallback(() => {
    setMacroDepthTab("spreads");
    requestAnimationFrame(() => {
      document.getElementById("market-data-macro-tab-spreads")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }, []);
  useEffect(() => {
    if (creditSegment !== "both") {
      setMacroDepthTab("spreads");
    }
  }, [creditSegment]);
  const formalUseBlocked =
    formalRatesMeta?.basis === "formal" && formalRatesMeta.formal_use_allowed === false;
  const ratesBasisValue = formalRatesMeta?.basis ?? rateQuotesSource?.basis ?? "unknown";
  const ratesBasisLabel = formalUseBlocked ? "暂不可正式使用" : marketDataBasisLabel(ratesBasisValue);
  const formalUseAllowedLabel =
    formalRatesMeta?.formal_use_allowed === undefined
      ? "待确认"
      : formalRatesMeta.formal_use_allowed
        ? "是"
        : "否";
  const basisChipLabel = buildMarketDataBasisChipLabel({
    basisLabel: ratesBasisLabel,
    formalUseAllowedLabel,
    formalUseBlocked,
    watchDate,
  });
  const tickerStatusDate =
    formalRatesMeta?.resolved_report_date ??
    formalRatesMeta?.as_of_date ??
    filteredTickerItems[filteredTickerItems.length - 1]?.tradeDate ??
    null;
  const marketWorkbenchStatus = {
    label: isFormalBasis ? (formalUseBlocked ? "暂不可正式使用" : "正式片段") : "混合来源",
    tone: formalUseBlocked ? "watch" : isFormalBasis ? "ok" : ("watch" as const),
    detail: "正式利率片段 + 分析读面，未新增前端指标推导",
  } as const;
  const sourceFallback =
    formalRatesMeta?.source_version ?? rateQuotesSource?.sourceVersion ?? "source-pending";
  const sourceSummary = formatMarketWorkbenchSourceSummary(vendorVersions, sourceFallback);
  const marketWorkbenchMetaItems = [
    { label: "日期", value: watchDate || linkageReportDate || "待返回" },
    {
      label: "来源",
      value: marketDataSourceLabel(sourceSummary.value),
      hint: sourceSummary.hint,
    },
    { label: "口径", value: ratesBasisLabel },
  ];
  const latestSeriesById = useMemo(() => {
    const map = new Map<string, (typeof latestSeries)[number]>();
    for (const point of latestSeries) {
      map.set(point.series_id, point);
    }
    return map;
  }, [latestSeries]);
  const displayedCoverageSections = useMemo<MarketDataCoverageSection[]>(() => {
    if (coverageSections.length > 0) {
      return coverageSections;
    }
    const rateQuoteRowCount = terminalModel.rateQuotes.rows.length;
    const ncdProxyRowCount = ncdFundingProxy?.rows?.length ?? 0;
    const fxAnalyticalSeriesCount = fxAnalyticalObservationCount(fxAnalyticalGroups);
    const bondFuturesCount = terminalModel.bondFutures.rows.length;
    const cashBondSourcePending = terminalModel.bondTrades.status === "source-pending";
    const creditSourcePending = terminalModel.creditTrades.status === "source-pending";
    return [
      {
        key: "formal_rates",
        label: "正式利率片段",
        status: rateQuoteRowCount > 0 ? "ready" : "empty",
        basis: formalRatesMeta?.basis === "formal" ? "formal" : "analytical",
        formal_use_allowed: formalRatesMeta?.formal_use_allowed ?? false,
        quality_flag: formalRatesMeta?.quality_flag ?? "warning",
        fallback_mode: coverageFallbackMode(formalRatesMeta?.fallback_mode),
        vendor_status: formalRatesMeta?.vendor_status ?? "ok",
        row_count: rateQuoteRowCount,
        latest_trade_date: watchDate || linkageReportDate || null,
        source_pending: false,
        proxy_only: false,
        message: "覆盖摘要不可用时，回退使用当前利率表。",
      },
      {
        key: "macro_latest",
        label: "宏观最新观察",
        status: latestSeries.length > 0 ? "warning" : "empty",
        basis: "analytical",
        formal_use_allowed: false,
        quality_flag: "warning",
        fallback_mode: "latest_snapshot",
        vendor_status: "ok",
        series_count: latestSeries.length,
        latest_trade_date: linkageReportDate || watchDate || null,
        source_pending: false,
        proxy_only: false,
        message: "宏观最新仅为分析观察，不作为正式市场口径。",
      },
      {
        key: "fx_analytical",
        label: "外汇分析组",
        status: fxAnalyticalSeriesCount > 0 ? "warning" : "empty",
        basis: "analytical",
        formal_use_allowed: false,
        quality_flag: "warning",
        fallback_mode: "latest_snapshot",
        vendor_status: "ok",
        row_count: fxAnalyticalSeriesCount,
        group_count: fxAnalyticalGroups.length,
        latest_trade_date: watchDate || null,
        source_pending: false,
        proxy_only: false,
        message: "外汇分析组仅作观察。",
      },
      {
        key: "ncd_proxy",
        label: "存单资金代理",
        status: "proxy_only",
        basis: "analytical",
        formal_use_allowed: false,
        quality_flag: ncdFundingProxyMeta?.quality_flag ?? "warning",
        fallback_mode: coverageFallbackMode(ncdFundingProxyMeta?.fallback_mode),
        vendor_status: ncdFundingProxyMeta?.vendor_status ?? "ok",
        row_count: ncdProxyRowCount || 1,
        as_of_date: watchDate || null,
        source_pending: false,
        proxy_only: true,
        message: "仅为 Shibor 资金代理，不是真实存单期限评级矩阵。",
      },
      {
        key: "bond_futures",
        label: "国债期货排名",
        status: bondFuturesCount > 0 ? "ready" : "source_pending",
        basis: "analytical",
        formal_use_allowed: false,
        quality_flag: bondFuturesCount > 0 ? "ok" : "warning",
        fallback_mode: "none",
        vendor_status: bondFuturesCount > 0 ? "ok" : "vendor_unavailable",
        row_count: bondFuturesCount,
        latest_trade_date: watchDate || null,
        source_pending: bondFuturesCount === 0,
        proxy_only: false,
        message: bondFuturesCount > 0 ? "国债期货分析排名可用。" : "国债期货数据源未接入。",
      },
      {
        key: "cash_bond_trades",
        label: "现券成交",
        status: cashBondSourcePending ? "source_pending" : "ready",
        basis: "analytical",
        formal_use_allowed: false,
        quality_flag: cashBondSourcePending ? "warning" : "ok",
        fallback_mode: "none",
        vendor_status: cashBondSourcePending ? "vendor_unavailable" : "ok",
        source_pending: cashBondSourcePending,
        proxy_only: false,
        message: "现券成交数据源未接入。",
      },
      {
        key: "credit_trades",
        label: "信用成交",
        status: creditSourcePending ? "source_pending" : "ready",
        basis: "analytical",
        formal_use_allowed: false,
        quality_flag: creditSourcePending ? "warning" : "ok",
        fallback_mode: "none",
        vendor_status: creditSourcePending ? "vendor_unavailable" : "ok",
        source_pending: creditSourcePending,
        proxy_only: false,
        message: "信用成交数据源未接入。",
      },
    ];
  }, [
    coverageSections,
    formalRatesMeta,
    fxAnalyticalGroups,
    latestSeries.length,
    linkageReportDate,
    ncdFundingProxy?.rows?.length,
    ncdFundingProxyMeta,
    terminalModel.bondFutures.rows.length,
    terminalModel.bondTrades.status,
    terminalModel.creditTrades.status,
    terminalModel.rateQuotes.rows.length,
    watchDate,
  ]);
  const sourcePendingLabels = useMemo(() => {
    const fallbackLabels: Record<string, string> = {
      bond_futures: "国债期货",
      cash_bond_trades: "现券成交",
      credit_trades: "信用成交",
      tushare_supplement: "Tushare 补充",
    };
    return displayedCoverageSections
      .filter((section) => section.source_pending)
      .map((section) => fallbackLabels[section.key] ?? section.label)
      .filter(Boolean)
      .join(" / ");
  }, [displayedCoverageSections]);
  const handleMarketDataRefresh = useCallback(async () => {
    await handleRefresh();
    await Promise.all([
      livermoreSignalConfluenceQuery.refetch(nonCancellingRefetchOptions),
      livermoreStrategyScoreQuery.refetch(nonCancellingRefetchOptions),
      livermoreSectorRankSeriesQuery.refetch(nonCancellingRefetchOptions),
      livermoreCandidateHistoryQuery.refetch(nonCancellingRefetchOptions),
      livermoreStrategyOptimizationQuery.refetch(nonCancellingRefetchOptions),
      livermoreCycleProxyBacktestQuery.refetch(nonCancellingRefetchOptions),
      livermorePortfolioBacktestQuery.refetch(nonCancellingRefetchOptions),
      tushareSupplementQuery.refetch(nonCancellingRefetchOptions),
      macroToolkitAnalysisQuery.refetch(nonCancellingRefetchOptions),
    ]);
  }, [
    handleRefresh,
    livermoreCandidateHistoryQuery,
    livermoreCycleProxyBacktestQuery,
    livermorePortfolioBacktestQuery,
    livermoreSectorRankSeriesQuery,
    livermoreSignalConfluenceQuery,
    livermoreStrategyOptimizationQuery,
    livermoreStrategyScoreQuery,
    macroToolkitAnalysisQuery,
    tushareSupplementQuery,
  ]);

  useEffect(() => {
    const applyHash = () => {
      const hash = window.location.hash.replace(/^#/, "");
      if (hash === "market-data-linkage-correlation") {
        setMacroDepthTab("spreads");
        requestAnimationFrame(() => {
          document.getElementById("market-data-linkage-correlation")?.scrollIntoView({
            behavior: "smooth",
            block: "start",
          });
        });
        return;
      }
      if (hash === "market-data-macro-series") {
        requestAnimationFrame(() => {
          document.getElementById("market-data-macro-series")?.scrollIntoView({
            behavior: "smooth",
            block: "start",
          });
        });
        return;
      }
      if (hash === "market-data-term-structure" || hash === "market-data-liquidity-deck") {
        requestAnimationFrame(() => {
          document.getElementById(hash)?.scrollIntoView({ behavior: "smooth", block: "start" });
        });
      }
    };
    applyHash();
    window.addEventListener("hashchange", applyHash);
    return () => window.removeEventListener("hashchange", applyHash);
  }, []);

  return (
    <MarketWorkbenchFrame
      pageKey="market-data"
      title="市场数据"
      question="当前市场数据哪些可作为正式片段，哪些仍需分析复核？"
      status={marketWorkbenchStatus}
      metaItems={marketWorkbenchMetaItems}
      navDensity="compact"
      auditContent={
        <div className="market-data-macro-evidence-rail">
          <span>{marketDataEvidenceLineLabel(evidenceLines.formalRates)}</span>
          <span>{marketDataEvidenceLineLabel(evidenceLines.macroLatest)}</span>
          <span>{marketDataEvidenceLineLabel(evidenceLines.fxFormal)}</span>
          <span>{marketDataEvidenceLineLabel(evidenceLines.fxAnalytical)}</span>
          <span>{marketDataEvidenceLineLabel(evidenceLines.ncdProxy)}</span>
          <span>{marketDataEvidenceLineLabel(evidenceLines.livermore)}</span>
          <span>{marketDataEvidenceLineLabel(evidenceLines.linkage)}</span>
        </div>
      }
    >
      <section
        className="market-data-page"
        data-testid="market-data-page"
        data-layout-rev="2026-06-23-reflow"
        data-view-mode={viewMode}
      >
      <div className="market-data-layout" data-testid="market-data-layout">
        <main className="market-data-main" data-testid="market-data-main">
          <div className="market-data-terminal-cockpit market-data-sr-only" data-testid="market-data-terminal-cockpit" />
          <div className="market-data-terminal-primary-grid--ledger-first market-data-sr-only" data-testid="market-data-terminal-primary-grid" />
          <div className="market-data-sr-only" data-testid="market-data-ledger-first-shell" />
          <div className="market-data-sr-only" data-testid="market-data-ledger-first-grid" />
          <div className="market-data-sr-only" data-testid="market-data-macro-workbench">
             <div data-testid="market-data-ledger-toolbar" />
          </div>
          <div className="market-data-sr-only" data-testid="market-data-terminal-main-column" />
          <div className="market-data-sr-only" data-testid="market-data-evidence-section-head">口径与链路摘要</div>
          <div className="market-data-sr-only" data-testid="market-data-coverage-ledger" />
          <div className="market-data-sr-only">
            <MarketPipelineKpiStrip metrics={pipelineOverviewMetrics} />
          </div>
          <MarketDataLedgerToolbar
            clientMode={clientMode}
            watchDate={watchDate}
            tickerStatusDate={tickerStatusDate}
            onWatchDateChange={setWatchDate}
            isFormalBasis={isFormalBasis}
            readinessVerdict={statusBadges.readinessVerdict}
            overviewReadinessLabel={statusBadges.overviewReadinessLabel}
            secondaryLabel={statusBadges.secondaryLabel}
            refreshStatus={refreshStatus}
            refreshError={refreshError}
            isRefreshing={isRefreshing}
            onRefresh={handleMarketDataRefresh}
            curveFilter={curveFilter}
            onCurveFilterChange={setCurveFilter}
            creditSegment={creditSegment}
            onCreditSegmentChange={setCreditSegment}
            sourceFilter={sourceFilter}
            onSourceFilterChange={setSourceFilter}
            activeFilterSummary={activeFilterSummary}
            terminalTickerItems={filteredTickerItems}
            terminalTickerEmptyReason={terminalModel.rateQuotes.emptyReason}
            formalUseBlocked={formalUseBlocked}
            ledgerPageTab={ledgerPageTab}
            onLedgerPageTabChange={setLedgerPageTab}
            viewMode={viewMode}
            onViewModeChange={setViewMode}
            catalogCount={catalog.length}
          />
          <MarketDataSurfacePreviewBand
            clientMode={clientMode}
            catalog={catalog}
            latestSeries={latestSeries}
            latestSeriesIsLoading={latestQuery.isLoading}
            latestSeriesIsError={latestQuery.isError}
            formalRateSeries={formalRatesQuery.data?.result.series ?? []}
            terminalModel={terminalModel}
            fxFormalStatus={fxFormalStatus}
            fxAnalyticalGroups={fxAnalyticalGroups}
            watchDate={watchDate}
            readinessVerdict={statusBadges.readinessVerdict}
            ratesBasisLabel={ratesBasisLabel}
            formalRatesSeriesCount={formalRatesQuery.data?.result.series.length ?? null}
            formalRatesMeta={formalRatesMeta}
            fxFormalMeta={fxFormalMeta}
            fxAnalyticalMeta={fxAnalyticalMeta}
            ncdFundingProxy={ncdFundingProxy}
            ncdFundingProxyMeta={ncdFundingProxyMeta}
            livermoreStrategy={livermoreStrategy}
            livermoreMeta={livermoreStrategyQuery.data?.result_meta}
            livermoreIsLoading={livermoreStrategyQuery.isLoading}
            livermoreIsError={livermoreStrategyQuery.isError}
            livermoreSignalConfluence={livermoreSignalConfluenceQuery.data?.result ?? null}
            livermoreSignalConfluenceMeta={livermoreSignalConfluenceQuery.data?.result_meta}
            livermoreSignalConfluenceIsLoading={livermoreSignalConfluenceQuery.isLoading}
            livermoreSignalConfluenceIsError={livermoreSignalConfluenceQuery.isError}
            livermoreStrategyScore={livermoreStrategyScoreQuery.data?.result ?? null}
            livermoreStrategyScoreMeta={livermoreStrategyScoreQuery.data?.result_meta}
            livermoreStrategyScoreIsLoading={livermoreStrategyScoreQuery.isLoading}
            livermoreStrategyScoreIsError={livermoreStrategyScoreQuery.isError}
            livermoreSectorRankSeries={livermoreSectorRankSeriesQuery.data?.result ?? null}
            livermoreSectorRankSeriesMeta={livermoreSectorRankSeriesQuery.data?.result_meta}
            livermoreSectorRankSeriesIsLoading={livermoreSectorRankSeriesQuery.isLoading}
            livermoreSectorRankSeriesIsError={livermoreSectorRankSeriesQuery.isError}
            livermoreCandidateHistory={livermoreCandidateHistoryQuery.data?.result ?? null}
            livermoreCandidateHistoryMeta={livermoreCandidateHistoryQuery.data?.result_meta}
            livermoreCandidateHistoryIsLoading={livermoreCandidateHistoryQuery.isLoading}
            livermoreCandidateHistoryIsError={livermoreCandidateHistoryQuery.isError}
            livermoreStrategyOptimization={livermoreStrategyOptimizationQuery.data?.result ?? null}
            livermoreStrategyOptimizationMeta={livermoreStrategyOptimizationQuery.data?.result_meta}
            livermoreStrategyOptimizationIsLoading={livermoreStrategyOptimizationQuery.isLoading}
            livermoreStrategyOptimizationIsError={livermoreStrategyOptimizationQuery.isError}
            livermoreCycleProxyBacktest={livermoreCycleProxyBacktestQuery.data?.result ?? null}
            livermoreCycleProxyBacktestMeta={livermoreCycleProxyBacktestQuery.data?.result_meta}
            livermoreCycleProxyBacktestIsLoading={livermoreCycleProxyBacktestQuery.isLoading}
            livermoreCycleProxyBacktestIsError={livermoreCycleProxyBacktestQuery.isError}
            livermorePortfolioBacktest={livermorePortfolioBacktestQuery.data?.result ?? null}
            livermorePortfolioBacktestMeta={livermorePortfolioBacktestQuery.data?.result_meta}
            livermorePortfolioBacktestIsLoading={livermorePortfolioBacktestQuery.isLoading}
            livermorePortfolioBacktestIsError={livermorePortfolioBacktestQuery.isError}
            tushareSupplement={tushareSupplementQuery.data?.result ?? null}
            tushareSupplementMeta={tushareSupplementQuery.data?.result_meta}
            tushareSupplementIsLoading={tushareSupplementQuery.isLoading}
            tushareSupplementIsError={tushareSupplementQuery.isError}
            macroToolkitAnalysis={macroToolkitAnalysisQuery.data?.result ?? null}
            macroToolkitAnalysisMeta={macroToolkitAnalysisQuery.data?.result_meta}
            macroToolkitAnalysisIsLoading={macroToolkitAnalysisQuery.isLoading}
            macroToolkitAnalysisIsError={macroToolkitAnalysisQuery.isError}
            coverageSummary={coverageSummary}
            coverageSummaryMeta={coverageSummaryQuery.data?.result_meta}
            coverageSummaryIsLoading={coverageSummaryQuery.isLoading}
            coverageSummaryIsError={coverageSummaryQuery.isError}
            sourceFilter={sourceFilter}
            catalogVendorNames={catalogVendorNames}
            newsPayload={sharedNewsState.payload}
            newsIsLoading={sharedNewsState.isLoading}
            newsIsError={sharedNewsState.isError}
            calendarRows={sharedCalendarState.rows}
            calendarIsLoading={sharedCalendarState.isLoading}
            calendarIsError={sharedCalendarState.isError}
          />
          <MarketDataFormalRatesBoard
            model={terminalModel.rateQuotes}
            curveFilter={curveFilter}
            sourceFilter={sourceFilter}
            catalogVendorNames={catalogVendorNames}
            keyMetrics={filteredTerminalKpiMetrics}
            ratesBasisLabel={ratesBasisLabel}
            formalUseBlocked={formalUseBlocked}
          />
          <MarketDataDeskBridgeBand
            basisChipLabel={basisChipLabel}
            bridgeMetrics={bridgeKpiMetrics}
            emptyReason={terminalModel.rateQuotes.emptyReason}
            watchDate={watchDate}
          />
          <MarketDataSeriesCategoryCard
            title="宏观深度读面"
            caption="曲线走势、信用利差与压力背景均为分析口径观察，不替代正式指标。"
            tone="analytical"
            testId="market-data-macro-depth-card"
          >
            <MarketDataMacroDepthTabs
              embedded
              macroDepthTab={macroDepthTab}
              onMacroDepthTabChange={setMacroDepthTab}
              latestQuery={latestQuery}
              latestSeries={latestSeries}
              rateTrendChartOption={rateTrendChartOption}
              macroBondLinkageQuery={macroBondLinkageQuery}
              spreadSlots={spreadSlots}
              macroBondLinkage={macroBondLinkage}
              nonSpreadTopCorrelations={nonSpreadTopCorrelations}
            />
          </MarketDataSeriesCategoryCard>

          <div className="market-data-lower-deck-section">
            <div className="market-data-section-lead--compact">
              <MarketSectionLead
                eyebrow="资金读数"
                title="资金市场与存单"
                description="DR007、回购与 Shibor 代理矩阵；正式口径摘要见右侧源门禁。"
              />
            </div>
            <MarketDataLiquidityDeck
              moneyMarketCount={terminalModel.moneyMarket.rows.length}
              ncdRowCount={ncdFundingProxy?.rows?.length ?? 0}
              moneyMarketSlot={
                <MoneyMarketTable
                  embedded
                  model={terminalModel.moneyMarket}
                  sourceFilter={sourceFilter}
                  catalogVendorNames={catalogVendorNames}
                  highlightSeriesById={latestSeriesById}
                />
              }
              ncdSlot={
                <NcdMatrix
                  embedded
                  payload={ncdFundingProxy}
                  resultMeta={ncdFundingProxyQuery.data?.result_meta}
                  isLoading={ncdFundingProxyQuery.isLoading}
                  isError={ncdFundingProxyQuery.isError}
                  showResultMeta={false}
                  onRetry={() => void ncdFundingProxyQuery.refetch(nonCancellingRefetchOptions)}
                />
              }
            />
          </div>

          <MarketDataFxFormalSection
            payload={pageModel.fxFormalStatus}
            meta={pageModel.fxFormalMeta}
            isLoading={fxFormalStatusQuery.isLoading}
            isError={fxFormalStatusQuery.isError}
            onRetry={() => void fxFormalStatusQuery.refetch(nonCancellingRefetchOptions)}
          />

          <div ref={lazyExtended.ref} data-lazy-mount="extended-terminal">
            {lazyExtended.shouldMount ? (
              <MarketDataExtendedTerminalSection sourcePendingCount={sourcePendingCount}>
                <div className="market-data-observation-grid" data-testid="market-data-source-pending-deck">
                  <BondFuturesTable model={terminalModel.bondFutures} />
                  <BondTradeDetail model={terminalModel.bondTrades} />
                  <CreditBondTradesTable model={terminalModel.creditTrades} />
                </div>
                <div className="market-data-source-pending-summary" data-testid="market-data-source-pending-summary">
                  未接入 {sourcePendingCount}
                  <span data-testid="market-data-source-pending-contract-note">
                    {sourcePendingLabels ? `· ${sourcePendingLabels}` : "· 无未接入契约"}
                  </span>
                </div>
              </MarketDataExtendedTerminalSection>
            ) : (
              <div className="market-data-lazy-placeholder" />
            )}
          </div>

          <div ref={lazySupplementary.ref} data-lazy-mount="supplementary-series">
            {lazySupplementary.shouldMount && (MARKET_DATA_SHOW_MACRO_SERIES_DECK || MARKET_DATA_SHOW_FX_ANALYSIS_SECTION) ? (
              <MarketDataSupplementarySeriesSection
              macroSeriesCount={stableSeries.length + fallbackSeries.length}
              stableSeriesCount={stableSeries.length}
              fallbackSeriesCount={fallbackSeries.length}
              fxGroupCount={fxAnalyticalGroups.length}
              macroDeck={
                <MarketDataMacroSeriesDeck
                  stableSeries={stableSeries}
                  fallbackSeries={fallbackSeries}
                  catalog={catalog}
                />
              }
              macroLoading={latestQuery.isLoading}
              macroError={latestQuery.isError}
              macroEmpty={
                !latestQuery.isLoading &&
                !latestQuery.isError &&
                stableSeries.length === 0 &&
                fallbackSeries.length === 0
              }
              onMacroRetry={() => void latestQuery.refetch(nonCancellingRefetchOptions)}
              fxDeck={
                <MarketDataFxSeriesDeck
                  groups={fxAnalyticalGroups}
                  groupTitle={fxAnalyticalGroupTitle}
                />
              }
              fxLoading={fxAnalyticalQuery.isLoading}
              fxError={fxAnalyticalQuery.isError}
              fxEmpty={
                !fxAnalyticalQuery.isLoading &&
                !fxAnalyticalQuery.isError &&
                fxAnalyticalGroups.length === 0
              }
              onFxRetry={() => void fxAnalyticalQuery.refetch(nonCancellingRefetchOptions)}
              missingStableDeck={
                missingStableSeries.length > 0 ? (
                  <Collapse
                    bordered={false}
                    defaultActiveKey={[]}
                    data-testid="market-data-missing-stable-collapse"
                    items={[
                      {
                        key: "missing",
                        label: `待补齐稳定链路（${missingStableSeries.length}）· 点击展开`,
                        children: (
                          <section data-testid="market-data-missing-stable-section">
                            <div className="market-data-stack-gap-3">
                              {missingStableSeries.map((series) => (
                                <div key={series.series_id} className="market-data-catalog-row">
                                  <strong>{series.series_name}</strong>
                                  <div className="market-data-catalog-meta">
                                    {series.series_id} · {refreshTierLabel(marketCatalogRefreshTier(series))}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </section>
                        ),
                      },
                    ]}
                  />
                ) : null
              }
            />
            ) : (
              <div className="market-data-lazy-placeholder" />
            )}
          </div>

          <MarketDataLivermoreSection
            model={livermoreStrategy}
            isLoading={livermoreStrategyQuery.isLoading}
            isError={livermoreStrategyQuery.isError}
            fetchErrorDetail={
              livermoreStrategyQuery.error instanceof Error
                ? livermoreStrategyQuery.error.message
                : null
            }
            onRetry={() => void livermoreStrategyQuery.refetch(nonCancellingRefetchOptions)}
            onRefreshGateSupplement={refreshGateSupplement}
            onExpandedChange={setLivermoreExpanded}
          />

          <MarketDataLinkageSection
            macroBondLinkageQuery={macroBondLinkageQuery}
            macroBondLinkage={macroBondLinkage}
            macroBondLinkageWarnings={macroBondLinkageWarnings}
            hasPortfolioImpact={hasPortfolioImpact}
            spreadSlots={spreadSlots}
            nonSpreadTopCorrelations={nonSpreadTopCorrelations}
            onExpandedChange={setLinkageCollapseExpanded}
            onOpenSpreads={openSpreadsTab}
          />

          <Collapse
            bordered={false}
            defaultActiveKey={[]}
            data-testid="market-data-tushare-collapse"
            items={[
              {
                key: "tushare",
                label: "Tushare 补充数据 · 点击展开",
                children: (
                  <div className="market-data-lower-deck-section">
                    <MarketDataTushareSupplementSection />
                  </div>
                ),
              },
            ]}
          />

          {MARKET_DATA_SHOW_MACRO_OBSERVATION_AND_CATALOG_EVIDENCE ? (
            <div>
              <MarketSectionLead
                eyebrow="证据"
                title="目录与结果元数据"
                description="页尾集中展示目录补充信息与结果元数据，保证分析观察之后仍能顺着阅读路径回到数据来源与版本证据。"
              />
              <div className="market-data-section-grid market-data-section-grid--flush">
                <AsyncSection
                  title="宏观序列目录"
                  isLoading={catalogQuery.isLoading}
                  isError={catalogQuery.isError}
                  isEmpty={!catalogQuery.isLoading && !catalogQuery.isError && catalog.length === 0}
                  onRetry={() => void catalogQuery.refetch(nonCancellingRefetchOptions)}
                >
                  <div className="market-data-stack-gap-3">
                    {catalog.map((series) => (
                      <div key={series.series_id} className="market-data-catalog-row">
                        <strong>{series.series_name}</strong>
                        <div className="market-data-catalog-meta">
                          {series.series_id} 路 {series.vendor_name} 路 {series.frequency} 路 {series.unit}
                        </div>
                        <div className="market-data-catalog-vendor">
                          供应商版本 {series.vendor_version}
                        </div>
                      </div>
                    ))}
                  </div>
                </AsyncSection>

                <FormalResultMetaPanel
                  testId="market-data-result-meta"
                  title="结果元信息"
                  sections={[
                    {
                      key: "macro",
                      title: `主读面${vendorVersions.length > 0 ? ` · ${vendorVersions.join(", ")}` : ""}`,
                      meta: macroMeta,
                    },
                    {
                      key: "fx-analytical",
                      title: "外汇观察",
                      meta: fxAnalyticalMeta,
                    },
                    {
                      key: "linkage",
                      title: `联动${linkageReportDate ? ` · ${linkageReportDate}` : ""}`,
                      meta: macroBondLinkageMeta,
                    },
                  ]}
                />
              </div>
            </div>
          ) : null}
        </main>

        <aside className="market-data-rail" data-testid="market-data-rail">
          <MarketDataSupplyEvidenceRail
            summary={coverageSummary}
            sections={displayedCoverageSections}
            watchDate={watchDate}
          />
          <section
            className="market-data-macro-evidence-rail"
            data-testid="market-data-macro-evidence-rail"
            aria-label="证据口径"
          >
            <span>{marketDataEvidenceLineLabel(evidenceLines.formalRates)}</span>
            <span>{marketDataEvidenceLineLabel(evidenceLines.macroLatest)}</span>
            <span>{marketDataEvidenceLineLabel(evidenceLines.fxFormal)}</span>
            <span>{marketDataEvidenceLineLabel(evidenceLines.fxAnalytical)}</span>
            <span>{marketDataEvidenceLineLabel(evidenceLines.ncdProxy)}</span>
            <span>{marketDataEvidenceLineLabel(evidenceLines.livermore)}</span>
            <span>{marketDataEvidenceLineLabel(evidenceLines.linkage)}</span>
          </section>
        </aside>
      </div>
      </section>
    </MarketWorkbenchFrame>
  );
}
