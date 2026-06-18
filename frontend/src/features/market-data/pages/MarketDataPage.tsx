import { useCallback, useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Collapse, Select, Spin } from "antd";
import { useApiClient } from "../../../api/client";
import { externalDataQueryOptions } from "../../../app/externalDataRefreshPolicy";
import type { ResearchCalendarEvent } from "../../../api/contracts";
import { nonCancellingRefetchOptions } from "../../../app/externalDataRefreshPolicy";
import { PageSectionLead, type PageSectionLeadProps } from "../../../components/page/PagePrimitives";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import type {
  ChoiceMacroLatestPoint,
  ChoiceMacroRecentPoint,
  FxAnalyticalPayload,
  FxFormalStatusPayload,
  MarketDataCoverageSection,
  MarketDataCoverageSummaryPayload,
  ResultMeta,
} from "../../../api/contracts";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { BondFuturesTable } from "../components/BondFuturesTable";
import { BondTradeDetail } from "../components/BondTradeDetail";
import { CreditBondTradesTable } from "../components/CreditBondTradesTable";
import { LiveResultMetaStrip } from "../components/LiveResultMetaStrip";
import { MarketDataDeskBridgeBand } from "../components/MarketDataDeskBridgeBand";
import { MarketDataEvidenceRailSection } from "../components/MarketDataEvidenceRailSection";
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
import { NewsAndCalendar, type NewsAndCalendarCalendarState } from "../components/NewsAndCalendar";
import { MarketDataSeriesCategoryCard } from "../components/MarketDataSeriesCategoryCard";
import { MarketDataTushareSupplementSection } from "../components/MarketDataTushareSupplementSection";
import { RateQuoteTable } from "../components/RateQuoteTable";
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
import {
  MarketDataHeroSection,
  MarketPipelineKpiStrip,
  type MarketOverviewMetric,
} from "./MarketDataHeroSection";
import { MarketDataMacroDepthTabs } from "./MarketDataMacroDepthTabs";
import { MarketDataTermStructureChart } from "../components/MarketDataTermStructureChart";
import { buildSpreadSlots, buildBridgeKpiMetrics, buildMarketDataBasisChipLabel, buildTerminalKpiMetricsFromTickerItems, formatMarketWorkbenchSourceSummary, pickRailHighlightMetric } from "./marketDataPageModel";
import { MarketWorkbenchFrame } from "../../workbench/market-shell";
import { InstitutionalKpiTile } from "../../workbench/shared/InstitutionalKpiTile";
import "./MarketDataPage.css";

/** 首屏不展示宏观读面蓝条（与 Bridge / Rail 去重）。 */
const MARKET_DATA_SHOW_OVERVIEW_META_STRIP = false;

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

function MarketSectionBlock({ children }: { children: ReactNode }) {
  return <div className="market-data-section-block">{children}</div>;
}

function _MarketSectionInnerBlock({ children }: { children: ReactNode }) {
  return <div className="market-data-section-inner-block">{children}</div>;
}

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
    stable: "稳定",
    fallback: "降级",
    isolated: "隔离",
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
  if (value === "ok") return "正常";
  if (value === "warning") return "预警";
  if (value === "error") return "错误";
  if (value === "stale") return "陈旧";
  return value ?? "待定";
}

function coverageStatusLabel(status: MarketDataCoverageSection["status"]): string {
  const labels: Record<MarketDataCoverageSection["status"], string> = {
    ready: "就绪",
    empty: "无数据",
    warning: "预警",
    stale: "陈旧",
    error: "错误",
    source_pending: "待接入",
    proxy_only: "代理口径",
    deferred: "暂缓",
  };
  return labels[status];
}

function coverageSectionCount(section: MarketDataCoverageSection): string {
  const count = section.series_count ?? section.row_count ?? section.group_count;
  return typeof count === "number" ? String(count) : "无";
}

function coverageSectionCountNumber(section: MarketDataCoverageSection): number {
  const count = section.series_count ?? section.row_count ?? section.group_count;
  return typeof count === "number" ? count : 1;
}

function coverageLatestDate(section: MarketDataCoverageSection | null | undefined): string {
  return section?.latest_trade_date ?? section?.as_of_date ?? "--";
}

function marketDataBasisLabel(value: string | null | undefined): string {
  const normalized = value ?? "";
  if (normalized.includes("formal")) return normalized.includes("blocked") ? "正式禁用" : "正式";
  if (normalized.includes("analytical")) return "分析";
  if (normalized.includes("mock")) return "回放";
  if (normalized.includes("source-pending")) return "待接入";
  if (normalized === "unknown" || normalized === "pending") return "待确认";
  return normalized || "--";
}

function marketDataStatusLabel(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    ready: "就绪",
    empty: "无数据",
    warning: "预警",
    stale: "陈旧",
    error: "错误",
    source_pending: "待接入",
    "source-pending": "待接入",
    proxy_only: "代理口径",
    "proxy-only": "代理口径",
    deferred: "暂缓",
    pending: "待接入",
    formal: "正式",
    analytical: "分析",
    ok: "正常",
    unknown: "待确认",
    vendor_unavailable: "供应商未接入",
  };
  return labels[value ?? ""] ?? value ?? "--";
}

function marketDataBooleanLabel(value: boolean): string {
  return value ? "是" : "否";
}

function marketDataFallbackLabel(value: string | null | undefined): string {
  if (value === "unknown") return "待确认";
  if (!value || value === "none") return "无";
  if (value === "latest_snapshot") return "最新快照";
  return value;
}

function marketDataSourceLabel(value: string | null | undefined): string {
  if (!value || value === "unknown") return "待确认";
  if (value === "source-pending" || value === "source_pending") return "待接入";
  return value;
}

function marketDataSectionLabel(section: MarketDataCoverageSection): string {
  const labels: Record<string, string> = {
    formal_rates: "正式利率",
    macro_catalog: "宏观目录",
    macro_latest: "宏观最新",
    fx_formal: "外汇正式",
    fx_analytical: "外汇分析",
    ncd_proxy: "存单代理",
    bond_futures: "国债期货",
    cash_bond_trades: "现券成交",
    credit_trades: "信用成交",
    macro_linkage: "宏观联动",
    livermore: "利弗莫尔信号",
  };
  return labels[section.key] ?? section.label;
}

function marketDataSeriesNameLabel(name: string): string {
  const labels: Record<string, string> = {
    "China 10Y government bond yield": "中国10年期国债收益率",
    "China 1Y government bond yield": "中国1年期国债收益率",
    "China 10Y policy bank yield": "中国10年期国开债收益率",
  };
  return labels[name] ?? name;
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
    .replaceAll("fallback=", "降级=")
    .replaceAll("vendor_status=", "供应商=")
    .replaceAll("source=", "来源=")
    .replace(/=formal\b/g, "=正式")
    .replace(/=analytical\b/g, "=分析")
    .replace(/=pending\b/g, "=待接入")
    .replace(/=false\b/g, "=否")
    .replace(/=true\b/g, "=是")
    .replace(/=ok\b/g, "=正常")
    .replace(/=warning\b/g, "=预警")
    .replace(/=stale\b/g, "=陈旧")
    .replace(/=error\b/g, "=错误")
    .replace(/=none\b/g, "=无")
    .replace(/=latest_snapshot\b/g, "=最新快照");
}

function coverageQualityLabel(section: MarketDataCoverageSection): string {
  if (section.status === "source_pending") return "待接入";
  if (section.status === "proxy_only") return "代理口径";
  if (section.status === "deferred") return "暂缓";
  return resultMetaQualityLabel(section.quality_flag);
}

function coverageActionLabel(section: MarketDataCoverageSection): string {
  if (section.source_pending) return "接入数据源";
  if (section.proxy_only) return "确认正式口径";
  if (section.status === "deferred") return "按需展开";
  if (section.fallback_mode !== "none") return "查看降级";
  return "查看详情";
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

function calendarKindLabel(kind: ResearchCalendarEvent["kind"]) {
  if (kind === "supply") return "供给";
  if (kind === "auction") return "招标";
  if (kind === "macro") return "宏观";
  return "内部";
}

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

function MarketDataLedgerEventsCard({
  calendarState,
}: {
  calendarState: NewsAndCalendarCalendarState;
}) {
  const calendarRows = useMemo(() => {
    const rows = calendarState.rows;
    return [...rows]
      .sort((a, b) => a.date.localeCompare(b.date) || a.title.localeCompare(b.title))
      .slice(0, 5);
  }, [calendarState.rows]);

  return (
    <article className="market-data-support-card market-data-support-card--wide" data-testid="market-data-ledger-events-card">
      <header>
        <strong>最新重要事件</strong>
        <a href="#market-data-news-calendar">查看经济日历</a>
      </header>
      {calendarState.isLoading ? (
        <div className="market-data-ledger-events-loading">
          <Spin size="small" />
        </div>
      ) : calendarState.isError ? (
        <p className="market-data-ledger-events-empty">供给与招标日历加载失败。</p>
      ) : calendarRows.length === 0 ? (
        <p className="market-data-ledger-events-empty">当前日历区间无供给/招标事件。</p>
      ) : (
        <ul data-testid="market-data-ledger-events-list" className="market-data-ledger-events-list">
          {calendarRows.map((event) => (
            <li key={event.id}>
              <span>{event.date}</span>
              <strong>{event.title}</strong>
              <em>{calendarKindLabel(event.kind)}</em>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function summarizeCoverageCount(
  sections: MarketDataCoverageSection[],
  predicate: (section: MarketDataCoverageSection) => boolean,
): number {
  return sections.filter(predicate).reduce((total, section) => total + coverageSectionCountNumber(section), 0);
}

function MarketDataCoverageCommand({
  summary,
  sections,
}: {
  summary: MarketDataCoverageSummaryPayload | null;
  sections: MarketDataCoverageSection[];
}) {
  const formalReadyCount = summarizeCoverageCount(
    sections,
    (section) => section.basis === "formal" && section.formal_use_allowed && section.status !== "source_pending",
  );
  const analyticalUsableCount = summarizeCoverageCount(
    sections,
    (section) =>
      section.basis === "analytical" &&
      !section.proxy_only &&
      !section.source_pending &&
      section.status !== "deferred",
  );
  const proxyOnlyCount =
    summary?.headline.proxy_only_count ??
    sections.filter((section) => section.proxy_only || section.status === "proxy_only").length;
  const sourcePendingCount =
    summary?.headline.source_pending_count ??
    sections.filter((section) => section.source_pending || section.status === "source_pending").length;
  const generatedLabel = summary?.as_of_date ?? summary?.generated_at ?? "summary unavailable";

  return (
    <section className="market-data-coverage-command" data-testid="market-data-coverage-command">
      <div className="market-data-coverage-command__headline">
        <span>覆盖指令</span>
        <strong>正式利率可用；宏观/外汇为分析读面；存单为代理口径；成交仍待接入</strong>
        <em>{generatedLabel}</em>
      </div>
      <div className="market-data-coverage-buckets" aria-label="市场数据供给覆盖桶">
        <article
          className="market-data-coverage-bucket market-data-coverage-bucket--formal"
          data-testid="market-data-coverage-bucket-formal-ready"
        >
          <span>正式口径</span>
          <strong>{formalReadyCount || (summary?.headline.formal_fragment_ready ? 1 : 0)}</strong>
          <small>正式口径片段</small>
        </article>
        <article
          className="market-data-coverage-bucket market-data-coverage-bucket--analytical"
          data-testid="market-data-coverage-bucket-analytical-usable"
        >
          <span>分析口径</span>
          <strong>{analyticalUsableCount}</strong>
          <small>分析读面可用</small>
        </article>
        <article
          className="market-data-coverage-bucket market-data-coverage-bucket--proxy"
          data-testid="market-data-coverage-bucket-proxy-only"
        >
          <span>代理口径</span>
          <strong>{proxyOnlyCount}</strong>
          <small>存单不作正式矩阵</small>
        </article>
        <article
          className="market-data-coverage-bucket market-data-coverage-bucket--pending"
          data-testid="market-data-coverage-bucket-source-pending"
        >
          <span>待接入</span>
          <strong>{sourcePendingCount}</strong>
          <small>成交/契约待接入</small>
        </article>
      </div>
    </section>
  );
}

function MarketDataCoverageLedger({
  sections,
}: {
  sections: MarketDataCoverageSection[];
}) {
  return (
    <section className="market-data-coverage-ledger" data-testid="market-data-coverage-ledger">
      <header className="market-data-panel-head">
        <span>数据供给组盘总览</span>
        <strong>覆盖台账</strong>
      </header>
      <div className="market-data-ledger-scroll">
        <table>
          <thead>
            <tr>
              <th>数据区块</th>
              <th>口径</th>
              <th>允许正式使用</th>
              <th>质量</th>
              <th>降级</th>
              <th>最新日期</th>
              <th>建议动作</th>
            </tr>
          </thead>
          <tbody>
            {sections.map((section) => (
              <tr key={section.key}>
                <td>
                  <span className="market-data-ledger-dot" data-coverage-status={section.status} />
                  {marketDataSectionLabel(section)}
                </td>
                <td>{marketDataBasisLabel(section.basis)}</td>
                <td>{marketDataBooleanLabel(section.formal_use_allowed)}</td>
                <td>{coverageQualityLabel(section)}</td>
                <td>{marketDataFallbackLabel(section.fallback_mode)}</td>
                <td>{coverageLatestDate(section)}</td>
                <td>{coverageActionLabel(section)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <footer className="market-data-ledger-legend" aria-label="coverage status legend">
          <span>
            <i className="market-data-ledger-dot" data-coverage-status="ready" /> 就绪
          </span>
          <span>
            <i className="market-data-ledger-dot" data-coverage-status="warning" /> 预警
          </span>
          <span>
            <i className="market-data-ledger-dot" data-coverage-status="proxy_only" /> 代理
          </span>
          <span>
            <i className="market-data-ledger-dot" data-coverage-status="source_pending" /> 待接入
          </span>
        </footer>
      </div>
    </section>
  );
}

function MarketDataSourceGatePanel({
  sourceGateFields,
  sections,
  highlightMetric,
}: {
  sourceGateFields: { label: string; value: string }[];
  sections: MarketDataCoverageSection[];
  highlightMetric: MarketOverviewMetric | null;
}) {
  const conciseSections = sections.filter((section) =>
    ["formal_rates", "macro_latest", "fx_formal", "fx_analytical", "ncd_proxy", "bond_futures", "cash_bond_trades", "credit_trades"].includes(
      section.key,
    ),
  );
  return (
    <section className="market-data-source-gate-panel" data-testid="market-data-source-gate-table">
      <header className="market-data-panel-head">
        <span>源门禁</span>
        <strong>数据源门禁</strong>
      </header>
      <div className="market-data-source-gate-summary">
        {sourceGateFields.slice(0, 4).map((field) => (
          <div key={field.label}>
            <span>{field.label}</span>
            <strong title={field.value}>{field.value}</strong>
          </div>
        ))}
      </div>
      <div className="market-data-source-gate-table-scroll">
        <table>
          <thead>
            <tr>
              <th>数据域</th>
              <th>状态</th>
              <th>最新可用</th>
              <th>备注</th>
            </tr>
          </thead>
          <tbody>
            {conciseSections.map((section) => (
              <tr key={section.key}>
                <td>{marketDataSectionLabel(section)}</td>
                <td>
                  <span className="market-data-source-status-pill" data-coverage-status={section.status}>
                    {coverageStatusLabel(section.status)}
                  </span>
                </td>
                <td>{coverageLatestDate(section)}</td>
                <td>{section.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {highlightMetric ? (
        <div className="market-data-source-gate-highlight">
          <span>{highlightMetric.title}</span>
          <strong>{highlightMetric.value}</strong>
          <small>{highlightMetric.detail}</small>
        </div>
      ) : null}
      <nav
        className="market-data-terminal-anchor-nav"
        aria-label="市场数据终端导航"
        data-testid="market-data-terminal-workbench-nav"
      >
        <a href="#market-data-core-workbench">利率曲线</a>
        <a href="#market-data-liquidity-deck">资金与存单</a>
        <a href="#market-data-evidence-gate">证据口径</a>
      </nav>
    </section>
  );
}

function MarketDataApiSupplyOverview({
  sections,
}: {
  sections: MarketDataCoverageSection[];
}) {
  const preferredKeys = [
    "formal_rates",
    "macro_catalog",
    "macro_latest",
    "fx_formal",
    "bond_futures",
    "ncd_proxy",
  ];
  const byKey = new Map(sections.map((section) => [section.key, section]));
  const cards = preferredKeys.map((key) => byKey.get(key)).filter(Boolean) as MarketDataCoverageSection[];
  const fallbackCards = cards.length > 0 ? cards : sections.slice(0, 6);
  return (
    <section className="market-data-api-supply-overview" data-testid="market-data-api-supply-overview">
      <header className="market-data-panel-head">
        <span>API 供给概览</span>
        <strong>页面级供给</strong>
      </header>
      <div className="market-data-api-supply-grid">
        {fallbackCards.map((section) => (
          <article key={section.key} data-coverage-status={section.status}>
            <span>{marketDataSectionLabel(section)}</span>
            <strong>{coverageSectionCount(section)}</strong>
            <small>{coverageStatusLabel(section.status)}</small>
          </article>
        ))}
      </div>
    </section>
  );
}

function countCoverageSections(
  sections: MarketDataCoverageSection[],
  predicate: (section: MarketDataCoverageSection) => boolean,
) {
  return sections.filter(predicate).length;
}

function MarketDataLedgerToolbar({
  clientMode,
  watchDate,
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
}: {
  clientMode: "real" | "mock";
  watchDate: string;
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
}) {
  const curveLockLabel =
    curveFilter === "treasury" ? "国债曲线" : curveFilter === "cdb" ? "国开曲线" : "全曲线";
  const tickerStatusLabel = buildLedgerTickerStatusLabel(formalUseBlocked, isFormalBasis);
  const formalBasisChipLabel = isFormalBasis ? "正式" : "分析/候选";

  return (
    <div className="market-data-ledger-chrome" data-testid="market-data-ledger-toolbar">
      <MarketTerminalTicker
        compact
        items={[...terminalTickerItems]}
        emptyReason={terminalTickerEmptyReason}
        statusDate={watchDate}
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
        <span className="market-data-ledger-status-strip__detail" data-testid="market-data-readiness-verdict">
          {readinessVerdict}
        </span>
        <span className="market-data-ledger-status-strip__detail" data-testid="market-data-overview-readiness-label">
          {overviewReadinessLabel}
        </span>
        <span className="market-data-ledger-status-strip__detail" data-testid="market-data-overview-secondary-label">
          {secondaryLabel}
        </span>
        <span className="market-data-ledger-status-strip__detail">
          {clientMode === "real" ? "真实 DuckDB 读路径" : "本地契约回放"}
        </span>
        <span className="market-data-ledger-status-strip__detail" data-testid="market-data-active-filter-summary">
          当前生效：{activeFilterSummary}
        </span>
        <span className="market-data-ledger-status-strip__detail" data-testid="market-data-rate-curve-lock">
          {curveLockLabel}
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
            <span>代理口径</span>
            <strong>{proxyCount}</strong>
            <small>不作正式矩阵</small>
          </article>
          <article data-testid="market-data-coverage-bucket-source-pending" data-tone="pending">
            <span>待接入口径</span>
            <strong>{sourcePendingCount}</strong>
            <small>数据源未闭合</small>
          </article>
          <article data-tone="stale">
            <span>陈旧数据</span>
            <strong>{staleCount}</strong>
          </article>
          <article data-tone="error">
            <span>错误数据</span>
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
              <em>{coverageStatusLabel(section.status)}</em>
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
              {hasRows ? (
                rows.map((row) => (
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
              ) : (
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

function MarketDataLedgerSupportRow({
  sections,
  catalogCount,
  latestCount,
  fxGroupCount,
  calendarState,
}: {
  sections: MarketDataCoverageSection[];
  catalogCount: number;
  latestCount: number;
  fxGroupCount: number;
  calendarState: NewsAndCalendarCalendarState;
}) {
  const catalogCoverage = catalogCount > 0 ? `${Math.round((latestCount / catalogCount) * 1000) / 10}%` : "--";
  const fxFormal = sections.find((section) => section.key === "fx_formal");
  return (
    <section className="market-data-ledger-support-row" data-testid="market-data-ledger-support-row">
      <article className="market-data-support-card">
        <header>
          <strong>宏观数据（目录与最新）</strong>
          <a href="#market-data-macro-series">查看宏观数据</a>
        </header>
        <dl>
          <div>
            <dt>目录</dt>
            <dd>{catalogCount}</dd>
          </div>
          <div>
            <dt>最新</dt>
            <dd>{latestCount}</dd>
          </div>
          <div>
            <dt>覆盖率</dt>
            <dd>{catalogCoverage}</dd>
          </div>
        </dl>
      </article>
      <MarketDataLedgerEventsCard calendarState={calendarState} />
      <article className="market-data-support-card">
        <header>
          <strong>外汇概览（正式口径）</strong>
          <a href="#market-data-evidence-gate">查看外汇详情</a>
        </header>
        <dl>
          <div>
            <dt>外汇正式</dt>
            <dd>{coverageStatusLabel(fxFormal?.status ?? "empty")}</dd>
          </div>
          <div>
            <dt>外汇分析组</dt>
            <dd>{fxGroupCount}</dd>
          </div>
          <div>
            <dt>最新日期</dt>
            <dd>{coverageLatestDate(fxFormal)}</dd>
          </div>
        </dl>
      </article>
    </section>
  );
}

function formatFxPreviewRate(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) {
    return "--";
  }
  return value.toFixed(4);
}

function MarketDataSurfacePreviewBand({
  latestSeries,
  terminalModel,
  fxFormalStatus,
  fxAnalyticalGroups,
  coverageSections,
  sourcePendingCount,
  watchDate,
  readinessVerdict,
  ratesBasisLabel,
}: {
  latestSeries: ChoiceMacroLatestPoint[];
  terminalModel: MarketDataTerminalModel;
  fxFormalStatus: FxFormalStatusPayload | null;
  fxAnalyticalGroups: FxAnalyticalPayload["groups"];
  coverageSections: MarketDataCoverageSection[];
  sourcePendingCount: number;
  watchDate: string;
  readinessVerdict: string;
  ratesBasisLabel: string;
}) {
  const formalRatesSection = coverageSections.find((section) => section.key === "formal_rates");
  const macroLatestSection = coverageSections.find((section) => section.key === "macro_latest");
  const ncdProxySection = coverageSections.find((section) => section.key === "ncd_proxy");
  const primaryMacro = latestSeries[0];
  const primaryMoney =
    terminalModel.moneyMarket.rows.find((row) => row.name === "DR007") ?? terminalModel.moneyMarket.rows[0];
  const primaryFx = fxFormalStatus?.rows[0];
  const primaryFutures = terminalModel.bondFutures.rows[0];
  const moneyRows = terminalModel.moneyMarket.rows.slice(0, 2);
  const fxRows = (fxFormalStatus?.rows ?? []).slice(0, 2);
  const bondFuturesRows = terminalModel.bondFutures.rows.slice(0, 2);
  const fxFormalMaterialized = fxFormalStatus?.materialized_count ?? 0;
  const fxFormalCandidates = fxFormalStatus?.candidate_count ?? 0;
  const fxAnalyticalSeriesCount = fxAnalyticalObservationCount(fxAnalyticalGroups);
  const formalRatesCount = formalRatesSection
    ? coverageSectionCount(formalRatesSection)
    : String(terminalModel.rateQuotes.rows.length);
  const macroLatestCount = macroLatestSection ? coverageSectionCount(macroLatestSection) : String(latestSeries.length);
  const ncdProxyCount = ncdProxySection ? coverageSectionCount(ncdProxySection) : "1";
  const ratesBasisText = marketDataBasisLabel(ratesBasisLabel);
  const futuresDetail = primaryFutures
    ? `${primaryFutures.memberName} / 多头 ${primaryFutures.longHoldingText} / ${primaryFutures.tradeDate}`
    : "待接入：现券成交 / 信用成交";
  const futuresState = primaryFutures
    ? "ready"
    : terminalModel.bondFutures.status === "source-pending"
      ? "pending"
      : "gap";

  return (
    <section className="market-data-surface-preview-band" data-testid="market-data-surface-preview-band">
      <header className="market-data-surface-preview-band__head">
        <div>
          <span>市场数据判断</span>
          <strong>先看正式利率，分析读面辅助，待接入项直接暴露</strong>
          <p>
            国债、国开利率与资金面进入首屏；宏观、外汇、存单代理和成交契约按正式、分析、代理、待接入分层呈现，
            外汇分析 {fxAnalyticalSeriesCount} 条仅作为辅助观察。
          </p>
        </div>
        <div className="market-data-surface-preview-meta">
          <span>
            观察日 <strong>{watchDate || "--"}</strong>
          </span>
          <span>
            读面 <strong>{readinessVerdict}</strong>
          </span>
          <span>
            口径 <strong>{ratesBasisText}</strong>
          </span>
          <span data-tone={sourcePendingCount > 0 ? "pending" : "ready"}>
            待接入 <strong>{sourcePendingCount}</strong>
          </span>
        </div>
      </header>
      <div className="market-data-surface-preview-grid">
        <InstitutionalKpiTile
          label="正式利率"
          value={formalRatesCount}
          detail={`主表 ${terminalModel.rateQuotes.rows.length} 行 / ${ratesBasisText}`}
          status="正式"
          priority="primary"
          state={terminalModel.rateQuotes.rows.length > 0 ? "ready" : "gap"}
          testId="market-data-preview-formal-rates"
          className="market-data-surface-kpi-tile"
        />
        <InstitutionalKpiTile
          label="宏观最新"
          value={macroLatestCount}
          detail={
            primaryMacro
              ? `${marketDataSeriesNameLabel(primaryMacro.series_name)} / ${formatChoiceMacroValue(primaryMacro)}`
              : "暂无宏观最新数据"
          }
          status={primaryMacro ? "分析" : "无数据"}
          priority="primary"
          state={primaryMacro ? "ready" : "gap"}
          testId="market-data-preview-macro-latest"
          className="market-data-surface-kpi-tile"
        />
        <InstitutionalKpiTile
          label="资金利率"
          value={primaryMoney?.rateText ?? "--"}
          detail={
            primaryMoney
              ? `${primaryMoney.name} / ${primaryMoney.deltaText} / ${primaryMoney.tradeDate}`
              : terminalModel.moneyMarket.emptyReason
          }
          status={marketDataStatusLabel(terminalModel.moneyMarket.status)}
          priority="primary"
          state={primaryMoney ? "ready" : "gap"}
          testId="market-data-preview-money-market"
          className="market-data-surface-kpi-tile"
        />
        <article
          className="market-data-surface-preview-card market-data-surface-preview-card--legacy"
          data-testid="market-data-preview-money-market-legacy"
        >
          <header>
            <strong>资金利率</strong>
            <span>{marketDataStatusLabel(terminalModel.moneyMarket.status)}</span>
          </header>
          {moneyRows.length ? (
            <ul className="market-data-surface-preview-list">
              {moneyRows.map((row) => (
                <li key={row.seriesId}>
                  <span>{row.name}</span>
                  <strong>{row.rateText}</strong>
                  <em>{row.deltaText} · {row.tradeDate}</em>
                </li>
              ))}
            </ul>
          ) : (
            <p className="market-data-surface-preview-empty">{terminalModel.moneyMarket.emptyReason}</p>
          )}
        </article>
        <InstitutionalKpiTile
          label="外汇正式"
          value={primaryFx ? formatFxPreviewRate(primaryFx.mid_rate) : `${fxFormalMaterialized}/${fxFormalCandidates}`}
          detail={
            primaryFx
              ? `${primaryFx.pair_label} / ${marketDataStatusLabel(primaryFx.status)}${primaryFx.is_carry_forward ? " / 递延" : ""}`
              : "正式数据待接入"
          }
          status={fxFormalStatus?.latest_trade_date ?? "待接入"}
          priority="primary"
          state={primaryFx ? "ready" : "pending"}
          testId="market-data-preview-fx-formal"
          className="market-data-surface-kpi-tile"
        />
        <InstitutionalKpiTile
          label="外汇分析"
          value={String(fxAnalyticalSeriesCount)}
          detail={`${fxAnalyticalGroups.length} 组 / 仅观察`}
          status="分析"
          priority="secondary"
          state={fxAnalyticalSeriesCount > 0 ? "ready" : "gap"}
          testId="market-data-preview-fx-analytical"
          className="market-data-surface-kpi-tile"
        />
        <InstitutionalKpiTile
          label="存单代理"
          value={ncdProxyCount}
          detail={ncdProxySection ? `代理口径 / ${coverageLatestDate(ncdProxySection)}` : "代理口径 / 正式待定"}
          status="代理"
          priority="secondary"
          state="pending"
          testId="market-data-preview-ncd-proxy"
          className="market-data-surface-kpi-tile"
        />
        <article
          className="market-data-surface-preview-card market-data-surface-preview-card--legacy"
          data-testid="market-data-preview-fx-formal-legacy"
        >
          <header>
            <strong>外汇正式</strong>
            <span>{fxFormalStatus?.latest_trade_date ?? "待接入"}</span>
          </header>
          {fxRows.length ? (
            <ul className="market-data-surface-preview-list">
              {fxRows.map((row) => (
                <li key={row.series_id}>
                  <span>{row.pair_label}</span>
                  <strong>{formatFxPreviewRate(row.mid_rate)}</strong>
                  <em>{marketDataStatusLabel(row.status)}{row.is_carry_forward ? " · 递延" : ""}</em>
                </li>
              ))}
            </ul>
          ) : (
            <p className="market-data-surface-preview-empty">外汇正式行待接入。</p>
          )}
        </article>
        <InstitutionalKpiTile
          label="期货/成交"
          value={primaryFutures?.contract ?? String(sourcePendingCount)}
          detail={futuresDetail}
          status={primaryFutures ? marketDataStatusLabel(terminalModel.bondFutures.status) : "待接入"}
          priority="secondary"
          state={futuresState}
          testId="market-data-preview-trades-futures"
          className="market-data-surface-kpi-tile"
        />
        <article
          className="market-data-surface-preview-card market-data-surface-preview-card--legacy"
          data-testid="market-data-preview-trades-futures-legacy"
        >
          <header>
            <strong>期货/成交</strong>
            <span>{marketDataStatusLabel(terminalModel.bondFutures.status)}</span>
          </header>
          {bondFuturesRows.length ? (
            <ul className="market-data-surface-preview-list">
              {bondFuturesRows.map((row) => (
                <li key={row.key}>
                  <span>{row.contract} · {row.memberName}</span>
                  <strong>{row.longHoldingText}</strong>
                  <em>{row.tradeDate}</em>
                </li>
              ))}
            </ul>
          ) : (
            <p
              className="market-data-surface-preview-empty"
              data-testid="market-data-preview-futures-source-pending"
            >
              待接入 · 现券成交 / 信用成交
            </p>
          )}
        </article>
      </div>
    </section>
  );
}

export default function MarketDataPage() {
  const client = useApiClient();
  const [livermoreExpanded, setLivermoreExpanded] = useState(false);
  const [linkageCollapseExpanded, setLinkageCollapseExpanded] = useState(false);
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
    livermoreStrategyQuery,
    macroBondLinkageQuery,
    ncdFundingProxy,
    refreshGateSupplement,
  } = useMarketDataPageData({
    livermoreEnabled: livermoreExpanded,
    linkageEnabled: linkageFetchEnabled,
  });
  const calendarQuery = useQuery({
    queryKey: ["market-data", "calendar", "supply-auctions", client.mode],
    queryFn: () => client.getResearchCalendarEvents({}),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "stable", fetch_mode: "date_slice" }),
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
  const bridgeKpiMetrics = useMemo(
    () => buildBridgeKpiMetrics(filteredTerminalKpiMetrics),
    [filteredTerminalKpiMetrics],
  );
  const railHighlightMetric = useMemo(
    () => pickRailHighlightMetric(filteredTerminalKpiMetrics),
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
  const ratesBasisLabel = `${marketDataBasisLabel(ratesBasisValue)}${
    formalUseBlocked ? " · 禁用" : ""
  }`;
  const formalUseAllowedLabel =
    formalRatesMeta?.formal_use_allowed === undefined
      ? "待确认"
      : formalRatesMeta.formal_use_allowed
        ? "是"
        : "否";
  const sourceGateFields = [
    { label: "口径", value: ratesBasisLabel },
    { label: "正式可用", value: formalUseAllowedLabel },
    { label: "供应商", value: marketDataStatusLabel(formalRatesMeta?.vendor_status ?? "unknown") },
    { label: "降级", value: marketDataFallbackLabel(formalRatesMeta?.fallback_mode ?? rateQuotesSource?.fallbackMode ?? "unknown") },
    { label: "来源版本", value: marketDataSourceLabel(formalRatesMeta?.source_version ?? rateQuotesSource?.sourceVersion ?? "source-pending") },
  ];
  const basisChipLabel = buildMarketDataBasisChipLabel({
    basisLabel: ratesBasisLabel,
    formalUseAllowedLabel,
    formalUseBlocked,
    watchDate,
  });
  const marketWorkbenchStatus = {
    label: isFormalBasis ? (formalUseBlocked ? "正式禁用" : "正式片段") : "混合来源",
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
        message: bondFuturesCount > 0 ? "国债期货分析排名可用。" : "国债期货数据源待接入。",
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
        message: "终端模型未返回行时，现券成交契约保持待接入。",
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
        message: "终端模型未返回行时，信用成交契约保持待接入。",
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
        data-layout-rev="2026-06-15g"
        data-view-mode={viewMode}
      >
      <section className="market-data-terminal-cockpit" data-testid="market-data-terminal-cockpit">
        <div
          className="market-data-terminal-primary-grid market-data-terminal-primary-grid--ledger-first"
          data-testid="market-data-terminal-primary-grid"
        >
          <div className="market-data-ledger-first-shell" data-testid="market-data-ledger-first-shell">
            <div className="market-data-macro-workbench" data-testid="market-data-macro-workbench">
              <MarketDataLedgerToolbar
                clientMode={clientMode}
                watchDate={watchDate}
                onWatchDateChange={setWatchDate}
                isFormalBasis={isFormalBasis}
                readinessVerdict={statusBadges.readinessVerdict}
                overviewReadinessLabel={statusBadges.overviewReadinessLabel}
                secondaryLabel={statusBadges.secondaryLabel}
                refreshStatus={refreshStatus}
                refreshError={refreshError}
                isRefreshing={isRefreshing}
                onRefresh={handleRefresh}
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
              />
              <MarketDataSurfacePreviewBand
                latestSeries={latestSeries}
                terminalModel={terminalModel}
                fxFormalStatus={fxFormalStatus}
                fxAnalyticalGroups={fxAnalyticalGroups}
                coverageSections={displayedCoverageSections}
                sourcePendingCount={sourcePendingCount}
                watchDate={watchDate}
                readinessVerdict={statusBadges.readinessVerdict}
                ratesBasisLabel={ratesBasisLabel}
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
              <MarketDataSupplyEvidenceRail
                summary={coverageSummary}
                sections={displayedCoverageSections}
                watchDate={watchDate}
              />
              <div className="market-data-ledger-first-grid" data-testid="market-data-ledger-first-grid">
                <MarketDataCoverageLedger sections={displayedCoverageSections} />
              </div>
              <MarketDataLedgerSupportRow
                sections={displayedCoverageSections}
                catalogCount={catalog.length}
                latestCount={latestSeries.length}
                fxGroupCount={fxAnalyticalGroups.length}
                calendarState={sharedCalendarState}
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
              <MarketDataDeskBridgeBand
                basisChipLabel={basisChipLabel}
                bridgeMetrics={bridgeKpiMetrics}
                emptyReason={terminalModel.rateQuotes.emptyReason}
                watchDate={watchDate}
              />
            </div>
          </div>
          {false ? (
          <>
          <MarketDataCoverageCommand summary={coverageSummary} sections={displayedCoverageSections} />
          <div className="market-data-analyst-split" data-testid="market-data-analyst-split">
          <div className="market-data-analyst-workbench" data-testid="market-data-macro-workbench">
          <div
            className="market-data-terminal-main-column market-data-terminal-primary-column"
            data-testid="market-data-terminal-main-column"
          >
            <div className="market-data-top-core-panel">
              <div className="market-data-section-lead--compact">
                <MarketSectionLead
                  eyebrow="核心观察"
                  title="利率曲线与宏观深度"
                  description="左侧为正式利率片段主表；右侧标签为分析口径曲线、信用利差与联动摘要。"
                />
              </div>
              <MarketDataSeriesCategoryCard
                id="market-data-term-structure"
                title="利率行情"
                caption="国债 / 国开正式利率；表格与期限结构图在同一工作区内核对。"
                count={terminalModel.rateQuotes.rows.length}
                tone="formal"
                testId="market-data-rate-quote-card"
              >
                <RateQuoteTable
                  embedded
                  model={terminalModel.rateQuotes}
                  curveFilter={curveFilter}
                  sourceFilter={sourceFilter}
                  catalogVendorNames={catalogVendorNames}
                />
              </MarketDataSeriesCategoryCard>
              <div className="market-data-workbench-shared-meta" data-testid="market-data-workbench-shared-meta">
                <span>口径摘要 {ratesBasisLabel}</span>
                {formalUseBlocked ? <span>禁止作为正式口径</span> : null}
              </div>
            </div>
            <MarketDataDeskBridgeBand
              basisChipLabel={basisChipLabel}
              bridgeMetrics={bridgeKpiMetrics}
              emptyReason={terminalModel.rateQuotes.emptyReason}
              watchDate={watchDate}
            />
      <MarketDataHeroSection
        clientMode={clientMode}
        watchDate={watchDate}
        onWatchDateChange={setWatchDate}
        isFormalBasis={isFormalBasis}
        terminalKpiMetrics={filteredTerminalKpiMetrics}
        pipelineOverviewMetrics={pipelineOverviewMetrics}
        terminalTickerItems={filteredTickerItems}
        terminalTickerBasisLabel={
          formalRatesMeta?.basis === "formal"
            ? `正式口径 · ${formalRatesMeta?.formal_use_allowed ? "可用" : "禁用"}`
            : rateQuotesSource?.basis
              ? `口径 ${marketDataBasisLabel(rateQuotesSource?.basis)}`
              : undefined
        }
        terminalTickerEmptyReason={terminalModel.rateQuotes.emptyReason}
        readinessVerdict={statusBadges.readinessVerdict}
        overviewReadinessLabel={statusBadges.overviewReadinessLabel}
        secondaryLabel={statusBadges.secondaryLabel}
        refreshStatus={refreshStatus}
        refreshError={refreshError}
        isRefreshing={isRefreshing}
        onRefresh={handleRefresh}
        curveFilter={curveFilter}
        onCurveFilterChange={setCurveFilter}
        creditSegment={creditSegment}
        onCreditSegmentChange={setCreditSegment}
        sourceFilter={sourceFilter}
        onSourceFilterChange={setSourceFilter}
        activeFilterSummary={activeFilterSummary}
        showTerminalKpiStrip={false}
        showPipelineKpiStrip={false}
      />

      {MARKET_DATA_SHOW_OVERVIEW_META_STRIP && macroMeta ? (
        <div className="market-data-meta-strip">
          <LiveResultMetaStrip
            lead="市场概览·宏观读面（最新优先）"
            meta={macroMeta}
            testId="market-data-overview-live-meta"
          />
        </div>
      ) : null}
          </div>

          <aside className="market-data-terminal-evidence-column" data-testid="market-data-terminal-evidence-column">
            <MarketDataCoverageLedger sections={displayedCoverageSections} />
            <MarketDataSourceGatePanel
              sourceGateFields={sourceGateFields}
              sections={displayedCoverageSections}
              highlightMetric={railHighlightMetric}
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
            <MarketDataApiSupplyOverview sections={displayedCoverageSections} />
          </aside>
          </div>
          </div>
          </>) : null}
        </div>
      </section>

      <MarketDataEvidenceRailSection>
        <section
          id="market-data-evidence-gate"
          className="market-data-macro-evidence-rail"
          data-testid="market-data-macro-evidence-rail"
        >
          <span>{marketDataEvidenceLineLabel(evidenceLines.formalRates)}</span>
          <span>{marketDataEvidenceLineLabel(evidenceLines.macroLatest)}</span>
          <span>{marketDataEvidenceLineLabel(evidenceLines.fxFormal)}</span>
          <span>{marketDataEvidenceLineLabel(evidenceLines.fxAnalytical)}</span>
          <span>{marketDataEvidenceLineLabel(evidenceLines.ncdProxy)}</span>
          <span>{marketDataEvidenceLineLabel(evidenceLines.livermore)}</span>
          <span>{marketDataEvidenceLineLabel(evidenceLines.linkage)}</span>
        </section>
      </MarketDataEvidenceRailSection>

      <MarketSectionBlock>
        <MarketPipelineKpiStrip metrics={pipelineOverviewMetrics} />
      </MarketSectionBlock>

      <MarketSectionBlock>
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
      </MarketSectionBlock>

      <MarketSectionBlock>
        <div className="market-data-lower-deck-section">
          <MarketDataTushareSupplementSection />
        </div>
      </MarketSectionBlock>

      <MarketSectionBlock>
        <div className="market-data-lower-deck-section">
          <NewsAndCalendar calendarState={sharedCalendarState} />
        </div>
      </MarketSectionBlock>

      {MARKET_DATA_SHOW_MACRO_SERIES_DECK || MARKET_DATA_SHOW_FX_ANALYSIS_SECTION ? (
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
      ) : null}

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

      <MarketDataFxFormalSection
        payload={pageModel.fxFormalStatus}
        meta={pageModel.fxFormalMeta}
        isLoading={fxFormalStatusQuery.isLoading}
        isError={fxFormalStatusQuery.isError}
        onRetry={() => void fxFormalStatusQuery.refetch(nonCancellingRefetchOptions)}
      />

      <MarketDataExtendedTerminalSection sourcePendingCount={sourcePendingCount}>
        <div className="market-data-observation-grid" data-testid="market-data-source-pending-deck">
          <BondFuturesTable model={terminalModel.bondFutures} />
          <BondTradeDetail model={terminalModel.bondTrades} />
          <CreditBondTradesTable model={terminalModel.creditTrades} />
        </div>
        <div className="market-data-source-pending-summary" data-testid="market-data-source-pending-summary">
          待契约 {sourcePendingCount}
          <span data-testid="market-data-source-pending-contract-note">
            · 国债期货 / 现券成交 / 信用成交
          </span>
        </div>
      </MarketDataExtendedTerminalSection>

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

      {MARKET_DATA_SHOW_MACRO_OBSERVATION_AND_CATALOG_EVIDENCE ? (
        <MarketSectionBlock>
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
        </MarketSectionBlock>
      ) : null}
      </section>
    </MarketWorkbenchFrame>
  );
}
