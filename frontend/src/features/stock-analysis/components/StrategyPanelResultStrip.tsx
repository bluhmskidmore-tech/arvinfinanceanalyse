import type {
  StockClosedLoopTone,
  StockStrategyPanelMiniStatValueTone,
  StockStrategyPanelResultSummary,
} from "../lib/stockAnalysisPageModel";

type StrategyPanelResultStripProps = {
  summary: StockStrategyPanelResultSummary;
  testId?: string;
};

function valueToneClass(valueTone?: StockStrategyPanelMiniStatValueTone): string {
  if (valueTone === "up") return "stock-analysis-page__panel-kpi-tile--up";
  if (valueTone === "down") return "stock-analysis-page__panel-kpi-tile--down";
  if (valueTone === "warning") return "stock-analysis-page__panel-kpi-tile--warning";
  if (valueTone === "emphasis") return "stock-analysis-page__panel-kpi-tile--emphasis";
  return "";
}

function legacyToneClass(tone?: StockClosedLoopTone): string {
  if (tone === "positive") return "stock-analysis-page__panel-kpi-tile--emphasis";
  if (tone === "negative") return "stock-analysis-page__panel-kpi-tile--down";
  if (tone === "warning") return "stock-analysis-page__panel-kpi-tile--warning";
  return "";
}

function tileClass(stat: StockStrategyPanelResultSummary["stats"][number]): string {
  return `stock-analysis-page__panel-kpi-tile ${valueToneClass(stat.valueTone) || legacyToneClass(stat.tone)}`.trim();
}

type StrategyPanelKpiGridProps = {
  stats: StockStrategyPanelResultSummary["stats"];
  testId?: string;
  maxItems?: number;
  className?: string;
};

export function StrategyPanelKpiGrid({
  stats,
  testId,
  maxItems,
  className,
}: StrategyPanelKpiGridProps) {
  const visibleStats = maxItems != null ? stats.slice(0, maxItems) : stats;
  if (visibleStats.length === 0) {
    return null;
  }
  return (
    <div
      className={`stock-analysis-page__panel-kpi-grid${className ? ` ${className}` : ""}`}
      aria-label="执行结果摘要"
      data-testid={testId}
    >
      {visibleStats.map((stat) => (
        <article
          key={stat.key}
          className={tileClass(stat)}
          data-testid={testId ? `${testId}-stat-${stat.key}` : undefined}
        >
          <span className="stock-analysis-page__panel-kpi-label">{stat.label}</span>
          <strong className="stock-analysis-page__panel-kpi-value stock-analysis-page__tabular">
            {stat.value}
          </strong>
        </article>
      ))}
    </div>
  );
}

export function StrategyPanelResultStrip({ summary, testId }: StrategyPanelResultStripProps) {
  return (
    <div
      className={`stock-analysis-page__panel-result${summary.tone ? ` stock-analysis-page__panel-result--${summary.tone}` : ""}`}
      data-testid={testId}
    >
      <StrategyPanelKpiGrid stats={summary.stats} testId={testId} />
      {summary.headline ? (
        <p className="stock-analysis-page__panel-result-headline">{summary.headline}</p>
      ) : null}
      {summary.detail ? <p className="stock-analysis-page__panel-result-detail">{summary.detail}</p> : null}
    </div>
  );
}

export function StrategyPanelComplianceDetails({
  complianceDetail,
  testId,
}: {
  complianceDetail?: string;
  testId?: string;
}) {
  if (!complianceDetail?.trim()) {
    return null;
  }
  return (
    <details className="stock-analysis-page__panel-compliance" data-testid={testId}>
      <summary>口径与限制</summary>
      <p>{complianceDetail}</p>
    </details>
  );
}
