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
        description: "加仓利率债",
        pnl_economic: yuan(800_000),
        pnl_accounting: yuan(800_000),
        delta_duration: ratio(0.05),
        delta_dv01: dv01(10_000),
        delta_spread_dv01: dv01(0),
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

  it("loads action attribution with KPI cards, by_action_type summary, and detail table", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsActionAttribution: vi.fn(async () => ({
        result_meta: createResultMeta(),
        result: createActionAttributionResult(),
      })),
    };

    render(
      <ApiClientProvider client={client}>
        <ActionAttributionView reportDate="2026-03-31" periodType="MoM" />
      </ApiClientProvider>,
    );

    await waitFor(() =>
      expect(client.getBondAnalyticsActionAttribution).toHaveBeenCalledWith("2026-03-31", "MoM"),
    );

    expect(await screen.findByTestId("action-attribution-shell-lead")).toHaveTextContent(
      "交易动作归因概览",
    );
    expect(screen.getByTestId("action-attribution-shell-lead")).toHaveTextContent(
      "不在前端补算正式归因",
    );
    expect(screen.getByTestId("action-attribution-summary-lead")).toHaveTextContent(
      "动作类型汇总",
    );
    expect(screen.getByTestId("action-attribution-detail-lead")).toHaveTextContent(
      "动作明细",
    );
    expect(await screen.findByText("动作数量")).toBeInTheDocument();
    expect(screen.getByText("动作贡献损益")).toBeInTheDocument();
    expect(screen.getByText("久期变化")).toBeInTheDocument();
    expect(screen.getByText("DV01变化")).toBeInTheDocument();

    expect(screen.getByText("按动作类型汇总")).toBeInTheDocument();
    expect(screen.getAllByText("加久期").length).toBeGreaterThanOrEqual(1);

    expect(screen.getAllByText("动作明细").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("加仓利率债")).toBeInTheDocument();
  });

  it("renders warning alert when warnings exist", async () => {
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

    render(
      <ApiClientProvider client={client}>
        <ActionAttributionView reportDate="2026-03-31" periodType="MoM" />
      </ApiClientProvider>,
    );

    expect(await screen.findByText("提示")).toBeInTheDocument();
    expect(screen.getByText("示例：动作链路未完全接入")).toBeInTheDocument();
  });
});
