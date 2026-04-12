import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type {
  ProductCategoryManualAdjustmentPayload,
  ProductCategoryManualAdjustmentQuery,
  ProductCategoryManualAdjustmentRequest,
} from "../../../api/contracts";

const PAGE_SIZE_OPTIONS = [2, 10, 20, 50];
const SORT_FIELD_OPTIONS = ["created_at", "account_code", "approval_status", "event_type", "operator", "currency"] as const;
const SORT_DIR_OPTIONS = ["desc", "asc"] as const;

function buildDefaultAuditFilters(): ProductCategoryManualAdjustmentQuery {
  return {
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
}

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

function isUtcIsoInput(value: string) {
  if (!value) {
    return true;
  }
  return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{3})?)?Z$/.test(value) && !Number.isNaN(Date.parse(value));
}

function rangeLabel(offset: number, limit: number, total: number) {
  return total === 0 ? "0 / 0" : `${offset + 1}-${Math.min(offset + limit, total)} / ${total}`;
}

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

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export default function ProductCategoryAdjustmentAuditPage() {
  const client = useApiClient();
  const [selectedDate, setSelectedDate] = useState("");
  const [showManualForm, setShowManualForm] = useState(false);
  const [editingAdjustmentId, setEditingAdjustmentId] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [adjustmentError, setAdjustmentError] = useState<string | null>(null);
  const [draft, setDraft] = useState<ProductCategoryManualAdjustmentRequest>(buildAdjustmentDraft(""));
  const [filterDraft, setFilterDraft] = useState<ProductCategoryManualAdjustmentQuery>(() => buildDefaultAuditFilters());
  const [appliedFilters, setAppliedFilters] = useState<ProductCategoryManualAdjustmentQuery>(() => buildDefaultAuditFilters());
  const [currentLimit, setCurrentLimit] = useState(20);
  const [currentOffset, setCurrentOffset] = useState(0);
  const [eventLimit, setEventLimit] = useState(20);
  const [eventOffset, setEventOffset] = useState(0);

  const resetAuditPagination = () => {
    setCurrentOffset(0);
    setEventOffset(0);
  };

  const datesQuery = useQuery({
    queryKey: ["product-category-audit", "dates", client.mode],
    queryFn: () => client.getProductCategoryDates(),
    retry: false,
  });

  useEffect(() => {
    if (!selectedDate && datesQuery.data?.result.report_dates.length) {
      setSelectedDate(datesQuery.data.result.report_dates[0] ?? "");
    }
  }, [datesQuery.data, selectedDate]);

  useEffect(() => {
    setDraft((current) => ({ ...current, report_date: selectedDate }));
    resetAuditPagination();
  }, [selectedDate]);

  const adjustmentsQuery = useQuery({
    queryKey: ["product-category-audit", "adjustments", client.mode, selectedDate, appliedFilters, currentLimit, currentOffset, eventLimit, eventOffset],
    queryFn: () => client.getProductCategoryManualAdjustments(selectedDate, { ...appliedFilters, adjustmentLimit: currentLimit, adjustmentOffset: currentOffset, limit: eventLimit, offset: eventOffset }),
    enabled: Boolean(selectedDate),
    retry: false,
  });

  const updateField = <K extends keyof ProductCategoryManualAdjustmentRequest>(key: K, value: ProductCategoryManualAdjustmentRequest[K]) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };
  const updateFilter = <K extends keyof ProductCategoryManualAdjustmentQuery>(key: K, value: ProductCategoryManualAdjustmentQuery[K]) => {
    setFilterDraft((current) => ({ ...current, [key]: value }));
  };

  const applyFilters = () => {
    const nextFilters = { ...filterDraft, createdAtFrom: filterDraft.createdAtFrom?.trim() ?? "", createdAtTo: filterDraft.createdAtTo?.trim() ?? "" };
    if (!isUtcIsoInput(nextFilters.createdAtFrom ?? "") || !isUtcIsoInput(nextFilters.createdAtTo ?? "")) {
      setAdjustmentError("created_at range must use ISO 8601 UTC, for example 2026-04-10T10:30:00Z");
      return;
    }
    setAdjustmentError(null);
    setFilterDraft(nextFilters);
    setAppliedFilters(nextFilters);
    resetAuditPagination();
  };

  const resetFilters = () => {
    const nextFilters = buildDefaultAuditFilters();
    setAdjustmentError(null);
    setFilterDraft(nextFilters);
    setAppliedFilters(nextFilters);
    resetAuditPagination();
  };

  const refreshAuditData = async () => {
    let payload = await client.refreshProductCategoryPnl();
    if (payload.run_id && payload.status !== "completed") {
      for (let attempt = 0; attempt < 20; attempt += 1) {
        await wait(20);
        payload = await client.getProductCategoryRefreshStatus(payload.run_id);
        if (payload.status === "completed") {
          break;
        }
      }
    }
    if (payload.status !== "completed") {
      throw new Error(payload.detail ?? `Refresh did not complete: ${payload.status}`);
    }
    await datesQuery.refetch();
    await adjustmentsQuery.refetch();
  };

  const submitDraft = async () => {
    setAdjustmentError(null);
    if (!draft.report_date || !draft.account_code.trim()) {
      setAdjustmentError("report_date and account_code are required");
      return;
    }
    if (!draft.beginning_balance && !draft.ending_balance && !draft.monthly_pnl && !draft.daily_avg_balance && !draft.annual_avg_balance) {
      setAdjustmentError("At least one adjustment value is required");
      return;
    }
    setIsRefreshing(true);
    try {
      if (editingAdjustmentId) {
        await client.updateProductCategoryManualAdjustment(editingAdjustmentId, draft);
      } else {
        await client.createProductCategoryManualAdjustment(draft);
      }
      await refreshAuditData();
      setShowManualForm(false);
      setEditingAdjustmentId(null);
      setDraft(buildAdjustmentDraft(selectedDate));
    } catch (error) {
      setAdjustmentError(error instanceof Error ? error.message : "Save failed");
    } finally {
      setIsRefreshing(false);
    }
  };

  const exportAudit = async () => {
    const payload = await client.exportProductCategoryManualAdjustmentsCsv(selectedDate, { ...appliedFilters });
    downloadAuditCsv(payload.filename, payload.content);
  };

  const currentTotal = adjustmentsQuery.data?.adjustment_count ?? 0;
  const eventTotal = adjustmentsQuery.data?.event_total ?? 0;

  return (
    <section style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
        <div>
          <h1 style={{ margin: 0 }}>Product Category Adjustment Audit</h1>
          <p style={{ margin: "8px 0 0", color: "#5c6b82" }}>The page only sends query params and renders the returned order.</p>
          {adjustmentError ? <p style={{ color: "#b42318" }}>{adjustmentError}</p> : null}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <a href="/product-category-pnl">Back</a>
          <button type="button" data-testid="audit-export-button" onClick={() => void exportAudit()} disabled={adjustmentsQuery.isLoading}>Export audit</button>
          <button type="button" data-testid="audit-manual-button" onClick={() => { setShowManualForm((current) => !current); setEditingAdjustmentId(null); setDraft(buildAdjustmentDraft(selectedDate)); }}>+ Manual entry</button>
          <button type="button" data-testid="audit-refresh-button" disabled={isRefreshing} onClick={() => void refreshAuditData()}>{isRefreshing ? "Refreshing..." : "Refresh PnL data"}</button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
        <label>Report date<select aria-label="audit-report-date" value={selectedDate} onChange={(event) => setSelectedDate(event.target.value)}>{(datesQuery.data?.result.report_dates ?? []).map((reportDate) => <option key={reportDate} value={reportDate}>{reportDate}</option>)}</select></label>
        <label>Adjustment ID<input data-testid="audit-filter-adjustment-id" value={filterDraft.adjustmentId ?? ""} onChange={(event) => updateFilter("adjustmentId", event.target.value)} /></label>
        <label>Account code<input data-testid="audit-filter-account-code" value={filterDraft.accountCode ?? ""} onChange={(event) => updateFilter("accountCode", event.target.value)} /></label>
        <label>Approval status<select data-testid="audit-filter-approval-status" value={filterDraft.approvalStatus ?? ""} onChange={(event) => updateFilter("approvalStatus", event.target.value)}><option value="">all</option><option value="approved">approved</option><option value="pending">pending</option><option value="rejected">rejected</option></select></label>
        <label>Event type<select data-testid="audit-filter-event-type" value={filterDraft.eventType ?? ""} onChange={(event) => updateFilter("eventType", event.target.value)}><option value="">all</option><option value="created">created</option><option value="edited">edited</option><option value="revoked">revoked</option><option value="restored">restored</option></select></label>
        <label>Current sort field<select data-testid="audit-current-sort-field" value={filterDraft.currentSortField ?? "created_at"} onChange={(event) => updateFilter("currentSortField", event.target.value)}>{SORT_FIELD_OPTIONS.map((option) => <option key={`current-sort-field-${option}`} value={option}>{option}</option>)}</select></label>
        <label>Current sort dir<select data-testid="audit-current-sort-dir" value={filterDraft.currentSortDir ?? "desc"} onChange={(event) => updateFilter("currentSortDir", event.target.value as "asc" | "desc")}>{SORT_DIR_OPTIONS.map((option) => <option key={`current-sort-dir-${option}`} value={option}>{option}</option>)}</select></label>
        <label>Event sort field<select data-testid="audit-event-sort-field" value={filterDraft.eventSortField ?? "created_at"} onChange={(event) => updateFilter("eventSortField", event.target.value)}>{SORT_FIELD_OPTIONS.map((option) => <option key={`event-sort-field-${option}`} value={option}>{option}</option>)}</select></label>
        <label>Event sort dir<select data-testid="audit-event-sort-dir" value={filterDraft.eventSortDir ?? "desc"} onChange={(event) => updateFilter("eventSortDir", event.target.value as "asc" | "desc")}>{SORT_DIR_OPTIONS.map((option) => <option key={`event-sort-dir-${option}`} value={option}>{option}</option>)}</select></label>
        <label>created_at from (UTC)<input data-testid="audit-created-at-from" placeholder="2026-04-10T10:30:00Z" value={filterDraft.createdAtFrom ?? ""} onChange={(event) => updateFilter("createdAtFrom", event.target.value)} /></label>
        <label>created_at to (UTC)<input data-testid="audit-created-at-to" placeholder="2026-04-10T11:00:00Z" value={filterDraft.createdAtTo ?? ""} onChange={(event) => updateFilter("createdAtTo", event.target.value)} /></label>
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}><input type="checkbox" data-testid="audit-exact-adjustment-id" checked={Boolean(filterDraft.adjustmentIdExact)} onChange={(event) => updateFilter("adjustmentIdExact", event.target.checked)} />Exact adjustment ID</label>
        <label>Event page size<select data-testid="audit-page-size-select" value={String(eventLimit)} onChange={(event) => { setEventLimit(Number(event.target.value)); setEventOffset(0); }}>{PAGE_SIZE_OPTIONS.map((value) => <option key={`event-page-size-${value}`} value={value}>{value}</option>)}</select></label>
        <div style={{ display: "flex", alignItems: "end", gap: 8 }}><button type="button" data-testid="audit-apply-filters" onClick={applyFilters}>Apply query</button><button type="button" data-testid="audit-reset-filters" onClick={resetFilters}>Reset</button></div>
      </div>

      {showManualForm ? (
        <div data-testid="audit-manual-form" style={{ display: "grid", gap: 12 }}>
          <div>{editingAdjustmentId ? "Edit manual adjustment" : "Create manual adjustment"}</div>
          <label>account_code<input aria-label="audit-account-code" value={draft.account_code} onChange={(event) => updateField("account_code", event.target.value)} /></label>
          <label>account_name<input aria-label="audit-account-name" value={draft.account_name ?? ""} onChange={(event) => updateField("account_name", event.target.value)} /></label>
          <label>monthly_pnl<input aria-label="audit-monthly-pnl" value={draft.monthly_pnl ?? ""} onChange={(event) => updateField("monthly_pnl", event.target.value || null)} /></label>
          <div style={{ display: "flex", gap: 8 }}><button type="button" data-testid="audit-manual-submit" onClick={() => void submitDraft()} disabled={isRefreshing}>{editingAdjustmentId ? "Save and refresh" : "Submit and refresh"}</button><button type="button" onClick={() => { setShowManualForm(false); setEditingAdjustmentId(null); setDraft(buildAdjustmentDraft(selectedDate)); }}>Cancel</button></div>
        </div>
      ) : null}

      <section style={{ display: "grid", gap: 12 }}>
        <h2 style={{ margin: 0 }}>Adjustment audit</h2>
        {adjustmentsQuery.isLoading ? <div>Loading...</div> : null}
        {adjustmentsQuery.isError ? (
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span>Failed to load audit data.</span>
            <button type="button" onClick={() => void adjustmentsQuery.refetch()}>
              Retry
            </button>
          </div>
        ) : null}
        {!adjustmentsQuery.isLoading && !adjustmentsQuery.isError && currentTotal === 0 && eventTotal === 0 ? (
          <div>No audit data.</div>
        ) : null}
        {!adjustmentsQuery.isLoading && !adjustmentsQuery.isError && (currentTotal > 0 || eventTotal > 0) ? (
        <div style={{ display: "grid", gap: 16 }}>
          <div data-testid="audit-current-state" style={{ display: "grid", gap: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <div>Current state ({currentTotal})</div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <select data-testid="audit-current-page-size-select" value={String(currentLimit)} onChange={(event) => { setCurrentLimit(Number(event.target.value)); setCurrentOffset(0); }}>{PAGE_SIZE_OPTIONS.map((value) => <option key={`current-page-size-${value}`} value={value}>{value}</option>)}</select>
                <span>{rangeLabel(currentOffset, currentLimit, currentTotal)}</span>
                <button type="button" data-testid="audit-current-prev-page" disabled={currentOffset === 0} onClick={() => setCurrentOffset((current) => Math.max(0, current - currentLimit))}>Prev</button>
                <button type="button" data-testid="audit-current-next-page" disabled={currentOffset + currentLimit >= currentTotal} onClick={() => setCurrentOffset((current) => current + currentLimit)}>Next</button>
              </div>
            </div>
            {(adjustmentsQuery.data?.adjustments ?? []).map((item: ProductCategoryManualAdjustmentPayload) => (
              <div key={`audit-current-${item.adjustment_id}`} style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.4fr) repeat(3, minmax(0, 0.7fr)) auto auto auto", gap: 8, alignItems: "center" }}>
                <div><strong>{item.account_code}</strong><div>{item.account_name || "Unnamed account"}</div><div>{item.event_type}</div></div>
                <div>{item.currency}</div>
                <div>{item.operator}</div>
                <div>{item.approval_status}</div>
                <button type="button" data-testid={`audit-edit-${item.adjustment_id}`} disabled={isRefreshing} onClick={() => { setEditingAdjustmentId(item.adjustment_id); setDraft({ report_date: item.report_date, operator: item.operator as "ADD" | "DELTA" | "OVERRIDE", approval_status: item.approval_status as "approved" | "pending" | "rejected", account_code: item.account_code, currency: item.currency as "CNX" | "CNY", account_name: item.account_name ?? "", beginning_balance: item.beginning_balance ?? null, ending_balance: item.ending_balance ?? null, monthly_pnl: item.monthly_pnl ?? null, daily_avg_balance: item.daily_avg_balance ?? null, annual_avg_balance: item.annual_avg_balance ?? null }); setShowManualForm(true); }}>Edit</button>
                <button type="button" data-testid={`audit-revoke-${item.adjustment_id}`} disabled={item.approval_status !== "approved" || isRefreshing} onClick={() => void client.revokeProductCategoryManualAdjustment(item.adjustment_id).then(refreshAuditData).catch((error: unknown) => setAdjustmentError(error instanceof Error ? error.message : "Revoke failed"))}>Revoke</button>
                <button type="button" data-testid={`audit-restore-${item.adjustment_id}`} disabled={item.approval_status !== "rejected" || isRefreshing} onClick={() => void client.restoreProductCategoryManualAdjustment(item.adjustment_id).then(refreshAuditData).catch((error: unknown) => setAdjustmentError(error instanceof Error ? error.message : "Restore failed"))}>Restore</button>
              </div>
            ))}
          </div>

          <div data-testid="audit-event-list" style={{ display: "grid", gap: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <div>Event timeline ({eventTotal})</div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span>{rangeLabel(eventOffset, eventLimit, eventTotal)}</span>
                <button type="button" data-testid="audit-prev-page" disabled={eventOffset === 0} onClick={() => setEventOffset((current) => Math.max(0, current - eventLimit))}>Prev</button>
                <button type="button" data-testid="audit-next-page" disabled={eventOffset + eventLimit >= eventTotal} onClick={() => setEventOffset((current) => current + eventLimit)}>Next</button>
              </div>
            </div>
            {(adjustmentsQuery.data?.events ?? []).map((item: ProductCategoryManualAdjustmentPayload) => (
              <div key={`audit-event-${item.adjustment_id}-${item.created_at}-${item.event_type}`} data-testid={`audit-event-${item.adjustment_id}-${item.event_type}`} style={{ display: "grid", gridTemplateColumns: "repeat(5, minmax(0, 1fr))", gap: 8 }}>
                <div>{item.created_at}</div>
                <div>{item.account_code}</div>
                <div>{item.event_type}</div>
                <div>{item.approval_status}</div>
                <div>{item.currency}</div>
              </div>
            ))}
          </div>
        </div>
        ) : null}
      </section>
    </section>
  );
}
