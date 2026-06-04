import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import { ApiClientProvider } from "../api/clientContext";
import type { ResultMeta } from "../api/contracts";
import MacroToolkitPage from "../features/macro-toolkit/pages/MacroToolkitPage";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

const MACRO_TOOLKIT_CSS_PATH = resolve(
  process.cwd(),
  "src/features/macro-toolkit/pages/MacroToolkitPage.css",
);
const MACRO_TOOLKIT_PAGE_PATH = resolve(
  process.cwd(),
  "src/features/macro-toolkit/pages/MacroToolkitPage.tsx",
);

type MacroToolkitAnalysisEnvelope = Awaited<ReturnType<ApiClient["getMacroToolkitAnalysis"]>>;
type MacroToolkitCapabilityResultFixture =
  MacroToolkitAnalysisEnvelope["result"]["capability_results"][number];
type MacroToolkitInputEvidenceFixture = NonNullable<
  NonNullable<MacroToolkitCapabilityResultFixture["input_evidence"]>["inputs"]
>[number];

function requireInputEvidenceInputs(
  result: MacroToolkitCapabilityResultFixture,
): MacroToolkitInputEvidenceFixture[] {
  const inputs = result.input_evidence?.inputs;
  if (!inputs) {
    throw new Error(`Missing input evidence for ${result.key}`);
  }
  return inputs;
}

function requireClosestElement<T extends Element>(element: T | null, label: string): T {
  if (!element) {
    throw new Error(`Missing ${label}`);
  }
  return element;
}

function withCrisisScoreInputEvidence(
  envelope: MacroToolkitAnalysisEnvelope,
  inputs: MacroToolkitInputEvidenceFixture[],
  warnings: string[],
) {
  return {
    ...envelope,
    result: {
      ...envelope.result,
      capability_results: envelope.result.capability_results.map((result) => {
        if (result.key !== "crisis_score_cn") {
          return result;
        }
        const rawInputEvidence =
          result.result.input_evidence && typeof result.result.input_evidence === "object"
            ? result.result.input_evidence
            : {};
        return {
          ...result,
          status: warnings.length ? ("degraded" as const) : result.status,
          warnings,
          input_evidence: result.input_evidence
            ? {
                ...result.input_evidence,
                inputs,
                missing_inputs: warnings,
              }
            : result.input_evidence,
          result: {
            ...result.result,
            input_evidence: {
              ...rawInputEvidence,
              inputs,
              missing_inputs: warnings,
            },
          },
        };
      }),
    },
  };
}

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
    expect(css).toContain(".macro-toolkit-crisis-shadow-impact");
    expect(css).toContain(".macro-toolkit-crisis-shadow-impact__metrics");
    expect(css).toContain(".macro-toolkit-crisis-shadow-impact__grid");
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

  it("ignores cached script registry payloads on the macro observation route", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const [scriptEnvelope, analysisEnvelope] = await Promise.all([
      baseClient.getMacroToolkitScripts(),
      baseClient.getMacroToolkitAnalysis(),
    ]);
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          source_checks: [
            {
              alias: "OBS_ONLY",
              row_count: 1,
              latest: {
                date: "2026-04-30",
                series_id: "OBS_ONLY",
                vendor_name: "choice",
                value: 1,
              },
            },
          ],
          capabilities: [],
        },
      }),
    } as ApiClient;
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: 0,
          refetchOnWindowFocus: false,
        },
      },
    });
    queryClient.setQueryData(["macro-toolkit", "scripts"], scriptEnvelope);

    render(
      <ApiClientProvider client={client}>
        <QueryClientProvider client={queryClient}>
          <MacroToolkitPage mode="observation" />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    const readiness = await screen.findByLabelText("宏观工具投研总览");
    expect(readiness).toHaveTextContent("1 个源命中");
    expect(await screen.findByText("能力闭环")).toBeInTheDocument();
    expect(screen.getByText("0/0")).toBeInTheDocument();
    expect(screen.queryByText(scriptEnvelope.result.scripts[0]?.name ?? "")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "脚本注册表" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /运行选中脚本/ })).not.toBeInTheDocument();
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
                  enabled: true,
                  reason: "可触发宏观来源补齐；完成后重新运行完整分析确认。",
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
    expect(dataHealth).toHaveTextContent("可触发宏观来源补齐");
    expect(dataHealth).toHaveTextContent("当前没有已接入的一键宏观序列刷新接口。");
    expect(within(dataHealth).queryByRole("button", { name: "需要刷新来源" })).not.toBeInTheDocument();
    expect(within(dataHealth).queryByRole("button", { name: "查看完整分析" })).not.toBeInTheDocument();
    expect(within(dataHealth).queryByRole("button", { name: "重新完整分析" })).not.toBeInTheDocument();
  });

  it("surfaces the hidden count when data-health repair items are truncated", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const repairItems = Array.from({ length: 8 }, (_, index) => {
      const itemNumber = index + 1;
      return {
        type: "missing",
        scope: "full",
        priority: "medium",
        key: `repair:${itemNumber}`,
        alias: `MISSING_${itemNumber}`,
        label: `缺口 ${itemNumber}`,
        source_table: "system_macro_sources",
        latest_date: null,
        reference_date: "2026-04-30",
        stale_days: null,
        suggested_action: `补齐缺口 ${itemNumber} 后重新运行完整宏观分析。`,
        action: null,
        tags: ["missing"],
      };
    });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          data_health: {
            ...analysisEnvelope.result.data_health!,
            repair_items: repairItems,
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-observation"], { client });

    const repairList = await screen.findByLabelText("待处理数据项");
    expect(repairList).toHaveTextContent("缺口 6");
    expect(repairList).not.toHaveTextContent("缺口 7");
    expect(repairList).toHaveTextContent("还有 2 项未显示");
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
    const sourceBackfillCalls: Array<Parameters<ApiClient["refreshMacroSourceBackfill"]>[0]> = [];
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
      refreshMacroSourceBackfill: async (options) => {
        sourceBackfillCalls.push(options);
        return {
          result_meta: {
            ...analysisEnvelope.result_meta,
            result_kind: "macro_toolkit.source_backfill_refresh",
          },
          result: {
            refresh: {
              status: "completed",
              alias: options.alias,
              series_ids: ["NCD.SHIBOR.3M"],
              total_added: 42,
            },
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
    await user.click(within(fullDataHealth).getByRole("button", { name: /需要补齐来源数据/ }));
    expect(sourceBackfillCalls).toEqual([
      {
        alias: "M0041813",
        startDate: undefined,
        endDate: "2026-04-30",
        sources: undefined,
      },
    ]);
    expect(calls.filter((item) => item?.detail === "full")).toHaveLength(2);
    await user.click(within(fullDataHealth).getAllByRole("button", { name: /重新完整分析/ })[0]!);
    await waitFor(() => expect(calls.filter((item) => item?.detail === "full")).toHaveLength(3));
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
    expect(crisisEvidence).toHaveTextContent("候选商品仅做影子评估，当前未计入 Crisis Score 分数");
    expect(crisisEvidence).toHaveTextContent("Copper futures");
    expect(crisisEvidence).toHaveTextContent("CU0 / CU0.SHF");
    expect(crisisEvidence).toHaveTextContent("matched CU0");
    expect(crisisEvidence).toHaveTextContent("同日");
    expect(crisisEvidence).toHaveTextContent("Crude oil futures");
    expect(crisisEvidence).toHaveTextContent("Gold futures");
    expect(crisisEvidence).toHaveTextContent("未纳入公式");
    expect(crisisEvidence).toHaveTextContent("商品扩展候选");
    expect(crisisEvidence).toHaveTextContent("影子评估就绪");
    expect(crisisEvidence).toHaveTextContent("6 个就绪");
    expect(crisisEvidence).toHaveTextContent("公式变更需审批");
    expect(crisisEvidence).toHaveTextContent("历史回测、相关性检验、权重审批");
    expect(crisisEvidence).toHaveTextContent("影子评估结果");
    expect(crisisEvidence).toHaveTextContent("2 个可读");
    expect(crisisEvidence).toHaveTextContent("4 个样本不足");
    expect(crisisEvidence).toHaveTextContent("样本 41");
    expect(crisisEvidence).toHaveTextContent("同日相关 0.00");
    expect(crisisEvidence).toHaveTextContent("危机期命中率 55.0%");
    const commodityDecisionPanel = within(crisisEvidence).getByLabelText("候选商品影子评估决策面板");
    expect(commodityDecisionPanel).toHaveTextContent("当前未计入 Crisis Score");
    expect(commodityDecisionPanel).toHaveTextContent("转正前需审批");
    expect(commodityDecisionPanel).toHaveTextContent("可复核 2/6");
    expect(commodityDecisionPanel).toHaveTextContent("样本不足 4");
    const commodityActionQueue = within(commodityDecisionPanel).getByLabelText("商品候选下一动作队列");
    expect(commodityActionQueue).toHaveTextContent("人工复核队列");
    expect(commodityActionQueue).toHaveTextContent("Copper futures / Crude oil futures");
    expect(commodityActionQueue).toHaveTextContent("补历史样本队列");
    expect(commodityActionQueue).toHaveTextContent(
      "Rebar futures / Iron ore futures / Aluminum futures / Gold futures",
    );
    expect(commodityActionQueue).toHaveTextContent("当前未计入 Crisis Score");
    expect(commodityActionQueue).toHaveTextContent("下一步：先补齐样本不足品种，再复核铜、原油的相关性与命中率");
    const commodityReviewConclusion = within(commodityDecisionPanel).getByLabelText("商品候选复核结论");
    expect(commodityReviewConclusion).toHaveTextContent("商品候选准入评估");
    expect(commodityReviewConclusion).toHaveTextContent("建议纳入 0 · 继续观察 2 · 暂不纳入 4");
    expect(commodityReviewConclusion).toHaveTextContent("rv_macro_crisis_commodity_admission_v1");
    expect(commodityReviewConclusion).toHaveTextContent("CANDIDATE_ADMISSION_READ_ONLY");
    expect(commodityReviewConclusion).toHaveTextContent("Copper futures");
    expect(commodityReviewConclusion).toHaveTextContent("继续观察");
    expect(commodityReviewConclusion).toHaveTextContent("相关性偏弱，需人工复核。");
    expect(commodityReviewConclusion).toHaveTextContent("样本 41");
    expect(commodityReviewConclusion).toHaveTextContent("危机样本 11");
    expect(commodityReviewConclusion).toHaveTextContent("命中率 55.0%");
    expect(commodityReviewConclusion).toHaveTextContent("下一步：复核相关性与危机期命中率");
    expect(commodityReviewConclusion).toHaveTextContent("Rebar futures");
    expect(commodityReviewConclusion).toHaveTextContent("暂不纳入");
    expect(commodityReviewConclusion).toHaveTextContent("样本不足，先补齐历史数据。");
    expect(commodityReviewConclusion).toHaveTextContent("样本 17/20");
    expect(commodityReviewConclusion).toHaveTextContent("下一步：先补齐历史样本和危机期样本");
    expect(commodityReviewConclusion).toHaveTextContent("审批前不改变正式 Crisis Score");
    const crisisShadowImpact = within(crisisEvidence).getByLabelText("Crisis Score v2 影子影响评估");
    expect(crisisShadowImpact).toHaveTextContent("Crisis Score v2 影子影响评估");
    expect(crisisShadowImpact).toHaveTextContent("正式 Crisis Score");
    expect(crisisShadowImpact).toHaveTextContent("-0.57");
    expect(crisisShadowImpact).toHaveTextContent("v2 shadow score");
    expect(crisisShadowImpact).toHaveTextContent("-0.53");
    expect(crisisShadowImpact).toHaveTextContent("delta +0.04");
    expect(crisisShadowImpact).toHaveTextContent("rv_macro_crisis_score_shadow_commodity_v1");
    expect(crisisShadowImpact).toHaveTextContent("影响方向");
    expect(crisisShadowImpact).toHaveTextContent("压力上行");
    expect(crisisShadowImpact).toHaveTextContent("候选驱动");
    expect(crisisShadowImpact).toHaveTextContent("2 个待复核");
    expect(crisisShadowImpact).toHaveTextContent("不改变正式 Crisis Score");
    expect(crisisShadowImpact).toHaveTextContent("Copper futures");
    expect(crisisShadowImpact).toHaveTextContent("daily_return_z +0.52");
    expect(crisisShadowImpact).toHaveTextContent("贡献 +0.0260");
    expect(crisisShadowImpact).toHaveTextContent("权重 5.0%");
    expect(crisisShadowImpact).toHaveTextContent("SHADOW_SCORE_READ_ONLY");
    expect(crisisShadowImpact).toHaveTextContent("审批前不改变正式 Crisis Score");
    expect(commodityDecisionPanel).toHaveTextContent("Copper futures");
    expect(commodityDecisionPanel).toHaveTextContent("影子评估可读");
    expect(commodityDecisionPanel).toHaveTextContent("样本 41");
    expect(commodityDecisionPanel).toHaveTextContent("窗口 2026-03-01 -> 2026-04-10");
    expect(commodityDecisionPanel).toHaveTextContent("领先相关 0.00");
    expect(commodityDecisionPanel).toHaveTextContent("滞后相关 0.00");
    expect(commodityDecisionPanel).toHaveTextContent("危机样本 11");
    expect(commodityDecisionPanel).toHaveTextContent("Crude oil futures");
    expect(commodityDecisionPanel).toHaveTextContent("Rebar futures");
    expect(commodityDecisionPanel).toHaveTextContent("影子评估样本不足");
    expect(commodityDecisionPanel).toHaveTextContent("最低样本 20");
    expect(commodityDecisionPanel).toHaveTextContent("还差 3");
    expect(commodityDecisionPanel).toHaveTextContent("进入公式前仍需历史回测、相关性检验、权重审批和版本记录");
    const promotionRulePack = within(crisisEvidence).getByLabelText("候选商品转正规则包");
    expect(promotionRulePack).toHaveTextContent("规则只用于审批前复核，不改变 Crisis Score 公式");
    expect(promotionRulePack).toHaveTextContent("待人工判断 2");
    expect(promotionRulePack).toHaveTextContent("不建议进入公式 4");
    expect(promotionRulePack).toHaveTextContent("准入检查：样本>=20 / 危机样本>=5 / 相关性可读 / 命中率可读");
    expect(promotionRulePack).toHaveTextContent("规则版本 shadow_rule_v1");
    expect(promotionRulePack).toHaveTextContent("样本阈值 >=20 个重叠样本");
    expect(promotionRulePack).toHaveTextContent("危机样本阈值 >=5 个高 Crisis Score 样本");
    expect(promotionRulePack).toHaveTextContent("相关性阈值 |corr|>=0.20 才可直接通过");
    const auditNote = within(promotionRulePack).getByLabelText("shadow_rule_v1 审计注记");
    expect(auditNote).toHaveTextContent("shadow_rule_v1 审计注记");
    expect(auditNote).toHaveTextContent("用途：商品候选进入公式前的影子复核");
    expect(auditNote).toHaveTextContent("边界：不写入 Crisis Score，不改变权重");
    expect(auditNote).toHaveTextContent("审批：历史回测、相关性检验、权重审批、版本记录齐备后再提交");
    const formulaBoundary = within(promotionRulePack).getByLabelText("Crisis Score 商品公式输入边界");
    expect(formulaBoundary).toHaveTextContent("正式输入");
    expect(formulaBoundary).toHaveTextContent("Nanhua commodity index · NH0100.NHF / NHCI.NH");
    expect(formulaBoundary).toHaveTextContent("已纳入 Crisis Score 公式");
    expect(formulaBoundary).toHaveTextContent("影子候选");
    expect(formulaBoundary).toHaveTextContent("Copper futures / Crude oil futures");
    expect(formulaBoundary).toHaveTextContent("当前未计入 Crisis Score");
    expect(promotionRulePack).toHaveTextContent("Copper futures");
    expect(promotionRulePack).toHaveTextContent("待人工判断");
    expect(promotionRulePack).toHaveTextContent("相关性偏弱，需人工复核");
    expect(promotionRulePack).toHaveTextContent("Crude oil futures");
    expect(promotionRulePack).toHaveTextContent("Rebar futures");
    expect(promotionRulePack).toHaveTextContent("不建议进入公式");
    expect(promotionRulePack).toHaveTextContent("样本不足，先补齐历史数据");
    expect(promotionRulePack).toHaveTextContent("Copper futures · 样本检查 通过 41/20");
    expect(promotionRulePack).toHaveTextContent("Copper futures · 危机样本检查 通过 11/5");
    expect(promotionRulePack).toHaveTextContent("Copper futures · 相关性检查 待人工判断 0.00");
    expect(promotionRulePack).toHaveTextContent("Copper futures · 命中率检查 通过 55.0%");
    expect(promotionRulePack).toHaveTextContent("Rebar futures · 样本检查 未通过 17/20");
    expect(promotionRulePack).toHaveTextContent("Rebar futures · 危机样本检查 未通过 缺失/5");
    expect(promotionRulePack).toHaveTextContent("Rebar futures · 相关性检查 未通过 缺失");
    expect(promotionRulePack).toHaveTextContent("Rebar futures · 命中率检查 未通过 缺失");
    expect(crisisEvidence).toHaveTextContent("先补齐样本不足品种的历史数据");
    expect(crisisEvidence).toHaveTextContent("样本不足：Rebar futures 17/20，还差 3");
    expect(crisisEvidence).toHaveTextContent("建议刷新品种：RB / I / AL / AU");
    await user.click(within(crisisEvidence).getByRole("button", { name: "按建议选择" }));
    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    expect(commodityPanel).toHaveTextContent("已按 Crisis Score 建议选择：RB / I / AL / AU");
    expect(commodityPanel).toHaveTextContent("下一步先预估商品期货");
    expect(commodityPanel).toHaveTextContent("4/7");
    expect(within(commodityPanel).getByRole("checkbox", { name: /螺纹钢/ })).toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /^铁矿石/ })).toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /铝/ })).toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /黄金/ })).toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /铜/ })).not.toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /原油/ })).not.toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /南华指数/ })).not.toBeChecked();
    await user.click(within(commodityPanel).getByRole("button", { name: /预估商品期货/ }));
    expect(commodityPanel).toHaveTextContent("商品期货预估完成：4 个品种，88 行");
    expect(crisisEvidence).toHaveTextContent("最低样本 20");
    expect(screen.queryByRole("button", { name: "查看完整分析" })).not.toBeInTheDocument();
  });

  it("copies the commodity promotion rule audit pack from the full evidence panel", async () => {
    const writeText = vi.fn(async (_text: string) => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    const originalWindowClipboard = Object.getOwnPropertyDescriptor(window.navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    Object.defineProperty(window.navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    try {
      renderWorkbenchApp(["/macro-toolkit"]);

      const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
      const promotionRulePack = within(crisisEvidence).getByLabelText("候选商品转正规则包");
      const copyButton = within(promotionRulePack).getByRole("button", { name: "复制审计包" });
      expect(copyButton).toBeEnabled();

      fireEvent.click(copyButton);

      expect(promotionRulePack).not.toHaveTextContent("复制失败");
      await waitFor(() =>
        expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Crisis Score 商品候选审计包")),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("分析日期 2026-04-30"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("source_version macro_toolkit_mock"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("vendor_version choice+tushare"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("rule_version rv_macro_toolkit_ui_v1"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("cache_version none"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("规则版本 shadow_rule_v1"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("用途：商品候选进入公式前的影子复核"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("边界：不写入 Crisis Score，不改变权重"));
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("审批：历史回测、相关性检验、权重审批、版本记录齐备后再提交"),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("人工复核队列 Copper futures / Crude oil futures"));
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("补历史样本队列 Rebar futures / Iron ore futures / Aluminum futures / Gold futures"),
      );
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("处理顺序 下一步：先补齐样本不足品种，再复核铜、原油的相关性与命中率"),
      );
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining(
          "正式商品输入 Nanhua commodity index · NH0100.NHF / NHCI.NH · source choice · latest 2026-04-10 · rows 120 · value 1075.20 · 已纳入 Crisis Score 公式",
        ),
      );
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining(
          "候选来源 Copper futures · CA.COPPER · aliases CU0 / CU0.SHF · matched CU0 · tushare · latest 2026-04-10 · report 2026-04-10 · 同日 · rows 120 · 当前未计入 Crisis Score",
        ),
      );
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining(
          "候选来源 Rebar futures · COMMODITY.RB · aliases RB0 / RB0.SHF · matched RB0 · tushare · latest 2026-04-10 · report 2026-04-10 · 同日 · rows 120 · 当前未计入 Crisis Score",
        ),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Copper futures · 待人工判断 · 相关性偏弱，需人工复核"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Copper futures · 样本检查 通过 41/20"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Copper futures · 相关性检查 待人工判断 0.00"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Rebar futures · 不建议进入公式 · 样本不足，先补齐历史数据"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Rebar futures · 危机样本检查 未通过 缺失/5"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("不建议进入公式 4"));
      await waitFor(() => expect(promotionRulePack).toHaveTextContent("审计包已复制"));
    } finally {
      if (originalClipboard) {
        Object.defineProperty(navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(navigator, "clipboard");
      }
      if (originalWindowClipboard) {
        Object.defineProperty(window.navigator, "clipboard", originalWindowClipboard);
      } else {
        Reflect.deleteProperty(window.navigator, "clipboard");
      }
    }
  });

  it("prefetches full analysis after the core screen without revealing evidence early", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const calls: Array<Parameters<ApiClient["getMacroToolkitAnalysis"]>[0]> = [];
    const sourceBackfillCalls: Array<Parameters<ApiClient["refreshMacroSourceBackfill"]>[0]> = [];
    const coreCrisisCard = {
      key: "crisis_score_cn",
      title: "Crisis Score",
      stance: "完整结果待加载",
      tone: "neutral",
      score: null,
      evidence: ["首屏未运行完整 Crisis Score，打开完整分析后显示分数"],
    } as const;
    const coreSignalCards = [
      coreCrisisCard,
      ...analysisEnvelope.result.signal_cards.filter((card) => card.key !== "crisis_score_cn"),
    ];
    const coreEnvelope = {
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
        signal_cards: coreSignalCards,
      },
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async (options) => {
        calls.push(options);
        return options?.detail === "full" ? analysisEnvelope : coreEnvelope;
      },
      refreshMacroSourceBackfill: async (options) => {
        sourceBackfillCalls.push(options);
        return baseClient.refreshMacroSourceBackfill(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    expect(await screen.findByText("完整结果待加载")).toBeInTheDocument();
    expect(calls.filter((item) => item?.detail === "full")).toHaveLength(0);
    expect(screen.queryByLabelText("Crisis Score 数据来源")).not.toBeInTheDocument();
    expect(screen.queryByText("影子评估结果")).not.toBeInTheDocument();

    await waitFor(() => expect(calls.filter((item) => item?.detail === "full")).toHaveLength(1), {
      timeout: 3_000,
    });
    expect(screen.queryByLabelText("Crisis Score 数据来源")).not.toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: /查看完整分析/ })[0]!);
    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    expect(crisisEvidence).toHaveTextContent("5/5");
    expect(crisisEvidence).toHaveTextContent("Nanhua commodity index");
    expect(crisisEvidence).toHaveTextContent("NH0100.NHF");
    expect(calls.filter((item) => item?.detail === "full")).toHaveLength(1);

    const fullDataHealth = await screen.findByLabelText("数据健康总览");
    await user.click(within(fullDataHealth).getByRole("button", { name: /需要补齐来源数据/ }));
    expect(sourceBackfillCalls).toEqual([
      {
        alias: "M0041813",
        startDate: undefined,
        endDate: "2026-04-30",
        sources: undefined,
      },
    ]);
    await waitFor(() => expect(calls.filter((item) => item?.detail === "full")).toHaveLength(2));
  });

  it("shows the Nanhua business alias when the Crisis Score input uses the system series id", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const envelopeWithSystemNanhuaSeries = {
      ...analysisEnvelope,
      result: {
        ...analysisEnvelope.result,
        capability_results: analysisEnvelope.result.capability_results.map((result) => {
          if (result.key !== "crisis_score_cn") {
            return result;
          }
          const systemInputs = requireInputEvidenceInputs(result).map((input) =>
            input.field === "nanhua"
              ? {
                  ...input,
                  aliases: [],
                  series_id: "NHCI.NH",
                  source: "fact_commodity_futures_daily",
                }
              : input,
          );
          const rawInputEvidence =
            result.result.input_evidence && typeof result.result.input_evidence === "object"
              ? result.result.input_evidence
              : {};
          return {
            ...result,
            input_evidence: result.input_evidence
              ? {
                  ...result.input_evidence,
                  inputs: systemInputs,
                  sources: ["fact_commodity_futures_daily"],
                }
              : result.input_evidence,
            result: {
              ...result.result,
              input_evidence: {
                ...rawInputEvidence,
                inputs: systemInputs,
                sources: ["fact_commodity_futures_daily"],
              },
            },
          };
        }),
      },
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => envelopeWithSystemNanhuaSeries,
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const commodityInputTile = requireClosestElement(
      within(crisisEvidence).getAllByText("商品期货输入")[0]?.closest(".macro-toolkit-metric") ?? null,
      "commodity input tile",
    );
    expect(commodityInputTile).toHaveTextContent("Nanhua commodity index");
    expect(commodityInputTile).toHaveTextContent("NH0100.NHF");
    expect(commodityInputTile).toHaveTextContent("NHCI.NH");
    expect(commodityInputTile.querySelector("small")).toHaveAttribute("title", expect.stringContaining("NH0100.NHF"));
    expect(commodityInputTile.querySelector("small")).toHaveAttribute("title", expect.stringContaining("NHCI.NH"));
  });

  it("uses backend-provided commodity refresh suggestions before field-name fallbacks", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const refreshCalls: Array<Parameters<ApiClient["refreshCommodityFutures"]>[0]> = [];
    const envelopeWithBackendRefreshSuggestions = {
      ...analysisEnvelope,
      result: {
        ...analysisEnvelope.result,
        capability_results: analysisEnvelope.result.capability_results.map((result) => {
          if (result.key !== "crisis_score_cn") {
            return result;
          }
          const rawCommodityCoverage =
            result.result.commodity_coverage && typeof result.result.commodity_coverage === "object"
              ? result.result.commodity_coverage
              : {};
          const rawCandidateSummary =
            "candidate_summary" in rawCommodityCoverage &&
            rawCommodityCoverage.candidate_summary &&
            typeof rawCommodityCoverage.candidate_summary === "object"
              ? rawCommodityCoverage.candidate_summary
              : {};
          return {
            ...result,
            result: {
              ...result.result,
              commodity_coverage: {
                ...rawCommodityCoverage,
                candidate_summary: {
                  ...rawCandidateSummary,
                  suggested_refresh_products: ["CU", "SC"],
                },
              },
            },
          };
        }),
      },
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => envelopeWithBackendRefreshSuggestions,
      refreshCommodityFutures: async (options) => {
        refreshCalls.push(options);
        return baseClient.refreshCommodityFutures(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    expect(crisisEvidence).toHaveTextContent("建议刷新品种：CU / SC");
    expect(crisisEvidence).not.toHaveTextContent("建议刷新品种：RB / I / AL / AU");
    await user.click(within(crisisEvidence).getAllByRole("button", { name: "按建议预估" })[0]!);

    expect(refreshCalls[0]).toEqual({
      startDate: "2026-02-24",
      endDate: "2026-04-30",
      products: ["CU", "SC"],
      dryRun: true,
    });
  });

  it("groups Crisis Score warning and missing inputs into actionable gaps", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const missingWarnings = ["HS300_MISSING", "DR007_MISSING", "NANHUA_MISSING", "AA_5Y_MISSING"];
    const missingFields = new Set(["hs300", "dr007", "nanhua", "aa_5y"]);
    const envelopeWithCrisisGaps = {
      ...analysisEnvelope,
      result: {
        ...analysisEnvelope.result,
        capability_results: analysisEnvelope.result.capability_results.map((result) => {
          if (result.key !== "crisis_score_cn") {
            return result;
          }
          const gapInputs = requireInputEvidenceInputs(result).map((input) =>
            missingFields.has(input.field)
              ? {
                  ...input,
                  available: false,
                  row_count: 0,
                  latest_date: null,
                  source: null,
                  value: null,
                }
              : input,
          );
          const rawInputEvidence =
            result.result.input_evidence && typeof result.result.input_evidence === "object"
              ? result.result.input_evidence
              : {};
          return {
            ...result,
            status: "degraded" as const,
            warnings: missingWarnings,
            input_evidence: result.input_evidence
              ? {
                  ...result.input_evidence,
                  inputs: gapInputs,
                  missing_inputs: missingWarnings,
                }
              : result.input_evidence,
            result: {
              ...result.result,
              input_evidence: {
                ...rawInputEvidence,
                inputs: gapInputs,
                missing_inputs: missingWarnings,
              },
            },
          };
        }),
      },
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => envelopeWithCrisisGaps,
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const gapList = within(crisisEvidence).getByLabelText("Crisis Score 缺口清单");
    expect(gapList).toHaveTextContent("股票风险输入");
    expect(gapList).toHaveTextContent("HS300 close");
    expect(gapList).toHaveTextContent("HS300_MISSING");
    expect(gapList).toHaveTextContent("利率与流动性输入");
    expect(gapList).toHaveTextContent("DR007");
    expect(gapList).toHaveTextContent("DR007_MISSING");
    expect(gapList).toHaveTextContent("商品期货输入");
    expect(gapList).toHaveTextContent("Nanhua commodity index");
    expect(gapList).toHaveTextContent("NANHUA_MISSING");
    expect(gapList).toHaveTextContent("曲线与信用输入");
    expect(gapList).toHaveTextContent("AA credit yield 5Y");
    expect(gapList).toHaveTextContent("AA_5Y_MISSING");
    expect(gapList).toHaveTextContent("缺失不按 0 处理");
  });

  it("offers available refresh actions from the Crisis Score gap list", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const refreshCalls: Array<Parameters<ApiClient["refreshCommodityFutures"]>[0]> = [];
    const sourceBackfillCalls: Array<Parameters<ApiClient["refreshMacroSourceBackfill"]>[0]> = [];
    const missingWarnings = ["NANHUA_MISSING", "NCD_3M_MISSING"];
    const envelopeWithActionableGaps = {
      ...analysisEnvelope,
      result: {
        ...analysisEnvelope.result,
        data_health: {
          ...analysisEnvelope.result.data_health!,
          repair_items: (analysisEnvelope.result.data_health?.repair_items ?? []).map((item) =>
            item.alias === "M0041813"
              ? {
                  ...item,
                  scope: "full",
                  reference_date: "2026-04-30",
                  action: {
                    kind: "source_backfill_required",
                    label: "需要补齐来源数据",
                    enabled: true,
                    reason: "可触发宏观来源补齐；完成后重新运行完整分析确认。",
                    analysis_detail: "full",
                  },
                }
              : item,
          ),
        },
        capability_results: analysisEnvelope.result.capability_results.map((result) => {
          if (result.key !== "crisis_score_cn") {
            return result;
          }
          const baseInputs = requireInputEvidenceInputs(result);
          const gapInputs = [
            ...baseInputs.map((input) =>
              input.field === "nanhua"
                ? {
                    ...input,
                    available: false,
                    row_count: 0,
                    latest_date: null,
                    source: null,
                    value: null,
                }
                : input,
            ),
            {
              field: "ncd_3m",
              label: "3M NCD",
              aliases: ["M0041813"],
              warning: "NCD_3M_MISSING",
              required: true,
              available: false,
              row_count: 0,
              latest_date: null,
              series_id: "NCD.SHIBOR.3M",
              source: null,
              value: null,
            },
          ];
          const rawInputEvidence =
            result.result.input_evidence && typeof result.result.input_evidence === "object"
              ? result.result.input_evidence
              : {};
          return {
            ...result,
            status: "degraded" as const,
            warnings: missingWarnings,
            input_evidence: result.input_evidence
              ? {
                  ...result.input_evidence,
                  inputs: gapInputs,
                  missing_inputs: missingWarnings,
                }
              : result.input_evidence,
            result: {
              ...result.result,
              input_evidence: {
                ...rawInputEvidence,
                inputs: gapInputs,
                missing_inputs: missingWarnings,
              },
            },
          };
        }),
      },
    };
    const envelopeAfterSourceBackfill = {
      ...envelopeWithActionableGaps,
      result: {
        ...envelopeWithActionableGaps.result,
        capability_results: envelopeWithActionableGaps.result.capability_results.map((result) => {
          if (result.key !== "crisis_score_cn") {
            return result;
          }
          const nextMissingWarnings = ["NANHUA_MISSING"];
          const nextInputs = requireInputEvidenceInputs(result).filter((input) => input.field !== "ncd_3m");
          const rawInputEvidence =
            result.result.input_evidence && typeof result.result.input_evidence === "object"
              ? result.result.input_evidence
              : {};
          return {
            ...result,
            warnings: nextMissingWarnings,
            input_evidence: result.input_evidence
              ? {
                  ...result.input_evidence,
                  inputs: nextInputs,
                  missing_inputs: nextMissingWarnings,
                }
              : result.input_evidence,
            result: {
              ...result.result,
              input_evidence: {
                ...rawInputEvidence,
                inputs: nextInputs,
                missing_inputs: nextMissingWarnings,
              },
            },
          };
        }),
      },
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () =>
        sourceBackfillCalls.length ? envelopeAfterSourceBackfill : envelopeWithActionableGaps,
      refreshCommodityFutures: async (options) => {
        refreshCalls.push(options);
        return baseClient.refreshCommodityFutures(options);
      },
      refreshMacroSourceBackfill: async (options) => {
        sourceBackfillCalls.push(options);
        return {
          result_meta: {
            ...analysisEnvelope.result_meta,
            result_kind: "macro_toolkit.source_backfill_refresh",
          },
          result: {
            refresh: {
              status: "completed",
              alias: options.alias,
              series_ids: ["NCD.SHIBOR.3M"],
              total_added: 42,
            },
          },
        };
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const gapList = within(crisisEvidence).getByLabelText("Crisis Score 缺口清单");
    await user.click(within(gapList).getAllByRole("button", { name: "按建议预估" })[0]!);
    expect(refreshCalls[0]).toEqual({
      startDate: "2026-02-24",
      endDate: "2026-04-30",
      products: ["RB", "I", "AL", "AU"],
      dryRun: true,
    });
    await waitFor(() => expect(gapList).toHaveTextContent("商品期货预估完成"));
    expect(gapList).toHaveTextContent("预计可补齐最低样本");

    await user.click(within(gapList).getByRole("button", { name: "需要补齐来源数据" }));
    await waitFor(() =>
      expect(sourceBackfillCalls).toEqual([
        {
          alias: "M0041813",
          startDate: undefined,
          endDate: "2026-04-30",
          sources: undefined,
        },
      ]),
    );
    await waitFor(() => expect(gapList).not.toHaveTextContent("NCD_3M_MISSING"));
    expect(gapList).toHaveTextContent("NANHUA_MISSING");
    const repairFeedback = await screen.findByTestId("crisis-gap-repair-feedback");
    expect(repairFeedback).toHaveTextContent("已补齐，完整分析已重读");
  });

  it("keeps source gap feedback partial when full analysis still reports same-group missing inputs", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const crisisResult = analysisEnvelope.result.capability_results.find((result) => result.key === "crisis_score_cn");
    if (!crisisResult) {
      throw new Error("Missing Crisis Score fixture");
    }
    const sourceBackfillCalls: Array<Parameters<ApiClient["refreshMacroSourceBackfill"]>[0]> = [];
    const ncdInput: MacroToolkitInputEvidenceFixture = {
      field: "ncd_3m",
      label: "3M NCD",
      aliases: ["M0041813"],
      warning: "NCD_3M_MISSING",
      required: true,
      available: false,
      row_count: 0,
      latest_date: null,
      series_id: "NCD.SHIBOR.3M",
      source: null,
      value: null,
    };
    const shiborInput: MacroToolkitInputEvidenceFixture = {
      field: "shibor_1m",
      label: "1M SHIBOR",
      aliases: ["M0041813"],
      warning: "SHIBOR_1M_MISSING",
      required: true,
      available: false,
      row_count: 0,
      latest_date: null,
      series_id: "SHIBOR.1M",
      source: null,
      value: null,
    };
    const initialEnvelope = withCrisisScoreInputEvidence(analysisEnvelope, [
      ...requireInputEvidenceInputs(crisisResult),
      ncdInput,
      shiborInput,
    ], ["NCD_3M_MISSING", "SHIBOR_1M_MISSING"]);
    const partialEnvelope = withCrisisScoreInputEvidence(analysisEnvelope, [
      ...requireInputEvidenceInputs(crisisResult),
      shiborInput,
    ], ["SHIBOR_1M_MISSING"]);
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => (sourceBackfillCalls.length ? partialEnvelope : initialEnvelope),
      refreshMacroSourceBackfill: async (options) => {
        sourceBackfillCalls.push(options);
        return baseClient.refreshMacroSourceBackfill(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const gapList = within(crisisEvidence).getByLabelText("Crisis Score 缺口清单");
    await user.click(within(gapList).getByRole("button", { name: "需要补齐来源数据" }));

    const repairFeedback = await screen.findByTestId("crisis-gap-repair-feedback");
    expect(repairFeedback).toHaveTextContent("完整分析已重读，仍有缺口");
    expect(repairFeedback).toHaveTextContent("SHIBOR_1M_MISSING");
    await waitFor(() => expect(gapList).not.toHaveTextContent("NCD_3M_MISSING"));
    expect(gapList).toHaveTextContent("SHIBOR_1M_MISSING");
  });

  it("keeps source gap failure feedback inside the Crisis Score gap list", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const crisisResult = analysisEnvelope.result.capability_results.find((result) => result.key === "crisis_score_cn");
    if (!crisisResult) {
      throw new Error("Missing Crisis Score fixture");
    }
    const ncdInput: MacroToolkitInputEvidenceFixture = {
      field: "ncd_3m",
      label: "3M NCD",
      aliases: ["M0041813"],
      warning: "NCD_3M_MISSING",
      required: true,
      available: false,
      row_count: 0,
      latest_date: null,
      series_id: "NCD.SHIBOR.3M",
      source: null,
      value: null,
    };
    const envelopeWithSourceGap = withCrisisScoreInputEvidence(analysisEnvelope, [
      ...requireInputEvidenceInputs(crisisResult),
      ncdInput,
    ], ["NCD_3M_MISSING"]);
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => envelopeWithSourceGap,
      refreshMacroSourceBackfill: async () => {
        throw new Error("source backfill unavailable");
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const gapList = within(crisisEvidence).getByLabelText("Crisis Score 缺口清单");
    await user.click(within(gapList).getByRole("button", { name: "需要补齐来源数据" }));

    const repairFeedback = await screen.findByTestId("crisis-gap-repair-feedback");
    expect(repairFeedback).toHaveTextContent("补齐失败，缺口仍需处理");
    expect(repairFeedback).toHaveTextContent("source backfill unavailable");
    expect(gapList).toHaveTextContent("NCD_3M_MISSING");
  });

  it("labels commodity preview failures as estimates in the Crisis Score gap list", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
      refreshCommodityFutures: async () => {
        throw new Error("commodity preview unavailable");
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const gapList = within(crisisEvidence).getByLabelText("Crisis Score 缺口清单");
    await user.click(within(gapList).getAllByRole("button", { name: "按建议预估" })[0]!);

    const repairFeedback = await screen.findByTestId("crisis-gap-repair-feedback");
    expect(repairFeedback).toHaveTextContent("预估失败，缺口仍需处理");
    expect(repairFeedback).toHaveTextContent("commodity preview unavailable");
  });

  it("previews Crisis Score suggested commodity futures from the evidence panel", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const refreshCalls: Array<Parameters<ApiClient["refreshCommodityFutures"]>[0]> = [];
    let completedRefreshCount = 0;
    const refreshedAnalysisEnvelope = {
      ...analysisEnvelope,
      result: {
        ...analysisEnvelope.result,
        capability_results: analysisEnvelope.result.capability_results.map((result) => {
          if (result.key !== "crisis_score_cn") {
            return result;
          }
          const updatedInputs = requireInputEvidenceInputs(result).map((input) =>
            input.field === "nanhua"
              ? {
                  ...input,
                  row_count: 22,
                  latest_date: "2026-06-01",
                  source: "tushare",
                  value: 3187.42,
                }
              : input,
          );
          const rawInputEvidence =
            result.result.input_evidence && typeof result.result.input_evidence === "object"
              ? result.result.input_evidence
              : {};
          const rawCommodityCoverage =
            result.result.commodity_coverage && typeof result.result.commodity_coverage === "object"
              ? result.result.commodity_coverage
              : {};
          const rawCandidateSummary =
            "candidate_summary" in rawCommodityCoverage &&
            rawCommodityCoverage.candidate_summary &&
            typeof rawCommodityCoverage.candidate_summary === "object"
              ? rawCommodityCoverage.candidate_summary
              : {};
          return {
            ...result,
            input_evidence: result.input_evidence
              ? {
                  ...result.input_evidence,
                  inputs: updatedInputs,
                  latest_dates: ["2026-06-01"],
                  sources: ["tushare"],
                }
              : result.input_evidence,
            result: {
              ...result.result,
              input_evidence: {
                ...rawInputEvidence,
                inputs: updatedInputs,
                latest_dates: ["2026-06-01"],
                sources: ["tushare"],
              },
              commodity_coverage: {
                ...rawCommodityCoverage,
                candidate_summary: {
                  ...rawCandidateSummary,
                  shadow_evaluation_short_count: 0,
                  shadow_evaluation_ready_count: 6,
                  shadow_evaluation_short_items: [],
                  shadow_evaluation_status_counts: { review_ready: 6 },
                  shadow_evaluation_next_step: "样本已补齐；进入人工复核和权重审批。",
                },
              },
            },
          };
        }),
      },
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async (options) => {
        if (options?.detail === "full" && completedRefreshCount > 0) {
          return refreshedAnalysisEnvelope;
        }
        return analysisEnvelope;
      },
      refreshCommodityFutures: async (options) => {
        refreshCalls.push(options);
        if (!options?.dryRun) {
          completedRefreshCount += 1;
        }
        return baseClient.refreshCommodityFutures(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    expect(crisisEvidence).toHaveTextContent("建议刷新品种：RB / I / AL / AU");

    await user.click(within(crisisEvidence).getAllByRole("button", { name: "按建议预估" })[0]!);

    expect(refreshCalls).toHaveLength(1);
    expect(refreshCalls[0]).toEqual({
      startDate: "2026-02-24",
      endDate: "2026-04-30",
      products: ["RB", "I", "AL", "AU"],
      dryRun: true,
    });
    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    expect(commodityPanel).toHaveTextContent("已按 Crisis Score 建议选择：RB / I / AL / AU");
    expect(commodityPanel).toHaveTextContent("商品期货预估完成：4 个品种，88 行");
    expect(commodityPanel).toHaveTextContent("Crisis Score 样本预估");
    expect(commodityPanel).toHaveTextContent("预计可补齐最低样本");
    expect(commodityPanel).toHaveTextContent("建议刷新商品期货");
    expect(commodityPanel).toHaveTextContent("Rebar futures 17/20，预计 +22，可补齐至 20/20");
    expect(commodityPanel).toHaveTextContent("Iron ore futures 17/20，预计 +22，可补齐至 20/20");
    expect(commodityPanel).toHaveTextContent("Aluminum futures 17/20，预计 +22，可补齐至 20/20");
    expect(commodityPanel).toHaveTextContent("Gold futures 17/20，预计 +22，可补齐至 20/20");
    expect(
      within(commodityPanel).getByRole("button", { name: "刷新商品期货：刷新并重算证据" }),
    ).toBeEnabled();
    const gapList = within(crisisEvidence).getByLabelText("Crisis Score 缺口清单");
    const gapRefreshButton = within(gapList).getByRole("button", { name: "按建议刷新并重读" });
    expect(gapRefreshButton).toBeEnabled();
    expect(within(commodityPanel).getByRole("checkbox", { name: /螺纹钢/ })).toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /^铁矿石/ })).toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /铝/ })).toBeChecked();
    expect(within(commodityPanel).getByRole("checkbox", { name: /黄金/ })).toBeChecked();

    await user.click(gapRefreshButton);

    expect(refreshCalls[1]).toEqual({
      startDate: "2026-02-24",
      endDate: "2026-04-30",
      products: ["RB", "I", "AL", "AU"],
      dryRun: false,
    });
    expect(commodityPanel).toHaveTextContent("商品期货刷新完成：4 个品种，88 行");
    expect(commodityPanel).toHaveTextContent("完整分析证据已重新读取");
    expect(commodityPanel).toHaveTextContent("Crisis Score 样本缺口变化");
    expect(commodityPanel).toHaveTextContent("Rebar futures 17/20 -> 20/20");
    expect(commodityPanel).toHaveTextContent("Iron ore futures 17/20 -> 20/20");
    expect(commodityPanel).toHaveTextContent("Aluminum futures 17/20 -> 20/20");
    expect(commodityPanel).toHaveTextContent("Gold futures 17/20 -> 20/20");
    const reloadedCrisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    await waitFor(() => expect(reloadedCrisisEvidence).toHaveTextContent("2026-06-01"));
    expect(reloadedCrisisEvidence).toHaveTextContent("3187.42");
    const closurePanel = within(reloadedCrisisEvidence).getByLabelText("Crisis Score 样本刷新闭环");
    expect(closurePanel).toHaveTextContent("建议品种 RB / I / AL / AU");
    expect(closurePanel).toHaveTextContent("实际刷新 RB / I / AL / AU");
    expect(closurePanel).toHaveTextContent("完整分析已重读");
    expect(closurePanel).toHaveTextContent("已补齐 4/4");
    expect(closurePanel).toHaveTextContent("Rebar futures");
    expect(closurePanel).toHaveTextContent("刷新前 17/20");
    expect(closurePanel).toHaveTextContent("刷新后 20/20");
    expect(closurePanel).toHaveTextContent("剩余缺口 0");
  });

  it("shows remaining Crisis Score sample gaps when the commodity preview is still short", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
      refreshCommodityFutures: async (options) => {
        const response = await baseClient.refreshCommodityFutures(options);
        if (!options?.dryRun) {
          return response;
        }
        return {
          ...response,
          result: {
            ...response.result,
            refresh: {
              ...response.result.refresh,
              estimated_total_rows: 4,
              estimated_trading_days: 1,
              products: response.result.refresh.products?.map((product) => ({
                ...product,
                estimated_rows: 1,
              })),
            },
          },
        };
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const gapSummaryTile = requireClosestElement(
      within(crisisEvidence).getByText("缺口提示").closest(".macro-toolkit-metric"),
      "gap summary tile",
    );
    expect(gapSummaryTile).toHaveTextContent("4");
    expect(gapSummaryTile.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("COMMODITY_SAMPLE_SHORT"),
    );
    const gapList = within(crisisEvidence).getByLabelText("Crisis Score 缺口清单");
    expect(gapList).toHaveTextContent("COMMODITY_SAMPLE_SHORT");
    await user.click(within(crisisEvidence).getAllByRole("button", { name: "按建议预估" })[0]!);

    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    expect(commodityPanel).toHaveTextContent("商品期货预估完成：4 个品种，4 行");
    expect(commodityPanel).toHaveTextContent("Crisis Score 样本预估");
    expect(commodityPanel).toHaveTextContent("预计仍有样本缺口");
    expect(commodityPanel).toHaveTextContent("刷新后仍不会闭环");
    expect(gapList).not.toHaveTextContent("按建议刷新并重读");
    expect(commodityPanel).toHaveTextContent("Rebar futures 17/20，预计 +1，预计到 18/20，还差 2");
    expect(commodityPanel).toHaveTextContent("Iron ore futures 17/20，预计 +1，预计到 18/20，还差 2");
    expect(
      within(commodityPanel).getByRole("button", { name: "刷新商品期货：仍有缺口，谨慎刷新" }),
    ).toBeEnabled();
  });

  it("keeps a partial Crisis Score sample closure after commodity refresh reloads full evidence", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const refreshCalls: Array<Parameters<ApiClient["refreshCommodityFutures"]>[0]> = [];
    let completedRefreshCount = 0;
    const partiallyRefreshedEnvelope = {
      ...analysisEnvelope,
      result: {
        ...analysisEnvelope.result,
        capability_results: analysisEnvelope.result.capability_results.map((result) => {
          if (result.key !== "crisis_score_cn") {
            return result;
          }
          const rawCommodityCoverage =
            result.result.commodity_coverage && typeof result.result.commodity_coverage === "object"
              ? result.result.commodity_coverage
              : {};
          const rawCandidateSummary =
            "candidate_summary" in rawCommodityCoverage &&
            rawCommodityCoverage.candidate_summary &&
            typeof rawCommodityCoverage.candidate_summary === "object"
              ? rawCommodityCoverage.candidate_summary
              : {};
          return {
            ...result,
            result: {
              ...result.result,
              commodity_coverage: {
                ...rawCommodityCoverage,
                candidate_summary: {
                  ...rawCandidateSummary,
                  shadow_evaluation_short_count: 2,
                  shadow_evaluation_ready_count: 4,
                  shadow_evaluation_short_items: [
                    {
                      field: "rebar",
                      label: "Rebar futures",
                      sample_count: 19,
                      minimum_sample_count: 20,
                      sample_gap: 1,
                      latest_date: "2026-04-30",
                    },
                    {
                      field: "iron_ore",
                      label: "Iron ore futures",
                      sample_count: 19,
                      minimum_sample_count: 20,
                      sample_gap: 1,
                      latest_date: "2026-04-30",
                    },
                  ],
                },
              },
            },
          };
        }),
      },
    };
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async (options) => {
        if (options?.detail === "full" && completedRefreshCount > 0) {
          return partiallyRefreshedEnvelope;
        }
        return analysisEnvelope;
      },
      refreshCommodityFutures: async (options) => {
        refreshCalls.push(options);
        if (!options?.dryRun) {
          completedRefreshCount += 1;
        }
        return baseClient.refreshCommodityFutures(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const gapList = within(crisisEvidence).getByLabelText("Crisis Score 缺口清单");
    await user.click(within(gapList).getAllByRole("button", { name: "按建议预估" })[0]!);
    await user.click(within(gapList).getByRole("button", { name: "按建议刷新并重读" }));

    expect(refreshCalls[1]).toEqual({
      startDate: "2026-02-24",
      endDate: "2026-04-30",
      products: ["RB", "I", "AL", "AU"],
      dryRun: false,
    });
    const reloadedCrisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    const closurePanel = await within(reloadedCrisisEvidence).findByLabelText("Crisis Score 样本刷新闭环");
    expect(closurePanel).toHaveTextContent("建议品种 RB / I / AL / AU");
    expect(closurePanel).toHaveTextContent("实际刷新 RB / I / AL / AU");
    expect(closurePanel).toHaveTextContent("完整分析已重读");
    expect(closurePanel).toHaveTextContent("已补齐 2/4");
    expect(closurePanel).toHaveTextContent("Rebar futures");
    expect(closurePanel).toHaveTextContent("刷新前 17/20");
    expect(closurePanel).toHaveTextContent("刷新后 19/20");
    expect(closurePanel).toHaveTextContent("剩余缺口 1");
    expect(reloadedCrisisEvidence).toHaveTextContent("完整分析已重读，仍有缺口");
    expect(reloadedCrisisEvidence).toHaveTextContent("COMMODITY_SAMPLE_SHORT");
  });

  it("previews selected commodity futures before refreshing full evidence", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const calls: Array<Parameters<ApiClient["getMacroToolkitAnalysis"]>[0]> = [];
    const refreshCalls: Array<Parameters<ApiClient["refreshCommodityFutures"]>[0]> = [];
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async (options) => {
        calls.push(options);
        return analysisEnvelope;
      },
      refreshCommodityFutures: async (options) => {
        refreshCalls.push(options);
        const products = options?.products ?? ["RB", "I", "CU", "AL", "SC", "AU", "NHCI"];
        const isDryRun = options?.dryRun ?? false;
        const productNames: Record<string, string> = {
          CU: "铜",
          SC: "原油",
          AU: "黄金",
          NHCI: "南华指数",
        };
        return {
          result_meta: {
            ...analysisEnvelope.result_meta,
            result_kind: "macro_toolkit.commodity_futures_refresh",
          },
          result: {
            refresh: {
              status: isDryRun ? "dry_run" : "completed",
              dry_run: isDryRun,
              start_date: "2026-04-01",
              end_date: "2026-04-30",
              product_count: products.length,
              row_count: isDryRun ? 0 : products.length * 22,
              estimated_total_rows: isDryRun ? products.length * 22 : undefined,
              estimated_trading_days: isDryRun ? 22 : undefined,
              before_status: isDryRun
                ? undefined
                : {
                    materialized: true,
                    status: "ok",
                    table: "fact_commodity_futures_daily",
                    row_count: 120,
                    latest_trade_date: "2026-05-20",
                    source_vendors: ["tushare"],
                    coverage: {
                      target_product_count: 7,
                      available_product_count: 5,
                      available_products: ["CU", "AL", "SC", "AU", "NHCI"],
                      missing_products: ["RB", "I"],
                    },
                    nanhua_input: {
                      status: "hit",
                      product_code: "NHCI",
                      series_id: "NH0100.NHF",
                      system_series_id: "NHCI.NH",
                      latest_trade_date: "2026-05-20",
                      latest_value: 3007.05,
                      row_count: 18,
                      source_version: "sv_tushare_index_daily_nhci_old",
                      vendor_version: "vv_tushare_index_daily_NHCI_20260520",
                      rule_version: "rv_commodity_daily_v1",
                    },
                  },
              after_status: isDryRun
                ? undefined
                : {
                    materialized: true,
                    status: "ok",
                    table: "fact_commodity_futures_daily",
                    row_count: 154,
                    latest_trade_date: "2026-06-01",
                    source_vendors: ["tushare"],
                    coverage: {
                      target_product_count: 7,
                      available_product_count: 7,
                      available_products: ["RB", "I", "CU", "AL", "SC", "AU", "NHCI"],
                      missing_products: [],
                    },
                    nanhua_input: {
                      status: "hit",
                      product_code: "NHCI",
                      series_id: "NH0100.NHF",
                      system_series_id: "NHCI.NH",
                      latest_trade_date: "2026-06-01",
                      latest_value: 3187.42,
                      row_count: 22,
                      source_version: "sv_tushare_index_daily_nhci_new",
                      vendor_version: "vv_tushare_index_daily_NHCI_20260601",
                      rule_version: "rv_commodity_daily_v1",
                    },
                  },
              summary: isDryRun
                ? {
                    table: "fact_commodity_futures_daily",
                    row_count_before: 120,
                    row_count_after: 120,
                    row_count_delta: 0,
                    latest_trade_date_before: "2026-05-20",
                    latest_trade_date_after: "2026-05-20",
                    available_product_count_before: 5,
                    available_product_count_after: 5,
                    target_product_count: 7,
                    newly_available_products: [],
                    missing_products_after: ["RB", "I"],
                    nanhua_status_before: "hit",
                    nanhua_status_after: "hit",
                    nanhua_latest_date_before: "2026-05-20",
                    nanhua_latest_date_after: "2026-05-20",
                    nanhua_latest_value_after: 3007.05,
                    source_vendors_after: ["tushare"],
                    dry_run: true,
                  }
                : {
                    table: "fact_commodity_futures_daily",
                    row_count_before: 120,
                    row_count_after: 154,
                    row_count_delta: 34,
                    latest_trade_date_before: "2026-05-20",
                    latest_trade_date_after: "2026-06-01",
                    available_product_count_before: 5,
                    available_product_count_after: 7,
                    target_product_count: 7,
                    newly_available_products: ["RB", "I"],
                    missing_products_after: [],
                    nanhua_status_before: "hit",
                    nanhua_status_after: "hit",
                    nanhua_latest_date_before: "2026-05-20",
                    nanhua_latest_date_after: "2026-06-01",
                    nanhua_latest_value_after: 3187.42,
                    source_vendors_after: ["tushare"],
                    dry_run: false,
                  },
              products: products.map((product) => {
                const productCode = product === "NHCI" ? "NH0100.NHF" : product;
                return {
                  product_code: productCode,
                  name_zh: productNames[product] ?? product,
                  row_count: isDryRun ? undefined : 22,
                  estimated_rows: isDryRun ? 22 : undefined,
                  latest_date: isDryRun ? undefined : "2026-04-30",
                  latest_value: product === "NHCI" && !isDryRun ? 3187.42 : undefined,
                  series_id:
                    product === "NHCI"
                      ? "NH0100.NHF"
                      : product === "CU"
                        ? "CA.COPPER"
                        : product === "AL"
                          ? "CA.ALUMINUM"
                          : `COMMODITY.${product}`,
                  vendor: isDryRun ? "estimate_only" : "tushare",
                };
              }),
              table: "fact_commodity_futures_daily",
              rule_version: "rv_commodity_daily_v1",
            },
          },
        };
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    const permissionTile = await waitFor(() => {
      const tile = within(commodityPanel).getByText("商品权限").closest(".macro-toolkit-metric");
      expect(tile).toHaveTextContent("已授权");
      return tile;
    });
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("resource macro_toolkit.commodity_futures"),
    );
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("actions dry_run / refresh"),
    );
    expect(within(commodityPanel).getByRole("button", { name: /预估商品期货/ })).toBeEnabled();
    expect(within(commodityPanel).getByRole("button", { name: /刷新商品期货/ })).toBeEnabled();
    expect(within(commodityPanel).getByRole("checkbox", { name: /南华指数/ })).toBeChecked();
    await user.click(within(commodityPanel).getByRole("checkbox", { name: /螺纹钢/ }));
    await user.click(within(commodityPanel).getByRole("checkbox", { name: /^铁矿石/ }));
    await user.click(within(commodityPanel).getByRole("checkbox", { name: /铝/ }));

    await user.click(within(commodityPanel).getByRole("button", { name: /预估商品期货/ }));

    expect(refreshCalls[0]).toEqual({
      endDate: "2026-04-30",
      products: ["CU", "SC", "AU", "NHCI"],
      dryRun: true,
    });
    const dryRunSummaries = await screen.findAllByText(/商品期货预估完成/);
    expect(dryRunSummaries[0]).toHaveTextContent("4 个品种，88 行");
    expect(dryRunSummaries[0]).toHaveTextContent("22 个交易日");
    const dryRunResult = await screen.findByLabelText("商品期货刷新结果");
    expect(dryRunResult).toHaveTextContent("预计可写");
    expect(dryRunResult).toHaveTextContent("预估基线");
    expect(dryRunResult).toHaveTextContent("120 → 120");
    expect(dryRunResult).toHaveTextContent("+0");
    expect(dryRunResult).toHaveTextContent("覆盖 5/7 → 5/7");
    expect(dryRunResult).toHaveTextContent("缺失 RB / I");
    expect(dryRunResult).toHaveTextContent("南华 2026-05-20 → 2026-05-20");
    expect(dryRunResult).toHaveTextContent("estimate_only");
    expect(dryRunResult).toHaveTextContent("CU / CA.COPPER");
    expect(dryRunResult).toHaveTextContent("NHCI / NH0100.NHF");
    expect(dryRunResult).toHaveTextContent("fact_commodity_futures_daily");
    expect(calls.filter((item) => item?.detail === "full")).toHaveLength(0);
    expect(screen.queryByTestId("crisis-gap-repair-feedback")).not.toBeInTheDocument();

    await user.click(within(commodityPanel).getByRole("button", { name: /刷新商品期货/ }));

    expect(refreshCalls[1]).toEqual({
      endDate: "2026-04-30",
      products: ["CU", "SC", "AU", "NHCI"],
      dryRun: false,
    });
    const refreshSummaries = await screen.findAllByText(/商品期货刷新完成/);
    expect(refreshSummaries[0]).toHaveTextContent("4 个品种，88 行");
    const completedResult = await screen.findByLabelText("商品期货刷新结果");
    expect(completedResult).toHaveTextContent("Crisis Score 南华输入已更新");
    expect(completedResult).toHaveTextContent("刷新后闭环");
    expect(completedResult).toHaveTextContent("120 → 154");
    expect(completedResult).toHaveTextContent("+34");
    expect(completedResult).toHaveTextContent("2026-05-20 → 2026-06-01");
    expect(completedResult).toHaveTextContent("5/7 → 7/7");
    expect(completedResult).toHaveTextContent("新增 RB / I");
    expect(completedResult).toHaveTextContent("缺失 无");
    expect(completedResult).toHaveTextContent("tushare");
    expect(completedResult).toHaveTextContent("已写入");
    expect(completedResult).toHaveTextContent("2026-04-30");
    expect(completedResult).toHaveTextContent("3187.42");
    await waitFor(() => expect(calls).toContainEqual({ detail: "full" }));
    const repairFeedback = screen.queryByTestId("crisis-gap-repair-feedback");
    if (repairFeedback) {
      expect(repairFeedback).not.toHaveTextContent("正在刷新并重读完整分析");
    }
    const crisisEvidence = await screen.findByLabelText("Crisis Score 数据来源");
    expect(crisisEvidence).toHaveTextContent("Nanhua commodity index");
    expect(crisisEvidence).toHaveTextContent("NH0100.NHF");
  });

  it("keeps commodity futures permission fallback tied to the commodity resource", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const scriptsEnvelope = await baseClient.getMacroToolkitScripts();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
      getMacroToolkitScripts: async () => ({
        ...scriptsEnvelope,
        result: {
          ...scriptsEnvelope.result,
          commodity_futures_refresh: undefined,
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    const permissionTile = within(commodityPanel).getByText("商品权限").closest(".macro-toolkit-metric");
    expect(permissionTile).toHaveTextContent("待确认");
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("resource macro_toolkit.commodity_futures"),
    );
  });

  it("shows commodity futures data health before a refresh is clicked", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const scriptsEnvelope = await baseClient.getMacroToolkitScripts();
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
      getMacroToolkitScripts: async () => ({
        ...scriptsEnvelope,
        result: {
          ...scriptsEnvelope.result,
          commodity_futures_refresh: {
            ...scriptsEnvelope.result.commodity_futures_refresh!,
            status: {
              materialized: true,
              status: "ok",
              table: "fact_commodity_futures_daily",
              row_count: 154,
              latest_trade_date: "2026-04-30",
              source_vendors: ["tushare"],
              coverage: {
                target_product_count: 7,
                available_product_count: 5,
                available_products: ["CU", "AL", "SC", "AU", "NHCI"],
                missing_products: ["RB", "I"],
              },
              nanhua_input: {
                status: "hit",
                product_code: "NHCI",
                series_id: "NH0100.NHF",
                system_series_id: "NHCI.NH",
                latest_trade_date: "2026-04-30",
                latest_value: 3187.42,
                row_count: 22,
                source_version: "sv_tushare_index_daily_nhci",
                vendor_version: "vv_tushare_index_daily_NHCI_20260430",
                rule_version: "rv_commodity_daily_v1",
              },
            },
          },
        },
      }),
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    await waitFor(() => expect(within(commodityPanel).getByText("南华输入")).toBeInTheDocument());
    const nanhuaTile = within(commodityPanel).getByText("南华输入").closest(".macro-toolkit-metric");
    expect(nanhuaTile?.querySelector("small")).toHaveAttribute("title", expect.stringContaining("NH0100.NHF"));
    expect(commodityPanel).toHaveTextContent("NH0100.NHF");
    expect(commodityPanel).toHaveTextContent("2026-04-30");
    expect(commodityPanel).toHaveTextContent("3187.42");
    expect(commodityPanel).toHaveTextContent("覆盖品种");
    expect(commodityPanel).toHaveTextContent("5/7");
    expect(commodityPanel).toHaveTextContent("数据来源");
    expect(commodityPanel).toHaveTextContent("tushare");
  });

  it("shows commodity futures refresh permission and blocks unauthorized actions", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const scriptsEnvelope = await baseClient.getMacroToolkitScripts();
    const refreshCalls: Array<Parameters<ApiClient["refreshCommodityFutures"]>[0]> = [];
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
      getMacroToolkitScripts: async () => ({
        ...scriptsEnvelope,
        result: {
          ...scriptsEnvelope.result,
          commodity_futures_refresh: {
            permission: {
              mode: "scoped_refresh",
              allowed: false,
              user_id: "commodity-user",
              role: "viewer",
              identity_source: "header",
              resource: "macro_toolkit.commodity_futures",
              actions: ["dry_run", "refresh"],
            },
          },
        },
      }),
      refreshCommodityFutures: async (options) => {
        refreshCalls.push(options);
        return baseClient.refreshCommodityFutures(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    const permissionTile = await waitFor(() => {
      const tile = within(commodityPanel).getByText("商品权限").closest(".macro-toolkit-metric");
      expect(tile).toHaveTextContent("未授权");
      return tile;
    });
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("resource macro_toolkit.commodity_futures"),
    );
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("actions dry_run / refresh"),
    );
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("user commodity-user"),
    );
    expect(commodityPanel).toHaveTextContent("缺少商品期货刷新授权");
    expect(commodityPanel).toHaveTextContent("macro_toolkit.commodity_futures");
    expect(commodityPanel).toHaveTextContent("dry_run / refresh");
    expect(commodityPanel).toHaveTextContent("commodity-user");
    expect(commodityPanel).toHaveTextContent("viewer");

    const dryRunButton = within(commodityPanel).getByRole("button", { name: /预估商品期货/ });
    const refreshButton = within(commodityPanel).getByRole("button", { name: /刷新商品期货/ });
    expect(dryRunButton).toBeDisabled();
    expect(refreshButton).toBeDisabled();
    await user.click(dryRunButton);
    expect(refreshCalls).toHaveLength(0);
  });

  it("shows pending commodity futures permission before scoped refresh is confirmed", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const scriptsEnvelope = await baseClient.getMacroToolkitScripts();
    const refreshCalls: Array<Parameters<ApiClient["refreshCommodityFutures"]>[0]> = [];
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
      getMacroToolkitScripts: async () => ({
        ...scriptsEnvelope,
        result: {
          ...scriptsEnvelope.result,
          commodity_futures_refresh: {
            ...scriptsEnvelope.result.commodity_futures_refresh!,
            permission: {
              mode: "scoped_refresh",
              user_id: "anonymous",
              role: "viewer",
              identity_source: "fallback",
              resource: "macro_toolkit.commodity_futures",
              actions: ["dry_run", "refresh"],
            },
          },
        },
      }),
      refreshCommodityFutures: async (options) => {
        refreshCalls.push(options);
        return baseClient.refreshCommodityFutures(options);
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    const permissionTile = await waitFor(() => {
      const tile = within(commodityPanel).getByText("商品权限").closest(".macro-toolkit-metric");
      expect(tile).toHaveTextContent("待确认");
      return tile;
    });
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("resource macro_toolkit.commodity_futures"),
    );
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("actions dry_run / refresh"),
    );
    expect(permissionTile?.querySelector("small")).toHaveAttribute(
      "title",
      expect.stringContaining("user anonymous"),
    );
    expect(commodityPanel).toHaveTextContent("商品期货刷新授权待确认");
    expect(commodityPanel).toHaveTextContent("macro_toolkit.commodity_futures");
    expect(commodityPanel).toHaveTextContent("dry_run / refresh");
    expect(commodityPanel).toHaveTextContent("action refresh");
    expect(commodityPanel).toHaveTextContent("scope store");
    expect(commodityPanel).toHaveTextContent("anonymous");
    expect(commodityPanel).toHaveTextContent("viewer");

    const dryRunButton = within(commodityPanel).getByRole("button", { name: /预估商品期货/ });
    const refreshButton = within(commodityPanel).getByRole("button", { name: /刷新商品期货/ });
    expect(dryRunButton).toBeDisabled();
    expect(refreshButton).toBeDisabled();
    await user.click(dryRunButton);
    expect(refreshCalls).toHaveLength(0);
  });

  it("shows a readable commodity futures permission error when the backend rejects refresh", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis({ detail: "full" });
    const refreshCalls: Array<Parameters<ApiClient["refreshCommodityFutures"]>[0]> = [];
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => analysisEnvelope,
      refreshCommodityFutures: async (options) => {
        refreshCalls.push(options);
        throw new Error("User is not allowed to refresh macro_toolkit.commodity_futures.");
      },
    } as ApiClient;
    const user = userEvent.setup();

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const commodityPanel = await screen.findByLabelText("商品期货刷新");
    await user.click(within(commodityPanel).getByRole("button", { name: /预估商品期货/ }));

    expect(refreshCalls).toHaveLength(1);
    expect(
      (await within(commodityPanel).findAllByText(/当前账号没有商品期货刷新权限/, {}, { timeout: 5_000 })).length,
    ).toBeGreaterThan(0);
    expect(
      (await within(commodityPanel).findAllByText(/macro_toolkit\.commodity_futures:refresh/, {}, { timeout: 5_000 }))
        .length,
    ).toBeGreaterThan(0);
  });

  it("does not trigger source backfill for unsupported aliases even when action is enabled", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const analysisEnvelope = await baseClient.getMacroToolkitAnalysis();
    const sourceBackfillCalls: Array<Parameters<ApiClient["refreshMacroSourceBackfill"]>[0]> = [];
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => ({
        ...analysisEnvelope,
        result: {
          ...analysisEnvelope.result,
          data_health: {
            ...analysisEnvelope.result.data_health!,
            repair_items: [
              {
                type: "stale",
                scope: "full",
                priority: "medium",
                key: "source:CU0",
                alias: "CU0",
                label: "CU0",
                reference_date: "2026-04-30",
                suggested_action: "Refresh CU0 after source update.",
                action: {
                  kind: "source_backfill_required",
                  label: "Refresh CU0 source",
                  enabled: true,
                  reason: "Backend should not enable unsupported aliases.",
                  analysis_detail: "full",
                },
                tags: ["source"],
              },
            ],
          },
        },
      }),
      refreshMacroSourceBackfill: async (options) => {
        sourceBackfillCalls.push(options);
        throw new Error("Unsupported alias should not refresh");
      },
    } as ApiClient;

    renderWorkbenchApp(["/macro-toolkit"], { client });

    const dataHealth = await screen.findByLabelText("数据健康总览");
    expect(dataHealth).toHaveTextContent("CU0");
    expect(dataHealth).toHaveTextContent("Backend should not enable unsupported aliases.");
    expect(within(dataHealth).queryByRole("button", { name: "Refresh CU0 source" })).not.toBeInTheDocument();
    expect(sourceBackfillCalls).toEqual([]);
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

  it("surfaces a copyable macro toolkit read-scope request when reads are forbidden", async () => {
    const writeText = vi.fn(async (_text: string) => undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(window.navigator, "clipboard");
    Object.defineProperty(window.navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => {
        throw new Error("User is not allowed to read macro_toolkit.");
      },
      getMacroToolkitScripts: async () => {
        throw new Error("User is not allowed to read macro_toolkit.");
      },
      getMacroToolkitStrategySummaries: async () => {
        throw new Error("User is not allowed to read macro_toolkit.");
      },
    } as ApiClient;

    try {
      renderWorkbenchApp(["/macro-toolkit"], { client });

      const errorState = await screen.findByTestId("macro-toolkit-error-state");
      expect(errorState).toHaveTextContent("缺少宏观工具读取权限");
      expect(errorState).toHaveTextContent("macro_toolkit/read");
      expect(errorState).toHaveTextContent("授权后点击重试读取");
      const permissionPanel = within(errorState).getByLabelText("宏观工具读取权限缺口");
      fireEvent.click(within(permissionPanel).getByRole("button", { name: "复制授权申请" }));

      await waitFor(() =>
        expect(writeText).toHaveBeenCalledWith(expect.stringContaining("申请授予 macro_toolkit/read")),
      );
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("resource=macro_toolkit"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("action=read"));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("页面=/macro-toolkit"));
      await waitFor(() => expect(permissionPanel).toHaveTextContent("授权申请已复制"));
    } finally {
      if (originalClipboard) {
        Object.defineProperty(window.navigator, "clipboard", originalClipboard);
      } else {
        Reflect.deleteProperty(window.navigator, "clipboard");
      }
    }
  });
});
