import type { StockMarketStateCard } from "../lib/stockAnalysisPageModel";
import { stockStatusLabel } from "../lib/stockAnalysisPageCopy";

type StockAnalysisGateConditionsCardProps = {
  marketState: StockMarketStateCard;
};

function conditionTone(status: string): "positive" | "negative" | "warning" {
  if (status === "pass") return "positive";
  if (status === "fail") return "negative";
  return "warning";
}

/** First-screen market-gate card: the four gate conditions with status dots and one-line evidence. */
export function StockAnalysisGateConditionsCard({
  marketState,
}: StockAnalysisGateConditionsCardProps) {
  return (
    <section
      className="stock-analysis-page__fs-card"
      data-testid="stock-analysis-gate-conditions-card"
      aria-label="市场门禁条件"
    >
      <header className="stock-analysis-page__fs-card-head">
        <h2>市场门禁</h2>
        <span className="stock-analysis-page__fs-card-pill stock-analysis-page__tabular">
          {marketState.passedLabel}
        </span>
      </header>
      {marketState.conditions.length > 0 ? (
        <ul className="stock-analysis-page__fs-gate-list">
          {marketState.conditions.map((condition) => (
            <li
              key={condition.key}
              data-status={condition.status}
              data-testid={`stock-analysis-gate-condition-${condition.key}`}
            >
              <span
                className="stock-analysis-page__fs-status-dot"
                data-tone={conditionTone(condition.status)}
                aria-hidden="true"
              />
              <div className="stock-analysis-page__fs-gate-body">
                <div className="stock-analysis-page__fs-gate-title">
                  <strong>{condition.label}</strong>
                  <em data-tone={conditionTone(condition.status)}>
                    {stockStatusLabel(condition.status)}
                  </em>
                </div>
                <p title={condition.evidence}>{condition.evidence}</p>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="stock-analysis-page__fs-card-empty" role="status">
          门禁条件未返回，等待主策略快照补齐。
        </p>
      )}
      <footer className="stock-analysis-page__fs-card-foot stock-analysis-page__tabular">
        <span>观察暴露 {marketState.exposureLabel}</span>
        {marketState.macroDisclosure?.adjustmentLabel ? (
          <span data-testid="stock-analysis-gate-macro-overlay">
            {marketState.macroDisclosure.cycleStateLabel
              ? `${marketState.macroDisclosure.adjustmentLabel} · ${marketState.macroDisclosure.cycleStateLabel}`
              : marketState.macroDisclosure.adjustmentLabel}
          </span>
        ) : null}
      </footer>
    </section>
  );
}
