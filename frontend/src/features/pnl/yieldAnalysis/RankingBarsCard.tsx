import "./yieldAnalysis.css";

export type RankingBarRow = {
  key: string;
  total_pnl: number;
  interest_income?: number;
  fair_value_change?: number;
  capital_gain?: number;
  proportion?: number | null;
};

type Props = {
  title: string;
  rows: RankingBarRow[];
  onPick?: (key: string) => void;
  emptyText?: string;
  maxDisplay?: number;
};

function fmtWan(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${(value / 10_000).toFixed(2)} 万`;
}

function buildBreakdownParts(row: RankingBarRow) {
  return [
    { key: "interest", label: "514 利息", value: fmtWan(row.interest_income) },
    { key: "fair-value", label: "516 公允", value: fmtWan(row.fair_value_change) },
    { key: "capital-gain", label: "517 投资收益", value: fmtWan(row.capital_gain) },
  ];
}

export function RankingBarsCard({
  title,
  rows,
  onPick,
  emptyText = "暂无数据",
  maxDisplay = 12,
}: Props) {
  const items = rows ?? [];
  const maxAbs = items.reduce((acc, row) => Math.max(acc, Math.abs(Number(row?.total_pnl ?? 0))), 0);
  const isClickable = typeof onPick === "function";

  const getDisplayLabel = (key: string): string => {
    if (title === "按数据来源") {
      if (key === "FI") return "标准债券";
      if (key === "NonStd") return "非标投资";
    }
    return key;
  };

  return (
    <div className="yield-analysis-card yield-ranking-card">
      <div className="yield-ranking-header">
        <div className="yield-ranking-heading">
          <h3
            className="yield-ranking-title"
          >
            {title}
          </h3>
          <p className="yield-ranking-subtitle">
            按损益绝对值排序展示
          </p>
        </div>
        <div className="yield-ranking-top-count">
          Top {Math.min(items.length, maxDisplay)}
        </div>
      </div>

      <div className="yield-ranking-body">
        {items.length === 0 ? (
          <div className="yield-ranking-empty">
            {emptyText}
          </div>
        ) : (
          items.slice(0, maxDisplay).map((row, index) => {
            const key = String(row?.key ?? "-");
            const displayLabel = getDisplayLabel(key);
            const value = Number(row?.total_pnl ?? 0);
            const width = maxAbs > 0 ? (Math.abs(value) / maxAbs) * 100 : 0;
            const positive = value >= 0;
            const proportion =
              row?.proportion === null || row?.proportion === undefined ? null : Number(row.proportion) * 100;
            const breakdownParts = buildBreakdownParts(row);
            const breakdown = breakdownParts.map((part) => `${part.label} ${part.value}`).join(" · ");
            const rowClassName = `yield-ranking-row ${isClickable ? "yield-ranking-row--clickable" : ""}`.trim();
            const inner = (
              <div className="yield-ranking-row-inner">
                <div className="yield-ranking-index">
                  {index + 1}
                </div>
                <div className="yield-ranking-main">
                  <div className="yield-ranking-line">
                    <div className="yield-ranking-text">
                      <div
                        className="yield-ranking-label"
                        title={displayLabel}
                      >
                        {displayLabel}
                      </div>
                    </div>
                    <div className="yield-ranking-value-block">
                      <div
                        className={`yield-ranking-value ${
                          positive ? "yield-ranking-value--positive" : "yield-ranking-value--negative"
                        }`}
                      >
                        {fmtWan(value)}
                      </div>
                      <div className="yield-ranking-proportion">
                        {proportion === null ? "-" : `${proportion.toFixed(1)}%`}
                      </div>
                    </div>
                  </div>
                  <div
                    className="yield-ranking-breakdown"
                    title={breakdown}
                  >
                    {breakdownParts.map((part) => (
                      <span key={part.key} className="yield-ranking-breakdown-part">
                        <span className="yield-ranking-breakdown-label">{part.label}</span>
                        <span className="yield-ranking-breakdown-value">{part.value}</span>
                      </span>
                    ))}
                  </div>
                  <div className="yield-ranking-bar">
                    <div
                      className={`yield-ranking-bar-fill ${
                        positive ? "yield-ranking-bar-fill--positive" : "yield-ranking-bar-fill--negative"
                      }`}
                      style={{ width: `${Math.min(100, Math.max(0, width))}%` }}
                    />
                  </div>
                </div>
              </div>
            );
            if (isClickable) {
              return (
                <button
                  key={`${title}:${key}`}
                  type="button"
                  className={rowClassName}
                  data-testid={`yield-ranking-row-${index}`}
                  onClick={() => onPick?.(key)}
                >
                  {inner}
                </button>
              );
            }
            return (
              <div key={`${title}:${key}`} className={rowClassName} data-testid={`yield-ranking-row-${index}`}>
                {inner}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
