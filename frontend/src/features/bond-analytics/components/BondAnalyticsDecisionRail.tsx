import { Button, Card, Tag } from "antd";

import type { BondAnalyticsActiveModuleContext, BondAnalyticsReadinessItem } from "../lib/bondAnalyticsOverviewModel";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import { EYEBROW, readinessStatusLabel, readinessSurface, readinessTagColor } from "./bondAnalyticsCockpitTokens";
import styles from "./BondAnalyticsDecisionRail.module.css";

export interface BondAnalyticsDecisionRailProps {
  activeModuleContext: BondAnalyticsActiveModuleContext;
  activeReadinessItem: BondAnalyticsReadinessItem;
  watchlistItems: BondAnalyticsReadinessItem[];
  onOpenModuleDetail: (key: BondAnalyticsModuleKey) => void;
}

export function BondAnalyticsDecisionRail({
  activeModuleContext,
  activeReadinessItem,
  watchlistItems,
  onOpenModuleDetail,
}: BondAnalyticsDecisionRailProps) {
  const activeSurface = readinessSurface(activeReadinessItem.statusLabel);

  return (
    <Card
      size="small"
      data-testid="bond-analysis-decision-rail"
      className={styles.railCard}
      variant="borderless"
    >
      <div className={styles.railBody}>
        <div className={styles.railHeader}>
          <div className={styles.railTitleBlock}>
            <div style={EYEBROW}>决策侧栏</div>
            <div className={styles.railModuleTitle}>{activeModuleContext.label}</div>
          </div>
          <Tag color={readinessTagColor(activeReadinessItem.statusLabel)}>
            {readinessStatusLabel(activeReadinessItem.statusLabel)}
          </Tag>
        </div>

        <div
          data-testid="bond-analysis-decision-trust"
          className={styles.trustPanel}
          style={{
            border: `1px solid ${activeSurface.borderColor}`,
            background: activeSurface.background,
          }}
        >
          <div className={styles.trustKicker} style={{ color: activeSurface.accent }}>
            当前决策上下文
          </div>
          <div className={styles.trustDescription}>{activeModuleContext.description}</div>
          <div className={styles.trustReason} style={{ color: activeSurface.text }}>
            {activeModuleContext.statusReason}
          </div>
        </div>

        <div className={styles.watchlist}>
          <div className={styles.watchlistKicker}>下一步观察项</div>
          {watchlistItems.slice(0, 2).map((item) => (
            <div key={item.key} className={styles.watchlistItem}>
              <div className={styles.watchlistLabel}>{item.label}</div>
              <div className={styles.watchlistReason}>{item.statusReason}</div>
            </div>
          ))}
        </div>

        <Button
          size="small"
          type="default"
          data-testid="bond-analysis-decision-next-action"
          onClick={() => onOpenModuleDetail(activeModuleContext.key)}
        >
          打开当前下钻
        </Button>
      </div>
    </Card>
  );
}
