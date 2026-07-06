import { Link } from "react-router-dom";

import type { ResultMeta } from "../../../../api/contracts";
import type { DashboardHomeFirstScreenView } from "../dashboardHomeFirstScreenTypes";
import styles from "../dashboardHomeShell.module.css";

type DecisionRailSectionProps = {
  decisionRail: DashboardHomeFirstScreenView["decisionRail"];
  reportDate: string;
  dataSyncPrefix: string;
  dataStatusKind: DashboardHomeFirstScreenView["headerStatus"]["dataStatusKind"];
  snapshotMeta?: ResultMeta | null;
};

type RailTone = "success" | "warning" | "danger" | "neutral";

function statusTone(kind: DashboardHomeFirstScreenView["headerStatus"]["dataStatusKind"] | "ready"): RailTone {
  if (kind === "ok" || kind === "ready") return "success";
  if (kind === "stale") return "warning";
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
          <span>{title}</span>
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
    <div className={styles.dhRailMessage} data-tone={tone}>
      {children}
    </div>
  );
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
  if (dataStatusKind === "stale") return "偏旧";
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
}: DecisionRailSectionProps) {
  const isError = dataStatusKind === "error";
  const isLoading = dataStatusKind === "loading";
  const railUpdatedAt = railUpdatedAtLabel({
    dataStatusKind,
    dataSyncPrefix,
    reportDate,
    dataUpdatedAt: decisionRail.dataUpdatedAt,
  });
  const pendingSummary = hasDisplayText(decisionRail.pendingSummary)
    ? decisionRail.pendingSummary
    : "暂无";
  const statusLabel = sourceLedgerStatusLabel(dataStatusKind, dataSyncPrefix, snapshotMeta);
  const sourceLedgerRows: Array<{
    label: string;
    value: string;
    status?: boolean;
    tone?: RailTone;
  }> = [
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
      value: snapshotMeta ? (snapshotMeta.formal_use_allowed ? "正式经营决策" : "复核参考") : "待来源确认",
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
    <aside data-testid="dashboard-home-decision-rail" className={styles.dhRail}>
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
          <RailMessage tone="danger">数据读取错误</RailMessage>
        ) : isLoading ? (
          <RailMessage>读取中</RailMessage>
        ) : (
          <div className={styles.dhRailActionList}>
            {decisionRail.actions.map((action) => (
              <div key={action.id} className={styles.dhRailActionRow}>
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
              </div>
            ))}
            <div className={styles.dhRailMutedNote}>
              暂无复核日志接口
            </div>
          </div>
        )}
      </RailCard>

      <RailCard
        testId="dashboard-home-action-queue-card"
        title="待办事项"
        status={<RailStatusPill tone="neutral">队列</RailStatusPill>}
      >
        {isError ? (
          <RailMessage tone="danger">数据读取错误</RailMessage>
        ) : isLoading ? (
          <RailMessage>读取中</RailMessage>
        ) : (
          <ul className={styles.dhRailSuggestionList}>
            {decisionRail.suggestions.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
            {decisionRail.suggestions.length === 0 && <li>暂无决策待办</li>}
          </ul>
        )}
      </RailCard>

      <RailCard
        testId="dashboard-home-data-quality-card"
        title="数据质量"
        status={<RailStatusPill tone={statusTone(dataStatusKind)}>链路</RailStatusPill>}
      >
        <div className={styles.dhRailEvidenceRows}>
          <RailEvidenceRow label="口径" value={`${dataSyncPrefix} · 经营读数`} />
          <RailEvidenceRow
            label="更新时间"
            value={<span data-testid="dashboard-home-rail-updated-at">{railUpdatedAt}</span>}
          />
          <RailEvidenceRow
            label="数据状态"
            value={statusLabel}
            status
            tone={statusTone(dataStatusKind === "ok" ? "ready" : dataStatusKind)}
            testId="dashboard-home-rail-data-status"
            statusKind={dataStatusKind}
          />
        </div>
      </RailCard>

      <section className={styles.dhRailSection}>
        <div className={styles.dhRailSectionHeader}>
          <h3>来源台账概要</h3>
          <RailStatusPill tone={statusTone(dataStatusKind)}>证据</RailStatusPill>
        </div>
        <div className={styles.dhRailEvidenceRows}>
          {sourceLedgerRows.map((row) => (
            <RailEvidenceRow
              key={row.label}
              label={row.label}
              value={row.value}
              status={row.status}
              tone={row.tone}
            />
          ))}
        </div>
      </section>
    </aside>
  );
}
