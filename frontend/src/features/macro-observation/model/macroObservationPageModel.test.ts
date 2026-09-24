import { describe, expect, it } from "vitest";

import type { ResultMeta } from "../../../api/contracts";
import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitAShareRiskPayload,
  MacroToolkitCapabilityResult,
  MacroToolkitDataHealth,
  MacroToolkitPrimarySignal,
  MacroToolkitReportBundle,
  MacroToolkitShadowPortfolioReport,
  MacroToolkitSignalCard,
  MacroToolkitStrategySummariesPayload,
  MacroToolkitStrategySummary,
} from "../../../api/macroToolkitClient";
import { EM_DASH } from "../../../pageModel";
import {
  aShareRiskMetricTone,
  buildAShareRiskView,
  buildCrisisEvidenceView,
  buildDataHealthView,
  buildEvidenceMetaView,
  buildObservationConclusion,
  buildObservationKpiBand,
  buildObservationSectionStates,
  buildObservationToolbarStatus,
  buildReportBundleView,
  buildSignalCardViews,
  buildStrategyCounts,
  buildStrategyEvidenceView,
  etfBoundaryText,
  hasonBoundaryText,
  looseStrategyDataStatus,
  mergeStrategySummaries,
  modelDegradedReasonText,
  observationRuntimeSummary,
  pickPrimarySignal,
  sanitizeEvidenceMetaForDisplay,
  strategySupplyState,
  type MacroObservationSectionStatesInput,
} from "./macroObservationPageModel";

// ---------------------------------------------------------------------------
// 最小 mock（手写对象 + as 收窄，不 import mock client）
// ---------------------------------------------------------------------------

function signalCard(overrides: Partial<MacroToolkitSignalCard> = {}): MacroToolkitSignalCard {
  return {
    key: "liquidity",
    title: "流动性",
    stance: "中性",
    tone: "neutral",
    score: 50,
    evidence: [],
    ...overrides,
  };
}

// 危机分是 z-score（2 已是高风险档），与 0-100 的方向卡不同量纲，fixture 必须按真实尺度构造。
function fullSignalCards(): MacroToolkitSignalCard[] {
  return [
    signalCard({ key: "crisis_score_cn", title: "危机分", stance: "高风险", tone: "negative", score: 2.5 }),
    signalCard({ key: "a_share_stampede_risk", title: "A股踩踏风险", stance: "数据不足", tone: "missing", score: null }),
    signalCard({ key: "liquidity", score: 78, stance: "偏松", tone: "positive" }),
    signalCard({ key: "risk_appetite", title: "风险偏好", score: 52 }),
    signalCard({ key: "credit", title: "信用", score: 55 }),
    signalCard({ key: "outputs", title: "脚本产物", stance: "已生成", tone: "positive", score: 99 }),
  ];
}

function primarySignal(
  overrides: Partial<MacroToolkitPrimarySignal> = {},
): MacroToolkitPrimarySignal {
  return {
    key: "crisis_score_cn",
    selection_status: "selected",
    reason_code: "risk_gate_crisis_score",
    rule_version: "rv_macro_primary_signal_risk_first_v1",
    ...overrides,
  };
}

function strategySummary(
  overrides: Partial<MacroToolkitStrategySummary> = {},
): MacroToolkitStrategySummary {
  return {
    key: "livermore_trend",
    label: "利弗莫尔趋势",
    group: "股票策略",
    status: "complete",
    tone: "neutral",
    primary_metric: null,
    evidence: [],
    warnings: [],
    result: { data_status: "complete", price_source: "choice_stock_daily_observation" },
    ...overrides,
  };
}

const fullChain = () => strategySummary();
// 该 key 要求行情 + 因子双来源，仅有行情来源 → 部分链路
const partialChain = () =>
  strategySummary({ key: "low_crowding_regime_multifactor", label: "低拥挤多因子" });
// 有真实来源但 status 非 complete → 与现页口径一致，partial 与 degraded 同时计数
const degradedChain = () =>
  strategySummary({
    key: "value_rotation",
    label: "价值轮动",
    status: "degraded",
    result: { data_status: "degraded", price_source: "choice_stock_daily_observation" },
  });
const sampleOnly = () =>
  strategySummary({ key: "sample_strategy", label: "样例策略", status: "sample_only", tone: "missing", result: {} });

function decisionCapabilityResult(): MacroToolkitCapabilityResult {
  return {
    key: "decision_summary",
    legacy_module: "M16",
    label: "宏观决策摘要",
    group: "决策摘要",
    status: "degraded",
    tone: "neutral",
    score: 52,
    headline: "宏观信号分化，维持中性观察。",
    primary_metric: { label: "可用模块", value: 12, unit: "/16" },
    evidence: [],
    warnings: [],
    result: { data_status: "degraded", usable_count: 12 },
  };
}

function crisisCapabilityResult(
  overrides: Partial<MacroToolkitCapabilityResult> = {},
): MacroToolkitCapabilityResult {
  return {
    key: "crisis_score_cn",
    legacy_module: "M13",
    label: "Crisis Score",
    group: "风险",
    status: "complete",
    tone: "negative",
    // Crisis 是加权 z-score：>=2 即高风险档，不是 0-100 分。
    score: 2.54,
    headline: "Crisis Score 2.54: 高风险",
    primary_metric: { label: "Crisis Score", value: 2.5, unit: "" },
    evidence: [],
    warnings: [],
    result: {
      crisis_score: 2.54,
      regime: "高风险",
      recommendation: "大幅降仓，启动 CTA 保护",
      percentile: 87.256,
      components: [
        { key: "equity_vol", label: "沪深300波动", z_score: 1.25 },
        { key: "fx_vol", label: "美元兑人民币波动", z_score: null },
      ],
      score_history: [
        { date: "2026-08-11", crisis_score: 1.98, percentile: 80.2 },
        { date: "2026-08-12", crisis_score: 2.54, percentile: 87.2 },
        { date: "2026-08-13" },
      ],
    },
    ...overrides,
  };
}

function aShareRisk(
  overrides: Partial<MacroToolkitAShareRiskPayload> = {},
): MacroToolkitAShareRiskPayload {
  return {
    trade_date: "2026-08-13",
    status: "complete",
    risk_score: 35,
    risk_level: "yellow",
    risk_name: "黄灯",
    summary: "市场情绪偏热，保持观察。",
    position_rule: "权益仓位不超过 60%",
    metrics: {},
    triggered_rules: ["turnover_spike"],
    watch_next: ["北向资金", "两融余额", "成交额", "波动率"],
    warnings: [],
    tables_used: [],
    ...overrides,
  };
}

function dataHealth(overrides: Partial<MacroToolkitDataHealth> = {}): MacroToolkitDataHealth {
  return {
    analysis_scope: "full",
    indicator_coverage: { hit_count: 18, total_count: 20, hit_rate: 0.9, missing_count: 2, missing: [] },
    source_coverage: {
      hit_count: 9,
      total_count: 10,
      hit_rate: 0.9,
      latest_date: "2026-08-12",
      deferred: false,
      missing_aliases: [],
    },
    capability_results: { complete: 10, degraded: 2, unavailable: 1, total_count: 13, deferred: false },
    capability_plan: { ready_count: 10, wired_count: 12, total_count: 13, deferred: false },
    deferred_sections: [],
    warnings: [],
    repair_items: [],
    ...overrides,
  };
}

function analysisPayload(
  overrides: Partial<MacroToolkitAnalysisPayload> = {},
): MacroToolkitAnalysisPayload {
  const base: MacroToolkitAnalysisPayload = {
    default_data_sources: [],
    as_of_date: "2026-08-13",
    conclusion: {
      stance: "偏防御",
      tone: "negative",
      summary: "宏观信号偏谨慎。",
      recommended_action: "维持防御仓位",
    },
    coverage: { indicator_count: 20, hit_count: 18, hit_rate: 0.9, script_count: 0, output_file_count: 0 },
    indicators: [],
    signal_cards: fullSignalCards(),
    primary_signal: primarySignal(),
    capability_results: [decisionCapabilityResult(), crisisCapabilityResult()],
    strategy_summaries: [],
    a_share_risk: aShareRisk(),
    output_files: [],
    source_checks: [],
    capabilities: [],
    runtime_status: { analysis_scope: "full", deferred_sections: [] },
    data_health: dataHealth(),
    warnings: [],
  };
  return { ...base, ...overrides };
}

const CORE_DEFERRED_SECTIONS = [
  "capability_results",
  "capabilities",
  "source_checks",
  "strategy_summaries",
  "a_share_risk",
].map((key) => ({ key, label: key, status: "deferred" }));

/** detail=core 首发载荷：能力结果空数组、a_share_risk 为 null、5 项延后。 */
function coreAnalysisPayload(): MacroToolkitAnalysisPayload {
  return analysisPayload({
    capability_results: [],
    a_share_risk: undefined,
    strategy_summaries: [],
    // core 首屏没有 Crisis / A股候选，后端不给主信号，前端不得让方向卡顶替。
    primary_signal: primarySignal({
      key: null,
      selection_status: "deferred",
      reason_code: "core_scope_risk_candidates_deferred",
    }),
    runtime_status: { analysis_scope: "core", deferred_sections: CORE_DEFERRED_SECTIONS },
    data_health: dataHealth({
      analysis_scope: "core",
      source_coverage: {
        hit_count: 0,
        total_count: 0,
        hit_rate: null,
        latest_date: null,
        deferred: true,
        missing_aliases: [],
      },
      capability_results: { complete: 0, degraded: 0, unavailable: 0, total_count: 0, deferred: true },
      deferred_sections: ["capability_results", "a_share_risk"],
    }),
  });
}

function resultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_0123456789abcdef",
    basis: "analytical",
    result_kind: "macro_toolkit_analysis",
    formal_use_allowed: false,
    source_version: "source_v1",
    vendor_version: "vendor_v1",
    rule_version: "rule_v1",
    cache_version: "cache_v1",
    quality_flag: "warning",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-08-13T09:00:00+08:00",
    tables_used: ["std_external_macro_daily", "fact_choice_macro_daily", "fx_daily_mid"],
    ...overrides,
  };
}

function reportBundle(overrides: Partial<MacroToolkitReportBundle> = {}): MacroToolkitReportBundle {
  return {
    status: "ready",
    reason: null,
    basis: "analytical",
    observation_only: true,
    formal_use_allowed: false,
    validation: { passed: 12, failed: 0, scope: "bundle" },
    warnings: [],
    artifacts: [
      {
        id: "daily-report",
        filename: "daily.pdf",
        label: "宏观日报",
        kind: "report",
        media_type: "application/pdf",
        size_bytes: 1024,
        sha256: "a",
      },
      {
        id: "trend chart",
        filename: "trend.png",
        label: "趋势图",
        kind: "chart",
        media_type: "image/png",
        size_bytes: 2 * 1024 * 1024,
        sha256: "b",
      },
    ],
    ...overrides,
  };
}

function sectionInput(
  overrides: Partial<MacroObservationSectionStatesInput> = {},
): MacroObservationSectionStatesInput {
  return {
    analysis: analysisPayload({ strategy_summaries: [strategySummary()] }),
    analysisLoading: false,
    analysisError: false,
    analysisMeta: resultMeta(),
    strategyPayload: undefined,
    strategySupply: "loaded",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// (a) 逐字迁移判定
// ---------------------------------------------------------------------------

describe("展示映射函数", () => {
  it("aShareRiskMetricTone：yellow 按警戒着琥珀，其余沿用共享判定", () => {
    expect(aShareRiskMetricTone("yellow")).toBe("warning");
    expect(aShareRiskMetricTone("green")).toBe("positive");
    expect(aShareRiskMetricTone("orange")).toBe("negative");
    expect(aShareRiskMetricTone("red")).toBe("negative");
    expect(aShareRiskMetricTone("unknown")).toBe("neutral");
  });

  it("modelDegradedReasonText：后端 token 中文化，未知原样，空值 EM_DASH", () => {
    expect(modelDegradedReasonText("stale_expected_outputs")).toBe("预期产物陈旧");
    expect(modelDegradedReasonText("script_unavailable")).toBe("脚本不可用");
    expect(modelDegradedReasonText("missing_expected_outputs")).toBe("预期产物缺失");
    expect(modelDegradedReasonText("indeterminate_output_dates")).toBe("产物日期待判定");
    expect(modelDegradedReasonText("no_expected_outputs_registered")).toBe("未登记预期产物");
    expect(modelDegradedReasonText("dry_run_not_executed")).toBe("干跑未执行");
    expect(modelDegradedReasonText("mystery_reason")).toBe("mystery_reason");
    expect(modelDegradedReasonText(null)).toBe(EM_DASH);
    expect(modelDegradedReasonText("  ")).toBe(EM_DASH);
  });

  it("etfBoundaryText：observation_only 中文化，未知原样，空值 EM_DASH", () => {
    expect(etfBoundaryText("observation_only")).toBe("仅观察，未启用自动执行");
    expect(etfBoundaryText("read_only_observation")).toBe("read_only_observation");
    expect(etfBoundaryText(undefined)).toBe(EM_DASH);
  });

  it("hasonBoundaryText：后端英文边界句中文化，未知句原样", () => {
    expect(
      hasonBoundaryText(
        "Analytical macro toolkit display only; not a formal MTR metric, trade order, or portfolio execution engine.",
      ),
    ).toBe("仅分析展示；不构成正式指标、交易指令或组合执行依据。");
    expect(hasonBoundaryText("仅观察使用，不进入正式投资流程。")).toBe(
      "仅观察使用，不进入正式投资流程。",
    );
    expect(hasonBoundaryText(null)).toBe(EM_DASH);
  });
});

describe("pickPrimarySignal", () => {
  it("按后端 key 取卡：危机分 2.5 不被流动性 78 的更高原始分挤掉", () => {
    expect(pickPrimarySignal(fullSignalCards(), primarySignal())?.key).toBe("crisis_score_cn");
  });

  it("后端改判方向信号时前端跟随，不自行排序", () => {
    const picked = pickPrimarySignal(
      fullSignalCards(),
      primarySignal({ key: "liquidity", reason_code: "strongest_direction_signal" }),
    );
    expect(picked?.key).toBe("liquidity");
  });

  it("deferred 时返回 null，不用方向卡顶替", () => {
    expect(
      pickPrimarySignal(
        fullSignalCards(),
        primarySignal({ key: null, selection_status: "deferred" }),
      ),
    ).toBeNull();
  });

  it("旧后端未返回 primary_signal 时 fail closed", () => {
    expect(pickPrimarySignal(fullSignalCards(), undefined)).toBeNull();
  });

  it("key 悬空（卡不在本次载荷）时返回 null", () => {
    expect(pickPrimarySignal([signalCard({ key: "liquidity" })], primarySignal())).toBeNull();
  });

  it("outputs 卡即使被指名也不入选", () => {
    const picked = pickPrimarySignal(
      [signalCard({ key: "outputs", title: "脚本产物", score: 99 })],
      primarySignal({ key: "outputs" }),
    );
    expect(picked).toBeNull();
  });
});

describe("buildStrategyCounts", () => {
  it("四态判定与现页逐字一致（partial 与 degraded 允许重叠）", () => {
    expect(buildStrategyCounts([fullChain(), partialChain(), degradedChain(), sampleOnly()])).toEqual({
      full: 1,
      partial: 2,
      degraded: 1,
      sample: 1,
    });
  });

  it("空摘要计数全零", () => {
    expect(buildStrategyCounts([])).toEqual({ full: 0, partial: 0, degraded: 0, sample: 0 });
  });
});

describe("strategySupplyState", () => {
  it.each([
    [true, false, false, "loading"],
    [false, true, false, "failed"],
    [true, true, true, "loaded"],
    [false, false, false, "loaded"],
  ] as const)("isFetching=%s isError=%s hasLoaded=%s → %s", (isFetching, isError, hasLoaded, expected) => {
    expect(strategySupplyState(isFetching, isError, hasLoaded)).toBe(expected);
  });
});

describe("observationRuntimeSummary", () => {
  it("core 且有延后项：N 项证据延后确认", () => {
    expect(observationRuntimeSummary(true, 5)).toBe("5 项证据延后确认");
  });

  it("core 且无延后项：等待完整分析确认", () => {
    expect(observationRuntimeSummary(true, 0)).toBe("等待完整分析确认");
  });

  it("full：证据已完整读取", () => {
    expect(observationRuntimeSummary(false, 3)).toBe("证据已完整读取");
  });
});

describe("mergeStrategySummaries", () => {
  it("strategy-summaries 接口优先，analysis 兜底，双缺为空数组", () => {
    const fromPayload = [strategySummary({ key: "from_payload" })];
    const fromAnalysis = [strategySummary({ key: "from_analysis" })];
    expect(
      mergeStrategySummaries(
        { strategy_summaries: fromPayload },
        analysisPayload({ strategy_summaries: fromAnalysis }),
      ),
    ).toBe(fromPayload);
    expect(mergeStrategySummaries(undefined, analysisPayload({ strategy_summaries: fromAnalysis }))).toBe(
      fromAnalysis,
    );
    expect(mergeStrategySummaries(undefined, undefined)).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// 页头工具条
// ---------------------------------------------------------------------------

describe("buildObservationToolbarStatus", () => {
  it("full 数据给出观察日 / 完整证据口径 / 来源覆盖 / 运行时摘要", () => {
    // core/full 枚举不再作为 note 直出（§7 语域）。
    expect(buildObservationToolbarStatus(analysisPayload(), resultMeta())).toEqual([
      { key: "as-of-date", label: "观察日", value: "2026-08-13" },
      { key: "analysis-scope", label: "分析口径", value: "完整证据" },
      { key: "source-coverage", label: "来源覆盖", value: "9/10" },
      { key: "runtime-status", label: "证据状态", value: "证据已完整读取" },
    ]);
  });

  it("core 数据给出首屏读数口径与延后计数，来源覆盖如实标延后", () => {
    expect(buildObservationToolbarStatus(coreAnalysisPayload(), resultMeta())).toEqual([
      { key: "as-of-date", label: "观察日", value: "2026-08-13" },
      { key: "analysis-scope", label: "分析口径", value: "首屏读数" },
      { key: "source-coverage", label: "来源覆盖", value: "延后加载" },
      { key: "runtime-status", label: "证据状态", value: "5 项证据延后确认" },
    ]);
  });

  it("analysis 未落地时缺值 EM_DASH，来源覆盖待确认", () => {
    expect(buildObservationToolbarStatus(undefined, undefined)).toEqual([
      { key: "as-of-date", label: "观察日", value: EM_DASH },
      { key: "analysis-scope", label: "分析口径", value: EM_DASH },
      { key: "source-coverage", label: "来源覆盖", value: "待确认" },
      { key: "runtime-status", label: "证据状态", value: EM_DASH },
    ]);
  });

  it("as_of_date 缺失时回落信封 as_of_date", () => {
    const chips = buildObservationToolbarStatus(
      analysisPayload({ as_of_date: null }),
      resultMeta({ as_of_date: "2026-08-12" }),
    );
    expect(chips[0]).toEqual({ key: "as-of-date", label: "观察日", value: "2026-08-12" });
  });
});

// ---------------------------------------------------------------------------
// 01 KPI 横带与结论
// ---------------------------------------------------------------------------

describe("buildObservationKpiBand", () => {
  it("full 数据全 6 格 ready", () => {
    const band = buildObservationKpiBand({
      analysis: analysisPayload(),
      strategyPayload: { strategy_summaries: [fullChain(), partialChain()] },
      analysisLoading: false,
      strategySupply: "loaded",
    });
    expect(band).toEqual([
      { key: "stance", label: "投研观点", value: "偏防御", tone: "negative", status: "ready" },
      { key: "decision-modules", label: "决策摘要可用模块", value: "12/16", note: "部分降级", status: "ready" },
      { key: "crisis-score", label: "危机分", value: "2.5", note: "高风险", status: "ready" },
      { key: "a-share-risk", label: "A股风险", value: "35", note: "黄灯", tone: "warning", status: "ready" },
      { key: "primary-signal", label: "主信号", value: "危机分", note: "高风险", tone: "negative", status: "ready" },
      { key: "strategy-supply", label: "策略供数", value: "1/2 全链路", note: "部分 1", status: "ready" },
    ]);
  });

  it("core 数据相应格 deferred + 说明 note（危机分先读 signal card 分数）", () => {
    const band = buildObservationKpiBand({
      analysis: coreAnalysisPayload(),
      strategyPayload: undefined,
      analysisLoading: false,
      strategySupply: "loaded",
    });
    expect(band).toEqual([
      { key: "stance", label: "投研观点", value: "偏防御", tone: "negative", status: "ready" },
      { key: "decision-modules", label: "决策摘要可用模块", value: EM_DASH, note: "完整分析后确认", status: "deferred" },
      { key: "crisis-score", label: "危机分", value: "2.5", note: "完整分析后确认", status: "deferred" },
      { key: "a-share-risk", label: "A股风险", value: EM_DASH, note: "完整分析后确认", status: "deferred" },
      // core 缺少风险候选，主信号必须延后，不能让方向卡冒充首屏结论。
      { key: "primary-signal", label: "主信号", value: EM_DASH, note: "完整分析后确认", status: "deferred" },
      {
        key: "strategy-supply",
        label: "策略供数",
        value: EM_DASH,
        note: "暂无策略摘要，完整分析后再确认。",
        status: "deferred",
      },
    ]);
  });

  it("conclusion 缺失时投研观点格容错为 EM_DASH", () => {
    const band = buildObservationKpiBand({
      analysis: analysisPayload({
        conclusion: undefined as unknown as MacroToolkitAnalysisPayload["conclusion"],
      }),
      strategyPayload: undefined,
      analysisLoading: false,
      strategySupply: "loaded",
    });
    expect(band[0]).toEqual({
      key: "stance",
      label: "投研观点",
      value: EM_DASH,
      tone: "neutral",
      status: "ready",
    });
  });

  it("analysis 读取中全格 loading，读取失败全格 failed", () => {
    const loadingBand = buildObservationKpiBand({
      analysis: undefined,
      strategyPayload: undefined,
      analysisLoading: true,
      strategySupply: "loading",
    });
    expect(loadingBand).toHaveLength(6);
    expect(loadingBand.every((cell) => cell.value === EM_DASH && cell.status === "loading")).toBe(true);

    const failedBand = buildObservationKpiBand({
      analysis: undefined,
      strategyPayload: undefined,
      analysisLoading: false,
      strategySupply: "failed",
    });
    expect(failedBand.every((cell) => cell.value === EM_DASH && cell.status === "failed")).toBe(true);
  });

  it("策略供数 loading / failed 态显式", () => {
    const loading = buildObservationKpiBand({
      analysis: analysisPayload(),
      strategyPayload: undefined,
      analysisLoading: false,
      strategySupply: "loading",
    });
    expect(loading[5]).toEqual({ key: "strategy-supply", label: "策略供数", value: EM_DASH, status: "loading" });

    const failed = buildObservationKpiBand({
      analysis: analysisPayload(),
      strategyPayload: undefined,
      analysisLoading: false,
      strategySupply: "failed",
    });
    expect(failed[5]).toEqual({
      key: "strategy-supply",
      label: "策略供数",
      value: EM_DASH,
      note: "策略摘要读取失败",
      status: "failed",
    });
  });

  it("策略供数 note 归纳非零的部分/降级/样例计数", () => {
    const band = buildObservationKpiBand({
      analysis: analysisPayload(),
      strategyPayload: { strategy_summaries: [fullChain(), degradedChain(), sampleOnly()] },
      analysisLoading: false,
      strategySupply: "loaded",
    });
    expect(band[5]).toEqual({
      key: "strategy-supply",
      label: "策略供数",
      value: "1/3 全链路",
      note: "部分 1 / 降级 1 / 样例 1",
      status: "ready",
    });
  });
});

describe("buildObservationConclusion", () => {
  it("full 数据给出结论正文与警示原文", () => {
    expect(buildObservationConclusion(analysisPayload({ warnings: ["w1", "w2"] }))).toEqual({
      stance: "偏防御",
      tone: "negative",
      summary: "宏观信号偏谨慎。",
      recommendedAction: "维持防御仓位",
      warnings: ["w1", "w2"],
    });
  });

  it("警示原文来源内去重且不把计数当正文", () => {
    expect(
      buildObservationConclusion(analysisPayload({ warnings: ["  曲线缺口  ", "曲线缺口", "补齐信用利差"] })),
    ).toEqual(
      expect.objectContaining({
        warnings: ["曲线缺口", "补齐信用利差"],
      }),
    );
  });

  it("recommended_action 命中补数语义时复用共享归纳文案", () => {
    const view = buildObservationConclusion(
      analysisPayload({
        conclusion: {
          stance: "中性",
          tone: "neutral",
          summary: "s",
          recommended_action: "先补齐 Choice 数据缺失",
        },
      }),
    );
    expect(view.recommendedAction).toBe("先补齐关键输入，再复核观察结论");
  });

  it("analysis 缺失时回落 EM_DASH 与等待文案", () => {
    expect(buildObservationConclusion(undefined)).toEqual({
      stance: EM_DASH,
      tone: "neutral",
      summary: EM_DASH,
      recommendedAction: "等待观察结论更新",
      warnings: [],
    });
  });
});

// ---------------------------------------------------------------------------
// 02 信号与风险
// ---------------------------------------------------------------------------

describe("buildSignalCardViews", () => {
  it("剔除 outputs 卡并做展示映射（score 一位小数、证据中文归纳、tone 映射）", () => {
    const views = buildSignalCardViews([
      signalCard({
        key: "crisis_score_cn",
        title: "危机分",
        stance: "警戒",
        tone: "negative",
        score: 61.24,
        evidence: ["score=61.2", "regime=警戒"],
      }),
      signalCard({ key: "credit", title: "信用", tone: "missing", score: null, evidence: [] }),
      signalCard({ key: "outputs", title: "脚本产物", score: 99 }),
    ]);
    expect(views).toEqual([
      {
        key: "crisis_score_cn",
        title: "危机分",
        stance: "警戒",
        scoreText: "61.2",
        evidenceText: "评分 61.2 / 状态 警戒",
        tone: "negative",
      },
      {
        key: "credit",
        title: "信用",
        stance: "中性",
        scoreText: EM_DASH,
        evidenceText: "观察证据待补齐",
        tone: "neutral",
      },
    ]);
  });
});

describe("buildAShareRiskView", () => {
  it("null（core 延后）给 deferred 诚实态", () => {
    expect(buildAShareRiskView(null)).toEqual({ state: "deferred", note: "完整分析后确认" });
  });

  it("full 缺失给 empty，不再显示完整分析后确认", () => {
    expect(buildAShareRiskView(null, "full")).toEqual({
      state: "empty",
      note: "暂无A股风险证据",
    });
  });

  it("非 null 时映射只读明细；只隐藏 1 项时不折叠（折叠收益为负）", () => {
    expect(buildAShareRiskView(aShareRisk())).toEqual({
      state: "ready",
      tradeDate: "2026-08-13",
      statusText: "已完成",
      scoreText: "35",
      level: "yellow",
      tone: "warning",
      name: "黄灯",
      summary: "市场情绪偏热，保持观察。",
      positionRule: "权益仓位不超过 60%",
      watchNext: ["北向资金", "两融余额", "成交额", "波动率"],
      watchNextMoreNote: null,
      triggeredRuleCount: 1,
    });
  });

  it("隐藏数 ≥2 才截断 watch_next 到 3 条并给「另 N 项」", () => {
    const view = buildAShareRiskView(
      aShareRisk({ watch_next: ["北向资金", "两融余额", "成交额", "波动率", "行业轮动"] }),
    );
    expect(view.state).toBe("ready");
    if (view.state === "ready") {
      expect(view.watchNext).toEqual(["北向资金", "两融余额", "成交额"]);
      expect(view.watchNextMoreNote).toBe("另 2 项");
    }
  });

  it("risk_score 缺失回落 EM_DASH，watch_next 不足 3 条无「另」注，red 映射 negative", () => {
    const view = buildAShareRiskView(
      aShareRisk({ risk_score: null, risk_level: "red", watch_next: ["北向资金"] }),
    );
    expect(view.state).toBe("ready");
    if (view.state === "ready") {
      expect(view.scoreText).toBe(EM_DASH);
      expect(view.watchNext).toEqual(["北向资金"]);
      expect(view.watchNextMoreNote).toBeNull();
      expect(view.tone).toBe("negative");
    }
  });
});

// ---------------------------------------------------------------------------
// 04 危机分证据
// ---------------------------------------------------------------------------

describe("buildCrisisEvidenceView", () => {
  it("core 无能力结果时给 deferred", () => {
    expect(buildCrisisEvidenceView(null)).toEqual({ state: "deferred", note: "完整分析后确认" });
  });

  it("full 无能力结果时给 empty，不再显示 deferred", () => {
    expect(buildCrisisEvidenceView(null, "full")).toEqual({
      state: "empty",
      note: "暂无危机分证据",
    });
  });

  it("完整结果映射 headline/score/regime/percentile/组件计数/折线数据", () => {
    expect(buildCrisisEvidenceView(crisisCapabilityResult())).toEqual({
      state: "ready",
      headline: "Crisis Score 2.54: 高风险",
      scoreText: "2.5",
      regime: "高风险",
      recommendation: "大幅降仓，启动 CTA 保护",
      percentileText: "87.26%",
      availableComponentCount: 1,
      componentCount: 2,
      componentMissingCount: 1,
      coverageNote: "组件覆盖按返回数组回退",
      history: [
        { date: "2026-08-11", value: 1.98 },
        { date: "2026-08-12", value: 2.54 },
      ],
    });
  });

  it("权威计数字段优先展示 4/5，不用 components.length 当成 4/4", () => {
    const view = buildCrisisEvidenceView(
      crisisCapabilityResult({
        result: {
          crisis_score: 2.54,
          regime: "高风险",
          recommendation: "大幅降仓，启动 CTA 保护",
          percentile: 87.256,
          available_component_count: 4,
          component_count: 5,
          components: [
            { key: "equity_vol", label: "沪深300波动", z_score: 1.25 },
            { key: "fx_vol", label: "美元兑人民币波动", z_score: 2.1 },
            { key: "credit", label: "信用利差", z_score: 0.8 },
            { key: "rates", label: "利率波动", z_score: 1.4 },
          ],
        },
      }),
    );
    expect(view).toEqual(
      expect.objectContaining({
        state: "ready",
        availableComponentCount: 4,
        componentCount: 5,
        coverageNote: null,
      }),
    );
  });

  it("权威计数字段 5/5 与 0/5 原样透出", () => {
    expect(
      buildCrisisEvidenceView(
        crisisCapabilityResult({
          result: { available_component_count: 5, component_count: 5, components: [] },
        }),
      ),
    ).toEqual(expect.objectContaining({ availableComponentCount: 5, componentCount: 5, coverageNote: null }));
    expect(
      buildCrisisEvidenceView(
        crisisCapabilityResult({
          result: { available_component_count: 0, component_count: 5, components: [] },
        }),
      ),
    ).toEqual(expect.objectContaining({ availableComponentCount: 0, componentCount: 5, coverageNote: null }));
  });

  it("score_history 映射保持 date/value 字段名并剔除无分数点", () => {
    const view = buildCrisisEvidenceView(crisisCapabilityResult());
    const firstPoint = view.state === "ready" ? view.history[0] : undefined;
    expect(view.state === "ready" ? view.history.length : 0).toBe(2);
    expect(firstPoint && Object.keys(firstPoint)).toEqual(["date", "value"]);
  });

  it("result 缺字段时回落 EM_DASH（score 回落能力 score，双缺才 EM_DASH）", () => {
    expect(buildCrisisEvidenceView(crisisCapabilityResult({ score: null, headline: "", result: {} }))).toEqual({
      state: "ready",
      headline: EM_DASH,
      scoreText: EM_DASH,
      regime: EM_DASH,
      recommendation: EM_DASH,
      percentileText: EM_DASH,
      availableComponentCount: 0,
      componentCount: 0,
      componentMissingCount: 0,
      coverageNote: "组件覆盖按返回数组回退",
      history: [],
    });
  });
});

// ---------------------------------------------------------------------------
// 03 模型与策略证据
// ---------------------------------------------------------------------------

describe("buildStrategyEvidenceView", () => {
  it("全表来源链同句时收敛为 commonChainNote 并透出 strategy_data_status", () => {
    const payload = {
      strategy_summaries: [fullChain()],
      strategy_data_status: { status: "complete", summary_count: 4 },
    } as MacroToolkitStrategySummariesPayload;
    const view = buildStrategyEvidenceView(payload, undefined);
    // 同句逐行重复收敛区头一次；行级差异位为 null（§6 去重）。
    expect(view.commonChainNote).toBe("已接入真实行情或因子快照");
    expect(view.rows).toEqual([
      {
        key: "livermore_trend",
        label: "利弗莫尔趋势",
        statusText: "已完成",
        tone: "neutral",
        chainNote: null,
      },
    ]);
    expect(view.counts).toEqual({ full: 1, partial: 0, degraded: 0, sample: 0 });
    expect(view.dataStatus).toEqual({
      status: "complete",
      statusText: "已完成",
      reason: null,
      summaryCount: 4,
    });
  });

  it("来源链有行间差异时保留在行内且不设 commonChainNote", () => {
    const view = buildStrategyEvidenceView(
      { strategy_summaries: [fullChain(), sampleOnly()] } as MacroToolkitStrategySummariesPayload,
      undefined,
    );
    expect(view.commonChainNote).toBeNull();
    expect(view.rows.map((row) => row.chainNote)).toEqual([
      "已接入真实行情或因子快照",
      "仅策略可用性检查，未接入真实供数",
    ]);
  });

  it("影子组合摘要复用只读观察文案", () => {
    const report: MacroToolkitShadowPortfolioReport = {
      status: "complete",
      basis: "read_only_shadow",
      label: "影子组合",
      as_of_date: "2026-08-12",
      completed_periods: 6,
      factor_dates: [],
      rule_version: "rule_v1",
      tables_used: [],
      warnings: [],
      cost_model: { cost_bps: [20, 50], initial_build_included: true, final_liquidation_included: true },
      benchmark: null,
      portfolios: [],
      period_returns: [],
    };
    const view = buildStrategyEvidenceView(
      { strategy_summaries: [], shadow_portfolio_report: report },
      undefined,
    );
    expect(view.shadowPortfolio).toEqual({
      label: "影子组合只读",
      value: "2026-08-12",
      detail: "6 个周期 · 保持观察，不替换正式规则",
      tone: "neutral",
    });
  });

  it("ETF 摘要映射 boundary 与双频状态", () => {
    const view = buildStrategyEvidenceView(
      {
        strategy_summaries: [],
        macro_etf_strategy: { boundary: "read_only_observation", dual_frequency: { status: "warning" } },
      },
      undefined,
    );
    expect(view.etfStrategy).toEqual({
      boundary: "read_only_observation",
      dualFrequencyStatusText: "存在缺口",
    });
  });

  it("ETF 无候选快照时回落 data_status.dual_frequency_status", () => {
    const view = buildStrategyEvidenceView(
      {
        strategy_summaries: [],
        macro_etf_strategy: {
          boundary: "read_only_observation",
          data_status: { dual_frequency_status: "not_evaluated" },
        },
      },
      undefined,
    );
    expect(view.etfStrategy).toEqual({
      boundary: "read_only_observation",
      dualFrequencyStatusText: "未评估",
    });
  });

  it("strategy-summaries 缺失时 strategy_data_status 从 analysis 宽松读取", () => {
    const analysis = {
      ...analysisPayload(),
      strategy_data_status: { status: "deferred", summary_count: 0 },
    } as MacroToolkitAnalysisPayload;
    const view = buildStrategyEvidenceView(undefined, analysis);
    expect(view.dataStatus).toEqual({
      status: "deferred",
      statusText: "已延后",
      reason: null,
      summaryCount: 0,
    });
  });

  it("载荷双缺时影子组合给待确认摘要，ETF 与供数状态为 null", () => {
    const view = buildStrategyEvidenceView(undefined, undefined);
    expect(view.rows).toEqual([]);
    expect(view.shadowPortfolio).toEqual({
      label: "影子组合待确认",
      value: "未返回",
      detail: "完整分析可继续确认只读组合证据。",
      tone: "neutral",
    });
    expect(view.etfStrategy).toBeNull();
    expect(view.dataStatus).toBeNull();
  });
});

describe("looseStrategyDataStatus", () => {
  it("宽松读取 status/reason/summary_count 并做中文化", () => {
    expect(
      looseStrategyDataStatus({
        strategy_data_status: { status: "unavailable", reason: "no_strategy_summaries", summary_count: 0 },
      }),
    ).toEqual({
      status: "unavailable",
      statusText: "不可用",
      reason: "no_strategy_summaries",
      summaryCount: 0,
    });
  });

  it("非对象 / 缺 status 一律回落 null，不虚构业务含义", () => {
    expect(looseStrategyDataStatus(undefined)).toBeNull();
    expect(looseStrategyDataStatus({})).toBeNull();
    expect(looseStrategyDataStatus({ strategy_data_status: { summary_count: 3 } })).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 05 数据健康
// ---------------------------------------------------------------------------

describe("buildDataHealthView", () => {
  it("data_health 未返回时为 null（交由分区状态兜底）", () => {
    expect(buildDataHealthView(undefined)).toBeNull();
  });

  it("三组覆盖读数就绪分支", () => {
    const view = buildDataHealthView(dataHealth());
    expect(view?.coverage).toEqual([
      { key: "indicator-coverage", label: "指标覆盖", value: "18/20", note: "命中率 90.0% · 缺失 2 项" },
      { key: "source-coverage", label: "来源覆盖", value: "9/10", date: "2026-08-12" },
      {
        key: "capability-results",
        label: "能力结果",
        value: "10/13",
        note: "10 完整 / 2 降级 / 1 不可用",
      },
    ]);
    expect(view?.repairItems).toEqual([]);
    expect(view?.repairMoreNote).toBeNull();
    expect(view?.deferredSectionLabels).toEqual([]);
    expect(view?.warnings).toEqual([]);
  });

  it("健康警示展示原文并在来源内去重", () => {
    const view = buildDataHealthView(
      dataHealth({ warnings: ["缺 PMI 核心输入", " 缺 PMI 核心输入", "曲线日滞后"] }),
    );
    expect(view?.warnings).toEqual(["缺 PMI 核心输入", "曲线日滞后"]);
  });

  it("core 延后加载态如实透出，不按 0 处理", () => {
    const view = buildDataHealthView(coreAnalysisPayload().data_health);
    expect(view?.coverage[1]).toEqual({ key: "source-coverage", label: "来源覆盖", value: "延后加载" });
    expect(view?.coverage[2]).toEqual({
      key: "capability-results",
      label: "能力结果",
      value: "延后加载",
      note: "能力结果延后加载，未按 0 处理",
    });
    expect(view?.deferredSectionLabels).toEqual(["能力结果", "风险证据"]);
  });

  it("修复项按优先级排序取前 5 并给「另 N 项」", () => {
    const view = buildDataHealthView(
      dataHealth({
        repair_items: [
          { type: "stale", priority: "low", alias: "L1", label: "低一", suggested_action: "补 L1" },
          { type: "missing", priority: "high", alias: "H1", label: "高一", suggested_action: "补 H1" },
          { type: "deferred", key: "capability_results" },
          { type: "degraded", priority: "medium", alias: "M1", label: "中一", suggested_action: "补 M1" },
          { type: "missing", priority: "high", alias: "H2", label: "高二", suggested_action: "补 H2" },
          { type: "stale", priority: "medium", alias: "M2", label: "中二", suggested_action: "补 M2" },
          { type: "stale", priority: "low", alias: "L2", label: "低二", suggested_action: "补 L2" },
        ],
      }),
    );
    expect(view?.repairItems.map((item) => item.label)).toEqual(["高一", "高二", "中一", "中二", "低一"]);
    expect(view?.repairMoreNote).toBe("另 2 项");
  });

  it("deferred 修复项映射中文标签与完整分析动作", () => {
    const view = buildDataHealthView(dataHealth({ repair_items: [{ type: "deferred", key: "a_share_risk" }] }));
    expect(view?.repairItems).toEqual([
      {
        key: "repair-0-a_share_risk",
        label: "风险证据",
        typeText: "完整分析后确认",
        priorityText: "中",
        actionText: "打开完整分析后确认这部分证据，不把首屏延后加载当作缺失。",
        actionTitle: null,
        latestDateText: EM_DASH,
        staleDaysText: EM_DASH,
      },
    ]);
  });

  it("建议动作英文错误码译中文短语、状态枚举中文化、去句首事项名；原句收 title", () => {
    const view = buildDataHealthView(
      dataHealth({
        repair_items: [
          {
            type: "missing",
            priority: "high",
            label: "经济周期定位",
            suggested_action:
              "经济周期定位 当前 unavailable：PMI_CORE_INPUT_MISSING / GOV_CURVE_MISSING_REQUIRED_TENORS；补齐输入证据后重新运行完整宏观分析。",
          },
        ],
      }),
    );
    const row = view?.repairItems[0];
    expect(row?.actionText).toBe(
      "当前不可用：缺 PMI 核心输入 / 缺国债曲线必需期限；补齐输入证据后重新运行完整宏观分析。",
    );
    expect(row?.actionTitle).toBe(
      "经济周期定位 当前 unavailable：PMI_CORE_INPUT_MISSING / GOV_CURVE_MISSING_REQUIRED_TENORS；补齐输入证据后重新运行完整宏观分析。",
    );
  });
});

// ---------------------------------------------------------------------------
// 06 证据与口径
// ---------------------------------------------------------------------------

describe("buildEvidenceMetaView", () => {
  it("分析信封读数含质量口径说明与 trace 截断 12 位", () => {
    const view = buildEvidenceMetaView(resultMeta(), undefined);
    expect(view.strategy).toBeNull();
    expect(view.analysis).toEqual([
      { key: "analysis-basis", label: "口径", value: "分析口径" },
      { key: "analysis-formal-use", label: "正式使用", value: "仅观察" },
      {
        key: "analysis-quality",
        label: "质量标记",
        value: "质量待复核",
        note: "分析口径恒 warning，不代表数据异常",
      },
      { key: "analysis-tables", label: "事实表", value: "3 张" },
      { key: "analysis-trace", label: "trace", value: "tr_012345678…" },
      { key: "analysis-generated-at", label: "生成时间", value: "2026-08-13T09:00:00+08:00" },
    ]);
  });

  it("策略信封无质量说明注；tables 缺失回落 EM_DASH；短 trace 不截断", () => {
    const view = buildEvidenceMetaView(
      undefined,
      resultMeta({ tables_used: undefined, trace_id: "short" }),
    );
    expect(view.analysis).toBeNull();
    expect(view.strategy?.[2]).toEqual({ key: "strategy-quality", label: "质量标记", value: "质量待复核" });
    expect(view.strategy?.[3]).toEqual({ key: "strategy-tables", label: "事实表", value: EM_DASH });
    expect(view.strategy?.[4]).toEqual({ key: "strategy-trace", label: "trace", value: "short" });
  });

  it("formal_use_allowed=true 时如实展示允许正式使用", () => {
    const view = buildEvidenceMetaView(resultMeta({ formal_use_allowed: true }), undefined);
    expect(view.analysis?.[1]).toEqual({
      key: "analysis-formal-use",
      label: "正式使用",
      value: "允许正式使用",
    });
  });
});

describe("sanitizeEvidenceMetaForDisplay", () => {
  it("空 JSON 筛选与 none 缓存版本清洗为缺值；有效值原样返回", () => {
    const meta = resultMeta({ filters_applied: {}, cache_version: "none" });
    const sanitized = sanitizeEvidenceMetaForDisplay(meta);
    expect(sanitized?.filters_applied).toBeUndefined();
    expect(sanitized?.cache_version).toBe("");
    // 原信封对象不被改写（仅展示层拷贝）。
    expect(meta.cache_version).toBe("none");

    const intact = resultMeta({ filters_applied: { report_date: "2026-08-12" }, cache_version: "cv-9" });
    expect(sanitizeEvidenceMetaForDisplay(intact)).toBe(intact);
    expect(sanitizeEvidenceMetaForDisplay(undefined)).toBeUndefined();
  });
});

describe("buildReportBundleView", () => {
  it("ready 包映射产物 sizeText（KB/MB 一位小数）与 downloadHref", () => {
    const view = buildReportBundleView(reportBundle());
    expect(view.status).toBe("ready");
    expect(view.statusText).toBe("可下载");
    expect(view.downloadable).toBe(true);
    expect(view.validationText).toBe("12 通过 / 0 未通过");
    expect(view.materialDate).toBe(EM_DASH);
    expect(view.curveDate).toBe(EM_DASH);
    expect(view.accountReportDate).toBe(EM_DASH);
    expect(view.validationScope).toBe("bundle");
    expect(view.warnings).toEqual([]);
    expect(view.artifacts).toEqual([
      {
        id: "daily-report",
        filename: "daily.pdf",
        label: "宏观日报",
        kind: "report",
        sizeText: "1.0 KB",
        downloadHref: "/ui/macro/toolkit/report-bundle/daily-report",
      },
      {
        id: "trend chart",
        filename: "trend.png",
        label: "趋势图",
        kind: "chart",
        sizeText: "2.0 MB",
        downloadHref: "/ui/macro/toolkit/report-bundle/trend%20chart",
      },
    ]);
  });

  it("bundle 未返回按 missing 处理（同现有面板缺省语义）", () => {
    expect(buildReportBundleView(undefined)).toEqual({
      status: "missing",
      statusText: "报告资产尚未发布",
      downloadable: false,
      reason: null,
      validationText: EM_DASH,
      validationFailedCount: 0,
      materialDate: EM_DASH,
      curveDate: EM_DASH,
      accountReportDate: EM_DASH,
      validationScope: EM_DASH,
      warnings: [],
      artifacts: [],
    });
  });

  it("invalid 包关闭下载并保留 reason", () => {
    const view = buildReportBundleView(reportBundle({ status: "invalid", reason: "sha256 mismatch" }));
    expect(view.statusText).toBe("资产校验失败，下载已关闭");
    expect(view.downloadable).toBe(false);
    expect(view.reason).toBe("sha256 mismatch");
  });

  it("三日期与校验范围各自透出，缺失不互相回填", () => {
    const view = buildReportBundleView(
      reportBundle({
        as_of_date: "2026-08-12",
        curve_date: "2026-08-11",
        warnings: ["哈希待复核", "哈希待复核"],
      }),
    );
    expect(view.materialDate).toBe("2026-08-12");
    expect(view.curveDate).toBe("2026-08-11");
    expect(view.accountReportDate).toBe(EM_DASH);
    expect(view.validationScope).toBe("bundle");
    expect(view.warnings).toEqual(["哈希待复核"]);
  });
});

// ---------------------------------------------------------------------------
// 分区五态判定
// ---------------------------------------------------------------------------

describe("buildObservationSectionStates", () => {
  it("全量就绪时各分区返回 null（ready 不渲染分区头状态）", () => {
    expect(buildObservationSectionStates(sectionInput())).toEqual({
      signalRisk: null,
      modelStrategy: null,
      crisis: null,
      dataHealth: null,
      evidence: null,
    });
  });

  it("analysis 读取中各分区 loading", () => {
    const states = buildObservationSectionStates(
      sectionInput({
        analysis: undefined,
        analysisMeta: undefined,
        analysisLoading: true,
        strategySupply: "loading",
      }),
    );
    expect(states.signalRisk).toEqual({ state: "loading", note: "观察证据加载中" });
    expect(states.crisis).toEqual({ state: "loading", note: "观察证据加载中" });
    expect(states.dataHealth).toEqual({ state: "loading", note: "观察证据加载中" });
    expect(states.evidence).toEqual({ state: "loading", note: "观察证据加载中" });
    expect(states.modelStrategy).toEqual({ state: "loading", note: "策略摘要正在生成。" });
  });

  it("analysis 读取失败各分区 error（复用现页失败文案）", () => {
    const states = buildObservationSectionStates(
      sectionInput({
        analysis: undefined,
        analysisMeta: undefined,
        analysisError: true,
        strategySupply: "failed",
      }),
    );
    expect(states.signalRisk).toEqual({ state: "error", note: "读取核心分析失败" });
    expect(states.crisis).toEqual({ state: "error", note: "读取核心分析失败" });
    expect(states.dataHealth).toEqual({ state: "error", note: "读取核心分析失败" });
    expect(states.evidence).toEqual({ state: "error", note: "读取核心分析失败" });
    expect(states.modelStrategy).toEqual({
      state: "error",
      note: "策略摘要读取失败，当前不能判断策略供数闭环。",
    });
  });

  it("core 首发时风险 / 危机 / 策略分区 deferred", () => {
    const states = buildObservationSectionStates(
      sectionInput({ analysis: coreAnalysisPayload(), strategySupply: "loaded" }),
    );
    expect(states.signalRisk).toEqual({ state: "deferred", note: "A股风险完整分析后确认" });
    expect(states.crisis).toEqual({ state: "deferred", note: "危机分证据完整分析后确认" });
    expect(states.modelStrategy).toEqual({ state: "deferred", note: "暂无策略摘要，完整分析后再确认。" });
    expect(states.dataHealth).toBeNull();
    expect(states.evidence).toBeNull();
  });

  it("full 模式无危机结果按空态处理，风险在场则信号分区就绪", () => {
    const states = buildObservationSectionStates(
      sectionInput({ analysis: analysisPayload({ capability_results: [] }) }),
    );
    expect(states.crisis).toEqual({ state: "empty", note: "暂无危机分证据" });
    expect(states.signalRisk).toBeNull();
  });

  it("full 模式无策略摘要按 empty 处理，不再写完整分析后再确认", () => {
    const states = buildObservationSectionStates(
      sectionInput({
        analysis: analysisPayload({ strategy_summaries: [] }),
        strategyPayload: { strategy_summaries: [] },
        strategySupply: "loaded",
      }),
    );
    expect(states.modelStrategy).toEqual({ state: "empty", note: "暂无策略摘要" });
  });

  it("信号卡全为 outputs 时信号分区 empty", () => {
    const states = buildObservationSectionStates(
      sectionInput({
        analysis: analysisPayload({ signal_cards: [signalCard({ key: "outputs", title: "脚本产物" })] }),
      }),
    );
    expect(states.signalRisk).toEqual({ state: "empty", note: "暂无信号证据" });
  });

  it("data_health 未返回时数据健康分区 empty", () => {
    const states = buildObservationSectionStates(
      sectionInput({
        analysis: analysisPayload({
          data_health: undefined as unknown as MacroToolkitAnalysisPayload["data_health"],
        }),
      }),
    );
    expect(states.dataHealth).toEqual({ state: "empty", note: "暂无数据健康证据" });
  });

  it("未加载且无错误时给 empty 兜底", () => {
    const states = buildObservationSectionStates(
      sectionInput({ analysis: undefined, analysisMeta: undefined }),
    );
    expect(states.signalRisk).toEqual({ state: "empty", note: "暂无观察证据" });
    expect(states.evidence).toEqual({ state: "empty", note: "暂无口径证据" });
  });
});
