import { Link } from "react-router-dom";

import type { DashboardHomeView } from "../dashboardHomeView";
import { resolveDeltaClass } from "../dashboardHomeView";
import { HomeSparkline } from "../HomeSparkline";
import styles from "../dashboardHome.module.css";

type MarketTapeSectionProps = {
  items: DashboardHomeView["marketTape"];
};

export function MarketTapeSection({ items }: MarketTapeSectionProps) {
  if (items.length === 0) {
    return (
      <section data-testid="dashboard-home-market" className={`${styles.dhCard} ${styles.dhMarket}`}>
        <div className={styles.dhSectionTitle}>
          <span>市场行情磁带</span>
          <Link to="/market-data" className={styles.dhLink}>
            更多市场数据 →
          </Link>
        </div>
        <p className={styles.dhEmpty}>市场数据待同步</p>
      </section>
    );
  }

  return (
    <section data-testid="dashboard-home-market" className={`${styles.dhCard} ${styles.dhMarket}`}>
      <div className={styles.dhSectionTitle}>
        <span>市场行情磁带</span>
        <Link to="/market-data" className={styles.dhLink}>
          更多市场数据 →
        </Link>
      </div>
      <div className={styles.dhTickerRow}>
        {items.map((ticker) => (
          <div key={ticker.id} className={styles.dhTicker}>
            <div className={styles.dhTickerName}>{ticker.label}</div>
            <div className={`${styles.dhTickerVal} ${styles.dhNum}`}>{ticker.value}</div>
            <div className={`${styles.dhTickerChg} ${resolveDeltaClass(ticker.deltaTone, styles)}`}>
              {ticker.delta}
            </div>
            <HomeSparkline
              values={ticker.sparkline}
              width={52}
              height={24}
              stroke={ticker.deltaTone === "down" ? "#197a5a" : "#d72222"}
              className={styles.dhTickerLine}
            />
          </div>
        ))}
      </div>
    </section>
  );
}
