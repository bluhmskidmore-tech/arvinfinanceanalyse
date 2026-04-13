import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ActionAttributionView } from "../features/bond-analytics/components/ActionAttributionView";
import type { ActionAttributionResponse } from "../features/bond-analytics/types";

function createResultMeta(overrides: Record<string, unknown> = {}) {
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
    total_pnl_from_actions: "1500000",
    by_action_type: [
      {
        action_type: "ADD_DURATION",
        action_type_name: "加久期",
        action_count: 2,
        total_pnl_economic: "1500000",
        total_pnl_accounting: "1500000",
        avg_pnl_per_action: "750000",
      },
    ],
    action_details: [
      {
        action_id: "act-1",
        action_type: "ADD_DURATION",
        action_date: "2026-03-15",
        bonds_involved: ["019547"],
        description: "加仓利率债",
        pnl_economic: "800000",
        pnl_accounting: "800000",
        delta_duration: "0.05",
        delta_dv01: "10000",
        delta_spread_dv01: "0",
      },
    ],
    period_start_duration: "3.10",
    period_end_duration: "3.20",
    duration_change_from_actions: "0.10",
    period_start_dv01: "120000",
    period_end_dv01: "130000",
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
    let resolvePayload!: (v: { result_meta: ReturnType<typeof createResultMeta>; result: ReturnType<typeof createActionAttributionResult> }) => void;
    const payloadPromise = new Promise<{
      result_meta: ReturnType<typeof createResultMeta>;
      result: ReturnType<typeof createActionAttributionResult>;
    }>((resolve) => {
      resolvePayload = resolve;
    });

    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => payloadPromise,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<ActionAttributionView reportDate="2026-03-31" periodType="MoM" />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const firstUrl = String(
      fetchMock.mock.calls[0]?.[0] instanceof Request
        ? fetchMock.mock.calls[0][0].url
        : fetchMock.mock.calls[0]?.[0],
    );
    expect(firstUrl).toContain("/api/bond-analytics/action-attribution");
    expect(firstUrl).toContain("period_type=MoM");

    expect(screen.queryByText("动作数量")).not.toBeInTheDocument();

    resolvePayload({
      result_meta: createResultMeta(),
      result: createActionAttributionResult(),
    });

    expect(await screen.findByText("动作数量")).toBeInTheDocument();
    expect(screen.getByText("动作贡献损益")).toBeInTheDocument();
    expect(screen.getByText("久期变化")).toBeInTheDocument();
    expect(screen.getByText("DV01变化")).toBeInTheDocument();

    expect(screen.getByText("按动作类型汇总")).toBeInTheDocument();
    expect(screen.getAllByText("加久期").length).toBeGreaterThanOrEqual(1);

    expect(screen.getByText("动作明细")).toBeInTheDocument();
    expect(screen.getByText("加仓利率债")).toBeInTheDocument();
  });

  it("renders warning alert when warnings exist", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({
          result_meta: createResultMeta(),
          result: createActionAttributionResult({
            warnings: ["示例：动作链路未完全接入"],
            by_action_type: [],
            action_details: [],
          }),
        }),
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<ActionAttributionView reportDate="2026-03-31" periodType="MoM" />);

    expect(await screen.findByText("提示")).toBeInTheDocument();
    expect(screen.getByText("示例：动作链路未完全接入")).toBeInTheDocument();
  });
});
