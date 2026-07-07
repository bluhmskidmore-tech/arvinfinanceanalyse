import type { HomeBondNewsModel, HomeBondNewsItem } from "../adapters/buildHomeBondNewsModel";
import styles from "../dashboardHome.module.css";

type BondNewsSectionProps = {
  bondNews: HomeBondNewsModel;
};

type BondNewsGroupProps = {
  testId: string;
  title: string;
  count: number;
  items: readonly HomeBondNewsItem[];
  message: string | null;
};

function BondNewsItemRow({ item }: { item: HomeBondNewsItem }) {
  return (
    <div className={styles.dhBondNewsItem}>
      <span className={styles.dhBondNewsTopic}>{item.topicLabel}</span>
      <span className={styles.dhBondNewsBody}>
        <strong>{item.title}</strong>
        <small>
          {item.hitLabel ?? item.sourceLabel} · {item.timeLabel}
        </small>
      </span>
    </div>
  );
}

function BondNewsGroup({ testId, title, count, items, message }: BondNewsGroupProps) {
  const isEmpty = items.length === 0;
  return (
    <div
      data-testid={testId}
      className={`${styles.dhBondNewsGroup} ${isEmpty ? styles.dhBondNewsGroupEmpty : ""}`}
    >
      <div className={styles.dhBondNewsGroupHeader}>
        <span>{title}</span>
        <small>{count} 条</small>
      </div>
      {items.length > 0 ? (
        <div className={styles.dhBondNewsList}>
          {items.map((item) => (
            <BondNewsItemRow key={item.id} item={item} />
          ))}
        </div>
      ) : (
        <p className={styles.dhBondNewsEmptyCompact}>{message}</p>
      )}
    </div>
  );
}

export function BondNewsSection({ bondNews }: BondNewsSectionProps) {
  return (
    <section data-testid="dashboard-home-bond-news" className={styles.dhBondNewsSection}>
      <article className={`${styles.dhCard} ${styles.dhBondNewsCard}`}>
        <div className={styles.dhBondNewsHeader}>
          <div>
            <span>债券信息新闻</span>
          </div>
        </div>
        <div className={styles.dhMacroTrustStrip} aria-label="债券新闻数据状态">
          <span>{bondNews.sourceLabel}</span>
          <span>{bondNews.asOfLabel}</span>
          <span>{bondNews.statusLabel}</span>
          <span>{bondNews.refreshLabel}</span>
        </div>
        <div className={styles.dhBondNewsGrid}>
          <BondNewsGroup
            testId="dashboard-home-bond-news-holding"
            title="持仓命中"
            count={bondNews.holdingHits.length}
            items={bondNews.holdingHits}
            message={bondNews.holdingMessage}
          />
          <BondNewsGroup
            testId="dashboard-home-bond-news-market"
            title="债券市场"
            count={bondNews.marketNews.length}
            items={bondNews.marketNews}
            message={bondNews.marketMessage}
          />
          <BondNewsGroup
            testId="dashboard-home-bond-news-credit"
            title="发行/评级"
            count={bondNews.creditAndIssuanceNews.length}
            items={bondNews.creditAndIssuanceNews}
            message={bondNews.creditMessage}
          />
        </div>
      </article>
    </section>
  );
}
