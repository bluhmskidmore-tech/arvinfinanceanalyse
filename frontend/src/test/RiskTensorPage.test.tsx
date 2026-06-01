import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="risk-tensor-echarts-stub" />,
}));

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ResultMeta, RiskTensorPayload } from "../api/contracts";
import { routerFuture } from "../router/routerFuture";
import { createWorkbenchMemoryRouter } from "./renderWorkbenchApp";

const WAN_YUAN_UNIT = "\u4e07\u5143";
const YI_YUAN_UNIT = "\u4ebf\u5143";
const RISK_TENSOR_CSS_PATH = resolve(
  process.cwd(),
  "src/features/risk-tensor/RiskTensorPage.css",
);

function buildMeta(resultKind: string, traceId: string): ResultMeta {
  return {
    trace_id: traceId,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_tensor_test",
    vendor_version: "vv_none",
    rule_version: "rv_tensor_test",
    cache_version: "cv_tensor_test",
    quality_flag: "warning",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T08:00:00Z",
  };
}

function tensorResult(reportDate: string): RiskTensorPayload {
  return {
    report_date: reportDate,
    portfolio_dv01: "12.34",
    krd_1y: "1",
    krd_3y: "2",
    krd_5y: "3",
    krd_7y: "2.5",
    krd_10y: "1.5",
    krd_30y: "0.5",
    cs01: "8.88",
    portfolio_convexity: "0.42",
    portfolio_modified_duration: "4.2",
    issuer_concentration_hhi: "0.18",
    issuer_top5_weight: "0.35",
    asset_cashflow_30d: "300.3",
    asset_cashflow_90d: "500.5",
    liability_cashflow_30d: "200.2",
    liability_cashflow_90d: "300.3",
    liquidity_gap_30d: "100.1",
    liquidity_gap_90d: "200.2",
    liquidity_gap_30d_ratio: "0.05",
    total_market_value: "999.99",
    bond_count: 12,
    quality_flag: "warning",
    warnings: ["Issuer concentration above desk threshold"],
    prior_period_change: {
      status: "available",
      comparison_report_date: "2026-02-27",
      summary: "较上一报告日 2026-02-27：监管口径 DV01 增加 +4.34；主风险桶由 3Y 切至 5Y。",
      dominant_krd_bucket: "5Y",
      previous_dominant_krd_bucket: "3Y",
      dominant_krd_shifted: true,
      metrics: [
        {
          key: "regulatory_dv01",
          label: "监管口径 DV01",
          current: {
            raw: 12.34,
            unit: "dv01" as const,
            display: "12.34",
            precision: 2,
            sign_aware: false,
          },
          previous: {
            raw: 8,
            unit: "dv01" as const,
            display: "8.00",
            precision: 2,
            sign_aware: false,
          },
          delta: {
            raw: 4.34,
            unit: "dv01" as const,
            display: "+4.34",
            precision: 2,
            sign_aware: true,
          },
          current_display: "12.34",
          previous_display: "8.00",
          delta_display: "+4.34",
          direction: "up",
          tone: "warning",
          interpretation: "监管口径 DV01 扩大",
        },
        {
          key: "liquidity_gap_30d_ratio",
          label: "30 日流动性缺口比例",
          current: {
            raw: 0.05,
            unit: "ratio" as const,
            display: "0.05",
            precision: 4,
            sign_aware: true,
          },
          previous: {
            raw: 0.03,
            unit: "ratio" as const,
            display: "0.03",
            precision: 4,
            sign_aware: true,
          },
          delta: {
            raw: 0.02,
            unit: "ratio" as const,
            display: "+0.02",
            precision: 4,
            sign_aware: true,
          },
          current_display: "5.0%",
          previous_display: "3.0%",
          delta_display: "+2.0%",
          direction: "up",
          tone: "good",
          interpretation: "30 日流动性缓冲改善",
        },
      ],
    },
  };
}

function renderRiskTensorRoute(
  initialEntry: string,
  client: ReturnType<typeof createApiClient>,
) {
  const router = createWorkbenchMemoryRouter([initialEntry]);
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
    },
  });

  return render(
    <ApiClientProvider client={client}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} future={routerFuture} />
      </QueryClientProvider>
    </ApiClientProvider>,
  );
}

describe("RiskTensorPage", () => {
  it("keeps page-local decorative colors on the homepage blue-gray token family", () => {
    const css = readFileSync(RISK_TENSOR_CSS_PATH, "utf8");

    expect(css).not.toMatch(/--moss-color-warm-(terracotta|taupe|slate-blue|burgundy)/);
    expect(css).not.toMatch(/rgba\((124, 88, 61|141, 48, 58|184, 121, 47|82, 63, 44)/);
    expect(css).not.toMatch(/rgba\((255, 253, 248|249, 244, 235)/);
    expect(css).toContain("var(--moss-color-info-600)");
    expect(css).toContain("var(--moss-color-warning-600)");
    expect(css).toContain("var(--moss-color-danger-600)");
    expect(css).toContain("var(--moss-color-text-muted)");
  });

  it("converts backend yuan amounts into the risk tensor page display units", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_yuan_unit_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_yuan_unit_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        portfolio_dv01: "120000",
        regulatory_dv01: "880000",
        krd_5y: "30000",
        cs01: "45600",
        total_market_value: "300000000",
        asset_cashflow_30d: "300000000",
        asset_cashflow_90d: "500000000",
        liability_cashflow_30d: "200000000",
        liability_cashflow_90d: "250000000",
        liquidity_gap_30d: "100000000",
        liquidity_gap_90d: "250000000",
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const kpi = await screen.findByTestId("risk-tensor-kpi-grid");
    expect(kpi).toHaveTextContent(new RegExp(`12\\.00\\s*${WAN_YUAN_UNIT}`));
    expect(kpi).toHaveTextContent(new RegExp(`88\\.00\\s*${WAN_YUAN_UNIT}`));
    expect(kpi).toHaveTextContent(new RegExp(`4\\.56\\s*${WAN_YUAN_UNIT}`));
    expect(kpi).toHaveTextContent(new RegExp(`3\\.00\\s*${YI_YUAN_UNIT}`));

    const cashflowGrid = await screen.findByTestId("risk-tensor-cashflow-grid");
    expect(within(cashflowGrid).getAllByText("3.00").length).toBeGreaterThanOrEqual(1);
    expect(cashflowGrid).toHaveTextContent(new RegExp(`3\\.00\\s*${YI_YUAN_UNIT}`));
    expect(cashflowGrid).toHaveTextContent(new RegExp(`2\\.00\\s*${YI_YUAN_UNIT}`));

    expect(screen.getByTestId("risk-tensor-tenor-drill")).toHaveTextContent(
      new RegExp(`3\\.00\\s*${WAN_YUAN_UNIT}`),
    );
  });

  it("surfaces the backend rate-risk duration denominator scope", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_duration_scope_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_duration_scope_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        total_market_value: "500000000",
        rate_risk_market_value: "400000000",
        rate_risk_dv01: "120000",
        rate_risk_modified_duration: "4.2",
        duration_excluded_market_value: "100000000",
        duration_excluded_count: 2,
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const durationScope = await screen.findByTestId("risk-tensor-duration-scope");
    expect(durationScope).toHaveTextContent("利率风险适用资产覆盖");
    expect(durationScope).toHaveTextContent("无到期日或零久期资产不造期限");
    expect(durationScope).toHaveTextContent(new RegExp(`4\\.00\\s*${YI_YUAN_UNIT}`));
    expect(durationScope).toHaveTextContent(new RegExp(`12\\.00\\s*${WAN_YUAN_UNIT}`));
    expect(durationScope).toHaveTextContent(new RegExp(`4\\.2\\s*年`));
    expect(durationScope).toHaveTextContent(new RegExp(`1\\.00\\s*${YI_YUAN_UNIT}`));
    expect(durationScope).toHaveTextContent("排除行数 2");
  });

  it("uses latest available report date when querystring is absent", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates"),
      result: { report_dates: ["2026-02-28", "2026-01-31"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    expect(await screen.findByRole("heading", { name: "风险张量" })).toBeInTheDocument();
    const kpi = await screen.findByTestId("risk-tensor-kpi-grid");
    const brief = await screen.findByTestId("risk-tensor-brief");
    expect(brief).toHaveTextContent("风险判读");
    expect(brief).toHaveTextContent("主风险桶 5Y");
    expect(brief).toHaveTextContent("30 日缺口为正");
    expect(brief).toHaveTextContent("质量标记：预警");
    expect(brief).toHaveTextContent("报告日 2026-02-28");
    expect(brief).toHaveTextContent("未降级");
    expect(brief).toHaveTextContent("来源 sv_tensor_test");
    expect(brief).toHaveTextContent("控制项未接入");
    expect(kpi).toHaveTextContent(new RegExp(`0\\.00\\s*${WAN_YUAN_UNIT}`));
    expect(kpi).toHaveTextContent("监管口径 DV01");
    expect(kpi).toHaveTextContent("待接入");
    expect(kpi).toHaveTextContent(new RegExp(`0\\.00\\s*${WAN_YUAN_UNIT}`));
    expect(screen.getByText("集中度")).toBeInTheDocument();
    expect(screen.getByText("流动性现金流缺口")).toBeInTheDocument();
    expect(screen.getByText("30 日资产现金流 - 负债现金流")).toBeInTheDocument();
    expect(screen.getByText("90 日资产现金流 - 负债现金流")).toBeInTheDocument();
    expect(screen.getByTestId("risk-tensor-liquidity-gap-ratio")).toHaveTextContent("5.0%");
    expect(screen.getAllByText("5.0%").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("现金流构成")).toBeInTheDocument();
    expect(screen.getByTestId("risk-tensor-cashflow-grid")).toBeVisible();
    expect(screen.getByText("30 日资产现金流")).toBeInTheDocument();
    expect(screen.getByText("30 日负债现金流")).toBeInTheDocument();
    expect(screen.getByText("90 日资产现金流")).toBeInTheDocument();
    expect(screen.getByText("90 日负债现金流")).toBeInTheDocument();
    expect(screen.getAllByText("Issuer concentration above desk threshold").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("质量标记：预警")).toBeInTheDocument();
    const priorChange = screen.getByTestId("risk-tensor-prior-period-change");
    expect(priorChange).toHaveTextContent("较上一报告日 2026-02-27");
    expect(priorChange).toHaveTextContent("监管口径 DV01");
    expect(priorChange).toHaveTextContent("+4.34");
    expect(priorChange).toHaveTextContent("30 日流动性缺口比例");
    expect(priorChange).toHaveTextContent("+2.0%");
    expect(priorChange).toHaveTextContent("30 日流动性缓冲改善");
    expect(screen.getByTestId("risk-tensor-tenor-drill")).toHaveTextContent("5Y");
    expect(screen.getByTestId("risk-tensor-tenor-drill")).toHaveTextContent("3");
    expect(screen.getByTestId("risk-tensor-result-meta-panel")).toBeVisible();
    expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent("tr_tensor_2026-02-28");
    expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent("sv_tensor_test");

    await waitFor(() => {
      expect(getRiskTensorDates).toHaveBeenCalled();
      expect(getRiskTensor).toHaveBeenCalledWith("2026-02-28");
    });
  });

  it("lets users switch among backend report dates from the page", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_switch_dates"),
      result: { report_dates: ["2026-02-28", "2026-01-31"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_switch_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        ...(reportDate === "2026-01-31"
          ? {
              krd_1y: "90000",
              krd_3y: "20000",
              krd_5y: "30000",
            }
          : {}),
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const reportDateSelect = await screen.findByLabelText("风险报告日");
    expect(reportDateSelect).toHaveValue("2026-02-28");

    await user.selectOptions(reportDateSelect, "2026-01-31");

    await waitFor(() => {
      expect(getRiskTensor).toHaveBeenCalledWith("2026-01-31");
    });
    expect(reportDateSelect).toHaveValue("2026-01-31");
    expect(await screen.findByTestId("risk-tensor-brief")).toHaveTextContent("报告日 2026-01-31");
    expect(screen.getByTestId("risk-tensor-brief")).toHaveTextContent("主风险桶 1Y");
  });

  it("renders prior-period no-data state without comparison metric cards", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_no_prior_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_no_prior_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        prior_period_change: {
          status: "no_prior",
          comparison_report_date: null,
          summary: "no prior comparable data",
          dominant_krd_bucket: "5Y",
          previous_dominant_krd_bucket: null,
          dominant_krd_shifted: false,
          metrics: [],
        },
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const priorChange = await screen.findByTestId("risk-tensor-prior-period-change");
    expect(priorChange).toHaveTextContent("no prior comparable data");
    expect(priorChange.querySelectorAll(".risk-tensor-prior-change__metric")).toHaveLength(0);
  });

  it("renders governed Numeric tensor values using backend display and raw ratio", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_numeric_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_numeric_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        portfolio_dv01: {
          raw: 1234.56,
          unit: "dv01" as const,
          display: "1,235 governed",
          precision: 0,
          sign_aware: false,
        },
        issuer_top5_weight: {
          raw: 0.42,
          unit: "ratio" as const,
          display: "0.42",
          precision: 2,
          sign_aware: false,
        },
        krd_5y: {
          raw: 3,
          unit: "ratio" as const,
          display: "3 governed",
          precision: 0,
          sign_aware: true,
        },
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const kpi = await screen.findByTestId("risk-tensor-kpi-grid");
    expect(kpi).toHaveTextContent(new RegExp(`0\\.12\\s*${WAN_YUAN_UNIT}`));
    expect(screen.getAllByText("42.0%").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByTestId("risk-tensor-tenor-drill")).toHaveTextContent(
      new RegExp(`0\\.00\\s*${WAN_YUAN_UNIT}`),
    );
  });

  it("renders backend-provided regulatory DV01 instead of the pending marker", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_regulatory_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_regulatory_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        regulatory_dv01: "88.8",
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const kpi = await screen.findByTestId("risk-tensor-kpi-grid");
    expect(kpi).toHaveTextContent("监管口径 DV01");
    expect(kpi).toHaveTextContent(new RegExp(`0\\.01\\s*${WAN_YUAN_UNIT}`));
    expect(kpi).not.toHaveTextContent("待接入");
  });

  it("shows the backend DV01 limit and volatility control deck", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_controls_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_dv01_controls_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        regulatory_dv01: {
          raw: 120.5,
          unit: "dv01" as const,
          display: "120.50",
          precision: 2,
          sign_aware: false,
        },
        dv01_controls: {
          basis: "regulatory_dv01",
          limit_status: "pending_configuration",
          approved_limit_dv01: null,
          limit_usage_ratio: null,
          volatility_status: "pending_market_volatility",
          daily_rate_volatility_bp: null,
          dominant_krd_bucket: "5Y",
          dominant_krd: {
            raw: 3,
            unit: "ratio" as const,
            display: "+3.00",
            precision: 2,
            sign_aware: true,
          },
          stress_scenarios: [
            {
              scenario_key: "parallel_up_10bp",
              label: "+10bp",
              shock_bp: {
                raw: 10,
                unit: "bp" as const,
                display: "+10 bp",
                precision: 0,
                sign_aware: true,
              },
              estimated_pnl_impact: {
                raw: -1205,
                unit: "yuan" as const,
                display: "-1,205.00",
                precision: 2,
                sign_aware: true,
              },
            },
            {
              scenario_key: "parallel_up_25bp",
              label: "+25bp",
              shock_bp: {
                raw: 25,
                unit: "bp" as const,
                display: "+25 bp",
                precision: 0,
                sign_aware: true,
              },
              estimated_pnl_impact: {
                raw: -3012.5,
                unit: "yuan" as const,
                display: "-3,012.50",
                precision: 2,
                sign_aware: true,
              },
            },
          ],
          operating_judgement:
            "当前监管口径 DV01 120.50；+10bp 平行上行估算影响 -1,205.00；主风险桶 5Y。审批限额与利率波动源未接入前，暂不判定超限。",
          control_actions: [
            {
              key: "approved_dv01_limit",
              title: "配置审批限额",
              status: "required",
              evidence: "审批 DV01 限额未接入。",
              action: "接入投委会或风控审批后的总 DV01 限额。",
            },
            {
              key: "rate_volatility_input",
              title: "接入利率波动",
              status: "required",
              evidence: "日度利率波动率未接入。",
              action: "接入曲线波动率后生成波动预警。",
            },
          ],
          control_message: "未接入正式限额源前，只展示当前监管口径敞口和标准平行冲击，不判定是否超限。",
          action_hint: "经营落地需要先配置审批 DV01 限额、利率波动率输入与预警阈值，再计算使用率和波动预警。",
        },
      } as RiskTensorPayload,
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const controls = await screen.findByTestId("risk-tensor-dv01-controls");
    expect(controls).toHaveTextContent("DV01");
    expect(controls).toHaveTextContent(new RegExp(`0\\.01\\s*${WAN_YUAN_UNIT}`));
    expect(controls).toHaveTextContent("5Y");
    expect(controls).toHaveTextContent("+10bp");
    expect(controls).toHaveTextContent(new RegExp(`-0\\.12\\s*${WAN_YUAN_UNIT}`));
    expect(controls).toHaveTextContent("未接入正式限额源");
    expect(controls).toHaveTextContent("当前监管口径 DV01 120.50");
    expect(controls).toHaveTextContent("配置审批限额");
    expect(controls).toHaveTextContent("接入利率波动");
    expect(controls).toHaveTextContent("必做项");
    expect(controls).not.toHaveTextContent("required");
    expect(controls).toHaveTextContent("波动源待接入");
    expect(controls).not.toHaveTextContent("pending_configuration");
    expect(controls).not.toHaveTextContent("pending_market_volatility");
  });

  it("surfaces backend-blocked stale dates without using them as the default", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates_with_blocked"),
      result: {
        report_dates: ["2026-02-28"],
        blocked_report_dates: [
          {
            report_date: "2026-02-26",
            reason: "older stale tensor",
          },
          {
            report_date: "2026-02-27",
            reason: "risk tensor source lineage is stale",
          },
        ],
      },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const blockedDates = await screen.findByTestId("risk-tensor-blocked-dates");
    expect(blockedDates).toHaveTextContent("2026-02-27");
    expect(blockedDates).toHaveTextContent("risk tensor source lineage is stale");
    expect(blockedDates).not.toHaveTextContent("older stale tensor");

    await waitFor(() => {
      expect(getRiskTensor).toHaveBeenCalledWith("2026-02-28");
      expect(getRiskTensor).not.toHaveBeenCalledWith("2026-02-27");
    });
  });

  it("honors report_date in the URL querystring", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates"),
      result: { report_dates: ["2026-02-28", "2026-01-31"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    renderRiskTensorRoute("/risk-tensor?report_date=2026-03-15", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    expect(await screen.findByRole("heading", { name: "风险张量" })).toBeInTheDocument();
    await waitFor(() => {
      expect(getRiskTensor).toHaveBeenCalledWith("2026-03-15");
    });
  });

  it("does not fall back to a hardcoded report date when backend dates are empty", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates_empty"),
      result: { report_dates: [] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    expect(await screen.findByText("后端未返回可用风险报告日。")).toBeInTheDocument();
    expect(getRiskTensor).not.toHaveBeenCalled();
    expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent("tr_tensor_dates_empty");
  });
});
