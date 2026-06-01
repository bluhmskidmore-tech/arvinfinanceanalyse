import { screen } from "@testing-library/react";
import { vi } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import type { ResultMeta } from "../api/contracts";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

function buildMeta(): ResultMeta {
  return {
    trace_id: "tr_agent_placeholder",
    basis: "mock",
    result_kind: "workbench.agent",
    formal_use_allowed: false,
    source_version: "sv_agent_reserved",
    vendor_version: "vv_none",
    rule_version: "rv_agent_reserved",
    cache_version: "cv_agent_reserved",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-05-01T00:00:00Z",
  };
}

function buildAgentPlaceholderClient(): ApiClient {
  const base = createApiClient({ mode: "mock" });
  return {
    ...base,
    getPlaceholderSnapshot: vi.fn(async (key: string) => ({
      result_meta: buildMeta(),
      result: {
        title: key === "agent" ? "Agent reserved" : "Unexpected placeholder",
        summary: "The Agent surface remains outside the current cutover boundary.",
        highlights: ["Reserved route", "No live Agent query controls"],
      },
    })),
  };
}

describe("/agent route", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the live Agent workbench on direct route access", async () => {
    const client = buildAgentPlaceholderClient();

    renderWorkbenchApp(["/agent"], { client });

    expect(await screen.findByLabelText("agent-question-input")).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
    expect(client.getPlaceholderSnapshot).not.toHaveBeenCalled();
  });

  it("does not call the Agent endpoint until the user submits a query", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({}), {
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderWorkbenchApp(["/agent"], { client: buildAgentPlaceholderClient() });

    expect(await screen.findByLabelText("agent-question-input")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
