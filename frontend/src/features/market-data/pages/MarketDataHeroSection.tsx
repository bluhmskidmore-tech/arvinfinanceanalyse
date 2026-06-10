import type { Dispatch, SetStateAction } from "react";
import { Collapse, Select } from "antd";

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
  catalogCount: number;
  stableCount: number;
  stableCatalogCount: number;
  terminalKpiMetrics: MarketOverviewMetric[];
  pipelineOverviewMetrics: MarketOverviewMetric[];
  terminalTickerItems: MarketTerminalTickerItem[];
  terminalTickerBasisLabel?: string;
  terminalTickerEmptyReason?: string;
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
};

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
      {metrics.map((metric) => {
        const tone = metric.tone ?? "default";
        return (
          <article
            key={metric.testId}
            data-testid={metric.testId}
            className={[
              "market-data-overview-card market-data-terminal-kpi-card",
              `market-data-overview-card--${tone}`,
              metric.valueVariant === "text" ? "market-data-overview-card--text" : "",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            <span aria-hidden className="market-data-overview-card__bar" />
            <div className="market-data-terminal-kpi-card__head">
              <div className="market-data-overview-card__label">{metric.title}</div>
              {metric.sparklineValues && metric.sparklineValues.length >= 2 ? (
                <MarketTerminalSparkline
                  values={metric.sparklineValues}
                  tone={metric.sparklineTone}
                />
              ) : null}
            </div>
            <div
              className="market-data-overview-card__value"
              style={metric.valueVariant === "text" ? undefined : tabularNumsStyle}
            >
              {metric.value}
            </div>
            <p className="market-data-overview-card__detail">{metric.detail}</p>
          </article>
        );
      })}
    </KpiBand>
  );
}

function MarketPipelineKpiCollapse({ metrics }: { metrics: MarketOverviewMetric[] }) {
  return (
    <Collapse
      data-testid="market-data-pipeline-kpi-collapse"
      className="market-data-pipeline-kpi-collapse"
      bordered={false}
      defaultActiveKey={[]}
      items={[
        {
          key: "pipeline-kpis",
          label: `读面运维指标（${metrics.length}）`,
          forceRender: true,
          children: (
            <KpiBand
              testId="market-data-pipeline-kpi-strip"
              className="dashboard-overview-hero-strip market-data-overview-strip market-data-pipeline-kpi-strip"
            >
              {metrics.map((metric) => {
                const tone = metric.tone ?? "default";
                return (
                  <article
                    key={metric.testId}
                    data-testid={metric.testId}
                    className={[
                      "market-data-overview-card",
                      `market-data-overview-card--${tone}`,
                      metric.valueVariant === "text" ? "market-data-overview-card--text" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    <span aria-hidden className="market-data-overview-card__bar" />
                    <div className="market-data-overview-card__label">{metric.title}</div>
                    <div
                      className="market-data-overview-card__value"
                      style={metric.valueVariant === "text" ? undefined : tabularNumsStyle}
                    >
                      {metric.value}
                    </div>
                    <p className="market-data-overview-card__detail">{metric.detail}</p>
                  </article>
                );
              })}
            </KpiBand>
          ),
        },
      ]}
    />
  );
}

export function MarketDataHeroSection({
  clientMode,
  watchDate,
  onWatchDateChange,
  isFormalBasis,
  catalogCount,
  stableCount,
  stableCatalogCount,
  terminalKpiMetrics,
  pipelineOverviewMetrics,
  terminalTickerItems,
  terminalTickerBasisLabel,
  terminalTickerEmptyReason,
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
}: MarketDataHeroSectionProps) {
  return (
    <PageDecisionHero
      testId="market-data-contract-hero"
      title="市场数据"
      titleTestId="market-data-page-title"
      questionTestId="market-data-page-subtitle"
      eyebrow="市场概览"
      businessQuestion="先确认读面是否 ready、口径边界是否清晰，再下钻利率、资金与成交。"
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
          <div className="market-data-header-meta">
            <span>利率主表口径：{isFormalBasis ? "正式" : "分析/候选"}</span>
            <span>目录 {catalogCount}</span>
            <span>
              稳定回收 {stableCount} / {stableCatalogCount}
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

          <MarketTerminalKpiStrip metrics={terminalKpiMetrics} />
          <MarketPipelineKpiCollapse metrics={pipelineOverviewMetrics} />
        </div>
      </div>
    </PageDecisionHero>
  );
}
