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
  if (valueTone === "up") return "text-success bg-success/10 border-success/20";
  if (valueTone === "down") return "text-danger bg-danger/10 border-danger/20";
  if (valueTone === "warning") return "text-warning bg-warning/10 border-warning/20";
  if (valueTone === "emphasis") return "text-primary bg-primary/10 border-primary/20";
  return "text-default-700 bg-default-100/50 border-default-200";
}

function legacyToneClass(tone?: StockClosedLoopTone): string {
  if (tone === "positive") return "text-primary bg-primary/10 border-primary/20";
  if (tone === "negative") return "text-danger bg-danger/10 border-danger/20";
  if (tone === "warning") return "text-warning bg-warning/10 border-warning/20";
  return "text-default-700 bg-default-100/50 border-default-200";
}

function tileClass(stat: StockStrategyPanelResultSummary["stats"][number]): string {
  const tone = valueToneClass(stat.valueTone) || legacyToneClass(stat.tone);
  return `flex flex-col p-2 rounded-lg border ${tone}`;
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
      className={`grid grid-cols-2 gap-3 ${className ?? ""}`}
      aria-label="执行结果摘要"
      data-testid={testId}
    >
      {visibleStats.map((stat) => (
        <article
          key={stat.key}
          className={tileClass(stat)}
          data-testid={testId ? `${testId}-stat-${stat.key}` : undefined}
        >
          <span className="text-xs opacity-80 mb-1">{stat.label}</span>
          <strong className="text-lg font-semibold tabular-nums leading-none">
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
      className="flex flex-col gap-3 p-3 bg-default-50 rounded-lg border border-default-100 mt-2"
      data-testid={testId}
    >
      <StrategyPanelKpiGrid stats={summary.stats} testId={testId} />
      {summary.headline ? (
        <p className="text-sm font-medium text-foreground">{summary.headline}</p>
      ) : null}
      {summary.detail ? <p className="text-xs text-default-500">{summary.detail}</p> : null}
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
    <details className="mt-3 text-xs text-default-500 border border-default-200 rounded-lg p-3 bg-default-100/30 group" data-testid={testId}>
      <summary className="cursor-pointer font-medium hover:text-default-700 transition-colors">口径与限制</summary>
      <p className="mt-2 pt-2 border-t border-default-200/50 leading-relaxed">{complianceDetail}</p>
    </details>
  );
}
