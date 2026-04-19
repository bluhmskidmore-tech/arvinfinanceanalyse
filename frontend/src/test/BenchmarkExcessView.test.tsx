import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="benchmark-excess-echarts-stub" />,
}));

import { ApiClientProvider, createApiClient } from "../api/client";
import type { Numeric, ResultMeta } from "../api/contracts";
import { BenchmarkExcessView } from "../features/bond-analytics/components/BenchmarkExcessView";
import type { BenchmarkExcessResponse } from "../features/bond-analytics/types";
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

const pct = (raw: number | null) => numeric(raw, "pct");
const bp = (raw: number | null) => numeric(raw, "bp");
const ratio = (raw: number | null, precision?: number) => numeric(raw, "ratio", false, precision);
const ratioAsBp = (raw: number | null) => bp(raw === null ? null : raw * 10_000);

function createResultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
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

function createBenchmarkExcessResult(
  overrides: Partial<BenchmarkExcessResponse> = {},
): BenchmarkExcessResponse {
  return {
    report_date: "2026-03-31",
    period_type: "MoM",
    period_start: "2026-03-01",
    period_end: "2026-03-31",
    portfolio_return: pct(0.0045),
    benchmark_return: pct(0.0040),
    excess_return: ratioAsBp(0.0005),
    duration_effect: ratioAsBp(0.0002),
    curve_effect: ratioAsBp(0.0001),
    spread_effect: ratioAsBp(0.0001),
    selection_effect: ratioAsBp(0.0001),
    allocation_effect: ratioAsBp(0),
    explained_excess: ratioAsBp(0.0005),
    recon_error: ratioAsBp(0),
    portfolio_duration: ratio(4.2, 1),
    benchmark_duration: ratio(4.0, 1),
    duration_diff: ratio(0.2, 1),
    excess_sources: [{ source: "久期敞口", contribution: ratioAsBp(0.0002), description: "" }],
    benchmark_id: "CDB_INDEX",
    benchmark_name: "中债国开债总指数",
    tracking_error: null,
    information_ratio: null,
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
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsBenchmarkExcess: vi.fn(async () => ({
        result_meta: createResultMeta(),
        result: createBenchmarkExcessResult(),
      })),
    };

    render(
      <ApiClientProvider client={client}>
        <BenchmarkExcessView reportDate="2026-03-31" periodType="MoM" />
      </ApiClientProvider>,
    );

    await waitFor(() =>
      expect(client.getBondAnalyticsBenchmarkExcess).toHaveBeenCalledWith(
        "2026-03-31",
        "MoM",
        "CDB_INDEX",
      ),
    );

    expect(await screen.findByTestId("benchmark-excess-shell-lead")).toHaveTextContent(
      "基准超额收益",
    );
    expect(screen.getByTestId("benchmark-excess-shell-lead")).toHaveTextContent(
      "不在前端重算超额收益",
    );
    expect(screen.getByTestId("benchmark-excess-summary-lead")).toHaveTextContent(
      "组合与基准摘要",
    );
    expect(screen.getByTestId("benchmark-excess-attribution-lead")).toHaveTextContent(
      "超额收益归因",
    );

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
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsBenchmarkExcess: vi.fn(async () => ({
        result_meta: createResultMeta(),
        result: createBenchmarkExcessResult(),
      })),
    };

    render(
      <ApiClientProvider client={client}>
        <BenchmarkExcessView reportDate="2026-03-31" periodType="MoM" />
      </ApiClientProvider>,
    );

    await waitFor(() =>
      expect(client.getBondAnalyticsBenchmarkExcess).toHaveBeenCalledWith(
        "2026-03-31",
        "MoM",
        "CDB_INDEX",
      ),
    );

    const select = screen.getByRole("combobox");
    await user.click(select);
    await user.click(await screen.findByText("中债国债总指数"));

    await waitFor(() =>
      expect(client.getBondAnalyticsBenchmarkExcess).toHaveBeenLastCalledWith(
        "2026-03-31",
        "MoM",
        "TREASURY_INDEX",
      ),
    );
  });

  it("renders warning alert when warnings exist", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsBenchmarkExcess: vi.fn(async () => ({
        result_meta: createResultMeta(),
        result: createBenchmarkExcessResult({
          warnings: ["示例：基准指数行情缺口"],
          excess_sources: [],
        }),
      })),
    };

    render(
      <ApiClientProvider client={client}>
        <BenchmarkExcessView reportDate="2026-03-31" periodType="MoM" />
      </ApiClientProvider>,
    );

    expect(await screen.findByText("提示")).toBeInTheDocument();
    expect(screen.getByText("示例：基准指数行情缺口")).toBeInTheDocument();
  });

  it("does not render optional risk metric cards when backend returns null", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsBenchmarkExcess: vi.fn(async () => ({
        result_meta: createResultMeta(),
        result: createBenchmarkExcessResult({
          tracking_error: null,
          information_ratio: null,
        }),
      })),
    };

    render(
      <ApiClientProvider client={client}>
        <BenchmarkExcessView reportDate="2026-03-31" periodType="MoM" />
      </ApiClientProvider>,
    );

    expect(await screen.findByText("超额收益")).toBeInTheDocument();
    expect(screen.queryByText("跟踪误差")).not.toBeInTheDocument();
    expect(screen.queryByText("信息比率")).not.toBeInTheDocument();
  });
});
