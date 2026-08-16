import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const echartsOptions = vi.hoisted(() => [] as unknown[]);

vi.mock("../lib/echarts", () => ({
  default: ({ option }: { option: unknown }) => {
    echartsOptions.push(option);
    return <div data-testid="macro-observation-echarts-stub" />;
  },
}));

import type {
  MacroToolkitHasonStrategy,
  MacroToolkitModelReadiness,
} from "../api/macroToolkitClient";
import type {
  MacroObservationCrisisEvidenceView,
  MacroObservationStrategyEvidenceView,
} from "../features/macro-observation/model/macroObservationPageModel";
import MacroObservationCrisisSection from "../features/macro-observation/sections/MacroObservationCrisisSection";
import MacroObservationModelStrategySection from "../features/macro-observation/sections/MacroObservationModelStrategySection";
import { EM_DASH } from "../pageModel";

function buildModelReadiness(
  overrides: Partial<MacroToolkitModelReadiness> = {},
): MacroToolkitModelReadiness {
  return {
    id: "crisis_score",
    label: "Crisis Score",
    script_name: "crisis_score_cn",
    expected_outputs: ["crisis_score_latest.csv"],
    readiness: "artifact_backed",
    observation_only: true,
    formal_use_allowed: false,
    missing_outputs: [],
    stale_outputs: [],
    notes: [],
    ...overrides,
  };
}

function buildHasonStrategy(
  overrides: Partial<MacroToolkitHasonStrategy> = {},
): MacroToolkitHasonStrategy {
  return {
    key: "hason_macro_strategy",
    framework_name: "Hason 宏观策略框架",
    basis: "analytical",
    observation_only: true,
    formal_use_allowed: false,
    formal_metric_id: null,
    status: "partial",
    display_status: "partial",
    readiness: {
      ready_modules: 3,
      partial_modules: 1,
      missing_modules: 2,
      missing_script_count: 1,
      total_modules: 6,
      ratio: 0.5,
    },
    modules: [],
    runtime_output_status: "partial",
    runtime_outputs: [],
    required_runtime_outputs: [],
    runtime_output_gaps: [],
    missing_runtime_outputs: [],
    stale_runtime_outputs: [],
    boundary: "仅观察使用，不进入正式投资流程。",
    source_trace: [],
    ...overrides,
  };
}

function buildStrategyView(
  overrides: Partial<MacroObservationStrategyEvidenceView> = {},
): MacroObservationStrategyEvidenceView {
  return {
    rows: [
      {
        key: "multi_factor_selection",
        label: "多因子选股",
        statusText: "已完成",
        tone: "positive",
        chainNote: "已接入真实行情或因子快照",
      },
      {
        key: "low_crowding",
        label: "低拥挤度",
        statusText: "部分降级",
        tone: "warning",
        chainNote: "部分真实供数，缺口需在完整分析中复核",
      },
      {
        key: "momentum_sample",
        label: "动量样例",
        statusText: "样例展示",
        tone: "neutral",
        chainNote: "仅策略可用性检查，未接入真实供数",
      },
      {
        key: "macro_etf",
        label: "宏观 ETF 轮动",
        statusText: "不可用",
        tone: "negative",
        chainNote: null,
      },
    ],
    counts: { full: 1, partial: 1, degraded: 2, sample: 1 },
    commonChainNote: null,
    shadowPortfolio: {
      label: "影子组合只读",
      value: "2026-08-12",
      detail: "6 个周期 · 保持观察，不替换正式规则",
      tone: "neutral",
    },
    etfStrategy: { boundary: "observation_only", dualFrequencyStatusText: "进攻" },
    dataStatus: {
      status: "unavailable",
      statusText: "不可用",
      reason: "价格上下文缺失",
      summaryCount: 4,
    },
    ...overrides,
  };
}

function buildCrisisView(
  overrides: Partial<Extract<MacroObservationCrisisEvidenceView, { state: "ready" }>> = {},
): MacroObservationCrisisEvidenceView {
  return {
    state: "ready",
    headline: "Crisis Score -0.57: 宽松",
    scoreText: "-0.6",
    regime: "常态",
    recommendation: "可适当加仓，风险偏好环境",
    percentileText: "36.21%",
    availableComponentCount: 4,
    componentCount: 5,
    componentMissingCount: 1,
    coverageNote: null,
    history: [
      { date: "2026-04-03", value: -0.63 },
      { date: "2026-04-10", value: -0.57 },
      { date: "2026-04-17", value: -0.52 },
    ],
    ...overrides,
  };
}

beforeEach(() => {
  echartsOptions.length = 0;
});

describe("MacroObservationModelStrategySection", () => {
  it("中文化就绪枚举、未知 token 兜底原样并渲染降级原因", () => {
    render(
      <MacroObservationModelStrategySection
        modelReadiness={[
          buildModelReadiness(),
          buildModelReadiness({
            id: "merrill_clock",
            label: "Merrill Clock",
            readiness: "degraded",
            degraded_reason: "产物内容日滞后",
          }),
          buildModelReadiness({
            id: "mystery_model",
            label: "Mystery Model",
            readiness: "mystery_state" as MacroToolkitModelReadiness["readiness"],
          }),
        ]}
        hasonStrategy={null}
        strategy={buildStrategyView()}
      />,
    );

    const table = screen.getByRole("region", { name: "模型就绪简表" });
    expect(within(table).getByText("工件支撑")).toHaveAttribute("data-tone", "positive");
    expect(within(table).getByText("降级")).toHaveAttribute("data-tone", "warning");
    expect(within(table).getByText("产物内容日滞后")).toBeInTheDocument();
    // 未知 token 兜底：原样文案 + neutral（muted 徽标）。
    expect(within(table).getByText("mystery_state")).toHaveAttribute("data-tone", "neutral");
    // degraded_reason 缺失时说明列用 EM_DASH，禁止空白。
    expect(within(table).getAllByText(EM_DASH).length).toBeGreaterThan(0);
    // 「仅观察」卡级脚注已按 §6 去重删除（只读边界由页头徽标与细注声明一次）。
    expect(within(table).queryByText("仅观察，不作为正式投资信号。")).not.toBeInTheDocument();
  });

  it("modelReadiness 空数组给待完整分析空态", () => {
    render(
      <MacroObservationModelStrategySection
        modelReadiness={[]}
        hasonStrategy={null}
        strategy={buildStrategyView()}
      />,
    );
    expect(screen.getByText("模型就绪清单待完整分析确认。")).toBeInTheDocument();
  });

  it("hason null 给空态，非空渲染就绪读数与边界", () => {
    const { rerender } = render(
      <MacroObservationModelStrategySection
        modelReadiness={[]}
        hasonStrategy={null}
        strategy={buildStrategyView()}
      />,
    );
    expect(screen.getByText("Hason 框架摘要待完整分析确认。")).toBeInTheDocument();

    rerender(
      <MacroObservationModelStrategySection
        modelReadiness={[]}
        hasonStrategy={buildHasonStrategy()}
        strategy={buildStrategyView()}
      />,
    );
    const card = screen.getByRole("region", { name: "Hason 框架摘要" });
    expect(within(card).getByText("Hason 宏观策略框架")).toBeInTheDocument();
    expect(within(card).getByText("部分就绪")).toHaveAttribute("data-tone", "warning");
    const readinessRow = within(card).getByLabelText("Hason 模块就绪读数");
    expect(readinessRow).toHaveTextContent("就绪 3");
    expect(readinessRow).toHaveTextContent("部分 1");
    expect(readinessRow).toHaveTextContent("缺失 2");
    expect(readinessRow).toHaveTextContent("共 6 模块");
    expect(within(card).getByText("仅观察使用，不进入正式投资流程。")).toBeInTheDocument();
  });

  it("策略表渲染四态徽标与来源链，并露出不可用原因琥珀行", () => {
    render(
      <MacroObservationModelStrategySection
        modelReadiness={[]}
        hasonStrategy={null}
        strategy={buildStrategyView()}
      />,
    );

    const panel = screen.getByRole("region", { name: "策略供数" });
    expect(within(panel).getByText("已完成")).toHaveAttribute("data-tone", "positive");
    expect(within(panel).getByText("部分降级")).toHaveAttribute("data-tone", "warning");
    expect(within(panel).getByText("样例展示")).toHaveAttribute("data-tone", "neutral");
    expect(within(panel).getByText("不可用")).toHaveAttribute("data-tone", "negative");
    // 来源链列只留行间差异；行级 null 用 EM_DASH 占位（§6 缺值纪律）。
    expect(within(panel).getByText("已接入真实行情或因子快照")).toBeInTheDocument();
    expect(within(panel).getAllByText(EM_DASH).length).toBeGreaterThan(0);
    // 区头 meta 全量列出（此夹具四计数均非零），分隔改斜杠不占 `·` 配额（§7）。
    expect(within(panel).getByText("全链路 1 / 部分 1 / 降级 2 / 样例 1")).toBeInTheDocument();

    // strategy_data_status.reason：P0 可见的不可用原因琥珀行。
    const reason = within(panel).getByText("价格上下文缺失");
    expect(reason.closest("p")).toHaveClass("macro-observation-modelstrategy-reason");
    // 右列策略数据状态卡同步露出 status 与摘要计数。
    const statusCard = screen.getByRole("region", { name: "策略数据状态" });
    expect(within(statusCard).getByText("不可用")).toBeInTheDocument();
    expect(within(statusCard).getByText("摘要 4 条")).toBeInTheDocument();
  });

  it("reason 缺失时不渲染琥珀行", () => {
    render(
      <MacroObservationModelStrategySection
        modelReadiness={[]}
        hasonStrategy={null}
        strategy={buildStrategyView({
          dataStatus: { status: "ready", statusText: "数据齐备", reason: null, summaryCount: 6 },
        })}
      />,
    );
    expect(screen.queryByText("策略不可用原因")).not.toBeInTheDocument();
  });

  it("shadow/etf 摘要卡渲染读数与缺失态", () => {
    const { rerender } = render(
      <MacroObservationModelStrategySection
        modelReadiness={[]}
        hasonStrategy={null}
        strategy={buildStrategyView()}
      />,
    );
    const shadowCard = screen.getByLabelText("影子组合摘要");
    expect(within(shadowCard).getByText("影子组合只读")).toBeInTheDocument();
    expect(within(shadowCard).getByText("2026-08-12")).toBeInTheDocument();
    expect(
      within(shadowCard).getByText("6 个周期 · 保持观察，不替换正式规则"),
    ).toBeInTheDocument();
    const etfCard = screen.getByLabelText("宏观 ETF 策略摘要");
    // 「仅观察」卡级脚注按 §6 去重删除；boundary 原文收 title 供溯源。
    expect(within(etfCard).getByText("双频 进攻")).toHaveAttribute("title", "observation_only");
    expect(within(etfCard).queryByText("observation_only")).not.toBeInTheDocument();

    rerender(
      <MacroObservationModelStrategySection
        modelReadiness={[]}
        hasonStrategy={null}
        strategy={buildStrategyView({ etfStrategy: null })}
      />,
    );
    const missingEtfCard = screen.getByLabelText("宏观 ETF 策略摘要");
    expect(within(missingEtfCard).getByText(EM_DASH)).toBeInTheDocument();
    expect(
      within(missingEtfCard).getByText("策略摘要未携带 ETF 快照，完整分析后再确认。"),
    ).toBeInTheDocument();
  });

  it("strategy rows 空给待完整分析空态文案", () => {
    render(
      <MacroObservationModelStrategySection
        modelReadiness={[]}
        hasonStrategy={null}
        strategy={buildStrategyView({
          rows: [],
          counts: { full: 0, partial: 0, degraded: 0, sample: 0 },
        })}
      />,
    );
    expect(screen.getByText("策略供数明细待完整分析确认。")).toBeInTheDocument();
  });

  it("来源链全表同句时收敛区头一次并删除整列", () => {
    render(
      <MacroObservationModelStrategySection
        modelReadiness={[]}
        hasonStrategy={null}
        strategy={buildStrategyView({
          rows: [
            {
              key: "multi_factor_selection",
              label: "多因子选股",
              statusText: "已完成",
              tone: "positive",
              chainNote: null,
            },
            {
              key: "low_crowding",
              label: "低拥挤度",
              statusText: "已完成",
              tone: "positive",
              chainNote: null,
            },
          ],
          commonChainNote: "已接入真实行情或因子快照",
        })}
      />,
    );

    const panel = screen.getByRole("region", { name: "策略供数" });
    // 同句只出现一次（收敛注），表头不再渲染来源链列。
    expect(within(panel).getAllByText("已接入真实行情或因子快照")).toHaveLength(1);
    expect(within(panel).queryByText("来源链")).not.toBeInTheDocument();
  });

  it("区头 meta 只显示非零计数", () => {
    render(
      <MacroObservationModelStrategySection
        modelReadiness={[]}
        hasonStrategy={null}
        strategy={buildStrategyView({
          counts: { full: 4, partial: 0, degraded: 0, sample: 0 },
        })}
      />,
    );
    expect(screen.getByText("全链路 4")).toBeInTheDocument();
  });
});

describe("MacroObservationCrisisSection", () => {
  it("渲染 score/regime/recommendation/percentile/components 读数栈", () => {
    render(
      <MemoryRouter>
        <MacroObservationCrisisSection crisis={buildCrisisView()} />
      </MemoryRouter>,
    );

    const readout = screen.getByLabelText("危机分读数");
    // 危机分大字徽标按 §6 去重删除（读数保留在 01 KPI 与 02 信号带）；
    // headline 原句保留作为证据上下文。
    expect(within(readout).queryByText("-0.6")).not.toBeInTheDocument();
    expect(within(readout).queryByText("常态")).not.toBeInTheDocument();
    expect(within(readout).getByText("Crisis Score -0.57: 宽松")).toBeInTheDocument();
    expect(within(readout).getByText("36.21%")).toBeInTheDocument();
    expect(within(readout).getByText("可用 4/5")).toBeInTheDocument();
    expect(within(readout).getByText("模型建议")).toBeInTheDocument();
    expect(within(readout).getByText("可适当加仓，风险偏好环境")).toBeInTheDocument();
    expect(within(readout).getByRole("link", { name: "宏观工具页" })).toHaveAttribute(
      "href",
      "/macro-toolkit",
    );
  });

  it("deferred 态给延后文案且不初始化图表", () => {
    render(
      <MemoryRouter>
        <MacroObservationCrisisSection crisis={{ state: "deferred", note: "完整分析后确认" }} />
      </MemoryRouter>,
    );

    expect(screen.getByText("危机分证据完整分析后确认。")).toBeInTheDocument();
    const container = screen.getByTestId("macro-observation-crisis-chart");
    expect(within(container).getByText("历史序列待完整分析确认")).toBeInTheDocument();
    expect(screen.queryByTestId("macro-observation-echarts-stub")).not.toBeInTheDocument();
    expect(echartsOptions).toHaveLength(0);
  });

  it("history 不足 2 点给暂无历史序列占位", () => {
    render(
      <MemoryRouter>
        <MacroObservationCrisisSection
          crisis={buildCrisisView({ history: [{ date: "2026-04-10", value: -0.57 }] })}
        />
      </MemoryRouter>,
    );

    const container = screen.getByTestId("macro-observation-crisis-chart");
    expect(within(container).getByText("暂无历史序列")).toBeInTheDocument();
    expect(screen.queryByTestId("macro-observation-echarts-stub")).not.toBeInTheDocument();
    expect(echartsOptions).toHaveLength(0);
  });

  it("history 正常时在占位容器内初始化折线并传入全量点", () => {
    render(
      <MemoryRouter>
        <MacroObservationCrisisSection crisis={buildCrisisView()} />
      </MemoryRouter>,
    );

    const container = screen.getByTestId("macro-observation-crisis-chart");
    expect(within(container).getByTestId("macro-observation-echarts-stub")).toBeInTheDocument();
    expect(echartsOptions.length).toBeGreaterThan(0);
    const option = echartsOptions.at(-1) as {
      xAxis: { data: string[] };
      series: Array<{
        type: string;
        data: number[];
        showSymbol: boolean;
        markLine?: { data: Array<{ yAxis?: number }> };
        markPoint?: { data: Array<{ coord?: [number, number] }>; label?: { formatter?: string } };
      }>;
    };
    expect(option.series).toHaveLength(1);
    expect(option.series[0]?.type).toBe("line");
    expect(option.series[0]?.data).toHaveLength(3);
    expect(option.series[0]?.showSymbol).toBe(false);
    expect(option.xAxis.data).toEqual(["2026-04-03", "2026-04-10", "2026-04-17"]);
    // 0 参考线 + 末点数值标注（阈值后端未下发，不虚构阈值带）。
    expect(option.series[0]?.markLine?.data).toEqual([{ yAxis: 0 }]);
    expect(option.series[0]?.markPoint?.data).toEqual([{ name: "latest", coord: [2, -0.52] }]);
    expect(option.series[0]?.markPoint?.label?.formatter).toBe("-0.52");
  });
});
