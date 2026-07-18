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
  const diagnosticNarratives = summary.diagnostics
    ? [
        { id: "source", text: summary.diagnostics.sourceVerdict },
        { id: "filter", text: summary.diagnostics.filterNarrative },
        { id: "action", text: summary.diagnostics.actionHint },
      ].filter((item): item is { id: string; text: string } => Boolean(item.text)).slice(0, 3)
    : [];
  const releaseHistoryItems = macroBriefing.releaseHistoryItems;
  const visibleReleaseHistoryItems = releaseHistoryItems;

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
        <div className={styles.dhMacroDecisionStrip}>
          <div>
            <span>宏观 / 日历上下文</span>
            <strong>未来事件、政策资金面、供给窗口</strong>
          </div>
          <div className={styles.dhMacroDecisionStats} aria-label="宏观上下文摘要">
            <span>
              <b>{macroBriefing.releaseItems.length}</b>
              <small>发布项</small>
            </span>
            <span>
              <b>{macroBriefing.newsItems.length}</b>
              <small>新闻项</small>
            </span>
            <span>
              <b>{macroBriefing.supplyItems.length}</b>
              <small>供给提示</small>
            </span>
          </div>
        </div>
        <div className={styles.dhMacroBriefingGrid}>
          <div className={`${styles.dhMacroBriefingPane} ${styles.dhMacroReleasePane}`}>
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
            {releaseHistoryItems.length > 0 ||
              macroBriefing.releaseItems.length > 0 ||
              Boolean(macroBriefing.releaseHistoryMessage) ? (
              <details
                className={styles.dhMacroReleaseDisclosure}
                data-testid="dashboard-home-release-history-disclosure"
              >
                <summary className={styles.dhMacroReleaseDisclosureSummary} role="button">
                  <span>过去数据与变动</span>
                  <span className={styles.dhMacroReleaseDisclosureMeta}>
                    <small>
                      {releaseHistoryItems.length > 0
                        ? `共 ${releaseHistoryItems.length} 项`
                        : "暂无可用历史数据"}
                    </small>
                    <span className={styles.dhMacroReleaseDisclosureChevron} aria-hidden="true" />
                  </span>
                </summary>
              <div className={styles.dhMacroReleaseInsight} aria-label="重大信息过往数据与变动">
                <div className={styles.dhMacroReleaseInsightHeader}>
                  <span>过往数据与变动</span>
                  <small>
                    {releaseHistoryItems.length > 0
                      ? `已维护 ${releaseHistoryItems.length} 项`
                      : "历史值待维护"}
                  </small>
                </div>
                {visibleReleaseHistoryItems.length > 0 ? (
                  <div className={styles.dhMacroReleaseHistoryList}>
                    {visibleReleaseHistoryItems.map((item) => (
                      <div
                        key={item.id}
                        className={styles.dhMacroReleaseHistoryRow}
                        data-testid="dashboard-home-release-history-row"
                      >
                        <span className={styles.dhMacroReleaseHistoryTitle}>{item.title}</span>
                        <span className={styles.dhMacroReleaseHistoryMetric}>
                          <small>{item.history.latestLabel}</small>
                          <b>{item.history.latestValue}</b>
                        </span>
                        <span className={styles.dhMacroReleaseHistoryMetric}>
                          <small>{item.history.previousLabel}</small>
                          <b>{item.history.previousValue}</b>
                        </span>
                        <span
                          className={styles.dhMacroReleaseHistoryMetric}
                          data-tone={item.history.changeTone}
                        >
                          <small>{item.history.changeLabel}</small>
                          <b>{item.history.changeValue}</b>
                        </span>
                        {item.history.note || item.history.sourceLabel ? (
                          <p className={styles.dhMacroReleaseHistoryNote}>
                            {item.history.note ? <span>{item.history.note}</span> : null}
                            {item.history.sourceLabel ? <small>{item.history.sourceLabel}</small> : null}
                          </p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className={styles.dhMacroReleaseHistoryMessage}>
                    {macroBriefing.releaseHistoryMessage ?? (
                      <>
                    当前前瞻清单尚未维护历史值与变动。
                      </>
                    )}
                  </p>
                )}
              </div>
              </details>
            ) : null}
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
                {diagnosticNarratives.length > 0 ? (
                  <div
                    className={styles.dhPolicyFundingDiagnosticNarratives}
                    data-tone={summary.diagnostics.narrativeTone}
                    aria-label="政策与资金面诊断说明"
                  >
                    {diagnosticNarratives.map((item) => (
                      <p key={item.id}>{item.text}</p>
                    ))}
                  </div>
                ) : null}
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
