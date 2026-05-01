import { describe, expect, it } from "vitest";

import type {
  ApiEnvelope,
  LivermoreStrategyPayload,
  ResultMeta,
} from "../../../api/contracts";
import { buildLivermoreStrategyModel } from "./livermoreStrategyModel";

function makeMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_livermore_test",
    basis: "analytical",
    result_kind: "market_data.livermore",
    formal_use_allowed: false,
    source_version: "sv_livermore_test",
    vendor_version: "vv_livermore_test",
    rule_version: "rv_livermore_test",
    cache_version: "cv_livermore_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-29T09:00:00Z",
    ...overrides,
  };
}

function makePayload(
  overrides: Partial<LivermoreStrategyPayload> = {},
): LivermoreStrategyPayload {
  return {
    as_of_date: "2026-04-29",
    requested_as_of_date: "2026-04-29",
    strategy_name: "Livermore A股趋势门控",
    basis: "analytical",
    market_gate: {
      state: "WARM",
      exposure: 0.4,
      passed_conditions: 2,
      available_conditions: 2,
      required_conditions: 4,
      conditions: [
        {
          key: "csi300_close_gt_ma60",
          label: "CSI300 close > MA60",
          status: "pass",
          evidence: "收盘价 3950，高于 MA60 3920。",
          source_series_id: "CA.CSI300",
        },
        {
          key: "csi300_ma20_gt_ma60",
          label: "CSI300 MA20 > MA60",
          status: "pass",
          evidence: "MA20 3940，高于 MA60 3920。",
          source_series_id: "CA.CSI300",
        },
        {
          key: "breadth_5d_positive",
          label: "5-day breadth > 0",
          status: "missing",
          evidence: "Breadth inputs are not landed for the Phase 1 slice.",
          source_series_id: null,
        },
        {
          key: "limit_up_quality_positive",
          label: "Limit-up seal/break quality positive",
          status: "missing",
          evidence: "Limit-up quality inputs are not landed for the Phase 1 slice.",
          source_series_id: null,
        },
      ],
    },
    rule_readiness: [
      {
        key: "market_gate",
        title: "Market gate",
        status: "partial",
        summary: "Trend-only market gate is available; breadth and limit-up quality remain missing.",
        required_inputs: ["broad_index_history", "breadth", "limit_up_quality"],
        missing_inputs: ["breadth", "limit_up_quality"],
      },
      {
        key: "sector_rank",
        title: "Sector ranking",
        status: "missing",
        summary: "Sector membership and sector-strength inputs are not landed yet.",
        required_inputs: ["sector_membership", "sector_strength"],
        missing_inputs: ["sector_membership", "sector_strength"],
      },
      {
        key: "stock_pivot",
        title: "Stock pivot filters",
        status: "blocked",
        summary: "Stock pivot output is blocked until sector rank and stock-universe inputs land.",
        required_inputs: ["stock_ohlcv", "stock_status", "sector_rank"],
        missing_inputs: ["stock_ohlcv", "stock_status", "sector_rank"],
      },
      {
        key: "risk_exit",
        title: "Risk and exit rules",
        status: "blocked",
        summary:
          "The defended-bundle 10EMA invalidation exit kernel is implemented, but output stays blocked until position, entry-cost, bars-since-entry, and close-history inputs land.",
        required_inputs: ["positions", "entry_cost", "bars_since_entry"],
        missing_inputs: ["positions", "entry_cost", "bars_since_entry"],
      },
    ],
    diagnostics: [
      {
        severity: "warning",
        code: "LIVERMORE_BREADTH_MISSING",
        message: "Breadth inputs are unavailable; the market gate is capped at the trend-only slice.",
        input_family: "breadth",
      },
      {
        severity: "warning",
        code: "LIVERMORE_LIMIT_UP_QUALITY_MISSING",
        message: "Limit-up quality inputs are unavailable; the market gate is capped at the trend-only slice.",
        input_family: "limit_up_quality",
      },
      {
        severity: "warning",
        code: "LIVERMORE_SECTOR_INPUTS_MISSING",
        message: "Sector membership and sector-strength inputs are unavailable.",
        input_family: "sector_strength",
      },
      {
        severity: "warning",
        code: "LIVERMORE_STOCK_INPUTS_MISSING",
        message: "Stock-universe inputs are unavailable, so no candidates are produced.",
        input_family: "stock_universe",
      },
      {
        severity: "warning",
        code: "LIVERMORE_RISK_INPUTS_MISSING",
        message:
          "The defended-bundle 10EMA invalidation MVP is implemented, but position, entry-cost, bars-since-entry, and close-history inputs are unavailable, so risk/exit output remains blocked.",
        input_family: "position_risk",
      },
    ],
    data_gaps: [
      {
        input_family: "breadth",
        status: "missing",
        evidence: "5-day breadth input family is not landed in DuckDB for this slice.",
      },
      {
        input_family: "limit_up_quality",
        status: "missing",
        evidence: "Limit-up seal/break quality input family is not landed in DuckDB for this slice.",
      },
      {
        input_family: "sector_strength",
        status: "missing",
        evidence: "Sector membership and ranking inputs are not landed in DuckDB for this slice.",
      },
      {
        input_family: "stock_universe",
        status: "missing",
        evidence: "Stock OHLCV, status, and candidate-filter inputs are not landed in DuckDB for this slice.",
      },
      {
        input_family: "position_risk",
        status: "missing",
        evidence:
          "Position, entry-cost, bars-since-entry, and close-history inputs are not landed in DuckDB for the defended-bundle 10EMA invalidation MVP.",
      },
    ],
    supported_outputs: ["market_gate"],
    unsupported_outputs: [
      {
        key: "sector_rank",
        reason: "Sector membership and sector-strength inputs are not landed yet.",
      },
      {
        key: "stock_candidates",
        reason: "Stock-level OHLCV, status, and candidate filters are not landed yet.",
      },
      {
        key: "risk_exit",
        reason:
          "The defended-bundle 10EMA invalidation MVP remains blocked until position, entry-cost, bars-since-entry, and close-history inputs land.",
      },
    ],
    ...overrides,
  };
}

function makeEnvelope(
  payloadOverrides: Partial<LivermoreStrategyPayload> = {},
  metaOverrides: Partial<ResultMeta> = {},
): ApiEnvelope<LivermoreStrategyPayload> {
  return {
    result_meta: makeMeta(metaOverrides),
    result: makePayload(payloadOverrides),
  };
}

describe("livermoreStrategyModel", () => {
  it("maps the backend contract into a display model without recalculating rules", () => {
    const model = buildLivermoreStrategyModel({
      envelope: makeEnvelope(),
    });

    expect(model.strategyName).toBe("Livermore A股趋势门控");
    expect(model.asOfDate).toBe("2026-04-29");
    expect(model.requestedAsOfDate).toBe("2026-04-29");
    expect(model.marketGate.state).toBe("WARM");
    expect(model.marketGate.exposureDisplay).toBe("0.4");
    expect(model.marketGate.passedConditions).toBe(2);
    expect(model.marketGate.availableConditions).toBe(2);
    expect(model.marketGate.conditions.map((condition) => condition.status)).toEqual([
      "pass",
      "pass",
      "missing",
      "missing",
    ]);
    expect(model.ruleBlocks.find((block) => block.key === "market_gate")?.status).toBe("partial");
    expect(model.ruleBlocks.find((block) => block.key === "sector_rank")?.status).toBe("missing");
    expect(model.ruleBlocks.find((block) => block.key === "stock_pivot")?.status).toBe("blocked");
    expect(model.ruleBlocks.find((block) => block.key === "risk_exit")?.status).toBe("blocked");
    expect(model.diagnostics[0]).toMatchObject({
      severity: "warning",
      code: "LIVERMORE_BREADTH_MISSING",
    });
    expect(model.dataGaps.map((gap) => gap.inputFamily)).toEqual([
      "breadth",
      "limit_up_quality",
      "sector_strength",
      "stock_universe",
      "position_risk",
    ]);
    expect(model.unsupportedOutputs).toEqual([
      {
        key: "sector_rank",
        label: "板块排序",
        reason: "Sector membership and sector-strength inputs are not landed yet.",
      },
      {
        key: "stock_candidates",
        label: "个股候选",
        reason: "Stock-level OHLCV, status, and candidate filters are not landed yet.",
      },
      {
        key: "risk_exit",
        label: "风险退出",
        reason:
          "The defended-bundle 10EMA invalidation MVP remains blocked until position, entry-cost, bars-since-entry, and close-history inputs land.",
      },
    ]);
  });

  it("surfaces stale and fallback governance notes from payload metadata", () => {
    const model = buildLivermoreStrategyModel({
      envelope: makeEnvelope(
        {
          as_of_date: "2026-04-28",
          requested_as_of_date: "2026-04-29",
          market_gate: {
            ...makePayload().market_gate,
            state: "STALE",
          },
        },
        {
          quality_flag: "stale",
          fallback_mode: "latest_snapshot",
        },
      ),
    });

    expect(model.statusNotes).toContain("请求日期 2026-04-29，解析结果日期 2026-04-28。");
    expect(model.statusNotes).toContain("当前结果带有陈旧数据标记。");
    expect(model.statusNotes).toContain("当前结果使用最新快照降级。");
  });

  it("maps emitted sector rank, stock candidates, and risk exit for display", () => {
    const envelope = makeEnvelope({
      supported_outputs: ["market_gate", "sector_rank", "stock_candidates", "risk_exit"],
      unsupported_outputs: [],
      rule_readiness: [
        {
          key: "market_gate",
          title: "Market gate",
          status: "partial",
          summary: "Trend-only market gate is available; breadth and limit-up quality remain missing.",
          required_inputs: ["broad_index_history", "breadth", "limit_up_quality"],
          missing_inputs: ["breadth", "limit_up_quality"],
        },
        {
          key: "sector_rank",
          title: "Sector ranking",
          status: "ready",
          summary: "Sector ranking is available from landed Choice sector inputs.",
          required_inputs: ["sector_membership", "sector_strength"],
          missing_inputs: [],
        },
        {
          key: "stock_pivot",
          title: "Stock pivot filters",
          status: "ready",
          summary: "Stock pivot candidate screening is available for landed Choice stock inputs.",
          required_inputs: [
            "stock_universe",
            "stock_ohlcv",
            "stock_status",
            "limit_up_quality",
            "sector_rank",
            "market_gate",
          ],
          missing_inputs: [],
        },
        {
          key: "risk_exit",
          title: "Risk and exit rules",
          status: "ready",
          summary: "Risk and exit output is available from landed position snapshots and close history.",
          required_inputs: ["positions", "entry_cost", "bars_since_entry", "close_history"],
          missing_inputs: [],
        },
      ],
      diagnostics: [
        {
          severity: "warning",
          code: "LIVERMORE_SECTOR_RANK_PROVISIONAL_FORMULA",
          message: "Sector rank currently uses the provisional percentile formula over pctchange, turn, and amplitude.",
          input_family: "sector_strength",
        },
      ],
      data_gaps: [
        {
          input_family: "breadth",
          status: "missing",
          evidence: "5-day breadth input family is not landed in DuckDB for this slice.",
        },
        {
          input_family: "limit_up_quality",
          status: "missing",
          evidence: "Choice limit-up quality catalog is confirmed, but landed inputs are unavailable; the market gate is capped at the trend-only slice.",
        },
        {
          input_family: "position_risk",
          status: "missing",
          evidence:
            "Position, entry-cost, bars-since-entry, and close-history inputs are not landed in DuckDB for the defended-bundle 10EMA invalidation MVP.",
        },
      ],
      sector_rank: {
        as_of_date: "2026-04-29",
        formula_version: "rv_livermore_sector_rank_provisional_v1",
        is_provisional: true,
        sector_count: 3,
        excluded_constituent_count: 0,
        excluded_sector_count: 0,
        items: [
          {
            rank: 1,
            sector_code: "801001",
            sector_name: "AI",
            score: 1,
            avg_pctchange: 4.8,
            avg_turn: 3,
            avg_amplitude: 3.5,
            constituent_count: 12,
          },
        ],
      } as unknown as never,
      stock_candidates: {
        as_of_date: "2026-04-29",
        formula_version: "rv_livermore_stock_candidates_bundle_v1",
        market_state: "WARM",
        input_stock_count: 4,
        candidate_count: 2,
        excluded_stock_count: 2,
        insufficient_history_count: 0,
        items: [
          {
            rank: 1,
            stock_code: "000001.SZ",
            stock_name: "Alpha",
            sector_code: "801001",
            sector_name: "AI",
            sector_rank: 1,
            close: 21.9,
            breakout_level: 21.8,
            ma20: 21.05,
            ma60: 19.05,
            ma120: 16.05,
            close_strength: 0.833333,
            gap_norm: -0.114679,
            abnormal_turnover: 1.386294,
          },
        ],
      } as unknown as never,
      risk_exit: {
        as_of_date: "2026-04-29",
        formula_version: "rv_livermore_risk_exit_ema10_mvp_v1",
        position_count: 2,
        signal_count: 1,
        excluded_position_count: 0,
        insufficient_history_count: 0,
        items: [
          {
            stock_code: "000001.SZ",
            stock_name: "Alpha",
            reason: "2d_below_ema10",
            entry_cost: 10.5,
            bars_since_entry: 6,
            latest_close: 9.1,
            latest_ema10: 10.2,
            prior_close: 9.8,
            prior_ema10: 10.4,
          },
        ],
      } as unknown as never,
    } as Partial<LivermoreStrategyPayload>);

    const model = buildLivermoreStrategyModel({
      envelope,
    }) as unknown as {
      sectorRank: { items: Array<{ sectorCode: string }> } | null;
      stockCandidates: { items: Array<{ stockCode: string }> } | null;
      riskExit: { items: Array<{ stockCode: string; reason: string }> } | null;
      supportedOutputs: Array<{ key: string }>;
    };

    expect(model.supportedOutputs.map((item) => item.key)).toEqual([
      "market_gate",
      "sector_rank",
      "stock_candidates",
      "risk_exit",
    ]);
    expect(model.sectorRank?.items[0]?.sectorCode).toBe("801001");
    expect(model.stockCandidates?.items[0]?.stockCode).toBe("000001.SZ");
    expect(model.riskExit?.items[0]).toMatchObject({
      stockCode: "000001.SZ",
      reason: "2d_below_ema10",
    });
  });
});
