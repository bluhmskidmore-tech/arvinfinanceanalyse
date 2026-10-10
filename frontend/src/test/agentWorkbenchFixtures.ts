/**
 * AgentWorkbenchPage 测试的共享 fixture：DOM 打开器、请求桩、AgentEnvelope 构造器
 * 与统一的 ApiClientProvider 渲染入口。按关注点拆分出的各 AgentWorkbench*.test.tsx
 * 都从这里取同一份构造器，保证拆分前后用例行为一致。
 */
import { fireEvent, render as rtlRender, screen } from "@testing-library/react";
import { resolve } from "node:path";
import { createElement, type ReactElement } from "react";
import { vi } from "vitest";

import { createRealAgentClient } from "../api/agentClient";
import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { AgentModelCatalog } from "../api/contracts/agent";
import {
  AGENT_COMPOSER_DRAFT_KEY as LEGACY_AGENT_COMPOSER_DRAFT_KEY,
  AGENT_CONVERSATION_TURNS_KEY as LEGACY_AGENT_CONVERSATION_TURNS_KEY,
  AGENT_QUEUED_QUERIES_KEY as LEGACY_AGENT_QUEUED_QUERIES_KEY,
  getScopedAgentWorkbenchStorageKey,
  LATEST_AGENT_RUN_ID_KEY as LEGACY_LATEST_AGENT_RUN_ID_KEY,
  PINNED_REPO_PATHS_KEY as LEGACY_PINNED_REPO_PATHS_KEY,
  RECENT_REPO_PATHS_KEY as LEGACY_RECENT_REPO_PATHS_KEY,
} from "../features/agent/lib/agentWorkbenchStorage";

export const RECENT_REPO_PATHS_KEY = getScopedAgentWorkbenchStorageKey(LEGACY_RECENT_REPO_PATHS_KEY);
export const PINNED_REPO_PATHS_KEY = getScopedAgentWorkbenchStorageKey(LEGACY_PINNED_REPO_PATHS_KEY);
export const LATEST_AGENT_RUN_ID_KEY = getScopedAgentWorkbenchStorageKey(LEGACY_LATEST_AGENT_RUN_ID_KEY);
export const AGENT_CONVERSATION_TURNS_KEY = getScopedAgentWorkbenchStorageKey(
  LEGACY_AGENT_CONVERSATION_TURNS_KEY,
);
export const AGENT_COMPOSER_DRAFT_KEY = getScopedAgentWorkbenchStorageKey(LEGACY_AGENT_COMPOSER_DRAFT_KEY);
export const AGENT_QUEUED_QUERIES_KEY = getScopedAgentWorkbenchStorageKey(LEGACY_AGENT_QUEUED_QUERIES_KEY);

export const AGENT_WORKBENCH_CSS_PATH = resolve(process.cwd(), "src/features/agent/AgentWorkbenchPage.css");
export const AGENT_PLACEHOLDER =
  "问问 MOSS";
export const PAGE_CONTEXT_PLACEHOLDER =
  "问当前页：主要结论？异常点？下一步复核什么？";
export const GITNEXUS_STATUS_BUTTON = "GitNexus 状态";
export const GITNEXUS_CONTEXT_BUTTON = "GitNexus 上下文";
export const GITNEXUS_PROCESSES_BUTTON = "GitNexus 流程";
export const AGENT_RUNTIME_STATUS_LABEL = "Agent 连接状态";
export const AGENT_QUESTION_INPUT_LABEL = "向 Agent 提问";
export const AGENT_CONVERSATION_LABEL = "Agent 对话记录";
export const AGENT_RESULT_DETAILS_LABEL = "回答依据与运行信息";
export const AGENT_ANSWER_ACTIONS_LABEL = "回答操作";
export const AGENT_FOLLOW_UP_SUGGESTIONS_LABEL = "继续追问";
export const AGENT_RESEARCH_SHORTCUTS_LABEL = "研究快捷入口";
export const AGENT_FINANCIAL_WORKFLOWS_LABEL = "金融工作流";
export const AGENT_DISABLED_STATUS_LABEL = "Agent 暂不可用";
export const AGENT_RESTORE_STATUS_LABEL = "正在恢复上次回答";
export const AGENT_RESTORE_ERROR_LABEL = "上次回答恢复失败";
export const PROCESS_SEARCH_LABEL = "流程搜索";
export const PROCESS_NAME_LABEL = "流程名称";
export const REPO_PATH_LABEL = "GitNexus 仓库路径";
export const MAX_PINNED_REPO_PATHS = 5;
export const LOCAL_ANALYSIS_PAGE_CONTEXT = {
  page_id: "dashboard",
  current_filters: { report_date: "2026-03-31" },
  selected_rows: [{ portfolio_id: "core" }],
};

export function openGitNexusTools() {
  const summary = screen.getByLabelText("高级工具", { selector: "summary" });
  const details = summary.closest("details");
  if (!details?.hasAttribute("open")) {
    fireEvent.click(summary);
  }
  return details;
}

export function openProcessTools() {
  const summary = screen.getByText(/流程筛选与查看/);
  const details = summary.closest("details");
  if (!details?.hasAttribute("open")) {
    fireEvent.click(summary);
  }
  return details;
}

export function openShortcutDrawer() {
  const summary = screen.getByText("常用入口", { selector: "summary *" });
  const details = summary.closest("details");
  if (!details?.hasAttribute("open")) {
    fireEvent.click(summary);
  }
  return details;
}

export function mockNarrowAgentViewport() {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: query.includes("max-width: 720px"),
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    })),
  );
}

export type ScrollIntoViewArg = boolean | ScrollIntoViewOptions;

export function mockScrollIntoView(implementation: (this: HTMLElement, options?: ScrollIntoViewArg) => void) {
  const originalDescriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollIntoView");
  if (!originalDescriptor || typeof originalDescriptor.value !== "function") {
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      writable: true,
      value: () => undefined,
    });
  }

  const spy = vi.spyOn(HTMLElement.prototype, "scrollIntoView").mockImplementation(implementation);
  return {
    restore() {
      spy.mockRestore();
      if (originalDescriptor) {
        Object.defineProperty(HTMLElement.prototype, "scrollIntoView", originalDescriptor);
      } else {
        Reflect.deleteProperty(HTMLElement.prototype, "scrollIntoView");
      }
    },
  };
}

export function buildJsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function buildManagedRunPayload(result: unknown, runId = "agent_run:test", provider = "hermes") {
  return {
    run_id: runId,
    status: "completed",
    provider,
    model: "gpt-5.5",
    transport: "bridge",
    toolsets: "file",
    elapsed_seconds: 1,
    result,
  };
}

export function buildAgentWorkbenchClient(
  fetchImpl: ReturnType<typeof vi.fn>,
  modelCatalog?: AgentModelCatalog,
): ApiClient {
  return {
    ...createApiClient({ mode: "mock" }),
    ...createRealAgentClient({
      fetchImpl: fetchImpl as unknown as typeof fetch,
      baseUrl: "",
    }),
    getAgentModels: async () => modelCatalog ?? ({
      provider: "hermes",
      default_model: "",
      models: [],
      source: "configured",
    }),
  };
}

export function mockManagedRunResult(
  fetchMock: ReturnType<typeof vi.fn>,
  result: unknown,
  runId = "agent_run:test",
  provider = "hermes",
) {
  fetchMock
    .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: runId,
          status: "queued",
          provider,
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          queued_at: "2026-05-07T08:00:00Z",
        }),
      )
    .mockResolvedValueOnce(buildJsonResponse(buildManagedRunPayload(result, runId, provider)));
}

export function getQueuedFollowUpStatus() {
  return screen.getByRole("status", { name: "待发送的下一句" });
}

export function queryQueuedFollowUpStatus() {
  return screen.queryByRole("status", { name: "待发送的下一句" });
}

export function getAgentTurnStatus() {
  const status = screen.getAllByRole("status", { name: /回答状态/ }).at(-1);
  if (!status) {
    throw new Error("Expected at least one agent turn status");
  }
  return status;
}

export function getWaitStatusStopAction() {
  const stopAction = document.querySelector<HTMLButtonElement>(".agent-wait-status__stop");
  if (!stopAction) {
    throw new Error("Expected wait status stop action");
  }
  return stopAction;
}

export function getRetryTurnAction(question: string) {
  const action = screen.getByLabelText(`重试这一轮：${question}`);
  if (!(action instanceof HTMLButtonElement)) {
    throw new Error(`Expected retry action for ${question}`);
  }
  return action;
}

export async function findAgentTurnStatus() {
  const statuses = await screen.findAllByRole("status", { name: /回答状态/ });
  const status = statuses.at(-1);
  if (!status) {
    throw new Error("Expected at least one agent turn status");
  }
  return status;
}

export function buildWorkflowExecutionResult() {
  return {
    answer:
      "Executed financial workflow 'Risk Memo' (risk_memo) using governed MOSS intents: duration_risk, credit_exposure, risk_tensor. The workflow summary is not a formal financial result.",
    cards: [
      {
        title: "Workflow Execution Steps",
        type: "table",
        data: [
          {
            order: 1,
            intent: "duration_risk",
            status: "completed",
            quality: "ok",
            evidence_rows: 3,
          },
        ],
        spec: {
          columns: ["order", "intent", "status", "quality", "evidence_rows"],
        },
      },
      {
        title: "Mapped Intent Results",
        type: "table",
        data: [
          {
            intent: "duration_risk",
            result_kind: "agent.intent.duration_risk",
            answer: "Duration risk ready.",
            tables: "fact_risk_tensor",
            evidence_rows: 3,
          },
        ],
        spec: {
          columns: ["intent", "result_kind", "answer", "tables", "evidence_rows"],
        },
      },
    ],
    evidence: {
      tables_used: ["fact_risk_tensor"],
      filters_applied: {},
      evidence_rows: 3,
      quality_flag: "warning",
    },
    result_meta: {
      trace_id: "tr_workflow_risk_memo",
      basis: "formal",
      result_kind: "agent.workflow.risk_memo",
      formal_use_allowed: false,
      source_version: "sv_agent_financial_workflow_reference",
      rule_version: "rv_agent_financial_workflow_catalog_v1",
    },
    next_drill: [],
    suggested_actions: [],
  };
}

export function buildLocalOrdinaryTextResult(answer = "本地普通问题回答。") {
  return {
    answer,
    cards: [],
    evidence: {
      tables_used: ["agent_query_local"],
      filters_applied: {
        provider: "local",
        transport: "sync",
        model: "default",
        toolsets: "default",
      },
      evidence_rows: 1,
      quality_flag: "ok",
    },
    result_meta: {
      trace_id: "tr_local_sync_query",
      basis: "formal",
      result_kind: "agent.local",
    },
    next_drill: [],
    suggested_actions: [],
  };
}

export function buildLocalAnalysisChatResult() {
  return {
    answer: "本地分析对话已接住这轮问题，但未运行正式指标查询。",
    cards: [
      {
        type: "status",
        title: "本地分析对话",
        value: "未匹配受治理指标 intent，本地 Agent 未运行正式指标查询。",
      },
      {
        type: "context",
        title: "已捕获上下文",
        data: {
          page_id: "dashboard",
          report_date: "2026-03-31",
        },
      },
    ],
    evidence: {
      tables_used: [],
      filters_applied: {
        page_id: "dashboard",
        report_date: "2026-03-31",
      },
      evidence_rows: 0,
      quality_flag: "warning",
    },
    result_meta: {
      trace_id: "tr_agent_analysis_chat",
      basis: "formal",
      result_kind: "agent.analysis_chat",
      formal_use_allowed: false,
    },
    next_drill: [],
    suggested_actions: [
      {
        type: "execute_intent",
        label: "组合概览",
        payload: { intent: "portfolio_overview" },
        requires_confirmation: true,
        confirmation_token: "agent_action:test-token-portfolio-overview",
      },
    ],
  };
}

export function buildGovernedPortfolioOverviewResult() {
  return {
    answer: "正式组合概览结果：资产规模和风险摘要已返回。",
    cards: [
      {
        type: "metric",
        title: "Total Market Value",
        value: "1000",
      },
    ],
    evidence: {
      tables_used: ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
      filters_applied: {
        report_date: "2026-03-31",
      },
      evidence_rows: 3,
      quality_flag: "ok",
    },
    result_meta: {
      trace_id: "tr_agent_portfolio_overview",
      basis: "formal",
      result_kind: "agent.portfolio_overview",
      formal_use_allowed: true,
    },
    next_drill: [],
    suggested_actions: [],
  };
}

export function buildDexterResearchResult(domain: "stock" | "macro", answer: string) {
  const tableName = domain === "stock" ? "choice_stock_daily_observation" : "fact_choice_macro_daily";
  return {
    answer,
    cards: [
      {
        title: "Research Summary",
        type: "summary",
        value: `${domain} context ready`,
      },
    ],
    evidence: {
      tables_used: [tableName],
      filters_applied: {
        provider: "dexter",
        transport: "sync",
        model: "gpt-5.5",
        toolsets: "file",
        research_domain: domain,
      },
      evidence_rows: 1,
      quality_flag: "ok",
    },
    result_meta: {
      trace_id: `tr_dexter_${domain}`,
      basis: "formal",
      result_kind: "agent.dexter",
      formal_use_allowed: false,
    },
    next_drill: [],
    suggested_actions: [],
  };
}

export function buildResearchRadarResult() {
  return {
    answer: "解释：当前事件先看利率与信用线索，再决定是否进入正式风险检查。",
    cards: [
      {
        title: "边界说明",
        type: "notice",
        value: "分析口径 / 非正式指标 / 非投资建议 / 需人工确认后再进入情景测算",
      },
      {
        title: "原始事件证据",
        type: "table",
        data: [
          {
            received_at: "2026-06-22T09:00:00Z",
            topic_code: "rates",
            headline: "央行表态引发利率预期调整",
            event_key: "evt-1",
          },
        ],
        spec: {
          columns: ["received_at", "topic_code", "headline", "event_key"],
        },
      },
      {
        title: "重点观察",
        type: "table",
        data: [
          {
            lens: "利率",
            review_needed: "确认是否改变利率路径、期限结构或久期暴露假设。",
          },
        ],
        spec: {
          columns: ["lens", "review_needed"],
        },
      },
      {
        title: "跨篇对比",
        type: "table",
        data: [
          {
            bucket: "same_direction",
            event_family: "rates",
            summary: "rates 相关事件按同一规则命中，需人工判断方向是否一致。",
          },
        ],
        spec: {
          columns: ["bucket", "event_family", "summary"],
        },
      },
      {
        title: "候选情景建议",
        type: "table",
        data: [
          {
            event_family: "rates",
            factor_tags: ["rate", "duration"],
            scenario_template_id: "candidate_rate_path_review",
            default_shocks: ["parallel_up_25bp_candidate"],
            human_review_required: true,
            source_event_ids: ["evt-1"],
          },
        ],
        spec: {
          columns: [
            "event_family",
            "factor_tags",
            "scenario_template_id",
            "default_shocks",
            "human_review_required",
            "source_event_ids",
          ],
        },
      },
      {
        title: "下一步检查",
        type: "link_list",
        data: [
          {
            label: "新闻事件",
            href: "/news-events",
            description: "回看原始事件、主题归类和明细来源。",
          },
        ],
        spec: {
          columns: ["label", "href", "description"],
        },
      },
    ],
    evidence: {
      tables_used: ["choice_news_event"],
      filters_applied: {
        provider: "local",
        transport: "sync",
        model: "moss_local",
        toolsets: "research_radar",
        intent: "research_radar_brief",
      },
      evidence_rows: 1,
      quality_flag: "ok",
    },
    result_meta: {
      trace_id: "tr_agent_research_radar",
      basis: "analytical",
      result_kind: "agent.research_radar_brief",
      formal_use_allowed: false,
      scenario_flag: false,
    },
    next_drill: [{ dimension: "route", label: "/news-events" }],
    suggested_actions: [],
  };
}

/** 统一渲染入口：所有拆分文件共用同一套 Agent ApiClient 装配。 */
export function renderWithAgentClient(
  fetchMock: ReturnType<typeof vi.fn>,
  ui: ReactElement,
  options?: Parameters<typeof rtlRender>[1],
  modelCatalog?: AgentModelCatalog,
) {
  return rtlRender(
    createElement(ApiClientProvider, {
      client: buildAgentWorkbenchClient(fetchMock, modelCatalog),
      children: ui,
    }),
    options,
  );
}
