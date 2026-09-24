import type { StockMacroCycleCardModel } from "../lib/stockAnalysisFirstScreenModel";

type StockAnalysisMacroCycleCardProps = {
  model: StockMacroCycleCardModel | null;
};

/** First-screen macro-cycle card: expansion score plus per-layer readiness. */
export function StockAnalysisMacroCycleCard({ model }: StockAnalysisMacroCycleCardProps) {
  return (
    <section
      className="stock-analysis-page__fs-card"
      data-testid="stock-analysis-macro-cycle-card"
      aria-label="宏观周期"
    >
      <header className="stock-analysis-page__fs-card-head">
        <h2>宏观周期</h2>
        {model ? (
          <span className="stock-analysis-page__fs-card-pill" data-tone={model.tone}>
            {model.statusLabel}
          </span>
        ) : null}
      </header>
      {model ? (
        <>
          <div className="stock-analysis-page__fs-macro-score" title={model.evidence}>
            <div>
              <span className="stock-analysis-page__fs-macro-label">宏观分</span>
              <strong className="stock-analysis-page__tabular">{model.macroScoreLabel}</strong>
            </div>
            <div>
              <span className="stock-analysis-page__fs-macro-label">周期状态</span>
              <strong>{model.cycleStateLabel}</strong>
            </div>
          </div>
          <ul className="stock-analysis-page__fs-macro-layers">
            {model.layers.map((layer) => (
              <li key={layer.key} data-tone={layer.tone} title={layer.evidence}>
                <span
                  className="stock-analysis-page__fs-status-dot"
                  data-tone={layer.tone}
                  aria-hidden="true"
                />
                <span className="stock-analysis-page__fs-macro-layer-name">{layer.label}</span>
                <small className="stock-analysis-page__tabular">{layer.weightLabel}</small>
                <em>{layer.statusLabel}</em>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="stock-analysis-page__fs-card-empty" role="status">
          宏观周期框架未返回，待后端补充证据。
        </p>
      )}
    </section>
  );
}
