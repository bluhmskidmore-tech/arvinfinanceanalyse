import type { Dispatch, SetStateAction } from "react";
import { Select } from "antd";

import { FilterBar } from "../../../components/FilterBar";
import {
  DataStatusStrip,
  KpiBand,
  PageDecisionHero,
} from "../../../components/page/PagePrimitives";
import { tabularNumsStyle } from "../../../theme/designSystem";
import { MarketTerminalSparkline } from "../components/MarketTerminalSparkline";
import { MarketTerminalTicker } from "../components/MarketTerminalTicker";
import type { MarketTerminalTickerItem } from "../lib/marketDataTerminalModel";
import "./MarketDataPage.css";

export type MarketOverviewTone = "default" | "positive" | "negative" | "warning" | "error";

export type MarketOverviewMetric = {
  testId: string;
  title: string;
  value: string;
  detail: string;
  tone?: MarketOverviewTone;
  valueVariant?: "metric" | "text";
  sparklineValues?: readonly number[];
  sparklineTone?: "up" | "down" | "flat";
};

type MarketDataHeroSectionProps = {
  clientMode: "real" | "mock";
  watchDate: string;
  onWatchDateChange: (value: string) => void;
  isFormalBasis: boolean;
  terminalKpiMetrics: MarketOverviewMetric[];
  pipelineOverviewMetrics: MarketOverviewMetric[];
  terminalTickerItems: MarketTerminalTickerItem[];
  terminalTickerBasisLabel?: string;
  terminalTickerEmptyReason?: string;
  readinessVerdict: string;
  overviewReadinessLabel: string;
  secondaryLabel: string;
  refreshStatus: string;
  refreshError: string;
  isRefreshing: boolean;
  onRefresh: () => void;
  curveFilter: "treasury" | "cdb" | "both";
  onCurveFilterChange: Dispatch<SetStateAction<"treasury" | "cdb" | "both">>;
  creditSegment: "mtn" | "urban" | "both";
  onCreditSegmentChange: Dispatch<SetStateAction<"mtn" | "urban" | "both">>;
  sourceFilter: "all" | "choice" | "internal";
  onSourceFilterChange: Dispatch<SetStateAction<"all" | "choice" | "internal">>;
  activeFilterSummary: string;
  showTerminalKpiStrip?: boolean;
  showPipelineKpiStrip?: boolean;
};

function MarketOverviewMetricCard({
  metric,
  variant = "pipeline",
}: {
  metric: MarketOverviewMetric;
  variant?: "terminal" | "pipeline";
}) {
  const tone = metric.tone ?? "default";
  return (
    <article
      data-testid={metric.testId}
      className={[
        "market-data-overview-card",
        variant === "terminal" ? "market-data-terminal-kpi-card" : "",
        `market-data-overview-card--${tone}`,
        metric.valueVariant === "text" ? "market-data-overview-card--text" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <span aria-hidden className="market-data-overview-card__bar" />
      {variant === "terminal" ? (
        <div className="market-data-terminal-kpi-card__head">
          <div className="market-data-overview-card__label">{metric.title}</div>
          {metric.sparklineValues && metric.sparklineValues.length >= 2 ? (
            <MarketTerminalSparkline values={metric.sparklineValues} tone={metric.sparklineTone} />
          ) : null}
        </div>
      ) : (
        <div className="market-data-overview-card__label">{metric.title}</div>
      )}
      <div
        className="market-data-overview-card__value"
        style={metric.valueVariant === "text" ? undefined : tabularNumsStyle}
      >
        {metric.value}
      </div>
      <p className="market-data-overview-card__detail">{metric.detail}</p>
    </article>
  );
}

function MarketTerminalKpiStrip({ metrics }: { metrics: MarketOverviewMetric[] }) {
  if (metrics.length === 0) {
    return (
      <div data-testid="market-data-terminal-kpi-empty" className="market-data-terminal-kpi-empty">
        正式利率读面暂无 KPI 序列，不展示示例走势。
      </div>
    );
  }

  return (
    <KpiBand
      testId="market-data-terminal-kpi-strip"
      className="dashboard-overview-hero-strip market-data-terminal-kpi-strip"
    >
      {metrics.map((metric) => (
        <MarketOverviewMetricCard key={metric.testId} metric={metric} variant="terminal" />
      ))}
    </KpiBand>
  );
}

export function MarketPipelineKpiStrip({ metrics }: { metrics: MarketOverviewMetric[] }) {
  if (metrics.length === 0) {
    return null;
  }

  return (
    <section
      className="market-data-pipeline-kpi-section"
      data-testid="market-data-pipeline-kpi-section"
      aria-label="读面链路状态"
    >
      <div className="market-data-pipeline-kpi-section-head" data-testid="market-data-pipeline-kpi-collapse">
        <span className="market-data-pipeline-kpi-section-kicker">读面链路</span>
        <strong>数据管线状态（{metrics.length}）</strong>
        <span className="market-data-pipeline-kpi-section-hint">目录回收、降级与缺失计数</span>
      </div>
      <KpiBand
        testId="market-data-pipeline-kpi-strip"
        className="dashboard-overview-hero-strip market-data-overview-strip market-data-pipeline-kpi-strip"
      >
        {metrics.map((metric) => (
          <MarketOverviewMetricCard key={metric.testId} metric={metric} />
        ))}
      </KpiBand>
    </section>
  );
}

export function MarketDataHeroSection({
  clientMode,
  watchDate,
  onWatchDateChange,
  isFormalBasis,
  terminalKpiMetrics,
  pipelineOverviewMetrics,
  terminalTickerItems,
  terminalTickerBasisLabel,
  terminalTickerEmptyReason,
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
  showTerminalKpiStrip = false,
  showPipelineKpiStrip = true,
}: MarketDataHeroSectionProps) {
  return (
    <PageDecisionHero
      testId="market-data-contract-hero"
      title="市场数据"
      titleTestId="market-data-page-title"
      questionTestId="market-data-page-subtitle"
      eyebrow="深度终端"
      businessQuestion="在此核对利率、资金、曲线与成交读数；结论回顾请回市场工作台。"
      reportDateSlot={<span data-testid="market-data-watch-date-slot">观察日期 {watchDate}</span>}
      className="market-data-page__decision-hero-shell"
      actions={
        <div className="market-data-hero-actions">
          <span
            className={`market-data-mode-pill ${clientMode === "real" ? "market-data-mode-pill--real" : "market-data-mode-pill--mock"}`}
          >
            {clientMode === "real" ? "真实 DuckDB 读路径" : "本地离线契约回放"}
          </span>
          <button
            type="button"
            data-testid="market-data-refresh-button"
            disabled={isRefreshing}
            onClick={() => void onRefresh()}
            className={`market-data-hero-refresh-btn ${isRefreshing ? "market-data-hero-refresh-btn--disabled" : "market-data-hero-refresh-btn--enabled"}`}
          >
            {isRefreshing ? "刷新中…" : "刷新宏观数据"}
          </button>
        </div>
      }
    >
      <div className="market-data-hero-inner">
        <DataStatusStrip testId="market-data-data-status-strip">
          <div className="market-data-header-meta market-data-header-meta--compact">
            <span data-testid="market-data-readiness-verdict">{readinessVerdict}</span>
            <span aria-hidden="true">·</span>
            <span data-testid="market-data-overview-readiness-label">{overviewReadinessLabel}</span>
            <span aria-hidden="true">·</span>
            <span data-testid="market-data-overview-secondary-label">{secondaryLabel}</span>
            <span aria-hidden="true">·</span>
            <span data-testid="market-data-hero-readiness-chip">读面结论：{readinessVerdict}</span>
            <span aria-hidden="true">·</span>
            <span data-testid="market-data-formal-basis-chip">
              利率主表：{isFormalBasis ? "正式可用" : "仅分析"}
            </span>
          </div>
        </DataStatusStrip>

        <div className="market-data-header-body">
          <div data-testid="market-data-filter-strip">
            <div className="market-data-filter-tray">
              <FilterBar className="market-data-filter-row">
                <label className="market-data-filter-label">
                  日期
                  <input
                    type="date"
                    value={watchDate}
                    onChange={(e) => onWatchDateChange(e.target.value)}
                    className="market-data-filter-control"
                  />
                </label>
                <label className="market-data-filter-label">
                  国债 / 国开
                  <Select
                    value={curveFilter}
                    onChange={(v) => onCurveFilterChange(v)}
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
                    onChange={(v) => onCreditSegmentChange(v)}
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
                    onChange={(v) => onSourceFilterChange(v)}
                    options={[
                      { value: "all", label: "全部" },
                      { value: "choice", label: "Choice" },
                      { value: "internal", label: "内部" },
                    ]}
                    className="market-data-filter-select"
                  />
                </label>
              </FilterBar>
              <div
                data-testid="market-data-active-filter-summary"
                className="market-data-active-filter-summary"
              >
                当前生效：{activeFilterSummary}
              </div>
            </div>
          </div>

          {(refreshStatus || refreshError) && (
            <div
              className={`market-data-refresh-banner ${refreshError ? "market-data-refresh-banner--warn" : "market-data-refresh-banner--info"}`}
            >
              {refreshError || refreshStatus}
            </div>
          )}

          <MarketTerminalTicker
            items={terminalTickerItems}
            basisLabel={terminalTickerBasisLabel}
            emptyReason={terminalTickerEmptyReason}
          />

          {showTerminalKpiStrip ? <MarketTerminalKpiStrip metrics={terminalKpiMetrics} /> : null}
          {showPipelineKpiStrip ? <MarketPipelineKpiStrip metrics={pipelineOverviewMetrics} /> : null}
        </div>
      </div>
    </PageDecisionHero>
  );
}
