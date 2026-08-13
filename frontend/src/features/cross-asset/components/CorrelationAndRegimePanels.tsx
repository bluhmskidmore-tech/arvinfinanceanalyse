import { EM_DASH } from "../../../utils/format";
import { correlationColor, formatCorrelation, type CorrelationMatrix } from "../lib/crossAssetAnalytics";
import { FrontendAnalyticsChip } from "./MomentumAndVolatilityPanels";
import {
  heatmapColorFor,
  resolveCrossAssetChartPalette,
  type CrossAssetChartTheme,
} from "../lib/crossAssetChartTheme";

type CorrelationSummaryCard = {
  id: string;
  title: string;
  pair: string;
  value: string;
  detail: string;
};

function formatCorrelationPair(matrix: CorrelationMatrix, rowIndex: number, colIndex: number) {
  return `${matrix.labels[rowIndex]} / ${matrix.labels[colIndex]}`;
}

function buildCorrelationSummaryCards(matrix: CorrelationMatrix): CorrelationSummaryCard[] {
  const pairs = matrix.cells
    .flatMap((row, rowIndex) =>
      row.slice(rowIndex + 1).map((cell, offset) => ({
        rowIndex,
        colIndex: rowIndex + offset + 1,
        value: cell.value,
      })),
    )
    .filter((pair) => pair.value != null);

  const fallback = {
    pair: "暂无可比组合",
    value: EM_DASH,
  };
  const strongestPositive = pairs.slice().sort((left, right) => (right.value ?? -Infinity) - (left.value ?? -Infinity))[0];
  const strongestNegative = pairs.slice().sort((left, right) => (left.value ?? Infinity) - (right.value ?? Infinity))[0];
  const strongestAbsolute = pairs.slice().sort((left, right) => Math.abs(right.value ?? 0) - Math.abs(left.value ?? 0))[0];

  function cardValue(pair: (typeof pairs)[number] | undefined) {
    if (!pair) {
      return fallback;
    }
    return {
      pair: formatCorrelationPair(matrix, pair.rowIndex, pair.colIndex),
      value: formatCorrelation(pair.value),
    };
  }

  const positive = cardValue(strongestPositive);
  const negative = cardValue(strongestNegative);
  const focus = cardValue(strongestAbsolute);

  return [
    {
      id: "positive",
      title: "最强共振",
      pair: positive.pair,
      value: positive.value,
      detail: "正相关最高，适合观察同向传导。",
    },
    {
      id: "negative",
      title: "最强背离",
      pair: negative.pair,
      value: negative.value,
      detail: "负相关最低，适合观察对冲或错位。",
    },
    {
      id: "focus",
      title: "关注组合",
      pair: focus.pair,
      value: focus.value,
      detail: "绝对相关最高，优先展开矩阵复核。",
    },
  ];
}

export function CorrelationHeatmapPanel({
  matrix,
  theme = "light",
}: {
  matrix: CorrelationMatrix;
  theme?: CrossAssetChartTheme;
}) {
  if (matrix.keys.length < 2) return null;
  const palette = resolveCrossAssetChartPalette(theme);
  const cellColor =
    theme === "terminal"
      ? (value: number | null) => heatmapColorFor(value, palette)
      : correlationColor;
  const n = matrix.keys.length;
  const summaryCards = buildCorrelationSummaryCards(matrix);
  return (
    <section className="ca-correlation" data-testid="cross-asset-correlation-heatmap">
      <h2 className="ca-correlation__title">
        资产相关性矩阵 <FrontendAnalyticsChip />
      </h2>
      <p className="ca-correlation__subtitle">
        基于 sparkline 窗口滚动 Pearson 相关系数，一眼看清哪些资产在共振或背离。
      </p>
      <div className="ca-correlation__summary" data-testid="cross-asset-correlation-summary">
        {summaryCards.map((card) => (
          <article className="ca-correlation__summary-card" key={card.id}>
            <span>{card.title}</span>
            <strong>{card.pair}</strong>
            <em>{card.value}</em>
            <small>{card.detail}</small>
          </article>
        ))}
      </div>
      <details open className="ca-correlation__details" data-testid="cross-asset-correlation-details">
        <summary>
          <span>完整相关性矩阵</span>
          <strong>{n} 项资产</strong>
        </summary>
        <div className="ca-correlation__matrix-wrap" data-testid="cross-asset-correlation-matrix-wrap">
          <div
            className="ca-correlation__grid ca-correlation__grid--compact"
            style={{ gridTemplateColumns: `48px repeat(${n}, minmax(30px, 1fr))` }}
          >
            <div className="ca-correlation__cell ca-correlation__cell--header" />
            {matrix.labels.map((label) => (
              <div key={`col-${label}`} className="ca-correlation__cell ca-correlation__cell--header ca-correlation__cell--header-top">
                {label}
              </div>
            ))}
            {matrix.cells.map((row, ri) => (
              <div key={`row-group-${matrix.keys[ri]}`} className="ca-correlation__row-group">
                <div className="ca-correlation__cell ca-correlation__cell--header">
                  {matrix.labels[ri]}
                </div>
                {row.map((cell, ci) => {
                  const isDiag = ri === ci;
                  return (
                    <div
                      key={`${cell.rowKey}-${cell.colKey}`}
                      className={`ca-correlation__cell${isDiag ? " ca-correlation__cell--diagonal" : ""}`}
                      style={{
                        background: isDiag ? undefined : cellColor(cell.value),
                        color: cell.value != null && Math.abs(cell.value) > 0.5 ? "var(--ca-on-dark)" : undefined,
                      }}
                      title={`${matrix.labels[ri]} × ${matrix.labels[ci]}: ${formatCorrelation(cell.value)}`}
                    >
                      {isDiag ? "1" : formatCorrelation(cell.value)}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </details>
      <div className="ca-correlation__legend">
        <span>−1</span>
        <div className="ca-correlation__legend-bar" />
        <span>+1</span>
        <span className="ca-correlation__legend-label">负相关 ← 中性 → 正相关</span>
      </div>
    </section>
  );
}
