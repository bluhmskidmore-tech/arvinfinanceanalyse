import { buildSparkPath } from "../../workbench/dashboard/sparklinePath";

const VIEW_W = 68;
const VIEW_H = 18;
const MIN_PLOTTABLE_POINTS = 2;

export type StockAnalysisTrendSparklineTone = "positive" | "negative" | "neutral";

type StockAnalysisTrendSparklineProps = {
  /** Backend-normalized cumulative percent series; the component does not recompute it. */
  values: readonly number[];
  tone: StockAnalysisTrendSparklineTone;
  /** Hover text carrying the window and the observed session count. */
  title?: string;
};

/**
 * Inline SVG mini trend line for one heavyweight stock row.
 *
 * Deliberately not an ECharts instance: this block renders up to 24 lines and
 * chart instances were the measured first-screen cost on this page. Stroke is
 * `currentColor` so the page tone tokens stay the single colour source.
 */
export function StockAnalysisTrendSparkline({
  values,
  tone,
  title,
}: StockAnalysisTrendSparklineProps) {
  const plottable = values.filter((value) => Number.isFinite(value));
  if (plottable.length < MIN_PLOTTABLE_POINTS) {
    return null;
  }

  return (
    <svg
      className="stock-analysis-page__sector-heavyweight-spark"
      data-testid="sector-heavyweight-sparkline"
      data-tone={tone}
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={title ?? "近期走势"}
      focusable="false"
    >
      {title ? <title>{title}</title> : null}
      <path
        d={buildSparkPath(plottable, VIEW_W, VIEW_H)}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
