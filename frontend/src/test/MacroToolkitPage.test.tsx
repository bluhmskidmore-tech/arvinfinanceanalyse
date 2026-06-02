import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import type { ResultMeta } from "../api/contracts";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

const MACRO_TOOLKIT_CSS_PATH = resolve(
  process.cwd(),
  "src/features/macro-toolkit/pages/MacroToolkitPage.css",
);
const MACRO_TOOLKIT_PAGE_PATH = resolve(
  process.cwd(),
  "src/features/macro-toolkit/pages/MacroToolkitPage.tsx",
);

describe("MacroToolkitPage", () => {
  it("keeps the macro toolkit page off the monolithic API client entrypoint", () => {
    const source = readFileSync(MACRO_TOOLKIT_PAGE_PATH, "utf8");

    expect(source).not.toContain('from "../../../api/client";');
    expect(source).toContain('from "../../../api/clientContext"');
  });

  it("loads first-screen analysis through the deferred core scope", () => {
    const source = readFileSync(MACRO_TOOLKIT_PAGE_PATH, "utf8");

    expect(source).toContain('client.getMacroToolkitAnalysis({ detail: "core" })');
  });

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
    const dataHealth = await screen.findByLabelText("数据健康总览");
    expect(dataHealth).toHaveTextContent("指标覆盖");
    expect(dataHealth).toHaveTextContent("7/8");
    expect(dataHealth).toHaveTextContent("来源覆盖");
    expect(dataHealth).toHaveTextContent("7/9");
    expect(dataHealth).toHaveTextContent("最新来源日期");
    expect(dataHealth).toHaveTextContent("2026-04-30");
    expect(dataHealth).toHaveTextContent("能力降级");
    expect(dataHealth).toHaveTextContent("1");
    expect(dataHealth).toHaveTextContent("待处理数据项");
    expect(dataHealth).toHaveTextContent("M0041813");
    expect(dataHealth).toHaveTextContent("补齐 M0041813 后重新运行完整宏观分析");
    expect(dataHealth).toHaveTextContent("宏观领先指标");
    expect(dataHealth).toHaveTextContent("PMI_MISSING");
    expect(dataHealth).toHaveTextContent("重新完整分析");
    expect(dataHealth).toHaveTextContent("M0041813");
    const boundary = await screen.findByTestId("macro-toolkit-contract-boundary");
    expect(boundary).toHaveTextContent("分析/工具口径");
    expect(boundary).toHaveTextContent("非正式口径");
    expect(boundary).toHaveTextContent("macro_toolkit.analysis");
    expect(boundary).toHaveTextContent("rv_macro_toolkit_ui_v1");
    const hasonStrategy = await screen.findByTestId("macro-toolkit-hason-strategy");
    expect(hasonStrategy).toHaveTextContent("Hason");
    expect(hasonStrategy).toHaveTextContent("analytical");
    expect(hasonStrategy).toHaveTextContent("observation-only");
    expect(hasonStrategy).toHaveTextContent("4/5");
    expect(hasonStrategy).toHaveTextContent("Module gaps");
    expect(hasonStrategy).toHaveTextContent("1 partial");
    expect(hasonStrategy).toHaveTextContent("1 missing script");
    expect(await screen.findByTestId("macro-toolkit-hason-module-market_state")).toHaveTextContent(
      "market_state",
    );
    expect(await screen.findByTestId("macro-toolkit-hason-module-market_state")).toHaveTextContent(
      "script-chain complete",
    );
    const allocationModule = await screen.findByTestId("macro-toolkit-hason-module-allocation");
    expect(allocationModule).toHaveTextContent("script-chain partial");
    expect(allocationModule).toHaveTextContent("risk_parity_cn");
    expect(allocationModule).toHaveTextContent("rebalance_cn");
    expect(await screen.findByTestId("macro-toolkit-hason-runtime-gaps")).toHaveTextContent(
      "final_signal.csv",
    );
    expect(await screen.findByTestId("macro-toolkit-hason-runtime-gaps")).toHaveTextContent(
      "stale",
    );
    expect(await screen.findByTestId("macro-toolkit-hason-runtime-gaps")).toHaveTextContent(
      "CSV content date",
    );
    expect(await screen.findByTestId("macro-toolkit-hason-runtime-gaps")).toHaveTextContent(
      "content 2026-04-29",
    );
    expect(await screen.findByTestId("macro-toolkit-hason-runtime-gaps")).not.toHaveTextContent(
      "csv_content",
    );
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
    const permissionLabel = await screen.findByText("刷新状态");
    const permissionTile = permissionLabel.closest(".macro-toolkit-metric");
    expect(permissionTile).not.toBeNull();
    expect(permissionTile).toHaveTextContent("已授权");
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      "resource macro_toolkit.choice_stock · mode scoped_refresh · actions history / factor_snapshot · user anonymous",
    );
    expect(await screen.findByText("低拥挤度择时多因子")).toBeInTheDocument();
    expect((await screen.findAllByText(/M7/)).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(/M16/)).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("signal_aggregator")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("equity_strategies")).length).toBeGreaterThan(0);
  });

  it("renders macro observation as a read-only analysis route without operations controls", async () => {
    renderWorkbenchApp(["/macro-observation"]);

    expect(await screen.findByTestId("macro-toolkit-tailwind-cockpit")).toBeInTheDocument();
    expect(await screen.findByTestId("macro-toolkit-contract-boundary")).toHaveTextContent(
      "macro_toolkit.analysis",
    );
    expect(await screen.findByRole("heading", { level: 2, name: "核心信号" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 2, name: "市场踩踏风险" })).toBeInTheDocument();
    expect(await screen.findByTestId("macro-observation-readonly-boundary")).toHaveTextContent(
      "read-only",
    );

    expect(screen.queryByRole("button", { name: /刷新席位/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /刷新股票数据/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /运行选中脚本/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "脚本注册表" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "运行结果" })).not.toBeInTheDocument();
  });

  it("renders handwritten data-health repair items from the analysis contract", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const resultMeta: ResultMeta = {
      trace_id: "trace_macro_health_contract",
      basis: "analytical",
      result_kind: "macro_toolkit.analysis",
      formal_use_allowed: false,
      source_version: "sv_macro_health_contract",
      vendor_version: "vv_choice_tushare",
      rule_version: "rv_macro_health_contract",
      cache_version: "cv_macro_health_contract",
      quality_flag: "warning",
      vendor_status: "vendor_stale",
      fallback_mode: "none",
      scenario_flag: false,
      as_of_date: "2026-04-10",
      generated_at: "2026-04-10T10:00:00Z",
      tables_used: ["system_macro_sources"],
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        result_meta: resultMeta,
        result: {
          default_data_sources: ["choice", "tushare"],
          as_of_date: "2026-04-10",
          conclusion: {
            stance: "数据健康待处理",
            tone: "neutral",
            summary: "存在缺失、滞后、降级和延后加载项。",
            recommended_action: "先处理高优先级输入，再查看完整分析。",
          },
          coverage: {
            indicator_count: 1,
            hit_count: 0,
            hit_rate: 0,
            script_count: 0,
            output_file_count: 0,
          },
          indicators: [],
          signal_cards: [],
          capability_results: [],
          strategy_summaries: [],
          output_files: [],
          source_checks: [],
          capabilities: [],
          runtime_status: {
            analysis_scope: "core",
            deferred_sections: [
              {
                key: "source_checks",
                label: "来源检查",
                status: "deferred",
              },
            ],
          },
          data_health: {
            analysis_scope: "core",
            indicator_coverage: {
              hit_count: 0,
              total_count: 1,
              hit_rate: 0,
              missing_count: 1,
              missing: [{ key: "ncd_3m", alias: "M0041813", label: "3M NCD" }],
            },
            source_coverage: {
              hit_count: 0,
              total_count: 0,
              hit_rate: null,
              latest_date: null,
              deferred: true,
              missing_aliases: [],
            },
            capability_results: {
              complete: 0,
              degraded: 0,
              unavailable: 0,
              total_count: 0,
              deferred: true,
            },
            capability_plan: {
              ready_count: 0,
              wired_count: 0,
              total_count: 0,
              deferred: true,
            },
            deferred_sections: ["source_checks"],
            warnings: ["存在待处理数据项"],
            repair_items: [
              {
                type: "missing",
                scope: "core",
                priority: "high",
                key: "indicator:ncd_3m",
                alias: "M0041813",
                label: "3M NCD",
                suggested_action: "补齐 M0041813 后重新运行完整宏观分析；缺失项不能按 0 处理。",
                action: {
                  kind: "source_backfill_required",
                  label: "需要补齐来源数据",
                  enabled: false,
                  reason: "当前没有已接入的一键宏观序列刷新接口。",
                  analysis_detail: "full",
                },
              },
              {
                type: "stale",
                scope: "core",
                priority: "medium",
                key: "source:CU0",
                alias: "CU0",
                label: "CU0",
                source_table: "system_macro_sources",
                latest_date: "2026-04-01",
                reference_date: "2026-04-10",
                stale_days: 9,
                suggested_action: "CU0 最新 2026-04-01，落后分析日 2026-04-10 9 天；刷新 Choice/Tushare 后再确认。",
                action: {
                  kind: "source_backfill_required",
                  label: "需要刷新来源",
                  enabled: false,
                  reason: "当前没有已接入的一键宏观序列刷新接口。",
                  analysis_detail: "full",
                },
              },
              {
                type: "degraded",
                scope: "core",
                priority: "medium",
                key: "capability:leading_indicator",
                label: "宏观领先指标",
                suggested_action: "宏观领先指标 当前 degraded：PMI_MISSING；补齐输入证据后重新运行完整宏观分析。",
                action: {
                  kind: "load_full_analysis",
                  label: "重新完整分析",
                  enabled: true,
                  reason: "补齐输入证据后重新运行完整分析确认状态。",
                  analysis_detail: "full",
                },
              },
              {
                type: "deferred",
                scope: "core",
                priority: "low",
                key: "deferred:source_checks",
                label: "source_checks",
                suggested_action: "打开完整分析后确认 source_checks，不把首屏延后加载当作缺失。",
                action: {
                  kind: "load_full_analysis",
                  label: "查看完整分析",
                  enabled: true,
                  reason: "首屏延后加载，完整分析可确认。",
                  analysis_detail: "full",
                },
              },
            ],
          },
          warnings: [],
        },
      }),
      getMacroToolkitStrategySummaries: async () => ({
        result_meta: { ...resultMeta, result_kind: "macro_toolkit.strategy_summaries" },
        result: { strategy_summaries: [] },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-observation"], { client });

    const dataHealth = await screen.findByLabelText("数据健康总览");
    expect(dataHealth).toHaveTextContent("3M NCD");
    expect(dataHealth).toHaveTextContent("CU0");
    expect(dataHealth).toHaveTextContent("落后 9 天");
    expect(dataHealth).toHaveTextContent("宏观领先指标");
    expect(dataHealth).toHaveTextContent("PMI_MISSING");
    expect(dataHealth).toHaveTextContent("完整分析后确认");
    expect(dataHealth).toHaveTextContent("当前没有已接入的一键宏观序列刷新接口。");
    expect(within(dataHealth).queryByRole("button", { name: "查看完整分析" })).not.toBeInTheDocument();
    expect(within(dataHealth).queryByRole("button", { name: "重新完整分析" })).not.toBeInTheDocument();
  });

  it("shows M7/M10/M14 input evidence and missing-input warnings in capability results", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    const m7Text = await screen.findByText((content) => content.includes("Policy rate 7D"));
    await waitFor(() => {
      const capabilityPmiTexts = screen
        .getAllByText((content) => content.includes("PMI_MISSING"))
        .filter((item) => item.closest(".macro-toolkit-capability-result"));
      expect(capabilityPmiTexts.length).toBeGreaterThanOrEqual(2);
    });
    const m10Texts = screen
      .getAllByText((content) => content.includes("PMI_MISSING"))
      .filter((item) => item.closest(".macro-toolkit-capability-result"));
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
    expect(
      screen.getByText("核心信号已先返回；市场踩踏风险需打开完整分析后显示。"),
    ).toBeInTheDocument();
  });

  it("loads the full macro analysis from the core first screen action", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const calls: Array<Parameters<ApiClient["getMacroToolkitAnalysis"]>[0]> = [];
    const coreCrisisCard = {
      key: "crisis_score_cn",
      title: "Crisis Score",
      stance: "完整结果待加载",
      tone: "neutral",
      score: null,
      evidence: ["首屏未运行完整 Crisis Score，打开完整分析后显示分数"],
    } as const;
    const coreSignalCards = analysisEnvelope.result.signal_cards.map((card) =>
      card.key === "crisis_score_cn" ? coreCrisisCard : card,
    );
    const coreSignalCardsWithCrisis = [
      coreCrisisCard,
      ...coreSignalCards.filter((card) => card.key !== "crisis_score_cn"),
    ];
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async (options) => {
        calls.push(options);
        const coreDataHealth = {
          ...analysisEnvelope.result.data_health!,
          analysis_scope: "core",
          source_coverage: {
            hit_count: 0,
            total_count: 0,
            hit_rate: null,
            latest_date: null,
            deferred: true,
            missing_aliases: [],
          },
          capability_results: {
            complete: 0,
            degraded: 0,
            unavailable: 0,
            total_count: 0,
            deferred: true,
          },
          capability_plan: {
            ready_count: 0,
            wired_count: 0,
            total_count: 0,
            deferred: true,
          },
          deferred_sections: ["capability_results", "source_checks"],
          repair_items: [
            {
              type: "deferred",
              scope: "core",
              priority: "low",
              key: "deferred:source_checks",
              alias: null,
              label: "source_checks",
              source_table: null,
              latest_date: null,
              reference_date: "2026-04-30",
              stale_days: null,
              suggested_action: "打开完整分析后确认 source_checks，不把首屏延后加载当作缺失。",
              action: {
                kind: "load_full_analysis",
                label: "查看完整分析",
                enabled: true,
                reason: "首屏延后加载，完整分析可确认。",
                analysis_detail: "full",
              },
              tags: ["deferred"],
            },
          ],
        } as const;
        return {
          ...analysisEnvelope,
          result: {
            ...analysisEnvelope.result,
            runtime_status: {
              analysis_scope: options?.detail === "full" ? "full" : "core",
              deferred_sections:
                options?.detail === "full"
                  ? []
                  : [
                      {
                        key: "capability_results",
                        label: "功能结果",
                        status: "deferred",
                      },
                    ],
            },
            capability_results:
              options?.detail === "full" ? analysisEnvelope.result.capability_results : [],
            signal_cards:
              options?.detail === "full" ? analysisEnvelope.result.signal_cards : coreSignalCardsWithCrisis,
            data_health: options?.detail === "full" ? analysisEnvelope.result.data_health : coreDataHealth,
          },
        };
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    expect(await screen.findByText("完整结果待加载")).toBeInTheDocument();
    const coreDataHealth = await screen.findByLabelText("数据健康总览");
    expect(coreDataHealth).toHaveTextContent("待处理数据项");
    expect(coreDataHealth).toHaveTextContent("完整分析后确认");
    expect(coreDataHealth).not.toHaveTextContent("来源未命中");
    expect(screen.queryByLabelText("Crisis Score 数据来源")).not.toBeInTheDocument();
    await user.click(within(coreDataHealth).getByRole("button", { name: /查看完整分析/ }));
    expect(calls).toContainEqual({ detail: "full" });
    await screen.findByLabelText("Crisis Score 数据来源");

    expect(calls).toContainEqual({ detail: "full" });
    const fullDataHealth = await screen.findByLabelText("数据健康总览");
    expect(fullDataHealth).toHaveTextContent("待处理数据项");
    expect(fullDataHealth).toHaveTextContent("补齐 M0041813 后重新运行完整宏观分析");
    expect(fullDataHealth).toHaveTextContent("PMI_MISSING");
    await user.click(within(fullDataHealth).getAllByRole("button", { name: /重新完整分析/ })[0]!);
    expect(calls.filter((item) => item?.detail === "full")).toHaveLength(2);
    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    expect(crisisEvidence).toHaveTextContent("分数组件覆盖");
    expect(crisisEvidence).toHaveTextContent("5/5");
    expect(crisisEvidence).toHaveTextContent("Nanhua commodity index");
    expect(crisisEvidence).toHaveTextContent("NH0100.NHF");
    expect(crisisEvidence).toHaveTextContent("commodity_vol");
    expect(crisisEvidence).toHaveTextContent("2026-04-10");
    expect(crisisEvidence).toHaveTextContent("120 rows");
    expect(crisisEvidence).toHaveTextContent("商品旁证覆盖");
    expect(crisisEvidence).toHaveTextContent("6/6");
    expect(crisisEvidence).toHaveTextContent("supplemental_observation");
    expect(crisisEvidence).toHaveTextContent("Crisis Score 公式仍仅使用 nanhua");
    expect(crisisEvidence).toHaveTextContent("Copper futures");
    expect(crisisEvidence).toHaveTextContent("CU0 / CU0.SHF");
    expect(crisisEvidence).toHaveTextContent("matched CU0");
    expect(crisisEvidence).toHaveTextContent("同日");
    expect(crisisEvidence).toHaveTextContent("Crude oil futures");
    expect(crisisEvidence).toHaveTextContent("Gold futures");
    expect(crisisEvidence).toHaveTextContent("未纳入公式");
    expect(screen.queryByRole("button", { name: "查看完整分析" })).not.toBeInTheDocument();
  });

  it("shows the full analysis action in the runtime strip when core capability results are deferred", async () => {
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
                key: "capability_results",
                label: "功能结果",
                status: "deferred",
              },
            ],
          },
          capability_results: [],
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const runtimeStrip = await screen.findByLabelText("宏观工具运行状态");
    expect(within(runtimeStrip).getByRole("button", { name: "查看完整分析" })).toBeInTheDocument();
  });

  it("does not mark Hason runtime outputs ready when freshness is unknown", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const hasonStrategy = analysisEnvelope.result.hason_strategy;
    if (!hasonStrategy) {
      throw new Error("mock analysis is missing hason_strategy");
    }
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          hason_strategy: {
            ...hasonStrategy,
            status: "degraded",
            runtime_output_status: "unknown",
            missing_runtime_outputs: [],
            stale_runtime_outputs: [],
            runtime_outputs: hasonStrategy.runtime_outputs.map((item) => ({
              ...item,
              freshness_status: "unknown",
              freshness_basis: "file_modified_date",
              content_date: null,
              content_date_min: null,
              content_date_max: null,
              modified_date: null,
              reference_date: "2026-04-30",
            })),
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const runtimeGaps = await screen.findByTestId("macro-toolkit-hason-runtime-gaps");
    expect(runtimeGaps).toHaveTextContent("unknown");
    expect(runtimeGaps).toHaveTextContent("final_signal.csv");
    expect(runtimeGaps).toHaveTextContent("crowding_latest.csv");
    const hasonStrategyPanel = await screen.findByTestId("macro-toolkit-hason-strategy");
    expect(hasonStrategyPanel).toHaveTextContent("Runtime outputs");
    expect(hasonStrategyPanel).toHaveTextContent("unknown · 2");
    expect(runtimeGaps).not.toHaveTextContent("runtime outputs · current");
  });

  it("shows Hason mixed CSV content date ranges", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const hasonStrategy = analysisEnvelope.result.hason_strategy;
    if (!hasonStrategy) {
      throw new Error("mock analysis is missing hason_strategy");
    }
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          hason_strategy: {
            ...hasonStrategy,
            status: "degraded",
            runtime_output_status: "unknown",
            runtime_output_gaps: ["final_signal.csv"],
            runtime_outputs: hasonStrategy.runtime_outputs.map((item) =>
              item.name === "final_signal.csv"
                ? {
                    ...item,
                    freshness_status: "mixed",
                    content_date: "2026-04-30",
                    content_date_min: "2026-04-29",
                    content_date_max: "2026-04-30",
                  }
                : {
                    ...item,
                    freshness_status: "current",
                    content_date: "2026-04-30",
                    content_date_min: "2026-04-30",
                    content_date_max: "2026-04-30",
                  },
            ),
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const runtimeGaps = await screen.findByTestId("macro-toolkit-hason-runtime-gaps");
    expect(runtimeGaps).toHaveTextContent("mixed");
    expect(runtimeGaps).toHaveTextContent("content 2026-04-29..2026-04-30");
    expect(await screen.findByTestId("macro-toolkit-hason-strategy")).toHaveTextContent("unknown · 1");
  });

  it("shows Hason invalid CSV content date counts", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const hasonStrategy = analysisEnvelope.result.hason_strategy;
    if (!hasonStrategy) {
      throw new Error("mock analysis is missing hason_strategy");
    }
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          hason_strategy: {
            ...hasonStrategy,
            status: "degraded",
            runtime_output_status: "unknown",
            runtime_output_gaps: ["final_signal.csv"],
            runtime_outputs: hasonStrategy.runtime_outputs.map((item) =>
              item.name === "final_signal.csv"
                ? {
                    ...item,
                    freshness_status: "invalid_date",
                    content_date: "2026-04-30",
                    content_date_min: "2026-04-30",
                    content_date_max: "2026-04-30",
                    content_date_invalid_count: 1,
                  }
                : {
                    ...item,
                    freshness_status: "current",
                    content_date: "2026-04-30",
                    content_date_min: "2026-04-30",
                    content_date_max: "2026-04-30",
                    content_date_invalid_count: 0,
                  },
            ),
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const runtimeGaps = await screen.findByTestId("macro-toolkit-hason-runtime-gaps");
    expect(runtimeGaps).toHaveTextContent("invalid_date");
    expect(runtimeGaps).toHaveTextContent("1 invalid date");
    expect(await screen.findByTestId("macro-toolkit-hason-strategy")).toHaveTextContent("unknown · 1");
  });

  it("shows Hason unknown CSV content freshness without treating file time as proof", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const hasonStrategy = analysisEnvelope.result.hason_strategy;
    if (!hasonStrategy) {
      throw new Error("mock analysis is missing hason_strategy");
    }
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          hason_strategy: {
            ...hasonStrategy,
            status: "degraded",
            runtime_output_status: "unknown",
            runtime_output_gaps: ["final_signal.csv"],
            runtime_outputs: hasonStrategy.runtime_outputs.map((item) =>
              item.name === "final_signal.csv"
                ? {
                    ...item,
                    freshness_status: "unknown",
                    freshness_basis: "csv_content",
                    content_date: null,
                    content_date_min: null,
                    content_date_max: null,
                    content_date_invalid_count: 0,
                    modified_date: "2026-04-30",
                  }
                : {
                    ...item,
                    freshness_status: "current",
                    freshness_basis: "csv_content",
                    content_date: "2026-04-30",
                    content_date_min: "2026-04-30",
                    content_date_max: "2026-04-30",
                    content_date_invalid_count: 0,
                  },
            ),
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const runtimeGaps = await screen.findByTestId("macro-toolkit-hason-runtime-gaps");
    expect(runtimeGaps).toHaveTextContent("final_signal.csv: unknown CSV content date");
    expect(runtimeGaps).toHaveTextContent("file 2026-04-30");
    expect(await screen.findByTestId("macro-toolkit-hason-strategy")).toHaveTextContent("unknown · 1");
  });

  it("labels fully current Hason output as observation-ready, not formal use", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const hasonStrategy = analysisEnvelope.result.hason_strategy;
    if (!hasonStrategy) {
      throw new Error("mock analysis is missing hason_strategy");
    }
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          hason_strategy: {
            ...hasonStrategy,
            status: "observation_ready",
            readiness: {
              ...hasonStrategy.readiness,
              ready_modules: hasonStrategy.readiness.total_modules,
              partial_modules: 0,
              missing_modules: 0,
              missing_script_count: 0,
              ratio: 1,
            },
            modules: hasonStrategy.modules.map((module) => ({
              ...module,
              status: "integrated",
              available_scripts: module.scripts,
              missing_scripts: [],
            })),
            runtime_output_status: "current",
            runtime_output_gaps: [],
            missing_runtime_outputs: [],
            stale_runtime_outputs: [],
            runtime_outputs: hasonStrategy.runtime_outputs.map((item) => ({
              ...item,
              freshness_status: "current",
              freshness_basis: "csv_content",
              content_date: "2026-04-30",
              content_date_min: "2026-04-30",
              content_date_max: "2026-04-30",
              content_date_invalid_count: 0,
              modified_date: "2026-04-30",
            })),
            observation_only: true,
            formal_use_allowed: false,
            formal_metric_id: null,
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const hasonStrategyPanel = await screen.findByTestId("macro-toolkit-hason-strategy");
    expect(hasonStrategyPanel).toHaveTextContent("observation-ready");
    expect(hasonStrategyPanel).toHaveTextContent("observation-only");
    expect(hasonStrategyPanel).toHaveTextContent("no formal MTR");
    expect(hasonStrategyPanel).toHaveTextContent("Runtime outputs");
    expect(hasonStrategyPanel).toHaveTextContent("current");
    expect(hasonStrategyPanel).not.toHaveTextContent("Runtime outputsready");
    expect(hasonStrategyPanel.querySelector(".macro-toolkit-metric:nth-child(1)")).not.toHaveClass(
      "macro-toolkit-metric--positive",
    );
    expect(hasonStrategyPanel.querySelector(".macro-toolkit-metric:nth-child(2)")).not.toHaveClass(
      "macro-toolkit-metric--positive",
    );
    expect(hasonStrategyPanel.querySelector(".macro-toolkit-metric:nth-child(4)")).not.toHaveClass(
      "macro-toolkit-metric--positive",
    );
    const marketStateModule = await screen.findByTestId("macro-toolkit-hason-module-market_state");
    expect(marketStateModule).toHaveTextContent("script-chain complete");
    expect(marketStateModule).not.toHaveTextContent("integrated");
  });

  it("counts all available Hason source trace scripts while keeping the detail preview bounded", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const hasonStrategy = analysisEnvelope.result.hason_strategy;
    if (!hasonStrategy) {
      throw new Error("mock analysis is missing hason_strategy");
    }
    const sourceTrace = Array.from({ length: 7 }, (_, index) => ({
      script: `trace_script_${index + 1}`,
      filename: `trace_script_${index + 1}.py`,
      group: "Hason",
      available: true,
      modules: index === 0 ? ["market_state", "risk_management"] : ["market_state"],
    }));
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          hason_strategy: {
            ...hasonStrategy,
            source_trace: sourceTrace,
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const hasonStrategyPanel = await screen.findByTestId("macro-toolkit-hason-strategy");
    const scriptTraceMetric = hasonStrategyPanel.querySelector("[data-testid='macro-toolkit-hason-script-trace']");
    expect(scriptTraceMetric).toHaveTextContent("Script trace");
    expect(scriptTraceMetric).toHaveTextContent("7");
    expect(scriptTraceMetric).toHaveTextContent("trace_script_1");
    const scriptTraceDetail = scriptTraceMetric?.querySelector("small");
    expect(scriptTraceDetail).toHaveAttribute(
      "title",
      expect.stringContaining("trace_script_1[market_state+risk_management]"),
    );
    expect(scriptTraceDetail).toHaveAttribute("title", expect.stringContaining("trace_script_5"));
    expect(scriptTraceDetail).not.toHaveAttribute("title", expect.stringContaining("trace_script_6"));
  });

  it("renders legacy Hason source trace entries without module context", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const hasonStrategy = analysisEnvelope.result.hason_strategy;
    if (!hasonStrategy) {
      throw new Error("mock analysis is missing hason_strategy");
    }
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          hason_strategy: {
            ...hasonStrategy,
            source_trace: [
              {
                script: "legacy_trace",
                filename: "legacy_trace.py",
                group: "legacy",
                available: true,
              },
            ],
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const scriptTraceMetric = await screen.findByTestId("macro-toolkit-hason-script-trace");
    expect(scriptTraceMetric).toHaveTextContent("legacy_trace");
  });

  it("keeps missing Hason scripts in the trace preview with module context", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const hasonStrategy = analysisEnvelope.result.hason_strategy;
    if (!hasonStrategy) {
      throw new Error("mock analysis is missing hason_strategy");
    }
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          hason_strategy: {
            ...hasonStrategy,
            source_trace: [
              {
                script: "rebalance_cn",
                filename: null,
                group: null,
                available: false,
                modules: ["allocation"],
              },
              {
                script: "risk_parity_cn",
                filename: "risk_parity_cn.py",
                group: "allocation",
                available: true,
                modules: ["allocation"],
              },
            ],
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const scriptTraceMetric = await screen.findByTestId("macro-toolkit-hason-script-trace");
    expect(scriptTraceMetric).toHaveTextContent("2");
    const scriptTraceDetail = scriptTraceMetric.querySelector("small");
    expect(scriptTraceDetail).toHaveAttribute("title", expect.stringContaining("rebalance_cn[allocation]:missing"));
    expect(scriptTraceDetail).toHaveAttribute("title", expect.stringContaining("risk_parity_cn[allocation]"));
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
    expect(strategySupply).toHaveTextContent("fallback latest_available · 最近可用 2026-04-27");
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

  it("shows scoped Choice refresh permission as authorized with trace detail", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const strategyEnvelope = await baseClient.getMacroToolkitStrategySummaries();
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
            permission: {
              mode: "scoped_refresh",
              allowed: true,
              user_id: "stock-refresh-user",
              role: "viewer",
              identity_source: "header",
              resource: "macro_toolkit.choice_stock",
              actions: ["history", "factor_snapshot"],
            },
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const permissionLabel = await screen.findByText("刷新状态");
    const permissionTile = permissionLabel.closest(".macro-toolkit-metric");
    expect(permissionTile).not.toBeNull();
    expect(permissionTile).toHaveTextContent("已授权");
    expect(permissionTile).not.toHaveTextContent("待确认");
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      "resource macro_toolkit.choice_stock · mode scoped_refresh · actions history / factor_snapshot · user stock-refresh-user",
    );
  });

  it("shows latest Choice refresh run status beside authorization evidence", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const strategyEnvelope = await baseClient.getMacroToolkitStrategySummaries();
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
            refresh: {
              status: "completed",
              run_id: "choice_stock_refresh:2026-04-30:done",
              report_date: "2026-04-30",
              trigger_mode: "terminal",
              history_row_count: 111,
              factor_row_count: 222,
              source_version: "sv_factor",
              vendor_version: "vv_factor",
              rule_version: "rv_choice_stock_refresh_v1",
              cache_version: "choice_stock_refresh_v1",
              permission: choiceStockRefresh.permission,
            },
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const permissionLabel = await screen.findByText("刷新状态");
    const permissionTile = permissionLabel.closest(".macro-toolkit-metric");
    expect(permissionTile).not.toBeNull();
    expect(permissionTile).toHaveTextContent("已完成");
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      "run choice_stock_refresh:2026-04-30:done · report 2026-04-30 · trigger terminal · rows history 111 / factor 222 · source sv_factor · vendor vv_factor · rule rv_choice_stock_refresh_v1 · cache choice_stock_refresh_v1 · resource macro_toolkit.choice_stock · mode scoped_refresh · actions history / factor_snapshot · user anonymous",
    );
  });

  it("shows Choice refresh failure category and reason in run evidence", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const strategyEnvelope = await baseClient.getMacroToolkitStrategySummaries();
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
            refresh: {
              status: "failed",
              run_id: "choice_stock_refresh:2026-04-30:failed",
              report_date: "2026-04-30",
              trigger_mode: "terminal",
              history_row_count: 111,
              factor_row_count: null,
              failure_category: "ChoiceVendorError",
              failure_reason: "factor snapshot vendor unavailable",
              error_message: "ChoiceVendorError: factor snapshot vendor unavailable",
              permission: choiceStockRefresh.permission,
            },
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const permissionLabel = await screen.findByText("刷新状态");
    const permissionTile = permissionLabel.closest(".macro-toolkit-metric");
    expect(permissionTile).not.toBeNull();
    expect(permissionTile).toHaveTextContent("失败");
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      "run choice_stock_refresh:2026-04-30:failed · report 2026-04-30 · trigger terminal · rows history 111 / factor - · failure ChoiceVendorError: factor snapshot vendor unavailable · resource macro_toolkit.choice_stock · mode scoped_refresh · actions history / factor_snapshot · user anonymous",
    );
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
              missing_factor_inputs: [
                "pe",
                "pb",
                "ps",
                "roe",
                "gross_margin",
                "three_month_return",
                "twelve_month_return",
                "volatility",
                "dividend_yield",
              ],
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
    expect(multiFactorCard).toHaveTextContent(
      "pe / pb / ps / roe / gross_margin / three_month_return / twelve_month_return / volatility / dividend_yield",
    );
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
