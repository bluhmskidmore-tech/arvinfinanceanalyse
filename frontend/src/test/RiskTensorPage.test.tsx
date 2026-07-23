import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { beforeAll, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: ({
    onEvents,
    option,
  }: {
    onEvents?: Record<string, (params: { name?: string }) => void>;
    option?: { radar?: { indicator?: unknown[] }; series?: Array<{ data?: unknown[] }> };
  }) => {
    const data = option?.series?.[0]?.data ?? [];
    const first = data[0];
    const chartData =
      first && typeof first === "object" && "value" in first && Array.isArray(first.value) ? first.value : data;
    return (
      <button
        type="button"
        data-testid="risk-tensor-echarts-stub"
        data-series={JSON.stringify(chartData)}
        data-indicator={JSON.stringify(option?.radar?.indicator ?? [])}
        onClick={() => onEvents?.click?.({ name: "1Y" })}
      />
    );
  },
}));

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ResultMeta, RiskScenarioStressPayload, RiskTensorPayload } from "../api/contracts";
import { routerFuture } from "../router/routerFuture";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { createWorkbenchMemoryRouter } from "./renderWorkbenchApp";

const WAN_YUAN_UNIT = "\u4e07\u5143";
const YI_YUAN_UNIT = "\u4ebf\u5143";
const RISK_TENSOR_CSS_PATH = resolve(
  process.cwd(),
  "src/features/risk-tensor/RiskTensorPage.css",
);

beforeAll(async () => {
  await preloadWorkbenchRouteModules("risk-tensor");
}, 20_000);

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

function buildScenarioMeta(resultKind: string, traceId: string): ResultMeta {
  return {
    ...buildMeta(resultKind, traceId),
    basis: "scenario",
    formal_use_allowed: false,
    scenario_flag: true,
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
    rate_risk_market_value: "900.00",
    rate_risk_dv01: "11.11",
    rate_risk_modified_duration: "4.20",
    duration_excluded_market_value: "99.99",
    duration_excluded_count: 2,
    missing_maturity_market_value: "0",
    missing_maturity_count: 0,
    floating_rate_proxy_market_value: "0",
    floating_rate_proxy_count: 0,
    payment_frequency_fallback_market_value: "0",
    payment_frequency_fallback_count: 0,
    bullet_value_date_fallback_market_value: "0",
    bullet_value_date_fallback_count: 0,
    projection_quality_status: "available",
    bond_count: 12,
    quality_flag: "warning",
    warnings: ["Issuer concentration above desk threshold"],
  };
}

function scenarioStressResult(reportDate: string): RiskScenarioStressPayload {
  const yuan = (raw: number | null, display = raw === null ? "待接入" : `${raw}`) => ({
    raw,
    unit: "yuan" as const,
    display,
    precision: 2,
    sign_aware: true,
  });
  const bp = (raw: number) => ({
    raw,
    unit: "bp" as const,
    display: `${raw > 0 ? "+" : ""}${raw} bp`,
    precision: 0,
    sign_aware: true,
  });
  const pct = (raw: number | null) => ({
    raw,
    unit: "pct" as const,
    display: raw === null ? "待接入" : `${(raw * 100).toFixed(1)}%`,
    precision: 1,
    sign_aware: true,
  });
  return {
    report_date: reportDate,
    basis: "scenario",
    scenario_set_id: "standard_risk_tensor_scenario_v1",
    rule_version: "rv_risk_tensor_scenario_stress_v1",
    source: {
      result_kind: "risk.tensor",
      trace_id: "tr_tensor_source",
      source_version: "sv_tensor_test",
      rule_version: "rv_tensor_test",
      cache_version: "cv_tensor_test",
      quality_flag: "warning",
    },
    summary: {
      scenario_count: 4,
      available_count: 3,
      review_required_count: 4,
      worst_estimated_impact: yuan(-50_000_000, "-50,000,000.00"),
      worst_scenario_key: "liquidity_30d_cashflow_10pct",
      message: "已生成标准多情景压力估算；所有结果均为情景口径，需复核后再用于经营判断。",
    },
    scenarios: [
      {
        scenario_key: "parallel_rate_up_10bp",
        category: "rate",
        label: "利率平行上行 10bp",
        source_field: "regulatory_dv01",
        shock: bp(10),
        estimated_impact: yuan(-1_200_000, "-1,200,000.00"),
        measure: "estimated_pnl_impact",
        calculation: "-regulatory_dv01 * shock_bp",
        interpretation: "利率上行时，按监管口径 DV01 估算组合价格影响。",
        data_status: "available",
        human_review_required: true,
      },
      {
        scenario_key: "credit_spread_up_10bp",
        category: "credit",
        label: "信用利差走阔 10bp",
        source_field: "cs01",
        shock: bp(10),
        estimated_impact: yuan(-180_000, "-180,000.00"),
        measure: "estimated_pnl_impact",
        calculation: "-cs01 * shock_bp",
        interpretation: "信用利差走阔时，按 CS01 估算信用敏感性影响。",
        data_status: "available",
        human_review_required: true,
      },
      {
        scenario_key: "liquidity_30d_cashflow_10pct",
        category: "liquidity",
        label: "30天现金流压力 10%",
        source_field: "asset_cashflow_30d/liability_cashflow_30d/liquidity_gap_30d",
        shock: pct(0.1),
        estimated_impact: yuan(-50_000_000, "-50,000,000.00"),
        measure: "stressed_30d_liquidity_gap_delta",
        calculation:
          "asset_cashflow_30d * (1 - shock_pct) - liability_cashflow_30d * (1 + shock_pct) - liquidity_gap_30d",
        interpretation: "现金流压力下的30天流动性缺口变化；负值表示缓冲收窄。",
        data_status: "available",
        human_review_required: true,
        baseline_value: yuan(100_000_000, "100,000,000.00"),
        stressed_value: yuan(50_000_000, "50,000,000.00"),
        baseline_ratio: pct(0.05),
        stressed_ratio: pct(0.025),
      },
      {
        scenario_key: "fx_usdcny_move_candidate",
        category: "fx",
        label: "汇率波动情景",
        source_field: "fx_exposure",
        shock: pct(null),
        estimated_impact: yuan(null),
        measure: "estimated_pnl_impact",
        calculation: "fx_exposure * fx_shock",
        interpretation: "当前风险张量未提供汇率敞口，需接入 FX exposure 后再估算。",
        data_status: "source_missing",
        human_review_required: true,
      },
    ],
    warnings: ["情景压力结果为基于正式风险张量的敏感性覆盖层，不是正式损益、正式限额判定或交易建议。"],
    source_warnings: [],
  };
}

function renderRiskTensorRoute(
  initialEntry: string,
  client: ReturnType<typeof createApiClient>,
  setupQueryClient?: (queryClient: QueryClient) => void,
) {
  const router = createWorkbenchMemoryRouter([initialEntry]);
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
    },
  });
  setupQueryClient?.(queryClient);

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

  it("renders scenario-basis stress tests from the selected risk tensor date", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_stress_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_stress_${reportDate}`),
      result: tensorResult(reportDate),
    }));
    const getRiskScenarioStress = vi.fn(async (reportDate: string) => ({
      result_meta: buildScenarioMeta("risk.tensor.scenario_stress", `tr_scenario_stress_${reportDate}`),
      result: scenarioStressResult(reportDate),
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
      getRiskScenarioStress,
    });

    const panel = await screen.findByTestId("risk-tensor-scenario-stress");
    expect(getRiskScenarioStress).toHaveBeenCalledWith("2026-02-28");
    expect(panel).toHaveTextContent("多情景压力测试");
    expect(panel).toHaveTextContent("利率平行上行 10bp");
    expect(panel).toHaveTextContent("信用利差走阔 10bp");
    expect(panel).toHaveTextContent("30天现金流压力 10%");
    expect(panel).toHaveTextContent("汇率波动情景");
    expect(panel).toHaveTextContent("human_review_required=true");
    expect(panel).toHaveTextContent("scenario_set_id standard_risk_tensor_scenario_v1");
    expect(await screen.findByTestId("risk-tensor-result-meta-panel")).toHaveTextContent("tr_scenario_stress_2026-02-28");
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

  it("renders projection quality disclosures separately from duration exclusions", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_projection_quality_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_projection_quality_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        duration_excluded_market_value: "100000000",
        duration_excluded_count: 2,
        missing_maturity_market_value: "30000000",
        missing_maturity_count: 3,
        floating_rate_proxy_market_value: "50000000",
        floating_rate_proxy_count: 5,
        payment_frequency_fallback_market_value: "70000000",
        payment_frequency_fallback_count: 7,
        bullet_value_date_fallback_market_value: "90000000",
        bullet_value_date_fallback_count: 9,
        projection_quality_status: "available",
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const projectionQuality = await screen.findByTestId("risk-tensor-projection-quality");
    const durationScope = await screen.findByTestId("risk-tensor-duration-scope");

    expect(projectionQuality).toHaveTextContent("可用");
    expect(projectionQuality).toHaveTextContent(new RegExp(`0\\.30\\s*${YI_YUAN_UNIT}`));
    expect(projectionQuality).toHaveTextContent("3 笔");
    expect(projectionQuality).toHaveTextContent(new RegExp(`0\\.50\\s*${YI_YUAN_UNIT}`));
    expect(projectionQuality).toHaveTextContent("5 笔");
    expect(projectionQuality).toHaveTextContent(new RegExp(`0\\.70\\s*${YI_YUAN_UNIT}`));
    expect(projectionQuality).toHaveTextContent("7 笔");
    expect(projectionQuality).toHaveTextContent(new RegExp(`0\\.90\\s*${YI_YUAN_UNIT}`));
    expect(projectionQuality).toHaveTextContent("9 笔");
    expect(projectionQuality).not.toHaveTextContent("1.00");
    expect(durationScope).toHaveTextContent(new RegExp(`1\\.00\\s*${YI_YUAN_UNIT}`));
    expect(durationScope).toHaveTextContent("排除行数 2");
  });

  it("shows unavailable projection quality placeholders for legacy payloads without optional fields", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_projection_quality_legacy_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => {
      const {
        missing_maturity_market_value: _missingMaturityMarketValue,
        missing_maturity_count: _missingMaturityCount,
        floating_rate_proxy_market_value: _floatingRateProxyMarketValue,
        floating_rate_proxy_count: _floatingRateProxyCount,
        payment_frequency_fallback_market_value: _paymentFrequencyFallbackMarketValue,
        payment_frequency_fallback_count: _paymentFrequencyFallbackCount,
        bullet_value_date_fallback_market_value: _bulletValueDateFallbackMarketValue,
        bullet_value_date_fallback_count: _bulletValueDateFallbackCount,
        projection_quality_status: _projectionQualityStatus,
        ...legacyPayload
      } = tensorResult(reportDate);
      return {
        result_meta: buildMeta("risk.tensor", `tr_tensor_projection_quality_legacy_${reportDate}`),
        result: legacyPayload,
      };
    });

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const projectionQuality = await screen.findByTestId("risk-tensor-projection-quality");
    expect(projectionQuality).toHaveTextContent("不可用/待重算");
    expect(projectionQuality).toHaveTextContent("笔数不可用");
    expect(projectionQuality).not.toHaveTextContent(new RegExp(`0\\.00\\s*${YI_YUAN_UNIT}`));
    expect(projectionQuality).not.toHaveTextContent("0 笔");
  });

  it("surfaces explicit unavailable_legacy projection status from the payload", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_projection_quality_unavailable_legacy_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_projection_quality_unavailable_legacy_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        missing_maturity_market_value: null,
        missing_maturity_count: null,
        floating_rate_proxy_market_value: null,
        floating_rate_proxy_count: null,
        payment_frequency_fallback_market_value: null,
        payment_frequency_fallback_count: null,
        bullet_value_date_fallback_market_value: null,
        bullet_value_date_fallback_count: null,
        projection_quality_status: "unavailable_legacy",
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const projectionQuality = await screen.findByTestId("risk-tensor-projection-quality");
    expect(projectionQuality).toHaveTextContent("历史版本未提供投影质量字段/待重算");
    expect(projectionQuality).toHaveTextContent("不可用/待重算");
    expect(projectionQuality).toHaveTextContent("笔数不可用");
    expect(projectionQuality).not.toHaveTextContent(new RegExp(`0\\.00\\s*${YI_YUAN_UNIT}`));
    expect(projectionQuality).not.toHaveTextContent("0 笔");
  });

  it("uses latest available report date when querystring is absent", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates"),
      result: { report_dates: ["2026-02-28", "2026-01-31"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: {
        ...buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
        rule_version: "rv_risk_tensor_formal_materialize_v5",
        cache_version: "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v5",
      },
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
    expect(brief).toHaveTextContent("1 条需核对");
    expect(brief).not.toHaveTextContent("控制项未接入");
    expect(brief).not.toHaveTextContent("上期变化载荷");
    expect(kpi).toHaveTextContent(new RegExp(`0\\.00\\s*${WAN_YUAN_UNIT}`));
    expect(kpi).toHaveTextContent("监管口径 DV01");
    expect(kpi).toHaveTextContent("待接入");
    expect(kpi).toHaveTextContent(new RegExp(`0\\.00\\s*${WAN_YUAN_UNIT}`));
    expect(screen.getByTestId("risk-tensor-issuer-concentration-detail")).toHaveTextContent("发行人集中度");
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
    expect(screen.queryByTestId("risk-tensor-prior-period-change")).not.toBeInTheDocument();
    expect(screen.queryByTestId("risk-tensor-dv01-controls")).not.toBeInTheDocument();
    const scenarioPanel = await screen.findByTestId("risk-tensor-scenario-stress");
    expect(scenarioPanel).toBeVisible();
    await waitFor(() => {
      expect(scenarioPanel).toHaveTextContent("利率平行上行 10bp");
      expect(scenarioPanel).toHaveTextContent("liquidity_30d_cashflow_10pct");
    });
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

  it("summarizes hidden warnings in the first-screen risk judgement", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_many_warnings_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_many_warnings_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        warnings: [
          "估值曲线 vendor stale",
          "回售权现金流未进入 formal 张量",
          "部分到期日缺失，已从久期分母排除",
        ],
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const brief = await screen.findByTestId("risk-tensor-brief");
    expect(brief).toHaveTextContent("估值曲线 vendor stale");
    expect(brief).toHaveTextContent("回售权现金流未进入 formal 张量");
    expect(brief).toHaveTextContent("另有 1 条预警见下方质量明细");
    expect(within(brief).queryByText("部分到期日缺失，已从久期分母排除")).not.toBeInTheDocument();
    expect(screen.getByText("部分到期日缺失，已从久期分母排除")).toBeInTheDocument();
  });

  it("lets users jump from first-screen warnings to the full quality detail", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_warning_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const hiddenWarning = "部分到期日缺失，已从久期分母排除";
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_warning_jump_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          warnings: ["估值曲线 vendor stale", "回售权现金流未进入 formal 张量", hiddenWarning],
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      const jumpAction = within(brief).getByTestId("risk-tensor-quality-detail-action");
      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");
      expect(within(brief).queryByText(hiddenWarning)).not.toBeInTheDocument();
      expect(qualityDetail).toHaveTextContent(hiddenWarning);

      await user.click(jumpAction);

      expect(scrollTargets).toContain(qualityDetail);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("copies the full quality warning list from quality detail", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_warning_copy_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const hiddenWarning = "部分到期日缺失，已从久期分母排除";
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_warning_copy_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          warnings: ["估值曲线 vendor stale", "回售权现金流未进入 formal 张量", hiddenWarning],
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");

      await user.click(within(qualityDetail).getByRole("button", { name: "复制预警清单" }));

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量质量预警清单"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("trace_id tr_tensor_warning_copy_2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("报告日 2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("warning[1] 估值曲线 vendor stale"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining(`warning[3] ${hiddenWarning}`));
      await waitFor(() => {
        expect(qualityDetail).toHaveTextContent("已复制预警清单");
      });
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      }
    }
  });

  it("ignores stale quality warning copy results after report date changes", async () => {
    const user = userEvent.setup();
    let resolveCopy: (() => void) | undefined;
    const writeText = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveCopy = resolve;
        }),
    );
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_warning_stale_copy_dates"),
        result: { report_dates: ["2026-02-28", "2026-01-31"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_warning_stale_copy_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          warnings:
            reportDate === "2026-01-31"
              ? ["刷新后预警需要单独复制"]
              : ["估值曲线 vendor stale", "回售权现金流未进入 formal 张量"],
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");
      await user.click(within(qualityDetail).getByRole("button", { name: "复制预警清单" }));
      await user.selectOptions(screen.getByLabelText("风险报告日"), "2026-01-31");

      const refreshedQualityDetail = await screen.findByTestId("risk-tensor-quality-detail");
      await waitFor(() => {
        expect(refreshedQualityDetail).toHaveTextContent("刷新后预警需要单独复制");
      });

      await act(async () => {
        resolveCopy?.();
      });

      expect(refreshedQualityDetail).not.toHaveTextContent("已复制预警清单");
      expect(
        within(refreshedQualityDetail).queryByTestId("risk-tensor-quality-warnings-manual-copy"),
      ).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("shows manual warning list text when quality warning copying fails", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => {
      throw new Error("clipboard unavailable");
    });
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_warning_copy_failure_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_warning_copy_failure_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          warnings: ["估值曲线 vendor stale", "回售权现金流未进入 formal 张量"],
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");

      await user.click(within(qualityDetail).getByRole("button", { name: "复制预警清单" }));

      await waitFor(() => {
        expect(qualityDetail).toHaveTextContent("复制失败，请手动选择预警清单");
      });
      const manualCopy = within(qualityDetail).getByTestId("risk-tensor-quality-warnings-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量质量预警清单");
      expect(manualCopy).toHaveTextContent("trace_id tr_tensor_warning_copy_failure_2026-02-28");
      expect(manualCopy).toHaveTextContent("warning[2] 回售权现金流未进入 formal 张量");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      }
    }
  });

  it("exposes the selected KRD tenor chip to assistive technology", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_tenor_a11y_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_tenor_a11y_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const drill = await screen.findByTestId("risk-tensor-tenor-drill");
    const fiveYear = within(drill).getByRole("button", { name: "5Y" });
    const oneYear = within(drill).getByRole("button", { name: "1Y" });

    await waitFor(() => {
      expect(fiveYear).toHaveAttribute("aria-pressed", "true");
      expect(oneYear).toHaveAttribute("aria-pressed", "false");
    });

    await user.click(oneYear);

    await waitFor(() => {
      expect(oneYear).toHaveAttribute("aria-pressed", "true");
      expect(fiveYear).toHaveAttribute("aria-pressed", "false");
      expect(drill).toHaveTextContent("当前桶：1Y");
    });
  });

  it("keeps the primary risk bucket stable and lets users return to it from the first-screen tile", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_primary_bucket_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_primary_bucket_${reportDate}`),
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      const drill = await screen.findByTestId("risk-tensor-tenor-drill");
      const primaryBucketAction = within(brief).getByTestId("risk-tensor-primary-tenor-action");
      const fiveYear = within(drill).getByRole("button", { name: "5Y" });
      const oneYear = within(drill).getByRole("button", { name: "1Y" });

      expect(primaryBucketAction).toHaveTextContent("5Y");
      await waitFor(() => {
        expect(fiveYear).toHaveAttribute("aria-pressed", "true");
      });

      await user.click(oneYear);

      await waitFor(() => {
        expect(oneYear).toHaveAttribute("aria-pressed", "true");
        expect(fiveYear).toHaveAttribute("aria-pressed", "false");
        expect(primaryBucketAction).toHaveTextContent("5Y");
      });

      await user.click(primaryBucketAction);

      await waitFor(() => {
        expect(fiveYear).toHaveAttribute("aria-pressed", "true");
        expect(oneYear).toHaveAttribute("aria-pressed", "false");
      });
      expect(scrollTargets).toContain(drill);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users jump from the first-screen liquidity tile to liquidity gap detail", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_liquidity_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_liquidity_jump_${reportDate}`),
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      const liquidityAction = within(brief).getByTestId("risk-tensor-liquidity-action");
      const liquidityGapDetail = await screen.findByTestId("risk-tensor-liquidity-gap-detail");

      await user.click(liquidityAction);

      expect(scrollTargets).toContain(liquidityGapDetail);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users jump from the first-screen data status tile to quality detail", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_data_status_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_data_status_jump_${reportDate}`),
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      const dataStatusAction = within(brief).getByTestId("risk-tensor-data-status-action");
      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");
      expect(within(brief).queryByTestId("risk-tensor-quality-review-action")).not.toBeInTheDocument();

      await user.click(dataStatusAction);

      expect(scrollTargets).toContain(qualityDetail);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it.each([
    ["stale", "陈旧"],
    ["error", "错误"],
  ])("flags %s first-screen conclusions for quality review", async (qualityFlag, qualityLabel) => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", `tr_tensor_${qualityFlag}_review_dates`),
        result: {
          report_dates: ["2026-02-28"],
          blocked_report_dates: [
            {
              report_date: "2026-02-27",
              reason: "risk tensor source lineage is stale",
            },
          ],
        },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", `tr_tensor_${qualityFlag}_review_${reportDate}`),
          fallback_mode: "latest_snapshot" as const,
          fallback_date: "2026-02-27",
          quality_flag: qualityFlag as ResultMeta["quality_flag"],
        },
        result: {
          ...tensorResult(reportDate),
          quality_flag: qualityFlag,
          warnings: ["估值曲线 vendor stale"],
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      const reviewAction = within(brief).getByTestId("risk-tensor-quality-review-action");
      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");
      const tracePriority = within(qualityDetail).getByTestId("risk-tensor-quality-trace-priority");

      expect(reviewAction).toHaveTextContent("结论需复核");
      expect(reviewAction).toHaveTextContent(qualityLabel);
      expect(reviewAction).toHaveTextContent("fallback_date 2026-02-27");
      expect(reviewAction).toHaveTextContent("1 个陈旧日期已拦截");
      expect(reviewAction).toHaveTextContent("估值曲线 vendor stale");
      expect(tracePriority).toHaveTextContent("证据优先级");
      expect(tracePriority).toHaveTextContent("source/rule");
      expect(tracePriority).toHaveTextContent("sv_tensor_test");
      expect(tracePriority).toHaveTextContent("rv_tensor_test");
      expect(tracePriority).toHaveTextContent("fallback");
      expect(tracePriority).toHaveTextContent("latest snapshot fallback");
      expect(tracePriority).toHaveTextContent("fallback_date 2026-02-27");
      expect(tracePriority).toHaveTextContent("陈旧日期");
      expect(tracePriority).toHaveTextContent("risk tensor source lineage is stale");
      expect(tracePriority).toHaveTextContent("warning");
      expect(tracePriority).toHaveTextContent("估值曲线 vendor stale");

      await user.click(reviewAction);

      expect(scrollTargets).toContain(qualityDetail);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("connects first-screen fallback status to quality evidence", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_fallback_status_dates"),
        result: {
          report_dates: ["2026-02-28"],
          blocked_report_dates: [
            {
              report_date: "2026-02-27",
              reason: "risk tensor source lineage is stale",
            },
          ],
        },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", `tr_tensor_fallback_status_${reportDate}`),
          fallback_mode: "latest_snapshot" as const,
          fallback_date: "2026-02-27",
          source_version: "sv_tensor_fallback",
          rule_version: "rv_tensor_fallback",
        },
        result: {
          ...tensorResult(reportDate),
          quality_flag: "stale",
          warnings: [],
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      const dataStatusAction = within(brief).getByTestId("risk-tensor-data-status-action");
      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");

      expect(dataStatusAction).toHaveTextContent("latest snapshot fallback");
      expect(dataStatusAction).toHaveTextContent("1 个陈旧日期已拦截");
      expect(qualityDetail).toHaveTextContent("latest snapshot fallback");
      expect(qualityDetail).toHaveTextContent("fallback_date 2026-02-27");
      expect(qualityDetail).toHaveTextContent("sv_tensor_fallback");
      expect(qualityDetail).toHaveTextContent("rv_tensor_fallback");
      expect(qualityDetail).toHaveTextContent("2026-02-27");
      expect(qualityDetail).toHaveTextContent("risk tensor source lineage is stale");

      await user.click(dataStatusAction);

      expect(scrollTargets).toContain(qualityDetail);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("surfaces backend tables, filters, and evidence rows in quality evidence", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_meta_evidence_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: {
        ...buildMeta("risk.tensor", `tr_tensor_meta_evidence_${reportDate}`),
        evidence_rows: 128,
        tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
        filters_applied: {
          report_date: "2026-02-28",
          desk: "FI",
        },
      },
      result: tensorResult(reportDate),
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");
    const tracePriority = within(qualityDetail).getByTestId("risk-tensor-quality-trace-priority");

    expect(qualityDetail).toHaveTextContent("evidence_rows 128");
    expect(qualityDetail).toHaveTextContent("trace_id tr_tensor_meta_evidence_2026-02-28");
    expect(qualityDetail).toHaveTextContent("risk_tensor_daily");
    expect(qualityDetail).toHaveTextContent("bond_position_snapshot");
    expect(qualityDetail).toHaveTextContent("report_date=2026-02-28");
    expect(qualityDetail).toHaveTextContent("desk=FI");
    expect(tracePriority).toHaveTextContent("证据范围");
    expect(tracePriority).toHaveTextContent("evidence_rows 128");
    expect(tracePriority).toHaveTextContent("trace_id tr_tensor_meta_evidence_2026-02-28");
    expect(tracePriority).toHaveTextContent("tables_used risk_tensor_daily / bond_position_snapshot");
    expect(tracePriority).toHaveTextContent("filters_applied report_date=2026-02-28；desk=FI");
    expect(tracePriority).toHaveTextContent("证据字段复核");
    expect(tracePriority).toHaveTextContent("evidence_rows 已提供");
    expect(tracePriority).toHaveTextContent("tables_used 已提供");
    expect(tracePriority).toHaveTextContent("filters_applied 已提供");
  });

  it("jumps from quality evidence scope to result metadata panel", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_meta_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", `tr_tensor_meta_jump_${reportDate}`),
          evidence_rows: 128,
          tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
          filters_applied: {
            report_date: "2026-02-28",
            desk: "FI",
          },
        },
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");
      const tracePriority = within(qualityDetail).getByTestId("risk-tensor-quality-trace-priority");
      const metaPanel = await screen.findByTestId("risk-tensor-result-meta-panel");
      const metadataJump = within(tracePriority).getByRole("button", { name: "定位元数据" });

      await user.click(metadataJump);

      expect(scrollTargets).toContain(metaPanel);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("copies quality evidence scope for audit review", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_meta_copy_dates"),
        result: { report_dates: ["2026-02-28", "2026-01-31"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", `tr_tensor_meta_copy_${reportDate}`),
          evidence_rows: reportDate === "2026-01-31" ? 96 : 128,
          tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
          filters_applied: {
            report_date: reportDate,
            desk: "FI",
          },
        },
        result: {
          ...tensorResult(reportDate),
          warnings: ["Issuer concentration above desk threshold", "Liquidity stress input requires desk signoff"],
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");
      const tracePriority = within(qualityDetail).getByTestId("risk-tensor-quality-trace-priority");
      const copyEvidence = within(tracePriority).getByRole("button", { name: "复制证据" });

      expect(tracePriority).toHaveTextContent("复核状态：待复核");
      expect(within(tracePriority).queryByRole("button", { name: "确认业务复核" })).not.toBeInTheDocument();
      expect(qualityDetail).toHaveTextContent("basis formal");
      expect(qualityDetail).toHaveTextContent("cache_version cv_tensor_test");
      expect(qualityDetail).toHaveTextContent("generated_at 2026-04-12T08:00:00Z");

      await user.click(copyEvidence);

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("trace_id tr_tensor_meta_copy_2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("报告日 2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("复核状态 待复核"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("source_version sv_tensor_test"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("rule_version rv_tensor_test"));
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("warning Issuer concentration above desk threshold / Liquidity stress input requires desk signoff"),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("evidence_rows 128"));
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("tables_used risk_tensor_daily / bond_position_snapshot"),
      );
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("filters_applied report_date=2026-02-28；desk=FI"),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("证据字段复核"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("evidence_rows 已提供"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("tables_used 已提供"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("filters_applied 已提供"));
      expect(tracePriority).toHaveTextContent("已复制证据摘要");
      expect(tracePriority).toHaveTextContent("复核状态：证据已复制，待业务确认");

      const confirmReview = within(tracePriority).getByRole("button", { name: "确认业务复核" });
      await user.click(confirmReview);

      expect(tracePriority).toHaveTextContent("复核状态：业务已确认");
      const copyReviewRecord = within(tracePriority).getByRole("button", { name: "复制确认记录" });

      await user.click(copyEvidence);

      expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining("复核状态 业务已确认"));

      await user.click(copyReviewRecord);

      expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining("风险张量质量证据确认记录"));
      expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining("trace_id tr_tensor_meta_copy_2026-02-28"));
      expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining("报告日 2026-02-28"));
      expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining("确认状态 业务已确认"));
      expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining("quality_flag warning"));
      expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining("fallback 未降级"));
      expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining("陈旧日期 0 个陈旧日期已拦截"));
      expect(writeText).toHaveBeenLastCalledWith(
        expect.stringContaining("warning Issuer concentration above desk threshold / Liquidity stress input requires desk signoff"),
      );
      expect(writeText).toHaveBeenLastCalledWith(
        expect.stringContaining("证据范围 trace_id tr_tensor_meta_copy_2026-02-28；evidence_rows 128"),
      );
      expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining("证据字段复核"));
      expect(tracePriority).toHaveTextContent("已复制确认记录");

      const reportDateSelect = screen.getByLabelText("风险报告日");
      await user.selectOptions(reportDateSelect, "2026-01-31");

      const nextTracePriority = within(await screen.findByTestId("risk-tensor-quality-detail")).getByTestId(
        "risk-tensor-quality-trace-priority",
      );
      await waitFor(() => {
        expect(nextTracePriority).toHaveTextContent("evidence_rows 96");
      });
      expect(nextTracePriority).toHaveTextContent("复核状态：待复核");
      expect(nextTracePriority).not.toHaveTextContent("已复制证据摘要");
      expect(nextTracePriority).not.toHaveTextContent("已复制确认记录");
      expect(within(nextTracePriority).queryByRole("button", { name: "确认业务复核" })).not.toBeInTheDocument();
      expect(within(nextTracePriority).queryByRole("button", { name: "复制确认记录" })).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("resets quality review state when report date changes even if trace id is reused", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_reused_trace_dates"),
        result: { report_dates: ["2026-02-28", "2026-01-31"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", "tr_tensor_reused_trace"),
          requested_report_date: reportDate,
          resolved_report_date: reportDate,
          evidence_rows: reportDate === "2026-01-31" ? 96 : 128,
          tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
          filters_applied: {
            report_date: reportDate,
            desk: "FI",
          },
        },
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const tracePriority = within(await screen.findByTestId("risk-tensor-quality-detail")).getByTestId(
        "risk-tensor-quality-trace-priority",
      );
      await user.click(within(tracePriority).getByRole("button", { name: "复制证据" }));
      await user.click(await within(tracePriority).findByRole("button", { name: "确认业务复核" }));

      expect(tracePriority).toHaveTextContent("复核状态：业务已确认");
      expect(within(tracePriority).getByRole("button", { name: "复制确认记录" })).toBeInTheDocument();

      await user.selectOptions(screen.getByLabelText("风险报告日"), "2026-01-31");

      const nextTracePriority = within(await screen.findByTestId("risk-tensor-quality-detail")).getByTestId(
        "risk-tensor-quality-trace-priority",
      );
      await waitFor(() => {
        expect(nextTracePriority).toHaveTextContent("evidence_rows 96");
      });
      expect(nextTracePriority).toHaveTextContent("复核状态：待复核");
      expect(nextTracePriority).not.toHaveTextContent("已复制证据摘要");
      expect(nextTracePriority).not.toHaveTextContent("业务已确认");
      expect(within(nextTracePriority).queryByRole("button", { name: "确认业务复核" })).not.toBeInTheDocument();
      expect(within(nextTracePriority).queryByRole("button", { name: "复制确认记录" })).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("ignores stale quality evidence review record copy results after report date changes", async () => {
    const user = userEvent.setup();
    let resolveReviewRecordCopy: (() => void) | undefined;
    const writeText = vi
      .fn()
      .mockResolvedValueOnce(undefined)
      .mockImplementationOnce(
        () =>
          new Promise<void>((resolve) => {
            resolveReviewRecordCopy = resolve;
          }),
      )
      .mockResolvedValueOnce(undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_review_record_stale_copy_dates"),
        result: { report_dates: ["2026-02-28", "2026-01-31"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", `tr_tensor_review_record_stale_copy_${reportDate}`),
          evidence_rows: reportDate === "2026-01-31" ? 96 : 128,
          tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
          filters_applied: {
            report_date: reportDate,
            desk: "FI",
          },
        },
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const tracePriority = within(await screen.findByTestId("risk-tensor-quality-detail")).getByTestId(
        "risk-tensor-quality-trace-priority",
      );
      await user.click(within(tracePriority).getByRole("button", { name: "复制证据" }));
      await user.click(await within(tracePriority).findByRole("button", { name: "确认业务复核" }));
      await user.click(within(tracePriority).getByRole("button", { name: "复制确认记录" }));
      await user.selectOptions(screen.getByLabelText("风险报告日"), "2026-01-31");

      const nextTracePriority = within(await screen.findByTestId("risk-tensor-quality-detail")).getByTestId(
        "risk-tensor-quality-trace-priority",
      );
      await waitFor(() => {
        expect(nextTracePriority).toHaveTextContent("evidence_rows 96");
      });

      await act(async () => {
        resolveReviewRecordCopy?.();
      });

      await user.click(within(nextTracePriority).getByRole("button", { name: "复制证据" }));
      await user.click(await within(nextTracePriority).findByRole("button", { name: "确认业务复核" }));

      expect(nextTracePriority).toHaveTextContent("复核状态：业务已确认");
      expect(nextTracePriority).not.toHaveTextContent("已复制确认记录");
      expect(
        within(nextTracePriority).queryByTestId("risk-tensor-quality-evidence-review-record-manual-copy"),
      ).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("ignores stale quality evidence copy results after report date changes", async () => {
    const user = userEvent.setup();
    let resolveCopy: (() => void) | undefined;
    const writeText = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveCopy = resolve;
        }),
    );
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_stale_quality_copy_dates"),
        result: { report_dates: ["2026-02-28", "2026-01-31"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", "tr_tensor_stale_quality_copy"),
          requested_report_date: reportDate,
          resolved_report_date: reportDate,
          evidence_rows: reportDate === "2026-01-31" ? 96 : 128,
          tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
          filters_applied: {
            report_date: reportDate,
            desk: "FI",
          },
        },
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const tracePriority = within(await screen.findByTestId("risk-tensor-quality-detail")).getByTestId(
        "risk-tensor-quality-trace-priority",
      );
      await user.click(within(tracePriority).getByRole("button", { name: "复制证据" }));
      await user.selectOptions(screen.getByLabelText("风险报告日"), "2026-01-31");

      const nextTracePriority = within(await screen.findByTestId("risk-tensor-quality-detail")).getByTestId(
        "risk-tensor-quality-trace-priority",
      );
      await waitFor(() => {
        expect(nextTracePriority).toHaveTextContent("evidence_rows 96");
      });

      await act(async () => {
        resolveCopy?.();
      });

      expect(nextTracePriority).toHaveTextContent("复核状态：待复核");
      expect(nextTracePriority).not.toHaveTextContent("已复制证据摘要");
      expect(within(nextTracePriority).queryByRole("button", { name: "确认业务复核" })).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("shows manual quality evidence text when clipboard copy fails", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => {
      throw new Error("clipboard denied");
    });
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_meta_copy_failure_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", `tr_tensor_meta_copy_failure_${reportDate}`),
          evidence_rows: 128,
          tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
          filters_applied: {
            report_date: reportDate,
            desk: "FI",
          },
        },
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");
      const tracePriority = within(qualityDetail).getByTestId("risk-tensor-quality-trace-priority");
      await user.click(within(tracePriority).getByRole("button", { name: "复制证据" }));

      await waitFor(() => {
        expect(tracePriority).toHaveTextContent("复制失败，请手动选择证据");
      });

      const manualCopy = within(tracePriority).getByTestId("risk-tensor-quality-evidence-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量质量证据");
      expect(manualCopy).toHaveTextContent("trace_id tr_tensor_meta_copy_failure_2026-02-28");
      expect(manualCopy).toHaveTextContent("报告日 2026-02-28");
      expect(manualCopy).toHaveTextContent(
        "证据范围 trace_id tr_tensor_meta_copy_failure_2026-02-28；evidence_rows 128",
      );
      expect(manualCopy).toHaveTextContent("tables_used risk_tensor_daily / bond_position_snapshot");
      expect(manualCopy).toHaveTextContent("filters_applied report_date=2026-02-28；desk=FI");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("explicitly marks missing backend evidence fields in quality evidence", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_missing_meta_evidence_dates"),
      result: { report_dates: ["2026-02-28", "2026-01-31"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_missing_meta_evidence_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    try {
      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");
      const tracePriority = within(qualityDetail).getByTestId("risk-tensor-quality-trace-priority");

      expect(qualityDetail).toHaveTextContent("evidence_rows 未提供");
      expect(qualityDetail).toHaveTextContent("tables_used 未提供");
      expect(qualityDetail).toHaveTextContent("filters_applied 未提供");
      expect(tracePriority).toHaveTextContent("证据范围");
      expect(tracePriority).toHaveTextContent("evidence_rows 未提供");
      expect(tracePriority).toHaveTextContent("tables_used 未提供");
      expect(tracePriority).toHaveTextContent("filters_applied 未提供");
      expect(tracePriority).toHaveTextContent("证据字段复核");
      expect(tracePriority).toHaveTextContent("evidence_rows 未提供");
      expect(tracePriority).toHaveTextContent("tables_used 未提供");
      expect(tracePriority).toHaveTextContent("filters_applied 未提供");
      expect(tracePriority).toHaveTextContent("复核状态：证据不完整，待补证");
      expect(within(tracePriority).queryByRole("button", { name: "确认业务复核" })).not.toBeInTheDocument();
      expect(within(tracePriority).queryByRole("button", { name: "复制确认记录" })).not.toBeInTheDocument();

      const copyRequest = within(tracePriority).getByRole("button", { name: "复制补证请求" });
      await user.click(copyRequest);

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量质量证据补证请求"));
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("trace_id tr_tensor_missing_meta_evidence_2026-02-28"),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("报告日 2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("basis formal"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("cache_version cv_tensor_test"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("generated_at 2026-04-12T08:00:00Z"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("缺失字段 evidence_rows / tables_used / filters_applied"));
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("请在 result_meta 补充 evidence_rows、tables_used、filters_applied 后重新出具"),
      );
      expect(tracePriority).toHaveTextContent("已复制补证请求");

      const reportDateSelect = screen.getByLabelText("风险报告日");
      await user.selectOptions(reportDateSelect, "2026-01-31");

      await waitFor(() => {
        expect(getRiskTensor).toHaveBeenCalledWith("2026-01-31");
      });
      const nextTracePriority = within(await screen.findByTestId("risk-tensor-quality-detail")).getByTestId(
        "risk-tensor-quality-trace-priority",
      );
      expect(nextTracePriority).toHaveTextContent("复核状态：证据不完整，待补证");
      expect(nextTracePriority).toHaveTextContent("evidence_rows 未提供");
      expect(nextTracePriority).not.toHaveTextContent("已复制补证请求");
      expect(within(nextTracePriority).queryByRole("button", { name: "确认业务复核" })).not.toBeInTheDocument();
      expect(within(nextTracePriority).queryByRole("button", { name: "复制确认记录" })).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("shows manual supplement request text when clipboard copy fails", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => {
      throw new Error("clipboard denied");
    });
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_missing_request_failure_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_missing_request_failure_${reportDate}`),
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");
      const tracePriority = within(qualityDetail).getByTestId("risk-tensor-quality-trace-priority");
      await user.click(within(tracePriority).getByRole("button", { name: "复制补证请求" }));

      await waitFor(() => {
        expect(tracePriority).toHaveTextContent("复制失败，请手动选择补证请求");
      });

      const manualCopy = within(tracePriority).getByTestId("risk-tensor-quality-evidence-request-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量质量证据补证请求");
      expect(manualCopy).toHaveTextContent("trace_id tr_tensor_missing_request_failure_2026-02-28");
      expect(manualCopy).toHaveTextContent("报告日 2026-02-28");
      expect(manualCopy).toHaveTextContent("缺失字段 evidence_rows / tables_used / filters_applied");
      expect(manualCopy).toHaveTextContent(
        "请在 result_meta 补充 evidence_rows、tables_used、filters_applied 后重新出具",
      );
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("shows manual review record text when confirmation copy fails", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => {
      throw new Error("clipboard denied");
    });
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_review_record_failure_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", `tr_tensor_review_record_failure_${reportDate}`),
          evidence_rows: 128,
          tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
          filters_applied: {
            report_date: reportDate,
            desk: "FI",
          },
        },
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");
      const tracePriority = within(qualityDetail).getByTestId("risk-tensor-quality-trace-priority");
      await user.click(within(tracePriority).getByRole("button", { name: "复制证据" }));

      await waitFor(() => {
        expect(tracePriority).toHaveTextContent("复制失败，请手动选择证据");
      });

      expect(within(tracePriority).queryByRole("button", { name: "确认业务复核" })).not.toBeInTheDocument();

      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: { writeText: vi.fn(async () => undefined) },
      });
      await user.click(within(tracePriority).getByRole("button", { name: "复制证据" }));
      const confirmReview = await within(tracePriority).findByRole("button", { name: "确认业务复核" });
      await user.click(confirmReview);

      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: { writeText },
      });
      await user.click(within(tracePriority).getByRole("button", { name: "复制确认记录" }));

      await waitFor(() => {
        expect(tracePriority).toHaveTextContent("复制失败，请手动选择确认记录");
      });

      const manualCopy = within(tracePriority).getByTestId("risk-tensor-quality-evidence-review-record-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量质量证据确认记录");
      expect(manualCopy).toHaveTextContent("trace_id tr_tensor_review_record_failure_2026-02-28");
      expect(manualCopy).toHaveTextContent("报告日 2026-02-28");
      expect(manualCopy).toHaveTextContent("确认状态 业务已确认");
      expect(manualCopy).toHaveTextContent(
        "证据范围 trace_id tr_tensor_review_record_failure_2026-02-28；evidence_rows 128",
      );
      expect(manualCopy).toHaveTextContent("证据字段复核");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("surfaces issuer concentration detail from backend fields", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_issuer_detail_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_issuer_detail_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        issuer_top5_weight: "0.42",
        issuer_concentration_hhi: "0.18",
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const issuerDetail = await screen.findByTestId("risk-tensor-issuer-concentration-detail");
    const issuerHhi = within(issuerDetail).getByTestId("risk-tensor-issuer-hhi");
    expect(issuerDetail).toHaveTextContent("发行人集中度");
    expect(issuerDetail).toHaveTextContent("42.0%");
    expect(issuerDetail).toHaveTextContent("0.18");
    expect(issuerDetail).toHaveTextContent("issuer_top5_weight");
    expect(issuerDetail).toHaveTextContent("issuer_concentration_hhi");
    expect(issuerHhi).toHaveAttribute("data-tone", "default");
    expect(within(issuerHhi).getByText("0.18")).toHaveClass("kpi-card__value");
  });

  it("lets users select a tenor from the KRD chart and lands on the tenor drilldown", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_krd_chart_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_krd_chart_jump_${reportDate}`),
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const drill = await screen.findByTestId("risk-tensor-tenor-drill");
      const oneYear = within(drill).getByRole("button", { name: "1Y" });
      const fiveYear = within(drill).getByRole("button", { name: "5Y" });
      const krdChart = screen.getAllByTestId("risk-tensor-echarts-stub")[1]!;

      await waitFor(() => {
        expect(fiveYear).toHaveAttribute("aria-pressed", "true");
      });

      await user.click(krdChart);

      await waitFor(() => {
        expect(oneYear).toHaveAttribute("aria-pressed", "true");
        expect(fiveYear).toHaveAttribute("aria-pressed", "false");
        expect(drill).toHaveTextContent("当前桶：1Y");
      });
      expect(scrollTargets).toContain(drill);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users jump from the radar concentration dimension to issuer detail", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_radar_hhi_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_radar_hhi_jump_${reportDate}`),
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const issuerDetail = await screen.findByTestId("risk-tensor-issuer-concentration-detail");
      const radarAction = await screen.findByTestId("risk-tensor-radar-action-hhi");

      await user.click(radarAction);

      expect(scrollTargets).toContain(issuerDetail);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users jump from the radar CS01 dimension to the CS01 KPI card", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_radar_cs01_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_radar_cs01_jump_${reportDate}`),
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const cs01Card = await screen.findByTestId("risk-tensor-cs01-kpi");
      const radarAction = await screen.findByTestId("risk-tensor-radar-action-cs01");

      await user.click(radarAction);

      expect(scrollTargets).toContain(cs01Card);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users jump from the first-screen issuer concentration tile to issuer detail", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_issuer_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_issuer_jump_${reportDate}`),
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      const issuerAction = within(brief).getByTestId("risk-tensor-issuer-concentration-action");
      const issuerDetail = await screen.findByTestId("risk-tensor-issuer-concentration-detail");

      await user.click(issuerAction);

      expect(scrollTargets).toContain(issuerDetail);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
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

  it("moves a selected KRD tenor back to a valid bucket when the report date payload makes it unparseable", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_tenor_report_date_reset_dates"),
      result: { report_dates: ["2026-02-28", "2026-01-31"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_tenor_report_date_reset_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        ...(reportDate === "2026-01-31"
          ? {
              krd_1y: "bad-krd",
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

    const tenorDrill = await screen.findByTestId("risk-tensor-tenor-drill");
    await user.click(within(tenorDrill).getByRole("button", { name: "1Y" }));

    await waitFor(() => {
      expect(within(tenorDrill).getByText("1Y", { selector: "strong" })).toBeInTheDocument();
    });

    await user.selectOptions(await screen.findByRole("combobox"), "2026-01-31");

    await waitFor(() => {
      expect(getRiskTensor).toHaveBeenCalledWith("2026-01-31");
      expect(
        within(screen.getByTestId("risk-tensor-tenor-drill")).getByText("5Y", { selector: "strong" }),
      ).toBeInTheDocument();
    });
    const updatedTenorDrill = screen.getByTestId("risk-tensor-tenor-drill");
    expect(within(updatedTenorDrill).getByRole("button", { name: "5Y" })).toHaveAttribute("aria-pressed", "true");
    expect(within(updatedTenorDrill).queryByText("1Y", { selector: "strong" })).not.toBeInTheDocument();
    expect(await screen.findByTestId("risk-tensor-krd-quality-note")).toHaveTextContent("krd_1y");
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

  it("flags missing or unparseable main payload fields without frontend recalculation", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_payload_quality_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_payload_quality_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        portfolio_dv01: "",
        liquidity_gap_30d_ratio: "not-a-number",
        krd_5y: {
          raw: Number.NaN,
          unit: "dv01" as const,
          display: "--",
          precision: 2,
          sign_aware: false,
        },
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const warning = await screen.findByTestId("risk-tensor-payload-quality-warning");
    expect(warning).toHaveTextContent("主读 payload 字段待核对");
    expect(warning).toHaveTextContent("trace_id tr_tensor_payload_quality_2026-02-28");
    expect(warning).toHaveTextContent("portfolio_dv01");
    expect(warning).toHaveTextContent("liquidity_gap_30d_ratio");
    expect(warning).toHaveTextContent("krd_5y");
    expect(warning).toHaveTextContent("不会在前端补算正式指标");

    const kpi = await screen.findByTestId("risk-tensor-kpi-grid");
    expect(kpi).toHaveTextContent("估值口径 DV01");
    expect(kpi).toHaveTextContent("—");
    expect(screen.getByTestId("risk-tensor-liquidity-action")).toHaveTextContent("not-a-number");
  });

  it("lets users retry the risk tensor main read from the first-screen payload warning", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_payload_warning_retry_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi
      .fn()
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor", "tr_tensor_payload_warning_retry_initial"),
        result: {
          ...tensorResult("2026-02-28"),
          portfolio_dv01: "",
          liquidity_gap_30d_ratio: "not-a-number",
        },
      })
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor", "tr_tensor_payload_warning_retry_success"),
        result: tensorResult("2026-02-28"),
      });

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const warning = await screen.findByTestId("risk-tensor-payload-quality-warning");
    expect(getRiskTensor).toHaveBeenCalledTimes(1);

    await user.click(within(warning).getByRole("button", { name: "\u91cd\u8bd5\u4e3b\u8bfb\u9762" }));

    await waitFor(() => {
      expect(getRiskTensor).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByTestId("risk-tensor-brief")).toHaveTextContent("\u62a5\u544a\u65e5 2026-02-28");
    expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent(
      "tr_tensor_payload_warning_retry_success",
    );
    expect(screen.queryByTestId("risk-tensor-payload-quality-warning")).not.toBeInTheDocument();
  });

  it("lets users jump from the first-screen payload warning to the payload checklist", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_payload_quality_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_payload_quality_jump_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          portfolio_dv01: "",
          liquidity_gap_30d_ratio: "not-a-number",
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const warning = await screen.findByTestId("risk-tensor-payload-quality-warning");
      const payloadChecklist = await screen.findByTestId("risk-tensor-quality-payload-checklist");

      await user.click(within(warning).getByTestId("risk-tensor-payload-quality-review-action"));

      expect(scrollTargets).toContain(payloadChecklist);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users jump from the first-screen payload warning to result_meta evidence", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_payload_meta_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_payload_meta_jump_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          portfolio_dv01: "",
          liquidity_gap_30d_ratio: "not-a-number",
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const warning = await screen.findByTestId("risk-tensor-payload-quality-warning");
      const resultMetaPanel = await screen.findByTestId("risk-tensor-result-meta-panel");

      await user.click(within(warning).getByTestId("risk-tensor-payload-quality-meta-action"));

      expect(scrollTargets).toContain(resultMetaPanel);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("shows result_meta evidence summary in the first-screen payload warning", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_payload_warning_evidence_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: {
        ...buildMeta("risk.tensor", `tr_tensor_payload_warning_evidence_${reportDate}`),
        evidence_rows: 128,
        tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
        filters_applied: {
          report_date: reportDate,
          desk: "FI",
        },
      },
      result: {
        ...tensorResult(reportDate),
        portfolio_dv01: "",
        liquidity_gap_30d_ratio: "not-a-number",
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const warning = await screen.findByTestId("risk-tensor-payload-quality-warning");
    expect(warning).toHaveTextContent("evidence_rows 128");
    expect(warning).toHaveTextContent("tables_used risk_tensor_daily / bond_position_snapshot");
    expect(warning).toHaveTextContent("filters_applied report_date=2026-02-28；desk=FI");
  });

  it("does not show a quality evidence supplement request in the first-screen warning when result_meta evidence is complete", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_payload_warning_evidence_complete_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: {
        ...buildMeta("risk.tensor", `tr_tensor_payload_warning_evidence_complete_${reportDate}`),
        evidence_rows: 128,
        tables_used: ["risk_tensor_daily"],
        filters_applied: { report_date: reportDate },
      },
      result: {
        ...tensorResult(reportDate),
        portfolio_dv01: "",
        liquidity_gap_30d_ratio: "not-a-number",
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const warning = await screen.findByTestId("risk-tensor-payload-quality-warning");
    expect(within(warning).queryByRole("button", { name: "复制证据补证请求" })).not.toBeInTheDocument();
  });

  it("lets users copy a quality evidence supplement request from the first-screen payload warning", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_payload_warning_evidence_request_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_payload_warning_evidence_request_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          portfolio_dv01: "",
          liquidity_gap_30d_ratio: "not-a-number",
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const warning = await screen.findByTestId("risk-tensor-payload-quality-warning");
      await user.click(within(warning).getByRole("button", { name: "复制证据补证请求" }));

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量质量证据补证请求"));
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("trace_id tr_tensor_payload_warning_evidence_request_2026-02-28"),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("basis formal"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("cache_version cv_tensor_test"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("generated_at 2026-04-12T08:00:00Z"));
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("缺失字段 evidence_rows / tables_used / filters_applied"),
      );
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("请在 result_meta 补充 evidence_rows、tables_used、filters_applied 后重新出具"),
      );
      await waitFor(() => {
        expect(warning).toHaveTextContent("已复制补证请求");
      });
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("shows manual quality evidence supplement request text in the first-screen warning when clipboard copy fails", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => {
      throw new Error("clipboard denied");
    });
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_payload_warning_evidence_request_failure_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_payload_warning_evidence_request_failure_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          portfolio_dv01: "",
          liquidity_gap_30d_ratio: "not-a-number",
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const warning = await screen.findByTestId("risk-tensor-payload-quality-warning");
      await user.click(within(warning).getByRole("button", { name: "复制证据补证请求" }));

      await waitFor(() => {
        expect(warning).toHaveTextContent("复制失败，请手动选择补证请求");
      });

      const manualCopy = within(warning).getByTestId("risk-tensor-quality-evidence-warning-request-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量质量证据补证请求");
      expect(manualCopy).toHaveTextContent("trace_id tr_tensor_payload_warning_evidence_request_failure_2026-02-28");
      expect(manualCopy).toHaveTextContent("缺失字段 evidence_rows / tables_used / filters_applied");
      expect(manualCopy).toHaveTextContent(
        "请在 result_meta 补充 evidence_rows、tables_used、filters_applied 后重新出具",
      );
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("clears first-screen evidence supplement feedback when result_meta evidence becomes complete", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      let queryClient: QueryClient | undefined;
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_payload_warning_evidence_resolved_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", "tr_tensor_payload_warning_evidence_resolved"),
        result: {
          ...tensorResult(reportDate),
          portfolio_dv01: "",
          liquidity_gap_30d_ratio: "not-a-number",
        },
      }));

      renderRiskTensorRoute(
        "/risk-tensor",
        {
          ...base,
          getRiskTensorDates,
          getRiskTensor,
        },
        (client) => {
          queryClient = client;
        },
      );

      const warning = await screen.findByTestId("risk-tensor-payload-quality-warning");
      await user.click(within(warning).getByRole("button", { name: "复制证据补证请求" }));
      await user.click(within(warning).getByRole("button", { name: "复制完整补证包" }));

      await waitFor(() => {
        expect(warning).toHaveTextContent("已复制补证请求");
        expect(warning).toHaveTextContent("已复制完整补证包");
      });

      await act(async () => {
        queryClient?.setQueryData(["risk-tensor", "2026-02-28"], {
          result_meta: {
            ...buildMeta("risk.tensor", "tr_tensor_payload_warning_evidence_resolved"),
            evidence_rows: 128,
            tables_used: ["risk_tensor_daily"],
            filters_applied: { report_date: "2026-02-28" },
          },
          result: {
            ...tensorResult("2026-02-28"),
            portfolio_dv01: "",
            liquidity_gap_30d_ratio: "not-a-number",
          },
        });
      });

      await waitFor(() => {
        expect(warning).toHaveTextContent("evidence_rows 128");
      });
      expect(within(warning).queryByRole("button", { name: "复制证据补证请求" })).not.toBeInTheDocument();
      expect(within(warning).queryByRole("button", { name: "复制完整补证包" })).not.toBeInTheDocument();
      expect(warning).not.toHaveTextContent("已复制补证请求");
      expect(warning).not.toHaveTextContent("已复制完整补证包");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("resets quality review confirmation when result_meta evidence content changes", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      let queryClient: QueryClient | undefined;
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_evidence_content_reset_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", "tr_tensor_evidence_content_reset"),
          evidence_rows: 128,
          tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
          filters_applied: { report_date: reportDate, desk: "FI" },
        },
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute(
        "/risk-tensor",
        {
          ...base,
          getRiskTensorDates,
          getRiskTensor,
        },
        (client) => {
          queryClient = client;
        },
      );

      const tracePriority = within(await screen.findByTestId("risk-tensor-quality-detail")).getByTestId(
        "risk-tensor-quality-trace-priority",
      );
      await user.click(within(tracePriority).getByRole("button", { name: "复制证据" }));
      await user.click(await within(tracePriority).findByRole("button", { name: "确认业务复核" }));

      expect(tracePriority).toHaveTextContent("复核状态：业务已确认");
      expect(within(tracePriority).getByRole("button", { name: "复制确认记录" })).toBeInTheDocument();

      await act(async () => {
        queryClient?.setQueryData(["risk-tensor", "2026-02-28"], {
          result_meta: {
            ...buildMeta("risk.tensor", "tr_tensor_evidence_content_reset"),
            evidence_rows: 96,
            tables_used: ["risk_tensor_daily"],
            filters_applied: { report_date: "2026-02-28", desk: "FI", book: "TRADING" },
          },
          result: tensorResult("2026-02-28"),
        });
      });

      await waitFor(() => {
        expect(tracePriority).toHaveTextContent("evidence_rows 96");
      });
      expect(tracePriority).toHaveTextContent("tables_used risk_tensor_daily");
      expect(tracePriority).toHaveTextContent("filters_applied report_date=2026-02-28；desk=FI；book=TRADING");
      expect(tracePriority).toHaveTextContent("复核状态：待复核");
      expect(tracePriority).not.toHaveTextContent("业务已确认");
      expect(within(tracePriority).queryByRole("button", { name: "复制确认记录" })).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("resets quality review confirmation when source or rule version changes", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      let queryClient: QueryClient | undefined;
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_lineage_version_reset_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", "tr_tensor_lineage_version_reset"),
          evidence_rows: 128,
          tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
          filters_applied: { report_date: reportDate, desk: "FI" },
        },
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute(
        "/risk-tensor",
        {
          ...base,
          getRiskTensorDates,
          getRiskTensor,
        },
        (client) => {
          queryClient = client;
        },
      );

      const tracePriority = within(await screen.findByTestId("risk-tensor-quality-detail")).getByTestId(
        "risk-tensor-quality-trace-priority",
      );
      await user.click(within(tracePriority).getByRole("button", { name: "复制证据" }));
      await user.click(await within(tracePriority).findByRole("button", { name: "确认业务复核" }));

      expect(tracePriority).toHaveTextContent("复核状态：业务已确认");
      expect(within(tracePriority).getByRole("button", { name: "复制确认记录" })).toBeInTheDocument();

      await act(async () => {
        queryClient?.setQueryData(["risk-tensor", "2026-02-28"], {
          result_meta: {
            ...buildMeta("risk.tensor", "tr_tensor_lineage_version_reset"),
            source_version: "sv_tensor_reissued",
            rule_version: "rv_tensor_reissued",
            evidence_rows: 128,
            tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
            filters_applied: { report_date: "2026-02-28", desk: "FI" },
          },
          result: tensorResult("2026-02-28"),
        });
      });

      await waitFor(() => {
        expect(tracePriority).toHaveTextContent("来源 sv_tensor_reissued；规则 rv_tensor_reissued");
      });
      expect(tracePriority).toHaveTextContent("复核状态：待复核");
      expect(tracePriority).not.toHaveTextContent("业务已确认");
      expect(within(tracePriority).queryByRole("button", { name: "复制确认记录" })).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("resets quality review confirmation when fallback status changes", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      let queryClient: QueryClient | undefined;
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_fallback_reset_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", "tr_tensor_fallback_reset"),
          evidence_rows: 128,
          tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
          filters_applied: { report_date: reportDate, desk: "FI" },
        },
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute(
        "/risk-tensor",
        {
          ...base,
          getRiskTensorDates,
          getRiskTensor,
        },
        (client) => {
          queryClient = client;
        },
      );

      const tracePriority = within(await screen.findByTestId("risk-tensor-quality-detail")).getByTestId(
        "risk-tensor-quality-trace-priority",
      );
      await user.click(within(tracePriority).getByRole("button", { name: "复制证据" }));
      await user.click(await within(tracePriority).findByRole("button", { name: "确认业务复核" }));

      expect(tracePriority).toHaveTextContent("复核状态：业务已确认");
      expect(within(tracePriority).getByRole("button", { name: "复制确认记录" })).toBeInTheDocument();

      await act(async () => {
        queryClient?.setQueryData(["risk-tensor", "2026-02-28"], {
          result_meta: {
            ...buildMeta("risk.tensor", "tr_tensor_fallback_reset"),
            fallback_mode: "latest_snapshot",
            fallback_date: "2026-02-27",
            evidence_rows: 128,
            tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
            filters_applied: { report_date: "2026-02-28", desk: "FI" },
          },
          result: tensorResult("2026-02-28"),
        });
      });

      await waitFor(() => {
        expect(tracePriority).toHaveTextContent("fallback_date 2026-02-27");
      });
      expect(tracePriority).toHaveTextContent("复核状态：待复核");
      expect(tracePriority).not.toHaveTextContent("业务已确认");
      expect(within(tracePriority).queryByRole("button", { name: "复制确认记录" })).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("resets quality review confirmation when warning evidence changes", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      let queryClient: QueryClient | undefined;
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_warning_reset_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", "tr_tensor_warning_reset"),
          evidence_rows: 128,
          tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
          filters_applied: { report_date: reportDate, desk: "FI" },
        },
        result: {
          ...tensorResult(reportDate),
          warnings: ["估值曲线 vendor stale"],
        },
      }));

      renderRiskTensorRoute(
        "/risk-tensor",
        {
          ...base,
          getRiskTensorDates,
          getRiskTensor,
        },
        (client) => {
          queryClient = client;
        },
      );

      const tracePriority = within(await screen.findByTestId("risk-tensor-quality-detail")).getByTestId(
        "risk-tensor-quality-trace-priority",
      );
      await user.click(within(tracePriority).getByRole("button", { name: "复制证据" }));
      await user.click(await within(tracePriority).findByRole("button", { name: "确认业务复核" }));

      expect(tracePriority).toHaveTextContent("复核状态：业务已确认");
      expect(within(tracePriority).getByRole("button", { name: "复制确认记录" })).toBeInTheDocument();

      await act(async () => {
        queryClient?.setQueryData(["risk-tensor", "2026-02-28"], {
          result_meta: {
            ...buildMeta("risk.tensor", "tr_tensor_warning_reset"),
            evidence_rows: 128,
            tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
            filters_applied: { report_date: "2026-02-28", desk: "FI" },
          },
          result: {
            ...tensorResult("2026-02-28"),
            warnings: ["回售权现金流未进入 formal 张量"],
          },
        });
      });

      await waitFor(() => {
        expect(tracePriority).toHaveTextContent("回售权现金流未进入 formal 张量");
      });
      expect(tracePriority).toHaveTextContent("复核状态：待复核");
      expect(tracePriority).not.toHaveTextContent("业务已确认");
      expect(within(tracePriority).queryByRole("button", { name: "复制确认记录" })).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("resets quality review confirmation when blocked report date evidence changes", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      let queryClient: QueryClient | undefined;
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_blocked_evidence_reset_dates"),
        result: { report_dates: ["2026-02-28"], blocked_report_dates: [] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", "tr_tensor_blocked_evidence_reset"),
          evidence_rows: 128,
          tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
          filters_applied: { report_date: reportDate, desk: "FI" },
        },
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute(
        "/risk-tensor",
        {
          ...base,
          getRiskTensorDates,
          getRiskTensor,
        },
        (client) => {
          queryClient = client;
        },
      );

      const tracePriority = within(await screen.findByTestId("risk-tensor-quality-detail")).getByTestId(
        "risk-tensor-quality-trace-priority",
      );
      await user.click(within(tracePriority).getByRole("button", { name: "复制证据" }));
      await user.click(await within(tracePriority).findByRole("button", { name: "确认业务复核" }));

      expect(tracePriority).toHaveTextContent("复核状态：业务已确认");
      expect(within(tracePriority).getByRole("button", { name: "复制确认记录" })).toBeInTheDocument();

      await act(async () => {
        queryClient?.setQueryData(["risk-tensor", "dates", "mock"], {
          result_meta: buildMeta("risk.tensor.dates", "tr_tensor_blocked_evidence_reset_dates"),
          result: {
            report_dates: ["2026-02-28"],
            blocked_report_dates: [
              {
                report_date: "2026-02-27",
                reason: "risk tensor source lineage is stale",
              },
            ],
          },
        });
      });

      await waitFor(() => {
        expect(tracePriority).toHaveTextContent("1 个陈旧日期已拦截");
      });
      expect(tracePriority).toHaveTextContent("risk tensor source lineage is stale");
      expect(tracePriority).toHaveTextContent("复核状态：待复核");
      expect(tracePriority).not.toHaveTextContent("业务已确认");
      expect(within(tracePriority).queryByRole("button", { name: "复制确认记录" })).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("resets quality review confirmation when quality flag changes", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      let queryClient: QueryClient | undefined;
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_quality_flag_reset_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", "tr_tensor_quality_flag_reset"),
          evidence_rows: 128,
          tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
          filters_applied: { report_date: reportDate, desk: "FI" },
          quality_flag: "warning" as ResultMeta["quality_flag"],
        },
        result: {
          ...tensorResult(reportDate),
          quality_flag: "warning" as RiskTensorPayload["quality_flag"],
        },
      }));

      renderRiskTensorRoute(
        "/risk-tensor",
        {
          ...base,
          getRiskTensorDates,
          getRiskTensor,
        },
        (client) => {
          queryClient = client;
        },
      );

      const tracePriority = within(await screen.findByTestId("risk-tensor-quality-detail")).getByTestId(
        "risk-tensor-quality-trace-priority",
      );
      await user.click(within(tracePriority).getByRole("button", { name: "复制证据" }));
      await user.click(await within(tracePriority).findByRole("button", { name: "确认业务复核" }));

      expect(tracePriority).toHaveTextContent("复核状态：业务已确认");
      expect(within(tracePriority).getByRole("button", { name: "复制确认记录" })).toBeInTheDocument();

      await act(async () => {
        queryClient?.setQueryData(["risk-tensor", "2026-02-28"], {
          result_meta: {
            ...buildMeta("risk.tensor", "tr_tensor_quality_flag_reset"),
            evidence_rows: 128,
            tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
            filters_applied: { report_date: "2026-02-28", desk: "FI" },
            quality_flag: "error" as ResultMeta["quality_flag"],
          },
          result: {
            ...tensorResult("2026-02-28"),
            quality_flag: "error" as RiskTensorPayload["quality_flag"],
          },
        });
      });

      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");
      await waitFor(() => {
        expect(qualityDetail).toHaveTextContent("质量标记：错误");
      });
      expect(tracePriority).toHaveTextContent("复核状态：待复核");
      expect(tracePriority).not.toHaveTextContent("业务已确认");
      expect(within(tracePriority).queryByRole("button", { name: "复制确认记录" })).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("resets quality review confirmation when result kind changes", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      let queryClient: QueryClient | undefined;
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_result_kind_reset_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", "tr_tensor_result_kind_reset"),
          evidence_rows: 128,
          tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
          filters_applied: { report_date: reportDate, desk: "FI" },
        },
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute(
        "/risk-tensor",
        {
          ...base,
          getRiskTensorDates,
          getRiskTensor,
        },
        (client) => {
          queryClient = client;
        },
      );

      const tracePriority = within(await screen.findByTestId("risk-tensor-quality-detail")).getByTestId(
        "risk-tensor-quality-trace-priority",
      );
      await user.click(within(tracePriority).getByRole("button", { name: "复制证据" }));
      await user.click(await within(tracePriority).findByRole("button", { name: "确认业务复核" }));

      expect(tracePriority).toHaveTextContent("复核状态：业务已确认");
      expect(within(tracePriority).getByRole("button", { name: "复制确认记录" })).toBeInTheDocument();

      await act(async () => {
        queryClient?.setQueryData(["risk-tensor", "2026-02-28"], {
          result_meta: {
            ...buildMeta("risk.tensor.reissued", "tr_tensor_result_kind_reset"),
            evidence_rows: 128,
            tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
            filters_applied: { report_date: "2026-02-28", desk: "FI" },
          },
          result: tensorResult("2026-02-28"),
        });
      });

      await user.click(within(tracePriority).getByRole("button", { name: "复制证据" }));

      expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining("result_kind risk.tensor.reissued"));
      expect(tracePriority).toHaveTextContent("复核状态：证据已复制，待业务确认");
      expect(tracePriority).not.toHaveTextContent("业务已确认");
      expect(within(tracePriority).queryByRole("button", { name: "复制确认记录" })).not.toBeInTheDocument();
      expect(within(tracePriority).getByRole("button", { name: "确认业务复核" })).toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("resets quality review confirmation when result_meta issuance context changes", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      let queryClient: QueryClient | undefined;
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_issuance_context_reset_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", "tr_tensor_issuance_context_reset"),
          evidence_rows: 128,
          tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
          filters_applied: { report_date: reportDate, desk: "FI" },
        },
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute(
        "/risk-tensor",
        {
          ...base,
          getRiskTensorDates,
          getRiskTensor,
        },
        (client) => {
          queryClient = client;
        },
      );

      const tracePriority = within(await screen.findByTestId("risk-tensor-quality-detail")).getByTestId(
        "risk-tensor-quality-trace-priority",
      );
      await user.click(within(tracePriority).getByRole("button", { name: "复制证据" }));
      await user.click(await within(tracePriority).findByRole("button", { name: "确认业务复核" }));

      expect(tracePriority).toHaveTextContent("复核状态：业务已确认");
      expect(within(tracePriority).getByRole("button", { name: "复制确认记录" })).toBeInTheDocument();

      await act(async () => {
        queryClient?.setQueryData(["risk-tensor", "2026-02-28"], {
          result_meta: {
            ...buildMeta("risk.tensor", "tr_tensor_issuance_context_reset"),
            basis: "regulatory_dv01" as ResultMeta["basis"],
            cache_version: "cv_tensor_reissued",
            generated_at: "2026-04-12T09:30:00Z",
            evidence_rows: 128,
            tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
            filters_applied: { report_date: "2026-02-28", desk: "FI" },
          },
          result: tensorResult("2026-02-28"),
        });
      });

      const metaPanel = await screen.findByTestId("risk-tensor-result-meta-panel");
      await waitFor(() => {
        expect(metaPanel).toHaveTextContent("cv_tensor_reissued");
      });
      expect(metaPanel).toHaveTextContent("2026-04-12T09:30:00Z");
      expect(screen.getByTestId("risk-tensor-brief")).toHaveTextContent("regulatory_dv01 口径");
      expect(tracePriority).toHaveTextContent("复核状态：待复核");
      expect(tracePriority).not.toHaveTextContent("业务已确认");
      expect(within(tracePriority).queryByRole("button", { name: "复制确认记录" })).not.toBeInTheDocument();

      await user.click(within(tracePriority).getByRole("button", { name: "复制证据" }));

      expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining("basis regulatory_dv01"));
      expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining("cache_version cv_tensor_reissued"));
      expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining("generated_at 2026-04-12T09:30:00Z"));

      await user.click(await within(tracePriority).findByRole("button", { name: "确认业务复核" }));
      await user.click(within(tracePriority).getByRole("button", { name: "复制确认记录" }));

      expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining("basis regulatory_dv01"));
      expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining("cache_version cv_tensor_reissued"));
      expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining("generated_at 2026-04-12T09:30:00Z"));
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("lets users copy a combined payload and evidence supplement package from the first-screen warning", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async (_text: string) => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_payload_warning_combined_request_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_payload_warning_combined_request_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          portfolio_dv01: "",
          liquidity_gap_30d_ratio: "not-a-number",
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const warning = await screen.findByTestId("risk-tensor-payload-quality-warning");
      await user.click(within(warning).getByRole("button", { name: "复制完整补证包" }));

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量首屏补证包"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量主读 payload 补证请求"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量质量证据补证请求"));
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("trace_id tr_tensor_payload_warning_combined_request_2026-02-28"),
      );
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("异常字段 portfolio_dv01 缺失 / liquidity_gap_30d_ratio 不可解析"),
      );
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("缺失字段 evidence_rows / tables_used / filters_applied"),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("不会在前端补算正式指标"));
      const copiedPackage = writeText.mock.calls.at(-1)?.[0] ?? "";
      expect(copiedPackage).toContain("basis formal");
      expect(copiedPackage).toContain("cache_version cv_tensor_test");
      expect(copiedPackage).toContain("generated_at 2026-04-12T08:00:00Z");
      expect(copiedPackage.match(/^basis formal$/gm)).toHaveLength(2);
      expect(copiedPackage.match(/^cache_version cv_tensor_test$/gm)).toHaveLength(2);
      expect(copiedPackage.match(/^generated_at 2026-04-12T08:00:00Z$/gm)).toHaveLength(2);
      await waitFor(() => {
        expect(warning).toHaveTextContent("已复制完整补证包");
      });
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("resets combined supplement package copy feedback when report date changes", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_payload_warning_combined_reset_dates"),
        result: { report_dates: ["2026-02-28", "2026-01-31"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", "tr_tensor_payload_warning_combined_reset_reused_trace"),
        result: {
          ...tensorResult(reportDate),
          portfolio_dv01: "",
          liquidity_gap_30d_ratio: "not-a-number",
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const warning = await screen.findByTestId("risk-tensor-payload-quality-warning");
      await user.click(within(warning).getByRole("button", { name: "复制完整补证包" }));

      await waitFor(() => {
        expect(warning).toHaveTextContent("已复制完整补证包");
      });

      await user.selectOptions(screen.getByLabelText("风险报告日"), "2026-01-31");

      await waitFor(() => {
        expect(getRiskTensor).toHaveBeenCalledWith("2026-01-31");
      });
      const nextWarning = await screen.findByTestId("risk-tensor-payload-quality-warning");
      expect(nextWarning).toHaveTextContent("报告日 2026-01-31");
      expect(nextWarning).not.toHaveTextContent("已复制完整补证包");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("ignores stale combined supplement package copy results after report date changes", async () => {
    const user = userEvent.setup();
    let resolveCopy: (() => void) | undefined;
    const writeText = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveCopy = resolve;
        }),
    );
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_payload_warning_stale_combined_dates"),
        result: { report_dates: ["2026-02-28", "2026-01-31"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", "tr_tensor_payload_warning_stale_combined"),
        result: {
          ...tensorResult(reportDate),
          portfolio_dv01: null as unknown as RiskTensorPayload["portfolio_dv01"],
          liquidity_gap_30d_ratio: "bad-ratio",
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const warning = await screen.findByTestId("risk-tensor-payload-quality-warning");
      await user.click(within(warning).getByRole("button", { name: "复制完整补证包" }));
      await user.selectOptions(screen.getByLabelText("风险报告日"), "2026-01-31");

      const nextWarning = await screen.findByTestId("risk-tensor-payload-quality-warning");
      await waitFor(() => {
        expect(nextWarning).toHaveTextContent("报告日 2026-01-31");
      });

      await act(async () => {
        resolveCopy?.();
      });

      expect(nextWarning).not.toHaveTextContent("已复制完整补证包");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("shows manual combined supplement package text in the first-screen warning when clipboard copy fails", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => {
      throw new Error("clipboard denied");
    });
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_payload_warning_combined_request_failure_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_payload_warning_combined_request_failure_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          portfolio_dv01: "",
          liquidity_gap_30d_ratio: "not-a-number",
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const warning = await screen.findByTestId("risk-tensor-payload-quality-warning");
      await user.click(within(warning).getByRole("button", { name: "复制完整补证包" }));

      await waitFor(() => {
        expect(warning).toHaveTextContent("复制失败，请手动选择完整补证包");
      });

      const manualCopy = within(warning).getByTestId("risk-tensor-combined-quality-warning-request-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量首屏补证包");
      expect(manualCopy).toHaveTextContent("风险张量主读 payload 补证请求");
      expect(manualCopy).toHaveTextContent("风险张量质量证据补证请求");
      expect(manualCopy).toHaveTextContent("trace_id tr_tensor_payload_warning_combined_request_failure_2026-02-28");
      expect(manualCopy).toHaveTextContent("异常字段 portfolio_dv01 缺失 / liquidity_gap_30d_ratio 不可解析");
      expect(manualCopy).toHaveTextContent("缺失字段 evidence_rows / tables_used / filters_applied");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("lets users copy a payload supplement request from the first-screen warning", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_payload_warning_copy_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_payload_warning_copy_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          portfolio_dv01: "",
          liquidity_gap_30d_ratio: "not-a-number",
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const warning = await screen.findByTestId("risk-tensor-payload-quality-warning");
      await user.click(within(warning).getByRole("button", { name: "复制字段补证请求" }));

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量主读 payload 补证请求"));
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("trace_id tr_tensor_payload_warning_copy_2026-02-28"),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("报告日 2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("basis formal"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("cache_version cv_tensor_test"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("generated_at 2026-04-12T08:00:00Z"));
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("异常字段 portfolio_dv01 缺失 / liquidity_gap_30d_ratio 不可解析"),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("不会在前端补算正式指标"));
      await waitFor(() => {
        expect(warning).toHaveTextContent("已复制字段补证请求");
      });
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("shows manual payload supplement request text in the first-screen warning when clipboard copy fails", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => {
      throw new Error("clipboard denied");
    });
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_payload_warning_copy_failure_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_payload_warning_copy_failure_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          portfolio_dv01: "",
          liquidity_gap_30d_ratio: "not-a-number",
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const warning = await screen.findByTestId("risk-tensor-payload-quality-warning");
      await user.click(within(warning).getByRole("button", { name: "复制字段补证请求" }));

      await waitFor(() => {
        expect(warning).toHaveTextContent("复制失败，请手动选择字段补证请求");
      });

      const manualCopy = within(warning).getByTestId("risk-tensor-payload-quality-warning-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量主读 payload 补证请求");
      expect(manualCopy).toHaveTextContent("trace_id tr_tensor_payload_warning_copy_failure_2026-02-28");
      expect(manualCopy).toHaveTextContent("报告日 2026-02-28");
      expect(manualCopy).toHaveTextContent("异常字段 portfolio_dv01 缺失 / liquidity_gap_30d_ratio 不可解析");
      expect(manualCopy).toHaveTextContent("不会在前端补算正式指标");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("lets users review and retry unparseable KRD bucket fields from the drilldown note", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_krd_quality_actions_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi
        .fn()
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_krd_quality_actions_initial"),
          result: {
            ...tensorResult("2026-02-28"),
            krd_1y: "10000",
            krd_3y: "90000",
            krd_5y: "not-a-number",
            krd_7y: "25000",
            krd_10y: "15000",
            krd_30y: "5000",
          },
        })
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_krd_quality_actions_success"),
          result: tensorResult("2026-02-28"),
        });

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const drill = await screen.findByTestId("risk-tensor-tenor-drill");
      const qualityNote = within(drill).getByTestId("risk-tensor-krd-quality-note");
      const payloadChecklist = await screen.findByTestId("risk-tensor-quality-payload-checklist");

      await user.click(within(qualityNote).getByRole("button", { name: "查看字段复核" }));

      expect(scrollTargets).toContain(payloadChecklist);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });

      await user.click(within(qualityNote).getByRole("button", { name: "重试主读面" }));

      await waitFor(() => {
        expect(getRiskTensor).toHaveBeenCalledTimes(2);
      });
      expect(screen.queryByTestId("risk-tensor-krd-quality-note")).not.toBeInTheDocument();
      expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent(
        "tr_tensor_krd_quality_actions_success",
      );
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("keeps invalid KRD chart bucket clicks on the field review path", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_krd_invalid_chart_click_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_krd_invalid_chart_click_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          krd_1y: "bad-krd",
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const tenorDrill = await screen.findByTestId("risk-tensor-tenor-drill");
      const qualityNote = await screen.findByTestId("risk-tensor-krd-quality-note");
      const krdChart = screen.getAllByTestId("risk-tensor-echarts-stub")[1]!;
      expect(tenorDrill).toHaveTextContent("当前桶：5Y");
      expect(qualityNote).toHaveTextContent("krd_1y");

      await user.click(krdChart);

      expect(scrollTargets).toContain(qualityNote);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
      expect(tenorDrill).toHaveTextContent("当前桶：5Y");
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("keeps invalid KRD tenor chip clicks on the field review path", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_krd_invalid_chip_click_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_krd_invalid_chip_click_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          krd_1y: "bad-krd",
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const tenorDrill = await screen.findByTestId("risk-tensor-tenor-drill");
      const qualityNote = await screen.findByTestId("risk-tensor-krd-quality-note");
      expect(within(tenorDrill).getByText("5Y", { selector: "strong" })).toBeInTheDocument();

      await user.click(within(tenorDrill).getByRole("button", { name: "1Y" }));

      expect(scrollTargets).toContain(qualityNote);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
      expect(within(tenorDrill).getByText("5Y", { selector: "strong" })).toBeInTheDocument();
      expect(within(tenorDrill).queryByText("1Y", { selector: "strong" })).not.toBeInTheDocument();
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("shows review and retry actions when every KRD bucket is unparseable", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_krd_all_invalid_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi
        .fn()
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_krd_all_invalid_initial"),
          result: {
            ...tensorResult("2026-02-28"),
            krd_1y: "not-a-number",
            krd_3y: "",
            krd_5y: "undefined",
            krd_7y: "bad",
            krd_10y: "NaN",
            krd_30y: "missing",
          },
        })
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_krd_all_invalid_retry"),
          result: tensorResult("2026-02-28"),
        });

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      expect(await screen.findByTestId("risk-tensor-brief")).toHaveTextContent("主风险桶 —");
      expect(screen.queryByTestId("risk-tensor-tenor-drill")).not.toBeInTheDocument();

      const qualityNote = await screen.findByTestId("risk-tensor-krd-quality-note");
      const payloadChecklist = await screen.findByTestId("risk-tensor-quality-payload-checklist");
      expect(qualityNote).toHaveTextContent("krd_1y 不可解析");
      expect(qualityNote).toHaveTextContent("krd_3y 缺失");
      expect(qualityNote).toHaveTextContent("未参与前端主风险桶排序和图表数值");

      await user.click(within(qualityNote).getByRole("button", { name: "查看字段复核" }));

      expect(scrollTargets).toContain(payloadChecklist);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });

      await user.click(within(qualityNote).getByRole("button", { name: "重试主读面" }));

      await waitFor(() => {
        expect(getRiskTensor).toHaveBeenCalledTimes(2);
      });
      expect(await screen.findByTestId("risk-tensor-tenor-drill")).toHaveTextContent("当前桶：5Y");
      expect(screen.queryByTestId("risk-tensor-krd-quality-note")).not.toBeInTheDocument();
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("jumps from the first-screen primary bucket tile to KRD quality review when every KRD bucket is unparseable", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_krd_all_invalid_tile_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_krd_all_invalid_tile_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          krd_1y: "bad",
          krd_3y: "",
          krd_5y: "undefined",
          krd_7y: "bad",
          krd_10y: "NaN",
          krd_30y: "missing",
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      const primaryBucketAction = within(brief).getByTestId("risk-tensor-primary-tenor-action");
      const qualityNote = await screen.findByTestId("risk-tensor-krd-quality-note");

      await user.click(primaryBucketAction);

      expect(scrollTargets).toContain(qualityNote);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("keeps unparseable radar dimensions out of chart magnitudes", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_radar_payload_quality_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_radar_payload_quality_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        portfolio_modified_duration: "bad-duration",
        liquidity_gap_30d_ratio: "not-a-number",
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const radarCard = await screen.findByTestId("risk-tensor-radar-card");
    const radarChart = screen.getAllByTestId("risk-tensor-echarts-stub")[0]!;
    const radarData = JSON.parse(radarChart.getAttribute("data-series") ?? "[]");
    expect(radarData[0]).toBeNull();
    expect(radarData[1]).toBeCloseTo(0.001234);
    expect(radarData[2]).toBeCloseTo(0.42);
    expect(radarData[3]).toBeCloseTo(0.000888);
    expect(radarData[4]).toBeCloseTo(0.18);
    expect(radarData[5]).toBeNull();

    const radarQualityNote = within(radarCard).getByTestId("risk-tensor-radar-quality-note");
    expect(radarQualityNote).toHaveTextContent("portfolio_modified_duration");
    expect(radarQualityNote).toHaveTextContent("liquidity_gap_30d_ratio");
  });

  it("lets users review and retry unparseable radar dimension fields from the quality note", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_radar_quality_actions_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi
        .fn()
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_radar_quality_actions_initial"),
          result: {
            ...tensorResult("2026-02-28"),
            portfolio_modified_duration: "bad-duration",
            liquidity_gap_30d_ratio: "not-a-number",
          },
        })
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_radar_quality_actions_success"),
          result: tensorResult("2026-02-28"),
        });

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const radarCard = await screen.findByTestId("risk-tensor-radar-card");
      const qualityNote = within(radarCard).getByTestId("risk-tensor-radar-quality-note");
      const payloadChecklist = await screen.findByTestId("risk-tensor-quality-payload-checklist");

      await user.click(within(qualityNote).getByRole("button", { name: "查看字段复核" }));

      expect(scrollTargets).toContain(payloadChecklist);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });

      await user.click(within(qualityNote).getByRole("button", { name: "重试主读面" }));

      await waitFor(() => {
        expect(getRiskTensor).toHaveBeenCalledTimes(2);
      });
      expect(screen.queryByTestId("risk-tensor-radar-quality-note")).not.toBeInTheDocument();
      expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent(
        "tr_tensor_radar_quality_actions_success",
      );
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users continue from an unparseable radar liquidity detail to payload field review", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_radar_liquidity_detail_quality_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_radar_liquidity_detail_quality_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          liquidity_gap_30d_ratio: "not-a-number",
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const liquidityDetail = await screen.findByTestId("risk-tensor-liquidity-gap-detail");
      const payloadChecklist = await screen.findByTestId("risk-tensor-quality-payload-checklist");
      const radarAction = await screen.findByTestId("risk-tensor-radar-action-liq_ratio");

      await user.click(radarAction);

      expect(scrollTargets).toContain(liquidityDetail);
      expect(within(liquidityDetail).getByTestId("risk-tensor-liquidity-quality-note")).toHaveTextContent(
        "liquidity_gap_30d_ratio",
      );

      await user.click(within(liquidityDetail).getByRole("button", { name: "查看字段复核" }));

      expect(scrollTargets).toContain(payloadChecklist);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users continue from an unparseable radar issuer detail to payload field review", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_radar_issuer_detail_quality_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_radar_issuer_detail_quality_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          issuer_concentration_hhi: "bad-hhi",
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const issuerDetail = await screen.findByTestId("risk-tensor-issuer-concentration-detail");
      const payloadChecklist = await screen.findByTestId("risk-tensor-quality-payload-checklist");
      const radarAction = await screen.findByTestId("risk-tensor-radar-action-hhi");

      await user.click(radarAction);

      expect(scrollTargets).toContain(issuerDetail);
      expect(within(issuerDetail).getByTestId("risk-tensor-issuer-quality-note")).toHaveTextContent(
        "issuer_concentration_hhi",
      );

      await user.click(within(issuerDetail).getByRole("button", { name: "查看字段复核" }));

      expect(scrollTargets).toContain(payloadChecklist);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users continue from an unparseable radar KPI detail to payload field review", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_radar_kpi_detail_quality_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_radar_kpi_detail_quality_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          portfolio_convexity: "bad-convexity",
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const convexityCard = await screen.findByTestId("risk-tensor-convexity-kpi");
      const payloadChecklist = await screen.findByTestId("risk-tensor-quality-payload-checklist");
      const radarAction = await screen.findByTestId("risk-tensor-radar-action-convexity");

      await user.click(radarAction);

      expect(scrollTargets).toContain(convexityCard);
      const kpiQualityNote = screen.getByTestId("risk-tensor-kpi-quality-note");
      expect(kpiQualityNote).toHaveTextContent("portfolio_convexity");

      await user.click(within(kpiQualityNote).getByRole("button", { name: "查看字段复核" }));

      expect(scrollTargets).toContain(payloadChecklist);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users continue from an unparseable radar duration scope to payload field review", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_radar_duration_scope_quality_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_radar_duration_scope_quality_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          portfolio_modified_duration: "bad-duration",
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
      const payloadChecklist = await screen.findByTestId("risk-tensor-quality-payload-checklist");
      const radarAction = await screen.findByTestId("risk-tensor-radar-action-duration");

      await user.click(radarAction);

      expect(scrollTargets).toContain(durationScope);
      const durationQualityNote = within(durationScope).getByTestId("risk-tensor-duration-quality-note");
      expect(durationQualityNote).toHaveTextContent("portfolio_modified_duration");

      await user.click(within(durationQualityNote).getByRole("button", { name: "查看字段复核" }));

      expect(scrollTargets).toContain(payloadChecklist);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users continue from unparseable duration coverage fields to payload field review", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_duration_coverage_quality_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_duration_coverage_quality_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          rate_risk_market_value: "400000000",
          rate_risk_dv01: "bad-rate-dv01",
          rate_risk_modified_duration: "4.2",
          duration_excluded_market_value: "not-a-number",
          duration_excluded_count: 2,
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const durationScope = await screen.findByTestId("risk-tensor-duration-scope");
      const payloadChecklist = await screen.findByTestId("risk-tensor-quality-payload-checklist");
      const qualityNote = within(durationScope).getByTestId("risk-tensor-duration-coverage-quality-note");
      expect(qualityNote).toHaveTextContent("rate_risk_dv01 不可解析");
      expect(qualityNote).toHaveTextContent("duration_excluded_market_value 不可解析");

      await user.click(within(qualityNote).getByRole("button", { name: "查看字段复核" }));

      expect(scrollTargets).toContain(payloadChecklist);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("uses readable dynamic max values for radar axes", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_radar_axis_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_radar_axis_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        portfolio_dv01: "120000",
        cs01: "18000",
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    await screen.findByTestId("risk-tensor-radar-card");
    const radarChart = screen.getAllByTestId("risk-tensor-echarts-stub")[0]!;
    const indicator = JSON.parse(radarChart.getAttribute("data-indicator") ?? "[]");

    expect(indicator[1]).toMatchObject({ max: 25, interval: 5 });
    expect(indicator[2]).toMatchObject({ max: 250, interval: 50 });
    expect(indicator[3]).toMatchObject({ max: 5, interval: 1 });
  });

  it("copies a supplement request for missing or unparseable main payload fields", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_payload_request_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: {
          ...buildMeta("risk.tensor", `tr_tensor_payload_request_${reportDate}`),
          evidence_rows: 128,
          tables_used: ["risk_tensor_daily"],
          filters_applied: { report_date: reportDate },
        },
        result: {
          ...tensorResult(reportDate),
          portfolio_dv01: "",
          liquidity_gap_30d_ratio: "not-a-number",
          krd_5y: {
            raw: Number.NaN,
            unit: "dv01" as const,
            display: "--",
            precision: 2,
            sign_aware: false,
          },
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");
      const payloadChecklist = within(qualityDetail).getByTestId("risk-tensor-quality-payload-checklist");

      expect(within(qualityDetail).queryByRole("button", { name: "复制补证请求" })).not.toBeInTheDocument();

      await user.click(within(payloadChecklist).getByRole("button", { name: "复制字段补证请求" }));

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量主读 payload 补证请求"));
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("trace_id tr_tensor_payload_request_2026-02-28"),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("报告日 2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("basis formal"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("cache_version cv_tensor_test"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("generated_at 2026-04-12T08:00:00Z"));
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("异常字段 portfolio_dv01 缺失 / krd_5y 不可解析 / liquidity_gap_30d_ratio 不可解析"),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("不会在前端补算正式指标"));
      expect(payloadChecklist).toHaveTextContent("已复制字段补证请求");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("shows manual payload supplement request text when clipboard copy fails", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => {
      throw new Error("clipboard denied");
    });
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    try {
      const base = createApiClient({ mode: "mock" });
      const getRiskTensorDates = vi.fn(async () => ({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_payload_request_failure_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_payload_request_failure_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          portfolio_dv01: "",
          liquidity_gap_30d_ratio: "not-a-number",
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const payloadChecklist = within(await screen.findByTestId("risk-tensor-quality-detail")).getByTestId(
        "risk-tensor-quality-payload-checklist",
      );
      await user.click(within(payloadChecklist).getByRole("button", { name: "复制字段补证请求" }));

      await waitFor(() => {
        expect(payloadChecklist).toHaveTextContent("复制失败，请手动选择字段补证请求");
      });

      const manualCopy = within(payloadChecklist).getByTestId("risk-tensor-payload-quality-request-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量主读 payload 补证请求");
      expect(manualCopy).toHaveTextContent("trace_id tr_tensor_payload_request_failure_2026-02-28");
      expect(manualCopy).toHaveTextContent("报告日 2026-02-28");
      expect(manualCopy).toHaveTextContent("异常字段 portfolio_dv01 缺失 / liquidity_gap_30d_ratio 不可解析");
      expect(manualCopy).toHaveTextContent("不会在前端补算正式指标");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
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

  it("blocks a URL-selected report date that backend marked stale", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async (_text: string) => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates_with_selected_blocked"),
      result: {
        report_dates: ["2026-02-28"],
        blocked_report_dates: [
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

    try {
      renderRiskTensorRoute("/risk-tensor?report_date=2026-02-27", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const errorContext = await screen.findByTestId("risk-tensor-error-context");
      expect(errorContext).toHaveTextContent("风险报告日已被新鲜度校验拦截");
      expect(errorContext).toHaveTextContent("2026-02-27");
      expect(errorContext).toHaveTextContent("risk tensor source lineage is stale");
      expect(errorContext).toHaveTextContent("trace_id tr_tensor_dates_with_selected_blocked");
      expect(errorContext).toHaveTextContent("主读面未读取");
      expect(getRiskTensor).not.toHaveBeenCalled();
      expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent(
        "tr_tensor_dates_with_selected_blocked",
      );

      await user.click(within(errorContext).getByRole("button", { name: "复制拦截信息" }));

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量报告日拦截排查信息"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("报告日 2026-02-27"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("reason risk tensor source lineage is stale"));
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("日期治理 trace_id tr_tensor_dates_with_selected_blocked"),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("主读面未读取"));
      expect(errorContext).toHaveTextContent("已复制拦截信息");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("ignores stale blocked report-date copy results after date governance evidence changes", async () => {
    const user = userEvent.setup();
    let resolveCopy: (() => void) | undefined;
    const writeText = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveCopy = resolve;
        }),
    );
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi
      .fn()
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_blocked_stale_copy_initial"),
        result: {
          report_dates: [],
          blocked_report_dates: [
            {
              report_date: "2026-02-27",
              reason: "risk tensor source lineage is stale",
            },
          ],
        },
      })
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_blocked_stale_copy_refreshed"),
        result: {
          report_dates: [],
          blocked_report_dates: [
            {
              report_date: "2026-02-27",
              reason: "risk tensor source lineage refreshed but report date remains blocked",
            },
          ],
        },
      });
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    try {
      renderRiskTensorRoute("/risk-tensor?report_date=2026-02-27", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const errorContext = await screen.findByTestId("risk-tensor-error-context");
      await user.click(within(errorContext).getByRole("button", { name: "复制拦截信息" }));
      await user.click(within(errorContext).getByRole("button", { name: "重试日期治理" }));

      await waitFor(() => {
        expect(screen.getByTestId("risk-tensor-error-context")).toHaveTextContent(
          "trace_id tr_tensor_blocked_stale_copy_refreshed",
        );
      });
      expect(screen.getByTestId("risk-tensor-error-context")).toHaveTextContent(
        "risk tensor source lineage refreshed but report date remains blocked",
      );

      await act(async () => {
        resolveCopy?.();
      });

      const refreshedErrorContext = await screen.findByTestId("risk-tensor-error-context");
      expect(refreshedErrorContext).not.toHaveTextContent("已复制拦截信息");
      expect(within(refreshedErrorContext).queryByTestId("risk-tensor-blocked-date-manual-copy")).not.toBeInTheDocument();
      expect(getRiskTensor).not.toHaveBeenCalled();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("keeps blocked report-date copy feedback cleared when retry returns the same evidence", async () => {
    const user = userEvent.setup();
    let resolveCopy: (() => void) | undefined;
    const writeText = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveCopy = resolve;
        }),
    );
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const blockedDatesResponse = {
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_blocked_same_evidence_retry"),
      result: {
        report_dates: [],
        blocked_report_dates: [
          {
            report_date: "2026-02-27",
            reason: "risk tensor source lineage is stale",
          },
        ],
      },
    };
    const getRiskTensorDates = vi
      .fn()
      .mockResolvedValueOnce(blockedDatesResponse)
      .mockResolvedValueOnce(blockedDatesResponse);
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    try {
      renderRiskTensorRoute("/risk-tensor?report_date=2026-02-27", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const errorContext = await screen.findByTestId("risk-tensor-error-context");
      const [, copyBlockedDate, retryDatesGovernance] = within(errorContext).getAllByRole("button");
      await user.click(copyBlockedDate!);
      await user.click(retryDatesGovernance!);

      await waitFor(() => {
        expect(getRiskTensorDates).toHaveBeenCalledTimes(2);
      });

      await act(async () => {
        resolveCopy?.();
      });

      const retriedErrorContext = await screen.findByTestId("risk-tensor-error-context");
      expect(retriedErrorContext.querySelector(".risk-tensor-quality-detail__trace-feedback")).toBeNull();
      expect(within(retriedErrorContext).queryByTestId("risk-tensor-blocked-date-manual-copy")).not.toBeInTheDocument();
      expect(getRiskTensor).not.toHaveBeenCalled();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("lets users jump from blocked report date context to result metadata", async () => {
    const user = userEvent.setup();
    const scrollTargets: Element[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_blocked_meta_jump_dates"),
      result: {
        report_dates: ["2026-02-28"],
        blocked_report_dates: [
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

    try {
      renderRiskTensorRoute("/risk-tensor?report_date=2026-02-27", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const errorContext = await screen.findByTestId("risk-tensor-error-context");
      const metaPanel = await screen.findByTestId("risk-tensor-result-meta-panel");
      await user.click(within(errorContext).getByRole("button", { name: "定位元数据" }));

      expect(scrollTargets).toContain(metaPanel);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
      expect(getRiskTensor).not.toHaveBeenCalled();
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users recover from a backend-blocked report date by switching to the latest available date", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_blocked_recovery_dates"),
      result: {
        report_dates: ["2026-02-28", "2026-01-31"],
        blocked_report_dates: [
          {
            report_date: "2026-02-27",
            reason: "risk tensor source lineage is stale",
          },
        ],
      },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_recovered_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    renderRiskTensorRoute("/risk-tensor?report_date=2026-02-27", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const errorContext = await screen.findByTestId("risk-tensor-error-context");
    expect(errorContext).toHaveTextContent("风险报告日已被新鲜度校验拦截");
    expect(getRiskTensor).not.toHaveBeenCalled();

    await user.click(within(errorContext).getByRole("button", { name: "切换到最新可用报告日" }));

    await waitFor(() => {
      expect(getRiskTensor).toHaveBeenCalledWith("2026-02-28");
    });
    expect(await screen.findByTestId("risk-tensor-brief")).toHaveTextContent("报告日 2026-02-28");
    expect(screen.getByLabelText("风险报告日")).toHaveValue("2026-02-28");
    expect(screen.queryByTestId("risk-tensor-error-context")).not.toBeInTheDocument();
  });

  it("lets users retry report-date governance when a blocked report date has no available replacement yet", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi
      .fn()
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_blocked_no_replacement_initial"),
        result: {
          report_dates: [],
          blocked_report_dates: [
            {
              report_date: "2026-02-27",
              reason: "risk tensor source lineage is stale",
            },
          ],
        },
      })
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_blocked_no_replacement_recovered"),
        result: {
          report_dates: ["2026-02-28"],
          blocked_report_dates: [
            {
              report_date: "2026-02-27",
              reason: "risk tensor source lineage is stale",
            },
          ],
        },
      });
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_blocked_no_replacement_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    renderRiskTensorRoute("/risk-tensor?report_date=2026-02-27", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const errorContext = await screen.findByTestId("risk-tensor-error-context");
    expect(errorContext).toHaveTextContent("风险报告日已被新鲜度校验拦截");
    expect(within(errorContext).queryByRole("button", { name: "切换到最新可用报告日" })).not.toBeInTheDocument();
    expect(getRiskTensor).not.toHaveBeenCalled();

    await user.click(within(errorContext).getByRole("button", { name: "重试日期治理" }));

    await waitFor(() => {
      expect(getRiskTensorDates).toHaveBeenCalledTimes(2);
    });
    await user.click(within(await screen.findByTestId("risk-tensor-error-context")).getByRole("button", {
      name: "切换到最新可用报告日",
    }));

    await waitFor(() => {
      expect(getRiskTensor).toHaveBeenCalledWith("2026-02-28");
    });
    expect(await screen.findByTestId("risk-tensor-brief")).toHaveTextContent("报告日 2026-02-28");
    expect(screen.queryByTestId("risk-tensor-error-context")).not.toBeInTheDocument();
  });

  it("does not surface cached tensor data for a backend-blocked report date", async () => {
    const base = createApiClient({ mode: "mock" });
    const blockedReportDate = "2026-02-27";
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates_with_selected_blocked_cache"),
      result: {
        report_dates: ["2026-02-28"],
        blocked_report_dates: [
          {
            report_date: blockedReportDate,
            reason: "risk tensor source lineage is stale",
          },
        ],
      },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    renderRiskTensorRoute(
      `/risk-tensor?report_date=${blockedReportDate}`,
      {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      },
      (queryClient) => {
        queryClient.setQueryData(["risk-tensor", blockedReportDate], {
          result_meta: buildMeta("risk.tensor", "tr_tensor_cached_blocked_date"),
          result: tensorResult(blockedReportDate),
        });
      },
    );

    const errorContext = await screen.findByTestId("risk-tensor-error-context");
    expect(errorContext).toHaveTextContent("风险报告日已被新鲜度校验拦截");
    expect(getRiskTensor).not.toHaveBeenCalled();
    expect(screen.queryByTestId("risk-tensor-brief")).not.toBeInTheDocument();
    const metaPanel = screen.getByTestId("risk-tensor-result-meta-panel");
    expect(metaPanel).toHaveTextContent("tr_tensor_dates_with_selected_blocked_cache");
    expect(metaPanel).not.toHaveTextContent("tr_tensor_cached_blocked_date");
  });

  it("shows manual blocked report date diagnostic text when clipboard copy fails", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => {
      throw new Error("clipboard denied");
    });
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_blocked_copy_failure_dates"),
      result: {
        report_dates: ["2026-02-28"],
        blocked_report_dates: [
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

    try {
      renderRiskTensorRoute("/risk-tensor?report_date=2026-02-27", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const errorContext = await screen.findByTestId("risk-tensor-error-context");
      await user.click(within(errorContext).getByRole("button", { name: "复制拦截信息" }));

      await waitFor(() => {
        expect(errorContext).toHaveTextContent("复制失败，请手动选择拦截信息");
      });

      const manualCopy = within(errorContext).getByTestId("risk-tensor-blocked-date-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量报告日拦截排查信息");
      expect(manualCopy).toHaveTextContent("报告日 2026-02-27");
      expect(manualCopy).toHaveTextContent("reason risk tensor source lineage is stale");
      expect(manualCopy).toHaveTextContent("日期治理 trace_id tr_tensor_blocked_copy_failure_dates");
      expect(manualCopy).toHaveTextContent("主读面未读取");
      expect(getRiskTensor).not.toHaveBeenCalled();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
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
    const emptyState = await screen.findByTestId("risk-tensor-dates-empty-state");
    expect(emptyState).toHaveTextContent("后端未返回可用风险报告日");
    expect(emptyState).toHaveTextContent("trace_id tr_tensor_dates_empty");
    expect(emptyState).toHaveTextContent("可用报告日 0 个");
    expect(emptyState).toHaveTextContent("页面不会回退到硬编码报告日");
    expect(emptyState).toHaveTextContent("请核对风险张量报告日物化任务和日期治理结果");
    expect(getRiskTensor).not.toHaveBeenCalled();
    expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent("tr_tensor_dates_empty");
  });

  it("copies empty report-date list diagnostic context", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async (_text: string) => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates_empty_copy"),
      result: { report_dates: [] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    try {
      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const emptyState = await screen.findByTestId("risk-tensor-dates-empty-state");
      await user.click(within(emptyState).getByRole("button", { name: "复制空日期排查信息" }));

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量报告日列表为空排查信息"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("trace_id tr_tensor_dates_empty_copy"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("可用报告日 0 个"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("报告日参数 未选择"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("页面不会回退到硬编码报告日"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("主读面未读取"));
      expect(emptyState).toHaveTextContent("已复制空日期排查信息");
      expect(getRiskTensor).not.toHaveBeenCalled();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("ignores stale empty report-date copy results after date governance evidence changes", async () => {
    const user = userEvent.setup();
    let resolveCopy: (() => void) | undefined;
    const writeText = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveCopy = resolve;
        }),
    );
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi
      .fn()
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates_empty_stale_copy_initial"),
        result: { report_dates: [] },
      })
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates_empty_stale_copy_refreshed"),
        result: { report_dates: [] },
      });
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    try {
      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const emptyState = await screen.findByTestId("risk-tensor-dates-empty-state");
      await user.click(within(emptyState).getByRole("button", { name: "复制空日期排查信息" }));
      await user.click(within(emptyState).getByRole("button", { name: "重试日期治理" }));

      await waitFor(() => {
        expect(screen.getByTestId("risk-tensor-dates-empty-state")).toHaveTextContent(
          "trace_id tr_tensor_dates_empty_stale_copy_refreshed",
        );
      });

      await act(async () => {
        resolveCopy?.();
      });

      const refreshedEmptyState = await screen.findByTestId("risk-tensor-dates-empty-state");
      expect(refreshedEmptyState).not.toHaveTextContent("已复制空日期排查信息");
      expect(screen.queryByTestId("risk-tensor-dates-empty-manual-copy")).not.toBeInTheDocument();
      expect(getRiskTensor).not.toHaveBeenCalled();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("keeps empty report-date copy feedback cleared when retry returns the same empty evidence", async () => {
    const user = userEvent.setup();
    let resolveCopy: (() => void) | undefined;
    const writeText = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveCopy = resolve;
        }),
    );
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const emptyDatesResponse = {
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates_empty_same_evidence_retry"),
      result: { report_dates: [] },
    };
    const getRiskTensorDates = vi.fn().mockResolvedValueOnce(emptyDatesResponse).mockResolvedValueOnce(emptyDatesResponse);
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    try {
      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const emptyState = await screen.findByTestId("risk-tensor-dates-empty-state");
      const [, retryDatesGovernance, copyEmptyDates] = within(emptyState).getAllByRole("button");
      await user.click(copyEmptyDates!);
      await user.click(retryDatesGovernance!);

      await waitFor(() => {
        expect(getRiskTensorDates).toHaveBeenCalledTimes(2);
      });

      await act(async () => {
        resolveCopy?.();
      });

      const retriedEmptyState = await screen.findByTestId("risk-tensor-dates-empty-state");
      expect(retriedEmptyState.querySelector(".risk-tensor-quality-detail__trace-feedback")).toBeNull();
      expect(within(retriedEmptyState).queryByTestId("risk-tensor-dates-empty-manual-copy")).not.toBeInTheDocument();
      expect(getRiskTensor).not.toHaveBeenCalled();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("lets users jump from empty report-date context to result metadata", async () => {
    const user = userEvent.setup();
    const scrollTargets: Element[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates_empty_meta_jump"),
      result: { report_dates: [] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    try {
      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const emptyState = await screen.findByTestId("risk-tensor-dates-empty-state");
      const metaPanel = await screen.findByTestId("risk-tensor-result-meta-panel");
      await user.click(within(emptyState).getByRole("button", { name: "定位元数据" }));

      expect(scrollTargets).toContain(metaPanel);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
      expect(getRiskTensor).not.toHaveBeenCalled();
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users retry report-date governance from the empty report-date state", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi
      .fn()
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates_empty_retry_initial"),
        result: { report_dates: [] },
      })
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates_empty_retry_success"),
        result: { report_dates: ["2026-02-28"] },
      });
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_empty_dates_retry_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const emptyState = await screen.findByTestId("risk-tensor-dates-empty-state");
    expect(emptyState).toHaveTextContent("后端未返回可用风险报告日");
    expect(getRiskTensor).not.toHaveBeenCalled();

    await user.click(within(emptyState).getByRole("button", { name: "重试日期治理" }));

    await waitFor(() => {
      expect(getRiskTensorDates).toHaveBeenCalledTimes(2);
      expect(getRiskTensor).toHaveBeenCalledWith("2026-02-28");
    });
    expect(await screen.findByTestId("risk-tensor-brief")).toHaveTextContent("报告日 2026-02-28");
    expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent(
      "tr_tensor_dates_empty_retry_success",
    );
    expect(screen.queryByTestId("risk-tensor-dates-empty-state")).not.toBeInTheDocument();
  });

  it("shows manual empty report-date diagnostic text when clipboard copy fails", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => {
      throw new Error("clipboard denied");
    });
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates_empty_copy_failure"),
      result: { report_dates: [] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    try {
      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const emptyState = await screen.findByTestId("risk-tensor-dates-empty-state");
      await user.click(within(emptyState).getByRole("button", { name: "复制空日期排查信息" }));

      await waitFor(() => {
        expect(emptyState).toHaveTextContent("复制失败，请手动选择空日期排查信息");
      });

      const manualCopy = within(emptyState).getByTestId("risk-tensor-dates-empty-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量报告日列表为空排查信息");
      expect(manualCopy).toHaveTextContent("trace_id tr_tensor_dates_empty_copy_failure");
      expect(manualCopy).toHaveTextContent("可用报告日 0 个");
      expect(manualCopy).toHaveTextContent("报告日参数 未选择");
      expect(manualCopy).toHaveTextContent("页面不会回退到硬编码报告日");
      expect(manualCopy).toHaveTextContent("主读面未读取");
      expect(getRiskTensor).not.toHaveBeenCalled();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("surfaces a traceable no-position state when the risk tensor result is empty", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_empty_position_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: {
        ...buildMeta("risk.tensor", `tr_tensor_empty_position_${reportDate}`),
        quality_flag: "missing" as const,
        evidence_rows: 0,
        tables_used: ["risk_tensor_daily"],
        filters_applied: {
          report_date: reportDate,
          desk: "FI",
        },
      },
      result: {
        ...tensorResult(reportDate),
        bond_count: 0,
        quality_flag: "missing",
        warnings: [],
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const emptyState = await screen.findByTestId("risk-tensor-empty-state");
    expect(emptyState).toHaveTextContent("当前报告日无风险张量持仓");
    expect(emptyState).toHaveTextContent("报告日 2026-02-28");
    expect(emptyState).toHaveTextContent("trace_id tr_tensor_empty_position_2026-02-28");
    expect(emptyState).toHaveTextContent("质量标记：缺失");
    expect(emptyState).toHaveTextContent("页面不会在前端补算正式指标");
    expect(screen.queryByTestId("risk-tensor-brief")).not.toBeInTheDocument();
    expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent(
      "tr_tensor_empty_position_2026-02-28",
    );
  });

  it("copies no-position diagnostic context when the risk tensor result is empty", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async (_text: string) => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_empty_position_copy_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: {
        ...buildMeta("risk.tensor", `tr_tensor_empty_position_copy_${reportDate}`),
        quality_flag: "missing" as const,
        evidence_rows: 0,
        tables_used: ["risk_tensor_daily"],
        filters_applied: {
          report_date: reportDate,
          desk: "FI",
        },
      },
      result: {
        ...tensorResult(reportDate),
        bond_count: 0,
        quality_flag: "missing",
        warnings: [],
      },
    }));

    try {
      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const emptyState = await screen.findByTestId("risk-tensor-empty-state");
      await user.click(within(emptyState).getByRole("button", { name: "复制空持仓排查信息" }));

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量空持仓排查信息"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("报告日 2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("trace_id tr_tensor_empty_position_copy_2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("bond_count 0"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("quality_flag missing"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("evidence_rows 0"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("tables_used risk_tensor_daily"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("filters_applied report_date=2026-02-28；desk=FI"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("不会在前端补算正式指标"));
      expect(emptyState).toHaveTextContent("已复制空持仓排查信息");
      expect(screen.queryByTestId("risk-tensor-brief")).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("ignores stale no-position copy results after empty evidence changes", async () => {
    const user = userEvent.setup();
    let resolveCopy: (() => void) | undefined;
    const writeText = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveCopy = resolve;
        }),
    );
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_empty_position_stale_copy_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi
      .fn()
      .mockResolvedValueOnce({
        result_meta: {
          ...buildMeta("risk.tensor", "tr_tensor_empty_position_stale_copy_initial"),
          quality_flag: "missing" as const,
          evidence_rows: 0,
          tables_used: ["risk_tensor_daily"],
          filters_applied: {
            report_date: "2026-02-28",
            desk: "FI",
          },
        },
        result: {
          ...tensorResult("2026-02-28"),
          bond_count: 0,
          quality_flag: "missing",
          warnings: [],
        } as RiskTensorPayload,
      })
      .mockResolvedValueOnce({
        result_meta: {
          ...buildMeta("risk.tensor", "tr_tensor_empty_position_stale_copy_refreshed"),
          quality_flag: "missing" as const,
          evidence_rows: 0,
          tables_used: ["risk_tensor_daily", "bond_position_snapshot"],
          filters_applied: {
            report_date: "2026-02-28",
            desk: "FI",
            refresh: "manual",
          },
        },
        result: {
          ...tensorResult("2026-02-28"),
          bond_count: 0,
          quality_flag: "missing",
          warnings: [],
        } as RiskTensorPayload,
      });

    try {
      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const emptyState = await screen.findByTestId("risk-tensor-empty-state");
      await user.click(within(emptyState).getByRole("button", { name: "复制空持仓排查信息" }));
      await user.click(within(emptyState).getByRole("button", { name: "重试主读面" }));

      await waitFor(() => {
        expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent(
          "tr_tensor_empty_position_stale_copy_refreshed",
        );
      });

      await act(async () => {
        resolveCopy?.();
      });

      const refreshedEmptyState = await screen.findByTestId("risk-tensor-empty-state");
      expect(refreshedEmptyState).toHaveTextContent("tables_used risk_tensor_daily / bond_position_snapshot");
      expect(refreshedEmptyState).not.toHaveTextContent("已复制空持仓排查信息");
      expect(screen.queryByTestId("risk-tensor-empty-position-manual-copy")).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("lets users jump from no-position context to result metadata", async () => {
    const user = userEvent.setup();
    const scrollTargets: Element[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_empty_position_meta_jump_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: {
        ...buildMeta("risk.tensor", `tr_tensor_empty_position_meta_jump_${reportDate}`),
        quality_flag: "missing" as const,
        evidence_rows: 0,
        tables_used: ["risk_tensor_daily"],
        filters_applied: {
          report_date: reportDate,
          desk: "FI",
        },
      },
      result: {
        ...tensorResult(reportDate),
        bond_count: 0,
        quality_flag: "missing",
        warnings: [],
      },
    }));

    try {
      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const emptyState = await screen.findByTestId("risk-tensor-empty-state");
      const metaPanel = await screen.findByTestId("risk-tensor-result-meta-panel");
      await user.click(within(emptyState).getByRole("button", { name: "定位元数据" }));

      expect(scrollTargets).toContain(metaPanel);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
      expect(screen.queryByTestId("risk-tensor-brief")).not.toBeInTheDocument();
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users retry the risk tensor main read from the no-position state", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_empty_position_retry_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi
      .fn()
      .mockResolvedValueOnce({
        result_meta: {
          ...buildMeta("risk.tensor", "tr_tensor_empty_position_retry_initial"),
          quality_flag: "missing" as const,
          evidence_rows: 0,
        },
        result: {
          ...tensorResult("2026-02-28"),
          bond_count: 0,
          quality_flag: "missing",
          warnings: [],
        },
      })
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor", "tr_tensor_empty_position_retry_success"),
        result: tensorResult("2026-02-28"),
      });

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const emptyState = await screen.findByTestId("risk-tensor-empty-state");
    expect(emptyState).toHaveTextContent("当前报告日无风险张量持仓");
    expect(screen.queryByTestId("risk-tensor-brief")).not.toBeInTheDocument();

    await user.click(within(emptyState).getByRole("button", { name: "重试主读面" }));

    await waitFor(() => {
      expect(getRiskTensor).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByTestId("risk-tensor-brief")).toHaveTextContent("报告日 2026-02-28");
    expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent(
      "tr_tensor_empty_position_retry_success",
    );
    expect(screen.queryByTestId("risk-tensor-empty-state")).not.toBeInTheDocument();
  });

  it("shows manual no-position diagnostic text when clipboard copy fails", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => {
      throw new Error("clipboard denied");
    });
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_empty_position_copy_failure_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: {
        ...buildMeta("risk.tensor", `tr_tensor_empty_position_copy_failure_${reportDate}`),
        quality_flag: "missing" as const,
        evidence_rows: 0,
        tables_used: ["risk_tensor_daily"],
        filters_applied: {
          report_date: reportDate,
          desk: "FI",
        },
      },
      result: {
        ...tensorResult(reportDate),
        bond_count: 0,
        quality_flag: "missing",
        warnings: [],
      },
    }));

    try {
      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const emptyState = await screen.findByTestId("risk-tensor-empty-state");
      await user.click(within(emptyState).getByRole("button", { name: "复制空持仓排查信息" }));

      await waitFor(() => {
        expect(emptyState).toHaveTextContent("复制失败，请手动选择空持仓排查信息");
      });

      const manualCopy = within(emptyState).getByTestId("risk-tensor-empty-position-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量空持仓排查信息");
      expect(manualCopy).toHaveTextContent("报告日 2026-02-28");
      expect(manualCopy).toHaveTextContent("trace_id tr_tensor_empty_position_copy_failure_2026-02-28");
      expect(manualCopy).toHaveTextContent("bond_count 0");
      expect(manualCopy).toHaveTextContent("quality_flag missing");
      expect(manualCopy).toHaveTextContent("evidence_rows 0");
      expect(manualCopy).toHaveTextContent("tables_used risk_tensor_daily");
      expect(manualCopy).toHaveTextContent("filters_applied report_date=2026-02-28；desk=FI");
      expect(manualCopy).toHaveTextContent("不会在前端补算正式指标");
      expect(screen.queryByTestId("risk-tensor-brief")).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("surfaces report-date list failures without hardcoded fallback", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => {
      throw new Error("Request failed: /api/risk/tensor/dates (503)");
    });
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const errorContext = await screen.findByTestId("risk-tensor-error-context");
    expect(errorContext).toHaveTextContent("风险报告日列表加载失败");
    expect(errorContext).toHaveTextContent("503");
    expect(errorContext).toHaveTextContent("不会回退到硬编码报告日");
    expect(getRiskTensor).not.toHaveBeenCalled();
  });

  it("copies report-date list failure diagnostic context", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async (_text: string) => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => {
      throw new Error("Request failed: /api/risk/tensor/dates (503)");
    });
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    try {
      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const errorContext = await screen.findByTestId("risk-tensor-error-context");
      await user.click(within(errorContext).getByRole("button", { name: "复制日期排查信息" }));

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量报告日列表加载失败排查信息"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("HTTP 状态 503"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("请求 /api/risk/tensor/dates"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("报告日参数 未选择"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("页面不会回退到硬编码报告日"));
      expect(errorContext).toHaveTextContent("已复制日期排查信息");
      expect(getRiskTensor).not.toHaveBeenCalled();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("lets users retry report-date governance from the failure context", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi
      .fn()
      .mockRejectedValueOnce(new Error("Request failed: /api/risk/tensor/dates (503)"))
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates_retry_success"),
        result: { report_dates: ["2026-02-28"] },
      });
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_dates_retry_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const errorContext = await screen.findByTestId("risk-tensor-error-context");
    expect(errorContext).toHaveTextContent("风险报告日列表加载失败");
    expect(getRiskTensor).not.toHaveBeenCalled();

    await user.click(within(errorContext).getByRole("button", { name: "重试日期治理" }));

    await waitFor(() => {
      expect(getRiskTensorDates).toHaveBeenCalledTimes(2);
      expect(getRiskTensor).toHaveBeenCalledWith("2026-02-28");
    });
    expect(await screen.findByTestId("risk-tensor-brief")).toHaveTextContent("报告日 2026-02-28");
    expect(screen.queryByTestId("risk-tensor-error-context")).not.toBeInTheDocument();
  });

  it("ignores stale report-date list failure copy results after retry evidence changes with the same status", async () => {
    const user = userEvent.setup();
    let resolveCopy: (() => void) | undefined;
    const writeText = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveCopy = resolve;
        }),
    );
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi
      .fn()
      .mockRejectedValueOnce(new Error("Request failed: /api/risk/tensor/dates?trace=initial (503)"))
      .mockRejectedValueOnce(new Error("Request failed: /api/risk/tensor/dates?trace=retry (503)"));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    try {
      renderRiskTensorRoute("/risk-tensor?report_date=2026-02-27", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const errorContext = await screen.findByTestId("risk-tensor-error-context");
      expect(errorContext).toHaveTextContent("HTTP 状态 503");

      await user.click(within(errorContext).getByRole("button", { name: "复制日期排查信息" }));
      await user.click(within(errorContext).getByRole("button", { name: "重试日期治理" }));

      await waitFor(() => {
        expect(getRiskTensorDates).toHaveBeenCalledTimes(2);
      });
      expect(screen.getByTestId("risk-tensor-error-context")).toHaveTextContent("HTTP 状态 503");

      await act(async () => {
        resolveCopy?.();
      });

      const retriedErrorContext = await screen.findByTestId("risk-tensor-error-context");
      expect(retriedErrorContext).not.toHaveTextContent("已复制日期排查信息");
      expect(within(retriedErrorContext).queryByTestId("risk-tensor-dates-error-manual-copy")).not.toBeInTheDocument();
      expect(getRiskTensor).not.toHaveBeenCalled();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("shows manual report-date list failure diagnostic text when clipboard copy fails", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => {
      throw new Error("clipboard denied");
    });
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => {
      throw new Error("Request failed: /api/risk/tensor/dates (503)");
    });
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    try {
      renderRiskTensorRoute("/risk-tensor?report_date=2026-02-27", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const errorContext = await screen.findByTestId("risk-tensor-error-context");
      await user.click(within(errorContext).getByRole("button", { name: "复制日期排查信息" }));

      await waitFor(() => {
        expect(errorContext).toHaveTextContent("复制失败，请手动选择日期排查信息");
      });

      const manualCopy = within(errorContext).getByTestId("risk-tensor-dates-error-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量报告日列表加载失败排查信息");
      expect(manualCopy).toHaveTextContent("HTTP 状态 503");
      expect(manualCopy).toHaveTextContent("错误 Request failed: /api/risk/tensor/dates (503)");
      expect(manualCopy).toHaveTextContent("请求 /api/risk/tensor/dates");
      expect(manualCopy).toHaveTextContent("报告日参数 2026-02-27");
      expect(manualCopy).toHaveTextContent("页面不会回退到硬编码报告日");
      expect(manualCopy).toHaveTextContent("主读面未读取");
      expect(getRiskTensor).not.toHaveBeenCalled();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("does not load an explicit report date when report-date governance fails", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => {
      throw new Error("Request failed: /api/risk/tensor/dates (503)");
    });
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    renderRiskTensorRoute("/risk-tensor?report_date=2026-02-27", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const errorContext = await screen.findByTestId("risk-tensor-error-context");
    expect(errorContext).toHaveTextContent("风险报告日列表加载失败");
    expect(errorContext).toHaveTextContent("503");
    expect(errorContext).toHaveTextContent("不会回退到硬编码报告日");
    expect(getRiskTensor).not.toHaveBeenCalled();
  });

  it("lets users jump from risk tensor API failure context to result metadata", async () => {
    const user = userEvent.setup();
    const scrollTargets: Element[] = [];
    const scrollOptions: unknown[] = [];
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_error_meta_jump_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async () => {
      throw new Error("Request failed: /api/risk/tensor?report_date=2026-03-15 (404)");
    });

    try {
      renderRiskTensorRoute("/risk-tensor?report_date=2026-03-15", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const errorContext = await screen.findByTestId("risk-tensor-error-context");
      const metaPanel = await screen.findByTestId("risk-tensor-result-meta-panel");
      await user.click(within(errorContext).getByRole("button", { name: "定位元数据" }));

      expect(scrollTargets).toContain(metaPanel);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users retry the risk tensor main read from the failure context", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_error_retry_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi
      .fn()
      .mockRejectedValueOnce(new Error("Request failed: /api/risk/tensor?report_date=2026-03-15 (404)"))
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor", "tr_tensor_retry_success"),
        result: tensorResult("2026-03-15"),
      });

    renderRiskTensorRoute("/risk-tensor?report_date=2026-03-15", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const errorContext = await screen.findByTestId("risk-tensor-error-context");
    expect(errorContext).toHaveTextContent("当前报告日无风险张量数据");
    expect(getRiskTensor).toHaveBeenCalledTimes(1);

    await user.click(within(errorContext).getByRole("button", { name: "重试主读面" }));

    await waitFor(() => {
      expect(getRiskTensor).toHaveBeenCalledTimes(2);
      expect(getRiskTensor).toHaveBeenLastCalledWith("2026-03-15");
    });
    expect(await screen.findByTestId("risk-tensor-brief")).toHaveTextContent("报告日 2026-03-15");
    expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent("tr_tensor_retry_success");
    expect(screen.queryByTestId("risk-tensor-error-context")).not.toBeInTheDocument();
  });

  it("ignores stale risk tensor failure copy results after retry evidence changes", async () => {
    const user = userEvent.setup();
    let resolveCopy: (() => void) | undefined;
    const writeText = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveCopy = resolve;
        }),
    );
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_error_stale_copy_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi
      .fn()
      .mockRejectedValueOnce(new Error("Request failed: /api/risk/tensor?report_date=2026-03-15 (404)"))
      .mockRejectedValueOnce(new Error("Request failed: /api/risk/tensor?report_date=2026-03-15 (503)"));

    try {
      renderRiskTensorRoute("/risk-tensor?report_date=2026-03-15", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const errorContext = await screen.findByTestId("risk-tensor-error-context");
      expect(errorContext).toHaveTextContent("当前报告日无风险张量数据");
      expect(errorContext).toHaveTextContent("HTTP 状态 404");

      await user.click(within(errorContext).getByRole("button", { name: "复制排查信息" }));
      await user.click(within(errorContext).getByRole("button", { name: "重试主读面" }));

      await waitFor(() => {
        expect(screen.getByTestId("risk-tensor-error-context")).toHaveTextContent("风险张量治理前置缺失");
      });
      expect(screen.getByTestId("risk-tensor-error-context")).toHaveTextContent("HTTP 状态 503");

      await act(async () => {
        resolveCopy?.();
      });

      const retriedErrorContext = await screen.findByTestId("risk-tensor-error-context");
      expect(retriedErrorContext).not.toHaveTextContent("已复制排查信息");
      expect(within(retriedErrorContext).queryByTestId("risk-tensor-error-manual-copy")).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("keeps risk tensor failure copy feedback cleared when retry returns the same failure evidence", async () => {
    const user = userEvent.setup();
    let resolveCopy: (() => void) | undefined;
    const writeText = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveCopy = resolve;
        }),
    );
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_error_same_evidence_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async () => {
      throw new Error("Request failed: /api/risk/tensor?report_date=2026-03-15 (404)");
    });

    try {
      renderRiskTensorRoute("/risk-tensor?report_date=2026-03-15", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const errorContext = await screen.findByTestId("risk-tensor-error-context");
      const [, retryMainRead, copyTensorError] = within(errorContext).getAllByRole("button");
      await user.click(copyTensorError!);
      await user.click(retryMainRead!);

      await waitFor(() => {
        expect(getRiskTensor).toHaveBeenCalledTimes(2);
      });

      await act(async () => {
        resolveCopy?.();
      });

      const retriedErrorContext = await screen.findByTestId("risk-tensor-error-context");
      expect(retriedErrorContext.querySelector(".risk-tensor-quality-detail__trace-feedback")).toBeNull();
      expect(within(retriedErrorContext).queryByTestId("risk-tensor-error-manual-copy")).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("shows manual risk tensor failure diagnostic text when clipboard copy fails", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => {
      throw new Error("clipboard denied");
    });
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_error_copy_failure_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async () => {
      throw new Error("Request failed: /api/risk/tensor?report_date=2026-03-15 (404)");
    });

    try {
      renderRiskTensorRoute("/risk-tensor?report_date=2026-03-15", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const errorContext = await screen.findByTestId("risk-tensor-error-context");
      await user.click(within(errorContext).getByRole("button", { name: "复制排查信息" }));

      await waitFor(() => {
        expect(errorContext).toHaveTextContent("复制失败，请手动选择排查信息");
      });

      const manualCopy = within(errorContext).getByTestId("risk-tensor-error-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量主读面加载失败排查信息");
      expect(manualCopy).toHaveTextContent("报告日 2026-03-15");
      expect(manualCopy).toHaveTextContent("HTTP 状态 404");
      expect(manualCopy).toHaveTextContent("日期治理 trace_id tr_tensor_error_copy_failure_dates");
      expect(manualCopy).toHaveTextContent("basis formal");
      expect(manualCopy).toHaveTextContent("cache_version cv_tensor_test");
      expect(manualCopy).toHaveTextContent("generated_at 2026-04-12T08:00:00Z");
      expect(manualCopy).toHaveTextContent("source_version sv_tensor_test");
      expect(manualCopy).toHaveTextContent("rule_version rv_tensor_test");
      expect(manualCopy).toHaveTextContent("主读面 trace_id 未提供");
      expect(manualCopy).toHaveTextContent("不会使用缓存或前端补算替代正式主读结果");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });
});
