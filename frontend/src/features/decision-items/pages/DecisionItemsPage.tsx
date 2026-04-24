import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Select, Input, Button } from "antd";

import { useApiClient } from "../../../api/client";
import type {
  BalanceAnalysisDecisionItemStatusRow,
  BalanceAnalysisDecisionStatus,
  BalanceAnalysisSeverity,
  BalanceCurrencyBasis,
  BalancePositionScope,
  ResultMeta,
} from "../../../api/contracts";
import {
  PageHeader,
  PageSectionLead,
  pageSurfacePanelStyle,
} from "../../../components/page/PagePrimitives";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { buildDecisionItemsPageViewModel } from "../lib/decisionItemsPageModel";

const t = designTokens;

const detailPanelStyle = {
  ...pageSurfacePanelStyle,
  padding: t.space[5],
  boxShadow: t.shadow.card,
} as const;

const filterLabelStyle = {
  display: "grid",
  gap: t.space[2],
  fontSize: t.fontSize[12],
  fontWeight: 600,
  color: t.color.neutral[600],
} as const;

const filterControlStyle = {
  minWidth: 160,
} as const;

const tableStyle = {
  width: "100%",
  borderCollapse: "collapse" as const,
  fontSize: t.fontSize[13],
};

const thStyle = {
  textAlign: "left" as const,
  padding: `${t.space[2]}px ${t.space[3]}px`,
  borderBottom: `1px solid ${t.color.neutral[200]}`,
  color: t.color.neutral[600],
  fontWeight: 600,
  background: t.color.neutral[50],
};

const tdStyle = {
  padding: `${t.space[2]}px ${t.space[3]}px`,
  borderBottom: `1px solid ${t.color.neutral[100]}`,
  verticalAlign: "top" as const,
  color: t.color.neutral[900],
};

type StatusFilter = "all" | BalanceAnalysisDecisionStatus;
type SeverityFilter = "all" | BalanceAnalysisSeverity;

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
  { value: "native", label: "本币（Native）" },
];

function formatMetaLine(meta: ResultMeta | undefined) {
  if (!meta) {
    return "—";
  }
  return [
    `trace ${meta.trace_id || "—"}`,
    `source ${meta.source_version || "—"}`,
    `rule ${meta.rule_version || "—"}`,
    `cache ${meta.cache_version || "—"}`,
  ].join(" · ");
}

function resultMetaSubline(meta: ResultMeta | undefined) {
  if (!meta) {
    return null;
  }
  return `basis=${meta.basis} · quality=${meta.quality_flag} · vendor=${meta.vendor_status} · fallback=${meta.fallback_mode}`;
}

export default function DecisionItemsPage() {
  const client = useApiClient();
  const queryClient = useQueryClient();

  const [selectedReportDate, setSelectedReportDate] = useState<string | null>(null);
  const [positionScope, setPositionScope] = useState<BalancePositionScope>("all");
  const [currencyBasis, setCurrencyBasis] = useState<BalanceCurrencyBasis>("CNY");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("all");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [draftComment, setDraftComment] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [updatingKey, setUpdatingKey] = useState<string | null>(null);

  const datesQuery = useQuery({
    queryKey: ["balance-analysis", "dates"],
    queryFn: () => client.getBalanceAnalysisDates(),
  });

  const sortedDates = useMemo(() => {
    const list = datesQuery.data?.result?.report_dates ?? [];
    return [...list].sort((a, b) => a.localeCompare(b));
  }, [datesQuery.data?.result?.report_dates]);

  const defaultLatest = sortedDates.length > 0 ? sortedDates[sortedDates.length - 1]! : null;
  const reportDate = selectedReportDate ?? defaultLatest;

  const currentUserQuery = useQuery({
    queryKey: ["balance-analysis", "current-user"],
    queryFn: () => client.getBalanceAnalysisCurrentUser(),
  });

  const itemsQuery = useQuery({
    queryKey: [
      "balance-analysis-decision-items",
      reportDate,
      positionScope,
      currencyBasis,
    ],
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
    return vm.rows.filter((row) => {
      if (statusFilter !== "all" && row.latest_status?.status !== statusFilter) {
        return false;
      }
      if (severityFilter !== "all" && row.severity !== severityFilter) {
        return false;
      }
      return true;
    });
  }, [vm.rows, statusFilter, severityFilter]);

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
        await queryClient.invalidateQueries({ queryKey: ["balance-analysis-decision-items"] });
        await queryClient.invalidateQueries({ queryKey: ["balance-analysis", "current-user"] });
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
  const userLabel = currentUserQuery.data
    ? `${currentUserQuery.data.user_id}（${currentUserQuery.data.role}）`
    : "—";

  return (
    <div
      data-testid="decision-items-page"
      style={{ padding: t.space[6], background: t.color.neutral[50], minHeight: "100%" }}
    >
      <PageHeader
        eyebrow="Workbench"
        title="决策事项"
        description="按报告日与口径拉取资产负债分析「决策事项」读模型，可在此确认/忽略并写回同一路径的更新接口。"
        style={{ marginBottom: t.space[4] }}
      />

      {showMockWarning ? (
        <div
          style={{
            marginBottom: t.space[4],
            padding: t.space[3],
            borderRadius: t.radius.md,
            border: `1px solid ${t.color.warning[300]}`,
            background: t.color.warning[50],
            color: t.color.neutral[800],
            fontSize: t.fontSize[13],
          }}
        >
          当前为 mock 数据模式，决策事项与操作人回写为本地模拟，不代表生产正式结果。
        </div>
      ) : null}

      <PageSectionLead
        title="决策工作区"
        description="对规则生成的待办做集中处理，保留 trace / 规则版本与写回人信息以便审计。"
      />

      <section
        style={{
          ...detailPanelStyle,
          display: "grid",
          gap: t.space[4],
        }}
      >
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: t.space[4],
            fontSize: t.fontSize[12],
            color: t.color.neutral[700],
            alignItems: "flex-start",
          }}
        >
          <div>
            <div style={{ color: t.color.neutral[500], fontWeight: 600 }}>报告日</div>
            <div style={{ ...tabularNumsStyle, fontWeight: 600, color: t.color.neutral[900] }}>
              {reportDate || "—"}
            </div>
          </div>
          <div>
            <div style={{ color: t.color.neutral[500], fontWeight: 600 }}>数据模式</div>
            <div>{client.mode === "real" ? "正式接口（real）" : "Mock（本地模拟）"}</div>
          </div>
          <div>
            <div style={{ color: t.color.neutral[500], fontWeight: 600 }}>当前用户</div>
            <div>{userLabel}</div>
          </div>
          <div>
            <div style={{ color: t.color.neutral[500], fontWeight: 600 }}>待办</div>
            <div data-testid="decision-items-summary-pending" style={tabularNumsStyle}>
              {vm.statusCounts.pending}
            </div>
          </div>
          <div>
            <div style={{ color: t.color.neutral[500], fontWeight: 600 }}>高等级</div>
            <div data-testid="decision-items-summary-high" style={tabularNumsStyle}>
              {vm.severityCounts.high}
            </div>
          </div>
        </div>

        <div style={{ display: "grid", gap: t.space[1] }}>
          <div style={{ fontSize: t.fontSize[11], color: t.color.neutral[500], fontWeight: 600 }}>result_meta</div>
          <div style={{ fontSize: t.fontSize[12], color: t.color.neutral[800] }}>{formatMetaLine(resultMeta)}</div>
          {resultMetaSubline(resultMeta) ? (
            <div style={{ fontSize: t.fontSize[11], color: t.color.neutral[500] }}>{resultMetaSubline(resultMeta)}</div>
          ) : null}
        </div>
      </section>

      <div
        style={{
          marginTop: t.space[5],
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: t.space[4],
        }}
      >
        <label style={filterLabelStyle}>
          报告日
          <Select
            data-testid="decision-items-report-date"
            value={reportDate ?? undefined}
            disabled={datesQuery.isLoading || sortedDates.length === 0}
            options={sortedDates.map((d) => ({ value: d, label: d }))}
            onChange={(v) => setSelectedReportDate(v)}
            style={filterControlStyle}
            showSearch
            optionFilterProp="label"
            placeholder="选择报告日"
          />
        </label>
        <label style={filterLabelStyle}>
          头寸范围
          <Select
            data-testid="decision-items-position-scope"
            value={positionScope}
            onChange={(v) => setPositionScope(v as BalancePositionScope)}
            options={SCOPE_OPTIONS}
            style={filterControlStyle}
          />
        </label>
        <label style={filterLabelStyle}>
          币种口径
          <Select
            data-testid="decision-items-currency-basis"
            value={currencyBasis}
            onChange={(v) => setCurrencyBasis(v as BalanceCurrencyBasis)}
            options={CURRENCY_OPTIONS}
            style={filterControlStyle}
          />
        </label>
        <label style={filterLabelStyle}>
          状态筛选
          <Select
            data-testid="decision-items-status-filter"
            value={statusFilter}
            onChange={(v) => setStatusFilter(v as StatusFilter)}
            options={STATUS_FILTER_OPTIONS}
            style={filterControlStyle}
          />
        </label>
        <label style={filterLabelStyle}>
          严重度筛选
          <Select
            data-testid="decision-items-severity-filter"
            value={severityFilter}
            onChange={(v) => setSeverityFilter(v as SeverityFilter)}
            options={SEVERITY_FILTER_OPTIONS}
            style={filterControlStyle}
          />
        </label>
      </div>

      {((anyError && errorMessage) || actionError) ? (
        <div
          data-testid="decision-items-error"
          style={{
            marginTop: t.space[4],
            padding: t.space[3],
            borderRadius: t.radius.md,
            border: `1px solid ${t.color.semantic.loss}`,
            background: t.color.danger[50],
            color: t.color.neutral[900],
            fontSize: t.fontSize[13],
            whiteSpace: "pre-wrap",
          }}
        >
          {anyError && errorMessage ? errorMessage : null}
          {anyError && errorMessage && actionError ? "\n" : null}
          {actionError ? `更新失败：${actionError}` : null}
        </div>
      ) : null}

      {noDates ? (
        <div
          data-testid="decision-items-error"
          style={{ marginTop: t.space[4], color: t.color.neutral[700] }}
        >
          无可用报告日。请检查资产负债物化/日期服务是否已产出数据。
        </div>
      ) : null}

      {vm.contractWarnings.length > 0 ? (
        <div
          data-testid="decision-items-contract-warning"
          style={{
            marginTop: t.space[4],
            padding: t.space[3],
            borderRadius: t.radius.md,
            border: `1px solid ${t.color.warning[400]}`,
            background: t.color.warning[50],
            color: t.color.neutral[900],
            fontSize: t.fontSize[12],
            whiteSpace: "pre-wrap",
          }}
        >
          <strong>契约/质量提示</strong>
          {vm.contractWarnings.map((w, i) => (
            <div key={i} style={{ marginTop: t.space[1] }}>
              · {w}
            </div>
          ))}
        </div>
      ) : null}

      {datesQuery.isLoading || (canFetchItems && (itemsQuery.isLoading || itemsQuery.isFetching) && !itemsQuery.isError) ? (
        <p style={{ marginTop: t.space[5], color: t.color.neutral[600] }}>正在加载…</p>
      ) : null}

      {!anyError && !noDates && canFetchItems && !itemsResolving && (
        <div
          style={{
            marginTop: t.space[5],
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))",
            gap: t.space[5],
          }}
        >
          <div style={{ minWidth: 0, ...detailPanelStyle }}>
            {filteredRows.length === 0 ? (
              <div style={{ color: t.color.neutral[600], fontSize: t.fontSize[13] }}>
                {vm.rows.length === 0 ? "本报告日未返回决策事项。" : "当前筛选下无决策事项，请调整筛选或更换报告日。"}
              </div>
            ) : (
              <div data-testid="decision-items-list" style={{ overflowX: "auto" }}>
                <table style={tableStyle}>
                  <thead>
                    <tr>
                      <th style={thStyle}>标题</th>
                      <th style={thStyle}>严重度</th>
                      <th style={thStyle}>操作</th>
                      <th style={thStyle}>原因</th>
                      <th style={thStyle}>来源段落</th>
                      <th style={thStyle}>规则</th>
                      <th style={thStyle}>版本</th>
                      <th style={thStyle}>状态</th>
                      <th style={thStyle}>更新人/时间</th>
                      <th style={thStyle}> </th>
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
                          style={{
                            cursor: "pointer",
                            background: isSel ? t.color.info[50] : undefined,
                          }}
                        >
                          <td style={tdStyle}>{row.title}</td>
                          <td style={tdStyle}>{row.severity}</td>
                          <td style={tdStyle}>{row.action_label}</td>
                          <td style={tdStyle}>{row.reason}</td>
                          <td style={tdStyle}>{row.source_section}</td>
                          <td style={{ ...tdStyle, ...tabularNumsStyle }}>{row.rule_id}</td>
                          <td style={{ ...tdStyle, ...tabularNumsStyle }}>{row.rule_version}</td>
                          <td style={tdStyle}>{row.latest_status?.status}</td>
                          <td style={{ ...tdStyle, fontSize: t.fontSize[12] }}>
                            {(row.latest_status?.updated_by || "—") + " / " + (row.latest_status?.updated_at || "—")}
                          </td>
                          <td style={tdStyle}>
                            <div style={{ display: "flex", gap: t.space[2] }}>
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
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <aside data-testid="decision-items-detail" style={detailPanelStyle}>
            <h3
              style={{
                margin: `0 0 ${t.space[3]}px`,
                fontSize: t.fontSize[16],
                fontWeight: 700,
                color: t.color.neutral[900],
              }}
            >
              事项详情
            </h3>
            {!selectedRow ? (
              <p style={{ margin: 0, color: t.color.neutral[600] }}>请从列表选择一行以查看与填写备注</p>
            ) : (
              <div style={{ display: "grid", gap: t.space[3] }}>
                <div style={{ fontSize: t.fontSize[12], color: t.color.neutral[600] }}>decision_key</div>
                <div style={tabularNumsStyle}>{selectedRow.decision_key}</div>
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
                  <strong>状态</strong> {selectedRow.latest_status?.status} · 更新人 {selectedRow.latest_status?.updated_by || "—"}{" "}
                  · {selectedRow.latest_status?.updated_at || "—"}
                </div>
                <label style={filterLabelStyle}>
                  备注
                  <Input.TextArea
                    value={draftComment}
                    onChange={(e) => setDraftComment(e.target.value)}
                    rows={4}
                    placeholder="填写确认/忽略说明（会随写回一起提交，可选）"
                  />
                </label>
                <div style={{ display: "flex", gap: t.space[2] }}>
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
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
