import type { StockBacktestCaliberDisclosureModel } from "../lib/stockAnalysisBacktestModel";

type StockAnalysisBacktestCaliberDisclosureProps = {
  model: StockBacktestCaliberDisclosureModel | null;
};

/** 回测口径说明：注脚折叠区，model 为 null 时完全不渲染（零布局影响）。 */
export function StockAnalysisBacktestCaliberDisclosure({
  model,
}: StockAnalysisBacktestCaliberDisclosureProps) {
  if (!model) return null;

  return (
    <details
      className="mt-2 rounded-md border border-default-200 p-2 text-xs"
      data-testid="stock-analysis-strategy-backtest-caliber-disclosure"
    >
      <summary className="cursor-pointer font-medium text-default-600">口径说明</summary>
      <div className="mt-2 flex flex-col gap-1.5">
        {model.entryPriceWarning ? (
          <p
            className="rounded bg-warning/10 p-2 text-warning"
            data-testid="stock-analysis-strategy-backtest-caliber-warning"
          >
            {model.entryPriceWarning}
          </p>
        ) : null}
        {model.sampleGenerationLabel ? (
          <p className="text-default-500" data-testid="stock-analysis-strategy-backtest-caliber-sample">
            {model.sampleGenerationLabel}
          </p>
        ) : null}
        {model.basisNotes.length > 0 ? (
          <ul
            className="list-disc pl-4 text-default-500"
            data-testid="stock-analysis-strategy-backtest-caliber-notes"
          >
            {model.basisNotes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        ) : null}
      </div>
    </details>
  );
}
