import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../api/client";
import type {
  PnlByBusinessConcentrationRow,
  PnlByBusinessConcentrationSummary,
  PnlByBusinessInsightsComponentEvidence,
  PnlByBusinessInsightsPayload,
  PnlByBusinessNegativeFtpPersistenceRow,
  PnlByBusinessPrecomputeStatus,
  PnlByBusinessShareDriftRow,
} from "../../api/contracts";
import { FilterBar } from "../../components/FilterBar";
import { KpiCard } from "../../components/KpiCard";
import { PageAsyncSection } from "../../components/page/PageAsyncSection";
import {
  DataStatusStrip,
  PageDecisionHero,
  PageFilterTray,
  PageStateSurface,
  PageV2Shell,
} from "../../components/page/PagePrimitives";
import {
  DataTable,
  SECTION_HEAD_STACK_CLASSNAME,
  SectionHead,
  type DataTableColumn,
} from "../../components/layout";
import { EM_DASH } from "../../utils/format";
import { CapitalEfficiencyQuadrantPanel } from "./CapitalEfficiencyQuadrantPanel";
import { UntracedReconciliationTrendPanel } from "./UntracedReconciliationTrendPanel";
import { hasApprovedPnlByBusinessInsightsEvidence } from "../pnl/pnlByBusinessInsightsModel";
import "./PnlByBusinessInsightsPage.css";

const RECONCILIATION_NOTE_TEXT =
  "以下为正式数据链路的对账诊断趋势，反映的是追溯完整性，不是业务贡献或拖累结论，不作为资源配置或业务评价依据。";

const PRECOMPUTE_STATUS_POLL_INTERVAL_MS = 3_000;

const PRECOMPUTE_READINESS_LABEL = {
  ready: "已就绪",
  pending: "准备中",
  stale: "结果已过期",
  failed: "准备失败",
  source_missing: "源数据缺失",
} as const;

const PRECOMPUTE_DEPENDENCY_LABEL = {
  current_ytd: "本期累计",
  baseline_ytd: "上年同期间累计",
  monthly: "本期月度",
  monthly_baseline: "同期月度",
} as const;

function isAccessDeniedReadError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? "");
  return /\b(?:401|403)\b/.test(message) || /\b(?:unauthorized|forbidden|not authenticated|permission denied)\b/i.test(message);
}

function usesPrecomputeReadinessProtocol(
  status: PnlByBusinessPrecomputeStatus | undefined,
): boolean {
  return status?.readiness !== undefined;
}

function describePrecomputeDependencies(status: PnlByBusinessPrecomputeStatus): string | null {
  if (!status.dependencies?.length) {
    return null;
  }
  return status.dependencies
    .map((dependency) =>
      `${PRECOMPUTE_DEPENDENCY_LABEL[dependency.key]} ${dependency.requested_report_date}：${PRECOMPUTE_READINESS_LABEL[dependency.readiness]}`,
    )
    .join("；");
}

function toNumber(value: string | null | undefined): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatPct(value: string | null | undefined, digits = 2): string {
  const parsed = toNumber(value);
  return parsed === null ? EM_DASH : `${parsed.toFixed(digits)}%`;
}

function formatSignedPp(value: string | null | undefined): string {
  const parsed = toNumber(value);
  if (parsed === null) {
    return EM_DASH;
  }
  return `${parsed > 0 ? "+" : ""}${parsed.toFixed(2)}pp`;
}

const YUAN_PER_YI = 100_000_000;

function formatYuanAsYi(value: string | null | undefined): string {
  const parsed = toNumber(value);
  return parsed === null ? EM_DASH : (parsed / YUAN_PER_YI).toFixed(2);
}

function validIsoDate(value: string | null): string | null {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return null;
  }
  const [year, month, day] = value.split("-").map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day
    ? value
    : null;
}

function initialFilters(searchParams: URLSearchParams): { year: number; asOfDate: string } | null {
  const asOfDate = validIsoDate(searchParams.get("as_of_date"));
  const rawYear = searchParams.get("year");
  const year = /^\d{4}$/.test(rawYear ?? "") ? Number(rawYear) : Number.NaN;
  if (
    asOfDate &&
    Number.isInteger(year) &&
    year >= 2000 &&
    year <= 2100 &&
    asOfDate.startsWith(`${year}-`)
  ) {
    return { year, asOfDate };
  }
  return null;
}

function topConcentrationRows(summary: PnlByBusinessConcentrationSummary) {
  return [...summary.rows]
    .sort((left, right) => (toNumber(right.share_pct) ?? -1) - (toNumber(left.share_pct) ?? -1))
    .slice(0, summary.top_n);
}

function ytdRuleVersions(componentEvidence: PnlByBusinessInsightsComponentEvidence[]) {
  const current = componentEvidence.find((item) => item.component === "current_ytd")?.rule_version ?? null;
  const baseline = componentEvidence.find((item) => item.component === "baseline_ytd")?.rule_version ?? null;
  return {
    current,
    baseline,
    mismatch: Boolean(current && baseline && current !== baseline),
  };
}

function BusinessDecisionBrief({ result }: { result: PnlByBusinessInsightsPayload }) {
  const pendingIssues = result.negative_ftp_persistence.balance_quality_issues ?? [];
  const sourcePending = result.negative_ftp_persistence.status === "source_pending" || pendingIssues.length > 0;
  const topRows = topConcentrationRows(result.concentration);
  const driftByRowKey = new Map(result.share_drift.rows.map((row) => [row.row_key, row]));
  const warningRows = result.negative_ftp_persistence.rows
    .filter((row) => row.eligible && row.status === "eligible" && row.warning_triggered)
    .sort(
      (left, right) =>
        (toNumber(right.negative_ftp_month_share_pct) ?? -1) -
        (toNumber(left.negative_ftp_month_share_pct) ?? -1),
    );
  const approvedManualEntriesIncluded = result.component_evidence.some(
    (item) =>
      item.component.startsWith("monthly_") && item.tables_used.includes("pnl_by_business_adjustments"),
  );
  const warningDoesNotCoverEveryMonth = warningRows.some(
    (row) => (toNumber(row.negative_ftp_month_share_pct) ?? 100) < 100,
  );
  const ruleVersions = ytdRuleVersions(result.component_evidence);

  return (
    <section
      className="pnl-by-business-insights-decision-brief"
      data-testid="pnl-by-business-insights-decision-brief"
      aria-labelledby="pnl-by-business-insights-decision-brief-title"
    >
      <div className="pnl-by-business-insights-decision-brief__header">
        <div>
          <span>管理层先看</span>
          <h2 id="pnl-by-business-insights-decision-brief-title">结构、异常与使用顺序</h2>
        </div>
        <span className="pnl-by-business-insights-decision-brief__cutoff">截至 {result.as_of_date}</span>
      </div>

      <div className="pnl-by-business-insights-decision-brief__grid">
        <article>
          <span className="pnl-by-business-insights-decision-brief__label">结构底盘</span>
          <strong>Top{result.concentration.top_n} 占比 {formatPct(result.concentration.top_n_share_pct)}</strong>
          <p>{topRows.length > 0 ? topRows.map((row) => row.business_type).join("、") : "暂无合格父级业务"}</p>
          <small>
            HHI {formatPct(result.concentration.hhi_pct)} 用于观察集中度趋势，不作为单期红黄绿阈值。
          </small>
        </article>

        <article className="pnl-by-business-insights-decision-brief__focus">
          <span className="pnl-by-business-insights-decision-brief__label">FTP后损益为负月份观察</span>
          {sourcePending ? (
            <p role="status">{pendingIssues.map((issue) => issue.report_date).join("、")}余额来源待核实，连续负 FTP 暂不形成结论；取得正确源表后重算。</p>
          ) : warningRows.length > 0 ? (
            <div className="pnl-by-business-insights-decision-brief__signals">
              {warningRows.map((row) => {
                const drift = result.share_drift.available ? driftByRowKey.get(row.row_key) : undefined;
                return (
                  <p key={row.row_key}>
                    <strong>{row.business_type}</strong>
                    ：FTP后损益为负月份占比 {formatPct(row.negative_ftp_month_share_pct)}，最长连续
                    {row.negative_ftp_longest_streak_months ?? EM_DASH}个月
                    {drift?.drift_pp !== null && drift?.drift_pp !== undefined ? (
                      <>
                        ；当前日均份额 {formatPct(drift.current_share_pct)}，较上年同期间 {formatSignedPp(drift.drift_pp)}
                      </>
                    ) : null}
                    。
                  </p>
                );
              })}
            </div>
          ) : (
            <p>当前没有业务达到FTP后损益为负月份占比提示条件。</p>
          )}
          <small>
            {approvedManualEntriesIncluded ? "滚动月度口径已纳入已批准手工补录。" : ""}
            {warningDoesNotCoverEveryMonth
              ? "FTP后损益为负月份占比较高不表示每个月均为负，也不表示业务总损益为负。"
              : ""}
            该交叉观察只组合展示后端正式结果，不新增阈值或配置建议。
          </small>
        </article>

        <article>
          <span className="pnl-by-business-insights-decision-brief__label">怎么使用</span>
          <ol>
            <li>先看 Top{result.concentration.top_n} 与 HHI，确认资源集中在哪些业务。</li>
            <li>再把FTP后损益为负月份频率与份额漂移对照，定位需要解释的业务。</li>
            <li>最后用四象限看相对位置，并下钻资产收益率、FTP率和期限结构。</li>
          </ol>
          <small>当前接口未返回利润影响所需输入，本页不作估算。</small>
        </article>
      </div>

      {ruleVersions.mismatch ? (
        <div
          className="pnl-by-business-insights-rule-warning"
          data-testid="pnl-by-business-insights-cross-period-rule-warning"
          role="note"
        >
          <strong>跨期口径提示</strong>
          <span>
            当前 YTD 使用 {ruleVersions.current}，上年同期间使用 {ruleVersions.baseline}。份额漂移仅表示当前治理口径下的差异，统一口径重算后再形成经营判断。
          </span>
        </div>
      ) : null}
    </section>
  );
}

const CONCENTRATION_COLUMNS: readonly DataTableColumn<PnlByBusinessConcentrationRow>[] = [
  { key: "business_type", title: "业务种类" },
  {
    key: "avg_balance",
    title: "YTD日均（亿元）",
    align: "numeric",
    render: (row) => formatYuanAsYi(row.avg_balance),
  },
  {
    key: "share_pct",
    title: "日均份额",
    align: "numeric",
    render: (row) => formatPct(row.share_pct),
  },
];

function ConcentrationTable({ rows }: { rows: PnlByBusinessConcentrationRow[] }) {
  const sortedRows = [...rows].sort(
    (left, right) => (toNumber(right.share_pct) ?? -1) - (toNumber(left.share_pct) ?? -1),
  );
  return (
    <DataTable<PnlByBusinessConcentrationRow>
      testId="pnl-by-business-insights-concentration-table"
      rows={sortedRows}
      rowKey="row_key"
      columns={CONCENTRATION_COLUMNS}
      emptyMessage="暂无集中度明细"
    />
  );
}

function negativeFtpShareCell(row: PnlByBusinessNegativeFtpPersistenceRow) {
  if (!(row.eligible && row.status === "eligible")) {
    return EM_DASH;
  }
  const value = formatPct(row.negative_ftp_month_share_pct);
  return row.warning_triggered ? (
    <span className="pnl-by-business-insights-negative-ftp-warning" data-warning="true">
      {value}
    </span>
  ) : (
    value
  );
}

const NEGATIVE_FTP_COLUMNS: readonly DataTableColumn<PnlByBusinessNegativeFtpPersistenceRow>[] = [
  { key: "business_type", title: "业务种类" },
  {
    key: "negative_ftp_month_share_pct",
    title: "FTP后损益为负月份占比",
    align: "numeric",
    render: negativeFtpShareCell,
  },
  {
    key: "negative_ftp_longest_streak_months",
    title: "最长连续负值",
    align: "numeric",
    render: (row) =>
      row.eligible && row.status === "eligible" && row.negative_ftp_longest_streak_months !== null
        ? `${row.negative_ftp_longest_streak_months} 个月`
        : EM_DASH,
  },
  { key: "months_observed", title: "已观测月份", align: "numeric" },
  {
    key: "status",
    title: "状态",
    render: (row) =>
      row.status === "source_pending" ? "余额来源待核实" : !row.eligible || row.status === "insufficient_observations"
        ? "观察不足"
        : row.warning_triggered
          ? "达到提示条件"
          : "观察",
  },
];

function NegativeFtpTable({ rows }: { rows: PnlByBusinessNegativeFtpPersistenceRow[] }) {
  const sortedRows = [...rows].sort(
    (left, right) =>
      Number(right.warning_triggered) - Number(left.warning_triggered) ||
      (toNumber(right.negative_ftp_month_share_pct) ?? -1) -
        (toNumber(left.negative_ftp_month_share_pct) ?? -1),
  );
  return (
    <DataTable<PnlByBusinessNegativeFtpPersistenceRow>
      testId="pnl-by-business-insights-negative-ftp-table"
      rows={sortedRows}
      rowKey="row_key"
      columns={NEGATIVE_FTP_COLUMNS}
      emptyMessage="暂无持续性明细"
    />
  );
}

const SHARE_DRIFT_LIFECYCLE_LABEL = {
  continued: "持续",
  new: "新进",
  exited: "退出",
  unavailable: "不可用",
} as const;

const SHARE_DRIFT_COLUMNS: readonly DataTableColumn<PnlByBusinessShareDriftRow>[] = [
  { key: "business_type", title: "业务种类" },
  {
    key: "current_share_pct",
    title: "当前份额",
    align: "numeric",
    render: (row) => formatPct(row.current_share_pct),
  },
  {
    key: "baseline_share_pct",
    title: "上年同期间份额",
    align: "numeric",
    render: (row) => formatPct(row.baseline_share_pct),
  },
  {
    key: "drift_pp",
    title: "漂移",
    align: "numeric",
    render: (row) => formatSignedPp(row.drift_pp),
  },
  {
    key: "lifecycle_status",
    title: "状态",
    render: (row) => SHARE_DRIFT_LIFECYCLE_LABEL[row.lifecycle_status],
  },
];

function ShareDriftTable({
  rows,
  baselineAvailable,
  available,
  availabilityReason,
}: {
  rows: PnlByBusinessShareDriftRow[];
  baselineAvailable: boolean;
  available: boolean;
  availabilityReason: "baseline_missing" | "current_total_non_positive" | "baseline_total_non_positive" | null;
}) {
  if (!available || !baselineAvailable) {
    const reason =
      availabilityReason === "current_total_non_positive" ||
      availabilityReason === "baseline_total_non_positive"
        ? "当前期或上年同期间日均余额分母不可用，暂不计算份额漂移"
        : "上年同期间基准不可用，暂不计算份额漂移";
    return (
      <PageStateSurface
        variant="empty"
        testId="pnl-by-business-insights-share-drift-empty"
        title={reason}
      />
    );
  }
  const sortedRows = [...rows].sort(
    (left, right) => Math.abs(toNumber(right.drift_pp) ?? 0) - Math.abs(toNumber(left.drift_pp) ?? 0),
  );
  return (
    <DataTable<PnlByBusinessShareDriftRow>
      testId="pnl-by-business-insights-share-drift-table"
      rows={sortedRows}
      rowKey="row_key"
      columns={SHARE_DRIFT_COLUMNS}
    />
  );
}

export default function PnlByBusinessInsightsPage() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [initial] = useState(() => initialFilters(searchParams));
  const [year, setYear] = useState(initial?.year ?? 0);
  const [asOfDate, setAsOfDate] = useState(initial?.asOfDate ?? "");

  const datesQuery = useQuery({
    queryKey: ["pnl-by-business-insights", "dates", client.mode],
    queryFn: () => client.getFormalPnlDates({ page: "by_business_insights" }),
    retry: false,
  });
  const reportDates = useMemo(
    () => datesQuery.data?.result.report_dates ?? [],
    [datesQuery.data?.result.report_dates],
  );
  const availableYears = useMemo(
    () => Array.from(new Set(reportDates.map((reportDate) => Number(reportDate.slice(0, 4))))),
    [reportDates],
  );
  const yearReportDates = useMemo(
    () => reportDates.filter((reportDate) => reportDate.startsWith(`${year}-`)),
    [reportDates, year],
  );

  useEffect(() => {
    if (reportDates.length === 0) {
      return;
    }
    const selectionIsAvailable =
      reportDates.includes(asOfDate) && asOfDate.startsWith(`${year}-`);
    if (selectionIsAvailable) {
      return;
    }
    const initialDate = initial?.asOfDate;
    const nextDate = initialDate && reportDates.includes(initialDate) ? initialDate : reportDates[0];
    setAsOfDate(nextDate);
    setYear(Number(nextDate.slice(0, 4)));
  }, [asOfDate, initial, reportDates, year]);

  const selectedDateIsAvailable =
    reportDates.includes(asOfDate) && asOfDate.startsWith(`${year}-`);
  const hasRetainedDatesData = Boolean(datesQuery.data);
  const datesAccessDenied = datesQuery.isError && isAccessDeniedReadError(datesQuery.error);

  const precomputeStatusQueryKey = [
    "pnl-by-business-insights",
    "precompute-status",
    client.mode,
    year,
    asOfDate,
  ] as const;
  const precomputeStatusQuery = useQuery({
    queryKey: precomputeStatusQueryKey,
    queryFn: ({ signal }) => client.getPnlByBusinessPrecomputeStatus(year, asOfDate, { signal }),
    enabled: hasRetainedDatesData && !datesAccessDenied && selectedDateIsAvailable,
    retry: false,
    refetchInterval: (query) => {
      const status = query.state.data;
      return status?.readiness === "pending" && !status.worker_stalled
        ? PRECOMPUTE_STATUS_POLL_INTERVAL_MS
        : false;
    },
  });
  const precomputeStatus = precomputeStatusQuery.data;
  const usesReadinessProtocol = usesPrecomputeReadinessProtocol(precomputeStatus);
  const publishedGeneration =
    usesReadinessProtocol && precomputeStatus?.readiness === "ready" && precomputeStatus.generation
      ? precomputeStatus.generation
      : null;
  const legacyReadAllowed = precomputeStatusQuery.isSuccess && !usesReadinessProtocol;
  const generationReadAllowed = usesReadinessProtocol && publishedGeneration !== null;

  const insightsQuery = useQuery({
    queryKey: [
      "pnl-by-business-insights",
      "formal",
      client.mode,
      year,
      asOfDate,
      publishedGeneration ?? "legacy",
    ],
    queryFn: ({ signal }) =>
      client.getPnlByBusinessInsights(
        year,
        asOfDate,
        publishedGeneration ? { signal, generation: publishedGeneration } : { signal },
      ),
    enabled:
      hasRetainedDatesData &&
      !datesAccessDenied &&
      selectedDateIsAvailable &&
      (legacyReadAllowed || generationReadAllowed),
    retry: false,
  });

  const rebuildMutation = useMutation({
    mutationFn: (selection: { year: number; asOfDate: string }) =>
      client.rebuildPnlByBusinessPrecompute(selection.year, selection.asOfDate, {
        includePageDependencies: true,
        scope: "selected",
      }),
    onSuccess: (nextStatus, selection) => {
      queryClient.setQueryData(
        [
          "pnl-by-business-insights",
          "precompute-status",
          client.mode,
          selection.year,
          selection.asOfDate,
        ],
        nextStatus,
      );
    },
  });

  const datesLoading = datesQuery.isLoading && !hasRetainedDatesData;
  const datesRefreshError =
    datesQuery.isError && hasRetainedDatesData && !datesQuery.isFetching && !datesAccessDenied;
  const hasRetainedInsightsData = Boolean(insightsQuery.data);
  const precomputeStatusAccessDenied =
    precomputeStatusQuery.isError && isAccessDeniedReadError(precomputeStatusQuery.error);
  const insightsAccessDenied = insightsQuery.isError && isAccessDeniedReadError(insightsQuery.error);
  const accessDenied = datesAccessDenied || precomputeStatusAccessDenied || insightsAccessDenied;
  const accessDeniedIsRetrying = datesAccessDenied
    ? datesQuery.isFetching
    : precomputeStatusAccessDenied
      ? precomputeStatusQuery.isFetching
      : insightsQuery.isFetching;
  const precomputeStatusLoading = precomputeStatusQuery.isLoading && !precomputeStatus;
  const precomputeStatusInitialError =
    precomputeStatusQuery.isError && !precomputeStatus && !precomputeStatusAccessDenied;
  const precomputeStatusRefreshError =
    precomputeStatusQuery.isError && Boolean(precomputeStatus) && !precomputeStatusAccessDenied;
  const insightsLoading = insightsQuery.isLoading && !hasRetainedInsightsData;
  const insightsRefreshing = insightsQuery.isFetching && hasRetainedInsightsData;
  const insightsRefreshError =
    insightsQuery.isError && hasRetainedInsightsData && !insightsQuery.isFetching && !insightsAccessDenied;
  const meta = insightsQuery.data?.result_meta;
  const result = insightsQuery.data?.result;
  const generationMatches =
    !usesReadinessProtocol ||
    Boolean(publishedGeneration && result?.generation === publishedGeneration);
  const formalUseAllowedForDisplay = Boolean(
    meta?.formal_use_allowed &&
      generationMatches &&
      (!usesReadinessProtocol || precomputeStatus?.readiness === "ready"),
  );
  const contractReady = Boolean(
    generationMatches &&
      meta?.basis === "formal" &&
      meta.formal_use_allowed &&
      meta.result_kind === "pnl.by_business_insights" &&
      (meta.quality_flag === "ok" || meta.quality_flag === "warning") &&
      meta.vendor_status === "ok" &&
      !meta.scenario_flag &&
      meta.fallback_mode === "none" &&
      !meta.fallback_date &&
      meta.requested_report_date === asOfDate &&
      meta.resolved_report_date === asOfDate &&
      result?.result_version === "v2" &&
      hasApprovedPnlByBusinessInsightsEvidence(result) &&
      result?.as_of_date === asOfDate,
  );
  const isEmpty =
    (datesQuery.isSuccess && reportDates.length === 0) ||
    (insightsQuery.isSuccess &&
      contractReady &&
      (result?.concentration.rows.length ?? 0) === 0 &&
      (result?.negative_ftp_persistence.rows.length ?? 0) === 0 &&
      (result?.share_drift.rows.length ?? 0) === 0);
  const dependencyDescription = precomputeStatus
    ? describePrecomputeDependencies(precomputeStatus)
    : null;
  const canRequestPreparation = precomputeStatus?.permissions?.can_rebuild === true;
  const preparationActionAvailable = Boolean(
    usesReadinessProtocol &&
      precomputeStatus &&
      precomputeStatus.readiness !== "ready" &&
      (precomputeStatus.readiness !== "pending" || precomputeStatus.worker_stalled) &&
      canRequestPreparation,
  );
  const preparationActions = precomputeStatus && usesReadinessProtocol ? (
    <>
      {(precomputeStatus.readiness !== "pending" || precomputeStatus.worker_stalled) ? (
        <button
          type="button"
          className="moss-page-async-section__retry"
          disabled={precomputeStatusQuery.isFetching}
          onClick={() => void precomputeStatusQuery.refetch()}
        >
          重试读取状态
        </button>
      ) : null}
      {preparationActionAvailable ? (
        <button
          type="button"
          className="moss-page-async-section__retry"
          disabled={rebuildMutation.isPending}
          onClick={() => rebuildMutation.mutate({ year, asOfDate })}
        >
          {rebuildMutation.isPending ? "正在提交准备请求" : "请求后台准备"}
        </button>
      ) : null}
    </>
  ) : undefined;
  const preparationDescription = precomputeStatus && usesReadinessProtocol
    ? [
        precomputeStatus.readiness === "pending"
          ? "整页本期、同期和月度依赖正在后台准备。"
          : precomputeStatus.readiness === "stale"
            ? "该截止日的旧结果已失效，页面不会沿用旧响应的正式使用结论。"
            : precomputeStatus.readiness === "failed"
              ? precomputeStatus.error_message ?? "后台准备未完成，请先核对失败原因。"
              : precomputeStatus.readiness === "source_missing"
                ? "所选截止日的源数据不完整，页面不会补零或换用其他日期。"
                : publishedGeneration
                  ? `整页依赖已由版本 ${publishedGeneration} 覆盖。`
                  : "后台已返回就绪，但尚未提供可固定读取的版本。",
        dependencyDescription,
        precomputeStatus.run_id ? `任务 ${precomputeStatus.run_id}` : null,
        precomputeStatus.worker_stalled
          ? precomputeStatus.recovery_hint ?? "后台任务长时间没有进展，请联系运维检查 worker 后再重试读取状态。"
          : null,
        !canRequestPreparation && precomputeStatus.readiness !== "ready"
          ? precomputeStatus.permissions?.reason ?? "当前账号只能查看准备状态。"
          : null,
      ].filter((item): item is string => Boolean(item)).join(" ")
    : null;

  return (
    <section
      data-testid="pnl-by-business-insights-page"
      data-moss-theme-scope="pnl-by-business-insights"
      className="pnl-by-business-insights-page"
    >
      <PageV2Shell testId="pnl-by-business-insights-page-shell">
        <PageDecisionHero
          testId="pnl-by-business-insights-hero"
          titleTestId="pnl-by-business-insights-page-title"
          questionTestId="pnl-by-business-insights-page-subtitle"
          eyebrow="组合工作台 · 正式结构分析"
          title="业务结构与FTP后收益分析"
          businessQuestion="业务结构是否集中、哪些业务频繁或连续未覆盖FTP成本、日均份额同比如何变化、规模与FTP后收益处于什么相对位置？"
        >
          <PageFilterTray testId="pnl-by-business-insights-filter-tray">
            <FilterBar>
              <label className="pnl-by-business-insights-filter-label">
                年份
                <select
                  aria-label="pnl-by-business-insights-year"
                  value={year || ""}
                  disabled={datesQuery.isLoading || datesAccessDenied || availableYears.length === 0}
                  onChange={(event) => {
                    const nextYear = Number(event.target.value);
                    const nextDate = reportDates.find((reportDate) => reportDate.startsWith(`${nextYear}-`));
                    if (nextDate) {
                      setYear(nextYear);
                      setAsOfDate(nextDate);
                    }
                  }}
                  className="pnl-by-business-insights-control"
                >
                  {availableYears.map((availableYear) => (
                    <option key={availableYear} value={availableYear}>{availableYear}</option>
                  ))}
                </select>
              </label>
              <label className="pnl-by-business-insights-filter-label">
                截止日
                <select
                  aria-label="pnl-by-business-insights-as-of-date"
                  value={asOfDate}
                  disabled={datesQuery.isLoading || datesAccessDenied || yearReportDates.length === 0}
                  onChange={(event) => {
                    const nextDate = event.target.value;
                    setAsOfDate(nextDate);
                    setYear(Number(nextDate.slice(0, 4)));
                  }}
                  className="pnl-by-business-insights-control"
                >
                  {yearReportDates.map((reportDate) => (
                    <option key={reportDate} value={reportDate}>{reportDate}</option>
                  ))}
                </select>
              </label>
            </FilterBar>
          </PageFilterTray>
        </PageDecisionHero>

        <PageAsyncSection
          title="正式结构分析"
          isLoading={datesLoading || precomputeStatusLoading || insightsLoading}
          isError={
            (datesQuery.isError && !hasRetainedDatesData) ||
            (insightsQuery.isError && !hasRetainedInsightsData)
          }
          isEmpty={isEmpty}
          fillHeight={false}
          onRetry={() => {
            if (datesQuery.isError) {
              void datesQuery.refetch();
              return;
            }
            if (precomputeStatusQuery.isError) {
              void precomputeStatusQuery.refetch();
              return;
            }
            void insightsQuery.refetch();
          }}
        >
          {accessDenied ? (
            <PageStateSurface
              variant="error"
              testId="pnl-by-business-insights-access-denied"
              title="正式结构分析读取权限已变更"
              description={
                datesAccessDenied
                  ? "报告日期目录读取权限已变更，已停止使用缓存目录和已返回的正式结构分析结果。请重新登录或联系管理员恢复权限后重试。"
                  : precomputeStatusAccessDenied
                    ? "准备状态读取权限已变更，已停止读取和显示正式结构分析结果。请重新登录或联系管理员恢复权限后重试。"
                  : "已停止显示此前返回的正式结构分析结果。请重新登录或联系管理员恢复权限后重试。"
              }
              actions={
                <button
                  type="button"
                  className="moss-page-async-section__retry"
                  disabled={accessDeniedIsRetrying}
                  onClick={() => void (
                    datesAccessDenied
                      ? datesQuery.refetch()
                      : precomputeStatusAccessDenied
                        ? precomputeStatusQuery.refetch()
                        : insightsQuery.refetch()
                  )}
                >
                  重新检查权限
                </button>
              }
            />
          ) : null}
          {!accessDenied && datesRefreshError ? (
            <PageStateSurface
              variant="error"
              testId="pnl-by-business-insights-dates-refresh-error"
              title="报告日期目录更新失败"
              description="当前继续使用已成功加载的报告日期目录和该截止日的结构分析结果，可重试更新。"
              actions={
                <button
                  type="button"
                  className="moss-page-async-section__retry"
                  onClick={() => void datesQuery.refetch()}
                >
                  重试
                </button>
              }
            />
          ) : null}
          {!accessDenied && precomputeStatusInitialError ? (
            <PageStateSurface
              variant="error"
              testId="pnl-by-business-insights-precompute-status-error"
              title="准备状态读取失败"
              description="尚未确认整页本期、同期和月度依赖是否就绪，页面暂不读取正式结构分析结果。"
              actions={
                <button
                  type="button"
                  className="moss-page-async-section__retry"
                  onClick={() => void precomputeStatusQuery.refetch()}
                >
                  重试读取状态
                </button>
              }
            />
          ) : null}
          {!accessDenied && precomputeStatusRefreshError ? (
            <PageStateSurface
              variant="error"
              testId="pnl-by-business-insights-precompute-status-refresh-error"
              title="准备状态更新失败"
              description="页面保留上次成功取得的准备状态，可单独重试状态读取。"
              actions={
                <button
                  type="button"
                  className="moss-page-async-section__retry"
                  onClick={() => void precomputeStatusQuery.refetch()}
                >
                  重试读取状态
                </button>
              }
            />
          ) : null}
          {!accessDenied && usesReadinessProtocol && precomputeStatus?.readiness !== "ready" ? (
            <PageStateSurface
              variant={precomputeStatus?.readiness === "failed" ? "error" : "definition-pending"}
              testId="pnl-by-business-insights-precompute-state"
              title={
                precomputeStatus?.worker_stalled
                  ? "后台准备长时间没有进展"
                  : precomputeStatus?.readiness
                    ? PRECOMPUTE_READINESS_LABEL[precomputeStatus.readiness]
                    : "准备状态待确认"
              }
              description={preparationDescription ?? undefined}
              actions={preparationActions}
            />
          ) : null}
          {!accessDenied && usesReadinessProtocol && precomputeStatus?.readiness === "ready" && !publishedGeneration ? (
            <PageStateSurface
              variant="definition-pending"
              testId="pnl-by-business-insights-precompute-generation-missing"
              title="已就绪结果缺少版本"
              description={preparationDescription ?? undefined}
              actions={preparationActions}
            />
          ) : null}
          {!accessDenied && publishedGeneration && precomputeStatus?.refresh_status === "failed" ? (
            <PageStateSurface
              variant="definition-pending"
              testId="pnl-by-business-insights-refresh-failed-serving-published"
              title="最新准备失败，继续显示已发布结果"
              description={[
                `当前显示的正式结果日期为 ${precomputeStatus.report_date ?? EM_DASH}，版本 ${publishedGeneration}。`,
                precomputeStatus.refresh_error_message ?? "后台更新未完成。",
                "页面未用失败更新尝试的日期替换当前正式结果。",
              ].join(" ")}
              actions={preparationActions}
            />
          ) : null}
          {!accessDenied && rebuildMutation.isError ? (
            <PageStateSurface
              variant="error"
              testId="pnl-by-business-insights-precompute-rebuild-error"
              title="后台准备请求未受理"
              description="准备请求和状态读取相互独立。请先重试读取状态；若状态仍无变化，再按页面提示处理。"
            />
          ) : null}
          {!accessDenied && result && meta ? (
            <>
              {insightsRefreshError ? (
                <PageStateSurface
                  variant="error"
                  testId="pnl-by-business-insights-refresh-error"
                  title="结构分析更新失败"
                  description="当前仍显示该截止日上次成功返回的结果，可重试更新。"
                  actions={
                    <button
                      type="button"
                      className="moss-page-async-section__retry"
                      onClick={() => void insightsQuery.refetch()}
                    >
                      重试
                    </button>
                  }
                />
              ) : null}
              <DataStatusStrip
                testId="pnl-by-business-insights-contract-status"
                className="pnl-by-business-insights-data-status-strip"
              >
                {insightsRefreshing ? <span data-testid="pnl-by-business-insights-refreshing"><strong>更新</strong> 正在更新当前截止日的结构分析</span> : null}
                {usesReadinessProtocol ? <span><strong>准备</strong> {precomputeStatus?.readiness ? PRECOMPUTE_READINESS_LABEL[precomputeStatus.readiness] : EM_DASH}</span> : null}
                {usesReadinessProtocol ? <span><strong>版本</strong> {publishedGeneration ?? EM_DASH}</span> : null}
                <span><strong>正式口径</strong> {formalUseAllowedForDisplay ? "已批准" : "待确认"}</span>
                <span><strong>质量</strong> {meta.quality_flag}</span>
                <span><strong>截止</strong> {meta.resolved_report_date ?? result.as_of_date}</span>
                <span><strong>降级</strong> {meta.fallback_mode}</span>
                <span><strong>供应商</strong> {meta.vendor_status}</span>
                <span><strong>生成</strong> {meta.generated_at ?? EM_DASH}</span>
                <span><strong>Trace</strong> {meta.trace_id}</span>
              </DataStatusStrip>

              {!contractReady ? (
                <PageStateSurface
                  variant="definition-pending"
                  testId="pnl-by-business-insights-contract-review"
                  title="结构分析待复核"
                  description="正式状态、响应版本、截止日、质量、供应商或降级状态未通过门禁，页面不将其作为正式汇报结论。"
                />
              ) : (
                <>
              <BusinessDecisionBrief result={result} />

              <div
                className="pnl-by-business-insights-summary-grid"
                data-testid="pnl-by-business-insights-concentration-kpis"
              >
                <KpiCard
                  label={`Top${result.concentration.top_n} 日均份额`}
                  value={formatPct(result.concentration.top_n_share_pct)}
                  detail={topConcentrationRows(result.concentration).map((row) => row.business_type).join("、") || "暂无合格父级业务"}
                />
                <KpiCard
                  label="总日均余额"
                  value={`${formatYuanAsYi(result.concentration.total_avg_balance)} 亿元`}
                  detail="YTD日均余额、人民币等值、父级业务"
                />
                <KpiCard
                  label="HHI（趋势观察）"
                  value={formatPct(result.concentration.hhi_pct)}
                  detail="辅助观察集中度变化，不设单期阈值"
                />
              </div>

              <div className={SECTION_HEAD_STACK_CLASSNAME}>
                <section>
                  <SectionHead
                    category="结构集中"
                    title="业务集中度"
                    note="按YTD日均余额份额降序展示；HHI以百分比形式返回，不与传统HHI点数混用。"
                  />
                  <ConcentrationTable rows={result.concentration.rows} />
                </section>

                <section>
                  <SectionHead
                    category="持续性观察"
                    title="FTP后损益为负月份频率与最长连续期"
                    note={`滚动 ${result.negative_ftp_persistence.lookback_months} 个自然月；至少 ${result.negative_ftp_persistence.minimum_observed_months} 个已观测月份且负值月份占比达到 ${formatPct(result.negative_ftp_persistence.warning_threshold_pct)} 才提示，缺失月份不进分母并打断连续期。`}
                  />
                  <NegativeFtpTable rows={result.negative_ftp_persistence.rows} />
                </section>

                <section>
                  <SectionHead
                    category="跨期结构"
                    title="日均份额同比漂移"
                    note={`当前YTD与上年同期间 ${result.share_drift.baseline_as_of_date ?? EM_DASH} 对比；新进及退出业务缺失侧按0处理。`}
                  />
                  <ShareDriftTable
                    rows={result.share_drift.rows}
                    baselineAvailable={result.share_drift.baseline_available}
                    available={result.share_drift.available}
                    availabilityReason={result.share_drift.availability_reason}
                  />
                </section>

                <section>
                  <SectionHead
                    category="相对位置"
                    title="规模与FTP后收益相对象限"
                    note="规模轴使用日均余额份额，收益轴使用FTP后年化收益率；按当期中位数作描述性相对比较，不生成增配或压降建议。"
                  />
                  <CapitalEfficiencyQuadrantPanel summary={result.scale_yield_quadrant} />
                </section>
              </div>
                </>
              )}
            </>
          ) : null}
        </PageAsyncSection>

        {!accessDenied && contractReady && result?.reconciliation_diagnostics ? (
          <>
            <hr
              className="pnl-by-business-insights-reconciliation-divider"
              data-testid="pnl-by-business-insights-reconciliation-divider"
            />
            <div
              className="pnl-by-business-insights-reconciliation-section"
              data-testid="pnl-by-business-insights-reconciliation-section"
            >
              <span className="pnl-by-business-insights-reconciliation-eyebrow">非业务分析 · 数据链路诊断</span>
              <h2 className="pnl-by-business-insights-reconciliation-title">对账健康度诊断（非业务结论）</h2>
              <p className="pnl-by-business-insights-reconciliation-note">{RECONCILIATION_NOTE_TEXT}</p>
              {result.reconciliation_diagnostics.available ? (
                <UntracedReconciliationTrendPanel rows={result.reconciliation_diagnostics.rows} />
              ) : (
                <PageStateSurface
                  variant="empty"
                  testId="pnl-by-business-insights-reconciliation-unavailable"
                  title={
                    result.reconciliation_diagnostics.availability_reason === "source_unavailable"
                      ? "诊断源暂不可用，当前不能判断未追溯趋势"
                      : "当前窗口没有可用于诊断的正式 FI 观测"
                  }
                />
              )}
            </div>
          </>
        ) : null}
      </PageV2Shell>
    </section>
  );
}
