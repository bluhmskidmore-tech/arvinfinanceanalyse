import type { CrossAssetKpiBandItem } from "../lib/crossAssetKpiBand";

import "./CrossAssetKpiBand.css";

export type CrossAssetKpiBandProps = {
  items: CrossAssetKpiBandItem[];
};

const UI = {
  sectionLabel: "关键指标横带",
  changePrefix: "日变动",
} as const;

/** 纯 SVG polyline sparkline（stroke currentColor，颜色由卡片 CSS 给定）。 */
function KpiBandSparkline({ values }: { values: number[] }) {
  if (values.length < 2) {
    return null;
  }
  const width = 72;
  const height = 24;
  const pad = 2;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values.map((value, index) => {
    const x = pad + (index / (values.length - 1)) * (width - pad * 2);
    const y = pad + (1 - (value - min) / span) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return (
    <svg
      className="cross-asset-kpi-band__spark"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      aria-hidden
    >
      <polyline
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        points={points.join(" ")}
      />
    </svg>
  );
}

export function CrossAssetKpiBand({ items }: CrossAssetKpiBandProps) {
  return (
    <section className="cross-asset-kpi-band" data-testid="cross-asset-kpi-band" aria-label={UI.sectionLabel}>
      {items.map((item) => (
        <article
          key={item.key}
          className="cross-asset-kpi-band__card"
          data-testid={`cross-asset-kpi-band-${item.key}`}
        >
          <header className="cross-asset-kpi-band__card-head">
            <span className="cross-asset-kpi-band__name">{item.label}</span>
            <span className={`cross-asset-kpi-band__badge cross-asset-kpi-band__badge--${item.impact}`}>
              {item.impactLabel}
            </span>
          </header>
          <div className="cross-asset-kpi-band__value-row">
            <span className="cross-asset-kpi-band__value">{item.valueLabel}</span>
            {item.unit ? <span className="cross-asset-kpi-band__unit">{item.unit}</span> : null}
          </div>
          <div className="cross-asset-kpi-band__change">
            {UI.changePrefix} {item.changeLabel}
          </div>
          <div className="cross-asset-kpi-band__foot">
            <span className="cross-asset-kpi-band__source">
              {item.sourceLabel} · {item.dateLabel}
            </span>
            <KpiBandSparkline values={item.spark} />
          </div>
        </article>
      ))}
    </section>
  );
}
