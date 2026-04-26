import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { runPollingTask } from "../../../app/jobs/polling";
import { useApiClient } from "../../../api/client";
import { FilterBar } from "../../../components/FilterBar";
import type {
  ProductCategoryManualAdjustmentQuery,
  ProductCategoryManualAdjustmentRequest,
} from "../../../api/contracts";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import MonthlyOperatingAnalysisAuditPage from "./MonthlyOperatingAnalysisAuditPage";
import { nextDefaultReportDateIfUnset } from "./productCategoryPnlPageModel";
import { buildProductCategoryAuditListExportQuery } from "./productCategoryAdjustmentAuditPageModel";

const pageHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: 16,
  padding: 20,
  borderRadius: 18,
  border: "1px solid #d7dfea",
  background: "#fbfcfe",
  marginBottom: 18,
} as const;

const modeBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "8px 12px",
  borderRadius: 999,
  background: "#edf3ff",
  color: "#1f5eff",
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
} as const;

const sectionLeadWrapStyle = {
  display: "grid",
  gap: 6,
  marginBottom: 14,
} as const;

const sectionEyebrowStyle = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#8090a8",
} as const;

const sectionTitleStyle = {
  margin: 0,
  fontSize: 18,
  fontWeight: 600,
  color: "#162033",
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 900,
  color: "#5c6b82",
  fontSize: 13,
  lineHeight: 1.7,
} as const;

const DEFAULT_FILTERS: ProductCategoryManualAdjustmentQuery = {
  adjustmentId: "",
  adjustmentIdExact: false,
  accountCode: "",
  approvalStatus: "",
  eventType: "",
  currentSortField: "created_at",
  currentSortDir: "desc",
  eventSortField: "created_at",
  eventSortDir: "desc",
  createdAtFrom: "",
  createdAtTo: "",
};

const PAGE_SIZE_OPTIONS = [2, 10, 20, 50];
const CURRENT_SORT_FIELD_OPTIONS = [
  { value: "created_at", label: "created_at" },
  { value: "adjustment_id", label: "adjustment_id" },
  { value: "approval_status", label: "approval_status" },
  { value: "account_code", label: "account_code" },
] as const;
const EVENT_SORT_FIELD_OPTIONS = [
  { value: "created_at", label: "created_at" },
  { value: "adjustment_id", label: "adjustment_id" },
  { value: "event_type", label: "event_type" },
  { value: "approval_status", label: "approval_status" },
  { value: "account_code", label: "account_code" },
] as const;
const SORT_DIRECTION_OPTIONS = [
  { value: "desc", label: "desc" },
  { value: "asc", label: "asc" },
] as const;
const SHARED_QUERY_FILTER_KEYS = [
  "adjustmentId",
  "adjustmentIdExact",
  "accountCode",
  "approvalStatus",
  "createdAtFrom",
  "createdAtTo",
] as const satisfies readonly (keyof ProductCategoryManualAdjustmentQuery)[];
const CURRENT_QUERY_FILTER_KEYS = [
  ...SHARED_QUERY_FILTER_KEYS,
  "currentSortField",
  "currentSortDir",
] as const satisfies readonly (keyof ProductCategoryManualAdjustmentQuery)[];
const EVENT_QUERY_FILTER_KEYS = [
  ...SHARED_QUERY_FILTER_KEYS,
  "eventType",
  "eventSortField",
  "eventSortDir",
] as const satisfies readonly (keyof ProductCategoryManualAdjustmentQuery)[];

function buildAdjustmentDraft(reportDate: string): ProductCategoryManualAdjustmentRequest {
  return {
    report_date: reportDate,
    operator: "DELTA",
    approval_status: "approved",
    account_code: "",
    currency: "CNX",
    account_name: "",
    beginning_balance: null,
    ending_balance: null,
    monthly_pnl: null,
    daily_avg_balance: null,
    annual_avg_balance: null,
  };
}

/**
 * Feeds the API response string into a download `Blob` as a single part.
 * The audit page does not parse numbers, reformat values, or prepend a UTF-8 BOM; any BOM
 * is whatever the server returned (if any) and is out of band for this helper.
 */
function downloadAuditCsv(
  filename: string,
  content: string,
) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function hasValueChanged(
  left: string | number | boolean | undefined,
  right: string | number | boolean | undefined,
) {
  return (left ?? "") !== (right ?? "");
}

function didFiltersChange<K extends keyof ProductCategoryManualAdjustmentQuery>(
  left: ProductCategoryManualAdjustmentQuery,
  right: ProductCategoryManualAdjustmentQuery,
  keys: readonly K[],
) {
  return keys.some((key) => hasValueChanged(left[key], right[key]));
}

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
  testId?: string;
}) {
  return (
    <div data-testid={props.testId} style={sectionLeadWrapStyle}>
      <span style={sectionEyebrowStyle}>{props.eyebrow}</span>
      <h2 style={sectionTitleStyle}>{props.title}</h2>
      <p style={sectionDescriptionStyle}>{props.description}</p>
    </div>
  );
}

function LegacyProductCategoryAdjustmentAuditBody() {
  const client = useApiClient();
  const [selectedDate, setSelectedDate] = useState("");
  const [showManualForm, setShowManualForm] = useState(false);
  const [editingAdjustmentId, setEditingAdjustmentId] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [adjustmentError, setAdjustmentError] = useState<string | null>(null);
  const [lastRefreshRunId, setLastRefreshRunId] = useState<string | null>(null);
  const [lastAdjustmentId, setLastAdjustmentId] = useState<string | null>(null);
  const [draft, setDraft] = useState<ProductCategoryManualAdjustmentRequest>(
    buildAdjustmentDraft(""),
  );
  const [filterDraft, setFilterDraft] = useState<ProductCategoryManualAdjustmentQuery>(
    DEFAULT_FILTERS,
  );
  const [appliedFilters, setAppliedFilters] = useState<ProductCategoryManualAdjustmentQuery>(
    DEFAULT_FILTERS,
  );
  const [currentLimit, setCurrentLimit] = useState(20);
  const [currentOffset, setCurrentOffset] = useState(0);
  const [eventLimit, setEventLimit] = useState(20);
  const [eventOffset, setEventOffset] = useState(0);

  const datesQuery = useQuery({
    queryKey: ["product-category-audit", "dates", client.mode],
    queryFn: () => client.getProductCategoryDates(),
    retry: false,
  });

  useEffect(() => {
    const next = nextDefaultReportDateIfUnset(selectedDate, datesQuery.data?.result.report_dates);
    if (next !== null) {
      setSelectedDate(next);
    }
  }, [datesQuery.data, selectedDate]);

  useEffect(() => {
    setDraft((current) => ({
      ...current,
      report_date: selectedDate,
    }));
    setCurrentOffset(0);
    setEventOffset(0);
  }, [selectedDate]);

  const adjustmentsQuery = useQuery({
    queryKey: [
      "product-category-audit",
      "adjustments",
      client.mode,
      selectedDate,
      appliedFilters.adjustmentId ?? "",
      String(appliedFilters.adjustmentIdExact ?? false),
      appliedFilters.accountCode ?? "",
      appliedFilters.approvalStatus ?? "",
      appliedFilters.eventType ?? "",
      appliedFilters.currentSortField ?? "",
      appliedFilters.currentSortDir ?? "",
      appliedFilters.eventSortField ?? "",
      appliedFilters.eventSortDir ?? "",
      appliedFilters.createdAtFrom ?? "",
      appliedFilters.createdAtTo ?? "",
      currentLimit,
      currentOffset,
      eventLimit,
      eventOffset,
    ],
    queryFn: () =>
      client.getProductCategoryManualAdjustments(selectedDate, {
        ...appliedFilters,
        adjustmentLimit: currentLimit,
        adjustmentOffset: currentOffset,
        limit: eventLimit,
        offset: eventOffset,
      }),
    enabled: Boolean(selectedDate),
    retry: false,
  });

  function applyAuditQuery(nextFilters: ProductCategoryManualAdjustmentQuery) {
    const currentChanged = didFiltersChange(
      nextFilters,
      appliedFilters,
      CURRENT_QUERY_FILTER_KEYS,
    );
    const eventChanged = didFiltersChange(
      nextFilters,
      appliedFilters,
      EVENT_QUERY_FILTER_KEYS,
    );

    if (currentChanged) {
      setCurrentOffset(0);
    }
    if (eventChanged) {
      setEventOffset(0);
    }
    setAppliedFilters(nextFilters);
  }

  async function runRefreshWorkflow() {
    const payload = await runPollingTask({
      start: () => client.refreshProductCategoryPnl(),
      getStatus: (runId) => client.getProductCategoryRefreshStatus(runId),
    });
    setLastRefreshRunId(payload.run_id);
    if (payload.status !== "completed") {
      throw new Error(payload.detail ?? `刷新任务未完成：${payload.status}`);
    }
    await datesQuery.refetch();
    await adjustmentsQuery.refetch();
  }

  async function handleRefresh() {
    setAdjustmentError(null);
    setIsRefreshing(true);
    try {
      await runRefreshWorkflow();
    } catch (error) {
      setAdjustmentError(error instanceof Error ? error.message : "刷新损益数据失败");
    } finally {
      setIsRefreshing(false);
    }
  }

  function updateField<K extends keyof ProductCategoryManualAdjustmentRequest>(
    key: K,
    value: ProductCategoryManualAdjustmentRequest[K],
  ) {
    setDraft((current) => ({
      ...current,
      [key]: value,
    }));
  }

  function updateFilter<K extends keyof ProductCategoryManualAdjustmentQuery>(
    key: K,
    value: ProductCategoryManualAdjustmentQuery[K],
  ) {
    setFilterDraft((current) => ({
      ...current,
      [key]: value,
    }));
  }

  async function handleSubmit() {
    setAdjustmentError(null);
    if (!draft.report_date || !draft.account_code.trim()) {
      setAdjustmentError("请填写报表日期和科目代码。");
      return;
    }
    if (
      !draft.beginning_balance &&
      !draft.ending_balance &&
      !draft.monthly_pnl &&
      !draft.daily_avg_balance &&
      !draft.annual_avg_balance
    ) {
      setAdjustmentError("至少填写一个调整数值。");
      return;
    }

    setIsRefreshing(true);
    try {
      const payload = editingAdjustmentId
        ? await client.updateProductCategoryManualAdjustment(editingAdjustmentId, draft)
        : await client.createProductCategoryManualAdjustment(draft);
      setLastAdjustmentId(payload.adjustment_id);
      await runRefreshWorkflow();
      setShowManualForm(false);
      setEditingAdjustmentId(null);
      setDraft(buildAdjustmentDraft(selectedDate));
    } catch (error) {
      setAdjustmentError(error instanceof Error ? error.message : "保存手工调整失败");
    } finally {
      setIsRefreshing(false);
    }
  }

  async function handleRevoke(adjustmentId: string) {
    setAdjustmentError(null);
    setIsRefreshing(true);
    try {
      await client.revokeProductCategoryManualAdjustment(adjustmentId);
      await runRefreshWorkflow();
    } catch (error) {
      setAdjustmentError(error instanceof Error ? error.message : "撤销失败");
    } finally {
      setIsRefreshing(false);
    }
  }

  async function handleRestore(adjustmentId: string) {
    setAdjustmentError(null);
    setIsRefreshing(true);
    try {
      await client.restoreProductCategoryManualAdjustment(adjustmentId);
      await runRefreshWorkflow();
    } catch (error) {
      setAdjustmentError(error instanceof Error ? error.message : "恢复失败");
    } finally {
      setIsRefreshing(false);
    }
  }

  const currentTotal = adjustmentsQuery.data?.adjustment_count ?? 0;
  const currentCanPrev = currentOffset > 0;
  const currentCanNext = currentOffset + currentLimit < currentTotal;
  const eventTotal = adjustmentsQuery.data?.event_total ?? 0;
  const eventCanPrev = eventOffset > 0;
  const eventCanNext = eventOffset + eventLimit < eventTotal;

  async function handleExport() {
    try {
      const payload = await client.exportProductCategoryManualAdjustmentsCsv(
        selectedDate,
        buildProductCategoryAuditListExportQuery(appliedFilters),
      );
      downloadAuditCsv(payload.filename, payload.content);
    } catch (error) {
      setAdjustmentError(error instanceof Error ? error.message : "导出审计失败");
    }
  }

  return (
    <section data-testid="product-category-audit-page">
      <div style={pageHeaderStyle}>
        <div>
          <h1 data-testid="product-category-audit-page-title" style={{ margin: 0, fontSize: 28, fontWeight: 700 }}>产品损益调整审计</h1>
          <p data-testid="product-category-audit-boundary-copy" style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 14 }}>
            查看产品类别损益的手工调整当前状态、完整事件时间线和刷新结果。
          </p>
          <p style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 12 }}>
            Audit view records adjustment events and refresh evidence; it does not mutate formal read models directly.
          </p>
          {lastRefreshRunId ? (
            <p style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 12 }}>
              最近刷新任务：{lastRefreshRunId}
            </p>
          ) : null}
          {lastAdjustmentId ? (
            <p style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 12 }}>
              最近录入调整：{lastAdjustmentId}
            </p>
          ) : null}
          {adjustmentError ? (
            <p style={{ marginTop: 8, marginBottom: 0, color: "#b42318", fontSize: 12 }}>
              {adjustmentError}
            </p>
          ) : null}
        </div>
        <FilterBar style={{ justifyContent: "flex-end" }}>
          <span style={modeBadgeStyle}>
            {client.mode === "real" ? "正式只读链路" : "本地离线契约回放"}
          </span>
          <a href="/product-category-pnl">返回产品损益页</a>
          <button
            type="button"
            data-testid="audit-export-button"
            onClick={() => void handleExport()}
            disabled={adjustmentsQuery.isLoading}
          >
            导出审计
          </button>
          <button
            type="button"
            data-testid="audit-manual-button"
            onClick={() => {
              setShowManualForm((current) => !current);
              setEditingAdjustmentId(null);
              setAdjustmentError(null);
            }}
          >
            + 手工录入
          </button>
          <button
            type="button"
            data-testid="audit-refresh-button"
            disabled={isRefreshing}
            onClick={() => void handleRefresh()}
          >
            {isRefreshing ? "刷新中..." : "刷新损益数据"}
          </button>
        </FilterBar>
      </div>

      <SectionLead
        eyebrow="Filters"
        title="审计筛选与排序"
        description="筛选条件只驱动调整审计查询、分页和导出请求，不改变产品类别损益 formal baseline。"
        testId="product-category-audit-filter-lead"
      />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(5, minmax(0, 1fr))",
          gap: 12,
          marginBottom: 18,
          padding: 18,
          borderRadius: 18,
          border: "1px solid #d7dfea",
          background: "#fbfcfe",
        }}
      >
        <label style={{ display: "grid", gap: 8 }}>
          选择报表月份
          <select
            aria-label="审计-报表月份"
            value={selectedDate}
            onChange={(event) => setSelectedDate(event.target.value)}
          >
            {(datesQuery.data?.result.report_dates ?? []).map((reportDate) => (
              <option key={reportDate} value={reportDate}>
                {reportDate}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "grid", gap: 8 }}>
          调整ID
          <input
            data-testid="audit-filter-adjustment-id"
            value={filterDraft.adjustmentId ?? ""}
            onChange={(event) => updateFilter("adjustmentId", event.target.value)}
          />
        </label>
        <label style={{ display: "grid", gap: 8 }}>
          科目代码
          <input
            data-testid="audit-filter-account-code"
            value={filterDraft.accountCode ?? ""}
            onChange={(event) => updateFilter("accountCode", event.target.value)}
          />
        </label>
        <label style={{ display: "grid", gap: 8 }}>
          审批状态
          <select
            data-testid="audit-filter-approval-status"
            value={filterDraft.approvalStatus ?? ""}
            onChange={(event) => updateFilter("approvalStatus", event.target.value)}
          >
            <option value="">全部</option>
            <option value="approved">approved</option>
            <option value="pending">pending</option>
            <option value="rejected">rejected</option>
          </select>
        </label>
        <label style={{ display: "grid", gap: 8 }}>
          事件类型
          <select
            data-testid="audit-filter-event-type"
            value={filterDraft.eventType ?? ""}
            onChange={(event) => updateFilter("eventType", event.target.value)}
          >
            <option value="">全部</option>
            <option value="created">created</option>
            <option value="edited">edited</option>
            <option value="revoked">revoked</option>
            <option value="restored">restored</option>
          </select>
        </label>
        <label style={{ display: "grid", gap: 8 }}>
          Current sort field
          <select
            data-testid="audit-current-sort-field"
            value={filterDraft.currentSortField ?? "created_at"}
            onChange={(event) =>
              updateFilter(
                "currentSortField",
                event.target.value as ProductCategoryManualAdjustmentQuery["currentSortField"],
              )
            }
          >
            {CURRENT_SORT_FIELD_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "grid", gap: 8 }}>
          Current sort dir
          <select
            data-testid="audit-current-sort-dir"
            value={filterDraft.currentSortDir ?? "desc"}
            onChange={(event) =>
              updateFilter(
                "currentSortDir",
                event.target.value as ProductCategoryManualAdjustmentQuery["currentSortDir"],
              )
            }
          >
            {SORT_DIRECTION_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "grid", gap: 8 }}>
          Event sort field
          <select
            data-testid="audit-event-sort-field"
            value={filterDraft.eventSortField ?? "created_at"}
            onChange={(event) =>
              updateFilter(
                "eventSortField",
                event.target.value as ProductCategoryManualAdjustmentQuery["eventSortField"],
              )
            }
          >
            {EVENT_SORT_FIELD_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "grid", gap: 8 }}>
          Event sort dir
          <select
            data-testid="audit-event-sort-dir"
            value={filterDraft.eventSortDir ?? "desc"}
            onChange={(event) =>
              updateFilter(
                "eventSortDir",
                event.target.value as ProductCategoryManualAdjustmentQuery["eventSortDir"],
              )
            }
          >
            {SORT_DIRECTION_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "grid", gap: 8 }}>
          created_at from (UTC)
          <input
            data-testid="audit-created-at-from"
            placeholder="UTC，ISO 8601，例 2006-01-02T15:04:05Z"
            value={filterDraft.createdAtFrom ?? ""}
            onChange={(event) => updateFilter("createdAtFrom", event.target.value)}
          />
        </label>
        <label style={{ display: "grid", gap: 8 }}>
          created_at to (UTC)
          <input
            data-testid="audit-created-at-to"
            placeholder="UTC，ISO 8601，例 2006-01-02T23:59:59Z"
            value={filterDraft.createdAtTo ?? ""}
            onChange={(event) => updateFilter("createdAtTo", event.target.value)}
          />
        </label>
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            paddingTop: 26,
          }}
        >
          <input
            type="checkbox"
            data-testid="audit-exact-adjustment-id"
            checked={Boolean(filterDraft.adjustmentIdExact)}
            onChange={(event) => updateFilter("adjustmentIdExact", event.target.checked)}
          />
          调整ID精确匹配
        </label>
        <label style={{ display: "grid", gap: 8 }}>
          每页事件数
          <select
            data-testid="audit-page-size-select"
            value={String(eventLimit)}
            onChange={(event) => {
              setEventLimit(Number(event.target.value));
              setEventOffset(0);
            }}
          >
            {PAGE_SIZE_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <div style={{ display: "flex", alignItems: "end" }}>
          <button
            type="button"
            data-testid="audit-apply-filters"
            onClick={() => applyAuditQuery(filterDraft)}
          >
            应用筛选
          </button>
        </div>
        <div style={{ display: "flex", alignItems: "end" }}>
          <button
            type="button"
            data-testid="audit-reset-time-range"
            onClick={() => {
              const nextFilters = {
                ...filterDraft,
                createdAtFrom: "",
                createdAtTo: "",
              };
              setFilterDraft(nextFilters);
              applyAuditQuery(nextFilters);
            }}
          >
            重置时间范围
          </button>
        </div>
      </div>

      <SectionLead
        eyebrow="Workflow"
        title="手工调整录入"
        description="手工调整继续走既有 create / update / refresh workflow；本区只记录调整事件，不在前端写入正式结果。"
        testId="product-category-audit-manual-lead"
      />
      {showManualForm ? (
        <div
          data-testid="audit-manual-form"
          style={{
            display: "grid",
            gap: 12,
            marginBottom: 18,
            padding: 18,
            borderRadius: 18,
            border: "1px solid #d7dfea",
            background: "#fbfcfe",
          }}
        >
          <div style={{ fontWeight: 600 }}>
            {editingAdjustmentId ? "编辑手工调整" : "新建手工调整"}
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
              gap: 12,
            }}
          >
            <label style={{ display: "grid", gap: 6 }}>
              报表日期
              <input aria-label="审计-报表日期" value={draft.report_date} readOnly />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              操作方式
              <select
                aria-label="审计-操作方式"
                value={draft.operator}
                onChange={(event) =>
                  updateField("operator", event.target.value as "ADD" | "DELTA" | "OVERRIDE")
                }
              >
                <option value="ADD">ADD</option>
                <option value="DELTA">DELTA</option>
                <option value="OVERRIDE">OVERRIDE</option>
              </select>
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              币种
              <select
                aria-label="审计-币种"
                value={draft.currency}
                onChange={(event) =>
                  updateField("currency", event.target.value as "CNX" | "CNY")
                }
              >
                <option value="CNX">CNX</option>
                <option value="CNY">CNY</option>
              </select>
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              科目代码
              <input
                aria-label="审计-科目代码"
                value={draft.account_code}
                onChange={(event) => updateField("account_code", event.target.value)}
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              科目名称
              <input
                aria-label="审计-科目名称"
                value={draft.account_name ?? ""}
                onChange={(event) => updateField("account_name", event.target.value)}
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              审批状态
              <select
                aria-label="审计-审批状态"
                value={draft.approval_status}
                onChange={(event) =>
                  updateField(
                    "approval_status",
                    event.target.value as "approved" | "pending" | "rejected",
                  )
                }
              >
                <option value="approved">approved</option>
                <option value="pending">pending</option>
                <option value="rejected">rejected</option>
              </select>
            </label>
            {[
              ["beginning_balance", "期初余额"],
              ["ending_balance", "期末余额"],
              ["monthly_pnl", "月度损益"],
              ["daily_avg_balance", "月日均"],
              ["annual_avg_balance", "年日均"],
            ].map(([field, label]) => (
              <label key={field} style={{ display: "grid", gap: 6 }}>
                {label}
                <input
                  aria-label={`审计-${label}`}
                  value={(draft as Record<string, string | null | undefined>)[field] ?? ""}
                  onChange={(event) =>
                    updateField(
                      field as keyof ProductCategoryManualAdjustmentRequest,
                      event.target.value || null,
                    )
                  }
                />
              </label>
            ))}
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <button
              type="button"
              data-testid="audit-manual-submit"
              onClick={() => void handleSubmit()}
              disabled={isRefreshing}
            >
              {editingAdjustmentId ? "保存并刷新" : "提交并刷新"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowManualForm(false);
                setEditingAdjustmentId(null);
                setDraft(buildAdjustmentDraft(selectedDate));
              }}
            >
              取消
            </button>
          </div>
        </div>
      ) : null}

      <SectionLead
        eyebrow="Timeline"
        title="调整审计时间线"
        description="当前状态和完整事件时间线分开展示，保留现有 current / event pagination、排序和导出语义。与主页面一致：仅当审批通过可撤销、仅当已拒绝可恢复；进行中时随整页刷新置灰。撤销、恢复、保存后触发同一 PnL 刷新工作流再拉列表。"
        testId="product-category-audit-timeline-lead"
      />
      <div data-testid="product-category-audit-list-timeline-async">
        <AsyncSection
          title="调整审计"
          isLoading={adjustmentsQuery.isLoading}
          isError={adjustmentsQuery.isError}
          isEmpty={
            !adjustmentsQuery.isLoading &&
            !adjustmentsQuery.isError &&
            currentTotal === 0 &&
            eventTotal === 0
          }
          onRetry={() => void adjustmentsQuery.refetch()}
        >
        <div style={{ display: "grid", gap: 18 }}>
          <div data-testid="audit-current-state" style={{ display: "grid", gap: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ fontWeight: 600 }}>当前状态（{currentTotal}）</div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <select
                  data-testid="audit-current-page-size-select"
                  value={String(currentLimit)}
                  onChange={(event) => {
                    setCurrentLimit(Number(event.target.value));
                    setCurrentOffset(0);
                  }}
                >
                  {PAGE_SIZE_OPTIONS.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
                <span style={{ color: "#5c6b82", fontSize: 12 }}>
                  {currentTotal === 0
                    ? "0 / 0"
                    : `${currentOffset + 1}-${Math.min(currentOffset + currentLimit, currentTotal)} / ${currentTotal}`}
                </span>
                <button
                  type="button"
                  data-testid="audit-current-prev-page"
                  disabled={!currentCanPrev}
                  onClick={() =>
                    setCurrentOffset((current) => Math.max(0, current - currentLimit))
                  }
                >
                  上一页
                </button>
                <button
                  type="button"
                  data-testid="audit-current-next-page"
                  disabled={!currentCanNext}
                  onClick={() => setCurrentOffset((current) => current + currentLimit)}
                >
                  下一页
                </button>
              </div>
            </div>
            {(adjustmentsQuery.data?.adjustments ?? []).map((item) => (
              <div
                key={`audit-current-${item.adjustment_id}`}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1.2fr 0.8fr 0.8fr 0.8fr auto auto auto",
                  gap: 12,
                  alignItems: "center",
                  padding: 12,
                  borderRadius: 12,
                  border: "1px solid #d7dfea",
                }}
              >
                <div>
                  <div style={{ fontWeight: 600 }}>{item.account_code}</div>
                  <div style={{ color: "#5c6b82", fontSize: 12 }}>
                    {item.account_name || "未填写科目名称"}
                  </div>
                  <div style={{ color: "#8090a8", fontSize: 12 }}>
                    最近事件：{item.event_type}
                  </div>
                </div>
                <div>{item.currency}</div>
                <div>{item.operator}</div>
                <div>{item.approval_status}</div>
                <button
                  type="button"
                  data-testid={`audit-edit-${item.adjustment_id}`}
                  disabled={isRefreshing}
                  onClick={() => {
                    setEditingAdjustmentId(item.adjustment_id);
                    setDraft({
                      report_date: item.report_date,
                      operator: item.operator as "ADD" | "DELTA" | "OVERRIDE",
                      approval_status: item.approval_status as "approved" | "pending" | "rejected",
                      account_code: item.account_code,
                      currency: item.currency as "CNX" | "CNY",
                      account_name: item.account_name ?? "",
                      beginning_balance: item.beginning_balance ?? null,
                      ending_balance: item.ending_balance ?? null,
                      monthly_pnl: item.monthly_pnl ?? null,
                      daily_avg_balance: item.daily_avg_balance ?? null,
                      annual_avg_balance: item.annual_avg_balance ?? null,
                    });
                    setShowManualForm(true);
                  }}
                >
                  编辑
                </button>
                <button
                  type="button"
                  data-testid={`audit-revoke-${item.adjustment_id}`}
                  disabled={item.approval_status !== "approved" || isRefreshing}
                  onClick={() => void handleRevoke(item.adjustment_id)}
                >
                  撤销
                </button>
                <button
                  type="button"
                  data-testid={`audit-restore-${item.adjustment_id}`}
                  disabled={item.approval_status !== "rejected" || isRefreshing}
                  onClick={() => void handleRestore(item.adjustment_id)}
                >
                  恢复
                </button>
              </div>
            ))}
          </div>

          <div data-testid="audit-event-list" style={{ display: "grid", gap: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ fontWeight: 600 }}>完整事件时间线（{eventTotal}）</div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ color: "#5c6b82", fontSize: 12 }}>
                  {eventTotal === 0
                    ? "0 / 0"
                    : `${eventOffset + 1}-${Math.min(eventOffset + eventLimit, eventTotal)} / ${eventTotal}`}
                </span>
                <button
                  type="button"
                  data-testid="audit-prev-page"
                  disabled={!eventCanPrev}
                  onClick={() => setEventOffset((current) => Math.max(0, current - eventLimit))}
                >
                  上一页
                </button>
                <button
                  type="button"
                  data-testid="audit-next-page"
                  disabled={!eventCanNext}
                  onClick={() => setEventOffset((current) => current + eventLimit)}
                >
                  下一页
                </button>
              </div>
            </div>
            {(adjustmentsQuery.data?.events ?? []).map((item) => (
              <div
                key={`audit-event-${item.adjustment_id}-${item.created_at}-${item.event_type}`}
                data-testid={`audit-event-${item.adjustment_id}-${item.event_type}`}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1.2fr 1fr 1fr 1fr 1fr",
                  gap: 12,
                  padding: 12,
                  borderRadius: 12,
                  border: "1px dashed #d7dfea",
                  background: "#fcfdff",
                }}
              >
                <div>{item.created_at}</div>
                <div>{item.account_code}</div>
                <div>{item.event_type}</div>
                <div>{item.approval_status}</div>
                <div>{item.currency}</div>
              </div>
            ))}
          </div>
        </div>
        </AsyncSection>
      </div>
    </section>
  );
}

export default function ProductCategoryAdjustmentAuditPage() {
  const [searchParams] = useSearchParams();
  if (searchParams.get("branch") === "monthly_operating_analysis") {
    return <MonthlyOperatingAnalysisAuditPage />;
  }
  return <LegacyProductCategoryAdjustmentAuditBody />;
}
