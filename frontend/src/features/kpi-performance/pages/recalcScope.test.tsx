import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { KpiFetchAndRecalcResponse, KpiOwner } from "../../../api/contracts";
import KpiPerformancePage from "./KpiPerformancePage";

const client = vi.hoisted(() => ({
  getKpiOwners: vi.fn(), getKpiValues: vi.fn(), fetchAndRecalcKpi: vi.fn(),
}));
vi.mock("../../../api/client", () => ({ useApiClient: () => client }));
const owner: KpiOwner = {
  owner_id: 1, owner_name: "Synthetic A", org_unit: "Synthetic", person_name: null,
  year: 2026, scope_type: "department", scope_key: null, is_active: true,
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};

const result: KpiFetchAndRecalcResponse = {
  owner_id: 1, owner_name: "Synthetic A", as_of_date: "2026-10-08",
  total_metrics: 1, fetched_count: 1, scored_count: 1, failed_count: 0, skipped_count: 0, results: [],
};

function deferred() {
  let resolve!: (value: KpiFetchAndRecalcResponse) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<KpiFetchAndRecalcResponse>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}

async function openOwnerA() {
  render(<KpiPerformancePage />);
  fireEvent.click(await screen.findByRole("button", { name: "Synthetic A" }));
  await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(1));
}

async function switchOwner(name: string, expectedReads: number) {
  fireEvent.click(screen.getByRole("button", { name }));
  await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(expectedReads));
}

function changeDate(value: string) {
  const date = screen.getByRole("textbox", { name: "KPI as-of date" });
  fireEvent.change(date, { target: { value } });
  fireEvent.keyDown(date, { key: "Enter", code: "Enter", keyCode: 13 });
}

beforeEach(() => {
  vi.resetAllMocks();
  client.getKpiOwners.mockResolvedValue({ owners: [owner, { ...owner, owner_id: 2, owner_name: "Synthetic B" }] });
  client.getKpiValues.mockResolvedValue({ metrics: [] });
});

describe("KPI recalc scope-switch recovery", () => {
  it("retains the unknown write in its original owner after a normally reachable switch", async () => {
    let reject!: (error: Error) => void;
    client.fetchAndRecalcKpi.mockReturnValueOnce(new Promise((_resolve, fail) => { reject = fail; }));
    render(<KpiPerformancePage />);
    fireEvent.click(await screen.findByRole("button", { name: "Synthetic A" }));
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("button", { name: /抓取并重算/ }));
    expect(client.fetchAndRecalcKpi).toHaveBeenCalledTimes(1);
    // No modal or mask is open: owners remain ordinary clickable page controls.
    fireEvent.click(screen.getByRole("button", { name: "Synthetic B" }));
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(2));
    await act(async () => { reject(new TypeError("Synthetic response lost after server write")); });
    fireEvent.click(screen.getByRole("button", { name: "Synthetic A" }));
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(3));
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    expect(await screen.findByRole("button", { name: "刷新核实" })).toBeEnabled();
    expect(client.fetchAndRecalcKpi).toHaveBeenCalledTimes(1);
  });

  it("blocks another original-owner write before the switched-away request settles", async () => {
    const pending = deferred();
    client.fetchAndRecalcKpi.mockReturnValueOnce(pending.promise);
    await openOwnerA();
    fireEvent.click(screen.getByRole("button", { name: /抓取并重算/ }));
    await switchOwner("Synthetic B", 2);
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeEnabled();
    await switchOwner("Synthetic A", 3);
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    expect(screen.getByText(/写入结果尚未确认/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /抓取并重算/ }));
    expect(client.fetchAndRecalcKpi).toHaveBeenCalledTimes(1);
    await act(async () => { pending.resolve(result); });
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(4));
    expect(screen.getByText("写入已返回成功结果，请核对最新数据。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeEnabled();
    expect(client.fetchAndRecalcKpi).toHaveBeenCalledTimes(1);
  });

  it.each(["success", "rejection"] as const)("old-owner %s cannot clear a newer owner's in-flight lock or refresh its page", async (outcome) => {
    const original = deferred();
    const newer = deferred();
    client.fetchAndRecalcKpi.mockReturnValueOnce(original.promise).mockReturnValueOnce(newer.promise);
    await openOwnerA();
    fireEvent.click(screen.getByRole("button", { name: /抓取并重算/ }));
    await switchOwner("Synthetic B", 2);
    fireEvent.click(screen.getByRole("button", { name: /抓取并重算/ }));
    expect(client.fetchAndRecalcKpi).toHaveBeenCalledTimes(2);
    await act(async () => {
      if (outcome === "success") original.resolve(result);
      else original.reject(new TypeError("Synthetic original response lost"));
    });
    const activeButton = screen.getByRole("button", { name: /抓取并重算/ });
    expect(activeButton).toHaveClass("ant-btn-loading");
    fireEvent.click(activeButton);
    expect(client.fetchAndRecalcKpi).toHaveBeenCalledTimes(2);
    expect(client.getKpiValues).toHaveBeenCalledTimes(2);
    expect(screen.queryByText(/写入结果尚未确认/)).not.toBeInTheDocument();
    expect(screen.queryByTestId("kpi-performance-fetch-result")).not.toBeInTheDocument();
    await act(async () => { newer.resolve({ ...result, owner_id: 2, owner_name: "Synthetic B" }); });
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(3));
    expect(screen.getByTestId("kpi-performance-fetch-result")).toHaveTextContent("共 1 个指标");
    expect(activeButton).not.toHaveClass("ant-btn-loading");
    expect(client.fetchAndRecalcKpi).toHaveBeenCalledTimes(2);
    await switchOwner("Synthetic A", 4);
    if (outcome === "success") {
      expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeEnabled();
      expect(screen.getByText("写入已返回成功结果，请核对最新数据。")).toBeInTheDocument();
    } else {
      expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
      expect(screen.getByText(/Synthetic original response lost/)).toBeInTheDocument();
    }
  });

  it("retains a date-switched pending write and requires original-context recovery after rejection", async () => {
    const pending = deferred();
    client.fetchAndRecalcKpi.mockReturnValueOnce(pending.promise);
    await openOwnerA();
    const originalDate = client.getKpiValues.mock.calls[0][0].as_of_date;
    fireEvent.click(screen.getByRole("button", { name: /抓取并重算/ }));
    changeDate("2026-07-31");
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(2));
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "刷新核实" })).toBeDisabled();
    await act(async () => { pending.reject(new TypeError("Synthetic original date response lost")); });
    changeDate(originalDate);
    await waitFor(() => expect(client.getKpiValues).toHaveBeenCalledTimes(3));
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeDisabled();
    fireEvent.click(await screen.findByRole("button", { name: "刷新核实" }));
    fireEvent.click(await screen.findByRole("button", { name: "已核实，继续编辑" }));
    expect(screen.getByRole("button", { name: /抓取并重算/ })).toBeEnabled();
    expect(screen.getByText(/原写入结果仍未知/)).toBeInTheDocument();
    expect(client.fetchAndRecalcKpi).toHaveBeenCalledTimes(1);
  });

  it("refreshes once on ordinary recalc success without handing off an unknown write", async () => {
    client.fetchAndRecalcKpi.mockResolvedValueOnce(result);
    await openOwnerA();
    fireEvent.click(screen.getByRole("button", { name: /抓取并重算/ }));
    await screen.findByText("抓取并重算已完成");
    expect(client.getKpiValues).toHaveBeenCalledTimes(2);
    expect(client.fetchAndRecalcKpi).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "刷新核实" })).not.toBeInTheDocument();
  });
});
