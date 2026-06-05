import type { HomeMacroBriefingModel } from "../adapters/buildHomeMacroBriefingModel";
import styles from "../dashboardHome.module.css";

type ResearchCalendarSectionProps = {
  macroBriefing: HomeMacroBriefingModel;
};

function releaseImportanceClass(importance: string): string {
  if (importance === "high") {
    return styles.dhMacroReleaseItemHigh ?? "";
  }
  if (importance === "medium") {
    return styles.dhMacroReleaseItemMedium ?? "";
  }
  return "";
}

export function ResearchCalendarSection({ macroBriefing }: ResearchCalendarSectionProps) {
  return (
    <section data-testid="dashboard-home-research-calendar" className={styles.dhCalendarSection}>
      <article className={`${styles.dhCard} ${styles.dhMacroBriefingCard}`}>
        <div className={styles.dhMacroBriefingGrid}>
          <div className={styles.dhMacroBriefingPane}>
            <div className={styles.dhMacroBriefingHeader}>
              <span>重大信息发布日期前瞻</span>
              <small>{macroBriefing.releaseWindowLabel}</small>
            </div>
            {macroBriefing.releaseItems.length > 0 ? (
              <div className={styles.dhMacroBriefingList}>
                {macroBriefing.releaseItems.map((item) => (
                  <a
                    key={item.id}
                    className={`${styles.dhMacroReleaseItem} ${releaseImportanceClass(item.importance)}`}
                    href={item.sourceUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <span className={styles.dhMacroReleaseDate}>
                      <b>{item.dateLabel}</b>
                      <small>{item.daysUntilLabel}</small>
                    </span>
                    <span className={styles.dhMacroReleaseBody}>
                      <span className={styles.dhMacroReleaseTitle}>
                        <span className={styles.dhMacroRegionTag}>{item.region}</span>
                        {item.title}
                      </span>
                      <span className={styles.dhMacroReleaseMetaRow}>
                        <span className={styles.dhMacroBriefingMeta}>
                          {item.timeLabel} · {item.category} · {item.sourceName}
                        </span>
                        <span className={styles.dhMacroImportanceTag}>{item.importanceLabel}</span>
                      </span>
                    </span>
                  </a>
                ))}
              </div>
            ) : (
              <p className={styles.dhMacroBriefingMessage}>{macroBriefing.releaseMessage}</p>
            )}
          </div>

          <div className={styles.dhMacroBriefingPane}>
            <div className={styles.dhMacroBriefingHeader}>
              <span>国内外宏观新闻</span>
              <small>{macroBriefing.newsFreshnessLabel}</small>
            </div>
            <div className={styles.dhMacroTrustStrip} aria-label="宏观新闻数据状态">
              <span>{macroBriefing.newsSourceLabel}</span>
              <span>{macroBriefing.newsAsOfLabel}</span>
              <span>{macroBriefing.newsStatusLabel}</span>
              <span>{macroBriefing.newsRefreshLabel}</span>
            </div>
            {macroBriefing.newsStale ? <span className={styles.dhMacroNewsStale}>新闻源偏旧</span> : null}
            {macroBriefing.newsItems.length > 0 ? (
              <div className={styles.dhMacroBriefingList}>
                {macroBriefing.newsItems.map((item) => (
                  <div key={item.id} className={styles.dhMacroNewsItem}>
                    <span className={styles.dhMacroNewsTopic}>{item.topicLabel}</span>
                    <span className={styles.dhMacroNewsBody}>
                      <span className={styles.dhMacroNewsTitle}>{item.title}</span>
                      <span className={styles.dhMacroBriefingMeta}>{item.timeLabel}</span>
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className={styles.dhMacroBriefingMessage}>{macroBriefing.newsMessage}</p>
            )}
          </div>
        </div>
        <div className={styles.dhMacroSupplyStrip}>
          {macroBriefing.supplyItems.map((item) => (
            <span key={item.id}>{item.label}</span>
          ))}
        </div>
      </article>
    </section>
  );
}
