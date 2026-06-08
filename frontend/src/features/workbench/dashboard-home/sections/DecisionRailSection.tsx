import { Link } from "react-router-dom";

import type { ResultMeta } from "../../../../api/contracts";
import { LightIcon } from "../../../../components/LightIcon";
import type {
  DashboardHomeFirstScreenView,
  HomeDecisionAction,
} from "../dashboardHomeFirstScreenTypes";
import styles from "../dashboardHomeShell.module.css";

type DecisionRailSectionProps = {
  decisionRail: DashboardHomeFirstScreenView["decisionRail"];
  reportDate: string;
  dataSyncPrefix: string;
  dataStatusKind: DashboardHomeFirstScreenView["headerStatus"]["dataStatusKind"];
  snapshotMeta?: ResultMeta | null;
};

const GAP = "—";

function formatSourceSurfaceLabel(surface: string | null | undefined): string {
  if (!surface) {
    return "主快照来源未返回";
  }
  if (surface === "executive_analytical") {
    return "经营主快照（分析读面）";
  }
  if (surface === "formal_balance") {
    return "正式余额读面";
  }
  return surface;
}

function hasRailText(value: string | null | undefined): boolean {
  const trimmed = value?.trim();
  return Boolean(trimmed && trimmed !== GAP && trimmed !== "--");
}

function formatRailUpdatedAt(
  statusKind: DashboardHomeFirstScreenView["headerStatus"]["dataStatusKind"],
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

function DecisionActionItem({ action }: { action: HomeDecisionAction }) {
  const className = [
    styles.dhDecisionAction,
    action.to ? styles.dhDecisionActionLink : styles.dhDecisionActionDisabled,
  ]
    .filter(Boolean)
    .join(" ");
  const content = (
    <>
      <span className={styles.dhDecisionActionMeta}>{action.sourceLabel}</span>
      <span className={styles.dhDecisionActionText}>
        <b>{action.title}</b>
        <small>{action.reason}</small>
      </span>
      {action.to ? <LightIcon name="arrow-right" /> : <LightIcon name="warning" />}
    </>
  );

  if (action.to) {
    return (
      <Link
        className={className}
        data-priority={action.priority}
        data-status-kind={action.statusKind}
        data-testid={`dashboard-home-decision-action-${action.id}`}
        to={action.to}
      >
        {content}
      </Link>
    );
  }

  return (
    <div
      aria-disabled="true"
      className={className}
      data-priority={action.priority}
      data-status-kind={action.statusKind}
      data-testid={`dashboard-home-decision-action-${action.id}`}
    >
      {content}
    </div>
  );
}

function formatBasisLabel(meta: ResultMeta | null | undefined): string {
  if (!meta) {
    return "快照元数据未返回";
  }
  if (meta.basis === "formal" && meta.formal_use_allowed) {
    return "正式口径已放行";
  }
  if (meta.basis === "formal") {
    return "正式口径待放行";
  }
  if (meta.basis === "analytical") {
    return "分析读面";
  }
  if (meta.basis === "scenario") {
    return "情景读面";
  }
  if (meta.basis === "mock") {
    return "演示读面";
  }
  return meta.basis;
}

function formatQualityLabel(meta: ResultMeta | null | undefined): string {
  if (!meta) {
    return "质量状态未返回";
  }
  const quality = meta.quality_flag === "ok" ? "质量正常" : `质量 ${meta.quality_flag}`;
  const fallback = meta.fallback_mode === "none" ? "无降级" : `降级 ${meta.fallback_mode}`;
  return `${quality} · ${fallback}`;
}

export function DecisionRailSection({
  decisionRail,
  reportDate,
  dataSyncPrefix,
  dataStatusKind,
  snapshotMeta,
}: DecisionRailSectionProps) {
  const railUpdatedAt = formatRailUpdatedAt(
    dataStatusKind,
    reportDate,
    decisionRail.dataUpdatedAt,
  );
  const hasDrag = hasRailText(decisionRail.maxDragValue);
  const hasContribution = hasRailText(decisionRail.maxContributionValue);
  const hasKeyRisk = hasRailText(decisionRail.keyRisk);

  return (
    <aside data-testid="dashboard-home-decision-rail" className={styles.dhRail}>
      <article className={styles.dhReviewRail}>
        <div className={styles.dhReviewRailHead}>
          <span>复核记录</span>
          <b className={styles.dhNum}>{reportDate}</b>
        </div>

        <dl className={styles.dhReviewList}>
          <div className={styles.dhReviewListPrimary}>
            <dt>摘录</dt>
            <dd>{decisionRail.conclusion}</dd>
          </div>

          <div>
            <dt>依据</dt>
            <dd>{hasKeyRisk ? decisionRail.keyRisk : "主快照未返回可摘录依据"}</dd>
          </div>

          {hasDrag || hasContribution ? (
            <div>
              <dt>贡献 / 拖累</dt>
              <dd className={styles.dhReviewPairList}>
            {hasDrag ? (
              <span>
                最大拖累：{decisionRail.maxDragLabel}{" "}
                <b className={`${styles.dhNum} ${styles.dhUpRed}`}>{decisionRail.maxDragValue}</b>
              </span>
            ) : null}
            {hasContribution ? (
              <span>
                最大贡献：{decisionRail.maxContributionLabel}{" "}
                <b className={`${styles.dhNum} ${styles.dhDownGreen}`}>
                  {decisionRail.maxContributionValue}
                </b>
              </span>
            ) : null}
              </dd>
            </div>
          ) : null}

          <div>
            <dt>入口</dt>
            <dd>
              {decisionRail.actions.length > 0 ? (
                <div className={styles.dhReviewActionList}>
                  {decisionRail.actions.map((action) => (
                    <DecisionActionItem key={action.id} action={action} />
                  ))}
                </div>
              ) : (
                <ol className={styles.dhSuggestionList}>
                  {decisionRail.suggestions.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ol>
              )}
            </dd>
          </div>

          <div>
            <dt>待办</dt>
            <dd className={styles.dhNum}>{decisionRail.pendingSummary}</dd>
          </div>
        </dl>
      </article>

      <article className={styles.dhDataNote}>
        <h3>来源台账</h3>
        <p>来源：{formatSourceSurfaceLabel(snapshotMeta?.source_surface)}</p>
        <p>口径：{formatBasisLabel(snapshotMeta)}</p>
        <p>质量：{formatQualityLabel(snapshotMeta)}</p>
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
          {dataSyncPrefix} · 主快照读数
        </p>
      </article>
    </aside>
  );
}
