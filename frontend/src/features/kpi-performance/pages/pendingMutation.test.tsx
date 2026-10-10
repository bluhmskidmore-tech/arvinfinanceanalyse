import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { KpiMetricWithValue, KpiOwner } from "../../../api/contracts";
import { createRealKpiClient } from "../../../api/kpiClient";
import KpiPerformancePage from "./KpiPerformancePage";

const client = vi.hoisted(() => ({
  getKpiOwners: vi.fn(), getKpiValues: vi.fn(), getKpiValuesSummary: vi.fn(),
  getKpiMetricById: vi.fn(), updateKpiMetric: vi.fn(), deleteKpiMetric: vi.fn(),
  updateKpiValue: vi.fn(), batchUpdateKpiValues: vi.fn(),
  createKpiMetric: vi.fn(),
  fetchAndRecalcKpi: vi.fn(),
}));
vi.mock("../../../api/client", () => ({ useApiClient: () => client }));

const owner: KpiOwner = {
  owner_id: 1, owner_name: "Synthetic A", org_unit: "Synthetic", person_name: null,
  year: 2026, scope_type: "department", scope_key: null, is_active: true,
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};
const metric: KpiMetricWithValue = {
  metric_id: 11, metric_code: "M1", metric_name: "Synthetic metric", owner_id: 1,
  year: 2026, major_category: "规模类", target_value: "100", score_weight: "10",
  scoring_rule_type: "LINEAR_RATIO", data_source_type: "AUTO", is_active: true,
  actual_value: "2", progress_pct: "0", as_of_date: "2026-06-30",
};
const kinds = ["value", "definition", "delete", "batch"] as const;
type Mutation = typeof kinds[number];

function deferred() {
  let resolve!: () => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<void>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}

function mutationMethod(kind: Mutation) {
  return kind === "value" ? client.updateKpiValue : kind === "definition" ? client.updateKpiMetric
    : kind === "delete" ? client.deleteKpiMetric : client.batchUpdateKpiValues;
}

beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  client.getKpiOwners.mockResolvedValue({ owners: [owner, { ...owner, owner_id: 2, owner_name: "Synthetic B" }] });
  client.getKpiValues.mockImplementation(async ({ owner_id }: { owner_id: number }) => ({
    metrics: [{ ...metric, owner_id }],
  }));
  client.getKpiMetricById.mockImplementation(async () => metric);
  client.getKpiValuesSummary.mockResolvedValue({
    owner_id: 1, year: 2026, period_type: "MONTH", period_value: 6, period_label: "Synthetic month",
    period_start_date: "2026-06-01", period_end_date: "2026-06-30", total_weight: "10", total_score: "0",
    metrics: [{ ...metric, period_actual_value: "2", period_progress_pct: "0", period_score_value: "0", data_date: "2026-06-30" }],
  });
});

async function openPage() {
  render(<KpiPerformancePage />);
  fireEvent.click(await screen.findByRole("button", { name: "Synthetic A" }));
  await screen.findByText(metric.metric_name);
}

async function openDialog(kind: Mutation) {
  if (kind === "batch") {
    fireEvent.click(screen.getByRole("button", { name: /批量导入/ }));
  } else if (kind === "value") {
    if (!screen.queryByRole("button", { name: "表单编辑完成情况" })) fireEvent.click(screen.getByText(metric.metric_name));
    fireEvent.click(screen.getByRole("button", { name: "表单编辑完成情况" }));
  } else {
    fireEvent.click(screen.getByRole("button", { name: "设置指标" }));
  }
  return screen.findByRole("dialog");
}

async function openCreateDialog() {
  fireEvent.click(within(screen.getByTestId("kpi-performance-action-row")).getByRole("button", { name: /新增指标/ }));
  const dialog = await screen.findByRole("dialog");
  fireEvent.change(within(dialog).getAllByRole("textbox")[0], { target: { value: "SYNTHETIC_NEW" } });
  fireEvent.change(within(dialog).getAllByRole("textbox")[1], { target: { value: "Synthetic created" } });
  return dialog;
}

async function closeDialog(dialog: HTMLElement) {
  fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
}

function submit(dialog: HTMLElement, kind: Mutation) {
  if (kind === "batch") {
    fireEvent.change(within(dialog).getByPlaceholderText("从 Excel 粘贴…"), { target: { value: "M1\t9\t0" } });
    fireEvent.click(within(dialog).getByRole("button", { name: /解\s*析/ }));
    fireEvent.click(within(dialog).getByRole("button", { name: /导入（1 条）/ }));
  } else if (kind === "delete") {
    fireEvent.click(within(dialog).getByRole("button", { name: /删除指标/ }));
    fireEvent.click(within(dialog).getByRole("button", { name: /确认删除/ }));
  } else {
    fireEvent.change(within(dialog).getAllByRole("textbox")[1], {
      target: { value: kind === "value" ? "9" : "Synthetic renamed" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: /保\s*存/ }));
  }
}

function attemptDismiss(dialog: HTMLElement) {
  const close = within(dialog).queryByRole("button", { name: "Close" });
  if (close) fireEvent.click(close);
  const wrap = dialog.closest(".ant-modal-wrap")!;
  fireEvent.keyDown(wrap, { key: "Escape", code: "Escape", keyCode: 27 });
  fireEvent.mouseDown(wrap);
  fireEvent.mouseUp(wrap);
  fireEvent.click(wrap);
  within(dialog).queryAllByRole("button", { name: /取\s*消/ }).forEach((button) => fireEvent.click(button));
}

function assertRefreshed(kind: Mutation) {
  const table = within(screen.getByTestId("kpi-metric-table-panel"));
  if (kind === "delete") {
    expect(table.queryByText(metric.metric_name)).not.toBeInTheDocument();
  } else if (kind === "definition") {
    expect(table.getByText("Synthetic renamed")).toBeInTheDocument();
  } else {
    expect(table.getByText(metric.metric_name).closest("tr")!.children[6]).toHaveTextContent("9.00");
  }
}

describe("KPI pending mutation dismissal contract", () => {
  it.each(kinds)("%s pending dismissal attempts still refresh the real page after successful mutation", async (kind) => {
    const pending = deferred();
    let saved = false;
    client.getKpiValues.mockImplementation(async () => ({ metrics: saved && kind === "delete" ? [] : [{
      ...metric, actual_value: saved ? "9" : "2", metric_name: saved && kind === "definition" ? "Synthetic renamed" : metric.metric_name,
    }] }));
    mutationMethod(kind).mockImplementationOnce(async () => {
      await pending.promise;
      saved = true;
      return { success_count: 1, failed_count: 0, errors: [] };
    });
    await openPage();
    const dialog = await openDialog(kind);
    submit(dialog, kind);
    expect(mutationMethod(kind)).toHaveBeenCalledTimes(1);
    attemptDismiss(dialog);
    await act(async () => { pending.resolve(); });
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(2));
    assertRefreshed(kind);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(mutationMethod(kind)).toHaveBeenCalledTimes(1);
  });

  it.each(kinds)("%s ordinary successful mutation refreshes and closes only its current dialog", async (kind) => {
    mutationMethod(kind).mockResolvedValueOnce({ success_count: 1, failed_count: 0, errors: [] });
    await openPage();
    submit(await openDialog(kind), kind);
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(mutationMethod(kind)).toHaveBeenCalledTimes(1);
  });

  it.each(kinds)("%s pending dismissal is blocked; failure stays visible and restores normal closing", async (kind) => {
    const pending = deferred();
    mutationMethod(kind).mockReturnValueOnce(pending.promise);
    await openPage();
    const dialog = await openDialog(kind);
    submit(dialog, kind);
    expect(within(dialog).queryByRole("button", { name: "Close" })).not.toBeInTheDocument();
    const footer = dialog.querySelector(".ant-modal-footer") as HTMLElement;
    expect(within(footer).getByRole("button", { name: /取\s*消/ })).toBeDisabled();
    attemptDismiss(dialog);
    expect(screen.getByRole("dialog")).toBe(dialog);
    await act(async () => { pending.reject(new Error("Synthetic write rejected")); });
    await screen.findByText("Synthetic write rejected");
    expect(client.getKpiValues).toHaveBeenCalledTimes(1);
    expect(within(dialog).getByRole("button", { name: "Close" })).toBeEnabled();
    expect(within(footer).getByRole("button", { name: /取\s*消/ })).toBeEnabled();
    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("batch keeps dismissal locked through the successful-result delay", async () => {
    client.batchUpdateKpiValues.mockResolvedValueOnce({ success_count: 1, failed_count: 0, errors: [] });
    await openPage();
    const dialog = await openDialog("batch");
    submit(dialog, "batch");
    await waitFor(() => expect(within(dialog).getByRole("button", { name: /导入（0 条）/ })).toBeDisabled());
    expect(within(dialog).queryByRole("button", { name: "Close" })).not.toBeInTheDocument();
    attemptDismiss(dialog);
    expect(screen.getByRole("dialog")).toBe(dialog);
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it.each([
    ["value", "owner"], ["value", "date"], ["value", "view"],
    ["definition", "owner"], ["definition", "date"], ["definition", "view"],
    ["batch", "owner"], ["batch", "date"], ["batch", "view"],
  ] as const)("late %s success does not refresh or close a new dialog after a %s switch", async (kind, change) => {
    const pending = deferred();
    mutationMethod(kind).mockImplementationOnce(async () => {
      await pending.promise;
      return kind === "batch" ? { success_count: 1, failed_count: 0, errors: [] } : metric;
    });
    await openPage();
    submit(await openDialog(kind), kind);
    if (change === "owner") {
      fireEvent.click(screen.getByRole("button", { name: "Synthetic B" }));
    } else if (change === "view") {
      fireEvent.mouseDown(screen.getByRole("combobox", { name: "KPI period type" }));
      fireEvent.click(screen.getByText("月度"));
    } else {
      const date = screen.getByRole("textbox", { name: "KPI as-of date" });
      fireEvent.change(date, { target: { value: "2026-07-31" } });
      fireEvent.keyDown(date, { key: "Enter", code: "Enter", keyCode: 13 });
    }
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await screen.findByText(metric.metric_name);
    fireEvent.click(screen.getByRole("button", { name: /新增指标/ }));
    const newer = await screen.findByRole("dialog");
    fireEvent.change(within(newer).getAllByRole("textbox")[1], { target: { value: "Keep my new draft" } });
    const reads = client.getKpiValues.mock.calls.length + client.getKpiValuesSummary.mock.calls.length;
    await act(async () => { pending.resolve(); });
    expect(screen.getByRole("dialog")).toBe(newer);
    expect(within(newer).getAllByRole("textbox")[1]).toHaveValue("Keep my new draft");
    expect(client.getKpiValues.mock.calls.length + client.getKpiValuesSummary.mock.calls.length).toBe(reads);
  });
});


describe("KPI explicit stop waiting", () => {
  it("a stopped create late success refreshes the page without closing or overwriting the new create draft", async () => {
    const pending = deferred();
    client.createKpiMetric.mockImplementationOnce(async () => { await pending.promise; return metric; });
    await openPage();
    const oldDialog = await openCreateDialog();
    fireEvent.click(within(oldDialog).getByRole("button", { name: /新\s*增/ }));
    fireEvent.click(within(oldDialog).getByRole("button", { name: "停止等待" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const newer = await openCreateDialog();
    fireEvent.change(within(newer).getAllByRole("textbox")[1], { target: { value: "Keep newer create draft" } });
    await act(async () => { pending.resolve(); });
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(2));
    expect(screen.getByRole("dialog")).toBe(newer);
    expect(within(newer).getAllByRole("textbox")[1]).toHaveValue("Keep newer create draft");
    expect(client.createKpiMetric).toHaveBeenCalledTimes(1);
  });

  it.each(kinds)("%s can leave an unresolved write and later refresh without resubmission", async (kind) => {
    const pending = deferred();
    let saved = false;
    client.getKpiValues.mockImplementation(async () => ({ metrics: saved && kind === "delete" ? [] : [{
      ...metric, actual_value: saved ? "9" : "2", metric_name: saved && kind === "definition" ? "Synthetic renamed" : metric.metric_name,
    }] }));
    mutationMethod(kind).mockImplementationOnce(async () => {
      await pending.promise; saved = true;
      return { success_count: 1, failed_count: 0, errors: [] };
    });
    await openPage();
    const dialog = await openDialog(kind);
    submit(dialog, kind);
    fireEvent.click(within(dialog).getByRole("button", { name: "停止等待" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByText(/写入结果尚未确认/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新核实" })).toBeEnabled();
    expect(mutationMethod(kind)).toHaveBeenCalledTimes(1);
    const reopened = await openDialog(kind);
    const mainAction = kind === "batch" ? /导入（0 条）/ : /保\s*存/;
    expect(within(reopened).getByRole("button", { name: mainAction })).toBeDisabled();
    await act(async () => { pending.resolve(); });
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(2));
    assertRefreshed(kind);
    expect(screen.getByRole("dialog")).toBe(reopened);
    expect(mutationMethod(kind)).toHaveBeenCalledTimes(1);
  });
});


describe("KPI stopped write scope and readback", () => {
  it("a new verification invalidates the previous successful readback, including when the new GET fails", async () => {
    const pending = deferred();
    client.updateKpiValue.mockReturnValueOnce(pending.promise);
    await openPage();
    const dialog = await openDialog("value");
    submit(dialog, "value");
    fireEvent.click(within(dialog).getByRole("button", { name: "停止等待" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await act(async () => { pending.reject(new TypeError("Synthetic write response lost")); });
    fireEvent.click(screen.getByRole("button", { name: "刷新核实" }));
    await screen.findByRole("button", { name: "已核实，继续编辑" });
    const latestRead = deferred();
    client.getKpiValues.mockReturnValueOnce(latestRead.promise);
    fireEvent.click(screen.getByRole("button", { name: "刷新核实" }));
    const couldResumeDuringRead = Boolean(screen.queryByRole("button", { name: "已核实，继续编辑" }));
    await act(async () => { latestRead.reject(new Error("Synthetic second read failed")); });
    expect(couldResumeDuringRead).toBe(false);
    expect(screen.queryByRole("button", { name: "已核实，继续编辑" })).not.toBeInTheDocument();
    const locked = await openCreateDialog();
    expect(within(locked).getByRole("button", { name: /新\s*增/ })).toBeDisabled();
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
  });

  it("late stopped success cannot refresh another owner or close its new dialog", async () => {
    const pending = deferred();
    client.updateKpiValue.mockReturnValueOnce(pending.promise);
    await openPage();
    const oldDialog = await openDialog("value");
    submit(oldDialog, "value");
    fireEvent.click(within(oldDialog).getByRole("button", { name: "停止等待" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Synthetic B" }));
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(2));
    const nextDialog = await openDialog("value");
    await act(async () => { pending.resolve(); });
    expect(screen.getByRole("dialog")).toBe(nextDialog);
    expect(client.getKpiValues).toHaveBeenCalledTimes(2);
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
  });

  it("readback never resubmits and a stopped rejection remains visible", async () => {
    const pending = deferred();
    client.updateKpiValue.mockReturnValueOnce(pending.promise);
    await openPage();
    const dialog = await openDialog("value");
    submit(dialog, "value");
    fireEvent.click(within(dialog).getByRole("button", { name: "停止等待" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "刷新核实" }));
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(2));
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/写入结果尚未确认/)).toBeInTheDocument();
    const reopened = await openDialog("value");
    fireEvent.click(within(reopened).getByRole("button", { name: /保\s*存/ }));
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
    await act(async () => { pending.reject(new Error("Synthetic response lost")); });
    expect(await screen.findByText(/Synthetic response lost/)).toBeInTheDocument();
    expect(within(reopened).getByRole("button", { name: /保\s*存/ })).toBeDisabled();
    expect(screen.getByRole("dialog")).toBe(reopened);
    expect(client.getKpiValues).toHaveBeenCalledTimes(2);
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "已核实，继续编辑" })).not.toBeInTheDocument();
    fireEvent.click(within(reopened).getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "刷新核实" }));
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(3));
    fireEvent.click(await screen.findByRole("button", { name: "已核实，继续编辑" }));
    const verified = await openDialog("value");
    expect(within(verified).getByRole("button", { name: /保\s*存/ })).toBeEnabled();
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
  });
});

describe("KPI unconfirmed ordinary writes and refreshed drafts", () => {
  it("a successful recalc with failed readback does not claim the page updated or repeat the write", async () => {
    client.fetchAndRecalcKpi.mockResolvedValueOnce({ total_metrics: 1, fetched_count: 1, scored_count: 1, failed_count: 0, skipped_count: 0 });
    await openPage();
    client.getKpiValues.mockRejectedValueOnce(new Error("Synthetic recalc readback failed"));
    fireEvent.click(screen.getByRole("button", { name: /抓取并重算/ }));
    expect(await screen.findByText("抓取并重算请求已成功，但当前页面刷新失败，请刷新核实数据。")).toBeInTheDocument();
    expect(screen.queryByText("抓取并重算已完成")).not.toBeInTheDocument();
    expect(screen.queryByText("抓取并重算失败")).not.toBeInTheDocument();
    expect(client.getKpiValues).toHaveBeenCalledTimes(2);
    expect(client.fetchAndRecalcKpi).toHaveBeenCalledTimes(1);
  });

  it("recalc response loss requires readback and explicit continuation without another write", async () => {
    client.fetchAndRecalcKpi.mockRejectedValueOnce(new TypeError("Synthetic recalc response lost"));
    await openPage();
    fireEvent.click(screen.getByRole("button", { name: /抓取并重算/ }));
    await screen.findByText(/抓取并重算请求结果未知/);
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    expect(client.getKpiValues).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "刷新核实" }));
    fireEvent.click(await screen.findByRole("button", { name: "已核实，继续编辑" }));
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeEnabled();
    expect(screen.getByText(/原写入结果仍未知/)).toBeInTheDocument();
    expect(client.fetchAndRecalcKpi).toHaveBeenCalledTimes(1);
  });

  it("a new verification revokes an already released unknown write when the new GET fails", async () => {
    client.updateKpiValue.mockRejectedValueOnce(new TypeError("Synthetic response lost"));
    await openPage();
    const dialog = await openDialog("value");
    submit(dialog, "value");
    await waitFor(() => expect(within(dialog).getByRole("button", { name: "Close" })).toBeEnabled());
    await closeDialog(dialog);
    fireEvent.click(screen.getByRole("button", { name: "刷新核实" }));
    fireEvent.click(await screen.findByRole("button", { name: "已核实，继续编辑" }));
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeEnabled();
    const read = deferred();
    client.getKpiValues.mockReturnValueOnce(read.promise);
    fireEvent.click(screen.getByRole("button", { name: "刷新核实" }));
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    await act(async () => { read.reject(new Error("Synthetic released read failed")); });
    expect(screen.queryByRole("button", { name: "已核实，继续编辑" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
  });

  it.each(["date", "view"] as const)("a %s switch cannot verify or release the original unknown write with different-context data", async (change) => {
    client.updateKpiValue.mockRejectedValueOnce(new TypeError("Synthetic scoped response lost"));
    await openPage();
    const originalDate = client.getKpiValues.mock.calls[0][0].as_of_date;
    const dialog = await openDialog("value");
    submit(dialog, "value");
    await waitFor(() => expect(within(dialog).getByRole("button", { name: "Close" })).toBeEnabled());
    await closeDialog(dialog);
    fireEvent.click(screen.getByRole("button", { name: "刷新核实" }));
    await screen.findByRole("button", { name: "已核实，继续编辑" });
    if (change === "date") {
      const date = screen.getByRole("textbox", { name: "KPI as-of date" });
      fireEvent.change(date, { target: { value: "2026-07-31" } });
      fireEvent.keyDown(date, { key: "Enter", code: "Enter", keyCode: 13 });
      await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(3));
    } else {
      fireEvent.mouseDown(screen.getByRole("combobox", { name: "KPI period type" }));
      fireEvent.click(screen.getByText("月度"));
      await waitFor(() => expect(client.getKpiValuesSummary).toHaveBeenCalledTimes(1));
    }
    expect(screen.getByText(/原提交口径/)).toHaveTextContent(originalDate.replace(/-(0?)(\d+)-(0?)(\d+)/, "年$2月$4日"));
    expect(screen.getByRole("button", { name: "刷新核实" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "已核实，继续编辑" })).not.toBeInTheDocument();
    const locked = await openCreateDialog();
    expect(within(locked).getByRole("button", { name: /新\s*增/ })).toBeDisabled();
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
  });

  it("a late verification GET cannot unlock after switching the view", async () => {
    client.updateKpiValue.mockRejectedValueOnce(new TypeError("Synthetic scoped response lost"));
    await openPage();
    const dialog = await openDialog("value");
    submit(dialog, "value");
    await waitFor(() => expect(within(dialog).getByRole("button", { name: "Close" })).toBeEnabled());
    await closeDialog(dialog);
    let resolveRead!: (value: { metrics: KpiMetricWithValue[] }) => void;
    client.getKpiValues.mockReturnValueOnce(new Promise((resolve) => { resolveRead = resolve; }));
    fireEvent.click(screen.getByRole("button", { name: "刷新核实" }));
    fireEvent.mouseDown(screen.getByRole("combobox", { name: "KPI period type" }));
    fireEvent.click(screen.getByText("月度"));
    await screen.findByText("Synthetic month");
    await act(async () => { resolveRead({ metrics: [metric] }); });
    expect(screen.queryByRole("button", { name: "已核实，继续编辑" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新核实" })).toBeDisabled();
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
  });


  it.each(["response-lost-after-insert", "server-422"] as const)("ordinary create %s requires successful readback and explicit continuation before another POST", async (failure) => {
    let inserted = false;
    const fetchImpl = vi.fn<typeof fetch>().mockImplementation(async () => {
      if (failure === "server-422") return new Response("Synthetic validation rejected", { status: 422 });
      inserted = true;
      throw new TypeError("Synthetic response lost after insert");
    });
    client.createKpiMetric.mockImplementation(createRealKpiClient({ fetchImpl, baseUrl: "https://synthetic.invalid" }).createKpiMetric);
    client.getKpiValues.mockImplementation(async () => ({ metrics: inserted
      ? [metric, { ...metric, metric_id: 12, metric_code: "SYNTHETIC_NEW", metric_name: "Synthetic created" }]
      : [metric] }));
    await openPage();
    const dialog = await openCreateDialog();
    const submitCreate = within(dialog).getByRole("button", { name: /新\s*增/ });
    fireEvent.click(submitCreate);
    fireEvent.click(submitCreate);
    await waitFor(() => expect(within(dialog).getByRole("button", { name: "Close" })).toBeEnabled());
    expect(submitCreate).toBeDisabled();
    fireEvent.click(submitCreate);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(fetchImpl.mock.calls[0][1]?.method).toBe("POST");
    expect(client.getKpiValues).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/请核对是否已创建同名或同代码指标/)).toBeInTheDocument();
    await closeDialog(dialog);
    client.getKpiValues.mockRejectedValueOnce(new Error("Synthetic readback failed"));
    fireEvent.click(screen.getByRole("button", { name: "刷新核实" }));
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByRole("button", { name: "刷新核实" })).not.toHaveClass("ant-btn-loading"));
    expect(screen.queryByRole("button", { name: "已核实，继续编辑" })).not.toBeInTheDocument();
    const locked = await openCreateDialog();
    expect(within(locked).getByRole("button", { name: /新\s*增/ })).toBeDisabled();
    await closeDialog(locked);
    fireEvent.click(screen.getByRole("button", { name: "刷新核实" }));
    const resume = await screen.findByRole("button", { name: "已核实，继续编辑" });
    if (inserted) expect(within(screen.getByTestId("kpi-metric-table-panel")).getByText("Synthetic created")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    fireEvent.click(resume);
    expect(screen.getByText(/原写入结果仍未知/)).toBeInTheDocument();
    expect(screen.getByText(/未知请求仍可能有迟到写入/)).toBeInTheDocument();
    const continued = await openCreateDialog();
    expect(within(continued).getByRole("button", { name: /新\s*增/ })).toBeEnabled();
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it.each(kinds)("ordinary %s response loss locks further writes without treating rejection as no-write proof", async (kind) => {
    mutationMethod(kind).mockRejectedValueOnce(new TypeError("Synthetic response lost"));
    await openPage();
    const dialog = await openDialog(kind);
    submit(dialog, kind);
    await waitFor(() => expect(within(dialog).getByRole("button", { name: "Close" })).toBeEnabled());
    const action = kind === "batch" ? /导入（1 条）/ : /保\s*存/;
    expect(within(dialog).getByRole("button", { name: action })).toBeDisabled();
    if (kind === "batch") expect(within(dialog).queryByText(/成功 0 条，失败 1 条/)).not.toBeInTheDocument();
    await closeDialog(dialog);
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "刷新核实" }));
    fireEvent.click(await screen.findByRole("button", { name: "已核实，继续编辑" }));
    expect(mutationMethod(kind)).toHaveBeenCalledTimes(1);
    expect(client.getKpiValues).toHaveBeenCalledTimes(2);
  });

  it("ordinary inline response loss uses the same unknown-write recovery without resubmission", async () => {
    client.updateKpiValue.mockRejectedValueOnce(new TypeError("Synthetic inline response lost"));
    await openPage();
    fireEvent.click(screen.getByText("100.00"));
    fireEvent.click(screen.getByRole("button", { name: "保存编辑" }));
    await screen.findByRole("button", { name: "刷新核实" });
    expect(screen.queryByRole("button", { name: "保存编辑" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "刷新核实" }));
    fireEvent.click(await screen.findByRole("button", { name: "已核实，继续编辑" }));
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
  });

  it("stopped batch late success refreshes rows but preserves the newer draft and requires reparse", async () => {
    const pending = deferred();
    let saved = false;
    client.getKpiValues.mockImplementation(async () => ({ metrics: [{ ...metric, metric_id: saved ? 12 : 11, actual_value: saved ? "9" : "2" }] }));
    client.batchUpdateKpiValues.mockImplementationOnce(async () => {
      await pending.promise;
      saved = true;
      return { success_count: 1, failed_count: 0, errors: [] };
    });
    await openPage();
    const oldDialog = await openDialog("batch");
    submit(oldDialog, "batch");
    fireEvent.click(within(oldDialog).getByRole("button", { name: "停止等待" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const newer = await openDialog("batch");
    const draft = within(newer).getByPlaceholderText("从 Excel 粘贴…");
    fireEvent.change(draft, { target: { value: "M1\t123\t0" } });
    fireEvent.click(within(newer).getByRole("button", { name: /解\s*析/ }));
    await act(async () => { pending.resolve(); });
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(2));
    assertRefreshed("batch");
    expect(screen.getByRole("dialog")).toBe(newer);
    expect(draft).toHaveValue("M1\t123\t0");
    expect(within(newer).getByRole("button", { name: /导入（0 条）/ })).toBeDisabled();
    expect(client.batchUpdateKpiValues).toHaveBeenCalledTimes(1);
    fireEvent.click(within(newer).getByRole("button", { name: /解\s*析/ }));
    const another = deferred();
    client.batchUpdateKpiValues.mockReturnValueOnce(another.promise);
    const importButton = within(newer).getByRole("button", { name: /导入（1 条）/ });
    fireEvent.click(importButton);
    fireEvent.click(importButton);
    expect(client.batchUpdateKpiValues).toHaveBeenCalledTimes(2);
    expect(client.batchUpdateKpiValues.mock.calls[1][1]).toEqual([{ metric_id: 12, actual_value: "123", progress_pct: "0" }]);
  });
});
