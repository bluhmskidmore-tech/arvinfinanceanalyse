import type { StockFirstScreenHeroModel } from "../lib/stockAnalysisFirstScreenModel";

type StockAnalysisFirstScreenHeroProps = {
  asOfLabel: string;
  requestedAsOfLabel?: string | null;
  model: StockFirstScreenHeroModel;
};

/** First-screen hero: one-sentence review verdict plus 3-4 KPI numbers. */
export function StockAnalysisFirstScreenHero({
  asOfLabel,
  requestedAsOfLabel,
  model,
}: StockAnalysisFirstScreenHeroProps) {
  return (
    <section
      className="stock-analysis-page__fs-hero"
      data-testid="stock-analysis-decision-panel"
      aria-label="今日复核结论"
    >
      <div className="stock-analysis-page__fs-hero-lead">
        <p className="stock-analysis-page__fs-hero-eyebrow">
          <span>今日股票复核</span>
          <span className="stock-analysis-page__fs-hero-date stock-analysis-page__tabular">
            数据日 {asOfLabel}
            {requestedAsOfLabel && requestedAsOfLabel !== "默认"
              ? `（请求 ${requestedAsOfLabel}）`
              : ""}
          </span>
        </p>
        <h1 className="stock-analysis-page__fs-hero-headline" data-testid="stock-analysis-hero-headline">
          {model.headline}
        </h1>
        <p className="stock-analysis-page__fs-hero-sub" data-testid="stock-analysis-hero-lead">
          {model.lead}
        </p>
      </div>
      <dl className="stock-analysis-page__fs-hero-kpis" aria-label="首屏复核摘要">
        {model.kpis.map((kpi) => (
          <div
            key={kpi.key}
            className="stock-analysis-page__fs-hero-kpi"
            data-tone={kpi.tone}
            data-testid={`stock-analysis-hero-kpi-${kpi.key}`}
          >
            <dt>{kpi.label}</dt>
            <dd>
              <strong className="stock-analysis-page__tabular">{kpi.value}</strong>
              {kpi.unit ? <span>{kpi.unit}</span> : null}
            </dd>
            {kpi.detail ? <small title={kpi.detail}>{kpi.detail}</small> : null}
          </div>
        ))}
      </dl>
    </section>
  );
}
