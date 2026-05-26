import type { Dispatch, SetStateAction } from "react";
import { Select } from "antd";

import { FilterBar } from "../../../components/FilterBar";
import {
  DataStatusStrip,
  KpiBand,
  PageDecisionHero,
} from "../../../components/page/PagePrimitives";
import { tabularNumsStyle } from "../../../theme/designSystem";
import "./MarketDataPage.css";

export type MarketOverviewTone = "default" | "positive" | "negative" | "warning" | "error";

export type MarketOverviewMetric = {
  testId: string;
  title: string;
  value: string;
  detail: string;
  tone?: MarketOverviewTone;
  valueVariant?: "metric" | "text";
};

type MarketDataHeroSectionProps = {
  clientMode: "real" | "mock";
  watchDate: string;
  onWatchDateChange: (value: string) => void;
  isFormalBasis: boolean;
  catalogCount: number;
  stableCount: number;
  stableCatalogCount: number;
  overviewMetrics: MarketOverviewMetric[];
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
};

function MarketOverviewHeroStrip({ metrics }: { metrics: MarketOverviewMetric[] }) {
  return (
    <KpiBand
      testId="market-data-overview-hero-strip"
      className="dashboard-overview-hero-strip market-data-overview-strip"
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
  overviewMetrics,
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
            <span>利率主表口径：{isFormalBasis ? "正式" : "分析"}</span>
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
            </div>
          </div>

          {(refreshStatus || refreshError) && (
            <div
              className={`market-data-refresh-banner ${refreshError ? "market-data-refresh-banner--warn" : "market-data-refresh-banner--info"}`}
            >
              {refreshError || refreshStatus}
            </div>
          )}

          <MarketOverviewHeroStrip metrics={overviewMetrics} />
        </div>
      </div>
    </PageDecisionHero>
  );
}
