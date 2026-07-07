import { Link } from "react-router-dom";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import type { MarketDeskIntelView } from "./moduleHomeModel";
import marketStyles from "./marketHome.module.css";

type MarketDeskIntelStripProps = {
  intel: MarketDeskIntelView | null | undefined;
};

function toneClass(tone: "ok" | "watch" | "error" | "muted") {
  if (tone === "watch") return dhStyles.dhMuted;
  if (tone === "error") return dhStyles.dhUpRed;
  return "";
}

export function MarketDeskIntelStrip({ intel }: MarketDeskIntelStripProps) {
  if (!intel) {
    return null;
  }

  const hasCurve = Boolean(intel.curveShapeLabel || intel.curveInterpretation);
  const hasIndicators = intel.indicators.length > 0;

  if (!hasCurve && !hasIndicators) {
    return null;
  }

  return (
    <section
      className={`${dhStyles.dhCard} ${marketStyles.marketDeskIntelStrip} ${marketStyles.marketDeskPanel}`}
      data-testid="module-home-market-desk-intel"
    >
      <header className={marketStyles.marketDeskIntelHead}>
        <div>
          <span className={marketStyles.marketSummaryKicker}>DESK</span>
          <h3 className={marketStyles.marketDeskIntelTitle}>市场读数 · 曲线形态与工具指标</h3>
        </div>
        <Link to="/macro-toolkit" className={marketStyles.marketIbLink}>
          指标明细 →
        </Link>
      </header>
      <div className={marketStyles.marketDeskIntelGrid}>
        {hasCurve ? (
          <article className={marketStyles.marketDeskIntelCurveCard} data-testid="module-home-market-desk-curve-shape">
            <span className={marketStyles.marketDeskIntelCardKicker}>曲线形态</span>
            <strong className={`${marketStyles.marketDeskIntelCurveShape} ${marketStyles.marketCurveSpreadBandTitle}`}>
              {intel.curveShapeLabel ?? intel.curveShape ?? "待返回"}
            </strong>
            {intel.spread10y1yBp !== null ? (
              <span className={`${dhStyles.dhNum} ${marketStyles.marketDeskIntelMetric}`}>
                10Y-1Y {intel.spread10y1yBp.toFixed(1)} bp
              </span>
            ) : null}
            {intel.curvePercentile1y !== null ? (
              <span className={`${dhStyles.dhNum} ${marketStyles.marketDeskIntelMetric}`}>
                1Y分位 P{intel.curvePercentile1y.toFixed(1)}
              </span>
            ) : null}
            {intel.curveInterpretation ? (
              <p className={marketStyles.marketDeskIntelInterpretation}>{intel.curveInterpretation}</p>
            ) : null}
          </article>
        ) : null}
        {hasIndicators ? (
          <div className={marketStyles.marketDeskIntelIndicatorGrid} data-testid="module-home-market-desk-indicators">
            {intel.indicators.map((item) => (
              <article className={marketStyles.marketDeskIntelIndicatorCard} data-testid={`module-home-market-desk-indicator-${item.key}`} key={item.key}>
                <span className={marketStyles.marketDeskIntelCardKicker}>{item.group}</span>
                <span className={marketStyles.marketDeskIntelIndicatorLabel}>{item.label}</span>
                <strong className={`${dhStyles.dhNum} ${marketStyles.marketMetricNum} ${toneClass(item.tone)}`}>{item.value}</strong>
              </article>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}
