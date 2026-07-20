import { describe, expect, it } from "vitest";

import observationKeysConfig from "../../../config/macro_decision_observation_keys.json";
import {
  buildMockDecisionSummaryCard,
  DECISION_SUMMARY_OBSERVATION_KEYS,
} from "../api/macroDecisionSummaryMock";
import type { MacroToolkitCapabilityResult } from "../api/macroToolkitClient";
import { createMockMacroToolkitClient } from "../api/macroToolkitMockClient";

function card(
  key: string,
  status: MacroToolkitCapabilityResult["status"],
  tone: MacroToolkitCapabilityResult["tone"],
): MacroToolkitCapabilityResult {
  return {
    key,
    legacy_module: key.toUpperCase(),
    label: key,
    group: "test",
    status,
    tone,
    score: null,
    headline: `${key} headline`,
    primary_metric: null,
    evidence: [],
    warnings: [],
    result: {},
  };
}

describe("macroDecisionSummaryMock", () => {
  it("loads the shared observation-key list used by the backend config", () => {
    expect([...DECISION_SUMMARY_OBSERVATION_KEYS].sort()).toEqual(
      [...observationKeysConfig.observation_keys].sort(),
    );
    expect(observationKeysConfig.observation_keys).toEqual(
      [...observationKeysConfig.observation_keys].sort(),
    );
  });

  it("excludes only observation keys that are present as usable mock cards from tone voting", () => {
    const cards = [
      card("crisis_score_cn", "complete", "positive"),
      card("monetary_policy_stance", "degraded", "neutral"),
      card("yield_curve_shape", "complete", "positive"),
      card("merrill_clock_cn", "degraded", "positive"),
      card("cta_trend_cn", "degraded", "negative"),
    ];

    const summary = buildMockDecisionSummaryCard(cards, 14);

    expect(summary.tone).toBe("positive");
    expect(summary.result.positive_count).toBe(1);
    expect(summary.result.negative_count).toBe(0);
    expect(summary.result.observation_excluded_count).toBe(3);
    expect(summary.result.usable_count).toBe(5);
    expect(summary.result.missing_count).toBe(9);
    expect(summary.score).toBe(31);
    expect(summary.result.formal_use_allowed).toBe(false);
  });

  it("keeps mock analysis decision_summary aligned with shared observation exclusion", async () => {
    const client = createMockMacroToolkitClient();
    const envelope = await client.getMacroToolkitAnalysis();
    const decision = envelope.result.capability_results.find(
      (item) => item.key === "decision_summary",
    );
    const partial = envelope.result.capability_results.filter(
      (item) => item.key !== "decision_summary",
    );
    const usable = partial.filter(
      (item) => item.status === "complete" || item.status === "degraded",
    );
    const expectedExcluded = usable.filter((item) =>
      DECISION_SUMMARY_OBSERVATION_KEYS.has(item.key),
    ).length;

    expect(decision).toBeDefined();
    expect(decision?.result.observation_excluded_count).toBe(expectedExcluded);
    expect(decision?.result.observation_excluded_count).toBe(5);
    expect(decision?.tone).toBe("positive");
    expect(decision?.score).toBe(43);
    expect(decision?.result.positive_count).toBe(1);
    expect(decision?.result.negative_count).toBe(0);
  });
});
