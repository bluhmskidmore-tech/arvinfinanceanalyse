import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

describe("MacroToolkitPage", () => {
  it("renders from the workbench route", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    expect(
      await screen.findByRole("heading", { level: 1, name: "宏观分析结果" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("投研观点")).toBeInTheDocument();
    expect(await screen.findByText("证据覆盖")).toBeInTheDocument();
    expect(await screen.findByText("87.5%")).toBeInTheDocument();
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
    expect(await screen.findByText("移动均线策略")).toBeInTheDocument();
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

  it("loads strategy summaries from the dedicated endpoint and surfaces the shadow portfolio report", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
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
        result_meta: {
          ...analysisEnvelope.result_meta,
          result_kind: "macro_toolkit.analysis.strategy_summaries",
          formal_use_allowed: false,
          tables_used: ["choice_stock_daily_observation", "choice_stock_factor_snapshot"],
        },
        result: {
          strategy_summaries: [
            {
              key: "multi_factor_selection",
              label: "Multi-factor selection",
              group: "Equity strategies",
              status: "complete",
              tone: "neutral",
              primary_metric: { label: "Selected count", value: 30, unit: "" },
              evidence: ["choice_stock_factor_snapshot 2026-05-03"],
              warnings: [],
              result: {
                data_status: "complete",
                price_source: "choice_stock_daily_observation",
                factor_source: "choice_stock_factor_snapshot",
              },
            },
          ],
          shadow_portfolio_report: {
            status: "complete",
            basis: "read_only_shadow",
            label: "Shadow portfolio report",
            as_of_date: "2026-05-03",
            completed_periods: 2,
            factor_dates: ["2026-05-01", "2026-05-02", "2026-05-03"],
            rule_version: "rv_macro_toolkit_shadow_portfolio_v1",
            tables_used: ["choice_stock_daily_observation", "choice_stock_factor_snapshot"],
            warnings: ["READ_ONLY_SHADOW_NOT_PRODUCTION", "SHORT_HISTORY"],
            cost_model: {
              cost_bps: [0, 10, 20, 50],
              initial_build_included: true,
              final_liquidation_included: false,
              method: "cost_bps_applied_to_abs_weight_delta",
            },
            benchmark: {
              key: "equal_weight_factor_universe",
              label: "Equal-weight factor universe",
              total_return: 0.018,
              max_drawdown: -0.004,
            },
            portfolios: [
              {
                key: "current_baseline",
                label: "Current production rule",
                role: "production_reference",
                total_return: 0.019,
                excess_return: 0.001,
                max_drawdown: -0.003,
                win_rate: 0.5,
                average_turnover: 0.2,
                average_traded_notional: 0.4,
                average_count: 30,
                average_pe: 24.2,
                average_pb: 1.7,
                weights: { value: 0.3, quality: 0.25, momentum: 0.15, low_vol: 0.15, dividend: 0.15 },
                constraints: { pe_max: null, pb_max: null, turnover_cap: null, top_pct: 0.1, max_candidates: 30 },
                cost_results: [
                  { cost_bps: 0, total_return: 0.019, excess_return: 0.001, max_drawdown: -0.003, win_rate: 0.5 },
                  { cost_bps: 20, total_return: 0.017, excess_return: -0.001, max_drawdown: -0.004, win_rate: 0.5 },
                ],
                latest_holdings: [],
              },
              {
                key: "deep_value_quality_pe80",
                label: "Deep value quality shadow",
                role: "shadow_candidate",
                total_return: 0.026,
                excess_return: 0.008,
                max_drawdown: -0.002,
                win_rate: 1,
                average_turnover: 0.18,
                average_traded_notional: 0.35,
                average_count: 30,
                average_pe: 21.4,
                average_pb: 1.5,
                weights: { value: 0.45, quality: 0.25, momentum: 0.05, low_vol: 0.1, dividend: 0.15 },
                constraints: { pe_max: 80, pb_max: null, turnover_cap: null, top_pct: 0.1, max_candidates: 30 },
                cost_results: [
                  { cost_bps: 0, total_return: 0.026, excess_return: 0.008, max_drawdown: -0.002, win_rate: 1 },
                  { cost_bps: 20, total_return: 0.023, excess_return: 0.005, max_drawdown: -0.003, win_rate: 1 },
                  { cost_bps: 50, total_return: 0.02, excess_return: 0.002, max_drawdown: -0.004, win_rate: 0.5 },
                ],
                latest_holdings: [
                  {
                    rank: 1,
                    stock_code: "000001.SZ",
                    industry: "Technology",
                    score: 1.234,
                    pe: 18.5,
                    pb: 1.3,
                    three_month_return: 0.08,
                  },
                ],
                admission: {
                  status: "needs_review",
                  label: "Needs review",
                  summary: "Keep as shadow observation until validation is complete",
                  criteria: [
                    { key: "history_length", passed: false, actual: 2, threshold: ">=12" },
                    { key: "cost_20bps_outperformance", passed: true, actual: 0.005, threshold: "above reference" },
                  ],
                },
              },
            ],
            period_returns: [
              {
                portfolio_key: "deep_value_quality_pe80",
                start_date: "2026-05-01",
                end_date: "2026-05-02",
                gross_return: 0.011,
                benchmark_return: 0.008,
                excess_return: 0.003,
                selected_count: 30,
                name_turnover: null,
                traded_notional: 1,
                cost_results: [{ cost_bps: 20, net_return: 0.009, cost: 0.002 }],
              },
            ],
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const shadowPanel = await screen.findByLabelText("A股影子组合观察");
    expect(shadowPanel).toHaveTextContent("read_only_shadow");
    expect(shadowPanel).toHaveTextContent("rv_macro_toolkit_shadow_portfolio_v1");
    expect(shadowPanel).toHaveTextContent("READ_ONLY_SHADOW_NOT_PRODUCTION");
    expect(shadowPanel).toHaveTextContent("Deep value quality shadow");
    expect(shadowPanel).toHaveTextContent("Needs review");
    expect(shadowPanel).toHaveTextContent("20bp");
    expect(shadowPanel).toHaveTextContent("50bp");
    expect(shadowPanel).toHaveTextContent("000001.SZ");
    expect(shadowPanel).toHaveTextContent("choice_stock_daily_observation");
    expect(shadowPanel).toHaveTextContent("choice_stock_factor_snapshot");
  });

  it("keeps core analysis visible when the strategy summaries endpoint fails", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      getMacroToolkitStrategySummaries: async () => {
        throw new Error("Request failed: /ui/macro/toolkit/analysis/strategy-summaries (502)");
      },
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    expect(await screen.findByText("87.5%")).toBeInTheDocument();
    const strategySection = await screen.findByLabelText("绛栫暐渚涙暟闂幆");
    expect(strategySection).toHaveTextContent("/ui/macro/toolkit/analysis/strategy-summaries");
  });
});
