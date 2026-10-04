import { describe, expect, it } from "vitest";

import {
  buildCommodityPromotionAuditPackCopyText,
  commodityAdmissionDecisionColor,
  commodityAdmissionDecisionDisplayLabel,
  commodityAdmissionThresholds,
  formatCommodityAdmissionMetrics,
  formatCommodityAdmissionNextStep,
  normalizeCommodityAdmission,
  type CrisisCommodityAdmission,
  type CrisisCommodityAdmissionItem,
} from "./macroToolkitCrisisSupport";

// M2 修复回归测试：商品影子指标"准入判定"只消费后端 commodity_candidate_admission
// 的 decision 字段，前端不得重跑 shadow_rule_v1 规则或硬编码第二份阈值常量。
//
// M3 review 回归测试（本轮新增）：
// 1. 缺失/未知 decision 必须显示为"暂无判定"（灰色 default），绝不能被误判为红色"暂不纳入"。
// 2. next_step 展示直接透传后端字段，前端不得用固定文案覆盖 recommend_include/watch。
// 3. 全局阈值（minimum_crisis_sample_count / correlation_threshold）读取 admission envelope
//    本身，不从 items[0] 借用逐品种的 minimum_sample_count。

function buildAdmissionItem(overrides: Partial<CrisisCommodityAdmissionItem>): CrisisCommodityAdmissionItem {
  return {
    field: "copper",
    label: "Copper futures",
    decision: "watch",
    decision_label: "继续观察",
    reason: "相关性偏弱，需人工复核。",
    next_step: "复核相关性与危机期命中率，并检查异常点后再决定是否提交审批。",
    sample_count: 41,
    minimum_sample_count: 20,
    crisis_sample_count: 11,
    minimum_crisis_sample_count: 5,
    crisis_hit_rate: 0.55,
    max_abs_correlation: 0,
    correlation_threshold: 0.2,
    latest_date: "2026-04-10",
    series_id: "CA.COPPER",
    source: "tushare",
    used_in_official_score: false,
    ...overrides,
  };
}

function buildAdmission(overrides: Partial<CrisisCommodityAdmission>): CrisisCommodityAdmission {
  return {
    rule_version: "rv_macro_crisis_commodity_admission_v1",
    scope: "commodity_candidate_admission_read_only",
    decision_counts: { recommend_include: 0, watch: 1, do_not_include: 0 },
    minimum_crisis_sample_count: 5,
    correlation_threshold: 0.2,
    items: [buildAdmissionItem({})],
    warnings: [],
    approval_required: true,
    official_score_unchanged: true,
    next_step: "",
    ...overrides,
  };
}

describe("commodity admission decision -> display mapping (backend enum only)", () => {
  it.each([
    ["recommend_include", "建议纳入", "green"],
    ["watch", "继续观察", "gold"],
    ["do_not_include", "暂不纳入", "red"],
  ] as const)("maps backend decision %s to color %s using the backend decision_label verbatim", (decision, decisionLabel, color) => {
    const item = buildAdmissionItem({ decision, decision_label: decisionLabel });
    expect(commodityAdmissionDecisionColor(item.decision)).toBe(color);
    // decision_label 直接来自后端，前端不重新分类展示文案。
    expect(item.decision_label).toBe(decisionLabel);
    expect(commodityAdmissionDecisionDisplayLabel(item)).toBe(decisionLabel);
  });

  it("normalizes an unrecognized backend decision as unknown (null), never as a rejection", () => {
    const admission = normalizeCommodityAdmission({
      rule_version: "rv_macro_crisis_commodity_admission_v1",
      scope: "commodity_candidate_admission_read_only",
      decision_counts: {},
      items: [{ field: "gold", label: "Gold futures", decision: "unknown_decision" }],
      warnings: [],
      approval_required: true,
      official_score_unchanged: true,
      next_step: "",
    });
    expect(admission?.items[0]?.decision).toBeNull();
  });

  it("normalizes a missing decision field as unknown (null), never as a rejection", () => {
    const admission = normalizeCommodityAdmission({
      rule_version: "rv_macro_crisis_commodity_admission_v1",
      scope: "commodity_candidate_admission_read_only",
      decision_counts: {},
      items: [{ field: "gold", label: "Gold futures" }],
      warnings: [],
      approval_required: true,
      official_score_unchanged: true,
      next_step: "",
    });
    expect(admission?.items[0]?.decision).toBeNull();
  });

  it("displays unknown decision as a neutral 暂无判定 tag, never the red 暂不纳入 color", () => {
    const item = buildAdmissionItem({ decision: null, decision_label: "准入结论待确认" });
    expect(commodityAdmissionDecisionColor(item.decision)).toBe("default");
    expect(commodityAdmissionDecisionDisplayLabel(item)).toBe("暂无判定");
  });
});

describe("commodityAdmissionThresholds", () => {
  it("returns null (no thresholds to display) when admission is missing", () => {
    expect(commodityAdmissionThresholds(null)).toBeNull();
  });

  it("reads global thresholds from the admission envelope itself, not from items[0]", () => {
    // items[0] 的 minimum_crisis_sample_count/correlation_threshold 与 envelope 全局值不同，
    // 证明阈值确实来自 envelope 字段，而不是逐品种借用。
    const admission = buildAdmission({
      minimum_crisis_sample_count: 8,
      correlation_threshold: 0.35,
      items: [
        buildAdmissionItem({
          minimum_sample_count: 30,
          minimum_crisis_sample_count: 5,
          correlation_threshold: 0.2,
        }),
      ],
    });
    expect(commodityAdmissionThresholds(admission)).toEqual({
      minimumCrisisSampleCount: 8,
      correlationThreshold: 0.35,
    });
  });
});

describe("formatCommodityAdmissionMetrics / formatCommodityAdmissionNextStep", () => {
  it("formats do_not_include items without falling back to a frontend sample-count constant", () => {
    const item = buildAdmissionItem({
      decision: "do_not_include",
      decision_label: "暂不纳入",
      reason: "样本不足，先补齐历史数据。",
      sample_count: 17,
      minimum_sample_count: null,
      crisis_sample_count: null,
      crisis_hit_rate: null,
      max_abs_correlation: null,
    });
    expect(formatCommodityAdmissionMetrics(item)).toContain("样本 17/缺失");
    expect(formatCommodityAdmissionNextStep(item)).toBe(item.next_step);
  });

  it("passes through the backend next_step verbatim for every decision, without a frontend override", () => {
    expect(formatCommodityAdmissionNextStep(buildAdmissionItem({ decision: "recommend_include" }))).toBe(
      buildAdmissionItem({ decision: "recommend_include" }).next_step,
    );
    expect(formatCommodityAdmissionNextStep(buildAdmissionItem({ decision: "watch" }))).toBe(
      buildAdmissionItem({ decision: "watch" }).next_step,
    );
  });

  it("shows a custom backend next_step verbatim instead of a fixed frontend copy", () => {
    const customNextStep = "已提交风控委员会二次复核，等待反馈。";
    expect(
      formatCommodityAdmissionNextStep(buildAdmissionItem({ decision: "recommend_include", next_step: customNextStep })),
    ).toBe(customNextStep);
    expect(
      formatCommodityAdmissionNextStep(buildAdmissionItem({ decision: "watch", next_step: customNextStep })),
    ).toBe(customNextStep);
  });
});

describe("buildCommodityPromotionAuditPackCopyText (audit copy pack)", () => {
  const baseCounts = {
    analysisMeta: null,
    analysisAsOfDate: "2026-04-30",
    reviewQueueItems: [],
    shortQueueItems: [],
    coverageItems: [],
    commodityInput: null,
    summary: null,
  };

  it("shows an explicit 暂无判定 placeholder and never falls back to shadow_rule_v1 when admission is missing", () => {
    const text = buildCommodityPromotionAuditPackCopyText(null, baseCounts);
    expect(text).toContain("规则版本 暂无判定");
    expect(text).toContain("准入检查：commodity_candidate_admission 缺失，暂无判定");
    expect(text).toContain("暂无判定：commodity_candidate_admission 缺失，请重新运行完整分析");
    expect(text).not.toContain("shadow_rule_v1");
    expect(text).not.toContain("ready_for_review");
    expect(text).not.toContain("manual_review");
    expect(text).not.toContain("not_recommended");
  });

  it("embeds the backend rule_version, global envelope thresholds, and per-item decision/reason when admission is present", () => {
    const admission = buildAdmission({});
    const text = buildCommodityPromotionAuditPackCopyText(admission, baseCounts);
    expect(text).toContain("规则版本 rv_macro_crisis_commodity_admission_v1");
    expect(text).toContain("危机样本阈值 >=5 个高 Crisis Score 样本");
    expect(text).toContain("相关性阈值 |corr|>=0.20 才可直接通过");
    expect(text).toContain("Copper futures · 继续观察 · 相关性偏弱，需人工复核。");
    expect(text).not.toContain("shadow_rule_v1");
    // minimum_sample_count 是逐品种取值，不是全局阈值：不能再出现"样本阈值 >=N 个重叠样本"这类全局陈述。
    expect(text).not.toContain("个重叠样本");
  });

  it("writes 暂无判定 for an item with an unknown/missing decision, not the raw decision_label", () => {
    const admission = buildAdmission({
      items: [
        buildAdmissionItem({
          field: "gold",
          label: "Gold futures",
          decision: null,
          decision_label: "准入结论待确认",
        }),
      ],
    });
    const text = buildCommodityPromotionAuditPackCopyText(admission, baseCounts);
    expect(text).toContain("Gold futures · 暂无判定 ·");
    expect(text).not.toContain("Gold futures · 准入结论待确认 ·");
  });
});
