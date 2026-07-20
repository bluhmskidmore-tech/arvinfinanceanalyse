import observationKeysConfig from "../../../config/macro_decision_observation_keys.json";
import type { MacroToolkitCapabilityResult } from "./macroToolkitClient";

/** Shared with backend `config/macro_decision_observation_keys.json`. */
export const DECISION_SUMMARY_OBSERVATION_KEYS = new Set<string>(
  observationKeysConfig.observation_keys,
);

/**
 * Build mock decision_summary with the same observation-exclusion voting rules
 * as backend `_decision_summary_card`. Only keys that are both in the shared
 * observation set and present as usable mock cards are excluded from tone votes.
 */
export function buildMockDecisionSummaryCard(
  cards: MacroToolkitCapabilityResult[],
  totalCount: number,
  reportDate = "2026-04-30",
): MacroToolkitCapabilityResult {
  const usableCards = cards.filter(
    (card) => card.status === "complete" || card.status === "degraded",
  );
  const votingCards = usableCards.filter(
    (card) => !DECISION_SUMMARY_OBSERVATION_KEYS.has(card.key),
  );
  const positiveCount = votingCards.filter((card) => card.tone === "positive").length;
  const negativeCount = votingCards.filter((card) => card.tone === "negative").length;
  const missingCount = Math.max(0, totalCount - cards.length);

  let tone: MacroToolkitCapabilityResult["tone"] = "neutral";
  let headline = "宏观信号分化，维持中性观察。";
  if (usableCards.length === 0) {
    tone = "missing";
    headline = "宏观模块均不可用，无法给出方向性判断。";
  } else if (negativeCount > positiveCount) {
    tone = "negative";
    headline = "宏观信号偏谨慎，优先控制久期和信用敞口。";
  } else if (positiveCount > negativeCount) {
    tone = "positive";
    headline = "宏观信号偏支持，组合可保留适度久期与高等级信用。";
  }

  let status: MacroToolkitCapabilityResult["status"] = "degraded";
  if (usableCards.length === 0) {
    status = "unavailable";
  } else if (usableCards.length === totalCount && missingCount === 0) {
    status = "complete";
  }

  const score =
    usableCards.length === 0
      ? null
      : Math.max(0, Math.min(100, Math.round((50 + (positiveCount - negativeCount) * 8 - missingCount * 3) * 100) / 100));

  const evidence = usableCards
    .slice(0, 4)
    .filter((card) => Boolean(card.headline))
    .map((card) => `${card.legacy_module} ${card.headline}`);

  return {
    key: "decision_summary",
    legacy_module: "M16",
    label: "宏观决策摘要",
    group: "决策摘要",
    status,
    tone,
    score,
    headline,
    primary_metric: { label: "可用模块", value: usableCards.length, unit: `/${totalCount}` },
    evidence,
    warnings:
      status === "unavailable"
        ? ["宏观模块结果全部不可用"]
        : status === "degraded"
          ? ["部分模块数据降级或不可用"]
          : [],
    result: {
      report_date: reportDate,
      data_status: status,
      formal_use_allowed: false,
      positive_count: positiveCount,
      negative_count: negativeCount,
      observation_excluded_count: usableCards.length - votingCards.length,
      missing_count: missingCount,
      usable_count: usableCards.length,
      headline,
    },
  };
}
