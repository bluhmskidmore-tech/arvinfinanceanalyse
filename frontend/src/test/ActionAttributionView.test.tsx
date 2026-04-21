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
        action_type_name: "Add duration",
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

    expect(await screen.findByTestId("action-attribution-meta")).toHaveTextContent("2026-03-31");
    expect(screen.getByTestId("action-attribution-meta")).toHaveTextContent("MoM");
    expect(await screen.findByTestId("action-attribution-shell-lead")).toHaveTextContent(
      "Action Attribution",
    );
    expect(screen.getByTestId("action-attribution-shell-lead")).toHaveTextContent(
      "Reads the governed action-attribution payload",
    );
    expect(screen.getByTestId("action-attribution-summary-lead")).toHaveTextContent(
      "Summary",
    );
    expect(screen.getByTestId("action-attribution-detail-lead")).toHaveTextContent(
      "鍔ㄤ綔鏄庣粏",
    );
    expect(await screen.findByText("鍔ㄤ綔鏁伴噺")).toBeInTheDocument();
    expect(screen.getByText("鍔ㄤ綔璐＄尞鎹熺泭")).toBeInTheDocument();
    expect(screen.getByText("涔呮湡鍙樺寲")).toBeInTheDocument();
    expect(screen.getByText("DV01鍙樺寲")).toBeInTheDocument();
    expect(screen.getByTestId("action-attribution-summary-lead")).toHaveTextContent("Summary");
    expect(screen.getAllByText("Add duration").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Add duration").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/鍧囨/).length).toBeGreaterThan(0);

    expect(screen.getByText("Add rate position")).toBeInTheDocument();
    expect(screen.getByText("Add rate position")).toBeInTheDocument();
    expect(screen.getAllByText("娑夊強鍊哄埜").length).toBeGreaterThan(0);
    expect(screen.getByText("019547")).toBeInTheDocument();
    expect(screen.getAllByText("鏈轰細鎴愭湰鍙ｅ緞").length).toBeGreaterThan(0);
    expect(screen.getByTestId("action-attribution-result-meta")).toHaveTextContent("vendor_status");
    expect(screen.getByText("shadow_bench")).toBeInTheDocument();
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

    render(
      <ApiClientProvider client={client}>
        <ActionAttributionView reportDate="2026-03-31" periodType="MoM" />
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("action-attribution-readiness")).toHaveTextContent("partial");
    expect(screen.getByTestId("action-attribution-readiness")).toHaveTextContent("formal_positions");
  });

  it("renders warning alert when warnings exist", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsActionAttribution: vi.fn(async () => ({
        result_meta: createResultMeta(),
        result: createActionAttributionResult({
          warnings: ["绀轰緥锛氬姩浣滈摼璺湭瀹屽叏鎺ュ叆"],
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

    expect(await screen.findByText("鎻愮ず")).toBeInTheDocument();
    expect(screen.getByText("绀轰緥锛氬姩浣滈摼璺湭瀹屽叏鎺ュ叆")).toBeInTheDocument();
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

    render(
      <ApiClientProvider client={client}>
        <ActionAttributionView reportDate="2026-03-31" periodType="MoM" />
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("action-attribution-result-meta-alert")).toHaveTextContent(
      "vendor_status=vendor_stale",
    );
    expect(screen.getByTestId("action-attribution-result-meta-alert")).toHaveTextContent(
      "fallback_mode=latest_snapshot",
    );
    expect(screen.getByTestId("action-attribution-result-meta")).toHaveTextContent("vendor_stale");
  });
});
