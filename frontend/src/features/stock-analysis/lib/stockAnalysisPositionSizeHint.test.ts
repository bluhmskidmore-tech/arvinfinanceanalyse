import { describe, expect, it } from "vitest";

import type { LivermorePositionSizeHint, LivermoreStrategyPayload } from "../../../api/contracts";
import { buildCandidateReviewQueue } from "./stockAnalysisPageModel";
import {
  attachCandidateSizeHintFields,
  buildCandidatePositionSizeHintNotice,
} from "./stockAnalysisPositionSizeHintModel";
import { enrichStockAnalysisWorkbenchReviewQueue } from "./stockAnalysisWorkbenchQueueModel";

const OOS_NOTE =
  "walk-forward 样本外验证显示逐窗最优 rpt 在 0.25%~1% 间漂移，固定 0.5% 的全窗口优势在样本外普遍缩水；本建议仅供参考，需结合等权 shadow 对照观察。";
const GATE_NOTE =
  "raw_weight 为单票权重上限建议；实盘按引擎串联口径，建仓金额仍受当日 gate 敞口剩余预算截断，本提示不做实时敞口截断。";
const SHADOW_NOTE = "等权 shadow 对照仍在回测输出（sizing=equal_weight 变体），用于 drift 监控。";
const COVERAGE_WARNING =
  "ema10 stop_ref 缺失率超过 10%，建议仓位提示已降级：缺失候选按 fallback 止损距离估算，仅供参考。";

function buildPositionSizeHint(
  overrides: Partial<LivermorePositionSizeHint> = {},
): LivermorePositionSizeHint {
  return {
    policy_version: "sizing_rb_v1",
    sizing_mode: "risk_budget",
    signal_kind: "stock_candidate",
    risk_per_trade: 0.005,
    single_name_cap: 0.2,
    fallback_stop_distance_pct: 0.05,
    stop_basis: "ema10_stop_ref",
    items: [
      {
        stock_code: "000001.SZ",
        raw_weight: 0.084249,
        stop_distance_pct: 0.059348,
        stop_basis: "ema10_stop_ref",
        capped: false,
      },
      {
        stock_code: "000002.SZ",
        raw_weight: 0.2,
        stop_distance_pct: 0.05,
        stop_basis: "fallback",
        capped: true,
      },
    ],
    stop_ref_fallback_count: 0,
    stop_ref_missing_ratio: 0,
    coverage_degraded: false,
    coverage_warning: null,
    gate_exposure_note: GATE_NOTE,
    equal_weight_shadow_note: SHADOW_NOTE,
    oos_validation: {
      status: "not_supported_by_walk_forward",
      note: OOS_NOTE,
      evidence_ref: "docs/strategy-reports/walk-forward-first-run.md",
    },
    ...overrides,
  };
}

function buildPayload(): LivermoreStrategyPayload {
  return {
    as_of_date: "2026-06-26",
    requested_as_of_date: null,
    strategy_name: "Position size hint fixture",
    basis: "analytical",
    market_gate: {
      state: "WARM",
      exposure: 0.4,
      passed_conditions: 2,
      available_conditions: 2,
      required_conditions: 4,
      conditions: [],
    },
    rule_readiness: [],
    diagnostics: [],
    data_gaps: [],
    supported_outputs: ["market_gate", "stock_candidates"],
    unsupported_outputs: [],
    module_states: [
      {
        key: "stock_candidates",
        state: "ready",
        render_mode: "primary",
        source_date: "2026-06-26",
        lag_days: 0,
        threshold_days: null,
        reasons: [],
        evidence_scope: "primary",
        excludes_from_primary: false,
      },
    ],
    stock_candidates: {
      as_of_date: "2026-06-26",
      formula_version: "rv_livermore_stock_candidates_bundle_v1",
      market_state: "WARM",
      input_stock_count: 2,
      candidate_count: 2,
      excluded_stock_count: 0,
      insufficient_history_count: 0,
      items: [
        {
          rank: 1,
          stock_code: "000001.SZ",
          stock_name: "Alpha Leader",
          sector_code: "801010",
          sector_name: "Banks",
          sector_rank: 1,
          close: 21.9,
          breakout_level: 21.8,
          ema10: 20.6,
          ma20: 21.05,
          ma60: 19.05,
          ma120: 16.05,
          close_strength: 0.833333,
          gap_norm: -0.114679,
          breakout_extension_norm: 0.045872,
          abnormal_turnover: 1.386294,
        },
        {
          rank: 2,
          stock_code: "000002.SZ",
          stock_name: "Beta Watch",
          sector_code: "801020",
          sector_name: "Software",
          sector_rank: 2,
          close: 19.8,
          breakout_level: 20,
          ema10: 19.2,
          ma20: 19,
          ma60: 18,
          ma120: 17,
          close_strength: 0.64,
          gap_norm: 0.02,
          breakout_extension_norm: -0.01,
          abnormal_turnover: 0.9,
        },
      ],
      position_size_hint: buildPositionSizeHint(),
    },
  };
}

describe("stock candidate position size hint pass-through", () => {
  it("formats per-candidate hint badges and passes disclosure text into the tooltip detail", () => {
    const queue = attachCandidateSizeHintFields(
      buildCandidateReviewQueue(buildPayload()),
      buildPositionSizeHint(),
    );

    expect(queue).toHaveLength(2);
    expect(queue[0].sizeHintLabel).toBe("仓位 ≤ 8.4%");
    expect(queue[0].sizeHintDetail).toContain("EMA10 止损距离折算");
    expect(queue[0].sizeHintDetail).not.toContain("已触单票上限");
    expect(queue[0].sizeHintDetail).toContain(`样本外验证：${OOS_NOTE}`);
    expect(queue[0].sizeHintDetail).toContain(GATE_NOTE);

    expect(queue[1].sizeHintLabel).toBe("仓位 ≤ 20.0%");
    expect(queue[1].sizeHintDetail).toContain("fallback 止损距离折算");
    expect(queue[1].sizeHintDetail).toContain("已触单票上限");
  });

  it("keeps hint fields absent when the backend omits position_size_hint (legacy response)", () => {
    const queue = attachCandidateSizeHintFields(buildCandidateReviewQueue(buildPayload()), undefined);

    expect(queue[0].sizeHintLabel).toBeUndefined();
    expect(queue[0].sizeHintDetail).toBeUndefined();
    expect(buildCandidatePositionSizeHintNotice(undefined)).toBeNull();
    expect(buildCandidatePositionSizeHintNotice(null)).toBeNull();
  });

  it("keeps a candidate without a matching hint item badge-free", () => {
    const hint = buildPositionSizeHint({
      items: [
        {
          stock_code: "000001.SZ",
          raw_weight: 0.084249,
          stop_distance_pct: 0.059348,
          stop_basis: "ema10_stop_ref",
          capped: false,
        },
      ],
    });
    const queue = attachCandidateSizeHintFields(buildCandidateReviewQueue(buildPayload()), hint);

    expect(queue[0].sizeHintLabel).toBe("仓位 ≤ 8.4%");
    expect(queue[1].sizeHintLabel).toBeUndefined();
    expect(queue[1].sizeHintDetail).toBeUndefined();
  });

  it("injects hint fields through queue enrichment only for the stock_candidates source", () => {
    const strategyQueue = buildCandidateReviewQueue(buildPayload());
    const workbenchQueue = strategyQueue.map((candidate) => ({
      ...candidate,
      rawFields: [
        ...candidate.rawFields,
        { key: "source_module_key", label: "来源模块标识", value: "stock_candidates" },
      ],
    }));

    const enriched = enrichStockAnalysisWorkbenchReviewQueue(
      workbenchQueue,
      strategyQueue,
      "stock_candidates",
      buildPositionSizeHint(),
    );
    expect(enriched[0].sizeHintLabel).toBe("仓位 ≤ 8.4%");
    expect(enriched[1].sizeHintLabel).toBe("仓位 ≤ 20.0%");

    const nonTrend = enrichStockAnalysisWorkbenchReviewQueue(
      workbenchQueue,
      strategyQueue,
      "hybrid_fusion_candidates",
      buildPositionSizeHint(),
    );
    expect(nonTrend[0].sizeHintLabel).toBeUndefined();
  });

  it("builds the page-level notice with the oos validation disclosure verbatim", () => {
    const notice = buildCandidatePositionSizeHintNotice(buildPositionSizeHint());

    expect(notice).not.toBeNull();
    expect(notice?.summary).toBe("建议仓位为单票上限参考（样本外验证未获支持）");
    expect(notice?.tone).toBe("neutral");
    expect(notice?.oosStatusLabel).toBe("样本外验证未获支持");
    expect(notice?.oosNote).toBe(OOS_NOTE);
    expect(notice?.coverageWarning).toBeNull();
    expect(notice?.detail).toContain(`样本外验证：${OOS_NOTE}`);
    expect(notice?.detail).toContain("验证证据：docs/strategy-reports/walk-forward-first-run.md");
    expect(notice?.detail).toContain(GATE_NOTE);
    expect(notice?.detail).toContain(SHADOW_NOTE);
  });

  it("escalates the notice tone and surfaces the coverage warning when coverage degrades", () => {
    const hint = buildPositionSizeHint({
      coverage_degraded: true,
      coverage_warning: COVERAGE_WARNING,
    });
    const notice = buildCandidatePositionSizeHintNotice(hint);

    expect(notice?.summary).toBe("建议仓位为单票上限参考（样本外验证未获支持；覆盖率降级）");
    expect(notice?.tone).toBe("warning");
    expect(notice?.coverageWarning).toBe(COVERAGE_WARNING);
    expect(notice?.detail).toContain(COVERAGE_WARNING);

    const queue = attachCandidateSizeHintFields(buildCandidateReviewQueue(buildPayload()), hint);
    expect(queue[0].sizeHintDetail).toContain(COVERAGE_WARNING);
  });

  it("tolerates hint blocks without the oos_validation disclosure (pre-disclosure payloads)", () => {
    const hint = buildPositionSizeHint();
    delete (hint as Record<string, unknown>).oos_validation;

    const queue = attachCandidateSizeHintFields(buildCandidateReviewQueue(buildPayload()), hint);
    expect(queue[0].sizeHintLabel).toBe("仓位 ≤ 8.4%");
    expect(queue[0].sizeHintDetail).not.toContain("样本外验证");

    const notice = buildCandidatePositionSizeHintNotice(hint);
    expect(notice?.summary).toBe("建议仓位为单票上限参考");
    expect(notice?.oosStatusLabel).toBeNull();
    expect(notice?.oosNote).toBeNull();
  });

  it("labels unknown oos statuses as pending confirmation instead of inventing meaning", () => {
    const hint = buildPositionSizeHint({
      oos_validation: {
        status: "some_future_status",
        note: OOS_NOTE,
        evidence_ref: null,
      },
    });
    const notice = buildCandidatePositionSizeHintNotice(hint);

    expect(notice?.oosStatusLabel).toBe("样本外验证状态待确认");
    expect(notice?.summary).toBe("建议仓位为单票上限参考（样本外验证状态待确认）");
  });
});
