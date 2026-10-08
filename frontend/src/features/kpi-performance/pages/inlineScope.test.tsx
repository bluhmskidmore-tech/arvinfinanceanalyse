import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { KpiMetricWithValue, KpiOwner } from "../../../api/contracts";
import KpiPerformancePage from "./KpiPerformancePage";

const client = vi.hoisted(() => ({
  getKpiOwners: vi.fn(), getKpiValues: vi.fn(), updateKpiValue: vi.fn(),
  fetchAndRecalcKpi: vi.fn(),
}));
vi.mock("../../../api/client", () => ({ useApiClient: () => client }));

const owner: KpiOwner = {
  owner_id: 1, owner_name: "Synthetic A", org_unit: "Synthetic", person_name: null,
  year: 2026, scope_type: "department", scope_key: null, is_active: true,
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};
const metric: KpiMetricWithValue = {
  metric_id: 11, metric_code: "M1", metric_name: "Synthetic A metric", owner_id: 1,
  year: 2026, major_category: "规模类", target_value: "100", score_weight: "10",
  scoring_rule_type: "LINEAR_RATIO", data_source_type: "AUTO", is_active: true,
  actual_value: "2", progress_pct: "0",
};

function deferred() {
  let resolve!: () => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<void>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}

beforeEach(() => {
  vi.resetAllMocks();
  client.getKpiOwners.mockResolvedValue({ owners: [owner, { ...owner, owner_id: 2, owner_name: "Synthetic B" }] });
  client.getKpiValues.mockImplementation(async ({ owner_id, as_of_date }: { owner_id: number; as_of_date: string }) => ({
    metrics: [{ ...metric, owner_id, metric_id: owner_id === 1 ? 11 : 22,
      metric_name: owner_id === 1 ? "Synthetic A metric" : "Synthetic B metric", as_of_date }],
  }));
});

async function openOwnerA() {
  render(<KpiPerformancePage />);
  fireEvent.click(await screen.findByRole("button", { name: "Synthetic A" }));
  await screen.findByText("Synthetic A metric");
}

async function switchOwner(name: "Synthetic A" | "Synthetic B", expectedReads: number) {
  fireEvent.click(screen.getByRole("button", { name }));
  await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(expectedReads));
  await screen.findByText(`${name} metric`);
}

function saveInline(value = "9") {
  fireEvent.click(screen.getByText("100.00"));
  const save = screen.getByRole("button", { name: "保存编辑" });
  const input = within(save.parentElement!).getByRole("textbox");
  fireEvent.change(input, { target: { value } });
  fireEvent.click(save);
  return input;
}

describe("KPI inline scope-switch recovery", () => {
  it.each(["inline", "recalc"] as const)("retains every concurrent write when %s succeeds while the other response is still unknown", async (completed) => {
    const inline = deferred();
    const recalc = deferred();
    client.updateKpiValue.mockReturnValueOnce(inline.promise);
    client.fetchAndRecalcKpi.mockImplementationOnce(async () => {
      await recalc.promise;
      return { owner_id: 1, owner_name: owner.owner_name, as_of_date: "2026-10-08",
        total_metrics: 1, fetched_count: 1, scored_count: 1, failed_count: 0, skipped_count: 0, results: [] };
    });
    await openOwnerA();
    saveInline();
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: /抓取并重算/ }));
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
    expect(client.fetchAndRecalcKpi).toHaveBeenCalledTimes(1);
    await switchOwner("Synthetic B", 2);
    await act(async () => {
      if (completed === "inline") inline.resolve();
      else recalc.resolve();
    });
    await switchOwner("Synthetic A", 3);
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    fireEvent.click(await screen.findByRole("button", { name: "刷新核实" }));
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(4));
    expect(screen.queryByRole("button", { name: "已核实，继续编辑" })).not.toBeInTheDocument();
    await act(async () => {
      const error = new TypeError("Synthetic concurrent response still unknown");
      if (completed === "inline") recalc.reject(error);
      else inline.reject(error);
    });
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    expect(screen.getByText(/Synthetic concurrent response still unknown/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "已核实，继续编辑" })).not.toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "刷新核实" }));
    fireEvent.click(await screen.findByRole("button", { name: "已核实，继续编辑" }));
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeEnabled();
    expect(screen.getByText(/原写入结果仍未知/)).toBeInTheDocument();
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
    expect(client.fetchAndRecalcKpi).toHaveBeenCalledTimes(1);
  });

  it("invalidates a verification that hands off another in-flight write before its GET returns", async () => {
    const inline = deferred();
    const recalc = deferred();
    const readback = deferred();
    client.updateKpiValue.mockReturnValueOnce(inline.promise);
    client.fetchAndRecalcKpi.mockReturnValueOnce(recalc.promise);
    await openOwnerA();
    saveInline();
    fireEvent.click(screen.getByRole("button", { name: /抓取并重算/ }));
    await act(async () => { recalc.reject(new TypeError("Synthetic recalc response lost")); });
    client.getKpiValues.mockImplementationOnce(async () => {
      await readback.promise;
      return { metrics: [{ ...metric, as_of_date: "2026-10-08" }] };
    });
    fireEvent.click(await screen.findByRole("button", { name: "刷新核实" }));
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(2));
    await act(async () => { inline.reject(new TypeError("Synthetic inline response lost during verification")); });
    await act(async () => { readback.resolve(); });
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "已核实，继续编辑" })).not.toBeInTheDocument();
    expect(screen.getByText(/Synthetic inline response lost during verification/)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "刷新核实" }));
    fireEvent.click(await screen.findByRole("button", { name: "已核实，继续编辑" }));
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeEnabled();
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
    expect(client.fetchAndRecalcKpi).toHaveBeenCalledTimes(1);
  });

  it("hands off a normal pending recalc before verifying an inline rejection and refreshes its late success once", async () => {
    const inline = deferred();
    const recalc = deferred();
    client.updateKpiValue.mockReturnValueOnce(inline.promise);
    client.fetchAndRecalcKpi.mockImplementationOnce(async () => {
      await recalc.promise;
      return { owner_id: 1, owner_name: owner.owner_name, as_of_date: "2026-10-08",
        total_metrics: 1, fetched_count: 1, scored_count: 1, failed_count: 0, skipped_count: 0, results: [] };
    });
    await openOwnerA();
    saveInline();
    fireEvent.click(screen.getByRole("button", { name: /抓取并重算/ }));
    await act(async () => { inline.reject(new TypeError("Synthetic inline response lost first")); });
    fireEvent.click(await screen.findByRole("button", { name: "刷新核实" }));
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(2));
    await screen.findByRole("button", { name: "刷新核实" });
    expect(screen.queryByRole("button", { name: "已核实，继续编辑" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    await act(async () => { recalc.resolve(); });
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(3));
    await screen.findByRole("button", { name: "刷新核实" });
    expect(client.getKpiValues).toHaveBeenCalledTimes(3);
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "已核实，继续编辑" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "刷新核实" }));
    fireEvent.click(await screen.findByRole("button", { name: "已核实，继续编辑" }));
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeEnabled();
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
    expect(client.fetchAndRecalcKpi).toHaveBeenCalledTimes(1);
  });

  it("retains an unresolved inline write when returning to its owner before settlement", async () => {
    const pending = deferred();
    client.updateKpiValue.mockReturnValueOnce(pending.promise);
    await openOwnerA();
    saveInline();
    await switchOwner("Synthetic B", 2);
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeEnabled();
    await switchOwner("Synthetic A", 3);
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    fireEvent.click(screen.getByText("100.00"));
    expect(screen.queryByRole("button", { name: "保存编辑" })).not.toBeInTheDocument();
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
    await act(async () => { pending.resolve(); });
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(4));
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeEnabled();
    expect(screen.getByText("写入已返回成功结果，请核对最新数据。")).toBeInTheDocument();
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
  });

  it("retains a switched-away inline rejection until readback and explicit continuation", async () => {
    const pending = deferred();
    client.updateKpiValue.mockReturnValueOnce(pending.promise);
    await openOwnerA();
    saveInline();
    await switchOwner("Synthetic B", 2);
    await act(async () => { pending.reject(new TypeError("Synthetic inline response lost")); });
    await switchOwner("Synthetic A", 3);
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    expect(screen.getByText(/Synthetic inline response lost/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "刷新核实" }));
    fireEvent.click(await screen.findByRole("button", { name: "已核实，继续编辑" }));
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeEnabled();
    expect(screen.getByText(/原写入结果仍未知/)).toBeInTheDocument();
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
  });

  it.each(["success", "rejection"] as const)("old-owner inline %s preserves a newer owner's pending edit and does not refresh that page", async (outcome) => {
    const original = deferred();
    const newer = deferred();
    client.updateKpiValue.mockReturnValueOnce(original.promise).mockReturnValueOnce(newer.promise);
    await openOwnerA();
    saveInline();
    await switchOwner("Synthetic B", 2);
    const newerInput = saveInline("73");
    await act(async () => {
      if (outcome === "success") original.resolve();
      else original.reject(new TypeError("Synthetic original inline response lost"));
    });
    expect(newerInput).toHaveValue("73");
    expect(newerInput).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "保存编辑" }));
    expect(client.updateKpiValue).toHaveBeenCalledTimes(2);
    expect(client.getKpiValues).toHaveBeenCalledTimes(2);
    expect(screen.queryByText(/写入结果尚未确认/)).not.toBeInTheDocument();
    await act(async () => { newer.resolve(); });
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(3));
    expect(screen.queryByRole("button", { name: "保存编辑" })).not.toBeInTheDocument();
    expect(client.updateKpiValue).toHaveBeenCalledTimes(2);
    await switchOwner("Synthetic A", 4);
    if (outcome === "success") {
      expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeEnabled();
      expect(screen.getByText("写入已返回成功结果，请核对最新数据。")).toBeInTheDocument();
    } else {
      expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
      expect(screen.getByText(/Synthetic original inline response lost/)).toBeInTheDocument();
    }
  });

  it("refreshes once on ordinary inline success without handing off a completed request", async () => {
    client.updateKpiValue.mockResolvedValueOnce(undefined);
    await openOwnerA();
    saveInline();
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(2));
    await screen.findByText("Synthetic A metric");
    expect(screen.queryByRole("button", { name: "刷新核实" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "保存编辑" })).not.toBeInTheDocument();
    expect(client.updateKpiValue).toHaveBeenCalledTimes(1);
  });
});
