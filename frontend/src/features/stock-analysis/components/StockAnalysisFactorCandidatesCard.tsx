import type { FactorScreenCandidateItem } from "../../../api/contracts";
import type { StockFactorScreenCardModel } from "../lib/stockAnalysisFirstScreenModel";

type StockAnalysisFactorCandidatesCardProps = {
  model: StockFactorScreenCardModel | null;
  items: FactorScreenCandidateItem[];
  onOpenDetail: (row: FactorScreenCandidateItem) => void;
};

const MISSING = "—";

function formatScore(value: number | null | undefined): string {
  return value != null && Number.isFinite(value) ? value.toFixed(4) : MISSING;
}

function formatRatioPercent(value: number | null | undefined, digits = 1): string {
  return value != null && Number.isFinite(value) ? `${(value * 100).toFixed(digits)}%` : MISSING;
}

function formatSignedRatioPercent(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return MISSING;
  const pct = value * 100;
  return `${pct > 0 ? "+" : ""}${pct.toFixed(1)}%`;
}

function returnTone(value: number | null | undefined): "up" | "down" | "flat" {
  if (value == null || !Number.isFinite(value) || value === 0) return "flat";
  return value > 0 ? "up" : "down";
}

/** First-screen factor-screen candidate table (read-only observation pool). */
export function StockAnalysisFactorCandidatesCard({
  model,
  items,
  onOpenDetail,
}: StockAnalysisFactorCandidatesCardProps) {
  return (
    <section
      className="stock-analysis-page__fs-card stock-analysis-page__fs-factor-card"
      data-testid="stock-analysis-factor-candidates-card"
      aria-label="因子初筛候选"
    >
      <header className="stock-analysis-page__fs-card-head">
        <div className="stock-analysis-page__fs-card-head-main">
          <h2>因子初筛候选</h2>
          <small
            className="stock-analysis-page__fs-factor-meta stock-analysis-page__tabular"
            title={model?.coverageLabel ?? undefined}
          >
            {model ? `因子截面 ${model.asOfLabel}` : "接口未提供"}
          </small>
        </div>
        <div className="stock-analysis-page__fs-card-head-side">
          {model?.degraded ? (
            <span
              className="stock-analysis-page__fs-card-pill"
              data-tone="warning"
              data-testid="stock-analysis-factor-degraded-badge"
              title={model.degradedTitle ?? undefined}
            >
              截面滞后
            </span>
          ) : null}
          {model?.observationOnly ? (
            <span className="stock-analysis-page__fs-card-pill">只读观察</span>
          ) : null}
          <span className="stock-analysis-page__fs-card-pill stock-analysis-page__tabular">
            {model ? model.countLabel : "0 只"}
          </span>
        </div>
      </header>
      {!model ? (
        <p className="stock-analysis-page__fs-card-empty" role="status" data-testid="stock-analysis-factor-candidates-empty">
          多因子初筛未返回，等待主策略快照补齐。
        </p>
      ) : items.length === 0 ? (
        <p className="stock-analysis-page__fs-card-empty" role="status" data-testid="stock-analysis-factor-candidates-empty">
          本次因子截面没有通过初筛的候选。
        </p>
      ) : (
        <div className="stock-analysis-page__fs-factor-table-wrap">
          <table className="stock-analysis-page__fs-factor-table">
            <thead>
              <tr>
                <th scope="col" className="stock-analysis-page__fs-num">排名</th>
                <th scope="col">标的</th>
                <th scope="col">行业</th>
                <th scope="col" className="stock-analysis-page__fs-num">综合分</th>
                <th scope="col" className="stock-analysis-page__fs-num">PE</th>
                <th scope="col" className="stock-analysis-page__fs-num">ROE</th>
                <th scope="col" className="stock-analysis-page__fs-num">近3月</th>
                <th scope="col" className="stock-analysis-page__fs-num">股息率</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.stock_code} data-testid={`stock-analysis-factor-row-${row.stock_code}`}>
                  <td className="stock-analysis-page__fs-num stock-analysis-page__tabular">{row.rank}</td>
                  <td>
                    <button
                      type="button"
                      className="stock-analysis-page__fs-factor-stock"
                      aria-label={`查看${row.stock_name}（${row.stock_code}）详情`}
                      onClick={() => onOpenDetail(row)}
                    >
                      <span>{row.stock_name}</span>
                      <small className="stock-analysis-page__tabular">{row.stock_code}</small>
                    </button>
                  </td>
                  <td className="stock-analysis-page__fs-factor-sector">
                    {row.sector_name || row.industry || MISSING}
                  </td>
                  <td className="stock-analysis-page__fs-num stock-analysis-page__tabular">
                    {formatScore(row.score)}
                  </td>
                  <td className="stock-analysis-page__fs-num stock-analysis-page__tabular">
                    {row.pe != null && Number.isFinite(row.pe) ? row.pe.toFixed(1) : MISSING}
                  </td>
                  <td className="stock-analysis-page__fs-num stock-analysis-page__tabular">
                    {formatRatioPercent(row.roe)}
                  </td>
                  <td
                    className="stock-analysis-page__fs-num stock-analysis-page__tabular"
                    data-trend={returnTone(row.three_month_return)}
                  >
                    {formatSignedRatioPercent(row.three_month_return)}
                  </td>
                  <td className="stock-analysis-page__fs-num stock-analysis-page__tabular">
                    {row.dividend_yield != null && row.dividend_yield > 0
                      ? formatRatioPercent(row.dividend_yield, 2)
                      : MISSING}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
