/**
 * Option two 页面共享的迷你走势线：归一化 path，缺值断笔不插值。
 * 支持可选的 xValues（如期限年限），按真实横轴比例定位，避免等距连线误导斜率。
 * 纯视觉编码（复述同屏已展示的数值序列），不承载新的业务口径。
 */
type OptionTwoSparklineProps = {
  values: ReadonlyArray<number | null>;
  className?: string;
  title?: string;
  endDot?: boolean;
  /** 与 values 等长的横轴刻度（须递增）；缺省时按索引等距。 */
  xValues?: ReadonlyArray<number>;
};

const VIEW_W = 100;
const VIEW_H = 20;
const PAD_Y = 2;

type SparkPoint = { x: number; y: number; gapBefore: boolean };

function resolveXPositions(
  count: number,
  xValues: ReadonlyArray<number> | undefined,
): number[] {
  if (
    xValues &&
    xValues.length === count &&
    xValues.every((value, index) => index === 0 || value > xValues[index - 1]!)
  ) {
    const min = xValues[0]!;
    const span = xValues[count - 1]! - min;
    if (span > 0) {
      return xValues.map((value) => ((value - min) / span) * VIEW_W);
    }
  }
  const step = count > 1 ? VIEW_W / (count - 1) : VIEW_W;
  return Array.from({ length: count }, (_, index) => index * step);
}

export function OptionTwoSparkline({
  values,
  className,
  title,
  endDot = false,
  xValues,
}: OptionTwoSparklineProps) {
  const numeric = values.filter(
    (value): value is number => value != null && Number.isFinite(value),
  );
  if (numeric.length < 2) {
    return null;
  }
  const min = Math.min(...numeric);
  const max = Math.max(...numeric);
  const span = max - min;
  const xPositions = resolveXPositions(values.length, xValues);
  const plotY = (value: number) =>
    span === 0
      ? VIEW_H / 2
      : VIEW_H - PAD_Y - ((value - min) / span) * (VIEW_H - PAD_Y * 2);

  const points: SparkPoint[] = [];
  let gapPending = false;
  values.forEach((value, index) => {
    if (value == null || !Number.isFinite(value)) {
      gapPending = true;
      return;
    }
    points.push({
      x: xPositions[index] ?? 0,
      y: plotY(value),
      gapBefore: points.length === 0 || gapPending,
    });
    gapPending = false;
  });
  const path = points
    .map(
      (point) =>
        `${point.gapBefore ? "M" : "L"}${point.x.toFixed(2)} ${point.y.toFixed(2)}`,
    )
    .join("");
  const lastPoint = points[points.length - 1];

  return (
    <svg
      className={className}
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      preserveAspectRatio="none"
      aria-hidden="true"
      focusable="false"
    >
      {title ? <title>{title}</title> : null}
      <path
        d={path}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
      {endDot && lastPoint ? (
        <circle
          cx={lastPoint.x}
          cy={lastPoint.y}
          r={1.8}
          fill="currentColor"
          stroke="none"
        />
      ) : null}
    </svg>
  );
}
