import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClientProvider, createApiClient } from "../api/client";
import { createRealAgentClient } from "../api/agentClient";
import { createDeferredApiClient } from "../api/clientContext";
import type { AgentModelCatalog } from "../api/contracts/agent";
import AgentWorkbenchPage from "../features/agent/AgentWorkbenchPage";

const catalog: AgentModelCatalog = {
  provider: "openai-codex", default_model: "gpt-test", source: "live",
  models: [
    { id: "gpt-test", label: "Test model", reasoning_efforts: ["low", "high"], default_reasoning_effort: "low" },
    { id: "gpt-other", label: "Other model", reasoning_efforts: ["medium"], default_reasoning_effort: "medium" },
  ],
};

afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

async function selectOption(label: string, name: string) {
  fireEvent.mouseDown(screen.getByRole("combobox", { name: label }));
  fireEvent.click(await screen.findByRole("option", { name }));
}

function expectSelection(label: string, name: string) {
  expect(screen.getByRole("combobox", { name: label }).closest(".ant-select")).toHaveTextContent(name);
}

describe("Chat model selection", () => {
  it("opens composer tools from the icon and closes them on Escape or focus leaving the panel", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getAgentModels").mockResolvedValue(catalog);
    const send = vi.spyOn(client, "createAgentRun");
    const query = vi.spyOn(client, "queryAgent");
    render(<ApiClientProvider client={client}><AgentWorkbenchPage /></ApiClientProvider>);
    await user.type(screen.getByLabelText("向 Agent 提问"), "保留这条草稿");
    const trigger = screen.getByLabelText("高级工具", { selector: "summary" });
    const tools = trigger.closest("details");
    await user.click(trigger);
    expect(tools).toHaveAttribute("open");
    await user.click(screen.getByLabelText("GitNexus 仓库路径"));
    expect(tools).toHaveAttribute("open");
    await user.keyboard("{Enter}");
    expect(send).not.toHaveBeenCalled();
    expect(query).not.toHaveBeenCalled();
    expect(screen.getByLabelText("向 Agent 提问")).toHaveValue("保留这条草稿");
    await user.keyboard("{Escape}");
    expect(tools).not.toHaveAttribute("open");
    expect(trigger).toHaveFocus();
    await user.click(trigger);
    await user.click(screen.getByLabelText("向 Agent 提问"));
    expect(tools).not.toHaveAttribute("open");
    expect(screen.getByLabelText("向 Agent 提问")).toHaveFocus();
  });

  it("loads once with the production deferred client even when its method identity changes", async () => {
    const fetchImpl = vi.fn().mockImplementation(async () => new Response(JSON.stringify(catalog), { status: 200 }));
    const client = createDeferredApiClient({ mode: "real", fetchImpl });
    render(<ApiClientProvider client={client}><AgentWorkbenchPage /></ApiClientProvider>);
    await waitFor(() => expect(screen.getByRole("combobox", { name: "选择模型" })).toBeEnabled());
    fireEvent.change(screen.getByLabelText("向 Agent 提问"), { target: { value: "draft" } });
    await selectOption("思考程度", "深入思考");
    expect(screen.getByRole("combobox", { name: "选择模型" })).toBeEnabled();
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("sends the selected model and supported effort, and preserves the choice after remount", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getAgentModels").mockResolvedValue(catalog);
    const send = vi.spyOn(client, "createAgentRun");
    const query = vi.spyOn(client, "queryAgent");
    const view = render(<ApiClientProvider client={client}><AgentWorkbenchPage /></ApiClientProvider>);
    await waitFor(() => expectSelection("选择模型", "Test model"));
    await selectOption("思考程度", "深入思考");
    await selectOption("选择模型", "Other model");
    expectSelection("思考程度", "均衡思考");
    expect(screen.queryByRole("option", { name: "深入思考" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("向 Agent 提问"), { target: { value: "解释彩虹如何形成" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    await waitFor(() => expect(send).toHaveBeenCalledWith(expect.objectContaining({
      question: "解释彩虹如何形成", model: "gpt-other", reasoning_effort: "medium", routing_surface: "standalone_workbench",
    })));
    expect(query).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.getByRole("button", { name: "发送" })).toBeInTheDocument());
    view.unmount();
    render(<ApiClientProvider client={client}><AgentWorkbenchPage /></ApiClientProvider>);
    await waitFor(() => expectSelection("选择模型", "Other model"));
    expectSelection("思考程度", "均衡思考");
  });

  it("reports catalog failure and omits obsolete preferences from the request", async () => {
    localStorage.setItem("moss.agent.model-selection.v1", JSON.stringify({ model: "removed-model", reasoning_effort: "ultra" }));
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getAgentModels").mockRejectedValue(new Error("offline"));
    const send = vi.spyOn(client, "createAgentRun");
    render(<ApiClientProvider client={client}><AgentWorkbenchPage /></ApiClientProvider>);
    expect(await screen.findByText(/模型列表暂不可用/)).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "选择模型" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("向 Agent 提问"), { target: { value: "解释彩虹如何形成" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    await waitFor(() => expect(send).toHaveBeenCalled());
    expect(send.mock.calls[0][0]).not.toHaveProperty("model");
    expect(send.mock.calls[0][0]).not.toHaveProperty("reasoning_effort");
    await waitFor(() => expect(screen.getByRole("button", { name: "发送" })).toBeInTheDocument());
  });

  it("loads the catalog through the Agent domain client", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(JSON.stringify(catalog), { status: 200 }));
    const client = createRealAgentClient({ fetchImpl, baseUrl: "" });
    expect(await client.getAgentModels()).toEqual(catalog);
    expect(fetchImpl).toHaveBeenCalledWith("/api/agent/models", expect.objectContaining({ method: "GET" }));
  });

  it("searches models with the keyboard, preserves the draft and returns focus to the composer", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getAgentModels").mockResolvedValue(catalog);
    const send = vi.spyOn(client, "createAgentRun");
    render(<ApiClientProvider client={client}><AgentWorkbenchPage /></ApiClientProvider>);
    await user.type(screen.getByLabelText("向 Agent 提问"), "保留草稿");
    await waitFor(() => expectSelection("选择模型", "Test model"));
    const models = screen.getByRole("combobox", { name: "选择模型" });
    await user.click(models);
    await user.type(models, "Other");
    expect(await screen.findByRole("option", { name: "Other model" })).toBeVisible();
    expect(screen.queryByRole("option", { name: "Test model" })).not.toBeInTheDocument();
    fireEvent.keyDown(models, { key: "ArrowDown", keyCode: 40 });
    fireEvent.keyDown(models, { key: "Enter", keyCode: 13 });
    await waitFor(() => expectSelection("选择模型", "Other model"));
    await waitFor(() => expect(screen.getByLabelText("向 Agent 提问")).toHaveFocus());
    expect(screen.getByLabelText("向 Agent 提问")).toHaveValue("保留草稿");
    expect(send).not.toHaveBeenCalled();
  });

  it("does not send an IME candidate confirmation with a missing composing flag", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getAgentModels").mockResolvedValue(catalog);
    const send = vi.spyOn(client, "createAgentRun");
    render(<ApiClientProvider client={client}><AgentWorkbenchPage /></ApiClientProvider>);
    const input = screen.getByLabelText("向 Agent 提问");
    fireEvent.change(input, { target: { value: "中文草稿" } });
    fireEvent.compositionStart(input);
    fireEvent.keyDown(input, { key: "Enter", isComposing: false });
    fireEvent.compositionEnd(input);
    fireEvent.keyDown(input, { key: "Enter", keyCode: 229, isComposing: false });
    expect(send).not.toHaveBeenCalled();
    expect(input).toHaveValue("中文草稿");
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(send).toHaveBeenCalledOnce());
    await waitFor(() => expect(screen.getByRole("button", { name: "发送" })).toBeInTheDocument());
  });
});
