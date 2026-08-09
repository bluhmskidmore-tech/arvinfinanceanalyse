import { Link } from "react-router-dom";

import type { ResultMeta, VerdictPayload } from "../../../../api/contracts";
import type { DataSectionState } from "../../../../components/DataSection.types";
import type {
  DashboardHomeFirstScreenView,
  HomeReportDateContext,
} from "../dashboardHomeFirstScreenTypes";
import type { HomeSnapshotPnlAttributionVM } from "../dashboardHomeSnapshotAdapter";
import {
  formatShortDate,
  hasReportDateDivergence,
  reportDateContextLabel,
} from "../homeReportDateLabel";
import styles from "../dashboardHomeShell.module.css";

type DecisionRailSectionProps = {
  decisionRail: DashboardHomeFirstScreenView["decisionRail"];
  riskObservations?: DashboardHomeFirstScreenView["keyRiskStrip"];
  reportDate: string;
  dataSyncPrefix: string;
  dataStatusKind: DashboardHomeFirstScreenView["headerStatus"]["dataStatusKind"];
  snapshotFailureKind?: DashboardHomeFirstScreenView["headerStatus"]["snapshotFailureKind"];
  snapshotMeta?: ResultMeta | null;
  reportDateContext: HomeReportDateContext;
  missingDomains?: DashboardHomeFirstScreenView["missingDomains"];
  reviewReasons?: VerdictPayload["reasons"];
  contributionAttribution?: HomeSnapshotPnlAttributionVM | null;
  contributionState?: DataSectionState;
};

/**
 * 右栏「报告日」行的值：label 已经是「报告日」，value 不再重复前缀。
 * exact 模式只给 ISO 日期；fallback/stale 分歧时给「实际 MM/DD · 请求 MM/DD」，
 * 完整原因仍由顶栏状态 chip 的复合标签承载（page_contracts 的显式说明要求）。
 */
function railReportDateValue(ctx: HomeReportDateContext): string {
  if (hasReportDateDivergence(ctx)) {
    return `实际 ${formatShortDate(ctx.actualDataDate)} · 请求 ${formatShortDate(ctx.requestedDate)}`;
  }
  const actual = ctx.actualDataDate.trim();
  return actual || reportDateContextLabel(ctx);
}

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
  title: React.ReactNode;
  status?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section
      data-testid={testId}
      data-layout-role="decision-rail-card"
      className={`${styles.dhCard} ${styles.dhRailCard} ${styles.dhSurfaceCard}`}
    >
      <div className={styles.dhRailCardBody}>
        <div data-layout-role="decision-rail-card-header" className={styles.dhRailCardHeader}>
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
  valueTitle,
  activityKind,
}: {
  label: string;
  value: React.ReactNode;
  status?: boolean;
  tone?: RailTone;
  testId?: string;
  statusKind?: DashboardHomeFirstScreenView["headerStatus"]["dataStatusKind"];
  valueTitle?: string;
  activityKind?: string;
}) {
  const resolvedValueTitle =
    valueTitle ??
    (typeof value === "string" || typeof value === "number"
      ? String(value)
      : undefined);

  return (
    <div
      className={styles.dhRailEvidenceRow}
      data-activity-kind={activityKind}
      data-testid={testId}
      data-status-kind={statusKind}
      title={
        resolvedValueTitle ? `${label}：${resolvedValueTitle}` : undefined
      }
    >
      <span title={label}>{label}</span>
      {status ? (
        <RailStatusPill tone={tone}>{value}</RailStatusPill>
      ) : (
        <strong title={resolvedValueTitle}>{value}</strong>
      )}
    </div>
  );
}

function RailNarrativeRow({
  label,
  value,
  activityKind,
}: {
  label: string;
  value: string;
  activityKind?: string;
}) {
  return (
    <div
      aria-label={`${label}：${value}`}
      className={`${styles.dhRailEvidenceRow} ${styles.dhDecisionRailNarrative}`}
      data-activity-kind={activityKind}
      title={`${label}：${value}`}
    >
      <span title={label}>{label}</span>
      <strong title={value}>{value}</strong>
    </div>
  );
}

function ContributionObservationRow({ row }: { row: HoldingRailRow }) {
  return (
    <div
      aria-label={`${row.label}：${row.value}`}
      className={styles.dhContributionObservationRow}
      data-contribution-kind={row.id}
      data-tone={row.tone}
      title={`${row.label}：${row.value}`}
    >
      <i
        aria-hidden="true"
        className={styles.dhContributionToneMarker}
      />
      <span title={row.label}>{row.label}</span>
      <strong title={row.value}>{row.value}</strong>
    </div>
  );
}

type ReviewBasisReason = VerdictPayload["reasons"][number];

function ReviewBasisRow({
  index,
  reason,
}: {
  index: number;
  reason: ReviewBasisReason;
}) {
  const label = reason.label.trim();
  const value = reason.value.trim();
  const detail = reason.detail.trim();
  const accessibleCopy = [`${label}：${value}`, detail]
    .filter(Boolean)
    .join("；");

  return (
    <div
      aria-label={accessibleCopy}
      className={styles.dhReviewBasisRow}
      data-review-basis-index={index + 1}
      data-tone={reason.tone}
      title={accessibleCopy}
    >
      <i
        aria-hidden="true"
        className={styles.dhReviewBasisMarker}
      />
      <span title={label}>{label}</span>
      <strong title={value}>{value}</strong>
      <small title={detail}>{detail}</small>
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
  return "暂无";
}

function normalizeRailText(value: string | null | undefined): string {
  return value?.trim().replace(/\s+/g, " ") ?? "";
}

function hasDisplayText(value: string | null | undefined): boolean {
  const normalized = normalizeRailText(value);
  return Boolean(
    normalized &&
      normalized !== "—" &&
      normalized !== "--" &&
      normalized !== "暂无",
  );
}

type RiskObservation =
  DashboardHomeFirstScreenView["keyRiskStrip"][number];

function buildRiskObservationRows(
  observations: DashboardHomeFirstScreenView["keyRiskStrip"],
): RiskObservation[] {
  const rows: RiskObservation[] = [];
  const exactRows = new Set<string>();

  for (const observation of observations) {
    const label = normalizeRailText(observation.label);
    const valueKey = normalizeRailText(observation.value);
    const deltaKey = normalizeRailText(observation.delta);
    if (
      !hasDisplayText(label) ||
      (!hasDisplayText(valueKey) && !hasDisplayText(deltaKey))
    ) {
      continue;
    }

    const exactKey = `${label}\u0000${valueKey}\u0000${deltaKey}`;
    if (exactRows.has(exactKey)) {
      continue;
    }
    exactRows.add(exactKey);
    rows.push({
      ...observation,
      label,
    });
    if (rows.length === 5) {
      break;
    }
  }

  return rows;
}

function formatSnapshotGeneratedAt(snapshotMeta: ResultMeta | null | undefined): string {
  const generatedAt = snapshotMeta?.generated_at?.trim();
  if (!generatedAt) {
    return "暂无";
  }
  const match =
    /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})(?::\d{2}(?:\.\d+)?)?(Z|[+-]\d{2}:\d{2})?$/.exec(
      generatedAt,
    );
  if (!match) {
    return generatedAt;
  }
  const zoneLabel =
    match[3] === "Z" ? " UTC" : match[3] ? ` UTC${match[3]}` : "";
  return `${match[1]} ${match[2]}${zoneLabel}`;
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

type DecisionRailData = DashboardHomeFirstScreenView["decisionRail"];
type DecisionRailAction = DecisionRailData["actions"][number];

type TodoRailRow =
  | {
      kind: "summary";
      id: string;
      text: string;
      normalizedText: string;
      to?: undefined;
      order: number;
    }
  | {
      kind: "action";
      id: string;
      text: string;
      normalizedText: string;
      to?: string;
      order: number;
      action: DecisionRailAction;
    }
  | {
      kind: "suggestion";
      id: string;
      text: string;
      normalizedText: string;
      to?: string;
      order: number;
    };

type HoldingRailRow = {
  id: string;
  label: string;
  value: string;
  tone: HomeSnapshotPnlAttributionVM["segments"][number]["tone"];
};

type ActivityRailRow = {
  id: "report-date" | "generated-at" | "conclusion" | "formal-use" | "missing-domains";
  label: string;
  value: string;
  dateTime?: string;
  narrative?: boolean;
};

function buildTodoRows(decisionRail: DecisionRailData): TodoRailRow[] {
  const actionRows: TodoRailRow[] = decisionRail.actions
    .filter(
      (action) =>
        action.id !== "no-action" && hasDisplayText(action.title),
    )
    .map((action, order) => ({
      kind: "action",
      id: `action-${action.id}`,
      text: normalizeRailText(action.title),
      normalizedText: normalizeRailText(action.title),
      to: action.to?.trim() || undefined,
      order,
      action,
    }));
  const suggestionRows: TodoRailRow[] = decisionRail.suggestions
    .filter((item) => hasDisplayText(item.text))
    .map((item, order) => ({
      kind: "suggestion",
      id: `suggestion-${item.id}`,
      text: normalizeRailText(item.text),
      normalizedText: normalizeRailText(item.text),
      to: item.to?.trim() || undefined,
      order,
    }));
  const summaryRows: TodoRailRow[] = hasDisplayText(decisionRail.pendingSummary)
    ? [
        {
          kind: "summary",
          id: "pending-summary",
          text: normalizeRailText(decisionRail.pendingSummary),
          normalizedText: normalizeRailText(decisionRail.pendingSummary),
          order: 0,
        },
      ]
    : [];

  const priorityCandidates = [
    ...actionRows,
    ...suggestionRows,
    ...summaryRows,
  ];
  const exactRows = new Map<string, TodoRailRow>();
  priorityCandidates.forEach((row) => {
    const exactKey = `${row.normalizedText}\u0000${row.to ?? ""}`;
    if (!exactRows.has(exactKey)) {
      exactRows.set(exactKey, row);
    }
  });
  const linkedTexts = new Set(
    Array.from(exactRows.values())
      .filter((row) => Boolean(row.to))
      .map((row) => row.normalizedText),
  );
  const displayOrder: Record<TodoRailRow["kind"], number> = {
    summary: 0,
    action: 1,
    suggestion: 2,
  };

  return Array.from(exactRows.values())
    .filter((row) => Boolean(row.to) || !linkedTexts.has(row.normalizedText))
    .sort(
      (left, right) =>
        displayOrder[left.kind] - displayOrder[right.kind] ||
        left.order - right.order,
    )
    .slice(0, 5);
}

function buildHoldingRows(
  attribution: HomeSnapshotPnlAttributionVM | null | undefined,
): HoldingRailRow[] {
  const title = normalizeRailText(attribution?.title);
  if (
    !attribution ||
    !title ||
    title.includes("无受控产品分类月度数据")
  ) {
    return [];
  }
  const segments = attribution.segments.slice(0, 5);
  if (
    segments.length === 0 ||
    !segments.some((segment) => Number.isFinite(segment.amount.raw))
  ) {
    return [];
  }
  return segments.map((segment) => ({
    id: segment.id,
    label: normalizeRailText(segment.label),
    value:
      Number.isFinite(segment.amount.raw) &&
      normalizeRailText(segment.amount.display)
        ? normalizeRailText(segment.amount.display)
        : "—",
    tone: segment.tone,
  }));
}

function buildActivityRows(args: {
  reportDateValue: string;
  reportDateDateTime: string;
  generatedAt: string;
  generatedAtDateTime: string;
  conclusion: string;
  formalUseLabel: string;
  missingDomainLabel: string;
  excludedNarrativeTexts: ReadonlySet<string>;
}): ActivityRailRow[] {
  const normalizedConclusion = normalizeRailText(args.conclusion);
  const includeConclusion =
    hasDisplayText(normalizedConclusion) &&
    !args.excludedNarrativeTexts.has(normalizedConclusion);
  const rows: ActivityRailRow[] = [
    {
      id: "report-date",
      label: "报告日",
      value: args.reportDateValue,
      dateTime: args.reportDateDateTime || undefined,
    },
    {
      id: "generated-at",
      label: "快照生成",
      value: args.generatedAt,
      dateTime: args.generatedAtDateTime || undefined,
    },
  ];
  if (includeConclusion) {
    rows.push({
      id: "conclusion",
      label: "最新结论",
      value: normalizedConclusion,
      narrative: true,
    });
  }
  rows.push(
    {
      id: "formal-use",
      label: "用途",
      value: args.formalUseLabel,
    },
    {
      id: "missing-domains",
      label: "数据缺口",
      value: args.missingDomainLabel,
    },
  );
  return rows.slice(0, 5);
}

export function DecisionRailSection({
  decisionRail,
  riskObservations = [],
  reportDate,
  dataSyncPrefix,
  dataStatusKind,
  snapshotFailureKind,
  snapshotMeta,
  reportDateContext,
  missingDomains = [],
  reviewReasons = [],
  contributionAttribution,
  contributionState,
}: DecisionRailSectionProps) {
  const isError = dataStatusKind === "error";
  const isLoading = dataStatusKind === "loading";
  const errorRecovery = snapshotFailureKind === "permission"
    ? "当前账号缺少 executive 读取权限；联系管理员开通后重试。"
    : "主快照请求未完成；请重试主快照。";
  const hasNoSnapshot = reportDateContext.mode === "empty";
  const snapshotGeneratedAtDateTime = hasNoSnapshot
    ? ""
    : snapshotMeta?.generated_at?.trim() ?? "";
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
  const statusLabel = hasNoSnapshot
    ? "暂无可用快照"
    : sourceLedgerStatusLabel(dataStatusKind, dataSyncPrefix, snapshotMeta);
  const formalUseAllowed =
    dataStatusKind === "ok" && snapshotMeta?.formal_use_allowed === true;
  const formalUseLabel = snapshotMeta
    ? formalUseAllowed
      ? "正式经营决策"
      : "复核参考"
    : "待来源确认";
  const dateDivergent = hasReportDateDivergence(reportDateContext);
  const keyRisk = hasDisplayText(decisionRail.keyRisk)
    ? normalizeRailText(decisionRail.keyRisk)
    : null;
  const riskObservationRows = buildRiskObservationRows(riskObservations);
  const todoRows = buildTodoRows(decisionRail);
  const todoSummaryRows = todoRows.filter((row) => row.kind === "summary");
  const todoActionRows = todoRows.filter((row) => row.kind === "action");
  const todoSuggestionRows = todoRows.filter(
    (row) => row.kind === "suggestion",
  );
  const reviewCandidateRows = reviewReasons
    .slice(0, 3)
    .filter(
      (reason) =>
        hasDisplayText(reason.label) &&
        (hasDisplayText(reason.value) || hasDisplayText(reason.detail)),
    );
  const reviewRowsAllowed = !isError && !isLoading && !hasNoSnapshot;
  const reviewRows = reviewRowsAllowed ? reviewCandidateRows : [];
  const reviewContentState:
    | DashboardHomeFirstScreenView["headerStatus"]["dataStatusKind"]
    | "empty" =
    isError || hasNoSnapshot
      ? "error"
      : isLoading
        ? "loading"
        : reviewRows.length === 0
          ? "empty"
          : dataStatusKind;
  const reviewStatusLabel =
    reviewContentState === "error"
      ? "不可用"
      : reviewContentState === "loading"
        ? "读取中"
        : reviewContentState === "empty"
          ? "暂无数据"
          : reviewContentState === "stale"
            ? "数据偏旧"
            : reviewContentState === "fallback" ||
                reviewContentState === "partial"
              ? "需复核"
              : snapshotMeta?.formal_use_allowed === false
                ? "复核参考"
                : snapshotMeta
                  ? "快照依据"
                  : "待来源确认";
  const reviewStatusTone: RailTone =
    reviewContentState === "error"
      ? "danger"
      : reviewContentState === "stale" ||
          reviewContentState === "fallback" ||
          reviewContentState === "partial" ||
          (reviewContentState === "ok" &&
            snapshotMeta?.formal_use_allowed === false)
        ? "warning"
        : "neutral";
  const reviewReportDate = /^\d{4}-\d{2}-\d{2}$/.test(reportDate.trim())
    ? reportDate.trim()
    : "";
  const reviewFooterLabel = snapshotMeta
    ? `首页快照 · 报告日 ${reviewReportDate ? reviewReportDate.slice(5) : "暂无"}`
    : "暂无受管来源元数据";
  const reviewFooterTitle = snapshotMeta
    ? `来源：首页快照；报告日：${reviewReportDate || "暂无"}`
    : "暂无受管来源元数据";
  const contributionCandidateRows = buildHoldingRows(contributionAttribution);
  const contributionStateKind: DataSectionState["kind"] =
    contributionState?.kind ??
    (isLoading
      ? "loading"
      : isError
        ? "error"
        : dataStatusKind === "stale"
          ? "stale"
          : dataStatusKind === "fallback"
            ? "fallback"
            : "ok");
  const contributionRowsAllowed =
    contributionStateKind === "ok" ||
    contributionStateKind === "stale" ||
    contributionStateKind === "fallback";
  const holdingRows = contributionRowsAllowed ? contributionCandidateRows : [];
  const contributionContentState: DataSectionState["kind"] =
    holdingRows.length === 0 &&
    contributionStateKind !== "loading" &&
    contributionStateKind !== "error" &&
    contributionStateKind !== "vendor_unavailable" &&
    contributionStateKind !== "explicit_miss"
      ? "empty"
      : contributionStateKind;
  const contributionStatusLabel =
    contributionContentState === "error" ||
    contributionContentState === "vendor_unavailable"
      ? "不可用"
      : contributionContentState === "loading"
        ? "读取中"
        : contributionContentState === "explicit_miss"
          ? "指定日无数据"
          : contributionContentState === "empty"
            ? "暂无数据"
            : contributionContentState === "stale"
              ? "数据偏旧"
              : contributionContentState === "fallback" ||
                  dataStatusKind === "partial" ||
                  dataStatusKind === "fallback"
                ? "需复核"
                : "复核参考";
  const contributionStatusTone: RailTone =
    contributionContentState === "error"
      ? "danger"
      : contributionContentState === "stale" ||
          contributionContentState === "fallback"
        ? "warning"
        : contributionContentState === "ok"
          ? "warning"
          : "neutral";
  const sourceLabel = snapshotMeta ? "首页快照" : "暂无受管来源元数据";
  const missingDomainLabel =
    missingDomains.length === 0
      ? "暂无"
      : missingDomains.map((domain) => domain.label).join("、");
  const excludedNarrativeTexts = new Set<string>([
    ...(keyRisk ? [normalizeRailText(keyRisk)] : []),
    ...todoRows.map((row) => row.normalizedText),
  ]);
  const activityRows = buildActivityRows({
    reportDateValue: railReportDateValue(reportDateContext),
    reportDateDateTime: /^\d{4}-\d{2}-\d{2}$/.test(
      reportDateContext.actualDataDate.trim(),
    )
      ? reportDateContext.actualDataDate.trim()
      : "",
    generatedAt: railUpdatedAt,
    generatedAtDateTime: snapshotGeneratedAtDateTime,
    conclusion: decisionRail.conclusion,
    formalUseLabel,
    missingDomainLabel,
    excludedNarrativeTexts,
  });

  return (
    <aside
      data-testid="dashboard-home-decision-rail"
      className={styles.dhRail}
      aria-label="风险、待办、复核依据、经营贡献与动态"
    >
      <RailCard
        testId="dashboard-home-anomaly-card"
        title="风险观察"
        status={<RailStatusPill tone="neutral">预警未接入</RailStatusPill>}
      >
        {riskObservationRows.length > 0 ? (
          <div
            className={styles.dhRiskObservationRows}
            aria-label="风险观察：来自页面已加载风险带，不是受管风险预警"
            role="region"
          >
            {riskObservationRows.map((observation) => (
              <div
                key={`${observation.label}\u0000${observation.value}\u0000${observation.delta}`}
                className={styles.dhRiskObservationRow}
                data-testid="dashboard-home-risk-observation-row"
                title={`${observation.label}：${observation.value} · ${observation.delta}；页面风险观察，非预警`}
              >
                <span>{observation.label}</span>
                <strong>{observation.value}</strong>
                <span>{observation.delta}</span>
              </div>
            ))}
          </div>
        ) : (
          <RailMessage>
            {isLoading
              ? "风险观察读取中。预警来源未接入。"
              : "暂无可核验风险观察。预警来源未接入。"}
          </RailMessage>
        )}
        {riskObservationRows.length > 0 ? (
          <div
            className={styles.dhRiskObservationFooter}
            title="观察项沿用页面已加载风险带，不能解释为受管风险预警"
          >
            页面已加载观察项 · 非预警
          </div>
        ) : null}
      </RailCard>

      <RailCard
        testId="dashboard-home-review-entry-card"
        title={
          <>
            {`待办事项 (${todoActionRows.length})`}
          </>
        }
      >
        {isError ? (
          <RailMessage tone="danger">
            {`${dataSyncPrefix}：主快照未取得。${errorRecovery}`}
          </RailMessage>
        ) : isLoading ? (
          <RailMessage>读取中，待主快照返回。</RailMessage>
        ) : (
          <div
            className={`${styles.dhRailActionList} ${styles.dhDecisionRailRows}`}
            aria-label="待复核列表"
            role="region"
            tabIndex={0}
          >
            {todoSummaryRows.map((row) => (
              <div
                key={row.id}
                className={styles.dhDecisionRailKvRow}
                title={`待复核：${row.text}`}
              >
                <span>待复核</span>
                <strong>{row.text}</strong>
              </div>
            ))}
            {todoActionRows.map((row) => (
              <div
                key={row.id}
                className={`${styles.dhRailActionRow} ${styles.dhDecisionRailActionRow}`}
                data-testid="dashboard-home-decision-action-row"
                data-status-kind={row.action.statusKind}
                title={[
                  row.action.title,
                  row.action.reason,
                  `来源：${row.action.sourceLabel}`,
                  `优先级：${actionPriorityLabel(row.action.priority)}`,
                  row.action.statusKind === "ready" ? "可执行" : "待接入",
                ]
                  .filter(Boolean)
                  .join("｜")}
              >
                {row.to ? (
                  <Link
                    to={row.to}
                    data-testid={`dashboard-home-decision-action-${row.action.id}`}
                  >
                    {row.text}
                  </Link>
                ) : (
                  <span data-testid={`dashboard-home-decision-action-${row.action.id}`}>
                    {row.text}
                  </span>
                )}
                <span>{row.action.reason}</span>
                <span className={styles.dhRailActionMeta}>
                  <span>{`来源：${row.action.sourceLabel}`}</span>
                  <span>{`优先级：${actionPriorityLabel(row.action.priority)}`}</span>
                  <span>{row.action.statusKind === "ready" ? "可执行" : "待接入"}</span>
                </span>
                <span className={styles.dhRailActionOwnership}>
                  <span>负责人待接入</span>
                  <span>截止时间未维护</span>
                </span>
              </div>
            ))}
            {todoSuggestionRows.length > 0 ? (
              <ul
                className={`${styles.dhRailSuggestionList} ${styles.dhDecisionRailSuggestionList}`}
                aria-label="可下钻建议"
              >
                {todoSuggestionRows.map((row) => (
                  <li key={row.id} title={`建议｜${row.text}`}>
                    {row.to ? (
                      <Link to={row.to}>{`建议｜${row.text}`}</Link>
                    ) : (
                      <span>{`建议｜${row.text}`}</span>
                    )}
                  </li>
                ))}
              </ul>
            ) : null}
            {todoRows.length === 0 ? (
              <RailMessage>暂无待办事项：主快照未下发可执行动作。</RailMessage>
            ) : null}
          </div>
        )}
      </RailCard>

      <RailCard
        testId="dashboard-home-action-queue-card"
        title="复核依据"
        status={
          <RailStatusPill tone={reviewStatusTone}>
            {reviewStatusLabel}
          </RailStatusPill>
        }
      >
        {reviewContentState === "error" ? (
          <RailMessage tone="danger">复核依据暂不可用</RailMessage>
        ) : reviewContentState === "loading" ? (
          <RailMessage>复核依据加载中</RailMessage>
        ) : (
          <div
            aria-description={`首页快照结论的支撑理由，分析口径，仅供复核参考，报告日${reviewReportDate || "暂无"}。`}
            aria-label="复核依据"
            className={styles.dhReviewBasisRegion}
            data-state={reviewContentState}
            role="region"
            tabIndex={0}
          >
            {reviewRows.map((reason, index) => (
              <ReviewBasisRow
                key={`${index}\u0000${reason.label}\u0000${reason.value}`}
                index={index}
                reason={reason}
              />
            ))}
            {reviewRows.length === 0 ? (
              <RailMessage>暂无可核验复核依据</RailMessage>
            ) : null}
            <div
              className={styles.dhReviewBasisFooter}
              data-testid="dashboard-home-review-basis-footer"
              title={reviewFooterTitle}
            >
              {reviewFooterLabel}
            </div>
          </div>
        )}
      </RailCard>

      <RailCard
        testId="dashboard-home-data-quality-card"
        title="经营贡献观察"
        status={
          <RailStatusPill tone={contributionStatusTone}>
            {contributionStatusLabel}
          </RailStatusPill>
        }
      >
        {contributionContentState === "error" ? (
          <RailMessage tone="danger">经营贡献数据暂不可用</RailMessage>
        ) : contributionContentState === "vendor_unavailable" ? (
          <RailMessage>经营贡献数据来源暂不可用</RailMessage>
        ) : contributionContentState === "explicit_miss" ? (
          <RailMessage>指定报告日暂无经营贡献数据</RailMessage>
        ) : contributionContentState === "loading" ? (
          <RailMessage>经营贡献数据加载中</RailMessage>
        ) : (
          <div
            aria-description={`产品类别级经营贡献拆解，分析口径，仅供复核参考，报告日${reportDate || "暂无"}；不具备事件或工作流语义。`}
            aria-label="经营贡献观察"
            className={`${styles.dhRailEvidenceRows} ${styles.dhDecisionRailRows} ${styles.dhContributionObservationRows}`}
            data-state={contributionContentState}
            role="region"
            tabIndex={0}
          >
            {holdingRows.map((row) => (
              <ContributionObservationRow
                key={row.id}
                row={row}
              />
            ))}
            {holdingRows.length === 0 ? (
              <RailMessage>暂无可核验经营贡献拆解。</RailMessage>
            ) : null}
          </div>
        )}
      </RailCard>

      <RailCard
        testId="dashboard-home-evidence-material-card"
        title="最新动态"
        status={
          <span
            data-testid="dashboard-home-rail-data-status"
            data-status-kind={dataStatusKind}
          >
            <RailStatusPill
              tone={hasNoSnapshot ? "neutral" : statusTone(dataStatusKind)}
            >
              {statusLabel}
            </RailStatusPill>
          </span>
        }
      >
        <div
          className={`${styles.dhRailEvidenceRows} ${styles.dhDecisionRailRows} ${styles.dhDecisionRailActivityRows}`}
          aria-label="最新动态明细"
          role="region"
          tabIndex={0}
        >
          {activityRows.map((row) => {
            const activityKind =
              row.id === "generated-at" ? "snapshot-generated" : row.id;
            if (row.narrative) {
              return (
                <RailNarrativeRow
                  key={row.id}
                  activityKind={activityKind}
                  label={row.label}
                  value={row.value}
                />
              );
            }
            return (
              <RailEvidenceRow
                key={row.id}
                label={row.label}
                activityKind={activityKind}
                value={
                  row.id === "generated-at" ? (
                    row.dateTime ? (
                      <time
                        data-testid="dashboard-home-rail-updated-at"
                        dateTime={row.dateTime}
                      >
                        {row.value}
                      </time>
                    ) : (
                      <span data-testid="dashboard-home-rail-updated-at">
                        {row.value}
                      </span>
                    )
                  ) : row.id === "report-date" &&
                    row.dateTime &&
                    !dateDivergent ? (
                    <time dateTime={row.dateTime}>
                      {row.value}
                    </time>
                  ) : (
                    row.value
                  )
                }
                status={row.id === "report-date" && dateDivergent}
                tone={
                  row.id === "report-date" && dateDivergent
                    ? "warning"
                    : "neutral"
                }
                testId={
                  row.id === "report-date"
                    ? "dashboard-home-rail-report-date"
                    : undefined
                }
                statusKind={
                  row.id === "report-date"
                    ? dateDivergent
                      ? "stale"
                      : dataStatusKind
                    : undefined
                }
                valueTitle={row.value}
              />
            );
          })}
        </div>
        <div
          className={`${styles.dhRailActivityFooter} ${styles.dhDecisionRailFooter}`}
          title={`来源：${sourceLabel}`}
        >
          <span>来源</span>
          <strong>{sourceLabel}</strong>
        </div>
      </RailCard>
    </aside>
  );
}
