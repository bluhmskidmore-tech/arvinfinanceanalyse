import type { BondAnalyticsTruthStrip } from "../lib/bondAnalyticsOverviewModel";
import styles from "./BondAnalyticsMarketContextStrip.module.css";

export interface BondAnalyticsMarketContextStripProps {
  leadModuleLabel: string;
  leadPromotionLabel: string;
  truthStrip: BondAnalyticsTruthStrip;
}

export function BondAnalyticsMarketContextStrip({
  leadModuleLabel,
  leadPromotionLabel,
  truthStrip,
}: BondAnalyticsMarketContextStripProps) {
  return (
    <section data-testid="bond-analysis-market-context-strip" className={styles.contextPanel}>
      <div className={styles.panelHeader}>
        <div className={styles.panelTitle}>{truthStrip.title}</div>
        <div className={styles.leadModule} data-testid="bond-analysis-lead-module">
          <span>下钻主线</span>
          <strong>{leadModuleLabel}</strong>
          <span>{leadPromotionLabel}</span>
        </div>
      </div>

      <div className={styles.truthStrip} data-testid="bond-analysis-truth-strip">
        {truthStrip.items.map((item) => (
          <div key={item.key} className={styles.truthCell} data-tone={item.tone}>
            <span className={styles.truthLabel}>{item.label}</span>
            <strong className={styles.truthValue}>{item.value}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
