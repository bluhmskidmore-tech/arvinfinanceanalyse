import { Button } from "antd";

import type { BondAnalyticsActiveModuleContext, BondAnalyticsReadinessItem } from "../lib/bondAnalyticsOverviewModel";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import { readinessStatusLabel } from "./bondAnalyticsCockpitTokens";
import styles from "./BondAnalyticsDecisionRail.module.css";

/** 与 `readinessTagColor` 同一状态语义，改用页面 tone 词汇替代 antd Tag 预设色。 */
function readinessTone(statusLabel: string) {
  if (statusLabel === "eligible") return "positive";
  if (statusLabel === "request-error") return "negative";
  if (statusLabel === "placeholder-blocked" || statusLabel === "warning") return "warning";
  return "neutral";
}

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
  const tone = readinessTone(activeReadinessItem.statusLabel);

  return (
    <section data-testid="bond-analysis-decision-rail" className={styles.railCard}>
      <div className={styles.railBody}>
        <div className={styles.railHeader}>
          <div className={styles.railTitleBlock}>
            <div className={styles.railEyebrow}>决策侧栏</div>
            <div className={styles.railModuleTitle}>{activeModuleContext.label}</div>
          </div>
          <span className={styles.railStatus} data-tone={tone}>
            <i aria-hidden="true" />
            {readinessStatusLabel(activeReadinessItem.statusLabel)}
          </span>
        </div>

        <div
          data-testid="bond-analysis-decision-trust"
          className={styles.trustPanel}
          data-tone={tone}
        >
          <div className={styles.trustKicker}>当前决策上下文</div>
          <div className={styles.trustDescription}>{activeModuleContext.description}</div>
          <div className={styles.trustReason}>{activeModuleContext.statusReason}</div>
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
          className={styles.railAction}
          data-testid="bond-analysis-decision-next-action"
          onClick={() => onOpenModuleDetail(activeModuleContext.key)}
        >
          打开当前下钻
        </Button>
      </div>
    </section>
  );
}
