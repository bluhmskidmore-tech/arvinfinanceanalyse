import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import type { ApiEnvelope, BalanceMovementPayload } from "../../../api/contracts";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ApiClientProvider, createApiClient } from "../../../api/client";
import { renderWorkbenchApp } from "../../../test/renderWorkbenchApp";
import { downloadCsv } from "../lib/balanceMovementCsv";
import BalanceMovementAnalysisPage from "./BalanceMovementAnalysisPage";

vi.mock("../../../lib/echarts", () => ({ default: () => <div data-testid="chart-stub" /> }));
vi.mock("../lib/balanceMovementCsv", async (importOriginal) => ({ ...await importOriginal<typeof import("../lib/balanceMovementCsv")>(), downloadCsv: vi.fn() }));

it("reviews the synthetic 200 to 210 three-bucket movement, follows sources and exports the same selection without writing", async () => {
  const client = createApiClient({ mode: "mock" });
  const detail = await client.getBalanceMovementAnalysis({ reportDate: "2026-06-30" });
  const before = [100, 80, 20];
  const after = [120, 70, 20];
  detail.result.rows = detail.result.rows.map((row, i) => ({ ...row,
    report_date: "2026-06-30", report_month: "2026-06", currency_basis: "CNX",
    previous_balance: String(before[i] * 1e8), current_balance: String(after[i] * 1e8),
    balance_change: String((after[i] - before[i]) * 1e8),
    current_balance_pct: String(after[i] / 210 * 100), contribution_pct: String(Math.abs(after[i] - before[i]) / 30 * 100),
    reconciliation_status: "matched", chain_status: "continuous", position_source_basis: "CNX",
    zqtz_amount: String(after[i] * 1e8), gl_amount: String(after[i] * 1e8), reconciliation_diff: "0",
  }));
  detail.result.summary = { previous_balance_total: "20000000000", current_balance_total: "21000000000", balance_change_total: "1000000000", zqtz_amount_total: "21000000000", reconciliation_diff_total: "0", matched_bucket_count: 3, bucket_count: 3 };
  detail.result.zqtz_maturity_structure = { meta: { ...detail.result.basis_movement_decomposition!.meta, report_date: "2026-06-30", zqtz_currency_basis: "CNY" }, buckets: [] };
  detail.result.accounting_controls = ["141", "142", "143", "1440101"];
  detail.result.excluded_controls = ["144020"];
  detail.result.trend_months = [];
  detail.result.business_trend_months = [];
  detail.result_meta.resolved_report_date = "2026-06-30";
  vi.spyOn(client, "getBalanceMovementDates").mockResolvedValue({ result: { report_dates: ["2026-06-30"], currency_basis: "CNX" }, result_meta: detail.result_meta });
  vi.spyOn(client, "getBalanceMovementAnalysis").mockResolvedValue(detail);
  const refresh = vi.spyOn(client, "refreshBalanceMovementAnalysis");
  renderWorkbenchApp(["/balance-movement-analysis?report_date=2026-06-30&currency_basis=CNX"], { client, routes: [{ path: "/balance-movement-analysis", element: <BalanceMovementAnalysisPage /> }] });
  const core = await screen.findByTestId("balance-movement-analysis-accounting-buckets");
  const rows = within(core).getAllByRole("row");
  expect(rows).toHaveLength(4);
  expect(rows[1]).toHaveTextContent("100.00");
  expect(rows[1]).toHaveTextContent("120.00");
  expect(rows[1]).toHaveTextContent("66.67%");
  expect(rows[2]).toHaveTextContent("33.33%");
  expect(rows[3]).toHaveTextContent("0.00%");
  fireEvent.change(screen.getByLabelText("余额变动分析-分类桶"), { target: { value: "OCI" } });
  fireEvent.click(screen.getByRole("button", { name: "查看分类桶来源" }));
  const evidence = await screen.findByTestId("balance-movement-bucket-evidence");
  expect(evidence).toHaveTextContent("OCI 来源复核");
  expect(evidence).toHaveTextContent("独立头寸主链实际来源CNX");
  expect(evidence).toHaveTextContent("明细头寸币种口径CNY");
  expect(evidence).toHaveTextContent("141、142、143、1440101");
  fireEvent.click(within(evidence).getByRole("button", { name: "返回核心对账" }));
  expect(screen.getByLabelText("余额变动分析-分类桶")).toHaveValue("OCI");
  expect(screen.getByLabelText("余额变动分析-报告日期")).toHaveValue("2026-06-30");
  expect(screen.queryByTestId("balance-movement-bucket-evidence")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("balance-movement-analysis-export-csv"));
  expect(downloadCsv).toHaveBeenCalledOnce();
  const [filename, csv] = vi.mocked(downloadCsv).mock.calls[0];
  expect(filename).toContain("2026-06-30-CNX-OCI");
  expect(csv).toMatch(/\r\nOCI,80.00,70.00,-10.00,33.33%/);
  expect(csv).not.toMatch(/\r\nAC,/);
  expect(refresh).not.toHaveBeenCalled();
});

const date = "2026-06-30";
async function readStatusFixture(): Promise<ApiEnvelope<BalanceMovementPayload>> {
  const data = await createApiClient({ mode: "mock" }).getBalanceMovementAnalysis({ reportDate: date });
  const prior = [100, 80, 20];
  const current = [120, 70, 20];
  data.result.rows = (["AC", "OCI", "TPL"] as const).map((basis_bucket, i) => ({
    report_date: date, report_month: "2026-06", currency_basis: "CNX", sort_order: i, basis_bucket,
    previous_balance: String(prior[i] * 1e8), current_balance: String(current[i] * 1e8),
    previous_balance_pct: String(prior[i] / 2), current_balance_pct: String(current[i] / 2.1),
    balance_change: String((current[i] - prior[i]) * 1e8),
    change_pct: String((current[i] - prior[i]) / prior[i] * 100),
    contribution_pct: String(Math.abs(current[i] - prior[i]) / 30 * 100),
    zqtz_amount: String(current[i] * 1e8), gl_amount: String(current[i] * 1e8),
    reconciliation_diff: "0", reconciliation_status: "matched", chain_status: "continuous",
    position_source_basis: i === 1 ? "CNY" : "CNX",
    source_version: "synthetic-read-status-source", rule_version: "synthetic-read-status-rule",
  }));
  data.result.summary = {
    previous_balance_total: "20000000000", current_balance_total: "21000000000",
    balance_change_total: "1000000000", zqtz_amount_total: "21000000000",
    reconciliation_diff_total: "0", matched_bucket_count: 3, bucket_count: 3,
  };
  data.result.trend_months = [];
  data.result.business_trend_months = [];
  data.result.structure_migration_analysis = null;
  data.result.zqtz_calibration_analysis = null;
  data.result.zqtz_maturity_structure = null;
  data.result.zqtz_concentration_analysis = null;
  const meta = {
    source_tables: ["synthetic_component_table"], source_scope: "synthetic only",
    report_date: date, prior_report_date: "2026-05-31", currency_basis: "CNX", unit: "yuan" as const,
    eligible_total: "21000000000", covered_total: "21000000000", unknown_total: "0",
    coverage_pct: "100", status: "supported" as const, caveat: "synthetic only",
  };
  data.result.basis_movement_decomposition = {
    meta,
    buckets: data.result.rows.map((row) => ({
      ...row, rows: [], residual_amount: row.basis_bucket === "OCI" ? "300000000" : "0",
      closing_check: row.basis_bucket === "OCI" ? "300000000" : "0",
    })),
  };
  data.result.difference_attribution_waterfall = {
    reference_label: "synthetic source", reference_total: "20500000000",
    target_label: "synthetic target", target_total: "21000000000", net_difference: "500000000",
    components: [{
      component_key: "residual_unclassified", component_label: "未分类 / 残差", amount: "500000000",
      source_kind: "residual", evidence_note: "synthetic only", is_residual: true, is_supported: true,
    }],
    closing_check: "0", caveat: "synthetic only",
  };
  data.result.accounting_controls = ["141", "142", "143", "1440101"];
  data.result.excluded_controls = ["144020"];
  data.result_meta = {
    ...data.result_meta,
    requested_report_date: date, resolved_report_date: date, as_of_date: date,
    quality_flag: "ok", fallback_mode: "none", fallback_date: null,
    source_version: "synthetic-read-status-source", rule_version: "synthetic-read-status-rule",
    tables_used: ["synthetic_only"], trace_id: "synthetic-read-status-trace",
  };
  return data;
}

async function setupReadStatus(
  entry = `/balance-movement-analysis?report_date=${date}&currency_basis=CNX`,
  initialFailure?: "dates" | "detail",
) {
  const detail = await readStatusFixture();
  const client = createApiClient({ mode: "mock" });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 60_000, refetchOnWindowFocus: false } } });
  const dateEnvelope: Awaited<ReturnType<typeof client.getBalanceMovementDates>> = {
    result: { report_dates: [date, "2026-05-31"], currency_basis: "CNX", freshness_status: "fresh", latest_read_model_report_date: date, latest_upstream_control_report_date: date },
    result_meta: detail.result_meta,
  };
  const dates = vi.spyOn(client, "getBalanceMovementDates").mockResolvedValue(dateEnvelope);
  const read = vi.spyOn(client, "getBalanceMovementAnalysis").mockResolvedValue(detail);
  const refresh = vi.spyOn(client, "refreshBalanceMovementAnalysis").mockResolvedValue({ status: "completed", report_date: date, currency_basis: "CNX", cache_key: "synthetic-read-status", rule_version: "synthetic-read-status-rule" });
  if (initialFailure === "dates") dates.mockRejectedValue(new Error("synthetic initial dates unavailable"));
  if (initialFailure === "detail") read.mockRejectedValue(new Error("synthetic initial detail unavailable"));
  function Location() { const location = useLocation(); return <output data-testid="read-status-location">{location.pathname}{location.search}</output>; }
  render(<MemoryRouter initialEntries={[entry]}><QueryClientProvider client={queryClient}><ApiClientProvider client={client}><Location /><Routes><Route path="/balance-movement-analysis" element={<BalanceMovementAnalysisPage />} /></Routes></ApiClientProvider></QueryClientProvider></MemoryRouter>);
  await screen.findByTestId(initialFailure ? `balance-movement-analysis-${initialFailure === "dates" ? "date" : "detail"}-status` : "balance-movement-analysis-accounting-buckets");
  return { client, queryClient, dates, read, refresh, detail, dateEnvelope };
}

function exportedCsv() {
  fireEvent.click(screen.getByTestId("balance-movement-analysis-export-csv"));
  return vi.mocked(downloadCsv).mock.calls.at(-1)![1];
}

function governanceState(label: string) {
  return screen.getByText(label, { selector: "strong" }).closest("article")!;
}

it("keeps the originally requested date visible in governance and CSV after canonicalization", async () => {
  const state = await setupReadStatus("/balance-movement-analysis?report_date=2026-04-30&currency_basis=CNY");
  expect(screen.getByTestId("balance-movement-selection-dates")).toHaveTextContent(`请求日期 2026-04-30 · 实际报告日 ${date}`);
  await waitFor(() => expect(screen.getByTestId("read-status-location")).toHaveTextContent(`report_date=${date}`));
  expect(governanceState("回退日期")).toHaveTextContent(date);
  expect(governanceState("回退日期")).not.toHaveTextContent("当前未发生日期回退");
  const csv = exportedCsv();
  expect(csv).toContain("meta,requested_report_date,2026-04-30,");
  expect(csv).toContain(`meta,resolved_report_date,${date},`);
  expect(csv).toContain("meta,read_status,confirmed,");
  expect(state.refresh).not.toHaveBeenCalled();
});

it.each(["dates", "detail"] as const)("marks a failed %s read as cached in freshness, governance and CSV without relabeling original evidence", async (query) => {
  const state = await setupReadStatus();
  const failure = new Error(`synthetic ${query} unavailable`);
  if (query === "dates") state.dates.mockRejectedValue(failure);
  else state.read.mockRejectedValue(failure);
  await act(async () => { await state.queryClient.refetchQueries({ queryKey: ["balance-movement-analysis", query] }); });
  await waitFor(() => expect(governanceState("加载 / 刷新失败")).toHaveTextContent("是"));
  expect(screen.getByTestId(`balance-movement-analysis-${query === "dates" ? "date" : "detail"}-status`)).toHaveTextContent("上次成功读取结果");
  expect.soft(screen.getByTestId("balance-movement-analysis-freshness")).not.toHaveTextContent("数据已同步");
  expect.soft(screen.getByTestId("balance-movement-analysis-data-states")).not.toHaveTextContent("数据已同步");
  const csv = exportedCsv();
  expect.soft(csv).toContain("meta,read_status,cached_after_error,");
  expect(csv).toContain("meta,source_version,synthetic-read-status-source,");
  expect(csv).toContain(`meta,resolved_report_date,${date},`);
  expect(screen.getByTestId("balance-movement-selection-dates")).toHaveTextContent(`请求日期 ${date} · 实际报告日 ${date}`);
  if (query === "detail") {
    fireEvent.change(screen.getByLabelText("余额变动分析-分类桶"), { target: { value: "OCI" } });
    expect(screen.getByRole("button", { name: "查看分类桶来源" })).toBeDisabled();
  }
});

it("surfaces a failed refresh POST in governance and CSV, then clears it on a successful retry", async () => {
  const state = await setupReadStatus();
  state.refresh.mockRejectedValueOnce(new Error("synthetic refresh unavailable"));
  fireEvent.click(screen.getByTestId("balance-movement-analysis-refresh"));
  await waitFor(() => expect(screen.getByTestId("balance-movement-analysis-refresh-message")).toHaveTextContent("synthetic refresh unavailable"));
  expect.soft(governanceState("加载 / 刷新失败")).toHaveTextContent("synthetic refresh unavailable");
  expect.soft(governanceState("加载 / 刷新失败")).not.toHaveTextContent("当前没有加载或刷新错误");
  expect.soft(exportedCsv()).toContain("meta,read_status,cached_after_error,");
  expect.soft(screen.getByTestId("balance-movement-analysis-freshness")).not.toHaveTextContent("数据已同步");
  fireEvent.click(screen.getByTestId("balance-movement-analysis-refresh"));
  await waitFor(() => expect(state.read).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(governanceState("加载 / 刷新失败")).toHaveTextContent("当前没有加载或刷新错误"));
  expect(exportedCsv()).toContain("meta,read_status,confirmed,");
  expect(screen.getByTestId("balance-movement-analysis-freshness")).toHaveTextContent("数据已同步");
});

it.each(["dates", "detail"] as const)("does not treat old cached data as a successful post-refresh %s read", async (query) => {
  const state = await setupReadStatus();
  if (query === "dates") state.dates.mockRejectedValue(new Error("synthetic follow-up dates unavailable"));
  else state.read.mockRejectedValue(new Error("synthetic follow-up detail unavailable"));
  fireEvent.click(screen.getByTestId("balance-movement-analysis-refresh"));
  await waitFor(() => expect(screen.getByTestId("balance-movement-analysis-refresh")).toBeEnabled());
  await waitFor(() => expect(governanceState("加载 / 刷新失败")).toHaveTextContent("是"));
  expect.soft(screen.getByTestId("balance-movement-analysis-refresh-message")).toHaveTextContent(`synthetic follow-up ${query} unavailable`);
  expect(exportedCsv()).toContain("meta,read_status,cached_after_error,");
  expect(exportedCsv()).toContain("meta,source_version,synthetic-read-status-source,");
  if (query === "dates") expect(state.read).toHaveBeenCalledTimes(1);
  state.dates.mockResolvedValue(state.dateEnvelope);
  state.read.mockResolvedValue(state.detail);
  fireEvent.click(within(screen.getByTestId(`balance-movement-analysis-${query === "dates" ? "date" : "detail"}-status`)).getByRole("button", { name: "重试读取" }));
  await waitFor(() => expect(screen.queryByTestId("balance-movement-analysis-refresh-message")).not.toBeInTheDocument());
  expect(governanceState("加载 / 刷新失败")).toHaveTextContent("当前没有加载或刷新错误");
  expect(exportedCsv()).toContain("meta,read_status,confirmed,");
  expect(state.refresh).toHaveBeenCalledTimes(1);
});

it("confirms successfully read data and reports no fallback for the requested month", async () => {
  await setupReadStatus();
  expect(screen.getByTestId("balance-movement-analysis-freshness")).toHaveTextContent("数据已同步");
  expect(governanceState("回退日期")).toHaveTextContent("当前未发生日期回退");
  expect(governanceState("加载 / 刷新失败")).toHaveTextContent("当前没有加载或刷新错误");
  expect(exportedCsv()).toContain("meta,read_status,confirmed,");
});


it.each(["dates", "detail"] as const)("does not claim a confirmed snapshot when the initial %s read fails without cache", async (query) => {
  await setupReadStatus(undefined, query);
  const status = screen.getByTestId(`balance-movement-analysis-${query === "dates" ? "date" : "detail"}-status`);
  expect(status).not.toHaveTextContent("上次成功读取结果");
  expect(screen.queryByTestId("balance-movement-analysis-accounting-buckets")).not.toBeInTheDocument();
  expect(screen.getByTestId("balance-movement-analysis-export-csv")).toBeDisabled();
  expect(governanceState("加载 / 刷新失败")).toHaveTextContent("是");
  expect(governanceState("回退日期")).toHaveTextContent("未知");
});

it.each(["dates", "detail"] as const)("exports a pending %s refetch as refreshing until the new read succeeds", async (query) => {
  const state = await setupReadStatus();
  let release = () => {};
  if (query === "dates") {
    state.dates.mockReturnValue(new Promise((resolve) => { release = () => resolve(state.dateEnvelope); }));
  } else {
    state.read.mockReturnValue(new Promise((resolve) => { release = () => resolve(state.detail); }));
  }
  let refetch!: Promise<void>;
  act(() => { refetch = state.queryClient.refetchQueries({ queryKey: ["balance-movement-analysis", query] }); });
  try {
    await waitFor(() => expect(governanceState("加载中")).toHaveTextContent("请求中"));
    expect.soft(exportedCsv()).toContain("meta,read_status,refreshing,");
    expect.soft(screen.getByTestId("balance-movement-analysis-freshness")).not.toHaveTextContent("数据已同步");
  } finally {
    await act(async () => { release(); await refetch; });
  }
  await waitFor(() => expect(governanceState("加载中")).toHaveTextContent("已完成"));
  expect(exportedCsv()).toContain("meta,read_status,confirmed,");
});


it.each(["bucket", "evidence"] as const)("keeps a refresh failure across presentation-only %s navigation without another read", async (change) => {
  const state = await setupReadStatus();
  fireEvent.change(screen.getByLabelText("余额变动分析-分类桶"), { target: { value: "OCI" } });
  state.refresh.mockRejectedValueOnce(new Error("synthetic refresh unavailable"));
  fireEvent.click(screen.getByTestId("balance-movement-analysis-refresh"));
  await waitFor(() => expect(screen.getByTestId("balance-movement-analysis-refresh-message")).toHaveTextContent("synthetic refresh unavailable"));
  const readCounts = [state.dates.mock.calls.length, state.read.mock.calls.length];
  if (change === "bucket") fireEvent.change(screen.getByLabelText("余额变动分析-分类桶"), { target: { value: "TPL" } });
  else fireEvent.click(screen.getByRole("button", { name: "查看分类桶来源" }));
  expect([state.dates.mock.calls.length, state.read.mock.calls.length]).toEqual(readCounts);
  expect.soft(screen.getByTestId("balance-movement-analysis-freshness")).not.toHaveTextContent("数据已同步");
  expect.soft(screen.queryByTestId("balance-movement-analysis-refresh-message")).not.toBeNull();
  expect.soft(governanceState("加载 / 刷新失败")).toHaveTextContent("synthetic refresh unavailable");
  expect(exportedCsv()).toContain("meta,read_status,cached_after_error,");
  expect(exportedCsv()).toContain("meta,source_version,synthetic-read-status-source,");
});
