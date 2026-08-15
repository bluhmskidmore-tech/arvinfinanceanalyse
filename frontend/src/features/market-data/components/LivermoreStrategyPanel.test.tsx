import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EM_DASH } from "../../../utils/format";
import type { LivermoreStrategyModel } from "../lib/livermoreStrategyModel";
import { LivermoreStrategyPanel } from "./LivermoreStrategyPanel";

function makeModel(): LivermoreStrategyModel {
  return {
    strategyName: "Livermore A股趋势门控",
    asOfDate: "2026-04-30",
    requestedAsOfDate: "2026-05-06",
    statusNotes: [],
    marketGate: {
      state: "HOT",
      exposure: 0.75,
      exposureDisplay: "80%",
      passedConditions: 3,
      availableConditions: 4,
      requiredConditions: 4,
      conditions: [],
      macroDisclosure: null,
    },
    ruleBlocks: [],
    diagnostics: [],
    dataGaps: [
      {
        inputFamily: "position_risk",
        status: "missing",
        statusLabel: "缺失",
        evidence: "No position snapshot is loaded.",
        input: null,
        businessDate: null,
        ageDays: null,
        tier: null,
        freshnessLabel: null,
      },
    ],
    supportedOutputs: [
      { key: "market_gate", label: "市场门控" },
      { key: "stock_candidates", label: "个股候选" },
    ],
    sectorRank: null,
    stockCandidates: {
      formulaVersion: "rv_livermore_stock_candidates_bundle_v1",
      marketState: "HOT",
      factorMissingCount: null,
      positionSizeHint: null,
      items: [
        {
          rank: 1,
          stockCode: "000001.SZ",
          stockName: "Alpha",
          sectorName: "电子",
          sectorRank: 1,
          close: "22.000",
          breakoutLevel: "21.800",
          ma20: "20.500",
          ma60: "19.800",
          ma120: "18.200",
          closeStrength: "0.830",
          gapNorm: "-0.120",
          abnormalTurnover: "1.390",
          entryTrigger: "21.800",
          pullbackWatch: "20.500",
          defenseLine: "19.800",
          sizeHint: null,
        },
      ],
    },
    meanReversionCandidates: null,
    factorScreenCandidates: null,
    themeBreakout: null,
    riskExit: null,
    unsupportedOutputs: [
      {
        key: "risk_exit",
        label: "风险退出",
        reason: "No position snapshot is loaded.",
      },
    ],
  } as LivermoreStrategyModel;
}

describe("LivermoreStrategyPanel", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.useRealTimers();
  });

  it("shows candidate observation levels and lets the user manage a local watch pool", () => {
    render(
      <LivermoreStrategyPanel
        model={makeModel()}
        isLoading={false}
        isError={false}
        onRetry={vi.fn()}
      />,
    );

    const candidates = screen.getByTestId("livermore-stock-candidates");
    expect(candidates).toHaveTextContent("突破买点 21.800");
    expect(candidates).toHaveTextContent("回踩观察 20.500");
    expect(candidates).toHaveTextContent("防守位 19.800");

    fireEvent.click(within(candidates).getByRole("button", { name: "加入观察" }));

    const pool = screen.getByTestId("livermore-watch-pool");
    expect(pool).toHaveTextContent("Alpha");
    expect(pool).toHaveTextContent("买点 21.800");
    expect(within(candidates).getByRole("button", { name: "已入池" })).toBeDisabled();

    fireEvent.click(within(pool).getByRole("button", { name: "移出" }));
    expect(pool).toHaveTextContent("尚未选中候选股");
  });

  it("renders the risk_budget position size hint with policy version when present", () => {
    const model = makeModel();
    model.stockCandidates = {
      ...model.stockCandidates!,
      positionSizeHint: {
        policyVersion: "sizing_rb_v1_stock_candidate",
        coverageDegraded: true,
        coverageWarning: "ema10 stop_ref 缺失率超过 10%，建议仓位提示已降级。",
        gateExposureNote: "raw_weight 为单票权重上限建议；串联 gate 敞口截断由引擎执行。",
        shadowNote: "等权 shadow 对照仍在回测输出。",
      },
      items: model.stockCandidates!.items.map((item) => ({
        ...item,
        sizeHint: "≤ 12.5% · EMA10止损",
      })),
    };

    render(
      <LivermoreStrategyPanel
        model={model}
        isLoading={false}
        isError={false}
        onRetry={vi.fn()}
      />,
    );

    const policyLine = screen.getByTestId("livermore-position-size-hint-policy");
    expect(policyLine).toHaveTextContent("建议仓位政策 sizing_rb_v1_stock_candidate");
    expect(policyLine).toHaveTextContent("串联 gate 敞口截断由引擎执行");
    expect(policyLine).toHaveTextContent("等权 shadow 对照仍在回测输出");
    expect(policyLine).toHaveTextContent("建议仓位提示已降级");
    expect(screen.getByTestId("livermore-stock-candidates")).toHaveTextContent(
      "建议仓位 ≤ 12.5% · EMA10止损",
    );
  });

  it("hides the position size hint for legacy models without the block", () => {
    render(
      <LivermoreStrategyPanel
        model={makeModel()}
        isLoading={false}
        isError={false}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.queryByTestId("livermore-position-size-hint-policy")).toBeNull();
    expect(screen.getByTestId("livermore-stock-candidates")).not.toHaveTextContent("建议仓位");
  });

  it("shows input freshness and degraded quality notes in data gaps", () => {
    const model = makeModel();
    model.statusNotes = [
      "breadth breadth_close data lagged 8 days (stale), signal quality degraded",
    ];
    model.dataGaps = [
      {
        inputFamily: "breadth",
        status: "stale",
        statusLabel: "陈旧",
        evidence: "Breadth input is stale.",
        input: "breadth_close",
        businessDate: "2026-04-21",
        ageDays: 8,
        tier: "stale",
        freshnessLabel: "输入 breadth_close · 日期 2026-04-21 · T+8 · stale",
      },
    ];

    render(
      <LivermoreStrategyPanel
        model={model}
        isLoading={false}
        isError={false}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByTestId("livermore-status-notes")).toHaveTextContent(
      "signal quality degraded",
    );
    const dataGaps = screen.getByTestId("livermore-data-gaps");
    expect(dataGaps).toHaveTextContent("breadth_close");
    expect(dataGaps).toHaveTextContent("2026-04-21");
    expect(dataGaps).toHaveTextContent("T+8");
    expect(dataGaps).toHaveTextContent("stale");
  });

  it("discloses missing fundamental factors and missing entry cost basis", () => {
    const model = makeModel();
    model.stockCandidates = {
      ...model.stockCandidates!,
      factorMissingCount: 2,
    };
    model.riskExit = {
      formulaVersion: "rv_livermore_risk_exit_ema10_volume_obsfallback_v3",
      positionCount: 1,
      signalCount: 1,
      items: [
        {
          stockCode: "000777.SZ",
          stockName: "Watch Alpha",
          reason: "2d_below_ema10_with_volume",
          entryCost: EM_DASH,
          entryCostAvailable: false,
          barsSinceEntry: 4,
          latestClose: "19.800",
          latestEma10: "20.100",
        },
      ],
    };

    render(
      <LivermoreStrategyPanel
        model={model}
        isLoading={false}
        isError={false}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByTestId("livermore-stock-candidates")).toHaveTextContent("缺 2 个因子");
    expect(screen.getByTestId("livermore-risk-exit")).toHaveTextContent("成本价缺失");
  });

  it("renders multiple data gaps from the same input family without duplicate row keys", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    const model = makeModel();
    model.dataGaps = [
      {
        inputFamily: "breadth",
        status: "stale",
        statusLabel: "陈旧",
        evidence: "Breadth input is stale.",
        input: "breadth_close",
        businessDate: "2026-04-21",
        ageDays: 8,
        tier: "stale",
        freshnessLabel: "输入 breadth_close · 日期 2026-04-21 · T+8 · stale",
      },
      {
        inputFamily: "breadth",
        status: "look_ahead",
        statusLabel: "前视风险",
        evidence: "breadth_close business_date is later than the resolved trade_date.",
        input: "breadth_close",
        businessDate: "2026-05-02",
        ageDays: -1,
        tier: "fresh",
        freshnessLabel: "输入 breadth_close · 日期 2026-05-02 · T+-1 · fresh",
      },
    ];

    render(
      <LivermoreStrategyPanel
        model={model}
        isLoading={false}
        isError={false}
        onRetry={vi.fn()}
      />,
    );

    const dataGaps = screen.getByTestId("livermore-data-gaps");
    expect(dataGaps).toHaveTextContent("T+8");
    expect(dataGaps).toHaveTextContent("T+-1");
    expect(dataGaps).toHaveTextContent("前视风险");
    expect(
      consoleError.mock.calls.some((call) =>
        call.some((part) => String(part).includes("Encountered two children with the same key")),
      ),
    ).toBe(false);
    consoleError.mockRestore();
  });

  it("collapses a repeated gap sentence into one shared note with row references", () => {
    const model = makeModel();
    const sharedSentence =
      "Choice stock materialized input coverage is incomplete for the resolved trade date.";
    model.ruleBlocks = [
      {
        key: "stock_pivot",
        title: "Stock pivot filters",
        status: "blocked",
        statusLabel: "受阻",
        summary: sharedSentence,
        requiredInputs: [],
        missingInputs: [],
      },
      {
        key: "risk_exit",
        title: "Risk and exit rules",
        status: "ready",
        statusLabel: "可用",
        summary: "Risk and exit output is available.",
        requiredInputs: [],
        missingInputs: [],
      },
    ];
    model.dataGaps = [
      {
        inputFamily: "turnover_persistence",
        status: "partial",
        statusLabel: "部分",
        evidence: sharedSentence,
        input: null,
        businessDate: null,
        ageDays: null,
        tier: null,
        freshnessLabel: null,
      },
      {
        inputFamily: "stock_universe",
        status: "partial",
        statusLabel: "部分",
        evidence: sharedSentence,
        input: null,
        businessDate: null,
        ageDays: null,
        tier: null,
        freshnessLabel: null,
      },
    ];

    render(
      <LivermoreStrategyPanel
        model={model}
        isLoading={false}
        isError={false}
        onRetry={vi.fn()}
      />,
    );

    // 完整原文只出现在共同说明一处，行内收敛为短引用（原文保留在 title）。
    const sharedNotes = screen.getByTestId("livermore-shared-gap-notes");
    expect(sharedNotes).toHaveTextContent(sharedSentence);
    expect(screen.getAllByText(sharedSentence)).toHaveLength(1);
    const rowReferences = screen.getAllByText("同上方共同缺口说明");
    expect(rowReferences).toHaveLength(3);
    expect(rowReferences[0]).toHaveAttribute("title", sharedSentence);
    // 非重复说明保持原样。
    expect(screen.getByTestId("livermore-rule-readiness")).toHaveTextContent(
      "Risk and exit output is available.",
    );
  });

  it("collapses the constant per-row market state into one batch line", () => {
    const model = makeModel();
    model.factorScreenCandidates = {
      formulaVersion: "rv_factor_screen_candidates_v4",
      marketState: "WARM",
      coverageNote: "本次多因子评分池为 646 只，仅在该评分池内生成观察候选",
      items: [
        {
          rank: 1,
          stockCode: "600000.SH",
          stockName: "Bank Alpha",
          sectorName: "银行",
          score: "0.812",
        },
        {
          rank: 2,
          stockCode: "600001.SH",
          stockName: "Bank Beta",
          sectorName: "银行",
          score: "0.788",
        },
      ],
    };

    render(
      <LivermoreStrategyPanel
        model={model}
        isLoading={false}
        isError={false}
        onRetry={vi.fn()}
      />,
    );

    const block = screen.getByTestId("livermore-factor-screen-candidates");
    // 整列同值的 WARM 档位收敛为头部一句，行内不再重复。
    expect(within(block).getAllByText(/WARM/)).toHaveLength(1);
    expect(block).toHaveTextContent("本批 2 只均为 WARM 档");
    expect(block).toHaveTextContent("因子得分 0.812");
    expect(block).not.toHaveTextContent("factor score");
    // 表名开头的口径版本收进 title，不占正文。
    expect(block).not.toHaveTextContent("rv_factor_screen_candidates_v4");
    // 个股候选块（HOT）同样只在头部发声一次。
    const candidates = screen.getByTestId("livermore-stock-candidates");
    expect(within(candidates).getAllByText(/HOT/)).toHaveLength(1);
    expect(candidates).toHaveTextContent("本批 1 只均为 HOT 档");
  });

  it("renders market gate macro overlay disclosure on the gate card", () => {
    render(
      <LivermoreStrategyPanel
        model={{
          ...makeModel(),
          marketGate: {
            ...makeModel().marketGate,
            macroDisclosure: {
              adjustmentLabel: "宏观调节 0.75→0.25",
              cycleStateLabel: "衰退",
              statusMarker: null,
              lagLabel: null,
            },
          },
        }}
        isLoading={false}
        isError={false}
        onRetry={vi.fn()}
      />,
    );

    const disclosure = screen.getByTestId("livermore-market-gate-macro-disclosure");
    expect(disclosure).toHaveTextContent("宏观调节 0.75→0.25");
    expect(disclosure).toHaveTextContent("衰退");
    expect(screen.queryByText("宏观背景缺失")).not.toBeInTheDocument();
  });
});
