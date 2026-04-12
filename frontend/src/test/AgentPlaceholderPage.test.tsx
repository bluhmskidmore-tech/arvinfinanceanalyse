import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWorkbenchApp } from "./renderWorkbenchApp";

function buildJsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

describe("/agent route", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the agent workbench shell without issuing a query on load", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      buildJsonResponse({}),
    );

    renderWorkbenchApp(["/agent"]);

    expect(
      await screen.findByRole("heading", { name: "Agent 工作台" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("输入自然语言问题，Agent 路由到已有分析服务返回结构化结果。"),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("例如：组合概览、损益汇总、久期风险、信用集中度..."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "查询" }),
    ).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("posts the manual query payload and renders answer, cards, evidence, and drill suggestions", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      buildJsonResponse({
        answer: "组合久期风险主要集中在 3Y-5Y 桶位，久期贡献高于其他期限段。",
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
          trace_id: "tr_agent_query_001",
        },
        next_drill: [
          { dimension: "portfolio", label: "按组合下钻" },
          { dimension: "tenor_bucket", label: "按期限桶下钻" },
        ],
      }),
    );

    renderWorkbenchApp(["/agent"]);

    await user.type(
      await screen.findByPlaceholderText(
        "例如：组合概览、损益汇总、久期风险、信用集中度...",
      ),
      "久期风险",
    );
    await user.click(screen.getByRole("button", { name: "查询" }));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledTimes(1);
    });

    const [url, options] = fetchSpy.mock.calls[0] ?? [];
    expect(url).toBe("/api/agent/query");
    expect(options?.method).toBe("POST");
    expect(options?.headers).toEqual({
      "Content-Type": "application/json",
    });
    expect(JSON.parse(String(options?.body))).toEqual({
      question: "久期风险",
      basis: "formal",
      filters: {},
      position_scope: "all",
      currency_basis: "CNY",
      context: {
        user_id: "web-user",
      },
    });

    expect(
      await screen.findByText("组合久期风险主要集中在 3Y-5Y 桶位，久期贡献高于其他期限段。"),
    ).toBeInTheDocument();
    expect(screen.getByText("组合久期")).toBeInTheDocument();
    expect(screen.getByText("4.27")).toBeInTheDocument();
    expect(screen.getByText("duration")).toBeInTheDocument();
    expect(screen.getByText("DV01")).toBeInTheDocument();
    expect(screen.getByText("128.5万")).toBeInTheDocument();
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
  });

  it("shows the phase-1 disabled banner when the backend returns 503 disabled", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      buildJsonResponse(
        {
          enabled: false,
          phase: "phase1",
          detail: "agent is not enabled",
        },
        503,
      ),
    );

    renderWorkbenchApp(["/agent"]);

    await user.type(
      await screen.findByPlaceholderText(
        "例如：组合概览、损益汇总、久期风险、信用集中度...",
      ),
      "组合概览",
    );
    await user.click(screen.getByRole("button", { name: "查询" }));

    expect(
      await screen.findByText(
        "Agent 当前未启用。设置环境变量 MOSS_AGENT_ENABLED=true 后重启后端即可使用。",
      ),
    ).toBeInTheDocument();
  });
});
