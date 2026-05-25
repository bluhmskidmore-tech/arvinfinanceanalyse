import { describe, expect, it, vi } from "vitest";

import {
  AgentDisabledError,
  buildStableDemoAgentEnvelope,
  createDemoAgentClient,
  createRealAgentClient,
} from "../api/agentClient";
import { createApiClient } from "../api/client";

describe("AgentClient", () => {
  it("returns a stable mock envelope from createApiClient mock mode", async () => {
    const client = createApiClient({ mode: "mock" });
    const env = await client.queryAgent({ question: "测试问题" });
    expect(env.answer).toBe("Agent 当前为演示模式");
    expect(env.evidence.quality_flag).toBe("ok");
    expect(Array.isArray(env.suggested_actions)).toBe(true);
  });

  it("buildStableDemoAgentEnvelope matches contract shape", () => {
    const env = buildStableDemoAgentEnvelope();
    expect(env.result_meta.trace_id).toBeTruthy();
    expect(env.cards).toEqual([]);
  });

  it("returns the stable mock envelope from createDemoAgentClient", async () => {
    const delay = vi.fn(async () => undefined);
    const client = createDemoAgentClient(delay);

    const env = await client.queryAgent({ question: "测试问题" });

    expect(delay).toHaveBeenCalledOnce();
    expect(env.answer).toBe("Agent 当前为演示模式");
    expect(env.cards).toEqual([]);
    expect(env.result_meta.result_kind).toBe("agent.frontend_mock");
    expect(env.result_meta.generated_at).toBeTruthy();
  });

  it("throws AgentDisabledError on 503 disabled payload", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ enabled: false, phase: "phase1", detail: "disabled" }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = createRealAgentClient({
      fetchImpl: fetchImpl as unknown as typeof fetch,
      baseUrl: "http://example.test",
    });
    await expect(client.queryAgent({ question: "x" })).rejects.toBeInstanceOf(AgentDisabledError);
  });

  it("parses successful AgentEnvelope JSON", async () => {
    const envelope = buildStableDemoAgentEnvelope();
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify(envelope), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = createRealAgentClient({
      fetchImpl: fetchImpl as unknown as typeof fetch,
      baseUrl: "http://example.test",
    });
    const out = await client.queryAgent({ question: "你好" });
    expect(out.answer).toBe(envelope.answer);
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://example.test/api/agent/query",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
