import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import { Collapse } from "antd";

import { nonCancellingRefetchOptions } from "../../../app/externalDataRefreshPolicy";
import { PageSectionLead, type PageSectionLeadProps } from "../../../components/page/PagePrimitives";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import type {
  ChoiceMacroRecentPoint,
  MacroBondLinkageTopCorrelation,
  ResultMeta,
} from "../../../api/contracts";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { KpiCard } from "../../../components/KpiCard";
import { toneFromSignedNumber } from "../../workbench/components/kpiFormat";
import { BondFuturesTable } from "../components/BondFuturesTable";
import { BondTradeDetail } from "../components/BondTradeDetail";
import { CreditBondTradesTable } from "../components/CreditBondTradesTable";
import { LiveResultMetaStrip } from "../components/LiveResultMetaStrip";
import { MarketDataFxFormalSection } from "../components/MarketDataFxFormalSection";
import { MarketDataLivermoreSection } from "../components/MarketDataLivermoreSection";
import { MacroLatestReadinessBanner } from "../components/MacroLatestReadinessBanner";
import { MoneyMarketTable } from "../components/MoneyMarketTable";
import { NcdMatrix } from "../components/NcdMatrix";
import { NewsAndCalendar } from "../components/NewsAndCalendar";
import { RateQuoteTable } from "../components/RateQuoteTable";
import {
  marketCatalogRefreshTier,
  marketSeriesRefreshTier,
  type MarketObservationPoint,
} from "../lib/marketDataCategoryStore";
import { formatSignedNumber } from "../lib/marketDataFormat";
import { designTokens } from "../../../theme/designSystem";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../../../utils/choiceMacroFormat";
import {
  buildCatalogVendorNameMap,
  buildMarketDataActiveFilterSummary,
  filterTerminalTickerItems,
} from "../lib/marketDataTerminalModel";
import { useMarketDataPageData } from "../hooks/useMarketDataPageData";
import { MarketTerminalSparkline } from "../components/MarketTerminalSparkline";
import { MarketDataHeroSection } from "./MarketDataHeroSection";
import { MarketDataMacroDepthTabs } from "./MarketDataMacroDepthTabs";
import { buildSpreadSlots, buildTerminalKpiMetricsFromTickerItems } from "./marketDataPageModel";
import "./MarketDataPage.css";

/** 产品默认：不显式铺开 Choice 宏观序列读面大卡与页尾目录/追踪版本证据面板（仍为分析读面保留接口拉取与市场概览 KPI）。 */
const MARKET_DATA_SHOW_MACRO_OBSERVATION_AND_CATALOG_EVIDENCE = false;

/** 外汇分析观察区块顶部元数据蓝条（本区块·外汇分析）；默认隐藏。 */
const MARKET_DATA_SHOW_FX_ANALYSIS_META_STRIP = false;

/** 默认不渲染「外汇分析观察」整块 UI（分组与序列卡）；接口仍照常拉取以供概览 KPI。 */
const MARKET_DATA_SHOW_FX_ANALYSIS_SECTION = false;

const s = designTokens.space;

const marketDataSectionLeadStyle: CSSProperties = {
  marginTop: 0,
  marginBottom: s[2],
};

function MarketSectionBlock({ children }: { children: ReactNode }) {
  return <div className="market-data-section-block">{children}</div>;
}

function MarketSectionInnerBlock({ children }: { children: ReactNode }) {
  return <div className="market-data-section-inner-block">{children}</div>;
}

function MarketSectionLead({
  flushTop: _flushTop = false,
  ...props
}: Omit<PageSectionLeadProps, "style"> & { flushTop?: boolean }) {
  return <PageSectionLead {...props} style={marketDataSectionLeadStyle} />;
}

const TARGET_FAMILY_LABELS: Record<string, string> = {
  treasury: "国债收益率",
  cdb: "国开收益率",
  aaa_credit: "AAA 信用收益率",
  credit_spread: "信用利差",
};

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
  };
  return labels[title] ?? title;
}

function fxAnalyticalGroupDescription(description: string) {
  const labels: Record<string, string> = {
    "Catalog-observed middle-rate series remain analytical views and do not redefine the formal seam.":
      "目录观察到的中间价序列保留为分析口径视图，不重定义正式口径边界。",
    "RMB index / estimate index series stay analytical-only and never flow into formal FX.":
      "人民币指数和估算指数序列保留为分析口径，不流入正式外汇读面。",
  };
  return labels[description] ?? description;
}

function familyLabel(targetFamily: string) {
  return TARGET_FAMILY_LABELS[targetFamily] ?? targetFamily;
}

function formatCorrelation(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) {
    return "不可用";
  }
  return value.toFixed(2);
}

function renderCorrelationCard(point: MacroBondLinkageTopCorrelation) {
  const dirClass =
    point.direction === "positive"
      ? "market-data-dir-pill--pos"
      : point.direction === "negative"
        ? "market-data-dir-pill--neg"
        : "market-data-dir-pill--neu";
  return (
    <div
      key={`${point.series_id}:${point.target_family}:${point.target_tenor ?? "none"}`}
      className="market-data-inset-card market-data-inset-card--surface"
    >
      <div className="market-data-corr-card-header">
        <div>
          <div className="market-data-series-title">{point.series_name}</div>
          <div className="market-data-dim-label">{point.series_id}</div>
        </div>
        <div className={`market-data-dir-pill ${dirClass}`}>{point.direction}</div>
      </div>

      <div className="market-data-body-line">
        目标维度：{familyLabel(point.target_family)}
        {point.target_tenor ? ` / ${point.target_tenor}` : " / 期限不可用"}
      </div>

      <div className="market-data-corr-grid-inner">
        <div>
          <div className="market-data-dim-label">3月相关</div>
          <div className="market-data-tabular">{formatCorrelation(point.correlation_3m)}</div>
        </div>
        <div>
          <div className="market-data-dim-label">6月相关</div>
          <div className="market-data-tabular">{formatCorrelation(point.correlation_6m)}</div>
        </div>
        <div>
          <div className="market-data-dim-label">1年相关</div>
          <div className="market-data-tabular">{formatCorrelation(point.correlation_1y)}</div>
        </div>
        <div>
          <div className="market-data-dim-label">领先/滞后</div>
          <div className="market-data-tabular">{`${point.lead_lag_days} 天`}</div>
        </div>
      </div>
    </div>
  );
}

function renderSeriesCards(
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

export default function MarketDataPage() {
  const [livermoreExpanded, setLivermoreExpanded] = useState(false);
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
  } = useMarketDataPageData({ livermoreEnabled: livermoreExpanded });
  const {
    catalog,
    visibleLatestSeries,
    stableSeries,
    fallbackSeries,
    stableCatalogSeries,
    missingStableSeries,
    linkageReportDate,
    vendorVersions,
    terminalModel,
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
  } = pageModel;
  const [curveFilter, setCurveFilter] = useState<"treasury" | "cdb" | "both">("both");
  const [creditSegment, setCreditSegment] = useState<"mtn" | "urban" | "both">("both");
  const [sourceFilter, setSourceFilter] = useState<"all" | "choice" | "internal">("all");
  const [macroDepthTab, setMacroDepthTab] = useState<"curve" | "spreads" | "linkage">("curve");
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
  const spreadSlots = useMemo(
    () => buildSpreadSlots(macroBondLinkage.top_correlations, creditSegment),
    [macroBondLinkage.top_correlations, creditSegment],
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
  useEffect(() => {
    if (creditSegment !== "both") {
      setMacroDepthTab("spreads");
    }
  }, [creditSegment]);
  const formalUseBlocked =
    formalRatesMeta?.basis === "formal" && formalRatesMeta.formal_use_allowed === false;
  const ratesBasisLabel = `${formalRatesMeta?.basis ?? rateQuotesSource?.basis ?? "unknown"}${
    formalUseBlocked ? " · blocked" : ""
  }`;
  const formalUseAllowedLabel =
    formalRatesMeta?.formal_use_allowed === undefined
      ? "unknown"
      : formalRatesMeta.formal_use_allowed
        ? "是"
        : "否";
  const sourceGateFields = [
    { label: "口径", value: ratesBasisLabel },
    { label: "正式可用", value: formalUseAllowedLabel },
    { label: "供应商", value: formalRatesMeta?.vendor_status ?? "unknown" },
    { label: "降级", value: formalRatesMeta?.fallback_mode ?? rateQuotesSource?.fallbackMode ?? "unknown" },
    { label: "Source", value: formalRatesMeta?.source_version ?? rateQuotesSource?.sourceVersion ?? "source-pending" },
  ];
  const railMetrics = filteredTerminalKpiMetrics.slice(0, 3);

  return (
    <section className="market-data-page" data-testid="market-data-page" data-layout-rev="2026-06-10e">
      <section className="market-data-terminal-cockpit" data-testid="market-data-terminal-cockpit">
        <div className="market-data-terminal-primary-grid" data-testid="market-data-terminal-primary-grid">
          <div className="market-data-terminal-primary-column">
      <MarketDataHeroSection
        clientMode={clientMode}
        watchDate={watchDate}
        onWatchDateChange={setWatchDate}
        isFormalBasis={isFormalBasis}
        catalogCount={catalog.length}
        stableCount={stableSeries.length}
        stableCatalogCount={stableCatalogSeries.length}
        terminalKpiMetrics={filteredTerminalKpiMetrics}
        pipelineOverviewMetrics={pipelineOverviewMetrics}
        terminalTickerItems={filteredTickerItems}
        terminalTickerBasisLabel={
          formalRatesMeta?.basis === "formal"
            ? `正式口径 · ${formalRatesMeta.formal_use_allowed ? "可用" : "blocked"}`
            : rateQuotesSource?.basis
              ? `口径 ${rateQuotesSource.basis}`
              : undefined
        }
        terminalTickerEmptyReason={terminalModel.rateQuotes.emptyReason}
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
      />

      {macroMeta ? (
        <div className="market-data-meta-strip">
          <LiveResultMetaStrip
            lead="市场概览·宏观读面（最新优先）"
            meta={macroMeta}
            testId="market-data-overview-live-meta"
          />
        </div>
      ) : null}

      <div className="market-data-contract-status">
        <span data-testid="market-data-readiness-verdict">
          {statusBadges.readinessVerdict}
        </span>
        <span data-testid="market-data-overview-readiness-label">
          {statusBadges.overviewReadinessLabel}
        </span>
        <span data-testid="market-data-overview-secondary-label">{statusBadges.secondaryLabel}</span>
      </div>

      <MarketSectionBlock>
        <MarketSectionLead
          eyebrow="核心观察"
          title="利率、资金、宏观深度与成交观察"
          description="左侧保留利率行情主表；右侧「宏观深度」页签聚合 V3 client 已支持的曲线（Choice）、结构化信用利差槽位与联动环境/组合影响摘要。V1 其余 `/api/macro/*` 决策类端点未暴露则不在此实现。"
        />
        <div
          id="market-data-core-workbench"
          className="market-data-command-grid"
          data-testid="market-data-macro-workbench"
        >
          <RateQuoteTable
            model={terminalModel.rateQuotes}
            curveFilter={curveFilter}
            sourceFilter={sourceFilter}
            catalogVendorNames={catalogVendorNames}
          />
          <MarketDataMacroDepthTabs
            macroDepthTab={macroDepthTab}
            onMacroDepthTabChange={setMacroDepthTab}
            latestQuery={latestQuery}
            rateTrendChartOption={rateTrendChartOption}
            macroBondLinkageQuery={macroBondLinkageQuery}
            spreadSlots={spreadSlots}
            macroBondLinkage={macroBondLinkage}
          />
        </div>
        <div className="market-data-workbench-shared-meta" data-testid="market-data-workbench-shared-meta">
          <span>口径 {ratesBasisLabel}</span>
          <span>
            正式可用{" "}
            {formalUseAllowedLabel}
          </span>
          <span>供应商 {formalRatesMeta?.vendor_status ?? "unknown"}</span>
          <span>降级 {formalRatesMeta?.fallback_mode ?? rateQuotesSource?.fallbackMode ?? "unknown"}</span>
          <span>{formalRatesMeta?.source_version ?? rateQuotesSource?.sourceVersion ?? "source-pending"}</span>
          {formalUseBlocked ? <span>禁止作为正式口径</span> : null}
        </div>
      </MarketSectionBlock>
          </div>

          <aside
            className="market-data-terminal-decision-rail"
            data-testid="market-data-terminal-decision-rail"
          >
            <div className="market-data-terminal-rail-head">
              <span>Market Data Terminal</span>
              <strong>{statusBadges.readinessVerdict}</strong>
              <small>{statusBadges.secondaryLabel}</small>
            </div>
            <div className="market-data-terminal-source-gate">
              <span className="market-data-terminal-rail-kicker">Source Gate</span>
              {sourceGateFields.map((field) => (
                <div
                  key={field.label}
                  className={`market-data-terminal-source-row ${
                    field.label === "Source" ? "market-data-terminal-source-row--source" : ""
                  }`}
                >
                  <span>{field.label}</span>
                  <strong title={field.value}>{field.value}</strong>
                </div>
              ))}
            </div>
            <div className="market-data-terminal-rail-metrics">
              {railMetrics.map((metric) => (
                <div
                  key={metric.testId}
                  className={`market-data-terminal-rail-metric market-data-terminal-rail-metric--${metric.tone ?? "default"}`}
                >
                  <div className="market-data-terminal-rail-metric-head">
                    <span>{metric.title}</span>
                    {metric.sparklineValues && metric.sparklineValues.length >= 2 ? (
                      <MarketTerminalSparkline
                        values={metric.sparklineValues}
                        tone={metric.sparklineTone}
                        variant="ticker"
                      />
                    ) : null}
                  </div>
                  <strong>{metric.value}</strong>
                  <small>{metric.detail}</small>
                </div>
              ))}
            </div>
            <nav className="market-data-terminal-anchor-nav" aria-label="市场数据终端导航">
              <a href="#market-data-core-workbench">曲线工作台</a>
              <a href="#market-data-liquidity-deck" aria-label="资金市场">资金</a>
              <a href="#market-data-evidence-gate">证据口径</a>
            </nav>
          </aside>
        </div>
      </section>

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

      <div id="market-data-liquidity-deck" className="market-data-observation-grid">
        <MoneyMarketTable
          model={terminalModel.moneyMarket}
          sourceFilter={sourceFilter}
          catalogVendorNames={catalogVendorNames}
        />
        <BondFuturesTable model={terminalModel.bondFutures} />
        <NcdMatrix
          payload={ncdFundingProxy}
          resultMeta={ncdFundingProxyQuery.data?.result_meta}
          isLoading={ncdFundingProxyQuery.isLoading}
          isError={ncdFundingProxyQuery.isError}
          showResultMeta={false}
          onRetry={() => void ncdFundingProxyQuery.refetch(nonCancellingRefetchOptions)}
        />
      </div>

      <div className="market-data-observation-grid" data-testid="market-data-source-pending-deck">
        <BondTradeDetail model={terminalModel.bondTrades} />
        <CreditBondTradesTable model={terminalModel.creditTrades} />
        <NewsAndCalendar />
      </div>
      <div className="market-data-source-pending-summary" data-testid="market-data-source-pending-summary">
        source-pending {sourcePendingCount}
        <span data-testid="market-data-source-pending-contract-note">
          · 待契约：国债期货 / 现券成交 / 信用成交（后端未暴露，前端不展示 demo）
        </span>
      </div>

      <section
        id="market-data-evidence-gate"
        className="market-data-macro-evidence-rail"
        data-testid="market-data-macro-evidence-rail"
      >
        <strong>证据与口径（只读）</strong>
        <span>{evidenceLines.formalRates}</span>
        <span>{evidenceLines.macroLatest}</span>
        <span>{evidenceLines.fxFormal}</span>
        <span>{evidenceLines.fxAnalytical}</span>
        <span>{evidenceLines.ncdProxy}</span>
        <span>{evidenceLines.livermore}</span>
        <span>{evidenceLines.linkage}</span>
      </section>

      {(MARKET_DATA_SHOW_MACRO_OBSERVATION_AND_CATALOG_EVIDENCE ||
        MARKET_DATA_SHOW_FX_ANALYSIS_SECTION) && (
      <MarketSectionBlock>
        {MARKET_DATA_SHOW_MACRO_OBSERVATION_AND_CATALOG_EVIDENCE ? (
          <>
            <MarketSectionLead
              eyebrow="观察"
              title="宏观序列与分析观察"
              description="在市场主观察之后，单独查看 Choice 宏观序列的稳定链路、缺口与外汇分析观察，避免和正式读面混用。"
            />
            <MacroLatestReadinessBanner
              testId="market-data-macro-readiness"
              isLoading={latestQuery.isLoading}
              isError={latestQuery.isError}
              hasSeries={visibleLatestSeries.length > 0}
              meta={latestQuery.data?.result_meta}
            />
            <MarketSectionInnerBlock>
              <AsyncSection
                title="宏观序列观察"
                isLoading={latestQuery.isLoading}
                isError={latestQuery.isError}
                isEmpty={
                  !latestQuery.isLoading && !latestQuery.isError && visibleLatestSeries.length === 0
                }
                onRetry={() => void latestQuery.refetch(nonCancellingRefetchOptions)}
              >
                <div className="market-data-stack-gap-6">
                  {!latestQuery.isLoading && !latestQuery.isError ? (
                    <LiveResultMetaStrip
                      lead="本区块·宏观最新"
                      meta={latestQuery.data?.result_meta}
                      testId="market-data-macro-section-meta"
                    />
                  ) : null}
                  <section data-testid="market-data-stable-section">
                    <div className="market-data-section-heading">
                      <h2>稳定主链路</h2>
                      <p>
                        面向日常分析的主刷新读面，只显示稳定可取的序列。
                      </p>
                    </div>
                    {renderSeriesCards(stableSeries)}
                  </section>

                  <section data-testid="market-data-missing-stable-section">
                    <div className="market-data-section-heading">
                      <h2>待补齐稳定链路</h2>
                      <p>
                        目录中归属稳定链路，但当前刷新尚未回收的序列。
                      </p>
                    </div>
                    {missingStableSeries.length > 0 ? (
                      <div className="market-data-stack-gap-3">
                        {missingStableSeries.map((series) => (
                          <div key={series.series_id} className="market-data-catalog-row">
                            <strong>{series.series_name}</strong>
                            <div className="market-data-catalog-meta">
                              {series.series_id} 路 {refreshTierLabel(marketCatalogRefreshTier(series))} 路{" "}
                              {seriesFetchModeLabel(series)}
                            </div>
                            <div className="market-data-catalog-note">
                              {series.policy_note ?? "主刷新日期切片链路"}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="market-data-catalog-empty">
                        当前稳定目录已全部回收。
                      </div>
                    )}
                  </section>

                  <section data-testid="market-data-fallback-section">
                    <div className="market-data-section-heading">
                      <h2>仅取最新降级</h2>
                      <p>
                        低频或稀疏序列保留为降级链路展示，不混入稳定主链路。
                      </p>
                    </div>
                    {fallbackSeries.length > 0 ? (
                      renderSeriesCards(fallbackSeries)
                    ) : (
                      <div className="market-data-catalog-empty">
                        当前无仅取最新降级序列。
                      </div>
                    )}
                  </section>
                </div>
              </AsyncSection>
            </MarketSectionInnerBlock>
          </>
        ) : null}

        {MARKET_DATA_SHOW_FX_ANALYSIS_SECTION ? (
        <MarketSectionInnerBlock>
          <AsyncSection
          title="外汇分析观察"
          isLoading={fxAnalyticalQuery.isLoading}
          isError={fxAnalyticalQuery.isError}
          isEmpty={
            !fxAnalyticalQuery.isLoading &&
            !fxAnalyticalQuery.isError &&
            fxAnalyticalGroups.length === 0
          }
          onRetry={() => void fxAnalyticalQuery.refetch(nonCancellingRefetchOptions)}
        >
          <div className="market-data-stack-gap-6">
            {!fxAnalyticalQuery.isLoading && !fxAnalyticalQuery.isError && MARKET_DATA_SHOW_FX_ANALYSIS_META_STRIP ? (
              <LiveResultMetaStrip
                lead="本区块·外汇分析"
                meta={fxAnalyticalQuery.data?.result_meta}
                testId="market-data-fx-section-meta"
              />
            ) : null}
            {fxAnalyticalGroups.map((group) => (
              <section
                key={group.group_key}
                data-testid={`market-data-fx-group-${group.group_key}`}
              >
                <div className="market-data-section-heading market-data-section-heading--relaxed">
                  <h2>{fxAnalyticalGroupTitle(group.title)}</h2>
                  <p>
                    {fxAnalyticalGroupDescription(group.description)}
                  </p>
                </div>
                {renderSeriesCards(group.series, {
                  testIdPrefix: `market-data-fx-series-${group.group_key}`,
                  hideSeriesProvenance: true,
                })}
              </section>
            ))}
          </div>
          </AsyncSection>
        </MarketSectionInnerBlock>
        ) : null}
      </MarketSectionBlock>
      )}

      <MarketSectionBlock>
        <MarketSectionLead
          eyebrow="分析口径"
          title="宏观-债市联动"
          description="联动区保留为分析口径折叠块，继续显式标注分析口径和非正式口径，不向正式结果读面越界。"
        />
        <Collapse
          data-testid="market-data-linkage-collapse"
          bordered={false}
        defaultActiveKey={[]}
        items={[
          {
            key: "macro-linkage",
            label: "宏观-债市联动（分析口径，点击展开）",
            children: (
              <AsyncSection
                title="宏观-债市联动"
                isLoading={macroBondLinkageQuery.isLoading}
                isError={macroBondLinkageQuery.isError}
                isEmpty={
                  !macroBondLinkageQuery.isLoading &&
                  !macroBondLinkageQuery.isError &&
                  (macroBondLinkage.top_correlations?.length ?? 0) === 0 &&
                  macroBondLinkageWarnings.length === 0
                }
                onRetry={() => void macroBondLinkageQuery.refetch(nonCancellingRefetchOptions)}
              >
                <div className="market-data-stack-gap-5">
            <section data-testid="market-data-linkage-caveat" className="market-data-linkage-caveat">
              <div className="market-data-linkage-caveat-tags">
                <span className="market-data-pill-tag market-data-pill-tag--info">分析口径</span>
                <span className="market-data-pill-tag market-data-pill-tag--warn">非正式口径</span>
              </div>
              <div className="market-data-linkage-caveat-body">
                本区为宏观联动分析口径。组合影响仅用于研究和配置讨论，属于分析估算，不代表账本口径下的损益（PnL）、
                不代表正式估值归因，也不替代债券分析的正式读面。
              </div>
              {macroBondLinkageWarnings.length > 0 ? (
                <ul data-testid="market-data-linkage-warning-list" className="market-data-linkage-warning-list">
                  {macroBondLinkageWarnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              ) : (
                <div className="market-data-linkage-warning-empty" data-testid="market-data-linkage-warning-empty">
                  当前无额外方法警示。
                </div>
              )}
            </section>

            <div className="market-data-summary-grid">
              <div data-testid="market-data-linkage-composite-score">
                <KpiCard
                  title="综合评分"
                  value={
                    macroBondLinkage.environment_score?.composite_score != null
                      ? String(macroBondLinkage.environment_score.composite_score.toFixed(2))
                      : "不可用"
                  }
                  detail={macroBondLinkage.environment_score?.signal_description ?? "缺少环境评分数据。"}
                  valueVariant="text"
                  tone={toneFromSignedNumber(
                    macroBondLinkage.environment_score?.composite_score != null
                      ? macroBondLinkage.environment_score.composite_score
                      : null,
                  )}
                />
              </div>
              <div data-testid="market-data-linkage-rate-direction">
                <KpiCard
                  title="利率方向"
                  value={macroBondLinkage.environment_score?.rate_direction ?? "不可用"}
                  detail={
                    macroBondLinkage.environment_score?.rate_direction_score != null
                      ? `direction score ${macroBondLinkage.environment_score.rate_direction_score.toFixed(2)}`
                      : "缺少方向评分。"
                  }
                  valueVariant="text"
                  tone={toneFromSignedNumber(
                    macroBondLinkage.environment_score?.rate_direction_score != null
                      ? macroBondLinkage.environment_score.rate_direction_score
                      : null,
                  )}
                />
              </div>
              <div data-testid="market-data-linkage-liquidity-score">
                <KpiCard
                  title="流动性评分"
                  value={
                    macroBondLinkage.environment_score?.liquidity_score != null
                      ? macroBondLinkage.environment_score.liquidity_score.toFixed(2)
                      : "不可用"
                  }
                  detail="正值偏松，负值偏紧。"
                  valueVariant="text"
                  tone={toneFromSignedNumber(
                    macroBondLinkage.environment_score?.liquidity_score != null
                      ? macroBondLinkage.environment_score.liquidity_score
                      : null,
                  )}
                />
              </div>
              <div data-testid="market-data-linkage-growth-score">
                <KpiCard
                  title="增长评分"
                  value={
                    macroBondLinkage.environment_score?.growth_score != null
                      ? macroBondLinkage.environment_score.growth_score.toFixed(2)
                      : "不可用"
                  }
                  detail="宏观增长方向的简化分值。"
                  valueVariant="text"
                  tone={toneFromSignedNumber(
                    macroBondLinkage.environment_score?.growth_score != null
                      ? macroBondLinkage.environment_score.growth_score
                      : null,
                  )}
                />
              </div>
            </div>

            <section data-testid="market-data-linkage-portfolio-impact" className="market-data-detail-panel">
              <h2 className="market-data-linkage-panel-title">组合影响估算</h2>
              <p className="market-data-linkage-panel-lede">
                以下数值为分析口径估算，基于宏观环境评分与组合在利率、利差维度上的敏感度静态映射，不代表正式损益。
              </p>
              {hasPortfolioImpact ? (
                <div className="market-data-portfolio-grid">
                  <div>
                    <div className="market-data-dim-label">利率变动</div>
                    <div className="market-data-tabular">
                      {formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_rate_change_bps, " bp")}
                    </div>
                  </div>
                  <div>
                    <div className="market-data-dim-label">利差走阔</div>
                    <div className="market-data-tabular">
                      {formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_spread_widening_bps, " bp")}
                    </div>
                  </div>
                  <div>
                    <div className="market-data-dim-label">利率影响</div>
                    <div className="market-data-tabular">{formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_rate_pnl_impact)}</div>
                  </div>
                  <div>
                    <div className="market-data-dim-label">利差影响</div>
                    <div className="market-data-tabular">{formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_spread_pnl_impact)}</div>
                  </div>
                  <div>
                    <div className="market-data-dim-label">合计估算</div>
                    <div className="market-data-tabular">{formatSignedNumber(macroBondLinkage.portfolio_impact?.total_estimated_impact)}</div>
                  </div>
                  <div>
                    <div className="market-data-dim-label">影响占比</div>
                    <div className="market-data-tabular">{macroBondLinkage.portfolio_impact?.impact_ratio_to_market_value ?? "不可用"}</div>
                  </div>
                </div>
              ) : (
                <div
                  data-testid="market-data-linkage-portfolio-impact-unavailable"
                  className="market-data-portfolio-empty"
                >
                  当前报告日未返回组合影响估算，状态按不可用处理，不在前端补零。
                </div>
              )}
            </section>

            <section data-testid="market-data-linkage-spread-tenors" className="market-data-detail-panel">
              <h2 className="market-data-linkage-panel-title">信用利差显式维度</h2>
              <p className="market-data-linkage-panel-lede">
                仅按结构化字段渲染，不从标签或目标收益率反推期限。
              </p>
              <div className="market-data-spread-slot-grid">
                {spreadSlots.map(({ tenor, point }) => (
                  <div
                    key={tenor}
                    data-testid={`market-data-linkage-spread-slot-${tenor}`}
                    className="market-data-spread-slot"
                  >
                    <div className="market-data-slot-title">{`信用利差 ${tenor}`}</div>
                    {point ? (
                      <>
                        <div className="market-data-muted-body">{point.series_name}</div>
                        <div className="market-data-tabular">{`1年相关 ${formatCorrelation(point.correlation_1y)}`}</div>
                        <div className="market-data-tabular">{`领先/滞后 ${point.lead_lag_days} 天`}</div>
                      </>
                    ) : (
                      <div className="market-data-muted-body">
                        不可用：当前载荷未返回该期限的结构化相关性，不在前端推断。
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>

            <section data-testid="market-data-linkage-top-correlations" className="market-data-detail-panel">
              <h2 className="market-data-linkage-panel-title">相关性前十</h2>
              {(nonSpreadTopCorrelations.length > 0 ||
                spreadSlots.some((slot) => slot.point !== null)) ? (
                <div className="market-data-stack-gap-3">
                  {(macroBondLinkage.top_correlations ?? []).map((point) =>
                    renderCorrelationCard(point),
                  )}
                </div>
              ) : (
                <div className="market-data-corr-empty">当前无可展示的结构化相关性结果。</div>
              )}
            </section>
                </div>
              </AsyncSection>
            ),
          },
        ]}
      />
      </MarketSectionBlock>

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
  );
}
