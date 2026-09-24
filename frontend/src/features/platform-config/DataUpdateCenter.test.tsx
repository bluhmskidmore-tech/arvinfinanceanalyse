import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { DataUpdateRun, DataUpdatesClient, DataUpdatesOverview, UpdatePreflight } from "../../api/dataUpdatesClient";
import DataUpdateCenter from "./DataUpdateCenter";
import { buildDataUpdateCenterModel } from "./dataUpdateCenterModel";

const reportDate = "2026-08-31";
const preflight: UpdatePreflight = { report_date: reportDate, workflow: "core_financial", ready: false, input_directory: "F:/fixtures/input",
  checks: [{ key: "pnl", label: "固收损益文件", status: "waiting", files: [], detail: "尚未找到该报告日的文件。" }] };
const overview: DataUpdatesOverview = {
  checked_at: "2026-09-06T08:00:00Z", input_directory: "F:/fixtures/input", permissions: { core: true, market: true },
  schedule: { status: "available", detail: "执行结果与数据日期分别核验。", tasks: [
    { task_name: "MOSS-DataUpdateQueue", label: "财务更新与文件检查", status: "ready",
      last_run_time: "2026-09-06 16:00", next_run_time: "2026-09-06 16:05", last_result: "0" },
    { task_name: "MOSS-DailyDataRefresh", label: "每日市场数据", status: "ready",
      last_run_time: "2026-09-05 18:45", next_run_time: "2026-09-06 18:45", last_result: "0" },
  ] },
  financial_dates: [{ key: "pnl", label: "正式损益", as_of_date: "2026-07-31", status: "available" }],
  runs: [], steps: [{ key: "verify", label: "结果日期核验" }],
};
const run: DataUpdateRun = { run_id: "receipt-1", report_date: reportDate, status: "waiting_inputs", attempt: 0,
  submitted_at: "2026-09-06T08:00:00Z", updated_at: "2026-09-06T08:00:00Z", steps: [], message: "已受理，等待文件到齐。" };

function makeApi(): DataUpdatesClient {
  return { overview: vi.fn().mockResolvedValue(structuredClone(overview)), preflight: vi.fn().mockResolvedValue(preflight),
    requestCore: vi.fn().mockResolvedValue(run), cancel: vi.fn().mockResolvedValue({ ...run, status: "cancelled" }),
    requestMarket: vi.fn().mockResolvedValue({ status: "accepted", message: "已请求启动市场更新。" }) };
}

function mount(api: DataUpdatesClient, mode: "real" | "mock" = "real") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><DataUpdateCenter mode={mode} api={api} /></QueryClientProvider>);
}

describe("DataUpdateCenter", () => {
  it("allows waiting for missing files without allowing an immediate update", async () => {
    const api = makeApi();
    mount(api);
    fireEvent.change(await screen.findByLabelText("报告日期"), { target: { value: reportDate } });
    await screen.findByText("尚未找到该报告日的文件。");
    expect(screen.getByRole("button", { name: "立即更新" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "资料齐全后自动更新" }));
    await screen.findByText("已受理，等待文件到齐。");
    expect(api.requestCore).toHaveBeenCalledWith(reportDate, true, expect.any(String), "core_financial");
    expect(api.requestMarket).not.toHaveBeenCalled();
  });

  it("uses the selected date and keeps errors visible after an unsuccessful request", async () => {
    const api = makeApi();
    vi.mocked(api.preflight).mockResolvedValue({ ...preflight, ready: true });
    vi.mocked(api.requestCore).mockRejectedValue(new Error("后台任务尚未启用"));
    mount(api);
    fireEvent.change(await screen.findByLabelText("报告日期"), { target: { value: reportDate } });
    await waitFor(() => expect(screen.getByRole("button", { name: "立即更新" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "立即更新" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("后台任务尚未启用");
    expect(screen.getByLabelText("报告日期")).toHaveValue(reportDate);
    expect(api.requestCore).toHaveBeenCalledWith(reportDate, false, expect.any(String), "core_financial");
  });

  it("keeps actual data dates separate from a successful scheduler result", async () => {
    mount(makeApi());
    expect(await screen.findByLabelText("各模块实际数据日期")).toHaveTextContent("2026-07-31");
    expect(screen.getAllByText("上次执行成功")).toHaveLength(2);
    expect(screen.queryByText("全部数据已更新")).not.toBeInTheDocument();
  });

  it("opens the completed daily balance result at the request report date", async () => {
    const api = makeApi();
    vi.mocked(api.overview).mockResolvedValue({ ...overview, runs: [
      { ...run, workflow: "balance_daily", status: "completed" },
    ] });
    mount(api);
    const link = await screen.findByRole("link", { name: "查看余额结果" });
    expect(link).toHaveAttribute("href", `/balance-analysis?report_date=${reportDate}`);
  });

  it.each(["failed", "queued"] as const)("does not offer a completed balance result for a %s request", async (status) => {
    const api = makeApi();
    vi.mocked(api.overview).mockResolvedValue({ ...overview, runs: [
      { ...run, workflow: "balance_daily", status },
    ] });
    mount(api);
    await screen.findByText("已受理，等待文件到齐。");
    expect(screen.queryByRole("link", { name: "查看余额结果" })).not.toBeInTheDocument();
  });

  it("shows interrupted runs and allows selecting their date for a deliberate retry", async () => {
    const api = makeApi();
    vi.mocked(api.overview).mockResolvedValue({ ...overview, runs: [{ ...run, status: "failed", message: "上次执行中断。" }] });
    mount(api);
    await screen.findByText("上次执行中断。");
    fireEvent.click(screen.getByRole("button", { name: "重新提交此日期" }));
    expect(screen.getByLabelText("报告日期")).toHaveValue(reportDate);
    expect(api.requestCore).not.toHaveBeenCalled();
  });

  it.each([
    { failed_step: "publish" },
    { failed_step: "system_read_publish" },
    { failed_step: "source_preview", business_body_status: "completed" },
  ])("keeps completed financial work out of the retry shortcut for $failed_step", async (failureReceipt) => {
    const api = makeApi();
    const failedRun = { ...run, status: "failed" as const,
      workflow: failureReceipt.failed_step === "publish" ? "core_financial" as const : "balance_daily" as const,
      failure_receipt: failureReceipt, steps: [
      { key: "verify", label: "结果日期核验", status: "completed" },
      { key: failureReceipt.failed_step, label: "发布检查", status: "failed", error_message: "连接失败" },
    ] };
    vi.mocked(api.overview).mockResolvedValue({ ...overview, permissions: { ...overview.permissions, balance: true }, runs: [failedRun] });
    mount(api);
    expect(await screen.findByText("财务计算已完成，发布待处理")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重新提交此日期" })).not.toBeInTheDocument();
    expect(screen.getByText(/重新提交会重跑所选财务流程/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("查看失败回执与已完成步骤"));
    expect(screen.getByText("连接失败")).toBeVisible();
    expect(screen.getByLabelText("报告日期")).toHaveValue("");
    expect(api.requestCore).not.toHaveBeenCalled();
  });

  it.each([undefined, "running", "failed"])("keeps a normal source-preview failure retryable when body status is %s", async (bodyStatus) => {
    const api = makeApi();
    const failedRun = { ...run, status: "failed" as const,
      failure_receipt: { failed_step: "source_preview", business_body_status: bodyStatus },
      steps: [{ key: "source_preview", label: "来源摘要", status: "failed" }] };
    vi.mocked(api.overview).mockResolvedValue({ ...overview, runs: [failedRun] });
    mount(api);
    fireEvent.click(await screen.findByRole("button", { name: "重新提交此日期" }));
    expect(screen.queryByText("财务计算已完成，发布待处理")).not.toBeInTheDocument();
    expect(screen.getByLabelText("报告日期")).toHaveValue(reportDate);
    expect(api.requestCore).not.toHaveBeenCalled();
  });

  it("keeps publication receipts readable without granting retry permission", async () => {
    const api = makeApi();
    const failedRun = { ...run, status: "failed" as const,
      failure_receipt: { failed_step: "system_read_publish" } };
    vi.mocked(api.overview).mockResolvedValue({ ...overview,
      permissions: { core: false, balance: false, market: false }, runs: [failedRun, { ...run, run_id: "ordinary", status: "failed" }] });
    mount(api);
    expect(await screen.findByText("财务计算已完成，发布待处理")).toBeInTheDocument();
    expect(screen.getByText("查看失败回执与已完成步骤")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重新提交此日期" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "立即更新" })).toBeDisabled();
    expect(api.requestCore).not.toHaveBeenCalled();
  });

  it("does not label a completed run from its retained failure receipt", async () => {
    const api = makeApi();
    const completedRun = { ...run, status: "completed" as const,
      failure_receipt: { failed_step: "publish" } };
    vi.mocked(api.overview).mockResolvedValue({ ...overview, runs: [completedRun] });
    mount(api);
    await screen.findByText("更新已核验");
    expect(screen.queryByText("财务计算已完成，发布待处理")).not.toBeInTheDocument();
  });

  it.each([
    { workflow: "balance_daily" as const, core: true, balance: false, canRetry: false },
    { workflow: "balance_daily" as const, core: false, balance: true, canRetry: true },
    { workflow: "core_financial" as const, core: false, balance: true, canRetry: false },
  ])("keeps the $workflow retry shortcut scoped to its own permission ($canRetry)", async ({ workflow, core, balance, canRetry }) => {
    const api = makeApi();
    vi.mocked(api.overview).mockResolvedValue({ ...overview,
      permissions: { core, balance, market: false },
      runs: [{ ...run, workflow, status: "failed", message: "计算阶段失败。" }] });
    mount(api);
    await screen.findByText("计算阶段失败。");
    expect(Boolean(screen.queryByRole("button", { name: "重新提交此日期" }))).toBe(canRetry);
  });

  it("shows only valid recorded elapsed time for completed and failed steps", async () => {
    const api = makeApi();
    vi.mocked(api.overview).mockResolvedValue({ ...overview, runs: [{ ...run, status: "failed", steps: [
      { key: "balance", label: "余额与汇率", status: "completed", elapsed_seconds: 1.234 },
      { key: "verify", label: "结果日期核验", status: "failed", elapsed_seconds: 0 },
      { key: "legacy", label: "旧步骤", status: "completed" },
      { key: "negative", label: "负数步骤", status: "failed", elapsed_seconds: -1 },
      { key: "nan", label: "无效步骤", status: "completed", elapsed_seconds: Number.NaN },
    ] }] });
    mount(api);
    expect(await screen.findByText("耗时 1.234 秒")).toBeInTheDocument();
    expect(screen.getByText("耗时 0.000 秒")).toBeInTheDocument();
    expect(screen.getAllByText(/耗时/)).toHaveLength(2);
  });

  it("does not offer write controls to a read-only user", async () => {
    const api = makeApi();
    vi.mocked(api.overview).mockResolvedValue({ ...overview, permissions: { core: false, market: false } });
    mount(api);
    await screen.findByText("当前账号没有所选范围的更新权限。");
    expect(screen.getByRole("button", { name: "资料齐全后自动更新" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "更新市场数据" })).toBeDisabled();
  });

  it("never contacts operational endpoints in mock mode", () => {
    const api = makeApi();
    mount(api, "mock");
    expect(screen.getByText("数据更新仅在真实数据模式下开放")).toBeInTheDocument();
    expect(api.overview).not.toHaveBeenCalled();
  });

  it("checks the daily source bundle separately and submits the chosen scope", async () => {
    const api = makeApi();
    vi.mocked(api.overview).mockResolvedValue({ ...overview, permissions: { core: true, balance: true, market: true } });
    vi.mocked(api.preflight).mockResolvedValue({ ...preflight, ready: true, workflow: "balance_daily" });
    mount(api);
    fireEvent.change(await screen.findByLabelText("更新范围"), { target: { value: "balance_daily" } });
    fireEvent.change(screen.getByLabelText("报告日期"), { target: { value: reportDate } });
    await waitFor(() => expect(screen.getByRole("button", { name: "立即更新" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "立即更新" }));
    await waitFor(() => expect(api.requestCore).toHaveBeenCalledWith(reportDate, false, expect.any(String), "balance_daily"));
  });

  it("blocks submission when preflight returns a different workflow for the same date", async () => {
    const api = makeApi();
    vi.mocked(api.preflight).mockResolvedValue({ ...preflight, ready: true, workflow: "balance_daily" });
    mount(api);
    fireEvent.change(await screen.findByLabelText("报告日期"), { target: { value: reportDate } });
    await screen.findByText("文件检查结果与所选报告日期或更新范围不一致，请刷新重试。");
    expect(screen.getByRole("button", { name: "立即更新" })).toBeDisabled();
    expect(api.requestCore).not.toHaveBeenCalled();
  });

  it("clears the actionable failure banner after a newer successful run for the same date", () => {
    const model = buildDataUpdateCenterModel({ ...overview,
      runs: [{ ...run, run_id: "new", status: "completed" }, { ...run, status: "failed" }],
      financial_dates: [{ key: "pnl", label: "正式损益", as_of_date: null, status: "missing" }],
    });
    expect(model.surfaces).toHaveLength(0);
    expect(model.dates[0].value).toBe("—");
  });
});
