import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Collapse, DatePicker, Select } from "antd";
import dayjs from "dayjs";
import { flushSync } from "react-dom";
import {
  DataQualityPill,
  DiagnosticDisclosure,
} from "../../../components/StatusPill";
import { nonCancellingRefetchOptions } from "../../../app/externalDataRefreshPolicy";
import { KpiStrip, SectionHead } from "../../../components/layout";
import {
  DataStatusStrip,
  PageDecisionHero,
} from "../../../components/page/PagePrimitives";
import { EM_DASH } from "../../../utils/format";
import type {
  ApiEnvelope,
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
  ExternalDataWatermarkLedger,
  FxAnalyticalPayload,
  MarketDataCoverageSection,
  MarketDataCoverageSummaryPayload,
  ResultMeta,
} from "../../../api/contracts";
import { BondFuturesTable } from "../components/BondFuturesTable";
import { BondTradeDetail } from "../components/BondTradeDetail";
import { CreditBondTradesTable } from "../components/CreditBondTradesTable";
import { MacroLatestReadinessBanner } from "../components/MacroLatestReadinessBanner";
import { ChartCard } from "../../../components/charts/ChartCard";
import { MARKET_DATA_CHART_ERROR } from "../lib/charts/marketDataChartMessages";
import { MarketDataExtendedTerminalSection } from "../components/MarketDataExtendedTerminalSection";
import { MarketDataFxFormalSection } from "../components/MarketDataFxFormalSection";
import { MarketDataLiquidityDeck } from "../components/MarketDataLiquidityDeck";
import { MarketDataNewsCalendarSummary } from "../components/MarketDataNewsCalendarSummary";
import {
  CROSS_ASSET_LINKAGE_PATH,
  MarketDataLinkageSummaryCard,
} from "../components/MarketDataLinkageSummaryCard";
import { MoneyMarketTable } from "../components/MoneyMarketTable";
import { NcdMatrix } from "../components/NcdMatrix";
import { MarketDataTushareSupplementSection } from "../components/MarketDataTushareSupplementSection";
import { MarketDataTermStructureChart } from "../components/MarketDataTermStructureChart";
import { formatGeneratedAtLocal } from "../lib/marketDataFormat";
import {
  buildCatalogVendorNameMap,
  filterRateQuoteRows,
  filterTerminalTickerItems,
  type MarketDataRateQuoteSection,
} from "../lib/marketDataTerminalModel";
import { useMarketDataPageData } from "../hooks/useMarketDataPageData";
import type { MarketDataEvidenceLines, MarketOverviewMetric } from "./marketDataPageModel";
import { buildMarketDataBasisChipLabel, buildTerminalKpiMetricsFromTickerItems, formatMarketWorkbenchSourceSummary } from "./marketDataPageModel";
import type { EChartsOption } from "../../../lib/echarts";
import { useLazyMount } from "../lib/useLazyMount";
import { MarketWorkbenchFrame } from "../../workbench/market-shell";
import "./MarketDataPage.css";

/** 序列浏览器（?view=explorer）独立分包：宏观/外汇主题读面不进驾驶舱首包。 */
const MarketDataExplorerView = lazy(() => import("./MarketDataExplorerView"));

function fxAnalyticalObservationCount(groups: FxAnalyticalPayload["groups"]): number {
  return groups.reduce((total, group) => total + group.series.length + (group.events?.length ?? 0), 0);
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
  return normalized || EM_DASH;
}

function marketDataSourceLabel(value: string | null | undefined): string {
  if (!value || value === "unknown") return "待确认";
  if (value === "source-pending" || value === "source_pending") return "未接入";
  return value;
}

function marketDataEvidenceLineLabel(line: string): string {
  const labels: Record<string, string> = {
    "formal rates": "正式利率",
    "macro latest": "宏观最新",
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
  if (section.status === "error") return "检查数据链路";
  if (section.status === "stale") return "复核数据延迟";
  if (section.source_pending) return "接入数据源";
  if (section.proxy_only) return "确认正式口径";
  if (section.status === "deferred") return "按需展开";
  if (section.fallback_mode !== "none") return "查看数据延迟";
  return "查看详情";
}


function coverageFallbackMode(value: ResultMeta["fallback_mode"] | undefined): "none" | "latest_snapshot" {
  return value === "latest_snapshot" ? "latest_snapshot" : "none";
}

function weekChangeBpText(sparklineValues: readonly number[]): string {
  if (sparklineValues.length < 6) {
    return EM_DASH;
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

type MarketDataRailStatusCounts = {
  formalCount: number;
  analyticalCount: number;
  proxyCount: number;
  sourcePendingCount: number;
  staleCount: number;
  errorCount: number;
};

function computeRailStatusCounts(
  summary: MarketDataCoverageSummaryPayload | null,
  sections: MarketDataCoverageSection[],
): MarketDataRailStatusCounts {
  return {
    formalCount: countCoverageSections(
      sections,
      (section) => section.basis === "formal" && section.formal_use_allowed,
    ),
    analyticalCount: countCoverageSections(
      sections,
      (section) => section.basis === "analytical" && !section.proxy_only && !section.source_pending,
    ),
    proxyCount:
      summary?.headline.proxy_only_count ??
      countCoverageSections(sections, (section) => section.proxy_only || section.status === "proxy_only"),
    sourcePendingCount:
      summary?.headline.source_pending_count ??
      countCoverageSections(sections, (section) => section.source_pending || section.status === "source_pending"),
    staleCount: countCoverageSections(sections, (section) => section.status === "stale"),
    errorCount: countCoverageSections(sections, (section) => section.status === "error"),
  };
}

/** 收起态入口条文案：延迟/不可用计数必须显式可见（stale/fallback 显式披露要求）。 */
function buildRailEntrySummary(counts: MarketDataRailStatusCounts): string {
  const parts = [
    `正式 ${counts.formalCount}`,
    `代理 ${counts.proxyCount}`,
    `未接入 ${counts.sourcePendingCount}`,
  ];
  if (counts.staleCount > 0) {
    parts.push(`延迟 ${counts.staleCount}`);
  }
  if (counts.errorCount > 0) {
    parts.push(`不可用 ${counts.errorCount}`);
  }
  return `数据状态：${parts.join(" · ")}`;
}

/** “线路状态”组的九条链路（方案 §5）：业务标签 + 状态 + 最新日期，必要时展开诊断。 */
const MARKET_DATA_RAIL_LINE_SPECS = [
  { key: "formal_rates", label: "正式利率" },
  { key: "money_market", label: "资金市场" },
  { key: "fx_formal", label: "外汇正式" },
  { key: "macro_latest", label: "宏观最新" },
  { key: "fx_analytical", label: "外汇分析" },
  { key: "ncd_proxy", label: "存单代理" },
  { key: "bond_futures", label: "国债期货" },
  { key: "cash_bond_trades", label: "现券成交" },
  { key: "credit_trades", label: "信用成交" },
] as const;

type MarketDataRailLineLayer = "l0" | "l1" | "l2";

type MarketDataRailLineRow = {
  key: string;
  label: string;
  status: MarketDataCoverageSection["status"];
  latestDate: string;
  layer: MarketDataRailLineLayer;
  diagnostic: {
    basisLabel: string;
    formalUseLabel: string;
    message: string;
  } | null;
};

/** 治理分层（方案 §5 矩阵）：L2=运行时异常（stale/error），L1=结构性（代理/未接入/按需），其余 L0。 */
function railLineLayer(
  section: Pick<MarketDataCoverageSection, "status" | "source_pending" | "proxy_only">,
): MarketDataRailLineLayer {
  if (section.status === "stale" || section.status === "error") return "l2";
  if (
    section.source_pending ||
    section.proxy_only ||
    section.status === "source_pending" ||
    section.status === "proxy_only" ||
    section.status === "deferred"
  ) {
    return "l1";
  }
  return "l0";
}

function buildRailLineRow(label: string, section: MarketDataCoverageSection): MarketDataRailLineRow {
  const layer = railLineLayer(section);
  return {
    key: section.key,
    label,
    status: section.status,
    latestDate: section.latest_trade_date ?? section.as_of_date ?? EM_DASH,
    layer,
    diagnostic:
      layer !== "l0" || section.status !== "ready"
        ? {
            basisLabel: marketDataBasisLabel(section.basis),
            formalUseLabel: section.formal_use_allowed ? "是" : "否",
            message: section.message,
          }
        : null,
  };
}

function MarketDataSupplyEvidenceRail({
  summary,
  sections,
  watchDate,
  lineRows,
  sourcePendingLabels,
  evidenceLines,
  basisLabel,
  formalUseAllowedLabel,
  refreshStatus,
  refreshError,
  isRefreshing,
}: {
  summary: MarketDataCoverageSummaryPayload | null;
  sections: MarketDataCoverageSection[];
  watchDate: string;
  lineRows: MarketDataRailLineRow[];
  sourcePendingLabels: string;
  evidenceLines: MarketDataEvidenceLines;
  basisLabel: string;
  formalUseAllowedLabel: string;
  refreshStatus: string;
  refreshError: string;
  isRefreshing: boolean;
}) {
  const { formalCount, analyticalCount, proxyCount, sourcePendingCount, staleCount, errorCount } =
    computeRailStatusCounts(summary, sections);
  // L2 运行时异常置顶为“下一步动作”；结构性（代理/未接入）归 L1 灰列，不再进入该清单。
  const nextActions = sections
    .filter((section) => section.status === "stale" || section.status === "error")
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
      {nextActions.length > 0 ? (
        <section className="market-data-supply-panel" data-testid="market-data-rail-next-actions">
          <header className="market-data-panel-head">
            <span>运行时异常</span>
            <strong>下一步动作</strong>
          </header>
          <ol className="market-data-next-action-list">
            {nextActions.map((section) => (
              <li key={section.key}>
                <span>
                  {coverageActionLabel(section)}：{section.label}
                </span>
                <DataQualityPill raw={section.status} label={coverageStatusLabel(section.status)} />
              </li>
            ))}
          </ol>
        </section>
      ) : null}
      <section className="market-data-supply-panel" data-testid="market-data-rail-group-line-status">
        <header className="market-data-panel-head">
          <span>供给与未接入清单</span>
          <strong>线路状态</strong>
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
            <small data-testid="market-data-rail-source-pending-summary">
              {sourcePendingLabels || "无未接入契约"}
            </small>
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
        <ul className="market-data-rail-line-list" data-testid="market-data-rail-line-list">
          {lineRows.map((row) => (
            <li key={row.key} data-layer={row.layer} data-testid={`market-data-rail-line-${row.key}`}>
              <span>{row.label}</span>
              <DataQualityPill raw={row.status} label={coverageStatusLabel(row.status)} />
              <em>{row.latestDate}</em>
              {row.diagnostic ? (
                <DiagnosticDisclosure summary="查看诊断">
                  <dl>
                    <div>
                      <dt>口径</dt>
                      <dd>{row.diagnostic.basisLabel}</dd>
                    </div>
                    <div>
                      <dt>允许正式使用</dt>
                      <dd>{row.diagnostic.formalUseLabel}</dd>
                    </div>
                    <div>
                      <dt>说明</dt>
                      <dd>{row.diagnostic.message}</dd>
                    </div>
                  </dl>
                </DiagnosticDisclosure>
              ) : null}
            </li>
          ))}
        </ul>
      </section>
      <section className="market-data-supply-panel" data-testid="market-data-rail-group-evidence">
        <header className="market-data-panel-head">
          <span>口径与时间语义</span>
          <strong>口径证据</strong>
        </header>
        <div className="market-data-supply-meta">
          <div>
            <span>口径</span>
            <strong>{basisLabel}</strong>
          </div>
          <div>
            <span>允许正式使用</span>
            <strong>{formalUseAllowedLabel}</strong>
          </div>
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
            <strong title={summary?.generated_at ? `原始时间戳（UTC）${summary.generated_at}` : undefined}>
              {formatGeneratedAtLocal(summary?.generated_at)}
            </strong>
          </div>
        </div>
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
        <p className="market-data-supply-note">
          提示：本页为混合来源；正式使用以“允许正式使用”且“质量正常”的数据区块为准。
        </p>
      </section>
      <section className="market-data-supply-panel" data-testid="market-data-rail-group-ops">
        <header className="market-data-panel-head">
          <span>Choice 刷新链路</span>
          <strong>数据运维</strong>
        </header>
        <div className="market-data-supply-meta">
          <div>
            <span>刷新范围</span>
            <strong>Choice 宏观 · 回填 30 天</strong>
          </div>
          <div>
            <span>最近刷新</span>
            <strong>{isRefreshing && !refreshStatus ? "刷新中…" : refreshStatus || EM_DASH}</strong>
          </div>
          {refreshError ? (
            <div data-tone="error">
              <span>刷新错误</span>
              <strong>{refreshError}</strong>
            </div>
          ) : null}
        </div>
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
  rateTrendChartOption,
  latestQuery,
  latestSeries,
  watermarksQuery,
}: {
  model: MarketDataRateQuoteSection;
  curveFilter: "treasury" | "cdb" | "both";
  sourceFilter: "all" | "choice" | "internal";
  catalogVendorNames: ReadonlyMap<string, string>;
  keyMetrics: readonly MarketOverviewMetric[];
  ratesBasisLabel: string;
  formalUseBlocked: boolean;
  rateTrendChartOption: EChartsOption | null;
  latestQuery: UseQueryResult<ApiEnvelope<ChoiceMacroLatestPayload>, Error>;
  latestSeries: readonly ChoiceMacroLatestPoint[];
  watermarksQuery: UseQueryResult<ExternalDataWatermarkLedger, Error>;
}) {
  const rows = filterRateQuoteRows(model.rows, curveFilter, sourceFilter, catalogVendorNames).slice(0, 8);
  const hasRows = model.status === "ready" && rows.length > 0;
  const latestSeriesIds = latestSeries.map((point) => point.series_id);
  return (
    <section
      id="market-data-term-structure"
      className="market-data-formal-rates-board"
      data-testid="market-data-formal-rates-board"
      aria-labelledby="market-data-formal-rates-title"
    >
      <div className="market-data-section-head-shell">
        <SectionHead
          category="利率行情"
          title="01 正式利率"
          note="利率曲线与宏观深度"
          actions={<a href="#market-data-evidence-gate">查看完整曲线</a>}
          numbered={false}
          contentGap="flush"
          titleId="market-data-formal-rates-title"
          testId="market-data-formal-rates-head"
        />
      </div>
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
        <section
          className="market-data-formal-rate-panel market-data-formal-rate-panel--quote"
          data-testid="market-data-rate-quote-table"
        >
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
        <section
          className="market-data-formal-rate-panel market-data-formal-rate-panel--curve"
          data-testid="market-data-formal-rates-curve"
        >
          <MarketDataTermStructureChart
            model={model}
            curveFilter={curveFilter}
            sourceFilter={sourceFilter}
            catalogVendorNames={catalogVendorNames}
            activeCurve={curveFilter}
            height={220}
          />
        </section>
        <section
          className="market-data-formal-rate-panel market-data-formal-rate-panel--key"
          data-testid="market-data-key-rate-list"
        >
          <header>
            <strong>关键利率 / 资金指标</strong>
            <span>最新</span>
          </header>
          <div className="market-data-key-rate-list">
            {keyMetrics.length > 0 ? (
              keyMetrics.slice(0, 7).map((metric) => (
                <article key={metric.testId} data-testid={`market-data-key-rate-${metric.testId}`}>
                  <span>{metric.title}</span>
                  <em>{metric.detail.split(" · ")[0]}</em>
                  <strong>{metric.value}</strong>
                </article>
              ))
            ) : (
              <p className="market-data-key-rate-list__empty" data-testid="market-data-key-rate-empty">
                关键利率序列已全部展示于首屏 KPI 带，无额外序列。
              </p>
            )}
          </div>
        </section>
        {/* 原 02 区曲线 Tab 的走势能力并入 01 区次行；macro latest 为分析口径，与正式片段显式分标。 */}
        <section
          className="market-data-formal-rate-panel market-data-formal-rate-panel--trend"
          data-testid="market-data-rate-trend-panel"
        >
          <MacroLatestReadinessBanner
            testId="market-data-macro-readiness"
            isLoading={latestQuery.isLoading}
            isError={latestQuery.isError}
            hasSeries={latestSeries.length > 0}
            meta={latestQuery.data?.result_meta}
            watermarkLedger={watermarksQuery.data}
            watermarkIsLoading={watermarksQuery.isLoading}
            watermarkIsError={watermarksQuery.isError}
            seriesIds={latestSeriesIds}
          />
          <ChartCard
            flat
            title="收益率走势"
            question="近 30 日 · 分析口径"
            unit="%"
            option={rateTrendChartOption}
            height={220}
            legendRows={2}
            state={latestQuery.isLoading ? "loading" : latestQuery.isError ? "error" : undefined}
            errorMessage={MARKET_DATA_CHART_ERROR}
            onRetry={() => void latestQuery.refetch()}
            testId="market-data-rate-trend-chart"
            emptyMessage="当前响应中缺少上述利率序列的近期点位，无法绘制走势图。"
          />
        </section>
      </div>
    </section>
  );
}

/** Livermore 读面已迁 /cross-asset（方案裁决 #9）：本卡为纯导航证据卡，不挂任何策略查询。 */
function MarketDataStrategyEvidenceCard() {
  return (
    <section
      className="market-data-summary-nav-card"
      data-testid="market-data-strategy-evidence-card"
      aria-label="Livermore 策略读面入口"
    >
      <div className="market-data-summary-nav-card__row">
        <span className="market-data-summary-nav-card__title">
          Livermore 趋势门控
          <span className="market-data-summary-nav-card__badge">分析口径</span>
        </span>
        <span className="market-data-summary-nav-card__metric">
          策略读面已迁移，本页不再加载策略数据
        </span>
        <Link
          className="market-data-summary-nav-card__link"
          to={CROSS_ASSET_LINKAGE_PATH}
          data-testid="market-data-strategy-evidence-link"
        >
          完整策略面见跨资产驱动页 →
        </Link>
      </div>
    </section>
  );
}

export default function MarketDataPage() {
  // 右栏治理元数据默认收起为"数据状态"入口条；details 内容常驻 DOM，保证契约 testid 折叠后仍可及。
  const [railExpanded, setRailExpanded] = useState(false);
  const [deferredWorkspacesRequested, setDeferredWorkspacesRequested] = useState(false);
  const navigate = useNavigate();
  // 序列浏览器子视图由 URL query 驱动（?view=explorer）：可书签、可前进后退。
  const [searchParams, setSearchParams] = useSearchParams();
  const seriesExplorerActive = searchParams.get("view") === "explorer";
  const setSearchParamsRef = useRef(setSearchParams);
  useEffect(() => {
    setSearchParamsRef.current = setSearchParams;
  });
  const openSeriesExplorer = useCallback((options?: { replace?: boolean }) => {
    setSearchParamsRef.current(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("view", "explorer");
        return next;
      },
      { replace: options?.replace ?? false },
    );
  }, []);
  const lazyExtended = useLazyMount({ rootMargin: "300px", fallbackDelayMs: 0 });
  // 联动摘要卡近视口才发 macro-bond-linkage 请求；较长的 fallback 只兜底无 IntersectionObserver 环境。
  const lazyLinkage = useLazyMount({ rootMargin: "400px", fallbackDelayMs: 8000 });
  const [viewMode] = useState<"default" | "compact">("default");
  const [curveFilter, setCurveFilter] = useState<"treasury" | "cdb" | "both">("both");
  const [sourceFilter, setSourceFilter] = useState<"all" | "choice" | "internal">("all");
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
    macroBondLinkageQuery,
    ncdFundingProxy,
  } = useMarketDataPageData({
    // 联动摘要卡近视口才拉 macro-bond-linkage；Livermore 读面已迁 /cross-asset，本页不再拉取策略数据。
    linkageEnabled: lazyLinkage.shouldMount,
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
    macroBondLinkage,
    macroBondLinkageWarnings,
    hasPortfolioImpact,
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
  const ncdFundingProxyMeta = ncdFundingProxyQuery.data?.result_meta;
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
  const filteredTerminalKpiMetrics = useMemo(
    () => buildTerminalKpiMetricsFromTickerItems(filteredTickerItems),
    [filteredTickerItems],
  );
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
  const railStatusCounts = useMemo(
    () => computeRailStatusCounts(coverageSummary, displayedCoverageSections),
    [coverageSummary, displayedCoverageSections],
  );
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
  const railLineRows = useMemo<MarketDataRailLineRow[]>(() => {
    const sectionsByKey = new Map(displayedCoverageSections.map((section) => [section.key, section]));
    return MARKET_DATA_RAIL_LINE_SPECS.map((spec): MarketDataRailLineRow => {
      const section = sectionsByKey.get(spec.key);
      if (section) {
        return buildRailLineRow(spec.label, section);
      }
      if (spec.key === "money_market") {
        // 资金市场无独立覆盖摘要节，由终端模型本地推导。
        const moneyMarket = terminalModel.moneyMarket;
        const latestDate = moneyMarket.rows.reduce<string | null>(
          (max, row) => (max && max >= row.tradeDate ? max : row.tradeDate),
          null,
        );
        const hasRows = moneyMarket.rows.length > 0;
        return {
          key: spec.key,
          label: spec.label,
          status: hasRows ? "ready" : "empty",
          latestDate: latestDate ?? EM_DASH,
          layer: "l0",
          diagnostic: hasRows
            ? null
            : {
                basisLabel: marketDataBasisLabel(moneyMarket.source?.basis),
                formalUseLabel: "否",
                message: moneyMarket.emptyReason,
              },
        };
      }
      if (spec.key === "fx_formal") {
        // 覆盖摘要缺席时由正式外汇状态载荷本地推导。
        const payload = pageModel.fxFormalStatus;
        const meta = pageModel.fxFormalMeta;
        const status: MarketDataCoverageSection["status"] = !payload
          ? "empty"
          : meta?.quality_flag === "stale"
            ? "stale"
            : meta?.quality_flag === "error"
              ? "error"
              : payload.materialized_count > 0
                ? "ready"
                : "empty";
        const layer = railLineLayer({ status, source_pending: false, proxy_only: false });
        return {
          key: spec.key,
          label: spec.label,
          status,
          latestDate: payload?.latest_trade_date ?? EM_DASH,
          layer,
          diagnostic:
            layer !== "l0" || status !== "ready"
              ? {
                  basisLabel: marketDataBasisLabel(meta?.basis),
                  formalUseLabel: meta?.formal_use_allowed ? "是" : "否",
                  message: payload
                    ? `正式外汇中间价已落地 ${payload.materialized_count}/${payload.candidate_count}。`
                    : "正式外汇状态待返回。",
                }
              : null,
        };
      }
      return {
        key: spec.key,
        label: spec.label,
        status: "deferred",
        latestDate: EM_DASH,
        layer: "l1",
        diagnostic: {
          basisLabel: "待确认",
          formalUseLabel: "否",
          message: "覆盖摘要未返回该链路状态。",
        },
      };
    });
  }, [
    displayedCoverageSections,
    pageModel.fxFormalMeta,
    pageModel.fxFormalStatus,
    terminalModel.moneyMarket,
  ]);
  // 刷新只覆盖本页仍在挂载的查询：Livermore 六件套与 Tushare/宏观工具暖查询已随读面退役，
  // 不再由本页 refetch（Tushare 折叠区自行拉数，策略读面由 /cross-asset 负责）。
  const handleMarketDataRefresh = handleRefresh;

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
        // 旧锚点兼容：联动明细读面已由 /cross-asset 承接（方案裁决 #10）。
        navigate(CROSS_ASSET_LINKAGE_PATH, { replace: true });
        return;
      }
      if (hash === "market-data-macro-series") {
        // 旧锚点兼容：04 区已迁入序列浏览器，以 replace 语义直接打开 ?view=explorer，不再滚动主列。
        openSeriesExplorer({ replace: true });
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
  }, [navigate, openSeriesExplorer]);

  const heroUsesTerminalMetrics = filteredTerminalKpiMetrics.length >= 4;
  const heroKpiCells = useMemo(() => {
    const metrics = heroUsesTerminalMetrics ? filteredTerminalKpiMetrics : pipelineOverviewMetrics;
    return metrics.slice(0, 4).map((metric) => ({
      key: metric.testId.replace(/^market-data-/, ""),
      label: metric.title,
      value: metric.value,
      note: metric.detail,
      noteTitle: metric.detailTitle,
    }));
  }, [heroUsesTerminalMetrics, filteredTerminalKpiMetrics, pipelineOverviewMetrics]);
  // 关键利率卡只列 KPI 带未含的序列（§6 去重）；KPI 带走管线回退时保留全部序列。
  const keyRateSupplementMetrics = useMemo(
    () => (heroUsesTerminalMetrics ? filteredTerminalKpiMetrics.slice(4) : filteredTerminalKpiMetrics),
    [heroUsesTerminalMetrics, filteredTerminalKpiMetrics],
  );

  return (
    <MarketWorkbenchFrame
      pageKey="market-data"
      title="市场数据"
      question="当前市场利率、资金面、外汇状况如何？"
      status={marketWorkbenchStatus}
      metaItems={marketWorkbenchMetaItems}
      navDensity="compact"
      themeScope="market-data"
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
        data-layout-rev="2026-07-01-redesign"
        data-view-mode={viewMode}
      >
        <PageDecisionHero
          title="市场数据"
          businessQuestion="当前市场利率、资金面、外汇状况如何？"
          eyebrow="市场数据终端"
          className="market-data-page__decision-hero-shell"
          testId="market-data-hero"
          actions={
            <div className="market-data-hero-actions">
              <span className="market-data-hero-date-note" data-testid="market-data-hero-date-note">
                {tickerStatusDate ? `数据日期 ${tickerStatusDate}` : ""}
              </span>
              <DatePicker
                value={watchDate ? dayjs(watchDate) : null}
                onChange={(date) => setWatchDate(date ? date.format("YYYY-MM-DD") : "")}
                format="YYYY-MM-DD"
                allowClear={false}
                className="market-data-hero-date-input"
                data-testid="market-data-date-picker"
                aria-label="市场数据观察日期"
                getPopupContainer={(trigger) => trigger.parentElement ?? document.body}
              />
              <Select
                value={curveFilter}
                onChange={setCurveFilter}
                className="market-data-hero-select market-data-hero-select--curve"
                aria-label="利率曲线筛选"
                getPopupContainer={(trigger) => trigger.parentElement ?? document.body}
                options={[
                  { value: "both", label: "国债+国开" },
                  { value: "treasury", label: "国债" },
                  { value: "cdb", label: "国开" },
                ]}
                data-testid="market-data-curve-filter"
              />
              <Select
                value={sourceFilter}
                onChange={setSourceFilter}
                className="market-data-hero-select market-data-hero-select--source"
                aria-label="数据来源筛选"
                getPopupContainer={(trigger) => trigger.parentElement ?? document.body}
                options={[
                  { value: "all", label: "全部来源" },
                  { value: "choice", label: "Choice" },
                  { value: "internal", label: "内部" },
                ]}
                data-testid="market-data-source-filter"
              />
              <button
                onClick={handleMarketDataRefresh}
                disabled={isRefreshing}
                className="market-data-hero-refresh-btn"
                data-testid="market-data-refresh-btn"
                aria-label="刷新 Choice 宏观（回填 30 天）"
              >
                {isRefreshing ? "刷新中…" : "刷新 Choice 宏观（回填 30 天）"}
              </button>
            </div>
          }
        >
          <DataStatusStrip className="market-data-hero-status" testId="market-data-status-strip">
            <span>{statusBadges.readinessVerdict}</span>
            {statusBadges.overviewReadinessLabel !== statusBadges.readinessVerdict ? (
              <>
                <span aria-hidden="true">·</span>
                <span>{statusBadges.overviewReadinessLabel}</span>
              </>
            ) : null}
            {formalUseBlocked ? (
              <>
                <span aria-hidden="true">·</span>
                <span className="market-data-hero-status-warn">{basisChipLabel}</span>
              </>
            ) : null}
            {refreshStatus ? (
              <>
                <span aria-hidden="true">·</span>
                <span className="market-data-hero-status-accent">{refreshStatus}</span>
              </>
            ) : null}
            {refreshError ? (
              <>
                <span aria-hidden="true">·</span>
                <span className="market-data-hero-status-danger">{refreshError}</span>
              </>
            ) : null}
          </DataStatusStrip>

          {/* 快捷行情 chips 与 KPI 带/正式利率表同源同值，按 §6 状态去重删除；空态由 KPI 带与 01 区表格各自披露。 */}
          {filteredTickerItems.length === 0 ? (
            <div
              data-testid="market-data-terminal-ticker-empty"
              className="market-data-terminal-ticker-empty"
            >
              {terminalModel.rateQuotes.emptyReason ?? "正式利率读面暂无可用序列。"}
            </div>
          ) : null}

          <KpiStrip
            className="market-data-hero-kpi-strip"
            testId="market-data-kpi-band"
            cellTestIdPrefix="market-data"
            cells={heroKpiCells}
            cols={{ base: 2, md: 4, lg: 4, xl: 4 }}
          />
        </PageDecisionHero>

        <div
          className="market-data-layout"
          data-testid="market-data-layout"
          data-rail-expanded={railExpanded ? "true" : "false"}
        >
          {seriesExplorerActive ? (
            <main
              className="market-data-main"
              data-testid="market-data-main"
              data-active-view="explorer"
            >
              <Suspense
                fallback={
                  <div
                    className="market-data-explorer-fallback"
                    data-testid="market-data-explorer-skeleton"
                  >
                    <div className="market-data-rail-skeleton">
                      <div className="market-data-rail-skeleton-item" />
                      <div className="market-data-rail-skeleton-item" />
                      <div className="market-data-rail-skeleton-item" />
                      <div className="market-data-rail-skeleton-item" />
                    </div>
                  </div>
                }
              >
                <MarketDataExplorerView
                  stableSeries={stableSeries}
                  fallbackSeries={fallbackSeries}
                  missingStableSeries={missingStableSeries}
                  catalog={catalog}
                  fxGroups={fxAnalyticalGroups}
                  observationDate={watchDate || undefined}
                  macroLoading={macroSeriesLoading}
                  macroError={macroSeriesError}
                  macroEmpty={macroSeriesEmpty}
                  onMacroRetry={refetchMacroSeries}
                  fxLoading={fxAnalyticalQuery.isLoading}
                  fxError={fxAnalyticalQuery.isError}
                  onFxRetry={() => void fxAnalyticalQuery.refetch(nonCancellingRefetchOptions)}
                />
              </Suspense>
            </main>
          ) : (
          <main className="market-data-main" data-testid="market-data-main">
            <MarketDataFormalRatesBoard
              model={terminalModel.rateQuotes}
              curveFilter={curveFilter}
              sourceFilter={sourceFilter}
              catalogVendorNames={catalogVendorNames}
              keyMetrics={keyRateSupplementMetrics}
              ratesBasisLabel={ratesBasisLabel}
              formalUseBlocked={formalUseBlocked}
              rateTrendChartOption={rateTrendChartOption}
              latestQuery={latestQuery}
              latestSeries={latestSeries}
              watermarksQuery={externalDataWatermarksQuery}
            />

            <section
              className="market-data-lower-deck-section"
              aria-labelledby="market-data-liquidity-title"
            >
              <div className="market-data-section-head-shell">
                <SectionHead
                  category="资金读数"
                  title="03 资金市场与存单"
                  note="DR007、回购与 Shibor 代理矩阵；正式口径摘要见右侧源门禁。"
                  numbered={false}
                  contentGap="flush"
                  titleId="market-data-liquidity-title"
                  testId="market-data-liquidity-head"
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
            </section>

            <MarketDataFxFormalSection
              payload={pageModel.fxFormalStatus}
              meta={pageModel.fxFormalMeta}
              isLoading={fxFormalStatusQuery.isLoading}
              isError={fxFormalStatusQuery.isError}
              onRetry={() => void fxFormalStatusQuery.refetch(nonCancellingRefetchOptions)}
            />

            {/* 分析上下文：PAGE-MKT-001 §C NewsAndCalendar 摘要位（组件内近视口才发请求）。 */}
            <MarketDataNewsCalendarSummary reportDate={watchDate || linkageReportDate} />

            <div ref={lazyExtended.ref} data-lazy-mount="extended-terminal">
              {lazyExtended.shouldMount || deferredWorkspacesRequested ? (
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
                <div
                  className="market-data-lazy-placeholder"
                  data-testid="market-data-extended-terminal-placeholder"
                  role="status"
                >
                  <strong>扩展行情</strong>
                  <span>滚动到此处时按需加载</span>
                </div>
              )}
            </div>

            {/* 04 宏观与外汇序列已迁入序列浏览器（?view=explorer）：主列只保留单行入口卡。 */}
            <button
              type="button"
              className="market-data-series-library-entry"
              data-testid="market-data-series-library-entry"
              onClick={() => openSeriesExplorer()}
            >
              <span className="market-data-series-library-entry__titles">
                <span className="market-data-series-library-entry__kicker">更多读数</span>
                <span className="market-data-series-library-entry__title">宏观与外汇序列</span>
              </span>
              <span className="market-data-series-library-entry__meta market-data-tabular">
                稳定 {macroSeriesLoading || macroSeriesError ? EM_DASH : stableSeries.length} · 降级{" "}
                {macroSeriesLoading || macroSeriesError ? EM_DASH : fallbackSeries.length} · 按需查看
              </span>
            </button>

            {/* 联动明细与 Livermore 策略读面已由 /cross-asset 承接：本页只留摘要与导航证据卡。 */}
            <div ref={lazyLinkage.ref} data-lazy-mount="linkage-summary">
              <MarketDataLinkageSummaryCard
                macroBondLinkageQuery={macroBondLinkageQuery}
                macroBondLinkage={macroBondLinkage}
                macroBondLinkageWarnings={macroBondLinkageWarnings}
                hasPortfolioImpact={hasPortfolioImpact}
                requestedReportDate={linkageReportDate || watchDate || null}
              />
            </div>

            <MarketDataStrategyEvidenceCard />

            <Collapse
              bordered={false}
              defaultActiveKey={[]}
              data-testid="market-data-tushare-collapse"
              items={[
                {
                  key: "tushare",
                  label: (
                    <span className="market-data-tushare-collapse-label">
                      <span>补充数据</span>
                      <span className="market-data-tushare-collapse-label__badge">Tushare</span>
                    </span>
                  ),
                  children: (
                    <div className="market-data-lower-deck-section">
                      <MarketDataTushareSupplementSection />
                    </div>
                  ),
                },
              ]}
            />
          </main>
          )}

          <aside className="market-data-rail" data-testid="market-data-rail">
            {/* 原生 details：收起时 children 仍在 DOM（契约 testid 可及），antd Collapse 懒挂载不满足该要求。 */}
            <details
              className="market-data-rail-disclosure"
              data-testid="market-data-rail-disclosure"
              onToggle={(event) => setRailExpanded(event.currentTarget.open)}
            >
              <summary
                className="market-data-rail-disclosure__summary"
                data-testid="market-data-rail-summary"
              >
                <span className="market-data-rail-disclosure__label">
                  {buildRailEntrySummary(railStatusCounts)}
                </span>
                <span className="market-data-rail-disclosure__hint">
                  {railExpanded ? "收起明细" : "展开明细"}
                </span>
              </summary>
              <div className="market-data-rail-disclosure__body">
                <MarketDataSupplyEvidenceRail
                  summary={coverageSummary}
                  sections={displayedCoverageSections}
                  watchDate={watchDate}
                  lineRows={railLineRows}
                  sourcePendingLabels={sourcePendingLabels}
                  evidenceLines={evidenceLines}
                  basisLabel={ratesBasisLabel}
                  formalUseAllowedLabel={formalUseAllowedLabel}
                  refreshStatus={refreshStatus}
                  refreshError={refreshError}
                  isRefreshing={isRefreshing}
                />
              </div>
            </details>
          </aside>
        </div>
      </section>
    </MarketWorkbenchFrame>
  );
}
