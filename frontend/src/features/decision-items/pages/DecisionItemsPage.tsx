import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Select, Input, Button } from "antd";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { apiQueryKeys } from "../../../api/queryKeys";
import type {
  BalanceAnalysisDecisionItemStatusRow,
  BalanceAnalysisDecisionStatus,
  BalanceAnalysisSeverity,
  BalanceCurrencyBasis,
  BalancePositionScope,
  ResultMeta,
} from "../../../api/contracts";
import {
  DataStatusStrip,
  PageDecisionHero,
  PageSectionLead,
} from "../../../components/page/PagePrimitives";
import { buildDecisionItemsPageViewModel } from "../lib/decisionItemsPageModel";

import "./DecisionItemsPage.css";

import { EM_DASH } from "../../../utils/format";
type StatusFilter = "all" | BalanceAnalysisDecisionStatus;
type SeverityFilter = "all" | BalanceAnalysisSeverity;

const SEVERITY_ORDER: Record<BalanceAnalysisSeverity, number> = {
  high: 0,
  medium: 1,
  low: 2,
};

const STATUS_FILTER_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "全部状态" },
  { value: "pending", label: "待处理" },
  { value: "confirmed", label: "已确认" },
  { value: "dismissed", label: "已忽略" },
];

const SEVERITY_FILTER_OPTIONS: { value: SeverityFilter; label: string }[] = [
  { value: "all", label: "全部等级" },
  { value: "high", label: "高" },
  { value: "medium", label: "中" },
  { value: "low", label: "低" },
];

const SCOPE_OPTIONS: { value: BalancePositionScope; label: string }[] = [
  { value: "all", label: "全组合" },
  { value: "asset", label: "资产" },
  { value: "liability", label: "负债" },
];

const CURRENCY_OPTIONS: { value: BalanceCurrencyBasis; label: string }[] = [
  { value: "CNY", label: "人民币（CNY）" },
  { value: "native", label: "本币（原币）" },
];

function cleanReportDateParam(value: string | null): string | null {
  const trimmed = value?.trim() ?? "";
  return /^\d{4}-\d{2}-\d{2}$/.test(trimmed) ? trimmed : null;
}

function formatMetaLine(meta: ResultMeta | undefined) {
  if (!meta) {
    return EM_DASH;
  }
  return [
    `追踪 ${meta.trace_id || EM_DASH}`,
    `来源 ${meta.source_version || EM_DASH}`,
    `规则 ${meta.rule_version || EM_DASH}`,
    `缓存 ${meta.cache_version || EM_DASH}`,
  ].join(" · ");
}

function resultMetaBasisLabel(value: ResultMeta["basis"]): string {
  if (value === "formal") return "正式口径";
  if (value === "scenario") return "情景口径";
  if (value === "analytical") return "分析口径";
  if (value === "mock") return "演示口径";
  return value;
}

function resultMetaQualityLabel(value: ResultMeta["quality_flag"]): string {
  if (value === "ok") return "正常";
  if (value === "warning") return "预警";
  if (value === "error") return "错误";
  if (value === "stale") return "陈旧";
  return value;
}

function resultMetaVendorLabel(value: ResultMeta["vendor_status"]): string {
  if (value === "ok") return "正常";
  if (value === "vendor_stale") return "供应商数据陈旧";
  if (value === "vendor_unavailable") return "供应商不可用";
  return value;
}

function resultMetaFallbackLabel(value: ResultMeta["fallback_mode"]): string {
  if (value === "none") return "未降级";
  if (value === "latest_snapshot") return "最新快照降级";
  return value;
}

function resultMetaSubline(meta: ResultMeta | undefined) {
  if (!meta) {
    return null;
  }
  return `口径=${resultMetaBasisLabel(meta.basis)}，质量=${resultMetaQualityLabel(meta.quality_flag)}，供应商=${resultMetaVendorLabel(meta.vendor_status)}，降级=${resultMetaFallbackLabel(meta.fallback_mode)}`;
}

export default function DecisionItemsPage() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const linkedReportDate = cleanReportDateParam(searchParams.get("report_date"));
  const linkedSource = searchParams.get("source")?.trim() ?? "";
  const linkedActionId = searchParams.get("action_id")?.trim() ?? "";
  const isDashboardRiskReviewQueue =
    linkedSource === "dashboard-home" && linkedActionId === "risk-review-queue";

  const [selectedReportDate, setSelectedReportDate] = useState<string | null>(linkedReportDate);
  const [positionScope, setPositionScope] = useState<BalancePositionScope>("all");
  const [currencyBasis, setCurrencyBasis] = useState<BalanceCurrencyBasis>("CNY");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(
    isDashboardRiskReviewQueue ? "pending" : "all",
  );
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("all");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [draftComment, setDraftComment] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [updateFeedback, setUpdateFeedback] = useState<string | null>(null);
  const [updatingKey, setUpdatingKey] = useState<string | null>(null);

  useEffect(() => {
    setSelectedReportDate(linkedReportDate);
    setStatusFilter(isDashboardRiskReviewQueue ? "pending" : "all");
    setSelectedKey(null);
    setDraftComment("");
    setUpdateFeedback(null);
  }, [isDashboardRiskReviewQueue, linkedReportDate]);

  const datesQuery = useQuery({
    queryKey: apiQueryKeys.balanceAnalysisDates(client.mode),
    queryFn: () => client.getBalanceAnalysisDates(),
  });

  const sortedDates = useMemo(() => {
    const list = datesQuery.data?.result?.report_dates ?? [];
    return [...list].sort((a, b) => a.localeCompare(b));
  }, [datesQuery.data?.result?.report_dates]);

  const defaultLatest = sortedDates.length > 0 ? sortedDates[sortedDates.length - 1]! : null;
  const reportDate = selectedReportDate ?? defaultLatest;

  const currentUserQuery = useQuery({
    queryKey: ["balance-analysis", "current-user", client.mode],
    queryFn: () => client.getBalanceAnalysisCurrentUser(),
  });

  const itemsQuery = useQuery({
    queryKey: apiQueryKeys.balanceAnalysisDecisionItems(
      client.mode,
      reportDate,
      positionScope,
      currencyBasis,
    ),
    queryFn: () =>
      client.getBalanceAnalysisDecisionItems({
        reportDate: reportDate!,
        positionScope,
        currencyBasis,
      }),
    enabled: Boolean(reportDate) && sortedDates.length > 0,
  });

  const canFetchItems = Boolean(reportDate) && sortedDates.length > 0;
  const resultMeta = itemsQuery.data?.result_meta;
  const payload = itemsQuery.data?.result;
  const itemsResolving = canFetchItems && (itemsQuery.isLoading || itemsQuery.isFetching);

  const vm = useMemo(
    () =>
      buildDecisionItemsPageViewModel({
        payload: canFetchItems && !itemsQuery.isError && !itemsResolving ? payload : undefined,
        result_meta: resultMeta,
        currentUser: currentUserQuery.data,
        loading: datesQuery.isLoading || itemsResolving,
        error: canFetchItems && itemsQuery.isError,
      }),
    [
      canFetchItems,
      currentUserQuery.data,
      datesQuery.isLoading,
      itemsQuery.isError,
      itemsResolving,
      payload,
      resultMeta,
    ],
  );

  const filteredRows = useMemo(() => {
    const rows = vm.rows.filter((row) => {
      if (statusFilter !== "all" && row.latest_status?.status !== statusFilter) {
        return false;
      }
      if (severityFilter !== "all" && row.severity !== severityFilter) {
        return false;
      }
      return true;
    });
    if (!isDashboardRiskReviewQueue) {
      return rows;
    }
    return [...rows].sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]);
  }, [isDashboardRiskReviewQueue, vm.rows, statusFilter, severityFilter]);

  const selectedRow = useMemo(
    () => vm.rows.find((r) => r.decision_key === selectedKey) ?? null,
    [selectedKey, vm.rows],
  );

  useEffect(() => {
    if (selectedKey && !filteredRows.some((r) => r.decision_key === selectedKey)) {
      setSelectedKey(null);
    }
  }, [filteredRows, selectedKey]);

  useEffect(() => {
    if (selectedRow) {
      setDraftComment(selectedRow.latest_status?.comment?.trim() || "");
    } else {
      setDraftComment("");
    }
  }, [selectedKey, selectedRow]);

  const runUpdate = useCallback(
    async (row: BalanceAnalysisDecisionItemStatusRow, status: "confirmed" | "dismissed", comment: string | undefined) => {
      if (!reportDate) {
        return;
      }
      setActionError(null);
      setUpdateFeedback(null);
      setUpdatingKey(row.decision_key);
      try {
        await client.updateBalanceAnalysisDecisionStatus({
          reportDate,
          positionScope,
          currencyBasis,
          decisionKey: row.decision_key,
          status,
          comment,
        });
        await queryClient.invalidateQueries({ queryKey: ["balance-analysis", "decision-items"] });
        await queryClient.invalidateQueries({ queryKey: ["balance-analysis", "current-user"] });
        await queryClient.invalidateQueries({ queryKey: ["home-snapshot"] });
        setUpdateFeedback(`${status === "confirmed" ? "已确认" : "已忽略"}并回写：${row.title}`);
      } catch (e) {
        const message = e instanceof Error ? e.message : String(e);
        setActionError(message);
      } finally {
        setUpdatingKey(null);
      }
    },
    [client, currencyBasis, positionScope, queryClient, reportDate],
  );

  const datesError = datesQuery.isError;
  const itemsError = itemsQuery.isError;
  const anyError = datesError || itemsError;
  const errorMessage = datesError
    ? (datesQuery.error as Error)?.message || "无法加载报告日列表"
    : itemsError
      ? (itemsQuery.error as Error)?.message || "无法加载决策事项"
      : null;

  const noDates = !datesQuery.isLoading && !datesError && sortedDates.length === 0;
  const showMockWarning = client.mode === "mock";
  const decisionWriteCapability = currentUserQuery.data?.can_write_decision_status ?? null;
  const canWriteDecisionItems = decisionWriteCapability === true;
  const cannotWriteDecisionItems = Boolean(currentUserQuery.data) && decisionWriteCapability === false;
  const decisionWritePermissionUnknown =
    currentUserQuery.isError || (Boolean(currentUserQuery.data) && decisionWriteCapability === null);
  const writePermissionNotice = decisionWritePermissionUnknown
    ? {
        className: "decision-items-page__permission-unknown",
        testId: "decision-items-permission-unknown",
        text: "权限状态暂不可用，暂不开放确认或忽略回写。",
      }
    : cannotWriteDecisionItems
      ? {
          className: "decision-items-page__readonly-notice",
          testId: "decision-items-readonly-notice",
          text: "当前用户无治理事项回写权限，仅可查看队列与证据。",
        }
      : null;
  const userLabel = currentUserQuery.data
    ? `${currentUserQuery.data.user_id}（${currentUserQuery.data.role}）`
    : EM_DASH;

  return (
    <div
      className="decision-items-page theme-dh-api"
      data-moss-theme-scope="decision-items"
      data-testid="decision-items-page"
    >
      <PageDecisionHero
        testId="decision-items-contract-hero"
        title="决策事项"
        titleTestId="decision-items-page-title"
        questionTestId="decision-items-page-subtitle"
        eyebrow="工作台"
        reportDateSlot={
          <span data-testid="decision-items-report-date-slot">
            报告日 <strong className="decision-items-page__mono">{reportDate || EM_DASH}</strong>
          </span>
        }
        businessQuestion="按报告日与口径拉取资产负债分析「决策事项」读模型，可在此确认/忽略并写回同一路径的更新接口。"
        className="decision-items-page__hero"
        actions={
          <span className="decision-items-page__mode-badge" data-mode={client.mode}>
            {client.mode === "real" ? "正式只读链路" : "本地演示数据"}
          </span>
        }
      >
        <div className="decision-items-page__hero-status">
          <DataStatusStrip testId="decision-items-data-status-strip">
            <div className="decision-items-page__status-row">
              <span className="decision-items-page__status-copy">
                模式 {client.mode === "real" ? "real" : "mock"} · 操作人 {userLabel}
              </span>
            </div>
            {isDashboardRiskReviewQueue ? (
              <div className="decision-items-page__entry-context" data-testid="decision-items-entry-context">
                来自首页风险复核队列 · 默认聚焦待处理事项，高风险优先
              </div>
            ) : null}
            {writePermissionNotice ? (
              <div className={writePermissionNotice.className} data-testid={writePermissionNotice.testId}>
                {writePermissionNotice.text}
              </div>
            ) : null}
            {showMockWarning ? (
              <div className="decision-items-page__mock-warning">
                当前为 mock 数据模式，决策事项与操作人回写为本地模拟，不代表生产正式结果。
              </div>
            ) : null}
          </DataStatusStrip>
        </div>
      </PageDecisionHero>

      <PageSectionLead
        eyebrow="治理"
        title="决策工作区"
        description="对规则生成的待办做集中处理，保留追踪编号、规则版本与写回人信息以便审计。"
      />

      <section className="decision-items-page__summary-panel">
        <div className="decision-items-page__summary-grid">
          <div>
            <div className="decision-items-page__summary-label">报告日</div>
            <div className="decision-items-page__summary-value decision-items-page__mono">
              {reportDate || EM_DASH}
            </div>
          </div>
          <div>
            <div className="decision-items-page__summary-label">数据模式</div>
            <div>{client.mode === "real" ? "正式接口" : "本地模拟"}</div>
          </div>
          <div>
            <div className="decision-items-page__summary-label">当前用户</div>
            <div>{userLabel}</div>
          </div>
          <div>
            <div className="decision-items-page__summary-label">待办</div>
            <div data-testid="decision-items-summary-pending" className="decision-items-page__mono">
              {vm.statusCounts.pending}
            </div>
          </div>
          <div>
            <div className="decision-items-page__summary-label">高等级</div>
            <div data-testid="decision-items-summary-high" className="decision-items-page__mono">
              {vm.severityCounts.high}
            </div>
          </div>
        </div>

        <div className="decision-items-page__meta-block">
          <div className="decision-items-page__meta-label">结果元信息</div>
          <div className="decision-items-page__meta-line">{formatMetaLine(resultMeta)}</div>
          {resultMetaSubline(resultMeta) ? (
            <div className="decision-items-page__meta-subline">{resultMetaSubline(resultMeta)}</div>
          ) : null}
        </div>
      </section>

      <div className="decision-items-page__filter-grid">
        <label className="decision-items-page__filter-label">
          报告日
          <Select
            data-testid="decision-items-report-date"
            value={reportDate ?? undefined}
            disabled={datesQuery.isLoading || sortedDates.length === 0}
            options={sortedDates.map((d) => ({ value: d, label: d }))}
            onChange={(v) => setSelectedReportDate(v)}
            className="decision-items-page__filter-control"
            showSearch
            optionFilterProp="label"
            placeholder="选择报告日"
          />
        </label>
        <label className="decision-items-page__filter-label">
          头寸范围
          <Select
            data-testid="decision-items-position-scope"
            value={positionScope}
            onChange={(v) => setPositionScope(v as BalancePositionScope)}
            options={SCOPE_OPTIONS}
            className="decision-items-page__filter-control"
          />
        </label>
        <label className="decision-items-page__filter-label">
          币种口径
          <Select
            data-testid="decision-items-currency-basis"
            value={currencyBasis}
            onChange={(v) => setCurrencyBasis(v as BalanceCurrencyBasis)}
            options={CURRENCY_OPTIONS}
            className="decision-items-page__filter-control"
          />
        </label>
        <label className="decision-items-page__filter-label">
          状态筛选
          <Select
            data-testid="decision-items-status-filter"
            value={statusFilter}
            onChange={(v) => setStatusFilter(v as StatusFilter)}
            options={STATUS_FILTER_OPTIONS}
            className="decision-items-page__filter-control"
          />
        </label>
        <label className="decision-items-page__filter-label">
          严重度筛选
          <Select
            data-testid="decision-items-severity-filter"
            value={severityFilter}
            onChange={(v) => setSeverityFilter(v as SeverityFilter)}
            options={SEVERITY_FILTER_OPTIONS}
            className="decision-items-page__filter-control"
          />
        </label>
      </div>

      {((anyError && errorMessage) || actionError) ? (
        <div data-testid="decision-items-error" className="decision-items-page__alert" data-tone="danger">
          {anyError && errorMessage ? errorMessage : null}
          {anyError && errorMessage && actionError ? "\n" : null}
          {actionError ? `更新失败：${actionError}` : null}
        </div>
      ) : null}

      {updateFeedback ? (
        <div className="decision-items-page__update-feedback" data-testid="decision-items-update-feedback">
          {updateFeedback}
        </div>
      ) : null}

      {noDates ? (
        <div data-testid="decision-items-error" className="decision-items-page__empty-note">
          无可用报告日。请检查资产负债物化/日期服务是否已产出数据。
        </div>
      ) : null}

      {vm.contractWarnings.length > 0 ? (
        <div data-testid="decision-items-contract-warning" className="decision-items-page__alert" data-tone="warning">
          <strong>契约/质量提示</strong>
          {vm.contractWarnings.map((w, i) => (
            <div key={i} className="decision-items-page__alert-line">
              · {w}
            </div>
          ))}
        </div>
      ) : null}

      {datesQuery.isLoading || (canFetchItems && (itemsQuery.isLoading || itemsQuery.isFetching) && !itemsQuery.isError) ? (
        <p className="decision-items-page__loading-note">正在加载...</p>
      ) : null}

      {!anyError && !noDates && canFetchItems && !itemsResolving && (
        <div className="decision-items-page__content-grid">
          <div className="decision-items-page__list-panel">
            {filteredRows.length === 0 ? (
              <div className="decision-items-page__empty-note">
                {vm.rows.length === 0 ? "本报告日未返回决策事项。" : "当前筛选下无决策事项，请调整筛选或更换报告日。"}
              </div>
            ) : (
              <div data-testid="decision-items-list" className="decision-items-page__table-scroll">
                <table className="decision-items-page__table">
                  <thead>
                    <tr>
                      <th className="decision-items-page__table-head-cell">标题</th>
                      <th className="decision-items-page__table-head-cell">严重度</th>
                      <th className="decision-items-page__table-head-cell">操作</th>
                      <th className="decision-items-page__table-head-cell">原因</th>
                      <th className="decision-items-page__table-head-cell">来源段落</th>
                      <th className="decision-items-page__table-head-cell">规则</th>
                      <th className="decision-items-page__table-head-cell">版本</th>
                      <th className="decision-items-page__table-head-cell">状态</th>
                      <th className="decision-items-page__table-head-cell">更新人/时间</th>
                      <th className="decision-items-page__table-head-cell"> </th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.map((row, index) => {
                      const isSel = selectedKey === row.decision_key;
                      const busy = updatingKey === row.decision_key;
                      return (
                        <tr
                          key={row.decision_key}
                          data-testid={`decision-items-row-${index}`}
                          onClick={() => setSelectedKey(row.decision_key)}
                          className="decision-items-page__table-row"
                          data-selected={isSel ? "true" : undefined}
                        >
                          <td className="decision-items-page__table-cell">{row.title}</td>
                          <td className="decision-items-page__table-cell">{row.severity}</td>
                          <td className="decision-items-page__table-cell">{row.action_label}</td>
                          <td className="decision-items-page__table-cell">{row.reason}</td>
                          <td className="decision-items-page__table-cell">{row.source_section}</td>
                          <td className="decision-items-page__table-cell decision-items-page__mono">{row.rule_id}</td>
                          <td className="decision-items-page__table-cell decision-items-page__mono">{row.rule_version}</td>
                          <td className="decision-items-page__table-cell">{row.latest_status?.status}</td>
                          <td className="decision-items-page__table-cell decision-items-page__table-cell--small">
                            {(row.latest_status?.updated_by || EM_DASH) + " / " + (row.latest_status?.updated_at || EM_DASH)}
                          </td>
                          <td className="decision-items-page__table-cell">
                            {canWriteDecisionItems ? (
                              <div className="decision-items-page__button-row">
                                <Button
                                  size="small"
                                  data-testid={`decision-items-confirm-${index}`}
                                  type="primary"
                                  disabled={busy}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    const comment =
                                      row.decision_key === selectedKey
                                        ? draftComment.trim() || undefined
                                        : row.latest_status?.comment?.trim() || undefined;
                                    void runUpdate(row, "confirmed", comment);
                                  }}
                                >
                                  确认
                                </Button>
                                <Button
                                  size="small"
                                  data-testid={`decision-items-dismiss-${index}`}
                                  disabled={busy}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    const comment =
                                      row.decision_key === selectedKey
                                        ? draftComment.trim() || undefined
                                        : row.latest_status?.comment?.trim() || undefined;
                                    void runUpdate(row, "dismissed", comment);
                                  }}
                                >
                                  忽略
                                </Button>
                              </div>
                            ) : (
                              <span
                                className="decision-items-page__readonly-inline"
                                data-testid={`decision-items-readonly-${index}`}
                              >
                                只读
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <aside data-testid="decision-items-detail" className="decision-items-page__detail-panel">
            <h3 className="decision-items-page__detail-title">
              事项详情
            </h3>
            {!selectedRow ? (
              <p className="decision-items-page__empty-note">请选择一行查看详情。</p>
            ) : (
              <div className="decision-items-page__detail-stack">
                <div className="decision-items-page__detail-label">decision_key</div>
                <div className="decision-items-page__mono">{selectedRow.decision_key}</div>
                <div>
                  <strong>标题</strong> {selectedRow.title}
                </div>
                <div>
                  <strong>严重度</strong> {selectedRow.severity}
                </div>
                <div>
                  <strong>操作</strong> {selectedRow.action_label}
                </div>
                <div>
                  <strong>原因</strong> {selectedRow.reason}
                </div>
                <div>
                  <strong>来源</strong> {selectedRow.source_section}
                </div>
                <div>
                  <strong>规则</strong> {selectedRow.rule_id} @ {selectedRow.rule_version}
                </div>
                <div>
                  <strong>状态</strong> {selectedRow.latest_status?.status} · 更新人 {selectedRow.latest_status?.updated_by || EM_DASH}{" "}
                  · {selectedRow.latest_status?.updated_at || EM_DASH}
                </div>
                <label className="decision-items-page__filter-label">
                  备注
                  <Input.TextArea
                    value={draftComment}
                    onChange={(e) => setDraftComment(e.target.value)}
                    rows={4}
                    placeholder="填写确认/忽略说明（会随写回一起提交，可选）"
                  />
                </label>
                {canWriteDecisionItems ? (
                  <div className="decision-items-page__button-row">
                    <Button
                      type="primary"
                      disabled={updatingKey === selectedRow.decision_key}
                      onClick={() => void runUpdate(selectedRow, "confirmed", draftComment.trim() || undefined)}
                    >
                      确认
                    </Button>
                    <Button
                      disabled={updatingKey === selectedRow.decision_key}
                      onClick={() => void runUpdate(selectedRow, "dismissed", draftComment.trim() || undefined)}
                    >
                      忽略
                    </Button>
                  </div>
                ) : (
                  <div className={writePermissionNotice?.className ?? "decision-items-page__readonly-notice"}>
                    {writePermissionNotice?.text ?? "当前用户无治理事项回写权限，仅可查看队列与证据。"}
                  </div>
                )}
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
