import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { vi } from "vitest";

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
import type { ResultMeta, RiskTensorPayload } from "../api/contracts";
import { routerFuture } from "../router/routerFuture";
import { displayTokens } from "../theme/displayTokens";
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

function dv01ControlsFixture(
  overrides: Partial<NonNullable<RiskTensorPayload["dv01_controls"]>> = {},
): NonNullable<RiskTensorPayload["dv01_controls"]> {
  return {
    basis: "regulatory_dv01",
    limit_status: "pending_configuration",
    approved_limit_dv01: null,
    limit_usage_ratio: null,
    volatility_status: "pending_market_volatility",
    daily_rate_volatility_bp: null,
    dominant_krd_bucket: "5Y",
    dominant_krd: {
      raw: 3,
      unit: "dv01",
      display: "+3.00",
      precision: 2,
      sign_aware: true,
    },
    stress_scenarios: [],
    operating_judgement: "DV01 controls require configuration.",
    control_actions: [],
    control_message: "Limit configuration is pending.",
    action_hint: "Configure approved DV01 limit.",
    ...overrides,
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

  it("lets users jump from the first-screen DV01 control tile to the control detail", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_dv01_jump_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          dv01_controls: dv01ControlsFixture(),
        } as RiskTensorPayload,
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      const dv01Action = within(brief).getByTestId("risk-tensor-dv01-controls-action");
      const controls = await screen.findByTestId("risk-tensor-dv01-controls");

      await user.click(dv01Action);

      expect(scrollTargets).toContain(controls);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users jump from the first-screen required information tile to DV01 actions", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_required_action_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_required_action_jump_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          dv01_controls: dv01ControlsFixture({
            control_actions: [
              {
                key: "approved_dv01_limit",
                title: "Configure approved DV01 limit",
                status: "required",
                evidence: "Approved limit is missing.",
                action: "Connect approved limit source.",
              },
            ],
          }),
        } as RiskTensorPayload,
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      const requiredAction = within(brief).getByTestId("risk-tensor-required-action");
      const actions = await screen.findByTestId("risk-tensor-dv01-actions");
      expect(requiredAction).toHaveTextContent("Configure approved DV01 limit");
      expect(actions).toHaveTextContent("Configure approved DV01 limit");

      await user.click(requiredAction);

      expect(scrollTargets).toContain(actions);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users jump from the first-screen required information tile to quality detail", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_required_info_quality_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const qualityWarning = "Quality warning needs review.";
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_required_info_quality_jump_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          warnings: [qualityWarning],
          dv01_controls: dv01ControlsFixture(),
        } as RiskTensorPayload,
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      const requiredAction = within(brief).getByTestId("risk-tensor-required-action");
      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");
      expect(requiredAction).toHaveTextContent(qualityWarning);

      await user.click(requiredAction);

      expect(scrollTargets).toContain(qualityDetail);
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
        result: tensorResult(reportDate),
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

      await user.click(copyEvidence);

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("trace_id tr_tensor_meta_copy_2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("报告日 2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("复核状态 待复核"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("source_version sv_tensor_test"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("rule_version rv_tensor_test"));
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
    expect(within(issuerHhi).getByText("0.18")).toHaveStyle({ color: displayTokens.kpi.valueDefault });
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

  it("lets users jump from prior-period liquidity change to liquidity gap detail", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_prior_liquidity_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_prior_liquidity_jump_${reportDate}`),
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const priorChange = await screen.findByTestId("risk-tensor-prior-period-change");
      const liquidityAction = within(priorChange).getByTestId(
        "risk-tensor-prior-change-action-liquidity_gap_30d_ratio",
      );
      const liquidityGapDetail = await screen.findByTestId("risk-tensor-liquidity-gap-detail");

      await user.click(liquidityAction);

      expect(scrollTargets).toContain(liquidityGapDetail);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("falls back from prior-period DV01 change to the KPI grid when controls are absent", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_prior_dv01_fallback_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_prior_dv01_fallback_${reportDate}`),
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const priorChange = await screen.findByTestId("risk-tensor-prior-period-change");
      const regulatoryDv01Action = within(priorChange).getByTestId(
        "risk-tensor-prior-change-action-regulatory_dv01",
      );
      const kpiGrid = await screen.findByTestId("risk-tensor-kpi-grid");

      expect(screen.queryByTestId("risk-tensor-dv01-controls")).not.toBeInTheDocument();
      expect(regulatoryDv01Action.querySelector("p, small")).toBeNull();

      await user.click(regulatoryDv01Action);

      expect(scrollTargets).toContain(kpiGrid);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
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

  it("keeps unparseable KRD buckets out of frontend chart magnitudes and dominant bucket fallback", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_krd_payload_quality_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_krd_payload_quality_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        krd_1y: "10000",
        krd_3y: "90000",
        krd_5y: "not-a-number",
        krd_7y: "25000",
        krd_10y: "15000",
        krd_30y: "5000",
        dv01_controls: null,
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const brief = await screen.findByTestId("risk-tensor-brief");
    expect(brief).toHaveTextContent("主风险桶 3Y");

    const krdChart = screen.getAllByTestId("risk-tensor-echarts-stub")[1]!;
    expect(JSON.parse(krdChart.getAttribute("data-series") ?? "[]")).toEqual([1, 9, null, 2.5, 1.5, 0.5]);

    const drill = await screen.findByTestId("risk-tensor-tenor-drill");
    expect(drill).toHaveTextContent("当前桶：3Y");
    expect(drill).toHaveTextContent("krd_5y 不可解析");
    expect(drill).toHaveTextContent("未参与前端主风险桶排序和图表数值");
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

  it("surfaces a DV01 stress scenario no-data state when backend scenarios are empty", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_stress_empty_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_dv01_stress_empty_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        dv01_controls: dv01ControlsFixture({ stress_scenarios: [] }),
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const stressScenarios = await screen.findByTestId("risk-tensor-dv01-stress-scenarios");
    expect(stressScenarios).toHaveTextContent("暂无压力情景");
    expect(stressScenarios).toHaveTextContent("stress_scenarios");
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

  it("blocks a URL-selected report date that backend marked stale", async () => {
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

  it("renders default mock risk tensor controls and prior-period context", async () => {
    const client = createApiClient({ mode: "mock" });

    renderRiskTensorRoute("/risk-tensor", client);

    const priorChange = await screen.findByTestId("risk-tensor-prior-period-change");
    expect(priorChange).toHaveTextContent("暂无可比较的上一报告日");

    const controls = await screen.findByTestId("risk-tensor-dv01-controls");
    expect(controls).toHaveTextContent("DV01");
    expect(controls).toHaveTextContent("配置审批限额");
    expect(controls).toHaveTextContent("接入利率波动");
    expect(controls).toHaveTextContent("+10bp");
    expect(controls).toHaveTextContent("未接入正式限额源");
    expect(controls).not.toHaveTextContent("pending_configuration");
  });

  it.each([
    [404, "当前报告日无风险张量数据", "2026-03-15"],
    [503, "风险张量治理前置缺失", "2026-03-16"],
  ])("surfaces risk tensor %s API failures with business context", async (statusCode, message, reportDate) => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_error_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async () => {
      throw new Error(`Request failed: /api/risk/tensor?report_date=${reportDate} (${statusCode})`);
    });

    renderRiskTensorRoute(`/risk-tensor?report_date=${reportDate}`, {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const errorContext = await screen.findByTestId("risk-tensor-error-context");
    expect(errorContext).toHaveTextContent(message);
    expect(errorContext).toHaveTextContent(reportDate);
    expect(errorContext).toHaveTextContent(String(statusCode));
    expect(errorContext).toHaveTextContent("日期治理 trace_id tr_tensor_error_dates");
    expect(errorContext).toHaveTextContent("主读面 trace_id 未提供");
    expect(errorContext).toHaveTextContent("不会使用缓存或前端补算替代正式主读结果");
  });
});
