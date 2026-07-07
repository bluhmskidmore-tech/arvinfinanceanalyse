import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { FilterBar } from "../../../components/FilterBar";
import type {
  QdbGlMonthlyAnalysisManualAdjustmentPayload,
  QdbGlMonthlyAnalysisManualAdjustmentRequest,
} from "../../../api/contracts";
import "./ProductCategoryAuditPages.css";
import "./ProductCategoryPnlPage.css";

const COPY = {
  title: "\u6708\u5ea6\u7ecf\u8425\u5206\u6790\u8c03\u6574\u5ba1\u8ba1",
  subtitle: "\u67e5\u770b\u5e76\u64cd\u4f5c\u6708\u5ea6\u7ecf\u8425\u5206\u6790\u5206\u652f\u7684\u624b\u5de5\u8c03\u6574\u3002",
  reportMonth: "\u62a5\u544a\u6708\u4efd",
  exportAudit: "\u5bfc\u51fa\u5ba1\u8ba1",
  adjustmentClass: "\u8c03\u6574\u7c7b\u578b",
  mappingTarget: "\u6620\u5c04\u76ee\u6807",
  mappingHint: "\u7528\u4e8e\u4fee\u6b63\u540d\u79f0\u7c7b\u6620\u5c04\uff0c\u4e0d\u76f4\u63a5\u6539\u5206\u6790\u7ed3\u679c\u3002",
  mappingAccountCode: "\u6620\u5c04\u79d1\u76ee\u4ee3\u7801",
  mappingField: "\u6620\u5c04\u5b57\u6bb5",
  analysisTarget: "\u5206\u6790\u76ee\u6807",
  analysisHint: "\u76f4\u63a5\u4fee\u6b63\u5206\u6790\u7ed3\u679c\u4e2d\u7684\u6307\u5b9a\u5355\u5143\u683c\u3002",
  sectionKey: "\u5de5\u4f5c\u8868\u6807\u8bc6",
  rowKey: "\u884c\u6807\u8bc6",
  metricKey: "\u6307\u6807\u6807\u8bc6",
  adjustmentValue: "\u8c03\u6574\u503c",
  createAdjustment: "\u65b0\u589e\u8c03\u6574",
  saveAdjustment: "\u4fdd\u5b58\u8c03\u6574",
  cancelEdit: "\u53d6\u6d88\u7f16\u8f91",
  edit: "\u7f16\u8f91",
  revoke: "\u64a4\u9500",
  restore: "\u6062\u590d",
  revoking: "\u6b63\u5728\u64a4\u9500",
  restoring: "\u6b63\u5728\u6062\u590d",
  empty: "\u5f53\u524d\u6ca1\u6709\u8c03\u6574\u8bb0\u5f55\u3002",
  emptyEvents: "\u5f53\u524d\u6ca1\u6709\u8c03\u6574\u4e8b\u4ef6\u3002",
  submitFailed: "\u63d0\u4ea4\u8c03\u6574\u5931\u8d25",
  revokeFailed: "\u64a4\u9500\u5931\u8d25",
  restoreFailed: "\u6062\u590d\u5931\u8d25",
  exportFailed: "\u5bfc\u51fa\u5ba1\u8ba1\u5931\u8d25",
  datesLoadFailed: "\u62a5\u544a\u6708\u4efd\u52a0\u8f7d\u5931\u8d25",
  adjustmentsLoadFailed: "\u8c03\u6574\u8bb0\u5f55\u52a0\u8f7d\u5931\u8d25",
  loadingDates: "\u6b63\u5728\u52a0\u8f7d\u62a5\u544a\u6708\u4efd\u2026",
  loadingAdjustments: "\u6b63\u5728\u52a0\u8f7d\u8c03\u6574\u8bb0\u5f55\u2026",
  noReportMonths: "当前没有可用报告月份，无法查看或操作月度经营分析调整审计。",
  mappingAccountPlaceholder:
    "\u79d1\u76ee\u4ee3\u7801\uff08GL \u5c3e\u5e16\u7801\uff0c\u4e0e\u540e\u7aef\u7ea6\u675f\u4e00\u81f4\uff09",
  adjustmentValuePlaceholder:
    "\u6307\u6807\u503c\u6216\u6620\u5c04\u540e\u6587\u672c\uff08\u4e0e\u540e\u7aef\u7ea6\u675f\u4e00\u81f4\uff09",
  requiredValue: "\u8bf7\u586b\u5199\u8c03\u6574\u503c\u3002",
  requiredMapping: "\u8bf7\u5b8c\u6574\u586b\u5199\u6620\u5c04\u8c03\u6574\u7684\u79d1\u76ee\u4ee3\u7801\u548c\u6620\u5c04\u5b57\u6bb5\u3002",
  requiredAnalysis:
    "\u8bf7\u5b8c\u6574\u586b\u5199\u5206\u6790\u8c03\u6574\u7684\u5de5\u4f5c\u8868\u3001\u884c\u6807\u8bc6\u548c\u6307\u6807\u6807\u8bc6\u3002",
};

const MAPPING_FIELD_OPTIONS = [
  { value: "industry_name", label: "\u884c\u4e1a\u540d\u79f0" },
  { value: "category_name", label: "\u5206\u7c7b\u540d\u79f0" },
  { value: "account_name", label: "\u79d1\u76ee\u540d\u79f0" },
] as const;

const ANALYSIS_SECTION_OPTIONS = [
  { value: "overview", label: "\u7ecf\u8425\u6982\u89c8 (overview)" },
  { value: "alerts", label: "\u5f02\u52a8\u9884\u8b66 (alerts)" },
] as const;

const ANALYSIS_METRIC_OPTIONS: Record<string, Array<{ value: string; label: string }>> = {
  overview: [{ value: "value", label: "\u6307\u6807\u503c (value)" }],
  alerts: [{ value: "alert_level", label: "\u9884\u8b66\u7ea7\u522b (alert_level)" }],
};

const ANALYSIS_ROW_KEY_OPTIONS: Record<string, Array<{ value: string; label: string }>> = {
  overview: [{ value: "loan_ratio", label: "\u5b58\u8d37\u6bd4 (loan_ratio)" }],
  alerts: [{ value: "14001000001", label: "14001000001 / \u4e70\u5165\u8fd4\u552e" }],
};

function downloadAuditCsv(filename: string, content: string) {
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

function buildDraft(reportMonth: string): QdbGlMonthlyAnalysisManualAdjustmentRequest {
  return {
    report_month: reportMonth,
    adjustment_class: "mapping_adjustment",
    target: {
      account_code: "",
      field: "industry_name",
    },
    operator: "OVERRIDE",
    value: "",
    approval_status: "approved",
  };
}

function serializeTarget(item: QdbGlMonthlyAnalysisManualAdjustmentPayload): string {
  const target = item.target;
  if (typeof target?.account_code === "string" && typeof target?.field === "string") {
    return `${target.account_code} / ${target.field}`;
  }
  if (
    typeof target?.section_key === "string" &&
    typeof target?.row_key === "string" &&
    typeof target?.metric_key === "string"
  ) {
    return `${target.section_key} / ${target.row_key} / ${target.metric_key}`;
  }
  return JSON.stringify(target ?? {});
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function formatActionErrorMessage(error: unknown, fallback: string) {
  const message = errorMessage(error, fallback);
  const requestFailure = /^Request failed: .+ \((\d{3})\)$/.exec(message);
  if (requestFailure?.[1]) {
    return `请求失败（${requestFailure[1]}），请稍后重试或检查服务状态。`;
  }
  return message;
}

function canRevokeAdjustment(item: QdbGlMonthlyAnalysisManualAdjustmentPayload) {
  return item.approval_status === "approved";
}

function canRestoreAdjustment(item: QdbGlMonthlyAnalysisManualAdjustmentPayload) {
  return item.approval_status === "rejected";
}

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
  testId?: string;
}) {
  return (
    <div data-testid={props.testId} className="product-category-section-lead">
      <span className="product-category-section-lead__eyebrow">{props.eyebrow}</span>
      <h2 className="product-category-section-lead__title">{props.title}</h2>
      <p className="product-category-section-lead__description">{props.description}</p>
    </div>
  );
}

export default function MonthlyOperatingAnalysisAuditPage() {
  const client = useApiClient();
  const [searchParams] = useSearchParams();
  const routeReportMonth = searchParams.get("report_month") ?? "";
  const [selectedMonth, setSelectedMonth] = useState("");
  const [draft, setDraft] = useState<QdbGlMonthlyAnalysisManualAdjustmentRequest>(buildDraft(""));
  const [editingAdjustmentId, setEditingAdjustmentId] = useState<string | null>(null);
  const [lastActionId, setLastActionId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmittingAdjustment, setIsSubmittingAdjustment] = useState(false);
  const [isExportingAudit, setIsExportingAudit] = useState(false);
  const [pendingAdjustmentAction, setPendingAdjustmentAction] = useState<{
    adjustmentId: string;
    action: "revoke" | "restore";
  } | null>(null);
  const appliedReportMonthParamRef = useRef<string | null>(null);
  const pendingAdjustmentActionRef = useRef<string | null>(null);
  const isAdjustmentActionRunning = Boolean(pendingAdjustmentAction);

  const datesQuery = useQuery({
    queryKey: ["monthly-operating-analysis", "audit", "dates", client.mode],
    queryFn: () => client.getQdbGlMonthlyAnalysisDates(),
    retry: false,
  });

  useEffect(() => {
    const reportMonths = datesQuery.data?.result.report_months ?? [];
    if (!reportMonths.length) {
      return;
    }

    const targetMonth =
      routeReportMonth && reportMonths.includes(routeReportMonth)
        ? routeReportMonth
        : reportMonths[0] ?? "";
    const shouldApplyRouteMonth =
      !selectedMonth ||
      !reportMonths.includes(selectedMonth) ||
      appliedReportMonthParamRef.current !== routeReportMonth;

    if (targetMonth && shouldApplyRouteMonth) {
      appliedReportMonthParamRef.current = routeReportMonth;
      setSelectedMonth(targetMonth);
    }
  }, [datesQuery.data, routeReportMonth, selectedMonth]);

  useEffect(() => {
    setEditingAdjustmentId(null);
    setDraft(buildDraft(selectedMonth));
    setLastActionId(null);
    setErrorMessage(null);
  }, [selectedMonth]);

  const adjustmentsQuery = useQuery({
    queryKey: ["monthly-operating-analysis", "audit", "adjustments", client.mode, selectedMonth],
    queryFn: () => client.getQdbGlMonthlyAnalysisManualAdjustments(selectedMonth),
    enabled: Boolean(selectedMonth),
    retry: false,
  });

  const isMappingAdjustment = draft.adjustment_class === "mapping_adjustment";
  const selectedSectionKey = String(draft.target.section_key ?? "overview");
  const metricOptions = ANALYSIS_METRIC_OPTIONS[selectedSectionKey] ?? [];
  const rowKeyOptions = ANALYSIS_ROW_KEY_OPTIONS[selectedSectionKey] ?? [];
  const selectedRowKey = String(draft.target.row_key ?? "");
  const rowKeyOptionsWithFallback =
    selectedRowKey && rowKeyOptions.every((option) => option.value !== selectedRowKey)
      ? [...rowKeyOptions, { value: selectedRowKey, label: selectedRowKey }]
      : rowKeyOptions;
  const reportMonths = datesQuery.data?.result.report_months ?? [];
  const hasReportMonths = reportMonths.length > 0;
  const loadErrorMessage = datesQuery.isError
    ? formatActionErrorMessage(datesQuery.error, COPY.datesLoadFailed)
    : adjustmentsQuery.isError
      ? formatActionErrorMessage(adjustmentsQuery.error, COPY.adjustmentsLoadFailed)
      : null;
  const isAuditLoading = datesQuery.isLoading || adjustmentsQuery.isFetching;
  const loadingMessage = datesQuery.isLoading
    ? COPY.loadingDates
    : adjustmentsQuery.isFetching
      ? COPY.loadingAdjustments
      : null;
  const canOperateAudit =
    Boolean(selectedMonth) &&
    hasReportMonths &&
    !datesQuery.isError &&
    !adjustmentsQuery.isError &&
    !isAuditLoading;
  const isAuditWriteRunning = isSubmittingAdjustment || isAdjustmentActionRunning;
  const isAuditOperationLocked = isAuditWriteRunning || isExportingAudit;
  const isMonthSelectLocked = isAuditOperationLocked || !hasReportMonths || datesQuery.isError;
  const isAuditBusy = isAuditOperationLocked || isAuditLoading;
  const canSubmitAdjustment = canOperateAudit && !isAuditBusy;
  const canExportAudit = canOperateAudit && !isExportingAudit && !isAuditWriteRunning;
  const isAuditFormLocked = !canOperateAudit || isAuditBusy;
  const showDatesEmpty = datesQuery.isSuccess && !hasReportMonths;
  const showAdjustmentsEmpty =
    adjustmentsQuery.isSuccess && !isAuditLoading && (adjustmentsQuery.data?.adjustments ?? []).length === 0;
  const showEventsEmpty =
    adjustmentsQuery.isSuccess && !isAuditLoading && (adjustmentsQuery.data?.events ?? []).length === 0;

  function updateDraft<K extends keyof QdbGlMonthlyAnalysisManualAdjustmentRequest>(
    key: K,
    value: QdbGlMonthlyAnalysisManualAdjustmentRequest[K],
  ) {
    if (isAuditFormLocked) {
      return;
    }
    setDraft((current) => ({
      ...current,
      [key]: value,
    }));
  }

  function validateDraft(): string | null {
    if (!draft.value.trim()) {
      return COPY.requiredValue;
    }
    if (isMappingAdjustment) {
      const accountCode = String(draft.target.account_code ?? "").trim();
      const field = String(draft.target.field ?? "").trim();
      if (!accountCode || !field) {
        return COPY.requiredMapping;
      }
      return null;
    }
    const sectionKey = String(draft.target.section_key ?? "").trim();
    const rowKey = String(draft.target.row_key ?? "").trim();
    const metricKey = String(draft.target.metric_key ?? "").trim();
    if (!sectionKey || !rowKey || !metricKey) {
      return COPY.requiredAnalysis;
    }
    return null;
  }

  async function handleSubmitAdjustment() {
    if (!canSubmitAdjustment) {
      return;
    }
    const validationError = validateDraft();
    if (validationError) {
      setErrorMessage(validationError);
      return;
    }
    setErrorMessage(null);
    setIsSubmittingAdjustment(true);
    try {
      const payload = {
        ...draft,
        report_month: selectedMonth,
      };
      const response = editingAdjustmentId
        ? await client.updateQdbGlMonthlyAnalysisManualAdjustment(editingAdjustmentId, payload)
        : await client.createQdbGlMonthlyAnalysisManualAdjustment(payload);
      setLastActionId(response.adjustment_id);
      resetToCreateDraft(selectedMonth);
      await adjustmentsQuery.refetch();
    } catch (error) {
      setErrorMessage(formatActionErrorMessage(error, COPY.submitFailed));
    } finally {
      setIsSubmittingAdjustment(false);
    }
  }

  async function handleRevoke(item: QdbGlMonthlyAnalysisManualAdjustmentPayload) {
    if (!canRevokeAdjustment(item) || isAuditBusy) {
      return;
    }
    const adjustmentId = item.adjustment_id;
    const actionKey = `revoke:${adjustmentId}`;
    if (pendingAdjustmentActionRef.current) {
      return;
    }
    pendingAdjustmentActionRef.current = actionKey;
    setPendingAdjustmentAction({ adjustmentId, action: "revoke" });
    setErrorMessage(null);
    try {
      const response = await client.revokeQdbGlMonthlyAnalysisManualAdjustment(adjustmentId);
      setLastActionId(response.adjustment_id);
      await adjustmentsQuery.refetch();
    } catch (error) {
      setErrorMessage(formatActionErrorMessage(error, COPY.revokeFailed));
    } finally {
      if (pendingAdjustmentActionRef.current === actionKey) {
        pendingAdjustmentActionRef.current = null;
        setPendingAdjustmentAction(null);
      }
    }
  }

  async function handleRestore(item: QdbGlMonthlyAnalysisManualAdjustmentPayload) {
    if (!canRestoreAdjustment(item) || isAuditBusy) {
      return;
    }
    const adjustmentId = item.adjustment_id;
    const actionKey = `restore:${adjustmentId}`;
    if (pendingAdjustmentActionRef.current) {
      return;
    }
    pendingAdjustmentActionRef.current = actionKey;
    setPendingAdjustmentAction({ adjustmentId, action: "restore" });
    setErrorMessage(null);
    try {
      const response = await client.restoreQdbGlMonthlyAnalysisManualAdjustment(adjustmentId);
      setLastActionId(response.adjustment_id);
      await adjustmentsQuery.refetch();
    } catch (error) {
      setErrorMessage(formatActionErrorMessage(error, COPY.restoreFailed));
    } finally {
      if (pendingAdjustmentActionRef.current === actionKey) {
        pendingAdjustmentActionRef.current = null;
        setPendingAdjustmentAction(null);
      }
    }
  }

  async function handleExport() {
    if (!canExportAudit) {
      return;
    }
    setErrorMessage(null);
    setIsExportingAudit(true);
    try {
      const payload = await client.exportQdbGlMonthlyAnalysisManualAdjustmentsCsv(selectedMonth);
      downloadAuditCsv(payload.filename, payload.content);
    } catch (error) {
      setErrorMessage(formatActionErrorMessage(error, COPY.exportFailed));
    } finally {
      setIsExportingAudit(false);
    }
  }

  function handleCancelEdit() {
    if (isAuditFormLocked) {
      return;
    }
    resetToCreateDraft();
    clearTransientMessages();
  }

  function resetToCreateDraft(reportMonth = selectedMonth) {
    setEditingAdjustmentId(null);
    setDraft(buildDraft(reportMonth));
  }

  function clearTransientMessages() {
    setLastActionId(null);
    setErrorMessage(null);
  }

  function startEditingAdjustment(item: QdbGlMonthlyAnalysisManualAdjustmentPayload) {
    if (isAuditBusy) {
      return;
    }
    setEditingAdjustmentId(item.adjustment_id);
    clearTransientMessages();
    setDraft({
      report_month: item.report_month,
      adjustment_class: item.adjustment_class,
      target:
        item.adjustment_class === "mapping_adjustment"
          ? {
              account_code: String(item.target.account_code ?? ""),
              field: String(item.target.field ?? "industry_name"),
            }
          : {
              section_key: String(item.target.section_key ?? "overview"),
              row_key: String(item.target.row_key ?? ""),
              metric_key: String(
                item.target.metric_key ??
                  ANALYSIS_METRIC_OPTIONS[String(item.target.section_key ?? "overview")]?.[0]?.value ??
                  "",
              ),
            },
      operator: item.operator as "ADD" | "DELTA" | "OVERRIDE",
      value: item.value,
      approval_status: item.approval_status as "approved" | "pending" | "rejected",
    });
  }

  return (
    <section data-testid="monthly-operating-analysis-audit-page">
      <div className="product-category-audit-page-header">
        <div>
          <h1 data-testid="monthly-operating-analysis-audit-title" className="product-category-audit-page-title">
            {COPY.title}
          </h1>
          <p
            data-testid="monthly-operating-analysis-audit-boundary-copy"
            className="product-category-audit-boundary-copy"
          >
            {COPY.subtitle}
          </p>
          <p className="product-category-audit-meta-copy">
            月度经营审计只调整分析分支记录，并保持与产品分类正式结果分离。
          </p>
          {lastActionId ? <p className="product-category-audit-meta-copy--compact">{lastActionId}</p> : null}
          {errorMessage ? (
            <p data-testid="monthly-operating-analysis-audit-error" className="product-category-audit-meta-copy--danger">
              {errorMessage}
            </p>
          ) : null}
          {loadErrorMessage ? (
            <p
              data-testid="monthly-operating-analysis-audit-load-error"
              className="product-category-audit-meta-copy--danger"
            >
              {loadErrorMessage}
            </p>
          ) : null}
          {loadingMessage ? (
            <p
              data-testid="monthly-operating-analysis-audit-loading"
              className="product-category-audit-meta-copy--compact"
            >
              {loadingMessage}
            </p>
          ) : null}
          {showDatesEmpty ? (
            <p
              data-testid="monthly-operating-analysis-audit-dates-empty"
              className="product-category-audit-meta-copy--danger"
            >
              {COPY.noReportMonths}
            </p>
          ) : null}
        </div>
        <FilterBar className="product-category-audit-filter-bar--end">
          <span
            className={`product-category-audit-chip ${
              client.mode === "real" ? "product-category-audit-chip--real" : "product-category-audit-chip--mock"
            }`}
          >
            {client.mode === "real" ? "正式接口链路" : "本地离线契约回放"}
          </span>
          <label className="product-category-audit-field">
            {COPY.reportMonth}
            <select
              data-testid="monthly-operating-analysis-audit-month-select"
              value={selectedMonth}
              disabled={isMonthSelectLocked}
              onChange={(event) => {
                if (isMonthSelectLocked) {
                  return;
                }
                setSelectedMonth(event.target.value);
              }}
            >
              {reportMonths.map((reportMonth) => (
                <option key={reportMonth} value={reportMonth}>
                  {reportMonth}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            data-testid="monthly-operating-analysis-adjustment-export"
            disabled={!canExportAudit}
            onClick={() => void handleExport()}
          >
            {isExportingAudit ? "正在导出审计" : COPY.exportAudit}
          </button>
        </FilterBar>
      </div>

      <SectionLead
        eyebrow="调整"
        title="月度经营调整录入"
        description="映射调整用于修正映射类字段，分析调整用于修正指定分析单元格，均沿用既有调整接口。"
        testId="monthly-operating-analysis-audit-form-lead"
      />
      <div className="product-category-audit-form-stack">
        <div className="product-category-audit-form-panel">
          <label className="product-category-audit-field--compact">
            {COPY.adjustmentClass}
            <select
              data-testid="monthly-operating-analysis-adjustment-class"
              value={draft.adjustment_class}
              disabled={isAuditFormLocked}
              onChange={(event) => {
                if (isAuditFormLocked) {
                  return;
                }
                const adjustmentClass = event.target.value as "mapping_adjustment" | "analysis_adjustment";
                setDraft((current) => ({
                  ...current,
                  adjustment_class: adjustmentClass,
                  target:
                    adjustmentClass === "mapping_adjustment"
                      ? {
                          account_code:
                            typeof current.target.account_code === "string" ? current.target.account_code : "",
                          field: typeof current.target.field === "string" ? current.target.field : "industry_name",
                        }
                      : {
                          section_key: "overview",
                          row_key: "",
                          metric_key: "value",
                        },
                }));
              }}
            >
              <option value="mapping_adjustment">mapping_adjustment</option>
              <option value="analysis_adjustment">analysis_adjustment</option>
            </select>
          </label>

          {isMappingAdjustment ? (
            <>
              <div className="product-category-audit-target-hint">
                <span>{COPY.mappingTarget}</span>
                <span className="product-category-audit-hint">{COPY.mappingHint}</span>
              </div>
              <label className="product-category-audit-field--compact">
                <span>{COPY.mappingAccountCode}</span>
                <input
                  aria-label={COPY.mappingAccountCode}
                  data-testid="monthly-operating-analysis-mapping-account-code"
                  value={String(draft.target.account_code ?? "")}
                  disabled={isAuditFormLocked}
                  onChange={(event) =>
                    updateDraft("target", {
                      account_code: event.target.value,
                      field: String(draft.target.field ?? "industry_name"),
                    })
                  }
                  placeholder={COPY.mappingAccountPlaceholder}
                />
              </label>
              <label className="product-category-audit-field--compact">
                <span>{COPY.mappingField}</span>
                <select
                  aria-label={COPY.mappingField}
                  data-testid="monthly-operating-analysis-mapping-field"
                  value={String(draft.target.field ?? "industry_name")}
                  disabled={isAuditFormLocked}
                  onChange={(event) =>
                    updateDraft("target", {
                      account_code: String(draft.target.account_code ?? ""),
                      field: event.target.value,
                    })
                  }
                >
                  {MAPPING_FIELD_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </>
          ) : (
            <>
              <div className="product-category-audit-target-hint">
                <span>{COPY.analysisTarget}</span>
                <span className="product-category-audit-hint">{COPY.analysisHint}</span>
              </div>
              <label className="product-category-audit-field--compact">
                <span>{COPY.sectionKey}</span>
                <select
                  data-testid="monthly-operating-analysis-analysis-section-key"
                  value={selectedSectionKey}
                  disabled={isAuditFormLocked}
                  onChange={(event) =>
                    updateDraft("target", {
                      section_key: event.target.value,
                      row_key: "",
                      metric_key: ANALYSIS_METRIC_OPTIONS[event.target.value]?.[0]?.value ?? "",
                    })
                  }
                >
                  {ANALYSIS_SECTION_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="product-category-audit-field--compact">
                <span>{COPY.rowKey}</span>
                <select
                  data-testid="monthly-operating-analysis-analysis-row-key"
                  value={selectedRowKey}
                  disabled={isAuditFormLocked}
                  onChange={(event) =>
                    updateDraft("target", {
                      section_key: selectedSectionKey,
                      row_key: event.target.value,
                      metric_key: String(draft.target.metric_key ?? metricOptions[0]?.value ?? ""),
                    })
                  }
                >
                  <option value="">请选择行标识</option>
                  {rowKeyOptionsWithFallback.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="product-category-audit-field--compact">
                <span>{COPY.metricKey}</span>
                <select
                  data-testid="monthly-operating-analysis-analysis-metric-key"
                  value={String(draft.target.metric_key ?? metricOptions[0]?.value ?? "")}
                  disabled={isAuditFormLocked}
                  onChange={(event) =>
                    updateDraft("target", {
                      section_key: selectedSectionKey,
                      row_key: String(draft.target.row_key ?? ""),
                      metric_key: event.target.value,
                    })
                  }
                >
                  {metricOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}

          <label className="product-category-audit-field--compact">
            <span>{COPY.adjustmentValue}</span>
            <input
              data-testid="monthly-operating-analysis-adjustment-value"
              value={draft.value}
              disabled={isAuditFormLocked}
              onChange={(event) => updateDraft("value", event.target.value)}
              placeholder={COPY.adjustmentValuePlaceholder}
            />
          </label>
          <div className="product-category-audit-form-actions">
            <div className="product-category-audit-form-actions__row">
              <button
                type="button"
                data-testid="monthly-operating-analysis-adjustment-submit"
                disabled={!canSubmitAdjustment}
                onClick={() => void handleSubmitAdjustment()}
              >
                {isSubmittingAdjustment
                  ? "正在提交调整"
                  : editingAdjustmentId
                    ? COPY.saveAdjustment
                    : COPY.createAdjustment}
              </button>
              {editingAdjustmentId ? (
                <button
                  type="button"
                  data-testid="monthly-operating-analysis-adjustment-cancel-edit"
                  disabled={isAuditFormLocked}
                  onClick={handleCancelEdit}
                >
                  {COPY.cancelEdit}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      <SectionLead
        eyebrow="审计"
        title="月度经营调整记录"
        description="列表和事件区继续展示后端返回的 adjustments / events，并保留编辑、撤销、恢复与导出行为。"
        testId="monthly-operating-analysis-audit-list-lead"
      />
      <div data-testid="monthly-operating-analysis-adjustment-list" className="product-category-audit-list">
        {(adjustmentsQuery.data?.adjustments ?? []).map((item) => (
          <div
            key={item.adjustment_id}
            data-testid={`monthly-operating-analysis-adjustment-row-${item.adjustment_id}`}
            className="product-category-audit-adjustment-row product-category-audit-adjustment-row--monthly product-category-audit-adjustment-row--filled"
          >
            <div>
              <div>{item.adjustment_class}</div>
              <div className="product-category-audit-adjustment-secondary">{serializeTarget(item)}</div>
            </div>
            <div>{item.value}</div>
            <div>{item.approval_status}</div>
            <button
              type="button"
              data-testid={`monthly-operating-analysis-adjustment-edit-${item.adjustment_id}`}
              disabled={isAuditBusy}
              onClick={() => startEditingAdjustment(item)}
            >
              {COPY.edit}
            </button>
            <div className="product-category-audit-row-actions">
              <button
                type="button"
                data-testid={`monthly-operating-analysis-adjustment-revoke-${item.adjustment_id}`}
                disabled={!canRevokeAdjustment(item) || isAuditBusy}
                onClick={() => void handleRevoke(item)}
              >
                {pendingAdjustmentAction?.adjustmentId === item.adjustment_id &&
                pendingAdjustmentAction.action === "revoke"
                  ? COPY.revoking
                  : COPY.revoke}
              </button>
              <button
                type="button"
                data-testid={`monthly-operating-analysis-adjustment-restore-${item.adjustment_id}`}
                disabled={!canRestoreAdjustment(item) || isAuditBusy}
                onClick={() => void handleRestore(item)}
              >
                {pendingAdjustmentAction?.adjustmentId === item.adjustment_id &&
                pendingAdjustmentAction.action === "restore"
                  ? COPY.restoring
                  : COPY.restore}
              </button>
            </div>
          </div>
        ))}
        {showAdjustmentsEmpty ? (
          <div className="product-category-audit-empty">{COPY.empty}</div>
        ) : null}
      </div>

      <div data-testid="monthly-operating-analysis-adjustment-events" className="product-category-audit-events">
        {(adjustmentsQuery.data?.events ?? []).map((item) => (
          <div
            key={`${item.adjustment_id}-${item.created_at}-${item.event_type}`}
            className="product-category-audit-event-row"
          >
            {item.event_type} / {item.adjustment_id}
          </div>
        ))}
        {showEventsEmpty ? (
          <div className="product-category-audit-empty">{COPY.emptyEvents}</div>
        ) : null}
      </div>
    </section>
  );
}
