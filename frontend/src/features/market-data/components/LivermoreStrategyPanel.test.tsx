import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
      exposureDisplay: "0.8",
      passedConditions: 3,
      availableConditions: 4,
      requiredConditions: 4,
      conditions: [],
    },
    ruleBlocks: [],
    diagnostics: [],
    dataGaps: [
      {
        inputFamily: "position_risk",
        status: "missing",
        statusLabel: "缺失",
        evidence: "No position snapshot is loaded.",
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
});
