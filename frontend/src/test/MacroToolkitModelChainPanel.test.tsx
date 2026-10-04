import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import type { MacroToolkitModelChainResults, MacroToolkitModelReadiness } from "../api/macroToolkitClient";
import { createMockMacroToolkitClient } from "../mocks/macroToolkitMockClient";
import { MacroToolkitModelChainPanel } from "../features/macro-toolkit/panels/MacroToolkitModelChainPanel";
import { publishModelChainEvidenceBridge } from "../features/macro-toolkit/panels/macroToolkitModelEvidenceShared";

const STEP_LABELS = [
  "市场状态识别",
  "策略选择",
  "资产配置",
  "风险管理",
  "再平衡",
  "绩效评估",
  "决策链输出",
] as const;

const MODEL_HEADLINES = [
  "象限 过热 · 债券方向 空",
  "高波动 1/5 · 原油 63.49%",
  "平均相关 0.2764 · 正常",
  "高波动 3/5",
  "强多头 铜、原油 · 强空头 沪深300、中证500",
  "风险平价最大权重 铜期货 24.6362%",
  "-0.068 · 宽松",
  "无冷却 · 正常运行",
  "告警 1 条 · VOL_ALERT 1",
  "再平衡样本 4 条 · 夏普区间 0.75-1.21",
  "绩效样本 7 条 · 夏普区间 0.183-1.179",
  "研究回测 · PIT 门禁阻断",
  "空仓 4/4",
] as const;

const TREND_MODEL_IDS = ["merrill_clock", "dcc_garch", "crisis_score", "final_signal"] as const;

function applyCurrentModelChainContract(
  results: MacroToolkitModelChainResults,
): MacroToolkitModelChainResults {
  const cloned = structuredClone(results);
  const models = cloned.steps.flatMap((step) => step.models);
  const patchModel = (
    modelId: string,
    patch: Partial<MacroToolkitModelChainResults["steps"][number]["models"][number]>,
  ) => {
    const model = models.find((entry) => entry.id === modelId);
    if (!model) {
      throw new Error(`model ${modelId} missing`);
    }
    Object.assign(model, patch);
  };

  patchModel("garch", {
    as_of: null,
    generated_at: "2026-08-12T01:04:59+00:00",
  });
  patchModel("rebalance", {
    as_of: null,
    generated_at: "2026-08-12T01:07:15+00:00",
    headline: "再平衡样本 4 条 · 夏普区间 0.75-1.21",
  });
  patchModel("performance", {
    as_of: null,
    generated_at: "2026-08-12T01:07:30+00:00",
    headline: "绩效样本 7 条 · 夏普区间 0.183-1.179",
  });
  patchModel("backtest", {
    generated_at: "2026-08-12T01:07:45+00:00",
  });
  return cloned;
}

async function loadMockModelChainResults(): Promise<MacroToolkitModelChainResults> {
  const envelope = await createMockMacroToolkitClient().fetchMacroToolkitModelChainResults();
  return applyCurrentModelChainContract(envelope.result);
}

const MISSING_ARTIFACT_RESULTS: MacroToolkitModelChainResults = {
  as_of_date: "2026-08-11",
  observation_only: true,
  formal_use_allowed: false,
  steps: [
    {
      key: "market_state",
      step_no: 1,
      label: "市场状态识别",
      models: [
        {
          id: "merrill_clock",
          label: "美林时钟（中国版）",
          script_name: "merrill_clock_cn",
          artifact: "merrill_clock_latest.csv",
          artifact_status: "missing",
          as_of: null,
          generated_at: null,
          headline: "",
          columns: [],
          rows: [],
          trend: null,
        },
      ],
    },
  ],
};

function modelReadinessEntry(
  overrides: Partial<MacroToolkitModelReadiness> & Pick<MacroToolkitModelReadiness, "id" | "label" | "script_name">,
): MacroToolkitModelReadiness {
  return {
    expected_outputs: [],
    readiness: "artifact_backed",
    observation_only: true,
    formal_use_allowed: false,
    latest_modified_at: null,
    latest_content_date: null,
    missing_outputs: [],
    stale_outputs: [],
    notes: [],
    ...overrides,
  };
}

describe("MacroToolkitModelChainPanel", () => {
  afterEach(() => {
    publishModelChainEvidenceBridge(null);
  });

  it("renders the seven decision-chain steps and all thirteen model headlines", async () => {
    const results = await loadMockModelChainResults();

    render(<MacroToolkitModelChainPanel results={results} />);

    const panel = screen.getByTestId("macro-toolkit-model-chain");
    expect(panel).toHaveTextContent("模型链结果 · 决策链视图");
    expect(panel).toHaveTextContent("数据日 2026-08-11");
    expect(within(panel).getByText("仅观察 · 不入正式口径")).toBeInTheDocument();

    for (const label of STEP_LABELS) {
      expect(within(panel).getByText(label)).toBeInTheDocument();
    }
    for (const headline of MODEL_HEADLINES) {
      expect(within(panel).getByText(headline)).toBeInTheDocument();
    }
    expect(screen.getAllByTestId(/^macro-toolkit-model-chain-model-/)).toHaveLength(13);
  });

  it("keeps model tables collapsed by default and expands details on demand", async () => {
    const results = await loadMockModelChainResults();
    const user = userEvent.setup();

    render(<MacroToolkitModelChainPanel results={results} />);

    expect(screen.queryAllByRole("table")).toHaveLength(0);
    const toggles = screen.getAllByRole("button", { name: /^展开 .+ 明细$/ });
    expect(toggles).toHaveLength(13);

    const merrillCard = screen.getByTestId("macro-toolkit-model-chain-model-merrill_clock");
    const merrillToggle = within(merrillCard).getByRole("button", {
      name: "展开 美林时钟（中国版） 明细",
    });
    expect(merrillToggle).toHaveAttribute("aria-expanded", "false");

    await user.click(merrillToggle);

    expect(merrillToggle).toHaveAttribute("aria-expanded", "true");
    const table = within(merrillCard).getByRole("table");
    expect(within(table).getByText("增长动量")).toBeInTheDocument();
    expect(within(table).getByText("0.228")).toBeInTheDocument();
    expect(within(table).getByText("过热")).toBeInTheDocument();
    expect(within(table).getByText("0.228")).toHaveClass("macro-toolkit-model-chain__cell--numeric");

    await user.click(merrillToggle);
    expect(within(merrillCard).queryByRole("table")).not.toBeInTheDocument();
    expect(merrillToggle).toHaveAttribute("aria-expanded", "false");
  });

  it("shows a missing-artifact placeholder instead of a table", () => {
    render(<MacroToolkitModelChainPanel results={MISSING_ARTIFACT_RESULTS} />);

    const card = screen.getByTestId("macro-toolkit-model-chain-model-merrill_clock");
    expect(within(card).getByText("产物缺失")).toBeInTheDocument();
    expect(within(card).queryByRole("table")).not.toBeInTheDocument();
    expect(within(card).queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders nothing when the decision chain has no steps", () => {
    const { container } = render(
      <MacroToolkitModelChainPanel
        results={{
          as_of_date: null,
          observation_only: true,
          formal_use_allowed: false,
          steps: [],
        }}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("renders trend sparklines only for models that provide trend series", async () => {
    const results = await loadMockModelChainResults();

    render(<MacroToolkitModelChainPanel results={results} />);

    for (const modelId of TREND_MODEL_IDS) {
      const card = screen.getByTestId(`macro-toolkit-model-chain-model-${modelId}`);
      const chart = within(card).getByTestId(`macro-toolkit-model-chain-trend-${modelId}`);
      expect(chart).toBe(within(card).getByRole("img"));
      expect(chart.querySelectorAll("polyline").length).toBeGreaterThanOrEqual(1);
    }
    expect(screen.getAllByTestId(/^macro-toolkit-model-chain-trend-/)).toHaveLength(4);

    const merrillChart = screen.getByTestId("macro-toolkit-model-chain-trend-merrill_clock");
    expect(merrillChart.querySelectorAll("polyline")).toHaveLength(3);
    expect(merrillChart.querySelector("polyline title")).toHaveTextContent(
      "增长动量 · 2025-07 ~ 2026-06",
    );

    const finalChart = screen.getByTestId("macro-toolkit-model-chain-trend-final_signal");
    expect(finalChart.querySelectorAll("polyline")).toHaveLength(4);

    const merrillCard = screen.getByTestId("macro-toolkit-model-chain-model-merrill_clock");
    expect(within(merrillCard).getByText("近 12 月宏观动量（月度）")).toBeInTheDocument();

    for (const modelId of ["garch", "regime", "cta_trend", "risk_parity", "rebalance"]) {
      const card = screen.getByTestId(`macro-toolkit-model-chain-model-${modelId}`);
      expect(within(card).queryByRole("img")).not.toBeInTheDocument();
    }
  });

  it("keeps unknown data-day separate from generated time for timestamp-only artifacts", async () => {
    const results = await loadMockModelChainResults();

    render(<MacroToolkitModelChainPanel results={results} />);

    const garchCard = screen.getByTestId("macro-toolkit-model-chain-model-garch");
    // 数据日是业务口径日期，留在卡面；生成时间是系统运行时间戳，改由 title 留痕（含原始 ISO）。
    const asOf = within(garchCard).getByText("数据日 未知");
    expect(asOf).toHaveAttribute(
      "title",
      "数据日 未知 · 生成时间 08-12 09:04 · 2026-08-12T01:04:59+00:00",
    );
    expect(garchCard).not.toHaveTextContent("生成时间");
  });

  it("renders scheduler health badges with tone mapping and summary tooltips", async () => {
    const results = await loadMockModelChainResults();

    render(<MacroToolkitModelChainPanel results={results} />);

    const schedulerRow = screen.getByTestId("macro-toolkit-model-chain-scheduler");

    const dailyBadge = within(schedulerRow).getByTestId(
      "macro-toolkit-model-chain-scheduler-daily_chain",
    );
    expect(dailyBadge).toHaveTextContent("自动重算 08-12 09:04 部分降级");
    expect(dailyBadge).toHaveClass("macro-toolkit-model-chain__scheduler-badge--ok");
    expect(dailyBadge).not.toHaveClass("macro-toolkit-model-chain__scheduler-badge--failed");
    expect(dailyBadge).toHaveAttribute("title", "链 degraded · 链外脚本 6/6 完成");

    const freshnessBadge = within(schedulerRow).getByTestId(
      "macro-toolkit-model-chain-scheduler-freshness",
    );
    expect(freshnessBadge).toHaveTextContent("数据刷新 08-11 19:40 失败");
    expect(freshnessBadge).toHaveClass("macro-toolkit-model-chain__scheduler-badge--failed");
    expect(freshnessBadge).toHaveAttribute("title", "步骤 2 成功 / 2 失败 / 1 降级");
  });

  it("shows idle badges when scheduler receipts are null", async () => {
    const results = await loadMockModelChainResults();

    render(
      <MacroToolkitModelChainPanel
        results={{ ...results, scheduler: { daily_chain: null, freshness: null } }}
      />,
    );

    const dailyBadge = screen.getByTestId("macro-toolkit-model-chain-scheduler-daily_chain");
    expect(dailyBadge).toHaveTextContent("自动重算 未运行");
    expect(dailyBadge).toHaveClass("macro-toolkit-model-chain__scheduler-badge--idle");
    expect(screen.getByTestId("macro-toolkit-model-chain-scheduler-freshness")).toHaveTextContent(
      "数据刷新 未运行",
    );
  });

  it("shows a damaged receipt separately from a task that has never run", async () => {
    const results = await loadMockModelChainResults();

    render(
      <MacroToolkitModelChainPanel
        results={{
          ...results,
          scheduler: {
            daily_chain: {
              read_status: "invalid",
              reason_code: "receipt_invalid",
              task_name: "",
              status: "invalid",
              exit_code: null,
              generated_at: "",
              run_kind: "",
              summary: "回执不可读或已损坏",
            },
            freshness: null,
          },
        }}
      />,
    );

    const damaged = screen.getByTestId("macro-toolkit-model-chain-scheduler-daily_chain");
    expect(damaged).toHaveTextContent("自动重算 回执不可读/损坏");
    expect(damaged).toHaveClass("macro-toolkit-model-chain__scheduler-badge--failed");
    expect(damaged).toHaveAttribute("title", "回执不可读或已损坏");
    expect(screen.getByTestId("macro-toolkit-model-chain-scheduler-freshness")).toHaveTextContent(
      "数据刷新 未运行",
    );
  });

  // 徽标正文只留业务结论；模式/读写状态与 run_id 是系统标识，改由 title 留痕（证据不丢，只是不占业务段版面）。
  it("keeps reader, writer and run identity in the verified snapshot tooltip", async () => {
    const results = await loadMockModelChainResults();
    results.artifact_snapshot = {
      schema_version: "macro_toolkit_allocation_snapshot_read.v1",
      status: "ready",
      read_status: "ready",
      mode: "snapshot",
      run_id: "run-a",
      snapshot_status: "captured",
      writer_status: "captured",
      manifest_sha256: "a".repeat(64),
      target_artifact_count: 9,
      verified_artifact_count: 9,
      warnings: [],
    };

    render(<MacroToolkitModelChainPanel results={results} />);

    const badge = screen.getByTestId("macro-toolkit-model-chain-artifact-snapshot");
    expect(badge).toHaveAttribute("title", "模式 snapshot · 读取 ready · 写入 captured · run_id run-a");
    expect(badge).toHaveTextContent("已验证快照");
    expect(badge).not.toHaveTextContent("run_id");
  });

  it.each([
    {
      status: "missing" as const,
      readStatus: "missing" as const,
      mode: "live_unverified" as const,
      writerStatus: null,
      expected: "仅作未验证证据",
    },
    {
      status: "invalid" as const,
      readStatus: "invalid" as const,
      mode: "snapshot_fail_closed" as const,
      writerStatus: null,
      expected: "不可正式使用",
    },
    {
      status: "partial" as const,
      readStatus: "partial" as const,
      mode: "snapshot" as const,
      writerStatus: "partial" as const,
      expected: "不可正式使用",
    },
  ])("does not present $mode/$readStatus as verified", async (sample) => {
    const results = await loadMockModelChainResults();
    results.artifact_snapshot = {
      schema_version: "macro_toolkit_allocation_snapshot_read.v1",
      status: sample.status,
      read_status: sample.readStatus,
      mode: sample.mode,
      run_id: sample.mode === "live_unverified" ? null : "run-b",
      snapshot_status: sample.writerStatus,
      writer_status: sample.writerStatus,
      manifest_sha256: null,
      target_artifact_count: 9,
      verified_artifact_count: sample.status === "partial" ? 8 : 0,
      warnings: ["snapshot_warning"],
    };

    render(<MacroToolkitModelChainPanel results={results} />);

    const badge = screen.getByTestId("macro-toolkit-model-chain-artifact-snapshot");
    expect(badge).toHaveTextContent(sample.expected);
    expect(badge).not.toHaveTextContent("已验证快照");
  });

  it("omits the scheduler row when the scheduler field is absent", () => {
    render(<MacroToolkitModelChainPanel results={MISSING_ARTIFACT_RESULTS} />);

    expect(screen.getByTestId("macro-toolkit-model-chain")).toBeInTheDocument();
    expect(screen.queryByTestId("macro-toolkit-model-chain-scheduler")).not.toBeInTheDocument();
  });

  it("collapses the card wall to headline rows by default while keeping the DOM intact", async () => {
    const results = await loadMockModelChainResults();
    const user = userEvent.setup();

    render(<MacroToolkitModelChainPanel results={results} />);

    const panel = screen.getByTestId("macro-toolkit-model-chain");
    expect(panel).toHaveClass("macro-toolkit-model-chain--cards-collapsed");
    // 折叠只走 CSS：headline、13 个明细开关和趋势图仍全部在 DOM 里。
    expect(screen.getAllByRole("button", { name: /^展开 .+ 明细$/ })).toHaveLength(13);
    expect(screen.getAllByTestId(/^macro-toolkit-model-chain-trend-/)).toHaveLength(4);

    const wallToggle = screen.getByRole("button", { name: "展开全部模型卡" });
    expect(wallToggle).toHaveAttribute("aria-expanded", "false");

    await user.click(wallToggle);
    expect(panel).not.toHaveClass("macro-toolkit-model-chain--cards-collapsed");
    expect(wallToggle).toHaveTextContent("收起全部模型卡");
    expect(wallToggle).toHaveAttribute("aria-expanded", "true");

    await user.click(wallToggle);
    expect(panel).toHaveClass("macro-toolkit-model-chain--cards-collapsed");
  });

  it("keeps the backtest admission gate and actual run coverage visible while the card wall is collapsed", async () => {
    const results = await loadMockModelChainResults();
    const backtest = results.steps
      .flatMap((step) => step.models)
      .find((model) => model.id === "backtest");

    expect(backtest).toMatchObject({
      script_name: "backtest_cn",
      artifact: "backtest_results.csv",
      as_of: "2026-08-21",
      headline: "研究回测 · PIT 门禁阻断",
    });
    expect(backtest?.as_of).toBe(backtest?.backtest_context?.sample.return_end_date);

    render(<MacroToolkitModelChainPanel results={results} />);

    const panel = screen.getByTestId("macro-toolkit-model-chain");
    const card = screen.getByTestId("macro-toolkit-model-chain-model-backtest");
    const context = within(card).getByTestId("macro-toolkit-model-chain-backtest-context");
    expect(panel).toHaveClass("macro-toolkit-model-chain--cards-collapsed");
    expect(context).toHaveTextContent("未准入");
    expect(context).toHaveTextContent("PIT 门禁阻断");
    expect(context).toHaveTextContent("禁止正式使用");
    expect(context).toHaveTextContent("2024-01-03 至 2026-08-21");
    expect(context).toHaveTextContent("638 个交易日");
    expect(context).toHaveTextContent("639 条");
    expect(context).toHaveTextContent("5 / 8");
    expect(context).toHaveTextContent("目标上限 5 年 · 实际以收益样本为准");
    expect(context).toHaveTextContent("bond_gov、bond_10y、bond_cdb");
  });

  it("renders missing backtest-manifest coverage as unknown instead of zero", async () => {
    const results = structuredClone(await loadMockModelChainResults());
    const backtest = results.steps
      .flatMap((step) => step.models)
      .find((model) => model.id === "backtest");
    const context = backtest?.backtest_context;
    if (!backtest || !context) {
      throw new Error("mock backtest context missing");
    }
    backtest.backtest_context = {
      ...context,
      sample: {
        ...context.sample,
        price_start_date: null,
        price_end_date: null,
        price_observation_days: null,
        return_start_date: null,
        return_end_date: null,
        return_trading_days: null,
      },
      asset_coverage: {
        ...context.asset_coverage,
        used_asset_count: null,
        used_assets: [],
        missing_assets: [],
        complete: null,
      },
      pit_gate: {
        ...context.pit_gate,
        reason_code: "backtest_manifest_missing",
        completeness_pct: null,
      },
    };

    render(<MacroToolkitModelChainPanel results={results} />);

    const summary = screen.getByTestId("macro-toolkit-model-chain-backtest-context");
    expect(summary).toHaveTextContent("回测运行清单缺失");
    expect(summary).toHaveTextContent("— / 8");
    expect(summary).not.toHaveTextContent("0 个交易日");
    expect(summary).not.toHaveTextContent("null");
  });

  it("badges chain cards with published readiness and opens the evidence drawer from a card", async () => {
    const results = await loadMockModelChainResults();
    const user = userEvent.setup();
    publishModelChainEvidenceBridge({
      entries: [
        modelReadinessEntry({
          id: "final_signal",
          label: "Final Signal Aggregator",
          script_name: "signal_aggregator",
          expected_outputs: ["final_signal.csv"],
          readiness: "artifact_backed",
          latest_content_date: "2026-08-08",
        }),
        modelReadinessEntry({
          id: "dcc_garch",
          label: "DCC-GARCH",
          script_name: "dcc_garch_cn",
          expected_outputs: ["dcc_latest.csv", "dcc_results.csv"],
          readiness: "missing_output",
          missing_outputs: ["dcc_latest.csv", "dcc_results.csv"],
        }),
      ],
      chainRunResult: null,
      showAcceptance: true,
    });

    render(<MacroToolkitModelChainPanel results={results} />);

    const finalCard = screen.getByTestId("macro-toolkit-model-chain-model-final_signal");
    expect(within(finalCard).getByText("产物支撑")).toBeInTheDocument();
    const dccCard = screen.getByTestId("macro-toolkit-model-chain-model-dcc_garch");
    expect(within(dccCard).getByText("缺产物")).toBeInTheDocument();
    // 未匹配就绪度条目的卡不带角标、不带证据按钮。
    const garchCard = screen.getByTestId("macro-toolkit-model-chain-model-garch");
    expect(within(garchCard).queryByRole("button", { name: /模型证据/ })).not.toBeInTheDocument();

    const evidenceButton = within(dccCard).getByRole("button", {
      name: "查看 DCC-GARCH 动态相关 模型证据",
    });
    await user.click(evidenceButton);

    const detail = screen.getByTestId("macro-toolkit-model-signal-detail");
    expect(detail).toHaveTextContent("DCC-GARCH");
    expect(detail).toHaveTextContent("预期产物");
    expect(detail).toHaveTextContent("dcc_latest.csv");
    expect(detail).toHaveTextContent("产物验收");
    expect(detail).toHaveTextContent("需要运行模型链");
    // 预检/运行按钮已移到模型链工具条（模型信号摘要区），抽屉内不再渲染。
    expect(within(detail).queryByTestId("macro-toolkit-model-signal-chain-preflight")).not.toBeInTheDocument();
    expect(within(detail).queryByTestId("macro-toolkit-model-signal-chain-run")).not.toBeInTheDocument();

    await user.click(evidenceButton);
    expect(screen.queryByTestId("macro-toolkit-model-signal-detail")).not.toBeInTheDocument();
  });

  it("keeps evidence entry points for published readiness models outside the chain", async () => {
    const results = await loadMockModelChainResults();
    const user = userEvent.setup();
    publishModelChainEvidenceBridge({
      entries: [
        modelReadinessEntry({
          id: "crowding",
          label: "Crowding",
          script_name: "crowding_cn",
          expected_outputs: ["crowding_latest.csv"],
          readiness: "stale",
          stale_outputs: ["crowding_latest.csv"],
        }),
      ],
      chainRunResult: null,
      showAcceptance: true,
    });

    render(<MacroToolkitModelChainPanel results={results} />);

    const offChainButton = screen.getByRole("button", { name: "查看 拥挤度 模型证据" });
    expect(screen.getByText("链外模型证据")).toBeInTheDocument();

    await user.click(offChainButton);
    const detail = screen.getByTestId("macro-toolkit-model-signal-detail");
    expect(detail).toHaveTextContent("拥挤度");
    expect(detail).toHaveTextContent("陈旧");
  });
});
