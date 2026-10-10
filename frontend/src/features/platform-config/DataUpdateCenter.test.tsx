import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { DataUpdateRun, DataUpdatesClient, DataUpdatesOverview, UpdatePreflight } from "../../api/dataUpdatesClient";
import { createDataUpdatesClient } from "../../api/dataUpdatesClient";
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
    recoverPublication: vi.fn().mockResolvedValue({ ...run, run_id: "recovery-1", status: "queued", recovery_mode: "publication_only", recovery_of_run_id: run.run_id,
      message: "已受理仅恢复发布请求。" }),
    requestMarket: vi.fn().mockResolvedValue({ status: "accepted", message: "已请求启动市场更新。" }) };
}

function mount(api: DataUpdatesClient, mode: "real" | "mock" = "real") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><DataUpdateCenter mode={mode} api={api} /></QueryClientProvider>);
}

describe("DataUpdateCenter", () => {
  it("renders the API receipt's scanned, rebuilt, reused and removed scopes independently of its requested date", async () => {
    const scope = {
      scanned_report_dates: ["2025-01-31", "2026-01-31", "2026-02-28"], scanned_years: ["2025", "2026"], scanned_date_count: 3,
      rebuilt_report_dates: ["2026-01-31", "2026-02-28"], rebuilt_years: ["2026"], rebuilt_date_count: 2,
      reused_report_dates: ["2025-01-31"], reused_years: ["2025"], reused_date_count: 1,
      removed_report_dates: ["2024-12-31"], removed_years: ["2024"], removed_date_count: 1,
    };
    const payload = { ...overview, runs: [{ ...run, status: "failed", message: "后续步骤未完成。", steps: [
      { key: "product_category_pnl", label: "产品损益", status: "completed", refresh_scope: scope },
    ] }] };
    const fetchImpl = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload)));
    mount(createDataUpdatesClient({ baseUrl: "http://fixture", fetchImpl }));
    fireEvent.click(await screen.findByText("查看步骤与结果"));
    const displayed = screen.getByLabelText("产品损益实际处理范围");
    expect(displayed).toBeVisible();
    expect(displayed).toHaveTextContent("扫描来源：3 个报告日；来源年份：2025、2026");
    expect(displayed).toHaveTextContent("实际重建：2 个报告日；重建年份：2026");
    expect(displayed).toHaveTextContent("沿用结果：1 个报告日；复用年份：2025");
    expect(displayed).toHaveTextContent("移除结果：1 个报告日；完整移除年份：2024");
    expect(displayed).toHaveTextContent("2024-12-31");
    expect(displayed).toHaveTextContent("本请求的结果日期核验按所选报告日执行");
    expect(displayed).not.toHaveTextContent(reportDate);
    expect(screen.getByText(`报告日 ${reportDate}`).parentElement).toHaveTextContent("更新未完成");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("keeps legacy product-category receipts readable without inventing a zero scope", async () => {
    const api = makeApi();
    vi.mocked(api.overview).mockResolvedValue({ ...overview, runs: [{ ...run, status: "completed", steps: [
      { key: "product_category_pnl", label: "产品损益", status: "completed" },
    ] }] });
    mount(api);
    fireEvent.click(await screen.findByText("查看步骤与结果"));
    expect(screen.getByText("产品损益")).toBeVisible();
    expect(screen.queryByLabelText("产品损益实际处理范围")).not.toBeInTheDocument();
    expect(screen.queryByText(/实际重建：0/)).not.toBeInTheDocument();
  });

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

  it.each([undefined, { failed_step: "publish" }])("keeps a failed historical stock restoration out of financial retry and publication recovery (%s)", async (failureReceipt) => {
    const api = makeApi();
    vi.mocked(api.overview).mockResolvedValue({ ...overview, runs: [{ ...run,
      workflow: "choice_stock_pit_history" as DataUpdateRun["workflow"], report_date: "2026-05-28", status: "failed",
      message: "历史来源恢复未完成。", recovery_mode: failureReceipt ? "publication_only" : undefined,
      failure_receipt: failureReceipt,
      publication_recovery: { available: true, reason: null, failed_step: "publish" },
    }] });
    mount(api);
    await screen.findByText("历史来源恢复未完成。");
    expect(screen.queryByRole("button", { name: "重新提交此日期" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "仅恢复发布" })).not.toBeInTheDocument();
    expect(screen.queryByText("财务计算已完成，发布待处理")).not.toBeInTheDocument();
    expect(screen.getByText("历史股票来源恢复")).toBeInTheDocument();
    expect(screen.getByLabelText("报告日期")).toHaveValue("");
    expect(api.requestCore).not.toHaveBeenCalled();
    expect(api.recoverPublication).not.toHaveBeenCalled();
  });

  it.each([
    { core: true, market: false, canCancel: false },
    { core: false, market: true, canCancel: true },
  ])("uses market permission for cancelling historical stock restoration ($canCancel)", async ({ core, market, canCancel }) => {
    const api = makeApi();
    vi.mocked(api.overview).mockResolvedValue({ ...overview, permissions: { core, market }, runs: [{ ...run,
      workflow: "choice_stock_pit_history" as DataUpdateRun["workflow"], report_date: "2026-05-28", status: "queued",
      message: "历史来源恢复已受理。",
    }] });
    mount(api);
    await screen.findByText("历史来源恢复已受理。");
    const button = screen.queryByRole("button", { name: "取消等待" });
    expect(Boolean(button)).toBe(canCancel);
    if (button) {
      fireEvent.click(button);
      await waitFor(() => expect(vi.mocked(api.cancel).mock.calls[0]?.[0]).toBe(run.run_id));
    }
    expect(api.requestCore).not.toHaveBeenCalled();
  });

  it("shows historical restoration completion without advancing financial result dates", async () => {
    const api = makeApi();
    vi.mocked(api.overview).mockResolvedValue({ ...overview, runs: [{ ...run,
      workflow: "choice_stock_pit_history" as DataUpdateRun["workflow"], report_date: "2026-05-28", status: "completed",
      message: "历史来源恢复已核验。",
    }] });
    mount(api);
    await screen.findByText("历史来源恢复已核验。");
    expect(screen.getByRole("region", { name: "更新记录" })).toHaveTextContent("历史股票来源恢复");
    expect(screen.getByLabelText("各模块实际数据日期")).toHaveTextContent("2026-07-31");
    expect(screen.getByLabelText("各模块实际数据日期")).not.toHaveTextContent("2026-05-28");
  });

  it("recovers only publication, refreshes the overview and displays the new receipt", async () => {
    const api = makeApi();
    const failedRun = { ...run, status: "failed" as const, failure_receipt: { failed_step: "publish" },
      publication_recovery: { available: true, reason: null, failed_step: "publish" } };
    const recovery = { ...run, run_id: "recovery-1", status: "queued" as const, recovery_mode: "publication_only" as const,
      recovery_of_run_id: run.run_id, message: "已受理仅恢复发布请求。" };
    vi.mocked(api.overview).mockResolvedValueOnce({ ...overview, runs: [failedRun] })
      .mockResolvedValue({ ...overview, runs: [recovery, failedRun] });
    mount(api);
    fireEvent.click(await screen.findByRole("button", { name: "仅恢复发布" }));
    await screen.findByText(/恢复请求编号：/);
    expect(api.recoverPublication).toHaveBeenCalledWith(run.run_id, expect.any(String));
    expect(api.requestCore).not.toHaveBeenCalled();
    expect(api.overview).toHaveBeenCalledTimes(2);
    expect(await screen.findByText(/原请求编号：/)).toHaveTextContent(run.run_id);
    expect(screen.getByText("仅恢复发布，保留已完成财务计算。")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "仅恢复发布" })).not.toBeInTheDocument();
  });

  it.each([
    { core: false, available: true },
    { core: true, available: false },
    { core: true, available: undefined },
    { core: true, available: "true" },
  ])("requires explicit backend eligibility and scope permission for recovery ($core/$available)", async ({ core, available }) => {
    const api = makeApi();
    const failedRun = { ...run, status: "failed" as const, failure_receipt: { failed_step: "publish" },
      publication_recovery: { available, reason: "完成回执不完整，不能恢复发布。", failed_step: "publish" } };
    vi.mocked(api.overview).mockResolvedValue({ ...overview, permissions: { core, balance: true, market: false }, runs: [failedRun] } as DataUpdatesOverview);
    mount(api);
    await screen.findByText("财务计算已完成，发布待处理");
    expect(screen.queryByRole("button", { name: "仅恢复发布" })).not.toBeInTheDocument();
    expect(api.recoverPublication).not.toHaveBeenCalled();
  });

  it("blocks duplicate recovery clicks and keeps its key when an uncertain request is retried", async () => {
    const api = makeApi();
    vi.mocked(api.overview).mockResolvedValue({ ...overview, runs: [{ ...run, status: "failed",
      failure_receipt: { failed_step: "publish" }, publication_recovery: { available: true, reason: null, failed_step: "publish" } }] });
    let rejectRequest!: (reason: Error) => void;
    vi.mocked(api.recoverPublication).mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectRequest = reject; }))
      .mockRejectedValue(new Error("来源版本已变化，不能恢复发布。"));
    mount(api);
    const button = await screen.findByRole("button", { name: "仅恢复发布" });
    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(() => expect(api.recoverPublication).toHaveBeenCalledTimes(1));
    expect(button).toBeDisabled();
    rejectRequest(new Error("连接中断，请刷新回执后重试。"));
    await screen.findByText("连接中断，请刷新回执后重试。");
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);
    await screen.findByText("来源版本已变化，不能恢复发布。");
    expect(vi.mocked(api.recoverPublication).mock.calls[1]).toEqual(vi.mocked(api.recoverPublication).mock.calls[0]);
    expect(api.requestCore).not.toHaveBeenCalled();
  });

  it("keeps a failed recovery out of the financial resubmission shortcut and targets its original receipt", async () => {
    const api = makeApi();
    vi.mocked(api.overview).mockResolvedValue({ ...overview, runs: [{ ...run, run_id: "recovery-failed", status: "failed",
      recovery_mode: "publication_only", recovery_of_run_id: "original-run", message: "恢复发布失败。",
      publication_recovery: { available: true, reason: null, failed_step: "publish" } }] });
    mount(api);
    fireEvent.click(await screen.findByRole("button", { name: "仅恢复发布" }));
    await waitFor(() => expect(api.recoverPublication).toHaveBeenCalledWith("original-run", expect.any(String)));
    expect(screen.queryByRole("button", { name: "重新提交此日期" })).not.toBeInTheDocument();
    expect(api.requestCore).not.toHaveBeenCalled();
  });

  it("shows an ineligible receipt reason without offering a financial retry", async () => {
    const api = makeApi();
    vi.mocked(api.overview).mockResolvedValue({ ...overview, runs: [{ ...run, status: "failed",
      failure_receipt: { failed_step: "source_preview", business_body_status: "completed" },
      publication_recovery: { available: false, reason: "该失败阶段缺少可复用发布回执，请联系运维。", failed_step: "source_preview" } }] });
    mount(api);
    expect(await screen.findByText("该失败阶段缺少可复用发布回执，请联系运维。")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "仅恢复发布" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重新提交此日期" })).not.toBeInTheDocument();
  });

  it("shows verified completion and actual dates only after refreshing the recovery receipt", async () => {
    const api = makeApi();
    const recovery = { ...run, run_id: "recovery-1", status: "queued" as const, recovery_mode: "publication_only" as const,
      recovery_of_run_id: "original-run", message: "仅恢复发布已受理。" };
    vi.mocked(api.overview).mockResolvedValueOnce({ ...overview, runs: [recovery] })
      .mockResolvedValue({ ...overview, financial_dates: [{ key: "pnl", label: "正式损益", as_of_date: reportDate, status: "available" }],
        runs: [{ ...recovery, status: "completed", message: "只读结果已发布并核验。", steps: [{ key: "publish", label: "只读结果发布", status: "completed" }] }] });
    mount(api);
    await screen.findByText("仅恢复发布已受理。");
    expect(screen.getByLabelText("各模块实际数据日期")).toHaveTextContent("2026-07-31");
    expect(screen.queryByText("更新已核验")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "刷新状态" }));
    await screen.findByText("只读结果已发布并核验。");
    expect(screen.getAllByText("更新已核验")).toHaveLength(2);
    expect(screen.getByLabelText("各模块实际数据日期")).toHaveTextContent(reportDate);
    expect(screen.getByText(/原请求编号：/)).toHaveTextContent("original-run");
    expect(api.requestCore).not.toHaveBeenCalled();
    expect(api.recoverPublication).not.toHaveBeenCalled();
  });
});
