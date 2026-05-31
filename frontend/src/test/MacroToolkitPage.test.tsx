import { screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

const MACRO_TOOLKIT_CSS_PATH = resolve(
  process.cwd(),
  "src/features/macro-toolkit/pages/MacroToolkitPage.css",
);

describe("MacroToolkitPage", () => {
  it("keeps page-local decorative colors on the homepage blue-gray token family", () => {
    const css = readFileSync(MACRO_TOOLKIT_CSS_PATH, "utf8");

    expect(css).not.toMatch(/moss-color-warm-/);
    expect(css).not.toMatch(/rgba\((255, 253, 248|120, 99, 76|147, 111, 88|111, 139, 106|171, 95, 62|143, 63, 63|55, 42, 30)/);
    expect(css).not.toMatch(/#(fffdf8|fffaf4|456882|6f8b6a|8f3f3f|2b2520|f0e7dc)/i);
    expect(css).toContain("var(--moss-color-primary-600)");
    expect(css).toContain("var(--moss-color-info-600)");
    expect(css).toContain("var(--moss-color-success-600)");
    expect(css).toContain("var(--moss-color-danger-600)");
    expect(css).toContain("var(--moss-color-warning-600)");
  });

  it("renders from the workbench route", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    expect(
      await screen.findByRole("heading", { level: 1, name: "宏观分析结果" }),
    ).toBeInTheDocument();
    const cockpit = await screen.findByTestId("macro-toolkit-tailwind-cockpit");
    expect(cockpit.className).toContain("bg-white");
    expect(await screen.findByText("投研观点")).toBeInTheDocument();
    expect(await screen.findByText("证据覆盖")).toBeInTheDocument();
    expect(await screen.findByText("87.5%")).toBeInTheDocument();
    const boundary = await screen.findByTestId("macro-toolkit-contract-boundary");
    expect(boundary).toHaveTextContent("分析/工具口径");
    expect(boundary).toHaveTextContent("非正式口径");
    expect(boundary).toHaveTextContent("macro_toolkit.analysis");
    expect(boundary).toHaveTextContent("rv_macro_toolkit_ui_v1");
    expect(
      await screen.findByLabelText("宏观工具投研总览"),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "核心信号" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "市场踩踏风险" }),
    ).toBeInTheDocument();
    expect((await screen.findAllByText("橙色风险")).length).toBeGreaterThanOrEqual(2);
    expect(await screen.findByText("总仓位上限30%，高位主题只减不加，午后不做冲高追买。")).toBeInTheDocument();
    expect(await screen.findByText("上涨家数")).toBeInTheDocument();
    expect(await screen.findByText("跌停家数")).toBeInTheDocument();
    expect(await screen.findByText("触发规则")).toBeInTheDocument();
    expect(await screen.findByText("观察条件")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "指标矩阵" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "功能补齐方案" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "CFFEX席位状态" }),
    ).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /刷新席位/ })).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "脚本产物" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "未纳入脚本" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "脚本注册表" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "功能结果" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "策略展示" }),
    ).toBeInTheDocument();
    const strategySupply = await screen.findByLabelText("策略供数闭环");
    expect(strategySupply).toHaveTextContent("完整链路 0/4");
    expect(strategySupply).toHaveTextContent("部分链路 0");
    expect(strategySupply).toHaveTextContent("降级 0");
    expect(strategySupply).toHaveTextContent("样例 4");
    expect(strategySupply).toHaveTextContent("股票历史 2026-04-30");
    expect(strategySupply).toHaveTextContent("因子快照 2026-04-30");
    const movingAverageTitle = await screen.findByText("移动均线策略");
    const movingAverageCard = movingAverageTitle.closest(".macro-toolkit-strategy-card");
    expect(movingAverageCard).not.toBeNull();
    expect(movingAverageCard).toHaveTextContent("SYNTHETIC_SAMPLE_ONLY");
    expect(movingAverageCard).toHaveTextContent("sample_only");
    expect(movingAverageCard).toHaveTextContent("价格来源缺失");
    expect(movingAverageCard).toHaveTextContent("因子来源缺失");
    expect(await screen.findByText("多因子选股")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /刷新股票数据/ })).toBeInTheDocument();
    expect(await screen.findByText("低拥挤度择时多因子")).toBeInTheDocument();
    expect((await screen.findAllByText(/M7/)).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(/M16/)).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("signal_aggregator")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("equity_strategies")).length).toBeGreaterThan(0);
  });

  it("shows M7/M10/M14 input evidence and missing-input warnings in capability results", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    const m7Text = await screen.findByText((content) => content.includes("Policy rate 7D"));
    const m10Texts = await screen.findAllByText((content) => content.includes("PMI_MISSING"));
    const m7Card = m7Text.closest(".macro-toolkit-capability-result");
    const m10Card = m10Texts[0]?.closest(".macro-toolkit-capability-result");
    const m14Card = m10Texts[1]?.closest(".macro-toolkit-capability-result");

    expect(m7Card).not.toBeNull();
    expect(m10Card).not.toBeNull();
    expect(m14Card).not.toBeNull();

    expect(m7Card).toHaveTextContent("Policy rate 7D: M001 2026-04-10");
    expect(m7Card).not.toHaveTextContent("POLICY_RATE_7D_MISSING");
    expect(m7Card).toHaveTextContent("choice");
    expect(m7Card).toHaveTextContent("2026-04-10");

    expect(m10Card).toHaveTextContent("PMI_MISSING");
    expect(m10Card).toHaveTextContent("M2_YOY_MISSING");
    expect(m10Card).toHaveTextContent("choice / fred / moss_derived");
    expect(m10Card).toHaveTextContent("2026-02-01");

    expect(m14Card).toHaveTextContent("PMI_MISSING");
    expect(m14Card).toHaveTextContent("PPI_YOY_MISSING");
    expect(m14Card).toHaveTextContent("M2_YOY_MISSING");
    expect(m14Card).toHaveTextContent("2026-03-01");
  });

  it("keeps core risk analysis visible while deferred strategy summaries are still loading", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          runtime_status: {
            analysis_scope: "core",
            deferred_sections: [
              {
                key: "strategy_summaries",
                label: "策略展示",
                status: "loading",
              },
            ],
          },
          strategy_summaries: [],
        },
      }),
      getMacroToolkitStrategySummaries: () => new Promise(() => {}),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    expect(
      await screen.findByRole("heading", { level: 2, name: "市场踩踏风险" }),
    ).toBeInTheDocument();
    expect(await screen.findByLabelText("宏观工具运行状态")).toHaveTextContent("策略展示 · 加载中");
    const strategySupply = await screen.findByLabelText("策略供数闭环");
    expect(strategySupply).toHaveTextContent("策略供数 加载中");
    expect(strategySupply).not.toHaveTextContent("0/0");
    expect(strategySupply).not.toHaveTextContent("样例 0");
    expect(await screen.findByText("策略展示正在生成")).toBeInTheDocument();
    expect(screen.getByText("核心判断和市场踩踏风险已先返回。")).toBeInTheDocument();
  });

  it("keeps the page frame and non-formal boundary visible while core analysis is still loading", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: () => new Promise(() => {}),
      getMacroToolkitScripts: () => new Promise(() => {}),
      getMacroToolkitStrategySummaries: () => new Promise(() => {}),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    expect(await screen.findByTestId("macro-toolkit-tailwind-cockpit")).toBeInTheDocument();
    const boundary = await screen.findByTestId("macro-toolkit-contract-boundary");
    expect(boundary).toHaveTextContent("非正式口径");
    expect(await screen.findByTestId("macro-toolkit-initial-analysis-loading")).toHaveTextContent(
      "核心分析加载中",
    );
    expect(await screen.findByRole("heading", { level: 2, name: "核心信号" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 2, name: "市场踩踏风险" })).toBeInTheDocument();
    expect(screen.queryByText("正在读取宏观工具")).not.toBeInTheDocument();
  });

  it("shows strategy source versions when real factor snapshots are used", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const strategyEnvelope = await baseClient.getMacroToolkitStrategySummaries();
    const realStrategies = strategyEnvelope.result.strategy_summaries.map((strategy) =>
      strategy.key === "multi_factor_selection"
        ? {
            ...strategy,
            status: "complete" as const,
            warnings: [],
            primary_metric: { label: "真实入选数量", value: 1, unit: "" },
            result: {
              data_status: "complete",
              price_source: "choice_stock_daily_observation",
              factor_source: "choice_stock_factor_snapshot",
              as_of_date: "2026-05-06",
              factor_as_of_date: "2026-04-30",
              factor_date_status: "fallback",
              factor_source_versions: ["sv_factor"],
              factor_vendor_versions: ["vv_factor"],
              factor_rule_versions: ["rv_factor"],
              factor_run_ids: ["run-factor"],
            },
          }
        : strategy,
    );
    const choiceStockRefresh = strategyEnvelope.result.choice_stock_refresh!;
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          strategy_summaries: [],
        },
      }),
      getMacroToolkitStrategySummaries: async () => ({
        ...strategyEnvelope,
            result: {
              ...strategyEnvelope.result,
              choice_stock_refresh: {
                ...choiceStockRefresh,
                daily_observation: {
                  ...choiceStockRefresh.daily_observation,
                  freshness_status: "current",
                  reference_date: "2026-05-06",
                  stale_days: 1,
                  fallback_mode: "none",
                  fallback_date: null,
                },
                factor_snapshot: {
                  ...choiceStockRefresh.factor_snapshot,
                  freshness_status: "stale",
                  reference_date: "2026-05-06",
                  stale_days: 9,
                  fallback_mode: "latest_available",
                  fallback_date: "2026-04-27",
                },
              },
              strategy_summaries: realStrategies,
            },
          }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const strategySupply = await screen.findByLabelText("策略供数闭环");
    expect(strategySupply).toHaveTextContent("完整链路 1/4");
    expect(strategySupply).toHaveTextContent("部分链路 0");
    expect(strategySupply).toHaveTextContent("股票历史 2026-04-30 · 已对齐");
    expect(strategySupply).toHaveTextContent("因子快照 2026-04-30 · 陈旧");
    expect(strategySupply).toHaveTextContent("最近可用 2026-04-27");
    const multiFactorTitle = await screen.findByText("多因子选股");
    const multiFactorCard = multiFactorTitle.closest(".macro-toolkit-strategy-card");
    expect(multiFactorCard).not.toBeNull();
    expect(multiFactorCard).toHaveTextContent("choice_stock_factor_snapshot");
    expect(multiFactorCard).toHaveTextContent("2026-05-06");
    expect(multiFactorCard).toHaveTextContent("2026-04-30");
    expect(multiFactorCard).toHaveTextContent("最近快照");
    expect(multiFactorCard).toHaveTextContent("sv_factor");
    expect(multiFactorCard).toHaveTextContent("vv_factor");
    expect(multiFactorCard).toHaveTextContent("rv_factor");
    expect(multiFactorCard).toHaveTextContent("run-factor");
  });

  it("shows price source versions when factor strategy is degraded", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const strategyEnvelope = await baseClient.getMacroToolkitStrategySummaries();
    const degradedStrategies = strategyEnvelope.result.strategy_summaries.map((strategy) =>
      strategy.key === "multi_factor_selection"
        ? {
            ...strategy,
            status: "degraded" as const,
            warnings: ["FUNDAMENTAL_FACTORS_NOT_MATERIALIZED"],
            primary_metric: null,
            result: {
              data_status: "degraded",
              price_source: "choice_stock_daily_observation",
              source_versions: ["sv_stock"],
              vendor_versions: ["vv_stock"],
              missing_factor_inputs: ["pe", "pb"],
            },
          }
        : strategy,
    );
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          strategy_summaries: [],
        },
      }),
      getMacroToolkitStrategySummaries: async () => ({
        ...strategyEnvelope,
        result: {
          ...strategyEnvelope.result,
          strategy_summaries: degradedStrategies,
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const strategySupply = await screen.findByLabelText("策略供数闭环");
    expect(strategySupply).toHaveTextContent("完整链路 0/4");
    expect(strategySupply).toHaveTextContent("部分链路 1");
    expect(strategySupply).toHaveTextContent("降级 1");
    expect(strategySupply).toHaveTextContent("样例 3");
    const multiFactorTitle = await screen.findByText("多因子选股");
    const multiFactorCard = multiFactorTitle.closest(".macro-toolkit-strategy-card");
    expect(multiFactorCard).not.toBeNull();
    expect(multiFactorCard).toHaveTextContent("FUNDAMENTAL_FACTORS_NOT_MATERIALIZED");
    expect(multiFactorCard).toHaveTextContent("choice_stock_daily_observation");
    expect(multiFactorCard).toHaveTextContent("sv_stock");
    expect(multiFactorCard).toHaveTextContent("vv_stock");
    expect(multiFactorCard).toHaveTextContent("因子来源缺失");
    expect(multiFactorCard).toHaveTextContent("缺失输入");
    expect(multiFactorCard).toHaveTextContent("pe / pb");
  });

  it("shows the read-only shadow portfolio report beside the current rule", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const strategyEnvelope = await baseClient.getMacroToolkitStrategySummaries();
    const shadowReport = {
      status: "complete",
      basis: "read_only_shadow",
      label: "影子组合报告",
      as_of_date: "2026-05-27",
      completed_periods: 13,
      factor_dates: [
        "2026-04-01",
        "2026-04-03",
        "2026-04-08",
        "2026-04-10",
        "2026-04-15",
        "2026-04-17",
        "2026-04-22",
        "2026-04-24",
        "2026-04-29",
        "2026-05-06",
        "2026-05-08",
        "2026-05-13",
        "2026-05-20",
        "2026-05-27",
      ],
      rule_version: "rv_macro_toolkit_shadow_portfolio_v1",
      tables_used: ["choice_stock_daily_observation", "choice_stock_factor_snapshot"],
      warnings: ["READ_ONLY_SHADOW_NOT_PRODUCTION"],
      cost_model: {
        cost_bps: [0, 10, 20, 50],
        initial_build_included: true,
        final_liquidation_included: false,
      },
      benchmark: {
        key: "equal_weight_factor_universe",
        label: "因子池等权基准",
        total_return: -0.0211,
        max_drawdown: -0.0601,
      },
      portfolios: [
        {
          key: "current_baseline",
          label: "当前正式规则",
          role: "production_reference",
          total_return: -0.0448,
          excess_return: -0.0242,
          max_drawdown: -0.0558,
          win_rate: 0.25,
          average_turnover: 0.3247,
          average_count: 29.25,
          average_pe: 43.02,
          average_pb: 2.06,
          weights: { value: 0.3, quality: 0.25, momentum: 0.15, low_vol: 0.15, dividend: 0.15 },
          constraints: { pe_max: null, pb_max: null, turnover_cap: null },
          cost_results: [
            { cost_bps: 0, total_return: -0.0448, excess_return: -0.0242, max_drawdown: -0.0558 },
            { cost_bps: 20, total_return: -0.0505, excess_return: -0.0301, max_drawdown: -0.0578 },
            { cost_bps: 50, total_return: -0.058, excess_return: -0.038, max_drawdown: -0.061 },
          ],
          latest_holdings: [
            { rank: 1, stock_code: "600519.SH", industry: "食品饮料", score: 1.9, pe: 29.13, pb: 4.32, three_month_return: 0.0613 },
            { rank: 2, stock_code: "600001.SH", industry: "银行", score: 1.7, pe: 5.3, pb: 0.62, three_month_return: -0.011 },
          ],
        },
        {
          key: "deep_value_quality_pe80",
          label: "深度价值质量影子组合",
          role: "shadow_candidate",
          total_return: 0.3798,
          excess_return: 0.0674,
          max_drawdown: -0.0402,
          win_rate: 0.5,
          average_turnover: 0.3472,
          average_count: 26.92,
          average_pe: 31.08,
          average_pb: 2.42,
          weights: { value: 0.45, quality: 0.25, momentum: 0.05, low_vol: 0.1, dividend: 0.15 },
          constraints: { pe_max: 80, pb_max: null, turnover_cap: null },
          cost_results: [
            { cost_bps: 0, total_return: 0.3798, excess_return: 0.0674, max_drawdown: -0.0402 },
            { cost_bps: 20, total_return: 0.3593, excess_return: 0.0516, max_drawdown: -0.0447 },
            { cost_bps: 50, total_return: 0.3291, excess_return: 0.0282, max_drawdown: -0.0581 },
          ],
          latest_holdings: [
            { rank: 1, stock_code: "600519.SH", industry: "食品饮料", score: 2.0071, pe: 29.13, pb: 4.32, three_month_return: 0.0613 },
            { rank: 2, stock_code: "603008.SH", industry: "轻工制造", score: 1.9121, pe: 18.6, pb: 1.52, three_month_return: 0.0413 },
          ],
          admission: {
            status: "passed",
            label: "通过",
            summary: "可进入正式规则候选评审",
            criteria: [
              { key: "history_length", label: "历史周期", passed: true, actual: 13, threshold: ">=12" },
              {
                key: "cost_20bps_outperformance",
                label: "20bp 成本后胜出",
                passed: true,
                actual: { total_return: 0.3593, excess_return: 0.0516 },
                threshold: { total_return: ">-0.0505", excess_return: ">-0.0301" },
              },
              {
                key: "cost_50bps_outperformance",
                label: "50bp 成本后胜出",
                passed: true,
                actual: { total_return: 0.3291, excess_return: 0.0282 },
                threshold: { total_return: ">-0.058", excess_return: ">-0.038" },
              },
              { key: "drawdown", label: "最大回撤", passed: true, actual: -0.0402, threshold: ">=-0.0658" },
              { key: "diversification", label: "持仓分散度", passed: true, actual: 26.92, threshold: ">=15" },
              { key: "blocking_warnings", label: "阻断告警", passed: true, actual: [], threshold: "无" },
            ],
          },
        },
      ],
      period_returns: [
        {
          portfolio_key: "current_baseline",
          start_date: "2026-04-30",
          end_date: "2026-05-08",
          gross_return: -0.008,
          benchmark_return: -0.01,
          excess_return: 0.002,
          selected_count: 29,
          name_turnover: null,
          traded_notional: 1,
          cost_results: [{ cost_bps: 20, net_return: -0.01, cost: 0.002 }],
        },
        {
          portfolio_key: "deep_value_quality_pe80",
          start_date: "2026-04-30",
          end_date: "2026-05-08",
          gross_return: 0.031,
          benchmark_return: 0,
          excess_return: 0.031,
          selected_count: 27,
          name_turnover: null,
          traded_notional: 1,
          cost_results: [{ cost_bps: 20, net_return: 0.029, cost: 0.002 }],
        },
        {
          portfolio_key: "deep_value_quality_pe80",
          start_date: "2026-05-08",
          end_date: "2026-05-13",
          gross_return: -0.019,
          benchmark_return: -0.007,
          excess_return: -0.012,
          selected_count: 27,
          name_turnover: 0.2,
          traded_notional: 0.4,
          cost_results: [{ cost_bps: 20, net_return: -0.0198, cost: 0.0008 }],
        },
        {
          portfolio_key: "deep_value_quality_pe80",
          start_date: "2026-05-13",
          end_date: "2026-05-20",
          gross_return: 0.024,
          benchmark_return: 0.011,
          excess_return: 0.013,
          selected_count: 26,
          name_turnover: 0.3,
          traded_notional: 0.6,
          cost_results: [{ cost_bps: 20, net_return: 0.0228, cost: 0.0012 }],
        },
      ],
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          strategy_summaries: [],
        },
      }),
      getMacroToolkitStrategySummaries: async () => ({
        ...strategyEnvelope,
        result: {
          ...strategyEnvelope.result,
          shadow_portfolio_report: shadowReport,
        } as never,
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const report = await screen.findByLabelText("影子组合报告");
    expect(report).toHaveTextContent("只读影子组合");
    expect(report).toHaveTextContent("当前正式规则");
    expect(report).toHaveTextContent("深度价值质量影子组合");
    expect(report).toHaveTextContent("+38.0%");
    expect(report).toHaveTextContent("+6.7%");
    expect(report).toHaveTextContent("20bp");
    expect(report).toHaveTextContent("+35.9%");
    expect(report).toHaveTextContent("PE≤80");
    expect(report).not.toHaveTextContent("PB≤");
    expect(report).not.toHaveTextContent("换手≤");
    expect(report).toHaveTextContent("600519.SH");
    const review = await screen.findByLabelText("影子组合稳健性审查");
    expect(review).toHaveTextContent("周期胜负");
    expect(review).toHaveTextContent("2赢 / 1输");
    expect(review).toHaveTextContent("最佳 +3.1% / 最差 -1.2%");
    expect(review).toHaveTextContent("20bp/50bp 均胜出");
    expect(review).toHaveTextContent("准入结论");
    expect(review).toHaveTextContent("通过");
    expect(review).toHaveTextContent("可进入正式规则候选评审");
    expect(review).toHaveTextContent("历史周期");
    expect(review).toHaveTextContent("持仓分散度");
    expect(review).toHaveTextContent("持仓重合 1/2");
    expect(review).toHaveTextContent("新增观察 603008.SH");
    expect(review).toHaveTextContent("正式独有 600001.SH");
    const evidencePack = await screen.findByLabelText("影子组合准入证据包");
    expect(evidencePack).toHaveTextContent("评审动作");
    expect(evidencePack).toHaveTextContent("进入正式候选评审");
    expect(evidencePack).toHaveTextContent("不自动替换正式规则");
    expect(evidencePack).toHaveTextContent("规则版本");
    expect(evidencePack).toHaveTextContent("rv_macro_toolkit_shadow_portfolio_v1");
    expect(evidencePack).toHaveTextContent("回测窗口");
    expect(evidencePack).toHaveTextContent("2026-04-01 → 2026-05-27 / 13周期");
    expect(evidencePack).toHaveTextContent("成本模型");
    expect(evidencePack).toHaveTextContent("0/10/20/50bp");
    expect(evidencePack).toHaveTextContent("choice_stock_daily_observation / choice_stock_factor_snapshot");
    expect(evidencePack).toHaveTextContent("只读影子评估，不能作为正式投研信号");
  });

  it("shows why the shadow portfolio report is temporarily unavailable", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const strategyEnvelope = await baseClient.getMacroToolkitStrategySummaries();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          strategy_summaries: [],
        },
      }),
      getMacroToolkitStrategySummaries: async () => ({
        ...strategyEnvelope,
        result: {
          ...strategyEnvelope.result,
          shadow_portfolio_report: {
            status: "unavailable",
            basis: "read_only_shadow",
            label: "影子组合报告",
            as_of_date: null,
            completed_periods: 0,
            factor_dates: [],
            rule_version: "rv_macro_toolkit_shadow_portfolio_v1",
            tables_used: ["choice_stock_daily_observation", "choice_stock_factor_snapshot"],
            warnings: ["READ_ONLY_SHADOW_NOT_PRODUCTION", "DUCKDB_BUSY", "DUCKDB_OPEN_FAILED: IOException"],
            cost_model: {
              cost_bps: [0, 10, 20, 50],
              initial_build_included: true,
              final_liquidation_included: false,
            },
            benchmark: null,
            portfolios: [],
            period_returns: [],
          },
        } as never,
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const report = await screen.findByLabelText("影子组合报告");
    expect(report).toHaveTextContent("影子组合报告暂不可用");
    expect(report).toHaveTextContent("本地股票历史库正在刷新或被落库任务占用");
    expect(report).toHaveTextContent("DUCKDB_BUSY");
  });

  it("keeps analytical boundary and failing sources visible when macro toolkit reads fail", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => {
        throw new Error("Request failed: /ui/macro/toolkit/analysis?detail=core (502)");
      },
      getMacroToolkitScripts: async () => {
        throw new Error("Request failed: /ui/macro/toolkit/scripts (502)");
      },
      getMacroToolkitStrategySummaries: async () => {
        throw new Error("Request failed: /ui/macro/toolkit/analysis/strategy-summaries (502)");
      },
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const errorState = await screen.findByTestId("macro-toolkit-error-state");
    expect(errorState).toHaveTextContent("宏观工具暂不可用");
    expect(errorState).toHaveTextContent("分析/工具口径");
    expect(errorState).toHaveTextContent("非正式口径");
    expect(errorState).toHaveTextContent("macro_toolkit.analysis");
    expect(errorState).toHaveTextContent("/ui/macro/toolkit/analysis?detail=core");
    expect(errorState).toHaveTextContent("/ui/macro/toolkit/scripts");
    expect(errorState).toHaveTextContent("/ui/macro/toolkit/analysis/strategy-summaries");
    expect(await screen.findByRole("button", { name: /重试读取/ })).toBeInTheDocument();
  });
});
