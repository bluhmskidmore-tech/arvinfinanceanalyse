import { Link } from "react-router-dom";

import { SectionHead } from "../../../components/layout";
import type { BondTradingDeskDecisionItem } from "../lib/bondTradingDeskPageModel";
import styles from "../BondTradingDeskPage.module.css";

export function BondTradingDeskDecisionRail({ items }: { items: BondTradingDeskDecisionItem[] }) {
  return (
    <aside data-testid="bond-trading-desk-decision-rail" className={styles.railCard}>
      <div className={styles.railBody}>
        {/* 卡内面板头：不参与页面编号域，间距交给 railBody 的 12px 栅格。 */}
        <SectionHead title="下一步核查" numbered={false} contentGap="flush" />
        {items.map((item) => (
          <div key={item.key} className={styles.railItem}>
            <Link to={item.href} className={styles.railItemLabel}>
              {item.label}
            </Link>
            <div className={styles.railItemDescription}>{item.description}</div>
          </div>
        ))}
      </div>
    </aside>
  );
}
