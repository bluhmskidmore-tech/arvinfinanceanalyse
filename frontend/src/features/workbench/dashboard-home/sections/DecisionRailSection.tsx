import { Link } from "react-router-dom";

import type { ResultMeta } from "../../../../api/contracts";
import type {
  DashboardHomeFirstScreenView,
  HomeReportDateContext,
} from "../dashboardHomeFirstScreenTypes";
import {
  hasReportDateDivergence,
  reportDateContextLabel,
} from "../homeReportDateLabel";
import styles from "../dashboardHomeShell.module.css";

type DecisionRailSectionProps = {
  decisionRail: DashboardHomeFirstScreenView["decisionRail"];
  reportDate: string;
  dataSyncPrefix: string;
  dataStatusKind: DashboardHomeFirstScreenView["headerStatus"]["dataStatusKind"];
  snapshotMeta?: ResultMeta | null;
  reportDateContext: HomeReportDateContext;
  missingDomains?: DashboardHomeFirstScreenView["missingDomains"];
};

type RailTone = "success" | "warning" | "danger" | "neutral";

function statusTone(kind: DashboardHomeFirstScreenView["headerStatus"]["dataStatusKind"] | "ready"): RailTone {
  if (kind === "ok" || kind === "ready") return "success";
  if (kind === "partial" || kind === "fallback" || kind === "stale") return "warning";
  if (kind === "error") return "danger";
  return "neutral";
}

function RailStatusPill({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: RailTone;
}) {
  return (
    <span className={styles.dhRailStatusPill} data-tone={tone}>
      <i aria-hidden="true" />
      <span>{children}</span>
    </span>
  );
}

function RailCard({
  testId,
  title,
  status,
  children,
}: {
  testId: string;
  title: string;
  status?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section
      data-testid={testId}
      className={`${styles.dhCard} ${styles.dhRailCard} ${styles.dhSurfaceCard}`}
    >
      <div className={styles.dhRailCardBody}>
        <div className={styles.dhRailCardHeader}>
          <h2>{title}</h2>
          {status ? <span className={styles.dhRailHeaderStatus}>{status}</span> : null}
        </div>
        {children}
      </div>
    </section>
  );
}

function RailMessage({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: RailTone;
}) {
  return (
    <div className={styles.dhRailMessage} data-tone={tone} role="status">
      {children}
    </div>
  );
}

function actionPriorityLabel(
  priority: DashboardHomeFirstScreenView["decisionRail"]["actions"][number]["priority"],
): string {
  if (priority === "high") return "高";
  if (priority === "medium") return "中";
  return "低";
}

function RailEvidenceRow({
  label,
  value,
  status,
  tone = "neutral",
  testId,
  statusKind,
}: {
  label: string;
  value: React.ReactNode;
  status?: boolean;
  tone?: RailTone;
  testId?: string;
  statusKind?: DashboardHomeFirstScreenView["headerStatus"]["dataStatusKind"];
}) {
  return (
    <div
      className={styles.dhRailEvidenceRow}
      data-testid={testId}
      data-status-kind={statusKind}
    >
      <span>{label}</span>
      {status ? (
        <RailStatusPill tone={tone}>{value}</RailStatusPill>
      ) : (
        <strong>{value}</strong>
      )}
    </div>
  );
}

function railUpdatedAtLabel(args: {
  dataStatusKind: DashboardHomeFirstScreenView["headerStatus"]["dataStatusKind"];
  dataSyncPrefix: string;
  reportDate: string;
  dataUpdatedAt: string;
}): string {
  if (args.dataStatusKind === "error") {
    return "—";
  }
  if (args.dataStatusKind === "loading") {
    return "读取中";
  }
  if (args.dataStatusKind === "stale") {
    return `沿用报告日 ${args.reportDate}`;
  }
  return `${args.reportDate} ${args.dataUpdatedAt || "16:00"}`;
}

function hasDisplayText(value: string | null | undefined): boolean {
  const trimmed = value?.trim();
  return Boolean(trimmed && trimmed !== "—" && trimmed !== "--");
}

function formatSnapshotGeneratedAt(snapshotMeta: ResultMeta | null | undefined): string {
  const generatedAt = snapshotMeta?.generated_at?.trim();
  if (!generatedAt) {
    return "暂无";
  }
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(generatedAt);
  return match ? `${match[1]} ${match[2]}` : generatedAt;
}

function sourceLedgerStatusLabel(
  dataStatusKind: DashboardHomeFirstScreenView["headerStatus"]["dataStatusKind"],
  dataSyncPrefix: string,
  snapshotMeta: ResultMeta | null | undefined,
): string {
  if (dataStatusKind === "error") return dataSyncPrefix;
  if (dataStatusKind === "loading") return "读取中";
  if (dataStatusKind === "fallback") return "回退链路";
  if (dataStatusKind === "stale") return "偏旧";
  if (dataStatusKind === "partial") return dataSyncPrefix;
  if (!snapshotMeta) return "暂无受管来源元数据";
  if (snapshotMeta.fallback_mode && snapshotMeta.fallback_mode !== "none") return "回退链路";
  if (snapshotMeta.quality_flag === "warning") return "需复核";
  return "与快照一致";
}

export function DecisionRailSection({
  decisionRail,
  reportDate,
  dataSyncPrefix,
  dataStatusKind,
  snapshotMeta,
  reportDateContext,
  missingDomains = [],
}: DecisionRailSectionProps) {
  const isError = dataStatusKind === "error";
  const isLoading = dataStatusKind === "loading";
  const hasNoSnapshot = reportDateContext.mode === "empty";
  const snapshotGeneratedAt = formatSnapshotGeneratedAt(snapshotMeta);
  const railUpdatedAt = hasNoSnapshot
    ? "暂无"
    : snapshotGeneratedAt !== "暂无"
      ? snapshotGeneratedAt
      : railUpdatedAtLabel({
          dataStatusKind,
          dataSyncPrefix,
          reportDate,
          dataUpdatedAt: decisionRail.dataUpdatedAt,
        });
  const missingDomainText = missingDomains
    .map((domain) => `${domain.label}（${domain.id}）`)
    .join("、");
  const pendingSummary = hasDisplayText(decisionRail.pendingSummary)
    ? decisionRail.pendingSummary
    : "暂无";
  const statusLabel = hasNoSnapshot
    ? "暂无可用快照"
    : sourceLedgerStatusLabel(dataStatusKind, dataSyncPrefix, snapshotMeta);
  const formalUseAllowed =
    dataStatusKind === "ok" && snapshotMeta?.formal_use_allowed === true;
  const dateDivergent = hasReportDateDivergence(reportDateContext);
  const sourceLedgerRows: Array<{
    label: string;
    value: string;
    status?: boolean;
    tone?: RailTone;
    testId?: string;
  }> = [
    {
      label: "报告日",
      value: reportDateContextLabel(reportDateContext),
      status: dateDivergent,
      tone: dateDivergent ? "warning" : "neutral",
      testId: "dashboard-home-rail-report-date",
    },
    {
      label: "来源",
      value: snapshotMeta ? "首页快照" : "暂无受管来源元数据",
    },
    {
      label: "口径",
      value: snapshotMeta?.basis?.trim() || dataSyncPrefix,
    },
    {
      label: "用途",
      value: snapshotMeta ? (formalUseAllowed ? "正式经营决策" : "复核参考") : "待来源确认",
    },
    {
      label: "更新时间",
      value: snapshotMeta ? formatSnapshotGeneratedAt(snapshotMeta) : railUpdatedAt,
    },
    {
      label: "数据状态",
      value: statusLabel,
      status: true,
      tone: statusTone(dataStatusKind === "ok" ? "ready" : dataStatusKind),
    },
  ];

  return (
    <aside
      data-testid="dashboard-home-decision-rail"
      className={styles.dhRail}
      aria-label="决策复核与数据质量"
    >
      <RailCard
        testId="dashboard-home-review-entry-card"
        title="待复核"
        status={
          <RailStatusPill tone={pendingSummary === "暂无" ? "neutral" : "danger"}>
            {pendingSummary}
          </RailStatusPill>
        }
      >
        {isError ? (
          <RailMessage tone="danger">
            数据读取失败：主快照未取得。刷新重试；持续失败请到「平台配置」查看服务状态。
          </RailMessage>
        ) : isLoading ? (
          <RailMessage>读取中，待主快照返回。</RailMessage>
        ) : (
          <div className={styles.dhRailActionList}>
            {decisionRail.actions.map((action) => (
              <div
                key={action.id}
                className={styles.dhRailActionRow}
                data-testid="dashboard-home-decision-action-row"
              >
                {action.to ? (
                  <Link
                    to={action.to}
                    data-testid={`dashboard-home-decision-action-${action.id}`}
                  >
                    {action.title}
                  </Link>
                ) : (
                  <span data-testid={`dashboard-home-decision-action-${action.id}`}>
                    {action.title}
                  </span>
                )}
                <span>{action.reason}</span>
                <span className={styles.dhRailActionMeta}>
                  <span>{`来源：${action.sourceLabel}`}</span>
                  <span>{`优先级：${actionPriorityLabel(action.priority)}`}</span>
                  <span>{action.statusKind === "ready" ? "可执行" : "待接入"}</span>
                </span>
                <span className={styles.dhRailActionOwnership}>
                  <span>负责人待接入</span>
                  <span>截止时间未维护</span>
                </span>
              </div>
            ))}
            <div className={styles.dhRailMutedNote}>
              暂无复核日志接口：当前未接入此模块，需要时到「平台配置」启用。
            </div>
          </div>
        )}
      </RailCard>

      <RailCard
        testId="dashboard-home-action-queue-card"
        title="决策建议"
        status={<RailStatusPill tone="neutral">建议</RailStatusPill>}
      >
        {isError ? (
          <RailMessage tone="danger">
            数据读取失败：决策建议无法展示。刷新后重试。
          </RailMessage>
        ) : isLoading ? (
          <RailMessage>读取中。</RailMessage>
        ) : (
          <ul className={styles.dhRailSuggestionList}>
            {decisionRail.suggestions.map((item) => (
              <li key={item.id}>
                {item.to ? (
                  <Link to={item.to}>{item.text}</Link>
                ) : (
                  item.text
                )}
              </li>
            ))}
            {decisionRail.suggestions.length === 0 && (
              <li>暂无决策建议：主链路未下发新增建议。</li>
            )}
          </ul>
        )}
      </RailCard>

      <RailCard
        testId="dashboard-home-data-quality-card"
        title="数据质量"
        status={<RailStatusPill tone={hasNoSnapshot ? "neutral" : statusTone(dataStatusKind)}>链路</RailStatusPill>}
      >
        <div className={styles.dhRailEvidenceRows}>
          <RailEvidenceRow
            label="报告日"
            value={reportDateContextLabel(reportDateContext)}
            status={dateDivergent}
            tone={dateDivergent ? "warning" : "neutral"}
            testId="dashboard-home-rail-report-date"
            statusKind={dateDivergent ? "stale" : dataStatusKind}
          />
          <RailEvidenceRow
            label="来源"
            value={sourceLedgerRows.find((row) => row.label === "来源")?.value ?? ""}
          />
          <RailEvidenceRow label="口径" value={`${dataSyncPrefix} · 经营读数`} />
          {missingDomainText ? (
            <RailEvidenceRow
              label="缺失域"
              value={missingDomainText}
              status
              tone="warning"
            />
          ) : null}
          <RailEvidenceRow
            label="更新时间"
            value={<span data-testid="dashboard-home-rail-updated-at">{railUpdatedAt}</span>}
          />
          <RailEvidenceRow
            label="用途"
            value={sourceLedgerRows.find((row) => row.label === "用途")?.value ?? ""}
          />
          <RailEvidenceRow
            label="数据状态"
            value={statusLabel}
            status
            tone={hasNoSnapshot ? "neutral" : statusTone(dataStatusKind === "ok" ? "ready" : dataStatusKind)}
            testId="dashboard-home-rail-data-status"
            statusKind={dataStatusKind}
          />
        </div>
      </RailCard>
    </aside>
  );
}
