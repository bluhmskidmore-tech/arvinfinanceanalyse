import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiClientProvider, createApiClient, type ApiClient } from "../../../api/client";
import type { ApiEnvelope, RiskScenarioStressPayload, RiskTensorDatesPayload } from "../../../api/contracts";
import { MarketPortfolioScenarioPanel } from "./MarketPortfolioScenarioPanel";

const CURVE_DATE = "2026-09-04";
const HISTORY_DATE = "2026-08-31";

function scenario(date = CURVE_DATE): ApiEnvelope<RiskScenarioStressPayload> {
  return {
    result_meta: { fallback_mode: "none", result_kind: "risk.tensor.scenario_stress", basis: "scenario", formal_use_allowed: false },
    result: {
      report_date: date, basis: "scenario", rule_version: "scenario-v1", source: { source_version: "risk-v1" },
      evidence: {
        requested_report_date: date, actual_risk_date: date, date_status: "verified", fallback_status: "none",
        fallback_date: null, metric_id: "MTR-RSK-001R", scope_label: "适用监管口径持仓", amount_display_allowed: true,
        human_review_required: true,
        coverage: { status: "complete", total_position_count: 5, included_position_count: 4, excluded_position_count: 1, missing_risk_position_count: 0, reasons: [] },
      },
      scenarios: [{
        scenario_key: "parallel_rate_up_10bp", source_field: "regulatory_dv01", data_status: "available", human_review_required: true,
        shock: { raw: 10, raw_text: "10", unit: "bp", display: "10", precision: 2, sign_aware: true },
        estimated_impact: { raw: -10000, raw_text: "-10000", unit: "yuan", display: "-10000", precision: 2, sign_aware: true },
      }],
      summary: { worst_estimated_impact: { raw: -999999, unit: "yuan" } }, warnings: [], source_warnings: [],
    },
  } as unknown as ApiEnvelope<RiskScenarioStressPayload>;
}

function setup(options: {
  curve?: string | null;
  dates?: string[];
  blockedDates?: RiskTensorDatesPayload["blocked_report_dates"];
  response?: ApiEnvelope<RiskScenarioStressPayload>;
  failure?: Error;
  loadScenario?: (date: string) => Promise<ApiEnvelope<RiskScenarioStressPayload>>;
} = {}) {
  const getRiskTensorDates = vi.fn(async () => ({ result: {
    report_dates: options.dates ?? [CURVE_DATE, HISTORY_DATE], blocked_report_dates: options.blockedDates,
  } } as ApiEnvelope<RiskTensorDatesPayload>));
  const getRiskScenarioStress = vi.fn(async (date: string) => {
    if (options.failure) throw options.failure;
    if (options.loadScenario) return options.loadScenario(date);
    return options.response ?? scenario(date);
  });
  const client: ApiClient = { ...createApiClient({ mode: "mock" }), getRiskTensorDates, getRiskScenarioStress };
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrap = (curve: string | null) => <ApiClientProvider client={client}><QueryClientProvider client={queryClient}><MarketPortfolioScenarioPanel curveObservationDate={curve} /></QueryClientProvider></ApiClientProvider>;
  const view = render(wrap(options.curve === undefined ? CURVE_DATE : options.curve));
  return { ...view, getRiskTensorDates, getRiskScenarioStress, queryClient, wrap };
}

describe("MarketPortfolioScenarioPanel", () => {
  it("loads on demand, reads only the fixed scenario and keeps exact date, unit and scope", async () => {
    const { getRiskTensorDates, getRiskScenarioStress } = setup();
    expect(screen.getByRole("heading", { name: "组合利率情景" })).toBeVisible();
    expect(screen.getByText("平行上行 10 bp")).toBeVisible();
    expect(screen.queryByText(/基于已物化监管口径 DV01 的线性冲击估算/)).not.toBeInTheDocument();
    expect(getRiskTensorDates).not.toHaveBeenCalled();
    expect(getRiskScenarioStress).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "加载组合情景" }));
    expect(await within(await screen.findByRole("dialog")).findByText("-10,000.00")).toBeInTheDocument();
    expect(getRiskScenarioStress).toHaveBeenCalledWith(CURVE_DATE);
    expect(screen.queryByText(/999,999/)).not.toBeInTheDocument();
    expect(screen.getByText(/监管口径 DV01（MTR-RSK-001R）/)).toBeInTheDocument();
    expect(screen.getByText(/按口径排除 1 项，风险输入缺失 0 项/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看风险详情" })).toHaveAttribute("href", `/risk-tensor?report_date=${CURVE_DATE}`);
    expect(screen.getByText(/基于已物化监管口径 DV01 的线性冲击估算/)).toBeVisible();
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: /close/i }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: "查看计算依据" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("-10,000.00")).toBeVisible();
    expect(getRiskTensorDates).toHaveBeenCalledTimes(1);
  });

  it("does not fall back silently and requests history only after explicit selection", async () => {
    const { getRiskScenarioStress } = setup({ dates: [HISTORY_DATE] });
    await userEvent.click(screen.getByRole("button", { name: "加载组合情景" }));
    expect(await screen.findByText(/缺少同日风险数据/)).toBeInTheDocument();
    expect(getRiskScenarioStress).not.toHaveBeenCalled();
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "历史风险日期" }), HISTORY_DATE);
    expect(await within(await screen.findByRole("dialog")).findByText("-10,000.00")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "基于历史持仓的情景" })).toBeInTheDocument();
    expect(getRiskScenarioStress).toHaveBeenCalledWith(HISTORY_DATE);
    expect(screen.getByText(CURVE_DATE)).toBeInTheDocument();
  });

  it.each(["date", "missing", "coverage", "legacy", "fallback", "unit", "source", "basis", "formal"])("withholds amount when %s evidence is invalid", async (kind) => {
    const response = scenario();
    if (kind === "date") response.result.evidence!.actual_risk_date = HISTORY_DATE;
    if (kind === "missing") response.result.scenarios[0]!.data_status = "source_missing";
    if (kind === "coverage") response.result.evidence!.coverage.status = "incomplete";
    if (kind === "legacy") delete response.result.evidence;
    if (kind === "fallback") response.result.evidence!.fallback_status = "fallback";
    if (kind === "unit") response.result.scenarios[0]!.estimated_impact.unit = "yi";
    if (kind === "source") response.result.scenarios[0]!.source_field = "portfolio_dv01";
    if (kind === "basis") response.result_meta.basis = "formal";
    if (kind === "formal") response.result_meta.formal_use_allowed = true;
    setup({ response });
    await userEvent.click(screen.getByRole("button", { name: "加载组合情景" }));
    expect(await within(await screen.findByRole("dialog")).findByText(/暂不显示金额/)).toBeInTheDocument();
    expect(screen.queryByText("-10,000.00")).not.toBeInTheDocument();
  });

  it("shows verified zero rather than treating it as missing", async () => {
    const response = scenario();
    response.result.scenarios[0]!.estimated_impact.raw = 0;
    response.result.scenarios[0]!.estimated_impact.raw_text = "0";
    setup({ response });
    await userEvent.click(screen.getByRole("button", { name: "加载组合情景" }));
    expect(await within(await screen.findByRole("dialog")).findByText("0.00")).toBeInTheDocument();
  });

  it("keeps permissions local and does not expose a cached amount after failure", async () => {
    setup({ failure: new Error("Request failed (403)") });
    await userEvent.click(screen.getByRole("button", { name: "加载组合情景" }));
    expect(await within(await screen.findByRole("dialog")).findByText(/组合风险数据权限受限/)).toBeInTheDocument();
    expect(screen.queryByText("-10,000.00")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "历史风险日期" })).not.toBeInTheDocument();
  });

  it("does not infer a risk date if the curve date is missing", async () => {
    const { getRiskTensorDates, getRiskScenarioStress } = setup({ curve: null });
    await userEvent.click(screen.getByRole("button", { name: "加载组合情景" }));
    expect(screen.getByText(/缺少曲线观察日/)).toBeInTheDocument();
    expect(getRiskTensorDates).not.toHaveBeenCalled();
    expect(getRiskScenarioStress).not.toHaveBeenCalled();
  });

  it("resets a historical selection when the curve date changes", async () => {
    const { rerender, wrap, getRiskScenarioStress } = setup({ dates: [HISTORY_DATE] });
    await userEvent.click(screen.getByRole("button", { name: "加载组合情景" }));
    await userEvent.selectOptions(await screen.findByRole("combobox"), HISTORY_DATE);
    await within(await screen.findByRole("dialog")).findByText("-10,000.00");
    rerender(wrap("2026-09-07"));
    await waitFor(() => expect(screen.queryByText("-10,000.00")).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: "加载组合情景" })).toHaveAttribute("aria-expanded", "false");
    expect(getRiskScenarioStress).toHaveBeenCalledTimes(1);
  });

  it("keeps the amount in yuan when the backend has no exact raw_text", async () => {
    const response = scenario();
    delete response.result.scenarios[0]!.estimated_impact.raw_text;
    setup({ response });
    await userEvent.click(screen.getByRole("button", { name: "加载组合情景" }));
    expect(await within(await screen.findByRole("dialog")).findByText("-10,000.00")).toBeInTheDocument();
    expect(within(screen.getByRole("dialog")).getByText("元", { exact: true })).toBeInTheDocument();
  });

  it("allows explicit historical selection after a same-day response reveals a different actual date", async () => {
    const response = scenario();
    response.result.evidence!.actual_risk_date = HISTORY_DATE;
    const { getRiskScenarioStress } = setup({ response });
    await userEvent.click(screen.getByRole("button", { name: "加载组合情景" }));
    await screen.findByText(/风险实际日期与所选日期不一致/);
    expect(getRiskScenarioStress).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("-10,000.00")).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByRole("combobox"), HISTORY_DATE);
    await waitFor(() => expect(getRiskScenarioStress).toHaveBeenCalledWith(HISTORY_DATE));
  });

  it.each(["incomplete", "unknown-date", "source-missing"])("offers explicit history when a same-day scenario has %s evidence", async (kind) => {
    const sameDay = scenario();
    if (kind === "incomplete") {
      sameDay.result.evidence!.coverage = {
        status: "incomplete", total_position_count: 1799, included_position_count: 1799,
        excluded_position_count: 0, missing_risk_position_count: 139, reasons: ["139项缺少到期日，监管DV01尚未核验。"],
      };
      sameDay.result.evidence!.amount_display_allowed = false;
    }
    if (kind === "unknown-date") sameDay.result.evidence!.date_status = "unknown";
    if (kind === "source-missing") sameDay.result.scenarios[0]!.data_status = "source_missing";
    const { getRiskScenarioStress } = setup({ loadScenario: async (date) => date === CURVE_DATE ? sameDay : scenario(date) });
    await userEvent.click(screen.getByRole("button", { name: "加载组合情景" }));
    expect(await within(await screen.findByRole("dialog")).findByText(/暂不显示金额/)).toBeInTheDocument();
    expect(screen.queryByText("-10,000.00")).not.toBeInTheDocument();
    if (kind === "incomplete") expect(within(screen.getByRole("dialog")).getByText(/风险输入缺失 139 项/)).toBeInTheDocument();
    expect(getRiskScenarioStress.mock.calls).toEqual([[CURVE_DATE]]);
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "历史风险日期" }), HISTORY_DATE);
    expect(await within(await screen.findByRole("dialog")).findByText("-10,000.00")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "基于历史持仓的情景" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "历史风险日期" })).toHaveValue(HISTORY_DATE);
    expect(getRiskScenarioStress.mock.calls).toEqual([[CURVE_DATE], [HISTORY_DATE]]);
  });

  it("allows choosing history after same-day HTTP 500 without retrying the same-day request automatically", async () => {
    const { getRiskScenarioStress } = setup({ loadScenario: async (date) => {
      if (date === CURVE_DATE) throw new Error("Request failed (500)");
      return scenario(date);
    } });
    await userEvent.click(screen.getByRole("button", { name: "加载组合情景" }));
    expect(await screen.findByText(/组合情景读取失败/)).toBeInTheDocument();
    expect(getRiskScenarioStress.mock.calls).toEqual([[CURVE_DATE]]);
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "历史风险日期" }), HISTORY_DATE);
    expect(await within(await screen.findByRole("dialog")).findByText("-10,000.00")).toBeInTheDocument();
    expect(screen.queryByText(/组合情景读取失败/)).not.toBeInTheDocument();
    expect(getRiskScenarioStress.mock.calls).toEqual([[CURVE_DATE], [HISTORY_DATE]]);
  });

  it("does not describe a pending same-day request as unavailable or offer recovery before it resolves", async () => {
    let resolveScenario!: (value: ApiEnvelope<RiskScenarioStressPayload>) => void;
    const pending = new Promise<ApiEnvelope<RiskScenarioStressPayload>>((resolve) => { resolveScenario = resolve; });
    const { getRiskScenarioStress } = setup({ loadScenario: () => pending });
    await userEvent.click(screen.getByRole("button", { name: "加载组合情景" }));
    await waitFor(() => expect(getRiskScenarioStress).toHaveBeenCalledWith(CURVE_DATE));
    expect(screen.getByText(/正在核验风险日期与情景来源/)).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "历史风险日期" })).not.toBeInTheDocument();
    expect(within(screen.getByRole("dialog")).queryByText(/当前日期的情景不可用|暂不显示金额/)).not.toBeInTheDocument();
    await act(async () => { resolveScenario(scenario()); });
    expect(await within(await screen.findByRole("dialog")).findByText("-10,000.00")).toBeInTheDocument();
  });

  it("excludes blocked and future dates from the available history choices", async () => {
    const blockedHistory = "2026-09-03";
    const futureDate = "2026-09-07";
    setup({
      dates: [CURVE_DATE, HISTORY_DATE, blockedHistory, futureDate],
      blockedDates: [{ report_date: blockedHistory, reason: "风险来源不完整" }],
      failure: new Error("Request failed (500)"),
    });
    await userEvent.click(screen.getByRole("button", { name: "加载组合情景" }));
    await screen.findByRole("combobox", { name: "历史风险日期" });
    expect(screen.getAllByRole("option").map((option) => (option as HTMLOptionElement).value)).toEqual(["", HISTORY_DATE]);
  });

  it("states that no history is available when all earlier dates are blocked", async () => {
    const response = scenario();
    response.result.evidence!.coverage.status = "incomplete";
    setup({ response, blockedDates: [{ report_date: HISTORY_DATE, reason: "风险来源不完整" }] });
    await userEvent.click(screen.getByRole("button", { name: "加载组合情景" }));
    expect(await screen.findByText("暂无可选择的历史风险日期。")).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "历史风险日期" })).not.toBeInTheDocument();
  });

  it.each(["scenario", "dates"])("hides a previously displayed amount and selection after a cached %s refetch receives 403", async (kind) => {
    const { getRiskScenarioStress, getRiskTensorDates, queryClient } = setup({ dates: [HISTORY_DATE] });
    await userEvent.click(screen.getByRole("button", { name: "加载组合情景" }));
    await userEvent.selectOptions(await screen.findByRole("combobox", { name: "历史风险日期" }), HISTORY_DATE);
    expect(await within(await screen.findByRole("dialog")).findByText("-10,000.00")).toBeInTheDocument();
    if (kind === "scenario") getRiskScenarioStress.mockRejectedValue(new Error("Request failed (403)"));
    else getRiskTensorDates.mockRejectedValue(new Error("Request failed (403)"));
    await act(async () => { await queryClient.invalidateQueries({
      queryKey: kind === "scenario" ? ["market-portfolio-scenario", "mock", HISTORY_DATE] : ["market-portfolio-scenario", "dates", "mock"],
    }); });
    expect(await within(await screen.findByRole("dialog")).findByText(/组合风险数据权限受限/)).toBeInTheDocument();
    expect(screen.queryByText("-10,000.00")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "历史风险日期" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重试组合情景" })).not.toBeInTheDocument();
  });

  it("keeps source restrictions visible as a notice with their full text one click away", async () => {
    const response = scenario();
    response.result.source_warnings = ["Risk source requires review"];
    setup({ response });
    await userEvent.click(screen.getByRole("button", { name: "加载组合情景" }));
    expect(await screen.findByText(/来源含 1 条使用限制/)).toBeVisible();
    expect(screen.getByText("Risk source requires review")).not.toBeVisible();
    await userEvent.click(screen.getByText("查看情景依据"));
    expect(screen.getByText("Risk source requires review")).toBeVisible();
  });
});
