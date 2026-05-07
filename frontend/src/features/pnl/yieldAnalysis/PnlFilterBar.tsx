import { useMemo, useState } from "react";
import "./yieldAnalysis.css";

type Props = {
  filterSource: string;
  filterInvestType: string;
  filterPortfolio: string;
  searchText: string;
  filterOptions: {
    sources: string[];
    invests: string[];
    portfolios: string[];
  };
  filteredCount: number;
  totalCount: number;
  onSourceChange: (value: string) => void;
  onInvestTypeChange: (value: string) => void;
  onPortfolioChange: (value: string) => void;
  onSearchChange: (value: string) => void;
  onClearAll: () => void;
};

export function PnlFilterBar({
  filterSource,
  filterInvestType,
  filterPortfolio,
  searchText,
  filterOptions,
  filteredCount,
  totalCount,
  onSourceChange,
  onInvestTypeChange,
  onPortfolioChange,
  onSearchChange,
  onClearAll,
}: Props) {
  const [summaryExpanded, setSummaryExpanded] = useState(false);

  const activeFilters = useMemo(() => {
    const chips: string[] = [];
    if (filterSource !== "ALL") chips.push(`来源 ${filterSource}`);
    if (filterInvestType !== "ALL") chips.push(`类型 ${filterInvestType}`);
    if (filterPortfolio !== "ALL") chips.push(`组合 ${filterPortfolio}`);
    const keyword = searchText.trim();
    if (keyword) chips.push(`搜索 ${keyword}`);
    return chips;
  }, [filterInvestType, filterPortfolio, filterSource, searchText]);

  const hasAnyFilter = activeFilters.length > 0;
  const summaryText = hasAnyFilter ? activeFilters.join(" · ") : "当前未加筛选条件";

  return (
    <div className="yield-analysis-card pnl-filter-panel">
      <div className="pnl-filter-header">
        <div className="pnl-filter-copy">
          <div className="pnl-filter-title">筛选条件</div>
          <div className="pnl-filter-description">用于收窄当前损益分析范围</div>
          <div className="pnl-filter-summary">
            <div className="pnl-filter-summary-row">
              <span
                className="pnl-filter-count"
              >
                已筛选 {filteredCount} / {totalCount}
              </span>
              <span
                className={`pnl-filter-summary-text ${
                  summaryExpanded ? "pnl-filter-summary-text--expanded" : ""
                }`}
                title={summaryText}
              >
                {summaryText}
              </span>
            </div>
          </div>
        </div>
        <div className="pnl-filter-actions">
          {hasAnyFilter ? (
            <button
              type="button"
              onClick={() => setSummaryExpanded((v) => !v)}
              className="pnl-filter-button"
            >
              {summaryExpanded ? "收起摘要" : "展开摘要"}
            </button>
          ) : null}
          <button
            type="button"
            onClick={onClearAll}
            className="pnl-filter-button"
          >
            清空
          </button>
        </div>
      </div>

      <div className="pnl-filter-grid">
        <div>
          <div className="pnl-filter-field-label">数据来源</div>
          <select value={filterSource} onChange={(e) => onSourceChange(e.target.value)} className="pnl-filter-control">
            {filterOptions.sources.map((s) => (
              <option key={s} value={s}>
                {s === "ALL" ? "全部" : s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <div className="pnl-filter-field-label">投资类型</div>
          <select value={filterInvestType} onChange={(e) => onInvestTypeChange(e.target.value)} className="pnl-filter-control">
            {filterOptions.invests.map((s) => (
              <option key={s} value={s}>
                {s === "ALL" ? "全部" : s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <div className="pnl-filter-field-label">投资组合</div>
          <select value={filterPortfolio} onChange={(e) => onPortfolioChange(e.target.value)} className="pnl-filter-control">
            {filterOptions.portfolios.map((s) => (
              <option key={s} value={s}>
                {s === "ALL" ? "全部" : s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <div className="pnl-filter-field-label">搜索名称或代码</div>
          <input
            value={searchText}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="例如：国债 / 102000 / 同业存单"
            className="pnl-filter-control"
          />
        </div>
      </div>

      {hasAnyFilter ? (
        <div className="pnl-filter-chips">
          {activeFilters.map((item) => (
            <span
              key={item}
              className="pnl-filter-chip"
            >
              {item}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
