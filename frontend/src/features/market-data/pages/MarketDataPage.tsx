import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { Collapse, Select } from "antd";
import { flushSync } from "react-dom";
import { useApiClient } from "../../../api/client";
import {
  DataQualityPill,
  DiagnosticDisclosure,
} from "../../../components/StatusPill";
import { externalDataQueryOptions, nonCancellingRefetchOptions } from "../../../app/externalDataRefreshPolicy";
import { PageSectionLead, type PageSectionLeadProps } from "../../../components/page/PagePrimitives";
import {
  DataStatusStrip,
  KpiBand,
  KpiBandMetric,
  PageDecisionHero,
} from "../../../components/page/PagePrimitives";
import { designTokens } from "../../../theme/designSystem";
import type {
  MarketDataCoverageSection,
  MarketDataCoverageSummaryPayload,
} from "../../../api/contracts";
import { BondFuturesTable } from "../components/BondFuturesTable";
import { BondTradeDetail } from "../components/BondTradeDetail";
import { CreditBondTradesTable } from "../components/CreditBondTradesTable";
import { MarketDataExtendedTerminalSection } from "../components/MarketDataExtendedTerminalSection";
import { MarketDataDetailDeck } from "../components/MarketDataDetailDeck";
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
import { NewsAndCalendar } from "../components/NewsAndCalendar";
import { MarketDataSeriesCategoryCard } from "../components/MarketDataSeriesCategoryCard";
import { MarketDataTushareSupplementSection } from "../components/MarketDataTushareSupplementSection";
import { MarketDataTermStructureChart } from "../components/MarketDataTermStructureChart";
import { marketCatalogRefreshTier } from "../lib/marketDataCategoryStore";
import {
  buildCatalogVendorNameMap,
  filterMoneyMarketRows,
  filterRateQuoteRows,
  filterTerminalTickerItems,
  type MarketDataRateQuoteSection,
} from "../lib/marketDataTerminalModel";
import { useMarketDataPageData } from "../hooks/useMarketDataPageData";
import type { MarketOverviewMetric } from "./MarketDataHeroSection";
import { MarketDataMacroDepthTabs } from "./MarketDataMacroDepthTabs";
import { MarketDataFigmaDesktopView } from "./MarketDataFigmaDesktopView";
import { buildSpreadSlots, buildMarketDataBasisChipLabel, buildTerminalKpiMetricsFromTickerItems, formatMarketWorkbenchSourceSummary } from "./marketDataPageModel";
import { useLazyMount } from "../lib/useLazyMount";
import { MarketWorkbenchFrame } from "../../workbench/market-shell";
import "./MarketDataPage.css";
import "./marketDataNocturne.css";

/** 展示已拉取的宏观稳定/降级序列（不含页尾目录运维面板）。 */
const MARKET_DATA_SHOW_MACRO_SERIES_DECK = true;

/** 展示已拉取的外汇分析序列分组。 */
const MARKET_DATA_SHOW_FX_ANALYSIS_SECTION = true;

/** Legacy terminal remains source-compatible while the routed page renders only the approved Figma surface. */
const MARKET_DATA_SHOW_LEGACY_SURFACE = false;

const MARKET_DATA_CURVE_FILTER_OPTIONS = [
  { value: "both", label: "国债+国开" },
  { value: "treasury", label: "国债" },
  { value: "cdb", label: "国开" },
] as const;

const MARKET_DATA_SOURCE_FILTER_OPTIONS = [
  { value: "all", label: "全部来源" },
  { value: "choice", label: "Choice" },
  { value: "internal", label: "内部" },
] as const;

const MARKET_DATA_CREDIT_FILTER_OPTIONS = [
  { value: "both", label: "全部信用" },
  { value: "mtn", label: "中票" },
  { value: "urban", label: "城投" },
] as const;

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

function isAccessDeniedError(error: unknown): boolean {
  if (!error || typeof error !== "object") {
    return false;
  }
  const status = (error as { status?: unknown; response?: { status?: unknown } }).status
    ?? (error as { response?: { status?: unknown } }).response?.status;
  if (status === 403) {
    return true;
  }
  const message = error instanceof Error ? error.message : String(error);
  return /(^|\D)403(\D|$)|forbidden|permission|not allowed|access denied|无权限|不允许/i.test(message);
}

function marketDataEvidenceLineLabel(line: string): string {
  const labels: Record<string, string> = {
    "formal rates": "正式市场序列",
    "macro latest": "市场与宏观最新",
    "FX formal": "外汇正式",
    "FX analytical": "外汇分析",
    "NCD proxy": "存单代理",
    Livermore: "利弗莫尔",
    "macro-bond linkage": "宏观债券联动",
  };
  const [rawLabel, detail] = line.split(/:\s*/, 2);
  return `${labels[rawLabel] ?? rawLabel}：${detail ?? "查看数据诊断"}`;
}

function coverageActionLabel(section: MarketDataCoverageSection): string {
  if (section.source_pending) return "接入数据源";
  if (section.proxy_only) return "确认正式口径";
  if (section.status === "deferred") return "按需展开";
  if (section.fallback_mode !== "none") return "查看数据延迟";
  return "查看详情";
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

function countCoverageSections(
  sections: MarketDataCoverageSection[],
  predicate: (section: MarketDataCoverageSection) => boolean,
) {
  return sections.filter(predicate).length;
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

export default function MarketDataPage() {
  const client = useApiClient();
  const [livermoreExpanded, setLivermoreExpanded] = useState(false);
  const [linkageCollapseExpanded, setLinkageCollapseExpanded] = useState(false);
  const [deferredWorkspacesRequested, setDeferredWorkspacesRequested] = useState(false);
  const [supplementarySectionRequested, setSupplementarySectionRequested] = useState(
    () => typeof window !== "undefined" && window.location.hash === "#market-data-macro-series",
  );
  const lazyExtended = useLazyMount({ rootMargin: "300px", fallbackDelayMs: 0 });
  const lazySupplementary = useLazyMount({ rootMargin: "300px", fallbackDelayMs: 0 });
  const lazyDetails = useLazyMount({ rootMargin: "500px", fallbackDelayMs: 2500 });
  // The delay only protects no-IntersectionObserver environments; normal browsers wait for viewport proximity.
  const lazyLivermore = useLazyMount({ rootMargin: "400px", fallbackDelayMs: 2000 });
  const [macroDepthTab, setMacroDepthTab] = useState<"curve" | "spreads" | "linkage">("curve");
  const [viewMode] = useState<"default" | "compact">("default");
  const [curveFilter, setCurveFilter] = useState<"treasury" | "cdb" | "both">("both");
  const [creditSegment, setCreditSegment] = useState<"mtn" | "urban" | "both">("both");
  const [sourceFilter, setSourceFilter] = useState<"all" | "choice" | "internal">("all");
  const linkageFetchEnabled =
    linkageCollapseExpanded ||
    lazyDetails.shouldMount ||
    macroDepthTab === "spreads" ||
    macroDepthTab === "linkage" ||
    creditSegment !== "both";
  const {
    watchDate,
    setWatchDate,
    isRefreshing,
    refreshStatus,
    refreshError,
    handleRefresh,
    pageModel,
    catalogQuery,
    latestQuery,
    externalDataWatermarksQuery,
    fxAnalyticalQuery,
    fxFormalStatusQuery,
    ncdFundingProxyQuery,
    bondFuturesRankingsQuery,
    coverageSummaryQuery,
    livermoreStrategyQuery,
    formalRatesQuery,
    macroBondLinkageQuery,
    ncdFundingProxy,
    refreshGateSupplement,
  } = useMarketDataPageData({
    // Defer the heavy Livermore strategy payload until the section approaches the viewport.
    livermoreEnabled: lazyLivermore.shouldMount || livermoreExpanded,
    linkageEnabled: linkageFetchEnabled,
  });
  const tushareSupplementQuery = useQuery({
    queryKey: ["market-data", "tushare-supplement", client.mode],
    queryFn: () => client.getTushareSupplement({ moneySupplyLimit: 120, ecoCalLimit: 300 }),
    enabled: lazyDetails.shouldMount,
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
    refetchOnWindowFocus: false,
  });
  const supplyCalendarQuery = useQuery({
    queryKey: ["market-data", "supply-calendar", client.mode, watchDate],
    queryFn: () =>
      client.getResearchCalendarEvents({
        reportDate: watchDate || undefined,
      }),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
    refetchOnWindowFocus: false,
  });
  const choiceNewsQuery = useQuery({
    queryKey: ["market-data", "headlines", "choice-events", client.mode],
    queryFn: () => client.getChoiceNewsEvents({ limit: 12, offset: 0, includePayloadJson: false }),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "stable", fetch_mode: "date_slice" }),
    refetchOnWindowFocus: false,
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
    fxAnalyticalGroups,
    rateTrendChartOption,
    livermoreStrategy,
    macroBondLinkage,
    macroBondLinkageWarnings,
    hasPortfolioImpact,
    nonSpreadTopCorrelations,
    formalRatesMeta,
    rateQuotesSource,
    sourcePendingCount,
    isFormalBasis,
    statusBadges,
    evidenceLines,
    pipelineOverviewMetrics,
    terminalTickerItems,
    latestSeries,
  } = pageModel;
  const macroSeriesLoading = catalogQuery.isLoading || latestQuery.isLoading;
  const macroSeriesError = catalogQuery.isError || latestQuery.isError;
  const macroSeriesEmpty =
    !macroSeriesLoading &&
    !macroSeriesError &&
    stableSeries.length === 0 &&
    fallbackSeries.length === 0;
  const refetchMacroSeries = () => {
    void Promise.all([
      catalogQuery.refetch(nonCancellingRefetchOptions),
      latestQuery.refetch(nonCancellingRefetchOptions),
    ]);
  };
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
  const filteredRateRows = useMemo(
    () =>
      filterRateQuoteRows(
        terminalModel.rateQuotes.rows,
        curveFilter,
        sourceFilter,
        catalogVendorNames,
      ),
    [terminalModel.rateQuotes.rows, curveFilter, sourceFilter, catalogVendorNames],
  );
  const filteredMoneyRows = useMemo(
    () =>
      filterMoneyMarketRows(
        terminalModel.moneyMarket.rows,
        sourceFilter,
        catalogVendorNames,
    ),
    [terminalModel.moneyMarket.rows, sourceFilter, catalogVendorNames],
  );
  const analyticalSubstituteCount = useMemo(
    () =>
      [...filteredRateRows, ...filteredMoneyRows].filter(
        (row) => row.basis !== "formal" || !row.formalUseAllowed,
      ).length,
    [filteredMoneyRows, filteredRateRows],
  );
  const filteredTerminalKpiMetrics = useMemo(
    () => buildTerminalKpiMetricsFromTickerItems(filteredTickerItems),
    [filteredTickerItems],
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
  const ratesBasisLabel = formalUseBlocked ? "formal · blocked" : marketDataBasisLabel(ratesBasisValue);
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
  const curveFilterLabel =
    MARKET_DATA_CURVE_FILTER_OPTIONS.find((option) => option.value === curveFilter)?.label ?? curveFilter;
  const sourceFilterLabel =
    MARKET_DATA_SOURCE_FILTER_OPTIONS.find((option) => option.value === sourceFilter)?.label ?? sourceFilter;
  const creditSegmentLabel =
    MARKET_DATA_CREDIT_FILTER_OPTIONS.find((option) => option.value === creditSegment)?.label ?? creditSegment;
  const tickerStatusDate =
    formalRatesMeta?.resolved_report_date ??
    formalRatesMeta?.as_of_date ??
    filteredTickerItems[filteredTickerItems.length - 1]?.tradeDate ??
    null;
  const marketWorkbenchStatus = {
    label: formalUseBlocked ? "分析/候选" : isFormalBasis ? "正式片段" : "混合来源",
    tone: formalUseBlocked ? "watch" : isFormalBasis ? "ok" : ("watch" as const),
    detail: formalUseBlocked
      ? "正式市场片段当前禁止作为正式口径；其余分析读面保持候选语义"
      : "正式市场片段 + 分析读面，未新增前端指标推导",
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
  const displayedCoverageSections = coverageSections;
  const coverageSummaryState = coverageSummaryQuery.isLoading
    ? "loading"
    : coverageSummaryQuery.isError
      ? "error"
      : coverageSummary && coverageSections.length > 0
        ? "ready"
        : "empty";
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
      tushareSupplementQuery.refetch(nonCancellingRefetchOptions),
      supplyCalendarQuery.refetch(nonCancellingRefetchOptions),
    ]);
  }, [
    handleRefresh,
    supplyCalendarQuery,
    tushareSupplementQuery,
  ]);

  useEffect(() => {
    const revealDeferredWorkspaces = () => {
      flushSync(() => setDeferredWorkspacesRequested(true));
    };
    const handleNativeFind = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "f") {
        revealDeferredWorkspaces();
      }
    };

    window.addEventListener("beforeprint", revealDeferredWorkspaces);
    window.addEventListener("keydown", handleNativeFind);
    return () => {
      window.removeEventListener("beforeprint", revealDeferredWorkspaces);
      window.removeEventListener("keydown", handleNativeFind);
    };
  }, []);

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
        setSupplementarySectionRequested(true);
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

  const heroKpiMetrics = useMemo(() => {
    const metrics = filteredTerminalKpiMetrics.length >= 4
      ? filteredTerminalKpiMetrics
      : pipelineOverviewMetrics;
    return metrics.slice(0, 4).map((metric) => ({
      label: metric.title,
      value: <span className="market-data-hero-kpi-value">{metric.value}</span>,
      footer: metric.detail,
      testId: metric.testId,
    }));
  }, [filteredTerminalKpiMetrics, pipelineOverviewMetrics]);

  const shouldRenderExtendedTerminalSection =
    deferredWorkspacesRequested ||
    terminalModel.bondFutures.rows.length > 0 ||
    terminalModel.bondTrades.rows.length > 0 ||
    terminalModel.creditTrades.rows.length > 0 ||
    sourcePendingCount > 0;

  const shouldRenderSupplementarySection =
    deferredWorkspacesRequested ||
    supplementarySectionRequested ||
    stableSeries.length + fallbackSeries.length > 0 ||
    fxAnalyticalGroups.length > 0;

  return (
    <MarketWorkbenchFrame
      pageKey="market-data"
      title="市场数据"
      question="当前市场利率、资金面、外汇状况如何？"
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
        className="market-data-page market-data-page--nocturne theme-dh-api"
        data-testid="market-data-page"
        data-layout-rev="2026-07-01-redesign"
        data-view-mode={viewMode}
      >
        <h1 className="market-data-sr-only" data-testid="market-data-page-title">
          市场数据
        </h1>
        <section className="market-data-filter-strip" data-testid="market-data-filter-strip">
          <div className="market-data-filter-strip-primary">
            <div className="market-data-filter-strip-head">
              <div>
                <span className="market-data-filter-strip-eyebrow">观察命令条</span>
                <strong>筛选与刷新</strong>
              </div>
              <p className="market-data-filter-strip-note">
                观察/请求日期仅影响本页请求与刷新；数据日期以后端实际返回为准。
              </p>
            </div>
            <div className="market-data-filter-strip-controls">
              <label className="market-data-filter-strip-date-group">
                <span>观察/请求日期</span>
                <input
                  type="date"
                  value={watchDate}
                  onChange={(e) => setWatchDate(e.target.value)}
                  className="market-data-hero-date-input"
                  data-testid="market-data-date-picker"
                  aria-label="市场数据观察日期"
                />
              </label>
              <div className="market-data-filter-strip-select-group">
                <span>利率曲线</span>
                <Select
                  size="small"
                  value={curveFilter}
                  onChange={setCurveFilter}
                  className="market-data-hero-select market-data-hero-select--curve"
                  aria-label="利率曲线筛选"
                  options={MARKET_DATA_CURVE_FILTER_OPTIONS.map((option) => ({ ...option }))}
                  data-testid="market-data-curve-filter"
                />
              </div>
              <div className="market-data-filter-strip-select-group">
                <span>数据来源</span>
                <Select
                  size="small"
                  value={sourceFilter}
                  onChange={setSourceFilter}
                  className="market-data-hero-select market-data-hero-select--source"
                  aria-label="数据来源筛选"
                  options={MARKET_DATA_SOURCE_FILTER_OPTIONS.map((option) => ({ ...option }))}
                  data-testid="market-data-source-filter"
                />
              </div>
              <div className="market-data-filter-strip-select-group">
                <span>信用分层</span>
                <Select
                  size="small"
                  value={creditSegment}
                  onChange={setCreditSegment}
                  className="market-data-hero-select market-data-hero-select--credit"
                  aria-label="信用分层筛选"
                  options={MARKET_DATA_CREDIT_FILTER_OPTIONS.map((option) => ({ ...option }))}
                  data-testid="market-data-credit-filter"
                />
              </div>
              <button
                onClick={handleMarketDataRefresh}
                disabled={isRefreshing}
                className="market-data-hero-refresh-btn"
                data-testid="market-data-refresh-btn"
              >
                {isRefreshing ? "刷新中…" : "刷新数据"}
              </button>
            </div>
          </div>
          <DataStatusStrip testId="market-data-active-filter-summary">
            <span>{statusBadges.readinessVerdict}</span>
            <span aria-hidden="true">·</span>
            <span>{statusBadges.overviewReadinessLabel}</span>
            <span aria-hidden="true">·</span>
            <span>{`观察/请求日期 ${watchDate || "待设置"}`}</span>
            <span aria-hidden="true">·</span>
            <span>{`数据日期 ${tickerStatusDate ?? "待返回"}`}</span>
            <span aria-hidden="true">·</span>
            <span>{`曲线 ${curveFilterLabel}`}</span>
            <span aria-hidden="true">·</span>
            <span>{`来源 ${sourceFilterLabel}`}</span>
            <span aria-hidden="true">·</span>
            <span>{`信用 ${creditSegmentLabel}`}</span>
            {formalUseBlocked ? (
              <>
                <span aria-hidden="true">·</span>
                <span className="market-data-hero-status-warn">{basisChipLabel}</span>
              </>
            ) : null}
            {isRefreshing ? (
              <>
                <span aria-hidden="true">·</span>
                <span className="market-data-hero-status-accent">{refreshStatus || "刷新中…"}</span>
              </>
            ) : null}
            {refreshError ? (
              <>
                <span aria-hidden="true">·</span>
                <span className="market-data-hero-status-danger">{refreshError}</span>
              </>
            ) : null}
          </DataStatusStrip>
        </section>
        <MarketDataFigmaDesktopView
          watchDate={watchDate}
          statusDate={tickerStatusDate}
          tickerItems={filteredTickerItems}
          rateRows={filteredRateRows}
          moneyRows={filteredMoneyRows}
          moneySeriesLoading={formalRatesQuery.isLoading || latestQuery.isLoading}
          moneySeriesError={formalRatesQuery.isError || latestQuery.isError}
          analyticalSubstituteCount={analyticalSubstituteCount}
          formalSeriesLoading={formalRatesQuery.isLoading}
          formalSeriesError={formalRatesQuery.isError}
          latestSeries={latestSeries}
          latestSeriesLoading={latestQuery.isLoading}
          latestSeriesError={latestQuery.isError}
          fxFormalStatus={pageModel.fxFormalStatus}
          fxFormalLoading={fxFormalStatusQuery.isLoading}
          fxFormalError={fxFormalStatusQuery.isError}
          ncdFundingProxy={ncdFundingProxy}
          ncdLoading={ncdFundingProxyQuery.isLoading}
          ncdError={ncdFundingProxyQuery.isError}
          coverageSummary={coverageSummary}
          coverageSections={displayedCoverageSections}
          coverageSummaryState={coverageSummaryState}
          catalogCount={catalog.length}
          catalogLoading={catalogQuery.isLoading}
          catalogError={catalogQuery.isError}
          livermorePayload={livermoreStrategyQuery.data?.result}
          livermoreLoading={livermoreStrategyQuery.isLoading}
          livermoreError={livermoreStrategyQuery.isError}
          linkagePayload={macroBondLinkageQuery.data?.result}
          linkageLoading={macroBondLinkageQuery.isLoading}
          linkageError={macroBondLinkageQuery.isError}
          newsPayload={choiceNewsQuery.data?.result ?? null}
          newsLoading={choiceNewsQuery.isLoading}
          newsError={choiceNewsQuery.isError}
          livermoreRef={lazyLivermore.ref}
          supplyEvents={supplyCalendarQuery.data ?? []}
          supplyLoading={supplyCalendarQuery.isLoading}
          supplyError={supplyCalendarQuery.isError}
        />
        <div data-testid="market-data-figma-news-panel">
          <NewsAndCalendar
            newsState={{
              payload: choiceNewsQuery.data?.result ?? null,
              isLoading: choiceNewsQuery.isLoading,
              isError: choiceNewsQuery.isError,
            }}
            calendarState={{
              rows: supplyCalendarQuery.data ?? [],
              isLoading: supplyCalendarQuery.isLoading,
              isError: supplyCalendarQuery.isError,
            }}
          />
        </div>
        <MarketDataDetailDeck
          detailRef={lazyDetails.ref}
          catalog={catalog}
          formalRateSeries={formalRatesQuery.data?.result.series ?? []}
          formalDerivedSpreads={formalRatesQuery.data?.result.derived_spreads}
          formalUseBlocked={formalUseBlocked}
          latestSeries={latestSeries}
          macroDerivedSpreads={latestQuery.data?.result.derived_spreads}
          fxFormalStatus={pageModel.fxFormalStatus}
          fxAnalytical={fxAnalyticalQuery.data?.result}
          ncdFundingProxy={ncdFundingProxy}
          bondFutures={bondFuturesRankingsQuery.data?.result}
          coverageSummary={coverageSummary}
          linkage={macroBondLinkageQuery.data?.result}
          creditSegment={creditSegment}
          creditSpreadSlots={spreadSlots}
          livermore={livermoreStrategyQuery.data?.result}
          watermarks={externalDataWatermarksQuery.data}
          tushare={tushareSupplementQuery.data?.result}
          supplyEvents={supplyCalendarQuery.data ?? []}
          resultMeta={[
            { key: "catalog", label: "宏观目录", meta: catalogQuery.data?.result_meta },
            { key: "formal-rates", label: "正式市场序列", meta: formalRatesQuery.data?.result_meta },
            { key: "macro-latest", label: "市场与宏观最新", meta: latestQuery.data?.result_meta },
            { key: "fx-formal", label: "外汇正式", meta: fxFormalStatusQuery.data?.result_meta },
            { key: "fx-analytical", label: "外汇分析", meta: fxAnalyticalQuery.data?.result_meta },
            { key: "ncd-proxy", label: "存单代理", meta: ncdFundingProxyQuery.data?.result_meta },
            { key: "bond-futures", label: "国债期货", meta: bondFuturesRankingsQuery.data?.result_meta },
            { key: "coverage", label: "覆盖摘要", meta: coverageSummaryQuery.data?.result_meta },
            { key: "linkage", label: "宏债联动", meta: macroBondLinkageQuery.data?.result_meta },
            { key: "livermore", label: "策略观察", meta: livermoreStrategyQuery.data?.result_meta },
            { key: "tushare", label: "补充数据", meta: tushareSupplementQuery.data?.result_meta },
          ]}
          loading={{
            catalog: catalogQuery.isLoading,
            formalRates: formalRatesQuery.isLoading,
            macroLatest: latestQuery.isLoading,
            fxFormal: fxFormalStatusQuery.isLoading,
            fxAnalytical: fxAnalyticalQuery.isLoading,
            ncd: ncdFundingProxyQuery.isLoading,
            bondFutures: bondFuturesRankingsQuery.isLoading,
            coverage: coverageSummaryQuery.isLoading,
            linkage: macroBondLinkageQuery.isLoading,
            livermore: livermoreStrategyQuery.isLoading,
            watermarks: externalDataWatermarksQuery.isLoading,
            tushare: tushareSupplementQuery.isLoading,
            supply: supplyCalendarQuery.isLoading,
          }}
          error={{
            catalog: catalogQuery.isError,
            formalRates: formalRatesQuery.isError,
            macroLatest: latestQuery.isError,
            fxFormal: fxFormalStatusQuery.isError,
            fxAnalytical: fxAnalyticalQuery.isError,
            ncd: ncdFundingProxyQuery.isError,
            bondFutures: bondFuturesRankingsQuery.isError,
            coverage: coverageSummaryQuery.isError,
            linkage: macroBondLinkageQuery.isError,
            livermore: livermoreStrategyQuery.isError,
            watermarks: externalDataWatermarksQuery.isError,
            tushare: tushareSupplementQuery.isError,
            supply: supplyCalendarQuery.isError,
          }}
          watermarksAccessDenied={isAccessDeniedError(externalDataWatermarksQuery.error)}
        />

        {MARKET_DATA_SHOW_LEGACY_SURFACE ? (
        <div className="market-data-deep-workspaces" data-testid="market-data-deep-workspaces">
        <PageDecisionHero
          title="市场数据"
          businessQuestion="当前市场利率、资金面、外汇状况如何？"
          eyebrow="市场数据终端"
          testId="market-data-hero"
          className="market-data-nocturne-command"
          reportDateSlot={
            <div className="market-data-hero-date-slot">
              <input
                type="date"
                value={watchDate}
                onChange={(e) => setWatchDate(e.target.value)}
                className="market-data-hero-date-input"
                data-testid="market-data-date-picker"
                aria-label="市场数据观察日期"
              />
              <span className="market-data-hero-date-note">
                {tickerStatusDate ? `数据日期 ${tickerStatusDate}` : ""}
              </span>
            </div>
          }
          conclusion={
            <DataStatusStrip testId="market-data-status-strip">
              <span>{statusBadges.readinessVerdict}</span>
              <span aria-hidden="true">·</span>
              <span>{statusBadges.overviewReadinessLabel}</span>
              {formalUseBlocked ? (
                <>
                  <span aria-hidden="true">·</span>
                  <span className="market-data-hero-status-warn">{basisChipLabel}</span>
                </>
              ) : null}
              {isRefreshing ? (
                <>
                  <span aria-hidden="true">·</span>
                  <span className="market-data-hero-status-accent">{refreshStatus || "刷新中…"}</span>
                </>
              ) : null}
              {refreshError ? (
                <>
                  <span aria-hidden="true">·</span>
                  <span className="market-data-hero-status-danger">{refreshError}</span>
                </>
              ) : null}
            </DataStatusStrip>
          }
          actions={
            <div className="market-data-hero-actions">
              <Select
                size="small"
                value={curveFilter}
                onChange={setCurveFilter}
                className="market-data-hero-select market-data-hero-select--curve"
                aria-label="利率曲线筛选"
                options={MARKET_DATA_CURVE_FILTER_OPTIONS.map((option) => ({ ...option }))}
                data-testid="market-data-curve-filter"
              />
              <Select
                size="small"
                value={sourceFilter}
                onChange={setSourceFilter}
                className="market-data-hero-select market-data-hero-select--source"
                aria-label="数据来源筛选"
                options={MARKET_DATA_SOURCE_FILTER_OPTIONS.map((option) => ({ ...option }))}
                data-testid="market-data-source-filter"
              />
              <button
                onClick={handleMarketDataRefresh}
                disabled={isRefreshing}
                className="market-data-hero-refresh-btn"
                data-testid="market-data-refresh-btn"
              >
                {isRefreshing ? "刷新中…" : "刷新数据"}
              </button>
            </div>
          }
        >
          {filteredTickerItems.length > 0 ? (
            <MarketTerminalTicker
              items={filteredTickerItems}
              compact
              statusDate={tickerStatusDate ?? undefined}
              statusLabel={isFormalBasis ? "正式" : "分析"}
              basisLabel={ratesBasisLabel}
            />
          ) : (
            <div
              data-testid="market-data-terminal-ticker-empty"
              className="market-data-terminal-ticker-empty"
            >
              {terminalModel.rateQuotes.emptyReason ?? "正式利率读面暂无可用序列。"}
            </div>
          )}

          <KpiBand testId="market-data-kpi-band">
            {heroKpiMetrics.map((metric) => (
              <KpiBandMetric
                key={metric.testId}
                label={metric.label}
                value={metric.value}
                footer={metric.footer}
                testId={metric.testId}
              />
            ))}
          </KpiBand>
        </PageDecisionHero>

        <div className="market-data-layout" data-testid="market-data-layout">
          <main className="market-data-main" data-testid="market-data-main">
            <MarketDataFormalRatesBoard
              model={terminalModel.rateQuotes}
              curveFilter={curveFilter}
              sourceFilter={sourceFilter}
              catalogVendorNames={catalogVendorNames}
              keyMetrics={filteredTerminalKpiMetrics}
              ratesBasisLabel={ratesBasisLabel}
              formalUseBlocked={formalUseBlocked}
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
                  flushTop
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
              {shouldRenderExtendedTerminalSection ? (
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
              ) : null}
            </div>

            <div ref={lazySupplementary.ref} data-lazy-mount="supplementary-series">
              {shouldRenderSupplementarySection &&
              (MARKET_DATA_SHOW_MACRO_SERIES_DECK || MARKET_DATA_SHOW_FX_ANALYSIS_SECTION) ? (
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
                  macroLoading={macroSeriesLoading}
                  macroError={macroSeriesError}
                  macroEmpty={macroSeriesEmpty}
                  onMacroRetry={refetchMacroSeries}
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
                                        {refreshTierLabel(marketCatalogRefreshTier(series))}
                                      </div>
                                      <DiagnosticDisclosure summary="查看数据诊断">
                                        <dl>
                                          <div>
                                            <dt>序列编号</dt>
                                            <dd>{series.series_id}</dd>
                                          </div>
                                        </dl>
                                      </DiagnosticDisclosure>
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
            </div>

            <div data-lazy-mount="livermore-section">
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
            </div>

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
        </div>
        ) : null}
      </section>
    </MarketWorkbenchFrame>
  );
}
