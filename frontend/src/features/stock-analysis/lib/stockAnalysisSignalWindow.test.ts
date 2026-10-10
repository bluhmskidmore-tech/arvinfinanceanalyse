import { describe, expect, it } from "vitest";

import type {
  LivermoreStrategyScorePayload,
  LivermoreStrategyScoreRow,
} from "../../../api/contracts";
import {
  attachCandidateSignalWindow,
  buildCandidateSignalWindow,
} from "./stockAnalysisSignalWindowModel";

function horizonStats(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    available_count: 0,
    missing_count: 0,
    positive_count: 0,
    non_positive_count: 0,
    avg_return: null,
    median_return: null,
    win_rate: null,
    ...overrides,
  };
}

function scoreRow(overrides: Partial<LivermoreStrategyScoreRow> = {}): LivermoreStrategyScoreRow {
  return {
    market_state: "HOT",
    signal_kind: "theme_breakout",
    strategy_label: "题材突破",
    sample_status: "sufficient",
    priority_score: 106.54,
    priority_rank: null,
    priority_label: "降权观察",
    reason: "T+5 成熟样本 30/30。",
    stats: {
      return_1d: horizonStats({ available_count: 30, win_rate: 0.9, median_return: 0.0687 }),
      return_5d: horizonStats({ available_count: 30, win_rate: 0.9, median_return: 0.1588 }),
      return_10d: horizonStats({ available_count: 30, win_rate: 0.7667, median_return: 0.1365 }),
      return_20d: horizonStats({ available_count: 30, win_rate: 0.2333, median_return: -0.1124 }),
    },
    ...overrides,
  } as LivermoreStrategyScoreRow;
}

function scorePayload(
  rows: LivermoreStrategyScoreRow[],
  overrides: Partial<LivermoreStrategyScorePayload> = {},
): LivermoreStrategyScorePayload {
  return {
    as_of_date: "2026-08-24",
    snapshot_from: "2026-02-25",
    snapshot_to: "2026-08-24",
    primary_horizon: "return_5d",
    min_sample: 30,
    current_market_state: "HOT",
    rows,
    current_market_state_rows: rows,
    ...overrides,
  } as LivermoreStrategyScorePayload;
}

describe("buildCandidateSignalWindow", () => {
  it("surfaces the T+5 window and warns when the T+20 median turns negative", () => {
    const signalWindow = buildCandidateSignalWindow(scorePayload([scoreRow()]), "theme_breakout");

    expect(signalWindow).toMatchObject({
      signalKind: "theme_breakout",
      marketState: "HOT",
      horizonLabel: "T+5",
      sampleLabel: "样本 30",
      winRateLabel: "T+5 胜率 90.0%",
      medianLabel: "T+5 中位 +15.88%",
      longHorizonLabel: "T+20 中位 -11.24%",
      tone: "warning",
    });
    expect(signalWindow?.guidance).toBe(
      "建议观察窗口 T+5；该池历史 T+20 中位为负，不作持有依据。",
    );
  });

  it("keeps a positive tone and the neutral guidance when T+20 does not turn negative", () => {
    const row = scoreRow({
      stats: {
        return_1d: horizonStats({ available_count: 12, win_rate: 0.6, median_return: 0.01 }),
        return_5d: horizonStats({ available_count: 12, win_rate: 0.6, median_return: 0.03 }),
        return_10d: horizonStats({ available_count: 12, win_rate: 0.6, median_return: 0.04 }),
        return_20d: horizonStats({ available_count: 12, win_rate: 0.6, median_return: 0.05 }),
      },
    } as Partial<LivermoreStrategyScoreRow>);

    const signalWindow = buildCandidateSignalWindow(scorePayload([row]), "theme_breakout");

    expect(signalWindow?.tone).toBe("positive");
    expect(signalWindow?.guidance).toBe("建议观察窗口 T+5；超过该窗口的持有需另行验证。");
  });

  it("maps pool keys onto the backend signal_kind naming", () => {
    const rows = [
      scoreRow({ signal_kind: "stock_candidate" }),
      scoreRow({ signal_kind: "factor_screen" }),
    ];
    const payload = scorePayload(rows);

    expect(buildCandidateSignalWindow(payload, "stock_candidates")?.signalKind).toBe("stock_candidate");
    expect(buildCandidateSignalWindow(payload, "factor_screen_candidates")?.signalKind).toBe(
      "factor_screen",
    );
    // 首屏 workbench 队列无来源池统计，不构造披露。
    expect(buildCandidateSignalWindow(payload, "workbench_review_queue")).toBeNull();
  });

  it("falls back to the market-state row when current_market_state_rows is empty", () => {
    const payload = scorePayload([scoreRow({ market_state: "HOT" })], {
      current_market_state_rows: [],
      current_market_state: "HOT",
    });

    expect(buildCandidateSignalWindow(payload, "theme_breakout")?.marketState).toBe("HOT");
  });

  it("returns null when the pool has no matching row or no usable T+5 sample", () => {
    expect(buildCandidateSignalWindow(scorePayload([scoreRow()]), "hybrid_fusion")).toBeNull();
    expect(buildCandidateSignalWindow(null, "theme_breakout")).toBeNull();

    const emptySample = scoreRow({
      stats: {
        return_1d: horizonStats(),
        return_5d: horizonStats(),
        return_10d: horizonStats(),
        return_20d: horizonStats(),
      },
    } as Partial<LivermoreStrategyScoreRow>);
    expect(buildCandidateSignalWindow(scorePayload([emptySample]), "theme_breakout")).toBeNull();
  });
});

describe("attachCandidateSignalWindow", () => {
  it("injects the window onto candidates of the matching pool and leaves others untouched", () => {
    const queue = [
      { stockCode: "300888.SZ", sourcePool: "theme_breakout" as const },
      { stockCode: "000009.SZ", sourcePool: "hybrid_fusion" as const },
    ];

    const enriched = attachCandidateSignalWindow(queue, scorePayload([scoreRow()]));

    expect(enriched[0]).toHaveProperty("signalWindow");
    expect(enriched[1]).not.toHaveProperty("signalWindow");
  });

  it("returns the queue unchanged when the score payload is missing (legacy response)", () => {
    const queue = [{ stockCode: "300888.SZ", sourcePool: "theme_breakout" as const }];
    expect(attachCandidateSignalWindow(queue, null)).toBe(queue);
  });
});
