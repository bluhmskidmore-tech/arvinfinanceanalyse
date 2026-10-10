import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ApiClientProvider, createApiClient } from "../../../api/client";
import type { MarketOverviewCrisis, MarketOverviewCrisisHistoryPoint, MarketOverviewSnapshotPayload } from "../../../api/contracts";
import { MarketRiskObservation } from "./MarketRiskObservation";
import { crisisCurrentPublishable, crisisHistoryOption } from "./marketRiskObservationModel";

vi.mock("../../../components/charts/ChartCard", () => ({ ChartCard: () => <div aria-label="历史图" /> }));

function crisis(overrides: Partial<MarketOverviewCrisis> = {}): MarketOverviewCrisis {
  return {
    score: null, current_available: false, history_only: true, status: "degraded", data_status: "degraded",
    report_date: "2026-09-04", reason: "刷新待核验", regime: null, percentile: null,
    risk_gate: { eligible: false, triggered: false, threshold: 2, reason_code: "blocked" },
    dependency_gate: { status: "blocked", blocked_by: ["policy"], reason_code: "blocked" },
    score_history: [{ date: "2026-09-04", crisis_score: -0.6, percentile: 24, data_status: "degraded", available_component_count: 4, component_count: 5, available_weight: 0.85 }],
    score_trends: [], available_component_count: 4, component_count: 5,
    input_evidence: { inputs: [], missing_inputs: [], stale_inputs: [], sources: [], latest_dates: [] }, warnings: [],
    ...overrides,
  } as MarketOverviewCrisis;
}

function setup(snapshot: MarketOverviewSnapshotPayload = { crisis: crisis(), components: {} }, failure = false, capabilityStatus: "complete" | "unavailable" = "complete") {
  const baseClient = createApiClient({ mode: "mock" });
  const getMacroToolkitAnalysis = vi.fn(async () => {
    if (failure) throw new Error("failure");
    const base = await baseClient.getMacroToolkitAnalysis();
    const capabilityBase = base.result.capability_results[0];
    return { ...base, result: { ...base.result, as_of_date: "2026-09-08", capability_results: [{ ...capabilityBase, key: "not_crisis", result: { crisis_score: 999 } }, {
      ...capabilityBase, key: "crisis_score_cn", status: capabilityStatus, result: { crisis_score: 99, components: [{ key: "equity_vol", raw_value: 0, z_score: 0, weight: 0.25, latest_date: "2026-09-08" }], weights: { equity_vol: 0.25, commodity_vol: 0.15 }, commodity_coverage: { available_count: 0, tracked_count: 6, items: [] }, shadow_impact: { current_score: 99, shadow_score: 100, delta: 1, candidate_contributions: [{ field: "copper", candidate_value: 0, weight: 0.05, contribution: 0, used_in_official_score: false }] }, commodity_candidate_approval_pack: { summary: "待审批样本", copy_text: "只读审批材料" } },
    }] } };
  });
  const client = { ...createApiClient({ mode: "mock" }), getMacroToolkitAnalysis };
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<MemoryRouter><ApiClientProvider client={client}><QueryClientProvider client={queryClient}><MarketRiskObservation snapshot={snapshot} /></QueryClientProvider></ApiClientProvider></MemoryRouter>);
  return { getMacroToolkitAnalysis };
}

describe("MarketRiskObservation", () => {
  it("uses actual availability and staleness instead of static missing-code metadata", async () => {
    const inputs = [
      { field: "hs300", label: "沪深300", available: true, stale: false, warning: "HS300_MISSING" },
      { field: "aa_5y", label: "AA 5Y", available: true, stale: true, warning: "AA_5Y_MISSING" },
      { field: "nanhua", label: "南华", available: false, stale: null, warning: "NANHUA_MISSING" },
    ].map(input => ({ aliases: [], required: true, row_count: input.available ? 60 : 0, latest_date: input.available ? "2026-09-04" : null, series_id: null, source: null, stale_days: input.stale ? 9 : null, ...input }));
    setup({ components: {}, crisis: crisis({ input_evidence: { inputs, missing_inputs: ["nanhua"], stale_inputs: ["aa_5y"], sources: [], latest_dates: [] } }) });
    await userEvent.click(screen.getByRole("button", { name: "评分依据" }));
    const block = screen.getByRole("heading", { name: "评分输入" }).parentElement!;
    expect(within(block).getByText("沪深300").parentElement).toHaveTextContent("有记录 / 2026-09-04");
    expect(within(block).getByText("AA 5Y 收益率").parentElement).toHaveTextContent("有记录 / 数据陈旧 / 2026-09-04");
    expect(within(block).getByText("南华商品指数").parentElement).toHaveTextContent("缺少记录 / —");
    expect(block).not.toHaveTextContent("_MISSING");
    expect(screen.getByTestId("market-risk-current-score")).toHaveTextContent("—");
  });

  it.each([
    ["crisis dependency gate blocked: required_refresh_step_not_ready", "必要的宏观数据刷新尚未通过核验，当前评分暂不发布。"],
    ["unexpected_upstream_failure", "评分依据尚未通过核验，当前评分暂不发布。"],
  ])("keeps technical reason %s in expandable diagnostics", async (raw, message) => {
    setup({ components: {}, crisis: crisis({ reason: raw }) });
    expect(screen.getByText(new RegExp(message))).toBeVisible();
    expect(screen.queryByText(raw)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "评分依据" }));
    const diagnostic = screen.getByText(raw);
    expect(diagnostic).not.toBeVisible();
    await userEvent.click(screen.getByText("原始诊断信息"));
    expect(diagnostic).toBeVisible();
  });

  it("loads keyed full evidence only on demand and never republishes its raw score", async () => {
    const { getMacroToolkitAnalysis } = setup();
    expect(getMacroToolkitAnalysis).not.toHaveBeenCalled();
    expect(screen.getByTestId("market-risk-current-score")).toHaveTextContent("—");
    await userEvent.click(screen.getByRole("button", { name: "评分依据" }));
    expect(await screen.findByText(/完整分析实际日期 2026-09-08/)).toBeVisible();
    expect(getMacroToolkitAnalysis).toHaveBeenCalledWith({ detail: "full", historyLimit: 60 });
    expect(screen.getByTestId("market-risk-current-score")).toHaveTextContent("—");
    expect(screen.getByText("南华商品实现波动")).toBeVisible();
    expect(screen.getAllByText("组成项缺失，保留位置待补齐").length).toBeGreaterThan(0);
    expect(screen.queryByText("999")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "商品扩展与影子分析" }));
    expect(screen.getByRole("textbox", { name: "审批材料原文" })).toHaveAttribute("readonly");
    expect(screen.getByRole("textbox", { name: "审批材料原文" })).toHaveValue("只读审批材料");
    expect(screen.getByText(/这里的原始模型试算属于研究输入/)).toBeVisible();
    expect(screen.queryByRole("button", { name: /提交|批准/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "返回评分依据" }));
    expect(await screen.findByText("评分组成")).toBeVisible();
    expect(getMacroToolkitAnalysis).toHaveBeenCalledTimes(1);
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("shows zero current score when eligible and does not use operational cards as directions", async () => {
    setup({ components: {}, crisis: crisis({ score: 0, percentile: 0, history_only: false, current_available: true, status: "ok", data_status: "complete", dependency_gate: null, risk_gate: { eligible: true, triggered: false, threshold: 2, reason_code: "below" } }), signals: { status: "ok", reason: null, cards: [{ key: "ops", kind: "ops_status", title: "运行检查", stance: "不要当市场方向" }] } });
    expect(screen.getByTestId("market-risk-current-score")).toHaveTextContent("0.00");
    expect(within(screen.getByRole("heading", { name: "市场信号" }).parentElement!).queryByText("不要当市场方向")).not.toBeInTheDocument();
    expect(screen.getByText("方向暂不发布")).toBeVisible();
    expect(screen.queryByText("不要当市场方向")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "查看信号依据" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("不要当市场方向")).not.toBeVisible();
    await userEvent.click(within(dialog).getByText("技术诊断"));
    expect(within(dialog).getByText("不要当市场方向")).toBeVisible();
  });

  it.each(["missing", undefined, "unrecognized"])("keeps %s operational state pending when the action list is empty", async (tone) => {
    setup({ components: {}, actions: { status: "ok", items: [] }, signals: { status: "ok", reason: null, cards: [{ key: "ops", kind: "ops_status", title: "运行检查", stance: "缺少必要数据", tone }] } });
    expect(screen.queryByText("当前无待核验事项。")).not.toBeInTheDocument();
    expect(screen.getByText(tone === "missing" ? "数据更新需复核，部分分析结果可能暂不可用。请查看信号依据。" : "部分数据的可用状态待核验，请查看信号依据。")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "查看信号依据" }));
    const dialog = screen.getByRole("dialog");
    await userEvent.click(within(dialog).getByText("技术诊断"));
    expect(within(dialog).getByText("缺少必要数据")).toBeVisible();
  });

  it("keeps failed news counts missing and an evidence failure retryable", async () => {
    setup({ components: {}, crisis: crisis(), news: { sample: { requested: 0, returned: 0, total_rows: 0, excluded_future_rows: 0, latest_received_at: null, stale_days: null }, granularity: { datetime_rows: 0, date_only_rows: 0 }, density: { tz: "Asia/Shanghai", bucket_hours: 1, topics: [], max_count: 0 }, latest: [], status: "unavailable", reason: "新闻读取失败", compare: { same_direction: 0, conflicting: 0, review_needed: 0, candidate_scenarios: 0, review_items: [] } } }, true);
    await userEvent.click(screen.getByRole("button", { name: "新闻比较与人工复核" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/同向/)).toHaveTextContent("同向 — / 冲突 — / 待复核 —");
    await userEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    await userEvent.click(screen.getByRole("button", { name: "评分依据" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("评分依据读取失败");
    expect(screen.getByRole("button", { name: "重试" })).toBeVisible();
  });

  it("restores keyboard focus when the drawer closes", async () => {
    setup();
    const button = screen.getByRole("button", { name: "评分依据" });
    await userEvent.click(button);
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Close" }));
    await waitFor(() => expect(button).toHaveFocus());
  });

  it("does not expose stale raw research when the full capability is unavailable", async () => {
    setup(undefined, false, "unavailable");
    await userEvent.click(screen.getByRole("button", { name: "评分依据" }));
    expect(await screen.findByText("完整分析未返回可用 Crisis Score 依据，暂不展示研究明细。")).toBeVisible();
    expect(screen.queryByText("评分组成")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "商品扩展与影子分析" }));
    expect(screen.queryByRole("textbox", { name: "审批材料原文" })).not.toBeInTheDocument();
  });
});

describe("risk observation publication and history", () => {
  it.each([
    { current_available: false }, { history_only: true }, { data_status: "degraded" }, { score: Number.NaN },
    { dependency_gate: { status: "blocked" } }, { risk_gate: { eligible: false } },
  ])("fails closed for %j", patch => {
    expect(crisisCurrentPublishable(crisis({ score: 0, current_available: true, history_only: false, data_status: "complete", dependency_gate: null, risk_gate: { eligible: true, triggered: false, threshold: 2, reason_code: "below" }, ...patch } as Partial<MarketOverviewCrisis>))).toBe(false);
  });

  it("retains partial history as a separate dashed series without filling missing points", () => {
    const points = [{ date: "2026-09-01", crisis_score: 0, data_status: "complete" }, { date: "2026-09-02", crisis_score: -0.1, data_status: "degraded" }, { date: "2026-09-03", crisis_score: null, data_status: "degraded" }] as MarketOverviewCrisisHistoryPoint[];
    const option = crisisHistoryOption(points);
    const series = option?.series as Array<{ data: unknown[]; lineStyle: { type?: string }; connectNulls: boolean }>;
    expect(series[0].data).toEqual([0, null, null]);
    expect(series[1].data).toEqual([0, -0.1, null]);
    expect(series[1].lineStyle.type).toBe("dashed");
    expect(series.every(item => item.connectNulls === false)).toBe(true);
  });
});
