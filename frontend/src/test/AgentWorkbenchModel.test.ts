import { describe, expect, it } from "vitest";

import {
  buildGovernanceNotices,
  isAgentEvidence,
  isAgentQueryResult,
  isAgentResultCard,
  isAgentRunPayload,
  normalizeAgentResult,
  normalizeAgentRunPayload,
  type AgentQueryResult,
} from "../features/agent/lib/agentWorkbenchModel";

function buildResult(
  evidenceStrength: "governed_moss" | "provider_runtime" | "local_fallback" | "mixed",
) {
  return {
    answer: "测试回答",
    cards: [],
    evidence: {
      tables_used: [],
      filters_applied: {},
      sql_executed: [],
      evidence_rows: 0,
      quality_flag: evidenceStrength === "governed_moss" ? "ok" : "warning",
      evidence_strength: evidenceStrength,
    },
    result_meta: {
      result_kind: "agent.test",
      formal_use_allowed: false,
    },
    next_drill: [],
    suggested_actions: [],
  } satisfies AgentQueryResult;
}

describe("agent workbench evidence governance", () => {
  it("warns when a result only carries provider runtime evidence", () => {
    expect(buildGovernanceNotices(buildResult("provider_runtime"))).toContain(
      "当前仅有外部模型与工具运行证据，未证明 MOSS 指标口径",
    );
  });

  it("warns when a result comes from the local fallback", () => {
    expect(buildGovernanceNotices(buildResult("local_fallback"))).toContain(
      "当前为本地降级回答，未运行受治理指标查询",
    );
  });

  it("warns when an external answer uses governed MOSS context", () => {
    expect(buildGovernanceNotices(buildResult("mixed"))).toContain(
      "当前回答由外部模型基于 MOSS 只读上下文生成，不等同受治理指标结论",
    );
  });

  it("keeps stored results without evidence_strength readable", () => {
    expect(
      isAgentEvidence({
        tables_used: [],
        filters_applied: {},
        evidence_rows: 0,
        quality_flag: "warning",
      }),
    ).toBe(true);
  });
});

describe("agent result guard and normalization compatibility", () => {
  it("accepts stored results without suggested actions and normalizes them in place", () => {
    const storedResult = {
      answer: "历史回答",
      cards: [],
      evidence: {
        tables_used: [],
        filters_applied: {},
        evidence_rows: 0,
        quality_flag: "ok",
      },
      result_meta: {},
      next_drill: [],
    };

    expect(isAgentQueryResult(storedResult)).toBe(true);
    if (!isAgentQueryResult(storedResult)) {
      throw new Error("expected stored result to remain readable");
    }

    const normalized = normalizeAgentResult(storedResult);

    expect(normalized).toBe(storedResult);
    expect(normalized.suggested_actions).toEqual([]);
  });

  it("normalizes a stored run result without replacing either payload object", () => {
    const storedRun = {
      run_id: "agent_run:stored",
      status: "completed",
      result: {
        answer: "历史回答",
        cards: [],
        evidence: {
          tables_used: [],
          filters_applied: {},
          evidence_rows: 0,
          quality_flag: "ok",
        },
        result_meta: {},
        next_drill: [],
      },
    };

    expect(isAgentRunPayload(storedRun)).toBe(true);
    if (!isAgentRunPayload(storedRun)) {
      throw new Error("expected stored run to remain readable");
    }
    const originalResult = storedRun.result;

    const normalized = normalizeAgentRunPayload(storedRun);

    expect(normalized).toBe(storedRun);
    expect(normalized.result).toBe(originalResult);
    expect(normalized.result?.suggested_actions).toEqual([]);
  });

  it("preserves existing card data acceptance semantics", () => {
    expect(
      isAgentResultCard({
        title: "明细",
        value: null,
        type: "table",
        data: [{ name: "有效行" }],
        spec: {},
      }),
    ).toBe(true);
    expect(
      isAgentResultCard({
        title: "明细",
        type: "table",
        data: [{ name: "有效行" }, null],
      }),
    ).toBe(true);
    expect(
      isAgentResultCard({
        title: "明细",
        type: "table",
        data: "invalid",
      }),
    ).toBe(false);
  });

  it("rejects malformed suggested actions inside an otherwise valid result", () => {
    expect(
      isAgentQueryResult({
        ...buildResult("governed_moss"),
        suggested_actions: [
          {
            type: "execute_intent",
            label: "执行",
            payload: null,
            requires_confirmation: true,
          },
        ],
      }),
    ).toBe(false);
  });
});
