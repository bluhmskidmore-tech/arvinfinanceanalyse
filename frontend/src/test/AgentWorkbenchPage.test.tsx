import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AgentWorkbenchPage from "../features/agent/AgentWorkbenchPage";

const AGENT_PLACEHOLDER =
  "例如：组合概览、损益汇总、久期风险、信用集中度、GitNexus 仓库图谱...";
const GITNEXUS_STATUS_BUTTON = "GitNexus 状态";
const GITNEXUS_CONTEXT_BUTTON = "GitNexus context";
const GITNEXUS_PROCESSES_BUTTON = "GitNexus processes";

function buildJsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("AgentWorkbenchPage", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("advertises GitNexus repo graph as a supported query example", () => {
    render(<AgentWorkbenchPage />);

    expect(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
    ).toBeInTheDocument();
  });

  it("renders explicit repo_path input and GitNexus quick examples", () => {
    render(<AgentWorkbenchPage />);

    expect(screen.getByLabelText("repo-path-input")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: GITNEXUS_STATUS_BUTTON })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: GITNEXUS_CONTEXT_BUTTON })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: GITNEXUS_PROCESSES_BUTTON })).toBeInTheDocument();
  });

  it("submits explicit repo_path in filters when provided", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "GitNexus ok",
        cards: [],
        evidence: {
          tables_used: [".gitnexus/meta.json"],
          filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
          evidence_rows: 1,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_gitnexus",
          basis: "analytical",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByLabelText("repo-path-input"), "F:\\MOSS-SYSTEM-V1");
    await user.type(
      screen.getByPlaceholderText(AGENT_PLACEHOLDER),
      "请给我看 GitNexus context",
    );
    await user.click(screen.getByRole("button", { name: "查询" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/agent/query",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            question: "请给我看 GitNexus context",
            basis: "formal",
            filters: { repo_path: "F:\\MOSS-SYSTEM-V1" },
            position_scope: "all",
            currency_basis: "CNY",
            context: {
              user_id: "web-user",
            },
          }),
        }),
      );
    });
  });

  it("clicking GitNexus quick example fills the query box", async () => {
    const user = userEvent.setup();
    render(<AgentWorkbenchPage />);

    await user.click(screen.getByRole("button", { name: GITNEXUS_PROCESSES_BUTTON }));

    expect(screen.getByPlaceholderText(AGENT_PLACEHOLDER)).toHaveValue("请给我看 GitNexus processes");
  });

  it("shows validation error when submitting with empty input", async () => {
    const user = userEvent.setup();
    render(<AgentWorkbenchPage />);

    await user.click(screen.getByRole("button", { name: "查询" }));

    expect(
      screen.getByText("请输入查询问题。"),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows disabled banner when backend returns 503 with enabled:false", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse(
        {
          enabled: false,
          phase: "phase1",
          detail: "agent is not enabled",
        },
        503,
      ),
    );

    render(<AgentWorkbenchPage />);

    await user.type(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
      "test",
    );
    await user.click(screen.getByRole("button", { name: "查询" }));

    expect(
      await screen.findByText(
        "Agent 当前未启用。设置环境变量 MOSS_AGENT_ENABLED=true 后重启后端即可使用。",
      ),
    ).toBeInTheDocument();
  });

  it("shows request error on non-OK response", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse({}, 500));

    render(<AgentWorkbenchPage />);

    await user.type(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
      "q",
    );
    await user.click(screen.getByRole("button", { name: "查询" }));

    expect(
      await screen.findByText("Agent 查询失败（500）"),
    ).toBeInTheDocument();
  });

  it("shows request error when fetch throws", async () => {
    const user = userEvent.setup();
    fetchMock.mockRejectedValueOnce(new Error("network down"));

    render(<AgentWorkbenchPage />);

    await user.type(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
      "q",
    );
    await user.click(screen.getByRole("button", { name: "查询" }));

    expect(await screen.findByText("network down")).toBeInTheDocument();
  });

  it("shows format error when response is 200 but body is not AgentQueryResult", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({ answer: "only answer" }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
      "q",
    );
    await user.click(screen.getByRole("button", { name: "查询" }));

    expect(
      await screen.findByText("Agent 返回结果格式无效。"),
    ).toBeInTheDocument();
  });

  it("renders answer, cards, evidence, next_drill, and result_meta on success", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "组合久期风险主要集中在 3Y-5Y。",
        cards: [
          { title: "组合久期", value: "4.27", type: "duration" },
          { title: "DV01", value: "128.5万", type: "risk" },
        ],
        evidence: {
          tables_used: ["fact_risk_tensor", "dim_portfolio"],
          filters_applied: { currency_basis: "CNY" },
          evidence_rows: 42,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_1",
          basis: "formal",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [
          { dimension: "portfolio", label: "按组合下钻" },
          { dimension: "tenor_bucket", label: "按期限桶下钻" },
        ],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
      "久期",
    );
    await user.click(screen.getByRole("button", { name: "查询" }));

    expect(
      await screen.findByText("组合久期风险主要集中在 3Y-5Y。"),
    ).toBeInTheDocument();
    expect(screen.getByText("组合久期")).toBeInTheDocument();
    expect(screen.getByText("4.27")).toBeInTheDocument();
    expect(screen.getByText("duration")).toBeInTheDocument();
    expect(screen.getByText("证据链")).toBeInTheDocument();
    expect(
      screen.getByText(/tables: fact_risk_tensor, dim_portfolio/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/filters: \{"currency_basis":"CNY"\}/),
    ).toBeInTheDocument();
    expect(screen.getByText(/rows: 42/)).toBeInTheDocument();
    expect(screen.getByText(/quality: ok/)).toBeInTheDocument();
    expect(screen.getByText("按组合下钻")).toBeInTheDocument();
    expect(screen.getByText("按期限桶下钻")).toBeInTheDocument();
    expect(screen.getByText("结果元信息")).toBeInTheDocument();
    expect(screen.getByText(/trace_id: tr_1/)).toBeInTheDocument();
    expect(screen.getByText(/basis: formal/)).toBeInTheDocument();
    expect(screen.getByText(/generated_at: 2026-04-12T09:00:00Z/)).toBeInTheDocument();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/agent/query",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("shows empty-renderable fallback when payload is valid but nothing to display", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "   ",
        cards: [],
        evidence: {
          tables_used: [],
          filters_applied: {},
          evidence_rows: 0,
          quality_flag: "",
        },
        result_meta: { trace_id: "tr_empty" },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
      "x",
    );
    await user.click(screen.getByRole("button", { name: "查询" }));

    expect(
      await screen.findByText("本次查询未返回可展示结果。请调整问题后重试。"),
    ).toBeInTheDocument();
    expect(screen.getByText(/trace_id: tr_empty/)).toBeInTheDocument();
  });
});
