import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  AdbInsightsResponse,
  AdbInsightsWindow,
} from "../api/contracts";
import AdbDeepAnalysisSection from "../features/average-balance/components/AdbDeepAnalysisSection";
import { EM_DASH } from "../utils/format";

function availableWindow(start: string, end: string): AdbInsightsWindow {
  return {
    start_date: start,
    end_date: end,
    calendar_days_inclusive: 90,
    coverage_days: 90,
    available: true,
    reason: "ok",
  };
}

function unavailableWindow(start: string, end: string): AdbInsightsWindow {
  return {
    start_date: start,
    end_date: end,
    calendar_days_inclusive: 90,
    coverage_days: 0,
    available: false,
    reason: "no_data",
  };
}

function buildInsights(overrides: Partial<AdbInsightsResponse> = {}): AdbInsightsResponse {
  return {
    start_date: "2026-05-01",
    end_date: "2026-07-31",
    calendar_days_inclusive: 92,
    insufficient_window: false,
    windows: {
      current: availableWindow("2026-05-01", "2026-07-31"),
      qoq: availableWindow("2026-01-30", "2026-04-30"),
      yoy: availableWindow("2025-05-01", "2025-07-31"),
    },
    scale_attribution: {
      qoq: {
        side_totals: {
          assets: { current_avg: 52_000_000_000, prior_avg: 50_000_000_000, delta: 2_000_000_000, delta_pct: 4 },
          liabilities: { current_avg: 21_500_000_000, prior_avg: 20_000_000_000, delta: 1_500_000_000, delta_pct: 7.5 },
        },
        asset_contributions: [
          { category: "国债", side: "asset", current_avg: 15_800_000_000, prior_avg: 15_000_000_000, delta: 800_000_000, contribution_pct: 40 },
          { category: "同业存单", side: "asset", current_avg: 2_950_000_000, prior_avg: null, delta: -50_000_000, contribution_pct: null },
        ],
        liability_contributions: [
          { category: "同业负债", side: "liability", current_avg: 8_900_000_000, prior_avg: 8_000_000_000, delta: 900_000_000, contribution_pct: 60 },
        ],
      },
      yoy: {
        side_totals: {
          assets: { current_avg: 52_000_000_000, prior_avg: 45_000_000_000, delta: 7_000_000_000, delta_pct: 15.56 },
          liabilities: { current_avg: 21_500_000_000, prior_avg: 17_000_000_000, delta: 4_500_000_000, delta_pct: 26.47 },
        },
        asset_contributions: [
          { category: "国债", side: "asset", current_avg: 15_800_000_000, prior_avg: 12_000_000_000, delta: 3_800_000_000, contribution_pct: 54.29 },
        ],
        liability_contributions: [
          { category: "同业负债", side: "liability", current_avg: 8_900_000_000, prior_avg: 6_500_000_000, delta: 2_400_000_000, contribution_pct: 53.33 },
        ],
      },
    },
    nim_attribution: {
      basis: "qoq",
      nim_current: 0.9,
      nim_prior: 1.02,
      nim_delta_bp: -12,
      asset_side: {
        total_effect_bp: 3,
        rate_effect_bp: 2.5,
        mix_effect_bp: 0.6,
        residual_bp: -0.1,
        by_category: [
          { category: "国债", share_current: 0.3, share_prior: 0.267, rate_current: 2.1, rate_prior: 2.05, rate_effect_bp: 1, mix_effect_bp: 0.3 },
          { category: "新增品种", share_current: 0.02, share_prior: null, rate_current: 2.4, rate_prior: null, rate_effect_bp: 0, mix_effect_bp: 0.2 },
        ],
      },
      liability_side: {
        total_effect_bp: 15,
        rate_effect_bp: 13,
        mix_effect_bp: 2.5,
        residual_bp: -0.5,
        by_category: [
          { category: "同业负债", share_current: 0.41, share_prior: 0.4, rate_current: 2.15, rate_prior: 1.85, rate_effect_bp: 8, mix_effect_bp: 1.5 },
        ],
      },
    },
    nim_attribution_unavailable_reason: null,
    volatility: {
      assets: {
        mean: 51_500_000_000,
        std: 800_000_000,
        cv: 0.0155,
        min: { date: "2026-05-14", value: 50_200_000_000 },
        max: { date: "2026-07-30", value: 53_100_000_000 },
        max_daily_change: { date: "2026-06-05", delta: 420_000_000, pct: 0.82 },
      },
      liabilities: {
        mean: 21_000_000_000,
        std: 350_000_000,
        cv: 0.0167,
        min: { date: "2026-05-10", value: 20_300_000_000 },
        max: { date: "2026-07-31", value: 21_900_000_000 },
        max_daily_change: null,
      },
      anomaly_detection_available: true,
      anomalies: [
        { date: "2026-06-05", side: "asset", value: 52_800_000_000, delta: 420_000_000, zscore: 3.1, direction: "up" },
      ],
      month_end_effect: {
        assets: { uplift_pct: 1.8, months_observed: 3, flagged: true },
        liabilities: { uplift_pct: 0.3, months_observed: 3, flagged: false },
      },
    },
    concentration: {
      assets: {
        start_observation_date: "2026-05-01",
        end_observation_date: "2026-07-31",
        hhi_start: 0.184,
        hhi_end: 0.212,
        top3_share_start: 0.63,
        top3_share_end: 0.68,
        top5_share_start: 0.82,
        top5_share_end: 0.86,
        movers: [{ category: "国债", share_start_pct: 28.5, share_end_pct: 32.1, delta_pp: 3.6 }],
      },
      liabilities: null,
      reason: null,
    },
    insights: [],
    ...overrides,
  };
}

function renderSection(props: Partial<Parameters<typeof AdbDeepAnalysisSection>[0]> = {}) {
  return render(
    <AdbDeepAnalysisSection
      data={buildInsights()}
      isLoading={false}
      isError={false}
      {...props}
    />,
  );
}

describe("AdbDeepAnalysisSection", () => {
  it("renders all four deep-analysis panels", () => {
    renderSection();

    expect(screen.getByTestId("adb-scale-attribution-panel")).toBeInTheDocument();
    expect(screen.getByTestId("adb-nim-attribution-panel")).toBeInTheDocument();
    expect(screen.getByTestId("adb-volatility-panel")).toBeInTheDocument();
    expect(screen.getByTestId("adb-concentration-panel")).toBeInTheDocument();
    expect(screen.getByText("规模变动归因（环比/同比）")).toBeInTheDocument();
    expect(screen.getByText("NIM 量价归因（环比）")).toBeInTheDocument();
    expect(screen.getByText("波动与异常")).toBeInTheDocument();
    expect(screen.getByText("结构集中度与迁移")).toBeInTheDocument();
  });

  it("renders backend-provided figures without recomputing them", () => {
    renderSection();

    const qoqBlock = within(screen.getByTestId("adb-scale-block-qoq"));
    expect(qoqBlock.getByText("+20.00 亿")).toBeInTheDocument();
    expect(qoqBlock.getByText("环比 +4.00%")).toBeInTheDocument();
    const yoyBlock = within(screen.getByTestId("adb-scale-block-yoy"));
    expect(yoyBlock.getByText("同比 +15.56%")).toBeInTheDocument();

    const nimPanel = within(screen.getByTestId("adb-nim-attribution-panel"));
    expect(nimPanel.getByText("-12.0 bp")).toBeInTheDocument();
    expect(nimPanel.getByText("残差 -0.1 bp")).toBeInTheDocument();

    const concentrationPanel = within(screen.getByTestId("adb-concentration-panel"));
    expect(
      concentrationPanel.getByText((_, element) => element?.textContent === "HHI：0.1840 → 0.2120"),
    ).toBeInTheDocument();
  });

  it("renders the deep-analysis lineage and snapshot fallback visibly", () => {
    renderSection({
      data: buildInsights({
        result_meta: {
          trace_id: "tr-adb-insights-fallback",
          basis: "analytical",
          result_kind: "adb.insights",
          formal_use_allowed: false,
          source_version: "sv-adb-insights-fallback",
          vendor_version: "vv-none",
          rule_version: "rv-adb-insights-v1",
          cache_version: "cv-adb-insights-v1",
          quality_flag: "warning",
          vendor_status: "ok",
          fallback_mode: "latest_snapshot",
          scenario_flag: false,
          generated_at: "2026-08-14T08:00:00+08:00",
        },
      }),
    });

    const evidence = within(screen.getByTestId("adb-insights-result-meta-insights"));
    expect(evidence.getByText("adb.insights")).toBeInTheDocument();
    expect(evidence.getByText("sv-adb-insights-fallback")).toBeInTheDocument();
    expect(evidence.getAllByText("最新快照降级").length).toBeGreaterThan(0);
  });

  it("renders EM_DASH for null values instead of zero", () => {
    renderSection();

    const qoqBlock = within(screen.getByTestId("adb-scale-block-qoq"));
    const emptyCells = qoqBlock.getAllByText(EM_DASH);
    expect(emptyCells.length).toBeGreaterThan(0);

    const nimPanel = within(screen.getByTestId("adb-nim-attribution-panel"));
    expect(nimPanel.getAllByText(EM_DASH).length).toBeGreaterThan(0);
  });

  it("shows the comparison-window unavailable notice instead of empty tables", () => {
    const data = buildInsights({
      windows: {
        current: availableWindow("2026-05-01", "2026-07-31"),
        qoq: unavailableWindow("2026-01-30", "2026-04-30"),
        yoy: availableWindow("2025-05-01", "2025-07-31"),
      },
      scale_attribution: { qoq: null, yoy: buildInsights().scale_attribution.yoy },
      nim_attribution: null,
      nim_attribution_unavailable_reason: "comparison_unavailable",
    });
    renderSection({ data });

    expect(
      screen.getAllByText("对比期无数据（2026-01-30～2026-04-30）").length,
    ).toBeGreaterThan(0);
    expect(screen.getByTestId("adb-scale-block-yoy")).toBeInTheDocument();
  });

  it("flags month-end window dressing on the side the backend marked", () => {
    renderSection();

    const monthEnd = within(screen.getByTestId("adb-month-end-effect"));
    expect(monthEnd.getByText("资产端存在月末冲高迹象")).toBeInTheDocument();
    expect(
      monthEnd.getByText("负债月末余额较月中均值平均+0.30%（覆盖 3 个月）"),
    ).toBeInTheDocument();
  });

  it("degrades the whole section when the window is too short", () => {
    renderSection({ data: buildInsights({ insufficient_window: true }) });

    expect(screen.getByText("区间过短，无法计算深度分析")).toBeInTheDocument();
    expect(screen.queryByTestId("adb-scale-attribution-panel")).not.toBeInTheDocument();
    expect(screen.queryByTestId("adb-nim-attribution-panel")).not.toBeInTheDocument();
  });

  it("fails visibly when the current window has no valid balances", () => {
    const data = buildInsights({
      windows: {
        current: unavailableWindow("2026-05-01", "2026-07-31"),
        qoq: availableWindow("2026-01-30", "2026-04-30"),
        yoy: availableWindow("2025-05-01", "2025-07-31"),
      },
      nim_attribution_unavailable_reason: "current_unavailable",
    });
    renderSection({ data });

    expect(screen.getByText("本期无有效余额，无法计算深度分析")).toBeInTheDocument();
    expect(screen.queryByTestId("adb-scale-attribution-panel")).not.toBeInTheDocument();
  });

  it("shows loading and error surfaces without rendering stale panels", () => {
    const { unmount } = renderSection({ data: undefined, isLoading: true });
    expect(screen.getByText("深度分析数据读取中…")).toBeInTheDocument();
    expect(screen.queryByTestId("adb-volatility-panel")).not.toBeInTheDocument();
    unmount();

    renderSection({ data: undefined, isLoading: false, isError: true });
    expect(
      screen.getByText("深度分析暂不可用，请查看上方「区间结论与警示」区的提示。"),
    ).toBeInTheDocument();
  });

  it("explains single-observation concentration instead of showing zeros", () => {
    renderSection();

    const liabilityBlock = within(screen.getByTestId("adb-concentration-block-liabilities"));
    expect(
      liabilityBlock.getByText("区间只有 1 个观测日，无法计算结构集中度。"),
    ).toBeInTheDocument();
  });
});
