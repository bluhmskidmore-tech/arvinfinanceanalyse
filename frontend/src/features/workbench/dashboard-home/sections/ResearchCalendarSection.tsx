import type { HomeMacroBriefingModel } from "../adapters/buildHomeMacroBriefingModel";
import { formatResearchTitleDisplay } from "../lib/researchTitleDisplay";
import styles from "../dashboardHomeOptionTwoDeferred.module.css";

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

/** 来源长说明只进 title；可见处保留不被截断的短文案。 */
function compactNewsSourceLabel(sourceLabel: string): string {
  const base = sourceLabel.replace(/^来源：/, "").trim();
  if (base.includes("Choice 不可用")) {
    return "来源 Tushare · Choice 回退";
  }
  const head = (base.split("（")[0] ?? base).trim();
  return `来源 ${head || base}`;
}

export function ResearchCalendarSection({
  macroBriefing,
}: ResearchCalendarSectionProps) {
  const summary = macroBriefing.policyFundingSummary;
  const diagnosticNarratives = summary.diagnostics
    ? [
        { id: "source", text: summary.diagnostics.sourceVerdict },
        { id: "filter", text: summary.diagnostics.filterNarrative },
        { id: "action", text: summary.diagnostics.actionHint },
      ]
        .filter((item): item is { id: string; text: string } =>
          Boolean(item.text),
        )
        .slice(0, 3)
    : [];
  const releaseHistoryItems = macroBriefing.releaseHistoryItems;
  const visibleReleaseHistoryItems = releaseHistoryItems;
  // 常态零徽标：仅异常态（偏旧/兜底/错误）保留轻量徽标，中性元信息进悬浮说明。
  const visibleSummaryChips = summary.chips.filter(
    (chip) => chip.tone === "warning" || chip.tone === "danger",
  );
  const newsSourceTooltip = [
    macroBriefing.newsSourceLabel,
    macroBriefing.newsStatusLabel,
    macroBriefing.newsAsOfLabel,
    macroBriefing.newsRefreshLabel,
  ].join(" · ");

  return (
    <section
      data-testid="dashboard-home-research-calendar"
      data-layout-role="research-calendar"
      className={styles.dhCalendarSection}
    >
      <article
        data-layout-role="research-calendar-card"
        className={`${styles.dhCard} ${styles.dhMacroBriefingCard}`}
      >
        <div
          data-layout-role="research-decision-strip"
          className={styles.dhMacroDecisionStrip}
        >
          <div>
            <span>宏观 / 日历上下文</span>
            <strong>未来事件、政策资金面、供给窗口</strong>
          </div>
          <div
            className={styles.dhMacroDecisionStats}
            aria-label="宏观上下文摘要"
          >
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
        <div
          data-layout-role="research-calendar-grid"
          className={styles.dhMacroBriefingGrid}
        >
          <div
            data-layout-role="research-release-pane"
            className={`${styles.dhMacroBriefingPane} ${styles.dhMacroReleasePane}`}
          >
            <div
              data-layout-role="research-release-header"
              className={styles.dhMacroBriefingHeader}
              title={macroBriefing.releaseWindowLabel}
            >
              <span className={styles.dhMacroReleaseLegacyTitle}>
                重大信息发布日期前瞻
              </span>
              {macroBriefing.releaseItems.length > 0 ? (
                <>
                  <span>时间</span>
                  <span>主题 / 事件</span>
                  <span>来源</span>
                  <span>重要性</span>
                </>
              ) : null}
            </div>
            {macroBriefing.releaseItems.length > 0 ? (
              <div
                data-layout-role="research-release-list"
                className={styles.dhMacroBriefingList}
              >
                {macroBriefing.releaseItems.map((item) => (
                  <a
                    key={item.id}
                    data-layout-role="research-release-item"
                    className={`${styles.dhMacroReleaseItem} ${releaseImportanceClass(item.importance)}`}
                    href={item.sourceUrl}
                    target="_blank"
                    rel="noreferrer"
                    title={`${item.title} · ${item.sourceName}`}
                  >
                    <span className={styles.dhMacroReleaseDate}>
                      <b>{item.dateLabel}</b>
                      <small>{item.daysUntilLabel}</small>
                    </span>
                    <span className={styles.dhMacroReleaseBody}>
                      <span
                        className={styles.dhMacroReleaseTitle}
                        title={item.title}
                      >
                        <span className={styles.dhMacroRegionTag}>
                          {item.region}
                        </span>
                        {item.title}
                      </span>
                      <span className={styles.dhMacroReleaseMetaRow}>
                        <span className={styles.dhMacroBriefingMeta}>
                          {item.timeLabel} · {item.category}
                        </span>
                      </span>
                    </span>
                    <span className={styles.dhMacroReleaseSource}>
                      {item.sourceName}
                    </span>
                    <span className={styles.dhMacroImportanceTag}>
                      {item.importanceLabel}
                    </span>
                  </a>
                ))}
              </div>
            ) : (
              <p className={styles.dhMacroBriefingMessage}>
                {macroBriefing.releaseMessage}
              </p>
            )}
            {releaseHistoryItems.length > 0 ||
            macroBriefing.releaseItems.length > 0 ||
            Boolean(macroBriefing.releaseHistoryMessage) ? (
              <details
                className={styles.dhMacroReleaseDisclosure}
                data-testid="dashboard-home-release-history-disclosure"
                data-layout-role="research-release-history"
              >
                <summary
                  className={styles.dhMacroReleaseDisclosureSummary}
                  role="button"
                >
                  <span>更多日历</span>
                  <span className={styles.dhMacroReleaseDisclosureMeta}>
                    <small>{macroBriefing.releaseWindowLabel}</small>
                    <small>
                      {releaseHistoryItems.length > 0
                        ? `共 ${releaseHistoryItems.length} 项`
                        : "暂无历史"}
                    </small>
                    <span
                      className={styles.dhMacroReleaseDisclosureChevron}
                      aria-hidden="true"
                    />
                  </span>
                </summary>
                <div
                  className={styles.dhMacroReleaseInsight}
                  aria-label="重大信息过往数据与变动"
                >
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
                          <span className={styles.dhMacroReleaseHistoryTitle}>
                            {item.title}
                          </span>
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
                              {item.history.note ? (
                                <span>{item.history.note}</span>
                              ) : null}
                              {item.history.sourceLabel ? (
                                <small>{item.history.sourceLabel}</small>
                              ) : null}
                            </p>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className={styles.dhMacroReleaseHistoryMessage}>
                      {macroBriefing.releaseHistoryMessage ?? (
                        <>当前前瞻清单尚未维护历史值与变动。</>
                      )}
                    </p>
                  )}
                </div>
              </details>
            ) : null}
          </div>

          <div
            className={`${styles.dhMacroBriefingPane} ${styles.dhPolicyFundingPane}`}
            data-testid="dashboard-home-policy-funding-pane"
            data-layout-role="research-policy-pane"
          >
            <div className={styles.dhMacroBriefingHeader}>
              <span>政策与资金面</span>
              <small>{macroBriefing.newsFreshnessLabel}</small>
            </div>
            {visibleSummaryChips.length > 0 ? (
              <div
                className={styles.dhPolicyFundingChips}
                aria-label="政策与资金面状态标签"
              >
                {visibleSummaryChips.map((chip) => (
                  <span key={chip.id} data-tone={chip.tone}>
                    {chip.label}
                  </span>
                ))}
              </div>
            ) : null}
            <p className={styles.dhPolicyFundingHeadline}>{summary.headline}</p>
            <div
              className={styles.dhMacroTrustStrip}
              aria-label="政策与资金面数据状态"
              title={newsSourceTooltip}
            >
              <span title={macroBriefing.newsSourceLabel}>
                {compactNewsSourceLabel(macroBriefing.newsSourceLabel)}
              </span>
            </div>
            {summary.diagnostics ? (
              <div
                className={styles.dhPolicyFundingDiagnostics}
                aria-label="政策与资金面数据诊断"
              >
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
          </div>
        </div>
        {summary.groups.length > 0 ? (
          <div
            data-layout-role="research-policy-groups"
            className={styles.dhPolicyFundingGroupsBoard}
          >
            {summary.groups.map((group) => (
              <div key={group.id} className={styles.dhPolicyFundingGroup}>
                <div className={styles.dhPolicyFundingGroupHeader}>
                  <span>{group.label}</span>
                  <small>{group.countLabel}</small>
                </div>
                <div className={styles.dhMacroBriefingList}>
                  {group.items.map((item) => (
                    <div key={item.id} className={styles.dhMacroNewsItem}>
                      <span className={styles.dhMacroNewsTopic}>
                        {item.topicLabel}
                      </span>
                      <span className={styles.dhMacroNewsBody}>
                        <span
                          className={styles.dhMacroNewsTitle}
                          title={item.title}
                        >
                          {formatResearchTitleDisplay(item.title)}
                        </span>
                        <span className={styles.dhMacroBriefingMeta}>
                          {item.timeLabel}
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className={styles.dhMacroBriefingMessage}>
            {macroBriefing.newsMessage}
          </p>
        )}
        <div
          data-layout-role="research-supply-strip"
          className={styles.dhMacroSupplyStrip}
        >
          {macroBriefing.supplyItems.map((item) => (
            <span key={item.id}>{item.label}</span>
          ))}
        </div>
      </article>
    </section>
  );
}
