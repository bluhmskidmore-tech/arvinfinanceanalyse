import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AppProviders } from "../app/providers";
import { createApiClient, type ApiClient } from "../api/client";
import { LedgerPnlCandidateFinancialIndicatorsPanel } from "../features/ledger-pnl/components/LedgerPnlCandidateFinancialIndicatorsPanel";
import { LedgerPnlCandidatePeriodComparison } from "../features/ledger-pnl/components/LedgerPnlCandidatePeriodComparison";

function renderComparison(client: ApiClient, reportMonth = "202606") {
  return render(
    <AppProviders client={client}>
      <LedgerPnlCandidatePeriodComparison
        reportMonth={reportMonth}
      />
    </AppProviders>,
  );
}

describe("LedgerPnlCandidatePeriodComparison", () => {
  it("renders the four-item backend net-interest bridge before the seven metrics", async () => {
    const client = createApiClient({ mode: "mock" });
    renderComparison(client);

    const bridge = await screen.findByRole("region", { name: "净利息收入算术贡献" });
    const metricsTable = screen.getByRole("table", { name: "候选财务指标跨期变化明细" });
    expect(
      bridge.compareDocumentPosition(metricsTable) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(within(bridge).getByText("净息变动 +2.5000 亿元")).toBeInTheDocument();
    expect(within(bridge).getByText("勾稽通过")).toBeInTheDocument();
    expect(within(bridge).getAllByRole("row")).toHaveLength(5);
    const loanRow = within(bridge).getByRole("row", { name: /贷款利息收入/ });
    expect(within(loanRow).getByText("11.0000")).toBeInTheDocument();
    expect(within(loanRow).getByText("10.0000")).toBeInTheDocument();
    expect(within(loanRow).getAllByText("+1.0000")).toHaveLength(2);
    const depositRow = within(bridge).getByRole("row", { name: /存款利息支出/ });
    expect(within(depositRow).getByText("6.0000")).toBeInTheDocument();
    expect(within(depositRow).getByText("5.5000")).toBeInTheDocument();
    expect(within(depositRow).getByText("+0.5000")).toBeInTheDocument();
    expect(within(depositRow).getByText("−0.5000")).toBeInTheDocument();
    expect(within(bridge).getByText(
      "后端按固定公式生成的算术贡献，不代表规模、利率或业务原因归因。",
    )).toBeInTheDocument();
    expect(within(bridge).queryByText(/息差原因|利好|利空/)).not.toBeInTheDocument();
  });

  it("shows a quiet bridge-unavailable message while keeping the seven metrics", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicatorPeriodComparison("202606");
    const bridge = response.net_interest_component_bridge;
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicatorPeriodComparison: vi.fn(async () => ({
        ...response,
        net_interest_component_bridge: {
          ...bridge,
          status: "not_evaluable" as const,
          quality_status: "not_evaluable" as const,
          foot_status: "not_evaluable" as const,
          net_delta_yi: null,
          component_contribution_total_yi: null,
          reconciliation_delta_yi: null,
          reasons: ["component_metric_status_not_ok"],
          components: bridge.components.map((component) => ({
            ...component,
            current_value_yi: null,
            previous_value_yi: null,
            component_delta_yi: null,
            contribution_to_net_delta_yi: null,
            reasons: ["metric_status_not_ok"],
          })),
        },
      })),
    };

    renderComparison(client);

    expect(await screen.findByText("净利息收入算术贡献暂不可用")).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "净利息收入四项算术贡献" })).not.toBeInTheDocument();
    expect(screen.getByRole("table", { name: "候选财务指标跨期变化明细" })).toBeInTheDocument();
  });

  it("leads with the comparable conclusion and preserves the candidate boundary", async () => {
    const client = createApiClient({ mode: "mock" });
    renderComparison(client);

    const heading = await screen.findByRole("heading", {
      level: 3,
      name: "5项可比、2项暂不可比（降级候选）",
    });
    const region = heading.closest("section");
    expect(region).not.toBeNull();
    if (!region) throw new Error("comparison region is missing");
    expect(within(region).getByRole("heading", { level: 3 })).toHaveTextContent(
      "5项可比、2项暂不可比（降级候选）",
    );
    expect(within(region).getByText("候选分析 · 禁止正式使用")).toBeInTheDocument();
    expect(within(region).getByText("历史源未锁 · 降级候选")).toBeInTheDocument();
    expect(within(region).getByText("完整 186 项对比不可用")).toBeInTheDocument();
    expect(within(region).getByText("202605 · 日均源")).toBeInTheDocument();
    expect(within(region).getByText("缺少工作表：微贷")).toBeInTheDocument();

    const metricsTable = within(region).getByRole("table", {
      name: "候选财务指标跨期变化明细",
    });
    const interestRow = within(metricsTable).getByRole("row", { name: /利息净收入/ });
    expect(within(interestRow).getByText("自然月单月环比")).toBeInTheDocument();
    expect(within(interestRow).getByText("+2.5000")).toBeInTheDocument();
    expect(within(interestRow).getByText("+25.00%")).toBeInTheDocument();

    const unavailableRow = within(region).getByRole("row", { name: /非息净收入合计/ });
    expect(within(unavailableRow).getAllByText("--")).toHaveLength(4);
    expect(within(unavailableRow).getByText(
      "指标依赖包含待补手工项和缺失总账科目，跨期结果暂不可比。",
    )).toBeInTheDocument();
    expect(within(region).queryByText(/重大异常|正常|利好|利空/)).not.toBeInTheDocument();
  });

  it("shows an explicit loading state without demo values", () => {
    const baseClient = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicatorPeriodComparison: vi.fn(
        () => new Promise<never>(() => undefined),
      ),
    };

    renderComparison(client);

    const loading = screen.getByTestId("candidate-period-comparison-loading");
    expect(loading).toHaveAttribute("data-state", "loading");
    expect(loading).toHaveTextContent("正在读取跨期变化");
    expect(screen.queryByText("12.5000")).not.toBeInTheDocument();
  });

  it("shows no-data for an empty month without calling the comparison endpoint", () => {
    const baseClient = createApiClient({ mode: "mock" });
    const comparisonRead = vi.fn(
      baseClient.getLedgerPnlCandidateFinancialIndicatorPeriodComparison,
    );
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicatorPeriodComparison: comparisonRead,
    };

    renderComparison(client, "   ");

    const noData = screen.getByTestId("candidate-period-comparison-no-data");
    expect(noData).toHaveAttribute("data-state", "no-data");
    expect(noData).toHaveTextContent("未选择跨期比较月份");
    expect(noData).toHaveTextContent("缺失月份不会按零处理");
    expect(comparisonRead).not.toHaveBeenCalled();
  });

  it("offers a retry after a transport error", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicatorPeriodComparison("202606");
    const comparisonRead = vi.fn()
      .mockRejectedValueOnce(new Error("503 period comparison unavailable"))
      .mockResolvedValue(response);
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicatorPeriodComparison: comparisonRead,
    };

    renderComparison(client);

    const error = await screen.findByTestId("candidate-period-comparison-error");
    expect(error).toHaveTextContent("503 period comparison unavailable");
    await user.click(within(error).getByRole("button", { name: "重新读取跨期变化" }));

    expect(await screen.findByText("5项可比、2项暂不可比（降级候选）")).toBeInTheDocument();
    expect(comparisonRead).toHaveBeenCalledTimes(2);
  });

  it("fails closed for a malformed or wrong-month response", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicatorPeriodComparison("202606");
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicatorPeriodComparison: vi.fn(async () => ({
        ...response,
        report_month: "202605",
      })),
    };

    renderComparison(client);

    const error = await screen.findByTestId("candidate-period-comparison-contract-error");
    expect(error).toHaveAttribute("data-state", "contract-error");
    expect(error).toHaveTextContent("响应月份与当前请求不一致");
    expect(screen.queryByRole("table", { name: "候选财务指标跨期变化明细" })).not.toBeInTheDocument();
  });

  it("prioritizes backend detail when the previous-month full-source replay is available", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicatorPeriodComparison("202606");
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicatorPeriodComparison: vi.fn(async () => ({
        ...response,
        full_scope_status: "available" as const,
        full_scope_reason_code: "available" as const,
        full_scope_detail: "后端证据：上期完整来源已通过重放校验。",
        full_scope_gaps: [],
      })),
    };

    renderComparison(client);

    expect(await screen.findByText("后端证据：上期完整来源已通过重放校验。")).toBeInTheDocument();
    expect(screen.getByText("上期完整来源 186 项重放校验可用")).toBeInTheDocument();
    expect(screen.queryByText("完整 186 项跨期重放可用；本区仍仅展示固定七项关键候选指标。")).not.toBeInTheDocument();
  });

  it("renders an unavailable 0-of-7 comparison without a fabricated trend", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const response = await baseClient.getLedgerPnlCandidateFinancialIndicatorPeriodComparison("202606");
    const unavailable = {
      ...response,
      overall_status: "unavailable" as const,
      net_interest_component_bridge: {
        ...response.net_interest_component_bridge,
        status: "not_evaluable" as const,
        quality_status: "not_evaluable" as const,
        foot_status: "not_evaluable" as const,
        net_delta_yi: null,
        component_contribution_total_yi: null,
        reconciliation_delta_yi: null,
        reasons: ["net_interest_comparison_not_evaluable"],
        components: response.net_interest_component_bridge.components.map((component) => ({
          ...component,
          current_value_yi: null,
          previous_value_yi: null,
          component_delta_yi: null,
          contribution_to_net_delta_yi: null,
          reasons: ["bridge_not_evaluable"],
        })),
      },
      metrics: response.metrics.map((metric) => ({
        ...metric,
        comparison_status: "not_comparable" as const,
        current_metric_status: "warning" as const,
        previous_metric_status: "missing" as const,
        two_month_prior_metric_status: metric.basis === "calendar_month_from_cumulative"
          ? "missing" as const
          : null,
        current_value_yi: null,
        previous_value_yi: null,
        delta_yi: null,
        change_rate: null,
        rate_reason: "metric_status_not_ok" as const,
        reasons: ["连续月份指标状态未通过，跨期值不可用。"],
        quality_status: "not_comparable" as const,
      })),
    };
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicatorPeriodComparison: vi.fn(async () => unavailable),
    };

    renderComparison(client);

    const heading = await screen.findByRole("heading", {
      name: "0项可比、7项暂不可比（候选）",
    });
    const region = heading.closest("section");
    expect(region).not.toBeNull();
    if (!region) throw new Error("comparison region is missing");
    expect(within(region).getAllByText(
      "连续月份指标状态未通过，跨期结果暂不可比。",
    )).toHaveLength(7);
    const metricsTable = within(region).getByRole("table", {
      name: "候选财务指标跨期变化明细",
    });
    const dataRows = within(metricsTable).getAllByRole("row").slice(1);
    expect(dataRows).toHaveLength(7);
    for (const row of dataRows) {
      expect(within(row).getAllByText("--")).toHaveLength(4);
    }
    expect(within(region).getByText("不绘制伪趋势，也不把缺失值解释为零。", { exact: false })).toBeInTheDocument();
    expect(within(region).queryByRole("img")).not.toBeInTheDocument();
  });

  it("mounts only in analysis after the decision brief and cancels when governance is restored", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const baseResponse = await baseClient.getLedgerPnlCandidateFinancialIndicators("202606");
    let comparisonSignal: AbortSignal | undefined;
    const comparisonRead = vi.fn((
      _reportMonth: string,
      options: { signal?: AbortSignal } = {},
    ) => {
      comparisonSignal = options.signal;
      return new Promise<never>(() => undefined);
    });
    const client: ApiClient = {
      ...baseClient,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => ({
        ...baseResponse,
        result: {
          ...baseResponse.result,
          source_version_impact: null,
        },
      })),
      getLedgerPnlCandidateFinancialIndicatorPeriodComparison: comparisonRead,
    };
    render(
      <AppProviders client={client}>
        <LedgerPnlCandidateFinancialIndicatorsPanel reportMonth="202606" currency="CNX" />
      </AppProviders>,
    );

    const governanceTab = await screen.findByRole("tab", { name: /^治理与补证/ });
    expect(governanceTab).toHaveAttribute("aria-selected", "true");
    expect(comparisonRead).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("tab", { name: /^经营分析/ }));
    await waitFor(() => expect(comparisonRead).toHaveBeenCalledTimes(1));
    expect(comparisonSignal).toBeDefined();
    expect(comparisonSignal?.aborted).toBe(false);
    const comparison = screen.getByRole("region", { name: "候选财务指标跨期变化" });
    const decisionBrief = screen.getByText("本期经营判断").closest("section");
    expect(decisionBrief).not.toBeNull();
    expect(
      (decisionBrief?.compareDocumentPosition(comparison) ?? 0)
      & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    fireEvent.click(governanceTab);
    await waitFor(() => expect(comparisonSignal?.aborted).toBe(true));
    expect(screen.queryByRole("region", { name: "候选财务指标跨期变化" })).not.toBeInTheDocument();
  });
});
