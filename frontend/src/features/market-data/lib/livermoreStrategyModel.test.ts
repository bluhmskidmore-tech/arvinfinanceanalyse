import { describe, expect, it } from "vitest";

import { EM_DASH } from "../../../utils/format";
import type {
  ApiEnvelope,
  LivermoreModuleState,
  LivermoreOutputKey,
  LivermoreStrategyPayload,
  ResultMeta,
} from "../../../api/contracts";
import {
  buildLivermoreStrategyModel,
  buildMarketGateMacroDisclosure,
  translateLivermoreEvidence,
} from "./livermoreStrategyModel";

const LIVERMORE_OUTPUT_KEYS: LivermoreOutputKey[] = [
  "market_gate",
  "sector_rank",
  "stock_candidates",
  "mean_reversion_candidates",
  "factor_screen_candidates",
  "theme_breakout",
  "hybrid_fusion",
  "risk_exit",
];

function readyModuleStates(asOfDate = "2026-04-29"): LivermoreModuleState[] {
  return LIVERMORE_OUTPUT_KEYS.map((key) => ({
    key,
    state: "ready",
    render_mode: "primary",
    source_date: asOfDate,
    lag_days: 0,
    threshold_days: null,
    reasons: [],
    evidence_scope: "primary",
    excludes_from_primary: false,
  }));
}

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
        summary: "Risk and exit output is blocked until position and entry-cost inputs land.",
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
        message: "Position and entry-cost inputs are unavailable, so risk/exit output is blocked.",
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
        evidence: "Position and entry-cost inputs are not landed in DuckDB for this slice.",
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
        reason: "Position and entry-cost inputs are not landed yet.",
      },
    ],
    ...overrides,
    module_states: overrides.module_states ?? readyModuleStates(),
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
    expect(model.marketGate.exposureDisplay).toBe("40%");
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
        reason: "Position and entry-cost inputs are not landed yet.",
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

  it("surfaces backend input freshness fields and degraded quality notes", () => {
    const degradedMessage = "breadth DR007 data lagged 8 days (stale), signal quality degraded";
    const model = buildLivermoreStrategyModel({
      envelope: makeEnvelope(
        {
          diagnostics: [
            {
              severity: "warning",
              code: "LIVERMORE_INPUT_FRESHNESS_DEGRADED",
              message: degradedMessage,
              input_family: "breadth",
            },
          ],
          data_gaps: [
            {
              input_family: "breadth",
              status: "stale",
              evidence: "Breadth input is stale.",
              input: "DR007",
              business_date: "2026-04-21",
              age_days: 8,
              tier: "stale",
            },
          ],
        },
        { quality_flag: "warning" },
      ),
    });

    expect(model.statusNotes).toContain(degradedMessage);
    expect(model.dataGaps[0]).toMatchObject({
      inputFamily: "breadth",
      input: "DR007",
      businessDate: "2026-04-21",
      ageDays: 8,
      tier: "stale",
      freshnessLabel: "输入 DR007 · 日期 2026-04-21 · T+8 · stale",
    });
  });

  it("maps data gap status ready to 就绪", () => {
    const model = buildLivermoreStrategyModel({
      envelope: makeEnvelope({
        data_gaps: [
          { input_family: "breadth", status: "ready", evidence: "landed" },
          ...makePayload().data_gaps.slice(1),
        ],
      }),
    });
    expect(model.dataGaps.find((g) => g.inputFamily === "breadth")?.statusLabel).toBe("就绪");
  });
  it("renders a dash instead of crashing when a risk-exit row has no entry cost", () => {
    const model = buildLivermoreStrategyModel({
      envelope: makeEnvelope({
        supported_outputs: ["market_gate", "risk_exit"],
        risk_exit: {
          as_of_date: "2026-04-29",
          formula_version: "rv_livermore_risk_exit_v1",
          position_count: 2,
          signal_count: 2,
          excluded_position_count: 0,
          insufficient_history_count: 0,
          items: [
            {
              stock_code: "000001.SZ",
              stock_name: "Alpha",
              reason: "2d_below_ema10_with_volume",
              entry_cost: null,
              entry_cost_available: false,
              bars_since_entry: 6,
              latest_close: 9.1,
              latest_ema10: 10.2,
              prior_close: 9.4,
              prior_ema10: 10.3,
            },
            {
              stock_code: "000002.SZ",
              stock_name: "Beta",
              reason: "2d_below_ema10_with_volume",
              entry_cost: 10.5,
              entry_cost_available: true,
              bars_since_entry: 6,
              latest_close: 9.1,
              latest_ema10: 10.2,
              prior_close: 9.4,
              prior_ema10: 10.3,
            },
          ],
        },
      }),
    });

    expect(model.riskExit?.items.map((item) => item.entryCost)).toEqual([EM_DASH, "10.500"]);
  });

  it("derives stock-candidate observation levels from the backend candidate fields", () => {
    const model = buildLivermoreStrategyModel({
      envelope: makeEnvelope({
        supported_outputs: ["market_gate", "sector_rank", "stock_candidates"],
        stock_candidates: {
          as_of_date: "2026-04-30",
          formula_version: "rv_livermore_stock_candidates_bundle_v1",
          market_state: "HOT",
          input_stock_count: 1,
          candidate_count: 1,
          excluded_stock_count: 0,
          insufficient_history_count: 0,
          items: [
            {
              rank: 1,
              stock_code: "000001.SZ",
              stock_name: "Alpha",
              sector_code: "S270000",
              sector_name: "电子",
              sector_rank: 1,
              close: 22,
              breakout_level: 21.8,
              ma20: 20.5,
              ma60: 19.8,
              ma120: 18.2,
              close_strength: 0.83,
              gap_norm: -0.12,
              abnormal_turnover: 1.39,
            },
          ],
        },
      }),
    });

    const candidate = model.stockCandidates?.items[0] as Record<string, unknown> | undefined;
    expect(candidate).toMatchObject({
      close: "22.000",
      entryTrigger: "21.800",
      pullbackWatch: "20.500",
      defenseLine: "19.800",
    });
  });

  it("surfaces the fundamental overlay factor_missing_count when the backend reports it", () => {
    const model = buildLivermoreStrategyModel({
      envelope: makeEnvelope({
        supported_outputs: ["market_gate", "sector_rank", "stock_candidates"],
        stock_candidates: {
          as_of_date: "2026-04-30",
          formula_version: "rv_livermore_stock_candidates_bundle_v7",
          market_state: "HOT",
          input_stock_count: 1,
          candidate_count: 1,
          excluded_stock_count: 0,
          insufficient_history_count: 0,
          fundamental_overlay: {
            status: "applied",
            input_candidate_count: 3,
            valid_factor_count: 1,
            selected_factor_count: 1,
            top_fraction: 0.5,
            factor_missing_count: 2,
          },
          items: [
            {
              rank: 1,
              stock_code: "000001.SZ",
              stock_name: "Alpha",
              sector_code: "S270000",
              sector_name: "电子",
              sector_rank: 1,
              close: 22,
              breakout_level: 21.8,
              ma20: 20.5,
              ma60: 19.8,
              ma120: 18.2,
              close_strength: 0.83,
              gap_norm: -0.12,
              abnormal_turnover: 1.39,
            },
          ],
        },
      }),
    });

    expect(model.stockCandidates?.factorMissingCount).toBe(2);
  });

  it("defaults the fundamental overlay factor_missing_count to null for legacy payloads", () => {
    const model = buildLivermoreStrategyModel({
      envelope: makeEnvelope({
        supported_outputs: ["market_gate", "sector_rank", "stock_candidates"],
        stock_candidates: {
          as_of_date: "2026-04-30",
          formula_version: "rv_livermore_stock_candidates_bundle_v1",
          market_state: "HOT",
          input_stock_count: 1,
          candidate_count: 1,
          excluded_stock_count: 0,
          insufficient_history_count: 0,
          items: [],
        },
      }),
    });

    expect(model.stockCandidates?.factorMissingCount).toBeNull();
  });

  it("maps the risk_budget position_size_hint onto candidates when the backend provides it", () => {
    const model = buildLivermoreStrategyModel({
      envelope: makeEnvelope({
        supported_outputs: ["market_gate", "sector_rank", "stock_candidates"],
        stock_candidates: {
          as_of_date: "2026-04-30",
          formula_version: "rv_livermore_stock_candidates_bundle_v7",
          market_state: "HOT",
          input_stock_count: 2,
          candidate_count: 2,
          excluded_stock_count: 0,
          insufficient_history_count: 0,
          items: [
            {
              rank: 1,
              stock_code: "000001.SZ",
              stock_name: "Alpha",
              sector_code: "S270000",
              sector_name: "电子",
              sector_rank: 1,
              close: 22,
              breakout_level: 21.8,
              ma20: 20.5,
              ma60: 19.8,
              ma120: 18.2,
              close_strength: 0.83,
              gap_norm: -0.12,
              abnormal_turnover: 1.39,
            },
            {
              rank: 2,
              stock_code: "600000.SH",
              stock_name: "Beta",
              sector_code: "S480000",
              sector_name: "银行",
              sector_rank: 2,
              close: 10,
              breakout_level: 9.8,
              ma20: 9.5,
              ma60: 9.2,
              ma120: 8.9,
              close_strength: 0.91,
              gap_norm: 0.05,
              abnormal_turnover: 1.5,
            },
          ],
          position_size_hint: {
            policy_version: "sizing_rb_v1_stock_candidate",
            sizing_mode: "risk_budget",
            signal_kind: "stock_candidate",
            risk_per_trade: 0.005,
            single_name_cap: 0.25,
            fallback_stop_distance_pct: 0.08,
            stop_basis: "ema10_stop_ref",
            items: [
              {
                stock_code: "000001.SZ",
                raw_weight: 0.125,
                stop_distance_pct: 0.04,
                stop_basis: "ema10_stop_ref",
                capped: false,
              },
              {
                stock_code: "600000.SH",
                raw_weight: 0.0625,
                stop_distance_pct: 0.08,
                stop_basis: "fallback",
                capped: false,
              },
            ],
            stop_ref_fallback_count: 1,
            stop_ref_missing_ratio: 0.5,
            coverage_degraded: true,
            coverage_warning: "ema10 stop_ref 缺失率超过 10%，建议仓位提示已降级。",
            gate_exposure_note: "raw_weight 为单票权重上限建议；串联 gate 敞口截断由引擎执行。",
            equal_weight_shadow_note: "等权 shadow 对照仍在回测输出。",
          },
        },
      }),
    });

    expect(model.stockCandidates?.positionSizeHint).toEqual({
      policyVersion: "sizing_rb_v1_stock_candidate",
      coverageDegraded: true,
      coverageWarning: "ema10 stop_ref 缺失率超过 10%，建议仓位提示已降级。",
      gateExposureNote: "raw_weight 为单票权重上限建议；串联 gate 敞口截断由引擎执行。",
      shadowNote: "等权 shadow 对照仍在回测输出。",
    });
    expect(model.stockCandidates?.items[0]?.sizeHint).toBe("≤ 12.5% · EMA10止损");
    expect(model.stockCandidates?.items[1]?.sizeHint).toBe("≤ 6.3% · fallback止损");
  });

  it("marks capped hints and leaves candidates without a hint entry as null", () => {
    const model = buildLivermoreStrategyModel({
      envelope: makeEnvelope({
        supported_outputs: ["market_gate", "sector_rank", "stock_candidates"],
        stock_candidates: {
          as_of_date: "2026-04-30",
          formula_version: "rv_livermore_stock_candidates_bundle_v7",
          market_state: "HOT",
          input_stock_count: 2,
          candidate_count: 2,
          excluded_stock_count: 0,
          insufficient_history_count: 0,
          items: [
            {
              rank: 1,
              stock_code: "000001.SZ",
              stock_name: "Alpha",
              sector_code: "S270000",
              sector_name: "电子",
              sector_rank: 1,
              close: 22,
              breakout_level: 21.8,
              ma20: 20.5,
              ma60: 19.8,
              ma120: 18.2,
              close_strength: 0.83,
              gap_norm: -0.12,
              abnormal_turnover: 1.39,
            },
            {
              rank: 2,
              stock_code: "600000.SH",
              stock_name: "Beta",
              sector_code: "S480000",
              sector_name: "银行",
              sector_rank: 2,
              close: 10,
              breakout_level: 9.8,
              ma20: 9.5,
              ma60: 9.2,
              ma120: 8.9,
              close_strength: 0.91,
              gap_norm: 0.05,
              abnormal_turnover: 1.5,
            },
          ],
          position_size_hint: {
            policy_version: "sizing_rb_v1_stock_candidate",
            sizing_mode: "risk_budget",
            signal_kind: "stock_candidate",
            risk_per_trade: 0.005,
            single_name_cap: 0.25,
            fallback_stop_distance_pct: 0.08,
            stop_basis: "ema10_stop_ref",
            items: [
              {
                stock_code: "000001.SZ",
                raw_weight: 0.25,
                stop_distance_pct: 0.01,
                stop_basis: "ema10_stop_ref",
                capped: true,
              },
            ],
            stop_ref_fallback_count: 0,
            stop_ref_missing_ratio: 0,
            coverage_degraded: false,
            coverage_warning: null,
            gate_exposure_note: "raw_weight 为单票权重上限建议；串联 gate 敞口截断由引擎执行。",
            equal_weight_shadow_note: "等权 shadow 对照仍在回测输出。",
          },
        },
      }),
    });

    expect(model.stockCandidates?.positionSizeHint?.coverageDegraded).toBe(false);
    expect(model.stockCandidates?.positionSizeHint?.coverageWarning).toBeNull();
    expect(model.stockCandidates?.items[0]?.sizeHint).toBe(
      "≤ 25.0% · EMA10止损 · 已触单票上限",
    );
    expect(model.stockCandidates?.items[1]?.sizeHint).toBeNull();
  });

  it("keeps position_size_hint null for legacy stock_candidates payloads without the block", () => {
    const model = buildLivermoreStrategyModel({
      envelope: makeEnvelope({
        supported_outputs: ["market_gate", "sector_rank", "stock_candidates"],
        stock_candidates: {
          as_of_date: "2026-04-30",
          formula_version: "rv_livermore_stock_candidates_bundle_v1",
          market_state: "HOT",
          input_stock_count: 1,
          candidate_count: 1,
          excluded_stock_count: 0,
          insufficient_history_count: 0,
          items: [
            {
              rank: 1,
              stock_code: "000001.SZ",
              stock_name: "Alpha",
              sector_code: "S270000",
              sector_name: "电子",
              sector_rank: 1,
              close: 22,
              breakout_level: 21.8,
              ma20: 20.5,
              ma60: 19.8,
              ma120: 18.2,
              close_strength: 0.83,
              gap_norm: -0.12,
              abnormal_turnover: 1.39,
            },
          ],
        },
      }),
    });

    expect(model.stockCandidates?.positionSizeHint).toBeNull();
    expect(model.stockCandidates?.items[0]?.sizeHint).toBeNull();
  });

  it("derives entryCostAvailable for risk-exit items, defaulting to true for legacy payloads without the flag", () => {
    const modelWithMissingCost = buildLivermoreStrategyModel({
      envelope: makeEnvelope({
        supported_outputs: ["market_gate", "risk_exit"],
        risk_exit: {
          as_of_date: "2026-04-30",
          formula_version: "rv_livermore_risk_exit_ema10_volume_obsfallback_v3",
          position_count: 1,
          signal_count: 1,
          excluded_position_count: 0,
          insufficient_history_count: 0,
          items: [
            {
              stock_code: "000777.SZ",
              stock_name: "Watch Alpha",
              reason: "2d_below_ema10_with_volume",
              entry_cost: null,
              entry_cost_available: false,
              bars_since_entry: 4,
              latest_close: 19.8,
              latest_ema10: 20.1,
              prior_close: 20.4,
              prior_ema10: 20,
            },
          ],
        },
      }),
    });
    expect(modelWithMissingCost.riskExit?.items[0]).toMatchObject({
      entryCost: EM_DASH,
      entryCostAvailable: false,
    });

    const legacyModel = buildLivermoreStrategyModel({
      envelope: makeEnvelope({
        supported_outputs: ["market_gate", "risk_exit"],
        risk_exit: {
          as_of_date: "2026-04-30",
          formula_version: "rv_livermore_risk_exit_ema10_mvp_v1",
          position_count: 1,
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
        },
      }),
    });
    expect(legacyModel.riskExit?.items[0]).toMatchObject({
      entryCost: "10.500",
      entryCostAvailable: true,
    });
  });

  it("returns null macro disclosure for legacy market gate payloads", () => {
    const model = buildLivermoreStrategyModel({ envelope: makeEnvelope() });
    expect(model.marketGate.macroDisclosure).toBeNull();
    expect(buildMarketGateMacroDisclosure(makePayload().market_gate)).toBeNull();
  });

  it("builds applied macro adjustment disclosure with cycle state label", () => {
    const disclosure = buildMarketGateMacroDisclosure({
      ...makePayload().market_gate,
      exposure: 0.25,
      exposure_raw: 0.75,
      formula_version: "rv_market_gate_macro_overlay_v1",
      macro_context: {
        status: "ready",
        cycle_state: "recession",
        macro_score: 0.2,
        gate_as_of_date: "2026-04-29",
        data_date: "2026-03-28",
        lag_days: 32,
        max_component_lag_days: 32,
        components: [],
        evidence: "cycle inputs ready",
        formula_version: "rv_market_gate_macro_overlay_v1",
      },
      macro_overlay: {
        applied: true,
        exposure_cap: 0.25,
        exposure_raw: 0.75,
        exposure_adjusted: 0.25,
        rule: "cap recession",
        formula_version: "rv_market_gate_macro_overlay_v1",
      },
    });

    expect(disclosure).toMatchObject({
      adjustmentLabel: "宏观调节 0.75→0.25",
      cycleStateLabel: "衰退",
      statusMarker: null,
      lagLabel: "宏观数据滞后 32 天",
    });
  });

  it("formats the macro adjustment as percentages when the percent exposure format is requested", () => {
    const disclosure = buildMarketGateMacroDisclosure(
      {
        ...makePayload().market_gate,
        exposure: 0.25,
        exposure_raw: 0.75,
        formula_version: "rv_market_gate_macro_overlay_v1",
        macro_context: {
          status: "ready",
          cycle_state: "recession",
          macro_score: 0.2,
          lag_days: 32,
          components: [],
        },
        macro_overlay: {
          applied: true,
          exposure_cap: 0.25,
          exposure_raw: 0.75,
          exposure_adjusted: 0.25,
        },
      },
      { exposureFormat: "percent" },
    );

    expect(disclosure?.adjustmentLabel).toBe("宏观调节 75%→25%");
  });

  it("keeps disclosure without adjustment when macro overlay is not applied", () => {
    const disclosure = buildMarketGateMacroDisclosure({
      ...makePayload().market_gate,
      exposure: 0.4,
      exposure_raw: 0.4,
      formula_version: "rv_market_gate_macro_overlay_v1",
      macro_context: {
        status: "ready",
        cycle_state: "neutral",
        macro_score: 0.5,
        lag_days: 12,
        components: [],
      },
      macro_overlay: {
        applied: false,
        exposure_cap: null,
        exposure_raw: 0.4,
        exposure_adjusted: 0.4,
      },
    });

    expect(disclosure).toMatchObject({
      adjustmentLabel: null,
      cycleStateLabel: null,
      statusMarker: null,
      lagLabel: "宏观数据滞后 12 天",
    });
  });

  it("surfaces missing macro background marker", () => {
    const disclosure = buildMarketGateMacroDisclosure({
      ...makePayload().market_gate,
      exposure_raw: 0.4,
      macro_context: {
        status: "missing",
        cycle_state: null,
        macro_score: null,
        components: [],
      },
      macro_overlay: {
        applied: false,
        exposure_raw: 0.4,
        exposure_adjusted: 0.4,
      },
    });

    expect(disclosure).toMatchObject({
      adjustmentLabel: null,
      statusMarker: "宏观背景缺失",
      lagLabel: null,
    });
  });

  it("surfaces expired macro background marker", () => {
    const disclosure = buildMarketGateMacroDisclosure({
      ...makePayload().market_gate,
      exposure_raw: 0.4,
      macro_context: {
        status: "expired",
        cycle_state: null,
        macro_score: 0.3,
        components: [],
      },
      macro_overlay: {
        applied: false,
        exposure_raw: 0.4,
        exposure_adjusted: 0.4,
      },
    });

    expect(disclosure).toMatchObject({
      statusMarker: "宏观背景过期",
    });
  });
});

describe("translateLivermoreEvidence", () => {
  it("translates gate comparison evidence into Chinese short sentences", () => {
    expect(translateLivermoreEvidence("Close 4649.19 vs MA60 4843.24 on 2026-07-24.")).toEqual({
      text: "收盘 4649.19 低于 MA60 4843.24（07-24）",
      sourceRef: null,
    });
    expect(translateLivermoreEvidence("MA20 4848.51 vs MA60 4793.12 on 2026-08-11.")).toEqual({
      text: "MA20 4848.51 高于 MA60 4793.12（08-11）",
      sourceRef: null,
    });
  });

  it("strips the physical table reference into sourceRef", () => {
    expect(
      translateLivermoreEvidence(
        "5-day breadth 3002.0000 on 2026-08-11 (fact_livermore_gate_supplement_daily).",
      ),
    ).toEqual({
      text: "5日广度 3002.0000（08-11）",
      sourceRef: "fact_livermore_gate_supplement_daily",
    });
    expect(
      translateLivermoreEvidence(
        "Limit-up quality positive on 2026-08-11 (fact_livermore_gate_supplement_daily).",
      ),
    ).toEqual({
      text: "涨停封板质量为正（08-11）",
      sourceRef: "fact_livermore_gate_supplement_daily",
    });
  });

  it("passes through unrecognized evidence verbatim (fail-open)", () => {
    expect(translateLivermoreEvidence("Breadth inputs are not landed for the Phase 1 slice.")).toEqual({
      text: "Breadth inputs are not landed for the Phase 1 slice.",
      sourceRef: null,
    });
    expect(translateLivermoreEvidence("收盘价 3950，高于 MA60 3920。")).toEqual({
      text: "收盘价 3950，高于 MA60 3920。",
      sourceRef: null,
    });
  });
});

describe("display-layer register mappings", () => {
  it("maps registered gate condition keys and diagnostic codes to Chinese labels", () => {
    const model = buildLivermoreStrategyModel({
      envelope: makeEnvelope({
        diagnostics: [
          {
            severity: "error",
            code: "LIVERMORE_RISK_INPUTS_MISSING",
            message: "Position inputs missing.",
            input_family: "position_risk",
          },
        ],
      }),
    });

    expect(model.marketGate.conditions[0]?.label).toBe("CSI300 收盘 > MA60");
    expect(model.diagnostics[0]?.codeLabel).toBe("风险输入缺失");
    expect(model.diagnostics[0]?.code).toBe("LIVERMORE_RISK_INPUTS_MISSING");
  });

  it("passes through unregistered diagnostic codes as evidence references", () => {
    const model = buildLivermoreStrategyModel({
      envelope: makeEnvelope({
        diagnostics: [
          {
            severity: "info",
            code: "LIVERMORE_SOME_NEW_CODE",
            message: "New diagnostic.",
            input_family: null,
          },
        ],
      }),
    });

    expect(model.diagnostics[0]?.codeLabel).toBe("LIVERMORE_SOME_NEW_CODE");
  });
});
