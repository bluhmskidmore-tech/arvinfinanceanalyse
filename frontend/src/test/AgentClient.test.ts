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
    const env = await client.queryAgent({ question: "test question" });
    expect(env.answer).toBe("Agent is running in demo mode.");
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

    const env = await client.queryAgent({ question: "test question" });

    expect(delay).toHaveBeenCalledOnce();
    expect(env.answer).toBe("Agent is running in demo mode.");
    expect(env.cards).toEqual([]);
    expect(env.result_meta.result_kind).toBe("agent.frontend_mock");
    expect(env.result_meta.generated_at).toBeTruthy();
  });

  it("returns a completed demo run without network in createDemoAgentClient", async () => {
    const delay = vi.fn(async () => undefined);
    const client = createDemoAgentClient(delay);

    const run = await client.createAgentRun({ question: "demo run" });

    expect(delay).toHaveBeenCalledOnce();
    expect(run).toMatchObject({
      run_id: "agent_run:frontend_mock",
      status: "completed",
      question: "demo run",
      result: {
        result_meta: {
          result_kind: "agent.frontend_mock",
        },
      },
    });
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

  it("throws AgentApiError with payload on non-ok run creation", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ detail: "Agent runs require MOSS_AGENT_PROVIDER=hermes." }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = createRealAgentClient({
      fetchImpl: fetchImpl as unknown as typeof fetch,
      baseUrl: "http://example.test",
    });

    await expect(client.createAgentRun({ question: "x" })).rejects.toMatchObject({
      name: "AgentApiError",
      status: 400,
      path: "/api/agent/runs",
      payload: { detail: "Agent runs require MOSS_AGENT_PROVIDER=hermes." },
    });
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
    const out = await client.queryAgent({ question: "hello" });
    expect(out.answer).toBe(envelope.answer);
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://example.test/api/agent/query",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("uses baseUrl for agent run endpoints", async () => {
    const runPayload = { run_id: "agent_run:test", status: "completed", result: null };
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify(runPayload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = createRealAgentClient({
      fetchImpl: fetchImpl as unknown as typeof fetch,
      baseUrl: "http://example.test/base",
    });

    await expect(client.getAgentRun("agent_run:test")).resolves.toEqual(runPayload);

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://example.test/base/api/agent/runs/agent_run%3Atest",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("posts to the cancel endpoint with the encoded run id", async () => {
    const cancelledPayload = { run_id: "agent_run:test", status: "cancelled", result: null };
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify(cancelledPayload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = createRealAgentClient({
      fetchImpl: fetchImpl as unknown as typeof fetch,
      baseUrl: "http://example.test/base",
    });

    await expect(client.cancelAgentRun("agent_run:test")).resolves.toEqual(cancelledPayload);

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://example.test/base/api/agent/runs/agent_run%3Atest/cancel",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("returns a cancelled demo run without network in createDemoAgentClient", async () => {
    const delay = vi.fn(async () => undefined);
    const client = createDemoAgentClient(delay);

    const run = await client.cancelAgentRun("agent_run:demo");

    expect(delay).toHaveBeenCalledOnce();
    expect(run).toMatchObject({
      run_id: "agent_run:demo",
      status: "cancelled",
      result: null,
    });
  });
});
