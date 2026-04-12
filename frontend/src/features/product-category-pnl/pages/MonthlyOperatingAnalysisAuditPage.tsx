import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type {
  QdbGlMonthlyAnalysisManualAdjustmentPayload,
  QdbGlMonthlyAnalysisManualAdjustmentRequest,
} from "../../../api/contracts";

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
    target: { target: "" },
    operator: "OVERRIDE",
    value: "",
    approval_status: "approved",
  };
}

function serializeTarget(item: QdbGlMonthlyAnalysisManualAdjustmentPayload): string {
  const target = item.target;
  if (typeof target?.target === "string") {
    return target.target;
  }
  return JSON.stringify(target ?? {});
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

  function updateDraft<K extends keyof QdbGlMonthlyAnalysisManualAdjustmentRequest>(
    key: K,
    value: QdbGlMonthlyAnalysisManualAdjustmentRequest[K],
  ) {
    setDraft((current) => ({
      ...current,
      [key]: value,
    }));
  }

  async function handleSubmitAdjustment() {
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
      setErrorMessage(error instanceof Error ? error.message : "submit failed");
    }
  }

  async function handleRevoke(adjustmentId: string) {
    setErrorMessage(null);
    try {
      const response = await client.revokeQdbGlMonthlyAnalysisManualAdjustment(adjustmentId);
      setLastActionId(response.adjustment_id);
      await adjustmentsQuery.refetch();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "revoke failed");
    }
  }

  async function handleRestore(adjustmentId: string) {
    setErrorMessage(null);
    try {
      const response = await client.restoreQdbGlMonthlyAnalysisManualAdjustment(adjustmentId);
      setLastActionId(response.adjustment_id);
      await adjustmentsQuery.refetch();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "restore failed");
    }
  }

  async function handleExport() {
    setErrorMessage(null);
    try {
      const payload = await client.exportQdbGlMonthlyAnalysisManualAdjustmentsCsv(selectedMonth);
      downloadAuditCsv(payload.filename, payload.content);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "export failed");
    }
  }

  return (
    <section data-testid="monthly-operating-analysis-audit-page">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 16,
          padding: 20,
          borderRadius: 18,
          border: "1px solid #d7dfea",
          background: "#fbfcfe",
          marginBottom: 18,
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: 28, fontWeight: 700 }}>
            Monthly Operating Analysis Audit
          </h1>
          <p style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 14 }}>
            Review and operate on branch-specific manual adjustments.
          </p>
          {lastActionId ? (
            <p style={{ margin: "8px 0 0", color: "#5c6b82", fontSize: 12 }}>{lastActionId}</p>
          ) : null}
          {errorMessage ? (
            <p style={{ margin: "8px 0 0", color: "#b42318", fontSize: 12 }}>{errorMessage}</p>
          ) : null}
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "end" }}>
          <label style={{ display: "grid", gap: 8 }}>
            Report Month
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
            Export Audit
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gap: 12, marginBottom: 18 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr auto",
            gap: 12,
            padding: 12,
            borderRadius: 12,
            border: "1px solid #d7dfea",
            background: "#fbfcfe",
          }}
        >
          <select
            data-testid="monthly-operating-analysis-adjustment-class"
            value={draft.adjustment_class}
            onChange={(event) =>
              updateDraft(
                "adjustment_class",
                event.target.value as "mapping_adjustment" | "analysis_adjustment",
              )
            }
          >
            <option value="mapping_adjustment">mapping_adjustment</option>
            <option value="analysis_adjustment">analysis_adjustment</option>
          </select>
          <input
            data-testid="monthly-operating-analysis-adjustment-target"
            value={String(draft.target.target ?? "")}
            onChange={(event) => updateDraft("target", { target: event.target.value })}
            placeholder="target"
          />
          <input
            data-testid="monthly-operating-analysis-adjustment-value"
            value={draft.value}
            onChange={(event) => updateDraft("value", event.target.value)}
            placeholder="value"
          />
          <button
            type="button"
            data-testid="monthly-operating-analysis-adjustment-submit"
            onClick={() => void handleSubmitAdjustment()}
          >
            {editingAdjustmentId ? "Save Adjustment" : "Create Adjustment"}
          </button>
        </div>
      </div>

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
                  target: { target: serializeTarget(item) },
                  operator: item.operator as "ADD" | "DELTA" | "OVERRIDE",
                  value: item.value,
                  approval_status: item.approval_status as "approved" | "pending" | "rejected",
                });
              }}
            >
              Edit
            </button>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                data-testid={`monthly-operating-analysis-adjustment-revoke-${item.adjustment_id}`}
                onClick={() => void handleRevoke(item.adjustment_id)}
              >
                Revoke
              </button>
              <button
                type="button"
                data-testid={`monthly-operating-analysis-adjustment-restore-${item.adjustment_id}`}
                onClick={() => void handleRestore(item.adjustment_id)}
              >
                Restore
              </button>
            </div>
          </div>
        ))}
        {(adjustmentsQuery.data?.adjustments ?? []).length === 0 ? (
          <div style={{ color: "#8090a8", fontSize: 13 }}>No adjustments found.</div>
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
