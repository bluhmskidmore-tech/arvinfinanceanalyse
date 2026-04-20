import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import { FilterBar } from "../../../components/FilterBar";
import type {
  QdbGlMonthlyAnalysisManualAdjustmentPayload,
  QdbGlMonthlyAnalysisManualAdjustmentRequest,
} from "../../../api/contracts";

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
  edit: "\u7f16\u8f91",
  revoke: "\u64a4\u9500",
  restore: "\u6062\u590d",
  empty: "\u5f53\u524d\u6ca1\u6709\u8c03\u6574\u8bb0\u5f55\u3002",
  submitFailed: "\u63d0\u4ea4\u8c03\u6574\u5931\u8d25",
  revokeFailed: "\u64a4\u9500\u5931\u8d25",
  restoreFailed: "\u6062\u590d\u5931\u8d25",
  exportFailed: "\u5bfc\u51fa\u5ba1\u8ba1\u5931\u8d25",
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

export default function MonthlyOperatingAnalysisAuditPage() {
  const client = useApiClient();
  const [selectedMonth, setSelectedMonth] = useState("");
  const [draft, setDraft] = useState<QdbGlMonthlyAnalysisManualAdjustmentRequest>(buildDraft(""));
  const [editingAdjustmentId, setEditingAdjustmentId] = useState<string | null>(null);
  const [lastActionId, setLastActionId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const datesQuery = useQuery({
    queryKey: ["monthly-operating-analysis", "audit", "dates", client.mode],
    queryFn: () => client.getQdbGlMonthlyAnalysisDates(),
    retry: false,
  });

  useEffect(() => {
    if (!selectedMonth && datesQuery.data?.result.report_months.length) {
      setSelectedMonth(datesQuery.data.result.report_months[0] ?? "");
    }
  }, [datesQuery.data, selectedMonth]);

  useEffect(() => {
    setDraft((current) => ({
      ...current,
      report_month: selectedMonth,
    }));
    setEditingAdjustmentId(null);
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

  function updateDraft<K extends keyof QdbGlMonthlyAnalysisManualAdjustmentRequest>(
    key: K,
    value: QdbGlMonthlyAnalysisManualAdjustmentRequest[K],
  ) {
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
    const validationError = validateDraft();
    if (validationError) {
      setErrorMessage(validationError);
      return;
    }
    setErrorMessage(null);
    try {
      const payload = {
        ...draft,
        report_month: selectedMonth,
      };
      const response = editingAdjustmentId
        ? await client.updateQdbGlMonthlyAnalysisManualAdjustment(editingAdjustmentId, payload)
        : await client.createQdbGlMonthlyAnalysisManualAdjustment(payload);
      setLastActionId(response.adjustment_id);
      setEditingAdjustmentId(null);
      setDraft(buildDraft(selectedMonth));
      await adjustmentsQuery.refetch();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : COPY.submitFailed);
    }
  }

  async function handleRevoke(adjustmentId: string) {
    setErrorMessage(null);
    try {
      const response = await client.revokeQdbGlMonthlyAnalysisManualAdjustment(adjustmentId);
      setLastActionId(response.adjustment_id);
      await adjustmentsQuery.refetch();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : COPY.revokeFailed);
    }
  }

  async function handleRestore(adjustmentId: string) {
    setErrorMessage(null);
    try {
      const response = await client.restoreQdbGlMonthlyAnalysisManualAdjustment(adjustmentId);
      setLastActionId(response.adjustment_id);
      await adjustmentsQuery.refetch();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : COPY.restoreFailed);
    }
  }

  async function handleExport() {
    setErrorMessage(null);
    try {
      const payload = await client.exportQdbGlMonthlyAnalysisManualAdjustmentsCsv(selectedMonth);
      downloadAuditCsv(payload.filename, payload.content);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : COPY.exportFailed);
    }
  }

  return (
    <section data-testid="monthly-operating-analysis-audit-page">
      <div style={pageHeaderStyle}>
        <div>
          <h1 data-testid="monthly-operating-analysis-audit-title" style={{ margin: 0, fontSize: 28, fontWeight: 700 }}>{COPY.title}</h1>
          <p data-testid="monthly-operating-analysis-audit-boundary-copy" style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 14 }}>
            {COPY.subtitle}
          </p>
          <p style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 12 }}>
            Monthly operating audit adjusts analytical branch records and preserves separation from legacy product-category formal results.
          </p>
          {lastActionId ? (
            <p style={{ margin: "8px 0 0", color: "#5c6b82", fontSize: 12 }}>{lastActionId}</p>
          ) : null}
          {errorMessage ? (
            <p style={{ margin: "8px 0 0", color: "#b42318", fontSize: 12 }}>{errorMessage}</p>
          ) : null}
        </div>
        <FilterBar style={{ justifyContent: "flex-end" }}>
          <span style={modeBadgeStyle}>
            {client.mode === "real" ? "正式只读链路" : "本地离线契约回放"}
          </span>
          <label style={{ display: "grid", gap: 8 }}>
            {COPY.reportMonth}
            <select value={selectedMonth} onChange={(event) => setSelectedMonth(event.target.value)}>
              {(datesQuery.data?.result.report_months ?? []).map((reportMonth) => (
                <option key={reportMonth} value={reportMonth}>
                  {reportMonth}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            data-testid="monthly-operating-analysis-adjustment-export"
            onClick={() => void handleExport()}
          >
            {COPY.exportAudit}
          </button>
        </FilterBar>
      </div>

      <SectionLead
        eyebrow="Adjustment"
        title="月度经营调整录入"
        description="mapping adjustment 修正映射类字段，analysis adjustment 修正指定分析单元格，均沿用既有 adjustment API。"
        testId="monthly-operating-analysis-audit-form-lead"
      />
      <div style={{ display: "grid", gap: 12, marginBottom: 18 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
            gap: 12,
            padding: 12,
            borderRadius: 12,
            border: "1px solid #d7dfea",
            background: "#fbfcfe",
          }}
        >
          <label style={{ display: "grid", gap: 6 }}>
            {COPY.adjustmentClass}
            <select
              data-testid="monthly-operating-analysis-adjustment-class"
              value={draft.adjustment_class}
              onChange={(event) => {
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
              <div style={{ display: "grid", gap: 6 }}>
                <span>{COPY.mappingTarget}</span>
                <span style={{ color: "#5c6b82", fontSize: 12 }}>{COPY.mappingHint}</span>
              </div>
              <label style={{ display: "grid", gap: 6 }}>
                <span>{COPY.mappingAccountCode}</span>
                <input
                  aria-label={COPY.mappingAccountCode}
                  data-testid="monthly-operating-analysis-mapping-account-code"
                  value={String(draft.target.account_code ?? "")}
                  onChange={(event) =>
                    updateDraft("target", {
                      account_code: event.target.value,
                      field: String(draft.target.field ?? "industry_name"),
                    })
                  }
                  placeholder={COPY.mappingAccountPlaceholder}
                />
              </label>
              <label style={{ display: "grid", gap: 6 }}>
                <span>{COPY.mappingField}</span>
                <select
                  aria-label={COPY.mappingField}
                  data-testid="monthly-operating-analysis-mapping-field"
                  value={String(draft.target.field ?? "industry_name")}
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
              <div style={{ display: "grid", gap: 6 }}>
                <span>{COPY.analysisTarget}</span>
                <span style={{ color: "#5c6b82", fontSize: 12 }}>{COPY.analysisHint}</span>
              </div>
              <label style={{ display: "grid", gap: 6 }}>
                <span>{COPY.sectionKey}</span>
                <select
                  data-testid="monthly-operating-analysis-analysis-section-key"
                  value={selectedSectionKey}
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
              <label style={{ display: "grid", gap: 6 }}>
                <span>{COPY.rowKey}</span>
                <select
                  data-testid="monthly-operating-analysis-analysis-row-key"
                  value={selectedRowKey}
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
              <label style={{ display: "grid", gap: 6 }}>
                <span>{COPY.metricKey}</span>
                <select
                  data-testid="monthly-operating-analysis-analysis-metric-key"
                  value={String(draft.target.metric_key ?? metricOptions[0]?.value ?? "")}
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

          <label style={{ display: "grid", gap: 6 }}>
            <span>{COPY.adjustmentValue}</span>
            <input
              data-testid="monthly-operating-analysis-adjustment-value"
              value={draft.value}
              onChange={(event) => updateDraft("value", event.target.value)}
              placeholder={COPY.adjustmentValuePlaceholder}
            />
          </label>
          <div style={{ display: "flex", alignItems: "end" }}>
            <button
              type="button"
              data-testid="monthly-operating-analysis-adjustment-submit"
              onClick={() => void handleSubmitAdjustment()}
            >
              {editingAdjustmentId ? COPY.saveAdjustment : COPY.createAdjustment}
            </button>
          </div>
        </div>
      </div>

      <SectionLead
        eyebrow="Audit"
        title="月度经营调整记录"
        description="列表和事件区继续展示后端返回的 adjustments / events，并保留编辑、撤销、恢复与导出行为。"
        testId="monthly-operating-analysis-audit-list-lead"
      />
      <div data-testid="monthly-operating-analysis-adjustment-list" style={{ display: "grid", gap: 12 }}>
        {(adjustmentsQuery.data?.adjustments ?? []).map((item) => (
          <div
            key={item.adjustment_id}
            data-testid={`monthly-operating-analysis-adjustment-row-${item.adjustment_id}`}
            style={{
              display: "grid",
              gridTemplateColumns: "1.4fr 1fr auto auto auto",
              gap: 12,
              alignItems: "center",
              padding: 12,
              borderRadius: 12,
              border: "1px solid #d7dfea",
              background: "#fbfcfe",
            }}
          >
            <div>
              <div>{item.adjustment_class}</div>
              <div style={{ color: "#5c6b82", fontSize: 12 }}>{serializeTarget(item)}</div>
            </div>
            <div>{item.value}</div>
            <div>{item.approval_status}</div>
            <button
              type="button"
              data-testid={`monthly-operating-analysis-adjustment-edit-${item.adjustment_id}`}
              onClick={() => {
                setEditingAdjustmentId(item.adjustment_id);
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
              }}
            >
              {COPY.edit}
            </button>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                data-testid={`monthly-operating-analysis-adjustment-revoke-${item.adjustment_id}`}
                onClick={() => void handleRevoke(item.adjustment_id)}
              >
                {COPY.revoke}
              </button>
              <button
                type="button"
                data-testid={`monthly-operating-analysis-adjustment-restore-${item.adjustment_id}`}
                onClick={() => void handleRestore(item.adjustment_id)}
              >
                {COPY.restore}
              </button>
            </div>
          </div>
        ))}
        {(adjustmentsQuery.data?.adjustments ?? []).length === 0 ? (
          <div style={{ color: "#8090a8", fontSize: 13 }}>{COPY.empty}</div>
        ) : null}
      </div>

      <div
        data-testid="monthly-operating-analysis-adjustment-events"
        style={{ display: "grid", gap: 8, marginTop: 18 }}
      >
        {(adjustmentsQuery.data?.events ?? []).map((item) => (
          <div
            key={`${item.adjustment_id}-${item.created_at}-${item.event_type}`}
            style={{
              padding: 12,
              borderRadius: 12,
              border: "1px dashed #d7dfea",
              background: "#fcfdff",
            }}
          >
            {item.event_type} / {item.adjustment_id}
          </div>
        ))}
      </div>
    </section>
  );
}
