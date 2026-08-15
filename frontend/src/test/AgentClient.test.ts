import { describe, expect, it, vi } from "vitest";

import {
  AgentDisabledError,
  buildStableDemoAgentEnvelope,
  createDemoAgentClient,
  createRealAgentClient,
  type AgentClientMethods,
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
      new Response(JSON.stringify({ detail: "Run creation rejected." }), {
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
      payload: { detail: "Run creation rejected." },
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

  it.each([
    [
      "listAgentProjects",
      (client: AgentClientMethods) => client.listAgentProjects(),
      "/base/api/agent/projects",
    ],
    [
      "listAgentProjects with includeArchived",
      (client: AgentClientMethods) => client.listAgentProjects({ includeArchived: true }),
      "/base/api/agent/projects?include_archived=true",
    ],
    [
      "getAgentProject",
      (client: AgentClientMethods) => client.getAgentProject("agent_project:a/b"),
      "/base/api/agent/projects/agent_project%3Aa%2Fb",
    ],
    [
      "listAgentConversations",
      (client: AgentClientMethods) => client.listAgentConversations("agent_project:a"),
      "/base/api/agent/projects/agent_project%3Aa/conversations",
    ],
    [
      "getAgentConversation",
      (client: AgentClientMethods) => client.getAgentConversation("agent_conversation:a"),
      "/base/api/agent/conversations/agent_conversation%3Aa",
    ],
    [
      "listAgentConversationMessages",
      (client: AgentClientMethods) => client.listAgentConversationMessages("agent_conversation:a"),
      "/base/api/agent/conversations/agent_conversation%3Aa/messages",
    ],
    [
      "listAgentConversationArtifacts",
      (client: AgentClientMethods) => client.listAgentConversationArtifacts("agent_conversation:a"),
      "/base/api/agent/conversations/agent_conversation%3Aa/artifacts",
    ],
    [
      "getAgentArtifact",
      (client: AgentClientMethods) => client.getAgentArtifact("agent_artifact:a"),
      "/base/api/agent/artifacts/agent_artifact%3Aa",
    ],
  ])("issues a GET with encoded ids and passes the payload through for %s", async (_label, invoke, expectedUrl) => {
    const probePayload = { probe: "workspace-read" };
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify(probePayload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = createRealAgentClient({
      fetchImpl: fetchImpl as unknown as typeof fetch,
      baseUrl: "/base",
    });

    await expect(invoke(client)).resolves.toEqual(probePayload);

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(fetchImpl).toHaveBeenCalledWith(
      expectedUrl,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("throws AgentDisabledError when a workspace read hits the flat 503 disabled body", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ enabled: false, phase: "phase1", detail: "disabled" }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = createRealAgentClient({
      fetchImpl: fetchImpl as unknown as typeof fetch,
      baseUrl: "",
    });

    await expect(client.listAgentProjects()).rejects.toBeInstanceOf(AgentDisabledError);
  });

  it("surfaces the structured 409 corrupt-record detail through AgentApiError", async () => {
    const corruptDetail = {
      code: "AGENT_WORKSPACE_RECORD_CORRUPT",
      message: "Agent workspace record is corrupt and cannot be read.",
    };
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ detail: corruptDetail }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = createRealAgentClient({
      fetchImpl: fetchImpl as unknown as typeof fetch,
      baseUrl: "",
    });

    await expect(client.getAgentConversation("agent_conversation:x")).rejects.toMatchObject({
      name: "AgentApiError",
      status: 409,
      path: "/api/agent/conversations/agent_conversation%3Ax",
      payload: { detail: corruptDetail },
    });
  });

  it("serves stable contract-shaped workspace reads from createDemoAgentClient", async () => {
    const delay = vi.fn(async () => undefined);
    const client = createDemoAgentClient(delay);

    const projects = await client.listAgentProjects();
    expect(projects.corrupt_records).toBe(0);
    expect(projects.items).toHaveLength(1);
    expect(projects.items[0]).toMatchObject({
      project_id: "agent_project:frontend_mock",
      default_scope: "all",
      default_currency_basis: "CNY",
      archived_at: null,
    });

    const archivedIncluded = await client.listAgentProjects({ includeArchived: true });
    expect(archivedIncluded.items).toHaveLength(2);
    expect(archivedIncluded.items[1]?.archived_at).not.toBeNull();

    const project = await client.getAgentProject("agent_project:x");
    expect(project.project_id).toBe("agent_project:x");

    const conversations = await client.listAgentConversations("agent_project:x");
    expect(conversations.items[0]?.conversation_id).toBe("agent_conversation:frontend_mock");

    const conversation = await client.getAgentConversation("agent_conversation:x");
    expect(conversation.conversation_id).toBe("agent_conversation:x");

    const messages = await client.listAgentConversationMessages("agent_conversation:x");
    expect(messages.items[0]).toMatchObject({
      conversation_id: "agent_conversation:x",
      role: "assistant",
      run_id: "agent_run:frontend_mock",
    });
    expect(messages.items[0]?.result?.result_meta.result_kind).toBe("agent.frontend_mock");

    const artifacts = await client.listAgentConversationArtifacts("agent_conversation:x");
    expect(artifacts.items[0]?.kind).toBe("agent_envelope");

    const artifact = await client.getAgentArtifact("agent_artifact:x");
    expect(artifact.artifact_id).toBe("agent_artifact:x");
    expect(artifact.content.result_meta).toEqual(artifact.result_meta);
    expect(delay).toHaveBeenCalledTimes(8);
  });
});
