import { Card } from "antd";

import { designTokens } from "../../../theme/designSystem";
import { displayTokens } from "../../../theme/displayTokens";
import type { BondAnalyticsTruthStrip } from "../lib/bondAnalyticsOverviewModel";
import { EYEBROW, panelStyle, toneColor } from "./bondAnalyticsCockpitTokens";
import styles from "./BondAnalyticsMarketContextStrip.module.css";

const dt = designTokens;
const stripPanelStyle = panelStyle(displayTokens.surface.section);

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
    <Card
      size="small"
      data-testid="bond-analysis-market-context-strip"
      style={stripPanelStyle}
      styles={{ body: { padding: dt.space[4] } }}
    >
      <div className={styles.strip}>
        <div className={styles.stripHeader}>
          <div>
            <div style={EYEBROW}>{truthStrip.title}</div>
            <div className={styles.leadModule} data-testid="bond-analysis-lead-module">
              <span>下钻主线</span>
              <strong>{leadModuleLabel}</strong>
              <span>{leadPromotionLabel}</span>
            </div>
          </div>
        </div>

        <div className={styles.truthStrip} data-testid="bond-analysis-truth-strip">
          {truthStrip.items.map((item) => {
            const colors = toneColor(item.tone);
            return (
              <div
                key={item.key}
                className={styles.truthItem}
                style={{
                  border: `1px solid ${colors.borderColor}`,
                  background: colors.background,
                }}
              >
                <div className={styles.truthLabel} style={{ color: colors.accent }}>
                  {item.label}
                </div>
                <div className={styles.truthValue} style={{ color: colors.color }}>
                  {item.value}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
}
