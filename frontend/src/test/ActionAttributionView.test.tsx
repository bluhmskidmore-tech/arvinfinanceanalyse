import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { Numeric, ResultMeta } from "../api/contracts";
import { ActionAttributionView } from "../features/bond-analytics/components/ActionAttributionView";
import type { ActionAttributionResponse } from "../features/bond-analytics/types";
import { formatRawAsNumeric } from "../utils/format";

function numeric(
  raw: number | null,
  unit: Numeric["unit"],
  signAware = false,
  precision?: number,
): Numeric {
  return formatRawAsNumeric({
    raw,
    unit,
    sign_aware: signAware,
    ...(precision === undefined ? {} : { precision }),
  });
}

const yuan = (raw: number | null) => numeric(raw, "yuan", true);
const ratio = (raw: number | null) => numeric(raw, "ratio");
const dv01 = (raw: number | null) => numeric(raw, "dv01");

function createResultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_demo",
    basis: "formal",
    result_kind: "bond_analytics.action_attribution",
    formal_use_allowed: true,
    source_version: "sv_demo",
    vendor_version: "vv_demo",
    rule_version: "rv_demo",
    cache_version: "cv_demo",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-10T00:00:00Z",
    ...overrides,
  };
}

function createActionAttributionResult(
  overrides: Partial<ActionAttributionResponse> = {},
): ActionAttributionResponse {
  return {
    report_date: "2026-03-31",
    period_type: "MoM",
    period_start: "2026-03-01",
    period_end: "2026-03-31",
    total_actions: 2,
    total_pnl_from_actions: yuan(1_500_000),
    by_action_type: [
      {
        action_type: "ADD_DURATION",
        action_type_name: "加久期",
        action_count: 2,
        total_pnl_economic: yuan(1_500_000),
        total_pnl_accounting: yuan(1_500_000),
        avg_pnl_per_action: yuan(750_000),
      },
    ],
    action_details: [
      {
        action_id: "act-1",
        action_type: "ADD_DURATION",
        action_date: "2026-03-15",
        bonds_involved: ["019547"],
        description: "Add rate position",
        pnl_economic: yuan(800_000),
        pnl_accounting: yuan(800_000),
        delta_duration: ratio(0.05),
        delta_dv01: dv01(10_000),
        delta_spread_dv01: dv01(0),
        opportunity_cost: yuan(10_000),
        opportunity_cost_method: "shadow_bench",
      },
    ],
    period_start_duration: ratio(3.1),
    period_end_duration: ratio(3.2),
    duration_change_from_actions: ratio(0.1),
    period_start_dv01: dv01(120_000),
    period_end_dv01: dv01(130_000),
    warnings: [],
    computed_at: "2026-04-10T00:00:00Z",
    ...overrides,
  };
}

describe("ActionAttributionView", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function renderActionAttributionView(client: ReturnType<typeof createApiClient>) {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, refetchOnWindowFocus: false },
      },
    });

    return render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <ActionAttributionView reportDate="2026-03-31" periodType="MoM" />
        </ApiClientProvider>
      </QueryClientProvider>,
    );
  }

  it("loads action attribution with KPI cards, by_action_type summary, and detail table", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsActionAttribution: vi.fn(async () => ({
        result_meta: createResultMeta(),
        result: createActionAttributionResult(),
      })),
    };

    renderActionAttributionView(client);

    await waitFor(() =>
      expect(client.getBondAnalyticsActionAttribution).toHaveBeenCalledWith("2026-03-31", "MoM"),
    );

    expect(await screen.findByTestId("action-attribution-meta")).toHaveTextContent("2026-03-31");
    expect(screen.getByTestId("action-attribution-meta")).toHaveTextContent("期间 月度环比");
    expect(await screen.findByTestId("action-attribution-shell-lead")).toHaveTextContent(
      "动作归因",
    );
    expect(screen.getByTestId("action-attribution-shell-lead")).toHaveTextContent(
      "读取治理后的动作归因结果",
    );
    expect(screen.getByTestId("action-attribution-shell-lead")).toHaveTextContent(
      "交易动作归因概览",
    );
    expect(screen.getByTestId("action-attribution-summary-lead")).toHaveTextContent("汇总");
    expect(screen.getByTestId("action-attribution-detail-lead")).toHaveTextContent("动作明细");
    expect(await screen.findByText("动作数量")).toBeInTheDocument();
    expect(screen.getByText("动作贡献损益")).toBeInTheDocument();
    expect(screen.getByText("久期变化")).toBeInTheDocument();
    expect(screen.getByText("DV01变化（万元/bp）")).toBeInTheDocument();
    expect(screen.getByTestId("action-attribution-summary-lead")).toHaveTextContent("动作汇总");
    expect(screen.getAllByText("加久期").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/均次/).length).toBeGreaterThan(0);

    expect(screen.getByText("Add rate position")).toBeInTheDocument();
    expect(screen.getAllByText("涉及债券").length).toBeGreaterThan(0);
    expect(screen.getByText("019547")).toBeInTheDocument();
    expect(screen.getAllByText("机会成本口径").length).toBeGreaterThan(0);
    expect(screen.getByTestId("action-attribution-result-meta")).toHaveTextContent("供应商状态");
    expect(screen.getByText("shadow_bench")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/[\u9344\u9396\u93C3\u8796\u920B\u951B]/);
    expect(document.body.textContent).not.toContain("\u7487\u8A2A\u6F7C");
    expect(document.body.textContent).not.toContain("\u93B6\u5BA0\u61A1");
  });

  it("shows readiness metadata when backend returns component hints", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsActionAttribution: vi.fn(async () => ({
        result_meta: createResultMeta(),
        result: createActionAttributionResult({
          status: "partial",
          missing_inputs: ["formal_positions"],
          available_components: ["actions"],
          blocked_components: [],
        }),
      })),
    };

    renderActionAttributionView(client);

    /* 状态 token 中文化（C10）：partial→部分可用；组件技术名收进 title（正文只报数量）。 */
    const readiness = await screen.findByTestId("action-attribution-readiness");
    expect(readiness).toHaveTextContent("部分可用");
    expect(readiness).toHaveTextContent("缺失输入 1 项");
    expect(readiness.querySelector('[title*="formal_positions"]')).not.toBeNull();
  });

  it("does not present unavailable DV01 as zero and discloses derived accounting PnL", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsActionAttribution: vi.fn(async () => ({
        result_meta: createResultMeta({ formal_use_allowed: false, basis: "analytical" }),
        result: createActionAttributionResult({
          period_start_dv01: null,
          period_end_dv01: null,
          action_details: [
            {
              ...createActionAttributionResult().action_details[0],
              delta_dv01: null,
              delta_spread_dv01: null,
            },
          ],
          status: "partial",
          missing_inputs: ["action_level_dv01", "independent_accounting_pnl"],
          blocked_components: [
            "dv01_attribution",
            "independent_accounting_pnl_reconciliation",
          ],
          warnings: [
            "ACTION_ATTRIBUTION_DV01_UNAVAILABLE",
            "ACTION_ATTRIBUTION_ACCOUNTING_PNL_DERIVED_COPY",
          ],
        }),
      })),
    };

    renderActionAttributionView(client);

    expect(await screen.findByText("DV01变化（万元/bp）")).toBeInTheDocument();
    expect(screen.getByTestId("action-attribution-dv01-unavailable")).toHaveTextContent("不可用");
    expect(screen.getByTestId("action-attribution-accounting-derived-note")).toHaveTextContent(
      "会计损益当前由经济损益复制派生，不能独立核对",
    );
    expect(screen.getAllByText("ΔDV01（万元/bp）").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Δ利差DV01（万元/bp）").length).toBeGreaterThan(0);
  });

  it("renders warnings inside a collapsed disclosure with verbatim text", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsActionAttribution: vi.fn(async () => ({
        result_meta: createResultMeta(),
        result: createActionAttributionResult({
          warnings: ["示例：动作链路未完全接入"],
          by_action_type: [],
          action_details: [],
        }),
      })),
    };

    renderActionAttributionView(client);

    /* 技术 disclosure 默认折叠（C19，risk-overview 先例）：摘要报条数，原文逐字保留在折叠体内。 */
    const disclosure = await screen.findByTestId("action-attribution-warnings-disclosure");
    expect(disclosure).toHaveTextContent("口径与启发式提示（1 条）");
    expect(disclosure.hasAttribute("open")).toBe(false);
    expect(screen.getByText("示例：动作链路未完全接入")).toBeInTheDocument();
  });

  it("surfaces degraded provenance when result_meta is stale or fallback-backed", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsActionAttribution: vi.fn(async () => ({
        result_meta: createResultMeta({
          quality_flag: "warning",
          vendor_status: "vendor_stale",
          fallback_mode: "latest_snapshot",
        }),
        result: createActionAttributionResult(),
      })),
    };

    renderActionAttributionView(client);

    expect(await screen.findByTestId("action-attribution-result-meta-alert")).toHaveTextContent(
      "供应商状态=供应商数据陈旧",
    );
    expect(screen.getByTestId("action-attribution-result-meta-alert")).toHaveTextContent(
      "降级模式=最新快照降级",
    );
    expect(screen.getByTestId("action-attribution-result-meta")).toHaveTextContent("供应商陈旧");
  });
});
