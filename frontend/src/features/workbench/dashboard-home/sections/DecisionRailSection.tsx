import {
  ArrowRightOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  BulbOutlined,
  CheckCircleFilled,
  CheckSquareOutlined,
  ExclamationCircleFilled,
  FileTextOutlined,
  ThunderboltFilled,
  UnorderedListOutlined,
} from "@ant-design/icons";

import type { DashboardHomeView } from "../dashboardHomeView";
import styles from "../dashboardHome.module.css";

type DecisionRailSectionProps = {
  decisionRail: DashboardHomeView["decisionRail"];
  reportDate: string;
  dataSyncPrefix: string;
  dataStatusKind: DashboardHomeView["headerStatus"]["dataStatusKind"];
};

function formatRailUpdatedAt(
  statusKind: DashboardHomeView["headerStatus"]["dataStatusKind"],
  reportDate: string,
  updatedAt: string,
) {
  if (statusKind === "error") {
    return "—";
  }
  if (statusKind === "stale") {
    return `沿用报告日 ${reportDate}`;
  }
  return `${reportDate} ${updatedAt}`.trim();
}

export function DecisionRailSection({
  decisionRail,
  reportDate,
  dataSyncPrefix,
  dataStatusKind,
}: DecisionRailSectionProps) {
  const SyncStatusIcon = dataStatusKind === "ok" ? CheckCircleFilled : ExclamationCircleFilled;
  const railUpdatedAt = formatRailUpdatedAt(
    dataStatusKind,
    reportDate,
    decisionRail.dataUpdatedAt,
  );

  return (
    <aside data-testid="dashboard-home-decision-rail" className={styles.dhRail}>
      <article className={`${styles.dhCard} ${styles.dhDecision}`}>
        <div className={styles.dhDecisionTitle}>
          <span className={styles.dhDecisionIcon}>
            <ThunderboltFilled />
          </span>
          <span>AI 决策舱</span>
        </div>

        <div className={styles.dhAiCard}>
          <div className={styles.dhAiCardHead}>
            <BulbOutlined />
            <span>今日结论</span>
          </div>
          <p>{decisionRail.conclusion}</p>
        </div>

        <div className={`${styles.dhAiCard} ${styles.dhAiCardMetric}`}>
          <span className={`${styles.dhRailIcon} ${styles.dhUpRed}`}>
            <ArrowDownOutlined />
          </span>
          <div>
            <b>最大拖累</b>
            <p>
              {decisionRail.maxDragLabel}{" "}
              <span className={`${styles.dhNum} ${styles.dhUpRed}`}>{decisionRail.maxDragValue}</span>
            </p>
          </div>
        </div>

        <div className={`${styles.dhAiCard} ${styles.dhAiCardMetric}`}>
          <span className={`${styles.dhRailIcon} ${styles.dhDownGreen}`}>
            <ArrowUpOutlined />
          </span>
          <div>
            <b>最大贡献</b>
            <p>
              {decisionRail.maxContributionLabel}{" "}
              <span className={`${styles.dhNum} ${styles.dhDownGreen}`}>
                {decisionRail.maxContributionValue}
              </span>
            </p>
          </div>
        </div>

        <div className={`${styles.dhAiCard} ${styles.dhAiCardMetric}`}>
          <span className={`${styles.dhRailIcon} ${styles.dhRailIconBlue}`}>
            <ExclamationCircleFilled />
          </span>
          <div>
            <b>关键风险</b>
            <p>{decisionRail.keyRisk}</p>
          </div>
        </div>

        <div className={styles.dhAiCard}>
          <div className={styles.dhAiCardHead}>
            <CheckSquareOutlined />
            <span>建议动作</span>
          </div>
          <ol className={styles.dhSuggestionList}>
            {decisionRail.suggestions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        </div>

        <div className={`${styles.dhAiCard} ${styles.dhAiCardMetric}`}>
          <span className={`${styles.dhRailIcon} ${styles.dhRailIconBlue}`}>
            <UnorderedListOutlined />
          </span>
          <div>
            <b>待处理事项</b>
            <p>{decisionRail.pendingSummary}</p>
          </div>
        </div>

        <button type="button" className={styles.dhReportBtn}>
          <FileTextOutlined /> 生成完整经营报告 <ArrowRightOutlined />
        </button>
      </article>

      <article className={`${styles.dhCard} ${styles.dhCardSecondary} ${styles.dhDataNote}`}>
        <h3>数据说明</h3>
        <p>数据来源：交易系统、估值系统、风险系统等</p>
        <p>
          更新时间：
          <span className={styles.dhNum} data-testid="dashboard-home-rail-updated-at">
            {railUpdatedAt}
          </span>
        </p>
        <p
          data-testid="dashboard-home-rail-data-status"
          data-status-kind={dataStatusKind}
          className={dataStatusKind === "ok" ? styles.dhDataNoteOk : styles.dhDataNoteWarning}
        >
          <SyncStatusIcon /> {dataSyncPrefix} · 页面数据以后端 API 为准
        </p>
      </article>
    </aside>
  );
}
