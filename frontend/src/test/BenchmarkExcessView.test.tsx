import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="benchmark-excess-echarts-stub" />,
}));

import { BenchmarkExcessView } from "../features/bond-analytics/components/BenchmarkExcessView";

function createResultMeta(overrides: Record<string, unknown> = {}) {
  return {
    trace_id: "tr_demo",
    basis: "formal",
    result_kind: "bond_analytics.benchmark_excess",
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

function createBenchmarkExcessResult(overrides: Record<string, unknown> = {}) {
  return {
    report_date: "2026-03-31",
    period_type: "MoM",
    period_start: "2026-03-01",
    period_end: "2026-03-31",
    portfolio_return: "0.0045",
    benchmark_return: "0.0040",
    excess_return: "0.0005",
    duration_effect: "0.0002",
    curve_effect: "0.0001",
    spread_effect: "0.0001",
    selection_effect: "0.0001",
    allocation_effect: "0",
    explained_excess: "0.0005",
    recon_error: "0",
    portfolio_duration: "4.2",
    benchmark_duration: "4.0",
    duration_diff: "0.2",
    excess_sources: [{ source: "久期敞口", contribution: "0.0002", description: "" }],
    benchmark_id: "CDB_INDEX",
    benchmark_name: "中债国开债总指数",
    warnings: [],
    computed_at: "2026-04-10T00:00:00Z",
    ...overrides,
  };
}

describe("BenchmarkExcessView", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads benchmark excess with KPI cards, decomposition, and excess_sources", async () => {
    let resolvePayload!: (v: { result_meta: ReturnType<typeof createResultMeta>; result: ReturnType<typeof createBenchmarkExcessResult> }) => void;
    const payloadPromise = new Promise<{
      result_meta: ReturnType<typeof createResultMeta>;
      result: ReturnType<typeof createBenchmarkExcessResult>;
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

    render(<BenchmarkExcessView reportDate="2026-03-31" periodType="MoM" />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryByText("组合收益")).not.toBeInTheDocument();

    resolvePayload({
      result_meta: createResultMeta(),
      result: createBenchmarkExcessResult(),
    });

    expect(await screen.findByText("组合收益")).toBeInTheDocument();
    expect(screen.getByText("基准收益")).toBeInTheDocument();
    expect(screen.getByText("超额收益")).toBeInTheDocument();
    expect(screen.getByText("久期差")).toBeInTheDocument();

    expect(screen.getByText("超额收益分解")).toBeInTheDocument();
    expect(screen.getByText("久期效应")).toBeInTheDocument();
    expect(screen.getByText("曲线效应")).toBeInTheDocument();
    expect(screen.getByText("利差效应")).toBeInTheDocument();
    expect(screen.getByText("选券效应")).toBeInTheDocument();

    expect(screen.getByText("超额来源明细")).toBeInTheDocument();
    expect(screen.getByText("久期敞口")).toBeInTheDocument();
  });

  it("changes benchmark_id in fetch params when Select option changes", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({
          result_meta: createResultMeta(),
          result: createBenchmarkExcessResult(),
        }),
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<BenchmarkExcessView reportDate="2026-03-31" periodType="MoM" />);

    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(1));
    const firstUrl = String(
      fetchMock.mock.calls[0]?.[0] instanceof Request
        ? fetchMock.mock.calls[0][0].url
        : fetchMock.mock.calls[0]?.[0],
    );
    expect(firstUrl).toContain("benchmark_id=CDB_INDEX");

    const select = screen.getByRole("combobox");
    await user.click(select);
    await user.click(await screen.findByText("中债国债总指数"));

    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(2));
    const lastCall = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
    const lastUrl = String(lastCall?.[0] instanceof Request ? lastCall[0].url : lastCall?.[0]);
    expect(lastUrl).toContain("benchmark_id=TREASURY_INDEX");
  });

  it("renders warning alert when warnings exist", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({
          result_meta: createResultMeta(),
          result: createBenchmarkExcessResult({
            warnings: ["示例：基准指数行情缺口"],
            excess_sources: [],
          }),
        }),
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<BenchmarkExcessView reportDate="2026-03-31" periodType="MoM" />);

    expect(await screen.findByText("提示")).toBeInTheDocument();
    expect(screen.getByText("示例：基准指数行情缺口")).toBeInTheDocument();
  });
});
