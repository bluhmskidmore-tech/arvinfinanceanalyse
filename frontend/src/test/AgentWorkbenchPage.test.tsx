import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AgentWorkbenchPage, { AgentPanel } from "../features/agent/AgentWorkbenchPage";

const AGENT_PLACEHOLDER =
  "问一句业务问题，例如：今天损益为什么变动？当前久期风险在哪里？";
const PAGE_CONTEXT_PLACEHOLDER =
  "直接问当前页：主要结论？异常点？下一步复核什么？";
const GITNEXUS_STATUS_BUTTON = "GitNexus 状态";
const GITNEXUS_CONTEXT_BUTTON = "GitNexus 上下文";
const GITNEXUS_PROCESSES_BUTTON = "GitNexus 流程";
const RECENT_REPO_PATHS_KEY = "moss.agent.gitnexus.recentRepoPaths.v1";
const PINNED_REPO_PATHS_KEY = "moss.agent.gitnexus.pinnedRepoPaths.v1";
const MAX_PINNED_REPO_PATHS = 5;

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
    vi.useRealTimers();
    window.localStorage.clear();
  });

  it("advertises GitNexus repo graph as a supported query example", () => {
    render(<AgentWorkbenchPage />);

    expect(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
    ).toBeInTheDocument();
  });

  it("keeps the page shell while exposing AgentPanel as the reusable copilot body", () => {
    render(<AgentPanel />);

    expect(screen.queryByRole("heading", { name: "智能体对话" })).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText(AGENT_PLACEHOLDER)).toBeInTheDocument();
    expect(screen.getByLabelText("repo-path-input")).toBeInTheDocument();
  });

  it("renders explicit repo_path input and GitNexus quick examples", () => {
    render(<AgentWorkbenchPage />);

    expect(screen.getByLabelText("repo-path-input")).toBeInTheDocument();
    expect(screen.getByLabelText("process-search-input")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "固定当前仓库" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "读取流程" })).toBeInTheDocument();
    expect(screen.getByLabelText("process-name-select")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "解释当前页面的主要结论和风险点" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /组合概览/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: GITNEXUS_STATUS_BUTTON })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: GITNEXUS_CONTEXT_BUTTON })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: GITNEXUS_PROCESSES_BUTTON })).toBeInTheDocument();
  });

  it("pins the current repo and shows pinned/recent sections separately", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(
      RECENT_REPO_PATHS_KEY,
      JSON.stringify(["F:\\MOSS-SYSTEM-V1", "F:\\NEWMOSS"]),
    );

    render(<AgentWorkbenchPage />);

    await user.clear(screen.getByLabelText("repo-path-input"));
    await user.type(screen.getByLabelText("repo-path-input"), "F:\\PINNED-MOSS");
    await user.click(screen.getByRole("button", { name: "固定当前仓库" }));

    expect(screen.getByText("固定仓库")).toBeInTheDocument();
    expect(screen.getByText("最近仓库")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "F:\\PINNED-MOSS" })).toBeInTheDocument();
    expect(JSON.parse(window.localStorage.getItem(PINNED_REPO_PATHS_KEY) ?? "[]")).toEqual([
      "F:\\PINNED-MOSS",
    ]);
  });

  it("unpins a pinned repo without removing recent repos", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(
      PINNED_REPO_PATHS_KEY,
      JSON.stringify(["F:\\MOSS-SYSTEM-V1"]),
    );
    window.localStorage.setItem(
      RECENT_REPO_PATHS_KEY,
      JSON.stringify(["F:\\MOSS-SYSTEM-V1", "F:\\NEWMOSS"]),
    );

    render(<AgentWorkbenchPage />);

    await user.click(screen.getByRole("button", { name: "取消固定 F:\\MOSS-SYSTEM-V1" }));

    expect(screen.queryByRole("button", { name: "取消固定 F:\\MOSS-SYSTEM-V1" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "F:\\MOSS-SYSTEM-V1" })).toBeInTheDocument();
    expect(JSON.parse(window.localStorage.getItem(PINNED_REPO_PATHS_KEY) ?? "[]")).toEqual([]);
  });

  it("renders pinned repos even without recent repos and supports pinned ordering", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(
      PINNED_REPO_PATHS_KEY,
      JSON.stringify(["F:\\ALPHA", "F:\\BETA", "F:\\GAMMA"]),
    );

    render(<AgentWorkbenchPage />);

    expect(screen.getByText("固定仓库")).toBeInTheDocument();
    expect(screen.queryByText("最近仓库")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "上移固定仓库 F:\\GAMMA" }));

    expect(JSON.parse(window.localStorage.getItem(PINNED_REPO_PATHS_KEY) ?? "[]")).toEqual([
      "F:\\ALPHA",
      "F:\\GAMMA",
      "F:\\BETA",
    ]);
  });

  it("pins directly from recent repos, de-duplicates sections, and caps pinned repos", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(
      PINNED_REPO_PATHS_KEY,
      JSON.stringify([
        "F:\\PINNED-1",
        "F:\\PINNED-2",
        "F:\\PINNED-3",
        "F:\\PINNED-4",
        "F:\\PINNED-5",
      ]),
    );
    window.localStorage.setItem(
      RECENT_REPO_PATHS_KEY,
      JSON.stringify(["F:\\PIN-ME", "F:\\RECENT-2"]),
    );

    render(<AgentWorkbenchPage />);

    await user.click(screen.getByRole("button", { name: "固定仓库 F:\\PIN-ME" }));

    expect(JSON.parse(window.localStorage.getItem(PINNED_REPO_PATHS_KEY) ?? "[]")).toEqual([
      "F:\\PIN-ME",
      "F:\\PINNED-1",
      "F:\\PINNED-2",
      "F:\\PINNED-3",
      "F:\\PINNED-4",
    ]);
    expect(JSON.parse(window.localStorage.getItem(PINNED_REPO_PATHS_KEY) ?? "[]")).toHaveLength(
      MAX_PINNED_REPO_PATHS,
    );
    expect(screen.queryByRole("button", { name: "固定仓库 F:\\PIN-ME" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "取消固定 F:\\PIN-ME" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "取消固定 F:\\PIN-ME" }));

    expect(screen.getByRole("button", { name: "固定仓库 F:\\PIN-ME" })).toBeInTheDocument();
  });

  it("auto-refreshes processes when repo_path changes", async () => {
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "GitNexus processes ready.",
        cards: [
          {
            title: "GitNexus Processes Table",
            type: "table",
            data: [{ name: "CheckoutFlow", type: "cross_community", steps: 6 }],
            spec: { columns: ["name", "type", "steps"] },
          },
        ],
        evidence: {
          tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/processes"],
          filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
          evidence_rows: 1,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_gitnexus_processes_auto",
          basis: "analytical",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    fireEvent.change(screen.getByLabelText("repo-path-input"), {
      target: { value: "F:\\MOSS-SYSTEM-V1" },
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/agent/query",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            question: "请给我看 GitNexus processes",
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
    }, { timeout: 2000 });
  });

  it("includes page_context when provided by the mounting page", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "已使用页面上下文。",
        cards: [],
        evidence: {
          tables_used: [],
          filters_applied: {},
          evidence_rows: 0,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_page_context",
          basis: "formal",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(
      <AgentWorkbenchPage
        pageContext={{
          page_id: "risk-dashboard",
          current_filters: { as_of_date: "2026-04-12", portfolio: "core" },
          selected_rows: [{ bond_code: "240001.IB" }],
          context_note: "selected from risk table",
        }}
      />,
    );

    expect(screen.getByText("页面上下文")).toBeInTheDocument();
    expect(screen.getByText(/risk-dashboard/)).toBeInTheDocument();
    expect(screen.getByText(/selected from risk table/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(PAGE_CONTEXT_PLACEHOLDER)).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText(PAGE_CONTEXT_PLACEHOLDER), "解释当前选择");
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
    const [, options] = fetchMock.mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      page_context: {
        page_id: "risk-dashboard",
        current_filters: { as_of_date: "2026-04-12", portfolio: "core" },
        selected_rows: [{ bond_code: "240001.IB" }],
        context_note: "selected from risk table",
      },
    });
  });

  it("loads process selector options from GitNexus processes response", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "GitNexus processes ready.",
        cards: [
          {
            title: "GitNexus Processes Table",
            type: "table",
            data: [
              { name: "CheckoutFlow", type: "cross_community", steps: 6 },
              { name: "AuditFlow", type: "intra_community", steps: 3 },
            ],
            spec: { columns: ["name", "type", "steps"] },
          },
        ],
        evidence: {
          tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/processes"],
          filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
          evidence_rows: 2,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_gitnexus_processes",
          basis: "analytical",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByLabelText("repo-path-input"), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: "读取流程" }));

    await waitFor(() => {
      const select = screen.getByLabelText("process-name-select") as HTMLSelectElement;
      expect(Array.from(select.options).map((option) => option.value)).toEqual([
        "",
        "CheckoutFlow",
        "AuditFlow",
      ]);
    });
  });

  it("submits selected process_name when viewing a chosen process", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(
        buildJsonResponse({
          answer: "GitNexus processes ready.",
          cards: [
            {
              title: "GitNexus Processes Table",
              type: "table",
              data: [{ name: "CheckoutFlow", type: "cross_community", steps: 6 }],
              spec: { columns: ["name", "type", "steps"] },
            },
          ],
          evidence: {
            tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/processes"],
            filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
            evidence_rows: 1,
            quality_flag: "ok",
          },
          result_meta: {
            trace_id: "tr_gitnexus_processes",
            basis: "analytical",
            generated_at: "2026-04-12T09:00:00Z",
          },
          next_drill: [],
        }),
      )
      .mockResolvedValueOnce(
        buildJsonResponse({
          answer: "GitNexus process ready.",
          cards: [
            {
              title: "GitNexus Process Trace",
              type: "table",
              data: [{ step: 1, symbol: "start_checkout", file: "backend/app/api.py" }],
              spec: { columns: ["step", "symbol", "file"] },
            },
          ],
          evidence: {
            tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/process/CheckoutFlow"],
            filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1", process_name: "CheckoutFlow" },
            evidence_rows: 1,
            quality_flag: "ok",
          },
          result_meta: {
            trace_id: "tr_gitnexus_process",
            basis: "analytical",
            generated_at: "2026-04-12T09:00:00Z",
          },
          next_drill: [],
        }),
      );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByLabelText("repo-path-input"), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: "读取流程" }));
    await waitFor(() => expect(screen.getByRole("option", { name: "CheckoutFlow" })).toBeInTheDocument());

    const processSelect = screen.getByLabelText("process-name-select");
    await user.selectOptions(processSelect, "CheckoutFlow");
    await waitFor(() => expect(processSelect).toHaveValue("CheckoutFlow"));
    await user.click(screen.getByRole("button", { name: "查看所选流程" }));

    await waitFor(() => {
      const expectedBody = JSON.stringify({
        question: "请给我看 GitNexus process/CheckoutFlow",
        basis: "formal",
        filters: { repo_path: "F:\\MOSS-SYSTEM-V1", process_name: "CheckoutFlow" },
        position_scope: "all",
        currency_basis: "CNY",
        context: {
          user_id: "web-user",
        },
      });
      const matched = fetchMock.mock.calls.some(
        (call) =>
          call[0] === "/api/agent/query" &&
          typeof call[1] === "object" &&
          call[1] !== null &&
          "body" in call[1] &&
          (call[1] as { body?: string }).body === expectedBody,
      );
      expect(matched).toBe(true);
    });
  });

  it("filters process options by keyword search", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "GitNexus processes ready.",
        cards: [
          {
            title: "GitNexus Processes Table",
            type: "table",
            data: [
              { name: "CheckoutFlow", type: "cross_community", steps: 6 },
              { name: "AuditFlow", type: "intra_community", steps: 3 },
              { name: "BalanceFlow", type: "cross_community", steps: 5 },
            ],
            spec: { columns: ["name", "type", "steps"] },
          },
        ],
        evidence: {
          tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/processes"],
          filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
          evidence_rows: 3,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_gitnexus_processes_filter",
          basis: "analytical",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByLabelText("repo-path-input"), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: "读取流程" }));
    await waitFor(() => expect(screen.getByRole("option", { name: "AuditFlow" })).toBeInTheDocument());

    await user.type(screen.getByLabelText("process-search-input"), "Audit");

    const select = screen.getByLabelText("process-name-select") as HTMLSelectElement;
    expect(Array.from(select.options).map((option) => option.value)).toEqual(["", "AuditFlow"]);
  });



  it("ignores a stale query response after a newer manual process load wins", async () => {
    vi.useFakeTimers();
    let resolveQueryResponse!: (value: Response) => void;
    const queryResponse = new Promise<Response>((resolve) => {
      resolveQueryResponse = resolve;
    });
    let resolveManualLoadResponse!: (value: Response) => void;
    const manualLoadResponse = new Promise<Response>((resolve) => {
      resolveManualLoadResponse = resolve;
    });
    fetchMock.mockReturnValueOnce(queryResponse).mockReturnValueOnce(manualLoadResponse);

    render(<AgentWorkbenchPage />);

    fireEvent.change(screen.getByLabelText("repo-path-input"), {
      target: { value: "F:\\MOSS-SYSTEM-V1" },
    });
    fireEvent.change(screen.getByPlaceholderText(AGENT_PLACEHOLDER), {
      target: { value: "GitNexus processes" },
    });
    const submitButton = document.querySelector('button[type="submit"]');
    if (!(submitButton instanceof HTMLButtonElement)) {
      throw new Error("query submit button not found");
    }
    fireEvent.click(submitButton);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    const manualProcessButton = screen
      .getAllByRole("button")
      .find((button) => button.textContent?.includes("读取"));
    if (!(manualProcessButton instanceof HTMLButtonElement)) {
      throw new Error("manual process button not found");
    }
    fireEvent.click(manualProcessButton);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    await act(async () => {
      resolveManualLoadResponse(
        buildJsonResponse({
          answer: "GitNexus processes ready.",
          cards: [
            {
              title: "GitNexus Processes Table",
              type: "table",
              data: [{ name: "NewestManualFlow", type: "cross_community", steps: 5 }],
              spec: { columns: ["name", "type", "steps"] },
            },
          ],
          evidence: {
            tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/processes"],
            filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
            evidence_rows: 1,
            quality_flag: "ok",
          },
          result_meta: {
            trace_id: "tr_gitnexus_processes_manual_current",
            basis: "analytical",
            generated_at: "2026-04-12T09:00:00Z",
          },
          next_drill: [],
        }),
      )
      await Promise.resolve()
    });

    let select = screen.getByLabelText("process-name-select") as HTMLSelectElement;
    expect(select).toHaveValue("NewestManualFlow");
    expect(Array.from(select.options).map((option) => option.value)).toEqual(["", "NewestManualFlow"]);

    await act(async () => {
      resolveQueryResponse(
        buildJsonResponse({
          answer: "GitNexus processes ready.",
          cards: [
            {
              title: "GitNexus Processes Table",
              type: "table",
              data: [{ name: "StaleQueryFlow", type: "cross_community", steps: 2 }],
              spec: { columns: ["name", "type", "steps"] },
            },
          ],
          evidence: {
            tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/processes"],
            filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
            evidence_rows: 1,
            quality_flag: "ok",
          },
          result_meta: {
            trace_id: "tr_gitnexus_processes_query_old",
            basis: "analytical",
            generated_at: "2026-04-12T09:00:00Z",
          },
          next_drill: [],
        }),
      )
      await Promise.resolve()
    });

    select = screen.getByLabelText("process-name-select") as HTMLSelectElement;
    expect(select).toHaveValue("NewestManualFlow");
    expect(Array.from(select.options).map((option) => option.value)).toEqual(["", "NewestManualFlow"]);
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
    await user.click(screen.getByRole("button", { name: "发送" }));

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

  it("loads remembered repo_path from localStorage", () => {
    window.localStorage.setItem(
      RECENT_REPO_PATHS_KEY,
      JSON.stringify(["F:\\MOSS-SYSTEM-V1", "F:\\NEWMOSS"]),
    );

    render(<AgentWorkbenchPage />);

    expect(screen.getByLabelText("repo-path-input")).toHaveValue("F:\\MOSS-SYSTEM-V1");
    expect(screen.getByRole("button", { name: "F:\\MOSS-SYSTEM-V1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "F:\\NEWMOSS" })).toBeInTheDocument();
  });

  it("persists recent repo_path after query", async () => {
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
    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "GitNexus context");
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(JSON.parse(window.localStorage.getItem(RECENT_REPO_PATHS_KEY) ?? "[]")).toEqual([
        "F:\\MOSS-SYSTEM-V1",
      ]);
    });
  });

  it("renders structured table cards instead of flattening them into metrics", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "GitNexus resources ready.",
        cards: [
          {
            title: "GitNexus Processes Table",
            type: "table",
            data: [
              { name: "CheckoutFlow", type: "cross_community", steps: 6 },
              { name: "AuditFlow", type: "intra_community", steps: 3 },
            ],
          },
          {
            title: "GitNexus Context",
            type: "resource",
            value: "gitnexus://repo/MOSS-SYSTEM-V1/context",
            data: [{ label: "project", value: "MOSS-SYSTEM-V1" }],
          },
          {
            title: "GitNexus Tools",
            type: "table",
            data: [{ tool: "query", description: "Process-grouped code intelligence" }],
            spec: { columns: ["tool", "description"] },
          },
          {
            title: "GitNexus Process Trace",
            type: "table",
            data: [
              {
                step: 1,
                symbol: "start_checkout",
                file: "backend/app/api.py",
                module_group: "api",
                edge_label: "api -> services",
              },
              {
                step: 2,
                symbol: "calculate_total",
                file: "backend/app/services/order.py",
                module_group: "services",
                edge_label: "services -> repositories",
              },
              {
                step: 3,
                symbol: "save_order",
                file: "backend/app/repositories/order_repo.py",
                module_group: "repositories",
                edge_label: "",
              },
            ],
            spec: { columns: ["step", "symbol", "file", "module_group", "edge_label"] },
          },
        ],
        evidence: {
          tables_used: [".gitnexus/meta.json"],
          filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
          evidence_rows: 2,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_gitnexus_cards",
          basis: "analytical",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "GitNexus context");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("上下文概览")).toBeInTheDocument();
    expect(screen.getByText("执行流程")).toBeInTheDocument();
    expect(screen.getByText("流程图")).toBeInTheDocument();
    expect(screen.getAllByText("CheckoutFlow").length).toBeGreaterThan(0);
    expect(
      screen.getByText((content) => content.includes("cross_community") && content.includes("步骤 6")),
    ).toBeInTheDocument();
    expect(screen.getByText(/api -> services/)).toBeInTheDocument();
    expect(screen.getByText(/services -> repositories/)).toBeInTheDocument();
    expect(screen.getAllByText("api").length).toBeGreaterThan(0);
    expect(screen.getAllByText("services").length).toBeGreaterThan(0);
    expect(screen.getAllByText("repositories").length).toBeGreaterThan(0);
    expect(screen.getByText("gitnexus://repo/MOSS-SYSTEM-V1/context")).toBeInTheDocument();
    expect(screen.getByText("Process-grouped code intelligence")).toBeInTheDocument();
    expect(screen.getByText("start_checkout")).toBeInTheDocument();
    expect(screen.getByText("calculate_total")).toBeInTheDocument();
    expect(screen.getByText("save_order")).toBeInTheDocument();
    expect(screen.getByText("步骤 1")).toBeInTheDocument();
    expect(screen.getByText("步骤 2")).toBeInTheDocument();
    expect(screen.getByText("步骤 3")).toBeInTheDocument();
  });

  it("renders process graph using backend-provided module_group and edge_label", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "GitNexus process ready.",
        cards: [
          {
            title: "GitNexus Process Trace",
            type: "table",
            data: [
              {
                step: 1,
                symbol: "start_checkout",
                file: "backend/app/api.py",
                module_group: "governance",
                edge_label: "governance -> orchestration",
              },
              {
                step: 2,
                symbol: "calculate_total",
                file: "backend/app/services/order.py",
                module_group: "core",
                edge_label: "core -> persistence",
              },
              {
                step: 3,
                symbol: "save_order",
                file: "backend/app/repositories/order_repo.py",
                module_group: "repositories",
                edge_label: "",
              },
            ],
            spec: { columns: ["step", "symbol", "file", "module_group", "edge_label"] },
          },
        ],
        evidence: {
          tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/process/CheckoutFlow"],
          filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1", process_name: "CheckoutFlow" },
          evidence_rows: 3,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_gitnexus_process_graph",
          basis: "analytical",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "GitNexus process");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("流程图")).toBeInTheDocument();
    expect(screen.getByText(/governance -> orchestration/)).toBeInTheDocument();
    expect(screen.getByText(/core -> persistence/)).toBeInTheDocument();
    expect(screen.getAllByText("governance").length).toBeGreaterThan(0);
    expect(screen.getAllByText("core").length).toBeGreaterThan(0);
    expect(screen.queryByText(/api -> services/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^api$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^services$/)).not.toBeInTheDocument();
  });

  it("renders GitNexus summary metrics inside the specialized view instead of generic card mixing", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "GitNexus status ready.",
        cards: [
          { title: "Repo", type: "metric", value: "F:\\MOSS-SYSTEM-V1" },
          { title: "Indexed At", type: "metric", value: "2026-04-12T09:00:00Z" },
          { title: "Nodes", type: "metric", value: "8462" },
          { title: "Edges", type: "metric", value: "23878" },
          {
            title: "GitNexus Context",
            type: "resource",
            value: "gitnexus://repo/MOSS-SYSTEM-V1/context",
            data: [{ label: "project", value: "MOSS-SYSTEM-V1" }],
          },
          {
            title: "GitNexus Processes Table",
            type: "table",
            data: [{ name: "CheckoutFlow", type: "cross_community", steps: 6 }],
            spec: { columns: ["name", "type", "steps"] },
          },
        ],
        evidence: {
          tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/context"],
          filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
          evidence_rows: 1,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_gitnexus_specialized_summary",
          result_kind: "agent.gitnexus_status",
          basis: "analytical",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "GitNexus status");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("索引摘要")).toBeInTheDocument();
    expect(screen.getByText("Repo")).toBeInTheDocument();
    expect(screen.getByText("F:\\MOSS-SYSTEM-V1")).toBeInTheDocument();
    expect(screen.getByText("Nodes")).toBeInTheDocument();
    expect(screen.getByText("8462")).toBeInTheDocument();
    expect(screen.getByText("Edges")).toBeInTheDocument();
    expect(screen.getByText("23878")).toBeInTheDocument();
    expect(screen.getByText("执行流程")).toBeInTheDocument();
    expect(screen.getByText("上下文概览")).toBeInTheDocument();
  });

  it("shows validation error when submitting with empty input", async () => {
    const user = userEvent.setup();
    render(<AgentWorkbenchPage />);

    await user.click(screen.getByRole("button", { name: "发送" }));

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
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(
      await screen.findByText(
        "智能体当前未启用。设置环境变量 MOSS_AGENT_ENABLED=true 后重启后端即可使用。",
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
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(
      await screen.findByText("智能体查询失败（500）"),
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
    await user.click(screen.getByRole("button", { name: "发送" }));

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
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(
      await screen.findByText("智能体返回结果格式无效。"),
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
        suggested_actions: [
          {
            type: "inspect_drill",
            label: "继续下钻期限桶",
            payload: {
              dimension: "tenor_bucket",
              page_context: {
                page_id: "risk-dashboard",
              },
            },
            requires_confirmation: true,
          },
          {
            type: "inspect_lineage",
            label: "查看血缘",
            payload: {
              trace_id: "tr_1",
              tables_used: ["fact_risk_tensor"],
            },
            requires_confirmation: true,
          },
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
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(
      await screen.findByText("组合久期风险主要集中在 3Y-5Y。"),
    ).toBeInTheDocument();
    expect(screen.getByText("组合久期")).toBeInTheDocument();
    expect(screen.getByText("4.27")).toBeInTheDocument();
    expect(screen.getAllByText("久期").length).toBeGreaterThan(0);
    expect(screen.getByText("证据链")).toBeInTheDocument();
    expect(
      screen.getByText(/表：fact_risk_tensor, dim_portfolio/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/筛选：\{"currency_basis":"CNY"\}/),
    ).toBeInTheDocument();
    expect(screen.getByText(/行数：42/)).toBeInTheDocument();
    expect(screen.getByText(/质量：ok/)).toBeInTheDocument();
    expect(screen.getByText("按组合下钻")).toBeInTheDocument();
    expect(screen.getByText("按期限桶下钻")).toBeInTheDocument();
    expect(screen.getByText("建议动作")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "继续下钻期限桶" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "查看血缘" })).toBeInTheDocument();
    expect(screen.getAllByText("需确认后执行")).toHaveLength(2);
    expect(screen.getByText(/inspect_drill/)).toBeInTheDocument();
    expect(screen.getByText(/inspect_lineage/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "继续下钻期限桶" }));
    expect(screen.getByPlaceholderText(AGENT_PLACEHOLDER)).toHaveValue(
      "请基于当前 evidence 继续下钻：继续下钻期限桶",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("动作载荷 / 血缘信息")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "查看血缘" }));
    expect(screen.getByText("动作载荷 / 血缘信息")).toBeInTheDocument();
    expect(screen.getAllByText(/fact_risk_tensor/).length).toBeGreaterThanOrEqual(2);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    expect(screen.getByText("结果元信息")).toBeInTheDocument();
    expect(screen.getByText(/追踪编号: tr_1/)).toBeInTheDocument();
    expect(screen.getByText(/口径: 正式口径/)).toBeInTheDocument();
    expect(screen.getByText(/生成时间: 2026-04-12T09:00:00Z/)).toBeInTheDocument();

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
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(
      await screen.findByText("本次查询未返回可展示结果。请调整问题后重试。"),
    ).toBeInTheDocument();
    expect(screen.getByText(/追踪编号: tr_empty/)).toBeInTheDocument();
  });

  it("submits the conversation with Enter and keeps Shift+Enter as a newline", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      buildJsonResponse({
        answer: "已收到对话问题。",
        cards: [],
        evidence: {
          tables_used: [],
          filters_applied: {},
          evidence_rows: 0,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_enter_submit",
          basis: "formal",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    const input = screen.getByLabelText("agent-question-input");
    await user.type(input, "第一行{Shift>}{Enter}{/Shift}第二行");
    expect(input).toHaveValue("第一行\n第二行");
    expect(fetchMock).not.toHaveBeenCalled();

    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
    const [, options] = fetchMock.mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      question: "第一行\n第二行",
    });
  });
});
