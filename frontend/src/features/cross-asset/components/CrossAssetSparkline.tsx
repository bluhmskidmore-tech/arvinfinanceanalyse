type Props = {
  values: number[];
  stroke: string;
  height?: number;
};

export function CrossAssetSparkline({ values, stroke, height = 28 }: Props) {
  if (values.length < 2) {
    return <div style={{ height, width: "100%" }} />;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = 2;
  const w = 120;
  const h = height;
  const span = max - min || 1;
  const pts = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (w - pad * 2);
    const y = pad + (1 - (v - min) / span) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return (
    <svg
      width="100%"
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      aria-hidden
      style={{ display: "block" }}
    >
      <polyline fill="none" stroke={stroke} strokeWidth="1.5" points={pts.join(" ")} strokeLinejoin="round" />
    </svg>
  );
}
