import { render, screen } from "@testing-library/react";
import type { UseQueryResult } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ApiClient } from "../../../api/client";
import type { ApiEnvelope, ResultMeta, VolumeRateAttributionPayload } from "../../../api/contracts";
import { formatRawAsNumeric } from "../../../utils/format";
import { buildModuleHomeView } from "./moduleHomeModel";
import { PortfolioAttributionWaterfall } from "./PortfolioAttributionWaterfall";

vi.mock("../../../lib/echarts", () => ({
  default: () => <div data-testid="portfolio-attribution-chart" />,
}));
// Exercise the real hook, including its empty-to-chart transitions. jsdom has no layout.
beforeEach(() => { vi.stubGlobal("ResizeObserver", undefined); });
afterEach(() => { vi.unstubAllGlobals(); });

const amount = formatRawAsNumeric({ raw: 100, unit: "yuan", sign_aware: true });
const payload: VolumeRateAttributionPayload = {
  current_period: "2026-08", previous_period: "2026-07", compare_type: "mom",
  total_current_pnl: amount, total_previous_pnl: amount, total_pnl_change: amount,
  total_volume_effect: amount, total_rate_effect: amount, total_interaction_effect: amount,
  total_recon_error: amount, has_previous_data: true, has_complete_inputs: true, items: [],
};
const meta: ResultMeta = {
  trace_id: "quality-test", basis: "formal", result_kind: "pnl.volume_rate",
  formal_use_allowed: true, source_version: "sv", vendor_version: "vv", rule_version: "rv",
  cache_version: "cv", quality_flag: "ok", vendor_status: "ok", fallback_mode: "none",
  scenario_flag: false, as_of_date: "2026-08-31", generated_at: "2026-09-26T00:00:00Z",
};

function show(options: {
  payload?: Partial<VolumeRateAttributionPayload>;
  meta?: Partial<ResultMeta>;
  noData?: boolean;
  noMeta?: boolean;
  isError?: boolean;
  isLoading?: boolean;
} = {}) {
  const query = {
    data: options.noData ? undefined : {
      result: { ...payload, ...options.payload },
      result_meta: options.noMeta ? undefined : { ...meta, ...options.meta },
    },
    isError: options.isError ?? false,
    isLoading: options.isLoading ?? false,
  } as UseQueryResult<ApiEnvelope<VolumeRateAttributionPayload>>;
  const view = buildModuleHomeView("portfolio", { mode: "real" } as ApiClient, {
    pnlVolumeRate: query,
  });
  return render(<PortfolioAttributionWaterfall payload={view.pnlWaterfall} state={view.pnlWaterfallState} />);
}

describe("portfolio waterfall source status", () => {
  it("shows this chart's quality warning and incomplete-input reason beside available bars", () => {
    show({ payload: { has_complete_inputs: false, warnings: ["部分持仓缺少收益率。"] }, meta: { quality_flag: "warning" } });
    expect(screen.getByText("归因输入不完整")).toBeInTheDocument();
    expect(screen.getByText(/部分持仓缺少收益率/)).toBeInTheDocument();
    expect(screen.getByText("归因数据存在质量预警")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-attribution-chart")).toBeInTheDocument();
  });

  it("identifies cached data when refresh fails", () => {
    show({ isError: true });
    expect(screen.getByText("归因刷新失败，当前显示缓存结果")).toBeInTheDocument();
    expect(screen.getByText(/数据日 2026-08-31/)).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-attribution-chart")).toBeInTheDocument();
  });

  it("shows loading and error when no payload exists", () => {
    const rendered = show({ noData: true, isLoading: true });
    expect(screen.getByText("损益变动分解读取中")).toBeInTheDocument();
    rendered.unmount();
    show({ noData: true, isError: true });
    expect(screen.getByText("损益变动分解读取失败")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-attribution-chart")).not.toBeInTheDocument();
  });

  it("keeps hook order stable as one mounted view moves from loading to data and back to an error", () => {
    const rendered = show({ noData: true, isLoading: true });
    expect(screen.getByText("损益变动分解读取中")).toBeInTheDocument();
    rendered.rerender(<PortfolioAttributionWaterfall payload={payload} />);
    expect(screen.getByTestId("portfolio-attribution-chart")).toBeInTheDocument();
    rendered.rerender(<PortfolioAttributionWaterfall
      payload={undefined}
      state={[{ key: "error", variant: "error", title: "损益变动分解读取失败", description: "测试来源读取失败。" }]}
    />);
    expect(screen.getByText("损益变动分解读取失败")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-attribution-chart")).not.toBeInTheDocument();
    rendered.rerender(<PortfolioAttributionWaterfall payload={payload} />);
    expect(screen.getByTestId("portfolio-attribution-chart")).toBeInTheDocument();
  });

  it("discloses fallback and stale dates without substituting the response generation date", () => {
    show({ meta: { quality_flag: "stale", fallback_mode: "latest_snapshot", fallback_date: "2026-08-28", requested_report_date: "2026-08-31", as_of_date: null } });
    expect(screen.getByText("归因使用回退数据")).toBeInTheDocument();
    expect(screen.getByText("归因数据已过期")).toBeInTheDocument();
    expect(screen.getByText(/请求日 2026-08-31；数据日 2026-08-28/)).toBeInTheDocument();
    expect(screen.queryByText(/2026-09-26/)).not.toBeInTheDocument();
  });

  it("does not infer a missing data date from the period or request", () => {
    show({ meta: { as_of_date: null, requested_report_date: "2026-08-31" } });
    expect(screen.getByText("归因数据日期待核验")).toBeInTheDocument();
    expect(screen.getByText(/实际数据日未返回/)).toBeInTheDocument();
  });

  it("accepts a source filter date while disclosing a different request date", () => {
    show({ meta: { as_of_date: null, filters_applied: { requested_report_date: "2026-08-31", resolved_report_date: "2026-08-28" } } });
    expect(screen.getByText("归因数据日与请求日不一致")).toBeInTheDocument();
    expect(screen.getByText(/请求日 2026-08-31；数据日 2026-08-28/)).toBeInTheDocument();
    expect(screen.queryByText("归因数据日期待核验")).not.toBeInTheDocument();
  });

  it.each([
    [{ quality_flag: "error" }, "归因数据质量错误"],
    [{ quality_flag: "missing" }, "归因来源数据缺失"],
    [{ vendor_status: "vendor_unavailable" }, "归因数据来源不可用"],
    [{ basis: "analytical", formal_use_allowed: false }, "归因正式使用资格待核验"],
  ] as const)("keeps source restrictions visible: %j", (sourceMeta, message) => {
    show({ meta: sourceMeta });
    expect(screen.getByText(message)).toBeInTheDocument();
  });

  it("does not treat missing source metadata as permission for formal use", () => {
    show({ noMeta: true });
    expect(screen.getByText("归因正式使用资格待核验")).toBeInTheDocument();
    expect(screen.getByText("归因数据日期待核验")).toBeInTheDocument();
  });

  it("keeps warnings visible when there is no previous period to plot", () => {
    show({ payload: { has_previous_data: false, warnings: ["缺少上期正式数据。"] } });
    expect(screen.getByText(/缺少上期正式数据/)).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-attribution-chart")).not.toBeInTheDocument();
  });

  it("does not add a quality alarm for a healthy source", () => {
    show();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByTestId("portfolio-attribution-chart")).toBeInTheDocument();
  });
});
