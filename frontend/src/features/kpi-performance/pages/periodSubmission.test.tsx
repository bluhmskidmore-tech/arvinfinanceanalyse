import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { KpiMetricWithValue, KpiOwner } from "../../../api/contracts";
import KpiPerformancePage from "./KpiPerformancePage";

const client = vi.hoisted(() => ({
  getKpiOwners: vi.fn(), getKpiValues: vi.fn(), getKpiValuesSummary: vi.fn(),
  getKpiMetricById: vi.fn(), updateKpiMetric: vi.fn(), updateKpiValue: vi.fn(),
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
  actual_value: "50", progress_pct: "0", as_of_date: "2026-06-30", remarks: "Keep full definition",
};

function summary(dataDate: string | null = "2026-06-30") {
  return {
    owner_id: 1, year: 2026, period_type: "MONTH", period_value: 6, period_label: "Synthetic June",
    period_start_date: "2026-06-01", period_end_date: "2026-06-30", total_weight: "10", total_score: "5",
    metrics: [{ ...metric, period_actual_value: "50", period_progress_pct: "0", period_score_value: "5", data_date: dataDate }],
  };
}

beforeEach(() => {
  vi.resetAllMocks();
  client.getKpiOwners.mockResolvedValue({ owners: [owner, { ...owner, owner_id: 2, owner_name: "Synthetic B" }], total: 2 });
  client.getKpiValues.mockResolvedValue({ metrics: [metric] });
  client.getKpiValuesSummary.mockResolvedValue(summary());
  client.getKpiMetricById.mockResolvedValue(metric);
});

async function openSummary() {
  render(<KpiPerformancePage />);
  fireEvent.click(await screen.findByRole("button", { name: /Synthetic A/ }));
  await screen.findByText("Synthetic metric");
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "KPI period type" }));
  fireEvent.click(screen.getByText("月度"));
  await screen.findByText("Synthetic June");
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "KPI month" }));
  fireEvent.click(screen.getAllByText("6月").at(-1)!);
  await waitFor(() => expect(client.getKpiValuesSummary).toHaveBeenLastCalledWith(expect.objectContaining({ period_value: 6 })));
  await screen.findByText("Synthetic June");
}

describe("KPI period write context", () => {
  it("fetches the real definition before editing a summary row", async () => {
    await openSummary();
    fireEvent.click(screen.getByRole("button", { name: "设置指标" }));
    await screen.findByRole("dialog");
    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }));
    await waitFor(() => expect(client.updateKpiMetric).toHaveBeenCalledWith(11, expect.objectContaining({
      data_source_type: "AUTO", scoring_rule_type: "LINEAR_RATIO", remarks: "Keep full definition",
    })));
    expect(client.getKpiMetricById).toHaveBeenCalledWith(11);
  });

  it("targets the same historical date in full and inline editing", async () => {
    await openSummary();
    fireEvent.click(screen.getByText("Synthetic metric"));
    fireEvent.click(screen.getByRole("button", { name: "表单编辑完成情况" }));
    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }));
    await waitFor(() => expect(client.updateKpiValue).toHaveBeenCalledWith(0, 11, "2026-06-30", expect.any(Object)));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    fireEvent.click(screen.getByText("50.00"));
    fireEvent.click(screen.getByRole("button", { name: "保存编辑" }));
    await waitFor(() => expect(client.updateKpiValue).toHaveBeenCalledTimes(2));
    expect(client.updateKpiValue.mock.calls[1].slice(0, 3)).toEqual([0, 11, "2026-06-30"]);
  });

  it("does not offer undated summary writes or hidden daily batch/recalc writes", async () => {
    client.getKpiValuesSummary.mockResolvedValue(summary(null));
    await openSummary();
    fireEvent.click(screen.getByText("Synthetic metric"));
    const fullEdit = screen.queryByRole("button", { name: "表单编辑完成情况" });
    expect(fullEdit === null || fullEdit.hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: /批量导入/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    fireEvent.click(screen.getByText("50.00"));
    expect(screen.queryByRole("button", { name: "保存编辑" })).not.toBeInTheDocument();
    expect(client.updateKpiValue).not.toHaveBeenCalled();
  });

  it("ignores a delayed definition response after switching owners", async () => {
    let resolve!: (value: KpiMetricWithValue) => void;
    client.getKpiMetricById.mockReturnValue(new Promise<KpiMetricWithValue>((done) => { resolve = done; }));
    await openSummary();
    fireEvent.click(screen.getByRole("button", { name: "设置指标" }));
    fireEvent.click(screen.getByRole("button", { name: /Synthetic B/ }));
    if (resolve) await act(async () => { resolve(metric); });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(client.updateKpiMetric).not.toHaveBeenCalled();
  });

  it("does not open a definition editor when the authoritative read fails", async () => {
    client.getKpiMetricById.mockRejectedValueOnce(new Error("Synthetic definition unavailable"));
    await openSummary();
    fireEvent.click(screen.getByRole("button", { name: "设置指标" }));
    await screen.findByText("Synthetic definition unavailable");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(client.updateKpiMetric).not.toHaveBeenCalled();
  });

  it.each([
    { metric_id: 12 }, { owner_id: 2 }, { year: 2027 },
  ])("rejects an authoritative definition with mismatched scope %j", async (mismatch) => {
    client.getKpiMetricById.mockResolvedValueOnce({ ...metric, ...mismatch });
    await openSummary();
    fireEvent.click(screen.getByRole("button", { name: "设置指标" }));
    await screen.findByText("指标与当前考核对象不一致");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(client.updateKpiMetric).not.toHaveBeenCalled();
  });

  it("hides old rows and batch actions while the next owner's values are pending", async () => {
    render(<KpiPerformancePage />);
    fireEvent.click(await screen.findByRole("button", { name: /Synthetic A/ }));
    await screen.findByText("Synthetic metric");
    client.getKpiValues.mockReturnValueOnce(new Promise(() => undefined));
    fireEvent.click(screen.getByRole("button", { name: /Synthetic B/ }));
    expect(screen.queryByText("Synthetic metric")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "设置指标" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /批量导入/ })).toBeDisabled();
  });

  it("does not refresh a new owner after an old historical form save completes", async () => {
    let resolve!: () => void;
    client.updateKpiValue.mockReturnValueOnce(new Promise<void>((done) => { resolve = done; }));
    await openSummary();
    fireEvent.click(screen.getByText("Synthetic metric"));
    fireEvent.click(screen.getByRole("button", { name: "表单编辑完成情况" }));
    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }));
    const previousReads = client.getKpiValuesSummary.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /Synthetic B/ }));
    await waitFor(() => expect(client.getKpiValuesSummary).toHaveBeenCalledTimes(previousReads + 1));
    await act(async () => { resolve(); });
    expect(client.getKpiValuesSummary).toHaveBeenCalledTimes(previousReads + 1);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
