import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { KpiMetricWithValue, KpiOwner } from "../../../api/contracts";
import { createRealKpiClient } from "../../../api/kpiClient";
import { BatchPasteModal } from "./BatchPasteModal";
import { MetricEditModal } from "./MetricEditModal";
import { MetricManageModal } from "./MetricManageModal";
import { MetricTable } from "./MetricTable";

const client = vi.hoisted(() => ({
  updateKpiMetric: vi.fn(),
  createKpiMetric: vi.fn(),
  deleteKpiMetric: vi.fn(),
  updateKpiValue: vi.fn(),
  batchUpdateKpiValues: vi.fn(),
}));
vi.mock("../../../api/client", () => ({ useApiClient: () => client }));

const owner: KpiOwner = {
  owner_id: 1, owner_name: "Synthetic A", org_unit: "Synthetic", person_name: null,
  year: 2026, scope_type: "department", scope_key: null, is_active: true,
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};
const metric: KpiMetricWithValue = {
  metric_id: 11, metric_code: "M1", metric_name: "Synthetic metric", owner_id: 1,
  year: 2026, major_category: "规模类", target_value: "100", score_weight: "0",
  scoring_rule_type: "LINEAR_RATIO", data_source_type: "AUTO", is_active: true,
  actual_value: "0", progress_pct: "0", as_of_date: "2026-06-30",
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

beforeEach(() => { vi.resetAllMocks(); });

describe("KPI submission object and date binding", () => {
  it("preserves nonmanual definition types and valid zero on an ordinary edit", async () => {
    render(<MetricManageModal open mode="edit" metric={metric} owner={owner} onClose={vi.fn()} onSuccess={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }));
    await waitFor(() => expect(client.updateKpiMetric).toHaveBeenCalledWith(11, expect.objectContaining({
      data_source_type: "AUTO", scoring_rule_type: "LINEAR_RATIO", score_weight: "0",
    })));
  });

  it("keeps MANUAL defaults for a new definition", async () => {
    render(<MetricManageModal open mode="create" owner={owner} onClose={vi.fn()} onSuccess={vi.fn()} />);
    fireEvent.change(screen.getAllByRole("textbox")[1], { target: { value: "Synthetic new metric" } });
    fireEvent.click(screen.getByRole("button", { name: /新\s*增/ }));
    await waitFor(() => expect(client.createKpiMetric).toHaveBeenCalledWith(expect.objectContaining({
      data_source_type: "MANUAL", scoring_rule_type: "MANUAL", owner_id: 1,
    })));
  });

  it("rejects a definition belonging to another owner", () => {
    render(<MetricManageModal open mode="edit" metric={metric} owner={{ ...owner, owner_id: 2 }} onClose={vi.fn()} onSuccess={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }));
    expect(client.updateKpiMetric).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("指标与当前考核对象不一致");
  });

  it("ignores a definition save after closing and reopening", async () => {
    const pending = deferred<undefined>();
    client.updateKpiMetric.mockReturnValueOnce(pending.promise);
    const props = { open: true, mode: "edit" as const, metric, owner, onClose: vi.fn(), onSuccess: vi.fn() };
    const view = render(<MetricManageModal {...props} />);
    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }));
    view.rerender(<MetricManageModal {...props} open={false} />);
    view.rerender(<MetricManageModal {...props} />);
    await act(async () => { pending.resolve(undefined); });
    expect(props.onSuccess).not.toHaveBeenCalled();
  });

  it("uses the historical row date in the full form and discloses the write date", async () => {
    render(<MetricEditModal open metric={metric} asOfDate="2026-10-06" onClose={vi.fn()} onSaveSuccess={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }));
    await waitFor(() => expect(client.updateKpiValue).toHaveBeenCalledWith(0, 11, "2026-06-30", expect.objectContaining({ actual_value: "0", progress_pct: "0" })));
    expect(screen.getByText("2026-06-30")).toBeInTheDocument();
  });

  it("serializes a historical form save through the real client as a date-bound POST", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response("{}", { status: 201 }));
    client.updateKpiValue.mockImplementationOnce(createRealKpiClient({ fetchImpl, baseUrl: "https://synthetic.invalid" }).updateKpiValue);
    render(<MetricEditModal open metric={metric} asOfDate="2026-10-06" onClose={vi.fn()} onSaveSuccess={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }));
    await waitFor(() => expect(fetchImpl).toHaveBeenCalledTimes(1));
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe("https://synthetic.invalid/api/kpi/values");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({ metric_id: 11, as_of_date: "2026-06-30", target_value: "100", actual_value: "0", progress_pct: "0" });
  });

  it("serializes preserved definition types through the real client's PUT contract", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response("{}", { status: 200 }));
    client.updateKpiMetric.mockImplementationOnce(createRealKpiClient({ fetchImpl, baseUrl: "https://synthetic.invalid" }).updateKpiMetric);
    render(<MetricManageModal open mode="edit" metric={metric} owner={owner} onClose={vi.fn()} onSuccess={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }));
    await waitFor(() => expect(fetchImpl).toHaveBeenCalledTimes(1));
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe("https://synthetic.invalid/api/kpi/metrics/11");
    expect(init?.method).toBe("PUT");
    expect(JSON.parse(String(init?.body))).toMatchObject({ owner_id: 1, data_source_type: "AUTO", scoring_rule_type: "LINEAR_RATIO", score_weight: "0" });
  });

  it("keeps a daily existing value id and blocks repeated in-flight saves", async () => {
    const pending = deferred<undefined>();
    client.updateKpiValue.mockReturnValueOnce(pending.promise);
    const onSaveSuccess = vi.fn();
    render(<MetricEditModal open metric={{ ...metric, value_id: 501 }} asOfDate="2026-06-30" onClose={vi.fn()} onSaveSuccess={onSaveSuccess} />);
    const save = screen.getByRole("button", { name: /保\s*存/ });
    fireEvent.click(save);
    fireEvent.click(save);
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
    expect(client.updateKpiValue.mock.calls[0].slice(0, 3)).toEqual([501, 11, "2026-06-30"]);
    await act(async () => { pending.resolve(undefined); });
    expect(onSaveSuccess).toHaveBeenCalledTimes(1);
  });

  it("cannot save an undated summary value through the full form", () => {
    render(<MetricEditModal open metric={{ ...metric, as_of_date: undefined }} onClose={vi.fn()} onSaveSuccess={vi.fn()} />);
    expect(screen.getByRole("button", { name: /保\s*存/ })).toBeDisabled();
    expect(screen.getByText("未确定，请切换到日视图选择日期")).toBeInTheDocument();
    expect(client.updateKpiValue).not.toHaveBeenCalled();
  });

  it("resets inline edits on a date switch and ignores a late save/refresh", async () => {
    const pending = deferred<undefined>();
    client.updateKpiValue.mockReturnValueOnce(pending.promise);
    const props = { metrics: [{ ...metric, as_of_date: undefined }], valueAsOfDate: "2026-06-30", onRefresh: vi.fn() };
    const view = render(<MetricTable {...props} />);
    fireEvent.click(screen.getByText("100.00"));
    expect(screen.getByText("2026-06-30")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "0" } });
    const input = screen.getByRole("textbox");
    fireEvent.keyDown(input, { key: "Enter", code: "Enter", charCode: 13 });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter", charCode: 13 });
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
    expect(client.updateKpiValue).toHaveBeenCalledWith(0, 11, "2026-06-30", { target_value: "0" });
    view.rerender(<MetricTable {...props} valueAsOfDate="2026-07-31" />);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    await act(async () => { pending.resolve(undefined); });
    expect(props.onRefresh).not.toHaveBeenCalled();
  });

  it("ignores an old form save after close/reopen on a different object", async () => {
    const pending = deferred<undefined>();
    client.updateKpiValue.mockReturnValueOnce(pending.promise);
    const onSaveSuccess = vi.fn();
    const props = { open: true, metric, asOfDate: "2026-06-30", onClose: vi.fn(), onSaveSuccess };
    const view = render(<MetricEditModal {...props} />);
    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }));
    view.rerender(<MetricEditModal {...props} open={false} />);
    view.rerender(<MetricEditModal {...props} metric={{ ...metric, metric_id: 22, metric_name: "Synthetic B" }} />);
    await act(async () => { pending.resolve(undefined); });
    expect(onSaveSuccess).not.toHaveBeenCalled();
  });

  function parseBatch() {
    fireEvent.change(screen.getByPlaceholderText("从 Excel 粘贴…"), { target: { value: "M1\t0\t0" } });
    fireEvent.click(screen.getByRole("button", { name: /解\s*析/ }));
  }

  it.each(["owner", "date", "year", "reopen"])("invalidates parsed batch rows after a %s switch", (change) => {
    const props = { open: true, owner, asOfDate: "2026-06-30", metrics: [metric], onClose: vi.fn(), onSuccess: vi.fn() };
    const view = render(<BatchPasteModal {...props} />);
    parseBatch();
    expect(screen.getByRole("button", { name: /导入（1 条）/ })).toBeEnabled();
    if (change === "reopen") view.rerender(<BatchPasteModal {...props} open={false} />);
    view.rerender(<BatchPasteModal {...props}
      owner={change === "owner" ? { ...owner, owner_id: 2, owner_name: "Synthetic B" } : change === "year" ? { ...owner, year: 2027 } : owner}
      asOfDate={change === "date" ? "2026-07-31" : props.asOfDate}
      metrics={change === "owner" ? [{ ...metric, metric_id: 22, owner_id: 2 }] : props.metrics}
    />);
    expect(screen.getByRole("button", { name: /导入（0 条）/ })).toBeDisabled();
    expect(screen.getByPlaceholderText("从 Excel 粘贴…")).toHaveValue("");
    expect(client.batchUpdateKpiValues).not.toHaveBeenCalled();
  });

  it("does not accept rows from an old owner while new metrics are loading", () => {
    render(<BatchPasteModal open owner={{ ...owner, owner_id: 2 }} asOfDate="2026-07-31" metrics={[metric]} onClose={vi.fn()} onSuccess={vi.fn()} />);
    parseBatch();
    expect(screen.getByRole("button", { name: /导入（0 条）/ })).toBeDisabled();
  });

  it("requires reparse when pasted text changes after preview", () => {
    render(<BatchPasteModal open owner={owner} asOfDate="2026-06-30" metrics={[metric]} onClose={vi.fn()} onSuccess={vi.fn()} />);
    parseBatch();
    fireEvent.change(screen.getByPlaceholderText("从 Excel 粘贴…"), { target: { value: "M1\t80" } });
    expect(screen.getByRole("button", { name: /导入（0 条）/ })).toBeDisabled();
  });

  it("invalidates preview when the owner metric list is replaced", () => {
    const props = { open: true, owner, asOfDate: "2026-06-30", metrics: [metric], onClose: vi.fn(), onSuccess: vi.fn() };
    const view = render(<BatchPasteModal {...props} />);
    parseBatch();
    view.rerender(<BatchPasteModal {...props} metrics={[{ ...metric, metric_id: 12 }]} />);
    expect(screen.getByRole("button", { name: /导入（0 条）/ })).toBeDisabled();
    expect(screen.getByPlaceholderText("从 Excel 粘贴…")).toHaveValue("M1\t0\t0");
  });

  it("a metrics refresh cannot unlock an active batch request or erase its text", async () => {
    const pending = deferred<{ success_count: number; failed_count: number; errors: string[] }>();
    client.batchUpdateKpiValues.mockReturnValueOnce(pending.promise);
    const props = { open: true, owner, asOfDate: "2026-06-30", metrics: [metric], onClose: vi.fn(), onSuccess: vi.fn() };
    const view = render(<BatchPasteModal {...props} />);
    parseBatch();
    fireEvent.click(screen.getByRole("button", { name: /导入（1 条）/ }));
    view.rerender(<BatchPasteModal {...props} metrics={[{ ...metric, metric_id: 12 }]} />);
    expect(screen.getByPlaceholderText("从 Excel 粘贴…")).toHaveValue("M1\t0\t0");
    expect(screen.getByPlaceholderText("从 Excel 粘贴…")).toBeDisabled();
    expect(screen.getByRole("button", { name: /解\s*析/ })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Close" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /导入（0 条）/ }));
    expect(client.batchUpdateKpiValues).toHaveBeenCalledTimes(1);
    await act(async () => { pending.resolve({ success_count: 1, failed_count: 0, errors: [] }); });
    await waitFor(() => expect(props.onSuccess).toHaveBeenCalledTimes(1));
  });

  it("cancels the success timer on close/reopen and prevents duplicate imports after success", async () => {
    client.batchUpdateKpiValues.mockResolvedValueOnce({ success_count: 1, failed_count: 0, errors: [] });
    const props = { open: true, owner, asOfDate: "2026-06-30", metrics: [metric], onClose: vi.fn(), onSuccess: vi.fn() };
    const view = render(<BatchPasteModal {...props} />);
    parseBatch();
    fireEvent.click(screen.getByRole("button", { name: /导入（1 条）/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: /导入（0 条）/ })).toBeDisabled());
    expect(screen.getByPlaceholderText("从 Excel 粘贴…")).toBeDisabled();
    view.rerender(<BatchPasteModal {...props} open={false} />);
    view.rerender(<BatchPasteModal {...props} />);
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 1300)); });
    expect(props.onSuccess).not.toHaveBeenCalled();
    expect(client.batchUpdateKpiValues).toHaveBeenCalledTimes(1);
  });

  it("imports zero once and ignores a delayed result after context changes", async () => {
    const pending = deferred<{ success_count: number; failed_count: number; errors: string[] }>();
    client.batchUpdateKpiValues.mockReturnValueOnce(pending.promise);
    const onSuccess = vi.fn();
    const props = { open: true, owner, asOfDate: "2026-06-30", metrics: [metric], onClose: vi.fn(), onSuccess };
    const view = render(<BatchPasteModal {...props} />);
    parseBatch();
    const submit = screen.getByRole("button", { name: /导入（1 条）/ });
    fireEvent.click(submit);
    fireEvent.click(submit);
    expect(client.batchUpdateKpiValues).toHaveBeenCalledTimes(1);
    expect(client.batchUpdateKpiValues).toHaveBeenCalledWith("2026-06-30", [{ metric_id: 11, actual_value: "0", progress_pct: "0" }]);
    view.rerender(<BatchPasteModal {...props} asOfDate="2026-07-31" />);
    await act(async () => { pending.resolve({ success_count: 1, failed_count: 0, errors: [] }); });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 1300)); });
    expect(onSuccess).not.toHaveBeenCalled();
  });
});

describe("KPI pending mutation lifecycle", () => {
  it.each([false, true])("a forced value reopen (different record=%s) preserves the new draft", async (differentRecord) => {
    const pending = deferred<undefined>();
    client.updateKpiValue.mockReturnValueOnce(pending.promise);
    const props = { open: true, metric, asOfDate: "2026-06-30", onClose: vi.fn(), onSaveSuccess: vi.fn() };
    const view = render(<MetricEditModal {...props} />);
    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }));
    view.rerender(<MetricEditModal {...props} open={false} />);
    view.rerender(<MetricEditModal {...props} metric={differentRecord ? { ...metric, metric_id: 22 } : metric} />);
    fireEvent.change(screen.getAllByRole("textbox")[1], { target: { value: "73" } });
    await act(async () => { pending.resolve(undefined); });
    expect(props.onSaveSuccess).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getAllByRole("textbox")[1]).toHaveValue("73");
  });

  it.each([false, true])("a forced definition reopen (different record=%s) preserves the new draft", async (differentRecord) => {
    const pending = deferred<undefined>();
    client.updateKpiMetric.mockReturnValueOnce(pending.promise);
    const props = { open: true, mode: "edit" as const, metric, owner, onClose: vi.fn(), onSuccess: vi.fn() };
    const view = render(<MetricManageModal {...props} />);
    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }));
    view.rerender(<MetricManageModal {...props} open={false} />);
    view.rerender(<MetricManageModal {...props} metric={differentRecord ? { ...metric, metric_id: 22 } : metric} />);
    fireEvent.change(screen.getAllByRole("textbox")[1], { target: { value: "Keep new definition" } });
    await act(async () => { pending.resolve(undefined); });
    expect(props.onSuccess).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getAllByRole("textbox")[1]).toHaveValue("Keep new definition");
  });

  it.each([false, true])("a forced batch reopen (different record=%s) preserves the new draft", async (differentRecord) => {
    const pending = deferred<{ success_count: number; failed_count: number; errors: string[] }>();
    client.batchUpdateKpiValues.mockReturnValueOnce(pending.promise);
    const props = { open: true, owner, asOfDate: "2026-06-30", metrics: [metric], onClose: vi.fn(), onSuccess: vi.fn() };
    const view = render(<BatchPasteModal {...props} />);
    fireEvent.change(screen.getByPlaceholderText("从 Excel 粘贴…"), { target: { value: "M1\t0\t0" } });
    fireEvent.click(screen.getByRole("button", { name: /解\s*析/ }));
    fireEvent.click(screen.getByRole("button", { name: /导入（1 条）/ }));
    view.rerender(<BatchPasteModal {...props} open={false} />);
    view.rerender(<BatchPasteModal {...props} metrics={differentRecord ? [{ ...metric, metric_id: 22 }] : props.metrics} />);
    fireEvent.change(screen.getByPlaceholderText("从 Excel 粘贴…"), { target: { value: "M1\t73" } });
    await act(async () => { pending.resolve({ success_count: 1, failed_count: 0, errors: [] }); });
    expect(props.onSuccess).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("从 Excel 粘贴…")).toHaveValue("M1\t73");
  });

  it.each(["value", "definition", "batch"])("a pending %s completion after unmount does not call its old page", async (kind) => {
    const pending = deferred<{ success_count: number; failed_count: number; errors: string[] }>();
    const onSuccess = vi.fn();
    client.updateKpiValue.mockReturnValueOnce(pending.promise);
    client.updateKpiMetric.mockReturnValueOnce(pending.promise);
    client.batchUpdateKpiValues.mockReturnValueOnce(pending.promise);
    const view = render(kind === "value"
      ? <MetricEditModal open metric={metric} asOfDate="2026-06-30" onClose={vi.fn()} onSaveSuccess={onSuccess} />
      : kind === "definition"
        ? <MetricManageModal open mode="edit" metric={metric} owner={owner} onClose={vi.fn()} onSuccess={onSuccess} />
        : <BatchPasteModal open owner={owner} metrics={[metric]} asOfDate="2026-06-30" onClose={vi.fn()} onSuccess={onSuccess} />);
    if (kind === "batch") {
      fireEvent.change(screen.getByPlaceholderText("从 Excel 粘贴…"), { target: { value: "M1\t0\t0" } });
      fireEvent.click(screen.getByRole("button", { name: /解\s*析/ }));
      fireEvent.click(screen.getByRole("button", { name: /导入（1 条）/ }));
    } else {
      fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }));
    }
    view.unmount();
    await act(async () => { pending.resolve({ success_count: 1, failed_count: 0, errors: [] }); });
    expect(onSuccess).not.toHaveBeenCalled();
  });
});
