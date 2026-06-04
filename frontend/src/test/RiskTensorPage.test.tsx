import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { act, render, screen, waitFor, within } from "@testing-library/react";
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

  it("lets users retry the risk tensor main read when DV01 controls are missing from the first screen", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_missing_retry_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi
      .fn()
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor", "tr_tensor_dv01_missing_retry_initial"),
        result: {
          ...tensorResult("2026-02-28"),
          dv01_controls: null,
        },
      })
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor", "tr_tensor_dv01_missing_retry_success"),
        result: {
          ...tensorResult("2026-02-28"),
          dv01_controls: dv01ControlsFixture(),
        },
      });

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const brief = await screen.findByTestId("risk-tensor-brief");
    expect(brief).toHaveTextContent("控制未接入");
    expect(getRiskTensor).toHaveBeenCalledTimes(1);

    await user.click(within(brief).getByRole("button", { name: "重试主读面" }));

    await waitFor(() => {
      expect(getRiskTensor).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByTestId("risk-tensor-dv01-controls")).toHaveTextContent("Limit configuration is pending.");
    expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent("tr_tensor_dv01_missing_retry_success");
    expect(screen.getByTestId("risk-tensor-brief")).not.toHaveTextContent("控制未接入");
  });

  it("lets users locate metadata when DV01 controls are missing from the first screen", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_missing_meta_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_dv01_missing_meta_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          dv01_controls: null,
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      const metaPanel = await screen.findByTestId("risk-tensor-result-meta-panel");
      expect(brief).toHaveTextContent("控制未接入");

      await user.click(within(brief).getByRole("button", { name: "定位元数据" }));

      expect(scrollTargets).toContain(metaPanel);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users jump from required information to missing DV01 control diagnostics", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_missing_required_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_dv01_missing_required_jump_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          warnings: [],
          dv01_controls: null,
        } as RiskTensorPayload,
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      const requiredAction = within(brief).getByTestId("risk-tensor-required-action");
      const missingControls = within(brief).getByTestId("risk-tensor-dv01-missing-controls");

      await user.click(requiredAction);

      expect(scrollTargets).toContain(missingControls);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("copies DV01 control payload diagnostic context when controls are missing from the first screen", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_missing_copy_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_dv01_missing_copy_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          dv01_controls: null,
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      await user.click(within(brief).getByRole("button", { name: "复制控制排查信息" }));

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量 DV01 控制载荷缺失排查信息"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("报告日 2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("trace_id tr_tensor_dv01_missing_copy_2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("监管口径 DV01"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("dv01_controls 未提供"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("不会在前端补算 DV01 控制载荷"));
      expect(brief).toHaveTextContent("已复制控制排查信息");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("shows manual DV01 control diagnostic text when missing-control copying fails", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_missing_copy_failure_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_dv01_missing_copy_failure_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          dv01_controls: null,
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      await user.click(within(brief).getByRole("button", { name: "复制控制排查信息" }));

      await waitFor(() => {
        expect(brief).toHaveTextContent("复制失败，请手动选择控制排查信息");
      });
      const manualCopy = within(brief).getByTestId("risk-tensor-dv01-missing-controls-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量 DV01 控制载荷缺失排查信息");
      expect(manualCopy).toHaveTextContent("trace_id tr_tensor_dv01_missing_copy_failure_2026-02-28");
      expect(manualCopy).toHaveTextContent("dv01_controls 未提供");
      expect(manualCopy).toHaveTextContent("不会在前端补算 DV01 控制载荷");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("resets missing DV01 control copy feedback when regulatory DV01 changes", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_missing_feedback_reset_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi
        .fn()
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_dv01_missing_feedback_reset"),
          result: {
            ...tensorResult("2026-02-28"),
            regulatory_dv01: "120000",
            dv01_controls: null,
          } as RiskTensorPayload,
        })
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_dv01_missing_feedback_reset"),
          result: {
            ...tensorResult("2026-02-28"),
            regulatory_dv01: "240000",
            dv01_controls: null,
          } as RiskTensorPayload,
        });

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      await user.click(within(brief).getByRole("button", { name: "复制控制排查信息" }));

      await waitFor(() => {
        expect(brief).toHaveTextContent("已复制控制排查信息");
      });

      await user.click(within(brief).getByRole("button", { name: "重试主读面" }));

      await waitFor(() => {
        expect(brief).toHaveTextContent("24.00 万元");
      });
      expect(brief).not.toHaveTextContent("已复制控制排查信息");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
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

  it("lets users jump from first-screen no-required-action status to DV01 controls", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_no_required_action_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_no_required_action_jump_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          warnings: [],
          dv01_controls: dv01ControlsFixture({ control_actions: [] }),
        } as RiskTensorPayload,
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      const requiredAction = within(brief).getByTestId("risk-tensor-required-action");
      const controls = await screen.findByTestId("risk-tensor-dv01-controls");
      expect(requiredAction).toHaveTextContent("暂无必做项");

      await user.click(requiredAction);

      expect(scrollTargets).toContain(controls);
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

  it("lets users jump from the radar duration dimension to the duration KPI card when scope disclosure is absent", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_radar_duration_kpi_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_radar_duration_kpi_jump_${reportDate}`),
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const durationCard = await screen.findByTestId("risk-tensor-duration-kpi");
      const radarAction = await screen.findByTestId("risk-tensor-radar-action-duration");

      await user.click(radarAction);

      expect(scrollTargets).toContain(durationCard);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users jump from the radar DV01 dimension to missing control diagnostics", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_radar_dv01_missing_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_radar_dv01_missing_jump_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          warnings: [],
          dv01_controls: null,
        } as RiskTensorPayload,
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const brief = await screen.findByTestId("risk-tensor-brief");
      const missingControls = within(brief).getByTestId("risk-tensor-dv01-missing-controls");
      const radarAction = await screen.findByTestId("risk-tensor-radar-action-dv01");

      await user.click(radarAction);

      expect(scrollTargets).toContain(missingControls);
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

  it("lets users jump from prior-period no-data state to result metadata", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_no_prior_meta_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_no_prior_meta_${reportDate}`),
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
      const metaPanel = await screen.findByTestId("risk-tensor-result-meta-panel");

      await user.click(within(priorChange).getByRole("button", { name: "定位元数据" }));

      expect(scrollTargets).toContain(metaPanel);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("copies prior-period diagnostic context when comparison data is unavailable", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_no_prior_copy_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_no_prior_copy_${reportDate}`),
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
      await user.click(within(priorChange).getByRole("button", { name: "复制上期排查信息" }));

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量较上期变化排查信息"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("报告日 2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("trace_id tr_tensor_no_prior_copy_2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("状态 no_prior"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("摘要 no prior comparable data"));
      expect(priorChange).toHaveTextContent("已复制上期排查信息");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("copies prior-period diagnostic context when comparison metrics are available", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_prior_available_copy_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_prior_available_copy_${reportDate}`),
        result: tensorResult(reportDate),
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const priorChange = await screen.findByTestId("risk-tensor-prior-period-change");
      expect(priorChange).toHaveTextContent("监管口径 DV01");

      await user.click(within(priorChange).getByRole("button", { name: "复制上期排查信息" }));

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量较上期变化排查信息"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("trace_id tr_tensor_prior_available_copy_2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("状态 available"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("对比日期 2026-02-27"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("metrics_count 2"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("metric[1] 监管口径 DV01"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("current 12.34"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("previous 8.00"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("delta +4.34"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("interpretation 监管口径 DV01 扩大"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("metric[2] 30 日流动性缺口比例"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("current 5.0%"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("previous 3.0%"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("delta +2.0%"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("interpretation 30 日流动性缓冲改善"));
      await waitFor(() => {
        expect(priorChange).toHaveTextContent("已复制上期排查信息");
      });
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("resets prior-period diagnostic copy feedback when quality flag changes", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_prior_feedback_reset_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi
        .fn()
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_prior_feedback_reset"),
          result: {
            ...tensorResult("2026-02-28"),
            quality_flag: "warning",
          } as RiskTensorPayload,
        })
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_prior_feedback_reset"),
          result: {
            ...tensorResult("2026-02-28"),
            quality_flag: "stale",
          } as RiskTensorPayload,
        });

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const priorChange = await screen.findByTestId("risk-tensor-prior-period-change");
      await user.click(within(priorChange).getByRole("button", { name: "复制上期排查信息" }));

      await waitFor(() => {
        expect(priorChange).toHaveTextContent("已复制上期排查信息");
      });

      await user.click(within(priorChange).getByRole("button", { name: "重试主读面" }));

      await waitFor(() => {
        expect(screen.getByTestId("risk-tensor-data-status-action")).toHaveTextContent("陈旧");
      });
      expect(screen.getByTestId("risk-tensor-prior-period-change")).not.toHaveTextContent("已复制上期排查信息");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("resets prior-period diagnostic copy feedback when metric evidence changes", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_prior_metric_feedback_reset_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const changedPriorPeriod = {
        ...tensorResult("2026-02-28").prior_period_change!,
        metrics: tensorResult("2026-02-28").prior_period_change!.metrics.map((metric) =>
          metric.key === "regulatory_dv01"
            ? {
                ...metric,
                delta_display: "+9.99",
                interpretation: "监管口径 DV01 显著扩大",
              }
            : metric,
        ),
      };
      const getRiskTensor = vi
        .fn()
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_prior_metric_feedback_reset"),
          result: tensorResult("2026-02-28"),
        })
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_prior_metric_feedback_reset"),
          result: {
            ...tensorResult("2026-02-28"),
            prior_period_change: changedPriorPeriod,
          } as RiskTensorPayload,
        });

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const priorChange = await screen.findByTestId("risk-tensor-prior-period-change");
      await user.click(within(priorChange).getByRole("button", { name: "复制上期排查信息" }));

      await waitFor(() => {
        expect(priorChange).toHaveTextContent("已复制上期排查信息");
      });

      await user.click(within(priorChange).getByRole("button", { name: "重试主读面" }));

      await waitFor(() => {
        expect(screen.getByTestId("risk-tensor-prior-period-change")).toHaveTextContent("监管口径 DV01 显著扩大");
      });
      expect(screen.getByTestId("risk-tensor-prior-period-change")).not.toHaveTextContent("已复制上期排查信息");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("ignores stale prior-period copy failures after metric evidence changes", async () => {
    const user = userEvent.setup();
    let rejectCopy: ((error: Error) => void) | undefined;
    const writeText = vi.fn(
      () =>
        new Promise<void>((_resolve, reject) => {
          rejectCopy = reject;
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_prior_metric_stale_failure_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const changedPriorPeriod = {
        ...tensorResult("2026-02-28").prior_period_change!,
        metrics: tensorResult("2026-02-28").prior_period_change!.metrics.map((metric) =>
          metric.key === "regulatory_dv01"
            ? {
                ...metric,
                delta_display: "+9.99",
                interpretation: "监管口径 DV01 显著扩大",
              }
            : metric,
        ),
      };
      const getRiskTensor = vi
        .fn()
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_prior_metric_stale_failure"),
          result: tensorResult("2026-02-28"),
        })
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_prior_metric_stale_failure"),
          result: {
            ...tensorResult("2026-02-28"),
            prior_period_change: changedPriorPeriod,
          } as RiskTensorPayload,
        });

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const priorChange = await screen.findByTestId("risk-tensor-prior-period-change");
      await user.click(within(priorChange).getByRole("button", { name: "复制上期排查信息" }));
      await user.click(within(priorChange).getByRole("button", { name: "重试主读面" }));

      await waitFor(() => {
        expect(screen.getByTestId("risk-tensor-prior-period-change")).toHaveTextContent("监管口径 DV01 显著扩大");
      });

      await act(async () => {
        rejectCopy?.(new Error("clipboard unavailable"));
      });

      expect(screen.getByTestId("risk-tensor-prior-period-change")).not.toHaveTextContent(
        "复制失败，请手动选择上期排查信息",
      );
      expect(screen.queryByTestId("risk-tensor-prior-period-manual-copy")).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("shows manual prior-period diagnostic text when clipboard copy fails", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_prior_missing_copy_failure_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_prior_missing_copy_failure_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          prior_period_change: null,
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const priorChange = await screen.findByTestId("risk-tensor-prior-period-change");
      await user.click(within(priorChange).getByRole("button", { name: "复制上期排查信息" }));

      await waitFor(() => {
        expect(priorChange).toHaveTextContent("复制失败，请手动选择上期排查信息");
      });
      const manualCopy = within(priorChange).getByTestId("risk-tensor-prior-period-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量较上期变化排查信息");
      expect(manualCopy).toHaveTextContent("trace_id tr_tensor_prior_missing_copy_failure_2026-02-28");
      expect(manualCopy).toHaveTextContent("状态 missing");
      expect(manualCopy).toHaveTextContent("后端未返回上期变化载荷");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("lets users retry the risk tensor main read from the prior-period no-data state", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_no_prior_retry_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi
      .fn()
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor", "tr_tensor_no_prior_retry_initial"),
        result: {
          ...tensorResult("2026-02-28"),
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
      })
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor", "tr_tensor_no_prior_retry_success"),
        result: tensorResult("2026-02-28"),
      });

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const priorChange = await screen.findByTestId("risk-tensor-prior-period-change");
    expect(priorChange).toHaveTextContent("no prior comparable data");
    expect(priorChange.querySelectorAll(".risk-tensor-prior-change__metric")).toHaveLength(0);

    await user.click(within(priorChange).getByRole("button", { name: "重试主读面" }));

    await waitFor(() => {
      expect(getRiskTensor).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByTestId("risk-tensor-prior-period-change")).toHaveTextContent("监管口径 DV01");
    expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent("tr_tensor_no_prior_retry_success");
  });

  it("surfaces a traceable prior-period payload missing state", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_prior_missing_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_prior_missing_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          prior_period_change: null,
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const priorChange = await screen.findByTestId("risk-tensor-prior-period-change");
      const metaPanel = await screen.findByTestId("risk-tensor-result-meta-panel");
      expect(priorChange).toHaveTextContent("后端未返回上期变化载荷");
      expect(priorChange).toHaveTextContent("trace_id tr_tensor_prior_missing_2026-02-28");
      expect(priorChange.querySelectorAll(".risk-tensor-prior-change__metric")).toHaveLength(0);

      await user.click(within(priorChange).getByRole("button", { name: "定位元数据" }));

      expect(scrollTargets).toContain(metaPanel);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users retry the risk tensor main read when prior-period payload is missing", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_prior_missing_retry_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi
      .fn()
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor", "tr_tensor_prior_missing_retry_initial"),
        result: {
          ...tensorResult("2026-02-28"),
          prior_period_change: null,
        },
      })
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor", "tr_tensor_prior_missing_retry_success"),
        result: tensorResult("2026-02-28"),
      });

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const priorChange = await screen.findByTestId("risk-tensor-prior-period-change");
    expect(priorChange).toHaveTextContent("后端未返回上期变化载荷");

    await user.click(within(priorChange).getByRole("button", { name: "重试主读面" }));

    await waitFor(() => {
      expect(getRiskTensor).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByTestId("risk-tensor-prior-period-change")).toHaveTextContent("监管口径 DV01");
    expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent(
      "tr_tensor_prior_missing_retry_success",
    );
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

  it("selects the current KRD bucket when users open the prior-period bucket change", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_prior_krd_select_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_prior_krd_select_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          prior_period_change: {
            ...tensorResult(reportDate).prior_period_change,
            status: tensorResult(reportDate).prior_period_change?.status ?? "available",
            comparison_report_date: tensorResult(reportDate).prior_period_change?.comparison_report_date ?? "2026-02-27",
            summary: tensorResult(reportDate).prior_period_change?.summary ?? "主风险桶切换",
            dominant_krd_bucket: tensorResult(reportDate).prior_period_change?.dominant_krd_bucket ?? "5Y",
            previous_dominant_krd_bucket:
              tensorResult(reportDate).prior_period_change?.previous_dominant_krd_bucket ?? "3Y",
            dominant_krd_shifted: tensorResult(reportDate).prior_period_change?.dominant_krd_shifted ?? true,
            metrics: [
              ...(tensorResult(reportDate).prior_period_change?.metrics ?? []),
              {
                key: "dominant_krd_bucket",
                label: "主风险桶",
                current: {
                  raw: null,
                  unit: "count" as const,
                  display: "5Y",
                  precision: 0,
                  sign_aware: false,
                },
                previous: {
                  raw: null,
                  unit: "count" as const,
                  display: "3Y",
                  precision: 0,
                  sign_aware: false,
                },
                delta: {
                  raw: null,
                  unit: "count" as const,
                  display: "5Y - 3Y",
                  precision: 0,
                  sign_aware: false,
                },
                current_display: "5Y",
                previous_display: "3Y",
                delta_display: "5Y - 3Y",
                direction: "changed",
                tone: "warning",
                interpretation: "主风险桶切换",
              },
            ],
          },
        } as RiskTensorPayload,
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

      const priorChange = await screen.findByTestId("risk-tensor-prior-period-change");
      const krdAction = within(priorChange).getByTestId("risk-tensor-prior-change-action-dominant_krd_bucket");
      await user.click(krdAction);

      expect(scrollTargets).toContain(tenorDrill);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
      await waitFor(() => {
        expect(within(tenorDrill).getByText("5Y", { selector: "strong" })).toBeInTheDocument();
        expect(within(tenorDrill).getByRole("button", { name: "5Y" })).toHaveAttribute("aria-pressed", "true");
      });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("opens KRD field review when the prior-period current bucket is not in the tenor rows", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_prior_krd_unmapped_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_prior_krd_unmapped_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          krd_7y: "bad",
          prior_period_change: {
            ...tensorResult(reportDate).prior_period_change,
            status: tensorResult(reportDate).prior_period_change?.status ?? "available",
            comparison_report_date: tensorResult(reportDate).prior_period_change?.comparison_report_date ?? "2026-02-27",
            summary: tensorResult(reportDate).prior_period_change?.summary ?? "主风险桶待复核",
            dominant_krd_bucket: "9Y",
            previous_dominant_krd_bucket:
              tensorResult(reportDate).prior_period_change?.previous_dominant_krd_bucket ?? "3Y",
            dominant_krd_shifted: true,
            metrics: [
              ...(tensorResult(reportDate).prior_period_change?.metrics ?? []),
              {
                key: "dominant_krd_bucket",
                label: "主风险桶",
                current: {
                  raw: null,
                  unit: "count" as const,
                  display: "9Y",
                  precision: 0,
                  sign_aware: false,
                },
                previous: {
                  raw: null,
                  unit: "count" as const,
                  display: "3Y",
                  precision: 0,
                  sign_aware: false,
                },
                delta: {
                  raw: null,
                  unit: "count" as const,
                  display: "9Y - 3Y",
                  precision: 0,
                  sign_aware: false,
                },
                current_display: "9Y",
                previous_display: "3Y",
                delta_display: "9Y - 3Y",
                direction: "changed",
                tone: "warning",
                interpretation: "主风险桶待复核",
              },
            ],
          },
        } as RiskTensorPayload,
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const priorChange = await screen.findByTestId("risk-tensor-prior-period-change");
      const krdAction = within(priorChange).getByTestId("risk-tensor-prior-change-action-dominant_krd_bucket");
      const qualityNote = await screen.findByTestId("risk-tensor-krd-quality-note");

      await user.click(krdAction);

      expect(scrollTargets).toContain(qualityNote);
      expect(scrollTargets.at(-1)).toBe(qualityNote);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("falls back from prior-period KRD bucket change to KRD quality review when every bucket is unparseable", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_prior_krd_quality_fallback_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_prior_krd_quality_fallback_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          krd_1y: "bad",
          krd_3y: "",
          krd_5y: "undefined",
          krd_7y: "bad",
          krd_10y: "NaN",
          krd_30y: "missing",
          prior_period_change: {
            ...tensorResult(reportDate).prior_period_change,
            status: tensorResult(reportDate).prior_period_change?.status ?? "available",
            comparison_report_date: tensorResult(reportDate).prior_period_change?.comparison_report_date ?? "2026-02-27",
            summary: tensorResult(reportDate).prior_period_change?.summary ?? "主风险桶切换",
            dominant_krd_bucket: tensorResult(reportDate).prior_period_change?.dominant_krd_bucket ?? "5Y",
            previous_dominant_krd_bucket:
              tensorResult(reportDate).prior_period_change?.previous_dominant_krd_bucket ?? "3Y",
            dominant_krd_shifted: tensorResult(reportDate).prior_period_change?.dominant_krd_shifted ?? true,
            metrics: [
              ...(tensorResult(reportDate).prior_period_change?.metrics ?? []),
              {
                key: "dominant_krd_bucket",
                label: "主风险桶",
                current: {
                  raw: null,
                  unit: "count" as const,
                  display: "5Y",
                  precision: 0,
                  sign_aware: false,
                },
                previous: {
                  raw: null,
                  unit: "count" as const,
                  display: "3Y",
                  precision: 0,
                  sign_aware: false,
                },
                delta: {
                  raw: null,
                  unit: "count" as const,
                  display: "5Y - 3Y",
                  precision: 0,
                  sign_aware: false,
                },
                current_display: "5Y",
                previous_display: "3Y",
                delta_display: "5Y - 3Y",
                direction: "changed",
                tone: "warning",
                interpretation: "主风险桶切换",
              },
            ],
          },
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const priorChange = await screen.findByTestId("risk-tensor-prior-period-change");
      const krdAction = within(priorChange).getByTestId("risk-tensor-prior-change-action-dominant_krd_bucket");
      const qualityNote = await screen.findByTestId("risk-tensor-krd-quality-note");
      expect(screen.queryByTestId("risk-tensor-tenor-drill")).not.toBeInTheDocument();

      await user.click(krdAction);

      expect(scrollTargets).toContain(qualityNote);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("falls back from prior-period regulatory DV01 change to the regulatory DV01 KPI card when controls are absent", async () => {
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
      const regulatoryDv01Card = await screen.findByTestId("risk-tensor-regulatory-dv01-kpi");

      expect(screen.queryByTestId("risk-tensor-dv01-controls")).not.toBeInTheDocument();
      expect(regulatoryDv01Action.querySelector("p, small")).toBeNull();

      await user.click(regulatoryDv01Action);

      expect(scrollTargets).toContain(regulatoryDv01Card);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("falls back from prior-period portfolio DV01 change to the portfolio DV01 KPI card when controls are absent", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_prior_portfolio_dv01_fallback_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_prior_portfolio_dv01_fallback_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          prior_period_change: {
            ...tensorResult(reportDate).prior_period_change,
            status: tensorResult(reportDate).prior_period_change?.status ?? "available",
            comparison_report_date: tensorResult(reportDate).prior_period_change?.comparison_report_date ?? "2026-02-27",
            summary: tensorResult(reportDate).prior_period_change?.summary ?? "估值 DV01 变动",
            dominant_krd_bucket: tensorResult(reportDate).prior_period_change?.dominant_krd_bucket ?? "5Y",
            previous_dominant_krd_bucket:
              tensorResult(reportDate).prior_period_change?.previous_dominant_krd_bucket ?? "3Y",
            dominant_krd_shifted: tensorResult(reportDate).prior_period_change?.dominant_krd_shifted ?? true,
            metrics: [
              ...(tensorResult(reportDate).prior_period_change?.metrics ?? []),
              {
                key: "portfolio_dv01",
                label: "估值口径 DV01",
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
                interpretation: "估值口径 DV01 扩大",
              },
            ],
          },
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const priorChange = await screen.findByTestId("risk-tensor-prior-period-change");
      const portfolioDv01Action = within(priorChange).getByTestId("risk-tensor-prior-change-action-portfolio_dv01");
      const portfolioDv01Card = await screen.findByTestId("risk-tensor-portfolio-dv01-kpi");

      expect(screen.queryByTestId("risk-tensor-dv01-controls")).not.toBeInTheDocument();
      expect(portfolioDv01Action.querySelector("p, small")).toBeNull();

      await user.click(portfolioDv01Action);

      expect(scrollTargets).toContain(portfolioDv01Card);
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

      expect(await screen.findByTestId("risk-tensor-brief")).toHaveTextContent("主风险桶 --");
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

  it("lets users locate quality evidence from the DV01 stress scenario empty state", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_stress_quality_jump_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_dv01_stress_quality_jump_${reportDate}`),
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
      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");

      await user.click(within(stressScenarios).getByRole("button", { name: "定位质量证据" }));

      expect(scrollTargets).toContain(qualityDetail);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("lets users retry the risk tensor main read from the DV01 stress scenario empty state", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_stress_retry_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi
      .fn()
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor", "tr_tensor_dv01_stress_retry_initial"),
        result: {
          ...tensorResult("2026-02-28"),
          dv01_controls: dv01ControlsFixture({ stress_scenarios: [] }),
        },
      })
      .mockResolvedValueOnce({
        result_meta: buildMeta("risk.tensor", "tr_tensor_dv01_stress_retry_success"),
        result: {
          ...tensorResult("2026-02-28"),
          dv01_controls: dv01ControlsFixture({
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
                  raw: -1200,
                  unit: "yuan" as const,
                  display: "-1,200.00",
                  precision: 2,
                  sign_aware: true,
                },
              },
            ],
          }),
        },
      });

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const stressScenarios = await screen.findByTestId("risk-tensor-dv01-stress-scenarios");
    expect(stressScenarios).toHaveTextContent("暂无压力情景");

    await user.click(within(stressScenarios).getByRole("button", { name: "重试主读面" }));

    await waitFor(() => {
      expect(getRiskTensor).toHaveBeenCalledTimes(2);
    });
    expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent("tr_tensor_dv01_stress_retry_success");
    expect(screen.queryByTestId("risk-tensor-dv01-stress-empty")).not.toBeInTheDocument();
    expect(await screen.findByTestId("risk-tensor-dv01-stress-scenarios")).toHaveTextContent("+10bp");
  });

  it("copies DV01 stress scenario diagnostics when backend scenarios are empty", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_stress_copy_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_dv01_stress_copy_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          dv01_controls: dv01ControlsFixture({
            limit_status: "ok",
            approved_limit_dv01: {
              raw: 100,
              unit: "dv01" as const,
              display: "100.00",
              precision: 2,
              sign_aware: false,
            },
            limit_usage_ratio: {
              raw: 0.45,
              unit: "ratio" as const,
              display: "45.0%",
              precision: 1,
              sign_aware: false,
            },
            volatility_status: "ok",
            daily_rate_volatility_bp: {
              raw: 5,
              unit: "bp" as const,
              display: "5.00",
              precision: 2,
              sign_aware: false,
            },
            stress_scenarios: [],
          }),
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const stressEmpty = await screen.findByTestId("risk-tensor-dv01-stress-empty");
      await user.click(within(stressEmpty).getByRole("button", { name: "复制压力情景排查信息" }));

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量 DV01 压力情景排查信息"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("trace_id tr_tensor_dv01_stress_copy_2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("报告日 2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("limit_status 限额内"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("volatility_status ok"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("stress_scenarios_count 0"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("页面不会在前端补算 DV01 压力情景"));
      expect(stressEmpty).toHaveTextContent("已复制压力情景排查信息");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("shows manual DV01 stress scenario diagnostics when copying fails", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_stress_copy_failure_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_dv01_stress_copy_failure_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          dv01_controls: dv01ControlsFixture({
            limit_status: "ok",
            approved_limit_dv01: {
              raw: 100,
              unit: "dv01" as const,
              display: "100.00",
              precision: 2,
              sign_aware: false,
            },
            limit_usage_ratio: {
              raw: 0.45,
              unit: "ratio" as const,
              display: "45.0%",
              precision: 1,
              sign_aware: false,
            },
            volatility_status: "ok",
            daily_rate_volatility_bp: {
              raw: 5,
              unit: "bp" as const,
              display: "5.00",
              precision: 2,
              sign_aware: false,
            },
            stress_scenarios: [],
          }),
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const stressEmpty = await screen.findByTestId("risk-tensor-dv01-stress-empty");
      await user.click(within(stressEmpty).getByRole("button", { name: "复制压力情景排查信息" }));

      await waitFor(() => {
        expect(stressEmpty).toHaveTextContent("复制失败，请手动选择压力情景排查信息");
      });
      const manualCopy = within(stressEmpty).getByTestId("risk-tensor-dv01-stress-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量 DV01 压力情景排查信息");
      expect(manualCopy).toHaveTextContent("trace_id tr_tensor_dv01_stress_copy_failure_2026-02-28");
      expect(manualCopy).toHaveTextContent("stress_scenarios_count 0");
      expect(manualCopy).toHaveTextContent("页面不会在前端补算 DV01 压力情景");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("ignores stale DV01 stress scenario copy results after control evidence changes", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_stress_stale_copy_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi
        .fn()
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_dv01_stress_stale_copy_initial"),
          result: {
            ...tensorResult("2026-02-28"),
            dv01_controls: dv01ControlsFixture({ stress_scenarios: [] }),
          } as RiskTensorPayload,
        })
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_dv01_stress_stale_copy_refreshed"),
          result: {
            ...tensorResult("2026-02-28"),
            dv01_controls: dv01ControlsFixture({
              limit_status: "ok",
              approved_limit_dv01: {
                raw: 100,
                unit: "dv01" as const,
                display: "100.00",
                precision: 2,
                sign_aware: false,
              },
              limit_usage_ratio: {
                raw: 0.45,
                unit: "ratio" as const,
                display: "45.0%",
                precision: 1,
                sign_aware: false,
              },
              volatility_status: "ok",
              daily_rate_volatility_bp: {
                raw: 5,
                unit: "bp" as const,
                display: "5.00",
                precision: 2,
                sign_aware: false,
              },
              stress_scenarios: [],
            }),
          } as RiskTensorPayload,
        });

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const stressEmpty = await screen.findByTestId("risk-tensor-dv01-stress-empty");
      await user.click(within(stressEmpty).getByRole("button", { name: "复制压力情景排查信息" }));
      await user.click(within(stressEmpty).getByRole("button", { name: "重试主读面" }));

      await waitFor(() => {
        expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent(
          "tr_tensor_dv01_stress_stale_copy_refreshed",
        );
      });

      await act(async () => {
        resolveCopy?.();
      });

      const stressScenarios = await screen.findByTestId("risk-tensor-dv01-stress-scenarios");
      expect(stressScenarios).toHaveTextContent("暂无压力情景");
      expect(stressScenarios).not.toHaveTextContent("已复制压力情景排查信息");
      expect(screen.queryByTestId("risk-tensor-dv01-stress-manual-copy")).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
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

  it("copies the DV01 control action checklist for handoff", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_actions_copy_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_dv01_actions_copy_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          dv01_controls: dv01ControlsFixture({
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
          }),
        } as RiskTensorPayload,
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const actions = await screen.findByTestId("risk-tensor-dv01-actions");

      await user.click(within(actions).getByRole("button", { name: "复制处置清单" }));

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量 DV01 控制处置清单"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("trace_id tr_tensor_dv01_actions_copy_2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("报告日 2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("basis formal"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("approved_dv01_limit required 配置审批限额"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("证据 审批 DV01 限额未接入。"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("处置 接入曲线波动率后生成波动预警。"));
      await waitFor(() => {
        expect(actions).toHaveTextContent("已复制处置清单");
      });
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      }
    }
  });

  it("shows manual copy text when DV01 action checklist copying fails", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_actions_copy_failure_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_dv01_actions_copy_failure_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          dv01_controls: dv01ControlsFixture({
            control_actions: [
              {
                key: "approved_dv01_limit",
                title: "配置审批限额",
                status: "required",
                evidence: "审批 DV01 限额未接入。",
                action: "接入投委会或风控审批后的总 DV01 限额。",
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

      const actions = await screen.findByTestId("risk-tensor-dv01-actions");

      await user.click(within(actions).getByRole("button", { name: "复制处置清单" }));

      await waitFor(() => {
        expect(actions).toHaveTextContent("复制失败，请手动选择处置清单");
      });
      const manualCopy = within(actions).getByTestId("risk-tensor-dv01-actions-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量 DV01 控制处置清单");
      expect(manualCopy).toHaveTextContent("approved_dv01_limit required 配置审批限额");
      expect(manualCopy).toHaveTextContent("处置 接入投委会或风控审批后的总 DV01 限额。");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      }
    }
  });

  it("resets DV01 action checklist copy feedback when refreshed control actions change", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_actions_feedback_reset_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi
        .fn()
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_dv01_actions_feedback_reset"),
          result: {
            ...tensorResult("2026-02-28"),
            dv01_controls: dv01ControlsFixture({
              control_actions: [
                {
                  key: "approved_dv01_limit",
                  title: "配置审批限额",
                  status: "required",
                  evidence: "审批 DV01 限额未接入。",
                  action: "接入总 DV01 限额。",
                },
              ],
            }),
          } as RiskTensorPayload,
        })
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_dv01_actions_feedback_reset"),
          result: {
            ...tensorResult("2026-02-28"),
            dv01_controls: dv01ControlsFixture({
              control_actions: [
                {
                  key: "rate_volatility_input",
                  title: "复核利率波动预警",
                  status: "watch",
                  evidence: "波动率源已接入。",
                  action: "每日复核利率波动预警。",
                },
              ],
            }),
          } as RiskTensorPayload,
        });

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const actions = await screen.findByTestId("risk-tensor-dv01-actions");

      await user.click(within(actions).getByRole("button", { name: "复制处置清单" }));

      await waitFor(() => {
        expect(actions).toHaveTextContent("已复制处置清单");
      });

      const retryActions = within(screen.getByTestId("risk-tensor-dv01-controls")).getAllByRole("button", {
        name: "重试主读面",
      });
      await user.click(retryActions[0]!);

      await waitFor(() => {
        expect(screen.getByTestId("risk-tensor-dv01-actions")).toHaveTextContent("复核利率波动预警");
      });
      expect(screen.getByTestId("risk-tensor-dv01-actions")).not.toHaveTextContent("已复制处置清单");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("lets users hand off diagnostics when DV01 control actions are empty", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_empty_actions_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi
        .fn()
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_dv01_empty_actions_initial"),
          result: {
            ...tensorResult("2026-02-28"),
            dv01_controls: dv01ControlsFixture({
              limit_status: "ok",
              approved_limit_dv01: {
                raw: 100,
                unit: "dv01" as const,
                display: "100.00",
                precision: 2,
                sign_aware: false,
              },
              limit_usage_ratio: {
                raw: 0.45,
                unit: "ratio" as const,
                display: "45.0%",
                precision: 1,
                sign_aware: false,
              },
              volatility_status: "ok",
              daily_rate_volatility_bp: {
                raw: 5,
                unit: "bp" as const,
                display: "5.00",
                precision: 2,
                sign_aware: false,
              },
              control_actions: [],
              control_message: "DV01 controls are configured, but action detail is empty.",
              action_hint: "后端未返回控制动作明细，请核对控制动作生成链路。",
            }),
          },
        })
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_dv01_empty_actions_retry"),
          result: {
            ...tensorResult("2026-02-28"),
            dv01_controls: dv01ControlsFixture({
              limit_status: "ok",
              approved_limit_dv01: {
                raw: 100,
                unit: "dv01" as const,
                display: "100.00",
                precision: 2,
                sign_aware: false,
              },
              limit_usage_ratio: {
                raw: 0.45,
                unit: "ratio" as const,
                display: "45.0%",
                precision: 1,
                sign_aware: false,
              },
              volatility_status: "ok",
              daily_rate_volatility_bp: {
                raw: 5,
                unit: "bp" as const,
                display: "5.00",
                precision: 2,
                sign_aware: false,
              },
              control_actions: [
                {
                  key: "volatility_watch",
                  title: "复核利率波动预警",
                  status: "watch",
                  evidence: "波动率源已接入。",
                  action: "每日复核利率波动预警。",
                },
              ],
              control_message: "DV01 controls are configured.",
              action_hint: "继续按处置清单复核。",
            }),
          },
        });

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const controls = await screen.findByTestId("risk-tensor-dv01-controls");
      const emptyActions = within(controls).getByTestId("risk-tensor-dv01-actions-empty");

      expect(emptyActions).toHaveTextContent("后端未返回 DV01 控制动作明细");
      expect(screen.queryByTestId("risk-tensor-dv01-actions")).not.toBeInTheDocument();

      await user.click(within(emptyActions).getByRole("button", { name: "复制处置排查信息" }));

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量 DV01 控制处置清单"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("trace_id tr_tensor_dv01_empty_actions_initial"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("control_actions_count 0"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("control_actions 后端未返回处置动作"));
      expect(emptyActions).toHaveTextContent("已复制处置清单");

      await user.click(within(emptyActions).getByRole("button", { name: "重试主读面" }));

      await waitFor(() => {
        expect(getRiskTensor).toHaveBeenCalledTimes(2);
      });
      expect(await screen.findByTestId("risk-tensor-dv01-actions")).toHaveTextContent("复核利率波动预警");
      expect(screen.queryByTestId("risk-tensor-dv01-actions-empty")).not.toBeInTheDocument();
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("shows manual diagnostics when empty DV01 control action copying fails", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_empty_actions_copy_failure_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_dv01_empty_actions_copy_failure_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          dv01_controls: dv01ControlsFixture({
            limit_status: "ok",
            approved_limit_dv01: {
              raw: 100,
              unit: "dv01" as const,
              display: "100.00",
              precision: 2,
              sign_aware: false,
            },
            limit_usage_ratio: {
              raw: 0.45,
              unit: "ratio" as const,
              display: "45.0%",
              precision: 1,
              sign_aware: false,
            },
            volatility_status: "ok",
            daily_rate_volatility_bp: {
              raw: 5,
              unit: "bp" as const,
              display: "5.00",
              precision: 2,
              sign_aware: false,
            },
            control_actions: [],
            control_message: "DV01 controls are configured, but action detail is empty.",
            action_hint: "后端未返回控制动作明细，请核对控制动作生成链路。",
          }),
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const emptyActions = await screen.findByTestId("risk-tensor-dv01-actions-empty");
      await user.click(within(emptyActions).getByRole("button", { name: "复制处置排查信息" }));

      await waitFor(() => {
        expect(emptyActions).toHaveTextContent("复制失败，请手动选择处置清单");
      });
      const manualCopy = within(emptyActions).getByTestId("risk-tensor-dv01-actions-empty-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量 DV01 控制处置清单");
      expect(manualCopy).toHaveTextContent("trace_id tr_tensor_dv01_empty_actions_copy_failure_2026-02-28");
      expect(manualCopy).toHaveTextContent("control_actions_count 0");
      expect(manualCopy).toHaveTextContent("control_actions 后端未返回处置动作");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("lets users locate quality evidence and retry when DV01 control inputs are pending", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_pending_actions_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const stressScenarios: NonNullable<RiskTensorPayload["dv01_controls"]>["stress_scenarios"] = [
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
            raw: -1200,
            unit: "yuan" as const,
            display: "-1,200.00",
            precision: 2,
            sign_aware: true,
          },
        },
      ];
      const getRiskTensor = vi
        .fn()
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_dv01_pending_actions_initial"),
          result: {
            ...tensorResult("2026-02-28"),
            dv01_controls: dv01ControlsFixture({ stress_scenarios: stressScenarios }),
          } as RiskTensorPayload,
        })
        .mockResolvedValueOnce({
          result_meta: buildMeta("risk.tensor", "tr_tensor_dv01_pending_actions_retry"),
          result: {
            ...tensorResult("2026-02-28"),
            dv01_controls: dv01ControlsFixture({
              limit_status: "ok",
              approved_limit_dv01: {
                raw: 2000000,
                unit: "dv01" as const,
                display: "2,000,000.00",
                precision: 2,
                sign_aware: false,
              },
              limit_usage_ratio: {
                raw: 0.24,
                unit: "ratio" as const,
                display: "24.0%",
                precision: 1,
                sign_aware: false,
              },
              volatility_status: "ok",
              daily_rate_volatility_bp: {
                raw: 8,
                unit: "bp" as const,
                display: "8.00",
                precision: 2,
                sign_aware: false,
              },
              stress_scenarios: stressScenarios,
              control_message: "DV01 controls are configured.",
              action_hint: "Continue daily monitoring.",
            }),
          } as RiskTensorPayload,
        });

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const controls = await screen.findByTestId("risk-tensor-dv01-controls");
      const qualityDetail = await screen.findByTestId("risk-tensor-quality-detail");
      expect(controls).toHaveTextContent("限额待配置");
      expect(controls).toHaveTextContent("波动源待接入");

      await user.click(within(controls).getByRole("button", { name: "定位质量证据" }));

      expect(scrollTargets).toContain(qualityDetail);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "center" });

      await user.click(within(controls).getByRole("button", { name: "重试主读面" }));

      await waitFor(() => {
        expect(getRiskTensor).toHaveBeenCalledTimes(2);
      });
      expect(await screen.findByTestId("risk-tensor-dv01-controls")).toHaveTextContent("DV01 controls are configured.");
      expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent(
        "tr_tensor_dv01_pending_actions_retry",
      );
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("copies DV01 pending input diagnostics from the control detail", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_pending_copy_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_dv01_pending_copy_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          dv01_controls: dv01ControlsFixture({ control_actions: [] }),
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const controls = await screen.findByTestId("risk-tensor-dv01-controls");
      await user.click(within(controls).getByRole("button", { name: "复制输入排查信息" }));

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量 DV01 控制输入排查信息"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("trace_id tr_tensor_dv01_pending_copy_2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("报告日 2026-02-28"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("limit_status 限额待配置"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("volatility_status 波动源待接入"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("control_actions_count 0"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("请补充正式限额源、利率波动输入或控制动作明细"));
      expect(controls).toHaveTextContent("已复制输入排查信息");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
  });

  it("shows manual DV01 pending input diagnostics when copying fails", async () => {
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
        result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dv01_pending_copy_failure_dates"),
        result: { report_dates: ["2026-02-28"] },
      }));
      const getRiskTensor = vi.fn(async (reportDate: string) => ({
        result_meta: buildMeta("risk.tensor", `tr_tensor_dv01_pending_copy_failure_${reportDate}`),
        result: {
          ...tensorResult(reportDate),
          dv01_controls: dv01ControlsFixture({ control_actions: [] }),
        },
      }));

      renderRiskTensorRoute("/risk-tensor", {
        ...base,
        getRiskTensorDates,
        getRiskTensor,
      });

      const controls = await screen.findByTestId("risk-tensor-dv01-controls");
      await user.click(within(controls).getByRole("button", { name: "复制输入排查信息" }));

      await waitFor(() => {
        expect(controls).toHaveTextContent("复制失败，请手动选择输入排查信息");
      });
      const manualCopy = within(controls).getByTestId("risk-tensor-dv01-pending-inputs-manual-copy");
      expect(manualCopy).toHaveTextContent("风险张量 DV01 控制输入排查信息");
      expect(manualCopy).toHaveTextContent("trace_id tr_tensor_dv01_pending_copy_failure_2026-02-28");
      expect(manualCopy).toHaveTextContent("limit_status 限额待配置");
      expect(manualCopy).toHaveTextContent("volatility_status 波动源待接入");
      expect(manualCopy).toHaveTextContent("control_actions_count 0");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
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

  it("ignores stale report-date list failure copy results after retry evidence changes", async () => {
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
      .mockRejectedValueOnce(new Error("Request failed: /api/risk/tensor/dates (503)"))
      .mockRejectedValueOnce(new Error("Request failed: /api/risk/tensor/dates (504)"));
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
        expect(screen.getByTestId("risk-tensor-error-context")).toHaveTextContent("HTTP 状态 504");
      });

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
    const user = userEvent.setup();
    const writeText = vi.fn(async (_text: string) => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_error_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async () => {
      throw new Error(`Request failed: /api/risk/tensor?report_date=${reportDate} (${statusCode})`);
    });

    try {
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
      expect(errorContext).toHaveTextContent("basis formal");
      expect(errorContext).toHaveTextContent("cache_version cv_tensor_test");
      expect(errorContext).toHaveTextContent("generated_at 2026-04-12T08:00:00Z");
      expect(errorContext).toHaveTextContent("source_version sv_tensor_test");
      expect(errorContext).toHaveTextContent("rule_version rv_tensor_test");
      expect(errorContext).toHaveTextContent("主读面 trace_id 未提供");
      expect(errorContext).toHaveTextContent("不会使用缓存或前端补算替代正式主读结果");

      await user.click(within(errorContext).getByRole("button", { name: "复制排查信息" }));

      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("风险张量主读面加载失败排查信息"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining(`报告日 ${reportDate}`));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining(`HTTP 状态 ${statusCode}`));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("日期治理 trace_id tr_tensor_error_dates"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("basis formal"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("cache_version cv_tensor_test"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("generated_at 2026-04-12T08:00:00Z"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("source_version sv_tensor_test"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("rule_version rv_tensor_test"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("主读面 trace_id 未提供"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("不会使用缓存或前端补算替代正式主读结果"));
      expect(errorContext).toHaveTextContent("已复制排查信息");
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
    }
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
