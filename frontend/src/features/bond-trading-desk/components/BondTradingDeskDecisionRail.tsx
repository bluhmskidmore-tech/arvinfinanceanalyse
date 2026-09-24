import { Link } from "react-router-dom";

import type { BondTradingDeskDecisionItem } from "../lib/bondTradingDeskPageModel";
import styles from "../BondTradingDeskPage.module.css";

export function BondTradingDeskDecisionRail({ items }: { items: BondTradingDeskDecisionItem[] }) {
  return (
    <aside data-testid="bond-trading-desk-decision-rail" className={styles.railCard}>
      <div className={styles.railBody}>
        <div className={styles.railTitle}>下一步核查</div>
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
