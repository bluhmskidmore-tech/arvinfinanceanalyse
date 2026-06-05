import { useEffect, useRef } from "react";

import type { HomeMacroBriefingModel } from "../adapters/buildHomeMacroBriefingModel";
import styles from "../dashboardHome.module.css";

type ResearchCalendarSectionProps = {
  macroBriefing: HomeMacroBriefingModel;
  focusPolicyFunding?: boolean;
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

export function ResearchCalendarSection({
  macroBriefing,
  focusPolicyFunding = false,
}: ResearchCalendarSectionProps) {
  const policyFundingPaneRef = useRef<HTMLDivElement | null>(null);
  const summary = macroBriefing.policyFundingSummary;

  useEffect(() => {
    if (!focusPolicyFunding) {
      return;
    }

    const pane = policyFundingPaneRef.current;
    pane?.scrollIntoView?.({ block: "start" });
    pane?.focus({ preventScroll: true });
  }, [focusPolicyFunding, summary.headline]);

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

          <div
            ref={policyFundingPaneRef}
            className={`${styles.dhMacroBriefingPane} ${styles.dhPolicyFundingPane}`}
            data-focused={focusPolicyFunding ? "true" : "false"}
            data-testid="dashboard-home-policy-funding-pane"
            tabIndex={-1}
          >
            <div className={styles.dhMacroBriefingHeader}>
              <span>政策与资金面</span>
              <small>{macroBriefing.newsFreshnessLabel}</small>
            </div>
            <div className={styles.dhPolicyFundingChips} aria-label="政策与资金面状态标签">
              {summary.chips.map((chip) => (
                <span key={chip.id} data-tone={chip.tone}>
                  {chip.label}
                </span>
              ))}
            </div>
            <p className={styles.dhPolicyFundingHeadline}>{summary.headline}</p>
            <div className={styles.dhMacroTrustStrip} aria-label="政策与资金面数据状态">
              <span>{macroBriefing.newsSourceLabel}</span>
              <span>{macroBriefing.newsAsOfLabel}</span>
              <span>{macroBriefing.newsStatusLabel}</span>
              <span>{macroBriefing.newsRefreshLabel}</span>
            </div>
            {summary.diagnostics ? (
              <div className={styles.dhPolicyFundingDiagnostics} aria-label="政策与资金面数据诊断">
                <div className={styles.dhPolicyFundingDiagnosticsHeader}>
                  <span>数据诊断</span>
                  <small>{summary.diagnostics.summary}</small>
                </div>
                <div className={styles.dhPolicyFundingDiagnosticMetrics}>
                  {summary.diagnostics.metrics.map((metric) => (
                    <span key={metric.id} data-tone={metric.tone}>
                      <small>{metric.label}</small>
                      <b>{metric.value}</b>
                    </span>
                  ))}
                </div>
                {summary.diagnostics.emptyHint ? (
                  <p className={styles.dhPolicyFundingDiagnosticHint}>
                    {summary.diagnostics.emptyHint}
                  </p>
                ) : null}
                {summary.diagnostics.reasons.length > 0 ? (
                  <div className={styles.dhPolicyFundingDiagnosticReasons}>
                    {summary.diagnostics.reasons.map((reason) => (
                      <span key={reason.id} data-tone={reason.tone}>
                        {reason.label}
                        <b>{reason.countLabel}</b>
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
            {macroBriefing.newsStale ? <span className={styles.dhMacroNewsStale}>新闻源偏旧</span> : null}
            {summary.groups.length > 0 ? (
              <div className={styles.dhPolicyFundingGroups}>
                {summary.groups.map((group) => (
                  <div key={group.id} className={styles.dhPolicyFundingGroup}>
                    <div className={styles.dhPolicyFundingGroupHeader}>
                      <span>{group.label}</span>
                      <small>{group.countLabel}</small>
                    </div>
                    <div className={styles.dhMacroBriefingList}>
                      {group.items.map((item) => (
                        <div key={item.id} className={styles.dhMacroNewsItem}>
                          <span className={styles.dhMacroNewsTopic}>{item.topicLabel}</span>
                          <span className={styles.dhMacroNewsBody}>
                            <span className={styles.dhMacroNewsTitle}>{item.title}</span>
                            <span className={styles.dhMacroBriefingMeta}>{item.timeLabel}</span>
                          </span>
                        </div>
                      ))}
                    </div>
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
